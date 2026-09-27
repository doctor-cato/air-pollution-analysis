# Agent Instructions – Air Pollution Analysis

> Full project specifications and detailed domain rules live in [`.agents/AGENTS.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/AGENTS.md).

## Project Identity
- **Domain:** Time-series urban air quality ($\text{PM}_{2.5}$) and meteorology in Hanoi, Vietnam (INFO3020 Data Science).
- **Stage:** Week 1 / Specification & Kickoff. Authoritative plan in [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md).
- **Architecture Notice:** Distinguish planned modules (`src/`, `notebooks/`, `data/`) from existing files. Inspect before writing code.

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
- **Data Integrity:** Keep `data/raw/` read-only. Store clean output as Snappy Parquet (`.parquet`).
- **Time-Series Safety:** Enforce chronological sort, unique timestamps, and check row counts to prevent Row Explosion on joins.
- **Strict Leakage Prevention:** Temporal train/test splits only. Fit transformers strictly on Train partitions.
- **Statistical Testing:** Mandatory trio: Test statistic + $p$-value + Effect Size ($r_{rb}$) + 95% Bootstrap CI.
- **Regression:** Check 4 LINE assumptions and VIF before reporting $R^2$. Never make causal claims.
- **Classification:** Focus on Recall and PR-AUC; avoid the Accuracy trap on imbalanced data.
- **Notebooks:** Must run cleanly via **Restart Kernel & Run All** with deterministic seeds (`random_state=42`).

## Reference Documentation
- **Master Agent Guide:** [`.agents/AGENTS.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/AGENTS.md)
- **Project & Engineering Rules:** [`.agents/rules/project.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/project.md)
- **Data & Time-Series Rules:** [`.agents/rules/data.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/data.md)
- **Notebook Rules:** [`.agents/rules/notebooks.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/notebooks.md)
- **Analysis & Modeling Rules:** [`.agents/rules/analysis.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/analysis.md)
- **Git Rules:** [`.agents/rules/git.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/rules/git.md)
- **Workflows:** [`.agents/workflows/`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/workflows/)
- **Specialized Skills:** [`.agents/skills/`](file:///C:/Users/Admin/Documents/code_workspace/khdl/.agents/skills/)
