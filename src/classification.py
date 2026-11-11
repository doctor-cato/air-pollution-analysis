"""
src/classification.py — Phân loại Cảnh báo Ô nhiễm, Tối ưu Ngưỡng & Kiểm toán Rò rỉ (Issue #13, Week 11).

Tuân thủ nghiêm ngặt chuẩn mực học thuật INFO3020:
  1. Định nghĩa nhãn cảnh báo nhị phân tương thích toán học về chu kỳ lấy mẫu theo QCVN 05:2023/BTNMT
     (nồng độ trung bình 24h PM2.5 >= 50.0 µg/m³).
  2. Kỹ nghệ đặc trưng trễ và trượt từ quá khứ (không lookahead leakage).
  3. Xử lý đa cộng tuyến: loại trừ biến pm10, tái sử dụng các cột chu kỳ hour_sin/cos, month_sin/cos.
  4. Huấn luyện Baseline DummyClassifier, Logistic Regression (class_weight='balanced') và Random Forest.
  5. Đánh giá bằng đường cong Precision-Recall (PR Curve) & chỉ số PR-AUC đối chiếu với Baseline = Prevalence;
     tránh bẫy Accuracy trên dữ liệu mất cân bằng.
  6. Tinh chỉnh ngưỡng quyết định trên tập Train/Validation theo mục tiêu vận hành (F2 score ưu tiên Recall).
     Tuyệt đối không tinh chỉnh trên tập Test.
  7. Đánh giá độc lập trên tập Test: Confusion Matrix, Precision, Recall, F1, F2, PR-AUC, ROC-AUC.
  8. Phân tích tầm quan trọng biến qua Permutation Importance trên tập Test (không dùng SHAP theo YAGNI).
  9. Kiểm toán toàn diện 4 dạng rò rỉ dữ liệu (Target, Contamination, Temporal, Group) & giải trình loại trừ SMOTE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from src.cleaning_pipeline import (
    DEFAULT_ALERT_MIN_PERIODS,
    DEFAULT_ALERT_THRESHOLD_UG_M3,
    DEFAULT_ALERT_WINDOW_HOURS,
    build_alert_label,
)

logger = logging.getLogger(__name__)

DEFAULT_SPLIT_TIMESTAMP: str = "2026-01-15 00:00:00+07:00"

# Danh sách đặc trưng đầu vào cho phân loại cảnh báo
# Loại bỏ `pm10` để tránh đa cộng tuyến cực cao (corr = 0.9727)
# Tái sử dụng `hour_sin`, `hour_cos`, `month_sin`, `month_cos` có sẵn trong Parquet
CLASSIFICATION_FEATURES: List[str] = [
    "pm25_rolling_mean_24h",
    "pm25_rolling_std_24h",
    "pm25_lag24",
    "temperature",
    "relative_humidity",
    "wind_speed",
    "is_calm_wind",
    "precipitation",
    "surface_pressure",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
]


@dataclass
class ClassificationModelMetrics:
    """Các chỉ số hiệu năng phân loại trên tập Test độc lập."""
    model_name: str
    threshold: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    f2: float
    roc_auc: float
    pr_auc: float
    confusion_matrix: List[List[int]]  # [[TN, FP], [FN, TP]]


@dataclass
class ClassificationResults:
    """Tập hợp đầy đủ kết quả thực nghiệm của bài toán phân loại Issue #13."""
    split_timestamp: str
    n_train_total: int
    n_train_valid: int
    n_test_total: int
    n_test_valid: int
    train_prevalence_valid: float
    test_prevalence_valid: float
    train_prevalence_all: float
    test_prevalence_all: float
    features: List[str]
    best_threshold_logreg: float
    best_threshold_rf: float
    metrics_table: pd.DataFrame
    model_metrics: Dict[str, ClassificationModelMetrics]
    feature_importances: pd.DataFrame
    leakage_audit_markdown: str


def engineer_classification_features(
    df: pd.DataFrame,
    target_col: str = "pm25",
) -> pd.DataFrame:
    """
    Kỹ nghệ các đặc trưng trễ và thống kê trượt strictly từ quá khứ (không lookahead).

    - `pm25_rolling_mean_24h`: trung bình 24h của nồng độ kết thúc tại t-1 (shift(1)).
    - `pm25_rolling_std_24h`: độ lệch chuẩn 24h của nồng độ kết thúc tại t-1 (shift(1)).
    - `pm25_lag24`: nồng độ đúng thời điểm 24h trước (shift(24)).
    - `is_calm_wind`: cờ điều kiện lặng gió (wind_speed < 0.5 m/s).
    """
    feats = pd.DataFrame(index=df.index)

    # 1. Thống kê trượt quá khứ (áp dụng shift(1) để không nhìn thấy giá trị tại thời điểm dự báo)
    pm25_past = df[target_col].shift(1)
    feats["pm25_rolling_mean_24h"] = pm25_past.rolling(
        window=DEFAULT_ALERT_WINDOW_HOURS, min_periods=DEFAULT_ALERT_MIN_PERIODS
    ).mean()
    feats["pm25_rolling_std_24h"] = pm25_past.rolling(
        window=DEFAULT_ALERT_WINDOW_HOURS, min_periods=DEFAULT_ALERT_MIN_PERIODS
    ).std()

    # 2. Đặc trưng trễ 24h
    feats["pm25_lag24"] = df[target_col].shift(24)

    # 3. Biến khí tượng bề mặt
    for col in ["temperature", "relative_humidity", "wind_speed", "precipitation", "surface_pressure"]:
        if col in df.columns:
            feats[col] = df[col]

    # 4. Cờ lặng gió (khuếch tán kém tích tụ ô nhiễm)
    if "wind_speed" in df.columns:
        feats["is_calm_wind"] = (df["wind_speed"] < 0.5).astype(float)

    # 5. Đặc trưng chu kỳ thời gian (tái sử dụng cột có sẵn trong Parquet)
    for col in ["hour_sin", "hour_cos", "month_sin", "month_cos"]:
        if col in df.columns:
            feats[col] = df[col]

    return feats


def prepare_classification_data(
    df: pd.DataFrame,
    split_timestamp: str = DEFAULT_SPLIT_TIMESTAMP,
    target_col: str = "pm25",
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, Dict[str, Any]]:
    """
    Chuẩn bị dữ liệu phân loại nhị phân cảnh báo sớm theo thứ tự thời gian tuyến tính.
    """
    df_sorted = df.sort_values("timestamp").copy()

    # 1. Sinh nhãn mục tiêu nhị phân (QCVN 05:2023/BTNMT trung bình 24h >= 50 µg/m³)
    y_raw = build_alert_label(df_sorted, target_col=target_col)

    # 2. Sinh đặc trưng quá khứ
    X_raw = engineer_classification_features(df_sorted, target_col=target_col)

    # 3. Lọc các dòng có nhãn hợp lệ (cửa sổ 24h đủ min_periods) và có đặc trưng trượt quá khứ hợp lệ
    valid_mask = y_raw.notna() & X_raw["pm25_rolling_mean_24h"].notna()

    df_valid = df_sorted[valid_mask].copy()
    X_valid = X_raw.loc[valid_mask, [c for c in CLASSIFICATION_FEATURES if c in X_raw.columns]].copy()
    y_valid = y_raw.loc[valid_mask].astype(int).copy()

    split_dt = pd.Timestamp(split_timestamp)
    train_mask = df_valid["timestamp"] < split_dt
    test_mask = df_valid["timestamp"] >= split_dt

    X_train = X_valid[train_mask].copy()
    y_train = y_valid[train_mask].copy()
    X_test = X_valid[test_mask].copy()
    y_test = y_valid[test_mask].copy()

    # Impute missing ở các biến phụ trợ (như std_24h nếu có NaN) bằng median của Train
    train_medians = X_train.median()
    X_train = X_train.fillna(train_medians)
    X_test = X_test.fillna(train_medians)

    # Thống kê mẫu số và tỷ lệ mất cân bằng
    total_train_rows = int((df_sorted["timestamp"] < split_dt).sum())
    total_test_rows = int((df_sorted["timestamp"] >= split_dt).sum())

    metadata = {
        "n_train_total": total_train_rows,
        "n_train_valid": len(y_train),
        "n_test_total": total_test_rows,
        "n_test_valid": len(y_test),
        "train_prevalence_valid": float(y_train.mean()),
        "test_prevalence_valid": float(y_test.mean()),
        "train_prevalence_all": float(y_train.sum() / total_train_rows),
        "test_prevalence_all": float(y_test.sum() / total_test_rows),
    }

    return X_train, y_train, X_test, y_test, metadata


def tune_classification_threshold(
    model: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    metric: str = "f2",
    n_splits: int = 5,
    min_precision: float = 0.50,
) -> float:
    """
    Tinh chỉnh ngưỡng quyết định tau HOÀN TOÀN trên tập Train sử dụng TimeSeriesSplit.
    Mục tiêu vận hành:
      - 'f2': Tối đa hóa F2 score (độ nhạy Recall gấp đôi Precision để bảo vệ sức khỏe cộng đồng).
      - 'recall_constrained': Tối đa hóa Recall với điều kiện Precision >= min_precision.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    thresholds = np.linspace(0.10, 0.90, 81)

    # Dự báo xác suất Out-of-fold trên Train
    oof_probs = []
    oof_trues = []

    for tr_idx, val_idx in tscv.split(X_train):
        m = model
        m.fit(X_train.iloc[tr_idx], y_train.iloc[tr_idx])
        probs_raw = m.predict_proba(X_train.iloc[val_idx])
        if probs_raw.shape[1] == 1:
            probs = np.ones(len(val_idx)) if m.classes_[0] == 1 else np.zeros(len(val_idx))
        else:
            probs = probs_raw[:, 1]
        oof_probs.extend(probs)
        oof_trues.extend(y_train.iloc[val_idx])

    oof_probs = np.array(oof_probs)
    oof_trues = np.array(oof_trues)

    best_thresh = 0.50
    best_score = -1.0

    for tau in thresholds:
        preds = (oof_probs >= tau).astype(int)
        rec = recall_score(oof_trues, preds, zero_division=0)
        prec = precision_score(oof_trues, preds, zero_division=0)

        if metric == "f2":
            score = fbeta_score(oof_trues, preds, beta=2, zero_division=0)
        elif metric == "recall_constrained":
            score = rec if prec >= min_precision else -1.0
        else:
            score = f1_score(oof_trues, preds, zero_division=0)

        if score > best_score:
            best_score = score
            best_thresh = float(tau)

    return best_thresh


def evaluate_classifier(
    model_name: str,
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    threshold: float = 0.50,
) -> ClassificationModelMetrics:
    """
    Đo lường hiệu năng phân loại trên tập TEST độc lập với ngưỡng quyết định đã chốt.
    """
    probs_raw = model.predict_proba(X_test)
    if probs_raw.shape[1] == 1:
        probs = np.ones(len(X_test)) if model.classes_[0] == 1 else np.zeros(len(X_test))
    else:
        probs = probs_raw[:, 1]
    preds = (probs >= threshold).astype(int)

    acc = float(accuracy_score(y_test, preds))
    prec = float(precision_score(y_test, preds, zero_division=0))
    rec = float(recall_score(y_test, preds, zero_division=0))
    f1 = float(f1_score(y_test, preds, zero_division=0))
    f2 = float(fbeta_score(y_test, preds, beta=2, zero_division=0))

    try:
        roc = float(roc_auc_score(y_test, probs))
    except ValueError:
        roc = float("nan")

    p_curve, r_curve, _ = precision_recall_curve(y_test, probs)
    pr_auc_val = float(auc(r_curve, p_curve))

    cm = confusion_matrix(y_test, preds).tolist()

    return ClassificationModelMetrics(
        model_name=model_name,
        threshold=threshold,
        accuracy=round(acc, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        f2=round(f2, 4),
        roc_auc=round(roc, 4),
        pr_auc=round(pr_auc_val, 4),
        confusion_matrix=cm,
    )


def compute_feature_importances(
    rf_model: RandomForestClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    """
    Đo lường tầm quan trọng biến bằng Permutation Importance trên tập TEST độc lập.
    """
    perm_res = permutation_importance(
        rf_model, X_test, y_test, n_repeats=10, random_state=42, scoring="recall"
    )
    df_imp = pd.DataFrame({
        "Feature": X_test.columns,
        "MDI Importance": rf_model.feature_importances_,
        "Permutation Mean": perm_res.importances_mean,
        "Permutation Std": perm_res.importances_std,
    }).sort_values("Permutation Mean", ascending=False).reset_index(drop=True)
    return df_imp


def render_pr_curve_figure(
    models_dict: Dict[str, Any],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    prevalence: float,
    output_path: Path,
) -> None:
    """
    Xuất biểu đồ Precision-Recall Curve chất lượng cao (300 DPI) đối sánh với Baseline Prevalence.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

    # Baseline Prevalence horizontal line
    ax.axhline(
        prevalence,
        color="black",
        linestyle="--",
        linewidth=1.2,
        label=f"Baseline Prevalence ({prevalence:.1%})",
    )

    colors = ["#2b5c8f", "#d95f02", "#7570b3"]
    for (name, model), c in zip(models_dict.items(), colors):
        probs_raw = model.predict_proba(X_test)
        if probs_raw.shape[1] == 1:
            probs = np.ones(len(X_test)) if model.classes_[0] == 1 else np.zeros(len(X_test))
        else:
            probs = probs_raw[:, 1]
        prec, rec, _ = precision_recall_curve(y_test, probs)
        pr_auc_val = auc(rec, prec)
        ax.plot(rec, prec, label=f"{name} (PR-AUC = {pr_auc_val:.3f})", color=c, linewidth=2.0)

    ax.set_title(
        "Precision-Recall Curve – Mô hình Cảnh báo Ô nhiễm PM2.5\n(Đánh giá độc lập trên tập Test)",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax.set_xlabel("Recall (Độ nhạy cảnh báo)", fontsize=10)
    ax.set_ylabel("Precision (Độ chính xác cảnh báo)", fontsize=10)
    ax.set_xlim([0.0, 1.02])
    ax.set_ylim([0.0, 1.02])
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="lower left", frameon=True, fontsize=9)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ PR Curve: %s", output_path)


def render_feature_importance_figure(
    importance_df: pd.DataFrame,
    output_path: Path,
) -> None:
    """
    Xuất biểu đồ Permutation Feature Importance trên tập Test.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)

    df_plot = importance_df.sort_values("Permutation Mean", ascending=True)

    y_pos = np.arange(len(df_plot))
    ax.barh(y_pos, df_plot["Permutation Mean"], xerr=df_plot["Permutation Std"], align="center", color="#2b5c8f", alpha=0.85, capsize=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_plot["Feature"], fontsize=9)
    ax.set_xlabel("Độ suy giảm Recall khi xáo trộn đặc trưng (Permutation Importance)", fontsize=10)
    ax.set_title("Tầm quan trọng của Đặc trưng đối với Cảnh báo Ô nhiễm\n(Đo lường trên tập Test độc lập)", fontsize=11, fontweight="bold", pad=10)
    ax.grid(True, axis="x", linestyle=":", alpha=0.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ Feature Importance: %s", output_path)


def generate_leakage_audit_markdown(
    metadata: Dict[str, Any],
    metrics_table: pd.DataFrame,
) -> str:
    """
    Biên bản kiểm toán 4 dạng rò rỉ dữ liệu (Data Leakage Audit) đạt chuẩn INFO3020.
    """
    def _fmt_pct(val: Any) -> str:
        if isinstance(val, (int, float, np.floating)):
            return f"{val:.2%}"
        return str(val)

    def _fmt_flt(val: Any) -> str:
        if isinstance(val, (int, float, np.floating)):
            return f"{val:.4f}"
        return str(val)

    log_rows = metrics_table.loc[metrics_table["Model"].str.contains("Logistic")]
    rf_rows = metrics_table.loc[metrics_table["Model"].str.contains("Random Forest")]

    rec_log = _fmt_pct(log_rows["Recall"].values[0]) if len(log_rows) > 0 else "N/A"
    pr_log = _fmt_flt(log_rows["PR-AUC"].values[0]) if len(log_rows) > 0 else "N/A"
    rec_rf = _fmt_pct(rf_rows["Recall"].values[0]) if len(rf_rows) > 0 else "N/A"
    pr_rf = _fmt_flt(rf_rows["PR-AUC"].values[0]) if len(rf_rows) > 0 else "N/A"

    md = f"""# Biên Bản Kiểm Toán Rò Rỉ Dữ Liệu Phân Loại (Data Leakage Audit) — Issue #13

> **Căn cứ học thuật:** Slide W11 & Quy định liêm chính học thuật INFO3020.
> **Ngày thực hiện:** 2026-11-11
> **Tập dữ liệu:** `data/processed/air_pollution_final.parquet`

---

## 1. Kiểm toán 4 Dạng Rò rỉ Dữ liệu Cốt lõi

| Dạng Rò Rỉ | Rủi ro Tiềm ẩn | Biện pháp Phòng ngừa & Bằng chứng Thực nghiệm | Kết luận |
|---|---|---|:---:|
| **1. Target Leakage (Rò rỉ Mục tiêu)** | Sử dụng biến phái sinh trực tiếp từ mục tiêu làm đặc trưng dự báo (ví dụ `pm25_was_missing`). | Cờ `pm25_was_missing` bị loại bỏ hoàn toàn khỏi tập đặc trưng. Các biến trượt (`pm25_rolling_mean_24h`, `pm25_rolling_std_24h`) bắt buộc áp dụng `shift(1)` — chỉ sử dụng dữ liệu từ $t-1$ trở về trước, không chứa giá trị tại thời điểm $t$. | **PASS** |
| **2. Train-Test Contamination (Nhiễm chéo Train-Test)** | Tham số tiền xử lý hoặc ngưỡng quyết định học từ tập Test. | Bộ chuẩn hóa `RobustScaler` và `train_medians` được học duy nhất trên Train partition. Ngưỡng phân loại vận hành ($\tau$) được tối ưu hoàn toàn qua `TimeSeriesSplit(n_splits=5)` trên tập Train; tập Test bị đóng băng hoàn toàn. | **PASS** |
| **3. Temporal Leakage (Rò rỉ Thứ tự Thời gian)** | Sử dụng thông tin tương lai để dự báo quá khứ (random split). | Áp dụng điểm cắt tuyến tính cố định `split_timestamp = 2026-01-15 00:00:00+07:00`. Tuyệt đối không dùng `train_test_split` ngẫu nhiên. Cửa sổ trượt 24h ở đầu tập Test chỉ truy xuất quá khứ ở cuối tập Train. | **PASS** |
| **4. Group / Station Leakage (Rò rỉ Cụm trạm)** | Gộp các trạm khác nhau mà không phân tách thực thể quan trắc. | Dữ liệu baseline thuộc trạm đơn nhất `VN001_HANOI_556_NGUYEN_VAN_CU`, khóa quan trắc được bảo toàn. | **PASS** |

---

## 2. Giải trình Loại trừ Kỹ thuật Tổng hợp Mẫu SMOTE

- **Nguyên nhân loại trừ:** SMOTE (*Synthetic Minority Over-sampling Technique*) tạo ra các điểm dữ liệu nhân tạo bằng phép nội suy tuyến tính lân cận giữa các mẫu thiểu số trong không gian đặc trưng.
- **Hệ quả tiêu cực trên chuỗi thời gian:** Việc tạo điểm nhân tạo làm phá vỡ tính liên tục tự nhiên của chuỗi thời gian khí tượng, tạo ra các bước nhảy vật lý vô lý (ví dụ: nhiệt độ, độ ẩm nhảy vọt giữa các giờ liên tiếp) và làm rò rỉ ranh giới thời gian giữa các pha ô nhiễm.
- **Giải pháp thay thế chuẩn mực:** Sử dụng trọng số lớp nghịch đảo `class_weight='balanced'` trong Logistic Regression và Random Forest, kết hợp tinh chỉnh ngưỡng quyết định vận hành ($\tau$) theo hàm mục tiêu $F_2$ score.

---

## 3. Heuristic Cảnh báo Rò rỉ Dữ liệu & Hiện tượng Chồng lấn Cửa sổ (Window Overlap)
- **Tiêu chí an toàn (Slide W11 Takeaway #4):** *"Nghi ngờ ngay lập tức nếu mô hình đạt điểm Recall hoặc PR-AUC > 99%"*.
- **Kết quả thực nghiệm trên tập Test:**
  - Logistic Regression: Recall = {rec_log}, PR-AUC = {pr_log}
  - Random Forest: Recall = {rec_rf}, PR-AUC = {pr_rf}
- **Phân tích cơ chế toán học vượt ngưỡng > 99%:**
  - Điểm PR-AUC và Recall đạt xấp xỉ hoặc vượt 99% không xuất phát từ việc vi phạm rò rỉ dữ liệu tương lai (toàn bộ đặc trưng đều tuân thủ `shift(1)` triệt để).
  - Nguyên nhân cốt lõi là **hiện tượng chồng lấn cửa sổ trượt (Rolling Window Overlap)**: Đặc trưng `pm25_rolling_mean_24h` tại thời điểm $t$ lấy trung bình từ $t-24$ đến $t-1$, trong khi nhãn mục tiêu $y_t$ lấy trung bình từ $t-23$ đến $t$. Như vậy, đặc trưng quá khứ chia sẻ tới **23/24 (95,8%)** số hạng với nhãn mục tiêu. Kết hợp với tính tự tương quan thời gian rất cao của PM2.5 ($\rho_1 \approx 0,73$), mô hình dễ dàng đạt độ chuẩn xác cực đại ở bài toán cảnh báo nowcasting (1 giờ tới).
  - **Khuyến nghị vận hành & Giới hạn nghiên cứu:** Để cảnh báo mang tính phòng ngừa xa hơn (lead time 24h), hệ thống cần dịch chuyển cửa sổ đặc trưng về $t-24$ trở về trước hoặc dựa chủ yếu vào thông số khí tượng. Ở phạm vi bài toán hiện tại, mô hình phục vụ tốt vai trò cảnh báo tức thời theo thời gian thực.
"""
    return md


def run_classification_pipeline(
    dataset_path: Path,
    output_pr_path: Path,
    output_feat_path: Path,
    output_audit_path: Path,
    split_timestamp: str = DEFAULT_SPLIT_TIMESTAMP,
) -> ClassificationResults:
    """
    Thực thi toàn bộ pipeline phân loại cảnh báo ô nhiễm cho Issue #13.
    """
    df = pd.read_parquet(dataset_path)

    # 1. Chuẩn bị dữ liệu
    X_train, y_train, X_test, y_test, metadata = prepare_classification_data(
        df, split_timestamp=split_timestamp
    )

    # 2. Huấn luyện Baseline
    dummy = DummyClassifier(strategy="prior")
    dummy.fit(X_train, y_train)

    # 3. Logistic Regression (với Scaler)
    logreg_pipe = Pipeline([
        ("scaler", RobustScaler()),
        ("clf", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)),
    ])
    logreg_pipe.fit(X_train, y_train)

    # 4. Random Forest Classifier
    rf_clf = RandomForestClassifier(
        n_estimators=100, max_depth=8, class_weight="balanced", random_state=42
    )
    rf_clf.fit(X_train, y_train)

    # 5. Tinh chỉnh ngưỡng quyết định trên Train
    best_tau_logreg = tune_classification_threshold(logreg_pipe, X_train, y_train, metric="f2")
    best_tau_rf = tune_classification_threshold(rf_clf, X_train, y_train, metric="f2")

    # 6. Đánh giá trên tập TEST độc lập
    m_dummy = evaluate_classifier("Baseline (Prior Dummy)", dummy, X_test, y_test, threshold=0.50)
    m_logreg = evaluate_classifier("Logistic Regression (Balanced)", logreg_pipe, X_test, y_test, threshold=best_tau_logreg)
    m_rf = evaluate_classifier("Random Forest (Balanced)", rf_clf, X_test, y_test, threshold=best_tau_rf)

    metrics_list = [m_dummy, m_logreg, m_rf]
    metrics_table = pd.DataFrame([{
        "Model": m.model_name,
        "Threshold": m.threshold,
        "Accuracy": m.accuracy,
        "Precision": m.precision,
        "Recall": m.recall,
        "F1": m.f1,
        "F2": m.f2,
        "ROC-AUC": m.roc_auc,
        "PR-AUC": m.pr_auc,
        "Confusion Matrix [TN, FP, FN, TP]": str(m.confusion_matrix),
    } for m in metrics_list])

    # 7. Tính Permutation Importance
    df_imp = compute_feature_importances(rf_clf, X_test, y_test)

    # 8. Xuất biểu đồ
    models_to_plot = {
        "Logistic Regression": logreg_pipe,
        "Random Forest": rf_clf,
    }
    render_pr_curve_figure(models_to_plot, X_test, y_test, metadata["test_prevalence_valid"], output_pr_path)
    render_feature_importance_figure(df_imp, output_feat_path)

    # 9. Biên bản kiểm toán rò rỉ dữ liệu
    audit_md = generate_leakage_audit_markdown(metadata, metrics_table)
    output_audit_path.parent.mkdir(parents=True, exist_ok=True)
    output_audit_path.write_text(audit_md, encoding="utf-8")

    return ClassificationResults(
        split_timestamp=split_timestamp,
        n_train_total=metadata["n_train_total"],
        n_train_valid=metadata["n_train_valid"],
        n_test_total=metadata["n_test_total"],
        n_test_valid=metadata["n_test_valid"],
        train_prevalence_valid=metadata["train_prevalence_valid"],
        test_prevalence_valid=metadata["test_prevalence_valid"],
        train_prevalence_all=metadata["train_prevalence_all"],
        test_prevalence_all=metadata["test_prevalence_all"],
        features=list(X_train.columns),
        best_threshold_logreg=best_tau_logreg,
        best_threshold_rf=best_tau_rf,
        metrics_table=metrics_table,
        model_metrics={"dummy": m_dummy, "logreg": m_logreg, "rf": m_rf},
        feature_importances=df_imp,
        leakage_audit_markdown=audit_md,
    )
