
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
    
@dataclass
class 기본정보:
    건물명       :str 
    GR준공일     :str 
    조사일       :str 
    응답자근무기간:str 
    유형         :str
    
    @classmethod
    def from_row(cls, row:pd.Series,):
        pass
    
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
        obj.metadata = MetaData(
            row["userId"], row["userName"], row["name"], row["department"], row["updatedAt"], row["version"]
        )
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
        obj.metadata = MetaData(
            row["userId"], row["userName"], row["name"], row["department"], row["updatedAt"], row["version"]
        )
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
        obj.metadata = MetaData(
            row["userId"], row["userName"], row["name"], row["department"], row["updatedAt"], row["version"]
        )
        obj.기본정보 = 기본정보(row["A1"],row["A2"],row["A3"],row["A4"],row["A5"])
        
        return obj
    
    def apply_to(self, grm:GreenRetrofitModel) -> IDF:
        
        return IDF()
    
class 보건소GR이후체크리스트(현장조사체크리스트):

    @classmethod
    def from_row(cls, row:pd.Series) -> 보건소GR이전체크리스트:
        
        # create obj
        obj = cls()
        obj.raw = row
        
        # metadata
        obj.metadata = MetaData(
            row["userId"], row["userName"], row["name"], row["department"], row["updatedAt"], row["version"]
        )
        obj.기본정보 = 기본정보(row["A1"],row["A2"],row["A3"],row["A4"],row["A5"])
        
        return obj
        
    def apply_to(self, grm:GreenRetrofitModel) -> IDF:
        
        return IDF()
    
class 의료시설GR이전체크리스트(현장조사체크리스트): ...

class 의료시설GR이후체크리스트(현장조사체크리스트): ...

