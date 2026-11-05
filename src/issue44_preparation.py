"""Safe, station-aware preparation and evaluation helpers for Issue #44.

These functions never modify canonical observed pollutant columns (`pm25`, `pm10`)
and strictly enforce station and chronological split boundaries.
"""
from __future__ import annotations

import math
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


def assign_station_chronological_split(
    frame: pd.DataFrame,
    train_fraction: float = 0.80,
    *,
    station_column: str = "station_id",
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    """Assign chronological train/test splits independently per station_id."""
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be strictly between 0 and 1")
    required = {station_column, timestamp_column}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    result = frame.copy()
    result["split"] = ""
    for sid, positions in result.groupby(station_column, sort=False).groups.items():
        group = result.loc[positions].sort_values(timestamp_column)
        n = len(group)
        if n < 2:
            raise ValueError(f"Station '{sid}' must have at least 2 rows for chronological split")
        cut_idx = max(1, min(n - 1, int(math.floor(n * train_fraction))))
        train_idx = group.index[:cut_idx]
        test_idx = group.index[cut_idx:]
        result.loc[train_idx, "split"] = "train"
        result.loc[test_idx, "split"] = "test"
        if not (result.loc[train_idx, timestamp_column].max() < result.loc[test_idx, timestamp_column].min()):
            raise AssertionError(f"Chronological split violation for station '{sid}'")
    return result


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
