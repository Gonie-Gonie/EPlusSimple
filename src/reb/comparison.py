
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
from abc import ABC, abstractmethod
from typing import Literal

# third-party modules
import pandas as pd

# local modules
from .preprocess import process_excel_file
from .postprocess import (
    현장조사체크리스트,
    어린이집체크리스트,
    보건소체크리스트  ,
)


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
        
        # data
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
        
        # main
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
                    diffs.append(cls(zonename, "평균열관류율", round(before_U,2), round(after_U,2), "W/m2K"))
                
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
                    diffs.append(cls(zonename, "태양열취득계수", round(before_SHGC,3), round(after_SHGC,3), "-"))     
        
        return diffs



class LightDensityDifference(ExcelDifference):
    
    KoreanNAME = "조명"
    
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
                diffs.append(cls(zonename, "교체", before_LPD, after_LPD, "W/m2"))
                
        return diffs
    
class InfiltrationDifference(ExcelDifference):
    
    KoreanNAME = "침기율"
    
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
                diffs.append(cls(zonename, "변화", before_LPD, after_LPD, "ACH50"))
                
        return diffs

class HeatingHVACDifference(ExcelDifference):
    
    KoreanNAME = "난방설비"
    
    @classmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame]
        ) -> list[HeatingHVACDifference]:
        
        # data
        before_supplydict = {
            row["이름"]: row
            for _, row in before["공급설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        after_supplydict = {
            row["이름"]: row
            for _, row in after["공급설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        before_sourcedict = {
            row["이름"]: row
            for _, row in before["생산설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        after_sourcedict = {
            row["이름"]: row
            for _, row in after["생산설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        
        # main
        diffs = []
        for _, row in before["실"].iterrows():
            
            zonename = row["이름"]
            if zonename not in after["실"]["이름"].values:
                continue
            else:
                afterrow = after["실"][after["실"]["이름"] == zonename].iloc[0]
            
            # before 
            if pd.isna(row["난방 공급 설비"]):
                beforeheating = ""
            else:
                beforesupply = before_supplydict[row["난방 공급 설비"]]
                beforesource = before_sourcedict.get(beforesupply["생산설비명"], None)
                
                match beforesupply["유형"]:
                    case "공조기"   :
                        beforeheating = f"공조기&{beforesource["유형"]}: COP {beforesource["난방COP [W/w]"]:.2f}, {beforesource["난방용량 [W]"]*1E-3:.2f}kW"
                    case "팬코일유닛":
                        beforeheating = f"팬코일유닛&{beforesource["유형"]}: 효율 {beforesource["효율 [%]"]:.21}%, {beforesource["난방용량 [W]"]*1E-3:.2f}kW"
                    case "방열기"   :
                        beforeheating = f"방열기&{beforesource["유형"]}: 효율 {beforesource["효율 [%]"]:.21}%, {beforesource["난방용량 [W]"]*1E-3:.2f}kW"
                    case "전기방열기":
                        beforeheating = f"전기방열기: {beforesupply["난방용량 [W]"]*1E-3:.2f}kW"
                    case "바닥난방"  : 
                        beforeheating = f"바닥난방&{beforesource["유형"]}: 효율 {beforesource["효율 [%]"]:.21}%, {beforesource["난방용량 [W]"]*1E-3:.2f}kW"
            
            # after
            if pd.isna(afterrow["난방 공급 설비"]):
                afterheating = ""
            else:
                aftersupply = after_supplydict[afterrow["난방 공급 설비"]]
                aftersource = after_sourcedict.get(aftersupply["생산설비명"], None)
                
                match aftersupply["유형"]:
                    case "공조기"   :
                        afterheating = f"공조기&{aftersource["유형"]}: COP {aftersource["난방COP [W/w]"]:.2f}, {aftersource["난방용량 [W]"]*1E-3:.2f}kW"
                    case "팬코일유닛":
                        afterheating = f"팬코일유닛&{aftersource["유형"]}: 효율 {aftersource["효율 [%]"]:.21}%, {aftersource["난방용량 [W]"]*1E-3:.2f}kW"
                    case "방열기"   :
                        afterheating = f"방열기&{aftersource["유형"]}: 효율 {aftersource["효율 [%]"]:.21}%, {aftersource["난방용량 [W]"]*1E-3:.2f}kW"
                    case "전기방열기":
                        afterheating = f"전기방열기: {aftersupply["난방용량 [W]"]*1E-3:.2f}kW"
                    case "바닥난방"  : 
                        afterheating = f"바닥난방&{aftersource["유형"]}: 효율 {aftersource["효율 [%]"]:.21}%, {aftersource["난방용량 [W]"]*1E-3:.2f}kW"
                
                if beforeheating != afterheating:
                    diffs.append(cls(zonename, "변경", beforeheating, afterheating, "-"))
            
        return diffs
    
class CoolingHVACDifference(ExcelDifference):
    
    KoreanNAME = "냉방설비"
    
    @classmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame]
        ) -> list[CoolingHVACDifference]:
        
        # data
        before_supplydict = {
            row["이름"]: row
            for _, row in before["공급설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        after_supplydict = {
            row["이름"]: row
            for _, row in after["공급설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        before_sourcedict = {
            row["이름"]: row
            for _, row in before["생산설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        after_sourcedict = {
            row["이름"]: row
            for _, row in after["생산설비"].iterrows()
            if not pd.isna(row["이름"])
        }
        
        # main
        diffs = []
        for _, row in before["실"].iterrows():
            
            zonename = row["이름"]
            if zonename not in after["실"]["이름"].values:
                continue
            else:
                afterrow = after["실"][after["실"]["이름"] == zonename].iloc[0]
            
            # before
            if pd.isna(row["냉방 공급 설비"]):
                beforecooling = ""
            else:
                beforesupply = before_supplydict[row["냉방 공급 설비"]]
                beforesource = before_sourcedict.get(beforesupply["생산설비명"], None)
                
                match beforesupply["유형"]:
                    case "패키지에어컨":
                        beforecooling = f"패키지에어컨: COP {beforesupply["냉방COP [W/W]"]:.2f}, {beforesupply["냉방용량 [W]"]*1E-3:.2f}kW"
                    case "공조기"   :
                        beforecooling = f"공조기&{beforesource["유형"]}: COP {beforesource["냉방COP [W/W]"]:.2f}, {beforesource["냉방용량 [W]"]*1E-3:.2f}kW"
                    case "팬코일유닛":
                        beforecooling = f"팬코일유닛&{beforesource["유형"]}: 효율 {beforesource["냉방COP [W/W]"]:.21}%, {beforesource["냉방용량 [W]"]*1E-3:.2f}kW"
            
            # after
            if pd.isna(afterrow["냉방 공급 설비"]):
                aftercooling = ""
            else:
                aftersupply = after_supplydict[afterrow["냉방 공급 설비"]]
                aftersource = after_sourcedict.get(aftersupply["생산설비명"], None)
                
                match aftersupply["유형"]:
                    case "패키지에어컨":
                        beforecooling = f"패키지에어컨: COP {beforesupply["냉방COP [W/W]"]:.2f}, {beforesupply["냉방용량 [W]"]*1E-3:.2f}kW"
                    case "공조기"   :
                        aftercooling = f"공조기&{aftersource["유형"]}: COP {aftersource["냉방COP [W/W]"]:.2f}, {aftersource["냉방용량 [W]"]*1E-3:.2f}kW"
                    case "팬코일유닛":
                        aftercooling = f"팬코일유닛&{aftersource["유형"]}: 효율 {aftersource["냉방COP [W/W]"]:.21}%, {aftersource["냉방용량 [W]"]*1E-3:.2f}kW"
            
            # compare
            if beforecooling != aftercooling:
                diffs.append(cls(zonename, "변경", beforecooling, aftercooling, "-"))
        
        return diffs


# ---------------------------------------------------------------------------- #
#                         OPERATION DIFFERENCE CLASSES                         #
# ---------------------------------------------------------------------------- #

# 어린이집
class ProfileDifferenceKindergarten(ExcelDifference):
    
    KoreanNAME = "프로필변동"
    
    @classmethod
    def compare(cls,
        before: dict[str, pd.DataFrame],
        after : dict[str, pd.DataFrame],
        checklistbefore: 어린이집체크리스트,
        checklistafter : 어린이집체크리스트,
        ) -> list[ProfileDifferenceKindergarten]:
        
        diffs = []
        for _, row in before["실"].iterrows():
            
            zonename = row["이름"]
            if zonename not in after["실"]["이름"].values:
                continue
            else:
                afterrow = after["실"][after["실"]["이름"] == zonename].iloc[0]
            
            if row["현장조사프로필"] != afterrow["현장조사프로필"]:
                diffs.append(cls(zonename, "프로필변경", row["현장조사프로필"], afterrow["현장조사프로필"], "-"))
                
            else:
                match row["현장조사프로필"]:
                    case "일반존":
                        
                        # 재실밀도
                        peoplestr_before = f"평일: {checklistbefore.일반존.기본보육교사+checklistbefore.일반존.기본보육원생}→{checklistbefore.일반존.연장보육A교사+checklistbefore.일반존.연장보육A원생}→{checklistbefore.일반존.연장보육B교사+checklistbefore.일반존.연장보육B원생}→{checklistbefore.일반존.야간보육교사+checklistbefore.일반존.야간보육원생}, 주말: {checklistbefore.일반존.주말보육교사+checklistbefore.일반존.주말보육원생} (명)"
                        peoplestr_after = f"평일: {checklistafter.일반존.기본보육교사+checklistafter.일반존.기본보육원생}→{checklistafter.일반존.연장보육A교사+checklistafter.일반존.연장보육A원생}→{checklistafter.일반존.연장보육B교사+checklistafter.일반존.연장보육B원생}→{checklistafter.일반존.야간보육교사+checklistafter.일반존.야간보육원생}, 주말: {checklistafter.일반존.주말보육교사+checklistafter.일반존.주말보육원생} (명)"
                        if peoplestr_before != peoplestr_after:
                            diffs.append(cls(zonename, "재실인원", peoplestr_before, peoplestr_after, "-"))
                        
                        # 설비 
                        for targethvac in ["난방설비1", "난방설비2", "냉방설비1", "냉방설비2"]:
                            hvac_before = getattr(checklistbefore.특화존1, targethvac)
                            hvac_after = getattr(checklistafter.특화존1, targethvac)
                            
                            if hvac_before is None or hvac_after is None:
                                continue
                            
                            hvacstr_before = f"{hvac_before.사용기간} {hvac_before.사용시간}: {hvac_before.설정온도:.1f}℃"
                            hvacstr_after = f"{hvac_after.사용기간} {hvac_after.사용시간}: {hvac_after.설정온도:.1f}℃"
                            if hvacstr_before != hvacstr_after:
                                diffs.append(cls(zonename, targethvac.replace("설비",""), hvac_before, hvacstr_after, "-"))
                                
                    case "특화존1":
                        
                        # 운영시간
                        operationstr_before = " & ".join(s for s in [checklistbefore.특화존1.오전운영시간, checklistbefore.특화존1.오후운영시간] if s is not None)
                        operationstr_after = " & ".join(s for s in [checklistafter.특화존1.오전운영시간, checklistafter.특화존1.오후운영시간] if s is not None)
                        if operationstr_before != operationstr_after:
                            diffs.append(cls(zonename, "운영시간", operationstr_before, operationstr_after, "-"))
                        
                        # 재실밀도
                        peoplestr_before = f"오전{checklistbefore.특화존1.오전인원}명, 오후{checklistbefore.특화존1.오후인원}명"
                        peoplestr_after = f"오전{checklistafter.특화존1.오전인원}명, 오후{checklistafter.특화존1.오후인원}명"
                        if peoplestr_before != peoplestr_after:
                            diffs.append(cls(zonename, "재실인원", peoplestr_before, peoplestr_after, "-"))
                            
                        # 설비 
                        for targethvac in ["난방설비1", "난방설비2", "냉방설비1", "냉방설비2"]:
                            hvac_before = getattr(checklistbefore.특화존1, targethvac)
                            hvac_after = getattr(checklistafter.특화존1, targethvac)
                            
                            if hvac_before is None or hvac_after is None:
                                continue
                            
                            hvacstr_before = f"{hvac_before.사용기간} {hvac_before.사용시간}: {hvac_before.설정온도:.1f}℃"
                            hvacstr_after = f"{hvac_after.사용기간} {hvac_after.사용시간}: {hvac_after.설정온도:.1f}℃"
                            if hvacstr_before != hvacstr_after:
                                diffs.append(cls(zonename, targethvac.replace("설비",""), hvac_before, hvacstr_after, "-"))
                            
                    case "특화존2":
                        
                        # 운영시간
                        operationstr_before = checklistbefore.특화존2.운영요일.replace(" ","") + " " + " & ".join(s for s in [checklistbefore.특화존2.오전운영시간, checklistbefore.특화존2.오후운영시간] if s is not None)
                        operationstr_after = checklistafter.특화존2.운영요일.replace(" ","") + " " + " & ".join(s for s in [checklistafter.특화존2.오전운영시간, checklistafter.특화존2.오후운영시간] if s is not None)
                        if operationstr_before != operationstr_after:
                            diffs.append(cls(zonename, "운영시간", operationstr_before, operationstr_after, "-"))
                        
                        # 재실밀도
                        peoplestr_before = f"오전{checklistbefore.특화존2.오전인원}명, 오후{checklistbefore.특화존2.오후인원}명"
                        peoplestr_after = f"오전{checklistafter.특화존2.오전인원}명, 오후{checklistafter.특화존2.오후인원}명"
                        if peoplestr_before != peoplestr_after:
                            diffs.append(cls(zonename, "재실인원", peoplestr_before, peoplestr_after, "-"))
                            
                        # 설비 
                        for targethvac in ["난방설비1", "난방설비2", "냉방설비1", "냉방설비2"]:
                            hvac_before = getattr(checklistbefore.특화존2, targethvac)
                            hvac_after = getattr(checklistafter.특화존2, targethvac)
                            
                            if hvac_before is None or hvac_after is None:
                                continue
                            
                            hvacstr_before = f"{hvac_before.사용기간} {hvac_before.사용시간}: {hvac_before.설정온도:.1f}℃"
                            hvacstr_after = f"{hvac_after.사용기간} {hvac_after.사용시간}: {hvac_after.설정온도:.1f}℃"
                            if hvacstr_before != hvacstr_after:
                                diffs.append(cls(zonename, targethvac.replace("설비",""), hvac_before, hvacstr_after, "-"))
        
        return diffs
        
        


# ---------------------------------------------------------------------------- #
#                                 SUBFUNCTIONS                                 #
# ---------------------------------------------------------------------------- #

PERFORMANCE_DIFFLIST = [
    WindowDifference      ,
    LightDensityDifference,
    InfiltrationDifference,
    HeatingHVACDifference ,
    CoolingHVACDifference ,
]

OPERATION_DIFFLIST = {
    "보건소": [
        
    ],
    "어린이집": [
        ProfileDifferenceKindergarten
    ],
}

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
    checklistbefore: 현장조사체크리스트,
    checklistafter : 현장조사체크리스트,
    buildingtype:Literal["보건소","어린이집"],
    ) -> list[ExcelDifference]:
    
    diffs = []
    for diff in OPERATION_DIFFLIST[buildingtype]:
        diffs += diff.compare(
            excelbefore    ,
            excelafter     ,
            checklistbefore,
            checklistafter ,
        )
    
    return diffs

# ---------------------------------------------------------------------------- #
#                                   MAIN FUNC                                  #
# ---------------------------------------------------------------------------- #

def compare_rebexcel(
    excelbeforepath:dict[str, pd.DataFrame],
    excelafterpath :dict[str, pd.DataFrame],
    ) -> tuple[list[ExcelDifference]]:
    
    checklistclass = {"보건소": 보건소체크리스트, "어린이집": 어린이집체크리스트}
    
    # before data
    processedbeforepath = process_excel_file(excelbeforepath, verbose=False)
    excelbefore         = pd.read_excel(processedbeforepath, sheet_name=None)
    os.remove(processedbeforepath)
    
    # after data
    processedafterpath = process_excel_file(excelafterpath, verbose=False)
    excelafter         = pd.read_excel(processedafterpath, sheet_name=None)
    os.remove(processedafterpath)
    
    # checklist data
    buldingtype = excelbefore["현장조사"].iloc[0,0]
    checklistbefore = checklistclass[buldingtype].from_excel(excelbeforepath)
    checklistafter  = checklistclass[buldingtype].from_excel(excelafterpath)
    
    # compare
    performance_differences = compare_performance(excelbefore, excelafter)
    operation_differences   = compare_operation(excelbefore, excelafter, checklistbefore, checklistafter, buldingtype)
    
    performance_differences = pd.DataFrame([diff.to_dict() for diff in performance_differences])
    operation_differences   = pd.DataFrame([diff.to_dict() for diff in operation_differences])
    
    return performance_differences, operation_differences
    