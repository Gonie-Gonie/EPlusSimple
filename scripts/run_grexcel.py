
import os

from pyGRsim import run_grjson, run_grexcel


target_dir   = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_grexcel"

target_files = [
    r"제물포어린이집_v250721retrofit.xlsx",
    r"제물포어린이집_v250721.xlsx",
]

for file in target_files:
    run_grexcel(
        os.path.join(target_dir, file),
        os.path.join(target_dir, file.replace(r".xlsx",r".grr"))
    )