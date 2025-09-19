
import os
import sys

from pyGRsim import run_grjson, run_grexcel


target_dir   = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_grm"

target_files = [
    r"제물포어린이집_v1.7.grm",
    r"문평어린이집_v1.7.grm",
    r"서현어린이집_v1.7.grm",
]

for file in target_files:
    run_grjson(
        os.path.join(target_dir, file),
        os.path.join(target_dir, file.replace(r".grm",r".grr"))
    )
