
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

import numpy             as np
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

def draw_3step_bargraph(
    title : str,
    values: list[list[int|float]],
    index : list[str],
    *,
    ylabel: str = "Value",
    energy_types: list[tuple[str, str]] | None = None,
    ax    : plt.Axes
    ) -> None:

    energy_types = ENERGY_TYPES if energy_types is None else energy_types
    num_bars = len(values)
    x_positions = range(num_bars) # [0, 1, 2]
    width = 0.7  # 그룹이 아니므로 막대 폭을 넓게 설정
    num_subbars = len(energy_types)
    subbar_width = width / num_subbars

    for n, (pos, val) in enumerate(zip(x_positions, values)):
        for et_idx, (et_key, et_label) in enumerate(energy_types):
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
    max_value = max((max(val) if len(val) > 0 else 0) for val in values)
    ax.set_ylim(top=max(1, max_value * 1.1))
    
    ax.legend(
        fontsize=8,
        handles=[
            Patch(ec=None, fc=DEFAULT_COLORS_BEFORE[et_key]+'90')
            for et_key, _ in energy_types
        ],
        labels=[et_label for _, et_label in energy_types],
        loc="upper center", ncol=min(4, len(energy_types)), bbox_to_anchor=(0.5, -0.15),
    )

# ---------------------------------------------------------------------------
# New functions: Python versions of HTML Chart.js visualizations
# ---------------------------------------------------------------------------


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
SCENARIO_PREFIXES = ("GR이전", "GR이후", "N년차")

DEFAULT_COLORS_BEFORE = {
    "NATURALGAS": PALETTE[0],
    "ELECTRICITY": PALETTE[1],
    "OIL": PALETTE[2],
    "DISTRICTHEATING": PALETTE[3],
}

def _normalize_gas_ignore(
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None
) -> tuple[bool, bool, bool]:
    if gas_ignore is None:
        return (False, False, False)

    if len(gas_ignore) != len(SCENARIO_PREFIXES):
        raise ValueError(f"gas_ignore must have {len(SCENARIO_PREFIXES)} items.")

    return tuple(bool(v) for v in gas_ignore)

def _display_energy_types(
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None
) -> list[tuple[str, str]]:
    flags = _normalize_gas_ignore(gas_ignore)
    return [
        (et_key, et_label)
        for et_key, et_label in ENERGY_TYPES
        if et_key != "NATURALGAS" or not all(flags)
    ]

def _get_energy_values(category_data: dict, et_key: str, ignore_gas: bool = False) -> np.ndarray:
    if ignore_gas and et_key == "NATURALGAS":
        return np.zeros(12, dtype=float)

    return np.asarray(category_data.get(et_key, [0] * 12), dtype=float)

def _sum_grr_monthly_totals(
    result: dict,
    datatype: str,
    ignore_gas: bool = False,
) -> np.ndarray:
    totals = np.zeros(12)

    for cat_key, _ in GRAPH_ORDER:
        sign = -1 if cat_key == "generators" else 1
        category_data = result[datatype].get(cat_key, {})
        for et_key, _ in ENERGY_TYPES:
            totals += sign * _get_energy_values(category_data, et_key, ignore_gas)

    return totals

def _sum_grr_annual_total(
    result: dict,
    datatype: str,
    ignore_gas: bool = False,
) -> float:
    return float(_sum_grr_monthly_totals(result, datatype, ignore_gas).sum())

def _sum_grr_energy_total(
    result: dict,
    datatype: str,
    et_key: str,
    ignore_gas: bool = False,
) -> float:
    total = 0.0

    for cat_key, _ in GRAPH_ORDER:
        sign = -1 if cat_key == "generators" else 1
        total += sign * _get_energy_values(
            result[datatype].get(cat_key, {}),
            et_key,
            ignore_gas,
        ).sum()

    return float(total)

def _masterdict_value_is_lpg(value) -> bool:
    if value is None or pd.isna(value):
        return False

    normalized = str(value).upper().replace(" ", "")
    return any(token in normalized for token in ("LPG", "액화석유가스"))

def _find_heating_energy_source(masterdict: dict, prefix: str):
    exact_suffixes = (
        "_난방1_에너지원",
        "_난방1_ET",
        "_보일러_에너지원",
        "_보일러_ET",
        "_난방_에너지원",
        "_난방_ET",
        "_에너지원",
        "_연료종류",
        "_ET",
    )

    for suffix in exact_suffixes:
        key = f"{prefix}{suffix}"
        if key in masterdict and masterdict[key] is not None and not pd.isna(masterdict[key]):
            return masterdict[key]

    candidates = []
    for key, value in masterdict.items():
        if not isinstance(key, str) or not key.startswith(f"{prefix}_"):
            continue
        if value is None or pd.isna(value):
            continue
        if not any(token in key for token in ("에너지원", "연료종류", "_ET")):
            continue
        if key == f"{prefix}_ET" or any(token in key for token in ("난방", "보일러")):
            score = 0
            if "난방1" in key:
                score -= 4
            if "보일러" in key:
                score -= 2
            if key.endswith("_ET"):
                score -= 1
            score += len(key)
            candidates.append((score, key, value))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]

def parse_gas_ignore(masterdict: dict) -> tuple[bool, bool, bool]:
    return tuple(
        _masterdict_value_is_lpg(_find_heating_energy_source(masterdict, prefix))
        for prefix in SCENARIO_PREFIXES
    )

def _draw_monthly_stacked_bar(
    category_key: str,
    category_label: str,
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    datatype: str = "source_uses",
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None,
    ax: plt.Figure | None = None
) -> plt.Figure:
    """HTML의 월별 stacked bar (ex. 난방, 냉방 등)"""

    gas_ignore = _normalize_gas_ignore(gas_ignore)
    energy_types = _display_energy_types(gas_ignore)
    month_labels = np.arange(1, 13)
    bottom_before = np.zeros(12)
    bottom_after  = np.zeros(12)
    bottom_afterN = np.zeros(12)

    for et_key, et_label in energy_types:
        bvals = _get_energy_values(grr_before[datatype].get(category_key, {}), et_key, gas_ignore[0])
        avals = _get_energy_values(grr_after[datatype].get(category_key, {}), et_key, gas_ignore[1])
        nvals = _get_energy_values(grr_afterN[datatype].get(category_key, {}), et_key, gas_ignore[2])

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
        _get_energy_values(grr_before[datatype].get(category_key, {}), et_key, gas_ignore[0])
        for et_key, _ in energy_types
    ] + [
        _get_energy_values(grr_after[datatype].get(category_key, {}), et_key, gas_ignore[1])
        for et_key, _ in energy_types
    ] + [
        _get_energy_values(grr_afterN[datatype].get(category_key, {}), et_key, gas_ignore[2])
        for et_key, _ in energy_types
    ])
    ymax = all_values.max() if len(all_values) > 0 else 0
    ax.set_ylim(0, max(5, ymax * 1.15))  # 상단 15% 여유


def _draw_monthly_stacked_bars(
    fig: plt.Figure,
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    datatype: str = "source_uses",
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None,
) -> None:
    
    gas_ignore = _normalize_gas_ignore(gas_ignore)
    energy_types = _display_energy_types(gas_ignore)
    axs = fig.subplots(3, 2)

    # (1) 난방, 냉방, 조명, 팬/펌프/전열, 급탕, 발전량
    for cat_idx, (cat_key, cat_label) in enumerate(GRAPH_ORDER):
        _draw_monthly_stacked_bar(
            cat_key, cat_label, grr_before, grr_after, grr_afterN, datatype,
            gas_ignore=gas_ignore,
            ax = axs.ravel()[cat_idx]
        )

    handles = []
    labels = []
    for et_key, et_label in energy_types:
        for l_idx, label in enumerate(["GR 이전", "GR 이후", "운영특성 반영"]):
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


def _draw_annual_by_purpose(
    ax: plt.Axes,
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    datatype="source_uses",
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None,
) -> None:
    """HTML의 연간 용도별 stacked bar (bar-annual-by-purpose)"""
    gas_ignore = _normalize_gas_ignore(gas_ignore)
    energy_types = _display_energy_types(gas_ignore)
    x = np.arange(len(GRAPH_ORDER))
    width = 0.25

    ymax = 0.0
    for idx, (label, dataset, ignore_gas) in enumerate([
        ("GR 이전", grr_before, gas_ignore[0]),
        ("GR 이후", grr_after, gas_ignore[1]),
        ("운영특성 반영", grr_afterN, gas_ignore[2]),
    ]):
        bottoms = np.zeros(len(GRAPH_ORDER))
        for et_key, et_label in energy_types:
            vals = [
                _get_energy_values(dataset[datatype].get(cat_key, {}), et_key, ignore_gas).sum()
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

def _draw_total_monthly_bar(
    ax: plt.Axes,
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    datatype="source_uses",
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None,
) -> None:
    """HTML의 bar-total (월별 총합 비교 - 막대그래프)"""
    gas_ignore = _normalize_gas_ignore(gas_ignore)
    months = np.arange(1, 13)
    
    # 막대 너비 설정
    width = 0.25 

    before_vals = _sum_grr_monthly_totals(grr_before, datatype, gas_ignore[0])
    after_vals = _sum_grr_monthly_totals(grr_after, datatype, gas_ignore[1])
    afterN_vals = _sum_grr_monthly_totals(grr_afterN, datatype, gas_ignore[2])

    # x축 위치를 조정하여 막대를 그립니다 (왼쪽, 가운데, 오른쪽)
    # zorder=3을 주어 그리드 위로 막대가 올라오게 합니다.
    ax.bar(months - width, before_vals, width=width, color=PALETTE[0], label="GR 이전", zorder=3)
    ax.bar(months, after_vals, width=width, color=PALETTE[1], label="GR 이후", zorder=3)
    
    # 운영특성 반영은 기존 스타일(점선/빈 원)을 반영하여 빗금(hatch)이나 테두리 스타일로 표현
    ax.bar(months + width, afterN_vals, width=width, 
           color='white', edgecolor=PALETTE[2], hatch='////', linewidth=1.0, 
           label="운영특성 반영", zorder=3)

    ax.set_ylim(bottom=0)
    ax.set_xticks(months)
    ax.set_xticklabels([f"{m}월" for m in months])
    ax.set_ylabel("월별 합계 (kWh/$\\mathrm{m^2\\cdot}$월)")
    ax.set_title("월별 1차에너지소요량", y=1.1)
    
    # 그리드가 막대 뒤로 가도록 설정
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0) 
    ax.legend(fontsize=8, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.15))


def draw_mainfigures(
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None,
):
    """
    matplotlib로 두 개의 Figure(메인 그래프, 요약 그래프)를 생성하여 반환
    Returns:
        fig1 (Figure): 용도별, 월별 사용량 비교 (상단 큰 그래프)
        fig2 (Figure): 연간 용도별 비교 및 월별 총합 라인 (하단 요약 그래프)
    """
    
    gas_ignore = _normalize_gas_ignore(gas_ignore)
    energy_types = _display_energy_types(gas_ignore)

    # --- Figure 1: 월별 스택 바 (메인) ---
    # 기존 비율(3:1.2)을 고려하여 세로 길이를 적절히 배분 (예: 높이 8)
    fig1 = plt.figure(figsize=(9, 8), constrained_layout=True)
    
    # 기존 helper 함수가 Figure 객체를 받아 subplot을 추가한다고 가정
    _draw_monthly_stacked_bars(fig1, grr_before, grr_after, grr_afterN, gas_ignore=gas_ignore)

    fig1.suptitle('월간 단위면적당 1차에너지소요량', fontsize=16, fontweight='bold')


    # --- Figure 2: 요약 (하단 2개 그래프) ---
    # 높이를 작게 설정 (예: 높이 4)
    fig2 = plt.figure(figsize=(9, 3), constrained_layout=True)
    
    # 1행 2열로 서브플롯 생성
    summary_ax = fig2.subplots(1, 1)

    # (3) 월별 총합 라인 그래프
    draw_3step_bargraph(
        "면적당 1차에너지소요량 (연간)",
        [
            [
                _sum_grr_energy_total(result, "source_uses", et_key, ignore_gas)
                for et_key, _ in energy_types
            ]
            for result, ignore_gas in zip([grr_before, grr_after, grr_afterN], gas_ignore)
        ],
        ["GR이전","GR이후","운영특성 반영"],
        ylabel = "1차에너지 (kWh/$\\mathrm{m^2\\cdot}$년)",
        energy_types=energy_types,
        ax = summary_ax
    )
    
    return fig1, fig2

def draw_page3_summaryfigures(
    grr_before: dict,
    grr_after: dict,
    grr_afterN: dict,
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None,
    ) -> plt.Figure:
    
    gas_ignore = _normalize_gas_ignore(gas_ignore)
    energy_types = _display_energy_types(gas_ignore)
    fig = plt.figure(figsize=(9, 3), constrained_layout=True)
    axes = fig.subplots(1, 2)
    
    _draw_annual_by_purpose(
        axes[0],
        grr_before, grr_after, grr_afterN,  "source_uses",
        gas_ignore=gas_ignore,
    )
    
    draw_3step_bargraph(
        "면적당 온실가스 배출량 (연간)",
        [
            [
                _sum_grr_energy_total(result, "co2", et_key, ignore_gas)
                for et_key, _ in energy_types
            ]
            for result, ignore_gas in zip([grr_before, grr_after, grr_afterN], gas_ignore)
        ],
        ["GR이전","GR이후","운영특성 반영"],
        ylabel = r"$\mathrm{CO_2,eq}$ (kg/$\mathrm{m^2\cdot}$년)",
        energy_types=energy_types,
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
    gas_ignore: list[bool] | tuple[bool, bool, bool] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    gas_ignore = _normalize_gas_ignore(gas_ignore)
    
    df1 = pd.DataFrame(
        [
            [
                _sum_grr_annual_total(grrbefore, "source_uses", gas_ignore[0]),
                _sum_grr_annual_total(grrafter, "source_uses", gas_ignore[1]),
                _sum_grr_annual_total(grrafterN, "source_uses", gas_ignore[2]),
            ],
            [
                _sum_grr_annual_total(grrbefore, "co2", gas_ignore[0]),
                _sum_grr_annual_total(grrafter, "co2", gas_ignore[1]),
                _sum_grr_annual_total(grrafterN, "co2", gas_ignore[2]),
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
    checklist1: 현장조사체크리스트,
    checklist2: 현장조사체크리스트,
) -> str:

    func_certaincoolingsetpoint = lambda x: x if isinstance(x, int | float) else 26
    func_certainheatingsetpoint = lambda x: x if isinstance(x, int | float) else 20

    def mark_same_as_above(row1, row2, same_text="상동"):
        return [same_text if v1 == v2 else v2 for v1, v2 in zip(row1, row2)]

    # heating
    if checklist1.일반존.난방설비1 is None:
        heatingtime1 = "사용안함"
        heatingsetpoint1 = "(없음)"
    else:
        heatingtime1 = f"{checklist1.일반존.난방설비1.사용기간} {checklist1.일반존.난방설비1.사용시간}"
        heatingsetpoint1 = f"{func_certainheatingsetpoint(checklist1.일반존.난방설비1.설정온도):.1f}$^\\circ C$"

    if checklist2.일반존.난방설비1 is None:
        heatingtime2 = "사용안함"
        heatingsetpoint2 = "(없음)"
    else:
        heatingtime2 = f"{checklist2.일반존.난방설비1.사용기간} {checklist2.일반존.난방설비1.사용시간}"
        heatingsetpoint2 = f"{func_certainheatingsetpoint(checklist2.일반존.난방설비1.설정온도):.1f}$^\\circ C$"

    # cooling
    if checklist1.일반존.냉방설비1 is None:
        coolingtime1 = "사용안함"
        coolingsetpoint1 = "(없음)"
    else:
        coolingtime1 = f"{checklist1.일반존.냉방설비1.사용기간} {checklist1.일반존.냉방설비1.사용시간}"
        coolingsetpoint1 = f"{func_certaincoolingsetpoint(checklist1.일반존.냉방설비1.설정온도):.1f}$^\\circ C$"

    if checklist2.일반존.냉방설비1 is None:
        coolingtime2 = "사용안함"
        coolingsetpoint2 = "(없음)"
    else:
        coolingtime2 = f"{checklist2.일반존.냉방설비1.사용기간} {checklist2.일반존.냉방설비1.사용시간}"
        coolingsetpoint2 = f"{func_certaincoolingsetpoint(checklist2.일반존.냉방설비1.설정온도):.1f}$^\\circ C$"

    row1 = [heatingtime1, heatingsetpoint1, coolingtime1, coolingsetpoint1]
    row2 = [heatingtime2, heatingsetpoint2, coolingtime2, coolingsetpoint2]
    row2 = mark_same_as_above(row1, row2)

    df = pd.DataFrame(
        [row1, row2],
        columns=["난방 사용시간", "난방 설정온도", "냉방 사용시간", "냉방 설정온도"],
        index=["GR 직후", "2025년"],
    )

    tablestyle = {
        "column_format": ">{\\centering\\arraybackslash}p{3cm}" + "|>{\\centering\\arraybackslash}p{3.325cm}" * 4,
        "clines": "all;data",
        "hrules": True,
    }

    tex = (
        df.style.to_latex(**tablestyle)
        .replace(r"\toprule", r"\hline")
        .replace(r"\midrule", r"\hline")
        .replace(r"\bottomrule", r"\hline")
        .replace("~", "-")
    )

    return tex


def parse_occupantchange(
    checklist1: 현장조사체크리스트,
    checklist2: 현장조사체크리스트,
):

    def mark_same_as_above(row1, row2, same_text="상동"):
        return [same_text if v1 == v2 else v2 for v1, v2 in zip(row1, row2)]

    if isinstance(checklist1, 어린이집체크리스트):

        func_nanto0 = lambda x: 0 if pd.isna(x) else x

        row1 = [
            func_nanto0(checklist1.일반존.기본보육교사 + checklist1.일반존.기본보육원생),
            func_nanto0(checklist1.일반존.연장보육A교사 + checklist1.일반존.연장보육A원생),
            func_nanto0(checklist1.일반존.연장보육B교사 + checklist1.일반존.연장보육B원생),
            func_nanto0(checklist1.일반존.야간보육교사 + checklist1.일반존.야간보육원생),
            func_nanto0(checklist1.일반존.주말보육교사 + checklist1.일반존.주말보육원생),
        ]
        row2 = [
            func_nanto0(checklist2.일반존.기본보육교사 + checklist2.일반존.기본보육원생),
            func_nanto0(checklist2.일반존.연장보육A교사 + checklist2.일반존.연장보육A원생),
            func_nanto0(checklist2.일반존.연장보육B교사 + checklist2.일반존.연장보육B원생),
            func_nanto0(checklist2.일반존.야간보육교사 + checklist2.일반존.야간보육원생),
            func_nanto0(checklist2.일반존.주말보육교사 + checklist2.일반존.주말보육원생),
        ]
        row2 = mark_same_as_above(row1, row2)

        df = pd.DataFrame(
            [row1, row2],
            columns=["기본 (-16:00)", "연장 (-18:00)", "연장 (-19:30)", "야간 (-21:00)", "주말"],
            index=["GR 직후", "2025년"],
        )

        tablestyle = {
            "column_format": ">{\\centering\\arraybackslash}p{3cm}" + "|>{\\centering\\arraybackslash}p{2.66cm}" * 5,
            "clines": "all;data",
            "hrules": True,
        }

        tex = (
            df.style.format(lambda x: x if x == "상동" else f"{x}명")
            .to_latex(**tablestyle)
            .replace(r"\toprule", r"\hline")
            .replace(r"\midrule", r"\hline")
            .replace(r"\bottomrule", r"\hline")
        )

        return tex

    else:

        집중진료연인원1 = (
            (checklist1.일반존.집중진료오전방문객 * checklist1.일반존.집중진료오전체류시간)
            + (checklist1.일반존.집중진료오후방문객 * checklist1.일반존.집중진료오후체류시간)
        ) / 60 * len(checklist1.일반존.집중진료요일.split(","))

        집중진료연인원2 = (
            (checklist2.일반존.집중진료오전방문객 * checklist2.일반존.집중진료오전체류시간)
            + (checklist2.일반존.집중진료오후방문객 * checklist2.일반존.집중진료오후체류시간)
        ) / 60 * len(checklist2.일반존.집중진료요일.split(","))

        row1 = [
            f"{checklist1.일반존.운영시간.replace('~', '-')}",
            f"{checklist1.일반존.직원}명 상주",
            f"주 {집중진료연인원1:.0f}명$\\cdot$시간",
            f"{checklist1.특화존2.사용관사수}개소",
        ]
        row2 = [
            f"{checklist2.일반존.운영시간.replace('~', '-')}",
            f"{checklist2.일반존.직원}명 상주",
            f"주 {집중진료연인원2:.0f}명$\\cdot$시간",
            f"{checklist2.특화존2.사용관사수}개소",
        ]
        row2 = mark_same_as_above(row1, row2)

        df = pd.DataFrame(
            [row1, row2],
            columns=["운영시간", "직원", "집중진료 방문객", "이용 관사 수"],
            index=["GR 직후", "2025년"],
        )

        tablestyle = {
            "column_format": ">{\\centering\\arraybackslash}p{3cm}" + "|>{\\centering\\arraybackslash}p{3.325cm}" * 4,
            "clines": "all;data",
            "hrules": True,
        }

        tex = (
            df.style.to_latex(**tablestyle)
            .replace(r"\toprule", r"\hline")
            .replace(r"\midrule", r"\hline")
            .replace(r"\bottomrule", r"\hline")
            .replace("~", "-")
        )

        return tex
    
    
def parse_majorchange(masterdict: dict) -> str:

    def is_missing(v) -> bool:
        return v is None or (isinstance(v, str) and v.strip() == "") or pd.isna(v)

    def fmt_num(v, digits: int = 3) -> str:
        if is_missing(v):
            return "-"
        v = float(v)
        return f"{v:.{digits}f}".rstrip("0").rstrip(".")

    def fmt_pct_from_ratio(v, digits: int = 1) -> str:
        if is_missing(v):
            return "-"
        return f"{float(v) * 100:.{digits}f}".rstrip("0").rstrip(".") + r"\%"

    def fmt_pct_direct(v, digits: int = 1) -> str:
        if is_missing(v):
            return "-"
        return f"{float(v):.{digits}f}".rstrip("0").rstrip(".") + r"\%"

    def fmt_hrv(h, c) -> str:
        if is_missing(h) and is_missing(c):
            return "-"
        return f"{fmt_pct_from_ratio(h)} / {fmt_pct_from_ratio(c)}"

    def fmt_solar(area, eff) -> str:
        if is_missing(area) and is_missing(eff):
            return "-"
        area_txt = "-" if is_missing(area) else f"{fmt_num(area, 1)} m2"
        eff_txt = "-" if is_missing(eff) else fmt_pct_direct(eff, 1)
        return f"{area_txt}, {eff_txt}"

    def heating_value(prefix: str):
        heating_type = masterdict.get(f"{prefix}_난방1_유형")
        if heating_type == "히트펌프":
            return masterdict.get(f"{prefix}_난방1_COP [W/W]")
        return masterdict.get(f"{prefix}_난방1_효율 [%]")

    def heating_note() -> str:
        types = {
            masterdict.get("GR이전_난방1_유형"),
            masterdict.get("GR이후_난방1_유형"),
            masterdict.get("N년차_난방1_유형"),
        }
        if types == {"히트펌프"}:
            return "[W/W]"
        if "히트펌프" in types:
            return r"히트펌프 [W/W], 보일러 [\%]"
        return r"[\%]"

    rows = [
        [
            fmt_num(masterdict.get("GR이전_외벽_열관류율 [W/m2·K]"), 3),
            fmt_num(masterdict.get("GR이후_외벽_열관류율 [W/m2·K]"), 3),
            fmt_num(masterdict.get("N년차_외벽_열관류율 [W/m2·K]"), 3),
            "[W/m2·K]",
        ],
        [
            fmt_num(masterdict.get("GR이전_창 및 문_열관류율 [W/m2·K]"), 3),
            fmt_num(masterdict.get("GR이후_창 및 문_열관류율 [W/m2·K]"), 3),
            fmt_num(masterdict.get("N년차_창 및 문_열관류율 [W/m2·K]"), 3),
            "[W/m2·K]",
        ],
        [
            fmt_num(masterdict.get("GR이전_냉방1_COP [W/W]"), 2),
            fmt_num(masterdict.get("GR이후_냉방1_COP [W/W]"), 2),
            fmt_num(masterdict.get("N년차_냉방1_COP [W/W]"), 2),
            "[W/W]",
        ],
        [
            fmt_num(heating_value("GR이전"), 2),
            fmt_num(heating_value("GR이후"), 2),
            fmt_num(heating_value("N년차"), 2),
            heating_note(),
        ],
        [
            fmt_hrv(
                masterdict.get("GR이전_전열 교환기_난방[%]"),
                masterdict.get("GR이전_전열 교환기_냉방[%]")
            ),
            fmt_hrv(
                masterdict.get("GR이후_전열 교환기_난방[%]"),
                masterdict.get("GR이후_전열 교환기_냉방[%]")
            ),
            fmt_hrv(
                masterdict.get("N년차_전열 교환기_난방[%]"),
                masterdict.get("N년차_전열 교환기_냉방[%]")
            ),
            r"[난방] / [냉방]",
        ],
        [
            fmt_num(masterdict.get("GR이전_조명밀도 [W/m2]"), 2),
            fmt_num(masterdict.get("GR이후_조명밀도 [W/m2]"), 2),
            fmt_num(masterdict.get("N년차_조명밀도 [W/m2]"), 2),
            "[W/m2]",
        ],
        [
            fmt_solar(
                masterdict.get("GR이전_태양광_면적[m2]"),
                masterdict.get("GR이전_태양광_효율[%]")
            ),
            fmt_solar(
                masterdict.get("GR이후_태양광_면적[m2]"),
                masterdict.get("GR이후_태양광_효율[%]")
            ),
            fmt_solar(
                masterdict.get("N년차_태양광_면적[m2]"),
                masterdict.get("N년차_태양광_효율[%]")
            ),
            r"[면적 m2], [효율 \%]",
        ],
        ["-", "-", "-", "-"],
        ["-", "-", "-", "-"],
        ["-", "-", "-", "-"],
    ]

    df = pd.DataFrame(
        rows,
        columns=["GR이전", "GR이후", "N년차", "비고"],
        index=pd.MultiIndex.from_tuples(
            [
                ("기술요소", "외피"),
                ("기술요소", "창호"),
                ("기술요소", "냉방"),
                ("기술요소", "난방"),
                ("기술요소", "환기"),
                ("기술요소", "조명"),
                ("기술요소", "신재생"),
                ("운영특성", "재실인원"),
                ("운영특성", "운영시간"),
                ("운영특성", "설정온도"),
            ],
            names=["대분류", "구분"]
        )
    )

    df = df[df[["GR이전", "GR이후", "N년차"]].nunique(axis=1) > 1]

    tex = df.style.hide(axis="index", names=True).to_latex(
        hrules=True,
        clines="all;data",
        sparse_index=True,
        multirow_align="c",
        column_format=(
            r">{\centering\arraybackslash}p{1cm}|"
            r">{\centering\arraybackslash}p{2.6cm}|"
            r">{\centering\arraybackslash}p{3.2cm}|"
            r">{\centering\arraybackslash}p{3.2cm}|"
            r">{\centering\arraybackslash}p{3.2cm}|"
            r">{\centering\arraybackslash}p{2.8cm}"
        ),
    )

    tex = tex.replace(r"\toprule", r"\hline")
    tex = tex.replace(r"\midrule", r"\hline")
    tex = tex.replace(r"\bottomrule", r"\hline")

    tex = tex.replace(
        "& & GR이전 & GR이후 & N년차 & 비고 \\\n",
        r"\multicolumn{2}{c|}{구분} & GR이전 & GR이후 & N년차 & 비고 \\" + "\n"
    )

    tex = tex.replace(
        r"{기술요소}",
        r"{\shortstack{기\\술\\요\\소}}"
    )
    tex = tex.replace(
        r"{운영특성}",
        r"{\shortstack{운\\영\\특\\성}}"
    )

    tex = tex.replace(r"\cline{1-6} \cline{2-6}", r"\hline")

    return tex


def parse_allchange(masterdict: dict) -> str:
    
    df = pd.DataFrame(
        [
            [
                "외벽 열관류율 [W/m2·K]",
                f"{masterdict.get('GR이전_외벽_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('GR이후_외벽_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('N년차_외벽_열관류율 [W/m2·K]'):.2f}",
                "/".join(set([
                    masterdict.get("GR이전_외벽_근거"),
                    masterdict.get("GR이후_외벽_근거"),
                    masterdict.get("N년차_외벽_근거"),
                ]) - {"-"})
            ],
            [
                "창호 열관류율 [W/m2·K]",
                f"{masterdict.get('GR이전_창 및 문_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('GR이후_창 및 문_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('N년차_창 및 문_열관류율 [W/m2·K]'):.2f}",
                "/".join(set([
                    masterdict.get("GR이전_창 및 문_근거"),
                    masterdict.get("GR이후_창 및 문_근거"),
                    masterdict.get("N년차_창 및 문_근거"),
                ]) - {"-"})
            ],
            [
                "창호 취득계수(SHGC)",
                f"{masterdict.get('GR이전_창 및 문_취득계수'):.2f}",
                f"{masterdict.get('GR이후_창 및 문_취득계수'):.2f}",
                f"{masterdict.get('N년차_창 및 문_취득계수'):.2f}",
                "/".join(set([
                    masterdict.get("GR이전_창 및 문_근거"),
                    masterdict.get("GR이후_창 및 문_근거"),
                    masterdict.get("N년차_창 및 문_근거"),
                ]) - {"-"})
            ],
            [
                "지붕 열관류율 [W/m2·K]",
                f"{masterdict.get('GR이전_지붕_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('GR이후_지붕_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('N년차_지붕_열관류율 [W/m2·K]'):.2f}",
                "/".join(set([
                    masterdict.get("GR이전_지붕_근거"),
                    masterdict.get("GR이후_지붕_근거"),
                    masterdict.get("N년차_지붕_근거"),
                ]) - {"-"})
            ],
            [
                "바닥 열관류율 [W/m2·K]",
                f"{masterdict.get('GR이전_바닥_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('GR이후_바닥_열관류율 [W/m2·K]'):.2f}",
                f"{masterdict.get('N년차_바닥_열관류율 [W/m2·K]'):.2f}",
                "/".join(set([
                    masterdict.get("GR이전_바닥_근거"),
                    masterdict.get("GR이후_바닥_근거"),
                    masterdict.get("N년차_바닥_근거"),
                ]) - {"-"})
            ],
            [
                "조명밀도",
                f"{masterdict.get('GR이전_조명밀도 [W/m2]'):.2f}",
                f"{masterdict.get('GR이후_조명밀도 [W/m2]'):.2f}",
                f"{masterdict.get('N년차_조명밀도 [W/m2]'):.2f}",
                "-"
            ],
            [
                "침기율",
                f"{masterdict.get('GR이전_침기율 [ACH]'):.2f}",
                f"{masterdict.get('GR이후_침기율 [ACH]'):.2f}",
                f"{masterdict.get('N년차_침기율 [ACH]'):.2f}",
                "-",
            ],
            [
                "난방1 유형/열원",
                masterdict.get("GR이전_난방1_유형") + " / " + str(masterdict.get("GR이전_난방1_열원")),
                masterdict.get("GR이후_난방1_유형") + " / " + str(masterdict.get("GR이후_난방1_열원")),
                masterdict.get("N년차_난방1_유형") + " / " + str(masterdict.get("N년차_난방1_열원")),
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_난방1_근거")) else masterdict.get("GR이전_난방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_난방1_근거")) else masterdict.get("GR이후_난방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_난방1_근거")) else masterdict.get("N년차_난방1_근거"),
                ]) - {"-"})
            ],
            [
                "난방1 용량 [kW]",
                "-" if pd.isna(masterdict.get("GR이전_난방1_용량 [kW]")) else f"{masterdict.get('GR이전_난방1_용량 [kW]')*1E-3:.2f}",
                "-" if pd.isna(masterdict.get("GR이후_난방1_용량 [kW]")) else f"{masterdict.get('GR이후_난방1_용량 [kW]')*1E-3:.2f}",
                "-" if pd.isna(masterdict.get("N년차_난방1_용량 [kW]")) else f"{masterdict.get('N년차_난방1_용량 [kW]')*1E-3:.2f}",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_난방1_근거")) else masterdict.get("GR이전_난방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_난방1_근거")) else masterdict.get("GR이후_난방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_난방1_근거")) else masterdict.get("N년차_난방1_근거"),
                ]) - {"-"})
            ],
            [
                "난방1 COP [W/W]",
                "-" if pd.isna(masterdict.get("GR이전_난방1_COP [W/W]")) else f"{masterdict.get('GR이전_난방1_COP [W/W]'):.2f}",
                "-" if pd.isna(masterdict.get("GR이후_난방1_COP [W/W]")) else f"{masterdict.get('GR이후_난방1_COP [W/W]'):.2f}",
                "-" if pd.isna(masterdict.get("N년차_난방1_COP [W/W]")) else f"{masterdict.get('N년차_난방1_COP [W/W]'):.2f}",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_난방1_근거")) else masterdict.get("GR이전_난방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_난방1_근거")) else masterdict.get("GR이후_난방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_난방1_근거")) else masterdict.get("N년차_난방1_근거"),
                ]) - {"-"})
            ],
            [
                "난방1 효율 [%]",
                "-" if pd.isna(masterdict.get("GR이전_난방1_효율 [%]")) else f"{masterdict.get('GR이전_난방1_효율 [%]'):.1f}",
                "-" if pd.isna(masterdict.get("GR이후_난방1_효율 [%]")) else f"{masterdict.get('GR이후_난방1_효율 [%]'):.1f}",
                "-" if pd.isna(masterdict.get("N년차_난방1_효율 [%]")) else f"{masterdict.get('N년차_난방1_효율 [%]'):.1f}",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_난방1_근거")) else masterdict.get("GR이전_난방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_난방1_근거")) else masterdict.get("GR이후_난방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_난방1_근거")) else masterdict.get("N년차_난방1_근거"),
                ]) - {"-"})
            ],
            [
                "냉방1 유형/열원",
                f"{masterdict.get('GR이전_냉방1_유형')} / {str(masterdict.get('GR이전_냉방1_열원'))}",
                f"{masterdict.get('GR이후_냉방1_유형')} / {str(masterdict.get('GR이후_냉방1_열원'))}",
                f"{masterdict.get('N년차_냉방1_유형')} / {str(masterdict.get('N년차_냉방1_열원'))}",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_냉방1_근거")) else masterdict.get("GR이전_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_냉방1_근거")) else masterdict.get("GR이후_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_냉방1_근거")) else masterdict.get("N년차_냉방1_근거"),
                ]) - {"-"})
            ],
            [
                "냉방1 용량 [kW]",
                "-" if pd.isna(masterdict.get("GR이전_냉방1_용량 [kW]")) else f"{masterdict.get('GR이전_냉방1_용량 [kW]')*1E-3:.2f}",
                "-" if pd.isna(masterdict.get("GR이후_냉방1_용량 [kW]")) else f"{masterdict.get('GR이후_냉방1_용량 [kW]')*1E-3:.2f}",
                "-" if pd.isna(masterdict.get("N년차_냉방1_용량 [kW]")) else f"{masterdict.get('N년차_냉방1_용량 [kW]')*1E-3:.2f}",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_냉방1_근거")) else masterdict.get("GR이전_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_냉방1_근거")) else masterdict.get("GR이후_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_냉방1_근거")) else masterdict.get("N년차_냉방1_근거"),
                ]) - {"-"})
            ],
            [
                "냉방1 COP [W/W]",
                "-" if pd.isna(masterdict.get("GR이전_냉방1_COP [W/W]")) else f"{masterdict.get('GR이전_냉방1_COP [W/W]'):.2f}",
                "-" if pd.isna(masterdict.get("GR이후_냉방1_COP [W/W]")) else f"{masterdict.get('GR이후_냉방1_COP [W/W]'):.2f}",
                "-" if pd.isna(masterdict.get("N년차_냉방1_COP [W/W]")) else f"{masterdict.get('N년차_냉방1_COP [W/W]'):.2f}",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_냉방1_근거")) else masterdict.get("GR이전_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_냉방1_근거")) else masterdict.get("GR이후_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_냉방1_근거")) else masterdict.get("N년차_냉방1_근거"),
                ]) - {"-"})
            ],
            [
                "냉방1 효율 [%]",
                "-" if pd.isna(masterdict.get("GR이전_냉방1_효율 [%]")) else f"{masterdict.get('GR이전_냉방1_효율 [%]'):.1f}",
                "-" if pd.isna(masterdict.get("GR이후_냉방1_효율 [%]")) else f"{masterdict.get('GR이후_냉방1_효율 [%]'):.1f}",
                "-" if pd.isna(masterdict.get("N년차_냉방1_효율 [%]")) else f"{masterdict.get('N년차_냉방1_효율 [%]'):.1f}",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_냉방1_근거")) else masterdict.get("GR이전_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_냉방1_근거")) else masterdict.get("GR이후_냉방1_근거"),
                    "-" if pd.isna(masterdict.get("N년차_냉방1_근거")) else masterdict.get("N년차_냉방1_근거"),
                ]) - {"-"})
            ],
            [
                "전열교환기 효율(난방)",
                "-" if pd.isna(masterdict.get("GR이전_전열 교환기_난방[%]")) else f"{masterdict.get('GR이전_전열 교환기_난방[%]'):.1f}%",
                "-" if pd.isna(masterdict.get("GR이후_전열 교환기_난방[%]")) else f"{masterdict.get('GR이후_전열 교환기_난방[%]'):.1f}%",
                "-" if pd.isna(masterdict.get("N년차_전열 교환기_난방[%]")) else f"{masterdict.get('N년차_전열 교환기_난방[%]'):.1f}%",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_전열 교환기_난방 근거")) else masterdict.get("GR이전_전열 교환기_난방 근거"),
                    "-" if pd.isna(masterdict.get("GR이후_전열 교환기_난방 근거")) else masterdict.get("GR이후_전열 교환기_난방 근거"),
                    "-" if pd.isna(masterdict.get("N년차_전열 교환기_난방 근거")) else masterdict.get("N년차_전열 교환기_난방 근거"),
                ]) - {"-"})
            ],
            [
                "전열교환기 효율(냉방)",
                "-" if pd.isna(masterdict.get("GR이전_전열 교환기_냉방[%]")) else f"{masterdict.get('GR이전_전열 교환기_냉방[%]'):.1f}%",
                "-" if pd.isna(masterdict.get("GR이후_전열 교환기_냉방[%]")) else f"{masterdict.get('GR이후_전열 교환기_냉방[%]'):.1f}%",
                "-" if pd.isna(masterdict.get("N년차_전열 교환기_냉방[%]")) else f"{masterdict.get('N년차_전열 교환기_냉방[%]'):.1f}%", 
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_전열 교환기_냉방 근거")) else masterdict.get("GR이전_전열 교환기_냉방 근거"),
                    "-" if pd.isna(masterdict.get("GR이후_전열 교환기_냉방 근거")) else masterdict.get("GR이후_전열 교환기_냉방 근거"),
                    "-" if pd.isna(masterdict.get("N년차_전열 교환기_냉방 근거")) else masterdict.get("N년차_전열 교환기_냉방 근거"),
                ]) - {"-"})
            ],
            [
                "태양광 설치 여부",
                "O" if not pd.isna(masterdict.get("GR이전_태양광_면적[m2]")) and masterdict.get("GR이전_태양광_면적[m2]") > 0 else "X",
                "O" if not pd.isna(masterdict.get("GR이후_태양광_면적[m2]")) and masterdict.get("GR이후_태양광_면적[m2]") > 0 else "X",
                "O" if not pd.isna(masterdict.get("N년차_태양광_면적[m2]")) and masterdict.get("N년차_태양광_면적[m2]") > 0 else "X",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_태양광_근거")) else masterdict.get("GR이전_태양광_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_태양광_근거")) else masterdict.get("GR이후_태양광_근거"),
                    "-" if pd.isna(masterdict.get("N년차_태양광_근거")) else masterdict.get("N년차_태양광_근거"),
                ]) - {"-"})
            ],
            [
                "태양광 면적[m2]",
                f"{masterdict.get('GR이전_태양광_면적[m2]'):.1f}" if not pd.isna(masterdict.get("GR이전_태양광_면적[m2]")) else "-",
                f"{masterdict.get('GR이후_태양광_면적[m2]'):.1f}" if not pd.isna(masterdict.get("GR이후_태양광_면적[m2]")) else "-",
                f"{masterdict.get('N년차_태양광_면적[m2]'):.1f}" if not pd.isna(masterdict.get("N년차_태양광_면적[m2]")) else "-",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_태양광_근거")) else masterdict.get("GR이전_태양광_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_태양광_근거")) else masterdict.get("GR이후_태양광_근거"),
                    "-" if pd.isna(masterdict.get("N년차_태양광_근거")) else masterdict.get("N년차_태양광_근거"),
                ]) - {"-"})
            ],
            [
                "태양광 효율[%]",
                f"{masterdict.get('GR이전_태양광_효율[%]'):.1f}" if not pd.isna(masterdict.get("GR이전_태양광_효율[%]")) else "-",
                f"{masterdict.get('GR이후_태양광_효율[%]'):.1f}" if not pd.isna(masterdict.get("GR이후_태양광_효율[%]")) else "-",
                f"{masterdict.get('N년차_태양광_효율[%]'):.1f}" if not pd.isna(masterdict.get("N년차_태양광_효율[%]")) else "-",
                "/".join(set([
                    "-" if pd.isna(masterdict.get("GR이전_태양광_근거")) else masterdict.get("GR이전_태양광_근거"),
                    "-" if pd.isna(masterdict.get("GR이후_태양광_근거")) else masterdict.get("GR이후_태양광_근거"),
                    "-" if pd.isna(masterdict.get("N년차_태양광_근거")) else masterdict.get("N년차_태양광_근거"),
                ]) - {"-"})
            ]
        ],
        columns = ["항목","그린리모델링 이전", "그린리모델링 이후", "운영특성 반영", "근거"],
    )
    
    def prettify_latex_table(tex: str, header_color: str = "EAEAEA", arraystretch: float = 1.5) -> str:
        lines = tex.splitlines()
        new_lines = []
        in_tabular = False
        header_done = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith(r"\begin{tabular}"):
                in_tabular = True
                new_lines.append(rf"\renewcommand{{\arraystretch}}{{{arraystretch}}}")
                new_lines.append(line)
                new_lines.append(r"\hline")
                continue

            if stripped.startswith(r"\end{tabular}"):
                in_tabular = False
                new_lines.append(line)
                new_lines.append(r"\renewcommand{\arraystretch}{1}")
                continue

            if in_tabular and stripped.endswith(r"\\"):
                if not header_done:
                    new_lines.append(rf"\rowcolor[HTML]{{{header_color}}}")
                    header_done = True
                new_lines.append(line)
                new_lines.append(r"\hline")
                continue

            new_lines.append(line)

        return "\n".join(new_lines)
        
    tex = (
        df.style
        .hide(axis="index")
        .format(escape="latex")   # %, _, & 같은 LaTeX 특수문자 자동 처리
        .to_latex(
            hrules=False,         # hline은 우리가 직접 넣을 것
            column_format=(
                r">{\centering\arraybackslash}p{4cm}|"
                r">{\centering\arraybackslash}p{2.5cm}|"
                r">{\centering\arraybackslash}p{2.5cm}|"
                r">{\centering\arraybackslash}p{2.5cm}|"
                r">{\centering\arraybackslash}p{4.5cm}"   # 마지막 | 제거
            ),
        )
        .replace("~", "-")
    )

    tex = prettify_latex_table(tex, header_color="EAEAEA")
    return tex

def parse_occupant(masterdict: dict) -> str:
    
    if masterdict.get("구분") == "어린이집":
        df = pd.DataFrame(
            [
                [
                    "기본보육 인원",
                    masterdict.get("GR이전_어린이집_기본보육 교사수")+masterdict.get("GR이전_어린이집_기본보육 원생수"),
                    masterdict.get("GR이후_어린이집_기본보육 교사수")+masterdict.get("GR이후_어린이집_기본보육 원생수"),
                ],
                [
                    "연장보육A 인원",
                    masterdict.get("GR이전_어린이집_연장보육A 교사수")+masterdict.get("GR이전_어린이집_연장보육A 원생수"),
                    masterdict.get("GR이후_어린이집_연장보육A 교사수")+masterdict.get("GR이후_어린이집_연장보육A 원생수"),
                ],
                [
                    "연장보육 B인원",
                    masterdict.get("GR이전_어린이집_연장보육B 교사수")+masterdict.get("GR이전_어린이집_연장보육B 원생수"),
                    masterdict.get("GR이후_어린이집_연장보육B 교사수")+masterdict.get("GR이후_어린이집_연장보육B 원생수"),
                ],
                [
                    "야간보육 인원",
                    masterdict.get("GR이전_어린이집_야간보육 교사수")+masterdict.get("GR이전_어린이집_야간보육 원생수"),
                    masterdict.get("GR이후_어린이집_야간보육 교사수")+masterdict.get("GR이후_어린이집_야간보육 원생수"),
                ],
                [
                    "주말보육 인원",
                    masterdict.get("GR이전_어린이집_주말보육 교사수")+masterdict.get("GR이전_어린이집_주말보육 원생수"),
                    masterdict.get("GR이후_어린이집_주말보육 교사수")+masterdict.get("GR이후_어린이집_주말보육 원생수"),
                ],
                [
                    "난방 사용기간",
                    masterdict.get("GR이전_일반존_난방1 사용기간"),
                    masterdict.get("GR이후_일반존_난방1 사용기간"),
                ],
                [
                    "난방 사용시간",
                    masterdict.get("GR이전_일반존_난방1 사용시간"),
                    masterdict.get("GR이후_일반존_난방1 사용시간"),
                ],
                [
                    "난방 설정온도(℃)",
                    masterdict.get("GR이전_일반존_난방1 설정온도"),
                    masterdict.get("GR이후_일반존_난방1 설정온도"),
                ],
                [
                    "냉방 사용기간",
                    masterdict.get("GR이전_일반존_냉방1 사용기간"),
                    masterdict.get("GR이후_일반존_냉방1 사용기간"),
                ],
                [
                    "냉방 사용시간",
                    masterdict.get("GR이전_일반존_냉방1 사용시간"),
                    masterdict.get("GR이후_일반존_냉방1 사용시간"),
                ],
                [
                    "냉방 설정온도(℃)",
                    masterdict.get("GR이전_일반존_냉방1 설정온도"),
                    masterdict.get("GR이후_일반존_냉방1 설정온도"),
                ],
            ],
            columns = ["항목","그린리모델링 이전", "그린리모델링 이후"],
        )
    else:
        df = pd.DataFrame(
            [
                [
                    "운영시간",
                    masterdict.get("GR이전_보건지소·진료소_기본운영시간"),
                    masterdict.get("GR이후_보건지소·진료소_기본운영시간"),
                ],
                [
                    "외근시간",
                    masterdict.get("GR이전_보건지소·진료소_외근시간"),
                    masterdict.get("GR이후_보건지소·진료소_외근시간"),
                ],
                [
                    "외근요일",
                    masterdict.get("GR이전_보건지소·진료소_외근요일"),
                    masterdict.get("GR이후_보건지소·진료소_외근요일")
                ],
                [
                    "직원",
                    masterdict.get("GR이전_보건지소·진료소_직원수"),
                    masterdict.get("GR이후_보건지소·진료소_직원수")
                ],
                [
                    "방문객수 / 체류시간",
                    f"{masterdict.get('GR이전_보건지소·진료소_오전 방문객수')+masterdict.get('GR이전_보건지소·진료소_오후 방문객수')}명 / {(masterdict.get('GR이전_보건지소·진료소_오전 체류시간')+masterdict.get("GR이전_보건지소·진료소_오후 체류시간"))/2:.0f}분",
                ]
            ],
            columns = ["항목","그린리모델링 이전", "그린리모델링 이후"],
        )
    
    def prettify_latex_table(tex: str, header_color: str = "EAEAEA", arraystretch: float = 1) -> str:
        lines = tex.splitlines()
        new_lines = []
        in_tabular = False
        header_done = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith(r"\begin{tabular}"):
                in_tabular = True
                new_lines.append(rf"\renewcommand{{\arraystretch}}{{{arraystretch}}}")
                new_lines.append(line)
                new_lines.append(r"\hline")
                continue

            if stripped.startswith(r"\end{tabular}"):
                in_tabular = False
                new_lines.append(line)
                new_lines.append(r"\renewcommand{\arraystretch}{1}")
                continue

            if in_tabular and stripped.endswith(r"\\"):
                if not header_done:
                    new_lines.append(rf"\rowcolor[HTML]{{{header_color}}}")
                    header_done = True
                new_lines.append(line)
                new_lines.append(r"\hline")
                continue

            new_lines.append(line)

        return "\n".join(new_lines)
        
    tex = (
        df.style
        .hide(axis="index")
        .format(escape="latex")   # %, _, & 같은 LaTeX 특수문자 자동 처리
        .to_latex(
            hrules=False,         # hline은 우리가 직접 넣을 것
            column_format=(
                r">{\centering\arraybackslash}p{4cm}|"
                r">{\centering\arraybackslash}p{2.5cm}|"
                r">{\centering\arraybackslash}p{2.5cm}|"
                r">{\centering\arraybackslash}p{2.5cm}"
            ),
        )
        .replace("~", "-")
    )

    tex = prettify_latex_table(tex, header_color="EAEAEA")
    return tex


def parse_equinity(masterdict: dict) -> str:
    
    df = pd.DataFrame(
        [
            [
                "벽체단열",
                masterdict.get("GR이후_그린리모델링 공사내역_벽체단열_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_벽체단열_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_벽체단열_일치여부"),
            ],
            [
                "지붕단열",
                masterdict.get("GR이후_그린리모델링 공사내역_지붕단열_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_지붕단열_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_지붕단열_일치여부"),
            ],
            [
                "바닥단열",
                masterdict.get("GR이후_그린리모델링 공사내역_바닥단열_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_바닥단열_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_바닥단열_일치여부"),
            ],
            [
                "창호",
                masterdict.get("GR이후_그린리모델링 공사내역_창호_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_창호_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_창호_일치여부"),
            ],
            [
                "환기장치",
                masterdict.get("GR이후_그린리모델링 공사내역_환기장치_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_환기장치_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_환기장치_일치여부"),
            ],
            [
                "냉난방장치",
                masterdict.get("GR이후_그린리모델링 공사내역_냉난방장치_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_냉난방장치_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_냉난방장치_일치여부"),
            ],
            [
                "고효율 보일러",
                masterdict.get("GR이후_그린리모델링 공사내역_고효율 보일러_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_고효율 보일러_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_고효율 보일러_일치여부"),
            ],
            [
                "조명(LED)",
                masterdict.get("GR이후_그린리모델링 공사내역_조명(LED)_보고서"),
                masterdict.get("GR이후_그린리모델링 공사내역_조명(LED)_현장확인"),
                masterdict.get("GR이후_그린리모델링 공사내역_조명(LED)_일치여부"),
            ]
        ],
        columns = ["항목","보고서","현장확인","일치여부"],
    )
    
    def prettify_latex_table(tex: str, header_color: str = "EAEAEA", arraystretch: float = 1) -> str:
        lines = tex.splitlines()
        new_lines = []
        in_tabular = False
        header_done = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith(r"\begin{tabular}"):
                in_tabular = True
                new_lines.append(rf"\renewcommand{{\arraystretch}}{{{arraystretch}}}")
                new_lines.append(line)
                new_lines.append(r"\hline")
                continue

            if stripped.startswith(r"\end{tabular}"):
                in_tabular = False
                new_lines.append(line)
                new_lines.append(r"\renewcommand{\arraystretch}{1}")
                continue

            if in_tabular and stripped.endswith(r"\\"):
                if not header_done:
                    new_lines.append(rf"\rowcolor[HTML]{{{header_color}}}")
                    header_done = True
                new_lines.append(line)
                new_lines.append(r"\hline")
                continue

            new_lines.append(line)

        return "\n".join(new_lines)
        
    tex = (
        df.style
        .hide(axis="index")
        .format(escape="latex")   # %, _, & 같은 LaTeX 특수문자 자동 처리
        .to_latex(
            hrules=False,         # hline은 우리가 직접 넣을 것
            column_format=(
                r">{\centering\arraybackslash}p{4cm}|"
                r">{\centering\arraybackslash}p{2.5cm}|"
                r">{\centering\arraybackslash}p{2.5cm}|"
                r">{\centering\arraybackslash}p{2.5cm}"
            ),
        )
        .replace("~", "-")
    )

    tex = prettify_latex_table(tex, header_color="EAEAEA")
    return tex

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
    
    # metadata
    building_info = pd.read_excel(before_rebexcelpath, sheet_name="건물정보", usecols=range(6), nrows=1).iloc[0]
    metadata = MetaData(
        escape_str(building_info["건물명"])     ,
        f"{grrbefore["building"]["total_area"]:.1f}",
        building_info["주소"],
        building_info["허가일자"]   , 
    )
    
    # occupant change
    occupantchange = parse_occupantchange(checklistafter, checklistafterN)
    # hvacoperation change
    hvacoperationchange = parse_hvacoperationchange(checklistafter, checklistafterN)
    # major change
    gas_ignore = parse_gas_ignore(masterdict)
    
    # get figures
    fig_detail, fig_summary = draw_mainfigures(grrbefore, grrafter, grrafterN, gas_ignore=gas_ignore)
    fig_detail.savefig(FIG_DIR / "simulation_results.png", dpi=400, format="png", bbox_inches="tight")
    fig_summary.savefig(FIG_DIR / "energy_summary.png", dpi=400, format="png", bbox_inches="tight")
    
    # get figures (by weather)
    fig_page3_summary = draw_page3_summaryfigures(grrbefore, grrafter, grrafterN, gas_ignore=gas_ignore)
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
        "hvacoperchangetex": hvacoperationchange,
        "occupantchangetex": occupantchange,
        "majorchangetex":  parse_majorchange(masterdict),
        "allchangetex": parse_allchange(masterdict),
        "equinitytex": parse_equinity(masterdict),
        "summarytabletex" : [df.style.format(lambda x: f"{x:>6,.1f}").to_latex(**summarytablestyle).replace(r"\toprule", r"\hline").replace(r"\midrule", r"\hline").replace(r"\bottomrule", r"\hline") for df in summarytable(grrbefore, grrafter, grrafterN, gas_ignore=gas_ignore)],
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
