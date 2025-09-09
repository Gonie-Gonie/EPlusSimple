
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import json
from types import SimpleNamespace
from enum import (
    Enum,
    auto,
)
from abc import (
    ABC,
    abstractmethod
)
from typing import Any

# third-party modules
import pandas as pd

# local modules


# ---------------------------------------------------------------------------- #
#                                JSON EXCEPTIONS                               #
# ---------------------------------------------------------------------------- #

class JsonException(Exception, ABC):
    
    def __init__(self,
        class_name :str,
        object_name:str,
        *,
        subcategory:str|None=None,
        ) -> None:
        
        self.sheet_name  = class_name
        self.object_name = object_name
        self.subcategory = subcategory

        return

    @staticmethod
    @abstractmethod
    def inspect(jsondata:SimpleNamespace) -> list[ExcelException]: ...

    def to_dict(self) -> dict[str,str]:
        
        return {
            "importance" : "ERROR",
            "category"   : type(self).__name__,
            "subcategory": self.subcategory.value if self.subcategory is not None else 0   ,
            "type"       : self.sheet_name    ,
            "object"     : self.object_name   ,
            "message"    : self.message       ,
        }

# ---------------------------------------------------------------------------- #
#                               EXCEL EXCEPTIONS                               #
# ---------------------------------------------------------------------------- #

class ExcelException(Exception, ABC):
    
    def __init__(self,
        sheet_name :str,
        object_name:str,
        *,
        subcategory:str|None=None,
        ) -> None:
        
        self.sheet_name  = sheet_name
        self.object_name = object_name
        self.subcategory = subcategory

        return
    
    @staticmethod
    @abstractmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[ExcelException]: ...
    
    def to_dict(self) -> dict[str,str]:
        
        return {
            "importance" : "ERROR",
            "category"   : type(self).__name__,
            "subcategory": self.subcategory.value if self.subcategory is not None else 0   ,
            "type"       : self.sheet_name    ,
            "object"     : self.object_name   ,
            "message"    : self.message       ,
        }


class InSufficientSurfaceForZoneSubCategory(str, Enum):
    
    NO_FLOOR   = auto()
    NO_CEILING = auto()
    NO_WALL    = auto()

class InsufficientSurfaceForZone(ExcelException):
    
    def __init__(self,
        subcategory:InSufficientSurfaceForZoneSubCategory,
        object_name:str,
        ) -> None:
        
        super().__init__("면", object_name, subcategory=subcategory)
        match subcategory:
            case InSufficientSurfaceForZoneSubCategory.NO_FLOOR:
                self.message = f"실 '{object_name}'에 바닥면이 없습니다."
            case InSufficientSurfaceForZoneSubCategory.NO_CEILING:
                self.message = f"실 '{object_name}'에 천장면이 없습니다."
            case InSufficientSurfaceForZoneSubCategory.NO_WALL:
                self.message = f"실 '{object_name}'에 벽체가 없습니다."
    
    @staticmethod
    def inspect_floor(zonename:str, floor_sheet:pd.DataFrame, ceiling_sheet:pd.DataFrame):
        
        if (zonename not in floor_sheet["소속 실"].values) and (zonename not in ceiling_sheet["인접존 이름"].values):
            return InsufficientSurfaceForZone(
                InSufficientSurfaceForZoneSubCategory.NO_FLOOR,
                zonename,
            )
        
        else:
            return
        
    @staticmethod
    def inspect_ceiling(zonename:str, ceiling_sheet:pd.DataFrame, floor_sheet:pd.DataFrame):
        
        if (zonename not in ceiling_sheet["소속 실"].values) and (zonename not in floor_sheet["인접존 이름"].values):
            return InsufficientSurfaceForZone(
                InSufficientSurfaceForZoneSubCategory.NO_CEILING,
                zonename,
            )
        
        else:
            return
    
    @staticmethod
    def inspect_wall(zonename:str, wall_sheet:pd.DataFrame):
        
        if (zonename not in wall_sheet["소속 실"].values) and (zonename not in wall_sheet["인접존 이름"].values):
            return InsufficientSurfaceForZone(
                InSufficientSurfaceForZoneSubCategory.NO_WALL,
                zonename,
            )
        
        else:
            return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[InsufficientSurfaceForZone]:
        
        # for reference
        floors   = exceldata["면"].loc[~pd.isna(exceldata["면"]["이름"])].query("유형 == 'floor'")
        ceilings = exceldata["면"].loc[~pd.isna(exceldata["면"]["이름"])].query("유형 == 'ceiling'")
        walls    = exceldata["면"].loc[~pd.isna(exceldata["면"]["이름"])].query("유형 == 'wall'")
        
        exceptions = []
        for _, row in exceldata["실"].iterrows():
            
            # skip for empty row
            if pd.isna(row["이름"]):
                break
            
            # inspect for each part
            exception_floor   = InsufficientSurfaceForZone.inspect_floor(row["이름"], floors, ceilings)
            exception_ceiling = InsufficientSurfaceForZone.inspect_ceiling(row["이름"], ceilings, floors)
            exception_wall    = InsufficientSurfaceForZone.inspect_wall(row["이름"], walls)
            
            # append to the exception lists
            exceptions += [
                exception for exception
                in [exception_floor, exception_ceiling, exception_wall]
                if isinstance(exception, InsufficientSurfaceForZone)
            ]
            
        return exceptions
    

class InvalidFenestrationConstructionSubCategory(str, Enum):
    
    INVALID_CONSTRUCTION_NAME      = auto()
    TRANSPARENT_FOR_DOOR           = auto()
    OPAQUE_FOR_WINDOW_OR_GLASSDOOR = auto()

class InvalidFenestrationConstruction(ExcelException):
    
    def __init__(self,
        subcategory:InvalidFenestrationConstructionSubCategory,
        object_name      :str,
        fenestration_type:str,
        construction_name:str,
        ) -> None:
        
        super().__init__("개구부", object_name, subcategory=subcategory)
        
        match subcategory:
            
            case InvalidFenestrationConstructionSubCategory.INVALID_CONSTRUCTION_NAME:
                self.message = f"개구부 '{object_name}'의 구조체로 입력된 '{construction_name}'는 존재하지 않는 구조체입니다."
            
            case InvalidFenestrationConstructionSubCategory.TRANSPARENT_FOR_DOOR:
                self.message = f"'{fenestration_type}'유형 개구부 '{object_name}'은/는 투명한 구조체 '{construction_name}'를 사용할 수 없습니다."
                
            case InvalidFenestrationConstructionSubCategory.OPAQUE_FOR_WINDOW_OR_GLASSDOOR:
                self.message = f"'{fenestration_type}'유형 개구부 '{object_name}'은/는 불투명한 구조체 '{construction_name}'를 사용할 수 없습니다."
        
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[InsufficientSurfaceForZone]: 
        
        # for the reference
        fenestration_construction = exceldata["구조체_개구부"].set_index("이름")
        
        # check
        exceptions = []
        for _, row in exceldata["개구부"].iterrows():
            
            # 그냥 존재하지도 않는 경우
            if row["구조체 이름"] not in fenestration_construction.index:
                exceptions.append(
                    InvalidFenestrationConstruction(
                        InvalidFenestrationConstructionSubCategory.INVALID_CONSTRUCTION_NAME,
                        row["이름"],
                        row["유형"],
                        row["구조체 이름"],
                    )
                )
                continue
            
            # 존재하면 검사
            match row["유형"]:
                
                case "window"|"glassdoor":
                    if fenestration_construction.loc[row["구조체 이름"], "투명여부"] == "불투명":
                        exceptions.append(
                            InvalidFenestrationConstruction(
                                InvalidFenestrationConstructionSubCategory.OPAQUE_FOR_WINDOW_OR_GLASSDOOR,
                                row["이름"],
                                row["유형"],
                                row["구조체 이름"],
                            )
                        )
                
                case "door":
                    if fenestration_construction.loc[row["구조체 이름"], "투명여부"] == "투명":
                        exceptions.append(
                            InvalidFenestrationConstruction(
                                InvalidFenestrationConstructionSubCategory.TRANSPARENT_FOR_DOOR,
                                row["이름"],
                                row["유형"],
                                row["구조체 이름"],
                            )
                        )
                        
        return exceptions
    
    
    
class InvalidSurfaceConstructionSubCategory(str, Enum):
    
    INVALID_CONSTRUCTION_NAME      = auto()
    
class InvalidSurfaceConstruction(ExcelException):
    
    def __init__(self,
        subcategory:InvalidFenestrationConstructionSubCategory,
        object_name      :str,
        fenestration_type:str,
        construction_name:str,
        ) -> None:
        
        super().__init__("면", object_name, subcategory=subcategory)
        match subcategory:
            
            case InvalidSurfaceConstructionSubCategory.INVALID_CONSTRUCTION_NAME:
                self.message = f"면 '{object_name}'의 구조체로 입력된 '{construction_name}'는 존재하지 않는 구조체입니다."
            
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[InsufficientSurfaceForZone]: 
        
        # for the reference
        surface_construction = exceldata["구조체_면"].set_index("이름")
        
        # check
        exceptions = []
        for _, row in exceldata["면"].iterrows():
            
            # skip empty row
            if pd.isna(row["이름"]):
                break
            
            # check
            if (not pd.isna(row["구조체 이름"]) and (row["구조체 이름"] not in surface_construction.index)):
                exceptions.append(
                    InvalidSurfaceConstruction(
                        InvalidSurfaceConstructionSubCategory.INVALID_CONSTRUCTION_NAME,
                        row["이름"],
                        row["유형"],
                        row["구조체 이름"],
                    )
                )
                continue
            
                # 또 에러날 이유 있으면 subcategory 추가하고 검사
        
        return exceptions
    

class BlindForNonOutdoorWindow(ExcelException):
    
    def __init__(self,
        object_name :str,
        surface_name:str,
        ) -> None:
        
        super().__init__("개구부", object_name)
        self.message = f"경계조건이 'outdoors'가 아닌 면 '{surface_name}'에 소속된 개구부 '{object_name}'의 블라인드는 False 이어야 합니다."

    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[BlindForNonOutdoorWindow]:
        
        # for the reference
        interzone_surfaces = exceldata["면"].query("경계조건 != 'outdoors'")["이름"].tolist()
        
        exceptions = []
        for _, row in exceldata["개구부"].iterrows():
            
            if (row["소속 면"] in interzone_surfaces) and (row["블라인드"] != 0.0):
                exceptions.append(
                    BlindForNonOutdoorWindow(
                        row["이름"],
                        row["소속 면"],
                    )
                )
        
        return exceptions


class InsufficientMaterialDefinition(ExcelException):
    
    def __init__(self, 
        object_name   :str      ,
        property_names:list[str],
        ) -> None:
        
        super().__init__("재료", object_name)
        self.message = f"재료 '{object_name}'의 {','.join(property_names)}가 정의되지 않았습니다."
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[InsufficientMaterialDefinition]:
    
        exceptions = []
        for _, row in exceldata["재료"].iterrows():
            
            # skip empty row
            if pd.isna(row["이름"]):
                break
            
            if bool(pd.isna(row.iloc[1:4]).any()):
                exceptions.append(
                    InsufficientMaterialDefinition(
                        row["이름"],
                        list(row.index[1:4][pd.isna(row.iloc[1:4]).values]),
                    )
                )
            
        return exceptions
    
class InvalidAdjacentZoneName(ExcelException):
    
    def __init__(self, object_name:str, inputted_adjacent_zone_name:str) -> None:
        
        super().__init__("면", object_name)
        self.message = f"면 '{self.object_name}'의 인접존으로 입력된 '{inputted_adjacent_zone_name}'은 존재하지 않는 존 이름입니다."
        
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[InvalidAdjacentZoneName]: 
        
        # for the reference
        existing_zones = exceldata["실"]["이름"].to_list()
        
        # check
        exceptions = []
        for _, row in exceldata["면"].iterrows():
            
            if not pd.isna(row["인접존 이름"]) and row["인접존 이름"] not in existing_zones:
                exceptions.append(
                    InvalidAdjacentZoneName(
                        row["이름"],
                        row["인접존 이름"]
                    )
                )
        
        return exceptions
    
class InvalidSourceSystemName(ExcelException):
    
    def __init__(self, object_name:str, inputted_sourcesystem_name:str) -> None:
        
        super().__init__("공급설비", object_name)
        self.message = f"공급설비 '{self.object_name}'의 생산설비명으로 입력된 '{inputted_sourcesystem_name}'은 존재하지 않는 생산설비 이름입니다."
        
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[InvalidSourceSystemName]: 
        
        # for the reference
        existing_sources = exceldata["생산설비"]["이름"].to_list()
        
        # check
        exceptions = []
        for _, row in exceldata["공급설비"].iterrows():
            
            if not pd.isna(row["생산설비명"]) and row["생산설비명"] not in existing_sources:
                exceptions.append(
                    InvalidSourceSystemName(
                        row["이름"],
                        row["생산설비명"]
                    )
                )
        
        return exceptions

class DuplicatedName(ExcelException):
    
    def __init__(self,
        sheet_name :str,
        object_name:str,
        ) -> None:
        
        super().__init__(sheet_name, object_name)
        self.message = f"중복된 '{object_name}' 이름이 {sheet_name}에 사용되었습니다."
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[DuplicatedName]: 
        
        exceptions = []
        for sheet_name, df in exceldata.items():
            
            if "이름" not in df.columns:
                continue
            
            name_count = df["이름"].value_counts()
            for duplicated_name in name_count[name_count > 1].index:
                
                exceptions.append(
                    DuplicatedName(sheet_name, duplicated_name)
                )
        
        return exceptions

# ---------------------------------------------------------------------------- #
#                                 JSON WARNINGS                                #
# ---------------------------------------------------------------------------- #

class JsonWarning(UserWarning, ABC):
    
    def __init__(self,
        class_name :str,
        object_name:str,
        *,
        subcategory:str|None=None,
        ) -> None:
        
        self.sheet_name  = class_name
        self.object_name = object_name
        self.subcategory = subcategory

        return
    
    @staticmethod
    @abstractmethod
    def inspect(jsondata:SimpleNamespace) -> list[JsonWarning]: ...

    def to_dict(self) -> dict[str,str]:
        
        return {
            "importance" : "WARNING",
            "category"   : type(self).__name__,
            "subcategory": self.subcategory.value if self.subcategory is not None else 0,
            "type"       : self.sheet_name    ,
            "object"     : self.object_name   ,
            "message"    : self.message       ,
        }

# ---------------------------------------------------------------------------- #
#                                EXCEL WARNINGS                                #
# ---------------------------------------------------------------------------- #

class ExcelWarning(UserWarning, ABC):
    
    def __init__(self,
        sheet_name :str,
        object_name:str,
        *,
        subcategory:str|None=None,
        ) -> None:
        
        self.sheet_name  = sheet_name
        self.object_name = object_name
        self.subcategory = subcategory

        return
    
    @staticmethod
    @abstractmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[ExcelWarning]: ...

    def to_dict(self) -> dict[str,str]:
        
        return {
            "importance" : "WARNING",
            "category"   : type(self).__name__   ,
            "subcategory": self.subcategory.value if self.subcategory is not None else 0,
            "type"       : self.sheet_name       ,
            "object"     : self.object_name      ,
            "message"    : self.message          ,
        }

class NotUsedSupplySystem(ExcelWarning):
    
    def __init__(self, object_name:str) -> None:
        
        # superclass properties
        super().__init__("공급설비", object_name)
        
        # class-specific properties
        self.message = f"공급설비 '{self.object_name}'은/는 어느 존에서도 사용되지 않습니다."
        
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[NotUsedSupplySystem]:
        
        # for the reference
        used_supply_systems = set(exceldata["실"][["난방 공급 설비", "난방 공급 설비2", "냉방 공급 설비"]].values.flatten().tolist())
        used_supply_systems = [item for item in used_supply_systems if not pd.isna(item)]
        
        # check
        warnings = []
        for _, row in exceldata["공급설비"].iterrows():
            
            if not pd.isna(row["이름"]) and (row["이름"] not in used_supply_systems):
                warnings.append(
                    NotUsedSupplySystem(
                        row["이름"]
                    )
                )
        
        return warnings
    
    
class NotUsedSourceSystem(ExcelWarning):
    
    def __init__(self, object_name:str) -> None:
        
        super().__init__("생산설비", object_name)
        self.message = f"생산설비 '{self.object_name}'은/는 어느 공급설비에서도 사용되지 않습니다."
        
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[NotUsedSupplySystem]:
        
        # for the reference
        used_source_systems = set(exceldata["공급설비"]["생산설비명"].to_list())
        used_source_systems = [item for item in used_source_systems if not pd.isna(item)]
        
        # check
        warnings = []
        for _, row in exceldata["생산설비"].iterrows():
            
            if (row["이름"] not in used_source_systems) and (row["급탕용"] == 0.0):
                warnings.append(
                    NotUsedSupplySystem(
                        row["이름"]
                    )
                )
        
        return warnings

class NotUsedSurfaceConstruction(ExcelWarning):
    
    def __init__(self, object_name:str) -> None:
        
        super().__init__("구조체_면", object_name)
        self.message = f"구조체 '{self.object_name}'은/는 어느 면에서도 사용되지 않습니다."
        
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[NotUsedSupplySystem]:
        
        # for the reference
        used_constructions = set(exceldata["면"]["구조체 이름"].to_list())
        used_constructions = [item for item in used_constructions if not pd.isna(item)]
        
        # check
        warnings = []
        for _, row in exceldata["구조체_면"].iterrows():
            
            # skip empty rows
            if pd.isna(row["이름"]):
                break
            
            # check
            if row["이름"] not in used_constructions:
                warnings.append(
                    NotUsedSurfaceConstruction(
                        row["이름"]
                    )
                )
        
        return warnings
    
class NoHVACSystemAppliedSubCategory(str, Enum):
    
    NoCoolingSupply  = auto()
    NoHeatingSupply  = auto()
    NoHotwaterSource = auto()   

class NoHVACSystemApplied(ExcelWarning):
    
    def __init__(self, subcategory:NoHVACSystemAppliedSubCategory) -> None:
        
        # superclass properties
        match subcategory:
            
            case NoHVACSystemAppliedSubCategory.NoCoolingSupply:
                super().__init__("공급설비", None, subcategory=subcategory)
                self.message = f"어떠한 존에도 냉방용 공급설비가 입력되지 않아 냉방에너지가 계산되지 않습니다."
            
            case NoHVACSystemAppliedSubCategory.NoHeatingSupply:
                super().__init__("공급설비", None, subcategory=subcategory)
                self.message = f"어떠한 존에도 난방용 공급설비가 입력되지 않아 난방에너지가 계산되지 않습니다."
            
            case NoHVACSystemAppliedSubCategory.NoHotwaterSource:
                super().__init__("생산설비", None, subcategory=subcategory)
                self.message = f"급탕용 설비가 입력되지 않아 효율 85%의 가스보일러로 가정됩니다."
        
        return
    
    @staticmethod
    def inspect(exceldata:dict[str, pd.DataFrame]) -> list[NoHVACSystemApplied]:
        
        exceptions = []
        
        # heating
        if pd.isna(exceldata["실"]["난방 공급 설비"]).all():
            exceptions.append(
                NoHVACSystemApplied(
                    NoHVACSystemAppliedSubCategory.NoHeatingSupply
                )
            )
            
        # cooling
        if pd.isna(exceldata["실"]["냉방 공급 설비"]).all():
            exceptions.append(
                NoHVACSystemApplied(
                    NoHVACSystemAppliedSubCategory.NoCoolingSupply
                )
            )
        
        # hotwater
        if not (exceldata["생산설비"]["급탕용"] == 1.0).any():
            exceptions.append(
                NoHVACSystemApplied(
                    NoHVACSystemAppliedSubCategory.NoHotwaterSource
                )
            )
            
        return exceptions

# ---------------------------------------------------------------------------- #
#                                DEBUG FUNCTIONS                               #
# ---------------------------------------------------------------------------- #


EXCEL_INSPECTORS = [
    # exceptions
    InvalidAdjacentZoneName,
    InvalidSourceSystemName,
    InvalidSurfaceConstruction,
    InvalidFenestrationConstruction,
    InsufficientSurfaceForZone,
    BlindForNonOutdoorWindow,
    InsufficientMaterialDefinition,
    DuplicatedName,
    # warnings
    NotUsedSupplySystem,
    NotUsedSourceSystem,
    NotUsedSurfaceConstruction,
    NoHVACSystemApplied,
]

JSON_INSPECTORS = [
    
]

def debug_excel(filepath:str) -> list[ExcelException]:
    
    exceldata = pd.read_excel(filepath, sheet_name=None)

    exceptions = []
    warnings   = []
    
    for inspector in EXCEL_INSPECTORS:
        
        # check
        inspect_result = inspector.inspect(exceldata)
        # errors
        if issubclass(inspector, ExcelException):
            exceptions += inspect_result
        # and warnings
        if issubclass(inspector, ExcelWarning):
            warnings += inspect_result
    
    return exceptions, warnings


def debug_json(filepath:str) -> list[ExcelException]:
    
    with open(filepath, encoding="UTF-8") as f:
        exceldata = json.load(f, object_hook=lambda d: SimpleNamespace(**d))

    exceptions = []
    warnings   = []
    
    for inspector in JSON_INSPECTORS:
        
        # check
        inspect_result = inspector.inspect(exceldata)
        # errors
        if issubclass(inspector, ExcelException):
            exceptions += inspect_result
        # and warnings
        if issubclass(inspector, ExcelWarning):
            exeptions += inspect_result
    
    return exceptions, warnings


class ReportCode(Enum):
    
    CLEAR   = auto()
    WARNING = auto()
    SEVERE  = auto()
    
    
def report_result(exceptions:list[Exception], warnings:list[UserWarning]) -> tuple[ReportCode, pd.DataFrame]:
    
    if len(exceptions) >= 1:
        code = ReportCode.SEVERE
    elif len(warnings) >= 1:
        code = ReportCode.WARNING
    else:
        code = ReportCode.CLEAR
        
    if code is not ReportCode.CLEAR:
        report = pd.DataFrame(
            [exception.to_dict() for exception in exceptions] +\
            [warning.to_dict()   for warning   in warnings  ]
        )
        
    else:
        report = pd.DataFrame(columns = ["importance", "category", "subcategory", "type", "object", "message"])
        
    return code, report