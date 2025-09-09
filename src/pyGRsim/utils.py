
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os
import sys
import json
import warnings
import importlib
import subprocess
from uuid     import uuid4
from copy     import deepcopy
from pathlib  import Path
from datetime import datetime
from openpyxl import load_workbook
from typing   import (
    Any     ,
    List    ,
    Optional,
)

# third-party modules
import pandas as pd

# local modules
from .constants import Unit

# ---------------------------------------------------------------------------- #
#                              PACKAGE MANAGEMENT                              #
# ---------------------------------------------------------------------------- #

def check_modules(modules:list[str]):
    
    # check if all required modules are importable
    missing_module = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except ImportError:
                missing_module.append(mod)
    
    # if missing module exists,
    if missing_module:
        
        # check if the user want to install the modules
        print(
            f"Required but uninstalled modules: {', '.join(missing_module)}"
        )
        want_import = input("Do you want to install the modules? [Y/N]")
        
        if want_import == "Y":
            
            # install missing modules and check failures
            failed_module = [] 
            for mod in missing_module:
                result = subprocess.run([sys.executable, "-m", "pip", "install", mod])
                if result.returncode != 0:
                    failed_module.append(mod)
            
            # if failed module exists,
            # return error code (1)
            if failed_module:
                print(f"Failed to install: {', '.join(failed_module)}")
                return 1, failed_module
            
            # else (successed insalling all required moduels),
            # return normal code (0)
            else:
                return 0, []
        
        # if user do not want to install module automatically,
        # return error code (1)
        else:
            return 1, missing_module
    
    # if there's no missing module,
    # return normal code (0)
    else:
        return 0, []

# ---------------------------------------------------------------------------- #
#                             EXCEL GUI: VARIABLES                             #
# ---------------------------------------------------------------------------- #

VALID_COLUMNS = {
    "건물정보"     : ["건물명", "north_axis [°]","주소","지상층수","지하층수","허가일자"],
    "실"           : ["이름","층","천정고 [m]", "용도프로필","조명밀도 [W/m2]", "침기율 [ACH@50]","난방 공급 설비","냉방 공급 설비", "환기 설비"],
    "면"           : ["이름","소속 실","유형","경계조건","면적 [m2]","향 [°]","인접존 이름","구조체 이름", "쿨루프 반사율 [%]"],
    "개구부"       : ["이름","소속 면","유형","면적 [m2]","구조체 이름", "블라인드"],
    "구조체_면"    : ["이름","레이어1_재료","레이어1_두께 [mm]","레이어2_재료","레이어2_두께 [mm]","레이어3_재료","레이어3_두께 [mm]","레이어4_재료","레이어4_두께 [mm]","레이어5_재료","레이어5_두께 [mm]"],
    "구조체_개구부": ["이름","투명여부","열관류율 [W/m2·K]","태양열취득계수"],
    "재료"         : ["이름","열전도율 [W/m·K]", "밀도 [kg/m3]","비열 [J/kg·K]"],
    "공급설비"     : ["이름","유형","냉방용량 [W]","난방용량 [W]","냉방COP [W/W]","생산설비명"],
    "생산설비"     : ["이름","유형","냉방용량 [W]","난방용량 [W]","냉방COP [W/W]","난방COP [W/W]","효율 [%]","급탕용","연료종류", "압축기 종류", "냉각탑 종류","냉각탑 용량 [W]", "냉각탑 제어방식", "연동보일러 효율 [%]"],
    "환기설비"     : ["이름", "난방효율 [%]", "냉방효율 [%]"],
    "PV패널"      : ["이름","면적","효율 [%]","방위각 [°]","경사각 [°]"],
}

ID_PREFIX = {
    "실"           :"ZONE",
    "면"           :"SURF",
    "개구부"       :"FNST",
    "구조체_면"    :"CTSF",
    "구조체_개구부":"CTFN",
    "재료"         :"MTRL",
    "공급설비"     :"SUPL",
    "생산설비"     :"SRCE",
    "환기설비"     :"ERVT",
    "PV패널"       :"PVPN",
}

COLUMN_RENAME_DICT = {
    # 건물정보
    "건물명"  :"name",
    "주소"    :"address",
    "지상층수": "num_aboveground_floors",
    "지하층수": "num_underground_floors",
    "허가일자": "vintage",
    # 실
    "이름"      : "name",
    "층"        : "floor_number",
    "천정고"    : "height",
    "용도프로필": "profile",
    "조명밀도" : "light_density",
    "침기율"    : "infiltration" ,
    "난방 공급 설비": "supply_system_heating_name",
    "냉방 공급 설비": "supply_system_cooling_name",
    "환기 설비"     : "ventilation_system_name",
    # 면
    "소속 실"    : "parent_zone_name",
    "유형"       : "type",
    "경계조건"   : "boundary_condition",
    "면적"       : "area",
    "향"         : "azimuth",
    "인접존 이름": "adj_zone_name",
    "구조체 이름": "construction_name",
    "쿨루프 반사율": "coolroof_reflectance",
    # 개구부
    "소속 면": "parent_surface_name",
    "블라인드": "blind",
    # 구조체_면
    "레이어1_재료": "layer1_material",
    "레이어1_두께": "layer1_thickness",
    "레이어2_재료": "layer2_material",
    "레이어2_두께": "layer2_thickness",
    "레이어3_재료": "layer3_material",
    "레이어3_두께": "layer3_thickness",
    "레이어4_재료": "layer4_material",
    "레이어4_두께": "layer4_thickness",
    "레이어5_재료": "layer5_material",
    "레이어5_두께": "layer5_thickness",
    # 구조체_개구부
    "투명여부"      : "is_transparent",
    "열관류율"      : "u",
    "태양열취득계수": "g",
    # 재료
    "열전도율": "conductivity",
    "밀도"    : "density",
    "비열"    : "specific_heat",
    # 공급설비
    "냉방용량": "capacity_cooling",
    "난방용량": "capacity_heating",
    "냉방COP" : "cop_cooling",
    "생산설비명": "source_sys_name",
    # 생산설비
    "난방COP" : "cop_heating",
    "효율"    : "efficiency",
    "급탕용"  : "hotwater_supply",
    "연료종류": "fuel_type",
    "압축기 종류" : "compressor_type",
    "냉각탑 종류" : "coolingtower_type",
    "냉각탑 용량" : "coolingtower_capacity",
    "냉각탑 제어방식": "coolingtower_control",
    "연동보일러 효율": "boiler_efficiency",
    # 환기설비
    "난방효율" : "efficiency_heating",
    "냉방효율" : "efficiency_cooling",
    # PV패널
    "방위각": "azimuth",
    "경사각": "tilt"   ,
}

PROPERTY_RENAME_DICT = {
    "source_type": {
        "히트펌프": "heatpump",
        "지열히트펌프": "geothermal_heatpump",
        "냉동기"  : "chiller",
        "흡수식냉동기": "absorption_chiller",
        "지역난방": "district_heating",
        "보일러"  : "boiler"  ,
    },
    "supply_type": {
        "공조기": "air_handling_unit",
        "팬코일유닛": "fan_coil_unit",
        "바닥난방":"radiant_floor",
        "패키지에어컨": "packaged_air_conditioner",
        "방열기" : "radiator",
        "전기방열기" : "electric_radiator"
    },
    "fuel_type": {
        "전기"   : "electricity",
        "가스"   : "natural_gas",
        "천연가스": "natural_gas",
        "난방유" : "oil"        ,
        "지역난방": "district_heating",
    },
    "compressor_type": {
        "터보식": "turbo",
        "스크류식": "screw",
        "왕복동식": "reciprocating",
    },
    "coolingtower_type": {
        "개방형": "open",
        "밀폐형": "closed",
    },
    "is_transparent": {
        "투명": True,
        "불투명": False,
    }
}

GRJSON_FORMAT =  {
    "building":{
        "name"      : "",
        "north_axis": 0,
        "address"   : "",
        "vintage"   : [1900,1,1],
        "num_aboveground_floors": 0,
        "num_underground_floors": 0, 
        "floors"        : [],
        "supply_systems": [],
        "source_systems": [],
        "ventilation_systems": [],
        "photovoltaic_systems": [],
    },
    "profiles":[],
    "profile_components":{
        "schedules"    : [],
        "rulesets"     : [],
        "day_schedules": [],
    },
    "materials":[],
    "surface_constructions"     :[],
    "fenestration_constructions":[],
}



# ---------------------------------------------------------------------------- #
#                             EXCEL GUI: FUNCTIONS                             #
# ---------------------------------------------------------------------------- #

def _clean_column_names(
    df:pd.DataFrame
    ) -> pd.DataFrame:
    
    # Create a copy of the DataFrame to avoid modifying the original
    df_cleaned = df.copy()
    
    # Remove units
    df_cleaned.columns = df_cleaned.columns.str.replace(r"\[[\w/·%°@]+\]", "", regex=True,).str.strip()
    
    # Rename columns
    df_cleaned.rename(columns=COLUMN_RENAME_DICT, inplace=True)
    
    return df_cleaned


def _assign_id(
    df       :pd.DataFrame,
    sheetname:str         ,
    ) -> pd.DataFrame:
    
    # Create a copy of the DataFrame to avoid modifying the original
    df_assigned = df.copy()
    
    # If no ID is required for the sheet, return the copy itself
    if sheetname in ["건물정보"]:
        return df_assigned
    
    # Get prefix for the sheetname
    prefix = ID_PREFIX[sheetname]
    
    # Check uniqueness of the names
    # If not, raise an exception
    if not all((name_bin:=df_assigned["name"].value_counts()) == 1):
        duplicated_name_str = ", ".join([
            f"{name} ({count} times)"
            for name, count in zip(name_bin[name_bin>1].index, name_bin[name_bin>1].values)
        ])
        raise ValueError(
            f"Duplicated name detected in the sheet '{sheetname}': {duplicated_name_str}"
        )
    
    # Assign id using the index
    # For the safety, reset the index before the assigning
    df_assigned.reset_index(inplace=True, drop=True)
    df_assigned.insert(0, "id", df_assigned.index.map(lambda v: f"{prefix}-0x{v:06X}"))
    
    return df_assigned


def _replace_nan_to_none(
    obj:Any
    ) -> Any:
    
    # Revursively apply the function to the items: dict
    if isinstance(obj, dict):
        return {k: _replace_nan_to_none(v) for k, v in obj.items()}
    
    # Revursively apply the function to the items: list
    elif isinstance(obj, list):
        return [_replace_nan_to_none(v) for v in obj]
    
    # Convert the nan instance to the None
    # to export 'null' into the result json
    if pd.isna(obj):
        obj =  None
    
    return obj
    

def _name_to_id(
    df  :pd.DataFrame,
    name:str         ,
    ) -> str:
    
    # If name is not given, return None (for json: null)
    # This is desinged for empty use of the reference inputs (e.g. zone:supply_system_heating_id)
    if pd.isna(name):
        return None    

    # Find the 'name' in the given dataframe
    target_row = df.loc[df['name'] == name, 'id']
    
    # If there's no 'name' in the dataframe
    if target_row.empty:
        raise KeyError(f"ID for name '{name}' not found.")
    
    # If there's two or more 'name' in the dataframe (duplicated name usage)
    if len(target_row) > 1:
        raise KeyError(f"Multiple ({len(target_row)}) IDs found for name '{name}'. Please check for duplicate entries.")
    
    # Return ID matched with the 'name'
    target_id = target_row.iloc[0]
    return target_id
    
    
def _preprocess_excel_dict(
    excel_dict: dict[str, pd.DataFrame]
    ) -> dict[str, pd.DataFrame]:
    
    # Filter unused sheets
    excel_dict = {k:v for k,v in excel_dict.items() if k in VALID_COLUMNS.keys()}
    
    for sheetname, df in excel_dict.items():
        
        # Delete unused columns (auto-calculated columns)
        df_valid = df[VALID_COLUMNS[sheetname]]
        
        # Delete unused rows (unintended rows)
        df_valid = df_valid.loc[~df_valid.isna().all(axis=1),:]
        
        # Rename columns (removing units, translating Korean to English)
        df_cleaned = _clean_column_names(df_valid)
        
        # Assign ID for objects
        df_assigned = _assign_id(df_cleaned, sheetname)

        # Save the pre-processed dataframe
        excel_dict[sheetname] = df_assigned
    
    return excel_dict

def _rename_properties(
    row_dict  :dict,
    *args:tuple[str, str] # [mapper key name, row column name]
    ) -> None:
    
    for key, col in args:
        
        mapper = PROPERTY_RENAME_DICT[key]
        v      = row_dict[col]
        row_dict[col] = mapper[v] if not pd.isna(v) else v
        
    return
        
def _convert_source_systems(
    df_source:pd.DataFrame
    ) -> list[dict]:
    
    # Define required properties by the source system type
    VALID_PROPERTIES = {
        "heatpump"            : ["capacity_heating", "capacity_cooling", "cop_heating", "cop_cooling", "fuel_type"],
        "geothermal_heatpump" : ["capacity_heating", "capacity_cooling", "cop_heating", "cop_cooling", "fuel_type"],
        "chiller"             : ["capacity_cooling","cop_cooling","compressor_type","coolingtower_type","coolingtower_capacity","coolingtower_control","fuel_type"],
        "absorption_chiller"  : ["capacity_cooling", "cop_cooling","boiler_efficiency","fuel_type"],
        "boiler"              : ["capacity_heating", "efficiency","hotwater_supply", "fuel_type"],
        "district_heating"    : ["hotwater_supply"],
    }
    
    source_list = []
    for _, row in df_source.iterrows():
        
        # Convert form
        source_dict = row.to_dict()
        
        # Rename values
        _rename_properties(source_dict,
            ("source_type"      , "type"            ),
            ("fuel_type"        , "fuel_type"       ),
            ("compressor_type"  , "compressor_type" ),
            ("coolingtower_type","coolingtower_type"),
        )
                
        # convert value type
        if "hotwater_supply" in source_dict.keys():
            source_dict["hotwater_supply"] = bool(source_dict["hotwater_supply"])
         
        # convert unit
        source_dict["efficiency"]           *= Unit.PRC2NONE
        source_dict["boiler_efficiency"] *= Unit.PRC2NONE
         
        # Remove unused properties
        source_dict = {k:v for k,v in source_dict.items() if k in VALID_PROPERTIES[source_dict["type"]] + ["name", "id", "type"]}

        # Append to the list
        source_list.append(source_dict)
    
    return source_list


def _convert_supply_systems(
    df_supply:pd.DataFrame,
    df_source:pd.DataFrame,
    ) -> list[dict]:
    
    # Define required properties by the supply system type
    VALID_PROPERTIES = {
        "packaged_air_conditioner": ["capacity_cooling","cop_cooling"],
        "air_handling_unit"       : [],
        "fan_coil_unit"           : [],
        "radiator"                : ["capacity_heating"],
        "electric_radiator"       : ["capacity_heating"],
        "radiant_floor"           : []
    }
    
    supply_list = []
    for _, row in df_supply.iterrows():
        
        # Convert form
        supply_dict = row.to_dict()
        
        # Rename values
        _rename_properties(supply_dict,
            ("supply_type", "type")
        )
        
        # Get ID of the reference properties (source system)
        supply_dict["source_system_id"] = _name_to_id(df_source, supply_dict["source_sys_name"])
        
        # Remove unused properties
        supply_dict = {k:v for k,v in supply_dict.items() if k in VALID_PROPERTIES[supply_dict["type"]] + ["name", "id", "type","source_system_id"]}
        
        # Append to the list
        supply_list.append(supply_dict)
    
    return supply_list


def _convert_ventilation_systems(
    df_ventilation:pd.DataFrame
    ) -> list[dict]:
    
    ventilation_list = []
    for _, row in df_ventilation.iterrows():
        
        # Convert form
        ventilation_dict = row.to_dict()
        
        # convert unit
        ventilation_dict["efficiency_heating"] *= Unit.PRC2NONE
        ventilation_dict["efficiency_cooling"] *= Unit.PRC2NONE
        
        # Append to the list
        ventilation_list.append(ventilation_dict)
    
    return ventilation_list


def _convert_photovoltaic_systems(
    df_photovoltaic:pd.DataFrame
    ) -> list[dict]:
    
    photovoltaic_list = []
    for _, row in df_photovoltaic.iterrows():
        
        # Convert form
        photovoltaic_dict = row.to_dict()
        
        # convert unit
        photovoltaic_dict["efficiency"] *= Unit.PRC2NONE
        
        # Append to the list
        photovoltaic_list.append(photovoltaic_dict)
    
    return photovoltaic_list


def _convert_fenestrations(
    df_fenestration             :pd.DataFrame,
    df_construction_fenestration:pd.DataFrame,
    ) -> list[dict]:
    
    fenestration_list = []
    for _, row in df_fenestration.iterrows():

        # Convert form
        fenestration_dict = row.to_dict()
        
        # Get ID of the reference properties (construction)
        fenestration_dict["construction_id"] = _name_to_id(df_construction_fenestration, fenestration_dict["construction_name"])
        
        # Remove unused properties
        fenestration_dict.pop("parent_surface_name")
        fenestration_dict.pop("construction_name")
        
        # allocate default blind
        if fenestration_dict["blind"] == 1.0:
            fenestration_dict["blind"] = "shade"
        else:
            fenestration_dict["blind"] = None
        
        # Append to the list
        fenestration_list.append(fenestration_dict)
    
    return fenestration_list


def _convert_surfaces(
    df_surface     :pd.DataFrame,
    df_zone        :pd.DataFrame,
    df_fenestration:pd.DataFrame,
    df_construction_surface     :pd.DataFrame,
    df_construction_fenestration:pd.DataFrame,
    ) -> list[dict]:
    
    surf_list = []
    for _, row in df_surface.iterrows():
        
        # Convert form
        surf_dict = row.to_dict()
            
        # Get ID of the reference properties (adjacent zone),
        # if required
        if surf_dict["boundary_condition"] == "zone":
            surf_dict["adjacent_zone_id"] = _name_to_id(df_zone, surf_dict["adj_zone_name"])
        
        # Get ID of the reference properties (construction)
        # '오픈' -> "open", 빈 칸 -> "unknown"
        match surf_dict["construction_name"]:
            case "오픈":
                surf_dict["construction_id"] ="open"
            case _:
                surf_dict["construction_id"] = _name_to_id(df_construction_surface, surf_dict["construction_name"])
        
        # remove unused properties
        surf_dict.pop("parent_zone_name")
        surf_dict.pop("adj_zone_name")
        surf_dict.pop("construction_name")
        
        # convert unit
        if surf_dict["coolroof_reflectance"] is not None:
            surf_dict["coolroof_reflectance"] *= Unit.PRC2NONE
        
        # Remove unused properties,
        # if required 1 (no azimuth except for outdoor-wall)
        if (surf_dict["type"] != "wall") or (surf_dict["boundary_condition"] != "outdoors"):
            surf_dict.pop("azimuth")
        # if required 2 (no coolroof_reflectance except for outside-ceiling)
        if (surf_dict["type"] != "ceiling") or (surf_dict["boundary_condition"] != "outdoors"):
            surf_dict.pop("coolroof_reflectance")
        
        # Find children fenestration objects,
        child_fenestrations = df_fenestration.query("parent_surface_name == @row['name']")
        # and convert the children fenestrations to dicts
        fen_list = _convert_fenestrations(child_fenestrations, df_construction_fenestration)
        surf_dict["fenestrations"] = fen_list
        
        # Append to the list
        surf_list.append(surf_dict)
    
    return surf_list


def _convert_zones(
    df_zone        :pd.DataFrame,
    df_surface     :pd.DataFrame,
    df_fenestration:pd.DataFrame,
    df_construction_surface     :pd.DataFrame,
    df_construction_fenestration:pd.DataFrame,
    df_supply_system     :pd.DataFrame,
    df_ventilation_system:pd.DataFrame,
    ) -> dict:
    
    zone_list = []
    for _, row in df_zone.iterrows():
        
        # Convert form
        zone_dict = row.to_dict()

        # Get ID of the reference properties (heating supply system, cooling supply system)
        zone_dict["supply_system_heating_id"] = _name_to_id(df_supply_system, zone_dict["supply_system_heating_name"])
        zone_dict["supply_system_cooling_id"] = _name_to_id(df_supply_system, zone_dict["supply_system_cooling_name"])
        zone_dict["ventilation_system_id"] = _name_to_id(df_ventilation_system, zone_dict["ventilation_system_name"])
        
        # Remove unused properties
        zone_dict.pop("floor_number")
        zone_dict.pop("supply_system_heating_name")
        zone_dict.pop("supply_system_cooling_name")
        zone_dict.pop("ventilation_system_name")
        
        # Find children surface objects,
        child_surfaces = df_surface.query("parent_zone_name == @row['name']")
        # and convert the children surfaces to dicts
        surf_list = _convert_surfaces(child_surfaces, df_zone, df_fenestration, df_construction_surface, df_construction_fenestration) 
        zone_dict["surfaces"] = surf_list

        # Append to the list
        zone_list.append(zone_dict)
        
    return zone_list


def _convert_material(
    df_material:pd.DataFrame
    ) -> list[dict]:
    
    material_list = []
    for _, row in df_material.iterrows():
        
        # Convert form
        material_dict = row.to_dict()
        
        # Append to the list
        material_list.append(material_dict)
        
    return material_list


def _convert_construction_surface(
    df_construction_surface:pd.DataFrame,
    df_material            :pd.DataFrame,
    ) -> list[dict]:
    
    const_list = []
    for _, row in df_construction_surface.iterrows():
        
        # Convert form
        const_dict = row.to_dict()
        
        # Get ID of the reference properties (material)
        const_dict = {k:(_name_to_id(df_material, v) if k.endswith("material") else v) for k,v in const_dict.items()}
        
        # Construct layer info.:
        # After first two values (id, name), the remaining values come in material_id & thickness pairs
        material_ids = list(const_dict.values())[2::2]
        thicknesses  = list(const_dict.values())[3::2]
        layers = [
            {"material_id": material_id, "thickness": thickness*Unit.MM2M}
            for material_id, thickness in zip(material_ids, thicknesses)
            if material_id is not None
        ]
        
        # Reconstruct construction dict
        const_dict_structured = {
            "id"    : const_dict["id"]  ,
            "name"  : const_dict["name"],
            "layers": layers            ,
        }
        
        # Append to the list
        const_list.append(const_dict_structured)
    
    return const_list


def _convert_construction_fenestration(
    df_construction_fenestration:pd.DataFrame,
    ) -> list[dict]:
    
    const_list = []
    for _, row in df_construction_fenestration.iterrows():
        
        # Convert form
        const_dict = row.to_dict()
        
        # Rename values
        _rename_properties(const_dict,
            ("is_transparent" ,"is_transparent")
        )
        
        # Append to the list
        const_list.append(const_dict)
    
    return const_list


def excel2grjson(
    input_filepath :str          ,
    output_filepath:str|None=None,
    save           :bool    =True,
    ) -> tuple[dict, str]:
    
    """ Convert an excel input file to a grjson formatted file

    Args
    ----
    input_filepath (str)
        * filepath of an input excel file 
    output_filepath (str, default=None)
        * filepath of the output grjson file (grm extension recommanded). 
        * default to uuid-based temporal filename in the current directory
    save (bool, default=True)
        * if True, save the result grjson to the output_filepath
    
    Returns
    -------
    grjson (dict)
        * json structured converted dict
    output_filepath (str)
        * output_filepath
        * if save==False, returns None
        * if given as parameter and save==True, returned value is same as the given
    """
    
    # filter warnings
    warnings.filterwarnings("ignore", message="Data Validation extension is not supported and will be removed")
    
    # Read the excel file and preprocess:
    # filtering sheets and columns, renaming columns, assigning id
    excel_org = pd.read_excel(input_filepath, sheet_name=None)
    excel     = _preprocess_excel_dict(excel_org)

    # Get default grjson struct and assign building information
    grjson = deepcopy(GRJSON_FORMAT)
    grjson["building"] |= excel["건물정보"].iloc[0].to_dict()
    
    # Convert form of the building vintage: timestamp -> list[year, month, day]
    if isinstance(grjson["building"]["vintage"], str):
        grjson["building"]["vintage"] = datetime.strptime(grjson["building"]["vintage"], r"%Y-%m-%d")
    
    grjson["building"]["vintage"] = [
        grjson["building"]["vintage"].year ,
        grjson["building"]["vintage"].month,
        grjson["building"]["vintage"].day
    ]
    
    # Get zone dict
    zone_list = _convert_zones(
        excel["실"]      , excel["면"]         , excel["개구부"]  ,
        excel["구조체_면"], excel["구조체_개구부"],
        excel["공급설비"] , excel["환기설비"]
    )
    
    # Get zone dict by floors
    for floor_num, floor_zones in excel["실"].sort_values(by="floor_number", ascending=True).groupby("floor_number"):
        
        floor_dict = {
            "floor_number": int(floor_num)    ,
            "zones"       : [zone for zone in zone_list if (zone["id"] in floor_zones["id"].values)],
        }
        grjson["building"]["floors"].append(floor_dict)
    
    # Get system dict
    grjson["building"]["supply_systems"] = _convert_supply_systems(excel["공급설비"], excel["생산설비"])
    grjson["building"]["source_systems"] = _convert_source_systems(excel["생산설비"])
    grjson["building"]["ventilation_systems"]  = _convert_ventilation_systems(excel["환기설비"])
    grjson["building"]["photovoltaic_systems"] = _convert_photovoltaic_systems(excel["PV패널"])
    
    # Get construction dict
    grjson["materials"]                  = _convert_material(excel["재료"])
    grjson["surface_constructions"]      = _convert_construction_surface(excel["구조체_면"], excel["재료"])
    grjson["fenestration_constructions"] = _convert_construction_fenestration(excel["구조체_개구부"])
    
    # Finalize: replace pd.NA to None
    grjson = _replace_nan_to_none(grjson)
        
    if save: 
        # Set default output filepath by uuid
        if output_filepath is None:
            output_filepath = os.path.join(os.path.dirname(input_filepath), f"{uuid4()}.grm")
            
        # Write json
        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(grjson, f, ensure_ascii=False, indent=4)
            
    else:
        # If save=False but output_filepath is provided,
        # issue a warning and reset output_filepath to None
        if output_filepath is not None:
            warnings.warn(
                "The 'output_filepath' parameter is set but will be ignored because save=False.",
                UserWarning
            )
            output_filepath = None
    
    return grjson, output_filepath

