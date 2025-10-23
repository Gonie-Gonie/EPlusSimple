
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
import json
import subprocess
from pathlib  import Path
from dataclasses import dataclass

# third-party modules
import pandas            as pd
import matplotlib.pyplot as plt
from jinja2 import Template

# local modules


# settings
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ---------------------------------------------------------------------------- #
#                                   VARIABLES                                  #
# ---------------------------------------------------------------------------- #

TEMPLATEPATH = Path(__file__).parent / "report_template.tex"
BUILD_DIR    = Path(__file__).parents[2] / "dist" / "reb-report"
FIG_DIR      = BUILD_DIR / "figures"


# ---------------------------------------------------------------------------- #
#                                   METADATA                                   #
# ---------------------------------------------------------------------------- #

@dataclass
class MetaData:
    name: str
    area: str
    addr: str
    date: str

# ---------------------------------------------------------------------------- #
#                                 SUBFUNCTIONS                                 #
# ---------------------------------------------------------------------------- #


# ---------------------------------------------------------------------------- #
#                               FIGURE FUNCTIONS                               #
# ---------------------------------------------------------------------------- #

def draw_weather_monthlycomparision() -> plt.Figure:
    
    return

def draw_weather_degreedays() -> plt.Figure:
    
    return

def draw_weather_figures() -> tuple[plt.Figure]:
    
    return


def draw_3step_bargraph(
    title : str,
    values: list[int|float],
    index : list[str],
    *,
    ylabel: str = "Value",
    colors: tuple = ("tab:blue", "tab:orange", "tab:green"),
    ) -> plt.Figure:
    
    fig, ax = plt.subplots(figsize=(4, 3))
    
    num_bars = len(values)
    x_positions = range(num_bars) # [0, 1, 2]
    width = 0.7  # 그룹이 아니므로 막대 폭을 넓게 설정

    for n, (pos, val) in enumerate(zip(x_positions, values)):
        # x축 0, 1, 2 위치에 막대 생성
        # xticklabels를 사용하므로 'label=' 인자는 제거
        bars = ax.bar(pos, val, width, color=colors[n])
        
        # 막대 위에 값 표시 (padding을 3 정도로 살짝 띄움)
        ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)

    # --- 축 및 레이블 수정 ---
    # x축 눈금 위치를 막대 위치(0, 1, 2)와 동일하게 설정
    ax.set_xticks(x_positions)
    # x축 눈금 레이블을 index 리스트로 설정
    ax.set_xticklabels(index, fontsize=10)
    
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11, weight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    
    # xlim을 막대 좌우로 0.5만큼 여유 있게 설정 (-0.5 ~ 2.5)
    ax.set_xlim(-0.5, num_bars - 0.5)
    
    # bar_label이 잘 보이도록 y축 상단에 15% 여유 공간 추가
    ax.set_ylim(top=max(values) * 1.15) 
    
    fig.tight_layout()
    
    return fig

def draw_energysimulation_figures(
    grrbefore:dict,
    grrafter :dict,
    grrafterN:dict,
    ) -> tuple[plt.Figure]:
    
    fig_use = draw_3step_bargraph(
        "에너지 사용량 비교",
        [
            grrbefore["summary_per_area"]["site_uses"]["total_annual"],
            grrafter["summary_per_area"]["site_uses"]["total_annual"],
            grrafterN["summary_per_area"]["site_uses"]["total_annual"],
        ],
        ["Before","GR이후","N년차"],
        ylabel = "EUI [kWh/m2/year]",
    )
    
    fig_co2 = draw_3step_bargraph(
        "온실가스 배출량 비교",
        [
            grrbefore["summary_per_area"]["co2"]["total_annual"],
            grrafter["summary_per_area"]["co2"]["total_annual"],
            grrafterN["summary_per_area"]["co2"]["total_annual"],
        ],
        ["GR이전","GR이후","N년차"],
        ylabel = "CO2-eq [kgCO2/m2/year]",
    )
    
    return fig_use, fig_co2


# ---------------------------------------------------------------------------- #
#                                   MAIN FUNC                                  #
# ---------------------------------------------------------------------------- #

def build_report(
    before_rebexcelpath:str,
    after_rebexcelpath :str,
    afterN_rebexcelpath:str,
    before_grrpath:str,
    after_grrpath :str,
    afterN_grrpath:str,
    pdfpath:str,
    ) -> None:
    
    # resultdata
    with open(before_grrpath, "r") as f:
        grrbefore = json.load(f)
    with open(after_grrpath, "r") as f:
        grrafter  = json.load(f)
    with open(afterN_grrpath, "r") as f:
        grrafterN = json.load(f)
    
    # metadata
    building_info = pd.read_excel(before_rebexcelpath, sheet_name="건물정보", usecols=range(6), nrows=1).iloc[0]
    metadata = MetaData(
        building_info["건물명"]     ,
        str(grrbefore["building"]["total_area"]),
        building_info["주소"],
        building_info["허가일자"]   , 
    )
    
    # get figures
    fig_use, fig_co2 = draw_energysimulation_figures(grrbefore, grrafter, grrafterN)
    fig_use.savefig(FIG_DIR / "energy_summary_use.png")
    fig_co2.savefig(FIG_DIR / "energy_summary_co2.png")
    
    # arrange the results
    context = {
        "metadata": metadata,
        "EUIdiff" : [
            round(grrbefore["summary_per_area"]["site_uses"]["total_annual"] - grrafter["summary_per_area"]["site_uses"]["total_annual"],2),
            round(grrbefore["summary_per_area"]["site_uses"]["total_annual"] - grrafterN["summary_per_area"]["site_uses"]["total_annual"],2),
            round(grrafterN["summary_per_area"]["site_uses"]["total_annual"] - grrafter["summary_per_area"]["site_uses"]["total_annual"],2),
        ]
    }
    
    # build
    template = Template(TEMPLATEPATH.read_text(encoding="utf-8"))
    rendered_tex = template.render(**context)
    texpath = BUILD_DIR / "report.tex"
    os.makedirs(BUILD_DIR, exist_ok=True)
    with open(texpath, "w", encoding="utf-8") as f:
        f.write(rendered_tex)
    
    cmd = ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", texpath.name]
    subprocess.run(cmd, cwd=str(BUILD_DIR), check=True)
    
    return
