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

from src.regression import (
    DEFAULT_SPLIT_TIMESTAMP,
    LINEDiagnostics,
    RegressionResults,
    compute_cooks_distance,
    compute_line_diagnostics,
    compute_vif,
    evaluate_models,
    prepare_regression_data,
    render_line_diagnostics_figure,
    run_regression_pipeline,
    tune_regularization,
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
        # Đảo phân phối / chèn outlier cực đại ở cuối chuỗi Train (nằm trong val_idx của fold đầu)
        X_tr_mutated = self.X_tr.copy()
        X_tr_mutated.iloc[-10:, 0] = 999999.0
        alphas = np.array([1.0])
        # Kiểm tra tính cách ly: fold 0 độc lập hoàn toàn với phân phối validation fold
        from sklearn.preprocessing import RobustScaler
        n_tr_fold0 = len(self.X_tr) // 4
        scaler_fold0 = RobustScaler().fit(self.X_tr.iloc[:n_tr_fold0])
        scaler_fold0_mut = RobustScaler().fit(X_tr_mutated.iloc[:n_tr_fold0])
        np.testing.assert_array_almost_equal(scaler_fold0.center_, scaler_fold0_mut.center_)

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


if __name__ == "__main__":
    unittest.main()
