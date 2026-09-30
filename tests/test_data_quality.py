"""
Unit Test Suite for Data Quality Audit Framework (Issue #5)
===========================================================
Kiểm thử tự động 10 tiêu chí bắt buộc theo đặc tả của đồ án INFO3020:
1. missing count
2. missing percentage
3. unique count
4. numeric statistics (min, max, median, 25%, 75%)
5. duplicate (station_id, timestamp)
6. invalid negative PM2.5 detection
7. humidity outside [0, 100] detection
8. zero/stuck-value detection
9. timestamp statistics (sampling intervals)
10. missingness by station/time
"""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_quality import (
    audit_dataframe,
    audit_uniqueness,
    audit_missing_representations,
    audit_prolonged_zeros,
    audit_six_dimensions,
    analyze_missingness_patterns,
    run_quality_audit_pipeline,
)


class TestDataQualityFramework(unittest.TestCase):
    """Bộ kiểm thử đơn vị cho framework kiểm toán chất lượng dữ liệu 6 chiều."""

    def setUp(self):
        """Khởi tạo các tập dữ liệu synthetic nhỏ phục vụ kiểm thử độc lập."""
        # 1. Dataset chuẩn mẫu
        self.ts_base = pd.date_range("2025-01-01 00:00:00+07:00", periods=10, freq="h")
        self.df_sample = pd.DataFrame({
            "timestamp": self.ts_base,
            "station_id": ["STATION_A"] * 5 + ["STATION_B"] * 5,
            "location": ["Hanoi"] * 10,
            "pm25": [10.0, 20.0, np.nan, 40.0, 50.0, 60.0, np.nan, 80.0, 90.0, 100.0],
            "pm10": [15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0, 105.0],
            "temperature": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0],
            "relative_humidity": [70, 75, 80, 85, 90, 92, 95, 60, 65, 50],
        })

    def test_1_missing_count(self):
        """1. Kiểm thử đếm chính xác số lượng giá trị khuyết thiếu per column."""
        audit_res = audit_dataframe(self.df_sample)
        pm25_row = audit_res[audit_res["column_name"] == "pm25"].iloc[0]
        temp_row = audit_res[audit_res["column_name"] == "temperature"].iloc[0]

        self.assertEqual(pm25_row["missing_count"], 2)
        self.assertEqual(temp_row["missing_count"], 0)

    def test_2_missing_percentage(self):
        """2. Kiểm thử tính toán chính xác tỷ lệ % khuyết thiếu."""
        audit_res = audit_dataframe(self.df_sample)
        pm25_row = audit_res[audit_res["column_name"] == "pm25"].iloc[0]
        # 2 / 10 = 20.0%
        self.assertEqual(pm25_row["missing_percentage"], 20.0)

    def test_3_unique_count(self):
        """3. Kiểm thử đếm đúng số lượng giá trị duy nhất (unique count)."""
        audit_res = audit_dataframe(self.df_sample)
        station_row = audit_res[audit_res["column_name"] == "station_id"].iloc[0]
        location_row = audit_res[audit_res["column_name"] == "location"].iloc[0]

        self.assertEqual(station_row["unique_count"], 2)
        self.assertEqual(location_row["unique_count"], 1)

    def test_4_numeric_statistics(self):
        """4. Kiểm thử tính toán thống kê số học (min, max, median, q25, q75)."""
        audit_res = audit_dataframe(self.df_sample)
        temp_row = audit_res[audit_res["column_name"] == "temperature"].iloc[0]

        self.assertEqual(temp_row["min"], 20.0)
        self.assertEqual(temp_row["max"], 29.0)
        self.assertEqual(temp_row["q50"], 24.5)  # median of [20..29]
        self.assertEqual(temp_row["q25"], 22.25)
        self.assertEqual(temp_row["q75"], 26.75)

    def test_5_duplicate_station_timestamp(self):
        """5. Kiểm thử phát hiện chính xác trùng lặp khóa quan sát (station_id, timestamp)."""
        # Tạo bản ghi trùng lặp
        df_dup = self.df_sample.copy()
        df_dup = pd.concat([df_dup, df_dup.iloc[[0]]], ignore_index=True)

        res_no_dup = audit_uniqueness(self.df_sample, key_cols=["station_id", "timestamp"])
        self.assertFalse(res_no_dup["has_duplicates"])
        self.assertEqual(res_no_dup["duplicate_rows"], 0)

        res_dup = audit_uniqueness(df_dup, key_cols=["station_id", "timestamp"])
        self.assertTrue(res_dup["has_duplicates"])
        self.assertEqual(res_dup["duplicate_rows"], 1)
        self.assertEqual(res_dup["affected_rows_total"], 2)

    def test_6_invalid_negative_pm25_detection(self):
        """6. Kiểm thử phát hiện vi phạm giới hạn nồng độ bụi âm (PM2.5 < 0)."""
        df_negative = self.df_sample.copy()
        df_negative.loc[0, "pm25"] = -15.5
        df_negative.loc[1, "pm25"] = -0.1

        dims = audit_six_dimensions(df_negative)
        pm25_checks = dims["dimensions"]["accuracy"]["atmospheric_boundary_checks"]["pm25"]

        self.assertEqual(pm25_checks["violations_below_min"], 2)
        self.assertEqual(pm25_checks["total_violations"], 2)

    def test_7_humidity_outside_zero_to_hundred(self):
        """7. Kiểm thử phát hiện độ ẩm tương đối ngoài khoảng [0, 100%]."""
        df_bad_rh = self.df_sample.copy()
        df_bad_rh.loc[0, "relative_humidity"] = -5
        df_bad_rh.loc[1, "relative_humidity"] = 105

        dims = audit_six_dimensions(df_bad_rh)
        rh_checks = dims["dimensions"]["accuracy"]["atmospheric_boundary_checks"]["relative_humidity"]

        self.assertEqual(rh_checks["violations_below_min"], 1)
        self.assertEqual(rh_checks["violations_above_max"], 1)
        self.assertEqual(rh_checks["total_violations"], 2)

    def test_8_zero_stuck_value_detection(self):
        """8. Kiểm thử phát hiện và đo lường chuỗi giá trị 0 kéo dài (prolonged zeros)."""
        # Tạo chuỗi zero 7 giờ liên tiếp cùng 1 trạm
        df_zero = self.df_sample.copy()
        df_zero["station_id"] = "STATION_A"
        df_zero["pm25"] = [10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 60.0]

        zeros_audit = audit_prolonged_zeros(df_zero, target_cols=["pm25"], threshold_hours=6)
        pm25_zero_res = zeros_audit["pm25"]

        self.assertEqual(pm25_zero_res["zero_count"], 7)
        self.assertEqual(pm25_zero_res["longest_zero_streak_hours"], 7)
        self.assertEqual(pm25_zero_res["prolonged_zero_streaks_count"], 1)
        self.assertEqual(len(pm25_zero_res["prolonged_streaks_details"]), 1)
        self.assertEqual(pm25_zero_res["prolonged_streaks_details"][0]["streak_length_hours"], 7)

    def test_8b_prolonged_zeros_timestamp_gap_aware(self):
        """8b. Regression Test: Kiểm thử khoảng trống thời gian (gap) phải ngắt streak số 0."""
        # 4 số 0 liên tiếp, sau đó nhảy cóc 3 giờ, rồi tiếp tục 4 số 0
        ts_gap = [
            pd.Timestamp("2025-01-01 00:00:00+07:00"),
            pd.Timestamp("2025-01-01 01:00:00+07:00"),
            pd.Timestamp("2025-01-01 02:00:00+07:00"),
            pd.Timestamp("2025-01-01 03:00:00+07:00"),
            # Gap: nhảy thẳng từ 03:00 sang 06:00 (cách 3 giờ)
            pd.Timestamp("2025-01-01 06:00:00+07:00"),
            pd.Timestamp("2025-01-01 07:00:00+07:00"),
            pd.Timestamp("2025-01-01 08:00:00+07:00"),
            pd.Timestamp("2025-01-01 09:00:00+07:00"),
        ]
        df_gap = pd.DataFrame({
            "timestamp": ts_gap,
            "pm25": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        })
        # Ngưỡng 6 giờ: Mỗi đoạn chỉ dài 4 giờ -> không được coi là prolonged zero (>=6h)
        zeros_audit = audit_prolonged_zeros(df_gap, target_cols=["pm25"], threshold_hours=6)
        res = zeros_audit["pm25"]

        self.assertEqual(res["zero_count"], 8)
        self.assertEqual(res["longest_zero_streak_hours"], 4)  # Gap làm đứt streak
        self.assertEqual(res["prolonged_zero_streaks_count"], 0)

    def test_8c_prolonged_zeros_multi_station_aware(self):
        """8c. Regression Test: Kiểm thử không nối chuỗi zero giữa các trạm khác nhau."""
        ts_common = pd.date_range("2025-01-01 00:00:00+07:00", periods=5, freq="h")
        # Station A có 4 số 0, Station B có 4 số 0 (cả 2 đều < 6h)
        df_multi = pd.DataFrame({
            "timestamp": list(ts_common) + list(ts_common),
            "station_id": ["STATION_A"] * 5 + ["STATION_B"] * 5,
            "pm25": [0.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0, 20.0],
        })
        zeros_audit = audit_prolonged_zeros(df_multi, target_cols=["pm25"], threshold_hours=6)
        res = zeros_audit["pm25"]

        self.assertEqual(res["zero_count"], 8)
        self.assertEqual(res["longest_zero_streak_hours"], 4)  # Không bị cộng dồn thành 8
        self.assertEqual(res["prolonged_zero_streaks_count"], 0)

    def test_9_timestamp_statistics_and_sampling_intervals(self):
        """9. Kiểm thử tính toán dải thời gian min/max và khoảng cách lấy mẫu (sampling interval)."""
        # Tạo khoảng cách lấy mẫu có 1 chỗ nhảy 3 giờ
        ts_custom = [
            pd.Timestamp("2025-01-01 00:00:00+07:00"),
            pd.Timestamp("2025-01-01 01:00:00+07:00"),
            pd.Timestamp("2025-01-01 04:00:00+07:00"),  # Nhảy 3h
            pd.Timestamp("2025-01-01 05:00:00+07:00"),
        ]
        df_ts = pd.DataFrame({"timestamp": ts_custom, "pm25": [10.0, 20.0, 30.0, 40.0]})

        dims = audit_six_dimensions(df_ts)
        timeliness = dims["dimensions"]["timeliness"]
        profile = timeliness["sampling_interval_profile"]

        self.assertEqual(timeliness["actual_min_timestamp"], "2025-01-01 00:00:00+07:00")
        self.assertEqual(timeliness["actual_max_timestamp"], "2025-01-01 05:00:00+07:00")
        self.assertEqual(profile["min_interval_hours"], 1.0)
        self.assertEqual(profile["max_interval_hours"], 3.0)
        self.assertEqual(profile["irregular_intervals_count"], 1)

    def test_10_missingness_by_station_and_source(self):
        """10. Kiểm thử phân tích hình thái khuyết thiếu theo trạm và nguồn (reusable metrics)."""
        df_with_source = self.df_sample.copy()
        df_with_source["source"] = ["OpenAQ"] * 5 + ["AirNow"] * 5

        patterns = analyze_missingness_patterns(df_with_source, target_col="pm25")

        self.assertEqual(patterns["target_variable"], "pm25")
        self.assertEqual(patterns["missing_count"], 2)
        self.assertEqual(patterns["missing_pct"], 20.0)

        # Kiểm tra reusable metrics theo station_id
        self.assertIn("missingness_by_station", patterns)
        stn_res = patterns["missingness_by_station"]
        self.assertEqual(stn_res["STATION_A"]["missing_count"], 1)
        self.assertEqual(stn_res["STATION_A"]["total_records"], 5)
        self.assertEqual(stn_res["STATION_A"]["missing_pct"], 20.0)
        self.assertEqual(stn_res["STATION_B"]["missing_count"], 1)

        # Kiểm tra reusable metrics theo source
        self.assertIn("missingness_by_source", patterns)
        src_res = patterns["missingness_by_source"]
        self.assertEqual(src_res["OpenAQ"]["missing_count"], 1)
        self.assertEqual(src_res["OpenAQ"]["total_records"], 5)
        self.assertEqual(src_res["AirNow"]["missing_count"], 1)

        # Kiểm tra chẩn đoán Rubin
        self.assertIn("rubin_diagnosis", patterns)
        self.assertIn("mcar_diagnostic_hypothesis", patterns["rubin_diagnosis"])
        self.assertIn("uncertainty_declaration", patterns["rubin_diagnosis"])

    def test_11_diurnal_denominator_exactness(self):
        """11. Regression Test: Kiểm thử mẫu số tính missingness theo giờ dùng total records (size), không dùng count."""
        # Tạo 2 dòng cùng vào lúc 08:00: 1 dòng quan sát (pm25=50), 1 dòng missing (pm25=NaN)
        ts_hr = [
            pd.Timestamp("2025-01-01 08:00:00+07:00"),
            pd.Timestamp("2025-01-02 08:00:00+07:00"),
        ]
        df_hr = pd.DataFrame({"timestamp": ts_hr, "pm25": [50.0, np.nan]})
        patterns = analyze_missingness_patterns(df_hr, target_col="pm25")

        diurnal = patterns["diurnal_missing_pattern"]
        self.assertIn(8, diurnal)
        # Mẫu số đúng là 2 (tổng số bản ghi), không phải 1 (số giá trị non-null)
        self.assertEqual(diurnal[8]["total"], 2)
        self.assertEqual(diurnal[8]["missing"], 1)
        self.assertEqual(diurnal[8]["missing_pct"], 50.0)

    def test_12_aerodynamic_inversion_strict_and_tolerance(self):
        """12. Regression Test: Kiểm thử ràng buộc PM2.5 <= PM10 cả vi phạm chặt và dung sai sai số đo."""
        df_aero = pd.DataFrame({
            "pm25": [20.0, 31.0, 35.0],
            "pm10": [25.0, 30.0, 30.0],
            # Cặp 1: 20 <= 25 (Hợp lệ)
            # Cặp 2: 31 > 30 (Vi phạm strict, nhưng <= 30 + 2.0 -> trong ngưỡng dung sai)
            # Cặp 3: 35 > 30 (Vi phạm strict và vượt cả ngưỡng 30 + 2.0)
        })
        dims = audit_six_dimensions(df_aero)
        aero = dims["dimensions"]["accuracy"]["aerodynamic_subset_inversion"]

        self.assertEqual(aero["evaluated_pairs"], 3)
        self.assertEqual(aero["strict_inversion_count"], 2)
        self.assertEqual(round(aero["strict_inversion_pct"], 2), 66.67)
        self.assertEqual(aero["tolerance_inversion_count"], 1)
        self.assertEqual(round(aero["tolerance_inversion_pct"], 2), 33.33)
        self.assertIn("documentation_rationale", aero)


class TestAuditSixDimensionUntestedBlocks(unittest.TestCase):
    """Ba khối của báo cáo 6 chiều chưa có assertion nào.

    Sản phẩm bàn giao của Issue #5 là BÁO CÁO 6 CHIỀU. Nếu ba khối dưới đây
    hỏng mà không ai biết thì báo cáo vẫn "hoàn thành" về mặt hình thức.
    """

    def setUp(self):
        self.ts = pd.date_range("2025-01-01 00:00:00+07:00", periods=8, freq="h")
        self.df = pd.DataFrame({
            "timestamp": self.ts,
            "station_id": ["STATION_A"] * 8,
            "location": ["Hanoi"] * 8,
            "pm25": [10.0, 20.0, np.nan, 40.0, 50.0, 60.0, 70.0, 80.0],
            "pm10": [15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0],
        })

    def test_temporal_grid_completeness_counts_the_gaps(self):
        """8 quan sát nhưng lưới 1 giờ giữa min và max chỉ dài 8 — 0 khoảng trống."""
        dims = audit_six_dimensions(self.df)
        grid = dims["dimensions"]["completeness"]["temporal_grid_completeness"]
        self.assertEqual(grid["expected_continuous_hours"], 8)
        self.assertEqual(grid["actual_recorded_hours"], 8)
        self.assertEqual(grid["unrecorded_hours_gaps"], 0)
        self.assertEqual(grid["unrecorded_hours_pct"], 0.0)

    def test_temporal_grid_completeness_detects_a_real_gap(self):
        """Bỏ 3 giờ giữa chuỗi -> phải báo đúng 3 giờ trống."""
        gapped = self.df.drop(index=[3, 4, 5]).reset_index(drop=True)
        dims = audit_six_dimensions(gapped)
        grid = dims["dimensions"]["completeness"]["temporal_grid_completeness"]
        self.assertEqual(grid["expected_continuous_hours"], 8)
        self.assertEqual(grid["actual_recorded_hours"], 5)
        self.assertEqual(grid["unrecorded_hours_gaps"], 3)
        self.assertEqual(grid["unrecorded_hours_pct"], 37.5)

    def test_high_humidity_fog_evidence_is_reported(self):
        """Chiều Accuracy phải chứa bằng chứng sương mù quang học (RH > 90%)."""
        df = self.df.assign(relative_humidity=[50.0, 95.0, 91.0, 90.0, 100.0,
                                              80.0, 70.0, 60.0])
        dims = audit_six_dimensions(df)
        fog = dims["dimensions"]["accuracy"]["high_humidity_fog_evidence"]
        # > 90 (không phải >= 90): 95, 91, 100 -> 3 giờ
        self.assertEqual(fog["high_humidity_hours"], 3)
        self.assertEqual(fog["threshold"], "> 90%")
        self.assertIn("Issue #6", fog["audit_note"])

    def test_high_humidity_fog_evidence_is_none_without_humidity(self):
        dims = audit_six_dimensions(self.df)
        self.assertIsNone(dims["dimensions"]["accuracy"]["high_humidity_fog_evidence"])

    def test_validity_dimension_reports_every_column(self):
        """Chiều Validity phải phủ đủ mọi cột và đánh dấu đúng kiểu."""
        dims = audit_six_dimensions(self.df)
        validity = dims["dimensions"]["validity"]
        self.assertTrue(validity["all_columns_conformant"])
        self.assertEqual(set(validity["column_validity"]), set(self.df.columns))
        self.assertIn("datetime64", validity["column_validity"]["timestamp"]["actual_dtype"])
        self.assertTrue(validity["column_validity"]["station_id"]["is_schema_conformant"])
        self.assertTrue(validity["column_validity"]["pm25"]["is_schema_conformant"])

    def test_validity_dimension_rejects_a_string_measurement_column(self):
        """Cột đo kiểu chuỗi là vi phạm schema — phải BÁO CÁO, không được sập.

        Bản gốc ném `TypeError: '>' not supported between 'str' and 'float'` tại
        phép so khí động học trước khi tới khối Validity. Tức là bộ kiểm toán
        chết vì đúng cái lỗi mà nó được giao để tìm — và không trả báo cáo nào.
        Nay nó bỏ qua phép so trên cột không phải số VÀ vẫn đánh dấu vi phạm.
        """
        df = self.df.copy()
        df["pm25"] = df["pm25"].astype(str)
        dims = audit_six_dimensions(df)          # không được ném lỗi
        validity = dims["dimensions"]["validity"]
        self.assertFalse(validity["column_validity"]["pm25"]["is_schema_conformant"])
        self.assertFalse(validity["all_columns_conformant"])
        # Phép so khí động học không thể chạy -> None, KHÔNG phải 0 (0 là khẳng
        # định sai sự thật: "không có nghịch đảo nào" khác "không đo được").
        self.assertIsNone(dims["dimensions"]["accuracy"]["aerodynamic_subset_inversion"])

    def test_string_humidity_column_does_not_crash_the_audit(self):
        df = self.df.copy()
        df["relative_humidity"] = ["50.0", "95.0", "80.0", "70.0",
                                   "60.0", "99.0", "55.0", "65.0"]
        dims = audit_six_dimensions(df)
        self.assertIsNone(dims["dimensions"]["accuracy"]["high_humidity_fog_evidence"])
        self.assertFalse(
            dims["dimensions"]["validity"]["column_validity"]["relative_humidity"]["is_schema_conformant"]
        )

    def test_completeness_missing_by_variable_is_reported(self):
        dims = audit_six_dimensions(self.df)
        by_var = dims["dimensions"]["completeness"]["missing_by_variable"]
        self.assertEqual(by_var["pm25"]["missing_count"], 1)
        self.assertEqual(by_var["pm25"]["missing_pct"], 12.5)
        self.assertEqual(by_var["pm10"]["missing_count"], 0)


class TestMissingnessPatternUntestedBlocks(unittest.TestCase):
    """`missing_blocks` và `co_missing_analysis` chưa có assertion nào."""

    def setUp(self):
        # Chuỗi: 2 giá trị, 1 khối trống 1h, 2 giá trị, 1 khối trống 3h, 2 giá trị.
        self.df = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01 00:00:00+07:00", periods=11, freq="h"),
            "station_id": ["STATION_A"] * 11,
            "pm25": [10.0, 11.0, np.nan, 12.0, 13.0, np.nan, np.nan, np.nan, 14.0, 15.0, 16.0],
            "pm10": [20.0, 21.0, np.nan, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0],
        })

    def test_missing_blocks_are_segmented(self):
        out = analyze_missingness_patterns(self.df, target_col="pm25")
        blocks = out["missing_blocks"]
        self.assertEqual(blocks["total_blocks"], 2)
        self.assertEqual(blocks["isolated_1h_drops"], 1)
        self.assertEqual(blocks["multi_hour_outages"], 1)
        self.assertEqual(blocks["longest_block_hours"], 3)
        self.assertEqual(blocks["block_length_distribution"], {1: 1, 3: 1})

    def test_missing_blocks_on_a_fully_observed_column(self):
        out = analyze_missingness_patterns(self.df, target_col="pm10")
        blocks = out["missing_blocks"]
        self.assertEqual(blocks["total_blocks"], 1)
        self.assertEqual(blocks["longest_block_hours"], 1)

    def test_co_missing_analysis_separates_both_channels(self):
        out = analyze_missingness_patterns(self.df, target_col="pm25")
        co = out["co_missing_analysis"]
        # pm25 NaN ở 4 hàng (index 2, 5, 6, 7); chỉ index 2 có pm10 cũng NaN.
        self.assertEqual(co["both_pm25_and_pm10_missing"], 1)
        self.assertEqual(co["pm25_missing_pm10_observed"], 3)
        self.assertEqual(co["pm10_missing_pm25_observed"], 0)
        self.assertIsNotNone(co["pm10_median_during_pm25_missing"])
        self.assertGreater(co["pm10_mean_overall"], 0.0)

    def test_missing_target_column_raises(self):
        with self.assertRaises(KeyError):
            analyze_missingness_patterns(self.df, target_col="pm999")

    def test_rubin_diagnosis_declares_uncertainty(self):
        """AC #5 bắt buộc phải GHI NHẬN bất định, không gán nhãn võ đoán."""
        out = analyze_missingness_patterns(self.df, target_col="pm25")
        rubin = out["rubin_diagnosis"]
        for key in ("mcar_diagnostic_hypothesis", "mar_diagnostic_hypothesis",
                    "mnar_diagnostic_hypothesis", "uncertainty_declaration"):
            self.assertIn(key, rubin)
        self.assertIn("TUYÊN BỐ BẤT ĐỊNH", rubin["uncertainty_declaration"])


class TestProlongedZeroThresholdBoundary(unittest.TestCase):
    """Ngưỡng `>= 6` của #5 chỉ phân biệt được với chuỗi ĐÚNG 6 quan sát.

    Fixture cũ dùng chuỗi 7 và chuỗi 4, nên `>= 6` và `> 6` cho cùng kết quả.
    """

    def _streak(self, length):
        ts = pd.date_range("2025-01-01 00:00:00+07:00", periods=length + 1, freq="h")
        values = [0.0] * length + [5.0]     # chuỗi 0.0 dài `length`, rồi ngắt
        return pd.DataFrame({
            "timestamp": ts,
            "station_id": ["STATION_A"] * (length + 1),
            "pm25": values,
        })

    def test_exactly_six_hours_counts_as_prolonged(self):
        result = audit_prolonged_zeros(self._streak(6), target_cols=["pm25"])
        self.assertEqual(result["pm25"]["longest_zero_streak_hours"], 6)
        self.assertEqual(result["pm25"]["prolonged_zero_streaks_count"], 1,
                         "chuỗi đúng 6 giờ phải được tính là kéo dài (ngưỡng >= 6)")

    def test_five_hours_is_not_prolonged(self):
        result = audit_prolonged_zeros(self._streak(5), target_cols=["pm25"])
        self.assertEqual(result["pm25"]["longest_zero_streak_hours"], 5)
        self.assertEqual(result["pm25"]["prolonged_zero_streaks_count"], 0,
                         "chuỗi 5 giờ chưa đạt ngưỡng >= 6")

    def test_threshold_is_configurable(self):
        result = audit_prolonged_zeros(self._streak(5), target_cols=["pm25"],
                                       threshold_hours=5)
        self.assertEqual(result["pm25"]["prolonged_zero_streaks_count"], 1)


class TestAuditMissingRepresentations(unittest.TestCase):
    """`audit_missing_representations()` được import nhưng KHÔNG test nào gọi."""

    def test_reports_nan_and_disguised_string_markers(self):
        df = pd.DataFrame({
            "pm25": [1.0, np.nan, "N/A", "null"],
            "pm10": [1.0, 2.0, 3.0, 4.0],
        })
        report = audit_missing_representations(df)
        self.assertEqual(report["pm25"]["np_nan"], 1)
        self.assertEqual(report["pm25"]["str_'N/A'"], 1)
        self.assertEqual(report["pm25"]["str_'null'"], 1)
        # pm10 sạch -> dict rỗng, KHÔNG khai báo có marker nào tồn tại.
        self.assertEqual(report["pm10"], {})

    def test_absent_markers_are_not_reported(self):
        """Không khai báo hình thái khuyết thiếu không tồn tại — trung thực."""
        df = pd.DataFrame({"pm25": [1.0, 2.0], "pm10": [1.0, np.nan]})
        report = audit_missing_representations(df)
        self.assertEqual(report["pm25"], {})
        self.assertEqual(report["pm10"], {"np_nan": 1})

    def test_rejects_none(self):
        with self.assertRaises(ValueError):
            audit_missing_representations(None)


class TestRunQualityAuditPipeline(unittest.TestCase):
    """Điểm vào chính của Issue #5 có 0 test tham chiếu."""

    def test_pipeline_returns_both_datasets_with_all_sections(self):
        import tempfile
        from pathlib import Path

        from src.data_quality import run_quality_audit_pipeline

        ts = pd.date_range("2025-01-01 00:00:00+07:00", periods=8, freq="h")
        air = pd.DataFrame({
            "timestamp": ts, "station_id": ["A"] * 8, "location": ["Hanoi"] * 8,
            "pm25": [10.0, 20.0, np.nan, 40.0, 50.0, 60.0, 70.0, 80.0],
            "pm10": [15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0],
        })
        wx = pd.DataFrame({
            "timestamp": ts,
            "temperature": np.arange(20.0, 28.0),
            "relative_humidity": np.full(8, 80.0),
            "wind_speed": np.arange(1.0, 9.0),
            "wind_direction": np.arange(10.0, 18.0),
            "precipitation": np.zeros(8),
            "surface_pressure": np.full(8, 1010.0),
        })
        with tempfile.TemporaryDirectory() as tmp:
            air_path = Path(tmp) / "air.parquet"
            wx_path = Path(tmp) / "wx.parquet"
            air.to_parquet(air_path, index=False)
            wx.to_parquet(wx_path, index=False)
            results = run_quality_audit_pipeline(air_path, wx_path)

        self.assertEqual(set(results), {"air_quality", "weather"})
        for section in ("summary_table", "six_dimensions", "prolonged_zeros",
                        "uniqueness", "missing_representations"):
            self.assertIn(section, results["air_quality"])
        self.assertIn("missingness_patterns", results["air_quality"])
        for section in ("summary_table", "six_dimensions", "prolonged_zeros",
                        "uniqueness", "missing_representations"):
            self.assertIn(section, results["weather"])

    def test_missing_files_are_skipped_not_fatal(self):
        from src.data_quality import run_quality_audit_pipeline
        results = run_quality_audit_pipeline(
            Path("does/not/exist_air.parquet"), Path("does/not/exist_wx.parquet")
        )
        self.assertEqual(results, {})


class TestTemporalGridMultiStation(unittest.TestCase):
    """Review #34: `temporal_grid_completeness` trộn hai đại lượng khác nhau.

    Bản gốc lấy `expected_grid` từ `min_ts → max_ts` của CẢ DataFrame nhưng trừ
    `len(df)` — tức chiều dài lưới *toàn khung* trừ số dòng của *mọi trạm*. Với
    nhiều trạm, kết quả sai theo hướng nguy hiểm:

    - 2 trạm × 8 giờ đều đầy đủ → `8 - 16 = -8`, tức **-100%**. Số âm.
    - Trạm B mất thật 3 giờ → vẫn ra số âm, tức **khoảng trống bị giấu hoàn toàn**.

    Nay tính theo từng trạm rồi cộng, với mẫu số là cửa sổ triển khai dùng chung
    (`min → max` toàn khung) × số trạm. Bắt được cả ba loại thiếu hút:
    khoảng trống nội bộ, trạm vắng mặt, và coverage bị cắt cụt ở hai mép.
    """

    TZ = "Asia/Ho_Chi_Minh"

    def _frame(self, station, hours, start="2025-01-01 00:00"):
        ts = pd.date_range(start, periods=hours, freq="h", tz=self.TZ)
        return pd.DataFrame({
            "timestamp": ts,
            "station_id": [station] * hours,
            "location": ["Hanoi"] * hours,
            "pm25": np.full(hours, 10.0),
            "pm10": np.full(hours, 12.0),
        })

    def _grid(self, df):
        return (audit_six_dimensions(df)["dimensions"]["completeness"]
                ["temporal_grid_completeness"])

    def test_two_complete_stations_report_zero_gaps_not_a_negative(self):
        """Bản gốc: unrecorded = -8, pct = -100.0. Nay phải là 0."""
        df = pd.concat([self._frame("A", 8), self._frame("B", 8)],
                       ignore_index=True)
        grid = self._grid(df)
        self.assertEqual(grid["unrecorded_hours_gaps"], 0)
        self.assertEqual(grid["unrecorded_hours_pct"], 0.0)
        self.assertEqual(grid["expected_continuous_hours"], 16,
                         "8 giờ chung × 2 trạm")
        self.assertEqual(grid["actual_recorded_hours"], 16)
        self.assertEqual(grid["stations_evaluated"], 2)
        self.assertEqual(grid["per_station"]["A"]["missing_vs_shared_window_hours"], 0)
        self.assertEqual(grid["per_station"]["B"]["missing_vs_shared_window_hours"], 0)

    def test_the_gap_count_is_never_negative(self):
        """Bất biến chung cho mọi số trạm — đây là lỗi gốc."""
        for n_stations in (1, 2, 3, 5):
            df = pd.concat(
                [self._frame("ST%d" % k, 8) for k in range(n_stations)],
                ignore_index=True)
            grid = self._grid(df)
            self.assertGreaterEqual(
                grid["unrecorded_hours_gaps"], 0,
                "%d tram day du phai ra so khong am" % n_stations)
            self.assertGreaterEqual(grid["unrecorded_hours_pct"], 0.0)
            self.assertEqual(grid["unrecorded_hours_gaps"], 0)

    def test_a_station_missing_hours_is_no_longer_hidden(self):
        """Trạm B chỉ quan sát 5/8 giờ đầu — bản gốc báo số âm, tức giấu mất 3 giờ."""
        df = pd.concat([self._frame("A", 8), self._frame("B", 5)],
                       ignore_index=True)
        grid = self._grid(df)
        self.assertEqual(grid["unrecorded_hours_gaps"], 3)
        self.assertEqual(grid["per_station"]["A"]["missing_vs_shared_window_hours"], 0)
        self.assertEqual(grid["per_station"]["B"]["missing_vs_shared_window_hours"], 3)

    def test_an_internal_gap_inside_one_station_is_counted(self):
        """Khoảng trống nằm GIỮA cửa sổ của riêng trạm B."""
        b = self._frame("B", 8).drop(index=[3, 4, 5])
        df = pd.concat([self._frame("A", 8), b], ignore_index=True)
        grid = self._grid(df)
        self.assertEqual(grid["unrecorded_hours_gaps"], 3)
        self.assertEqual(grid["per_station"]["B"]["internal_gap_hours"], 3)
        self.assertEqual(grid["per_station"]["A"]["internal_gap_hours"], 0)

    def test_stations_with_disjoint_windows_surface_the_coverage_shortfall(self):
        """A quan sát 00–07, B quan sát 10–17: cả hai tự chúng đềy đủ, nhưng trong
        cửa sổ triển khai chung thì thiếu 20 giờ — phải được phản ánh."""
        df = pd.concat(
            [self._frame("A", 8), self._frame("B", 8, start="2025-01-01 10:00")],
            ignore_index=True)
        grid = self._grid(df)
        self.assertEqual(grid["shared_window_hours"], 18)
        self.assertEqual(grid["expected_continuous_hours"], 36)
        self.assertEqual(grid["actual_recorded_hours"], 16)
        self.assertEqual(grid["unrecorded_hours_gaps"], 20)
        # Cả hai vẫn "đầy đủ" trong cửa sổ riêng — hai sự thật khác nhau.
        self.assertEqual(grid["per_station"]["A"]["internal_gap_hours"], 0)
        self.assertEqual(grid["per_station"]["B"]["internal_gap_hours"], 0)
        self.assertEqual(grid["per_station"]["A"]["missing_vs_shared_window_hours"], 10)

    def test_single_station_behaviour_is_unchanged(self):
        """Đối chiếu hành vi một trạm so với trước khi sửa."""
        df = self._frame("A", 8)
        grid = self._grid(df)
        self.assertEqual(grid["expected_continuous_hours"], 8)
        self.assertEqual(grid["actual_recorded_hours"], 8)
        self.assertEqual(grid["unrecorded_hours_gaps"], 0)
        self.assertEqual(grid["stations_evaluated"], 1)

    def test_single_station_internal_gap(self):
        df = self._frame("A", 8).drop(index=[3, 4, 5]).reset_index(drop=True)
        grid = self._grid(df)
        self.assertEqual(grid["expected_continuous_hours"], 8)
        self.assertEqual(grid["unrecorded_hours_gaps"], 3)
        self.assertEqual(grid["unrecorded_hours_pct"], 37.5)

    def test_dataset_without_station_column_still_works(self):
        df = self._frame("A", 8).drop(columns=["station_id"])
        grid = self._grid(df)
        self.assertEqual(grid["stations_evaluated"], 1)
        self.assertEqual(grid["unrecorded_hours_gaps"], 0)
        self.assertIn("(khong co cot station_id)", grid["per_station"])

    def test_per_station_windows_are_reported_for_transparency(self):
        df = pd.concat([self._frame("A", 8), self._frame("B", 5)],
                       ignore_index=True)
        grid = self._grid(df)
        b = grid["per_station"]["B"]
        self.assertTrue(b["window_start"].startswith("2025-01-01T00:00"))
        self.assertTrue(b["window_end"].startswith("2025-01-01T04:00"))
        self.assertEqual(grid["aggregation"], "per_station_then_summed")


if __name__ == "__main__":
    unittest.main()
