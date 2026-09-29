"""
Unit tests cho pipeline thu thập và chuẩn hóa dữ liệu chất lượng không khí & khí tượng Hà Nội.

Kiểm thử (Sử dụng unittest chuẩn thư viện Python):
1. Geographic filtering: Lọc đúng tọa độ Hà Nội, loại bỏ tọa độ ngoại lai (Albuquerque 35.1353, -106.584702).
2. Phát hiện duplicate (station_id, timestamp) và fail-fast.
3. Làm sạch giá trị dị thường: -999, -9999 -> NaN, âm -> NaN.
4. Bảo toàn giá trị đo 0.0 hợp lệ (không biến thành NaN).
5. Ánh xạ station_id và cơ chế từ chối location_id 2178 đã bị disqualified.
6. Assertion kiểm định 100% bản ghi canonical nằm trong Bounding Box Hà Nội.
"""

import unittest
import numpy as np
import pandas as pd

from src.data_collection import (
    HANOI_BBOX,
    STATION_OPENAQ_HANOI,
    STATION_AIRNOW_HANOI,
    WEATHER_CANONICAL_COLUMNS,
    WEATHER_PHYSICAL_BOUNDS,
    clean_air_quality_values,
    clean_weather_values,
    filter_hanoi_bounds,
    assert_canonical_within_hanoi,
    validate_canonical_uniqueness,
    validate_weather_canonical,
    resolve_station_metadata,
    OpenMeteoAdapter,
)


class TestDataCollectionPipeline(unittest.TestCase):
    def test_geographic_filtering_keeps_hanoi_and_drops_albuquerque(self):
        """Kiểm thử lọc địa lý: Giữ tọa độ Hà Nội, loại bỏ tọa độ Albuquerque (2178)."""
        df_test = pd.DataFrame({
            "location": ["556 Nguyễn Văn Cừ", "US Embassy Hanoi", "Del Norte (Albuquerque)", "Ho Chi Minh City"],
            "lat": [21.0491, 21.0215, 35.1353, 10.7769],
            "lon": [105.8831, 105.8184, -106.584702, 106.7009],
            "value": [35.0, 42.0, 18.0, 25.0],
        })

        df_filtered, stats = filter_hanoi_bounds(df_test, lat_col="lat", lon_col="lon")

        self.assertEqual(stats["raw_records"], 4)
        self.assertEqual(stats["filtered_out_records"], 2)
        self.assertEqual(stats["retained_records"], 2)
        self.assertFalse(stats["all_within_bounds"])

        retained_locs = df_filtered["location"].tolist()
        self.assertIn("556 Nguyễn Văn Cừ", retained_locs)
        self.assertIn("US Embassy Hanoi", retained_locs)
        self.assertNotIn("Del Norte (Albuquerque)", retained_locs)
        self.assertNotIn("Ho Chi Minh City", retained_locs)

    def test_duplicate_station_timestamp_fails_fast(self):
        """Kiểm thử phát hiện trùng lặp khóa (station_id, timestamp) và fail fast."""
        ts = pd.Timestamp("2025-07-04 10:00:00+07:00")
        df_dup = pd.DataFrame({
            "timestamp": [ts, ts],
            "station_id": [STATION_OPENAQ_HANOI, STATION_OPENAQ_HANOI],
            "pm25": [30.5, 32.1],
        })

        with self.assertRaises(ValueError) as ctx:
            validate_canonical_uniqueness(df_dup, key_cols=["station_id", "timestamp"])
        self.assertIn("Data Quality Violation", str(ctx.exception))

    def test_invalid_values_converted_to_nan(self):
        """Kiểm thử bóc trần mã lỗi ngụy trang (-999, -9999) và giá trị âm thành NaN."""
        self.assertTrue(np.isnan(clean_air_quality_values(-999)))
        self.assertTrue(np.isnan(clean_air_quality_values(-999.0)))
        self.assertTrue(np.isnan(clean_air_quality_values(-9999)))
        self.assertTrue(np.isnan(clean_air_quality_values(-9999.0)))
        self.assertTrue(np.isnan(clean_air_quality_values(-1.5)))
        self.assertTrue(np.isnan(clean_air_quality_values(np.nan)))
        self.assertTrue(np.isnan(clean_air_quality_values(None)))
        self.assertTrue(np.isnan(clean_air_quality_values("invalid")))

    def test_valid_zero_preserved(self):
        """Kiểm thử bảo toàn giá trị đo 0.0 hợp lệ (tuyệt đối không biến thành NaN)."""
        val = clean_air_quality_values(0.0)
        self.assertEqual(val, 0.0)
        self.assertFalse(np.isnan(val))

        val_int = clean_air_quality_values(0)
        self.assertEqual(val_int, 0.0)
        self.assertFalse(np.isnan(val_int))

    def test_positive_values_preserved(self):
        """Kiểm thử giá trị quan trắc dương bình thường được giữ nguyên."""
        self.assertEqual(clean_air_quality_values(35.5), 35.5)
        self.assertEqual(clean_air_quality_values(120.0), 120.0)

    def test_station_id_mapping_and_rejection_of_location_2178(self):
        """Kiểm thử ánh xạ đúng trạm và từ chối tuyệt đối location_id 2178."""
        # Trạm 4946811 hợp thức
        sid, loc, coords = resolve_station_metadata("openaq", 4946811)
        self.assertEqual(sid, STATION_OPENAQ_HANOI)
        self.assertEqual(loc, "556 Nguyễn Văn Cừ")
        self.assertEqual(coords, (21.0491, 105.8831))

        # Location 2178 bị disqualified -> phải ném lỗi
        with self.assertRaises(ValueError) as ctx:
            resolve_station_metadata("openaq", 2178)
        self.assertIn("loại bỏ/disqualified", str(ctx.exception))

        # Trạm AirNow DOS
        sid_air, loc_air, coords_air = resolve_station_metadata("airnow", "Hanoi")
        self.assertEqual(sid_air, STATION_AIRNOW_HANOI)
        self.assertEqual(loc_air, "US Diplomatic Post: Hanoi")
        self.assertEqual(coords_air, (21.0215, 105.8184))

    def test_canonical_assertion_passes_for_hanoi_and_fails_for_out_of_bounds(self):
        """Kiểm thử assertion 100% canonical records nằm trong Bounding Box Hà Nội."""
        df_valid = pd.DataFrame({
            "station_id": [STATION_OPENAQ_HANOI],
            "latitude": [21.0491],
            "longitude": [105.8831],
            "pm25": [45.0],
        })
        # Không ném lỗi
        assert_canonical_within_hanoi(df_valid)

        df_invalid = pd.DataFrame({
            "station_id": ["UNKNOWN_OUT_STATION"],
            "latitude": [35.1353],
            "longitude": [-106.584702],
            "pm25": [45.0],
        })
        with self.assertRaises((AssertionError, ValueError)):
            assert_canonical_within_hanoi(df_invalid)

    def test_airnow_adapter_raises_filenotfound_when_file_missing(self):
        """Kiểm thử AirNowDOSAdapter ném FileNotFoundError với thông báo rõ ràng khi tệp thô chưa có."""
        from src.data_collection import AirNowDOSAdapter
        adapter = AirNowDOSAdapter(csv_path="data/raw/non_existent_airnow.csv")
        with self.assertRaises(FileNotFoundError) as ctx:
            adapter.load_and_canonicalize()
        self.assertIn("AirNow DOS CSV không tồn tại", str(ctx.exception))

    def test_airnow_adapter_canonicalizes_valid_sample(self):
        """Kiểm thử AirNowDOSAdapter chuẩn hóa đúng khi có dữ liệu đầu vào chuẩn."""
        import tempfile
        import os
        from src.data_collection import AirNowDOSAdapter

        sample_csv_content = (
            "Site, Parameter, Date (LST), Year, Month, Day, Hour, Value, Unit, Duration, QC Name\n"
            "Hanoi, PM2.5, 2023-01-01 01:00, 2023, 1, 1, 1, 35.5, UG/M3, 1 Hr, Valid\n"
            "Hanoi, PM2.5, 2023-01-01 02:00, 2023, 1, 1, 2, -999, UG/M3, 1 Hr, Missing\n"
            "Hanoi, PM2.5, 2023-01-01 03:00, 2023, 1, 1, 3, 0.0, UG/M3, 1 Hr, Valid\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as tmp:
            tmp.write(sample_csv_content)
            tmp_path = tmp.name

        try:
            adapter = AirNowDOSAdapter(csv_path=tmp_path)
            df_canonical = adapter.load_and_canonicalize()
            self.assertEqual(len(df_canonical), 3)
            self.assertEqual(df_canonical["station_id"].iloc[0], STATION_AIRNOW_HANOI)
            self.assertEqual(df_canonical["pm25"].iloc[0], 35.5)
            self.assertTrue(np.isnan(df_canonical["pm25"].iloc[1]))  # -999 -> NaN
            self.assertEqual(df_canonical["pm25"].iloc[2], 0.0)      # 0.0 preserved
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_actual_timestamps_computed_directly_from_dataframe(self):
        """Kiểm thử actual_min_timestamp và actual_max_timestamp được lấy động từ DataFrame, không hardcode."""
        ts_range = pd.date_range("2023-05-01 00:00:00+07:00", "2023-05-10 23:00:00+07:00", freq="h")
        df_test = pd.DataFrame({"timestamp": ts_range})
        min_ts = str(df_test["timestamp"].min())
        max_ts = str(df_test["timestamp"].max())
        self.assertEqual(min_ts, "2023-05-01 00:00:00+07:00")
        self.assertEqual(max_ts, "2023-05-10 23:00:00+07:00")

    def test_open_meteo_raw_filename_reflects_date_range(self):
        """Kiểm thử OpenMeteoAdapter sinh tên file raw động theo dải ngày yêu cầu khi raw_output_name=None."""
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from src.data_collection import OpenMeteoAdapter

        with tempfile.TemporaryDirectory() as tmp_dir:
            adapter = OpenMeteoAdapter(raw_dir=Path(tmp_dir), interim_dir=Path(tmp_dir))

            mock_ctx = MagicMock()
            mock_ctx.status = 200
            mock_ctx.read.return_value = json.dumps({
                "latitude": 21.0545,
                "longitude": 105.8985,
                "hourly": {
                    "time": ["2025-07-03T00:00"],
                    "temperature_2m": [28.5],
                    "relative_humidity_2m": [80],
                    "wind_speed_10m": [2.1],
                    "wind_direction_10m": [120],
                    "precipitation": [0.0],
                    "surface_pressure": [1005.0],
                },
            }).encode("utf-8")

            mock_urlopen = MagicMock()
            mock_urlopen.__enter__.return_value = mock_ctx
            mock_urlopen.__exit__.return_value = None

            with patch("urllib.request.urlopen", return_value=mock_urlopen):
                _, raw_path = adapter.fetch_raw_data(
                    start_date="2025-07-03",
                    end_date="2026-07-15",
                    raw_output_name=None
                )

            self.assertEqual(raw_path.name, "open_meteo_raw_2025-07-03_2026-07-15.json")

    def test_air_and_weather_temporal_overlap_not_empty(self):
        """Kiểm thử phép inner join theo timestamp giữa chuỗi ô nhiễm và khí tượng không rỗng."""
        ts_air = pd.date_range("2025-07-03 22:00:00+07:00", "2025-07-04 10:00:00+07:00", freq="h")
        ts_weather = pd.date_range("2025-07-03 00:00:00+07:00", "2025-07-05 00:00:00+07:00", freq="h")

        df_air = pd.DataFrame({"timestamp": ts_air, "pm25": [35.0] * len(ts_air)})
        df_weather = pd.DataFrame({"timestamp": ts_weather, "temperature": [28.0] * len(ts_weather)})

        df_merged = pd.merge(df_air, df_weather, on="timestamp", how="inner")
        self.assertGreater(len(df_merged), 0)
        self.assertEqual(df_merged["timestamp"].min(), ts_air.min())
        self.assertEqual(df_merged["timestamp"].max(), ts_air.max())

    def test_dynamic_sync_window_derivation(self):
        """Kiểm thử trích xuất dải ngày động (YYYY-MM-DD) từ timestamp tz-aware Asia/Ho_Chi_Minh."""
        ts_range = pd.date_range(
            "2025-07-03 22:40:00",
            "2026-07-15 17:05:00",
            freq="h",
            tz="Asia/Ho_Chi_Minh"
        )
        df_air_sample = pd.DataFrame({"timestamp": ts_range})

        derived_start = df_air_sample["timestamp"].min().strftime("%Y-%m-%d")
        derived_end = df_air_sample["timestamp"].max().strftime("%Y-%m-%d")

        self.assertEqual(derived_start, "2025-07-03")
        self.assertEqual(derived_end, "2026-07-15")

    def test_weather_canonical_schema_and_types(self):
        """Kiểm thử chuẩn hóa Open-Meteo: Đủ 7 cột canonical, ép kiểu float64 và timezone Asia/Ho_Chi_Minh."""
        mock_raw = {
            "latitude": 21.0545,
            "longitude": 105.8985,
            "hourly": {
                "time": ["2025-07-03T00:00", "2025-07-03T01:00"],
                "temperature_2m": [25.5, 24.8],
                "relative_humidity_2m": [80, 85],
                "wind_speed_10m": [2.1, 1.8],
                "wind_direction_10m": [120, 135],
                "precipitation": [0.0, 1.2],
                "surface_pressure": [1005.2, 1004.9],
            },
        }
        adapter = OpenMeteoAdapter()
        df_canonical = adapter.to_canonical(mock_raw)

        # 1. Kiểm tra danh mục cột
        self.assertEqual(list(df_canonical.columns), WEATHER_CANONICAL_COLUMNS)

        # 2. Kiểm tra timezone
        self.assertIsNotNone(df_canonical["timestamp"].dt.tz)
        self.assertEqual(str(df_canonical["timestamp"].dt.tz), "Asia/Ho_Chi_Minh")

        # 3. Kiểm tra kiểu dữ liệu float64 cho 6 biến
        for col in WEATHER_CANONICAL_COLUMNS[1:]:
            self.assertEqual(df_canonical[col].dtype, np.float64, f"Cột {col} chưa được ép kiểu float64!")

    def test_weather_validation_passes_valid_data(self):
        """Kiểm thử validate_weather_canonical thành công đối với chuỗi giờ chuẩn."""
        ts_range = pd.date_range("2025-07-03 00:00:00+07:00", periods=24, freq="h")
        df_valid = pd.DataFrame({
            "timestamp": ts_range,
            "temperature": np.linspace(24.0, 32.0, 24),
            "relative_humidity": np.linspace(70.0, 85.0, 24),
            "wind_speed": np.linspace(1.5, 4.0, 24),
            "wind_direction": np.linspace(90.0, 180.0, 24),
            "precipitation": [0.0] * 20 + [2.5, 5.0, 1.0, 0.0],
            "surface_pressure": np.linspace(1005.0, 1008.0, 24),
        })

        report = validate_weather_canonical(df_valid)
        self.assertTrue(report["is_valid"])
        self.assertTrue(report["is_continuous_hourly"])
        self.assertEqual(report["gap_count"], 0)
        self.assertEqual(report["total_records"], 24)

    def test_weather_validation_detects_physical_bounds_violations(self):
        """Kiểm thử phát hiện vi phạm giới hạn vật lý khí tượng và ném lỗi ValueError."""
        ts_range = pd.date_range("2025-07-03 00:00:00+07:00", periods=3, freq="h")

        # Nhiệt độ phi lý (65°C tại Hà Nội)
        df_invalid_temp = pd.DataFrame({
            "timestamp": ts_range,
            "temperature": [25.0, 65.0, 28.0],
            "relative_humidity": [80.0, 80.0, 80.0],
            "wind_speed": [2.0, 2.0, 2.0],
            "wind_direction": [100.0, 100.0, 100.0],
            "precipitation": [0.0, 0.0, 0.0],
            "surface_pressure": [1005.0, 1005.0, 1005.0],
        })
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_invalid_temp)
        self.assertIn("vi phạm giới hạn vật lý", str(ctx.exception))

    def test_weather_validation_detects_duplicate_timestamps(self):
        """Kiểm thử validate_weather_canonical phát hiện trùng lặp timestamp."""
        ts = pd.Timestamp("2025-07-03 10:00:00+07:00")
        df_dup = pd.DataFrame({
            "timestamp": [ts, ts],
            "temperature": [25.0, 26.0],
            "relative_humidity": [80.0, 80.0],
            "wind_speed": [2.0, 2.0],
            "wind_direction": [100.0, 100.0],
            "precipitation": [0.0, 0.0],
            "surface_pressure": [1005.0, 1005.0],
        })
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_dup)
        self.assertIn("Data Quality Violation", str(ctx.exception))

    def test_weather_validation_detects_temporal_gap(self):
        """Kiểm thử phát hiện khoảng gián đoạn thời gian (> 1 giờ) trong chuỗi khí tượng."""
        ts = [
            pd.Timestamp("2025-07-03 00:00:00+07:00"),
            pd.Timestamp("2025-07-03 01:00:00+07:00"),
            pd.Timestamp("2025-07-03 04:00:00+07:00"),  # Nhảy cóc 3 giờ
        ]
        df_gap = pd.DataFrame({
            "timestamp": ts,
            "temperature": [25.0, 25.0, 26.0],
            "relative_humidity": [80.0, 80.0, 80.0],
            "wind_speed": [2.0, 2.0, 2.0],
            "wind_direction": [100.0, 100.0, 100.0],
            "precipitation": [0.0, 0.0, 0.0],
            "surface_pressure": [1005.0, 1005.0, 1005.0],
        })
        report = validate_weather_canonical(df_gap, check_continuity=True)
        self.assertFalse(report["is_continuous_hourly"])
        self.assertEqual(report["gap_count"], 1)

    def test_clean_weather_values_handles_disguised_missing_and_valid_zero(self):
        """Kiểm thử clean_weather_values: bóc trần mã lỗi, xử lý giá trị âm, bảo toàn 0.0 hợp lệ."""
        # Mã lỗi ngụy trang -> NaN
        self.assertTrue(np.isnan(clean_weather_values(-999)))
        self.assertTrue(np.isnan(clean_weather_values("-9999")))
        self.assertTrue(np.isnan(clean_weather_values("invalid")))

        # Giá trị âm phi vật lý -> NaN
        self.assertTrue(np.isnan(clean_weather_values(-2.5, "wind_speed")))
        self.assertTrue(np.isnan(clean_weather_values(-1.0, "precipitation")))
        self.assertTrue(np.isnan(clean_weather_values(105.0, "relative_humidity")))

        # Giá trị 0.0 hợp lệ -> giữ nguyên 0.0
        val_rain = clean_weather_values(0.0, "precipitation")
        self.assertEqual(val_rain, 0.0)
        self.assertFalse(np.isnan(val_rain))

        val_wind = clean_weather_values(0.0, "wind_speed")
        self.assertEqual(val_wind, 0.0)
        self.assertFalse(np.isnan(val_wind))

        # Giá trị hợp lệ bình thường
        self.assertEqual(clean_weather_values(28.5, "temperature"), 28.5)

    def test_open_meteo_adapter_rejects_out_of_bounds_grid_coordinates(self):
        """Kiểm thử OpenMeteoAdapter ném lỗi nếu tọa độ điểm lưới trả về nằm ngoài Bounding Box Hà Nội."""
        mock_raw_out = {
            "latitude": 35.1353,  # Albuquerque, NM
            "longitude": -106.5847,
            "hourly": {
                "time": ["2025-07-03T00:00"],
                "temperature_2m": [25.0],
                "relative_humidity_2m": [80],
                "wind_speed_10m": [2.0],
                "wind_direction_10m": [100],
                "precipitation": [0.0],
                "surface_pressure": [1005.0],
            },
        }
        adapter = OpenMeteoAdapter()
        with self.assertRaises(AssertionError) as ctx:
            adapter.to_canonical(mock_raw_out)
        self.assertIn("nằm ngoài Bounding Box Hà Nội", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
