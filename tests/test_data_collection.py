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
    clean_air_quality_values,
    filter_hanoi_bounds,
    assert_canonical_within_hanoi,
    validate_canonical_uniqueness,
    resolve_station_metadata,
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


if __name__ == "__main__":
    unittest.main()
