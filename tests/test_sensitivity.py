"""
tests/test_sensitivity.py — Bộ kiểm thử biên & hợp đồng tất định cho `src/sensitivity.py` (Issue #15).

Chạy hoàn toàn ngoại tuyến (KHÔNG phụ thuộc thư mục `data/`), kiểm chứng:
  1. Cô lập ranh giới trạm (`station_id`): tiêm cực trị đột biến vào cuối trạm A, khẳng định các dòng đầu trạm B
     hoàn toàn bất biến với mọi phép `lag_*`, `roll_mean_*`, nhãn cảnh báo và kỹ nghệ đặc trưng.
  2. Từ chối fail-closed đối với đầu vào gộp đa trạm (Protocol B), `station_id` NaN/rỗng, hoặc khóa trùng lặp.
  3. Bảo toàn số dòng (không row explosion) và không fit tiền xử lý trên tập Test (`validate_no_leakage`).
  4. Hợp đồng gắn nhãn ngưỡng: `40/45/55 µg/m³` KHÔNG BAO GIỜ mang nhãn `QCVN`; chỉ `50.0 µg/m³` tham chiếu
     `QCVN 05:2023/BTNMT (24h reference)`.
  5. Tính tương đương (parity) giữa chế độ baseline và extended `VN001` khi truyền cùng mốc cắt/giao thức,
     và khác biệt minh bạch khi mốc cắt khác nhau (`fixed_timestamp` vs `80/20`).
  6. Kiểm tra độ nhạy `pm25_derived_interpolated` KHÔNG BAO GIỜ sửa đổi `pm25` ground-truth hay `X_test` của Test.
  7. Xử lý an toàn `UNESTIMABLE` khi Test không có ca dương hoặc tầng mùa rỗng.
  8. Kiểm chứng SHA-256 bất biến artifact baseline phát hiện ngay mọi đột biến tệp.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.cleaning_pipeline import add_cyclical_time_features
from src.issue44_preparation import assign_station_chronological_split
from src.sensitivity import (
    QCVN_24H_LABEL,
    TECHNICAL_SENSITIVITY_LABEL,
    CohortSpec,
    add_station_past_lag_or_rolling_feature,
    classify_threshold_label,
    run_classification_threshold_sensitivity,
    run_coverage_min_periods_sensitivity,
    run_derived_interpolation_sensitivity,
    run_regression_lag_rolling_sensitivity,
    run_season_stratified_sensitivity,
    run_training_window_sensitivity,
    snapshot_artifact_hashes,
    validate_single_station_frame,
    verify_artifact_immutability,
)


def _make_synthetic_station_df(
    station_id: str,
    start: str = "2025-11-01 00:00:00+07:00",
    n_hours: int = 420,
    seed: int = 42,
    pm25_base: float = 48.0,
    pm25_amp: float = 22.0,
) -> pd.DataFrame:
    """Sinh chuỗi giờ tổng hợp tất định cho một trạm kèm đủ biến khí tượng & chu kỳ."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start=start, periods=n_hours, freq="1h")
    t = np.arange(n_hours, dtype=float)

    wind = np.clip(2.5 + 1.2 * np.sin(2 * np.pi * t / 24.0) + rng.normal(0, 0.4, n_hours), 0.1, 10.0)
    temp = 20.0 + 4.0 * np.sin(2 * np.pi * t / 24.0) + 2.0 * np.cos(2 * np.pi * t / 240.0) + rng.normal(0, 0.5, n_hours)
    rh = np.clip(75.0 - 8.0 * np.sin(2 * np.pi * t / 24.0) + rng.normal(0, 3.0, n_hours), 30.0, 99.0)
    precip = np.where(rng.random(n_hours) < 0.08, rng.exponential(1.5, n_hours), 0.0)
    press = 1015.0 + 3.0 * np.cos(2 * np.pi * t / 120.0) + rng.normal(0, 0.5, n_hours)

    # Tạo dao động PM2.5 rõ nét quanh ngưỡng 40..55 µg/m³ phụ thuộc vào gió và chu kỳ
    pm25 = np.clip(
        pm25_base
        + pm25_amp * np.sin(2 * np.pi * t / 96.0)
        - 5.0 * (wind - 2.5)
        - 1.5 * precip
        + rng.normal(0, 3.0, n_hours),
        5.0,
        220.0,
    )

    df = pd.DataFrame(
        {
            "timestamp": ts,
            "station_id": station_id,
            "pm25": pm25,
            "temperature": temp,
            "relative_humidity": rh,
            "wind_speed": wind,
            "precipitation": precip,
            "surface_pressure": press,
        }
    )
    return add_cyclical_time_features(df, timestamp_col="timestamp")


class TestSensitivityGuardsAndBoundaries(unittest.TestCase):
    """Kiểm thử cổng fail-closed, cô lập ranh giới trạm và nhãn ngưỡng."""

    def test_station_boundary_isolation_blocks_spike_leakage_across_stations(self) -> None:
        df_a = _make_synthetic_station_df("STATION_A", start="2025-11-01 00:00:00+07:00", n_hours=120, seed=1)
        df_b = _make_synthetic_station_df("STATION_B", start="2025-11-06 00:00:00+07:00", n_hours=120, seed=2)

        # Bản gốc không tiêm cực trị vào cuối trạm A
        pooled_clean = pd.concat([df_a, df_b], ignore_index=True)

        # Tiêm cực trị cực đại 9999.0 vào 48 giờ cuối của trạm A
        df_a_spiked = df_a.copy()
        df_a_spiked.loc[df_a_spiked.index[-48:], "pm25"] = 9999.0
        pooled_spiked = pd.concat([df_a_spiked, df_b], ignore_index=True)

        for spec in ("lag_6h", "lag_12h", "lag_24h", "lag_48h", "roll_mean_6h", "roll_mean_24h", "roll_mean_72h"):
            out_clean, col_name = add_station_past_lag_or_rolling_feature(pooled_clean, spec=spec)
            out_spiked, _ = add_station_past_lag_or_rolling_feature(pooled_spiked, spec=spec)
            assert col_name is not None

            # Không phát sinh row explosion
            self.assertEqual(len(out_clean), len(pooled_clean))
            self.assertEqual(len(out_spiked), len(pooled_spiked))

            # Toàn bộ các dòng của STATION_B phải hoàn toàn bất biến trước cực trị ở cuối STATION_A
            b_clean = out_clean.loc[out_clean["station_id"] == "STATION_B", col_name].reset_index(drop=True)
            b_spiked = out_spiked.loc[out_spiked["station_id"] == "STATION_B", col_name].reset_index(drop=True)
            pd.testing.assert_series_equal(b_clean, b_spiked, check_exact=False, rtol=0, atol=1e-12)

            # Các dòng đầu của STATION_B phải là NaN đúng bằng độ dài cửa sổ/độ trễ
            self.assertTrue(pd.isna(b_spiked.iloc[0]), f"First row of STATION_B must be NaN for {spec}")

    def test_protocol_b_pooled_multistation_rejected_fail_closed(self) -> None:
        df_a = _make_synthetic_station_df("VN001", n_hours=60, seed=10)
        df_b = _make_synthetic_station_df("VN003", n_hours=60, seed=11)
        pooled = pd.concat([df_a, df_b], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "Protocol B"):
            validate_single_station_frame(pooled, station_id=None)

    def test_nan_or_empty_station_id_and_duplicate_keys_rejected(self) -> None:
        df = _make_synthetic_station_df("VN001", n_hours=60, seed=12)

        df_nan = df.copy()
        df_nan.loc[5, "station_id"] = np.nan
        with self.assertRaisesRegex(ValueError, "NaN"):
            validate_single_station_frame(df_nan, station_id="VN001")

        df_empty = df.copy()
        df_empty.loc[5, "station_id"] = "   "
        with self.assertRaisesRegex(ValueError, "rỗng"):
            validate_single_station_frame(df_empty, station_id="VN001")

        df_dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "trùng lặp"):
            validate_single_station_frame(df_dup, station_id="VN001")

    def test_threshold_label_contract_only_50_references_qcvn(self) -> None:
        self.assertEqual(classify_threshold_label(50.0), QCVN_24H_LABEL)
        self.assertIn("QCVN 05:2023/BTNMT", classify_threshold_label(50.0))

        for tech_thr in (40.0, 45.0, 55.0, 35.0, 60.0):
            lbl = classify_threshold_label(tech_thr)
            self.assertEqual(lbl, TECHNICAL_SENSITIVITY_LABEL)
            self.assertNotIn("QCVN", lbl.upper())


class TestSensitivityPipelinesAndContracts(unittest.TestCase):
    """Kiểm thử parity, bất biến Test ground-truth, UNESTIMABLE và SHA-256."""

    def setUp(self) -> None:
        self.df_vn001 = _make_synthetic_station_df(
            "VN001_HANOI_556_NGUYEN_VAN_CU",
            start="2025-11-01 00:00:00+07:00",
            n_hours=480,
            seed=42,
        )
        self.split_ts = str(self.df_vn001["timestamp"].iloc[320])
        self.df_vn001_ext = assign_station_chronological_split(self.df_vn001.copy(), train_fraction=0.80)

    def test_parity_between_baseline_and_extended_vn001_under_identical_split(self) -> None:
        spec_base = CohortSpec(
            cohort_name="VN001_baseline",
            station_id="VN001_HANOI_556_NGUYEN_VAN_CU",
            dataset_version="1.0.0-m2-baseline",
            split_protocol=f"fixed_timestamp ({self.split_ts})",
            use_split_column=False,
            split_timestamp=self.split_ts,
        )
        # Extended frame có thêm trạm khác và cột split, nhưng chạy cùng mốc cắt fixed_timestamp trên VN001
        df_other = _make_synthetic_station_df("VN003_HANOI_OPENAQ_7441", start="2023-01-01 00:00:00+07:00", n_hours=120, seed=99)
        df_ext_multi = pd.concat([self.df_vn001_ext, assign_station_chronological_split(df_other, 0.80)], ignore_index=True)

        spec_ext_same_cut = CohortSpec(
            cohort_name="VN001_ext_same_cut",
            station_id="VN001_HANOI_556_NGUYEN_VAN_CU",
            dataset_version="2.0.0-issue44-extended",
            split_protocol=f"fixed_timestamp ({self.split_ts})",
            use_split_column=False,
            split_timestamp=self.split_ts,
        )

        res_base = run_classification_threshold_sensitivity(
            self.df_vn001, spec_base, run_id="test_parity", thresholds=(45.0, 50.0)
        )
        res_ext = run_classification_threshold_sensitivity(
            df_ext_multi, spec_ext_same_cut, run_id="test_parity", thresholds=(45.0, 50.0)
        )

        compare_cols = [
            "threshold_ug_m3", "threshold_label", "valid_n_train", "valid_n_test",
            "prevalence_train", "prevalence_test", "tuned_prob_threshold",
            "test_pr_auc", "test_recall", "test_precision", "test_f1", "test_f2", "test_far",
        ]
        pd.testing.assert_frame_equal(res_base[compare_cols], res_ext[compare_cols])

        # Ngược lại, khi dùng cột split 80/20 khác mốc cắt, valid_n_train/test phải khác nhau rõ ràng
        spec_ext_80_20 = CohortSpec(
            cohort_name="VN001_ext_80_20",
            station_id="VN001_HANOI_556_NGUYEN_VAN_CU",
            dataset_version="2.0.0-issue44-extended",
            split_protocol="station_specific_80_20",
            use_split_column=True,
        )
        res_80_20 = run_classification_threshold_sensitivity(
            df_ext_multi, spec_ext_80_20, run_id="test_diff", thresholds=(50.0,)
        )
        self.assertNotEqual(
            int(res_base.loc[res_base["threshold_ug_m3"] == 50.0, "valid_n_test"].iloc[0]),
            int(res_80_20["valid_n_test"].iloc[0]),
        )

    def test_derived_interpolation_never_modifies_test_ground_truth(self) -> None:
        df = self.df_vn001_ext.copy()
        # Tạo khoảng trống 2 giờ ở Train và 2 giờ ở Test
        tr_idx = df.index[df["split"] == "train"]
        te_idx = df.index[df["split"] == "test"]
        df["pm25_derived_interpolated"] = df["pm25"].copy()

        # Xóa 2 giờ ở Train (chỉ lấp trong pm25_derived_interpolated)
        df.loc[tr_idx[80:82], "pm25"] = np.nan
        # Cố tình tiêm giá trị sai lệch lớn vào pm25_derived_interpolated trên vùng Test
        # để chứng minh nhánh Test hoàn toàn bỏ qua pm25_derived_interpolated!
        df.loc[te_idx[20:22], "pm25"] = np.nan
        df.loc[te_idx[10:30], "pm25_derived_interpolated"] = 999.0

        spec = CohortSpec(
            cohort_name="VN001_ext_derived_test",
            station_id="VN001_HANOI_556_NGUYEN_VAN_CU",
            dataset_version="2.0.0-issue44-extended",
            split_protocol="station_specific_80_20",
            use_split_column=True,
        )
        der_df = run_derived_interpolation_sensitivity(df, spec, run_id="test_derived")
        self.assertEqual(len(der_df), 2)
        self.assertTrue(der_df["test_ground_truth_unchanged"].all())

        reg_row = der_df[der_df["task_type"] == "regression"].iloc[0]
        # Train phải thu hồi đúng 2 dòng từ khoảng trống Train; Test valid_n giữ nguyên trên pm25 quan trắc
        self.assertEqual(int(reg_row["recovered_train_rows"]), 2)
        self.assertEqual(int(reg_row["valid_n_test"]), int(df.loc[te_idx, "pm25"].notna().sum()))
        # RMSE không bị phá hỏng bởi giá trị 999.0 đã tiêm vào pm25_derived_interpolated của Test
        self.assertLess(float(reg_row["test_rmse_der"]), 50.0)

    def test_zero_positive_test_returns_unestimable_safely(self) -> None:
        df = self.df_vn001_ext.copy()
        # Ép toàn bộ Test có PM2.5 thấp (< 20 µg/m³) -> 0 ca dương tính ở ngưỡng 50.0
        df.loc[df["split"] == "test", "pm25"] = 15.0
        spec = CohortSpec(
            cohort_name="VN001_zero_pos_test",
            station_id="VN001_HANOI_556_NGUYEN_VAN_CU",
            dataset_version="2.0.0-issue44-extended",
            split_protocol="station_specific_80_20",
            use_split_column=True,
        )
        thr_df = run_classification_threshold_sensitivity(df, spec, run_id="test_unest", thresholds=(50.0,))
        self.assertIn("UNESTIMABLE", str(thr_df["status"].iloc[0]))
        self.assertTrue(np.isnan(float(thr_df["test_pr_auc"].iloc[0])))
        self.assertTrue(np.isnan(float(thr_df["test_recall"].iloc[0])))

    def test_coverage_regression_window_and_season_runs_end_to_end(self) -> None:
        spec = CohortSpec(
            cohort_name="VN001_full_smoke",
            station_id="VN001_HANOI_556_NGUYEN_VAN_CU",
            dataset_version="1.0.0-m2-baseline",
            split_protocol=f"fixed_timestamp ({self.split_ts})",
            use_split_column=False,
            split_timestamp=self.split_ts,
        )
        cov_df = run_coverage_min_periods_sensitivity(self.df_vn001, spec, run_id="smoke")
        self.assertEqual(list(cov_df["min_periods"]), [12, 18, 24])

        reg_df = run_regression_lag_rolling_sensitivity(
            self.df_vn001, spec, run_id="smoke", specs=("baseline_no_lag", "lag_6h", "roll_mean_24h")
        )
        self.assertEqual(list(reg_df["spec"]), ["baseline_no_lag", "lag_6h", "roll_mean_24h"])
        self.assertTrue(np.isfinite(reg_df["beta_wind_speed"]).all())
        self.assertTrue(np.isfinite(reg_df["se_wind_speed_hac24"]).all())

        win_df = run_training_window_sensitivity(self.df_vn001, spec, run_id="smoke")
        # 3 mức (50, 75, 100) × 2 bài toán (classification + regression) = 6 dòng
        self.assertEqual(len(win_df), 6)
        # Tập Test phải giữ nguyên cố định trên cả 3 mức cửa sổ Train
        cls_win = win_df[win_df["task_type"] == "classification"]
        self.assertEqual(cls_win["valid_n_test"].nunique(), 1)
        reg_win = win_df[win_df["task_type"] == "regression"]
        self.assertEqual(reg_win["valid_n_test"].nunique(), 1)

        seas_df = run_season_stratified_sensitivity(self.df_vn001, spec, run_id="smoke")
        # 4 mùa × 2 bài toán = 8 dòng; các mùa không xuất hiện trong Test phải mang trạng thái UNESTIMABLE
        self.assertEqual(len(seas_df), 8)
        empty_rows = seas_df[seas_df["valid_n_test"] == 0]
        self.assertGreater(len(empty_rows), 0)
        self.assertTrue(empty_rows["status"].str.contains("UNESTIMABLE").all())

    def test_baseline_sha256_immutability_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "baseline_dummy.txt"
            p.write_text("original-content\n", encoding="utf-8")
            before = snapshot_artifact_hashes({"dummy": p})
            after_same = snapshot_artifact_hashes({"dummy": p})
            verify_artifact_immutability(before, after_same)

            p.write_text("mutated-content\n", encoding="utf-8")
            after_mut = snapshot_artifact_hashes({"dummy": p})
            with self.assertRaisesRegex(AssertionError, "SHA-256"):
                verify_artifact_immutability(before, after_mut)


if __name__ == "__main__":
    unittest.main()
