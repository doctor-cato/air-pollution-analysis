"""Group-level six-dimension data-quality metrics for the Issue #50 audit.

The Issue #5 auditor (``src.data_quality.audit_six_dimensions``) reports at the
dataset/station level. Issue #50 needs the same six dimensions *inside* every
station × year/month/season/winter cohort, with explicit denominators and a
clear separation between:

* missing observations (active grid hours without a value),
* invalid observations (non-finite or out-of-physical-bounds values),
* missing source rows (active hours with no raw source row),
* hours outside the station's active window,
* partial calendar periods.

Device accuracy is **never** promoted to PASS because values sit inside a
physical range: without a reference instrument or independent QC flags it is
``UNVERIFIABLE``. Numerical plausibility is reported separately.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

PM25_MIN = 0.0
PM25_MAX = 1000.0
CANONICAL_TIMEZONE = "Asia/Ho_Chi_Minh"
IRREGULAR_INTERVAL_HOURS = 1.0


def _finite_values(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric[numeric.notna()]


def group_quality_dimensions(
    group: pd.DataFrame,
    *,
    expected_calendar_hours: int,
    outside_active_window_hours: int,
    raw_observations: Optional[int] = None,
    raw_source_hours: Optional[int] = None,
    raw_invalid_observations: Optional[int] = None,
    physical_bounds: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """Compute six-dimension QC fields for one station/period group.

    Parameters are explicit so every ratio has a named denominator. The caller
    is responsible for passing the calendar size and active-window remainder
    that belong to *this* group only; errors from one group must never leak
    into another group's denominator.
    """
    if expected_calendar_hours < 0 or outside_active_window_hours < 0:
        raise ValueError("Calendar denominators must be non-negative")
    if outside_active_window_hours > expected_calendar_hours:
        raise ValueError("Outside-active-window hours exceed the calendar period")

    active = int(len(group))
    if active > expected_calendar_hours:
        raise ValueError("Active hours exceed the calendar period")

    keys = [column for column in ("station_id", "timestamp") if column in group.columns]
    duplicates = int(group.duplicated(keys).sum()) if keys else 0

    timestamps = group["timestamp"] if "timestamp" in group.columns else None
    if timestamps is not None and len(timestamps):
        timezone_ok = bool(
            isinstance(timestamps.dtype, pd.DatetimeTZDtype)
            and str(timestamps.dt.tz) == CANONICAL_TIMEZONE
            and not timestamps.isna().any()
        )
        order_ok = bool(timestamps.is_monotonic_increasing)
        diffs = timestamps.diff().dropna()
        irregular = int((diffs != pd.Timedelta(hours=IRREGULAR_INTERVAL_HOURS)).sum())
    else:
        timezone_ok = False
        order_ok = False
        irregular = active

    pm25 = group["pm25"] if "pm25" in group.columns else pd.Series(dtype=float)
    numeric = pd.to_numeric(pm25, errors="coerce")
    observed_mask = numeric.notna()
    finite_mask = np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan))
    valid_mask = observed_mask & finite_mask & numeric.between(PM25_MIN, PM25_MAX)
    observed = int(observed_mask.sum())
    valid = int(valid_mask.sum())
    nonfinite = int((observed_mask & ~pd.Series(finite_mask, index=numeric.index)).sum())
    out_of_bounds = int(
        (observed_mask & pd.Series(finite_mask, index=numeric.index)
         & (~numeric.between(PM25_MIN, PM25_MAX))).sum()
    )
    negative_sentinel = int((observed_mask & (numeric < PM25_MIN)).sum())

    bound_violations: Dict[str, int] = {}
    if physical_bounds:
        for column, bounds in physical_bounds.items():
            if column not in group.columns:
                continue
            values = _finite_values(group[column])
            bound_violations[column] = int(
                ((values < bounds["min"]) | (values > bounds["max"])).sum()
            )

    missing_observed = active - valid
    missing_source = None if raw_source_hours is None else active - int(raw_source_hours)
    if missing_source is not None and missing_source < 0:
        raise ValueError("Raw source hours exceed active grid hours")
    invalid_source = None if raw_invalid_observations is None else int(raw_invalid_observations)
    derived_cells = (
        int(group["pm25_is_derived"].fillna(False).astype(bool).sum())
        if "pm25_is_derived" in group.columns
        else None
    )

    completeness_status = "PASS" if valid == active else "FAIL"
    uniqueness_status = "PASS" if duplicates == 0 else "FAIL"
    consistency_status = "PASS" if timezone_ok and order_ok else "FAIL"
    validity_status = (
        "PASS" if nonfinite == 0 and out_of_bounds == 0
        and not any(bound_violations.values()) else "FAIL"
    )
    timeliness_status = (
        "PASS" if irregular == 0 and timezone_ok and order_ok else "FAIL"
    )
    accuracy_status = "UNVERIFIABLE"

    return {
        "expected_calendar_hours": int(expected_calendar_hours),
        "active_grid_hours": active,
        "observed_pm25_hours": observed,
        "valid_pm25_hours": valid,
        "missing_observed_hours": missing_observed,
        "missing_source_rows": missing_source,
        "invalid_source_rows": invalid_source,
        "outside_active_window_hours": int(outside_active_window_hours),
        "partial_calendar_period": bool(outside_active_window_hours > 0),
        "duplicate_keys": duplicates,
        "nonfinite_pm25_values": nonfinite,
        "out_of_bounds_pm25_values": out_of_bounds,
        "negative_sentinel_values": negative_sentinel,
        "other_bound_violations": int(sum(bound_violations.values())),
        "derived_pm25_hours": derived_cells,
        "timestamp_order_ok": order_ok,
        "timezone_consistent": timezone_ok,
        "irregular_sampling_intervals": irregular,
        "dim_completeness_status": completeness_status,
        "dim_accuracy_status": accuracy_status,
        "dim_accuracy_reason": (
            "No reference instrument or independent row-level QC flag; numerical "
            "plausibility is not device accuracy"
        ),
        "dim_consistency_status": consistency_status,
        "dim_validity_status": validity_status,
        "dim_uniqueness_status": uniqueness_status,
        "dim_timeliness_status": timeliness_status,
        "dim_source_timeliness_status": (
            "UNVERIFIABLE: no per-row acquisition-latency or publication timestamp"
        ),
        "denominator_basis": (
            "active_grid_hours for active ratios; expected_calendar_hours for calendar ratios"
        ),
    }


def compare_station_evidence(
    key: str,
    baseline: Dict[str, Any],
    extended: Dict[str, Any],
    *,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Compare two station-specific conclusions without equating decisions.

    Agreement of a reject/do-not-reject decision is **not** evidence that the two
    physical stations share the same effect. The classification therefore looks
    at effect direction, magnitude and primary CI overlap as well as the Holm
    decision. Seasonal effects stay exploratory/incomparable by rule R5.
    """
    if key == "season_effect":
        return {
            "classification": "EXPLORATORY / INCOMPARABLE",
            "rationale": (
                "Seasonal tests are exploratory (R5); seasons are confounded with time and "
                "the two stations have different spans and cohort coverage"
            ),
            "same_direction": None,
            "ci_overlap": None,
        }
    estimate_b = _as_float(baseline.get("primary_estimate"))
    estimate_h = _as_float(extended.get("primary_estimate"))
    low_b, high_b = _as_float(baseline.get("primary_ci_low")), _as_float(baseline.get("primary_ci_high"))
    low_h, high_h = _as_float(extended.get("primary_ci_low")), _as_float(extended.get("primary_ci_high"))
    p_b, p_h = _as_float(baseline.get("holm_p_value")), _as_float(extended.get("holm_p_value"))
    values = (estimate_b, estimate_h, low_b, high_b, low_h, high_h, p_b, p_h)
    if any(value is None or not np.isfinite(value) for value in values):
        return {
            "classification": "UNVERIFIED",
            "rationale": "A required primary estimate, CI or Holm p-value is missing/non-finite",
            "same_direction": None,
            "ci_overlap": None,
        }
    reject_b, reject_h = bool(p_b < alpha), bool(p_h < alpha)
    same_direction = bool(np.sign(estimate_b) == np.sign(estimate_h)) and estimate_b != 0 and estimate_h != 0
    ci_overlap = bool(max(low_b, low_h) <= min(high_b, high_h))
    if not same_direction:
        classification = "INCOMPARABLE (effect direction differs across physical stations)"
        rationale = "Primary estimates have different signs or one is exactly zero"
    elif reject_b and reject_h:
        if ci_overlap:
            classification = "CONCORDANT DIRECTION; OVERLAPPING CI"
            rationale = (
                "Both stations reject after Holm with the same direction and overlapping "
                "primary CIs; this is not proof that the effects are equal"
            )
        else:
            classification = "CONCORDANT DIRECTION; DIFFERENT MAGNITUDE"
            rationale = "Both stations reject after Holm but the primary CIs do not overlap"
    elif reject_b or reject_h:
        classification = "WEAKENED / NOT REPLICATED AT ONE STATION"
        rationale = "Only one station rejects after Holm; the other gives no comparable evidence"
    else:
        classification = "NO EVIDENCE OF EFFECT IN EITHER STATION"
        rationale = "Neither station rejects after Holm"
    return {
        "classification": classification,
        "rationale": rationale,
        "same_direction": same_direction,
        "ci_overlap": ci_overlap,
        "reject_baseline": reject_b,
        "reject_extended": reject_h,
        "estimate_baseline": estimate_b,
        "estimate_extended": estimate_h,
    }


def _as_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None
