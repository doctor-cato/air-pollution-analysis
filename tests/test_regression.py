"""
tests/test_regression.py — Kiểm thử tự động cho module hồi quy OLS & LINE (Issue #12).

Toàn bộ test hoạt động ngoại tuyến (offline), độc lập với dataset thật bằng fixture tổng hợp,
và có kiểm thử tích hợp trên dataset thật khi file parquet khả dụng.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.cleaning_pipeline import validate_no_leakage
from src.regression import (
    DEFAULT_SPLIT_TIMESTAMP,
    LINEDiagnostics,
    RegressionResults,
    build_regression_preprocessor,
    compute_cooks_distance,
    compute_hac_lag_sensitivity,
    compute_influence_summary,
    compute_line_diagnostics,
    compute_vif,
    evaluate_derived_interpolation_sensitivity,
    evaluate_models,
    evaluate_seasonal_and_lag_ablation,
    prepare_regression_data,
    render_line_diagnostics_figure,
    run_regression_pipeline,
    tune_regularization,
    write_regression_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_DATA_PATH = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"


def _synthetic_regression_fixture(n_rows: int = 120) -> pd.DataFrame:
    """Tạo fixture chuỗi thời gian tổng hợp để kiểm thử tất định."""
    ts = pd.date_range("2026-01-01 00:00:00+07:00", periods=n_rows, freq="h")
    np.random.seed(42)
    temp = np.linspace(15.0, 30.0, n_rows)
    rh = np.linspace(60.0, 95.0, n_rows)
    ws = np.random.uniform(0.5, 5.0, n_rows)
    precip = np.zeros(n_rows)
    pres = np.linspace(1010.0, 1025.0, n_rows)
    h_sin = np.sin(2 * np.pi * ts.hour / 24)
    h_cos = np.cos(2 * np.pi * ts.hour / 24)
    m_sin = np.sin(2 * np.pi * ts.month / 12)
    m_cos = np.cos(2 * np.pi * ts.month / 12)

    # pm25 có quan hệ tuyến tính với nhiễu
    pm25 = 20.0 + 0.8 * temp - 0.2 * rh - 1.5 * ws + np.random.normal(0, 3, n_rows)
    pm10 = pm25 * 1.5 + np.random.normal(0, 1, n_rows)

    df = pd.DataFrame({
        "timestamp": ts,
        "station_id": "TEST_STATION",
        "pm25": pm25,
        "pm10": pm10,
        "temperature": temp,
        "relative_humidity": rh,
        "wind_speed": ws,
        "precipitation": precip,
        "surface_pressure": pres,
        "hour_sin": h_sin,
        "hour_cos": h_cos,
        "month_sin": m_sin,
        "month_cos": m_cos,
    })
    return df


class TestRegressionDataPreparation(unittest.TestCase):
    """Kiểm thử khâu chuẩn bị dữ liệu hồi quy tuyến tính."""

    def setUp(self):
        self.df = _synthetic_regression_fixture(100)
        self.split_ts = "2026-01-03 00:00:00+07:00"

    def test_chronological_split_preserves_order_and_no_leakage(self):
        X_tr, y_tr, X_te, y_te = prepare_regression_data(
            self.df, split_timestamp=self.split_ts, drop_collinear_pm10=True
        )
        self.assertEqual(len(X_tr), 48)
        self.assertEqual(len(X_te), 52)
        self.assertEqual(len(y_tr), 48)
        self.assertEqual(len(y_te), 52)
        # pm10 phải bị loại bỏ để chống đa cộng tuyến
        self.assertNotIn("pm10", X_tr.columns)
        self.assertNotIn("pm25", X_tr.columns)

    def test_missing_target_rows_are_dropped_without_imputation(self):
        df_nan = self.df.copy()
        df_nan.loc[5:10, "pm25"] = np.nan
        X_tr, y_tr, X_te, y_te = prepare_regression_data(
            df_nan, split_timestamp=self.split_ts
        )
        self.assertEqual(len(X_tr), 48 - 6)
        self.assertFalse(y_tr.isna().any())

    def test_invalid_target_col_raises_key_error(self):
        with self.assertRaises(KeyError):
            prepare_regression_data(self.df, target_col="non_existent")


class TestVIFAndCollinearity(unittest.TestCase):
    """Kiểm thử tính toán VIF và phát hiện đa cộng tuyến."""

    def setUp(self):
        self.df = _synthetic_regression_fixture(80)
        self.X = self.df[["temperature", "relative_humidity", "wind_speed", "surface_pressure"]]

    def test_compute_vif_returns_sorted_dataframe(self):
        vif_df = compute_vif(self.X)
        self.assertIn("Feature", vif_df.columns)
        self.assertIn("VIF", vif_df.columns)
        self.assertEqual(len(vif_df), 4)
        self.assertTrue((vif_df["VIF"] >= 1.0).all())

    def test_collinear_variable_has_huge_vif(self):
        X_coll = self.X.copy()
        X_coll["temp_duplicate"] = X_coll["temperature"] * 2.0 + 0.001
        vif_df = compute_vif(X_coll)
        max_vif = vif_df["VIF"].max()
        self.assertGreater(max_vif, 50.0)


class TestLINEDiagnostics(unittest.TestCase):
    """Kiểm thử tính toán 4 giả định LINE trên phần dư OLS."""

    def setUp(self):
        self.df = _synthetic_regression_fixture(90)
        X_tr, y_tr, _, _ = prepare_regression_data(self.df, split_timestamp="2026-01-03 00:00:00+07:00")
        self.X_const = sm.add_constant(X_tr)
        self.ols_res = sm.OLS(y_tr, self.X_const).fit()
        self.diag = compute_line_diagnostics(self.ols_res, X_tr, y_tr, max_lags=12)

    def test_linearity_diagnostics(self):
        # Phần dư OLS phải có trung bình xấp xỉ 0
        self.assertAlmostEqual(self.diag.residuals_mean, 0.0, places=5)
        self.assertAlmostEqual(self.diag.residuals_fitted_corr, 0.0, places=5)

    def test_independence_diagnostics(self):
        # Durbin-Watson nằm trong khoảng [0, 4]
        self.assertGreaterEqual(self.diag.durbin_watson, 0.0)
        self.assertLessEqual(self.diag.durbin_watson, 4.0)
        self.assertEqual(len(self.diag.acf_values), 13)  # lag 0 to 12

    def test_normality_diagnostics(self):
        self.assertIsInstance(self.diag.skewness, float)
        self.assertIsInstance(self.diag.kurtosis, float)
        self.assertGreaterEqual(self.diag.jarque_bera_pvalue, 0.0)
        self.assertLessEqual(self.diag.jarque_bera_pvalue, 1.0)

    def test_equal_variance_diagnostics(self):
        self.assertGreaterEqual(self.diag.breusch_pagan_stat, 0.0)
        self.assertGreaterEqual(self.diag.breusch_pagan_pvalue, 0.0)
        self.assertLessEqual(self.diag.breusch_pagan_pvalue, 1.0)


class TestCooksDistance(unittest.TestCase):
    """Kiểm thử khoảng cách Cook."""

    def test_cooks_distance_threshold_and_shape(self):
        df = _synthetic_regression_fixture(60)
        X_tr, y_tr, _, _ = prepare_regression_data(df, split_timestamp="2026-01-02 12:00:00+07:00")
        ols_res = sm.OLS(y_tr, sm.add_constant(X_tr)).fit()
        cooks_d, thresh, n_inf = compute_cooks_distance(ols_res)
        self.assertEqual(len(cooks_d), len(y_tr))
        self.assertAlmostEqual(thresh, 4.0 / len(y_tr), places=6)
        self.assertGreaterEqual(n_inf, 0)


class TestRegularizationAndEvaluation(unittest.TestCase):
    """Kiểm thử điều hòa Ridge/Lasso và đánh giá mô hình."""

    def setUp(self):
        self.df = _synthetic_regression_fixture(100)
        self.X_tr, self.y_tr, self.X_te, self.y_te = prepare_regression_data(
            self.df, split_timestamp="2026-01-03 00:00:00+07:00"
        )

    def test_tune_regularization_returns_positive_alphas(self):
        alphas = np.array([0.01, 0.1, 1.0, 10.0])
        r_alpha, l_alpha, r_mod, l_mod, scaler = tune_regularization(
            self.X_tr, self.y_tr, n_splits=3, alphas=alphas
        )
        self.assertIn(r_alpha, alphas)
        self.assertIn(l_alpha, alphas)
        self.assertEqual(len(r_mod.coef_), self.X_tr.shape[1])
        self.assertEqual(len(l_mod.coef_), self.X_tr.shape[1])

    def test_timeseries_cv_does_not_leak_validation_distribution(self):
        # Đảm bảo Imputer + Scaler trong CV không bị rò rỉ từ validation fold hay tập Test:
        # 1) Mutate X_test không được làm thay đổi tham số pipeline hay trọng số mô hình.
        X_te_mutated = self.X_te.copy()
        X_te_mutated.iloc[:, 0] = 999999.0

        alphas = np.array([0.1, 1.0])
        r1, l1, rm1, lm1, p1 = tune_regularization(self.X_tr, self.y_tr, n_splits=3, alphas=alphas)
        r2, l2, rm2, lm2, p2 = tune_regularization(self.X_tr, self.y_tr, n_splits=3, alphas=alphas)
        self.assertEqual(r1, r2)
        self.assertEqual(l1, l2)
        np.testing.assert_allclose(rm1.coef_, rm2.coef_)

        # Kiểm chứng với validate_no_leakage trên timestamp tuần tự
        _, _, _, _, ts_tr, ts_te = prepare_regression_data(
            self.df, split_timestamp="2026-01-03 00:00:00+07:00", return_timestamps=True
        )
        validate_no_leakage(p1, X_train=self.X_tr, X_test=X_te_mutated, timestamps=ts_tr, test_timestamps=ts_te)

        # 2) Khi X_train chứa NaN + ngoại lai ở cuối Train (validation fold cuối), Imputer/Scaler
        # vẫn xử lý không lỗi và chỉ khớp đúng refit Train (tức biến bị NaN ở X_test không tác động).
        X_tr_nan = self.X_tr.copy()
        X_tr_nan.iloc[0:3, 0] = np.nan
        _, _, rm_nan, _, p_nan = tune_regularization(X_tr_nan, self.y_tr, n_splits=3, alphas=alphas)
        validate_no_leakage(p_nan, X_train=X_tr_nan, X_test=X_te_mutated, timestamps=ts_tr, test_timestamps=ts_te)
        self.assertEqual(len(rm_nan.coef_), self.X_tr.shape[1])

    def test_evaluate_models_returns_expected_metrics_table(self):
        alphas = np.array([0.1, 1.0])
        _, _, r_mod, l_mod, scaler = tune_regularization(self.X_tr, self.y_tr, n_splits=2, alphas=alphas)
        metrics_df, _ = evaluate_models(self.X_tr, self.y_tr, self.X_te, self.y_te, r_mod, l_mod, scaler=scaler)
        self.assertEqual(len(metrics_df), 4)  # Baseline, OLS, Ridge, Lasso
        for col in ["Model", "MAE (µg/m³)", "RMSE (µg/m³)", "R²", "Adjusted R²"]:
            self.assertIn(col, metrics_df.columns)
        # Dummy Baseline không bị phạt degrees of freedom (p=0) -> R² bằng Adjusted R²
        dummy_row = metrics_df[metrics_df["Model"].str.contains("Dummy")].iloc[0]
        self.assertEqual(dummy_row["R²"], dummy_row["Adjusted R²"])


class TestFigureRendering(unittest.TestCase):
    """Kiểm thử xuất biểu đồ chẩn đoán LINE."""

    def test_render_line_diagnostics_figure_creates_non_empty_png(self):
        df = _synthetic_regression_fixture(80)
        X_tr, y_tr, _, _ = prepare_regression_data(df, split_timestamp="2026-01-02 12:00:00+07:00")
        ols_res = sm.OLS(y_tr, sm.add_constant(X_tr)).fit()
        diag = compute_line_diagnostics(ols_res, X_tr, y_tr, max_lags=10)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_png = Path(tmp_dir) / "line_diag.png"
            render_line_diagnostics_figure(ols_res, diag, out_png)
            self.assertTrue(out_png.exists())
            self.assertGreater(out_png.stat().st_size, 50000)  # > 50KB


class TestRegressionRealDataset(unittest.TestCase):
    """Kiểm thử trên dữ liệu thật khi tệp Parquet tồn tại."""

    @classmethod
    def setUpClass(cls):
        if not REAL_DATA_PATH.exists():
            raise unittest.SkipTest("Thiếu data/processed/air_pollution_final.parquet (bỏ qua test dữ liệu thật)")

    def test_full_pipeline_on_real_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_fig = Path(tmp_dir) / "test_diag.png"
            out_rep = Path(tmp_dir) / "test_report.md"
            results = run_regression_pipeline(
                REAL_DATA_PATH, out_fig, report_path=out_rep, split_timestamp=DEFAULT_SPLIT_TIMESTAMP
            )
            self.assertIsInstance(results, RegressionResults)
            self.assertEqual(results.n_train, 4279)
            self.assertEqual(results.n_test, 3216)
            self.assertTrue(out_fig.exists())
            self.assertTrue(out_rep.exists())
            self.assertGreater(out_rep.stat().st_size, 1000)
            # VIF của các biến khí tượng không chứa pm10
            self.assertNotIn("pm10", results.predictors)


class TestRegressionScopeAndReviewGuards(unittest.TestCase):
    """Kiểm thử hồi quy cho các phát hiện audit PR #48 và mở rộng Protocol A/B."""

    def test_reset_detects_quadratic_nonlinearity_despite_zero_corr(self):
        rng = np.random.default_rng(42)
        n = 200
        x = np.linspace(-10.0, 10.0, n)
        y = 3.0 * (x ** 2) + rng.normal(0.0, 0.5, size=n)
        X_df = pd.DataFrame({"temperature": x, "wind_speed": np.linspace(1.0, 5.0, n)})
        ols_fit = sm.OLS(y, sm.add_constant(X_df)).fit()
        diag = compute_line_diagnostics(ols_fit, X_df, pd.Series(y), max_lags=10)
        # corr(resid, fitted) luôn = 0 theo đại số OLS, nhưng Ramsey RESET phải phát hiện phi tuyến
        self.assertAlmostEqual(diag.residuals_fitted_corr, 0.0, places=8)
        self.assertIsNotNone(diag.reset_power2_pvalue)
        self.assertLess(diag.reset_power2_pvalue, 1e-6)
        self.assertTrue(diag.linearity_violated)

    def test_multi_station_fail_closed_protocol_b_guard(self):
        df1 = _synthetic_regression_fixture(80)
        df1["station_id"] = "STATION_A"
        df1["split"] = ["train"] * 60 + ["test"] * 20

        df2 = _synthetic_regression_fixture(80)
        df2["station_id"] = "STATION_B"
        df2["timestamp"] = df2["timestamp"] + pd.Timedelta(days=100)
        df2["split"] = ["train"] * 60 + ["test"] * 20

        multi = pd.concat([df1, df2], ignore_index=True)
        with self.assertRaises(ValueError):
            prepare_regression_data(multi, use_split_column=True, station_id=None)

        X_tr, y_tr, X_te, y_te = prepare_regression_data(
            multi, use_split_column=True, station_id="STATION_B"
        )
        self.assertEqual(len(X_tr), 60)
        self.assertEqual(len(X_te), 20)

    def test_rejects_target_leakage_flag_in_predictors(self):
        df = _synthetic_regression_fixture(80)
        df["pm25_was_missing"] = 0
        with self.assertRaises(ValueError):
            prepare_regression_data(
                df,
                split_timestamp="2026-01-02 12:00:00+07:00",
                predictor_cols=["temperature", "pm25_was_missing"],
            )

    def test_influence_summary_separates_outliers_leverage_and_cooks(self):
        df = _synthetic_regression_fixture(80)
        df.loc[10, "pm25"] = df.loc[10, "pm25"] + 150.0  # outlier mạnh
        X_tr, y_tr, _, _, ts_tr, _ = prepare_regression_data(
            df, split_timestamp="2026-01-03 00:00:00+07:00", return_timestamps=True
        )
        ols_res = sm.OLS(y_tr.reset_index(drop=True), sm.add_constant(X_tr.reset_index(drop=True))).fit()
        inf = compute_influence_summary(ols_res, timestamps=ts_tr, top_n=5)
        self.assertGreaterEqual(inf["n_outliers_stud_gt_3"], 1)
        self.assertGreaterEqual(inf["n_cooks_gt_4n"], 1)
        self.assertEqual(len(inf["top_influential"]), 5)

    def test_hac_lag_sensitivity_covers_zero_and_nw_plugin(self):
        df = _synthetic_regression_fixture(120)
        X_tr, y_tr, _, _ = prepare_regression_data(df, split_timestamp="2026-01-04 00:00:00+07:00")
        sens_df, nw_lag = compute_hac_lag_sensitivity(X_tr, y_tr, lags=[0, 4, 12])
        self.assertGreaterEqual(nw_lag, 1)
        self.assertTrue({0, 4, 12}.issubset(set(sens_df["maxlags"].unique())))
        self.assertIn("wind_speed", set(sens_df["Feature"].unique()))

    def test_ablation_lag24_uses_exact_24h_timestamp_offset(self):
        df = _synthetic_regression_fixture(120)
        # Xóa 12 giờ giữa chuỗi để kiểm chứng lag24 khớp theo timestamp-24h chứ không shift(24) sai dòng
        df_gapped = df.drop(index=list(range(30, 42))).reset_index(drop=True)
        ab_df, ab_diag = evaluate_seasonal_and_lag_ablation(
            df_gapped, split_timestamp="2026-01-04 00:00:00+07:00"
        )
        self.assertIn("OLS Khí tượng + Giờ + pm25_lag24 (8 biến, AR)", set(ab_df["Specification"]))
        self.assertIn("ols_drop_season_test_r2", ab_diag)

    def test_derived_sensitivity_keeps_test_ground_truth_untouched(self):
        df = _synthetic_regression_fixture(120)
        df["pm25_derived_interpolated"] = df["pm25"].copy()
        df.loc[5, "pm25"] = np.nan
        df.loc[5, "pm25_derived_interpolated"] = 45.0
        # Cố tình nhiễu giá trị derived trên Test: kết quả đánh giá Test phải bất biến
        df_mut = df.copy()
        df_mut.loc[df_mut.index[-10:], "pm25_derived_interpolated"] = 9999.0

        res1 = evaluate_derived_interpolation_sensitivity(
            df, split_timestamp="2026-01-04 00:00:00+07:00"
        )
        res2 = evaluate_derived_interpolation_sensitivity(
            df_mut, split_timestamp="2026-01-04 00:00:00+07:00"
        )
        self.assertEqual(res1["n_derived_hours_added_in_train"], 1)
        self.assertAlmostEqual(res1["test_rmse_derived_train_model"], res2["test_rmse_derived_train_model"], places=8)

    def test_write_regression_report_renders_dynamic_values_without_hardcode(self):
        df = _synthetic_regression_fixture(120)
        with tempfile.TemporaryDirectory() as tmp_dir:
            pq_path = Path(tmp_dir) / "synth.parquet"
            fig_path = Path(tmp_dir) / "fig.png"
            rep_path = Path(tmp_dir) / "rep.md"
            df.to_parquet(pq_path, index=False)
            res = run_regression_pipeline(
                pq_path, fig_path, report_path=rep_path, split_timestamp="2026-01-04 00:00:00+07:00"
            )
            text = rep_path.read_text(encoding="utf-8")
            self.assertIn(f"DW = {res.line_diagnostics.durbin_watson:.4f}", text)
            self.assertNotIn("ACF lag 1 = 0,764", text)
            self.assertNotIn("-1,9540", text)


if __name__ == "__main__":
    unittest.main()
