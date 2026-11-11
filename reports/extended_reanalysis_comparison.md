# Issue #50 — baseline versus extended reanalysis

Dataset `2.0.0-issue44-extended`; actual SHA-256 `124c7fc851b89114d7734ed73e4834945d2f589cec263ffe443f23956d35bb4b`; stored snapshot SHA-256 `6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02`; byte match: `False`.
All numbers below derive from the saved CSVs and the baseline Parquet. VN001 is the same physical station in baseline and extended and its observed cells are identical. VN003 is a separate station without overlap; cross-station differences do not establish a temporal trend at one location.
Open-Meteo raw snapshot SHA-256 `303aacb68798667e2c838be09ad0047a6cedf292282e9ab250a7dfa88160923f`; local live reanalysis SHA-256 `a0d841fc92efd3e63f4e3f5664fed9211a7cc50ba50ff5a632a288ff7329d99b`; byte match `False`. Meteorological association under a changed ERA5 response is exploratory; content equality with the frozen weather snapshot is UNVERIFIED.

## Dataset comparison

| Station | Span | Grid hours | Observed PM2.5 hours | Coverage (active) | Missing hours | Eligible days (≥18/24) |
|---|---|---:|---:|---:|---:|---:|
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-07-03 22:00:00+07:00–2026-07-15 18:00:00+07:00 (exclusive end) | 9,044 | 7,495 | 82.87% | 1,549 | 299 |
| VN003_HANOI_OPENAQ_7441 | 2022-01-01 01:00:00+07:00–2025-04-09 23:00:00+07:00 (exclusive end) | 28,678 | 18,208 | 63.49% | 10,470 | 756 |

## Descriptive comparison

| Station | PM2.5 median / mean (µg/m³) | SD / IQR (µg/m³) | Daily rho1 / n_eff | Strongest linear weather association | Yearly observed medians (µg/m³; full-calendar coverage) |
|---|---|---|---|---|---|
| VN001_HANOI_556_NGUYEN_VAN_CU | 37.32 / 43.76 | 27.89 / 30.73 | 0.728 / 47.1 | surface_pressure: r=0.291 (n=7,495) | 2025: 36.9 (coverage 45.3%), 2026: 37.8 (coverage 40.3%) |
| VN003_HANOI_OPENAQ_7441 | 38.00 / 45.83 | 30.65 / 32.00 | 0.749 / 108.7 | surface_pressure: r=0.298 (n=18,208) | 2022: 41.0 (coverage 35.1%), 2023: 35.0 (coverage 64.5%), 2024: 37.0 (coverage 82.2%), 2025: 44.0 (coverage 25.9%) |

Winter coverage and seasonal cohorts: `extended_data_quality_by_station_year_season.csv` (period_type=winter_year); year-specific median CI and partial-winter exclusion: `extended_inference_sensitivity.csv`. All station/year PM2.5 distributions: `extended_statistical_profile.csv`.

## Test-by-test concordance (direction, magnitude and uncertainty)

`CONCORDANT DIRECTION` only means both stations reject after Holm with the same sign; it does **not** mean the two stations share one effect. Overlapping CIs are not proof of equality, and non-overlapping CIs indicate a magnitude difference.

| Test | VN001 primary estimate [95% CI] | VN003 primary estimate [95% CI] | Holm p (VN001 / VN003) | Evidence level (VN001 / VN003) | Classification |
|---|---|---|---|---|---|
| season_effect | 61.53 n/a | 164.2 n/a | 0.05599 / 0.0003999 | no_exploratory_signal / exploratory_signal | EXPLORATORY / INCOMPARABLE |
| weekday_effect | 3.709 [-0.822, 8.24] | -0.256 [-3.86, 3.34] | 0.1082 / 0.889 | no_confirmatory_evidence / no_confirmatory_evidence | INCOMPARABLE (effect direction differs across physical stations) |
| qcvn_24h | 0.2809 [0.119, 0.443] | 0.3148 [0.222, 0.408] | 0.02501 / 0.0003162 | confirmatory_evidence / confirmatory_evidence | CONCORDANT DIRECTION; OVERLAPPING CI |
| qcvn_annual | 43.38 [35.1, 51.7] | 45.8 [40.2, 51.4] | 7.375e-05 / 2.171e-12 | confirmatory_evidence / confirmatory_evidence | CONCORDANT DIRECTION; OVERLAPPING CI |

## Supported, weakened or unsupported baseline conclusions

| Conclusion | Baseline | Extended evidence | Stability |
|---|---|---|---|
| VN001 daily median | 37.20 µg/m³ | 37.20 µg/m³ at VN001 | SUPPORTED (identical observations) |
| 2022–2026 single-site trend | Not estimated | Stations have disjoint spans | INCOMPARABLE (two physical stations, not one site over time) |
| Device accuracy | No independent calibration | OpenAQ VN003 lacks independent row QC | UNVERIFIED |
| Seasonal effect | Exploratory (single/multi-year but confounded) | Exploratory at both stations | EXPLORATORY / INCOMPARABLE (R5) |

`reports/extended_inference_results.csv` contains test statistics, primary/secondary estimands, effects, CI and adjusted p for each station. `reports/extended_inference_sensitivity.csv` contains block/HAC, daily threshold, derived-value and winter-coverage sensitivity. Negative or unstable tests remain visible; no confirmatory upgrade is inferred from a small p-value alone.
