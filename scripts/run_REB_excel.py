
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

input_excel_dir = os.path.join(working_dir,"input_excel")
result_grr_dir  = os.path.join(working_dir, "result_grr")
result_idf_dir  = os.path.join(working_dir, "result_idf")


# main

filelist = [file for file in input_excel_dir]
if __name__ == "__main__":
    
    for file in filelist:
        grr_path = os.path.join(result_grr_dir, file.replace(r".xlsx",r".grr"))
        idf_path = os.path.join(result_idf_dir, file.replace(r".xlsx",r".idf"))
        grr, idf = run_rebexcel(os.path.join(input_excel_dir,file))

