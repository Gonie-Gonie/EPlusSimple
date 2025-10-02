
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os

# third-party modules


# local modules
from reb import run_rebexcel


# setting
working_dir = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_REB_excel"
filelist = [file for file in os.listdir(working_dir) if file.endswith(".xlsx")]


if __name__ == "__main__":
    
    for file in filelist:
        run_rebexcel(os.path.join(working_dir,file))

