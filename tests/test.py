import os
import json

from epsimple import run_grexcel
from epsimple.reb.preprocess import process_excel_file
from epsimple.debug import debug_excel, report_result

working_dir   = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\tests\250924 PHIKO excel test"

target_files = [file for file in os.listdir(working_dir) if file.endswith(r".xlsx") and not file.endswith(r"preprocess.xlsx")]

for file in target_files:
    
    fullfilename = os.path.join(working_dir, file)
    
    processed_file = process_excel_file(fullfilename)
    
    errors, warnings = debug_excel(processed_file)
    
    if len(errors) > 1:
        continue
    
    output_filepath = run_grexcel(
        processed_file,
        fullfilename.replace(r".xlsx",r".grr")
    )

    with open(output_filepath, "r") as f:
        data = json.load(f)
    
    if sum(sum(data["site_uses"]["cooling"].values(),[])) < 0.1:
        print(f"🐲🐲🐲🐲🐲🐲🐲🐲🐲🐲  {file}  🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥")
