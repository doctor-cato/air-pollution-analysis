
import datetime
import json
import unittest
import numpy as np
import pandas as pd

from src.data_collection import (
    HANOI_BBOX,
    CANONICAL_TIMEZONE,
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
    OpenMeteoAdapter,
)

EXPECTED_HOURLY_UNITS = {
    provider_field: unit for provider_field, unit in WEATHER_EXPECTED_UNITS.values()
}


class TestDataCollectionPipeline(unittest.TestCase):
    def test_geographic_filtering_keeps_hanoi_and_drops_albuquerque(self):
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
        self.assertTrue(np.isnan(clean_air_quality_values(-999)))
        self.assertTrue(np.isnan(clean_air_quality_values(-999.0)))
        self.assertTrue(np.isnan(clean_air_quality_values(-9999)))
        self.assertTrue(np.isnan(clean_air_quality_values(-9999.0)))
        self.assertTrue(np.isnan(clean_air_quality_values(-1.5)))
        self.assertTrue(np.isnan(clean_air_quality_values(np.nan)))
        self.assertTrue(np.isnan(clean_air_quality_values(None)))
        self.assertTrue(np.isnan(clean_air_quality_values("invalid")))

    def test_valid_zero_preserved(self):
        val = clean_air_quality_values(0.0)
        self.assertEqual(val, 0.0)
        self.assertFalse(np.isnan(val))

        val_int = clean_air_quality_values(0)
        self.assertEqual(val_int, 0.0)
        self.assertFalse(np.isnan(val_int))

    def test_positive_values_preserved(self):
        self.assertEqual(clean_air_quality_values(35.5), 35.5)
        self.assertEqual(clean_air_quality_values(120.0), 120.0)

    def test_station_id_mapping_and_rejection_of_location_2178(self):
        sid, loc, coords = resolve_station_metadata("openaq", 4946811)
        self.assertEqual(sid, STATION_OPENAQ_HANOI)
        self.assertEqual(loc, "556 Nguyễn Văn Cừ")
        self.assertEqual(coords, (21.0491, 105.8831))

        with self.assertRaises(ValueError) as ctx:
            resolve_station_metadata("openaq", 2178)
        self.assertIn("loại bỏ/disqualified", str(ctx.exception))

        sid_air, loc_air, coords_air = resolve_station_metadata("airnow", "Hanoi")
        self.assertEqual(sid_air, STATION_AIRNOW_HANOI)
        self.assertEqual(loc_air, "US Diplomatic Post: Hanoi")
        self.assertEqual(coords_air, (21.0215, 105.8184))

    def test_canonical_assertion_passes_for_hanoi_and_fails_for_out_of_bounds(self):
        df_valid = pd.DataFrame({
            "station_id": [STATION_OPENAQ_HANOI],
            "latitude": [21.0491],
            "longitude": [105.8831],
            "pm25": [45.0],
        })
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
        from src.data_collection import AirNowDOSAdapter
        adapter = AirNowDOSAdapter(csv_path="data/raw/non_existent_airnow.csv")
        with self.assertRaises(FileNotFoundError) as ctx:
            adapter.load_and_canonicalize()
        self.assertIn("AirNow DOS CSV không tồn tại", str(ctx.exception))

    def test_airnow_adapter_canonicalizes_valid_sample(self):
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
            self.assertTrue(np.isnan(df_canonical["pm25"].iloc[1]))
            self.assertEqual(df_canonical["pm25"].iloc[2], 0.0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_actual_timestamps_computed_directly_from_dataframe(self):
        ts_range = pd.date_range("2023-05-01 00:00:00+07:00", "2023-05-10 23:00:00+07:00", freq="h")
        df_test = pd.DataFrame({"timestamp": ts_range})
        min_ts = str(df_test["timestamp"].min())
        max_ts = str(df_test["timestamp"].max())
        self.assertEqual(min_ts, "2023-05-01 00:00:00+07:00")
        self.assertEqual(max_ts, "2023-05-10 23:00:00+07:00")

    def test_open_meteo_raw_filename_reflects_date_range(self):
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
        ts_air = pd.date_range("2025-07-03 22:00:00+07:00", "2025-07-04 10:00:00+07:00", freq="h")
        ts_weather = pd.date_range("2025-07-03 00:00:00+07:00", "2025-07-05 00:00:00+07:00", freq="h")

        df_air = pd.DataFrame({"timestamp": ts_air, "pm25": [35.0] * len(ts_air)})
        df_weather = pd.DataFrame({"timestamp": ts_weather, "temperature": [28.0] * len(ts_weather)})

        df_merged = pd.merge(df_air, df_weather, on="timestamp", how="inner")
        self.assertGreater(len(df_merged), 0)
        self.assertEqual(df_merged["timestamp"].min(), ts_air.min())
        self.assertEqual(df_merged["timestamp"].max(), ts_air.max())

    def test_dynamic_sync_window_derivation(self):
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

        self.assertEqual(list(df_canonical.columns), WEATHER_CANONICAL_COLUMNS)

        self.assertIsNotNone(df_canonical["timestamp"].dt.tz)
        self.assertEqual(str(df_canonical["timestamp"].dt.tz), "Asia/Ho_Chi_Minh")

        for col in WEATHER_CANONICAL_COLUMNS[1:]:
            self.assertEqual(df_canonical[col].dtype, np.float64, f"Cột {col} chưa được ép kiểu float64!")

    def test_weather_validation_passes_valid_data(self):
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
        ts_range = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz=CANONICAL_TIMEZONE)

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
        self.assertEqual(report["gap_count"], 1)

    def test_clean_weather_values_handles_disguised_missing_and_valid_zero(self):
        self.assertTrue(np.isnan(clean_weather_values(-999)))
        self.assertTrue(np.isnan(clean_weather_values("-9999")))
        self.assertTrue(np.isnan(clean_weather_values("invalid")))

        self.assertTrue(np.isnan(clean_weather_values(-2.5, "wind_speed")))
        self.assertTrue(np.isnan(clean_weather_values(-1.0, "precipitation")))
        self.assertTrue(np.isnan(clean_weather_values(105.0, "relative_humidity")))

        val_rain = clean_weather_values(0.0, "precipitation")
        self.assertEqual(val_rain, 0.0)
        self.assertFalse(np.isnan(val_rain))

        val_wind = clean_weather_values(0.0, "wind_speed")
        self.assertEqual(val_wind, 0.0)
        self.assertFalse(np.isnan(val_wind))

        self.assertEqual(clean_weather_values(28.5, "temperature"), 28.5)

    def test_open_meteo_adapter_rejects_out_of_bounds_grid_coordinates(self):
        mock_raw_out = {
            "latitude": 35.1353,
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


    def test_weather_station_metadata_resolves_to_hanoi_grid(self):
        sid, loc, coords = resolve_station_metadata("open_meteo", None)
        self.assertEqual(sid, STATION_WEATHER_ERA5)
        self.assertIn("ERA5", loc)
        lat, lon = coords
        self.assertTrue(HANOI_BBOX["lat_min"] <= lat <= HANOI_BBOX["lat_max"])
        self.assertTrue(HANOI_BBOX["lon_min"] <= lon <= HANOI_BBOX["lon_max"])

    def test_open_meteo_default_query_coordinates_are_inside_hanoi_bbox(self):
        lat, lon = WEATHER_QUERY_COORDS
        self.assertTrue(HANOI_BBOX["lat_min"] <= lat <= HANOI_BBOX["lat_max"])
        self.assertTrue(HANOI_BBOX["lon_min"] <= lon <= HANOI_BBOX["lon_max"])

        adapter = OpenMeteoAdapter()
        self.assertEqual(adapter.latitude, lat)
        self.assertEqual(adapter.longitude, lon)

    def test_open_meteo_adapter_rejects_non_hanoi_request_coordinates(self):
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter(latitude=35.1353, longitude=-106.5847)
        self.assertIn("nằm NGOÀI Bounding Box Hà Nội", str(ctx.exception))

    def test_open_meteo_to_canonical_fails_loud_when_response_has_no_coordinates(self):
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


    def test_fetch_raw_data_requires_explicit_window(self):
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
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().fetch_raw_data(start_date="", end_date="")
        self.assertIn("là bắt buộc", str(ctx.exception))

    def test_request_url_encodes_requested_dynamic_window(self):
        url = OpenMeteoAdapter().build_request_url("2025-07-03", "2026-07-15")
        self.assertIn("start_date=2025-07-03", url)
        self.assertIn("end_date=2026-07-15", url)
        self.assertIn("wind_speed_unit=ms", url)
        self.assertIn("archive-api.open-meteo.com", url)


    def test_weather_validation_rejects_naive_timestamp(self):
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
        adapter = OpenMeteoAdapter()
        df = adapter.to_canonical(_mock_weather_payload(), validate=False)
        report = validate_weather_canonical(df)
        self.assertEqual(report["timezone"], "Asia/Ho_Chi_Minh")
        self.assertEqual(str(df["timestamp"].dt.tz), CANONICAL_TIMEZONE)


    def test_is_sentinel_code_keeps_valid_zero(self):
        self.assertTrue(is_sentinel_code(-999))
        self.assertTrue(is_sentinel_code(-9999.0))
        self.assertTrue(is_sentinel_code("-999.0"))
        self.assertFalse(is_sentinel_code(0.0))
        self.assertFalse(is_sentinel_code(0))
        self.assertFalse(is_sentinel_code(None))
        self.assertFalse(is_sentinel_code(float("nan")))

    def test_summarize_weather_cleaning_separates_null_reasons(self):
        raw = {"temperature": [25.0, -999.0, 999.0, 0.0, None, "abc"]}
        cleaned = {
            "temperature": [
                clean_weather_values(v, "temperature") for v in raw["temperature"]
            ]
        }
        stats = summarize_weather_cleaning(raw, cleaned)["temperature"]
        self.assertEqual(stats["disguised_missing"], 1)
        self.assertEqual(stats["out_of_bounds"], 1)
        self.assertEqual(stats["unparseable"], 1)
        self.assertEqual(sum(stats.values()), 3)

    def test_to_canonical_preserves_zero_and_nulls_sentinels(self):
        payload = _mock_weather_payload(
            temperature=[0.0, -999.0, 25.5],
            precipitation=[0.0, 0.0, 1.2],
        )
        df = OpenMeteoAdapter().to_canonical(payload, validate=False)

        self.assertEqual(df["temperature"].iloc[0], 0.0)
        self.assertTrue(np.isnan(df["temperature"].iloc[1]))
        self.assertEqual(df["temperature"].iloc[2], 25.5)
        self.assertEqual(list(df["precipitation"][:2]), [0.0, 0.0])

        cleaning = df.attrs["weather_cleaning"]
        self.assertEqual(cleaning["temperature"]["disguised_missing"], 1)
        self.assertEqual(cleaning["temperature"]["out_of_bounds"], 0)
        self.assertEqual(cleaning["precipitation"]["disguised_missing"], 0)

    def test_validation_surfaces_values_nulled_by_cleaning(self):
        payload = _mock_weather_payload(temperature=[25.0, 999.0, 26.0])
        df = OpenMeteoAdapter().to_canonical(payload, validate=False)
        self.assertTrue(np.isnan(df["temperature"].iloc[1]))

        report = validate_weather_canonical(df)
        self.assertEqual(report["cleaning_totals"]["out_of_bounds"], 1)
        self.assertTrue(any("vi phạm giới hạn" in w for w in report["warnings"]))


    def test_weather_validation_detects_schema_violation(self):
        ts_range = pd.date_range("2025-07-03 00:00:00+07:00", periods=3, freq="h")
        df_bad = pd.DataFrame({"timestamp": ts_range, "temperature": [25.0, 25.5, 26.0]})
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(df_bad)
        self.assertIn("thiếu cột bắt buộc", str(ctx.exception))

    def test_weather_validation_detects_non_monotonic_timestamps(self):
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
        pd.testing.assert_frame_equal(df_unsorted, before)

    def test_weather_validation_fails_when_missing_exceeds_threshold(self):
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

        report = validate_weather_canonical(df_missing, max_missing_pct=50.0)
        self.assertEqual(report["max_missing_pct"], 25.0)

    def test_weather_validation_reports_gap_as_warning_not_silent_pass(self):
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
        df = OpenMeteoAdapter().to_canonical(_mock_weather_payload(), validate=False)
        snapshot = df.copy(deep=True)
        validate_weather_canonical(df)
        pd.testing.assert_frame_equal(df, snapshot)
        self.assertEqual(list(df.columns), WEATHER_CANONICAL_COLUMNS)


    def test_expected_units_constant_maps_all_six_canonical_variables(self):
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
        validated = validate_open_meteo_hourly_units(_mock_weather_payload())
        self.assertEqual(
            validated,
            {var: unit for var, (_field, unit) in WEATHER_EXPECTED_UNITS.items()},
        )

    def test_hourly_units_helper_rejects_missing_hourly_units_block(self):
        payload = _mock_weather_payload()
        del payload["hourly_units"]
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(payload)
        self.assertIn("hourly_units", str(ctx.exception))

    def test_hourly_units_helper_rejects_missing_single_variable_unit(self):
        units = dict(EXPECTED_HOURLY_UNITS)
        del units["surface_pressure"]
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(_mock_weather_payload(hourly_units=units))
        message = str(ctx.exception)
        self.assertIn("thiếu khai báo đơn vị", message)
        self.assertIn("surface_pressure", message)

    def test_hourly_units_helper_rejects_wrong_unit_value(self):
        units = dict(EXPECTED_HOURLY_UNITS)
        units["temperature_2m"] = "°F"
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(_mock_weather_payload(hourly_units=units))
        message = str(ctx.exception)
        self.assertIn("temperature", message)
        self.assertIn("°F", message)
        self.assertIn("°C", message)

    def test_hourly_units_helper_rejects_unknown_unit_without_silent_conversion(self):
        units = dict(EXPECTED_HOURLY_UNITS)
        units["wind_speed_10m"] = "km/h"
        with self.assertRaises(ValueError) as ctx:
            validate_open_meteo_hourly_units(_mock_weather_payload(hourly_units=units))
        self.assertIn("km/h", str(ctx.exception))

    def test_hourly_units_helper_is_read_only(self):
        payload = _mock_weather_payload()
        snapshot = json.loads(json.dumps(payload))
        validate_open_meteo_hourly_units(payload)
        self.assertEqual(payload, snapshot)

    def test_to_canonical_passes_with_correct_hourly_units(self):
        df = OpenMeteoAdapter().to_canonical(_mock_weather_payload(), validate=True)
        self.assertEqual(list(df.columns), WEATHER_CANONICAL_COLUMNS)
        self.assertEqual(str(df["timestamp"].dt.tz), CANONICAL_TIMEZONE)

    def test_to_canonical_fails_when_hourly_units_missing(self):
        payload = _mock_weather_payload()
        del payload["hourly_units"]
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().to_canonical(payload, validate=False)
        self.assertIn("hourly_units", str(ctx.exception))

    def test_to_canonical_fails_when_single_unit_is_wrong(self):
        payload = _mock_weather_payload()
        payload["hourly_units"]["precipitation"] = "inch"
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().to_canonical(payload, validate=False)
        message = str(ctx.exception)
        self.assertIn("precipitation", message)
        self.assertIn("inch", message)
        self.assertIn("mm", message)

    def test_to_canonical_fails_when_single_unit_is_absent(self):
        payload = _mock_weather_payload()
        del payload["hourly_units"]["relative_humidity_2m"]
        with self.assertRaises(ValueError) as ctx:
            OpenMeteoAdapter().to_canonical(payload, validate=False)
        message = str(ctx.exception)
        self.assertIn("thiếu khai báo đơn vị", message)
        self.assertIn("relative_humidity_2m", message)


    def _valid_weather_frame(self, timestamps) -> pd.DataFrame:
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
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz=CANONICAL_TIMEZONE)
        report = validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["timezone"], CANONICAL_TIMEZONE)
        self.assertEqual(report["utc_offset_hours"], 7.0)

    def test_validation_rejects_fixed_offset_0700_timezone(self):
        ts = pd.date_range(
            "2025-07-03 00:00:00", periods=3, freq="h", tz=datetime.timezone(datetime.timedelta(hours=7))
        )
        self.assertEqual(ts[0].utcoffset(), datetime.timedelta(hours=7))
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn(CANONICAL_TIMEZONE, str(ctx.exception))
        self.assertIn("fixed offset", str(ctx.exception))

    def test_validation_rejects_utc_offset_alias_timezone(self):
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz="Etc/GMT-7")
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn(CANONICAL_TIMEZONE, str(ctx.exception))

    def test_validation_rejects_other_iana_timezone_with_same_offset(self):
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h", tz="Asia/Singapore")
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn(CANONICAL_TIMEZONE, str(ctx.exception))

    def test_validation_rejects_naive_timestamp_via_timezone_layer(self):
        ts = pd.date_range("2025-07-03 00:00:00", periods=3, freq="h")
        with self.assertRaises(ValueError) as ctx:
            validate_weather_canonical(self._valid_weather_frame(ts))
        self.assertIn("tz-aware", str(ctx.exception))

    def test_canonical_timezone_key_helper_distinguishes_named_zone_from_fixed_offset(self):
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
        payload = _mock_weather_payload(n_hours=2)
        payload["hourly"]["time"] = ["2025-07-03T00:00:00+07:00", "2025-07-03T01:00:00+07:00"]
        df = OpenMeteoAdapter().to_canonical(payload, validate=True)
        self.assertEqual(str(df["timestamp"].dt.tz), CANONICAL_TIMEZONE)
        self.assertTrue(is_canonical_timezone(df["timestamp"].dtype.tz))


def _mock_weather_payload(n_hours: int = 3, hourly_units=None, **overrides) -> dict:
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


if __name__ == "__main__":
    unittest.main()
