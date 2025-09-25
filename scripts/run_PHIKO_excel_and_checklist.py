# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os

# third-party modules
import tqdm

# local modules
from pyGRsim import run_grexcel
from pyGRsim.debug import debug_excel, report_result
from pyGRsim.reb.preprocess  import process_excel_file
from pyGRsim.reb.postprocess import (
    어린이집GR이전체크리스트,
    어린이집GR이후체크리스트,
    보건소GR이전체크리스트,
    보건소GR이후체크리스트,
    보건지소GR이전체크리스트,
    보건지소GR이후체크리스트,
)


# settings
working_dir = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_PHIKO_excel_and_checklist"

# ---------------------------------------------------------------------------- #
#                                ON-SITE SURVEY                                #
# ---------------------------------------------------------------------------- #

