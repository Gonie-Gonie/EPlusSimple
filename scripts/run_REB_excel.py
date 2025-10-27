
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os

# third-party modules


# local modules
from reb import run_rebexcel
from reb.core import rebexcel_to_idf_and_grm
from epsimple.core.model import EnergyPlusError


# setting
working_dir = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_REB_excel"

input_excel_dir = os.path.join(working_dir,"input_excel")
result_grr_dir  = os.path.join(working_dir, "result_grr")
result_idf_dir  = os.path.join(working_dir, "result_idf")
err_idf_dir     = os.path.join(working_dir, "err_idf")


# main

filelist = [file for file in os.listdir(input_excel_dir) if not file.endswith("preprocess.xlsx")]
if __name__ == "__main__":
    
    for file in filelist[130:]:
        
        grr_path = os.path.join(result_grr_dir, file.replace(r".xlsx",r".grr"))
        idf_path = os.path.join(result_idf_dir, file.replace(r".xlsx",r".idf"))
        
        if os.path.exists(grr_path):
            continue
        
        try:    
            grr, idf = run_rebexcel(os.path.join(input_excel_dir,file), grr_path, idf_path)
            
        except EnergyPlusError:
            print(f"!!!!!!!!!!!!!!!EP에러로 실패: {file}")
            idf, grm = rebexcel_to_idf_and_grm(os.path.join(input_excel_dir,file))
            idf_path = os.path.join(err_idf_dir, file.replace(r".xlsx",r".idf"))
            idf.write(idf_path)
            

