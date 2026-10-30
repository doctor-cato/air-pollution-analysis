# Issue #44 — Proposed extended-dataset contract

This is a **blocked design contract**, not an approved VN002 artifact.

| Field / rule | Contract |
|---|---|
| Series identity | `station_id` is required. `VN001` and prospective `VN002_HANOI_US_EMBASSY` are never coalesced or substituted. |
| Observation status | Canonical `pm25`/`pm10` retain observed values only. Any experiment writes `<pollutant>_derived_interpolated` and `<pollutant>_is_derived`; it never overwrites observed columns. |
| Provenance | Each artifact records source name, immutable source version/commit, raw relative path, SHA-256, retrieval UTC, schema, device/station metadata, coordinates, license/terms decision and coverage. |
| Time | `timestamp` is timezone-aware `Asia/Ho_Chi_Minh`, hourly, and unique on `(station_id, timestamp)`. |
| Split policy | The existing VN001 chronological baseline/split is immutable. Any extended comparison creates station-aware, chronological partitions and prohibits interpolation across a split boundary. |
| Comparison | Report legacy and approved extended results separately, including sample/season coverage and missingness. Do not replace legacy figures or Issue #11 inference. Regression models remain Issue #12 scope. |

VN002 ingestion and ERA5 backfill remain blocked until CP0 obtains reviewable source permission, provenance and station/device evidence.
