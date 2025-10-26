
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import os
import json
import shutil
import subprocess
from pathlib  import Path
from collections import Counter
from dataclasses import dataclass

# third-party modules
import pandas            as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from jinja2 import Template

# local modules
from .comparison import compare_rebexcel
from .auxiliary  import find_weatherdata

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

MONTH_LBLS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
DEFAULT_COLORS = ("tab:blue", "tab:orange")  # epw1, epw2 색상

def _apply_axis_style(ax, title:str=None, ylabel:str=None):
    if title:
        ax.set_title(title, fontsize=11, weight="bold")
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_xticks(range(1,13))
    ax.set_xticklabels(MONTH_LBLS, fontsize=9)

# ---------------------------------------------------------------------------- #
#                               FIGURE FUNCTIONS                               #
# ---------------------------------------------------------------------------- #

EPW_COLUMNS = [
    "Year","Month","Day","Hour","Minute","Data Source and Uncertainty Flags",
    "Dry Bulb Temperature","Dew Point Temperature","Relative Humidity",
    "Atmospheric Station Pressure","Extraterrestrial Horizontal Radiation",
    "Extraterrestrial Direct Normal Radiation","Horizontal Infrared Radiation Intensity",
    "Global Horizontal Radiation","Direct Normal Radiation","Diffuse Horizontal Radiation",
    "Global Horizontal Illuminance","Direct Normal Illuminance","Diffuse Horizontal Illuminance",
    "Zenith Luminance","Wind Direction","Wind Speed","Total Sky Cover","Opaque Sky Cover",
    "Visibility","Ceiling Height","Present Weather Observation","Present Weather Codes",
    "Precipitable Water","Aerosol Optical Depth","Snow Depth","Days Since Last Snowfall",
    "Albedo","Liquid Precipitation Depth","Liquid Precipitation Quantity"
]

def read_epw_drybulb(epw_path: str | Path) -> pd.DataFrame:
    """
    EPW 파일에서 Dry Bulb Temperature(°C)와 (Year, Month, Day, Hour) 추출.
    - 헤더/주석('!')/DATA PERIODS 라인 자동 건너뛰기
    - EPW는 1~24시가 '해당 시각 종료' time stamp → 시간대를 0~23으로 보정(Hour-1)
    반환: df[["datetime","Year","Month","Day","Hour","DryBulb"]]
    """
    epw_path = Path(epw_path)
    rows = []
    with epw_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line or line.startswith("!"):
                continue
            parts = [p.strip() for p in line.rstrip("\n").split(",")]
            # 데이터 레코드 후보: 최소 30~35열, 앞 5개가 숫자
            if len(parts) < 30:
                continue
            y, m, d, h, mi = parts[0:5]
            if not (y.isdigit() and m.isdigit() and d.isdigit() and h.isdigit() and mi.isdigit()):
                continue
            # EPW 표준 컬럼에서 DryBulb는 7번째(0-base 6)
            try:
                dry = float(parts[6])
            except Exception:
                continue

            Y = int(y); M = int(m); D = int(d); H = int(h)
            # EPW는 Hour=1..24 (end-of-hour). pandas에 맞게 0~23로 보정
            H_adj = max(0, min(23, H - 1))
            # 빠르게 문자열 조합보다 pandas에 맡기기
            rows.append((Y, M, D, H_adj, dry))

    if not rows:
        raise ValueError(f"EPW 데이터 행을 찾지 못했습니다: {epw_path}")

    df = pd.DataFrame(rows, columns=["Year","Month","Day","Hour","DryBulb"])
    # 연도 정보가 0이거나 비정상인 EPW도 있으니, 가짜 기준년도 보정은 하지 않음 (그대로 사용)
    dt = pd.to_datetime(df[["Year","Month","Day","Hour"]], errors="coerce")
    df.insert(0, "datetime", dt)
    return df

# ===== (1) 월별 평균 + 박스플롯 비교 =====
def draw_weather_monthlycomparision(
    epw1: str | Path,
    epw2: str | Path,
    *,
    label1: str | None = None,
    label2: str | None = None,
    colors: tuple[str,str] = DEFAULT_COLORS,
    figsize=(6.0, 3.8),
) -> plt.Figure:
    """
    두 EPW의 월별 DryBulb 분포(boxplot)와 월평균(라인)을 한 그림에 비교.
    """
    df1 = read_epw_drybulb(epw1)
    df2 = read_epw_drybulb(epw2)
    if label1 is None: label1 = Path(epw1).stem
    if label2 is None: label2 = Path(epw2).stem

    # 월별 시계열 → 박스플롯 데이터
    box1 = [df1.loc[df1["Month"]==m, "DryBulb"].to_numpy() for m in range(1,13)]
    box2 = [df2.loc[df2["Month"]==m, "DryBulb"].to_numpy() for m in range(1,13)]
    mean1 = [float(pd.Series(b).mean()) if len(b)>0 else float("nan") for b in box1]
    mean2 = [float(pd.Series(b).mean()) if len(b)>0 else float("nan") for b in box2]

    fig, ax = plt.subplots(figsize=figsize)

    pos1 = list(range(1,13))
    shift = 0.3
    pos2 = [p + shift for p in pos1]

    bp1 = ax.boxplot(
        box1, positions=pos1, widths=0.25, patch_artist=True,
        boxprops=dict(facecolor=colors[0], alpha=0.3, linewidth=1.2),
        medianprops=dict(color=colors[0], linewidth=1.2),
        whiskerprops=dict(color=colors[0], linewidth=1.0),
        capprops=dict(color=colors[0], linewidth=1.0),
        flierprops=dict(markeredgecolor=colors[0], alpha=0.4, markersize=3),
    )
    bp2 = ax.boxplot(
        box2, positions=pos2, widths=0.25, patch_artist=True,
        boxprops=dict(facecolor=colors[1], alpha=0.3, linewidth=1.2),
        medianprops=dict(color=colors[1], linewidth=1.2),
        whiskerprops=dict(color=colors[1], linewidth=1.0),
        capprops=dict(color=colors[1], linewidth=1.0),
        flierprops=dict(markeredgecolor=colors[1], alpha=0.4, markersize=3),
    )

    # 월평균 표시(점선+마커)
    ax.plot(pos1, mean1, color=colors[0], marker="o", linestyle="--", linewidth=1.3, label=f"{label1} mean")
    ax.plot(pos2, mean2, color=colors[1], marker="o", linestyle="--", linewidth=1.3, label=f"{label2} mean")

    _apply_axis_style(ax, "Monthly Outdoor Temperature (Box & Mean)", "Dry Bulb Temperature (°C)")
    ax.set_xlim(0.5, 12.5 + shift)
    all_values = pd.concat([
        df1["DryBulb"].dropna(),
        df2["DryBulb"].dropna()
    ])
    vmin, vmax = all_values.min(), all_values.max()
    margin = (vmax - vmin) * 0.1  # 상하단 10% 여유

    ax.set_ylim(vmin - margin, vmax + margin)
    ax.legend(fontsize=9, ncols=2, loc="upper center", bbox_to_anchor=(0.5, 1.20))
    fig.tight_layout()
    return fig

# ===== (2) HDD/CDD 비교 =====
def draw_weather_degreedays(
    epw1: str | Path,
    epw2: str | Path,
    *,
    base_temp: float = 18.0,
    label1: str | None = None,
    label2: str | None = None,
    colors: tuple[str, str] = ("tab:blue", "tab:orange"),
    figsize=(3.9, 3.8),
) -> plt.Figure:
    """
    두 EPW 파일의 연간 Heating/Cooling Degree Days를 막대 4개로 비교.
    HDD/CDD는 °C·day 단위로 계산.
    """

    # --- EPW 데이터 읽기 (Month, DryBulb) ---
    df1 = read_epw_drybulb(epw1)
    df2 = read_epw_drybulb(epw2)
    if label1 is None: label1 = Path(epw1).stem
    if label2 is None: label2 = Path(epw2).stem

    # --- HDD/CDD 계산 ---
    def degree_days(df: pd.DataFrame, base: float):
        hdd = (base - df["DryBulb"]).clip(lower=0).sum() / 24.0
        cdd = (df["DryBulb"] - base).clip(lower=0).sum() / 24.0
        return hdd, cdd

    hdd1, cdd1 = degree_days(df1, base_temp)
    hdd2, cdd2 = degree_days(df2, base_temp)

    # --- Figure 구성 ---
    fig, ax = plt.subplots(figsize=figsize)
    x_positions = [0, 1, 3, 4]  # HDD1, HDD2, CDD1, CDD2
    heights = [hdd1, hdd2, cdd1, cdd2]
    colors_seq = [colors[0], colors[1], colors[0], colors[1]]

    bars = ax.bar(x_positions, heights, width=0.8, color=colors_seq, alpha=0.8)

    # --- x축 그룹 라벨 ---
    ax.set_xticks([0.5, 3.5])
    ax.set_xticklabels(["HDD", "CDD"], fontsize=10)
    ax.set_ylabel("Degree Days (°C·day)")
    ax.set_title(f"Annual HDD/CDD Comparison (Base {base_temp:.1f}°C)",
                 fontsize=11, weight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # --- 막대 위 값 표시 ---
    ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=9)

    # --- 범례 ---
    custom = [plt.Rectangle((0,0),1,1,color=colors[0],alpha=0.8),
              plt.Rectangle((0,0),1,1,color=colors[1],alpha=0.8)]
    ax.legend(custom, [label1, label2], fontsize=9, loc="upper right")

    fig.tight_layout()
    return fig

def draw_weather_figures(
    before_weatherdata_filepath:str,
    after_weatherdata_filepath :str,
    ) -> tuple[plt.Figure]:
    
    fig_monthlytemp = draw_weather_monthlycomparision(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
    )
    fig_degreedays = draw_weather_degreedays(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
    )
    
    return fig_monthlytemp, fig_degreedays


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

def preprocess_diff_dicts(
    diffs:list[dict]
    ) -> list[dict]:
    
    def mapper(v):
        
        if isinstance(v, str):
            v = v.replace(r"_",r"\_")
            v = v.replace(r"&", r"\&")
            v = v.replace(r"%", r"\%")
        
        if isinstance(v, int|float):
            v = f"{v:.10f}".rstrip("0").rstrip(".")
        
        return v
    
    return [
        {k:mapper(v) for k, v in d.items()
        }
        for d in diffs
    ]
    

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
        f"{grrbefore["building"]["total_area"]:1f}",
        building_info["주소"],
        building_info["허가일자"]   , 
    )
    
    # get comparison result
    perf_diff12, oper_diff12 = compare_rebexcel(
        before_rebexcelpath,
        after_rebexcelpath ,
    )
    perf_diff23, oper_diff23 = compare_rebexcel(
        after_rebexcelpath,
        afterN_rebexcelpath ,
    )
    
    # comparison summry
    if len(perf_diff12) > 0:
        diff_counts12 = perf_diff12.drop_duplicates(["type", "zonename"]).groupby("type")["zonename"].nunique().to_dict()
        diffstr12 = ", ".join(f"{k} {v}개 존" for k, v in diff_counts12.items())
    else:
        diffstr12 = "없음"
    if len(perf_diff23) > 0:
        diff_counts23 = perf_diff23.drop_duplicates(["type", "zonename"]).groupby("type")["zonename"].nunique().to_dict()
        diffstr23 = ", ".join(f"{k} {v}개 존" for k, v in diff_counts23.items())
    else:
        diffstr23 = "없음"
    if len(oper_diff23) > 0:
        diff_counts23oper = oper_diff23.drop_duplicates(["type", "zonename"]).groupby("type")["zonename"].nunique().to_dict()
        diffstr23oper = ", ".join(f"{k} {v}개 존" for k, v in diff_counts23oper.items())
    else:
        diffstr23oper = "없음"
    
    # get figures (by results)
    fig_use, fig_co2 = draw_energysimulation_figures(grrbefore, grrafter, grrafterN)
    os.makedirs(FIG_DIR, exist_ok=True)
    fig_use.savefig(FIG_DIR / "energy_summary_use.png", dpi=400, format="png")
    fig_co2.savefig(FIG_DIR / "energy_summary_co2.png", dpi=400, format="png")
    
    # get figures (by weather)
    before_weatherdata_filepath = find_weatherdata(building_info["주소"], "이전")
    after_weatherdata_filepath  = find_weatherdata(building_info["주소"], "직후")
    fig_monthlytemp, fig_degreedays = draw_weather_figures(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
    )
    fig_monthlytemp.savefig(FIG_DIR / "weather_compare_monthly.png", dpi=400, format="png")
    fig_degreedays.savefig(FIG_DIR / "weather_compare_degreeday.png", dpi=400, format="png")
    
    # arrange the results
    context = {
        "metadata": metadata,
        "diffsummary": [diffstr12, diffstr23, diffstr23oper],
        "perf_diff12": preprocess_diff_dicts(list(perf_diff12.T.to_dict().values())),
        "perf_diff23": preprocess_diff_dicts(list(perf_diff23.T.to_dict().values())),
        "oper_diff23": preprocess_diff_dicts(list(oper_diff23.T.to_dict().values())),
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
    
    shutil.copy(str(texpath).replace(".tex",".pdf"), pdfpath)
    
    return
