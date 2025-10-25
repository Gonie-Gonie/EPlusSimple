
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
from epsimple import GreenRetrofitModel
from idragon import (
    dragon     ,
    IDF        ,
)

# settings
random.seed(hash("REB-PHIKO-SNU"))


# ---------------------------------------------------------------------------- #
#                          SUBFUNCTIONS: EXCEL TO DATA                         #
# ---------------------------------------------------------------------------- #

def row_to_timestring(row:pd.Series) -> None|str:
    
    if pd.isna(row).any():
        return None
    
    else:
        row = row.astype(int)
        return f"{row["시작시"]:02d}:{row["시작분"]:02d}~{row["종료시"]:02d}:{row["종료분"]:02d}"
    
    
def row_to_dayofweekstr(row:pd.Series) -> str:
    
    return ", ".join([dayofweek for dayofweek, condition in row.to_dict().items() if condition and (dayofweek in ["월","화","수","목","금","토","일"])])


def row_to_설비운영(row:pd.Series) -> None|설비운영:
    
    if pd.isna(row).any():
        return None
    
    else:
        return 설비운영(
            row_to_timestring(row[["시작시","시작분","종료시","종료분"]]),
            f"{int(row["시작월"]):02d}~{int(row["종료월"]):02d}월",
            float(v) if not isinstance(v:=row["설정온도"], str) else v,
        )

# ---------------------------------------------------------------------------- #
#                         SUBFUNCTINOS: DATA TO DRAGON                         #
# ---------------------------------------------------------------------------- #

def parse_duration_hours(operation_str:str) -> tuple[int,int,int,int]:
    
    pattern = re.compile(r"(?P<starth>\d{1,2}):(?P<startm>\d{2}) ?(-|~) ?(?P<endh>\d{1,2}):(?P<endm>\d{2})")
    matched = re.search(pattern, operation_str)
    
    return int(matched.group("starth")), int(matched.group("startm")), int(matched.group("endh")), int(matched.group("endm"))

def parse_duration_month(operation_str:str) -> tuple[list[int, int], list[int,int]|None]:
    
    pattern = re.compile(r"(?P<startm>\d{1,2})월? ?(-|~) ?(?P<endm>\d{1,2})월")
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
        "토": "saturday" ,
        "일": "sunday"   ,
    }
    
    return dow_dict[korean_dow]

def get_end_of_the_month(mth:int) -> int:
    
    endofthemonth_dict = {
        1:31, 2:28, 3:31,  4:30,  5:31,  6:30,
        7:31, 8:31, 9:30, 10:31, 11:30, 12:31,
    }
    
    return endofthemonth_dict[mth]

def ensure_integer_with_nan(v) -> int:
    if not pd.isna(v):
        return v
    else:
        return 0

# ---------------------------------------------------------------------------- #
#                          SUBFUNCTIONS: SCHEDULE 관련                          #
# ---------------------------------------------------------------------------- #

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
class 설비운영:
    사용시간:str
    사용기간:str
    설정온도:int    
    
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

    def get_setpoint_schedule(self,
        original_schedule:dragon.Schedule             ,
        mode             :Literal["heating","cooling"],
        ) -> dragon.Schedule:
        
        # uncontrolled temperature
        match mode:
            case "heating": default_temperature = -30
            case "cooling": default_temperature =  50
        
        # for invalid case: return default setpoint temperature
        if self.설정온도 == "확인불가":
            match mode:
                case "heating": setpoint = original_schedule.max
                case "cooling": setpoint = original_schedule.min
        else:
            setpoint = self.설정온도
                
        starth, startm, endh, endm = parse_duration_hours(self.사용시간)
        temperature_dayschedule = dragon.DaySchedule.from_compact(
            None,
            [
                (starth, startm, default_temperature),
                (endh  , endm  , int(setpoint)      ),
                (24    , 0     , default_temperature),
            ],
            dragon.ScheduleType.TEMPERATURE         
        )
        
        # ruleset:
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
class hvac존:
    
    # hvac
    난방설비1:설비운영
    난방설비2:설비운영
    냉방설비1:설비운영
    냉방설비2:설비운영
    
    def get_heating_setpoint_schedule(self, original_schedule:dragon.Schedule) -> dragon.Schedule:
        
        # 난방설비 1
        if self.난방설비1 is not None:
            first_equipment_setpoint = self.난방설비1.get_setpoint_schedule(original_schedule, "heating")
        
            # 난방설비 2
            if self.난방설비2 is not None:
                second_equipment_setpoint = self.난방설비2.get_setpoint_schedule(original_schedule, "heating")
                
                # 둘 다 고려 (최댓값으로)
                final_schedule = first_equipment_setpoint.element_max(second_equipment_setpoint)
                
            else:
                final_schedule = first_equipment_setpoint
        
        else:
            final_schedule = original_schedule
        
        return final_schedule
    
    def get_cooling_setpoint_schedule(self, original_schedule:dragon.Schedule) -> dragon.Schedule:
        
        # 냉방설비 1
        if self.냉방설비1 is not None:
            first_equipment_setpoint = self.냉방설비1.get_setpoint_schedule(original_schedule, "cooling")
            
            # 냉방설비 2
            if self.냉방설비2 is not None:
                second_equipment_setpoint = self.냉방설비2.get_setpoint_schedule(original_schedule, "cooling")
                
                # 둘 다 고려 (최솟값으로)
                final_schedule = first_equipment_setpoint.element_min(second_equipment_setpoint)
                
            else:
                final_schedule = first_equipment_setpoint
        
        else:
            final_schedule = original_schedule
        
        return final_schedule
    

@dataclass
class 보건소일반존(hvac존):
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
    
    @classmethod
    def from_excel(cls, filepath:str):
        
        # components
        재실 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=5, nrows=5, usecols=[3,4,5], index_col=0)
        운영시간 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=11, nrows=4, usecols=[3,4,5,6,7], index_col=0)
        운영요일 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=16, nrows=3, usecols=[3,4,5,6,7,8], index_col=0)
        설비 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=21, nrows=5, usecols=[3,4,5,6,7,8,9,10], index_col=0)
        설비.columns = ["시작시","시작분","종료시","종료분","시작월","종료월","설정온도"]
        
        return cls(
            *[
                row_to_설비운영(row)
                for _, row in 설비.iterrows()
            ],
            row_to_timestring(운영시간.loc["기본운영"]),
            int(재실.at["직원","인원수"]),
            int(운영요일.loc["외근"].sum()),
            row_to_timestring(운영시간.loc["외근"]),
            int(재실.at["외근직원","인원수"]),
            row_to_dayofweekstr(운영요일.loc["집중진료"]),
            row_to_timestring(운영시간.loc["집중진료"]),
            int(재실.at["집중진료-오전","인원수"]),
            int(재실.at["집중진료-오후","인원수"]),
            재실.at["집중진료-오전","체류시간"],
            재실.at["집중진료-오후","체류시간"],
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
        집중진료_dayofweeks = [translate_dayofweek(s.strip()) for s in self.집중진료요일.split(",") if not s==""]
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
            if 설비 is not None:
                operation_schedules.append(설비.get_hvac_availability_schedule())
            else:
                operation_schedules.append(dragon.Schedule.from_compact(
                    None, [("0101","1231", dragon.RuleSet(
                        None,
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                    ))]
                ))
            
        # 설비 가동스케줄 (or조건으로 개별 설비 결합: 모종의 설비가 가동중)
        hvac_availability = operation_schedules[0]
        for schedule in operation_schedules[1:]:
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
            
        return
    
@dataclass
class 보건소특화존1(hvac존):
    # zone
    운영요일:str
    오전운영시간:str
    오후운영시간:str
    오전재실인원:int
    오후재실인원:int
    
    @classmethod
    def from_excel(cls, filepath:str):
        
        # components
        재실 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=29, nrows=3, usecols=[3,4], index_col=0)
        운영시간 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=33, nrows=3, usecols=[3,4,5,6,7], index_col=0)
        운영요일 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=37, nrows=2, usecols=[3,4,5,6,7,8], index_col=0)
        설비 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=41, nrows=5, usecols=[3,4,5,6,7,8,9,10], index_col=0)
        설비.columns = ["시작시","시작분","종료시","종료분","시작월","종료월","설정온도"]
        
        # ensure validity by dayofweek
        has_valid_dayofweek = bool(운영요일.loc["운영요일"].any())
        
        return cls(
            *[
                row_to_설비운영(row)
                for _, row in 설비.iterrows()
            ],
            row_to_dayofweekstr(운영요일.loc["운영요일"]),
            row_to_timestring(운영시간.loc["오전"]) if has_valid_dayofweek else None,
            row_to_timestring(운영시간.loc["오후"]) if has_valid_dayofweek else None,
            int(v) if not pd.isna(v:=재실.at["오전","인원수"]) else pd.NA,
            int(v) if not pd.isna(v:=재실.at["오후","인원수"]) else pd.NA,
        )
    
    def get_occupant_schedule(self) -> dragon.Schedule:
        
        # 기본 스케줄 (0명)
        occupant_ruleset = dragon.RuleSet(
            None,
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
        )
        
        # 오전 재실
        if not pd.isna(self.오전운영시간):
            starth, startm, endh, endm = parse_duration_hours(self.오전운영시간)
            dayofweeks = [translate_dayofweek(s.strip()) for s in self.운영요일.split(",") if not s==""]
            오전_ruleset = dragon.RuleSet(
                None,
                dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
                dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
                **{
                    k: dragon.DaySchedule.from_compact(
                        None,
                        [
                            (starth, startm,              0),
                            (endh  , endm  , self.오전재실인원),
                            (24    , 0     ,              0),
                        ],
                        dragon.ScheduleType.REAL,
                    )
                    for k in dayofweeks
                }
            )
            occupant_ruleset += 오전_ruleset
        
        # 오후 재실
        if not pd.isna(self.오후운영시간):
            starth, startm, endh, endm = parse_duration_hours(self.오후운영시간)
            dayofweeks = [translate_dayofweek(s.strip()) for s in self.운영요일.split(",") if not s==""]
            오후_ruleset = dragon.RuleSet(
                None,
                dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
                dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.REAL,),
                **{
                    k: dragon.DaySchedule.from_compact(
                        None,
                        [
                            (starth, startm,              0),
                            (endh  , endm  , self.오후재실인원),
                            (24    , 0     ,              0),
                        ],
                        dragon.ScheduleType.REAL,
                    )
                    for k in dayofweeks
                }
            )
            occupant_ruleset += 오후_ruleset

        # 둘이 합치기
        occupant_schedule = dragon.Schedule.from_compact(
            None,
            [("0101","1231", occupant_ruleset)]
        )
        
        return occupant_schedule
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        # 기본 운영시간
        기본운영_ruleset = dragon.RuleSet(
            None,
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.ONOFF,),
            dragon.DaySchedule.from_compact(None, [(24,0,0)],dragon.ScheduleType.ONOFF,),
        )
        
        # 오전 운영시간
        if not pd.isna(self.오전운영시간):
            starth, startm, endh, endm = parse_duration_hours(self.오전운영시간)
            오전운영_ruleset = dragon.RuleSet(
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
            기본운영_ruleset |= 오전운영_ruleset
        
        # 오후 운영시간
        if not pd.isna(self.오후운영시간):
            starth, startm, endh, endm = parse_duration_hours(self.오후운영시간)
            오후운영_ruleset = dragon.RuleSet(
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
            기본운영_ruleset |= 오후운영_ruleset
        
        # 기본 운영 schedule 정리
        기본운영_schedule = dragon.Schedule.from_compact(
            None,
            [("0101","1231", 기본운영_ruleset)]
        )
        
        # 설비 가동스케줄 (개별)
        operation_schedules = []
        for 설비 in [self.난방설비1, self.난방설비2, self.냉방설비1, self.냉방설비2]:
            if 설비 is not None:
                operation_schedules.append(설비.get_hvac_availability_schedule())
            else:
                operation_schedules.append(dragon.Schedule.from_compact(
                    None, [("0101","1231", dragon.RuleSet(
                        None,
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                    ))]
                ))
        
        # 설비 가동스케줄 (or조건으로 개별 설비 결합: 모종의 설비가 가동중)
        hvac_availability = operation_schedules[0]
        for schedule in operation_schedules[1:]:
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
                f"{zone.name}_특화존1체크리스트",
                self.get_heating_setpoint_schedule(zone.profile.heating_setpoint), 
                self.get_cooling_setpoint_schedule(zone.profile.cooling_setpoint), 
                hvac_availability_schedule,
                occupant_schedule         ,
                zone.profile.lighting     ,
                zone.profile.equipment    ,
            )
            
        return
    
    
@dataclass
class 보건소특화존2(hvac존):
    #zone
    사용관사수:str
    동거인수:int
    운영요일:int

    @classmethod
    def from_excel(cls, filepath:str):
        
        # components
        재실 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=49, nrows=3, usecols=[3,4], index_col=0)
        운영요일 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=53, nrows=2, usecols=[3,4,5,6,7,8,9,10], index_col=0)
        설비 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=57, nrows=5, usecols=[3,4,5,6,7,8,9,10], index_col=0)
        설비.columns = ["시작시","시작분","종료시","종료분","시작월","종료월","설정온도"]
        
        return cls(
            *[
                row_to_설비운영(row)
                for _, row in 설비.iterrows()
            ],
            int(재실.at["사용관사수","인원수"]),
            int(재실.at["동거인수","인원수"]),
            row_to_dayofweekstr(운영요일.loc["운영요일"]),   
        )
    
    def get_occupant_schedule(self) -> dragon.Schedule:
        
        return
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        return

    def apply_to(self, zones:list[dragon.Zone]) -> None:
        
        total_area = max(sum(zone.floor_area for zone in zones), 1E-6)
        
        for zone in zones:
            zone.profile = dragon.Profile(
                f"{zone.name}_특화존2체크리스트",
                zone.profile.heating_setpoint, 
                zone.profile.cooling_setpoint, 
                zone.profile.hvac_availability,
                zone.profile.occupant,
                zone.profile.lighting     ,
                zone.profile.equipment    ,
            )
            
        return
    

@dataclass
class 어린이집일반존(hvac존):
    # zone
    기본보육교사:int
    기본보육원생:int
    연장보육A교사:int
    연장보육A원생:int
    연장보육B교사:int
    연장보육B원생:int
    야간보육교사:int
    야간보육원생:int
    주말보육시간:str
    주말보육교사:int
    주말보육원생:int
            
    @classmethod
    def from_excel(cls, filepath:str):
        
        재실 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=5, nrows=6, usecols=[3,4,5], index_col=0)
        주말보육시간 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=12, nrows=2, usecols=[3,4,5,6,7], index_col=0)
        설비 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=16, nrows=5, usecols=[3,4,5,6,7,8,9,10], index_col=0)
        설비.columns = ["시작시","시작분","종료시","종료분","시작월","종료월","설정온도"]
        
        return cls(
            *[
                row_to_설비운영(row)
                for _, row in 설비.iterrows()
            ],
            int(재실.at["기본보육","교사"]),
            int(재실.at["기본보육","원생"]),
            int(재실.at["연장보육A","교사"]),
            int(재실.at["연장보육A","원생"]),
            int(재실.at["연장보육B","교사"]),
            int(재실.at["연장보육B","원생"]),
            int(v) if not pd.isna(v:= 재실.at["야간보육","교사"]) else v,
            int(v) if not pd.isna(v:= 재실.at["야간보육","원생"]) else v,
            row_to_timestring(주말보육시간.loc["주말보육"]),
            int(v) if not pd.isna(v:=재실.at["주말보육","교사"]) else pd.NA,
            int(v) if not pd.isna(v:=재실.at["주말보육","원생"]) else pd.NA,
        )
    
    def get_occupant_schedule(self) -> dragon.Schedule:
        
        # 평일
        기본보육인원 = self.기본보육교사 + self.기본보육원생
        연장보육A인원 = ensure_integer_with_nan(self.연장보육A교사) + ensure_integer_with_nan(self.연장보육A원생)
        연장보육B인원 = ensure_integer_with_nan(self.연장보육B교사) + ensure_integer_with_nan(self.연장보육B원생)
        야간보육인원 = ensure_integer_with_nan(self.야간보육교사) + ensure_integer_with_nan(self.야간보육원생)
        평일_dayschedule = dragon.DaySchedule.from_compact(
                None, [
                    (7, 30, 0),
                    (16,  0, 기본보육인원),
                    (18,  0, 연장보육A인원),
                    (19, 30, 연장보육B인원),
                    (21,  0, 야간보육인원),
                    (24,  0,  0),
                ],
                dragon.ScheduleType.REAL
            )
        
        # 주말
        if not pd.isna(self.주말보육시간):
            starth, startm, endh, endm = parse_duration_hours(self.주말보육시간)
            주말보육인원 = ensure_integer_with_nan(self.주말보육교사) + ensure_integer_with_nan(self.주말보육원생)
            주말_dayschedule = dragon.DaySchedule.from_compact(
                    None, [
                        (starth, startm, 0),
                        (endh, endm, 주말보육인원),
                        (24, 0, 0)
                    ],
                    dragon.ScheduleType.REAL
                )
        else:
            주말_dayschedule = dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.REAL)
        
        # 스케줄
        occupant_ruleset = dragon.RuleSet(
            None,
            평일_dayschedule,
            주말_dayschedule,            
        )
        
        occupant_schedule = dragon.Schedule.from_compact(
            None,
            [("0101","1231", occupant_ruleset)]
        )
        
        return occupant_schedule
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        # 평일
        연장보육A인원 = ensure_integer_with_nan(self.연장보육A교사) + ensure_integer_with_nan(self.연장보육A원생)
        연장보육B인원 = ensure_integer_with_nan(self.연장보육B교사) + ensure_integer_with_nan(self.연장보육B원생)
        야간보육인원 = ensure_integer_with_nan(self.야간보육교사) + ensure_integer_with_nan(self.야간보육원생)
        평일_dayschedule = dragon.DaySchedule.from_compact(
                None, [
                    (7, 30, 0),
                    (16,  0, 1),
                    (18,  0, int(연장보육A인원 > 0)),
                    (19, 30, int(연장보육B인원 > 0)),
                    (21,  0, int(야간보육인원 > 0)),
                    (24,  0,  0),
                ],
                dragon.ScheduleType.ONOFF
            )
        
        # 주말
        if not pd.isna(self.주말보육시간):
            starth, startm, endh, endm = parse_duration_hours(self.주말보육시간)
            주말_dayschedule = dragon.DaySchedule.from_compact(
                    None, [
                        (starth, startm, 0),
                        (endh   , endm, 1),
                        (24, 0, 0)
                    ],
                    dragon.ScheduleType.ONOFF
                )
        else:
            주말_dayschedule = dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF)
        
        # 스케줄
        기본운영_ruleset = dragon.RuleSet(
            None,
            평일_dayschedule,
            주말_dayschedule,            
        )
        
        기본운영_schedule = dragon.Schedule.from_compact(
            None,
            [("0101","1231", 기본운영_ruleset)]
        )
        
        # 설비 가동스케줄 (개별)
        operation_schedules = []
        for 설비 in [self.난방설비1, self.난방설비2, self.냉방설비1, self.냉방설비2]:
            if 설비 is not None:
                operation_schedules.append(설비.get_hvac_availability_schedule())
            else:
                operation_schedules.append(dragon.Schedule.from_compact(
                    None, [("0101","1231", dragon.RuleSet(
                        None,
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                    ))]
                ))
                
        # 설비 가동스케줄 (or조건으로 개별 설비 결합: 모종의 설비가 가동중)
        hvac_availability = operation_schedules[0]
        for schedule in operation_schedules[1:]:
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
                self.get_cooling_setpoint_schedule(zone.profile.cooling_setpoint), 
                hvac_availability_schedule,
                occupant_schedule         ,
                zone.profile.lighting     ,
                zone.profile.equipment    ,
            )
            
        return

@dataclass
class 어린이집특화존1(hvac존):
    # zone
    오전운영시간:str
    오후운영시간:str
    오전인원:int
    오후인원:int
        
    @classmethod
    def from_excel(cls, filepath:str):
        
        재실 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=24, nrows=3, usecols=[3,4], index_col=0)
        운영시간 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=28, nrows=3, usecols=[3,4,5,6,7], index_col=0)
        설비 = pd.read_excel(filepath, sheet_name="현장조사", skiprows=33, nrows=5, usecols=[3,4,5,6,7,8,9,10], index_col=0)
        설비.columns = ["시작시","시작분","종료시","종료분","시작월","종료월","설정온도"]
        
        return cls(
            *[
                row_to_설비운영(row)
                for _, row in 설비.iterrows()
            ],
            row_to_timestring(운영시간.loc["오전"]),
            row_to_timestring(운영시간.loc["오후"]),
            int(v) if not pd.isna(v:=재실.at["오전","인원"]) else pd.NA,
            int(v) if not pd.isna(v:=재실.at["오후","인원"]) else pd.NA,
        )
    
    def get_occupant_schedule(self) -> dragon.Schedule:
        
        오전starth, 오전startm, 오전endh, 오전endm = parse_duration_hours(self.오전운영시간)
        오후starth, 오후startm, 오후endh, 오후endm = parse_duration_hours(self.오후운영시간)
        
        if 오전endh == 오후starth and 오전endm == 오후startm:
            dayschedule_values = [
                (오전starth, 오전startm, 0),
                (오후starth, 오후startm, self.오전인원),
                (오후endh  , 오전endm  , self.오후인원),
                (24        , 0        , 0),
            ]
        else:
            dayschedule_values = [
                (오전starth, 오전startm, 0),
                (오전endh  , 오전endm  , self.오전인원),
                (오후starth, 오후startm, 0),
                (오후endh  , 오전endm  , self.오후인원),
                (24        , 0        , 0),
            ]
            
        occupant_schedule = dragon.Schedule.from_compact(
            None, [("0101","1231", dragon.RuleSet(
                None,
                dragon.DaySchedule.from_compact(None, dayschedule_values, dragon.ScheduleType.REAL),
                dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.REAL)
            ))]
        )
        
        return occupant_schedule
    
    def get_hvac_availability_schedule(self) -> dragon.Schedule:
        
        오전starth, 오전startm, 오전endh, 오전endm = parse_duration_hours(self.오전운영시간)
        오후starth, 오후startm, 오후endh, 오후endm = parse_duration_hours(self.오후운영시간)
        
        if 오전endh == 오후starth and 오전endm == 오후startm:
            dayschedule_values = [
                (오전starth, 오전startm, 0),
                (오후starth, 오후startm, 1),
                (오후endh  , 오전endm  , 1),
                (24        , 0        , 0),
            ]
        else:
            dayschedule_values = [
                (오전starth, 오전startm, 0),
                (오전endh  , 오전endm  , 1),
                (오후starth, 오후startm, 0),
                (오후endh  , 오전endm  , 1),
                (24        , 0        , 0),
            ]
            
        기본운영_schedule = dragon.Schedule.from_compact(
            None, [("0101","1231", dragon.RuleSet(
                None,
                dragon.DaySchedule.from_compact(None, dayschedule_values, dragon.ScheduleType.ONOFF),
                dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF)
            ))]
        )
        
        # 설비 가동스케줄 (개별)
        operation_schedules = []
        for 설비 in [self.난방설비1, self.난방설비2, self.냉방설비1, self.냉방설비2]:
            if 설비 is not None:
                operation_schedules.append(설비.get_hvac_availability_schedule())
            else:
                operation_schedules.append(dragon.Schedule.from_compact(
                    None, [("0101","1231", dragon.RuleSet(
                        None,
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                        dragon.DaySchedule.from_compact(None, [(24,0,0)], dragon.ScheduleType.ONOFF),
                    ))]
                ))
                
        # 설비 가동스케줄 (or조건으로 개별 설비 결합: 모종의 설비가 가동중)
        hvac_availability = operation_schedules[0]
        for schedule in operation_schedules[1:]:
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
                f"{zone.name}_특화존체크리스트",
                self.get_heating_setpoint_schedule(zone.profile.heating_setpoint), 
                self.get_cooling_setpoint_schedule(zone.profile.cooling_setpoint), 
                hvac_availability_schedule,
                occupant_schedule         ,
                zone.profile.lighting     ,
                zone.profile.equipment    ,
            )
            
        return

# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #

class 현장조사체크리스트(ABC):
    
    """ input
    """
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 현장조사체크리스트: ...
    
    @classmethod
    def from_dataframe(cls, df:pd.DataFrame) -> list[현장조사체크리스트]:
        return [cls.from_row(row) for _, row in df.iterrows()]
    
    @staticmethod
    def from_excel(
        filepath:str,
        ) -> None:
        
        building_type = pd.read_excel(filepath, sheet_name="현장조사", nrows=1, usecols=[0]).at[0,"현장조사유형"]
        
        match building_type:
            case "보건소":
                return 보건소체크리스트.from_excel(filepath)
            case "어린이집":
                return 어린이집체크리스트.from_excel(filepath)
    
    """ output
    """
    
    @abstractmethod
    def apply_to(self, grm:GreenRetrofitModel) -> IDF: ...
        

class 어린이집체크리스트:
    
    def __init__(self,
        일반존 : 어린이집일반존 ,
        특화존1: 어린이집특화존1,
        ) -> None:
        
        # zone survey
        self.일반존  = 일반존
        self.특화존1 = 특화존1
    
    @classmethod
    def from_excel(cls, filepath:str) -> 어린이집체크리스트:
        
        return cls(
            어린이집일반존.from_excel(filepath),
            어린이집특화존1.from_excel(filepath),
        )
        
    def apply_to(self, grm:GreenRetrofitModel, exceldata:dict[str,pd.DataFrame]) -> IDF:
        
        zoneID_category = {
            category: [
                zone.ID for zone in grm.zone
                if zone.name in list(exceldata["실"].query("현장조사프로필 == @category" )["이름"].values)
            ]
            for category in ["일반존","특화존1"]
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
        
        return em.to_idf()
    
class 보건소체크리스트:
    
    def __init__(self,
        일반존 : 보건소일반존 ,
        특화존1: 보건소특화존1,
        특화존2: 보건소특화존2,
        ) -> None:
        
        # zone survey
        self.일반존  = 일반존
        self.특화존1 = 특화존1
        self.특화존2 = 특화존2
    
    @classmethod
    def from_excel(cls, filepath:str) -> 보건소체크리스트:
        
        return cls(
            보건소일반존.from_excel(filepath),
            보건소특화존1.from_excel(filepath),
            보건소특화존2.from_excel(filepath),
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

# ---------------------------------------------------------------------------- #
#                                  APPLICATION                                 #
# ---------------------------------------------------------------------------- #

def compare_surveys(
    survey1:현장조사체크리스트,
    survey2:현장조사체크리스트,
    ) -> str:
    
    pass

