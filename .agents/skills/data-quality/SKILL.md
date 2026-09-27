---
name: data-quality
description: Audit time-series air quality and weather datasets across 6 quality dimensions, uncover disguised missing markers, validate physical atmospheric bounds, and identify sensor faults without mutating raw data.
---

# Data Quality Audit Skill

## Purpose
Systematically audit raw and interim air quality and meteorological datasets across the international **6 Dimensions of Data Quality** (Completeness, Accuracy, Consistency, Validity, Uniqueness, Timeliness). Identifies disguised missing markers, detects hardware failure modes (stuck sensors, optical fog scatter), validates environmental physical bounds, and diagnoses missingness mechanisms without modifying underlying raw files.

## When to Use
- Immediately following data collection from OpenAQ v3 and Open-Meteo APIs.
- When validating intermediate datasets before running cleaning scripts or merging tables.
- When preparing the Week 3 Data Quality Audit report or updating `docs/cleaning_log.md`.
- Before executing downstream EDA, regression, or classification pipelines.

## Preconditions
- Raw datasets exist in `data/raw/` (e.g. `openaq_raw_2023_2024.json`, `weather_raw_2023_2024.json`) or interim files in `data/interim/`.
- Target column definitions are specified in [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md) or `docs/data_dictionary.md`.

## Procedure

### 1. Schema & Datatype Inspection
- Load data in inspection mode without modifying the file.
- Verify expected columns exist: `timestamp`, `pm25`, `pm10`, `temperature`, `relative_humidity`, `wind_speed`, `wind_direction`, `precipitation`, `surface_pressure`.
- Check data types: `timestamp` must parse to datetime with timezone awareness; physical measurements must be numeric (`float64`).

### 2. Disguised Missing Value Detection
- Search for disguised missing string markers encoded as numeric values or text:
  ```python
  disguised_markers = ['-999', '-9999', 'N/A', 'None', 'null', 'nan', '']
  ```
- Identify repeated exact zeroes in urban pollution series (`pm25 == 0.00` across multiple consecutive hours indicates sensor zero-drift or disconnect, not clean air).

### 3. Missingness Mechanism Classification (Rubin's Taxonomy)
- Compute column-wise null percentage:
  $$\text{Completeness} = 1 - \frac{\text{Missing Count}}{\text{Total Expected Records}}$$
- Classify the mechanism for each missing feature:
  - **MCAR:** Isolated 1–2 hour missing blocks due to random network transmission drops.
  - **MAR:** Extended outages during documented heavy rainstorms (`precipitation > 50 mm`) or power failure.
  - **MNAR:** Station clipping/saturation during severe winter pollution episodes ($\text{PM}_{2.5} > 300\,\mu\text{g/m}^3$). **Flag for bias analysis; never drop blindly.**

### 4. Record Uniqueness & Temporal Grid Verification
- Assert uniqueness on `timestamp`:
  ```python
  duplicates = df.duplicated(subset=['timestamp']).sum()
  ```
- Generate complete hourly date grid from `min(timestamp)` to `max(timestamp)` at `freq='h'`.
- Quantify total missing hours (temporal gaps) vs. expected 17,520 hours (for 2 complete non-leap/leap years).

### 5. Physical Domain Constraints Validation
Execute boundary checks against atmospheric physics:
- **Aerodynamic Subset Rule:** Verify $\text{PM}_{2.5} \le \text{PM}_{10} + 2.0\,\mu\text{g/m}^3$. Flag all physical inversions.
- **Non-Negativity:** Flag any $\text{PM}_{2.5} < 0$, $\text{PM}_{10} < 0$, or $\text{wind\_speed} < 0$.
- **Atmospheric Bounds:** Check $0\% \le \text{RH} \le 100\%$ and $0^\circ \le \text{wind\_dir} \le 360^\circ$.
- **Optical Fog Artifacts:** Check hours where $\text{RH} > 90\%$ and $\text{PM}_{2.5}$ shows rapid isolated spikes (optical scattering noise).
- **Stuck Sensor Detection:** Identify periods where floating-point concentrations remain unchanged for $> 6$ consecutive hours.

### 6. Compilation of 6-Dimension Scorecard
Score each dimension from 1 (unacceptable) to 5 (excellent) with quantified evidence:
1. *Completeness:* Percentage of non-null records.
2. *Accuracy:* Conformance with official station calibrations and peer sensor consistency.
3. *Consistency:* Units standardized to $\mu\text{g/m}^3$, $^\circ\text{C}$, $\text{m/s}$, $\text{hPa}$; timezone unified to UTC+7.
4. *Validity:* Conformance to physical ranges and datatypes.
5. *Uniqueness:* Zero duplicate timestamps.
6. *Timeliness:* Full temporal continuity across all 12 calendar months without multi-week blackouts.

## Validation
- Ensure the audit script executes purely in read-only mode; source files on disk must remain bit-for-bit unchanged.
- The output report explicitly lists exact row indices, timestamps, and column names for any detected anomaly.

## Failure Modes
- Silently imputing or dropping records during the audit step.
- Failing to inspect raw text payloads, allowing string `"-999"` to cast into numeric $-999.0$.
- Assuming a dataset has no gaps simply because `df['timestamp'].is_monotonic_increasing` is True without checking hourly grid completeness.

## Expected Output
A structured Markdown Data Quality Report containing:
1. 6-dimension quantitative scorecard (1–5 score per dimension).
2. Missingness mechanism breakdown (MCAR vs. MAR vs. MNAR).
3. Table of physical boundary violations (counts, dates, and severity).
4. Concrete recommendations and parameters for [`docs/cleaning_log.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/cleaning_log.md).
