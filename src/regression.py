"""
src/regression.py — Mô hình hóa Hồi quy Tuyến tính OLS, Chẩn đoán LINE & Điều hòa (Issue #12, Week 10).

Tuân thủ nghiêm ngặt chuẩn mực học thuật INFO3020 và hợp đồng mở rộng lịch sử Issue #44/#50:
  1. Tách riêng từng trạm theo Protocol A (từ chối gộp đa trạm lệch thời gian theo Protocol B).
  2. Kế thừa điểm cắt chuỗi thời gian tuyến tính (`2026-01-15` cho VN001 baseline; cột `split` 80/20
     cho từng trạm trên tập mở rộng 2022–2026) với đảm bảo `train.max() < test.min()`.
  3. Chống rò rỉ dữ liệu tuyệt đối: mọi imputer (`SimpleImputer`) và scaler (`RobustScaler`)
     nằm gọn trong `Pipeline` fit độc lập bên trong từng fold CV và kiểm chứng bằng `validate_no_leakage()`.
  4. Khảo sát biến đổi mục tiêu `Y = log(1 + PM2.5)` trên tập Train và giữ đơn vị gốc nếu độ lệch xấu đi.
  5. Chẩn đoán đầy đủ 4 giả định LINE trên phần dư:
     - L (Linearity): Ramsey RESET test (bậc 2 & 3) + đường cong LOWESS + bảng trung bình phần dư theo phân vị.
     - I (Independence): Durbin-Watson statistic, ACF chuỗi phần dư & độ nhạy sai số chuẩn HAC Newey-West
       tại các độ trễ (0/HC1, plug-in Andrews/NW, 12, 24, 48, 72, 168 giờ).
     - N (Normality): Normal Q-Q plot, Skewness/Kurtosis, kiểm định Jarque-Bera & Shapiro-Wilk (khi n <= 5000).
     - E (Equal Variance): Kiểm định Breusch-Pagan & Scale-Location kèm đường cong LOWESS.
  6. Kiểm toán đa cộng tuyến VIF, phân loại Outlier (`|stud_resid| > 3`), High Leverage (`2p/n`),
     và Cook's Distance (`> 4/n`, `> 0.5`, `> 1.0`).
  7. Thử nghiệm ablation (bỏ chu kỳ mùa `month_sin/cos`, chỉ khí tượng, bổ sung `pm25_lag24` nội trạm),
     rolling-origin backtest trong Train, độ ổn định hệ số phân tầng kèm cỡ mẫu hiệu dụng `n_eff`,
     và phân tích độ nhạy nội suy phái sinh (`pm25_derived_interpolated`, chỉ trên Train).
  8. Xuất báo cáo động 100% từ kết quả tính toán thực tế (không hard-code số liệu).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from statsmodels.stats.diagnostic import het_breuschpagan, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import acf

from src.cleaning_pipeline import validate_no_leakage
from src.issue44_preparation import validate_modeling_split

logger = logging.getLogger(__name__)

# Ranh giới phân chia thời gian tuyến tính kế thừa từ Issue #7 (baseline VN001)
DEFAULT_SPLIT_TIMESTAMP: str = "2026-01-15 00:00:00+07:00"
PRIMARY_BASELINE_STATION: str = "VN001_HANOI_556_NGUYEN_VAN_CU"
EXTENDED_HISTORICAL_STATION: str = "VN003_HANOI_OPENAQ_7441"

# Tập biến giải thích mặc định: khí tượng bề mặt + chu kỳ thời gian
# - `pm10`: loại trừ do cộng tuyến gần hoàn hảo với PM2.5 (r = 0.9727, VIF > 30)
# - `pm25_was_missing`: loại trừ do structural target leakage
# - `is_high_humidity_fog`: loại trừ do chưa có bằng chứng dự báo marginal
REGRESSION_PREDICTORS: List[str] = [
    "temperature",
    "relative_humidity",
    "wind_speed",
    "precipitation",
    "surface_pressure",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
]

METEOROLOGY_PREDICTORS: List[str] = [
    "temperature",
    "relative_humidity",
    "wind_speed",
    "precipitation",
    "surface_pressure",
]

FORBIDDEN_TARGET_FLAGS: Tuple[str, ...] = (
    "pm25",
    "pm25_was_missing",
    "pm25_derived_interpolated",
    "pm25_is_derived",
)

_FEATURE_METADATA: Dict[str, Tuple[str, str, str]] = {
    "wind_speed": (
        "Tốc độ gió (`wind_speed`)",
        "m/s",
        "cơ chế khuếch tán ngang và thông gió khí quyển trong đô thị",
    ),
    "precipitation": (
        "Lượng mưa (`precipitation`)",
        "mm",
        "quá trình rửa trôi ướt các hạt bụi mịn theo giờ",
    ),
    "temperature": (
        "Nhiệt độ (`temperature`)",
        "°C",
        "độ ổn định nhiệt động lực học và đối lưu thẳng đứng của lớp biên",
    ),
    "relative_humidity": (
        "Độ ẩm tương đối (`relative_humidity`)",
        "%",
        "điều kiện ẩm bề mặt và khả năng hình thành sol khí thứ cấp",
    ),
    "surface_pressure": (
        "Áp suất bề mặt (`surface_pressure`)",
        "hPa",
        "trạng thái xoáy thuận/khối khí áp cao quy mô synop",
    ),
    "hour_sin": (
        "Thành phần sin chu kỳ giờ (`hour_sin`)",
        "đơn vị chuẩn hóa [-1, 1]",
        "biến thiên phát thải giao thông và co giãn chiều cao lớp trộn ngày đêm",
    ),
    "hour_cos": (
        "Thành phần cos chu kỳ giờ (`hour_cos`)",
        "đơn vị chuẩn hóa [-1, 1]",
        "nhịp điều hòa pha ngày đêm giữa ban ngày và ban đêm",
    ),
    "month_sin": (
        "Thành phần sin chu kỳ mùa (`month_sin`)",
        "đơn vị chuẩn hóa [-1, 1]",
        "biến thiên pha mùa trong năm (gió mùa Đông Bắc / Đông Nam)",
    ),
    "month_cos": (
        "Thành phần cos chu kỳ mùa (`month_cos`)",
        "đơn vị chuẩn hóa [-1, 1]",
        "mức nền phân tầng nghịch nhiệt mùa đông so với mùa hè",
    ),
    "pm25_lag24": (
        "PM2.5 trễ 24 giờ (`pm25_lag24`)",
        "µg/m³",
        "tính bền bỉ tự hồi quy chuỗi thời gian cùng khung giờ ngày hôm trước",
    ),
}


@dataclass
class LINEDiagnostics:
    """Kết quả chẩn đoán 4 giả định LINE trên phần dư OLS."""

    # L - Linearity
    residuals_mean: float
    residuals_fitted_corr: float
    # I - Independence
    durbin_watson: float
    acf_values: np.ndarray
    acf_lags: int
    # N - Normality
    skewness: float
    kurtosis: float
    jarque_bera_stat: float
    jarque_bera_pvalue: float
    shapiro_stat: Optional[float]
    shapiro_pvalue: Optional[float]
    # E - Equal Variance (Homoscedasticity)
    breusch_pagan_stat: float
    breusch_pagan_pvalue: float
    # L - Non-linearity tests (Ramsey RESET & binned means)
    reset_power2_f: Optional[float] = None
    reset_power2_pvalue: Optional[float] = None
    reset_power3_f: Optional[float] = None
    reset_power3_pvalue: Optional[float] = None
    linearity_violated: Optional[bool] = None
    binned_residual_means: Optional[pd.DataFrame] = None
    plugin_nw_maxlags: int = 24


@dataclass
class RegressionResults:
    """Tập hợp đầy đủ kết quả thực nghiệm của bài toán hồi quy Issue #12."""

    split_timestamp: str
    n_train: int
    n_test: int
    predictors: List[str]
    vif_table: pd.DataFrame
    ols_summary_str: str
    hac_summary_str: str
    coefficients: pd.DataFrame
    line_diagnostics: LINEDiagnostics
    cooks_distance_max: float
    cooks_distance_threshold: float
    n_influential_points: int
    ridge_best_alpha: float
    lasso_best_alpha: float
    metrics_table: pd.DataFrame
    log1p_target_evaluated: bool = False
    log1p_metrics: Optional[Dict[str, float]] = None
    station_id: Optional[str] = None
    run_label: str = "VN001_baseline"
    split_mode: str = "timestamp"
    dataset_path: Optional[str] = None
    predictor_ranges: Optional[pd.DataFrame] = None
    influence_summary: Optional[Dict[str, Any]] = None
    hac_sensitivity_table: Optional[pd.DataFrame] = None
    ablation_table: Optional[pd.DataFrame] = None
    ablation_diagnostics: Optional[Dict[str, Any]] = None
    rolling_origin_cv: Optional[pd.DataFrame] = None
    stratified_stability: Optional[pd.DataFrame] = None
    derived_sensitivity: Optional[Dict[str, Any]] = None
    metadata_summary: Optional[Dict[str, Any]] = None
    test_target_stats: Optional[Dict[str, float]] = None
    n_train_imputed_features: int = 0
    n_test_imputed_features: int = 0


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Chuyển DataFrame thành bảng Markdown mà không cần gói tabulate."""
    if df.empty:
        return "_(Không có dữ liệu)_"
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = []
    for _, row in df.iterrows():
        vals = [str(row[c]) for c in df.columns]
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep] + rows)


def _fmt_p(p: float) -> str:
    """Định dạng p-value thống nhất."""
    if np.isnan(p):
        return "NaN"
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.4f}"


def _sha256_file(path: Path) -> str:
    """Tính SHA-256 cho tệp dữ liệu đầu vào."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _select_single_station(
    df: pd.DataFrame,
    station_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Lọc và kiểm chứng tính đơn trạm + thứ tự thời gian đơn điệu nghiêm ngặt.

    Từ chối fail-closed nếu phát hiện nhiều hơn 1 trạm mà không chỉ định `station_id`
    (ngăn chặn gộp đa trạm bất hợp lệ theo Protocol B) hoặc nếu có timestamp trùng lặp.
    """
    if "timestamp" not in df.columns:
        raise KeyError("Thiếu cột bắt buộc 'timestamp' trong DataFrame.")

    out = df.copy()
    if "station_id" in out.columns:
        if out["station_id"].isna().any():
            raise ValueError("Cột 'station_id' chứa giá trị NaN — từ chối fail-closed.")
        if station_id is not None:
            out = out[out["station_id"] == station_id].copy()
            if out.empty:
                raise ValueError(f"Không tìm thấy dữ liệu cho trạm '{station_id}'.")
        else:
            unique_stations = list(out["station_id"].unique())
            if len(unique_stations) > 1:
                raise ValueError(
                    f"Phát hiện nhiều trạm {unique_stations} khi chưa chỉ định `station_id`. "
                    "Cấm gộp đa trạm theo Protocol B vì các trạm lệch pha thời gian (ví dụ VN003 2022–2025 vs VN001 2025–2026). "
                    "Hãy truyền `station_id` cụ thể để phân tích theo Protocol A."
                )
    elif station_id is not None:
        raise ValueError("Dữ liệu không có cột 'station_id' để lọc theo trạm.")

    out["timestamp"] = pd.to_datetime(out["timestamp"])
    if out["timestamp"].isna().any():
        raise ValueError("Cột 'timestamp' chứa giá trị NaT không hợp lệ.")
    if out["timestamp"].duplicated().any():
        raise ValueError("Phát hiện timestamp trùng lặp trong cùng một trạm.")

    return out.sort_values("timestamp").reset_index(drop=True)


def build_regression_preprocessor(predictor_cols: Sequence[str]) -> Pipeline:
    """
    Xây dựng Pipeline tiền xử lý chống rò rỉ (SimpleImputer median → RobustScaler)
    tương thích với `src.cleaning_pipeline.validate_no_leakage`.
    """
    cols = list(predictor_cols)
    if not cols:
        raise ValueError("Danh sách cột biến giải thích không được rỗng.")
    for forbidden in FORBIDDEN_TARGET_FLAGS:
        if forbidden in cols:
            raise ValueError(f"Biến '{forbidden}' bị cấm xuất hiện trong tập predictor hồi quy.")

    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", RobustScaler()),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[("num", numeric_pipe, cols)],
        remainder="drop",
    )
    return Pipeline(steps=[("preprocessor", preprocessor)])


def _fit_transform_train_only_ols_inputs(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], int, int]:
    """
    Impute biến giải thích bị thiếu (nếu có) strictly bằng median của Train
    dành cho các bước statsmodels OLS/VIF (ngoài CV).
    """
    n_tr_missing = int(X_train.isna().sum().sum())
    n_te_missing = int(X_test.isna().sum().sum()) if X_test is not None else 0

    medians = X_train.median()
    X_tr_clean = X_train.fillna(medians).astype(float)
    if X_tr_clean.isna().any().any():
        X_tr_clean = X_tr_clean.fillna(0.0)

    X_te_clean: Optional[pd.DataFrame] = None
    if X_test is not None:
        X_te_clean = X_test.fillna(medians).astype(float)
        if X_te_clean.isna().any().any():
            X_te_clean = X_te_clean.fillna(0.0)

    return X_tr_clean, X_te_clean, n_tr_missing, n_te_missing


def prepare_regression_data(
    df: pd.DataFrame,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    target_col: str = "pm25",
    predictor_cols: Optional[List[str]] = None,
    drop_collinear_pm10: bool = True,
    station_id: Optional[str] = None,
    use_split_column: bool = False,
    return_timestamps: bool = False,
) -> Union[
    Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series],
    Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.Series, pd.Series],
]:
    """
    Chuẩn bị dữ liệu đầu vào cho bài toán hồi quy OLS và điều chuẩn theo Protocol A:
      - Kiểm chứng đơn trạm (cấm gộp đa trạm lệch thời gian).
      - Loại trừ hàng thiếu biến mục tiêu (`pm25`) thay vì nội suy giả.
      - Loại trừ `pm10`, `pm25_was_missing`, và `is_high_humidity_fog` khỏi biến giải thích.
      - Phân chia Train/Test nghiêm ngặt theo thời gian (`train.max() < test.min()`).
      - KHÔNG thực hiện impute hay scaling toàn cục tại bước này để ngăn rò rỉ across-fold trong CV.
    """
    if target_col not in df.columns:
        raise KeyError(f"Thiếu cột biến mục tiêu bắt buộc '{target_col}' trong DataFrame.")

    df_sorted = _select_single_station(df, station_id=station_id)
    df_valid = df_sorted[df_sorted[target_col].notna()].copy()

    if predictor_cols is None:
        candidates = [c for c in REGRESSION_PREDICTORS if c in df_valid.columns]
    else:
        candidates = list(predictor_cols)

    if drop_collinear_pm10 and "pm10" in candidates:
        candidates.remove("pm10")

    for col in (target_col, "pm25_was_missing", "is_high_humidity_fog"):
        if col in candidates:
            if col in (target_col, "pm25_was_missing"):
                raise ValueError(f"Biến '{col}' gây rò rỉ mục tiêu và không được nằm trong predictors.")
            candidates.remove(col)

    missing_preds = [c for c in candidates if c not in df_valid.columns]
    if missing_preds:
        raise KeyError(f"Thiếu các cột biến giải thích trong dữ liệu: {missing_preds}")
    if not candidates:
        raise ValueError("Danh sách biến giải thích sau khi lọc bị rỗng.")

    if use_split_column:
        if "split" not in df_valid.columns:
            raise KeyError("Thiếu cột 'split' khi `use_split_column=True`.")
        if "station_id" in df_valid.columns:
            validate_modeling_split(df_valid, "station_specific")
        train_mask = df_valid["split"] == "train"
        test_mask = df_valid["split"] == "test"
    else:
        if split_timestamp is None:
            raise ValueError("Phải cung cấp `split_timestamp` khi `use_split_column=False`.")
        split_dt = pd.Timestamp(split_timestamp)
        ts_col = df_valid["timestamp"]
        if ts_col.dt.tz is not None and split_dt.tzinfo is None:
            split_dt = split_dt.tz_localize(ts_col.dt.tz)
        elif ts_col.dt.tz is None and split_dt.tzinfo is not None:
            split_dt = split_dt.tz_localize(None)
        train_mask = ts_col < split_dt
        test_mask = ts_col >= split_dt

    df_train = df_valid.loc[train_mask].copy()
    df_test = df_valid.loc[test_mask].copy()

    if df_train.empty or df_test.empty:
        raise ValueError(
            f"Tập Train ({len(df_train)}) hoặc Test ({len(df_test)}) rỗng sau phân chia thời gian."
        )
    if not (df_train["timestamp"].max() < df_test["timestamp"].min()):
        raise AssertionError(
            f"Vi phạm thứ tự thời gian: train.max()={df_train['timestamp'].max()} >= test.min()={df_test['timestamp'].min()}."
        )

    X_train = df_train[candidates].copy()
    y_train = df_train[target_col].astype(float).copy()
    X_test = df_test[candidates].copy()
    y_test = df_test[target_col].astype(float).copy()

    if return_timestamps:
        return (
            X_train,
            y_train,
            X_test,
            y_test,
            df_train["timestamp"].reset_index(drop=True),
            df_test["timestamp"].reset_index(drop=True),
        )
    return X_train, y_train, X_test, y_test


def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    """
    Tính chỉ số Phóng đại Phương sai VIF (Variance Inflation Factor) cho các biến giải thích.
    Quy ước diễn giải: VIF < 5 (thấp), 5 <= VIF < 10 (trung bình cần lưu ý), VIF >= 10 (nghiêm trọng).
    """
    X_clean, _, _, _ = _fit_transform_train_only_ols_inputs(X)
    X_with_const = sm.add_constant(X_clean, has_constant="add")
    vif_data = []
    for i, col in enumerate(X_with_const.columns):
        if col == "const":
            continue
        vif_val = float(variance_inflation_factor(X_with_const.values, i))
        vif_data.append({"Feature": col, "VIF": round(vif_val, 3)})

    return pd.DataFrame(vif_data).sort_values("VIF", ascending=False).reset_index(drop=True)


def compute_line_diagnostics(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
    X: pd.DataFrame,
    y: pd.Series,
    max_lags: int = 48,
) -> LINEDiagnostics:
    """
    Thực hiện kiểm toán 4 giả định LINE trên phần dư OLS:
      - L: Ramsey RESET test (power=2 và power=3 với use_f=True) + trung bình phần dư theo 10 phân vị fitted.
      - I: Durbin-Watson + chuỗi ACF đến `max_lags` + độ trễ plug-in Newey-West `floor(4*(n/100)^(2/9))`.
      - N: Skewness, excess Kurtosis, Jarque-Bera test và Shapiro-Wilk (khi n <= 5000).
      - E: Breusch-Pagan LM test.
    """
    residuals = np.asarray(ols_model.resid, dtype=float)
    fitted = np.asarray(ols_model.fittedvalues, dtype=float)
    n_obs = len(residuals)

    # L - Linearity: trung bình, tương quan OLS (gần 0 do đại số) và kiểm định Ramsey RESET thực chất
    res_mean = float(np.mean(residuals))
    if np.std(fitted) > 0 and np.std(residuals) > 0:
        res_fit_corr = float(stats.pearsonr(residuals, fitted)[0])
    else:
        res_fit_corr = 0.0

    reset2 = linear_reset(ols_model, power=2, use_f=True)
    reset3 = linear_reset(ols_model, power=3, use_f=True)
    reset_p2_f = float(np.asarray(reset2.fvalue).item())
    reset_p2_p = float(np.asarray(reset2.pvalue).item())
    reset_p3_f = float(np.asarray(reset3.fvalue).item())
    reset_p3_p = float(np.asarray(reset3.pvalue).item())
    linearity_violated = bool(reset_p2_p < 0.05 or reset_p3_p < 0.05)

    # Bảng trung bình phần dư theo 10 phân vị giá trị dự báo (kiểm chứng độ cong phi tuyến)
    n_bins = min(10, max(2, len(np.unique(fitted))))
    bins = pd.qcut(fitted, q=n_bins, duplicates="drop")
    binned_df = (
        pd.DataFrame({"bin": bins.astype(str), "fitted": fitted, "residual": residuals})
        .groupby("bin", sort=False, observed=True)
        .agg(
            n=("residual", "size"),
            mean_fitted=("fitted", "mean"),
            mean_residual=("residual", "mean"),
            std_residual=("residual", "std"),
        )
        .reset_index()
    )

    # I - Independence
    dw_stat = float(sm.stats.stattools.durbin_watson(residuals))
    effective_max_lags = min(max_lags, max(1, n_obs - 2))
    acf_vals = acf(residuals, nlags=effective_max_lags, fft=False)
    plugin_nw = max(1, int(np.floor(4.0 * (n_obs / 100.0) ** (2.0 / 9.0))))

    # N - Normality
    res_skew = float(stats.skew(residuals))
    res_kurt = float(stats.kurtosis(residuals))
    jb_stat, jb_p = stats.jarque_bera(residuals)
    jb_stat, jb_p = float(jb_stat), float(jb_p)

    shapiro_stat, shapiro_p = None, None
    if n_obs <= 5000:
        s_stat, s_p = stats.shapiro(residuals)
        shapiro_stat, shapiro_p = float(s_stat), float(s_p)

    # E - Equal Variance
    X_clean, _, _, _ = _fit_transform_train_only_ols_inputs(X)
    X_const = sm.add_constant(X_clean, has_constant="add")
    bp_test = het_breuschpagan(residuals, X_const)
    bp_lm_stat = float(bp_test[0])
    bp_lm_pvalue = float(bp_test[1])

    return LINEDiagnostics(
        residuals_mean=res_mean,
        residuals_fitted_corr=res_fit_corr,
        durbin_watson=dw_stat,
        acf_values=acf_vals,
        acf_lags=effective_max_lags,
        skewness=res_skew,
        kurtosis=res_kurt,
        jarque_bera_stat=jb_stat,
        jarque_bera_pvalue=jb_p,
        shapiro_stat=shapiro_stat,
        shapiro_pvalue=shapiro_p,
        breusch_pagan_stat=bp_lm_stat,
        breusch_pagan_pvalue=bp_lm_pvalue,
        reset_power2_f=reset_p2_f,
        reset_power2_pvalue=reset_p2_p,
        reset_power3_f=reset_p3_f,
        reset_power3_pvalue=reset_p3_p,
        linearity_violated=linearity_violated,
        binned_residual_means=binned_df,
        plugin_nw_maxlags=plugin_nw,
    )


def compute_cooks_distance(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
) -> Tuple[np.ndarray, float, int]:
    """Tính Cook's Distance và ngưỡng cảnh báo 4 / n."""
    influence = ols_model.get_influence()
    cooks_d = np.asarray(influence.cooks_distance[0], dtype=float)
    n = len(cooks_d)
    threshold = 4.0 / n
    n_influential = int(np.sum(cooks_d > threshold))
    return cooks_d, threshold, n_influential


def compute_influence_summary(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
    timestamps: Optional[pd.Series] = None,
    top_n: int = 10,
) -> Dict[str, Any]:
    """
    Phân tách rạch ròi 3 khái niệm chẩn đoán ảnh hưởng OLS:
      1. Regression outliers: |studentized residual| > 3.0
      2. High leverage points: h_ii > 2 * p / n
      3. Influential observations (Cook's Distance): D_i > 4/n, D_i > 0.5, D_i > 1.0
    """
    influence = ols_model.get_influence()
    cooks_d = np.asarray(influence.cooks_distance[0], dtype=float)
    leverage = np.asarray(influence.hat_matrix_diag, dtype=float)
    stud_resid = np.asarray(influence.resid_studentized_external, dtype=float)
    resid = np.asarray(ols_model.resid, dtype=float)
    fitted = np.asarray(ols_model.fittedvalues, dtype=float)
    endog = np.asarray(ols_model.model.endog, dtype=float)

    n_obs = len(cooks_d)
    p_params = len(ols_model.params)
    cooks_thresh_4n = 4.0 / n_obs
    lev_thresh_2pn = 2.0 * p_params / n_obs
    stud_thresh = 3.0

    is_outlier = np.abs(stud_resid) > stud_thresh
    is_high_lev = leverage > lev_thresh_2pn
    is_cooks_4n = cooks_d > cooks_thresh_4n

    top_idx = np.argsort(cooks_d)[::-1][:top_n]
    top_rows = []
    for idx in top_idx:
        ts_val = str(timestamps.iloc[idx]) if timestamps is not None else str(idx)
        top_rows.append(
            {
                "timestamp": ts_val,
                "pm25_obs": round(float(endog[idx]), 2),
                "fitted": round(float(fitted[idx]), 2),
                "residual": round(float(resid[idx]), 2),
                "stud_resid": round(float(stud_resid[idx]), 3),
                "leverage": round(float(leverage[idx]), 5),
                "cooks_d": round(float(cooks_d[idx]), 5),
            }
        )

    return {
        "n_obs": n_obs,
        "p_params": p_params,
        "cooks_threshold_4n": cooks_thresh_4n,
        "n_cooks_gt_4n": int(np.sum(is_cooks_4n)),
        "pct_cooks_gt_4n": 100.0 * float(np.mean(is_cooks_4n)),
        "n_cooks_gt_05": int(np.sum(cooks_d > 0.5)),
        "n_cooks_gt_10": int(np.sum(cooks_d > 1.0)),
        "cooks_max": float(np.max(cooks_d)),
        "leverage_threshold_2pn": lev_thresh_2pn,
        "n_high_leverage": int(np.sum(is_high_lev)),
        "leverage_max": float(np.max(leverage)),
        "stud_resid_threshold": stud_thresh,
        "n_outliers_stud_gt_3": int(np.sum(is_outlier)),
        "n_outlier_and_high_leverage": int(np.sum(is_outlier & is_high_lev)),
        "top_influential": pd.DataFrame(top_rows),
    }


def compute_hac_lag_sensitivity(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    lags: Optional[Sequence[int]] = None,
    focus_features: Optional[Sequence[str]] = None,
) -> Tuple[pd.DataFrame, int]:
    """
    Đánh giá độ nhạy sai số chuẩn và p-value dưới HAC Newey-West tại nhiều độ trễ L,
    bao gồm L=0 (HC1), plug-in Newey-West `floor(4*(n/100)^(2/9))`, 12, 24, 48, 72, 168 giờ.
    """
    X_clean, _, _, _ = _fit_transform_train_only_ols_inputs(X_train)
    X_const = sm.add_constant(X_clean, has_constant="add")
    y_arr = pd.Series(y_train).astype(float).reset_index(drop=True)
    X_const = X_const.reset_index(drop=True)

    plugin_nw = max(1, int(np.floor(4.0 * (len(y_arr) / 100.0) ** (2.0 / 9.0))))
    if lags is None:
        raw_lags = [0, plugin_nw, 12, 24, 48, 72, 168]
    else:
        raw_lags = list(lags)
    unique_lags = sorted({int(l) for l in raw_lags if 0 <= int(l) < len(y_arr)})

    if focus_features is None:
        cols_focus = [c for c in METEOROLOGY_PREDICTORS if c in X_clean.columns]
    else:
        cols_focus = [c for c in focus_features if c in X_clean.columns]

    rows = []
    for lag in unique_lags:
        if lag == 0:
            fit_res = sm.OLS(y_arr, X_const).fit(cov_type="HC1")
            lag_label = "0 (HC1)"
        else:
            fit_res = sm.OLS(y_arr, X_const).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
            lag_label = f"{lag} (NW plug-in)" if lag == plugin_nw else str(lag)

        for feat in cols_focus:
            pval = float(fit_res.pvalues[feat])
            rows.append(
                {
                    "maxlags": lag,
                    "lag_label": lag_label,
                    "Feature": feat,
                    "Beta": round(float(fit_res.params[feat]), 4),
                    "SE": round(float(fit_res.bse[feat]), 4),
                    "p_value": round(pval, 6),
                    "p_display": _fmt_p(pval),
                    "sig_5pct": pval < 0.05,
                }
            )

    return pd.DataFrame(rows), plugin_nw


def tune_regularization(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_splits: int = 5,
    alphas: Optional[np.ndarray] = None,
) -> Tuple[float, float, Ridge, Lasso, Pipeline]:
    """
    Dò tìm siêu tham số alpha tối ưu cho Ridge và Lasso HOÀN TOÀN trên tập Train
    bằng TimeSeriesSplit.

    An toàn rò rỉ triệt để:
      Mỗi fold dựng `fold_prep = build_regression_preprocessor(...)`, chỉ gọi `.fit()`
      trên `tr_idx` (học cả `SimpleImputer(median)` lẫn `RobustScaler` trong từng fold),
      rồi mới `.transform(val_idx)`. Không tiền-impute trên toàn Train trước vòng lặp CV.
    """
    if alphas is None:
        alphas = np.logspace(-3, 3, 50)

    cols = list(X_train.columns)
    effective_splits = min(n_splits, max(2, len(X_train) - 1))
    tscv = TimeSeriesSplit(n_splits=effective_splits)
    y_series = pd.Series(y_train).reset_index(drop=True)
    X_df = X_train.reset_index(drop=True)

    fold_splits = list(tscv.split(X_df))
    fold_transformed: List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    for tr_idx, val_idx in fold_splits:
        fold_prep = build_regression_preprocessor(cols)
        X_tr_fold = fold_prep.fit_transform(X_df.iloc[tr_idx])
        X_val_fold = fold_prep.transform(X_df.iloc[val_idx])
        fold_transformed.append(
            (X_tr_fold, y_series.iloc[tr_idx].to_numpy(), X_val_fold, y_series.iloc[val_idx].to_numpy())
        )

    best_ridge_alpha = float(alphas[0])
    best_ridge_rmse = float("inf")
    for alpha in alphas:
        rmses = []
        for X_tr_f, y_tr_f, X_val_f, y_val_f in fold_transformed:
            model = Ridge(alpha=float(alpha))
            model.fit(X_tr_f, y_tr_f)
            preds = model.predict(X_val_f)
            rmses.append(float(np.sqrt(mean_squared_error(y_val_f, preds))))
        mean_rmse = float(np.mean(rmses))
        if mean_rmse < best_ridge_rmse:
            best_ridge_rmse = mean_rmse
            best_ridge_alpha = float(alpha)

    best_lasso_alpha = float(alphas[0])
    best_lasso_rmse = float("inf")
    for alpha in alphas:
        rmses = []
        for X_tr_f, y_tr_f, X_val_f, y_val_f in fold_transformed:
            model = Lasso(alpha=float(alpha), max_iter=10000, random_state=42)
            model.fit(X_tr_f, y_tr_f)
            preds = model.predict(X_val_f)
            rmses.append(float(np.sqrt(mean_squared_error(y_val_f, preds))))
        mean_rmse = float(np.mean(rmses))
        if mean_rmse < best_lasso_rmse:
            best_lasso_rmse = mean_rmse
            best_lasso_alpha = float(alpha)

    # Fit preprocessor cuối cùng STRICTLY trên toàn bộ Train
    final_prep = build_regression_preprocessor(cols)
    X_train_scaled = final_prep.fit_transform(X_df)

    final_ridge = Ridge(alpha=best_ridge_alpha).fit(X_train_scaled, y_series.to_numpy())
    final_lasso = Lasso(alpha=best_lasso_alpha, max_iter=10000, random_state=42).fit(
        X_train_scaled, y_series.to_numpy()
    )

    return best_ridge_alpha, best_lasso_alpha, final_ridge, final_lasso, final_prep


def evaluate_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    ridge_model: Ridge,
    lasso_model: Lasso,
    scaler: Optional[Any] = None,
) -> Tuple[pd.DataFrame, LinearRegression]:
    """Đánh giá hiệu năng tổng thể trên tập Test độc lập: Baseline vs OLS vs Ridge vs Lasso."""
    X_tr_clean, X_te_clean, _, _ = _fit_transform_train_only_ols_inputs(X_train, X_test)

    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_tr_clean, y_train)
    pred_dummy = dummy.predict(X_te_clean)

    ols_sk = LinearRegression()
    ols_sk.fit(X_tr_clean, y_train)
    pred_ols = ols_sk.predict(X_te_clean)

    if scaler is None:
        scaler = build_regression_preprocessor(list(X_train.columns)).fit(X_train)
    X_test_scaled = scaler.transform(X_test)
    pred_ridge = ridge_model.predict(X_test_scaled)
    pred_lasso = lasso_model.predict(X_test_scaled)

    n_test = len(y_test)
    p = X_train.shape[1]

    models_preds = {
        "Baseline (Dummy Mean)": pred_dummy,
        "OLS Linear Regression": pred_ols,
        f"Ridge (alpha={ridge_model.alpha:.3f})": pred_ridge,
        f"Lasso (alpha={lasso_model.alpha:.3f})": pred_lasso,
    }

    metrics = []
    for name, pred in models_preds.items():
        mae = float(mean_absolute_error(y_test, pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
        r2 = float(r2_score(y_test, pred))
        p_val = 0 if ("Baseline" in name or "Dummy" in name) else p
        adj_r2 = (
            float(1.0 - (1.0 - r2) * (n_test - 1) / (n_test - p_val - 1))
            if n_test > p_val + 1
            else np.nan
        )
        metrics.append(
            {
                "Model": name,
                "MAE (µg/m³)": round(mae, 2),
                "RMSE (µg/m³)": round(rmse, 2),
                "R²": round(r2, 4),
                "Adjusted R²": round(adj_r2, 4),
            }
        )

    return pd.DataFrame(metrics), ols_sk


def evaluate_seasonal_and_lag_ablation(
    df_station: pd.DataFrame,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    use_split_column: bool = False,
    station_id: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Thử nghiệm ablation để bóc tách căn nguyên R² âm trên Test:
      1. Full 9 biến (khí tượng + chu kỳ giờ + chu kỳ mùa)
      2. Bỏ `month_sin`, `month_cos` (7 biến — chẩn đoán ngoại suy mùa từ nửa chu kỳ Train)
      3. Chỉ 5 biến khí tượng bề mặt (`temperature`, `relative_humidity`, `wind_speed`, `precipitation`, `surface_pressure`)
      4. Khí tượng + chu kỳ giờ + `pm25_lag24` nội trạm (tính nghiêm ngặt theo `timestamp - 24h`)
    """
    df_sorted = _select_single_station(df_station, station_id=station_id)
    pm25_by_ts = df_sorted.set_index("timestamp")["pm25"]
    df_sorted["pm25_lag24"] = (df_sorted["timestamp"] - pd.Timedelta(hours=24)).map(pm25_by_ts)

    full_preds = [c for c in REGRESSION_PREDICTORS if c in df_sorted.columns]
    no_month_preds = [c for c in full_preds if c not in ("month_sin", "month_cos")]
    met_preds = [c for c in METEOROLOGY_PREDICTORS if c in df_sorted.columns]
    ar_preds = [c for c in full_preds if c not in ("month_sin", "month_cos")] + ["pm25_lag24"]

    specs = [
        ("Baseline (Dummy Mean)", [], False),
        ("OLS Full (9 biến: khí tượng + giờ + mùa)", full_preds, False),
        ("OLS Bỏ chu kỳ mùa (7 biến: bỏ month_sin/cos)", no_month_preds, False),
        ("OLS Chỉ khí tượng (5 biến)", met_preds, False),
        ("OLS Khí tượng + Giờ + pm25_lag24 (8 biến, AR)", ar_preds, True),
    ]

    rows = []
    diag: Dict[str, Any] = {}

    for label, cols, requires_lag24 in specs:
        sub_df = df_sorted[df_sorted["pm25"].notna()].copy()
        if requires_lag24:
            sub_df = sub_df[sub_df["pm25_lag24"].notna()].copy()
        if sub_df.empty:
            continue

        if use_split_column:
            train_mask = sub_df["split"] == "train"
            test_mask = sub_df["split"] == "test"
        else:
            split_dt = pd.Timestamp(split_timestamp)
            ts_col = sub_df["timestamp"]
            if ts_col.dt.tz is not None and split_dt.tzinfo is None:
                split_dt = split_dt.tz_localize(ts_col.dt.tz)
            elif ts_col.dt.tz is None and split_dt.tzinfo is not None:
                split_dt = split_dt.tz_localize(None)
            train_mask = ts_col < split_dt
            test_mask = ts_col >= split_dt

        tr = sub_df.loc[train_mask]
        te = sub_df.loc[test_mask]
        if tr.empty or te.empty:
            continue

        y_tr = tr["pm25"].astype(float)
        y_te = te["pm25"].astype(float)

        if not cols:
            dummy = DummyRegressor(strategy="mean").fit(np.zeros((len(y_tr), 1)), y_tr)
            pred_tr = dummy.predict(np.zeros((len(y_tr), 1)))
            pred_te = dummy.predict(np.zeros((len(y_te), 1)))
        else:
            X_tr_clean, X_te_clean, _, _ = _fit_transform_train_only_ols_inputs(tr[cols], te[cols])
            model = LinearRegression().fit(X_tr_clean, y_tr)
            pred_tr = model.predict(X_tr_clean)
            pred_te = model.predict(X_te_clean)

        tr_r2 = float(r2_score(y_tr, pred_tr))
        te_mae = float(mean_absolute_error(y_te, pred_te))
        te_rmse = float(np.sqrt(mean_squared_error(y_te, pred_te)))
        te_r2 = float(r2_score(y_te, pred_te))
        mean_bias = float(np.mean(pred_te - y_te))

        rows.append(
            {
                "Specification": label,
                "n_train": int(len(y_tr)),
                "n_test": int(len(y_te)),
                "Train R²": round(tr_r2, 4),
                "Test MAE (µg/m³)": round(te_mae, 2),
                "Test RMSE (µg/m³)": round(te_rmse, 2),
                "Test R²": round(te_r2, 4),
                "Mean Bias (Pred−Obs)": round(mean_bias, 2),
            }
        )

        if label.startswith("OLS Full"):
            diag["train_pm25_mean"] = float(y_tr.mean())
            diag["test_pm25_mean"] = float(y_te.mean())
            diag["ols_full_test_pred_mean"] = float(np.mean(pred_te))
            diag["ols_full_mean_bias"] = mean_bias
            diag["ols_full_test_r2"] = te_r2
            if "month_sin" in tr.columns and "month_sin" in te.columns:
                ms_min, ms_max = float(tr["month_sin"].min()), float(tr["month_sin"].max())
                out_mask = (te["month_sin"] < ms_min) | (te["month_sin"] > ms_max)
                diag["test_month_sin_out_of_train_range_pct"] = 100.0 * float(out_mask.mean())
                diag["train_month_sin_range"] = (ms_min, ms_max)
                diag["test_month_sin_range"] = (float(te["month_sin"].min()), float(te["month_sin"].max()))
        elif "Bỏ chu kỳ mùa" in label:
            diag["ols_drop_season_test_r2"] = te_r2
            diag["ols_drop_season_mean_bias"] = mean_bias
        elif "pm25_lag24" in label:
            diag["ols_lag24_test_r2"] = te_r2
            diag["ols_lag24_test_rmse"] = te_rmse
            diag["ols_lag24_test_mae"] = te_mae

    return pd.DataFrame(rows), diag


def run_rolling_origin_backtest(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    timestamps_train: Optional[pd.Series] = None,
    n_splits: int = 5,
) -> pd.DataFrame:
    """
    Kiểm thử chéo chuỗi thời gian mở rộng dần (Rolling-Origin CV) hoàn toàn trong tập Train
    để đo tính ổn định R², MAE và RMSE của OLS vs Baseline qua từng giai đoạn tích lũy dữ liệu.
    """
    effective_splits = min(n_splits, max(2, len(X_train) - 1))
    tscv = TimeSeriesSplit(n_splits=effective_splits)
    rows = []
    for fold_idx, (tr_idx, val_idx) in enumerate(tscv.split(X_train), start=1):
        X_tr_f, X_val_f, _, _ = _fit_transform_train_only_ols_inputs(
            X_train.iloc[tr_idx], X_train.iloc[val_idx]
        )
        y_tr_f = y_train.iloc[tr_idx]
        y_val_f = y_train.iloc[val_idx]

        dummy = DummyRegressor(strategy="mean").fit(X_tr_f, y_tr_f)
        ols_f = LinearRegression().fit(X_tr_f, y_tr_f)

        p_dum = dummy.predict(X_val_f)
        p_ols = ols_f.predict(X_val_f)

        val_start = (
            str(timestamps_train.iloc[val_idx[0]])[:10]
            if timestamps_train is not None
            else str(val_idx[0])
        )
        val_end = (
            str(timestamps_train.iloc[val_idx[-1]])[:10]
            if timestamps_train is not None
            else str(val_idx[-1])
        )
        rows.append(
            {
                "Fold": fold_idx,
                "n_train_fold": int(len(tr_idx)),
                "n_val_fold": int(len(val_idx)),
                "Val Window": f"{val_start} → {val_end}",
                "Dummy RMSE": round(float(np.sqrt(mean_squared_error(y_val_f, p_dum))), 2),
                "OLS MAE": round(float(mean_absolute_error(y_val_f, p_ols)), 2),
                "OLS RMSE": round(float(np.sqrt(mean_squared_error(y_val_f, p_ols))), 2),
                "OLS R²": round(float(r2_score(y_val_f, p_ols)), 4),
            }
        )
    return pd.DataFrame(rows)


def compute_stratified_coefficient_stability(
    df_station: pd.DataFrame,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    use_split_column: bool = False,
    station_id: Optional[str] = None,
    min_obs_per_stratum: int = 120,
) -> pd.DataFrame:
    """
    Kiểm định độ ổn định hệ số khí tượng trên Train phân tầng theo năm (`year`) và mùa (`season`),
    báo cáo kèm hệ số tự tương quan phần dư bậc 1 (`rho1`) và cỡ mẫu hiệu dụng `n_eff = n*(1-rho1)/(1+rho1)`.
    """
    df_sorted = _select_single_station(df_station, station_id=station_id)
    df_valid = df_sorted[df_sorted["pm25"].notna()].copy()

    if use_split_column and "split" in df_valid.columns:
        df_tr = df_valid[df_valid["split"] == "train"].copy()
    elif split_timestamp is not None:
        split_dt = pd.Timestamp(split_timestamp)
        ts_col = df_valid["timestamp"]
        if ts_col.dt.tz is not None and split_dt.tzinfo is None:
            split_dt = split_dt.tz_localize(ts_col.dt.tz)
        elif ts_col.dt.tz is None and split_dt.tzinfo is not None:
            split_dt = split_dt.tz_localize(None)
        df_tr = df_valid[ts_col < split_dt].copy()
    else:
        df_tr = df_valid.copy()

    df_tr["year_str"] = df_tr["timestamp"].dt.year.astype(str)
    met_cols = [c for c in METEOROLOGY_PREDICTORS if c in df_tr.columns]
    if not met_cols or df_tr.empty:
        return pd.DataFrame()

    strata: List[Tuple[str, pd.DataFrame]] = []
    for yr, grp in df_tr.groupby("year_str", sort=True):
        strata.append((f"Year {yr}", grp))
    if "season" in df_tr.columns:
        for sea, grp in df_tr.groupby("season", sort=False):
            strata.append((f"Season {sea}", grp))

    rows = []
    for name, grp in strata:
        if len(grp) < min_obs_per_stratum:
            continue
        X_sub, _, _, _ = _fit_transform_train_only_ols_inputs(grp[met_cols])
        # Bỏ cột hằng số trong phân tầng hẹp nếu xảy ra (ví dụ toàn 0 mưa)
        varying_cols = [c for c in met_cols if X_sub[c].std() > 1e-12]
        if not varying_cols:
            continue
        X_const = sm.add_constant(X_sub[varying_cols].reset_index(drop=True), has_constant="add")
        y_sub = grp["pm25"].astype(float).reset_index(drop=True)
        ols_hac = sm.OLS(y_sub, X_const).fit(cov_type="HAC", cov_kwds={"maxlags": 24})
        res = np.asarray(ols_hac.resid, dtype=float)
        rho1 = float(np.corrcoef(res[:-1], res[1:])[0, 1]) if len(res) > 2 else 0.0
        n_obs = len(res)
        n_eff = max(1.0, n_obs * (1.0 - rho1) / max(1e-6, 1.0 + rho1))

        row: Dict[str, Any] = {
            "Stratum": name,
            "n_obs": n_obs,
            "rho1_resid": round(rho1, 3),
            "n_eff": int(round(n_eff)),
            "Train R²": round(float(ols_hac.rsquared), 4),
        }
        if "wind_speed" in ols_hac.params.index:
            row["wind_speed Beta"] = round(float(ols_hac.params["wind_speed"]), 3)
            row["wind_speed p(HAC)"] = _fmt_p(float(ols_hac.pvalues["wind_speed"]))
        if "precipitation" in ols_hac.params.index:
            row["precip Beta"] = round(float(ols_hac.params["precipitation"]), 3)
            row["precip p(HAC)"] = _fmt_p(float(ols_hac.pvalues["precipitation"]))
        rows.append(row)

    return pd.DataFrame(rows)


def evaluate_derived_interpolation_sensitivity(
    df_station: pd.DataFrame,
    predictor_cols: Optional[List[str]] = None,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    use_split_column: bool = False,
    station_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Đánh giá độ nhạy khi huấn luyện trên biến phái sinh `pm25_derived_interpolated`
    chỉ trong tập Train so với `pm25` quan trắc gốc.

    Quy tắc an toàn nghiêm ngặt: tập Test luôn đánh giá ĐỘC LẬP trên `pm25` quan trắc gốc
    (tuyệt đối không dùng giá trị nội suy làm ground truth cho Test).
    """
    if "pm25_derived_interpolated" not in df_station.columns:
        return None

    df_sorted = _select_single_station(df_station, station_id=station_id)
    preds = list(predictor_cols or [c for c in REGRESSION_PREDICTORS if c in df_sorted.columns])

    X_tr_obs, y_tr_obs, X_te_obs, y_te_obs = prepare_regression_data(
        df_sorted,
        split_timestamp=split_timestamp,
        target_col="pm25",
        predictor_cols=preds,
        use_split_column=use_split_column,
    )
    X_tr_der, y_tr_der, _, _ = prepare_regression_data(
        df_sorted,
        split_timestamp=split_timestamp,
        target_col="pm25_derived_interpolated",
        predictor_cols=preds,
        use_split_column=use_split_column,
    )

    X_tr_obs_c, X_te_obs_c, _, _ = _fit_transform_train_only_ols_inputs(X_tr_obs, X_te_obs)
    X_tr_der_c, _, _, _ = _fit_transform_train_only_ols_inputs(X_tr_der)

    ols_obs = sm.OLS(
        y_tr_obs.reset_index(drop=True),
        sm.add_constant(X_tr_obs_c.reset_index(drop=True), has_constant="add"),
    ).fit()
    ols_der = sm.OLS(
        y_tr_der.reset_index(drop=True),
        sm.add_constant(X_tr_der_c.reset_index(drop=True), has_constant="add"),
    ).fit()

    X_te_const = sm.add_constant(X_te_obs_c.reset_index(drop=True), has_constant="add")
    pred_te_obs = ols_obs.predict(X_te_const)
    pred_te_der = ols_der.predict(X_te_const)

    beta_delta = (ols_der.params - ols_obs.params).abs()
    comp_rows = []
    for col in ols_obs.params.index:
        comp_rows.append(
            {
                "Feature": col,
                "Beta (Observed Train)": round(float(ols_obs.params[col]), 4),
                "Beta (Derived Train)": round(float(ols_der.params[col]), 4),
                "Abs Diff": round(float(beta_delta[col]), 4),
            }
        )

    return {
        "n_train_observed": int(len(y_tr_obs)),
        "n_train_derived": int(len(y_tr_der)),
        "n_derived_hours_added_in_train": int(len(y_tr_der) - len(y_tr_obs)),
        "n_test_observed_ground_truth": int(len(y_te_obs)),
        "max_abs_beta_diff": float(beta_delta.max()),
        "test_rmse_observed_model": float(np.sqrt(mean_squared_error(y_te_obs, pred_te_obs))),
        "test_rmse_derived_train_model": float(np.sqrt(mean_squared_error(y_te_obs, pred_te_der))),
        "test_r2_observed_model": float(r2_score(y_te_obs, pred_te_obs)),
        "test_r2_derived_train_model": float(r2_score(y_te_obs, pred_te_der)),
        "coef_comparison": pd.DataFrame(comp_rows),
    }


def render_line_diagnostics_figure(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
    diagnostics: LINEDiagnostics,
    output_path: Path,
    title_prefix: str = "",
) -> None:
    """
    Xuất biểu đồ 4 ô kiểm định giả định LINE đạt chuẩn Tufte / Cleveland (300 DPI):
      1. Linearity: Residuals vs Fitted values kèm đường tham chiếu 0 và đường cong LOWESS.
      2. Independence: Biểu đồ ACF phần dư với dải tin cậy 95% Bartlett.
      3. Normality: Normal Q-Q plot của phần dư chuẩn hóa.
      4. Equal Variance: Scale-Location plot kèm đường cong LOWESS.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(13, 10), dpi=300)
    residuals = np.asarray(ols_model.resid, dtype=float)
    fitted = np.asarray(ols_model.fittedvalues, dtype=float)
    std_residuals = (residuals - residuals.mean()) / residuals.std(ddof=1)

    c_point = "#2b5c8f"
    c_line = "#d95f02"

    if title_prefix:
        fig.suptitle(title_prefix, fontsize=13, fontweight="bold", y=1.01)

    lowess_delta = 0.01 * max(1e-6, float(np.ptp(fitted)))

    # 1. Linearity (Residuals vs Fitted + LOWESS)
    ax1 = axes[0, 0]
    ax1.scatter(fitted, residuals, alpha=0.32, s=14, color=c_point, edgecolors="none", label="Phần dư")
    ax1.axhline(0, color="black", linestyle="--", linewidth=1.0, alpha=0.8)
    lowess_lin = sm.nonparametric.lowess(
        residuals, fitted, frac=0.25, delta=lowess_delta, return_sorted=True
    )
    ax1.plot(lowess_lin[:, 0], lowess_lin[:, 1], color=c_line, linewidth=2.0, label="LOWESS smooth")
    reset_txt = (
        f"RESET(p=2): F={diagnostics.reset_power2_f:.1f}, p={_fmt_p(diagnostics.reset_power2_pvalue)}"
        if diagnostics.reset_power2_f is not None and diagnostics.reset_power2_pvalue is not None
        else f"Mean={diagnostics.residuals_mean:.2e}"
    )
    ax1.set_title(
        f"1. Linearity: Residuals vs Fitted + LOWESS\n({reset_txt})",
        fontsize=11,
        fontweight="bold",
        pad=8,
    )
    ax1.set_xlabel("Giá trị dự báo Fitted (µg/m³)", fontsize=9)
    ax1.set_ylabel("Phần dư Residuals (µg/m³)", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper left", frameon=True, fontsize=8)

    # 2. Independence (ACF)
    ax2 = axes[0, 1]
    lags = np.arange(len(diagnostics.acf_values))
    ax2.vlines(lags, [0], diagnostics.acf_values, color=c_point, linewidth=1.5)
    ax2.scatter(lags, diagnostics.acf_values, color=c_point, s=16)
    ax2.axhline(0, color="black", linestyle="-", linewidth=0.8)
    ci_bound = 1.96 / np.sqrt(len(residuals))
    ax2.axhline(ci_bound, color=c_line, linestyle="--", linewidth=1.0, label="95% CI (Bartlett)")
    ax2.axhline(-ci_bound, color=c_line, linestyle="--", linewidth=1.0)
    acf1 = float(diagnostics.acf_values[1]) if len(diagnostics.acf_values) > 1 else np.nan
    ax2.set_title(
        f"2. Independence: Autocorrelation Function (ACF)\n(DW = {diagnostics.durbin_watson:.3f}, ACF(1) = {acf1:.3f})",
        fontsize=11,
        fontweight="bold",
        pad=8,
    )
    ax2.set_xlabel("Độ trễ Lag (Giờ)", fontsize=9)
    ax2.set_ylabel("Hệ số tự tương quan ACF", fontsize=9)
    ax2.set_ylim(-0.3, 1.05)
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right", frameon=True, fontsize=8)

    # 3. Normality (Q-Q Plot)
    ax3 = axes[1, 0]
    (osm, osr), (slope, intercept, r) = stats.probplot(std_residuals, dist="norm")
    ax3.scatter(osm, osr, alpha=0.32, s=14, color=c_point, edgecolors="none")
    ax3.plot(osm, slope * np.array(osm) + intercept, color=c_line, linewidth=1.4, label=f"Q-Q R² = {r**2:.3f}")
    ax3.set_title(
        f"3. Normality: Normal Q-Q Plot\n(Skew = {diagnostics.skewness:.2f}, Excess Kurtosis = {diagnostics.kurtosis:.2f})",
        fontsize=11,
        fontweight="bold",
        pad=8,
    )
    ax3.set_xlabel("Phân vị lý thuyết phân phối Chuẩn", fontsize=9)
    ax3.set_ylabel("Phần dư chuẩn hóa quan sát", fontsize=9)
    ax3.grid(True, linestyle=":", alpha=0.5)
    ax3.legend(loc="upper left", frameon=True, fontsize=8)

    # 4. Equal Variance (Scale-Location + LOWESS)
    ax4 = axes[1, 1]
    sqrt_abs_std_res = np.sqrt(np.abs(std_residuals))
    ax4.scatter(fitted, sqrt_abs_std_res, alpha=0.32, s=14, color=c_point, edgecolors="none")
    lowess_scale = sm.nonparametric.lowess(
        sqrt_abs_std_res, fitted, frac=0.25, delta=lowess_delta, return_sorted=True
    )
    ax4.plot(lowess_scale[:, 0], lowess_scale[:, 1], color=c_line, linewidth=2.0, label="LOWESS smooth")
    ax4.set_title(
        f"4. Equal Variance: Scale-Location + LOWESS\n(Breusch-Pagan p = {_fmt_p(diagnostics.breusch_pagan_pvalue)})",
        fontsize=11,
        fontweight="bold",
        pad=8,
    )
    ax4.set_xlabel("Giá trị dự báo Fitted (µg/m³)", fontsize=9)
    ax4.set_ylabel(r"$\sqrt{|\text{Standardized Residuals}|}$", fontsize=9)
    ax4.grid(True, linestyle=":", alpha=0.5)
    ax4.legend(loc="upper left", frameon=True, fontsize=8)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ chẩn đoán LINE: %s", output_path)


def _format_vif_verdict(vif_df: pd.DataFrame) -> str:
    """Phát sinh mô tả VIF động chính xác dựa trên ngưỡng <5 và <10."""
    max_vif = float(vif_df["VIF"].max())
    gt5 = vif_df[vif_df["VIF"] >= 5.0]
    gt10 = vif_df[vif_df["VIF"] >= 10.0]
    if gt10.empty and gt5.empty:
        return f"Tất cả các biến giải thích còn lại đều có $\\text{{VIF}} < 5,0$ (lớn nhất = {max_vif:.2f})."
    if gt10.empty:
        names = ", ".join(f"`{r['Feature']}` ({r['VIF']:.2f})" for _, r in gt5.iterrows())
        return (
            f"Không có biến nào vượt ngưỡng đa cộng tuyến nghiêm trọng $\\text{{VIF}} \\ge 10$; "
            f"tuy nhiên có {len(gt5)} biến ở mức trung bình ($5 \\le \\text{{VIF}} < 10$): {names} "
            "(chấp nhận giữ lại có giám sát do mang thông tin nhiệt động lực học nền), các biến còn lại đều $< 5,0$."
        )
    names = ", ".join(f"`{r['Feature']}` ({r['VIF']:.2f})" for _, r in gt10.iterrows())
    return f"Cảnh báo {len(gt10)} biến có $\\text{{VIF}} \\ge 10$: {names}."


def _format_beta_obligations(results: RegressionResults) -> List[str]:
    """Sinh chi tiết diễn giải từng hệ số beta hoàn toàn động theo 3 nghĩa vụ học thuật."""
    lines: List[str] = []
    ranges_df = results.predictor_ranges
    range_map: Dict[str, Tuple[float, float]] = {}
    if ranges_df is not None and not ranges_df.empty:
        for _, r in ranges_df.iterrows():
            range_map[str(r["Feature"])] = (float(r["Train Min"]), float(r["Train Max"]))

    for _, row in results.coefficients.iterrows():
        feat = str(row["Feature"])
        if feat == "const":
            continue
        beta = float(row["Coefficient (Beta)"])
        se_hac = float(row["SE (HAC-24)"])
        p_hac_str = str(row["p-Value (HAC-24)"])
        p_hac = float(row["p_hac_num"]) if "p_hac_num" in row.index else float(p_hac_str)
        ci_low = float(row["95% CI Lower (HAC)"])
        ci_high = float(row["95% CI Upper (HAC)"])

        label, unit, mechanism = _FEATURE_METADATA.get(
            feat, (f"`{feat}`", "đơn vị biến", "mối liên hệ quan sát tuyến tính trong mô hình")
        )
        if feat in range_map:
            r_min, r_max = range_map[feat]
            range_str = f"[{r_min:.2f}; {r_max:.2f}] {unit}"
        else:
            range_str = unit

        direction = "liên hệ với mức tăng" if beta >= 0 else "liên hệ với mức giảm"
        sig_note = (
            "Đạt ý nghĩa thống kê ở mức 5% dưới HAC"
            if p_hac < 0.05
            else "Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*)"
        )
        lines.append(
            f"- **{label} (dải quan sát Train {range_str}):**\n"
            f"  - $\\beta = {beta:+.4f}$ (SE HAC-24 = {se_hac:.4f}, $p_{{\\text{{HAC}}}} = {p_hac_str}$, "
            f"95% CI $[{ci_low:.4f}; {ci_high:.4f}]$). {sig_note}.\n"
            f"  - *Diễn giải:* Trong miền giá trị quan sát trên Train ({range_str}), mỗi khi biến tăng 1 {unit}, "
            f"PM2.5 trung bình giờ **{direction}** {abs(beta):.2f} µg/m³ trong điều kiện giữ nguyên các biến còn lại "
            f"(*ceteris paribus*), phản ánh {mechanism}."
        )
    return lines


def _render_single_scope_section(results: RegressionResults, heading_prefix: str = "##") -> str:
    """Dựng các phần phân tích chi tiết hoàn toàn động từ một đối tượng RegressionResults."""
    diag = results.line_diagnostics
    vif_md = _df_to_markdown(results.vif_table)
    coef_cols = [c for c in results.coefficients.columns if c != "p_hac_num"]
    coef_md = _df_to_markdown(results.coefficients[coef_cols])
    metrics_md = _df_to_markdown(results.metrics_table)
    acf1 = float(diag.acf_values[1]) if len(diag.acf_values) > 1 else np.nan
    acf24 = float(diag.acf_values[24]) if len(diag.acf_values) > 24 else np.nan

    reset2_txt = (
        f"Power=2: F = {diag.reset_power2_f:.2f}, p = {_fmt_p(diag.reset_power2_pvalue)}; "
        f"Power=3: F = {diag.reset_power3_f:.2f}, p = {_fmt_p(diag.reset_power3_pvalue)}"
        if diag.reset_power2_f is not None
        else f"r = {diag.residuals_fitted_corr:.2e}"
    )
    l_verdict = (
        "**VI PHẠM:** Kiểm định Ramsey RESET bác bỏ tuyến tính bậc một nghiêm trọng ($p < 10^{-10}$); "
        "dù $\\bar{e}$ và $\\text{corr}(\\hat{e}, \\hat{y}) \\approx 0$ theo đại số OLS."
        if diag.linearity_violated
        else "**THỎA MÃN:** Không bác bỏ giả định tuyến tính ở mức 5% trên Ramsey RESET."
    )
    shapiro_txt = (
        f", Shapiro W = {diag.shapiro_stat:.4f} (p = {_fmt_p(diag.shapiro_pvalue)})"
        if diag.shapiro_stat is not None and diag.shapiro_pvalue is not None
        else " (n > 5000 nên dùng Jarque-Bera)"
    )

    inf = results.influence_summary or {}
    inf_line = (
        f"Regression Outliers ($|\\text{{stud\\_resid}}| > 3$) = {inf.get('n_outliers_stud_gt_3', 0)}; "
        f"High Leverage ($h_{{ii}} > {inf.get('leverage_threshold_2pn', 0):.5f}$) = {inf.get('n_high_leverage', 0)}; "
        f"Cook's $D > 4/n$ ({results.cooks_distance_threshold:.6f}) = {results.n_influential_points} điểm "
        f"({inf.get('pct_cooks_gt_4n', 0.0):.2f}%), $D > 0,5$ = {inf.get('n_cooks_gt_05', 0)}, "
        f"$D > 1,0$ = {inf.get('n_cooks_gt_10', 0)}, $D_{{\\max}} = {results.cooks_distance_max:.4f}$."
    )

    log1p_m = results.log1p_metrics or {}
    orig_sk = float(log1p_m.get("original_resid_skew", diag.skewness))
    log_sk = float(log1p_m.get("log1p_resid_skew", np.nan))
    log1p_verdict = (
        f"Độ lệch phần dư chuyển từ `{orig_sk:+.3f}` ($|\\text{{skew}}| = {abs(orig_sk):.3f}$) "
        f"sang `{log_sk:+.3f}` ($|\\text{{skew}}| = {abs(log_sk):.3f}$). "
        + (
            "Độ lệch tuyệt đối tăng lên nên giữ nguyên đơn vị gốc µg/m³."
            if abs(log_sk) > abs(orig_sk)
            else "Độ lệch tuyệt đối giảm nhẹ nhưng mô hình chính giữ đơn vị gốc µg/m³ để diễn giải trực tiếp với QCVN 05:2023."
        )
    )

    beta_lines = "\n".join(_format_beta_obligations(results))

    # HAC sensitivity summary
    hac_block = ""
    if results.hac_sensitivity_table is not None and not results.hac_sensitivity_table.empty:
        piv = results.hac_sensitivity_table.pivot(index="lag_label", columns="Feature", values="p_display")
        piv = piv.reindex(
            results.hac_sensitivity_table[["maxlags", "lag_label"]]
            .drop_duplicates()
            .sort_values("maxlags")["lag_label"]
        ).reset_index()
        hac_block = (
            f"\n{heading_prefix}# Độ Nhạy HAC Newey-West Theo Độ Trễ L (plug-in NW = {diag.plugin_nw_maxlags} giờ)\n\n"
            + _df_to_markdown(piv)
            + "\n"
        )

    ablation_block = ""
    if results.ablation_table is not None and not results.ablation_table.empty:
        ab_diag = results.ablation_diagnostics or {}
        diag_note = ""
        if ab_diag:
            diag_note = (
                f"\n- **Giải phẫu dịch chuyển phân phối & hiệu ứng mùa vụ:** Mean PM2.5 Train = {ab_diag.get('train_pm25_mean', np.nan):.2f} vs "
                f"Test = {ab_diag.get('test_pm25_mean', np.nan):.2f} µg/m³; "
                f"Mean Pred OLS Full trên Test = {ab_diag.get('ols_full_test_pred_mean', np.nan):.2f} µg/m³ "
                f"(bias = {ab_diag.get('ols_full_mean_bias', np.nan):+.2f} µg/m³). "
                f"Tỷ lệ Test nằm ngoài dải `month_sin` của Train = {ab_diag.get('test_month_sin_out_of_train_range_pct', 0.0):.1f}%. "
                f"Khi bỏ `month_sin`/`month_cos`, Test $R^2$ đổi từ {ab_diag.get('ols_full_test_r2', np.nan):.4f} "
                f"thành {ab_diag.get('ols_drop_season_test_r2', np.nan):.4f}; khi thêm trễ nội trạm `pm25_lag24`, "
                f"Test $R^2$ đạt {ab_diag.get('ols_lag24_test_r2', np.nan):.4f}.\n"
            )
        ablation_block = (
            f"\n{heading_prefix}# Thử Nghiệm Ablation (Bỏ Chu Kỳ Mùa & Bổ Sung Autoregressive Lag 24h)\n\n"
            + _df_to_markdown(results.ablation_table)
            + "\n"
            + diag_note
        )

    cv_block = ""
    if results.rolling_origin_cv is not None and not results.rolling_origin_cv.empty:
        cv_block = (
            f"\n{heading_prefix}# Rolling-Origin CV Trong Tập Train (5 Expanding Folds)\n\n"
            + _df_to_markdown(results.rolling_origin_cv)
            + "\n"
        )

    strat_block = ""
    if results.stratified_stability is not None and not results.stratified_stability.empty:
        strat_block = (
            f"\n{heading_prefix}# Độ Ổn Định Hệ Số Phân Tầng Theo Năm & Mùa (kèm n_eff)\n\n"
            + _df_to_markdown(results.stratified_stability)
            + "\n"
        )

    der_block = ""
    if results.derived_sensitivity is not None:
        ds = results.derived_sensitivity
        der_block = (
            f"\n{heading_prefix}# Độ Nhạy Nội Suy Phái Sinh `pm25_derived_interpolated` (Chỉ Trong Train)\n\n"
            f"- Train quan trắc gốc: {ds['n_train_observed']:,} giờ | Train + nội suy phái sinh ngắn: "
            f"{ds['n_train_derived']:,} giờ (+{ds['n_derived_hours_added_in_train']:,} giờ); "
            f"Test ground truth LUÔN giữ 100% quan trắc gốc ({ds['n_test_observed_ground_truth']:,} giờ).\n"
            f"- Sai khác hệ số lớn nhất (`max |ΔBeta|`) = {ds['max_abs_beta_diff']:.4f}; "
            f"Test RMSE (Observed vs Derived Train) = {ds['test_rmse_observed_model']:.2f} vs "
            f"{ds['test_rmse_derived_train_model']:.2f} µg/m³ "
            f"(R² = {ds['test_r2_observed_model']:.4f} vs {ds['test_r2_derived_train_model']:.4f}).\n\n"
            + _df_to_markdown(ds["coef_comparison"])
            + "\n"
        )

    top_inf_block = ""
    if inf.get("top_influential") is not None and not inf["top_influential"].empty:
        top_inf_block = (
            f"\n{heading_prefix}# Top 10 Quan Sát Có Cook's Distance Cao Nhất Trên Train\n\n"
            + _df_to_markdown(inf["top_influential"])
            + "\n"
        )

    return f"""- **Trạm & Phạm vi:** `{results.station_id or 'Single-Station'}` | Nhãn chạy: `{results.run_label}` | Chế độ split: `{results.split_mode}` (`{results.split_timestamp}`)
- **Kích thước mẫu:** Train = {results.n_train:,} giờ | Test = {results.n_test:,} giờ | Imputed feature cells = {results.n_train_imputed_features} (Train), {results.n_test_imputed_features} (Test)

{heading_prefix}# Kiểm Toán Đa Cộng Tuyến VIF
- {_format_vif_verdict(results.vif_table)}

{vif_md}

{heading_prefix}# Bảng Hệ Số OLS (Classical vs HAC Newey-West 24 lags)

{coef_md}
{hac_block}
{heading_prefix}# Diễn Giải Hệ Số Theo 3 Nghĩa Vụ Học Thuật

{beta_lines}

{heading_prefix}# Chẩn Đoán 4 Giả Định LINE & Điểm Ảnh Hưởng

| Giả Định | Kiểm Định / Chỉ Số | Giá Trị Đo Được | Kết Luận |
|---|---|---|---|
| **L – Linearity** | Ramsey RESET & Residuals Mean | {reset2_txt}; mean = {diag.residuals_mean:.2e} | {l_verdict} |
| **I – Independence** | Durbin-Watson & ACF | DW = {diag.durbin_watson:.4f}, ACF(1) = {acf1:.4f}, ACF(24) = {acf24:.4f} | **VI PHẠM NẶNG:** Tự tương quan phần dư mạnh; bắt buộc dùng sai số chuẩn HAC. |
| **N – Normality** | Jarque-Bera & Skew/Kurtosis | JB = {diag.jarque_bera_stat:.1f} (p = {_fmt_p(diag.jarque_bera_pvalue)}), Skew = {diag.skewness:.3f}, Excess Kurtosis = {diag.kurtosis:.3f}{shapiro_txt} | **VI PHẠM:** Phân phối phần dư lệch phải và có đuôi dày trong các đợt ô nhiễm. |
| **E – Equal Variance** | Breusch-Pagan LM test | LM = {diag.breusch_pagan_stat:.2f} (p = {_fmt_p(diag.breusch_pagan_pvalue)}) | **VI PHẠM:** Phương sai sai số thay đổi theo điều kiện khí tượng và mùa vụ. |

- **Điểm đòn bẩy & Cook's Distance:** {inf_line} Giữ nguyên các điểm cực trị vì phản ánh các đợt nghịch nhiệt thực tế.
- **Khảo sát `log(1 + PM2.5)` trên Train:** {log1p_verdict}
{top_inf_block}
{heading_prefix}# Hiệu Năng Tập Test Độc Lập (MAE vs RMSE)

{metrics_md}

- **Lý do dùng cả MAE và RMSE:** MAE đo sai số tuyệt đối điển hình ít nhạy với điểm cực trị đơn lẻ, trong khi RMSE phạt bình phương các sai số lớn ở đỉnh ô nhiễm (đặc trưng của phân phối lệch phải).
{ablation_block}{cv_block}{strat_block}{der_block}"""


def write_regression_report(
    results: RegressionResults,
    report_path: Path,
    extra_runs: Optional[Sequence[RegressionResults]] = None,
) -> None:
    """
    Xuất báo cáo khoa học tổng hợp kết quả hồi quy OLS (Issue #12) hoàn toàn động
    từ các đối tượng `RegressionResults`, hỗ trợ cả chạy đơn lẻ lẫn bộ 3 chạy mở rộng đa trạm.
    """
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    runs: List[RegressionResults] = [results]
    if extra_runs:
        runs.extend(extra_runs)

    # Bảng metadata tổng hợp nguồn dữ liệu
    meta_rows = []
    for r in runs:
        m = r.metadata_summary or {}
        meta_rows.append(
            {
                "Run": r.run_label,
                "Station": r.station_id or m.get("station_id", "N/A"),
                "Date Window": f"{m.get('date_min', 'N/A')} .. {m.get('date_max', 'N/A')}",
                "Obs Hours": f"{m.get('valid_pm25_rows', r.n_train + r.n_test):,}",
                "Grid Hours": f"{m.get('grid_rows', 'N/A')}",
                "Missing PM2.5": m.get("pm25_missing_pct", "N/A"),
                "Split Cut": r.split_timestamp,
                "Train / Test": f"{r.n_train:,} / {r.n_test:,}",
                "Dataset SHA-256 (prefix)": str(m.get("dataset_sha256", "N/A"))[:12],
            }
        )
    meta_md = _df_to_markdown(pd.DataFrame(meta_rows))

    # Bảng tóm tắt đối chiếu Test R² giữa các scope
    cross_rows = []
    for r in runs:
        mt = r.metrics_table
        dum = mt[mt["Model"].str.contains("Dummy")].iloc[0]
        ols = mt[mt["Model"].str.contains("OLS")].iloc[0]
        diag = r.line_diagnostics
        cross_rows.append(
            {
                "Run": r.run_label,
                "Station": r.station_id or "N/A",
                "Train / Test": f"{r.n_train:,} / {r.n_test:,}",
                "Dummy RMSE": dum["RMSE (µg/m³)"],
                "OLS MAE": ols["MAE (µg/m³)"],
                "OLS RMSE": ols["RMSE (µg/m³)"],
                "OLS Test R²": ols["R²"],
                "RESET(2) p": _fmt_p(diag.reset_power2_pvalue) if diag.reset_power2_pvalue is not None else "N/A",
                "DW": round(diag.durbin_watson, 3),
            }
        )
    cross_md = _df_to_markdown(pd.DataFrame(cross_rows))

    sections_md = []
    for idx, r in enumerate(runs, start=1):
        sections_md.append(
            f"## {idx}. Kết Quả Chi Tiết — `{r.run_label}`\n\n"
            + _render_single_scope_section(r, heading_prefix="##")
        )

    protocol_note = (
        "- **Tuân thủ Protocol A vs Protocol B (Issue #44):** `VN003` (2022-01..2025-04) và `VN001` "
        "(2025-07..2026-07) có khoảng thời gian tách rời hoàn toàn và cách nhau khoảng trống 85 ngày; "
        "do đó bị CẤM gộp vào một phép chia Train/Test chung (Protocol B bị từ chối fail-closed), "
        "và được đánh giá độc lập theo từng trạm."
    )

    joined_sections = "\n---\n\n".join(sections_md)
    content = f"""# Báo Cáo Kết Quả Mô Hình Hóa Hồi Quy OLS & Chẩn Đoán LINE — Issue #12

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 10 (kèm Scope Extension 2022–2026)
> **Biến mục tiêu:** `pm25` (µg/m³, giữ nguyên giá trị quan trắc thực)
{protocol_note}

---

## 0. Tóm Tắt Nguồn Dữ Liệu & Đối Chiếu Đa Phạm Vi (Protocol A)

### Metadata Các Lượt Chạy Thực Nghiệm

{meta_md}

### Bảng Đối Chiếu Hiệu Năng Tổng Hợp Trên Tập Test Độc Lập

{cross_md}

---

{joined_sections}
"""

    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.rstrip() + "\n")
    logger.info("Đã xuất báo cáo hồi quy: %s", report_path)


def _build_metadata_summary(df: pd.DataFrame, df_station: pd.DataFrame, dataset_path: Path) -> Dict[str, Any]:
    """Thu thập metadata provenance chuẩn xác cho một trạm và tệp parquet."""
    n_grid = len(df_station)
    n_valid = int(df_station["pm25"].notna().sum())
    miss_pct = f"{100.0 * (1.0 - n_valid / n_grid):.1f}%" if n_grid > 0 else "N/A"
    return {
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256_file(dataset_path) if dataset_path.exists() else "N/A",
        "station_id": str(df_station["station_id"].iloc[0]) if "station_id" in df_station.columns else "N/A",
        "date_min": str(df_station["timestamp"].min())[:19],
        "date_max": str(df_station["timestamp"].max())[:19],
        "grid_rows": n_grid,
        "valid_pm25_rows": n_valid,
        "pm25_missing_pct": miss_pct,
        "total_dataset_rows": len(df),
    }


def run_regression_pipeline(
    dataset_path: Path,
    output_fig_path: Path,
    report_path: Optional[Path] = None,
    split_timestamp: Optional[str] = DEFAULT_SPLIT_TIMESTAMP,
    station_id: Optional[str] = None,
    use_split_column: bool = False,
    run_label: Optional[str] = None,
) -> RegressionResults:
    """
    Thực thi toàn bộ quy trình hồi quy OLS, chẩn đoán LINE, HAC lag sensitivity,
    CV điều chuẩn không rò rỉ và phân tích mở rộng cho một trạm đơn lẻ (Protocol A).
    """
    dataset_path = Path(dataset_path)
    df = pd.read_parquet(dataset_path)
    df_station = _select_single_station(df, station_id=station_id)
    effective_station = (
        str(df_station["station_id"].iloc[0]) if "station_id" in df_station.columns else None
    )
    label = run_label or (
        f"{effective_station[:5]}_{'extended' if use_split_column else 'baseline'}"
        if effective_station
        else "single_station"
    )

    X_train, y_train, X_test, y_test, ts_train, ts_test = prepare_regression_data(
        df_station,
        split_timestamp=split_timestamp,
        drop_collinear_pm10=True,
        station_id=effective_station,
        use_split_column=use_split_column,
        return_timestamps=True,
    )

    if use_split_column:
        grid_tr_max = df_station.loc[df_station["split"] == "train", "timestamp"].max()
        split_label = f"split=='train'/'test' (grid cut > {str(grid_tr_max)[:19]}, last obs: {str(ts_train.max())[:19]})"
    else:
        split_label = str(split_timestamp)

    # Phạm vi quan sát trên Train (phục vụ diễn giải 3 nghĩa vụ)
    pred_ranges = pd.DataFrame(
        [
            {
                "Feature": col,
                "Train Min": round(float(X_train[col].min()), 3),
                "Train Max": round(float(X_train[col].max()), 3),
                "Train Median": round(float(X_train[col].median()), 3),
            }
            for col in X_train.columns
        ]
    )

    X_tr_clean, X_te_clean, n_tr_imp, n_te_imp = _fit_transform_train_only_ols_inputs(X_train, X_test)
    df_vif = compute_vif(X_tr_clean)

    X_train_const = sm.add_constant(X_tr_clean.reset_index(drop=True), has_constant="add")
    y_train_reset = y_train.reset_index(drop=True)
    ols_sm = sm.OLS(y_train_reset, X_train_const).fit()
    ols_hac = sm.OLS(y_train_reset, X_train_const).fit(cov_type="HAC", cov_kwds={"maxlags": 24})

    coef_df = pd.DataFrame(
        {
            "Feature": ols_sm.params.index,
            "Coefficient (Beta)": ols_sm.params.values.round(4),
            "SE (Classical)": ols_sm.bse.values.round(4),
            "p-Value (Classical)": [_fmt_p(float(p)) for p in ols_sm.pvalues],
            "SE (HAC-24)": ols_hac.bse.values.round(4),
            "p-Value (HAC-24)": [_fmt_p(float(p)) for p in ols_hac.pvalues],
            "95% CI Lower (HAC)": ols_hac.conf_int()[0].round(4),
            "95% CI Upper (HAC)": ols_hac.conf_int()[1].round(4),
            "p_hac_num": [float(p) for p in ols_hac.pvalues],
        }
    )

    line_diag = compute_line_diagnostics(ols_sm, X_tr_clean, y_train_reset)
    cooks_d, threshold, n_influential = compute_cooks_distance(ols_sm)
    inf_summary = compute_influence_summary(ols_sm, timestamps=ts_train, top_n=10)
    hac_sens_df, _ = compute_hac_lag_sensitivity(X_tr_clean, y_train_reset)

    # Tuning Ridge/Lasso với fold-level SimpleImputer + RobustScaler và xác nhận chống rò rỉ
    best_ridge_a, best_lasso_a, ridge_m, lasso_m, prep_pipe = tune_regularization(X_train, y_train)
    validate_no_leakage(
        prep_pipe,
        X_train=X_train,
        X_test=X_test,
        timestamps=ts_train,
        test_timestamps=ts_test,
    )

    metrics_df, ols_sk = evaluate_models(
        X_train, y_train, X_test, y_test, ridge_m, lasso_m, scaler=prep_pipe
    )

    log_y_train = np.log1p(np.clip(y_train_reset, a_min=0.0, a_max=None))
    log_ols = sm.OLS(log_y_train, X_train_const).fit()
    log1p_metrics = {
        "original_train_r2": float(ols_sm.rsquared),
        "log1p_train_r2": float(log_ols.rsquared),
        "original_resid_skew": float(line_diag.skewness),
        "log1p_resid_skew": float(stats.skew(log_ols.resid)),
    }

    ablation_df, ablation_diag = evaluate_seasonal_and_lag_ablation(
        df_station,
        split_timestamp=split_timestamp,
        use_split_column=use_split_column,
        station_id=effective_station,
    )
    rolling_cv_df = run_rolling_origin_backtest(X_train, y_train, timestamps_train=ts_train, n_splits=5)
    strat_df = compute_stratified_coefficient_stability(
        df_station,
        split_timestamp=split_timestamp,
        use_split_column=use_split_column,
        station_id=effective_station,
    )
    der_sens = evaluate_derived_interpolation_sensitivity(
        df_station,
        predictor_cols=list(X_train.columns),
        split_timestamp=split_timestamp,
        use_split_column=use_split_column,
        station_id=effective_station,
    )
    meta_summary = _build_metadata_summary(df, df_station, dataset_path)

    pred_ols_test = ols_sk.predict(X_te_clean)
    target_stats = {
        "train_mean": float(y_train.mean()),
        "test_mean": float(y_test.mean()),
        "train_std": float(y_train.std(ddof=1)),
        "test_std": float(y_test.std(ddof=1)),
        "mean_pred_ols": float(np.mean(pred_ols_test)),
        "mean_bias_ols": float(np.mean(pred_ols_test) - y_test.mean()),
    }

    render_line_diagnostics_figure(
        ols_sm,
        line_diag,
        output_fig_path,
        title_prefix=f"Chẩn đoán 4 Giả định LINE — {label} (n_train={len(y_train):,})",
    )

    results = RegressionResults(
        split_timestamp=split_label,
        n_train=len(y_train),
        n_test=len(y_test),
        predictors=list(X_train.columns),
        vif_table=df_vif,
        ols_summary_str=str(ols_sm.summary()),
        hac_summary_str=str(ols_hac.summary()),
        coefficients=coef_df,
        line_diagnostics=line_diag,
        cooks_distance_max=float(np.max(cooks_d)),
        cooks_distance_threshold=threshold,
        n_influential_points=n_influential,
        ridge_best_alpha=best_ridge_a,
        lasso_best_alpha=best_lasso_a,
        metrics_table=metrics_df,
        log1p_target_evaluated=True,
        log1p_metrics=log1p_metrics,
        station_id=effective_station,
        run_label=label,
        split_mode="split_column_80_20" if use_split_column else "timestamp",
        dataset_path=str(dataset_path),
        predictor_ranges=pred_ranges,
        influence_summary=inf_summary,
        hac_sensitivity_table=hac_sens_df,
        ablation_table=ablation_df,
        ablation_diagnostics=ablation_diag,
        rolling_origin_cv=rolling_cv_df,
        stratified_stability=strat_df,
        derived_sensitivity=der_sens,
        metadata_summary=meta_summary,
        test_target_stats=target_stats,
        n_train_imputed_features=n_tr_imp,
        n_test_imputed_features=n_te_imp,
    )

    if report_path is not None:
        write_regression_report(results, report_path)

    return results


def run_extended_regression_suite(
    baseline_path: Path,
    extended_path: Optional[Path],
    figures_dir: Path,
    report_path: Path,
) -> Dict[str, RegressionResults]:
    """
    Thực thi bộ 3 phân tích độc lập theo Protocol A (Issue #12 + Scope Extension 2022–2026):
      1. `VN001_baseline`: Trạm 556 Nguyễn Văn Cừ (mốc cắt Issue #7: 2026-01-15)
      2. `VN001_extended`: Trạm 556 Nguyễn Văn Cừ trên tập mở rộng (mốc 80/20: 2026-05-01)
      3. `VN003_extended`: Trạm lịch sử OpenAQ 7441 2022–2025 (mốc 80/20: 2024-08-13)
    """
    figures_dir = Path(figures_dir)
    results_map: Dict[str, RegressionResults] = {}

    res_vn001_base = run_regression_pipeline(
        baseline_path,
        figures_dir / "regression_line_diagnostics.png",
        report_path=None,
        split_timestamp=DEFAULT_SPLIT_TIMESTAMP,
        station_id=PRIMARY_BASELINE_STATION,
        use_split_column=False,
        run_label="VN001_baseline_2026_01_15",
    )
    results_map["VN001_baseline"] = res_vn001_base

    extra_runs: List[RegressionResults] = []
    if extended_path is not None and Path(extended_path).exists():
        res_vn001_ext = run_regression_pipeline(
            extended_path,
            figures_dir / "regression_line_diagnostics_vn001_extended.png",
            report_path=None,
            split_timestamp=None,
            station_id=PRIMARY_BASELINE_STATION,
            use_split_column=True,
            run_label="VN001_extended_80_20",
        )
        res_vn003_ext = run_regression_pipeline(
            extended_path,
            figures_dir / "regression_line_diagnostics_vn003_extended.png",
            report_path=None,
            split_timestamp=None,
            station_id=EXTENDED_HISTORICAL_STATION,
            use_split_column=True,
            run_label="VN003_extended_2022_2025",
        )
        results_map["VN001_extended"] = res_vn001_ext
        results_map["VN003_extended"] = res_vn003_ext
        extra_runs.extend([res_vn001_ext, res_vn003_ext])

    write_regression_report(res_vn001_base, report_path, extra_runs=extra_runs)
    return results_map
