"""Validate committed Issue #50 artifacts; add ``--real-data`` for source checks.

Two tiers are reported separately:

* ``structural`` — runs everywhere (including CI without ``data/``) and checks
  schemas, arithmetic identities, Holm family, status semantics, figure
  mapping, provenance metadata and frozen-baseline hashes.
* ``semantic`` — requires ``data/`` and independently recomputes the content
  from the pinned Parquet. Without ``data/`` the tier is reported as SKIPPED
  (exit code 2), never as PASS.

Run from the repository root::

    python scripts/validate_extended_reanalysis.py
    python scripts/validate_extended_reanalysis.py --real-data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from PIL import Image

from scripts.run_extended_reanalysis import (
    BASELINE, DATA, FIGURES, META, RAW_MANIFEST, REPORTS, STATIONS, VERSION, sha256,
)
from src.reanalysis_validation import (
    ReanalysisValidationError, ReanalysisValidationSkipped, ValidationSuite,
    load_artifacts, validate_real_data, validate_structural,
)

REQUIRED_COLUMNS = {
    "quality": {
        "station_id", "period_type", "period", "period_start", "period_end_exclusive",
        "expected_calendar_hours", "active_grid_hours", "available_raw_observations",
        "valid_pm25_observations", "invalid_raw_observations", "missing_active_hours",
        "outside_active_window_hours", "missing_pct_active", "coverage_pct_calendar",
        "coverage_pct_active", "gap_count", "longest_missing_gap_hours",
        "median_gap_hours", "sample_size_denominator", "valid_pm25_hours",
        "missing_observed_hours", "missing_source_rows", "invalid_source_rows",
        "duplicate_keys", "nonfinite_pm25_values", "out_of_bounds_pm25_values",
        "negative_sentinel_values", "derived_pm25_hours", "timestamp_order_ok",
        "timezone_consistent", "irregular_sampling_intervals",
        "partial_calendar_period", "dim_completeness_status", "dim_accuracy_status",
        "dim_accuracy_reason", "dim_consistency_status", "dim_validity_status",
        "dim_uniqueness_status", "dim_timeliness_status", "denominator_basis",
    },
    "profile": {
        "station_id", "period_type", "period", "variable", "grid_count",
        "valid_count", "missing_count", "coverage_pct_active", "coverage_pct_calendar",
        "missing_pct_active", "mean", "median", "variance", "sd", "min", "max",
        "q25", "q75", "iqr", "p90", "p95", "skewness", "excess_kurtosis",
    },
    "inference": {
        "station_id", "test", "hypothesis_h0", "test_design", "statistical_decision",
        "evidence_level", "analysis_start", "analysis_end", "n_valid_days",
        "statistic_name", "statistic", "raw_iid_p_value", "dependence_aware_p_value",
        "holm_p_value", "primary_estimand", "primary_unit", "primary_estimate",
        "primary_ci_low", "primary_ci_high", "primary_ci_method", "effect_size_name",
        "effect_size", "effect_size_ci_low", "effect_size_ci_high",
        "effect_size_ci_status", "secondary_estimand", "secondary_estimate",
        "secondary_ci_low", "secondary_ci_high", "secondary_ci_method",
        "secondary_effect_size_name", "secondary_effect_size",
        "secondary_effect_size_ci_status", "ci_status", "interpretation_scope",
        "method", "assumptions", "status", "status_reason", "conclusion",
        "interpretation",
    },
    "sensitivity": {
        "station_id", "test", "axis", "setting", "p_value", "reject_at_0_05",
        "n_days", "estimate", "ci_low", "ci_high", "n_hours",
        "coverage_pct_calendar", "partial_window",
    },
    "figures": {
        "figure", "research_question", "decision", "reason", "dataset_version",
        "station_id", "start", "end", "n_observed_pm25", "coverage_pct_active",
        "partial_periods", "limitation", "existing_figure", "extended_figure",
        "supplementary_figure",
    },
}

FIGURE_FILES = {
    "FIG-01": "figures/FIG-01-extended-historical.png",
    "FIG-02": "figures/extended/FIG-02-extended.png",
    "FIG-03": "figures/extended/FIG-03-extended.png",
}


def _require_columns(suite: ValidationSuite, name: str, frame: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS[name].difference(frame.columns)
    suite.true(f"{name}.schema", not missing, f"missing columns: {sorted(missing)}")


def validate_provenance(suite: ValidationSuite, config: dict, meta: dict, manifest: dict) -> None:
    suite.equal("provenance.version", meta.get("dataset_version"), VERSION)
    suite.equal(
        "provenance.path", meta.get("path"),
        str(DATA.relative_to(ROOT)).replace("\\", "/"),
    )
    suite.true("provenance.sha_snapshot", bool(meta.get("sha256")), "snapshot SHA missing")
    suite.equal("provenance.config_snapshot", config.get("dataset_sha256_snapshot"), meta.get("sha256"))
    suite.true("provenance.config_actual", bool(config.get("dataset_sha256_actual")), "actual SHA missing")
    suite.true("provenance.raw_path", bool(manifest.get("raw_parquet_path")), "raw path missing")
    suite.true("provenance.raw_sha", bool(manifest.get("raw_parquet_sha256")), "raw SHA missing")
    stations = meta.get("stations", {})
    suite.equal("provenance.stations", set(stations), set(STATIONS))
    suite.equal(
        "provenance.total_rows", meta.get("total_rows"),
        sum(int(entry["grid_rows"]) for entry in stations.values()),
    )
    for station, entry in stations.items():
        suite.true(
            f"provenance.{station}.grid", int(entry["grid_rows"]) > 0, "empty station",
        )
        suite.true(
            f"provenance.{station}.observed",
            0 < int(entry["observed_pm25_rows"]) <= int(entry["grid_rows"]),
            "observed count outside grid",
        )
        suite.true(
            f"provenance.{station}.derived",
            0 <= int(entry["derived_interpolated_2h_rows"]) <= int(entry["grid_rows"]),
            "derived count outside grid",
        )
        suite.equal(
            f"provenance.{station}.split",
            int(entry["train_rows"]) + int(entry["test_rows"]),
            int(entry["grid_rows"]),
        )
    suite.true(
        "provenance.weather", bool(meta.get("weather_backfill", {}).get("raw_path")),
        "weather provenance missing",
    )
    for key in ("numpy", "pandas", "scipy"):
        suite.true(f"config.library.{key}", bool(config.get(key)), f"{key} version not recorded")


def validate_baseline_hashes(suite: ValidationSuite, *, real_data: bool) -> None:
    path = REPORTS / "issue50_baseline_hashes.json"
    suite.true("baseline.hash_file", path.is_file(), "issue50_baseline_hashes.json missing")
    if not path.is_file():
        return
    hashes = json.loads(path.read_text(encoding="utf-8"))
    suite.equal("baseline.before_after", hashes.get("before_reanalysis"), hashes.get("after_reanalysis"))
    suite.true("baseline.unchanged_flag", bool(hashes.get("all_present_unchanged")), "runner did not assert unchanged")
    for name, digest in hashes.get("before", {}).items():
        suite.equal(f"baseline.preflight.{name}", hashes.get("after_reanalysis", {}).get(name), digest)
    for name, digest in hashes.get("after_reanalysis", {}).items():
        file_path = ROOT / name
        if not file_path.exists():
            suite.true(
                f"baseline.missing.{name}",
                not real_data and name.startswith(("data/processed/", "data/interim/")),
                f"baseline artifact missing: {name}",
            )
            continue
        if digest is not None:
            suite.equal(f"baseline.sha.{name}", sha256(file_path), digest)
    for name in BASELINE:
        suite.true(f"baseline.listed.{name}", name in hashes.get("after_reanalysis", {}), "baseline entry missing")


def validate_gaps(suite: ValidationSuite, gaps: pd.DataFrame) -> None:
    suite.true("gaps.rows", len(gaps) > 0, "no missing runs recorded")
    if gaps.empty:
        return
    suite.true("gaps.positive", (gaps["gap_hours"] > 0).all(), "non-positive gap")
    suite.true("gaps.order", (gaps["start"] <= gaps["end"]).all(), "gap start after end")
    suite.true("gaps.stations", set(gaps["station_id"]) <= set(STATIONS), "unknown station in gaps")


def validate_figure_files(suite: ValidationSuite, figures: pd.DataFrame) -> None:
    for figure, path in FIGURE_FILES.items():
        file_path = ROOT / path
        suite.true(f"figures.file.{figure}", file_path.is_file(), f"missing {path}")
        if file_path.is_file():
            with Image.open(file_path) as image:
                suite.true(
                    f"figures.dpi.{figure}",
                    abs(image.info.get("dpi", (0, 0))[0] - 300) <= 1,
                    "DPI is below 300",
                )
    supplementary = FIGURES / "FIG-03b-winter-coverage.png"
    suite.true("figures.file.FIG-03b", supplementary.is_file(), "winter coverage QC figure missing")
    if supplementary.is_file():
        with Image.open(supplementary) as image:
            suite.true(
                "figures.dpi.FIG-03b",
                abs(image.info.get("dpi", (0, 0))[0] - 300) <= 1,
                "DPI is below 300",
            )
    for _, row in figures.iterrows():
        if row["decision"] == "EXTEND" and pd.notna(row["extended_figure"]):
            path = ROOT / str(row["extended_figure"])
            suite.true(f"figures.mapped.{row['figure']}", path.is_file(), f"missing {path}")
        if pd.notna(row["supplementary_figure"]):
            path = ROOT / str(row["supplementary_figure"])
            suite.true(f"figures.supplementary.{row['figure']}", path.is_file(), f"missing {path}")


def validate_reports(suite: ValidationSuite) -> None:
    expected = {
        "extended_data_quality_audit.md": ("UNVERIFIABLE", "missing_source_rows", "outside_active_window_hours"),
        "extended_inference_results.md": ("primary", "secondary", "ci_status", "HAC"),
        "extended_preprocessing_validation.md": ("observed", "derived"),
        "extended_leakage_audit.md": ("station-specific", "Protocol B"),
        "extended_eda_findings.md": ("partial", "descriptive"),
        "extended_reanalysis_comparison.md": ("INCOMPARABLE", "UNVERIFIED", "EXPLORATORY"),
    }
    for name, tokens in expected.items():
        path = REPORTS / name
        suite.true(f"reports.file.{name}", path.is_file(), f"missing {name}")
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            suite.true(f"reports.{name}.{token}", token in text, f"missing token {token!r}")


def validate_dataset_content(data: pd.DataFrame, *, suite: ValidationSuite, config: dict, meta: dict) -> None:
    """Provenance/content fingerprint and leakage-safety checks (G1/G3)."""
    suite.equal("data.rows", len(data), int(meta["total_rows"]))
    suite.equal("data.schema", list(data.columns), list(meta["columns"]))
    suite.equal("data.stations", set(data["station_id"].dropna()), set(STATIONS))
    suite.true("data.station_null", not data["station_id"].isna().any(), "null station id")
    suite.true(
        "data.timestamp_tz",
        isinstance(data["timestamp"].dtype, pd.DatetimeTZDtype)
        and str(data["timestamp"].dt.tz) == "Asia/Ho_Chi_Minh"
        and not data["timestamp"].isna().any(),
        "timestamps are not non-null Asia/Ho_Chi_Minh",
    )
    suite.true(
        "data.unique_key",
        not data.duplicated(["station_id", "timestamp"]).any(),
        "duplicate (station_id, timestamp) key",
    )
    for station, part in data.groupby("station_id"):
        part = part.sort_values("timestamp")
        suite.true(
            f"data.{station}.hourly_grid",
            (part["timestamp"].diff().dropna() == pd.Timedelta(hours=1)).all(),
            "hidden grid gap or irregular hourly step",
        )
        suite.true(
            f"data.{station}.monotonic",
            part["timestamp"].is_monotonic_increasing,
            "timestamps are not chronological",
        )
        entry = meta["stations"][station]
        suite.equal(f"data.{station}.grid_rows", len(part), int(entry["grid_rows"]))
        suite.equal(
            f"data.{station}.observed_rows",
            int(part["pm25"].notna().sum()),
            int(entry["observed_pm25_rows"]),
        )
        suite.equal(
            f"data.{station}.derived_rows",
            int(part["pm25_is_derived"].sum()),
            int(entry["derived_interpolated_2h_rows"]),
        )
        suite.equal(f"data.{station}.min_timestamp", str(part["timestamp"].min()), entry["min_timestamp"])
        suite.equal(f"data.{station}.max_timestamp", str(part["timestamp"].max()), entry["max_timestamp"])
        suite.equal(
            f"data.{station}.split",
            part["split"].value_counts().to_dict(),
            {"train": int(entry["train_rows"]), "test": int(entry["test_rows"])},
        )
        suite.true(
            f"data.{station}.pm25_bounds",
            part["pm25"].dropna().between(0, 1000).all(),
            "observed PM2.5 outside physical bounds",
        )
        suite.true(
            f"data.{station}.derived_flag",
            part.loc[part["pm25"].isna(), "pm25_is_derived"].equals(
                part.loc[part["pm25"].isna(), "pm25_derived_interpolated"].notna()
            ),
            "derived flag disagrees with observed/derived cells",
        )
        observed = part.loc[part["pm25"].notna(), ["pm25", "pm25_derived_interpolated"]]
        suite.true(
            f"data.{station}.observed_immutable",
            observed["pm25"].equals(observed["pm25_derived_interpolated"]),
            "derived column changed an observed cell",
        )
    spans = data.groupby("station_id")["timestamp"].agg(["min", "max"])
    first_station, second_station = sorted(STATIONS)
    suite.true(
        "data.spans_disjoint",
        spans.loc[first_station, "min"] > spans.loc[second_station, "max"]
        or spans.loc[second_station, "min"] > spans.loc[first_station, "max"],
        "station spans overlap, so a pooled comparison could be mistaken for a trend",
    )
    # Raw VN003 payload must still match its frozen manifest.
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    raw_path = ROOT / manifest["raw_parquet_path"]
    suite.true("data.raw_vn003", raw_path.is_file(), f"missing {raw_path}")
    if raw_path.is_file():
        suite.equal("data.raw_vn003_sha256", sha256(raw_path), manifest["raw_parquet_sha256"])
    actual = sha256(DATA)
    suite.equal("data.sha256_actual", actual, config.get("dataset_sha256_actual"))
    weather_path = ROOT / meta["weather_backfill"]["raw_path"]
    suite.true("data.weather_raw", weather_path.is_file(), "missing ERA5 raw payload")
    if weather_path.is_file():
        payload = json.loads(weather_path.read_text(encoding="utf-8"))
        suite.equal(
            "data.weather_rows",
            len(payload.get("hourly", {}).get("time", [])),
            int(meta["weather_backfill"]["rows"]),
        )
        suite.equal("data.weather_sha256", sha256(weather_path), config.get("weather_raw_sha256_actual"))


def validate_outputs(*, real_data: bool = False, bootstrap: bool = True) -> dict:
    config = json.loads((REPORTS / "extended_reanalysis_config.json").read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    suite = ValidationSuite("structural")
    suite.equal("config.dataset_version", config.get("dataset_version"), VERSION)
    artifacts = load_artifacts(REPORTS)
    for name, frame in artifacts.items():
        if name in REQUIRED_COLUMNS:
            _require_columns(suite, name, frame)
    validate_provenance(suite, config, meta, manifest)
    validate_structural(artifacts, config=config, suite=suite)
    for key in ("quality", "profile", "inference", "sensitivity", "figures"):
        suite.true(f"artifacts.{key}.rows", len(artifacts[key]) > 0, "empty artifact")
    validate_gaps(suite, artifacts["gaps"])
    validate_figure_files(suite, artifacts["figures"])
    validate_reports(suite)
    validate_baseline_hashes(suite, real_data=real_data and DATA.is_file())
    structural_summary = {
        "status": "PASS",
        "checks": suite.checks,
        "failure_count": len(suite.failures),
        "failures": suite.failures[:20],
    }
    if suite.failures:
        raise ReanalysisValidationError("structural", suite.failures, suite.checks)

    semantic_summary: dict = {"status": "SKIPPED", "reason": "run with --real-data to recompute from data/"}
    if real_data:
        if not DATA.is_file():
            raise ReanalysisValidationSkipped(
                f"{DATA} is absent; semantic validation is SKIPPED, not passed"
            )
        data = pd.read_parquet(DATA)
        baseline = pd.read_parquet(ROOT / "data/processed/air_pollution_final.parquet")
        raw_vn003 = pd.read_parquet(ROOT / manifest["raw_parquet_path"])
        content_suite = ValidationSuite("semantic-content")
        validate_dataset_content(data, suite=content_suite, config=config, meta=meta)
        content_suite.finish()
        semantic = validate_real_data(
            data,
            baseline=baseline,
            raw_vn003=raw_vn003,
            artifacts=artifacts,
            config=config,
            reports_dir=REPORTS,
            figures_dir=FIGURES,
            bootstrap=bootstrap,
        )
        semantic_summary = {"status": "PASS", **semantic}

    return {
        "status": "PASS",
        "dataset_version": VERSION,
        "tiers": {"structural": structural_summary, "semantic": semantic_summary},
        "quality_rows": len(artifacts["quality"]),
        "profile_rows": len(artifacts["profile"]),
        "inference_rows": len(artifacts["inference"]),
        "sensitivity_rows": len(artifacts["sensitivity"]),
        "figure_audit_rows": len(artifacts["figures"]),
        "baseline_unchanged": True,
        "real_data_checked": bool(real_data),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-data", action="store_true")
    parser.add_argument(
        "--skip-bootstrap", action="store_true",
        help="recompute deterministic content only (faster, still semantic)",
    )
    args = parser.parse_args()
    try:
        result = validate_outputs(
            real_data=args.real_data, bootstrap=not args.skip_bootstrap,
        )
    except ReanalysisValidationSkipped as skipped:
        print(json.dumps({"status": "SKIPPED", "reason": str(skipped)}, indent=2))
        raise SystemExit(2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
