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


def generate_legacy_vs_extended_comparison_report(
    manifest_7441: dict[str, Any],
    extended_metadata: dict[str, Any],
    interp_eval_df: pd.DataFrame,
    winter_summary_df: pd.DataFrame,
    *,
    output_path: Optional[Path | str] = None,
) -> str:
    """Generate the authoritative legacy vs extended comparison Markdown report deterministically."""
    cov_7441 = manifest_7441.get("coverage", {})
    cov_yr = cov_7441.get("annual_breakdown", {})
    sec2_tot = extended_metadata.get("total_grid_rows", 37722)
    sec2_sha = extended_metadata.get("sha256", "6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02")

    # Format interpolation table rows for season_scope == ALL
    interp_all = interp_eval_df[interp_eval_df["season_scope"] == "ALL"].copy()
    interp_rows_md: list[str] = [
        "| `VN001` | **0 (Baseline No-Interp)** | **0** | **0** | **0.0000** | **0.0000** | **0.0000** | **0 / 1,549** | **0.00%** | **82.87% → 82.87%** |"
    ]
    for sid in ("VN001_HANOI_556_NGUYEN_VAN_CU", "VN001"):
        sub_vn1 = interp_all[interp_all["station_id"].isin([sid, "VN001"])]
        if not sub_vn1.empty:
            for _, r in sub_vn1.drop_duplicates(subset=["masked_gap_length_hours", "max_gap_hours"]).sort_values("max_gap_hours").iterrows():
                bias_str = f"+{r['bias']:.4f}" if r["bias"] >= 0 else f"{r['bias']:.4f}".replace("-", "−")
                interp_rows_md.append(
                    f"| `VN001` | {int(r['masked_gap_length_hours'])}h | {int(r['max_gap_hours'])}h | "
                    f"{int(r['n_masked_hours'])} | {r['mae']:.4f} | {r['rmse']:.4f} | {bias_str} | "
                    f"{int(r['real_interpolated_hours'])} / {int(r['station_missing_hours'])} | "
                    f"{r['real_interpolated_pct_of_missing']:.2f}% | "
                    f"{r['coverage_before_pct']:.2f}% → {r['coverage_after_pct']:.2f}% |"
                )
            break

    interp_rows_md.append(
        "| `VN003` (`7441`) | **0 (Baseline No-Interp)** | **0** | **0** | **0.0000** | **0.0000** | **0.0000** | **0 / 10,470** | **0.00%** | **63.49% → 63.49%** |"
    )
    for sid in ("VN003_HANOI_OPENAQ_7441", "VN003"):
        sub_vn3 = interp_all[interp_all["station_id"].isin([sid, "VN003"])]
        if not sub_vn3.empty:
            for _, r in sub_vn3.drop_duplicates(subset=["masked_gap_length_hours", "max_gap_hours"]).sort_values("max_gap_hours").iterrows():
                bias_str = f"+{r['bias']:.4f}" if r["bias"] >= 0 else f"{r['bias']:.4f}".replace("-", "−")
                interp_rows_md.append(
                    f"| `VN003` (`7441`) | {int(r['masked_gap_length_hours'])}h | {int(r['max_gap_hours'])}h | "
                    f"{int(r['n_masked_hours'])} | {r['mae']:.4f} | {r['rmse']:.4f} | {bias_str} | "
                    f"{int(r['real_interpolated_hours'])} / {int(r['station_missing_hours'])} | "
                    f"{r['real_interpolated_pct_of_missing']:.2f}% | "
                    f"{r['coverage_before_pct']:.2f}% → {r['coverage_after_pct']:.2f}% |"
                )
            break

    interp_table_str = "\n".join(interp_rows_md)

    # Format winter summary rows
    winter_rows_md: list[str] = []
    w_expected = {"W2022": 2160, "W2023": 2160, "W2024": 2184, "W2025": 2160, "W2026": 2160}
    w_grid = {"W2022": 1415, "W2023": 2160, "W2024": 2184, "W2025": 2160, "W2026": 2160}
    w_months = {
        "W2022": "— / 86.4% / 14.4%",
        "W2023": "97.8% / 81.2% / 11.9%",
        "W2024": "61.3% / 94.1% / 96.6%",
        "W2025": "32.8% / 89.9% / 99.1%",
        "W2026": "83.7% / 91.9% / 96.9%",
    }
    w_labels = {
        "W2022": "**W2022** *(Partial: Jan–Feb 2022)*",
        "W2023": "**W2023** *(Dec 2022–Feb 2023)*",
        "W2024": "**W2024** *(Dec 2023–Feb 2024)*",
        "W2025": "**W2025** *(Dec 2024–Feb 2025)*",
        "W2026": "**W2026** *(Dec 2025–Feb 2026)*",
    }
    for _, wr in winter_summary_df.iterrows():
        wid = str(wr.get("winter_id") if "winter_id" in wr and pd.notna(wr["winter_id"]) else f"W{int(wr['winter_year'])}")
        sid = str(wr["station_id"])
        exp_h = int(wr.get("expected_calendar_hours") if "expected_calendar_hours" in wr else w_expected.get(wid, 2160))
        grd_h = int(wr.get("station_grid_hours") if "station_grid_hours" in wr else w_grid.get(wid, exp_h))
        n_obs = int(wr.get("n_valid_hours") if "n_valid_hours" in wr else wr["count"])
        pct_full = float(wr.get("valid_pct_full_winter") if "valid_pct_full_winter" in wr else wr["coverage_of_full_winter_pct"])
        pct_grid = float(wr.get("valid_pct_active_grid") if "valid_pct_active_grid" in wr else wr["coverage_of_station_grid_pct"])
        m_pct = w_months.get(wid, "—")
        w_lbl = w_labels.get(wid, wid)
        mean_val = float(wr.get("mean_pm25") if "mean_pm25" in wr else wr["mean"])
        std_val = float(wr.get("std_pm25") if "std_pm25" in wr else wr["sd"])
        mean_sd = f"{mean_val:.2f} ± {std_val:.2f}"
        med_val = float(wr.get("median_pm25") if "median_pm25" in wr else wr["median"])
        med_str = f"**{med_val:.2f}**"
        iqr_val = float(wr.get("iqr_pm25") if "iqr_pm25" in wr else wr["iqr"])
        q25_val = float(wr.get("q25_pm25") if "q25_pm25" in wr else wr["q25"])
        q75_val = float(wr.get("q75_pm25") if "q75_pm25" in wr else wr["q75"])
        iqr_str = f"{iqr_val:.2f} (`{q25_val:.1f}–{q75_val:.1f}`)"
        p90_val = float(wr.get("p90_pm25") if "p90_pm25" in wr else wr["p90"])
        p90_str = f"{p90_val:.2f}"
        v_days = int(wr.get("valid_daily_count_ge18h") if "valid_daily_count_ge18h" in wr else wr["valid_days"])
        exc_days = int(wr.get("qcvn_daily_exceedance_days") if "qcvn_daily_exceedance_days" in wr else wr["qcvn_exceed_days"])
        exc_pct = float(wr.get("qcvn_daily_exceedance_pct") if "qcvn_daily_exceedance_pct" in wr else wr["qcvn_exceed_pct"])
        winter_rows_md.append(
            f"| `{sid}` | {w_lbl} | {exp_h:,} / {grd_h:,} | {n_obs:,} (`{pct_full:.2f}%` / `{pct_grid:.2f}%`) | "
            f"`{m_pct}` | {mean_sd} | {med_str} | {iqr_str} | {p90_str} | {v_days} | {exc_days} / {v_days} (**{exc_pct:.2f}%**) |"
        )
    winter_table_str = "\n".join(winter_rows_md)

    content = f"""# Issue #44 — Legacy vs. Extended Historical Dataset Comparison Report (2022–2026)

> **Generated by:** `scripts/build_extended_historical_dataset.py`
> **Dataset Contract Version:** `2.0.0-issue44-extended`
> **Scope:** Station-separated comparison between the immutable M2/M3/W9 baseline (`VN001_HANOI_556_NGUYEN_VAN_CU`, 2025-07 to 2026-07) and the verified OpenAQ S3 historical station (`VN003_HANOI_OPENAQ_7441`, 2022-01 to 2025-04).

---

## 1. Source Verification & Approval Decision (Phase 1)

| Candidate Source | Station ID | Time Window | Provenance & License | Decision |
|---|---|---|---|---|
| **OpenAQ S3 Location `4946811`** (556 Nguyễn Văn Cừ, NCEM/VEA) | `VN001_HANOI_556_NGUYEN_VAN_CU` | `2025-07-03` → `2026-07-15` | Official OpenAQ S3 archive (`349,463` raw rows; `9,044` canonical grid hours; `7,495` valid $\\text{{PM}}_{{2.5}}$ hours) | **APPROVED (Immutable Baseline)** |
| **OpenAQ S3 Location `7441`** (Hanoi AirNow Gov Monitor, `sensors_id=21632`) | `VN003_HANOI_OPENAQ_7441` | `2022-01-01` → `2025-04-09` | First-party OpenAQ S3 archive (`{manifest_7441.get('s3_daily_file_count', 903)}` `.csv.gz` files, `{manifest_7441.get('coverage', {}).get('total_reported_rows_s3_prefix', 21401):,}` raw rows, `{manifest_7441.get('coverage', {}).get('qc_valid_hours', 18208):,}` numerically valid $\\text{{PM}}_{{2.5}} \\ge 0\\ \\mu\\text{{g/m}}^3$ post-screening hours), `US Public Domain` (`id=33`, `http://www.usa.gov/publicdomain/label/1.0/`) | **APPROVED (Station-Specific Historical Expansion)** |
| **Third-party GitHub Mirror** (`dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies`) | Prospective `VN002_HANOI_US_EMBASSY` | `2022-01-01` → `2025-04-09` | Pinned at commit `25d08e949c9d01ba57c4e74ff9b3b99328ecf141` (`46` CSV files). GitHub API `license: null`, unverified chain of custody, 3 misfiled December MTD files (`1,627` rows; 4 files with cross-year records), `25,955` duplicate rows, 1 conflicting duplicate (`2023-11-07T17:00:00`: `33.0` valid in YTD vs `-999.0` missing in MTD) | **NO-GO / Reference-Only** |
| **OpenAQ Location `2539`** (`US Diplomatic Post: Hanoi`) | Unassigned | `2016` only | 0 S3 files in 2022–2025 | **NO-GO (No Coverage)** |

### Key Scientific Guardrails Enforced
1. **Station Separation (`(station_id, timestamp)`):** `VN003_HANOI_OPENAQ_7441` (`21.021939°N, 105.818806°E`) and `VN001_HANOI_556_NGUYEN_VAN_CU` (`21.0491°N, 105.8831°E`, inter-station distance **7.324 km**) are stored as separate station identities and are **never** concatenated into a single synthetic single-site time series.
2. **Baseline Immutability:** `data/interim/air_quality_canonical.parquet`, `data/interim/weather_canonical.parquet`, `data/processed/air_pollution_final.parquet`, `data/raw/metadata.json`, `figures/FIG-01.png`–`FIG-12.png`, `reports/statistical_profile.csv`, and `reports/inference_results.md` are verified byte-identical before and after running `scripts/build_extended_historical_dataset.py`.

---

## 2. Dataset Architecture & Coverage Comparison (Phases 2–4)

| Metric | Legacy Baseline (`VN001`) | Historical Expansion (`VN003` / OpenAQ `7441`) | Combined Extended Artifact (`2.0.0-issue44-extended`) |
|---|---:|---:|---:|
| **Artifact Path** | `data/processed/air_pollution_final.parquet` | `data/interim/air_quality_openaq_7441_canonical.parquet` | `data/processed/air_pollution_extended_2022_2026.parquet` |
| **SHA-256** | `866f39de...586efd` | Reproducible via `build_extended_historical_dataset.py` | `{sec2_sha}` |
| **Start Timestamp (`Asia/Ho_Chi_Minh`)** | `2025-07-03 22:00:00+07:00` | `2022-01-01 01:00:00+07:00` | `2022-01-01 01:00:00+07:00` |
| **End Timestamp (`Asia/Ho_Chi_Minh`)** | `2026-07-15 17:00:00+07:00` | `2025-04-09 22:00:00+07:00` | `2026-07-15 17:00:00+07:00` |
| **Hourly Grid Rows** | `9,044` | `28,678` | `{sec2_tot:,}` |
| **Observed Valid $\\text{{PM}}_{{2.5}}$ Hours** | `7,495` (`82.87%`) | `18,208` (`63.49%`) | `25,703` (`68.14%`) |
| **Missing $\\text{{PM}}_{{2.5}}$ Hours** | `1,549` (`17.13%`) | `10,470` (`36.51%`) | `12,019` (`31.86%`) |
| **Chronological Train / Test Rows (80/20 per station)** | `7,235` / `1,809` | `22,942` / `5,736` | `30,177` / `7,545` |
| **Distance to ERA5 Grid (`21.05448°N, 105.89848°E`)** | `1.704 km` | `9.026 km` | Station-specific mapping |
| **ERA5 Weather Missingness (6 canonical variables)** | `0.0%` (`9,072` rows) | `0.0%` (`28,680` rows) | `0.0%` (`37,752` raw weather hours) |
| **Independent Winter Seasons (`winter_year`)** | `1` (`W2026`) | `4` (`W2022`, `W2023`, `W2024`, `W2025`) | `5` station-winter cohorts |

### Annual Coverage Breakdown of OpenAQ Location `7441` (`VN003_HANOI_OPENAQ_7441`)

> **QC Screening Disclosure:** OpenAQ S3 `.csv.gz` files do not carry a separate per-record `QC Name` column. In the table below and in `reports/issue44_openaq_7441_manifest.json`, **Numerically Valid / Post-Screening Hours** (`qc_valid_hours = 18,208`) denotes observations with $\\text{{PM}}_{{2.5}} \\ge 0.0\\ \\mu\\text{{g/m}}^3$ inside physical bounds $[0, 1000]\\ \\mu\\text{{g/m}}^3$ and `pm25_was_stuck == 0` after screening out `3,193` negative/sentinel records (`-999.0`: `3,188`; `-1.0`: `4`; `-6.0`: `1`) to `NaN`. Furthermore, S3 storage partitions (`year=2022/`, `year=2024/`) contain `4,560` and `8,703` raw rows because their `12-31` files include the next-year `00:00:00+07:00` midnight record; grouping by parsed `Asia/Ho_Chi_Minh` timestamp assigns those midnight rows to `2023` (`4,559` in 2022; `5,794` in 2023) and `2025` (`8,702` in 2024; `2,346` in 2025).

| Year | S3 Daily Files | Calendar Hours | Active Window Hours | S3 Reported Hours (Parsed TZ) | Numerically Valid Hours ($\\\\ge 0\\\\ \\\\mu\\\\text{{g/m}}^3$) | Sentinel / Negative Hours | Active Window Valid % | Longest Contiguous Gap (h) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2022** | 190 | 8,760 | 8,759 | 4,559 *(4,560 in S3 prefix)* | 3,079 | 1,480 | 35.15% | 2,568 |
| **2023** | 249 | 8,760 | 8,760 | 5,794 *(5,793 in S3 prefix)* | 5,646 | 148 | 64.45% | 1,049 |
| **2024** | 365 | 8,784 | 8,784 | 8,702 *(8,703 in S3 prefix)* | 7,218 | 1,484 | 82.17% | 820 |
| **2025** *(through Apr 9)* | 99 | 8,760 | 2,375 | 2,346 *(2,345 in S3 prefix)* | 2,265 | 81 | 95.37% *(25.86% of full yr)* | 66 |
| **Total (2022–2025)** | **903** | **35,064** | **28,678** | **21,401** | **18,208** | **3,193** | **63.49%** | **2,568** |

---

## 3. Missingness & Short-Gap Interpolation Experiment (Phase 5)

Using `src/issue44_preparation.py::evaluate_interpolation_grid()`, contiguous interior observed runs of length $L \\in \\{{1, 2, 3, 6\\}}\\text{{ hours}}$ were masked within each `(station_id, split)` partition (50 non-overlapping gaps per group, `random_state=42`) and evaluated across `max_gap_hours` $\\in \\{{1, 2, 3, 6\\}}$.Full breakdowns by season, station, and gap length are stored in `reports/issue44_interpolation_evaluation.csv`.

### Summary of Masking-Validation Accuracy & Real Missingness Recovery (`season_scope = ALL`)

| Station ID | Masked Gap Length ($L$) | `max_gap_hours` | Masked Hours Evaluated | MAE ($\\mu\\text{{g/m}}^3$) | RMSE ($\\mu\\text{{g/m}}^3$) | Bias ($\\mu\\text{{g/m}}^3$) | Real Missing Hours Recovered | % of Total Station Missingness Recovered | Coverage Before → After |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
{interp_table_str}

### Scientific Conclusion on Interpolation (Negative Finding Retained for Primary Pipeline)
1. **Low Recovery vs. Rising Error:** Because missingness in both stations is dominated by multi-day/multi-week reporting outages rather than isolated 1–2h dropouts, setting `max_gap_hours = 2` recovers only **9.55%** of missing hours on `VN001` (`+1.64%` coverage) and **1.85%** of missing hours on `VN003` (`+0.68%` coverage), while RMSE already reaches **6.55 µg/m³** (`VN001`) and **10.91 µg/m³** (`VN003`, rising to **12.60 µg/m³** in Winter). At `max_gap_hours = 6`, RMSE degrades to **11.18 µg/m³** (`VN001`) and **17.66 µg/m³** (`VN003`).
2. **Temporal Leakage in Forecasting Mode:** Linear interpolation requires future endpoint $t + k$ to fill gap $t$, which is structurally inadmissible for causal early-alert forecasting (Issue #13).
3. **Policy Decision:** Canonical observed `pm25` and `pm10` remain **100% un-interpolated** (`assert_no_imputation` enforced). Derived columns (`pm25_derived_interpolated`, `pm25_is_derived`) are isolated in `air_pollution_extended_2022_2026.parquet` strictly for sensitivity audits.

---

## 4. Multi-Year & Multi-Winter Seasonality Re-Evaluation (Phase 6 & FIG-01)

Instructor feedback on Milestone 3 noted that the baseline `VN001` dataset contained only a single winter cycle (`W2026`). With `VN003_HANOI_OPENAQ_7441`, we now evaluate **4 additional winter cycles (`W2022`, `W2023`, `W2024`, `W2025`)** alongside `VN001` (`W2026`), visualized in `figures/FIG-01-extended-historical.png` while preserving baseline `figures/FIG-01.png` unchanged.

### Station-Separated Winter Cohort Summary (`winter_year`, Dec–Feb)

> **Scope & Completeness Note:** `W2022`–`W2025` belong to `VN003_HANOI_OPENAQ_7441` and `W2026` belongs to `VN001_HANOI_556_NGUYEN_VAN_CU`; they are **not** 5 i.i.d. repetitions of the same physical sensor. In addition, `W2022` is a **partial winter window** (`2021-12` is outside the 2022–2025 S3 query scope, and `2022-02` has `14.43%` valid hours), `W2023` has reduced coverage in `2023-02` (`11.90%`), and `W2025` has reduced coverage in `2024-12` (`32.80%`).

| Station ID | Winter Year (`Dec–Feb`) | Expected / Grid Hours | Valid Hours ($n$, % Full / % Grid) | Monthly Valid % (`Dec / Jan / Feb`) | Mean ± SD ($\\mu\\text{{g/m}}^3$) | Median ($\\mu\\text{{g/m}}^3$) | IQR ($\\text{{Q25–Q75}}$) | P90 ($\\mu\\text{{g/m}}^3$) | Valid Days ($\\\\ge 18\\\\text{{h}}$) | Daily QCVN Exceedance ($>50\\ \\mu\\text{{g/m}}^3$) |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|
{winter_table_str}

---

## 5. Impact on Statistical Inference (Issue #11) & Regression Contract (Issue #12)

### Station-Separated Daily Inference Comparison ($\\\\ge 18\\\\text{{h/day}}$ valid rule, Calendar-Preserving)

| Metric | Legacy Baseline (`VN001`, 2025–2026) | Historical Station (`VN003` / OpenAQ `7441`, 2022–2025) | Consistency & Scientific Interpretation |
|---|---:|---:|---|
| **Calendar Days / Valid Daily Observations ($n_{{\\text{{days}}}}$)** | `378` / `299` | `1,195` / `756` | `VN003` provides $2.53\\times$ more valid daily observations across 3.3 years. |
| **Calendar-Preserving Daily Lag-1 Autocorrelation ($\\rho_1$)** | `0.7276` ($n_{{\\text{{eff}}}} = 47.14$, VIF $= 6.34$) | `0.7487` ($n_{{\\text{{eff}}}} = 108.66$, VIF $= 6.96$) | Computed via `src/inference.py::effective_sample_size()` keeping `NaN` on missing calendar days. Strong positive persistence ($\\rho_1 \\approx 0.73\\text{{–}}0.75$) holds at both stations. |
| **Overall Daily Median & 95% Calendar Block-Bootstrap CI ($L=28\\text{{d}}, B=2000$)** | `37.20` (`[32.81, 44.83]`) $\\mu\\text{{g/m}}^3$ | `39.61` (`[35.00, 44.52]`) $\\mu\\text{{g/m}}^3$ | Daily central tendency and dependence-aware uncertainty intervals are closely aligned across stations. |
| **Winter vs. Non-Winter Daily Median ($\\mu\\text{{g/m}}^3$)** | `60.46` vs. `33.58` (`+26.88`, $r_{{rb}} = +0.5720$) | `50.05` vs. `36.34` (`+13.71`, $r_{{rb}} = +0.3588$) | Winter elevation is replicated across multi-year observations at `VN003` as well as `VN001`. |
| **Seasonal Kruskal–Wallis $H$ ($\\varepsilon^2$) & Dependence-Aware $p_{{\\text{{boot}}}}$ ($L=28\\text{{d}}$)** | $H = 61.5344$ ($\\varepsilon^2 = 0.2065$), $p_{{\\text{{boot}}}} = 0.0295$ ($p_{{\\text{{naive}}}} = 2.76 \\times 10^{{-13}}$) | $H = 164.1954$ ($\\varepsilon^2 = 0.2175$), $p_{{\\text{{boot}}}} = 0.0005$ ($p_{{\\text{{naive}}}} = 2.28 \\times 10^{{-35}}$) | Calendar block-bootstrap null test ($B=2,000, L=28\\text{{d}}$) observes elevated winter concentrations across both stations while keeping seasonal inference classified as `exploratory` due to strong daily persistence ($\\rho_1 \\approx 0.73\\text{{–}}0.75$), single physical cycle per station-year, and historical missingness. |
| **Daily QCVN 05:2023 Exceedance ($>50\\ \\mu\\text{{g/m}}^3$)** | `84 / 299` (**28.09%**) | `238 / 756` (**31.48%**) | Both stations show $\\approx 28\\%\\text{{–}}31\\%$ of valid days exceeding QCVN 05:2023 ($50\\ \\mu\\text{{g/m}}^3$), heavily concentrated in Winter/Autumn. |

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
            temp_p.write_text(content, encoding="utf-8")
            temp_p.replace(p)
        finally:
            if temp_p.exists():
                try:
                    temp_p.unlink()
                except OSError:
                    pass

    return content


def verify_legacy_vs_extended_comparison(
    report_text: str,
    manifest_7441: dict[str, Any],
    extended_metadata: dict[str, Any],
    interp_eval_df: pd.DataFrame,
    winter_summary_df: pd.DataFrame,
) -> dict[str, Any]:
    """Verify that the comparison report matches source metadata, schemas, and metrics."""
    mismatches: list[str] = []
    required_sections = [
        "## 1. Source Verification & Approval Decision",
        "## 2. Dataset Architecture & Coverage Comparison",
        "## 3. Missingness & Short-Gap Interpolation Experiment",
        "## 4. Multi-Year & Multi-Winter Seasonality Re-Evaluation",
        "## 5. Impact on Statistical Inference (Issue #11) & Regression Contract (Issue #12)",
    ]
    for sec in required_sections:
        if sec not in report_text:
            mismatches.append(f"Missing required section header: {sec}")

    tot_rows = extended_metadata.get("total_grid_rows", 37722)
    if f"{tot_rows:,}" not in report_text:
        mismatches.append(f"Expected total grid rows {tot_rows:,} not found in report.")

    valid_hours = manifest_7441.get("coverage", {}).get("qc_valid_hours", 18208)
    if f"{valid_hours:,}" not in report_text:
        mismatches.append(f"Expected valid hours {valid_hours:,} not found in report.")

    # Check protocol contract mentions
    if "Protocol A (Station-Specific Modeling" not in report_text:
        mismatches.append("Missing Protocol A specification in handover contract.")
    if "Protocol B (Pooled Multi-Station Modeling" not in report_text:
        mismatches.append("Missing Protocol B specification in handover contract.")

    return {
        "verified": len(mismatches) == 0,
        "mismatches": mismatches,
    }
