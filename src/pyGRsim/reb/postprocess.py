
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
    userId    : str = field()
    userName  : str
    name      : str
    department: str
    updatedAt : str
    version   : str
    
@dataclass
class 기본사항:
    건물명       :str
    GR준공일     :str
    조사일       :str
    응답자근무기간:str
    유형         :str
    
# @dataclass
# class Record:
#     date_str: str # 입력은 str로 받음
#     date: datetime = field(init=False)

#     def __post_init__(self): # str → datetime 변환
#         self.date = datetime.strptime(self.date_str, "%Y-%m-%d")

# from dataclasses import dataclass, field, fields

# @dataclass
# class SurveyResponse:
#     age: int = field(default=None, metadata={"col": "A1"})
#     gender: str = field(default=None, metadata={"col": "A2"})
#     income: float = field(default=None, metadata={"col": "A3"})

# import pandas as pd

# row = {"A1": 25, "A2": "M", "A3": 50000.0}  # 데이터 예시

# def row_to_dataclass(row: dict, cls):
#     kwargs = {}
#     for f in fields(cls):
#         col = f.metadata.get("col")
#         if col and col in row:
#             kwargs[f.name] = row[col]
#     return cls(**kwargs)

# person = row_to_dataclass(row, SurveyResponse)
# print(person)  # SurveyResponse(age=25, gender='M', income=50000.0)
    
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
    def apply_to(grm:GreenRetrofitModel) -> IDF:
        ...
        
class 어린이집GR이전체크리스트(현장조사체크리스트):
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 어린이집GR이전체크리스트:
        pass

class 어린이집GR이후체크리스트(현장조사체크리스트):
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 어린이집GR이후체크리스트:
        pass
    
class 보건소GR이전체크리스트(현장조사체크리스트): 
    
    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        pass
    
class 보건소GR이후체크리스트(현장조사체크리스트):

    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이후체크리스트:
        pass
    
class 의료시설GR이전체크리스트(현장조사체크리스트): ...

class 의료시설GR이후체크리스트(현장조사체크리스트): ...




