# Feature Implementation Workflow

> **Purpose:** Standard procedure for implementing a new analysis, module, pipeline stage, or model.

---

## 1. Workflow Diagram

```text
Understand task
       │
       ▼
Inspect repository
       │
       ▼
Identify relevant rules (project.md, data.md, analysis.md, notebooks.md, git.md)
       │
       ▼
Identify relevant skills (data-quality, exploratory-analysis, etc.)
       │
       ▼
Read relevant roadmap section (docs/roadmap.md)
       │
       ▼
Plan minimal change (avoid speculative abstractions)
       │
       ▼
Implement (PEP 8, modular in src/, reproducible seeds)
       │
       ▼
Verify (syntax check, assertions, clean kernel run)
       │
       ▼
Review diff (git diff check, zero unintended edits)
       │
       ▼
Report (concrete evidence, metrics, limitations)
```

---

## 2. Step-by-Step Execution Guide

### Step 1: Understand Task
- Clarify goals, target variables, and domain constraints.
- Determine the milestone and technical scope.

### Step 2: Inspect Repository
- Check active git branch: `git branch --show-current`.
- Run `git status` to verify working tree status.
- Inspect existing modules in `src/` and notebooks in `notebooks/` to avoid redundant code.

### Step 3: Identify Relevant Rules
- Review governing rules in [`.agents/rules/`](../rules):
  - Engineering constraints $\to$ [`project.md`](../rules/project.md)
  - Data integrity & joins $\to$ [`data.md`](../rules/data.md)
  - Statistical & ML validity $\to$ [`analysis.md`](../rules/analysis.md)
  - Notebook standards $\to$ [`notebooks.md`](../rules/notebooks.md)
  - Git hygiene $\to$ [`git.md`](../rules/git.md)

### Step 4: Identify Relevant Skills
- Consult the Skill Selection Matrix in [`.agents/AGENTS.md`](../AGENTS.md) and load only relevant skills from [`.agents/skills/`](../skills).

### Step 5: Read Relevant Roadmap Section
- Read the corresponding Week / Milestone in [`docs/roadmap.md`](../../docs/roadmap.md) to extract exact academic requirements, formulas, and evaluation rubrics.

### Step 6: Plan Minimal Change
- Define the smallest coherent change set.
- Select target files and write modular functions in `src/`. Avoid adding unnecessary dependencies or over-engineering.

### Step 7: Implement
- Write clean, PEP 8 compliant code.
- Add defensive assertions for data boundaries, row counts, and monotonic timestamps.
- Fix stochastic seeds: `random_state=42`.

### Step 8: Verify
- Syntax check: `python -m py_compile path/to/script.py`.
- Run assertions and verify generated outputs (Parquet, tables, 300 DPI figures).
- If modifying notebooks, run **Kernel $\to$ Restart & Run All**.

### Step 9: Review Diff
- Run `git diff` and `git status`.
- Ensure no stray temporary files, raw API dumps, or secrets are tracked.

### Step 10: Report
- Provide a concise verification summary with executed commands, verified metrics, output artifact paths, and honest limitations.
