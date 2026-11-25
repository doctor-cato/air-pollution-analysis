# Model Card — Hanoi $\text{PM}_{2.5}$ Retrospective Alert Classifier & Explanatory Regression Models

> **Standard:** Margaret Mitchell et al. (2019), *Model Cards for Model Reporting* (1-page academic format, INFO3020 — Issue #14)  
> **Authors:** Topic 6 Team (Huy, Khương, Khánh, Hưng, Hùng) — CMC University  
> **Primary Evidence Sources:** [`reports/classification_results.md`](../reports/classification_results.md), [`docs/classification_findings.md`](classification_findings.md), [`reports/regression_results.md`](../reports/regression_results.md), [`docs/regression_findings.md`](regression_findings.md), [`docs/leakage_audit.md`](leakage_audit.md)

---

## 1. Model Details

| Component | Primary Alert Classifier (Issue #13) | Explanatory Regression Suite (Issue #12) |
|---|---|---|
| **Model Type & Version** | Binary Classifiers (`v1.0`): `LogisticRegression(class_weight='balanced')` & `RandomForestClassifier(class_weight='balanced', random_state=42)` wrapped in leak-safe `sklearn.pipeline.Pipeline` (`SimpleImputer(median)` + `RobustScaler`) | `OLS` (with Newey-West HAC-24 standard errors) + regularized `Ridge` & `Lasso` tuned via 5-fold `TimeSeriesSplit` |
| **Target Definition** | $y_t = \mathbb{I}\!\left(\overline{\text{PM}_{2.5}}_{[t-23, t]} \ge 50.0\ \mu\text{g/m}^3\right)$ (observed-only 24h rolling mean, `min_periods=24`, aligned to QCVN 05:2023/BTNMT 24h standard) | Observed hourly `pm25` ($\mu\text{g/m}^3$, uninterpolated) |
| **Feature Set** | 14 retrospective features: past-only `pm25` lags/rolling (`t-1..t-24`: `pm25_rolling_mean_24h`, `pm25_rolling_std_24h`, `pm25_lag24`) + Open-Meteo ERA5 weather + cyclic time (`hour_sin/cos`, `month_sin/cos`, `is_calm_wind`, `temp_humidity_interaction`). **Strictly excludes** `pm10` ($r=0.9727$), `pm25_was_missing`, `is_high_humidity_fog`, and `pm25_derived_interpolated` (in primary). | 9 features: 5 ERA5 weather variables (`temperature`, `relative_humidity`, `wind_speed`, `precipitation`, `surface_pressure`) + 4 cyclic calendar features (`hour_sin/cos`, `month_sin/cos`). AR ablation adds `pm25_lag24`. |
| **Decision Thresholding** | Out-of-fold (OOF) $F_2$-optimal threshold $\tau^*$ tuned **strictly on Train** and locked before Test evaluation (secondary operating point: Recall under `Precision >= 0.60`). | Continuous prediction ($\mu\text{g/m}^3$); **all 4 LINE assumptions violated** — coefficients are strictly *associational (ceteris paribus)*, never causal. |
| **Station Protocol** | **Protocol A (strict single-station)** — `VN001` and `VN003` are never pooled due to 0h overlap (2,040h gap, 7.324 km apart). | Same **Protocol A** enforcement (`src/regression.py`). |

---

## 2. Intended Use, Latency Constraint & Out-of-Scope Uses

- **Intended Use:** Academic research, retrospective air-quality episode analysis, and prototype decision-support methodology for public health risk communication in urban Hanoi (sensitive groups: children, elderly, respiratory patients).
- **Critical Operational Constraint (ERA5 ~5-Day Latency):** Meteorological inputs come from **Open-Meteo ECMWF ERA5 hourly reanalysis**, which carries a **~5-day publication latency**. Consequently, the $h = 0\text{h}$ classification setup is a **retrospective historical nowcast**, **NOT** a real-time operational alert system unless ERA5 inputs are replaced with live surface observations or Numerical Weather Prediction (NWP) forecasts with verified issue times.
- **Out-of-Scope Uses (Prohibited):**
  - Real-time automated public emergency broadcasting without live NWP/sensor integration and human oversight.
  - Legal QCVN regulatory compliance enforcement or enterprise liability attribution (models evaluate a single urban monitor using a 24h rolling completeness rule, not statutory multi-station compliance).
  - Extrapolation to peri-urban industrial zones, craft villages, or extreme unobserved shocks (e.g., major industrial fires, volcanic/transboundary smoke plumes outside training distributions).
  - Causal claims regarding meteorological interventions (OLS violates Linearity, Independence, Normality, and Equal Variance).

---

## 3. Stratified Quantitative Performance (Verbatim from Saved Reports)

### 3.1. Issue #13 Early-Alert Classifier — Test Set Results ($h = 0\text{h}$, Locked Train-OOF $F_2$ Threshold $\tau^*$)

*Sources: `reports/classification_results.md` (§2, VN001_extended_80_20, VN003_extended_2022_2025) & `docs/classification_findings.md` (§2, §4). Figures: [`precision_recall_curve.png`](../figures/precision_recall_curve.png), [`precision_recall_curve_vn001_extended.png`](../figures/precision_recall_curve_vn001_extended.png), [`precision_recall_curve_vn003_extended.png`](../figures/precision_recall_curve_vn003_extended.png), [`calibration_reliability.png`](../figures/calibration_reliability.png), [`calibration_reliability_vn001_extended.png`](../figures/calibration_reliability_vn001_extended.png), [`calibration_reliability_vn003_extended.png`](../figures/calibration_reliability_vn003_extended.png).*

| Cohort (Protocol A) | Test Evaluable (Pos / Prev) | Model (Threshold $\tau^*$) | Precision | Recall | FAR | F2 | PR-AUC | Brier / ECE | Confusion Matrix `[TN, FP, FN, TP]` | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| **`VN001_baseline_2026_01_15`** (`1.0.0-m2-baseline`, cut `2026-01-15`) | 2,302 (666 / 28.93%) | Prior Dummy (`0.50`) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2893 | 0.2073 / — | `[[1636, 0], [666, 0]]` | `OK` |
| | | Persistence Rule `>=50` (`0.50`) | 0.9865 | 0.9850 | 0.0055 | 0.9853 | 0.9992 | 0.0845 / 0.2592 | `[[1627, 9], [10, 656]]` | `OK` |
| | | **LogReg Balanced ($F_2$, `0.43`)** | **0.9418** | **0.9955** | **0.0251** | **0.9843** | **0.9989** | **0.0143 / 0.0351** | `[[1595, 41], [3, 663]]` | `OK` |
| | | **Random Forest Balanced ($F_2$, `0.32`)** | **0.9610** | **1.0000** | **0.0165** | **0.9920** | **0.9985** | **0.0134 / 0.0750** | `[[1609, 27], [0, 666]]` | `OK` |
| **`VN001_extended_80_20`** (`2.0.0-issue44-extended`, cut `2026-05-01`) | 242 (**0 / 0.00%**) | LogReg Balanced ($F_2$, `0.47`) | `UNESTIMABLE` | `UNESTIMABLE` | 0.0000 | `UNESTIMABLE` | `UNESTIMABLE` | 0.0008 / `UNESTIMABLE` | `[[242, 0], [0, 0]]` | **`UNESTIMABLE` (0 pos)** |
| | | Random Forest Balanced ($F_2$, `0.28`) | `UNESTIMABLE` | `UNESTIMABLE` | 0.0000 | `UNESTIMABLE` | `UNESTIMABLE` | 0.0013 / `UNESTIMABLE` | `[[242, 0], [0, 0]]` | **`UNESTIMABLE` (0 pos)** |
| **`VN003_extended_2022_2025`** (`2.0.0-issue44-extended`, cut `2024-08-13`) | 3,439 (1,713 / 49.81%) | Prior Dummy (`0.50`) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.4981 | 0.3107 / — | `[[1726, 0], [1713, 0]]` | `OK` |
| | | Persistence Rule `>=50` (`0.50`) | 0.9860 | 0.9860 | 0.0139 | 0.9860 | 0.9992 | 0.0732 / 0.2160 | `[[1702, 24], [24, 1689]]` | `OK` |
| | | **LogReg Balanced ($F_2$, `0.36`)** | **0.9553** | **0.9977** | **0.0463** | **0.9889** | **0.9995** | **0.0120 / 0.0176** | `[[1646, 80], [4, 1709]]` | `OK` |
| | | **Random Forest Balanced ($F_2$, `0.30`)** | **0.9703** | **0.9930** | **0.0301** | **0.9884** | **0.9983** | **0.0135 / 0.0343** | `[[1674, 52], [12, 1701]]` | `OK` |

> **Why `VN001_extended_80_20` is `UNESTIMABLE`:** Its 80/20 chronological Test window (`2026-05-01` to `2026-07-15`) falls entirely in the clean summer rainy season and suffers a **630-hour contiguous sensor outage** (`2026-06-19` to `2026-07-15`), yielding **0/242** positive 24h windows (`reports/classification_results.md`, §`VN001_extended_80_20`). Discrimination and calibration metrics are explicitly reported as `UNESTIMABLE` rather than imputed or hidden.

### 3.2. Issue #12 Explanatory Regression — Test Performance & LINE Diagnostics

*Sources: `reports/regression_results.md` (§0, §1–§3) & `docs/regression_findings.md` (§3–§5). Figures: [`regression_line_diagnostics.png`](../figures/regression_line_diagnostics.png), [`regression_line_diagnostics_vn001_extended.png`](../figures/regression_line_diagnostics_vn001_extended.png), [`regression_line_diagnostics_vn003_extended.png`](../figures/regression_line_diagnostics_vn003_extended.png).*

| Scope (Train / Test) | Dummy RMSE | OLS Test MAE / RMSE / $R^2$ | Ridge RMSE / $R^2$ | Lasso RMSE / $R^2$ | OLS + `pm25_lag24` Test $R^2$ | LINE Diagnostics (All 4 Violated) |
|---|---:|---:|---:|---:|---:|---|
| **`VN001_baseline_2026_01_15`** (`4,279 / 3,216`) | 24.46 | 37.32 / 41.46 / `-1.9540` | 39.97 / `-1.7457` | 41.91 / `-2.0182` | `+0.2245` | RESET(2) `F=223.27 (p=3.02e-49)`, `DW=0.2430`, `JB=392.7`, `BP=658.27` (65.0% Test outside Train `month_sin`) |
| **`VN001_extended_80_20`** (`6,749 / 746`) | 24.15 | 15.63 / 21.12 / `-0.1073` | 21.11 / `-0.1069` | 20.61 / `-0.0549` | `+0.0587` | RESET(2) `F=615.42 (p=4.40e-130)`, `DW=0.2079`, `JB=1641.1`, `BP=513.49` |
| **`VN003_extended_2022_2025`** (`13,835 / 4,373`) | 37.73 | 23.98 / 32.82 / **`+0.1498`** | 32.91 / `+0.1456` | 33.06 / `+0.1377` | **`+0.3490`** | RESET(2) `F=243.15 (p=2.35e-54)`, `DW=0.3033`, `JB=51355.1`, `BP=701.19` |

- **Most Stable Meteorological Association (HAC-24):** `wind_speed` maintains a robust negative association across all 3 scopes ($\beta = -6.0673$, $p_{\text{HAC-24}} = 5.63 \times 10^{-8}$ on `VN001_baseline`; $\beta = -7.2891$, $p = 6.48 \times 10^{-21}$ on `VN001_extended`; $\beta = -6.2864$, $p = 1.09 \times 10^{-44}$ on `VN003_extended`). No predictor exceeds $\text{VIF} \ge 10$ (`surface_pressure` `5.955–8.061`, `temperature` `5.730–7.655`).

---

## 4. Explainability & 23/24h Rolling-Window Overlap Insight

*Sources: `reports/classification_results.md` (§3–§4), `docs/classification_findings.md` (§1, §3), `docs/leakage_audit.md` (§3). Figures: [`feature_importance.png`](../figures/feature_importance.png), [`feature_importance_vn001_extended.png`](../figures/feature_importance_vn001_extended.png), [`feature_importance_vn003_extended.png`](../figures/feature_importance_vn003_extended.png).*

1. **Why $h = 0\text{h}$ PR-AUC $\approx 0.999$ (Not Leakage):** At $h = 0\text{h}$, `pm25_rolling_mean_24h` aggregates $[t-24, t-1]$ while target $y_t$ aggregates $[t-23, t]$, sharing **23/24 hours (95.8% window overlap)**. Four-layer leakage audit (`docs/leakage_audit.md`) verifies **PASS** on Target, Train-Test, Temporal (purge gap $t+h < t_{\text{split}}$), and Group/Station leakage.
2. **Feature Importance (`VN001_baseline_2026_01_15`):** Both RF MDI (`feature_importances_`) and 20-repeat Test `permutation_importance` (`average_precision`) are dominated by `pm25_rolling_mean_24h` (MDI `0.5763`, Perm `0.474302 ± 0.015432`, LogReg Coef `+11.5228`), followed by `pm25_lag24` (MDI `0.0855`, Perm `0.001424`) and `pm25_rolling_std_24h` (MDI `0.0697`, Perm `0.001000`). Among weather predictors, `wind_speed` leads (Perm `0.000407`, LogReg Coef `-0.3781`, OR `0.6852`). On `VN003_extended_2022_2025`, the same top-3 autoregressive order holds (`pm25_rolling_mean_24h` MDI `0.6225`, Perm `0.273909`).
3. **True Forecast Decay & Ablation:** Removing the 24h rolling feature drops `VN001_baseline` PR-AUC from `0.9989 / 0.9985` to `0.7908 / 0.7364` (Lag24 + Met) and `0.4338 / 0.5954` (Meteorology + Time Only). Extending to genuine future horizons with purge gaps lowers PR-AUC monotonically: `h=1h` (`0.9966 / 0.9951`) $\to$ `h=6h` (`0.9696 / 0.9509`) $\to$ `h=12h` (`0.9094 / 0.8586`) $\to$ `h=24h` (`0.7513 / 0.5876` on `VN001_baseline`; `0.8852 / 0.8479` on `VN003_extended`).

---

## 5. Ethical Considerations, Failure Modes & Caveats

- **Asymmetric Error Cost (FN vs. FP):**
  - **False Negatives (Missed Hazardous Episode):** High public-health cost — sensitive residents remain outdoors without N95/indoor precautions during $\ge 50\,\mu\text{g/m}^3$ episodes. Mitigated via $F_2$-tuned thresholds prioritizing Recall (`99.55%–100.00%` on `VN001_baseline`; `99.30%–99.77%` on `VN003_extended`).
  - **False Positives (Alert Fatigue):** Moderate behavioral cost — unnecessary advisories reduce public trust over time. Controlled via low False Alarm Rate (`FAR = 1.65%–2.51%` on `VN001_baseline`; `3.01%–4.63%` on `VN003_extended`).
- **Sensor, Spatial & Missingness Biases:** Detailed quantitatively in [`docs/bias_assessment.md`](bias_assessment.md) — includes non-MCAR multi-week outages (up to 630h on `VN001`, 2,568h on `VN003`), seasonal `RH > 90%` fog interaction ($F(3, 7487)=16.78, p=7.38 \times 10^{-11}$), single-station urban coverage, and ERA5 grid smoothing (`1.704 km` / `9.026 km`).
- **No SMOTE on Time Series:** Synthetic oversampling is strictly prohibited to avoid non-physical meteorological interpolation across seasons (`docs/leakage_audit.md` §2).
