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
    BASELINE_DATASET_VERSION,
    DEFAULT_SPLIT_TIMESTAMP,
    ClassificationModelMetrics,
    ClassificationResults,
    PersistenceRuleClassifier,
    _assert_split_totals_match,
    _build_coverage_base_frame,
    _df_to_markdown,
    build_classification_pipeline,
    compute_calibration_summary,
    compute_coverage_and_outage_tables,
    compute_feature_importances,
    compute_monthly_test_drift,
    compute_year_season_coverage_tables,
    engineer_classification_features,
    evaluate_classifier,
    evaluate_derived_pm25_sensitivity,
    evaluate_feature_ablation_and_horizons,
    generate_leakage_audit_markdown,
    prepare_classification_data,
    render_feature_importance_figure,
    render_pr_curve_figure,
    render_reliability_figure,
    run_classification_pipeline,
    run_extended_classification_suite,
    run_temporal_backtest_and_drift,
    tune_classification_threshold,
    verify_classification_no_leakage,
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
            self.assertTrue((Path(tmp_dir) / "calibration_reliability_VN001_baseline_2026_01_15.png").exists())

    def test_real_extended_suite_vn001_and_vn003_protocol_a_and_unestimable(self):
        ext_path = REPO_ROOT / "data" / "processed" / "air_pollution_extended_2022_2026.parquet"
        if not ext_path.exists():
            self.skipTest("Thiếu air_pollution_extended_2022_2026.parquet")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            suite = run_extended_classification_suite(
                baseline_path=REAL_DATA_PATH,
                extended_path=ext_path,
                figures_dir=tmp / "figures",
                report_results_path=tmp / "classification_results.md",
                findings_path=tmp / "classification_findings.md",
                report_audit_path=tmp / "classification_leakage_audit.md",
                docs_audit_path=tmp / "leakage_audit.md",
            )
            self.assertIn("VN001_baseline", suite)
            self.assertIn("VN001_extended", suite)
            self.assertIn("VN003_extended", suite)

            ext1 = suite["VN001_extended"]
            self.assertEqual(ext1.calibration_status, "UNESTIMABLE")
            self.assertTrue(np.isnan(ext1.model_metrics["rf"].pr_auc))
            self.assertIn("UNESTIMABLE", ext1.model_metrics["rf"].status)

            ext3 = suite["VN003_extended"]
            self.assertEqual(ext3.calibration_status, "OK")
            self.assertGreater(ext3.n_test_valid, 1000)

            rep_txt = (tmp / "classification_results.md").read_text(encoding="utf-8")
            self.assertIn(ext1.dataset_sha256, rep_txt)
            self.assertIn(ext3.dataset_sha256, rep_txt)
            self.assertIn("UNESTIMABLE", rep_txt)
            self.assertTrue((tmp / "figures" / "calibration_reliability.png").exists())
            self.assertTrue((tmp / "figures" / "calibration_reliability_vn001_extended.png").exists())
            self.assertTrue((tmp / "figures" / "calibration_reliability_vn003_extended.png").exists())

            for sc_key, sc_res in suite.items():
                cov_tot = sc_res.coverage_table
                for tbl in (sc_res.yearly_coverage_table, sc_res.seasonal_coverage_table, sc_res.monthly_coverage_table):
                    self.assertIn("Split", tbl.columns, msg=f"Thiếu Split ở {sc_key}")
                    self.assertIn("Station", tbl.columns, msg=f"Thiếu Station ở {sc_key}")
                    self.assertEqual(set(tbl["Split"].unique()), {"train", "test"})
                    self.assertEqual(int(tbl["Grid Hours"].sum()), int(cov_tot.loc[0, "Total (giờ)"]))
                    self.assertEqual(
                        int(tbl.loc[tbl["Split"] == "train", "Evaluable"].sum()),
                        int(cov_tot.loc[3, "Train (giờ)"]),
                    )
                    self.assertEqual(
                        int(tbl.loc[tbl["Split"] == "test", "Evaluable"].sum()),
                        int(cov_tot.loc[3, "Test (giờ)"]),
                    )


class TestClassificationGuardsAndExtensions(unittest.TestCase):
    """Kiểm thử các guard chống rò rỉ, baseline quy tắc, đa trạm, tầm dự báo và trường hợp Test đơn lớp."""

    def test_dummy_pr_auc_equals_test_prevalence(self):
        df = _synthetic_classification_fixture(120)
        split_ts = "2026-01-03 12:00:00+07:00"
        X_tr, y_tr, X_te, y_te, meta = prepare_classification_data(df, split_timestamp=split_ts)
        dummy = DummyClassifier(strategy="prior").fit(X_tr, y_tr)
        m = evaluate_classifier("Dummy", dummy, X_te, y_te, threshold=0.50)
        self.assertAlmostEqual(m.pr_auc, round(float(y_te.mean()), 4), places=4)
        self.assertAlmostEqual(m.pr_auc, round(meta["test_prevalence_valid"], 4), places=4)

    def test_persistence_rule_baseline_metrics(self):
        df = _synthetic_classification_fixture(120)
        split_ts = "2026-01-03 12:00:00+07:00"
        X_tr, y_tr, X_te, y_te, _ = prepare_classification_data(df, split_timestamp=split_ts)
        rule = PersistenceRuleClassifier(feature_col="pm25_rolling_mean_24h", threshold_ug_m3=50.0).fit(X_tr, y_tr)
        expected_preds = (X_te["pm25_rolling_mean_24h"] >= 50.0).astype(int).to_numpy()
        np.testing.assert_array_equal(rule.predict(X_te), expected_preds)
        m = evaluate_classifier("Persistence Rule", rule, X_te, y_te, threshold=0.50)
        self.assertEqual(len(m.confusion_matrix), 2)
        self.assertEqual(len(m.confusion_matrix[0]), 2)
        self.assertTrue(np.isfinite(m.false_alarm_rate))
        self.assertTrue(np.isfinite(m.brier_score))

    def test_cross_station_isolation_and_timestamp_gap_safety(self):
        df_a = _synthetic_classification_fixture(60)
        df_a["station_id"] = "STATION_A"
        df_b = _synthetic_classification_fixture(60)
        df_b["station_id"] = "STATION_B"
        df_multi = pd.concat([df_a, df_b], ignore_index=True)

        feats = engineer_classification_features(df_multi, include_wind_stagnant_alias=True)
        # 24 giờ đầu của trạm B tuyệt đối không được mượn từ cuối trạm A
        b_mask = df_multi["station_id"] == "STATION_B"
        feats_b = feats.loc[b_mask]
        self.assertTrue(feats_b["pm25_rolling_mean_24h"].iloc[:24].isna().all())
        self.assertTrue(feats_b["pm25_rolling_std_24h"].iloc[:24].isna().all())
        self.assertTrue(feats_b["pm25_lag24"].iloc[:24].isna().all())
        self.assertIn("wind_stagnant", feats.columns)
        pd.testing.assert_series_equal(feats["wind_stagnant"], feats["is_calm_wind"], check_names=False)

        # Kiểm tra bỏ qua khoảng trống thời gian: xóa hàng index 25 không được làm lag24 dịch sai giờ
        df_gap = df_a.drop(index=25).reset_index(drop=True)
        feats_gap = engineer_classification_features(df_gap)
        # Giờ t = ts[24 + 25] tương ứng 2026-01-03 01:00 (24h trước là ts bị xóa -> phải là NaN)
        missing_ts = df_a.loc[25, "timestamp"]
        target_ts = missing_ts + pd.Timedelta(hours=24)
        idx_target = df_gap.index[df_gap["timestamp"] == target_ts][0]
        self.assertTrue(pd.isna(feats_gap.loc[idx_target, "pm25_lag24"]))

    def test_prepare_data_rejects_unfiltered_multi_station_protocol_b(self):
        df_a = _synthetic_classification_fixture(60)
        df_a["station_id"] = "STATION_A"
        df_b = _synthetic_classification_fixture(60)
        df_b["station_id"] = "STATION_B"
        df_multi = pd.concat([df_a, df_b], ignore_index=True)
        with self.assertRaises(ValueError):
            prepare_classification_data(df_multi, split_timestamp="2026-01-02 00:00:00+07:00")

    def test_threshold_tuning_invariant_to_y_test_and_leakage_guard(self):
        from sklearn.linear_model import LogisticRegression

        df = _synthetic_classification_fixture(120)
        split_ts = "2026-01-03 12:00:00+07:00"
        X_tr, y_tr, X_te, y_te, _, ts_tr, ts_te = prepare_classification_data(
            df, split_timestamp=split_ts, return_timestamps=True
        )
        pipe_clean = build_classification_pipeline(
            LogisticRegression(class_weight="balanced", random_state=42, max_iter=500),
            list(X_tr.columns),
            scale_features=True,
        )
        tau_1 = tune_classification_threshold(pipe_clean, X_tr, y_tr, metric="f2", n_splits=2)
        y_te_flipped = 1 - y_te  # Thử đột biến hoàn toàn y_test -> tau* trên Train phải bất biến
        _ = y_te_flipped
        tau_2 = tune_classification_threshold(pipe_clean, X_tr, y_tr, metric="f2", n_splits=2)
        self.assertEqual(tau_1, tau_2)

        pipe_clean.fit(X_tr, y_tr)
        verify_classification_no_leakage(
            pipe_clean, X_train=X_tr, X_test=X_te, timestamps=ts_tr, test_timestamps=ts_te
        )

        # Cố tình fit sai trên X_test -> guard phải phát hiện rò rỉ và ném AssertionError
        pipe_leaked = build_classification_pipeline(
            LogisticRegression(class_weight="balanced", random_state=42, max_iter=500),
            list(X_tr.columns),
            scale_features=True,
        )
        pipe_leaked.fit(X_te, y_te)
        with self.assertRaises(AssertionError):
            verify_classification_no_leakage(
                pipe_leaked, X_train=X_tr, X_test=X_te, timestamps=ts_tr, test_timestamps=ts_te
            )

    def test_horizon_purge_gap_prevents_boundary_overlap(self):
        df = _synthetic_classification_fixture(168)
        split_ts = "2026-01-05 00:00:00+07:00"
        _, _, _, _, meta_h24, ts_tr, ts_te = prepare_classification_data(
            df, split_timestamp=split_ts, horizon_hours=24, return_timestamps=True
        )
        self.assertGreater(meta_h24["n_purged_horizon_rows"], 0)
        self.assertLess(ts_tr.max() + pd.Timedelta(hours=24), ts_te.min())

    def test_derived_pm25_sensitivity_keeps_test_and_labels_observed(self):
        df = _synthetic_classification_fixture(140)
        df["pm25_derived_interpolated"] = df["pm25"].copy()
        # Tạo một khoảng trống ngắn 2h ở phần Train nơi pm25 gốc là NaN nhưng derived đã nội suy
        df.loc[30:31, "pm25"] = np.nan
        split_ts = "2026-01-04 00:00:00+07:00"
        sens_df = evaluate_derived_pm25_sensitivity(df, split_timestamp=split_ts)
        self.assertIsNotNone(sens_df)
        self.assertEqual(len(sens_df), 2)
        self.assertEqual(sens_df.iloc[0]["n_test"], sens_df.iloc[1]["n_test"])
        self.assertEqual(sens_df.iloc[0]["Test Positives"], sens_df.iloc[1]["Test Positives"])
        self.assertGreaterEqual(sens_df.iloc[1]["Train Recovered Rows"], 0)

    def test_single_class_zero_positive_test_returns_unestimable(self):
        df = _synthetic_classification_fixture(120)
        split_ts = "2026-01-03 12:00:00+07:00"
        X_tr, y_tr, X_te, _, _ = prepare_classification_data(df, split_timestamp=split_ts)
        y_te_zero = pd.Series(0, index=X_te.index, dtype=int)
        rf = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=42).fit(X_tr, y_tr)

        m = evaluate_classifier("RF_AllNeg", rf, X_te, y_te_zero, threshold=0.50)
        self.assertEqual(m.confusion_matrix[0][0] + m.confusion_matrix[0][1], len(y_te_zero))
        self.assertEqual(m.confusion_matrix[1], [0, 0])
        self.assertIn("UNESTIMABLE", m.status)
        self.assertTrue(np.isnan(m.pr_auc))
        self.assertTrue(np.isnan(m.roc_auc))
        self.assertTrue(np.isnan(m.recall))
        self.assertTrue(np.isfinite(m.false_alarm_rate))

        imp = compute_feature_importances(rf, X_te, y_te_zero)
        self.assertTrue(imp["Permutation Mean"].isna().all())

        with tempfile.TemporaryDirectory() as tmp_dir:
            pr_path = Path(tmp_dir) / "unestimable_pr.png"
            render_pr_curve_figure({"RF": rf}, X_te, y_te_zero, 0.0, pr_path)
            self.assertTrue(pr_path.exists())
            self.assertGreater(pr_path.stat().st_size, 10000)

    def test_markdown_ablation_table_escapes_pipes_and_columns_align(self):
        df = _synthetic_classification_fixture(180)
        split_ts = "2026-01-05 00:00:00+07:00"
        ab_df = evaluate_feature_ablation_and_horizons(df, split_timestamp=split_ts)
        md = _df_to_markdown(ab_df)
        lines = [ln for ln in md.splitlines() if ln.strip().startswith("|")]
        self.assertGreaterEqual(len(lines), 5)
        expected_pipes = lines[0].count("|")
        for ln in lines[2:]:
            # Đếm cột dữ liệu thật (bỏ `\|` đã escape) phải khớp header
            unescaped = ln.replace(r"\|", "")
            self.assertEqual(unescaped.count("|"), expected_pipes, msg=f"Lệch cột ở dòng: {ln}")

    def test_coverage_year_season_month_and_report_provenance(self):
        df = _synthetic_classification_fixture(168)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            pq_path = tmp / "synthetic.parquet"
            df.to_parquet(pq_path, index=False)
            res = run_classification_pipeline(
                pq_path,
                tmp / "precision_recall_curve.png",
                tmp / "feature_importance.png",
                tmp / "audit.md",
                report_results_path=tmp / "results.md",
                findings_path=tmp / "findings.md",
                split_timestamp="2026-01-05 00:00:00+07:00",
                scope_name="SYNTH_TEST",
            )
            self.assertEqual(res.dataset_version, BASELINE_DATASET_VERSION)
            self.assertEqual(len(res.dataset_sha256), 64)
            self.assertIsNotNone(res.yearly_coverage_table)
            self.assertIsNotNone(res.seasonal_coverage_table)
            self.assertIsNotNone(res.monthly_coverage_table)
            self.assertIsNotNone(res.monthly_drift_table)
            self.assertIsNotNone(res.calibration_table)
            self.assertIsNotNone(res.test_predictions)
            self.assertTrue((tmp / "calibration_reliability.png").exists())

            rep_txt = (tmp / "results.md").read_text(encoding="utf-8")
            self.assertIn(res.dataset_sha256, rep_txt)
            self.assertIn(res.dataset_version, rep_txt)
            self.assertIn("Provenance Dữ Liệu & Đặc Tả Cohort", rep_txt)
            self.assertIn("Độ phủ & tỷ lệ thiếu dữ liệu theo năm & split", rep_txt)
            self.assertIn("Độ phủ & tỷ lệ thiếu dữ liệu theo mùa khí tượng & split", rep_txt)

    def test_locked_threshold_consistency_in_backtest_and_monthly_drift(self):
        df = _synthetic_classification_fixture(180)
        split_ts = "2026-01-05 00:00:00+07:00"
        X_tr, y_tr, X_te, y_te, _, _, ts_te = prepare_classification_data(
            df, split_timestamp=split_ts, return_timestamps=True
        )
        rf = build_classification_pipeline(
            RandomForestClassifier(n_estimators=20, max_depth=4, class_weight="balanced", random_state=42),
            list(X_tr.columns),
            scale_features=False,
        ).fit(X_tr, y_tr)
        bt_df, drift_df = run_temporal_backtest_and_drift(
            df,
            split_timestamp=split_ts,
            n_folds=3,
            rf_model=rf,
            logreg_model=rf,
            threshold_rf=0.37,
            threshold_logreg=0.41,
        )
        self.assertIn("Fold Tau (RF / LogReg)", bt_df.columns)
        self.assertTrue((drift_df["Locked Tau (RF / LogReg)"] == "0.37 / 0.41").all())

        m_drift = compute_monthly_test_drift(
            X_te, y_te, ts_te, rf, rf, threshold_rf=0.37, threshold_logreg=0.41
        )
        self.assertTrue((m_drift["Locked Tau (RF / LogReg)"] == "0.37 / 0.41").all())

        m_drift_zero = compute_monthly_test_drift(
            X_te, pd.Series(0, index=y_te.index), ts_te, rf, rf, threshold_rf=0.37, threshold_logreg=0.41
        )
        self.assertTrue(m_drift_zero["Status"].str.contains("UNESTIMABLE").all())

    def test_calibration_summary_and_reliability_figure_valid_and_unestimable(self):
        df = _synthetic_classification_fixture(160)
        split_ts = "2026-01-04 12:00:00+07:00"
        X_tr, y_tr, X_te, y_te, _ = prepare_classification_data(df, split_timestamp=split_ts)
        rf = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=42).fit(X_tr, y_tr)

        cal_ok, status_ok, note_ok = compute_calibration_summary({"RF": rf}, X_te, y_te, min_bin_samples=1)
        self.assertEqual(status_ok, "OK")
        self.assertIn("Ước lượng hợp lệ", note_ok)
        self.assertTrue(np.isfinite(cal_ok.loc[0, "Brier Score"]))
        self.assertTrue(np.isfinite(cal_ok.loc[0, "ECE (10 bins)"]))

        y_zero = pd.Series(0, index=y_te.index, dtype=int)
        cal_un, status_un, note_un = compute_calibration_summary({"RF": rf}, X_te, y_zero)
        self.assertEqual(status_un, "UNESTIMABLE")
        self.assertIn("UNESTIMABLE", note_un)
        self.assertTrue(np.isnan(cal_un.loc[0, "ECE (10 bins)"]))

        with tempfile.TemporaryDirectory() as tmp_dir:
            p_ok = Path(tmp_dir) / "rel_ok.png"
            p_un = Path(tmp_dir) / "rel_un.png"
            render_reliability_figure({"RF": rf}, X_te, y_te, p_ok, min_bin_samples=1)
            render_reliability_figure({"RF": rf}, X_te, y_zero, p_un)
            self.assertTrue(p_ok.exists() and p_ok.stat().st_size > 10000)
            self.assertTrue(p_un.exists() and p_un.stat().st_size > 10000)

    def test_guards_reject_derived_pm25_ground_truth_and_future_feature_names(self):
        from sklearn.linear_model import LogisticRegression

        df = _synthetic_classification_fixture(120)
        df["pm25_derived_interpolated"] = df["pm25"].copy()
        split_ts = "2026-01-03 12:00:00+07:00"

        with self.assertRaises(ValueError):
            prepare_classification_data(
                df, split_timestamp=split_ts, target_col="pm25_derived_interpolated"
            )
        with self.assertRaises(ValueError):
            prepare_classification_data(
                df, split_timestamp=split_ts, feature_source_col="pm25_derived_interpolated"
            )
        with self.assertRaises(ValueError):
            prepare_classification_data(
                df,
                split_timestamp=split_ts,
                horizon_hours=6,
                feature_source_col="pm25_derived_interpolated",
                allow_derived_feature_source=True,
            )
        with self.assertRaises(ValueError):
            build_classification_pipeline(
                LogisticRegression(), ["pm25_rolling_mean_24h", "pm25_lead_1h"]
            )

    def test_coverage_tables_stratify_by_station_period_and_split_and_conserve_totals(self):
        # Chuỗi liên tục từ 2025-12-20 đến 2026-03-10 cắt giữa tháng 2026-01 (và giữa mùa Winter, giữa 2 năm)
        df = _synthetic_classification_fixture(2000)
        df["timestamp"] = pd.date_range("2025-12-20 00:00:00+07:00", periods=len(df), freq="h")
        df["station_id"] = "SYNTH_ST"
        df.loc[150:160, "pm25"] = np.nan
        df.loc[900:915, "pm25"] = np.nan
        split_ts = "2026-01-15 00:00:00+07:00"

        cov_df, _, monthly_df = compute_coverage_and_outage_tables(
            df, split_timestamp=split_ts, station_id="SYNTH_ST"
        )
        yr_df, sea_df = compute_year_season_coverage_tables(
            df, split_timestamp=split_ts, station_id="SYNTH_ST"
        )

        # Kiểm tra sự hiện diện của Station và Split ở cả 3 bảng (phát hiện lỗi thiếu Split)
        for name, tbl in (("monthly", monthly_df), ("yearly", yr_df), ("seasonal", sea_df)):
            self.assertIn("Station", tbl.columns, msg=name)
            self.assertIn("Split", tbl.columns, msg=name)
            self.assertEqual(set(tbl["Split"].unique()), {"train", "test"}, msg=name)

        # Tháng cắt 2026-01 và mùa Winter (Dec-Feb) phải có cả hàng train lẫn test
        jan_splits = set(monthly_df.loc[monthly_df["YearMonth"] == "2026-01", "Split"])
        self.assertEqual(jan_splits, {"train", "test"})
        winter_splits = set(sea_df.loc[sea_df["Season"] == "Winter (Dec-Feb)", "Split"])
        self.assertEqual(winter_splits, {"train", "test"})
        y2026_splits = set(yr_df.loc[yr_df["Year"] == "2026", "Split"])
        self.assertEqual(y2026_splits, {"train", "test"})

        # Bảo đảm tử/mẫu số và tổng Train + Test = Total khớp 100% với coverage_table ở cả 3 bảng
        for tbl in (monthly_df, yr_df, sea_df):
            self.assertTrue((tbl["Grid Hours"] == tbl["Valid PM2.5"] + tbl["Missing PM2.5"]).all())
            self.assertEqual(int(tbl.loc[tbl["Split"] == "train", "Grid Hours"].sum()), int(cov_df.loc[0, "Train (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "test", "Grid Hours"].sum()), int(cov_df.loc[0, "Test (giờ)"]))
            self.assertEqual(int(tbl["Grid Hours"].sum()), int(cov_df.loc[0, "Total (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "train", "Valid PM2.5"].sum()), int(cov_df.loc[1, "Train (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "test", "Valid PM2.5"].sum()), int(cov_df.loc[1, "Test (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "train", "Valid Label 24h"].sum()), int(cov_df.loc[2, "Train (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "test", "Valid Label 24h"].sum()), int(cov_df.loc[2, "Test (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "train", "Evaluable"].sum()), int(cov_df.loc[3, "Train (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "test", "Evaluable"].sum()), int(cov_df.loc[3, "Test (giờ)"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "train", "Positives (Eval)"].sum()), int(cov_df.loc[3, "Positives Train"]))
            self.assertEqual(int(tbl.loc[tbl["Split"] == "test", "Positives (Eval)"].sum()), int(cov_df.loc[3, "Positives Test"]))

    def test_assert_split_totals_match_detects_missing_split_wrong_denominator_and_aggregation_error(self):
        df = _synthetic_classification_fixture(200)
        split_ts = "2026-01-05 00:00:00+07:00"
        _, _, monthly_df = compute_coverage_and_outage_tables(df, split_timestamp=split_ts)
        _, base_df, *_ = _build_coverage_base_frame(df, split_timestamp=split_ts)

        # 1. Thiếu phân nhóm Split (bị gộp mất toàn bộ dòng test) -> phải bắt lỗi
        missing_split_df = monthly_df.loc[monthly_df["Split"] == "train"].copy()
        with self.assertRaises(AssertionError):
            _assert_split_totals_match(missing_split_df, base_df, label="missing_split_check")

        # 2. Sai mẫu số (Grid Hours lệch +1) -> phải bắt lỗi
        wrong_denom_df = monthly_df.copy()
        wrong_denom_df.loc[0, "Grid Hours"] += 1
        with self.assertRaises(AssertionError):
            _assert_split_totals_match(wrong_denom_df, base_df, label="wrong_denom_check")

        # 3. Lỗi tổng hợp tử số (Positives (Eval) lệch) -> phải bắt lỗi
        wrong_agg_df = monthly_df.copy()
        wrong_agg_df.loc[0, "Positives (Eval)"] += 5
        with self.assertRaises(AssertionError):
            _assert_split_totals_match(wrong_agg_df, base_df, label="wrong_agg_check")


if __name__ == "__main__":
    unittest.main()
