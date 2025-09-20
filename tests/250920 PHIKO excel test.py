
import os

from pyGRsim import run_grexcel


target_dir   = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\tests\250920 PHIKO excel test"

target_files = [
    r"032_판부보건지소_GR이전.xlsx",
    r"032_판부보건지소_GR이후.xlsx",
]

for file in target_files:
    run_grexcel(
        os.path.join(target_dir, file),
        os.path.join(target_dir, file.replace(r".xlsx",r".grr"))
    )