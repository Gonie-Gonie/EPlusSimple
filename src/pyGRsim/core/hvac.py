
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
from enum   import Enum
from types  import SimpleNamespace
from typing import Any

# third-party modules

# local modules
from ..idragon import dragon
from ..idragon.utils import (
    SMALLEST_VALUE,
    validate_type ,
    validate_enum ,
    validate_range,
)
from ..constants import (
    Unit      ,
    SpecialTag,
    AUTOID_PREFIX ,
)



# ---------------------------------------------------------------------------- #
#                                 SOURCE SYSTEM                                #
# ---------------------------------------------------------------------------- #

class Fuel(str, Enum):
    
    ELECTRICITY     = "electricity"
    NATURALGAS      = "natural_gas"
    OIL             = "oil"
    DISTRICTHEATING = "district_heating"
    
    def __str__(self) -> str:
        return self.value
    
    def to_dragon(self) -> dragon.Fuel:
        
        match self:
            case Fuel.ELECTRICITY:
                return dragon.Fuel.ELECTRICITY
            case Fuel.NATURALGAS:
                return dragon.Fuel.NATURALGAS
            case Fuel.OIL:
                return dragon.Fuel.DIESEL
            case Fuel.DISTRICTHEATING:
                return dragon.Fuel.OTHER


class SourceSystem:
    
    type_mapper={}
    
    @staticmethod
    def from_json(
        input:SimpleNamespace,
        ) -> Any:
        
        return SourceSystem.type_mapper[input.type].from_json(input)


class HeatPump(SourceSystem):
    
    def __init__(self,
        name:str,
        fuel            :str|Fuel ,
        heating_cop     :int|float|None=None,
        cooling_cop     :int|float|None=None,
        heating_capacity:int|float|None=None,
        cooling_capacity:int|float|None=None,
        *,
        ID:str|None=None
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties (w/ default values)
        self.fuel = fuel
        self.heating_cop      = 3.0  if heating_cop      is None else heating_cop
        self.cooling_cop      = 3.0  if cooling_cop      is None else cooling_cop
        self.heating_capacity = None if heating_capacity is None else heating_capacity
        self.cooling_capacity = None if cooling_capacity is None else cooling_capacity
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SOURCE_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def fuel(self) -> str:
        return str(self.__fuel)
    
    @fuel.setter
    @validate_enum(Fuel)
    def fuel(self, value: str) -> None:
        self.__fuel = value
    
    @property
    def heating_cop(self) -> int|float:
        return self.__heating_cop
    
    @heating_cop.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float)
    def heating_cop(self, value: int|float) -> None:
        self.__heating_cop = value
    
    @property
    def cooling_cop(self) -> int|float:
        return self.__cooling_cop
    
    @cooling_cop.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float)
    def cooling_cop(self, value: int|float) -> None:
        self.__cooling_cop = value
    
    @property
    def heating_capacity(self) -> int|float:
        return self.__heating_capacity
    
    @heating_capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def heating_capacity(self, value: int|float) -> None:
        self.__heating_capacity = value
        
    @property
    def cooling_capacity(self) -> int|float:
        return self.__cooling_capacity
    
    @cooling_capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def cooling_capacity(self, value: int|float) -> None:
        self.__cooling_capacity = value
        
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:HeatPump) -> bool:
        
        # type validation
        if not isinstance(other, HeatPump):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two packaged air conditioners are equal if fuel, cops, and capacities are equal
        return (self.fuel             == other.fuel            ) and\
               (self.heating_cop      == other.heating_cop     ) and\
               (self.cooling_cop      == other.cooling_cop     ) and\
               (self.heating_capacity == other.heating_capacity) and\
               (self.cooling_capacity == other.cooling_capacity)
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input:SimpleNamespace
        ) -> HeatPump:
        
        return HeatPump(
            input.name,
            input.fuel_type,
            getattr(input, "cop_heating", None),
            getattr(input, "cop_cooling", None),
            getattr(input, "capacity_heating", None),
            getattr(input, "capacity_cooling", None),
            ID=input.id
        )
    
    def to_dragon(self) -> dragon.HeatPump:
        
        return dragon.HeatPump(
            self.ID,
            Fuel(self.fuel).to_dragon(),
            self.heating_cop,
            self.cooling_cop,
            self.heating_capacity,
            self.cooling_capacity,
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        
        # formatting capacity
        heating_cap_str = f"{self.heating_capacity*Unit.W2KW:4,.1f}kW" if self.heating_capacity is not None else "autosize"
        cooling_cap_str = f"{self.cooling_capacity*Unit.W2KW:4,.1f}kW" if self.cooling_capacity is not None else "autosize"
        
        return (
            f"{self.fuel} HeatPump {self.name} (ID={self.ID})\n"
            f"\t- heating capacity={heating_cap_str}, COP={self.heating_cop:4.2f}\n"
            f"\t- cooling capacity={cooling_cap_str}, COP={self.cooling_cop:4.2f}"
        )
    
    def __repr__(self) -> str:
        return f"<HeatPump {self.name} (ID={self.ID}) at {hex(id(self))}>"
    

class GeothermalHeatPump(HeatPump):
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input:SimpleNamespace
        ) -> GeothermalHeatPump:
        
        return GeothermalHeatPump(
            input.name,
            input.fuel_type,
            getattr(input, "cop_heating", None),
            getattr(input, "cop_cooling", None),
            getattr(input, "capacity_heating", None),
            getattr(input, "capacity_cooling", None),
            ID=input.id
        )
        
    def to_dragon(self):
        
        return dragon.HeatPump(
            self.ID,
            Fuel(self.fuel).to_dragon(),
            self.heating_cop,
            self.cooling_cop,
            self.heating_capacity,
            self.cooling_capacity,
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        
        # formatting capacity
        heating_cap_str = f"{self.heating_capacity*Unit.W2KW:4,.1f}kW" if self.heating_capacity is not None else "autosize"
        cooling_cap_str = f"{self.cooling_capacity*Unit.W2KW:4,.1f}kW" if self.cooling_capacity is not None else "autosize"
        
        return (
            f"{self.fuel} GeothermalHeatPump {self.name} (ID={self.ID})\n"
            f"\t- heating capacity={heating_cap_str}, COP={self.heating_cop:4.2f}\n"
            f"\t- cooling capacity={cooling_cap_str}, COP={self.cooling_cop:4.2f}"
        )
    
    def __repr__(self) -> str:
        return f"<GeothermalHeatPump {self.name} (ID={self.ID}) at {hex(id(self))}>"
    

class CompressorType(str, Enum):
    
    TURBO         = "turbo"
    SCREW         = "screw"
    RECIPROCATING = "reciprocating"
    
    def __str__(self) -> str:
        return self.value
    
    def to_dragon(self) -> dragon.CompressorType:
        return dragon.CompressorType(self.value)
    
    
class CoolingTowerType(str, Enum):
    
    CLOSED = "closed"
    OPEN   = "open"
    
    def __str__(self) -> str:
        return self.value
    
    
class CoolingTowerControl(str, Enum):
    
    SINGLESPEED = "single-speed"
    TWOSPEED    = "two-speed"
    
    def __str__(self) -> str:
        return self.value


class Chiller(SourceSystem):
    
    def __init__(self,
        name:str     ,
        compressor_type      :str|CompressorType,
        coolingtower_type    :str|CoolingTowerType,
        coolingtower_control :str|CoolingTowerControl,
        cop     :int|float|None=None,
        capacity:int|float|None=None,
        coolingtower_capacity:int|float|None=None,
        *,
        ID:str|None=None,
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.cop             = 3.0  if cop      is None else cop
        self.capacity        = None if capacity is None else capacity
        self.compressor_type = compressor_type
        
        # secondary source system (cooing tower) properties
        self.coolingtower_type     = coolingtower_type
        self.coolingtower_control  = coolingtower_control
        self.coolingtower_capacity = None if coolingtower_capacity is None else coolingtower_capacity
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SOURCE_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
         
    """ fundamental properties
    """
    
    @property
    def cop(self) -> int|float:
        return self.__cop
    
    @cop.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float)
    def cop(self, value: int|float) -> None:
        self.__cop = value
    
    @property
    def capacity(self) -> int|float:
        return self.__capacity
    
    @capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def capacity(self, value: int|float) -> None:
        self.__capacity = value
        
    @property
    def compressor_type(self) -> str:
        return str(self.__compressor_type)
    
    @compressor_type.setter
    @validate_enum(CompressorType)
    def compressor_type(self, value: str) -> None:
        self.__compressor_type = CompressorType(value)
    
    @property
    def coolingtower_type(self) -> str:
        return str(self.__coolingtower_type)
    
    @coolingtower_type.setter
    @validate_enum(CoolingTowerType)
    def coolingtower_type(self, value: str) -> None:
        self.__coolingtower_type = CoolingTowerType(value)
        
    @property
    def coolingtower_capacity(self) -> int|float:
        return self.__coolingtower_capacity
    
    @coolingtower_capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def coolingtower_capacity(self, value: int|float) -> None:
        self.__coolingtower_capacity = value
        
    @property
    def coolingtower_control(self) -> str:
        return str(self.__coolingtower_control)
    
    @coolingtower_control.setter
    @validate_enum(CoolingTowerControl)
    def coolingtower_control(self, value: str) -> None:
        self.__coolingtower_control = CoolingTowerControl(value)
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:Chiller) -> bool:
        
        # type validation
        if not isinstance(other, Chiller):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two chillers are equal if all fundamental properties are euqal
        return (self.fuel            == other.fuel           ) and\
               (self.cop             == other.cop            ) and\
               (self.capacity        == other.capacity       ) and\
               (self.compressor_type == other.compressor_type) and\
               (self.coolingtower_type     == other.coolingtower_type    ) and\
               (self.coolingtower_capacity == other.coolingtower_capacity) and\
               (self.coolingtower_control  == other.coolingtower_control )
    
    """ in-out
    """
        
    @staticmethod
    def from_json(
        input:SimpleNamespace
    ) -> Chiller:
        
        return Chiller(
            input.name,
            input.compressor_type ,
            input.coolingtower_type    ,
            input.coolingtower_control ,
            getattr(input, "cop_cooling", None)     ,
            getattr(input, "capacity_cooling", None),
            getattr(input, "coolingtower_capacity", None),
            ID=input.id,
        )
    
    def to_dragon(self) -> dragon.Chiller:
        
        
        coolingtower_name = f"CoolingTower_for_{self.ID}"
        
        match (self.coolingtower_type, self.coolingtower_control):
            case (CoolingTowerType.OPEN, CoolingTowerControl.SINGLESPEED):
                coolingtower = dragon.OpenSingleSpeedCoolingTower(
                    coolingtower_name,
                    self.coolingtower_capacity,
                )
            case (CoolingTowerType.OPEN, CoolingTowerControl.TWOSPEED):
                coolingtower = dragon.OpenTwoSpeedCoolingTower(
                    coolingtower_name,
                    self.coolingtower_capacity
                )
            case (CoolingTowerType.CLOSED, CoolingTowerControl.SINGLESPEED):
                coolingtower = dragon.ClosedSingleSpeedCoolingTower(
                    coolingtower_name,
                    self.coolingtower_capacity
                )
            case (CoolingTowerType.CLOSED, CoolingTowerControl.TWOSPEED):
                coolingtower = dragon.ClosedTwoSpeedCoolingTower(
                    coolingtower_name,
                    self.coolingtower_capacity
                )
        
        dragonized_chiller = dragon.Chiller(
            self.ID,
            self.cop,
            self.capacity,
            CompressorType(self.compressor_type).to_dragon(),
            coolingtower,
        )
        
        return dragonized_chiller
    
    """ representation
    """
    
    def __str__(self) -> str:
        
        # formatting capacity
        chiller_cap_str = f"{self.capacity*Unit.W2KW:4,.1f}kW" if self.capacity is not None else "autosize"
        coolingtower_cap_str = f"{self.coolingtower_capacity*Unit.W2KW:4,.1f}kW" if self.cooling_capacity is not None else "autosize"
        
        return (
            f"{self.fuel} Chiller {self.name} (ID={self.ID})\n"
            f"\t- capacity={chiller_cap_str}, COP={self.cop:4.2f}\n"
            f"\t- connected coolingtower ({coolingtower_cap_str}): {self.CoolingTowerType} type, {self.coolingtower_control} controlled"
        )
    
    def __repr__(self) -> str:
        return f"<Chiller {self.name} (ID={self.ID}) at {hex(id(self))}>"
    
    
class AbsorptionChiller(SourceSystem):
    
    def __init__(self,
        name:str     ,
        cop     :int|float|None=None,
        capacity:int|float|None=None,
        boiler_efficiency:int|float|None=None,
        *,
        ID:str|None=None
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.cop      = 0.9  if cop      is None else cop
        self.capacity = None if capacity is None else capacity
        
        # secondary source system (boiler) properties
        self.boiler_efficiency = 0.85 if boiler_efficiency is None else boiler_efficiency

        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SOURCE_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def cop(self) -> int|float:
        return self.__cop
    
    @cop.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float)
    def cop(self, value: int|float) -> None:
        self.__cop = value
    
    @property
    def capacity(self) -> int|float:
        return self.__capacity
    
    @capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def capacity(self, value: int|float) -> None:
        self.__capacity = value
    
    @property
    def boiler_efficiency(self) -> int|float:
        return self.__boiler_efficiency
    
    @boiler_efficiency.setter
    @validate_range(min=SMALLEST_VALUE, max=1)
    @validate_type(int, float, allow_none=True)
    def boiler_efficiency(self, value: int|float) -> None:
        self.__boiler_efficiency = value
        
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:AbsorptionChiller) -> bool:
        
        # type validation
        if not isinstance(other, AbsorptionChiller):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two chillers are equal if all fundamental properties are euqal
        return (self.fuel              == other.fuel             ) and\
               (self.cop               == other.cop              ) and\
               (self.capacity          == other.capacity         ) and\
               (self.boiler_efficiency == other.boiler_efficiency)
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input:SimpleNamespace
    ) -> AbsorptionChiller:
        
        return AbsorptionChiller(
            input.name,
            getattr(input,"cop_cooling", None),
            getattr(input,"capacity_cooling ", None),
            getattr(input,"boiler_efficiency", None),
            ID=input.id
        )
        
    def to_dragon(self) -> dragon.AbsorptionChiller:
        
        boiler = dragon.Boiler(
            f"Boiler_for_{self.ID}",
            Fuel.NATURALGAS.to_dragon(),
            self.boiler_efficiency
        )
        
        coolingtower = dragon.OpenSingleSpeedCoolingTower(
            f"CoolingTower_for_{self.ID}",
            self.capacity,
        )
        
        return dragon.AbsorptionChiller(
            self.ID,
            self.cop     ,
            self.capacity,
            boiler       ,
            coolingtower ,
        )
    
    """ representation
    """
    
    def __str__(self) -> str:
        
        # formatting capacity
        cap_str = f"{self.capacity*Unit.W2KW:4,.1f}kW" if self.capacity is not None else "autosize"
        
        return (
            f"{self.fuel}-based AbsorptionChiller {self.name} (ID={self.ID})\n"
            f"\t- capacity={cap_str}, COP={self.cop:4.2f}\n"
            f"\t- connected boiler efficiency={self.boiler_efficiency}"
        )
    
    def __repr__(self) -> str:
        return f"<AbsorptionChiller {self.name} (ID={self.ID}) at {hex(id(self))}>"
    
    
class DistrictHeating(SourceSystem):
    
    def __init__(self,
        name:str,
        hotwater_supply:bool,
        *,
        ID:str|None=None
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.hotwater_supply = hotwater_supply
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SOURCE_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
        
    """ fundamental properties
    """
    
    @property
    def hotwater_supply(self) -> bool:
        return self.__hotwater_supply
    
    @hotwater_supply.setter
    @validate_type(bool)
    def hotwater_supply(self, value:bool) -> None:
        self.__hotwater_supply = value
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:DistrictHeating) -> bool:
        
        # type validation
        if not isinstance(other, DistrictHeating):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two district heating systems are equal if both are used for the hot water system, or if neither is used.
        return (self.hotwater_supply == other.hotwater_supply)
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input:SimpleNamespace
    ) -> DistrictHeating:
    
        return DistrictHeating(
            input.name,
            input.hotwater_supply,
            ID=input.id
        )
    
    def to_dragon(self):
        
        return dragon.Boiler(
            self.ID,
            Fuel.DISTRICTHEATING.to_dragon(),
            1.0 ,
            None,
            pump_efficiency=0.9,
        )
        
        
    """ representation
    """

    def __str__(self) -> str:
        
        hotwater_supply_string = "" if not self.hotwater_supply else "(for hot-water supply) "
        
        return f"District-heating system {hotwater_supply_string}{self.name} (ID={self.ID})"
    
    def __repr__(self) -> str:
        return f"<DistrictHeating {self.name} (ID={self.ID}) at {hex(id(self))}>"
    

class Boiler(SourceSystem):
    
    def __init__(self,
        name:str,
        fuel           :str|Fuel ,
        hotwater_supply:bool     ,
        efficiency     :int|float|None=None,
        capacity       :int|float|None=None,
        
        *,
        ID:str|None=None
    ) -> Boiler:
        
        # user properties
        self.name = name
        
        # fundamental properties        
        self.fuel            = fuel
        self.capacity        = None if capacity   is None else capacity
        self.efficiency      = 0.85 if efficiency is None else efficiency
        self.hotwater_supply = hotwater_supply
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SOURCE_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def fuel(self) -> str:
        return str(self.__fuel)
    
    @fuel.setter
    @validate_enum(Fuel)
    def fuel(self, value: str) -> None:
        self.__fuel = Fuel(value)
    
    @property
    def efficiency(self) -> int|float:
        return self.__efficiency
    
    @efficiency.setter
    @validate_range(min=SMALLEST_VALUE, max=1)
    @validate_type(int, float)
    def efficiency(self, value: int|float) -> None:
        self.__efficiency = value
    
    @property
    def capacity(self) -> int|float:
        return self.__capacity
    
    @capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def capacity(self, value: int|float) -> None:
        self.__capacity = value
        
    @property
    def hotwater_supply(self) -> bool:
        return self.__hotwater_supply
    
    @hotwater_supply.setter
    @validate_type(bool)
    def hotwater_supply(self, value:bool) -> None:
        self.__hotwater_supply = value
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:Boiler) -> bool:
        
        # type validation
        if not isinstance(other, Boiler):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two boilers are euqal if all fundamental properties are euqal
        return (self.fuel            == other.fuel           ) and\
               (self.efficiency      == other.efficiency     ) and\
               (self.capacity        == other.capacity       ) and\
               (self.hotwater_supply == other.hotwater_supply) 
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input:SimpleNamespace
    ) -> Boiler:
        
        return Boiler(
            input.name,
            input.fuel_type       ,
            input.hotwater_supply ,
            getattr(input,"efficiency", None),
            getattr(input,"capacity_heating", None),
            ID = input.id
        )
        
    def to_dragon(self) -> dragon.Boiler:
        
        return dragon.Boiler(
            self.ID,
            Fuel(self.fuel).to_dragon(),
            self.efficiency,
            self.capacity  ,
            pump_efficiency=0.9,
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        
        
        # formatting capacity and hotwater supply
        cap_str = f"{self.capacity*Unit.W2KW:4,.1f}kW" if self.capacity is not None else "autosize"
        hotwater_supply_string = "" if not self.hotwater_supply else "(for hot-water supply) "
        
        return (
            f"{self.fuel} Boiler {hotwater_supply_string}{self.name} (ID={self.ID})\n"
            f"\t- capacity={cap_str}, eff.={self.efficiency*Unit.NONE2PRC:.1f}%"
        )
    
    def __repr__(self) -> str:
        return f"<Boiler {self.name} (ID={self.ID}) at {hex(id(self))}>"
    

class NoneSource(SourceSystem):
    
    # ID for singleton instance
    ID = f"{SpecialTag.SPECIAL}{AUTOID_PREFIX.SOURCE_SYSTEM}-NONE"
    
    # none-source is singleton class
    _instance = None    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    # none-source cannot be dragonized
    def to_dragon(self) -> None:
        return None
    


# ---------------------------------------------------------------------------- #
#                                 SUPPLY SYSTEM                                #
# ---------------------------------------------------------------------------- #

class SupplySystem:
    
    # map json input to a correspondingsubclasses 
    # type_mapper class-variable will be defined at the end of the document
    type_mapper={}
    
    @staticmethod
    def from_json(
        input:SimpleNamespace,
        source_system_dict:dict[str, SourceSystem],
        ) -> Any:
        
        return SupplySystem.type_mapper[input.type].from_json(input, source_system_dict)

    # define heat/cool-ablity by subclass and the connected source system
    _heatable_sources = []
    _coolable_sources = []
    
    @property
    def heatable(self) -> bool:
        return (type(self.source) in self._heatable_sources)
    
    @property
    def coolable(self) -> bool:
        return (type(self.source) in self._coolable_sources)
    

class PackagedAirConditioner(SupplySystem):
    
    _heatable_sources = []
    _coolable_sources = [NoneSource]
    
    def __init__(self,
        name:str,
        cop     :int|float|None=None,
        capacity:int|float|None=None,
        *,
        ID:str|None=None
        ) -> None:
        
        # user property
        self.name = name
        
        # fundamental property
        self.cop      = 3.0  if cop      is None else cop
        self.capacity = None if capacity is None else capacity
        
        # a packaged air conditioner doesn't require source system
        self.__source = NoneSource()
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SUPPLY_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
        
    """ fundamental properties
    """
    
    @property
    def cop(self) -> int|float|None:
        return self.__cop
    
    @cop.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float)
    def cop(self, value: int|float|None) -> None:
        self.__cop = value
        
    @property
    def capacity(self) -> int|float|None:
        return self.__capacity
    
    @capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def capacity(self, value: int|float|None) -> None:
        self.__capacity = value
        
    @property
    def source(self) -> NoneSource:
        return self.__source
        
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:PackagedAirConditioner) -> bool:
        
        # type validation
        if not isinstance(other, PackagedAirConditioner):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two packaged air conditioners are equal if cop and capacity are equal
        return (self.cop      == other.cop     ) and\
               (self.capacity == other.capacity)
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input             :SimpleNamespace        ,
        source_system_dict:dict[str, SourceSystem],
    ) -> PackagedAirConditioner:
        
        return PackagedAirConditioner(
            input.name            ,
            getattr(input,"cop_cooling", None)     ,
            getattr(input,"capacity_cooling", None),
            ID=input.id
        )
        
    def to_dragon(self, source_dict:dict[str, dragon.SourceSystem]) -> dragon.PackagedAirConditioner:
        
        return dragon.PackagedAirConditioner(
            self.ID,
            self.cop,
            self.capacity,
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        
        # formatting capacity and hotwater supply
        cap_str = f"{self.capacity*Unit.W2KW:4,.1f}kW" if self.capacity is not None else "autosize"
        
        return (
            f"PackagedAirConditioner {self.name} (ID={self.ID})"
            f" with COP={self.cop:.2f}, Capa={cap_str}"
        )
        
    def __repr__(self) -> str:
        return f"<PackagedAirConditioner {self.name} (ID={self.ID}) at {hex(id(self))}>"
        
    
class AirHandlingUnit(SupplySystem):
    
    _heatable_sources = [HeatPump, GeothermalHeatPump]
    _coolable_sources = [HeatPump, GeothermalHeatPump]
    
    def __init__(self,
        name,
        source:SourceSystem,
        *,
        ID:str|None=None
        ) -> None:

        # user properties
        self.name = name
        
        # fundamental properties
        self.source = source
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SUPPLY_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def source(self) -> SourceSystem:
        return self.__source
    
    @source.setter
    @validate_type(*_heatable_sources, *_coolable_sources)
    def source(self, value:SourceSystem) -> None:
        self.__source = value
            
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:AirHandlingUnit) -> bool:
        
        # type validation
        if not isinstance(other, type(self)):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two air handling units are equal if source systems are identitcal (note: not equal)
        return (self.source is other.source)
    
    """ in-out
    """
            
    @staticmethod
    def from_json(
        input             :SimpleNamespace        ,
        source_system_dict:dict[str, SourceSystem],
        ) -> AirHandlingUnit:
        
        return AirHandlingUnit(
            input.name,
            source_system_dict[input.source_system_id],
            ID=input.id
        )
    
    def to_dragon(self, source_dict:dict[str, dragon.SourceSystem]) -> dragon.AirHandlingUnit:
        
        return dragon.AirHandlingUnit(
            self.ID,
            source_dict[self.source.ID],
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        return f"AirHandlingUnit {self.name} (ID={self.ID}) using {type(self.source)} {self.source.name}"
    
    def __repr__(self) -> str:
        return f"<AirHandlingUnit {self.name} (ID={self.ID}) at {hex(id(self))}>"


class FanCoilUnit(AirHandlingUnit):
    
    _heatable_sources = [Boiler, DistrictHeating]
    _coolable_sources = [Chiller, AbsorptionChiller]
    
    def __init__(self,
        name,
        source:SourceSystem,
        *,
        ID:str|None=None
        ) -> None:

        # user properties
        self.name = name
        
        # fundamental properties
        self.source = source
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SUPPLY_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def source(self) -> SourceSystem:
        return self.__source
    
    @source.setter
    @validate_type(*_heatable_sources, *_coolable_sources)
    def source(self, value:SourceSystem) -> None:
        self.__source = value
            
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:FanCoilUnit) -> bool:
        
        # type validation
        if not isinstance(other, type(self)):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two fan coil units are equal if source systems are identitcal (note: not equal)
        return (self.source is other.source)
    
    """ in-out
    """
            
    @staticmethod
    def from_json(
        input             :SimpleNamespace        ,
        source_system_dict:dict[str, SourceSystem],
        ) -> FanCoilUnit:
        
        return FanCoilUnit(
            input.name,
            source_system_dict[input.source_system_id],
            ID=input.id
        )
    
    def to_dragon(self, source_dict:dict[str, dragon.SourceSystem]) -> dragon.FanCoilUnit:
        
        return dragon.FanCoilUnit(
            self.ID,
            source_dict[self.source.ID],
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        return f"FanCoilUnit {self.name} (ID={self.ID}) using {type(self.source)} {self.source.name}"
    
    def __repr__(self) -> str:
        return f"<FanCoilUnit {self.name} (ID={self.ID}) at {hex(id(self))}>"
    
        
class Radiator(SupplySystem):
    
    _heatable_sources = [Boiler, DistrictHeating]
    _coolable_sources = []
    
    def __init__(self,
        name:str,
        source  :SourceSystem,
        capacity:int|float|None=None,
        *,
        ID:str|None=None
        ) -> None:
        
        # user property
        self.name = name
        
        # fundamental properties
        self.capacity = None if capacity is None else capacity
        self.source   = source
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SUPPLY_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
        
    """ fundamental properties
    """
    
    @property
    def capacity(self) -> int|float:
        return self.__capacity
    
    @capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def capacity(self, value: int|float) -> None:
        self.__capacity = value
    
    @property
    def source(self) -> SourceSystem:
        return self.__source
    
    @source.setter
    @validate_type(*_heatable_sources, *_coolable_sources)
    def source(self, value:SourceSystem) -> None:
        self.__source = value
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:Radiator) -> bool:
        
        # type validation
        if not isinstance(other, Radiator):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two air handling units are equal if capacities are equal and source systems are identitcal (note: not equal)
        return (self.capacity == other.capacity) and\
               (self.source   is other.source  )
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input             :SimpleNamespace        ,
        source_system_dict:dict[str, SourceSystem],
    ) -> Radiator:
        
        return Radiator(
            input.name,
            source_system_dict[input.source_system_id],
            getattr(input,"capacity_heating"),
            ID=input.id
        )
    
    def to_dragon(self, source_dict:dict[str, dragon.SourceSystem]) -> dragon.Radiator:
        
        return dragon.Radiator(
            self.ID,
            self.capacity,
            source_dict[self.source.ID],
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        return f"Radiator {self.name} (ID={self.ID}) using {type(self.source)} {self.source.name}"
    
    def __repr__(self) -> str:
        return f"<Radiator {self.name} (ID={self.ID}) at {hex(id(self))}>"
    
    
class ElectricRadiator(SupplySystem):
    
    _heatable_sources = [NoneSource]
    _coolable_sources = []
    
    def __init__(self,
        name:str,
        capacity:int|float|None=None,
        *,
        ID:str|None=None
        ) -> None:
        
        # user property
        self.name = name
        
        # fundamental properties
        self.capacity = None if capacity is None else capacity
        
        # a packaged air conditioner doesn't require source system
        self.__source = NoneSource()
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SUPPLY_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
        
    """ fundamental properties
    """
    
    @property
    def capacity(self) -> int|float|None:
        return self.__capacity
    
    @capacity.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float, allow_none=True)
    def capacity(self, value: int|float|None) -> None:
        self.__capacity = value
        
    @property
    def source(self) -> NoneSource:
        return self.__source
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:Radiator) -> bool:
        
        # type validation
        if not isinstance(other, Radiator):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two air handling units are equal if capacities are equal 
        return (self.capacity == other.capacity)
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input             :SimpleNamespace        ,
        source_system_dict:dict[str, SourceSystem],
    ) -> ElectricRadiator:
        
        return ElectricRadiator(
            input.name,
            input.capacity_heating,
            ID=input.id,
        )
        
    def to_dragon(self, source_dict:dict[str, dragon.SourceSystem]) -> dragon.ElectricRadiator:
        
        return dragon.ElectricRadiator(
            self.ID,
            self.capacity,
        )
    
    """ representation
    """
    
    def __str__(self) -> str:
        
        # formatting capacity and hotwater supply
        cap_str = f"{self.capacity*Unit.W2KW:4,.1f}kW" if self.capacity is not None else "autosize"
        
        return f"Electric radiator {self.name} with capa={cap_str} (ID={self.ID})"
    
    def __repr__(self) -> str:
        return f"<ElectricRadiator {self.name} (ID={self.ID}) at {hex(id(self))}>"
        
        
class RadiantFloor(SupplySystem):
    
    _heatable_sources = [Boiler, DistrictHeating]
    _coolable_sources = []
    
    def __init__(self,
        name,
        source:SourceSystem,
        *,
        ID:str|None=None
        ) -> None:

        # user properties
        self.name = name
        
        # fundamental properties
        self.source = source
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SUPPLY_SYSTEM}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def source(self) -> SourceSystem:
        return self.__source
    
    @source.setter
    @validate_type(*_heatable_sources, *_coolable_sources)
    def source(self, value:SourceSystem) -> None:
        self.__source = value
    
    @property
    def heatable(self) -> bool:
        return True
    
    @property
    def coolable(self) -> bool:
        return False
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:RadiantFloor) -> bool:
        
        # type validation
        if not isinstance(other, RadiantFloor):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two radiant floors are equal if source systems are identitcal (note: not equal)
        return (self.source is other.source)
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input             :SimpleNamespace        ,
        source_system_dict:dict[str, SourceSystem],
        ) -> RadiantFloor:   
        
        return RadiantFloor(
            input.name,
            source_system_dict[input.source_system_id],
            ID=input.id
        )
        
    def to_dragon(self, source_dict:dict[str, dragon.SourceSystem]) -> dragon.RadiantFloor:
        
        return dragon.RadiantFloor(
            self.ID,
            source_dict[self.source.ID]
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        return f"Radiant floor {self.name} (ID={self.ID}) using {type(self.source)} {self.source.name}"
    
    def __repr__(self) -> str:
        return f"<RadiantFloor {self.name} (ID={self.ID}) at {hex(id(self))}>"
            
    

# ---------------------------------------------------------------------------- #
#                                 OTHER SYSTEMS                                #
# ---------------------------------------------------------------------------- #

class VentilationSystem:
    
    def __init__(self,
        name:str,
        heating_efficiency:int|float|None=None,
        cooling_efficiency:int|float|None=None,
        *,
        ID:str|None=None
        ) -> None:
        
        # user property
        self.name = name
        
        # fundamental properties
        self.heating_efficiency = 0.7  if heating_efficiency is None else heating_efficiency
        self.cooling_efficiency = 0.45 if cooling_efficiency is None else cooling_efficiency
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.HEAT_EXCHANGER}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def heating_efficiency(self) -> int|float:
        return self.__heating_efficiency
    
    @heating_efficiency.setter
    @validate_range(min=SMALLEST_VALUE, max=1)
    @validate_type(int, float)
    def heating_efficiency(self, value:int|float) -> None:
        self.__heating_efficiency = value
        
    @property
    def cooling_efficiency(self) -> int|float:
        return self.__cooling_efficiency
    
    @cooling_efficiency.setter
    @validate_range(min=SMALLEST_VALUE, max=1)
    @validate_type(int, float)
    def cooling_efficiency(self, value:int|float) -> None:
        self.__cooling_efficiency = value
        
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:VentilationSystem) -> bool:
        
        # type validation
        if not isinstance(other, VentilationSystem):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )    
            
        # two ventilation systems are equal if all efficiencies are equal
        return (self.heating_efficiency == other.heating_efficiency) and\
               (self.cooling_efficiency == other.cooling_efficiency)
               
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input:SimpleNamespace
        ) -> VentilationSystem:
        
        return VentilationSystem(
            input.name,
            getattr(input,"efficiency_heating", None),
            getattr(input,"efficiency_cooling", None),
            ID=input.id,
        )
    
    def to_dragon(self) -> None:
        
        return dragon.EnergyRecoveryVentilator(
            self.ID,
            self.heating_efficiency,
            self.cooling_efficiency,
        )
    
    """ representation
    """
    
    def __str__(self) -> str:
        return f"Ventilator (HEX) {self.name} (ID={self.ID}) with eff_h={self.heating_efficiency*Unit.NONE2PRC:.1f}%, eff_c={self.cooling_efficiency*Unit.NONE2PRC:.1f}%"
    
    def __repr__(self) -> str:
        return f"<VentilationSystem {self.name} (ID={self.ID}) at {hex(id(self))}>"
    
    
class PhotoVoltaicSystem:
    
    def __init__(self,
        name:str,
        area      :int|float,
        efficiency:int|float,
        azimuth   :int|float,
        tilt      :int|float,
        *,
        ID:str|None=None
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.area      =area
        self.efficiency=efficiency
        self.azimuth   =azimuth
        self.tilt      =tilt

        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.PV_PANEL}AUTOID{hex(id(self))}"
        self.__ID = ID

    """ fundamental properties
    """
    
    @property
    def area(self) -> int|float:
        return self.__area
    
    @area.setter
    @validate_range(min=SMALLEST_VALUE)
    @validate_type(int, float)
    def area(self, value:int|float) -> None:
        self.__area = value
        
    @property
    def efficiency(self) -> int|float:
        return self.__efficiency
    
    @efficiency.setter
    @validate_range(min=SMALLEST_VALUE, max=1)
    @validate_type(int, float)
    def efficiency(self, value:int|float) -> None:
        self.__efficiency = value
        
    @property
    def azimuth(self) -> int|float:
        return self.__azimuth
    
    @azimuth.setter
    @validate_range(min=0, max=360-SMALLEST_VALUE)
    @validate_type(int, float)
    def azimuth(self, value:int|float) -> None:
        self.__azimuth = value
        
    @property
    def tilt(self) -> int|float:
        return self.__tilt
    
    @tilt.setter
    @validate_range(min=0, max=90)
    @validate_type(int, float)
    def tilt(self, value:int|float) -> None:
        self.__tilt = value

    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    def __eq__(self, other:PhotoVoltaicSystem) -> bool:
        
        # type validation
        if not isinstance(other, PhotoVoltaicSystem):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two PV-panels are equal if physical properties and specifications are euqal
        return (self.area     == other.area      ) and\
               (self.effiency == other.efficiency) and\
               (self.azimuth  == other.azimuth   ) and\
               (self.tilt     == other.tilt      )
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input:SimpleNamespace
        ) -> PhotoVoltaicSystem:
        
        return PhotoVoltaicSystem(
            input.name,
            input.area      ,
            input.efficiency,
            input.azimuth   ,
            input.tilt      ,
            ID=input.id
        )
    
    def to_dragon(self):
        
        return dragon.PhotoVoltaicPanel(
            self.ID,
            self.area      ,
            self.tilt      ,
            self.azimuth   ,
            self.efficiency,
        )
        
    """ representation
    """
    
    def __str__(self) -> str:
        return f"{self.area:.1f}m2 PV panel {self.name} (ID={self.ID}): eff={self.efficiency*Unit.NONE2PRC:.1f}%, azim={self.azimuth:.1f}°, tilt={self.tilt:.1f}°"
    
    def __repr__(self) -> str:
        return f"<PhotoVoltaicSystem {self.name} (ID={self.ID}) at {hex(id(self))}>"
    
    
    
# ---------------------------------------------------------------------------- #
#                                 CHILD CLASSES                                #
# ---------------------------------------------------------------------------- #

SupplySystem.type_mapper = {
    "packaged_air_conditioner": PackagedAirConditioner,
    "air_handling_unit"       : AirHandlingUnit       ,
    "fan_coil_unit"           : FanCoilUnit           ,
    "radiator"                : Radiator              ,
    "electric_radiator"       : ElectricRadiator      ,
    "radiant_floor"           : RadiantFloor          ,
}

SourceSystem.type_mapper = {
    "heatpump"           : HeatPump          ,
    "geothermal_heatpump": GeothermalHeatPump,
    "chiller"            : Chiller           ,
    "absorption_chiller" : AbsorptionChiller ,
    "boiler"             : Boiler            ,
    "district_heating"   : DistrictHeating   ,
}







