# Analytical Integrity & Methodology Rules

> **Scope:** Exploratory Data Analysis, Statistical Inference, Regression, Classification, and Visualization.  
> **Source Document:** [`docs/roadmap.md`](file:///C:/Users/Admin/Documents/code_workspace/khdl/docs/roadmap.md) (Chapters 3 & 4, Weeks 6–11).

---

## 1. Exploratory Data Analysis (EDA)

1. **"Shape Picks the Statistic":**
   - Always characterize the distribution shape before calculating summary measures.
   - For urban $\text{PM}_{2.5}$ distributions exhibiting strong right-skewness ($\text{Skewness} > 1.0$) and fat tails ($\text{Kurtosis} > 3.0$):
     - **Primary Location:** Report **Median** ($P_{50}$), not Mean.
     - **Primary Spread:** Report **IQR** ($Q_3 - Q_1$), not Standard Deviation.
     - Explain why Mean/Std distort typical exposure when pulled by episodic winter inversions.
2. **The 4 Metric Families:**
   - Any profile of a numerical feature must report across all 4 families:
     1. *Location:* Mean, Median.
     2. *Spread:* Std, IQR, Range ($\max - \min$).
     3. *Shape:* Skewness, Kurtosis.
     4. *Quantiles:* $P_{10}, P_{25}, P_{50}, P_{75}, P_{90}, P_{95}, P_{99}$.
3. **Temporal Cycle Deconstruction:**
   - Analyze air pollution across three concurrent cyclical tiers:
     - **Diurnal (Hourly):** Identify morning rush-hour peak ($07:00–09:00$) and evening peak ($18:00–21:00$) vs. afternoon dilution ($13:00–15:00$).
     - **Day-of-Week:** Test the "weekend effect" (reduced vehicle emissions on Sat/Sun).
     - **Seasonal (Monthly):** Contrast winter stagnation/dry season (Nov–Feb) against summer monsoon convective scavenging (May–Aug).
4. **Anscombe & Datasaurus Guardrail:**
   - Never report correlation coefficients without inspecting scatter plots.
   - Calculate both **Pearson $r$** (linear association) and **Spearman $\rho$** (monotonic association). For non-linear weather interactions (e.g. wind speed vs. PM2.5 dispersion), prioritize Spearman $\rho$.

---

## 2. Statistical Inference ("Inference is a Leap")

1. **Explicit Hypothesis Formulation:**
   - State null ($H_0$) and alternative ($H_1$) hypotheses explicitly in scientific terms before executing tests.
2. **Normality Testing & Test Selection:**
   - Test distributional normality using the Shapiro-Wilk test (`scipy.stats.shapiro`).
   - If normality is violated ($p < 0.05$, expected for pollution data):
     - **Do NOT use Student's t-test or ANOVA.**
     - **Use non-parametric tests:** Two-sample **Mann-Whitney U** (`scipy.stats.mannwhitneyu`) or **Wilcoxon signed-rank** test.
3. **The Mandatory Reporting Trio:**
   - An isolated $p$-value is **never acceptable**. Every hypothesis test report must present:
     1. **Test Statistic & $p$-value** (e.g. $U = 142050, p < 0.001$).
     2. **Effect Size:** Compute Rank-Biserial Correlation ($r_{rb} = 1 - \frac{2U}{n_1 n_2}$) or Cliff's Delta.
     3. **Confidence Interval:** 95% Bootstrap Confidence Interval on the median difference ($\ge 1,000$ iterations).
4. **Statistical vs. Practical Significance:**
   - In large hourly datasets ($N > 10,000$), microscopic differences ($< 1.5\,\mu\text{g/m}^3$) can achieve $p < 0.001$. Never claim a finding is "impactful" solely on a low $p$-value; evaluate the practical effect size.

---

## 3. Regression Modeling (OLS & LINE Diagnostics)

1. **Target Formulation:**
   - Model transformed target $Y = \log(1 + \text{PM}_{2.5})$ (`np.log1p`) to linearize exponential atmospheric dispersion dynamics and stabilize residual variance.
2. **Strict Chronological Split:**
   - Partition train and test strictly chronologically (e.g. earlier 70–80% continuous partition for training, contiguous final 20–30% partition for testing, or historical training year vs evaluation period). **Never use random k-fold or random train_test_split.**
3. **Mandatory Baseline:**
   - Always evaluate models side-by-side with a DummyRegressor predicting the training mean ($\hat{y} = \bar{y}_{\text{train}}$).
   - Report Test Set metrics: **MAE**, **RMSE**, and **$R^2$**.
4. **The 4 LINE Assumptions Diagnostic Checklist:**
   Before trusting any OLS model, verify all 4 LINE assumptions on residuals:
   - **L (Linearity):** Plot Residuals vs. Fitted values. Check for curved patterns; resolve with non-linear terms or log-transforms.
   - **I (Independence):** Check Durbin-Watson statistic ($d \approx 2$). Address temporal auto-correlation with lag variables (`pm25_lag24`).
   - **N (Normality):** Q-Q plot and Shapiro-Wilk test on residuals.
   - **E (Equal Variance / Homoscedasticity):** Check Residuals vs Fitted spread for funnel shapes. Apply Breusch-Pagan test; consider Huber Regressor or Ridge ($L_2$) if heteroscedastic.
5. **Multicollinearity & Influential Points:**
   - Compute Variance Inflation Factor (**VIF**). If $\text{VIF} > 5.0$, eliminate collinear weather variables or regularize with Ridge/Lasso.
   - Compute **Cook's Distance**. Inspect points with $D_i > 0.5$ for data collection errors.
6. **The 3 Mandatory Obligations of Coefficient Interpretation ($\beta$):**
   When interpreting regression weights, you MUST fulfill 3 obligations:
   - State **association**, never causation (*"each 1 m/s increase in wind speed is associated with..."* — NEVER *"causes"*).
   - State **ceteris paribus** (*"holding all other weather variables in the model constant"*).
   - State the **observed range** (*"within the observed wind speed range of 0.2 to 8.5 m/s"*).

---

## 4. Classification & Early Alert Modeling

1. **Binary Target Definition:**
   - Class 1 (Unhealthy / Alert) vs. Class 0 (Acceptable / Normal): Defined using an explicitly documented regulatory or health threshold (e.g. QCVN 05:2023/BTNMT 24h average limit of $45\,\mu\text{g/Nm}^3$ effective 01/01/2026, transitional $50\,\mu\text{g/m}^3$, or WHO 2021 interim guidelines) applied on 24-hour aggregated values with proper unit/condition reconciliation, or an hourly advisory threshold explicitly documented in the modeling specification.
2. **Class Imbalance & The Accuracy Trap:**
   - High pollution days comprise only $\approx 15 - 25\%$ of observations.
   - **Accuracy is forbidden as a solitary performance metric.** A trivial model predicting all zeros achieves $80\%$ accuracy but has a catastrophic $0\%$ Recall.
3. **Core Performance Metrics:**
   - Prioritize **Recall** and **PR-AUC** (Area Under the Precision-Recall Curve).
   - *Public Health Rationale:* A False Negative (failing to alert vulnerable citizens during a hazardous episode) causes severe health harm, whereas a False Positive (unneeded advisory) carries low cost.
4. **Decision Threshold Tuning:**
   - Calibrate decision thresholds explicitly (e.g. lowering threshold from $0.50$ to $0.30$) to optimize Recall for Class 1. Document the clinical/policy trade-off.
   - **Never tune a threshold against the final test set.** Determine optimal thresholds strictly on a validation partition (or time-series cross-validation on training data); evaluate once on the untouched test partition.
5. **The 4-Way Data Leakage Audit:**
   - **Target Leakage:** Exclude variables directly calculated from the target (e.g. AQI).
   - **Train-Test Contamination:** Scalers/Imputers must be fit strictly on the training partition via Scikit-Learn `Pipeline`.
   - **Temporal Leakage:** Features must strictly represent past data ($t - k$). Split train/test chronologically.
   - **Group Leakage:** Ensure observations from the same calendar day do not bleed across both train and test splits.

---

## 5. Visual Standards (Edward Tufte & Cleveland Guidelines)

1. **High Data-Ink Ratio:**
   - Remove non-data ink: strip heavy chart borders, remove top and right spines, eliminate background grey shading, soften grid lines.
2. **Conclusion-Driven Titles:**
   - Titles must state the empirical insight, not the variable names.
   - *Bad:* "PM2.5 vs Month Boxplot"
   - *Good:* *"Winter records 2.8x higher median PM2.5 than summer due to atmospheric temperature inversion"*
3. **Zero-Baseline Mandate for Bar Charts:**
   - Every bar chart must begin at zero on the quantitative axis. Truncated bar axes are misleading.
4. **Visual Hierarchy & Formatting:**
   - Always label both axes with metric names and units ($\mu\text{g/m}^3$, $^\circ\text{C}$, $\text{m/s}$, $\%$).
   - Use colorblind-safe palettes (e.g., Seaborn `colorblind` or `viridis`).
   - Prohibit 3D charts, pie charts, and rainbow colormaps.
