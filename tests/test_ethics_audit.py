"""Deterministic offline unit tests for src/ethics_audit.py (Issue #14).

Runs completely offline using synthetic Parquet fixtures inside a temporary
directory so CI passes without access to the gitignored ``data/`` folder.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.ethics_audit import (
    BASELINE_PARQUET_REL,
    EXTENDED_PARQUET_REL,
    optimize_dataframe_dtypes,
    run_bias_audit,
    run_data_scale_benchmark,
)


def _make_synthetic_station_frame(
    station_id: str,
    location: str,
    start: str,
    periods: int,
    seed: int,
    add_zeros: int = 0,
    gap_start: int = 100,
    gap_len: int = 30,
) -> pd.DataFrame:
    """Build a deterministic hourly synthetic dataset matching Canonical Schema."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start=start, periods=periods, freq="h", tz="Asia/Ho_Chi_Minh")
    hours = ts.hour.to_numpy()
    months = ts.month.to_numpy()

    temp = 24.0 + 6.0 * np.sin(2.0 * np.pi * (months - 4) / 12.0) + rng.normal(0, 1.5, periods)
    rh = np.clip(78.0 + 18.0 * rng.normal(0, 1.0, periods), 35.0, 100.0)
    # Guarantee fog=1 and fog=0 across all 4 seasons
    fog = (rh > 90.0).astype(np.int64)
    for m_group in ([12, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]):
        idx = np.flatnonzero(np.isin(months, m_group))
        if idx.size >= 10:
            fog[idx[:5]] = 1
            rh[idx[:5]] = 95.0
            fog[idx[5:10]] = 0
            rh[idx[5:10]] = 65.0

    wind = np.clip(2.5 + rng.normal(0, 1.0, periods), 0.1, 10.0)
    wind_dir = rng.uniform(0.0, 360.0, periods)
    precip = np.where(rng.random(periods) < 0.15, rng.exponential(2.0, periods), 0.0)
    pressure = 1012.0 + rng.normal(0, 5.0, periods)

    pm25 = np.clip(
        42.0
        + 18.0 * np.isin(months, [12, 1, 2]).astype(float)
        - 3.5 * wind
        + rng.normal(0, 12.0, periods),
        2.0,
        250.0,
    )

    # Inject a deterministic contiguous gap
    pm25[gap_start : gap_start + gap_len] = np.nan
    if add_zeros > 0:
        valid_idx = np.flatnonzero(~np.isnan(pm25))
        pm25[valid_idx[:add_zeros]] = 0.0

    season_map = {
        12: "Winter (Dec-Feb)", 1: "Winter (Dec-Feb)", 2: "Winter (Dec-Feb)",
        3: "Spring (Mar-May)", 4: "Spring (Mar-May)", 5: "Spring (Mar-May)",
        6: "Summer (Jun-Aug)", 7: "Summer (Jun-Aug)", 8: "Summer (Jun-Aug)",
        9: "Autumn (Sep-Nov)", 10: "Autumn (Sep-Nov)", 11: "Autumn (Sep-Nov)",
    }

    df = pd.DataFrame(
        {
            "timestamp": ts,
            "station_id": pd.Series([station_id] * periods, dtype="string"),
            "location": pd.Series([location] * periods, dtype="string"),
            "pm25": pm25.astype(np.float64),
            "pm10": (pm25 * 1.4).astype(np.float64),
            "pm25_was_stuck": np.zeros(periods, dtype=np.int64),
            "pm25_was_missing": np.isnan(pm25).astype(np.int64),
            "is_high_humidity_fog": fog.astype(np.int64),
            "temperature": temp.astype(np.float64),
            "relative_humidity": rh.astype(np.float64),
            "wind_speed": wind.astype(np.float64),
            "wind_direction": wind_dir.astype(np.float64),
            "precipitation": precip.astype(np.float64),
            "surface_pressure": pressure.astype(np.float64),
            "hour_sin": np.sin(2.0 * np.pi * hours / 24.0),
            "hour_cos": np.cos(2.0 * np.pi * hours / 24.0),
            "month_sin": np.sin(2.0 * np.pi * months / 12.0),
            "month_cos": np.cos(2.0 * np.pi * months / 12.0),
            "split": pd.Series(
                ["train"] * int(periods * 0.8) + ["test"] * (periods - int(periods * 0.8)),
                dtype="string",
            ),
            "pm25_derived_interpolated": pm25.astype(np.float64),
            "pm25_is_derived": np.zeros(periods, dtype=bool),
            "winter_year": pd.Series(ts.year, dtype="Int64"),
            "season": pd.Series([season_map[int(m)] for m in months], dtype="string"),
        }
    )
    return df


class TestEthicsAudit(unittest.TestCase):
    """Offline unit tests for Issue #14 benchmark and 4-hypothesis bias audit."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="test_ethics_audit_")
        self.root = Path(self._tmp.name)
        self.data_dir = self.root / "data"
        self.reports_dir = self.root / "reports"
        self.docs_dir = self.root / "docs"
        (self.data_dir / "processed").mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        # Build full 1-year baseline VN001 (8,760h -> all 4 seasons present)
        # and 1-year VN003 with 4 exact zeros and 2,040h gap before VN001.
        self.df_vn003 = _make_synthetic_station_frame(
            station_id="VN003_HANOI_OPENAQ_7441",
            location="Hanoi OpenAQ 7441",
            start="2024-04-10 00:00:00",
            periods=8760,
            seed=101,
            add_zeros=4,
            gap_start=200,
            gap_len=48,
        )
        self.df_vn001 = _make_synthetic_station_frame(
            station_id="VN001_HANOI_556_NGUYEN_VAN_CU",
            location="556 Nguyen Van Cu, Hanoi",
            start="2025-07-04 00:00:00",
            periods=8760,
            seed=202,
            add_zeros=0,
            gap_start=300,
            gap_len=36,
        )
        self.df_base = self.df_vn001.drop(
            columns=["split", "pm25_derived_interpolated", "pm25_is_derived", "winter_year", "season"]
        )
        self.df_ext = pd.concat([self.df_vn003, self.df_vn001], ignore_index=True)

        self.df_base.to_parquet(self.data_dir / BASELINE_PARQUET_REL, index=False)
        self.df_ext.to_parquet(self.data_dir / EXTENDED_PARQUET_REL, index=False)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_optimize_dataframe_dtypes_reduces_memory(self) -> None:
        before = int(self.df_ext.memory_usage(deep=True).sum())
        opt = optimize_dataframe_dtypes(self.df_ext)
        after = int(opt.memory_usage(deep=True).sum())

        self.assertLess(after, before)
        self.assertEqual(opt["pm25"].dtype, np.float32)
        self.assertEqual(str(opt["station_id"].dtype), "category")
        self.assertEqual(str(opt["season"].dtype), "category")
        self.assertEqual(str(opt["split"].dtype), "category")
        self.assertEqual(opt["is_high_humidity_fog"].dtype, np.int8)

    def test_run_data_scale_benchmark_schema_and_readonly_data_dir(self) -> None:
        before_files = sorted(p.name for p in (self.data_dir / "processed").iterdir())
        out_md = self.reports_dir / "data_scale_benchmark.md"
        out_json = self.reports_dir / "data_scale_benchmark.json"

        payload = run_data_scale_benchmark(
            data_dir=self.data_dir,
            output_md=out_md,
            output_json=out_json,
            repeats=2,
        )

        # Read-only guarantee: no CSVs or extra files written inside data_dir
        after_files = sorted(p.name for p in (self.data_dir / "processed").iterdir())
        self.assertEqual(before_files, after_files)

        self.assertTrue(out_md.exists() and out_md.stat().st_size > 200)
        self.assertTrue(out_json.exists() and out_json.stat().st_size > 200)

        loaded = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(loaded["issue"], "#14")
        self.assertFalse(loaded["recommendation"]["spark_justified"])
        self.assertFalse(loaded["recommendation"]["polars_benchmarked"])
        self.assertEqual(loaded["recommendation"]["w12_volume_tier"], "< 10 GB")

        for key in ("baseline_vn001", "extended_2022_2026"):
            ds = payload["datasets"][key]
            self.assertGreater(ds["storage"]["csv_bytes"], ds["storage"]["parquet_snappy_bytes"])
            self.assertGreater(ds["memory"]["before_bytes"], ds["memory"]["after_bytes"])
            self.assertGreater(ds["memory"]["reduction_pct"], 0.0)
            self.assertGreater(ds["workload"]["naive_loop_ms"], 0.0)
            self.assertGreater(ds["workload"]["vectorized_opt_ms"], 0.0)

        md_text = out_md.read_text(encoding="utf-8")
        self.assertIn("5V", md_text)
        self.assertIn("Scale Up", md_text)
        self.assertIn("polars", md_text.lower())

    def test_run_bias_audit_distinguishes_nan_vs_zero_and_tests_missingness(self) -> None:
        out_md = self.docs_dir / "bias_assessment.md"
        audit = run_bias_audit(
            data_dir=self.data_dir,
            reports_dir=self.reports_dir,
            output_md=out_md,
        )

        self.assertTrue(out_md.exists() and out_md.stat().st_size > 500)
        md_text = out_md.read_text(encoding="utf-8")
        for heading in ("Sensor Bias", "Spatial", "Survivorship", "NaN"):
            self.assertIn(heading, md_text)

        # Representation: exact NaN vs 0.0 counts
        ext_rep = {r["station_id"]: r for r in audit["representation_bias"]["extended"]}
        self.assertEqual(ext_rep["VN001_HANOI_556_NGUYEN_VAN_CU"]["nan_rows"], 36)
        self.assertEqual(ext_rep["VN001_HANOI_556_NGUYEN_VAN_CU"]["exact_zero_rows"], 0)
        self.assertEqual(ext_rep["VN003_HANOI_OPENAQ_7441"]["nan_rows"], 48)
        self.assertEqual(ext_rep["VN003_HANOI_OPENAQ_7441"]["exact_zero_rows"], 4)

        # Sensor overlap: zero temporal overlap between VN003 and VN001
        self.assertEqual(audit["sensor_bias"]["inter_station_overlap"]["overlap_hours"], 0)
        self.assertGreater(audit["sensor_bias"]["inter_station_overlap"]["gap_hours"], 0)

        # Weather missingness associations computed for all 5 weather cols × 2 stations
        wx_assoc = audit["survivorship_bias"]["weather_missingness_associations"]
        self.assertEqual(len(wx_assoc), 10)
        for row in wx_assoc:
            self.assertIsNotNone(row["mannwhitney_u"])
            self.assertIsNotNone(row["rank_biserial_r"])
            self.assertIsNotNone(row["point_biserial_r"])
            self.assertGreaterEqual(row["rank_biserial_r"], -1.0)
            self.assertLessEqual(row["rank_biserial_r"], 1.0)

        # Missingness table by (station, year, season) includes longest_gap_hours
        miss_rows = audit["survivorship_bias"]["missingness_by_station_year_season"]
        self.assertGreaterEqual(len(miss_rows), 8)
        max_gap = max(r["longest_gap_hours"] for r in miss_rows)
        self.assertEqual(max_gap, 48)


if __name__ == "__main__":
    unittest.main()
