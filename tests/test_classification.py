"""
tests/test_classification.py — Kiểm thử tự động cho module phân loại cảnh báo ô nhiễm (Issue #13).

Toàn bộ test hoạt động ngoại tuyến (offline), độc lập với dataset thật bằng fixture tổng hợp,
và có kiểm thử tích hợp trên dataset thật khi file parquet khả dụng.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier

from src.classification import (
    DEFAULT_SPLIT_TIMESTAMP,
    ClassificationModelMetrics,
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
)
from src.cleaning_pipeline import (
    DEFAULT_ALERT_MIN_PERIODS,
    DEFAULT_ALERT_THRESHOLD_UG_M3,
    DEFAULT_ALERT_WINDOW_HOURS,
    build_alert_label,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_DATA_PATH = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"


def _synthetic_classification_fixture(n_rows: int = 120) -> pd.DataFrame:
    """Tạo fixture chuỗi thời gian tổng hợp để kiểm thử tất định."""
    ts = pd.date_range("2026-01-01 00:00:00+07:00", periods=n_rows, freq="h")
    np.random.seed(42)
    # Tạo chuỗi pm25 có trung bình trượt 24h lúc vượt 50, lúc dưới 50 ở cả 2 nửa chuỗi
    pm25 = np.full(n_rows, 30.0)
    # Đợt ô nhiễm cao kéo dài > 24h để rolling mean >= 50 ở cả Train và Test
    pm25[25:55] = 75.0
    if n_rows > 80:
        pm25[80:min(110, n_rows)] = 80.0
    ws = np.random.uniform(0.1, 4.0, n_rows)

    df = pd.DataFrame({
        "timestamp": ts,
        "station_id": "TEST_STATION",
        "pm25": pm25,
        "pm10": pm25 * 1.4,
        "temperature": np.linspace(16.0, 28.0, n_rows),
        "relative_humidity": np.linspace(65.0, 92.0, n_rows),
        "wind_speed": ws,
        "precipitation": np.zeros(n_rows),
        "surface_pressure": np.linspace(1012.0, 1020.0, n_rows),
        "hour_sin": np.sin(2 * np.pi * ts.hour / 24),
        "hour_cos": np.cos(2 * np.pi * ts.hour / 24),
        "month_sin": np.sin(2 * np.pi * ts.month / 12),
        "month_cos": np.cos(2 * np.pi * ts.month / 12),
    })
    return df


class TestAlertLabelConstruction(unittest.TestCase):
    """Kiểm thử khóa tham số và logic sinh nhãn cảnh báo (Task 0.7b)."""

    def setUp(self):
        self.df = _synthetic_classification_fixture(60)

    def test_alert_label_locks_default_parameters(self):
        self.assertEqual(DEFAULT_ALERT_WINDOW_HOURS, 24)
        self.assertEqual(DEFAULT_ALERT_MIN_PERIODS, 24)
        self.assertEqual(DEFAULT_ALERT_THRESHOLD_UG_M3, 50.0)

    def test_alert_label_returns_expected_series(self):
        label = build_alert_label(self.df)
        self.assertIsInstance(label, pd.Series)
        self.assertEqual(label.name, "pm25_alert_24h")
        self.assertEqual(len(label), len(self.df))
        # 23 giờ đầu tiên không đủ 24 giờ lịch sử -> phải là NaN
        self.assertTrue(label.iloc[:23].isna().all())
        # Giờ thứ 24 (index 23) có đủ 24 giá trị -> phải là 0.0 hoặc 1.0
        self.assertIn(label.iloc[23], [0.0, 1.0])

    def test_alert_label_requires_monotonic_timestamps(self):
        df_unsor = self.df.sort_values("timestamp", ascending=False)
        with self.assertRaises(ValueError):
            build_alert_label(df_unsor)

    def test_alert_label_requires_existing_target(self):
        with self.assertRaises(KeyError):
            build_alert_label(self.df, target_col="non_existent")

    def test_nan_window_propagates_nan_label(self):
        df_gap = self.df.copy()
        # Chèn 1 NaN vào giữa cửa sổ -> min_periods=24 sẽ không thỏa mãn
        df_gap.loc[30, "pm25"] = np.nan
        label = build_alert_label(df_gap)
        # Các cửa sổ bao trùm index 30 phải bị NaN
        self.assertTrue(label.iloc[30:54].isna().all())


class TestFeatureEngineering(unittest.TestCase):
    """Kiểm thử kỹ nghệ đặc trưng quá khứ chống rò rỉ dữ liệu."""

    def setUp(self):
        self.df = _synthetic_classification_fixture(70)
        self.feats = engineer_classification_features(self.df)

    def test_no_lookahead_leakage_via_shift_1(self):
        # pm25_rolling_mean_24h tại index t không được phụ thuộc vào pm25[t]
        orig_mean_30 = self.feats.loc[30, "pm25_rolling_mean_24h"]
        df_mod = self.df.copy()
        df_mod.loc[30, "pm25"] = 999.0  # Đổi giá trị tại t
        feats_mod = engineer_classification_features(df_mod)
        # Giá trị đặc trưng tại t phải giữ nguyên (do shift(1))
        self.assertEqual(orig_mean_30, feats_mod.loc[30, "pm25_rolling_mean_24h"])

    def test_calm_wind_flag_threshold(self):
        self.assertIn("is_calm_wind", self.feats.columns)
        for i in range(len(self.df)):
            ws = self.df.loc[i, "wind_speed"]
            expected = 1.0 if ws < 0.5 else 0.0
            self.assertEqual(self.feats.loc[i, "is_calm_wind"], expected)


class TestClassificationDataPreparation(unittest.TestCase):
    """Kiểm thử chuẩn bị dữ liệu phân loại và tỷ lệ mất cân bằng lớp."""

    def test_prepare_data_splits_and_prevalence_metadata(self):
        df = _synthetic_classification_fixture(100)
        split_ts = "2026-01-03 00:00:00+07:00"
        X_tr, y_tr, X_te, y_te, meta = prepare_classification_data(df, split_timestamp=split_ts)

        self.assertGreater(len(X_tr), 0)
        self.assertGreater(len(X_te), 0)
        self.assertIn("train_prevalence_valid", meta)
        self.assertIn("test_prevalence_valid", meta)
        self.assertIn("train_prevalence_all", meta)
        self.assertIn("test_prevalence_all", meta)
        self.assertNotIn("pm10", X_tr.columns)


class TestThresholdTuningAndEvaluation(unittest.TestCase):
    """Kiểm thử tối ưu ngưỡng quyết định và đo lường hiệu năng."""

    def setUp(self):
        df = _synthetic_classification_fixture(120)
        split_ts = "2026-01-03 12:00:00+07:00"
        self.X_tr, self.y_tr, self.X_te, self.y_te, _ = prepare_classification_data(df, split_timestamp=split_ts)
        self.dummy = DummyClassifier(strategy="prior")
        self.dummy.fit(self.X_tr, self.y_tr)
        self.rf = RandomForestClassifier(n_estimators=30, max_depth=5, random_state=42)
        self.rf.fit(self.X_tr, self.y_tr)

    def test_threshold_tuning_returns_valid_tau(self):
        tau = tune_classification_threshold(self.rf, self.X_tr, self.y_tr, metric="f2", n_splits=2)
        self.assertGreaterEqual(tau, 0.10)
        self.assertLessEqual(tau, 0.90)

    def test_evaluate_classifier_metrics_structure(self):
        m = evaluate_classifier("Random Forest", self.rf, self.X_te, self.y_te, threshold=0.50)
        self.assertIsInstance(m, ClassificationModelMetrics)
        self.assertEqual(len(m.confusion_matrix), 2)
        self.assertGreaterEqual(m.accuracy, 0.0)
        self.assertGreaterEqual(m.recall, 0.0)
        self.assertGreaterEqual(m.precision, 0.0)
        self.assertGreaterEqual(m.pr_auc, 0.0)

    def test_accuracy_trap_on_dummy(self):
        m = evaluate_classifier("Dummy", self.dummy, self.X_te, self.y_te, threshold=0.50)
        # Dummy phân loại theo tần suất lớp đa số: không học bất kỳ tương quan thực tế nào
        self.assertIn(m.recall, [0.0, 1.0])
        self.assertLess(m.pr_auc, 1.0)

    def test_threshold_tuning_does_not_mutate_model(self):
        # Kiểm tra mô hình truyền vào tune_classification_threshold không bị đột biến (mutate)
        probs_before = self.rf.predict_proba(self.X_te)
        tau = tune_classification_threshold(self.rf, self.X_tr, self.y_tr, metric="f2", n_splits=2)
        probs_after = self.rf.predict_proba(self.X_te)
        np.testing.assert_array_almost_equal(probs_before, probs_after)


class TestFeatureImportanceAndAudit(unittest.TestCase):
    """Kiểm thử đo lường tầm quan trọng biến và lập biên bản kiểm toán rò rỉ."""

    def test_compute_feature_importances(self):
        df = _synthetic_classification_fixture(100)
        X_tr, y_tr, X_te, y_te, _ = prepare_classification_data(df, split_timestamp="2026-01-03 00:00:00+07:00")
        rf = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=42).fit(X_tr, y_tr)
        imp_df = compute_feature_importances(rf, X_te, y_te)
        self.assertEqual(len(imp_df), X_te.shape[1])
        self.assertIn("Feature", imp_df.columns)
        self.assertIn("Permutation Mean", imp_df.columns)

    def test_leakage_audit_markdown_covers_all_4_forms(self):
        meta = {
            "n_train_total": 4682, "n_train_valid": 2994,
            "n_test_total": 4362, "n_test_valid": 2323,
            "train_prevalence_valid": 0.3293, "test_prevalence_valid": 0.2880,
            "train_prevalence_all": 0.2106, "test_prevalence_all": 0.1534,
        }
        metrics_table = pd.DataFrame([
            {"Model": "Logistic Regression", "Recall": 0.85, "PR-AUC": 0.72},
            {"Model": "Random Forest", "Recall": 0.90, "PR-AUC": 0.80},
        ])
        audit_md = generate_leakage_audit_markdown(meta, metrics_table)
        self.assertIn("Target Leakage", audit_md)
        self.assertIn("Train-Test Contamination", audit_md)
        self.assertIn("Temporal Leakage", audit_md)
        self.assertIn("Group / Station Leakage", audit_md)
        self.assertIn("SMOTE", audit_md)
        self.assertIn("PASS", audit_md)


class TestClassificationFigures(unittest.TestCase):
    """Kiểm thử xuất biểu đồ PR Curve và Feature Importance."""

    def test_render_classification_figures(self):
        df = _synthetic_classification_fixture(90)
        X_tr, y_tr, X_te, y_te, _ = prepare_classification_data(df, split_timestamp="2026-01-03 00:00:00+07:00")
        rf = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=42).fit(X_tr, y_tr)
        imp_df = compute_feature_importances(rf, X_te, y_te)

        with tempfile.TemporaryDirectory() as tmp_dir:
            pr_path = Path(tmp_dir) / "pr_curve.png"
            feat_path = Path(tmp_dir) / "feat_imp.png"
            render_pr_curve_figure({"Random Forest": rf}, X_te, y_te, 0.30, pr_path)
            render_feature_importance_figure(imp_df, feat_path)
            self.assertTrue(pr_path.exists())
            self.assertTrue(feat_path.exists())
            self.assertGreater(pr_path.stat().st_size, 30000)
            self.assertGreater(feat_path.stat().st_size, 30000)


class TestClassificationRealDataset(unittest.TestCase):
    """Kiểm thử tích hợp trên dữ liệu thật khi Parquet tồn tại."""

    @classmethod
    def setUpClass(cls):
        if not REAL_DATA_PATH.exists():
            raise unittest.SkipTest("Thiếu data/processed/air_pollution_final.parquet (bỏ qua test dữ liệu thật)")

    def test_full_classification_pipeline_on_real_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pr_fig = Path(tmp_dir) / "pr.png"
            feat_fig = Path(tmp_dir) / "feat.png"
            audit_rep = Path(tmp_dir) / "audit.md"
            res_rep = Path(tmp_dir) / "results.md"
            find_rep = Path(tmp_dir) / "findings.md"
            results = run_classification_pipeline(
                REAL_DATA_PATH, pr_fig, feat_fig, audit_rep,
                report_results_path=res_rep, findings_path=find_rep,
                split_timestamp=DEFAULT_SPLIT_TIMESTAMP
            )
            self.assertIsInstance(results, ClassificationResults)
            self.assertEqual(results.n_train_total, 4682)
            self.assertEqual(results.n_test_total, 4362)
            self.assertTrue(pr_fig.exists())
            self.assertTrue(feat_fig.exists())
            self.assertTrue(audit_rep.exists())
            self.assertTrue(res_rep.exists())
            self.assertTrue(find_rep.exists())


if __name__ == "__main__":
    unittest.main()
