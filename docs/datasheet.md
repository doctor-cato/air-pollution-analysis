# Datasheet for Dataset — Dữ liệu Chất lượng Không khí ($\text{PM}_{2.5}$) & Khí tượng Hà Nội (2022–2026)

> **Căn cứ học thuật:** Gebru et al. (2021), *Datasheets for Datasets* (*Communications of the ACM*) · Tuần 12 / Issue #14 (Task 8.6, Task 1.24, Task D18)  
> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (Trường Đại học CMC)  
> **Phiên bản tập dữ liệu bao phủ:**
> - **Baseline (`1.0.0-m2-baseline`):** [`data/processed/air_pollution_final.parquet`](../data/processed/air_pollution_final.parquet) (`9.044` dòng × `18` cột, trạm `VN001_HANOI_556_NGUYEN_VAN_CU`)
> - **Mở rộng tách trạm (`2.0.0-issue44-extended`):** [`data/processed/air_pollution_extended_2022_2026.parquet`](../data/processed/air_pollution_extended_2022_2026.parquet) (`37.722` dòng × `23` cột = `28.678` dòng `VN003` + `9.044` dòng `VN001`)  
> **Tài liệu liên quan:** [`docs/data_dictionary.md`](data_dictionary.md) · [`docs/issue44_dataset_contract.md`](issue44_dataset_contract.md) · [`docs/issue44_source_verification.md`](issue44_source_verification.md) · [`docs/issue50_reproducibility.md`](issue50_reproducibility.md)

---

## 1. Mục đích Khởi tạo (Motivation)

- **Mục đích tạo lập:** Tập dữ liệu được xây dựng cho đồ án học thuật INFO3020 nhằm: (1) mô tả phân phối thực nghiệm và chu kỳ thời gian đa tầng của $\text{PM}_{2.5}$ tại Hà Nội; (2) kiểm định giả thuyết thống kê có xét tự tương quan thời gian; (3) phân tích hồi quy OLS và mô hình phân loại cảnh báo sớm trung bình trượt 24 giờ theo ngưỡng tham chiếu QCVN 05:2023/BTNMT ($50\,\mu\text{g/m}^3$).
- **Đơn vị thực hiện & tài trợ:** Nhóm Chủ đề 6 (*Topic 6 Team*), Khoa CNTT & Truyền thông, Trường Đại học CMC (giảng viên hướng dẫn: ThS. Phạm Ngọc Đông). Không có tài trợ thương mại hay bên thứ ba.
- **Lưu ý ranh giới mục đích:** Dữ liệu khí tượng từ Open-Meteo ERA5 là dữ liệu tái phân tích có độ trễ phát hành khoảng 5 ngày; do đó mô hình sử dụng tập dữ liệu này mang bản chất nghiên cứu hồi cứu / truy hồi lịch sử (*retrospective analysis*), không phải hệ thống vận hành thời gian thực.

---

## 2. Thành phần Dữ liệu (Composition)

### 2.1. Thực thể quan sát & Quy tắc tách trạm tuyệt đối
Mỗi bản ghi đại diện cho **1 giờ quan trắc chuẩn hóa** theo múi giờ `Asia/Ho_Chi_Minh` (UTC+7), định danh duy nhất bởi cặp khóa `(station_id, timestamp)` (0 bản ghi trùng khóa). Hai trạm thực tế không có giờ chồng lấp (cách nhau `7,324 km` và cách nhau `2.040` giờ ngừng ghi nhận giữa `2025-04-09 22:00` và `2025-07-03 22:00`), do đó **tuyệt đối không được ghép nối thành một chuỗi liên tục duy nhất**.

| Mã trạm (`station_id`) | Nguồn & Location ID | Tọa độ | Khoảng cách tới ô lưới ERA5 | Cửa sổ thời gian (`Asia/Ho_Chi_Minh`) | Số giờ lưới | $\text{PM}_{2.5}$ hợp lệ (`n`) | $\text{PM}_{2.5}$ khuyết (`NaN`) | Trạng thái sử dụng |
|---|---|---|---:|---|---:|---:|---:|---|
| `VN001_HANOI_556_NGUYEN_VAN_CU` | OpenAQ S3 `4946811` (NCEM/VEA, 556 Nguyễn Văn Cừ) | `21.0491°N, 105.8831°E` | `1,704 km` | `2025-07-03 22:00` → `2026-07-15 17:00` | `9.044` | `7.495` (`82,87%`) | `1.549` (`17,13%`) | **Baseline chính** (`1.0.0-m2-baseline`) & cohort `VN001` |
| `VN003_HANOI_OPENAQ_7441` | OpenAQ S3 `7441` (`sensors_id=21632`, AirNow Gov Monitor) | `21.021939°N, 105.818806°E` | `9,026 km` | `2022-01-01 01:00` → `2025-04-09 22:00` | `28.678` | `18.208` (`63,49%`) | `10.470` (`36,51%`) | **Mở rộng lịch sử độc lập** (`2.0.0-issue44-extended`) |
| `VN002_HANOI_US_EMBASSY` | AirNow DOS Historical CSV / GitHub mirror `dolekhanhdang` | `21.0215°N, 105.8184°E` | `9,081 km` | `2022-01-01` → `2025-04-09` (trên mirror) | — | — | — | **`NO-GO / Reference-Only`** (không ingest) |

### 2.2. Lược đồ cột & Khuyết thiếu (Schema & Missingness)
- **`1.0.0-m2-baseline` (18 cột):** `timestamp`, `station_id`, `location`, `pm25` (`17,13%` khuyết), `pm10` (`1.469` khuyết = `16,24%`), 3 cờ chẩn đoán (`pm25_was_stuck`, `pm25_was_missing`, `is_high_humidity_fog`), 6 biến khí tượng ERA5 (`temperature`, `relative_humidity`, `wind_speed`, `wind_direction`, `precipitation`, `surface_pressure` — `0,00%` khuyết), và 4 đặc trưng chu kỳ (`hour_sin`, `hour_cos`, `month_sin`, `month_cos`).
- **`2.0.0-issue44-extended` (23 cột = 18 cột trên + 5 cột mở rộng):** `split` (`train`/`test` theo thời gian nội trạm `80/20`), `pm25_derived_interpolated`, `pm25_is_derived`, `winter_year`, `season`. Trên `VN003`, `pm10` khuyết `100%` (`NaN`) do sensor `7441` trên OpenAQ chỉ cung cấp `pm25`.
- **Phân tách tuyệt đối `NaN` vs `0.0`:** Giá trị thiếu quan trắc luôn được giữ nguyên là `NaN` trong cột `pm25`; nghiêm cấm điền số `0.0` hay giá trị nội suy vào cột quan trắc gốc.

### 2.3. Phân chia Train/Test chuẩn hóa
- **Baseline `VN001` (`1.0.0-m2-baseline`):** Cắt tuyến tính tại `2026-01-15 00:00:00+07:00` → Train `4.682` giờ lưới (`4.279` `pm25` hợp lệ), Test `4.362` giờ lưới (`3.216` `pm25` hợp lệ).
- **Extended (`2.0.0-issue44-extended`, tách riêng từng trạm — Protocol A):**
  - `VN003`: cắt tại `2024-08-13 23:00:00+07:00` → Train `22.942` giờ / Test `5.736` giờ.
  - `VN001`: cắt tại `2026-05-01 09:00:00+07:00` → Train `7.235` giờ / Test `1.809` giờ (lưu ý kỹ thuật: phần Test này rơi vào giai đoạn có sự cố mất kết nối `630` giờ từ `2026-06-19`, dẫn tới `0` ca dương tính trượt 24h trong `242` giờ đánh giá).
- **Protocol B (gộp chung 2 trạm):** Bị bác bỏ chính thức trong [`docs/issue44_dataset_contract.md`](issue44_dataset_contract.md) §4 vì rò rỉ tương lai `VN001` vào `VN003` Test.

---

## 3. Quy trình Thu thập & Nguồn gốc Dữ liệu (Collection Process & Provenance)

- **Nguồn chất lượng không khí `VN001`:** OpenAQ Public S3 Archive (`locationid=4946811`, `sensors_id=13502150` cho `pm25`, `13502165` cho `pm10`), trạm quan trắc chính phủ NCEM/VEA tại 556 Nguyễn Văn Cừ (`349.463` bản ghi thô sub-hourly tổng hợp về `8.022` giờ canonical).
- **Nguồn chất lượng không khí `VN003`:** OpenAQ Public S3 Archive (`locationid=7441`, `sensors_id=21632`, `AirNow` Government Monitor), gồm `903` tệp ngày `.csv.gz` (`21.401` dòng thô; `3.193` dòng `-999.0`/`-1.0`/`-6.0` chuyển sang `NaN`; còn `18.208` giờ hợp lệ).
- **Nguồn `VN002` Mirror bị từ chối (`NO-GO`):** Kho GitHub bên thứ ba `dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies` (commit `25d08e949c9d01ba57c4e74ff9b3b99328ecf141`) bị từ chối ingest do `license: null`, `3` tệp tháng 12 xếp nhầm thư mục năm, `4` tệp chứa bản ghi chéo năm và `1` mốc xung đột `conflicting_duplicate` (`2023-11-07T17:00:00`). Chi tiết kiểm toán lưu tại [`reports/issue44_mirror_manifest.json`](../reports/issue44_mirror_manifest.json).
- **Nguồn khí tượng bề mặt:** Open-Meteo Historical Archive API (ECMWF ERA5 Reanalysis `0.25°`, điểm lưới `21.05448°N, 105.89848°E`, `0,00%` thiếu trên cả cửa sổ `9.072` giờ baseline lẫn `28.680` giờ mở rộng 2022–2025).
- **Mã băm kiểm chứng toàn vẹn (SHA-256) đã ghi nhận:**

| Artifact | Vai trò | SHA-256 ghi nhận | Nguồn kiểm chứng & Ghi chú tái lập |
|---|---|---|---|
| `data/raw/openaq_raw_4946811.parquet` | Raw `VN001` | `4168735570d16f80df7136e93b8da96bbb03ed5631c57ca8ffea6f09d92ae60f` | [`data/raw/metadata.json`](../data/raw/metadata.json) |
| `data/raw/open_meteo_raw_2025-07-03_2026-07-15.json` | Raw ERA5 `VN001` | `59bfececa2dc658c15898df082a19566fce7019048ec8236b55dc731f45bc79c` | [`data/raw/metadata.json`](../data/raw/metadata.json) |
| `data/processed/air_pollution_final.parquet` | Processed baseline (`1.0.0`) | `866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd` | [`reports/issue44_extended_dataset_metadata.json`](../reports/issue44_extended_dataset_metadata.json) (lưu ý serialize Parquet có thể đổi theo phiên bản thư viện khi build lại) |
| `data/raw/openaq_raw_7441_2022_2025.parquet` | Raw `VN003` | `57b6fbaa63089e57a6377fd85293355cb475f8d8bb62fb58b469ced27a4cdae8` | [`reports/issue44_openaq_7441_manifest.json`](../reports/issue44_openaq_7441_manifest.json) |
| `data/raw/open_meteo_raw_2022-01-01_2025-04-09.json` | Raw ERA5 `VN003` | `303aacb68798667e2c838be09ad0047a6cedf292282e9ab250a7dfa88160923f` | Snapshot Issue #44; bản tải lại ở Issue #50 có SHA-256 `a0d841fc92efd3e63f4e3f5664fed9211a7cc50ba50ff5a632a288ff7329d99b`, do không còn tệp gốc cũ nên đối chiếu giá trị từng ô ERA5 gắn **`UNVERIFIED`** ([`docs/issue50_reproducibility.md`](issue50_reproducibility.md)) |
| `data/processed/air_pollution_extended_2022_2026.parquet` | Processed extended (`2.0.0`) | `6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02` | [`docs/issue44_dataset_contract.md`](issue44_dataset_contract.md) (bản build cục bộ Issue #50 ghi nhận `124c7fc851b89114d7734ed73e4834945d2f589cec263ffe443f23956d35bb4b` do khác phiên bản Parquet, khớp 100% schema/số dòng/ô quan trắc) |

---

## 4. Tiền xử lý, Làm sạch & Dữ liệu Dẫn xuất (Preprocessing, Cleaning & Derived Data)

- **Làm sạch tất định (`src/cleaning.py`):**
  1. Chuẩn hóa trục thời gian sang `Asia/Ho_Chi_Minh` và khử trùng lặp theo `(station_id, timestamp)`.
  2. Chuyển đổi mã lỗi ngụy trang (`-999`, `-9999`) và giá trị âm phi vật lý (`< 0`) thành `NaN` (`3.193` dòng trên `VN003`).
  3. Kiểm tra ràng buộc khí động học $\text{PM}_{2.5} \le \text{PM}_{10}$ trên `VN001`.
  4. Kiểm tra kẹt cảm biến (`pm25_was_stuck`: `0` giờ kẹt thực tế ở cả `VN001` và `VN003`).
  5. Reindex lưới 1 giờ liên tục độc lập theo từng trạm — **không điền khuyết** (`assert_no_imputation()` xác nhận mọi ô quan trắc giữ nguyên giá trị gốc hoặc thành `NaN`).
- **Tách biệt Dẫn xuất Nội suy vs Quan trắc (`pm25_derived_interpolated` vs `pm25`):**
  - Thực nghiệm masking-validation ([`reports/issue44_interpolation_evaluation.csv`](../reports/issue44_interpolation_evaluation.csv)) cho thấy nội suy tuyến tính $\le 2\text{h}$ chỉ khôi phục `1,85%` số giờ thiếu của `VN003` (`194/10.470`) và `9,55%` của `VN001` (`148/1.549`) nhưng gây sai số mùa đông `12,40–17,24 µg/m³` RMSE và sử dụng điểm tương lai $t+1$.
  - Vì vậy, **cột `pm25` giữ nguyên `NaN`**. Giá trị nội suy chỉ nằm ở cột dẫn xuất `pm25_derived_interpolated` (đánh dấu `pm25_is_derived=True`) và bị cấm làm feature trong mô hình cảnh báo sớm ([`src/classification.py`](../src/classification.py)).
- **Cờ bị loại khỏi tập feature (`src/cleaning_pipeline.py`):**
  - `pm25_was_missing` (`TARGET_DERIVED_FLAGS`): loại do rò rỉ cấu trúc với `SimpleImputer(median)`.
  - `is_high_humidity_fog` (`NON_PREDICTIVE_FLAGS`): giữ trong dataset phục vụ chẩn đoán tương tác `fog × mùa`, không đưa làm feature đơn lẻ mặc định.

---

## 5. Miền Sử dụng, Rủi ro Đạo đức & Giải trình Pháp lý (Uses, Ethics & Legal Compliance)

### 5.1. Phạm vi sử dụng phù hợp và không phù hợp
- **Nên dùng cho:** Phân tích chuỗi thời gian ô nhiễm đô thị tại 2 điểm đo Hà Nội; đánh giá mô hình giải thích OLS và cảnh báo hồi cứu đa tầm có kiểm soát rò rỉ.
- **Không nên dùng cho:** Suy diễn nhân quả; đại diện cho toàn bộ 30 quận/huyện Hà Nội (chỉ có 2 trạm đô thị nội thành cách `7,324 km` không có quan trắc chồng lấp); vận hành cảnh báo thời gian thực khi chưa thay ERA5 (độ trễ ~5 ngày) bằng khí tượng thời gian thực/NWP; gộp `VN003` và `VN001` thành một chuỗi đơn trạm.

### 5.2. Giải trình loại trừ các khái niệm ẩn danh cá nhân & Nghị định 13/2023/NĐ-CP (Task 1.24)
Theo tài liệu chuẩn Slide W12 và yêu cầu đối soát của `docs/TASK_LIST_M3_M6.md` (Task 1.24 & mục Nghị định 13/2023/NĐ-CP), các kỹ thuật bảo vệ quyền riêng tư và công bằng cá nhân dưới đây **không áp dụng (N/A)** trên tập dữ liệu này vì lý do cấu trúc dữ liệu rõ ràng:
1. **`k-anonymity`:** Tập dữ liệu không chứa bản ghi cấp cá nhân và không có bất kỳ *quasi-identifier* nào của con người (như tuổi, giới tính, nghề nghiệp, địa chỉ cư trú hay mã định danh cá nhân); thực thể duy nhất là 2 trạm quan trắc môi trường cố định công khai (`VN001`, `VN003`).
2. **`Fairness–Accuracy Trade-off`:** Tập dữ liệu không có thuộc tính nhạy cảm nhân khẩu học (*protected attributes* như chủng tộc, giới tính, thu nhập cá nhân) để phân tầng công bằng theo nhóm dân cư; việc phân tầng độ tin cậy được thực hiện theo **trạm, năm, mùa và độ phủ dữ liệu** nhằm kiểm soát thiên lệch lấy mẫu (*sampling/missingness bias*).
3. **`Anonymisation vs Pseudonymisation` & Nghị định 13/2023/NĐ-CP:** Toàn bộ dữ liệu đầu vào là thông số vật lý – môi trường công khai (nồng độ bụi $\text{PM}_{2.5}/\text{PM}_{10}$ và khí tượng bề mặt ERA5) được cung cấp dưới giấy phép mở `ODC-BY v1.0`, `US Public Domain`, và `CC BY 4.0`, **không phải dữ liệu cá nhân** gắn với bất kỳ chủ thể dữ liệu tự nhiên nào theo định nghĩa tại Khoản 1 Điều 2 Nghị định 13/2023/NĐ-CP của Chính phủ Việt Nam. Do đó, việc thu thập và xử lý tập dữ liệu này không phát sinh nghĩa vụ xử lý/ẩn danh dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP.

---

## 6. Phân phối & Giấy phép (Distribution)

- **Chính sách lưu trữ 3 tầng (`Three-tier Raw Data Policy`):** Tệp thô và tệp Parquet xử lý (`data/raw/*.parquet`, `data/raw/*.json`, `data/interim/*.parquet`, `data/processed/*.parquet`) **không commit lên Git** (`.gitignore`). Kho lưu trữ theo dõi `data/raw/metadata.json`, các manifest JSON/CSV trong `reports/`, mã nguồn `src/` và script tái lập `scripts/`.
- **Giấy phép thành phần nguồn:**
  - `VN001` (OpenAQ Location `4946811`, NCEM/VEA): **ODC-BY v1.0** (yêu cầu ghi công OpenAQ & VEA/CEM).
  - `VN003` (OpenAQ Location `7441`, AirNow Gov Monitor): **U.S. Public Domain** (`license id=33`).
  - Khí tượng Open-Meteo ERA5: **CC BY 4.0** (ghi công Open-Meteo & Copernicus C3S).
  - Mã nguồn phân tích trong repository: **MIT License** ([`LICENSE`](../LICENSE)).
- **Cách tái tạo đầy đủ cục bộ:** Chạy tuần tự `python scripts/fetch_dataset.py` → thực thi `notebooks/03_data_cleaning.ipynb` → `notebooks/03_transformation_pipeline.ipynb` → `python scripts/build_extended_historical_dataset.py`.

---

## 7. Bảo trì & Quản trị Phiên bản (Maintenance)

- **Người phụ trách bảo trì:** Nhóm Chủ đề 6 (`doctor-cato/air-pollution-analysis`), kiểm chứng hợp đồng dữ liệu qua `tests/test_issue44_preparation.py`, `tests/test_cleaning_pipeline_guards.py`, `scripts/validate_extended_reanalysis.py --real-data`, và `scripts/verify_claims.py`.
- **Quy tắc bất biến khi cập nhật:** Mọi phiên bản mở rộng trong tương lai (như `2.0.0-issue44-extended`) phải được lưu tách tệp và tách cohort theo `station_id`, tuyệt đối không sửa ngược cột quan trắc của `1.0.0-m2-baseline` (`air_pollution_final.parquet`) hoặc gộp nối 2 trạm khác vị trí.
