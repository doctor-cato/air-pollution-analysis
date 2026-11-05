"""Synthetic tests for Issue #44 preparation helpers, not scientific results."""
import unittest

import numpy as np
import pandas as pd

from src.issue44_preparation import (
    add_derived_short_gap_interpolation,
    assign_station_chronological_split,
    evaluate_interpolation_grid,
    haversine_distance_km,
    interpolation_metrics,
    mask_contiguous_gaps,
    mask_observed_values,
    winter_station_summary,
    winter_year,
)


class TestIssue44Preparation(unittest.TestCase):
    def test_interpolation_is_derived_and_split_station_bounded(self):
        frame = pd.DataFrame({"station_id": ["A"] * 5 + ["B"] * 3, "split": ["train"] * 3 + ["test"] * 2 + ["train"] * 3, "timestamp": pd.date_range("2024-01-01", periods=8, freq="h"), "pm25": [10.0, np.nan, 30.0, 40.0, np.nan, 10.0, np.nan, 30.0]})
        result = add_derived_short_gap_interpolation(frame, "pm25", max_gap_hours=1)
        self.assertEqual(result.loc[1, "pm25_derived_interpolated"], 20.0)
        self.assertTrue(result.loc[1, "pm25_is_derived"])
        self.assertTrue(pd.isna(result.loc[4, "pm25_derived_interpolated"]))
        self.assertEqual(result.loc[6, "pm25_derived_interpolated"], 20.0)
        self.assertEqual(result.loc[0, "pm25"], result.loc[0, "pm25_derived_interpolated"])

    def test_interpolation_rejects_timestamp_gap_and_long_missing_run(self):
        frame = pd.DataFrame({"station_id": ["A"] * 3, "split": ["train"] * 3, "timestamp": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01 02:00"), pd.Timestamp("2024-01-01 03:00")], "pm25": [1.0, np.nan, 3.0]})
        with self.assertRaisesRegex(ValueError, "non-hourly"):
            add_derived_short_gap_interpolation(frame, "pm25", max_gap_hours=1)

    def test_mask_and_metrics_are_explicit_and_deterministic(self):
        frame = pd.DataFrame({"pm25": [1.0, 2.0, 3.0, np.nan]})
        masked = mask_observed_values(frame, "pm25", 0.5, random_state=42)
        self.assertEqual(masked["pm25_mask_validation"].sum(), 2)
        metrics = interpolation_metrics([1, 2], [2, 0])
        self.assertEqual(metrics, {"n": 2, "mae": 1.5, "rmse": float(np.sqrt(2.5)), "bias": -0.5})

    def test_winter_year_and_station_summary_keep_stations_separate(self):
        timestamps = pd.Series(pd.to_datetime(["2023-12-01", "2024-01-01", "2024-02-01", "2024-03-01"]))
        self.assertEqual(winter_year(timestamps).tolist(), [2024, 2024, 2024, pd.NA])
        frame = pd.DataFrame({"station_id": ["VN001", "VN002"], "timestamp": pd.to_datetime(["2023-12-01", "2024-01-01"]), "pm25": [10.0, 30.0]})
        summary = winter_station_summary(frame)
        self.assertEqual(set(summary["station_id"]), {"VN001", "VN002"})

    def test_contiguous_gap_masking_and_evaluation_grid_respect_boundaries(self):
        ts = pd.date_range("2024-01-01", periods=24, freq="h", tz="Asia/Ho_Chi_Minh")
        frame = pd.DataFrame({
            "station_id": ["VN003"] * 12 + ["VN001"] * 12,
            "timestamp": list(ts[:12]) + list(ts[12:]),
            "pm25": np.linspace(20.0, 43.0, 24),
        })
        split_df = assign_station_chronological_split(frame, train_fraction=0.75)
        self.assertEqual(set(split_df["split"]), {"train", "test"})
        masked = mask_contiguous_gaps(split_df, "pm25", gap_length=2, max_gaps_per_group=1, random_state=42)
        self.assertGreater(int(masked["pm25_mask_validation"].sum()), 0)
        grid = evaluate_interpolation_grid(
            split_df, "pm25", max_gap_candidates=(1, 2), gap_lengths=(1, 2), max_gaps_per_group=2, random_state=42
        )
        self.assertTrue({"station_id", "season_scope", "masked_gap_length_hours", "max_gap_hours", "mae", "rmse", "bias"}.issubset(grid.columns))
        # When masked_gap_length_hours == 2 and max_gap_hours == 1, 0 masked points should be interpolated
        under_cap = grid[(grid["masked_gap_length_hours"] == 2) & (grid["max_gap_hours"] == 1)]
        self.assertTrue((under_cap["n_interpolated_masked_hours"] == 0).all())
        # Haversine distance check between OpenAQ 7441 and ERA5 grid (~8.98 km)
        dist = haversine_distance_km((21.021939, 105.818806), (21.05448, 105.89848))
        self.assertTrue(8.0 < dist < 10.0)
