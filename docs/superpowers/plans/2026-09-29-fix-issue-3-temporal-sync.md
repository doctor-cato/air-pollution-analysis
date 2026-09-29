# Kế Hoạch Triển Khai: Đồng Bộ Dải Thời Gian Khí Tượng & Khắc Phục Hiện Trạng Pipeline (Issue #3 & Issue #4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khắc phục triệt để lỗi lệch pha thời gian (temporal misalignment) giữa dữ liệu chất lượng không khí OpenAQ 4946811 (07/2025–07/2026) và dữ liệu khí tượng Open-Meteo ERA5 (đang bị hardcode 2023–2024), hiện thực hóa cơ chế đồng bộ thời gian động tuân thủ tiêu chí nghiệm thu Issue #4 và sẵn sàng cho bước tích hợp dữ liệu tại Issue #7.

**Architecture:** 
1. Cải tiến `OpenMeteoAdapter` tự động sinh tên tệp cache theo khoảng ngày `open_meteo_raw_{start_date}_{end_date}.json` thay vì hardcode cố định.
2. Nâng cấp `run_collection_pipeline()` trong `src/data_collection.py` hỗ trợ cơ chế đồng bộ động: nếu không chỉ định cửa sổ thời gian cứng, pipeline tự động trích xuất `min_date` và `max_date` từ chuỗi quan trắc `df_air_canonical` để gửi truy vấn Open-Meteo ERA5, bảo đảm hai chuỗi interim canonical có phần giao thời gian 100%.
3. Bổ sung unit tests kiểm thử cơ chế đồng bộ động và kiểm định không rỗng khi join theo timestamp.
4. Chạy lại ingestion, cập nhật `data/raw/metadata.json`, tài liệu `docs/source_profiling_decision.md` và thực thi kernel sạch sẽ cho `notebooks/01_data_collection.ipynb`.

**Tech Stack:** Python 3.10+, pandas, numpy, unittest, urllib, pyarrow (Snappy Parquet), matplotlib, seaborn.

**Spec:** GitHub Issue #3, Issue #4, Issue #19, `docs/source_profiling_decision.md`, `docs/roadmap.md`.

## Global Constraints

- Chế độ dữ liệu thô: Áp dụng Chính sách dữ liệu thô ba tầng (Mục 3.2 Roadmap), lưu tệp raw JSON/Parquet nguyên bản không sửa đổi thủ công, kiểm toán qua SHA-256 trong metadata.json.
- Múi giờ chuẩn: `Asia/Ho_Chi_Minh` (UTC+7) trên toàn bộ các chuỗi thời gian.
- Khóa quan trắc chuẩn: `(station_id, timestamp)` duy nhất, không duplicate.
- Liêm chính học thuật: Tuyệt đối không tạo dữ liệu giả lập (no synthetic/mock data).
- Tính tái lập: 100% unit tests pass, notebook thực thi tuần tự từ cell 1 đến hết không lỗi.

## Review Focus

1. **Lệch pha thời gian (Temporal Disjointness):** `df_air_canonical` (2025–2026) và `df_weather_canonical` (2023–2024) không giao nhau $\to$ Test: `test_air_and_weather_temporal_overlap_not_empty`.
2. **Xung đột cache Open-Meteo:** Khi đổi khoảng ngày query, `OpenMeteoAdapter` nạp nhầm file cache cũ $\to$ Test: `test_open_meteo_raw_filename_reflects_date_range`.
3. **Truy vấn Open-Meteo tự động từ dữ liệu trạm:** Pipeline không truyền `study_window_start`/`end` tự động khớp với trạm 4946811 $\to$ Test: `test_dynamic_sync_dates_derived_from_air_quality`.
4. **Bảo tồn tính năng AirNow adapter:** Đảm bảo `AirNowDOSAdapter` vẫn giữ nguyên trạng thái `implemented / not_executed_pending_raw_input` mà không văng lỗi khi file thiếu.
5. **Tính toàn vẹn của metadata:** Khối `collection_pipeline_execution` trong `metadata.json` phải phản ánh đúng dải ngày thực tế được query và mã SHA-256 mới.

---

### Task 1: Nâng cấp OpenMeteoAdapter và Hàm Đồng Bộ Thời Gian Động trong `src/data_collection.py`

**Files:**
- Modify: `src/data_collection.py:473-543` (OpenMeteoAdapter)
- Modify: `src/data_collection.py:595-750` (run_collection_pipeline)
- Test: `tests/test_data_collection.py`

**Interfaces:**
- Consumes: `df_air_canonical["timestamp"]`
- Produces: `OpenMeteoAdapter.fetch_raw_data(start_date, end_date, raw_output_name=None)`, `run_collection_pipeline(study_window_start=None, study_window_end=None, ...)` tự động đồng bộ theo dải ngày thực tế của chuỗi ô nhiễm.

- [ ] **Step 1: Viết failing unit tests trong `tests/test_data_collection.py`**
  - Viết `test_open_meteo_raw_filename_reflects_date_range`: Kiểm tra hàm sinh tên file tự động `open_meteo_raw_2025-07-03_2026-07-15.json` khi `raw_output_name=None`.
  - Viết `test_air_and_weather_temporal_overlap_not_empty`: Tạo 2 sample DataFrames có cùng dải thời gian và xác minh phép inner join theo `timestamp` trả về số dòng > 0.
  - Viết `test_dynamic_sync_window_derivation`: Kiểm tra logic trích xuất `min_date` và `max_date` (dạng `YYYY-MM-DD`) từ chuỗi timestamp tz-aware UTC+7.

- [ ] **Step 2: Chạy unit tests để xác nhận các test mới fail hoặc chưa khớp**
  - Run: `python -m unittest tests/test_data_collection.py`
  - Expected: FAIL do hàm hoặc tham số chưa hỗ trợ dynamic filename.

- [ ] **Step 3: Cập nhật `OpenMeteoAdapter.fetch_raw_data()` và `run_collection_pipeline()` trong `src/data_collection.py`**
  - Trong `OpenMeteoAdapter.fetch_raw_data()`: nếu `raw_output_name is None`, tự động sinh `raw_output_name = f"open_meteo_raw_{start_date}_{end_date}.json"`.
  - Trong `run_collection_pipeline()`:
    - Nếu `study_window_start is None`: gán bằng `df_air_canonical["timestamp"].min().strftime("%Y-%m-%d")`.
    - Nếu `study_window_end is None`: gán bằng `df_air_canonical["timestamp"].max().strftime("%Y-%m-%d")`.
    - Gọi `weather_adapter.fetch_raw_data(start_date=query_start, end_date=query_end)`.
    - Ghi nhận `requested_query_window` và `actual_source_coverage` chính xác theo dải thời gian đồng bộ.

- [ ] **Step 4: Chạy lại toàn bộ unit tests để xác nhận 100% PASS**
  - Run: `python -m unittest tests/test_data_collection.py`
  - Expected: 13/13 tests PASS.

---

### Task 2: Thực thi Pipeline Ingestion Đồng Bộ & Cập Nhật Dữ Liệu Interim

**Files:**
- Execute: `src/data_collection.py`
- Modify: `data/raw/metadata.json`
- Output: `data/raw/open_meteo_raw_2025-07-03_2026-07-15.json` (tự động tạo qua API), `data/interim/weather_canonical.parquet` (Snappy Parquet)

- [ ] **Step 1: Thực thi pipeline qua command line**
  - Run: `python src/data_collection.py`
  - Expected: Tải thành công dữ liệu Open-Meteo ERA5 từ `2025-07-03` đến `2026-07-15` khớp 100% với trạm OpenAQ 4946811.
  - Xuất ra `data/interim/air_quality_canonical.parquet` và `data/interim/weather_canonical.parquet`.
  - Cả hai file interim đều có dải thời gian trùng khớp trong tháng 07/2025 – 07/2026.

- [ ] **Step 2: Kiểm tra tính toàn vẹn và không rỗng của phép ghép nối**
  - Chạy script kiểm tra nhanh: nạp cả 2 tệp interim, thực hiện `pd.merge(df_air, df_weather, on="timestamp")`.
  - Assert `len(df_merged) > 7,000` (đảm bảo không còn lỗi 0 dòng của Issue #7).

- [ ] **Step 3: Cập nhật `data/raw/metadata.json`**
  - Ghi nhận `execution_timestamp_utc`, thông số `open_meteo_ingestion` với dải ngày đồng bộ thực tế (`2025-07-03` $\to$ `2026-07-15`), mã SHA-256 của file raw mới, số bản ghi canonical.

---

### Task 3: Cập Nhật Tài Liệu `docs/source_profiling_decision.md`

**Files:**
- Modify: `docs/source_profiling_decision.md:433-479`

- [ ] **Step 1: Cập nhật Mục 13 và Mục 14 trong `docs/source_profiling_decision.md`**
  - Làm rõ quyết định kỹ thuật: Do trạm chuẩn quốc gia OpenAQ 4946811 có độ bao phủ từ 07/2025 đến 07/2026, pipeline thu thập tự động đã đồng bộ động dải thời gian khí tượng ERA5 tương ứng (07/2025 – 07/2026) để bảo đảm tính toàn vẹn khi phân tích tương quan và mô hình hóa.
  - Ghi rõ `AirNowDOSAdapter` là giải pháp kỹ thuật sẵn sàng nạp offline cho dữ liệu lịch sử 2023 khi có tài khoản tổ chức.

---

### Task 4: Đồng Bộ và Thực Thi Notebook `notebooks/01_data_collection.ipynb`

**Files:**
- Modify: `notebooks/01_data_collection.ipynb`

- [ ] **Step 1: Cập nhật Cell 2 và Cell 7 trong Notebook**
  - Cell 2: Sử dụng cơ chế đồng bộ động để nạp thời tiết theo dải thực tế của OpenAQ 4946811.
  - Cell 6 & 7: Kiểm định assertion giao thời gian; vẽ 2 biểu đồ chuỗi thời gian (PM2.5 và Nhiệt độ) trên **cùng một trục thời gian đồng nhất** (07/2025 – 07/2026).
  - Cell 8: Ghi nhận metadata audit đầy đủ.

- [ ] **Step 2: Thực thi sạch sẽ qua nbconvert / Restart Kernel & Run All**
  - Run: `python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_collection.ipynb`
  - Expected: Exit code 0, toàn bộ cell output sạch sẽ, có biểu đồ hiển thị dải thời gian đồng bộ.

---

### Task 5: Kiểm Thử Toàn Diện & Chuẩn Bị Pull Request Mới

**Files:**
- Verify: toàn bộ repo
- Run: `git status`, `git diff`, `python -m unittest tests/test_data_collection.py`

- [ ] **Step 1: Chạy toàn bộ test suite**
  - Run: `python -m unittest discover tests`
  - Expected: 100% tests PASS.

- [ ] **Step 2: Review `git diff`**
  - Đảm bảo không có secret, không có file rác build/cache, không sửa file raw trực tiếp.

- [ ] **Step 3: Commit và sẵn sàng mở PR mới**
  - Commit theo chuẩn Conventional Commits: `fix(pipeline): synchronize dynamic meteorological window with air quality timeline (#3, #4)`.
