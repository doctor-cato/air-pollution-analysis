"""Issue #50: reproduce station-separated M2/M3/W9 evidence from the pinned dataset.

Run from the repository root: python scripts/run_extended_reanalysis.py
The script reads data/ only and writes reports/extended_* and figures/extended/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cleaning import validate_cleaned_dataset
from src.data_quality import ATMOSPHERIC_BOUNDS, audit_six_dimensions
from src.extended_audit import compare_station_evidence, group_quality_dimensions
from src.inference import (
    BLOCK_LENGTH_DAYS, HAC_LAG_DAILY, N_NULL_BOOTSTRAP,
    build_daily_calendar, build_daily_panel, calendar_bootstrap_ci, run_inference,
)
from src.issue44_preparation import validate_modeling_split, vietnam_season, winter_year
from src.visualizer import configure_vietnamese_fonts

DATA = ROOT / "data/processed/air_pollution_extended_2022_2026.parquet"
META = ROOT / "reports/issue44_extended_dataset_metadata.json"
RAW_MANIFEST = ROOT / "reports/issue44_openaq_7441_manifest.json"
REPORTS = ROOT / "reports"
FIGURES = ROOT / "figures/extended"
VERSION = "2.0.0-issue44-extended"
STATIONS = {"VN001_HANOI_556_NGUYEN_VAN_CU", "VN003_HANOI_OPENAQ_7441"}
BASELINE = [
    "data/processed/air_pollution_final.parquet",
    "data/interim/air_quality_canonical.parquet",
    "data/interim/weather_canonical.parquet",
    "data/raw/metadata.json",
    "reports/statistical_profile.csv", "reports/inference_results.md",
    *(f"figures/FIG-{i:02d}.png" for i in range(1, 13)),
    "figures/FIG-01-extended-historical.png",
    "reports/issue44_extended_dataset_metadata.json",
    "reports/issue44_legacy_vs_extended_comparison.md",
    "reports/issue44_multiyear_eda_summary.csv",
    "reports/issue44_interpolation_evaluation.csv",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_hashes() -> dict[str, str | None]:
    return {name: sha256(ROOT / name) if (ROOT / name).exists() else None for name in BASELINE}


def validate_input_frame(df: pd.DataFrame) -> None:
    required = {"station_id", "timestamp", "pm25", "pm25_derived_interpolated",
                "pm25_is_derived", "season", "winter_year", "split"}
    if missing := required.difference(df.columns):
        raise ValueError(f"Missing extended dataset columns: {sorted(missing)}")
    if set(df.station_id.dropna()) != STATIONS or df.station_id.isna().any():
        raise ValueError("Unapproved or missing station identity")
    if not isinstance(df.timestamp.dtype, pd.DatetimeTZDtype) or str(df.timestamp.dt.tz) != "Asia/Ho_Chi_Minh" or df.timestamp.isna().any():
        raise ValueError("Timestamps must be non-null Asia/Ho_Chi_Minh")
    if df.duplicated(["station_id", "timestamp"]).any():
        raise ValueError("Duplicate station/timestamp key")
    if not pd.api.types.is_numeric_dtype(df.pm25):
        raise ValueError("PM2.5 must be numeric")
    observed = df.pm25.dropna()
    if not np.isfinite(observed).all() or not observed.between(0, 1000).all():
        raise ValueError("Invalid observed PM2.5 value")
    for column, bounds in ATMOSPHERIC_BOUNDS.items():
        if column in df.columns:
            values = df[column].dropna()
            if not pd.api.types.is_numeric_dtype(values) or not np.isfinite(values).all() or not values.between(bounds["min"], bounds["max"]).all():
                raise ValueError(f"Invalid physical values in {column}")
    if df.pm25_is_derived.isna().any() or not pd.api.types.is_bool_dtype(df.pm25_is_derived):
        raise ValueError("Invalid derived flag")
    if not df.loc[df.pm25.notna(), "pm25_derived_interpolated"].equals(df.loc[df.pm25.notna(), "pm25"]):
        raise ValueError("Derived column changed an observed PM2.5 cell")
    derived = df.pm25_derived_interpolated.dropna()
    if not pd.api.types.is_numeric_dtype(derived) or not np.isfinite(derived).all() or not derived.between(0, 1000).all():
        raise ValueError("Invalid derived PM2.5 value")
    expected_derived = df.pm25.isna() & df.pm25_derived_interpolated.notna()
    if not df.pm25_is_derived.eq(expected_derived).all():
        raise ValueError("Derived flag and observed/derived cells disagree")
    if not df.season.equals(vietnam_season(df.timestamp)) or not df.winter_year.equals(winter_year(df.timestamp)):
        raise ValueError("Season/winter_year is misaligned with local timestamps")
    validate_modeling_split(df, protocol="station_specific")
    for station, part in df.groupby("station_id"):
        if not part.timestamp.is_monotonic_increasing or not (part.timestamp.diff().dropna() == pd.Timedelta(hours=1)).all():
            raise ValueError(f"Hidden grid gap or order error: {station}")


def assert_observed_cells_unchanged(baseline: pd.DataFrame, extended: pd.DataFrame) -> None:
    """Compare baseline cells to extended cells by key, treating NaN as unchanged.

    ``DataFrame.equals`` is dtype-strict: the same cell read as
    datetime64[ns] in one Parquet and datetime64[us] in another makes a
    correct frame compare unequal. Timestamp resolution is not part of the
    data contract, so the audit aligns on ``(station_id, timestamp)`` and
    compares only the observed values, where a NaN must stay NaN.
    """
    keys = ["station_id", "timestamp"]
    old = baseline[keys + ["pm25"]]
    new = extended[keys + ["pm25"]]
    merged = old.merge(new, on=keys, how="outer", suffixes=("_baseline", "_extended"),
                       indicator=True)
    if len(merged) != len(old) or len(merged) != len(new) or not merged["_merge"].eq("both").all():
        raise ValueError("Extended dataset changed baseline VN001 observation keys")
    before, after = merged["pm25_baseline"], merged["pm25_extended"]
    if not (before.eq(after) | (before.isna() & after.isna())).all():
        raise ValueError("Extended dataset changed baseline VN001 observations")


def validate_dataset(path: Path = DATA, metadata_path: Path = META) -> tuple[pd.DataFrame, dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing real dataset: {path}. Reproduce with scripts/build_extended_historical_dataset.py")
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    if meta.get("dataset_version") != VERSION or meta.get("path") != str(DATA.relative_to(ROOT)).replace("\\", "/"):
        raise ValueError("Extended dataset version/path does not match Issue #44 contract")
    df = pd.read_parquet(path)
    if list(df.columns) != meta["columns"] or len(df) != meta["total_rows"]:
        raise ValueError("Extended dataset schema/row count differs from provenance metadata")
    validate_input_frame(df)
    for station, part in df.groupby("station_id"):
        if not validate_cleaned_dataset(part)["all_passed"]:
            raise ValueError(f"Deterministic cleaning contract failed: {station}")
        recorded = meta["stations"][station]
        if (len(part) != recorded["grid_rows"] or int(part.pm25.notna().sum()) != recorded["observed_pm25_rows"]
                or int(part.pm25_is_derived.sum()) != recorded["derived_interpolated_2h_rows"]
                or str(part.timestamp.min()) != recorded["min_timestamp"]
                or str(part.timestamp.max()) != recorded["max_timestamp"]):
            raise ValueError(f"Station content differs from provenance metadata: {station}")
        if part.split.value_counts().to_dict() != {"train": recorded["train_rows"], "test": recorded["test_rows"]}:
            raise ValueError(f"Split counts differ from metadata: {station}")
    baseline = ROOT / "data/processed/air_pollution_final.parquet"
    if not baseline.is_file():
        raise FileNotFoundError("Missing baseline Parquet for observed-cell immutability audit")
    old = pd.read_parquet(baseline)[["station_id", "timestamp", "pm25"]]
    new = df.loc[df.station_id == "VN001_HANOI_556_NGUYEN_VAN_CU", old.columns]
    assert_observed_cells_unchanged(old, new)
    manifest = json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))
    raw = ROOT / manifest["raw_parquet_path"]
    if not raw.is_file() or sha256(raw) != manifest["raw_parquet_sha256"]:
        raise ValueError("Pinned VN003 raw source is missing or checksum differs")
    weather = ROOT / meta["weather_backfill"]["raw_path"]
    if not weather.is_file():
        raise ValueError("ERA5 raw source is missing")
    weather_payload = json.loads(weather.read_text(encoding="utf-8"))
    if len(weather_payload.get("hourly", {}).get("time", [])) != meta["weather_backfill"]["rows"]:
        raise ValueError("ERA5 source hourly count differs from provenance metadata")
    # Open-Meteo serves a live reanalysis; retain both raw hashes rather than silently
    # rewriting the frozen Issue #44 provenance when its response bytes change.
    meta["weather_raw_sha256_actual"] = sha256(weather)
    meta["weather_raw_snapshot_match"] = meta["weather_raw_sha256_actual"] == meta["weather_backfill"]["raw_sha256"]
    # Parquet byte hashes may vary by library version; content/manifest guards above are authoritative.
    meta["actual_sha256"] = sha256(path)
    meta["snapshot_sha256_match"] = meta["actual_sha256"] == meta["sha256"]
    return df, meta


def period_groups(part: pd.DataFrame):
    ts = part.timestamp
    yield "station", "all", part, ts.min(), ts.max() + pd.Timedelta(hours=1)
    for year in sorted(ts.dt.year.unique()):
        start = pd.Timestamp(f"{year}-01-01", tz=ts.dt.tz)
        end = pd.Timestamp(f"{year+1}-01-01", tz=ts.dt.tz)
        yield "year", str(year), part.loc[(ts >= start) & (ts < end)], start, end
    for month in sorted(ts.dt.strftime("%Y-%m").unique()):
        start = pd.Timestamp(f"{month}-01", tz=ts.dt.tz)
        end = start + pd.DateOffset(months=1)
        yield "month", month, part.loc[(ts >= start) & (ts < end)], start, end
    season_month = {"Winter (Dec-Feb)": 12, "Spring (Mar-May)": 3,
                    "Summer (Jun-Aug)": 6, "Autumn (Sep-Nov)": 9}
    years = sorted(set(ts.dt.year) | {int(ts.dt.year.max()) + 1})
    for year in years:
        for name, month in season_month.items():
            start_year = year - 1 if month == 12 else year
            start = pd.Timestamp(year=start_year, month=month, day=1, tz=ts.dt.tz)
            end = start + pd.DateOffset(months=3)
            scoped = part.loc[(ts >= start) & (ts < end)]
            if not scoped.empty:
                kind = "winter_year" if month == 12 else "season_year"
                yield kind, f"{name}:{year}", scoped, start, end


def missing_runs(part: pd.DataFrame) -> pd.DataFrame:
    records = []
    for station, group in part.groupby("station_id"):
        missing = group.pm25.isna().to_numpy()
        changes = np.r_[True, missing[1:] != missing[:-1]]
        ids = np.cumsum(changes)
        for _, run in group.loc[missing].groupby(ids[missing]):
            records.append({"station_id": station, "start": str(run.timestamp.iloc[0]),
                            "end": str(run.timestamp.iloc[-1]), "gap_hours": len(run),
                            "year": int(run.timestamp.iloc[0].year),
                            "season": str(run.season.iloc[0]) if "season" in run else "UNAVAILABLE"})
    return pd.DataFrame(records)


def quality_and_profile(df: pd.DataFrame, raw_vn003: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    quality, profile = [], []
    gaps = missing_runs(df)
    audits = {}
    raw_vn003 = raw_vn003.copy()
    raw_vn003["timestamp"] = pd.to_datetime(raw_vn003.datetime, utc=True).dt.tz_convert("Asia/Ho_Chi_Minh").dt.floor("h")
    raw_vn003["value"] = pd.to_numeric(raw_vn003.value, errors="coerce")
    numeric = ["pm25", "pm10", "temperature", "relative_humidity", "wind_speed",
               "wind_direction", "precipitation", "surface_pressure"]
    for station, part in df.groupby("station_id"):
        # The Issue #5 auditor knows the baseline 18-column schema; the five Issue #44
        # extension fields are checked separately by validate_dataset().
        audits[station] = audit_six_dimensions(part[list(df.columns[:18])], dataset_name=station)
        for kind, key, group, start, end in period_groups(part):
            expected = int((end - start) / pd.Timedelta(hours=1))
            n_grid = len(group)
            n_valid = int(group.pm25.notna().sum())
            raw = raw_vn003.loc[(raw_vn003.timestamp >= start) & (raw_vn003.timestamp < end)] if station.endswith("7441") else None
            raw_n = len(raw) if raw is not None else None
            raw_source_hours = int(raw.timestamp.drop_duplicates().isin(group.timestamp).sum()) if raw is not None else None
            invalid_n = int((raw.value.lt(0) | raw.value.gt(1000) | raw.value.isna()).sum()) if raw is not None else None
            local_gaps = missing_runs(group)
            sizes = local_gaps.gap_hours if not local_gaps.empty else pd.Series(dtype=int)
            quality.append({"station_id": station, "period_type": kind, "period": key,
                            "period_start": str(start), "period_end_exclusive": str(end),
                            "expected_calendar_hours": expected, "active_grid_hours": n_grid,
                            "available_raw_observations": raw_n, "valid_pm25_observations": n_valid,
                            "invalid_raw_observations": invalid_n, "missing_active_hours": n_grid-n_valid,
                            "outside_active_window_hours": expected-n_grid,
                            "missing_pct_active": 100*(n_grid-n_valid)/n_grid,
                            "coverage_pct_calendar": 100*n_valid/expected,
                            "coverage_pct_active": 100*n_valid/n_grid,
                            "gap_count": len(sizes), "longest_missing_gap_hours": int(sizes.max()) if len(sizes) else 0,
                            "median_gap_hours": float(sizes.median()) if len(sizes) else 0,
                            "sample_size_denominator": expected})
            quality[-1].update(group_quality_dimensions(
                group, expected_calendar_hours=expected,
                outside_active_window_hours=max(0, expected - n_grid),
                raw_observations=raw_n, raw_source_hours=raw_source_hours,
                raw_invalid_observations=invalid_n,
                physical_bounds=ATMOSPHERIC_BOUNDS,
            ))
            for variable in numeric:
                vals = group[variable].dropna().astype(float)
                row = {"station_id": station, "period_type": kind, "period": key,
                       "variable": variable, "unit": "degrees circular" if variable == "wind_direction" else "µg/m³" if variable in {"pm25","pm10"} else "source unit",
                       "grid_count": n_grid, "valid_count": len(vals), "missing_count": n_grid-len(vals),
                       "coverage_pct_active": 100*len(vals)/n_grid, "coverage_pct_calendar": 100*len(vals)/expected,
                       "missing_pct_active": 100*(n_grid-len(vals))/n_grid}
                if len(vals):
                    row.update(mean=float(vals.mean()), median=float(vals.median()), variance=float(vals.var()) if len(vals)>1 else np.nan,
                               sd=float(vals.std()) if len(vals)>1 else np.nan, min=float(vals.min()), max=float(vals.max()),
                               q25=float(vals.quantile(.25)), q75=float(vals.quantile(.75)), iqr=float(vals.quantile(.75)-vals.quantile(.25)),
                               p90=float(vals.quantile(.9)), p95=float(vals.quantile(.95)),
                               skewness=float(stats.skew(vals, bias=False)) if len(vals)>2 else np.nan,
                               excess_kurtosis=float(stats.kurtosis(vals, bias=False)) if len(vals)>3 else np.nan)
                    if variable == "wind_direction":
                        row["circular_mean_degrees"] = float(stats.circmean(vals, high=360, low=0))
                        row["circular_sd_degrees"] = float(stats.circstd(vals, high=360, low=0))
                profile.append(row)
        # Hourly and weekday patterns remain descriptive and station-specific.
        for kind, key, col in [("hour", str(h), part.timestamp.dt.hour) for h in range(24)] + [("weekday", str(d), part.timestamp.dt.day_of_week) for d in range(7)]:
            group = part.loc[col == int(key)]
            vals = group.pm25.dropna()
            profile.append({"station_id": station, "period_type": kind, "period": key, "variable": "pm25", "unit": "µg/m³",
                            "grid_count": len(group), "valid_count": len(vals), "missing_count": len(group)-len(vals),
                            "coverage_pct_active": 100*len(vals)/len(group), "coverage_pct_calendar": np.nan,
                            "missing_pct_active": 100*(len(group)-len(vals))/len(group),
                            "mean": float(vals.mean()), "median": float(vals.median()), "variance": float(vals.var()),
                            "sd": float(vals.std()), "min": float(vals.min()), "max": float(vals.max()),
                            "q25": float(vals.quantile(.25)), "q75": float(vals.quantile(.75)),
                            "iqr": float(vals.quantile(.75)-vals.quantile(.25)), "p90": float(vals.quantile(.9)),
                            "p95": float(vals.quantile(.95)), "skewness": float(stats.skew(vals, bias=False)),
                            "excess_kurtosis": float(stats.kurtosis(vals, bias=False))})
    return pd.DataFrame(quality), pd.DataFrame(profile), gaps, audits


def monthly_figure_groups(part: pd.DataFrame, quality: pd.DataFrame) -> list[dict]:
    """Monthly box inputs with observed n and full-calendar coverage from the QC table."""
    station = part.station_id.iloc[0]
    scoped_quality = quality.loc[
        (quality.station_id == station) & (quality.period_type == "month")
    ].set_index("period")
    rows = []
    for period, group in part.groupby(part.timestamp.dt.strftime("%Y-%m"), sort=False):
        start = pd.Timestamp(f"{period}-01", tz=part.timestamp.dt.tz)
        end = start + pd.DateOffset(months=1)
        n = int(group.pm25.notna().sum())
        expected = int((end - start) / pd.Timedelta(hours=1))
        coverage = 100 * n / expected
        if period in scoped_quality.index:
            qc = scoped_quality.loc[period]
            if int(qc.valid_pm25_observations) != n or not np.isclose(qc.coverage_pct_calendar, coverage):
                raise ValueError(f"FIG-03 monthly QC mismatch: {station}, {period}")
        rows.append({"period": period, "year": int(period[:4]), "month": int(period[5:]),
                     "values": group.pm25.dropna().to_numpy(), "n": n,
                     "coverage_pct_calendar": coverage})
    return rows


def save_figures(df: pd.DataFrame, quality: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    configure_vietnamese_fonts()
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 300})
    # FIG-02: observed PM2.5 distribution by station and calendar year. Partial
    # years keep full-calendar coverage on the tick label so they are not read
    # as equivalent cohorts.
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.0), layout="constrained")
    for ax, (station, part) in zip(axes, df.groupby("station_id")):
        by_year = [v.pm25.dropna().to_numpy() for _, v in part.groupby(part.timestamp.dt.year)]
        labels = [str(y) for y in sorted(part.timestamp.dt.year.unique())]
        q = quality.loc[(quality.station_id == station) & (quality.period_type == "year")].set_index("period")
        ticks = []
        for y, x in zip(labels, by_year):
            row = q.loc[y]
            partial = bool(row.active_grid_hours < row.expected_calendar_hours)
            ticks.append(
                f"{y}{'*' if partial else ''}\nn={len(x):,}\n"
                f"{row.coverage_pct_calendar:.0f}% calendar"
            )
        ax.boxplot(by_year, tick_labels=ticks, showfliers=False, widths=.55)
        ax.set_title(f"{station.split('_')[0]}: observed PM2.5 by calendar year")
        ax.set_xlabel("Calendar year (* partial year: active window < full year)")
        ax.set_ylabel("PM2.5 (µg/m³)")
    fig.savefig(FIGURES/"FIG-02-extended.png", dpi=300)
    plt.close(fig)

    # FIG-03: monthly PM2.5 distribution per station, with year-specific boxes
    # and a coverage panel. This answers the documented question (seasonal and
    # monthly distribution); winter coverage is a separate QC figure below.
    months = list(range(1, 13))
    years = sorted(df.timestamp.dt.year.unique())
    cmap = plt.get_cmap("viridis")
    colors = {year: cmap(i / max(1, len(years) - 1)) for i, year in enumerate(years)}
    fig = plt.figure(figsize=(13, 8.2), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=[3.0, 1.05], hspace=.08)
    for column, (station, part) in enumerate(df.groupby("station_id")):
        ax = fig.add_subplot(grid[0, column])
        cover_ax = fig.add_subplot(grid[1, column], sharex=ax)
        monthly = monthly_figure_groups(part, quality)
        month_width = 0.8 / max(1, len([y for y in years if (part.timestamp.dt.year == y).any()]))
        present_years = [y for y in years if (part.timestamp.dt.year == y).any()]
        for index, year in enumerate(present_years):
            annual = part.loc[part.timestamp.dt.year == year]
            offset = -0.4 + month_width * (index + .5)
            selected = [row for row in monthly if row["year"] == year and row["n"]]
            data = [row["values"] for row in selected]
            positions = [row["month"] + offset for row in selected]
            if not data:
                continue
            ax.boxplot(data, positions=positions, widths=month_width * .85,
                       showfliers=False, patch_artist=True,
                       boxprops={"facecolor": colors[year], "alpha": .75,
                                 "edgecolor": "#333333", "linewidth": .6},
                       medianprops={"color": "#111111", "linewidth": 1.0})
            observed = int(annual.pm25.notna().sum())
            cover_ax.bar(positions, [row["coverage_pct_calendar"] for row in selected],
                          width=month_width * .85,
                          color=colors[year], alpha=.85, linewidth=0,
                          label=f"{year}: n={observed:,}")
        for winter_month in (12, 1, 2):
            ax.axvspan(winter_month - .5, winter_month + .5, color="#d9d9d9", alpha=.18, zorder=0)
            cover_ax.axvspan(winter_month - .5, winter_month + .5, color="#d9d9d9", alpha=.18, zorder=0)
        ax.set_xticks(months)
        ax.set_xticklabels(["Dec" if m == 12 else str(m) for m in months])
        ax.set_xlim(.5, 12.5)
        ax.set_ylabel("PM2.5 (µg/m³)")
        ax.set_title(f"{station.split('_')[0]}: monthly observed PM2.5 by year")
        cover_ax.set_ylim(0, 100)
        cover_ax.set_ylabel("Full-month\ncoverage (%)", fontsize=8)
        cover_ax.set_xlabel("Calendar month (grey = Dec–Feb; winter cohort coverage in FIG-03b)")
        cover_ax.legend(fontsize=7, ncol=2, frameon=False, loc="upper right")
    fig.savefig(FIGURES/"FIG-03-extended.png", dpi=300)
    plt.close(fig)

    # Supplementary QC figure: full-calendar winter coverage. Kept because it
    # is the evidence that partial winters must not be ranked as full cohorts.
    winter = quality.loc[quality.period_type == "winter_year"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for ax, (station, part) in zip(axes, winter.groupby("station_id")):
        labels = [x.rsplit(":", 1)[-1] + ("*" if active < expected else "")
                  for x, active, expected in zip(part.period, part.active_grid_hours, part.expected_calendar_hours)]
        ax.bar(labels, part.coverage_pct_calendar, color="#287c8e", width=.55)
        if len(labels) == 1:
            ax.set_xlim(-.8, .8)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Observed PM2.5 / full winter calendar (%)")
        ax.set_xlabel("Winter ending year")
        ax.set_title(f"{station.split('_')[0]}: full-calendar winter coverage")
        if any(x.endswith("*") for x in labels):
            ax.text(.02, .02, "* partial active window", transform=ax.transAxes, fontsize=8)
        for i, row in enumerate(part.itertuples()):
            ax.text(i, row.coverage_pct_calendar + 2,
                    f"n={row.valid_pm25_observations:,}", ha="center", fontsize=8)
    fig.savefig(FIGURES/"FIG-03b-winter-coverage.png", dpi=300)
    plt.close(fig)


def write_outputs(df: pd.DataFrame, meta: dict, quality: pd.DataFrame, profile: pd.DataFrame,
                  gaps: pd.DataFrame, audits: dict, *, n_bootstrap: int, seed: int) -> None:
    REPORTS.mkdir(exist_ok=True)
    quality.to_csv(REPORTS/"extended_data_quality_by_station_year_season.csv", index=False)
    profile.to_csv(REPORTS/"extended_statistical_profile.csv", index=False)
    gaps.to_csv(REPORTS/"extended_missingness_gaps.csv", index=False)
    save_figures(df, quality)
    figure_rows = []
    decisions = [
        ("FIG-01", "Multiscale history", "REUSE", "Issue #44 historical figure already answers the time-series question"),
        ("FIG-02", "PM2.5 distribution by station/year", "EXTEND", "Year-specific distributions expose uneven coverage; tick labels carry n and full-calendar coverage and mark partial years"),
        ("FIG-03", "Seasonal and monthly PM2.5 distribution by station and year", "EXTEND", "Monthly observed-PM2.5 distributions split by station and year; legend gives annual observed n and lower panel gives full-month calendar coverage; partial winter coverage is separate supplementary QC figure"),
        ("FIG-04", "Hour × weekday pattern", "NOT NEEDED", "Station-specific hourly/weekday profile table answers the descriptive question; traffic source remains NO-GO, so no traffic claim is made"),
        ("FIG-05", "Meteorology LOWESS", "NOT NEEDED", "Station/year correlations and quintile medians inspect nonlinearity with n and coverage; ERA5 is a grid product and no causal claim is made"),
        ("FIG-06", "Pearson/Spearman matrix", "NOT NEEDED", "Station-specific correlation table avoids a misleading pooled matrix across disjoint stations"),
        ("FIG-07", "Rolling-24h and eligible daily categories", "NOT NEEDED", "Extended daily exceedance counts are in the inference artifacts; no unverified rolling-window category is created"),
    ]
    for fig, question, decision, reason in decisions:
        for station, part in df.groupby("station_id"):
            years = quality.loc[(quality.station_id == station) & (quality.period_type == "year")]
            winters = quality.loc[(quality.station_id == station) & (quality.period_type == "winter_year")]
            partial_years = [row.period for row in years.itertuples()
                             if row.active_grid_hours < row.expected_calendar_hours]
            partial_winters = [row.period for row in winters.itertuples()
                               if row.active_grid_hours < row.expected_calendar_hours]
            figure_rows.append({"figure": fig, "research_question": question, "decision": decision,
                                "reason": reason, "dataset_version": VERSION, "station_id": station,
                                "start": str(part.timestamp.min()), "end": str(part.timestamp.max()),
                                "n_observed_pm25": int(part.pm25.notna().sum()),
                                "coverage_pct_active": 100*part.pm25.notna().mean(),
                                "partial_periods": (
                                    f"partial years: {', '.join(partial_years) or 'none'}; "
                                    f"partial winters: {', '.join(partial_winters) or 'none'}"
                                ),
                                "limitation": (
                                    "Station spans do not overlap; missingness and partial periods "
                                    "vary by year/winter, so cross-station and cross-year comparisons "
                                    "are descriptive and not a single-site trend"
                                ),
                                "existing_figure": "figures/FIG-01-extended-historical.png" if fig == "FIG-01" else "",
                                "extended_figure": f"figures/extended/{fig}-extended.png" if decision == "EXTEND" else "",
                                "supplementary_figure": "figures/extended/FIG-03b-winter-coverage.png" if fig == "FIG-03" else ""})
    pd.DataFrame(figure_rows).to_csv(REPORTS/"extended_figure_audit.csv", index=False)
    inference_rows, sensitivity_rows, narratives, comparisons = [], [], [], []
    for station, part in df.groupby("station_id"):
        result = run_inference(part, min_valid_hours=18, n_bootstrap=n_bootstrap,
                               seed=seed, include_simulation=False)
        panel = result["panel"]["frame"]
        for key, test in result["tests"].items():
            row = {"station_id": station, "test": key, "hypothesis_h0": test["h0"],
                   "test_design": test["test_design"],
                   "statistical_decision": test["statistical_decision"],
                   "evidence_level": test["evidence_level"],
                   "analysis_start": str(part.timestamp.min()),
                   "analysis_end": str(part.timestamp.max()), "n_valid_days": int(test["n"]),
                   "statistic_name": test["statistic_name"], "statistic": test["statistic"],
                   "raw_iid_p_value": test["p_value_independence"],
                   "dependence_aware_p_value": test["p_value"], "holm_p_value": test["p_holm"],
                   "primary_estimand": test["primary_estimand"],
                   "primary_unit": test["primary_unit"],
                   "primary_estimate": test["primary_estimate"],
                   "primary_ci_low": test["primary_ci_low"],
                   "primary_ci_high": test["primary_ci_high"],
                   "primary_ci_method": test["primary_ci_method"],
                   "effect_size_name": test.get("primary_effect_size_name", test["effect_size_name"]),
                   "effect_size": test.get("primary_effect_size", test["effect_size"]),
                   "effect_size_ci_low": test.get("primary_effect_size_ci_low"),
                   "effect_size_ci_high": test.get("primary_effect_size_ci_high"),
                   "effect_size_ci_status": test.get(
                       "primary_effect_size_ci_status", test.get("effect_size_ci_status")),
                   "secondary_estimand": test["secondary_estimand"],
                   "secondary_estimate": test["secondary_estimate"],
                   "secondary_ci_low": test["secondary_ci_low"],
                   "secondary_ci_high": test["secondary_ci_high"],
                   "secondary_ci_method": test["secondary_ci_method"],
                   "secondary_effect_size_name": test.get("secondary_effect_size_name"),
                   "secondary_effect_size": test.get("secondary_effect_size"),
                   "secondary_effect_size_ci_status": test.get(
                       "secondary_effect_size_ci_status"),
                   "ci_status": test["ci_status"],
                   "interpretation_scope": test["interpretation_scope"],
                   "method": test["method"]["primary"], "assumptions": test["method"]["assumptions"],
                   "status": test["status"], "status_reason": test["status_reason"],
                   "conclusion": (
                       f"{test['statistical_decision']} | design={test['test_design']} | "
                       f"evidence={test['evidence_level']}"
                   ),
                   "interpretation": (
                       f"{test['statistical_decision'].replace('_', ' ')} at Holm alpha=0.05; "
                       f"design={test['test_design']}, evidence={test['evidence_level']}"
                   )}
            inference_rows.append(row)
            for axis, entries in test.get("sensitivity", {}).items():
                for setting, detail in entries.items():
                    sensitivity_rows.append({"station_id": station, "test": key, "axis": axis,
                                             "setting": setting, "p_value": detail["p_value"],
                                             "reject_at_0_05": detail["p_value"] < .05})
        for hours in (12, 18, 24):
            daily, _ = build_daily_panel(part, min_valid_hours=hours)
            sensitivity_rows.append({"station_id": station, "test": "daily_median", "axis": "min_valid_hours",
                                     "setting": hours, "n_days": len(daily), "estimate": float(daily.pm25_mean.median())})
        derived = part.copy()
        derived["pm25"] = derived.pm25_derived_interpolated
        daily_derived, _ = build_daily_panel(derived)
        sensitivity_rows.append({"station_id": station, "test": "daily_median", "axis": "derived_interpolation_only",
                                 "setting": "max_gap_2h", "n_days": len(daily_derived),
                                 "estimate": float(daily_derived.pm25_mean.median())})
        calendar = build_daily_calendar(part)
        for block in (7,14,28,42):
            ci = calendar_bootstrap_ci(calendar, block_length_days=block, n_bootstrap=n_bootstrap, seed=seed)
            sensitivity_rows.append({"station_id": station, "test": "daily_median", "axis": "block_length_days",
                                     "setting": block, "n_days": len(panel), "estimate": ci["point"],
                                     "ci_low": ci["ci_low"], "ci_high": ci["ci_high"]})
        winter = quality.loc[(quality.station_id == station) & (quality.period_type == "winter_year")]
        for row in winter.itertuples():
            sensitivity_rows.append({"station_id": station, "test": "winter_coverage", "axis": "winter_year",
                                     "setting": row.period, "n_hours": row.valid_pm25_observations,
                                     "coverage_pct_calendar": row.coverage_pct_calendar,
                                     "partial_window": row.active_grid_hours < row.expected_calendar_hours})
        full_winter_years = {int(row.period.rsplit(":",1)[-1]) for row in winter.itertuples()
                             if row.active_grid_hours == row.expected_calendar_hours and row.coverage_pct_calendar >= 70}
        winter_dates = panel.date.dt.month.isin([12,1,2])
        panel_winter_year = panel.date.dt.year + panel.date.dt.month.eq(12).astype(int)
        for scope, mask in (("all_observed_winters", winter_dates),
                            ("full_window_coverage_ge_70pct", winter_dates & panel_winter_year.isin(full_winter_years))):
            values = panel.loc[mask, "pm25_mean"]
            sensitivity_rows.append({"station_id": station, "test": "winter_daily_median", "axis": "partial_winter_exclusion",
                                     "setting": scope, "n_days": len(values),
                                     "estimate": float(values.median()) if len(values) else np.nan})
        for year, yearly in part.groupby(part.timestamp.dt.year):
            annual_panel, _ = build_daily_panel(yearly)
            qrow = quality.loc[(quality.station_id == station) & (quality.period_type == "year") & (quality.period == str(year))].iloc[0]
            if len(annual_panel) >= 30:
                annual_calendar = build_daily_calendar(yearly)
                ci = calendar_bootstrap_ci(annual_calendar, n_bootstrap=n_bootstrap, seed=seed)
                sensitivity_rows.append({"station_id": station, "test": "year_specific_daily_median", "axis": "year_selection",
                                         "setting": year, "n_days": len(annual_panel), "estimate": ci["point"],
                                         "ci_low": ci["ci_low"], "ci_high": ci["ci_high"],
                                         "coverage_pct_calendar": qrow.coverage_pct_calendar,
                                         "partial_window": qrow.active_grid_hours < qrow.expected_calendar_hours})
        dep = result["dependence"]["daily_effective_n"]
        exceed = int((panel.pm25_mean > 50).sum())
        narratives.append(f"| {station} | {len(part):,} | {part.pm25.notna().sum():,} | {len(panel):,} | {panel.pm25_mean.median():.2f} | {exceed}/{len(panel)} | {dep['rho_lag1']:.3f} | {dep['n_effective']:.1f} |")
        comparisons.append((station, result))
    inference = pd.DataFrame(inference_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    inference.to_csv(REPORTS/"extended_inference_results.csv", index=False)
    sensitivity.to_csv(REPORTS/"extended_inference_sensitivity.csv", index=False)
    baseline = pd.read_parquet(ROOT/"data/processed/air_pollution_final.parquet")
    baseline_panel, _ = build_daily_panel(baseline)
    baseline_median = float(baseline_panel.pm25_mean.median())
    correlations, binned = [], []
    for station, part in df.groupby("station_id"):
        for col in ("temperature", "relative_humidity", "wind_speed", "precipitation", "surface_pressure"):
            pairs = part[["pm25", col]].dropna()
            correlations.append({"station_id": station, "variable": col, "n_pairs": len(pairs),
                                 "period": "all", "active_grid_hours": len(part),
                                 "pair_coverage_pct_active": 100*len(pairs)/len(part),
                                 "pearson_r": float(pairs.corr(method="pearson").iloc[0,1]),
                                 "spearman_rho": float(pairs.corr(method="spearman").iloc[0,1])})
            for year, annual in part.groupby(part.timestamp.dt.year):
                yearly_pairs = annual[["pm25", col]].dropna()
                if len(yearly_pairs) >= 30:
                    correlations.append({"station_id": station, "variable": col, "n_pairs": len(yearly_pairs),
                                         "period": str(year), "active_grid_hours": len(annual),
                                         "pair_coverage_pct_active": 100*len(yearly_pairs)/len(annual),
                                         "pearson_r": float(yearly_pairs.corr(method="pearson").iloc[0,1]),
                                         "spearman_rho": float(yearly_pairs.corr(method="spearman").iloc[0,1])})
            if pairs[col].nunique() >= 5:
                bins = pd.qcut(pairs[col], q=5, duplicates="drop")
                for interval, values in pairs.groupby(bins, observed=True):
                    binned.append({"station_id": station, "variable": col, "bin": str(interval),
                                   "n_pairs": len(values), "median_pm25": float(values.pm25.median()),
                                   "median_weather": float(values[col].median())})
    pd.DataFrame(correlations).to_csv(REPORTS/"extended_meteorology_associations.csv", index=False)
    pd.DataFrame(binned).to_csv(REPORTS/"extended_meteorology_binned.csv", index=False)
    lines = ["# Issue #50 — extended W9 inference", "", f"Dataset version: `{VERSION}`; actual SHA-256: `{meta['actual_sha256']}`.",
             f"Configuration: 18 observed hours/day, CI B={n_bootstrap}, null B={N_NULL_BOOTSTRAP}, block={BLOCK_LENGTH_DAYS} calendar days, HAC lag={HAC_LAG_DAILY}, seed={seed}; Holm family fixed at four tests per station.",
             "The 18/24 rule is a study completeness rule, not a legal QCVN definition. Seasonal tests remain exploratory (R5). The QCVN 50 µg/m³ daily comparator follows the existing W9 contract; no legal compliance determination is made.",
             "", "| Station | Grid hours | Observed hours | Eligible days | Daily median (µg/m³) | Days >50 / eligible | Daily rho1 | n_eff (AR1 approximation) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|", *narratives, "",
             "Full statistics, primary/secondary estimands, effects, dependence-aware p, Holm p and assumptions: `reports/extended_inference_results.csv`. Sensitivity: `reports/extended_inference_sensitivity.csv`.",
             "Primary CI and secondary CI are separate columns. For the seasonal omnibus H, no single-contrast primary CI exists; `secondary_ci_*` is the winter–summer median contrast and is described as such. For weekday, `primary_ci_*` is the HAC interval for the trend-adjusted weekend coefficient while `secondary_ci_*` is the median contrast. For QCVN 24h, `primary_ci_*` is the HAC interval for the exceedance share, not the daily-mean location. For QCVN annual, `primary_ci_*` is the HAC interval for the mean of eligible daily means. `ci_status`/`effect_size_ci_status` state which intervals are estimable.",
             "The 18/24 rule is a study completeness rule, not the legal QCVN sampling definition; no legal compliance determination is made. Associations are observational, not causal. The calendar mask is retained in src/inference.py's bootstrap.",
             "Open-Meteo raw snapshot byte match: " + str(meta["weather_raw_snapshot_match"]) + ". Daily PM2.5 inference uses observed OpenAQ readings, not ERA5 weather."]
    (REPORTS/"extended_inference_results.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    qc_summary = quality.loc[quality.period_type == "station"]
    dimension_rows = []
    for period_type, frame in quality.groupby("period_type", sort=False):
        dimension_rows.append(
            f"| {period_type} | {len(frame)} | "
            f"{(frame.dim_completeness_status == 'PASS').sum()}/{len(frame)} | "
            f"{(frame.dim_consistency_status == 'PASS').sum()}/{len(frame)} | "
            f"{(frame.dim_validity_status == 'PASS').sum()}/{len(frame)} | "
            f"{(frame.dim_uniqueness_status == 'PASS').sum()}/{len(frame)} | "
            f"{(frame.dim_timeliness_status == 'PASS').sum()}/{len(frame)} | "
            f"{int(frame.duplicate_keys.sum())} | {int(frame.out_of_bounds_pm25_values.sum())} | "
            f"{int(frame.nonfinite_pm25_values.sum())} | {int(frame.irregular_sampling_intervals.sum())} |"
        )
    failing = quality.loc[
        (quality.dim_completeness_status != "PASS")
        | (quality.dim_consistency_status != "PASS")
        | (quality.dim_validity_status != "PASS")
        | (quality.dim_uniqueness_status != "PASS")
        | (quality.dim_timeliness_status != "PASS")
    ]
    failing_rows = [
        f"| {row.station_id} | {row.period_type} | {row.period} | {row.dim_completeness_status} | "
        f"{row.dim_consistency_status} | {row.dim_validity_status} | "
        f"{row.dim_uniqueness_status} | {row.dim_timeliness_status} |"
        for row in failing.itertuples()
    ] or ["| none | - | - | PASS | PASS | PASS | PASS | PASS |"]
    lines = ["# Extended six-dimension quality audit", "", f"Dataset `{VERSION}`, SHA-256 `{meta['actual_sha256']}`; generated by `python scripts/run_extended_reanalysis.py`.",
             "Accuracy of instrument readings: **UNVERIFIABLE** without independent QC flags or reference instrument. Physical-bound screening is reported separately and is not device accuracy.",
             "Every station × year/month/season/winter cohort carries explicit completeness, accuracy, consistency, validity, uniqueness and timeliness fields in `extended_data_quality_by_station_year_season.csv`; the Issue #5 six-dimension auditor still runs on its 18-column baseline schema per station, and the five Issue #44 fields are checked by the extended contract gate.",
             "", "## Denominator and missingness definitions", "",
             "- `expected_calendar_hours` — full calendar hours in the period (month/year/season).",
             "- `active_grid_hours` — hourly grid rows inside the station's own active window.",
             "- `valid_pm25_hours` — finite observed PM2.5 inside `[0, 1000]` µg/m³.",
             "- `missing_observed_hours` — active hours without a valid observation.",
             "- `missing_source_rows` — active hours with no raw source row (VN003 only).",
             "- `invalid_source_rows` — raw rows that are NaN/out of numerical bounds (VN003 only).",
             "- `outside_active_window_hours` — calendar hours outside the station's active window (partial periods).",
             "- Missing, invalid and outside-window hours are never merged into one count; ratios always name their denominator.",
             "", "## Station-level summary", "",
             "| Station | Active hours | Valid observed | Coverage active | Longest gap (h) |",
             "|---|---:|---:|---:|---:|", *[f"| {r.station_id} | {r.active_grid_hours:,} | {r.valid_pm25_observations:,} | {r.coverage_pct_active:.2f}% | {r.longest_missing_gap_hours:,} |" for r in qc_summary.itertuples()],
             "", "| Station | Completeness (observed/grid) | Accuracy | Consistency | Validity | Uniqueness | Timeliness |",
             "|---|---|---|---|---|---|---|",
             *[f"| {station} | {100*df.loc[df.station_id==station,'pm25'].notna().mean():.2f}% | UNVERIFIABLE device accuracy; numerical screen only | {'PASS' if audit['dimensions']['consistency']['is_timezone_consistent'] and audit['dimensions']['consistency']['is_chronologically_monotonic'] else 'FAIL'} | {'PASS' if audit['dimensions']['validity']['all_columns_conformant'] else 'FAIL'} | {audit['dimensions']['uniqueness']['duplicate_rows']} duplicate keys | {audit['dimensions']['timeliness']['sampling_interval_profile']['irregular_intervals_count']} irregular grid intervals |" for station, audit in audits.items()],
             "", "## Dimension coverage by cohort type", "",
             "| Cohort type | Cohorts | Completeness PASS | Consistency PASS | Validity PASS | Uniqueness PASS | Timeliness PASS | Duplicate keys | Out-of-bounds PM2.5 | Non-finite PM2.5 | Irregular intervals |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|", *dimension_rows,
             "", "## Groups failing a structural dimension", "",
             "Completeness is expected to fail in partial cohorts (it is a coverage measure); the other dimensions must remain PASS. Device accuracy is UNVERIFIABLE in every group.",
             "", "| Station | Period type | Period | Completeness | Consistency | Validity | Uniqueness | Timeliness |",
             "|---|---|---|---|---|---|---|---|", *failing_rows,
             "", "Raw VN003 availability and invalid/sentinel counts are computed from the pinned raw Parquet. VN001 raw availability at the same hourly unit is unavailable in this runner and is left blank. `extended_missingness_gaps.csv` records every observed missing run. Weather/season association with missingness can suggest selective outages but does not identify MCAR, MAR or MNAR from observed values alone."]
    (REPORTS/"extended_data_quality_audit.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    (REPORTS/"extended_preprocessing_validation.md").write_text(
        "# Extended cleaning and preprocessing validation\n\n"
        f"Version `{VERSION}`; observed baseline VN001 cells matched by key; {int(df.pm25_is_derived.sum())} derived-only cells are flagged and excluded from main statistics. "
        "Numerical bounds, missing/sentinel handling, unique station-hour key, 1-hour grid, timezone, season alignment, and split counts passed the preflight gate. "
        "Extreme valid observed values were retained. The raw VN003 sentinel screen and masking evaluation are reused from Issue #44.\n", encoding="utf-8")
    (REPORTS/"extended_leakage_audit.md").write_text(
        "# Extended station and temporal leakage audit\n\n"
        "Protocol A station-specific chronological train/test passed `validate_modeling_split`. Protocol B pooled remains rejected for disjoint spans. "
        "`add_derived_short_gap_interpolation` groups by station and split; observed cells stay unchanged. "
        "`build_daily_panel` rejects multiple stations, and W9 runs once for each station with its own complete calendar. "
        "No model is fit in this runner; train-only scaler/imputer fitting is covered by existing cleaning-pipeline tests. "
        "No lag or rolling feature is generated by this runner.\n", encoding="utf-8")
    station_profile = profile.loc[(profile.period_type == "station") & (profile.variable == "pm25")]
    eda = ["# Extended station-specific EDA", "", "Main statistics use observed PM2.5 only. Full profiles by year, month, season/winter, hour and weekday are in `extended_statistical_profile.csv`; associations in `extended_meteorology_associations.csv`.",
           "", "| Station | n | Median (µg/m³) | IQR | Coverage active |", "|---|---:|---:|---:|---:|",
           *[f"| {r.station_id} | {r.valid_count:,} | {r.median:.2f} | {r.iqr:.2f} | {r.coverage_pct_active:.2f}% |" for r in station_profile.itertuples()],
           "", "Partial years and winters retain full-calendar denominators; low-coverage periods are descriptive only. Year-specific daily median CIs and exclusion of partial/low-coverage winters are in `extended_inference_sensitivity.csv`. Circular wind-direction mean/SD use angular statistics. `extended_meteorology_binned.csv` shows quintile medians to inspect departures from linear association. ERA5 represents a grid cell, not a co-located reference instrument. No causal interpretation is made."]
    (REPORTS/"extended_eda_findings.md").write_text("\n".join(eda)+"\n", encoding="utf-8")
    baseline_tests = inference.loc[inference.station_id == "VN001_HANOI_556_NGUYEN_VAN_CU"].set_index("test")
    historical_tests = inference.loc[inference.station_id == "VN003_HANOI_OPENAQ_7441"].set_index("test")
    stability_rows = []
    for key in ("season_effect", "weekday_effect", "qcvn_24h", "qcvn_annual"):
        b, h = baseline_tests.loc[key], historical_tests.loc[key]
        verdict = compare_station_evidence(key, b.to_dict(), h.to_dict())
        b_ci = f"[{b.primary_ci_low:.3g}, {b.primary_ci_high:.3g}]" if pd.notna(b.primary_ci_low) else "n/a"
        h_ci = f"[{h.primary_ci_low:.3g}, {h.primary_ci_high:.3g}]" if pd.notna(h.primary_ci_low) else "n/a"
        stability_rows.append(
            f"| {key} | {b.primary_estimate:.4g} {b_ci} | {h.primary_estimate:.4g} {h_ci} | "
            f"{b.holm_p_value:.4g} / {h.holm_p_value:.4g} | {b.evidence_level} / {h.evidence_level} | "
            f"{verdict['classification']} |"
        )
    dataset_rows, statistical_rows = [], []
    for station, result in comparisons:
        q = quality.loc[(quality.station_id == station) & (quality.period_type == "station")].iloc[0]
        p = station_profile.loc[station_profile.station_id == station].iloc[0]
        dep = result["dependence"]["daily_effective_n"]
        dataset_rows.append(f"| {station} | {q.period_start}–{q.period_end_exclusive} (exclusive end) | {q.active_grid_hours:,} | {q.valid_pm25_observations:,} | {q.coverage_pct_active:.2f}% | {q.missing_active_hours:,} | {len(result['panel']['frame']):,} |")
        years = profile.loc[(profile.station_id == station) & (profile.period_type == "year") & (profile.variable == "pm25")]
        year_text = ", ".join(f"{r.period}: {r.median:.1f} (coverage {r.coverage_pct_calendar:.1f}%)" for r in years.itertuples())
        meteo = pd.DataFrame(correlations)
        strongest = meteo.loc[(meteo.station_id == station) & (meteo.period == "all")].iloc[lambda x: x.pearson_r.abs().argmax()]
        statistical_rows.append(f"| {station} | {p['median']:.2f} / {p['mean']:.2f} | {p['sd']:.2f} / {p['iqr']:.2f} | {dep['rho_lag1']:.3f} / {dep['n_effective']:.1f} | {strongest.variable}: r={strongest.pearson_r:.3f} (n={strongest.n_pairs:,}) | {year_text} |")
    comparison = ["# Issue #50 — baseline versus extended reanalysis", "", f"Dataset `{VERSION}`; actual SHA-256 `{meta['actual_sha256']}`; stored snapshot SHA-256 `{meta['sha256']}`; byte match: `{meta['snapshot_sha256_match']}`.",
                  "All numbers below derive from the saved CSVs and the baseline Parquet. VN001 is the same physical station in baseline and extended and its observed cells are identical. VN003 is a separate station without overlap; cross-station differences do not establish a temporal trend at one location.",
                  f"Open-Meteo raw snapshot SHA-256 `{meta['weather_backfill']['raw_sha256']}`; local live reanalysis SHA-256 `{meta['weather_raw_sha256_actual']}`; byte match `{meta['weather_raw_snapshot_match']}`. Meteorological association under a changed ERA5 response is exploratory; content equality with the frozen weather snapshot is UNVERIFIED.",
                  "", "## Dataset comparison", "", "| Station | Span | Grid hours | Observed PM2.5 hours | Coverage (active) | Missing hours | Eligible days (≥18/24) |",
                  "|---|---|---:|---:|---:|---:|---:|", *dataset_rows,
                  "", "## Descriptive comparison", "", "| Station | PM2.5 median / mean (µg/m³) | SD / IQR (µg/m³) | Daily rho1 / n_eff | Strongest linear weather association | Yearly observed medians (µg/m³; full-calendar coverage) |",
                  "|---|---|---|---|---|---|", *statistical_rows,
                  "", "Winter coverage and seasonal cohorts: `extended_data_quality_by_station_year_season.csv` (period_type=winter_year); year-specific median CI and partial-winter exclusion: `extended_inference_sensitivity.csv`. All station/year PM2.5 distributions: `extended_statistical_profile.csv`.",
                  "", "## Test-by-test concordance (direction, magnitude and uncertainty)", "",
                  "`CONCORDANT DIRECTION` only means both stations reject after Holm with the same sign; it does **not** mean the two stations share one effect. Overlapping CIs are not proof of equality, and non-overlapping CIs indicate a magnitude difference.",
                  "", "| Test | VN001 primary estimate [95% CI] | VN003 primary estimate [95% CI] | Holm p (VN001 / VN003) | Evidence level (VN001 / VN003) | Classification |",
                  "|---|---|---|---|---|---|", *stability_rows,
                  "", "## Supported, weakened or unsupported baseline conclusions", "",
                  "| Conclusion | Baseline | Extended evidence | Stability |", "|---|---|---|---|",
                  f"| VN001 daily median | {baseline_median:.2f} µg/m³ | {comparisons[0][1]['panel']['frame'].pm25_mean.median():.2f} µg/m³ at VN001 | SUPPORTED (identical observations) |",
                  "| 2022–2026 single-site trend | Not estimated | Stations have disjoint spans | INCOMPARABLE (two physical stations, not one site over time) |",
                  "| Device accuracy | No independent calibration | OpenAQ VN003 lacks independent row QC | UNVERIFIED |",
                  "| Seasonal effect | Exploratory (single/multi-year but confounded) | Exploratory at both stations | EXPLORATORY / INCOMPARABLE (R5) |",
                  "", "`reports/extended_inference_results.csv` contains test statistics, primary/secondary estimands, effects, CI and adjusted p for each station. `reports/extended_inference_sensitivity.csv` contains block/HAC, daily threshold, derived-value and winter-coverage sensitivity. Negative or unstable tests remain visible; no confirmatory upgrade is inferred from a small p-value alone."]
    (REPORTS/"extended_reanalysis_comparison.md").write_text("\n".join(comparison)+"\n", encoding="utf-8")
    config = {"issue": 50, "dataset_version": VERSION, "dataset_sha256_actual": meta["actual_sha256"],
              "dataset_sha256_snapshot": meta["sha256"], "snapshot_byte_match": meta["snapshot_sha256_match"],
              "weather_raw_sha256_actual": meta["weather_raw_sha256_actual"],
              "weather_raw_sha256_snapshot": meta["weather_backfill"]["raw_sha256"],
              "weather_raw_snapshot_match": meta["weather_raw_snapshot_match"],
              "seed": seed, "n_ci_bootstrap": n_bootstrap, "n_null_bootstrap": N_NULL_BOOTSTRAP,
              "block_length_days": BLOCK_LENGTH_DAYS, "hac_lag_days": HAC_LAG_DAILY,
              "min_valid_hours_per_day": 18, "numpy": np.__version__, "pandas": pd.__version__,
              "scipy": stats.__version__ if hasattr(stats,"__version__") else __import__("scipy").__version__,
              "command": "python scripts/run_extended_reanalysis.py"}
    (REPORTS/"extended_reanalysis_config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA, help="Pinned Issue #44 Parquet path")
    parser.add_argument("--ci-bootstrap", type=int, default=1000, help="Calendar CI replicates (default: 1000)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.ci_bootstrap < 200:
        parser.error("--ci-bootstrap must be >= 200")
    before = baseline_hashes()
    df, meta = validate_dataset(args.data)
    raw = pd.read_parquet(ROOT/json.loads(RAW_MANIFEST.read_text(encoding="utf-8"))["raw_parquet_path"])
    quality, profile, gaps, audits = quality_and_profile(df, raw)
    write_outputs(df, meta, quality, profile, gaps, audits, n_bootstrap=args.ci_bootstrap, seed=args.seed)
    after = baseline_hashes()
    if before != after:
        raise AssertionError("Baseline artifact changed during Issue #50 analysis")
    manifest_path = REPORTS/"issue50_baseline_hashes.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    existing.update({"before_reanalysis": before, "after_reanalysis": after,
                     "all_present_unchanged": before == after,
                     "note": "Data Parquets absent before local source reconstruction; their hashes are captured immediately before and after the Issue #50 runner."})
    manifest_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"Issue #50 outputs written; {len(df):,} real rows; baseline unchanged; dataset SHA-256 {meta['actual_sha256']}")


if __name__ == "__main__":
    main()
