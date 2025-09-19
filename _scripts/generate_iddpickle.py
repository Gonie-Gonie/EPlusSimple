
import os
import sys
import cProfile

from idragon.common import Version
from idragon      import read_idd

idd_org_dir = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\idd_generation"

iddfiles = os.listdir(idd_org_dir)
for file in iddfiles[::-1]:
    
    idd = read_idd(os.path.join(idd_org_dir, file), verbose=True)
    idd.to_pickle(idd_org_dir)

pass