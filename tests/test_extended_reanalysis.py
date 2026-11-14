"""Data-free Issue #50 contracts; real-data claims are verified by the runner locally."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from scripts import run_extended_reanalysis as ext
from scripts.validate_extended_reanalysis import validate_outputs
from src.reanalysis_validation import _contrast_ci, _group_replicates
from src.extended_audit import group_quality_dimensions
from src.inference import build_daily_panel, calendar_block_indices, holm_adjust
from src.issue44_preparation import add_derived_short_gap_interpolation, validate_modeling_split, vietnam_season, winter_year
from src.visualizer import compute_causal_rolling_pm25


def fixture() -> pd.DataFrame:
    stamps = pd.date_range("2024-12-31 21:00", periods=6, freq="h", tz="Asia/Ho_Chi_Minh")
    return pd.concat([
        pd.DataFrame({"station_id": station, "timestamp": stamps,
                      "pm25": [10., np.nan, np.nan, 40., 50., 60.],
                      "split": ["train"]*3+["test"]*3})
        for station in sorted(ext.STATIONS)
    ], ignore_index=True)


def contract_fixture() -> pd.DataFrame:
    frame = fixture()
    frame["pm25_derived_interpolated"] = frame.pm25
    frame["pm25_is_derived"] = False
    frame["season"] = vietnam_season(frame.timestamp)
    frame["winter_year"] = winter_year(frame.timestamp)
    return frame


class TestExtendedReanalysis(unittest.TestCase):
    def test_missing_raw_source_hours_are_not_hidden_by_duplicate_rows(self):
        group = pd.DataFrame({
            "station_id": ["A"] * 4,
            "timestamp": pd.date_range("2024-01-01", periods=4, freq="h", tz="Asia/Ho_Chi_Minh"),
            "pm25": [10., np.nan, 20., np.nan],
        })
        qc = group_quality_dimensions(
            group, expected_calendar_hours=4, outside_active_window_hours=0,
            raw_observations=4, raw_source_hours=2, raw_invalid_observations=1,
        )
        self.assertEqual(qc["missing_source_rows"], 2)
        self.assertEqual(qc["invalid_source_rows"], 1)

    def test_nonfinite_is_not_double_counted_as_out_of_bounds(self):
        group = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="h", tz="Asia/Ho_Chi_Minh"),
            "pm25": [float("inf"), -999., np.nan],
        })
        qc = group_quality_dimensions(
            group, expected_calendar_hours=3, outside_active_window_hours=0,
        )
        self.assertEqual(qc["nonfinite_pm25_values"], 1)
        self.assertEqual(qc["out_of_bounds_pm25_values"], 1)
        self.assertEqual(qc["negative_sentinel_values"], 1)

    def test_group_six_dimensions_catch_duplicate_irregular_and_invalid_timestamp(self):
        stamps = pd.date_range("2024-01-01", periods=4, freq="h", tz="Asia/Ho_Chi_Minh")
        group = pd.DataFrame({
            "station_id": ["A"] * 4,
            "timestamp": [stamps[0], stamps[0], stamps[2], pd.NaT],
            "pm25": [10., np.nan, 20., 30.],
        })
        qc = group_quality_dimensions(
            group, expected_calendar_hours=4, outside_active_window_hours=0,
        )
        self.assertEqual(qc["duplicate_keys"], 1)
        self.assertEqual(qc["dim_uniqueness_status"], "FAIL")
        self.assertEqual(qc["dim_consistency_status"], "FAIL")
        self.assertEqual(qc["dim_timeliness_status"], "FAIL")

    def test_group_weather_bound_violation_fails_validity_not_device_accuracy(self):
        group = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=2, freq="h", tz="Asia/Ho_Chi_Minh"),
            "pm25": [10., 20.], "temperature": [20., 10000.],
        })
        qc = group_quality_dimensions(
            group, expected_calendar_hours=2, outside_active_window_hours=0,
            physical_bounds=ext.ATMOSPHERIC_BOUNDS,
        )
        self.assertGreater(qc["other_bound_violations"], 0)
        self.assertEqual(qc["dim_validity_status"], "FAIL")
        self.assertEqual(qc["dim_accuracy_status"], "UNVERIFIABLE")
    def test_contrast_ci_resamples_calendar_groups_without_crossing_missing_days(self):
        grid = {"values": np.array([10., np.nan, 12., 14., 40., np.nan, 42., 44.])}
        winter = np.array([True, True, True, True, False, False, False, False])
        summer = ~winter
        ci = _contrast_ci(
            grid, winter, summer, statistic="median", block=2,
            n_bootstrap=60, seed=42,
        )
        self.assertEqual(ci["point"], -30.)
        self.assertLess(ci["ci_high"], 0.)

    def test_calendar_group_replicates_do_not_cross_separated_cohorts(self):
        values = np.array([10., 10., np.nan, 10., 20., 20., 20., 100., 100., np.nan, 100.])
        mask = np.array([True] * 4 + [False] * 3 + [True] * 4)
        copies = _group_replicates(values, mask=mask, block=3, n_bootstrap=60, seed=42)
        self.assertEqual(copies.shape, (60, 6))
        self.assertTrue(np.isin(copies, [10., 100.]).all())

    def test_missing_input_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                ext.validate_dataset(Path(tmp)/"absent.parquet")

    def test_observed_cell_audit_ignores_timestamp_resolution_only(self):
        stamps = pd.date_range("2024-01-01", periods=3, freq="h", tz="Asia/Ho_Chi_Minh")
        old = pd.DataFrame({"station_id": "VN001_HANOI_556_NGUYEN_VAN_CU",
                            "timestamp": stamps, "pm25": [10., np.nan, 40.]})
        for unit in ("ns", "us"):
            new = old.copy()
            new["timestamp"] = new["timestamp"].astype(f"datetime64[{unit}, Asia/Ho_Chi_Minh]")
            if unit == "us":
                self.assertFalse(old.timestamp.equals(new.timestamp))
            ext.assert_observed_cells_unchanged(old, new)
        changed = old.copy()
        changed.loc[0, "pm25"] = 11.
        with self.assertRaises(ValueError):
            ext.assert_observed_cells_unchanged(old, changed)
        disappeared = old.copy()
        disappeared.loc[2, "pm25"] = np.nan
        with self.assertRaises(ValueError):
            ext.assert_observed_cells_unchanged(old, disappeared)
        with self.assertRaises(ValueError):
            ext.assert_observed_cells_unchanged(old, old.iloc[:2])

    def test_station_missing_runs_do_not_join(self):
        gaps = ext.missing_runs(fixture())
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps.gap_hours.tolist(), [2, 2])

    def test_winter_year_crosses_new_year(self):
        group = fixture().iloc[:6]
        periods = list(ext.period_groups(group))
        winter = [(key, len(rows), int((end-start)/pd.Timedelta(hours=1)))
                  for kind, key, rows, start, end in periods if kind == "winter_year"]
        self.assertEqual(winter, [("Winter (Dec-Feb):2025", 6, 2160)])

    def test_year_denominator_is_full_calendar(self):
        group = fixture().iloc[:6]
        years = [(key, len(rows), int((end-start)/pd.Timedelta(hours=1)))
                 for kind, key, rows, start, end in ext.period_groups(group) if kind == "year"]
        self.assertEqual(years, [("2024", 3, 8784), ("2025", 3, 8760)])

    def test_derived_values_do_not_change_observed(self):
        frame = fixture()
        filled = add_derived_short_gap_interpolation(frame, "pm25", max_gap_hours=2)
        pd.testing.assert_series_equal(frame.pm25, filled.pm25)
        # Split boundary at the gap stops a future Test value from filling Train.
        self.assertEqual(int(filled.pm25_is_derived.sum()), 0)

    def test_daily_panel_rejects_station_pooling(self):
        with self.assertRaises(ValueError):
            build_daily_panel(fixture(), min_valid_hours=1)

    def test_causal_rolling_starts_fresh_at_station_boundary(self):
        frame = fixture()
        frame.loc[6, "pm25"] = 100.
        rolled = compute_causal_rolling_pm25(frame[["station_id", "timestamp", "pm25"]],
                                               min_periods_24h=1, min_periods_7d=1)
        first = rolled.groupby("station_id").first()
        self.assertEqual(first.loc[sorted(ext.STATIONS)[0], "rolling_24h"], 10.)
        self.assertEqual(first.loc[sorted(ext.STATIONS)[1], "rolling_24h"], 100.)

    def test_pooled_split_is_rejected(self):
        frame = fixture()
        station = sorted(ext.STATIONS)[1]
        frame.loc[frame.station_id == station, "timestamp"] += pd.DateOffset(years=1)
        validate_modeling_split(frame, protocol="station_specific")
        with self.assertRaises(ValueError):
            validate_modeling_split(frame, protocol="pooled")

    def test_calendar_blocks_are_reproducible(self):
        a = calendar_block_indices(50, block_length_days=7, n_bootstrap=20, seed=42)
        b = calendar_block_indices(50, block_length_days=7, n_bootstrap=20, seed=42)
        np.testing.assert_array_equal(a, b)

    def test_holm_family_remains_four(self):
        p = holm_adjust([.01, .02, .03, .04])
        self.assertEqual(len(p), 4)
        self.assertAlmostEqual(p[0], .04)

    def test_figure_is_300_dpi_and_inputs_immutable(self):
        frame = fixture()
        before = frame.copy(deep=True)
        quality = pd.DataFrame([
            {"station_id": station, "period_type": "winter_year", "period": "Winter (Dec-Feb):2025",
             "coverage_pct_calendar": 10., "valid_pm25_observations": 4,
             "active_grid_hours": 6, "expected_calendar_hours": 2160}
            for station in sorted(ext.STATIONS)
        ] + [{"station_id": station, "period_type": "year", "period": str(year),
              "coverage_pct_calendar": 10., "valid_pm25_observations": 2}
             for station in sorted(ext.STATIONS) for year in (2024, 2025)])
        with tempfile.TemporaryDirectory() as tmp:
            original = ext.FIGURES
            try:
                ext.FIGURES = Path(tmp)
                ext.save_figures(frame, quality)
                for name in ("FIG-02-extended.png", "FIG-03-extended.png"):
                    with Image.open(Path(tmp)/name) as img:
                        self.assertAlmostEqual(img.info["dpi"][0], 300, delta=1)
            finally:
                ext.FIGURES = original
        pd.testing.assert_frame_equal(frame, before)

    def test_monthly_figure_uses_full_calendar_coverage_not_bar_height_placeholder(self):
        part = fixture().iloc[:6]
        quality = pd.DataFrame([
            {"station_id": part.station_id.iloc[0], "period_type": "month",
             "period": "2024-12", "coverage_pct_calendar": 1 / 744 * 100,
             "valid_pm25_observations": 1},
            {"station_id": part.station_id.iloc[0], "period_type": "month",
             "period": "2025-01", "coverage_pct_calendar": 3 / 744 * 100,
             "valid_pm25_observations": 3},
        ])
        rows = ext.monthly_figure_groups(part, quality)
        self.assertEqual([row["n"] for row in rows], [1, 3])
        for row, n in zip(rows, [1, 3]):
            self.assertAlmostEqual(row["coverage_pct_calendar"], n / 744 * 100)
        self.assertEqual([row["month"] for row in rows], [12, 1])
        altered = quality.copy()
        altered.loc[0, "coverage_pct_calendar"] = 100.
        with self.assertRaises(ValueError):
            ext.monthly_figure_groups(part, altered)

    def test_baseline_list_includes_all_twelve_figures(self):
        for number in range(1, 13):
            self.assertIn(f"figures/FIG-{number:02d}.png", ext.BASELINE)

    def test_input_contract_rejects_corruptions(self):
        good = contract_fixture()
        ext.validate_input_frame(good)
        mutations = {
            "schema": lambda f: f.drop(columns="season"),
            "station_identity": lambda f: f.assign(station_id=None),
            "duplicate_key": lambda f: f.assign(timestamp=f.timestamp.where(f.index != 1, f.timestamp.iloc[0])),
            "timezone": lambda f: f.assign(timestamp=f.timestamp.dt.tz_localize(None)),
            "invalid_pm25": lambda f: f.assign(pm25=f.pm25.where(f.index != 0, -999.)),
            "observed_changed_in_derived": lambda f: f.assign(pm25_derived_interpolated=f.pm25_derived_interpolated.where(f.index != 0, 99.)),
            "derived_flag": lambda f: f.assign(pm25_is_derived=f.pm25_is_derived.where(f.index != 0, True)),
            "season_alignment": lambda f: f.assign(season=f.season.where(f.index != 0, "bad")),
            "split_leakage": lambda f: f.assign(split=f.split.where(f.index != 0, "test")),
            "hidden_grid_gap": lambda f: f.assign(timestamp=f.timestamp.where(f.index != 5, f.timestamp.iloc[5]+pd.Timedelta(hours=2))),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                ext.validate_input_frame(mutation(good.copy()))

    def test_committed_artifacts_are_consistent_without_real_data(self):
        result = validate_outputs(real_data=False)
        self.assertEqual(result["inference_rows"], 8)
        self.assertTrue(result["baseline_unchanged"])


if __name__ == "__main__":
    unittest.main()
