"""
src/regression.py — Mô hình hóa Hồi quy Tuyến tính OLS, Chẩn đoán LINE & Điều hòa (Issue #12, Week 10).

Tuân thủ nghiêm ngặt chuẩn mực học thuật INFO3020:
  1. Kế thừa điểm cắt Train/Test theo chuỗi thời gian tuyến tính (2026-01-15 00:00:00+07:00).
  2. Khảo sát biến đổi mục tiêu ứng viên Y = log(1 + PM2.5) trên tập Train.
  3. Huấn luyện Dummy Regressor Baseline và mô hình OLS đa biến.
  4. Chẩn đoán đầy đủ 4 giả định LINE trên phần dư:
     - L (Linearity): Residuals vs Fitted values & LOWESS.
     - I (Independence): Durbin-Watson statistic & biểu đồ ACF phần dư.
     - N (Normality): Q-Q plot & kiểm định Jarque-Bera / Shapiro-Wilk.
     - E (Equal Variance): Kiểm định Breusch-Pagan & đồ thị Scale-Location.
  5. Đánh giá đa cộng tuyến qua chỉ số VIF (loại trừ biến pm10 do r = 0.9727) và điểm ảnh hưởng Cook's Distance.
  6. Huấn luyện điều hòa Ridge (L2) & Lasso (L1) với siêu tham số alpha tối ưu qua TimeSeriesSplit trên Train.
  7. Đánh giá độc lập trên tập Test: MAE, RMSE, R², Adjusted R² cạnh Baseline.
  8. Diễn giải hệ số beta theo chuẩn 3 nghĩa vụ: liên hệ quan sát, ceteris paribus, giới hạn miền giá trị.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import RobustScaler
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import acf

logger = logging.getLogger(__name__)

# Ranh giới phân chia thời gian tuyến tính kế thừa từ Issue #7
DEFAULT_SPLIT_TIMESTAMP: str = "2026-01-15 00:00:00+07:00"

# Biến giải thích mặc định: Các yếu tố khí tượng bề mặt và chu kỳ thời gian
# Biến `pm10` BỊ LOẠI KHỎI feature mặc định vì r(pm25, pm10) = 0.9727 gây đa cộng tuyến nghiêm trọng (VIF > 30)
# Biến `pm25_was_missing` BỊ LOẠI vì là target-derived leakage.
# Biến `is_high_humidity_fog` BỊ LOẠI vì không có giá trị marginal độc lập.
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


@dataclass
class RegressionResults:
    """Tập hợp đầy đủ kết quả thực nghiệm của bài toán hồi quy Issue #12."""
    split_timestamp: str
    n_train: int
    n_test: int
    predictors: List[str]
    vif_table: pd.DataFrame
    ols_summary_str: str
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


def prepare_regression_data(
    df: pd.DataFrame,
    split_timestamp: str = DEFAULT_SPLIT_TIMESTAMP,
    target_col: str = "pm25",
    predictor_cols: Optional[List[str]] = None,
    drop_collinear_pm10: bool = True,
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Chuẩn bị dữ liệu huấn luyện và kiểm thử theo thứ tự thời gian tuyến tính.

    Quy tắc an toàn rò rỉ:
      - Phân chia tuyến tính: timestamp < split_timestamp là Train, >= split_timestamp là Test.
      - Loại bỏ các dòng mà target (pm25) bị khuyết (NaN).
      - Điền giá trị khuyết cho biến giải thích X bằng median được tính duy nhất trên Train.
    """
    if target_col not in df.columns:
        raise KeyError(f"Không tìm thấy cột mục tiêu '{target_col}' trong DataFrame.")

    if predictor_cols is None:
        predictor_cols = list(REGRESSION_PREDICTORS)

    if drop_collinear_pm10 and "pm10" in predictor_cols:
        predictor_cols.remove("pm10")

    missing_cols = [c for c in predictor_cols if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Các cột giải thích thiếu trong DataFrame: {missing_cols}")

    # Đảm bảo sắp xếp thời gian tăng dần
    df_sorted = df.sort_values("timestamp").copy()

    # Chỉ giữ các dòng có target hợp lệ để huấn luyện và đánh giá
    df_valid = df_sorted[df_sorted[target_col].notna()].copy()

    split_dt = pd.Timestamp(split_timestamp)
    train_mask = df_valid["timestamp"] < split_dt
    test_mask = df_valid["timestamp"] >= split_dt

    train_df = df_valid[train_mask].copy()
    test_df = df_valid[test_mask].copy()

    if len(train_df) == 0 or len(test_df) == 0:
        raise ValueError(f"Phân chia thời gian với mốc {split_timestamp} tạo ra tập rỗng.")

    X_train = train_df[predictor_cols].copy()
    y_train = train_df[target_col].copy()
    X_test = test_df[predictor_cols].copy()
    y_test = test_df[target_col].copy()

    # Impute biến giải thích bằng median của Train (chống rò rỉ)
    medians = X_train.median()
    X_train = X_train.fillna(medians)
    X_test = X_test.fillna(medians)

    return X_train, y_train, X_test, y_test


def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    """
    Tính chỉ số Phóng đại Phương sai VIF (Variance Inflation Factor) cho các biến giải thích.
    VIF > 5.0 là cảnh báo heuristic về đa cộng tuyến.
    """
    X_with_const = sm.add_constant(X)
    vif_data = []
    for i, col in enumerate(X_with_const.columns):
        if col == "const":
            continue
        vif_val = variance_inflation_factor(X_with_const.values, i)
        vif_data.append({"Feature": col, "VIF": vif_val})

    df_vif = pd.DataFrame(vif_data).sort_values("VIF", ascending=False).reset_index(drop=True)
    return df_vif


def compute_line_diagnostics(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
    X: pd.DataFrame,
    y: pd.Series,
    max_lags: int = 48,
) -> LINEDiagnostics:
    """
    Thực hiện quy trình chẩn đoán toàn diện 4 giả định LINE trên phần dư OLS.
    """
    residuals = ols_model.resid
    fitted = ols_model.fittedvalues

    # L - Linearity
    res_mean = float(np.mean(residuals))
    res_fit_corr = float(stats.pearsonr(residuals, fitted)[0])

    # I - Independence
    dw_stat = float(sm.stats.stattools.durbin_watson(residuals))
    acf_vals = acf(residuals, nlags=max_lags, fft=True)

    # N - Normality
    res_skew = float(stats.skew(residuals))
    res_kurt = float(stats.kurtosis(residuals))
    jb_stat, jb_p = stats.jarque_bera(residuals)
    jb_stat, jb_p = float(jb_stat), float(jb_p)

    shapiro_stat, shapiro_p = None, None
    if len(residuals) <= 5000:
        s_stat, s_p = stats.shapiro(residuals)
        shapiro_stat, shapiro_p = float(s_stat), float(s_p)

    # E - Equal Variance (Homoscedasticity)
    X_const = sm.add_constant(X)
    bp_test = het_breuschpagan(residuals, X_const)
    bp_lm_stat = float(bp_test[0])
    bp_lm_pvalue = float(bp_test[1])

    return LINEDiagnostics(
        residuals_mean=res_mean,
        residuals_fitted_corr=res_fit_corr,
        durbin_watson=dw_stat,
        acf_values=acf_vals,
        acf_lags=max_lags,
        skewness=res_skew,
        kurtosis=res_kurt,
        jarque_bera_stat=jb_stat,
        jarque_bera_pvalue=jb_p,
        shapiro_stat=shapiro_stat,
        shapiro_pvalue=shapiro_p,
        breusch_pagan_stat=bp_lm_stat,
        breusch_pagan_pvalue=bp_lm_pvalue,
    )


def compute_cooks_distance(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
) -> Tuple[np.ndarray, float, int]:
    """
    Tính khoảng cách Cook (Cook's Distance) để phát hiện điểm đòn bẩy có ảnh hưởng quá mức.
    Ngưỡng heuristic: D_i > 4 / n.
    """
    influence = ols_model.get_influence()
    cooks_d = influence.cooks_distance[0]
    n = len(cooks_d)
    threshold = 4.0 / n
    n_influential = int(np.sum(cooks_d > threshold))
    max_d = float(np.max(cooks_d))
    return cooks_d, threshold, n_influential


def tune_regularization(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_splits: int = 5,
    alphas: Optional[np.ndarray] = None,
) -> Tuple[float, float, Ridge, Lasso]:
    """
    Dò tìm siêu tham số alpha tối ưu cho Ridge và Lasso HOÀN TOÀN trên tập Train
    sử dụng TimeSeriesSplit cross-validation (chống rò rỉ dữ liệu chuỗi thời gian).
    """
    if alphas is None:
        alphas = np.logspace(-3, 3, 50)

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X_train)

    tscv = TimeSeriesSplit(n_splits=n_splits)

    # 1. Ridge Tuning
    best_ridge_alpha = float(alphas[0])
    best_ridge_rmse = float("inf")

    for alpha in alphas:
        rmses = []
        for tr_idx, val_idx in tscv.split(X_scaled):
            model = Ridge(alpha=alpha, random_state=42)
            model.fit(X_scaled[tr_idx], y_train.iloc[tr_idx])
            pred = model.predict(X_scaled[val_idx])
            rmse = np.sqrt(mean_squared_error(y_train.iloc[val_idx], pred))
            rmses.append(rmse)
        mean_rmse = float(np.mean(rmses))
        if mean_rmse < best_ridge_rmse:
            best_ridge_rmse = mean_rmse
            best_ridge_alpha = float(alpha)

    # 2. Lasso Tuning
    best_lasso_alpha = float(alphas[0])
    best_lasso_rmse = float("inf")

    for alpha in alphas:
        rmses = []
        for tr_idx, val_idx in tscv.split(X_scaled):
            model = Lasso(alpha=alpha, random_state=42, max_iter=2000)
            model.fit(X_scaled[tr_idx], y_train.iloc[tr_idx])
            pred = model.predict(X_scaled[val_idx])
            rmse = np.sqrt(mean_squared_error(y_train.iloc[val_idx], pred))
            rmses.append(rmse)
        mean_rmse = float(np.mean(rmses))
        if mean_rmse < best_lasso_rmse:
            best_lasso_rmse = mean_rmse
            best_lasso_alpha = float(alpha)

    # Fit final models on full scaled train
    final_ridge = Ridge(alpha=best_ridge_alpha, random_state=42)
    final_ridge.fit(X_scaled, y_train)

    final_lasso = Lasso(alpha=best_lasso_alpha, random_state=42, max_iter=2000)
    final_lasso.fit(X_scaled, y_train)

    return best_ridge_alpha, best_lasso_alpha, final_ridge, final_lasso


def evaluate_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    ridge_model: Ridge,
    lasso_model: Lasso,
) -> Tuple[pd.DataFrame, LinearRegression]:
    """
    Đo lường hiệu năng tổng thể trên tập TEST độc lập:
    So sánh Baseline (Mean Dummy) vs OLS vs Ridge vs Lasso.
    """
    # 1. Baseline
    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    pred_dummy = dummy.predict(X_test)

    # 2. OLS
    ols_sk = LinearRegression()
    ols_sk.fit(X_train, y_train)
    pred_ols = ols_sk.predict(X_test)

    # 3. Ridge & Lasso (cần scaler)
    scaler = RobustScaler()
    scaler.fit(X_train)
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
        # Adjusted R²
        adj_r2 = float(1.0 - (1.0 - r2) * (n_test - 1) / (n_test - p - 1)) if n_test > p + 1 else np.nan
        metrics.append({
            "Model": name,
            "MAE (µg/m³)": round(mae, 2),
            "RMSE (µg/m³)": round(rmse, 2),
            "R²": round(r2, 4),
            "Adjusted R²": round(adj_r2, 4),
        })

    metrics_df = pd.DataFrame(metrics)
    return metrics_df, ols_sk


def render_line_diagnostics_figure(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
    diagnostics: LINEDiagnostics,
    output_path: Path,
) -> None:
    """
    Xuất biểu đồ 4 ô kiểm định giả định LINE đạt chuẩn Edward Tufte / William Cleveland:
      1. Linearity: Residuals vs Fitted values kèm đường tham chiếu 0.
      2. Independence: Biểu đồ ACF phần dư với dải tin cậy 95% Bartlett.
      3. Normality: Normal Q-Q plot của phần dư chuẩn hóa.
      4. Equal Variance: Scale-Location plot (Căn bậc hai phần dư chuẩn hóa vs Fitted).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(13, 10), dpi=300)
    residuals = ols_model.resid
    fitted = ols_model.fittedvalues
    std_residuals = (residuals - residuals.mean()) / residuals.std(ddof=1)

    # Màu sắc tối giản, độ tương phản cao theo Tufte
    c_point = "#2b5c8f"
    c_line = "#d95f02"

    # --- 1. Linearity (Residuals vs Fitted) ---
    ax1 = axes[0, 0]
    ax1.scatter(fitted, residuals, alpha=0.35, s=16, color=c_point, edgecolors="none")
    ax1.axhline(0, color="black", linestyle="--", linewidth=1.0, alpha=0.8)
    ax1.set_title("1. Linearity: Residuals vs Fitted Values\n(Kiểm tra độ tuyến tính)", fontsize=11, fontweight="bold", pad=8)
    ax1.set_xlabel("Giá trị dự báo Fitted (µg/m³)", fontsize=9)
    ax1.set_ylabel("Phần dư Residuals (µg/m³)", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.5)

    # --- 2. Independence (ACF of Residuals) ---
    ax2 = axes[0, 1]
    lags = np.arange(len(diagnostics.acf_values))
    ax2.vlines(lags, [0], diagnostics.acf_values, color=c_point, linewidth=1.5)
    ax2.scatter(lags, diagnostics.acf_values, color=c_point, s=18)
    ax2.axhline(0, color="black", linestyle="-", linewidth=0.8)
    # 95% Bartlett bounds
    ci_bound = 1.96 / np.sqrt(len(residuals))
    ax2.axhline(ci_bound, color=c_line, linestyle="--", linewidth=1.0, label="95% CI (Bartlett)")
    ax2.axhline(-ci_bound, color=c_line, linestyle="--", linewidth=1.0)
    ax2.set_title(f"2. Independence: Autocorrelation Function (ACF)\n(Durbin-Watson = {diagnostics.durbin_watson:.2f})", fontsize=11, fontweight="bold", pad=8)
    ax2.set_xlabel("Độ trễ Lag (Giờ)", fontsize=9)
    ax2.set_ylabel("Hệ số tự tương quan ACF", fontsize=9)
    ax2.set_ylim(-0.3, 1.05)
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right", frameon=True, fontsize=8)

    # --- 3. Normality (Normal Q-Q Plot) ---
    ax3 = axes[1, 0]
    (osm, osr), (slope, intercept, r) = stats.probplot(std_residuals, dist="norm")
    ax3.scatter(osm, osr, alpha=0.35, s=16, color=c_point, edgecolors="none")
    ax3.plot(osm, slope * np.array(osm) + intercept, color=c_line, linewidth=1.2, label=f"R² = {r**2:.3f}")
    ax3.set_title(f"3. Normality: Normal Q-Q Plot\n(Skew = {diagnostics.skewness:.2f}, Kurtosis = {diagnostics.kurtosis:.2f})", fontsize=11, fontweight="bold", pad=8)
    ax3.set_xlabel("Phân vị lý thuyết phân phối Chuẩn", fontsize=9)
    ax3.set_ylabel("Phần dư chuẩn hóa quan sát", fontsize=9)
    ax3.grid(True, linestyle=":", alpha=0.5)
    ax3.legend(loc="upper left", frameon=True, fontsize=8)

    # --- 4. Equal Variance (Scale-Location Plot) ---
    ax4 = axes[1, 1]
    sqrt_abs_std_res = np.sqrt(np.abs(std_residuals))
    ax4.scatter(fitted, sqrt_abs_std_res, alpha=0.35, s=16, color=c_point, edgecolors="none")
    ax4.set_title(f"4. Equal Variance: Scale-Location Plot\n(Breusch-Pagan p = {diagnostics.breusch_pagan_pvalue:.2e})", fontsize=11, fontweight="bold", pad=8)
    ax4.set_xlabel("Giá trị dự báo Fitted (µg/m³)", fontsize=9)
    ax4.set_ylabel(r"$\sqrt{|\text{Standardized Residuals}|}$", fontsize=9)
    ax4.grid(True, linestyle=":", alpha=0.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ chẩn đoán LINE: %s", output_path)


def run_regression_pipeline(
    dataset_path: Path,
    output_fig_path: Path,
    split_timestamp: str = DEFAULT_SPLIT_TIMESTAMP,
) -> RegressionResults:
    """
    Thực thi toàn bộ quy trình mô hình hóa hồi quy OLS và chẩn đoán cho Issue #12.
    """
    df = pd.read_parquet(dataset_path)

    # 1. Chuẩn bị dữ liệu
    X_train, y_train, X_test, y_test = prepare_regression_data(
        df, split_timestamp=split_timestamp, drop_collinear_pm10=True
    )

    # 2. Đa cộng tuyến VIF
    df_vif = compute_vif(X_train)

    # 3. Fit OLS statsmodels
    X_train_const = sm.add_constant(X_train)
    ols_sm = sm.OLS(y_train, X_train_const).fit()

    # 4. Trích xuất bảng hệ số beta
    coef_df = pd.DataFrame({
        "Feature": ols_sm.params.index,
        "Coefficient (Beta)": ols_sm.params.values.round(4),
        "Std. Error": ols_sm.bse.values.round(4),
        "t-Statistic": ols_sm.tvalues.round(2),
        "p-Value": ols_sm.pvalues.apply(lambda p: f"{p:.4e}" if p < 0.0001 else f"{p:.4f}"),
        "95% CI Lower": ols_sm.conf_int()[0].round(4),
        "95% CI Upper": ols_sm.conf_int()[1].round(4),
    })

    # 5. LINE diagnostics
    line_diag = compute_line_diagnostics(ols_sm, X_train, y_train)

    # 6. Cook's Distance
    cooks_d, threshold, n_influential = compute_cooks_distance(ols_sm)

    # 7. Tune Ridge & Lasso
    best_ridge_a, best_lasso_a, ridge_m, lasso_m = tune_regularization(X_train, y_train)

    # 8. Đánh giá Test độc lập
    metrics_df, _ = evaluate_models(X_train, y_train, X_test, y_test, ridge_m, lasso_m)

    # 9. Khảo sát log1p transform Y
    log_y_train = np.log1p(y_train)
    log_ols = sm.OLS(log_y_train, X_train_const).fit()
    log1p_metrics = {
        "original_train_r2": float(ols_sm.rsquared),
        "log1p_train_r2": float(log_ols.rsquared),
        "original_resid_skew": float(line_diag.skewness),
        "log1p_resid_skew": float(stats.skew(log_ols.resid)),
    }

    # 10. Xuất biểu đồ
    render_line_diagnostics_figure(ols_sm, line_diag, output_fig_path)

    return RegressionResults(
        split_timestamp=split_timestamp,
        n_train=len(y_train),
        n_test=len(y_test),
        predictors=list(X_train.columns),
        vif_table=df_vif,
        ols_summary_str=str(ols_sm.summary()),
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
    )
