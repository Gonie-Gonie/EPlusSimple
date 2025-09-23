
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from abc import (
    ABC           ,
    abstractmethod,
)
from dataclasses import (
    field    ,
    dataclass,
)


# third-party modules


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
    
# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #

class 현장조사체크리스트(ABC):

    @abstractmethod
    def from_dataframe(filepath:str):
        ...
        
    @abstractmethod
    def apply_to(grm:GreenRetrofitModel) -> IDF:
        ...
        
class 어린이집GR이전체크리스트(현장조사체크리스트): ...

class 어린이집GR이후체크리스트(현장조사체크리스트): ...
    
class 보건소GR이전체크리스트(현장조사체크리스트): ...

class 보건소GR이후체크리스트(현장조사체크리스트): ...

# 보건지소 = 보건소
보건지소GR이전체크리스트 = 보건소GR이전체크리스트
보건지소GR이후체크리스트 = 보건소GR이후체크리스트

class 의료시설GR이전체크리스트(현장조사체크리스트): ...

class 의료시설GR이후체크리스트(현장조사체크리스트): ...




