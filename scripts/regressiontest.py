
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
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

# settings
mothergrmpath = Path(__file__).parents[1] / "examples/grm/ASHRAE 140 modified.grm"


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


# ---------------------------------------------------------------------------- #
#                                 BUILD REPORT                                 #
# ---------------------------------------------------------------------------- #

def summary_grrs2dataframe(grrs_dict: dict[str, GreenRetrofitResult]):
    
     # --- 1) 카테고리별 키 정의 ---
    FUEL = {
        "전기 [kWh/m2]": "ELECTRICITY",
        "가스 [kWh/m2]": "NATURALGAS",
        "등유 [kWh/m2]": "OIL",
        "지역난방 [kWh/m2]": "DISTRICTHEATING",
    }

    USE = {
        "난방 [kWh/m2]": "heating",
        "냉방 [kWh/m2]": "cooling",
        "조명 [kWh/m2]": "lighting",
        "유체동력 [kWh/m2]": "circulation",
        "급탕 [kWh/m2]": "hotwater",
        "태양광 [kWh/m2]": "generators",
    }

    SUM = {
        "소요량 [kWh/m2]": ("site_uses", "total_annual"),
        "1차소요량 [kWh/m2]": ("source_uses", "total_annual"),
        "온실가스 [kgCO2eq/m2]": ("co2", "total_annual"),
        "비용 [won/m2]": ("cost", "total_annual"),
    }

    rows = []

    # --- 2) DataFrame row 생성 ---
    for name, d in grrs_dict.items():
        row = {}

        # 연료별
        for col_name, key in FUEL.items():
            row[("연료별", col_name)] = d["summary_per_area"]["site_uses"][key]

        # 용도별
        for col_name, key in USE.items():
            row[("용도별", col_name)] = d["summary_per_area"]["site_uses"][key]

        # 합계
        for col_name, (group, key) in SUM.items():
            row[("합계", col_name)] = d["summary_per_area"][group][key]

        # name 추가
        row[("", "name")] = name

        rows.append(row)

    # --- 3) MultiIndex DataFrame 생성 ---
    df = pd.DataFrame(rows)
    df = df.reindex(columns=[("", "name")] + [c for c in df.columns if c != ("", "name")])
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    
    return df


profilegrrs = test_profile()
profiledf   = summary_grrs2dataframe(profilegrrs)

pass