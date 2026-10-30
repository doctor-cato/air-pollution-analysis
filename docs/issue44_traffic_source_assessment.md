# Issue #44 — Traffic-source assessment for FIG-04

**Decision (2026-10-30): NOT AVAILABLE / NOT VERIFIED for a station-level PM2.5 analysis.** No traffic data were downloaded, generated, joined, or used to alter FIG-04.

| Source | Provenance / terms | 2022–2025 history and resolution | Raw data / geographic match | Decision |
|---|---|---|---|---|
| [TomTom Traffic Index — Ha Noi](https://www.tomtom.com/traffic-index/city/ha-noi/) | TomTom describes anonymized trip data over city/metro road networks. | Public page exposes annual aggregate indicators (the reviewed page reports 2025), not a reproducible hourly 2022–2025 series. | Aggregated city/metro measure, not either VN001/VN002 station catchment; no raw observations exposed on that page. | Reference context only; unsuitable for statistical PM2.5 covariate. |
| [TomTom Traffic Stats](https://docs.tomtom.com/traffic-stats/documentation/product-information/introduction) | Commercial product documentation; access/trial is required. | Documentation describes historical analytics, but this review did not establish a public licensed Hanoi extract for the project window. | No downloaded raw Hanoi series or station-level geographic crosswalk. | **NOT VERIFIED**; do not use without a reviewable export, license and spatial protocol. |
| [TomTom free city downloads](https://www.tomtom.com/downloads/traffic-index/) | TomTom publishes selected city CSV downloads. | The reviewed public list does not include Hanoi. | Therefore no Hanoi raw artifact or checksum can be recorded. | **NOT AVAILABLE**. |
| Hanoi traffic-camera / municipal source | No official, licensed, downloadable historical 2022–2025 camera-count dataset was verified in this review. | Camera imagery, if available, is not automatically a traffic-count time series and requires legal/measurement validation. | No station correspondence or raw archive verified. | **NOT VERIFIED**. |

## Consequence

FIG-04 remains descriptive and has no traffic causal interpretation. To reopen this checkpoint, retain a raw artifact and checksum; document license/terms, retrieval method, city/station spatial correspondence, time zone, resolution and missingness; and pre-specify an observational (not causal) analysis.
