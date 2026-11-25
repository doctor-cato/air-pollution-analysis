# Project Charter — Time-Series Air Pollution Analysis ($\text{PM}_{2.5}$ in Hanoi, Vietnam)

> **Course:** INFO3020 – Introduction to Data Science (*Nhập môn Khoa học Dữ liệu*)
> **Institution:** Faculty of Information & Communication Technology, CMC University
> **Instructor:** M.Sc. Pham Ngoc Dong (*ThS. Phạm Ngọc Đông*)
> **Methodology:** CRISP-DM (6 Phases, Weeks 01–15)
> **Repository:** [`doctor-cato/air-pollution-analysis`](https://github.com/doctor-cato/air-pollution-analysis)
> **Deliverable Owner:** Issue #14 (Milestone 5 — Week 12)

---

## 1. Project Identity & Team Roster

| No. | Member | GitHub Account | Role | Core Responsibilities |
|:---:|---|---|---|---|
| 1 | **Huy** | [@doctor-cato](https://github.com/doctor-cato) | Team Leader (*Nhóm trưởng*) | Architecture, CI/testing governance, pipeline integration, statistical & modeling verification, final sign-off |
| 2 | **Khương** | [@lekhuong123456798-cpu](https://github.com/lekhuong123456798-cpu) | Team Member | Data collection, quality audit, EDA & visualization support |
| 3 | **Khánh** | [@nguyenphanminhkhanh9a-netizen](https://github.com/nguyenphanminhkhanh9a-netizen) | Team Member | Deterministic cleaning, statistical inference & reporting |
| 4 | **Hưng** | [@ViolaPeracia](https://github.com/ViolaPeracia) | Team Member | Regression/classification experiments, sensitivity analysis & documentation |
| 5 | **Hùng** | [@Izuki-1780N](https://github.com/Izuki-1780N) | Team Member | Documentation, ethics/bias audit support, slide deck & Viva preparation |

---

## 2. Problem Statement & CRISP-DM Scope

### 2.1. Problem Statement & Research Questions
Urban fine particulate matter ($\text{PM}_{2.5}$) in Hanoi exhibits severe seasonal episodes that pose acute and chronic public health risks. This academic data science project analyzes multi-year hourly $\text{PM}_{2.5}$ observations paired with surface meteorology to answer one main research question and four supporting sub-questions ([`docs/research_questions.md`](research_questions.md)):

- **Main Research Question:** *How does $\text{PM}_{2.5}$ concentration in Hanoi vary across temporal cycles, how is it associated with surface meteorological factors, and how can an interpretable early-alert classification model be built on time-series data without data leakage?*
- **SQ1 (Distribution & Measurement):** What are the skewness and tail properties of empirical $\text{PM}_{2.5}$, and which descriptive statistics (Median/IQR vs. Mean/SD) best represent typical exposure?
- **SQ2 (Temporal Cycles & Inference):** Do $\text{PM}_{2.5}$ levels differ significantly across seasons and weekday/weekend periods, and how do daily/period averages compare against QCVN 05:2023/BTNMT ($50\,\mu\text{g/m}^3$ 24h; $25\,\mu\text{g/m}^3$ annual) after accounting for temporal autocorrelation?
- **SQ3 (Explanatory Regression):** How are surface meteorological variables associated with hourly $\text{PM}_{2.5}$ (*ceteris paribus*) under OLS/Ridge/Lasso, and do residuals satisfy the 4 LINE assumptions?
- **SQ4 (Early-Alert Classification):** How can class imbalance and decision thresholds ($F_2$ / constrained Recall) be optimized to detect 24h QCVN exceedance episodes ($\ge 50\,\mu\text{g/m}^3$) while preventing all 4 forms of time-series leakage?

### 2.2. In-Scope Deliverables (CRISP-DM 6 Phases)
1. **Business & Domain Understanding:** Research questions, Canonical Schema, QCVN 05:2023/BTNMT & WHO 2021 alignment.
2. **Data Understanding:** Multi-source profiling gate (Issue #19), 6-dimension quality audit (Issue #5), 4-family descriptive statistics (Issue #8), and 7 publication-grade Tufte/Cleveland figures (`FIG-01`–`FIG-07`, Issue #9).
3. **Data Preparation:** Deterministic cleaning with `assert_no_imputation()` (Issue #6), leakage-safe `merge_air_weather()`, chronological Train/Test split, `sklearn.pipeline.Pipeline` fit strictly on Train (Issue #7), and station-separated historical expansion (`VN003`, Issues #44 & #50).
4. **Modeling:** Dependence-aware statistical inference with calendar block bootstrap, HAC Newey-West, Holm-Bonferroni, and Monte Carlo validation (Issue #11); OLS/Ridge/Lasso with LINE diagnostics and VIF (Issue #12); Logistic Regression & Random Forest early-alert classifiers with calibration, ablation, and 4-layer leakage audit (Issue #13).
5. **Evaluation & Governance:** Empirical Data Scale Benchmark vs. Apache Spark, 4-hypothesis Ethics & Bias Audit, Datasheet for Dataset, 1-page Model Card, and Project Charter (Issue #14); sensitivity analysis & refactoring (Issue #15).
6. **Deployment / Academic Handoff:** Final SCQA Capstone Report, defense slide deck, Viva Q&A preparation, full repository audit, and `final-defense-submission` release tag (Issues #16–#17).

### 2.3. Explicit Out-of-Scope Exclusions
- ❌ **Distributed Big Data Frameworks (Apache Spark / Hadoop):** Excluded based on empirical benchmark evidence (`reports/data_scale_benchmark.md`: total Parquet volume $< 3\text{ MB}$, well below the W12 $> 100\text{ GB}$ threshold).
- ❌ **Black-Box Deep Learning (LSTM / GRU / Transformers):** Excluded to preserve statistical interpretability, assumption auditability, and alignment with INFO3020 core curriculum.
- ❌ **Randomized Controlled Trials (RCT / A/B Testing):** Physically infeasible for urban meteorology; the study is strictly **observational** (zero causal claims).
- ❌ **PII Anonymization ($k$-anonymity / Differential Privacy):** Public environmental monitoring stations contain no Personally Identifiable Information (PII).
- ❌ **Live Real-Time Operational Forecasting:** Open-Meteo ERA5 reanalysis has a ~5-day publication latency; $h=0$ classification is explicitly framed as a retrospective historical nowcast unless paired with live NWP forecasts.

---

## 3. Milestones & 15-Week Schedule (M1–M6)

*Aligned with authoritative [`docs/roadmap.md`](roadmap.md):*

| Milestone | Weeks | Issues | Key Deliverables | Status |
|---|:---:|---|---|---|
| **M1 — Setup, Schema & Source Gate** | W01–W02 | #1, #2, #19, #3, #4 | CRISP-DM repo, Canonical Schema (`docs/data_dictionary.md`), Source Decision Gate (`docs/source_profiling_decision.md`), OpenAQ & Open-Meteo adapters (`src/data_collection.py`) | **Completed** |
| **M2 — Quality, Cleaning & Pipeline** | W03–W05 | #5, #6, #7, #38 | 6-dimension audit (`src/data_quality.py`), deterministic cleaning (`src/cleaning.py`, `docs/cleaning_log.md`), leak-safe pipeline (`src/cleaning_pipeline.py`), fog-flag evidence (`src/flag_evidence.py`) | **Completed** |
| **M3 — EDA & Publication Figures** | W06–W08 | #8, #9 | 4-family descriptive stats (`notebooks/04_descriptive_stats.ipynb`, `reports/statistical_profile.csv`), 7 publication figures (`figures/FIG-01..07.png`, `src/visualizer.py`) | **Completed** |
| **Historical Expansion & Reanalysis** | — | #44, #50 | Station-separated `VN003` (2022–2025) expansion (`src/issue44_preparation.py`), extended audit & validation (`src/extended_audit.py`, `src/reanalysis_validation.py`) | **Completed** |
| **M4 — Inference, Regression & Classification** | W09–W11 | #11, #12, #13 (#10 closed) | W9 dependence-aware inference (`src/inference.py`), W10 OLS/LINE/Ridge/Lasso (`src/regression.py`), W11 classification & 4-layer leakage audit (`src/classification.py`) | **Completed** |
| **M5 — Ethics, Scale, Refactor & Final Report** | W12–W14 | #14, #15, #16 | Data Scale Benchmark vs. Spark, 4-hypothesis Bias Audit, Datasheet, Model Card, Project Charter (#14); threshold sensitivity & mentoring log (#15); Final SCQA Report & Viva prep (#16) | **In Progress** |
| **M6 — Final Defense & Handoff** | W15 | #17 | Full technical repo audit, clean-kernel notebook verification, defense minutes, `final-defense-submission` tag | **Planned** |

---

## 4. Data Provenance & Three-Tier Raw Data Policy

### 4.1. Approved Data Sources & Station Separation (Protocol A)
| Dataset / Station | Source & Location ID | Period | License | Role |
|---|---|---|---|---|
| `VN001_HANOI_556_NGUYEN_VAN_CU` | OpenAQ S3 (`location_id=4946811`) | 07/2025–07/2026 (9,044 grid h; 7,495 valid) | ODC-BY v1.0 | Primary baseline (`1.0.0-m2-baseline`) |
| `VN003_HANOI_OPENAQ_7441` | OpenAQ S3 (`location_id=7441`, AirNow Gov Monitor) | 01/2022–04/2025 (28,678 grid h; 18,208 valid) | US Public Domain | Station-separated historical expansion (`2.0.0-issue44-extended`) |
| `ERA5_HANOI_GRID_2105_10590` | Open-Meteo Historical Weather API (ECMWF ERA5) | 01/2022–07/2026 (hourly, 0% missing) | CC BY 4.0 | Surface meteorology (retrospective ~5d latency) |
| `VN002_HANOI_US_EMBASSY` | AirNow DOS Historical CSV | Historical fallback | US Public Domain | Fallback adapter only; GitHub mirror rejected (`NO-GO`, Issue #44) |

- **Protocol A Discipline:** Because `VN003` and `VN001` have **0 overlapping hours** (2,040-hour gap, 7.324 km spatial separation), cross-station pooling (Protocol B) is strictly prohibited in all inference and modeling pipelines.

### 4.2. Three-Tier Raw Data Policy (`docs/roadmap.md` §3.2)
- **Tier A (Runtime Acquisition & Persistence):** Raw API payloads are written unmodified under `data/raw/` during pipeline execution.
- **Tier B (Integrity & Provenance Verification):** Every raw payload is hashed (SHA-256) and cataloged with query parameters, retrieval date, and license in `data/raw/metadata.json`; deterministic cleaning never mutates `data/raw/`.
- **Tier C (Version Control & Reproducibility):** Raw and processed payloads in `data/` are excluded from Git via `.gitignore` and reproduced on demand via `python scripts/fetch_dataset.py` and `python scripts/build_extended_historical_dataset.py` (no API key required).

---

## 5. Risk Register

| Risk | Likelihood | Impact | Mitigation Strategy | Contingency / Backup Plan |
|---|:---:|:---:|---|---|
| **1. API rate limits or schema drift** | Medium | High | Throttled chunked requests (`time.sleep()`), raw caching, isolated source adapters (`src/data_collection.py`) | Switch to pre-approved fallback adapter (`AirNowDOSAdapter`) per Issue #19 matrix |
| **2. Clustered missingness / sensor outages** | High | High | Preserve `NaN` (`assert_no_imputation()`), report coverage by `(station, year, season)`, use calendar block bootstrap | Mark degenerate splits explicitly as `UNESTIMABLE` (e.g., `VN001_extended_80_20` Test) |
| **3. Timezone misalignment (AQ vs. Weather)** | Medium | Critical | Enforce timezone-aware `Asia/Ho_Chi_Minh` (UTC+7) in all adapters and assert diurnal temperature peak | Fail-closed validation in `merge_air_weather()` if all weather columns become `NaN` |
| **4. Row explosion on table joins** | Low | Critical | Enforce unique keys + `validate="1:1"` + `assert len(merged) == len(df_air)` in `src/cleaning_pipeline.py` | Halt pipeline immediately on key duplication |
| **5. OLS LINE assumption violations** | High | Medium | Run Ramsey RESET, DW/ACF, Jarque-Bera, Breusch-Pagan, VIF, Cook's $D$; apply HAC-24 SE & Ridge/Lasso | Report violations transparently; restrict OLS to non-causal descriptive associations |
| **6. Time-series data leakage** | Medium | Critical | Strict chronological split, Train-only `Pipeline`, purge gap for $h>0$, Protocol A single-station lock | Independent 4-layer audit (`docs/leakage_audit.md`) + automated unit tests |
| **7. Over-engineering (Spark / Deep Learning)** | Medium | High | Ground architecture decisions in empirical benchmark (`reports/data_scale_benchmark.md`) | Retain single-node Pandas + Parquet + `statsmodels`/`scikit-learn` stack |

---

## 6. CLO4 Academic Integrity & AI Governance

This project strictly adheres to **CMC University CLO4 Academic Integrity Standards**:
1. **Zero Fabrication:** Every count, $p$-value, effect size, regression coefficient, classification score, and resource benchmark is computed from real verified data and reproducible code — never fabricated or cherry-picked.
2. **Transparent Limitations:** All assumption violations (OLS LINE), non-estimable splits (`UNESTIMABLE`), autocorrelation caveats ($n_{\text{eff}}$), and ERA5 latency limits are disclosed prominently.
3. **Deterministic Reproducibility:** Fixed `random_state=42`, automated unit test suite (`docs/TEST_SUITE.md`), serialization-stable notebooks, and clean-kernel execution (`Restart Kernel & Run All`).
4. **AI Usage Declaration (`README.md` §7):** AI assistants (Google Gemini / Antigravity, GitHub Copilot) are used solely for code scaffolding, test drafting, and documentation formatting; **100% of statistical reasoning, leakage controls, experimental verification, and oral Viva defense are owned and executed by the student team**.
