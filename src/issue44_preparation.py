"""Safe, data-independent preparation helpers for Issue #44 experiments.

These functions never modify canonical observed pollutant columns and do not
produce or report real-data findings.  They make future experiments auditable
once CP0 approves a historical source.
"""
from __future__ import annotations

from typing import Iterable

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
        timestamps = pd.DatetimeIndex(group[timestamp_column])
        if len(timestamps) > 1 and not np.all(np.diff(timestamps.asi8) == 3_600_000_000_000):
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
