import os

from pyGRsim import run_grexcel
from pyGRsim.reb.preprocess import process_excel_file
from pyGRsim.debug import debug_excel, report_result

working_dir   = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\tests\250924 PHIKO excel test"

target_files = [file for file in os.listdir(working_dir) if file.endswith(r".xlsx")]

target_files = [
    r"054_상남보건지소_GR이전.xlsx"
]

for file in target_files:
    
    fullfilename = os.path.join(working_dir, file)
    
    processed_file = process_excel_file(fullfilename)
    
    errors, warnings = debug_excel(processed_file)
    
    if len(errors) > 1:
        continue
    
    run_grexcel(
        processed_file,
        fullfilename.replace(r".xlsx",r".grr")
    )

pass