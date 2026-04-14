
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
from dataclasses import dataclass

# third-party modules
import pandas            as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from jinja2 import Template

# local modules
from epsimple import GreenRetrofitModel, Zone
from .auxiliary  import find_weatherdata
from .postprocess import (
    현장조사체크리스트,
    어린이집체크리스트,
    보건소체크리스트,
)
from .core import rebexcel_to_idf_and_grm

# settings
PLOTFONTSIZE = 11
PLOTFONTFAMILY = 'Malgun Gothic'
plt.rc('font', family=PLOTFONTFAMILY, size=PLOTFONTSIZE)
plt.rc('mathtext', fontset='custom', rm=PLOTFONTFAMILY,
       it=f'{PLOTFONTFAMILY}:italic', bf=f'{PLOTFONTFAMILY}:bold')
plt.rc('axes.formatter', useoffset=False)
plt.rc('axes', titlesize=PLOTFONTSIZE, labelsize=PLOTFONTSIZE, unicode_minus=False)
plt.rc('xtick', labelsize=PLOTFONTSIZE)
plt.rc('ytick', labelsize=PLOTFONTSIZE)
plt.rc('legend', fontsize=PLOTFONTSIZE)


# ---------------------------------------------------------------------------- #
#                                   VARIABLES                                  #
# ---------------------------------------------------------------------------- #

TEMPLATEPATH = Path(__file__).parent / "report_template.tex"
BUILD_DIR    = Path(__file__).parents[2] / "dist" / "reb-report"
FIG_DIR      = BUILD_DIR / "figures"

os.makedirs(BUILD_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)

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

MONTH_LBLS = ([f"{m}월" for m in range(1, 13)])
DEFAULT_COLORS = ("tab:blue", "tab:orange")  # epw1, epw2 색상
# PALETTE = ['#FF0305', '#363AFF', '#FF8820', '#FFFE03', '#98C1EF', '#A4C761']
PALETTE = ['#e15759', '#4e79a7', '#F28e3b', '#b07aa1', '#FFC61E', '#00CD6C', '#A1B1BA', '#A6761D']

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
    colors: list[str,str] = PALETTE[:2],
    ax: plt.Axes
) -> None:
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

    pos1 = list(range(1,13))
    shift = 0.3
    pos2 = [p + shift for p in pos1]

    bp1 = ax.boxplot(
        box1, positions=pos1, widths=0.25, patch_artist=True, showfliers=False,
        boxprops=dict(ec=colors[0], fc='none', linewidth=1.0),
        medianprops=dict(color=colors[0], linewidth=1.0),
        whiskerprops=dict(color=colors[0], linewidth=1.0),
        capprops=dict(color=colors[0], linewidth=1.0),
        flierprops=dict(markeredgecolor=colors[0], alpha=0.4, markersize=3),
    )
    bp2 = ax.boxplot(
        box2, positions=pos2, widths=0.25, patch_artist=True, showfliers=False,
        boxprops=dict(ec=colors[1], fc='none', linewidth=1.0),
        medianprops=dict(color=colors[1], linewidth=1.0),
        whiskerprops=dict(color=colors[1], linewidth=1.0),
        capprops=dict(color=colors[1], linewidth=1.0),
        flierprops=dict(markeredgecolor=colors[1], alpha=0.4, markersize=3),
    )

    # 월평균 표시(점선+마커)
    ax.plot(pos1, mean1, color=colors[0], marker="o", ms=3, linestyle="--", linewidth=1.3, label=f"{label1.split('_')[1]}년")
    ax.plot(pos2, mean2, color=colors[1], marker="o", ms=3, linestyle="--", linewidth=1.3, label=f"{label2.split('_')[1]}년")

    ax.set_xticks(range(1,13))
    ax.set_xticklabels(MONTH_LBLS, fontsize=9)
    ax.set_xlim(0.5, 12.5 + shift)
    ax.set_title("월평균 외기 온도 및 범위", fontsize=11, weight="bold")
    ax.set_ylabel("온도 (°C)")
    ax.grid(axis="both", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    all_values = pd.concat([
        df1["DryBulb"].dropna(),
        df2["DryBulb"].dropna()
    ])
    vmin, vmax = all_values.min(), all_values.max()
    margin = (vmax - vmin) * 0.1  # 상하단 10% 여유

    # ax.set_ylim(vmin - margin, vmax + margin)
    ax.set_ylim(-30, 45)
    ax.legend(fontsize=9, ncols=2, loc='upper center', bbox_to_anchor=(0.5, -0.1))


# ===== (2) HDD/CDD 비교 =====
def draw_weather_degreedays(
    epw1: str | Path,
    epw2: str | Path,
    *,
    base_temp: float = 18.0,
    label1: str | None = None,
    label2: str | None = None,
    colors: list[str,str] = PALETTE[:2],
    ax: plt.Axes
) -> None:
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
    x_positions = [0, 1, 3, 4]  # HDD1, HDD2, CDD1, CDD2
    degreedays = [hdd1, hdd2, cdd1, cdd2]
    colors_seq = [colors[0], colors[1], colors[0], colors[1]]

    bars = ax.bar(x_positions, degreedays, width=0.8, color=colors_seq, alpha=0.8)

    # --- x축 그룹 라벨 ---
    ax.set_xticks([0.5, 3.5])
    ax.set_xticklabels(["난방도일", "냉방도일"], fontsize=10)
    ax.set_ylabel("도일 (°C·day)")
    ax.set_title(f"연간 냉난방부하(도일) 비교",
                 fontsize=11, weight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # --- 막대 위 값 표시 ---
    ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=9)
    ax.set_ylim(0, max(degreedays)*1.15)

    # --- 범례 ---
    custom = [plt.Rectangle((0,0),1,1,color=colors[0],alpha=0.8),
              plt.Rectangle((0,0),1,1,color=colors[1],alpha=0.8)]
    ax.legend(custom, [f"{l.split('_')[1]}년" for l in [label1, label2]], fontsize=9, ncols=2, loc='upper center', bbox_to_anchor=(0.5, -0.1))
    
    return degreedays


def draw_weather_figures(
    before_weatherdata_filepath:str,
    after_weatherdata_filepath :str,
    ) -> tuple[plt.Figure]:

    fig, axs = plt.subplots(1, 2, figsize=(8, 3), gridspec_kw={'width_ratios': [2, 1]}, layout='constrained')
    
    draw_weather_monthlycomparision(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
        ax = axs[0]
    )
    degreedays = draw_weather_degreedays(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
        ax = axs[1]
    )
    fig.get_layout_engine().set(wspace=0.1)
    
    return fig, degreedays


def draw_3step_bargraph(
    title : str,
    values: list[list[int|float]],
    index : list[str],
    *,
    ylabel: str = "Value",
    ax    : plt.Axes
    ) -> None:

    num_bars = len(values)
    x_positions = range(num_bars) # [0, 1, 2]
    width = 0.7  # 그룹이 아니므로 막대 폭을 넓게 설정
    num_subbars =len(ENERGY_TYPES)
    subbar_width = width / num_subbars

    for n, (pos, val) in enumerate(zip(x_positions, values)):
        for et_idx, (et_key, et_label) in enumerate(ENERGY_TYPES):
            color = DEFAULT_COLORS_BEFORE[et_key]
            subbar_pos = pos - subbar_width*(num_subbars/2-et_idx-0.5)
            bar = ax.bar(subbar_pos, val[et_idx], width=subbar_width,
                   ec=None, fc=color+'90', lw=1)

    # --- 축 및 레이블 수정 ---
    # x축 눈금 위치를 막대 위치(0, 1, 2)와 동일하게 설정
    ax.set_xticks(x_positions)
    # x축 눈금 레이블을 index 리스트로 설정
    ax.set_xticklabels(index, fontsize=10)
    
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11, y=1.1)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    
    # xlim을 막대 좌우로 0.5만큼 여유 있게 설정 (-0.5 ~ 2.5)
    ax.set_xlim(-0.5, num_bars - 0.5)
    
    # bar_label이 잘 보이도록 y축 상단에 15% 여유 공간 추가
    ax.set_ylim(top=max([max(val) for val in values]) * 1.1)
    
    ax.legend(
        fontsize=8,
        handles=[
            Patch(ec=None, fc=DEFAULT_COLORS_BEFORE[et_key]+'90')
            for et_key, _ in ENERGY_TYPES
        ],
        labels=[et_label for _, et_label in ENERGY_TYPES],
        loc="upper center", ncol=4, bbox_to_anchor=(0.5, -0.15),
    )

# ---------------------------------------------------------------------------
# New functions: Python versions of HTML Chart.js visualizations
# ---------------------------------------------------------------------------

import numpy as np

GRAPH_ORDER = [
    ("heating", "난방"),
    ("cooling", "냉방"),
    ("lighting", "조명"),
    ("circulation", "팬/펌프/전열"),
    ("hotwater", "급탕"),
    ("generators", "발전량"),
]
ENERGY_TYPES = [
    ("ELECTRICITY", "전기"),
    ("NATURALGAS", "가스"),
    ("DISTRICTHEATING", "지역난방"),
]

DEFAULT_COLORS_BEFORE = {
    k: PALETTE[k_idx]
    for k_idx, k in enumerate(["NATURALGAS", "ELECTRICITY", "DISTRICTHEATING"])
}

def _draw_monthly_stacked_bar(
    category_key: str,
    category_label: str,
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    datatype: str = "source_uses",
    ax: plt.Figure | None = None
) -> plt.Figure:
    """HTML의 월별 stacked bar (ex. 난방, 냉방 등)"""

    month_labels = np.arange(1, 13)
    bottom_before = np.zeros(12)
    bottom_after = np.zeros(12)
    bottom_afterN = np.zeros(12)

    for et_key, et_label in ENERGY_TYPES:
        bvals = [
            sum(
                (-grr_before[datatype][cat_key].get(et_key, [0]*12)[m] if cat_key == "generators"
                else grr_before[datatype][cat_key].get(et_key, [0]*12)[m])
                for cat_key, _ in GRAPH_ORDER
                for et_key, _ in ENERGY_TYPES
            )
            for m in range(12)
        ]

        avals = [
            sum(
                (-grr_after[datatype][cat_key].get(et_key, [0]*12)[m] if cat_key == "generators"
                else grr_after[datatype][cat_key].get(et_key, [0]*12)[m])
                for cat_key, _ in GRAPH_ORDER
                for et_key, _ in ENERGY_TYPES
            )
            for m in range(12)
        ]

        nvals = [
            sum(
                (-grr_afterN[datatype][cat_key].get(et_key, [0]*12)[m] if cat_key == "generators"
                else grr_afterN[datatype][cat_key].get(et_key, [0]*12)[m])
                for cat_key, _ in GRAPH_ORDER
                for et_key, _ in ENERGY_TYPES
            )
            for m in range(12)
        ]

        color = DEFAULT_COLORS_BEFORE[et_key]

        ax.bar(month_labels - 0.25, bvals, width=0.25, bottom=bottom_before,
               label=f"{et_label} (전)",
               fc=color)
        ax.bar(month_labels - 0.25, bvals, width=0.25, bottom=bottom_before,
               ec=None, fc='none', zorder=5, lw=1.0)
        
        ax.bar(month_labels, avals, width=0.25, bottom=bottom_after,
               label=f"{et_label} (후)",
               ec=None, fc=color+'40', hatch='//////', lw=0.8)
        ax.bar(month_labels, avals, width=0.25, bottom=bottom_after,
               ec=None, fc='none', zorder=5, lw=1.0)

        ax.bar(month_labels + 0.25, nvals, width=0.25, bottom=bottom_afterN,
               label=f"{et_label} (N)",
               ec=None, fc=color+'40', zorder=5, lw=1.0)

        bottom_before += bvals
        bottom_after += avals
        bottom_afterN += nvals

    ax.set_xticks(month_labels)
    ax.set_xticklabels([f"{m}월" for m in month_labels])
    ax.set_ylabel("(kWh/$\\mathrm{m^2\\cdot}$월)")
    ax.set_title(f"{category_label}")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    # legend는 나중에 한 번에
    # ax.legend(fontsize=8, ncols=2)
    
    # --- ylim 자동 여유 설정 ---
    all_values = np.concatenate([
        np.array(grr_before[datatype][category_key].get(et_key, [0]*12))
        for et_key, _ in ENERGY_TYPES
    ] + [
        np.array(grr_after[datatype][category_key].get(et_key, [0]*12))
        for et_key, _ in ENERGY_TYPES
    ] + [
        np.array(grr_afterN[datatype][category_key].get(et_key, [0]*12))
        for et_key, _ in ENERGY_TYPES
    ])
    ymax = all_values.max() if len(all_values) > 0 else 0
    ax.set_ylim(0, max(5, ymax * 1.15))  # 상단 15% 여유


def _draw_monthly_stacked_bars(
    fig: plt.Figure,
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    datatype: str = "source_uses"
) -> None:
    
    axs = fig.subplots(3, 2)

    # (1) 난방, 냉방, 조명, 팬/펌프/전열, 급탕, 발전량
    for cat_idx, (cat_key, cat_label) in enumerate(GRAPH_ORDER):
        _draw_monthly_stacked_bar(
            cat_key, cat_label, grr_before, grr_after, grr_afterN, datatype,
            ax = axs.ravel()[cat_idx]
        )

    handles = []
    labels = []
    for et_key, et_label in ENERGY_TYPES:
        for l_idx, label in enumerate(["GR 이전", "GR 이후", "(운영특성 반영)"]):
            color = DEFAULT_COLORS_BEFORE[et_key]
            handles.append(Patch(ec=None, lw=0.8,
                                 fc=[color, color+'40', color+'40'][l_idx],
                                 hatch=[None, '//////', None][l_idx]))
            labels.append(f"{et_label} {label}")

    legend_ncol = 3

    fig.legend(
        handles=handles,
        labels=labels,
        loc='outside lower center', ncol=legend_ncol,
    )


def _draw_annual_by_purpose(ax: plt.Axes, grr_before: dict, grr_after: dict, grr_afterN: dict, datatype="source_uses") -> None:
    """HTML의 연간 용도별 stacked bar (bar-annual-by-purpose)"""
    x = np.arange(len(GRAPH_ORDER))
    width = 0.25

    ymax = -np.inf
    for idx, (label, dataset) in enumerate([
        ("GR 이전", grr_before),
        ("GR 이후", grr_after),
        ("(운영특성 반영)", grr_afterN),
    ]):
        bottoms = np.zeros(len(GRAPH_ORDER))
        for et_key, et_label in ENERGY_TYPES:
            vals = [
                sum(dataset[datatype][cat_key].get(et_key, [0]*12))
                for cat_key, _ in GRAPH_ORDER
            ]
            color = DEFAULT_COLORS_BEFORE[et_key]
            ax.bar(x + (idx - 1) * width, vals, width=width,
                   bottom=bottoms,
                   label=f"{et_label} {label}",
                   ec=None, lw=0.8,
                   fc=[color, color+'40', color+'40'][idx],
                   hatch=[None, '//////', None][idx])
            ax.bar(x + (idx - 1) * width, vals, width=width,
                   bottom=bottoms, ec=None, fc='none', zorder=5, lw=1.0)
            bottoms += vals
            ymax = max(ymax, bottoms.max())

    ax.set_ylim(0, max(5, ymax * 1.15))  # 상단 15% 여유

    ax.set_xticks(x)
    ax.set_xticklabels([lbl.replace('/', '/\n') for _, lbl in GRAPH_ORDER])
    ax.set_ylabel("연간 합계 (kWh/$\\mathrm{m^2\\cdot}$연)")
    ax.set_title("연간 용도별 1차에너지소요량")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

def _draw_total_monthly_bar(ax: plt.Axes, grr_before: dict, grr_after: dict, grr_afterN: dict, datatype="source_uses") -> None:
    """HTML의 bar-total (월별 총합 비교 - 막대그래프)"""
    months = np.arange(1, 13)
    
    # 막대 너비 설정
    width = 0.25 

    before_vals = grr_before["summary_per_area"][datatype]["total_monthly"]
    after_vals = grr_after["summary_per_area"][datatype]["total_monthly"]
    afterN_vals = grr_afterN["summary_per_area"][datatype]["total_monthly"]

    # x축 위치를 조정하여 막대를 그립니다 (왼쪽, 가운데, 오른쪽)
    # zorder=3을 주어 그리드 위로 막대가 올라오게 합니다.
    ax.bar(months - width, before_vals, width=width, color=PALETTE[0], label="GR 이전", zorder=3)
    ax.bar(months, after_vals, width=width, color=PALETTE[1], label="GR 이후", zorder=3)
    
    # (운영특성 반영)은 기존 스타일(점선/빈 원)을 반영하여 빗금(hatch)이나 테두리 스타일로 표현
    ax.bar(months + width, afterN_vals, width=width, 
           color='white', edgecolor=PALETTE[2], hatch='////', linewidth=1.0, 
           label="(운영특성 반영)", zorder=3)

    ax.set_ylim(bottom=0)
    ax.set_xticks(months)
    ax.set_xticklabels([f"{m}월" for m in months])
    ax.set_ylabel("월별 합계 (kWh/$\\mathrm{m^2\\cdot}$월)")
    ax.set_title("월별 1차에너지소요량", y=1.1)
    
    # 그리드가 막대 뒤로 가도록 설정
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0) 
    ax.legend(fontsize=8, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.15))


def draw_simulation_figures(grr_before: dict, grr_after: dict, grr_afterN: dict):
    """
    matplotlib로 두 개의 Figure(메인 그래프, 요약 그래프)를 생성하여 반환
    Returns:
        fig1 (Figure): 용도별, 월별 사용량 비교 (상단 큰 그래프)
        fig2 (Figure): 연간 용도별 비교 및 월별 총합 라인 (하단 요약 그래프)
    """
    
    # --- Figure 1: 월별 스택 바 (메인) ---
    # 기존 비율(3:1.2)을 고려하여 세로 길이를 적절히 배분 (예: 높이 8)
    fig1 = plt.figure(figsize=(9, 8), constrained_layout=True)
    
    # 기존 helper 함수가 Figure 객체를 받아 subplot을 추가한다고 가정
    _draw_monthly_stacked_bars(fig1, grr_before, grr_after, grr_afterN)

    fig1.suptitle('월간 단위면적당 1차에너지소요량', fontsize=16, fontweight='bold')


    # --- Figure 2: 요약 (하단 2개 그래프) ---
    # 높이를 작게 설정 (예: 높이 4)
    fig2 = plt.figure(figsize=(9, 3), constrained_layout=True)
    
    # 1행 2열로 서브플롯 생성
    summary_axs = fig2.subplots(1, 2)

    # (3) 월별 총합 라인 그래프
    _draw_total_monthly_bar(summary_axs[0], grr_before, grr_after, grr_afterN)

    draw_3step_bargraph(
        "면적당 1차에너지소요량 (연간)",
        [
            [
                sum([
                    # cat이 'generators'이면 음수(-)로, 아니면 양수(+)로 합산
                    -sum(result["source_uses"][cat][et_key]) if cat == "generators" 
                    else sum(result["source_uses"][cat][et_key])
                    
                    for cat, _ in GRAPH_ORDER
                ])
                for et_key, _ in ENERGY_TYPES
            ]
            for result in [grr_before, grr_after, grr_afterN]
        ],
        ["GR이전","GR이후","(운영특성 반영)"],
        ylabel = "1차에너지 (kWh/$\\mathrm{m^2\\cdot}$년)",
        ax = summary_axs[1]
    )
    
    return fig1, fig2

def draw_page3_summaryfigure(
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    ) -> plt.Figure:
    
    fig = plt.figure(figsize=(9, 3), constrained_layout=True)
    axes = fig.subplots(1, 2)
    
    _draw_annual_by_purpose(
        axes[0],
        grr_before, grr_after, grr_afterN,  "source_uses"
    )
    
    draw_3step_bargraph(
        "면적당 온실가스 배출량 (연간)",
        [
            [
                sum([
                    # cat이 'generators'이면 음수(-)로, 아니면 양수(+)로 합산
                    -sum(result["co2"][cat][et_key]) if cat == "generators" 
                    else sum(result["co2"][cat][et_key])
                    
                    for cat, _ in GRAPH_ORDER
                ])
                for et_key, _ in ENERGY_TYPES
            ]
            for result in [grr_before, grr_after, grr_afterN]
        ],
        ["GR이전","GR이후","(운영특성 반영)"],
        ylabel = r"$\mathrm{CO_2,eq}$ (kg/$\mathrm{m^2\cdot}$년)",
        ax = axes[1]
    )
    
    fig.suptitle('요약', fontsize=16, fontweight='bold')
    
    return fig
    

# ---------------------------------------------------------------------------- #
#                                   MAIN FUNC                                  #
# ---------------------------------------------------------------------------- #

def escape_str(v:str):
    
    v = v.replace(r"_",r"\_")
    v = v.replace(r"&", r"\&")
    v = v.replace(r"%", r"\%")
    v = v.replace(r"~", r"\textasciitilde{}")
    v = v.replace(r"#", r"\#")
    
    return v

def preprocess_diff_dicts(
    diffs:list[dict]
    ) -> list[dict]:
    
    def mapper(v):
        
        if isinstance(v, str):
            v = escape_str(v)
        
        if isinstance(v, int|float):
            v = f"{v:.10f}".rstrip("0").rstrip(".")
        
        return v
    
    return [
        {k:mapper(v) for k, v in d.items()
        }
        for d in diffs
    ]
    

def summarytable(
    grrbefore:dict,
    grrafter :dict,
    grrafterN:dict,
    ) -> pd.DataFrame:
    
    df1 = pd.DataFrame(
        [
            [
                grrbefore["summary_per_area"]["source_uses"]["total_annual"],
                grrafter["summary_per_area"]["source_uses"]["total_annual"],
                grrafterN["summary_per_area"]["source_uses"]["total_annual"],
            ],
            [
                grrbefore["summary_per_area"]["co2"]["total_annual"],
                grrafter["summary_per_area"]["co2"]["total_annual"],
                grrafterN["summary_per_area"]["co2"]["total_annual"],
            ],
        ],
        columns=["GR 이전 (①)", "GR 이후 (②)", "운영특성 반영시 (③)"],
        index  =["1차에너지[$kWh/m^2$]", "온실가스[$kgCO_{2,eq}/m^2$]"]
    )
    
    df2 = pd.DataFrame(
        columns=["GR 감축량 (①-②)","운영특성 반영 감축량 (①-③)","운영특성 반영 영향 (③-②)"],
        index  =["1차에너지[$kWh/m^2$]", "온실가스[$kgCO_{2,eq}/m^2$]"]
        )
    df2["GR 감축량 (①-②)"] = df1["GR 이전 (①)"] - df1["GR 이후 (②)"]
    df2["운영특성 반영 감축량 (①-③)"] = df1["GR 이전 (①)"] - df1["운영특성 반영시 (③)"]
    df2["운영특성 반영 영향 (③-②)"] = df1["운영특성 반영시 (③)"] - df1["GR 이후 (②)"]
    
    return df1, df2

def parse_activechange(
    grm1:GreenRetrofitModel,
    grm2:GreenRetrofitModel,
    ) -> tuple[str]:
    
    # heating and cooling hvac
    def hvac2str(zone:Zone) -> str:
        
        if zone.heating_supply is None:
            heatingstr =  ""
        else:
            heatingstr =  f"{zone.heating_supply}\n{zone.heating_supply.source}"
            
        if zone.cooling_supply is None:
            coolingstr =  ""
        else:
            coolingstr =  f"{zone.cooling_supply}\n{zone.cooling_supply.source}"

        return heatingstr, coolingstr
    
    hvacdict1 = {
        zone.name: hvac2str(zone)
        for zone in grm1.zone
    }
    hvacdict2 = {
        zone.name: hvac2str(zone)
        for zone in grm2.zone
    }
    
    heatingchanged = 0
    coolingchanged = 0
    for zonename in hvacdict1.keys():
        if zonename in hvacdict2.keys() and (hvacdict1[zonename][0] != hvacdict2[zonename][0]):
            heatingchanged += 1
        if zonename in hvacdict2.keys() and (hvacdict1[zonename][1] != hvacdict2[zonename][1]):
            coolingchanged += 1
    
    if heatingchanged == 0:
        heatingchangestr = "변화 없음."
    else:
        heatingchangestr = f"{heatingchanged}개 실에 영향을 주는 교체 있음."
        
    if coolingchanged == 0:
        coolingchangestr = "변화 없음."
    else:
        coolingchangestr = f"{coolingchanged}개 실에 영향을 주는 교체 있음."
    
    # ventilation
    ventdict1 = {
        zone.name: zone.ventilation_system
        for zone in grm1.zone
    }
    ventdict2 = {
        zone.name: zone.ventilation_system
        for zone in grm2.zone
    }
    
    ventadded   = 0 
    ventchanged = 0
    for zonename in ventdict1.keys():
        if zonename in ventdict2.keys():
            if ventdict1[zonename] is None and ventdict2[zonename] is not None:
                ventadded += 1
            elif str(ventdict1[zonename]) != str(ventdict2[zonename]):
                ventchanged += 1
    
    if ventadded == 0 and ventchanged == 0:
        ventchangedstr = "변화 없음."
    elif ventadded == 0 and ventchanged > 0:
        ventchangedstr = f"{ventchanged}개 실에서 전열교환기 교체됨."
    elif ventadded > 0 and ventchanged == 0:
        ventchangedstr = f"{ventadded}개 실에서 전열교환기 추가됨."
    else:
        ventchangedstr =  f"{ventadded}개 실에 전열교환기 추가, {ventchanged}개 실에서 전열교환기 교체됨."
    
    return heatingchangestr, coolingchangestr, ventchangedstr

def parse_hvacoperationchange(
    checklist1:현장조사체크리스트,
    checklist2:현장조사체크리스트,
    ) -> tuple[str]:
    
    func_certaincoolingsetpoint = lambda x: x if isinstance(x, int|float) else 26
    func_certainheatingsetpoint = lambda x: x if isinstance(x, int|float) else 20
    
    # heating
    if checklist1.일반존.난방설비1 is None:
        heatingtime1     = "사용안함"
        heatingsetpoint1 = "(없음)"
    else:
        heatingtime1 = f"{checklist1.일반존.난방설비1.사용기간} {checklist1.일반존.난방설비1.사용시간}"
        heatingsetpoint1 = f"{func_certainheatingsetpoint(checklist1.일반존.난방설비1.설정온도):.1f}$^\\circ C$"
        
    if checklist2.일반존.난방설비1 is None:
        heatingtime2     = "사용안함"
        heatingsetpoint2 = "(없음)"
    else:
        heatingtime2 = f"{checklist2.일반존.난방설비1.사용기간} {checklist2.일반존.난방설비1.사용시간}"
        heatingsetpoint2 = f"{func_certainheatingsetpoint(checklist2.일반존.난방설비1.설정온도):.1f}$^\\circ C$"
    
    if heatingtime1 == heatingtime2:
        heatingtime = "변화 없음."
    else:
        heatingtime = f"{heatingtime1} $\\rightarrow$ {heatingtime2}"
    
    if heatingsetpoint1 == heatingsetpoint2:
        heatingsetpoint = "변화 없음."
    else:
        heatingsetpoint = f"{heatingsetpoint1} $\\rightarrow$ {heatingsetpoint2}"
    
    # cooling
    if checklist1.일반존.냉방설비1 is None:
        coolingtime1     = "사용안함"
        coolingsetpoint1 = "(없음)"
    else:
        coolingtime1 = f"{checklist1.일반존.냉방설비1.사용기간} {checklist1.일반존.냉방설비1.사용시간}"
        coolingsetpoint1 = f"{func_certaincoolingsetpoint(checklist1.일반존.냉방설비1.설정온도):.1f}$^\\circ C$"
        
    if checklist2.일반존.냉방설비1 is None:
        coolingtime2     = "사용안함"
        coolingsetpoint2 = "(없음)"
    else:
        coolingtime2 = f"{checklist2.일반존.냉방설비1.사용기간} {checklist2.일반존.냉방설비1.사용시간}"
        coolingsetpoint2 = f"{func_certaincoolingsetpoint(checklist2.일반존.냉방설비1.설정온도):.1f}$^\\circ C$"
    
    if coolingtime1 == coolingtime2:
        coolingtime = "변화 없음."
    else:
        coolingtime = f"{coolingtime1} $\\rightarrow$ {coolingtime2}"
    
    if coolingsetpoint1 == coolingsetpoint2:
        coolingsetpoint = "변화 없음."
    else:
        coolingsetpoint = f"{coolingsetpoint1} $\\rightarrow$ {coolingsetpoint2}"
        
    df = pd.DataFrame(
            [
                [heatingtime1, heatingsetpoint1, coolingtime1, coolingsetpoint1],
                [heatingtime2, heatingsetpoint2, coolingtime2, coolingsetpoint2], 
            ],
            columns = ["난방 사용시간", "난방 설정온도", "냉방 사용시간", "냉방 설정온도"],
            index   = ["GR 직후", "2025년"], 
    )
    
    tablestyle = {
        "column_format":">{\\centering\\arraybackslash}p{3cm}" + "|>{\\centering\\arraybackslash}p{3.325cm}" * 4,
        "clines":"all;data",  
        "hrules":True,
        }
    tex =  df.style.to_latex(**tablestyle).replace(r"\toprule", r"\hline").replace(r"\midrule", r"\hline").replace(r"\bottomrule", r"\hline").replace("~","-")
        
    
    return tex

def parse_occupantchange(
    checklist1:현장조사체크리스트,
    checklist2:현장조사체크리스트,
    ):
    
    if isinstance(checklist1, 어린이집체크리스트):
        
        func_nanto0 =  lambda x: 0 if pd.isna(x) else x
        
        df = pd.DataFrame(
            [
                [
                    func_nanto0(checklist1.일반존.기본보육교사  + checklist1.일반존.기본보육원생),
                    func_nanto0(checklist1.일반존.연장보육A교사 + checklist1.일반존.연장보육A원생),
                    func_nanto0(checklist1.일반존.연장보육B교사 + checklist1.일반존.연장보육B원생),
                    func_nanto0(checklist1.일반존.야간보육교사  + checklist1.일반존.야간보육원생),
                    func_nanto0(checklist1.일반존.주말보육교사  + checklist1.일반존.주말보육원생),
                ],
                                [
                    func_nanto0(checklist2.일반존.기본보육교사  + checklist2.일반존.기본보육원생),
                    func_nanto0(checklist2.일반존.연장보육A교사 + checklist2.일반존.연장보육A원생),
                    func_nanto0(checklist2.일반존.연장보육B교사 + checklist2.일반존.연장보육B원생),
                    func_nanto0(checklist2.일반존.야간보육교사  + checklist2.일반존.야간보육원생),
                    func_nanto0(checklist2.일반존.주말보육교사  + checklist2.일반존.주말보육원생),
                ]    
            ],
            columns = ["기본 (-16:00)", "연장 (-18:00)", "연장 (-19:30)","야간 (-21:00)","주말"],
            index   = ["GR 직후", "2025년"] 
        )
        
        tablestyle = {
            "column_format":">{\\centering\\arraybackslash}p{3cm}" + "|>{\\centering\\arraybackslash}p{2.66cm}" * 5,
            "clines":"all;data",  
            "hrules":True,
            }
        tex = df.style.format(lambda x: f"{x}명").to_latex(**tablestyle).replace(r"\toprule", r"\hline").replace(r"\midrule", r"\hline").replace(r"\bottomrule", r"\hline")
        
        return tex
    
    else:
        
        집중진료연인원1 = ((checklist1.일반존.집중진료오전방문객 * checklist1.일반존.집중진료오전체류시간) + (checklist1.일반존.집중진료오후방문객 * checklist1.일반존.집중진료오후체류시간))/60 * len(checklist1.일반존.집중진료요일.split(","))
        집중진료연인원2 = ((checklist2.일반존.집중진료오전방문객 * checklist2.일반존.집중진료오전체류시간) + (checklist2.일반존.집중진료오후방문객 * checklist2.일반존.집중진료오후체류시간))/60 * len(checklist2.일반존.집중진료요일.split(","))
        
        df = pd.DataFrame(
            [
                [
                    f"{checklist1.일반존.운영시간.replace("~","-")}",
                    f"{checklist1.일반존.직원}명 상주",
                    f"주 {집중진료연인원1:.0f}명$\\cdot$시간",
                    f"{checklist1.특화존2.사용관사수}개소",
                ],
                [
                    f"{checklist2.일반존.운영시간.replace("~","-")}",
                    f"{checklist2.일반존.직원}명 상주",
                    f"주 {집중진료연인원1:.0f}명$\\cdot$시간",
                    f"{checklist2.특화존2.사용관사수}개소",
                ]    
            ],
            columns = ["운영시간", "직원", "집중진료 방문객","이용 관사 수"],
            index   = ["GR 직후", "2025년"] 
        )
        
        tablestyle = {
            "column_format":">{\\centering\\arraybackslash}p{3cm}" + "|>{\\centering\\arraybackslash}p{3.325cm}" * 4,
            "clines":"all;data",  
            "hrules":True,
            }
        tex =  df.style.to_latex(**tablestyle).replace(r"\toprule", r"\hline").replace(r"\midrule", r"\hline").replace(r"\bottomrule", r"\hline").replace("~","-")
        
        return tex

def bool_to_적용(b:bool|list[bool]) -> str|list[str]:
    
    if isinstance(b, list):
        return [bool_to_적용(bi) for bi in b]
    
    return "적용" if b else "미적용"
    
def get_passivechange_bool(
    grm1:GreenRetrofitModel,
    grm2:GreenRetrofitModel,
    ) -> list[bool]:
    
    bools = [False]*5 # 벽체, 지붕, 바닥, 창호, 쿨루프
    
    # 벽체
    if round(grm1.averaged_exteriorwall_Uvalue,3) != round(grm2.averaged_exteriorwall_Uvalue,3):
        bools[0] = True
        
    # 지붕
    if round(grm1.averaged_exteriorroof_Uvalue,3) != round(grm2.averaged_exteriorroof_Uvalue,3):
        bools[1] = True
    
    # 바닥
    if round(grm1.averaged_exteriorfloor_Uvalue,3) != round(grm2.averaged_exteriorfloor_Uvalue,3):
        bools[2] = True
    
    # 창호
    if round(grm1.averaged_window_Uvalue,3) != round(grm2.averaged_window_Uvalue,3):
        bools[3] = True
    
    # 쿨루프
    coolroof1 = [roof for roof in grm1.exteriorroofs if roof.reflectance is not None]
    coolroof2 = [roof for roof in grm2.exteriorroofs if roof.reflectance is not None]
    if len(coolroof1) < len(coolroof2):
        bools[4] = True
        
    return bools

def get_activechange_bool(
    grm1:GreenRetrofitModel,
    grm2:GreenRetrofitModel,
    ) -> list[bool]:
    
    bools = [False]*5 # 난방, 냉방, 환기, 조명, 태양광
    
    heatingchanged, coolingchanged, ventchanged = parse_activechange(grm1, grm2)
    
    if heatingchanged != "변화 없음.":
        bools[0] = True
    if coolingchanged != "변화 없음.":
        bools[1] = True
    if ventchanged != "변화 없음.":
        bools[2] = True
        
    # 조명
    if round(grm1.averaged_lightdensity,3) != round(grm2.averaged_lightdensity,3):
        bools[3] = True
        
    # 태양광
    if len(grm1.pv) != len(grm2.pv):
        bools[4] = True
    elif any(
        round(pv1.efficiency,3) != round(pv2.efficiency,3) or
        round(pv1.area,3) != round(pv2.area,3) or
        round(pv1.azimuth,2) != round(pv2.azimuth,2) or
        round(pv1.tilt,2) != round(pv2.tilt,2)
        for pv1, pv2 in zip(grm1.pv, grm2.pv)
    ):
        bools[4] = True
    
    return bools

def build_report(
    before_rebexcelpath:str,
    after_rebexcelpath :str,
    afterN_rebexcelpath:str,
    before_grrpath:str,
    after_grrpath :str,
    afterN_grrpath:str,
    commentdict   :dict[str,str],
    masterdict    :dict,
    pdfpath:str,
    ) -> None:
    
    # resultdata
    with open(before_grrpath, "r") as f:
        grrbefore = json.load(f)
    with open(after_grrpath, "r") as f:
        grrafter  = json.load(f)
    with open(afterN_grrpath, "r") as f:
        grrafterN = json.load(f)
    
    # checklist
    checklistbefore = 현장조사체크리스트.from_excel(before_rebexcelpath)
    checklistafter  = 현장조사체크리스트.from_excel(after_rebexcelpath)
    checklistafterN = 현장조사체크리스트.from_excel(afterN_rebexcelpath)
    
    # model
    idfbefore, grmbefore = rebexcel_to_idf_and_grm(before_rebexcelpath)
    idfafter , grmafter  = rebexcel_to_idf_and_grm(after_rebexcelpath)
    idfafterN, grmafterN = rebexcel_to_idf_and_grm(afterN_rebexcelpath)
    
    # metadata
    building_info = pd.read_excel(before_rebexcelpath, sheet_name="건물정보", usecols=range(6), nrows=1).iloc[0]
    metadata = MetaData(
        escape_str(building_info["건물명"])     ,
        f"{grrbefore["building"]["total_area"]:.1f}",
        building_info["주소"],
        building_info["허가일자"]   , 
    )
    
    # passive change
    passivechangedict = {
        "before": {
            "wallU": round(grmbefore.averaged_exteriorwall_Uvalue,3),
            "roofU": round(grmbefore.averaged_exteriorroof_Uvalue,3),
            "floorU": round(grmbefore.averaged_exteriorfloor_Uvalue,3),
            "winU" : round(grmbefore.averaged_window_Uvalue,3),
            "ld"   : round(grmbefore.averaged_lightdensity,2),
        },
        "after": {
            "wallU": round(grmafter.averaged_exteriorwall_Uvalue,3),
            "roofU": round(grmafter.averaged_exteriorroof_Uvalue,3),
            "floorU": round(grmafter.averaged_exteriorfloor_Uvalue,3),
            "winU" : round(grmafter.averaged_window_Uvalue,3),
            "ld"   : round(grmafter.averaged_lightdensity,2),
        },
        "afterN": {
            "wallU": round(grmafterN.averaged_exteriorwall_Uvalue,3),
            "roofU": round(grmafterN.averaged_exteriorroof_Uvalue,3),
            "floorU": round(grmafterN.averaged_exteriorfloor_Uvalue,3),
            "winU" : round(grmafterN.averaged_window_Uvalue,3),
            "ld"   : round(grmafterN.averaged_lightdensity,2),
            "infil": round(grmafterN.averaged_infiltration*0.07,2),
        },
        "before2after": bool_to_적용(get_passivechange_bool(grmbefore, grmafter)),
        "countbefore2after": sum(get_passivechange_bool(grmbefore, grmafter)),
        "after2afterN": bool_to_적용(get_passivechange_bool(grmafter, grmafterN)),
        "countafter2afterN": sum(get_passivechange_bool(grmafter, grmafterN)),
    }
    # active change
    activechange_before2after = parse_activechange(grmbefore, grmafter)
    activechange_after2afterN = parse_activechange(grmafter, grmafterN)
    activechangedict = {
        "before2after": bool_to_적용(get_activechange_bool(grmbefore, grmafter)),
        "countbefore2after": sum(get_activechange_bool(grmbefore, grmafter)),
        "after2afterN": bool_to_적용(get_activechange_bool(grmafter, grmafterN)),
        "countafter2afterN": sum(get_activechange_bool(grmafter, grmafterN)),
        "before2afterdetail":{
            "heating": activechange_before2after[0],
            "cooling": activechange_before2after[1],
            "ventilation": activechange_before2after[2],
        },
        "after2afterNdetail":{
            "heating": activechange_after2afterN[0],
            "cooling": activechange_after2afterN[1],
            "ventilation": activechange_after2afterN[2],
        }
    }
    
    # occupant change
    occupantchange = parse_occupantchange(checklistafter, checklistafterN)
    # hvacoperation change
    hvacoperationchange = parse_hvacoperationchange(checklistafter, checklistafterN)
    
    # get figures
    fig_detail, fig_summary = draw_simulation_figures(grrbefore, grrafter, grrafterN)
    fig_detail.savefig(FIG_DIR / "simulation_results.png", dpi=400, format="png", bbox_inches="tight")
    fig_summary.savefig(FIG_DIR / "energy_summary.png", dpi=400, format="png", bbox_inches="tight")
    
    # get figures (by weather)
    before_weatherdata_filepath = find_weatherdata(building_info["주소"], "이전")
    after_weatherdata_filepath  = find_weatherdata(building_info["주소"], "이후")
    fig_weather, degreedays = draw_weather_figures(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
    )
    fig_weather.savefig(FIG_DIR / "weather_compare.png", dpi=400, format="png", bbox_inches="tight")
    fig_page3_summary = draw_page3_summaryfigure(grrbefore, grrafter, grrafterN)
    fig_page3_summary.savefig(FIG_DIR / "page3_summary.png", dpi=400, format="png", bbox_inches="tight")
        
    # arrange the results
    summarytablestyle = {
    "column_format":">{\\centering\\arraybackslash}p{4cm}" + "|>{\\centering\\arraybackslash}p{4.5cm}" * 3,
    "clines":"all;data",  
    "hrules":True,
    }
    context = {
        "metadata": metadata,
        "master"  : masterdict,
        "imagesrc": (Path(__file__).parent / "imagesrc").resolve().as_posix(),
        "passivechange": passivechangedict,
        "activechange": activechangedict,
        "hvacoperchangetex": hvacoperationchange,
        "occupantchangetex": occupantchange,
        "summarytabletex" : [df.style.format(lambda x: f"{x:>6,.1f}").to_latex(**summarytablestyle).replace(r"\toprule", r"\hline").replace(r"\midrule", r"\hline").replace(r"\bottomrule", r"\hline") for df in summarytable(grrbefore, grrafter, grrafterN)],
        "degreedays": {k:v for k,v in zip(["HDD2018","HDD2023","CDD2018","CDD2023"], degreedays)}|{"HDDchange": ("증가" if (degreedays[1]-degreedays[0])>0 else "감소"),"CDDchange": ("증가" if (degreedays[3]-degreedays[2])>0 else "감소")},
        "comment": {k:escape_str(v) for k,v in commentdict.items()}
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
