
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
from idragon import IDF


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
    
    @classmethod
    def from_row(cls, row:pd.Series):
        
        return cls(
            row["userId"], row["userName"], row["name"], row["department"], row["updatedAt"], row["version"]
        )
    
@dataclass
class 기본정보:
    건물명       :str 
    GR준공일     :str 
    조사일       :str 
    응답자근무기간:str 
    유형         :str
    

@dataclass
class 보건소운영현황:
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
    def from_row(cls, row:pd.Series, is_priorGR:bool):
        
        return cls(
            row["B1"], row["B2"], row["B3"], row["B4"], row["B5"],
            row["B6"], row["B7"], row["B8"], row["B9"], row["B10"], row["B11"],
        )

@dataclass
class 설비운영:
    이름:str
    사용시간:str
    사용기간:str
    설정온도:int|str
    사용여부:str

@dataclass
class 보건소일반존:
    난방설비1:설비운영
    난방설비2:설비운영
    냉방설비1:설비운영
    냉방설비2:설비운영
    
    @classmethod
    def from_row(cls, row:pd.Series, is_priorGR:bool):
        
        if is_priorGR:
            return cls(
                설비운영(row["B55"],row["B56"],row["B58"],row["B59"],row["BA1"]),
                설비운영(row["B60"],row["B61"],row["B63"],row["B64"],row["BA2"]),
                설비운영(row["B65"],row["B66"],row["B68"],row["B69"],row["BA3"]),
                설비운영(row["B70"],row["B71"],row["B73"],row["B74"],row["BA4"]),
            )
        else:
            return cls(
                설비운영(row["B51"],row["B52"],row["B54"],row["B55"],row["BA1"]),
                설비운영(row["B56"],row["B57"],row["B59"],row["B60"],row["BA2"]),
                설비운영(row["B61"],row["B61"],row["B64"],row["B65"],row["BA3"]),
                설비운영(row["B66"],row["B67"],row["B69"],row["B70"],row["BA4"]),
            )

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

# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #

class 현장조사체크리스트(ABC):
    
    """ input
    """
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 현장조사체크리스트:
        ...
    
    @classmethod
    def from_dataframe(cls, df:pd.DataFrame) -> list[현장조사체크리스트]:
        return [cls.from_row(row) for _, row in df.iterrows()]
    
    """ output
    """
    
    @abstractmethod
    def apply_to(self, grm:GreenRetrofitModel) -> IDF:
        ...
        
class 어린이집GR이전체크리스트(현장조사체크리스트):
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        # create obj
        obj = cls()
        obj.raw = row
        
        # metadata
        obj.metadata = MetaData.from_row(row)
        obj.기본정보 = 기본정보(row["A1"],row["A2"],row["A3"],row["A4"],None)
        
        return obj
        
    def apply_to(self, grm:GreenRetrofitModel) -> IDF:
        
        return IDF()

class 어린이집GR이후체크리스트(현장조사체크리스트):
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        # create obj
        obj = cls()
        obj.raw = row
        
        # metadata
        obj.metadata = MetaData.from_row(row)
        obj.기본정보 = 기본정보(row["A1"],row["A2"],row["A3"],row["A4"],row["A5"])
        
        return obj
        
    def apply_to(self, grm:GreenRetrofitModel) -> IDF:
        
        return IDF()
    
class 보건소GR이전체크리스트(현장조사체크리스트): 
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        # create obj
        obj = cls()
        obj.raw = row
        
        # metadata
        obj.metadata = MetaData.from_row(row)
        obj.기본정보 = 기본정보(row["A1"],row["A2"],row["A3"],row["A4"],row["A5"])
        
        # operational data
        obj.운영 = 보건소운영현황.from_row(row, True)
        obj.일반존 = 보건소일반존.from_row(row, True)
        obj.특화존1 = 보건소특화존1.from_row(row, True)
        obj.특화존2 = 보건소특화존2.from_row(row, True)
        
        return obj
    
    def apply_to(self, grm:GreenRetrofitModel, exceldata:dict[str,pd.DataFrame]) -> IDF:
        
        return IDF()
    
class 보건소GR이후체크리스트(현장조사체크리스트):

    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        # create obj
        obj = cls()
        obj.raw = row
        
        # metadata
        obj.metadata = MetaData.from_row(row)
        obj.기본정보 = 기본정보(row["A1"],row["A2"],row["A3"],row["A4"],row["A5"])
        
        # operational data
        obj.운영 = 보건소운영현황.from_row(row, False)
        obj.일반존 = 보건소일반존.from_row(row, True)
        obj.특화존1 = 보건소특화존1.from_row(row, True)
        obj.특화존2 = 보건소특화존2.from_row(row, True)
        
        return obj
        
    def apply_to(self, grm:GreenRetrofitModel, exceldata:dict[str,pd.DataFrame]) -> IDF:
        
        return IDF()
    
class 의료시설GR이전체크리스트(현장조사체크리스트): ...

class 의료시설GR이후체크리스트(현장조사체크리스트): ...

