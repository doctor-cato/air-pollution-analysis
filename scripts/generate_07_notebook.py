"""
scripts/generate_07_notebook.py — Sinh tự động notebook `notebooks/07_classification_alerts.ipynb` (Issue #13, W11).

Chạy:
    python scripts/generate_07_notebook.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "07_classification_alerts.ipynb"

cells = []


def add_md(source: str):
    idx = len(cells) + 1
    cells.append({
        "cell_type": "markdown",
        "id": f"cell_{idx:02d}",
        "metadata": {},
        "source": [line + "\n" for line in source.strip().split("\n")],
    })


def add_code(source: str):
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
# CELL 1: Title
# ---------------------------------------------------------------------------
add_md(r"""# 07 – Phân loại Cảnh báo Ô nhiễm, Tối ưu Ngưỡng & Kiểm toán Rò rỉ Dữ liệu (Issue #13, W11)

**Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC<br>
**Dữ liệu nguồn:** `data/processed/air_pollution_final.parquet` (Trạm NCEM/VEA 556 Nguyễn Văn Cừ, Hà Nội)<br>
**Quy chuẩn áp dụng:** QCVN 05:2023/BTNMT — Giá trị giới hạn nồng độ bụi mịn PM₂.₅ trung bình 24 giờ là 50 µg/m³<br>
**Mục tiêu nghiên cứu:** Xây dựng hệ thống phân loại nhị phân cảnh báo sớm các đợt ô nhiễm vượt ngưỡng an toàn dựa trên đặc trưng quá khứ, giải quyết bài toán mất cân bằng lớp qua đường cong Precision-Recall (PR-AUC), tối ưu hóa ngưỡng quyết định theo mục tiêu bảo vệ sức khỏe cộng đồng ($F_2$ score), và thực hiện kiểm toán rà soát 4 dạng rò rỉ dữ liệu.

---

## Các Câu Hỏi Nghiên Cứu Cốt Lõi (RQ4)

1. **Định nghĩa Nhãn tương thích Quy chuẩn:** Làm thế nào để định nghĩa nhãn cảnh báo ô nhiễm nhị phân bảo đảm tính tương thích toán học về chu kỳ lấy mẫu 24h của QCVN 05:2023/BTNMT mà không vi phạm rò rỉ dữ liệu tương lai?
2. **Kỹ nghệ Đặc trưng Quá khứ:** Liệu các biến thống kê trượt quá khứ (trung bình, độ lệch chuẩn 24h) kết hợp với các tham số thời tiết bề mặt có đủ sức mạnh phân biệt các đợt bùng phát ô nhiễm?
3. **Bẫy Accuracy & Đánh giá qua PR-AUC:** Khi tỷ lệ vượt ngưỡng trong dữ liệu bị mất cân bằng, tại sao Accuracy trở thành cái bẫy nguy hiểm và đường cong Precision-Recall phản ánh hiệu năng trung thực như thế nào?
4. **Tối ưu Ngưỡng Quyết định:** Làm thế nào để giải quyết sự đánh đổi giữa Precision (báo động giả) và Recall (bỏ sót cảnh báo nguy hại) thông qua việc tinh chỉnh ngưỡng trên tập Train/Validation theo hàm mục tiêu $F_\beta$ ($\beta > 1$)?
5. **Kiểm toán Rò rỉ Dữ liệu:** Đảm bảo hệ thống đạt chuẩn qua 4 tiêu chí kiểm toán: Target, Train-Test contamination, Temporal, và Group leakage.
""")

# ---------------------------------------------------------------------------
# CELL 2: Setup
# ---------------------------------------------------------------------------
add_code(r"""import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

warnings.filterwarnings("ignore")

# Cố định hạt giống ngẫu nhiên theo quy định toàn dự án
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# Thiết lập đường dẫn thư mục gốc repo
REPO_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.classification import (
    DEFAULT_SPLIT_TIMESTAMP,
    ClassificationResults,
    compute_feature_importances,
    engineer_classification_features,
    evaluate_classifier,
    generate_leakage_audit_markdown,
    prepare_classification_data,
    render_feature_importance_figure,
    render_pr_curve_figure,
    run_classification_pipeline,
    tune_classification_threshold,
    write_classification_findings,
    write_classification_report,
)
from src.cleaning_pipeline import (
    DEFAULT_ALERT_MIN_PERIODS,
    DEFAULT_ALERT_THRESHOLD_UG_M3,
    DEFAULT_ALERT_WINDOW_HOURS,
    build_alert_label,
)

DATA_PATH = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
PR_FIG_PATH = REPO_ROOT / "figures" / "precision_recall_curve.png"
FEAT_FIG_PATH = REPO_ROOT / "figures" / "feature_importance.png"
AUDIT_REPORT_PATH = REPO_ROOT / "reports" / "classification_leakage_audit.md"
RESULTS_REPORT_PATH = REPO_ROOT / "reports" / "classification_results.md"
FINDINGS_DOC_PATH = REPO_ROOT / "docs" / "classification_findings.md"

print(f"Data path: {DATA_PATH.resolve()}")
print(f"Tồn tại trên đĩa: {DATA_PATH.exists()}")
""")

# ---------------------------------------------------------------------------
# CELL 3: Alert Label Definition & Imbalance Measurement
# ---------------------------------------------------------------------------
add_md(r"""## 1. Định nghĩa Nhãn Cảnh báo & Đo lường Mất cân bằng Lớp (Task 0.7b)

QCVN 05:2023/BTNMT quy định giới hạn trung bình 24 giờ là 50 µg/m³. Nhãn nhị phân $y_t$ được xác định:
$$ y_t = \mathbb{I}\left(\frac{1}{24}\sum_{i=0}^{23} \text{PM}_{2.5, t-i} \ge 50.0\right) $$
- **Xử lý thiếu dữ liệu:** Yêu cầu đủ `min_periods = 24` giờ liên tục không có NaN. Nếu thiếu dữ liệu, nhãn là `NaN` (không suy diễn võ đoán).
- **Thống nhất hai mẫu số:**
  1. *Mẫu số hợp lệ (Valid rolling):* 5.317 giờ $\to$ Tỷ lệ dương: 31,13% (1.655 / 5.317).
  2. *Mẫu số toàn bộ thời gian:* 9.044 giờ $\to$ Tỷ lệ dương: 18,30% (1.655 / 9.044).
""")

add_code(r"""df = pd.read_parquet(DATA_PATH)
X_train, y_train, X_test, y_test, metadata = prepare_classification_data(
    df, split_timestamp=DEFAULT_SPLIT_TIMESTAMP
)

print("THỐNG KÊ MẪU SỐ VÀ TỶ LỆ DƯƠNG (PREVALENCE):")
print(f"  Train: {metadata['n_train_valid']:,} dòng hợp lệ / {metadata['n_train_total']:,} tổng dòng")
print(f"         Prevalence (mẫu số hợp lệ): {metadata['train_prevalence_valid']:.2%}")
print(f"         Prevalence (toàn bộ thời gian): {metadata['train_prevalence_all']:.2%}")
print(f"  Test:  {metadata['n_test_valid']:,} dòng hợp lệ / {metadata['n_test_total']:,} tổng dòng")
print(f"         Prevalence (mẫu số hợp lệ): {metadata['test_prevalence_valid']:.2%}")
print(f"         Prevalence (toàn bộ thời gian): {metadata['test_prevalence_all']:.2%}")
""")

# ---------------------------------------------------------------------------
# CELL 4: Past-only Feature Engineering
# ---------------------------------------------------------------------------
add_md(r"""## 2. Kỹ nghệ Đặc trưng Quá khứ (Past-only Feature Engineering)

Quy tắc bất biến: **Tuyệt đối không truy xuất thông tin tương lai**.
- Thống kê trượt quá khứ `pm25_rolling_mean_24h` và `pm25_rolling_std_24h` được tính với `shift(1)`, chỉ sử dụng dữ liệu từ $t-1$ trở về trước.
- Biến trễ `pm25_lag24`: nồng độ đúng 24 giờ trước.
- Biến khí tượng bề mặt và cờ lặng gió (`wind_speed < 0.5 m/s`).
- Tái sử dụng 4 cột chu kỳ có sẵn trong Parquet: `hour_sin`, `hour_cos`, `month_sin`, `month_cos`.
- Loại bỏ hoàn toàn `pm10` (tránh đa cộng tuyến) và `pm25_was_missing` (tránh target leakage).
""")

add_code(r"""print(f"Số lượng đặc trưng đầu vào: {X_train.shape[1]}")
print("Danh sách đặc trưng:")
for col in X_train.columns:
    print(f"  - {col}")

display(X_train.head(3))
""")

# ---------------------------------------------------------------------------
# CELL 5: Model Training
# ---------------------------------------------------------------------------
add_md(r"""## 3. Huấn luyện Mô hình Phân loại

Huấn luyện 3 mô hình trên tập Train:
1. **Baseline DummyClassifier:** Chiến lược dự báo theo phân phối tiên nghiệm (`strategy='prior'`).
2. **Logistic Regression:** Áp dụng `class_weight='balanced'` để bù trừ mất cân bằng lớp và chuẩn hóa đặc trưng qua `RobustScaler`.
3. **Random Forest Classifier:** Rừng cây ngẫu nhiên 100 cây, độ sâu tối đa 8, trọng số lớp cân bằng.
""")

add_code(r"""# 1. Baseline
dummy = DummyClassifier(strategy="prior")
dummy.fit(X_train, y_train)

# 2. Logistic Regression
logreg = Pipeline([
    ("scaler", RobustScaler()),
    ("clf", LogisticRegression(class_weight="balanced", random_state=RANDOM_STATE, max_iter=1000)),
])
logreg.fit(X_train, y_train)

# 3. Random Forest
rf = RandomForestClassifier(
    n_estimators=100, max_depth=8, class_weight="balanced", random_state=RANDOM_STATE
)
rf.fit(X_train, y_train)

print("Đã hoàn thành huấn luyện 3 mô hình trên tập Train.")
""")

# ---------------------------------------------------------------------------
# CELL 6: Operational Threshold Tuning
# ---------------------------------------------------------------------------
add_md(r"""## 4. Tinh chỉnh Ngưỡng Quyết định theo Mục tiêu Vận hành ($F_2$ Score)

Trong cảnh báo ô nhiễm không khí nguy hại, **bỏ sót một đợt ô nhiễm nặng (False Negative)** gây hậu quả sức khỏe nghiêm trọng hơn nhiều so với **báo động giả (False Positive)**.<br>
Do đó, hàm mục tiêu vận hành ưu tiên độ nhạy là $F_2$ score:
$$ F_2 = \frac{5 \cdot \text{Precision} \cdot \text{Recall}}{4 \cdot \text{Precision} + \text{Recall}} $$
Ngưỡng quyết định $\tau$ được tối ưu hoàn toàn trên tập Train qua 5-fold `TimeSeriesSplit` (tuyệt đối không tune trên tập Test).
""")

add_code(r"""tau_logreg = tune_classification_threshold(logreg, X_train, y_train, metric="f2")
tau_rf = tune_classification_threshold(rf, X_train, y_train, metric="f2")

# Đảm bảo các mô hình đã được huấn luyện trọn vẹn trên toàn bộ Train trước khi test
logreg.fit(X_train, y_train)
rf.fit(X_train, y_train)

print(f"Ngưỡng quyết định tối ưu F2 cho Logistic Regression: tau = {tau_logreg:.2f}")
print(f"Ngưỡng quyết định tối ưu F2 cho Random Forest:       tau = {tau_rf:.2f}")
""")

# ---------------------------------------------------------------------------
# CELL 7: Independent Test Evaluation & Metrics
# ---------------------------------------------------------------------------
add_md(r"""## 5. Đánh giá Độc lập trên Tập TEST & Vượt qua Bẫy Accuracy

Đánh giá hiệu năng của các mô hình trên tập Test độc lập với ngưỡng đã chốt.
- **Bẫy Accuracy:** Mô hình Baseline Dummy có thể đạt Accuracy $\approx 71\%$ (bằng tỷ lệ lớp đa số) nhưng Recall = 0.0% (hoàn toàn vô dụng trong việc cảnh báo ô nhiễm).
- **Tiêu chuẩn vàng:** Tập trung vào Recall, Precision, $F_2$, và PR-AUC.
""")

add_code(r"""m_dummy = evaluate_classifier("Baseline (Dummy Prior)", dummy, X_test, y_test, threshold=0.50)
m_logreg = evaluate_classifier("Logistic Regression (Balanced)", logreg, X_test, y_test, threshold=tau_logreg)
m_rf = evaluate_classifier("Random Forest (Balanced)", rf, X_test, y_test, threshold=tau_rf)

metrics_table = pd.DataFrame([{
    "Model": m.model_name,
    "Threshold": m.threshold,
    "Accuracy": f"{m.accuracy:.2%}",
    "Precision": f"{m.precision:.2%}",
    "Recall": f"{m.recall:.2%}",
    "F1": f"{m.f1:.4f}",
    "F2": f"{m.f2:.4f}",
    "ROC-AUC": f"{m.roc_auc:.4f}",
    "PR-AUC": f"{m.pr_auc:.4f}",
    "Confusion Matrix [TN, FP, FN, TP]": str(m.confusion_matrix),
} for m in [m_dummy, m_logreg, m_rf]])

print("BẢNG HIỆU NĂNG PHÂN LOẠI TRÊN TẬP TEST ĐỘC LẬP:")
display(metrics_table)
""")

# ---------------------------------------------------------------------------
# CELL 8: PR Curve Visualization
# ---------------------------------------------------------------------------
add_md(r"""## 6. Đường cong Precision-Recall (PR Curve) vs Baseline Prevalence
""")

add_code(r"""models_dict = {
    "Logistic Regression": logreg,
    "Random Forest": rf,
}
render_pr_curve_figure(models_dict, X_test, y_test, metadata["test_prevalence_valid"], PR_FIG_PATH)
print(f"Đã lưu biểu đồ PR Curve: {PR_FIG_PATH.resolve()}")

from IPython.display import Image
Image(filename=str(PR_FIG_PATH))
""")

# ---------------------------------------------------------------------------
# CELL 9: Feature Importance
# ---------------------------------------------------------------------------
add_md(r"""## 7. Tầm quan trọng của Đặc trưng (Permutation Importance)

Đo lường mức độ suy giảm Recall khi xáo trộn từng đặc trưng trên tập Test độc lập (thay thế SHAP theo nguyên tắc YAGNI).
""")

add_code(r"""imp_df = compute_feature_importances(rf, X_test, y_test)
print("BẢNG XẾP HẠNG TẦM QUAN TRỌNG ĐẶC TRƯNG:")
display(imp_df)

render_feature_importance_figure(imp_df, FEAT_FIG_PATH)
print(f"Đã lưu biểu đồ Feature Importance: {FEAT_FIG_PATH.resolve()}")
Image(filename=str(FEAT_FIG_PATH))
""")

# ---------------------------------------------------------------------------
# CELL 10: Leakage Audit Report
# ---------------------------------------------------------------------------
add_md(r"""## 8. Biên bản Kiểm toán 4 Dạng Rò rỉ Dữ liệu & Lý do Loại trừ SMOTE
""")

add_code(r"""audit_md = generate_leakage_audit_markdown(metadata, metrics_table)
AUDIT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
AUDIT_REPORT_PATH.write_text(audit_md, encoding="utf-8")
print(f"Đã xuất biên bản kiểm toán rò rỉ dữ liệu: {AUDIT_REPORT_PATH.resolve()}")

from IPython.display import Markdown
Markdown(audit_md)
""")

# ---------------------------------------------------------------------------
# CELL 11: Scientific Results Report & Findings Synthesis
# ---------------------------------------------------------------------------
add_md(r"""## 9. Báo Cáo Kết Quả Toàn Diện & Tổng Hợp Phát Hiện Khoa Học

Xuất các báo cáo kết quả nghiệm thu:
1. `reports/classification_results.md`: Tổng hợp bảng hiệu năng, phân tích ngưỡng, bẫy Accuracy, hai quần thể nhãn.
2. `docs/classification_findings.md`: Tài liệu phát hiện khoa học, động lực khí tượng, tương tác nhiệt-ẩm, và đánh đổi Precision-Recall.
""")

add_code(r"""results_obj = ClassificationResults(
    split_timestamp=DEFAULT_SPLIT_TIMESTAMP,
    n_train_total=metadata["n_train_total"],
    n_train_valid=metadata["n_train_valid"],
    n_test_total=metadata["n_test_total"],
    n_test_valid=metadata["n_test_valid"],
    train_prevalence_valid=metadata["train_prevalence_valid"],
    test_prevalence_valid=metadata["test_prevalence_valid"],
    train_prevalence_all=metadata["train_prevalence_all"],
    test_prevalence_all=metadata["test_prevalence_all"],
    features=list(X_train.columns),
    best_threshold_logreg=tau_logreg,
    best_threshold_rf=tau_rf,
    metrics_table=metrics_table,
    model_metrics={"dummy": m_dummy, "logreg": m_logreg, "rf": m_rf},
    feature_importances=imp_df,
    leakage_audit_markdown=audit_md,
)

write_classification_report(results_obj, RESULTS_REPORT_PATH)
write_classification_findings(results_obj, FINDINGS_DOC_PATH)

print(f"Đã xuất báo cáo kết quả: {RESULTS_REPORT_PATH.resolve()}")
print(f"Đã xuất tài liệu phát hiện khoa học: {FINDINGS_DOC_PATH.resolve()}")
""")


def build_notebook_dict() -> dict:
    return {
        "cells": cells,
        "metadata": {
            "language_info": {"name": "python", "version": "3.10"},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def generate_and_execute(output_path: Path = NOTEBOOK_PATH, execute: bool = True):
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
    nbformat.write(nbformat.from_dict(notebook_json), output_path)

    code_count = len([c for c in cells if c["cell_type"] == "code"])
    md_count = len([c for c in cells if c["cell_type"] == "markdown"])
    print(f"Đã tạo {output_path} với {len(cells)} cells ({code_count} code, {md_count} markdown).")

    if execute:
        parquet_path = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
        if not parquet_path.exists():
            print(f"Không tìm thấy {parquet_path}. Bỏ qua execute.")
            return notebook_json

        print("Đang thực thi notebook 07 từ đầu đến cuối (Restart Kernel & Run All)...")
        from nbclient import NotebookClient

        nb_obj = nbformat.read(output_path, as_version=4)
        client = NotebookClient(nb_obj, timeout=1200, kernel_name="python3")
        client.execute()
        nbformat.write(nb_obj, output_path)
        print("Notebook 07 đã thực thi 100% không lỗi và đã lưu outputs.")

    return notebook_json


if __name__ == "__main__":
    generate_and_execute()
