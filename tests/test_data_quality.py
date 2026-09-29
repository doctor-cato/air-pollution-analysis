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
import numpy as np
import pandas as pd

from src.data_quality import (
    audit_dataframe,
    audit_uniqueness,
    audit_missing_representations,
    audit_prolonged_zeros,
    audit_six_dimensions,
    analyze_missingness_patterns,
    ATMOSPHERIC_BOUNDS,
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
        # Tạo chuỗi zero 7 giờ liên tiếp
        df_zero = self.df_sample.copy()
        df_zero["pm25"] = [10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 60.0]

        zeros_audit = audit_prolonged_zeros(df_zero, target_cols=["pm25"], threshold_hours=6)
        pm25_zero_res = zeros_audit["pm25"]

        self.assertEqual(pm25_zero_res["zero_count"], 7)
        self.assertEqual(pm25_zero_res["longest_zero_streak_hours"], 7)
        self.assertEqual(pm25_zero_res["prolonged_zero_streaks_count"], 1)
        self.assertEqual(len(pm25_zero_res["prolonged_streaks_details"]), 1)
        self.assertEqual(pm25_zero_res["prolonged_streaks_details"][0]["streak_length_hours"], 7)

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

    def test_10_missingness_by_station_and_time(self):
        """10. Kiểm thử phân tích hình thái khuyết thiếu theo trạm và thời gian."""
        # Phân tích diurnal và missing blocks
        patterns = analyze_missingness_patterns(self.df_sample, target_col="pm25")

        self.assertEqual(patterns["target_variable"], "pm25")
        self.assertEqual(patterns["missing_count"], 2)
        self.assertEqual(patterns["missing_pct"], 20.0)
        self.assertIn("rubin_diagnosis", patterns)
        self.assertIn("uncertainty_declaration", patterns["rubin_diagnosis"])

        # Kiểm tra missing theo station
        by_station = self.df_sample.groupby("station_id")["pm25"].agg(
            total="count", missing=lambda x: x.isna().sum()
        )
        self.assertEqual(by_station.loc["STATION_A", "missing"], 1)
        self.assertEqual(by_station.loc["STATION_B", "missing"], 1)


if __name__ == "__main__":
    unittest.main()
