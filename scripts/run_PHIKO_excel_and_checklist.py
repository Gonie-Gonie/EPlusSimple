# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os
from datetime  import datetime
from functools import partial

# third-party modules
import pandas as pd
from tqdm     import tqdm
from tqdm.contrib.concurrent import process_map

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
workers = 6

# ---------------------------------------------------------------------------- #
#                                   CONSTANTS                                  #
# ---------------------------------------------------------------------------- #

# log
LOGFILE_PATH = os.path.join(working_dir, datetime.now().strftime(r"%Y%m%d-%H%M%S.log"))
        
# directory: on-site survey
SURVEY_BEFORE_GR = os.path.join(working_dir, "checklist_beforeGR")
SURVEY_AFTER_GR  = os.path.join(working_dir, "checklist_afterGR")

# directory: excel
ORIGINAL_EXCEL_FILES_BEFORE_GR  = os.path.join(working_dir, "excel_original_beforeGR")
PROCESSED_EXCEL_FILES_BEFORE_GR = os.path.join(working_dir, "excel_preprocessed_beforeGR")
ORIGINAL_EXCEL_FILES_AFTER_GR   = os.path.join(working_dir, "excel_original_afterGR")
PROCESSED_EXCEL_FILES_AFTER_GR  = os.path.join(working_dir, "excel_preprocessed_afterGR")

# directory: result
STANDARD_CONDITION_BEFORE_GR = os.path.join(working_dir, "result_standard_beforeGR")
STANDARD_CONDITION_AFTER_GR  = os.path.join(working_dir, "result_standard_afterGR")
PRIORSURVEY_CONDITION_BEFORE_GR = os.path.join(working_dir, "result_priorsurvey_beforeGR")
PRIORSURVEY_CONDITION_AFTER_GR  = os.path.join(working_dir, "result_priorsurvey_afterGR")
POSTERIORSURVEY_CONDITION_BEFORE_GR = os.path.join(working_dir, "result_posteriorsurvey_beforeGR")
POSTERIORSURVEY_CONDITION_AFTER_GR  = os.path.join(working_dir, "result_posteriorsurvey_afterGR")

# ---------------------------------------------------------------------------- #
#                                   FUNCTIONS                                  #
# ---------------------------------------------------------------------------- #

def write_log(
    category :str ,
    success  :bool,
    filename :str ,
    exception:Exception|None=None
    ) -> None:
    
    with open(LOGFILE_PATH, "a") as f:
        if success: f.write(f"{category:10s}, success, {filename}\n")
        else      : f.write(f"{category:10s}, fail   , {filename}, {exception}\n")

    return

def preprocess_single(
    filename:str,
    *,
    dir_original :str,
    dir_processed:str,
    log_category :str,
    ) -> None:
    
    # define output path
    output_filepath = os.path.join(dir_processed, filename)
    
    # try to preprocess and log if succeed
    try:
        _ = process_excel_file(
            os.path.join(dir_original, filename),
            output_filepath=output_filepath,
            verbose=False
        )
        write_log(log_category, True, filename)
    
    # log if failed
    except Exception as e:
        write_log(log_category, False, filename, e)
        
    return

def preprocess(
    dir_original :str,
    dir_processed:str,
    desc         :str,
    ) -> None:
    
    # settings
    LOG_CATEGORY = "PREPROCESSING"
    filelist = os.listdir(dir_original)
    
    # multiprocessing
    worker = partial(
        preprocess_single,
        dir_original =dir_original,
        dir_processed=dir_processed,
        log_category =LOG_CATEGORY,
    )
    process_map(worker, filelist, max_workers=workers, desc=desc, ncols=150)     

    return


def run_standard_condition_single(
    filename:str,
    *,
    dir_processed:str,
    dir_result   :str,
    log_category :str,
    ) -> None:
    
    # define output path
    output_filepath = os.path.join(dir_result, filename).replace(r".xlsx",r".grr")
    
    # try to preprocess and log if succeed
    try:
        _ = run_grexcel(os.path.join(dir_processed,filename), output_filepath)
        write_log(log_category, True, filename)
    
    # log if failed
    except Exception as e:
        write_log(log_category, False, filename, e)
        
    return

def run_standard_condition(
    dir_processed:str,
    dir_result   :str,
    desc         :str,
    ) -> None:
    
    # settings
    LOG_CATEGORY = "RUNNING_STANDRAD"
    filelist = os.listdir(dir_processed)
    
    # multiprocessing
    worker = partial(
        run_standard_condition_single,
        dir_processed=dir_processed  ,
        dir_result = dir_result      ,
        log_category=LOG_CATEGORY    ,
    )
    process_map(worker, filelist, max_workers=workers, desc=desc, ncols=150)
    
    return



if __name__ == "__main__":

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

    if PREPROCESSING_REQUIRED:=False:
        
        # before GR
        preprocess(
            ORIGINAL_EXCEL_FILES_BEFORE_GR ,
            PROCESSED_EXCEL_FILES_BEFORE_GR,
            "Preprocessing before-GR excel files",
        )
        
        # after GR
        preprocess(
            ORIGINAL_EXCEL_FILES_AFTER_GR ,
            PROCESSED_EXCEL_FILES_AFTER_GR,
            "Preprocessing after-GR excel files",
        )            
        
    # ---------------------------------------------------------------------------- #
    #                              STANDARD CONDITION                              #
    # ---------------------------------------------------------------------------- #

    if STANDARD_RUNNING_REQUIRED:=True:
        
        # before-GR
        run_standard_condition(
            PROCESSED_EXCEL_FILES_BEFORE_GR,
            STANDARD_CONDITION_BEFORE_GR,
            "Running before-GR excel files w/ standard condition",        
        )

        # after GR
        run_standard_condition(
            PROCESSED_EXCEL_FILES_AFTER_GR,
            STANDARD_CONDITION_AFTER_GR,
            "Running after-GR  excel files w/ standard condition",        
        )
        
        
    # ---------------------------------------------------------------------------- #
    #                          BEFORE-GR SURVEY CONDITION                          #
    # ---------------------------------------------------------------------------- #

    # ---------------------------------------------------------------------------- #
    #                           AFTER-GR SURVEY CONDITION                          #
    # ---------------------------------------------------------------------------- #
