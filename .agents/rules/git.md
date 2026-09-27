# Git Workflow & Safety Guardrails

> **Scope:** Git hygiene, branch conventions, commit formatting, and safety checks.  
> **Source Document:** [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md) (Section 12.2 & Week 1).

---

## 1. Repository Branching Context

The repository has two distinct branch contexts:

- **`main`:** Canonical academic branch. Contains core project documentation (`docs/roadmap.md`), Python source modules (`src/`), analysis notebooks (`notebooks/`), and generated reports.
- **`gh-pages`:** Dedicated web presentation branch. Hosts the interactive static single-page application (`index.html`, `styles.css`, `script.js`) visualizing the course roadmap.
- **Always check your active branch:** Run `git branch --show-current` before making changes.

---

## 2. Pre-Modification Protocol

Before touching or creating any files:
1. Run `git status` to ensure a clean working tree or identify existing uncommitted work.
2. Verify you are not modifying files outside the user's specific request.
3. Review `.gitignore` to confirm required exclusions are active.

---

## 3. Strict Safety Guardrails

- 🚫 **NEVER commit raw data:** Raw API responses (`data/raw/*.json`, `data/raw/*.csv`) must remain uncommitted or tracked strictly via `.gitignore`.
- 🚫 **NEVER commit credentials:** Never commit API keys, auth tokens, passwords, or `.env` files.
- 🚫 **NEVER rewrite history:** Never run `git reset --hard`, `git push --force`, or interactive rebases on shared branches unless explicitly commanded by the user.
- 🚫 **NEVER auto-commit or auto-push:** The agent must only run `git commit` or `git push` when the user has explicitly requested a commit or push.
- 🚫 **NEVER include stray build/system files:** Exclude `.ipynb_checkpoints`, `__pycache__`, `.DS_Store`, and temporary test artifacts.

---

## 4. Standard Working Cycle

Agents must strictly adhere to the 5-step operational loop:

```text
1. INSPECT      → Run git status, review branch & existing files
2. IMPLEMENT    → Make minimal, focused, PEP 8 compliant edits
3. VERIFY       → Execute code, run assertions, test clean kernel
4. REVIEW DIFF  → Inspect git diff to catch accidental modifications
5. SUMMARIZE    → Present verified evidence and concise status
```

---

## 5. Commit Standards (When Requested by User)

When explicitly instructed to create a commit, follow the Conventional Commits specification:

### Format
```text
<type>(<scope>): <concise description in imperative mood>

- <bullet point detailing specific change and rationale>
- <bullet point detailing verification performed>
```

### Commit Types
- `feat`: New analysis, new model, or new data pipeline stage.
- `fix`: Bug fix, leakage prevention, physical bounds correction.
- `docs`: Updates to `docs/roadmap.md`, `docs/cleaning_log.md`, or `README.md`.
- `refactor`: Moving reusable logic from notebooks into `src/`.
- `test`: Adding assertion checks, schema tests, or validation scripts.
- `chore`: Maintenance of `.gitignore`, requirements updates, directory setup.

### Example
```text
feat(pipeline): implement clean hourly time-grid reindexing and gap flags

- Reindex timestamps against continuous hourly grid to expose station downtime
- Add time-weighted interpolation for gaps <= 2 hours
- Generate pm25_was_missing flag for gaps > 6 hours
- Update docs/cleaning_log.md with imputation counts
```
