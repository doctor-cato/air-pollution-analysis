# Issue #44 — Historical-source feasibility & approval decision

**Decision date:** 2026-11-05
**Decision:** **APPROVED for station-specific historical data expansion (`VN003_HANOI_OPENAQ_7441`, OpenAQ S3 Location `7441`, 2022–2025); third-party GitHub mirror remains NO-GO / Reference-Only.**

OpenAQ S3 Location `7441` (`sensors_id=21632`, provider `AirNow`, `Government Monitor`, `US Public Domain` license `http://www.usa.gov/publicdomain/label/1.0/`, coordinates `21.021939°N, 105.818806°E`) is approved and ingested as an independent historical station (`VN003_HANOI_OPENAQ_7441`) covering `2022-01-01 01:00:00+07:00` to `2025-04-09 22:00:00+07:00` (`903` daily `.csv.gz` files, `21,401` raw rows, `18,208` numerically valid $\ge 0\ \mu\text{g/m}^3$ post-screening hourly observations). Because OpenAQ S3 CSV files do not carry a per-record `QC Name` column, validity is defined transparently via numerical/sentinel screening (`3,193` negative/sentinel `-999.0` rows converted to `NaN`) and deterministic range/stuck-sensor checks (`pm25_was_stuck == 0`). It is never coalesced into `VN001_HANOI_556_NGUYEN_VAN_CU` or forced to claim identity with unverified mirror files (`VN002_HANOI_US_EMBASSY`). All baseline `VN001` artifacts, splits, figures (`FIG-01`–`FIG-12`), and W9 inference outputs remain byte-identical.

## Verified S3 Archive Inventory (2022–2025)

`reports/issue44_openaq_7441_manifest.json` and `reports/issue44_openaq_poc.json` record the S3 prefix inventory, SHA-256 checksums, schema, and monthly/annual coverage.

| Location | Station ID | 2022 files / rows (S3 → parsed TZ) | 2023 files / rows (S3 → parsed TZ) | 2024 files / rows (S3 → parsed TZ) | 2025 files / rows (S3 → parsed TZ) | Decision & Finding |
|---|---|---:|---:|---:|---:|---|
| `7441` | `VN003_HANOI_OPENAQ_7441` | 190 / 4,560 → 4,559 (`3,079` valid) | 249 / 5,793 → 5,794 (`5,646` valid) | 365 / 8,703 → 8,702 (`7,218` valid) | 99 / 2,345 → 2,346 (`2,265` valid) | **APPROVED (Station-Specific Historical Series).** `21,401` raw hourly rows (`18,208` numerically valid $\ge 0\ \mu\text{g/m}^3$, `3,193` negative/sentinel nulled to `NaN`). |
| `4946811` | `VN001_HANOI_556_NGUYEN_VAN_CU` | 0 / 0 | 0 / 0 | 0 / 0 | 180+ / 349,463 total | **APPROVED (Immutable Baseline).** Covers `2025-07-03` to `2026-07-15` (`9,044` canonical grid hours, `7,495` valid $\text{PM}_{2.5}$ hours). |
| `2539` | Unassigned (`StateAir Hanoi`) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | **NO-GO.** Zero public S3 objects in 2022–2025. |
| GitHub Mirror (`dolekhanhdang/...`) | Prospective `VN002` | `46` CSVs total (2022–2025) | — | — | — | **NO-GO / Reference-Only.** `license: null`, unverified chain of custody, 3 misfiled December MTD files (`1,627` rows; 4 files with cross-year records), `25,955` duplicate rows, 1 conflicting duplicate (`2023-11-07T17:00:00`: `33.0` valid in YTD vs `-999.0` missing in MTD). |

## Provenance, License & Station-Separation Rules

1. **First-Party OpenAQ S3 Provenance & License:** The SSR hydration payload on `https://explore.openaq.org/locations/7441` and raw S3 objects verify `id: 7441`, `provider: AirNow (id=119)`, `instruments: ["Government Monitor"]`, `sensors_id: 21632 (pm25 µg/m³)`, `coordinates: (21.021939, 105.818806)`, and `licenses: [{id: 33, name: "US Public Domain", sourceUrl: "http://www.usa.gov/publicdomain/label/1.0/", commercialUseAllowed: true, modificationAllowed: true, redistributionAllowed: true}]`.
2. **Parsed Timestamps Over Storage Prefixes:** S3 year-prefixes (`year=2022`, `year=2024`) are storage partitions whose final daily files include next-year `00:00:00+07:00` midnight records. `OpenAQAdapter.to_canonical()` and `scripts/build_extended_historical_dataset.py` group strictly by parsed `Asia/Ho_Chi_Minh` timestamps (`0` duplicate timestamps across all `21,401` rows).
3. **Strict Station Separation:** `VN003_HANOI_OPENAQ_7441` (`21.021939°N, 105.818806°E`, `9.026 km` from the ERA5 grid point) and `VN001_HANOI_556_NGUYEN_VAN_CU` (`21.0491°N, 105.8831°E`, `1.704 km` from the ERA5 grid point; inter-station distance `7.324 km`) are stored as separate `station_id` partitions in `data/processed/air_pollution_extended_2022_2026.parquet` (`37,722` total rows). Rolling windows, chronological train/test splits, and short-gap interpolation experiments never cross `station_id` or `split` boundaries.
4. **Deliverables Produced:**
   - Reproducible pipeline: `scripts/build_extended_historical_dataset.py`
   - Provenance & coverage manifests: `reports/issue44_openaq_7441_manifest.json`, `reports/issue44_extended_dataset_metadata.json`
   - Masking-validation interpolation evaluation: `reports/issue44_interpolation_evaluation.csv`
   - Multi-year / multi-winter EDA summary: `reports/issue44_multiyear_eda_summary.csv`
   - Extended publication figure: `figures/FIG-01-extended-historical.png` (preserving `figures/FIG-01.png` untouched)
   - Legacy vs. Extended comparison report: `reports/issue44_legacy_vs_extended_comparison.md`
