---
name: classification
description: Develop, calibrate, and evaluate early-alert binary classification models for hazardous air pollution events, handling class imbalance, optimizing Recall and PR-AUC, tuning decision thresholds, and auditing for data leakage.
---

# Classification & Early Alert Modeling Skill

## Purpose
Build, tune, and evaluate an interpretable binary classification model designed to issue early alerts for hazardous air pollution episodes. Enforces public-health metric priorities (optimizing **Recall** and **PR-AUC** over raw Accuracy), conducts rigorous decision threshold calibration without test-set contamination, and audits for all 4 types of data leakage.

## When to Use
- When executing Milestone 4 (Week 11) in `notebooks/06_classification_alerts.ipynb`.
- When developing an early-warning system for days exceeding national health thresholds.
- When evaluating model trade-offs under class imbalance and tuning probability thresholds.

## Preconditions
- Clean, merged dataset in `data/processed/air_pollution_final.parquet`.
- Feature set with temporal lags (`pm25_lag24`, rolling statistics) and surface meteorology.

## Procedure

### 1. Binary Target Definition & Imbalance Analysis
- **Target Variable ($Y \in \{0, 1\}$):**
  - Class 1 (Unhealthy / Alert): $\text{PM}_{2.5} \ge 50\,\mu\text{g/m}^3$ (QCVN 05:2023/BTNMT 24-hour limit).
  - Class 0 (Acceptable / Normal): $\text{PM}_{2.5} < 50\,\mu\text{g/m}^3$.
- **Class Imbalance Quantification:**
  - Compute positive class prevalence: $\text{Prevalence} = \frac{\sum Y}{N}$.
  - Note: In Hanoi, hazardous days typically constitute $\approx 15 - 25\%$ of observations.
  - **The Accuracy Trap:** A naive classifier predicting Class 0 for every instance achieves $80\%$ accuracy but has a catastrophic $0\%$ Recall, failing to warn the public of any pollution crisis.

### 2. The 4-Way Data Leakage Audit
Audit the feature engineering pipeline against all 4 forms of leakage:
1. **Target Leakage:** Exclude derived air quality indices (e.g. `AQI`, `pm10_ratio`) calculated directly from $\text{PM}_{2.5}$.
2. **Train-Test Contamination:** Encapsulate all feature transformations (imputation, scaling) inside a Scikit-Learn `Pipeline`. Fit transformers strictly on the training partition.
3. **Temporal Leakage:** Lag and rolling features must use strictly backward-looking time windows ($t - k$). Split chronologically.
4. **Group Leakage:** Ensure observations from the same calendar day do not appear in both training and test partitions.

### 3. Chronological 3-Way Partitioning
Partition the continuous time series into three chronological segments:
- **Train Split (e.g. 2023 Jan–Sep):** Model parameter estimation.
- **Validation Split (e.g. 2023 Oct–Dec):** Threshold tuning and hyperparameter selection.
- **Test Split (e.g. 2024 Jan–Dec):** Final, untouched out-of-sample evaluation.

### 4. Model Training & Baselines
Train three distinct models for comparison:
1. **Baseline Model:** `DummyClassifier(strategy='stratified', random_state=42)`.
2. **Interpretable Benchmark:** `LogisticRegression(class_weight='balanced', max_iter=1000)`.
3. **Non-linear Ensemble:** `RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)`.

### 5. Multi-Metric Evaluation & PR Curve
- Compute comprehensive evaluation metrics on the Validation set:
  - **Precision:** $\frac{TP}{TP + FP}$ (proportion of alerts that were genuine).
  - **Recall (Sensitivity):** $\frac{TP}{TP + FN}$ (proportion of actual hazardous episodes successfully alerted).
  - **F1-Score:** Harmonic mean of Precision and Recall.
  - **PR-AUC:** Area under the Precision-Recall curve (standard metric for imbalanced detection).
  - **Confusion Matrix:** Explicit count of $TP, FP, TN, FN$.

### 6. Public-Health Threshold Tuning
- **Public-Health Objective:** A False Negative (failing to alert asthmatic or vulnerable populations to dangerous air) carries severe medical and moral costs, whereas a False Positive (advisory when air is moderate) incurs low cost.
- **Tuning Procedure:**
  - Generate predicted probabilities on the **Validation set**: $\hat{p} = P(Y=1 \mid X)$.
  - Evaluate Recall, Precision, and F1 across threshold sweep: $\tau \in [0.10, 0.90]$ with step $0.05$.
  - Select optimal threshold $\tau^*$ (e.g. $\tau^* = 0.30$) maximizing Recall while maintaining acceptable Precision ($> 60\%$).
- **Strict Prohibition:** **NEVER tune the decision threshold on the Test set.** Evaluate the chosen $\tau^*$ on the Test set once to record final unbiased metrics.

## Validation
- Confirm the model is compared side-by-side with the DummyClassifier baseline.
- Verify that both PR-AUC and ROC-AUC are reported, with PR-AUC prioritized.
- Ensure the decision threshold was selected using the Validation partition, not the Test set.

## Failure Modes
- Reporting Accuracy alone as evidence of model success on imbalanced data.
- Tuning decision thresholds on the final Test set, invalidating test set independence.
- Using future weather observations to predict today's alert status (future leakage).

## Expected Output
1. Model comparison table (Baseline vs. Logistic Regression vs. Random Forest) reporting Precision, Recall, F1, and PR-AUC.
2. Precision-Recall curve with tuned threshold $\tau^*$ annotated.
3. Confusion matrix comparing standard ($\tau=0.50$) vs. tuned ($\tau^*=0.30$) performance on the independent Test set.
