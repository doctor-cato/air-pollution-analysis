# Báo Cáo Kiểm Toán Chất Lượng Dữ Liệu 6 Chiều & Cơ Chế Khuyết Thiếu
## Data Quality Audit & Missingness Mechanism Report

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)  
> **Căn cứ kỹ thuật:** Lộ trình đồ án [`docs/roadmap.md`](roadmap.md), GitHub Issue #5 (Milestone 1), và phương pháp luận CRISP-DM.  
> **Tài liệu tham chiếu:** [`docs/data_dictionary.md`](data_dictionary.md), [`docs/source_profiling_decision.md`](source_profiling_decision.md), [`notebooks/02_quality_audit.ipynb`](../notebooks/02_quality_audit.ipynb).  
> **Trạng thái:** Hoàn tất kiểm toán dữ liệu Canonical trên `data/interim/`.

---

## 1. Mục Đích & Nguyên Tắc Kiểm Toán (Purpose & Audit Principles)

### 1.1. Mục đích
Issue #5 thực hiện kiểm toán độc lập chất lượng dữ liệu của hai tập dữ liệu chuẩn hóa theo **Canonical Schema** tại `data/interim/`:
1. Tập dữ liệu chất lượng không khí: `data/interim/air_quality_canonical.parquet` (sản phẩm từ Issue #3).
2. Tập dữ liệu khí tượng bề mặt ERA5: `data/interim/weather_canonical.parquet` (sản phẩm từ Issue #4).

Kiểm toán được tiến hành theo khung tiêu chuẩn **6 Chiều Chất lượng Dữ liệu Quốc tế** (*Six Dimensions of Data Quality*): **Completeness**, **Accuracy**, **Consistency**, **Validity**, **Uniqueness**, và **Timeliness**. Đồng thời, báo cáo khảo sát các hình thái khuyết thiếu theo không gian, thời gian và phân loại theo hệ thống cơ chế của Donald Rubin (1976: MCAR, MAR, MNAR).

### 1.2. Ranh giới bất biến giữa Issue #5 và Issue #6
- **Chế độ chỉ đọc (Strict Read-Only Audit):** Báo cáo và module kiểm toán chỉ làm nhiệm vụ đo lường, kiểm định, đánh giá và ghi nhận bằng chứng khách quan hiện trạng dữ liệu. Tuyệt đối **không xóa dòng, không sửa đổi dữ liệu và không điền khuyết (imputation)**.
- **Xử lý mã lỗi ngụy trang (Sentinel handling note):**
  > *Sentinel codes such as -999/-9999 were converted to NaN during ingestion in Issues #3/#4. Issue #5 audits the resulting missingness and does not repeat sentinel cleaning.*  
  > (Các mã ngụy trang như `-999`, `-9999` đã được chuyển đổi thành `NaN` trong quá trình thu thập và chuẩn hóa tại Issue #3/#4. Issue #5 chỉ kiểm toán tỷ lệ khuyết thiếu thực tế còn lại và không lặp lại thao tác làm sạch sentinel).
- **Xử lý chuỗi giá trị số 0 (Stuck values note):**
  > *Prolonged zero patterns are measured as quantitative evidence only; final stuck-sensor treatment belongs to Issue #6.*  
  > (Các chuỗi giá trị số 0 kéo dài chỉ được đo lường dưới dạng bằng chứng định lượng; quyết định cuối cùng về việc xử lý kẹt cảm biến thuộc thẩm quyền của Issue #6).

---

## 2. Phạm Vi Tập Dữ Liệu (Dataset Scope & Provenance)

Toàn bộ chỉ số định lượng trong báo cáo được trích xuất trực tiếp từ các tệp dữ liệu Canonical thực tế trên đĩa:

| Thuộc tính phạm vi | Tập Chất Lượng Không Khí (`air_quality_canonical`) | Tập Khí Tượng Bề Mặt (`weather_canonical`) |
|---|---|---|
| **Đường dẫn lưu trữ** | `data/interim/air_quality_canonical.parquet` | `data/interim/weather_canonical.parquet` |
| **Nguồn dữ liệu gốc** | OpenAQ S3 Public Archive (`location_id=4946811`) | Open-Meteo Historical Weather API (ECMWF ERA5 Reanalysis) |
| **Trạm quan trắc / Điểm lưới** | `VN001_HANOI_556_NGUYEN_VAN_CU` (556 Nguyễn Văn Cừ, Long Biên, Hà Nội) | Điểm lưới ERA5 ($21.0545^\circ\text{N}, 105.8985^\circ\text{E}$) |
| **Tọa độ thực tế** | $21.0491^\circ\text{N}, 105.8831^\circ\text{E}$ | $21.0545^\circ\text{N}, 105.8985^\circ\text{E}$ (cách trạm quan trắc 1.7 km) |
| **Tổng số bản ghi** | **8.022 mốc giờ** | **9.072 mốc giờ** |
| **Số trường (cột)** | 5 cột (`timestamp`, `station_id`, `location`, `pm25`, `pm10`) | 7 cột (`timestamp`, `temperature`, `relative_humidity`, `wind_speed`, `wind_direction`, `precipitation`, `surface_pressure`) |
| **Dải thời gian thực tế (`actual_source_coverage`)** | **`2025-07-03 22:00:00+07:00` $\to$ `2026-07-15 17:00:00+07:00`** | **`2025-07-03 00:00:00+07:00` $\to$ `2026-07-15 23:00:00+07:00`** |
| **Cơ chế dẫn xuất dải thời gian** | Tính toán động trực tiếp từ `min()` và `max()` timestamp trong DataFrame | Tính toán động trực tiếp từ `min()` và `max()` timestamp trong DataFrame |
| **Cửa sổ nghiên cứu truy vấn (`requested_study_window`)** | Tham số dự án: 2023–2024 (lưu ý: OpenAQ trạm 4946811 bắt đầu từ 07/2025) | 2025-07-03 $\to$ 2026-07-15 (cửa sổ được **dẫn xuất động** từ `min()`/`max()` của chuỗi chất lượng không khí, không phải khung 2023–2024) |

> [!IMPORTANT]
> **Giao thoa thời gian (Temporal Overlap) — đã kiểm chứng:**
> Phép `inner join` trên khóa `timestamp` cho ra **8.022 bản ghi**, tức **100,00%** tập chất lượng không khí có dữ liệu khí tượng đi kèm. **Không** xảy ra Row Explosion (số bản ghi sau join không vượt quá số bản ghi trước join). Khoảng giao thoa: `2025-07-03 22:00` → `2026-07-15 17:00`. Cùng kết luận này được ghi nhận độc lập trong `data/raw/metadata.json` → `collection_pipeline_execution.temporal_integration` (`air_quality_coverage_pct = 100.0`, `row_explosion_detected = false`).

---

## 3. Bảng Tổng Hợp Dữ Liệu Khuyết Thiếu (Missing-Data Summary)

Kết quả kiểm toán từng cột thông qua hàm `audit_dataframe(df)` và `audit_missing_representations(df)`:

| Cột (Variable) | Kiểu dữ liệu (dtype) | Tổng số dòng | Số lượng khuyết (`NaN`) | Tỷ lệ khuyết (%) | Số giá trị duy nhất | Giá trị nhỏ nhất (Min) | Phân vị 25% | Trung vị (Median) | Phân vị 75% | Giá trị lớn nhất (Max) | Ký tự ngụy trang (`N/A`, `null`, `None`) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`timestamp`** (Air) | `datetime64[ns, Asia/Ho_Chi_Minh]` | 8.022 | 0 | 0,00% | 8.022 | 2025-07-03 22:00 | - | - | - | 2026-07-15 17:00 | 0 |
| **`station_id`** | `object` | 8.022 | 0 | 0,00% | 1 | `VN001...` | - | - | - | `VN001...` | 0 |
| **`location`** | `object` | 8.022 | 0 | 0,00% | 1 | `556 Nguyễn Văn Cừ` | - | - | - | `556 Nguyễn Văn Cừ` | 0 |
| **`pm25`** | `float64` | 8.022 | **203** | **2,53%** | 7.666 | 1,06 | 25,29 | 37,91 | 58,09 | 252,64 | 0 |
| **`pm10`** | `float64` | 8.022 | **123** | **1,53%** | 7.759 | 1,01 | 37,88 | 55,56 | 83,36 | 339,99 | 0 |
| **`timestamp`** (Weather) | `datetime64[ns, Asia/Ho_Chi_Minh]` | 9.072 | 0 | 0,00% | 9.072 | 2025-07-03 00:00 | - | - | - | 2026-07-15 23:00 | 0 |
| **`temperature`** | `float64` | 9.072 | 0 | 0,00% | 283 | 8,90 | 21,30 | 25,40 | 28,40 | 38,60 | 0 |
| **`relative_humidity`** | `float64` | 9.072 | 0 | 0,00% | 68 | 30,0 | 71,0 | 83,0 | 92,0 | 100,0 | 0 |
| **`wind_speed`** | `float64` | 9.072 | 0 | 0,00% | 626 | 0,0 | 1,43 | 2,31 | 3,23 | 9,55 | 0 |
| **`wind_direction`** | `float64` | 9.072 | 0 | 0,00% | 360 | 1,0 | 82,0 | 139,0 | 175,0 | 360,0 | 0 |
| **`precipitation`** | `float64` | 9.072 | 0 | 0,00% | 100 | 0,0 | 0,0 | 0,0 | 0,1 | 20,50 | 0 |
| **`surface_pressure`** | `float64` | 9.072 | 0 | 0,00% | 377 | 986,5 | 1002,4 | 1007,6 | 1014,1 | 1028,4 | 0 |

---

## 4. Bảng Kiểm Toán Chất Lượng Dữ Liệu 6 Chiều (Six-Dimension Quality Table)

Đánh giá định lượng toàn bộ dữ liệu đối chiếu với các nguyên tắc Tufte/Cleveland và ISO/IEC 25012:

| Chiều chất lượng (Dimension) | Tiêu chí đo lường (Metric) | Bằng chứng thực nghiệm định lượng (Actual Evidence) | Kết quả quan sát & Đánh giá (Result / Observation) | Hạn chế kỹ thuật & Khuyến nghị (Limitation & Recommendation) |
|---|---|---|---|---|
| **1. Completeness** *(Độ đầy đủ)* | Tỷ lệ khuyết thiếu từng biến & Độ bao phủ lưới 1 giờ liên tục | - Tập Weather: 0/9.072 ô khuyết (0,00% missing trên 100% biến).<br>- Tập Air Quality: PM2.5 thiếu 203/8.022 mốc (2,53%), PM10 thiếu 123 mốc (1,53%).<br>- Lưới thời gian liên tục từ `2025-07-03 22:00` đến `2026-07-15 17:00` là 9.044 giờ; thực tế ghi nhận 8.022 giờ (thiếu 1.022 giờ ngắt quãng trên S3, tương đương 11,30%). | - Tập thời tiết đạt độ đầy đủ tuyệt đối 100%.<br>- Tập chất lượng không khí đạt độ khả dụng cao (97,47% PM2.5).<br>- Tồn tại các khoảng trống thời gian do trạm ngừng phát sóng telemetry lên S3. | - Khoảng trống 1.022 giờ chưa xuất hiện dưới dạng hàng `NaN` trong bảng interim.<br>- **Khuyến nghị Issue #6:** Thực hiện `reindex` chuỗi thời gian liên tục 1 giờ độc lập cho trạm để bộc lộ các hàng khuyết tự nhiên kèm cờ `pm25_was_missing`. |
| **2. Accuracy** *(Độ chính xác)* | Giới hạn vật lý khí quyển & Tính hợp lý khí động học ($\text{PM}_{2.5} \le \text{PM}_{10}$) | - Nhiệt độ: min 8,9°C, max 38,6°C (0 vi phạm bounds [0, 50]°C).<br>- Độ ẩm: min 30%, max 100% (0 vi phạm bounds [0, 100]%).<br>- Tốc độ gió: min 0,0, max 9,55 m/s (0 giá trị âm).<br>- PM2.5: min 1,06, max 252,64 µg/m³ (0 giá trị âm).<br>- **Ràng buộc khí động học:** Trong 7.696 cặp đo đồng thời:<br>  + **Vi phạm nghiệm ngặt ($\text{PM}_{2.5} > \text{PM}_{10}$): 324 cặp (4,21%)**.<br>  + **Vượt ngưỡng dung sai ($\text{PM}_{2.5} > \text{PM}_{10} + 2.0\,\mu\text{g/m}^3$): 282 cặp (3,66%)**.<br>  + *Cơ sở dung sai:* BAM-1020 và cảm biến quang học có độ không đảm bảo đo lường thiết bị (instrumentation measurement uncertainty $\approx \pm 2.0\,\mu\text{g/m}^3$ theo chuẩn US EPA / QCVN).<br>- Độ ẩm cao: 2.843 giờ có $\text{RH} > 90\%$ (31,34%). | - Toàn bộ các biến vật lý đơn lẻ đều nằm trong giới hạn tự nhiên hợp lý tại Hà Nội.<br>- Bằng chứng thực nghiệm ghi nhận 4,21% vi phạm nghiệm ngặt và 3,66% vượt ngưỡng dung sai nồng độ bụi ($\text{PM}_{2.5} > \text{PM}_{10}$). Mẫu hình quan sát có thể liên quan đến sai số đo giữa các cảm biến quang học độc lập và ảnh hưởng của độ ẩm môi trường; nguyên nhân vật lý cụ thể chưa được xác minh trực tiếp từ log thiết bị tại trạm. | - Cần phân biệt rõ sai số phần cứng và biến động thực tế.<br>- **Khuyến nghị Issue #6:** Chuyển các cặp nghịch đảo vượt quá sai số đo ($\epsilon = 2.0\,\mu\text{g/m}^3$) thành `NaN`, gắn cờ `is_high_humidity_fog = 1` cho giờ $\text{RH} > 90\%$ thay vì xóa dòng. |
| **3. Consistency** *(Độ nhất quán)* | Sự đồng nhất về đơn vị, múi giờ và thứ tự thời gian | - Đơn vị: PM2.5/PM10 ($\mu\text{g/m}^3$), Nhiệt độ ($^\circ\text{C}$), Độ ẩm ($\%$), Gió ($\text{m/s}$), Áp suất ($\text{hPa}$), Mưa ($\text{mm}$).<br>- Múi giờ: 100% bản ghi được định danh `Asia/Ho_Chi_Minh` (UTC+7).<br>- Thứ tự thời gian: `df['timestamp'].is_monotonic_increasing == True` trên cả hai tập. | - Đồng nhất 100% với Canonical Data Dictionary.<br>- Không có hiện tượng trượt pha thời gian giữa giờ địa phương và UTC.<br>- Hai tập interim **cùng phủ dải 2025-07 → 2026-07** và đã `inner join` thành công: **8.022 bản ghi, độ phủ 100,00%**, không Row Explosion. | - Dải thời gian vận hành (2025-07 → 2026-07) **không** phù hợp khung mục tiêu 2023–2024 của dự án; việc mở rộng phụ thuộc nguồn lịch sử và thuộc phạm vi M2. |
| **4. Validity** *(Tính hợp lệ)* | Định dạng kiểu dữ liệu (dtypes) và lược đồ chuẩn | - `timestamp`: `datetime64[ns, Asia/Ho_Chi_Minh]`.<br>- Các biến đo lường: `float64`.<br>- Định danh: `station_id` và `location` là `object`.<br>- Không có giá trị vô cực (`inf`) hoặc mã lỗi ngụy trang. | - 100% cột hợp lệ theo lược đồ giao diện Canonical Schema. | Không phát hiện vi phạm định dạng. |
| **5. Uniqueness** *(Tính duy nhất)* | Tính duy nhất của khóa quan sát (Observation Key) | - Tập Air Quality: Khóa `(station_id, timestamp)` có **0 bản ghi trùng lặp** (duplicate rate = 0.00%).<br>- Tập Weather: Khóa `timestamp` có **0 bản ghi trùng lặp** (duplicate rate = 0.00%). | - Tính duy nhất đạt 100%. Toàn vẹn khóa chính hoàn hảo. | Không có rủi ro trùng lặp bản ghi. |
| **6. Timeliness** *(Tính kịp thời)* | Tần suất lấy mẫu, khoảng cách quan trắc và độ trễ | - Khoảng cách lấy mẫu trung vị: **1,0 giờ** trên cả hai tập.<br>- Tập Weather: 9.071/9.071 khoảng cách đều đúng 1,0 giờ (100% hoàn hảo).<br>- Tập Air: 7.928/8.021 khoảng cách đúng 1,0 giờ (98,84%); 42 khoảng cách 2 giờ, 14 khoảng cách 3 giờ; khoảng cách lớn nhất **626 giờ**.<br>- Dải thời gian thực tế: phản ánh trung thực năng lực vận hành trạm. | - Tần suất lấy mẫu theo giờ được duy trì ổn định.<br>- Tập thời tiết đạt tính liên tục hoàn hảo.<br>- Tập ô nhiễm có độ trễ gián đoạn cục bộ ngắn hạn (1–3 giờ) **và** một đợt mất dữ liệu kéo dài rất dài (626 giờ ≈ 26 ngày). | - Cần phân biệt rõ giữa `requested_study_window` (cửa sổ nghiên cứu giả định) và `actual_source_coverage` (thực tế vận hành).<br>- Đợt mất 626 giờ phải được rà soát kỹ tại Issue #6 (`reindex`) vì có thể là khoảng trống thời gian thực chứ không chỉ là nhiễu telemetry ngắn hạn. |

---

## 5. Phân Tích Hình Thái Khuyết Thiếu (Missingness Patterns)

### 5.1. Khuyết thiếu theo biến (Variable Dimension)
- **Khí tượng bề mặt:** 0.00% missing trên cả 6 thông số, phản ánh ưu thế chất lượng của mô hình tái phân tích ECMWF ERA5 được đồng hóa dữ liệu toàn cầu.
- **Chất lượng không khí:** Tỷ lệ khuyết thiếu rất thấp ($\text{PM}_{2.5}$: 2,53%; $\text{PM}_{10}$: 1,53%). 
- **Đặc điểm đồng khuyết thiếu:** Không có bất kỳ mốc giờ nào cả $\text{PM}_{2.5}$ và $\text{PM}_{10}$ đồng thời bị khuyết (`both_missing == 0`). Khi $\text{PM}_{2.5}$ bị khuyết (203 giờ), cảm biến $\text{PM}_{10}$ vẫn đo đạc bình thường; ngược lại khi $\text{PM}_{10}$ khuyết (123 giờ), $\text{PM}_{2.5}$ vẫn ghi nhận dữ liệu. Điều này tương thích với nhận định rằng hai kênh đo đạc hoạt động độc lập trên cùng một trạm; cần log kỹ thuật từ thiết bị để xác minh cấu hình phần cứng.

### 5.2. Khuyết thiếu theo thời gian (Temporal Dimension)
- **Chu kỳ ngày đêm (Diurnal Missing Pattern):**
  - Tỷ lệ thiếu $\text{PM}_{2.5}$ tập trung cao nhất vào ban đêm và rạng sáng: Khung giờ $00:00 - 04:00$ đạt từ **$3.80\%$ đến $4.79\%$** (đỉnh cao nhất tại $01:00$ với 16 giờ khuyết).
  - Tỷ lệ thiếu thấp nhất vào khung trưa và chiều: Khung giờ $10:00 - 17:00$ dao động từ **$0.60\%$ đến $1.80\%$** (thấp nhất tại $11:00$ với chỉ 2 giờ khuyết, tương đương $0.60\%$).
- **Phân bố theo tháng:**
  - Tháng 07/2025: $\text{PM}_{2.5}$ đạt $0.0\%$ missing, trong khi $\text{PM}_{10}$ khuyết 111 giờ ($17.87\%$) do cảm biến $\text{PM}_{10}$ hiệu chỉnh đầu chu kỳ.
  - Tháng 08/2025: $\text{PM}_{2.5}$ khuyết 41 giờ ($5.58\%$), xuất hiện đợt mất tín hiệu 23 giờ liên tục ngày 19/08/2025.
  - Tháng 06/2026: $\text{PM}_{2.5}$ khuyết 80 giờ ($19.95\%$), với các đợt gián đoạn ca đêm ngày 02/06 (9h), 06/06 (10h), và 07/06 (12h).
- **Phân bố độ dài các khối khuyết (Consecutive Missing Blocks):**
  - Tổng số đợt gián đoạn $\text{PM}_{2.5}$: **67 khối**.
  - **Khối đơn lẻ 1 giờ (Isolated 1-hour drops):** Chiếm đa số với **35 khối** (tương đương 52.2% tổng số đợt), tương thích với giả thuyết chẩn đoán về suy giảm truyền dẫn viễn thông tạm thời (telemetry packet drop hypothesis); chưa thể khẳng định nguyên nhân nhân quả khi chưa có log truyền dẫn thực tế từ trạm.
  - **Khối 2 giờ:** 9 đợt; **Khối 3 giờ:** 8 đợt; **Khối 4 giờ:** 4 đợt.
  - **Khối mất dữ liệu kéo dài (>6 giờ):** Chỉ có 7 đợt, dài nhất là đợt 23 giờ (19/08/2025) và 16 giờ (20/08/2025).

---

## 6. Chẩn Đoán Cơ Chế Khuyết Thiếu Theo Rubin (MCAR / MAR / MNAR)

Áp dụng khung lý thuyết khuyết thiếu kinh điển của Donald Rubin (1976), nhóm nghiên cứu đối chiếu các bằng chứng thực nghiệm:

### 6.1. Bằng chứng kiểm tra MCAR (Missing Completely at Random)
- **Mẫu hình quan sát (Observed Pattern):** Tồn tại 35 đợt mất dữ liệu đơn lẻ đúng 1 giờ (chiếm 52.2% tổng số đợt), xuất hiện rải rác trong các ngày không có hình thái thời tiết cực đoan.
- **Giả thuyết chẩn đoán (Diagnostic Hypothesis):** Đặc trưng này tương thích với hiện tượng sụt giảm truyền dẫn viễn thông tạm thời (telemetry packet drop hypothesis). *Lưu ý học thuật:* Đây là giả thuyết chẩn đoán dựa trên hình thái chuỗi thời gian quan sát được, không khẳng định là nguyên nhân nhân quả khi chưa có log truyền dẫn thực tế từ hệ thống trạm.
- **Hạn chế:** Tỷ lệ khuyết không phân bổ hoàn toàn đồng đều qua 24 giờ mà có xu hướng nhỉnh hơn về đêm, cho thấy MCAR thuần túy không thể giải thích toàn bộ chuỗi khuyết.

### 6.2. Bằng chứng kiểm tra MAR (Missing at Random)
- **Mẫu hình quan sát (Observed Pattern):** Tỷ lệ khuyết thiếu có tương quan rõ nét với biến thời gian (giờ trong ngày: đêm cao hơn trưa) và tháng trong năm (mùa mưa bão tháng 8/2025 và tháng 6/2026).
- **Phân tích với biến quan sát được:** Khi $\text{PM}_{2.5}$ bị khuyết, biến $\text{PM}_{10}$ vẫn quan sát được đầy đủ và có nồng độ trung bình là **$15.42\,\mu\text{g/m}^3$** (trung vị **$12.16\,\mu\text{g/m}^3$**), thấp hơn rất nhiều so với mức trung bình toàn chuỗi ($65.97\,\mu\text{g/m}^3$). Điều này cho thấy khuyết thiếu xảy ra chủ yếu vào các giai đoạn khí quyển sạch, rửa trôi sau mưa hoặc độ ẩm cao ban đêm, phụ thuộc vào các điều kiện quan sát được.

### 6.3. Bằng chứng kiểm tra MNAR (Missing Not at Random)
- **Khảo sát rủi ro:** Giả thuyết MNAR đối với bụi mịn thường là: nồng độ ô nhiễm quá cao ($>300\,\mu\text{g/m}^3$) làm nghẽn buồng đếm hạt hoặc tắc màng lọc quang học, khiến cảm biến dừng ghi nhận.
- **Bác bỏ giả thuyết cực đoan:** Bằng chứng thực nghiệm cho thấy trước và trong các khung giờ $\text{PM}_{2.5}$ bị khuyết, nồng độ $\text{PM}_{10}$ không hề tăng cao đột biến mà ngược lại rất thấp. Do đó, không có dấu hiệu cho thấy dữ liệu bị mất do ô nhiễm vượt ngưỡng thiết bị (sensor saturation). Tuy nhiên, không thể loại trừ khả năng cảm biến gặp lỗi đo do độ ẩm bão hòa quá cao mà bản thân thiết bị tự ngắt.

### 6.4. Tuyên bố minh bạch mức độ không chắc chắn (Uncertainty Declaration)
> [!CAUTION]
> **TUYÊN BỐ BẤT ĐỊNH (Uncertainty Declaration):**  
> Dữ liệu quan sát hiện tại **chưa đủ cơ sở thực nghiệm để khẳng định dứt khoát một cơ chế khuyết thiếu duy nhất** (*Observed data are insufficient to identify the missingness mechanism conclusively*).  
> Nguyên nhân kỹ thuật: Tập dữ liệu trạm quan trắc mặt đất 556 Nguyễn Văn Cừ mới được OpenAQ tích hợp lưu trữ từ tháng 07/2025, nên chuỗi đo vận hành là 2025-07 → 2026-07, **không** phủ được khung mục tiêu 2023–2024 của dự án. Tuy vậy, **hai chuỗi có giao thoa hoàn toàn**: `inner join` trên khóa `timestamp` cho ra 8.022 bản ghi với độ phủ 100,00% và không Row Explosion (xem `data/raw/metadata.json` → `collection_pipeline_execution.temporal_integration`).
>
> Vì vậy, khẳng định rằng "không thể kiểm định cơ chế khuyết thiếu vì thiếu giao thoa" là **không còn đúng**. Dữ liệu đủ điều kiện để chạy kiểm định hồi quy logistic giữa xác suất khuyết thiếu $\text{PM}_{2.5}$ và các biến khí tượng quan sát được; tuy nhiên Issue #5 **chưa** thực hiện kiểm định đó. Do đó cơ chế MCAR/MAR/MNAR ở §6 vẫn là **giả định chẩn đoán dựa trên mô tả hình thái**, chưa được kiểm định thống kê, và cần được thẩm định tại Issue #6 (hoặc Issue #7 khi dựng pipeline tích hợp).

---

## 7. Khảo Sát Chuỗi Số 0 Kéo Dài & Rà Soát Kẹt Cảm Biến (Prolonged Zero Audit)

Khung kiểm toán đã được nâng cấp theo chuẩn **timestamp-aware** và **station-aware**:
- **Timestamp-aware:** Kiểm tra khoảng cách lấy mẫu thực tế (3,600 giây). Bất kỳ khoảng trống thời gian (temporal gap) nào cũng sẽ tự động ngắt chuỗi số 0, ngăn ngừa việc gộp nhầm các dòng dữ liệu không liên tục thành streak kéo dài.
- **Station-aware:** Phân tách và đo lường chuỗi giá trị độc lập cho từng trạm quan trắc (`station_id`), tránh hiện tượng nối chuỗi dữ liệu xuyên trạm.

**Kết quả kiểm toán trên dữ liệu thực tế:**
- **Tập chất lượng không khí:**
  - Biến `pm25`: **0 lần xuất hiện giá trị 0.0** (min đo đạc thực tế là $1.06\,\mu\text{g/m}^3$). Chuỗi zero dài nhất là **0 giờ**.
  - Biến `pm10`: **0 lần xuất hiện giá trị 0.0** (min thực tế là $1.01\,\mu\text{g/m}^3$).
  - **Kết luận:** Trạm quan trắc chuẩn quốc gia 556 Nguyễn Văn Cừ không có bất kỳ hiện tượng trôi gốc về 0 (zero-drift) hay mất nguồn duy trì đường số 0 giả mạo nào.
- **Tập khí tượng bề mặt:**
  - Biến `precipitation`: Có 6.727 giờ có lượng mưa bằng $0.0\,\text{mm}$ (chiếm 74,15%). Chuỗi không mưa dài nhất kéo dài **275 giờ liên tục** (~11,5 ngày); có 252 đợt kéo dài trên 6 giờ. Đây là hiện tượng khí tượng tự nhiên bình thường trong mùa khô tại miền Bắc Việt Nam, không phải lỗi kỹ thuật.
  - Biến `wind_speed`: Có 10 giờ lặng gió ($0.0\,\text{m/s}$), chuỗi dài nhất là 2 giờ; không có đợt nào vượt ngưỡng 6 giờ.
- **Ghi chú chuyển giao Issue #6:** Không có trường hợp kẹt cảm biến nồng độ bụi ở mức 0. Bằng chứng định lượng này chuyển giao cho Issue #6 để rà soát thêm trường hợp nồng độ không đổi kéo dài quá 6 giờ ở các mức giá trị dương khác (stuck constant values).

---

## 8. Ứng Dụng Khung Lý Thuyết Chi Phí Chất Lượng (1–10–100 Cost of Quality)

Nguyên lý **1–10–100 Rule** (George Labovitz & Yu Sang Chang) chỉ ra rằng chi phí để phát hiện và ngăn chặn một lỗi chất lượng dữ liệu ở giai đoạn đầu luôn thấp hơn một bậc độ lớn so với chi phí sửa chữa ở các giai đoạn sau:

```text
┌─────────────────────────────────┐
│ CHI PHÍ PHÒNG NGỪA / AUDIT: $1   │  ◄── [ ISSUE #5: DATA QUALITY AUDIT ]
│ Phát hiện sớm 282 điểm đảo      │      Đo lường, định lượng 6 chiều, gắn cờ lỗi
│ nghịch, 1.022 giờ ngắt quãng    │      Chi phí thấp nhất, bảo toàn tính nguyên bản.
└─────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ CHI PHÍ SỬA LỖI / TIỀN XỬ LÝ: $10 │  ◄── [ ISSUE #6 & #7: CLEANING & PIPELINE ]
│ Reindex lưới 1h, chuyển nghịch  │      Nếu không audit sớm, bước tiền xử lý phải
│ đảo thành NaN, fit scaler train │      thực hiện mò mẫm, tốn công gấp 10 lần.
└─────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ CHI PHÍ THẤT BẠI MÔ HÌNH: $100  │  ◄── [ ISSUE #11 - #14: OLS & ALERT CLASSIFIER ]
│ Dự báo sai lệch, rò rỉ dữ liệu  │      Đưa dữ liệu vi phạm khí động học vào OLS
│ OLS suy diễn ngụy tạo, báo sai   │      gây kết luận sai lầm về mặt khoa học và chính sách.
└─────────────────────────────────┘
```

1. **Giai đoạn Kiểm toán Issue #5 (\$1):** Chỉ tốn chi phí tính toán đơn giản trên `data/interim/` để phát hiện ra 282 cặp giá trị nghịch đảo vật lý, 1.022 giờ gián đoạn chuỗi đo và xác nhận 100% không trùng lặp khóa.
2. **Giai đoạn Làm sạch Issue #6 (\$10):** Dựa trên bằng chứng định lượng từ Issue #5, kỹ sư dữ liệu chỉ cần áp dụng quy tắc tất định chính xác mà không phải tái thẩm định toàn bộ tập dữ liệu thô.
3. **Giai đoạn Huấn luyện & Cảnh báo (\$100):** Ngăn chặn triệt để nguy cơ mô hình OLS bị bóp méo hệ số hồi quy hoặc mô hình phân loại cảnh báo sớm (Early Alerting) đưa ra các dự báo giả mạo, bảo đảm liêm chính học thuật và độ tin cậy khoa học cao nhất theo chuẩn CMC University.

---

## 9. Kết Luận & Kế Hoạch Bàn Giao Kỹ Thuật (Handoff to Issue #6)

### 9.1. Tóm tắt kết quả kiểm toán
1. Toàn bộ dữ liệu Canonical tuân thủ nghiêm ngặt lược đồ giao diện `docs/data_dictionary.md`, không có duplicate records trên khóa quan trắc, không còn mã lỗi ngụy trang.
2. Dữ liệu khí tượng đạt chất lượng hoàn hảo (0% missing trên 9.072 giờ).
3. Dữ liệu chất lượng không khí đạt độ bao phủ cao (97.46% PM2.5 khả dụng), với tỷ lệ khuyết tập trung vào ban đêm và các đợt gián đoạn ngắn hạn.

### 9.2. Danh mục bàn giao kỹ thuật cho Issue #6 (Làm sạch tất định)
- **Handoff 1 (Xử lý nghịch đảo khí động học):** Cung cấp danh sách 282 bản ghi $\text{PM}_{2.5} > \text{PM}_{10} + 2.0\,\mu\text{g/m}^3$ để Issue #6 chuyển đổi thành `NaN`.
- **Handoff 2 (Reindex chuỗi thời gian liên tục):** Cung cấp thông số lưới 9.044 giờ để Issue #6 reindex độc lập theo trạm `VN001_HANOI_556_NGUYEN_VAN_CU`, bộc lộ 1.022 giờ thiếu và gắn cờ `pm25_was_missing = 1` cho các đợt mất tín hiệu $>6$ giờ.
- **Handoff 3 (Cảnh báo độ ẩm cao):** Gắn cờ `is_high_humidity_fog = 1` cho 2.843 giờ có $\text{RH} > 90\%$ để phân tích tán xạ quang học mà không xóa dòng.
- **Handoff 4 (Ghi nhật ký làm sạch):** Mọi thao tác làm sạch ở Issue #6 phải được ghi nhận đầy đủ vào [`docs/cleaning_log.md`](cleaning_log.md).
