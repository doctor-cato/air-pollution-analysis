---
name: time-series-analysis
description: Perform robust time-series operations, timestamp normalization, continuous grid reindexing, rolling smoothing, classical decomposition, and strictly chronological train-test partitioning.
---

# Time-Series Analysis Skill

## Purpose
Enforce rigorous, leakage-free time-series protocols on continuous hourly air quality and meteorological observations. Handles datetime parsing, timezone harmonization, uniform grid reindexing, rolling trend extraction, cyclical decomposition, and chronological train/test partitioning.

## When to Use
- During data cleaning and feature engineering in `notebooks/02_quality_audit_cleaning.ipynb`.
- When calculating multi-scale rolling statistics (`pm25_rolling_mean_24h`, 7-day trend).
- When decomposing series into Trend, Seasonal, and Residual components.
- When splitting datasets into Train, Validation, and Test partitions for regression and classification.

## Preconditions
- Data contains a parseable datetime column representing hourly observation intervals.
- Target timezone is standard Vietnam local time: `Asia/Ho_Chi_Minh` (UTC+7).

## Procedure

### 1. Timestamp Normalization & Timezone Localization
- Convert string timestamps into timezone-aware datetimes:
  ```python
  df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('Asia/Ho_Chi_Minh')
  ```
- Verify monotonic chronological sort:
  ```python
  df = df.sort_values('timestamp').reset_index(drop=True)
  assert df['timestamp'].is_monotonic_increasing, "Timestamps out of chronological order!"
  ```

### 2. Time-Grid Reindexing & Gap Identification
- Construct a full, uninterrupted hourly grid covering the minimum and maximum period:
  ```python
  full_grid = pd.date_range(start=df['timestamp'].min(), end=df['timestamp'].max(), freq='h')
  df = df.set_index('timestamp').reindex(full_grid).rename_axis('timestamp').reset_index()
  ```
- Quantify duration and frequency of missing time blocks.

### 3. Temporal Resampling & Multi-Scale Rolling Statistics
- **24-Hour Rolling Mean:** Smooth diurnal fluctuations to expose multi-day pollution episodes:
  ```python
  df['pm25_rolling_24h'] = df['pm25'].rolling(window=24, min_periods=18).mean()
  ```
- **7-Day Rolling Trend:** Filter out intra-week noise to track synoptic weather patterns:
  ```python
  df['pm25_rolling_7d'] = df['pm25'].rolling(window=24 * 7, min_periods=24 * 5).mean()
  ```
- **Resampling Aggregations:** Downsample hourly series to daily (`'D'`) and monthly (`'M'`) medians for macro-trend visualization.

### 4. Classical Time-Series Decomposition
- Decompose the continuous series using additive or multiplicative models (`statsmodels.tsa.seasonal.seasonal_decompose`):
  $$Y_t = T_t + S_t + R_t$$
  - **Trend ($T_t$):** Long-term multi-month trajectory.
  - **Seasonal ($S_t$):** Periodic 24-hour diurnal or annual cycles.
  - **Residual ($R_t$):** Stochastic noise, episodic events (e.g. Lunar New Year fireworks, agricultural residue burning).

### 5. Leakage-Free Temporal Train/Test Separation
- **Strict Chronological Splitting Mandate:**
  - Training partition: Historical window (e.g. 2023-01-01 00:00:00 to 2023-12-31 23:00:00).
  - Testing partition: Subsequent future window (e.g. 2024-01-01 00:00:00 to 2024-12-31 23:00:00).
  ```python
  train_mask = df['timestamp'] < '2024-01-01'
  test_mask = df['timestamp'] >= '2024-01-01'
  train_df = df[train_mask].copy()
  test_df = df[test_mask].copy()
  ```
- **Prohibition:** NEVER use random shuffling or standard `train_test_split(shuffle=True)` for time-series modeling. Random splitting leaks past, present, and future observations across sets, creating artificially inflated, invalid performance scores.

## Validation
- Assert `df['timestamp'].is_unique` and `df['timestamp'].is_monotonic_increasing`.
- Verify `max(train_df['timestamp']) < min(test_df['timestamp'])`.
- Ensure lag features (`pm25_lag24`) strictly reference past time horizons ($t - 24$) with no future lookahead.

## Failure Modes
- Mixing UTC timestamps with unlocalized strings, leading to artificial 7-hour phase shifts in diurnal traffic peaks.
- Calculating rolling statistics with centered windows (`center=True`), which peeks into future observations ($t + k$) and causes data leakage.
- Filling missing periods by simply forward-filling across multi-day station outages.

## Expected Output
1. Continuous, fully reindexed hourly dataframe with zero hidden temporal gaps.
2. Verified lag and rolling features computed strictly on past observations.
3. Clean, leak-free chronological Train and Test datasets ready for modeling.
