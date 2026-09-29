"""
Unit tests cho pipeline thu thập và chuẩn hóa dữ liệu chất lượng không khí & khí tượng Hà Nội.

Kiểm thử (Sử dụng unittest chuẩn thư viện Python):
1. Geographic filtering: Lọc đúng tọa độ Hà Nội, loại bỏ tọa độ ngoại lai (Albuquerque 35.1353, -106.584702).
2. Phát hiện duplicate (station_id, timestamp) và fail-fast.
3. Làm sạch giá trị dị thường: -999, -9999 -> NaN, âm -> NaN.
4. Bảo toàn giá trị đo 0.0 hợp lệ (không biến thành NaN).
5. Ánh xạ station_id và cơ chế từ chối location_id 2178 đã bị disqualified.
6. Assertion kiểm định 100% bản ghi canonical nằm trong Bounding Box Hà Nội.
7. AC4-11: đối chiếu `hourly_units` của raw Open-Meteo response với đơn vị chuẩn.
8. AC4-12: timestamp bắt buộc đúng timezone IANA `Asia/Ho_Chi_Minh`
   (fixed offset +07:00 bị từ chối).
"""

import datetime
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_collection import (
    HANOI_BBOX,
    CANONICAL_TIMEZONE,
    LOCATION_OPENAQ_HANOI,
    STATION_OPENAQ_HANOI,
    STATION_AIRNOW_HANOI,
    STATION_WEATHER_ERA5,
    WEATHER_CANONICAL_COLUMNS,
    WEATHER_EXPECTED_UNITS,
    WEATHER_PHYSICAL_BOUNDS,
    WEATHER_QUERY_COORDS,
    clean_air_quality_values,
    clean_weather_values,
    filter_hanoi_bounds,
    assert_canonical_within_hanoi,
    is_canonical_timezone,
    is_sentinel_code,
    resolve_canonical_timezone_key,
    summarize_weather_cleaning,
    validate_canonical_uniqueness,
    validate_open_meteo_hourly_units,
    validate_weather_canonical,
    resolve_station_metadata,
    OpenAQAdapter,
    OpenMeteoAdapter,
)

# `hourly_units` chuẩn của Open-Meteo cho 6 biến khí tượng canonical.
# Dùng cho fixture payload; KHÔNG phải dữ liệu quan trắc thực tế.
EXPECTED_HOURLY_UNITS = {
    provider_field: unit for provider_field, unit in WEATHER_EXPECTED_UNITS.values()
}


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
                "hourly_units": dict(EXPECTED_HOURLY_UNITS),
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
            "hourly_units": dict(EXPECTED_HOURLY_UNITS),
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
        ts_range = pd.date_range("2025-07-03 00:00:00", periods=24, freq="h", tz=CANONICAL_TIMEZONE)
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
        ts_range = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz=CANONICAL_TIMEZONE)

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
        ts = pd.Timestamp("2025-07-03 10:00:00", tz=CANONICAL_TIMEZONE)
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
            pd.Timestamp("2025-07-03 00:00:00", tz=CANONICAL_TIMEZONE),
            pd.Timestamp("2025-07-03 01:00:00", tz=CANONICAL_TIMEZONE),
            pd.Timestamp("2025-07-03 04:00:00", tz=CANONICAL_TIMEZONE),  # Nhảy cóc 3 giờ
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
            "hourly_units": dict(EXPECTED_HOURLY_UNITS),
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

    # ------------------------------------------------------------------
    # AC3 – Hanoi geographic compatibility
    # ------------------------------------------------------------------

    def test_weather_station_metadata_resolves_to_hanoi_grid(self):
        """AC3: trạm khí tượng canonical phải là điểm lưới ERA5 nằm trong Hà Nội."""
        sid, loc, coords = resolve_station_metadata("open_meteo", None)
        self.assertEqual(sid, STATION_WEATHER_ERA5)
        self.assertIn("ERA5", loc)
        lat, lon = coords
        self.assertTrue(HANOI_BBOX["lat_min"] <= lat <= HANOI_BBOX["lat_max"])
        self.assertTrue(HANOI_BBOX["lon_min"] <= lon <= HANOI_BBOX["lon_max"])

    def test_open_meteo_default_query_coordinates_are_inside_hanoi_bbox(self):
        """AC3: tọa độ truy vấn mặc định phải là tâm lõi Hà Nội, nằm trong Bounding Box."""
        lat, lon = WEATHER_QUERY_COORDS
        self.assertTrue(HANOI_BBOX["lat_min"] <= lat <= HANOI_BBOX["lat_max"])
        self.assertTrue(HANOI_BBOX["lon_min"] <= lon <= HANOI_BBOX["lon_max"])

        adapter = OpenMeteoAdapter()
        self.assertEqual(adapter.latitude, lat)
        self.assertEqual(adapter.longitude, lon)

    def test_open_meteo_adapter_rejects_non_hanoi_request_coordinates(self):
        """AC3: adapter phải từ chối tọa độ truy vấn ngoài Hà Nội ngay khi khởi tạo."""
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter(latitude=35.1353, longitude=-106.5847)  # Albuquerque, NM
        self.assertIn("nằm NGOÀI Bounding Box Hà Nội", str(ctx.exception))

    def test_open_meteo_to_canonical_fails_loud_when_response_has_no_coordinates(self):
        """AC3: thiếu tọa độ trong payload phải raise, không được thay bằng hằng số nội bộ."""
        mock_raw_no_coords = {
            "hourly_units": dict(EXPECTED_HOURLY_UNITS),
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
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().to_canonical(mock_raw_no_coords)
        self.assertIn("không trả về tọa độ điểm lưới", str(ctx.exception))

    # ------------------------------------------------------------------
    # AC2 – dynamic temporal window (không hardcode study window)
    # ------------------------------------------------------------------

    def test_fetch_raw_data_requires_explicit_window(self):
        """
        AC2: fetch_raw_data() KHÔNG được có khung thời gian lịch sử cố định mặc định.
        Issue #4 yêu cầu loại bỏ hoàn toàn việc áp đặt trước cửa sổ nghiên cứu.
        """
        import inspect

        params = inspect.signature(OpenMeteoAdapter.fetch_raw_data).parameters
        self.assertIn("start_date", params)
        self.assertIn("end_date", params)
        self.assertIs(
            params["start_date"].default, inspect.Parameter.empty, "start_date không được có giá trị mặc định"
        )
        self.assertIs(
            params["end_date"].default, inspect.Parameter.empty, "end_date không được có giá trị mặc định"
        )

    def test_fetch_raw_data_rejects_empty_window(self):
        """AC2: cửa sổ rỗng phải bị từ chối rõ ràng, không được âm thầm dùng cửa sổ cố định."""
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().fetch_raw_data(start_date="", end_date="")
        self.assertIn("là bắt buộc", str(ctx.exception))

    def test_request_url_encodes_requested_dynamic_window(self):
        """AC2: URL truy vấn phải mang đúng dải ngày động được yêu cầu (dùng cho provenance)."""
        url = OpenMeteoAdapter().build_request_url("2025-07-03", "2026-07-15")
        self.assertIn("start_date=2025-07-03", url)
        self.assertIn("end_date=2026-07-15", url)
        self.assertIn("wind_speed_unit=ms", url)
        self.assertIn("archive-api.open-meteo.com", url)

    # ------------------------------------------------------------------
    # AC7 – timezone
    # ------------------------------------------------------------------

    def test_weather_validation_rejects_naive_timestamp(self):
        """AC7: canonical timestamp bắt buộc tz-aware, naive datetime phải bị từ chối."""
        df_naive = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-07-03 00:00:00", periods=3, freq="h"),
                "temperature": [25.0, 25.5, 26.0],
                "relative_humidity": [80.0, 81.0, 82.0],
                "wind_speed": [2.0, 2.1, 2.2],
                "wind_direction": [100.0, 110.0, 120.0],
                "precipitation": [0.0, 0.0, 0.0],
                "surface_pressure": [1005.0, 1005.1, 1005.2],
            }
        )
        self.assertIsNone(df_naive["timestamp"].dt.tz)
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_naive)
        self.assertIn("tz-aware", str(ctx.exception))

    def test_weather_validation_rejects_wrong_timezone(self):
        """AC7: timestamp tz-aware nhưng sai múi giờ (ví dụ UTC) vẫn phải bị từ chối."""
        ts_utc = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz="UTC")
        df_utc = pd.DataFrame(
            {
                "timestamp": ts_utc,
                "temperature": [25.0, 25.5, 26.0],
                "relative_humidity": [80.0, 81.0, 82.0],
                "wind_speed": [2.0, 2.1, 2.2],
                "wind_direction": [100.0, 110.0, 120.0],
                "precipitation": [0.0, 0.0, 0.0],
                "surface_pressure": [1005.0, 1005.1, 1005.2],
            }
        )
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_utc)
        self.assertIn(CANONICAL_TIMEZONE, str(ctx.exception))

    def test_weather_canonical_reports_hanoi_timezone(self):
        """AC7: báo cáo kiểm định phải ghi rõ múi giờ canonical đang áp dụng."""
        adapter = OpenMeteoAdapter()
        df = adapter.to_canonical(_mock_weather_payload(), validate=False)
        report = validate_weather_canonical(df)
        self.assertEqual(report["timezone"], "Asia/Ho_Chi_Minh")
        self.assertEqual(str(df["timestamp"].dt.tz), CANONICAL_TIMEZONE)

    # ------------------------------------------------------------------
    # AC8 – sentinel / zero preservation / cleaning transparency
    # ------------------------------------------------------------------

    def test_is_sentinel_code_keeps_valid_zero(self):
        """AC8: -999/-9999 là sentinel; 0.0 là giá trị đo hợp lệ, tuyệt đối không phải sentinel."""
        self.assertTrue(is_sentinel_code(-999))
        self.assertTrue(is_sentinel_code(-9999.0))
        self.assertTrue(is_sentinel_code("-999.0"))
        self.assertFalse(is_sentinel_code(0.0))
        self.assertFalse(is_sentinel_code(0))
        self.assertFalse(is_sentinel_code(None))
        self.assertFalse(is_sentinel_code(float("nan")))

    def test_summarize_weather_cleaning_separates_null_reasons(self):
        """AC8/AC10: cleaning phải báo cáo minh bạch sentinel vs vi phạm giới hạn vật lý."""
        raw = {"temperature": [25.0, -999.0, 999.0, 0.0, None, "abc"]}
        cleaned = {
            "temperature": [
                clean_weather_values(v, "temperature") for v in raw["temperature"]
            ]
        }
        stats = summarize_weather_cleaning(raw, cleaned)["temperature"]
        self.assertEqual(stats["disguised_missing"], 1)   # -999
        self.assertEqual(stats["out_of_bounds"], 1)        # 999 °C
        self.assertEqual(stats["unparseable"], 1)          # "abc"
        # 0.0 hợp lệ và NaN sẵn có không bị tính là giá trị bị loại bỏ
        self.assertEqual(sum(stats.values()), 3)

    def test_to_canonical_preserves_zero_and_nulls_sentinels(self):
        """AC8: 0.0 đo được giữ nguyên; sentinel -999 thành NaN; cleaning được đếm minh bạch."""
        payload = _mock_weather_payload(
            temperature=[0.0, -999.0, 25.5],
            precipitation=[0.0, 0.0, 1.2],
        )
        df = OpenMeteoAdapter().to_canonical(payload, validate=False)

        self.assertEqual(df["temperature"].iloc[0], 0.0)      # 0 °C hợp lệ
        self.assertTrue(np.isnan(df["temperature"].iloc[1]))  # -999 -> NaN
        self.assertEqual(df["temperature"].iloc[2], 25.5)
        self.assertEqual(list(df["precipitation"][:2]), [0.0, 0.0])  # 0 mm hợp lệ

        cleaning = df.attrs["weather_cleaning"]
        self.assertEqual(cleaning["temperature"]["disguised_missing"], 1)
        self.assertEqual(cleaning["temperature"]["out_of_bounds"], 0)
        self.assertEqual(cleaning["precipitation"]["disguised_missing"], 0)

    def test_validation_surfaces_values_nulled_by_cleaning(self):
        """
        AC8/AC9/AC10: giá trị bị lớp cleaning loại bỏ vì vi phạm giới hạn vật lý phải được
        báo cáo, thay vì báo '0 vi phạm' một cách giả định.
        """
        payload = _mock_weather_payload(temperature=[25.0, 999.0, 26.0])
        df = OpenMeteoAdapter().to_canonical(payload, validate=False)
        self.assertTrue(np.isnan(df["temperature"].iloc[1]))

        report = validate_weather_canonical(df)
        self.assertEqual(report["cleaning_totals"]["out_of_bounds"], 1)
        self.assertTrue(any("vi phạm giới hạn" in w for w in report["warnings"]))

    # ------------------------------------------------------------------
    # AC6/AC8/AC10 – schema, ordering, missing threshold
    # ------------------------------------------------------------------

    def test_weather_validation_detects_schema_violation(self):
        """AC6: thiếu cột canonical phải raise ValueError nêu rõ danh sách cột thiếu."""
        ts_range = pd.date_range("2025-07-03 00:00:00+07:00", periods=3, freq="h")
        df_bad = pd.DataFrame({"timestamp": ts_range, "temperature": [25.0, 25.5, 26.0]})
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_bad)
        self.assertIn("thiếu cột bắt buộc", str(ctx.exception))

    def test_weather_validation_detects_non_monotonic_timestamps(self):
        """AC8/AC10: timestamp không tăng đơn điệu phải raise, không tự sắp xếp lại."""
        ts = [
            pd.Timestamp("2025-07-03 01:00:00", tz=CANONICAL_TIMEZONE),
            pd.Timestamp("2025-07-03 00:00:00", tz=CANONICAL_TIMEZONE),
        ]
        df_unsorted = pd.DataFrame({
            "timestamp": ts,
            "temperature": [25.0, 26.0],
            "relative_humidity": [80.0, 81.0],
            "wind_speed": [2.0, 2.1],
            "wind_direction": [100.0, 110.0],
            "precipitation": [0.0, 0.0],
            "surface_pressure": [1005.0, 1005.1],
        })
        before = df_unsorted.copy(deep=True)
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_unsorted)
        self.assertIn("tăng đơn điệu", str(ctx.exception))
        # Hàm kiểm định phải read-only: dữ liệu đầu vào không bị sửa
        pd.testing.assert_frame_equal(df_unsorted, before)

    def test_weather_validation_fails_when_missing_exceeds_threshold(self):
        """AC8/AC10: tỷ lệ khuyết thiếu vượt ngưỡng phải raise thay vì im lặng."""
        ts_range = pd.date_range("2025-07-03 00:00:00", periods=4, freq="h", tz=CANONICAL_TIMEZONE)
        df_missing = pd.DataFrame({
            "timestamp": ts_range,
            "temperature": [25.0, np.nan, 26.0, 27.0],
            "relative_humidity": [80.0, 81.0, 82.0, 83.0],
            "wind_speed": [2.0, 2.1, 2.2, 2.3],
            "wind_direction": [100.0, 110.0, 120.0, 130.0],
            "precipitation": [0.0, 0.0, 0.0, 0.0],
            "surface_pressure": [1005.0, 1005.1, 1005.2, 1005.3],
        })
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_missing, max_missing_pct=0.0)
        self.assertIn("vượt ngưỡng cho phép", str(ctx.exception))

        # Nới ngưỡng thì phải qua được và vẫn báo cáo tỷ lệ khuyết thiếu
        report = validate_weather_canonical(df_missing, max_missing_pct=50.0)
        self.assertEqual(report["max_missing_pct"], 25.0)

    def test_weather_validation_reports_gap_as_warning_not_silent_pass(self):
        """AC10: gián đoạn là WARNING, nhưng `is_valid` phải phản ánh trung thực."""
        ts = [
            pd.Timestamp("2025-07-03 00:00:00", tz=CANONICAL_TIMEZONE),
            pd.Timestamp("2025-07-03 01:00:00", tz=CANONICAL_TIMEZONE),
            pd.Timestamp("2025-07-03 04:00:00", tz=CANONICAL_TIMEZONE),
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
        self.assertFalse(report["is_valid"])
        self.assertEqual(report["validation_status"], "passed_with_warnings")
        self.assertEqual(report["gap_count"], 1)
        self.assertTrue(any("gián đoạn" in w for w in report["warnings"]))

    def test_weather_validation_is_read_only(self):
        """AC10: hàm kiểm định không được âm thầm sửa dữ liệu đầu vào."""
        df = OpenMeteoAdapter().to_canonical(_mock_weather_payload(), validate=False)
        snapshot = df.copy(deep=True)
        validate_weather_canonical(df)
        pd.testing.assert_frame_equal(df, snapshot)
        self.assertEqual(list(df.columns), WEATHER_CANONICAL_COLUMNS)

    # ------------------------------------------------------------------
    # AC11 – đơn vị: đối chiếu `hourly_units` của raw Open-Meteo response
    # ------------------------------------------------------------------

    def test_expected_units_constant_maps_all_six_canonical_variables(self):
        """AC11: bảng đơn vị chuẩn phải phủ đúng 6 biến canonical + tên trường provider."""
        self.assertEqual(
            WEATHER_EXPECTED_UNITS,
            {
                "temperature": ("temperature_2m", "°C"),
                "relative_humidity": ("relative_humidity_2m", "%"),
                "wind_speed": ("wind_speed_10m", "m/s"),
                "wind_direction": ("wind_direction_10m", "°"),
                "precipitation": ("precipitation", "mm"),
                "surface_pressure": ("surface_pressure", "hPa"),
            },
        )

    def test_hourly_units_helper_accepts_complete_correct_units(self):
        """AC11: payload có đủ 6 đơn vị đúng -> validation pass, trả về đơn vị đã kiểm định."""
        validated = validate_open_meteo_hourly_units(_mock_weather_payload())
        self.assertEqual(
            validated,
            {var: unit for var, (_field, unit) in WEATHER_EXPECTED_UNITS.items()},
        )

    def test_hourly_units_helper_rejects_missing_hourly_units_block(self):
        """AC11: thiếu hẳn trường `hourly_units` phải fail loud, không giả định đơn vị đúng."""
        payload = _mock_weather_payload()
        del payload["hourly_units"]
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(payload)
        self.assertIn("hourly_units", str(ctx.exception))

    def test_hourly_units_helper_rejects_missing_single_variable_unit(self):
        """AC11: thiếu unit của một biến phải fail và nêu rõ biến/trường bị thiếu."""
        units = dict(EXPECTED_HOURLY_UNITS)
        del units["surface_pressure"]
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(_mock_weather_payload(hourly_units=units))
        message = str(ctx.exception)
        self.assertIn("thiếu khai báo đơn vị", message)
        self.assertIn("surface_pressure", message)

    def test_hourly_units_helper_rejects_wrong_unit_value(self):
        """AC11: unit sai (ví dụ °F thay vì °C) phải fail và nêu rõ expected vs actual."""
        units = dict(EXPECTED_HOURLY_UNITS)
        units["temperature_2m"] = "°F"
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(_mock_weather_payload(hourly_units=units))
        message = str(ctx.exception)
        self.assertIn("temperature", message)
        self.assertIn("°F", message)
        self.assertIn("°C", message)

    def test_hourly_units_helper_rejects_unknown_unit_without_silent_conversion(self):
        """AC11: unit lạ (ví dụ km/h cho wind_speed) không được âm thầm quy đổi hay chấp nhận."""
        units = dict(EXPECTED_HOURLY_UNITS)
        units["wind_speed_10m"] = "km/h"
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(_mock_weather_payload(hourly_units=units))
        self.assertIn("km/h", str(ctx.exception))

    def test_hourly_units_helper_is_read_only(self):
        """AC11: hàm kiểm định đơn vị không được sửa payload gốc."""
        payload = _mock_weather_payload()
        snapshot = json.loads(json.dumps(payload))
        validate_open_meteo_hourly_units(payload)
        self.assertEqual(payload, snapshot)

    def test_to_canonical_passes_with_correct_hourly_units(self):
        """AC11: pipeline canonicalization chạy được khi raw response khai báo đủ đơn vị chuẩn."""
        df = OpenMeteoAdapter().to_canonical(_mock_weather_payload(), validate=True)
        self.assertEqual(list(df.columns), WEATHER_CANONICAL_COLUMNS)
        self.assertEqual(str(df["timestamp"].dt.tz), CANONICAL_TIMEZONE)

    def test_to_canonical_fails_when_hourly_units_missing(self):
        """AC11: to_canonical phải chặn payload không có `hourly_units` (fail loud end-to-end)."""
        payload = _mock_weather_payload()
        del payload["hourly_units"]
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().to_canonical(payload, validate=False)
        self.assertIn("hourly_units", str(ctx.exception))

    def test_to_canonical_fails_when_single_unit_is_wrong(self):
        """AC11: một unit sai trong raw response phải làm to_canonical raise, nêu rõ biến."""
        payload = _mock_weather_payload()
        payload["hourly_units"]["precipitation"] = "inch"
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().to_canonical(payload, validate=False)
        message = str(ctx.exception)
        self.assertIn("precipitation", message)
        self.assertIn("inch", message)
        self.assertIn("mm", message)

    def test_to_canonical_fails_when_single_unit_is_absent(self):
        """AC11: một unit bị thiếu trong raw response phải làm to_canonical raise."""
        payload = _mock_weather_payload()
        del payload["hourly_units"]["relative_humidity_2m"]
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().to_canonical(payload, validate=False)
        message = str(ctx.exception)
        self.assertIn("thiếu khai báo đơn vị", message)
        self.assertIn("relative_humidity_2m", message)

    # ------------------------------------------------------------------
    # AC12 – timezone: đúng identity IANA `Asia/Ho_Chi_Minh`
    # ------------------------------------------------------------------

    def _valid_weather_frame(self, timestamps) -> pd.DataFrame:
        """Frame khí tượng hợp lệ về mặt schema, chỉ khác nhau ở cách biểu diễn timestamp."""
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "temperature": [25.0] * len(timestamps),
                "relative_humidity": [80.0] * len(timestamps),
                "wind_speed": [2.0] * len(timestamps),
                "wind_direction": [100.0] * len(timestamps),
                "precipitation": [0.0] * len(timestamps),
                "surface_pressure": [1005.0] * len(timestamps),
            }
        )

    def test_validation_accepts_canonical_iana_timezone(self):
        """AC12: timezone IANA `Asia/Ho_Chi_Minh` phải pass."""
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz=CANONICAL_TIMEZONE)
        report = validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["timezone"], CANONICAL_TIMEZONE)
        self.assertEqual(report["utc_offset_hours"], 7.0)

    def test_validation_rejects_fixed_offset_0700_timezone(self):
        """AC12: fixed offset `+07:00` phải bị từ chối dù có cùng độ lệch UTC+7."""
        ts = pd.date_range(
            "2025-07-03 00:00:00", periods=3, freq="h", tz=datetime.timezone(datetime.timedelta(hours=7))
        )
        # Offset thực tế đúng +7 -> chứng minh đây là fixed offset, không phải sai lệch múi giờ.
        self.assertEqual(ts[0].utcoffset(), datetime.timedelta(hours=7))
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn(CANONICAL_TIMEZONE, str(ctx.exception))
        self.assertIn("fixed offset", str(ctx.exception))

    def test_validation_rejects_utc_offset_alias_timezone(self):
        """AC12: timezone alias khác tên nhưng cùng offset (Etc/GMT-7) cũng phải bị từ chối."""
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz="Etc/GMT-7")
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn(CANONICAL_TIMEZONE, str(ctx.exception))

    def test_validation_rejects_other_iana_timezone_with_same_offset(self):
        """AC12: timezone IANA khác nhưng cùng UTC+7 (Asia/Singapore) phải bị từ chối."""
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz="Asia/Singapore")
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn(CANONICAL_TIMEZONE, str(ctx.exception))

    def test_validation_rejects_naive_timestamp_via_timezone_layer(self):
        """AC12: timestamp naive không có timezone phải bị từ chối ở lớp kiểm định."""
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h")
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn("tz-aware", str(ctx.exception))

    def test_canonical_timezone_key_helper_distinguishes_named_zone_from_fixed_offset(self):
        """AC12: helper phải trả về khóa IANA cho named zone và None cho fixed offset."""
        named = pd.date_range("2025-07-03", periods=1, tz=CANONICAL_TIMEZONE).dtype.tz
        fixed = pd.date_range(
            "2025-07-03", periods=1, tz=datetime.timezone(datetime.timedelta(hours=7))
        ).dtype.tz

        self.assertEqual(resolve_canonical_timezone_key(named), CANONICAL_TIMEZONE)
        self.assertIsNone(resolve_canonical_timezone_key(fixed))
        self.assertIsNone(resolve_canonical_timezone_key(None))

        self.assertTrue(is_canonical_timezone(named))
        self.assertFalse(is_canonical_timezone(fixed))

    def test_to_canonical_normalizes_fixed_offset_input_to_canonical_zone(self):
        """
        AC12: payload có mốc giờ ghi kèm offset `+07:00` vẫn được chuẩn hóa về
        đúng timezone IANA canonical (tz_convert), và output pass validation.
        """
        payload = _mock_weather_payload(n_hours=2)
        payload["hourly"]["time"] = ["2025-07-03T00:00:00+07:00", "2025-07-03T01:00:00+07:00"]
        df = OpenMeteoAdapter().to_canonical(payload, validate=True)
        self.assertEqual(str(df["timestamp"].dt.tz), CANONICAL_TIMEZONE)
        self.assertTrue(is_canonical_timezone(df["timestamp"].dtype.tz))


def _mock_weather_payload(n_hours: int = 3, hourly_units=None, **overrides) -> dict:
    """Payload Open-Meteo tối giản, deterministic, dùng cho unit test (không gọi mạng)."""
    payload = {
        "latitude": 21.05448,
        "longitude": 105.898476,
        "hourly_units": dict(EXPECTED_HOURLY_UNITS) if hourly_units is None else hourly_units,
        "hourly": {
            "time": [f"2025-07-03T{h:02d}:00" for h in range(n_hours)],
            "temperature_2m": [25.0] * n_hours,
            "relative_humidity_2m": [80.0] * n_hours,
            "wind_speed_10m": [2.0] * n_hours,
            "wind_direction_10m": [100.0] * n_hours,
            "precipitation": [0.0] * n_hours,
            "surface_pressure": [1005.0] * n_hours,
        },
    }
    for canonical_col, values in overrides.items():
        provider_field = {
            "temperature": "temperature_2m",
            "relative_humidity": "relative_humidity_2m",
            "wind_speed": "wind_speed_10m",
            "wind_direction": "wind_direction_10m",
            "precipitation": "precipitation",
            "surface_pressure": "surface_pressure",
        }[canonical_col]
        payload["hourly"][provider_field] = values
    return payload


class TestOpenAQAdapterToCanonical(unittest.TestCase):
    """
    Kiểm thử TRỰC TIẾP hợp đồng (contract) của `OpenAQAdapter.to_canonical()`.

    Mọi fixture là dữ liệu TỔNG HỢP trong bộ nhớ, dựng theo đúng schema raw OpenAQ
    (`location_id, sensors_id, location, datetime, lat, lon, parameter, units, value`).
    KHÔNG có bất kỳ lời gọi mạng nào, KHÔNG đọc/ghi data/raw, và TẤT ĐỊNH hoàn toàn
    (cùng đầu vào -> cùng đầu ra).
    """

    STATION_LAT = 21.0491
    STATION_LON = 105.8831
    ALBUQUERQUE_LAT = 35.1353
    ALBUQUERQUE_LON = -106.584702

    def _adapter(self, tmp_dir):
        return OpenAQAdapter(raw_dir=Path(tmp_dir), interim_dir=Path(tmp_dir))

    def _raw_frame(self, datetimes, parameters, values, lats=None, lons=None):
        """Dựng DataFrame raw OpenAQ tối thiểu theo schema provider thực tế."""
        n = len(datetimes)
        return pd.DataFrame({
            "location_id": [4946811] * n,
            "sensors_id": ["sensor-synthetic-001"] * n,
            "location": [LOCATION_OPENAQ_HANOI] * n,
            "datetime": datetimes,
            "lat": lats if lats is not None else [self.STATION_LAT] * n,
            "lon": lons if lons is not None else [self.STATION_LON] * n,
            "parameter": parameters,
            "units": ["µg/m³"] * n,
            "value": values,
        })

    def test_to_canonical_returns_exact_canonical_schema(self):
        """Đầu ra đúng 5 cột canonical theo đúng thứ tự và index sạch."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:00:00+07:00"],
            parameters=["pm25"],
            values=[30.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertEqual(
            list(df_out.columns),
            ["timestamp", "station_id", "location", "pm25", "pm10"],
        )
        self.assertTrue(df_out.index.equals(pd.RangeIndex(len(df_out))))
        self.assertEqual(len(df_out), 1)
        self.assertIsNone(df_out.index.name)

    def test_to_canonical_maps_station_identity_to_canonical_constants(self):
        """station_id / location được phân giải đúng theo quy chuẩn trạm Hà Nội."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:00:00+07:00"],
            parameters=["pm25"],
            values=[30.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertEqual(df_out["station_id"].unique().tolist(), [STATION_OPENAQ_HANOI])
        self.assertEqual(df_out["location"].unique().tolist(), [LOCATION_OPENAQ_HANOI])

    def test_to_canonical_produces_tz_aware_hanoi_hourly_timestamps(self):
        """Timestamp đầu ra phải tz-aware Asia/Ho_Chi_Minh và đã floor về giờ."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:37:41+07:00"],
            parameters=["pm25"],
            values=[30.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        ts = df_out["timestamp"].iloc[0]
        self.assertEqual(str(ts.tz), CANONICAL_TIMEZONE)
        self.assertEqual(ts.minute, 0)
        self.assertEqual(ts.second, 0)
        self.assertEqual(ts, pd.Timestamp("2025-07-04 22:00:00+07:00"))

    def test_to_canonical_converts_utc_input_and_rolls_over_date_boundary(self):
        """
        Đầu vào UTC phải được quy đổi sang Asia/Ho_Chi_Minh TRƯỚC khi floor về giờ,
        nên một mốc UTC tối khuya vẫn sinh ra giờ 00:00 của ngày hôm sau (lịch Hà Nội).
        """
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T16:40:00Z", "2025-07-04T17:10:00Z"],
            parameters=["pm25", "pm25"],
            values=[10.0, 20.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        timestamps = df_out["timestamp"].tolist()
        self.assertEqual(
            timestamps,
            [
                pd.Timestamp("2025-07-04 23:00:00+07:00"),
                pd.Timestamp("2025-07-05 00:00:00+07:00"),
            ],
        )

    def test_to_canonical_aggregates_subhourly_telemetry_to_hourly_mean(self):
        """Telemetry dưới giờ được tổng hợp thành trung bình theo giờ cho từng thông số."""
        df_raw = self._raw_frame(
            datetimes=[
                "2025-07-04T22:10:00+07:00",
                "2025-07-04T22:40:00+07:00",
                "2025-07-04T22:50:00+07:00",
            ],
            parameters=["pm25", "pm25", "pm25"],
            values=[30.0, 40.0, 50.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertEqual(len(df_out), 1)
        self.assertAlmostEqual(float(df_out["pm25"].iloc[0]), 40.0, places=6)

    def test_to_canonical_separates_pm25_and_pm10_into_distinct_columns(self):
        """pm25 và pm10 là hai cột độc lập, không trộn lẫn giá trị."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:00:00+07:00"] * 2,
            parameters=["pm25", "pm10"],
            values=[12.5, 88.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertAlmostEqual(float(df_out["pm25"].iloc[0]), 12.5, places=6)
        self.assertAlmostEqual(float(df_out["pm10"].iloc[0]), 88.0, places=6)

    def test_to_canonical_keeps_non_pm_parameters_out_of_canonical_output(self):
        """Thông số ngoài pm25/pm10 (o3, co, no2, so2) bị loại, không sinh cột mới."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:00:00+07:00"] * 4,
            parameters=["o3", "co", "no2", "pm25"],
            values=[1.0, 2.0, 3.0, 33.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertEqual(list(df_out.columns), ["timestamp", "station_id", "location", "pm25", "pm10"])
        self.assertAlmostEqual(float(df_out["pm25"].iloc[0]), 33.0, places=6)
        self.assertTrue(np.isnan(float(df_out["pm10"].iloc[0])))

    def test_to_canonical_emits_all_nan_column_when_a_pollutant_is_absent(self):
        """Thiếu hoàn toàn một thông số -> cột tương ứng phải tồn tại và toàn NaN (không fill 0)."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:00:00+07:00", "2025-07-04T23:00:00+07:00"],
            parameters=["pm25", "pm25"],
            values=[30.0, 31.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertIn("pm10", df_out.columns)
        self.assertTrue(df_out["pm10"].isna().all())
        self.assertEqual(len(df_out), 2)

    def test_to_canonical_nulls_sentinels_and_negative_values_but_preserves_zero(self):
        """-999/-9999/giá trị âm -> NaN; giá trị đo 0.0 hợp lệ phải được giữ nguyên."""
        df_raw = self._raw_frame(
            datetimes=[
                "2025-07-04T22:00:00+07:00",
                "2025-07-04T23:00:00+07:00",
                "2025-07-05T00:00:00+07:00",
            ],
            parameters=["pm25", "pm25", "pm25"],
            values=[-999.0, -9999.0, 0.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        by_hour = dict(zip(df_out["timestamp"], df_out["pm25"]))
        self.assertTrue(np.isnan(by_hour[pd.Timestamp("2025-07-04 22:00:00+07:00")]))
        self.assertTrue(np.isnan(by_hour[pd.Timestamp("2025-07-04 23:00:00+07:00")]))
        self.assertEqual(float(by_hour[pd.Timestamp("2025-07-05 00:00:00+07:00")]), 0.0)

    def test_to_canonical_drops_records_outside_hanoi_bounding_box(self):
        """Bản ghi ngoài Bounding Box Hà Nội bị lọc TRƯỚC khi canonicalize."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:00:00+07:00", "2025-07-04T22:00:00+07:00"],
            parameters=["pm25", "pm25"],
            values=[10.0, 999.0],
            lats=[self.STATION_LAT, self.ALBUQUERQUE_LAT],
            lons=[self.STATION_LON, self.ALBUQUERQUE_LON],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertEqual(len(df_out), 1)
        self.assertAlmostEqual(float(df_out["pm25"].iloc[0]), 10.0, places=6)

    def test_to_canonical_fails_loud_when_every_record_is_out_of_bounds(self):
        """Không còn bản ghi nào trong bbox -> ValueError, KHÔNG trả về DataFrame rỗng."""
        df_raw = self._raw_frame(
            datetimes=["2025-07-04T22:00:00+07:00"],
            parameters=["pm25"],
            values=[10.0],
            lats=[self.ALBUQUERQUE_LAT],
            lons=[self.ALBUQUERQUE_LON],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                self._adapter(tmp_dir).to_canonical(df_raw)

    def test_to_canonical_sorts_chronologically_regardless_of_input_order(self):
        """Đầu ra luôn tăng dần theo thời gian bất kể thứ tự dòng thô."""
        df_raw = self._raw_frame(
            datetimes=[
                "2025-07-05T01:00:00+07:00",
                "2025-07-04T23:00:00+07:00",
                "2025-07-04T22:00:00+07:00",
            ],
            parameters=["pm25", "pm25", "pm25"],
            values=[33.0, 32.0, 31.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            df_out = self._adapter(tmp_dir).to_canonical(df_raw)

        self.assertTrue(df_out["timestamp"].is_monotonic_increasing)
        self.assertEqual(
            df_out["timestamp"].tolist(),
            [
                pd.Timestamp("2025-07-04 22:00:00+07:00"),
                pd.Timestamp("2025-07-04 23:00:00+07:00"),
                pd.Timestamp("2025-07-05 01:00:00+07:00"),
            ],
        )

    def test_to_canonical_is_deterministic_across_repeated_runs(self):
        """Cùng đầu vào -> cùng đầu ra tuyệt đối (không phụ thuộc thời gian chạy)."""
        df_raw = self._raw_frame(
            datetimes=[
                "2025-07-04T22:10:00+07:00",
                "2025-07-04T22:40:00+07:00",
                "2025-07-04T23:05:00+07:00",
            ],
            parameters=["pm25", "pm25", "pm10"],
            values=[30.0, 40.0, 77.0],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            adapter = self._adapter(tmp_dir)
            first = adapter.to_canonical(df_raw)
            second = adapter.to_canonical(df_raw)

        pd.testing.assert_frame_equal(first, second)

    def test_to_canonical_does_not_mutate_the_input_dataframe(self):
        """Adapter phải tôn trọng nguyên trạng DataFrame thô (hợp đồng bất biến)."""
        df_raw = self._raw_frame(
            datetimes=[
                "2025-07-04T22:10:00+07:00",
                "2025-07-04T22:40:00+07:00",
            ],
            parameters=["pm25", "pm10"],
            values=[30.0, 60.0],
        )
        before = df_raw.copy(deep=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            self._adapter(tmp_dir).to_canonical(df_raw)

        pd.testing.assert_frame_equal(df_raw, before)


if __name__ == "__main__":
    unittest.main()
