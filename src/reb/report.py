import os
import pandas as pd
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
from datetime import date
import subprocess

# ======================
# 경로 설정
# ======================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # EPLUSSIMPLE/
SRC_DIR = os.path.join(BASE_DIR, "src", "reb")
DIST_DIR = os.path.join(BASE_DIR, "dist", "reb-report")
FIG_DIR = os.path.join(DIST_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ======================
# 그래프 예시 생성
# ======================
months = list(range(1, 13))
temp_before = [5,6,9,14,20,24,28,29,25,19,11,6]
temp_after  = [4,5,8,13,19,23,27,28,24,18,10,5]
temp_yearn  = [4,5,9,13,21,24,27,28,25,19,11,6]

plt.figure()
plt.plot(months, temp_before, label="Before")
plt.plot(months, temp_after, label="After")
plt.plot(months, temp_yearn, label="Year-N")
plt.xlabel("Month")
plt.ylabel("Outdoor Temp (°C)")
plt.legend()
weather_fig = os.path.join(FIG_DIR, "weather.png")
plt.savefig(weather_fig, bbox_inches="tight")
plt.close()

# 에너지 그래프 예시
monthly_energy = pd.DataFrame({
    "Month": months,
    "Before": [100,90,80,70,60,55,60,65,70,80,90,95],
    "After":  [90,80,70,60,55,50,52,55,60,70,80,85],
    "YearN":  [91,82,72,63,56,51,53,56,61,71,82,86],
})
annual = monthly_energy[["Before","After","YearN"]].sum()
plt.bar(annual.index, annual.values)
plt.ylabel("Total Annual Energy (kWh/m²)")
energy_fig1 = os.path.join(FIG_DIR, "annual_energy.png")
plt.savefig(energy_fig1, bbox_inches="tight")
plt.close()

plt.figure()
for col in ["Before", "After", "YearN"]:
    plt.plot(monthly_energy["Month"], monthly_energy[col], label=col)
plt.legend()
plt.xlabel("Month")
plt.ylabel("Energy (kWh/m²)")
energy_fig2 = os.path.join(FIG_DIR, "monthly_energy.png")
plt.savefig(energy_fig2, bbox_inches="tight")
plt.close()

# ======================
# LaTeX 렌더링
# ======================
env = Environment(loader=FileSystemLoader(SRC_DIR))
template = env.get_template("report_template.tex")

performance_data = [
    {"name": "U-value (W/m²K)", "before": 1.8, "after": 0.95, "nyear": 0.97},
    {"name": "Infiltration (ACH)", "before": 0.9, "after": 0.4, "nyear": 0.45},
    {"name": "Window SHGC", "before": 0.65, "after": 0.55, "nyear": 0.56},
]

context = {
    "weather_fig": "weather.png",
    "energy_fig1": "annual_energy.png",
    "energy_fig2": "monthly_energy.png",
    "performance": performance_data,
    "weather_summary": "기상 데이터는 세 시나리오 간 유사한 월별 경향을 보였으나, 리모델링 이후 온도가 다소 낮게 나타났다.",
    "conclusion_text": "리모델링 후 건물의 단열성능이 향상되어 연간 에너지 사용량이 약 15% 절감되었다.",
    "today": date.today().strftime("%Y-%m-%d"),
}

rendered_tex = template.render(**context)

tex_path = os.path.join(DIST_DIR, "report.tex")
with open(tex_path, "w", encoding="utf-8") as f:
    f.write(rendered_tex)


def build_pdf_with_latexmk(tex_path, build_dir):
    tex_name = os.path.basename(tex_path)
    cmd = ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_name]

    subprocess.run(cmd, cwd=build_dir, check=True)
    print(f"✅ latexmk build completed: {os.path.join(build_dir, tex_name.replace('.tex', '.pdf'))}")


# ======================
# PDF 빌드
# ======================
build_pdf_with_latexmk(tex_path, DIST_DIR)
print(f"✅ PDF 생성 완료: {os.path.join(DIST_DIR, 'report.pdf')}")
