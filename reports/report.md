# Báo Cáo Tiến Trình Dự án & Phân Tích Dữ Liệu Milestone 2

## Project Progress & Data Analysis Report

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)  
> **Trường:** Đại học CMC, Khoa Công nghệ Thông tin & Truyền thông  
> **Giảng viên hướng dẫn:** ThS. Phạm Ngọc Đông  
> **Nhóm thực hiện:** Nhóm Chủ đề 6 (*Topic 6 Team*)  
> **Ngày báo cáo:** 30/09/2026  
> **Trạng thái:** Milestone 1 hoàn thành — Milestone 2 đang triển khai

---

## 1. Executive Summary

Báo cáo này tổng hợp toàn bộ tiến trình dự án **Phân Tích Mức Độ Ô Nhiễm Không Khí Theo Chuỗi Thời Gian** từ khi khởi tạo đến hết Milestone 2. Dự án tuân thủ phương pháp luận **CRISP-DM** và tập trung vào việc phân tích biến thiên nồng độ bụi mịn $\text{PM}_{2.5}$ tại Hà Nội cùng các yếu tố khí tượng bề mặt.

**Kết quả chính đạt được:**

| Chỉ tiêu | Kết quả |
|----------|---------|
| Dữ liệu chất lượng không khí | 8,022 bản ghi canonical (349,463 bản ghi thô) |
| Dữ liệu khí tượng | 9,072 bản ghi canonical (0% missing) |
| Độ phủ thời gian | 2025-07-03 → 2026-07-15 (100% overlap) |
| Unit tests | 101 tests (4 files) |
| Notebooks | 5 notebooks |
| Source modules | 3 modules (1,400 + 750 + 723 lines) |

**Trạng thái Milestone 2:**
- ✅ Issue #5 (Data Quality Audit): Hoàn thành, merge vào `main`
- ⚠️ Issue #6 (Deterministic Cleaning): Chưa triển khai
- ⚠️ Issue #7 (Preprocessing Pipeline): Đã triển khai trên branch, chưa merge vào `main`

---

## 2. Project Overview

### 2.1 Thông tin dự án

| Thuộc tính | Giá trị |
|------------|---------|
| Tên dự án | Phân Tích Mức Độ Ô Nhiễm Không Khí Theo Chuỗi Thời Gian |
| Môn học | INFO3020 – Nhập môn Khoa học Dữ liệu |
| Trường | Đại học CMC |
| Khoa | Công nghệ Thông tin & Truyền thông |
| Giảng viên | ThS. Phạm Ngọc Đông |
| Nhóm | Nhóm Chủ đề 6 |
| Phương pháp luận | CRISP-DM (6 giai đoạn) |
| Ngôn ngữ chính | Tiếng Việt |

### 2.2 Mục tiêu nghiên cứu

Dự án hướng tới việc phân tích có hệ thống dữ liệu chuỗi thời gian về nồng độ bụi mịn $\text{PM}_{2.5}$ tại khu vực đô thị Hà Nội cùng các yếu tố khí tượng bề mặt liên quan. Mục tiêu khoa học bao gồm:

1. Khám phá và mô tả trung thực hình thái phân phối thực nghiệm của $\text{PM}_{2.5}$
2. Định lượng các biến thiên chuỗi thời gian ở nhiều thang đo
3. Đánh giá mối liên hệ quan sát được giữa các thông số thời tiết và nồng độ bụi mịn
4. Xây dựng bài toán phân loại cảnh báo sớm ô nhiễm

### 2.3 Phạm vi địa lý

- **Khu vực nghiên cứu:** Hà Nội, Việt Nam
- **Trạm quan trắc:** 556 Nguyễn Văn Cừ, Long Biên, Hà Nội ($21.0491^\circ\text{N}, 105.8831^\circ\text{E}$)
- **Điểm lưới khí tượng:** $21.0545^\circ\text{N}, 105.8985^\circ\text{E}$ (cách trạm 1.7 km)
- **Bounding Box Hà Nội:** $[20.50, 21.60]^\circ\text{N}, [105.30, 106.10]^\circ\text{E}$

### 2.4 Tại sao cần xử lý dữ liệu theo chuỗi thời gian

Dữ liệu ô nhiễm không khí mang bản chất **chuỗi thời gian** (time-series) với các đặc điểm:

- **Phụ thuộc thời gian:** Quan sát tại thời điểm $t$ phụ thuộc vào các quan sát trước đó
- **Chu kỳ ngày đêm:** Nồng độ $\text{PM}_{2.5}$ biến thiên theo giờ trong ngày
- **Chu kỳ mùa vụ:** Có sự khác biệt giữa các mùa trong năm
- **Rò rỉ dữ liệu:** Chia tập Train/Test ngẫu nhiên sẽ gây rò rỉ thông tin từ tương lai vào quá khứ

Do đó, toàn bộ pipeline xử lý dữ liệu phải tuân thủ nghiêm ngặt nguyên tắc **temporal safety**.

---

## 3. Research Questions

### 3.1 Main Research Question

> *"Khảo sát quy luật biến thiên theo thời gian của nồng độ PM2.5 tại Hà Nội, định lượng mối liên hệ quan sát được với các yếu tố khí tượng bề mặt và xây dựng mô hình cảnh báo sớm nồng độ ô nhiễm dựa trên dữ liệu thực nghiệm được thu thập."*

### 3.2 Các câu hỏi thành phần (Sub-Questions)

| Research Question | Mục đích | Dữ liệu cần | Trạng thái |
|---|---|---|---|
| **SQ1** — Phân phối thực nghiệm | Khảo sát hình thái phân phối $\text{PM}_{2.5}$ (4 họ chỉ số) | Dữ liệu $\text{PM}_{2.5}$ đã làm sạch | ⏳ Chưa phân tích |
| **SQ2** — Biến thiên thời gian | Phân tích chu kỳ giờ, ngày, tháng, mùa | Dữ liệu chuỗi thời gian | ⏳ Chưa phân tích |
| **SQ3** — Liên hệ khí tượng | Mô hình hóa OLS giữa $\text{PM}_{2.5}$ và 6 biến khí tượng | Dữ liệu Train/Test đã split | ⏳ Chưa phân tích |
| **SQ4** — Cảnh báo sớm | Phân loại nhị phân cảnh báo ô nhiễm | Dữ liệu đã split + feature engineering | ⏳ Chưa phân tích |

> **Lưu ý quan trọng:** Tất cả các câu hỏi nghiên cứu đều là **kế hoạch phân tích**. Dữ liệu đã được thu thập và kiểm toán, nhưng phần phân tích thống kê và mô hình hóa (Milestone 3–4) **chưa được thực hiện**.

---

## 4. Project Timeline

### 4.1 Timeline trực quan

```text
Week 01
Project setup (Issue #1)
    ↓
Canonical Schema (Issue #2)
    ↓
Week 02
Source Profiling (Issue #19)
    ↓
Air Quality Collection (Issue #3)
    ↓
Weather Collection (Issue #4)
    ↓
Week 03–04
Data Quality Audit (Issue #5) ✅
    ↓
Deterministic Cleaning (Issue #6) ⏳
    ↓
Week 05
Preprocessing Pipeline (Issue #7) ⚠️
    ↓
Milestone 2 IN PROGRESS
```

### 4.2 Bảng tiến trình chi tiết

| Week | Milestone | Issue | Công việc | Trạng thái | Evidence |
|------|-----------|-------|-----------|------------|----------|
| 01 | M1 | #1 | Project setup, .gitignore, requirements.txt | ✅ Done | Commit `e4a3e28` |
| 01 | M1 | #2 | Research questions, Canonical Schema | ✅ Done | Commit `fe21343` |
| 02 | M1 | #19 | Source profiling & decision gate | ✅ Done | PR #21 merged |
| 02 | M1 | #3 | Air quality data collection (OpenAQ) | ✅ Done | PR #22, #24 merged |
| 02 | M1 | #4 | Weather data collection (Open-Meteo) | ✅ Done | PR #25, #26 merged |
| 03–04 | M2 | #5 | Data quality audit (6 dimensions) | ✅ Done | PR #27 merged |
| 04–05 | M2 | #6 | Deterministic data cleaning | ⏳ Not started | — |
| 05 | M2 | #7 | Preprocessing pipeline (leakage-safe) | ⚠️ Implemented on branch | PR #32 review |

---

## 5. Milestone 1 — Data Foundation

### 5.1 Project structure

```text
air-pollution-analysis/
├── .github/workflows/ci.yml    # CI pipeline (2 jobs)
├── data/
│   ├── raw/                      # Dữ liệu thô (gitignored)
│   │   └── metadata.json         # Provenance & SHA-256
│   ├── interim/                 # Dữ liệu canonical (gitignored)
│   └── processed/               # Dữ liệu sạch (gitignored)
├── docs/                         # Tài liệu dự án
├── notebooks/                    # 5 notebooks
├── scripts/
│   └── fetch_dataset.py          # Script thu thập dữ liệu
├── src/
│   ├── data_collection.py        # 1,400 lines
│   ├── data_quality.py           # 750 lines
│   └── cleaning_pipeline.py      # 723 lines
├── tests/                        # 4 test files, 101 tests
├── figures/                      # Biểu đồ (chưa có)
└── reports/                      # Báo cáo (file này)
```

### 5.2 Data sources

| Nguồn | Vai trò | Giấy phép | API key? | Phạm vi thời gian |
|-------|---------|-----------|----------|-------------------|
| OpenAQ S3 (loc=4946811) | Primary (chất lượng không khí) | ODC-BY v1.0 | Không | 2025-07-03 → 2026-07-15 |
| Open-Meteo ERA5 | Primary (khí tượng) | CC BY 4.0 | Không | 2023-01-01 → 2024-12-31 |
| AirNow DOS CSV | Fallback (lịch sử 2023) | US Public Domain | Có (login) | 2016 → 2023 |
| NOAA ISD 48820 | Fallback (khí tượng) | US Public Domain | Không | 2023 → 2024 |
| Kaggle datasets | Reference only | Non-uniform | Có | Phụ thuộc tác giả |
| PAM Air | Unused | Proprietary | Có (đóng) | — |

### 5.3 Data provenance

Dự án tuân thủ **Chính sách dữ liệu thô ba tầng** (Three-tier Raw Data Policy):

| Tầng | Mô tả | Evidence |
|------|-------|----------|
| Tầng A | Lưu trữ payload thô tại `data/raw/` | `data/raw/` (gitignored) |
| Tầng B | Bảo toàn & SHA-256 trong `metadata.json` | `data/raw/metadata.json` |
| Tầng C | Không Git-track raw files | `.gitignore` |

**SHA-256 hashes đã ghi nhận:**
- OpenAQ raw: `4168735570d16f80df7136e93b8da96bbb03ed5631c57ca8ffea6f09d92ae60f`
- Open-Meteo raw: `59bfececa2dc658c15898df082a19566fce7019048ec8236b55dc731f45bc79c`

### 5.4 Canonical Schema

| Column | Ý nghĩa | Type | Unit |
|--------|---------|------|------|
| `timestamp` | Mốc thời gian quan trắc | `datetime64[ns, Asia/Ho_Chi_Minh]` | UTC+7 |
| `station_id` | Mã định danh trạm | `string` | — |
| `location` | Tên địa danh | `string` | — |
| `pm25` | Nồng độ bụi mịn | `float64` | $\mu\text{g/m}^3$ |
| `pm10` | Nồng độ bụi thô | `float64` | $\mu\text{g/m}^3$ |
| `temperature` | Nhiệt độ không khí | `float64` | $^\circ\text{C}$ |
| `relative_humidity` | Độ ẩm tương đối | `float64` | $\%$ |
| `wind_speed` | Tốc độ gió | `float64` | $\text{m/s}$ |
| `wind_direction` | Hướng gió | `float64$ | Độ ($0^\circ-360^\circ$) |
| `precipitation` | Lượng mưa | `float64` | $\text{mm}$ |
| `surface_pressure` | Áp suất bề mặt | `float64` | $\text{hPa}$ |

### 5.5 Data collection pipeline

```text
OpenAQ S3 (352 CSV.gz files)
    ↓
Download & Extract
    ↓
Geographic Filtering (Hanoi BBox)
    ↓
Canonicalization (hourly aggregation)
    ↓
Parquet (data/interim/air_quality_canonical.parquet)
    ↓
8,022 canonical records

Open-Meteo ERA5 API
    ↓
Query with timezone=Asia/Ho_Chi_Minh
    ↓
Validation (schema, bounds, continuity)
    ↓
Parquet (data/interim/weather_canonical.parquet)
    ↓
9,072 canonical records
```

---

## 6. Milestone 2 — Data Quality Audit

### 6.1 Bộ kiểm toán 6 chiều

Module `src/data_quality.py` (750 lines) cung cấp bộ kiểm toán chất lượng dữ liệu theo **6 chiều quốc tế**:

| Chiều | Tên tiếng Việt | Mô tả |
|-------|----------------|-------|
| 1 | Completeness | Độ đầy đủ — tỷ lệ missing, độ bao phủ lưới thời gian |
| 2 | Accuracy | Độ chính xác — giới hạn vật lý, ràng buộc khí động học |
| 3 | Consistency | Độ nhất quán — đơn vị, múi giờ, thứ tự thời gian |
| 4 | Validity | Tính hợp lệ — định dạng dtype, lược đồ |
| 5 | Uniqueness | Tính duy nhất — khóa quan sát |
| 6 | Timeliness | Tính kịp thời — tần suất lấy mẫu, độ trễ |

### 6.2 Kết quả kiểm toán thực tế

#### Bảng tổng hợp missing data

| Cột | Dataset | Số dòng | Missing | % missing |
|-----|---------|---------|---------|-----------|
| `pm25` | Air Quality | 8,022 | 203 | 2.53% |
| `pm10` | Air Quality | 8,022 | 123 | 1.53% |
| `temperature` | Weather | 9,072 | 0 | 0.00% |
| `relative_humidity` | Weather | 9,072 | 0 | 0.00% |
| `wind_speed` | Weather | 9,072 | 0 | 0.00% |
| `wind_direction` | Weather | 9,072 | 0 | 0.00% |
| `precipitation` | Weather | 9,072 | 0 | 0.00% |
| `surface_pressure` | Weather | 9,072 | 0 | 0.00% |

#### Bảng kiểm toán 6 chiều

| Chiều | Kết quả | Đánh giá |
|-------|---------|----------|
| **Completeness** | Weather: 100% đầy đủ; Air: PM2.5 97.47%, PM10 98.47% | ✅ Tốt |
| **Accuracy** | 0 giá trị âm; 282 cặp PM2.5 > PM10 + 2.0 (3.66%) | ⚠️ Cần xử lý |
| **Consistency** | 100% đồng nhất UTC+7, monotonic timestamp | ✅ Tốt |
| **Validity** | 100% dtype hợp lệ theo Canonical Schema | ✅ Tốt |
| **Uniqueness** | 0 duplicate trên khóa (station_id, timestamp) | ✅ Tốt |
| **Timeliness** | Median 1.0 giờ; 1,022 gaps (11.30%) | ⚠️ Cần reindex |

### 6.3 Phân tích missingness theo Rubin

| Cơ chế | Bằng chứng | Kết luận |
|--------|------------|----------|
| **MCAR** | 35 đợt mất 1 giờ đơn lẻ (52.2%) | Giả thuyết: telemetry drop |
| **MAR** | Missing tập trung ban đêm (3.80–4.79%), PM10 thấp khi PM2.5 missing | Giả thuyết: phụ thuộc thời tiết |
| **MNAR** | Không có bằng ngạt cảm biến | Không bằng chứng ủng hộ |

> **Tuyên bố bất định:** Dữ liệu quan sát hiện tại chưa đủ cơ sở để khẳng định dứt khoát cơ chế khuyết thiếu.

---

## 7. Data Quality Results

### 7.1 Số liệu thực tế

| Metric | Before cleaning | After cleaning | Change |
|--------|-----------------|----------------|--------|
| Số dòng Air Quality | 8,022 | 8,022 | 0 |
| Số dòng Weather | 9,072 | 9,072 | 0 |
| PM2.5 missing | 203 (2.53%) | 203 (2.53%) | 0 |
| PM10 missing | 123 (1.53%) | 123 (1.53%) | 0 |
| Duplicate | 0 | 0 | 0 |
| PM2.5 > PM10 + 2.0 | 282 (3.66%) | 282 (3.66%) | 0 |
| Temporal gaps | 1,022 (11.30%) | 1,022 (11.30%) | 0 |

> **Lưu ý:** Bảng trên thể hiện trạng thái **trước và sau kiểm toán** (Issue #5). Issue #6 (Deterministic Cleaning) **chưa được triển khai**, nên số liệu "After cleaning" vẫn giống "Before cleaning". Các thay đổi thực sự sẽ được ghi nhận tại `docs/cleaning_log.md` khi Issue #6 hoàn thành.

### 7.2 Thông tin station

| Thuộc tính | Giá trị |
|------------|---------|
| Số station | 1 |
| Station ID | `VN001_HANOI_556_NGUYEN_VAN_CU` |
| Vị trí | 556 Nguyễn Văn Cừ, Long Biên, Hà Nội |
| Tọa độ | $21.0491^\circ\text{N}, 105.8831^\circ\text{E}$ |

### 7.3 Weather coverage

| Thuộc tính | Giá trị |
|------------|---------|
| Số bản ghi | 9,072 |
| Dải thời gian | 2025-07-03 00:00 → 2026-07-15 23:00 |
| Missing | 0 (0.00%) |
| Continuous | 100% (1 giờ liên tục) |

### 7.4 Overlap giữa Air Quality và Weather

| Thuộc tính | Giá trị |
|------------|---------|
| Số bản ghi giao thoa | 8,022 |
| Độ phủ | 100.00% |
| Row explosion | Không |

---

## 8. Milestone 2 — Deterministic Data Cleaning

### 8.1 Trạng thái triển khai

> **Issue #6 (Deterministic Data Cleaning) — CHƯA TRIỂN KHAI**

Dự án hiện tại **chưa có**:
- `src/cleaning.py` — module cleaning
- `docs/cleaning_log.md` — nhật ký làm sạch
- `notebooks/03_data_cleaning.ipynb` — notebook cleaning

### 8.2 Kế hoạch cleaning (theo roadmap)

| Transformation | Rule | Rows affected | Reason |
|----------------|------|---------------|--------|
| Timezone normalization | UTC+7 | 0 | Đã canonical từ #3/#4 |
| Duplicate removal | Khóa (station_id, timestamp) | 0 | Đã verify unique |
| Negative value handling | PM2.5 < 0 → NaN | 0 | Đã verify không có |
| Physical constraints | PM2.5 > PM10 + ε → NaN | 282 | Chờ xử lý |
| Stuck sensor detection | > 6h không đổi → NaN | ? | Chờ xử lý |
| High humidity flag | RH > 90% → flag | 2,843 | Chờ xử lý |
| Missingness flags | pm25_was_missing | ? | Chờ xử lý |
| Hourly reindexing | Lưới 1h liên tục | 1,022 gaps | Chờ xử lý |

> **Lưu ý:** Số `Rows affected` sẽ được xác định chính xác khi Issue #6 được triển khai và ghi nhận vào `docs/cleaning_log.md`.

---

## 9. Before vs After Cleaning

### 9.1 Trạng thái hiện tại

Vì Issue #6 chưa được triển khai, **không có số liệu Before/After thực tế** để trình bày. Các biểu đồ so sánh sẽ được tạo khi:

1. `src/cleaning.py` được implement
2. `docs/cleaning_log.md` được tạo với số liệu cụ thể
3. Pipeline được chạy trên dữ liệu thực tế

### 9.2 Kế hoạch visualization

Khi Issue #6 hoàn thành, các biểu đồ sau sẽ được tạo:

- **Figure 1:** Missingness Before vs After (bar chart)
- **Figure 2:** Data Cleaning Impact (flow chart: Raw → Canonical → Audited → Cleaned)
- **Figure 3:** PM2.5 Distribution Before vs After (histogram)

---

## 10. Milestone 2 — Data Integration

### 10.1 Pipeline tích hợp (Issue #7)

Module `src/cleaning_pipeline.py` (723 lines) cung cấp các function độc lập:

```text
Air Quality (8,022 rows)
      +
Weather (9,072 rows)
      ↓
Key validation (station_id, timestamp)
      ↓
Safe merge (row-explosion protection)
      ↓
Dataset freeze (metadata)
      ↓
Chronological split (temporal cutoff)
      ↓
Train-only fitting (SimpleImputer + RobustScaler)
      ↓
Train/Test transform
      ↓
Processed Parquet
```

### 10.2 Các function chính

| Function | Mô tả | Lines |
|----------|-------|-------|
| `add_cyclical_time_features()` | Thêm hour_sin/cos, month_sin/cos | 80–116 |
| `chronological_split()` | Split theo thời gian (không random) | 124–178 |
| `build_preprocessing_pipeline()` | sklearn Pipeline + ColumnTransformer | 186–238 |
| `fit_pipeline_on_train()` | Fit strictly trên Train | 241–262 |
| `transform_with_pipeline()` | Transform Train/Test | 265–286 |
| `merge_air_weather()` | Merge với row-explosion protection | 351–414 |
| `export_to_parquet()` | Xuất Parquet (snappy) | 422–469 |
| `freeze_dataset()` | Ghi nhận metadata | 490–541 |
| `validate_no_leakage()` | Kiểm tra không fit trên Test | 590–671 |

### 10.3 Tại sao merge không gây Row Explosion

Hàm `merge_air_weather()` có cơ chế bảo vệ:

1. **Kiểm tra uniqueness** của khóa trên mỗi bảng trước khi merge
2. **Assert** `len(df_merged) <= len(df_air)` sau khi merge
3. **Validation** quan hệ `1:1` giữa hai bảng

---

## 11. Final Dataset Results

### 11.1 Trạng thái hiện tại

> **File `data/processed/air_pollution_final.parquet` CHƯA TỒN TẠI**

Dataset cuối cùng của Milestone 2 chưa được tạo vì:
- Issue #6 (Cleaning) chưa triển khai
- Issue #7 (Preprocessing) chưa merge vào main

### 11.2 Số liệu dự kiến (từ metadata.json)

| Thuộc tính | Giá trị |
|------------|---------|
| Số rows | 8,022 (giao thoa) |
| Số columns | 11 (Canonical) + 4 (cyclical) + flags |
| Timestamp range | 2025-07-03 22:00 → 2026-07-15 17:00 |
| Số stations | 1 |
| Missing PM2.5 | 203 (2.53%) |
| Missing PM10 | 123 (1.53%) |
| Duplicate | 0 |
| Train/Test split | Chưa xác định |

### 11.3 Cách tạo dataset

```bash
# 1. Thu thập dữ liệu
python scripts/fetch_dataset.py

# 2. Chạy notebooks theo thứ tự
jupyter nbconvert --execute notebooks/01_data_collection.ipynb
jupyter nbconvert --execute notebooks/02_quality_audit.ipynb

# 3. Sau khi Issue #6 hoàn thành:
# - Chạy src/cleaning.py
# - Chạy src/cleaning_pipeline.py
# - Output: data/processed/air_pollution_final.parquet
```

---

## 12. Train / Test Split

### 12.1 Trạng thái hiện tại

> **Train/Test split CHƯA ĐƯỢC XÁC ĐỊNH**

Theo roadmap, điểm cắt sẽ được xác định dựa trên:
- Độ bao phủ thực tế của dữ liệu
- Kích thước mẫu đủ lớn
- Tính đại diện theo mùa
- **Không** đặt trước tỷ lệ cố định

### 12.2 Kế hoạch split

| Property | Train | Test |
|----------|-------|------|
| Rows | ~70% | ~30% |
| Start | 2025-07-03 | TBD |
| End | TBD | 2026-07-15 |
| PM2.5 statistics | TBD | TBD |
| Missingness | TBD | TBD |

### 12.3 Tại sao dùng chronological split

| Nguyên tắc | Giải thích |
|------------|------------|
| Temporal leakage | Random split cho phép mô hình "nhìn" tương lai |
| Realism | Dự báo thực tế chỉ dùng quá khứ |
| Seasonality | Train/Test phải cover đủ mùa |

---

## 13. Leakage Prevention

### 13.1 Kiến trúc chống rò rỉ

```text
┌─────────────────────────────────────────┐
│           TRAIN SET ONLY                │
│  ┌─────────────────────────────────┐    │
│  │  SimpleImputer (median)         │    │
│  │  RobustScaler (IQR)             │    │
│  │  Fit HERE ONLY                  │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
                    ↓
            Transform parameters
                    ↓
┌─────────────────────────────────────────┐
│           TEST SET                      │
│  ┌─────────────────────────────────┐    │
│  │  SimpleImputer (median)         │    │
│  │  RobustScaler (IQR)             │    │
│  │  Transform ONLY (no fit)        │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### 13.2 Các lớp bảo vệ

| Lớp | Mô tả | Implementation |
|-----|-------|----------------|
| 1 | Fit chỉ trên Train | `fit_pipeline_on_train()` |
| 2 | Transform Test | `transform_with_pipeline()` |
| 3 | Không fit lại | `validate_no_leakage()` |
| 4 | Target không lọt vào features | `NUMERIC_FEATURES` excludes `pm25` |
| 5 | Temporal separation | `chronological_split()` |

### 13.3 Validation

Hàm `validate_no_leakage()` kiểm tra:
1. Pipeline đã fit (có `named_steps`)
2. Imputer đã fit (có `statistics_`)
3. Scaler đã fit (có `center_`, `scale_`)
4. **So sánh** imputer/scaler với Train median

---

## 14. Final Data Visualization

### 14.1 Trạng thái hiện tại

> **Chưa có biểu đồ nào được tạo** vì:
> - `data/processed/air_pollution_final.parquet` chưa tồn tại
> - Issue #6 và #7 chưa hoàn thành

### 14.2 Kế hoạch visualization

Khi dataset sẵn sàng, các biểu đồ sau sẽ được tạo:

| Figure | Tên | Dữ liệu | Trạng thái |
|--------|-----|---------|------------|
| FIG-01 | PM2.5 over Time | timestamp, pm25 | ⏳ Planned |
| FIG-02 | PM2.5 Distribution | pm25 | ⏳ Planned |
| FIG-03 | PM2.5 by Month | month, pm25 | ⏳ Planned |
| FIG-04 | Correlation Heatmap | All numeric | ⏳ Planned |
| FIG-05 | Train/Test Timeline | timestamp | ⏳ Planned |
| FIG-06 | Missingness Heatmap | All columns | ⏳ Planned |
| FIG-07 | PM2.5 by Station | station_id, pm25 | ⏳ Planned |

### 14.3 Yêu cầu visualization

- Lấy từ dữ liệu thật (không giả lập)
- Có title, axis label, unit
- Có caption
- Resolution 300 DPI
- Lưu tại `figures/report/`

---

## 15. Statistical Results Currently Available

### 15.1 Trạng thái các giai đoạn

```text
Milestone 2
├── Data collection       ✅ Done
├── Data quality audit    ✅ Done
├── Cleaning              ⏳ Not started
├── Integration           ⚠️ Implemented (not merged)
├── Leakage prevention    ⚠️ Implemented (not merged)
├── EDA                   ⏳ Not started
├── Statistical inference ⏳ Not started
└── ML models             ⏳ Not started
```

### 15.2 Kết quả thống kê đã có

| Chỉ số | Giá trị | Nguồn |
|--------|---------|-------|
| PM2.5 mean | 46.31 µg/m³ | metadata.json |
| PM2.5 median | 37.91 µg/m³ | data_quality_audit.md |
| PM2.5 std | 32.69 µg/m³ | metadata.json |
| PM2.5 min | 1.06 µg/m³ | data_quality_audit.md |
| PM2.5 max | 252.64 µg/m³ | data_quality_audit.md |
| PM2.5 missing | 203 (2.53%) | metadata.json |
| PM10 mean | 65.97 µg/m³ | data_quality_audit.md |
| PM10 median | 55.56 µg/m³ | data_quality_audit.md |
| Temperature mean | 24.87°C | metadata.json |
| RH mean | 80.63% | metadata.json |
| Wind speed mean | 2.41 m/s | metadata.json |

### 15.3 Kết quả chưa có

- Skewness, Kurtosis của PM2.5
- Correlation matrix
- OLS regression coefficients
- Classification metrics (Recall, Precision, PR-AUC)
- Hypothesis test results (p-value, effect size)

---

## 16. Testing & Reproducibility

### 16.1 Unit tests

| Component | Tests | Status |
|-----------|-------|--------|
| `test_data_collection.py` | 57 | ✅ Pass |
| `test_data_quality.py` | 14 | ✅ Pass |
| `test_cleaning_pipeline.py` | 21 | ✅ Pass |
| `test_fetch_dataset.py` | 9 | ✅ Pass |
| **Total** | **101** | ✅ |

### 16.2 CI Pipeline

| Job | Mô tả | Status |
|-----|-------|--------|
| `validate` | compileall, import, unittest, whitespace | ✅ |
| `notebook-smoke` | Execute 00_environment_test.ipynb | ✅ |

### 16.3 Determinism

- `random_state=42` cho mọi thao tác ngẫu nhiên
- Notebooks chạy tuần tự từ đầu đến cuối
- Không phụ thuộc thứ tự thực thi song song

---

## 17. Current Project Status

### 17.1 Bảng tổng kết

| Milestone / Issue | Status | Evidence |
|-------------------|--------|----------|
| **M1** | ✅ Complete | Multiple PRs merged |
| #1 Project setup | ✅ Done | Commit `e4a3e28` |
| #2 Research questions | ✅ Done | Commit `fe21343` |
| #19 Source profiling | ✅ Done | PR #21 merged |
| #3 Air quality collection | ✅ Done | PR #22, #24 merged |
| #4 Weather collection | ✅ Done | PR #25, #26 merged |
| **M2** | ⚠️ In Progress | — |
| #5 Data quality audit | ✅ Done | PR #27 merged |
| #6 Deterministic cleaning | ⏳ Not started | — |
| #7 Preprocessing pipeline | ⚠️ On branch | PR #32 review |
| **M3** | ⏳ Not started | — |
| #8 EDA | ⏳ Not started | — |
| #9 Visualization | ⏳ Not started | — |
| #10 Midterm report | ⏳ Not started | — |
| **M4** | ⏳ Not started | — |
| #11 Hypothesis testing | ⏳ Not started | — |
| #12 OLS regression | ⏳ Not started | — |
| #13 Classification | ⏳ Not started | — |
| **M5** | ⏳ Not started | — |
| #14 Bias audit | ⏳ Not started | — |
| #15 Datasheet | ⏳ Not started | — |
| **M6** | ⏳ Not started | — |
| #16 Final report | ⏳ Not started | — |
| #17 Defense | ⏳ Not started | — |

### 17.2 Phân biệt merged vs branch-only

| Feature | Branch | Merged to main |
|---------|--------|----------------|
| Data collection (M1) | — | ✅ |
| Data quality audit (M1) | — | ✅ |
| Preprocessing pipeline (M2) | `feat/issue-7-preprocessing-pipeline` | ❌ |
| Processed data preview | `feat/m2-processed-data-preview` | ❌ |

---

## 18. Limitations

### 18.1 Giới hạn dữ liệu

| Giới hạn | Mô tả | Tác động |
|----------|-------|----------|
| 1 station | Chỉ có trạm 556 Nguyễn Văn Cừ | Không phân tích không gian |
| 1 chu kỳ mùa | Dữ liệu 2025-07 → 2026-07 | Chưa đủ 2 năm |
| Không có 2023–2024 | OpenAQ mới tích hợp từ 07/2025 | Không so sánh dài hạn |
| AirNow chưa chạy | Thiếu dữ liệu lịch sử 2023 | Không có ground truth 2023 |

### 18.2 Giới hạn kỹ thuật

| Giới hạn | Mô tả |
|----------|-------|
| Chưa có EDA | Phân tích thống kê chưa thực hiện |
| Chưa có ML | Mô hình hóa chưa bắt đầu |
| Chưa có visualization | Biểu đồ chưa được tạo |
| Raw data không Git-track | Cần chạy pipeline để tái tạo |

### 18.3 Giới hạn về thời gian

- Dữ liệu chỉ trong ~1 năm (2025-07 → 2026-07)
- Chưa đủ dài để phân tích xu hướng dài hạn
- Chưa đủ để kiểm định seasonal pattern ổn định

---

## 19. Next Steps

### 19.1 Milestone 2 (tiếp theo)

```text
1. Issue #6 — Deterministic Cleaning
   - Implement src/cleaning.py
   - Create docs/cleaning_log.md
   - Run on real data
   - Record rows affected

2. Issue #7 — Merge to main
   - Address PR #32 review feedback
   - Merge feat/issue-7-preprocessing-pipeline → main

3. Generate processed dataset
   - Run full pipeline
   - Output: data/processed/air_pollution_final.parquet
```

### 19.2 Milestone 3 (sau M2)

```text
- Issue #8: EDA (4 họ thống kê, chu kỳ thời gian)
- Issue #9: Visualization (7 biểu đồ FIG-01 → FIG-07)
- Issue #10: Midterm report (SCQA, 8–10 pages)
```

### 19.3 Milestone 4 (sau M3)

```text
- Issue #11: Hypothesis testing (Mann-Whitney U, effect size, Bootstrap CI)
- Issue #12: OLS regression (LINE diagnostics, VIF, Ridge/Lasso)
- Issue #13: Classification (Recall, PR-AUC, threshold tuning)
```

### 19.4 Milestone 5–6

```text
- Issue #14: Bias audit, computational resources
- Issue #15: Datasheet, Model Card
- Issue #16: Final report
- Issue #17: Defense
```

---

## 20. Conclusion

### 20.1 Những gì đã hoàn thành

Dự án đã hoàn thành **Milestone 1** và phần lớn **Milestone 2**:

1. ✅ **Data collection pipeline** — 8,022 air quality records + 9,072 weather records
2. ✅ **Data quality audit** — 6-dimension framework, 101 unit tests
3. ✅ **Provenance & metadata** — SHA-256, three-tier raw data policy
4. ✅ **CI/CD** — GitHub Actions với 2 jobs
5. ⚠️ **Preprocessing pipeline** — Implemented, chưa merge

### 20.2 Chất lượng dữ liệu

| Tiêu chí | Kết quả |
|----------|---------|
| Completeness | Weather 100%, Air 97.47% (PM2.5) |
| Accuracy | 0 negative values, 282 physical violations |
| Consistency | 100% UTC+7, monotonic |
| Validity | 100% schema conformant |
| Uniqueness | 0 duplicates |
| Timeliness | 1.0 giờ median, 11.30% gaps |

### 20.3 Khả năng tái lập

- ✅ Deterministic (random_state=42)
- ✅ CI-tested (101 tests)
- ✅ Documented (README, CONTRIBUTING, docs/)
- ⚠️ Cần chạy pipeline để tái tạo dữ liệu

### 20.4 Sẵn sàng cho Milestone 3

Dataset hiện tại **sẵn sàng** cho các bước tiếp theo:
- EDA (Issue #8)
- Visualization (Issue #9)
- Midterm report (Issue #10)

Sau khi Issue #6 hoàn thành, dataset sẽ được làm sạch và sẵn sàng cho modeling.

---

## 21. Appendix — Dataset Schema

### 21.1 Canonical Schema (11 fields)

| Column | Type | Description | Unit |
|--------|------|-------------|------|
| `timestamp` | `datetime64[ns, Asia/Ho_Chi_Minh]` | Mốc thời gian quan trắc | UTC+7 |
| `station_id` | `string` | Mã định danh trạm | — |
| `location` | `string` | Tên địa danh | — |
| `pm25` | `float64` | Nồng độ bụi mịn | $\mu\text{g/m}^3$ |
| `pm10` | `float64` | Nồng độ bụi thô | $\mu\text{g/m}^3$ |
| `temperature` | `float64` | Nhiệt độ không khí | $^\circ\text{C}$ |
| `relative_humidity` | `float64` | Độ ẩm tương đối | $\%$ |
| `wind_speed` | `float64` | Tốc độ gió | $\text{m/s}$ |
| `wind_direction` | `float64` | Hướng gió | Độ |
| `precipitation` | `float64` | Lượng mưa | $\text{mm}$ |
| `surface_pressure` | `float64` | Áp suất bề mặt | $\text{hPa}$ |

### 2.2 Engineered Features (dự kiến)

| Column | Type | Description |
|--------|------|-------------|
| `hour_sin` | `float64` | $\sin(2\pi \cdot \text{hour}/24)$ |
| `hour_cos` | `float64` | $\cos(2\pi \cdot \text{hour}/24)$ |
| `month_sin` | `float64` | $\sin(2\pi \cdot \text{month}/12)$ |
| `month_cos` | `float64` | $\cos(2\pi \cdot \text{month}/12)$ |
| `pm25_was_missing` | `int` | Cờ missing (1=missing) |
| `pm25_was_stuck` | `int` | Cờ stuck sensor (1=stuck) |
| `is_high_humidity_fog` | `int` | Cờ RH > 90% (1=fog risk) |

---

## Tài liệu tham chiếu

| Tài liệu | Đường dẫn |
|----------|-----------|
| Roadmap | `docs/roadmap.md` |
| Data Dictionary | `docs/data_dictionary.md` |
| Research Questions | `docs/research_questions.md` |
| Source Profiling Decision | `docs/source_profiling_decision.md` |
| Data Quality Audit | `docs/data_quality_audit.md` |
| Project Overview | `docs/air_quality_project_overview.md` |
| README | `README.md` |
| Contributing Guide | `CONTRIBUTING.md` |

---

*Báo cáo được tạo bởi Nhóm Chủ đề 6 — INFO3020, Đại học CMC*
