# Agent Instructions – Air Pollution Analysis

> Full project specifications and detailed domain rules live in [`.agents/AGENTS.md`](.agents/AGENTS.md).

## Project Identity
- **Domain:** Time-series urban air quality ($\text{PM}_{2.5}$) and meteorology in Hanoi, Vietnam (INFO3020 Data Science).
- **Stage:** Milestone 2 (Data Quality Audit & Deterministic Cleaning), entering Week 05. Authoritative plan in [`docs/roadmap.md`](docs/roadmap.md).
- **Architecture Notice:** Implemented: ingestion module (`src/data_collection.py`), 6-dimension quality audit module (`src/data_quality.py`), deterministic cleaning module (`src/cleaning.py`), leakage-safe preprocessing module (`src/cleaning_pipeline.py`), flag-evidence module (`src/flag_evidence.py`), unit tests (393 test tất định: `tests/test_data_collection.py` 57, `tests/test_data_quality.py` 44, `tests/test_cleaning.py` 114, `tests/test_cleaning_pipeline.py` 44, `tests/test_cleaning_pipeline_guards.py` 43, `tests/test_fetch_dataset.py` 9, `tests/test_flag_evidence.py` 35, `tests/test_pipeline_runtime_log.py` 40, `tests/test_verify_claims_rolling.py` 7), dataset acquisition script (`scripts/fetch_dataset.py`), CI workflow, and notebooks `notebooks/00`–`03`. **Not yet implemented (NOT IMPLEMENTED): `notebooks/04`–`07`** — the classification notebook was renumbered from `06_` to `07_` in task 0.3, so the missing range is 04 through 07, not 04 through 06. Always inspect the filesystem before writing code.
- **Notebook Execution Order:** `00` → `01` (collection) → `02` (audit) → `03` (deterministic cleaning) → `03` (transformation pipeline, Issue #7). The cleaning notebook and the transformation notebook both read/write the canonical interim Parquet files in `data/interim/`, so `02` must run first to audit the pre-cleaning state. To re-run the cleaning notebook correctly, restore `data/interim/` from `data/raw/` first — `reindex_hourly_grid()` requires the pre-cleaning state, not its own output. The transformation notebook writes `data/processed/air_pollution_final.parquet` (gitignored).
- **Test count semantics — do not conflate these numbers.** *393* is the number of tests **discovered** by `python -m unittest discover tests`; it is the same on every platform. What differs is how many actually **execute**:
  - Windows (local, **with `data/interim/*.parquet` present**): `Ran 393 tests` + `OK` → **393 executed, 393 passed, 0 skipped**.
  - Ubuntu (CI `ubuntu-latest`, **no `data/`**): `Ran 393 tests` + `OK (skipped=6)` → **387 executed, 387 passed, 6 skipped**.

  The skips have two different causes and both are expected, not regressions:
  1. `test_windows_separators_in_payload_are_preserved_verbatim` and `test_metadata_block_and_runtime_log_disagree_on_separators` in `tests/test_pipeline_runtime_log.py`, gated by `@unittest.skipUnless(os.name == "nt")` because the separator invariant only exists on Windows;
  2. the four tests in `tests/test_flag_evidence.py::TestDocumentedReproduction`, which skip when `data/interim/*.parquet` is absent — the repo **does not commit `data/`**, so these only run locally. They are the tests that pin the documented `F = 16,78` / `p = 7,4·10⁻¹¹` against a real fit; run them locally with `python -m unittest tests.test_flag_evidence -v` after `scripts/fetch_dataset.py`.

  So a platform gap in the executed count is expected — never present the discovered count as the passed count without saying which platform it refers to.

## Package Manager & Toolchain
- **Runtime:** Python 3.10+
- **Tool:** Use standard **pip**: `pip install -r requirements.txt`
- **Web (gh-pages):** Vanilla HTML5 / CSS3 / ES6+ JS (no build or node/npm required).
- **Excluded:** No Spark/Hadoop, no Deep Learning (LSTM/Transformers), no unnecessary dev bloat.

## File-Scoped Commands
| Task | Command |
|---|---|
| Syntax Check | `python -m py_compile path/to/file.py` |
| Run Script | `python path/to/script.py` |
| Local Web Preview | `python -m http.server 8000` |
| Git Status | `git status` |
| Review Diff | `git diff path/to/file` |

## Key Conventions & Non-Negotiables
- **Data Integrity:** Apply Three-tier Raw Data Policy (roadmap §3.2); preserve payloads in `data/raw/` without manual edits, track SHA-256 in `data/raw/metadata.json`, keep raw payloads untracked via `.gitignore`. Store clean outputs as Snappy Parquet (`.parquet`).
- **Deterministic Cleaning vs. Data-Dependent Preprocessing:** Never impute, scale, or compute global statistics before the chronological split. Deterministic cleaning (`src/cleaning.py`) is bounded by `assert_no_imputation()`, which compares **cell by cell** on the `(station_id, timestamp)` key: a cell that was `NaN` before must still be `NaN`, and a cell that held a value must keep that exact value or become `NaN`. Observed measurements may only disappear, never appear or change.
- **Diagnostic flags are not imputations:** `pm25_was_missing` (station reporting gap), `pm25_was_stuck` (sensor frozen), and `is_high_humidity_fog` (high-humidity optical flag) are separate flags. Issue #7 must read all three before deciding whether imputation is admissible. All three stay in the dataset; only two are barred from the feature set, for **different** reasons — `pm25_was_missing` is structural target leakage, `is_high_humidity_fog` has no demonstrated **marginal** predictive value (`corr(pm25, RH) = -0,037`; it *does* interact with season, so re-testing the RH threshold will not change this). See `TARGET_DERIVED_FLAGS` and `NON_PREDICTIVE_FLAGS` in `src/cleaning_pipeline.py`.
- **Time-Series Safety:** Enforce chronological sort, unique timestamps, and check row counts to prevent Row Explosion on joins.
- **Strict Leakage Prevention:** Temporal train/test splits only. Fit transformers strictly on Train partitions.
- **Statistical Testing:** Mandatory trio: Test statistic + $p$-value + Effect Size ($r_{rb}$) + 95% Bootstrap CI.
- **Regression:** Check 4 LINE assumptions and VIF before reporting $R^2$. Never make causal claims.
- **Classification:** Focus on Recall and PR-AUC; avoid the Accuracy trap on imbalanced data.
- **Notebooks:** Must run cleanly via **Restart Kernel & Run All** with deterministic seeds (`random_state=42`).

## Reference Documentation
- **Master Agent Guide:** [`.agents/AGENTS.md`](.agents/AGENTS.md)
- **Project & Engineering Rules:** [`.agents/rules/project.md`](.agents/rules/project.md)
- **Data & Time-Series Rules:** [`.agents/rules/data.md`](.agents/rules/data.md)
- **Notebook Rules:** [`.agents/rules/notebooks.md`](.agents/rules/notebooks.md)
- **Analysis & Modeling Rules:** [`.agents/rules/analysis.md`](.agents/rules/analysis.md)
- **Git Rules:** [`.agents/rules/git.md`](.agents/rules/git.md)
- **Workflows:** [`.agents/workflows/`](.agents/workflows/)
- **Specialized Skills:** [`.agents/skills/`](.agents/skills/)
