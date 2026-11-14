"""
scripts/generate_06_notebook.py — Sinh tự động notebook `notebooks/06_regression_modeling.ipynb` (Issue #12, W10 + Scope Extension).

Chạy:
    python scripts/generate_06_notebook.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "06_regression_modeling.ipynb"

cells = []


def add_md(source: str) -> None:
    idx = len(cells) + 1
    cells.append(
        {
            "cell_type": "markdown",
            "id": f"cell_{idx:02d}",
            "metadata": {},
            "source": [line + "\n" for line in source.strip().split("\n")],
        }
    )


def add_code(source: str) -> None:
    idx = len(cells) + 1
    cells.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "id": f"cell_{idx:02d}",
            "metadata": {},
            "outputs": [],
            "source": [line + "\n" for line in source.strip().split("\n")],
        }
    )


# ---------------------------------------------------------------------------
# CELL 1: Title & Questions
# ---------------------------------------------------------------------------
add_md(r"""# 06 – Hồi quy Tuyến tính OLS, Chẩn đoán 4 Giả định LINE & Mở rộng Đa Trạm 2022–2026 (Issue #12, W10)

**Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC<br>
**Dữ liệu nguồn:**
- Baseline: `data/processed/air_pollution_final.parquet` (`VN001_HANOI_556_NGUYEN_VAN_CU`, 07/2025–07/2026, mốc cắt `2026-01-15`)
- Mở rộng (Issue #44/#50): `data/processed/air_pollution_extended_2022_2026.parquet` (`VN001_HANOI_556_NGUYEN_VAN_CU` và `VN003_HANOI_OPENAQ_7441` 01/2022–04/2025, mốc 80/20 tách trạm theo **Protocol A**)

---

## Trọng Tâm Thực Nghiệm (Issue #12 + W10 Slide + Scope Extension)

1. **Chống rò rỉ dữ liệu & Protocol A/B:** Từ chối fail-closed việc gộp đa trạm lệch thời gian (Protocol B); toàn bộ imputer/scaler đặt trong `Pipeline` fit từng fold CV và kiểm chứng bằng `validate_no_leakage()`.
2. **Kiểm toán VIF & 4 Giả định LINE:**
   - **L (Linearity):** Kiểm định Ramsey **RESET** (bậc 2 & 3) + đường cong **LOWESS**, không dựa vào tính chất đại số $\text{corr}(\hat{e}, \hat{y}) \equiv 0$.
   - **I (Independence):** Durbin-Watson, ACF phần dư và độ nhạy sai số chuẩn **HAC Newey-West** qua các độ trễ $L \in \{0, L_{\text{NW plug-in}}, 12, 24, 48, 72, 168\}$.
   - **N (Normality):** Normal Q-Q, Jarque-Bera, Shapiro-Wilk (khi $n \le 5000$) và kiểm chứng $\log(1 + \text{PM}_{2.5})$ trên Train.
   - **E (Equal Variance):** Breusch-Pagan & Scale-Location kèm LOWESS.
3. **Điểm đòn bẩy & Ảnh hưởng:** Phân tách Outliers ($|\text{stud\_resid}| > 3$), High Leverage ($h_{ii} > 2p/n$), Cook's $D$ ($>4/n$, $>0,5$, $>1,0$).
4. **Giải phẫu $R^2$ âm, Ablation & Độ ổn định:** Thử nghiệm bỏ chu kỳ mùa `month_sin/cos`, bổ sung `pm25_lag24` nội trạm, Rolling-Origin CV trong Train, độ ổn định phân tầng kèm $n_{\text{eff}}$, và độ nhạy `pm25_derived_interpolated` (chỉ trên Train).
""")

# ---------------------------------------------------------------------------
# CELL 2: Setup & Protocol B Guard Check
# ---------------------------------------------------------------------------
add_code(r"""import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import Image, display

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

REPO_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.regression import (
    DEFAULT_SPLIT_TIMESTAMP,
    EXTENDED_HISTORICAL_STATION,
    PRIMARY_BASELINE_STATION,
    prepare_regression_data,
    run_extended_regression_suite,
)

BASELINE_PATH = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
EXTENDED_PATH = REPO_ROOT / "data" / "processed" / "air_pollution_extended_2022_2026.parquet"
FIG_DIR = REPO_ROOT / "figures"
REPORT_PATH = REPO_ROOT / "reports" / "regression_results.md"

print(f"Baseline Parquet: {BASELINE_PATH.exists()} ({BASELINE_PATH})")
print(f"Extended Parquet: {EXTENDED_PATH.exists()} ({EXTENDED_PATH})")
""")

# ---------------------------------------------------------------------------
# CELL 3: Fail-closed Protocol B Verification & Full Suite Run
# ---------------------------------------------------------------------------
add_md(r"""## 1. Kiểm Chứng Chặn Gộp Đa Trạm (Protocol B Guard) & Thực Thi Bộ 3 Phạm Vi (Protocol A)
""")

add_code(r"""if EXTENDED_PATH.exists():
    df_ext = pd.read_parquet(EXTENDED_PATH)
    try:
        prepare_regression_data(df_ext, use_split_column=True, station_id=None)
    except ValueError as exc:
        print("✓ Fail-closed Protocol B Guard hoạt động đúng:", exc)

suite = run_extended_regression_suite(
    baseline_path=BASELINE_PATH,
    extended_path=EXTENDED_PATH if EXTENDED_PATH.exists() else None,
    figures_dir=FIG_DIR,
    report_path=REPORT_PATH,
)

summary_rows = []
for name, res in suite.items():
    mt = res.metrics_table.set_index("Model")
    d = res.line_diagnostics
    summary_rows.append({
        "Run": name,
        "Station": res.station_id,
        "Train": res.n_train,
        "Test": res.n_test,
        "Dummy RMSE": mt.loc["Baseline (Dummy Mean)", "RMSE (µg/m³)"],
        "OLS MAE": mt.loc["OLS Linear Regression", "MAE (µg/m³)"],
        "OLS RMSE": mt.loc["OLS Linear Regression", "RMSE (µg/m³)"],
        "OLS Test R²": mt.loc["OLS Linear Regression", "R²"],
        "RESET(2) F": round(d.reset_power2_f, 2),
        "RESET(2) p": f"{d.reset_power2_pvalue:.2e}",
        "DW": round(d.durbin_watson, 4),
        "ACF(1)": round(float(d.acf_values[1]), 4),
    })

display(pd.DataFrame(summary_rows))
""")

# ---------------------------------------------------------------------------
# CELL 4: VN001 Baseline — VIF, Coefficients, HAC Lag Sensitivity
# ---------------------------------------------------------------------------
add_md(r"""## 2. Trạm Chính VN001 Baseline (`2026-01-15`) — VIF, Hệ Số HAC & Độ Nhạy Độ Trễ L
""")

add_code(r"""res_b = suite["VN001_baseline"]
print("Bảng VIF trên Train (chú ý biến có 5 <= VIF < 10):")
display(res_b.vif_table)

print("\nBảng hệ số OLS (Classical vs HAC-24):")
display(res_b.coefficients.drop(columns=["p_hac_num"], errors="ignore"))

print(f"\nĐộ nhạy p-value theo độ trễ HAC (NW plug-in = {res_b.line_diagnostics.plugin_nw_maxlags}h):")
display(res_b.hac_sensitivity_table.pivot(index="lag_label", columns="Feature", values="p_display"))
""")

# ---------------------------------------------------------------------------
# CELL 5: LINE Diagnostics, Influence Breakdown, Ablation & CV (VN001 Baseline)
# ---------------------------------------------------------------------------
add_md(r"""## 3. Chẩn Đoán LINE, Phân Loại Ảnh Hưởng, Ablation $R^2 < 0$ & Rolling-Origin CV (VN001 Baseline)
""")

add_code(r"""d = res_b.line_diagnostics
print(f"Ramsey RESET(p=2): F = {d.reset_power2_f:.2f}, p = {d.reset_power2_pvalue:.2e} -> Linearity VIOLATED = {d.linearity_violated}")
print(f"Ramsey RESET(p=3): F = {d.reset_power3_f:.2f}, p = {d.reset_power3_pvalue:.2e}")
print(f"Durbin-Watson = {d.durbin_watson:.4f}, ACF(1) = {d.acf_values[1]:.4f}, ACF(24) = {d.acf_values[24]:.4f}")
print(f"Jarque-Bera = {d.jarque_bera_stat:.1f} (p = {d.jarque_bera_pvalue:.2e}), Skew = {d.skewness:.3f}, Excess Kurtosis = {d.kurtosis:.3f}")
print(f"Breusch-Pagan LM = {d.breusch_pagan_stat:.2f} (p = {d.breusch_pagan_pvalue:.2e})")
print(f"Log1p Skew Comparison: original={res_b.log1p_metrics['original_resid_skew']:.3f} vs log1p={res_b.log1p_metrics['log1p_resid_skew']:.3f}")

inf = res_b.influence_summary
print("\nPhân loại Outliers / High Leverage / Influential Points:")
print({k: v for k, v in inf.items() if k != "top_influential"})
display(inf["top_influential"])

print("\nThử nghiệm Ablation giải phẫu R² âm & Rolling-Origin CV:")
display(res_b.ablation_table)
print("Chẩn đoán dịch chuyển phân phối:", res_b.ablation_diagnostics)
display(res_b.rolling_origin_cv)
""")

# ---------------------------------------------------------------------------
# CELL 6: Extended Historical Multi-Year Station (VN003 2022–2025 & VN001 Extended)
# ---------------------------------------------------------------------------
add_md(r"""## 4. Kết Quả Mở Rộng Lịch Sử Đa Năm (VN001 Extended 80/20 & VN003 2022–2025)
""")

add_code(r"""for key in ["VN001_extended", "VN003_extended"]:
    if key in suite:
        r = suite[key]
        print(f"=== {key} ({r.station_id}) | Train={r.n_train:,}, Test={r.n_test:,} ===")
        display(r.metrics_table)
        display(r.ablation_table)
        if not r.stratified_stability.empty:
            print("Độ ổn định hệ số phân tầng (kèm rho1 & n_eff):")
            display(r.stratified_stability)
        if r.derived_sensitivity is not None:
            ds = r.derived_sensitivity
            print(
                f"Độ nhạy pm25_derived_interpolated (Train-only): +{ds['n_derived_hours_added_in_train']}h, "
                f"max|ΔBeta|={ds['max_abs_beta_diff']:.4f}, "
                f"Test RMSE obs={ds['test_rmse_observed_model']:.2f} vs der_train={ds['test_rmse_derived_train_model']:.2f}"
            )
""")

# ---------------------------------------------------------------------------
# CELL 7: Diagnostic Figures & Dynamic Report Confirmation
# ---------------------------------------------------------------------------
add_md(r"""## 5. Biểu Đồ Chẩn Đoán LINE (300 DPI kèm LOWESS) & Báo Cáo Nghiệm Thu
""")

add_code(r"""fig_base = FIG_DIR / "regression_line_diagnostics.png"
if fig_base.exists():
    print(f"Hiển thị {fig_base.name}:")
    display(Image(filename=str(fig_base)))

fig_vn003 = FIG_DIR / "regression_line_diagnostics_vn003_extended.png"
if fig_vn003.exists():
    print(f"Hiển thị {fig_vn003.name}:")
    display(Image(filename=str(fig_vn003)))

print(f"Đã xuất báo cáo động: {REPORT_PATH.resolve()} ({REPORT_PATH.stat().st_size:,} bytes)")
""")


def build_notebook_dict() -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def generate_and_execute(output_path: Path = NOTEBOOK_PATH, execute: bool = True) -> dict:
    notebook_json = build_notebook_dict()

    for index, cell in enumerate(notebook_json["cells"], start=1):
        if cell["cell_type"] != "code":
            continue
        try:
            compile("".join(cell["source"]), f"<cell {index}>", "exec")
        except SyntaxError as exc:
            raise SystemExit(f"Cell {index} lỗi cú pháp: {exc}") from exc

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import nbformat

    nb_obj = nbformat.from_dict(notebook_json)
    text_init = nbformat.writes(nb_obj).rstrip("\n") + "\n"
    with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text_init)

    nb_cells = notebook_json["cells"]
    code_count = len([c for c in nb_cells if c["cell_type"] == "code"])
    md_count = len([c for c in nb_cells if c["cell_type"] == "markdown"])
    print(f"Đã tạo {output_path} với {len(nb_cells)} cells ({code_count} code, {md_count} markdown).")

    if execute:
        parquet_path = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
        if not parquet_path.exists():
            print(f"Không tìm thấy {parquet_path}. Bỏ qua execute.")
            return notebook_json

        print("Đang thực thi notebook 06 từ đầu đến cuối (Restart Kernel & Run All)...")
        import asyncio
        import sys
        if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        from nbclient import NotebookClient

        nb_read = nbformat.read(output_path, as_version=4)
        client = NotebookClient(nb_read, timeout=1200, kernel_name="python3")
        client.execute()
        text_exec = nbformat.writes(nb_read).rstrip("\n") + "\n"
        with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text_exec)
        print("Notebook 06 đã thực thi 100% không lỗi và đã lưu outputs.")

    return notebook_json


if __name__ == "__main__":
    generate_and_execute()
