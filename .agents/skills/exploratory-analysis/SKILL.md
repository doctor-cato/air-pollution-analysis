---
name: exploratory-analysis
description: Perform research-question-driven exploratory data analysis on air pollution and meteorology, profiling distribution shapes, 4-family statistics, multi-tier temporal cycles, and bivariate relationships.
---

# Exploratory Data Analysis (EDA) Skill

## Purpose
Execute systematic, research-question-driven Exploratory Data Analysis on multi-year time-series air pollution and weather data. Applies the foundational principle **"Shape picks the statistic"**, calculates the 4 metric families, decodes multi-tier temporal variations, investigates meteorological relationships, and translates numerical patterns into actionable domain insights.

## When to Use
- When executing Milestone 3 (Weeks 6–8) in `notebooks/03_exploratory_data_analysis.ipynb`.
- When preparing the Midterm EDA Report (`reports/midterm_report.pdf`).
- When evaluating distribution skewness and selecting central tendency metrics.
- Prior to specifying hypothesis tests or fitting predictive models.

## Preconditions
- Cleaned and joined dataset exists in `data/processed/air_pollution_final.parquet`.
- Primary research questions are defined in [`docs/roadmap.md`](../../../docs/roadmap.md) (Main RQ and SQ1–SQ4).

## Procedure

### 1. Dataset Understanding & Structural Inspection
- Inspect dataset dimensions, start/end dates, and memory consumption.
- Confirm temporal continuity: hourly granularity across 2023–2024.

### 2. Distribution Profiling & Shape Assessment
- Compute distribution shape parameters for $\text{PM}_{2.5}$ and $\text{PM}_{10}$:
  - **Skewness:** $\text{Skew} = \frac{n}{(n-1)(n-2)} \sum \left(\frac{x_i - \bar{x}}{s}\right)^3$. Values $> 1.0$ indicate severe right-skew.
  - **Kurtosis:** Values $> 3.0$ confirm fat-tailed (*leptokurtic*) behavior driven by extreme pollution episodes.
- **Select Summary Statistics Based on Shape:**
  - When $\text{Skewness} > 1.0$, establish **Median** and **IQR** as authoritative primary metrics.
  - Provide a quantitative comparison between Mean and Median (e.g. Mean $\approx 54\,\mu\text{g/m}^3$ vs. Median $\approx 38\,\mu\text{g/m}^3$), explaining how winter temperature inversions inflate the Mean.

### 3. Compute the 4 Metric Families
For every continuous environmental feature, report all 4 metric families:
1. *Location:* Mean, Median, Mode.
2. *Spread:* Standard Deviation, IQR ($Q_3 - Q_1$), Range ($\max - \min$).
3. *Shape:* Skewness, Kurtosis.
4. *Quantiles:* $P_{10}, P_{25}, P_{50}, P_{75}, P_{90}, P_{95}, P_{99}$.

### 4. Multi-Scale Temporal Pattern Deconstruction
Deconstruct time-series variations across three temporal tiers:
- **Diurnal Cycle (Hour of Day $0–23$):** Group by hour and calculate Median and IQR. Identify morning traffic rush ($07:00–09:00$) and evening rush ($18:00–21:00$) peaks, versus midday boundary layer dilution ($13:00–15:00$).
- **Day-of-Week Effect:** Compare Weekdays (Mon–Fri) vs. Weekends (Sat–Sun) to detect urban emission reductions.
- **Seasonal Cycle (Monthly):** Analyze month-by-month boxplots. Contrast winter dry-season pollution (Nov–Feb) against summer monsoon convective cleaning (May–Aug).

### 5. Meteorological Bivariate Relationships
- Generate scatter plots with LOWESS smoothing curves for key pairs:
  - $\text{PM}_{2.5}$ vs. `wind_speed` (evaluate mechanical dispersion).
  - $\text{PM}_{2.5}$ vs. `temperature` (evaluate thermal convection).
  - $\text{PM}_{2.5}$ vs. `relative_humidity` (evaluate hygroscopic growth vs. rain scavenging).
  - $\text{PM}_{2.5}$ vs. `surface_pressure` (evaluate atmospheric stability and winter high-pressure anticyclones).
- **Anscombe & Datasaurus Check:** Always visually inspect scatter plots before trusting correlation coefficients. Compute both **Pearson $r$** (linear) and **Spearman $\rho$** (monotonic/non-linear).

### 6. Synthesis & Hypothesis Generation
- Synthesize empirical findings into candidate hypotheses for statistical inference:
  - Is the winter vs. summer difference statistically significant?
  - Does the weekend traffic lull produce a measurable reduction in median exposure?

## Validation
- Verify that every produced visual answers an explicit research question.
- Confirm that distributions are explicitly tested for normality before any parametric metric is cited.
- Ensure all reported quantiles and summary tables match calculations from the clean Parquet file.

## Failure Modes
- Reporting only Mean and Standard Deviation on heavily skewed $\text{PM}_{2.5}$ data.
- Producing decorative 3D or rainbow charts that fail to convey actionable analytical insights.
- Making causal assertions (e.g. stating that low wind speed "causes" pollution rather than "is strongly associated with higher concentrations").

## Expected Output
1. Comprehensive 4-family statistical profile table saved to `reports/statistical_profile.csv`.
2. Narrative answers to Sub-Questions SQ1 and SQ2 documented in markdown.
3. Clean, publication-quality exploratory figures generated via the `data-visualization` skill.
