# Antigravity Agent Instructions – Air Pollution Analysis

> **Repository:** `doctor-cato/air-pollution-analysis`  
> **Course:** INFO3020 – Introduction to Data Science (CMC University)  
> **Instructor:** M.Sc. Pham Ngoc Dong  
> **Target Domain:** Time-series urban air quality ($\text{PM}_{2.5}$, $\text{PM}_{10}$) & meteorology (Hanoi, Vietnam)

---

## 1. Project Identity

This repository is an **academic data-science project**, not an enterprise distributed-data system or a commercial cloud microservice.
- **Goal:** Analyze multi-year temporal variations of urban fine particulate matter ($\text{PM}_{2.5}$), quantify meteorological drivers, and develop an interpretable early alert classification model following CRISP-DM methodology.
- **Dataset:** 2-year hourly series (2023–2024) integrating OpenAQ BAM 1020 reference monitor (US Embassy Hanoi) with Open-Meteo ERA5 surface weather ($\approx 17,500$ rows, $\approx 5 - 20\text{ MB}$).
- **Current State:** **Week 1 / Specification & Kickoff Stage**.
  - Authoritative requirements are in [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md).
  - An interactive landing page lives on branch `gh-pages` (`index.html`, `styles.css`, `script.js`).
  - Python scripts (`src/`), analysis notebooks (`notebooks/`), and processed data (`data/`) are planned specifications and **not yet written**.
  - **Roadmap vs. Reality:** [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md) defines requirements, not existing implementation. Never assume code or datasets exist without inspecting the filesystem.

---

## 2. Instruction Priority Hierarchy

When conflicts or ambiguities arise, strictly follow this precedence order:

1. **Explicit User Instruction:** Direct commands given in the current user prompt.
2. **Actual Repository State:** Files, code, and configurations that actually exist on disk.
3. **Applicable `.agents/` Rules:** Non-negotiable domain rules in [`.agents/rules/`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/).
4. **Project Roadmap:** Academic specifications in [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md).
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
| **Modifying Raw Data** | Treat `data/raw/` as read-only. Never edit raw CSV/JSON files or open them in Excel. |
| **Row Explosion on Joins** | Check timestamp uniqueness and assert `len(df_merged) <= len(df_air)` on all joins. |
| **Temporal Data Leakage** | Enforce chronological train/test splits (e.g. 2023 vs 2024). Random splitting is strictly prohibited. |
| **Preprocessing Leakage** | Fit transformers (Scalers, Imputers) strictly on the training partition inside a `Pipeline`. |
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
5. **Documentation:** [`docs/cleaning_log.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/cleaning_log.md) or [`README.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/README.md) is updated if logic or assumptions changed.
6. **Clean Diff:** `git diff` contains zero unintended modifications, leftover debug code, or secrets.
7. **Evidence-Based Summary:** Response provides exact commands executed, observed outputs, and verified metrics.

---

## 8. Directory & Navigation Index

- **Rules:**
  - Project & Engineering Standards: [`.agents/rules/project.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/project.md)
  - Data Governance & Safety: [`.agents/rules/data.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/data.md)
  - Analytical & Statistical Integrity: [`.agents/rules/analysis.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/analysis.md)
  - Notebook Reproducibility: [`.agents/rules/notebooks.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/notebooks.md)
  - Git Hygiene & Guardrails: [`.agents/rules/git.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/git.md)
- **Workflows:**
  - Feature Development: [`.agents/workflows/feature.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/workflows/feature.md)
  - Data Pipeline Lifecycle: [`.agents/workflows/data-pipeline.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/workflows/data-pipeline.md)
  - Notebook Authoring: [`.agents/workflows/notebook.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/workflows/notebook.md)
  - Pre-Completion Verification: [`.agents/workflows/verification.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/workflows/verification.md)
- **Skills:**
  - Data Quality Audit: [`.agents/skills/data-quality/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/data-quality/SKILL.md)
  - Exploratory Data Analysis: [`.agents/skills/exploratory-analysis/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/exploratory-analysis/SKILL.md)
  - Time-Series Analysis: [`.agents/skills/time-series-analysis/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/time-series-analysis/SKILL.md)
  - Statistical Analysis & Inference: [`.agents/skills/statistical-analysis/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/statistical-analysis/SKILL.md)
  - Regression Modeling: [`.agents/skills/regression/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/regression/SKILL.md)
  - Classification & Alerts: [`.agents/skills/classification/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/classification/SKILL.md)
  - Data Visualization: [`.agents/skills/data-visualization/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/data-visualization/SKILL.md)
  - Research Documentation: [`.agents/skills/research-documentation/SKILL.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/research-documentation/SKILL.md)
