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

    @staticmethod
    def _build_report_fixture():
        manifest = {
            "s3_daily_file_count": 903,
            "coverage": {
                "raw_rows": 21401,
                "qc_valid_hours": 18208,
                "sentinel_or_negative_hours": 3193,
                "longest_contiguous_gap_active_window_hours": 2568,
                "source_observation_window": {
                    "start": "2022-01-01T01:00:00+07:00",
                    "end": "2025-04-09T22:00:00+07:00",
                    "active_window_hours": 28678,
                },
                "annual": [
                    {
                        "year": 2022,
                        "s3_daily_files": 190,
                        "expected_hours": 8760,
                        "source_available_hours": 8759,
                        "s3_reported_hours": 4559,
                        "qc_valid_hours": 3079,
                        "qc_valid_pct_of_calendar_year": 35.15,
                        "qc_valid_pct_of_active_window": 35.15,
                        "sentinel_or_negative_hours": 1480,
                        "longest_gap_hours": 2568,
                    },
                    {
                        "year": 2023,
                        "s3_daily_files": 249,
                        "expected_hours": 8760,
                        "source_available_hours": 8760,
                        "s3_reported_hours": 5794,
                        "qc_valid_hours": 5646,
                        "qc_valid_pct_of_calendar_year": 64.45,
                        "qc_valid_pct_of_active_window": 64.45,
                        "sentinel_or_negative_hours": 148,
                        "longest_gap_hours": 1049,
                    },
                    {
                        "year": 2024,
                        "s3_daily_files": 365,
                        "expected_hours": 8784,
                        "source_available_hours": 8784,
                        "s3_reported_hours": 8702,
                        "qc_valid_hours": 7218,
                        "qc_valid_pct_of_calendar_year": 82.17,
                        "qc_valid_pct_of_active_window": 82.17,
                        "sentinel_or_negative_hours": 1484,
                        "longest_gap_hours": 820,
                    },
                    {
                        "year": 2025,
                        "s3_daily_files": 99,
                        "expected_hours": 8760,
                        "source_available_hours": 2375,
                        "s3_reported_hours": 2346,
                        "qc_valid_hours": 2265,
                        "qc_valid_pct_of_calendar_year": 25.86,
                        "qc_valid_pct_of_active_window": 95.37,
                        "sentinel_or_negative_hours": 81,
                        "longest_gap_hours": 66,
                    },
                ],
            },
        }
        ext_meta = {
            "total_rows": 37722,
            "sha256": "6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02",
            "stations": {
                "VN001_HANOI_556_NGUYEN_VAN_CU": {
                    "grid_rows": 9044,
                    "observed_pm25_rows": 7495,
                    "missing_pm25_rows": 1549,
                    "missing_pm25_pct": 17.13,
                    "min_timestamp": "2025-07-03 22:00:00+07:00",
                    "max_timestamp": "2026-07-15 17:00:00+07:00",
                    "train_rows": 7235,
                    "test_rows": 1809,
                    "distance_to_era5_grid_km": 1.704,
                    "winter_years_covered": [2026],
                },
                "VN003_HANOI_OPENAQ_7441": {
                    "grid_rows": 28678,
                    "observed_pm25_rows": 18208,
                    "missing_pm25_rows": 10470,
                    "missing_pm25_pct": 36.51,
                    "min_timestamp": "2022-01-01 01:00:00+07:00",
                    "max_timestamp": "2025-04-09 22:00:00+07:00",
                    "train_rows": 22942,
                    "test_rows": 5736,
                    "distance_to_era5_grid_km": 9.026,
                    "winter_years_covered": [2022, 2023, 2024, 2025],
                },
            },
            "weather_backfill": {
                "rows": 28680,
                "max_missing_pct": 0.0,
                "inter_station_distance_7441_to_vn001_km": 7.324,
            },
            "baseline_sha256": {
                "final_processed": "866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd",
            },
            "inference_comparison": {
                "VN001_HANOI_556_NGUYEN_VAN_CU": {
                    "calendar_days": 378,
                    "valid_days_ge18h": 299,
                    "daily_median": 37.2,
                    "daily_median_ci95_calendar_bootstrap": [32.81, 44.83],
                    "winter_daily_median": 60.46,
                    "non_winter_daily_median": 33.58,
                    "kruskal_wallis_h": 61.5344,
                    "kruskal_wallis_epsilon2": 0.2065,
                    "kruskal_wallis_naive_p": 2.7629736724292755e-13,
                    "kruskal_wallis_calendar_bootstrap_p": 0.029485,
                    "winter_vs_nonwinter_r_rb": 0.572,
                    "daily_lag1_autocorr_rho1": 0.7276,
                    "effective_sample_size_n_eff": 47.14,
                    "variance_inflation_factor": 6.34,
                    "qcvn_exceedance_days": 84,
                    "qcvn_exceedance_pct": 28.09,
                },
                "VN003_HANOI_OPENAQ_7441": {
                    "calendar_days": 1195,
                    "valid_days_ge18h": 756,
                    "daily_median": 39.61,
                    "daily_median_ci95_calendar_bootstrap": [35.0, 44.52],
                    "winter_daily_median": 50.05,
                    "non_winter_daily_median": 36.34,
                    "kruskal_wallis_h": 164.1954,
                    "kruskal_wallis_epsilon2": 0.2175,
                    "kruskal_wallis_naive_p": 2.2786024501735895e-35,
                    "kruskal_wallis_calendar_bootstrap_p": 0.0005,
                    "winter_vs_nonwinter_r_rb": 0.3588,
                    "daily_lag1_autocorr_rho1": 0.7487,
                    "effective_sample_size_n_eff": 108.66,
                    "variance_inflation_factor": 6.96,
                    "qcvn_exceedance_days": 238,
                    "qcvn_exceedance_pct": 31.48,
                },
            },
        }
        interp_df = pd.DataFrame([
            {
                "station_id": "VN001_HANOI_556_NGUYEN_VAN_CU",
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
            },
            {
                "station_id": "VN003_HANOI_OPENAQ_7441",
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
            },
        ])
        winter_df = pd.DataFrame([
            {
                "station_id": "VN001_HANOI_556_NGUYEN_VAN_CU",
                "winter_year": 2026,
                "expected_calendar_hours": 2160,
                "station_grid_hours": 2160,
                "count": 1958,
                "coverage_of_full_winter_pct": 90.65,
                "coverage_of_station_grid_pct": 90.65,
                "monthly_completeness": {
                    "2025-12": {"valid_pct": 83.74},
                    "2026-01": {"valid_pct": 91.94},
                    "2026-02": {"valid_pct": 96.88},
                },
                "mean": 63.15,
                "sd": 33.56,
                "median": 57.11,
                "q25": 37.14,
                "q75": 85.75,
                "iqr": 48.61,
                "p90": 110.19,
                "valid_days": 79,
                "qcvn_exceed_days": 47,
                "qcvn_exceed_pct": 59.49,
            },
        ])
        return manifest, ext_meta, interp_df, winter_df

    def test_generate_and_verify_legacy_vs_extended_comparison_report(self):
        """Report generator and verifier run deterministically in a temporary directory."""
        manifest, ext_meta, interp_df, winter_df = self._build_report_fixture()

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
            self.assertTrue(res["verified"], f"Unexpected mismatches: {res['mismatches']}")
            self.assertEqual(len(res["mismatches"]), 0)

    def test_verify_legacy_vs_extended_comparison_catches_mismatches(self):
        """Verifier fails closed when required schema keys or report sections are missing."""
        manifest, ext_meta, interp_df, winter_df = self._build_report_fixture()
        bad_text = "# Incomplete Report without required sections"
        res = verify_legacy_vs_extended_comparison(bad_text, manifest, ext_meta, interp_df, winter_df)
        self.assertFalse(res["verified"])
        self.assertGreater(len(res["mismatches"]), 0)

        # Missing required schema key (e.g., total_rows replaced by legacy typo total_grid_rows)
        bad_meta = dict(ext_meta)
        del bad_meta["total_rows"]
        bad_meta["total_grid_rows"] = 37722
        with self.assertRaisesRegex(KeyError, "total_rows"):
            generate_legacy_vs_extended_comparison_report(manifest, bad_meta, interp_df, winter_df)
        res_schema = verify_legacy_vs_extended_comparison(bad_text, manifest, bad_meta, interp_df, winter_df)
        self.assertFalse(res_schema["verified"])
        self.assertIn("total_rows", res_schema["mismatches"][0])

    def test_verifier_fails_on_mutated_report_metrics(self):
        """F-04 Mutation test: Mutating key metrics in any report table forces verifier to FAIL."""
        manifest, ext_meta, interp_df, winter_df = self._build_report_fixture()
        valid_report = generate_legacy_vs_extended_comparison_report(
            manifest, ext_meta, interp_df, winter_df, output_path=None
        )

        mutations = [
            # 1. Mutate combined total_rows in Section 2 Coverage Table
            ("`37,722`", "`37,999`", "Hourly Grid Rows"),
            # 2. Mutate 2024 valid hours in Section 2 Annual Table
            ("| 7,218 |", "| 7,219 |", "Section 2 Annual Table (year 2024"),
            # 3. Mutate interpolation RMSE in Section 3 Table
            ("| 10.2376 |", "| 10.9999 |", "Section 3 Interpolation Table"),
            # 4. Mutate winter median in Section 4 Winter Table
            ("|**57.11**|" if "|**57.11**|" in valid_report else "| **57.11** |", "| **59.99** |", "Section 4 Winter Table"),
            # 5. Mutate daily lag-1 autocorrelation rho_1 in Section 5 Inference Table
            ("`0.7487`", "`0.5123`", "Calendar-Preserving Daily Lag-1 Autocorrelation"),
            # 6. Mutate Kruskal-Wallis H statistic in Section 5 Inference Table
            ("H = 164.1954", "H = 120.0000", "Seasonal Kruskal–Wallis"),
        ]
        for target_str, replacement_str, expected_mismatch_hint in mutations:
            with self.subTest(mutation=target_str):
                self.assertIn(target_str, valid_report)
                mutated_report = valid_report.replace(target_str, replacement_str, 1)
                res = verify_legacy_vs_extended_comparison(
                    mutated_report, manifest, ext_meta, interp_df, winter_df
                )
                self.assertFalse(
                    res["verified"],
                    f"Verifier failed to catch mutation {target_str!r} -> {replacement_str!r}",
                )
                joined = " | ".join(res["mismatches"])
                self.assertIn(expected_mismatch_hint, joined)
