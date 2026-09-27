# Pre-Completion Verification Workflow

> **Purpose:** Final verification gate that agents must complete before declaring any task, script, analysis, or notebook complete.

---

## 1. Final Verification Checklist

Every completed task must pass through this 9-point verification gate:

| # | Verification Area | Verification Action / Command | Success Criteria |
|---|---|---|---|
| **1** | **Git Status** | `git status` | Clean working tree, no untracked junk or unintended files |
| **2** | **Git Diff** | `git diff` | Diff contains only requested changes; zero secrets or raw dumps |
| **3** | **Tests / Assertions** | Run project assertions script | All data boundaries, uniqueness, and ordering checks pass |
| **4** | **Syntax / Imports** | `python -m py_compile src/<module>.py` | Clean exit code 0; all imports resolve cleanly |
| **5** | **Data Integrity** | Run time-series safety assertions | Unique timestamps, monotonic order, no Cartesian row explosion |
| **6** | **Notebook Health** | Run "Restart Kernel & Run All" | Notebook executes sequentially from top to bottom with 0 errors |
| **7** | **Plots & Tables** | Inspect `figures/*.png` and reports | 300 DPI, conclusion titles, labeled axes with units, bar at $y=0$ |
| **8** | **Statistical Rigor** | Inspect hypothesis & model tables | Trio reported ($p$-val, Effect size, CI); LINE checked; baseline present |
| **9** | **Documentation** | Inspect `docs/` and `README.md` | `cleaning_log.md` updated; planned vs. completed clearly distinguished |

---

## 2. Core Python Assertion Verification Block

Copy and execute this script to programmatically verify processed datasets:

```python
import numpy as np
import pandas as pd

# Load dataset for verification
df = pd.read_parquet('data/processed/air_pollution_final.parquet')

# 1. Time-series safety checks
assert df['timestamp'].is_unique, "FAIL: Duplicate timestamps detected!"
assert df['timestamp'].is_monotonic_increasing, "FAIL: Timestamps not chronologically sorted!"
assert df['timestamp'].dt.tz is not None, "FAIL: Timestamps lack timezone awareness!"

# 2. Physical domain bounds checks
if 'pm10' in df.columns:
    violations = (df['pm25'] > df['pm10'] + 2.0).sum()
    assert violations == 0, f"FAIL: {violations} records violate PM2.5 <= PM10!"

assert (df['pm25'].dropna() > 0).all(), "FAIL: Non-positive PM2.5 values detected!"

if 'relative_humidity' in df.columns:
    assert ((df['relative_humidity'].dropna() >= 0) & 
            (df['relative_humidity'].dropna() <= 100)).all(), "FAIL: RH outside [0, 100]%!"

if 'wind_speed' in df.columns:
    assert (df['wind_speed'].dropna() >= 0).all(), "FAIL: Negative wind speed detected!"

print("✓ All physical and time-series assertions PASSED.")
```

---

## 3. Reporting Verification Results

In the final response to the user, the agent must clearly distinguish the following 4 categories:

### A. Implemented
- Explicit list of files created, functions written, or notebooks updated during this task.

### B. Verified (with Concrete Evidence)
- Specific commands executed and their output results.
- Concrete metrics obtained (e.g. row counts, test statistics, $p$-values, $R^2$, Recall, PR-AUC).
- Confirmation of clean `git diff` review.

### C. Not Verified (Out of Scope)
- Downstream steps or upcoming roadmap milestones that were intentionally not executed in this turn.

### D. Known Limitations & Caveats
- Environmental sensing limitations (e.g. single BAM 1020 station spatial representation bias, optical fog distortion when $\text{RH} > 90\%$).
- Model boundaries (e.g. model applies to urban central Hanoi; not calibrated for extreme catastrophic events).
