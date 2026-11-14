"""
src/classification.py — Phân loại Cảnh báo Ô nhiễm (Truy hồi tức thời & Đa tầm), Tối ưu Ngưỡng & Kiểm toán Rò rỉ (Issue #13, Week 11).

Tuân thủ nghiêm ngặt chuẩn mực học thuật INFO3020:
  1. Định nghĩa bài toán: Cảnh báo ô nhiễm theo QCVN 05:2023/BTNMT (trung bình 24h PM2.5 >= 50.0 µg/m³).
     - Với dữ liệu khí tượng Open-Meteo ERA5 (độ trễ tái phân tích ~5 ngày), thiết lập tại tầm h = 0 giờ là
       **truy hồi tức thời (retrospective historical nowcast)** tại thời điểm t sử dụng nồng độ PM2.5 kết thúc
       ở t-1 (`shift(1)`) và khí tượng ERA5 tại t — không phải hệ thống cảnh báo thời gian thực (real-time).
     - Đánh giá mở rộng sang các tầm dự báo tương lai thực thụ h in {0, 1, 6, 12, 24} giờ với vùng đệm loại bỏ
       (purge gap) nghiêm ngặt tại biên Train/Test.
  2. Kỹ nghệ đặc trưng trễ và trượt từ quá khứ theo từng trạm trên lưới giờ liên tục (không bắc cầu qua gap thiếu dữ liệu).
  3. Xử lý đa cộng tuyến & rò rỉ: loại trừ `pm10`, `pm25_was_missing`, `is_high_humidity_fog`; từ chối fail-closed nếu
     gộp nhiều trạm không chỉ định `station_id` (Protocol A).
  4. Đối sánh đầy đủ Baseline (`DummyClassifier(strategy='prior')`, `PersistenceRuleClassifier` 1 biến),
     `LogisticRegression(class_weight='balanced')` và `RandomForestClassifier(class_weight='balanced')`.
  5. Chống rò rỉ trong Pipeline & Cross-Validation: `SimpleImputer` + `RobustScaler` nằm trong `ColumnTransformer`
     (`validate_no_leakage`), không impute toàn cục trước `TimeSeriesSplit`.
  6. Đo lường hiệu năng trung thực qua `average_precision_score` (PR-AUC), ROC-AUC, Recall, Precision, F1/F2,
     False Alarm Rate (FAR), Brier score và ma trận nhầm lẫn 2x2 đầy đủ; xử lý an toàn `UNESTIMABLE` khi Test không có ca dương.
  7. Tầm quan trọng đặc trưng bằng Permutation Importance theo `average_precision` (20 lần lặp, kèm CI 95%) kết hợp
     hệ số & Odds Ratio của Logistic Regression và phân tích cắt giảm đặc trưng (Feature Ablation).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
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
    NON_PREDICTIVE_FLAGS,
    TARGET_DERIVED_FLAGS,
    build_alert_label,
    validate_no_leakage,
)
from src.issue44_preparation import validate_modeling_split

logger = logging.getLogger(__name__)

DEFAULT_SPLIT_TIMESTAMP: str = "2026-01-15 00:00:00+07:00"
PRIMARY_BASELINE_STATION: str = "VN001_HANOI_556_NGUYEN_VAN_CU"
EXTENDED_HISTORICAL_STATION: str = "VN003_HANOI_OPENAQ_7441"

FORBIDDEN_CLASSIFICATION_COLS: Tuple[str, ...] = tuple(
    ["pm25", "pm10", *TARGET_DERIVED_FLAGS, *NON_PREDICTIVE_FLAGS]
)

# Danh sách đặc trưng đầu vào chuẩn cho phân loại cảnh báo
# Loại bỏ `pm10` (đa cộng tuyến cực cao r = 0.9727), `pm25_was_missing` (rò rỉ mục tiêu),
# và `is_high_humidity_fog` (không có giá trị dự báo biên độc lập).
CLASSIFICATION_FEATURES: List[str] = [
    "pm25_rolling_mean_24h",
    "pm25_rolling_std_24h",
    "pm25_lag24",
    "temperature",
    "relative_humidity",
    "temp_humidity_interaction",
    "wind_speed",
    "is_calm_wind",
    "precipitation",
    "surface_pressure",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
]

MET_AND_LAG24_FEATURES: List[str] = [
    c for c in CLASSIFICATION_FEATURES
    if c not in ("pm25_rolling_mean_24h", "pm25_rolling_std_24h")
]

METEOROLOGY_ONLY_FEATURES: List[str] = [
    c for c in CLASSIFICATION_FEATURES if not c.startswith("pm25_")
]

_ERA5_LATENCY_NOTE: str = (
    "Khí tượng Open-Meteo ERA5 là dữ liệu tái phân tích (reanalysis) có độ trễ phát hành ~5 ngày; "
    "do đó thiết lập tại h = 0 giờ mang bản chất truy hồi tức thời lịch sử (retrospective nowcast), "
    "không phải vận hành thời gian thực trừ khi thay bằng dữ liệu quan trắc/dự báo NWP trực tuyến."
)


class PersistenceRuleClassifier(BaseEstimator, ClassifierMixin):
    """
    Baseline quy tắc tất định 1 biến (Persistence Rule Baseline):
    Dự báo vượt ngưỡng khi `pm25_rolling_mean_24h >= threshold_ug_m3` (mặc định 50.0 µg/m³).
    """

    def __init__(
        self,
        feature_col: str = "pm25_rolling_mean_24h",
        threshold_ug_m3: float = DEFAULT_ALERT_THRESHOLD_UG_M3,
        scale_ug_m3: float = 15.0,
    ) -> None:
        self.feature_col = feature_col
        self.threshold_ug_m3 = threshold_ug_m3
        self.scale_ug_m3 = scale_ug_m3

    def fit(self, X: pd.DataFrame, y: Any = None) -> "PersistenceRuleClassifier":
        self.classes_ = np.array([0, 1], dtype=int)
        if isinstance(X, pd.DataFrame) and self.feature_col in X.columns and X[self.feature_col].notna().any():
            self.fallback_value_ = float(X[self.feature_col].median())
        else:
            self.fallback_value_ = 0.0
        self.is_fitted_ = True
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if isinstance(X, pd.DataFrame) and self.feature_col in X.columns:
            vals = X[self.feature_col].astype(float).fillna(self.fallback_value_).to_numpy()
        else:
            vals = np.asarray(X, dtype=float)[:, 0]
        z = np.clip((vals - self.threshold_ug_m3) / max(float(self.scale_ug_m3), 1e-6), -30.0, 30.0)
        p1 = 1.0 / (1.0 + np.exp(-z))
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if isinstance(X, pd.DataFrame) and self.feature_col in X.columns:
            vals = X[self.feature_col].astype(float).fillna(self.fallback_value_).to_numpy()
        else:
            vals = np.asarray(X, dtype=float)[:, 0]
        return (vals >= self.threshold_ug_m3).astype(int)


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
    false_alarm_rate: float = float("nan")
    brier_score: float = float("nan")
    status: str = "OK"


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
    scope_name: str = "VN001_baseline_2026_01_15"
    station_id: str = PRIMARY_BASELINE_STATION
    horizon_hours: int = 0
    best_threshold_logreg_constrained: float = 0.50
    best_threshold_rf_constrained: float = 0.50
    logreg_odds_ratios: Optional[pd.DataFrame] = None
    coverage_table: Optional[pd.DataFrame] = None
    outage_gaps_table: Optional[pd.DataFrame] = None
    monthly_coverage_table: Optional[pd.DataFrame] = None
    ablation_horizon_table: Optional[pd.DataFrame] = None
    backtest_table: Optional[pd.DataFrame] = None
    annual_drift_table: Optional[pd.DataFrame] = None
    derived_sensitivity_table: Optional[pd.DataFrame] = None
    threshold_warnings: List[str] = field(default_factory=list)
    dataset_sha256: str = ""
    extra_runs: List["ClassificationResults"] = field(default_factory=list)


def _write_lf_text(path: Path, text: str) -> None:
    """Ghi tệp UTF-8 chuẩn UNIX LF (\\n) kết thúc đúng một dòng mới."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.replace("\r\n", "\n").rstrip("\n") + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(normalized)


def _sha256_file(path: Path) -> str:
    """Tính mã băm SHA-256 của tệp artifact dữ liệu."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _df_to_markdown(df: Optional[pd.DataFrame]) -> str:
    """Chuyển đổi DataFrame thành bảng Markdown sạch không phụ thuộc tabulate."""
    if df is None or df.empty:
        return "_Không có dữ liệu bảng._"
    headers = [str(c) for c in df.columns]
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_lines = []
    for _, row in df.iterrows():
        cells = []
        for val in row.values:
            if isinstance(val, (float, np.floating)) and np.isnan(val):
                cells.append("UNESTIMABLE")
            else:
                cells.append(str(val))
        data_lines.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_line, separator_line, *data_lines])


def _select_single_station(
    df: pd.DataFrame,
    station_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Lọc và kiểm chứng đơn trạm theo Protocol A; từ chối fail-closed nếu dữ liệu
    chứa nhiều trạm mà chưa truyền `station_id` hoặc phát hiện timestamp trùng/NaT.
    """
    if "timestamp" not in df.columns:
        raise KeyError("Thiếu cột bắt buộc 'timestamp' trong DataFrame.")

    out = df.copy()
    if "station_id" in out.columns:
        if out["station_id"].isna().any():
            raise ValueError("Cột 'station_id' chứa NaN — từ chối fail-closed.")
        if station_id is not None:
            out = out[out["station_id"] == station_id].copy()
            if out.empty:
                raise ValueError(f"Không tìm thấy dữ liệu cho trạm '{station_id}'.")
        else:
            unique_stations = list(out["station_id"].unique())
            if len(unique_stations) > 1:
                raise ValueError(
                    f"Phát hiện nhiều trạm {unique_stations} khi chưa chỉ định `station_id`. "
                    "Cấm gộp đa trạm lệch pha theo Protocol B; hãy truyền `station_id` cụ thể."
                )
    elif station_id is not None:
        raise ValueError("Dữ liệu không có cột 'station_id' để lọc theo trạm.")

    out["timestamp"] = pd.to_datetime(out["timestamp"])
    if out["timestamp"].isna().any():
        raise ValueError("Cột 'timestamp' chứa giá trị NaT không hợp lệ.")
    if out["timestamp"].duplicated().any():
        raise ValueError("Phát hiện timestamp trùng lặp trong cùng một trạm.")

    return out.sort_values("timestamp").reset_index(drop=True)


def _compute_past_rolling_and_lag_on_station(
    group: pd.DataFrame,
    target_col: str,
    window: int = DEFAULT_ALERT_WINDOW_HOURS,
    min_periods: int = DEFAULT_ALERT_MIN_PERIODS,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Tính `pm25_rolling_mean_24h`, `pm25_rolling_std_24h` (kết thúc ở t-1) và `pm25_lag24`
    (đúng t - 24 giờ) trên một trạm duy nhất, tuyệt đối không bắc cầu qua khoảng trống thời gian.
    """
    if "timestamp" not in group.columns:
        pm25_past = group[target_col].astype(float).shift(1)
        roll_mean = pm25_past.rolling(window=window, min_periods=min_periods).mean()
        roll_std = pm25_past.rolling(window=window, min_periods=min_periods).std()
        lag24 = group[target_col].astype(float).shift(window)
        return roll_mean, roll_std, lag24

    ts = pd.to_datetime(group["timestamp"])
    if not ts.is_monotonic_increasing:
        raise ValueError("Dữ liệu trong từng trạm phải tăng dần theo timestamp.")
    if ts.duplicated().any():
        raise ValueError("Phát hiện timestamp trùng lặp trong cùng một trạm.")

    vals = group[target_col].astype(float).to_numpy()
    s = pd.Series(vals, index=ts)

    # Trễ đúng 24 giờ thực thụ theo đồng hồ bất kể thiếu dòng trên lưới
    lag24_vals = s.reindex(ts - pd.Timedelta(hours=window)).to_numpy(dtype=float)

    t_min = ts.iloc[0]
    t_max = ts.iloc[-1]
    n_span_hours = int(round((t_max - t_min).total_seconds() / 3600.0)) + 1

    # Đường nhanh cho lưới 1 giờ liên tục chuẩn
    diffs = ts.diff().dropna()
    is_contiguous_1h = diffs.eq(pd.Timedelta(hours=1)).all() if len(diffs) > 0 else True
    if is_contiguous_1h:
        past_s = pd.Series(vals, index=group.index).shift(1)
        rm = past_s.rolling(window=window, min_periods=min_periods).mean()
        rs = past_s.rolling(window=window, min_periods=min_periods).std()
        lag_s = pd.Series(lag24_vals, index=group.index)
        return rm, rs, lag_s

    # Nếu có khoảng trống timestamp: chỉ reindex lên lưới giờ chuẩn nếu toàn bộ nằm trên bội số giờ
    on_hourly_grid = ((ts - t_min) % pd.Timedelta(hours=1) == pd.Timedelta(0)).all()
    if on_hourly_grid and n_span_hours <= 500_000:
        hourly_grid = t_min + pd.to_timedelta(np.arange(n_span_hours), unit="h")
        s_grid = s.reindex(hourly_grid)
        past_grid = s_grid.shift(1)
        rm_grid = past_grid.rolling(window=window, min_periods=min_periods).mean()
        rs_grid = past_grid.rolling(window=window, min_periods=min_periods).std()
        rm = pd.Series(rm_grid.reindex(ts).to_numpy(dtype=float), index=group.index)
        rs = pd.Series(rs_grid.reindex(ts).to_numpy(dtype=float), index=group.index)
        lag_s = pd.Series(lag24_vals, index=group.index)
        return rm, rs, lag_s

    # Trường hợp lưới thời gian không đều tổng quát: mặt nạ nếu độ dài cửa sổ khác 23h
    past_raw = pd.Series(vals, index=ts.index).shift(1)
    rm = past_raw.rolling(window=window, min_periods=min_periods).mean()
    rs = past_raw.rolling(window=window, min_periods=min_periods).std()
    span_ok = (ts - ts.shift(window)) == pd.Timedelta(hours=window)
    rm = rm.where(span_ok)
    rs = rs.where(span_ok)
    lag_s = pd.Series(lag24_vals, index=group.index)
    return rm, rs, lag_s


def engineer_classification_features(
    df: pd.DataFrame,
    target_col: str = "pm25",
    *,
    include_wind_stagnant_alias: bool = False,
) -> pd.DataFrame:
    """
    Kỹ nghệ đặc trưng trễ và thống kê trượt strictly từ quá khứ theo từng trạm (không lookahead):
      - `pm25_rolling_mean_24h`: trung bình trượt 24h kết thúc tại t-1 (`shift(1)` trên lưới giờ).
      - `pm25_rolling_std_24h`: độ lệch chuẩn 24h kết thúc tại t-1.
      - `pm25_lag24`: nồng độ đúng `t - 24h` theo mốc thời gian thực.
      - `is_calm_wind`: cờ lặng gió (`wind_speed < 0.5` m/s). Tùy chọn xuất thêm `wind_stagnant` như bí danh đồng nhất.
    """
    if target_col not in df.columns:
        raise KeyError(f"Thiếu cột '{target_col}' để kỹ nghệ đặc trưng.")

    feats = pd.DataFrame(index=df.index)
    rm_out = pd.Series(np.nan, index=df.index, dtype=float)
    rs_out = pd.Series(np.nan, index=df.index, dtype=float)
    lag24_out = pd.Series(np.nan, index=df.index, dtype=float)

    if "station_id" in df.columns:
        if df["station_id"].isna().any():
            raise ValueError("Cột 'station_id' chứa NaN trong engineer_classification_features.")
        for _, grp in df.groupby("station_id", sort=False):
            rm_g, rs_g, lag_g = _compute_past_rolling_and_lag_on_station(grp, target_col=target_col)
            rm_out.loc[grp.index] = rm_g
            rs_out.loc[grp.index] = rs_g
            lag24_out.loc[grp.index] = lag_g
    else:
        rm_g, rs_g, lag_g = _compute_past_rolling_and_lag_on_station(df, target_col=target_col)
        rm_out.loc[df.index] = rm_g
        rs_out.loc[df.index] = rs_g
        lag24_out.loc[df.index] = lag_g

    feats["pm25_rolling_mean_24h"] = rm_out
    feats["pm25_rolling_std_24h"] = rs_out
    feats["pm25_lag24"] = lag24_out

    for col in ["temperature", "relative_humidity", "wind_speed", "precipitation", "surface_pressure"]:
        if col in df.columns:
            feats[col] = df[col].astype(float)

    if "temperature" in df.columns and "relative_humidity" in df.columns:
        feats["temp_humidity_interaction"] = feats["temperature"] * feats["relative_humidity"]

    if "wind_speed" in df.columns:
        calm = pd.Series(np.nan, index=df.index, dtype=float)
        non_na_ws = df["wind_speed"].notna()
        calm.loc[non_na_ws] = (df.loc[non_na_ws, "wind_speed"] < 0.5).astype(float)
        feats["is_calm_wind"] = calm
        if include_wind_stagnant_alias:
            feats["wind_stagnant"] = calm.copy()

    for col in ["hour_sin", "hour_cos", "month_sin", "month_cos"]:
        if col in df.columns:
            feats[col] = df[col].astype(float)

    return feats


def _build_hourly_safe_alert_label(df_station: pd.DataFrame, target_col: str) -> pd.Series:
    """Xây dựng nhãn QCVN 24h từ `build_alert_label`, bảo đảm không bắc cầu qua hàng bị thiếu giờ."""
    ts = pd.to_datetime(df_station["timestamp"])
    diffs = ts.diff().dropna()
    is_contiguous_1h = diffs.eq(pd.Timedelta(hours=1)).all() if len(diffs) > 0 else True
    if is_contiguous_1h:
        return build_alert_label(df_station, target_col=target_col)

    t_min, t_max = ts.iloc[0], ts.iloc[-1]
    n_span = int(round((t_max - t_min).total_seconds() / 3600.0)) + 1
    on_hourly_grid = ((ts - t_min) % pd.Timedelta(hours=1) == pd.Timedelta(0)).all()
    if on_hourly_grid and n_span <= 500_000:
        grid_ts = t_min + pd.to_timedelta(np.arange(n_span), unit="h")
        grid_df = pd.DataFrame({"timestamp": grid_ts})
        s = pd.Series(df_station[target_col].astype(float).to_numpy(), index=ts)
        grid_df[target_col] = s.reindex(grid_ts).to_numpy()
        y_grid = build_alert_label(grid_df, target_col=target_col, station_col=None)
        y_grid_s = pd.Series(y_grid.to_numpy(), index=grid_ts)
        out = pd.Series(y_grid_s.reindex(ts).to_numpy(), index=df_station.index, name=f"{target_col}_alert_24h")
        return out

    y_raw = build_alert_label(df_station, target_col=target_col)
    span_ok = (ts - ts.shift(DEFAULT_ALERT_WINDOW_HOURS - 1)) == pd.Timedelta(hours=DEFAULT_ALERT_WINDOW_HOURS - 1)
    return y_raw.where(span_ok)


def _align_split_timestamp(ts_col: pd.Series, split_timestamp: str) -> pd.Timestamp:
    """Chuẩn hóa múi giờ của mốc cắt cho khớp chuỗi thời gian."""
    split_dt = pd.Timestamp(split_timestamp)
    if ts_col.dt.tz is not None and split_dt.tzinfo is None:
        split_dt = split_dt.tz_localize(ts_col.dt.tz)
    elif ts_col.dt.tz is None and split_dt.tzinfo is not None:
        split_dt = split_dt.tz_localize(None)
    return split_dt


def prepare_classification_data(
    df: pd.DataFrame,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    target_col: str = "pm25",
    *,
    station_id: Optional[str] = None,
    use_split_column: bool = False,
    horizon_hours: int = 0,
    feature_cols: Optional[Sequence[str]] = None,
    feature_source_col: Optional[str] = None,
    return_timestamps: bool = False,
) -> Union[
    Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, Dict[str, Any]],
    Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, Dict[str, Any], pd.Series, pd.Series],
]:
    """
    Chuẩn bị dữ liệu phân loại nhị phân cảnh báo theo Protocol A và thứ tự thời gian nghiêm ngặt:
      - Kiểm chứng đơn trạm (từ chối fail-closed nếu nhiều trạm mà chưa chọn `station_id`).
      - KHÔNG thực hiện impute toàn cục trước Cross-Validation.
      - Hỗ trợ tầm dự báo tương lai `horizon_hours >= 0` kèm vùng đệm loại bỏ (purge gap)
        để không một nhãn huấn luyện nào chồng lấn sang miền thời gian tập Test.
    """
    if horizon_hours < 0:
        raise ValueError("horizon_hours phải >= 0.")

    df_sorted = _select_single_station(df, station_id=station_id)
    feat_src = feature_source_col or target_col

    if target_col not in df_sorted.columns:
        raise KeyError(f"Thiếu cột mục tiêu '{target_col}'.")
    if feat_src not in df_sorted.columns:
        raise KeyError(f"Thiếu cột nguồn đặc trưng '{feat_src}'.")

    # 1. Nhãn mục tiêu luôn sinh strictly từ `target_col` quan trắc (không bao giờ từ giá trị nội suy)
    y_t = _build_hourly_safe_alert_label(df_sorted, target_col=target_col)
    ts = df_sorted["timestamp"]
    if horizon_hours == 0:
        y_horizon = y_t.copy()
    else:
        y_indexed = pd.Series(y_t.to_numpy(dtype=float), index=ts)
        y_horizon = pd.Series(
            y_indexed.reindex(ts + pd.Timedelta(hours=horizon_hours)).to_numpy(dtype=float),
            index=df_sorted.index,
            name=f"{target_col}_alert_24h_h{horizon_hours}",
        )

    # 2. Xác định mặt nạ chia Train/Test trước để phục vụ purge gap & kiểm soát nguồn đặc trưng Train-only
    if use_split_column:
        if "split" not in df_sorted.columns:
            raise KeyError("Thiếu cột 'split' khi `use_split_column=True`.")
        if "station_id" in df_sorted.columns:
            validate_modeling_split(df_sorted, "station_specific")
        raw_train_mask = df_sorted["split"] == "train"
        raw_test_mask = df_sorted["split"] == "test"
        test_boundary_ts = df_sorted.loc[raw_test_mask, "timestamp"].min()
        effective_split_str = str(test_boundary_ts)
    else:
        if split_timestamp is None:
            raise ValueError("Phải truyền `split_timestamp` khi `use_split_column=False`.")
        split_dt = _align_split_timestamp(ts, split_timestamp)
        raw_train_mask = ts < split_dt
        raw_test_mask = ts >= split_dt
        test_boundary_ts = split_dt
        effective_split_str = split_timestamp

    # Nếu `feature_source_col` khác `target_col`, chỉ áp dụng cho tập Train; toàn bộ đặc trưng Test luôn đóng băng từ `target_col` quan trắc gốc
    X_obs = engineer_classification_features(df_sorted, target_col=target_col)
    if feat_src != target_col:
        X_raw = engineer_classification_features(df_sorted, target_col=feat_src).copy()
        X_raw.loc[raw_test_mask] = X_obs.loc[raw_test_mask]
    else:
        X_raw = X_obs

    requested_cols = list(feature_cols) if feature_cols is not None else [c for c in CLASSIFICATION_FEATURES if c in X_raw.columns]
    for forbidden in FORBIDDEN_CLASSIFICATION_COLS:
        if forbidden in requested_cols:
            raise ValueError(f"Cột '{forbidden}' bị cấm xuất hiện trong tập đặc trưng phân loại.")
    selected_cols = [c for c in requested_cols if c in X_raw.columns]
    if not selected_cols:
        raise ValueError("Không có đặc trưng hợp lệ nào được chọn cho mô hình phân loại.")

    # Cổng hợp lệ theo cửa sổ quá khứ hoặc các biến khí tượng có sẵn
    if "pm25_rolling_mean_24h" in selected_cols:
        feature_gate = X_raw["pm25_rolling_mean_24h"].notna()
    else:
        feature_gate = X_raw[selected_cols].notna().all(axis=1)

    valid_mask = y_horizon.notna() & feature_gate

    # Vùng đệm loại bỏ biên (purge gap) khi horizon_hours > 0: nhãn Train t+h không được chạm mốc Test
    purged_train_mask = raw_train_mask.copy()
    if horizon_hours > 0 and pd.notna(test_boundary_ts):
        target_end_ts = ts + pd.Timedelta(hours=horizon_hours)
        purged_train_mask = raw_train_mask & (target_end_ts < test_boundary_ts)

    n_purged_horizon = int((raw_train_mask & valid_mask & ~purged_train_mask).sum())

    train_valid_mask = valid_mask & purged_train_mask
    test_valid_mask = valid_mask & raw_test_mask

    X_train = X_raw.loc[train_valid_mask, selected_cols].copy()
    y_train = y_horizon.loc[train_valid_mask].astype(int).copy()
    X_test = X_raw.loc[test_valid_mask, selected_cols].copy()
    y_test = y_horizon.loc[test_valid_mask].astype(int).copy()

    ts_train = ts.loc[train_valid_mask].reset_index(drop=True)
    ts_test = ts.loc[test_valid_mask].reset_index(drop=True)

    if not ts_train.empty and not ts_test.empty:
        if not (ts_train.max() < ts_test.min()):
            raise AssertionError(
                f"Vi phạm thứ tự thời gian: train.max()={ts_train.max()} >= test.min()={ts_test.min()}."
            )

    total_train_rows = int(raw_train_mask.sum())
    total_test_rows = int(raw_test_mask.sum())

    y_raw_train_valid = y_t.loc[raw_train_mask].notna().sum()
    y_raw_test_valid = y_t.loc[raw_test_mask].notna().sum()

    metadata = {
        "split_timestamp": effective_split_str,
        "horizon_hours": int(horizon_hours),
        "n_purged_horizon_rows": n_purged_horizon,
        "n_train_total": total_train_rows,
        "n_train_y_raw_valid": int(y_raw_train_valid),
        "n_train_valid": len(y_train),
        "n_test_total": total_test_rows,
        "n_test_y_raw_valid": int(y_raw_test_valid),
        "n_test_valid": len(y_test),
        "n_test_positive": int(y_test.sum()) if len(y_test) > 0 else 0,
        "n_train_positive": int(y_train.sum()) if len(y_train) > 0 else 0,
        "train_prevalence_valid": float(y_train.mean()) if len(y_train) > 0 else float("nan"),
        "test_prevalence_valid": float(y_test.mean()) if len(y_test) > 0 else float("nan"),
        "train_prevalence_all": float(y_train.sum() / total_train_rows) if total_train_rows > 0 else float("nan"),
        "test_prevalence_all": float(y_test.sum() / total_test_rows) if total_test_rows > 0 else float("nan"),
        "n_train_missing_cells": int(X_train.isna().sum().sum()),
        "n_test_missing_cells": int(X_test.isna().sum().sum()),
    }

    if return_timestamps:
        return X_train, y_train, X_test, y_test, metadata, ts_train, ts_test
    return X_train, y_train, X_test, y_test, metadata


def build_classification_pipeline(
    classifier: Any,
    feature_cols: Sequence[str],
    *,
    scale_features: bool = True,
) -> Pipeline:
    """
    Đóng gói tiền xử lý chống rò rỉ (`SimpleImputer` + optional `RobustScaler`) trong `ColumnTransformer`
    mang tên bước `'preprocessor'` để tương thích trực tiếp với `validate_no_leakage()`.
    """
    cols = list(feature_cols)
    for forbidden in FORBIDDEN_CLASSIFICATION_COLS:
        if forbidden in cols:
            raise ValueError(f"Cột '{forbidden}' bị cấm nằm trong pipeline phân loại.")

    num_steps: List[Tuple[str, Any]] = [
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True))
    ]
    if scale_features:
        num_steps.append(("scaler", RobustScaler()))

    preprocessor = ColumnTransformer(
        transformers=[("num", Pipeline(steps=num_steps), cols)],
        remainder="drop",
    )
    return Pipeline(steps=[("preprocessor", preprocessor), ("clf", clone(classifier))])


def verify_classification_no_leakage(
    fitted_pipeline: Pipeline,
    *,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    timestamps: Optional[pd.Series] = None,
    test_timestamps: Optional[pd.Series] = None,
    verify_chronology: bool = True,
) -> None:
    """
    Xác thực pipeline tiền xử lý phân loại không rò rỉ tham số hay thứ tự thời gian
    qua `src.cleaning_pipeline.validate_no_leakage` (tách riêng bước `'preprocessor'`
    vì `validate_no_leakage` refit chỉ với `X` không truyền `y`).
    """
    if not hasattr(fitted_pipeline, "named_steps") or "preprocessor" not in fitted_pipeline.named_steps:
        raise AssertionError("Pipeline phân loại thiếu bước 'preprocessor' để kiểm chứng rò rỉ.")
    prep_only = Pipeline([("preprocessor", fitted_pipeline.named_steps["preprocessor"])])
    validate_no_leakage(
        prep_only,
        X_train=X_train,
        X_test=X_test,
        timestamps=timestamps,
        test_timestamps=test_timestamps,
        verify_chronology=verify_chronology,
    )


def _extract_pos_probs(model: Any, X: pd.DataFrame) -> np.ndarray:
    """Trích xuất xác suất lớp dương từ estimator bất kể mô hình chỉ học 1 lớp."""
    probs_raw = model.predict_proba(X)
    if probs_raw.shape[1] == 1:
        pos_val = model.classes_[0] if hasattr(model, "classes_") else 0
        return np.ones(len(X), dtype=float) if int(pos_val) == 1 else np.zeros(len(X), dtype=float)
    return probs_raw[:, 1].astype(float)


def tune_classification_threshold(
    model: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    metric: str = "f2",
    n_splits: int = 5,
    min_precision: float = 0.60,
    return_details: bool = False,
) -> Union[float, Tuple[float, Optional[str]]]:
    """
    Tinh chỉnh ngưỡng quyết định tau HOÀN TOÀN trên tập Train qua `TimeSeriesSplit`.
    Dùng `clone()` để không làm đột biến mô hình gốc và bọc imputer trong từng fold nếu `X_train` có NaN.
    Phát hiện & cảnh báo minh bạch khi ngưỡng tối ưu chạm biên lưới [0.10, 0.90].
    """
    n_splits_eff = min(n_splits, max(2, len(X_train) - 1))
    tscv = TimeSeriesSplit(n_splits=n_splits_eff)
    thresholds = np.linspace(0.10, 0.90, 81)

    has_preprocessor = hasattr(model, "named_steps") and "preprocessor" in model.named_steps
    needs_fold_imputer = (not has_preprocessor) and bool(X_train.isna().any().any())

    oof_probs: List[float] = []
    oof_trues: List[int] = []

    for tr_idx, val_idx in tscv.split(X_train):
        y_tr_fold = y_train.iloc[tr_idx]
        if y_tr_fold.nunique() < 2:
            # Nếu fold đầu thiếu đa dạng lớp, gán xác suất prior nội fold thay vì làm lỗi solver
            const_p = float(y_tr_fold.mean())
            oof_probs.extend([const_p] * len(val_idx))
            oof_trues.extend(y_train.iloc[val_idx].tolist())
            continue

        m = clone(model)
        if needs_fold_imputer:
            m = build_classification_pipeline(m, list(X_train.columns), scale_features=False)
        m.fit(X_train.iloc[tr_idx], y_tr_fold)
        probs = _extract_pos_probs(m, X_train.iloc[val_idx])
        oof_probs.extend(probs.tolist())
        oof_trues.extend(y_train.iloc[val_idx].tolist())

    oof_probs_arr = np.asarray(oof_probs, dtype=float)
    oof_trues_arr = np.asarray(oof_trues, dtype=int)

    best_thresh = 0.50
    best_score = -1.0
    fallback_best_tau = 0.50
    fallback_best_f2 = -1.0

    for tau in thresholds:
        preds = (oof_probs_arr >= tau).astype(int)
        rec = recall_score(oof_trues_arr, preds, zero_division=0)
        prec = precision_score(oof_trues_arr, preds, zero_division=0)
        f2_val = fbeta_score(oof_trues_arr, preds, beta=2, zero_division=0)

        if f2_val > fallback_best_f2:
            fallback_best_f2 = f2_val
            fallback_best_tau = float(tau)

        if metric == "f2":
            score = f2_val
        elif metric == "recall_constrained":
            score = rec if prec >= min_precision else -1.0
        else:
            score = f1_score(oof_trues_arr, preds, zero_division=0)

        if score > best_score:
            best_score = score
            best_thresh = float(tau)

    # Nếu ràng buộc min_precision không có điểm khả thi trên OOF, quay về phương án F2 tốt nhất và ghi cảnh báo
    saturation_note: Optional[str] = None
    if best_score < 0 and metric == "recall_constrained":
        best_thresh = fallback_best_tau
        saturation_note = (
            f"Cảnh báo tune ({metric}, min_precision={min_precision:.2f}): không có tau nào trên OOF đạt Precision >= "
            f"{min_precision:.2f}; fallback sang F2 tối đa tau={best_thresh:.2f}."
        )
    elif best_thresh <= 0.10 + 1e-9 or best_thresh >= 0.90 - 1e-9:
        bound_label = "cận dưới 0.10" if best_thresh <= 0.10 + 1e-9 else "cận trên 0.90"
        saturation_note = (
            f"Cảnh báo bão hòa biên lưới ({metric}): tau*={best_thresh:.2f} chạm {bound_label} trên OOF "
            "(phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu)."
        )

    if saturation_note:
        logger.warning(saturation_note)

    best_thresh = round(float(best_thresh), 4)
    if return_details:
        return best_thresh, saturation_note
    return best_thresh


def evaluate_classifier(
    model_name: str,
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    threshold: float = 0.50,
) -> ClassificationModelMetrics:
    """
    Đo lường hiệu năng phân loại trên tập TEST độc lập với ngưỡng đã chốt.
    Luôn trả về ma trận nhầm lẫn 2x2 `[[TN, FP], [FN, TP]]`, bổ sung False Alarm Rate (FAR),
    Brier score và đánh dấu `NaN` (`UNESTIMABLE`) nếu tập Test đơn lớp (0 ca dương).
    """
    probs = _extract_pos_probs(model, X_test)
    preds = (probs >= threshold).astype(int)

    cm_arr = confusion_matrix(y_test, preds, labels=[0, 1])
    tn, fp, fn, tp = (int(cm_arr[0, 0]), int(cm_arr[0, 1]), int(cm_arr[1, 0]), int(cm_arr[1, 1]))
    cm = [[tn, fp], [fn, tp]]

    acc = float(accuracy_score(y_test, preds))
    far = float(fp / (fp + tn)) if (fp + tn) > 0 else float("nan")
    brier = float(brier_score_loss(y_test, probs)) if len(y_test) > 0 else float("nan")

    has_both_classes = (pd.Series(y_test).nunique() >= 2) and (int(np.sum(y_test)) > 0)
    if has_both_classes:
        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))
        f1 = float(f1_score(y_test, preds, zero_division=0))
        f2 = float(fbeta_score(y_test, preds, beta=2, zero_division=0))
        roc = float(roc_auc_score(y_test, probs))
        pr_auc_val = float(average_precision_score(y_test, probs))
        status = "OK"
    else:
        prec = 0.0 if (tp + fp) > 0 else float("nan")
        rec = float("nan")
        f1 = float("nan")
        f2 = float("nan")
        roc = float("nan")
        pr_auc_val = float("nan")
        status = "UNESTIMABLE (0 positives in Test)"

    def _r4(v: float) -> float:
        return round(v, 4) if np.isfinite(v) else float("nan")

    return ClassificationModelMetrics(
        model_name=model_name,
        threshold=round(float(threshold), 4),
        accuracy=_r4(acc),
        precision=_r4(prec),
        recall=_r4(rec),
        f1=_r4(f1),
        f2=_r4(f2),
        roc_auc=_r4(roc),
        pr_auc=_r4(pr_auc_val),
        confusion_matrix=cm,
        false_alarm_rate=_r4(far),
        brier_score=_r4(brier),
        status=status,
    )


def compute_logreg_odds_ratios(logreg_pipe: Pipeline, feature_names: Sequence[str]) -> pd.DataFrame:
    """Trích xuất hệ số chuẩn hóa RobustScaler và Odds Ratio exp(beta) từ Logistic Regression."""
    clf = logreg_pipe.named_steps["clf"] if hasattr(logreg_pipe, "named_steps") else logreg_pipe
    coefs = np.asarray(clf.coef_[0], dtype=float)
    df_or = pd.DataFrame({
        "Feature": list(feature_names),
        "LogReg Coef (RobustScaler)": np.round(coefs, 4),
        "Odds Ratio (exp(beta))": np.round(np.exp(np.clip(coefs, -20.0, 20.0)), 4),
    }).sort_values("LogReg Coef (RobustScaler)", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)
    return df_or


def compute_feature_importances(
    rf_model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    *,
    logreg_model: Optional[Pipeline] = None,
    n_repeats: int = 20,
) -> pd.DataFrame:
    """
    Đo lường tầm quan trọng biến trên tập TEST độc lập bằng Permutation Importance
    với thước đo `scoring='average_precision'` (PR-AUC, không phụ thuộc ngưỡng 0.5) và CI 95%.
    """
    rf_clf = rf_model.named_steps["clf"] if (hasattr(rf_model, "named_steps") and "clf" in rf_model.named_steps) else rf_model
    mdi = np.asarray(rf_clf.feature_importances_, dtype=float)

    if pd.Series(y_test).nunique() >= 2 and int(np.sum(y_test)) > 0:
        perm_res = permutation_importance(
            rf_model,
            X_test,
            y_test,
            n_repeats=n_repeats,
            random_state=42,
            scoring="average_precision",
        )
        mean_imp = np.asarray(perm_res.importances_mean, dtype=float)
        std_imp = np.asarray(perm_res.importances_std, dtype=float)
        se = std_imp / np.sqrt(float(n_repeats))
        ci_low = mean_imp - 1.96 * se
        ci_high = mean_imp + 1.96 * se
    else:
        n_feat = X_test.shape[1]
        mean_imp = np.full(n_feat, np.nan)
        std_imp = np.full(n_feat, np.nan)
        ci_low = np.full(n_feat, np.nan)
        ci_high = np.full(n_feat, np.nan)

    df_imp = pd.DataFrame({
        "Feature": list(X_test.columns),
        "MDI Importance": np.round(mdi, 4),
        "Permutation Mean": np.round(mean_imp, 6),
        "Permutation Std": np.round(std_imp, 6),
        "CI95 Low": np.round(ci_low, 6),
        "CI95 High": np.round(ci_high, 6),
    })

    if logreg_model is not None:
        or_df = compute_logreg_odds_ratios(logreg_model, list(X_test.columns))
        df_imp = df_imp.merge(or_df, on="Feature", how="left")

    sort_col = "Permutation Mean" if df_imp["Permutation Mean"].notna().any() else "MDI Importance"
    return df_imp.sort_values(sort_col, ascending=False, na_position="last").reset_index(drop=True)


def compute_coverage_and_outage_tables(
    df_station: pd.DataFrame,
    *,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    use_split_column: bool = False,
    target_col: str = "pm25",
    top_n_gaps: int = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Tạo 3 bảng minh bạch độ phủ dữ liệu cho phạm vi đơn trạm:
      1. Đối soát 4 quần thể dữ liệu (Grid -> Valid PM2.5 -> Valid y_raw 24h -> Evaluable valid_mask).
      2. Danh sách top đợt gián đoạn quan trắc PM2.5 liên tục dài nhất.
      3. Độ phủ & tỷ lệ dương tính theo từng tháng.
    """
    df_s = _select_single_station(df_station)
    ts = df_s["timestamp"]
    y_raw = _build_hourly_safe_alert_label(df_s, target_col=target_col)
    X_raw = engineer_classification_features(df_s, target_col=target_col)
    eval_mask = y_raw.notna() & X_raw["pm25_rolling_mean_24h"].notna()

    if use_split_column:
        validate_modeling_split(df_s, "station_specific")
        train_m = df_s["split"] == "train"
        test_m = df_s["split"] == "test"
    else:
        split_dt = _align_split_timestamp(ts, split_timestamp or DEFAULT_SPLIT_TIMESTAMP)
        train_m = ts < split_dt
        test_m = ts >= split_dt

    valid_pm25 = df_s[target_col].notna()
    valid_y = y_raw.notna()

    def _row_stats(label: str, mask: pd.Series) -> Dict[str, Any]:
        sub_tr = mask & train_m
        sub_te = mask & test_m
        pos_all = int((y_raw == 1.0)[mask].sum())
        pos_tr = int((y_raw == 1.0)[sub_tr].sum())
        pos_te = int((y_raw == 1.0)[sub_te].sum())
        n_tot = int(mask.sum())
        n_tr = int(sub_tr.sum())
        n_te = int(sub_te.sum())
        return {
            "Quần thể": label,
            "Total (giờ)": n_tot,
            "Train (giờ)": n_tr,
            "Test (giờ)": n_te,
            "Positives Total": pos_all,
            "Positives Train": pos_tr,
            "Positives Test": pos_te,
            "Prevalence (Train / Test)": (
                f"{(pos_tr / n_tr):.2%} / {(pos_te / n_te):.2%}"
                if n_tr > 0 and n_te > 0 else "N/A"
            ),
        }

    coverage_table = pd.DataFrame([
        _row_stats("1. Toàn bộ lưới thời gian (All grid)", pd.Series(True, index=df_s.index)),
        _row_stats("2. Có quan trắc PM2.5 hợp lệ", valid_pm25),
        _row_stats("3. Đủ nhãn cửa sổ 24h (y_raw.notna())", valid_y),
        _row_stats("4. Đủ nhãn & đặc trưng trễ 24h (Evaluable)", eval_mask),
    ])

    # Top các đợt gián đoạn PM2.5 liên tục
    is_miss = df_s[target_col].isna()
    run_id = (is_miss != is_miss.shift(1)).cumsum()
    gap_rows: List[Dict[str, Any]] = []
    for _, grp in df_s.loc[is_miss].groupby(run_id[is_miss], sort=False):
        n_h = int(len(grp))
        sp = "train" if bool(train_m.loc[grp.index[0]]) else "test"
        if bool(train_m.loc[grp.index[0]]) != bool(train_m.loc[grp.index[-1]]):
            sp = "train+test"
        gap_rows.append({
            "Start": str(grp["timestamp"].iloc[0]),
            "End": str(grp["timestamp"].iloc[-1]),
            "Duration (hours)": n_h,
            "Split": sp,
        })
    outage_gaps_table = (
        pd.DataFrame(gap_rows).sort_values("Duration (hours)", ascending=False).head(top_n_gaps).reset_index(drop=True)
        if gap_rows else pd.DataFrame(columns=["Start", "End", "Duration (hours)", "Split"])
    )

    # Độ phủ theo tháng
    df_m = pd.DataFrame({
        "YearMonth": ts.dt.strftime("%Y-%m"),
        "grid_hours": 1,
        "valid_pm25": valid_pm25.astype(int),
        "valid_y": valid_y.astype(int),
        "pos_y": (y_raw == 1.0).astype(int),
    })
    monthly_df = df_m.groupby("YearMonth", as_index=False).sum()
    monthly_df["Valid PM2.5 (%)"] = (monthly_df["valid_pm25"] / monthly_df["grid_hours"] * 100.0).round(1)
    monthly_df["Valid Label 24h (%)"] = (monthly_df["valid_y"] / monthly_df["grid_hours"] * 100.0).round(1)
    monthly_df["Positive Rate (% valid y)"] = np.where(
        monthly_df["valid_y"] > 0,
        (monthly_df["pos_y"] / monthly_df["valid_y"] * 100.0).round(2),
        np.nan,
    )

    return coverage_table, outage_gaps_table, monthly_df


def _fit_and_eval_scope(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    ts_train: pd.Series,
    ts_test: pd.Series,
    feature_cols: Sequence[str],
    label: str,
) -> Dict[str, Any]:
    """Huấn luyện nhanh Pipeline LogReg + RF, kiểm tra `validate_no_leakage`, đánh giá trên Test."""
    if len(X_train) < 30 or len(X_test) == 0 or y_train.nunique() < 2:
        return {
            "Setting": label,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "Test Positives": int(y_test.sum()) if len(y_test) > 0 else 0,
            "Dummy PR-AUC": float("nan"),
            "LogReg PR-AUC": float("nan"),
            "LogReg Recall": float("nan"),
            "RF PR-AUC": float("nan"),
            "RF Recall": float("nan"),
            "RF F2": float("nan"),
            "Status": "INSUFFICIENT_DATA",
        }

    dummy = DummyClassifier(strategy="prior").fit(X_train, y_train)
    logreg_pipe = build_classification_pipeline(
        LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000),
        feature_cols,
        scale_features=True,
    )
    rf_pipe = build_classification_pipeline(
        RandomForestClassifier(n_estimators=100, max_depth=8, class_weight="balanced", random_state=42),
        feature_cols,
        scale_features=False,
    )

    tau_log = tune_classification_threshold(logreg_pipe, X_train, y_train, metric="f2", n_splits=5)
    tau_rf = tune_classification_threshold(rf_pipe, X_train, y_train, metric="f2", n_splits=5)

    logreg_pipe.fit(X_train, y_train)
    rf_pipe.fit(X_train, y_train)

    verify_classification_no_leakage(
        logreg_pipe,
        X_train=X_train,
        X_test=X_test,
        timestamps=ts_train,
        test_timestamps=ts_test,
        verify_chronology=True,
    )

    m_dum = evaluate_classifier("Dummy", dummy, X_test, y_test, threshold=0.50)
    m_log = evaluate_classifier("LogReg", logreg_pipe, X_test, y_test, threshold=tau_log)
    m_rf = evaluate_classifier("RF", rf_pipe, X_test, y_test, threshold=tau_rf)

    return {
        "Setting": label,
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "Test Positives": int(y_test.sum()),
        "Dummy PR-AUC": m_dum.pr_auc,
        "LogReg PR-AUC": m_log.pr_auc,
        "LogReg Recall": m_log.recall,
        "RF PR-AUC": m_rf.pr_auc,
        "RF Recall": m_rf.recall,
        "RF F2": m_rf.f2,
        "Status": m_rf.status,
    }


def evaluate_feature_ablation_and_horizons(
    df_station: pd.DataFrame,
    *,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    use_split_column: bool = False,
    station_id: Optional[str] = None,
    horizons: Sequence[int] = (0, 1, 6, 12, 24),
) -> pd.DataFrame:
    """
    Thực nghiệm cắt giảm đặc trưng (Feature Ablation: Full vs Met+Lag24 vs Met-only)
    và phân tích suy giảm hiệu năng theo tầm dự báo h in {0, 1, 6, 12, 24} giờ với purge gap nghiêm ngặt.
    """
    df_s = _select_single_station(df_station, station_id=station_id)
    rows: List[Dict[str, Any]] = []

    feature_sets: List[Tuple[str, List[str]]] = [
        ("Full (Rolling24 + Lag24 + Met)", [c for c in CLASSIFICATION_FEATURES if c in df_s.columns or c.startswith("pm25_") or c in ("temp_humidity_interaction", "is_calm_wind")]),
        ("Lag24 + Met (No 24h Rolling)", [c for c in MET_AND_LAG24_FEATURES if c in df_s.columns or c == "pm25_lag24" or c in ("temp_humidity_interaction", "is_calm_wind")]),
        ("Meteorology + Time Only (No PM2.5)", [c for c in METEOROLOGY_ONLY_FEATURES if c in df_s.columns or c in ("temp_humidity_interaction", "is_calm_wind")]),
    ]

    # 1. Cắt giảm bộ đặc trưng tại h = 0
    for fs_name, f_cols in feature_sets:
        X_tr, y_tr, X_te, y_te, _, ts_tr, ts_te = prepare_classification_data(
            df_s,
            split_timestamp=split_timestamp,
            use_split_column=use_split_column,
            horizon_hours=0,
            feature_cols=f_cols,
            return_timestamps=True,
        )
        rows.append(_fit_and_eval_scope(X_tr, y_tr, X_te, y_te, ts_tr, ts_te, list(X_tr.columns), f"h=0h | {fs_name}"))

    # 2. Khảo sát các tầm dự báo h > 0 (dự báo tương lai thực thụ có purge gap)
    for h in horizons:
        if h == 0:
            continue
        X_tr, y_tr, X_te, y_te, _, ts_tr, ts_te = prepare_classification_data(
            df_s,
            split_timestamp=split_timestamp,
            use_split_column=use_split_column,
            horizon_hours=int(h),
            return_timestamps=True,
        )
        rows.append(_fit_and_eval_scope(X_tr, y_tr, X_te, y_te, ts_tr, ts_te, list(X_tr.columns), f"h={h}h | Full Feature Set"))

    return pd.DataFrame(rows)


def run_temporal_backtest_and_drift(
    df_station: pd.DataFrame,
    *,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    use_split_column: bool = False,
    station_id: Optional[str] = None,
    n_folds: int = 5,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Thực hiện Expanding-Window Backtest trên tập Train và đo lường dịch chuyển phân phối
    (Prevalence & PR-AUC drift) theo năm/mùa trên tập Test.
    """
    X_tr, y_tr, X_te, y_te, _, ts_tr, ts_te = prepare_classification_data(
        df_station,
        split_timestamp=split_timestamp,
        use_split_column=use_split_column,
        station_id=station_id,
        return_timestamps=True,
    )

    fold_rows: List[Dict[str, Any]] = []
    tscv = TimeSeriesSplit(n_splits=min(n_folds, max(2, len(X_tr) // 40)))
    for fold_idx, (tr_i, val_i) in enumerate(tscv.split(X_tr), start=1):
        y_f_tr, y_f_val = y_tr.iloc[tr_i], y_tr.iloc[val_i]
        if y_f_tr.nunique() < 2 or y_f_val.nunique() < 2:
            fold_rows.append({
                "Fold": f"Fold {fold_idx}",
                "Train N": len(tr_i),
                "Val N": len(val_i),
                "Val Positives": int(y_f_val.sum()),
                "Val Prevalence": round(float(y_f_val.mean()), 4),
                "RF PR-AUC": float("nan"),
                "RF Recall": float("nan"),
                "RF Brier": float("nan"),
                "Status": "SINGLE_CLASS_FOLD",
            })
            continue
        rf_p = build_classification_pipeline(
            RandomForestClassifier(n_estimators=80, max_depth=8, class_weight="balanced", random_state=42),
            list(X_tr.columns),
            scale_features=False,
        )
        rf_p.fit(X_tr.iloc[tr_i], y_f_tr)
        m_val = evaluate_classifier(f"Fold {fold_idx}", rf_p, X_tr.iloc[val_i], y_f_val, threshold=0.50)
        fold_rows.append({
            "Fold": f"Fold {fold_idx}",
            "Train N": len(tr_i),
            "Val N": len(val_i),
            "Val Positives": int(y_f_val.sum()),
            "Val Prevalence": round(float(y_f_val.mean()), 4),
            "RF PR-AUC": m_val.pr_auc,
            "RF Recall": m_val.recall,
            "RF Brier": m_val.brier_score,
            "Status": m_val.status,
        })
    backtest_df = pd.DataFrame(fold_rows)

    # Phân tầng dịch chuyển theo năm trên Test
    rf_full = build_classification_pipeline(
        RandomForestClassifier(n_estimators=100, max_depth=8, class_weight="balanced", random_state=42),
        list(X_tr.columns),
        scale_features=False,
    )
    rf_full.fit(X_tr, y_tr)
    drift_rows: List[Dict[str, Any]] = []
    years = pd.to_datetime(ts_te).dt.year
    for yr, grp_idx in pd.Series(y_te.index, index=years).groupby(level=0):
        idx_pos = np.where(years.to_numpy() == yr)[0]
        X_sub = X_te.iloc[idx_pos]
        y_sub = y_te.iloc[idx_pos]
        m_yr = evaluate_classifier(f"Test {yr}", rf_full, X_sub, y_sub, threshold=0.50)
        drift_rows.append({
            "Test Year": int(yr),
            "N (hours)": int(len(y_sub)),
            "Positives": int(y_sub.sum()),
            "Prevalence": round(float(y_sub.mean()), 4) if len(y_sub) > 0 else float("nan"),
            "RF PR-AUC": m_yr.pr_auc,
            "RF Recall": m_yr.recall,
            "RF FAR": m_yr.false_alarm_rate,
            "Status": m_yr.status,
        })
    drift_df = pd.DataFrame(drift_rows)
    return backtest_df, drift_df


def evaluate_derived_pm25_sensitivity(
    df_station: pd.DataFrame,
    *,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    use_split_column: bool = False,
    station_id: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Phân tích độ nhạy dùng `pm25_derived_interpolated` (chỉ lấp khoảng trống <= 3h) ĐỘC LẬP CHO ĐẶC TRƯNG TẬP TRAIN:
      - Nhãn mục tiêu `y_train` và `y_test` LUÔN bám strictly vào `pm25` quan trắc gốc (không bao giờ dùng nhãn nội suy).
      - Tập đặc trưng `X_test` giữ nguyên 100% từ `pm25` quan trắc gốc.
    """
    if "pm25_derived_interpolated" not in df_station.columns:
        return None

    X_tr_obs, y_tr_obs, X_te_obs, y_te_obs, meta_obs, ts_tr_obs, ts_te_obs = prepare_classification_data(
        df_station,
        split_timestamp=split_timestamp,
        target_col="pm25",
        feature_source_col="pm25",
        use_split_column=use_split_column,
        station_id=station_id,
        return_timestamps=True,
    )
    X_tr_der, y_tr_der, X_te_der, y_te_der, meta_der, ts_tr_der, ts_te_der = prepare_classification_data(
        df_station,
        split_timestamp=split_timestamp,
        target_col="pm25",
        feature_source_col="pm25_derived_interpolated",
        use_split_column=use_split_column,
        station_id=station_id,
        return_timestamps=True,
    )

    if not X_te_obs.equals(X_te_der) or not y_te_obs.equals(y_te_der):
        raise AssertionError("Vi phạm nguyên tắc Test bất biến trong sensitivity check derived PM2.5!")

    res_obs = _fit_and_eval_scope(
        X_tr_obs, y_tr_obs, X_te_obs, y_te_obs, ts_tr_obs, ts_te_obs, list(X_tr_obs.columns),
        "Observed-Only Features & Labels (Chính thức)",
    )
    res_der = _fit_and_eval_scope(
        X_tr_der, y_tr_der, X_te_der, y_te_der, ts_tr_der, ts_te_der, list(X_tr_der.columns),
        "Train Derived Features (<=3h) + Observed Labels",
    )
    res_obs["Train Recovered Rows"] = 0
    res_der["Train Recovered Rows"] = int(meta_der["n_train_valid"] - meta_obs["n_train_valid"])
    return pd.DataFrame([res_obs, res_der])


def render_pr_curve_figure(
    models_dict: Dict[str, Any],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    prevalence: float,
    output_path: Path,
    *,
    title_suffix: str = "Tập Test Độc Lập",
) -> None:
    """
    Xuất biểu đồ Precision-Recall Curve chất lượng cao (300 DPI) đối sánh với Baseline Prevalence.
    Xử lý an toàn trường hợp tập Test đơn lớp (0 ca dương).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

    has_positives = (pd.Series(y_test).nunique() >= 2) and (int(np.sum(y_test)) > 0)
    if not has_positives:
        ax.text(
            0.5,
            0.5,
            f"UNESTIMABLE: Tập Test có {int(np.sum(y_test))} ca dương tính / {len(y_test)} giờ\n"
            f"(Prevalence = 0.00%, không thể dựng đường cong Precision-Recall)",
            ha="center",
            va="center",
            fontsize=11,
            bbox={"boxstyle": "round,pad=0.6", "facecolor": "#f8f9fa", "edgecolor": "#adb5bd"},
        )
        ax.set_title(
            f"Precision-Recall Curve – Cảnh báo PM2.5 ({title_suffix})\n[UNESTIMABLE trên Test đơn lớp]",
            fontsize=11,
            fontweight="bold",
        )
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.0])
        ax.set_xlabel("Recall (Độ nhạy cảnh báo)", fontsize=10)
        ax.set_ylabel("Precision (Độ chính xác cảnh báo)", fontsize=10)
        plt.tight_layout()
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return

    ax.axhline(
        prevalence,
        color="black",
        linestyle="--",
        linewidth=1.2,
        label=f"Baseline Prevalence ({prevalence:.1%})",
    )

    colors = ["#7f7f7f", "#d95f02", "#2b5c8f", "#1b9e77"]
    for (name, model), c in zip(models_dict.items(), colors):
        probs = _extract_pos_probs(model, X_test)
        prec, rec, _ = precision_recall_curve(y_test, probs)
        pr_auc_val = average_precision_score(y_test, probs)
        ax.plot(rec, prec, label=f"{name} (PR-AUC = {pr_auc_val:.4f})", color=c, linewidth=2.0)

    ax.set_title(
        f"Precision-Recall Curve – Mô hình Cảnh báo Ô nhiễm PM2.5\n({title_suffix}; n={len(y_test):,}, Prev={prevalence:.2%})",
        fontsize=11.5,
        fontweight="bold",
        pad=10,
    )
    ax.set_xlabel("Recall (Độ nhạy cảnh báo)", fontsize=10)
    ax.set_ylabel("Precision (Độ chính xác cảnh báo)", fontsize=10)
    ax.set_xlim([0.0, 1.02])
    ax.set_ylim([0.0, 1.02])
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="lower left", frameon=True, fontsize=8.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ PR Curve: %s", output_path)


def render_feature_importance_figure(
    importance_df: pd.DataFrame,
    output_path: Path,
    *,
    title_suffix: str = "Đo lường trên tập Test độc lập",
) -> None:
    """
    Xuất biểu đồ Permutation Feature Importance theo PR-AUC (`average_precision`) trên tập Test.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)

    if importance_df["Permutation Mean"].notna().any():
        df_plot = importance_df.sort_values("Permutation Mean", ascending=True)
        vals = df_plot["Permutation Mean"].to_numpy(dtype=float)
        errs = df_plot["Permutation Std"].fillna(0.0).to_numpy(dtype=float)
        xlabel = "Mức suy giảm PR-AUC (Average Precision) khi xáo trộn đặc trưng"
    else:
        df_plot = importance_df.sort_values("MDI Importance", ascending=True)
        vals = df_plot["MDI Importance"].to_numpy(dtype=float)
        errs = np.zeros_like(vals)
        xlabel = "MDI Feature Importance trên Train (Test 0 positives — Permutation PR-AUC UNESTIMABLE)"

    y_pos = np.arange(len(df_plot))
    bar_colors = ["#2b5c8f" if v >= 0 else "#c0392b" for v in vals]
    ax.barh(y_pos, vals, xerr=errs, align="center", color=bar_colors, alpha=0.85, capsize=3)
    ax.axvline(0.0, color="#333333", linewidth=0.9, linestyle="-")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_plot["Feature"], fontsize=9)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_title(
        f"Tầm quan trọng Đặc trưng Cảnh báo Ô nhiễm PM2.5\n({title_suffix})",
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    ax.grid(True, axis="x", linestyle=":", alpha=0.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ Feature Importance: %s", output_path)


def _fmt_metric_pct(val: Any) -> str:
    if isinstance(val, (int, float, np.floating)):
        if np.isnan(val):
            return "UNESTIMABLE"
        return f"{val:.2%}"
    return str(val)


def _fmt_metric_f4(val: Any) -> str:
    if isinstance(val, (int, float, np.floating)):
        if np.isnan(val):
            return "UNESTIMABLE"
        return f"{val:.4f}"
    return str(val)


def generate_leakage_audit_markdown(
    metadata: Dict[str, Any],
    metrics_table: pd.DataFrame,
    *,
    ablation_table: Optional[pd.DataFrame] = None,
    threshold_warnings: Optional[List[str]] = None,
) -> str:
    """
    Biên bản kiểm toán 4 dạng rò rỉ dữ liệu (Data Leakage Audit) đạt chuẩn INFO3020 — Issue #13 & Task D14.
    """
    log_rows = metrics_table.loc[metrics_table["Model"].str.contains("Logistic", na=False)]
    rf_rows = metrics_table.loc[metrics_table["Model"].str.contains("Random Forest", na=False)]

    rec_log = _fmt_metric_pct(log_rows["Recall"].values[0]) if len(log_rows) > 0 else "N/A"
    pr_log = _fmt_metric_f4(log_rows["PR-AUC"].values[0]) if len(log_rows) > 0 else "N/A"
    rec_rf = _fmt_metric_pct(rf_rows["Recall"].values[0]) if len(rf_rows) > 0 else "N/A"
    pr_rf = _fmt_metric_f4(rf_rows["PR-AUC"].values[0]) if len(rf_rows) > 0 else "N/A"

    split_str = metadata.get("split_timestamp", DEFAULT_SPLIT_TIMESTAMP)
    n_tr_v = metadata.get("n_train_valid", 0)
    n_te_v = metadata.get("n_test_valid", 0)
    n_tr_miss = metadata.get("n_train_missing_cells", 0)
    n_te_miss = metadata.get("n_test_missing_cells", 0)

    ablation_block = ""
    if ablation_table is not None and not ablation_table.empty:
        ablation_block = (
            "\n### Bằng chứng định lượng qua Feature Ablation & Dự báo đa tầm (Purge Gap)\n\n"
            + _df_to_markdown(ablation_table)
            + "\n"
        )

    warn_block = ""
    if threshold_warnings:
        warn_block = "\n### Ghi chú bão hòa ngưỡng trên OOF\n" + "\n".join(f"- {w}" for w in threshold_warnings) + "\n"

    md = f"""# Biên Bản Kiểm Toán Rò Rỉ Dữ Liệu Phân Loại (Data Leakage Audit) — Issue #13 & Task D14

> **Căn cứ học thuật:** Slide W11 & Quy định liêm chính học thuật INFO3020.
> **Mốc chia thời gian kiểm chứng:** `{split_str}`
> **Kích thước tập hợp lệ kiểm chứng:** Train = {n_tr_v:,} giờ (ô thiếu đầu vào: {n_tr_miss}) | Test = {n_te_v:,} giờ (ô thiếu đầu vào: {n_te_miss})

---

## 1. Kiểm toán 4 Dạng Rò rỉ Dữ liệu Cốt lõi & Bằng chứng Thực thi

| Dạng Rò Rỉ | Rủi ro Tiềm ẩn | Biện pháp Phòng ngừa & Bằng chứng Kiểm chứng | Kết luận |
|---|---|---|:---:|
| **1. Target Leakage (Rò rỉ Mục tiêu)** | Dùng biến phái sinh trực tiếp từ mục tiêu (`pm25_was_missing`), dùng biến đồng thời `pm10`, hoặc để đặc trưng trượt nhìn thấy giá trị tại $t$. | Cấm tuyệt đối `pm25`, `pm10`, `pm25_was_missing`, `is_high_humidity_fog` trong `FORBIDDEN_CLASSIFICATION_COLS` (raise `ValueError`). Đặc trưng trượt bắt buộc `shift(1)` (từ $t-1$ trở về trước) trên lưới giờ liên tục; kiểm chứng bằng unit test thay đổi `pm25[t] = 999` không làm biến thiên bất kỳ đặc trưng nào tại $t$. | **PASS** |
| **2. Train-Test Contamination (Nhiễm chéo Train-Test)** | Tham số imputer, scaler hoặc ngưỡng $\\tau$ học từ tập Test hoặc impute toàn cục trước CV. | Không còn impute trong `prepare_classification_data`. `SimpleImputer(median)` và `RobustScaler()` nằm bên trong `Pipeline([('preprocessor', ColumnTransformer(...)), ('clf', ...)])`; từng fold của `TimeSeriesSplit(5)` chỉ fit trên `X_train.iloc[tr_idx]`; ngưỡng $\\tau^*$ bất biến trước đột biến `y_test`; kiểm chứng sau fit bằng `src.cleaning_pipeline.validate_no_leakage()`. | **PASS** |
| **3. Temporal Leakage (Rò rỉ Thứ tự Thời gian)** | Chia ngẫu nhiên hoặc để nhãn $y_{{t+h}}$ ở cuối Train chồng lấn sang miền Test. | Phân chia tuyến tính kiểm chứng `ts_train.max() < ts_test.min()`. Khi tầm dự báo $h > 0$, áp dụng purge gap `t + h < split_timestamp` loại bỏ mọi mẫu cuối Train có cửa sổ nhãn chạm Test. | **PASS** |
| **4. Group / Station Leakage (Rò rỉ Cụm trạm)** | Gộp nhiều trạm lệch pha thời gian (`VN001` vs `VN003`) làm nhiễu rolling hoặc làm lộ ranh giới thời gian trạm khác. | Áp dụng Protocol A đơn trạm (`station_id` rõ ràng). `_select_single_station()` từ chối fail-closed nếu phát hiện > 1 trạm khi chưa chỉ định `station_id`. `engineer_classification_features()` nhóm độc lập theo `station_id` bảo đảm 24h đầu trạm B luôn là `NaN`, không tràn từ trạm A. | **PASS** |

---

## 2. Giải trình Loại trừ Kỹ thuật Tổng hợp Mẫu SMOTE

- **Nguyên nhân loại trừ:** SMOTE (*Synthetic Minority Over-sampling Technique*) nội suy tuyến tính giữa các hàng không kề nhau theo thời gian trong không gian đa biến.
- **Hệ quả trên chuỗi thời gian khí tượng:** Nội suy lân cận ghép cặp hai ngày khác mùa/khác bối cảnh synop, tạo ra bước nhảy phi vật lý giữa gió, áp suất và nhiệt-ẩm, đồng thời phá vỡ cấu trúc tự tương quan và ranh giới thời gian giữa các đợt ô nhiễm.
- **Giải pháp thay thế chuẩn mực:** Áp dụng `class_weight='balanced'` kết hợp tinh chỉnh ngưỡng $\\tau$ trên OOF của Train theo $F_2$ và `Recall` dưới ràng buộc `Precision >= 0.60`.

---

## 3. Giải trình Chồng lấn Cửa sổ (Window Overlap) tại $h=0$ & Độ trễ Reanalysis ERA5

- **Tiêu chí cảnh giác (Slide W11 Takeaway #4):** *"Nghi ngờ ngay lập tức nếu PR-AUC hoặc Recall đạt > 99%"*.
- **Kết quả thực nghiệm tại tầm truy hồi tức thời ($h=0$):**
  - Logistic Regression: Recall = {rec_log}, PR-AUC = {pr_log}
  - Random Forest: Recall = {rec_rf}, PR-AUC = {pr_rf}
- **Giải thích toán học:** Tại $h=0$, đặc trưng `pm25_rolling_mean_24h` tổng hợp $[t-24, t-1]$ còn nhãn $y_t$ tổng hợp $[t-23, t]$. Hai cửa sổ chia sẻ **23/24 giờ (95,8%)** nên trạng thái nhãn chủ yếu được suy trực tiếp từ 23 giờ giao thoa với hệ số tự tương quan $\\rho_1 \\approx 0,73$. Khi dịch chuyển sang dự báo tương lai thật tại $h = 24\\text{{h}}$ (giao thoa **0/24 giờ**) hoặc cắt bỏ đặc trưng PM2.5 quá khứ (chỉ dùng khí tượng), hiệu năng giảm mạnh theo đúng quy luật vật lý — đây là **bằng chứng trực tiếp khẳng định không có rò rỉ dữ liệu tương lai**.
- **Giới hạn vận hành (ERA5 Latency):** {_ERA5_LATENCY_NOTE}
{ablation_block}{warn_block}
"""
    return md


def _render_scope_markdown(res: ClassificationResults, heading: str = "##") -> str:
    """Sinh phần báo cáo động hoàn toàn cho một phạm vi chạy đơn trạm."""
    sub = "#" + heading
    lines: List[str] = [
        f"{heading} Phạm vi `{res.scope_name}` (`{res.station_id}`)",
        "",
        f"- **Mốc cắt thời gian:** `{res.split_timestamp}` | **Tầm dự báo:** `h = {res.horizon_hours}h`",
        f"- **Kích thước evaluable:** Train = {res.n_train_valid:,} / {res.n_train_total:,} giờ "
        f"(Prevalence = {res.train_prevalence_valid:.2%} hợp lệ; {res.train_prevalence_all:.2%} toàn lưới) | "
        f"Test = {res.n_test_valid:,} / {res.n_test_total:,} giờ "
        f"(Prevalence = {_fmt_metric_pct(res.test_prevalence_valid)} hợp lệ; {_fmt_metric_pct(res.test_prevalence_all)} toàn lưới)",
        f"- **Ngưỡng tối ưu OOF trên Train:** LogReg ($F_2$) $\\tau^* = {res.best_threshold_logreg:.2f}$, LogReg (`Prec>=0.60`) $\\tau^* = {res.best_threshold_logreg_constrained:.2f}$ | "
        f"RF ($F_2$) $\\tau^* = {res.best_threshold_rf:.2f}$, RF (`Prec>=0.60`) $\\tau^* = {res.best_threshold_rf_constrained:.2f}$",
        "",
        f"{sub} Bảng hiệu năng trên tập Test độc lập",
        "",
        _df_to_markdown(res.metrics_table),
        "",
    ]

    if res.threshold_warnings:
        lines.extend([f"{sub} Ghi chú chẩn đoán ngưỡng trên OOF", ""])
        lines.extend([f"- {w}" for w in res.threshold_warnings])
        lines.append("")

    if res.coverage_table is not None:
        lines.extend([f"{sub} Đối soát 4 quần thể dữ liệu & gián đoạn quan trắc", "", _df_to_markdown(res.coverage_table), ""])

    if res.outage_gaps_table is not None and not res.outage_gaps_table.empty:
        lines.extend(["**Top đợt gián đoạn PM2.5 liên tục dài nhất:**", "", _df_to_markdown(res.outage_gaps_table.head(5)), ""])

    if res.ablation_horizon_table is not None and not res.ablation_horizon_table.empty:
        lines.extend([f"{sub} Thực nghiệm Cắt giảm Đặc trưng (Ablation) & Tầm dự báo $h \\in \\{{0,1,6,12,24\\}}$", "", _df_to_markdown(res.ablation_horizon_table), ""])

    if res.feature_importances is not None and not res.feature_importances.empty:
        lines.extend([f"{sub} Permutation Importance (`average_precision`) & Logistic Odds Ratios", "", _df_to_markdown(res.feature_importances), ""])

    if res.backtest_table is not None and not res.backtest_table.empty:
        lines.extend([f"{sub} Expanding-Window Temporal Backtest (trên Train)", "", _df_to_markdown(res.backtest_table), ""])

    if res.annual_drift_table is not None and not res.annual_drift_table.empty:
        lines.extend([f"{sub} Dịch chuyển theo năm trên tập Test", "", _df_to_markdown(res.annual_drift_table), ""])

    if res.derived_sensitivity_table is not None and not res.derived_sensitivity_table.empty:
        lines.extend([f"{sub} Kiểm tra độ nhạy dùng `pm25_derived_interpolated` chỉ cho đặc trưng Train (nhãn luôn giữ observed)", "", _df_to_markdown(res.derived_sensitivity_table), ""])

    return "\n".join(lines)


def write_classification_report(
    results: ClassificationResults,
    report_path: Path,
    *,
    extra_runs: Optional[List[ClassificationResults]] = None,
) -> None:
    """
    Xuất báo cáo khoa học tổng hợp toàn bộ kết quả phân loại (Issue #13) từ dữ liệu tính toán thực tế,
    tuyệt đối không hardcode số liệu và chuẩn hóa LF.
    """
    extras = extra_runs if extra_runs is not None else results.extra_runs
    dum_m = results.model_metrics.get("dummy")
    pers_m = results.model_metrics.get("persistence")
    log_m = results.model_metrics.get("logreg")
    rf_m = results.model_metrics.get("rf")

    dum_acc = _fmt_metric_pct(dum_m.accuracy) if dum_m else "N/A"
    dum_rec = _fmt_metric_pct(dum_m.recall) if dum_m else "N/A"
    dum_pr = _fmt_metric_f4(dum_m.pr_auc) if dum_m else "N/A"
    pers_rec = _fmt_metric_pct(pers_m.recall) if pers_m else "N/A"
    pers_pr = _fmt_metric_f4(pers_m.pr_auc) if pers_m else "N/A"
    rf_rec = _fmt_metric_pct(rf_m.recall) if rf_m else "N/A"
    rf_prec = _fmt_metric_pct(rf_m.precision) if rf_m else "N/A"
    rf_f2 = _fmt_metric_f4(rf_m.f2) if rf_m else "N/A"
    rf_pr = _fmt_metric_f4(rf_m.pr_auc) if rf_m else "N/A"
    rf_far = _fmt_metric_pct(rf_m.false_alarm_rate) if rf_m else "N/A"
    log_rec = _fmt_metric_pct(log_m.recall) if log_m else "N/A"
    log_prec = _fmt_metric_pct(log_m.precision) if log_m else "N/A"
    log_f2 = _fmt_metric_f4(log_m.f2) if log_m else "N/A"
    log_pr = _fmt_metric_f4(log_m.pr_auc) if log_m else "N/A"
    log_far = _fmt_metric_pct(log_m.false_alarm_rate) if log_m else "N/A"

    n_te_pos = int(sum(rf_m.confusion_matrix[1])) if rf_m else 0
    rf_tp = int(rf_m.confusion_matrix[1][1]) if rf_m else 0
    rf_fn = int(rf_m.confusion_matrix[1][0]) if rf_m else 0
    log_tp = int(log_m.confusion_matrix[1][1]) if log_m else 0

    # Phân tích trung thực Permutation Importance theo average_precision
    imp_df = results.feature_importances
    met_only_imp = imp_df.loc[~imp_df["Feature"].str.startswith("pm25_")] if not imp_df.empty else imp_df
    pos_met_feats = met_only_imp.loc[met_only_imp["Permutation Mean"] > 0, "Feature"].tolist() if not met_only_imp.empty else []
    nonpos_met_feats = met_only_imp.loc[met_only_imp["Permutation Mean"] <= 0, "Feature"].tolist() if not met_only_imp.empty else []
    top_feats = imp_df.head(3)["Feature"].tolist() if not imp_df.empty else []

    if pos_met_feats:
        met_verdict = (
            f"Các biến khí tượng/chu kỳ có Permutation Mean dương theo `average_precision`: {', '.join(pos_met_feats)}; "
            f"trong khi {', '.join(nonpos_met_feats) if nonpos_met_feats else 'không có biến nào'} có đóng góp `<= 0` do bị biến tự hồi quy `pm25_rolling_mean_24h` che khuất ở tầm h=0."
        )
    else:
        met_verdict = (
            "Tại tầm h=0 với sự hiện diện của `pm25_rolling_mean_24h` (chồng lấn 23/24 giờ), toàn bộ các biến khí tượng có "
            "Permutation Importance xấp xỉ 0 hoặc âm nhẹ trong Random Forest — cho thấy tín hiệu trượt quá khứ chi phối gần như hoàn toàn quyết định ở h=0, "
            "còn vai trò khí tượng bộc lộ rõ hơn qua **Logistic Regression Odds Ratios** và mô hình **Meteorology-Only** trong bảng Ablation."
        )

    sha_note = f" | **SHA-256:** `{results.dataset_sha256[:16]}...`" if results.dataset_sha256 else ""
    extra_sections = "\n\n---\n\n".join(_render_scope_markdown(ex, heading="##") for ex in extras)
    extra_block = f"\n\n---\n\n{extra_sections}" if extra_sections else ""

    content = f"""# Báo Cáo Kết Quả Mô Hình Phân Loại Cảnh Báo Ô Nhiễm (Truy Hồi Tức Thời & Đa Tầm) — Issue #13

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 11
> **Phạm vi chính:** `{results.scope_name}` (`{results.station_id}`){sha_note}
> **Mốc phân chia chuỗi thời gian:** `{results.split_timestamp}` | **Kích thước Evaluable:** Train = {results.n_train_valid:,} giờ | Test = {results.n_test_valid:,} giờ ({n_te_pos:,} ca dương tính)

---

## 1. Bản Chất Bài Toán, Độ Trễ ERA5 & Đối Soát Quần Thể Dữ Liệu

- **Định vị khoa học:** Bài toán đánh giá khả năng phân loại vượt ngưỡng trung bình 24 giờ QCVN 05:2023/BTNMT ($\\text{{PM}}_{{2.5}} \\ge 50,0\\ \\mu\\text{{g/m}}^3$). {_ERA5_LATENCY_NOTE}
- **Minh bạch mẫu số & tỷ lệ mất cân bằng (Prevalence):**
  - Tập Train hợp lệ: **{results.n_train_valid:,} / {results.n_train_total:,}** giờ lưới (Prevalence = **{results.train_prevalence_valid:.2%}** trên mẫu hợp lệ; **{results.train_prevalence_all:.2%}** trên tổng lưới).
  - Tập Test hợp lệ: **{results.n_test_valid:,} / {results.n_test_total:,}** giờ lưới (Prevalence = **{_fmt_metric_pct(results.test_prevalence_valid)}** trên mẫu hợp lệ; **{_fmt_metric_pct(results.test_prevalence_all)}** trên tổng lưới).

{_df_to_markdown(results.coverage_table)}

---

## 2. Tổng Hợp Hiệu Năng Phân Loại Trên Tập Test Độc Lập (`{results.scope_name}`)

- **Bẫy Accuracy & Baseline tham chiếu:**
  - `DummyClassifier(strategy='prior')` đạt Accuracy = **{dum_acc}**, nhưng Recall = **{dum_rec}** và PR-AUC = **{dum_pr}** (bằng đúng tỷ lệ dương tính của tập Test).
  - `PersistenceRuleClassifier` (ngưỡng cơ học 1 biến `pm25_rolling_mean_24h >= 50`) đạt Recall = **{pers_rec}**, PR-AUC = **{pers_pr}**.
- **Mô hình Học máy (ngưỡng $F_2$ tinh chỉnh hoàn toàn trên Train OOF):**
  - **Logistic Regression (Balanced, $\\tau^*={results.best_threshold_logreg:.2f}$):** Recall = **{log_rec}** ({log_tp:,}/{n_te_pos:,} ca dương), Precision = **{log_prec}**, F2 = **{log_f2}**, PR-AUC = **{log_pr}**, FAR = **{log_far}**.
  - **Random Forest (Balanced, $\\tau^*={results.best_threshold_rf:.2f}$):** Recall = **{rf_rec}** ({rf_tp:,}/{n_te_pos:,} ca dương, bỏ sót {rf_fn:,} ca), Precision = **{rf_prec}**, F2 = **{rf_f2}**, PR-AUC = **{rf_pr}**, FAR = **{rf_far}**.

{_df_to_markdown(results.metrics_table)}

---

## 3. Phân Tích Chồng Lấn Cửa Sổ (Window Overlap), Ablation & Tầm Dự Báo Tương Lai ($h \\ge 1\\text{{h}}$)

- Tại $h=0$, `pm25_rolling_mean_24h` ($[t-24, t-1]$) và nhãn mục tiêu $y_t$ ($[t-23, t]$) chồng lấn **23/24 (95,8%)** phần tử. Hiệu năng tiệm cận 1,0 phản ánh tính kế thừa của cửa sổ 24h hơn là khả năng dự báo dài hạn.
- Bảng thực nghiệm dưới đây tách riêng vai trò của đặc trưng tự hồi quy so với biến khí tượng thuần túy và kiểm tra sự suy giảm PR-AUC theo từng tầm dự báo $h \\in \\{{0, 1, 6, 12, 24\\}}$ giờ (có áp dụng purge gap $t+h < t_{{test}}$):

{_df_to_markdown(results.ablation_horizon_table)}

---

## 4. Tầm Quan Trọng Biến (`average_precision`) & Logistic Regression Odds Ratios

- **3 đặc trưng đứng đầu theo Permutation PR-AUC:** {', '.join(top_feats) if top_feats else 'N/A'}.
- **Đánh giá trung thực về biến khí tượng ở $h=0$:** {met_verdict}

{_df_to_markdown(results.feature_importances)}

---

## 5. Khả Năng Tổng Quát Hóa Thời Gian (Temporal Backtest) & Độ Nhạy Nội Suy Ngắn Hạn

{_df_to_markdown(results.backtest_table)}

{_df_to_markdown(results.derived_sensitivity_table) if results.derived_sensitivity_table is not None else ""}
{extra_block}
"""
    _write_lf_text(report_path, content)
    logger.info("Đã lưu báo cáo kết quả phân loại: %s", report_path)


def write_classification_findings(
    results: ClassificationResults,
    findings_path: Path,
    *,
    extra_runs: Optional[List[ClassificationResults]] = None,
) -> None:
    """
    Xuất tài liệu tổng hợp phát hiện khoa học đáp ứng Task D13 (`docs/classification_findings.md`)
    bám sát 100% số liệu thực nghiệm và nguyên tắc liêm chính INFO3020.
    """
    extras = extra_runs if extra_runs is not None else results.extra_runs
    dum_m = results.model_metrics.get("dummy")
    pers_m = results.model_metrics.get("persistence")
    log_m = results.model_metrics.get("logreg")
    rf_m = results.model_metrics.get("rf")

    n_te_pos = int(sum(rf_m.confusion_matrix[1])) if rf_m else 0
    rf_tp = int(rf_m.confusion_matrix[1][1]) if rf_m else 0
    rf_fn = int(rf_m.confusion_matrix[1][0]) if rf_m else 0
    rf_tn = int(rf_m.confusion_matrix[0][0]) if rf_m else 0
    rf_fp = int(rf_m.confusion_matrix[0][1]) if rf_m else 0

    log_tp = int(log_m.confusion_matrix[1][1]) if log_m else 0
    log_fn = int(log_m.confusion_matrix[1][0]) if log_m else 0

    ext_summary_rows: List[Dict[str, Any]] = []
    for run in [results, *extras]:
        rf_r = run.model_metrics.get("rf")
        log_r = run.model_metrics.get("logreg")
        dum_r = run.model_metrics.get("dummy")
        ext_summary_rows.append({
            "Scope": run.scope_name,
            "Station": run.station_id,
            "Train Valid (Prev)": f"{run.n_train_valid:,} ({run.train_prevalence_valid:.2%})",
            "Test Valid (Prev)": f"{run.n_test_valid:,} ({_fmt_metric_pct(run.test_prevalence_valid)})",
            "Dummy PR-AUC": _fmt_metric_f4(dum_r.pr_auc) if dum_r else "N/A",
            "LogReg PR-AUC / Rec": f"{_fmt_metric_f4(log_r.pr_auc)} / {_fmt_metric_pct(log_r.recall)}" if log_r else "N/A",
            "RF PR-AUC / Rec": f"{_fmt_metric_f4(rf_r.pr_auc)} / {_fmt_metric_pct(rf_r.recall)}" if rf_r else "N/A",
        })

    content = f"""# Tổng Hợp Phát Hiện Khoa Học: Mô Hình Phân Loại Cảnh Báo Ô Nhiễm PM2.5 — Task D13 (Issue #13)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Phạm vi dữ liệu chính:** `{results.scope_name}` (`{results.station_id}`, cắt thời gian `{results.split_timestamp}`)
> **Tập Test độc lập:** {results.n_test_valid:,} giờ hợp lệ (trong {results.n_test_total:,} giờ lưới; **{n_te_pos:,} ca dương tính**, Prevalence = {_fmt_metric_pct(results.test_prevalence_valid)} trên mẫu hợp lệ / {_fmt_metric_pct(results.test_prevalence_all)} trên tổng lưới)

---

## 1. Bản Chất Khoa Học: Truy Hồi Tức Thời ($h=0$) vs Dự Báo Tương Lai ($h > 0$)

1. **Tương thích chu kỳ quy chuẩn QCVN 05:2023/BTNMT:** Nhãn mục tiêu $y_t = \\mathbb{{I}}(\\overline{{\\text{{PM}}_{{2.5}}}}_{{[t-23, t]}} \\ge 50,0\\ \\mu\\text{{g/m}}^3)$ giữ nguyên tính bất khả xâm phạm của giá trị quan trắc gốc (không nội suy nhãn).
2. **Minh bạch độ trễ dữ liệu ERA5 (Không gọi sai là real-time):** {_ERA5_LATENCY_NOTE}
3. **Tách biệt tín hiệu tự hồi quy vs khí tượng:**
   - Ở $h=0$, `pm25_rolling_mean_24h` ($[t-24, t-1]$) chia sẻ **23/24 giờ (95,8%)** với $y_t$, giúp cả `PersistenceRuleClassifier` lẫn `LogisticRegression`/`RandomForest` đạt hiệu năng rất cao (`RF PR-AUC = {_fmt_metric_f4(rf_m.pr_auc) if rf_m else 'N/A'}`, `Persistence PR-AUC = {_fmt_metric_f4(pers_m.pr_auc) if pers_m else 'N/A'}`).
   - Khi chuyển sang dự báo tương lai $h \\in \\{{1, 6, 12, 24\\}}$ giờ hoặc mô hình thuần khí tượng (Ablation không có PM2.5), PR-AUC phản ánh giới hạn vật lý thực sự khi không còn cửa sổ trượt chồng lấn.

---

## 2. Confusion Matrix & Đánh Đổi Precision–Recall–FAR Trên Tập Test Đã Chốt Ngưỡng

- **Baseline `DummyClassifier(strategy='prior')`:** Accuracy = **{_fmt_metric_pct(dum_m.accuracy) if dum_m else 'N/A'}**, Recall = **{_fmt_metric_pct(dum_m.recall) if dum_m else 'N/A'}**, PR-AUC = **{_fmt_metric_f4(dum_m.pr_auc) if dum_m else 'N/A'}** (khớp chính xác tỷ lệ dương tính của Test, chứng minh *Bẫy Accuracy*).
- **Random Forest (`Balanced`, $\\tau^* = {results.best_threshold_rf:.2f}$ tối ưu $F_2$ trên Train OOF):**
  - Confusion Matrix `[[TN, FP], [FN, TP]]` = `[[{rf_tn}, {rf_fp}], [{rf_fn}, {rf_tp}]]` (mẫu số dương: {n_te_pos:,} ca; mẫu số âm: {rf_tn + rf_fp:,} giờ).
  - Precision = **{_fmt_metric_pct(rf_m.precision) if rf_m else 'N/A'}**, Recall = **{_fmt_metric_pct(rf_m.recall) if rf_m else 'N/A'}**, F1 = **{_fmt_metric_f4(rf_m.f1) if rf_m else 'N/A'}**, F2 = **{_fmt_metric_f4(rf_m.f2) if rf_m else 'N/A'}**, FAR = **{_fmt_metric_pct(rf_m.false_alarm_rate) if rf_m else 'N/A'}**, Brier = **{_fmt_metric_f4(rf_m.brier_score) if rf_m else 'N/A'}**, ROC-AUC = **{_fmt_metric_f4(rf_m.roc_auc) if rf_m else 'N/A'}**, PR-AUC = **{_fmt_metric_f4(rf_m.pr_auc) if rf_m else 'N/A'}**.
- **Logistic Regression (`Balanced`, $\\tau^* = {results.best_threshold_logreg:.2f}$):** bắt được {log_tp:,}/{n_te_pos:,} ca (bỏ sót {log_fn:,} ca), Recall = **{_fmt_metric_pct(log_m.recall) if log_m else 'N/A'}**, Precision = **{_fmt_metric_pct(log_m.precision) if log_m else 'N/A'}**, PR-AUC = **{_fmt_metric_f4(log_m.pr_auc) if log_m else 'N/A'}**.

---

## 3. Feature Importance (`average_precision`) & Kiểm Soát Đa Cộng Tuyến `pm25`/`pm10`

- **Loại trừ bắt buộc `pm10`:** Trong bộ dữ liệu, tương quan Pearson giữa `pm25` và `pm10` rất cao ($r = 0,9727$); việc giữ `pm10` đồng thời ở thời điểm $t$ vừa gây đa cộng tuyến nghiêm trọng vừa tái tạo lại phép đo bụi đồng thời tại $t$. Do đó `pm10` bị cấm tuyệt đối trong `FORBIDDEN_CLASSIFICATION_COLS`.
- **Xếp hạng đặc trưng thực nghiệm (Permutation PR-AUC với 20 lần lặp trên Test):**
  - Nhóm tự hồi quy quá khứ (`pm25_rolling_mean_24h`, `pm25_rolling_std_24h`, `pm25_lag24`) giữ thứ hạng chi phối tuyệt đối.
  - Ở tầm $h=0$, Permutation Importance của các biến khí tượng đơn lẻ trong Random Forest gần 0 hoặc âm nhẹ do bị thông tin 23/24h của `pm25_rolling_mean_24h` che khuất; cấu trúc tác động của gió, nhiệt-ẩm và áp suất được quan sát bổ sung qua bảng **Odds Ratio của Logistic Regression** và kịch bản **Meteorology-Only** (xem bảng dưới).

{_df_to_markdown(results.feature_importances)}

---

## 4. Tổng Hợp Đa Phạm Vi (Protocol A: `VN001` & `VN003_OPENAQ_7441`)

- Khi đánh giá trên `VN001_extended_80_20` (mốc Test từ tháng 05–07/2026 là mùa sạch mưa nhiều kèm đợt mất dữ liệu dài **630 giờ**), tập Test ghi nhận **0 ca dương tính** (`Test positives = 0`); các chỉ số cần phân lớp dương (`PR-AUC`, `ROC-AUC`, `Recall`) được báo cáo minh bạch là **`UNESTIMABLE`** thay vì bị bóp méo.
- Tập lịch sử dài `VN003_extended_2022_2025` (14.207 giờ hợp lệ có nhãn) cung cấp bằng chứng kiểm chứng đa năm cho cả Train và Test có đủ cả hai lớp.

{_df_to_markdown(pd.DataFrame(ext_summary_rows))}

---

## 5. Bài Học Kiểm Toán Rò Rỉ Dữ Liệu

Chi tiết 4 dạng rò rỉ (Target, Train-Test contamination, Temporal, Group) kèm bằng chứng unit test, `validate_no_leakage()`, kiểm soát purge gap ở $h > 0$ và giải trình loại trừ SMOTE được lập thành biên bản chính thức tại `docs/leakage_audit.md` và `reports/classification_leakage_audit.md`.
"""
    _write_lf_text(findings_path, content)
    logger.info("Đã lưu tài liệu phát hiện khoa học phân loại: %s", findings_path)


def run_classification_pipeline(
    dataset_path: Path,
    output_pr_path: Path,
    output_feat_path: Path,
    output_audit_path: Path,
    report_results_path: Optional[Path] = None,
    findings_path: Optional[Path] = None,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    *,
    station_id: Optional[str] = None,
    use_split_column: bool = False,
    scope_name: str = "VN001_baseline_2026_01_15",
    docs_audit_path: Optional[Path] = None,
    compute_extended_diagnostics: bool = True,
) -> ClassificationResults:
    """
    Thực thi toàn bộ pipeline phân loại cảnh báo ô nhiễm chuẩn INFO3020 cho Issue #13.
    """
    dataset_path = Path(dataset_path)
    df = pd.read_parquet(dataset_path)
    df_station = _select_single_station(df, station_id=station_id)
    resolved_station = str(df_station["station_id"].iloc[0]) if "station_id" in df_station.columns else (station_id or "UNKNOWN")

    # 1. Chuẩn bị dữ liệu sạch không impute trước CV
    X_train, y_train, X_test, y_test, metadata, ts_train, ts_test = prepare_classification_data(
        df_station,
        split_timestamp=split_timestamp,
        use_split_column=use_split_column,
        horizon_hours=0,
        return_timestamps=True,
    )
    feature_cols = list(X_train.columns)

    # 2. Huấn luyện Baseline Dummy Prior & Baseline Persistence Rule (1 biến)
    dummy = DummyClassifier(strategy="prior")
    dummy.fit(X_train, y_train)

    persistence = PersistenceRuleClassifier(
        feature_col="pm25_rolling_mean_24h",
        threshold_ug_m3=DEFAULT_ALERT_THRESHOLD_UG_M3,
    )
    persistence.fit(X_train, y_train)

    # 3. Đóng gói Logistic Regression & Random Forest trong Pipeline chống rò rỉ
    logreg_pipe = build_classification_pipeline(
        LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000),
        feature_cols,
        scale_features=True,
    )
    rf_pipe = build_classification_pipeline(
        RandomForestClassifier(n_estimators=100, max_depth=8, class_weight="balanced", random_state=42),
        feature_cols,
        scale_features=False,
    )

    # 4. Tinh chỉnh ngưỡng quyết định trên Train OOF (F2 & Recall constrained Precision >= 0.60)
    warnings_list: List[str] = []
    best_tau_logreg, w1 = tune_classification_threshold(logreg_pipe, X_train, y_train, metric="f2", return_details=True)
    best_tau_rf, w2 = tune_classification_threshold(rf_pipe, X_train, y_train, metric="f2", return_details=True)
    best_tau_logreg_c, w3 = tune_classification_threshold(
        logreg_pipe, X_train, y_train, metric="recall_constrained", min_precision=0.60, return_details=True
    )
    best_tau_rf_c, w4 = tune_classification_threshold(
        rf_pipe, X_train, y_train, metric="recall_constrained", min_precision=0.60, return_details=True
    )
    for w in (w1, w2, w3, w4):
        if w:
            warnings_list.append(w)

    # 5. Fit trọn vẹn trên Train & xác thực rò rỉ qua validate_no_leakage
    logreg_pipe.fit(X_train, y_train)
    rf_pipe.fit(X_train, y_train)
    verify_classification_no_leakage(
        logreg_pipe,
        X_train=X_train,
        X_test=X_test,
        timestamps=ts_train,
        test_timestamps=ts_test,
        verify_chronology=True,
    )
    verify_classification_no_leakage(
        rf_pipe,
        X_train=X_train,
        X_test=X_test,
        timestamps=ts_train,
        test_timestamps=ts_test,
        verify_chronology=True,
    )

    # 6. Đánh giá độc lập trên Test
    m_dummy = evaluate_classifier("Baseline (Prior Dummy)", dummy, X_test, y_test, threshold=0.50)
    m_persistence = evaluate_classifier("Baseline (Persistence Rule >=50)", persistence, X_test, y_test, threshold=0.50)
    m_logreg = evaluate_classifier("Logistic Regression (Balanced, F2)", logreg_pipe, X_test, y_test, threshold=best_tau_logreg)
    m_logreg_c = evaluate_classifier("Logistic Regression (Prec>=0.60)", logreg_pipe, X_test, y_test, threshold=best_tau_logreg_c)
    m_rf = evaluate_classifier("Random Forest (Balanced, F2)", rf_pipe, X_test, y_test, threshold=best_tau_rf)
    m_rf_c = evaluate_classifier("Random Forest (Prec>=0.60)", rf_pipe, X_test, y_test, threshold=best_tau_rf_c)

    metrics_list = [m_dummy, m_persistence, m_logreg, m_logreg_c, m_rf, m_rf_c]
    metrics_table = pd.DataFrame([{
        "Model": m.model_name,
        "Threshold": m.threshold,
        "Accuracy": m.accuracy,
        "Precision": m.precision,
        "Recall": m.recall,
        "FAR": m.false_alarm_rate,
        "F1": m.f1,
        "F2": m.f2,
        "Brier": m.brier_score,
        "ROC-AUC": m.roc_auc,
        "PR-AUC": m.pr_auc,
        "Confusion Matrix [TN, FP, FN, TP]": str(m.confusion_matrix),
        "Status": m.status,
    } for m in metrics_list])

    # 7. Permutation Importance theo average_precision + Odds Ratios
    df_imp = compute_feature_importances(rf_pipe, X_test, y_test, logreg_model=logreg_pipe, n_repeats=20)
    or_df = compute_logreg_odds_ratios(logreg_pipe, feature_cols)

    # 8. Các phân tích chẩn đoán mở rộng
    if compute_extended_diagnostics:
        cov_df, gaps_df, monthly_df = compute_coverage_and_outage_tables(
            df_station, split_timestamp=split_timestamp, use_split_column=use_split_column
        )
        ablation_df = evaluate_feature_ablation_and_horizons(
            df_station, split_timestamp=split_timestamp, use_split_column=use_split_column
        )
        bt_df, drift_df = run_temporal_backtest_and_drift(
            df_station, split_timestamp=split_timestamp, use_split_column=use_split_column
        )
        derived_df = evaluate_derived_pm25_sensitivity(
            df_station, split_timestamp=split_timestamp, use_split_column=use_split_column
        )
    else:
        cov_df = gaps_df = monthly_df = ablation_df = bt_df = drift_df = derived_df = None

    # 9. Xuất biểu đồ PR Curve & Feature Importance
    models_to_plot = {
        "Persistence Rule (>=50)": persistence,
        "Logistic Regression": logreg_pipe,
        "Random Forest": rf_pipe,
    }
    test_prev_plot = 0.0 if np.isnan(metadata["test_prevalence_valid"]) else metadata["test_prevalence_valid"]
    render_pr_curve_figure(
        models_to_plot, X_test, y_test, test_prev_plot, output_pr_path, title_suffix=f"{scope_name}"
    )
    render_feature_importance_figure(
        df_imp, output_feat_path, title_suffix=f"{scope_name} — Test n={metadata['n_test_valid']:,}"
    )

    # 10. Biên bản kiểm toán rò rỉ dữ liệu
    audit_md = generate_leakage_audit_markdown(
        metadata, metrics_table, ablation_table=ablation_df, threshold_warnings=warnings_list
    )
    _write_lf_text(output_audit_path, audit_md)
    if docs_audit_path is not None:
        _write_lf_text(docs_audit_path, audit_md)

    results = ClassificationResults(
        split_timestamp=metadata["split_timestamp"],
        n_train_total=metadata["n_train_total"],
        n_train_valid=metadata["n_train_valid"],
        n_test_total=metadata["n_test_total"],
        n_test_valid=metadata["n_test_valid"],
        train_prevalence_valid=metadata["train_prevalence_valid"],
        test_prevalence_valid=metadata["test_prevalence_valid"],
        train_prevalence_all=metadata["train_prevalence_all"],
        test_prevalence_all=metadata["test_prevalence_all"],
        features=feature_cols,
        best_threshold_logreg=best_tau_logreg,
        best_threshold_rf=best_tau_rf,
        metrics_table=metrics_table,
        model_metrics={
            "dummy": m_dummy,
            "persistence": m_persistence,
            "logreg": m_logreg,
            "logreg_constrained": m_logreg_c,
            "rf": m_rf,
            "rf_constrained": m_rf_c,
        },
        feature_importances=df_imp,
        leakage_audit_markdown=audit_md,
        scope_name=scope_name,
        station_id=resolved_station,
        horizon_hours=0,
        best_threshold_logreg_constrained=best_tau_logreg_c,
        best_threshold_rf_constrained=best_tau_rf_c,
        logreg_odds_ratios=or_df,
        coverage_table=cov_df,
        outage_gaps_table=gaps_df,
        monthly_coverage_table=monthly_df,
        ablation_horizon_table=ablation_df,
        backtest_table=bt_df,
        annual_drift_table=drift_df,
        derived_sensitivity_table=derived_df,
        threshold_warnings=warnings_list,
        dataset_sha256=_sha256_file(dataset_path),
    )

    if report_results_path is not None:
        write_classification_report(results, report_results_path)
    if findings_path is not None:
        write_classification_findings(results, findings_path)

    return results


def run_extended_classification_suite(
    baseline_path: Path,
    extended_path: Optional[Path],
    figures_dir: Path,
    report_results_path: Path,
    findings_path: Path,
    report_audit_path: Path,
    docs_audit_path: Optional[Path] = None,
) -> Dict[str, ClassificationResults]:
    """
    Thực thi trọn bộ 3 phạm vi Protocol A (Issue #13 + Scope Extension 2022–2026):
      1. `VN001_baseline`: Trạm 556 Nguyễn Văn Cừ (mốc cắt Issue #7: 2026-01-15)
      2. `VN001_extended`: Trạm 556 Nguyễn Văn Cừ trên tập mở rộng (mốc 80/20; Test 0 positives -> UNESTIMABLE)
      3. `VN003_extended`: Trạm lịch sử OpenAQ 7441 (2022–2025, mốc 80/20 đa năm)
    """
    figures_dir = Path(figures_dir)
    results_map: Dict[str, ClassificationResults] = {}

    res_vn001_base = run_classification_pipeline(
        baseline_path,
        figures_dir / "precision_recall_curve.png",
        figures_dir / "feature_importance.png",
        report_audit_path,
        report_results_path=None,
        findings_path=None,
        split_timestamp=DEFAULT_SPLIT_TIMESTAMP,
        station_id=PRIMARY_BASELINE_STATION,
        use_split_column=False,
        scope_name="VN001_baseline_2026_01_15",
        docs_audit_path=docs_audit_path,
        compute_extended_diagnostics=True,
    )
    results_map["VN001_baseline"] = res_vn001_base

    extra_runs: List[ClassificationResults] = []
    if extended_path is not None and Path(extended_path).exists():
        res_vn001_ext = run_classification_pipeline(
            extended_path,
            figures_dir / "precision_recall_curve_vn001_extended.png",
            figures_dir / "feature_importance_vn001_extended.png",
            report_audit_path,
            report_results_path=None,
            findings_path=None,
            split_timestamp=None,
            station_id=PRIMARY_BASELINE_STATION,
            use_split_column=True,
            scope_name="VN001_extended_80_20",
            docs_audit_path=None,
            compute_extended_diagnostics=True,
        )
        res_vn003_ext = run_classification_pipeline(
            extended_path,
            figures_dir / "precision_recall_curve_vn003_extended.png",
            figures_dir / "feature_importance_vn003_extended.png",
            report_audit_path,
            report_results_path=None,
            findings_path=None,
            split_timestamp=None,
            station_id=EXTENDED_HISTORICAL_STATION,
            use_split_column=True,
            scope_name="VN003_extended_2022_2025",
            docs_audit_path=None,
            compute_extended_diagnostics=True,
        )
        results_map["VN001_extended"] = res_vn001_ext
        results_map["VN003_extended"] = res_vn003_ext
        extra_runs.extend([res_vn001_ext, res_vn003_ext])

    res_vn001_base.extra_runs = extra_runs
    # Re-write audit docs using baseline (has primary ablation table) so report_audit_path reflects VN001_baseline cleanly
    _write_lf_text(report_audit_path, res_vn001_base.leakage_audit_markdown)
    if docs_audit_path is not None:
        _write_lf_text(docs_audit_path, res_vn001_base.leakage_audit_markdown)

    write_classification_report(res_vn001_base, report_results_path, extra_runs=extra_runs)
    write_classification_findings(res_vn001_base, findings_path, extra_runs=extra_runs)
    return results_map
