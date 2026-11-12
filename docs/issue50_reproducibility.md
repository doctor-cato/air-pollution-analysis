# Issue #50 — station-separated historical reanalysis

## Execution

Run from the repository root with Python 3.10+ and `pip install -r requirements.txt`:

```bash
python scripts/fetch_dataset.py
# Execute notebooks/03_data_cleaning.ipynb then notebooks/03_transformation_pipeline.ipynb
python scripts/build_extended_historical_dataset.py
python scripts/run_extended_reanalysis.py
python scripts/validate_extended_reanalysis.py --real-data
python -m unittest discover tests -v
python scripts/validate_issue8.py
python scripts/verify_claims.py
```

The first three steps rebuild the gitignored baseline and Issue #44 Parquet files from official sources. Notebook `02_quality_audit.ipynb` must run before cleaning if the full baseline audit is being repeated. The Issue #50 runner only reads `data/`; it writes `reports/extended_*` and three PNGs in `figures/extended/`. Repeated runs use seed 42 and the same W9 family of four tests. `--ci-bootstrap` can increase the CI replication count (minimum 200); the null bootstrap count and HAC lag remain the validated defaults in `src/inference.py`. The output config records parameters and library versions.

## Implementation matrix

| Phase | Requirement | Existing work reused | New work | Evidence | Status |
|---|---|---|---|---|---|
| A | Six-dimension audit, station/year/month/season/winter coverage and gaps | `src/data_quality.py`, Issue #44 manifest | Station-specific QC, raw sentinel tally, missing-run CSV | `reports/extended_data_quality_audit.md`, `reports/extended_data_quality_by_station_year_season.csv`, `reports/extended_missingness_gaps.csv` | IMPLEMENTED; device accuracy UNVERIFIABLE |
| B | Observed/derived integrity, chronological station split, leakage | `src/cleaning.py`, `src/cleaning_pipeline.py`, `src/issue44_preparation.py` | Dataset contract gate, observed-cell equality, validation reports | `reports/extended_preprocessing_validation.md`, `reports/extended_leakage_audit.md`, tests | IMPLEMENTED; no lag/rolling feature built here |
| C | Station-specific multiyear EDA and meteorology | Issue #8 baseline profile; Issue #44 winter summary | Full profile, calendar denominators, year-specific correlations and quintile medians | `reports/extended_statistical_profile.csv`, `reports/extended_eda_findings.md`, `reports/extended_meteorology_*.csv` | IMPLEMENTED; low-coverage cohorts descriptive |
| D | Audit FIG-01..07; create useful figures | FIG-01 extended from PR #45, `src/visualizer.py` | Figure matrix, annual and monthly distribution (with full-calendar monthly coverage), plus supplementary winter-coverage QC | `reports/extended_figure_audit.csv`, `figures/extended/FIG-02-extended.png`, `figures/extended/FIG-03-extended.png`, `figures/extended/FIG-03b-winter-coverage.png` | IMPLEMENTED |
| E | Station-specific W9 with dependence and sensitivity | `src/inference.py` calendar bootstrap, HAC, Holm, Monte Carlo evidence | Run full four-test family independently per station; daily threshold, block/HAC, year and winter sensitivity | `reports/extended_inference_results.csv`, `.md`, `reports/extended_inference_sensitivity.csv` | IMPLEMENTED; season exploratory |
| F | Baseline versus extended stability | Issue #44 initial comparison | Generated dataset/statistical/inference comparison and status by test | `reports/extended_reanalysis_comparison.md` | IMPLEMENTED; cross-station trends incomparable |
| G | Reproducibility and CI/local distinction | Baseline test suite and Issue #44 pinned raw guard | One entrypoint, structural/semantic validator, 12 numbered mutations plus QC/CI regression tests, baseline hash manifest | `reports/extended_reanalysis_config.json`, `reports/issue50_baseline_hashes.json`, `tests/test_extended_reanalysis.py`, `tests/test_extended_validation_mutations.py` | IMPLEMENTED; exact weather snapshot equality UNVERIFIED |

## Provenance and scientific boundaries

The Issue #44 metadata is frozen. The official builder reconstructed 37,722 rows × 23 columns with 7,495 valid PM2.5 hours on VN001 and 18,208 on VN003. The pinned VN003 raw Parquet SHA-256 matched `reports/issue44_openaq_7441_manifest.json`. The locally rebuilt extended Parquet byte hash is `124c7fc851b89114d7734ed73e4834945d2f589cec263ffe443f23956d35bb4b`, while the Issue #44 stored hash is `6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02`. Parquet serialization can vary by library version, so the runner checks schema, station windows, counts, split boundaries, observed VN001 cell equality, station-hour uniqueness and raw provenance rather than treating byte identity as content identity.

The live Open-Meteo response SHA-256 was `a0d841fc92efd3e63f4e3f5664fed9211a7cc50ba50ff5a632a288ff7329d99b`; Issue #44 recorded `303aacb68798667e2c838be09ad0047a6cedf292282e9ab250a7dfa88160923f`. The response has the contracted 28,680 hourly records, but the original raw JSON is unavailable locally. Exact equality of weather values with the frozen snapshot is **UNVERIFIED**. Weather correlations from this rebuild are therefore exploratory. Daily PM2.5 inference does not use ERA5. The raw response and its hash are retained locally without rewriting Issue #44 metadata.

The two stations are roughly 7.324 km apart, with disjoint observation windows. All daily panels, gap runs, inference and year summaries are station-specific. The 18/24 observed-hour rule is an analysis choice, not the legal definition of a 24-hour standard. PM2.5 interpolated values are confined to a labeled sensitivity row. The seasonal null test is exploratory under rule R5; neither cross-station agreement nor small p-values support a causal claim.

## Verification tiers

CI without `data/` runs synthetic contract tests and the **structural** tier: schema/denominator identities, Holm family, estimand/CI contract, figure mapping and tracked-baseline hashes. Semantic tier is **SKIPPED**, not PASS, when real data are unavailable. Local `python scripts/validate_extended_reanalysis.py --real-data` recomputes cohort QC and profile row-by-row, daily panel and test statistics, HAC and calendar-bootstrap intervals with an independent implementation/different seed (Monte Carlo tolerance for stochastic estimates), Holm, sensitivity and comparison text from actual Parquet plus raw VN003. The semantic tier also checks provenance counts, station identity, observed VN001 cells and dataset hash; it cannot prove equality of the unavailable historical ERA5 snapshot. `reports/issue50_baseline_hashes.json` records before/after SHA-256 for baseline files. The three baseline Parquets were absent when this workspace opened; they were reconstructed from source before the Issue #50 runner and hashed immediately before and after it. No claim of byte identity with the unavailable original baseline Parquet is made.

**Remediation verification (Windows with local `data/`, 2026-11-11):** Two successive runs of `scripts/run_extended_reanalysis.py` each reported 37,722 real rows and baseline unchanged. After *each* run, `scripts/validate_extended_reanalysis.py --real-data` returned PASS (603 structural, 16,979 semantic checks; zero failures; 80 QC rows, 702 profile rows, 8 inference rows, 111 sensitivity rows, 14 figure-audit rows). SHA-256 of 19 generated artifacts (`reports/extended_*`, `figures/extended/*`, `reports/issue50_baseline_hashes.json`) was identical between the two runs; all files listed in `before_reanalysis` still matched their snapshot hashes. `FIG-03` shows year-specific monthly PM2.5 distributions and full-calendar *monthly* coverage; `FIG-03b` separately shows partial winter cohorts. The 12 numbered mutation tests cover structural and real-data semantic corruption; two additional mutations check weather validity and the comparison text. This local evidence does not replace CI verification or the still-UNVERIFIED old ERA5 content comparison.

The local full suite ran **764** tests in 194.248 s, `OK` (no skips), with the real Parquet available. `python -m compileall -q src scripts tests` and `git diff --check` exited 0; `scripts/validate_issue8.py` reported 213 passed / 0 failed / 6 warnings, while `scripts/verify_claims.py` reported 37 VERIFIED / 0 MISMATCH / 1 UNVERIFIABLE (38 claims). CI without `data/` ([Actions 43051282775](https://github.com/doctor-cato/air-pollution-analysis/actions/runs/43051282775), SHA `4f02edc`) reported `Ran 740 tests in 152.400s`, `OK (skipped=7)` → 736 executed/passed, 3 class holders excluded from `Ran`. Both CI jobs (Python validation and notebook smoke) passed. See `docs/TEST_SUITE.md` for count semantics.
