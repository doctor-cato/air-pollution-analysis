# Thẩm Định Hồ Sơ Đa Nguồn & Quyết Định Nguồn Dữ Liệu
## Source Profiling & Decision Gate Report

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)  
> **Căn cứ kỹ thuật:** Lộ trình đồ án [`docs/roadmap.md`](roadmap.md), GitHub Issue #19 (Milestone 1), và phương pháp luận CRISP-DM.  
> **Tài liệu liên quan:** [`docs/data_dictionary.md`](data_dictionary.md), [`docs/research_questions.md`](research_questions.md).  
> **Trạng thái:** Hoàn tất thẩm định & Ban hành quyết định nguồn (Source Decision Gate).

---

## 1. Mục Tiêu (Objective)

Mục tiêu của Issue #19 là tiến hành khảo sát, thẩm định thực nghiệm (*data profiling*), kiểm chứng tính khả thi và so sánh khách quan các nguồn dữ liệu ứng viên cho bài toán phân tích chuỗi thời gian ô nhiễm bụi mịn $\text{PM}_{2.5}$ và các yếu tố khí tượng bề mặt tại khu vực Hà Nội.

Dựa trên bằng chứng có thể kiểm chứng từ API, metadata và mẫu dữ liệu thực tế, tài liệu này ban hành **Quyết định Cổng Nguồn Dữ liệu (Source Decision Gate)**, phân định rõ vai trò của từng nguồn (Primary, Secondary, Fallback, Reference, Unused). Đây là căn cứ kỹ thuật và pháp lý bắt buộc trước khi triển khai các pipeline thu thập dữ liệu tự động tại Issue #3 (Chất lượng không khí) và Issue #4 (Khí tượng bề mặt), bảo đảm tuân thủ nghiêm ngặt nguyên tắc: **Khảo sát hồ sơ trước $\to$ Ra quyết định nguồn $\to$ Triển khai adapter thu thập**.

---

## 2. Danh Mục Nguồn Ứng Viên (Candidate Sources)

Theo danh mục định hướng tại `docs/roadmap.md` được mở rộng qua thực nghiệm profiling, **6 nguồn dữ liệu ứng viên** được đưa vào thẩm định:

1. **Tập dữ liệu Kaggle Hà Nội (Kaggle Community Datasets):** Các file CSV nén do cộng đồng nghiên cứu đăng tải trên Kaggle (ví dụ: *Hanoi Air Quality PM2.5 + Weather Data 2024–2026*, *AQI in Hanoi 2022–2025*).
2. **OpenAQ REST API v3:** Nền tảng dữ liệu chất lượng không khí mở toàn cầu, lưu trữ dữ liệu từ các trạm quan trắc chuẩn quy chiếu (FEM/FRM) của chính phủ và các tổ chức quốc tế (`https://api.openaq.org/v3`). Dữ liệu lịch sử truy xuất công khai qua kho lưu trữ S3 (`openaq-data-archive.s3.amazonaws.com`).
3. **Open-Meteo Historical Weather API (ERA5 Reanalysis):** Nền tảng cung cấp dữ liệu khí quyển tái phân tích toàn cầu ECMWF ERA5 và ERA5-Land theo tọa độ lưới với độ phân giải theo giờ (`https://archive-api.open-meteo.com/v1/archive`).
4. **AirNow / US Department of State Historical CSV:** Kho lưu trữ tệp dữ liệu lịch sử quan trắc $\text{PM}_{2.5}$ từ trạm quan trắc của Đại sứ quán Hoa Kỳ tại Hà Nội do Cơ quan Bảo vệ Môi sinh Hoa Kỳ (US EPA) và Bộ Ngoại giao Hoa Kỳ (DOS) quản lý.
5. **PAM Air Portal:** Mạng lưới trạm quan trắc IoT cảm biến quang học chi phí thấp do Công ty Cổ phần Tư vấn và Tích hợp Công nghệ D&L phát triển tại Việt Nam (`https://pamair.org`).
6. **NOAA Integrated Surface Database (ISD) – Trạm WMO 48820 (Sân bay Quốc tế Nội Bài):** Cơ sở dữ liệu khí tượng bề mặt tích hợp toàn cầu của Trung tâm Dữ liệu Khí hậu Quốc gia Hoa Kỳ (NCEI/NOAA), lưu trữ báo cáo METAR (FM-15) từ trạm khí tượng hàng không WMO 48820 (Nội Bài, Hà Nội) (`https://www.ncei.noaa.gov/data/global-hourly/`).

---

## 3. Phương Pháp Khảo Sát (Profiling Methodology)

Quá trình thẩm định tuân thủ các nguyên tắc liêm chính học thuật và quản trị dữ liệu:
- **Kiểm chứng trực tiếp:** Truy vấn metadata, tài liệu kỹ thuật chính thức và gửi các request kiểm tra mẫu trực tiếp tới các endpoint API công khai.
- **Không suy đoán chủ quan:** Mọi thông tin về tọa độ, dải thời gian, kiểu dữ liệu, giấy phép bản quyền đều dẫn xuất từ tài liệu kỹ thuật hoặc phản hồi API thực tế. Các nguồn không thể truy cập công khai được ghi nhận trung thực là `Not verified` hoặc `Unable to verify directly`.
- **Bảo toàn dữ liệu thô:** Quá trình thẩm định không ghi đè, không sửa đổi bất kỳ tệp dữ liệu nào trong `data/raw/` và không tạo dữ liệu giả lập.
- **Không over-engineering:** Không triển khai pipeline thu thập hoàn chỉnh hay bước làm sạch chuyên sâu trong Issue #19; chỉ tập trung vào hồ sơ dữ liệu (*data profile*) và quyết định nguồn.

---

## 3b. Profiling Metrics Thực Nghiệm (Empirical Profiling Metrics)

> [!CAUTION]
> **THÔNG BÁO ĐÍNH CHÍNH & THU HỒI DỮ LIỆU ĐỊA LÝ TRẠM OPENAQ (Correction & Retraction Notice):**  
> Trong các bản thảo ban đầu của Issue #19, trạm OpenAQ với `location_id = 2178` được gán nhãn là *"US Diplomatic Post: Hanoi"*. Tuy nhiên, qua rà soát và kiểm chứng kỹ thuật chuyên sâu đối với payload thô từ kho lưu trữ S3 (`s3://openaq-data-archive/records/csv.gz/locationid=2178/`), chúng tôi phát hiện bản ghi thực tế chứa:  
> ```csv
> 2178,3919,Del Norte-2178,2023-01-01T01:00:00-07:00,35.1353,-106.584702,pm10,µg/m³,45.0
> ```  
> Trạm `location_id = 2178` thực chất là trạm **Del Norte High School tại Thành phố Albuquerque, Bang New Mexico, Hoa Kỳ** (tọa độ $35.1353^\circ\text{N}, -106.5847^\circ\text{W}$, múi giờ `America/Denver` UTC-07:00), được sao chép nhầm từ mã ví dụ trong tài liệu hướng dẫn OpenAQ Developer Documentation.  
> Toàn bộ các chỉ số profiling sơ bộ trước đây gắn với location 2178 (bao gồm 14,424 dòng đo PM2.5 giai đoạn 2023–2024, 6,049 dòng năm 2023, 8,375 dòng năm 2024, độ đầy đủ 82.2%) hoàn toàn là dữ liệu tại Mỹ và **CHÍNH THỨC BỊ THU HỒI, LOẠI BỎ (DISQUALIFIED & RETRACTED)** khỏi bài toán chất lượng không khí Hà Nội.  
> 
> **Xác minh trạm OpenAQ chuẩn quy chuẩn thực tế tại Hà Nội:**  
> Đã xác minh thực nghiệm trạm quan trắc chuẩn quốc gia của Việt Nam trên OpenAQ:  
> - **Mã trạm (Location ID):** `4946811`  
> - **Tên trạm:** `"556 Nguyễn Văn Cừ"` (quận Long Biên, Hà Nội)  
> - **Tọa độ:** $21.0491^\circ\text{N}, 105.8831^\circ\text{E}$ (nằm trọn vẹn trong Bounding Box Hà Nội)  
> - **Đơn vị chủ quản:** Trung tâm Quan trắc Môi trường miền Bắc (NCEM / Cục Kiểm soát ô nhiễm môi trường - VEA) thông qua mạng lưới *Hanoi Air Quality Monitoring Network* (Provider ID: `67`).  
> - **Cảm biến & thông số:** Cung cấp đầy đủ 6 thông số chuẩn: `pm25` (Sensor ID `13502150`), `pm10` (Sensor ID `13502165`), `no2` (`13502159`), `co` (`13502158`), `so2` (`13502161`), `o3` (`13502160`).  
> - **Hồ sơ lưu trữ thực tế trên S3:** Hiện diện **352 tệp CSV.gz** từ ngày **`2025-07-03T15:40:00Z`** (`2025-07-03T22:40:00+07:00`) đến **`2026-07-15T10:05:00Z`** (`2026-07-15T17:05:00+07:00`). OpenAQ không lưu trữ dữ liệu giai đoạn 2023–2024 cho trạm này (0 tệp trong 2023–2024 do OpenAQ mới tích hợp nhà cung cấp từ tháng 7/2025).  
> - **Hệ quả kiến trúc nguồn:** Đối với dữ liệu lịch sử cửa sổ 2023, đồ án sử dụng **AirNow DOS Historical CSV** (Site: Hanoi, Đại sứ quán Hoa Kỳ, thiết bị Met One BAM-1020 chuẩn US EPA FEM) làm nguồn chuẩn lịch sử chính. Trạm OpenAQ `4946811` đóng vai trò nguồn chuẩn quy chuẩn quốc gia hiện hành và kiểm chuẩn đa thông số.

> [!IMPORTANT]
> Toàn bộ số liệu trong bảng dưới đây thu thập bằng script Python gọi API/tải file trực tiếp tại thời điểm profiling **`2026-09-28T16:47:26Z` đến `2026-09-29T07:15:00Z` (UTC)**.
>
> **Cơ chế tái lập hiện hành:** các script profiling thời điểm đó nằm trong thư mục làm việc cục bộ `scratch/` và **không** được commit vào repository. Vì vậy con số trong bảng này được xác minh lại theo đường tái tạo chính thức của dự án: `python scripts/fetch_dataset.py` tải lại tập dữ liệu từ nguồn công khai rồi đối chiếu nội dung với `data/raw/metadata.json` (xem `README.md` §4 và `docs/roadmap.md` §3.2). Do bucket OpenAQ S3 là kho sống và Parquet không tái lập được theo byte, đối chiếu thực hiện trên **số bản ghi, dải thời gian và độ phủ giao thoa** thay vì mã băm byte.  
> Đối với các nguồn không hỗ trợ API mở hoặc file công khai (Kaggle, PAM Air, AirNow), báo cáo nêu rõ căn cứ kỹ thuật và lý do không thể trích xuất tự động thay vì phỏng đoán.

| Chỉ tiêu profiling | OpenAQ (S3 Archive, loc=4946811 - 556 Nguyễn Văn Cừ) | Open-Meteo ERA5 | NOAA ISD (Station 48820099999) | AirNow DOS Historical | Kaggle Hanoi Datasets | PAM Air Portal |
|---|---|---|---|---|---|---|
| **Vai trò theo Quyết định** | **Primary (Current/Operational Air Quality)** | **Primary (Weather)** | **Fallback (Weather)** | **Primary (Historical 2023 Air Quality) / Fallback** | **Reference Only** | **Unused** |
| **Số dòng 2023 (toàn bộ params)** | **0** (Chưa tích hợp trên OpenAQ giai đoạn 2023) | Không áp dụng | 17,178 | Not verifiable directly (chưa có tệp mở 2023 trực tiếp không login) | Not verifiable directly (tệp cá nhân, không có schema chuẩn) | Not verifiable directly (API đóng, không công khai) |
| **Số dòng 2023 (pm25)** | **0** (dùng AirNow DOS CSV làm ground truth lịch sử) | Không có biến ô nhiễm | Không có biến ô nhiễm | Not verifiable directly (chưa có tệp mở 2023 trực tiếp không login) | Not verifiable directly (thay đổi theo từng file upload) | Not verifiable directly (API đóng, không thể tải qua script mở) |
| **Số dòng 2023 (khí tượng)** | Không có biến khí tượng | **8,760** (1h continuous) | 17,178 (METAR ~30m) | Không có biến khí tượng | Not verifiable directly (file ghép ngoài tùy tác giả) | Not verifiable directly (API đóng) |
| **Số dòng 2024 (toàn bộ params)** | **0** (Chưa tích hợp trên OpenAQ giai đoạn 2024) | Không áp dụng | 16,704 | Not verifiable directly (không có file mở trực tiếp 2024) | Not verifiable directly (thay đổi theo từng file upload) | Not verifiable directly (API đóng) |
| **Số dòng 2024 (pm25)** | **0** (chưa có dữ liệu OpenAQ 2024) | Không có biến ô nhiễm | Không có biến ô nhiễm | Not verifiable directly (đòi hỏi tài khoản tổ chức AirNow-Tech) | Not verifiable directly (thay đổi theo từng file upload) | Not verifiable directly (API đóng) |
| **Số dòng 2024 (khí tượng)** | Không có biến khí tượng | **8,784** (1h continuous) | 16,704 (METAR ~30m) | Không có biến khí tượng | Not verifiable directly (file ghép ngoài tùy tác giả) | Not verifiable directly (API đóng) |
| **Tổng quan trắc pm25 (2023–2024)** | **0** dòng trên OpenAQ (Tổng 352 files S3 trong 2025–2026, ~77,000 obs pm25) | Không áp dụng | Không áp dụng | Not verifiable directly (không đủ 2 năm mở trực tiếp) | Not verifiable directly (không kiểm chứng được gốc) | Not verifiable directly (API đóng) |
| **Tổng quan trắc khí tượng (2023–2024)** | Không áp dụng | **17,544** dòng liên tục | **33,882** bản ghi (~30m) | Không áp dụng | Not verifiable directly (không kiểm chứng được gốc) | Not verifiable directly (API đóng) |
| **Số cột / cấu trúc trường** | 9 cột (flat CSV: location_id, sensors_id, location, datetime, lat, lon, parameter, units, value) | 7 trường (1 thời gian + 6 biến) | 30 cột chuẩn ISD | Documented: 11 cột (định dạng US DOS tiêu chuẩn) | Not verifiable directly (không chuẩn hóa, dao động 5–12 cột) | Documented: JSON nội bộ (API đóng) |
| **min_timestamp (cửa sổ nghiên cứu)** | 2025-07-03T22:40:00+07:00 (mốc đầu tiên trên S3) | 2023-01-01T00:00:00+07:00 | 2023-01-01T00:00:00+07:00 | Documented: 2016-01-01 (thời điểm trạm bắt đầu) | Not verifiable directly (phụ thuộc tác giả upload) | Documented: ~2019 (theo thông tin nhà cung cấp) |
| **max_timestamp (cửa sổ nghiên cứu)** | 2026-07-15T17:05:00+07:00 (mốc mới nhất trên S3) | 2024-12-31T23:00:00+07:00 | 2024-12-31T23:30:00+07:00 | Documented: 2023-12-31 (bản mở công khai cuối) | Not verifiable directly (phụ thuộc tác giả upload) | Provider-reported: Thời gian thực (chỉ qua Web GUI) |
| **latest_available_timestamp (tại profiling)** | **2026-07-15T17:05:00+07:00** (file S3 mới nhất) | **2026-09-24T06:00** (ERA5 Reanalysis thuần túy, trễ ~5 ngày) | **2025-12-31** (2026 chưa ra) | Documented: 2023-12-31 (kho lưu trữ mở) | Not verifiable directly (phụ thuộc tác giả upload) | Provider-reported: Thời gian thực (chỉ xem trên Web GUI) |
| **Sampling frequency** | Sub-hourly telemetry (~5-10m) / Hourly aggregated (~220 obs/ngày/param) | 1 giờ (cố định - đo trực tiếp) | ~30 phút (METAR FM-15 - đo trực tiếp) | Documented: 1 giờ (theo quy chuẩn US DOS) | Documented: 1 giờ (file tổng hợp sẵn) | Documented: 5–15 phút (theo thông số cảm biến IoT) |
| **Missing rate pm25 (2023)** | **100% missing trên OpenAQ** (dùng AirNow DOS CSV) | Không áp dụng | Không áp dụng | Not verifiable directly (chưa có tệp mở 2023 trực tiếp) | Not verifiable directly (đã bị điền khuyết nhân tạo từ trước) | Not verifiable directly (API đóng) |
| **Missing rate pm25 (2024)** | **100% missing trên OpenAQ** | Không áp dụng | Không áp dụng | Not verifiable directly (không có file công khai 2024) | Not verifiable directly (đã bị điền khuyết nhân tạo từ trước) | Not verifiable directly (API đóng) |
| **Missing rate tổng hợp pm25 (2-year)** | **Không khả dụng trên OpenAQ cho 2023–2024** | Không áp dụng | Không áp dụng | Not verifiable directly (không đủ 2 năm công khai) | Not verifiable directly (không thể xác định tỷ lệ gốc) | Not verifiable directly (API đóng) |
| **Missing rate nhiệt độ (2023)** | Không có biến nhiệt độ | **0/8,760 = 0.00%** | **0/17,178 = 0.00%** (TMP) | Không có biến nhiệt độ | Not verifiable directly (đã tiền xử lý/impute ngoài) | Not verifiable directly (API đóng) |
| **Missing rate áp suất (2023)** | Không có biến áp suất | **0/8,760 = 0.00%** | **0/17,178 = 0.00%** (SLP) | Không có biến áp suất | Not verifiable directly (không có hoặc đã bị impute) | Not verifiable directly (không có trên hầu hết nốt IoT) |
| **Missing rate 6 biến khí tượng** | Không áp dụng | **0.00% trên toàn bộ 6 biến** | Thiếu precipitation & surface_pressure | Không áp dụng | Not verifiable directly (tùy tác giả, rủi ro rò rỉ cao) | Not verifiable directly (thiếu thông số gió và áp suất bề mặt) |
| **Duplicate records** | 0 (trên S3 daily files) | **0** (lưới đồng nhất 1h) | Cần deduplicate khi resample | Not verifiable directly (chưa tải tệp thô để verify) | Not verifiable directly (tùy tệp, thường đã bị deduplicate ngoài) | Not verifiable directly (API đóng) |
| **Xác thực trạm/vị trí Hà Nội** | ✅ location_id=4946811 ($21.0491^\circ\text{N}, 105.8831^\circ\text{E}$ - Trạm chuẩn 556 Nguyễn Văn Cừ, Long Biên) | ✅ Điểm lưới $21.0545^\circ\text{N}, 105.8985^\circ\text{E}$ | ✅ WMO 48820 ($21.2212^\circ\text{N}, 105.8072^\circ\text{E}$) | Documented: Trạm ĐSQ Hoa Kỳ tại Hà Nội ($21.0215^\circ\text{N}, 105.8184^\circ\text{E}$) | Not verifiable directly (thiếu metadata trạm và tọa độ gốc) | Documented: Mạng lưới nốt IoT nội thành (thiếu kiểm định FEM) |
| **Thông số thực tế ghi nhận** | `pm25`, `pm10`, `no2`, `co`, `so2`, `o3` (6 thông số chuẩn trạm QG) | `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `precipitation`, `surface_pressure` | `WND`, `TMP`, `DEW`, `SLP`, `CIG`, `VIS` (thiếu lượng mưa chuẩn) | Documented: `pm25` | Not verifiable directly (`pm25`, khí tượng ghép ngoài tùy file) | Documented: `pm25`, `pm10`, `aqi` (nhiệt/ẩm tùy nốt) |
| **Endpoint truy xuất** | `s3://openaq-data-archive/records/csv.gz/locationid=4946811/` | `https://archive-api.open-meteo.com/v1/archive` | `https://www.ncei.noaa.gov/data/global-hourly/access/{yr}/48820099999.csv` | Trang tải US DOS / AirNow | Kaggle API / Web download | Web/App GUI `pamair.org` |
| **Phương thức xác thực** | S3: **Không cần key**; REST: Cần API key | **Không cần key** (CC BY 4.0) | **Không cần key** (Public Domain) | Hạn chế (cần login đối tác) | Cần tài khoản cá nhân Kaggle | **Đóng** (cần hợp đồng thương mại) |

### 3c. Giải Trình Kỹ Thuật Chi Tiết Từng Ứng Viên (Candidate Source Profiling Analysis)

1. **OpenAQ (Location 4946811 – 556 Nguyễn Văn Cừ, Long Biên, Hà Nội):**
   - *Đính chính & Thu hồi Location 2178:* Qua kiểm chứng chuyên sâu, location 2178 (Del Norte, Albuquerque, NM, USA) hoàn toàn nằm ngoài Việt Nam và đã bị thu hồi/loại bỏ 100%. Trạm OpenAQ hợp thức duy nhất tại Hà Nội là location 4946811.
   - *Hồ sơ dữ liệu thực tế:* Xác nhận qua 352 tệp CSV.gz tải từ S3 archive: trạm bắt đầu ghi nhận từ ngày `2025-07-03T15:40:00Z` đến `2026-07-15T10:05:00Z` (180 tệp năm 2025, 172 tệp năm 2026). Dữ liệu dạng sub-hourly telemetry (~5-10 phút/lần đo), đạt trung bình ~220 quan sát/ngày đối với `pm25` (Sensor 13502150) và ~221 quan sát/ngày đối với `pm10` (Sensor 13502165).
   - *Đa dạng thông số chuẩn:* Cung cấp trọn bộ 6 thông số quan trắc chuẩn quốc gia: `pm25`, `pm10`, `no2`, `co`, `so2`, `o3` do Trung tâm Quan trắc Môi trường miền Bắc (NCEM / VEA) vận hành.
   - *Phân định vai trò nghiên cứu:* Do OpenAQ chỉ tích hợp trạm này từ tháng 7/2025, đối với nghiên cứu lịch sử (cửa sổ 2023), nguồn AirNow DOS CSV (trạm BAM-1020 của ĐSQ Hoa Kỳ) đảm nhiệm vai trò ground truth lịch sử chính. Trạm OpenAQ 4946811 đóng vai trò trạm chuẩn quốc gia hiện hành và kiểm chuẩn chéo đa thông số.

2. **Open-Meteo Historical Weather API (ERA5 Reanalysis):**
   - *Tính toàn vẹn thực nghiệm:* Xác nhận qua truy vấn API thực tế: $17.544$ mốc thời gian liên tục ($8.760$ giờ năm 2023 + $8.784$ giờ năm 2024), **$0{,}00\%$ missing** trên toàn bộ 6 biến số khí tượng.
   - *Độ trễ và latest_available_timestamp:* Khi truy vấn mô hình tái phân tích ERA5 thuần túy (`models=era5`), mốc thời gian mới nhất ghi nhận tại thời điểm profiling là **`2026-09-24T06:00:00+07:00`** (độ trễ cố hữu $\approx 5$ ngày do chu trình đồng hóa khí quyển toàn cầu của ECMWF). Điều này hoàn toàn không ảnh hưởng tới cửa sổ nghiên cứu 2023–2024 của đồ án (đã hoàn tất $100\%$).
   - *Độ lệch lưới tối ưu:* Lưới ERA5 ($0{,}25^\circ \approx 25\text{ km}$) khớp điểm lưới $21.0545^\circ\text{N}, 105.8985^\circ\text{E}$, cách trạm OpenAQ 4946811 ($21.0491^\circ\text{N}, 105.8831^\circ\text{E}$) chỉ **$1{,}7\text{ km}$** về phía Đông Bắc (giảm mạnh so với cự ly 8.7 km tới trạm ĐSQ tại Ba Đình). Cự ly 1.7 km bảo đảm tính đại diện khí hậu bề mặt ở mức rất cao.

3. **NOAA Integrated Surface Database (ISD – Trạm WMO 48820 Nội Bài):**
   - *Tính sẵn sàng thực tế:* File năm 2023 có $17.178$ bản ghi ($365/365$ ngày có dữ liệu, trung bình $47{,}1$ quan sát/ngày); file năm 2024 có $16.704$ bản ghi ($359/366$ ngày, khuyết 7 ngày). Nhiệt độ khô (`TMP`) và áp suất mực biển (`SLP`) đạt $0{,}00\%$ missing trong năm 2023.
   - *Giới hạn khiến xếp làm Fallback:* Trạm METAR sân bay thiếu hẳn trường đo lượng mưa liên tục (`precipitation` không xuất hiện trong trường AA1/AA2 của đa số bản ghi); trường áp suất bề mặt (`surface_pressure`) không đo trực tiếp mà chỉ có áp suất mực biển (`SLP`); tần suất quan sát $\approx 30$ phút đòi hỏi phải resample; khoảng cách $\approx 22\text{ km}$ về phía Bắc khiến vi khí hậu có độ lệch nhất định so với vùng lõi đô thị.

4. **AirNow (US Department of State Historical CSV):**
   - *Hiện trạng truy cập:* Dữ liệu xuất phát từ trạm BAM-1020 của ĐSQ Hoa Kỳ tại Hà Nội. Các tệp mở công khai trực tiếp hiện cung cấp đến hết ngày **31/12/2023**. Do trạm OpenAQ Hà Nội (4946811) chỉ bắt đầu lưu trữ từ 2025, AirNow DOS CSV chính là nguồn chuẩn lịch sử duy nhất cho năm 2023 có đầy đủ chuỗi đo PM2.5 đạt chuẩn US EPA FEM tại Hà Nội.
   - *Missing ngụy trang:* Dữ liệu sử dụng marker `-999` cho các khung giờ mất tín hiệu. Xếp làm nguồn dữ liệu chuẩn lịch sử (*Primary Historical Source*) cho giai đoạn 2023 và nguồn dự phòng (*Fallback Source*).

5. **Tập dữ liệu Kaggle Hà Nội (Community Datasets):**
   - *Lý do không thể trích xuất metric khách quan:* Các tập dữ liệu trên Kaggle do các cá nhân đăng tải không độc lập và không đồng nhất (kích thước và số dòng thay đổi tùy tác giả từ vài nghìn đến vài chục nghìn dòng). Phần lớn các tệp đã bị tiền xử lý (loại bỏ duplicate, tự ý điền khuyết bằng trung bình/nội suy), làm biến mất các thông số missing rate và phân phối tự nhiên ban đầu (biểu kiến 0% missing phản ánh phép điền khuyết nhân tạo chứ không phải quan trắc thực tế). Nguy cơ rò rỉ dữ liệu (*Data Leakage*) từ các feature trễ tạo sẵn là rất cao. Do đó các metric sơ cấp ghi nhận là *Not verifiable directly*. Chỉ giữ vai trò tham chiếu phân phối thống kê ngoài (*Reference only*).

6. **PAM Air Portal:**
   - *Lý do không trích xuất được metrics qua script:* Mạng lưới cảm biến IoT của D&L không mở REST API cho cộng đồng tải dữ liệu thô hàng loạt (`bulk export`). Mọi truy xuất API đòi hỏi token đối tác trả phí. Việc không thể kiểm chứng định lượng độc lập qua script tự động là rào cản kỹ thuật khiến nguồn này bị xếp vào nhóm loại bỏ (*Unused*).

---

## 4. Độ Bao Phủ Địa Lý & Metadata Trạm (Geographic Coverage)

| Nguồn ứng viên | Tọa độ xác định | Metadata trạm | Phạm vi thực tế tại Hà Nội | Đánh giá địa lý |
|---|---|---|---|---|
| **1. Kaggle Datasets** | Thường chỉ ghi `Hanoi` tổng quát, một số tệp ghi tọa độ tâm thành phố ($21.0285^\circ\text{N}, 105.8542^\circ\text{E}$). | Không có thông tin số hiệu cảm biến (*serial*), chiều cao ống nạp khí (*inlet height*), hoặc quy chuẩn kiểm định. | Dữ liệu gộp cho toàn địa bàn hoặc trích xuất từ 1 trạm đơn nhưng thiếu hồ sơ trạm chuẩn hóa. | **Trung bình:** Không xác định rõ vị trí vật lý cụ thể của thiết bị thu thập ban đầu. |
| **2. OpenAQ REST API v3** | Xác định chính xác: location_id=4946811 ($21.0491^\circ\text{N}, 105.8831^\circ\text{E}$). Trạm 556 Nguyễn Văn Cừ, quận Long Biên, Hà Nội. *(Đính chính: location 2178 tại Albuquerque, Hoa Kỳ đã bị loại bỏ)*. | Đầy đủ: `locationId=4946811`, tên trạm (`"556 Nguyễn Văn Cừ"`), đơn vị chủ quản: Trung tâm Quan trắc Môi trường miền Bắc (NCEM / VEA), Provider ID: 67 (Hanoi Air Quality Monitoring Network). | Trạm mặt đất cố định nằm tại quận Long Biên, Hà Nội, đại diện môi trường không khí đô thị trung tâm ven sông Hồng. | **Rất tốt:** Tọa độ rõ ràng, trạm chuẩn quốc gia của cơ quan quản lý môi trường Việt Nam, cách điểm lưới ERA5 chỉ 1.7 km. |
| **3. Open-Meteo ERA5** | Điểm lưới thực tế (xác nhận từ API response): $21.05448^\circ\text{N}, 105.89848^\circ\text{E}$, độ cao $19.0\,\text{m}$. | Cung cấp đầy đủ metadata lưới: tọa độ, elevation, timezone, utc_offset_seconds=25200. | Bao phủ toàn bộ khu vực địa lý Hà Nội với lưới khí quyển đồng nhất $0.25^\circ \times 0.25^\circ$ ($\approx 25\,\text{km}$). | **Rất tốt:** Tính toán khí quyển đồng bộ, cách trạm OpenAQ 4946811 chỉ 1.7 km. |
| **4. AirNow DOS CSV** | Trạm Đại sứ quán Hoa Kỳ tại Hà Nội (`Site: Hanoi`, $21.0215^\circ\text{N}, 105.8184^\circ\text{E}$). | Có mã site (`Hanoi`), tên thiết bị (`PM2.5 - Central`, Met One BAM-1020), cơ quan quản lý (US DOS / EPA). | Đặt tại Đại sứ quán Hoa Kỳ, Láng Hạ, Đống Đa / Ba Đình, Hà Nội. | **Tốt:** Đúng trạm mặt đất chuẩn quy chiếu US EPA FEM tại Hà Nội. |
| **5. PAM Air Portal** | Mạng lưới nhiều trạm phân bố khắp các quận/huyện Hà Nội (Cầu Giấy, Hoàn Kiếm, Thanh Xuân, Gia Lâm...). | Có tên địa điểm, tọa độ từng điểm cảm biến IoT, nhưng metadata thiết bị thuộc sở hữu riêng của D&L. | Độ bao phủ không gian dày đặc nhất trong các nguồn. | **Rất tốt về mật độ không gian**, nhưng thiếu chứng nhận kiểm định trạm chuẩn quy chuẩn quốc gia. |
| **6. NOAA ISD 48820** | Xác nhận trực tiếp từ file: `"NOIBAI INTERNATIONAL, VM"`, lat=$21.221192^\circ\text{N}$, lon=$105.807178^\circ\text{E}$, elevation=11.88m. | Mã WMO=48820, WBAN=99999, Report type FM-15 (METAR), trạm khí tượng hàng không sân bay Nội Bài. | Sân bay Nội Bài nằm cách trung tâm đô thị Hà Nội khoảng **20–25 km về phía Bắc**, môi trường ven thành thị, không đại diện cho vi khí hậu lõi đô thị. | **Tốt nhưng lệch địa lý:** Là nguồn thực đo mặt đất, nhưng khoảng cách 20km có thể tạo ra sai số vi khí hậu đáng kể so với vị trí trạm PM2.5 nội thành. |

---

### 4.1. Quy Tắc Xác Thực Địa Lý & Lọc Phạm Vi Hà Nội (Hanoi Geographic Validation & Spatial Filtering Rules)

Để đảm bảo toàn bộ dữ liệu đưa vào Canonical Schema thực sự phản ánh môi trường không khí và thời tiết tại Hà Nội, các quy tắc xác thực không gian sau được xác lập cho các pipeline thu thập:

1. **Khung Ranh Giới Địa Lý Chuẩn Hà Nội (Hanoi Bounding Box):**
   Mọi trạm quan trắc hoặc điểm trích xuất bắt buộc phải nằm trong giới hạn hình học của Thành phố Hà Nội:
   $$\text{Latitude} \in [20.50^\circ\text{N},\, 21.60^\circ\text{N}], \quad \text{Longitude} \in [105.30^\circ\text{E},\, 106.10^\circ\text{E}]$$

2. **Quy tắc xác thực nguồn Trạm Mặt Đất (Point / Station Sources - OpenAQ, AirNow):**
   - **Xác thực định danh:** Bản ghi phải có `location_id == 4946811` (đối với OpenAQ) hoặc `Site == "Hanoi"` (đối với AirNow). **Tuyệt đối loại bỏ bản ghi có `location_id == 2178` (Del Norte, Albuquerque, NM, Hoa Kỳ: $35.1353^\circ\text{N}, -106.5847^\circ\text{W}$).**
   - **Xác thực tọa độ:** Tọa độ ghi nhận của OpenAQ 4946811 ($21.0491^\circ\text{N}, 105.8831^\circ\text{E}$) hoặc AirNow ($21.0215^\circ\text{N}, 105.8184^\circ\text{E}$) nằm trọn vẹn trong vùng đô thị Hà Nội.
   - **Rule xử lý ngoại lai & Bảo toàn dữ liệu thô:** toàn bộ tệp payload tải về từ nguồn được lưu **nguyên trạng** (không chỉnh sửa thủ công, không chuyển đổi giá trị trước khi lưu) trong `data/raw/`; mã băm SHA-256 của từng tệp thô được ghi lại trong `data/raw/metadata.json` để kiểm chứng tính toàn vẹn. Quy tắc lọc không gian (*Spatial Filtering*) được áp dụng tại bước tiền xử lý / chuẩn hóa dữ liệu (*normalization step*): adapter loại bỏ (*drop*) các bản ghi có tọa độ nằm ngoài Bounding Box Hà Nội hoặc có `location_id == 2178` trước khi đưa vào `data/interim/` và Canonical Schema.

3. **Quy tắc xác thực nguồn Dữ Liệu Lưới Khí Tượng (Grid-based Sources - Open-Meteo ERA5):**
   - **Tọa độ truy vấn mục tiêu:** Gửi request tại tọa độ trung tâm lõi Hà Nội: $\text{lat}=21.0285^\circ\text{N}, \text{lon}=105.8542^\circ\text{E}$.
   - **Xác thực điểm lưới phản hồi:** API trả về điểm lưới tính toán gần nhất: $\text{lat}=21.05448^\circ\text{N}, \text{lon}=105.89848^\circ\text{E}$ ($19.0\,\text{m}$ elevation). Điểm này nằm trong quận Long Biên/Gia Lâm thuộc Hà Nội, cách trạm OpenAQ 4946811 (556 Nguyễn Văn Cừ) chỉ **$\approx 1.7\,\text{km}$** và cách trạm ĐSQ Hoa Kỳ $\approx 8.7\,\text{km}$. Khoảng cách $1.7\,\text{km}$ hoàn toàn nằm trong bán kính ảnh hưởng đồng nhất của lưới khí tượng $0.25^\circ \times 0.25^\circ$.

4. **Quy tắc xác thực trạm Khí Tượng Dự Phòng (NOAA ISD / WMO 48820):**
   - **Tọa độ trạm:** Trạm WMO 48820 đặt tại Sân bay Quốc tế Nội Bài ($21.221192^\circ\text{N}, 105.807178^\circ\text{E}$), thuộc huyện Sóc Sơn, Thành phố Hà Nội.
   - **Đánh giá ranh giới:** Trạm nằm hoàn toàn trong địa giới hành chính Hà Nội và Bounding Box chuẩn. Tuy nhiên, do khoảng cách $\approx 22\,\text{km}$ về phía Bắc so với trạm đo ô nhiễm lõi đô thị, trạm chỉ được phê duyệt làm **Nguồn Dự Phòng / Thay Thế (Weather Fallback Source)** kèm cảnh báo về sai số vi khí hậu.

---

## 5. Độ Bao Phủ Thời Gian Thực Tế & Tần Suất (Temporal Coverage)

> Các mốc thời gian được đo đạc trực tiếp từ phản hồi API và tệp thực tế tại thời điểm profiling (`2026-09-28/29` UTC).

| Nguồn ứng viên | min_timestamp (Cửa sổ) | max_timestamp (Cửa sổ) | latest_available_timestamp (Profiling) | Tần suất đo | Hourly? | Đánh giá khoảng trống (Temporal Gaps) |
|---|---|---|---|---|---|---|
| **1. Kaggle Datasets** | Not verifiable directly (phụ thuộc uploader) | Not verifiable directly (phụ thuộc uploader) | Not verifiable directly (phụ thuộc uploader) | Documented: 1 giờ (ghép sẵn) | Documented: Có | Not verifiable directly (đã bị điền khuyết nhân tạo, không thể xác định khoảng trống gốc) |
| **2. OpenAQ v3 (S3 Archive, loc=4946811)** | **2025-07-03T22:40** (S3) | **2026-07-15T17:05** (S3) | **2026-07-15T17:05:00+07:00** (file S3 mới nhất) | Sub-hourly (~5–10m) | Cần tổng hợp | **352 tệp S3 giai đoạn 2025–2026** (~220 obs/ngày/param). Không có dữ liệu 2023–2024 trên OpenAQ (0 files), dùng AirNow DOS CSV làm ground truth lịch sử. |
| **3. Open-Meteo ERA5** | **2023-01-01T00:00** | **2024-12-31T23:00** | **2026-09-24T06:00** (ERA5 thuần túy, trễ ~5 ngày) | 1 giờ | **Có (1h continuous)** | **0% khuyết thiếu.** Đúng 17,544 giờ liên tục (8,760h năm 2023 + 8,784h năm nhuận 2024). |
| **4. AirNow DOS CSV** | Documented: 2016-01-01 | Documented: 2023-12-31 | Documented: 2023-12-31 (bản mở công khai) | Documented: 1 giờ | Documented: Có | Documented: Chuỗi đo 2023 đầy đủ trạm ĐSQ Hoa Kỳ BAM-1020; có mã ngụy trang -999; năm 2024 không có file mở công khai |
| **5. PAM Air Portal** | Documented: ~2019 (theo thông tin cung cấp) | Provider-reported: Thời gian thực | Provider-reported: Thời gian thực (chỉ xem trên Web GUI) | Documented: 5–15 phút | Cần tổng hợp | Not verifiable directly (API đóng, không thể kiểm chứng lịch sử qua script mở) |
| **6. NOAA ISD 48820** | **2023-01-01T00:00** | **2024-12-31T23:30** | **2025-12-31** (năm 2026 chưa phát hành) | ~30 phút | Cần resample | 2023 có 17,178 obs (365/365 ngày); 2024 có 16,704 obs (359/366 ngày, thiếu 7 ngày). |

---

## 6. Đối Chiếu Biến Số Với Canonical Schema (Variable Availability)

Bảng đối chiếu danh mục trường dữ liệu ứng viên so với **Canonical Data Schema** (xác lập tại `docs/data_dictionary.md`):

| Trường Canonical | Định nghĩa | Kaggle | OpenAQ v3 (loc=4946811) | Open-Meteo ERA5 | AirNow DOS CSV | PAM Air Portal | NOAA ISD 48820 |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `timestamp` | Khóa thời gian chuẩn (`Asia/Ho_Chi_Minh`) | Có | Có (`datetime`) | Có (`time`) | Có (`Date (LST)`) | Có | Có (`DATE`) |
| `station_id` | Mã định danh trạm duy nhất | Khuyết/Tự sinh | Có (`location_id=4946811`) | Điểm lưới tọa độ | Có (`Site: Hanoi`) | Có mã trạm PAM | Có (`STATION=48820099999`) |
| `location` | Tên địa danh mô tả | Tùy file | Có (`"556 Nguyễn Văn Cừ"`) | Tọa độ / City name | Có (`"Hanoi"`) | Có tên điểm đo | Có (`NAME`) |
| `pm25` | Nồng độ bụi mịn $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) | Có | **Có (Sensor 13502150, 2025–2026)** | Không có | **Có (BAM-1020, 2023)** | Có (Cảm biến quang học) | **Không có** |
| `pm10` | Bụi thô $\text{PM}_{10}$ ($\mu\text{g/m}^3$) | Tùy file | **Có (Sensor 13502165, 2025–2026)** | Không có | Không có | Tùy trạm | **Không có** |
| `temperature` | Nhiệt độ bề mặt ($^\circ\text{C}$) | Tùy file | Không có | **Có (`temperature_2m`)** | Không có | Có trên một số nốt | Có (`TMP`, scale×10) |
| `relative_humidity` | Độ ẩm tương đối ($\%$) | Tùy file | Không có | **Có (`relative_humidity_2m`)** | Không có | Có trên một số nốt | **Từ DEW** (cần tính) |
| `wind_speed` | Tốc độ gió ($\text{m/s}$) | Tùy file | Không có | **Có (`wind_speed_10m`)** | Không có | Không có | Có (`WND`, scale×10) |
| `wind_direction` | Hướng gió ($0^\circ - 360^\circ$) | Tùy file | Không có | **Có (`wind_direction_10m`)** | Không có | Không có | Có (`WND`, trường riêng) |
| `precipitation` | Lượng mưa ($\text{mm}$) | Tùy file | Không có | **Có (`precipitation`)** | Không có | Không có | **Không thường xuyên** (AA1/AA2 không có trong đa số bản ghi) |
| `surface_pressure` | Áp suất khí quyển bề mặt ($\text{hPa}$) | Tùy file | Không có | **Có (`surface_pressure`)** | Không có | Không có | **Không trực tiếp** (có SLP = áp suất mực biển, cần hiệu chỉnh altitude) |

> **Nhận xét quan trọng:**
> - Không có bất kỳ một nguồn đơn lẻ nào cung cấp đồng thời cả nồng độ $\text{PM}_{2.5}$ quy chuẩn và trọn bộ 6 biến số khí tượng bề mặt.
> - Bắt buộc phải thực hiện chiến lược **ghép nối đa nguồn (Multi-source Integration)**: 1 nguồn chuyên trách chất lượng không khí + 1 nguồn chuyên trách khí tượng bề mặt.
> - **NOAA ISD thiếu 2 biến quan trọng:** `precipitation` (không có AA1/AA2 trong hầu hết bản ghi xác nhận qua profiling) và `surface_pressure` (chỉ có SLP cần hiệu chỉnh).

---

## 7. Quan Sát Chất Lượng Dữ Liệu & Cấu Trúc Schema (Data Quality & Schema Observations)

### 7.1. OpenAQ REST API v3 (S3 Public Archive – Location 4946811 - Trạm 556 Nguyễn Văn Cừ)

- **Phương thức truy xuất đã xác nhận:** Kho lưu trữ S3 công khai tại `openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=4946811/` — không yêu cầu API key. Dữ liệu tổ chức theo cấu trúc `year={YYYY}/month={MM}/location-4946811-{YYYYMMDD}.csv.gz`.
- **Cấu trúc file S3 (xác nhận thực tế):**
  ```
  location_id,sensors_id,location,datetime,lat,lon,parameter,units,value
  4946811,13502150,"556 Nguyễn Văn Cừ","2025-07-03T15:40:00Z",21.0491,105.8831,"pm25","µg/m³",32.0
  ```
- **Thông số & Cảm biến thực tế (6 thông số chuẩn quốc gia):**
  - `pm25`: Sensor ID `13502150`
  - `pm10`: Sensor ID `13502165`
  - `no2`: Sensor ID `13502159`
  - `co`: Sensor ID `13502158`
  - `so2`: Sensor ID `13502161`
  - `o3`: Sensor ID `13502160`
- **Kiểu dữ liệu:** `datetime` là chuỗi ISO 8601 UTC (ví dụ `2025-07-03T15:40:00Z`); `value` kiểu số thực `float64`; `parameter` kiểu chuỗi.
- **Tần suất quan sát & Phân biệt Terminology (Sub-hourly Telemetry vs. Hourly Aggregated):**
  - Tệp S3 của trạm 4946811 lưu trữ chuỗi đo tức thời tần suất dưới giờ (*sub-hourly raw telemetry*) với khoảng giãn cách đo $\approx 5 - 10$ phút/lần (trung bình $\approx 220$ bản ghi/ngày cho `pm25`).
  - Để đồng bộ với bước thời gian 1 giờ của Canonical Schema, adapter cần thực hiện tổng hợp theo giờ (**hourly aggregation**) bằng giá trị trung bình trên các mốc đo hợp lệ trong giờ.
- **Dải thời gian khả dụng trên S3:**
  - Tổng cộng **352 tệp CSV.gz** trong giai đoạn từ `2025-07-03` đến `2026-07-15` (180 tệp năm 2025, 172 tệp năm 2026).
  - OpenAQ không lưu trữ dữ liệu giai đoạn 2023–2024 cho trạm này (0 tệp) do OpenAQ mới bắt đầu ingest mạng lưới trạm Hà Nội từ tháng 7/2025. Vì vậy, đối với nghiên cứu lịch sử năm 2023, nguồn AirNow DOS CSV đóng vai trò ground truth lịch sử chính.
- **Tính chuẩn xác thiết bị:** Trạm do Trung tâm Quan trắc Môi trường miền Bắc (NCEM / Cục Kiểm soát ô nhiễm môi trường - VEA) trực tiếp quản lý và vận hành theo quy chuẩn kỹ thuật quốc gia về quan trắc môi trường.
- **REST API:** Endpoint `https://api.openaq.org/v3/locations/4946811` yêu cầu `X-API-Key` header.
- **Đính chính thu hồi:** `location_id = 2178` (Del Norte, Albuquerque, NM, Hoa Kỳ) đã bị thu hồi và loại bỏ hoàn toàn do nhầm lẫn mã mẫu tài liệu.

### 7.2. Open-Meteo Historical Weather API

- **Cấu trúc phản hồi (xác nhận từ API response):**
  ```json
  {
    "latitude": 21.05448,
    "longitude": 105.898476,
    "elevation": 19.0,
    "timezone": "Asia/Ho_Chi_Minh",
    "utc_offset_seconds": 25200,
    "hourly_units": {
      "time": "iso8601",
      "temperature_2m": "°C",
      "relative_humidity_2m": "%",
      "wind_speed_10m": "m/s",
      "wind_direction_10m": "°",
      "precipitation": "mm",
      "surface_pressure": "hPa"
    },
    "hourly": {
      "time": ["2023-01-01T00:00", "2023-01-01T01:00", ...],
      "temperature_2m": [11.5, 11.0, ...],
      ...
    }
  }
  ```
- **Kiểu dữ liệu:** `time` là chuỗi ISO 8601 local time; tất cả biến số là `float64`.
- **Lưu ý đơn vị tốc độ gió:** Khi dùng tham số `&wind_speed_unit=ms`, API trả trực tiếp $\text{m/s}$ (đã xác nhận từ response). Không cần tự chia 3.6.
- **Tính đầy đủ (xác nhận tại thời điểm profiling 2026-09-28/29 UTC):** 0/8,760 missing (2023), 0/8,784 missing (2024) cho tất cả 6 biến số, tức $0{,}00\%$ khuyết thiếu trong cửa sổ 2023–2024. Đây là kết quả đo tại một thời điểm cụ thể, không phải đảm bảo cho mọi lần truy vấn sau.

### 7.3. AirNow DOS CSV

- **Cấu trúc file:** Tệp phẳng CSV có tiêu đề:
  `Site, Parameter, Date (LST), Year, Month, Day, Hour, Value, Unit, Duration, QC Name`
- **Missing ngụy trang:** Giá trị khuyết thiếu được mã hóa bằng số nguyên `-999` hoặc `-999.0`. Nếu không bóc trần tại bước ingestion sẽ làm méo mó nghiêm trọng các chỉ số thống kê trung bình.
- **Múi giờ:** Cột `Date (LST)` là giờ địa phương (*Local Standard Time*, UTC+7), nhưng không có offset ISO rõ ràng.

### 7.4. Kaggle Datasets

- Cấu trúc không đồng nhất giữa các tác giả đăng tải.
- Một số tệp đã qua xử lý lọc nhiễu, điền khuyết thiếu bằng trung bình hoặc nội suy trước khi xuất CSV.
- Xuất hiện nguy cơ rò rỉ dữ liệu (*Data Leakage*) tiềm ẩn nếu sử dụng các đặc trưng trễ do bên thứ ba tạo sẵn mà không kiểm soát được quy trình phân tách Train/Test.

### 7.5. PAM Air Portal

- Cấu trúc payload API không công khai.
- Cảm biến quang học có hiện tượng trôi điểm zero (*baseline drift*) theo thời gian và bị ảnh hưởng mạnh bởi sương mù/độ ẩm cao ($\text{RH} > 90\%$) gây hiện tượng đọc quá nồng độ bụi thực tế.

### 7.6. NOAA ISD Station 48820099999 (Sân bay Nội Bài)

- **Phương thức truy xuất (xác nhận):** File CSV công khai không cần xác thực tại `https://www.ncei.noaa.gov/data/global-hourly/access/{YYYY}/48820099999.csv`. Trả về HTTP 200.
- **Cấu trúc file (xác nhận thực tế):**
  ```
  Columns: STATION, DATE, SOURCE, LATITUDE, LONGITUDE, ELEVATION, NAME,
           REPORT_TYPE, CALL_SIGN, QUALITY_CONTROL, WND, CIG, VIS,
           TMP, DEW, SLP, ED1, GA1, GA2, GA3, GA4, GE1, GF1,
           MA1, MW1, MW2, MW3, OC1, REM, EQD
  ```
- **Định dạng mã hóa (encoded fields):**
  - `TMP`: `+0110,1` → nhiệt độ $+11.0^\circ\text{C}$, quality flag=1. Cần chia giá trị cho 10.
  - `DEW`: `+0090,1` → điểm sương $+9.0^\circ\text{C}$. RH cần tính từ TMP và DEW bằng công thức August–Roche–Magnus.
  - `WND`: `999,9,V,0010,1` → hướng=999 (biến đổi), loại=V, tốc độ=1.0m/s (chia 10), quality=1.
  - `SLP`: `10250,1,99999,9` → áp suất mực biển $1025.0\,\text{hPa}$ (chia 10), quality=1. **Không phải `surface_pressure`** – cần hiệu chỉnh theo độ cao nếu dùng để ước lượng áp suất bề mặt.
- **Tần suất thực tế:** Báo cáo METAR (FM-15) khoảng 30 phút/lần (trung bình 47.1 bản ghi/ngày trong 2023). Cần resampling về 1 giờ trước khi ghép nối.
- **Thiếu sót chính:** `precipitation` không có trong trường AA1/AA2 đối với đa số bản ghi (xác nhận qua kiểm tra 50 dòng đầu), `surface_pressure` không trực tiếp có mà chỉ có SLP.
- **Vị trí:** Sân bay Nội Bài, cách trung tâm Hà Nội ~20km về phía Bắc — có sự chênh lệch vi khí hậu đô thị đáng kể.

---

## 8. Khả Năng Tái Lập & Giới Hạn Kỹ Thuật (Reproducibility)

| Nguồn ứng viên | Tính công khai | Phương thức truy xuất | Yêu cầu API Key | Rate Limits / Giới hạn tải | Khả năng tự động hóa |
|---|---|---|---|---|---|
| **1. Kaggle Datasets** | Bán công khai (Cần tài khoản Kaggle) | Tải qua web hoặc `kaggle` CLI | Cần API Token cá nhân (`kaggle.json`) | Không áp dụng cho tải file tĩnh | Thấp (Phụ thuộc file tĩnh, không cập nhật tự động) |
| **2. OpenAQ v3 REST** | Công khai | REST API (`requests`) | **Cần API Key miễn phí** (`X-API-Key`) | Có header `x-ratelimit`; phân quota hợp lý | **Rất cao** (Tự động hóa hoàn toàn qua script Python) |
| **2b. OpenAQ S3 Archive** | **Công khai hoàn toàn** | HTTP GET trực tiếp | **Không cần key** | Không giới hạn rõ ràng | **Rất cao** (Tải file CSV.gz theo ngày, không xác thực) |
| **3. Open-Meteo ERA5** | Công khai hoàn toàn | REST API chuẩn (`requests`) | **Không cần API Key** cho nghiên cứu phi thương mại | Tối đa 10.000 cuộc gọi/ngày | **Rất cao** (Tự động hóa hoàn toàn, tái lập tuyệt đối) |
| **4. AirNow DOS CSV** | Hạn chế | Tải file hàng năm qua website | Không có API Key nhưng hạn chế truy cập | Giới hạn theo cơ chế đăng nhập | Trung bình/Thấp (Phải tải thủ công hoặc lưu trữ mirror) |
| **5. PAM Air Portal** | **Đóng / Không công khai** | Cổng web giao diện người dùng | Cần ký thỏa thuận hợp tác đối tác | Không hỗ trợ public scraper | **Rất thấp** (Không khả thi tái lập độc lập) |
| **6. NOAA ISD** | **Công khai hoàn toàn** | HTTP GET file CSV trực tiếp | **Không cần key** | Không giới hạn rõ ràng | **Cao** (Tải file theo năm, định dạng cần giải mã ISD) |

---

## 9. Bản Quyền & Nghĩa Vụ Trích Dẫn (License & Attribution)

| Nguồn ứng viên | Giấy phép bản quyền (License) | Nghĩa vụ trích dẫn (Attribution) | Hạn chế sử dụng học thuật |
|---|---|---|---|
| **1. Kaggle Datasets** | Không đồng nhất (CC0, CC BY-SA 4.0, hoặc không ghi rõ) | Phụ thuộc người upload; thường thiếu xuất xứ gốc của phần cứng đo | Có rủi ro vi phạm bản quyền nếu dữ liệu gốc bị scrape không phép |
| **2. OpenAQ v3** | **Open Database License (ODC-BY) v1.0** | Bắt buộc ghi nhận: *"Data provided by OpenAQ and Hanoi Air Quality Monitoring Network (VEA/CEM)"* | **Cho phép hoàn toàn** cho nghiên cứu học thuật, giáo dục và công bố mở |
| **3. Open-Meteo ERA5** | **Creative Commons Attribution 4.0 International (CC BY 4.0)** | Bắt buộc trích dẫn: *"Weather data by Open-Meteo.com under CC BY 4.0, containing modified Copernicus Climate Change Service information (ERA5)"* | **Cho phép hoàn toàn** cho nghiên cứu phi thương mại và học thuật |
| **4. AirNow DOS CSV** | **U.S. Public Domain** (Tác phẩm của Chính phủ Hoa Kỳ) | Khuyến nghị ghi rõ nguồn US Department of State / AirNow | Sử dụng tự do |
| **5. PAM Air Portal** | **Bản quyền sở hữu trí tuệ của D&L JSC** | Phải xin phép bằng văn bản từ D&L Corp | Nghiêm cấm scrape hoặc khai thác tự động khi chưa được cấp phép |
| **6. NOAA ISD** | **U.S. Public Domain** (Dữ liệu chính phủ Hoa Kỳ / WMO) | Khuyến nghị ghi rõ nguồn NOAA NCEI / WMO Station 48820 | Sử dụng tự do cho mọi mục đích phi thương mại và học thuật |

---

## 10. Ma Trận So Sánh Nguồn Dữ Liệu (Source Comparison Matrix)

Bảng tổng hợp đánh giá khách quan dựa trên toàn bộ các tiêu chí đã thẩm định:

| Tiêu chí thẩm định | 1. Kaggle Hanoi | 2. OpenAQ v3 (loc=4946811) | 3. Open-Meteo ERA5 | 4. AirNow DOS CSV | 5. PAM Air Portal | 6. NOAA ISD 48820 |
|---|---|---|---|---|---|---|
| **Địa lý** | Not verifiable directly (Không rõ trạm) | Hà Nội (556 Nguyễn Văn Cừ, Long Biên) | Hà Nội (Lưới ERA5 $0.25^\circ$) | Documented: Hà Nội (ĐSQ HK, Ba Đình) | Documented: Hà Nội (>50 trạm nội thành) | Nội Bài (20km ngoại thành) |
| **Bao phủ thời gian** | Not verifiable directly (tùy file tải lên) | 2025–2026 (S3: 352 files; 2023–2024 chưa có trên OpenAQ) | 1940–Nay (2023–2024 đầy đủ) | Documented: 2016–2023 (bản mở) | Documented: ~2019–Nay (theo nhà cung cấp) | 2023–2024 xác nhận |
| **Tần suất** | Documented: 1 giờ (file ghép sẵn) | Sub-hourly (~5–10m) / Hourly aggregated | **1 giờ cố định** | Documented: 1 giờ (theo chuẩn US DOS) | Documented: 5–15 phút (theo thông số IoT) | ~30 phút (cần resample) |
| **Biến PM2.5** | Có | **Có (Sensor 13502150, 2025–2026)** | Không | **Có (BAM-1020, 2023)** | Có (cảm biến quang học) | **Không** |
| **Biến PM10** | Tùy file | **Có (Sensor 13502165, 2025–2026)** | Không | Không | Tùy nốt | **Không** |
| **Biến Khí tượng** | Một số (ghép sẵn) | Không có | **Đầy đủ 6/6 biến, 0% missing** | Không có | Thiếu gió/áp suất | 4/6 biến (thiếu precip, surface_pressure) |
| **Định dạng** | File tĩnh CSV | REST API (JSON) + S3 CSV.gz | REST API (JSON) | File tĩnh CSV | Web đóng | File CSV công khai |
| **Tái lập (Reproducibility)** | Thấp | **Cao** (REST, S3 không cần key) | **Xuất sắc** (Không cần key) | Trung bình (Tải thủ công) | **Không khả thi** | **Cao** (HTTP trực tiếp) |
| **Giấy phép** | Không rõ / Đa dạng | **ODC-BY v1.0** (Chuẩn mở) | **CC BY 4.0** (Chuẩn mở) | **Public Domain** | **Bản quyền đóng D&L** | **Public Domain** |
| **Hạn chế kỹ thuật** | Rủi ro rò rỉ; đã tiền xử lý | Cần API key cho REST; chuỗi đo S3 từ 07/2025 (dùng AirNow cho 2023) | Lưới tái phân tích ~25km | Format cũ; `-999` missing | Không có API công khai | Cần giải mã ISD; thiếu precip/pressure; vị trí lệch 20km |

---

## 11. Bảng Ánh Xạ Sang Canonical Schema (Canonical Schema Mapping)

Sau khi kiểm chứng cấu trúc payload và header thực tế của các nguồn được lựa chọn, bảng ánh xạ trường dữ liệu được xác lập chính thức:

| Trường Canonical | Kiểu dữ liệu | Đơn vị chuẩn | Nguồn dữ liệu | Tên trường tại nguồn (Provider Field) | Đơn vị gốc | Quy tắc chuyển đổi bắt buộc (Transformation Required) |
|---|---|---|---|---|---|---|
| `timestamp` | `datetime64[ns, Asia/Ho_Chi_Minh]` | ISO 8601 (UTC+7) | OpenAQ S3 / Open-Meteo / AirNow | `datetime` (OpenAQ S3)<br>`time` (Open-Meteo)<br>`Date (LST)` (AirNow) | ISO 8601 UTC (OpenAQ)<br>Local string với timezone query (Open-Meteo)<br>Chuỗi ngày giờ địa phương (AirNow) | OpenAQ S3: Parse ISO UTC string → chuyển đổi sang tz-aware `Asia/Ho_Chi_Minh` (UTC+7).<br>Open-Meteo: Truy vấn với `&timezone=Asia/Ho_Chi_Minh`, parse datetime và gán timezone UTC+7.<br>AirNow: Parse chuỗi `Date (LST)` thành tz-aware `Asia/Ho_Chi_Minh`.<br>Căn chỉnh đồng nhất làm trục thời gian hợp nhất. |
| `station_id` | `string` | Mã định danh trạm | OpenAQ S3 / AirNow DOS | `location_id` (OpenAQ)<br>`Site` (AirNow) | Integer ID / String | Chuẩn hóa thành mã danh mục duy nhất: `VN001_HANOI_556_NGUYEN_VAN_CU` (cho trạm OpenAQ location_id=4946811) hoặc `VN002_HANOI_US_EMBASSY` (cho trạm AirNow DOS CSV `Site == "Hanoi"`).<br>*(Tuyệt đối loại bỏ location_id=2178 thuộc Albuquerque, NM, Hoa Kỳ)*. |
| `location` | `string` | Tên địa danh | OpenAQ S3 / AirNow DOS | `location` (OpenAQ)<br>`Site` (AirNow) | String | Giá trị thực tế: `"556 Nguyễn Văn Cừ"` (hoặc `"US Diplomatic Post: Hanoi"` nếu dùng AirNow), chuẩn hóa khoảng trắng và UTF-8. |
| `pm25` | `float64` | $\mu\text{g/m}^3$ | OpenAQ S3 / AirNow DOS | `value` (OpenAQ khi `parameter == "pm25"`)<br>`Value` (AirNow DOS) | $\mu\text{g/m}^3$ | OpenAQ: Lọc `parameter == 'pm25'` (Sensor 13502150).<br>AirNow: Lấy cột `Value`.<br>Ép kiểu `Float64`. Quy tắc giá trị: Giá trị âm $(< 0\,\mu\text{g/m}^3)$ là lỗi vật lý $\to$ gán `NaN`; Giá trị đúng bằng 0 ($= 0.0\,\mu\text{g/m}^3$) giữ nguyên nếu hợp lệ (không kèm cờ lỗi QC); Bóc trần mã ngụy trang (`-999`, `-9999`) $\to$ gán `NaN`. |
| `pm10` | `float64` | $\mu\text{g/m}^3$ | OpenAQ S3 | `value` (khi `parameter == "pm10"`) | $\mu\text{g/m}^3$ | Lọc `parameter == 'pm10'` (Sensor 13502165). Ép kiểu `Float64`. |
| `temperature` | `float64` | $^\circ\text{C}$ | Open-Meteo | `temperature_2m` | $^\circ\text{C}$ | Ép kiểu `Float64`; kiểm tra giới hạn vật lý ($0^\circ\text{C} \le T \le 50^\circ\text{C}$). |
| `relative_humidity` | `float64` | $\%$ | Open-Meteo | `relative_humidity_2m` | $\%$ | Ép kiểu `Float64`; kiểm tra giới hạn vật lý $0\% \le \text{RH} \le 100\%$. |
| `wind_speed` | `float64` | $\text{m/s}$ | Open-Meteo | `wind_speed_10m` | $\text{m/s}$ (khi dùng `&wind_speed_unit=ms`) | Truy vấn API với `&wind_speed_unit=ms`. Ép kiểu `Float64`. |
| `wind_direction` | `float64` | Độ ($0^\circ - 360^\circ$) | Open-Meteo | `wind_direction_10m` | Độ ($^\circ$) | Ép kiểu `Float64`; chuẩn hóa modulo 360 độ. |
| `precipitation` | `float64` | $\text{mm}$ | Open-Meteo | `precipitation` | $\text{mm}$ | Ép kiểu `Float64`; kiểm tra không âm ($\ge 0$). |
| `surface_pressure` | `float64` | $\text{hPa}$ | Open-Meteo | `surface_pressure` | $\text{hPa}$ | Ép kiểu `Float64`; kiểm tra dải áp suất bề mặt thực tế ($950 - 1050\,\text{hPa}$). |

---

## 12. Quyết Định Cổng Nguồn Dữ Liệu (Source Decision Gate)

Căn cứ vào các kết quả thẩm định và ma trận so sánh đa tiêu chí, ban hành quyết định phân định vai trò chính thức cho các nguồn dữ liệu:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                       SOURCE DECISION GATE SUMMARY                       │
├──────────────────────────────────────────────────────────────────────────┤
│ 1. AIR QUALITY (PM2.5):                                                  │
│    • PRIMARY (CURRENT / OPERATIONAL): OpenAQ S3 (loc=4946811 - Long Biên)│
│    • PRIMARY (HISTORICAL 2023)      : AirNow DOS CSV (US Embassy BAM1020)│
│    • FALLBACK SOURCE                : AirNow DOS Historical CSV          │
│    • REFERENCE ONLY                 : Kaggle Hanoi Datasets              │
│    • DISQUALIFIED / EXCLUDED        : OpenAQ loc=2178 (Albuquerque, USA) │
│    • UNUSED                         : PAM Air Portal (Bản quyền đóng)    │
│                                                                          │
│ 2. METEOROLOGY (WEATHER):                                                │
│    • PRIMARY SOURCE  : Open-Meteo Historical Weather API (ERA5)          │
│    • FALLBACK SOURCE : NOAA ISD (WMO Station 48820 – Nội Bài Airport)    │
│    • UNUSED          : PAM Air Portal (Lý do: Không đủ 6 biến số)        │
└──────────────────────────────────────────────────────────────────────────┘
```

### 12.1. Nguồn Dữ Liệu Ô Nhiễm Không Khí (Air Quality)

- **Nguồn Chính Hiện Hành (Primary Current/Operational Source): OpenAQ REST API v3 / S3 Archive (location_id=4946811 - 556 Nguyễn Văn Cừ, Long Biên, Hà Nội)**
  - *Lý do chọn:*
    1. Trạm quan trắc chuẩn quốc gia do Trung tâm Quan trắc Môi trường miền Bắc (NCEM / VEA) vận hành, bảo đảm tính pháp lý và độ tin cậy khoa học cao nhất tại Việt Nam.
    2. Cung cấp đồng thời trọn bộ 6 thông số: `pm25` (Sensor 13502150), `pm10` (Sensor 13502165), `no2`, `co`, `so2`, `o3`.
    3. Profiling thực tế trên S3: 352 tệp CSV.gz từ 03/07/2025 đến 15/07/2026 với ~220 quan sát/ngày đối với PM2.5 (dạng sub-hourly telemetry, được tổng hợp thành hourly aggregated).
    4. Kho S3 công khai (`openaq-data-archive.s3.amazonaws.com`) cho phép tải file CSV.gz theo ngày mà không cần API key.
    5. Giấy phép bản quyền mở ODC-BY v1.0.

- **Nguồn Chuẩn Lịch Sử 2023 (Primary Historical Source): AirNow US Department of State Historical CSV**
  - *Lý do chọn:*
    1. Trạm Đại sứ quán Hoa Kỳ tại Hà Nội (`Site: Hanoi`) sử dụng thiết bị chuẩn Met One BAM-1020 đạt chứng nhận US EPA FEM (EQPM-0308-170).
    2. Cung cấp chuỗi đo nồng độ PM2.5 theo từng giờ hoàn chỉnh và liên tục trong suốt năm 2023 (thời điểm trạm OpenAQ 4946811 chưa được tích hợp lên hệ thống OpenAQ).
    3. Đóng vai trò ground truth lịch sử chính cho năm 2023 và phương án dự phòng ngoại tuyến (*Fallback Source*).
    4. Lưu ý: Bóc trần mã ngụy trang `-999` thành `NaN`.

- **Nguồn Bị Thu Hồi & Loại Bỏ Hoàn Toàn (Disqualified & Excluded): OpenAQ Location 2178**
  - *Lý do:* Tọa độ thực tế là Del Norte High School, Albuquerque, New Mexico, Hoa Kỳ. Toàn bộ dữ liệu và metrics trước đây (14,424 dòng) bị thu hồi và loại bỏ hoàn toàn khỏi bài toán Hà Nội.

- **Nguồn Tham Chiếu (Reference Only): Kaggle Hanoi Datasets**
  - *Lý do:* Chỉ dùng để đối sánh các chỉ số phân phối thống kê đã công bố; tuyệt đối không dùng làm nguồn nạp chính.

- **Nguồn Loại Bỏ (Unused): PAM Air Portal**
  - *Lý do:* Không có API công khai miễn phí; giấy phép dữ liệu đóng; cảm biến quang học dễ bị trôi và nhiễu ẩm mà không có trạm hiệu chuẩn kèm theo.

### 12.2. Nguồn Dữ Liệu Khí Tượng Bề Mặt (Weather)

- **Nguồn Chính (Primary Source): Open-Meteo Historical Weather API (ERA5 Reanalysis)**
  - *Lý do chọn:*
    1. Cung cấp đầy đủ 6/6 biến số khí tượng Canonical Schema tại đúng điểm lưới gần trạm OpenAQ 4946811 (khoảng cách chỉ **1.7 km**).
    2. **0% missing** cho toàn bộ 17,544 giờ (2023–2024) – xác nhận thực nghiệm từ API call trực tiếp.
    3. API công khai hoàn toàn, không yêu cầu key, không cần xác thực.
    4. Giấy phép mở CC BY 4.0.

- **Nguồn Dự Phòng (Fallback Source): NOAA Integrated Surface Database (ISD – Station 48820099999 Nội Bài Airport)**
  - *Hồ sơ profiling thực tế:*
    - Tệp file 2023: 17,178 bản ghi, 365/365 ngày, trung bình 47.1 obs/ngày (~30 phút/lần).
    - Tệp file 2024: 16,704 bản ghi, 359/366 ngày (7 ngày thiếu dữ liệu).
    - TMP missing 2023: 0/17,178 (0.0%). SLP missing 2023: 0/17,178 (0.0%).
    - **Thiếu:** `precipitation` (AA1/AA2 không có trong phần lớn bản ghi), `surface_pressure` trực tiếp (chỉ có SLP cần hiệu chỉnh).
    - **Tần suất không đều:** cần resampling về 1 giờ.
    - **Vị trí lệch:** Nội Bài (21.221°N, 105.807°E) cách trạm PM2.5 ~20km về phía Bắc — sai số vi khí hậu đô thị đáng kể.
  - *Lý do xếp là Fallback:* Open-Meteo hoàn toàn đáp ứng yêu cầu; NOAA chỉ dự phòng nếu ERA5 không khả dụng.

---

## 13. Hạn Chế & Bất Định Kỹ Thuật Chưa Giải Quyết (Limitations & Uncertainties)

1. **Đặc thù bao phủ thời gian của OpenAQ tại Hà Nội & Cơ chế Đồng bộ Động Khí tượng:**
   - Trạm chuẩn quốc gia 4946811 (556 Nguyễn Văn Cừ) là nguồn dữ liệu chất lượng không khí vận hành hiện hành (*current operational source*), được OpenAQ tích hợp lưu trữ từ tháng 7/2025 (352 tệp S3 thô, bao phủ từ `2025-07-03` đến `2026-07-15`).
   - Do trạm 4946811 không có dữ liệu giai đoạn 2023–2024 trên OpenAQ, việc cố định cửa sổ khí tượng Open-Meteo vào 2023–2024 trước đây dẫn tới xung đột thời gian (tập dữ liệu không giao thoa / *temporal disjointness*).
   - **Giải pháp đồng bộ động (Dynamic Temporal Synchronization):** Phạm vi thời gian thực tế của chuỗi quan trắc OpenAQ 4946811 được dùng làm nguồn chân lý (*source of truth*) để dẫn xuất động cửa sổ truy vấn khí tượng Open-Meteo ERA5 (`query_start = df_air['timestamp'].min().strftime('%Y-%m-%d')`, `query_end = df_air['timestamp'].max().strftime('%Y-%m-%d')`). Cơ chế này bảo đảm tập dữ liệu ô nhiễm và khí tượng có tập giao thoa thời gian không rỗng (100% bản ghi chất lượng không khí khớp 1:1 với dữ liệu thời tiết), sẵn sàng cho bước tích hợp đa nguồn tại Issue #7.
   - *Trạng thái triển khai AirNowDOSAdapter (Issue #3 / PR #24):* Class `AirNowDOSAdapter` đã được cài đặt hoàn chỉnh và kiểm thử đơn vị tự động trong `src/data_collection.py`. Do yêu cầu quyền truy cập tổ chức AirNow-Tech / State Dept để tải dữ liệu lịch sử thô, pipeline ghi nhận trạng thái nạp thực tế là `adapter: implemented`, `ingestion_status: not_executed_pending_raw_input`, `role: historical_source_fallback`, `raw_input: unavailable_in_current_execution`. AirNow đóng vai trò nguồn dự phòng lịch sử ngoại tuyến khi có tệp thô. Đồ án tuân thủ nghiêm ngặt liêm chính học thuật: tuyệt đối không tạo dữ liệu giả lập (no synthetic/mock data).
   - *Phân định thời gian thực nghiệm:* Phân biệt rành mạch giữa `requested_study_window` (cửa sổ truy vấn yêu cầu hoặc cửa sổ nghiên cứu mặc định) và `actual_source_coverage` (thời gian thực tế của từng nguồn được tính toán trực tiếp từ `min()` và `max()` timestamp của DataFrame sau chuẩn hóa).
2. **Tần suất đo telemetry dưới giờ của trạm 4946811:** Tệp S3 chứa các bản ghi chu kỳ 5–10 phút (~220 dòng/ngày/thông số), đòi hỏi adapter phải tổng hợp trung bình theo giờ (*hourly aggregation*) có kiểm soát số lượng điểm đo tối thiểu trong mỗi giờ.
3. **Đại diện không gian đơn trạm:** Cả hai trạm (556 Nguyễn Văn Cừ ở Long Biên và ĐSQ Hoa Kỳ ở Ba Đình) đều thuộc vùng nội đô Hà Nội, chưa phản ánh toàn diện các khu vực ngoại thành hoặc khu công nghiệp ven đô. Hạn chế này cần nêu rõ trong Datasheet for Dataset tại Issue #14.
4. **Độ phân giải không gian của ERA5:** Điểm lưới ERA5 ($21.0545^\circ\text{N}, 105.8985^\circ\text{E}$) cách trạm OpenAQ 4946811 ($21.0491^\circ\text{N}, 105.8831^\circ\text{E}$) chỉ **1.7 km** về phía Đông Bắc – độ khớp không gian rất cao và tối ưu cho nghiên cứu tương quan.
5. **Giới hạn Rate Limit OpenAQ v3 REST API:** Cần API key và áp dụng rate limit. Pipeline Issue #3 ưu tiên dùng S3 archive (không cần key) cho dữ liệu lưu trữ; REST API chỉ dùng cho dữ liệu real-time.
6. **NOAA ISD thiếu 2 biến Canonical:** `precipitation` và `surface_pressure` không đầy đủ trong file ISD 48820. NOAA chỉ dùng làm fallback thời tiết, không thể thay thế Open-Meteo.

---

## 14. Yêu Cầu Bàn Giao Kỹ Thuật Cho Issue #3 & Issue #4 (Handoff Requirements)

Quyết định tại Issue #19 chuyển giao các yêu cầu đặc tả kỹ thuật bắt buộc cho các bước tiếp theo:

### 14.1. Handoff cho Issue #3 (Pipeline Thu thập & Chuẩn hóa Dữ liệu Ô nhiễm)

- **Endpoint S3 OpenAQ (ưu tiên lưu trữ):** `s3://openaq-data-archive/records/csv.gz/locationid=4946811/year={YYYY}/month={MM}/location-4946811-{YYYYMMDD}.csv.gz`.
- **Endpoint REST API OpenAQ (cho real-time):** `https://api.openaq.org/v3/locations/4946811` — cần `X-API-Key`.
- **Trạm quan trắc hợp chuẩn:**
  - Trạm chuẩn quốc gia hiện hành: `location_id = 4946811` (`"556 Nguyễn Văn Cừ"`, Long Biên, Hà Nội).
  - Trạm chuẩn lịch sử 2023: AirNow DOS CSV (`Site == "Hanoi"`, US Embassy BAM-1020, trạng thái fallback ngoại tuyến pending raw input).
- **Tuyệt đối loại bỏ trạm:** `location_id = 2178` (Del Norte, Albuquerque, NM, Hoa Kỳ).
- **Thông số:** Lọc `parameter == 'pm25'` (Sensor 13502150) và `parameter == 'pm10'` (Sensor 13502165) cùng các khí NO2, CO, SO2, O3.
- **Yêu cầu adapter:**
  - Parse `datetime` với múi giờ: Với OpenAQ chuyển đổi từ UTC ISO 8601 sang `Asia/Ho_Chi_Minh` (UTC+7); với AirNow gán timezone `Asia/Ho_Chi_Minh` cho `Date (LST)`.
  - Tổng hợp chuỗi telemetry dưới giờ của trạm 4946811 thành dữ liệu tổng hợp theo giờ (**hourly aggregated data**) bằng hàm trung bình.
  - Lọc dòng theo `parameter == 'pm25'`; áp dụng quy tắc giá trị: giá trị $< 0\,\mu\text{g/m}^3$ gán `NaN`; giá trị $= 0.0\,\mu\text{g/m}^3$ giữ nguyên nếu hợp lệ (không kèm cờ lỗi QC); chuyển đổi các mã lỗi ngụy trang (`-999`, `-9999` từ AirNow) thành `NaN`.
  - Lưu tệp thô nguyên trạng vào `data/raw/` (không chỉnh sửa thủ công; mọi biến đổi diễn ra ở lớp chuẩn hóa).
  - Cập nhật `data/raw/metadata.json` với source URL, extraction date, và license.

### 14.2. Handoff cho Issue #4 (Pipeline Thu thập & Đồng Bộ Dữ liệu Khí Tượng)

- **Endpoint mục tiêu:** `https://archive-api.open-meteo.com/v1/archive`.
- **Tọa độ truy vấn:** `latitude=21.0285&longitude=105.8542`.
- **Đồng bộ hóa thời gian động (Dynamic Temporal Synchronization):**
  - Khi không có cửa sổ chỉ định từ caller, `start_date` và `end_date` được suy diễn tự động từ timestamp tối thiểu và tối đa của tập dữ liệu chất lượng không khí canonical thực tế (`df_air['timestamp'].min()` và `max()`).
  - Hỗ trợ cửa sổ truyền vào rõ ràng (`study_window_start`, `study_window_end`) khi người dùng cần chạy thực nghiệm trên một dải thời gian cố định.
- **Tham số biến số:**
  `hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,surface_pressure`.
- **Tham số kỹ thuật:**
  `&wind_speed_unit=ms&timezone=Asia%2FHo_Chi_Minh`.
- **Yêu cầu adapter:**
  - Đặt tên file thô theo dải ngày thực tế: `open_meteo_raw_{start_date}_{end_date}.json` để tránh va chạm cache (cache collision).
  - Bắt buộc truyền `start_date` / `end_date` (không có giá trị mặc định) để không thể vô tình áp đặt lại khung thời gian lịch sử cố định.
  - Đo và báo cáo tỷ lệ khuyết thiếu trên cả 6 biến; pipeline thực thi áp ngưỡng 0% (xem `WEATHER_PIPELINE_MAX_MISSING_PCT`) và dừng với thông báo lỗi nếu vượt ngưỡng.
  - Lưu tệp thô nguyên trạng vào `data/raw/` (không chỉnh sửa thủ công) kèm mã băm SHA-256.
  - Cập nhật `data/raw/metadata.json` ghi nhận rành mạch cả `requested_query_window` và `actual_source_coverage`.

### 14.3. Báo Cáo Triển Khai Thực Tế & Kiểm Định Chất Lượng Khí Tượng (Issue #4 Execution & Validation Report)

Pipeline thu thập và chuẩn hóa dữ liệu khí tượng bề mặt Hà Nội đã được hoàn thiện tại Issue #4, kế thừa cơ chế đồng bộ hóa thời gian động từ PR #25:

1. **Nguồn dữ liệu & Vị trí địa lý:**
   - **Nguồn chính (PRIMARY):** Open-Meteo Historical Weather API (ECMWF ERA5 Reanalysis) — đúng vai trò đã ban hành tại §12.2.
   - **Tọa độ truy vấn:** $21.0285^\circ\text{N}, 105.8542^\circ\text{E}$ (tâm lõi đô thị Hà Nội). Adapter kiểm tra tọa độ truy vấn nằm trong Bounding Box ngay khi khởi tạo.
   - **Điểm lưới ERA5 trả về:** $21.05448^\circ\text{N}, 105.89848^\circ\text{E}$ (độ cao $19.0\,\text{m}$) — cách trạm 556 Nguyễn Văn Cừ ($21.0491^\circ\text{N}, 105.8831^\circ\text{E}$) **$1{,}71\,\text{km}$** (tính từ tọa độ trong payload thô), nằm trọn vẹn trong Bounding Box Hà Nội. Nếu payload không trả về tọa độ, pipeline dừng với lỗi thay vì tự động pass.
   - **Nguồn dự phòng (NOAA ISD 48820 - Sân bay Nội Bài):** **không kích hoạt**. Lý do: Open-Meteo ERA5 đã cung cấp đủ 6/6 biến Canonical, 0 giá trị khuyết thiếu và bao phủ trọn vẹn dải thời gian quan trắc thực tế. Theo hồ sơ tại §3c mục 3, NOAA thiếu `precipitation` và `surface_pressure`, cần resampling và lệch vị trí ~22 km nên chỉ dùng khi Open-Meteo không khả dụng.

2. **Cơ chế Đồng bộ Hóa Thời Gian Động (Dynamic Temporal Synchronization - PR #25):**
   - Cửa sổ truy vấn khí tượng tự động suy diễn từ chuỗi thời gian canonical `Asia/Ho_Chi_Minh` của `df_air_canonical["timestamp"]` (`2025-07-03` đến `2026-07-15`) khi caller không truyền tham số cứng.
   - `OpenMeteoAdapter.fetch_raw_data()` **yêu cầu bắt buộc** `start_date` / `end_date` và không có giá trị mặc định nào — không tồn tại bất kỳ khung thời gian lịch sử cố định nào trong mã nguồn (được bảo vệ bởi unit test).
   - Tên tệp thô được sinh động theo dải ngày: `open_meteo_raw_2025-07-03_2026-07-15.json` để ngăn ngừa xung đột bộ nhớ đệm.

3. **Canonical Weather Schema & Kiểu Dữ Liệu:**
   - Đảm bảo trọn bộ 7 trường dữ liệu chuẩn theo `docs/data_dictionary.md`:
     - `timestamp`: `datetime64[ns, Asia/Ho_Chi_Minh]` (UTC+7, làm tròn đầu giờ).
     - 6 biến số kiểu `float64`: `temperature` ($^\circ\text{C}$), `relative_humidity` ($\%$), `wind_speed` ($\text{m/s}$), `wind_direction` (độ), `precipitation` ($\text{mm}$), `surface_pressure` ($\text{hPa}$).

4. **Kiểm Định Chất Lượng & Ranh Giới Vật Lý (`validate_weather_canonical`)** — hàm chỉ đọc, không sửa dữ liệu đầu vào:
   - **Phân định mức kết quả:** *validation failure* (ném lỗi: thiếu cột/sai kiểu, sai múi giờ, trùng lặp, không tăng đơn điệu, vi phạm giới hạn vật lý, khuyết thiếu vượt ngưỡng) vs *validation warning* (gaps, giá trị bị cleaning loại bỏ) vs *cleaning* (bước biến đổi riêng, được đếm minh bạch).
   - **Múi giờ:** bắt buộc tz-aware với offset `+07:00`; sai lệch bị từ chối (ví dụ tz-naive hoặc UTC).
   - **Tính duy nhất:** $0$ trùng lặp trên khóa `timestamp`.
   - **Tính liên tục chuỗi giờ:** $9.072$ giờ liên tiếp, bước đo chính xác $1\,\text{giờ}$, $0$ khoảng trống.
   - **Kiểm toán dải vật lý khí hậu Hà Nội:**
     - `temperature`: $[8.9, 38.6]^\circ\text{C}$ (nằm trong $[0, 50]^\circ\text{C}$, trung bình $24.87^\circ\text{C}$).
     - `relative_humidity`: $[30.0, 100.0]\%$ (nằm trong $[0, 100]\%$, trung bình $80.63\%$).
     - `wind_speed`: $[0.0, 9.55]\,\text{m/s}$ (nằm trong $[0, 60]\,\text{m/s}$, trung bình $2.41\,\text{m/s}$).
     - `wind_direction`: $[1.0, 360.0]^\circ$ (nằm trong $[0, 360]^\circ$, trung bình $147.16^\circ$).
     - `precipitation`: $[0.0, 20.5]\,\text{mm}$ ($\ge 0\,\text{mm}$, trung bình $0.26\,\text{mm}$).
     - `surface_pressure`: $[986.5, 1028.4]\,\text{hPa}$ (nằm trong $[950, 1050]\,\text{hPa}$, trung bình $1008.20\,\text{hPa}$).
   - **Tỷ lệ khuyết thiếu:** $0$ giá trị khuyết thiếu trên toàn bộ 6 biến ($9.072/9.072$ bản ghi đầy đủ), đo bằng `max_missing_pct` và ghi vào `metadata.json`.
   - **Xử lý số 0 & Missing ngụy trang (`clean_weather_values`):** Mã lỗi ngụy trang (`-999`, `-9999`) và giá trị vi phạm giới hạn vật lý được chuyển thành `NaN`; **thống kê số lượng theo từng nguyên nhân** được ghi vào `df.attrs["weather_cleaning"]` và báo cáo trong `metadata.json`, đảm bảo không có giá trị nào bị loại bỏ âm thầm. Các giá trị $0.0$ thực tế (lượng mưa $0.0\,\text{mm}$, tốc độ gió $0.0\,\text{m/s}$) được bảo toàn nguyên vẹn.

5. **Tích Hợp Chuỗi Thời Gian (Temporal Integration with Air Quality):**
   - Phép inner join theo `timestamp` đạt **$8.022$ bản ghi** (từ `2025-07-03 22:00:00+07:00` đến `2026-07-15 17:00:00+07:00`).
   - Độ bao phủ đối với chuỗi quan trắc chất lượng không khí là **$100{,}0\%$** (tính từ `len(overlap) / len(air_canonical)`), không phát hiện nổ dòng (*row explosion*) — pipeline dừng với lỗi nếu vượt ngưỡng này. Dữ liệu sẵn sàng cho bước tích hợp đa nguồn tại Issue #7.

6. **Tệp Dữ Liệu Thô & Truy Vết Xuất Xứ (Raw Artifact & Provenance):**
   - Tệp thô khí tượng: `data/raw/open_meteo_raw_2025-07-03_2026-07-15.json` ($9.072$ mốc giờ), sinh tên động theo dải ngày truy vấn thực tế.
   - Payload được ghi **nguyên trạng**; mọi biến đổi (parse, timezone, cleaning, kiểm định) diễn ra ở lớp canonical, không sửa tệp thô.
   - Mã băm SHA-256 của tệp thô được ghi trong `data/raw/metadata.json` cùng URL truy vấn, thời điểm thu thập, giấy phép và attribution.
   - **Tệp thô không được commit vào Git** (`.gitignore`: `data/raw/*.json`), đúng quy ước kho dữ liệu thô của dự án; được tái tạo lại bằng `run_collection_pipeline()`.

7. **Giới Hạn Nguồn Dữ Liệu (Source Limitations):**
   - ERA5 là mô hình tái phân tích khí quyển dạng lưới độ phân giải $0.25^\circ \times 0.25^\circ$ ($\approx 25\,\text{km}$), phản ánh điều kiện khí tượng vĩ mô khu vực thay vì hiệu ứng vi khí hậu siêu cục bộ (ví dụ hiệu ứng hẻm phố đô thị - street canyon effect). Hạn chế này cần được ghi nhận minh bạch trong các báo cáo phân tích hồi quy tại Issue #12.

