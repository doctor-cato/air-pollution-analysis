"""Independent semantic validation for the Issue #50 extended reanalysis.

The committed artifacts are not trusted: every number that can be recomputed
from the pinned Parquet is recomputed here with code that does **not** call the
runner's helpers or the W9 inference engine. Two tiers are reported separately:

* ``structural`` — schemas, identities, Holm family, status semantics, figure
  mapping and frozen-baseline hashes. Runs without ``data/``.
* ``semantic`` — content recomputation from the real dataset (quality,
  profile, daily panel, test statistics, effect sizes, HAC intervals, calendar
  bootstrap p-values/intervals, sensitivity, figure mapping, comparison text).
  Runs only when ``--real-data`` is supplied; otherwise the tier is SKIPPED,
  never PASS.

Bootstrap-derived quantities are stochastic. They are recomputed with an
independent circular calendar-block bootstrap and a different seed, then
compared with a Monte-Carlo tolerance tied to the replicate spread. Every
deterministic quantity (counts, medians, HAC coefficients, effect sizes,
Holm-adjusted p-values) is compared with a tight numerical tolerance.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

try:  # ``src`` is importable from the repository root and from tests.
    from src.data_quality import ATMOSPHERIC_BOUNDS
    from src.flag_evidence import SEASON_DISPLAY_ORDER
except ImportError:  # pragma: no cover - direct script execution
    from data_quality import ATMOSPHERIC_BOUNDS  # type: ignore
    from flag_evidence import SEASON_DISPLAY_ORDER  # type: ignore


CANONICAL_TIMEZONE = "Asia/Ho_Chi_Minh"
MIN_VALID_HOURS = 18
ALPHA = 0.05
N_NULL_BOOTSTRAP = 5_000
N_CI_BOOTSTRAP = 1_000
BLOCK_LENGTH_DAYS = 28
HAC_LAG_DAILY = 28
BOOTSTRAP_SEED = 42
QCVN_24H_LIMIT = 50.0
QCVN_ANNUAL_LIMIT = 25.0
AUDIT_SEED_OFFSET = 1_009

STATIONS: Tuple[str, ...] = (
    "VN001_HANOI_556_NGUYEN_VAN_CU",
    "VN003_HANOI_OPENAQ_7441",
)
TEST_KEYS: Tuple[str, ...] = (
    "season_effect",
    "weekday_effect",
    "qcvn_24h",
    "qcvn_annual",
)
PERIOD_TYPES: Tuple[str, ...] = (
    "station",
    "year",
    "month",
    "winter_year",
    "season_year",
)
PROFILE_VARIABLES: Tuple[str, ...] = (
    "pm25",
    "pm10",
    "temperature",
    "relative_humidity",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "surface_pressure",
)
SEASON_BY_MONTH: Dict[int, str] = {
    12: "Dong", 1: "Dong", 2: "Dong",
    3: "Xuan", 4: "Xuan", 5: "Xuan",
    6: "He", 7: "He", 8: "He",
    9: "Thu", 10: "Thu", 11: "Thu",
}
SEASON_MONTH_START = {
    "Winter (Dec-Feb)": 12,
    "Spring (Mar-May)": 3,
    "Summer (Jun-Aug)": 6,
    "Autumn (Sep-Nov)": 9,
}
DISPLAY_DECISIONS = {"REUSE", "EXTEND", "NOT NEEDED"}


class ReanalysisValidationError(AssertionError):
    """Raised when an artifact contradicts independently recomputed content."""

    def __init__(self, tier: str, failures: Sequence[str], checks: int):
        self.tier = tier
        self.failures = list(failures)
        self.checks = int(checks)
        head = "; ".join(self.failures[:8])
        more = f" (+{len(self.failures) - 8} more)" if len(self.failures) > 8 else ""
        super().__init__(f"{tier} validation failed ({len(self.failures)}/{checks}): {head}{more}")


class ReanalysisValidationSkipped(RuntimeError):
    """Raised when ``--real-data`` validation is requested without ``data/``."""


@dataclass
class ValidationSuite:
    """Collects field-level failures instead of stopping at the first one."""

    tier: str
    checks: int = 0
    failures: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def _record(self) -> None:
        self.checks += 1

    def fail(self, path: str, detail: str) -> None:
        self._record()
        if len(self.failures) < 200:
            self.failures.append(f"{path}: {detail}")

    def true(self, path: str, condition: Any, detail: str = "") -> None:
        self._record()
        if not bool(condition):
            self.failures.append(f"{path}: {detail or 'condition is false'}")

    def equal(self, path: str, reported: Any, expected: Any, *, context: str = "") -> None:
        self._record()
        if isinstance(reported, (float, np.floating)) and isinstance(expected, (float, np.floating)):
            same = (math.isnan(reported) and math.isnan(expected)) or reported == expected
        else:
            same = reported == expected
        if not same:
            self.failures.append(
                f"{path}: reported {reported!r} != recomputed {expected!r}"
                + (f" ({context})" if context else "")
            )

    def close(
        self,
        path: str,
        reported: Any,
        expected: Any,
        *,
        rtol: float = 1e-9,
        atol: float = 1e-9,
        context: str = "",
    ) -> None:
        self._record()
        try:
            reported_f = float(reported)
            expected_f = float(expected)
        except (TypeError, ValueError):
            self.failures.append(f"{path}: non-numeric reported {reported!r} vs {expected!r}")
            return
        if math.isnan(reported_f) and math.isnan(expected_f):
            return
        if not np.isclose(reported_f, expected_f, rtol=rtol, atol=atol):
            self.failures.append(
                f"{path}: reported {reported_f:.12g} != recomputed {expected_f:.12g}"
                + (f" ({context})" if context else "")
            )

    def finish(self) -> None:
        if self.failures:
            raise ReanalysisValidationError(self.tier, self.failures, self.checks)


# ---------------------------------------------------------------------------
# Independent daily aggregation and calendar
# ---------------------------------------------------------------------------


def _sort_station(part: pd.DataFrame) -> pd.DataFrame:
    return part.sort_values("timestamp").reset_index(drop=True)


def _daily_grid(part: pd.DataFrame) -> Dict[str, Any]:
    """One row per calendar day between the first and last observed day."""
    work = part[["timestamp", "pm25"]].copy()
    work["_date"] = work["timestamp"].dt.normalize()
    observed = work.dropna(subset=["pm25"])
    if observed.empty:
        raise ValueError("No observed PM2.5 values")
    per_day = observed.groupby("_date")["pm25"].agg(
        valid_hours="size", pm25_mean="mean", pm25_median="median"
    )
    per_day = per_day.sort_index()
    calendar = pd.date_range(per_day.index.min(), per_day.index.max(), freq="D")
    per_day = per_day.reindex(calendar)
    valid = per_day["valid_hours"].fillna(0).to_numpy(dtype=int)
    values = per_day["pm25_mean"].to_numpy(dtype=float, copy=True)
    values[valid < MIN_VALID_HOURS] = np.nan
    month = np.asarray(calendar.month, dtype=int)
    seasons = np.array([SEASON_BY_MONTH[int(m)] for m in month], dtype=object)
    weekend = (np.asarray(calendar.dayofweek, dtype=int) >= 5).astype(int)
    return {
        "calendar": calendar,
        "dates": np.asarray(calendar, dtype="datetime64[D]"),
        "valid_hours": valid,
        "values": values,
        "seasons": seasons,
        "weekend": weekend,
        "per_day": per_day,
    }


def independent_daily_panel(part: pd.DataFrame) -> pd.DataFrame:
    grid = _daily_grid(part)
    keep = grid["valid_hours"] >= MIN_VALID_HOURS
    panel = pd.DataFrame({
        "date": grid["calendar"][keep],
        "pm25_mean": grid["values"][keep],
        "season": grid["seasons"][keep],
        "is_weekend": grid["weekend"][keep],
    })
    return panel.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Quality / profile recomputation
# ---------------------------------------------------------------------------


def _period_groups(part: pd.DataFrame) -> Iterable[Tuple[str, str, pd.DataFrame, pd.Timestamp, pd.Timestamp]]:
    ts = part["timestamp"]
    tz = ts.dt.tz
    yield "station", "all", part, ts.min(), ts.max() + pd.Timedelta(hours=1)
    for year in sorted(ts.dt.year.unique()):
        start = pd.Timestamp(year=int(year), month=1, day=1, tz=tz)
        end = pd.Timestamp(year=int(year) + 1, month=1, day=1, tz=tz)
        yield "year", str(year), part.loc[(ts >= start) & (ts < end)], start, end
    for month in sorted(ts.dt.strftime("%Y-%m").unique()):
        start = pd.Timestamp(f"{month}-01", tz=tz)
        end = start + pd.DateOffset(months=1)
        yield "month", str(month), part.loc[(ts >= start) & (ts < end)], start, end
    years = sorted(set(ts.dt.year) | {int(ts.dt.year.max()) + 1})
    for year in years:
        for name, month in SEASON_MONTH_START.items():
            start_year = year - 1 if month == 12 else year
            start = pd.Timestamp(year=start_year, month=month, day=1, tz=tz)
            end = start + pd.DateOffset(months=3)
            scoped = part.loc[(ts >= start) & (ts < end)]
            if not scoped.empty:
                kind = "winter_year" if month == 12 else "season_year"
                yield kind, f"{name}:{year}", scoped, start, end


def _missing_runs(part: pd.DataFrame) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for station, group in part.groupby("station_id"):
        group = _sort_station(group)
        missing = group["pm25"].isna().to_numpy()
        changes = np.r_[True, missing[1:] != missing[:-1]]
        ids = np.cumsum(changes)
        for _, run in group.loc[missing].groupby(ids[missing]):
            records.append({
                "station_id": station,
                "start": str(run["timestamp"].iloc[0]),
                "end": str(run["timestamp"].iloc[-1]),
                "gap_hours": int(len(run)),
                "year": int(run["timestamp"].iloc[0].year),
            })
    return pd.DataFrame(records)


def _group_quality(group: pd.DataFrame, expected: int, outside: int) -> Dict[str, Any]:
    active = int(len(group))
    keys = ["station_id", "timestamp"]
    duplicates = int(group.duplicated(keys).sum()) if set(keys) <= set(group.columns) else 0
    ts = group["timestamp"]
    timezone_ok = bool(
        isinstance(ts.dtype, pd.DatetimeTZDtype)
        and str(ts.dt.tz) == CANONICAL_TIMEZONE
        and not ts.isna().any()
    )
    order_ok = bool(ts.is_monotonic_increasing)
    diffs = ts.diff().dropna()
    irregular = int((diffs != pd.Timedelta(hours=1)).sum()) if len(diffs) else 0
    numeric = pd.to_numeric(group["pm25"], errors="coerce")
    observed_mask = numeric.notna()
    finite_mask = pd.Series(
        np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan)), index=numeric.index
    )
    in_bounds = numeric.between(0.0, 1000.0)
    valid = int((observed_mask & finite_mask & in_bounds).sum())
    observed = int(observed_mask.sum())
    nonfinite = int((observed_mask & ~finite_mask).sum())
    out_of_bounds = int((observed_mask & finite_mask & ~in_bounds).sum())
    negative = int((observed_mask & (numeric < 0)).sum())
    other_bounds = 0
    for column, limits in ATMOSPHERIC_BOUNDS.items():
        if column in group:
            values = pd.to_numeric(group[column], errors="coerce").dropna()
            other_bounds += int(((values < limits["min"]) | (values > limits["max"])).sum())
    derived = (
        int(group["pm25_is_derived"].fillna(False).astype(bool).sum())
        if "pm25_is_derived" in group.columns else None
    )
    return {
        "active_grid_hours": active,
        "observed_pm25_hours": observed,
        "valid_pm25_hours": valid,
        "missing_observed_hours": active - valid,
        "duplicate_keys": duplicates,
        "nonfinite_pm25_values": nonfinite,
        "out_of_bounds_pm25_values": out_of_bounds,
        "negative_sentinel_values": negative,
        "other_bound_violations": other_bounds,
        "derived_pm25_hours": derived,
        "timestamp_order_ok": order_ok,
        "timezone_consistent": timezone_ok,
        "irregular_sampling_intervals": irregular,
        "partial_calendar_period": bool(outside > 0),
    }


def recompute_quality(data: pd.DataFrame, raw_vn003: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Recompute the extended quality table row by row."""
    raw = None
    if raw_vn003 is not None:
        raw = raw_vn003.copy()
        raw["timestamp"] = (
            pd.to_datetime(raw["datetime"], utc=True)
            .dt.tz_convert(CANONICAL_TIMEZONE)
            .dt.floor("h")
        )
        raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    rows: List[Dict[str, Any]] = []
    for station, part in data.groupby("station_id"):
        part = _sort_station(part)
        for kind, key, group, start, end in _period_groups(part):
            expected = int((end - start) / pd.Timedelta(hours=1))
            active = int(len(group))
            outside = expected - active
            valid = int(group["pm25"].notna().sum())
            runs = _missing_runs(group)
            sizes = runs["gap_hours"] if not runs.empty else pd.Series(dtype=int)
            raw_n = invalid_n = missing_source = None
            if raw is not None and station.endswith("7441"):
                scope = raw.loc[(raw["timestamp"] >= start) & (raw["timestamp"] < end)]
                raw_n = int(len(scope))
                missing_source = active - int(scope["timestamp"].drop_duplicates().isin(group["timestamp"]).sum())
                invalid_n = int(
                    (scope["value"].lt(0) | scope["value"].gt(1000) | scope["value"].isna()).sum()
                )
            row = {
                "station_id": station,
                "period_type": kind,
                "period": key,
                "period_start": str(start),
                "period_end_exclusive": str(end),
                "expected_calendar_hours": expected,
                "active_grid_hours": active,
                "available_raw_observations": raw_n,
                "missing_source_rows": missing_source,
                "invalid_source_rows": invalid_n,
                "valid_pm25_observations": valid,
                "invalid_raw_observations": invalid_n,
                "missing_active_hours": active - valid,
                "outside_active_window_hours": outside,
                "missing_pct_active": 100.0 * (active - valid) / active if active else np.nan,
                "coverage_pct_calendar": 100.0 * valid / expected if expected else np.nan,
                "coverage_pct_active": 100.0 * valid / active if active else np.nan,
                "gap_count": int(len(sizes)),
                "longest_missing_gap_hours": int(sizes.max()) if len(sizes) else 0,
                "median_gap_hours": float(sizes.median()) if len(sizes) else 0.0,
                "sample_size_denominator": expected,
            }
            row.update(_group_quality(group, expected, outside))
            rows.append(row)
    return pd.DataFrame(rows)


def recompute_profile(data: pd.DataFrame) -> pd.DataFrame:
    """Recompute descriptive statistics for every cohort and variable."""
    rows: List[Dict[str, Any]] = []
    for station, part in data.groupby("station_id"):
        part = _sort_station(part)
        for kind, key, group, _start, _end in _period_groups(part):
            expected = int((_end - _start) / pd.Timedelta(hours=1))
            active = int(len(group))
            for variable in PROFILE_VARIABLES:
                if variable not in group.columns:
                    continue
                values = group[variable].dropna().astype(float)
                row = {
                    "station_id": station, "period_type": kind, "period": key,
                    "variable": variable,
                    "grid_count": active, "valid_count": int(len(values)),
                    "missing_count": active - int(len(values)),
                    "coverage_pct_active": 100.0 * len(values) / active if active else np.nan,
                    "coverage_pct_calendar": 100.0 * len(values) / expected if expected else np.nan,
                    "missing_pct_active": 100.0 * (active - len(values)) / active if active else np.nan,
                }
                if len(values):
                    row.update(
                        mean=float(values.mean()), median=float(values.median()),
                        variance=float(values.var()) if len(values) > 1 else np.nan,
                        sd=float(values.std()) if len(values) > 1 else np.nan,
                        min=float(values.min()), max=float(values.max()),
                        q25=float(values.quantile(0.25)), q75=float(values.quantile(0.75)),
                        iqr=float(values.quantile(0.75) - values.quantile(0.25)),
                        p90=float(values.quantile(0.90)), p95=float(values.quantile(0.95)),
                        skewness=float(stats.skew(values, bias=False)) if len(values) > 2 else np.nan,
                        excess_kurtosis=float(stats.kurtosis(values, bias=False)) if len(values) > 3 else np.nan,
                    )
                    if variable == "wind_direction":
                        row["circular_mean_degrees"] = float(stats.circmean(values, high=360, low=0))
                        row["circular_sd_degrees"] = float(stats.circstd(values, high=360, low=0))
                rows.append(row)
        hours = part["timestamp"].dt.hour
        for hour in range(24):
            group = part.loc[hours == hour]
            values = group["pm25"].dropna()
            rows.append({
                "station_id": station, "period_type": "hour", "period": str(hour),
                "variable": "pm25", "grid_count": len(group), "valid_count": int(len(values)),
                "missing_count": len(group) - len(values),
                "coverage_pct_active": 100.0 * len(values) / len(group),
                "coverage_pct_calendar": np.nan,
                "missing_pct_active": 100.0 * (len(group) - len(values)) / len(group),
                "mean": float(values.mean()), "median": float(values.median()),
                "variance": float(values.var()), "sd": float(values.std()),
                "min": float(values.min()), "max": float(values.max()),
                "q25": float(values.quantile(0.25)), "q75": float(values.quantile(0.75)),
                "iqr": float(values.quantile(0.75) - values.quantile(0.25)),
                "p90": float(values.quantile(0.90)), "p95": float(values.quantile(0.95)),
                "skewness": float(stats.skew(values, bias=False)),
                "excess_kurtosis": float(stats.kurtosis(values, bias=False)),
            })
        weekdays = part["timestamp"].dt.day_of_week
        for day in range(7):
            group = part.loc[weekdays == day]
            values = group["pm25"].dropna()
            rows.append({
                "station_id": station, "period_type": "weekday", "period": str(day),
                "variable": "pm25", "grid_count": len(group), "valid_count": int(len(values)),
                "missing_count": len(group) - len(values),
                "coverage_pct_active": 100.0 * len(values) / len(group),
                "coverage_pct_calendar": np.nan,
                "missing_pct_active": 100.0 * (len(group) - len(values)) / len(group),
                "mean": float(values.mean()), "median": float(values.median()),
                "variance": float(values.var()), "sd": float(values.std()),
                "min": float(values.min()), "max": float(values.max()),
                "q25": float(values.quantile(0.25)), "q75": float(values.quantile(0.75)),
                "iqr": float(values.quantile(0.75) - values.quantile(0.25)),
                "p90": float(values.quantile(0.90)), "p95": float(values.quantile(0.95)),
                "skewness": float(stats.skew(values, bias=False)),
                "excess_kurtosis": float(stats.kurtosis(values, bias=False)),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# HAC / test statistics
# ---------------------------------------------------------------------------


def _newey_west(X: np.ndarray, residuals: np.ndarray, lag: int) -> np.ndarray:
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((k, k), dtype=float)
    for i in range(n):
        xi = X[i][:, None]
        meat += residuals[i] ** 2 * (xi @ xi.T)
    for step in range(1, lag + 1):
        weight = 1.0 - step / (lag + 1.0)
        cross = np.zeros((k, k), dtype=float)
        for i in range(step, n):
            cross += (
                residuals[i] * residuals[i - step]
                * (X[i][:, None] @ X[i - step][None, :])
            )
        meat += weight * (cross + cross.T)
    cov = xtx_inv @ meat @ xtx_inv
    return cov * n / (n - k)


def _ols_hac(y: np.ndarray, X: np.ndarray, lag: int) -> Dict[str, Any]:
    beta = np.linalg.pinv(X.T @ X) @ X.T @ y
    resid = y - X @ beta
    cov = _newey_west(X, resid, lag)
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    df = len(y) - X.shape[1]
    with np.errstate(divide="ignore", invalid="ignore"):
        t_values = np.where(se > 0, beta / se, np.nan)
    return {
        "beta": beta, "se": se, "cov": cov, "df": df, "t": t_values,
        "p": 2.0 * stats.t.sf(np.abs(t_values), df),
    }


def _time_index(panel: pd.DataFrame) -> np.ndarray:
    dates = pd.to_datetime(panel["date"])
    return (dates - dates.min()).dt.days.to_numpy(dtype=float) / 30.0


def _design_weekend(panel: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    t = _time_index(panel)
    return np.column_stack([
        np.ones(t.size), t, panel["is_weekend"].to_numpy(dtype=float)
    ]), ["intercept", "trend", "weekend"]


def _design_season(panel: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    t = _time_index(panel)
    columns = [np.ones(t.size), t]
    names = ["intercept", "trend"]
    seasons = panel["season"].to_numpy()
    for season in SEASON_DISPLAY_ORDER[1:]:
        columns.append((seasons == season).astype(float))
        names.append(season)
    return np.column_stack(columns), names


def _season_groups(panel: pd.DataFrame) -> Dict[str, np.ndarray]:
    return {
        season: panel.loc[panel["season"] == season, "pm25_mean"].to_numpy(dtype=float)
        for season in SEASON_DISPLAY_ORDER
        if (panel["season"] == season).any()
    }


def _recompute_test_statistics(part: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    panel = independent_daily_panel(part)
    values = panel["pm25_mean"].to_numpy(dtype=float)
    groups = _season_groups(panel)
    if len(groups) >= 2:
        kw = stats.kruskal(*groups.values())
        h_stat, h_p = float(kw.statistic), float(kw.pvalue)
        epsilon = float(min(max(h_stat / (values.size - 1), 0.0), 1.0))
        dong = groups[SEASON_DISPLAY_ORDER[0]]
        he = groups[SEASON_DISPLAY_ORDER[2]]
        season_secondary = float(np.median(dong) - np.median(he))
        season_effect = epsilon
    else:
        h_stat = h_p = epsilon = season_secondary = float("nan")
        season_effect = float("nan")

    X, names = _design_weekend(panel)
    model = _ols_hac(values, X, HAC_LAG_DAILY)
    weekend_index = names.index("weekend")
    weekend_beta = float(model["beta"][weekend_index])
    weekday_mask = panel["is_weekend"].to_numpy(dtype=int) == 0
    weekend_mask = ~weekday_mask
    mw = stats.mannwhitneyu(values[weekday_mask], values[weekend_mask], alternative="two-sided")
    mw_p = float(mw.pvalue)
    rrb = float(2.0 * mw.statistic / (weekday_mask.sum() * weekend_mask.sum()) - 1.0)
    weekday_secondary = float(np.median(values[weekday_mask]) - np.median(values[weekend_mask]))
    t_crit = float(stats.t.ppf(0.975, model["df"]))
    location_crit = float(stats.t.ppf(0.975, values.size - 1))

    share = (values > QCVN_24H_LIMIT).astype(float)
    share_model = _ols_hac(share, np.ones((values.size, 1)), HAC_LAG_DAILY)
    share_beta = float(share_model["beta"][0])
    share_se = float(share_model["se"][0])
    share_t = (share_beta - 0.5) / share_se
    share_p = float(2.0 * stats.t.sf(abs(share_t), values.size - 1))
    share_ci = (
        share_beta - location_crit * share_se, share_beta + location_crit * share_se,
    )
    deviations = values - QCVN_24H_LIMIT
    ranks = stats.rankdata(np.abs(deviations))
    w_plus = float(ranks[deviations > 0].sum())
    w_minus = float(ranks[deviations < 0].sum())
    rrb_pairs = (w_plus - w_minus) / (w_plus + w_minus) if (w_plus + w_minus) else float("nan")
    wilcoxon_p = float(
        stats.wilcoxon(deviations, alternative="two-sided", zero_method="wilcox", correction=False).pvalue
    )

    mean = float(values.mean())
    mean_sd = float(values.std(ddof=1))
    annual_model = _ols_hac(values, np.ones((values.size, 1)), HAC_LAG_DAILY)
    annual_beta = float(annual_model["beta"][0])
    annual_se = float(annual_model["se"][0])
    annual_t = (annual_beta - QCVN_ANNUAL_LIMIT) / annual_se
    annual_p = float(2.0 * stats.t.sf(abs(annual_t), values.size - 1))
    annual_ci = (
        annual_beta - location_crit * annual_se, annual_beta + location_crit * annual_se,
    )
    ttest_p = float(stats.ttest_1samp(values, popmean=QCVN_ANNUAL_LIMIT).pvalue)
    cohen_d = (mean - QCVN_ANNUAL_LIMIT) / mean_sd

    return {
        "panel": panel,
        "season_effect": {
            "statistic": h_stat, "p_independence": h_p,
            "effect_size": season_effect, "secondary_estimate": season_secondary,
            "n": int(values.size),
        },
        "weekday_effect": {
            "statistic": float(model["t"][weekend_index]),
            "p_independence": mw_p,
            "estimate": weekend_beta,
            "se": float(model["se"][weekend_index]),
            "ci": (weekend_beta - t_crit * float(model["se"][weekend_index]),
                   weekend_beta + t_crit * float(model["se"][weekend_index])),
            "secondary_estimate": weekday_secondary,
            "secondary_effect": rrb,
            "n": int(values.size),
        },
        "qcvn_24h": {
            "statistic": share_t, "p_independence": wilcoxon_p,
            "estimate": share_beta, "se": share_se, "ci": share_ci,
            "effect_size": share_beta - 0.5,
            "secondary_estimate": float(np.median(values)),
            "secondary_effect": rrb_pairs, "n": int(values.size),
        },
        "qcvn_annual": {
            "statistic": annual_t, "p_independence": ttest_p,
            "estimate": mean, "se": annual_se, "ci": annual_ci,
            "effect_size": cohen_d,
            "secondary_estimate": float(np.median(values)), "n": int(values.size),
        },
    }


# ---------------------------------------------------------------------------
# Independent calendar bootstrap
# ---------------------------------------------------------------------------


def _circular_indices(n: int, block: int, n_bootstrap: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_blocks = int(math.ceil(n / block))
    starts = rng.integers(0, n, size=(n_bootstrap, n_blocks))
    offsets = np.arange(block)
    index = (starts[:, :, None] + offsets[None, None, :]) % n
    return index.reshape(n_bootstrap, n_blocks * block)[:, :n]


def _row_ranks(matrix: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return np.asarray(stats.rankdata(matrix, axis=1, nan_policy="omit"), dtype=float)


def _kw_rows(values: np.ndarray, labels: np.ndarray) -> np.ndarray:
    ranks = _row_ranks(values)
    observed = np.isfinite(values)
    n_total = observed.sum(axis=1)
    masks = [labels == code for code in range(len(SEASON_DISPLAY_ORDER))]
    rank_sums = np.vstack([np.nansum(np.where(m, ranks, 0.0), axis=1) for m in masks])
    sizes = np.vstack([(m & observed).sum(axis=1) for m in masks]).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = (
            12.0 / (n_total * (n_total + 1.0))
            * (rank_sums ** 2 / sizes).sum(axis=0)
            - 3.0 * (n_total + 1.0)
        )
    valid = (n_total > 1) & (sizes > 0).all(axis=0)
    return np.where(valid, h, np.nan)


def _mw_rows(values: np.ndarray, labels: np.ndarray) -> np.ndarray:
    ranks = _row_ranks(values)
    observed = np.isfinite(values)
    mask_a = labels == 0
    n_a = (mask_a & observed).sum(axis=1)
    rank_sum = np.nansum(np.where(mask_a, ranks, 0.0), axis=1)
    return rank_sum - n_a * (n_a + 1) / 2.0


def _signed_rank_rows(deviations: np.ndarray) -> np.ndarray:
    ranks = _row_ranks(np.abs(deviations))
    return np.nansum(np.where(deviations > 0, ranks, 0.0), axis=1)


def _null_bootstrap_p(
    grid: Dict[str, Any],
    *,
    statistic: str,
    observed: float,
    alternative: str,
    block: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, float]:
    values = grid["values"]
    if statistic == "season":
        labels = np.array(
            [SEASON_DISPLAY_ORDER.index(s) for s in grid["seasons"]], dtype=int
        )
        stat_fn = _kw_rows
    elif statistic == "weekday":
        labels = grid["weekend"].astype(int)
        stat_fn = _mw_rows
    elif statistic == "share":
        labels = grid["weekend"].astype(int)
        stat_fn = _mw_rows
    else:
        raise ValueError(f"Unknown statistic: {statistic}")
    index = _circular_indices(values.size, block, n_bootstrap, seed)
    replicate_values = values[index]
    replicate_labels = np.broadcast_to(labels, replicate_values.shape)
    replicates = np.asarray(stat_fn(replicate_values, replicate_labels), dtype=float)
    replicates = replicates[np.isfinite(replicates)]
    if replicates.size == 0:
        return {"p_value": float("nan"), "replicates_sd": float("nan")}
    p_greater = (1 + int((replicates >= observed).sum())) / (n_bootstrap + 1)
    p_less = (1 + int((replicates <= observed).sum())) / (n_bootstrap + 1)
    if alternative == "greater":
        p_value = p_greater
    elif alternative == "less":
        p_value = p_less
    else:
        p_value = min(1.0, 2.0 * min(p_greater, p_less))
    return {
        "p_value": float(p_value),
        "replicates_sd": float(replicates.std(ddof=1)) if replicates.size > 1 else float("nan"),
        "n_extreme": int(max((replicates >= observed).sum(), (replicates <= observed).sum())),
        "n_bootstrap": int(n_bootstrap),
    }


def _signed_rank_null_p(
    grid: Dict[str, Any], mu: float, *,
    block: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, float]:
    values = grid["values"]
    observed_days = np.isfinite(values)
    centre = float(np.nanmedian(values))
    observed = float(
        stats.wilcoxon(
            values[observed_days] - mu, alternative="two-sided",
            zero_method="wilcox", correction=False,
        ).statistic
    )
    noise = values - centre
    index = _circular_indices(values.size, block, n_bootstrap, seed)
    replicates = _signed_rank_rows(noise[index])
    replicates = replicates[np.isfinite(replicates)]
    p_greater = (1 + int((replicates >= observed).sum())) / (n_bootstrap + 1)
    p_less = (1 + int((replicates <= observed).sum())) / (n_bootstrap + 1)
    return {
        "p_value": float(min(1.0, 2.0 * min(p_greater, p_less))),
        "replicates_sd": float(replicates.std(ddof=1)) if replicates.size > 1 else float("nan"),
        "n_bootstrap": int(n_bootstrap),
    }


def _percentile_interval(replicates: np.ndarray) -> Tuple[float, float]:
    lo, hi = np.percentile(replicates, [2.5, 97.5])
    return float(lo), float(hi)


def _group_replicates(
    values: np.ndarray, *, mask: np.ndarray, block: int, n_bootstrap: int, seed: int,
) -> np.ndarray:
    """Resample within each contiguous group footprint, never across a calendar gap."""
    if len(values) != len(mask):
        raise ValueError("group mask must span the complete daily calendar")
    positions = np.flatnonzero(mask)
    n_target = int(np.isfinite(values[positions]).sum())
    if not n_target:
        raise ValueError("group has no observed day")
    boundaries = np.r_[0, np.flatnonzero(np.diff(positions) > 1) + 1, len(positions)]
    windows, weights = [], []
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        segment = positions[start:end]
        width = min(block, len(segment))
        candidates = [
            values[segment[i:i + width]][np.isfinite(values[segment[i:i + width]])]
            for i in range(len(segment) - width + 1)
        ]
        candidates = [sample for sample in candidates if len(sample)]
        n_segment = int(np.isfinite(values[segment]).sum())
        if candidates:
            windows.append(candidates)
            weights.append(n_segment / np.mean([len(sample) for sample in candidates]))
    if not windows:
        raise ValueError("no segment contains observed days")
    rng = np.random.default_rng(seed)
    probabilities = np.asarray(weights, dtype=float) / sum(weights)
    copies = np.empty((n_bootstrap, n_target), dtype=float)
    for b in range(n_bootstrap):
        offset = 0
        while offset < n_target:
            segment = int(rng.choice(len(windows), p=probabilities))
            candidates = windows[segment]
            sample = candidates[int(rng.integers(len(candidates)))]
            count = min(len(sample), n_target - offset)
            copies[b, offset:offset + count] = sample[:count]
            offset += count
    return copies


def _contrast_ci(
    grid: Dict[str, Any], mask_a: np.ndarray, mask_b: np.ndarray,
    *, statistic: str, block: int, n_bootstrap: int, seed: int,
) -> Dict[str, Any]:
    values = grid["values"]
    observed = np.isfinite(values)
    a = values[mask_a & observed]
    b = values[mask_b & observed]
    reducer = np.median if statistic == "median" else np.mean
    point = float(reducer(a) - reducer(b))
    rep_a = reducer(_group_replicates(
        values, mask=mask_a, block=block, n_bootstrap=n_bootstrap, seed=seed,
    ), axis=1)
    rep_b = reducer(_group_replicates(
        values, mask=mask_b, block=block, n_bootstrap=n_bootstrap, seed=seed + 1,
    ), axis=1)
    reps = rep_a - rep_b
    lo, hi = _percentile_interval(reps)
    if not (lo <= point <= hi):
        half = float(np.quantile(np.abs(reps - point), 0.95))
        lo, hi = point - half, point + half
    return {
        "point": point, "ci_low": float(lo), "ci_high": float(hi),
        "replicates_sd": float(reps.std(ddof=1)),
        "width": float(hi - lo),
    }


def _location_ci(
    values: np.ndarray, *, statistic: str, block: int,
    n_bootstrap: int, seed: int,
) -> Dict[str, float]:
    """Percentile CI on the full calendar; the missing-day mask travels with each copy."""
    index = _circular_indices(values.size, min(block, values.size), n_bootstrap, seed)
    replicates = values[index]
    with np.errstate(invalid="ignore"):
        stats_values = (
            np.nanmedian(replicates, axis=1) if statistic == "median"
            else np.nanmean(replicates, axis=1)
        )
    stats_values = stats_values[np.isfinite(stats_values)]
    lo, hi = _percentile_interval(stats_values)
    point = float(np.nanmedian(values) if statistic == "median" else np.nanmean(values))
    return {
        "point": point, "ci_low": float(lo), "ci_high": float(hi),
        "replicates_sd": float(stats_values.std(ddof=1)),
        "width": float(hi - lo),
    }


# ---------------------------------------------------------------------------
# Framing helpers shared by structural and semantic tiers
# ---------------------------------------------------------------------------


def _reported_panel_median(part: pd.DataFrame) -> float:
    return float(independent_daily_panel(part)["pm25_mean"].median())


def _daily_effective_n(values: np.ndarray) -> Tuple[float, float]:
    x = np.asarray(values, dtype=float)
    finite = x[np.isfinite(x)]
    if finite.size < 3:
        return float("nan"), float("nan")
    a, b = x[:-1], x[1:]
    pair = np.isfinite(a) & np.isfinite(b)
    if pair.sum() < 3 or np.std(a[pair]) == 0 or np.std(b[pair]) == 0:
        return float("nan"), float("nan")
    rho = float(np.corrcoef(a[pair], b[pair])[0, 1])
    rho = min(rho, 0.999999)
    n = int(np.isfinite(x).sum())
    return rho, float(n * (1.0 - rho) / (1.0 + rho))


def _holm(pvalues: Sequence[float]) -> np.ndarray:
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(p) - rank) * p[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def _compare_classification(
    key: str, baseline: Mapping[str, Any], extended: Mapping[str, Any],
) -> str:
    if key == "season_effect":
        return "EXPLORATORY / INCOMPARABLE"
    e_b, e_h = float(baseline["primary_estimate"]), float(extended["primary_estimate"])
    lo_b, hi_b = float(baseline["primary_ci_low"]), float(baseline["primary_ci_high"])
    lo_h, hi_h = float(extended["primary_ci_low"]), float(extended["primary_ci_high"])
    reject_b = float(baseline["holm_p_value"]) < ALPHA
    reject_h = float(extended["holm_p_value"]) < ALPHA
    same_direction = np.sign(e_b) == np.sign(e_h) and e_b != 0 and e_h != 0
    overlap = max(lo_b, lo_h) <= min(hi_b, hi_h)
    if not same_direction:
        return "INCOMPARABLE (effect direction differs across physical stations)"
    if reject_b and reject_h:
        return (
            "CONCORDANT DIRECTION; OVERLAPPING CI" if overlap
            else "CONCORDANT DIRECTION; DIFFERENT MAGNITUDE"
        )
    if reject_b or reject_h:
        return "WEAKENED / NOT REPLICATED AT ONE STATION"
    return "NO EVIDENCE OF EFFECT IN EITHER STATION"


# ---------------------------------------------------------------------------
# Structural tier
# ---------------------------------------------------------------------------


def validate_structural(
    artifacts: Mapping[str, pd.DataFrame],
    *,
    config: Mapping[str, Any],
    suite: ValidationSuite,
) -> None:
    quality = artifacts["quality"]
    profile = artifacts["profile"]
    inference = artifacts["inference"]
    sensitivity = artifacts["sensitivity"]
    figures = artifacts["figures"]

    suite.equal("config.issue", config.get("issue"), 50)
    suite.true("config.dataset_version", bool(config.get("dataset_version")), "missing")
    suite.equal("quality.period_types", set(quality["period_type"]), set(PERIOD_TYPES))
    suite.equal("quality.stations", set(quality["station_id"]), set(STATIONS))
    suite.equal("profile.stations", set(profile["station_id"]), set(STATIONS))
    suite.equal("inference.stations", set(inference["station_id"]), set(STATIONS))
    suite.equal("inference.tests", set(inference["test"]), set(TEST_KEYS))
    suite.equal("figures.figure_set", set(figures["figure"]), {f"FIG-{i:02d}" for i in range(1, 8)})
    suite.equal("figures.row_count", len(figures), 14)

    # Quality identities and status semantics.
    q = quality
    suite.true(
        "quality.active_denominator",
        ((q["valid_pm25_observations"] + q["missing_active_hours"]) == q["active_grid_hours"]).all(),
        "valid + missing != active grid",
    )
    suite.true(
        "quality.calendar_denominator",
        ((q["active_grid_hours"] + q["outside_active_window_hours"]) == q["expected_calendar_hours"]).all(),
        "active + outside != calendar",
    )
    suite.true(
        "quality.coverage_calendar",
        np.allclose(
            q["coverage_pct_calendar"],
            100.0 * q["valid_pm25_observations"] / q["expected_calendar_hours"],
            rtol=1e-9, atol=1e-9,
        ),
        "coverage_pct_calendar does not use full calendar denominator",
    )
    suite.true(
        "quality.missing_pct",
        np.allclose(
            q["missing_pct_active"],
            100.0 * q["missing_active_hours"] / q["active_grid_hours"],
            rtol=1e-9, atol=1e-9,
        ),
        "missing_pct_active denominator error",
    )
    suite.true(
        "quality.valid_identity",
        (q["valid_pm25_observations"] == q["valid_pm25_hours"]).all(),
        "valid_pm25_observations != valid_pm25_hours",
    )
    suite.true(
        "quality.missing_identity",
        (q["missing_active_hours"] == q["missing_observed_hours"]).all(),
        "missing_active_hours != missing_observed_hours",
    )
    suite.true(
        "quality.partial_flag",
        (q["partial_calendar_period"] == (q["outside_active_window_hours"] > 0)).all(),
        "partial_calendar_period disagrees with outside_active_window_hours",
    )
    suite.true(
        "quality.accuracy_unverifiable",
        (q["dim_accuracy_status"] == "UNVERIFIABLE").all(),
        "device accuracy must stay UNVERIFIABLE without a reference QC",
    )
    suite.true(
        "quality.completeness_status",
        (q["dim_completeness_status"] == np.where(q["valid_pm25_observations"] == q["active_grid_hours"], "PASS", "FAIL")).all(),
        "completeness status is not derived from the active denominator",
    )
    suite.true(
        "quality.uniqueness_status",
        (q["dim_uniqueness_status"] == np.where(q["duplicate_keys"] == 0, "PASS", "FAIL")).all(),
        "uniqueness status does not match duplicate_keys",
    )
    suite.true(
        "quality.validity_status",
        (q["dim_validity_status"]
         == np.where((q["nonfinite_pm25_values"] == 0) & (q["out_of_bounds_pm25_values"] == 0)
                     & (q["other_bound_violations"] == 0), "PASS", "FAIL")).all(),
        "validity status does not match invalid values",
    )
    suite.true(
        "quality.consistency_status",
        (q["dim_consistency_status"]
         == np.where(q["timezone_consistent"] & q["timestamp_order_ok"], "PASS", "FAIL")).all(),
        "consistency status does not match timezone/order flags",
    )
    suite.true(
        "quality.timeliness_status",
        (q["dim_timeliness_status"]
         == np.where((q["irregular_sampling_intervals"] == 0) & q["timezone_consistent"] & q["timestamp_order_ok"], "PASS", "FAIL")).all(),
        "timeliness status does not match irregular intervals",
    )

    # Profile identities.
    suite.true(
        "profile.denominator",
        ((profile["valid_count"] + profile["missing_count"]) == profile["grid_count"]).all(),
        "profile valid + missing != grid",
    )
    suite.true(
        "profile.coverage",
        np.allclose(
            profile["coverage_pct_active"],
            100.0 * profile["valid_count"] / profile["grid_count"],
            rtol=1e-9, atol=1e-9, equal_nan=True,
        ),
        "profile coverage denominator error",
    )
    suite.true(
        "profile.variables",
        set(profile["variable"]) <= set(PROFILE_VARIABLES),
        "unexpected profile variable",
    )

    # Inference schema and family.
    for station, frame in inference.groupby("station_id"):
        suite.equal(f"inference.{station}.rows", len(frame), len(TEST_KEYS))
        suite.equal(f"inference.{station}.unique_tests", set(frame["test"]), set(TEST_KEYS))
        suite.true(
            f"inference.{station}.holm",
            np.allclose(frame["holm_p_value"], _holm(frame["dependence_aware_p_value"])),
            "Holm adjustment does not match the dependence-aware p-values",
        )
        row = frame.loc[frame["test"] == "season_effect"].iloc[0]
        suite.equal(f"inference.{station}.season_status", row["status"], "exploratory")
        suite.equal(f"inference.{station}.season_design", row["test_design"], "exploratory")
        suite.true(
            f"inference.{station}.season_reason",
            any(token in str(row["status_reason"]) for token in ("chu kỳ", "cohort", "chu kì")),
            "seasonal rationale does not describe the observed cohort structure",
        )
        for _, row in frame.iterrows():
            path = f"inference.{station}.{row['test']}"
            suite.true(
                f"{path}.estimand",
                bool(str(row["primary_estimand"]).strip()),
                "primary estimand is empty",
            )
            suite.equal(f"{path}.primary_unit_present", bool(str(row["primary_unit"]).strip()), True)
            suite.true(
                f"{path}.decision",
                row["statistical_decision"] in {
                    "reject_h0_after_holm", "do_not_reject_h0_after_holm",
                },
                "unknown statistical decision",
            )
            suite.true(
                f"{path}.evidence",
                row["evidence_level"] in {
                    "confirmatory_evidence", "no_confirmatory_evidence",
                    "exploratory_signal", "no_exploratory_signal",
                },
                "unknown evidence level",
            )
            rejects = float(row["holm_p_value"]) < ALPHA
            expected_level = (
                ("exploratory_signal" if rejects else "no_exploratory_signal")
                if row["test_design"] == "exploratory"
                else ("confirmatory_evidence" if rejects else "no_confirmatory_evidence")
            )
            suite.equal(f"{path}.evidence_consistency", row["evidence_level"], expected_level)
            expected_decision = (
                "reject_h0_after_holm" if row["holm_p_value"] < ALPHA
                else "do_not_reject_h0_after_holm"
            )
            suite.equal(f"{path}.decision_consistency", row["statistical_decision"], expected_decision)
            suite.true(
                f"{path}.ci_status",
                bool(str(row["ci_status"]).strip()),
                "ci_status is empty",
            )
            suite.true(
                f"{path}.scope",
                bool(str(row["interpretation_scope"]).strip()),
                "interpretation_scope is empty",
            )
            if pd.notna(row["primary_ci_low"]):
                suite.true(
                    f"{path}.primary_ci_order",
                    row["primary_ci_low"] <= row["primary_estimate"] <= row["primary_ci_high"],
                    "primary estimate is outside its primary interval",
                )
            if pd.notna(row["secondary_ci_low"]):
                suite.true(
                    f"{path}.secondary_ci_order",
                    row["secondary_ci_low"] <= row["secondary_estimate"] <= row["secondary_ci_high"],
                    "secondary estimate is outside its secondary interval",
                )
            for column in ("dependence_aware_p_value", "raw_iid_p_value", "holm_p_value"):
                suite.true(
                    f"{path}.{column}",
                    pd.isna(row[column]) or 0.0 <= float(row[column]) <= 1.0,
                    "p-value outside [0,1]",
                )
        # Estimand-specific contracts.
        season = frame.loc[frame["test"] == "season_effect"].iloc[0]
        suite.true(
            f"inference.{station}.season_primary",
            "omnibus" in str(season["primary_estimand"]).lower()
            and "h" in str(season["primary_unit"]).lower(),
            "season primary estimand must be the omnibus H",
        )
        suite.true(
            f"inference.{station}.season_no_primary_ci",
            pd.isna(season["primary_ci_low"]) and "NOT_ESTIMABLE" in str(season["primary_ci_method"]),
            "omnibus H must not claim a primary CI",
        )
        suite.true(
            f"inference.{station}.season_secondary",
            "winter" in str(season["secondary_estimand"]).lower()
            and pd.notna(season["secondary_ci_low"]),
            "season secondary contrast/CI missing",
        )
        weekday = frame.loc[frame["test"] == "weekday_effect"].iloc[0]
        suite.true(
            f"inference.{station}.weekday_primary",
            "hac" in str(weekday["primary_ci_method"]).lower()
            and "weekend" in str(weekday["primary_estimand"]).lower(),
            "weekday primary interval must be the HAC coefficient interval",
        )
        suite.true(
            f"inference.{station}.weekday_secondary",
            "median" in str(weekday["secondary_estimand"]).lower()
            and pd.notna(weekday["secondary_ci_low"]),
            "weekday secondary median contrast missing",
        )
        q24 = frame.loc[frame["test"] == "qcvn_24h"].iloc[0]
        suite.true(
            f"inference.{station}.qcvn24_primary",
            "share" in str(q24["primary_estimand"]).lower()
            and "hac" in str(q24["primary_ci_method"]).lower(),
            "QCVN 24h primary estimand must be the exceedance share with a HAC interval",
        )
        suite.true(
            f"inference.{station}.qcvn24_secondary",
            "median" in str(q24["secondary_estimand"]).lower()
            and pd.notna(q24["secondary_ci_low"]),
            "QCVN 24h secondary median/CI missing",
        )
        annual = frame.loc[frame["test"] == "qcvn_annual"].iloc[0]
        suite.true(
            f"inference.{station}.annual_primary",
            "mean" in str(annual["primary_estimand"]).lower()
            and "hac" in str(annual["primary_ci_method"]).lower(),
            "QCVN annual primary estimand must be the mean with a HAC interval",
        )
        suite.true(
            f"inference.{station}.annual_scope",
            "not a full calendar" in str(annual["interpretation_scope"]).lower()
            or "compliance" in str(annual["interpretation_scope"]).lower(),
            "annual interpretation must disclaim full-year compliance",
        )

    # Sensitivity schema.
    suite.true(
        "sensitivity.axes",
        {"hac_lag", "block_length_days", "min_valid_hours", "derived_interpolation_only",
         "winter_year", "partial_winter_exclusion", "year_selection"} <= set(sensitivity["axis"]),
        "sensitivity axes missing",
    )
    for _, row in sensitivity.loc[sensitivity["p_value"].notna()].iterrows():
        path = f"sensitivity.{row['station_id']}.{row['test']}.{row['axis']}.{row['setting']}"
        suite.true(f"{path}.p_range", 0.0 <= float(row["p_value"]) <= 1.0, "p-value outside [0,1]")
        suite.equal(
            f"{path}.reject_flag",
            bool(row["reject_at_0_05"]),
            bool(float(row["p_value"]) < ALPHA),
        )

    # Figure audit contracts.
    for _, row in figures.iterrows():
        path = f"figures.{row['figure']}.{row['station_id']}"
        suite.true(f"{path}.decision", row["decision"] in DISPLAY_DECISIONS, "unknown decision")
        suite.true(f"{path}.question", bool(str(row["research_question"]).strip()), "empty research question")
        suite.true(f"{path}.dataset", row["dataset_version"] == config["dataset_version"], "dataset version mismatch")
        suite.true(f"{path}.station", row["station_id"] in STATIONS, "unknown station")
        suite.true(f"{path}.span", bool(row["start"]) and bool(row["end"]), "missing span")
        suite.true(f"{path}.n", int(row["n_observed_pm25"]) >= 0, "invalid n")
        suite.true(f"{path}.coverage", 0.0 <= float(row["coverage_pct_active"]) <= 100.0, "coverage out of range")
        suite.true(f"{path}.partial", "partial years:" in str(row["partial_periods"]), "partial periods not explicit")
        suite.true(f"{path}.limitation", bool(str(row["limitation"]).strip()), "missing limitation")
        suite.true(
            f"{path}.reason",
            bool(str(row["reason"]).strip()),
            "missing decision rationale",
        )
        if row["decision"] == "EXTEND":
            suite.true(f"{path}.extended_figure", bool(str(row["extended_figure"]).strip()), "EXTEND without figure")
    for figure in ("FIG-02", "FIG-03"):
        rows = figures.loc[figures["figure"] == figure]
        suite.true(f"figures.{figure}.both_stations", set(rows["station_id"]) == set(STATIONS), "station row missing")
    fig03 = figures.loc[figures["figure"] == "FIG-03"].iloc[0]
    suite.true(
        "figures.FIG-03.semantics",
        "monthly" in str(fig03["research_question"]).lower()
        and "winter coverage" in str(fig03["reason"]).lower(),
        "FIG-03 must show monthly/seasonal distributions and point winter coverage to the supplementary figure",
    )
    suite.true(
        "figures.FIG-03.supplementary",
        "FIG-03b-winter-coverage.png" in str(fig03["supplementary_figure"]),
        "winter coverage supplementary figure missing",
    )
    fig02 = figures.loc[figures["figure"] == "FIG-02"].iloc[0]
    suite.true(
        "figures.FIG-02.partial",
        "partial" in str(fig02["reason"]).lower(),
        "FIG-02 must document partial-year handling",
    )

    suite.finish()


# ---------------------------------------------------------------------------
# Semantic tier
# ---------------------------------------------------------------------------


def _merge_on(
    suite: ValidationSuite, reported: pd.DataFrame, expected: pd.DataFrame,
    keys: Sequence[str], label: str,
) -> pd.DataFrame:
    merged = reported.merge(expected, on=list(keys), how="outer", suffixes=("_r", "_e"), indicator=True)
    suite.true(
        f"{label}.keys",
        merged["_merge"].eq("both").all(),
        f"reported/recomputed key sets differ: "
        f"{merged.loc[merged['_merge'] != 'both', list(keys)].head(5).to_dict('records')}",
    )
    return merged.loc[merged["_merge"] == "both"]


def validate_quality_semantics(
    reported: pd.DataFrame, expected: pd.DataFrame, suite: ValidationSuite,
) -> None:
    merged = _merge_on(suite, reported, expected, ("station_id", "period_type", "period"), "quality")
    exact = [
        "expected_calendar_hours", "active_grid_hours", "valid_pm25_observations",
        "missing_active_hours", "outside_active_window_hours", "gap_count",
        "longest_missing_gap_hours", "duplicate_keys", "nonfinite_pm25_values",
        "out_of_bounds_pm25_values", "negative_sentinel_values",
        "other_bound_violations",
        "irregular_sampling_intervals", "partial_calendar_period",
    ]
    for _, row in merged.iterrows():
        base = f"quality.{row['station_id']}.{row['period_type']}.{row['period']}"
        for column in exact:
            suite.equal(f"{base}.{column}", row[f"{column}_r"], row[f"{column}_e"])
        for column in (
            "coverage_pct_calendar", "coverage_pct_active", "missing_pct_active",
            "median_gap_hours",
        ):
            suite.close(f"{base}.{column}", row[f"{column}_r"], row[f"{column}_e"], rtol=1e-10, atol=1e-10)
        suite.equal(
            f"{base}.derived_pm25_hours",
            int(row["derived_pm25_hours_r"]),
            int(row["derived_pm25_hours_e"]),
        )
        if pd.notna(row.get("available_raw_observations_r")):
            suite.equal(
                f"{base}.raw_observations",
                int(row["available_raw_observations_r"]),
                int(row["available_raw_observations_e"]),
            )
            suite.equal(
                f"{base}.raw_invalid",
                int(row["invalid_raw_observations_r"]),
                int(row["invalid_raw_observations_e"]),
            )
            suite.equal(
                f"{base}.missing_source_rows",
                int(row["missing_source_rows_r"]),
                int(row["missing_source_rows_e"]),
            )
            suite.equal(
                f"{base}.invalid_source_rows",
                int(row["invalid_source_rows_r"]),
                int(row["invalid_source_rows_e"]),
            )


def validate_profile_semantics(
    reported: pd.DataFrame, expected: pd.DataFrame, suite: ValidationSuite,
) -> None:
    keys = ("station_id", "period_type", "period", "variable")
    merged = _merge_on(suite, reported, expected, keys, "profile")
    exact = ["grid_count", "valid_count", "missing_count"]
    numeric = [
        "mean", "median", "variance", "sd", "min", "max", "q25", "q75", "iqr",
        "p90", "p95", "skewness", "excess_kurtosis", "coverage_pct_active",
        "coverage_pct_calendar", "missing_pct_active", "circular_mean_degrees",
        "circular_sd_degrees",
    ]
    for _, row in merged.iterrows():
        base = f"profile.{row['station_id']}.{row['period_type']}.{row['period']}.{row['variable']}"
        for column in exact:
            suite.equal(f"{base}.{column}", int(row[f"{column}_r"]), int(row[f"{column}_e"]))
        for column in numeric:
            suite.close(f"{base}.{column}", row[f"{column}_r"], row[f"{column}_e"], rtol=1e-10, atol=1e-10)


def validate_inference_semantics(
    data: pd.DataFrame,
    reported: pd.DataFrame,
    *,
    config: Mapping[str, Any],
    suite: ValidationSuite,
) -> Dict[str, Any]:
    seed = int(config.get("seed", BOOTSTRAP_SEED))
    n_null = int(config.get("n_null_bootstrap", N_NULL_BOOTSTRAP))
    n_ci = int(config.get("n_ci_bootstrap", N_CI_BOOTSTRAP))
    block = int(config.get("block_length_days", BLOCK_LENGTH_DAYS))
    hac_lag = int(config.get("hac_lag_days", HAC_LAG_DAILY))
    audit_seed = seed + AUDIT_SEED_OFFSET
    recomputed: Dict[str, Any] = {}

    for station, part in data.groupby("station_id"):
        part = _sort_station(part)
        grid = _daily_grid(part)
        panel = independent_daily_panel(part)
        values = panel["pm25_mean"].to_numpy(dtype=float)
        base = _recompute_test_statistics(part)
        recomputed[station] = {"panel": panel, "tests": base}
        reported_station = reported.loc[reported["station_id"] == station].set_index("test")

        # Daily panel / eligible-day contract.
        q_station = None
        suite.equal(f"daily.{station}.n_days", int(reported_station.loc["season_effect", "n_valid_days"]), len(panel))
        suite.close(
            f"daily.{station}.median",
            _reported_panel_median(part),
            float(panel["pm25_mean"].median()),
            rtol=1e-12, atol=1e-12,
        )

        # Season omnibus.
        row = reported_station.loc["season_effect"]
        season = base["season_effect"]
        suite.close(f"season.{station}.H", row["statistic"], season["statistic"], rtol=1e-10, atol=1e-10)
        suite.close(f"season.{station}.p_independence", row["raw_iid_p_value"], season["p_independence"], rtol=1e-10, atol=1e-10)
        suite.close(f"season.{station}.epsilon2", row["effect_size"], season["effect_size"], rtol=1e-10, atol=1e-10)
        suite.close(f"season.{station}.secondary", row["secondary_estimate"], season["secondary_estimate"], rtol=1e-10, atol=1e-10)
        suite.equal(f"season.{station}.ci_status", row["ci_status"], "PRIMARY_NOT_ESTIMABLE; SECONDARY_BOOTSTRAP")
        season_null = _null_bootstrap_p(
            grid, statistic="season", observed=season["statistic"],
            alternative="greater", block=block, n_bootstrap=n_null, seed=audit_seed,
        )
        _compare_bootstrap_p(suite, f"season.{station}.p", row["dependence_aware_p_value"], season_null, n_null)
        season_ci = _contrast_ci(
            grid,
            grid["seasons"] == "Dong",
            grid["seasons"] == "He",
            statistic="median", block=block, n_bootstrap=n_ci, seed=audit_seed,
        )
        _compare_bootstrap_ci(suite, f"season.{station}.secondary_ci", row, season_ci)

        # Weekday.
        row = reported_station.loc["weekday_effect"]
        weekday = base["weekday_effect"]
        suite.close(f"weekday.{station}.t", row["statistic"], weekday["statistic"], rtol=1e-9, atol=1e-9)
        suite.close(f"weekday.{station}.p", row["dependence_aware_p_value"], _weekday_hac_p(part, hac_lag), rtol=1e-9, atol=1e-9)
        suite.close(f"weekday.{station}.estimate", row["primary_estimate"], weekday["estimate"], rtol=1e-10, atol=1e-10)
        suite.close(f"weekday.{station}.ci_low", row["primary_ci_low"], weekday["ci"][0], rtol=1e-9, atol=1e-9)
        suite.close(f"weekday.{station}.ci_high", row["primary_ci_high"], weekday["ci"][1], rtol=1e-9, atol=1e-9)
        suite.close(f"weekday.{station}.p_independence", row["raw_iid_p_value"], weekday["p_independence"], rtol=1e-10, atol=1e-10)
        suite.close(f"weekday.{station}.secondary", row["secondary_estimate"], weekday["secondary_estimate"], rtol=1e-10, atol=1e-10)
        suite.close(f"weekday.{station}.r_rb", row["secondary_effect_size"], weekday["secondary_effect"], rtol=1e-10, atol=1e-10)
        weekday_ci = _contrast_ci(
            grid, grid["weekend"] == 0,
            grid["weekend"] == 1,
            statistic="median", block=block, n_bootstrap=n_ci, seed=audit_seed,
        )
        _compare_bootstrap_ci(suite, f"weekday.{station}.secondary_ci", row, weekday_ci)

        # QCVN 24h.
        row = reported_station.loc["qcvn_24h"]
        q24 = base["qcvn_24h"]
        suite.close(f"q24.{station}.t", row["statistic"], q24["statistic"], rtol=1e-9, atol=1e-9)
        suite.close(f"q24.{station}.p", row["dependence_aware_p_value"], _hac_mean_p(values, QCVN_24H_LIMIT, kind="share", lag=hac_lag), rtol=1e-9, atol=1e-9)
        suite.close(f"q24.{station}.share", row["primary_estimate"], q24["estimate"], rtol=1e-10, atol=1e-10)
        suite.close(f"q24.{station}.ci_low", row["primary_ci_low"], q24["ci"][0], rtol=1e-9, atol=1e-9)
        suite.close(f"q24.{station}.ci_high", row["primary_ci_high"], q24["ci"][1], rtol=1e-9, atol=1e-9)
        suite.close(f"q24.{station}.effect", row["effect_size"], q24["effect_size"], rtol=1e-10, atol=1e-10)
        suite.close(f"q24.{station}.secondary", row["secondary_estimate"], q24["secondary_estimate"], rtol=1e-10, atol=1e-10)
        suite.close(f"q24.{station}.r_rb_pairs", row["secondary_effect_size"], q24["secondary_effect"], rtol=1e-10, atol=1e-10)
        q24_ci = _location_ci(grid["values"], statistic="median", block=block, n_bootstrap=n_ci, seed=audit_seed)
        _compare_bootstrap_ci(suite, f"q24.{station}.secondary_ci", row, q24_ci)

        # QCVN annual.
        row = reported_station.loc["qcvn_annual"]
        annual = base["qcvn_annual"]
        suite.close(f"annual.{station}.t", row["statistic"], annual["statistic"], rtol=1e-9, atol=1e-9)
        suite.close(f"annual.{station}.p", row["dependence_aware_p_value"], _hac_mean_p(values, QCVN_ANNUAL_LIMIT, kind="mean", lag=hac_lag), rtol=1e-9, atol=1e-9)
        suite.close(f"annual.{station}.mean", row["primary_estimate"], annual["estimate"], rtol=1e-10, atol=1e-10)
        suite.close(f"annual.{station}.ci_low", row["primary_ci_low"], annual["ci"][0], rtol=1e-9, atol=1e-9)
        suite.close(f"annual.{station}.ci_high", row["primary_ci_high"], annual["ci"][1], rtol=1e-9, atol=1e-9)
        suite.close(f"annual.{station}.cohen_d", row["effect_size"], annual["effect_size"], rtol=1e-10, atol=1e-10)
        suite.close(f"annual.{station}.secondary", row["secondary_estimate"], annual["secondary_estimate"], rtol=1e-10, atol=1e-10)
        annual_ci = _location_ci(grid["values"], statistic="median", block=block, n_bootstrap=n_ci, seed=audit_seed)
        _compare_bootstrap_ci(suite, f"annual.{station}.secondary_ci", row, annual_ci)

        # Holm is recomputed from the reported dependence-aware p-values.
        suite.true(
            f"holm.{station}",
            np.allclose(
                reported_station["holm_p_value"],
                _holm(reported_station["dependence_aware_p_value"]),
            ),
            "Holm family changed",
        )
        recomputed[station]["grid"] = grid
        recomputed[station]["daily"] = {
            "rho1": _daily_effective_n(grid["values"])[0],
            "n_eff": _daily_effective_n(grid["values"])[1],
        }
    return recomputed


def _weekday_hac_p(part: pd.DataFrame, lag: int) -> float:
    panel = independent_daily_panel(part)
    values = panel["pm25_mean"].to_numpy(dtype=float)
    X, names = _design_weekend(panel)
    model = _ols_hac(values, X, lag)
    return float(model["p"][names.index("weekend")])


def _hac_mean_p(values: np.ndarray, mu: float, *, kind: str, lag: int) -> float:
    if kind == "share":
        series = (values > mu).astype(float)
        model = _ols_hac(series, np.ones((series.size, 1)), lag)
        t_stat = (float(model["beta"][0]) - 0.5) / float(model["se"][0])
    else:
        model = _ols_hac(values, np.ones((values.size, 1)), lag)
        t_stat = (float(model["beta"][0]) - mu) / float(model["se"][0])
    return float(2.0 * stats.t.sf(abs(t_stat), values.size - 1))


def _compare_bootstrap_p(
    suite: ValidationSuite, path: str, reported: float,
    audit: Mapping[str, float], n_bootstrap: int,
) -> None:
    p_hat = float(audit["p_value"])
    p_reported = float(reported)
    if not np.isfinite(p_hat):
        suite.fail(path, "independent bootstrap produced no finite replicates")
        return
    # Two independent Monte-Carlo estimates each contribute variance p(1-p)/B.
    tolerance = max(
        0.01,
        4.0 * math.sqrt(2.0 * max(p_hat * (1.0 - p_hat), 1e-12) / (n_bootstrap + 1)),
    )
    suite.close(
        path, p_reported, p_hat, rtol=0.0, atol=tolerance,
        context=f"Monte-Carlo tolerance {tolerance:.4f} for B={n_bootstrap}",
    )


def _compare_bootstrap_ci(
    suite: ValidationSuite, path: str, row: Any, audit: Mapping[str, float],
) -> None:
    width = float(audit.get("width", 0.0))
    sd = float(audit.get("replicates_sd", 0.0))
    n_bootstrap = max(int(audit.get("n_bootstrap", N_CI_BOOTSTRAP)), 1)
    tolerance = max(
        0.05 * abs(float(audit["point"])),
        0.30 * width,
        4.0 * sd / math.sqrt(n_bootstrap),
    )
    for side, reported in (
        ("low", row["secondary_ci_low"]), ("high", row["secondary_ci_high"]),
    ):
        suite.close(
            f"{path}.{side}", float(reported), float(audit[f"ci_{side}"]),
            rtol=0.0, atol=tolerance,
            context=f"independent calendar bootstrap; tolerance {tolerance:.4g}",
        )


def validate_sensitivity_semantics(
    data: pd.DataFrame,
    reported: pd.DataFrame,
    quality_expected: pd.DataFrame,
    *,
    config: Mapping[str, Any],
    suite: ValidationSuite,
) -> None:
    seed = int(config.get("seed", BOOTSTRAP_SEED))
    n_null = int(config.get("n_null_bootstrap", N_NULL_BOOTSTRAP))
    n_ci = int(config.get("n_ci_bootstrap", N_CI_BOOTSTRAP))
    block = int(config.get("block_length_days", BLOCK_LENGTH_DAYS))
    audit_seed = seed + AUDIT_SEED_OFFSET + 17
    for station, part in data.groupby("station_id"):
        part = _sort_station(part)
        rows = reported.loc[reported["station_id"] == station]
        panel18 = independent_daily_panel(part)
        base_median = float(panel18["pm25_mean"].median())
        # Daily threshold sensitivity.
        for hours in (12, 18, 24):
            grid = _daily_grid(part)
            keep = grid["valid_hours"] >= hours
            values = grid["per_day"]["pm25_mean"].to_numpy(dtype=float)[keep]
            row = rows.loc[
                (rows["test"] == "daily_median") & (rows["axis"] == "min_valid_hours")
                & (rows["setting"].astype(str) == str(hours))
            ]
            suite.equal(f"sensitivity.{station}.min_valid_hours.{hours}.rows", len(row), 1)
            if len(row):
                suite.equal(f"sensitivity.{station}.min_valid_hours.{hours}.n", int(row["n_days"].iloc[0]), int(values.size))
                suite.close(f"sensitivity.{station}.min_valid_hours.{hours}.estimate", row["estimate"].iloc[0], float(np.median(values)), rtol=1e-12, atol=1e-12)
        # Derived interpolation sensitivity.
        derived = part.copy()
        derived["pm25"] = derived["pm25_derived_interpolated"]
        derived_panel = independent_daily_panel(derived)
        row = rows.loc[rows["axis"] == "derived_interpolation_only"]
        suite.equal(f"sensitivity.{station}.derived.rows", len(row), 1)
        if len(row):
            suite.equal(f"sensitivity.{station}.derived.n", int(row["n_days"].iloc[0]), len(derived_panel))
            suite.close(f"sensitivity.{station}.derived.estimate", row["estimate"].iloc[0], float(derived_panel["pm25_mean"].median()), rtol=1e-12, atol=1e-12)
        # Block length point estimates and ordering.
        block_rows = rows.loc[
            (rows["axis"] == "block_length_days") & (rows["test"] == "daily_median")
        ]
        suite.true(f"sensitivity.{station}.blocks", set(block_rows["setting"].astype(int)) == {7, 14, 28, 42}, "block settings missing")
        for _, row in block_rows.iterrows():
            path = f"sensitivity.{station}.block.{int(row['setting'])}"
            suite.close(f"{path}.point", row["estimate"], base_median, rtol=1e-12, atol=1e-12)
            suite.true(f"{path}.ci_order", row["ci_low"] <= row["estimate"] <= row["ci_high"], "CI misses point estimate")
            if int(row["setting"]) in (7, 28):
                ci = _location_ci(
                    _daily_grid(part)["values"], statistic="median",
                    block=int(row["setting"]), n_bootstrap=n_ci, seed=audit_seed,
                )
                _compare_bootstrap_ci(suite, f"{path}.ci", {"secondary_ci_low": row["ci_low"], "secondary_ci_high": row["ci_high"]}, ci)
        # HAC lag sensitivity p-values.
        model_p = {
            "season_effect": lambda lag: _season_hac_p(part, lag),
            "weekday_effect": lambda lag: _weekday_hac_p(part, lag),
            "qcvn_24h": lambda lag: _hac_mean_p(
                panel18["pm25_mean"].to_numpy(dtype=float), QCVN_24H_LIMIT, kind="share", lag=lag,
            ),
            "qcvn_annual": lambda lag: _hac_mean_p(
                panel18["pm25_mean"].to_numpy(dtype=float), QCVN_ANNUAL_LIMIT, kind="mean", lag=lag,
            ),
        }
        for test, function in model_p.items():
            for lag in (7, 14, 21, 28, 42):
                row = rows.loc[
                    (rows["test"] == test) & (rows["axis"] == "hac_lag")
                    & (rows["setting"].astype(str) == str(lag))
                ]
                suite.equal(f"sensitivity.{station}.{test}.hac_lag.{lag}.rows", len(row), 1)
                if len(row):
                    suite.close(
                        f"sensitivity.{station}.{test}.hac_lag.{lag}.p",
                        row["p_value"].iloc[0], function(lag), rtol=0.0, atol=1e-8,
                    )
        # Winter coverage rows.
        winter_expected = quality_expected.loc[
            (quality_expected["station_id"] == station) & (quality_expected["period_type"] == "winter_year")
        ].set_index("period")
        winter_rows = rows.loc[rows["axis"] == "winter_year"]
        suite.equal(f"sensitivity.{station}.winter.rows", len(winter_rows), len(winter_expected))
        for _, row in winter_rows.iterrows():
            path = f"sensitivity.{station}.winter.{row['setting']}"
            suite.true(f"{path}.period", row["setting"] in winter_expected.index, "unknown winter period")
            if row["setting"] in winter_expected.index:
                reference = winter_expected.loc[row["setting"]]
                suite.equal(f"{path}.hours", int(row["n_hours"]), int(reference["valid_pm25_observations"]))
                suite.close(f"{path}.coverage", row["coverage_pct_calendar"], reference["coverage_pct_calendar"], rtol=1e-10, atol=1e-10)
                suite.equal(
                    f"{path}.partial", bool(row["partial_window"]),
                    bool(reference["outside_active_window_hours"] > 0),
                )
        # Winter median with and without low-coverage winters.
        winter_dates = panel18["date"].dt.month.isin([12, 1, 2])
        panel_winter_year = panel18["date"].dt.year + panel18["date"].dt.month.eq(12).astype(int)
        full_years = {
            int(period.rsplit(":", 1)[-1]) for period, reference in winter_expected.iterrows()
            if reference["outside_active_window_hours"] == 0
            and reference["coverage_pct_calendar"] >= 70
        }
        for setting, mask in (
            ("all_observed_winters", winter_dates),
            ("full_window_coverage_ge_70pct", winter_dates & panel_winter_year.isin(full_years)),
        ):
            row = rows.loc[
                (rows["test"] == "winter_daily_median")
                & (rows["axis"] == "partial_winter_exclusion")
                & (rows["setting"] == setting)
            ]
            suite.equal(f"sensitivity.{station}.winter_median.{setting}.rows", len(row), 1)
            if len(row):
                values = panel18.loc[mask, "pm25_mean"]
                suite.equal(f"sensitivity.{station}.winter_median.{setting}.n", int(row["n_days"].iloc[0]), len(values))
                suite.close(
                    f"sensitivity.{station}.winter_median.{setting}.estimate",
                    row["estimate"].iloc[0],
                    float(values.median()) if len(values) else np.nan,
                    rtol=1e-12, atol=1e-12,
                )
        # Year-specific median and coverage.
        year_rows = rows.loc[rows["axis"] == "year_selection"]
        year_quality = quality_expected.loc[
            (quality_expected["station_id"] == station) & (quality_expected["period_type"] == "year")
        ].set_index("period")
        for _, row in year_rows.iterrows():
            year = str(row["setting"])
            path = f"sensitivity.{station}.year.{year}"
            suite.true(f"{path}.year", year in year_quality.index, "unknown year")
            if year not in year_quality.index:
                continue
            annual = part.loc[part["timestamp"].dt.year == int(year)]
            annual_panel = independent_daily_panel(annual)
            suite.equal(f"{path}.n", int(row["n_days"]), len(annual_panel))
            suite.close(f"{path}.estimate", row["estimate"], float(annual_panel["pm25_mean"].median()), rtol=1e-12, atol=1e-12)
            suite.close(f"{path}.coverage", row["coverage_pct_calendar"], year_quality.loc[year, "coverage_pct_calendar"], rtol=1e-10, atol=1e-10)
            suite.equal(
                f"{path}.partial", bool(row["partial_window"]),
                bool(year_quality.loc[year, "outside_active_window_hours"] > 0),
            )
        # Block-length p-values: recompute under H0 for a short and the primary block.
        block_grid = _daily_grid(part)
        block_stats = _recompute_test_statistics(part)
        weekday_mask = independent_daily_panel(part)["is_weekend"].to_numpy(dtype=int) == 0
        weekday_values = independent_daily_panel(part)["pm25_mean"].to_numpy(dtype=float)
        observed_u = float(stats.mannwhitneyu(
            weekday_values[weekday_mask], weekday_values[~weekday_mask],
            alternative="two-sided",
        ).statistic)
        block_audits = {
            "season_effect": lambda b: _null_bootstrap_p(
                block_grid, statistic="season",
                observed=block_stats["season_effect"]["statistic"],
                alternative="greater", block=b, n_bootstrap=n_null, seed=audit_seed,
            ),
            "weekday_effect": lambda b: _null_bootstrap_p(
                block_grid, statistic="weekday", observed=observed_u,
                alternative="two-sided", block=b, n_bootstrap=n_null, seed=audit_seed,
            ),
            "qcvn_24h": lambda b: _signed_rank_null_p(
                block_grid, QCVN_24H_LIMIT, block=b,
                n_bootstrap=n_null, seed=audit_seed,
            ),
        }
        for test, audit_function in block_audits.items():
            for block_setting in (7, 28):
                row = rows.loc[
                    (rows["test"] == test) & (rows["axis"] == "block_length_days")
                    & (rows["setting"].astype(str) == str(block_setting))
                ]
                if len(row):
                    audit = audit_function(block_setting)
                    _compare_bootstrap_p(
                        suite,
                        f"sensitivity.{station}.{test}.block_p.{block_setting}",
                        row["p_value"].iloc[0], audit, n_null,
                    )


def _season_hac_p(part: pd.DataFrame, lag: int) -> float:
    panel = independent_daily_panel(part)
    values = panel["pm25_mean"].to_numpy(dtype=float)
    X, names = _design_season(panel)
    model = _ols_hac(values, X, lag)
    season_columns = [
        index for index, name in enumerate(names)
        if name not in ("intercept", "trend")
    ]
    beta = model["beta"][season_columns]
    cov = model["cov"][np.ix_(season_columns, season_columns)]
    chi2 = float(beta @ np.linalg.pinv(cov) @ beta)
    f_stat = chi2 / len(season_columns)
    return float(stats.f.sf(f_stat, len(season_columns), model["df"]))


def validate_figure_semantics(
    data: pd.DataFrame,
    figures: pd.DataFrame,
    quality_expected: pd.DataFrame,
    *,
    reports_dir: Path,
    figures_dir: Path,
    suite: ValidationSuite,
) -> None:
    for station, part in data.groupby("station_id"):
        part = _sort_station(part)
        q = quality_expected.loc[
            (quality_expected["station_id"] == station) & (quality_expected["period_type"] == "station")
        ].iloc[0]
        partial_years = {
            str(row.period) for row in quality_expected.loc[
                (quality_expected["station_id"] == station)
                & (quality_expected["period_type"] == "year")
                & (quality_expected["outside_active_window_hours"] > 0)
            ].itertuples()
        }
        partial_winters = {
            str(row.period) for row in quality_expected.loc[
                (quality_expected["station_id"] == station)
                & (quality_expected["period_type"] == "winter_year")
                & (quality_expected["outside_active_window_hours"] > 0)
            ].itertuples()
        }
        for _, row in figures.loc[figures["station_id"] == station].iterrows():
            path = f"figures.{row['figure']}.{station}"
            suite.equal(f"{path}.n", int(row["n_observed_pm25"]), int(part["pm25"].notna().sum()))
            suite.close(f"{path}.coverage", row["coverage_pct_active"], 100.0 * part["pm25"].notna().mean(), rtol=1e-10, atol=1e-10)
            suite.equal(f"{path}.start", str(row["start"]), str(part["timestamp"].min()))
            suite.equal(f"{path}.end", str(row["end"]), str(part["timestamp"].max()))
            reported_years = _extract_partial(row["partial_periods"], "partial years")
            reported_winters = _extract_partial(row["partial_periods"], "partial winters")
            suite.equal(f"{path}.partial_years", reported_years, partial_years)
            suite.equal(f"{path}.partial_winters", reported_winters, partial_winters)
            if row["decision"] == "EXTEND":
                figure_path = figures_dir / f"{row['figure']}-extended.png"
                suite.true(f"{path}.file", figure_path.is_file(), f"missing {figure_path.name}")
                if figure_path.is_file():
                    from PIL import Image
                    with Image.open(figure_path) as image:
                        suite.true(f"{path}.dpi", abs(image.info.get("dpi", (0, 0))[0] - 300) <= 1, "DPI is below 300")
            if pd.notna(row["supplementary_figure"]):
                supplementary = reports_dir.parent / str(row["supplementary_figure"])
                suite.true(f"{path}.supplementary_file", supplementary.is_file(), f"missing {supplementary.name}")
                if supplementary.is_file():
                    from PIL import Image
                    with Image.open(supplementary) as image:
                        suite.true(f"{path}.supplementary_dpi", abs(image.info.get("dpi", (0, 0))[0] - 300) <= 1, "DPI is below 300")


def _extract_partial(text: Any, label: str) -> set:
    match = re.search(rf"{re.escape(label)}:\s*([^;]+)", str(text))
    if not match:
        return set()
    value = match.group(1).strip()
    if value.lower() == "none":
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def validate_comparison_semantics(
    data: pd.DataFrame,
    baseline: pd.DataFrame,
    text: str,
    *,
    config: Mapping[str, Any],
    suite: ValidationSuite,
) -> None:
    suite.true("comparison.sha_actual", str(config["dataset_sha256_actual"]) in text, "actual SHA missing")
    suite.true("comparison.sha_snapshot", str(config["dataset_sha256_snapshot"]) in text, "snapshot SHA missing")
    for heading in (
        "Dataset comparison", "Descriptive comparison",
        "Test-by-test concordance", "Supported, weakened or unsupported baseline conclusions",
    ):
        suite.true(f"comparison.heading.{heading}", f"## {heading}" in text, "section missing")
    suite.true(
        "comparison.disjoint",
        "two physical stations" in text and "INCOMPARABLE" in text,
        "cross-station comparison is not explicitly labelled incomparable",
    )
    suite.true(
        "comparison.accuracy",
        "UNVERIFIED" in text,
        "device accuracy is not labelled unverified",
    )
    suite.true(
        "comparison.seasonal",
        "EXPLORATORY / INCOMPARABLE" in text,
        "seasonal conclusion was not kept exploratory",
    )

    baseline_station = "VN001_HANOI_556_NGUYEN_VAN_CU"
    extended_station = "VN003_HANOI_OPENAQ_7441"
    baseline_part = _sort_station(baseline)
    baseline_median = _reported_panel_median(baseline_part)
    extended_part = _sort_station(data.loc[data["station_id"] == baseline_station])
    extended_median = _reported_panel_median(extended_part)
    suite.close(
        "comparison.baseline_median", baseline_median, extended_median,
        rtol=1e-12, atol=1e-12,
        context="VN001 observed cells must be identical in baseline and extended",
    )
    pattern = re.compile(
        r"\| VN001 daily median \| ([0-9.]+) µg/m³ \| ([0-9.]+) µg/m³ at VN001 \|"
    )
    match = pattern.search(text)
    suite.true("comparison.baseline_row", bool(match), "baseline median row missing")
    if match:
        suite.close("comparison.baseline_row.baseline", float(match.group(1)), baseline_median, rtol=1e-6, atol=0.005)
        suite.close("comparison.baseline_row.extended", float(match.group(2)), extended_median, rtol=1e-6, atol=0.005)
    for station in (baseline_station, extended_station):
        station_part = _sort_station(data.loc[data["station_id"] == station])
        panel = independent_daily_panel(station_part)
        match = re.search(
            rf"\| {re.escape(station)} \| ([^|]+) \| ([0-9,]+) \| ([0-9,]+) \| ([0-9.]+)% \| ([0-9,]+) \| ([0-9,]+) \|",
            text,
        )
        suite.true(f"comparison.dataset_row.{station}", bool(match), "dataset row missing")
        if match:
            suite.equal(f"comparison.dataset_row.{station}.grid", int(match.group(2).replace(",", "")), len(data.loc[data["station_id"] == station]))
            suite.equal(f"comparison.dataset_row.{station}.observed", int(match.group(3).replace(",", "")), int(data.loc[data["station_id"] == station, "pm25"].notna().sum()))
            suite.close(f"comparison.dataset_row.{station}.coverage", float(match.group(4)), 100.0 * data.loc[data["station_id"] == station, "pm25"].notna().mean(), rtol=1e-4, atol=0.02)
            suite.equal(f"comparison.dataset_row.{station}.days", int(match.group(6).replace(",", "")), len(panel))
        match = re.search(
            rf"\| {re.escape(station)} \| ([0-9.]+) / ([0-9.]+) \| ([0-9.]+) / ([0-9.]+) \| ([0-9.]+) / ([0-9.]+) \|",
            text,
        )
        suite.true(f"comparison.descriptive_row.{station}", bool(match), "descriptive row missing")
        if match:
            hourly = station_part["pm25"].dropna()
            suite.close(f"comparison.descriptive_row.{station}.median", float(match.group(1)), float(hourly.median()), rtol=1e-4, atol=0.02)
            suite.close(f"comparison.descriptive_row.{station}.mean", float(match.group(2)), float(hourly.mean()), rtol=1e-4, atol=0.02)
            suite.close(f"comparison.descriptive_row.{station}.sd", float(match.group(3)), float(hourly.std(ddof=1)), rtol=1e-4, atol=0.02)
            suite.close(f"comparison.descriptive_row.{station}.iqr", float(match.group(4)), float(hourly.quantile(.75) - hourly.quantile(.25)), rtol=1e-4, atol=0.02)
    # Concordance taxonomy must match independent classification.
    inference = pd.read_csv(config["_inference_path"]) if config.get("_inference_path") else None
    if inference is not None:
        for key in TEST_KEYS:
            b = inference.loc[
                (inference["station_id"] == baseline_station) & (inference["test"] == key)
            ].iloc[0]
            h = inference.loc[
                (inference["station_id"] == extended_station) & (inference["test"] == key)
            ].iloc[0]
            expected = _compare_classification(key, b.to_dict(), h.to_dict())
            line = next((line for line in text.splitlines() if line.startswith(f"| {key} |")), "")
            cells = [cell.strip() for cell in line.strip("|").split("|")] if line else []
            suite.true(f"comparison.concordance.{key}.row", len(cells) == 6, "test row missing or malformed")
            if len(cells) != 6:
                continue
            suite.equal(f"comparison.concordance.{key}.classification", cells[5], expected)
            for column, row in ((1, b), (2, h)):
                prefix = f"comparison.concordance.{key}.{row['station_id']}"
                entry = re.fullmatch(r"([\-\d.eE+]+) (\[[^\]]+\]|n/a)", cells[column])
                suite.true(f"{prefix}.format", bool(entry), "estimate/CI missing")
                if not entry:
                    continue
                point = float(row["primary_estimate"])
                suite.close(f"{prefix}.estimate", float(entry.group(1)), point,
                            rtol=0, atol=0.0006 * max(1, abs(point)))
                if pd.notna(row["primary_ci_low"]):
                    suite.true(f"{prefix}.ci_present", entry.group(2) != "n/a", "CI hidden")
                    if entry.group(2) != "n/a":
                        bounds = entry.group(2).strip("[]").split(",")
                        suite.true(f"{prefix}.ci_format", len(bounds) == 2, "CI bounds malformed")
                        if len(bounds) == 2:
                            for bound, field_name in zip(bounds, ("primary_ci_low", "primary_ci_high")):
                                value = float(row[field_name])
                                suite.close(f"{prefix}.{field_name}", float(bound), value,
                                            rtol=0, atol=0.006 * max(0.1, abs(value)))
            p_values = cells[3].split(" / ")
            suite.true(f"comparison.concordance.{key}.p_format", len(p_values) == 2, "Holm values missing")
            if len(p_values) == 2:
                for reported_p, row in zip(p_values, (b, h)):
                    suite.close(f"comparison.concordance.{key}.{row['station_id']}.holm",
                                float(reported_p), row["holm_p_value"], rtol=0, atol=0.0006)
            suite.equal(f"comparison.concordance.{key}.evidence", cells[4],
                        f"{b['evidence_level']} / {h['evidence_level']}")


# ---------------------------------------------------------------------------
# Bundle driver
# ---------------------------------------------------------------------------


def load_artifacts(reports_dir: Path) -> Dict[str, pd.DataFrame]:
    return {
        "quality": pd.read_csv(reports_dir / "extended_data_quality_by_station_year_season.csv"),
        "profile": pd.read_csv(reports_dir / "extended_statistical_profile.csv"),
        "inference": pd.read_csv(reports_dir / "extended_inference_results.csv"),
        "sensitivity": pd.read_csv(reports_dir / "extended_inference_sensitivity.csv"),
        "figures": pd.read_csv(reports_dir / "extended_figure_audit.csv"),
        "gaps": pd.read_csv(reports_dir / "extended_missingness_gaps.csv"),
        "meteorology": pd.read_csv(reports_dir / "extended_meteorology_associations.csv"),
    }


def validate_real_data(
    data: pd.DataFrame,
    *,
    baseline: pd.DataFrame,
    raw_vn003: Optional[pd.DataFrame],
    artifacts: Mapping[str, pd.DataFrame],
    config: Mapping[str, Any],
    reports_dir: Path,
    figures_dir: Path,
    bootstrap: bool = True,
) -> Dict[str, Any]:
    """Run the semantic tier and return a machine-readable summary."""
    suite = ValidationSuite("semantic")
    expected_quality = recompute_quality(data, raw_vn003)
    expected_profile = recompute_profile(data)
    validate_quality_semantics(artifacts["quality"], expected_quality, suite)
    validate_profile_semantics(artifacts["profile"], expected_profile, suite)
    recomputed: Dict[str, Any] = {}
    if bootstrap:
        recomputed = validate_inference_semantics(
            data, artifacts["inference"], config=config, suite=suite,
        )
    else:
        # Deterministic quantities still get recomputed; bootstrap-derived
        # quantities are only checked structurally.
        for station, part in data.groupby("station_id"):
            recomputed[station] = {"tests": _recompute_test_statistics(_sort_station(part))}
        reported = artifacts["inference"].set_index(["station_id", "test"])
        for station in STATIONS:
            for key in TEST_KEYS:
                base = recomputed[station]["tests"][key]
                row = reported.loc[(station, key)]
                suite.close(
                    f"{key}.{station}.statistic", row["statistic"],
                    base["statistic"], rtol=1e-9, atol=1e-9,
                )
    validate_sensitivity_semantics(
        data, artifacts["sensitivity"], expected_quality, config=config, suite=suite,
    )
    validate_figure_semantics(
        data, artifacts["figures"], expected_quality,
        reports_dir=reports_dir, figures_dir=figures_dir, suite=suite,
    )
    comparison_path = reports_dir / "extended_reanalysis_comparison.md"
    if comparison_path.is_file():
        config_with_paths = dict(config)
        config_with_paths["_inference_path"] = reports_dir / "extended_inference_results.csv"
        validate_comparison_semantics(
            data, baseline, comparison_path.read_text(encoding="utf-8"),
            config=config_with_paths, suite=suite,
        )
    else:
        suite.fail("comparison.file", "extended_reanalysis_comparison.md is missing")
    suite.finish()
    return {
        "checks": suite.checks,
        "failures": 0,
        "stations": list(STATIONS),
        "bootstrap_recomputed": bool(bootstrap),
        "recomputed_panels": {
            station: int(len(payload["tests"].get("panel", [])))
            for station, payload in recomputed.items()
        },
    }
