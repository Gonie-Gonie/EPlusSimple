
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import re
import math
import random
from typing      import Literal
from dataclasses import dataclass
from abc import (
    ABC           ,
    abstractmethod,
)

# third-party modules
import pandas as pd

# local modules
from pyGRsim import GreenRetrofitModel
from idragon import (
    dragon     ,
    IDF        ,
)

# settings
random.seed(hash("REB-PHIKO-SNU"))

# ---------------------------------------------------------------------------- #
#                                 SUBFUNCTIONS                                 #
# ---------------------------------------------------------------------------- #

def parse_duration_hours(operation_str:str) -> tuple[int,int,int,int]:
    
    pattern = re.compile(r"(?P<starth>\d{2}):(?P<startm>\d{2}) ?(-|~) ?(?P<endh>\d{2}):(?P<endm>\d{2})")
    matched = re.search(pattern, operation_str)
    
    return int(matched.group("starth")), int(matched.group("startm")), int(matched.group("endh")), int(matched.group("endm"))

def parse_duration_month(operation_str:str) -> tuple[list[int, int], list[int,int]|None]:
    
    pattern = re.compile(r"(?P<startm>\d{1,2})월 ?(-|~) ?(?P<endm>\d{1,2})월")
    matched = re.search(pattern, operation_str)
    
    startm1 = int(matched.group("startm"))
    endm1   = int(matched.group("endm"))

    if endm1 >= startm1:
        return [startm1, endm1], None
    
    else:
        return [1, endm1], [startm1, 12]
    
def translate_dayofweek(korean_dow:str) -> str:
    
    dow_dict = {
        "월": "monday"   ,
        "화": "tuesday"  ,
        "수": "wednesday",
        "목": "thursday" ,
        "금": "friday"   ,
    }
    
    return dow_dict[korean_dow]

def get_end_of_the_month(mth:int) -> int:
    
    endofthemonth_dict = {
        1:31, 2:28, 3:31,  4:30,  5:31,  6:30,
        7:31, 8:31, 9:30, 10:31, 11:30, 12:31,
    }
    
    return endofthemonth_dict[mth]

def make_집중진료_dayschedule_values(starth, startm, endh, endm,
                  x1, t1, x2, t2,
                  mode="random") -> list[int]:
    
    slots = [0] * 144  # 하루 전체

    # 운영시간을 슬롯 인덱스로 변환
    start_idx = (starth * 60 + startm) // 10
    end_idx   = (endh   * 60 + endm) // 10
    if end_idx > 144: end_idx = 144

    # 오전/오후 범위
    am_start, am_end = 0, 72
    pm_start, pm_end = 72, 144

    def assign_people(n, stay_min, seg_start, seg_end):
        stay_slots = math.ceil(stay_min / 10)
        # 운영시간과 교집합으로 제한
        seg_start = max(seg_start, start_idx)
        seg_end   = min(seg_end, end_idx)
        available = seg_end - seg_start
        if n == 0 or stay_slots <= 0 or available <= 0:
            return [], 0
        if mode == "random":
            start_points = sorted(random.sample(
                range(seg_start, seg_end - stay_slots + 1), n
            ))
        else:  # 균등 배치
            interval = (available - stay_slots) // (n - 1) if n > 1 else 0
            start_points = [seg_start + i * interval for i in range(n)]
        return start_points, stay_slots

    # 오전 배정
    am_points, am_stay = assign_people(x1, t1, am_start, am_end)
    for s in am_points:
        for i in range(am_stay):
            slots[s+i] += 1

    # 오후 배정
    pm_points, pm_stay = assign_people(x2, t2, pm_start, pm_end)
    for s in pm_points:
        for i in range(pm_stay):
            slots[s+i] += 1

    return slots

# ---------------------------------------------------------------------------- #
#                                 SURVEY ITEMS                                 #
# ---------------------------------------------------------------------------- #

@dataclass
class MetaData:
    userId    : str 
    userName  : str
    name      : str
    department: str
    updatedAt : str
    version   : str
    건물명       :str 
    GR준공일     :str 
    조사일       :str 
    응답자근무기간:str 
    
    @classmethod
    def from_row(cls, row:pd.Series):
        
        return cls(
            row["userId"], row["userName"], row["name"], row["department"], row["updatedAt"], row["version"],
            row["A1"],row["A2"],row["A3"],row["A4"],
        )    

@dataclass
class 설비운영:
    이름:str
    사용시간:str
    사용기간:str
    설정온도:int|str
    사용여부:str
    
    @property
    def is_valid(self) -> bool:
        return self.사용여부 == "사용"
    
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        # all-off schedule
        alloff_schedule = dragon.Schedule.from_compact(
            None,
            [("0101","1231", dragon.RuleSet(
                None,
                dragon.DaySchedule.from_compact(None,[(24,0,0)], dragon.ScheduleType.ONOFF),
                dragon.DaySchedule.from_compact(None,[(24,0,0)], dragon.ScheduleType.ONOFF),
            ))]
        )
        
        # 시간
        starth, startm, endh, endm = parse_duration_hours(self.사용시간)
        availability_dayschedule = dragon.DaySchedule.from_compact(
            None,
            [
                (starth, startm, 0),
                (endh  , endm  , 1),
                (24    , 0     , 0),
            ],
            dragon.ScheduleType.ONOFF         
        )
        availability_ruleset = dragon.RuleSet(
            None,
            availability_dayschedule,
            availability_dayschedule,
        )
        
        # 기간
        duration1, duration2 = parse_duration_month(self.사용기간) 
        availability_schedule = alloff_schedule.apply(
            availability_ruleset,
            start = f"{duration1[0]:02d}01",
            end   = f"{duration1[1]:02d}{get_end_of_the_month(duration1[1]):02d}",
            inplace=False
        )
        if duration2 is not None:
            availability_schedule.apply(
                availability_ruleset,
                start = f"{duration2[0]:02d}01",
                end   = f"{duration2[1]:02d}{get_end_of_the_month(duration2[1]):02d}",
                inplace=True
        )   
        
        return availability_schedule

    def get_setpoint_shcedule(self,
        original_schedule:dragon.Schedule             ,
        mode             :Literal["heating","cooling"],
        ) -> dragon.Schedule:
        
        # uncontrolled temperature
        match mode:
            case "heating": default_temperature = -30
            case "cooling": default_temperature =  50
        
         # 시간
        starth, startm, endh, endm = parse_duration_hours(self.사용시간)
        temperature_dayschedule = dragon.DaySchedule.from_compact(
            None,
            [
                (starth, startm, default_temperature),
                (endh  , endm  , self.설정온도       ),
                (24    , 0     , default_temperature),
            ],
            dragon.ScheduleType.TEMPERATURE         
        )
        temperature_ruleset = dragon.RuleSet(
            None,
            temperature_dayschedule,
            temperature_dayschedule,
        )
        
        # 기간
        duration1, duration2 = parse_duration_month(self.사용기간) 
        temperature_schedule = original_schedule.apply(
            temperature_ruleset,
            start = f"{duration1[0]:02d}01",
            end   = f"{duration1[1]:02d}{get_end_of_the_month(duration1[1]):02d}",
            inplace=False
        )
        if duration2 is not None:
            temperature_schedule.apply(
                temperature_ruleset,
                start = f"{duration2[0]:02d}01",
                end   = f"{duration2[1]:02d}{get_end_of_the_month(duration2[1]):02d}",
                inplace=True
            )  
        
        return temperature_schedule
    
@dataclass
class 보건소일반존:
    # zone
    운영시간:str
    직원   :str
    외근횟수:int
    외근시간:str
    외근직원:int
    집중진료요일:str
    집중진료시간:str
    집중진료오전방문객:str
    집중진료오후방문객:str
    집중진료오전체류시간:int
    집중진료오후체류시간:int
    # hvac
    난방설비1:설비운영
    난방설비2:설비운영
    냉방설비1:설비운영
    냉방설비2:설비운영
    
    @classmethod
    def from_row(cls, row:pd.Series, is_priorGR:bool):
        
        if is_priorGR:
            return cls(
                row["B1"], row["B2"], row["B3"], row["B4"], row["B5"],
                row["B6"], row["B7"], row["B8"], row["B9"], row["B10"], row["B11"],
                설비운영(row["B55"],row["B56"],row["B58"],row["B59"],row["BA1"]),
                설비운영(row["B60"],row["B61"],row["B63"],row["B64"],row["BA2"]),
                설비운영(row["B65"],row["B66"],row["B68"],row["B69"],row["BA3"]),
                설비운영(row["B70"],row["B71"],row["B73"],row["B74"],row["BA4"]),
            )
        else:
            return cls(
                row["B1"], row["B2"], row["B3"], row["B4"], row["B5"],
                row["B6"], row["B7"], row["B8"], row["B9"], row["B10"], row["B11"],
                설비운영(row["B51"],row["B52"],row["B54"],row["B55"],row["BA1"]),
                설비운영(row["B56"],row["B57"],row["B59"],row["B60"],row["BA2"]),
                설비운영(row["B61"],row["B61"],row["B64"],row["B65"],row["BA3"]),
                설비운영(row["B66"],row["B67"],row["B69"],row["B70"],row["BA4"]),
            )
            
    def get_occupant_schedule(self) -> dragon.Schedule:
        
        # 기본 운영시간
        starth, startm, endh, endm = parse_duration_hours(self.운영시간)
        기본운영_직원_ruleset = dragon.RuleSet(
            None,
            dragon.DaySchedule.from_compact(
                None,
                [
                    (starth, startm,        0),
                    (endh  , endm  , self.직원),
                    (24    , 0     ,        0),
                ],
                dragon.ScheduleType.REAL,
            ),
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,)
        )
        
        # 집중진료
        # 요일 parsing
        집중진료_dayofweeks = [translate_dayofweek(s.strip()) for s in self.집중진료요일.split(",")]
        # 시간 정하기 (random 배정)
        starth, startm, endh, endm = parse_duration_hours(self.집중진료시간)
        schedule_values = make_집중진료_dayschedule_values(
            starth, startm, endh, endm,
            self.집중진료오전방문객, self.집중진료오전체류시간, self.집중진료오후방문객, self.집중진료오후체류시간
        )
        # ruleset 만들기
        집중진료_방문객_ruleset = dragon.RuleSet(
            None,
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
            **{
                k: dragon.DaySchedule(None, schedule_values, type=dragon.ScheduleType.REAL)
                for k in 집중진료_dayofweeks
            }
        )
        
        # 외근
        # 요일 정하기
        non_집중진료_dayofweeks = {"monday","tuesday","wednesday","thursday","friday"} - set(집중진료_dayofweeks)
        if len(non_집중진료_dayofweeks) >= self.외근횟수:
            외근_dayofweeks = random.sample(sorted(non_집중진료_dayofweeks), self.외근횟수)
        else:
            외근_dayofweeks = list(non_집중진료_dayofweeks) + random.sample(sorted(집중진료_dayofweeks), self.외근횟수-len(non_집중진료_dayofweeks))

        # 시간 정하기
        starth, startm, endh, endm = parse_duration_hours(self.외근시간)
        # ruleset 만들기
        외근_직원_ruleset = dragon.RuleSet(
            None,
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
            **{
                k: dragon.DaySchedule.from_compact(
                    None,
                    [
                        (starth, startm,           0),
                        (endh  , endm  , self.외근직원),
                        (24    , 0     ,           0),
                    ],
                    dragon.ScheduleType.REAL,
                )
                for k in 외근_dayofweeks
            }
        )
        
        final_occupant_ruleset = 기본운영_직원_ruleset + 집중진료_방문객_ruleset - 외근_직원_ruleset
        occupant_schedule = dragon.Schedule(
            None,
            [final_occupant_ruleset] * 365
        )
        
        return occupant_schedule
    
    def get_heating_setpoint_schedule(self, original_schedule:dragon.Schedule) -> dragon.Schedule:
        
        # 난방설비 1
        first_equipment_setpoint = self.난방설비1.get_hvac_availability_schedule(original_schedule, "heating")
        
        # 난방설비 2
        if self.난방설비2.is_valid:
            second_equipment_setpoint = self.난방설비2.get_hvac_availability_schedule(original_schedule, "heating")
            
            # 둘 다 고려 (최댓값으로)
            final_schedule = first_equipment_setpoint.element_max(second_equipment_setpoint)
            
        else:
            final_schedule = first_equipment_setpoint
        
        return final_schedule
    
    def get_cooling_setpoint_schedule(self, original_schedule:dragon.Schedule) -> dragon.Schedule:
        
        # 냉방설비 1
        first_equipment_setpoint = self.냉방설비1.get_hvac_availability_schedule(original_schedule, "cooling")
        
        # 냉방설비 2
        if self.난방설비2.is_valid:
            second_equipment_setpoint = self.냉방설비2.get_hvac_availability_schedule(original_schedule, "cooling")
            
            # 둘 다 고려 (최솟값으로)
            final_schedule = first_equipment_setpoint.element_min(second_equipment_setpoint)
            
        else:
            final_schedule = first_equipment_setpoint
        
        return final_schedule
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        # 기본 운영시간
        starth, startm, endh, endm = parse_duration_hours(self.운영시간)
        기본운영_ruleset = dragon.RuleSet(
            None,
            dragon.DaySchedule.from_compact(
                None,
                [
                    (starth, startm, 0),
                    (endh  , endm  , 1),
                    (24    , 0     , 0),
                ],
                dragon.ScheduleType.ONOFF,
            ),
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.ONOFF,)
        )
        기본운영_schedule = dragon.Schedule.from_compact(
            None,
            [("0101","1231", 기본운영_ruleset)]
        )
        
        # 설비 가동스케줄 (개별)
        operation_schedules = []
        for 설비 in [self.난방설비1, self.난방설비2, self.냉방설비1, self.냉방설비2]:
            if 설비.is_valid:
                operation_schedules.append(설비.get_hvac_availability_schedule())
        
        # 설비 가동스케줄 (or조건으로 개별 설비 결합)
        hvac_availability = operation_schedules[0]
        for schedule in operation_schedules[2:]:
            hvac_availability |= schedule
        
        # 최종 스케줄 = 운영중이면서, 설비 가동 중
        hvac_availability &= 기본운영_schedule
        
        return hvac_availability
    

    def apply_to(self, zones:list[dragon.Zone]) -> None:
        
        total_area = max(sum(zone.floor_area for zone in zones), 1E-6)
        occupant_schedule          = self.get_occupant_schedule()/total_area 
        hvac_availability_schedule = self.get_hvac_availability_schedule()
        
        for zone in zones:
            zone.profile = dragon.Profile(
                f"{zone.name}_일반존체크리스트",
                self.get_heating_setpoint_schedule(zone.profile.heating_setpoint), 
                self.get_cooling_setpoint_schedule(zone.profile.cooling_setpoint) , 
                hvac_availability_schedule,
                occupant_schedule         ,
                zone.profile.lighting     ,
                zone.profile.equipment    ,
            )
            
        pass
    
@dataclass
class 보건소특화존1:
    # zone
    사용요일:str
    오전운영시간:str
    오후운영시간:str
    오전재실인원:int
    오후재실인원:int
    # hvac
    난방설비1:설비운영
    난방설비2:설비운영
    냉방설비1:설비운영
    냉방설비2:설비운영
    
    @classmethod
    def from_row(cls, row:pd.Series, is_prior_GR:bool):
        
        if is_prior_GR:
            return cls(
                row["B84"],row["B85"],row["B86"],row["B87"],row["B88"],
                설비운영(row["B89"],row["B90"],row["B92"],row["B93"],row["BA6"]),
                설비운영(row["B94"],row["B95"],row["B97"],row["B98"],row["BA7"]),
                설비운영(row["B99"],row["B100"],row["B102"],row["B103"],row["BA8"]),
                설비운영(row["B104"],row["B105"],row["B107"],row["B108"],row["BA9"]),
            )
        else:
            return cls(
                row["B80"],row["B81"],row["B82"],row["B83"],row["B84"],
                설비운영(row["B85"],row["B86"],row["B88"],row["B89"],row["BA6"]),
                설비운영(row["B90"],row["B91"],row["B93"],row["B94"],row["BA7"]),
                설비운영(row["B95"],row["B96"],row["B98"],row["B99"],row["BA8"]),
                설비운영(row["B100"],row["B101"],row["B103"],row["B104"],row["BA9"]),
            )

    def get_occupant_schedule(self) -> dragon.Schedule:
        
        
        
        return
    
    def get_heating_setpoint_schedule(self) -> dragon.Schedule:
        
        return
    
    def get_cooling_setpoint_schedule(self) -> dragon.Schedule:
        
        return
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        return

    def apply_to(self, zones:list[dragon.Zone]) -> None:
        
        total_area = sum(zone.floor_area for zone in zones)
        
        for zone in zones:
            zone.profile = dragon.Profile(
                f"{zone.name}_특화존1체크리스트",
                zone.profile.heating_setpoint, 
                zone.profile.cooling_setpoint, 
                zone.profile.hvac_availability,
                zone.profile.occupant,
                zone.profile.lighting,
                zone.profile.equipment,
            )
            
        pass
    
@dataclass
class 보건소특화존2:
    #zone
    관사여부:str
    관사수  :int
    사용관사수:str
    평일사용일수:int
    주말사용일수:int
    동거인여부:str
    동거인수:int
    # hvac
    난방설비1:설비운영
    난방설비2:설비운영
    냉방설비1:설비운영
    냉방설비2:설비운영
    
    @classmethod
    def from_row(cls, row:pd.Series, is_prior_GR:bool):
        
        if is_prior_GR:
            return cls(
                row["B118"],row["B119"],row["B120"],row["B121"],row["B122"],row["B123"],row["B124"],
                설비운영(row["B125"],row["B126"],row["B128"],row["B129"],row["BA11"]),
                설비운영(row["B130"],row["B131"],row["B133"],row["B134"],row["BA12"]),
                설비운영(row["B135"],row["B136"],row["B138"],row["B139"],row["BA13"]),
                설비운영(row["B140"],row["B141"],row["B143"],row["B144"],row["BA14"]),
            )
        else:
            return cls(
                row["B114"],row["B115"],row["B116"],row["B117"],row["B118"],row["B119"],row["B120"],
                설비운영(row["B121"],row["B122"],row["B124"],row["B125"],row["BA11"]),
                설비운영(row["B126"],row["B127"],row["B129"],row["B130"],row["BA12"]),
                설비운영(row["B131"],row["B132"],row["B134"],row["B135"],row["BA13"]),
                설비운영(row["B136"],row["B137"],row["B139"],row["B140"],row["BA14"]),
            )

    def get_occupant_schedule(self) -> dragon.Schedule:
        
        
        
        return
    
    def get_heating_setpoint_schedule(self) -> dragon.Schedule:
        
        return
    
    def get_cooling_setpoint_schedule(self) -> dragon.Schedule:
        
        return
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        return

    def apply_to(self, zones:list[dragon.Zone]) -> None:
        
        total_area = sum(zone.floor_area for zone in zones)
        
        for zone in zones:
            zone.profile = dragon.Profile(
                f"{zone.name}_특화존2체크리스트",
                zone.profile.heating_setpoint, 
                zone.profile.cooling_setpoint, 
                zone.profile.hvac_availability,
                zone.profile.occupant,
                zone.profile.lighting,
                zone.profile.equipment,
            )
            
        pass
# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #

class 현장조사체크리스트(ABC):
    
    def __init__(self,
        raw_input:pd.Series,
        metadata :MetaData,
        ) -> None:
        
        self.raw  = raw_input
        self.meta = metadata
    
    """ input
    """
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 현장조사체크리스트: ...
    
    @classmethod
    def from_dataframe(cls, df:pd.DataFrame) -> list[현장조사체크리스트]:
        return [cls.from_row(row) for _, row in df.iterrows()]
    
    """ output
    """
    
    @abstractmethod
    def apply_to(self, grm:GreenRetrofitModel) -> IDF: ...
        
        
class 어린이집GR이전체크리스트(현장조사체크리스트):
    
    def __init__(self,
        raw_input:pd.Series,
        metadata :MetaData,
        ) -> None:
        
        # common
        super().__init__(raw_input, metadata)
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        return cls(
            row,
            MetaData.from_row(row),
        )
        
    def apply_to(self, grm:GreenRetrofitModel, exceldata:dict[str,pd.DataFrame]) -> IDF:
        
        return IDF()


class 어린이집GR이후체크리스트(현장조사체크리스트):
    
    def __init__(self,
        raw_input:pd.Series,
        metadata :MetaData,
        ) -> None:
        
        # common
        super().__init__(raw_input, metadata)
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        return cls(
            row,
            MetaData.from_row(row),
        )
        
    def apply_to(self, grm:GreenRetrofitModel, exceldata:dict[str,pd.DataFrame]) -> IDF:
        
        return IDF()
    
    
class 보건소GR이전체크리스트(현장조사체크리스트):
    
    def __init__(self,
        raw_input:pd.Series,
        metadata :MetaData,
        일반존 : 보건소일반존 ,
        특화존1: 보건소특화존1,
        특화존2: 보건소특화존2,
        ) -> None:
        
        # common
        super().__init__(raw_input, metadata)
        
        # zone survey
        self.일반존  = 일반존
        self.특화존1 = 특화존1
        self.특화존2 = 특화존2
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        return cls(
            row,
            MetaData.from_row(row),
            보건소일반존.from_row(row, True),
            보건소특화존1.from_row(row, True),
            보건소특화존2.from_row(row, True),
        )
    
    def apply_to(self, grm:GreenRetrofitModel, exceldata:dict[str,pd.DataFrame]) -> IDF:
        
        zoneID_category = {
            category: [
                zone.ID for zone in grm.zone
                if zone.name in list(exceldata["실"].query("현장조사프로필 == @category" )["이름"].values)
            ]
            for category in ["일반존","특화존1","특화존2"]
        }
        
        em = grm.to_dragon()
        
        self.일반존.apply_to([
                zone for zone in em.zone
                if zone.name in zoneID_category["일반존"]
        ])
        self.특화존1.apply_to([
                zone for zone in em.zone
                if zone.name in zoneID_category["특화존1"]
        ])
        self.특화존2.apply_to([
                zone for zone in em.zone
                if zone.name in zoneID_category["특화존2"]
        ])
        
        return em.to_idf()
    
    
class 보건소GR이후체크리스트(현장조사체크리스트):

    def __init__(self,
        raw_input:pd.Series,
        metadata :MetaData,
        일반존 : 보건소일반존 ,
        특화존1: 보건소특화존1,
        특화존2: 보건소특화존2,
        ) -> None:
        
        # common
        super().__init__(raw_input, metadata)
        
        # zone survey
        self.일반존  = 일반존
        self.특화존1 = 특화존1
        self.특화존2 = 특화존2
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        return cls(
            row,
            MetaData.from_row(row),
            보건소일반존.from_row(row, False),
            보건소특화존1.from_row(row, False),
            보건소특화존2.from_row(row, False),
        )
        
    def apply_to(self, grm:GreenRetrofitModel, exceldata:dict[str,pd.DataFrame]) -> IDF:
        
        zoneID_category = {
            category: [
                zone.ID for zone in grm.zone
                if zone.name in list(exceldata["실"].query("현장조사프로필 == @category" )["이름"].values)
            ]
            for category in ["일반존","특화존1","특화존2"]
        }
        
        em = grm.to_dragon()
        
        self.일반존.apply_to([
                zone for zone in em.zone
                if zone.name in zoneID_category["일반존"]
        ])
        self.특화존1.apply_to([
                zone for zone in em.zone
                if zone.name in zoneID_category["특화존1"]
        ])
        self.특화존2.apply_to([
                zone for zone in em.zone
                if zone.name in zoneID_category["특화존2"]
        ])
        
        return em.to_idf()
    
    
class 의료시설GR이전체크리스트(현장조사체크리스트): ...

class 의료시설GR이후체크리스트(현장조사체크리스트): ...

