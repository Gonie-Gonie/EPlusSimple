
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
import re
from enum    import Enum
from typing  import Literal
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

# third-party modules

# local modules
from .core import (
    # construction
    Material                ,
    SurfaceConstruction     ,
    FenestrationConstruction,
    # profile
    Profile    ,
    # model
    GreenRetrofitModel,
)
from .utils import (
    excel2grjson,
)
from .debug import (
    debug_excel,
    report_result,
    ReportCode,
    report_to_records,
    merge_report_codes,
)

# ---------------------------------------------------------------------------- #
#                                   MAIN FUNC                                  #
# ---------------------------------------------------------------------------- #


def run_grjson(
    input_filepath :str      ="in.grm",
    output_filepath:str|None =None    ,
    *,
    save           :bool     =True    ,
    ) -> str|dict:
    
    """ run grjson input file and write result
    
    Args
    ----
    input_filepath (str, default="in.grm")
        * not need to have 'grm' extension
    output_filepath (str|None, defulat=None)
        * where to save the result
        * automatically defined using input_filepath if given None
    save (bool, default=True)
        * if True, save the result to output_filepath
        * else return the dictionarized data
    
    """
    
    # set default output filepath
    if output_filepath is None:
        input_path = Path(input_filepath)
        if input_path.suffix == "":
            output_filepath = str(input_path) + ".grr"
        else:
            output_filepath = str(input_path.with_suffix(".grr"))
     
    # read input file
    grm = GreenRetrofitModel.from_grjson(input_filepath)
    
    # run model
    grr = grm.run()
    
    # write the result if required
    if save:
        grr.write(output_filepath)
        return output_filepath
    
    # else return the dictionarized data
    else:
        return grr.to_dict()

def run_grexcel(
    input_filepath :str|None=None,
    output_filepath:str|None=None,
    *,
    save           :bool    =True,
    ) -> str|dict:
    
    """ run grexcel input file and write result
    * note: this function has the identital structure with the 'run_grjson' func
    
    Args
    ----
    input_filepath (str, default="in.xlsx")
        * not need to have 'xlsx' extension
    output_filepath (str|None, defulat=None)
        * where to save the result
        * automatically defined using input_filepath if given None
    save (bool, default=True)
        * if True, save the result to output_filepath
        * else return the dictionarized data
    
    """
    
    # set default input filepath
    if input_filepath is None:
        input_filepath = "in.xlsx"
    
    # convert grexcel into the grjson
    _, grjson_filepath = excel2grjson(input_filepath)
    
    # try to run grjson
    try:
        output_filepath = run_grjson(grjson_filepath, output_filepath, save=save)
        return output_filepath
    
    # and remove the temporal grjson file
    finally:
        os.remove(grjson_filepath)
    
def get_database(
    datatype:Literal[
        "profile"     ,
        "material"                 ,
        "surface_construction"     ,
        "fenestration_construction",
    ],
    key     :str,
    *,
    as_dict:bool=False
    ) -> dict|Profile|Material|SurfaceConstruction|FenestrationConstruction:
    
    """ get item from the specific database

    Args
    ----
    datatype (str)
        * type(name) of the database
        * one of ["day_schedule","ruleset","schedule","profile","material","surface_construction","fenestration_construction"]
    key (str)
        * profile, material: name of the item
        * (surface, fenestration) construction: options concatted by '&'
        *                                       or special keys: '__path__', '__all__'
    as_dict (bool, default=False)
        * if True, return item in a dictionary form (else return item itself)
        * set as True if the result need to be printed (for GUI, ...)
    
    Returns
    -------
    item(s) or dictionarized item(s)
    
    Examples
    --------
    >>> get_database("material", "concrete")
    <Material concrete (ID=$DB$:concrete) at 0x260cbfa2960>
    
    >>> get_database("material", "concrete", as_dict=True)
    {'name': 'concrete', 'conductivity': 2.5, 'density': 2400, 'specific_heat': 880}
    
    >>> get_database("fenestration_construction", "단창&하드코팅&미주입&적용&금속재&6mm", as_dict=True)
    {'name': '단창&하드코팅&미주입&적용&금속재&6mm', 'U-value': 6.1, 'SHGC': 0.717}
    
    >>> get_database("fenestration_construction", "__path__", as_dict=True)
    '.../_data/construction/fenestration_regulation_surface.csv'
    
    """
    
    match datatype:       
        case "profile":
            return Profile.get_DB(key, as_dict=as_dict)
        
        case "material":
            return Material.get_DB(key, as_dict=as_dict)
        
        case "surface_construction":
            
            # if not special key, decompose the keys
            if key not in ["__path__","__all__"]:
                key = tuple(key.split("&"))
            
            return SurfaceConstruction.get_DB(key, as_dict=as_dict)
        
        case "fenestration_construction":
            
            # if not special key, decompose the keys
            if key not in ["__path__","__all__"]:
                key = tuple(key.split("&"))
                
            return FenestrationConstruction.get_DB(key, as_dict=as_dict)
        
        case _:
            raise KeyError(
                f"{datatype} is not a valid database type"             ,
                f"(Expected 'day_scheduel', 'ruleset', 'schedule', 'profile', 'material', 'surface_construction' or 'fenestration_construction').",
            )
    
    return



class GreenRetrofitDataFormat(str, Enum):
    EXCEL = ("excel", "xlsx", ("json", "idf"))
    JSON  = ("json" , "grm" , ("idf",))
    IDF   = ("idf"  , "idf" , ())

    def __new__(cls,
        value    :str,
        extension:str,
        convertibles: tuple[str, ...]
        ) -> GreenRetrofitDataFormat:  
        
        # 
        obj = str.__new__(cls, value) 
        obj._value_ = value            
        
        # properties
        obj.extension    = extension
        obj.convertibles = tuple(convertibles)  
        
        return obj

def convert_inputformat(
    input_filepath: str,
    src: GreenRetrofitDataFormat,
    dst: GreenRetrofitDataFormat,
    *,
    output_filepath:str|None = None
) -> None:
    """ convert input file from src format to dst format
    
    Args
    ----
    input_filepath (str)
        * path to the input file
    src (GreenRetrofitDataFormat)
        * format of the input file
    dst (GreenRetrofitDataFormat)
        * format of the output file
    output_filepath (str|None, defulat=None)
        * where to save the result
        * automatically defined using input_filepath with changed extension if given None
    """
    
    # convert format to enum
    src = GreenRetrofitDataFormat(src)
    dst = GreenRetrofitDataFormat(dst)
    
    # inspect convertibility
    if dst.value not in src.convertibles:
        available = ",".join(src.convertibles)
        raise ValueError(
            f"{src.value} is not convertible to {dst.value} (available: {available})."
        )
        
    # default output filepath: same as input
    if output_filepath is None:
        if input_filepath.endswith(f".{src.extension}"):
            output_filepath = input_filepath.replace(src.extension, dst.extension)
        else:
            output_filepath = f"{input_filepath}.{dst.extension}"
    
    # main
    match (src, dst):
        
        case (GreenRetrofitDataFormat.EXCEL, GreenRetrofitDataFormat.JSON): 
            _ = excel2grjson(input_filepath, output_filepath)
            return
            
        case (GreenRetrofitDataFormat.EXCEL, GreenRetrofitDataFormat.IDF): 
            grm = GreenRetrofitModel.from_excel(input_filepath)
            idf = grm.to_idf()
            idf.write(output_filepath)
            return
        
        case (GreenRetrofitDataFormat.JSON, GreenRetrofitDataFormat.IDF): 
            grm = GreenRetrofitModel.from_grjson(input_filepath)
            idf = grm.to_idf()
            idf.write(output_filepath)
            return


def _debug_one_excel(filepath: str) -> tuple[dict, ReportCode]:
    """
    multiprocessing에서 호출하기 위한 단일 파일 debug 함수.
    Windows에서는 top-level 함수여야 합니다.
    """
    exceptions, warnings = debug_excel(filepath)
    code, report = report_result(exceptions, warnings)

    records = report_to_records(report)

    file_report = {
        "filename": os.path.basename(filepath),
        "filepath": filepath,
        "code": code.name,
        "report": records,
    }

    return file_report, code

def debug(
    input_filepath: str | list[str] | tuple[str, ...],
    *,
    workers: int = 1,
) -> dict:
    """
    Excel input file을 디버그하고 결과를 dict로 반환합니다.

    Args
    ----
    input_filepath
        단일 Excel 파일 경로 또는 Excel 파일 경로 list.
    workers
        병렬 실행 worker 수.
        1 이하이면 순차 실행.

    Returns
    -------
    dict
        {
            "code": "CLEAR" | "WARNING" | "SEVERE",
            "report": list[dict],
            "files": list[dict],
        }
    """

    # normalize input
    if isinstance(input_filepath, str):
        input_filepaths = [input_filepath]
    else:
        input_filepaths = list(input_filepath)

    if len(input_filepaths) == 0:
        raise ValueError("input_filepath is empty.")

    # debug each file
    if workers is None or workers <= 1 or len(input_filepaths) == 1:
        results = [
            _debug_one_excel(filepath)
            for filepath in input_filepaths
        ]
    else:
        num_workers = min(workers, len(input_filepaths))

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(_debug_one_excel, input_filepaths))

    file_reports = []
    codes = []

    for file_report, code in results:
        file_reports.append(file_report)
        codes.append(code)

    # merge file-level codes
    final_code = merge_report_codes(codes)

    # make a flat report for launcher table
    merged_report = []

    for file_report in file_reports:
        for row in file_report["report"]:
            merged_row = {"file": file_report["filename"]}
            merged_row.update(row)
            merged_report.append(merged_row)

    return {
        "code": final_code.name,
        "report": merged_report,
        "files": file_reports,
    }