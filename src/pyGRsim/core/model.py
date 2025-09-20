
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
import re
import json
from copy     import deepcopy
from types    import SimpleNamespace
from typing   import Iterable
from datetime import datetime

# third-party modules
import pandas as pd

# local modules
import idragon
from idragon       import dragon
from idragon.utils import (
    validate_range,
    validate_type ,
    SMALLEST_VALUE,
)
from ..constants import (
    Directory  ,
    Unit       ,
    Site2Source,
    Site2Cost  ,
    Site2CO2   ,
    SpecialTag ,
)
from . import (
    # construction
    Material                ,
    SurfaceConstruction     ,
    OpenConsruction         ,
    UnknownConstruction     ,
    FenestrationConstruction,
    # profile
    DaySchedule,
    RuleSet    ,
    Schedule   ,
    Profile    ,
    # hvac
    Fuel,
    SourceSystem      ,
    Boiler            ,
    DistrictHeating   ,
    SupplySystem      ,
    VentilationSystem ,
    PhotoVoltaicSystem,
    NoneSource        ,
    # shape
    Surface                 ,
    SurfaceType             ,
    SurfaceBoundaryCondition,
    Zone                    ,
)
from ..utils import (
    excel2grjson,
)


# ---------------------------------------------------------------------------- #
#                                   VARIABLES                                  #
# ---------------------------------------------------------------------------- #

ADDR_WEATHER_TABLE = pd.read_csv(os.path.join(Directory.WEATHER, "행정구역별기상데이터.csv")).set_index("행정구역명")
CLIMATE_TABLE      = pd.read_csv(os.path.join(Directory.WEATHER, "기후지역.csv"          )).set_index("행정구역명")

# ---------------------------------------------------------------------------- #
#                                  EXCEPTIONS                                  #
# ---------------------------------------------------------------------------- #

class InvalidAddressError(Exception):
    pass

class UnexpectedEnergyPlusRunResultError(Exception):
    
    def __init__(self, err:pd.DataFrame):
        
        err_message = "===EnergyPlusError===\n" +\
                      "\n".join(err.query("type=='Severe' | type=='Fatal'")["title"].values)
                      
        super().__init__(err_message)
        

# ---------------------------------------------------------------------------- #
#                             GRIM SIMULATOR MODEL                             #
# ---------------------------------------------------------------------------- #

def address_to_weather(
    address:str     ,
    vintage:datetime,
    ) -> tuple[str, str, str]:
    
    sigungu_match = re.search(r"^[\w ]+[시군구](?= |$)", address)
    if sigungu_match is None:
        raise InvalidAddressError(
            f"Cannot find '시' or '군' or '구' from '{address}'"
        )
    
    sigungu = sigungu_match.group(0)
    sigungu_info = ADDR_WEATHER_TABLE.loc[sigungu]
    
    terrain = sigungu_info["terrain"]
    weather_location = sigungu_info["기상지역명"]
    weather_filepath = os.path.join(idragon.constants.Directory.WEATHER, sigungu_info["EPW파일명"])
    
    climate = CLIMATE_TABLE.at[sigungu, max(datestr for datestr in CLIMATE_TABLE.columns if datestr < vintage.strftime(r"%Y%m%d"))]
    
    return terrain, climate, weather_location, weather_filepath


class GreenRetrofitModel:
    
    def __init__(self,
        name      :str,
        address   :str,
        vintage   :list[int]|datetime  ,
        north_axis:int|float =0         ,
        zone      :list[Zone]=[],
        pv        :list[PhotoVoltaicSystem]=[],
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.vintage   =vintage
        self.address   =address
        self.north_axis=north_axis
        
        # childrens
        self.zone=zone
        self.pv  =pv
        
        # initialization
        self.__supply_system = []
    
    """ address related
    """
    
    @property
    def address(self) -> str:
        return self.__address
    
    @address.setter
    def address(self, value:str) -> None:
        
        terrain, climate, weather_location, weather_filepath = address_to_weather(value, self.vintage)
        
        self.__terrain = terrain
        self.__climate = climate
        self.__weather = weather_location
        self.__weather_filepath = weather_filepath
        self.__address = value       
        
        return
    
    @property
    def climate(self) -> str:
        return self.__climate
    
    @property
    def terrain(self) -> str:
        return self.__terrain
    
    @property
    def weather(self) -> str:
        return self.__weather
    
    @property
    def weather_filepath(self) -> str:
        return self.__weather_filepath
    
    """ other fundamental properties
    """
    
    @property
    def vintage(self) -> datetime:
        return self.__vintage
    
    @vintage.setter
    def vintage(self, value: datetime|list[int]) -> None:
        
        if not isinstance(value, datetime):
            try:
                value = datetime(*tuple(value))
            except:
                raise ValueError(
                    f"Cannot convert {value} to datetime."
                )
                
        self.__vintage = value
        
    @property
    def north_axis(self) -> int|float:
        return self.__north_axis
    
    @north_axis.setter
    @validate_range(min=0, max=360-SMALLEST_VALUE)
    @validate_type(int, float)
    def north_axis(self, value: int|float) -> None:
        self.__north_axis = value
        
    """ additional properties
    """
        
    @property
    def supply_system(self) -> list[SupplySystem]:
        
        heating_supplies = {
            zone.heating_supply.source.ID: zone.heating_supply.source
            for zone in self.zone
            if isinstance(zone.heating_supply, SupplySystem) and not isinstance(zone.heating_supply, NoneSource)
        }
        
        cooling_supplies = {
            zone.cooling_supply.source.ID: zone.cooling_supply.source
            for zone in self.zone
            if isinstance(zone.cooling_supply, SupplySystem) and not isinstance(zone.cooling_supply, NoneSource)
        }
        
        unique_supplies = list((heating_supplies|cooling_supplies).values())
        
        return self.__supply_system + unique_supplies
    
    @supply_system.setter
    def supply_system(self, value:list[SupplySystem]):
        
        if not isinstance(value, Iterable) and not all(isinstance(item, SupplySystem) for item in value):
            raise ValueError(
                f"Supply system of a GreenRetrofitModel instance should be an iterable instance of SupplySystem(s)."
            )
        
        self.__supply_system = list(value)
    
    @property
    def hotwater_demand(self) -> list[float]:
        
        demand = [0]*12    
        for zone in self.zone:
            zone_use = [v*zone.area for v in zone.profile.hotwater]
            demand = [base+v for base, v in zip(demand, zone_use)]
        
        return demand
    
    @property
    def area(self) -> float:
        return sum(zone.area for zone in self.zone)
    
    """ useful methods (unique components)
    """
    
    def get_unique_fenestration_constructions(self) -> dict[str, FenestrationConstruction]:
        
        return {
            k: v
            for zone in self.zone
            for k, v in zone.get_unique_fenestraion_constructions().items()
        }
    
    def get_unique_surface_constructions(self) -> dict[str, SurfaceConstruction]:
        
        return {
            k:v
            for zone in self.zone
            for k,v in zone.get_unique_surface_constructions().items()
        }
        
    def get_unique_materials(self) -> dict[str, Material]:
        
        return {
            k:v
            for construction in self.get_unique_surface_constructions().values()
            for k,v in construction.get_unique_materials().items()
        }
        
    def get_unique_profiles(self) -> dict[str, Profile]:
        
        return {
            zone.profile.ID: zone.profile
            for zone in self.zone
        }
    
    def get_unique_schedules(self) -> dict[str, Schedule]:
        
        return {
            k:v
            for profile in self.get_unique_profiles().values()
            for k,v in profile.get_unique_schedules().items()
        }
        
    def get_unique_rulesets(self) -> dict[str, RuleSet]:
        
        return {
            k:v
            for schedule in self.get_unique_schedules().values()
            for k,v in schedule.get_unique_rulesets().items()
        }
        
    def get_unique_day_schedules(self) -> dict[str, DaySchedule]:
        
        return {
            k:v
            for ruleset in self.get_unique_rulesets().values()
            for k,v in ruleset.get_unique_day_schedules().items()
        }
    
    """ model in-out
    """
    
    @classmethod
    def from_grjson(cls, filepath:str) -> GreenRetrofitModel:
        
        # read the json file
        with open(filepath, encoding="UTF-8") as f:
            input = json.load(f, object_hook=lambda d: SimpleNamespace(**d))
        
        # building info.
        name       = input.building.name
        address    = input.building.address
        vintage    = input.building.vintage
        north_axis = input.building.north_axis
        
        # create a green-retrofit-model
        grm = cls(
            name      ,
            address   ,
            vintage   ,
            north_axis,
        )
        
        # construction
        material_dict = {
            material_input.id: Material.from_json(material_input)
            for material_input in input.materials
        }
        surface_construction_dict = {
            construction_input.id: SurfaceConstruction.from_json(construction_input, material_dict)
            for construction_input in input.surface_constructions
        }
        fenestration_construction_dict = {
            fenestration_input.id: FenestrationConstruction.from_json(fenestration_input)
            for fenestration_input in input.fenestration_constructions
        }
        
        # special constructions
        surface_construction_dict["open"]    = OpenConsruction()
        surface_construction_dict["unknown"] = UnknownConstruction()
        
        # profile
        day_schedule_dict = {
            day_schedule_input.id: DaySchedule.from_json(day_schedule_input)
            for day_schedule_input in input.profile_components.day_schedules
        }
        ruleset_dict = {
            ruleset_input.id: RuleSet.from_json(ruleset_input, day_schedule_dict)
            for ruleset_input in input.profile_components.rulesets
        }
        schedule_dict = {
            schedule_input.id: Schedule.from_json(schedule_input, ruleset_dict)
            for schedule_input in input.profile_components.schedules
        }
        profile_dict = {
            profile_input.id: Profile.from_json(profile_input, schedule_dict)
            for profile_input in input.profiles
        }
        
        # system
        source_system_dict = {
            system_input.id: SourceSystem.from_json(system_input)
            for system_input in input.building.source_systems
        }
        supply_system_dict = {
            system_input.id: SupplySystem.from_json(system_input, source_system_dict)
            for system_input in input.building.supply_systems
        }
        ventilation_system_dict = {
            ventilation_input.id: VentilationSystem.from_json(ventilation_input)
            for ventilation_input in input.building.ventilation_systems
        }
        photovoltaic_systems = {
            photovoltaic_input.id: PhotoVoltaicSystem.from_json(photovoltaic_input)
            for photovoltaic_input in input.building.photovoltaic_systems
        }
        
        # zone
        grm.zone = [
            Zone.from_json(
                zone_input                    ,
                surface_construction_dict     ,
                fenestration_construction_dict,
                profile_dict                  ,
                supply_system_dict            ,
                ventilation_system_dict       ,
                floor=floor_input.floor_number,
            )
            for floor_input in input.building.floors
            for zone_input  in floor_input.zones
        ]
        
        # add unused source systems
        # please refer to the definition of the supply_system property
        applied_ID = (supply.ID for supply in grm.supply_system)
        grm.supply_system = [sys for sys in source_system_dict.values() if sys.ID not in applied_ID]
        
        # pv panel
        grm.pv = list(photovoltaic_systems.values())
        
        # allocate adjacent zone information
        zone_dict = {zone.ID: zone for zone in grm.zone}
        surf_dict = {surf.ID: surf for zone in grm.zone for surf in zone.surface}
        for floor_input in input.building.floors:
            for zone_input in floor_input.zones:
                for surf_input in zone_input.surfaces:
                    if surf_input.boundary_condition == "zone":
                        surf_dict[surf_input.id].adjacent_zone = zone_dict[surf_input.adjacent_zone_id]
        
        return grm
    
    @classmethod
    def from_excel(cls, filepath:str) -> GreenRetrofitModel:
        
        _, json_path = excel2grjson(filepath)
        
        try:
            grm = cls.from_grjson(json_path)
            
        finally:
            os.remove(json_path)
        
        return grm
    
    def _dragonize_surface(self,
        surface_construction_dict     :dict[str, dragon.Construction],
        fenestration_construction_dict:dict
        ) -> dict[str, list[dragon.Surface]]:
        
        # collect surfaces
        surfaces_by_zone = {
            zone.ID: zone.surface
            for zone in self.zone
        }
        surface_dict = {
            surface.ID: surface
            for surface in sum(surfaces_by_zone.values(), start=[])
        }
        
        # allocate unknowns
        unknown_surfaces = []
        for surface in surface_dict.values():
            if surface.construction is UnknownConstruction():
                unknown_surfaces.append(surface)
                regulated_construction = SurfaceConstruction.get_regulated_construction(
                    self.vintage    ,
                    surface.type    ,
                    surface.boundary,
                    self.climate    ,
                    is_residential=False,
                )
                surface.construction = regulated_construction
                
                dragonized_construction = regulated_construction.to_dragon()
                surface_construction_dict[dragonized_construction.name] = dragonized_construction
        
        # duplicate surfaces by adjacency
        adjacent_pair       = dict()
        copied_surface_dict = dict()
        for surface in surface_dict.values():
            if surface.boundary == SurfaceBoundaryCondition.ZONE:
                
                adjacent_surface = surface.flip()
                    
                surfaces_by_zone[surface.adjacent_zone.ID].append(adjacent_surface)
                copied_surface_dict[adjacent_surface.ID] = adjacent_surface
                adjacent_pair[surface.ID] = adjacent_surface.ID
                
                reversed_construction = surface.constrcution.reversed()
                adjacent_surface.construction = reversed_construction
                
                dragonized_construction = reversed_construction.to_dragon()
                surface_construction_dict[dragonized_construction.name] = dragonized_construction
        surface_dict |= copied_surface_dict
        
        # create special constructions for coolroof
        # allocation of the coolroof construction is handled in Surface.to_dragon
        for surface in surface_dict.values():
            if surface.reflectance is not None:
                
                # get original construction
                original_construction = surface_construction_dict[surface.construction.ID]
                
                # create coolroof layer (outside layer)
                coolroof_layer = dragon.Layer(
                    f"{SpecialTag.COOLROOF}{original_construction.layers[0].name}",
                    dragon.Material(
                        f"{SpecialTag.COOLROOF}{original_construction.layers[0].material.name}",
                        original_construction.layers[0].material.conductivity,
                        original_construction.layers[0].material.density,
                        original_construction.layers[0].material.specific_heat,
                        solar_absorptance  =1 - surface.refelectance,
                        thermal_absorptance=1 - surface.refelectance,
                    ),
                    original_construction.layers[0].thickness
                )
                
                # create coolroof construction and save to the dictionary
                coolroof_construction = dragon.Construction(
                    f"{SpecialTag.COOLROOF}{original_construction.name}",
                    coolroof_layer, *original_construction.layers[1:]
                )
                surface_construction_dict[coolroof_construction.name] = coolroof_construction
        
        # dragonize
        dragonized_surfaces_by_zone = {
            zone_id: [
                v.to_dragon(
                    zone.height,
                    surface_construction_dict     ,
                    fenestration_construction_dict,
                )
                for v in surface_list
            ]
            for zone, (zone_id, surface_list) in zip(self.zone, surfaces_by_zone.items())
        }
        
        # allocate adjacent surfaces
        dragonized_surface_dict = {
            surface.name: surface
            for surface in sum(dragonized_surfaces_by_zone.values(), start=[])
        }
        for ID in adjacent_pair.keys():
            dragonized_surface_dict[ID].boundary = dragonized_surface_dict[adjacent_pair[ID]]
        
        # reset allocated unknowns
        for surface in unknown_surfaces:
            surface.construction = UnknownConstruction()
        
        return dragonized_surfaces_by_zone
    
    def to_dragon(self):
        
        # construction
        material_dict = {
            k: v.to_dragon()
            for k,v in self.get_unique_materials().items()
        }
        surface_construction_dict = {
            k: v.to_dragon(material_dict=material_dict)
            for k, v in self.get_unique_surface_constructions().items()
            if not isinstance(v, UnknownConstruction)
        }
        fenestration_construction_dict = {
            k: v.to_dragon()
            for k, v in self.get_unique_fenestration_constructions().items()
        }
        
        # profile
        day_schedule_dict = {
            k: v.to_dragon()
            for k, v in self.get_unique_day_schedules().items()
        }
        ruleset_dict = {
            k: v.to_dragon(day_schedule_dict=day_schedule_dict)
            for k, v in self.get_unique_rulesets().items()
        }
        schedule_dict = {
            k: v.to_dragon(ruleset_dict=ruleset_dict)
            for k, v in self.get_unique_schedules().items()
        }
        profile_dict = {
            k: v.to_dragon(schedule_dict=schedule_dict)
            for k, v in self.get_unique_profiles().items()
        }
        
        # surface
        dragonized_surfaces = self._dragonize_surface(
            surface_construction_dict     ,
            fenestration_construction_dict,
        )
        
        # source / supply system
        supply_dict = dict()
        source_dict = dict()
        for zone in self.zone:
            
            if zone.heating_supply is not None:
                
                if not isinstance(zone.heating_supply.source, NoneSource) and (zone.heating_supply.source.ID not in source_dict.keys()):
                    source_dict[zone.heating_supply.source.ID] = zone.heating_supply.source.to_dragon()
                supply_dict[zone.heating_supply.ID] = zone.heating_supply.to_dragon(source_dict)
                
            if zone.cooling_supply is not None:
                
                if not isinstance(zone.cooling_supply.source, NoneSource) and (zone.cooling_supply.source.ID not in source_dict.keys()):
                    source_dict[zone.cooling_supply.source.ID] = zone.cooling_supply.source.to_dragon()
                supply_dict[zone.cooling_supply.ID] = zone.cooling_supply.to_dragon(source_dict)
        
        # ventilation system
        ventilator_dict = {
            zone.ventilation_system.ID: zone.ventilation_system.to_dragon()
            for zone in self.zone
            if zone.ventilation_system is not None
        }
        
        # photovoltaic system
        pv_dict = {
            pv.ID: pv.to_dragon()
            for pv in self.pv
        }
        
        # model
        em = idragon.EnergyModel(
            self.name      ,
            self.north_axis,
            self.terrain   ,
            [
                dragon.Zone(
                    zone.ID,
                    dragonized_surfaces[zone.ID],
                    profile_dict[zone.profile.ID],
                    zone.infiltration*Unit.ACH502ACH,
                    zone.light_density,
                    supply_dict.get(getattr(zone.cooling_supply,"ID",None), None),
                    supply_dict.get(getattr(zone.heating_supply,"ID",None), None),
                    ventilator_dict.get(getattr(zone.ventilation_system,"ID", None), None)
                )
                for zone in self.zone
            ],
            pv=list(pv_dict.values())
        )
        
        return em
    
    def to_idf(self):
        em  = self.to_dragon()
        idf = em.to_idf()
        return idf
        
    """ run
    """
    
    def run(self) -> idragon.EnergyPlusResult:
        
        idf  = self.to_idf()
        result = idf.run(self.weather_filepath)
        
        return GreenRetrofitResult(
            self  ,
            result,
        )


class GreenRetrofitResult:
    
    def __init__(self,
        model :GreenRetrofitModel,
        result:idragon.EnergyPlusResult
        ) -> None:
        
        self.model  = model
        self.result = result
        
        if result.tbl is None:
            raise UnexpectedEnergyPlusRunResultError(self.result.err)
    
    @property
    def area(self) -> float:
        return self.model.area
    
    def calc_hotwater_energy(self) -> dict[str, list[float]]:
        
        # calculate hotwater demand using the applied profiles
        demand = self.model.hotwater_demand
        
        # find hotwater supply 
        hotwater_supply = [source for source in self.model.supply_system if hasattr(source, "hotwater_supply") and source.hotwater_supply]
        # if empty, add a boiler
        if len(hotwater_supply) == 0:
            DEFAULT_BOILER_EFFICIENCY_FOR_HOTWATER = 0.85
            hotwater_supply =[Boiler("HotWaterBoiler", Fuel.NATURALGAS, True, DEFAULT_BOILER_EFFICIENCY_FOR_HOTWATER, None)]
        
        # calc demand distribution for the hotwater supplies
        demand_per_supply = [v/self.area/len(hotwater_supply) for v in demand]
        
        # get hotwater energy by fuel types
        hotwater_energy = {fuel.name: [0]*12 for fuel in Fuel}
        for supply in hotwater_supply:            
            
            # case 1: district heating
            if isinstance(supply, DistrictHeating):
                
                EFFICIENCY_OF_DISTRICT_HEATING = 1.0
                hotwater_energy[Fuel.DISTRICTHEATING.name] = [
                    v_add/EFFICIENCY_OF_DISTRICT_HEATING +v_org 
                    for v_add, v_org in zip(demand_per_supply, hotwater_energy[Fuel.DISTRICTHEATING.name])
                ]
            
            # case 2: boiler 
            elif isinstance(supply, Boiler):
                hotwater_energy[Fuel(supply.fuel).name] = [
                    v_add/supply.efficiency +v_org 
                    for v_add, v_org in zip(demand_per_supply, hotwater_energy[Fuel(supply.fuel).name])
                ]
                
            else:
                raise RuntimeError("급탕이 보일러랑 바닥난방말고 또있나??")
        
        return hotwater_energy
    
    def to_site_uses(self) -> pd.DataFrame:
        
        usecol_map = {
            "heating"    : ["HEATING"],
            "cooling"    : ["COOLING"],
            "lighting"   : ["INTERIORLIGHTS","EXTERIORLIGHTS"],
            "circulation": ["FANS","PUMPS","HEATRECOVERY"],
            "hotwater"   : ["WATERSYSTEMS"],
            "generators" : []
        }
        
        fuel_name_in_energyplus = {
            Fuel.ELECTRICITY    : "Electricity",
            Fuel.NATURALGAS     : "NaturalGas" ,
            Fuel.OIL            : "FuelOil"    ,
            Fuel.DISTRICTHEATING: "OhterFuels" ,
        }
        
        df_site = pd.DataFrame(index=[v.name for v in Fuel], columns=list(usecol_map.keys())).map(lambda _: [float(0)]*12)
        for fuel_type in Fuel:
            
            # get use 
            table_name = f"EndUseEnergyConsumption{fuel_name_in_energyplus[fuel_type]}Monthly"
            df   = self.result.tbl[table_name]
            fuel = fuel_type.name
            for use in df_site.columns:
                target_cols = [col for col in df.columns if any(col.startswith(usecol) for usecol in usecol_map[use])]                
                df_site.loc[fuel,use] = list(df[target_cols].sum(axis=1)[:12].astype(float).map(lambda v: round(v/self.area, 1)))
                
        # hot water use from the profiles
        hotwater_energy_dict = self.calc_hotwater_energy()
        for fuel, energy in hotwater_energy_dict.items():
            df_site.loc[fuel, "hotwater"] = energy
        
        # PV panel production
        table_name = "EnergyConsumptionElectricityGeneratedPropaneMonthly"
        if table_name in self.result.tbl.keys():
            df_site.loc["ELECTRICITY","generators"] = self.result.tbl[table_name]["ELECTRICITYPRODUCED:FACILITY [kWh]"][:12].astype(float).map(lambda v: round(v/self.area, 1)).tolist()
        
        return df_site
    
    def to_source_uses(self) -> pd.DataFrame:
        
        df_source = deepcopy(self.to_site_uses())
        for idx, coeff in zip(df_source.index, [v.value for v in Site2Source]):
            df_source.loc[idx] = df_source.loc[idx].map(lambda l: [round(v*coeff,1) for v in l])
        
        return df_source
    
    def to_co2(self) -> pd.DataFrame:
        
        df_co2 = deepcopy(self.to_site_uses())
        for idx, coeff in zip(df_co2.index, [v.value for v in Site2CO2]):
            df_co2.loc[idx] = df_co2.loc[idx].map(lambda l: [round(v*coeff,1) for v in l])
        
        return df_co2
    
    def to_cost(self) -> pd.DataFrame:
        
        df_cost = deepcopy(self.to_site_uses())
        for idx, coeff in zip(df_cost.index, [v.value for v in Site2Cost]):
            df_cost.loc[idx] = df_cost.loc[idx].map(lambda l: [round(v*coeff,1) for v in l])
        
        return df_cost
    
    def dictionarize(self, df:pd.DataFrame) -> dict:
        
        return {
            col: {
                idx: df.loc[idx, col]
                for idx in df.index
            }
            for col in df.columns
        }
    
    def summarize(self, df:pd.DataFrame, *, gross:bool) -> dict:
        
        monthly_use = [round(sum(x),1) for x in zip(*list(df[["heating", "cooling", "lighting", "circulation", "hotwater"]].values.flatten()))]
        monthly_gen = [round(sum(x),1) for x in zip(*list(df[["generators"]].values.flatten()))]
        
        monthly_sum = [use-gen for use, gen in zip(monthly_use, monthly_gen)]
                
        if gross:
            summary = {
                "total_monthly": [round(v*self.area,1) for v in monthly_sum]           ,
                "total_annual" : round(sum(monthly_sum)*self.area,1)        ,
            }
        else:
            summary = {
                "total_monthly": monthly_sum,
                "total_annual" : round(sum(monthly_sum),1),
        } 
               
        return summary
    
    def to_dict(self) -> dict:
        
        # convert result dataframe to a dictionary tree
        result_dict = {
            "building": {
                "total_area":self.area,
            },
            "constants":{
                key:{
                    str(fuel): getattr(enum, fuel.name)
                    for fuel in tuple(Fuel)
                }
                for enum, key in zip(
                    [Site2Source  , Site2CO2  , Site2Cost  ],
                    ["site2source", "site2co2", "site2cost"],
                )
            }
        }

        # site uses
        df_site = self.to_site_uses()
        result_dict["site_uses"] = self.dictionarize(df_site)
        
        # source uses
        df_source = self.to_source_uses()
        result_dict["source_uses"] = self.dictionarize(df_source)
        
        # co2
        df_co2 = self.to_co2()
        result_dict["co2"] = self.dictionarize(df_co2)
                
        # cost
        df_cost = self.to_cost()
        result_dict["cost"] = self.dictionarize(df_cost)
        
        # summary
        result_dict["summary_per_area"] = {
            name: self.summarize(df, gross=False)
            for name, df in zip(["site_uses","source_uses","co2","cost"],[df_site, df_source, df_co2, df_cost])
        }
        result_dict["summary_gross"] = {
            name: self.summarize(df, gross=True)
            for name, df in zip(["site_uses","source_uses","co2","cost"],[df_site, df_source, df_co2, df_cost])
        }        
        
        return result_dict
    
    def write(self,
        filepath:str
        ) -> None:
        
        # dictionarize the result
        result_dict = self.to_dict()

        # write the dictionary tree as json format
        with open(filepath, "w", encoding="UTF-8") as f:
            # format the dictionrary into a json string
            json_str = json.dumps(result_dict, ensure_ascii=False, indent=4)
            # revise the multiline-list to a line
            json_str = re.sub(r"\[\s+([^\[\]]+?)\s+\]", lambda m: f"[{' '.join(m.group(1).split())}]", json_str)
            # write
            f.write(json_str)
  
        return
  