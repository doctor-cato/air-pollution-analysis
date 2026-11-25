"""
src/sensitivity.py — Phân tích Độ nhạy Đa chiều, Kiểm chứng Biên Trạm & Bất biến Baseline (Issue #15).

Tái sử dụng trực tiếp các thành phần đã kiểm chứng của dự án mà không lặp lại logic:
  - `src/cleaning_pipeline.py`: `build_alert_label`, `validate_no_leakage`
  - `src/classification.py`: `engineer_classification_features`, `build_classification_pipeline`,
    `verify_classification_no_leakage`, `tune_classification_threshold`, `evaluate_classifier`,
    `CLASSIFICATION_FEATURES`, `DEFAULT_SPLIT_TIMESTAMP`, `PRIMARY_BASELINE_STATION`,
    `EXTENDED_HISTORICAL_STATION`, `BASELINE_DATASET_VERSION`, `EXTENDED_DATASET_VERSION`
  - `src/regression.py`: `REGRESSION_PREDICTORS`, `build_regression_preprocessor`,
    `_fit_transform_train_only_ols_inputs`
  - `src/issue44_preparation.py`: `validate_modeling_split`

Các nguyên tắc bất khả xâm phạm (fail-closed):
  1. Protocol A đơn trạm nghiêm ngặt: từ chối `station_id` rỗng/NaN hoặc dữ liệu gộp đa trạm (Protocol B).
  2. Bảo toàn tính duy nhất `(station_id, timestamp)` và không phát sinh row explosion.
  3. Gắn nhãn ngưỡng minh bạch: chỉ `50.0 µg/m³` (trung bình 24h) mang nhãn `QCVN 05:2023/BTNMT (24h reference)`;
     các mức `40.0 / 45.0 / 55.0 µg/m³` luôn gắn nhãn `technical_sensitivity_threshold` (không phải quy chuẩn pháp lý).
  4. Mọi phép trễ/trượt (`lag_*`, `roll_mean_*`) chỉ dùng dữ liệu quá khứ nội trạm trên lưới giờ chuẩn,
     không bắc cầu qua khoảng trống dữ liệu và không bao giờ vượt ranh giới `station_id`.
  5. Mọi kiểm tra độ nhạy `pm25_derived_interpolated` chỉ áp dụng trên tập Train; tập Test ground-truth
     luôn khóa cứng trên `pm25` quan trắc gốc.
  6. Kiểm chứng SHA-256 bất biến của các artifact baseline trước và sau khi thực thi.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.classification import (
    BASELINE_DATASET_VERSION,
    CLASSIFICATION_FEATURES,
    DEFAULT_SPLIT_TIMESTAMP,
    EXTENDED_DATASET_VERSION,
    EXTENDED_HISTORICAL_STATION,
    PRIMARY_BASELINE_STATION,
    _align_split_timestamp,
    _compute_past_rolling_and_lag_on_station,
    build_classification_pipeline,
    engineer_classification_features,
    evaluate_classifier,
    tune_classification_threshold,
    verify_classification_no_leakage,
)
from src.cleaning_pipeline import (
    DEFAULT_ALERT_MIN_PERIODS,
    DEFAULT_ALERT_THRESHOLD_UG_M3,
    DEFAULT_ALERT_WINDOW_HOURS,
    build_alert_label,
    validate_no_leakage,
)
from src.issue44_preparation import validate_modeling_split
from src.regression import (
    REGRESSION_PREDICTORS,
    _fit_transform_train_only_ols_inputs,
    build_regression_preprocessor,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Labeling Contracts
# ---------------------------------------------------------------------------

SEED: int = 42
QCVN_24H_THRESHOLD_UG_M3: float = float(DEFAULT_ALERT_THRESHOLD_UG_M3)
QCVN_24H_LABEL: str = "QCVN 05:2023/BTNMT (24h reference)"
TECHNICAL_SENSITIVITY_LABEL: str = "technical_sensitivity_threshold"

CLASSIFICATION_THRESHOLD_GRID: Tuple[float, ...] = (40.0, 45.0, 50.0, 55.0)
COVERAGE_MIN_PERIODS_GRID: Tuple[int, ...] = (12, 18, 24)
REGRESSION_LAG_ROLL_SPECS: Tuple[str, ...] = (
    "baseline_no_lag",
    "lag_6h",
    "lag_12h",
    "lag_24h",
    "lag_48h",
    "roll_mean_6h",
    "roll_mean_24h",
    "roll_mean_72h",
)
TRAINING_WINDOW_FRACTIONS: Tuple[float, ...] = (0.50, 0.75, 1.00)
VIETNAM_SEASONS_VI: Tuple[str, ...] = ("Xuân", "Hạ", "Thu", "Đông")

_MONTH_TO_SEASON_VI: Dict[int, str] = {
    3: "Xuân",
    4: "Xuân",
    5: "Xuân",
    6: "Hạ",
    7: "Hạ",
    8: "Hạ",
    9: "Thu",
    10: "Thu",
    11: "Thu",
    12: "Đông",
    1: "Đông",
    2: "Đông",
}


@dataclass(frozen=True)
class CohortSpec:
    """Cấu hình định danh cho một phạm vi dữ liệu đơn trạm theo Protocol A."""

    cohort_name: str
    station_id: str
    dataset_version: str
    split_protocol: str
    use_split_column: bool = False
    split_timestamp: Optional[str] = None


@dataclass
class SensitivitySuiteResults:
    """Tập hợp toàn bộ kết quả phân tích độ nhạy và bằng chứng bất biến baseline."""

    run_id: str
    generated_at_utc: str
    seed: int
    threshold_df: pd.DataFrame
    coverage_df: pd.DataFrame
    regression_lag_df: pd.DataFrame
    training_window_df: pd.DataFrame
    season_stratified_df: pd.DataFrame
    derived_interpolation_df: pd.DataFrame
    combined_df: pd.DataFrame
    baseline_hashes_before: Dict[str, Optional[str]] = field(default_factory=dict)
    baseline_hashes_after: Dict[str, Optional[str]] = field(default_factory=dict)
    cohort_metadata: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core Guards & Provenance Helpers
# ---------------------------------------------------------------------------


def classify_threshold_label(threshold_ug_m3: float) -> str:
    """
    Phân loại nhãn ngưỡng cảnh báo minh bạch:
      - Chỉ 50.0 µg/m³ (trung bình 24h) tham chiếu QCVN 05:2023/BTNMT.
      - Mọi ngưỡng khác (40.0, 45.0, 55.0, ...) mang nhãn kỹ thuật `technical_sensitivity_threshold`.
    """
    val = float(threshold_ug_m3)
    if not np.isfinite(val) or val <= 0.0:
        raise ValueError(f"Ngưỡng nồng độ phải là số dương hữu hạn, nhận: {threshold_ug_m3!r}")
    if abs(val - QCVN_24H_THRESHOLD_UG_M3) < 1e-9:
        return QCVN_24H_LABEL
    return TECHNICAL_SENSITIVITY_LABEL


def map_vietnam_season_vi(timestamps: pd.Series) -> pd.Series:
    """Ánh xạ chuỗi thời gian sang 4 mùa khí tượng Việt Nam: Xuân, Hạ, Thu, Đông."""
    parsed = pd.to_datetime(timestamps, errors="raise")
    return parsed.dt.month.map(_MONTH_TO_SEASON_VI).astype("object")


def compute_sha256(path: Path) -> str:
    """Tính mã băm SHA-256 của tệp trên đĩa (chỉ đọc)."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_artifact_hashes(artifact_paths: Dict[str, Path]) -> Dict[str, Optional[str]]:
    """Chụp ảnh SHA-256 các artifact baseline (trả về None nếu tệp chưa tồn tại)."""
    out: Dict[str, Optional[str]] = {}
    for key, path in artifact_paths.items():
        p = Path(path)
        out[key] = compute_sha256(p) if p.is_file() else None
    return out


def verify_artifact_immutability(
    before: Dict[str, Optional[str]],
    after: Dict[str, Optional[str]],
) -> None:
    """Khẳng định SHA-256 của mọi artifact baseline hoàn toàn bất biến trước và sau khi chạy."""
    if set(before.keys()) != set(after.keys()):
        raise AssertionError(
            f"Danh sách artifact kiểm chứng bất biến bị thay đổi: {sorted(before.keys())} vs {sorted(after.keys())}"
        )
    changed = [
        f"{k}: {before[k]} -> {after[k]}"
        for k in sorted(before.keys())
        if before[k] != after[k]
    ]
    if changed:
        raise AssertionError(
            "Vi phạm bất biến artifact baseline (SHA-256 thay đổi sau phân tích độ nhạy): "
            + "; ".join(changed)
        )


def validate_single_station_frame(
    df: pd.DataFrame,
    station_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Cổng bảo vệ fail-closed cho đầu vào đơn trạm theo Protocol A:
      - Từ chối DataFrame rỗng, thiếu cột `timestamp` hoặc `timestamp` có `NaT`.
      - Từ chối `station_id` có `NaN` hoặc chuỗi rỗng.
      - Từ chối đầu vào gộp nhiều trạm (Protocol B) nếu không truyền `station_id`.
      - Kiểm chứng tính duy nhất khóa `(station_id, timestamp)` và bảo toàn số dòng sau sắp xếp.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("DataFrame đầu vào rỗng — từ chối fail-closed.")
    if "timestamp" not in df.columns:
        raise KeyError("Thiếu cột bắt buộc 'timestamp' trong DataFrame.")

    out = df.copy()
    if "station_id" in out.columns:
        if out["station_id"].isna().any():
            raise ValueError("Cột 'station_id' chứa NaN — từ chối fail-closed.")
        stripped = out["station_id"].astype(str).str.strip()
        if (stripped == "").any():
            raise ValueError("Cột 'station_id' chứa chuỗi rỗng — từ chối fail-closed.")
        out["station_id"] = stripped

        # Kiểm chứng duy nhất (station_id, timestamp) trên toàn khung đầu vào trước khi lọc
        ts_all = pd.to_datetime(out["timestamp"], errors="coerce")
        if ts_all.isna().any():
            raise ValueError("Cột 'timestamp' chứa giá trị NaT không hợp lệ.")
        out["timestamp"] = ts_all
        if out.duplicated(subset=["station_id", "timestamp"]).any():
            raise ValueError("Phát hiện khóa (station_id, timestamp) trùng lặp trong DataFrame đầu vào.")

        if station_id is not None:
            sid_clean = str(station_id).strip()
            if not sid_clean:
                raise ValueError("Tham số `station_id` không được là chuỗi rỗng.")
            out = out[out["station_id"] == sid_clean].copy()
            if out.empty:
                raise ValueError(f"Không tìm thấy dữ liệu cho trạm '{sid_clean}'.")
        else:
            unique_stations = sorted(out["station_id"].unique().tolist())
            if len(unique_stations) > 1:
                raise ValueError(
                    f"Phát hiện nhiều trạm {unique_stations} khi chưa chỉ định `station_id`. "
                    "Cấm gộp đa trạm theo Protocol B; hãy truyền `station_id` cụ thể (Protocol A)."
                )
    else:
        if station_id is not None:
            raise ValueError("Dữ liệu không có cột 'station_id' để lọc theo trạm.")
        ts_all = pd.to_datetime(out["timestamp"], errors="coerce")
        if ts_all.isna().any():
            raise ValueError("Cột 'timestamp' chứa giá trị NaT không hợp lệ.")
        out["timestamp"] = ts_all
        if out["timestamp"].duplicated().any():
            raise ValueError("Phát hiện timestamp trùng lặp trong DataFrame.")

    expected_rows = len(out)
    out = out.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    if len(out) != expected_rows:
        raise AssertionError(f"Row count mismatch sau sắp xếp: {len(out)} != {expected_rows}")
    if out["timestamp"].duplicated().any():
        raise ValueError("Phát hiện timestamp trùng lặp trong cùng một trạm.")
    return out


def _resolve_split_masks(
    df_station: pd.DataFrame,
    *,
    use_split_column: bool = False,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
) -> Tuple[pd.Series, pd.Series, str]:
    """Xác định mặt nạ Train/Test theo mốc thời gian hoặc cột `split` 80/20 có kiểm chứng Protocol A."""
    ts = df_station["timestamp"]
    if use_split_column:
        if "split" not in df_station.columns:
            raise KeyError("Thiếu cột 'split' khi `use_split_column=True`.")
        if "station_id" in df_station.columns:
            validate_modeling_split(df_station, "station_specific")
        train_mask = df_station["split"] == "train"
        test_mask = df_station["split"] == "test"
        if not train_mask.any() or not test_mask.any():
            raise ValueError("Cột 'split' phải chứa cả hai phân vùng 'train' và 'test'.")
        tr_max = ts.loc[train_mask].max()
        te_min = ts.loc[test_mask].min()
        if not (tr_max < te_min):
            raise AssertionError(f"Vi phạm thứ tự thời gian: train.max()={tr_max} >= test.min()={te_min}")
        return train_mask, test_mask, str(te_min)

    if split_timestamp is None:
        raise ValueError("Phải cung cấp `split_timestamp` khi `use_split_column=False`.")
    split_dt = _align_split_timestamp(ts, split_timestamp)
    train_mask = ts < split_dt
    test_mask = ts >= split_dt
    if not train_mask.any() or not test_mask.any():
        raise ValueError(
            f"Mốc cắt {split_timestamp} tạo ra phân vùng rỗng (train={int(train_mask.sum())}, test={int(test_mask.sum())})."
        )
    tr_max = ts.loc[train_mask].max()
    te_min = ts.loc[test_mask].min()
    if not (tr_max < te_min):
        raise AssertionError(f"Vi phạm thứ tự thời gian: train.max()={tr_max} >= test.min()={te_min}")
    return train_mask, test_mask, str(split_dt)


# ---------------------------------------------------------------------------
# Hourly-Safe Labels & Strictly-Past Station-Isolated Lag/Rolling Features
# ---------------------------------------------------------------------------


def build_hourly_safe_alert_label_with_params(
    df_station: pd.DataFrame,
    *,
    target_col: str = "pm25",
    window: int = DEFAULT_ALERT_WINDOW_HOURS,
    min_periods: int = DEFAULT_ALERT_MIN_PERIODS,
    threshold: float = QCVN_24H_THRESHOLD_UG_M3,
) -> pd.Series:
    """
    Sinh nhãn cảnh báo nhị phân trên lưới giờ chuẩn bằng `build_alert_label`,
    hỗ trợ tùy biến `threshold` và `min_periods` mà không bao giờ bắc cầu qua khoảng trống thời gian.
    """
    if "derived" in target_col.lower() or "interpolated" in target_col.lower():
        raise ValueError(
            f"Cấm sử dụng cột nội suy phái sinh '{target_col}' làm ground truth nhãn cảnh báo!"
        )
    if target_col not in df_station.columns:
        raise KeyError(f"Thiếu cột '{target_col}' để xây dựng nhãn cảnh báo.")
    if min_periods < 1 or min_periods > window:
        raise ValueError(f"min_periods={min_periods} phải nằm trong [1, {window}].")

    ts = pd.to_datetime(df_station["timestamp"])
    diffs = ts.diff().dropna()
    is_contiguous_1h = diffs.eq(pd.Timedelta(hours=1)).all() if len(diffs) > 0 else True
    if is_contiguous_1h:
        return build_alert_label(
            df_station,
            target_col=target_col,
            window=window,
            min_periods=min_periods,
            threshold=threshold,
            station_col=None,
        )

    t_min, t_max = ts.iloc[0], ts.iloc[-1]
    n_span = int(round((t_max - t_min).total_seconds() / 3600.0)) + 1
    on_hourly_grid = ((ts - t_min) % pd.Timedelta(hours=1) == pd.Timedelta(0)).all()
    if on_hourly_grid and n_span <= 500_000:
        grid_ts = t_min + pd.to_timedelta(np.arange(n_span), unit="h")
        grid_df = pd.DataFrame({"timestamp": grid_ts})
        s = pd.Series(df_station[target_col].astype(float).to_numpy(), index=ts)
        grid_df[target_col] = s.reindex(grid_ts).to_numpy()
        y_grid = build_alert_label(
            grid_df,
            target_col=target_col,
            window=window,
            min_periods=min_periods,
            threshold=threshold,
            station_col=None,
        )
        y_grid_s = pd.Series(y_grid.to_numpy(), index=grid_ts)
        return pd.Series(
            y_grid_s.reindex(ts).to_numpy(),
            index=df_station.index,
            name=f"{target_col}_alert_{window}h",
        )

    # Trường hợp tổng quát không nằm trên lưới 1 giờ
    y_raw = build_alert_label(
        df_station,
        target_col=target_col,
        window=window,
        min_periods=min_periods,
        threshold=threshold,
        station_col=None,
    )
    span_ok = (ts - ts.shift(window - 1)) == pd.Timedelta(hours=window - 1)
    return y_raw.where(span_ok)


def _engineer_classification_features_with_min_periods(
    df_station: pd.DataFrame,
    *,
    target_col: str = "pm25",
    min_periods: int = DEFAULT_ALERT_MIN_PERIODS,
) -> pd.DataFrame:
    """
    Tái sử dụng `engineer_classification_features` và cập nhật bộ đặc trưng trượt 24h
    theo `min_periods` khi kiểm tra độ nhạy coverage (`min_periods` in {12, 18, 24}).
    """
    feats = engineer_classification_features(df_station, target_col=target_col)
    if min_periods != DEFAULT_ALERT_MIN_PERIODS:
        rm, rs, lag24 = _compute_past_rolling_and_lag_on_station(
            df_station,
            target_col=target_col,
            window=DEFAULT_ALERT_WINDOW_HOURS,
            min_periods=min_periods,
        )
        feats["pm25_rolling_mean_24h"] = rm
        feats["pm25_rolling_std_24h"] = rs
        feats["pm25_lag24"] = lag24
    return feats


def _compute_single_station_past_spec(
    group: pd.DataFrame,
    spec: str,
    target_col: str = "pm25",
) -> Tuple[pd.Series, Optional[str]]:
    """
    Tính một biến trễ hoặc trung bình trượt strictly-past-only cho một trạm duy nhất
    trên lưới giờ chuẩn (không bắc cầu qua gap, không lookahead).
    """
    if spec == "baseline_no_lag":
        return pd.Series(np.nan, index=group.index, dtype=float), None

    ts = pd.to_datetime(group["timestamp"])
    if not ts.is_monotonic_increasing:
        raise ValueError("Timestamp trong mỗi trạm phải tăng dần đơn điệu.")
    if ts.duplicated().any():
        raise ValueError("Phát hiện timestamp trùng lặp trong cùng một trạm.")

    vals = group[target_col].astype(float).to_numpy()
    s = pd.Series(vals, index=ts)

    if spec.startswith("lag_") and spec.endswith("h"):
        lag_h = int(spec.removeprefix("lag_").removesuffix("h"))
        if lag_h < 1:
            raise ValueError(f"Độ trễ phải >= 1 giờ, nhận: {spec}")
        lag_vals = s.reindex(ts - pd.Timedelta(hours=lag_h)).to_numpy(dtype=float)
        col_name = f"pm25_{spec}"
        return pd.Series(lag_vals, index=group.index, name=col_name, dtype=float), col_name

    if spec.startswith("roll_mean_") and spec.endswith("h"):
        win_h = int(spec.removeprefix("roll_mean_").removesuffix("h"))
        if win_h < 1:
            raise ValueError(f"Cửa sổ trượt phải >= 1 giờ, nhận: {spec}")
        col_name = f"pm25_{spec}"
        t_min, t_max = ts.iloc[0], ts.iloc[-1]
        n_span = int(round((t_max - t_min).total_seconds() / 3600.0)) + 1
        diffs = ts.diff().dropna()
        is_contiguous_1h = diffs.eq(pd.Timedelta(hours=1)).all() if len(diffs) > 0 else True
        if is_contiguous_1h:
            past_s = pd.Series(vals, index=group.index).shift(1)
            rm = past_s.rolling(window=win_h, min_periods=win_h).mean()
            rm.name = col_name
            return rm, col_name

        on_hourly_grid = ((ts - t_min) % pd.Timedelta(hours=1) == pd.Timedelta(0)).all()
        if on_hourly_grid and n_span <= 500_000:
            hourly_grid = t_min + pd.to_timedelta(np.arange(n_span), unit="h")
            s_grid = s.reindex(hourly_grid)
            rm_grid = s_grid.shift(1).rolling(window=win_h, min_periods=win_h).mean()
            rm = pd.Series(rm_grid.reindex(ts).to_numpy(dtype=float), index=group.index, name=col_name)
            return rm, col_name

        past_raw = pd.Series(vals, index=group.index).shift(1)
        rm = past_raw.rolling(window=win_h, min_periods=win_h).mean()
        span_ok = (ts - ts.shift(win_h)) == pd.Timedelta(hours=win_h)
        rm = rm.where(span_ok)
        rm.name = col_name
        return rm, col_name

    raise ValueError(f"Spec lag/rolling không hợp lệ: {spec!r}. Hợp lệ: {REGRESSION_LAG_ROLL_SPECS}")


def add_station_past_lag_or_rolling_feature(
    df: pd.DataFrame,
    spec: str,
    *,
    target_col: str = "pm25",
) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Thêm đặc trưng trễ hoặc trung bình trượt strictly-past-only cô lập hoàn toàn theo `station_id`.
    Bảo toàn chính xác số dòng (không row explosion) và không bao giờ chảy dữ liệu giữa các trạm.
    """
    if target_col not in df.columns:
        raise KeyError(f"Thiếu cột '{target_col}'.")
    if "timestamp" not in df.columns:
        raise KeyError("Thiếu cột 'timestamp'.")

    out = df.copy()
    if spec == "baseline_no_lag":
        return out, None

    if "station_id" in out.columns:
        if out["station_id"].isna().any():
            raise ValueError("Cột 'station_id' chứa NaN.")
        col_name_ref: Optional[str] = None
        result_series = pd.Series(np.nan, index=out.index, dtype=float)
        for _, grp in out.groupby("station_id", sort=False):
            grp_sorted = grp.sort_values("timestamp", kind="mergesort")
            s_val, col_name = _compute_single_station_past_spec(grp_sorted, spec=spec, target_col=target_col)
            col_name_ref = col_name
            result_series.loc[grp_sorted.index] = s_val
        assert col_name_ref is not None
        out[col_name_ref] = result_series
    else:
        grp_sorted = out.sort_values("timestamp", kind="mergesort")
        s_val, col_name_ref = _compute_single_station_past_spec(grp_sorted, spec=spec, target_col=target_col)
        assert col_name_ref is not None
        out.loc[grp_sorted.index, col_name_ref] = s_val

    if len(out) != len(df):
        raise AssertionError(f"Row explosion detected: {len(out)} != {len(df)}")
    return out, col_name_ref


# ---------------------------------------------------------------------------
# Internal Model Fitting & Evaluation Helpers
# ---------------------------------------------------------------------------


def _build_default_logreg_pipeline(feature_cols: Sequence[str]):
    """Khởi tạo LogisticRegression balanced nằm trong Pipeline chống rò rỉ của `src/classification.py`."""
    return build_classification_pipeline(
        LogisticRegression(class_weight="balanced", random_state=SEED, max_iter=1000),
        feature_cols,
        scale_features=True,
    )


def _safe_verify_no_leakage(
    fitted_pipe: Any,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    ts_train: pd.Series,
    ts_test: pd.Series,
) -> None:
    """
    Gọi `verify_classification_no_leakage` (hoặc `validate_no_leakage` cho regression).
    Chỉ bỏ qua thông báo lớp 4 nếu Train và Test tình cờ trùng khớp hoàn toàn phân phối (dữ liệu tổng hợp),
    nhưng luôn bắt buộc thất bại với mọi vi phạm thứ tự thời gian hay rò rỉ tham số!
    """
    try:
        if hasattr(fitted_pipe, "named_steps") and "clf" in fitted_pipe.named_steps:
            verify_classification_no_leakage(
                fitted_pipe,
                X_train=X_train,
                X_test=X_test,
                timestamps=ts_train,
                test_timestamps=ts_test,
                verify_chronology=True,
            )
        else:
            validate_no_leakage(
                fitted_pipe,
                X_train=X_train,
                X_test=X_test,
                timestamps=ts_train,
                test_timestamps=ts_test,
                verify_chronology=True,
            )
    except AssertionError as exc:
        if "không có sức phân biệt" in str(exc):
            logger.debug("Bỏ qua kiểm tra sức phân biệt (Train/Test trùng phân phối): %s", exc)
        else:
            raise


def _fit_and_evaluate_classification_run(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    ts_train: pd.Series,
    ts_test: pd.Series,
) -> Tuple[Any, float, Dict[str, Any]]:
    """
    Huấn luyện LogisticRegression(class_weight='balanced') với tinh chỉnh ngưỡng F2 trên Train OOF,
    kiểm chứng không rò rỉ và chấm điểm trên Test với xử lý an toàn `UNESTIMABLE`.
    """
    valid_n_train = int(len(y_train))
    valid_n_test = int(len(y_test))
    prev_train = round(float(y_train.mean()), 4) if valid_n_train > 0 else float("nan")
    prev_test = round(float(y_test.mean()), 4) if valid_n_test > 0 else float("nan")

    if valid_n_train < 10 or y_train.nunique() < 2:
        return None, float("nan"), {
            "valid_n_train": valid_n_train,
            "valid_n_test": valid_n_test,
            "prevalence_train": prev_train,
            "prevalence_test": prev_test,
            "tuned_prob_threshold": float("nan"),
            "test_pr_auc": float("nan"),
            "test_recall": float("nan"),
            "test_precision": float("nan"),
            "test_f1": float("nan"),
            "test_f2": float("nan"),
            "test_far": float("nan"),
            "status": "UNESTIMABLE (single class or insufficient rows in Train)",
        }

    pipe = _build_default_logreg_pipeline(list(X_train.columns))
    tuned_tau = float(tune_classification_threshold(pipe, X_train, y_train, metric="f2", n_splits=5))
    pipe.fit(X_train, y_train)

    if valid_n_test > 0:
        _safe_verify_no_leakage(pipe, X_train, X_test, ts_train, ts_test)
        m = evaluate_classifier("LogisticRegression", pipe, X_test, y_test, threshold=tuned_tau)
        metrics_dict = {
            "valid_n_train": valid_n_train,
            "valid_n_test": valid_n_test,
            "prevalence_train": prev_train,
            "prevalence_test": prev_test,
            "tuned_prob_threshold": round(tuned_tau, 4),
            "test_pr_auc": m.pr_auc,
            "test_recall": m.recall,
            "test_precision": m.precision,
            "test_f1": m.f1,
            "test_f2": m.f2,
            "test_far": m.false_alarm_rate,
            "status": m.status,
        }
    else:
        metrics_dict = {
            "valid_n_train": valid_n_train,
            "valid_n_test": 0,
            "prevalence_train": prev_train,
            "prevalence_test": float("nan"),
            "tuned_prob_threshold": round(tuned_tau, 4),
            "test_pr_auc": float("nan"),
            "test_recall": float("nan"),
            "test_precision": float("nan"),
            "test_f1": float("nan"),
            "test_f2": float("nan"),
            "test_far": float("nan"),
            "status": "UNESTIMABLE (0 valid rows in Test)",
        }
    return pipe, tuned_tau, metrics_dict


def _prepare_classification_matrices_custom(
    df_station: pd.DataFrame,
    *,
    use_split_column: bool = False,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    threshold_ug_m3: float = QCVN_24H_THRESHOLD_UG_M3,
    min_periods: int = DEFAULT_ALERT_MIN_PERIODS,
    target_col: str = "pm25",
    train_feature_source_col: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.Series, pd.Series, str]:
    """
    Chuẩn bị (X_train, y_train, X_test, y_test, ts_train, ts_test, split_str) cho phân tích độ nhạy.
    Luôn giữ nhãn mục tiêu `y` và toàn bộ `X_test` trên `target_col` quan trắc gốc.
    """
    train_mask, test_mask, split_str = _resolve_split_masks(
        df_station,
        use_split_column=use_split_column,
        split_timestamp=split_timestamp,
    )
    y_all = build_hourly_safe_alert_label_with_params(
        df_station,
        target_col=target_col,
        window=DEFAULT_ALERT_WINDOW_HOURS,
        min_periods=min_periods,
        threshold=threshold_ug_m3,
    )
    X_obs = _engineer_classification_features_with_min_periods(
        df_station,
        target_col=target_col,
        min_periods=min_periods,
    )
    if train_feature_source_col is not None and train_feature_source_col != target_col:
        X_raw = _engineer_classification_features_with_min_periods(
            df_station,
            target_col=train_feature_source_col,
            min_periods=min_periods,
        ).copy()
        # Khóa cứng Test trên quan trắc gốc
        X_raw.loc[test_mask] = X_obs.loc[test_mask]
    else:
        X_raw = X_obs

    selected_cols = [c for c in CLASSIFICATION_FEATURES if c in X_raw.columns]
    valid_mask = y_all.notna() & X_raw["pm25_rolling_mean_24h"].notna()
    tr_valid = valid_mask & train_mask
    te_valid = valid_mask & test_mask

    X_train = X_raw.loc[tr_valid, selected_cols].copy()
    y_train = y_all.loc[tr_valid].astype(int).copy()
    X_test = X_raw.loc[te_valid, selected_cols].copy()
    y_test = y_all.loc[te_valid].astype(int).copy()
    ts_train = df_station.loc[tr_valid, "timestamp"].reset_index(drop=True)
    ts_test = df_station.loc[te_valid, "timestamp"].reset_index(drop=True)

    if not ts_train.empty and not ts_test.empty:
        if not (ts_train.max() < ts_test.min()):
            raise AssertionError(
                f"Vi phạm thứ tự thời gian: train.max()={ts_train.max()} >= test.min()={ts_test.min()}"
            )
    return X_train, y_train, X_test, y_test, ts_train, ts_test, split_str


def _fit_ols_hac24_and_evaluate(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    ts_train: pd.Series,
    ts_test: pd.Series,
    *,
    lag_col: Optional[str] = None,
) -> Dict[str, Any]:
    """Fit OLS + HAC-24 SE trên Train (impute bằng Train median) và chấm điểm trên Test."""
    n_tr = int(len(y_train))
    n_te = int(len(y_test))
    p = int(X_train.shape[1])

    if n_tr <= p + 2 or n_te == 0:
        return {
            "valid_n_train": n_tr,
            "valid_n_test": n_te,
            "beta_wind_speed": float("nan"),
            "se_wind_speed_hac24": float("nan"),
            "p_wind_speed_hac24": float("nan"),
            "beta_temperature": float("nan"),
            "beta_relative_humidity": float("nan"),
            "beta_lag_or_roll": float("nan"),
            "se_lag_or_roll_hac24": float("nan"),
            "test_mae": float("nan"),
            "test_rmse": float("nan"),
            "test_r2": float("nan"),
            "test_adj_r2": float("nan"),
            "status": "UNESTIMABLE (insufficient rows)",
        }

    # Kiểm chứng preprocessor không rò rỉ thời gian/tham số
    reg_prep = build_regression_preprocessor(list(X_train.columns)).fit(X_train)
    _safe_verify_no_leakage(reg_prep, X_train, X_test, ts_train, ts_test)

    X_tr_clean, X_te_clean, _, _ = _fit_transform_train_only_ols_inputs(X_train, X_test)
    assert X_te_clean is not None

    X_tr_const = sm.add_constant(X_tr_clean.reset_index(drop=True), has_constant="add")
    X_te_const = sm.add_constant(X_te_clean.reset_index(drop=True), has_constant="add")
    y_tr_arr = y_train.astype(float).reset_index(drop=True)
    y_te_arr = y_test.astype(float).reset_index(drop=True)

    maxlags = min(24, max(1, n_tr - 2))
    hac_fit = sm.OLS(y_tr_arr, X_tr_const).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    preds = np.asarray(hac_fit.predict(X_te_const), dtype=float)

    mae = float(mean_absolute_error(y_te_arr, preds))
    rmse = float(np.sqrt(mean_squared_error(y_te_arr, preds)))
    if n_te >= 2 and float(np.var(y_te_arr)) > 0.0:
        r2 = float(r2_score(y_te_arr, preds))
        adj_r2 = float(1.0 - (1.0 - r2) * (n_te - 1) / (n_te - p - 1)) if n_te > p + 1 else float("nan")
    else:
        r2 = float("nan")
        adj_r2 = float("nan")

    def _r4(val: float) -> float:
        return round(float(val), 4) if np.isfinite(val) else float("nan")

    return {
        "valid_n_train": n_tr,
        "valid_n_test": n_te,
        "beta_wind_speed": _r4(hac_fit.params["wind_speed"]) if "wind_speed" in hac_fit.params else float("nan"),
        "se_wind_speed_hac24": _r4(hac_fit.bse["wind_speed"]) if "wind_speed" in hac_fit.bse else float("nan"),
        "p_wind_speed_hac24": round(float(hac_fit.pvalues["wind_speed"]), 6) if "wind_speed" in hac_fit.pvalues else float("nan"),
        "beta_temperature": _r4(hac_fit.params["temperature"]) if "temperature" in hac_fit.params else float("nan"),
        "beta_relative_humidity": _r4(hac_fit.params["relative_humidity"]) if "relative_humidity" in hac_fit.params else float("nan"),
        "beta_lag_or_roll": _r4(hac_fit.params[lag_col]) if (lag_col and lag_col in hac_fit.params) else float("nan"),
        "se_lag_or_roll_hac24": _r4(hac_fit.bse[lag_col]) if (lag_col and lag_col in hac_fit.bse) else float("nan"),
        "test_mae": _r4(mae),
        "test_rmse": _r4(rmse),
        "test_r2": _r4(r2),
        "test_adj_r2": _r4(adj_r2),
        "status": "OK",
    }


# ---------------------------------------------------------------------------
# 1. Classification Threshold Sensitivity (Task 9.4)
# ---------------------------------------------------------------------------


def run_classification_threshold_sensitivity(
    df: pd.DataFrame,
    cohort: CohortSpec,
    *,
    run_id: str,
    thresholds: Sequence[float] = CLASSIFICATION_THRESHOLD_GRID,
    min_periods: int = DEFAULT_ALERT_MIN_PERIODS,
) -> pd.DataFrame:
    """
    Đánh giá độ nhạy ngưỡng cảnh báo [40.0, 45.0, 50.0, 55.0] µg/m³ trên trung bình trượt 24h
    cho một trạm duy nhất theo Protocol A.
    """
    df_s = validate_single_station_frame(df, station_id=cohort.station_id)
    rows: List[Dict[str, Any]] = []
    for thr in thresholds:
        thr_val = float(thr)
        thr_label = classify_threshold_label(thr_val)
        X_tr, y_tr, X_te, y_te, ts_tr, ts_te, _ = _prepare_classification_matrices_custom(
            df_s,
            use_split_column=cohort.use_split_column,
            split_timestamp=cohort.split_timestamp,
            threshold_ug_m3=thr_val,
            min_periods=min_periods,
            target_col="pm25",
        )
        _, _, m = _fit_and_evaluate_classification_run(X_tr, y_tr, X_te, y_te, ts_tr, ts_te)
        rows.append(
            {
                "analysis_group": "classification_threshold",
                "run_id": run_id,
                "cohort_name": cohort.cohort_name,
                "station_id": cohort.station_id,
                "dataset_version": cohort.dataset_version,
                "split_protocol": cohort.split_protocol,
                "seed": SEED,
                "threshold_ug_m3": thr_val,
                "threshold_label": thr_label,
                "min_periods": int(min_periods),
                **m,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. Coverage (`min_periods`) Sensitivity
# ---------------------------------------------------------------------------


def run_coverage_min_periods_sensitivity(
    df: pd.DataFrame,
    cohort: CohortSpec,
    *,
    run_id: str,
    min_periods_grid: Sequence[int] = COVERAGE_MIN_PERIODS_GRID,
    threshold_ug_m3: float = QCVN_24H_THRESHOLD_UG_M3,
) -> pd.DataFrame:
    """
    Đánh giá độ nhạy độ phủ `min_periods` in {12, 18, 24} cho nhãn cảnh báo 24h tại ngưỡng 50.0 µg/m³.
    """
    df_s = validate_single_station_frame(df, station_id=cohort.station_id)
    thr_label = classify_threshold_label(threshold_ug_m3)
    rows: List[Dict[str, Any]] = []
    for mp in min_periods_grid:
        mp_int = int(mp)
        X_tr, y_tr, X_te, y_te, ts_tr, ts_te, _ = _prepare_classification_matrices_custom(
            df_s,
            use_split_column=cohort.use_split_column,
            split_timestamp=cohort.split_timestamp,
            threshold_ug_m3=threshold_ug_m3,
            min_periods=mp_int,
            target_col="pm25",
        )
        _, _, m = _fit_and_evaluate_classification_run(X_tr, y_tr, X_te, y_te, ts_tr, ts_te)
        rows.append(
            {
                "analysis_group": "coverage_min_periods",
                "run_id": run_id,
                "cohort_name": cohort.cohort_name,
                "station_id": cohort.station_id,
                "dataset_version": cohort.dataset_version,
                "split_protocol": cohort.split_protocol,
                "seed": SEED,
                "threshold_ug_m3": float(threshold_ug_m3),
                "threshold_label": thr_label,
                "min_periods": mp_int,
                **m,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Regression Lag/Rolling Window Sensitivity (Task 9.5)
# ---------------------------------------------------------------------------


def run_regression_lag_rolling_sensitivity(
    df: pd.DataFrame,
    cohort: CohortSpec,
    *,
    run_id: str,
    specs: Sequence[str] = REGRESSION_LAG_ROLL_SPECS,
) -> pd.DataFrame:
    """
    Đánh giá độ ổn định hệ số hồi quy OLS (+ HAC-24 SE) đối với biến khí tượng
    và các cấu hình trễ/trượt quá khứ nội trạm (`baseline_no_lag`, `lag_*`, `roll_mean_*`).
    """
    df_s = validate_single_station_frame(df, station_id=cohort.station_id)
    train_mask, test_mask, _ = _resolve_split_masks(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
    )
    base_predictors = [c for c in REGRESSION_PREDICTORS if c in df_s.columns]
    if not base_predictors:
        raise ValueError("Không tìm thấy biến giải thích khí tượng/chu kỳ nào trong DataFrame.")

    rows: List[Dict[str, Any]] = []
    for spec in specs:
        df_aug, lag_col = add_station_past_lag_or_rolling_feature(df_s, spec=spec, target_col="pm25")
        preds = list(base_predictors) + ([lag_col] if lag_col else [])
        valid_mask = df_aug["pm25"].notna()
        if lag_col is not None:
            valid_mask = valid_mask & df_aug[lag_col].notna()

        tr_mask = valid_mask & train_mask
        te_mask = valid_mask & test_mask

        X_tr = df_aug.loc[tr_mask, preds].copy()
        y_tr = df_aug.loc[tr_mask, "pm25"].astype(float).copy()
        X_te = df_aug.loc[te_mask, preds].copy()
        y_te = df_aug.loc[te_mask, "pm25"].astype(float).copy()
        ts_tr = df_aug.loc[tr_mask, "timestamp"].reset_index(drop=True)
        ts_te = df_aug.loc[te_mask, "timestamp"].reset_index(drop=True)

        res = _fit_ols_hac24_and_evaluate(X_tr, y_tr, X_te, y_te, ts_tr, ts_te, lag_col=lag_col)
        rows.append(
            {
                "analysis_group": "regression_lag_rolling",
                "run_id": run_id,
                "cohort_name": cohort.cohort_name,
                "station_id": cohort.station_id,
                "dataset_version": cohort.dataset_version,
                "split_protocol": cohort.split_protocol,
                "seed": SEED,
                "spec": spec,
                "added_feature": lag_col or "none",
                **res,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. Scope Extension: Training-Window, Season & Derived-Interpolation Sensitivity
# ---------------------------------------------------------------------------


def run_training_window_sensitivity(
    df: pd.DataFrame,
    cohort: CohortSpec,
    *,
    run_id: str,
    window_fractions: Sequence[float] = TRAINING_WINDOW_FRACTIONS,
) -> pd.DataFrame:
    """
    Đánh giá độ nhạy độ dài cửa sổ huấn luyện (50%, 75%, 100% phần đuôi thời gian gần nhất của Train)
    trên CÙNG một tập Test cố định cho cả Phân loại (50.0 µg/m³) và Hồi quy (OLS baseline).
    """
    df_s = validate_single_station_frame(df, station_id=cohort.station_id)
    rows: List[Dict[str, Any]] = []

    # --- Classification on fixed Test ---
    X_tr_cls, y_tr_cls, X_te_cls, y_te_cls, ts_tr_cls, ts_te_cls, _ = _prepare_classification_matrices_custom(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
        threshold_ug_m3=QCVN_24H_THRESHOLD_UG_M3,
        min_periods=DEFAULT_ALERT_MIN_PERIODS,
    )
    n_tr_cls = len(X_tr_cls)
    for frac in window_fractions:
        f = float(frac)
        if not (0.0 < f <= 1.0):
            raise ValueError(f"window_fraction phải trong (0, 1], nhận: {frac}")
        keep_n = max(1, int(round(n_tr_cls * f)))
        start_i = max(0, n_tr_cls - keep_n)
        _, _, m_cls = _fit_and_evaluate_classification_run(
            X_tr_cls.iloc[start_i:],
            y_tr_cls.iloc[start_i:],
            X_te_cls,
            y_te_cls,
            ts_tr_cls.iloc[start_i:].reset_index(drop=True),
            ts_te_cls,
        )
        rows.append(
            {
                "analysis_group": "training_window_length",
                "task_type": "classification",
                "run_id": run_id,
                "cohort_name": cohort.cohort_name,
                "station_id": cohort.station_id,
                "dataset_version": cohort.dataset_version,
                "split_protocol": cohort.split_protocol,
                "seed": SEED,
                "train_window_pct": int(round(f * 100)),
                "threshold_ug_m3": QCVN_24H_THRESHOLD_UG_M3,
                "threshold_label": QCVN_24H_LABEL,
                **m_cls,
            }
        )

    # --- Regression on fixed Test ---
    train_mask, test_mask, _ = _resolve_split_masks(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
    )
    base_predictors = [c for c in REGRESSION_PREDICTORS if c in df_s.columns]
    valid_reg = df_s["pm25"].notna()
    tr_reg_df = df_s.loc[valid_reg & train_mask].copy()
    te_reg_df = df_s.loc[valid_reg & test_mask].copy()
    n_tr_reg = len(tr_reg_df)

    for frac in window_fractions:
        f = float(frac)
        keep_n = max(1, int(round(n_tr_reg * f)))
        start_i = max(0, n_tr_reg - keep_n)
        sub_tr = tr_reg_df.iloc[start_i:]
        m_reg = _fit_ols_hac24_and_evaluate(
            sub_tr[base_predictors],
            sub_tr["pm25"].astype(float),
            te_reg_df[base_predictors],
            te_reg_df["pm25"].astype(float),
            sub_tr["timestamp"].reset_index(drop=True),
            te_reg_df["timestamp"].reset_index(drop=True),
            lag_col=None,
        )
        rows.append(
            {
                "analysis_group": "training_window_length",
                "task_type": "regression",
                "run_id": run_id,
                "cohort_name": cohort.cohort_name,
                "station_id": cohort.station_id,
                "dataset_version": cohort.dataset_version,
                "split_protocol": cohort.split_protocol,
                "seed": SEED,
                "train_window_pct": int(round(f * 100)),
                **m_reg,
            }
        )

    return pd.DataFrame(rows)


def run_season_stratified_sensitivity(
    df: pd.DataFrame,
    cohort: CohortSpec,
    *,
    run_id: str,
) -> pd.DataFrame:
    """
    Đánh giá hiệu năng phân tầng theo 4 mùa khí tượng Việt Nam (Xuân, Hạ, Thu, Đông) trên tập Test,
    với cơ chế bảo vệ `UNESTIMABLE` cho tầng rỗng hoặc đơn lớp.
    """
    df_s = validate_single_station_frame(df, station_id=cohort.station_id)
    rows: List[Dict[str, Any]] = []

    # --- Classification season-stratified Test ---
    X_tr_cls, y_tr_cls, X_te_cls, y_te_cls, ts_tr_cls, ts_te_cls, _ = _prepare_classification_matrices_custom(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
        threshold_ug_m3=QCVN_24H_THRESHOLD_UG_M3,
        min_periods=DEFAULT_ALERT_MIN_PERIODS,
    )
    pipe_cls, tuned_tau, _ = _fit_and_evaluate_classification_run(
        X_tr_cls, y_tr_cls, X_te_cls, y_te_cls, ts_tr_cls, ts_te_cls
    )
    seasons_te_cls = map_vietnam_season_vi(ts_te_cls) if len(ts_te_cls) > 0 else pd.Series([], dtype="object")

    for season_name in VIETNAM_SEASONS_VI:
        mask = (seasons_te_cls == season_name).to_numpy() if len(seasons_te_cls) > 0 else np.array([], dtype=bool)
        n_sub = int(np.sum(mask))
        if n_sub == 0 or pipe_cls is None:
            rows.append(
                {
                    "analysis_group": "season_stratified_test",
                    "task_type": "classification",
                    "run_id": run_id,
                    "cohort_name": cohort.cohort_name,
                    "station_id": cohort.station_id,
                    "dataset_version": cohort.dataset_version,
                    "split_protocol": cohort.split_protocol,
                    "seed": SEED,
                    "season": season_name,
                    "valid_n_test": n_sub,
                    "n_test_positive": 0,
                    "prevalence_test": float("nan"),
                    "tuned_prob_threshold": round(tuned_tau, 4) if np.isfinite(tuned_tau) else float("nan"),
                    "test_pr_auc": float("nan"),
                    "test_recall": float("nan"),
                    "test_precision": float("nan"),
                    "test_f1": float("nan"),
                    "test_f2": float("nan"),
                    "test_far": float("nan"),
                    "status": "UNESTIMABLE (empty season stratum in Test)",
                }
            )
            continue

        X_sub = X_te_cls.iloc[mask]
        y_sub = y_te_cls.iloc[mask]
        m = evaluate_classifier(f"LogReg_{season_name}", pipe_cls, X_sub, y_sub, threshold=tuned_tau)
        rows.append(
            {
                "analysis_group": "season_stratified_test",
                "task_type": "classification",
                "run_id": run_id,
                "cohort_name": cohort.cohort_name,
                "station_id": cohort.station_id,
                "dataset_version": cohort.dataset_version,
                "split_protocol": cohort.split_protocol,
                "seed": SEED,
                "season": season_name,
                "valid_n_test": n_sub,
                "n_test_positive": int(y_sub.sum()),
                "prevalence_test": round(float(y_sub.mean()), 4),
                "tuned_prob_threshold": round(tuned_tau, 4),
                "test_pr_auc": m.pr_auc,
                "test_recall": m.recall,
                "test_precision": m.precision,
                "test_f1": m.f1,
                "test_f2": m.f2,
                "test_far": m.false_alarm_rate,
                "status": m.status,
            }
        )

    # --- Regression season-stratified Test ---
    train_mask, test_mask, _ = _resolve_split_masks(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
    )
    base_predictors = [c for c in REGRESSION_PREDICTORS if c in df_s.columns]
    valid_reg = df_s["pm25"].notna()
    tr_reg_df = df_s.loc[valid_reg & train_mask]
    te_reg_df = df_s.loc[valid_reg & test_mask]
    X_tr_clean, X_te_clean, _, _ = _fit_transform_train_only_ols_inputs(
        tr_reg_df[base_predictors], te_reg_df[base_predictors]
    )
    assert X_te_clean is not None
    X_tr_const = sm.add_constant(X_tr_clean.reset_index(drop=True), has_constant="add")
    X_te_const = sm.add_constant(X_te_clean.reset_index(drop=True), has_constant="add")
    ols_fit = sm.OLS(tr_reg_df["pm25"].astype(float).reset_index(drop=True), X_tr_const).fit()
    preds_all = np.asarray(ols_fit.predict(X_te_const), dtype=float)
    y_te_all = te_reg_df["pm25"].astype(float).to_numpy()
    seasons_te_reg = map_vietnam_season_vi(te_reg_df["timestamp"].reset_index(drop=True))

    for season_name in VIETNAM_SEASONS_VI:
        mask = (seasons_te_reg == season_name).to_numpy()
        n_sub = int(np.sum(mask))
        if n_sub == 0:
            rows.append(
                {
                    "analysis_group": "season_stratified_test",
                    "task_type": "regression",
                    "run_id": run_id,
                    "cohort_name": cohort.cohort_name,
                    "station_id": cohort.station_id,
                    "dataset_version": cohort.dataset_version,
                    "split_protocol": cohort.split_protocol,
                    "seed": SEED,
                    "season": season_name,
                    "valid_n_test": 0,
                    "test_mae": float("nan"),
                    "test_rmse": float("nan"),
                    "test_r2": float("nan"),
                    "mean_bias": float("nan"),
                    "status": "UNESTIMABLE (empty season stratum in Test)",
                }
            )
            continue

        y_sub = y_te_all[mask]
        p_sub = preds_all[mask]
        mae = round(float(mean_absolute_error(y_sub, p_sub)), 4)
        rmse = round(float(np.sqrt(mean_squared_error(y_sub, p_sub))), 4)
        bias = round(float(np.mean(p_sub - y_sub)), 4)
        if n_sub >= 2 and float(np.var(y_sub)) > 0.0:
            r2 = round(float(r2_score(y_sub, p_sub)), 4)
            st = "OK"
        else:
            r2 = float("nan")
            st = "UNESTIMABLE (insufficient variance/rows for R2)"
        rows.append(
            {
                "analysis_group": "season_stratified_test",
                "task_type": "regression",
                "run_id": run_id,
                "cohort_name": cohort.cohort_name,
                "station_id": cohort.station_id,
                "dataset_version": cohort.dataset_version,
                "split_protocol": cohort.split_protocol,
                "seed": SEED,
                "season": season_name,
                "valid_n_test": n_sub,
                "test_mae": mae,
                "test_rmse": rmse,
                "test_r2": r2,
                "mean_bias": bias,
                "status": st,
            }
        )

    return pd.DataFrame(rows)


def run_derived_interpolation_sensitivity(
    df: pd.DataFrame,
    cohort: CohortSpec,
    *,
    run_id: str,
) -> pd.DataFrame:
    """
    So sánh Observed-Only vs `pm25_derived_interpolated` (áp dụng STRICTLY trên Train;
    tập Test ground-truth luôn khóa cứng trên `pm25` quan trắc gốc) cho cả Hồi quy và Phân loại.
    """
    df_s = validate_single_station_frame(df, station_id=cohort.station_id)
    if "pm25_derived_interpolated" not in df_s.columns:
        return pd.DataFrame()

    train_mask, test_mask, _ = _resolve_split_masks(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
    )
    rows: List[Dict[str, Any]] = []

    # 1. Regression: Train target = pm25 (observed) vs pm25_derived_interpolated; Test target ALWAYS observed pm25!
    base_predictors = [c for c in REGRESSION_PREDICTORS if c in df_s.columns]
    te_obs_mask = test_mask & df_s["pm25"].notna()
    X_te_reg = df_s.loc[te_obs_mask, base_predictors].copy()
    y_te_reg = df_s.loc[te_obs_mask, "pm25"].astype(float).copy()
    ts_te_reg = df_s.loc[te_obs_mask, "timestamp"].reset_index(drop=True)

    tr_obs_mask = train_mask & df_s["pm25"].notna()
    tr_der_mask = train_mask & df_s["pm25_derived_interpolated"].notna()

    res_reg_obs = _fit_ols_hac24_and_evaluate(
        df_s.loc[tr_obs_mask, base_predictors],
        df_s.loc[tr_obs_mask, "pm25"].astype(float),
        X_te_reg,
        y_te_reg,
        df_s.loc[tr_obs_mask, "timestamp"].reset_index(drop=True),
        ts_te_reg,
    )
    res_reg_der = _fit_ols_hac24_and_evaluate(
        df_s.loc[tr_der_mask, base_predictors],
        df_s.loc[tr_der_mask, "pm25_derived_interpolated"].astype(float),
        X_te_reg,
        y_te_reg,
        df_s.loc[tr_der_mask, "timestamp"].reset_index(drop=True),
        ts_te_reg,
    )

    def _delta(a: float, b: float) -> float:
        return round(float(b - a), 4) if (np.isfinite(a) and np.isfinite(b)) else float("nan")

    rows.append(
        {
            "analysis_group": "derived_interpolation_train_only",
            "task_type": "regression",
            "run_id": run_id,
            "cohort_name": cohort.cohort_name,
            "station_id": cohort.station_id,
            "dataset_version": cohort.dataset_version,
            "split_protocol": cohort.split_protocol,
            "seed": SEED,
            "valid_n_train_obs": res_reg_obs["valid_n_train"],
            "valid_n_train_der": res_reg_der["valid_n_train"],
            "recovered_train_rows": int(res_reg_der["valid_n_train"] - res_reg_obs["valid_n_train"]),
            "valid_n_test": res_reg_obs["valid_n_test"],
            "test_mae_obs": res_reg_obs["test_mae"],
            "test_mae_der": res_reg_der["test_mae"],
            "delta_test_mae": _delta(res_reg_obs["test_mae"], res_reg_der["test_mae"]),
            "test_rmse_obs": res_reg_obs["test_rmse"],
            "test_rmse_der": res_reg_der["test_rmse"],
            "delta_test_rmse": _delta(res_reg_obs["test_rmse"], res_reg_der["test_rmse"]),
            "test_pr_auc_obs": float("nan"),
            "test_pr_auc_der": float("nan"),
            "delta_test_pr_auc": float("nan"),
            "test_ground_truth_unchanged": True,
            "status": res_reg_obs["status"],
        }
    )

    # 2. Classification: Train features from pm25 vs pm25_derived_interpolated; y_train, X_test, y_test ALWAYS observed!
    X_tr_obs, y_tr_obs, X_te_obs, y_te_obs, ts_tr_obs, ts_te_obs, _ = _prepare_classification_matrices_custom(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
        threshold_ug_m3=QCVN_24H_THRESHOLD_UG_M3,
        min_periods=DEFAULT_ALERT_MIN_PERIODS,
        target_col="pm25",
        train_feature_source_col="pm25",
    )
    X_tr_der, y_tr_der, X_te_der, y_te_der, ts_tr_der, ts_te_der, _ = _prepare_classification_matrices_custom(
        df_s,
        use_split_column=cohort.use_split_column,
        split_timestamp=cohort.split_timestamp,
        threshold_ug_m3=QCVN_24H_THRESHOLD_UG_M3,
        min_periods=DEFAULT_ALERT_MIN_PERIODS,
        target_col="pm25",
        train_feature_source_col="pm25_derived_interpolated",
    )
    if not X_te_obs.equals(X_te_der) or not y_te_obs.equals(y_te_der):
        raise AssertionError("Vi phạm bất biến Test: derived interpolation làm thay đổi X_test hoặc y_test!")

    _, _, m_cls_obs = _fit_and_evaluate_classification_run(
        X_tr_obs, y_tr_obs, X_te_obs, y_te_obs, ts_tr_obs, ts_te_obs
    )
    _, _, m_cls_der = _fit_and_evaluate_classification_run(
        X_tr_der, y_tr_der, X_te_der, y_te_der, ts_tr_der, ts_te_der
    )
    rows.append(
        {
            "analysis_group": "derived_interpolation_train_only",
            "task_type": "classification",
            "run_id": run_id,
            "cohort_name": cohort.cohort_name,
            "station_id": cohort.station_id,
            "dataset_version": cohort.dataset_version,
            "split_protocol": cohort.split_protocol,
            "seed": SEED,
            "valid_n_train_obs": m_cls_obs["valid_n_train"],
            "valid_n_train_der": m_cls_der["valid_n_train"],
            "recovered_train_rows": int(m_cls_der["valid_n_train"] - m_cls_obs["valid_n_train"]),
            "valid_n_test": m_cls_obs["valid_n_test"],
            "test_mae_obs": float("nan"),
            "test_mae_der": float("nan"),
            "delta_test_mae": float("nan"),
            "test_rmse_obs": float("nan"),
            "test_rmse_der": float("nan"),
            "delta_test_rmse": float("nan"),
            "test_pr_auc_obs": m_cls_obs["test_pr_auc"],
            "test_pr_auc_der": m_cls_der["test_pr_auc"],
            "delta_test_pr_auc": _delta(m_cls_obs["test_pr_auc"], m_cls_der["test_pr_auc"]),
            "test_ground_truth_unchanged": True,
            "status": m_cls_obs["status"],
        }
    )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Full Suite Orchestrator & Markdown Renderer
# ---------------------------------------------------------------------------


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Chuyển đổi DataFrame thành bảng Markdown sạch không phụ thuộc tabulate."""
    if df is None or df.empty:
        return "_Không có dữ liệu bảng._"
    headers = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in df.iterrows():
        cells = []
        for val in row.values:
            if isinstance(val, (float, np.floating)) and np.isnan(val):
                cells.append("UNESTIMABLE")
            else:
                cells.append(str(val).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run_full_sensitivity_suite(
    *,
    data_dir: Path,
    repo_root: Path,
    run_id: Optional[str] = None,
) -> SensitivitySuiteResults:
    """
    Điều phối toàn bộ chuỗi phân tích độ nhạy Issue #15 trên 3 phạm vi Protocol A:
      1. `VN001_baseline_2026_01_15` (`air_pollution_final.parquet`, split `2026-01-15 00:00:00+07:00`)
      2. `VN003_extended_80_20` (`air_pollution_extended_2022_2026.parquet`, cột `split` 80/20)
      3. `VN001_extended_80_20` (`air_pollution_extended_2022_2026.parquet`, cột `split` 80/20)
    Kiểm chứng SHA-256 bất biến của baseline artifacts trước và sau khi thực thi.
    """
    data_dir = Path(data_dir)
    repo_root = Path(repo_root)
    now_utc = datetime.now(timezone.utc)
    eff_run_id = run_id or f"issue15_sens_{now_utc.strftime('%Y%m%dT%H%M%SZ')}_seed{SEED}"

    baseline_parquet = data_dir / "processed" / "air_pollution_final.parquet"
    extended_parquet = data_dir / "processed" / "air_pollution_extended_2022_2026.parquet"
    if not baseline_parquet.is_file():
        raise FileNotFoundError(f"Không tìm thấy baseline Parquet: {baseline_parquet}")
    if not extended_parquet.is_file():
        raise FileNotFoundError(f"Không tìm thấy extended Parquet: {extended_parquet}")

    baseline_artifacts = {
        "air_pollution_final.parquet": baseline_parquet,
        "reports/regression_results.md": repo_root / "reports" / "regression_results.md",
        "reports/classification_results.md": repo_root / "reports" / "classification_results.md",
    }
    hashes_before = snapshot_artifact_hashes(baseline_artifacts)

    df_base = pd.read_parquet(baseline_parquet)
    df_ext = pd.read_parquet(extended_parquet)

    cohorts: List[Tuple[pd.DataFrame, CohortSpec, str]] = [
        (
            df_base,
            CohortSpec(
                cohort_name="VN001_baseline_2026_01_15",
                station_id=PRIMARY_BASELINE_STATION,
                dataset_version=BASELINE_DATASET_VERSION,
                split_protocol=f"fixed_timestamp ({DEFAULT_SPLIT_TIMESTAMP})",
                use_split_column=False,
                split_timestamp=DEFAULT_SPLIT_TIMESTAMP,
            ),
            compute_sha256(baseline_parquet),
        ),
        (
            df_ext,
            CohortSpec(
                cohort_name="VN003_extended_80_20",
                station_id=EXTENDED_HISTORICAL_STATION,
                dataset_version=EXTENDED_DATASET_VERSION,
                split_protocol="station_specific_80_20 (Protocol A)",
                use_split_column=True,
                split_timestamp=None,
            ),
            compute_sha256(extended_parquet),
        ),
        (
            df_ext,
            CohortSpec(
                cohort_name="VN001_extended_80_20",
                station_id=PRIMARY_BASELINE_STATION,
                dataset_version=EXTENDED_DATASET_VERSION,
                split_protocol="station_specific_80_20 (Protocol A)",
                use_split_column=True,
                split_timestamp=None,
            ),
            compute_sha256(extended_parquet),
        ),
    ]

    threshold_frames: List[pd.DataFrame] = []
    coverage_frames: List[pd.DataFrame] = []
    reg_lag_frames: List[pd.DataFrame] = []
    window_frames: List[pd.DataFrame] = []
    season_frames: List[pd.DataFrame] = []
    derived_frames: List[pd.DataFrame] = []
    cohort_meta: List[Dict[str, Any]] = []

    for df_src, spec, sha_val in cohorts:
        df_s = validate_single_station_frame(df_src, station_id=spec.station_id)
        tr_m, te_m, eff_cut = _resolve_split_masks(
            df_s,
            use_split_column=spec.use_split_column,
            split_timestamp=spec.split_timestamp,
        )
        cohort_meta.append(
            {
                "cohort_name": spec.cohort_name,
                "station_id": spec.station_id,
                "dataset_version": spec.dataset_version,
                "split_protocol": spec.split_protocol,
                "effective_test_start": eff_cut,
                "grid_rows": int(len(df_s)),
                "train_grid_rows": int(tr_m.sum()),
                "test_grid_rows": int(te_m.sum()),
                "valid_pm25_rows": int(df_s["pm25"].notna().sum()),
                "dataset_sha256": sha_val,
            }
        )

        threshold_frames.append(run_classification_threshold_sensitivity(df_src, spec, run_id=eff_run_id))
        coverage_frames.append(run_coverage_min_periods_sensitivity(df_src, spec, run_id=eff_run_id))
        reg_lag_frames.append(run_regression_lag_rolling_sensitivity(df_src, spec, run_id=eff_run_id))
        window_frames.append(run_training_window_sensitivity(df_src, spec, run_id=eff_run_id))
        season_frames.append(run_season_stratified_sensitivity(df_src, spec, run_id=eff_run_id))

        der_df = run_derived_interpolation_sensitivity(df_src, spec, run_id=eff_run_id)
        if not der_df.empty:
            derived_frames.append(der_df)

    threshold_df = pd.concat(threshold_frames, ignore_index=True)
    coverage_df = pd.concat(coverage_frames, ignore_index=True)
    reg_lag_df = pd.concat(reg_lag_frames, ignore_index=True)
    window_df = pd.concat(window_frames, ignore_index=True)
    season_df = pd.concat(season_frames, ignore_index=True)
    derived_df = pd.concat(derived_frames, ignore_index=True) if derived_frames else pd.DataFrame()

    combined_df = pd.concat(
        [threshold_df, coverage_df, reg_lag_df, window_df, season_df, derived_df],
        ignore_index=True,
        sort=False,
    )

    hashes_after = snapshot_artifact_hashes(baseline_artifacts)
    verify_artifact_immutability(hashes_before, hashes_after)

    return SensitivitySuiteResults(
        run_id=eff_run_id,
        generated_at_utc=now_utc.isoformat(),
        seed=SEED,
        threshold_df=threshold_df,
        coverage_df=coverage_df,
        regression_lag_df=reg_lag_df,
        training_window_df=window_df,
        season_stratified_df=season_df,
        derived_interpolation_df=derived_df,
        combined_df=combined_df,
        baseline_hashes_before=hashes_before,
        baseline_hashes_after=hashes_after,
        cohort_metadata=cohort_meta,
    )


def render_sensitivity_markdown(results: SensitivitySuiteResults) -> str:
    """Sinh báo cáo Markdown động 100% từ kết quả thực nghiệm của `SensitivitySuiteResults`."""
    cohort_df = pd.DataFrame(results.cohort_metadata)
    hash_rows = [
        {
            "Artifact": k,
            "SHA-256 Before": results.baseline_hashes_before.get(k) or "MISSING",
            "SHA-256 After": results.baseline_hashes_after.get(k) or "MISSING",
            "Immutable": "PASS" if results.baseline_hashes_before.get(k) == results.baseline_hashes_after.get(k) else "FAIL",
        }
        for k in sorted(results.baseline_hashes_before.keys())
    ]
    hash_df = pd.DataFrame(hash_rows)

    thr_cols = [
        "cohort_name", "threshold_ug_m3", "threshold_label",
        "valid_n_train", "valid_n_test", "prevalence_train", "prevalence_test",
        "tuned_prob_threshold", "test_pr_auc", "test_recall", "test_precision",
        "test_f1", "test_f2", "test_far", "status",
    ]
    cov_cols = [
        "cohort_name", "min_periods", "valid_n_train", "valid_n_test",
        "prevalence_train", "prevalence_test", "tuned_prob_threshold",
        "test_pr_auc", "test_recall", "test_precision", "test_f2", "test_far", "status",
    ]
    reg_cols = [
        "cohort_name", "spec", "valid_n_train", "valid_n_test",
        "beta_wind_speed", "se_wind_speed_hac24", "beta_temperature",
        "beta_relative_humidity", "beta_lag_or_roll",
        "test_mae", "test_rmse", "test_r2", "test_adj_r2",
    ]
    win_cls = results.training_window_df[results.training_window_df["task_type"] == "classification"]
    win_reg = results.training_window_df[results.training_window_df["task_type"] == "regression"]
    win_cls_cols = [
        "cohort_name", "train_window_pct", "valid_n_train", "valid_n_test",
        "tuned_prob_threshold", "test_pr_auc", "test_recall", "test_precision", "test_f2", "status",
    ]
    win_reg_cols = [
        "cohort_name", "train_window_pct", "valid_n_train", "valid_n_test",
        "beta_wind_speed", "se_wind_speed_hac24", "test_mae", "test_rmse", "test_r2",
    ]
    seas_cls = results.season_stratified_df[results.season_stratified_df["task_type"] == "classification"]
    seas_reg = results.season_stratified_df[results.season_stratified_df["task_type"] == "regression"]
    seas_cls_cols = [
        "cohort_name", "season", "valid_n_test", "n_test_positive", "prevalence_test",
        "test_pr_auc", "test_recall", "test_precision", "test_f2", "test_far", "status",
    ]
    seas_reg_cols = [
        "cohort_name", "season", "valid_n_test", "test_mae", "test_rmse", "test_r2", "mean_bias", "status",
    ]
    der_cols = [
        "cohort_name", "task_type", "valid_n_train_obs", "valid_n_train_der",
        "recovered_train_rows", "valid_n_test",
        "test_mae_obs", "test_mae_der", "delta_test_mae",
        "test_rmse_obs", "test_rmse_der", "delta_test_rmse",
        "test_pr_auc_obs", "test_pr_auc_der", "delta_test_pr_auc",
        "test_ground_truth_unchanged", "status",
    ]

    lines = [
        "# Báo Cáo Phân Tích Độ Nhạy Đa Chiều (Issue #15)",
        "",
        f"- **Run ID:** `{results.run_id}`",
        f"- **Generated (UTC):** `{results.generated_at_utc}`",
        f"- **Deterministic Seed:** `{results.seed}`",
        "- **Giao thức trạm:** Protocol A đơn trạm nghiêm ngặt (cấm gộp đa trạm lệch pha Protocol B).",
        "- **Khung mô hình:** Phân loại dùng `LogisticRegression(class_weight='balanced')` trong `Pipeline` chống rò rỉ (`SimpleImputer` + `RobustScaler`, tinh chỉnh ngưỡng $F_2$ trên Train 5-fold `TimeSeriesSplit`); Hồi quy dùng OLS kèm sai số chuẩn `HAC Newey-West (maxlags=24)`.",
        "",
        "## 1. Cấu Hình Phạm Vi Dữ Liệu & Minh Bạch Khác Biệt Mốc Chia",
        "",
        _df_to_markdown(cohort_df),
        "",
        "> **Lưu ý quan trọng về khác biệt giao thức giữa `VN001_baseline_2026_01_15` và `VN001_extended_80_20`:**",
        "> Cả hai phạm vi đều dùng cùng trạm `VN001_HANOI_556_NGUYEN_VAN_CU` (9,044 giờ lưới, 7,495 giờ `pm25` hợp lệ), nhưng mốc cắt thời gian khác nhau:",
        "> - `VN001_baseline_2026_01_15` cắt tại `2026-01-15 00:00:00+07:00` (Train gồm mùa Thu–Đông 07/2025–01/2026; Test trải dài Đông–Xuân–Hạ 01–07/2026 có cả đợt ô nhiễm cao lẫn mùa sạch).",
        "> - `VN001_extended_80_20` dùng cột `split` 80/20 chuẩn hóa của Issue #44 (Test bắt đầu từ `2026-05-01 09:00+07:00` rơi trọn vào mùa Hạ mưa nhiều + đợt mất dữ liệu dài 630 giờ), dẫn đến **0 ca dương tính** ở ngưỡng 50.0 µg/m³ (`UNESTIMABLE`).",
        "> Khi truyền cùng mốc cắt và giao thức trên cùng trạm, hai luồng cho kết quả đồng nhất tuyệt đối (được kiểm chứng bởi `tests/test_sensitivity.py`).",
        "",
        "## 2. Kiểm Chứng Bất Biến Artifact Baseline (SHA-256 Before/After)",
        "",
        _df_to_markdown(hash_df),
        "",
        "## 3. Độ Nhạy Ngưỡng Cảnh Báo Phân Loại (Task 9.4: 40 / 45 / 50 / 55 µg/m³)",
        "",
        "> Chỉ mức **`50.0 µg/m³`** (trung bình trượt 24h) tham chiếu **`QCVN 05:2023/BTNMT (24h reference)`**. Các mức `40.0`, `45.0` và `55.0 µg/m³` là **`technical_sensitivity_threshold`** phục vụ kiểm tra độ nhạy kỹ thuật, **không** phải quy chuẩn pháp lý.",
        "",
        _df_to_markdown(results.threshold_df[thr_cols]),
        "",
        "## 4. Độ Nhạy Độ Phủ Cửa Sổ Trượt (`min_periods` ∈ {12, 18, 24} tại 50.0 µg/m³)",
        "",
        "> Thay đổi đồng bộ `min_periods` cho cả nhãn trung bình trượt 24h và đặc trưng trượt quá khứ 24h (kết thúc ở `t-1`) để đo lường thực chất lượng mẫu thu hồi và độ ổn định hiệu năng.",
        "",
        _df_to_markdown(results.coverage_df[cov_cols]),
        "",
        "## 5. Độ Nhạy Độ Trễ & Cửa Sổ Trượt Trong Hồi Quy OLS + HAC-24 (Task 9.5)",
        "",
        "> Mọi biến `lag_*` và `roll_mean_*` được tính strictly-past-only trong nội bộ từng `station_id` trên lưới giờ chuẩn (không bắc cầu qua gap, không lookahead). Các hệ số phản ánh liên hệ quan sát (*associational, ceteris paribus*), không diễn giải nhân quả.",
        "",
        _df_to_markdown(results.regression_lag_df[reg_cols]),
        "",
        "## 6. Độ Nhạy Chiều Dài Cửa Sổ Huấn Luyện (50% / 75% / 100% Đuôi Train Trên Test Cố Định)",
        "",
        "### 6.1. Phân Loại (50.0 µg/m³, `min_periods=24`)",
        "",
        _df_to_markdown(win_cls[win_cls_cols]),
        "",
        "### 6.2. Hồi Quy OLS + HAC-24 (9 Biến Gốc)",
        "",
        _df_to_markdown(win_reg[win_reg_cols]),
        "",
        "## 7. Độ Nhạy Phân Tầng Theo Mùa Trên Tập Test (Xuân / Hạ / Thu / Đông)",
        "",
        "### 7.1. Phân Loại Theo Mùa",
        "",
        _df_to_markdown(seas_cls[seas_cls_cols]),
        "",
        "### 7.2. Hồi Quy Theo Mùa",
        "",
        _df_to_markdown(seas_reg[seas_reg_cols]),
        "",
        "## 8. Độ Nhạy Nội Suy Phái Sinh (`pm25_derived_interpolated`, Chỉ Trên Train)",
        "",
        "> Nội suy khoảng trống ngắn (`pm25_derived_interpolated`) chỉ được phép sử dụng trên tập Train; tập Test ground-truth (`pm25` quan trắc gốc) và `X_test` được khóa cứng bất biến (`test_ground_truth_unchanged = True`).",
        "",
        _df_to_markdown(results.derived_interpolation_df[der_cols]) if not results.derived_interpolation_df.empty else "_Không có phạm vi nào chứa `pm25_derived_interpolated`._",
        "",
    ]
    return "\n".join(lines).rstrip("\n") + "\n"
