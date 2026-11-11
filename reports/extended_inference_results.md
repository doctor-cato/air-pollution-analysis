# Issue #50 — extended W9 inference

Dataset version: `2.0.0-issue44-extended`; actual SHA-256: `124c7fc851b89114d7734ed73e4834945d2f589cec263ffe443f23956d35bb4b`.
Configuration: 18 observed hours/day, CI B=1000, null B=5000, block=28 calendar days, HAC lag=28, seed=42; Holm family fixed at four tests per station.
The 18/24 rule is a study completeness rule, not a legal QCVN definition. Seasonal tests remain exploratory (R5). The QCVN 50 µg/m³ daily comparator follows the existing W9 contract; no legal compliance determination is made.

| Station | Grid hours | Observed hours | Eligible days | Daily median (µg/m³) | Days >50 / eligible | Daily rho1 | n_eff (AR1 approximation) |
|---|---:|---:|---:|---:|---:|---:|---:|
| VN001_HANOI_556_NGUYEN_VAN_CU | 9,044 | 7,495 | 299 | 37.20 | 84/299 | 0.728 | 47.1 |
| VN003_HANOI_OPENAQ_7441 | 28,678 | 18,208 | 756 | 39.61 | 238/756 | 0.749 | 108.7 |

Full statistics, effect sizes, dependence-aware p, Holm p, assumptions, and CIs: `reports/extended_inference_results.csv`. Sensitivity: `reports/extended_inference_sensitivity.csv`.
A seasonal omnibus epsilon-squared has no single contrast CI; the reported CI belongs to the winter–summer median contrast. For weekday, the primary HAC test estimates a trend-adjusted mean contrast, while r_rb and the median-contrast CI describe the nonparametric reference and have different estimands. Associations are observational, not causal. The calendar mask is retained in src/inference.py's bootstrap.
Open-Meteo raw snapshot byte match: False. Daily PM2.5 inference uses observed OpenAQ readings, not ERA5 weather.
