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
import gzip
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from src.data_collection import (
    HANOI_BBOX,
    CANONICAL_TIMEZONE,
    HANOI_OPENAQ_HISTORICAL_LOCATION_ID,
    STATION_OPENAQ_HANOI,
    STATION_OPENAQ_7441,
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

    def test_airnow_adapter_canonicalizes_new_mirror_schema_without_nowcast(self):
        """New exports use Date (LT)/Raw Conc.; NowCast is not an observation."""
        import os
        import tempfile
        from src.data_collection import AirNowDOSAdapter

        content = (
            "Site,Parameter,Date (LT),NowCast Conc.,Raw Conc.,QC Name\n"
            "Hanoi,PM2.5 - Principal,2022-01-01 01:00 AM,99.9,50.0,Valid\n"
            "Hanoi,PM2.5 - Principal,2022-01-01 02:00 AM,88.8,-999,Missing\n"
            "Hanoi,PM2.5 - Principal,2022-01-01 03:00 PM,77.7,Invalid,Invalid\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            frame = AirNowDOSAdapter(csv_path=tmp_path).load_and_canonicalize()
            self.assertEqual(frame["pm25"].iloc[0], 50.0)
            self.assertTrue(np.isnan(frame["pm25"].iloc[1]))
            self.assertTrue(np.isnan(frame["pm25"].iloc[2]))
            self.assertTrue(frame["pm10"].isna().all())
            self.assertEqual(frame["station_id"].nunique(), 1)
            self.assertEqual(str(frame["timestamp"].dt.tz), CANONICAL_TIMEZONE)
            self.assertEqual(frame["timestamp"].iloc[2].hour, 15)
        finally:
            os.remove(tmp_path)

    def test_airnow_adapter_enforces_qc_name_unit_duration_and_conflicts(self):
        """AirNowDOSAdapter must nullify non-Valid QC, bad units/durations, and conflicting YTD/MTD duplicates."""
        import os
        import tempfile
        from src.data_collection import AirNowDOSAdapter

        ytd_content = (
            "Site,Parameter,Date (LT),Year,Month,Day,Hour,NowCast Conc.,Raw Conc.,Conc. Unit,Duration,QC Name\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 03:00 PM,2023,11,7,15,25.0,25.0,UG/M3,1 Hr,Valid\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 04:00 PM,2023,11,7,16,30.0,30.0,UG/M3,1 Hr,Invalid\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 05:00 PM,2023,11,7,17,22.0,22.0,UG/M3,1 Hr,Valid\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 06:00 PM,2023,11,7,18,18.0,18.0,PPB,1 Hr,Valid\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 07:00 PM,2023,11,7,19,19.0,19.0,UG/M3,24 Hr,Valid\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 08:00 PM,2023,11,7,20,21.0,21.0,UG/M3,1 Hr,Suspect\n"
        )
        mtd_content = (
            "Site,Parameter,Date (LT),Year,Month,Day,Hour,NowCast Conc.,Raw Conc.,Conc. Unit,Duration,QC Name\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 03:00 PM,2023,11,7,15,25.0,25.0,UG/M3,1 Hr,Valid\n"
            "Hanoi,PM2.5 - Principal,2023-11-07 05:00 PM,2023,11,7,17,15.0,15.0,UG/M3,1 Hr,Valid\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, suffix="_YTD.csv") as f1, \
             tempfile.NamedTemporaryFile("w", delete=False, suffix="_MTD.csv") as f2:
            f1.write(ytd_content)
            f2.write(mtd_content)
            p1, p2 = f1.name, f2.name
        try:
            frame = AirNowDOSAdapter().load_and_canonicalize(
                [p1, p2], include_qc_columns=True
            )
            self.assertEqual(len(frame), 6)
            # 15:00 identical valid duplicate across YTD/MTD -> kept as 25.0
            self.assertEqual(frame.loc[0, "pm25"], 25.0)
            self.assertEqual(frame.loc[0, "qc_reason"], "valid")
            # 16:00 numeric 30.0 but QC Name == Invalid -> NaN
            self.assertTrue(np.isnan(frame.loc[1, "pm25"]))
            self.assertEqual(frame.loc[1, "qc_reason"], "qc_invalid")
            # 17:00 conflicting valid duplicate (22.0 vs 15.0) -> NaN (never picked arbitrarily)
            self.assertTrue(np.isnan(frame.loc[2, "pm25"]))
            self.assertEqual(frame.loc[2, "qc_reason"], "conflicting_duplicate")
            # 18:00 invalid unit PPB -> NaN
            self.assertTrue(np.isnan(frame.loc[3, "pm25"]))
            self.assertEqual(frame.loc[3, "qc_reason"], "invalid_unit")
            # 19:00 invalid duration 24 Hr -> NaN
            self.assertTrue(np.isnan(frame.loc[4, "pm25"]))
            self.assertEqual(frame.loc[4, "qc_reason"], "invalid_duration")
            # 20:00 QC Name == Suspect -> NaN
            self.assertTrue(np.isnan(frame.loc[5, "pm25"]))
            self.assertEqual(frame.loc[5, "qc_reason"], "qc_suspect")

            qc_summary = frame.attrs["qc_summary"]
            self.assertEqual(qc_summary["identical_duplicate_hours"], 1)
            self.assertEqual(qc_summary["conflicting_duplicate_hours"], 1)
        finally:
            for p in (p1, p2):
                if os.path.exists(p):
                    os.remove(p)

    def test_openaq_7441_historical_station_resolves_separately_within_hanoi(self):
        """OpenAQ historical location 7441 resolves to VN003_HANOI_OPENAQ_7441 without coalescing into VN001 or VN002."""
        sid, loc, coords = resolve_station_metadata("openaq", HANOI_OPENAQ_HISTORICAL_LOCATION_ID)
        self.assertEqual(sid, STATION_OPENAQ_7441)
        self.assertNotIn(sid, {STATION_OPENAQ_HANOI, STATION_AIRNOW_HANOI})
        self.assertIn("7441", loc)
        df_7441 = pd.DataFrame({
            "station_id": [STATION_OPENAQ_7441],
            "latitude": [coords[0]],
            "longitude": [coords[1]],
            "pm25": [42.0],
        })
        assert_canonical_within_hanoi(df_7441)

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


def _make_gzip_csv(content_str: str) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(content_str.encode("utf-8"))
    return buf.getvalue()


class TestOpenAQS3AcquisitionFailClosed(unittest.TestCase):
    """Regression tests for F-03: S3 acquisition fail-closed and cache integrity."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_dir = Path(self.temp_dir.name) / "raw"
        self.interim_dir = Path(self.temp_dir.name) / "interim"
        self.raw_dir.mkdir(parents=True)
        self.interim_dir.mkdir(parents=True)
        self.adapter = OpenAQAdapter(
            location_id=HANOI_OPENAQ_HISTORICAL_LOCATION_ID,
            raw_dir=self.raw_dir,
            interim_dir=self.interim_dir,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_one_s3_key_fails_triggers_fail_closed(self):
        """F-03: When 1 out of multiple S3 keys fails, acquisition fails-closed without saving cache."""
        keys = ["file1.csv.gz", "file2.csv.gz"]
        df1 = pd.DataFrame({"datetime": ["2024-01-01T00:00:00Z"], "value": [25.0], "parameter": ["pm25"]})

        with patch.object(self.adapter, "_list_s3_keys", return_value=keys):
            with patch.object(
                self.adapter,
                "_fetch_single_s3_file",
                side_effect=[
                    ("file1.csv.gz", df1, None),
                    ("file2.csv.gz", None, "HTTP status 503"),
                ],
            ):
                with self.assertRaisesRegex(RuntimeError, "FAIL-CLOSED"):
                    self.adapter.fetch_raw_data(raw_output_name="test_raw.parquet", max_workers=1)

        # Crucial check: No partial cache file was written
        out_file = self.raw_dir / "test_raw.parquet"
        self.assertFalse(out_file.exists())

    def test_all_s3_keys_fail_raises_runtime_error(self):
        """F-03: When all S3 keys fail, RuntimeError is raised and no file is created."""
        keys = ["file1.csv.gz"]
        with patch.object(self.adapter, "_list_s3_keys", return_value=keys):
            with patch.object(
                self.adapter,
                "_fetch_single_s3_file",
                return_value=("file1.csv.gz", None, "ConnectionRefusedError"),
            ):
                with self.assertRaisesRegex(RuntimeError, "FAIL-CLOSED"):
                    self.adapter.fetch_raw_data(raw_output_name="test_raw.parquet", max_workers=1)
        self.assertFalse((self.raw_dir / "test_raw.parquet").exists())

    def test_retry_succeeds_after_transient_failure(self):
        """F-03: Bounded retry recovers from transient error on first attempt."""
        csv_bytes = _make_gzip_csv("datetime,value,parameter\n2024-01-01T00:00:00Z,30.0,pm25\n")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = csv_bytes
        mock_resp.__enter__.return_value = mock_resp

        call_count = 0
        def fake_urlopen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise urllib.error.URLError("Transient network glitch")
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            key, df, err = self.adapter._fetch_single_s3_file(
                "test.csv.gz", max_retries=3, backoff_seconds=0.01
            )
            self.assertIsNone(err)
            self.assertIsNotNone(df)
            self.assertEqual(len(df), 1)
            self.assertEqual(call_count, 2)

    def test_retry_exhausted_returns_error_tuple(self):
        """F-03: When all retries are exhausted, error tuple is returned with details."""
        def fake_urlopen(*args, **kwargs):
            raise urllib.error.URLError("Persistent timeout")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            key, df, err = self.adapter._fetch_single_s3_file(
                "timeout.csv.gz", max_retries=3, backoff_seconds=0.01
            )
            self.assertIsNone(df)
            self.assertIn("Persistent timeout", str(err))

    def test_corrupt_payload_handled(self):
        """F-03: Corrupt (non-gzip) bytes are caught and handled safely."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"NOT_A_GZIP_FILE_JUNK"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            key, df, err = self.adapter._fetch_single_s3_file(
                "corrupt.csv.gz", max_retries=2, backoff_seconds=0.01
            )
            self.assertIsNone(df)
            self.assertIn("BadGzipFile", str(err))

    def test_valid_empty_payload_handled(self):
        """F-03: Empty valid CSV gzip payload returns empty dataframe without crashing."""
        csv_bytes = _make_gzip_csv("")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = csv_bytes
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            key, df, err = self.adapter._fetch_single_s3_file("empty.csv.gz", max_retries=1)
            self.assertIsNone(err)
            self.assertIsNotNone(df)
            self.assertTrue(df.empty)

    def test_hash_mismatch_fails_closed(self):
        """F-03: Download succeeds on fresh path, but snapshot hash mismatch fails closed without creating cache."""
        cache_path = self.raw_dir / "test_raw_fresh.parquet"
        dummy_df = pd.DataFrame({"datetime": ["2024-01-01T00:00:00Z"], "value": [10.0]})

        keys = ["file1.csv.gz"]
        with patch.object(self.adapter, "_list_s3_keys", return_value=keys):
            with patch.object(
                self.adapter,
                "_fetch_single_s3_file",
                return_value=("file1.csv.gz", dummy_df, None),
            ):
                with self.assertRaisesRegex(RuntimeError, "FAIL-CLOSED: Mã băm"):
                    self.adapter.fetch_raw_data(
                        raw_output_name="test_raw_fresh.parquet",
                        force_reload=True,
                        expected_sha256="expected_pinned_hash_that_never_matches",
                    )
        self.assertFalse(cache_path.exists(), "Invalid snapshot must never be written to canonical cache path")
        self.assertEqual(list(self.raw_dir.glob("*.tmp*")), [], "Temporary file must be cleaned up on error")

    def test_existing_valid_cache_preserved_when_reload_fails_hash_check(self):
        """F-03: Pre-existing valid cache content and SHA-256 remain untouched if reload fails hash verification."""
        cache_path = self.raw_dir / "preserved_cache.parquet"
        original_df = pd.DataFrame({"datetime": ["2024-01-01T00:00:00Z"], "value": [10.0]})
        original_df.to_parquet(cache_path, index=False, engine="pyarrow", compression="snappy")
        original_bytes = cache_path.read_bytes()
        original_sha256 = hashlib.sha256(original_bytes).hexdigest()

        tampered_download_df = pd.DataFrame({"datetime": ["2024-01-01T00:00:00Z"], "value": [999.0]})
        keys = ["file1.csv.gz"]
        with patch.object(self.adapter, "_list_s3_keys", return_value=keys):
            with patch.object(
                self.adapter,
                "_fetch_single_s3_file",
                return_value=("file1.csv.gz", tampered_download_df, None),
            ):
                with self.assertRaisesRegex(RuntimeError, "FAIL-CLOSED: Mã băm"):
                    self.adapter.fetch_raw_data(
                        raw_output_name="preserved_cache.parquet",
                        force_reload=True,
                        expected_sha256=original_sha256,
                    )

        self.assertTrue(cache_path.exists())
        after_bytes = cache_path.read_bytes()
        self.assertEqual(hashlib.sha256(after_bytes).hexdigest(), original_sha256)
        self.assertEqual(after_bytes, original_bytes)
        df_after = pd.read_parquet(cache_path)
        self.assertEqual(df_after["value"].tolist(), [10.0])
        self.assertEqual(list(self.raw_dir.glob("*.tmp*")), [])

    def test_expected_s3_key_count_mismatch_fails_closed(self):
        """F-03: Mismatched S3 key count fails closed before downloading or overwriting existing cache."""
        cache_path = self.raw_dir / "key_count_cache.parquet"
        original_df = pd.DataFrame({"datetime": ["2024-01-01T00:00:00Z"], "value": [25.0]})
        original_df.to_parquet(cache_path, index=False, engine="pyarrow", compression="snappy")
        original_sha256 = hashlib.sha256(cache_path.read_bytes()).hexdigest()

        keys = ["file1.csv.gz", "file2.csv.gz"]
        with patch.object(self.adapter, "_list_s3_keys", return_value=keys):
            with patch.object(self.adapter, "_fetch_single_s3_file") as mock_fetch:
                with self.assertRaisesRegex(RuntimeError, "FAIL-CLOSED: Số lượng tệp S3"):
                    self.adapter.fetch_raw_data(
                        raw_output_name="key_count_cache.parquet",
                        force_reload=True,
                        expected_s3_key_count=3,
                    )
                mock_fetch.assert_not_called()

        self.assertEqual(hashlib.sha256(cache_path.read_bytes()).hexdigest(), original_sha256)
        self.assertEqual(list(self.raw_dir.glob("*.tmp*")), [])

    def test_valid_cache_reused_without_network(self):
        """F-03: Valid cache matching expected hash is reused without making any S3 calls."""
        cache_path = self.raw_dir / "valid_cache.parquet"
        dummy_df = pd.DataFrame({"datetime": ["2024-01-01T00:00:00Z"], "value": [10.0]})
        dummy_df.to_parquet(cache_path, index=False)
        actual_hash = hashlib.sha256(cache_path.read_bytes()).hexdigest()

        with patch.object(self.adapter, "_list_s3_keys") as mock_list:
            df_out, path_out = self.adapter.fetch_raw_data(
                raw_output_name="valid_cache.parquet",
                force_reload=False,
                expected_sha256=actual_hash,
            )
            self.assertEqual(len(df_out), 1)
            self.assertEqual(path_out, cache_path)
            # S3 list was never called
            mock_list.assert_not_called()

    def test_atomic_write_leaves_no_temp_file(self):
        """F-03: Fetch raw data leaves no leftover temporary files in raw directory."""
        keys = ["f1.csv.gz"]
        df_valid = pd.DataFrame({"datetime": ["2024-01-01T00:00:00Z"], "value": [15.0], "latitude": [21.0], "longitude": [105.8]})
        with patch.object(self.adapter, "_list_s3_keys", return_value=keys):
            with patch.object(
                self.adapter,
                "_fetch_single_s3_file",
                return_value=("f1.csv.gz", df_valid, None),
            ):
                df_res, p_res = self.adapter.fetch_raw_data(
                    raw_output_name="atomic_test.parquet", force_reload=True
                )
                self.assertTrue(p_res.exists())
                # Check that zero .tmp files exist
                tmp_files = list(self.raw_dir.glob("*.tmp*"))
                self.assertEqual(len(tmp_files), 0)

    def test_baseline_location_fetch_unaffected(self):
        """F-03: Baseline OpenAQ location 4946811 default path is preserved."""
        baseline_adapter = OpenAQAdapter(
            location_id=4946811, raw_dir=self.raw_dir, interim_dir=self.interim_dir
        )
        keys = ["b1.csv.gz"]
        df_valid = pd.DataFrame({"datetime": ["2025-07-04T00:00:00Z"], "value": [20.0]})
        with patch.object(baseline_adapter, "_list_s3_keys", return_value=keys):
            with patch.object(
                baseline_adapter,
                "_fetch_single_s3_file",
                return_value=("b1.csv.gz", df_valid, None),
            ):
                _, p = baseline_adapter.fetch_raw_data(force_reload=True)
                self.assertEqual(p.name, "openaq_raw_4946811.parquet")


if __name__ == "__main__":
    unittest.main()
