"""Synthetic tests for Issue #44 preparation helpers, not scientific results."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.issue44_preparation import (
    add_derived_short_gap_interpolation,
    assign_pooled_chronological_split,
    assign_station_chronological_split,
    check_station_temporal_overlap,
    evaluate_interpolation_grid,
    generate_legacy_vs_extended_comparison_report,
    haversine_distance_km,
    interpolation_metrics,
    mask_contiguous_gaps,
    mask_observed_values,
    validate_modeling_split,
    verify_legacy_vs_extended_comparison,
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

    def test_validate_modeling_split_station_specific_success(self):
        """Protocol A: Independent chronological split within each station succeeds."""
        ts_a = pd.date_range("2024-01-01", periods=10, freq="h")
        ts_b = pd.date_range("2025-01-01", periods=10, freq="h")
        frame = pd.DataFrame({
            "station_id": ["A"] * 10 + ["B"] * 10,
            "timestamp": list(ts_a) + list(ts_b),
            "split": ["train"] * 8 + ["test"] * 2 + ["train"] * 8 + ["test"] * 2,
        })
        # Should not raise
        validate_modeling_split(frame, protocol="station_specific")

    def test_validate_modeling_split_station_specific_rejects_intra_station_violation(self):
        """Protocol A: Chronological order violation inside a station is caught."""
        ts = pd.date_range("2024-01-01", periods=4, freq="h")
        frame = pd.DataFrame({
            "station_id": ["A"] * 4,
            "timestamp": ts,
            "split": ["test", "train", "test", "train"],
        })
        with self.assertRaisesRegex(ValueError, "Station-specific chronological split violation"):
            validate_modeling_split(frame, protocol="station_specific")

    def test_validate_modeling_split_station_specific_rejects_duplicate_timestamps(self):
        """Protocol A: Duplicate timestamps within station are rejected."""
        ts = [pd.Timestamp("2024-01-01 00:00")] * 2 + [pd.Timestamp("2024-01-01 01:00")] * 2
        frame = pd.DataFrame({
            "station_id": ["A"] * 4,
            "timestamp": ts,
            "split": ["train", "train", "test", "test"],
        })
        with self.assertRaisesRegex(ValueError, "Duplicate timestamps"):
            validate_modeling_split(frame, protocol="station_specific")

    def test_validate_modeling_split_pooled_rejects_station_specific_split(self):
        """Protocol B: Pooled model fails on station-specific split where train max >= test min."""
        # Station A: 2024 (train Jan 1-8, test Jan 9-10)
        # Station B: 2025 (train Jan 1-8, test Jan 9-10)
        # Station B train (2025-01-01) is chronologically after Station A test (2024-01-09)
        ts_a = pd.date_range("2024-01-01", periods=10, freq="h")
        ts_b = pd.date_range("2025-01-01", periods=10, freq="h")
        frame = pd.DataFrame({
            "station_id": ["A"] * 10 + ["B"] * 10,
            "timestamp": list(ts_a) + list(ts_b),
            "split": ["train"] * 8 + ["test"] * 2 + ["train"] * 8 + ["test"] * 2,
        })
        with self.assertRaisesRegex(ValueError, "Temporal leakage detected for Protocol B"):
            validate_modeling_split(frame, protocol="pooled")

    def test_validate_modeling_split_pooled_success_with_overlap(self):
        """Protocol B: Pooled split with global temporal order and both stations in train/test passes."""
        # Both stations active in 2024-01-01 -> 2024-01-10
        ts = pd.date_range("2024-01-01", periods=10, freq="h")
        frame = pd.DataFrame({
            "station_id": ["A"] * 10 + ["B"] * 10,
            "timestamp": list(ts) + list(ts),
            "split": (["train"] * 8 + ["test"] * 2) * 2,
        })
        validate_modeling_split(frame, protocol="pooled")

    def test_validate_modeling_split_pooled_rejects_missing_station_in_partition(self):
        """Protocol B: Disjoint stations where a station has 0 train or 0 test rows are rejected."""
        # Station A is entirely in train, Station B is entirely in test
        ts_a = pd.date_range("2024-01-01", periods=5, freq="h")
        ts_b = pd.date_range("2025-01-01", periods=5, freq="h")
        frame = pd.DataFrame({
            "station_id": ["A"] * 5 + ["B"] * 5,
            "timestamp": list(ts_a) + list(ts_b),
            "split": ["train"] * 5 + ["test"] * 5,
        })
        with self.assertRaisesRegex(ValueError, "Station representation failure for Protocol B"):
            validate_modeling_split(frame, protocol="pooled")

    def test_assign_pooled_chronological_split(self):
        """assign_pooled_chronological_split enforces global order and checks representation."""
        ts = pd.date_range("2024-01-01", periods=20, freq="h")
        frame = pd.DataFrame({
            "station_id": ["A"] * 10 + ["B"] * 10,
            "timestamp": list(ts[:10]) + list(ts[10:]),
        })
        # When require_all_stations_in_both is True, disjoint stations raise representation failure
        with self.assertRaisesRegex(ValueError, "Station representation failure for Protocol B"):
            assign_pooled_chronological_split(frame, train_fraction=0.8, require_all_stations_in_both=True)

        # When require_all_stations_in_both is False, global order is assigned
        res = assign_pooled_chronological_split(frame, train_fraction=0.8, require_all_stations_in_both=False)
        self.assertTrue((res.loc[res["split"] == "train", "timestamp"].max() <
                         res.loc[res["split"] == "test", "timestamp"].min()))

    def test_check_station_temporal_overlap_disjoint_and_overlapping(self):
        """check_station_temporal_overlap accurately detects disjoint gaps and overlapping hours."""
        # Disjoint scenario
        ts_a = pd.date_range("2024-01-01", periods=5, freq="h")
        ts_b = pd.date_range("2024-01-02", periods=5, freq="h")
        df_disjoint = pd.DataFrame({
            "station_id": ["A"] * 5 + ["B"] * 5,
            "timestamp": list(ts_a) + list(ts_b),
        })
        overlap_info = check_station_temporal_overlap(df_disjoint)
        self.assertFalse(overlap_info["has_temporal_overlap"])
        self.assertGreater(overlap_info["pairwise"][0]["gap_hours"], 0)

        # Overlapping scenario
        ts_shared = pd.date_range("2024-01-01", periods=5, freq="h")
        df_overlap = pd.DataFrame({
            "station_id": ["A"] * 5 + ["B"] * 5,
            "timestamp": list(ts_shared) + list(ts_shared),
        })
        overlap_info2 = check_station_temporal_overlap(df_overlap)
        self.assertTrue(overlap_info2["has_temporal_overlap"])
        self.assertEqual(overlap_info2["pairwise"][0]["shared_timestamps_count"], 5)

    def test_station_split_rejects_insufficient_rows(self):
        """Station with fewer than 2 rows raises ValueError for chronological split."""
        frame = pd.DataFrame({
            "station_id": ["A"],
            "timestamp": [pd.Timestamp("2024-01-01")],
        })
        with self.assertRaisesRegex(ValueError, "at least 2 rows"):
            assign_station_chronological_split(frame)

    def test_generate_and_verify_legacy_vs_extended_comparison_report(self):
        """Report generator and verifier run deterministically in a temporary directory."""
        manifest = {
            "s3_daily_file_count": 903,
            "coverage": {"qc_valid_hours": 18208, "total_reported_rows_s3_prefix": 21401},
        }
        ext_meta = {"total_grid_rows": 37722, "sha256": "mock_sha256_extended"}
        interp_df = pd.DataFrame([{
            "station_id": "VN001",
            "season_scope": "ALL",
            "masked_gap_length_hours": 1,
            "max_gap_hours": 1,
            "n_masked_hours": 100,
            "mae": 2.7757,
            "rmse": 3.7745,
            "bias": 0.1080,
            "real_interpolated_hours": 80,
            "station_missing_hours": 1549,
            "real_interpolated_pct_of_missing": 5.16,
            "coverage_before_pct": 82.87,
            "coverage_after_pct": 83.76,
        }, {
            "station_id": "VN003",
            "season_scope": "ALL",
            "masked_gap_length_hours": 1,
            "max_gap_hours": 1,
            "n_masked_hours": 100,
            "mae": 6.0550,
            "rmse": 10.2376,
            "bias": -0.6550,
            "real_interpolated_hours": 116,
            "station_missing_hours": 10470,
            "real_interpolated_pct_of_missing": 1.11,
            "coverage_before_pct": 63.49,
            "coverage_after_pct": 63.90,
        }])
        winter_df = pd.DataFrame([{
            "station_id": "VN001",
            "winter_id": "W2026",
            "n_valid_hours": 1958,
            "valid_pct_full_winter": 90.65,
            "valid_pct_active_grid": 90.65,
            "mean_pm25": 63.15,
            "std_pm25": 33.56,
            "median_pm25": 57.11,
            "iqr_pm25": 48.61,
            "q25_pm25": 37.1,
            "q75_pm25": 85.8,
            "p90_pm25": 110.19,
            "valid_daily_count_ge18h": 79,
            "qcvn_daily_exceedance_days": 47,
            "qcvn_daily_exceedance_pct": 59.49,
        }])

        with tempfile.TemporaryDirectory() as tmpdir:
            out_md = Path(tmpdir) / "test_report.md"
            text1 = generate_legacy_vs_extended_comparison_report(
                manifest, ext_meta, interp_df, winter_df, output_path=out_md
            )
            self.assertTrue(out_md.exists())
            text2 = generate_legacy_vs_extended_comparison_report(
                manifest, ext_meta, interp_df, winter_df, output_path=None
            )
            # Deterministic output
            self.assertEqual(text1, text2)

            res = verify_legacy_vs_extended_comparison(text1, manifest, ext_meta, interp_df, winter_df)
            self.assertTrue(res["verified"])
            self.assertEqual(len(res["mismatches"]), 0)

    def test_verify_legacy_vs_extended_comparison_catches_mismatches(self):
        """Verifier catches missing sections or corrupted values."""
        bad_text = "# Incomplete Report without required sections"
        res = verify_legacy_vs_extended_comparison(bad_text, {}, {}, pd.DataFrame(), pd.DataFrame())
        self.assertFalse(res["verified"])
        self.assertGreater(len(res["mismatches"]), 0)
