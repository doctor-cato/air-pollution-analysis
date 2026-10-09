# Antigravity Agent Instructions – Air Pollution Analysis

> **Repository:** `doctor-cato/air-pollution-analysis`  
> **Course:** INFO3020 – Introduction to Data Science (CMC University)  
> **Instructor:** M.Sc. Pham Ngoc Dong  
> **Target Domain:** Time-series urban air quality ($\text{PM}_{2.5}$, $\text{PM}_{10}$) & meteorology (Hanoi, Vietnam)

---

## 1. Project Identity

This repository is an **academic data-science project**, not an enterprise distributed-data system or a commercial cloud microservice.
- **Goal:** Analyze multi-year temporal variations of urban fine particulate matter ($\text{PM}_{2.5}$), quantify meteorological drivers, and develop an interpretable early alert classification model following CRISP-DM methodology.
- **Dataset:** Time series integrating OpenAQ NCEM/VEA station 4946811 (556 Nguyễn Văn Cừ, Hanoi; 07/2025–07/2026) with Open-Meteo ERA5 surface weather dynamically synchronized (8,022 air records, 9,072 weather records, 100% temporal overlap). AirNow DOS Hanoi serves as historical fallback.
- **Current State:** **Milestone 2 (Week 05)** — Issues #6 and #7 implemented; modelling Issues #11–#13 not started.
  - Authoritative requirements are in [`docs/roadmap.md`](../docs/roadmap.md).
  - An interactive landing page lives on branch `gh-pages` (`index.html`, `styles.css`, `script.js`).
  - **Implemented:** `src/data_collection.py`, `src/data_quality.py` (6-dimension audit, Issue #3), `src/cleaning.py` (deterministic cleaning, Issue #6), `src/cleaning_pipeline.py` (leakage-safe preprocessing, Issue #7), `scripts/fetch_dataset.py`, the CI workflow (`.github/workflows/ci.yml`), and notebooks `00`–`03`.
  - **Not yet implemented:** notebooks `04`–`06` (modelling & evaluation, Issues #11–#13). Everything under `data/processed/` is a gitignored artifact that notebook `03` regenerates.
  - **Roadmap vs. Reality:** Always inspect the filesystem to verify what exists versus what is planned.

---

## 2. Instruction Priority Hierarchy

When conflicts or ambiguities arise, strictly follow this precedence order:

1. **Explicit User Instruction:** Direct commands given in the current user prompt.
2. **Actual Repository State:** Files, code, and configurations that actually exist on disk.
3. **Applicable `.agents/` Rules:** Non-negotiable domain rules in [`.agents/rules/`](rules).
4. **Project Roadmap:** Academic specifications in [`docs/roadmap.md`](../docs/roadmap.md).
5. **Existing Project Conventions:** Existing naming, code style, and directory layout.
6. **General Engineering Conventions:** Industry standard Python/Data Science best practices.

*Rule:* Never claim roadmap functionality exists unless the repository actually implements it on disk.

---

## 3. Core Principles

- **Inspect before editing:** Check `git status`, branch name, and filesystem before touching code.
- **Understand existing code:** Read existing modules before adding or modifying code; avoid duplicating logic.
- **Prefer minimal changes:** Implement the smallest coherent change that satisfies the requirement.
- **Preserve reproducibility:** Use deterministic random seeds (`random_state=42`), clean pipelines, and sequential notebooks.
- **Preserve data provenance:** Record source APIs, query parameters, retrieval dates, and schema versions in `data/raw/metadata.json`.
- **Avoid unnecessary dependencies:** Rely on standard `pip` and core scientific libraries (`pandas`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`, `matplotlib`, `seaborn`). No Spark, no Deep Learning, no dev bloat.
- **Verify changes:** Run scripts, test assertions, execute clean kernels, and inspect generated tables/plots before claiming completion.
- **Review diffs:** Review `git diff` to ensure zero unintended changes or committed secrets.
- **Report limitations honestly:** State statistical assumptions, potential biases, and model limitations transparently.

---

## 4. Academic Integrity

Agents must strictly uphold academic honesty (CLO4 & CMC University standards):

- 🚫 **Never fabricate data:** Never create mock, synthetic, or fake pollution/weather values to fill gaps.
- 🚫 **Never fabricate metrics:** Never invent $R^2$, MAE, RMSE, Recall, Precision, or PR-AUC scores.
- 🚫 **Never fabricate statistical significance:** Never invent or alter $p$-values, effect sizes, or confidence intervals.
- 🚫 **Never fabricate model results:** Report actual outputs from model evaluation on the independent test set.
- 🚫 **Never fabricate sources:** Only cite verified data sources (OpenAQ, Open-Meteo, QCVN 05:2023/BTNMT, WHO 2021).
- 🚫 **Never claim an experiment was executed when it was not:** Run the code and provide concrete output evidence.
- 🚫 **Never alter analysis merely to obtain a desired result:** If an assumption is violated or hypothesis rejected, report it truthfully.

---

## 5. Antigravity Failure Modes to Prevent

Agents working in Antigravity must explicitly avoid these known failure modes:

| Failure Mode | Prevention Rule |
|---|---|
| **Hallucinated Files/Modules** | Inspect directory tree before importing or referencing any file. |
| **Treating Roadmap as Implemented** | Check file existence before assuming a feature or notebook is present. |
| **Modifying Raw Data** | Apply Three-tier Raw Data Policy (roadmap §3.2). Preserve raw payloads in `data/raw/` unchanged, track SHA-256 in `metadata.json`, never edit manually. |
| **Row Explosion on Joins** | Use `src/cleaning_pipeline.py::merge_air_weather()`. It rejects non-unique keys and colliding column names, asserts `len(df_merged) == len(df_air)` (**`==`, not `<=`** — with `how="left"` + unique keys + `validate="1:1"` the `<=` form is a tautology that can never fire), and raises when **every** joined weather column is `NaN` (the check that actually catches a timezone/window mismatch). |
| **Temporal Data Leakage** | Enforce chronological train/test splits (e.g. chronological split on study period). Random splitting is strictly prohibited. Since the M2 audit the chronology layer is **mandatory, not opt-in**: `verify_chronology()` raises if `timestamps` / `test_timestamps` are not supplied. Opting out requires the explicit `verify_chronology=False` and still emits a warning — a guard that can silently disable itself is not a guard. |
| **Preprocessing Leakage** | Fit transformers (Scalers, Imputers) strictly on the training partition inside a `Pipeline`, then prove it with `validate_no_leakage()` — it compares every learned parameter against a Train refit, checks `train.max() < test.min()`, **and** checks chronology (mandatory since the M2 audit; see the Temporal Data Leakage row). |
| **Target In The Feature Set** | Never put `pm25` in `X`; `build_preprocessing_pipeline()` raises `ValueError` if you try. Never put a target-derived flag (`pm25_was_missing` = `pm25.isna()`) in `X` either — `SimpleImputer` fills exactly those rows with the median, so every flagged row's target equals the median (100% on the real data). That leak is structural and **no parameter-level guard can detect it**; it must be excluded at the feature-list level. Separately, exclude flags that merely have **no demonstrated marginal predictive value** (`NON_PREDICTIVE_FLAGS`, currently `is_high_humidity_fog`: `corr(pm25, RH) = -0,037`, mutual information 0,0024 — the lowest of the meteorological variables). Keep the two groups disjoint: they look similar but call for different reasoning, and conflating them makes every exclusion look like a leakage catch. Caveat worth keeping: `is_high_humidity_fog` **does** interact with season (Đông +2,79; Xuân −8,91 µg/m³; joint F-test p = 7,4·10⁻¹¹), so the near-zero correlation is an artefact of averaging over seasons, not proof of independence. Exploiting that requires an explicit `fog × season` interaction term — an EDA decision (Issue #8), not a default feature. Diagnostic flags stay **in the dataset** either way. |
| **Interpolation vs. Observation** | Never impute, under any missingness mechanism. `assert_no_imputation()` compares cell by cell and rejects any invented value. See `.agents/rules/data.md` §3.5 and §5 — the old "safe to interpolate ≤ 2h" wording in §5 was withdrawn on 2026-09-30. |
| **Unjustified Outlier Deletion** | Never delete extreme pollution episodes (winter inversions, fireworks) merely because they look high. |
| **Silent Unit/Threshold Changes** | Maintain $\mu\text{g/m}^3$ and local time `Asia/Ho_Chi_Minh` (UTC+7). Document all thresholds. |
| **Accuracy Trap on Imbalance** | Never use Accuracy alone for binary alert evaluation. Prioritize Recall and PR-AUC. |
| **Causal Fallacy in Regression** | Interpret $\beta$ coefficients as observational associations under *ceteris paribus*, never causal effects. |
| **Unverified Success Claims** | Run runtime verification and inspect `git diff` before declaring a task done. |
| **Automatic Git Commits/Pushes** | Never run `git commit` or `git push` unless explicitly commanded by the user. |

---

## 6. Skill Selection Matrix

Antigravity agents must load only the skills relevant to the specific task:

```text
Task Domain                          Primary Skill                  Supporting Skill(s)
─────────────────────────────────────────────────────────────────────────────────────────────
Data collection & ingestion          data-quality                   research-documentation
Data audit & cleaning                data-quality                   time-series-analysis
Exploratory analysis (EDA)           exploratory-analysis           data-visualization
Time-series & temporal patterns      time-series-analysis           exploratory-analysis
Statistical inference & tests        statistical-analysis           data-visualization
Regression modeling (OLS/LINE)       regression                     statistical-analysis
Classification & alerts              classification                 statistical-analysis
Publication charting (Tufte)         data-visualization             exploratory-analysis
Datasheets, Model Cards, Reports     research-documentation         -
```

Do not load all skills simultaneously. Select only what the current task demands.

---

## 7. Definition of Done (DoD)

A task is complete **only** when all of the following criteria are satisfied:

1. **Implementation:** Code is written cleanly, modularized in `src/` where appropriate, and adheres to PEP 8.
2. **Runtime Verification:** Scripts or notebooks have been executed, and data assertions pass without error.
3. **Clean Kernel Certification:** Any modified notebook executes completely via **Restart Kernel & Run All**.
4. **Artifact Integrity:** Generated outputs (`.parquet`, figures in `figures/`, markdown reports) exist and are non-empty.
5. **Documentation:** [`docs/cleaning_log.md`](../docs/cleaning_log.md) or [`README.md`](../README.md) is updated if logic or assumptions changed.
6. **Clean Diff:** `git diff` contains zero unintended modifications, leftover debug code, or secrets.
7. **Evidence-Based Summary:** Response provides exact commands executed, observed outputs, and verified metrics.

---

## 8. Directory & Navigation Index

- **Rules:**
  - Project & Engineering Standards: [`.agents/rules/project.md`](rules/project.md)
  - Data Governance & Safety: [`.agents/rules/data.md`](rules/data.md)
  - Analytical & Statistical Integrity: [`.agents/rules/analysis.md`](rules/analysis.md)
  - Notebook Reproducibility: [`.agents/rules/notebooks.md`](rules/notebooks.md)
  - Git Hygiene & Guardrails: [`.agents/rules/git.md`](rules/git.md)
- **Workflows:**
  - Feature Development: [`.agents/workflows/feature.md`](workflows/feature.md)
  - Data Pipeline Lifecycle: [`.agents/workflows/data-pipeline.md`](workflows/data-pipeline.md)
  - Notebook Authoring: [`.agents/workflows/notebook.md`](workflows/notebook.md)
  - Pre-Completion Verification: [`.agents/workflows/verification.md`](workflows/verification.md)
- **Skills:**
  - Data Quality Audit: [`.agents/skills/data-quality/SKILL.md`](skills/data-quality/SKILL.md)
  - Exploratory Data Analysis: [`.agents/skills/exploratory-analysis/SKILL.md`](skills/exploratory-analysis/SKILL.md)
  - Time-Series Analysis: [`.agents/skills/time-series-analysis/SKILL.md`](skills/time-series-analysis/SKILL.md)
  - Statistical Analysis & Inference: [`.agents/skills/statistical-analysis/SKILL.md`](skills/statistical-analysis/SKILL.md)
  - Regression Modeling: [`.agents/skills/regression/SKILL.md`](skills/regression/SKILL.md)
  - Classification & Alerts: [`.agents/skills/classification/SKILL.md`](skills/classification/SKILL.md)
  - Data Visualization: [`.agents/skills/data-visualization/SKILL.md`](skills/data-visualization/SKILL.md)
  - Research Documentation: [`.agents/skills/research-documentation/SKILL.md`](skills/research-documentation/SKILL.md)
