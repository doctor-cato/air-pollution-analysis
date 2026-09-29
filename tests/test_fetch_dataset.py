"""
Unit tests cho `scripts/fetch_dataset.py` — cơ chế tái tạo tập dữ liệu có kiểm chứng.

Nguyên tắc:
- KHÔNG gọi mạng. Mọi fixture là DataFrame tổng hợp ghi ra thư mục tạm.
- Tất định: cùng đầu vào -> cùng kết quả so khớp.
- Mục tiêu là bảo vệ HỢP ĐỒNG so khớp nội dung, không phải chi tiết hiển thị.

Hai chế độ của script được kiểm thử:
1. `summarise_interim_on_disk()` — chế độ `--skip-fetch`, dẫn xuất bản tóm tắt từ
   `data/interim/*.parquet` rồi đối chiếu với `metadata.json` mà không cần mạng.
2. `compare_with_metadata()` — hàm so khớp thuần túy, bao gồm việc bỏ qua các mục
   không dẫn xuất được (ví dụ số bản ghi thô trong chế độ `--skip-fetch`).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.fetch_dataset import compare_with_metadata, summarise_interim_on_disk

# Fixture nhỏ, tự nhất quán: 3 mốc giờ liên tục. metadata.json sinh ra từ chính fixture
# này nên các giá trị phải khớp tuyệt đối — nếu lệch, so khớp sẽ báo đúng là KHAC.
SAMPLE_ROWS = 3
SAMPLE_AIR_MIN = "2025-07-03 22:00:00+07:00"
SAMPLE_AIR_MAX = "2025-07-04 00:00:00+07:00"


def _write_interim(directory: Path) -> None:
    """Ghi hai tệp canonical tối thiểu, đủ để dẫn xuất bản tóm tắt."""
    timestamps = pd.date_range("2025-07-03 22:00", periods=SAMPLE_ROWS, freq="h", tz="Asia/Ho_Chi_Minh")
    air = pd.DataFrame({
        "timestamp": timestamps,
        "station_id": ["VN001_HANOI_556_NGUYEN_VAN_CU"] * SAMPLE_ROWS,
        "location": ["556 Nguyễn Văn Cừ"] * SAMPLE_ROWS,
        "pm25": [30.0, 31.0, 32.0],
        "pm10": [60.0, 61.0, 62.0],
    })
    weather = pd.DataFrame({
        "timestamp": timestamps,
        "temperature": [28.0, 28.5, 29.0],
        "relative_humidity": [80.0, 79.0, 78.0],
        "wind_speed": [2.0, 2.1, 2.2],
        "wind_direction": [120.0, 121.0, 122.0],
        "precipitation": [0.0, 0.0, 0.1],
        "surface_pressure": [1005.0, 1005.1, 1005.2],
    })
    air.to_parquet(directory / "air_quality_canonical.parquet", index=False)
    weather.to_parquet(directory / "weather_canonical.parquet", index=False)


def _write_metadata(path: Path, *, canonical: int = SAMPLE_ROWS, overlap: int = SAMPLE_ROWS,
                    coverage: float = 100.0, raw_records: int = 999) -> None:
    """Ghi metadata.json tối thiểu chứa khối collection_pipeline_execution."""
    payload = {
        "collection_pipeline_execution": {
            "openaq_ingestion": {
                "raw_records_total": raw_records,
                "canonical_records": canonical,
                "actual_source_coverage": {
                    "actual_min_timestamp": SAMPLE_AIR_MIN,
                    "actual_max_timestamp": SAMPLE_AIR_MAX,
                },
            },
            "open_meteo_ingestion": {"canonical_records": SAMPLE_ROWS},
            "temporal_integration": {
                "overlap_records": overlap,
                "air_quality_coverage_pct": coverage,
            },
        }
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class TestFetchDatasetSkipFetch(unittest.TestCase):
    """Chế độ `--skip-fetch`: kiểm chứng dữ liệu trên đĩa mà không cần mạng."""

    def test_summarise_reads_canonical_files_without_network(self):
        """Bản tóm tắt phải dẫn xuất được từ parquet, không gọi bất kỳ lời gọi mạng nào."""
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp) / "interim"
            interim.mkdir()
            _write_interim(interim)

            with patch("urllib.request.urlopen", side_effect=AssertionError("network called!")):
                summary = summarise_interim_on_disk(interim)

        self.assertEqual(summary["openaq"]["canonical_records"], SAMPLE_ROWS)
        self.assertEqual(summary["open_meteo"]["canonical_records"], SAMPLE_ROWS)
        self.assertEqual(summary["temporal_integration"]["overlap_records"], SAMPLE_ROWS)
        self.assertEqual(summary["temporal_integration"]["air_quality_coverage_pct"], 100.0)
        self.assertFalse(summary["temporal_integration"]["row_explosion_detected"])

    def test_summarise_marks_raw_record_count_as_underivable(self):
        """
        Số bản ghi thô cần tệp thô nên phải là None — đây là hợp đồng để so khớp bỏ qua,
        KHÔNG được bịa ra số từ dữ liệu canonical.
        """
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp) / "interim"
            interim.mkdir()
            _write_interim(interim)
            summary = summarise_interim_on_disk(interim)

        self.assertIsNone(summary["openaq"]["raw_records_total"])

    def test_summarise_fails_loud_when_canonical_files_missing(self):
        """Thiếu tệp canonical thì phải ném lỗi rõ ràng, không im lặng trả về rỗng."""
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with self.assertRaises(FileNotFoundError) as ctx:
                summarise_interim_on_disk(empty)
        self.assertIn("fetch_dataset.py", str(ctx.exception))

    def test_skip_fetch_reports_match_against_metadata(self):
        """metadata khớp với dữ liệu trên đĩa -> báo cáo tất cả mục so sánh được đều OK."""
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp) / "interim"
            interim.mkdir()
            _write_interim(interim)
            metadata = Path(tmp) / "metadata.json"
            _write_metadata(metadata)

            summary = summarise_interim_on_disk(interim)
            with patch("builtins.print"):
                matched = compare_with_metadata(summary, metadata)

        self.assertTrue(matched)

    def test_skip_fetch_detects_canonical_count_drift(self):
        """Số bản ghi canonical lệch so với metadata -> phải báo KHỚP (không báo pass)."""
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp) / "interim"
            interim.mkdir()
            _write_interim(interim)
            metadata = Path(tmp) / "metadata.json"
            _write_metadata(metadata, canonical=SAMPLE_ROWS + 1)

            summary = summarise_interim_on_disk(interim)
            with patch("builtins.print"):
                matched = compare_with_metadata(summary, metadata)

        self.assertFalse(matched)

    def test_skip_fetch_detects_overlap_coverage_regression(self):
        """
        Độ phủ giao thoa sai là lỗi nghiêm trọng nhất (không thể phân tích phía sau),
        nên hàm so khớp phải phát hiện được.
        """
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp) / "interim"
            interim.mkdir()
            _write_interim(interim)
            metadata = Path(tmp) / "metadata.json"
            _write_metadata(metadata, coverage=42.0)

            summary = summarise_interim_on_disk(interim)
            with patch("builtins.print"):
                matched = compare_with_metadata(summary, metadata)

        self.assertFalse(matched)


class TestFetchDatasetCompare(unittest.TestCase):
    """Hàm so khớp thuần túy — không phụ thuộc filesystem ngoài metadata."""

    def _summary(self, *, raw=10, canonical=3, overlap=3, coverage=100.0):
        return {
            "openaq": {
                "raw_records_total": raw,
                "canonical_records": canonical,
                "actual_source_coverage": {
                    "actual_min_timestamp": SAMPLE_AIR_MIN,
                    "actual_max_timestamp": SAMPLE_AIR_MAX,
                },
            },
            "open_meteo": {"canonical_records": SAMPLE_ROWS},
            "temporal_integration": {
                "overlap_records": overlap,
                "air_quality_coverage_pct": coverage,
                "row_explosion_detected": False,
            },
        }

    def test_missing_metadata_is_not_treated_as_failure(self):
        """Không có metadata.json thì bỏ qua kiểm chứng, KHÔNG báo lỗi (fresh clone hợp lệ)."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "khong-ton-tai.json"
            with patch("builtins.print"):
                self.assertTrue(compare_with_metadata(self._summary(), missing))

    def test_underivable_fields_are_skipped_not_failed(self):
        """Trường None ở cả hai vế -> bỏ qua, vẫn coi là khớp."""
        with tempfile.TemporaryDirectory() as tmp:
            metadata = Path(tmp) / "metadata.json"
            _write_metadata(metadata, raw_records=10)
            summary = self._summary(raw=None)
            with patch("builtins.print"):
                self.assertTrue(compare_with_metadata(summary, metadata))

    def test_is_deterministic_across_repeated_calls(self):
        """Cùng đầu vào -> cùng kết luận (không phụ thuộc trạng thái hay thời gian)."""
        with tempfile.TemporaryDirectory() as tmp:
            metadata = Path(tmp) / "metadata.json"
            _write_metadata(metadata, raw_records=10)  # khớp raw mặc định của _summary()
            summary = self._summary()
            with patch("builtins.print"):
                results = {compare_with_metadata(summary, metadata) for _ in range(3)}
        self.assertEqual(results, {True})


if __name__ == "__main__":
    unittest.main()
