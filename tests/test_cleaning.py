"""
Unit Test Suite for Deterministic Cleaning Framework (Issue #6)
===============================================================
Kiểm thử tự động các tiêu chí nghiệm thu bắt buộc của Issue #6:

1.  Chuẩn hóa mốc thời gian về Asia/Ho_Chi_Minh (UTC+7), fail loudly khi hỏng.
2.  Sắp xếp tăng dần và khử trùng lặp tại đúng khóa quan sát.
3.  Chuyển missing ngụy trang thành NaN, giữ nguyên giá trị 0.0 hợp lệ.
4.  Lọc giá trị âm phi lý và dải hợp lệ khí tượng.
5.  Ràng buộc khí động học PM2.5 <= PM10 + epsilon.
6.  Reindex lưới 1 giờ liên tục, độc lập theo từng trạm, giữ khoảng trống là NaN.
7.  Nhận diện kẹt cảm biến (> 6 giờ không đổi) và gắn cờ `pm25_was_missing`.
8.  Gắn cờ sương mù độ ẩm cao `is_high_humidity_fog` mà không xóa bản ghi.
9.  Kiểm chứng tiêu chí nghiệm thu sau làm sạch.
10. Tính tất định (idempotent), không điền khuyết, bảo toàn giá trị cực trị,
    và tính tất định của Cleaning Log.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.cleaning import (
    CANONICAL_TIMEZONE,
    HIGH_HUMIDITY_FLAG,
    HIGH_HUMIDITY_FOG_THRESHOLD_PCT,
    PM25_MISSING_FLAG,
    PM_AERODYNAMIC_EPSILON_UG_M3,
    PROLONGED_MISSING_THRESHOLD_HOURS,
    STUCK_VALUE_THRESHOLD_HOURS,
    assert_no_imputation,
    attach_high_humidity_flag,
    clean_air_quality,
    clean_weather,
    drop_duplicate_observations,
    enforce_air_quality_physical_rules,
    enforce_pm_subset_constraint,
    enforce_weather_physical_rules,
    flag_prolonged_missing,
    flag_stuck_values,
    normalize_disguised_missing,
    normalize_timestamps,
    reindex_hourly_grid,
    reindex_station_series,
    render_cleaning_log,
    run_deterministic_cleaning,
    sort_chronologically,
    validate_cleaned_dataset,
)

HOURS_10 = pd.date_range("2025-01-01 00:00:00", periods=10, freq="h", tz=CANONICAL_TIMEZONE)


def make_air_frame(pm25, pm10=None, station="STATION_A", start="2025-01-01 00:00:00"):
    """Dựng DataFrame ô nhiễm không khí tối giản theo đúng Canonical Schema."""
    return pd.DataFrame({
        "timestamp": pd.date_range(start, periods=len(pm25), freq="h", tz=CANONICAL_TIMEZONE),
        "station_id": station,
        "location": "Hanoi",
        "pm25": pm25,
        "pm10": pm10 if pm10 is not None else np.full(len(pm25), np.nan),
    })


def make_weather_frame(humidity, start="2025-01-01 00:00:00"):
    """Dựng DataFrame khí tượng tối giản theo đúng Canonical Schema."""
    n = len(humidity)
    return pd.DataFrame({
        "timestamp": pd.date_range(start, periods=n, freq="h", tz=CANONICAL_TIMEZONE),
        "temperature": [25.0] * n,
        "relative_humidity": humidity,
        "wind_speed": [3.0] * n,
        "wind_direction": [180.0] * n,
        "precipitation": [0.0] * n,
        "surface_pressure": [1008.0] * n,
    })


def make_hourly_station_frame(hours, pm25, station="STATION_A", start="2025-01-01 00:00:00"):
    """
    Dựng DataFrame ô nhiễm không khí chỉ quan sát tại các giờ chỉ định trong `hours`
    (giờ tính từ `start`), nhờ vậy có thể tạo khoảng trống thời gian thật sự.
    """
    full = pd.date_range(start, periods=max(hours) + 1, freq="h", tz=CANONICAL_TIMEZONE)
    return pd.DataFrame({
        "timestamp": list(full[np.asarray(hours)]),
        "station_id": station,
        "location": "Hanoi",
        "pm25": list(pm25),
        "pm10": [np.nan] * len(hours),
    })


class TestNormalizeTimestamps(unittest.TestCase):
    """AC1 — chuẩn hóa mốc thời gian về múi giờ địa phương."""

    def test_naive_timestamps_are_localized(self):
        df = pd.DataFrame({"timestamp": ["2025-01-01 00:00", "2025-01-01 01:00"], "pm25": [1.0, 2.0]})
        out, stats = normalize_timestamps(df)
        self.assertEqual(str(out["timestamp"].dt.tz), CANONICAL_TIMEZONE)
        self.assertEqual(stats["rows_localized"], 2)
        self.assertEqual(stats["timezone_before"], "None (naive)")
        # Localize giữ nguyên mốc giờ địa phương (không dịch chuyển thời gian).
        self.assertEqual(out["timestamp"].iloc[0].hour, 0)

    def test_utc_timestamps_are_converted_not_shifted(self):
        df = pd.DataFrame({"timestamp": pd.to_datetime(["2025-01-01 17:00"], utc=True)})
        out, stats = normalize_timestamps(df)
        self.assertEqual(str(out["timestamp"].dt.tz), CANONICAL_TIMEZONE)
        # 17:00 UTC = 00:00 ngày 02/01 theo UTC+7 — mốc thời gian tuyệt đối không đổi.
        self.assertEqual(out["timestamp"].iloc[0].hour, 0)
        self.assertEqual(out["timestamp"].iloc[0].day, 2)
        self.assertEqual(out["timestamp"].iloc[0], pd.Timestamp("2025-01-01 17:00", tz="UTC"))
        self.assertEqual(stats["rows_localized"], 0)
        self.assertEqual(stats["rows_converted_from_other_timezone"], 1)

    def test_already_canonical_timestamps_are_noop(self):
        df = pd.DataFrame({"timestamp": HOURS_10})
        out, stats = normalize_timestamps(df)
        self.assertTrue(out["timestamp"].equals(df["timestamp"]))
        self.assertEqual(stats["rows_localized"], 0)
        self.assertEqual(stats["rows_converted_from_other_timezone"], 0)

    def test_unparseable_timestamp_raises_loudly(self):
        df = pd.DataFrame({"timestamp": ["2025-01-01 00:00", "KHONG_PHAI_THOI_GIAN"], "pm25": [1.0, 2.0]})
        with self.assertRaises(ValueError):
            normalize_timestamps(df)

    def test_missing_timestamp_column_raises(self):
        with self.assertRaises(ValueError):
            normalize_timestamps(pd.DataFrame({"pm25": [1.0]}))


class TestSortAndDeduplicate(unittest.TestCase):
    """AC1 — sắp xếp tăng dần và khử trùng lặp tại đúng khóa quan sát."""

    def test_sort_is_chronological_and_index_is_reset(self):
        df = make_air_frame([1.0] * 5, start="2025-01-01 05:00")
        shuffled = pd.concat([df.iloc[3:], df.iloc[:3]])
        out, stats = sort_chronologically(shuffled)
        self.assertTrue(out["timestamp"].is_monotonic_increasing)
        self.assertEqual(list(out.index), [0, 1, 2, 3, 4])
        self.assertEqual(stats["sort_keys"], ["station_id", "timestamp"])
        self.assertEqual(stats["rows_reordered"], 1)

    def test_sort_is_stable_for_equal_keys(self):
        df = make_air_frame([5.0, 1.0, 3.0])
        out, _ = sort_chronologically(df)
        # Ba hàng cùng khóa quan sát giữ nguyên thứ tự gốc nhờ mergesort ổn định.
        self.assertEqual(list(out["pm25"]), [5.0, 1.0, 3.0])

    def test_duplicates_removed_on_station_and_timestamp(self):
        df = make_air_frame([10.0, 20.0, 30.0])
        duplicated = pd.concat([df, df.iloc[[1]]], ignore_index=True)
        out, stats = drop_duplicate_observations(duplicated)
        self.assertEqual(stats["observation_key"], ["station_id", "timestamp"])
        self.assertEqual(stats["duplicate_rows_removed"], 1)
        self.assertEqual(len(out), 3)
        self.assertEqual(int(out["timestamp"].duplicated().sum()), 0)

    def test_weather_deduplicates_on_timestamp_only(self):
        df = make_weather_frame([50.0] * 4)
        duplicated = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        out, stats = drop_duplicate_observations(duplicated)
        self.assertEqual(stats["observation_key"], ["timestamp"])
        self.assertEqual(stats["duplicate_rows_removed"], 1)
        self.assertEqual(len(out), 4)

    def test_dedup_keeps_first_deterministically(self):
        df = pd.DataFrame({
            "timestamp": HOURS_10[:2],
            "station_id": ["STATION_A", "STATION_A"],
            "location": ["Hanoi", "Hanoi"],
            "pm25": [11.0, 99.0],
            "pm10": [np.nan, np.nan],
        })
        out, _ = drop_duplicate_observations(df)
        self.assertEqual(out["pm25"].iloc[0], 11.0)


class TestDisguisedMissing(unittest.TestCase):
    """AC — missing ngụy trang (-999/-9999, chuỗi lỗi) phải thành NaN."""

    def test_numeric_sentinel_codes_become_nan(self):
        df = make_air_frame([-999.0, -9999.0, 12.5])
        out, stats = normalize_disguised_missing(df, ["pm25"])
        self.assertTrue(pd.isna(out["pm25"].iloc[0]))
        self.assertTrue(pd.isna(out["pm25"].iloc[1]))
        self.assertEqual(out["pm25"].iloc[2], 12.5)
        self.assertEqual(stats["by_column"]["pm25"]["rows_converted_to_nan"], 2)

    def test_string_markers_become_nan(self):
        df = pd.DataFrame({
            "timestamp": HOURS_10[:4],
            "station_id": ["STATION_A"] * 4,
            "location": ["Hanoi"] * 4,
            "pm25": ["N/A", "None", "  ", 20.0],
            "pm10": [np.nan] * 4,
        })
        out, stats = normalize_disguised_missing(df, ["pm25"])
        self.assertEqual(int(out["pm25"].isna().sum()), 3)
        self.assertEqual(out["pm25"].iloc[3], 20.0)
        self.assertEqual(stats["total_cells_converted"], 3)

    def test_valid_zero_is_never_treated_as_missing(self):
        df = make_air_frame([0.0, 5.0])
        out, _ = normalize_disguised_missing(df, ["pm25"])
        self.assertEqual(out["pm25"].iloc[0], 0.0)
        self.assertEqual(int(out["pm25"].isna().sum()), 0)

    def test_column_dtype_becomes_float64_after_coercion(self):
        df = pd.DataFrame({"timestamp": HOURS_10[:2], "pm25": ["1.5", "null"]})
        out, _ = normalize_disguised_missing(df, ["pm25"])
        self.assertEqual(str(out["pm25"].dtype), "float64")


class TestPhysicalRules(unittest.TestCase):
    """AC — không còn giá trị âm phi lý; dải hợp lệ khí tượng được kiểm tra."""

    def test_negative_pm_becomes_nan_and_zero_is_kept(self):
        df = make_air_frame([-5.0, 0.0, 42.0])
        out, stats = enforce_air_quality_physical_rules(df)
        self.assertTrue(pd.isna(out["pm25"].iloc[0]))
        self.assertEqual(out["pm25"].iloc[1], 0.0)
        self.assertEqual(out["pm25"].iloc[2], 42.0)
        self.assertEqual(stats["by_column"]["pm25"]["negative_values_nullified"], 1)
        self.assertEqual(stats["by_column"]["pm25"]["valid_zero_preserved"], 1)
        self.assertEqual(int((out["pm25"] < 0).sum()), 0)

    def test_sentinel_pm_becomes_nan(self):
        df = make_air_frame([-999.0, 30.0])
        out, _ = enforce_air_quality_physical_rules(df)
        self.assertTrue(pd.isna(out["pm25"].iloc[0]))

    def test_extreme_real_pollution_episode_is_preserved(self):
        """Đợt ô nhiễm bùng phát là hiện tượng thực tế — không được cắt bỏ."""
        df = make_air_frame([850.0, 252.64])
        out, _ = enforce_air_quality_physical_rules(df)
        self.assertEqual(out["pm25"].iloc[0], 850.0)
        self.assertEqual(out["pm25"].iloc[1], 252.64)
        self.assertEqual(int(out["pm25"].isna().sum()), 0)

    def test_weather_bounds_and_range_rules(self):
        df = make_weather_frame([50.0] * 6)
        df.loc[0, "relative_humidity"] = 101.0   # vượt giới hạn khí quyển
        df.loc[1, "wind_speed"] = -2.0          # tốc độ gió âm là bất khả thi
        df.loc[2, "precipitation"] = -1.0       # lượng mưa âm là bất khả thi
        df.loc[3, "temperature"] = 55.0         # ngoài dải [0, 50]°C
        df.loc[4, "surface_pressure"] = 1200.0  # ngoài dải [950, 1050] hPa
        out, stats = enforce_weather_physical_rules(df)
        self.assertEqual(stats["total_out_of_range"], 5)
        for column in ("relative_humidity", "wind_speed", "precipitation",
                       "temperature", "surface_pressure"):
            self.assertTrue(pd.isna(out[column].iloc[
                {"relative_humidity": 0, "wind_speed": 1, "precipitation": 2,
                 "temperature": 3, "surface_pressure": 4}[column]
            ]), f"{column} phải được chuyển thành NaN")

    def test_wind_direction_is_normalized_modulo_360(self):
        df = make_weather_frame([50.0] * 3)
        df.loc[0, "wind_direction"] = 370.0
        df.loc[1, "wind_direction"] = -10.0
        out, _ = enforce_weather_physical_rules(df)
        self.assertEqual(out["wind_direction"].iloc[0], 10.0)
        self.assertTrue(pd.isna(out["wind_direction"].iloc[1]))

    def test_valid_weather_extremes_are_preserved(self):
        df = make_weather_frame([100.0, 0.0])
        df.loc[0, "wind_direction"] = 360.0
        df.loc[1, "relative_humidity"] = 0.0
        out, _ = enforce_weather_physical_rules(df)
        self.assertEqual(out["relative_humidity"].iloc[0], 100.0)
        self.assertEqual(out["relative_humidity"].iloc[1], 0.0)
        self.assertEqual(out["wind_direction"].iloc[0], 360.0)


class TestPmSubsetConstraint(unittest.TestCase):
    """AC — ràng buộc khí động học PM2.5 <= PM10 + epsilon được thực thi."""

    def test_strict_inversion_nullifies_both_channels(self):
        df = make_air_frame([30.0, 10.0], pm10=[20.0, 40.0])
        out, stats = enforce_pm_subset_constraint(df)
        self.assertTrue(pd.isna(out["pm25"].iloc[0]))
        self.assertTrue(pd.isna(out["pm10"].iloc[0]))
        self.assertEqual(stats["strict_inversions"], 1)
        self.assertEqual(stats["rows_nullified"], 1)

    def test_inversion_within_epsilon_is_nullified_for_issue6_acceptance(self):
        """Nghiệm thu Issue #6 đòi (pm25 > pm10 + 1e-3).sum() == 0 → nghịch đảo nhẹ cũng bị xử lý."""
        df = make_air_frame([21.5], pm10=[20.0])
        out, stats = enforce_pm_subset_constraint(df)
        self.assertTrue(pd.isna(out["pm25"].iloc[0]))
        self.assertEqual(stats["inversions_within_measurement_tolerance"], 1)
        self.assertEqual(stats["inversions_beyond_epsilon"], 0)

    def test_valid_pair_is_preserved(self):
        df = make_air_frame([5.0, 40.0], pm10=[50.0, 40.0])
        out, stats = enforce_pm_subset_constraint(df)
        self.assertEqual(out["pm25"].tolist(), [5.0, 40.0])
        self.assertEqual(stats["rows_nullified"], 0)

    def test_epsilon_splits_evidence_tiers(self):
        """ε là mốc phân loại bằng chứng: nghịch đảo vượt ε và trong ε được đếm riêng."""
        df = make_air_frame([30.0, 21.0], pm10=[20.0, 20.0])
        _, stats = enforce_pm_subset_constraint(df)
        self.assertEqual(stats["inversions_beyond_epsilon"], 1)   # 30 > 20 + 2
        self.assertEqual(stats["inversions_within_measurement_tolerance"], 1)  # 21 ≤ 22
        self.assertEqual(stats["rows_nullified"], 2)

    def test_missing_pm10_column_skips_with_reason(self):
        df = make_air_frame([5.0, 6.0]).drop(columns=["pm10"])
        out, stats = enforce_pm_subset_constraint(df)
        self.assertTrue(stats["skipped"])
        self.assertEqual(out["pm25"].tolist(), [5.0, 6.0])

    def test_valid_pairs_and_single_channel_rows_are_untouched(self):
        df = make_air_frame([5.0, np.nan, 7.0], pm10=[50.0, 60.0, np.nan])
        out, stats = enforce_pm_subset_constraint(df)
        self.assertEqual(out["pm25"].iloc[0], 5.0)
        self.assertTrue(pd.isna(out["pm25"].iloc[1]))  # chỉ có pm10 — không suy diễn pm25
        self.assertEqual(out["pm10"].iloc[1], 60.0)
        self.assertEqual(stats["pairs_evaluated"], 1)
        self.assertEqual(stats["rows_nullified"], 0)

    def test_epsilon_is_the_documented_measurement_uncertainty(self):
        self.assertEqual(PM_AERODYNAMIC_EPSILON_UG_M3, 2.0)


class TestReindexHourlyGrid(unittest.TestCase):
    """AC — reindex lưới 1 giờ liên tục, độc lập theo từng trạm."""

    def test_gap_is_filled_with_nan_rows(self):
        df = make_hourly_station_frame([0, 1, 4], [1.0, 2.0, 3.0])
        out, stats = reindex_hourly_grid(df)
        self.assertEqual(len(out), 5)  # lưới 0h → 4h, quan sát tại 0h, 1h, 4h
        self.assertEqual(stats["rows_inserted"], 2)
        self.assertEqual(int(out["pm25"].isna().sum()), 2)
        self.assertEqual(out["station_id"].unique().tolist(), ["STATION_A"])
        self.assertEqual(out["location"].unique().tolist(), ["Hanoi"])

    def test_reindexed_grid_is_continuous_hourly(self):
        df = make_hourly_station_frame([0, 1, 5, 6], [1.0, 2.0, 3.0, 4.0])
        out, _ = reindex_hourly_grid(df)
        diffs = out["timestamp"].diff().dropna()
        self.assertTrue((diffs == np.timedelta64(1, "h")).all())

    def test_gap_is_not_imputed(self):
        """Reindex chỉ bộc lộ khoảng trống — tuyệt đối không nội suy."""
        df = make_hourly_station_frame([0, 1, 4], [10.0, 20.0, 90.0])
        out, _ = reindex_hourly_grid(df)
        self.assertTrue(pd.isna(out["pm25"].iloc[2]))
        self.assertTrue(pd.isna(out["pm25"].iloc[3]))
        self.assertEqual(int(out["pm25"].isna().sum()), 2)
        self.assertEqual(out["pm25"].iloc[4], 90.0)

    def test_multi_station_reindex_is_independent_per_station(self):
        a = make_hourly_station_frame([0, 1, 2], [1.0, 2.0, 3.0], station="STATION_A")
        b = make_hourly_station_frame([2, 3], [11.0, 12.0], station="STATION_B")
        out, stats = reindex_hourly_grid(pd.concat([a, b], ignore_index=True))

        self.assertEqual(set(stats["stations"]), {"STATION_A", "STATION_B"})
        # Cửa sổ lưới chung 0h → 3h: mỗi trạm 4 hàng, không trạm nào mất hàng.
        self.assertEqual(len(out), 8)
        expected = {
            "STATION_A": [1.0, 2.0, 3.0, np.nan],
            "STATION_B": [np.nan, np.nan, 11.0, 12.0],
        }
        for station, values in expected.items():
            rows = out[out["station_id"] == station]["pm25"].tolist()
            self.assertEqual(len(rows), 4, f"{station} phải nằm trên cùng lưới 4 giờ")
            for got, want in zip(rows, values):
                if np.isnan(want):
                    self.assertTrue(pd.isna(got))
                else:
                    self.assertEqual(got, want)

    def test_single_global_index_is_never_forced_on_multiple_stations(self):
        """Hai trạm có dải quan sát rất khác nhau vẫn phải giữ trọn quan sát hợp lệ."""
        a = make_hourly_station_frame([0, 1], [1.0, 2.0], station="STATION_A")
        b = make_hourly_station_frame([0], [21.0], station="STATION_B",
                                      start="2025-01-05 00:00:00")
        out, stats = reindex_hourly_grid(pd.concat([a, b], ignore_index=True))

        station_b = out[out["station_id"] == "STATION_B"]
        station_a = out[out["station_id"] == "STATION_A"]
        # Quan sát duy nhất của trạm B được giữ nguyên tại đúng mốc thời gian.
        observed_at = station_b.loc[station_b["pm25"].notna(), "timestamp"].iloc[0]
        self.assertEqual(observed_at, pd.Timestamp("2025-01-05 00:00:00", tz=CANONICAL_TIMEZONE))
        self.assertEqual(station_b["pm25"].dropna().tolist(), [21.0])
        # Cả hai trạm nằm trên cùng một lưới giờ liên tục.
        for frame in (station_a, station_b):
            diffs = frame["timestamp"].diff().dropna()
            self.assertTrue((diffs == np.timedelta64(1, "h")).all())
        expected_hours = int(
            (out["timestamp"].max() - out["timestamp"].min()) / np.timedelta64(1, "h")
        ) + 1
        self.assertEqual(out["timestamp"].nunique(), expected_hours)

    def test_explicit_window_is_respected(self):
        df = make_air_frame([1.0, 2.0])
        window = (df["timestamp"].min(), df["timestamp"].min() + pd.Timedelta(5, "h"))
        out, stats = reindex_hourly_grid(df, window=window)
        self.assertEqual(len(out), 6)
        self.assertEqual(stats["window_end"], str(window[1]))

    def test_reindex_station_series_matches_issue_snippet_contract(self):
        df = make_hourly_station_frame([0, 2], [1.0, 3.0])
        result = reindex_station_series(df, df["timestamp"].min(), df["timestamp"].max())
        self.assertEqual(list(result.columns)[0], "timestamp")
        self.assertEqual(len(result), 3)
        self.assertTrue(pd.isna(result["pm25"].iloc[1]))
        self.assertEqual(result["station_id"].tolist(), ["STATION_A"] * 3)

    def test_conflicting_station_level_attribute_raises(self):
        df = make_air_frame([1.0, 2.0])
        df.loc[0, "location"] = "Khac"
        with self.assertRaises(ValueError):
            reindex_station_series(df, df["timestamp"].min(), df["timestamp"].max())

    def test_empty_frame_is_handled(self):
        empty = make_air_frame([])
        out, stats = reindex_hourly_grid(empty)
        self.assertEqual(len(out), 0)
        self.assertEqual(stats["rows_after"], 0)


class TestStuckSensorDetection(unittest.TestCase):
    """AC — lỗi kẹt cảm biến được gắn nhãn theo đúng quy chuẩn kỹ thuật."""

    def test_constant_run_longer_than_six_hours_is_nullified(self):
        df = make_air_frame([42.0] * 9 + [43.0])
        out, stats = flag_stuck_values(df)
        self.assertEqual(stats["by_column"]["pm25"]["rows_nullified"], 9)
        self.assertTrue(out["pm25"].iloc[:9].isna().all())
        self.assertEqual(out["pm25"].iloc[9], 43.0)

    def test_run_of_exactly_six_hours_is_preserved(self):
        """6 quan sát giống hệt chưa vượt ngưỡng > 6 quan sát của Issue #6."""
        df = make_air_frame([42.0] * 6 + [43.0])
        out, stats = flag_stuck_values(df)
        self.assertEqual(stats["by_column"]["pm25"]["rows_nullified"], 0)
        self.assertEqual(int(out["pm25"].isna().sum()), 0)

    def test_seven_equal_readings_exceed_the_six_observation_threshold(self):
        """Ngưỡng đếm bằng số quan sát (nhất quán với Issue #5): > 6 quan sát → loại."""
        df = make_air_frame([42.0] * 7 + [43.0])
        out, stats = flag_stuck_values(df)
        self.assertEqual(stats["by_column"]["pm25"]["rows_nullified"], 7)
        self.assertEqual(stats["by_column"]["pm25"]["nullified_runs"], 1)
        self.assertEqual(out["pm25"].iloc[7], 43.0)

    def test_eight_equal_readings_are_also_flagged(self):
        df = make_air_frame([42.0] * 8 + [43.0])
        out, stats = flag_stuck_values(df)
        self.assertEqual(stats["by_column"]["pm25"]["rows_nullified"], 8)

    def test_temporal_gap_breaks_the_stuck_run(self):
        # 4 quan sát giống hệt nhưng bị ngắt bởi khoảng trống 3 giờ → không kẹt cảm biến.
        df = make_hourly_station_frame([0, 1, 4, 5], [42.0] * 4)
        out, stats = flag_stuck_values(df)
        self.assertEqual(stats["by_column"]["pm25"]["rows_nullified"], 0)
        self.assertEqual(int(out["pm25"].isna().sum()), 0)

    def test_runs_are_never_joined_across_stations(self):
        a = make_air_frame([42.0] * 4, station="STATION_A", start="2025-01-01 00:00")
        b = make_air_frame([42.0] * 4, station="STATION_B", start="2025-01-01 04:00")
        out, stats = flag_stuck_values(pd.concat([a, b], ignore_index=True))
        self.assertEqual(stats["by_column"]["pm25"]["rows_nullified"], 0)

    def test_missing_runs_are_not_mistaken_for_stuck_values(self):
        df = make_air_frame([np.nan] * 12)
        out, stats = flag_stuck_values(df)
        self.assertEqual(stats["by_column"]["pm25"]["rows_nullified"], 0)
        self.assertEqual(int(out["pm25"].isna().sum()), 12)
        self.assertEqual(stats["by_column"]["pm25"]["missing_runs_excluded"], 1)

    def test_threshold_is_six_hours(self):
        self.assertEqual(STUCK_VALUE_THRESHOLD_HOURS, 6)


class TestProlongedMissingFlag(unittest.TestCase):
    """AC — đánh dấu khoảng khuyết lớn (> 6 giờ) bằng cờ `pm25_was_missing`."""

    def test_flag_set_for_blocks_longer_than_six_hours(self):
        df = make_air_frame([1.0] + [np.nan] * 8 + [2.0])
        out, stats = flag_prolonged_missing(df, column="pm25")
        self.assertEqual(stats["prolonged_blocks"], 1)
        self.assertEqual(stats["rows_flagged"], 8)
        self.assertTrue((out[PM25_MISSING_FLAG] == 1).sum() == 8)
        self.assertEqual(out[PM25_MISSING_FLAG].iloc[0], 0)
        self.assertEqual(out[PM25_MISSING_FLAG].iloc[-1], 0)

    def test_short_blocks_are_not_flagged(self):
        df = make_air_frame([1.0] + [np.nan] * 3 + [2.0])
        out, stats = flag_prolonged_missing(df, column="pm25")
        self.assertEqual(stats["prolonged_blocks"], 0)
        self.assertEqual(stats["rows_flagged"], 0)
        self.assertEqual(int(out[PM25_MISSING_FLAG].sum()), 0)

    def test_multiple_blocks_are_counted_separately(self):
        pm25 = [1.0] + [np.nan] * 8 + [2.0] + [3.0] + [np.nan] * 8 + [4.0]
        out, stats = flag_prolonged_missing(make_air_frame(pm25), column="pm25")
        self.assertEqual(stats["prolonged_blocks"], 2)
        self.assertEqual(stats["rows_flagged"], 16)

    def test_flag_does_not_impute(self):
        df = make_air_frame([1.0] + [np.nan] * 8)
        out, _ = flag_prolonged_missing(df, column="pm25")
        self.assertEqual(int(out["pm25"].isna().sum()), 8)

    def test_missing_source_column_yields_zero_flag(self):
        df = make_air_frame([1.0, 2.0]).drop(columns=["pm25"])
        out, stats = flag_prolonged_missing(df, column="pm25")
        self.assertTrue(stats["skipped"])
        self.assertEqual(int(out[PM25_MISSING_FLAG].sum()), 0)

    def test_threshold_is_six_hours(self):
        self.assertEqual(PROLONGED_MISSING_THRESHOLD_HOURS, 6)


class TestHighHumidityFlag(unittest.TestCase):
    """AC — cờ cảnh báo độ ẩm cao `is_high_humidity_fog` không xóa bản ghi."""

    def test_flag_set_when_humidity_above_ninety(self):
        air = make_air_frame([10.0] * 4)
        weather = make_weather_frame([91.0, 95.0, 90.0, 50.0])
        out, stats = attach_high_humidity_flag(air, weather)
        self.assertEqual(list(out[HIGH_HUMIDITY_FLAG]), [1, 1, 0, 0])
        self.assertEqual(stats["rows_flagged"], 2)
        self.assertEqual(stats["humidity_matched_rows"], 4)

    def test_no_row_is_deleted_for_high_humidity(self):
        air = make_air_frame([10.0] * 5)
        weather = make_weather_frame([99.0] * 5)
        out, _ = attach_high_humidity_flag(air, weather)
        self.assertEqual(len(out), 5)
        self.assertEqual(int(out["pm25"].isna().sum()), 0)

    def test_row_count_is_preserved_and_humidity_column_is_dropped(self):
        air = make_air_frame([10.0] * 6)
        weather = make_weather_frame([50.0] * 10)
        out, stats = attach_high_humidity_flag(air, weather)
        self.assertEqual(stats["rows_before_join"], stats["rows_after_join"])
        self.assertFalse(stats["row_explosion_detected"])
        self.assertNotIn("relative_humidity", out.columns)

    def test_rows_without_matching_humidity_are_flagged_zero(self):
        air = make_air_frame([10.0] * 2, start="2025-01-01 00:00")
        weather = make_weather_frame([95.0, 95.0], start="2025-02-01 00:00")
        out, stats = attach_high_humidity_flag(air, weather)
        self.assertEqual(stats["humidity_unavailable_rows"], 2)
        self.assertEqual(list(out[HIGH_HUMIDITY_FLAG]), [0, 0])

    def test_duplicate_weather_timestamps_raise_row_explosion_guard(self):
        air = make_air_frame([10.0] * 2)
        weather = make_weather_frame([50.0] * 2)
        weather = pd.concat([weather, weather.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            attach_high_humidity_flag(air, weather)

    def test_threshold_is_ninety_percent(self):
        self.assertEqual(HIGH_HUMIDITY_FOG_THRESHOLD_PCT, 90.0)


class TestValidationAndLeakageGuards(unittest.TestCase):
    """AC — không điền khuyết, tiêu chí nghiệm thu đều đạt."""

    def test_validation_passes_on_a_fully_cleaned_frame(self):
        df = make_air_frame([5.0, 6.0, 7.0], pm10=[50.0, 60.0, 70.0])
        df[PM25_MISSING_FLAG] = 0
        df[HIGH_HUMIDITY_FLAG] = 0
        result = validate_cleaned_dataset(df)
        self.assertTrue(result["all_passed"])
        self.assertTrue(result["pm_subset_constraint"]["passed"])
        self.assertEqual(result["pm_subset_constraint"]["violations_pm25_gt_pm10_plus_1e_3"], 0)

    def test_validation_detects_pm_inversion(self):
        df = make_air_frame([99.0], pm10=[10.0])
        df[PM25_MISSING_FLAG] = 0
        df[HIGH_HUMIDITY_FLAG] = 0
        result = validate_cleaned_dataset(df)
        self.assertFalse(result["all_passed"])
        self.assertFalse(result["pm_subset_constraint"]["passed"])

    def test_validation_detects_gap_in_hourly_grid(self):
        df = make_air_frame([5.0] * 5)
        df = df.drop(index=2).reset_index(drop=True)
        df[PM25_MISSING_FLAG] = 0
        df[HIGH_HUMIDITY_FLAG] = 0
        result = validate_cleaned_dataset(df)
        self.assertFalse(result["continuous_hourly_grid_per_station"]["passed"])

    def test_validation_detects_wrong_timezone(self):
        df = make_air_frame([5.0] * 3)
        df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
        df[PM25_MISSING_FLAG] = 0
        df[HIGH_HUMIDITY_FLAG] = 0
        result = validate_cleaned_dataset(df)
        self.assertFalse(result["timezone_is_canonical"]["passed"])

    def test_assert_no_imputation_detects_fabricated_observations(self):
        before = make_air_frame([1.0, np.nan, 3.0])
        after = make_air_frame([1.0, 2.0, 3.0])
        with self.assertRaises(AssertionError):
            assert_no_imputation(before, after, ["pm25"])

    def test_assert_no_imputation_allows_reindex_growth(self):
        before = make_air_frame([1.0, 3.0])
        after = make_air_frame([1.0, np.nan, np.nan, 3.0])
        assert_no_imputation(before, after, ["pm25"])


class TestPipelineEndToEnd(unittest.TestCase):
    """AC — pipeline hoàn chỉnh, tất định và kiểm chứng được."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cleaning_test_"))
        self.air_path = self.tmp / "air_quality_canonical.parquet"
        self.weather_path = self.tmp / "weather_canonical.parquet"

        # Giờ 0: nghịch đảo khí động học (30 > 20) · giờ 10: đợt ô nhiễm cực đoan
        # 900 µg/m³ với PM10 = 950 (hợp lệ, phải bảo toàn) · giờ 11: giá trị âm.
        # Giờ 11–12 vắng mặt → khoảng trống 2 giờ được reindex bộc lộ.
        pm25 = [30.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 900.0, -3.0]
        pm10 = [20.0, 32.0, 34.0, 36.0, 38.0, 40.0, 42.0, 44.0, 46.0, 48.0, 950.0, 25.0]
        hours = list(range(11)) + [13]  # bỏ giờ 11 và 12 → khoảng trống 2 giờ
        full = pd.date_range("2025-01-01 00:00:00", periods=14, freq="h", tz=CANONICAL_TIMEZONE)
        air = pd.DataFrame({
            "timestamp": list(full[hours]),
            "station_id": "STATION_A",
            "location": "Hanoi",
            "pm25": pm25,
            "pm10": pm10,
        })
        air.to_parquet(self.air_path, index=False)
        make_weather_frame([95.0, 55.0] * 7).to_parquet(self.weather_path, index=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pipeline_produces_artifacts_and_passes_validation(self):
        report = run_deterministic_cleaning(self.air_path, self.weather_path)

        self.assertTrue(self.air_path.exists())
        self.assertTrue(self.weather_path.exists())
        cleaned = pd.read_parquet(self.air_path)
        self.assertIn(PM25_MISSING_FLAG, cleaned.columns)
        self.assertIn(HIGH_HUMIDITY_FLAG, cleaned.columns)
        self.assertTrue(report["air_quality"]["validation"]["all_passed"])
        self.assertTrue(report["weather"]["validation"]["all_passed"])

    def test_pipeline_exposes_negative_values_and_inversions(self):
        report = run_deterministic_cleaning(self.air_path, self.weather_path)
        cleaned = pd.read_parquet(self.air_path)

        self.assertEqual(int((cleaned["pm25"] < 0).sum()), 0)
        pairs = cleaned.dropna(subset=["pm25", "pm10"])
        self.assertEqual(int((pairs["pm25"] > pairs["pm10"] + 1e-3).sum()), 0)
        pm_step = next(s for s in report["air_quality"]["steps"]
                       if s["name"] == "enforce_pm_subset_constraint")
        self.assertEqual(pm_step["stats"]["strict_inversions"], 1)

    def test_pipeline_is_idempotent_on_its_own_output(self):
        run_deterministic_cleaning(self.air_path, self.weather_path)
        first = pd.read_parquet(self.air_path)
        first_weather = pd.read_parquet(self.weather_path)

        second_report = run_deterministic_cleaning(self.air_path, self.weather_path)
        second = pd.read_parquet(self.air_path)

        pd.testing.assert_frame_equal(first, second)
        pd.testing.assert_frame_equal(first_weather, pd.read_parquet(self.weather_path))
        # Lần chạy lại phải tự nhận diện artifact đã làm sạch để không gây hiểu nhầm.
        self.assertEqual(second_report["air_quality"]["input_already_cleaned"],
                         [PM25_MISSING_FLAG, HIGH_HUMIDITY_FLAG])

    def test_pipeline_never_increases_observed_measurements(self):
        before = pd.read_parquet(self.air_path)
        before_pm25 = int(before["pm25"].notna().sum())
        run_deterministic_cleaning(self.air_path, self.weather_path)
        after = pd.read_parquet(self.air_path)
        self.assertLessEqual(int(after["pm25"].notna().sum()), before_pm25)
        self.assertGreaterEqual(int(after["pm25"].isna().sum()), int(before["pm25"].isna().sum()))

    def test_pipeline_preserves_extreme_pollution_episode(self):
        run_deterministic_cleaning(self.air_path, self.weather_path)
        cleaned = pd.read_parquet(self.air_path)
        self.assertEqual(cleaned["pm25"].max(), 900.0)

    def test_pipeline_reindexes_gap_but_keeps_every_original_row(self):
        run_deterministic_cleaning(self.air_path, self.weather_path)
        cleaned = pd.read_parquet(self.air_path)
        self.assertEqual(len(cleaned), 14)  # lưới đủ 0h → 13h, không quan sát nào bị xóa
        # Ba giờ mất quan sát: giờ 10 (nghịch đảo khí động học), giờ 11 (giá trị âm),
        # và giờ 11–12 là khoảng trống do trạm ngừng phát.
        self.assertEqual(int(cleaned["pm25"].isna().sum()), 4)
        self.assertEqual(int(cleaned[PM25_MISSING_FLAG].sum()), 0)  # khối trống chỉ 2 giờ < 6
        self.assertEqual(int(cleaned[HIGH_HUMIDITY_FLAG].sum()), 7)  # RH > 90% ở 7/14 giờ

    def test_save_false_leaves_input_untouched(self):
        before = pd.read_parquet(self.air_path)
        report = run_deterministic_cleaning(self.air_path, self.weather_path, save=False)
        pd.testing.assert_frame_equal(before, pd.read_parquet(self.air_path))
        self.assertIsNone(report["air_quality"]["output_path"])

    def test_missing_input_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            run_deterministic_cleaning(self.tmp / "khong_ton_tai.parquet", self.weather_path)

    def test_report_steps_are_ordered_and_documented(self):
        report = run_deterministic_cleaning(self.air_path, self.weather_path, save=False)
        names = [s["name"] for s in report["air_quality"]["steps"]]
        self.assertEqual(names, [
            "normalize_timestamps",
            "sort_chronologically",
            "drop_duplicate_observations",
            "normalize_disguised_missing",
            "enforce_air_quality_physical_rules",
            "enforce_pm_subset_constraint",
            "reindex_hourly_grid",
            "flag_stuck_values",
            "flag_prolonged_missing",
            "attach_high_humidity_flag",
        ])
        for index, step in enumerate(report["air_quality"]["steps"], start=1):
            self.assertEqual(step["step"], index)
            self.assertTrue(step["title"])
            self.assertTrue(step["rationale"])

    def test_weather_pipeline_does_not_apply_stuck_sensor_rule(self):
        report = run_deterministic_cleaning(self.air_path, self.weather_path, save=False)
        names = [s["name"] for s in report["weather"]["steps"]]
        self.assertNotIn("flag_stuck_values", names)
        self.assertIn("reindex_hourly_grid", names)


class TestCleaningLogRendering(unittest.TestCase):
    """AC — mọi thay đổi được ghi nhận minh bạch trong docs/cleaning_log.md."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cleaning_log_test_"))
        # Có khoảng trống 2 giờ (giờ 1, 2) và một nghịch đảo khí động học tại giờ 0
        # để mọi nhóm nguyên nhân tạo NaN đều xuất hiện trong Cleaning Log.
        air = make_hourly_station_frame([0, 3, 4], [40.0, 10.0, 20.0], station="STATION_A")
        air["pm10"] = [20.0, 50.0, 60.0]
        air.to_parquet(self.tmp / "air_quality_canonical.parquet", index=False)
        make_weather_frame([95.0, 55.0, 95.0, 60.0]).to_parquet(
            self.tmp / "weather_canonical.parquet", index=False
        )
        self.report = run_deterministic_cleaning(
            self.tmp / "air_quality_canonical.parquet",
            self.tmp / "weather_canonical.parquet",
            save=False,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_log_contains_all_mandatory_sections(self):
        log = render_cleaning_log(self.report)
        for heading in (
            "# Nhật Ký Làm Sạch Dữ Liệu (Cleaning Log)",
            "## 1. Ranh Giới Phân Định",
            "## 2. Ngưỡng & Hằng Số Quy ước",
            "## 3. Tập Dữ Liệu Ô Nhiễm Không Khí",
            "## 4. Tập Dữ Liệu Khí Tượng Bề Mặt",
            "## 5. Kiểm Chứng Tiêu Chí Nghiệm Thu",
            "## 6. Cột Cờ Chẩn Đoán Được Sinh Ra",
            "## 7. Bảo Toàn Giá Trị Cực Trị Thực Tế",
            "## 8. Bàn Giao Cho Issue #7",
        ):
            self.assertIn(heading, log)

    def test_log_records_every_step_with_row_counts(self):
        log = render_cleaning_log(self.report)
        for step in self.report["air_quality"]["steps"]:
            self.assertIn(step["title"], log)
        self.assertIn("duplicate_rows_removed", log)
        self.assertIn("rows_inserted", log)
        self.assertIn("rows_nullified", log)

    def test_log_is_deterministic_and_carries_no_wall_clock_timestamp(self):
        first = render_cleaning_log(self.report)
        second = render_cleaning_log(self.report)
        self.assertEqual(first, second)
        self.assertNotIn("Generated at", first)
        self.assertNotIn("executed_at", first)

    def test_log_warns_when_input_was_already_cleaned(self):
        report = run_deterministic_cleaning(
            self.tmp / "air_quality_canonical.parquet",
            self.tmp / "weather_canonical.parquet",
            save=True,
        )
        second_pass = run_deterministic_cleaning(
            self.tmp / "air_quality_canonical.parquet",
            self.tmp / "weather_canonical.parquet",
            save=False,
        )
        self.assertTrue(second_pass["air_quality"]["input_already_cleaned"])
        log = render_cleaning_log(second_pass)
        self.assertIn("Artifact đầu vào đã được làm sạch từ trước", log)
        self.assertEqual(report["air_quality"]["validation"]["all_passed"], True)

    def test_log_documents_the_exact_acceptance_assertions(self):
        log = render_cleaning_log(self.report)
        self.assertIn("assert (df['pm25'] < 0).sum() == 0", log)
        self.assertIn("pairs['pm25'] > pairs['pm10'] + 1e-3", log)
        self.assertIn("Asia/Ho_Chi_Minh", log)

    def test_log_proves_extreme_values_were_not_dropped(self):
        """§7.1 phải chứng minh bằng số liệu rằng không mất giá trị vô căn cứ."""
        log = render_cleaning_log(self.report)
        self.assertIn("Bằng Chứng Định Lượng", log)
        self.assertIn("Không đặt trần nồng độ hạt bụi", log)
        # Đỉnh PM2.5 của dữ liệu mẫu là 40.0 µg/m³ và phải được nêu đích danh.
        peak = self.report["air_quality"]["input"]["pm25_peak"]
        # Giá trị float nguyên được hiển thị không dấu thập phân (40.0 -> "40").
        rendered_peak = str(int(peak)) if float(peak).is_integer() else str(peak)
        self.assertIn(f"đỉnh PM2.5 lớn nhất trước làm sạch là {rendered_peak} µg/m³", log)

    def test_log_reports_peak_from_the_actual_input_not_a_constant(self):
        peak = self.report["air_quality"]["input"]["pm25_peak"]
        self.assertEqual(peak, 40.0)
        self.assertIn("40 µg/m³", render_cleaning_log(self.report))

    def test_log_shows_peak_before_and_after_cleaning(self):
        """§3.1 đối chiếu đỉnh PM2.5 trước và sau bằng số liệu, không chỉ nêu điều kiện."""
        air = self.report["air_quality"]
        log = render_cleaning_log(self.report)
        self.assertIn("Đỉnh PM2.5 (µg/m³)", log)
        # Float nguyên hiển thị không dấu thập phân (40.0 -> "40"), giống `_fmt`.
        for key in ("input", "output"):
            peak = float(air[key]["pm25_peak"])
            rendered = str(int(peak)) if peak.is_integer() else str(peak)
            self.assertIn(rendered, log)

    def test_peak_note_states_a_verified_outcome_not_a_conditional(self):
        """Ghi chú đỉnh nồng độ phải kết luận đã đối chiếu, không nêu điều kiện suông."""
        trace = self.report["air_quality"]["peak_trace"]
        log = render_cleaning_log(self.report)
        self.assertIn("Kiểm chứng đỉnh nồng độ", log)
        # Cụm cấu điều kiện cũ ("Nếu đỉnh này biến mất") không được quay lại.
        self.assertNotIn("Nếu đỉnh này biến mất", log)
        if trace["survived_cleaning"]:
            self.assertIn("vẫn còn nguyên", log)
        else:
            self.assertEqual(trace["nullified_by_physics_constraint"], True)
            self.assertIn("vi phạm ràng buộc khí động học", log)
            self.assertIn(trace["timestamp"], log)

    def test_log_lists_every_reason_that_created_missing_cells(self):
        """Mọi nguyên nhân tạo ra ô NaN phải xuất hiện trong bảng đối chiếu §7.1."""
        log = render_cleaning_log(self.report)
        for reason in (
            "Khoảng trống thời gian từ reindex + ràng buộc khí động học",
            "Thực thi ràng buộc khí động học PM2.5 ≤ PM10",
        ):
            self.assertIn(reason, log)

    def test_log_does_not_double_count_the_same_cause(self):
        """`rows_inserted` của reindex chỉ được liệt kê đúng một lần trong §7.1."""
        log = render_cleaning_log(self.report)
        reason = "Khoảng trống thời gian từ reindex (NaN cố ý)"
        self.assertEqual(log.count(reason), 1)
        # Bảng đối chiếu §7.1 nằm sau tiêu đề cột "| Phép biến đổi | Chỉ số | Số lượng |"
        # và trước ghi chú đỉnh nồng độ. Chỉ trong đoạn này mới được tính, vì tên chỉ số
        # `rows_inserted` vốn xuất hiện hợp lệ ở bảng thống kê từng bước của §3/§4.
        table = log.split("| Phép biến đổi | Chỉ số | Số lượng |", 1)[1]
        table = table.split("Lưu ý về đỉnh nồng độ", 1)[0]
        self.assertEqual(table.count(f"| {reason} | `rows_inserted` |"), 1)

    def test_log_uses_relative_paths_not_machine_specific_ones(self):
        """`docs/cleaning_log.md` được Git-track nên không chứa đường dẫn tuyệt đối."""
        report = run_deterministic_cleaning(
            self.tmp / "air_quality_canonical.parquet",
            self.tmp / "weather_canonical.parquet",
            save=False,
            project_root=self.tmp,
        )
        log = render_cleaning_log(report)
        # Đường dẫn được rút gọn còn tương đối so với project_root.
        self.assertIn("`air_quality_canonical.parquet`", log)
        self.assertNotIn(str(self.tmp), log)
        self.assertNotIn("C:\\", log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
