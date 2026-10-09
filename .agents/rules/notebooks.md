# Jupyter Notebook Rules & Standards

> **Scope:** Notebook development, reproducibility, output handling, and refactoring.  
> **Source Document:** [`docs/roadmap.md`](../../docs/roadmap.md) (Sections 12.2 & 13.E).

---

## 1. Planned Notebook Architecture

Notebooks are organized sequentially in `notebooks/` matching the project milestone progression:

| Notebook | Focus & Contents | Upstream Input | Primary Output |
|---|---|---|---|
| `00_environment_test.ipynb` | CI smoke test & environment verification | None | Execution verification output |
| `01_data_collection.ipynb` | API fetching, dynamic sync & interim canonical serialization | External APIs (OpenAQ S3, Open-Meteo) | `data/raw/*.json`, `data/interim/*.parquet`, `data/raw/metadata.json` |
| `02_quality_audit.ipynb` | Issue #3/#5 — 6-dimension audit of the pre-cleaning state | `data/raw/`, `data/interim/` | `docs/data_quality_audit.md` |
| `03_data_cleaning.ipynb` | Issue #6 — deterministic cleaning, `assert_no_imputation()` proof | `data/interim/` | `data/interim/air_quality_canonical.parquet`, `data/interim/weather_canonical.parquet`, `docs/cleaning_log.md` |
| `03_transformation_pipeline.ipynb` | Issue #7 — merge → freeze → split → fit, leakage validation, atomic export | `data/interim/` | `data/processed/air_pollution_final.parquet` (gitignored artifact) |
| `04_*.ipynb` *(planned)* | Exploratory data analysis: 4-family stats, diurnal/seasonal patterns | `data/processed/` | `figures/FIG-01`..`FIG-07.png`, `reports/statistical_profile.csv` |
| `05_*.ipynb` *(planned)* | Statistical inference: non-parametric tests, effect sizes, Bootstrap CI | `data/processed/` | `reports/inference_results.md` |
| `06_*.ipynb` *(planned)* | Regression + imbalanced classification (Issues #11–#13) | `data/processed/` | Regression tables, diagnostic plots, PR curves |

> **Two notebooks deliberately share the `03_` prefix.** Cleaning (`03_data_cleaning`)
> must run **before** the transformation pipeline, because both read and write the
> canonical interim Parquet files in `data/interim/`. The pipeline's audit must see
> the *pre-cleaning* state; re-running `03_data_cleaning` requires restoring
> `data/interim/` from `data/raw/` first, because `reindex_hourly_grid()` needs the
> pre-cleaning grid rather than its own output.

---

## 2. Core Execution & Reproducibility Rules

1. **Clean Kernel Standard:**
   - Any completed notebook must run completely from top to bottom via **Kernel $\to$ Restart & Run All** with zero errors or manual cell jumps.
   - "Zero errors" is a measurement, not a claim: execute the `.ipynb` programmatically (`nbclient.NotebookClient` with
     `resources={'metadata': {'path': 'notebooks/'}}`), then assert that no cell output has `output_type == 'error'`.
     `python -m nbconvert --execute` exiting 0 does **not** prove this.
2. **Deterministic State:**
   - Set fixed seeds (`random_state=42`) at the top of the notebook.
   - Cells must execute in linear sequential order ($1, 2, 3, \dots$).
   - Never rely on variables defined out-of-order, in deleted cells, or from previous sessions.
3. **Structured Cell Layout:**
   - **Cell 1:** Markdown title, metadata, purpose of the notebook, and prerequisite inputs.
   - **Cell 2:** All library imports and environment configuration (`warnings`, `matplotlib` settings).
   - **Cell 3:** Fixed constants, file paths (`pathlib.Path`), and random seeds.
   - **Facts stated in Markdown must come from the data, not from prose.** Station names,
     row counts and date spans are read and printed by a code cell; the Markdown refers to
     them. Writing a station name by hand is exactly how a fabricated source entered this
     repository once: `docs/roadmap.md` and notebook `03_transformation_pipeline`
     both claimed "Tư Liên", a station that appears nowhere in the data (the real
     `station_id` is `VN001_HANOI_556_NGUYEN_VAN_CU`, location `556 Nguyễn Văn Cừ`).
     That violates §4 "Never fabricate sources".
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
