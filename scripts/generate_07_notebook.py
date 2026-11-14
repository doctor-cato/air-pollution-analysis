"""
scripts/generate_07_notebook.py — Sinh tự động notebook `notebooks/07_classification_alerts.ipynb` (Issue #13, W11).

Chạy:
    python scripts/generate_07_notebook.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "07_classification_alerts.ipynb"

cells = []


def add_md(source: str) -> None:
    idx = len(cells) + 1
    cells.append({
        "cell_type": "markdown",
        "id": f"cell_{idx:02d}",
        "metadata": {},
        "source": [line + "\n" for line in source.strip().split("\n")],
    })


def add_code(source: str) -> None:
    idx = len(cells) + 1
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "id": f"cell_{idx:02d}",
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.strip().split("\n")],
    })


# ---------------------------------------------------------------------------
# CELL 1: Title & Scope Framing
# ---------------------------------------------------------------------------
add_md(r"""# 07 – Phân loại Cảnh báo Ô nhiễm, Tối ưu Ngưỡng & Kiểm toán Rò rỉ Dữ liệu (Issue #13, W11)

**Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC<br>
**Dữ liệu nguồn:** `data/processed/air_pollution_final.parquet` (Baseline `VN001`) & `data/processed/air_pollution_extended_2022_2026.parquet` (Protocol A đơn trạm `VN001` & `VN003_OPENAQ_7441`)<br>
**Quy chuẩn áp dụng:** QCVN 05:2023/BTNMT — Giá trị giới hạn nồng độ bụi mịn $\text{PM}_{2.5}$ trung bình 24 giờ là $50{,}0\ \mu\text{g/m}^3$<br>
**Định vị khoa học & độ trễ ERA5:** Do khí tượng Open-Meteo ERA5 là dữ liệu tái phân tích (reanalysis) có độ trễ phát hành khoảng 5 ngày, thiết lập tại $h = 0$ giờ là **truy hồi tức thời lịch sử (retrospective historical nowcast)** tại thời điểm $t$, sử dụng thống kê $\text{PM}_{2.5}$ quá khứ kết thúc ở $t-1$ (`shift(1)`) và khí tượng đồng bộ tại $t$. Để đánh giá khả năng dự báo phòng ngừa thực thụ khi không còn chồng lấn cửa sổ 24 giờ, notebook mở rộng thực nghiệm sang các tầm $h \in \{1, 6, 12, 24\}$ giờ kèm vùng đệm loại bỏ (purge gap) nghiêm ngặt.

---

## Các Câu Hỏi Nghiên Cứu Cốt Lõi (RQ4)

1. **Định nghĩa Nhãn tương thích Quy chuẩn:** Xây dựng nhãn nhị phân $y_t$ tương thích chu kỳ 24h của QCVN 05:2023/BTNMT trên dữ liệu quan trắc gốc (không nội suy nhãn) và đối soát đầy đủ 4 quần thể dữ liệu.
2. **Kỹ nghệ Đặc trưng Quá khứ theo Trạm:** Tạo các đặc trưng trượt (`pm25_rolling_mean_24h`, `pm25_rolling_std_24h` từ $t-1$ trở về trước trên lưới giờ liên tục) và trễ `pm25_lag24` (đúng $t-24\text{h}$), loại trừ `pm10`, `pm25_was_missing`, `is_high_humidity_fog`.
3. **Bẫy Accuracy & Baseline Thực chứng:** Đối sánh `DummyClassifier(strategy='prior')` và `PersistenceRuleClassifier` (1 biến) với `LogisticRegression` và `RandomForestClassifier` qua PR-AUC (`average_precision_score`), FAR, Brier score và Confusion Matrix 2x2.
4. **Tối ưu Ngưỡng & Tầm Dự báo Tương lai:** Tinh chỉnh ngưỡng $\tau$ hoàn toàn trên tập Train OOF ($F_2$ score & Recall dưới ràng buộc Precision $\ge 0{,}60$), đồng thời kiểm tra suy giảm hiệu năng khi loại bỏ chồng lấn 24h ở $h \in \{1, 6, 12, 24\}$ giờ.
5. **Kiểm toán 4 Dạng Rò rỉ Dữ liệu:** Chứng nhận Target, Train-Test contamination (`validate_no_leakage`), Temporal (chronological split + purge gap) và Group leakage (Protocol A đơn trạm).
""")

# ---------------------------------------------------------------------------
# CELL 2: Setup
# ---------------------------------------------------------------------------
add_code(r"""import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import Image, Markdown, display

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

REPO_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.classification import (
    DEFAULT_SPLIT_TIMESTAMP,
    PRIMARY_BASELINE_STATION,
    compute_coverage_and_outage_tables,
    prepare_classification_data,
    run_extended_classification_suite,
)

BASELINE_PATH = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
EXTENDED_PATH = REPO_ROOT / "data" / "processed" / "air_pollution_extended_2022_2026.parquet"
FIGURES_DIR = REPO_ROOT / "figures"
AUDIT_REPORT_PATH = REPO_ROOT / "reports" / "classification_leakage_audit.md"
DOCS_AUDIT_PATH = REPO_ROOT / "docs" / "leakage_audit.md"
RESULTS_REPORT_PATH = REPO_ROOT / "reports" / "classification_results.md"
FINDINGS_DOC_PATH = REPO_ROOT / "docs" / "classification_findings.md"

print(f"Baseline Parquet : {BASELINE_PATH.resolve()} (exists={BASELINE_PATH.exists()})")
print(f"Extended Parquet : {EXTENDED_PATH.resolve()} (exists={EXTENDED_PATH.exists()})")
""")

# ---------------------------------------------------------------------------
# CELL 3: 4-Population Reconciliation & Outage Inspection
# ---------------------------------------------------------------------------
add_md(r"""## 1. Định nghĩa Nhãn QCVN 24h, Đối Soát 4 Quần Thể & Gián Đoạn Quan Trắc

$$ y_t = \mathbb{I}\left(\frac{1}{24}\sum_{i=0}^{23} \text{PM}_{2.5, t-i} \ge 50{,}0\right) $$
- Yêu cầu đủ `min_periods = 24` giờ hợp lệ liên tục trên lưới giờ; nếu có bất kỳ giờ thiếu nào trong cửa sổ 24h, nhãn là `NaN` để bảo toàn tính nguyên bản dữ liệu.
- Bảng đối soát dưới đây thống kê đồng thời 4 quần thể từ lưới thời gian đầy đủ đến tập evaluable cuối cùng, cùng danh sách các đợt mất tín hiệu liên tục dài nhất.
""")

add_code(r"""df_base = pd.read_parquet(BASELINE_PATH)
cov_base, gaps_base, monthly_base = compute_coverage_and_outage_tables(
    df_base, split_timestamp=DEFAULT_SPLIT_TIMESTAMP, use_split_column=False
)
print("ĐỐI SOÁT 4 QUẦN THỂ DỮ LIỆU — VN001 BASELINE:")
display(cov_base)

print("TOP ĐỢT GIÁN ĐOẠN PM2.5 LIÊN TỤC DÀI NHẤT:")
display(gaps_base.head(5))

X_tr_chk, y_tr_chk, X_te_chk, y_te_chk, meta_chk = prepare_classification_data(
    df_base, split_timestamp=DEFAULT_SPLIT_TIMESTAMP, station_id=PRIMARY_BASELINE_STATION
)
print("THỐNG KÊ MẪU SỐ VÀ PREVALENCE THỰC TẾ:")
print(f"  Train: {meta_chk['n_train_valid']:,} / {meta_chk['n_train_total']:,} giờ | Prevalence valid={meta_chk['train_prevalence_valid']:.2%} | all={meta_chk['train_prevalence_all']:.2%}")
print(f"  Test : {meta_chk['n_test_valid']:,} / {meta_chk['n_test_total']:,} giờ | Prevalence valid={meta_chk['test_prevalence_valid']:.2%} | all={meta_chk['test_prevalence_all']:.2%}")
print(f"  Số ô NaN đầu vào chưa impute (sẽ impute trong từng fold CV): Train={meta_chk['n_train_missing_cells']}, Test={meta_chk['n_test_missing_cells']}")
print(f"  Số đặc trưng đầu vào ({X_tr_chk.shape[1]} biến): {list(X_tr_chk.columns)}")
""")

# ---------------------------------------------------------------------------
# CELL 4: Run Full Protocol A Suite (Baseline + Extended VN001 & VN003)
# ---------------------------------------------------------------------------
add_md(r"""## 2. Thực Thi Suite Phân Loại Đa Phạm Vi Theo Protocol A

Thực thi trọn bộ quy trình chống rò rỉ (`SimpleImputer` + `RobustScaler` trong `ColumnTransformer`, tinh chỉnh ngưỡng $\tau^*$ qua 5-fold `TimeSeriesSplit` trên Train, xác thực `validate_no_leakage`) trên cả 3 phạm vi độc lập theo từng trạm:
1. `VN001_baseline_2026_01_15` (`air_pollution_final.parquet`, mốc Issue #7)
2. `VN001_extended_80_20` (`air_pollution_extended_2022_2026.parquet`, trạm `VN001`, Test 0 ca dương $\to$ kiểm chứng cờ `UNESTIMABLE`)
3. `VN003_extended_2022_2025` (`air_pollution_extended_2022_2026.parquet`, trạm lịch sử `VN003`, đa năm 2022–2025)
""")

add_code(r"""suite_results = run_extended_classification_suite(
    baseline_path=BASELINE_PATH,
    extended_path=EXTENDED_PATH if EXTENDED_PATH.exists() else None,
    figures_dir=FIGURES_DIR,
    report_results_path=RESULTS_REPORT_PATH,
    findings_path=FINDINGS_DOC_PATH,
    report_audit_path=AUDIT_REPORT_PATH,
    docs_audit_path=DOCS_AUDIT_PATH,
)

res_base = suite_results["VN001_baseline"]
print(f"Các phạm vi đã hoàn thành: {list(suite_results.keys())}")
print(f"Ngưỡng tối ưu F2 (VN001 baseline): LogReg tau={res_base.best_threshold_logreg:.2f} | RF tau={res_base.best_threshold_rf:.2f}")
print(f"Ngưỡng ràng buộc Prec>=0.60      : LogReg tau={res_base.best_threshold_logreg_constrained:.2f} | RF tau={res_base.best_threshold_rf_constrained:.2f}")
if res_base.threshold_warnings:
    print("Cảnh báo bão hòa biên lưới trên OOF:")
    for w in res_base.threshold_warnings:
        print(f"  - {w}")
""")

# ---------------------------------------------------------------------------
# CELL 5: Independent Test Metrics & Accuracy Trap
# ---------------------------------------------------------------------------
add_md(r"""## 3. Hiệu Năng Trên Tập Test Độc Lập & Đối Chứng Baseline (`VN001_baseline`)

- So sánh đầy đủ `DummyClassifier(strategy='prior')`, `PersistenceRuleClassifier` (ngưỡng 1 biến `pm25_rolling_mean_24h >= 50`), `Logistic Regression` và `Random Forest` theo hai cơ chế chọn ngưỡng ($F_2$ và ràng buộc Precision $\ge 0{,}60$).
- Bổ sung **False Alarm Rate (FAR)** và **Brier score** bên cạnh Accuracy, Precision, Recall, $F_1$, $F_2$, ROC-AUC, PR-AUC và ma trận nhầm lẫn 2x2.
""")

add_code(r"""print("BẢNG HIỆU NĂNG PHÂN LOẠI TRÊN TẬP TEST ĐỘC LẬP (VN001 BASELINE):")
display(res_base.metrics_table)
""")

# ---------------------------------------------------------------------------
# CELL 6: PR Curve Figure
# ---------------------------------------------------------------------------
add_md(r"""## 4. Đường cong Precision-Recall (PR Curve) vs Baseline Prevalence""")

add_code(r"""pr_path = FIGURES_DIR / "precision_recall_curve.png"
print(f"Biểu đồ PR Curve: {pr_path.resolve()} ({pr_path.stat().st_size:,} bytes)")
display(Image(filename=str(pr_path)))
""")

# ---------------------------------------------------------------------------
# CELL 7: Permutation Importance (average_precision) & LogReg Odds Ratios
# ---------------------------------------------------------------------------
add_md(r"""## 5. Permutation Importance (`average_precision`, 20 repeats) & Logistic Regression Odds Ratios

- Đo mức suy giảm PR-AUC (`average_precision`) độc lập ngưỡng kèm khoảng tin cậy 95%, kết hợp hệ số & Odds Ratio ($\exp(\beta)$) từ Logistic Regression để đánh giá trung thực tác động khí tượng bên cạnh sự chi phối tự hồi quy ở $h = 0$.
""")

add_code(r"""print("BẢNG TẦM QUAN TRỌNG ĐẶC TRƯNG & ODDS RATIOS (VN001 BASELINE):")
display(res_base.feature_importances)

feat_path = FIGURES_DIR / "feature_importance.png"
print(f"Biểu đồ Feature Importance: {feat_path.resolve()} ({feat_path.stat().st_size:,} bytes)")
display(Image(filename=str(feat_path)))
""")

# ---------------------------------------------------------------------------
# CELL 8: Feature Ablation & Future Horizon Decay
# ---------------------------------------------------------------------------
add_md(r"""## 6. Cắt Giảm Đặc Trưng (Ablation) & Tầm Dự Báo Tương Lai $h \in \{0, 1, 6, 12, 24\}$ Giờ

- Định lượng rõ mức đóng góp của cửa sổ chồng lấn 23/24h so với `Lag24 + Met` và `Meteorology-Only`, đồng thời theo dõi PR-AUC suy giảm qua các tầm $h = 1, 6, 12, 24$ giờ khi áp dụng **purge gap** nghiêm ngặt tại biên Train/Test.
""")

add_code(r"""print("THỰC NGHIỆM FEATURE ABLATION & HORIZON DECAY (VN001 BASELINE):")
display(res_base.ablation_horizon_table)
""")

# ---------------------------------------------------------------------------
# CELL 9: Extended Multi-Station Protocol A Comparison, Backtest & Sensitivity
# ---------------------------------------------------------------------------
add_md(r"""## 7. Kiểm Chứng Mở Rộng Đa Phạm Vi (Protocol A), Backtest & Độ Nhạy Nội Suy Ngắn Hạn""")

add_code(r"""print("EXPANDING-WINDOW TEMPORAL BACKTEST (TRAIN FOLDS — VN001 BASELINE):")
display(res_base.backtest_table)

if "VN001_extended" in suite_results:
    res_ext1 = suite_results["VN001_extended"]
    print("\n--- PHẠM VI VN001_extended_80_20 (Mùa sạch, Test 0 ca dương -> UNESTIMABLE) ---")
    display(res_ext1.metrics_table)

if "VN003_extended" in suite_results:
    res_vn003 = suite_results["VN003_extended"]
    print("\n--- PHẠM VI VN003_extended_2022_2025 (Lịch sử 2022-2025) ---")
    display(res_vn003.metrics_table)
    print("Feature Ablation & Horizon Decay (VN003):")
    display(res_vn003.ablation_horizon_table)
    print("Dịch chuyển theo năm trên Test (VN003):")
    display(res_vn003.annual_drift_table)
    if res_vn003.derived_sensitivity_table is not None:
        print("Kiểm tra độ nhạy `pm25_derived_interpolated` chỉ cho đặc trưng Train (VN003):")
        display(res_vn003.derived_sensitivity_table)
    fig_vn003_pr = FIGURES_DIR / "precision_recall_curve_vn003_extended.png"
    if fig_vn003_pr.exists():
        display(Image(filename=str(fig_vn003_pr)))
    fig_vn003_fi = FIGURES_DIR / "feature_importance_vn003_extended.png"
    if fig_vn003_fi.exists():
        display(Image(filename=str(fig_vn003_fi)))
""")

# ---------------------------------------------------------------------------
# CELL 10: Formal 4-Form Leakage Audit & Deliverable Summary
# ---------------------------------------------------------------------------
add_md(r"""## 8. Biên bản Kiểm toán 4 Dạng Rò rỉ Dữ liệu & Tệp Bàn Giao Chính Thức""")

add_code(r"""for p in [AUDIT_REPORT_PATH, DOCS_AUDIT_PATH, RESULTS_REPORT_PATH, FINDINGS_DOC_PATH]:
    print(f"Artifact đã ghi: {p.resolve()} (exists={p.exists()}, size={p.stat().st_size:,} bytes)")

display(Markdown(res_base.leakage_audit_markdown))
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

    code_count = len([c for c in cells if c["cell_type"] == "code"])
    md_count = len([c for c in cells if c["cell_type"] == "markdown"])
    print(f"Đã tạo {output_path} với {len(cells)} cells ({code_count} code, {md_count} markdown).")

    if execute:
        parquet_path = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
        if not parquet_path.exists():
            print(f"Không tìm thấy {parquet_path}. Bỏ qua execute.")
            return notebook_json

        print("Đang thực thi notebook 07 từ đầu đến cuối (Restart Kernel & Run All)...")
        if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        from nbclient import NotebookClient

        nb_read = nbformat.read(output_path, as_version=4)
        client = NotebookClient(nb_read, timeout=1200, kernel_name="python3")
        client.execute()
        text_exec = nbformat.writes(nb_read).rstrip("\n") + "\n"
        with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text_exec)
        print("Notebook 07 đã thực thi 100% không lỗi và đã lưu outputs.")

    return notebook_json


if __name__ == "__main__":
    generate_and_execute()
