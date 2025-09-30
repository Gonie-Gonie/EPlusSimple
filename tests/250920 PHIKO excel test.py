
import os

from epsimple import run_grexcel
from reb.preprocess import process_excel_file
from epsimple.debug import debug_excel, report_result

target_dir   = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\tests\250920 PHIKO excel test"

target_files = [
    r"396_한마음어린이집_GR이전.xlsx",
]

for file in target_files:
    
    exceptions = debug_excel(os.path.join(target_dir, file))
    
    processed_file = process_excel_file(os.path.join(target_dir, file))
    
    run_grexcel(
        processed_file,
        os.path.join(target_dir, file.replace(r".xlsx",r".grr"))
    )