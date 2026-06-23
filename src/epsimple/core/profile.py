
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import re

# third-party modules
import pandas as pd

# local modules
from ..constants      import (
    Directory ,
    Unit      ,
    SpecialTag    ,
    AUTOID_PREFIX ,
)
from idragon        import dragon
from idragon.dragon import (
    DaySchedule ,
    RuleSet     ,
    Schedule    ,
    ScheduleType,
)
from idragon.constants import (
    THERMAL
)

# ---------------------------------------------------------------------------- #
#                                    PROFILE                                   #
# ---------------------------------------------------------------------------- #

class Profile:
    
    _DB = {}
    
    @staticmethod
    def get_DB(
        key:str,
        *,
        as_dict:bool=False
        ) -> Profile|list[Profile]|str|dict:
        
        # special keys
        if key == "__path__":
            return [
                KoreanUsageProfile.datapath
            ]
        
        elif key == "__all__":
            return [
                Profile.get_DB(_key, as_dict=as_dict)
                for _key in Profile._DB.keys()
            ]
        
        # database keys
        elif key in Profile._DB:
            profile = Profile._DB[key]
            if as_dict:
                return profile.to_dict()
            return profile
        
        else:
            raise KeyError(f"Profile with key '{key}' not found")


class KoreanUsageProfile(Profile):
    
    datapath = Directory.PROFILE_DIR / "KoreanUsageProfile.csv"
    
    def __init__(self,
        name:str,         
        occupant_start:int, # hh
        occupant_end  :int, # hh
        hvac_start    :int, # hh
        hvac_end      :int, # hh
        ventilation      :int|float, # m3/m2h
        domestic_hotwater:int|float, # Wh/m2d
        lighting_hours   :int,       # h
        occupancy        :int|float, # Wh/m2d
        equipment        :int|float, # Wh/m2d
        heating_setpoint :int|float, # °C
        cooling_setpoint :int|float, # °C
        operate_in_monday   :bool,
        operate_in_tuesday  :bool,
        operate_in_wednesday:bool,
        operate_in_thursday :bool,
        operate_in_friday   :bool,
        operate_in_saturday :bool,
        operate_in_sunday   :bool,
        operate_in_holiday  :bool,
        vacations:list[tuple[tuple[int, int], tuple[int, int]]], # list of (start_date, end_date) where date is (month, day)
        ID:str|None=None,
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.occupant_start = occupant_start
        self.occupant_end   = occupant_end
        self.hvac_start     = hvac_start
        self.hvac_end       = hvac_end
        self.ventilation       = ventilation
        self.domestic_hotwater = domestic_hotwater
        self.lighting_hours    = lighting_hours
        self.occupancy         = occupancy
        self.equipment         = equipment
        self.heating_setpoint  = heating_setpoint
        self.cooling_setpoint  = cooling_setpoint
        self.operate_in_monday    = operate_in_monday
        self.operate_in_tuesday   = operate_in_tuesday
        self.operate_in_wednesday = operate_in_wednesday
        self.operate_in_thursday  = operate_in_thursday
        self.operate_in_friday    = operate_in_friday
        self.operate_in_saturday  = operate_in_saturday
        self.operate_in_sunday    = operate_in_sunday
        self.operate_in_holiday   = operate_in_holiday
        self.vacations = vacations
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.PROFILE}AUTOID{hex(id(self))}"
        self.__ID = ID


    """ fundamental properties
    """
    
    """ derived properties
    """
    
    @property
    def occupied_hours(self) -> int:
        if self.occupant_end > self.occupant_start:
            return self.occupant_end - self.occupant_start
        else:
            return 24 - (self.occupant_start - self.occupant_end)
    
    @property
    def operating_days(self) -> list[str]:
        return [
            day
            for day in [
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday", "holiday",
            ]
            if getattr(self, f"operate_in_{day}")
        ]
    
    """ identity and equality
    """

    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> int:
        return hash(self.ID)
    
    """ in-out
    """
    
    def _get_vacation_mask(self) -> Schedule:
        
        return Schedule.from_windows(
            None, 0,
            [
                (f"{startmonth:02d}{startday:02d}", f"{endmonth:02d}{endday:02d}", 1)
                for (startmonth, startday), (endmonth, endday) in self.vacations
            ],
            type = ScheduleType.ONOFF
        )
    
    def _get_schedule_based_start_end(self,
        start_hour: int,
        start_min : int,
        end_hour  : int,
        end_min   : int,
        name: str|None=None,
        type: ScheduleType=ScheduleType.ONOFF,
        ) -> Schedule:
        day = DaySchedule.from_windows(
            None,
            0,
            [
                ((start_hour, start_min), (end_hour, end_min), 1)
            ],
            type=type,
        )

        off = DaySchedule.from_constant(None, 0, type=type)

        ruleset = RuleSet.from_days(
            None,
            default=off,
            type=type,
            **{
                day_name: day
                for day_name in self.operating_days
            },
        )

        return Schedule.from_constant(name, ruleset)
        
    def _get_occupied_mask(self) -> Schedule:
        
        return self._get_schedule_based_start_end(
            self.occupant_start, 0,
            self.occupant_end  , 0,
            f"{self.ID}-Occupied",
            ScheduleType.ONOFF,
        ) & (~self._get_vacation_mask())

    def _get_hvac_mask(self) -> Schedule:
        
        return self._get_schedule_based_start_end(
            self.hvac_start, 0,
            self.hvac_end  , 0,
            f"{self.ID}-HVACOperating",
            ScheduleType.ONOFF,
        ) & (~self._get_vacation_mask())
        
    def _get_lighting_mask(self) -> Schedule:
        
        lighting_end = self.occupant_end
        lighting_start = self.occupant_end - self.lighting_hours
        
        if self.lighting_hours < 0:
            lighting_start += 24
            
        return self._get_schedule_based_start_end(
            lighting_start, 0,
            lighting_end  , 0,
            f"{self.ID}-Lighted",
            ScheduleType.ONOFF,
        ) & (~self._get_vacation_mask())
    
    def to_dragon(self) -> dragon.Profile:
        
        # bsae
        is_occupied      = self._get_occupied_mask()
        is_hvac_operatng = self._get_hvac_mask()
        
        # hvac related
        heating_setpoint_schedule = Schedule.from_constant(
            f"{self.ID}-HeatingSetpoint",
            self.heating_setpoint       ,
            ScheduleType.TEMPERATURE    ,
        )
        cooling_setpoint_schedule = Schedule.from_constant(
            f"{self.ID}-CoolingSetpoint",
            self.cooling_setpoint       ,
            ScheduleType.TEMPERATURE    ,
        )
        hvac_availability_schedule = is_hvac_operatng
        
        # internal load related
        occupanct_schedule = is_occupied * self.occupancy / self.occupied_hours / THERMAL.PROPLE_ACTIVITY_LEVEL
        equipment_schedule = is_occupied * self.equipment / self.occupied_hours
        lighting_schedule  = self._get_lighting_mask().astype(ScheduleType.FRACTION)
        
        return dragon.Profile(
            self.ID,
            heating_setpoint =heating_setpoint_schedule ,
            cooling_setpoint =cooling_setpoint_schedule ,
            hvac_availability=hvac_availability_schedule,
            occupant =occupanct_schedule,
            lighting =lighting_schedule ,
            equipment=equipment_schedule,
        )
    
    """ representation
    """
    
    def to_dict(self) -> dict:
        
        return {
            "name": self.name,
            "occupant_start": self.occupant_start,
            "occupant_end"  : self.occupant_end  ,
            "hvac_start"    : self.hvac_start    ,
            "hvac_end"      : self.hvac_end      ,
            "ventilation"       : self.ventilation       ,
            "domestic_hotwater" : self.domestic_hotwater ,
            "lighting_hours"    : self.lighting_hours    ,
            "occupancy"         : self.occupancy         ,
            "equipment"         : self.equipment         ,
            "heating_setpoint"  : self.heating_setpoint  ,
            "cooling_setpoint"  : self.cooling_setpoint  ,
            "operate_weekdays": [
                day for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "holiday"]
                if getattr(self, f"operate_in_{day}")
            ],
            "vacations": [
                {
                    "start": f"{start_month:02d}/{start_day:02d}",
                    "end"  : f"{end_month:02d}/{end_day:02d}"
                }
                for (start_month, start_day), (end_month, end_day) in self.vacations
            ]
        }    

    def __str__(self) -> str:
        return "\n".join([
            f"KoreanUsageProfile {self.name}",
            f"\t-occupant: {self.occupant_start}h - {self.occupant_end}h",
            f"\t-hvac    : {self.hvac_start}h - {self.hvac_end}h",
            f"\t-lighting hours: {self.lighting_hours} h",  
            f"\t-ventilation      : {self.ventilation} m3/m2h",
            f"\t-domestic hotwater: {self.domestic_hotwater} Wh/m2d",
            f"\t-occupancy        : {self.occupancy} Wh/m2d",
            f"\t-equipment        : {self.equipment} Wh/m2d",
            f"\t-setpoints: [{self.heating_setpoint} °C, {self.cooling_setpoint} °C]",
            f"\t-operate in: {self.operating_days}",
            f"\t-vacations: {', '.join([f'{start_month:02d}/{start_day:02d} ~ {end_month:02d}/{end_day:02d}' for (start_month, start_day), (end_month, end_day) in self.vacations]) or "none"}"
        ])
    
    def __repr__(self) -> str:
        return f"<KoreanUsageProfile {self.name} (ID={self.ID}) at {hex(id(self))}>"


def read_csv_without_units(filepath:str, encoding:str="utf-8") -> pd.DataFrame:
    df = pd.read_csv(filepath, encoding=encoding)
    df.columns = [re.sub(r"\s*\[.+\]", "", str(col)) for col in df.columns]
    return df

Profile._DB = {
    row["Name"]: KoreanUsageProfile(
        row["Name"],
        row["Occupant-Start"],
        row["Occupant-End"],
        row["HVAC-Start"],
        row["HVAC-End"],
        row["Ventilation"],
        row["DomesticHotWater"],
        row["LightingHours"],
        row["Occupancy"],
        row["Equipment"],
        row["Heating-Setpoint"],
        row["Cooling-Setpoint"],
        operate_in_monday    = bool(row["Monday"]   ),
        operate_in_tuesday   = bool(row["Tuesday"]  ),
        operate_in_wednesday = bool(row["Wednesday"]),
        operate_in_thursday  = bool(row["Thursday"] ),
        operate_in_friday    = bool(row["Friday"]   ),
        operate_in_saturday  = bool(row["Saturday"] ),
        operate_in_sunday    = bool(row["Sunday"]   ),
        operate_in_holiday   = bool(row["Holiday"]  ),
        vacations= [] if pd.isna(row["Vacations"]) else [
            (
                (int(start_month), int(start_day)),
                (int(end_month), int(end_day))
            )
            for start_month, start_day, end_month, end_day in re.findall(r"(\d{1,2})/(\d{1,2})-(\d{1,2})/(\d{1,2})", row["Vacations"])
        ],
        ID=f"{SpecialTag.DB}{row["Name"]}"
    )
    for _, row in read_csv_without_units(KoreanUsageProfile.datapath,).iterrows()
}   


pass