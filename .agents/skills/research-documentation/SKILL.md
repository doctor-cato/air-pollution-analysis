---
name: research-documentation
description: Author authoritative academic documentation, Data Dictionaries, Cleaning Logs, Datasheets for Datasets, 1-page Model Cards, Ethics/Bias audits, and AI usage declarations with rigorous traceability.
---

# Research Documentation Skill

## Purpose
Produce rigorous academic documentation and accountability artifacts required by course **INFO3020** and scientific publication standards. Governs the authoring of the **Data Dictionary**, **Cleaning Log**, **Datasheet for Dataset**, **Model Card**, **Ethics & Bias Audit**, and **AI Usage Declaration**, ensuring 100% traceability between reported claims and verified experimental results.

## When to Use
- When documenting data variables in `docs/data_dictionary.md` (Week 2).
- When recording cleaning decisions in `docs/cleaning_log.md` (Weeks 3–5).
- When preparing the Midterm Report (Week 8) or Final Capstone Report (Weeks 14–15).
- When authoring the Datasheet for Dataset and Model Card in `docs/` (Week 12).
- When updating AI usage declarations in `README.md`.

## Preconditions
- Data transformations or model executions have been completed and verified on disk.
- Exact numeric counts, metrics, or API parameters are available from executed code.

## Procedure

### 1. Data Dictionary Authoring (`docs/data_dictionary.md`)
Every collected or engineered variable must be cataloged in a structured markdown table:
- **Variable Name:** Exact code identifier (e.g. `pm25`, `wind_speed`, `is_winter`).
- **Data Type:** Native pandas dtype (`datetime64[ns, Asia/Ho_Chi_Minh]`, `float64`, `int8`).
- **Physical Units:** Explicit measurement unit ($\mu\text{g/m}^3$, $^\circ\text{C}$, $\text{m/s}$, $\text{hPa}$, $\%$).
- **Sampling Frequency:** Temporal granularity (hourly, 24h rolling, static).
- **Analytical Role:** Predictor ($X$), Target ($Y$), Filter, or Metadata.
- **Upstream Source:** Exact API endpoint or derivation formula.

### 2. Cleaning Log Maintenance (`docs/cleaning_log.md`)
Every data filtering, imputation, or nullification step must be recorded immediately:
- **Timestamp / Stage:** Date and pipeline stage of the change.
- **Target Column(s):** Variable(s) affected.
- **Operation:** Exact transformation (e.g., linear interpolation $\le 2$h, nullification of $\text{PM}_{2.5} > \text{PM}_{10}$).
- **Row Count Affected:** Exact number of rows modified and percentage of total dataset.
- **Scientific/Business Rationale:** Why this operation was required under atmospheric physics or sensor specs.

### 3. Datasheet for Dataset Authoring (`docs/datasheet.md`)
Follow the Timnit Gebru et al. standard across 6 standardized sections:
1. *Motivation:* Created for INFO3020 academic air pollution and public health early-warning research.
2. *Composition:* 2-year hourly records (2023–2024) from US Embassy Hanoi BAM 1020 + Open-Meteo ERA5.
3. *Collection Process:* Automated REST API retrieval with monthly chunking and rate limits.
4. *Preprocessing & Cleaning:* Time-grid reindexing, physical bound validation, and Parquet export.
5. *Uses & Limitations:* Valid for urban central Hanoi temporal research; **prohibited** for commercial real-time navigation or legal enterprise enforcement.
6. *Distribution & Maintenance:* Maintained under open licenses (ODC-BY and CC BY 4.0).

### 4. Model Card Authoring (`docs/model_card.md`)
Follow the Margaret Mitchell et al. 1-page standard:
1. *Model Details:* Early Air Quality Alert Classifier v1 (Random Forest with threshold $\tau^* = 0.30$).
2. *Intended Use:* Public health advisories for sensitive populations in urban Hanoi.
3. *Factors & Subgroups:* Seasonal performance breakdown (Winter vs. Summer Recall).
4. *Metrics:* Prioritizes **Recall** and **PR-AUC** over raw Accuracy.
5. *Training & Evaluation Data:* Train (2023), Validation (threshold tuning), Test (2024).
6. *Ethical Considerations & Caveats:* False Positives carry minimal burden; False Negatives leave citizens unprotected. Does not generalize to extreme unobserved catastrophes (e.g. massive industrial fires).

### 5. Ethics & Bias Audit
Document the three core biases inherent in urban environmental sensing:
- **Sensor Bias:** Low-cost optical sensors suffer from fog scattering noise when $\text{RH} > 90\%$.
- **Spatial Representation Bias:** Monitored station is located in an affluent central diplomatic district, failing to reflect higher exposure in peri-urban industrial craft villages.
- **Survivorship / Missingness Bias:** Extreme storm events disrupt power and communications, making rain-related missing data MAR rather than MCAR.

### 6. AI Usage Declaration (`README.md`)
Provide a transparent statement of AI assistance:
- Specific tools utilized (e.g. Google Antigravity / Gemini).
- Exact scope of assistance: code scaffolding, documentation formatting, test generation.
- Explicit student affirmation: **100% of mathematical logic, statistical choices, and code behavior are fully understood and defended by the authors in oral viva examination.**

## Validation
- **Zero Fabrication Rule:** Every numeric value in documentation (counts, percentages, metrics) must trace to an executed script or saved artifact.
- **Separation of Planned vs. Completed:** Planned work must be labeled **PLANNED SPECIFICATION**; completed work must cite verified outputs.

## Failure Modes
- Documenting roadmap milestones as completed when the underlying code has not been written.
- Omitting physical units from the Data Dictionary.
- Copying generic AI boilerplate without tailoring to the Hanoi air-pollution domain.

## Expected Output
1. Authoritative Data Dictionary in `docs/data_dictionary.md`.
2. Traceable Cleaning Log in `docs/cleaning_log.md`.
3. Standardized `docs/datasheet.md` and `docs/model_card.md`.
4. Transparent AI Declaration section in `README.md`.
