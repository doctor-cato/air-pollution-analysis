# Issue #44 — Checkpoint evidence and gate status

**Status:** CP0 source-approval gate **BLOCKED**. CP1 adapter and CP2/CP3
preparation helpers are **PARTIAL**; CP4 assessment and CP5 contract are **DONE
as documentation gates**, not as data integration. Values below come from the
reproducible command shown in the evidence section, not synthetic fixtures.

## CP0 — public-mirror inventory

The candidate is `dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies`, pinned
at `25d08e949c9d01ba57c4e74ff9b3b99328ecf141`. The manifest contains the immutable
Git blob SHA, downloaded-file SHA-256, size, schema, observed time span, and
row/valid-row counts for all **46** Hanoi CSV files found under
`Data/Hanoi/2022` through `Data/Hanoi/2025`.

| Year | Calendar | Observed | QC-valid | Missing while source available | Invalid/conflict | Source unavailable | Longest annual gap (h) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022 | 8,760 | 6,995 | 6,939 | 1,764 | 56 | 1 | 1,081 |
| 2023 | 8,760 | 8,429 | 8,366 | 331 | 63 | 0 | 109 |
| 2024 | 8,784 | 7,360 | 7,318 | 1,424 | 42 | 0 | 820 |
| 2025 | 8,760 | 2,339 | 2,322 | 37 | 17 | 6,384 | 32 |

The corrected scan finds **25,955** duplicate source rows: **24,352** YTD–MTD
overlap hours, of which **24,351** are identical; **1** timestamp conflicts
(`2023-11-07T17:00`, MTD `-999`/Missing versus YTD `33`/Valid). The ledger is
committed in the manifest and conflicts are never selected as observations.
The full source-observation window is `2022-01-01T01:00` through
`2025-04-09T23:00`; the longest full-series source-available gap is **1,081 h**.
Consequently post-window 2025 calendar hours are reported as source-unavailable,
not station missing. It separately records three files in a wrong year directory
and four payloads with cross-year records. Downloads preserve repository-relative
paths, use the pinned commit URL, and verify both Git blob SHA-1 and SHA-256.

**Decision:** the mirror remains **unapproved, reference-only**.  GitHub's
repository metadata exposes no license, and the mirror has the inconsistencies
above.  It must not be added to `data/raw/metadata.json`, ingested into a
canonical dataset, or used for EDA/inference until the mirror maintainer or
official AirNow/US Department of State source supplies reviewable provenance,
terms of use, and station/device evidence.  This is a blocker, not a failed
attempt to join stations.

**Alternative-source feasibility:** public OpenAQ S3 location `7441` is
technically accessible for 2022–2025, unlike `2539`; the verified POC and
NO-GO integration decision are in `docs/issue44_feasibility_decision.md` and
`reports/issue44_openaq_poc.json`. It lacks verified operator/instrument/change
history and is not approved as a replacement, VN001 or VN002 input.

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

**PARTIAL, blocked for real-data results by CP0.**
`src/issue44_preparation.py` supplies synthetic-fixture-tested derived-column
interpolation, explicit masking and MAE/RMSE/bias evaluation. It requires a
caller-chosen gap threshold, preserves observed columns, and rejects crossing a
station, split, duplicate timestamp, or non-hourly interval. No parameter was
chosen and no scientific metric is reported.

## CP3 — EDA / FIG-01

**PARTIAL, blocked for findings by CP0.** Winter is defined as December–February
with December assigned to the ending `winter_year`; station-separated summaries
are prepared and tested. No historical comparison, figure regeneration, or
revised conclusion is claimed; FIG-01 remains the VN001 baseline.

## CP4 — traffic evidence for FIG-04

**DONE (negative assessment):** `docs/issue44_traffic_source_assessment.md`
records the reviewed official sources and their **NOT AVAILABLE / NOT VERIFIED**
outcomes. FIG-04 receives no traffic causal interpretation.

## CP5 — integration and modelling boundary

The dataset contract is in `docs/issue44_dataset_contract.md` and fixes:

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
The profiler and preparation helpers have independent synthetic tests. Full
unit, notebook, CI and legacy-vs-extended real-data comparisons remain required
before this Draft PR can become ready; the extended portion cannot run until CP0
is unblocked.
