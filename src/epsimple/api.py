
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
import re
from enum import Enum
from typing import Literal

# third-party modules

# local modules
from .core import (
    # construction
    Material                ,
    SurfaceConstruction     ,
    FenestrationConstruction,
    # profile
    DaySchedule,
    RuleSet    ,
    Schedule   ,
    Profile    ,
    # model
    GreenRetrofitModel,
)
from .utils import (
    excel2grjson,
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
        output_filepath = re.sub(r"(\.\w+?)$",rf".grr",input_filepath)
     
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
    ) -> str:
    
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
        "day_schedule",
        "ruleset"     ,
        "schedule"    ,
        "profile"     ,
        "material"                 ,
        "surface_construction"     ,
        "fenestration_construction",
    ],
    key     :str,
    *,
    as_dict:bool=False
    ) -> dict|DaySchedule|RuleSet|Schedule|Profile|Material|SurfaceConstruction|FenestrationConstruction:
    
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
        case "day_schedule":
            return DaySchedule.get_DB(key, as_dict=as_dict)
        
        case "ruleset":
            return RuleSet.get_DB(key, as_dict=as_dict)
        
        case "schedule":
            return Schedule.get_DB(key, as_dict=as_dict)
        
        case "profile":
            return Profile.get_DB(key, as_dict=as_dict)
        
        case "material":
            return Material.get_DB(key, as_dict=as_dict)
        
        case "surface_construction":
            
            # if not special key, decompose the keys
            if key not in ["__path__","__all__"]:
                key = tuple(key.split("&"))
            
            return SurfaceConstruction.get_DB(key, as_dict=True)
        
        case "fenestration_construction":
            
            # if not special key, decompose the keys
            if key not in ["__path__","__all__"]:
                key = tuple(key.split("&"))
                
            return FenestrationConstruction.get_DB(key, as_dict=True)
        
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
    