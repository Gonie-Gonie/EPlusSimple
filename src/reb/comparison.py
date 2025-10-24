
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
from abc import ABC, abstractmethod

# third-party modules
import pandas as pd

# local modules
from .preprocess import process_excel_file


# ---------------------------------------------------------------------------- #
#                              DIFFERENCE CLASSES                              #
# ---------------------------------------------------------------------------- #

class ExcelDifference(ABC):
    
    @classmethod
    @abstractmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame]
        ) -> ExcelDifference: ...
    


# ---------------------------------------------------------------------------- #
#                                 SUBFUNCTIONS                                 #
# ---------------------------------------------------------------------------- #

PERFORMANCE_DIFFLIST = [
    
]

OPERATION_DIFFLIST = [
    
]

def compare_performance(
    excelbefore:dict[str, pd.DataFrame],
    excelafter :dict[str, pd.DataFrame],
    ) -> list[ExcelDifference]:
    
    pass


def compare_operation(
    excelbefore:dict[str, pd.DataFrame],
    excelafter :dict[str, pd.DataFrame],
    ) -> list[ExcelDifference]:
    
    pass

# ---------------------------------------------------------------------------- #
#                                   MAIN FUNC                                  #
# ---------------------------------------------------------------------------- #

def compare_weather():
    pass

def compare_rebexcel(
    excelbeforepath:dict[str, pd.DataFrame],
    excelafterpath :dict[str, pd.DataFrame],
    ) -> tuple[list[ExcelDifference]]:
    
    # before data
    processedbeforepath = process_excel_file(excelbeforepath, verbose=False)
    excelbefore         = pd.read_excel(processedbeforepath, sheet_name=None)
    os.remove(processedbeforepath)
    
    # after data
    processedafterpath = process_excel_file(excelafterpath, verbose=False)
    excelafter         = pd.read_excel(processedafterpath, sheet_name=None)
    os.remove(processedafterpath)
    
    # compare
    performance_differences = compare_performance(excelbefore, excelafter)
    operation_differences   = compare_operation(excelbefore, excelafter)
    
    return performance_differences, operation_differences
    