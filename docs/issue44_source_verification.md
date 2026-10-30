# Issue #44 — CP0 source-verification record

**Checked:** 2026-10-30. **Decision:** **BLOCKED / reference-only**. This record
separates evidence about government-origin data from evidence about a third-party
mirror. It does not approve VN002 ingestion or join it to VN001.

## Evidence matrix

| Evidence | URL | Status | What it verifies / does not verify |
|---|---|---|---|
| EPA data licensing statement | <https://edg.epa.gov/EPA_Data_License.htm> | **VERIFIED** | EPA says data it produces are normally public domain, absent another specification, and carries no accuracy/fitness warranty. It does **not** license a third-party GitHub repository, prove a CSV originated at EPA, or determine Department of State rights. |
| Mirror repository README | <https://github.com/dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies> | **SELF-REPORTED** | It says its author obtained historical data from EPA Public Support and that sharing stopped on 2025-03-04. Neither claim identifies a request, response, archive, file hashes, terms, or station metadata. GitHub API reports repository `license: null` (recorded in the manifest): repository redistribution terms are **UNVERIFIED**. |
| OpenAQ location 7441, `Hanoi` | <https://explore.openaq.org/locations/7441> | **PARTIALLY VERIFIED** | The public page identifies an AirNow-provided reference-grade stationary PM2.5 location, “Government Monitor”, US Public Domain license, reporting since 2016 and updated two years ago. It does not establish that a mirror CSV is its export, instrument model, coordinates, or availability of a downloadable matching hourly raw series; download requires login. |
| OpenAQ location 2539, `US Diplomatic Post: Hanoi` | <https://explore.openaq.org/locations/2539> | **PARTIALLY VERIFIED** | The public page identifies a StateAir Hanoi reference-grade stationary PM2.5 location, “Government Monitor”, reporting since 2016, with only 2016 visible in the reviewed patterns. It does not map this identifier to 7441 or to every 2022–2025 mirror record. |
| OpenAQ public S3 archive, 7441 | <https://openaq-data-archive.s3.amazonaws.com/?prefix=records/csv.gz/locationid=7441/> | **VERIFIED (technical access)** | Public S3 listings and 903 parsed objects establish accessible 2022–2025 PM2.5 records with sensor 21632, `+07:00` timestamps and Hanoi coordinates; aggregate evidence is in `reports/issue44_openaq_poc.json`. This does not prove operator/instrument continuity or mirror provenance. |
| AirNow Data Exchange Guidelines | <https://docs.airnowapi.org/docs/DataUseGuidelines.pdf> | **PARTIALLY VERIFIED** | Official AirNow URL is available. Its terms must be retained/reviewed with the requested raw extract before use. This review does not treat the guideline as a license grant for the mirror or a provenance certificate for any CSV. |
| DoS/EPA Embassy archive | <https://gispub.epa.gov/airnowembassy/> | **VERIFIED** | The official map describes reference-grade embassy/consulate monitors, archive access and raw concentration display; it labels current readings preliminary/unvalidated and subject to change. It does not expose a reproducible Hanoi 2022–2025 bulk extract or station/device history in this review. |

## File-level and station evidence

`reports/issue44_mirror_manifest.json` reproducibly verifies the **Git object and
downloaded bytes** at mirror commit `25d08e949c9d01ba57c4e74ff9b3b99328ecf141`.
That is integrity of the mirror snapshot, not provenance of its CSV payload.

OpenAQ public S3 was accessible for location 7441; two one-day comparisons are
recorded in `reports/issue44_openaq_poc.json` (22/24 equal in a 2022 sample and
0/24 equal in a 2025 sample). This is **not** a provenance certification: no
official export linkage, QC-field equivalence, or station-identity mapping is
available. An AirNow raw comparison remains **NOT VERIFIED**.

OpenAQ 7441 and 2539 are independent records. Neither public page proves they
are the same physical station, nor that either is the mirror’s station in every
year. Existing historical references to a Met One BAM-1020 are insufficient to
claim the device, location or operator remained unchanged during 2022–2025;
those facts are **UNVERIFIED** for the extension window. VN001 and prospective
VN002 remain separate.

## March–April 2025 inconsistency

The mirror README says real-time sharing stopped on 2025-03-04 and calls its
snapshot no longer updated. The pinned mirror nevertheless contains
`Hanoi_PM2.5_2025_04_MTD.csv` with timestamped rows through
`2025-04-09T23:00` local time. This is **VERIFIED for the mirror bytes** but has
**no verified explanation from EPA, DoS, AirNow or the maintainer**. It could be
a delayed extract, a timezone/name convention, or another process; no such
cause is asserted here.

## Permission, attribution and scientific limits

- Government-origin EPA data may be public domain under the EPA statement, but
  this does not resolve the mirror’s redistribution license or the DoS/AirNow
  data-exchange terms.
- Before any approved use, record the official source, request/export identifier,
  terms, attribution, retrieval UTC, station metadata, raw hash and schema.
- Even an approved preliminary feed supports descriptive/exploratory analysis
  only within its documented limitations; it cannot alone establish a validated
  long-term trend or a causal claim. Trend conclusions require the provider’s
  validation status, continuity and change history.

## Required confirmations

1. EPA/DoS/AirNow: identify the official archive/export for Hanoi, its usage and
   redistribution terms, and whether a 2022–2025 historical extract is available.
2. EPA/DoS/AirNow: provide station ID, coordinates, operator, instrument model,
   calibration/QC policy and any move/replacement/change log for 2022–2025.
3. Mirror maintainer: provide the EPA Public Support request/response, original
   filenames/metadata, retrieval date, terms, and an explanation for records
   after 2025-03-04.
4. Official provider: provide enough raw records to compare timestamp, raw
   concentration, QC, unit and duration against the mirror without treating a
   superficial match as station identity.

## Draft email for manual sending

```text
Subject: Request to verify historical Hanoi embassy PM2.5 archive and reuse terms

Hello,

We are conducting a university data-science project and need to verify a public
GitHub mirror that claims to contain AirNow/Department of State historical Hanoi
PM2.5 records for 2022–2025. We will not ingest the mirror without confirmation.

Could you identify an official historical export/archive for the Hanoi embassy or
consulate monitor and confirm: (1) usage and redistribution terms; (2) station
ID, coordinates, operator and instrument model; (3) equipment/location/QC
changes during 2022–2025; (4) whether hourly Raw Conc., QC Name, Conc. Unit and
Duration can be obtained for an independent comparison; and (5) whether records
through 2025-04-09 are expected despite public reporting of a 2025-03-04 sharing
change?

We can provide the mirror commit, filenames and SHA-256 evidence on request.
Thank you.
```
