# Issue #44 — Checkpoint Status (CP0–CP6)

## Summary of Checkpoints

| Checkpoint | Status | Deliverable / Evidence |
|---|---|---|
| **CP0 — Historical Source Verification** | **COMPLETED (`VN003` APPROVED / Mirror NO-GO)** | OpenAQ S3 Location `7441` (`VN003_HANOI_OPENAQ_7441`, `sensors_id=21632`, `AirNow` Gov Monitor, `US Public Domain` license) is verified and approved for independent station-specific historical analysis (2022–2025). The third-party GitHub mirror (`dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies`) remains `NO-GO / Reference-Only`. See `docs/issue44_source_verification.md` and `docs/issue44_feasibility_decision.md`. |
| **CP1 — Multi-Year Raw Acquisition & Provenance** | **COMPLETED** | `903` daily `.csv.gz` S3 files (`21,401` raw hourly rows across 2022–2025) and `28,680` hourly Open-Meteo ERA5 weather records (`2022-01-01` to `2025-04-09`) acquired and hashed in `reports/issue44_openaq_7441_manifest.json` and `reports/issue44_extended_dataset_metadata.json`. |
| **CP2 — Canonicalization, QC & Versioned Extended Dataset** | **COMPLETED** | `AirNowDOSAdapter` upgraded to enforce `QC Name == 'Valid'`, `Conc. Unit` (`UG/M3`), `Duration` (`1 Hr`), and non-arbitrary YTD/MTD conflict nullification (`qc_reason='conflicting_duplicate'`). `OpenAQAdapter` supports `location_id=7441` (`VN003_HANOI_OPENAQ_7441`). Extended station-separated dataset saved to `data/processed/air_pollution_extended_2022_2026.parquet` (`37,722` rows) while baseline `VN001` artifacts remain byte-identical. |
| **CP3 — Missingness & Masking-Validation Interpolation Experiment** | **COMPLETED (Negative Finding Retained)** | Contiguous gap masking ($L \in \{1, 2, 3, 6\}\text{h}$) across `max_gap_hours` $\in \{1, 2, 3, 6\}$ by station and season saved in `reports/issue44_interpolation_evaluation.csv`. Because short-gap interpolation ($\le 2\text{h}$) recovers only `9.55%` (`VN001`) and `1.85%` (`VN003`) of missing hours while introducing `6.55–10.91 µg/m³` RMSE and future-endpoint leakage, canonical `pm25` remains un-interpolated. |
| **CP4 — Traffic Covariate Assessment (FIG-04)** | **COMPLETED (Negative Assessment Retained)** | No public hourly Hanoi traffic-volume dataset with verified coordinates, coverage, and redistribution terms exists for 2022–2026 (`docs/issue44_traffic_source_assessment.md`). `FIG-04` retains its observational commute-window framing without causal attribution. |
| **CP5 — Multi-Year EDA, `FIG-01` Extended & Inference Impact** | **COMPLETED** | Multi-year seasonal and `winter_year` (`W2022`–`W2026`) profiles saved in `reports/issue44_multiyear_eda_summary.csv`, `figures/FIG-01-extended-historical.png`, and `reports/issue44_legacy_vs_extended_comparison.md`. Baseline `figures/FIG-01.png` and `reports/inference_results.md` remain untouched. |
| **CP6 — Verification & Reproducibility** | **COMPLETED** | Reproducible commands below regenerate all manifests, extended datasets, figures, and comparison reports. |

## CP6 — Reproducibility Commands

To build the extended historical dataset, weather backfill, interpolation experiment, multi-year EDA, and extended figure from the approved OpenAQ S3 Location `7441` and Open-Meteo ERA5 archives:

```powershell
python scripts/build_extended_historical_dataset.py
```

To re-run the diagnostic profiler on the unapproved third-party GitHub mirror (reference-only):

```powershell
python scripts\profile_airnow_mirror.py `
  --output reports\issue44_mirror_manifest.json `
  --raw-dir data\raw\airnow_mirror
```
