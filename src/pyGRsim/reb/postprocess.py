
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
from abc import (
    ABC           ,
    abstractmethod,
)
from dataclasses import (
    field    ,
    dataclass,
)
from enum import Enum


# third-party modules
import pandas as pd

# local modules
from pyGRsim import GreenRetrofitModel
from idragon import (
    dragon     ,
    IDF        ,
)


# ---------------------------------------------------------------------------- #
#                                      SUB                                     #
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
    
    def get_hvac_availability_schedule(self, name:str) -> dragon.Schedule:
        
        # 미사용 -> ALL OFF
        if pd.isna(self.사용여부) or (self.사용여부 == "미사용"):
            return dragon.Schedule.from_compact(
                name,
                [
                    ("0101","1231", dragon.RuleSet(
                        f"ALLOFF_ruleset:for:{name}",
                        dragon.DaySchedule(
                            f"ALLOFF_dayschedule:for:{name}", [0]*dragon.DaySchedule.DATA_INTERVAL * 24
                        )
                    ))
                ]
            )
        
        # 사용 -> 기간과 시간으로 만들기..
        elif self.사용여부 == "사용":
            
            # 기본 운영시간도 반영해야 함...
            
            return dragon.Schedule.from_compact(
                name,
                ()
            )
            
        else:
            raise ValueError(
                f"TO PHIKO: 설비 {self.이름} '사용여부' 속성에 {self.사용여부} 넣어놓음 ('사용', '미사용', 또는 빈칸이어야 함)"
            )
    
    def get_setpoint_temperature(self, name:str) -> dragon.Schedule:
        pass


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
        
        
        
        return

    def apply_to(self, zones:list[dragon.Zone]) -> None:
        
        total_area = sum(zone.floor_area for zone in zones)
        
        for zone in zones:
            zone.profile = dragon.Profile(
                f"{zone.name}_일반존체크리스트",
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

    def apply_to(self, zones:list[dragon.Zone]) -> None:
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

    def apply_to(self, zones:list[dragon.Zone]) -> None:
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
        
    def apply_to(self, grm:GreenRetrofitModel) -> IDF:
        
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
        
    def apply_to(self, grm:GreenRetrofitModel) -> IDF:
        
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

