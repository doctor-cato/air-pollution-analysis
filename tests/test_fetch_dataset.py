
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.fetch_dataset import compare_with_metadata, summarise_interim_on_disk

SAMPLE_ROWS = 3
SAMPLE_AIR_MIN = "2025-07-03 22:00:00+07:00"
SAMPLE_AIR_MAX = "2025-07-04 00:00:00+07:00"


def _write_interim(directory: Path) -> None:
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

    def test_summarise_reads_canonical_files_without_network(self):
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
        with tempfile.TemporaryDirectory() as tmp:
            interim = Path(tmp) / "interim"
            interim.mkdir()
            _write_interim(interim)
            summary = summarise_interim_on_disk(interim)

        self.assertIsNone(summary["openaq"]["raw_records_total"])

    def test_summarise_fails_loud_when_canonical_files_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with self.assertRaises(FileNotFoundError) as ctx:
                summarise_interim_on_disk(empty)
        self.assertIn("fetch_dataset.py", str(ctx.exception))

    def test_skip_fetch_reports_match_against_metadata(self):
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
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "khong-ton-tai.json"
            with patch("builtins.print"):
                self.assertTrue(compare_with_metadata(self._summary(), missing))

    def test_underivable_fields_are_skipped_not_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = Path(tmp) / "metadata.json"
            _write_metadata(metadata, raw_records=10)
            summary = self._summary(raw=None)
            with patch("builtins.print"):
                self.assertTrue(compare_with_metadata(summary, metadata))

    def test_is_deterministic_across_repeated_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = Path(tmp) / "metadata.json"
            _write_metadata(metadata, raw_records=10)
            summary = self._summary()
            with patch("builtins.print"):
                results = {compare_with_metadata(summary, metadata) for _ in range(3)}
        self.assertEqual(results, {True})


if __name__ == "__main__":
    unittest.main()
