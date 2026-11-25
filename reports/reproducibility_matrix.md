# Reproducibility Matrix & Audit Ledger (Issue #17 — Milestone 6)

> **Course:** INFO3020 – Introduction to Data Science (CMC University)
> **Instructor:** M.Sc. Pham Ngoc Dong
> **Audit Date:** `2026-11-20`
> **Runtime Observed:** `Windows-11-10.0.26200-SP0` | Python `3.14.10` (`py -3.14`) | `pandas 3.1.1` | `numpy 2.5.4` | `scipy 1.18.1` | `statsmodels 0.15.0` | `scikit-learn 1.9.1` | `matplotlib 3.11.2` | `seaborn 0.13.2` | `pyarrow 26.0.1` | `nbconvert 7.17.2` | `nbclient 0.11.0` | `nbformat 5.11.1` | `python-docx 1.2.0`

---

## 1. Executive Summary & Verification Verdict

| Verification Dimension | Command / Scope | Directly Observed Result | Status |
|---|---|---|:---:|
| **Python Syntax & Compilation** | `py -3.14 -m compileall -q src tests scripts` | Exit code `0` across all modules in `src/`, `tests/`, `scripts/` | **PASS** |
| **Local Unit Test Suite (with `data/`)** | `py -3.14 -m unittest discover tests -v` | Exit code `0` across all **836** defined test methods across 20 modules (including `3` in `test_ethics_audit.py` + `9` in `test_sensitivity.py`) | **PASS** |
| **CI Projection (without `data/`)** | `.github/workflows/ci.yml` (`data/` excluded) | **836** defined − **28** in 5 skipped `setUpClass` classes = **808** expected `Ran` (**804** expected pass, **9** expected skips including 4 in-`Ran`) | **PROJECTED** |
| **Empirical Claims Verifier** | `py -3.14 scripts/verify_claims.py` | Exit code `0`: **37** `VERIFIED`, **0** `MISMATCH`, **1** documented `UNVERIFIABLE` (`fog_mutual_information`) | **PASS** |
| **Issue #8 Deliverable & Live NB 04 Audit** | `py -3.14 scripts/validate_issue8.py` | Exit code `0`: **213 passed**, **0 failed**, **6 warnings** (expected raw/processed metadata provenance warnings); live `04_descriptive_stats.ipynb` execution **0 errors** | **PASS** |
| **Issue #50 Extended Reanalysis Validator** | `py -3.14 scripts/validate_extended_reanalysis.py --real-data` | Exit code **`1`** (`ReanalysisValidationError: semantic-content validation failed (2/35)`): **603** structural checks passed, **33/35** semantic checks passed; **2/35** hash checks differ strictly between original Issue #44 files on disk (`6930557f...`, `303aacb6...`) and PR #52 rebuild hashes in `reports/extended_reanalysis_config.json` (`124c7fc8...`, `a0d841fc...`) | **PARTIAL / KNOWN HASH DIFF** |
| **Clean Notebook Sequential Execution** | `nbconvert --to notebook --execute --output-dir <tempdir>` on `00`, `04`, `05`, `06`, `07` | **5/5** executed with exit code `0` (`00`: `6.4s`, `04`: `9.8s`, `05`: `15.2s`, `06`: `111.5s`, `07`: `105.9s`; total `248.8s`) | **PASS** |
| **Notebook Serialization Stability** | `TestNotebooksAreSerializationStable` | `2/2` passed (`nbformat.write()` byte-identical, single LF trailing newline) | **PASS** |
| **Test Count Documentation Guard** | `TestDocumentedTestCounts` | `3/3` passed (`AGENTS.md`, `docs/TEST_SUITE.md`, `README.md`, `docs/roadmap.md` synced to `836`) | **PASS** |
| **Internal Markdown Links** | Relative link audit across `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/*.md`, `reports/*.md` | **43 files**, **161 links** checked: **0 broken** | **PASS** |
| **Git Hygiene & Raw Data Policy** | `git diff --check` & `git ls-files data/` | Zero trailing-whitespace/conflict errors; `git ls-files data/` contains only `.gitkeep` files and `data/raw/metadata.json` | **PASS** |

---

## 2. Input SHA-256 → Script / Notebook → Output Artifact → Verified Claims Matrix

| Input Artifact & Observed SHA-256 | Script / Notebook | Output Artifact & Observed SHA-256 / Size | Directly Verified Scientific Claims & Key Findings |
|---|---|---|---|
| `data/raw/openaq_raw_4946811.parquet`<br>`661578c388...` (`1,610,003 B`)<br>`data/raw/open_meteo_raw_2025-07-03_2026-07-15.json`<br>`249fc0c951...` (`929,879 B`) | `notebooks/01_data_collection.ipynb`<br>`src/data_collection.py`<br>`scripts/fetch_dataset.py` | `data/interim/air_quality_canonical.parquet`<br>`7e7c53509c...` (`199,958 B`)<br>`data/interim/weather_canonical.parquet`<br>`9a7d65f4a9...` (`150,012 B`) | • Station `VN001_HANOI_556_NGUYEN_VAN_CU` (`location_id=4946811`, `21.0491°N, 105.8831°E`).<br>• ERA5 weather (`1.704 km` from station) dynamically synchronized (`100%` overlap). |
| `data/interim/*.parquet`<br>`data/raw/metadata.json` (`4168f5442c...`, `20,191 B`) | `notebooks/02_quality_audit.ipynb`<br>`src/data_quality.py` | `docs/data_quality_audit.md` | • 6-dimension data quality audit before cleaning.<br>• Identified 1,549 `pm25` missing hours (`17.13%`), non-MCAR outage clusters, and sentinel screening rules. |
| `data/interim/*.parquet` | `notebooks/03_data_cleaning.ipynb`<br>`notebooks/03_transformation_pipeline.ipynb`<br>`src/cleaning.py`, `src/cleaning_pipeline.py` | `data/processed/air_pollution_final.parquet`<br>`866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd`<br>(`267,399 B`, `9,044 × 18`) | • Strict `assert_no_imputation()` cell-by-cell invariance (`1,549` NaN preserved).<br>• 1:1 `merge_air_weather()` with zero row explosion.<br>• Chronological split `2026-01-15 00:00+07:00` (`4,682` Train / `4,362` Test grid hours) & Train-only `Pipeline` verified by `validate_no_leakage()`. |
| `data/processed/air_pollution_final.parquet`<br>(`866f39de17...`) | `notebooks/04_descriptive_stats.ipynb`<br>`scripts/generate_04_notebook.py`<br>`src/visualizer.py` | `reports/statistical_profile.csv`<br>`6b2dd964129cf860481d9477eb7eaec091cc93127c3b55c13b4e938b313d8197` (`2,608 B`)<br>`figures/FIG-01.png`–`FIG-07.png` | • `pm25` (`n=7,495`): mean `43.76`, median `37.32`, IQR `30.73`, skewness `+1.2947`, kurtosis `+1.9133`.<br>• `corr(pm25, pm10) = 0.9727` (`R² = 0.9462`).<br>• Circular wind direction: mean `107.12°`, circular std `82.32°`.<br>• Fog interaction (`src/flag_evidence.py`): `F(3, 7487) = 16.7754`, `p = 7.38e-11`. |
| `data/processed/air_pollution_final.parquet`<br>(`866f39de17...`) | `notebooks/05_statistical_inference.ipynb`<br>`scripts/generate_05_notebook.py`<br>`src/inference.py` | `reports/inference_results.md`<br>`603bf56a57a5e6e42d580a5bed329d5c77794d9e5ed69d6f7e2e6864cc12661f` (`45,526 B`)<br>`figures/FIG-08.png`–`FIG-12.png` | • Daily panel (`≥18/24h`): `n=299 / 378` calendar days; `rho1=0.7276 => n_eff ≈ 47.1`.<br>• QCVN 24h exceedance (`>=50 µg/m³`): `84/299 = 28.09%`, `Holm p = 0.0250` (Confirmatory).<br>• Period mean `43.38 ± 21.68 µg/m³` vs `25 µg/m³` (`t=4.3535`, `Holm p = 7.38e-5`, Confirmatory).<br>• Weekend vs Weekday: median diff `-2.74 µg/m³`, `t(HAC)=1.611`, `Holm p = 0.1082` (No Confirmatory Difference).<br>• Season omnibus: `H = 61.5344`, `Holm p = 0.0560`, `ε² = 0.2065` (Downgraded to Exploratory per R5). |
| `data/processed/air_pollution_final.parquet` (`1.0.0`) & `air_pollution_extended_2022_2026.parquet` (`2.0.0`) | `notebooks/06_regression_modeling.ipynb`<br>`scripts/generate_06_notebook.py`<br>`src/regression.py` | `reports/regression_results.md`<br>`7dd79d8b1f...` (`54,906 B`)<br>`docs/regression_findings.md`<br>`figures/regression_line_diagnostics*.png` | • Protocol A single-station OLS Test $R^2$: **`-1.9540`** (`VN001_baseline`, 65% `month_sin` out-of-range), **`-0.1073`** (`VN001_extended_80_20`), **`+0.1498`** (`VN003_extended_2022_2025`); with `pm25_lag24`: `+0.2245`, `+0.0587`, `+0.3490`.<br>• All 4 LINE assumptions violated (`RESET p < 10⁻⁴⁸`, `DW = 0.208–0.303`, `JB p < 10⁻⁸⁵`, `BP p < 10⁻¹⁰⁴`).<br>• Max VIF `< 10` (`surface_pressure` `5.955–8.061`, `temperature` `5.730–7.655`); `wind_speed` HAC-24 $\beta \in [-7.29, -6.07]$ (*associational, ceteris paribus*). |
| `data/processed/air_pollution_final.parquet` (`1.0.0`) & `air_pollution_extended_2022_2026.parquet` (`2.0.0`) | `notebooks/07_classification_alerts.ipynb`<br>`scripts/generate_07_notebook.py`<br>`src/classification.py` | `reports/classification_results.md`<br>`80a15f6103...` (`55,914 B`)<br>`reports/classification_leakage_audit.md` (`a3c787d5a6...`, `6,748 B`)<br>`figures/precision_recall_curve*.png`, `feature_importance*.png`, `calibration_reliability*.png` | • Models: `LogisticRegression(class_weight='balanced')` & `RandomForestClassifier(class_weight='balanced')`, tuned for $F_2$ strictly on Train OOF.<br>• `VN001_baseline` (`2,302` Test, `28.93%` pos): `LogReg PR-AUC=0.9989 / Recall=99.55%`, `RF PR-AUC=0.9985 / Recall=100.00%` (`h=0` retrospective nowcast, 23/24h overlap; `h=24h` decay `0.7513 / 0.5876`).<br>• `VN003_extended`: `LogReg PR-AUC=0.9995 / Recall=99.77%`, `RF PR-AUC=0.9983 / Recall=99.30%`.<br>• `VN001_extended_80_20`: **`UNESTIMABLE`** (`0/242` positives after 630h outage). 4-layer leakage audit PASS. |
| `data/raw/openaq_raw_7441_2022_2025.parquet` (`57b6fbaa63...`) & `open_meteo_raw_2022-01-01_2025-04-09.json` (`303aacb687...`) | `scripts/build_extended_historical_dataset.py`<br>`scripts/run_extended_reanalysis.py` | `data/processed/air_pollution_extended_2022_2026.parquet`<br>`6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02` (`828,706 B`, `37,722 × 23`)<br>`reports/extended_*` | • `VN003` (`28,678` grid h, `18,208` valid `pm25`) + `VN001` (`9,044` grid h, `7,495` valid), `0h` overlap (`2,040h` gap, `7.324 km` apart).<br>• Baseline `VN001` SHA-256 unchanged (`baseline_immutability_verified: true`).<br>• Short-gap interpolation rejected (`1.85%–9.55%` recovery, future-endpoint $t+1$ leakage, winter RMSE up to `13.08 µg/m³`). |
| Baseline & Extended Parquet (`866f39de17...`, `6930557fbf...`) | `scripts/run_issue14_audit.py`<br>`src/ethics_audit.py` | `reports/data_scale_benchmark.md` (`3a9b7d2bac...`, `9,932 B`)<br>`reports/data_scale_benchmark.json` (`c95681262a...`, `4,377 B`)<br>`docs/bias_assessment.md`, `docs/model_card.md`, `docs/project_charter.md` | • Baseline: Parquet `0.2550 MB` vs CSV `1.8483 MB`, RAM `1.6820 -> 0.5263 MB` (`-68.71%`), Workload `235.65 -> 30.40 ms` (`7.75×`).<br>• Extended: Parquet `0.7903 MB` vs CSV `8.7952 MB`, RAM `9.3147 -> 2.7704 MB` (`-70.26%`), Workload `971.58 -> 66.69 ms` (`14.57×`).<br>• Total Parquet `1.0453 MB` (`<10 GB` tier); Spark rejected on measured evidence; `polars` not installed/unbenchmarked. |
| Baseline & Extended Parquet (`866f39de17...`, `6930557fbf...`) | `scripts/run_sensitivity_analysis.py`<br>`src/sensitivity.py` | `reports/sensitivity_analysis.md` (`66ff608303...`, `19,379 B`)<br>`reports/sensitivity_analysis.csv` (`d08556118c...`, `28,848 B`)<br>`docs/mentoring_feedback.md` | • Candidate technical thresholds `40, 45, 50, 55 µg/m³` (only `50.0` linked to QCVN 05:2023/BTNMT 24h), `min_periods` `{12,18,24}`, OLS lags `6/12/24/48h` & rolling `6/24/72h`, Train-tail `50/75/100%`, 4 seasons, Train-only derived interpolation (`+150` VN003 / `+117` VN001 Train rows, Test unchanged). |
| All verified M1–M5 docs/reports/figures | `scripts/build_final_report.py`<br>`scripts/build_defense_slides.py` | `reports/final_report.pdf` (`a56a59c8a5...`, `8,220,607 B`, 17 pages)<br>`reports/defense_slides.pdf` (`cc0e84d37f...`, `3,014,700 B`, 14 pages)<br>`docs/final_report_traceability.md` | • SCQA Vietnamese report & 14-slide defense deck pass 61 automated verbatim source-needle checks.<br>• Embed all 7 publication figures + extended/model diagnostic figures; zero causal-fallacy phrasing. |

---

## 3. Local (with `data/`) vs. CI (without `data/`) Test Environment Matrix

| Dimension | Local Environment (Full Real-Data Run) | CI Pipeline (`.github/workflows/ci.yml`) |
|---|---|---|
| **Dataset Availability (`data/`)** | **PRESENT** (`data/raw/`, `data/interim/`, `data/processed/`) | **ABSENT** (`data/` excluded by `.gitignore`) |
| **Command** | `py -3.14 -m unittest discover tests -v` | `python -m unittest discover tests -v` |
| **Defined Test Methods** | **836** | **836** |
| **Tests Reported as `Ran`** | **836** (`unittest_exit=0`, `0` skipped) | **808** (`836 − 28` in 5 skipped `setUpClass` classes) |
| **Expected Pass / Skip Counts** | **836 pass, 0 skip** | **804 pass, 9 skip** (`5` class holders + `4` in-`Ran` skips) |
| **CI-Only Limitations** | — | Cannot verify real-data F-test (`test_flag_evidence`), real W9 inference (`TestRealDataset`), real Issue #50 mutations (`TestSemanticMutations`), real OLS/LINE (`TestRegressionRealDataset`), real classification (`TestClassificationRealDataset`), live NB 04 on 9,044 rows, or Windows path invariants (`windows-paths` job covers `test_pipeline_runtime_log` separately). |

---

## 4. Notebook Execution Topology & Clean Execution Log

Prerequisite execution order (never re-run `03_data_cleaning.ipynb` against already-cleaned `data/interim/`; restore `data/interim/` from `data/raw/` first if re-running `02`→`03`):
`00_environment_test` → `01_data_collection` → `02_quality_audit` → `03_data_cleaning` → `03_transformation_pipeline` → `03_processed_data_preview` → `04_descriptive_stats` → `05_statistical_inference` → `06_regression_modeling` → `07_classification_alerts`.

Clean execution check via `py -3.14 -m jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 --output-dir "$env:TEMP\nb_audit_verify"` (preserving `TestNotebooksAreSerializationStable`):

| Notebook | Stage | Observed Wall Time | Exit Status |
|---|---|---:|:---:|
| `notebooks/00_environment_test.ipynb` | Environment & imports | `6.4s` | `0 (OK)` |
| `notebooks/04_descriptive_stats.ipynb` | EDA 4-family statistics (37 cells) | `9.8s` | `0 (OK)` |
| `notebooks/05_statistical_inference.ipynb` | W9 dependence-aware inference | `15.2s` | `0 (OK)` |
| `notebooks/06_regression_modeling.ipynb` | OLS/HAC/LINE/Ridge/Lasso | `111.5s` | `0 (OK)` |
| `notebooks/07_classification_alerts.ipynb` | Early-alert classification & leakage audit | `105.9s` | `0 (OK)` |
| **Total (5 notebooks)** | **Sequential clean execution** | **`248.8s`** | **`0 (All OK)`** |

---

## 5. Limitations, Provenance Caveats & Open PR Ledger

1. **Pending Open Pull Requests (`#59`–`#63`, plus superseded `#53`):**
   - Deliverables `docs/issue44_checkpoint_status.md` (PR `#59`), `docs/datasheet.md` (PR `#60`), `src/data_loader.py` & `tests/test_data_loader.py` (PR `#61`, doc conflicts only), `docs/viva_qa_prep.md` (PR `#62`), and `scripts/audit_defense_readiness.py` & `reports/defense_minutes.md` (PR `#63`) sit on open PR branches awaiting user review/merge and are intentionally left unmodified in this working tree.
2. **Issue #50 Parquet/ERA5 Snapshot Hash Difference (`validate_extended_reanalysis.py --real-data` exit 1 on `2/35`):**
   - Local disk contains the original Issue #44 snapshot (`6930557f...` extended Parquet, `303aacb6...` ERA5 JSON), matching `reports/issue44_extended_dataset_metadata.json`. `reports/extended_reanalysis_config.json` (committed by PR #52) stores a separate live-rebuild hash pair (`124c7fc8...`, `a0d841fc...`), causing `2/35` semantic hash checks to fail while all **603** structural checks and **33/35** semantic checks pass (`docs/issue50_reproducibility.md`).
3. **Raw `metadata.json` Checksum Provenance Warnings (`validate_issue8.py` 6 warnings):**
   - OpenAQ/Open-Meteo live re-fetches produce distinct byte-level Parquet/JSON hashes (`generationtime_ms` and PyArrow serialization differences), so `validate_issue8.py` flags raw hash mismatches as `WARN` while enforcing `MATCH`/`PASS` on `data/processed/air_pollution_final.parquet` or structural schema/count parity.
4. **`fog_mutual_information` (`0.0024`) Remains `UNVERIFIABLE`:**
   - Recorded transparently by `scripts/verify_claims.py` and `src/flag_evidence.py` (`0.0024` coincides under 7/8/10 quantile bins in `mutual_info_score`, vs `0.0081` `mutual_info_regression` and `0.0105` `mutual_info_classif`).
5. **Operational Boundaries:**
   - Open-Meteo ERA5 ~5-day reanalysis latency makes `h=0` classification a retrospective historical nowcast (`docs/model_card.md`).
   - `VN001_extended_80_20` Test has `0/242` positive 24h windows (`UNESTIMABLE`, retained honestly without fabrication).
   - `polars` and `pyspark` are not installed (`unbenchmarked`); Apache Spark rejection rests on measured single-node Parquet/CSV volume (`1.0453 MB` / `10.6435 MB`, >1,000× below the `10 GB` threshold).
