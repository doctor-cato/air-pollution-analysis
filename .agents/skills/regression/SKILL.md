---
name: regression
description: Build interpretable Ordinary Least Squares (OLS) regression models, verify all 4 LINE diagnostic assumptions, detect multicollinearity via VIF, evaluate Cook's distance, and interpret coefficients without causal fallacies.
---

# Regression Analysis Skill

## Purpose
Formulate, estimate, and rigorously diagnose linear regression models quantifying the observational association between surface meteorology and fine particulate matter ($\text{PM}_{2.5}$). Enforces the **4 LINE Diagnostics**, checks multicollinearity via Variance Inflation Factors (VIF), assesses influential points via Cook's Distance, compares against regularized estimators (Ridge/Lasso), and ensures valid non-causal coefficient interpretation.

## When to Use
- When executing Milestone 4 (Week 10) in `notebooks/05_regression_modeling.ipynb`.
- When quantifying how temperature, humidity, wind speed, and pressure relate to air quality.
- When generating residual diagnostic plots and verifying OLS assumptions.

## Preconditions
- Clean, integrated time-series data available in `data/processed/air_pollution_final.parquet`.
- Temporal train/test partitions generated (Train: 2023, Test: 2024).

## Procedure

### 1. Problem Formulation & Feature Space Setup
- **Dependent Variable ($Y$):** Apply log-transformation $Y = \log(1 + \text{PM}_{2.5})$ (`np.log1p`) to linearize exponential dispersion physics and stabilize residual variance.
- **Predictor Set ($X$):**
  - Meteorological drivers: `temperature`, `relative_humidity`, `wind_speed`, `surface_pressure`.
  - Autoregressive memory: `pm25_lag24` (concentration 24 hours prior).
- **Mandatory Baseline:** Instantiate a DummyRegressor predicting the training mean ($\hat{y} = \bar{y}_{\text{train}}$) as an essential reference point.

### 2. Preprocessing & Partitioning
- Enforce strict temporal split: Train on 2023, evaluate on 2024.
- Fit `RobustScaler` strictly on the training partition within a Scikit-Learn `Pipeline` or `statsmodels` formulation. Never fit scalers on the full dataset.

### 3. Model Estimation
- Estimate model parameters using `statsmodels.api.OLS` to extract comprehensive econometric summaries ($t$-stats, $p$-values, confidence intervals, $R^2$, Adj-$R^2$, AIC/BIC).

### 4. The 4 LINE Diagnostic Assumptions Checklist

| Assumption | Tool / Test | Evaluation Criteria & Mitigation |
|---|---|---|
| **L – Linearity** | Residuals vs. Fitted plot | Residuals must scatter randomly around 0 without parabolic curvature. If non-linear, add quadratic terms or splines. |
| **I – Independence** | Durbin-Watson statistic ($d$) | $d$ should be close to $2.0$ ($1.5 < d < 2.5$). If $d \ll 2$, strong positive autocorrelation exists $\to$ incorporate `pm25_lag24` or AR terms. |
| **N – Normality** | Q-Q Plot & Shapiro-Wilk on residuals | Points should track the diagonal. Small tail departures are tolerated under Central Limit Theorem ($N > 8,000$), but severe deviation requires target re-scaling. |
| **E – Equal Variance** | Residuals vs. Fitted spread / Breusch-Pagan | Check for funnel/trumpet shape. If heteroscedastic, evaluate robust standard errors (HC3) or Huber Regressor. |

### 5. Multicollinearity & Influential Observation Audit
- **Variance Inflation Factor (VIF):**
  - Calculate VIF for each predictor:
    $$\text{VIF}_j = \frac{1}{1 - R_j^2}$$
  - If $\text{VIF} > 5.0$, severe multicollinearity exists (common between temperature and surface pressure). Eliminate redundant features or switch to **Ridge Regression ($L_2$)**.
- **Influential Points (Cook's Distance):**
  - Compute Cook's Distance $D_i$.
  - Inspect points where $D_i > 0.5$ or $D_i > \frac{4}{n}$.
  - **Golden Rule:** **NEVER delete observations simply because they reduce $R^2$ or create high residuals.** Only correct verified sensor hardware corruption.

### 6. Regularization Comparison (Ridge vs. Lasso)
- Train Ridge ($L_2$) and Lasso ($L_1$) regressors using cross-validated penalty tuning (`RidgeCV`, `LassoCV`) strictly on the training split to assess coefficient shrinkage and feature selection.

### 7. The 3 Mandatory Obligations of Coefficient Interpretation ($\beta$)
Every reported regression coefficient $\beta_j$ must be interpreted under these 3 strict obligations:
1. State **association**, never causation (*"associated with an average change of..."* — NEVER *"causes"* or *"drives"*).
2. Explicitly include the **ceteris paribus** condition (*"holding all other variables in the model constant"*).
3. State the **observed domain range** of the predictor (*"over the observed wind speed range of 0.2 to 8.5 m/s"*).

## Validation
- Compare Test Set performance (MAE, RMSE, $R^2$) against the DummyRegressor baseline.
- Verify that all 4 LINE diagnostic plots have been generated and visually reviewed.
- Confirm zero VIF values exceed $5.0$ in the final model specification.

## Failure Modes
- Reporting $R^2$ without inspecting residual plots or Durbin-Watson autocorrelation.
- Randomly splitting time-series data, producing artificially inflated $R^2 > 0.95$ due to temporal leakage.
- Discarding genuine extreme pollution events as "outliers" to artificially improve goodness-of-fit.

## Expected Output
1. Full OLS regression summary table with MAE, RMSE, and $R^2$ on the independent Test set.
2. 4 LINE diagnostic figures saved to `figures/fig_line_diagnostics.png`.
3. Standardized, non-causal interpretations for all significant meteorological coefficients.
