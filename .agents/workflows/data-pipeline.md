# Data Pipeline Workflow

> **Purpose:** Standard procedure for collecting, auditing, cleaning, integrating, transforming, and persisting air quality and weather time-series data.

---

## 1. End-to-End Pipeline Sequence

```text
Source (OpenAQ S3 / API + Open-Meteo ERA5 Reanalysis)
       │
       ▼
Raw data (Preserved JSON files in data/raw/ + metadata.json per Three-tier policy)
       │
       ▼
Schema validation (Check required columns, datatypes, and timestamps)
       │
       ▼
Data-quality checks (6-dimension audit, disguised missing detection)
       │
       ▼
Cleaning (Domain physical bounds PM2.5 <= PM10, stuck values, fog flag)
       │
       ▼
Transformation (Reindex continuous 1h grid, safe join, RobustScaler, log1p)
       │
       ▼
Processed data (Snappy Parquet in data/processed/air_pollution_final.parquet)
       │
       ▼
Validation (Row counts, null rates, physical assertions, schema check)
       │
       ▼
Analysis (Downstream EDA, Statistical Inference, OLS Regression, Classification)
```

---

## 2. Core Operational Rules

1. **Three-Tier Raw Data Governance:** Raw API payloads stored in `data/raw/` are preserved without manual edits (Three-tier policy, roadmap §3.2) and verified via SHA-256 hashes recorded in `metadata.json`. Every transformation must be executed via deterministic code and saved to `data/processed/` (or `data/interim/`).
2. **Never Assume a Merge is Correct:** Always verify row counts before and after joining air and weather datasets to prevent Row Explosion bugs.
3. **Traceability:** Every cleaning decision, threshold, and row count change must be logged in [`docs/cleaning_log.md`](../../docs/cleaning_log.md).

---

## 3. Mandatory Validation Checklist

At every transition along the pipeline, validate these 9 criteria:

| Check | What to Validate | Validation Command / Code |
|---|---|---|
| **1. Schema** | Column presence and datatypes | `assert {'timestamp', 'pm25', 'pm10', 'temperature', 'wind_speed'}.issubset(df.columns)` |
| **2. Timestamps** | Chronological order & timezone | `assert df['timestamp'].is_monotonic_increasing and df['timestamp'].dt.tz is not None` |
| **3. Units** | Standard units ($\mu\text{g/m}^3, ^\circ\text{C}, \text{m/s}, \text{hPa}, \%$) | Cross-reference `docs/data_dictionary.md` |
| **4. Nulls** | Missing rates and mechanisms | Categorize into MCAR (random), MAR (storm), MNAR (extreme episode) |
| **5. Duplicates** | Zero duplicate station hours | `assert df['timestamp'].is_unique` |
| **6. Value Ranges** | Environmental physical bounds | `assert (df['pm25'] <= df['pm10'] + 2.0).all()`, `assert (df['pm25'] >= 0).all()` |
| **7. Temporal Coverage** | Continuous hourly grid over study period | Reindex against continuous hourly grid `pd.date_range(start, end, freq='h')` |
| **8. Join Coverage** | Matching time intersections | `assert not df_merged['temperature'].isna().all()` |
| **9. Row Counts** | No Row Explosion on merges | `assert len(df_merged) <= len(df_air)` |

---

## 4. Pipeline Execution Protocol

### Phase 1: Ingestion
- Ingest OpenAQ and Open-Meteo data using rate-limited requests (`time.sleep(1.0)`).
- Save raw responses to `data/raw/`. Create `data/raw/metadata.json` recording source URLs, query parameters, retrieval dates, and schema versions.

### Phase 2: Quality Audit
- Load data using [`data-quality`](../skills/data-quality/SKILL.md) skill.
- Score across the 6 quality dimensions and uncover disguised missing markers (`"-999"`, `"N/A"`).

### Phase 3: Cleaning & Time-Series Reindexing
- Apply physical rules: flag $\text{PM}_{2.5} > \text{PM}_{10}$ as `NaN`, remove negative values, detect stuck sensor series ($> 6$h identical float).
- Add boolean flags: `is_high_humidity_fog` when $\text{RH} > 90\%$ and `pm25` spikes.
- Reindex to a complete hourly time grid using [`time-series-analysis`](../skills/time-series-analysis/SKILL.md). Interpolate small gaps ($\le 2$h); flag large gaps ($> 6$h) with `pm25_was_missing = 1`.

### Phase 4: Integration
- Join `df_air` and `df_weather` on `timestamp` (UTC+7).
- Assert row counts match to guarantee no Cartesian row multiplication occurred.

### Phase 5: Pipeline Transformation & Storage
- Construct Scikit-Learn `Pipeline` with `ColumnTransformer`. Fit transformers strictly on the training partition.
- Export clean dataset to `data/processed/air_pollution_final.parquet` with Snappy compression.
- Update [`docs/cleaning_log.md`](../../docs/cleaning_log.md).
