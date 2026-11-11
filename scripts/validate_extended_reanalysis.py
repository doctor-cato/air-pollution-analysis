"""Validate committed Issue #50 artifacts; add --real-data for local source checks."""
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

from scripts.run_extended_reanalysis import FIGURES, REPORTS, STATIONS, VERSION, sha256, validate_dataset
from src.inference import holm_adjust


def validate_outputs(*, real_data: bool = False) -> dict:
    config = json.loads((REPORTS/"extended_reanalysis_config.json").read_text(encoding="utf-8"))
    if config["dataset_version"] != VERSION:
        raise AssertionError("Wrong dataset version in output config")
    quality = pd.read_csv(REPORTS/"extended_data_quality_by_station_year_season.csv")
    profile = pd.read_csv(REPORTS/"extended_statistical_profile.csv")
    inference = pd.read_csv(REPORTS/"extended_inference_results.csv")
    sensitivity = pd.read_csv(REPORTS/"extended_inference_sensitivity.csv")
    figures = pd.read_csv(REPORTS/"extended_figure_audit.csv")
    if set(quality.station_id) != STATIONS or set(profile.station_id) != STATIONS or set(inference.station_id) != STATIONS:
        raise AssertionError("Station identity lost in a report")
    if set(quality.period_type) != {"station", "year", "month", "winter_year", "season_year"}:
        raise AssertionError("Missing QC grouping")
    if not ((quality.valid_pm25_observations + quality.missing_active_hours) == quality.active_grid_hours).all():
        raise AssertionError("QC active-grid denominator error")
    if not np.allclose(quality.coverage_pct_calendar, 100*quality.valid_pm25_observations/quality.expected_calendar_hours):
        raise AssertionError("QC calendar denominator error")
    if not ((profile.valid_count + profile.missing_count) == profile.grid_count).all():
        raise AssertionError("Profile denominator error")
    if set(inference.test) != {"season_effect", "weekday_effect", "qcvn_24h", "qcvn_annual"}:
        raise AssertionError("Baseline four-test Holm family changed")
    for station, frame in inference.groupby("station_id"):
        if len(frame) != 4 or not np.allclose(frame.holm_p_value, holm_adjust(frame.dependence_aware_p_value)):
            raise AssertionError(f"Holm family inconsistency at {station}")
        if frame.loc[frame.test == "season_effect", "status"].iloc[0] != "exploratory":
            raise AssertionError("Seasonal inference was incorrectly upgraded")
        if not frame[["ci_low", "ci_high"]].notna().all().all():
            raise AssertionError("Missing reported effect/location CI")
    if set(figures.figure) != {f"FIG-{i:02d}" for i in range(1,8)} or len(figures) != 14:
        raise AssertionError("Figure audit incomplete")
    for name in ("FIG-02-extended.png", "FIG-03-extended.png"):
        with Image.open(FIGURES/name) as image:
            if abs(image.info["dpi"][0]-300) > 1:
                raise AssertionError("Figure DPI mismatch")
    hashes = json.loads((REPORTS/"issue50_baseline_hashes.json").read_text(encoding="utf-8"))
    if hashes["before_reanalysis"] != hashes["after_reanalysis"]:
        raise AssertionError("Baseline artifact hash changed")
    for name, digest in hashes.get("before", {}).items():
        if hashes["after_reanalysis"].get(name) != digest:
            raise AssertionError(f"Preflight baseline hash changed: {name}")
    for name, digest in hashes["after_reanalysis"].items():
        path = ROOT/name
        if not path.exists() and not real_data and name.startswith(("data/processed/", "data/interim/")):
            continue
        if digest is not None and (not path.exists() or sha256(path) != digest):
            raise AssertionError(f"Committed baseline artifact differs from recorded hash: {name}")
    if real_data:
        data, actual = validate_dataset()
        if len(data) != int(quality.loc[quality.period_type == "station", "active_grid_hours"].sum()):
            raise AssertionError("Real dataset row count differs from QC output")
        if config["dataset_sha256_actual"] != actual["actual_sha256"]:
            raise AssertionError("Real dataset SHA-256 differs from runner output")
    return {"quality_rows": len(quality), "profile_rows": len(profile), "inference_rows": len(inference),
            "sensitivity_rows": len(sensitivity), "figure_audit_rows": len(figures),
            "baseline_unchanged": True, "real_data_checked": real_data}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-data", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate_outputs(real_data=args.real_data), indent=2))


if __name__ == "__main__":
    main()
