# Issue #44 — Checkpoint Status (CP0–CP6)

> **Scope:** Station-separated historical dataset expansion (`2022–2025`, `VN003_HANOI_OPENAQ_7441`) alongside the frozen baseline (`2025–2026`, `VN001_HANOI_556_NGUYEN_VAN_CU`).
> **PR Status:** Implemented in PR #45 (under review; not yet merged/closed).

---

## 1. Summary of Checkpoints (CP0–CP6)

| Checkpoint | Status | Deliverable / Evidence |
|---|---|---|
| **CP0 — Historical Source Verification** | **COMPLETED (`VN003` APPROVED / Mirror NO-GO)** | OpenAQ S3 Location `7441` (`VN003_HANOI_OPENAQ_7441`, `sensors_id=21632`, `AirNow` Gov Monitor, `US Public Domain` license `id=33`) is verified and approved for independent station-specific historical analysis (2022–2025). The third-party GitHub mirror (`dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies`, commit `25d08e949c9d01ba57c4e74ff9b3b99328ecf141`) remains **`NO-GO / Reference-Only`** (`repository_license: null`, `3` misfiled directory files, `4` cross-year record files, `1` conflicting duplicate timestamp in `conflict_ledger`). Direct `AirNowDOSAdapter` ingestion (`VN002_HANOI_US_EMBASSY`) remains pending an authenticated official export from AirNow-Tech / U.S. State Department. See [`docs/issue44_source_verification.md`](issue44_source_verification.md), [`docs/issue44_feasibility_decision.md`](issue44_feasibility_decision.md), and [`reports/issue44_mirror_manifest.json`](../reports/issue44_mirror_manifest.json). |
| **CP1 — Multi-Year Raw Acquisition & Provenance** | **COMPLETED** | `903` daily `.csv.gz` S3 files (`2022: 190`, `2023: 249`, `2024: 365`, `2025: 99`; `21,401` raw hourly rows across `2022-01-01 01:00+07:00` → `2025-04-09 22:00+07:00`; `raw_parquet_sha256: 57b6fbaa63089e57a6377fd85293355cb475f8d8bb62fb58b469ced27a4cdae8`) and `28,680` hourly Open-Meteo ERA5 weather records (`2022-01-01` to `2025-04-09`, `0.0%` missing across all 6 variables; `raw_sha256: 303aacb68798667e2c838be09ad0047a6cedf292282e9ab250a7dfa88160923f`) acquired and hashed in [`reports/issue44_openaq_7441_manifest.json`](../reports/issue44_openaq_7441_manifest.json) and [`reports/issue44_extended_dataset_metadata.json`](../reports/issue44_extended_dataset_metadata.json). |
| **CP2 — Canonicalization, QC & Versioned Extended Dataset** | **COMPLETED** | `AirNowDOSAdapter` (`src/data_collection.py`) upgraded to support both `Date (LST)`/`Value` and `Date (LT)`/`Raw Conc.` schemas (never substituting `NowCast Conc.`), enforce `QC Name == 'Valid'`, `Conc. Unit` (`UG/M3`), and `Duration` (`1 Hr`), collapse identical YTD/MTD duplicates, and nullify conflicting duplicates (`qc_reason='conflicting_duplicate'`) while recording full provenance in `attrs['qc_summary']['conflict_ledger']`. `OpenAQAdapter` supports `location_id=7441` (`VN003_HANOI_OPENAQ_7441`), screening `3,193` negative/sentinel records (`-999.0`: `3,188`; `-1.0`: `4`; `-6.0`: `1`) to `NaN` and retaining `18,208` valid hourly observations on a `28,678`-hour station grid (`36.51%` missing). Extended station-separated dataset saved to `data/processed/air_pollution_extended_2022_2026.parquet` (`37,722` rows × `23` columns) while all 7 baseline `VN001` artifacts remain byte-for-byte unchanged (`baseline_immutability_verified: true`). |
| **CP3 — Missingness & Masking-Validation Interpolation Experiment** | **COMPLETED (Negative Finding Retained)** | Contiguous interior gap masking ($L \in \{1, 2, 3, 6\}\text{h}$) across `max_gap_hours` $\in \{1, 2, 3, 6\}$ by station and season (`src/issue44_preparation.py::evaluate_interpolation_grid()`) saved in [`reports/issue44_interpolation_evaluation.csv`](../reports/issue44_interpolation_evaluation.csv) (`160` evaluation rows). Because short-gap linear interpolation ($\le 2\text{h}$) recovers only `9.55%` (`148 / 1,549` missing hours on `VN001`) and `1.85%` (`194 / 10,470` missing hours on `VN003`) while introducing `6.55–10.91 µg/m³` overall RMSE (`12.40–17.24 µg/m³` winter RMSE) and future-endpoint leakage ($t+1$), canonical `pm25` remains strictly un-interpolated (`NaN`). Experimental derived values are isolated in `pm25_derived_interpolated` and `pm25_is_derived`. |
| **CP4 — Traffic Covariate Assessment (FIG-04)** | **COMPLETED (Negative Assessment Retained)** | Audited candidate traffic sources (OpenStreetMap static network, commercial TomTom/Google/HERE APIs, municipal camera portals, academic benchmarks) in [`docs/issue44_traffic_source_assessment.md`](issue44_traffic_source_assessment.md). No public hourly Hanoi traffic-volume series with verified coordinates, 2022–2026 temporal coverage, and open redistribution license exists (`NO-GO`). `FIG-04` retains its observational commute-window framing without causal attribution to traffic volume. |
| **CP5 — Multi-Year EDA, `FIG-01` Extended & Inference Impact** | **COMPLETED** | Station-separated multi-year seasonal and `winter_year` (`W2022`–`W2025` on `VN003`; `W2026` on `VN001`) profiles saved in [`reports/issue44_multiyear_eda_summary.csv`](../reports/issue44_multiyear_eda_summary.csv), [`figures/FIG-01-extended-historical.png`](../figures/FIG-01-extended-historical.png), and [`reports/issue44_legacy_vs_extended_comparison.md`](../reports/issue44_legacy_vs_extended_comparison.md). Calendar-preserving daily seasonal inference (`build_daily_calendar()`, 28-day moving-block bootstrap, Newey–West HAC lag 28) confirms strong winter surges across both stations (`VN003`: Kruskal–Wallis $H = 164.1954$, $\varepsilon^2 = 0.2175$, $p_{\text{boot}} = 0.0005$, Mann–Whitney $r_{rb} = +0.3588$; `VN001`: $H = 61.5344$, $\varepsilon^2 = 0.2065$, $p_{\text{boot}} = 0.029485$, $r_{rb} = +0.5720$) while keeping seasonal inference classified as `exploratory` due to strong daily persistence ($\rho_1 = 0.7487$ on `VN003`, $n_{\text{eff}} = 108.66$ vs `756` valid days; $\rho_1 = 0.7276$ on `VN001`, $n_{\text{eff}} = 47.14$ vs `299` valid days) and multi-month historical missingness (`longest_contiguous_gap_active_window_hours = 2,568` hours in `2022`). Baseline [`figures/FIG-01.png`](../figures/FIG-01.png) and [`reports/inference_results.md`](../reports/inference_results.md) remain untouched. |
| **CP6 — Verification & Reproducibility** | **COMPLETED** | Deterministic unit tests (`690` total test methods across the repository, including `60` in `tests/test_data_collection.py`, `5` in `tests/test_issue44_preparation.py`, and `8` in `tests/test_profile_airnow_mirror.py`) and reproducible CLI entry points below regenerate all manifests, extended datasets, figures, and comparison reports. |

---

## 2. Missingness & Contiguous Gap Metrics Definition

To prevent ambiguity between calendar-bounded and full-series gap statistics across Issue #44 manifests:

- **`longest_gap_hours` (in monthly/annual tables):** Maximum contiguous run of hours where `source_available == True` and `status != 'valid'`, clipped within that specific calendar month or calendar year boundary.
- **`longest_contiguous_gap_active_window_hours` (`reports/issue44_openaq_7441_manifest.json`):** Maximum unclipped contiguous run of missing/invalid hours across the entire active observation window of `VN003_HANOI_OPENAQ_7441` (`2,568` hours in `2022`).
- **`longest_contiguous_gap_full_series_hours` (`reports/issue44_mirror_manifest.json`):** Maximum unclipped contiguous run of missing/invalid hours across the full observation window of the audited third-party GitHub mirror (`1,081` hours, spanning `2022-04` into `2022-05`).

---

## 3. CP6 — Reproducibility Commands (Windows PowerShell & Ubuntu Bash)

1. **Build the extended historical dataset, ERA5 weather backfill, interpolation evaluation, multi-year EDA, and extended figure** (requires internet access only on first download from keyless public OpenAQ S3 Location `7441` and Open-Meteo ERA5; also requires baseline `data/processed/air_pollution_final.parquet` from the main pipeline):
   ```bash
   python scripts/build_extended_historical_dataset.py
   ```
   *(Pass `--force-reload` to force re-downloading raw files from OpenAQ S3 and Open-Meteo ERA5.)*

2. **Re-run the diagnostic profiler on the unapproved third-party GitHub mirror** (reference-only; writes `reports/issue44_mirror_manifest.json` and stores raw CSV blobs in a caller-selected directory without touching canonical datasets):
   ```bash
   python scripts/profile_airnow_mirror.py --output reports/issue44_mirror_manifest.json --raw-dir data/raw/airnow_mirror
   ```

3. **Run Issue #44 unit tests and full test suite:**
   ```bash
   python -m unittest tests.test_data_collection tests.test_issue44_preparation tests.test_profile_airnow_mirror -v
   python -m unittest discover tests
   ```
