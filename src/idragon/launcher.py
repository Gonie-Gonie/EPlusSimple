
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
import re
import uuid
import shutil
import tempfile
import subprocess
from io       import StringIO
from copy     import deepcopy
from datetime import datetime

# third-party modules
import pandas as pd
from tqdm import tqdm

# local modules
from .constants import (
    Directory  ,
    PackageInfo,
)
from .common import (
    Version    ,
    Setting    ,
)

# ---------------------------------------------------------------------------- #
#                                  EXCEPTIONS                                  #
# ---------------------------------------------------------------------------- #

class ExecutableEnergyPlusNotFoundError(Exception):
    pass

# ---------------------------------------------------------------------------- #
#                           MANAGE ENERGYPLUS RESULT                           #
# ---------------------------------------------------------------------------- #

class EnergyPlusResult:
    
    def __init__(self,
        *args,
        ) -> None:
        
        # default results
        self.audit = None
        self.err   = None
        self.bnd   = None
        self.tbl   = None
        self.eso   = None
        
        if len(args) == 0:
            pass
        
        # parse results
        for file in args:
            if not os.path.exists(file):
                raise FileNotFoundError(
                    f"'{file}' is not existing energyplus output file."
                )
            
            with open(file, encoding="UTF-8") as f:
                text = f.read()
            
            if file.endswith(".err"):
                elapsed_time, warnings = EnergyPlusResult.parse_err(text)
                self.time = elapsed_time
                self.err  = warnings
             
            elif file.endswith(".audit"):
                self.audit = EnergyPlusResult.parse_audit(text)
                
            elif file.endswith(".bnd"):
                self.bnd = EnergyPlusResult.parse_bnd(text)
        
            elif match:=re.match(r".+tbl\.(?P<extension>csv|html|xml)$", file):
                self.tbl = EnergyPlusResult.parse_table(text, match.group("extension"))
            
            elif file.endswith(".eso"):
                self.eso = EnergyPlusResult.parse_eso(text)
        
        return 
    
    @staticmethod
    def parse_audit(text:str) -> dict[str,int]:
        return {
            match.group("key"):int(match.group("value"))
            for match in re.finditer(r"(?P<key>\w+)=\s+(?P<value>\d+)", text)
        }
    
    @staticmethod
    def parse_err(text:str) -> tuple[float, pd.DataFrame]:
        
        time_match = re.search(r"Elapsed Time=(?P<hr>\d+)hr\s+(?P<min>\d+)min\s+(?P<sec>[\d\.]+)sec", text)
        time = float(time_match.group("hr"))*3600+float(time_match.group("min"))*60 + float(time_match.group("sec"))
        
        warning_match = re.finditer(r"\*\*\s*(?P<type>Warning|Severe)\s*\*\*\s*(?P<title>[^\n]+)", text)
        warning_df = pd.DataFrame([{"type":match.group("type"), "title":match.group("title")} for match in warning_match])        
        
        return time, warning_df
    
    @staticmethod
    def parse_bnd(text:str) -> dict[str, pd.DataFrame]:
        
        bnd = dict()
            
        column_texts = re.finditer(r"(?P<key>\<[\w ]+\>)(?P<columns>(?:,\<[\w #:/\[\]]+\>)+)", text)
        for match in column_texts:
            bnd[re.sub("<|>","",match.group("key"))] = pd.DataFrame(columns=re.sub("(^,)|<|>","",match.group("columns")).split(","))
        
        data_texts = re.finditer(r"\n\s*(?P<key>[\w ]+)(?P<body>(,[^,\n]+)+)", text)
        for match in data_texts:
            if not match.group("key") in bnd.keys():
                continue
            df = bnd[match.group("key")] 
            items = match.group("body").split(",")[1:]
            df.loc[len(df)] = items + [None] * (len(df.columns) - len(items))

        return bnd
    
    @staticmethod
    def parse_table(text:str, extension:str) -> None:
        
        match extension:
            case "csv":
                reports = re.finditer(r"\nREPORT:,(?P<reportname>\w+)\nFOR:,Meter\nCustom Monthly Report\n\n(?P<body>,.+?)\n{2,}", text, re.DOTALL)
                        
                tbl=dict()
                for report_match in reports:
                    body = re.sub(r"(?<=\n)\s*,|^,","",re.sub(r"\n\s*,+\s*\n",r"\n",report_match.group("body")))
                    df = pd.read_csv(StringIO(body))
                    df.set_index(df.columns[0], inplace=True)
                    df.index.name = "index"
                    tbl[report_match.group("reportname")] = df
                    
            case _:
                pass
        
        return tbl
    
    @staticmethod
    def parse_eso(text:str):        
        return 

# ---------------------------------------------------------------------------- #
#                                RUN ENERGYPLUS                                #
# ---------------------------------------------------------------------------- #

def find_executable_dir(version:Version|str):
    
    ep_dirname = Version.to_version_anyway(version).ep_dirname
    
    # 모듈 내부 포터블?
    if ep_dirname in os.listdir(Directory.ENERGYPLUS):
        return os.path.join(Directory.ENERGYPLUS, ep_dirname)
    
    # 님 컴?
    elif ep_dirname in os.listdir("C:\\"):
        return os.path.join("C:\\", ep_dirname)
    
    # ㅅㄱㄱ
    else:
        raise ExecutableEnergyPlusNotFoundError(
            f"EnergyPlus 버전 맞는걸로 안깔려있는듯"
        )
        
def run(
    idfpath:str|list[str],
    weather:str|list[str],
    *,
    ep_dir     =None,
    verbose    =True,
    output_dir =None,
    delete     =True,
    ) -> EnergyPlusResult|list[EnergyPlusResult]:
    
    if isinstance(idfpath,str):
        idfpath = [idfpath]
    if isinstance(weather, str):
        weather = [weather]
    
    if len(idfpath) == 1 and len(weather) > 1:
        idfpath *= len(weather)
    elif len(idfpath) > 1 and len(weather) == 1:
        weather *= len(idfpath)
    elif len(idfpath) > 1 and len(weather) > 1 and len(idfpath) != len(weather):
        raise ValueError(
            f""
        )
    
    if len(idfpath) == 1:
        return run_single(idfpath[0], weather[0], verbose=verbose, ep_dir=ep_dir, output_dir=output_dir, delete=delete)
    
    else:
        multirun_iterator = tqdm(zip(idfpath, weather), ncols=100, desc="Running idfs")
        return [
            run_single(idfpath_single, weather_single, verbose=False, ep_dir=ep_dir, delete=delete)
            for idfpath_single, weather_single in multirun_iterator
            ]

def run_single(
    idfpath:str,
    weather:str,
    *,
    verbose   =True,
    ep_dir    =None,
    output_dir=None,
    delete    =True,
    ) -> EnergyPlusResult:
    
    with open(idfpath, encoding="UTF-8") as f:
        idf_text = f.read()
    
    if ep_dir is None:
        
        # parse string identifying the version
        ep_version_match = re.search(r"(\n|^)[^!]*?Version,[^;]*?(?P<version>\d{1,2}\.\d{1,2}\.?\d*)\.?\d*\s*;", idf_text)
        
        # If there is no such a text,
        if not ep_version_match:
            raise RuntimeError(
                f"Cannot find EnergyPlus version as the format in the idf text"
            )
        
        # find executable energyplus       
        ep_dir = find_executable_dir(ep_version_match.group("version"))
    
    # launch
    if output_dir is None:
        output_dir = os.path.dirname(idfpath)
    
    run_dir = tempfile.mkdtemp(prefix=PackageInfo.NAME)
    status, output_files = _launch_energyplus(
        idfpath,
        weather,
        ep_dir ,
        run_dir,
        verbose=verbose,
    )
    
    copied_output_files = [os.path.join(output_dir, os.path.basename(file)) for file in output_files]
    for file, copied_file in zip(output_files, copied_output_files):
        shutil.copy(file, copied_file)
    shutil.rmtree(run_dir)
    
    epresult = EnergyPlusResult(*copied_output_files)
    
    if delete:
        for file in copied_output_files:
            os.remove(file)
        
    return epresult

def _expand_idf(
    idfpath:str,
    ep_dir :str, 
    *,
    expanded_idfpath:str=None
    ) -> str:
    
    if expanded_idfpath is None:
        expanded_idfpath = re.sub(r"\.idf$",r"_expanded.idf", idfpath)
    
    temp_dir = tempfile.mkdtemp(prefix=PackageInfo.NAME)
    shutil.copy(idfpath, os.path.join(temp_dir, "in.idf"))
    shutil.copy(os.path.join(ep_dir, "ExpandObjects.exe"), os.path.join(temp_dir, "ExpandObjects.exe"))
    shutil.copy(os.path.join(ep_dir, "Energy+.idd"      ), os.path.join(temp_dir, "Energy+.idd"      ))
    
    expanding_result = subprocess.run(os.path.join(temp_dir, "ExpandObjects.exe"), capture_output=True, text=True, cwd=temp_dir)

    if (expanding_result.returncode == 0) and not re.match(".+No expanded file generated",expanding_result.stdout, re.DOTALL):
        shutil.copy(os.path.join(temp_dir, r"expanded.idf"), expanded_idfpath)
    else:
        shutil.copy(os.path.join(temp_dir, r"in.idf"), expanded_idfpath)
    shutil.rmtree(temp_dir)
    
    return expanded_idfpath

def _parse_runperiod_from_idf(idfpath) -> tuple[datetime]:
    
    with open(idfpath, encoding="UTF-8") as f:
        idf_text = f.read()
    
    runperiod_text = re.search(r"\n\s*RunPeriod\s*,[^;]+?(?=;)", idf_text).group(0)
    runperiod_text = re.sub(r"\s+","",re.sub(r"!.+?\n","", runperiod_text))
    runperiod_text = re.sub(r"(,\d+,\d+),(,\d+,\d+),,",rf"\1,{Setting.DEFAULT_YEAR}\2,{Setting.DEFAULT_YEAR},", runperiod_text)
    runperiod_int = [int(txt) for txt in runperiod_text.split(",")[2:8]]
    start_date = datetime(runperiod_int[2],runperiod_int[0],runperiod_int[1])
    end_date = datetime(runperiod_int[5],runperiod_int[3],runperiod_int[4])
    
    return start_date, end_date

def _verbose_idf_stdout(
    proc      :subprocess.Popen,
    start_date:datetime,
    end_date  :datetime,
    ) -> None:
       
    pbar = tqdm(total=(end_date - start_date).days+1, ncols=100, desc="EP running...")
    simulating = False
    for line in proc.stdout:
        
        if line.startswith("Starting Simulation"):
            simulating=True
            current_date = start_date
            
        if not simulating:
            print(f"\r{line.strip():<80}", end="", flush=True)
        
        if line.startswith("Continuing Simulation"):
            datetime_str = re.sub(r"^(\d{2}/\d{2})$",rf"\1/{Setting.DEFAULT_YEAR}",re.search(r"(?<=at )\d{2}/\d{2}(/\d{4})?(?= for)", line).group(0))
            updated_date = datetime.strptime(datetime_str, r"%m/%d/%Y")
            pbar.update((updated_date-current_date).days)
            current_date = deepcopy(updated_date)
    
        if line.startswith("EnergyPlus Run Time"):
            pbar.update(pbar.total - pbar.n)
            pbar.close()
    return
    
def _launch_energyplus(
    idfpath:str,
    epwpath:str,
    ep_dir :str,
    run_dir:str,
    *,
    verbose:bool=True,
    ) -> tuple[int, list[str]]:
    
    expanded_idfpath = _expand_idf(idfpath, ep_dir)
    
    output_signature = f"{PackageInfo.NAME}-{uuid.uuid4()}"
    cmd = [
        os.path.join(ep_dir, r"EnergyPlus.exe"),
        "-r",
        "-x",
        "-d", run_dir         ,
        "-w", epwpath         ,
        "-p", output_signature,
        expanded_idfpath      ,
    ]
    
    if verbose:
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, encoding="UTF-8", errors="replace",text=True) as proc:
            start_date, end_date = _parse_runperiod_from_idf(idfpath)
            run_result =  _verbose_idf_stdout(proc, start_date, end_date)
    
    else:
        run_result = subprocess.run(cmd, encoding="UTF-8", errors="replace", capture_output=True, text=True)
              
    return 0, [os.path.join(run_dir, filename) for filename in os.listdir(run_dir) if filename.startswith(output_signature)]