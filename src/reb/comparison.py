
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
    
    def __init__(self,
        zonename:str,
        prop    :str,
        before  :int|float|str,
        after   :int|float|str,
        unit    :str,
        ) -> None:
        
        self.zonename = zonename
        self.prop     = prop
        self.before   = before
        self.after    = after
        self.unit     = unit
    
    @classmethod
    @abstractmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame]
        ) -> list[ExcelDifference]: ...
    
    def to_dict(self) -> dict:
        return {
            "zonename": self.zonename,
            "type"    : self.KoreanNAME,
            "prop"    : self.prop,
            "before"  : self.before,
            "after"   : self.after,
            "unit"    : self.unit,
        }

class ZoneDifference(ExcelDifference):
    
    KoreanNAME = "존 생성/삭제"
    
    @classmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame],
        ) -> list[ZoneDifference]:
        
        diffs = []
        for _, row in before["실"].iterrows():
            if (zonename:=row["이름"]) not in after["실"]["이름"]:
                diffs.append(cls(zonename, "존재", "소멸", "-","-"))
        
        for _, row in after["실"].iterrows():
            if (zonename:=row["이름"]) not in before["실"]["이름"]:
                diffs.append(cls(zonename, "존재", "-", "신규","-"))
                
        return diffs

class WindowDifference(ExcelDifference):
    
    KoreanNAME = "창호 변경"
    
    @classmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame]
        ) -> list[WindowDifference]: 
        
        before_Udict = {
            row["이름"]: row["열관류율 [W/m2·K]"]
            for _, row in before["구조체_개구부"].iterrows()
        }
        after_Udict = {
            row["이름"]: row["열관류율 [W/m2·K]"]
            for _, row in after["구조체_개구부"].iterrows()
        }
        
        before_SHGCdict = {
            row["이름"]: row["태양열취득계수"]
            for _, row in before["구조체_개구부"].iterrows()
        }
        after_SHGCdict = {
            row["이름"]: row["태양열취득계수"]
            for _, row in after["구조체_개구부"].iterrows()
        }
        
        diffs = []
        for _, row in before["실"].iterrows():
            
            zonename = row["이름"]
            if zonename not in after["실"]["이름"].values:
                continue
            
            # windowdata: before
            before_walls   = before["면"].loc[before["면"]["소속 실"] == zonename]
            before_windows = before["개구부"].loc[before["개구부"]["소속 면"].map(lambda v: v in before_walls["이름"].values)]
            before_winarea = before_windows["면적 [m2]"].sum()
            
            # windowdata: after
            after_walls   = after["면"].loc[after["면"]["소속 실"] == zonename]
            after_windows = after["개구부"].loc[after["개구부"]["소속 면"].map(lambda v: v in after_walls["이름"].values)]
            after_winarea  = after_windows["면적 [m2]"].sum()
            
            # area comparison
            if abs(before_winarea - after_winarea) > 0.1:
                diffs.append(cls(zonename, "면적", before_winarea, after_winarea, "m2"))
                
            if (before_winarea > 0 and after_winarea > 0):
                
                # U valud comparison
                before_U = float(sum(
                    row["면적 [m2]"]*before_Udict[row["구조체 이름"]]
                    for _, row in before_windows.iterrows()
                    )/before_winarea)
                after_U = float(sum(
                    row["면적 [m2]"]*after_Udict[row["구조체 이름"]]
                    for _, row in after_windows.iterrows()
                    )/after_winarea)

                if abs(before_U - after_U) > 0.1:
                    diffs.append(cls(zonename, "평균열관류율", before_U, after_U, "W/m2K"))
                
                # SHGC comparison
                before_SHGC = float(sum(
                    row["면적 [m2]"]*before_SHGCdict[row["구조체 이름"]]
                    for _, row in before_windows.iterrows()
                    )/before_winarea)
                after_SHGC = float(sum(
                    row["면적 [m2]"]*after_SHGCdict[row["구조체 이름"]]
                    for _, row in after_windows.iterrows()
                    )/after_winarea)

                if abs(before_SHGC - after_SHGC) > 0.1:
                    diffs.append(cls(zonename, "태양열취득계수", before_SHGC, after_SHGC, "-"))     
        
        return diffs



class LightDensityDifference(ExcelDifference):
    
    KoreanNAME = "조명 밀도 변경"
    
    @classmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame]
        ) -> list[LightDensityDifference]:
        
        diffs = []
        for _, row in before["실"].iterrows():
            
            zonename = row["이름"]
            if zonename not in after["실"]["이름"].values:
                continue
            
            before_LPD=row["조명밀도 [W/m2]"]
            after_LPD =float(after["실"]["조명밀도 [W/m2]"][after["실"]["이름"] == row["이름"]].iloc[0])
            
            if abs(before_LPD - after_LPD) > 0.01:
                diffs.append(cls(zonename, "조명밀도", before_LPD, after_LPD, "W/m2"))
                
        return diffs
    
class InfiltrationDifference(ExcelDifference):
    
    KoreanNAME = "침기율 변경"
    
    @classmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame]
        ) -> list[LightDensityDifference]:
        
        diffs = []
        for _, row in before["실"].iterrows():
            
            zonename = row["이름"]
            if zonename not in after["실"]["이름"].values:
                continue
            
            before_LPD=row["침기율 [ACH@50]"]
            after_LPD =float(after["실"]["침기율 [ACH@50]"][after["실"]["이름"] == row["이름"]].iloc[0])
            
            if abs(before_LPD - after_LPD) > 0.01:
                diffs.append(cls(zonename, "침기율", before_LPD, after_LPD, "ACH@50"))
                
        return diffs
            

# ---------------------------------------------------------------------------- #
#                                 SUBFUNCTIONS                                 #
# ---------------------------------------------------------------------------- #

PERFORMANCE_DIFFLIST = [
    WindowDifference      ,
    LightDensityDifference,
    InfiltrationDifference,
]

OPERATION_DIFFLIST = [
    
]

def compare_performance(
    excelbefore:dict[str, pd.DataFrame],
    excelafter :dict[str, pd.DataFrame],
    ) -> list[ExcelDifference]:
    
    diffs = []
    for diff in PERFORMANCE_DIFFLIST:
        diffs += diff.compare(excelbefore, excelafter)
    
    return diffs


def compare_operation(
    excelbefore:dict[str, pd.DataFrame],
    excelafter :dict[str, pd.DataFrame],
    ) -> list[ExcelDifference]:
    
    diffs = []
    for diff in OPERATION_DIFFLIST:
        diffs += diff.compare(excelbefore, excelafter)
    
    return diffs

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
    