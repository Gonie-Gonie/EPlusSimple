# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os

# third-party modules
import pandas as pd
from tqdm     import tqdm
from datetime import datetime

# local modules
from pyGRsim import run_grexcel
from pyGRsim.debug import debug_excel, report_result
from pyGRsim.reb.preprocess  import process_excel_file
from pyGRsim.reb.postprocess import (
    어린이집GR이전체크리스트,
    어린이집GR이후체크리스트,
    보건소GR이전체크리스트,
    보건소GR이후체크리스트,
)


# settings
working_dir = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_PHIKO_excel_and_checklist"


# ---------------------------------------------------------------------------- #
#                                INITIALIZATION                                #
# ---------------------------------------------------------------------------- #

# log
LOGFILE_PATH = os.path.join(working_dir, datetime.now().strftime(r"%Y%m%d-%H%M%S.log"))

def write_log(
    category :str ,
    success  :bool,
    filename :str ,
    exception:Exception|None=None
    ) -> None:
    
    with open(LOGFILE_PATH, "a") as f:
        if success: f.write(f"{category:10s}, success, {filename}\n")
        else      : f.write(f"{category:10s}, fail   , {filename}, {exception}\n")
        
# directory: on-site survey
SURVEY_BEFORE_GR = os.path.join(working_dir, "checklist_beforeGR")
SURVEY_AFTER_GR  = os.path.join(working_dir, "checklist_afterGR")

# directory: excel
ORIGINAL_EXCEL_FILES_BEFORE_GR  = os.path.join(working_dir, "excel_original_beforeGR")
PROCESSED_EXCEL_FILES_BEFORE_GR = os.path.join(working_dir, "excel_preprocessed_beforeGR")
ORIGINAL_EXCEL_FILES_AFTER_GR   = os.path.join(working_dir, "excel_original_afterGR")
PROCESSED_EXCEL_FILES_AFTER_GR  = os.path.join(working_dir, "excel_preprocessed_afterGR")

# directory: result



# ---------------------------------------------------------------------------- #
#                                ON-SITE SURVEY                                #
# ---------------------------------------------------------------------------- #

# 어린이집
beforesurvey어린이집 = 어린이집GR이전체크리스트.from_dataframe(
    pd.read_csv(os.path.join(SURVEY_BEFORE_GR, "어린이집.csv"))
)
aftersurvey어린이집  = 어린이집GR이후체크리스트.from_dataframe(
    pd.read_csv(os.path.join(SURVEY_AFTER_GR, "어린이집.csv"))
)

# 보건소
beforesurvey보건소 = 보건소GR이전체크리스트.from_dataframe(
    pd.read_csv(os.path.join(SURVEY_BEFORE_GR, "보건소.csv"))
)
aftersurvey보건소  = 보건소GR이후체크리스트.from_dataframe(
    pd.read_csv(os.path.join(SURVEY_AFTER_GR, "보건소.csv"))
)



# ---------------------------------------------------------------------------- #
#                                 PREPROCESSING                                #
# ---------------------------------------------------------------------------- #

LOG_CATEGORY = "PREPROCESSING"

if PREPROCESSING_REQUIRED:=True:
    
    # before GR
    beforeGR_filelist = os.listdir(ORIGINAL_EXCEL_FILES_BEFORE_GR) 
    for filename in tqdm(beforeGR_filelist, desc=f"Preprocessing before-GR excel files"):
        output_filepath = os.path.join(PROCESSED_EXCEL_FILES_BEFORE_GR, filename)
        
        try:
            _ = process_excel_file(os.path.join(ORIGINAL_EXCEL_FILES_BEFORE_GR, filename), output_filepath=output_filepath, verbose=False)
            write_log(LOG_CATEGORY, True, filename)
            
        except Exception as e:
            write_log(LOG_CATEGORY, False, filename, e)
    
    # after GR    
    afterGR_filelist = os.listdir(ORIGINAL_EXCEL_FILES_AFTER_GR) 
    for filename in tqdm(afterGR_filelist, desc=f"Preprocessing after-GR  excel files"):
        output_filepath = os.path.join(PROCESSED_EXCEL_FILES_AFTER_GR, filename)
        
        try:
            _ = process_excel_file(os.path.join(ORIGINAL_EXCEL_FILES_AFTER_GR, filename), output_filepath=output_filepath, verbose=False)
            write_log(LOG_CATEGORY, True, filename)
            
        except Exception as e:
            write_log(LOG_CATEGORY, False, filename, e)
            
    
# ---------------------------------------------------------------------------- #
#                              STANDARD CONDITION                              #
# ---------------------------------------------------------------------------- #

# ---------------------------------------------------------------------------- #
#                          BEFORE-GR SURVEY CONDITION                          #
# ---------------------------------------------------------------------------- #

# ---------------------------------------------------------------------------- #
#                           AFTER-GR SURVEY CONDITION                          #
# ---------------------------------------------------------------------------- #
