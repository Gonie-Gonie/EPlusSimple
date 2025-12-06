
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import re
from pathlib import Path


# third-party modules
import pandas as pd

# local modules
from epsimple import (
    GreenRetrofitModel ,
    GreenRetrofitResult,
    Profile,
    Fuel,
)

# paths
mothergrmpath = Path(__file__).parents[1] / "examples/grm/ASHRAE 140 modified.grm"
latexpath     = Path(__file__).parents[1] / "docs/RegressionTestReport/part3.tex"
figuredir     = Path(__file__).parents[1] / "docs/_figures/RTR"

# ---------------------------------------------------------------------------- #
#                                   FUNCTIONS                                  #
# ---------------------------------------------------------------------------- #

def grrs2df(grrs_dict: dict[str, GreenRetrofitResult]):
    
     # --- 1) 카테고리별 키 정의 ---
    FUEL = {
        "전기": "ELECTRICITY",
        "가스": "NATURALGAS",
        "등유": "OIL",
        "지역": "DISTRICTHEATING",
    }

    USE = {
        "난방": "heating",
        "냉방": "cooling",
        "조명": "lighting",
        "유체": "circulation",
        "급탕": "hotwater",
        "태양광": "generators",
    }

    SUM = {
        "소요량": ("site_uses", "total_annual"),
        "1차소요량": ("source_uses", "total_annual"),
        "온실가스": ("co2", "total_annual"),
        "비용": ("cost", "total_annual"),
    }

    rows = []

    # --- 2) DataFrame row 생성 ---
    for name, d in grrs_dict.items():
        row = {}

        # 연료별
        for col_name, key in FUEL.items():
            row[("연료별 소요량", col_name)] = d["summary_per_area"]["site_uses"][key]

        # 용도별
        for col_name, key in USE.items():
            row[("용도별 소요량", col_name)] = d["summary_per_area"]["site_uses"][key]

        # 합계
        for col_name, (group, key) in SUM.items():
            row[("합계", col_name)] = d["summary_per_area"][group][key]
        row[("합계", "비용")] /= 1000  # 단위 변환 (천원)
        # name 추가
        row[("", "name")] = name

        rows.append(row)

    # --- 3) MultiIndex DataFrame 생성 ---
    df = pd.DataFrame(rows)
    df = df.reindex(columns=[("", "name")] + [c for c in df.columns if c != ("", "name")])
    df.set_index(("", "name"), inplace=True)
    df.index.name = "유형"
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    
    return df

def df2latex(df: pd.DataFrame) -> str:
    latex_str = df.to_latex(float_format="%.1f", escape=False)
    latex_str = re.sub(r"(\\multicolumn\{\d+\})\{[lrc]\}", r"\1{c}", latex_str)
    return latex_str

# ---------------------------------------------------------------------------- #
#                                 PROFILE TEST                                 #
# ---------------------------------------------------------------------------- #

def test_profile():
    
    mothergrm = GreenRetrofitModel.from_grjson(mothergrmpath)

    def change_profile(grm: GreenRetrofitModel, profile: Profile) -> GreenRetrofitModel:
        for zone in grm.zone:
            zone.profile = profile
        return grm

    profilegrrs = {
        profile.name: change_profile(mothergrm, profile).run().to_dict()
        for profile in Profile.get_DB("__all__")
    }

    return profilegrrs


def apply_profilechange(tex:str) -> str:
    
    # get profile contents
    grrs = test_profile()
    df   = grrs2df(grrs)
    replacement = df2latex(df)
    
    # replace in tex
    pattern = r"% ASHRAE 140-modified 용도프로필별 결과\n\\begin\{tabular\}.*?\\end\{tabular\}"
    replaced_tex = re.sub(pattern, lambda m: replacement, tex, flags=re.DOTALL)
    
    return replaced_tex


# ---------------------------------------------------------------------------- #
#                                 WEATHER TEST                                 #
# ---------------------------------------------------------------------------- #

def test_weather():
    
    mothergrmp = GreenRetrofitModel.from_grjson(mothergrmpath)
    addrlist = [
        # 중부1
        "강원특별자치도 철원군",
        "강원특별자치도 춘천시",
        "경기도 의정부시",
        # 중부2
        "경상북도 안동시",
        "대전광역시 서구",
        "서울특별시 중구",
        "세종특별자치시 세종시",
        "인천광역시 남동구",
        "전북특별자치도 전주시 완산구",
        "충청남도 홍성군",
        "충청북도 청주시 상당구",
        # 남부
        "경상남도 창원시 의창구",
        "광주광역시 서구",
        "대구광역시 달서구",
        "부산광역시 연제구",
        "울산광역시 남구",
        "전라남도 무안군",
        # 제주
        "제주특별자치도 제주시",
    ]
    
    def change_address(grm: GreenRetrofitModel, address: str) -> GreenRetrofitModel:
        grm.address = address
        return grm
    
    weathergrrs = {
        address: change_address(mothergrmp, address).run().to_dict()   
        for address in addrlist
    }
    
    return weathergrrs

def apply_weatherchange(tex:str) -> str:
    
    # get weather contents
    grrs = test_weather()
    df   = grrs2df(grrs)
    replacement = df2latex(df)
    
    # replace in tex
    pattern = r"% ASHRAE 140-modified 지역별 결과\n\\begin\{tabular\}.*?\\end\{tabular\}"
    replaced_tex = re.sub(pattern, lambda m: replacement, tex, flags=re.DOTALL)
    
    return replaced_tex

# ---------------------------------------------------------------------------- #
#                                 BUILD REPORT                                 #
# ---------------------------------------------------------------------------- #

def main():
    
    # read
    with open(latexpath, "r", encoding="utf-8") as file:
        tex = file.read()
    
    # apply
    tex = apply_profilechange(tex)
    tex = apply_weatherchange(tex)
    
    # write
    with open(latexpath, "w", encoding="utf-8") as file:
        file.write(tex)   
    



if __name__ == "__main__":
    main()