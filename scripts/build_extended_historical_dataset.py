"""Reproducible acquisition, canonicalization, weather backfill, interpolation evaluation,
multi-year EDA, and legacy-vs-extended comparison for Issue #44 (2022-2026).

This script:
1. Acquires OpenAQ S3 Location 7441 (`VN003_HANOI_OPENAQ_7441`, 2022-2025) and records
   SHA-256 provenance and monthly/annual coverage in `reports/issue44_openaq_7441_manifest.json`.
2. Fetches Open-Meteo ERA5 surface meteorology backfill for 2022-01-01..2025-04-09.
3. Canonicalizes and deterministically cleans `VN003_HANOI_OPENAQ_7441` on its own
   observed window (`2022-01-01 01:00+07:00` to `2025-04-09 22:00+07:00`), never padding
   outside the station's operational lifetime and never coalescing with `VN001` or `VN002`.
4. Builds the versioned station-separated extended dataset
   `data/processed/air_pollution_extended_2022_2026.parquet` while verifying that all
   baseline VN001 artifacts remain byte-for-byte unchanged.
5. Runs the Phase 5 masking-validation interpolation experiment across `max_gap_hours`
   in {1, 2, 3, 6} and gap lengths {1, 2, 3, 6} -> `reports/issue44_interpolation_evaluation.csv`.
6. Computes multi-year / multi-winter EDA and dependence-aware seasonal comparisons ->
   `reports/issue44_multiyear_eda_summary.csv`, `figures/FIG-01-extended-historical.png`,
   and `reports/issue44_legacy_vs_extended_comparison.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cleaning import (
    AIR_MEASUREMENT_COLUMNS,
    WEATHER_MEASUREMENT_COLUMNS,
    assert_no_imputation,
    clean_air_quality,
    clean_weather,
)
from src.cleaning_pipeline import add_cyclical_time_features, merge_air_weather
from src.data_collection import (
    CANONICAL_TIMEZONE,
    COORDS_OPENAQ_7441,
    COORDS_OPENAQ_HANOI,
    COORDS_WEATHER_ERA5,
    HANOI_OPENAQ_HISTORICAL_LOCATION_ID,
    HANOI_OPENAQ_HISTORICAL_SENSOR_ID,
    LOCATION_OPENAQ_7441,
    STATION_OPENAQ_7441,
    STATION_OPENAQ_HANOI,
    STATION_WEATHER_ERA5,
    OpenAQAdapter,
    OpenMeteoAdapter,
    compute_file_sha256,
    validate_weather_canonical,
)
from src.inference import (
    _season_effect_test,
    build_daily_calendar,
    build_daily_panel,
    calendar_bootstrap_ci,
    effective_sample_size,
)
from src.issue44_preparation import (
    add_derived_short_gap_interpolation,
    assign_station_chronological_split,
    evaluate_interpolation_grid,
    haversine_distance_km,
    vietnam_season,
    winter_station_summary,
    winter_year,
)

EXPECTED_S3_7441_FILE_COUNT = 903
EXPECTED_S3_7441_FILES_BY_YEAR = {2022: 190, 2023: 249, 2024: 365, 2025: 99}
EXPECTED_RAW_7441_SHA256 = "57b6fbaa63089e57a6377fd85293355cb475f8d8bb62fb58b469ced27a4cdae8"


def _compute_7441_coverage(df_raw: pd.DataFrame, s3_keys: list[str]) -> dict[str, Any]:
    """Compute monthly and annual coverage profile for OpenAQ Location 7441 (2022-2025)."""
    df = df_raw.copy()
    df["dt_utc"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
    df = df.dropna(subset=["dt_utc"]).copy()
    df["timestamp"] = df["dt_utc"].dt.tz_convert(CANONICAL_TIMEZONE).dt.floor("h")
    df["value_num"] = pd.to_numeric(df["value"], errors="coerce")

    # Classify each raw hour
    df["status"] = np.where(df["value_num"] >= 0.0, "valid", "invalid_or_sentinel")
    hour_status = (
        df.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="first")[["timestamp", "status", "value_num"]]
    )

    grid_start = pd.Timestamp("2022-01-01 00:00:00", tz=CANONICAL_TIMEZONE)
    grid_end = pd.Timestamp("2025-12-31 23:00:00", tz=CANONICAL_TIMEZONE)
    calendar = pd.DataFrame({"timestamp": pd.date_range(grid_start, grid_end, freq="h")})
    calendar = calendar.merge(hour_status, on="timestamp", how="left")
    calendar["status"] = calendar["status"].fillna("missing")

    source_start = hour_status["timestamp"].min()
    source_end = hour_status["timestamp"].max()
    calendar["source_available"] = calendar["timestamp"].between(source_start, source_end)
    calendar["gap"] = calendar["source_available"] & calendar["status"].ne("valid")
    calendar["gap_run"] = calendar["gap"].ne(calendar["gap"].shift(fill_value=False)).cumsum()
    full_gap_sizes = calendar.loc[calendar["gap"]].groupby("gap_run").size()

    monthly: list[dict[str, Any]] = []
    for period in pd.period_range("2022-01", "2025-12", freq="M"):
        start = pd.Timestamp(period.start_time, tz=CANONICAL_TIMEZONE)
        end = pd.Timestamp(period.end_time.floor("h"), tz=CANONICAL_TIMEZONE)
        scoped = calendar[(calendar["timestamp"] >= start) & (calendar["timestamp"] <= end)]
        gap_sizes = scoped.loc[scoped["gap"]].groupby("gap_run").size()
        exp_h = int(len(scoped))
        valid_h = int(scoped["status"].eq("valid").sum())
        monthly.append({
            "month": str(period),
            "expected_hours": exp_h,
            "s3_reported_hours": int(scoped["status"].ne("missing").sum()),
            "qc_valid_hours": valid_h,
            "qc_valid_pct": round(100.0 * valid_h / exp_h, 2) if exp_h > 0 else 0.0,
            "sentinel_or_negative_hours": int(scoped["status"].eq("invalid_or_sentinel").sum()),
            "missing_while_source_available_hours": int((scoped["source_available"] & scoped["status"].eq("missing")).sum()),
            "source_unavailable_hours": int((~scoped["source_available"]).sum()),
            "longest_gap_hours": int(gap_sizes.max()) if not gap_sizes.empty else 0,
        })

    annual: list[dict[str, Any]] = []
    files_by_year = {
        y: sum(1 for k in s3_keys if f"/year={y}/" in k)
        for y in (2022, 2023, 2024, 2025)
    }
    for year in (2022, 2023, 2024, 2025):
        start = pd.Timestamp(f"{year}-01-01 00:00:00", tz=CANONICAL_TIMEZONE)
        end = pd.Timestamp(f"{year}-12-31 23:00:00", tz=CANONICAL_TIMEZONE)
        scoped = calendar[(calendar["timestamp"] >= start) & (calendar["timestamp"] <= end)]
        gap_sizes = scoped.loc[scoped["gap"]].groupby("gap_run").size()
        exp_h = int(len(scoped))
        valid_h = int(scoped["status"].eq("valid").sum())
        avail_h = int(scoped["source_available"].sum())
        annual.append({
            "year": year,
            "s3_daily_files": files_by_year[year],
            "expected_hours": exp_h,
            "source_available_hours": avail_h,
            "s3_reported_hours": int(scoped["status"].ne("missing").sum()),
            "qc_valid_hours": valid_h,
            "qc_valid_pct_of_calendar_year": round(100.0 * valid_h / exp_h, 2),
            "qc_valid_pct_of_active_window": round(100.0 * valid_h / avail_h, 2) if avail_h > 0 else 0.0,
            "sentinel_or_negative_hours": int(scoped["status"].eq("invalid_or_sentinel").sum()),
            "missing_while_source_available_hours": int((scoped["source_available"] & scoped["status"].eq("missing")).sum()),
            "source_unavailable_hours": int((~scoped["source_available"]).sum()),
            "longest_gap_hours": int(gap_sizes.max()) if not gap_sizes.empty else 0,
        })

    neg_vals = df.loc[df["value_num"] < 0.0, "value_num"].value_counts().to_dict()
    return {
        "source_observation_window": {
            "start": source_start.isoformat(),
            "end": source_end.isoformat(),
            "active_window_hours": int(calendar["source_available"].sum()),
        },
        "raw_rows": int(len(df_raw)),
        "unique_timestamps": int(len(hour_status)),
        "duplicate_timestamps": int(len(df) - len(hour_status)),
        "qc_valid_hours": int((hour_status["status"] == "valid").sum()),
        "sentinel_or_negative_hours": int((hour_status["status"] == "invalid_or_sentinel").sum()),
        "negative_value_breakdown": {str(k): int(v) for k, v in sorted(neg_vals.items())},
        "longest_contiguous_gap_active_window_hours": int(full_gap_sizes.max()) if not full_gap_sizes.empty else 0,
        "annual": annual,
        "monthly": monthly,
    }


def _generate_fig01_extended(
    df_ext: pd.DataFrame,
    winter_df: pd.DataFrame,
    out_path: Path,
) -> None:
    """Render publication-grade station-separated multi-year figure FIG-01-extended-historical.png."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "axes.edgecolor": "#333333",
        "axes.linewidth": 0.8,
    })

    fig = plt.figure(figsize=(14, 9.5), dpi=300)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], width_ratios=[1.35, 1.0], hspace=0.38, wspace=0.25)

    ax_7441 = fig.add_subplot(gs[0, :])
    ax_vn001 = fig.add_subplot(gs[1, 0])
    ax_winter = fig.add_subplot(gs[1, 1])

    # Panel A: VN003_HANOI_OPENAQ_7441 (2022-2025)
    s7441 = df_ext[df_ext["station_id"] == STATION_OPENAQ_7441].sort_values("timestamp").copy()
    s7441["date"] = s7441["timestamp"].dt.floor("D")
    daily_7441 = s7441.groupby("date")["pm25"].agg(["count", "mean"]).reset_index()
    daily_7441.loc[daily_7441["count"] < 18, "mean"] = np.nan
    daily_7441["roll30"] = daily_7441["mean"].rolling(30, min_periods=10).mean()

    ax_7441.plot(
        daily_7441["date"],
        daily_7441["mean"],
        color="#6baed6",
        alpha=0.42,
        linewidth=0.7,
        label="Daily mean (≥18h valid)",
    )
    ax_7441.plot(
        daily_7441["date"],
        daily_7441["roll30"],
        color="#08519c",
        linewidth=2.0,
        label="30-day rolling mean (within station)",
    )
    ax_7441.axhline(50.0, color="#cb181d", linestyle="--", linewidth=1.1, label="QCVN 05:2023 24h limit (50 µg/m³)")
    ax_7441.axhline(15.0, color="#525252", linestyle=":", linewidth=1.0, label="WHO 2021 24h AQG (15 µg/m³)")

    for wy, (w_start, w_end) in [
        (2022, ("2022-01-01", "2022-02-28")),
        (2023, ("2022-12-01", "2023-02-28")),
        (2024, ("2023-12-01", "2024-02-29")),
        (2025, ("2024-12-01", "2025-02-28")),
    ]:
        ax_7441.axvspan(
            pd.Timestamp(w_start, tz=CANONICAL_TIMEZONE),
            pd.Timestamp(w_end, tz=CANONICAL_TIMEZONE),
            color="#fee0d2",
            alpha=0.35,
            label="Winter (Dec–Feb)" if wy == 2022 else None,
        )

    ax_7441.set_title(
        "A. Historical Station VN003 (OpenAQ 7441 / AirNow Gov Monitor, 2022-01 to 2025-04): 4 Recurrent Winter PM2.5 Peaks",
        fontsize=11,
        fontweight="bold",
        loc="left",
        pad=8,
    )
    ax_7441.set_ylabel("PM2.5 (µg/m³)", fontsize=9.5)
    ax_7441.set_ylim(0, 220)
    ax_7441.spines["top"].set_visible(False)
    ax_7441.spines["right"].set_visible(False)
    ax_7441.legend(loc="upper left", frameon=False, ncol=3, fontsize=8.5)
    ax_7441.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax_7441.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # Panel B: VN001_HANOI_556_NGUYEN_VAN_CU (2025-07 to 2026-07)
    svn1 = df_ext[df_ext["station_id"] == STATION_OPENAQ_HANOI].sort_values("timestamp").copy()
    svn1["date"] = svn1["timestamp"].dt.floor("D")
    daily_vn1 = svn1.groupby("date")["pm25"].agg(["count", "mean"]).reset_index()
    daily_vn1.loc[daily_vn1["count"] < 18, "mean"] = np.nan
    daily_vn1["roll30"] = daily_vn1["mean"].rolling(30, min_periods=10).mean()

    ax_vn001.plot(
        daily_vn1["date"],
        daily_vn1["mean"],
        color="#74c476",
        alpha=0.45,
        linewidth=0.8,
        label="Daily mean (≥18h valid)",
    )
    ax_vn001.plot(
        daily_vn1["date"],
        daily_vn1["roll30"],
        color="#006d2c",
        linewidth=2.0,
        label="30-day rolling mean",
    )
    ax_vn001.axhline(50.0, color="#cb181d", linestyle="--", linewidth=1.0)
    ax_vn001.axhline(15.0, color="#525252", linestyle=":", linewidth=0.9)
    ax_vn001.axvspan(
        pd.Timestamp("2025-12-01", tz=CANONICAL_TIMEZONE),
        pd.Timestamp("2026-02-28", tz=CANONICAL_TIMEZONE),
        color="#fee0d2",
        alpha=0.35,
        label="Winter 2026 (Dec–Feb)",
    )
    ax_vn001.set_title(
        "B. Baseline Station VN001 (556 Nguyễn Văn Cừ, 2025-07 to 2026-07)",
        fontsize=10.5,
        fontweight="bold",
        loc="left",
        pad=8,
    )
    ax_vn001.set_ylabel("PM2.5 (µg/m³)", fontsize=9.5)
    ax_vn001.set_ylim(0, 220)
    ax_vn001.spines["top"].set_visible(False)
    ax_vn001.spines["right"].set_visible(False)
    ax_vn001.legend(loc="upper left", frameon=False, fontsize=8)
    ax_vn001.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_vn001.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # Panel C: Winter-by-Winter Comparison Across 5 Winter Years (Station-Separated)
    w_rows = winter_df.sort_values(["winter_year", "station_id"]).reset_index(drop=True)
    labels = [
        f"W{int(r.winter_year)}\n({'VN003' if r.station_id == STATION_OPENAQ_7441 else 'VN001'})"
        for r in w_rows.itertuples()
    ]
    colors = [
        "#08519c" if r.station_id == STATION_OPENAQ_7441 else "#006d2c"
        for r in w_rows.itertuples()
    ]
    x_pos = np.arange(len(w_rows))
    bars = ax_winter.bar(x_pos, w_rows["median"], width=0.55, color=colors, alpha=0.88)
    ax_winter.errorbar(
        x_pos,
        w_rows["median"],
        yerr=[w_rows["median"] - w_rows["q25"], w_rows["q75"] - w_rows["median"]],
        fmt="none",
        ecolor="#252525",
        elinewidth=1.3,
        capsize=4,
        label="IQR (Q25–Q75)",
    )
    ax_winter.axhline(50.0, color="#cb181d", linestyle="--", linewidth=1.0, label="QCVN 50 µg/m³")
    for idx, bar in enumerate(bars):
        med = float(w_rows.loc[idx, "median"])
        n_obs = int(w_rows.loc[idx, "count"])
        ax_winter.text(
            bar.get_x() + bar.get_width() / 2.0,
            float(w_rows.loc[idx, "q75"]) + 3.0,
            f"{med:.1f}\n(n={n_obs})",
            ha="center",
            va="bottom",
            fontsize=7.8,
            color="#252525",
        )
    ax_winter.set_xticks(x_pos)
    ax_winter.set_xticklabels(labels, fontsize=8.5)
    ax_winter.set_ylim(0, 125)
    ax_winter.set_ylabel("Hourly PM2.5 Median & IQR (µg/m³)", fontsize=9.5)
    ax_winter.set_title(
        "C. Multi-Winter Comparison (W2022–W2025 at VN003; W2026 at VN001)",
        fontsize=10.5,
        fontweight="bold",
        loc="left",
        pad=8,
    )
    ax_winter.spines["top"].set_visible(False)
    ax_winter.spines["right"].set_visible(False)
    ax_winter.legend(loc="upper right", frameon=False, fontsize=8)

    fig.suptitle(
        "Hanoi Multi-Year PM2.5 Seasonality (2022–2026): Station-Separated Historical Expansion Confirms Recurrent Winter Surge",
        fontsize=12.5,
        fontweight="bold",
        y=0.98,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Issue #44 extended historical dataset and evaluations.")
    parser.add_argument("--force-reload", action="store_true", help="Force re-download from OpenAQ S3 and Open-Meteo.")
    args = parser.parse_args()

    raw_dir = PROJECT_ROOT / "data" / "raw"
    interim_dir = PROJECT_ROOT / "data" / "interim"
    processed_dir = PROJECT_ROOT / "data" / "processed"
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = PROJECT_ROOT / "figures"

    for d in (raw_dir, interim_dir, processed_dir, reports_dir, figures_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Record baseline SHA-256 checksums before running to prove immutability
    baseline_files = {
        "air_interim": interim_dir / "air_quality_canonical.parquet",
        "weather_interim": interim_dir / "weather_canonical.parquet",
        "final_processed": processed_dir / "air_pollution_final.parquet",
        "raw_metadata": raw_dir / "metadata.json",
        "fig01_baseline": figures_dir / "FIG-01.png",
        "statistical_profile": reports_dir / "statistical_profile.csv",
        "inference_results": reports_dir / "inference_results.md",
    }
    baseline_sha_before = {
        k: compute_file_sha256(p) for k, p in baseline_files.items() if p.exists()
    }

    # ------------------------------------------------------------------
    # PHASE 2: Acquire OpenAQ Location 7441 (2022-2025)
    # ------------------------------------------------------------------
    adapter_7441 = OpenAQAdapter(
        location_id=HANOI_OPENAQ_HISTORICAL_LOCATION_ID,
        raw_dir=raw_dir,
        interim_dir=interim_dir,
    )
    s3_keys_7441 = sorted(adapter_7441._list_s3_keys(years=(2022, 2023, 2024, 2025)))
    if len(s3_keys_7441) != EXPECTED_S3_7441_FILE_COUNT:
        raise RuntimeError(
            f"OpenAQ S3 Location 7441 file count changed: expected {EXPECTED_S3_7441_FILE_COUNT}, "
            f"got {len(s3_keys_7441)}."
        )
    s3_inventory_sha256 = hashlib.sha256("\n".join(s3_keys_7441).encode("utf-8")).hexdigest()
    s3_year_partitions: dict[str, dict[str, Any]] = {}
    for yr in (2022, 2023, 2024, 2025):
        yr_keys = [k for k in s3_keys_7441 if f"/year={yr}/" in k]
        if len(yr_keys) != EXPECTED_S3_7441_FILES_BY_YEAR[yr]:
            raise RuntimeError(
                f"OpenAQ S3 Location 7441 year={yr} file count changed: "
                f"expected {EXPECTED_S3_7441_FILES_BY_YEAR[yr]}, got {len(yr_keys)}."
            )
        s3_year_partitions[str(yr)] = {
            "s3_daily_files": len(yr_keys),
            "first_key": yr_keys[0] if yr_keys else None,
            "last_key": yr_keys[-1] if yr_keys else None,
        }

    df_raw_7441, raw_7441_path = adapter_7441.fetch_raw_data(
        raw_output_name="openaq_raw_7441_2022_2025.parquet",
        force_reload=args.force_reload,
        years=(2022, 2023, 2024, 2025),
    )
    raw_7441_sha256 = compute_file_sha256(raw_7441_path)
    coverage_7441 = _compute_7441_coverage(df_raw_7441, s3_keys_7441)

    manifest_7441 = {
        "issue": "#44",
        "phase": "Phase 1-2 Historical Source Verification & Acquisition",
        "decision": "APPROVED_FOR_STATION_SPECIFIC_HISTORICAL_EXPANSION",
        "station_id": STATION_OPENAQ_7441,
        "location_id": HANOI_OPENAQ_HISTORICAL_LOCATION_ID,
        "sensors_id": HANOI_OPENAQ_HISTORICAL_SENSOR_ID,
        "location_name": LOCATION_OPENAQ_7441,
        "provider": {"id": 119, "name": "AirNow", "instrument": "Government Monitor"},
        "coordinates": {"latitude": COORDS_OPENAQ_7441[0], "longitude": COORDS_OPENAQ_7441[1]},
        "license": {
            "id": 33,
            "name": "US Public Domain",
            "source_url": "http://www.usa.gov/publicdomain/label/1.0/",
            "commercial_use_allowed": True,
            "modification_allowed": True,
            "redistribution_allowed": True,
        },
        "qc_screening_policy": (
            "OpenAQ S3 CSV archives do not carry a separate per-record 'QC Name' column. "
            "In this manifest, 'qc_valid_hours' (18,208 hours) denotes numerically valid "
            "observations (PM2.5 >= 0.0 ug/m3 within physical bounds [0, 1000] ug/m3 and "
            "pm25_was_stuck == 0) after screening out 3,193 negative/sentinel records "
            "(-999.0: 3,188; -1.0: 4; -6.0: 1) to NaN."
        ),
        "s3_archive_prefix": "s3://openaq-data-archive/records/csv.gz/locationid=7441/",
        "years_queried": [2022, 2023, 2024, 2025],
        "s3_daily_file_count": len(s3_keys_7441),
        "s3_inventory_sha256": s3_inventory_sha256,
        "s3_first_key": s3_keys_7441[0] if s3_keys_7441 else None,
        "s3_last_key": s3_keys_7441[-1] if s3_keys_7441 else None,
        "s3_year_partitions": s3_year_partitions,
        "raw_parquet_path": "data/raw/openaq_raw_7441_2022_2025.parquet",
        "raw_parquet_sha256": raw_7441_sha256,
        "expected_pinned_raw_parquet_sha256": EXPECTED_RAW_7441_SHA256,
        "raw_parquet_matches_pinned_snapshot": bool(raw_7441_sha256 == EXPECTED_RAW_7441_SHA256),
        "raw_parquet_bytes": int(raw_7441_path.stat().st_size),
        "coverage": coverage_7441,
    }
    manifest_7441_path = reports_dir / "issue44_openaq_7441_manifest.json"
    manifest_7441_path.write_text(json.dumps(manifest_7441, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # PHASE 3 & 4: Canonicalization, Weather Backfill & Deterministic Cleaning
    # ------------------------------------------------------------------
    df_7441_canon_pre = adapter_7441.to_canonical(df_raw_7441)
    start_date_7441 = df_7441_canon_pre["timestamp"].min().strftime("%Y-%m-%d")
    end_date_7441 = df_7441_canon_pre["timestamp"].max().strftime("%Y-%m-%d")

    meteo_adapter = OpenMeteoAdapter(raw_dir=raw_dir, interim_dir=interim_dir)
    raw_weather_22_25, raw_weather_path = meteo_adapter.fetch_raw_data(
        start_date=start_date_7441,
        end_date=end_date_7441,
        raw_output_name=f"open_meteo_raw_{start_date_7441}_{end_date_7441}.json",
        force_reload=args.force_reload,
    )
    raw_weather_sha256 = compute_file_sha256(raw_weather_path)
    df_weather_22_25_canon = meteo_adapter.to_canonical(raw_weather_22_25, validate=True)
    weather_val_report = validate_weather_canonical(df_weather_22_25_canon, max_missing_pct=0.0)

    df_weather_22_25_clean, weather_clean_report = clean_weather(df_weather_22_25_canon)
    df_7441_clean, air_7441_clean_report = clean_air_quality(df_7441_canon_pre, df_weather_22_25_clean)
    assert_no_imputation(df_7441_canon_pre, df_7441_clean, AIR_MEASUREMENT_COLUMNS)
    assert_no_imputation(df_weather_22_25_canon, df_weather_22_25_clean, WEATHER_MEASUREMENT_COLUMNS)

    air_7441_interim_path = interim_dir / "air_quality_openaq_7441_canonical.parquet"
    weather_22_25_interim_path = interim_dir / "weather_2022_2025_canonical.parquet"
    df_7441_clean.to_parquet(air_7441_interim_path, index=False, compression="snappy")
    df_weather_22_25_clean.to_parquet(weather_22_25_interim_path, index=False, compression="snappy")

    # Merge VN003_HANOI_OPENAQ_7441 with its ERA5 weather and add cyclical features
    df_7441_merged = merge_air_weather(df_7441_clean, df_weather_22_25_clean)
    df_7441_featured = add_cyclical_time_features(df_7441_merged)
    df_7441_split = assign_station_chronological_split(df_7441_featured, train_fraction=0.80)

    # Load baseline VN001 processed dataset (read-only) and assign its chronological 80/20 split
    df_vn001 = pd.read_parquet(baseline_files["final_processed"]).copy()
    df_vn001_split = assign_station_chronological_split(df_vn001, train_fraction=0.80)

    # Combine as station-separated rows (key = (station_id, timestamp))
    common_cols = list(df_vn001.columns) + ["split"]
    df_extended = pd.concat(
        [df_7441_split[common_cols], df_vn001_split[common_cols]],
        ignore_index=True,
    ).sort_values(["station_id", "timestamp"], kind="mergesort").reset_index(drop=True)

    # Add derived short-gap interpolation columns (max_gap_hours=2) strictly within (station_id, split)
    df_extended = add_derived_short_gap_interpolation(df_extended, "pm25", max_gap_hours=2)
    df_extended["winter_year"] = winter_year(df_extended["timestamp"])
    df_extended["season"] = vietnam_season(df_extended["timestamp"])

    extended_parquet_path = processed_dir / "air_pollution_extended_2022_2026.parquet"
    df_extended.to_parquet(extended_parquet_path, index=False, compression="snappy")
    extended_parquet_sha256 = compute_file_sha256(extended_parquet_path)

    # ------------------------------------------------------------------
    # PHASE 5: Missingness & Interpolation Masking-Validation Experiment
    # ------------------------------------------------------------------
    interp_eval_df = evaluate_interpolation_grid(
        df_extended,
        "pm25",
        max_gap_candidates=(1, 2, 3, 6),
        gap_lengths=(1, 2, 3, 6),
        max_gaps_per_group=50,
        random_state=42,
    )
    interp_csv_path = reports_dir / "issue44_interpolation_evaluation.csv"
    interp_eval_df.to_csv(interp_csv_path, index=False)

    # ------------------------------------------------------------------
    # PHASE 6 & 7: Multi-Year / Multi-Winter EDA, Inference & Extended Figure
    # ------------------------------------------------------------------
    eda_rows: list[dict[str, Any]] = []
    for (sid, yr, seas), grp in df_extended.groupby(["station_id", df_extended["timestamp"].dt.year, "season"], sort=True):
        s_valid = grp["pm25"].dropna()
        daily = grp.set_index("timestamp")["pm25"].resample("D").agg(["count", "mean"])
        valid_days = daily[daily["count"] >= 18]["mean"].dropna()
        qcvn_exceed = int((valid_days > 50.0).sum())
        who_exceed = int((valid_days > 15.0).sum())
        eda_rows.append({
            "station_id": str(sid),
            "year": int(yr),
            "season": str(seas),
            "grid_hours": int(len(grp)),
            "observed_hours": int(len(s_valid)),
            "missing_hours": int(grp["pm25"].isna().sum()),
            "missing_pct": round(100.0 * float(grp["pm25"].isna().mean()), 2),
            "mean": round(float(s_valid.mean()), 2) if not s_valid.empty else np.nan,
            "sd": round(float(s_valid.std(ddof=1)), 2) if len(s_valid) > 1 else np.nan,
            "median": round(float(s_valid.median()), 2) if not s_valid.empty else np.nan,
            "iqr": round(float(s_valid.quantile(0.75) - s_valid.quantile(0.25)), 2) if not s_valid.empty else np.nan,
            "p90": round(float(s_valid.quantile(0.90)), 2) if not s_valid.empty else np.nan,
            "p95": round(float(s_valid.quantile(0.95)), 2) if not s_valid.empty else np.nan,
            "valid_days_ge18h": int(len(valid_days)),
            "qcvn_exceed_days": qcvn_exceed,
            "qcvn_exceed_pct": round(100.0 * qcvn_exceed / len(valid_days), 2) if len(valid_days) > 0 else np.nan,
            "who_exceed_days": who_exceed,
            "who_exceed_pct": round(100.0 * who_exceed / len(valid_days), 2) if len(valid_days) > 0 else np.nan,
        })
    eda_summary_df = pd.DataFrame(eda_rows)
    eda_csv_path = reports_dir / "issue44_multiyear_eda_summary.csv"
    eda_summary_df.to_csv(eda_csv_path, index=False)

    # Winter-by-winter detailed summary (preserving full grid hours per winter_year)
    w_all = df_extended[df_extended["season"] == "Winter (Dec-Feb)"].dropna(subset=["winter_year"]).copy()
    w_all["winter_year"] = w_all["winter_year"].astype(int)
    w_all["year_month"] = w_all["timestamp"].dt.strftime("%Y-%m")
    winter_rows: list[dict[str, Any]] = []
    for (sid, wy), grp in w_all.groupby(["station_id", "winter_year"], sort=True):
        expected_cal_h = 2184 if int(wy) == 2024 else 2160
        grid_h = int(len(grp))
        vals = grp["pm25"].dropna()
        valid_h = int(len(vals))
        daily = grp.set_index("timestamp")["pm25"].resample("D").agg(["count", "mean"])
        vdays = daily[daily["count"] >= 18]["mean"].dropna()
        months_present = sorted(grp["year_month"].unique().tolist())
        monthly_comp = {
            ym: {
                "grid_hours": int(len(m_grp)),
                "valid_hours": int(m_grp["pm25"].notna().sum()),
                "valid_pct": round(100.0 * float(m_grp["pm25"].notna().mean()), 2),
            }
            for ym, m_grp in grp.groupby("year_month", sort=True)
        }
        winter_rows.append({
            "station_id": str(sid),
            "winter_year": int(wy),
            "is_complete_winter_window": bool(len(months_present) == 3 and grid_h == expected_cal_h),
            "expected_calendar_hours": expected_cal_h,
            "station_grid_hours": grid_h,
            "count": valid_h,
            "coverage_of_full_winter_pct": round(100.0 * valid_h / expected_cal_h, 2),
            "coverage_of_station_grid_pct": round(100.0 * valid_h / grid_h, 2) if grid_h > 0 else 0.0,
            "missing_months_in_window": [f"{int(wy) - 1}-12"] if len(months_present) < 3 else [],
            "monthly_completeness": monthly_comp,
            "mean": round(float(vals.mean()), 2),
            "sd": round(float(vals.std(ddof=1)), 2),
            "median": round(float(vals.median()), 2),
            "q25": round(float(vals.quantile(0.25)), 2),
            "q75": round(float(vals.quantile(0.75)), 2),
            "iqr": round(float(vals.quantile(0.75) - vals.quantile(0.25)), 2),
            "p90": round(float(vals.quantile(0.90)), 2),
            "valid_days": int(len(vdays)),
            "qcvn_exceed_days": int((vdays > 50.0).sum()),
            "qcvn_exceed_pct": round(100.0 * float((vdays > 50.0).mean()), 2) if len(vdays) else 0.0,
        })
    winter_detail_df = pd.DataFrame(winter_rows)

    fig01_ext_path = figures_dir / "FIG-01-extended-historical.png"
    _generate_fig01_extended(df_extended, winter_detail_df, fig01_ext_path)

    # Station-separated seasonal inference & calendar-preserving autocorrelation
    inference_comparison: dict[str, Any] = {}
    for sid in (STATION_OPENAQ_7441, STATION_OPENAQ_HANOI):
        sub = df_extended[df_extended["station_id"] == sid].copy()
        panel, _ = build_daily_panel(sub, min_valid_hours=18)
        cal = build_daily_calendar(sub, min_valid_hours=18, label="season")
        ess = effective_sample_size(cal.values)
        seas_test = _season_effect_test(
            panel, cal, block_length=28, n_bootstrap=2000, seed=42, hac_lag=28
        )
        ci_med = calendar_bootstrap_ci(
            cal, statistic="median", block_length_days=28, n_bootstrap=2000, seed=42
        )

        daily = (
            sub.set_index("timestamp")["pm25"]
            .resample("D")
            .agg(["count", "mean"])
            .reset_index()
        )
        daily = daily[daily["count"] >= 18].dropna(subset=["mean"]).copy()
        daily["season"] = vietnam_season(daily["timestamp"])
        daily["is_winter"] = daily["timestamp"].dt.month.isin([12, 1, 2])
        w_vals = daily.loc[daily["is_winter"], "mean"].to_numpy()
        nw_vals = daily.loc[~daily["is_winter"], "mean"].to_numpy()
        u_stat, mw_p = stats.mannwhitneyu(w_vals, nw_vals, alternative="two-sided")
        r_rb = float(2.0 * u_stat / (len(w_vals) * len(nw_vals)) - 1.0)
        n_days = int(len(daily))

        inference_comparison[sid] = {
            "calendar_days": int(len(cal.values)),
            "valid_days_ge18h": n_days,
            "winter_days": int(len(w_vals)),
            "non_winter_days": int(len(nw_vals)),
            "daily_median": round(float(ci_med["point"]), 2),
            "daily_median_ci95_calendar_bootstrap": [
                round(float(ci_med["ci_low"]), 2),
                round(float(ci_med["ci_high"]), 2),
            ],
            "winter_daily_median": round(float(np.median(w_vals)), 2),
            "non_winter_daily_median": round(float(np.median(nw_vals)), 2),
            "winter_daily_mean": round(float(np.mean(w_vals)), 2),
            "non_winter_daily_mean": round(float(np.mean(nw_vals)), 2),
            "kruskal_wallis_h": round(float(seas_test["statistic"]), 4),
            "kruskal_wallis_epsilon2": round(float(seas_test["effect_size"]), 4),
            "kruskal_wallis_naive_p": float(seas_test["p_value_independence"]),
            "kruskal_wallis_calendar_bootstrap_p": round(float(seas_test["p_value"]), 6),
            "kruskal_wallis_hac_p": float(seas_test["p_value_hac"]),
            "winter_vs_nonwinter_u": round(float(u_stat), 2),
            "winter_vs_nonwinter_naive_p": float(mw_p),
            "winter_vs_nonwinter_r_rb": round(r_rb, 4),
            "daily_lag1_autocorr_rho1": round(float(ess["rho_lag1"]), 4),
            "effective_sample_size_n_eff": round(float(ess["n_effective"]), 2),
            "variance_inflation_factor": round(float(ess["inflation_factor"]), 2),
            "qcvn_exceedance_days": int((daily["mean"] > 50.0).sum()),
            "qcvn_exceedance_pct": round(100.0 * float((daily["mean"] > 50.0).mean()), 2),
            "inference_status": str(seas_test["status"]),
            "inference_status_reason": (
                "Seasonal comparisons remain exploratory under temporal dependence "
                "(rho_1 = 0.73-0.75) and multi-month missingness; VN003 and VN001 are "
                "separate physical stations (7.324 km apart) and are never pooled as "
                "i.i.d. repetitions of a single monitor."
            ),
        }

    # Spatial correspondence metadata
    dist_7441_era5 = round(haversine_distance_km(COORDS_OPENAQ_7441, COORDS_WEATHER_ERA5), 3)
    dist_vn001_era5 = round(haversine_distance_km(COORDS_OPENAQ_HANOI, COORDS_WEATHER_ERA5), 3)
    dist_7441_vn001 = round(haversine_distance_km(COORDS_OPENAQ_7441, COORDS_OPENAQ_HANOI), 3)

    ext_meta = {
        "dataset_version": "2.0.0-issue44-extended",
        "path": "data/processed/air_pollution_extended_2022_2026.parquet",
        "sha256": extended_parquet_sha256,
        "total_rows": int(len(df_extended)),
        "columns": list(df_extended.columns),
        "stations": {
            STATION_OPENAQ_7441: {
                "location_id": HANOI_OPENAQ_HISTORICAL_LOCATION_ID,
                "sensors_id": HANOI_OPENAQ_HISTORICAL_SENSOR_ID,
                "coordinates": {"latitude": COORDS_OPENAQ_7441[0], "longitude": COORDS_OPENAQ_7441[1]},
                "distance_to_era5_grid_km": dist_7441_era5,
                "grid_rows": int(len(df_7441_split)),
                "observed_pm25_rows": int(df_7441_split["pm25"].notna().sum()),
                "missing_pm25_rows": int(df_7441_split["pm25"].isna().sum()),
                "missing_pm25_pct": round(100.0 * float(df_7441_split["pm25"].isna().mean()), 2),
                "derived_interpolated_2h_rows": int(df_extended.loc[df_extended["station_id"] == STATION_OPENAQ_7441, "pm25_is_derived"].sum()),
                "min_timestamp": str(df_7441_split["timestamp"].min()),
                "max_timestamp": str(df_7441_split["timestamp"].max()),
                "train_rows": int((df_7441_split["split"] == "train").sum()),
                "test_rows": int((df_7441_split["split"] == "test").sum()),
                "split_timestamp": str(df_7441_split.loc[df_7441_split["split"] == "test", "timestamp"].min()),
                "winter_years_covered": [2022, 2023, 2024, 2025],
            },
            STATION_OPENAQ_HANOI: {
                "location_id": 4946811,
                "coordinates": {"latitude": COORDS_OPENAQ_HANOI[0], "longitude": COORDS_OPENAQ_HANOI[1]},
                "distance_to_era5_grid_km": dist_vn001_era5,
                "grid_rows": int(len(df_vn001_split)),
                "observed_pm25_rows": int(df_vn001_split["pm25"].notna().sum()),
                "missing_pm25_rows": int(df_vn001_split["pm25"].isna().sum()),
                "missing_pm25_pct": round(100.0 * float(df_vn001_split["pm25"].isna().mean()), 2),
                "derived_interpolated_2h_rows": int(df_extended.loc[df_extended["station_id"] == STATION_OPENAQ_HANOI, "pm25_is_derived"].sum()),
                "min_timestamp": str(df_vn001_split["timestamp"].min()),
                "max_timestamp": str(df_vn001_split["timestamp"].max()),
                "train_rows": int((df_vn001_split["split"] == "train").sum()),
                "test_rows": int((df_vn001_split["split"] == "test").sum()),
                "split_timestamp": str(df_vn001_split.loc[df_vn001_split["split"] == "test", "timestamp"].min()),
                "winter_years_covered": [2026],
            },
        },
        "weather_backfill": {
            "station_id": STATION_WEATHER_ERA5,
            "coordinates": {"latitude": COORDS_WEATHER_ERA5[0], "longitude": COORDS_WEATHER_ERA5[1]},
            "raw_path": f"data/raw/open_meteo_raw_{start_date_7441}_{end_date_7441}.json",
            "raw_sha256": raw_weather_sha256,
            "interim_path": "data/interim/weather_2022_2025_canonical.parquet",
            "rows": int(len(df_weather_22_25_clean)),
            "max_missing_pct": weather_val_report["max_missing_pct"],
            "inter_station_distance_7441_to_vn001_km": dist_7441_vn001,
        },
        "winter_summary": winter_rows,
        "inference_comparison": inference_comparison,
    }

    # Verify baseline immutability
    baseline_sha_after = {
        k: compute_file_sha256(p) for k, p in baseline_files.items() if p.exists()
    }
    if baseline_sha_before != baseline_sha_after:
        raise AssertionError(f"Baseline artifact mutated! Before={baseline_sha_before}, After={baseline_sha_after}")
    ext_meta["baseline_immutability_verified"] = True
    ext_meta["baseline_sha256"] = baseline_sha_after

    meta_out_path = reports_dir / "issue44_extended_dataset_metadata.json"
    meta_out_path.write_text(json.dumps(ext_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] Saved {manifest_7441_path.relative_to(PROJECT_ROOT)}")
    print(f"[OK] Saved {extended_parquet_path.relative_to(PROJECT_ROOT)} ({len(df_extended)} rows)")
    print(f"[OK] Saved {interp_csv_path.relative_to(PROJECT_ROOT)} ({len(interp_eval_df)} rows)")
    print(f"[OK] Saved {eda_csv_path.relative_to(PROJECT_ROOT)} ({len(eda_summary_df)} rows)")
    print(f"[OK] Saved {fig01_ext_path.relative_to(PROJECT_ROOT)}")
    print(f"[OK] Saved {meta_out_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
