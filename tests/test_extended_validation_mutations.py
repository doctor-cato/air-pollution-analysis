"""Mutation checks: structural CI gates and semantic real-source gates stay distinct."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import validate_extended_reanalysis as validator
from src.reanalysis_validation import (
    ReanalysisValidationError, ReanalysisValidationSkipped, ValidationSuite,
    load_artifacts, recompute_profile, recompute_quality,
    validate_comparison_semantics, validate_profile_semantics,
    validate_quality_semantics, validate_structural,
)


class TestStructuralMutations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = load_artifacts(validator.REPORTS)
        cls.config = json.loads((validator.REPORTS / "extended_reanalysis_config.json").read_text(encoding="utf-8"))

    def assert_rejected(self, table: str, column: str, value, expected: str) -> None:
        artifacts = dict(self.artifacts)
        artifacts[table] = artifacts[table].copy()
        artifacts[table].loc[0, column] = value
        suite = ValidationSuite("structural")
        with self.assertRaises(ReanalysisValidationError) as error:
            validate_structural(artifacts, config=self.config, suite=suite)
        self.assertIn(expected, str(error.exception))

    def test_mutation_01_wrong_calendar_coverage(self):
        self.assert_rejected("quality", "coverage_pct_calendar", 100., "quality.coverage_calendar")

    def test_mutation_02_invalid_grid_denominator(self):
        self.assert_rejected("quality", "expected_calendar_hours", 1, "quality.calendar_denominator")

    def test_mutation_03_device_accuracy_cannot_be_pass(self):
        self.assert_rejected("quality", "dim_accuracy_status", "PASS", "quality.accuracy_unverifiable")

    def test_other_weather_bound_violation_cannot_pass_validity(self):
        self.assert_rejected("quality", "other_bound_violations", 1, "quality.validity_status")

    def test_mutation_04_holm_family_cannot_change(self):
        self.assert_rejected("inference", "holm_p_value", 0.9, "holm")

    def test_mutation_05_season_cannot_be_confirmatory(self):
        self.assert_rejected("inference", "test_design", "confirmatory", "season_design")

    def test_mutation_06_figure_three_cannot_lose_monthly_mapping(self):
        artifacts = dict(self.artifacts)
        artifacts["figures"] = artifacts["figures"].copy()
        mask = artifacts["figures"]["figure"] == "FIG-03"
        artifacts["figures"].loc[mask, "research_question"] = "Winter coverage only"
        suite = ValidationSuite("structural")
        with self.assertRaises(ReanalysisValidationError) as error:
            validate_structural(artifacts, config=self.config, suite=suite)
        self.assertIn("FIG-03.semantics", str(error.exception))

    def test_requested_real_data_is_skipped_if_data_missing(self):
        original = Path.is_file
        original_exists = Path.exists
        def missing_local_data(path):
            return (
                False if path.is_relative_to(validator.ROOT / "data" / "processed")
                or path.is_relative_to(validator.ROOT / "data" / "interim")
                else original_exists(path)
            )
        with patch.object(Path, "is_file", lambda path: False if path == validator.DATA else original(path)):
            with patch.object(Path, "exists", missing_local_data):
                with self.assertRaises(ReanalysisValidationSkipped):
                    validator.validate_outputs(real_data=True)


class TestSemanticMutations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not validator.DATA.is_file():
            raise unittest.SkipTest("real processed Parquet absent; semantic mutations skipped")
        cls.data = pd.read_parquet(validator.DATA)
        manifest = json.loads(validator.RAW_MANIFEST.read_text(encoding="utf-8"))
        cls.raw = pd.read_parquet(validator.ROOT / manifest["raw_parquet_path"])
        cls.artifacts = load_artifacts(validator.REPORTS)
        cls.quality = recompute_quality(cls.data, cls.raw)
        cls.profile = recompute_profile(cls.data)

    def assert_semantic_rejected(self, table: str, row: int, column: str, value, expected: str) -> None:
        mutated = self.artifacts[table].copy()
        mutated.loc[row, column] = value
        suite = ValidationSuite("semantic")
        with self.assertRaises(ReanalysisValidationError) as error:
            if table == "quality":
                validate_quality_semantics(mutated, self.quality, suite)
            else:
                validate_profile_semantics(mutated, self.profile, suite)
            suite.finish()
        self.assertIn(expected, str(error.exception))

    def test_mutation_07_valid_count_with_unchanged_denominator(self):
        self.assert_semantic_rejected("quality", 0, "valid_pm25_observations", 1, "valid_pm25_observations")

    def test_mutation_08_longest_gap_concealed(self):
        self.assert_semantic_rejected("quality", 0, "longest_missing_gap_hours", 0, "longest_missing_gap_hours")

    def test_mutation_09_missing_source_rows_concealed(self):
        row = self.artifacts["quality"].loc[
            (self.artifacts["quality"].station_id == "VN003_HANOI_OPENAQ_7441")
            & (self.artifacts["quality"].period_type == "station")
        ].index[0]
        self.assert_semantic_rejected("quality", row, "missing_source_rows", 0, "missing_source_rows")

    def test_weather_bound_violation_and_status_cannot_be_invented_together(self):
        mutated = self.artifacts["quality"].copy()
        mutated.loc[0, "other_bound_violations"] = 1
        mutated.loc[0, "dim_validity_status"] = "FAIL"
        suite = ValidationSuite("semantic")
        with self.assertRaises(ReanalysisValidationError) as error:
            validate_quality_semantics(mutated, self.quality, suite)
            suite.finish()
        self.assertIn("other_bound_violations", str(error.exception))

    def test_mutation_10_station_median_changed(self):
        self.assert_semantic_rejected("profile", 0, "median", 999., "median")

    def test_mutation_11_station_sd_changed(self):
        self.assert_semantic_rejected("profile", 0, "sd", 999., "sd")

    def test_mutation_12_monthly_coverage_changed(self):
        row = self.artifacts["profile"].loc[
            self.artifacts["profile"].period_type == "month"
        ].index[0]
        self.assert_semantic_rejected("profile", row, "coverage_pct_calendar", 100., "coverage_pct_calendar")

    def test_comparison_test_row_cannot_hide_changed_estimate(self):
        path = validator.REPORTS / "extended_reanalysis_comparison.md"
        text = path.read_text(encoding="utf-8")
        line = next(line for line in text.splitlines() if line.startswith("| qcvn_annual |"))
        corrupted = text.replace(line, line.replace("43.38", "99.99"), 1)
        self.assertNotEqual(text, corrupted)
        config = json.loads((validator.REPORTS / "extended_reanalysis_config.json").read_text(encoding="utf-8"))
        config["_inference_path"] = validator.REPORTS / "extended_inference_results.csv"
        suite = ValidationSuite("semantic")
        baseline = pd.read_parquet(validator.ROOT / "data/processed/air_pollution_final.parquet")
        with self.assertRaises(ReanalysisValidationError) as error:
            validate_comparison_semantics(self.data, baseline, corrupted, config=config, suite=suite)
            suite.finish()
        self.assertIn("comparison.concordance.qcvn_annual", str(error.exception))
