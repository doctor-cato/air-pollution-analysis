"""Unit tests for src/data_loader.py (Issue #15 / Issue #56)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_loader import (
    BASELINE_DATASET_PATH,
    BASELINE_REQUIRED_COLUMNS,
    COHORT_CONFIGS,
    EXTENDED_DATASET_PATH,
    EXTENDED_REQUIRED_COLUMNS,
    REPO_ROOT,
    VN001_STATION_ID,
    VN003_STATION_ID,
    compute_file_sha256,
    enforce_station_key,
    get_cohort_config,
    load_cohort,
    load_processed_parquet,
    validate_canonical_schema,
    write_parquet_snappy,
)


def _make_canonical_frame(
    station_id: str = VN001_STATION_ID,
    start: str = "2026-01-01 00:00",
    periods: int = 8,
    extended: bool = False,
) -> pd.DataFrame:
    ts = pd.date_range(start=start, periods=periods, freq="h", tz="Asia/Ho_Chi_Minh")
    data = {
        "timestamp": ts,
        "station_id": [station_id] * periods,
        "location": ["Hanoi Test"] * periods,
        "pm25": np.linspace(20.0, 55.0, periods),
        "pm10": np.linspace(30.0, 75.0, periods),
        "pm25_was_stuck": [0] * periods,
        "pm25_was_missing": [0] * periods,
        "is_high_humidity_fog": [0] * periods,
        "temperature": [22.5] * periods,
        "relative_humidity": [75.0] * periods,
        "wind_speed": [1.8] * periods,
        "wind_direction": [110.0] * periods,
        "precipitation": [0.0] * periods,
        "surface_pressure": [1012.0] * periods,
        "hour_sin": np.zeros(periods),
        "hour_cos": np.ones(periods),
        "month_sin": np.zeros(periods),
        "month_cos": np.ones(periods),
    }
    if extended:
        half = periods // 2
        data["split"] = ["train"] * half + ["test"] * (periods - half)
        data["pm25_derived_interpolated"] = data["pm25"]
        data["pm25_is_derived"] = [False] * periods
        data["winter_year"] = pd.Series([2026] * periods, dtype="Int64")
        data["season"] = ["Winter (Dec-Feb)"] * periods
    return pd.DataFrame(data)


class TestDataLoaderUnit(unittest.TestCase):
    """Kiểm thử tổng hợp không phụ thuộc dữ liệu thật (chạy được trên CI)."""

    def test_cohort_configs_keep_baseline_and_extended_isolated(self):
        cfg_base = get_cohort_config("vn001_baseline")
        cfg_ext1 = get_cohort_config("vn001_extended")
        cfg_ext3 = get_cohort_config("vn003_extended")

        self.assertEqual(cfg_base.dataset_version, "1.0.0-m2-baseline")
        self.assertEqual(cfg_ext1.dataset_version, "2.0.0-issue44-extended")
        self.assertEqual(cfg_ext3.station_id, VN003_STATION_ID)
        self.assertEqual(
            len({cfg_base.output_dir, cfg_ext1.output_dir, cfg_ext3.output_dir}),
            3,
        )
        with self.assertRaises(KeyError):
            get_cohort_config("pooled_all_stations")

    def test_validate_canonical_schema_rejects_missing_cols_and_naive_ts(self):
        df = _make_canonical_frame()
        validate_canonical_schema(df, BASELINE_REQUIRED_COLUMNS)

        with self.assertRaises(ValueError):
            validate_canonical_schema(df.drop(columns=["pm25"]), BASELINE_REQUIRED_COLUMNS)

        naive = df.copy()
        naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
        with self.assertRaises(ValueError):
            validate_canonical_schema(naive, BASELINE_REQUIRED_COLUMNS)

    def test_enforce_station_key_fails_closed_on_invalid_or_mixed_stations(self):
        df1 = _make_canonical_frame(station_id=VN001_STATION_ID)
        df3 = _make_canonical_frame(station_id=VN003_STATION_ID, start="2024-01-01 00:00")
        mixed = pd.concat([df1, df3], ignore_index=True)

        # Mixed stations rejected unless explicitly allowed or filtered
        with self.assertRaises(ValueError):
            enforce_station_key(mixed)

        filtered = enforce_station_key(mixed, expected_station_id=VN003_STATION_ID)
        self.assertEqual(set(filtered["station_id"].unique()), {VN003_STATION_ID})

        both = enforce_station_key(mixed, allow_multi_station=True)
        self.assertEqual(len(both), len(mixed))

        # Blank or NaN station_id rejected
        blank = df1.copy()
        blank.loc[0, "station_id"] = "   "
        with self.assertRaises(ValueError):
            enforce_station_key(blank)

        missing = df1.copy()
        missing.loc[0, "station_id"] = None
        with self.assertRaises(ValueError):
            enforce_station_key(missing)

    def test_enforce_station_key_rejects_duplicate_keys_and_sorts_chronologically(self):
        df = _make_canonical_frame()
        shuffled = df.iloc[::-1].reset_index(drop=True)
        sorted_df = enforce_station_key(shuffled)
        self.assertTrue(sorted_df["timestamp"].is_monotonic_increasing)

        dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            enforce_station_key(dup)

    def test_write_and_load_parquet_roundtrip_and_sha256(self):
        df = _make_canonical_frame(extended=True)
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "cohort.parquet"
            sha = write_parquet_snappy(df, out_path)
            self.assertEqual(len(sha), 64)
            self.assertEqual(sha, compute_file_sha256(out_path))

            with self.assertRaises(FileExistsError):
                write_parquet_snappy(df, out_path, allow_overwrite=False)

            loaded = load_processed_parquet(
                out_path,
                required_columns=EXTENDED_REQUIRED_COLUMNS,
                station_id=VN001_STATION_ID,
            )
            self.assertEqual(len(loaded), len(df))

    def test_load_cohort_rejects_split_leakage(self):
        df = _make_canonical_frame(extended=True, periods=8)
        # Swap split labels to force train_max >= test_min
        df["split"] = ["test", "test", "test", "test", "train", "train", "train", "train"]
        with tempfile.TemporaryDirectory() as tmp:
            target_rel = COHORT_CONFIGS["vn001_extended"].input_path
            fake_path = Path(tmp) / target_rel
            write_parquet_snappy(df, fake_path)
            with self.assertRaises(ValueError):
                load_cohort("vn001_extended", base_dir=tmp)

    def test_load_cohort_success_on_synthetic_extended_directory(self):
        df1 = _make_canonical_frame(station_id=VN001_STATION_ID, start="2026-01-01 00:00", extended=True)
        df3 = _make_canonical_frame(station_id=VN003_STATION_ID, start="2024-01-01 00:00", extended=True)
        combined = pd.concat([df3, df1], ignore_index=True)
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / EXTENDED_DATASET_PATH
            write_parquet_snappy(combined, fake_path)
            loaded, cfg = load_cohort("vn003_extended", base_dir=tmp)
            self.assertEqual(cfg.station_id, VN003_STATION_ID)
            self.assertEqual(len(loaded), len(df3))
            self.assertEqual(set(loaded["station_id"].unique()), {VN003_STATION_ID})


class TestDataLoaderRealDataset(unittest.TestCase):
    """Kiểm thử trên dữ liệu Parquet thật cục bộ (skip khi CI thiếu data/)."""

    @classmethod
    def setUpClass(cls):
        cls.base_file = REPO_ROOT / BASELINE_DATASET_PATH
        cls.ext_file = REPO_ROOT / EXTENDED_DATASET_PATH
        if not cls.base_file.exists() or not cls.ext_file.exists():
            raise unittest.SkipTest("Local processed Parquet files not available (CI mode).")

    def test_real_cohorts_load_cleanly_and_preserve_station_isolation(self):
        df_base, cfg_base = load_cohort("vn001_baseline")
        self.assertEqual(df_base.shape, (9044, 18))
        self.assertEqual(cfg_base.station_id, VN001_STATION_ID)

        df_v1, _ = load_cohort("vn001_extended")
        self.assertEqual(df_v1.shape, (9044, 23))

        df_v3, cfg_v3 = load_cohort("vn003_extended")
        self.assertEqual(df_v3.shape, (28678, 23))
        self.assertEqual(cfg_v3.station_id, VN003_STATION_ID)


if __name__ == "__main__":
    unittest.main()
