# Extended station-specific EDA

Main statistics use observed PM2.5 only. Full profiles by year, month, season/winter, hour and weekday are in `extended_statistical_profile.csv`; associations in `extended_meteorology_associations.csv`.

| Station | n | Median (µg/m³) | IQR | Coverage active |
|---|---:|---:|---:|---:|
| VN001_HANOI_556_NGUYEN_VAN_CU | 7,495 | 37.32 | 30.73 | 82.87% |
| VN003_HANOI_OPENAQ_7441 | 18,208 | 38.00 | 32.00 | 63.49% |

Partial years and winters retain full-calendar denominators; low-coverage periods are descriptive only. Year-specific daily median CIs and exclusion of partial/low-coverage winters are in `extended_inference_sensitivity.csv`. Circular wind-direction mean/SD use angular statistics. `extended_meteorology_binned.csv` shows quintile medians to inspect departures from linear association. ERA5 represents a grid cell, not a co-located reference instrument. No causal interpretation is made.
