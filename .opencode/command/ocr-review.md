---
description: Review code changes using OpenCodeReview (OCR) in delegation mode (no API key needed)
agent: build
---

Run an OCR delegation-mode review. OCR does the deterministic part (which files to
review, which review rules apply); you do the actual review with your own model.

Steps:

1. Load the `open-code-review-delegate` skill and follow its workflow.
2. Determine the scope:
   - If the user named a range (e.g. "main..HEAD", "PR #12", a commit sha), use
     `ocr delegate preview --format json --from <ref> --to <ref>` or `--commit <sha>`.
   - Otherwise review the workspace: `ocr delegate preview --format json`.
3. For this repo, pass background context so the review knows the domain rules:
   `--background-file AGENTS.md` (project rules live in `.agents/rules/`).
4. Review every `reviewable_files` entry, report findings with
   path / content / start_line / end_line / category / severity, and state
   coverage (total_files, reviewed_files, skipped_files).
5. Repo-specific focus — see `AGENTS.md` and `.agents/rules/`:
   - Deterministic cleaning must never impute (`assert_no_imputation()` invariant).
   - No data-dependent preprocessing before the chronological split (leakage).
   - Time-series safety: sorted timestamps, no Row Explosion on joins.
   - Statistical results need test statistic + p-value + effect size + bootstrap CI.

If the user also asked to fix issues, apply Critical/High fixes only and describe the rest.