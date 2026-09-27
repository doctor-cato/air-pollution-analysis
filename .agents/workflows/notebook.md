# Notebook Authoring & Verification Workflow

> **Purpose:** Standard procedure for creating, modifying, and certifying Jupyter notebooks.

---

## 1. Notebook Workflow Sequence

```text
Inspect notebook (check structure, imports, and execution order)
       │
       ▼
Identify current analysis (map to roadmap milestone: EDA, inference, regression, alert)
       │
       ▼
Load applicable rules (notebooks.md, analysis.md, project.md)
       │
       ▼
Load applicable skills (exploratory-analysis, regression, classification, etc.)
       │
       ▼
Modify minimally (atomic cell edits, move heavy logic to src/)
       │
       ▼
Execute (run affected cells, ensure no unhandled errors)
       │
       ▼
Inspect outputs (examine generated plots, summary tables, metrics)
       │
       ▼
Validate reproducibility (run "Kernel -> Restart & Run All" from top to bottom)
       │
       ▼
Review diff (git diff check, scrub oversized raw printouts before saving)
```

---

## 2. Detailed Execution Steps

### Step 1: Inspect Notebook
- Check if the notebook exists in `notebooks/` (`01_` through `06_`).
- Review current cell outputs, imports, and structure.

### Step 2: Identify Current Analysis
- Cross-reference the notebook with the relevant milestone in [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md):
  - `01_data_collection.ipynb` $\to$ Milestone 1 (API ingestion)
  - `02_quality_audit_cleaning.ipynb` $\to$ Milestone 2 (Quality audit, imputation, pipeline)
  - `03_exploratory_data_analysis.ipynb` $\to$ Milestone 3 (4 families of stats, 7 headline charts)
  - `04_statistical_inference.ipynb` $\to$ Milestone 4 (Mann-Whitney U, Bootstrap CI, Effect size)
  - `05_regression_modeling.ipynb` $\to$ Milestone 4 (OLS, LINE diagnostics, VIF, Cook's dist)
  - `06_classification_alerts.ipynb` $\to$ Milestone 4 (Random Forest, Recall & PR-AUC, Threshold)

### Step 3: Load Governing Rules & Skills
- Review [`notebooks.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/notebooks.md) and [`analysis.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/analysis.md).
- Activate corresponding skills (e.g. [`data-visualization`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/data-visualization/SKILL.md) for plotting).

### Step 4: Make Minimal, Focused Modifications
- Keep cell changes targeted. Do not rewrite functioning cells unnecessarily.
- Set deterministic seeds: `random_state=42`.
- Extract reusable functions $> 30$ lines into `src/` modules.

### Step 5: Execute & Inspect Outputs
- Run the modified cells and verify:
  - Tables display correct summary metrics.
  - Plots include units, honest axes (bar charts starting at 0), and conclusion-driven titles.
  - Test statistics include the mandatory trio ($p$-val, Effect size, 95% CI).
  - Regression reports baseline comparison and LINE diagnostic plots.
  - Classification reports Recall and PR-AUC.

### Step 6: Validate Reproducibility (Clean Kernel Certification)
- Execute **Kernel $\to$ Restart & Run All**.
- Verify that every cell finishes with sequential execution numbers and zero tracebacks.

### Step 7: Review Diff & Scrub Output Bloat
- Clear any accidental giant data dumps (e.g. printing 10,000 JSON rows).
- Inspect `git diff path/to/notebook.ipynb` to ensure clean, intended edits.
