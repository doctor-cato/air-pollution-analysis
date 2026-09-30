# Nhật Ký Làm Sạch Dữ Liệu (Cleaning Log)

> **Nguồn sinh:** `src/cleaning.py` · `run_deterministic_cleaning()` · `render_cleaning_log()`  
> **Notebook:** [`notebooks/03_data_cleaning.ipynb`](../notebooks/03_data_cleaning.ipynb)  
> **Issue:** #6 – Làm sạch tất định, lỗi cảm biến và reindex chuỗi thời gian  
> **Milestone:** Milestone 2 – Kiểm toán & Làm sạch Dữ liệu (Tuần 03–05)  
> **Tính tất định:** tài liệu này được sinh tự động từ mã nguồn và **không** chứa dấu
> thời gian chạy (wall-clock), nên chạy lại trên cùng dữ liệu cho ra kết quả giống hệt.

---

## 1. Ranh Giới Phân Định: Làm Sạch Tất Định vs. Tiền Xử Lý Phụ Thuộc Dữ Liệu

**Phạm vi thực hiện tại đây — Chỉ phép biến đổi tất định, thực hiện TRƯỚC khi đóng băng và chia tập.**

| Được thực hiện (Issue #6) | Bị hạn chế (chuyển sang Issue #7) |
|---|---|
| Chuẩn hóa schema và múi giờ `Asia/Ho_Chi_Minh` (UTC+7) | Điền khuyết trung vị / trung bình / nội suy |
| Sắp xếp tăng dần theo thời gian | Điền bằng giá trị trượt học từ dữ liệu |
| Khử trùng lặp tại khóa quan sát | Chuẩn hóa tỷ lệ (RobustScaler, StandardScaler) |
| Chuyển missing ngụy trang thành `NaN` | Lựa chọn đặc trưng phụ thuộc phân phối / nhãn |
| Lọc giá trị âm và giá trị vi phạm giới hạn vật lý | Phép biến đổi mục tiêu ứng viên `np.log1p` |
| Ràng buộc khí động học PM2.5 ≤ PM10 | Đóng băng tập dữ liệu và phân chia Train/Test |
| Nhận diện kẹt cảm biến, gắn cờ sương mù độ ẩm cao | Fit tiền xử lý **chỉ trên Train** |
| Reindex lưới 1 giờ liên tục theo từng trạm | Đóng gói Scikit-Learn `Pipeline` / `ColumnTransformer` |
| Gắn cờ chẩn đoán `pm25_was_missing`, `is_high_humidity_fog` | Xuất `data/processed/air_pollution_final.parquet` |

**Nguyên tắc chống rò rỉ được bảo vệ tại đây:** không một đại lượng thống kê toàn cục nào
được tính toán trước khi chia tập. Cột `relative_humidity` chỉ được dùng để **tra cứu
mốc thời gian** nhằm sinh cờ chẩn đoán và không được giữ lại trong artifact ô nhiễm.

**Bàn giao cho Issue #7:** Đóng băng tập dữ liệu, phân chia Train/Test theo chuỗi thời gian, fit tiền xử lý chỉ trên Train.

---

## 2. Ngưỡng & Hằng Số Quy ước Sử Dụng

| Hằng số | Giá trị | Nguồn quy định |
|---|---|---|
| Múi giờ canonical | `Asia/Ho_Chi_Minh` | `docs/data_dictionary.md` §3.1 |
| Tần suất lưới thời gian | `freq='h'` | Issue #6, `.agents/rules/data.md` §3.4 |
| Dung sai khí động học ε | `2.0 µg/m³` | `.agents/rules/data.md` §4, Handoff 1 của Issue #5 |
| Ngưỡng kẹt cảm biến | `> 6 giờ` không đổi | Issue #6, `docs/roadmap.md` §4.3 |
| Ngưỡng khối khuyết lớn | `> 6 giờ` liên tiếp | Issue #6, `.agents/rules/data.md` §3.5 |
| Ngưỡng sương mù độ ẩm cao | `RH > 90.0%` | Issue #6, `.agents/rules/data.md` §4 |

**Quy ước đếm của chuỗi liên tục:** ngưỡng được đếm bằng **số quan sát liên tiếp** trên lưới 1 giờ,
đúng theo `.agents/rules/data.md` §3.5 / §4 (kẹt cảm biến và khối khuyết lớn là chuỗi **dài hơn 6 giờ**). Vì vậy
“kẹt cảm biến > 6 giờ” và “khối khuyết lớn > 6 giờ” đều được hiện thực hoá bằng điều kiện **chuỗi có ít nhất 7 quan sát liên tiếp**.

> **Lưu ý về khác biệt 1 quan sát so với Issue #5:** `audit_prolonged_zeros()` của Issue #5
> dùng điều kiện `>= 6` nên một chuỗi 6 quan sát đã bị nó gọi là “kéo dài”, còn Issue #6 dùng
> `> 6` (tức ≥ 7) theo đúng câu chữ của `data.md`. Hai con số này **không so sánh trực tiếp
> được**; khi đối chiếu với số liệu Issue #5 phải tính lại theo cùng quy ước.

---

## 3. Tập Dữ Liệu Ô Nhiễm Không Khí (Air Quality)

**Tệp canonical:** `data/interim/air_quality_canonical.parquet` — sau làm sạch được ghi đè tại `data/interim/air_quality_canonical.parquet`

### 3.1. Trạng Thái Trước và Sau Làm Sạch

| Chỉ số | Trước làm sạch | Sau làm sạch |
|---|---|---|
| Số dòng | 8.022 | 9.044 |
| Số cột | 5 | 8 |
| Mốc thời gian nhỏ nhất | `2025-07-03 22:00:00+07:00` | `2025-07-03 22:00:00+07:00` |
| Mốc thời gian lớn nhất | `2026-07-15 17:00:00+07:00` | `2026-07-15 17:00:00+07:00` |
| Múi giờ | `Asia/Ho_Chi_Minh` | `Asia/Ho_Chi_Minh` |
| Bản ghi trùng khóa quan sát | 0 | 0 |
| Số ô `pm25` khuyết thiếu | 203 | 1.549 |
| Số ô `pm10` khuyết thiếu | 123 | 1.469 |
| Đỉnh PM2.5 (µg/m³) | 252.6436 | 198.9467 |

### 3.2. Khoảng Trống Thời Gian Được Bộc Lộ Sau Reindex

- Cửa sổ lưới thời gian thực hiện: `2025-07-03 22:00:00+07:00` → `2026-07-15 17:00:00+07:00`.
- Số dòng trước reindex: **8.022**; sau reindex: **9.044**.
- Số giờ trống được chèn ra dưới dạng `NaN`: **1.022**.
- Các trạm quan trắc được reindex độc lập: `VN001_HANOI_556_NGUYEN_VAN_CU`.

| Trạm | Số dòng quan sát | Số dòng lưới | Giờ trống chèn thêm | Mốc quan sát đầu | Mốc quan sát cuối |
|---|---|---|---|---|---|
| `VN001_HANOI_556_NGUYEN_VAN_CU` | 8.022 | 9.044 | 1.022 | `2025-07-03 22:00:00+07:00` | `2026-07-15 17:00:00+07:00` |

> Khoảng trống sau reindex được **giữ nguyên dạng `NaN`** — không nội suy và không xóa dòng —
> để phản ánh trung thực toàn bộ khoảng mất tín hiệu của trạm quan trắc.

### 3.3. Chi Tiết Từng Phép Biến Đổi

#### Bước 1 — Chuẩn hóa mốc thời gian về Asia/Ho_Chi_Minh (UTC+7)

**Căn cứ logic:** Mọi phép ghép và phân chia chuỗi thời gian phía sau yêu cầu một múi giờ duy nhất.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `normalize_timestamps()` |
| `timezone_before` | `Asia/Ho_Chi_Minh` |
| `timezone_after` | `Asia/Ho_Chi_Minh` |
| `rows_localized` | `0` |
| `rows_converted_from_other_timezone` | `0` |
| `rows_mixed_offsets_utc_first` | `0` |
| `rows_unparseable` | `0` |
| `canonical_timezone` | `Asia/Ho_Chi_Minh` |

#### Bước 2 — Sắp xếp tăng dần theo thời gian (và theo trạm)

**Căn cứ logic:** Đảm bảo chuỗi thời gian đơn điệu trước khi kiểm tra chuỗi liên tục.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `sort_chronologically()` |
| `sort_keys` | `["station_id", "timestamp"]` |
| `sort_algorithm` | `mergesort (ổn định, tất định)` |
| `was_monotonic_increasing` | `Có` |
| `rows_reordered` | `0` |

#### Bước 3 — Khử trùng lặp tại khóa quan sát

**Căn cứ logic:** Một mốc thời gian chỉ được mang một quan sát cho mỗi trạm.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `drop_duplicate_observations()` |
| `observation_key` | `["station_id", "timestamp"]` |
| `rows_before` | `8.022` |
| `duplicate_rows_removed` | `0` |
| `rows_after` | `8.022` |
| `rows_affected_pct` | `0` |
| `resolution_rule` | `giữ bản ghi đầu tiên theo thứ tự sắp xếp tất định` |

#### Bước 4 — Chuyển missing ngụy trang (-999/-9999, chuỗi lỗi) thành NaN

**Căn cứ logic:** Mã lỗi nhà cung cấp nếu không bóc trần sẽ thành giá trị đo giả âm thầm đi vào phân tích.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `normalize_disguised_missing()` |
| `columns_checked` | `["pm25", "pm10"]` |
| `by_column.pm25.rows_converted_to_nan` | `0` |
| `by_column.pm25.unparseable_values_to_nan` | `0` |
| `by_column.pm25.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.pm25.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `by_column.pm10.rows_converted_to_nan` | `0` |
| `by_column.pm10.unparseable_values_to_nan` | `0` |
| `by_column.pm10.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.pm10.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `total_cells_converted` | `0` |
| `note` | `Giá trị đo hợp lệ 0.0 được giữ nguyên, không bị quy nhầm là missing.` |

#### Bước 5 — Lọc giá trị âm phi lý của nồng độ hạt bụi

**Căn cứ logic:** Nồng độ âm là bất khả thi về mặt vật lý; 0.0 hợp lệ được giữ nguyên.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `enforce_air_quality_physical_rules()` |
| `by_column.pm25.negative_values_nullified` | `0` |
| `by_column.pm25.total_rows_nullified` | `0` |
| `by_column.pm25.valid_zero_preserved` | `0` |
| `by_column.pm10.negative_values_nullified` | `0` |
| `by_column.pm10.total_rows_nullified` | `0` |
| `by_column.pm10.valid_zero_preserved` | `0` |
| `total_rows_nullified` | `0` |
| `rule` | `NaN và mã lỗi -999/-9999 → NaN; giá trị < 0 → NaN; 0.0 hợp lệ được giữ nguyên.` |
| `upper_bound_policy` | `Không đặt trần nồng độ để bảo toàn đợt ô nhiễm cực đoan thực tế.` |

#### Bước 6 — Thực thi ràng buộc khí động học PM2.5 ≤ PM10

**Căn cứ logic:** PM2.5 là tập con khí động học của PM10; nghịch đảo cho thấy lỗi quang học hoặc nhập nội.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `enforce_pm_subset_constraint()` |
| `rule` | `pm25 <= pm10 (nghiêm ngặt, mọi nghịch đảo)` |
| `reporting_epsilon_ug_m3` | `2` |
| `action_on_violation` | `chuyển CẢ pm25 và pm10 thành NaN` |
| `skipped` | `Không` |
| `pairs_evaluated` | `7.696` |
| `pairs_single_channel` | `326` |
| `strict_inversions` | `324` |
| `inversions_beyond_epsilon` | `282` |
| `inversions_within_measurement_tolerance` | `42` |
| `rows_nullified` | `324` |
| `rows_nullified_pct_of_pairs` | `4.21` |

- `epsilon_rationale`: Mốc phân loại bằng chứng, KHÔNG phải ngưỡng hành động: dùng để tách nghịch đảo vượt sai số đo (BAM-1020 / cảm biến quang học, chuẩn US EPA & QCVN, theo .agents/rules/data.md §4 và bàn giao Handoff 1 của Issue #5) khỏi nghịch đảo nhẹ. Xem docs/cleaning_log.md §3.4.

#### Bước 7 — Reindex lưới thời gian liên tục 1 giờ theo từng trạm

**Căn cứ logic:** Bộc lộ trung thực mọi khoảng trống do trạm ngừng phát; khoảng trống giữ nguyên dạng NaN.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `reindex_hourly_grid()` |
| `stations` | `["VN001_HANOI_556_NGUYEN_VAN_CU"]` |
| `freq` | `h` |
| `grid_frequency_label` | `1 giờ ('h')` |
| `window_start` | `2025-07-03 22:00:00+07:00` |
| `window_end` | `2026-07-15 17:00:00+07:00` |
| `rows_before` | `8.022` |
| `rows_after` | `9.044` |
| `rows_inserted` | `1.022` |
| `gap_policy` | `Khoảng trống sau reindex được giữ nguyên dạng NaN (không nội suy, không xóa dòng).` |
| `per_station.VN001_HANOI_556_NGUYEN_VAN_CU.observed_rows_before` | `8.022` |
| `per_station.VN001_HANOI_556_NGUYEN_VAN_CU.grid_rows_after` | `9.044` |
| `per_station.VN001_HANOI_556_NGUYEN_VAN_CU.rows_inserted_as_nan` | `1.022` |
| `per_station.VN001_HANOI_556_NGUYEN_VAN_CU.observed_first` | `2025-07-03 22:00:00+07:00` |
| `per_station.VN001_HANOI_556_NGUYEN_VAN_CU.observed_last` | `2026-07-15 17:00:00+07:00` |

- `window_policy`: Dải quan sát thực tế chung của toàn tập (mặc định) để mọi trạm nằm trên cùng một lưới giờ; reindex vẫn thực hiện độc lập và riêng biệt cho từng trạm.

#### Bước 8 — Nhận diện lỗi kẹt cảm biến (> 6 giờ không đổi)

**Căn cứ logic:** Phần cứng đóng băng hoặc kẹt ở đường nền tạo ra chuỗi số đo hoàn toàn bất biến.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `flag_stuck_values()` |
| `threshold_hours` | `6` |
| `flag_name` | `pm25_was_stuck` |
| `by_column.pm25.rows_nullified` | `0` |
| `by_column.pm25.longest_observed_constant_run_hours` | `1` |
| `by_column.pm25.longest_nullified_run_hours` | `0` |
| `by_column.pm25.nullified_runs` | `0` |
| `by_column.pm25.missing_runs_excluded` | `189` |
| `by_column.pm25.nullified_pct` | `0` |
| `by_column.pm10.rows_nullified` | `0` |
| `by_column.pm10.longest_observed_constant_run_hours` | `1` |
| `by_column.pm10.longest_nullified_run_hours` | `0` |
| `by_column.pm10.nullified_runs` | `0` |
| `by_column.pm10.missing_runs_excluded` | `177` |
| `by_column.pm10.nullified_pct` | `0` |
| `total_rows_nullified` | `0` |
| `rows_flagged` | `0` |

- `rule`: Chuỗi quan sát không đổi giá trị trên dài hơn 6 giờ liên tiếp (tức ≥ 7 quan sát giống hệt) → gắn cờ `pm25_was_stuck` và chuyển thành NaN.
- `excluded_columns_rationale`: Không áp dụng cho precipitation/wind_speed: chuỗi 0.0 dài của chúng là hiện tượng khí tượng tự nhiên, đã được Issue #5 đo và kết luận rõ ràng.

#### Bước 9 — Gắn cờ pm25_was_missing cho khối khuyết > 6 giờ

**Căn cứ logic:** Chỉ báo chẩn đoán để Issue #7 không nội suy mù và không xóa dòng. Dùng cùng cờ `pm25_was_stuck` để phân biệt khối khuyết do trạm ngừng phát với giờ bị cảm biến kẹt.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `flag_prolonged_missing()` |
| `source_column` | `pm25` |
| `flag_name` | `pm25_was_missing` |
| `threshold_hours` | `6` |
| `missing_rows_total` | `1.549` |
| `skipped` | `Không` |
| `missing_blocks` | `189` |
| `prolonged_blocks` | `48` |
| `rows_flagged` | `1.289` |
| `flagged_pct` | `14.2525` |
| `longest_missing_block_hours` | `630` |
| `longest_flagged_block_hours` | `630` |
| `rows_also_flagged_as_stuck` | `0` |

- `flag_definition`: 1 = giờ này không có quan sát hợp lệ và nằm trong một khối khuyết liên tục dài hơn 6 giờ; 0 = ngược lại.

#### Bước 10 — Gắn cờ cảnh báo sương mù độ ẩm cao (RH > 90%)

**Căn cứ logic:** Cảm biến quang học nhầm giọt nước thành bụi khi RH cao — gắn cờ để chẩn đoán, không xóa dòng.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `attach_high_humidity_flag()` |
| `source` | `data/interim/weather_canonical.parquet (relative_humidity)` |
| `threshold_pct` | `90` |
| `flag_name` | `is_high_humidity_fog` |
| `flag_definition` | `1 = RH > 90.0% (sương mù quang học); 0 = ngược lại.` |
| `rows_before_join` | `9.044` |
| `rows_after_join` | `9.044` |
| `row_explosion_detected` | `Không` |
| `humidity_matched_rows` | `9.044` |
| `humidity_unavailable_rows` | `0` |
| `rows_flagged` | `2.834` |
| `flagged_pct` | `31.3357` |
| `row_deletion_policy` | `Không xóa bản ghi nào ở giờ RH cao.` |

### 3.4. Quyết Định Thiết Kế: Vì Sao Xử Lý Toàn Bộ Nghịch Đảo Nghiêm Ngặt

| Chỉ số | Số lượng | Ý nghĩa |
|---|---|---|
| Cặp quan sát đồng thời PM2.5 & PM10 | 7.696 | Cơ sở đánh giá |
| Nghịch đảo **vượt** sai số đo (PM2.5 > PM10 + 2) | 282 | Nghịch đảo không thể giải thích bằng sai số thiết bị |
| Nghịch đảo **trong** sai số đo | 42 | Chênh lệch nhỏ, có thể do ảnh hưởng độ ẩm giữa hai kênh quang học |
| Tổng nghịch đảo nghiêm ngặt được xử lý | 324 | Chuyển **cả hai** cột thành `NaN` |

**Vì sao xử lý 324 bản ghi thay vì 282 như Handoff 1 của Issue #5?**

Tiêu chí nghiệm thu và mục Kiểm chứng của Issue #6 yêu cầu rõ ràng:

```python
(df['pm25'] > df['pm10'] + 1e-3).sum() == 0
```

Nếu chỉ xử lý các bản ghi vượt sai số đo ε = 2,0 µg/m³ thì 42 bản ghi nghịch đảo nhẹ vẫn còn lại và
điều kiện kiểm chứng trên **không đạt**. Vì vậy Issue #6 áp dụng ràng buộc nghiêm ngặt
`PM2.5 <= PM10` cho mọi cặp quan sát đồng thời, đồng thời **vẫn báo cáo riêng** số bản ghi vượt
sai số để đối chiếu với con số 282 của Issue #5. ε = 2,0 µg/m³ do đó đóng vai trò **mốc phân loại
bằng chứng**, không phải ngưỡng hành động.

**Hành động khi vi phạm: chuyển CẢ `pm25` và `pm10` thành `NaN`.** Đây chính là hành động được
quy định tại `.agents/rules/data.md` §4 — khi hai kênh quang học của cùng một thiết bị mâu thuẫn
thì không kênh nào còn đáng tin; giữ lại một kênh trong khi xóa kênh kia sẽ tạo ra dữ liệu “nửa vời”
khó giải thích về mặt khoa học. Bản ghi chỉ có một kênh duy nhất được giữ nguyên và tuyệt đối không
được suy diễn giá trị cho kênh còn lại.

---

## 4. Tập Dữ Liệu Khí Tượng Bề Mặt (Weather ERA5)

**Tệp canonical:** `data/interim/weather_canonical.parquet` — sau làm sạch được ghi đè tại `data/interim/weather_canonical.parquet`

### 4.1. Trạng Thái Trước và Sau Làm Sạch

| Chỉ số | Trước làm sạch | Sau làm sạch |
|---|---|---|
| Số dòng | 9.072 | 9.072 |
| Mốc thời gian nhỏ nhất | `2025-07-03 00:00:00+07:00` | `2025-07-03 00:00:00+07:00` |
| Mốc thời gian lớn nhất | `2026-07-15 23:00:00+07:00` | `2026-07-15 23:00:00+07:00` |
| Múi giờ | `Asia/Ho_Chi_Minh` | `Asia/Ho_Chi_Minh` |
| Số ô khuyết thiếu (toàn bộ biến) | 0 | 0 |

### 4.2. Chi Tiết Từng Phép Biến Đổi

#### Bước 1 — Chuẩn hóa mốc thời gian về Asia/Ho_Chi_Minh (UTC+7)

**Căn cứ logic:** Đồng bộ múi giờ với chuỗi ô nhiễm không khí trước mọi phép ghép tương lai.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `normalize_timestamps()` |
| `timezone_before` | `Asia/Ho_Chi_Minh` |
| `timezone_after` | `Asia/Ho_Chi_Minh` |
| `rows_localized` | `0` |
| `rows_converted_from_other_timezone` | `0` |
| `rows_mixed_offsets_utc_first` | `0` |
| `rows_unparseable` | `0` |
| `canonical_timezone` | `Asia/Ho_Chi_Minh` |

#### Bước 2 — Sắp xếp tăng dần theo thời gian

**Căn cứ logic:** Đảm bảo chuỗi thời gian đơn điệu trước khi kiểm tra chuỗi liên tục.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `sort_chronologically()` |
| `sort_keys` | `["timestamp"]` |
| `sort_algorithm` | `mergesort (ổn định, tất định)` |
| `was_monotonic_increasing` | `Có` |
| `rows_reordered` | `0` |

#### Bước 3 — Khử trùng lặp tại khóa quan sát timestamp

**Căn cứ logic:** Điểm lưới ERA5 chỉ được mang một quan sát cho mỗi giờ.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `drop_duplicate_observations()` |
| `observation_key` | `["timestamp"]` |
| `rows_before` | `9.072` |
| `duplicate_rows_removed` | `0` |
| `rows_after` | `9.072` |
| `rows_affected_pct` | `0` |
| `resolution_rule` | `giữ bản ghi đầu tiên theo thứ tự sắp xếp tất định` |

#### Bước 4 — Chuyển missing ngụy trang thành NaN

**Căn cứ logic:** Bảo đảm mã lỗi nhà cung cấp không thành giá trị khí tượng giả.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `normalize_disguised_missing()` |
| `columns_checked` | `["temperature", "relative_humidity", "wind_speed", "wind_direction", "precipitation", "surface_pressure"]` |
| `by_column.temperature.rows_converted_to_nan` | `0` |
| `by_column.temperature.unparseable_values_to_nan` | `0` |
| `by_column.temperature.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.temperature.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `by_column.relative_humidity.rows_converted_to_nan` | `0` |
| `by_column.relative_humidity.unparseable_values_to_nan` | `0` |
| `by_column.relative_humidity.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.relative_humidity.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `by_column.wind_speed.rows_converted_to_nan` | `0` |
| `by_column.wind_speed.unparseable_values_to_nan` | `0` |
| `by_column.wind_speed.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.wind_speed.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `by_column.wind_direction.rows_converted_to_nan` | `0` |
| `by_column.wind_direction.unparseable_values_to_nan` | `0` |
| `by_column.wind_direction.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.wind_direction.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `by_column.precipitation.rows_converted_to_nan` | `0` |
| `by_column.precipitation.unparseable_values_to_nan` | `0` |
| `by_column.precipitation.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.precipitation.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `by_column.surface_pressure.rows_converted_to_nan` | `0` |
| `by_column.surface_pressure.unparseable_values_to_nan` | `0` |
| `by_column.surface_pressure.numeric_disguised_codes` | `[-999, -9999]` |
| `by_column.surface_pressure.string_disguised_markers` | `["N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "]` |
| `total_cells_converted` | `0` |
| `note` | `Giá trị đo hợp lệ 0.0 được giữ nguyên, không bị quy nhầm là missing.` |

#### Bước 5 — Kiểm tra dải hợp lệ khí tượng bề mặt

**Căn cứ logic:** 0% ≤ RH ≤ 100%, 0 ≤ hướng gió ≤ 360°, lượng mưa ≥ 0, nhiệt độ và áp suất trong dải vật lý.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `enforce_weather_physical_rules()` |
| `by_column.temperature.allowed_range` | `[0, 50]` |
| `by_column.temperature.unit` | `°C` |
| `by_column.temperature.values_out_of_range` | `0` |
| `by_column.temperature.total_rows_nullified` | `0` |
| `by_column.relative_humidity.allowed_range` | `[0, 100]` |
| `by_column.relative_humidity.unit` | `%` |
| `by_column.relative_humidity.values_out_of_range` | `0` |
| `by_column.relative_humidity.total_rows_nullified` | `0` |
| `by_column.wind_speed.allowed_range` | `[0, 60]` |
| `by_column.wind_speed.unit` | `m/s` |
| `by_column.wind_speed.values_out_of_range` | `0` |
| `by_column.wind_speed.total_rows_nullified` | `0` |
| `by_column.wind_direction.allowed_range` | `[0, 360]` |
| `by_column.wind_direction.unit` | `degrees` |
| `by_column.wind_direction.values_out_of_range` | `0` |
| `by_column.wind_direction.total_rows_nullified` | `0` |
| `by_column.precipitation.allowed_range` | `[0, 300]` |
| `by_column.precipitation.unit` | `mm` |
| `by_column.precipitation.values_out_of_range` | `0` |
| `by_column.precipitation.total_rows_nullified` | `0` |
| `by_column.surface_pressure.allowed_range` | `[950, 1050]` |
| `by_column.surface_pressure.unit` | `hPa` |
| `by_column.surface_pressure.values_out_of_range` | `0` |
| `by_column.surface_pressure.total_rows_nullified` | `0` |
| `total_rows_nullified` | `0` |
| `total_out_of_range` | `0` |
| `bounds_source` | `src.data_collection.WEATHER_PHYSICAL_BOUNDS (docs/data_dictionary.md)` |

#### Bước 6 — Reindex lưới thời gian liên tục 1 giờ

**Căn cứ logic:** Bộc lộ mọi khoảng trống của chuỗi ERA5 dưới dạng NaN thay vì ẩn giấu.

| Chỉ số | Giá trị |
|---|---|
| Hàm thực thi | `reindex_hourly_grid()` |
| `stations` | `["(single_series)"]` |
| `freq` | `h` |
| `grid_frequency_label` | `1 giờ ('h')` |
| `window_start` | `2025-07-03 00:00:00+07:00` |
| `window_end` | `2026-07-15 23:00:00+07:00` |
| `rows_before` | `9.072` |
| `rows_after` | `9.072` |
| `rows_inserted` | `0` |
| `gap_policy` | `Khoảng trống sau reindex được giữ nguyên dạng NaN (không nội suy, không xóa dòng).` |
| `per_station.(single_series).observed_rows_before` | `9.072` |
| `per_station.(single_series).grid_rows_after` | `9.072` |
| `per_station.(single_series).rows_inserted_as_nan` | `0` |
| `per_station.(single_series).observed_first` | `2025-07-03 00:00:00+07:00` |
| `per_station.(single_series).observed_last` | `2026-07-15 23:00:00+07:00` |

- `window_policy`: Dải quan sát thực tế chung của toàn tập (mặc định) để mọi trạm nằm trên cùng một lưới giờ; reindex vẫn thực hiện độc lập và riêng biệt cho từng trạm.


> **Vì sao không áp dụng quy tắc kẹt cảm biến cho khí tượng?** Issue #5 đã đo lịch sử và kết luận
> rõ ràng rằng chuỗi `precipitation = 0.0` kéo dài 275 giờ (74,15% số giờ) và các đợt gió lặng
> `wind_speed = 0.0` là **hiện tượng khí tượng tự nhiên** ở miền Bắc Việt Nam, không phải lỗi phần cứng.
> Áp dụng máy móc quy tắc kẹt cho các biến này sẽ xóa mất dữ liệu khí tượng hợp lệ, vi phạm nguyên tắc
> bảo toàn giá trị thực tế. Quy tắc kẹt vì thế chỉ áp dụng cho nồng độ hạt bụi `pm25` và `pm10`.

---

## 5. Kiểm Chứng Tiêu Chí Nghiệm Thu (Validation)

### 5.1. Tập Ô Nhiễm Không Khí

**Kiểm chứng tập ô nhiễm không khí:**

| Tiêu chí kiểm chứng | Kết quả | Trạng thái |
|---|---|---|
| `timezone_is_canonical` | observed=Asia/Ho_Chi_Minh; expected=Asia/Ho_Chi_Minh | **PASS** |
| `no_duplicate_observations` | duplicates=0 | **PASS** |
| `continuous_hourly_grid_per_station` | is_monotonic_increasing=Có; global_series_is_monotonic=Có; irregular_intervals_total=0; per_station.VN001_HANOI_556_NGUYEN_VAN_CU.rows=9.044; per_station.VN001_HANOI_556_NGUYEN_VAN_CU.irregular_intervals=0; per_station.VN001_HANOI_556_NGUYEN_VAN_CU.first=2025-07-03 22:00:00+07:00; per_station.VN001_HANOI_556_NGUYEN_VAN_CU.last=2026-07-15 17:00:00+07:00; per_station.VN001_HANOI_556_NGUYEN_VAN_CU.is_monotonic_increasing=Có | **PASS** |
| `no_negative_values` | negatives_by_column.pm25=0; negatives_by_column.pm10=0 | **PASS** |
| `pm_subset_constraint` | evaluated_pairs=7.372; violations_pm25_gt_pm10_plus_1e_3=0 | **PASS** |

Các phép kiểm chứng được thi hành trực tiếp trên DataFrame sau làm sạch:

```python
assert (df['pm25'] < 0).sum() == 0
pairs = df.dropna(subset=['pm25', 'pm10'])
assert (pairs['pm25'] > pairs['pm10'] + 1e-3).sum() == 0
assert df.groupby('station_id')['timestamp'].apply(lambda s: s.is_monotonic_increasing).all()
assert (df.groupby('station_id')['timestamp'].diff().dropna() == np.timedelta64(1, 'h')).all()
```

### 5.2. Tập Khí Tượng Bề Mặt

**Kiểm chứng tập khí tượng bề mặt:**

| Tiêu chí kiểm chứng | Kết quả | Trạng thái |
|---|---|---|
| `timezone_is_canonical` | observed=Asia/Ho_Chi_Minh; expected=Asia/Ho_Chi_Minh | **PASS** |
| `no_duplicate_observations` | duplicates=0 | **PASS** |
| `continuous_hourly_grid_per_station` | is_monotonic_increasing=Có; global_series_is_monotonic=Có; irregular_intervals_total=0 | **PASS** |
| `no_negative_values` | negatives_by_column.temperature=0; negatives_by_column.relative_humidity=0; negatives_by_column.wind_speed=0; negatives_by_column.wind_direction=0; negatives_by_column.precipitation=0; negatives_by_column.surface_pressure=0 | **PASS** |
| `pm_subset_constraint` | skipped=Có; reason=Không có đủ cột pm25/pm10 trong tập dữ liệu này. | **N/A** |

---

## 6. Cột Cờ Chẩn Đoán Được Sinh Ra

| Cột | Nguồn sinh | Ngữ nghĩa | Giá trị 1 |
|---|---|---|---|
| `pm25_was_missing` | `flag_prolonged_missing()` | Giờ không có quan sát hợp lệ nằm trong khối khuyết liên tục > 6 giờ | 1.289 hàng |
| `pm25_was_stuck` | `flag_stuck_values()` | Giá trị bị xoá vì cảm biến kẹt (chuỗi không đổi > 6 giờ) — KHÁC với trạm ngừng phát | 0 hàng |
| `is_high_humidity_fog` | `attach_high_humidity_flag()` | Giờ có độ ẩm tương đối > 90.0% (nghi vấn sương mù quang học) | 2.834 hàng |

> Cả ba cột cờ đều là **chỉ báo chẩn đoán**, tuyệt đối không phải phép điền khuyết và không làm thay
> đổi bất kỳ giá trị quan sát nào. Bản ghi ở giờ `is_high_humidity_fog = 1` **không** bị xóa.

> **Vì sao cần tách `pm25_was_stuck` khỏi `pm25_was_missing`:** cả hai đều khiến `pm25` bằng
> `NaN` nhưng nguyên nhân vật lý khác nhau. `pm25_was_missing` = trạm không phát tín hiệu;
> `pm25_was_stuck` = thiết bị có tín hiệu nhưng phần cứng đóng băng. Nếu gộp chung, Issue #7 sẽ
> không phân biệt được sự cố trạm với lỗi thiết bị khi quyết định có điền khuyết hay không.

---

## 7. Bảo Toàn Giá Trị Cực Trị Thực Tế

Làm sạch tất định ở Issue #6 **không** áp dụng bất kỳ quy tắc cắt bỏ giá trị cực trị nào:

1. **Không đặt trần nồng độ hạt bụi.** Các đợt bùng phát ô nhiễm, nghịch nhiệt mùa đông và
   sự kiện giao thừa pháo hoa đều được giữ nguyên.
2. **Chỉ chuyển `NaN` khi có căn cứ vật lý:** giá trị âm phi lý, mã lỗi ngụy trang, giá trị nằm ngoài
   dải khí quyển, chuỗi kẹt cảm biến chứng minh được, hoặc nghịch đảo khí động học.
3. **Không xóa dòng.** Reindex chỉ *chèn thêm* hàng `NaN` để bộc lộ khoảng trống; không bản ghi
   quan sát nào bị loại khỏi tập dữ liệu.

---

### 7.1. Bằng Chứng Định Lượng: Không Mất Giá Trị Vì Lý Do Không Được Chứng Minh

Nguyên tắc bảo toàn được kiểm chứng bằng cách **đối chiếu số ô khuyết trước và sau**
cùng với danh mục đầy đủ các nguyên nhân đã dùng để chuyển giá trị thành `NaN`:

| Biến | Số ô `NaN` trước | Số ô `NaN` sau | Nguyên nhân tăng thêm |
|---|---|---|---|
| `pm25` | 203 | 1.549 | Khoảng trống thời gian từ reindex + ràng buộc khí động học |
| `pm10` | 123 | 1.469 | Khoảng trống thời gian từ reindex + ràng buộc khí động học |

Như vậy **không có ô `NaN` nào được tạo ra bởi nguyên nhân nằm ngoài danh mục đã công bố**
(mã lỗi ngụy trang, giá trị âm phi lý, giá trị ngoài dải khí quyển, chuỗi kẹt cảm biến,
nghịch đảo khí động học, hoặc khoảng trống thời gian thật). Cụ thể trên dữ liệu thực tế:

| Phép biến đổi | Chỉ số | Số lượng |
|---|---|---|
| Thực thi ràng buộc khí động học PM2.5 ≤ PM10 | `rows_nullified` | 324 |
| Khoảng trống thời gian từ reindex (NaN cố ý) | `rows_inserted` | 1.022 |
| Cờ chẩn đoán pm25_was_missing (không xóa giá trị) | `rows_flagged` | 1.289 |

> **Kiểm chứng đỉnh nồng độ:** đỉnh PM2.5 lớn nhất trước làm sạch là 252.6436 µg/m³ (tại `2026-06-05 16:00:00+07:00`, trạm `VN001_HANOI_556_NGUYEN_VAN_CU`), kèm PM10 đo được là 174.7982 µg/m³ — tức vượt PM10 77.8454 µg/m³. Bản ghi này **vi phạm ràng buộc khí động học PM2.5 ≤ PM10** nên đã chuyển `NaN`. Đỉnh biến mất là hệ quả của bằng chứng vật lý, **không phải** quy tắc cắt bỏ cực trị.

---

## 8. Bàn Giao Cho Issue #7

Artifact sau làm sạch tất định (đã ghi ra đĩa):

- `data/interim/air_quality_canonical.parquet` — dạng đầu vào, sau làm sạch: 9.044 dòng, 2025-07-03 22:00:00+07:00 → 2026-07-15 17:00:00+07:00.
- `data/interim/weather_canonical.parquet` — dạng đầu ra, sau làm sạch: 9.072 dòng, 2025-07-03 00:00:00+07:00 → 2026-07-15 23:00:00+07:00.

Issue #7 tiếp tục theo đúng trình tự chống rò rỉ: đóng băng tập dữ liệu → phân chia Train/Test theo
chuỗi thời gian tuyến tính → fit tiền xử lý **chỉ trên Train** → transform Train và Test.
