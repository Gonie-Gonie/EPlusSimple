
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
import re
from copy      import deepcopy
from types     import SimpleNamespace
from typing    import Callable
from functools import wraps

# third-party modules
import pandas as pd

# local modules
from ..constants      import (
    Directory ,
    SpecialTag,
    AUTOID_PREFIX ,
)
from idragon        import dragon
from idragon.dragon import ScheduleType
from idragon.utils  import (
    validate_type ,
    validate_enum ,
    validate_range,
)


# ---------------------------------------------------------------------------- #
#                                   VARIABLES                                  #
# ---------------------------------------------------------------------------- #

# read datasheets
df_dayschedule = pd.read_csv(os.path.join(Directory.PROFILE,"day_schedule.csv")).set_index("name")
df_ruleset     = pd.read_csv(os.path.join(Directory.PROFILE,"ruleset.csv"     )).set_index("name")
df_schedule    = pd.read_csv(os.path.join(Directory.PROFILE,"schedule.csv"    )).set_index("name")
df_profile     = pd.read_csv(os.path.join(Directory.PROFILE,"profile.csv"     )).set_index("name")

# convert nan to None
df_dayschedule = df_dayschedule.astype("object").where(pd.notna(df_dayschedule), None)
df_ruleset     = df_ruleset.astype("object").where(pd.notna(df_ruleset), None)
df_schedule    = df_schedule.astype("object").where(pd.notna(df_schedule), None)
df_profile     = df_profile.astype("object").where(pd.notna(df_profile), None)

# ---------------------------------------------------------------------------- #
#                              PROFILE COMPONENTS                              #
# ---------------------------------------------------------------------------- #

class DaySchedule:
    
    _DB = {}
    
    def __init__(self,
        name :str,
        type :ScheduleType   ,
        value:tuple[int|float],
        *,
        ID:str|None=None,
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.type  = type
        self.value = value
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.DAY_SHCEDULE}AUTOID{hex(id(self))}"
        self.__ID = ID
        
    """ fundamental properties
    """
    
    @property
    def type(self) -> str:
        return str(self.__type)
    
    @type.setter
    @validate_enum(ScheduleType)
    def type(self, value:ScheduleType) -> None:        
        self.__type = ScheduleType(value)

    @property
    def value(self) -> list[int|float]:
        return self.__value
    
    @value.setter
    @validate_type(tuple)
    def value(self, value:list[int|float]) -> None:
        
        if len(value) != 24*6:
            raise ValueError(
                f"DaySchedule value should have length of 144 (24-hour data of 10-min. interval)"
            )
        
        match self.type:
            case ScheduleType.ONOFF:
                if any(v not in [0,1] for v in value):
                    raise ValueError(
                        f"Values for ON/OFF schedule should be 0 or 1"
                    )
            
            case ScheduleType.TEMPERATURE:
                if any(not (-50 < v < 100) for v in value):
                    raise ValueError(
                        f"Values for temperature schedule should be in (-50, 100)"
                    )
                    
            case ScheduleType.REAL:
                if any((v<0) for v in value):
                    raise ValueError(
                        f"Values for REAL schedule should be greater than zero"
                    )
        
        self.__value = value
        
    """ identity and eqality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> str:
        return hash(self.ID)
    
    def __eq__(self, other:DaySchedule) -> bool:
        
        # type validation
        if not isinstance(other, DaySchedule):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )

        # two day_schedules are equal if values and type are equal
        return (self.type  == other.type ) and\
               (self.value == other.value)
        
    """ in-out
    """
        
    @staticmethod
    def from_json(
        input:SimpleNamespace
        ) -> DaySchedule:
        
        return DaySchedule(
            input.name,
            input.type  ,
            tuple(input.values),
            ID=input.id,
        )
    
    def to_dragon(self) -> dragon.DaySchedule:
        
        return dragon.DaySchedule(
            self.ID,
            self.value,
            type=self.type,
        )
    
    @staticmethod
    def get_DB(
        key:str,
        *,
        as_dict:bool=False
        ) -> DaySchedule|list[DaySchedule]|str|dict:
        
        # special key for stable DB operation
        if key is None:
            return None
        
        # special key to get path of the database
        if key == "__path__":
            return os.path.join(Directory.PROFILE, "day_schedule.csv")
        
        # special key to get all item in the database
        if key == "__all__":
            return [
                DaySchedule.get_DB(_key, as_dict=as_dict)
                for _key in DaySchedule._DB.keys()
            ]
        
        #check if the key is a valid item name
        if key not in DaySchedule._DB.keys():
            raise KeyError(
                f"{key} is not a valid key of the Day-Schedule DB"
            )
        
        #return the day_schedule
        else:
            day_schedule =  DaySchedule._DB[key]
        
        # dictionarize the object if requried
        if not as_dict:
            return day_schedule
        else:
            return day_schedule.to_dict()

    """ representation
    """
    
    def to_dict(self) -> dict:
        return {
            "name" :self.name,
            "type" :self.type ,
            "value":self.value,
        }
        
    def __str__(self) -> str:
        
        match self.type:
            case ScheduleType.TEMPERATURE: decimal = 1
            case ScheduleType.ONOFF      : decimal = 0
            case ScheduleType.REAL       : decimal = 2
            
        num_lines = 4
        formatted_values = ",\n".join([
            ",\t".join([
                ", ".join([
                    f"{v:.{decimal}f}"
                    for v in self.value[int(6*(line*24/num_lines+group)):int(6*(line*24/num_lines+group+1))]
                    ])
                for group in range(int(24/num_lines))
                ])
            for line in range(num_lines)
        ])
        
        return f"DaySchedule {self.name} (ID={self.ID})\n{formatted_values}"
    
    def __repr__(self) -> str:
        return f"<DaySchedule {self.name} (ID={self.ID}) at {hex(id(self))}>"
    

class RuleSet:
    
    _Db = {}
    
    def __init__(self,
        name:str,
        weekdays:DaySchedule,
        weekends:DaySchedule,
        *,
        monday   :DaySchedule|None=None,
        tuesday  :DaySchedule|None=None,
        wednesday:DaySchedule|None=None,
        thursday :DaySchedule|None=None,
        friday   :DaySchedule|None=None,
        saturday :DaySchedule|None=None,
        sunday   :DaySchedule|None=None,
        holiday  :DaySchedule|None=None,
        ID:str|None=None,
        ) -> None:
        
        # user properties
        self.name = name
        
        # type check
        given_types = {
            day_schedule.type
            for day_schedule in [
                weekdays , weekends , 
                monday   , tuesday  , wednesday, thursday ,
                friday   , saturday , sunday   , holiday  ,   
            ]
            if day_schedule is not None
        }
        if len(given_types) > 1:
            raise AttributeError(
                f"Non-unique typed day-schedules are given for a ruleset: "
                f"{", ".join(list(given_types))}"
            )
        self.__type =  list(given_types)[0]
        
        # fundamental properties
        self.weekdays = weekdays
        self.weekends = weekends
        self.monday   = monday
        self.tuesday  = tuesday
        self.wednesday= wednesday
        self.thursday = thursday
        self.friday   = friday
        self.saturday = saturday
        self.sunday   = sunday
        self.holiday  = holiday
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.RULESET}AUTOID{hex(id(self))}"
        self.__ID = ID
    
    """ fundamental properties
    """
    
    @property
    def type(self) -> ScheduleType:
        return self.__type    
    
    def _validate_day_schedule_type(func) -> Callable:

        @wraps(func)
        def wrapper(self, value):
            
            if (value is not None) and (value.type != self.type):
                raise ValueError(
                    f"Type of the schedule doesn't match (expected {self.type}, got {value.type})"
                )
                
            return func(self, value)
        return wrapper
    
    @property
    def weekdays(self) -> DaySchedule:
        return self.__weekdays
    
    @weekdays.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule)
    def weekdays(self, value:DaySchedule) -> None:
        self.__weekdays = value
    
    @property
    def weekends(self) -> DaySchedule:
        return self.__weekends
    
    @weekends.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule)
    def weekends(self, value:DaySchedule) -> None:        
        self.__weekends = value
    
    @property
    def monday(self) -> DaySchedule:
        return self.__monday
    
    @monday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def monday(self, value:DaySchedule) -> None:
        self.__monday = value
        
    @property
    def tuesday(self) -> DaySchedule:
        return self.__tuesday
    
    @tuesday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def tuesday(self, value:DaySchedule) -> None:        
        self.__tuesday = value
        
    @property
    def wednesday(self) -> DaySchedule:
        return self.__wednesday
    
    @wednesday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def wednesday(self, value:DaySchedule) -> None:
        self.__wednesday = value
        
    @property
    def thursday(self) -> DaySchedule:
        return self.__thursday
    
    @thursday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def thursday(self, value:DaySchedule) -> None:
        self.__thursday = value
        
    @property
    def friday(self) -> DaySchedule:
        return self.__friday
    
    @friday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def friday(self, value:DaySchedule) -> None:
        self.__friday = value
        
    @property
    def saturday(self) -> DaySchedule:
        return self.__saturday
    
    @saturday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def saturday(self, value:DaySchedule) -> None:
        self.__saturday = value
        
    @property
    def sunday(self) -> DaySchedule:
        return self.__sunday
    
    @sunday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def sunday(self, value:DaySchedule) -> None:
        self.__sunday = value
        
    @property
    def holiday(self) -> DaySchedule:
        return self.__holiday
    
    @holiday.setter
    @_validate_day_schedule_type
    @validate_type(DaySchedule, allow_none=True)
    def holiday(self, value:DaySchedule) -> None:
        self.__holiday = value
    
    """ usefule methods
    """
    
    def get_unique_day_schedules(self) -> dict[str, DaySchedule]:
        
        return {
            day_schedule.ID: day_schedule
            for day_schedule in [
                self.weekdays , self.weekends , 
                self.monday   , self.tuesday  , self.wednesday, self.thursday ,
                self.friday   , self.saturday , self.sunday   , self.holiday  ,
            ]
            if day_schedule is not None
        }
    
    """ identiy and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> str:
        return hash(self.ID)
    
    def __eq__(self, other:RuleSet) -> bool:
        
        # type validation
        if not isinstance(other, RuleSet):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )

        # two day_schedules are equal if values and type are equal
        return (self.type  == other.type ) and\
               (self.value == other.value)
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input            :SimpleNamespace       ,
        day_schedule_dict:dict[str, DaySchedule],
        ) -> RuleSet:
        
        return RuleSet(
            input.name,
            day_schedule_dict[input.weekdays_id],
            day_schedule_dict[input.weekends_id],
            monday   =day_schedule_dict.get(input.monday_id   , None),
            tuesday  =day_schedule_dict.get(input.tuesday_id  , None),
            wednesday=day_schedule_dict.get(input.wednesday_id, None),
            thursday =day_schedule_dict.get(input.thursday_id , None),
            friday   =day_schedule_dict.get(input.friday_id   , None),
            saturday =day_schedule_dict.get(input.saturday_id , None),
            sunday   =day_schedule_dict.get(input.sunday_id   , None),
            holiday  =day_schedule_dict.get(input.holiday_id  , None),
            ID=input.id
            )
    
    def to_dragon(self,
        *,
        day_schedule_dict:dict[str, dragon.DaySchedule]=dict()
        ) -> dragon.RuleSet:
        
        # create undictionarized day_schedules
        # note that given day_schedule dict is not changed
        day_schedule_dict = deepcopy(day_schedule_dict)
        for ID, day_schedule in self.get_unique_day_schedules().items():
            if ID not in day_schedule_dict.keys():
                day_schedule_dict[ID] = day_schedule.to_dragon()
                
        # create an dragon-ruleset
        return dragon.RuleSet(
            self.ID,
            day_schedule_dict[self.weekdays.ID],
            day_schedule_dict[self.weekends.ID],
            monday   = day_schedule_dict.get(getattr(self.monday   , "ID", None), None),
            tuesday  = day_schedule_dict.get(getattr(self.tuesday  , "ID", None), None),
            wednesday= day_schedule_dict.get(getattr(self.wednesday, "ID", None), None),
            thursday = day_schedule_dict.get(getattr(self.thursday , "ID", None), None),
            friday   = day_schedule_dict.get(getattr(self.friday   , "ID", None), None),
            saturday = day_schedule_dict.get(getattr(self.saturday , "ID", None), None),
            sunday   = day_schedule_dict.get(getattr(self.sunday   , "ID", None), None),
            holiday  = day_schedule_dict.get(getattr(self.holiday  , "ID", None), None),
        )
        
    @staticmethod
    def get_DB(
        key:str,
        *,
        as_dict:bool=False
        ) -> RuleSet|list[RuleSet]|str|dict:
        
        # special key for stable DB operation
        if key is None:
            return None
        
        # special key to get path of the database
        if key == "__path__":
            return os.path.join(Directory.PROFILE, "ruleset.csv")
        
        # special key to get all item in the database
        if key == "__all__":
            return [
                RuleSet.get_DB(_key, as_dict=as_dict)
                for _key in RuleSet._DB.keys()
            ]
        
        #check if the key is a valid item name
        if key not in RuleSet._DB.keys():
            raise KeyError(
                f"{key} is not a valid key of the RuleSet DB"
            )
        
        #return the ruleset
        else:
            ruleset =  RuleSet._DB[key]
        
        # dictionarize the object if requried
        if not as_dict:
            return ruleset
        else:
            return ruleset.to_dict()
    
    """ representation
    """
    
    def to_dict(self) -> dict:
        
        return {
            "name": self.name,
            "weekdays": self.weekdays.name,
            "weekends": self.weekends.name,
            "monday"   : getattr(self.monday   , "name", None),
            "tuesday"  : getattr(self.tuesday  , "name", None),
            "wednesday": getattr(self.wednesday, "name", None),
            "thursday" : getattr(self.thursday , "name", None),
            "friday"   : getattr(self.friday   , "name", None),
            "saturday" : getattr(self.saturday , "name", None),
            "sunday"   : getattr(self.sunday   , "name", None),
            "holiday"  : getattr(self.holiday  , "name", None),
            "day_schedules":[
                day_schedule.to_dict()
                for day_schedule in self.get_unique_day_schedules().values()
            ]
        }
    
    def __str__(self) -> str:
        
        formatted_values = "\n".join([
            f"\t{day_of_week:9s}: {getattr(self, day_of_week).name}"
            for day_of_week in [
                "monday"   , "tuesday"  , "wednesday", "thursday" ,
                "friday"   , "saturday" , "sunday"   , "holiday"  ,
            ]
            if getattr(self, day_of_week) is not None
        ])
        
        return f"RuleSet {self.name} (ID={self.ID})\n{formatted_values}"
    
    def __repr__(self) -> str:
        return f"<RuleSet {self.name} (ID={self.ID}) at {hex(id(self))}>"
    

class Period:
    
    def __init__(self,
        start_month:int,
        start_day  :int,
        end_month  :int,
        end_day    :int,
        ruleset:RuleSet
        ) -> None:
        
        # default setting for initiation
        self.__start_month = 1
        self.__start_day   = 1
        self.__end_month = 12
        self.__end_day   = 31
        
        # fundamental properties
        self.start_month = start_month
        self.start_day   = start_day
        self.end_month   = end_month
        self.end_day     = end_day
        self.ruleset=ruleset
        
    """ fundamental properties
    """
    
    @property
    def start_month(self) -> int:
        return self.__start_month
    
    @start_month.setter
    @validate_range(min=1, max=12)
    @validate_type(int)
    def start_month(self, value:int) -> None:
        
        if self.end_month < value:
            self.end_month = value
            self.end_day   = self.start_day
            
        elif (self.end_month == value) and (self.end_day < self.start_day):
            self.end_day = self.start_day
        
        self.__start_month = value

    @property
    def start_day(self) -> int:
        return self.__start_day
    
    @start_day.setter
    @validate_range(min=1, max=31)
    @validate_type(int)
    def start_day(self, value:int) -> None:
        
        if (self.end_month == self.start_month) and (self.end_day < value):
            self.end_day = value
        
        self.__start_day = value
        
    @property
    def end_month(self) -> int:
        return self.__end_month
    
    @end_month.setter
    @validate_range(min=1, max=12)
    @validate_type(int)
    def end_month(self, value:int) -> None:
        
        if (value < self.start_month) or ((self.start_month == value) and (self.end_day < self.start_day)):
            raise ValueError(
                f"End-date (got {value}/{self.end_day}) cannot be earlier than start-date ({self.start_month}/{self.start_day})"
            )
        
        self.__end_month = value
        
    @property
    def end_day(self) -> int:
        return self.__end_day
    
    @end_day.setter
    @validate_range(min=1, max=31)
    @validate_type(int)
    def end_day(self, value:int) -> None:
        
        if (self.start_month == self.end_month) and (value < self.start_day):
            raise ValueError(
                f"End-date (got {self.end_month}/{value}) cannot be earlier than start-date ({self.start_month}/{self.start_day})"
            )
        
        self.__end_day = value
        
    @property
    def ruleset(self) -> RuleSet:
        return self.__ruleset
    
    @ruleset.setter
    @validate_type(RuleSet)
    def ruleset(self, value:RuleSet) -> None:
        self.__ruleset = value
    
    """ identity and equality
    """
    
    def __eq__(self, other:Period) -> bool:
        
        # type validation
        if not isinstance(other, Period):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
        
        # two periods are equal if start&end date and ruleset are equal
        return ((self.start_month, self.start_day) == (other.start_month, other.start_day)) and\
               ((self.end_month  , self.end_day  ) == (other.end_month  , other.end_day  )) and\
               (self.ruleset == other.ruleset)
    
    """ representation
    """
    
    def __str__(self) -> str:
        return f"Period {self.start_month}/{self.start_day} ~ {self.end_month}/{self.end_day}: applied {str(self.ruleset)}"
    
    def __repr__(self) -> str:
        return f"<Period from {self.start_month}/{self.start_day} to {self.end_month}/{self.end_day} at {hex(id(self))}>"
    

class Schedule:
    
    def __init__(self,
        name:str,
        *args:Period,
        ID:str|None = None
        ) -> None:
        
        # user properties
        self.name = name
        
        #fundamental properties
        self.period = list(args)
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.SCHEDULE}AUTOID{hex(id(self))}"
        self.__ID = ID
        
    """ fundamental properties
    """
    
    """ useful methods
    """
    
    def get_unique_rulesets(self) -> dict[str, RuleSet]:
        
        return {
            period.ruleset.ID: period.ruleset
            for period in self.period
        }
        
    def get_unique_day_schedules(self) -> dict[str, DaySchedule]:
        
        return {
            k:v
            for ruleset in self.get_unique_rulesets().values()
            for k,v in ruleset.get_unique_day_schedules().items()
        }
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> str:
        hash(self.ID)
        
    def __eq__(self, other:Schedule) -> bool:
        
        # type validation
        if not isinstance(other, Schedule):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
        
        # two schedules are equal if have same periods
        return (len(self.period) == len(other.period)) and\
               all(self_period == other_period for self_period, other_period in zip(self.period, other.period))
    
    """ in-out
    """
    
    @staticmethod
    def from_json(
        input       :SimpleNamespace   ,
        ruleset_dict:dict[str, RuleSet],
        ) -> Schedule:
        
        return Schedule(
            input.name,
            *[
                Period(
                    *[int(v) for v in re.split(r"\D", period.start)],
                    *[int(v) for v in re.split(r"\D", period.end  )],
                    ruleset_dict[period.ruleset_id],
                )
                for period in input.periods
            ],
            ID=input.id
        )
    
    def to_dragon(self,
        *,
        ruleset_dict:dict[str, dragon.RuleSet]=dict()
        ) -> dragon.Schedule:
        
        # create undictionarized rulesets
        # note that given ruleset dict is not changed
        ruleset_dict = deepcopy(ruleset_dict)
        for ID, ruleset in self.get_unique_rulesets().items():
            if ID not in ruleset_dict.keys():
                ruleset_dict[ID] = ruleset.to_dragon()
        
        # crate an dragon schedule
        return dragon.Schedule.from_compact(
            self.ID,
            [
                (
                    f"{period.start_month:02d}{period.start_day:02d}", 
                    f"{period.end_month  :02d}{period.end_day  :02d}", 
                    ruleset_dict[period.ruleset.ID]
                )
                for period in self.period
            ]
        )
    
    @staticmethod
    def get_DB(
        key:str,
        *,
        as_dict:bool=False
        ) -> Schedule:
        
        # special key for stable DB operation
        if key is None:
            return None
        
        if key == "__path__":
            return os.path.join(Directory.PROFILE, "schedule.csv")
        
        elif key == "__all__":
            return [
                Schedule.get_DB(_key, as_dict=as_dict)
                for _key in Schedule._DB.keys()
                ]
        
        elif key not in Schedule._DB.keys():
            raise KeyError(
                f"{key} is not a valid key of the default schedule DB"
            )
            
        else:
            schedule = Schedule._DB[key]
            
        if not as_dict:
            return schedule
        else:
            return schedule.to_dict()
    
    """ representation
    """
    
    def to_dict(self) -> dict:
        
        return {
            "name":self.name,
            "period":[
                {
                    "start": f"{period.start_month:02d}/{period.start_day:02d}",
                    "end"  : f"{period.end_month  :02d}/{period.end_day  :02d}",
                    "ruleset": period.ruleset.name
                }
                for period in self.period
            ],
            "rulesets": [
                ruleset.to_dict()
                for ruleset in self.get_unique_rulesets().values()
            ],
            "day_schedules": [
                day_schedule.to_dict()
                for day_schedule in self.get_unique_day_schedules().values()
            ]
        }
        
    def __str__(self) -> str:
        
        formatted_values = "\n".join([
            f"\t-{str(period)}"
            for period in self.period
        ])
        
        return f"Schedule {self.name} (ID={self.ID})\n{formatted_values}"
    
    def __repr__(self) -> str:
        return f"<Schedule {self.name} (ID={self.ID}) at {hex(id(self))}>"


        
# ---------------------------------------------------------------------------- #
#                                    PROFILE                                   #
# ---------------------------------------------------------------------------- #


class Profile:
    
    _DB = {}
    
    def __init__(self,
        name:str,
        heating_setpoint :Schedule|None=None,
        cooling_setpoint :Schedule|None=None,
        hvac_availability:Schedule|None=None,
        occupant         :Schedule|None=None,
        lighting         :Schedule|None=None,
        equipment        :Schedule|None=None,
        hotwater         :list[int|float] = [0]*12,
        *,
        ID:str|None=None
        ) -> None:
        
        # user properties
        self.name = name
        
        # fundamental properties
        self.heating_setpoint  = heating_setpoint
        self.cooling_setpoint  = cooling_setpoint
        self.hvac_availability = hvac_availability
        self.occupant          = occupant
        self.lighting          = lighting
        self.equipment         = equipment
        
        #! TODO: 이거 유효성 검사랑 format 등등...
        self.hotwater = hotwater
        
        # set default ID if not specified
        if ID is None:
            ID = f"{AUTOID_PREFIX.PROFILE}AUTOID{hex(id(self))}"
        self.__ID = ID
        
    """ fundamental properties
    """
    
    @property
    def heating_setpoint(self) -> Schedule:
        return self.__heating_setpoint
    
    @heating_setpoint.setter
    @validate_type(Schedule, allow_none=True)
    def heating_setpoint(self, value:Schedule) -> None:
        self.__heating_setpoint = value
    
    @property
    def cooling_setpoint(self) -> Schedule:
        return self.__cooling_setpoint
    
    @cooling_setpoint.setter
    @validate_type(Schedule, allow_none=True)
    def cooling_setpoint(self, value:Schedule) -> None:
        self.__cooling_setpoint = value
        
    @property
    def hvac_availability(self) -> Schedule:
        return self.__hvac_availability
    
    @hvac_availability.setter
    @validate_type(Schedule, allow_none=True)
    def hvac_availability(self, value:Schedule) -> None:
        self.__hvac_availability = value
        
    @property
    def occupant(self) -> Schedule:
        return self.__occupant
    
    @occupant.setter
    @validate_type(Schedule, allow_none=True)
    def occupant(self, value:Schedule) -> None:
        self.__occupant = value
    
    @property
    def lighting(self) -> Schedule:
        return self.__lighting
    
    @lighting.setter
    @validate_type(Schedule, allow_none=True)
    def lighting(self, value:Schedule) -> None:
        self.__lighting = value
    
    @property
    def equipment(self) -> Schedule:
        return self.__equipment
    
    @equipment.setter
    @validate_type(Schedule, allow_none=True)
    def equipment(self, value:Schedule) -> None:
        self.__equipment = value
        
    
     
    """ usefule methods
    """
    
    def get_unique_day_schedules(self) -> dict[str, DaySchedule]:
        
        return {
            k:v
            for ruleset in self.get_unique_rulesets().values()
            for k, v in ruleset.get_unique_day_schedules().items()
        }
    
    def get_unique_rulesets(self) -> dict[str, RuleSet]:
        
        return {
            k:v
            for schedule in self.get_unique_schedules().values()
            for k, v in schedule.get_unique_rulesets().items()
        }
    
    def get_unique_schedules(self) -> dict[str, Schedule]:
        
        return {
            schedule.ID: schedule
            for schedule in [
                self.heating_setpoint ,
                self.cooling_setpoint ,
                self.hvac_availability,
                self.occupant ,
                self.lighting ,
                self.equipment,
            ]
            if schedule is not None
        }
    
    """ identity and equality
    """
    
    @property
    def ID(self) -> str:
        return self.__ID
    
    def __hash__(self) -> str:
        hash(self.ID)
        
    def __eq__(self, other:Schedule):
        
        # type validation
        if not isinstance(other, Profile):
            raise TypeError(
                f"Cannot compare {type(self)} instance with {type(other)} instance"
            )
            
        # two profiles are equal if all schedules are equal
        return (self.heating_setpoint  == other.heating_setpoint ) and\
               (self.cooling_setpoint  == other.cooling_setpoint ) and\
               (self.hvac_availability == other.hvac_availability) and\
               (self.occupant  == other.occupant ) and\
               (self.lighting  == other.lighting ) and\
               (self.equipment == other.equipment)
    
    
    """ in-out 
    """
    
    @staticmethod
    def get_DB(
        key:str,
        *,
        as_dict:bool=False
        ) -> Profile:
        
        # special key for stable DB operation
        if key is None:
            return None
        
        if key == "__path__":
            return os.path.join(Directory.PROFILE, "profile.csv")
        
        elif key == "__all__":
            return [
                Profile.get_DB(_key, as_dict=as_dict)
                for _key in Profile._DB.keys()
                ]
        
        elif key not in Profile._DB.keys():
            raise KeyError(
                f"{key} is not a valid key of the default profile DB"
            )
            
        else:
            profile = Profile._DB[key]
            
        if not as_dict:
            return profile
        else:
            return profile.to_dict()
    
    
    @staticmethod
    def from_json(
        input:SimpleNamespace,
        schedule_dict:dict[str, Schedule]
        ) -> Profile:
        
        return Profile(
            input.name,
            schedule_dict.get(input.heating_setpoint_id) ,
            schedule_dict.get(input.cooling_setpoint_id) ,
            schedule_dict.get(input.hvac_availability_id),
            schedule_dict.get(input.occupant_id),
            schedule_dict.get(input.lighting_id),
            schedule_dict.get(input.equipment_id),
            ID = input.id
            )
        
    def to_dragon(self,
        *,
        schedule_dict:dict[str, dragon.Schedule]=dict()
        ) -> dragon.Profile:
        
        # create undictionarized schedules
        # note that given schedule dict is not changed
        schedule_dict = deepcopy(schedule_dict)
        for ID, schedule in self.get_unique_schedules().items():
            if ID not in schedule_dict.keys():
                schedule_dict[ID] = schedule.to_dragon()
        
        # create an dragon profile
        return dragon.Profile(
            self.name,
            schedule_dict.get(getattr(self.heating_setpoint , "ID", None), None),
            schedule_dict.get(getattr(self.cooling_setpoint , "ID", None), None),
            schedule_dict.get(getattr(self.hvac_availability, "ID", None), None),
            schedule_dict.get(getattr(self.occupant , "ID", None), None),
            schedule_dict.get(getattr(self.lighting , "ID", None), None),
            schedule_dict.get(getattr(self.equipment, "ID", None), None),            
            )
    
    """ representation
    """
    
    def to_dict(self) -> dict:
        
        return {
            "name": self.name,
            "heating_setpoint" : getattr(self.heating_setpoint, "name", None) ,
            "cooling_setpoint" : getattr(self.cooling_setpoint, "name", None) ,
            "hvac_availability": getattr(self.hvac_availability, "name", None), 
            "occupant" : getattr(self.occupant , "name", None),
            "lighitng" : getattr(self.lighting , "name", None),
            "equipment": getattr(self.equipment, "name", None),
            "schedules": [
                schedule.to_dict()
                for schedule in self.get_unique_schedules().values()
            ],
            "rulesets": [
                ruleset.to_dict()
                for ruleset in self.get_unique_rulesets().values()
            ],
            "day_schedules": [
                day_schedule.to_dict()
                for day_schedule in self.get_unique_day_schedules().values()
            ]
        }
        
    def __str__(self) -> str:
        return "\n".join([
            f"Profile {self.name} (ID={self.ID})",
            f"\t-heating setpoint : {self.heating_setpoint.name }",
            f"\t-cooling setpoint : {self.cooling_setpoint.name }",
            f"\t-hvac availability: {self.hvac_availability.name}",
            f"\t-occupant : {self.occupant.name }",
            f"\t-lighting : {self.lighting.name }",
            f"\t-equipment: {self.equipment.name}",
            ])
    
    def __repr__(self) -> str:
        return f"<Profile {self.name} (ID={self.ID}) at {hex(id(self))}>"



# ---------------------------------------------------------------------------- #
#                           INITIATION: LOAD PROFILES                          #
# ---------------------------------------------------------------------------- #

DaySchedule._DB = {
    row.name: DaySchedule(
        row.name,
        row["type"]         ,
        tuple(row.values[2:]),
        ID=f"{SpecialTag.DB}{row.name}"
    )
    for _, row in df_dayschedule.iterrows()
}

RuleSet._DB = {
    row.name: RuleSet(
        row.name,
        DaySchedule.get_DB(row["weekdays"]),
        DaySchedule.get_DB(row["weekends"]),
        monday   = DaySchedule.get_DB(row["monday"   ]),
        tuesday  = DaySchedule.get_DB(row["tuesday"  ]),
        wednesday= DaySchedule.get_DB(row["wednesday"]),
        thursday = DaySchedule.get_DB(row["thursday" ]),
        friday   = DaySchedule.get_DB(row["friday"   ]),
        saturday = DaySchedule.get_DB(row["saturday" ]),
        sunday   = DaySchedule.get_DB(row["sunday"   ]),
        holiday  = DaySchedule.get_DB(row["holiday"  ]),
        ID=f"{SpecialTag.DB}{row.name}"
    )
    for _, row in df_ruleset.iterrows()
}

Schedule._DB = {
    row.name: Schedule(
        row.name,
        *[
            Period(
                *[int(v) for v in re.findall(r"\d{1,2}", row[f"start{day}"])],
                *[int(v) for v in re.findall(r"\d{1,2}", row[f"end{day}"  ])],
                RuleSet.get_DB(row[f"ruleset{day}"]), 
            )
            for day in range(1,366)
            if not pd.isna(row[f"start{day}"])
        ]
    )
    for _, row in df_schedule.iterrows()
}

Profile._DB = {
    row.name: Profile(
        row.name,
        Schedule.get_DB(row["heating"]),
        Schedule.get_DB(row["cooling"]),
        Schedule.get_DB(row["hvac_availability"]),
        Schedule.get_DB(row["occupant"]),
        Schedule.get_DB(row["lighting"]),
        Schedule.get_DB(row["equipment"]),
        row[[f"hotwater{mth}" for mth in range(1,13)]],
        ID = f"{SpecialTag.DB}{row.name}"
    )
    for _, row in df_profile.iterrows()
}












