# Data Rules & Time-Series Protocols

> **Scope:** Data ingestion, auditing, cleaning, transformation, and storage.  
> **Source Document:** [`docs/roadmap.md`](../../docs/roadmap.md) (Chapters 1 & 2, Weeks 1–5).

---

## 1. Raw Data Governance (`data/raw/`)

1. **Three-Tier Raw Data Policy (Roadmap §3.2):**
   - **Tier A (Runtime Ingestion Storage):** Raw API payloads and downloaded archives are stored intact in `data/raw/` (JSON/Parquet).
   - **Tier B (Integrity Preservation & Hash Verification):** Raw payload files are never manually edited; cryptographic SHA-256 hashes are recorded in `data/raw/metadata.json` for independent integrity verification. All cleaning and transformations are executed deterministically in-memory by code and saved to `data/processed/` (or `data/interim/`).
   - **Tier C (Version Control Hygiene):** Large raw payloads in `data/raw/` are excluded from Git via `.gitignore` (`data/raw/*.json`, `data/raw/*.parquet`) and can be reproduced independently via the data collection pipeline without repository bloat.
2. **No Manual Tools:** Never open, edit, or re-save raw CSV/JSON files in spreadsheet applications (e.g. Microsoft Excel). Doing so corrupts Vietnamese UTF-8 encoding and alters datetime formatting silently.
3. **Provenance & Metadata:** Every batch of raw ingested files must be accompanied by `data/raw/metadata.json` logging:
   - Source endpoint URL and query parameters.
   - Retrieval timestamp (ISO 8601).
   - API version / payload schema snapshot.
   - License and attribution (OpenAQ ODC-BY, Open-Meteo CC BY 4.0).
4. **Resilient Download Strategy:** API calls must fetch monthly segments with `time.sleep(1.0)` between requests, saving interim chunk files to disk to prevent loss during rate limits or disconnects.

---

## 2. Processed Data Standards (`data/processed/`)

1. **100% Code-Generated:** Processed files must be generated strictly through executable scripts (e.g., `src/cleaning_pipeline.py`) or tracked notebooks.
2. **Target Format:** Store final clean datasets in **Apache Parquet** (`.parquet`) format using Snappy compression.
   - *Why:* Drastically reduces disk footprint, preserves native column dtypes (`datetime64[ns, Asia/Ho_Chi_Minh]`, `float64`), and provides orders-of-magnitude faster I/O than CSV.
3. **Cleaning Documentation:** Every data transformation, filtering step, or value replacement must be logged in [`docs/cleaning_log.md`](../../docs/cleaning_log.md) stating:
   - Target column(s).
   - Operation performed.
   - Exact count of affected rows.
   - Domain/scientific rationale.

---

## 3. Time-Series Safety & Integrity

1. **Timezone Normalization:**
   - Immediately localize all timestamps to Hanoi local time: `Asia/Ho_Chi_Minh` (UTC+7).
   - Ensure timestamps are aware and consistent before any cross-source merging.
2. **Chronological Sorting & Indexing:**
   - Datasets must be sorted chronologically and indexed cleanly:
     ```python
     df = df.sort_values('timestamp').reset_index(drop=True)
     ```
3. **Primary Key & Timestamp Uniqueness:**
   - Every station record must have a unique timestamp. Check:
     ```python
     assert df['timestamp'].is_unique, "Duplicate timestamps detected!"
     ```
4. **Time Grid Reindexing & Gap Identification:**
   - Station downtime causes temporal gaps. Reindex against a full hourly grid to expose missing intervals rather than leaving hidden gaps:
     ```python
     full_idx = pd.date_range(start=df['timestamp'].min(), end=df['timestamp'].max(), freq='h')
     df = df.set_index('timestamp').reindex(full_idx).rename_axis('timestamp').reset_index()
     ```
5. **Missing Value Policy — RETAIN, do not impute (binding invariant):**
   - **Mọi khuyết đều được giữ nguyên là `NaN`.** Dự án này cấm tạo ra giá trị quan
     sát bằng bất kỳ phép nội suy hay thay thế nào. Lý do không phải thẩm mỹ:
     `src/cleaning.py` chốt bằng `assert_no_imputation()`, hàm so **từng ô** trên
     khoá `(station_id, timestamp)` và chấp nhận đúng hai kết quả — ô `NaN` trước
     phải còn `NaN`, ô có giá trị phải giữ nguyên giá trị đó hoặc trở thành `NaN`.
     Bất kỳ phép điền nào cũng làm assert đỏ.
   - **Cờ chẩn đoán thay cho việc điền:**
     ```python
     df['pm25_was_missing'] = df['pm25'].isna().astype(int)   # khối khuyết > 6 giờ
     df['is_high_humidity_fog'] = ...                        # giờ RH > 90% (cờ độ ẩm)
     ```
   - **Cờ chẩn đoán là dữ liệu quan sát, KHÔNG phải giá trị đã được thay thế.**
     Chúng đi cùng dataset để giải thích *tại sao* ô đó trống.
   - **Không được đưa cờ phái sinh từ target vào feature.** `pm25_was_missing` bằng
     `pm25.isna()`, mà `SimpleImputer(strategy="median")` ở #7 lại điền median cho
     đúng những hàng đó — nên mọi hàng `flag == 1` có target bằng đúng median
     (đo trên dữ liệu thật: 100% ở cả Train và Test). Đó là rò rỉ target theo cấu
     trúc, và `validate_no_leakage()` **không** bắt được vì imputer vẫn học đúng trên
     Train. Xem `TARGET_DERIVED_FLAGS` trong `src/cleaning_pipeline.py`.
    - **Cờ không có giá trị dự báo *marginal* cũng không được đưa vào feature — nhưng lý do khác hẳn.** `is_high_humidity_fog` bị loại khỏi feature mặc định và nằm trong nhóm `NON_PREDICTIVE_FLAGS`, tách riêng `TARGET_DERIVED_FLAGS` để không nhầm lẫn hai lý do:
      - `TARGET_DERIVED_FLAGS` = **rò rỉ target chắc chắn**.
      - `NON_PREDICTIVE_FLAGS` = **chưa có bằng chứng** về giá trị dự báo marginal trên bộ
        dữ liệu hiện tại (`corr(pm25, RH) = -0,037`; mutual information 0,0024).
      Lưu ý: cờ **có** tương tác theo mùa (Đông +2,79; Xuân −8,91 µg/m³; F-test đồng thời
      `p = 7,4·10⁻¹¹`), nên `corr ≈ 0` là hệ quả của việc trung bình qua các mùa chứ **không**
      phải bằng chứng không có quan hệ. Vì vậy **không** được viết "không dự báo được" — đó là
      phủ định tuyệt đối mà tương quan gần 0 không chứng minh được. Cờ vẫn **được giữ trong
      dataset** như tài liệu chẩn đoán; chỉ không làm feature.
   - *Lịch sử:* bản sửa đổi trước đây của mục này cho phép
     `interpolate(method='time', limit=2)` cho khuyết ≤ 2 giờ. Quy tắc đó **đã bị
     thay thế** và không còn hiệu lực — nó mâu thuẫn trực tiếp với
     `assert_no_imputation()`. Không viết mã theo quy tắc cũ.
6. **Row Explosion Prevention (Critical Join Rule):**
   - **Never assume a merge is correct merely because the code executes.** Always inspect granularity, matching timezones, and key intersection.
   - When merging air quality data (`df_air`) with meteorological data (`df_weather`), ensure both datasets share unique `timestamp` keys.
   - Reject column-name collisions outside the join key **before** merging — pandas
     silently renames them to `_x`/`_y`, destroying the original name.
   - Always verify row counts before and after joining:
     ```python
     n_air = len(df_air)
     df_merged = pd.merge(df_air, df_weather, on='timestamp', how='left')
     assert len(df_merged) == n_air, f"Row Explosion detected! Before: {n_air}, After: {len(df_merged)}"
     assert not df_merged['temperature'].isna().all(), "Joined weather columns are entirely NaN! Check timezone or timestamp format mismatch."
     ```
   - Use `==`, not `<=`. With `how="left"` + unique keys + `validate="1:1"`,
     `len(merged) <= len(air)` is a tautology that can never fire. The all-NaN
     assertion is the check that actually catches a timezone/window mismatch.
   - `src/cleaning_pipeline.py::merge_air_weather()` enforces all three; use it
     rather than re-deriving the merge by hand.

---

## 4. Domain Validation & Physical Bounds

Validate measurements against environmental physics before downstream modeling:

| Metric | Physical Rule / Valid Range | Failure Action | Scientific Rationale |
|---|---|---|---|
| `pm25` vs `pm10` | $\text{PM}_{2.5} \le \text{PM}_{10}$ (**strict**, no tolerance) | Set both to `NaN` | $\text{PM}_{2.5}$ is aerodynamically a subset of $\text{PM}_{10}$. Any inversion indicates severe optical/inlet malfunction. |
| `pm25` vs `pm10` (classification only) | $\epsilon = 2.0\,\mu\text{g/m}^3$ measurement-uncertainty tier | **No action — reporting tier only** | Splits inversions into "beyond instrument uncertainty" vs "within tolerance" for the audit report. $\epsilon$ is **not** an action threshold. See `docs/cleaning_log.md` §3.4. |
| Negative values | $\text{PM}_{2.5} \ge 0$ and $\text{PM}_{10} \ge 0$ | Convert $< 0$ to `NaN`; retain valid observed $0.0$ unless flagged by QC | Negative concentrations are physically impossible. Valid $0.0$ readings without sensor QC fault flags are retained as real observations. |
| Stuck sensor | Identical float for $> 6$ consecutive hours | Convert series to `NaN` | Hardware frozen or sensor locked at baseline. |
| Optical fog noise | If $\text{RH} > 90\%$ and $\text{PM}_{2.5}$ spikes | Add boolean flag `is_high_humidity_fog = 1` | Optical sensors misclassify microscopic water droplets as particulate matter in high fog. Do not delete, but flag. |
| Relative humidity | $0\% \le \text{RH} \le 100\%$ | Drop or nullify invalid points | Physical atmospheric limit. |
| Wind speed | $\text{wind\_speed} \ge 0\,\text{m/s}$ | Assert non-negative | Negative speed is non-physical. |
| Wind direction | $0^\circ \le \text{wind\_dir} \le 360^\circ$ | Modulo 360 or nullify | Geometric circular degree bounds. |
| Disguised missing | String markers `"-999"`, `"N/A"`, `"None"`, `"null"` | Parse as `NaN` at load | Ingestion traps where APIs encode missing values as numeric outliers. |

---

## 5. Missingness Mechanisms (Rubin's Taxonomy)

Every missing observation must be **described** under the 3 mechanisms. Rubin's
taxonomy is a *descriptive* framework here, **not** a licence to fill gaps.

- **MCAR (Missing Completely at Random):** Periodic 1-hour packet loss due to cell
  transmission glitches. Described as a diagnostic hypothesis; observable patterns
  (e.g. a diurnal gradient) already contradict *pure* MCAR.
- **MAR (Missing at Random):** Station power cut during torrential rains. Dependent
  on observable variables (`precipitation > 50 mm`).
- **MNAR (Missing Not at Random):** Sensor saturation cutoff during an extreme
  hazardous pollution episode ($\text{PM}_{2.5} > 500\,\mu\text{g/m}^3$). **Never
  drop these rows without explicit bias analysis**, as doing so creates survivorship bias.

> 🚫 **No imputation under this section — for any mechanism.** A previous revision of
> this file said MCAR gaps were *"safe for local interpolation ($\le 2$h)"* and MAR
> gaps should be *"imputed with weather-stratified medians"*. **Both statements are
> withdrawn and must not be implemented.** They directly contradict §3.5, which is a
> binding invariant enforced cell-by-cell by
> `src/cleaning.py::assert_no_imputation()`: a cell that was `NaN` before cleaning
> must still be `NaN` after, and an observed cell may only keep its exact value or
> become `NaN`. Observed measurements may disappear; they may never appear, change,
> or be replaced by a statistical estimate. Any code written from the withdrawn rule
> is rejected by that assert.
>
> Statistical imputation, if ever authorised for a future milestone, is
> **data-dependent preprocessing** and therefore belongs to Issue #7 *after* the
> chronological split, fitted strictly on the Train partition — see §2 and Issue #6
> scope. It is out of scope for the audit (#5) and deterministic cleaning (#6).
>
> *History:* §3.5 was tightened to RETAIN-don't-impute; this section (§5) was
> originally written against the earlier, looser rule and had not been reconciled.
> Corrected 2026-09-30 during the Milestone 2 audit.
