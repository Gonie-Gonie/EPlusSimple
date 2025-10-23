
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os
import re

# third-party modules


# local modules
from reb.report import build_report


# ---------------------------------------------------------------------------- #
#                                   SETTINGS                                   #
# ---------------------------------------------------------------------------- #

rebexcel_dir = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_REB_excel\input_excel"
grr_dir      = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_REB_excel\result_grr"
report_dir   = r"B:\공유 드라이브\01 진행과제\(안전원) 시뮬레이터\12 개발\scripts\run_REB_excel\report"

# ---------------------------------------------------------------------------- #
#                                   MAIN FUNC                                  #
# ---------------------------------------------------------------------------- #

def find_building_sets(
    rebexcel_dir:str,
    grr_dir     :str,
    ) -> list[dict]:
    
    def create_new_data(name:str) -> dict:
        return {
            "name" : name ,
            "valid": False,
            "excel": {
                "GR이전":None,
                "GR이후":None,
                "N년차" :None,
            },
            "grr": {
                "GR이전":None,
                "GR이후":None,
                "N년차" :None,
            },
        }
        
    
    rebexcel_filelist = os.listdir(rebexcel_dir)
    grr_filelist      = os.listdir(grr_dir)
    
    buildingdict = dict()
    
    # excel files
    for file in rebexcel_filelist:
        
        info = re.search(r"(?P<name>^\d{,3}_[^_]+)_(?P<type>[^_]+)(.xlsx|_운영)", file)
        
        if info is None:
            raise ValueError(f"parsing이 안됨: {file}")
        
        if (n:=info.group("name")) not in buildingdict.keys():
            buildingdict[n] = create_new_data(n)
            
        if (t:=info.group("type")) not in buildingdict[n]["excel"].keys():
            raise ValueError(f"keyword '{t}'는 좀 이상한듯 ('{file}'을 parsing함)")        
        
        buildingdict[n]["excel"][t] = os.path.join(rebexcel_dir, file)

    # grr files
    for file in grr_filelist:
        
        info = re.search(r"(?P<name>^\d{,3}_[^_]+)_(?P<type>[^_]+)(.grr|_운영)", file)
        
        if info is None:
            raise ValueError(f"parsing이 안됨: {file}")
        
        if (n:=info.group("name")) not in buildingdict.keys():
            buildingdict[n] = create_new_data(n)
        
        if (t:=info.group("type")) not in buildingdict[n]["grr"].keys():
            raise ValueError(f"keyword '{t}'는 좀 이상한듯 ('{file}'을 parsing함)")
        
        buildingdict[n]["grr"][t] = os.path.join(rebexcel_dir, file)
    
    # validity
    for _, buildingdata in buildingdict.items():
        if all(v is not None for v in list(buildingdata["excel"].values())+list(buildingdata["grr"].values())):
            buildingdata["valid"] = True
    
    return [d for d in buildingdict.values() if d["valid"]], [d for d in buildingdict.values() if not d["valid"]] 



def main(
    rebexcel_dir:str,
    grr_dir     :str,
    report_dir  :str,
    ) -> None:
    
    validlist, invalidlist = find_building_sets(
        rebexcel_dir,
        grr_dir     ,
    )
    
    for d in invalidlist:
        lacked_files = [f"excel({k})" for k,v in d["excel"].items() if v is None] +\
                       [f"grr({k})"   for k,v in d["grr"].items()   if v is None]
        print(f"Cannot build report for {d["name"]}: {",".join(lacked_files)}")
    
    for d in validlist:
        
        pdfpath = os.path.join(report_dir, f"{d["name"]}.pdf")
        build_report(
            *d["excel"].values(),
            *d["grr"].values(),
            pdfpath
        )

# ---------------------------------------------------------------------------- #
#                                    SCRIPT                                    #
# ---------------------------------------------------------------------------- #

if __name__ == "__main__":
    
    main(
        rebexcel_dir,
        grr_dir     ,
        report_dir  ,
    )
