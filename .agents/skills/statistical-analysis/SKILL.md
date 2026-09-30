---
name: statistical-analysis
description: Conduct rigorous hypothesis testing, check distributional assumptions, calculate non-parametric effect sizes, and estimate bootstrap confidence intervals without relying solely on isolated p-values.
---

# Statistical Analysis & Inference Skill

## Purpose
Execute statistically sound inferential analyses on environmental time-series data. Strictly enforces the **Mandatory Reporting Trio** ($\text{Test Statistic} + p\text{-value} + \text{Effect Size} + 95\%\text{ Bootstrap Confidence Interval}$), validates distributional assumptions prior to test selection, and distinguishes statistical significance from practical, public-health significance.

## When to Use
- When executing Milestone 4 (Week 9) in `notebooks/04_statistical_inference.ipynb`.
- When comparing pollution levels across seasons (Winter vs. Summer) or calendar cycles (Weekday vs. Weekend).
- When benchmarking annual ambient exposure against national regulatory standards (QCVN 05:2023/BTNMT).
- When reporting uncertainty and confidence bounds for descriptive estimates.

## Preconditions
- Cleaned observational dataset in `data/processed/air_pollution_final.parquet`.
- Explicit research hypotheses ($H_0, H_1$) defined in [`docs/roadmap.md`](../../../docs/roadmap.md) (RQ2, SQ2).

## Procedure

### 1. Pre-Analysis Assumption Testing
- Before choosing a test, formally evaluate distributional normality on the groups:
  ```python
  from scipy.stats import shapiro
  stat, p_val = shapiro(sample_data[:5000])  # limit sample size if needed
  ```
- **Decision Rule:**
  - If $p < 0.05$ (normality rejected, standard for right-skewed $\text{PM}_{2.5}$): **Student's t-test and ANOVA are strictly prohibited.**
  - Proceed with non-parametric tests: **Mann-Whitney U** for two independent groups, or **Wilcoxon signed-rank** for paired/one-sample tests.
  - Document the statistical justification in the narrative prior to execution.

### 2. Hypothesis Testing Execution

#### Test A: Winter vs. Summer $\text{PM}_{2.5}$ Concentration
- **Hypotheses:**
  - $H_0: \tilde{\mu}_{\text{Winter}} = \tilde{\mu}_{\text{Summer}}$ (Medians are equal).
  - $H_1: \tilde{\mu}_{\text{Winter}} > \tilde{\mu}_{\text{Summer}}$ (Winter median is strictly greater — one-sided).
- **Execution:**
  ```python
  from scipy.stats import mannwhitneyu
  u_stat, p_val = mannwhitneyu(winter_pm25, summer_pm25, alternative='greater')
  ```

#### Test B: Weekday vs. Weekend Pollution Levels
- **Hypotheses:**
  - $H_0: \tilde{\mu}_{\text{Weekday}} = \tilde{\mu}_{\text{Weekend}}$.
  - $H_1: \tilde{\mu}_{\text{Weekday}} \ne \tilde{\mu}_{\text{Weekend}}$ (Two-sided).
- **Execution:**
  ```python
  u_stat, p_val = mannwhitneyu(weekday_pm25, weekend_pm25, alternative='two-sided')
  ```

### 3. Effect Size Estimation
Never report a $p$-value in isolation. Compute non-parametric effect sizes:
- **Rank-Biserial Correlation ($r_{rb}$):**
  $$r_{rb} = 1 - \frac{2U}{n_1 n_2}$$
  - $|r_{rb}| < 0.1$: Negligible
  - $0.1 \le |r_{rb}| < 0.3$: Small
  - $0.3 \le |r_{rb}| < 0.5$: Medium
  - $|r_{rb}| \ge 0.5$: Large

### 4. Non-Parametric Bootstrap Confidence Interval
Calculate 95% Confidence Intervals for the median difference via non-parametric bootstrapping ($\ge 1,000$ iterations):
```python
def bootstrap_median_diff(sample1, sample2, n_boot=1000, seed=42):
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        b1 = rng.choice(sample1, size=len(sample1), replace=True)
        b2 = rng.choice(sample2, size=len(sample2), replace=True)
        diffs.append(np.median(b1) - np.median(b2))
    ci_lower = np.percentile(diffs, 2.5)
    ci_upper = np.percentile(diffs, 97.5)
    return ci_lower, ci_upper
```

### 5. Contextual & Practical Interpretation
- Differentiate statistical power from real-world magnitude:
  - If $p < 0.001$ but the median difference is only $1.2\,\mu\text{g/m}^3$ and $r_{rb} = 0.04$, state clearly that the finding lacks practical air-quality significance.
  - If $p < 0.001$ with a large median difference ($31.3\,\mu\text{g/m}^3$, $r_{rb} = 0.64$, 95% CI $[27.8, 34.9]$), affirm that winter seasonality represents an actionable public-health hazard.

## Validation
- Verify the mandatory trio is complete for all tests: Test Statistic + $p$-value + Effect Size + 95% Bootstrap CI.
- Confirm deterministic execution by asserting a fixed seed (`seed=42`) in bootstrap functions.

## Failure Modes
- Reporting $p < 0.001$ and concluding "highly significant" without calculating effect size or CI.
- Applying Student's t-test to skewed raw particulate concentrations without normality justification.
- Inventing or rounding $p$-values to zero instead of reporting $p < 0.001$.

## Expected Output
1. Structured statistical inference markdown report in `reports/inference_results.md`.
2. Clean code cells in `notebooks/04_statistical_inference.ipynb` pairing statistical statements with rigorous interpretations.
