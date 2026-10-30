# Issue #44 — Checkpoint evidence and gate status

**Status:** CP0 evidence collected; CP0 source-approval gate **BLOCKED**.  This
document deliberately does not mark any Issue #44 acceptance criterion complete.
All values below come from the reproducible command shown in the evidence
section, not from a synthetic fixture.

## CP0 — public-mirror inventory

The candidate is `dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies` at its
`main` branch.  `reports/issue44_mirror_manifest.json` contains the immutable
Git blob SHA, downloaded-file SHA-256, size, schema, observed time span, and
row/valid-row counts for all **46** Hanoi CSV files found under
`Data/Hanoi/2022` through `Data/Hanoi/2025`.

| Year | Expected hours | Observed distinct hours | Valid raw-concentration hours | Missing / invalid hours | Longest gap (h) |
|---:|---:|---:|---:|---:|---:|
| 2022 | 8,760 | 6,995 | 6,956 | 1,804 | 720 |
| 2023 | 8,760 | 8,429 | 8,367 | 393 | 109 |
| 2024 | 8,784 | 7,360 | 7,318 | 1,466 | 589 |
| 2025 | 8,760 | 2,339 | 2,322 | 6,438 | 744 |

The union scan found **25,468** duplicate source rows across YTD/MTD payloads.
It also found cross-year or misfiled payloads, including the 2022 YTD with a
2023 timestamp and files named for 2023/2024/2025 located under the preceding
year directory.  The manifest retains these facts; it does not silently rename
or discard raw payloads.

**Decision:** the mirror remains **unapproved, reference-only**.  GitHub's
repository metadata exposes no license, and the mirror has the inconsistencies
above.  It must not be added to `data/raw/metadata.json`, ingested into a
canonical dataset, or used for EDA/inference until the mirror maintainer or
official AirNow/US Department of State source supplies reviewable provenance,
terms of use, and station/device evidence.  This is a blocker, not a failed
attempt to join stations.

## CP1 — collection and schema readiness

`AirNowDOSAdapter` now accepts both verified historical schemas:

- legacy `Date (LST)` + `Value`;
- mirror `Date (LT)` + `Raw Conc.`.

For the newer schema it uses only `Raw Conc.` and accepts `PM2.5 - Principal`.
It never treats `NowCast Conc.` as the raw observation; negative/sentinel values
remain `NaN`, PM10 remains `NaN`, timestamps are localized to
`Asia/Ho_Chi_Minh`, and the output station is always
`VN002_HANOI_US_EMBASSY`.

**Blocked:** no historical VN002 canonical output or 2022–2025 ERA5 backfill
was produced because CP0 has not approved the source.  VN001 baseline files and
their existing provenance are unchanged.

## CP2 — missing-data experiment

**Blocked by CP0.** No interpolation experiment, masking-validation metric, or
derived imputed column is reported without an approved, real historical input.
The existing canonical observed-value invariant remains binding: observed PM2.5
and PM10 are never overwritten, and no interpolation may cross station or a
chronological split.

## CP3 — EDA / FIG-01

**Blocked by CP0 and CP2.** No historical winter comparison, figure regeneration,
or revised scientific conclusion is claimed.  The seven existing M3 figures are
kept as the VN001 legacy baseline and are separately guarded in CI.

## CP4 — traffic evidence for FIG-04

**Not started.** No verified Hanoi traffic dataset with applicable license,
temporal resolution, and geographic correspondence was established in this
checkpoint.  FIG-04 must not be given a causal traffic interpretation.

## CP5 — integration and modelling boundary

The dataset contract for a future approved extension is fixed here:

1. `station_id` is mandatory; VN001 and VN002 remain separate series.
2. Any extended artifact records source version, raw SHA-256, station metadata,
   coverage, and missing-data method.
3. Rolling/lag/interpolation operations group by `station_id`; the existing VN001
   baseline and chronological split are retained unchanged.
4. Issue #11 is evaluated as a **legacy-versus-extended comparison**, never
   overwritten.  OLS/Ridge/Lasso, LINE diagnostics, and model results remain in
   Issue #12; none is implemented here.

## CP6 — verification and reproducibility

The real-source CP0 command was:

```powershell
python scripts\profile_airnow_mirror.py `
  --output reports\issue44_mirror_manifest.json `
  --raw-dir C:\Users\Admin\AppData\Local\Temp\opencode\issue44-airnow-mirror
```

The raw downloads stay outside Git; the committed manifest is derived evidence.
The adapter's new-schema regression test passes.  Full unit, notebook, CI, and
legacy-vs-extended comparisons remain required before this Draft PR can become
ready, and the extended portion cannot run until CP0 is unblocked.
