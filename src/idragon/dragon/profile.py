
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import re
import os
import math
import datetime
from typing import (
    Any     ,
    Callable,
)
from enum import Enum
from copy import deepcopy
from collections import UserList

# third-party modules

# local modules
from ..imugi import (
    # variables
    SMALLEST_VALUE,
    # classes
    IdfObject,
    IdfObjectList,
    IDF      ,
)
from ..utils import (
    validate_type ,
    validate_range,
    validate_enum ,
)
from ..common import (
    Setting,
)


# ---------------------------------------------------------------------------- #
#                                    CLASSES                                   #
# ---------------------------------------------------------------------------- #


class ScheduleType(str, Enum):
    
    TEMPERATURE ="temperature"
    ONOFF       ="onoff"
    REAL        ="real" 
    
    def __str__(self) -> str:
        return self.value   

class DaySchedule(UserList):
    
    DATA_INTERVAL = 6 # per hour
    
    MAX_TEMPERATURE = 200
    MIN_TEMPERATURE = -50
    
    def __init__(self,
        name         :str            ,
        value        :list[int|float]|None=None,
        *,
        type:ScheduleType=ScheduleType.REAL,
        unit:str=None
        ) -> None:
        
        if name is None:
            name = hex(id(self))
        self.name = name
        
        self.type = ScheduleType(type)
        self.unit = unit
        
        if value is None:
            value = [0]*self.fixed_length
        
        if len(value) != self.fixed_length:
            raise ValueError(
                f""
            )
        
        self.data = [0] * self.fixed_length
        for idx, item in enumerate(value):
            self[idx] = item
        
        
    @property
    def type(self) -> ScheduleType|str:
        return self.__schedule_type
    
    @type.setter
    @validate_type(ScheduleType)
    def type(self, value: ScheduleType|str) -> None:
        self.__schedule_type = value
    
    @property
    def fixed_length(self) -> int:
        return DaySchedule.DATA_INTERVAL * 24
    
    def __setitem__(self, index:int, item:int|float) -> None:
        
        match self.type:
            case ScheduleType.TEMPERATURE:
                if not (DaySchedule.MIN_TEMPERATURE <= item <= DaySchedule.MAX_TEMPERATURE):
                    raise ValueError(
                        f"Temperature-type schedule values must be in [{DaySchedule.MIN_TEMPERATURE}, {DaySchedule.MAX_TEMPERATURE}]"
                    )
            case ScheduleType.ONOFF:
                if item not in [0, 1]:
                    raise ValueError(
                        f"ONOFF-type schedule values must be 0 or 1."
                    )
            case ScheduleType.REAL:
                pass
        
        super().__setitem__(index, item)
        
    """ algebraric methods
    """
        
    def __mul__(self, value:int|float) -> DaySchedule:
        return DaySchedule(
            self.name,
            [item * value for item in self.data],
            type=self.type
            )
        
    def __rmul__(self, value:int|float) -> DaySchedule:
        return self.__mul__(value)
    
    def __truediv__(self, value:int|float) -> DaySchedule:
        return DaySchedule(
            self.name,
            [item / value for item in self.data],
            type=self.type
            )
        
    def __add__(self, other:DaySchedule) -> DaySchedule:
        
        if self.type != other.type:
            raise TypeError(
                f"Cannot add {self.type}-type DaySchedule to {other.type}-type DaySchedule."
            )
        
        return DaySchedule(
            f"{self.name}:ADD:{other.name}",
            [self_item+other_item for self_item, other_item in zip(self.data, other.data)],
            type=self.type
        )
        
    def __radd__(self, other:DaySchedule) -> DaySchedule:
        return self.__add__(other)
    
    def __sub__(self, other:DaySchedule) -> DaySchedule:
        
        if self.type != other.type:
            raise TypeError(
                f"Cannot substract {self.type}-type DaySchedule to {other.type}-type DaySchedule."
            )
            
        return self.__add__(other.__mul__(-1))
    
    def __and__(self, other:DaySchedule) -> DaySchedule:
        
        if (self.type is not ScheduleType.ONOFF) or (other.type is not ScheduleType.ONOFF):
            raise TypeError(
                f"Cannot 'AND' operate for non-ONOFF typed DaySchedules (get: {self.type} and {other.type})."
            )
            
        return DaySchedule(
            f"{self.name}:AND:{other.name}",
            [int(bool(a) and bool(b)) for a,b in zip(self.data, other.data)],
            type=ScheduleType.ONOFF
        )
        
    def __or__(self, other:DaySchedule) -> DaySchedule:
        
        if (self.type is not ScheduleType.ONOFF) or (other.type is not ScheduleType.ONOFF):
            raise TypeError(
                f"Cannot 'OR' operate for non-ONOFF typed DaySchedules (get: {self.type} and {other.type})."
            )
            
        return DaySchedule(
            f"{self.name}:OR:{other.name}",
            [int(bool(a) or bool(b)) for a,b in zip(self.data, other.data)],
            type=ScheduleType.ONOFF
        )
        
    def __invert__(self) -> DaySchedule:
        
        if self.type is not ScheduleType.ONOFF:
            raise TypeError(
                f"Cannot 'invert' operate for non-ONOFF typed DaySchedule (get: {self.type})."
            )
            
        return DaySchedule(
            f"{self.name}:INVERTED",
            [int(not bool(value)) for value in self.data]
        )
        
    def element_min(self, other:DaySchedule) -> DaySchedule:
        
        return DaySchedule(
            f"{self.name}:MIN:{other.name}",
            [min(a,b) for a,b in zip(self.data, other.data)]
        )
        
    def element_max(self, other:DaySchedule) -> DaySchedule:
        
        return DaySchedule(
            f"{self.name}:MAX:{other.name}",
            [max(a,b) for a,b in zip(self.data, other.data)]
        )
    
    @property
    def min(self) -> int|float:
        return min(self.data)
    
    @property
    def max(self) -> int|float:
        return max(self.data)
    
    def normalize_by_max(self, inplace:bool=False, *, new_name:str=None):
        
        if self.max == 0:
            scaler = 1
        else:
            scaler = self.max
        
        if inplace:
            self.data = [item/scaler for item in self.data]
            return
        
        else:
            
            if new_name is None:
                new_name = self.name + "_normalized"
            
            normalized_schedule = self / scaler
            normalized_schedule.name = new_name
            
            return normalized_schedule
    
    """ prohibited methods
    """
    
    def __delitem__(self, index:int) -> None:
        raise AttributeError(
            f"Cannot delete item from the fixed-length ({self.fixed_length}) DaySchedule"
        )
        
    def append(self, item:Any) -> None:
        raise AttributeError(
            f"Cannot append to the fixed-length ({self.fixed_length}) DaySchedule"
        )

    def extend(self, items: list) -> None:
        raise AttributeError(
            f"Cannot extend the fixed-length ({self.fixed_length}) DaySchedule"
        )
        
    def pop(self, index:int= -1) -> None:
        raise AttributeError(
            f"Cannot pop from the fixed-length ({self.fixed_length}) DaySchedule"
        )
        
    def clear(self) -> None:
        raise AttributeError(
            f"Cannot clear the fixed-length ({self.fixed_length}) DaySchedule"
        )
        
    def insert(self, index:int, item:Any) -> None:
        raise AttributeError(
            f"Cannot insert to the fixed-length ({self.fixed_length}) DaySchedule"
        )
    
    """ time-related operations
    """
    
    @staticmethod
    def time_tuple() -> list[tuple[int]]:
        return [
            (hh + (1 if math.isclose(mm,60) else 0), (0 if math.isclose(mm, 60) else mm)) 
            for hh in range(24)
            for mm in [int(n*60/DaySchedule.DATA_INTERVAL) for n in range(1,DaySchedule.DATA_INTERVAL+1)]
            ]
    
    def compactize(self) -> list[tuple[int, int, int|float]]:
        
        time_tuple = DaySchedule.time_tuple()
        
        compact_tuples = []
        for idx, value in enumerate(self.data):
            
            new_tuple = (*time_tuple[idx], value)
            
            if (idx == 0) or (value != self.data[idx-1]):
                compact_tuples.append(new_tuple)
            else:
                compact_tuples[-1] = new_tuple           
        
        return compact_tuples
    
    @classmethod
    def from_compact(cls, name, values:list[tuple], type=ScheduleType.REAL) -> DaySchedule:
        
        if values[-1][:2] != (24,0):
            raise ValueError(
                f""
            )
            
        schedule_values = []
        for time_tuple in DaySchedule.time_tuple():
            
            hh, mm, value = values[0]
            
            if time_tuple <= (hh, mm):
                schedule_values.append(value)
            else:
                values.pop(0)
                schedule_values.append(values[0][2])
         
        return cls(name, schedule_values, type=type)
    
    """ representation
    """
    
    def __str__(self) -> str:
        return f"DaySchedule {self.name}:\n" + "\n".join([
            f"\tUntil {hh:02d}:{mm:02d} -> {value}" for hh,mm,value in self.compactize()
        ])
    
    def __repr__(self) -> str:
        return f"<DaySchedule {self.name} at {hex(id(self))}>"

    def to_idf_compactexpr(self) -> list[str]:
        return sum([
            [f"Until: {hh:02d}:{mm:02d}", str(v)]
            for hh, mm, v in self.compactize()
        ], start=[])
    
class RuleSet:
    
    def __init__(self,
        name,
        weekdays:DaySchedule=DaySchedule("anonymous"),
        weekends:DaySchedule=DaySchedule("anonymous"),
        *,
        monday   :DaySchedule|None=None,
        tuesday  :DaySchedule|None=None,
        wednesday:DaySchedule|None=None,
        thursday :DaySchedule|None=None,
        friday   :DaySchedule|None=None,
        saturday :DaySchedule|None=None,
        sunday   :DaySchedule|None=None,
        holiday  :DaySchedule|None=None,
    ) -> None:
        
        if any(
            (day_schedule is not None) and (day_schedule.type != weekdays.type)
            for day_schedule in [weekends, monday, tuesday, wednesday, thursday, friday, saturday, sunday, holiday]
            ):
            raise ValueError(
                f"Unmatched typed schedule is included (expected weekdays': {weekdays.type})"
            )
        
        if name is None:
            name = hex(id(self))
        self.name = name
        self.__type = weekdays.type
        
        self.__weekdays = weekdays
        self.__weekends = weekends
        self.__monday    = monday
        self.__tuesday   = tuesday
        self.__wednesday = wednesday
        self.__thursday  = thursday
        self.__friday    = friday
        self.__saturday  = saturday
        self.__sunday    = sunday
        self.__holiday   = holiday
    
    """ fundamental properties
    """
    
    @property
    def type(self) -> ScheduleType|str:
        return self.__type
    
    @property
    def weekdays(self) -> DaySchedule:
        return self.__weekdays
    
    @weekdays.setter
    @validate_type(DaySchedule)
    def weekdays(self, value) -> None:
        self.__weekdays = value
        
    @property
    def weekends(self) -> DaySchedule:
        return self.__weekends
    
    @weekends.setter
    @validate_type(DaySchedule)
    def weekends(self, value) -> None:
        self.__weekends = value
    
    @property
    def monday(self) -> DaySchedule:
        return self.__monday
    
    @monday.setter
    @validate_type(DaySchedule)
    def monday(self, value: DaySchedule) -> None:
        self.__monday = value
    
    @property
    def tuesday(self) -> DaySchedule:
        return self.__tuesday
    
    @tuesday.setter
    @validate_type(DaySchedule)
    def tuesday(self, value: DaySchedule) -> None:
        self.__tuesday = value
        
    @property
    def wednesday(self) -> DaySchedule:
        return self.__wednesday
    
    @wednesday.setter
    @validate_type(DaySchedule)
    def wednesday(self, value: DaySchedule) -> None:
        self.__wednesday = value
        
    @property
    def thursday(self) -> DaySchedule:
        return self.__thursday
    
    @thursday.setter
    @validate_type(DaySchedule)
    def thursday(self, value: DaySchedule) -> None:
        self.__thursday = value
    
    @property
    def friday(self) -> DaySchedule:
        return self.__friday
    
    @friday.setter
    @validate_type(DaySchedule)
    def friday(self, value: DaySchedule) -> None:
        self.__friday = value
    
    @property
    def saturday(self) -> DaySchedule:
        return self.__saturday
    
    @saturday.setter
    @validate_type(DaySchedule)
    def saturday(self, value: DaySchedule) -> None:
        self.__saturday = value
    
    @property
    def sunday(self) -> DaySchedule:
        return self.__sunday
    
    @sunday.setter
    @validate_type(DaySchedule)
    def sunday(self, value: DaySchedule) -> None:
        self.__sunday = value
    
    @property
    def holiday(self) -> DaySchedule:
        return self.__holiday
    
    @holiday.setter
    @validate_type(DaySchedule)
    def holiday(self, value: DaySchedule) -> None:
        self.__holiday = value
    
    """ algebraric methods
    """
    
    def __mul__(self, value:int|float) -> RuleSet:
        return RuleSet(
            self.name,
            **{
                k: dayschedule.__mul__(value)
                for k,dayschedule in self.to_dict().items()
                if isinstance(dayschedule, DaySchedule)
            }
        )
        
    def __rmul__(self, value:int|float) -> RuleSet:
        return self.__mul__(value)
    
    def __truediv__(self, value:int|float) -> RuleSet:
        return RuleSet(
            self.name,
            **{
                k: dayschedule.__truediv__(value)
                for k,dayschedule in self.to_dict().items()
                if isinstance(dayschedule, DaySchedule)
            }
        )
    
    @staticmethod
    def __operate_dayschedule_with_default(
        operator     :Callable   ,
        self_day     :DaySchedule,
        other_day    :DaySchedule,
        self_default :DaySchedule,
        other_default:DaySchedule,
        ) -> DaySchedule:
        
        if (self_day is None) and (other_day is None):
            return None
        
        else:
            if self_day is None:
                self_day = self_default
            if other_day is None:
                other_day = other_default
            
            return operator(self_day, other_day)        
        
    def __add__(self, other:RuleSet) -> RuleSet:
        
        if self.type != other.type:
            raise TypeError(
                f"Cannot add {self.type}-type RuleSet to {other.type}-type RuleSet."
            )
            
        return RuleSet(
            f"{self.name}:ADD:{other.name}",
            **{
                k: RuleSet.__operate_dayschedule_with_default(
                    lambda a, b: a + b,
                    self_day    , other_day    ,
                    self_default, other_default,
                )
                for k, self_day, other_day, self_default, other_default
                in zip(
                    self.to_dict().keys(),
                    self.to_dict().values(), other.to_dict().values(),
                    [
                        self.weekdays, self.weekends,
                        self.weekdays, self.weekdays, self.weekdays, self.weekdays, self.weekdays,
                        self.weekends, self.weekends, self.weekends,
                    ],
                    [
                        other.weekdays, other.weekends,
                        other.weekdays, other.weekdays, other.weekdays, other.weekdays, other.weekdays,
                        other.weekends, other.weekends, other.weekends,
                    ],
                )
            }
        )
    
    def __radd__(self, other:RuleSet) -> RuleSet:
        return self.__add__(other)
    
    def __sub__(self, other:RuleSet) -> RuleSet:
        
        if self.type != other.type:
            raise TypeError(
                f"Cannot substract {self.type}-type RuleSet to {other.type}-type RuleSet."
            )
            
        return self.__add__(other.__mul__(-1))
    
    def __and__(self, other:RuleSet) -> RuleSet:
        
        if (self.type is not ScheduleType.ONOFF) or (other.type is not ScheduleType.ONOFF):
            raise TypeError(
                f"Cannot 'AND' operate for non-ONOFF typed RuleSets (get: {self.type} and {other.type})."
            )
            
        return RuleSet(
            f"{self.name}:AND:{other.name}",
            **{
                k: RuleSet.__operate_dayschedule_with_default(
                    lambda a, b: a.__and__(b),
                    self_day    , other_day    ,
                    self_default, other_default,
                )
                for k, self_day, other_day, self_default, other_default
                in zip(
                    self.to_dict().keys(),
                    self.to_dict().values(), other.to_dict().values(),
                    [
                        self.weekdays, self.weekends,
                        self.weekdays, self.weekdays, self.weekdays, self.weekdays, self.weekdays,
                        self.weekends, self.weekends, self.weekends,
                    ],
                    [
                        other.weekdays, other.weekends,
                        other.weekdays, other.weekdays, other.weekdays, other.weekdays, other.weekdays,
                        other.weekends, other.weekends, other.weekends,
                    ],
                )
            }
        )
        
    def __or__(self, other:RuleSet) -> RuleSet:
        
        if (self.type is not ScheduleType.ONOFF) or (other.type is not ScheduleType.ONOFF):
            raise TypeError(
                f"Cannot 'AND' operate for non-ONOFF typed RuleSets (get: {self.type} and {other.type})."
            )
            
        return RuleSet(
            f"{self.name}:AND:{other.name}",
            **{
                k: RuleSet.__operate_dayschedule_with_default(
                    lambda a, b: a.__or__(b),
                    self_day    , other_day    ,
                    self_default, other_default,
                )
                for k, self_day, other_day, self_default, other_default
                in zip(
                    self.to_dict().keys(),
                    self.to_dict().values(), other.to_dict().values(),
                    [
                        self.weekdays, self.weekends,
                        self.weekdays, self.weekdays, self.weekdays, self.weekdays, self.weekdays,
                        self.weekends, self.weekends, self.weekends,
                    ],
                    [
                        other.weekdays, other.weekends,
                        other.weekdays, other.weekdays, other.weekdays, other.weekdays, other.weekdays,
                        other.weekends, other.weekends, other.weekends,
                    ],
                )
            }
        )
        
    def __invert__(self) -> RuleSet:
        
        if self.type is not ScheduleType.ONOFF:
            raise TypeError(
                f"Cannot 'invert' operate for non-ONOFF typed RuleSet (get: {self.type})."
            )
            
        return RuleSet(
            self.name,
            **{
                k: dayschedule.__invert__()
                for k,dayschedule in self.to_dict().items()
                if isinstance(dayschedule, DaySchedule)
            }
        )
        
    def element_min(self, other:RuleSet) -> RuleSet:
        
        return RuleSet(
            f"{self.name}:MIN:{other.name}",
            **{
                k: RuleSet.__operate_dayschedule_with_default(
                    lambda a, b: a.element_min(b),
                    self_day    , other_day    ,
                    self_default, other_default,
                )
                for k, self_day, other_day, self_default, other_default
                in zip(
                    self.to_dict().keys(),
                    self.to_dict().values(), other.to_dict().values(),
                    [
                        self.weekdays, self.weekends,
                        self.weekdays, self.weekdays, self.weekdays, self.weekdays, self.weekdays,
                        self.weekends, self.weekends, self.weekends,
                    ],
                    [
                        other.weekdays, other.weekends,
                        other.weekdays, other.weekdays, other.weekdays, other.weekdays, other.weekdays,
                        other.weekends, other.weekends, other.weekends,
                    ],
                )
            }
        )
        
    def element_max(self, other:RuleSet) -> RuleSet:
        
        return RuleSet(
            f"{self.name}:MAX:{other.name}",
            **{
                k: RuleSet.__operate_dayschedule_with_default(
                    lambda a, b: a.element_max(b),
                    self_day    , other_day    ,
                    self_default, other_default,
                )
                for k, self_day, other_day, self_default, other_default
                in zip(
                    self.to_dict().keys(),
                    self.to_dict().values(), other.to_dict().values(),
                    [
                        self.weekdays, self.weekends,
                        self.weekdays, self.weekdays, self.weekdays, self.weekdays, self.weekdays,
                        self.weekends, self.weekends, self.weekends,
                    ],
                    [
                        other.weekdays, other.weekends,
                        other.weekdays, other.weekdays, other.weekdays, other.weekdays, other.weekdays,
                        other.weekends, other.weekends, other.weekends,
                    ],
                )
            }
        )
    
    @property
    def min(self) -> int|float:
        return min([
            day_schedule.min
            for day_schedule in self.to_dict().values()
            if day_schedule is not None
        ])
    
    @property
    def max(self) -> int|float:
        return max([
            day_schedule.max
            for day_schedule in self.to_dict().values()
            if day_schedule is not None
        ])
        
    def normalize_by_max(self, *, new_name:str=None):
        
        if new_name is None:
            new_name = self.name + "_normalized"
        
        return RuleSet(
            new_name,
            self.weekdays.normalize_by_max() if self.weekdays is not None else None,
            self.weekends.normalize_by_max() if self.weekends is not None else None,
            monday    = self.monday   .normalize_by_max() if self.monday    is not None else None,
            tuesday   = self.tuesday  .normalize_by_max() if self.tuesday   is not None else None,
            wednesday = self.wednesday.normalize_by_max() if self.wednesday is not None else None,
            thursday  = self.thursday .normalize_by_max() if self.thursday  is not None else None,
            friday    = self.friday   .normalize_by_max() if self.friday    is not None else None,
            saturday  = self.saturday .normalize_by_max() if self.saturday  is not None else None,
            sunday    = self.sunday   .normalize_by_max() if self.sunday    is not None else None,
            holiday   = self.holiday  .normalize_by_max() if self.holiday   is not None else None,
        )
    
    """ representation
    """
    
    def to_dict(self) -> dict[str, DaySchedule]:
        return {
            "weekdays" : self.weekdays ,
            "weekends": self.weekends ,
            "monday"   : self.monday   ,
            "tuesday"  : self.tuesday  ,
            "wednesday": self.wednesday,
            "thursday" : self.thursday ,
            "friday"   : self.friday   ,
            "saturday" : self.saturday ,
            "sunday"   : self.sunday   ,
            "holiday"  : self.holiday  ,
        }
    
    def __str__(self) -> str:        
        return f"RuleSet {self.name}:"
    
    def __repr__(self) -> str:
        return f"<RuleSet {self.name} at {hex(id(self))}>"
    
    def to_idf_compactexpr(self) -> list[str]:
        result = []

        # 평일: override 여부 확인
        weekday_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        if any(getattr(self, k) for k in weekday_keys):
            for k in weekday_keys:
                day = getattr(self, k)
                if day:
                    result.append(f"For: {k.capitalize()}")
                    result += day.to_idf_compactexpr()
                else:
                    result.append(f"For: {k.capitalize()}")
                    result += self.weekdays.to_idf_compactexpr()
        else:
            result.append("For: Weekdays")
            result += self.weekdays.to_idf_compactexpr()

        # 주말: override 여부 확인
        weekend_keys = ["saturday", "sunday"]
        if any(getattr(self, k) for k in weekend_keys):
            for k in weekend_keys:
                day = getattr(self, k)
                if day:
                    result.append(f"For: {k.capitalize()}")
                    result += day.to_idf_compactexpr()
                else:
                    result.append(f"For: {k.capitalize()}")
                    result += self.weekends.to_idf_compactexpr()
        else:
            result.append("For: Weekends")
            result += self.weekends.to_idf_compactexpr()

        # 휴일
        if self.holiday:
            result.append("For: Holiday")
            result += self.holiday.to_idf_compactexpr()

        # fallback (AllOtherDays → weekends 스케줄 사용)
        result.append("For: AllOtherDays")
        result += self.weekends.to_idf_compactexpr()
        
        return result
    
class Schedule(UserList):
    
    FIXED_LENGTH = 365
    TIME_TUPLE   = [datetime.date(Setting.DEFAULT_YEAR,1,1)+datetime.timedelta(days=days) for days in range(365)]
    
    def __init__(self,
        name   :str,
        rulesets:list[RuleSet]|None=None,
        ) -> None:
        
        if name is None:
            name = hex(id(self))
        self.name = name
        
        if rulesets is None:
            rulesets = [RuleSet("anonymous")] * Schedule.FIXED_LENGTH
        
        if len(rulesets) != Schedule.FIXED_LENGTH:
            raise ValueError(
                f""
            )
        
        if any(not isinstance(item, RuleSet) for item in rulesets):
            raise TypeError(
                f""
            )
        
        if any(ruleset.type != rulesets[0].type for ruleset in rulesets):
            raise ValueError(
                f""
            )
        
        self.__type = rulesets[0].type
        self.data = rulesets
    
    def apply(self,
        ruleset:RuleSet,
        *,
        start:datetime.date|str,
        end  :datetime.date|str,
        inplace:bool=True
        ) -> None:
        
        def datetime_parser(datestr:str) -> datetime.date:
            
            if re.match(r"\d{8}$", datestr):
                datetuple = (int(datestr[:4]), int(datestr[4:6]), int(datestr[6:8]))
            elif re.match(r"\d{4}$", datestr):
                datetuple = (Setting.DEFAULT_YEAR, int(datestr[:2]), int(datestr[2:4]))
            else:
                datetuple = tuple(map(lambda v: int(v), re.findall(r"\d+", datestr)))
                if len(datetuple) == 2:
                    datetuple = (Setting.DEFAULT_YEAR, *datetuple)
            
            date = datetime.date(*datetuple)
            return date
        
        if isinstance(start, str):
            start = datetime_parser(start)

        if isinstance(end, str):
            end = datetime_parser(end)
        
        if inplace:
            target = self
        else:
            target = deepcopy(self)
            
        for idx in range(Schedule.FIXED_LENGTH):
            if start <= Schedule.TIME_TUPLE[idx] <= end:
                target.data[idx] = ruleset
                
        if not inplace:
            return target
    
    """ algebraric operation
    """
    
    def __mul__(self, value:int|float) -> Schedule:
        return Schedule.from_compact(
            f"{self.name}:MUL:{value:.6f}",
            [
                (start_date, end_date, ruleset.__mul__(value))
                for start_date, end_date, ruleset in self.compactize()
            ]
        )
        
    def __rmul__(self, value:int|float) -> Schedule:
        return self.__mul__(value)
    
    def __truediv__(self, value:int|float) -> Schedule:
        return Schedule.from_compact(
            f"{self.name}:TRUEDIV:{value:.6f}",
            [
                (start_date, end_date, ruleset.__truediv__(value))
                for start_date, end_date, ruleset in self.compactize()
            ]
        )
        
    def __add__(self, other:Schedule) -> RuleSet:
        
        if self.type != other.type:
            raise TypeError(
                f"Cannot add {self.type}-type Schedule to {other.type}-type Schedule."
            )
            
        unified_compactized_self, unified_compactized_other = Schedule.unify_compactized_schedules(
            self.compactize(), other.compactize(),
        )
        
        return Schedule.from_compact(
            f"{self.name}:ADD:{other.name}",
            [
                (start_date, end_date, ruleset_self.__add__(ruleset_other))
                for (start_date, end_date, ruleset_self), (start_date, end_date, ruleset_other) in zip(unified_compactized_self, unified_compactized_other)
            ]
        )
    
    def __radd__(self, other:Schedule) -> Schedule:
        return self.__add__(other)
    
    def __sub__(self, other:Schedule) -> Schedule:
        
        if self.type != other.type:
            raise TypeError(
                f"Cannot sub {self.type}-type Schedule to {other.type}-type Schedule."
            )
            
        unified_compactized_self, unified_compactized_other = Schedule.unify_compactized_schedules(
            self.compactize(), other.compactize(),
        )
        
        return Schedule.from_compact(
            f"{self.name}:SUB:{other.name}",
            [
                (start_date, end_date, ruleset_self.__sub__(ruleset_other))
                for (start_date, end_date, ruleset_self), (start_date, end_date, ruleset_other) in zip(unified_compactized_self, unified_compactized_other)
            ]
        )
        
    def __and__(self, other:Schedule) -> Schedule:
        
        if (self.type is not ScheduleType.ONOFF) or (other.type is not ScheduleType.ONOFF):
            raise TypeError(
                f"Cannot 'AND' operate for non-ONOFF typed Schedules (get: {self.type} and {other.type})."
            )
            
        unified_compactized_self, unified_compactized_other = Schedule.unify_compactized_schedules(
            self.compactize(), other.compactize(),
        )

        return Schedule.from_compact(
            f"{self.name}:AND:{other.name}",
            [
                (start_date, end_date, ruleset_self.__and__(ruleset_other))
                for (start_date, end_date, ruleset_self), (start_date, end_date, ruleset_other) in zip(unified_compactized_self, unified_compactized_other)
            ]
        )
    
    def __or__(self, other:Schedule) -> Schedule:
        
        if (self.type is not ScheduleType.ONOFF) or (other.type is not ScheduleType.ONOFF):
            raise TypeError(
                f"Cannot 'OR' operate for non-ONOFF typed Schedules (get: {self.type} and {other.type})."
            )
            
        unified_compactized_self, unified_compactized_other = Schedule.unify_compactized_schedules(
            self.compactize(), other.compactize(),
        )

        return Schedule.from_compact(
            f"{self.name}:OR:{other.name}",
            [
                (start_date, end_date, ruleset_self.__or__(ruleset_other))
                for (start_date, end_date, ruleset_self), (start_date, end_date, ruleset_other) in zip(unified_compactized_self, unified_compactized_other)
            ]
        )
        
    def __invert__(self) -> Schedule:
        
        if self.type is not ScheduleType.ONOFF:
            raise TypeError(
                f"Cannot 'invert' operate for non-ONOFF typed Schedule (get: {self.type})."
            )
            
        return Schedule.from_compact(
            f"{self.name}:INVERTED",
            [
                (start_date, end_date, ruleset.__invert__())
                for start_date, end_date, ruleset in self.compactize()
            ]
        )
        
    def element_min(self, other:Schedule) -> Schedule:
        
        unified_compactized_self, unified_compactized_other = Schedule.unify_compactized_schedules(
            self.compactize(), other.compactize(),
        )

        return Schedule.from_compact(
            f"{self.name}:MIN:{other.name}",
            [
                (start_date, end_date, ruleset_self.element_min(ruleset_other))
                for (start_date, end_date, ruleset_self), (start_date, end_date, ruleset_other) in zip(unified_compactized_self, unified_compactized_other)
            ]
        )
    
    def element_max(self, other:Schedule) -> Schedule:
        
        unified_compactized_self, unified_compactized_other = Schedule.unify_compactized_schedules(
            self.compactize(), other.compactize(),
        )

        return Schedule.from_compact(
            f"{self.name}:MAX:{other.name}",
            [
                (start_date, end_date, ruleset_self.element_max(ruleset_other))
                for (start_date, end_date, ruleset_self), (start_date, end_date, ruleset_other) in zip(unified_compactized_self, unified_compactized_other)
            ]
        )
    
    @property
    def min(self) -> int|float:
        return min([ruleset.min for ruleset in self.data])
    
    @property
    def max(self) -> int|float:
        return max([ruleset.max for ruleset in self.data])
    
    def normalize_by_max(self, *, new_name:str=None):
        
        if new_name is None:
            new_name = self.name + "_normalized"
        
        return Schedule.from_compact(
            new_name                       ,
            [
                (start_date, end_date, ruleset.normalize_by_max())
                for start_date, end_date, ruleset in self.compactize()
            ]
        )
    
    """ prohibited methods
    """
    
    def __delitem__(self, index:int) -> None:
        raise AttributeError(
            f"Cannot delete item from the fixed-length ({self.fixed_length}) Schedule"
        )
        
    def append(self, item:Any) -> None:
        raise AttributeError(
            f"Cannot append to the fixed-length ({self.fixed_length}) Schedule"
        )

    def extend(self, items: list) -> None:
        raise AttributeError(
            f"Cannot extend the fixed-length ({self.fixed_length}) Schedule"
        )
        
    def pop(self, index:int= -1) -> None:
        raise AttributeError(
            f"Cannot pop from the fixed-length ({self.fixed_length}) Schedule"
        )
        
    def clear(self) -> None:
        raise AttributeError(
            f"Cannot clear the fixed-length ({self.fixed_length}) Schedule"
        )
        
    def insert(self, index:int, item:Any) -> None:
        raise AttributeError(
            f"Cannot insert to the fixed-length ({self.fixed_length}) Schedule"
        )
    
    
    @property
    def type(self) -> ScheduleType:
        return self.__type
    
    """ time-related operations
    """
    
    def compactize(self) -> list[tuple[datetime.date, datetime.date, RuleSet]]:
        
        compact_tuples = []
        for time, ruleset in zip(Schedule.TIME_TUPLE, self.data):
            
            if (len(compact_tuples) == 0) or (compact_tuples[-1][2] != ruleset):
                compact_tuples.append((time, time, ruleset))
            else:
                compact_tuples[-1] = (compact_tuples[-1][0], time, compact_tuples[-1][2])
        
        return compact_tuples
    
    @classmethod
    def from_compact(cls,
        name    :str,
        rulesets:list[tuple[datetime.date, datetime.date, RuleSet]],
        ) -> Schedule:
        
        # type check
        given_types = [ruleset.type for _, _, ruleset in rulesets]
        if len(set(given_types)) > 1:
            raise ValueError(
                f"Cannot create a schedule with rulesets of different types"
            )
        
        # create a default schedule with given type
        schedule = cls(name)
        schedule._Schedule__type = rulesets[0][2].type
        
        # apply rulesets for certain datetimes
        for start, end, ruleset in rulesets:
            schedule.apply(ruleset, start=start, end=end)
        
        return schedule
    
    @staticmethod
    def unify_compactized_schedules(
        compactized1:list[tuple[datetime.date, datetime.date, RuleSet]],
        compactized2:list[tuple[datetime.date, datetime.date, RuleSet]],
        ) -> tuple[
            list[tuple[datetime.date, datetime.date, RuleSet]],
            list[tuple[datetime.date, datetime.date, RuleSet]],
        ]:
            
        boundaries = set()
        for start_date, end_date, _ in compactized1 + compactized2:
            boundaries.add(start_date)
            boundaries.add(end_date + datetime.timedelta(days=1))
        boundaries = sorted(boundaries)
        
        def find_ruleset(compact_list, d):
            for s, e, rs in compact_list:
                if s <= d <= e:
                    return rs
        
        new_list1, new_list2 = [], []
        for i in range(len(boundaries) - 1):
            seg_start = boundaries[i]
            seg_end_excl = boundaries[i + 1]
            seg_end_incl = seg_end_excl - datetime.timedelta(days=1)

            r1 = find_ruleset(compactized1, seg_start)
            r2 = find_ruleset(compactized2, seg_start)

            new_list1.append((seg_start, seg_end_incl, r1))
            new_list2.append((seg_start, seg_end_incl, r2))
        
        return new_list1, new_list2
    
    def to_idf_object(self) -> IdfObject:
        
        return IdfObject("Schedule:Compact",[
            f"{self.name}",
            "",
            *sum([
                [
                    f"Through: {end_date.month}/{end_date.day}",
                    *ruleset.to_idf_compactexpr()
                ]
                for start_date, end_date, ruleset in self.compactize()  
            ],start=[])
        ])

    """ representation
    """
    
    def __str__(self) -> str:        
        return f"Schedule {self.name}:\n" + "\n".join([
            f"\t{start.month:02d}/{start.day:02d} ~ {end.month:02d}/{end.day:02d}:{ruleset.name}"
            for start, end, ruleset in self.compactize()
        ])
    
    def __repr__(self) -> str:
        return f"<Schedule {self.name} at {hex(id(self))}>"
    
class Profile:
    
    def __init__(self,
        name:str,
        heating_setpoint :Schedule|None=None,
        cooling_setpoint :Schedule|None=None,
        hvac_availability:Schedule|None=None,
        occupant         :Schedule|None=None, # W/m2
        lighting         :Schedule|None=None, # W/m2
        equipment        :Schedule|None=None, # W/m2
        ) -> None:
        
        self.name = name
        self.heating_setpoint  = heating_setpoint
        self.cooling_setpoint  = cooling_setpoint
        self.hvac_availability = hvac_availability
        self.occupant          =occupant
        self.lighting          =lighting
        self.equipment         =equipment    
    
    def to_idf_object(self) -> list[IdfObject]:
        
        return [
            schedule.to_idf_object()
            for schedule in [
                self.heating_setpoint,
                self.cooling_setpoint,
                self.hvac_availability,
                self.occupant,
                self.lighting,
                self.equipment,
            ]
            if isinstance(schedule, Schedule)
        ]