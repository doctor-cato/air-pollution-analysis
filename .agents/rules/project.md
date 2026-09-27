# Project & Engineering Rules

> **Scope:** General engineering standards, architecture awareness, dependency control, and anti-patterns.  
> **Source Document:** [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md) (Chapters 1 & 5).

---

## 1. Architecture Awareness & Roadmap Separation

- **Roadmap is a Specification, Not Code:** [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md) defines academic requirements across 15 weeks. Planned directories (`data/`, `notebooks/`, `src/`, `figures/`, `reports/`) and files are not implemented until created on disk.
- **Inspect Before Creating:** Never assume a helper function, pipeline stage, or dataset exists. Always inspect the filesystem (`Get-ChildItem` or `ls`) and review existing code before writing new modules.
- **No Duplicate Implementations:** Do not recreate existing loaders, transformers, or plotters. Extend existing modules in `src/` rather than adding parallel implementations.

---

## 2. Minimal Changes & Speculative Abstractions

- **Smallest Coherent Change:** Implement strictly what is needed to fulfill the current task or milestone. Avoid adding features that are not yet requested.
- **No Premature Generalization:** Do not build abstract plugin systems, generic factory classes, or multi-cloud abstractions for a single-station air-pollution project. Write direct, readable, modular Python code.
- **Scope Discipline:** Modify only files directly relevant to the user's prompt. Leave unrelated documentation, web assets (`index.html`, `styles.css`), and roadmap files untouched.

---

## 3. Dependency Management & Prohibited Technologies

- **Toolchain:** Standard Python **3.10+** using standard `venv` and `pip`.
- **Pinned Dependencies:** All project dependencies must be pinned in `requirements.txt`.
- **Zero Unnecessary Bloat:** Do not introduce packaging frameworks (Poetry, Hatch, Flit) or external linter pipelines (Black, Ruff, Pre-commit) unless the user explicitly requests them.

### Supported Python Dependencies

| Package | Project Role | Expected Scope |
|---|---|---|
| `pandas` | Tabular data manipulation, time-series indexing & resampling | Ingestion, Cleaning, EDA |
| `numpy` | Vectorized numerical operations, logarithmic transforms (`log1p`) | Transformations & Metrics |
| `pyarrow` / `fastparquet` | Columnar Snappy-compressed Parquet storage | Storage (`data/processed/`) |
| `scipy` | Non-parametric statistical tests (`mannwhitneyu`, `wilcoxon`), bootstrap | Inference (Week 9) |
| `statsmodels` | Time-series decomposition (`tsa`), OLS regression, LINE diagnostics | Regression (Week 10) |
| `scikit-learn` | `Pipeline`, `ColumnTransformer`, `RobustScaler`, Random Forest | Preprocessing & Modeling |
| `matplotlib` | High-quality 300 DPI publication charts (Object-Oriented API) | Figures (`figures/`) |
| `seaborn` | Statistical distribution plotting, heatmaps | EDA (Week 6–7) |
| `requests` | Fetching data from OpenAQ and Open-Meteo REST APIs | Data collection (Week 2) |

### Explicitly Prohibited Over-Engineering (Anti-Patterns)

The following technologies are **strictly prohibited** in this repository:

| Prohibited Technology | Why It Is Prohibited | Proper Alternative |
|---|---|---|
| **Apache Spark / PySpark / Hadoop** | The 2-year hourly dataset has only $\approx 17,500$ rows ($\approx 5 - 20\text{ MB}$). Spark creates massive JVM overhead and is over-engineering. | Standard **Pandas** and **Parquet** (processes in $< 50\text{ ms}$). |
| **Deep Learning (LSTM, GRU, Transformers)** | Course INFO3020 requires interpretable statistical modeling and LINE assumption diagnostics; deep nets are uninterpretable black boxes. | **OLS Regression** and **Random Forest** with threshold tuning. |
| **Databases (PostgreSQL, MongoDB, SQLite)** | Adds infrastructure complexity with zero analytical benefit for static time-series research. | Snappy-compressed **Apache Parquet** files in `data/processed/`. |
| **Kubernetes / Docker / Microservices** | This is a data-science research repository, not a microservice backend. | Local virtual environment (`venv`). |
| **Cloud Infrastructure (AWS/GCP/Azure)** | Academic scope requires local reproducibility without API billing or vendor lock-in. | Local execution with reproducible seeds (`random_state=42`). |

---

## 4. Code Modularity in `src/`

Code must not remain trapped in notebook cells. Reusable logic belongs in `src/`:

```text
src/
├── __init__.py
├── data_collection.py      # REST API scrapers for OpenAQ and Open-Meteo
├── data_loader.py          # Parquet loading and schema verification
├── cleaning_pipeline.py    # Scikit-Learn Pipeline & ColumnTransformer
└── visualizer.py           # Tufte/Cleveland-style plotting helpers
```

- Any helper function exceeding 30 lines or called across 2+ notebooks must be moved to `src/`.
- All functions must include concise docstrings specifying input/output types and purpose.

---

## 5. Execution & Git Guardrails

- **No Automatic Commits or Pushes:** Never run `git commit` or `git push` unless the user explicitly gives a command to commit or push.
- **Review Diff Before Declaring Done:** Always run and inspect `git diff` before concluding a task to verify that no unintended edits, secrets, or temporary files were left behind.
- **File-Scoped Verification:** Always syntax-check scripts (`python -m py_compile path/to/file.py`) and test notebooks from a clean kernel before declaring work complete.
