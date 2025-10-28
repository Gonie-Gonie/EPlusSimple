
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
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from jinja2 import Template

# local modules
from .comparison import compare_rebexcel
from .auxiliary  import find_weatherdata

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
PALETTE = ['#FF1F5B', '#009ADE', '#F28522', '#AF59BA', '#FFC61E', '#00CD6C', '#A1B1BA', '#A6761D']

def _apply_axis_style(ax, title:str=None, ylabel:str=None):
    if title:
        ax.set_title(title, fontsize=11, weight="bold")
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
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
    ax.plot(pos1, mean1, color=colors[0], marker="o", linestyle="--", linewidth=1.3, label=f"{label1} mean")
    ax.plot(pos2, mean2, color=colors[1], marker="o", linestyle="--", linewidth=1.3, label=f"{label2} mean")

    _apply_axis_style(ax, "월간 외기 온도", "건구 온도 (°C)")
    ax.set_xlim(0.5, 12.5 + shift)
    all_values = pd.concat([
        df1["DryBulb"].dropna(),
        df2["DryBulb"].dropna()
    ])
    vmin, vmax = all_values.min(), all_values.max()
    margin = (vmax - vmin) * 0.1  # 상하단 10% 여유

    ax.set_ylim(vmin - margin, vmax + margin)
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
    heights = [hdd1, hdd2, cdd1, cdd2]
    colors_seq = [colors[0], colors[1], colors[0], colors[1]]

    bars = ax.bar(x_positions, heights, width=0.8, color=colors_seq, alpha=0.8)

    # --- x축 그룹 라벨 ---
    ax.set_xticks([0.5, 3.5])
    ax.set_xticklabels(["HDD", "CDD"], fontsize=10)
    ax.set_ylabel("도일 (°C·day)")
    ax.set_title(f"연간 HDD/CDD 비교 ({base_temp:.1f}°C 기준)",
                 fontsize=11, weight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # --- 막대 위 값 표시 ---
    ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=9)
    ax.set_ylim(0, max(heights)*1.15)

    # --- 범례 ---
    custom = [plt.Rectangle((0,0),1,1,color=colors[0],alpha=0.8),
              plt.Rectangle((0,0),1,1,color=colors[1],alpha=0.8)]
    ax.legend(custom, [label1, label2], fontsize=9, ncols=2, loc='upper center', bbox_to_anchor=(0.5, -0.1))


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
    draw_weather_degreedays(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
        ax = axs[1]
    )
    fig.get_layout_engine().set(wspace=0.1)
    
    return fig


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
            #? step별로 구분
            # ax.bar(subbar_pos, val[et_idx], width=subbar_width,
            #        ec=color, lw=0.8,
            #        fc=[color, color+'40', color+'40'][n],
            #        hatch=[None, '//////', None][n])
            # bar = ax.bar(subbar_pos, val[et_idx], width=subbar_width,
            #        ec='k', fc='none', zorder=5, lw=1.0)
            #? 모두 같은 스타일
            bar = ax.bar(subbar_pos, val[et_idx], width=subbar_width,
                   ec='k', fc=color+'90', lw=1)
            #? 테두리 없이
            # bar = ax.bar(subbar_pos, val[et_idx], width=subbar_width,
            #        fc=color, lw=0)
        
            # 막대 위에 값 표시 (padding을 3 정도로 살짝 띄움)
            # ax.bar_label(bar, fmt="%.1f", padding=3 + 10*(et_idx%2), fontsize=9)

    # --- 축 및 레이블 수정 ---
    # x축 눈금 위치를 막대 위치(0, 1, 2)와 동일하게 설정
    ax.set_xticks(x_positions)
    # x축 눈금 레이블을 index 리스트로 설정
    ax.set_xticklabels(index, fontsize=10)
    
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11, weight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    
    # xlim을 막대 좌우로 0.5만큼 여유 있게 설정 (-0.5 ~ 2.5)
    ax.set_xlim(-0.5, num_bars - 0.5)
    
    # bar_label이 잘 보이도록 y축 상단에 15% 여유 공간 추가
    ax.set_ylim(top=max([max(val) for val in values]) * 1.1)

def draw_energysimulation_figures(
    grrbefore:dict,
    grrafter :dict,
    grrafterN:dict,
    ) -> tuple[plt.Figure]:

    fig, axs = plt.subplots(1, 2, figsize=(8, 3), layout='constrained')
    
    # ENERGY_TYPES 순서대로 입력
    draw_3step_bargraph(
        "에너지 사용량 비교",
        [
            [
                sum([
                    sum(result["site_uses"][cat][et_key])
                    for cat, _ in GRAPH_ORDER
                ])
                for et_key, _ in ENERGY_TYPES
            ]
            for result in [grrbefore, grrafter, grrafterN]
        ],
        ["GR이전","GR이후","N년차"],
        ylabel = r"(kWh/$\mathrm{m^2\cdot}$년)",
        ax = axs[0]
    )
    
    draw_3step_bargraph(
        "온실가스 배출량 비교",
        [
            [
                sum([
                    sum(result["co2"][cat][et_key])
                    for cat, _ in GRAPH_ORDER
                ])
                for et_key, _ in ENERGY_TYPES
            ]
            for result in [grrbefore, grrafter, grrafterN]
        ],
        ["GR이전","GR이후","N년차"],
        ylabel = r"$\mathrm{CO_2}$ 배출량 (kg/$\mathrm{m^2\cdot}$년)",
        ax = axs[1]
    )

    fig.legend(
        handles=[
            Patch(ec='k', fc=DEFAULT_COLORS_BEFORE[et_key]+'90')
            # Patch(color=DEFAULT_COLORS_BEFORE[et_key])
            for et_key, _ in ENERGY_TYPES
        ],
        labels=[et_label for _, et_label in ENERGY_TYPES],
        loc='outside lower center', ncol=4,
        # bbox_to_anchor=(0.5, 0.95)
    )

    fig.get_layout_engine().set(wspace=0.1)
    
    return fig

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
    ("OIL", "유류"),
    ("DISTRICTHEATING", "지역난방"),
]

DEFAULT_COLORS_BEFORE = {
    k: PALETTE[k_idx]
    for k_idx, k in enumerate(["ELECTRICITY", "NATURALGAS", "OIL", "DISTRICTHEATING"])
}

def _draw_monthly_stacked_bar(
    category_key: str,
    category_label: str,
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    datatype: str = "site_uses",
    ax: plt.Figure | None = None
) -> plt.Figure:
    """HTML의 월별 stacked bar (ex. 난방, 냉방 등)"""

    month_labels = np.arange(1, 13)
    bottom_before = np.zeros(12)
    bottom_after = np.zeros(12)
    bottom_afterN = np.zeros(12)

    for et_key, et_label in ENERGY_TYPES:
        bvals = np.array(grr_before[datatype][category_key].get(et_key, [0]*12))
        avals = np.array(grr_after[datatype][category_key].get(et_key, [0]*12))
        nvals = np.array(grr_afterN[datatype][category_key].get(et_key, [0]*12))

        color = DEFAULT_COLORS_BEFORE[et_key]

        ax.bar(month_labels - 0.25, bvals, width=0.25, bottom=bottom_before,
               label=f"{et_label} (전)",
               fc=color)
        ax.bar(month_labels - 0.25, bvals, width=0.25, bottom=bottom_before,
               ec='k', fc='none', zorder=5, lw=1.0)
        
        ax.bar(month_labels, avals, width=0.25, bottom=bottom_after,
               label=f"{et_label} (후)",
               ec=color, fc=color+'40', hatch='//////', lw=0.8)
        ax.bar(month_labels, avals, width=0.25, bottom=bottom_after,
               ec='k', fc='none', zorder=5, lw=1.0)
        
        ax.bar(month_labels + 0.25, nvals, width=0.25, bottom=bottom_afterN,
               label=f"{et_label} (N)",
               ec='k', fc=color+'40', zorder=5, lw=1.0)

        bottom_before += bvals
        bottom_after += avals
        bottom_afterN += nvals

    ax.set_xticks(month_labels)
    ax.set_xticklabels([f"{m}월" for m in month_labels])
    ax.set_ylabel("단위당 값")
    ax.set_title(f"{category_label} 월별 비교")
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
    datatype: str = "site_uses"
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
        for l_idx, label in enumerate(["GR 이전", "GR 이후", "GR N년차"]):
            color = DEFAULT_COLORS_BEFORE[et_key]
            handles.append(Patch(ec=color, lw=0.8,
                                 fc=[color, color+'40', color+'40'][l_idx],
                                 hatch=[None, '//////', None][l_idx]))
            labels.append(f"{et_label} {label}")

    legend_ncol = 4
    # handles = np.array(handles).reshape(-1, legend_ncol).T.flatten().tolist()
    # labels = np.array(labels).reshape(-1, legend_ncol).T.flatten().tolist()

    fig.legend(
        handles=handles,
        labels=labels,
        loc='outside upper center', ncol=legend_ncol,
        # bbox_to_anchor=(0.5, 0.95)
    )


def _draw_annual_by_purpose(ax: plt.Axes, grr_before: dict, grr_after: dict, grr_afterN: dict, datatype="site_uses") -> None:
    """HTML의 연간 용도별 stacked bar (bar-annual-by-purpose)"""
    x = np.arange(len(GRAPH_ORDER))
    width = 0.25

    ymax = -np.inf
    for idx, (label, dataset) in enumerate([
        ("GR 이전", grr_before),
        ("GR 이후", grr_after),
        ("GR N년차", grr_afterN),
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
                   ec=color, lw=0.8,
                   fc=[color, color+'40', color+'40'][idx],
                   hatch=[None, '//////', None][idx])
            ax.bar(x + (idx - 1) * width, vals, width=width,
                   bottom=bottoms, ec='k', fc='none', zorder=5, lw=1.0)
            bottoms += vals
            ymax = max(ymax, bottoms.max())

    ax.set_ylim(0, max(5, ymax * 1.15))  # 상단 15% 여유

    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl in GRAPH_ORDER])
    ax.set_ylabel("연간 합계")
    ax.set_title("연간 용도별 에너지소요량 비교")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    # ax.legend(fontsize=8, ncols=3)
    # fig.tight_layout()


def _draw_total_monthly_line(ax: plt.Axes, grr_before: dict, grr_after: dict, grr_afterN: dict, datatype="site_uses") -> None:
    """HTML의 line-total (월별 총합 비교)"""
    months = np.arange(1, 13)

    before_vals = grr_before["summary_per_area"][datatype]["total_monthly"]
    after_vals = grr_after["summary_per_area"][datatype]["total_monthly"]
    afterN_vals = grr_afterN["summary_per_area"][datatype]["total_monthly"]

    ax.plot(months, before_vals, color=PALETTE[0], marker="o", label="GR 이전")
    ax.plot(months, after_vals, color=PALETTE[1], marker="o", linestyle="-", label="GR 이후")
    ax.plot(months, afterN_vals, color=PALETTE[2], marker="o", linestyle=(0, (4, 6)), mfc='none', label="GR N년차")

    ax.set_xticks(months)
    ax.set_xticklabels([f"{m}월" for m in months])
    ax.set_ylabel("월별 총합")
    ax.set_title("월별 총 에너지소요량 비교")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=8, loc="upper right")
    # fig.tight_layout()


def draw_simulation_figures(grr_before: dict, grr_after: dict, grr_afterN: dict) -> dict[str, plt.Figure]:
    """
    HTML에서 표시되는 모든 주요 그림들을 matplotlib로 생성하여 반환
    """
    
    master_fig = plt.figure(figsize=(9, 3*4), constrained_layout=True)

    figs = master_fig.subfigures(2, 1, height_ratios=[3, 1], hspace=0.05)

    _draw_monthly_stacked_bars(figs[0], grr_before, grr_after, grr_afterN)

    summary_axs = figs[1].subplots(1, 2)

    # (2) 연간 용도별 비교
    _draw_annual_by_purpose(summary_axs[0], grr_before, grr_after, grr_afterN)

    # (3) 월별 총합 라인 그래프
    _draw_total_monthly_line(summary_axs[1], grr_before, grr_after, grr_afterN)

    figs[0].suptitle('용도별, 월별 사용량 비교', y=1.04, fontsize=16, fontweight='bold')
    master_fig.get_layout_engine().set(h_pad=0.1, wspace=0.05)
    figs[1].suptitle('요약', fontsize=16, fontweight='bold')
    
    master_fig.align_ylabels(master_fig.axes)

    return master_fig

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
            v = v.replace(r"~", r"\~")
        
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
        f"{grrbefore["building"]["total_area"]:.1f}",
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
    
    # comparison summary
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
    
    # get figures (by results summary)
    fig_use_co2 = draw_energysimulation_figures(grrbefore, grrafter, grrafterN)
    os.makedirs(FIG_DIR, exist_ok=True)
    fig_use_co2.savefig(FIG_DIR / "energy_summary.png", dpi=400, format="png", bbox_inches="tight")
    
    # get figures
    fig_simresults = draw_simulation_figures(grrbefore, grrafter, grrafterN)
    fig_simresults.savefig(FIG_DIR / "simulation_results.png", dpi=400, format="png", bbox_inches="tight")
    
    # get figures (by weather)
    before_weatherdata_filepath = find_weatherdata(building_info["주소"], "이전")
    after_weatherdata_filepath  = find_weatherdata(building_info["주소"], "이후")
    fig_weather = draw_weather_figures(
        before_weatherdata_filepath,
        after_weatherdata_filepath ,
    )
    fig_weather.savefig(FIG_DIR / "weather_compare.png", dpi=400, format="png", bbox_inches="tight")
    
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
