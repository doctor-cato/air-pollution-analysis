# Jupyter Notebook Rules & Standards

> **Scope:** Notebook development, reproducibility, output handling, and refactoring.  
> **Source Document:** [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md) (Sections 12.2 & 13.E).

---

## 1. Planned Notebook Architecture

Notebooks are organized sequentially in `notebooks/` matching the project milestone progression:

| Notebook | Focus & Contents | Upstream Input | Primary Output |
|---|---|---|---|
| `01_data_collection.ipynb` | API fetching & raw serialization | External APIs | `data/raw/*.json`, `metadata.json` |
| `02_quality_audit_cleaning.ipynb` | 6 dimensions audit, physical rules, imputation | `data/raw/` | `data/processed/air_pollution_final.parquet`, `docs/cleaning_log.md` |
| `03_exploratory_data_analysis.ipynb` | 4-family stats, diurnal/seasonal EDA, 7 charts | `data/processed/` | `figures/FIG-01` to `FIG-07.png`, `reports/statistical_profile.csv` |
| `04_statistical_inference.ipynb` | Non-parametric tests, effect sizes, Bootstrap CI | `data/processed/` | `reports/inference_results.md` |
| `05_regression_modeling.ipynb` | OLS regression, LINE diagnostics, VIF, Cook's dist | `data/processed/` | Regression tables, diagnostic plots |
| `06_classification_alerts.ipynb` | Imbalanced classification, PR-AUC, Threshold tuning | `data/processed/` | Model comparison tables, PR curves |

---

## 2. Core Execution & Reproducibility Rules

1. **Clean Kernel Standard:**
   - Any completed notebook must run completely from top to bottom via **Kernel $\to$ Restart & Run All** with zero errors or manual cell jumps.
2. **Deterministic State:**
   - Set fixed seeds (`random_state=42`) at the top of the notebook.
   - Cells must execute in linear sequential order ($1, 2, 3, \dots$).
   - Never rely on variables defined out-of-order, in deleted cells, or from previous sessions.
3. **Structured Cell Layout:**
   - **Cell 1:** Markdown title, metadata, purpose of the notebook, and prerequisite inputs.
   - **Cell 2:** All library imports and environment configuration (`warnings`, `matplotlib` settings).
   - **Cell 3:** Fixed constants, file paths (`pathlib.Path`), and random seeds.
   - **Subsequent Cells:** Modular analysis sections partitioned by clear Markdown headers (e.g. `## 1. Data Loading`, `## 2. Physical Bounds Check`).
4. **No Heavy Duplicated Code:**
   - Functions longer than 30 lines or logic reused across two or more notebooks must be extracted into `src/` modules.
   - Import functions cleanly: `from src.visualizer import plot_tufte_timeseries`.

---

## 3. Output Management & Figure Generation

1. **Avoid Committing Bloated Outputs:**
   - Strip giant, uncompressed outputs (e.g. printing thousands of raw JSON lines or multi-megabyte dataframes) before saving.
   - Notebooks should show concise data summaries (`.info()`, `.head(5)`, `.describe()`) and clean visual plots.
2. **Figure Export Protocol:**
   - Never rely solely on inline cell rendering for final report visuals.
   - Export all publication-quality figures directly to `figures/` in 300 DPI PNG format:
     ```python
     fig.savefig(
         "../figures/fig01_timeseries_overview.png",
         dpi=300,
         bbox_inches='tight'
     )
     ```
3. **No Silent Re-Execution of Expensive Tasks:**
   - If a computation is computationally demanding (e.g., 10,000 bootstrap resamples or grid searches), cache the intermediate result or print structured execution progress.

---

## 4. Protocol for Modifying Notebooks

When updating or fixing an existing notebook, follow this 5-step checklist:

1. **Audit Upstream Assumptions:** Check which data files or schema versions the notebook expects.
2. **Identify Downstream Dependents:** Determine if modifying a dataframe or column name will break downstream notebooks.
3. **Make Atomic Changes:** Keep cell edits minimal and targeted.
4. **Execute & Test:** Run the affected cells, then run **Restart & Run All** to verify end-to-end execution.
5. **Inspect Outputs:** Visually inspect generated charts, tables, and test statistics to ensure they make domain sense. Never claim success without verification.
