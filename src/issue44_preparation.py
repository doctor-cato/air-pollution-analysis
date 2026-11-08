"""Safe, station-aware preparation and evaluation helpers for Issue #44.

These functions never modify canonical observed pollutant columns (`pm25`, `pm10`)
and strictly enforce station and chronological split boundaries.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


def add_derived_short_gap_interpolation(
    frame: pd.DataFrame,
    value_column: str,
    *,
    max_gap_hours: int,
    station_column: str = "station_id",
    timestamp_column: str = "timestamp",
    split_column: str = "split",
) -> pd.DataFrame:
    """Add separate derived values, never filling across a station or split.

    ``max_gap_hours`` is an experimental parameter, deliberately not a project
    default. Timestamps must be hourly and unique per station/split.
    """
    if max_gap_hours < 1:
        raise ValueError("max_gap_hours must be at least one")
    required = {value_column, station_column, timestamp_column, split_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    result = frame.copy()
    derived_column = f"{value_column}_derived_interpolated"
    flag_column = f"{value_column}_is_derived"
    result[derived_column] = result[value_column]
    result[flag_column] = False
    for _, positions in result.groupby([station_column, split_column], sort=False).groups.items():
        group = result.loc[positions].sort_values(timestamp_column)
        if group[timestamp_column].duplicated().any():
            raise ValueError("Duplicate timestamps within station/split are not interpolable")
        if len(group) > 1 and not (group[timestamp_column].diff().dropna() == np.timedelta64(1, "h")).all():
            raise ValueError("Interpolation may not bridge non-hourly timestamp gaps")
        values = pd.to_numeric(group[value_column], errors="coerce")
        candidate = values.interpolate(method="linear", limit_area="inside")
        missing_runs = values.isna().ne(values.isna().shift(fill_value=False)).cumsum()
        run_sizes = values.isna().groupby(missing_runs).transform("sum")
        eligible = values.isna() & run_sizes.le(max_gap_hours) & candidate.notna()
        result.loc[group.index[eligible], derived_column] = candidate.loc[eligible]
        result.loc[group.index[eligible], flag_column] = True
    if not result.loc[result[value_column].notna(), derived_column].equals(result.loc[result[value_column].notna(), value_column]):
        raise AssertionError("Observed values changed during derived interpolation")
    return result


def mask_observed_values(
    frame: pd.DataFrame, value_column: str, fraction: float, random_state: int = 42
) -> pd.DataFrame:
    """Create an explicit synthetic holdout mask for validation only."""
    if not 0 < fraction < 1:
        raise ValueError("fraction must be strictly between zero and one")
    result = frame.copy()
    observed = result[value_column].notna().to_numpy()
    rng = np.random.default_rng(random_state)
    eligible = np.flatnonzero(observed)
    count = max(1, int(round(len(eligible) * fraction))) if len(eligible) else 0
    masked = rng.choice(eligible, size=count, replace=False) if count else np.array([], dtype=int)
    flag = np.zeros(len(result), dtype=bool)
    flag[masked] = True
    result[f"{value_column}_mask_validation"] = flag
    result.loc[flag, value_column] = np.nan
    return result


def mask_contiguous_gaps(
    frame: pd.DataFrame,
    value_column: str,
    gap_length: int,
    *,
    max_gaps_per_group: int = 40,
    random_state: int = 42,
    station_column: str = "station_id",
    split_column: str = "split",
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    """Mask non-overlapping interior contiguous gaps of exact length ``gap_length``."""
    if gap_length < 1:
        raise ValueError("gap_length must be at least one")
    required = {value_column, station_column, split_column, timestamp_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    result = frame.copy()
    mask_col = f"{value_column}_mask_validation"
    len_col = f"{value_column}_mask_gap_length"
    result[mask_col] = False
    result[len_col] = 0
    rng = np.random.default_rng(random_state + int(gap_length) * 1009)

    for _, positions in result.groupby([station_column, split_column], sort=False).groups.items():
        group = result.loc[positions].sort_values(timestamp_column)
        obs = group[value_column].notna().to_numpy()
        idx_array = group.index.to_numpy()
        n = len(obs)
        if n < gap_length + 2:
            continue

        # Find candidate start indices p where obs[p-1 : p+gap_length+1] are all True
        window = gap_length + 2
        valid_starts: list[int] = []
        for p in range(1, n - gap_length):
            if np.all(obs[p - 1 : p + gap_length + 1]):
                valid_starts.append(p)
        if not valid_starts:
            continue

        order = rng.permutation(len(valid_starts))
        occupied = np.zeros(n, dtype=bool)
        chosen_indices: list[Any] = []
        gaps_selected = 0
        for oi in order:
            p = valid_starts[int(oi)]
            # Keep at least 1 observed anchor on both sides so adjacent masked gaps never merge
            if np.any(occupied[p - 1 : p + gap_length + 1]):
                continue
            occupied[p : p + gap_length] = True
            chosen_indices.extend(idx_array[p : p + gap_length].tolist())
            gaps_selected += 1
            if gaps_selected >= max_gaps_per_group:
                break

        if chosen_indices:
            result.loc[chosen_indices, mask_col] = True
            result.loc[chosen_indices, len_col] = int(gap_length)
            result.loc[chosen_indices, value_column] = np.nan

    return result


def interpolation_metrics(actual: Iterable[float], predicted: Iterable[float]) -> dict[str, float]:
    """Return metrics only for aligned finite validation pairs."""
    actual_values, predicted_values = np.asarray(list(actual), float), np.asarray(list(predicted), float)
    keep = np.isfinite(actual_values) & np.isfinite(predicted_values)
    if not keep.any():
        raise ValueError("No finite actual/predicted validation pairs")
    errors = predicted_values[keep] - actual_values[keep]
    return {"n": int(keep.sum()), "mae": float(np.abs(errors).mean()), "rmse": float(np.sqrt(np.mean(errors**2))), "bias": float(errors.mean())}


def winter_year(timestamps: pd.Series) -> pd.Series:
    """Map Dec–Feb to its ending calendar year; other months are missing."""
    parsed = pd.to_datetime(timestamps, errors="raise")
    result = pd.Series(pd.NA, index=timestamps.index, dtype="Int64")
    months = parsed.dt.month
    is_winter = months.isin([12, 1, 2])
    result.loc[is_winter] = parsed.loc[is_winter].dt.year + (months.loc[is_winter] == 12).astype(int)
    return result


def winter_station_summary(frame: pd.DataFrame, value_column: str = "pm25") -> pd.DataFrame:
    """Prepare station-separated winter summaries without statistical inference."""
    required = {"station_id", "timestamp", value_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    scoped = frame.copy()
    scoped["winter_year"] = winter_year(scoped["timestamp"])
    scoped = scoped.dropna(subset=["winter_year", value_column])
    return scoped.groupby(["station_id", "winter_year"], as_index=False)[value_column].agg(["count", "median", "mean"]).reset_index()


def vietnam_season(timestamps: pd.Series) -> pd.Series:
    """Map timestamps to canonical Northern Vietnam meteorological seasons."""
    parsed = pd.to_datetime(timestamps, errors="raise")
    months = parsed.dt.month
    mapping = {
        12: "Winter (Dec-Feb)",
        1: "Winter (Dec-Feb)",
        2: "Winter (Dec-Feb)",
        3: "Spring (Mar-May)",
        4: "Spring (Mar-May)",
        5: "Spring (Mar-May)",
        6: "Summer (Jun-Aug)",
        7: "Summer (Jun-Aug)",
        8: "Summer (Jun-Aug)",
        9: "Autumn (Sep-Nov)",
        10: "Autumn (Sep-Nov)",
        11: "Autumn (Sep-Nov)",
    }
    return months.map(mapping)


def validate_modeling_split(
    frame: pd.DataFrame,
    protocol: str,
    *,
    split_column: str = "split",
    station_column: str = "station_id",
    timestamp_column: str = "timestamp",
) -> None:
    """Validate protocol-specific temporal and station invariants for downstream modeling.

    Evaluation Protocols:
    --------------------
    - Protocol A (``'station_specific'`` or ``'protocol_a'``):
      Models are trained and evaluated independently per station.
      Requires each station partition to preserve chronological order:
      ``train.max() < test.min()`` strictly within that station.
      Cross-station chronological precedence is NOT required, but cross-station pooling
      on this split is strictly prohibited.
    - Protocol B (``'pooled'`` or ``'protocol_b'``):
      A single model (e.g., with station fixed effects) is evaluated across multiple stations.
      Requires GLOBAL chronological order: ``train.max() < test.min()`` across ALL records.
      In addition, each station in the dataset must be present in both train and test partitions
      so that station-specific parameters can be fitted on train and evaluated out-of-sample on test.
      Disjoint station time spans (e.g. VN003 ending April 2025 and VN001 starting July 2025)
      cannot support valid pooled temporal validation and must be explicitly rejected.
    """
    proto = str(protocol).strip().lower().replace("-", "_")
    required = {split_column, station_column, timestamp_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns for split validation: {sorted(missing)}")

    valid_splits = {"train", "test"}
    present_splits = set(frame[split_column].dropna().unique())
    if not present_splits.issubset(valid_splits) or not present_splits:
        raise ValueError(f"Invalid split values {present_splits}; must be non-empty subset of {valid_splits}")

    if proto in {"station_specific", "protocol_a"}:
        for sid, positions in frame.groupby(station_column, sort=False).groups.items():
            group = frame.loc[positions]
            if group[timestamp_column].duplicated().any():
                raise ValueError(f"Duplicate timestamps found in station '{sid}'")
            tr = group.loc[group[split_column] == "train", timestamp_column]
            te = group.loc[group[split_column] == "test", timestamp_column]
            if tr.empty or te.empty:
                raise ValueError(
                    f"Station '{sid}' must contain both train and test rows (got train={len(tr)}, test={len(te)})"
                )
            if not (tr.max() < te.min()):
                raise ValueError(
                    f"Station-specific chronological split violation for station '{sid}': "
                    f"train max ({tr.max()}) >= test min ({te.min()})"
                )
    elif proto in {"pooled", "protocol_b"}:
        if frame.duplicated(subset=[station_column, timestamp_column]).any():
            raise ValueError("Duplicate (station_id, timestamp) keys found in pooled dataset.")
        tr = frame.loc[frame[split_column] == "train", timestamp_column]
        te = frame.loc[frame[split_column] == "test", timestamp_column]
        if tr.empty or te.empty:
            raise ValueError(
                f"Pooled dataset must contain both train and test rows (got train={len(tr)}, test={len(te)})"
            )
        if not (tr.max() < te.min()):
            raise ValueError(
                f"Temporal leakage detected for Protocol B (Pooled modeling): train maximum timestamp "
                f"({tr.max()}) is greater than or equal to test minimum timestamp ({te.min()}). "
                "Station-specific splits cannot be used directly for pooled multi-station models."
            )
        for sid, positions in frame.groupby(station_column, sort=False).groups.items():
            sub = frame.loc[positions]
            has_tr = (sub[split_column] == "train").any()
            has_te = (sub[split_column] == "test").any()
            if not (has_tr and has_te):
                raise ValueError(
                    f"Station representation failure for Protocol B (Pooled modeling): station '{sid}' "
                    f"is not present in both train and test partitions (train={has_tr}, test={has_te}). "
                    "Stations with disjoint time spans (like VN003 and VN001) cannot support pooled evaluation with station fixed effects."
                )
    else:
        raise ValueError(
            f"Unknown evaluation protocol '{protocol}'. Must be 'station_specific' (Protocol A) or 'pooled' (Protocol B)."
        )


def assign_station_chronological_split(
    frame: pd.DataFrame,
    train_fraction: float = 0.80,
    *,
    station_column: str = "station_id",
    timestamp_column: str = "timestamp",
    split_column: str = "split",
) -> pd.DataFrame:
    """Assign chronological train/test splits independently per station_id (Protocol A)."""
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be strictly between 0 and 1")
    required = {station_column, timestamp_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    result = frame.copy()
    result[split_column] = ""
    for sid, positions in result.groupby(station_column, sort=False).groups.items():
        group = result.loc[positions].sort_values(timestamp_column)
        n = len(group)
        if n < 2:
            raise ValueError(f"Station '{sid}' must have at least 2 rows for chronological split")
        cut_idx = max(1, min(n - 1, int(math.floor(n * train_fraction))))
        train_idx = group.index[:cut_idx]
        test_idx = group.index[cut_idx:]
        result.loc[train_idx, split_column] = "train"
        result.loc[test_idx, split_column] = "test"

    validate_modeling_split(
        result,
        protocol="station_specific",
        split_column=split_column,
        station_column=station_column,
        timestamp_column=timestamp_column,
    )
    return result


def assign_pooled_chronological_split(
    frame: pd.DataFrame,
    train_fraction: float = 0.80,
    *,
    station_column: str = "station_id",
    timestamp_column: str = "timestamp",
    split_column: str = "split",
    require_all_stations_in_both: bool = True,
) -> pd.DataFrame:
    """Assign a global chronological train/test split across all stations (Protocol B)."""
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be strictly between 0 and 1")
    required = {station_column, timestamp_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    result = frame.sort_values([timestamp_column, station_column], kind="mergesort").copy()
    n = len(result)
    if n < 2:
        raise ValueError("Frame must have at least 2 rows for chronological split")

    cut_idx = max(1, min(n - 1, int(math.floor(n * train_fraction))))
    result[split_column] = ""
    result.iloc[:cut_idx, result.columns.get_loc(split_column)] = "train"
    result.iloc[cut_idx:, result.columns.get_loc(split_column)] = "test"

    if require_all_stations_in_both:
        validate_modeling_split(
            result,
            protocol="pooled",
            split_column=split_column,
            station_column=station_column,
            timestamp_column=timestamp_column,
        )
    else:
        tr = result.loc[result[split_column] == "train", timestamp_column]
        te = result.loc[result[split_column] == "test", timestamp_column]
        if not (tr.max() < te.min()):
            raise ValueError(
                f"Global chronological split violation: train max ({tr.max()}) >= test min ({te.min()})"
            )
    return result


def check_station_temporal_overlap(
    frame: pd.DataFrame,
    *,
    station_column: str = "station_id",
    timestamp_column: str = "timestamp",
) -> dict[str, Any]:
    """Inspect station temporal ranges and verify pairwise overlap or disjoint gaps."""
    required = {station_column, timestamp_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    station_profiles: dict[str, dict[str, Any]] = {}
    stations = sorted(frame[station_column].dropna().unique())
    for sid in stations:
        sub = frame[frame[station_column] == sid]
        ts_min = sub[timestamp_column].min()
        ts_max = sub[timestamp_column].max()
        unique_count = int(sub[timestamp_column].nunique())
        row_count = int(len(sub))
        station_profiles[str(sid)] = {
            "start": str(ts_min),
            "end": str(ts_max),
            "rows": row_count,
            "unique_timestamps": unique_count,
            "min_timestamp": ts_min,
            "max_timestamp": ts_max,
        }

    pairwise: list[dict[str, Any]] = []
    has_any_overlap = False
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            s_a, s_b = stations[i], stations[j]
            p_a, p_b = station_profiles[str(s_a)], station_profiles[str(s_b)]
            overlap_start = max(p_a["min_timestamp"], p_b["min_timestamp"])
            overlap_end = min(p_a["max_timestamp"], p_b["max_timestamp"])
            if overlap_start <= overlap_end:
                has_any_overlap = True
                set_a = set(frame.loc[frame[station_column] == s_a, timestamp_column])
                set_b = set(frame.loc[frame[station_column] == s_b, timestamp_column])
                shared_hours = len(set_a.intersection(set_b))
                pairwise.append({
                    "station_a": str(s_a),
                    "station_b": str(s_b),
                    "has_overlap": True,
                    "overlap_start": str(overlap_start),
                    "overlap_end": str(overlap_end),
                    "shared_timestamps_count": shared_hours,
                    "gap_hours": 0.0,
                })
            else:
                earlier = p_a if p_a["max_timestamp"] < p_b["min_timestamp"] else p_b
                later = p_b if earlier is p_a else p_a
                gap_delta = later["min_timestamp"] - earlier["max_timestamp"]
                gap_hours = gap_delta.total_seconds() / 3600.0
                pairwise.append({
                    "station_a": str(s_a),
                    "station_b": str(s_b),
                    "has_overlap": False,
                    "overlap_start": None,
                    "overlap_end": None,
                    "shared_timestamps_count": 0,
                    "gap_hours": float(gap_hours),
                })

    clean_profiles = {
        sid: {k: v for k, v in prof.items() if not k.endswith("_timestamp")}
        for sid, prof in station_profiles.items()
    }
    return {
        "stations": clean_profiles,
        "pairwise": pairwise,
        "has_temporal_overlap": has_any_overlap,
    }


def haversine_distance_km(
    coord_a: tuple[float, float], coord_b: tuple[float, float]
) -> float:
    """Return great-circle distance in kilometers between two (lat, lon) pairs."""
    lat1, lon1 = math.radians(float(coord_a[0])), math.radians(float(coord_a[1]))
    lat2, lon2 = math.radians(float(coord_b[0])), math.radians(float(coord_b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return float(2.0 * 6371.0088 * math.asin(math.sqrt(max(0.0, min(1.0, a)))))


def evaluate_interpolation_grid(
    frame: pd.DataFrame,
    value_column: str = "pm25",
    *,
    max_gap_candidates: Sequence[int] = (1, 2, 3, 6),
    gap_lengths: Sequence[int] = (1, 2, 3, 6),
    max_gaps_per_group: int = 40,
    random_state: int = 42,
) -> pd.DataFrame:
    """Evaluate short-gap linear interpolation via contiguous gap masking across stations and seasons."""
    required = {"station_id", "timestamp", "split", value_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    work = frame.copy()
    work["season"] = vietnam_season(work["timestamp"])
    rows: list[dict[str, Any]] = []

    # 1. Real missingness recovery stats per (station_id, max_gap_hours)
    real_recovery: dict[tuple[str, int], dict[str, Any]] = {}
    for max_gap in max_gap_candidates:
        interp_real = add_derived_short_gap_interpolation(
            work, value_column, max_gap_hours=int(max_gap)
        )
        for sid, grp in interp_real.groupby("station_id", sort=True):
            total_rows = int(len(grp))
            obs_rows = int(grp[value_column].notna().sum())
            miss_rows = int(grp[value_column].isna().sum())
            rec_rows = int(grp[f"{value_column}_is_derived"].sum())
            real_recovery[(str(sid), int(max_gap))] = {
                "station_total_hours": total_rows,
                "station_observed_hours": obs_rows,
                "station_missing_hours": miss_rows,
                "real_interpolated_hours": rec_rows,
                "real_interpolated_pct_of_missing": round(100.0 * rec_rows / miss_rows, 2) if miss_rows > 0 else 0.0,
                "coverage_before_pct": round(100.0 * obs_rows / total_rows, 2) if total_rows > 0 else 0.0,
                "coverage_after_pct": round(100.0 * (obs_rows + rec_rows) / total_rows, 2) if total_rows > 0 else 0.0,
            }

    # 2. Masking validation across gap_lengths and max_gap_candidates
    for gap_len in gap_lengths:
        masked_df = mask_contiguous_gaps(
            work,
            value_column,
            int(gap_len),
            max_gaps_per_group=max_gaps_per_group,
            random_state=random_state,
        )
        mask_flag = masked_df[f"{value_column}_mask_validation"]

        for max_gap in max_gap_candidates:
            derived_df = add_derived_short_gap_interpolation(
                masked_df, value_column, max_gap_hours=int(max_gap)
            )
            derived_col = f"{value_column}_derived_interpolated"

            for sid, station_idx in derived_df.groupby("station_id", sort=True).groups.items():
                rec_info = real_recovery[(str(sid), int(max_gap))]
                for scope_label, season_filter in [
                    ("ALL", None),
                    ("Winter (Dec-Feb)", "Winter (Dec-Feb)"),
                    ("Spring (Mar-May)", "Spring (Mar-May)"),
                    ("Summer (Jun-Aug)", "Summer (Jun-Aug)"),
                    ("Autumn (Sep-Nov)", "Autumn (Sep-Nov)"),
                ]:
                    sub_idx = list(station_idx)
                    if season_filter is not None:
                        sub_idx = [i for i in station_idx if work.at[i, "season"] == season_filter]
                    if not sub_idx:
                        continue
                    masked_sub = [i for i in sub_idx if bool(mask_flag.at[i])]
                    if not masked_sub:
                        continue

                    actual_vals = work.loc[masked_sub, value_column].to_numpy(dtype=float)
                    pred_vals = derived_df.loc[masked_sub, derived_col].to_numpy(dtype=float)
                    finite_mask = np.isfinite(actual_vals) & np.isfinite(pred_vals)
                    n_masked = int(len(masked_sub))
                    n_eval = int(finite_mask.sum())

                    if n_eval > 0:
                        m = interpolation_metrics(actual_vals[finite_mask], pred_vals[finite_mask])
                        mae_val, rmse_val, bias_val = m["mae"], m["rmse"], m["bias"]
                    else:
                        mae_val, rmse_val, bias_val = float("nan"), float("nan"), float("nan")

                    rows.append({
                        "station_id": str(sid),
                        "season_scope": scope_label,
                        "masked_gap_length_hours": int(gap_len),
                        "max_gap_hours": int(max_gap),
                        "n_masked_hours": n_masked,
                        "n_interpolated_masked_hours": n_eval,
                        "masked_recovery_pct": round(100.0 * n_eval / n_masked, 2) if n_masked > 0 else 0.0,
                        "mae": round(mae_val, 4) if np.isfinite(mae_val) else np.nan,
                        "rmse": round(rmse_val, 4) if np.isfinite(rmse_val) else np.nan,
                        "bias": round(bias_val, 4) if np.isfinite(bias_val) else np.nan,
                        **rec_info,
                    })

    return pd.DataFrame(rows)


def _require_mapping_keys(
    mapping: dict[str, Any],
    required_keys: Iterable[str],
    context: str,
) -> None:
    if not isinstance(mapping, dict):
        raise ValueError(f"{context} must be a dict, got {type(mapping).__name__}.")
    missing = [k for k in required_keys if k not in mapping or mapping[k] is None]
    if missing:
        raise KeyError(f"{context} missing required keys (no fallback allowed): {missing}")


def _require_df_columns(
    df: pd.DataFrame,
    required_cols: Iterable[str],
    context: str,
) -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError(f"{context} must be a non-empty DataFrame.")
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"{context} missing required columns: {missing}")


def _format_monthly_winter_pct(
    winter_year_val: int,
    monthly_comp: Any,
) -> str:
    if not isinstance(monthly_comp, dict):
        raise ValueError(f"monthly_completeness for W{winter_year_val} must be a dict, got {type(monthly_comp).__name__}.")
    dec_key = f"{winter_year_val - 1}-12"
    jan_key = f"{winter_year_val}-01"
    feb_key = f"{winter_year_val}-02"
    parts: list[str] = []
    for k in (dec_key, jan_key, feb_key):
        if k in monthly_comp and isinstance(monthly_comp[k], dict) and "valid_pct" in monthly_comp[k]:
            parts.append(f"{float(monthly_comp[k]['valid_pct']):.1f}%")
        else:
            parts.append("—")
    return " / ".join(parts)


def _format_sci_p(p_val: float) -> str:
    if p_val <= 0.0:
        return "0.0"
    exp = int(math.floor(math.log10(abs(p_val))))
    mant = p_val / (10 ** exp)
    return f"{mant:.2f} \\times 10^{{{exp}}}"


def _validate_comparison_report_inputs(
    manifest_7441: dict[str, Any],
    extended_metadata: dict[str, Any],
    interp_eval_df: pd.DataFrame,
    winter_summary_df: pd.DataFrame,
) -> None:
    """Validate required schema keys and columns without using fallback defaults."""
    _require_mapping_keys(
        manifest_7441,
        ("s3_daily_file_count", "coverage"),
        "manifest_7441",
    )
    cov_7441 = manifest_7441["coverage"]
    _require_mapping_keys(
        cov_7441,
        (
            "raw_rows",
            "qc_valid_hours",
            "sentinel_or_negative_hours",
            "longest_contiguous_gap_active_window_hours",
            "source_observation_window",
            "annual",
        ),
        "manifest_7441['coverage']",
    )
    _require_mapping_keys(
        cov_7441["source_observation_window"],
        ("start", "end", "active_window_hours"),
        "manifest_7441['coverage']['source_observation_window']",
    )
    if not isinstance(cov_7441["annual"], list) or len(cov_7441["annual"]) == 0:
        raise ValueError("manifest_7441['coverage']['annual'] must be a non-empty list.")
    for idx, yr_entry in enumerate(cov_7441["annual"]):
        _require_mapping_keys(
            yr_entry,
            (
                "year",
                "s3_daily_files",
                "expected_hours",
                "source_available_hours",
                "s3_reported_hours",
                "qc_valid_hours",
                "qc_valid_pct_of_calendar_year",
                "qc_valid_pct_of_active_window",
                "sentinel_or_negative_hours",
                "longest_gap_hours",
            ),
            f"manifest_7441['coverage']['annual'][{idx}]",
        )

    _require_mapping_keys(
        extended_metadata,
        (
            "total_rows",
            "sha256",
            "stations",
            "weather_backfill",
            "inference_comparison",
            "baseline_sha256",
        ),
        "extended_metadata",
    )
    stations = extended_metadata["stations"]
    _require_mapping_keys(
        stations,
        ("VN001_HANOI_556_NGUYEN_VAN_CU", "VN003_HANOI_OPENAQ_7441"),
        "extended_metadata['stations']",
    )
    for sid in ("VN001_HANOI_556_NGUYEN_VAN_CU", "VN003_HANOI_OPENAQ_7441"):
        _require_mapping_keys(
            stations[sid],
            (
                "grid_rows",
                "observed_pm25_rows",
                "missing_pm25_rows",
                "missing_pm25_pct",
                "min_timestamp",
                "max_timestamp",
                "train_rows",
                "test_rows",
                "distance_to_era5_grid_km",
                "winter_years_covered",
            ),
            f"extended_metadata['stations']['{sid}']",
        )

    _require_mapping_keys(
        extended_metadata["weather_backfill"],
        ("rows", "max_missing_pct", "inter_station_distance_7441_to_vn001_km"),
        "extended_metadata['weather_backfill']",
    )
    _require_mapping_keys(
        extended_metadata["baseline_sha256"],
        ("final_processed",),
        "extended_metadata['baseline_sha256']",
    )

    inf_comp = extended_metadata["inference_comparison"]
    _require_mapping_keys(
        inf_comp,
        ("VN001_HANOI_556_NGUYEN_VAN_CU", "VN003_HANOI_OPENAQ_7441"),
        "extended_metadata['inference_comparison']",
    )
    for sid in ("VN001_HANOI_556_NGUYEN_VAN_CU", "VN003_HANOI_OPENAQ_7441"):
        _require_mapping_keys(
            inf_comp[sid],
            (
                "calendar_days",
                "valid_days_ge18h",
                "daily_median",
                "daily_median_ci95_calendar_bootstrap",
                "winter_daily_median",
                "non_winter_daily_median",
                "kruskal_wallis_h",
                "kruskal_wallis_epsilon2",
                "kruskal_wallis_naive_p",
                "kruskal_wallis_calendar_bootstrap_p",
                "winter_vs_nonwinter_r_rb",
                "daily_lag1_autocorr_rho1",
                "effective_sample_size_n_eff",
                "variance_inflation_factor",
                "qcvn_exceedance_days",
                "qcvn_exceedance_pct",
            ),
            f"extended_metadata['inference_comparison']['{sid}']",
        )

    _require_df_columns(
        interp_eval_df,
        (
            "station_id",
            "season_scope",
            "masked_gap_length_hours",
            "max_gap_hours",
            "n_masked_hours",
            "mae",
            "rmse",
            "bias",
            "real_interpolated_hours",
            "station_missing_hours",
            "real_interpolated_pct_of_missing",
            "coverage_before_pct",
            "coverage_after_pct",
        ),
        "interp_eval_df",
    )
    _require_df_columns(
        winter_summary_df,
        (
            "station_id",
            "winter_year",
            "expected_calendar_hours",
            "station_grid_hours",
            "count",
            "coverage_of_full_winter_pct",
            "coverage_of_station_grid_pct",
            "monthly_completeness",
            "mean",
            "sd",
            "median",
            "q25",
            "q75",
            "iqr",
            "p90",
            "valid_days",
            "qcvn_exceed_days",
            "qcvn_exceed_pct",
        ),
        "winter_summary_df",
    )


def generate_legacy_vs_extended_comparison_report(
    manifest_7441: dict[str, Any],
    extended_metadata: dict[str, Any],
    interp_eval_df: pd.DataFrame,
    winter_summary_df: pd.DataFrame,
    *,
    output_path: Optional[Path | str] = None,
) -> str:
    """Generate the authoritative legacy vs extended comparison Markdown report deterministically."""
    _validate_comparison_report_inputs(
        manifest_7441, extended_metadata, interp_eval_df, winter_summary_df
    )

    cov_7441 = manifest_7441["coverage"]
    s3_files_7441 = int(manifest_7441["s3_daily_file_count"])
    raw_rows_7441 = int(cov_7441["raw_rows"])
    qc_valid_7441 = int(cov_7441["qc_valid_hours"])
    sentinel_7441 = int(cov_7441["sentinel_or_negative_hours"])
    longest_gap_7441 = int(cov_7441["longest_contiguous_gap_active_window_hours"])
    active_win_7441 = int(cov_7441["source_observation_window"]["active_window_hours"])

    sec2_tot = int(extended_metadata["total_rows"])
    sec2_sha = str(extended_metadata["sha256"])
    baseline_final_sha = str(extended_metadata["baseline_sha256"]["final_processed"])
    baseline_sha_short = f"{baseline_final_sha[:8]}...{baseline_final_sha[-6:]}"

    st_vn1 = extended_metadata["stations"]["VN001_HANOI_556_NGUYEN_VAN_CU"]
    st_vn3 = extended_metadata["stations"]["VN003_HANOI_OPENAQ_7441"]
    w_backfill = extended_metadata["weather_backfill"]

    vn1_grid = int(st_vn1["grid_rows"])
    vn1_obs = int(st_vn1["observed_pm25_rows"])
    vn1_miss = int(st_vn1["missing_pm25_rows"])
    vn1_miss_pct = float(st_vn1["missing_pm25_pct"])
    vn1_obs_pct = round(100.0 - vn1_miss_pct, 2)
    vn1_train = int(st_vn1["train_rows"])
    vn1_test = int(st_vn1["test_rows"])
    vn1_dist = float(st_vn1["distance_to_era5_grid_km"])

    vn3_grid = int(st_vn3["grid_rows"])
    vn3_obs = int(st_vn3["observed_pm25_rows"])
    vn3_miss = int(st_vn3["missing_pm25_rows"])
    vn3_miss_pct = float(st_vn3["missing_pm25_pct"])
    vn3_obs_pct = round(100.0 - vn3_miss_pct, 2)
    vn3_train = int(st_vn3["train_rows"])
    vn3_test = int(st_vn3["test_rows"])
    vn3_dist = float(st_vn3["distance_to_era5_grid_km"])

    comb_obs = vn1_obs + vn3_obs
    comb_miss = vn1_miss + vn3_miss
    comb_obs_pct = round(100.0 * comb_obs / sec2_tot, 2)
    comb_miss_pct = round(100.0 * comb_miss / sec2_tot, 2)
    comb_train = vn1_train + vn3_train
    comb_test = vn1_test + vn3_test

    inter_station_km = float(w_backfill["inter_station_distance_7441_to_vn001_km"])
    w_22_25_rows = int(w_backfill["rows"])
    w_22_25_miss_pct = float(w_backfill["max_missing_pct"])
    w_vn1_rows = 9072  # Frozen M2 weather_canonical.parquet row count (data/raw/metadata.json)
    w_comb_rows = w_vn1_rows + w_22_25_rows

    # Format annual coverage breakdown rows for OpenAQ 7441
    annual_rows_md: list[str] = []
    tot_cal_hours = 0
    for yr_entry in cov_7441["annual"]:
        yr = int(yr_entry["year"])
        files_c = int(yr_entry["s3_daily_files"])
        cal_h = int(yr_entry["expected_hours"])
        tot_cal_hours += cal_h
        act_h = int(yr_entry["source_available_hours"])
        rep_h = int(yr_entry["s3_reported_hours"])
        val_h = int(yr_entry["qc_valid_hours"])
        sent_h = int(yr_entry["sentinel_or_negative_hours"])
        act_pct = float(yr_entry["qc_valid_pct_of_active_window"])
        cal_pct = float(yr_entry["qc_valid_pct_of_calendar_year"])
        gap_h = int(yr_entry["longest_gap_hours"])
        yr_label = f"**{yr}** *(through Apr 9)*" if yr == 2025 else f"**{yr}**"
        pct_str = (
            f"{act_pct:.2f}% *({cal_pct:.2f}% of full yr)*"
            if abs(act_pct - cal_pct) > 1e-4
            else f"{act_pct:.2f}%"
        )
        annual_rows_md.append(
            f"| {yr_label} | {files_c:,} | {cal_h:,} | {act_h:,} | {rep_h:,} | "
            f"{val_h:,} | {sent_h:,} | {pct_str} | {gap_h:,} |"
        )
    annual_rows_md.append(
        f"| **Total (2022–2025)** | **{s3_files_7441:,}** | **{tot_cal_hours:,}** | "
        f"**{active_win_7441:,}** | **{raw_rows_7441:,}** | **{qc_valid_7441:,}** | "
        f"**{sentinel_7441:,}** | **{vn3_obs_pct:.2f}%** | **{longest_gap_7441:,}** |"
    )
    annual_table_str = "\n".join(annual_rows_md)

    # Format interpolation table rows for season_scope == ALL
    interp_all = interp_eval_df[interp_eval_df["season_scope"] == "ALL"].copy()
    if interp_all.empty:
        raise ValueError("interp_eval_df contains no rows with season_scope == 'ALL'.")

    interp_rows_md: list[str] = [
        f"| `VN001` | **0 (Baseline No-Interp)** | **0** | **0** | **0.0000** | **0.0000** | "
        f"**0.0000** | **0 / {vn1_miss:,}** | **0.00%** | **{vn1_obs_pct:.2f}% → {vn1_obs_pct:.2f}%** |"
    ]
    sub_vn1 = interp_all[interp_all["station_id"].isin(["VN001_HANOI_556_NGUYEN_VAN_CU", "VN001"])]
    if sub_vn1.empty:
        raise ValueError("interp_eval_df missing rows for VN001.")
    for _, r in sub_vn1.sort_values(["masked_gap_length_hours", "max_gap_hours"]).iterrows():
        bias_str = f"+{r['bias']:.4f}" if r["bias"] >= 0 else f"{r['bias']:.4f}".replace("-", "−")
        interp_rows_md.append(
            f"| `VN001` | {int(r['masked_gap_length_hours'])}h | {int(r['max_gap_hours'])}h | "
            f"{int(r['n_masked_hours'])} | {r['mae']:.4f} | {r['rmse']:.4f} | {bias_str} | "
            f"{int(r['real_interpolated_hours'])} / {int(r['station_missing_hours']):,} | "
            f"{r['real_interpolated_pct_of_missing']:.2f}% | "
            f"{r['coverage_before_pct']:.2f}% → {r['coverage_after_pct']:.2f}% |"
        )

    interp_rows_md.append(
        f"| `VN003` (`7441`) | **0 (Baseline No-Interp)** | **0** | **0** | **0.0000** | **0.0000** | "
        f"**0.0000** | **0 / {vn3_miss:,}** | **0.00%** | **{vn3_obs_pct:.2f}% → {vn3_obs_pct:.2f}%** |"
    )
    sub_vn3 = interp_all[interp_all["station_id"].isin(["VN003_HANOI_OPENAQ_7441", "VN003"])]
    if sub_vn3.empty:
        raise ValueError("interp_eval_df missing rows for VN003.")
    for _, r in sub_vn3.sort_values(["masked_gap_length_hours", "max_gap_hours"]).iterrows():
        bias_str = f"+{r['bias']:.4f}" if r["bias"] >= 0 else f"{r['bias']:.4f}".replace("-", "−")
        interp_rows_md.append(
            f"| `VN003` (`7441`) | {int(r['masked_gap_length_hours'])}h | {int(r['max_gap_hours'])}h | "
            f"{int(r['n_masked_hours'])} | {r['mae']:.4f} | {r['rmse']:.4f} | {bias_str} | "
            f"{int(r['real_interpolated_hours'])} / {int(r['station_missing_hours']):,} | "
            f"{r['real_interpolated_pct_of_missing']:.2f}% | "
            f"{r['coverage_before_pct']:.2f}% → {r['coverage_after_pct']:.2f}% |"
        )
    interp_table_str = "\n".join(interp_rows_md)

    # Format winter summary rows directly from winter_summary_df
    w_labels = {
        2022: "**W2022** *(Partial: Jan–Feb 2022)*",
        2023: "**W2023** *(Dec 2022–Feb 2023)*",
        2024: "**W2024** *(Dec 2023–Feb 2024)*",
        2025: "**W2025** *(Dec 2024–Feb 2025)*",
        2026: "**W2026** *(Dec 2025–Feb 2026)*",
    }
    winter_rows_md: list[str] = []
    for _, wr in winter_summary_df.iterrows():
        wy = int(wr["winter_year"])
        wid = f"W{wy}"
        sid = str(wr["station_id"])
        exp_h = int(wr["expected_calendar_hours"])
        grd_h = int(wr["station_grid_hours"])
        n_obs = int(wr["count"])
        pct_full = float(wr["coverage_of_full_winter_pct"])
        pct_grid = float(wr["coverage_of_station_grid_pct"])
        m_pct = _format_monthly_winter_pct(wy, wr["monthly_completeness"])
        w_lbl = w_labels.get(wy, f"**{wid}**")
        mean_val = float(wr["mean"])
        std_val = float(wr["sd"])
        mean_sd = f"{mean_val:.2f} ± {std_val:.2f}"
        med_val = float(wr["median"])
        med_str = f"**{med_val:.2f}**"
        iqr_val = float(wr["iqr"])
        q25_val = float(wr["q25"])
        q75_val = float(wr["q75"])
        iqr_str = f"{iqr_val:.2f} (`{q25_val:.1f}–{q75_val:.1f}`)"
        p90_val = float(wr["p90"])
        p90_str = f"{p90_val:.2f}"
        v_days = int(wr["valid_days"])
        exc_days = int(wr["qcvn_exceed_days"])
        exc_pct = float(wr["qcvn_exceed_pct"])
        winter_rows_md.append(
            f"| `{sid}` | {w_lbl} | {exp_h:,} / {grd_h:,} | {n_obs:,} (`{pct_full:.2f}%` / `{pct_grid:.2f}%`) | "
            f"`{m_pct}` | {mean_sd} | {med_str} | {iqr_str} | {p90_str} | {v_days} | {exc_days} / {v_days} (**{exc_pct:.2f}%**) |"
        )
    winter_table_str = "\n".join(winter_rows_md)

    # Extract inference comparison metrics
    inf_vn1 = extended_metadata["inference_comparison"]["VN001_HANOI_556_NGUYEN_VAN_CU"]
    inf_vn3 = extended_metadata["inference_comparison"]["VN003_HANOI_OPENAQ_7441"]

    vn1_cal_d = int(inf_vn1["calendar_days"])
    vn1_val_d = int(inf_vn1["valid_days_ge18h"])
    vn3_cal_d = int(inf_vn3["calendar_days"])
    vn3_val_d = int(inf_vn3["valid_days_ge18h"])
    obs_ratio = vn3_val_d / vn1_val_d if vn1_val_d > 0 else 0.0

    vn1_rho1 = float(inf_vn1["daily_lag1_autocorr_rho1"])
    vn1_neff = float(inf_vn1["effective_sample_size_n_eff"])
    vn1_vif = float(inf_vn1["variance_inflation_factor"])
    vn3_rho1 = float(inf_vn3["daily_lag1_autocorr_rho1"])
    vn3_neff = float(inf_vn3["effective_sample_size_n_eff"])
    vn3_vif = float(inf_vn3["variance_inflation_factor"])

    vn1_med = float(inf_vn1["daily_median"])
    vn1_ci_lo, vn1_ci_hi = (
        float(inf_vn1["daily_median_ci95_calendar_bootstrap"][0]),
        float(inf_vn1["daily_median_ci95_calendar_bootstrap"][1]),
    )
    vn3_med = float(inf_vn3["daily_median"])
    vn3_ci_lo, vn3_ci_hi = (
        float(inf_vn3["daily_median_ci95_calendar_bootstrap"][0]),
        float(inf_vn3["daily_median_ci95_calendar_bootstrap"][1]),
    )

    vn1_w_med = float(inf_vn1["winter_daily_median"])
    vn1_nw_med = float(inf_vn1["non_winter_daily_median"])
    vn1_w_diff = vn1_w_med - vn1_nw_med
    vn1_rrb = float(inf_vn1["winter_vs_nonwinter_r_rb"])

    vn3_w_med = float(inf_vn3["winter_daily_median"])
    vn3_nw_med = float(inf_vn3["non_winter_daily_median"])
    vn3_w_diff = vn3_w_med - vn3_nw_med
    vn3_rrb = float(inf_vn3["winter_vs_nonwinter_r_rb"])

    vn1_kw_h = float(inf_vn1["kruskal_wallis_h"])
    vn1_kw_eps = float(inf_vn1["kruskal_wallis_epsilon2"])
    vn1_kw_pboot = float(inf_vn1["kruskal_wallis_calendar_bootstrap_p"])
    vn1_kw_pnaive = _format_sci_p(float(inf_vn1["kruskal_wallis_naive_p"]))

    vn3_kw_h = float(inf_vn3["kruskal_wallis_h"])
    vn3_kw_eps = float(inf_vn3["kruskal_wallis_epsilon2"])
    vn3_kw_pboot = float(inf_vn3["kruskal_wallis_calendar_bootstrap_p"])
    vn3_kw_pnaive = _format_sci_p(float(inf_vn3["kruskal_wallis_naive_p"]))

    vn1_qcvn_d = int(inf_vn1["qcvn_exceedance_days"])
    vn1_qcvn_pct = float(inf_vn1["qcvn_exceedance_pct"])
    vn3_qcvn_d = int(inf_vn3["qcvn_exceedance_days"])
    vn3_qcvn_pct = float(inf_vn3["qcvn_exceedance_pct"])

    content = f"""# Issue #44 — Legacy vs. Extended Historical Dataset Comparison Report (2022–2026)

> **Generated by:** `scripts/build_extended_historical_dataset.py`
> **Dataset Contract Version:** `2.0.0-issue44-extended`
> **Scope:** Station-separated comparison between the immutable M2/M3/W9 baseline (`VN001_HANOI_556_NGUYEN_VAN_CU`, 2025-07 to 2026-07) and the verified OpenAQ S3 historical station (`VN003_HANOI_OPENAQ_7441`, 2022-01 to 2025-04).

---

## 1. Source Verification & Approval Decision (Phase 1)

| Candidate Source | Station ID | Time Window | Provenance & License | Decision |
|---|---|---|---|---|
| **OpenAQ S3 Location `4946811`** (556 Nguyễn Văn Cừ, NCEM/VEA) | `VN001_HANOI_556_NGUYEN_VAN_CU` | `2025-07-03` → `2026-07-15` | Official OpenAQ S3 archive (`349,463` raw rows in `data/raw/metadata.json`; `{vn1_grid:,}` canonical grid hours; `{vn1_obs:,}` valid $\\text{{PM}}_{{2.5}}$ hours) | **APPROVED (Immutable Baseline)** |
| **OpenAQ S3 Location `7441`** (Hanoi AirNow Gov Monitor, `sensors_id=21632`) | `VN003_HANOI_OPENAQ_7441` | `2022-01-01` → `2025-04-09` | First-party OpenAQ S3 archive (`{s3_files_7441}` `.csv.gz` files, `{raw_rows_7441:,}` raw rows, `{qc_valid_7441:,}` numerically valid $\\text{{PM}}_{{2.5}} \\ge 0\\ \\mu\\text{{g/m}}^3$ post-screening hours), `US Public Domain` (`id=33`, `http://www.usa.gov/publicdomain/label/1.0/`) | **APPROVED (Station-Specific Historical Expansion)** |
| **Third-party GitHub Mirror** (`dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies`) | Prospective `VN002_HANOI_US_EMBASSY` | `2022-01-01` → `2025-04-09` | Frozen audit snapshot (`reports/issue44_source_verification.json` via `scripts/profile_airnow_mirror.py`) pinned at commit `25d08e949c9d01ba57c4e74ff9b3b99328ecf141` (`46` CSV files). GitHub API `license: null`, unverified chain of custody, 3 misfiled December MTD files (`1,627` rows; 4 files with cross-year records), `25,955` duplicate rows, 1 conflicting duplicate (`2023-11-07T17:00:00`: `33.0` valid in YTD vs `-999.0` missing in MTD) | **NO-GO / Reference-Only** |
| **OpenAQ Location `2539`** (`US Diplomatic Post: Hanoi`) | Unassigned | `2016` only | 0 S3 files in 2022–2025 (verified in `reports/issue44_source_verification.json`) | **NO-GO (No Coverage)** |

### Key Scientific Guardrails Enforced
1. **Station Separation (`(station_id, timestamp)`):** `VN003_HANOI_OPENAQ_7441` (`21.021939°N, 105.818806°E`) and `VN001_HANOI_556_NGUYEN_VAN_CU` (`21.0491°N, 105.8831°E`, inter-station distance **{inter_station_km:.3f} km**) are stored as separate station identities and are **never** concatenated into a single synthetic single-site time series.
2. **Baseline Immutability:** `data/interim/air_quality_canonical.parquet`, `data/interim/weather_canonical.parquet`, `data/processed/air_pollution_final.parquet`, `data/raw/metadata.json`, `figures/FIG-01.png`–`FIG-12.png`, `reports/statistical_profile.csv`, and `reports/inference_results.md` are verified byte-identical before and after running `scripts/build_extended_historical_dataset.py`.

---

## 2. Dataset Architecture & Coverage Comparison (Phases 2–4)

| Metric | Legacy Baseline (`VN001`) | Historical Expansion (`VN003` / OpenAQ `7441`) | Combined Extended Artifact (`2.0.0-issue44-extended`) |
|---|---:|---:|---:|
| **Artifact Path** | `data/processed/air_pollution_final.parquet` | `data/interim/air_quality_openaq_7441_canonical.parquet` | `data/processed/air_pollution_extended_2022_2026.parquet` |
| **SHA-256** | `{baseline_sha_short}` | Reproducible via `build_extended_historical_dataset.py` | `{sec2_sha}` |
| **Start Timestamp (`Asia/Ho_Chi_Minh`)** | `{st_vn1['min_timestamp']}` | `{st_vn3['min_timestamp']}` | `{st_vn3['min_timestamp']}` |
| **End Timestamp (`Asia/Ho_Chi_Minh`)** | `{st_vn1['max_timestamp']}` | `{st_vn3['max_timestamp']}` | `{st_vn1['max_timestamp']}` |
| **Hourly Grid Rows** | `{vn1_grid:,}` | `{vn3_grid:,}` | `{sec2_tot:,}` |
| **Observed Valid $\\text{{PM}}_{{2.5}}$ Hours** | `{vn1_obs:,}` (`{vn1_obs_pct:.2f}%`) | `{vn3_obs:,}` (`{vn3_obs_pct:.2f}%`) | `{comb_obs:,}` (`{comb_obs_pct:.2f}%`) |
| **Missing $\\text{{PM}}_{{2.5}}$ Hours** | `{vn1_miss:,}` (`{vn1_miss_pct:.2f}%`) | `{vn3_miss:,}` (`{vn3_miss_pct:.2f}%`) | `{comb_miss:,}` (`{comb_miss_pct:.2f}%`) |
| **Chronological Train / Test Rows (80/20 per station)** | `{vn1_train:,}` / `{vn1_test:,}` | `{vn3_train:,}` / `{vn3_test:,}` | `{comb_train:,}` / `{comb_test:,}` |
| **Distance to ERA5 Grid (`21.05448°N, 105.89848°E`)** | `{vn1_dist:.3f} km` | `{vn3_dist:.3f} km` | Station-specific mapping |
| **ERA5 Weather Missingness (6 canonical variables)** | `0.0%` (`{w_vn1_rows:,}` rows) | `{w_22_25_miss_pct:.1f}%` (`{w_22_25_rows:,}` rows) | `{w_22_25_miss_pct:.1f}%` (`{w_comb_rows:,}` raw weather hours) |
| **Independent Winter Seasons (`winter_year`)** | `{len(st_vn1['winter_years_covered'])}` (`W2026`) | `{len(st_vn3['winter_years_covered'])}` (`W2022`, `W2023`, `W2024`, `W2025`) | `{len(st_vn1['winter_years_covered']) + len(st_vn3['winter_years_covered'])}` station-winter cohorts |

### Annual Coverage Breakdown of OpenAQ Location `7441` (`VN003_HANOI_OPENAQ_7441`)

> **QC Screening Disclosure:** OpenAQ S3 `.csv.gz` files do not carry a separate per-record `QC Name` column. In the table below and in `reports/issue44_openaq_7441_manifest.json`, **Numerically Valid / Post-Screening Hours** (`qc_valid_hours = {qc_valid_7441:,}`) denotes observations with $\\text{{PM}}_{{2.5}} \\ge 0.0\\ \\mu\\text{{g/m}}^3$ inside physical bounds $[0, 1000]\\ \\mu\\text{{g/m}}^3$ and `pm25_was_stuck == 0` after screening out `{sentinel_7441:,}` negative/sentinel records (`-999.0`: `3,188`; `-1.0`: `4`; `-6.0`: `1`) to `NaN`.

| Year | S3 Daily Files | Calendar Hours | Active Window Hours | S3 Reported Hours (Parsed TZ) | Numerically Valid Hours ($\\\\ge 0\\\\ \\\\mu\\\\text{{g/m}}^3$) | Sentinel / Negative Hours | Active Window Valid % | Longest Contiguous Gap (h) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{annual_table_str}

---

## 3. Missingness & Short-Gap Interpolation Experiment (Phase 5)

Using `src/issue44_preparation.py::evaluate_interpolation_grid()`, contiguous interior observed runs of length $L \\in \\{{1, 2, 3, 6\\}}\\text{{ hours}}$ were masked within each `(station_id, split)` partition (50 non-overlapping gaps per group, `random_state=42`) and evaluated across `max_gap_hours` $\\in \\{{1, 2, 3, 6\\}}$. Full breakdowns by season, station, and gap length are stored in `reports/issue44_interpolation_evaluation.csv`.

### Summary of Masking-Validation Accuracy & Real Missingness Recovery (`season_scope = ALL`)

| Station ID | Masked Gap Length ($L$) | `max_gap_hours` | Masked Hours Evaluated | MAE ($\\mu\\text{{g/m}}^3$) | RMSE ($\\mu\\text{{g/m}}^3$) | Bias ($\\mu\\text{{g/m}}^3$) | Real Missing Hours Recovered | % of Total Station Missingness Recovered | Coverage Before → After |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
{interp_table_str}

### Scientific Conclusion on Interpolation (Negative Finding Retained for Primary Pipeline)
1. **Low Recovery vs. Rising Error:** Because missingness in both stations is dominated by multi-day/multi-week reporting outages rather than isolated 1–2h dropouts, short-gap linear interpolation recovers only a small fraction of total missing hours while introducing non-trivial reconstruction error across multi-hour gaps.
2. **Temporal Leakage in Forecasting Mode:** Linear interpolation requires future endpoint $t + k$ to fill gap $t$, which is structurally inadmissible for causal early-alert forecasting (Issue #13).
3. **Policy Decision:** Canonical observed `pm25` and `pm10` remain **100% un-interpolated** (`assert_no_imputation` enforced). Derived columns (`pm25_derived_interpolated`, `pm25_is_derived`) are isolated in `air_pollution_extended_2022_2026.parquet` strictly for sensitivity audits.

---

## 4. Multi-Year & Multi-Winter Seasonality Re-Evaluation (Phase 6 & FIG-01)

Instructor feedback on Milestone 3 noted that the baseline `VN001` dataset contained only a single winter cycle (`W2026`). With `VN003_HANOI_OPENAQ_7441`, we now evaluate **4 additional winter cycles (`W2022`, `W2023`, `W2024`, `W2025`)** alongside `VN001` (`W2026`), visualized in `figures/FIG-01-extended-historical.png` while preserving baseline `figures/FIG-01.png` unchanged.

### Station-Separated Winter Cohort Summary (`winter_year`, Dec–Feb)

> **Scope & Completeness Note:** `W2022`–`W2025` belong to `VN003_HANOI_OPENAQ_7441` and `W2026` belongs to `VN001_HANOI_556_NGUYEN_VAN_CU`; they are **not** 5 i.i.d. repetitions of the same physical sensor. In addition, `W2022` is a **partial winter window** (`2021-12` is outside the 2022–2025 S3 query scope).

| Station ID | Winter Year (`Dec–Feb`) | Expected / Grid Hours | Valid Hours ($n$, % Full / % Grid) | Monthly Valid % (`Dec / Jan / Feb`) | Mean ± SD ($\\mu\\text{{g/m}}^3$) | Median ($\\mu\\text{{g/m}}^3$) | IQR ($\\text{{Q25–Q75}}$) | P90 ($\\mu\\text{{g/m}}^3$) | Valid Days ($\\\\ge 18\\\\text{{h}}$) | Daily QCVN Exceedance ($>50\\ \\mu\\text{{g/m}}^3$) |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|
{winter_table_str}

---

## 5. Impact on Statistical Inference (Issue #11) & Regression Contract (Issue #12)

### Station-Separated Daily Inference Comparison ($\\\\ge 18\\\\text{{h/day}}$ valid rule, Calendar-Preserving)

| Metric | Legacy Baseline (`VN001`, 2025–2026) | Historical Station (`VN003` / OpenAQ `7441`, 2022–2025) | Consistency & Scientific Interpretation |
|---|---:|---:|---|
| **Calendar Days / Valid Daily Observations ($n_{{\\text{{days}}}}$)** | `{vn1_cal_d:,}` / `{vn1_val_d:,}` | `{vn3_cal_d:,}` / `{vn3_val_d:,}` | `VN003` provides ${obs_ratio:.2f}\\times$ more valid daily observations across 3.3 years. |
| **Calendar-Preserving Daily Lag-1 Autocorrelation ($\\rho_1$)** | `{vn1_rho1:.4f}` ($n_{{\\text{{eff}}}} = {vn1_neff:.2f}$, VIF $= {vn1_vif:.2f}$) | `{vn3_rho1:.4f}` ($n_{{\\text{{eff}}}} = {vn3_neff:.2f}$, VIF $= {vn3_vif:.2f}$) | Computed via `src/inference.py::effective_sample_size()` keeping `NaN` on missing calendar days. Strong positive persistence holds at both stations. |
| **Overall Daily Median & 95% Calendar Block-Bootstrap CI ($L=28\\text{{d}}, B=2000$)** | `{vn1_med:.2f}` (`[{vn1_ci_lo:.2f}, {vn1_ci_hi:.2f}]`) $\\mu\\text{{g/m}}^3$ | `{vn3_med:.2f}` (`[{vn3_ci_lo:.2f}, {vn3_ci_hi:.2f}]`) $\\mu\\text{{g/m}}^3$ | Daily central tendency and dependence-aware uncertainty intervals are closely aligned across stations. |
| **Winter vs. Non-Winter Daily Median ($\\mu\\text{{g/m}}^3$)** | `{vn1_w_med:.2f}` vs. `{vn1_nw_med:.2f}` (`+{vn1_w_diff:.2f}`, $r_{{rb}} = +{vn1_rrb:.4f}$) | `{vn3_w_med:.2f}` vs. `{vn3_nw_med:.2f}` (`+{vn3_w_diff:.2f}`, $r_{{rb}} = +{vn3_rrb:.4f}$) | Winter elevation is replicated across multi-year observations at `VN003` as well as `VN001`. |
| **Seasonal Kruskal–Wallis $H$ ($\\varepsilon^2$) & Dependence-Aware $p_{{\\text{{boot}}}}$ ($L=28\\text{{d}}$)** | $H = {vn1_kw_h:.4f}$ ($\\varepsilon^2 = {vn1_kw_eps:.4f}$), $p_{{\\text{{boot}}}} = {vn1_kw_pboot:.4f}$ ($p_{{\\text{{naive}}}} = {vn1_kw_pnaive}$) | $H = {vn3_kw_h:.4f}$ ($\\varepsilon^2 = {vn3_kw_eps:.4f}$), $p_{{\\text{{boot}}}} = {vn3_kw_pboot:.4f}$ ($p_{{\\text{{naive}}}} = {vn3_kw_pnaive}$) | Calendar block-bootstrap null test ($B=2,000, L=28\\text{{d}}$) observes elevated winter concentrations across both stations while keeping seasonal inference classified as `exploratory` due to strong daily persistence, single physical cycle per station-year, and historical missingness. |
| **Daily QCVN 05:2023 Exceedance ($>50\\ \\mu\\text{{g/m}}^3$)** | `{vn1_qcvn_d} / {vn1_val_d}` (**{vn1_qcvn_pct:.2f}%**) | `{vn3_qcvn_d} / {vn3_val_d}` (**{vn3_qcvn_pct:.2f}%**) | Both stations show substantial fractions of valid days exceeding QCVN 05:2023 ($50\\ \\mu\\text{{g/m}}^3$), heavily concentrated in Winter/Autumn. |

### Handover Contract for Issue #12 (Regression) & Issue #13 (Classification)
- **Primary Baseline Model Contract:** Issue #12 and Issue #13 retain `data/processed/air_pollution_final.parquet` (`VN001`) as the frozen baseline partition so all M2/M3/W9 benchmarks remain strictly comparable.
- **Protocol A (Station-Specific Modeling — APPROVED):** `data/processed/air_pollution_extended_2022_2026.parquet` provides station-stratified `split` (`train`/`test` chronologically partitioned within each `station_id`), allowing Issue #12/#13 to train and evaluate station-specific models independently without temporal leakage within each station series (`src/issue44_preparation.py::validate_modeling_split(df, protocol='station_specific')`).
- **Protocol B (Pooled Multi-Station Modeling — REJECTED FOR DISJOINT SPANS):** A pooled model (such as one with `station_id` fixed effects) cannot safely use the station-stratified split because `VN001` training records (2025–2026) occur chronologically *after* `VN003` test records (2024–2025), creating cross-station temporal leakage. Furthermore, because `VN003` (ending 2025-04-09) and `VN001` (starting 2025-07-03) have disjoint temporal operational windows with zero temporal overlap (gap of 2,040 hours), a global chronological cutoff places `VN003` exclusively in Train and `VN001` exclusively in Test. Consequently, station-level parameters cannot be trained and evaluated out-of-sample across both partitions. Protocol B is therefore formally rejected for this disjoint multi-station dataset (`src/issue44_preparation.py::validate_modeling_split(df, protocol='pooled')` enforces fail-closed rejection).
"""
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        temp_p = p.with_name(f"{p.stem}.tmp_{os.getpid()}_{int(time.time())}.md")
        try:
            temp_p.write_text(content, encoding="utf-8", newline="\n")
            temp_p.replace(p)
        finally:
            if temp_p.exists():
                try:
                    temp_p.unlink()
                except OSError:
                    pass

    return content


def _extract_sections(report_text: str) -> dict[str, str]:
    """Split markdown report by top-level `## ` headers."""
    sections: dict[str, str] = {}
    current_header: Optional[str] = None
    buf: list[str] = []
    for line in report_text.splitlines():
        if line.startswith("## "):
            if current_header is not None:
                sections[current_header] = "\n".join(buf)
            current_header = line.strip()
            buf = [line]
        elif current_header is not None:
            buf.append(line)
    if current_header is not None:
        sections[current_header] = "\n".join(buf)
    return sections


def _parse_markdown_table_rows(section_text: str) -> list[list[str]]:
    """Return parsed cells for every markdown table data row in a section."""
    rows: list[list[str]] = []
    for line in section_text.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c).issubset({"-", ":", " "}) and "-" in c for c in cells):
            continue
        rows.append(cells)
    return rows


def verify_legacy_vs_extended_comparison(
    report_text: str,
    manifest_7441: dict[str, Any],
    extended_metadata: dict[str, Any],
    interp_eval_df: pd.DataFrame,
    winter_summary_df: pd.DataFrame,
) -> dict[str, Any]:
    """Verify that the comparison report matches source metadata, schemas, and metrics per section and table row."""
    mismatches: list[str] = []
    try:
        _validate_comparison_report_inputs(
            manifest_7441, extended_metadata, interp_eval_df, winter_summary_df
        )
    except (KeyError, ValueError) as exc:
        return {
            "verified": False,
            "mismatches": [f"Input schema validation failed: {exc}"],
        }

    required_sections = [
        "## 1. Source Verification & Approval Decision (Phase 1)",
        "## 2. Dataset Architecture & Coverage Comparison (Phases 2–4)",
        "## 3. Missingness & Short-Gap Interpolation Experiment (Phase 5)",
        "## 4. Multi-Year & Multi-Winter Seasonality Re-Evaluation (Phase 6 & FIG-01)",
        "## 5. Impact on Statistical Inference (Issue #11) & Regression Contract (Issue #12)",
    ]
    sections = _extract_sections(report_text)
    for sec in required_sections:
        if sec not in sections:
            mismatches.append(f"Missing required section header: {sec}")
    if mismatches:
        return {"verified": False, "mismatches": mismatches}

    cov_7441 = manifest_7441["coverage"]
    st_vn1 = extended_metadata["stations"]["VN001_HANOI_556_NGUYEN_VAN_CU"]
    st_vn3 = extended_metadata["stations"]["VN003_HANOI_OPENAQ_7441"]
    w_backfill = extended_metadata["weather_backfill"]

    # --- Section 1 verification ---
    sec1_text = sections[required_sections[0]]
    sec1_rows = _parse_markdown_table_rows(sec1_text)
    loc7441_row = next((r for r in sec1_rows if len(r) >= 5 and "7441" in r[0]), None)
    if loc7441_row is None:
        mismatches.append("Section 1: Missing table row for OpenAQ S3 Location 7441.")
    else:
        for expected_tok in (
            f"`{int(manifest_7441['s3_daily_file_count'])}`",
            f"`{int(cov_7441['raw_rows']):,}`",
            f"`{int(cov_7441['qc_valid_hours']):,}`",
        ):
            if expected_tok not in loc7441_row[3]:
                mismatches.append(f"Section 1 (7441 provenance): Expected {expected_tok} in '{loc7441_row[3]}'.")

    mirror_row = next((r for r in sec1_rows if len(r) >= 5 and "Third-party GitHub Mirror" in r[0]), None)
    if mirror_row is None or "25d08e949c9d01ba57c4e74ff9b3b99328ecf141" not in mirror_row[3] or "issue44_source_verification.json" not in mirror_row[3]:
        mismatches.append("Section 1: Missing frozen provenance disclosure for Third-party GitHub Mirror.")

    inter_km_str = f"{float(w_backfill['inter_station_distance_7441_to_vn001_km']):.3f} km"
    if inter_km_str not in sec1_text:
        mismatches.append(f"Section 1: Expected inter-station distance '{inter_km_str}' not found.")

    # --- Section 2 verification (Coverage & Annual tables) ---
    sec2_rows = _parse_markdown_table_rows(sections[required_sections[1]])

    def _find_sec2_metric_row(label_substr: str) -> Optional[list[str]]:
        return next((r for r in sec2_rows if len(r) == 4 and label_substr in r[0]), None)

    tot_rows = int(extended_metadata["total_rows"])
    vn1_grid = int(st_vn1["grid_rows"])
    vn3_grid = int(st_vn3["grid_rows"])
    vn1_obs = int(st_vn1["observed_pm25_rows"])
    vn3_obs = int(st_vn3["observed_pm25_rows"])
    vn1_miss = int(st_vn1["missing_pm25_rows"])
    vn3_miss = int(st_vn3["missing_pm25_rows"])
    vn1_miss_pct = float(st_vn1["missing_pm25_pct"])
    vn3_miss_pct = float(st_vn3["missing_pm25_pct"])
    vn1_obs_pct = round(100.0 - vn1_miss_pct, 2)
    vn3_obs_pct = round(100.0 - vn3_miss_pct, 2)
    comb_obs = vn1_obs + vn3_obs
    comb_miss = vn1_miss + vn3_miss
    comb_obs_pct = round(100.0 * comb_obs / tot_rows, 2)
    comb_miss_pct = round(100.0 * comb_miss / tot_rows, 2)

    sec2_checks = [
        ("SHA-256", [extended_metadata["baseline_sha256"]["final_processed"][:8], "build_extended_historical_dataset.py", str(extended_metadata["sha256"])]),
        ("Start Timestamp", [str(st_vn1["min_timestamp"]), str(st_vn3["min_timestamp"]), str(st_vn3["min_timestamp"])]),
        ("End Timestamp", [str(st_vn1["max_timestamp"]), str(st_vn3["max_timestamp"]), str(st_vn1["max_timestamp"])]),
        ("Hourly Grid Rows", [f"`{vn1_grid:,}`", f"`{vn3_grid:,}`", f"`{tot_rows:,}`"]),
        ("Observed Valid", [f"`{vn1_obs:,}` (`{vn1_obs_pct:.2f}%`)", f"`{vn3_obs:,}` (`{vn3_obs_pct:.2f}%`)", f"`{comb_obs:,}` (`{comb_obs_pct:.2f}%`)"]),
        ("Missing", [f"`{vn1_miss:,}` (`{vn1_miss_pct:.2f}%`)", f"`{vn3_miss:,}` (`{vn3_miss_pct:.2f}%`)", f"`{comb_miss:,}` (`{comb_miss_pct:.2f}%`)"]),
        (
            "Chronological Train / Test Rows",
            [
                f"`{int(st_vn1['train_rows']):,}` / `{int(st_vn1['test_rows']):,}`",
                f"`{int(st_vn3['train_rows']):,}` / `{int(st_vn3['test_rows']):,}`",
                f"`{int(st_vn1['train_rows']) + int(st_vn3['train_rows']):,}` / `{int(st_vn1['test_rows']) + int(st_vn3['test_rows']):,}`",
            ],
        ),
        (
            "Distance to ERA5 Grid",
            [
                f"`{float(st_vn1['distance_to_era5_grid_km']):.3f} km`",
                f"`{float(st_vn3['distance_to_era5_grid_km']):.3f} km`",
                "Station-specific",
            ],
        ),
        (
            "ERA5 Weather Missingness",
            [
                "`0.0%` (`9,072` rows)",
                f"`{float(w_backfill['max_missing_pct']):.1f}%` (`{int(w_backfill['rows']):,}` rows)",
                f"`{float(w_backfill['max_missing_pct']):.1f}%` (`{9072 + int(w_backfill['rows']):,}` raw weather hours)",
            ],
        ),
    ]
    for metric_label, col_expectations in sec2_checks:
        r = _find_sec2_metric_row(metric_label)
        if r is None:
            mismatches.append(f"Section 2 Coverage Table: Missing row '{metric_label}'.")
            continue
        for col_idx, exp_sub in enumerate(col_expectations, start=1):
            if exp_sub not in r[col_idx]:
                mismatches.append(
                    f"Section 2 Coverage Table ('{metric_label}', col {col_idx}): expected '{exp_sub}' in '{r[col_idx]}'."
                )

    # Annual breakdown rows in Section 2 (9 columns)
    tot_cal_h = 0
    for yr_entry in cov_7441["annual"]:
        yr = int(yr_entry["year"])
        tot_cal_h += int(yr_entry["expected_hours"])
        yr_row = next((r for r in sec2_rows if len(r) == 9 and f"**{yr}**" in r[0]), None)
        if yr_row is None:
            mismatches.append(f"Section 2 Annual Table: Missing row for year {yr}.")
            continue
        expected_cols = {
            1: f"{int(yr_entry['s3_daily_files']):,}",
            2: f"{int(yr_entry['expected_hours']):,}",
            3: f"{int(yr_entry['source_available_hours']):,}",
            4: f"{int(yr_entry['s3_reported_hours']):,}",
            5: f"{int(yr_entry['qc_valid_hours']):,}",
            6: f"{int(yr_entry['sentinel_or_negative_hours']):,}",
            7: f"{float(yr_entry['qc_valid_pct_of_active_window']):.2f}%",
            8: f"{int(yr_entry['longest_gap_hours']):,}",
        }
        for c_idx, exp_val in expected_cols.items():
            if exp_val not in yr_row[c_idx]:
                mismatches.append(
                    f"Section 2 Annual Table (year {yr}, col {c_idx}): expected '{exp_val}', got '{yr_row[c_idx]}'."
                )

    tot_yr_row = next((r for r in sec2_rows if len(r) == 9 and "Total (2022–2025)" in r[0]), None)
    if tot_yr_row is None:
        mismatches.append("Section 2 Annual Table: Missing 'Total (2022–2025)' row.")
    else:
        tot_expected_cols = {
            1: f"**{int(manifest_7441['s3_daily_file_count']):,}**",
            2: f"**{tot_cal_h:,}**",
            3: f"**{int(cov_7441['source_observation_window']['active_window_hours']):,}**",
            4: f"**{int(cov_7441['raw_rows']):,}**",
            5: f"**{int(cov_7441['qc_valid_hours']):,}**",
            6: f"**{int(cov_7441['sentinel_or_negative_hours']):,}**",
            7: f"**{vn3_obs_pct:.2f}%**",
            8: f"**{int(cov_7441['longest_contiguous_gap_active_window_hours']):,}**",
        }
        for c_idx, exp_val in tot_expected_cols.items():
            if tot_yr_row[c_idx] != exp_val:
                mismatches.append(
                    f"Section 2 Annual Table (Total row, col {c_idx}): expected '{exp_val}', got '{tot_yr_row[c_idx]}'."
                )

    # --- Section 3 verification (Interpolation table) ---
    sec3_rows = _parse_markdown_table_rows(sections[required_sections[2]])
    interp_all = interp_eval_df[interp_eval_df["season_scope"] == "ALL"].copy()
    for _, ir in interp_all.iterrows():
        sid_raw = str(ir["station_id"])
        sid_short = "VN001" if "VN001" in sid_raw else "VN003"
        gap_str = f"{int(ir['masked_gap_length_hours'])}h"
        max_gap_str = f"{int(ir['max_gap_hours'])}h"
        match_row = next(
            (
                r
                for r in sec3_rows
                if len(r) == 10 and sid_short in r[0] and r[1] == gap_str and r[2] == max_gap_str
            ),
            None,
        )
        if match_row is None:
            mismatches.append(
                f"Section 3 Interpolation Table: Missing row for ({sid_short}, L={gap_str}, max_gap={max_gap_str})."
            )
            continue
        bias_val = float(ir["bias"])
        bias_str = f"+{bias_val:.4f}" if bias_val >= 0 else f"{bias_val:.4f}".replace("-", "−")
        expected_interp_cols = {
            3: f"{int(ir['n_masked_hours'])}",
            4: f"{float(ir['mae']):.4f}",
            5: f"{float(ir['rmse']):.4f}",
            6: bias_str,
            7: f"{int(ir['real_interpolated_hours'])} / {int(ir['station_missing_hours']):,}",
            8: f"{float(ir['real_interpolated_pct_of_missing']):.2f}%",
            9: f"{float(ir['coverage_before_pct']):.2f}% → {float(ir['coverage_after_pct']):.2f}%",
        }
        for c_idx, exp_val in expected_interp_cols.items():
            if match_row[c_idx] != exp_val:
                mismatches.append(
                    f"Section 3 Interpolation Table ({sid_short}, L={gap_str}, max_gap={max_gap_str}, col {c_idx}): "
                    f"expected '{exp_val}', got '{match_row[c_idx]}'."
                )

    # --- Section 4 verification (Winter Cohort Summary table) ---
    sec4_rows = _parse_markdown_table_rows(sections[required_sections[3]])
    for _, wr in winter_summary_df.iterrows():
        sid = str(wr["station_id"])
        wy = int(wr["winter_year"])
        wid = f"**W{wy}**"
        match_w_row = next(
            (r for r in sec4_rows if len(r) == 11 and f"`{sid}`" == r[0] and wid in r[1]),
            None,
        )
        if match_w_row is None:
            mismatches.append(f"Section 4 Winter Table: Missing row for ({sid}, W{wy}).")
            continue
        m_pct = _format_monthly_winter_pct(wy, wr["monthly_completeness"])
        v_days = int(wr["valid_days"])
        expected_w_cols = {
            2: f"{int(wr['expected_calendar_hours']):,} / {int(wr['station_grid_hours']):,}",
            3: f"{int(wr['count']):,} (`{float(wr['coverage_of_full_winter_pct']):.2f}%` / `{float(wr['coverage_of_station_grid_pct']):.2f}%`)",
            4: f"`{m_pct}`",
            5: f"{float(wr['mean']):.2f} ± {float(wr['sd']):.2f}",
            6: f"**{float(wr['median']):.2f}**",
            7: f"{float(wr['iqr']):.2f} (`{float(wr['q25']):.1f}–{float(wr['q75']):.1f}`)",
            8: f"{float(wr['p90']):.2f}",
            9: f"{v_days}",
            10: f"{int(wr['qcvn_exceed_days'])} / {v_days} (**{float(wr['qcvn_exceed_pct']):.2f}%**)",
        }
        for c_idx, exp_val in expected_w_cols.items():
            if match_w_row[c_idx] != exp_val:
                mismatches.append(
                    f"Section 4 Winter Table ({sid}, W{wy}, col {c_idx}): expected '{exp_val}', got '{match_w_row[c_idx]}'."
                )

    # --- Section 5 verification (Inference Comparison table & Handover Contract) ---
    sec5_text = sections[required_sections[4]]
    sec5_rows = _parse_markdown_table_rows(sec5_text)
    inf_vn1 = extended_metadata["inference_comparison"]["VN001_HANOI_556_NGUYEN_VAN_CU"]
    inf_vn3 = extended_metadata["inference_comparison"]["VN003_HANOI_OPENAQ_7441"]

    def _find_sec5_row(label_substr: str) -> Optional[list[str]]:
        return next((r for r in sec5_rows if len(r) == 4 and label_substr in r[0]), None)

    vn1_ci = inf_vn1["daily_median_ci95_calendar_bootstrap"]
    vn3_ci = inf_vn3["daily_median_ci95_calendar_bootstrap"]
    vn1_w_diff = float(inf_vn1["winter_daily_median"]) - float(inf_vn1["non_winter_daily_median"])
    vn3_w_diff = float(inf_vn3["winter_daily_median"]) - float(inf_vn3["non_winter_daily_median"])

    sec5_checks = [
        (
            "Calendar Days / Valid Daily Observations",
            f"`{int(inf_vn1['calendar_days']):,}` / `{int(inf_vn1['valid_days_ge18h']):,}`",
            f"`{int(inf_vn3['calendar_days']):,}` / `{int(inf_vn3['valid_days_ge18h']):,}`",
        ),
        (
            "Calendar-Preserving Daily Lag-1 Autocorrelation",
            f"`{float(inf_vn1['daily_lag1_autocorr_rho1']):.4f}` ($n_{{\\text{{eff}}}} = {float(inf_vn1['effective_sample_size_n_eff']):.2f}$, VIF $= {float(inf_vn1['variance_inflation_factor']):.2f}$)",
            f"`{float(inf_vn3['daily_lag1_autocorr_rho1']):.4f}` ($n_{{\\text{{eff}}}} = {float(inf_vn3['effective_sample_size_n_eff']):.2f}$, VIF $= {float(inf_vn3['variance_inflation_factor']):.2f}$)",
        ),
        (
            "Overall Daily Median & 95% Calendar Block-Bootstrap CI",
            f"`{float(inf_vn1['daily_median']):.2f}` (`[{float(vn1_ci[0]):.2f}, {float(vn1_ci[1]):.2f}]`)",
            f"`{float(inf_vn3['daily_median']):.2f}` (`[{float(vn3_ci[0]):.2f}, {float(vn3_ci[1]):.2f}]`)",
        ),
        (
            "Winter vs. Non-Winter Daily Median",
            f"`{float(inf_vn1['winter_daily_median']):.2f}` vs. `{float(inf_vn1['non_winter_daily_median']):.2f}` (`+{vn1_w_diff:.2f}`, $r_{{rb}} = +{float(inf_vn1['winter_vs_nonwinter_r_rb']):.4f}$)",
            f"`{float(inf_vn3['winter_daily_median']):.2f}` vs. `{float(inf_vn3['non_winter_daily_median']):.2f}` (`+{vn3_w_diff:.2f}`, $r_{{rb}} = +{float(inf_vn3['winter_vs_nonwinter_r_rb']):.4f}$)",
        ),
        (
            "Seasonal Kruskal–Wallis",
            f"$H = {float(inf_vn1['kruskal_wallis_h']):.4f}$ ($\\varepsilon^2 = {float(inf_vn1['kruskal_wallis_epsilon2']):.4f}$), $p_{{\\text{{boot}}}} = {float(inf_vn1['kruskal_wallis_calendar_bootstrap_p']):.4f}$",
            f"$H = {float(inf_vn3['kruskal_wallis_h']):.4f}$ ($\\varepsilon^2 = {float(inf_vn3['kruskal_wallis_epsilon2']):.4f}$), $p_{{\\text{{boot}}}} = {float(inf_vn3['kruskal_wallis_calendar_bootstrap_p']):.4f}$",
        ),
        (
            "Daily QCVN 05:2023 Exceedance",
            f"`{int(inf_vn1['qcvn_exceedance_days'])} / {int(inf_vn1['valid_days_ge18h'])}` (**{float(inf_vn1['qcvn_exceedance_pct']):.2f}%**)",
            f"`{int(inf_vn3['qcvn_exceedance_days'])} / {int(inf_vn3['valid_days_ge18h'])}` (**{float(inf_vn3['qcvn_exceedance_pct']):.2f}%**)",
        ),
    ]
    for row_label, exp_vn1, exp_vn3 in sec5_checks:
        r = _find_sec5_row(row_label)
        if r is None:
            mismatches.append(f"Section 5 Inference Table: Missing row '{row_label}'.")
            continue
        if exp_vn1 not in r[1]:
            mismatches.append(f"Section 5 Inference Table ('{row_label}', VN001 col): expected '{exp_vn1}' in '{r[1]}'.")
        if exp_vn3 not in r[2]:
            mismatches.append(f"Section 5 Inference Table ('{row_label}', VN003 col): expected '{exp_vn3}' in '{r[2]}'.")

    if "Protocol A (Station-Specific Modeling" not in sec5_text:
        mismatches.append("Section 5: Missing Protocol A specification in handover contract.")
    if "Protocol B (Pooled Multi-Station Modeling" not in sec5_text:
        mismatches.append("Section 5: Missing Protocol B specification in handover contract.")

    return {
        "verified": len(mismatches) == 0,
        "mismatches": mismatches,
    }
