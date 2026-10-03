# 02 — Nhật ký chi tiết từng Issue và PR

> Nguyên tắc: mỗi mục ghi lại **trạng thái tại thời điểm đó**, review/comment đã đưa ra,
> fix đáp ứng, và **sai sót còn lại tại thời điểm đó**.
> Nguồn: GitHub API (`gh issue view` / `gh pr view`) + `git show --stat` cho 14 merge commit.

---

## PHẦN A — MILESTONE

| # | Tiêu đề | Trạng thái | Issue đóng | Issue mở |
|---|---|---|---:|---:|
| 1 | Milestone 1: Thiết lập Dự án, Khảo sát Nguồn & Thu thập Dữ liệu (Week 1–2) | **closed** 29/09 14:18 | 5 | 0 |
| 2 | Milestone 2: Kiểm toán & Làm sạch Dữ liệu (Week 3–5) | **closed** 30/09 04:27 | 3 | 0 |
| 3 | Milestone 3: Báo cáo EDA Giữa kỳ (Week 6–8) | open | 0 | 3 |
| 4 | Milestone 4: Suy luận Thống kê & Mô hình hóa (Week 9–11) | open | 0 | 3 |
| 5 | Milestone 5: Project Charter, Đạo đức & Kể chuyện Dữ liệu (Week 12–14) | open | 0 | 3 |
| 6 | Milestone 6: Bảo vệ Đồ án Cuối kỳ (Week 15) | open | 0 | 1 |

Tất cả `due_on = null`. Tổng: **18 issue / 8 đóng / 10 mở**. Người tạo cả 6 milestone: `ViolaPeracia`.
Phân bổ: M1 = #1,#2,#3,#4,#19 · M2 = #5,#6,#7 · M3 = #8,#9,#10 · M4 = #11,#12,#13 · M5 = #14,#15,#16 · M6 = #17.

---

## PHẦN B — ISSUE #1 → #4 (Milestone 1)

### Issue #1 — `chore(setup): khởi tại cấu trúc dự án và môi trường tái lập CRISP-DM`
- **M1** · ViolaPeracia (author + assignee) · labels `type:feature`, `type:testing`
- Mở 25/09 05:18:33 → đóng **26/09 16:41:15** (`completed`) · 1 comment
- **AC 5/5 tick:** (1) cây thư mục `data/{raw,interim,processed}`, `notebooks`, `src`, `figures`, `reports`, `docs`;
  (2) `.gitignore` chặn raw data / `.env` / checkpoint; (3) `requirements.txt` đủ thư viện;
  (4) notebook 00 import toàn bộ thư việc không lỗi; (5) README cho phép clone + chạy ngay.
- **Validation 2/2:** `pip install -r requirements.txt` exit 0 trong venv sạch; notebook 00 chạy qua nbconvert.
- **Deps:** không. Chặn #2, #3, #4.
- **Sai sót còn lại tại thời điểm đó:** ban đầu còn ngoại lệ `!data/raw/metadata.json` trong `.gitignore`
  → review yêu cầu bỏ để bảo đảm raw bất biến tuyệt đối. Sau PR #30 mới hiện ra nghịch lý: metadata.json
  *là* file duy nhất cần git-track (Tầng B), nên ngoại lệ đó thực ra đúng — sẽ được thêm lại ở PR #21.

### Issue #2 — `docs: xác lập câu hỏi nghiên cứu và xây dựng từ điển dữ liệu dự án`
- **M1** · author ViolaPeracia, assignee `doctor-cato` · labels `type:documentation`, `type:research`
- Mở 25/09 05:18:36 → đóng **28/09 16:01:47** · 1 comment (ViolaPeracia xác nhận hoàn thành qua PR #20)
- **AC 4/4 tick:** (1) Main RQ + SQ1–SQ4 khách quan, không giả định kết quả;
  (2) Canonical Schema trung lập nguồn, gồm chất lượng không khí + khí tượng cốt lõi;
  (3) `docs/data_dictionary.md` định nghĩa **8 thuộc tính** cho mọi biến;
  (4) khoá `timestamp` + `station_id` quy chuẩn, tương thích đơn trạm / đa trạm.
- **Validation 1/1:** đối chiếu Canonical Schema với cấu trúc 6 nguồn ứng viên.
- **Deps:** #1. Chặn #3, #19.

### Issue #19 — `feat(data): khảo sát hồ sơ đa nguồn, kiểm chứng phạm vi Hà Nội và quyết định nguồn dữ liệu`
- **M1** · author ViolaPeracia, assignee `Izuki-1780N` · labels `area:data-collection`, `type:data`, `type:research`
- Mở **27/09 08:46** (tạo sau #17) → đóng **29/09 05:14:32** bởi PR #21
- **AC 5/5 tick:** (1) hồ sơ định lượng đầy đủ, **không áp đặt nguồn trước khi profiling**;
  (2) phạm vi Hà Nội có quy tắc lọc cụ thể; (3) mốc thời gian thực tế đo trực tiếp;
  (4) ma trận so sánh + phân định vai trò nguồn (primary/secondary/reference/fallback/unused);
  (5) bảng ánh xạ schema → Canonical Schema hoàn tất.
- **Chuỗi thẩm định bắt buộc:** Candidate Sources → Data Profiling → Hanoi Validation →
  Temporal Coverage Validation → Schema Comparison → Quality Assessment → Source Decision → Canonical Schema.
- **Quyết định tại thời điểm đó:** AQ Primary = OpenAQ S3 `location=2178`; AQ Fallback = AirNow DOS;
  WX Primary = Open-Meteo ERA5; WX Fallback = NOAA ISD 48820; Kaggle = Reference only; PAM Air = Unused.
- **Sai sót nghiêm trọng tại thời điểm đó:** `2178` **không phải Hà Nội** — là Del Norte High School,
  Albuquerque NM. 14.424 dòng dữ liệu Mỹ bị coi là Hà Nội. Bị phát hiện và thu hồi 100% ở PR #24 (29/09 07:29).

### Issue #3 — `feat(data): pipeline thu thập và chuẩn hóa dữ liệu chất lượng không khí Hà Nội`
- **M1** · author ViolaPeracia, assignee `nguyenphanminhkhanh9a-netizen` · labels `area:data-collection`
- Mở 25/09 05:18:38 → đóng **29/09 09:07:54** bởi `doctor-cato` · 1 comment
- **AC 5/5 tick:** (1) Adapter AQ đúng nguồn #19; (2) đúng phạm vi địa lý, định danh trạm bảo toàn;
  (3) raw + metadata + xuất xứ + SHA-256 + giấy phép; (4) ánh xạ Canonical Schema; (5) báo cáo I/O shape/dtypes/mốc thực tế.
- **Validation 1/1:** kiểm tra toàn vẹn tệp thô + xác thực dải thời gian **không dùng giả định cứng**.
- ⚠️ **LATE SCOPE/AC CHANGE** — comment 29/09 12:50 "Cập nhật sau kiểm toán Acceptance Criteria (Milestone 1 audit)",
  commit `942f186`, **không đụng `src/`, `tests/`, `notebooks/`, `data/`**:
  1. **Gỡ tuyên bố không kiểm chứng được**: bỏ *"dữ liệu thô bất biến"* / *"chế độ chỉ đọc"* →
     thay bằng "giữ nguyên trạng + SHA-256" (repo không khoá read-only ở tầng filesystem).
  2. Thêm **Chính sách dữ liệu thô 3 tầng**: A thu thập lúc chạy · B bảo toàn + SHA-256 trong metadata ·
     C Git-tracking tùy chọn, tái tạo độc lập.
  3. Vẽ lại **ranh giới sở hữu** với #4: #3 sở hữu AQ (OpenAQ 4946811 trên AWS S3), #4 sở hữu khí tượng
     (Open-Meteo ERA5 primary, NOAA ISD fallback) và **chỉ tiêu thụ** timeline canonical của #3.

### Issue #4 — `feat(data): pipeline thu thập và đồng bộ dữ liệu khí tượng Hà Nội`
- **M1** · author ViolaPeracia, assignees ViolaPeracia + `lekhuong123456798-cpu`
- Mở 25/09 05:18:40 → đóng **29/09 14:14:36** bởi `doctor-cato` · 1 comment
- **AC tại thời điểm đó: 5 tiêu chí.**
- ⚠️ **LATE AC EXPANSION 5 → 20** — comment 29/09 12:54 "🔍 Kết quả kiểm toán Acceptance Criteria sau Milestone 1",
  commit `942f186` (chỉ sửa `README.md`, `docs/roadmap.md`, `docs/ROADMAP_INFO3020_Air_Pollution.md`):
  - **AC4-1…3** vai trò nguồn · dải thời gian suy động từ `min()/max()` timeline canonical với cờ
    `derived_dynamically_from_air_quality = true` · kiểm chứng temporal overlap bằng số liệu tính toán.
  - **AC4-4…5** không khung lịch sử cứng (start/end thành tham số bắt buộc) · không nội suy / tạo dữ liệu giả.
  - **AC4-6** kiểm tra bbox Hà Nội **trước khi tải**, điểm lưới ERA5 cũng phải trong bbox, thiếu toạ độ → dừng.
  - **AC4-7…9** Chính sách 3 tầng A/B/C.
  - **AC4-10…13** đúng 7 trường weather · đơn vị °C/%/m/s/độ/mm/hPa đối chiếu `hourly_units` ·
    tz-aware `Asia/Ho_Chi_Minh`, tz-naive bị từ chối · timestamp duy nhất & đơn điệu.
  - **AC4-14…20** continuity 1h và báo cáo số khoảng trống · sentinel `-999/-9999` → `NaN` (**không** `fillna(0)`) ·
    giữ `0.0` hợp lệ · giới hạn vật lý theo `docs/data_dictionary.md` §4.3 ·
    đếm số giá trị bị loại theo nguyên nhân · validator chỉ đọc, phân biệt failure/warning/cleaning ·
    ngưỡng tỷ lệ khuyết thiếu tường minh.
  - Đồng thời **bỏ 2 tuyên bố không kiểm chứng**: ~~"raw data must be committed to Git"~~ và
    ~~"dữ liệu thô bất biến / chế độ chỉ đọc"~~ (`.gitignore` **không** bị sửa).
  - Ghi rõ #5/#7 khai báo đầu vào là artifact có sẵn trong `data/interim/` (bỏ trùng lặp).
- **Điều kiện đóng #4:** merge PR #26 rồi tick AC4-1 → AC4-20.

---

## PHẦN C — VÒNG LẬT #22 / #23 / #24: sự cố trạm đo

### PR #22 — `feat(data): build air quality and weather data collection pipeline (#3)`
- Author `nguyenphanminhkhanh9a-netizen` (Khánh) · branch `feat/issue-3-air-quality-pipeline`
- Mở **29/09 07:06:20** → merge **07:06:55** — **35 giây, tự merge bởi chính tác giả**
- `+1438 −8` · 3 files · 1 commit: `src/data_collection.py` (445 dòng), `notebooks/01_data_collection.ipynb` (943), `data/raw/metadata.json`
- **0 comment · 0 review.**
- **Trạng thái tại thời điểm đó:** 14.424 dòng `pm25` gắn `station_id` Hà Nội —
  nhưng thực chất là dữ liệu trạm Del Norte, Albuquerque NM.

### PR #23 — `Revert "feat(data): build air quality and weather data collection pipeline (#3)"`
- Author ViolaPeracia · branch `revert-22-feat/issue-3-air-quality-pipeline`
- Mở **07:08:02** → merge **07:08:18** — **16 giây**
- `-1438 +8` · 3 files · body chỉ ghi `Reverts #22`, **không giải thích**
- 1 review: `copilot-pull-request-reviewer[bot]` — **"quota limit, không review được"**
- Nguyên nhân gốc được làm rõ 65 giây sau ở PR #24.

### PR #24 — `feat(data): xây dựng pipeline thu thập và chuẩn hóa dữ liệu (#3)`
- Author `nguyenphanminhkhanh9a-netizen` · tái sử dụng **cùng branch** `feat/issue-3-air-quality-pipeline`
- Mở **07:15:13** → merge **09:07:53** bởi `doctor-cato` · `+2075 −160` · 6 files · 4 commits

**Vòng review (chi tiết):**

1. **`doctor-cato` 07:21 — 7 điểm chặn:**
   - `validate_geographic_bounds()` **chỉ kiểm tra coordinate đầu tiên** và chỉ trả bool, **chưa filter thật**.
   - `to_canonical()` **gán `station_id` cứng sau khi xử lý raw** → record ngoài Hà Nội bị gắn thành
     station Hà Nội. Raw có record `Del Norte-2178` tại `35.1353, −106.584702`.
   - Phải **filter trước khi tạo canonical**, không được sửa toạ độ raw để ép dữ liệu vào Hà Nội.
   - Thêm assert 100% canonical nằm trong bbox.
   - Cập nhật metadata **sau** bước filter.
   - Temporal coverage đang **hardcode** `2023-01-01 → 2024-12-31` → phải lấy actual coverage từ source.
   - Thiếu test cho: geographic filtering, duplicate `(station_id, timestamp)`, `-999/-9999`, giữ `0.0`.
2. **`ViolaPeracia` 07:29 — commit `a222766` (sự cố lớn nhất của chuỗi PR):**
   - **Thu hồi & loại bỏ 100% OpenAQ 2178** — 14.424 d��ng bị loại khỏi bài toán.
   - Trạm chuẩn quốc gia thực tế: **`location_id = 4946811`** — "556 Nguyễn Văn Cừ", Long Biên,
     `21.0491°N, 105.8831°E`, provider NCEM/VEA (67), 6 thông số (`pm25` sensor 13502150, `pm10` 13502165, no2, co, so2, o3).
   - S3 có **352 file** 2025-07-03 → 2026-07-15, dạng **sub-hourly ~5–10 phút** cần aggregate về 1h.
     **2023–2024 không có trên OpenAQ** (trạm mới tích hợp từ 07/2025).
   - Kiến trúc mới: AQ lịch sử 2023 = AirNow DOS Historical CSV · AQ hiện hành 2025–2026 = OpenAQ 4946811 ·
     WX = Open-Meteo ERA5 cách trạm 556 Nguyễn Văn Cừ **1.7 km**.
   - Canonical codes: `VN001_HANOI_556_NGUYEN_VAN_CU`, `VN002_HANOI_US_EMBASSY`.
   - 2178 đưa vào `disqualified_excluded`, gắn cờ `pending_reexecution_due_to_location_2178_disqualification`.
3. **`nguyenphanminhkhanh9a-netizen` 08:30 — commit `4edb396`** xử lý 100% 9 điểm:
   fail-fast nếu gọi 2178 · nạp **4946811** (352 file, **347.956 dòng thô** → `data/raw/openaq_raw_4946811.parquet`,
   SHA-256 `3c2fbd3c…`) · thêm `AirNowDOSAdapter` · `filter_hanoi_bounds()` + `assert_canonical_within_hanoi()` ·
   `resolve_station_metadata()` · rules `-999/-9999/<0 → NaN`, giữ `0.0` ·
   `validate_canonical_uniqueness()` fail-fast · ghi `actual_min/max_timestamp` ·
   `tests/test_data_collection.py` **7/7 PASS** · notebook nbconvert exit 0.
4. **`doctor-cato` 08:35 — 2 điểm chặn merge còn lại:**
   - **AirNow adapter chưa được ingest**: `run_collection_pipeline()` không gọi `AirNowDOSAdapter`,
     không có raw AirNow input → phải ghi rõ "adapter đã implement nhưng **chưa ingest**" để tránh hiểu nhầm.
   - **Temporal window vẫn hardcode** → phải phân biệt `requested_study_window` với `actual_min/max_timestamp`.
   - Đánh giá phần còn lại (filter từng record, station mapping, invalid-value handling, uniqueness, unit tests): **đã tốt**.
5. **Review `ViolaPeracia` — CHANGES_REQUESTED** 07:22: phần #19 đã bổ sung provenance nhưng còn thiếu
   comparison matrix, quyết định vai trò từng source, temporal coverage thực tế, schema mapping.

### PR #25 — `fix(pipeline): synchronize dynamic meteorological window with air quality timeline`
- Author ViolaPeracia · Mở **09:48:36** → merge **09:53:38** (~5 phút) · `+495 −139` · 6 files
- Sửa **temporal disjointness**: AQ 2025–2026 nhưng WX vẫn 2023–2024.
- `run_collection_pipeline()` suy cửa sổ khí tượng từ `df_air_canonical["timestamp"].min()/max()`
  khi caller không truyền dải ngày.
- `OpenMeteoAdapter.fetch_raw_data()` sinh tên `open_meteo_raw_{start}_{end}.json` → loại cache collision.
- `AirNowDOSAdapter` giữ trạng thái tường minh `implemented / not_executed_pending_raw_input` — **tuyệt đối không mock data**.
- Kiểm chứng: **13/13 test PASS**, inner join = **8.022** dòng (2025-07-03 22:00+07 → 2026-07-15 17:00+07),
  giao thoa **100%**, không Row Explosion.
- **0 comment. Review duy nhất: Copilot bot quota-exceeded → merge không có human review.**

### PR #26 — `feat(weather): complete weather data collection and validation (#4)`
- Author ViolaPeracia (co-author `lekhuong123456798-cpu`) · cùng branch #25
- Mở **10:32:17** → merge **14:14:35** · `+1989 −361` · **20 files** · 6 commits · 3 comment · 5 review

**Review của `doctor-cato` (4 vòng):**
1. 10:40 **CHANGES_REQUESTED**: AC #4 đáp ứng nhưng `validate_weather_canonical()` **chỉ kiểm tra timestamp có timezone**,
   chưa đảm bảo đúng `Asia/Ho_Chi_Minh`. Ngoài ra PR **chưa có CI status** (`statuses: []`) → "20/20 test" mới chỉ local.
2. 13:43 **CHANGES_REQUESTED** (2 điểm): (a) `to_canonical()` **giả định** đơn vị đúng theo request mà không đọc
   `hourly_units` từ raw; (b) timezone check mới ở mức UTC+7 nên **fixed offset `+07:00` vẫn pass**.
3. 14:14 **APPROVED**: đã validate `hourly_units` từ raw, validate đúng **IANA `Asia/Ho_Chi_Minh`** và reject
   fixed offset `+07:00` / `Etc/GMT-7` / `Asia/Singapore`, đã thêm test, CI xanh. *"Không còn blocker kỹ thuật — có thể merge."*
   (APPROVED **3 phút sau** comment cuối của tác giả nói "không merge, chờ reviewer".)

**Comment tác giả 12:51 — commit `89d4c8c` đóng 11 khoảng trống AC #4 (6 code · 3 doc · 1 test · 1 notebook):**
- Bỏ date default hardcode → `start_date`/`end_date` thành tham số bắt buộc (có unit test bảo vệ).
- **Làm cleaning có thể kiểm toán**: trước đây `clean_weather_values` âm thầm đổi giá trị ngoài giới hạn thành `NaN`
  rồi `metadata.json` ghi cứng `"bounds_violation_count": 0` → **số liệu không truy ngược được về dữ liệu**.
  Nay `df.attrs["weather_cleaning"]` báo `disguised_missing` / `out_of_bounds` / `unparseable` theo từng biến.
  *"Không còn giá trị nào bị loại bỏ mà không có dấu vết."*
- Test **20 → 39**.
- Đo thật: 9.072 mốc giờ · 0 trùng lặp · 0 khoảng trống · bước đo `1:00:00` · 0 missing 6 biến ·
  giữ **6.727 giá trị `0.0`** (precipitation) + 10 giá trị `0.0` (wind speed) · SHA-256 khớp ·
  AQ↔WX overlap **8.022 = 100.00%** · ERA5 grid → trạm **1.706 km**.
- CI cố tình **không** chạy notebook 01.

**Comment tác giả 13:20 — commit `eb0614e` đồng bộ 100% documentation** (14 file `.md`, +191/−136,
**không** đụng `src/`, `tests/`, logic notebook, CI, `.gitignore`, raw data):
- Chuyển sang **Three-Tier Raw Data Policy**, thay các tuyên bố không kiểm chứng được.
- Phân định µg/m³ (đo thực tế) vs µg/Nm³ (QCVN 05:2023/BTNMT, ngưỡng 24h = **45 µg/Nm³** từ 01/01/2026),
  **cấm áp ngưỡng 24h lên từng giờ**.
- **chronological split bắt buộc, cấm random split**.
- M1 đạt 4/5 DONE, 1/5 IN PROGRESS.

**Comment tác giả 14:11 — commit `4fea9f3` xử lý 2 điểm review:**
- Thêm `WEATHER_EXPECTED_UNITS` map 6 biến → helper `validate_open_meteo_hourly_units()` đọc `hourly_units`
  **thực tế từ raw response**, raise `ValueError` khi thiếu block / thiếu biến / unit ≠ expected,
  error message nêu rõ biến + actual vs expected. **Không silent convert.**
- `resolve_canonical_timezone_key(tz)` lấy khóa IANA qua `.key` (zoneinfo) / `.zone` (pytz), trả `None` cho fixed offset.
- Test **39 → 57** (+18).
- **Thay đổi hành vi có chủ đích:** 6 fixture "valid" đổi từ `date_range("+07:00")` sang `tz=CANONICAL_TIMEZONE`
  vì pandas biểu diễn `+07:00` thành fixed offset → nay bị reject đúng như reviewer yêu cầu.
- CI run `36580520390` (`headSha=4fea9f3`) **success**.

---

## PHẦN D — MILESTONE 2

### PR #27 — `feat(cleaning): build 6-dimension data quality audit and missingness taxonomy`
- Author `nguyenphanminhkhanh9a-netizen` · branch `feat/issue-5-data-quality-audit`
- Mở **29/09 14:31** → merge **16:00:55** · `+2403` · 4 files · 3 commits
- **Files:** `src/data_quality.py` (750), `tests/test_data_quality.py` (273),
  `notebooks/02_quality_audit.ipynb` (1186), `docs/data_quality_audit.md` (194)
- **Nội dung:** khung kiểm toán 6 chiều **read-only**; phân biệt `NaN` thật với disguised-missing strings
  (`"N/A"`, `"null"`, `"None"` = 0); định lượng chuỗi 0 kéo dài; Rubin MCAR/MAR/MNAR ở mức **giả thuyết chẩn đoán**
  (35 khối rơi telemetry 1 giờ); khai báo bất định vì 2 chuỗi không chồng lấn trên `data/interim/`.

**3 vòng `CHANGES_REQUESTED` của `doctor-cato`:**
1. `audit_prolonged_zeros()` đếm **số dòng liên tiếp** như số giờ liên tiếp → phải tính duration thật từ `timestamp`,
   và **theo từng `station_id`**.
2. Sai mẫu số: `groupby(...).agg(total="count")` không đếm NaN → `missing_pct` là missing/observed,
   không phải missing/total → dùng `size`.
3. AC #5 yêu cầu missingness theo trạm và theo nguồn; hàm tái sử dụng mới chỉ phủ diurnal/missing-blocks/co-missingness.
4. Audit PM2.5 ≤ PM10 dùng rule `pm25 > pm10 + 2.0`; AC yêu cầu `PM2.5 <= PM10` → phải ghi rõ epsilon là giả định có chủ đích.
5. MCAR/MAR/MNAR phải giữ ở mức giả thuyết.
6. Vòng 2 (commit `e03bc21`): 1–3 vẫn chưa sửa.
7. Vòng 3 (commit `ad74880`): §4 Accuracy vẫn khẳng định nguyên nhân → đổi thành *"Mẫu hình có thể liên quan đến sai số đo
   giữa các cảm biến quang học và ảnh hưởng của độ ẩm; nguyên nhân chưa được xác minh trực tiếp từ log thiết bị"*.

**Sai sót còn lại tại thời điểm đó (phát hiện ở PR #30):** báo cáo #5 ghi **nhiều số liệu không khớp** dữ liệu canonical trên đĩa —
weather 17.544→**9.072** dòng, air 7.999→**8.022**, temp max 40.2→**38.6 °C**, RH>90% 3.745 (21.35%)→**2.843 (31.34%)**,
max sampling gap 15h→**626h**, zero-precip 13.178 (75.11%)→**6.727 (74.15%)**;
và **một tiền đề sai**: báo cáo nói AQ và WX không giao thoa, trong khi inner join cho **8.022 dòng = 100.00%**.

### Issue #5 — `feat(cleaning): bộ kiểm toán chất lượng 6 chiều và phân loại cơ chế khuyết thiếu`
- **M2** · ViolaPeracia / assignee `nguyenphanminhkhanh9a-netizen` · **0 comment**
- Mở 25/09 05:18:43 → đóng **29/09 16:32:43**
- **AC 6 tiêu chí + 1 validation — TẤT CẢ VẪN `- [ ]` trong body dù issue đã đóng** (7 ô chưa tick)
- ⚠️ Đây là **sai lệch quy trình đầu tiên**: #1,#2,#3,#4,#7,#19 tick AC trước khi đóng, #5 thì không.

### PR #28 — `chore: complete M1 post-audit cleanup`
- Author ViolaPeracia · branch `chore/m1-cleanup` · Mở 15:15 → merge **15:42** · `+462 −19` · 5 files
- (1) doc sync M1 `5/5 DONE`, test 39 → **71**; (2) `run_collection_pipeline()` ghi `last_updated_utc` vào
  `data/raw/metadata.json` làm **bẩn provenance được track** → tách sang `pipeline_execution_runtime.json`;
  (3) **14 test offline trực tiếp** cho `OpenAQAdapter.to_canonical()`; (4) metadata temporal semantics.
- **Review `doctor-cato` — APPROVED.** Nhưng merge xong **18 phút sau** bị revert.
- **Sai lỗi tại thời điểm đó:** README ghi 71 test thuộc `test_data_collection.py` (thực chất file đó có 57; 71 là tổng trước revert).

### PR #29 — `Revert "chore: complete M1 post-audit cleanup"`
- Author ViolaPeracia · branch `revert-28-chore/m1-cleanup` · Mở 15:55 → **CLOSED 16:10, không merge**
- `doctor-cato` commit thẳng revert lên `main` (`962457c`), đóng PR, khóa conversation, xoá branch.
- **Hậu quả kéo dài (phát hiện ở PR #30):** `write_pipeline_runtime_log()` biến mất khỏi `src/data_collection.py`
  → `scripts/fetch_dataset.py --skip-fetch` thành **dead code trên mọi fresh clone** (đọc file không bao giờ được sinh ra).
  14 test adapter và fix metadata-determinism cũng mất luôn.

### PR #30 — `docs: correct M1 audit figures against real data and document dataset acquisition`
- Author ViolaPeracia · Mở 16:30 → merge **16:48:15** · `+583 −63` · 8 files
- **Files:** `scripts/fetch_dataset.py` (246, mới), `tests/test_fetch_dataset.py` (218, mới),
  README, AGENTS.md, `docs/roadmap.md`, `docs/data_quality_audit.md`, `docs/source_profiling_decision.md`, `.github/workflows/ci.yml`
- **Nội dung chính:** tính lại toàn bộ số liệu audit #5 bằng chính `src/data_quality.py` của repo →
  9 số sai như nêu trên. Thêm cơ chế tái tạo dataset **một lệnh, không API key**.
- **Giới hạn tái lập được ghi trung thực:** tải lại cho cùng 349.463 raw / 8.022 / 9.072 canonical và 100% overlap,
  nhưng **SHA-256 khác** (`4168735570…` vs `661578c38…`) vì Parquet không byte-reproducible →
  SHA-256 kiểm tra tính toàn vẹn tệp đã lưu, **không** chứng minh tái dựng được dataset.
- **Review `doctor-cato` — CHANGES_REQUESTED:** `compare_with_metadata()` có thể trả `False` trong khi `main()`
  lại `return 0 if matched else 0` → script có thể in `[KHAC]` mà vẫn exit 0. Vì OpenAQ S3 là repo sống
  (số bản ghi trôi), phải thống nhất semantics.
- **Tự audit của tác giả (commit `c6ad93c`) — 6 lỗi tự tìm:**
  1. 🔴 `--skip-fetch` là **dead code** (hậu quả của revert #28).
  2. 🟠 README ghi sai 71 test thuộc `test_data_collection.py`.
  3. 🟠 CI chưa thấy `scripts/` → `compileall -q src tests scripts` + `import src.data_quality`.
  4. 🟠 Không có test cho script mới → `tests/test_fetch_dataset.py` 9 test offline (patch `urlopen` để chứng minh không có network).
     Test **71 → 80**.
  5. 🔵 `docs/data_quality_audit.md` §5.2 missing-rate ceiling là 1.51%, đo thật **1.80%** (giờ 10:00).
  6. 🔵 `docs/roadmap.md` §3.2 Tầng C phải nêu `scripts/fetch_dataset.py` là cơ chế tái tạo thật.
- Tác giả cũng ghi lại 2 lỗi của chính mình: **đoán số thay vì đo** ("28 unit tests" thực tế 14;
  "7.819" giá trị unique thực tế 7.666) và 1 fixture sai (`max_timestamp` 2026-07-15 với 3 dòng sinh ra →
  max thật 2025-07-04) → sửa fixture, không sửa script.

### PR #31 — `Feat/issue 7 preprocessing pipeline`
- Author `doctor-cato` (chính owner) · branch `feat/issue-7-preprocessing-pipeline`
- Mở **17:54:31** → đóng **17:55** — **33 giây, không merge** · `+1607 −5` · 5 files
- **Nội dung:** `docs/research_questions.md` + `docs/data_dictionary.md` (tái tạo) + `src/cleaning_pipeline.py`
  (698 dòng, **không test**) + `notebooks/03_transformation_pipeline.ipynb`.
- **4 lỗi thừa kế lại PR #32 đã phải sửa:** notebook JSON hỏng · dead import `from data_quality import`
  (thiếu prefix `src.`) → `run_preprocessing_audit()` **luôn raise ImportError**, tức là docstring tính năng chưa từng chạy ·
  `validate_no_leakage()` **rỗng** (pipeline fit trên Test vẫn in "✓ No leakage") · 698 dòng không test.

### Issue #6 — `feat(cleaning): làm sạch logic vật lý, lỗi cảm biến và reindex chuỗi thời gian`
- **M2** · assignees ViolaPeracia + `Izuki-1780N` · Mở 25/09 05:18:45 → đóng **30/09 04:19:57** · **2 comment**
- **AC 7 tiêu chí + 3 validation — TẤT CẢ VẪN `- [ ]` trong body dù issue đã đóng** (10 ô chưa tick)
- **Comment 1 (29/09 19:08) — báo cáo hoàn thành:**
  (1) `timezone_is_canonical` PASS, duplicates=0 · (2) **8.022 → 9.044 dòng**, **1.022 giờ trống** giữ nguyên `NaN` ·
  (3) `pm_subset_constraint` **0** vi phạm trên **7.372** cặp quan sát · (4) `pm25_was_missing` **1.289** hàng ·
  `is_high_humidity_fog` **2.834** hàng · `pm25_was_stuck` **0** hàng · (5) `assert_no_imputation()` so **từng ô** ·
  (6) đỉnh PM2.5 **252.6436 → 198.9467 µg/m³**, giảm vì chính bản ghi có PM10 = 174.7982 (vượt 77.8455)
  → vi phạm khí động học, **không phải** quy tắc cắt cực trị · (7) `docs/cleaning_log.md` 573 dòng, tái lập byte-for-byte.
- **Điểm thiết kế thừa nhận:** xử lý **324** bản ghi nghịch đảo thay vì **282** của #5
  (ε = 2,0 µg/m³ là *mốc phân loại bằng chứng, không phải ngưỡng hành động*); vi phạm → chuyển **cả hai** cột thành `NaN`.
- **Thừa nhận lệch phạm vi:** mục "Lọc phạm vi địa lý" trong Scope không có trong AC/Validation vì đã làm ở tầng thu thập.
- **Sai sót còn lại tại thời điểm đó:** AC body chưa tick; claim trong cleaning log sai 1 quan sát (`>= 6` của #5 vs `> 6` ở đây).

### Issue #7 — `feat(preprocessing): tích hợp ô nhiễm - thời tiết và đóng gói pipeline chống rò rỉ`
- **M2** · assignee `doctor-cato` · Mở 25/09 05:18:48 → đóng **30/09 04:23:19** · **0 comment**
- **AC gốc 6 tiêu chí + 2 validation** (Row Explosion · đóng băng · điểm cắt tuyến tính · pipeline fit trên Train ·
  log1p · parquet · read-back · `train.max() < test.min()`).
- ⚠️ **LATE BODY EDIT 30/09 — section "Trạng thái nghiệm thu", `AC VERIFIED: 9/9`**
  (thêm 3 AC: all-NaN guard, timestamp trong leakage validator, target không được làm feature):

  | AC | Bằng chứng ghi trong body |
  |---|---|
  | AC1 row explosion | merged 9.044 = air 9.044 (giữ cả `<=` theo AC và `==`) |
  | AC2 freeze | 9.044 dòng, 2025-07-03 22:00 → 2026-07-15 17:00 (+07:00) |
  | AC3 điểm cắt | **2026-01-15**, Train 4.682 (51,8%) / Test 4.362 (48,2%) |
  | AC4 pipeline | 13 features; `validate_no_leakage()` PASS |
  | AC5 log1p | n=4.279, âm=0; skew 1,148 → −0,656; kurtosis 1,068 → 0,726 |
  | AC6 parquet | 9.044 × 18, đọc lại khớp schema + dtype 100% |
  | V1/V2 | `train.max()` 2026-01-14 23:00 < `test.min()` 2026-01-15 00:00, chồng lấn 0 dòng |

- **Quyết định 1:** giữ mốc cắt **2026-01-15**, **không** đổi sang 2026-01-01 — lý do *tính đại diện theo mùa*
  (mốc này cắt giữa mùa đông nên cả Train lẫn Test đều chứa mùa đông; tập chỉ có **đúng một chu kỳ mùa** 07/2025–07/2026).
  Nêu rõ 2026-01-01 có event coverage cao hơn (**181 vs 99**) và `p90_test/train` gần 1 hơn (0,97 vs 0,80)
  nhưng **không** dùng để tuyên bố là tối ưu.
- **Cảnh báo `[!IMPORTANT]` tự thừa nhận:** triển khai **CHƯA merge** (nằm trên PR #32); **AC bị tick sớm do yêu cầu rõ ràng.**
- ⚠️ **Số còn sai trong body #7 (PR #34 đã sửa ở #13 nhưng quên sửa lại #7):**
  tỷ lệ nhãn nặng Test **2,27%** / Train **6,30%** → dịch chuyển ~**2,8×** (chia nhầm mẫu số 4.362 dòng Test).
  Đúng phải là **99/3.216 = 3,08%** vs **295/4.279 = 6,89%** → **~2,24×** (chia trên tập có nhãn).

### PR #32 — `feat(cleaning): làm sạch tất định + pipeline biến đổi không rò rỉ (#6, #7)`
- Author ViolaPeracia · Mở **29/09 19:13** → merge **30/09 04:19:56** · **`+9921 −43` · 16 files · 8 commits**
- **Files:** `src/cleaning.py` (2067), `src/cleaning_pipeline.py` (1104),
  `tests/test_cleaning.py` (1247), `tests/test_cleaning_pipeline.py` (529), `tests/test_cleaning_pipeline_guards.py` (513),
  `notebooks/03_data_cleaning.ipynb` (1351), `notebooks/03_transformation_pipeline.ipynb` (2233),
  `docs/cleaning_log.md` (575, mới), `.agents/rules/data.md` §3.5 viết lại, `.github/workflows/ci.yml`, metadata, docs

**Ghi chú quan trọng về git:** PR này bị **commit, reset và viết lại message 4 lần**. Reflog cho thấy 5 commit
được replay 3 lần, 3 commit thử nghiệm bị reset, 1 lượt `filter-branch --msg-filter` làm mất dấu tiếng Việt,
rồi 5 lần `commit --amend` khôi phục dấu. Có branch backup `backup/pr32-before-msg-rewrite`.

**Lý do ship #6 + #7 chung PR (ghi ở PR #34):** `clean_air_quality()` phụ thuộc khí tượng **đã** làm sạch
→ #6 không tách được khỏi #7.

**Vòng review đối kháng #6 — 3 BLOCKER + 8 MAJOR + 8 MINOR/NIT, 18/20 test hồi quy FAIL trên bản gốc:**
- 🔴 `assert_no_imputation()` **tautology** (so một frame với chính nó).
- 🔴 `_snapshot()` gọi `float(df["pm25"].max())` **trước** `normalize_disguised_missing()` → cột string rác
  giết cả pipeline → disguised-missing **không dùng được qua main path**. Nay `errors="coerce"`.
- 🔴 `run_deterministic_cleaning()` chỉ **log** validation, không **enforce** → nay raise `AssertionError`
  và **không ghi artifact nào** vào `data/interim/` nếu AC fail.
- 🟠 `validate_cleaned_dataset()` AND điều kiện monotonicity **toàn cục** với số vi phạm
  → lưới đa trạm hoàn hảo bị báo FAIL.
- 🟠 **Sai thứ tự gọi**: `clean_air_quality()` chạy trước `clean_weather()` → phần humidity join **khí tượng raw**;
  error message còn bảo "chạy Issue #6 trước" trong khi đang ở Issue #6. Đảo thứ tự.
- 🟠 `reindex_hourly_grid()` **âm thầm xoá quan sát** khi cửa sổ hẹp hơn phạm vi quan sát (`rows_inserted` âm)
  → nay `ValueError` kèm số lượng.
- 🟠 Shared window đệm mọi trạm về phạm vi toàn tập → trạm sống ngắn nhận hàng nghìn NaN (repro 4 → 2.836)
  → thêm `max_pad_hours` (mặc định 31 ngày).
- 🟠 `groupby` **âm thầm bỏ NaN key** → quan sát thiếu `station_id` bị thay bằng hàng đệm mang ID trạm khác
  → **dữ liệu bịa**. Nay `ValueError`.
- 🟠 `reindex_station_series()` ghi đè attribute cấp trạm lên **mọi** dòng kể cả dòng NaN thật.
- 🔵 `drop_duplicate_observations()` docstring sai; cleaning log claim sai lệch 1 quan sát với #5.
- Nhóm NIT: `nullified_runs` đếm sau mask; `pm25_was_stuck` tách khỏi `pm25_was_missing`;
  `epsilon` → `reporting_epsilon_ug_m3`; `unparseable` luôn 0; tiêu chí bị skip hiển thị `**PASS**` thay vì `**N/A**`;
  `pd.Timedelta(hours=1)` DeprecationWarning → `np.timedelta64(1,'h')`; blind `KeyError` → `ValueError`.
- Commit `1c758a6`: `sort_chronologically()` báo `rows_reordered = 1` trên input đã sort
  (`Series.equals` bỏ qua index); `normalize_timestamps()` throw blind `AttributeError` trên mixed UTC offset
  → detect, fold về UTC rồi mới sang `Asia/Ho_Chi_Minh`, báo `rows_mixed_offsets_utc_first`.

**Vòng review #7 — 4 MAJOR (`doctor-cato`, commit `2a2207b`):**
(a) `from data_quality import` thiếu prefix `src.` · (b) `NUMERIC_FEATURES` **chứa target `pm25`** ·
(c) `validate_no_leakage()` chỉ làm `hasattr` check, chưa so số · (d) thêm `tests/test_cleaning_pipeline.py` 240 dòng.

**Vòng review #7 ròng 2 (5 reviewer độc lập) — 7 BLOCKER + phần lớn MAJOR, commit `8e1426a`, 34 test hồi quy RED-first:**
1. `validate_no_leakage()` **không đọc `timestamp`** → `train_test_split` ngẫu nhiên vẫn in "No leakage".
2. Chỉ so `imputer.statistics_`, bỏ qua `scaler.center_`/`scale_` dù docstring nói rõ → thay bằng RobustScaler
   fit trên Test vẫn pass 100%.
3. Guard hard-code tên transformer `"num"` → nhánh thứ hai fit trên Test bị bỏ qua → `_learned_arrays()` duyệt cây `named_steps`.
4. `X_train`/`X_test` truyền **positional** → đảo chỗ là vô hiệu mọi guard → keyword-only.
5. Target trong `NUMERIC_FEATURES` → `ValueError`.
6. `merge_air_weather()` thiếu **all-NaN guard** theo `.agents/rules/data.md` §3.6 → lệch khoá 1 ngày cho
   0/10 khớp, 6 cột khí tượng toàn NaN, `SimpleImputer` điền median và **mô hình "chạy mượt" trên 6 hằng bịa**.
7. 🔴 `pm25_was_missing = pm25.isna()` + `SimpleImputer` điền median → **rò rỉ target theo cấu trúc**,
   đo trên dữ liệu thật: **256/256 Train, 1033/1033 Test** dòng có `target == median` sau khi điền.
   `validate_no_leakage()` **không thể bắt** về mặt cấu trúc → flag chuyển sang `TARGET_DERIVED_FLAGS`.
- Bổ sung: từ chối certify khi Train-refit và Test-fit cho tham số giống hệt · bỏ qua `remainder` của sklearn ·
   merge chặn va chạm tên cột · `chronological_split()` **loại** NaT / không đơn điệu thay vì sửa âm thầm ·
   `add_cyclical_time_features()` chặn NaT · `export_to_parquet()` ghi atomic (temp + `os.replace`) ·
   `freeze_dataset()` đặt `station_count = None` khi không có cột trạm (0 là tuyên bố sai sự thật) ·
   `evaluate_log1p_transform()` chặn target âm.
- **Xoá test yếu:** tautological `assert_no_imputation(self.cleaned, self.cleaned, …)` · test chống lại chính hàm ·
   `station_count == 1` · `TARGET_CANDIDATE` tự tham chiếu · temp dir không `mkdtemp`.
- **Notebook:** bỏ tên trạm bịa "Tư Liên" (thật là `VN001_HANOI_556_NGUYEN_VAN_CU`) ·
   thay demo rò rỉ tự do bằng demo rò rỉ `pm25_was_missing` thật.

**Điểm dữ liệu quan trọng của #7:** chuyển notebook từ fixture tổng hợp `np.random.lognormal`
sang **dữ liệu thật** `data/interim/*.parquet` (9.044 quan sát giờ, 2025-07-03 → 2026-07-15),
ghi `data/processed/air_pollution_final.parquet`; thứ tự merge → freeze → split → fit.
`log1p` **chỉ chẩn đoán**, không transform target.

**Commit tài liệu `252c0ef`:** audit toàn bộ 7 AC của #6 và 6 AC + 2 validation của #7 (**18/18 PASS**),
ghi **bản ghi chính thức 3 quyết định** vào `docs/roadmap.md` (Week 05).
**Commit `01a6e95`/`0718be0`:** trả lời 2 câu hỏi mở — giữ `2026-01-15` với lý do *đại diện theo mùa*
(**không** phải tối ưu tuyệt đối, vì `2026-01-01` thắng ở cả hai tiêu chí đã nêu) · giữ cả hai phép `<=` và `==`.

---

## PHẦN E — HAI VÒNG AUDIT SAU MILESTONE 2

### PR #33 — `Feat/m2 processed data preview`
- Author `doctor-cato` · branch `feat/m2-processed-data-preview` · **không body, không review chính thức**
- **Nhưng `ViolaPeracia` đăng comment blocking dài, verdict "DO NOT MERGE as-is":**
  - 🔴 **BLOCKER 1 — base cũ hơn #32, merge sẽ xoá 9.017 dòng.** `mergeable: CONFLICTING / DIRTY`.
    Hai diff nói hai sự thật: `git diff origin/main...pr-33` = 4 files +1929 (nhìn hấp dẫn),
    `git diff origin/main pr-33` = 17 files **−9017 +1068** (điều thực sự sẽ land).
    Sẽ xoá `src/cleaning.py` (−2067), `notebooks/03_data_cleaning.ipynb` (−1351), `tests/test_cleaning.py` (−1247),
    `docs/cleaning_log.md` (−575), `tests/test_cleaning_pipeline_guards.py` (−513), job `notebook-smoke` trong ci.yml (−33);
    và **regress** `cleaning_pipeline.py` 1104→723, `test_cleaning_pipeline.py` 529→240,
    `03_transformation_pipeline.ipynb` 2233→383 — tức khôi phục bản trước `8e1426a`.
    Chỉ **1 file** thật sự là mới.
  - 🔴 **BLOCKER 2 — CI không hề chạy.** `gh pr checks 33` → 0 check-run trên SHA `77e6c83`, trong khi #32 có 7 run thành công.
  - 🟠 **MAJOR 3 — `validate_no_leakage` raise `IndexError`** với feature set notebook truyền vào:
    `imputer.statistics_` dài 7 (`NUMERIC_FEATURES`) nhưng notebook truyền 11 cột → cell "Validate không có leakage"
    **không bao giờ chạy được**. Test hiện tại che lỗi vì dựng frame 1 cột.
  - 🟠 **MAJOR 4 — false negative:** hàm nhận `X_test` nhưng không đọc; pipeline cố tình fit trên Test vẫn pass
    nếu median Train trùng median Test.
  - 🟠 **MAJOR 5 — `merge_air_weather` âm thầm mất toàn bộ khí tượng:** `how="left"` chỉ có check `len(merged) > len(df_air)`;
    lệch khoá → 0 khớp, 0 ô khí tượng khác null, **không lỗi**. Cộng thêm `SimpleImputer` mặc định
    `keep_empty_features=False` → cột toàn NaN bị âm thầm bỏ.
  - 🟡 MINOR: bare `assert` bị `python -O` gỡ (quy tắc dự án là fail loudly) · §7 đọc `data/raw/metadata.json`
    (tầng raw bất biến) để mô tả quyết định split của tầng processed, và `if 'split_timestamp' in str(metadata)`
    **luôn False**; câu "sẽ xác định sau khi #5/#6 hoàn thành" đã lỗi thời · đoán tên cột thay vì assert ·
    re-implement ngưỡng cleaning dưới dạng literal → sẽ trôi khỏi module thật.
- **Fix của tác giả (force-push `77e6c83 → 8681dee`):** rebase lên `origin/main`, `git rm` 3 file cũ,
  chỉ giữ `notebooks/03_processed_data_preview.ipynb` → 1 file, +709, 2/2 CI job success, 21/21 code cell clean.
  MAJOR 3–5 tự biến mất vì main đã có fix.
- **3 bug thật phát hiện khi *thực sự chạy* notebook:**
  (1) rule PM2.5⊆PM10 sai — strict `pm25 > pm10` trên dữ liệu đã làm sạch sẽ báo động giả,
      vì `src/cleaning.py` áp `+ε = 2.0 µg/m³` (độ bất định đo BAM-1020) → nay báo cả hai số;
  (2) `ax.text(n, col, …)` với `kind="barh"` → `ConversionError`;
  (3) 2 DeprecationWarning (`pd.Timedelta(hours=1)`, `ts.dt.to_period("M")` mất tz).
- **4 commit bổ sung của `doctor-cato` trước khi merge:** thêm `reports/report.md` +
  `scripts/generate_report_figures.py` → rồi **gỡ cả hai** vì out-of-scope (stale status; split 70% hard-code);
  thêm composite key duplicate check; thêm fail-fast schema validation.

### PR #34 — `fix(m2): sửa 1 bug thật + 2 sai số báo cáo HIGH của audit Milestone 2`
- Author ViolaPeracia · branch `fix/m2-audit-findings` · Mở 30/09 07:07 → merge **10:42:39** · `+1505 −113` · 14 files
- **Kết luận kiểm toán:** cả 3 issue đều đạt AC khi chạy thật — **không tìm ra bug nào ở mốc cắt `2026-01-15`**,
  giữ nguyên. Nhưng tìm ra 2 lỗi báo cáo HIGH, 1 bug thật MEDIUM, và nhiều chỗ rule-vs-code lệch nhau.

**Bug thật:**
1. `audit_six_dimensions()` **crash `TypeError`** khi so `valid_both["pm25"] > valid_both["pm10"]` trên cột kiểu string
   — ** auditor chết đúng trên lỗi được thuê đi tìm.** Nay chỉ chạy trên cột numeric, trả `None` thay vì `0`
   ("không đo được" ≠ "không có nghịch đảo", và `0` là tuyên bố sai sự thật).
2. `validate_no_leakage()` **âm thầm tắt lớp chống random-split** khi không truyền timestamps — đo trên dữ liệu thật
   cho thấy random `train_test_split` **không bị bắt** (lớp 2–3 chỉ so tham số học, mà random split vẫn học
   "đúng" trên Train của chính nó). Lớp 1 là lớp duy nhất chống random split.
3. 3 DeprecationWarning trên đường thành lỗi ở pandas tương lai; nay suppress hẹp cho mixed-timezone call,
   và suite chạy dưới `-W error::DeprecationWarning -W error::FutureWarning`.

**Lỗi báo cáo HIGH:**
- **H-1 — đuôi rỗng Test bị báo cáo thiếu.** Trong 4.362 dòng Test chỉ 3.216 có nhãn `pm25`,
  **1.146 (26,3%) mất nhãn**, tập trung 2026-06 (79,03% NaN) và 2026-07 (99,72% NaN). Trước đó chỉ nhắc 2026-07
  nên người đọc tưởng mất 15 ngày — thực ra **6 tuần**. Nguyên nhân là nguồn ngừng phát, không phải lỗi làm sạch
  (`reindex_hourly_grid()` đã chèn đủ lưới giờ).
- **H-2 — dịch chuyển tỷ lệ class dùng sai mẫu số.** Con số 2,8× đúng về phép tính (6,30%/2,27% = 2,77)
  nhưng chia nhầm mẫu số 1.146 dòng mất nhãn. Đúng là **2,24×** (Train 295/4.279 = 6,89% vs Test 99/3.216 = 3,08%).

**Rule-vs-code lệch (M-2…M-6):**
- M-2 `.agents/rules/data.md` §4 nói PM2.5 ≤ PM10 **+2.0** còn code áp **strict** → ε hạ xuống tầng báo cáo.
- M-3 §5 vẫn cho phép MCAR "nội suy an toàn ≤2h" và MAR "điền median theo tầng khí tượng",
  **mâu thuẫn trực tiếp** với bất biến §3.5 → rút lại và ghi rõ mâu thuẫn.
- M-4 README "mutation score 21/21 = 100%" là **đếm tay** (không `mutmut`/`cosic-ray`, không config, không CI step, không artifact).
- M-5 README số cũ `8.022` → 9.044 kèm giải thích 1.022 giờ chèn.
- M-6 README + body Issue #7 nói "chưa merge" sau khi #32 đã merge; và tài liệu hoá việc #6+#7 ship **một** PR.
- `docs/data_quality_audit.md` thêm bảng trạng thái **trước #6 vs sau #6** (8.022×5 → 9.044×8; pm25 NaN 203→1.549;
  pm10 NaN 123→1.469; đỉnh PM2.5 252.6436→198.9467; đỉnh PM10 339,99 không đổi).

**Mutation audit trên bản sao:** 41/137 mutant sống sót; đóng 38 lỗ hổng.
**Test không kiểm chứng được điều tên nói:**
- `test_dedup_keeps_first_deterministically` dùng hai timestamp **khác nhau** → 0 khoá trùng, pass ngay cả khi `keep="last"`.
- `test_temporal_gap_breaks_the_stuck_run` dùng 4 quan sát dưới ngưỡng → xoá cả nhánh temporal-gap vẫn xanh.
- 3 test cyclical **bất biến với ước số** (đổi `24` → `12` vẫn xanh, nghĩa là chu kỳ 24h/12 tháng **chưa từng được kiểm chứng**).
- `test_the_leak_is_actually_deterministic` **không gọi code dự án nào**.
- 3 assert read-back dùng chung 1 fixture hỏng cả về số dòng lẫn tên cột → xoá cái này cái kia bắt.

**Review vòng 1 của `doctor-cato` — CHANGES_REQUESTED, 2 điểm:**
- (a) `temporal_grid_completeness` **sai với dữ liệu đa trạm**: `expected_grid` tính từ `min_ts → max_ts` của **cả DataFrame**
  nhưng so với `total_rows` của **mọi** trạm → `unrecorded_hours` và phần trăm sai, thậm chí **âm**.
- (b) `validate_no_leakage()` vẫn cho phép bỏ qua kiểm tra thời gian bằng cách không truyền `timestamps`.
- **Đo lại của tác giả (tệ hơn mô tả):** 2 trạm × 8 giờ đủ → bản gốc báo **−8 giờ / −100%**, đúng là **0 / 0%**;
  trạm B mất 3 giờ → gốc **−5 / −62,5%**, đúng **3 / 18,75%**; cửa sổ rời nhau → gốc "2 giờ mất", đúng **20 giờ thiếu phủ**.
  Đây không phải "có thể âm" mà là **che khoảng trống thật bằng dấu hiệu tích cực**.
- **Fix:** dùng **cửa sổ triển khai dùng chung** (min→max toàn frame) × số trạm; khối `per_station` báo
  `internal_gap_hours` và `missing_vs_shared_window_hours` riêng để không mất thông tin.
  Hồi quy 1 trạm: lưới đủ 9.044 h → `9044 / gap 0` **giống hệt** bản cũ; khoảng trống chung 1.022 h → `9044 / gap 1022` **giống hệt**;
  khoá trùng → cũ **`-10` (phi lý)** vs mới **`0`**.

**Commit `b8b5009` — 2 phát hiện mới do đo đạc:**
- **Loại `is_high_humidity_fog` khỏi features.** Lý do ghi trong code ("sương mù quang học → cảm biến đọc sai →
  hợp lệ là dự đoán được") **không đứng vững**: `corr(pm25, RH)` = **−0.0365**; PM2.5 TB có cờ **41,65** vs không cờ **44,75**
  (cao hơn); quét RH > 80/85/90/95 đều cho kết luận như nhau. Chẩn đoán đúng: cờ **chọn đúng nhóm ẩm cao**
  (RH TB 94,99% vs 74,06%) nhưng **RH đơn lẻ không liên quan PM2.5** → đây là *cờ độ ẩm*, không phải *chỉ báo sương mù quang học*.
  Tạo nhóm `NON_PREDICTIVE_FLAGS`, **cố ý tách khỏi** `TARGET_DERIVED_FLAGS` vì hai lý do loại khác nhau và gộp sẽ giấu lý do thật.
  Features mặc định **13 → 12**.
- **Dropout là MỘT sự cố liên tục 630 giờ**, không rơi rải rác: `2026-06-19 11:00 → 2026-07-15 16:00` (TEST),
  cộng 52h/37h/24h trong Train. **630/630 dòng có `pm25_was_missing = 1`** và `pm10` cũng `NaN` đủ 630 giờ
  → **mất cả hai kênh** = trạm ngừng phát. Độ phủ nhãn: Train 4.279/4.682 = **91,4%**, Test 3.216/4.362 = **73,7%**
  → Test mất **17,7 điểm phần trăm**, tất cả trong **một** sự cố. Vì 630 giờ liên tục nghĩa là **4 tuần cuối không có quan sát nào**
  → mọi so sánh với kỳ đó là ngoại suy ngoài tầm quan sát. Test 307 → 310.

**Review vòng 2 — CHANGES_REQUESTED, 1 điểm còn lại:**
tương quan gần 0 và so sánh trung bình **không đủ mạnh** để khẳng định tuyệt đối "không dự báo được",
vì còn có thể quan hệ phi tuyến hoặc tương tác → đổi thành "chưa có bằng chứng về giá trị dự báo marginal".
- **Tác giả đi xa hơn — commit `dc446bf` tìm ra tương tác đảo chiều theo mùa:**
  PM2.5 khác biệt cờ vs không cờ theo mùa (n = 7.495):
  Đông **+2,79 µg/m³** (95% CI [−0,42, +6,01], p = 0,024) · Xuân **−8,91** ([−10,44, −7,38]) ·
  Hè +0,28 (không) · Thu **−2,72** ([−4,93, −0,51]).
  Hồi quy `pm25 ~ fog + season + fog:season`: `C(fog)[T.1]:C(season)[T.Xuan]` = **−11,70** (p < 0,001),
  `[T.Thu]` = −5,52 (p = 0,002), `[T.He]` = −2,51 (p = 0,169); **F đồng thời = 16,78, p = 7,4·10⁻¹¹**;
  khác biệt kép Đông vs Xuân+Hè **+7,77 µg/m³**.
  → **`corr(pm25, RH) ≈ 0` là hệ quả của trung bình qua các mùa nơi tác dụng ngược nhau triệt tiêu**,
  đúng là kết luận sai mà một hệ số tương quan đơn lẻ mời gọi. MI bổ sung = **0,0024** (thấp nhất trong các biến khí tượng).
  Feature mặc định **12 → 11**; flag vẫn giữ trong dataset. Test regression-guard
  `test_the_flag_group_documents_the_seasonal_interaction` **bắt buộc** khối giải thích phải chứa
  `marginal`, `F = 16,78`, `tương tác`. Test 310 → 311.
- **APPROVED** → merge. Tất cả phát hiện ghi vào **Issue #8** (bài học phương pháp: không kết luận "không tương quan"
  từ hệ số tương quan; kiểm tra tương tác cho **mọi** cờ chẩn đoán; `pm25_was_stuck` là hằng số 0;
  nhắc đa cộng tuyến `pm25`/`pm10` R² = 0,9462 cần VIF).

### PR #35 — `docs: đồng bộ toàn bộ tài liệu theo trạng thái thực tế sau PR #34`
- Author ViolaPeracia · branch `docs/sync-m2-state` · **OPEN, chưa merge** · `+222 −94` · 17 files · 2 commits
- 4 việc: (1) test count 259 → **311** kèm bảng per-file; (2) **xoá claim "mutation 21/21 = 100%"** khỏi roadmap;
  (3) sửa trạng thái merge #6+#7; (4) hợp đồng feature 3 cờ → 1, phát 6 nơi.
- **Chưa có review nào.**

---

## PHẦN F — ISSUE CÒN MỞ (M3–M6)

| Issue | Milestone | AC | Phụ thuộc | Ghi chú |
|---|---|---:|---|---|
| #8 `feat(eda)` — 4 họ chỉ số + chu kỳ đa tầng | M3 | 6 + 2 | #3,#4,#7 | ⚠️ Body đã **mở rộng scope** 30/09: tương tác fog×mùa (Xuân −8,91, Đông +2,79, F=16,78, p=7,4e-11), `pm25_was_stuck` hằng số 0, đa cộng tuyến `corr(pm25,pm10)=0,9727` R²=0,9462 → cần VIF |
| #9 `feat(viz)` — FIG-01…FIG-07 | M3 | 6 + 1 | #8 | Tiêu đề phải là **takeaway conclusion**; trục tung bar từ 0; palette thân thiện người khiếm thị màu |
| #10 `docs(midterm)` — báo cáo + slide SCQA 7 phút + tag | M3 | 5 + 1 | #8,#9 | AC3 nhắc notebook `00`→`04`; nhưng trên đĩa `04` chưa tồn tại |
| #11 `feat(stats)` — kiểm định phi tham số | M4 | 5 + 1 | #7,#8,#10 | Bộ bốn bắt buộc: thống kê + p + effect size + 95% Bootstrap CI; 1000 lặp; α=0,05; `r_rb = 1 − 2U/(n₁·n₂)` |
| #12 `feat(model)` — OLS + LINE | M4 | 7 + 2 | #7,#11 | VIF > 5,0 là **heuristic**; Ridge/Lasso tune **hoàn toàn trên Train**; cấm "causes" |
| #13 `feat(model)` — phân loại cảnh báo | M4 | **9** + 2 | #7,#11,#12 | ⚠️ AC **6 → 9** (PR #34 thêm 3). Thêm khối `[!WARNING]` về đuôi rỗng Test |
| #14 `docs(ethics)` — định kiến + Spark + datasheet/model card | M5 | 6 + 1 | #12,#13 | Datasheet theo khung Timnit Gebru |
| #15 `refactor(code)` — module hoá + độ nhạy ngưỡng | M5 | 5 + 1 | #11–#14 | Ngưỡng 40/45/50/55 µg/m³ phải **dán nhãn là ngưỡng phân tích độ nhạy kỹ thuật** |
| #16 `docs(report)` — SCQA + slide 12–15 + viva Q&A 15 câu | M5 | 6 + 1 | #9,#11–#15 | |
| #17 `chore(defense)` — kiểm toán + nbconvert 01→06 + tag | M6 | 8 + 2 | tất cả | ⚠️ AC7 nói "**17 issues**" nhưng repo có **18** (#19 tạo sau #17) |

**Quy tắc còn treo trong issue #11 (ghi rõ trong body):** ngưỡng QCVN 24h = 50 µg/m³, ngưỡng năm = 25 µg/m³ —
**mâu thuẫn** với những gì PR #20 và PR #26 đã chốt (45 µg/Nm³ từ 01/01/2026 theo QCVN 05:2023/BTNMT).