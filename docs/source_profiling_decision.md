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

> [!IMPORTANT]
> Toàn bộ số liệu trong bảng dưới đây thu thập bằng script Python gọi API/tải file trực tiếp tại timestamp **`2026-09-28T16:47:26Z` (UTC)**. Mọi con số có thể **tái lập** bằng cách chạy lại script profiling trong `scratch/profile_sources*.py`. Không có giá trị nào được ước lượng hoặc suy diễn chủ quan.

| Chỉ tiêu profiling | OpenAQ (S3 Archive, location_id=2178) | Open-Meteo ERA5 | NOAA ISD 48820099999 | AirNow DOS | Kaggle Datasets | PAM Air Portal |
|---|---|---|---|---|---|---|
| **Số dòng 2023 (tất cả params)** | 53,277 | — | 17,178 | Không tải | Tùy file | Không công khai |
| **Số dòng 2023 (pm25)** | **6,049** | — | N/A | Chưa kiểm | Tùy file | N/A |
| **Số dòng 2023 (khí tượng)** | — | **8,760** | 17,178 | — | — | — |
| **Số dòng 2024 (tất cả params)** | 63,821 | — | 16,704 | Không khả dụng | Tùy file | Không công khai |
| **Số dòng 2024 (pm25)** | **8,375** | — | N/A | — | Tùy file | N/A |
| **Số dòng 2024 (khí tượng)** | — | **8,784** | 16,704 | — | — | — |
| **Tổng pm25 (2023+2024)** | **14,424** | N/A | N/A | N/A | N/A | N/A |
| **Tổng khí tượng (2023+2024)** | N/A | **17,544** | **33,882** | N/A | N/A | N/A |
| **Số cột / trường** | 9 | 7 (1 thời gian + 6 biến) | 30 | ~11 | Tùy file | Không công khai |
| **min_timestamp (2023)** | 2023-01-01 | **2023-01-01T00:00** | **2023-01-01T00:00** | 2016-01-01 | Tùy file | ~2019 |
| **max_timestamp (2024)** | 2024-12-31 | **2024-12-31T23:00** | **2024-12-31** | 2023-12-31 | Tùy file | Hiện tại |
| **Tần suất** | 1 giờ | **1 giờ (cố định)** | ~30 phút (METAR) | 1 giờ | 1 giờ | 5–15 phút |
| **Missing rate pm25 (2023)** | **6,049/8,760 = 69.1%** nhận được | N/A | N/A | Chưa kiểm | Chưa kiểm | N/A |
| **Missing rate pm25 (2024)** | **8,375/8,784 = 95.3%** nhận được | N/A | N/A | N/A | Chưa kiểm | N/A |
| **Missing rate tổng pm25** | **14,424/17,544 = 82.2%** nhận được | N/A | N/A | N/A | N/A | N/A |
| **Missing rate TMP (2023)** | N/A | **0/8,760 = 0.0%** | **0/17,178 = 0.0%** | N/A | N/A | N/A |
| **Missing rate SLP (2023)** | N/A | **0/8,760 = 0.0%** | **0/17,178 = 0.0%** | N/A | N/A | N/A |
| **Missing rate (6 biến khí tượng)** | N/A | **0.0% tất cả biến** | N/A (SLP có; thiếu surface_pressure, precipitation) | N/A | N/A | N/A |
| **Ngày có dữ liệu / Tổng ngày (2023)** | 365 files | 365/365 | **365/365** | Chưa kiểm | Tùy file | Không công khai |
| **Ngày có dữ liệu / Tổng ngày (2024)** | 366 files | 366/366 | **359/366** (7 ngày thiếu) | N/A | Tùy file | Không công khai |
| **Duplicate rows** | Chưa kiểm | **0** (lưới đồng nhất) | Chưa kiểm | Chưa kiểm | Chưa kiểm | N/A |
| **Xác nhận vị trí Hà Nội** | ✅ location_id=2178 đã được S3 xác nhận tồn tại 2016–2024 | ✅ lat=21.054°N lon=105.898°E elev=19m | ✅ "NOIBAI INTERNATIONAL, VM" lat=21.221°N lon=105.807°E | ✅ Site=Hanoi | Tùy tác giả | ✅ Nhiều trạm nội thành |
| **Parameters thực tế** | pm25, **pm10**, no2, co, so2, o3, no, nox (8 params) | temperature_2m, relative_humidity_2m, wind_speed_10m, wind_direction_10m, precipitation, surface_pressure | WND, TMP, DEW, SLP, CIG, VIS (không có PM) | pm25 | pm25, weather (tùy file) | pm25, pm10, AQI |
| **Endpoint truy xuất** | `s3://openaq-data-archive/records/csv.gz/locationid=2178/` | `archive-api.open-meteo.com/v1/archive` | `ncei.noaa.gov/data/global-hourly/access/{yr}/48820099999.csv` | airnow.gov | Kaggle API | pamair.org |
| **Yêu cầu xác thực** | API key cho REST; **không cần key cho S3** | **Không cần key** | **Không cần key** | Cần đăng nhập | Cần API token | Đóng |

> [!NOTE]
> **Phát hiện quan trọng (OpenAQ location 2178):** Archive S3 xác nhận location_id=2178 cung cấp **8 thông số** bao gồm cả `pm10`, `no2`, `co`, `so2`, `o3`, `no`, `nox` bên cạnh `pm25`. Đây là bằng chứng cho thấy trạm đã được trang bị thêm cảm biến bổ sung, khác với giả định ban đầu rằng BAM-1020 chỉ đo PM2.5. Tuy nhiên, completeness của pm25 trong năm 2023 thấp (69.1%), phục hồi lên 95.3% năm 2024. Cần kiểm chứng thêm mức độ đầy đủ của pm10 tại Issue #3.

---

## 4. Độ Bao Phủ Địa Lý & Metadata Trạm (Geographic Coverage)

| Nguồn ứng viên | Tọa độ xác định | Metadata trạm | Phạm vi thực tế tại Hà Nội | Đánh giá địa lý |
|---|---|---|---|---|
| **1. Kaggle Datasets** | Thường chỉ ghi `Hanoi` tổng quát, một số tệp ghi tọa độ tâm thành phố ($21.0285^\circ\text{N}, 105.8542^\circ\text{E}$). | Không có thông tin số hiệu cảm biến (*serial*), chiều cao ống nạp khí (*inlet height*), hoặc quy chuẩn kiểm định. | Dữ liệu gộp cho toàn địa bàn hoặc trích xuất từ 1 trạm đơn nhưng thiếu hồ sơ trạm chuẩn hóa. | **Trung bình:** Không xác định rõ vị trí vật lý cụ thể của thiết bị thu thập ban đầu. |
| **2. OpenAQ REST API v3** | Xác định chính xác: location_id=2178, tọa độ xác nhận qua S3 archive (2016–2024). Trạm Đại sứ quán Hoa Kỳ tại Hà Nội, quận Đống Đa / Ba Đình. | Đầy đủ: `locationId=2178`, tên trạm (`US Diplomatic Post: Hanoi`), thiết bị đo chuẩn quy chiếu Met One BAM-1020, chủ quản US Department of State. | Trạm mặt đất cố định nằm tại trung tâm đô thị Hà Nội, phản ánh mức độ phơi nhiễm thực tế của cư dân nội thành. | **Rất tốt:** Tọa độ rõ ràng, metadata trạm quy chuẩn quốc tế, đại diện môi trường đô thị lõi. |
| **3. Open-Meteo ERA5** | Điểm lưới thực tế (xác nhận từ API response): $21.05448^\circ\text{N}, 105.89848^\circ\text{E}$, độ cao $19.0\,\text{m}$. | Cung cấp đầy đủ metadata lưới: tọa độ, elevation, timezone, utc_offset_seconds=25200. | Bao phủ toàn bộ khu vực địa lý Hà Nội với lưới khí quyển đồng nhất $0.25^\circ \times 0.25^\circ$ ($\approx 25\,\text{km}$). | **Rất tốt:** Tính toán khí quyển đồng bộ, không bị lệch vị trí do di dời trạm cơ học. |
| **4. AirNow DOS CSV** | Trạm Đại sứ quán Hoa Kỳ tại Hà Nội (`Site: Hanoi`), cùng trạm với OpenAQ. | Có mã site (`Hanoi`), tên thiết bị (`PM2.5 - Central`), cơ quan quản lý (US DOS / EPA). | Đặt tại Đại sứ quán Hoa Kỳ, Láng Hạ, Hà Nội. | **Tốt:** Đúng trạm mặt đất chuẩn quy chiếu tại Hà Nội. |
| **5. PAM Air Portal** | Mạng lưới nhiều trạm phân bố khắp các quận/huyện Hà Nội (Cầu Giấy, Hoàn Kiếm, Thanh Xuân, Gia Lâm...). | Có tên địa điểm, tọa độ từng điểm cảm biến IoT, nhưng metadata thiết bị thuộc sở hữu riêng của D&L. | Độ bao phủ không gian dày đặc nhất trong các nguồn. | **Rất tốt về mật độ không gian**, nhưng thiếu chứng nhận kiểm định trạm chuẩn quy chuẩn quốc gia. |
| **6. NOAA ISD 48820** | Xác nhận trực tiếp từ file: `"NOIBAI INTERNATIONAL, VM"`, lat=$21.221192^\circ\text{N}$, lon=$105.807178^\circ\text{E}$, elevation=11.88m. | Mã WMO=48820, WBAN=99999, Report type FM-15 (METAR), trạm khí tượng hàng không sân bay Nội Bài. | Sân bay Nội Bài nằm cách trung tâm đô thị Hà Nội khoảng **20–25 km về phía Bắc**, môi trường ven thành thị, không đại diện cho vi khí hậu lõi đô thị. | **Tốt nhưng lệch địa lý:** Là nguồn thực đo mặt đất, nhưng khoảng cách 20km có thể tạo ra sai số vi khí hậu đáng kể so với vị trí trạm PM2.5 tại Ba Đình. |

---

## 5. Độ Bao Phủ Thời Gian Thực Tế & Tần Suất (Temporal Coverage)

> Các timestamp min/max được xác minh từ API call và file thực tế tại thời điểm profiling `2026-09-28T16:47:26Z (UTC)`.

| Nguồn ứng viên | min_timestamp (thực tế) | max_timestamp (thực tế) | Tần suất đo | Hourly? | Tình trạng khoảng trống (Temporal Gaps) |
|---|---|---|---|---|---|
| **1. Kaggle Datasets** | Tùy file (ví dụ 14/02/2024) | Tùy file (ví dụ 26/01/2026) | 1 giờ | Có (trong các file time-series). | Nhiều khoảng khuyết đã bị tác giả tự ý điền khuyết (impute), không thể khôi phục trạng thái thô ban đầu. |
| **2. OpenAQ v3 (S3)** | 2023-01-01 (xác nhận file S3 tồn tại từ 2016) | 2024-12-31 (file cuối cùng xác nhận trong S3 archive) | 1 giờ | **Có** | **pm25 completeness: 69.1% (2023), 95.3% (2024), tổng 82.2%** – có các khoảng khuyết ngẫu nhiên thực tế (bảo trì, mất điện, kiểm định thiết bị). Không phải 0% missing. |
| **3. Open-Meteo ERA5** | **2023-01-01T00:00** (xác nhận từ API) | **2024-12-31T23:00** (xác nhận từ API) | 1 giờ | **Có** | **0% khoảng khuyết.** 8,760 giờ (2023) + 8,784 giờ (2024 – năm nhuận) = **17,544 giờ** hoàn chỉnh 100%. |
| **4. AirNow DOS CSV** | 2016-01-01 | 2023-12-31 (file năm 2024 không tải được trực tiếp không cần đăng nhập) | 1 giờ | **Có** | Có khoảng khuyết thực tế; mã lỗi khuyết thiếu được mã hóa dưới dạng `-999`. Năm 2024 chưa có tệp mở công khai trực tiếp. |
| **5. PAM Air Portal** | ~2019 | Hiện tại (thời gian thực) | 5–15 phút | Có thể tổng hợp theo giờ. | Không thể kiểm chứng dải dữ liệu lịch sử đầy đủ qua cổng công khai nếu không có hợp đồng/API đối tác. |
| **6. NOAA ISD 48820** | **2023-01-01T00:00** (xác nhận từ file CSV) | **2024-12-31** (xác nhận từ file CSV) | ~30 phút (METAR FM-15) | Không đúng giờ chẵn | **2023:** 17,178 bản ghi, 365/365 ngày, trung bình 47.1 obs/ngày. **2024:** 16,704 bản ghi, **359/366 ngày** (7 ngày thiếu). Cần resampling về 1h trước khi dùng. |

---

## 6. Đối Chiếu Biến Số Với Canonical Schema (Variable Availability)

Bảng đối chiếu danh mục trường dữ liệu ứng viên so với **Canonical Data Schema** (xác lập tại `docs/data_dictionary.md`):

| Trường Canonical | Định nghĩa | Kaggle | OpenAQ v3 | Open-Meteo ERA5 | AirNow DOS CSV | PAM Air Portal | NOAA ISD 48820 |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `timestamp` | Khóa thời gian chuẩn (`Asia/Ho_Chi_Minh`) | Có | Có (`datetime`) | Có (`time`) | Có (`Date (LST)`) | Có | Có (`DATE`) |
| `station_id` | Mã định danh trạm duy nhất | Khuyết/Tự sinh | Có (`location_id=2178`) | Điểm lưới tọa độ | Có (`Site: Hanoi`) | Có mã trạm PAM | Có (`STATION=48820099999`) |
| `location` | Tên địa danh mô tả | Tùy file | Có (`location`) | Tọa độ / City name | Có | Có tên điểm đo | Có (`NAME`) |
| `pm25` | Nồng độ bụi mịn $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) | Có | **Có (BAM-1020, 14,424 rows)** | Không có | **Có (BAM-1020)** | Có (Cảm biến quang học) | **Không có** |
| `pm10` | Bụi thô $\text{PM}_{10}$ ($\mu\text{g/m}^3$) | Tùy file | **Có** (xác nhận S3: pm10 parameter hiện diện 2023–2024) | Không có | Không có | Tùy trạm | **Không có** |
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

### 7.1. OpenAQ REST API v3 (S3 Public Archive – Location 2178)

- **Phương thức truy xuất đã xác nhận:** Kho lưu trữ S3 công khai tại `openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=2178/` — không yêu cầu API key. Dữ liệu tổ chức theo cấu trúc `year={YYYY}/month={MM}/location-2178-{YYYYMMDD}.csv.gz`.
- **Cấu trúc file S3 (xác nhận thực tế):**
  ```
  location_id, sensors_id, location, datetime, lat, lon, parameter, units, value
  2178, <id>, "US Diplomatic Post: Hanoi", "2024-11-15T00:00:00+07:00", 21.0215, 105.8184, "pm25", "µg/m³", 45.2
  ```
- **Parameters thực tế:** `pm25`, `pm10`, `no2`, `co`, `so2`, `o3`, `no`, `nox` (8 thông số đo được xác nhận từ file CSV).
- **Kiểu dữ liệu:** `datetime` là chuỗi ISO 8601 có timezone; `value` kiểu số thực; `parameter` kiểu chuỗi.
- **Đặc tính khuyết thiếu:** Khi mất tín hiệu trạm, bản ghi không xuất hiện (khuyết dòng tự nhiên). **pm25 completeness: 69.1% (2023), 95.3% (2024)**. Không phải 0% missing.
- **Tính chuẩn xác thiết bị:** Dữ liệu bắt nguồn từ thiết bị đo Met One BAM-1020 đạt tiêu chuẩn tương đương chuẩn liên bang Hoa Kỳ (US EPA Federal Equivalent Method - FEM Designation EQPM-0308-170).
- **REST API:** Yêu cầu `X-API-Key` header cho tất cả endpoints (trả về 401 nếu thiếu). Xem [openaq.org/developers](https://openaq.org/developers) để đăng ký key miễn phí.

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
- **Tính đầy đủ (xác nhận):** 0/8,760 missing (2023), 0/8,784 missing (2024) cho tất cả 6 biến số. Hoàn chỉnh tuyệt đối.

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
| **2. OpenAQ v3** | **Open Database License (ODC-BY) v1.0** | Bắt buộc ghi nhận: *"Data provided by OpenAQ and data originators (US Department of State / EPA)"* | **Cho phép hoàn toàn** cho nghiên cứu học thuật, giáo dục và công bố mở |
| **3. Open-Meteo ERA5** | **Creative Commons Attribution 4.0 International (CC BY 4.0)** | Bắt buộc trích dẫn: *"Weather data by Open-Meteo.com under CC BY 4.0, containing modified Copernicus Climate Change Service information (ERA5)"* | **Cho phép hoàn toàn** cho nghiên cứu phi thương mại và học thuật |
| **4. AirNow DOS CSV** | **U.S. Public Domain** (Tác phẩm của Chính phủ Hoa Kỳ) | Khuyến nghị ghi rõ nguồn US Department of State / AirNow | Sử dụng tự do |
| **5. PAM Air Portal** | **Bản quyền sở hữu trí tuệ của D&L JSC** | Phải xin phép bằng văn bản từ D&L Corp | Nghiêm cấm scrape hoặc khai thác tự động khi chưa được cấp phép |
| **6. NOAA ISD** | **U.S. Public Domain** (Dữ liệu chính phủ Hoa Kỳ / WMO) | Khuyến nghị ghi rõ nguồn NOAA NCEI / WMO Station 48820 | Sử dụng tự do cho mọi mục đích phi thương mại và học thuật |

---

## 10. Ma Trận So Sánh Nguồn Dữ Liệu (Source Comparison Matrix)

Bảng tổng hợp đánh giá khách quan dựa trên toàn bộ các tiêu chí đã thẩm định:

| Tiêu chí thẩm định | 1. Kaggle Hanoi | 2. OpenAQ v3 | 3. Open-Meteo ERA5 | 4. AirNow DOS CSV | 5. PAM Air Portal | 6. NOAA ISD 48820 |
|---|---|---|---|---|---|---|
| **Địa lý** | Hà Nội (Không rõ trạm) | Hà Nội (ĐSQ HK, lõi đô thị) | Hà Nội (Lưới ERA5 $0.25^\circ$) | Hà Nội (ĐSQ HK) | Hà Nội (>50 trạm nội thành) | Nội Bài (20km ngoại thành) |
| **Bao phủ thời gian** | Rời rạc / Tùy file | 2016–Nay (S3 xác nhận 2023–2024) | 1940–Nay (2023–2024 đầy đủ) | 2016–2023 | 2019–Nay | 2023–2024 xác nhận |
| **Tần suất** | 1 giờ | 1 giờ | **1 giờ cố định** | 1 giờ | 5–15 phút | ~30 phút (cần resample) |
| **Biến PM2.5** | Có | **Có (BAM-1020, 82.2% complete)** | Không | **Có (BAM-1020)** | Có (cảm biến quang học) | **Không** |
| **Biến PM10** | Tùy file | **Có (xác nhận S3)** | Không | Không | Tùy nốt | **Không** |
| **Biến Khí tượng** | Một số (ghép sẵn) | Không có | **Đầy đủ 6/6 biến, 0% missing** | Không có | Thiếu gió/áp suất | 4/6 biến (thiếu precip, surface_pressure) |
| **Định dạng** | File tĩnh CSV | REST API (JSON) + S3 CSV.gz | REST API (JSON) | File tĩnh CSV | Web đóng | File CSV công khai |
| **Tái lập (Reproducibility)** | Thấp | **Cao** (REST, S3 không cần key) | **Xuất sắc** (Không cần key) | Trung bình (Tải thủ công) | **Không khả thi** | **Cao** (HTTP trực tiếp) |
| **Giấy phép** | Không rõ / Đa dạng | **ODC-BY v1.0** (Chuẩn mở) | **CC BY 4.0** (Chuẩn mở) | **Public Domain** | **Bản quyền đóng D&L** | **Public Domain** |
| **Hạn chế kỹ thuật** | Rủi ro rò rỉ; đã tiền xử lý | Cần API key cho REST; thiếu 17.8% pm25 | Lưới tái phân tích ~25km | Format cũ; `-999` missing | Không có API công khai | Cần giải mã ISD; thiếu precip/pressure; vị trí lệch 20km |

---

## 11. Bảng Ánh Xạ Sang Canonical Schema (Canonical Schema Mapping)

Sau khi kiểm chứng cấu trúc payload và header thực tế của các nguồn được lựa chọn, bảng ánh xạ trường dữ liệu được xác lập chính thức:

| Trường Canonical | Kiểu dữ liệu | Đơn vị chuẩn | Nguồn dữ liệu | Tên trường tại nguồn (Provider Field) | Đơn vị gốc | Quy tắc chuyển đổi bắt buộc (Transformation Required) |
|---|---|---|---|---|---|---|
| `timestamp` | `datetime64[ns, Asia/Ho_Chi_Minh]` | ISO 8601 (UTC+7) | OpenAQ S3 / Open-Meteo | `datetime` (OpenAQ S3)<br>`time` (Open-Meteo) | ISO 8601 có timezone (OpenAQ)<br>Local string với timezone query (Open-Meteo) | OpenAQ S3: Parse ISO string có offset `+07:00` → tz-aware datetime.<br>Open-Meteo: Truy vấn với `&timezone=Asia/Ho_Chi_Minh`, parse datetime và gán timezone UTC+7.<br>Căn chỉnh đồng nhất làm trục thời gian hợp nhất. |
| `station_id` | `string` | Mã định danh trạm | OpenAQ | `location_id` | Integer ID | Chuẩn hóa thành mã danh mục duy nhất: `VN001_HANOI_US_EMBASSY`. |
| `location` | `string` | Tên địa danh | OpenAQ S3 | `location` | String | Giá trị thực tế: `"US Diplomatic Post: Hanoi"`, chuẩn hóa khoảng trắng và UTF-8. |
| `pm25` | `float64` | $\mu\text{g/m}^3$ | OpenAQ S3 | `value` (khi `parameter == "pm25"`) | $\mu\text{g/m}^3$ | Lọc `parameter == 'pm25'`. Ép kiểu `Float64`. Kiểm tra giá trị âm $\le 0$ → `NaN`. |
| `pm10` | `float64` | $\mu\text{g/m}^3$ | OpenAQ S3 | `value` (khi `parameter == "pm10"`) | $\mu\text{g/m}^3$ | Lọc `parameter == 'pm10'`. Ép kiểu `Float64`. Completeness cần kiểm chứng thêm tại Issue #3. |
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
│    • PRIMARY SOURCE  : OpenAQ REST API v3 / S3 Archive (locationId=2178) │
│    • BACKUP SOURCE   : AirNow US Department of State Historical CSV      │
│    • REFERENCE ONLY  : Kaggle Hanoi Datasets                             │
│    • UNUSED          : PAM Air Portal (Lý do: Bản quyền đóng, API đóng) │
│                                                                          │
│ 2. METEOROLOGY (WEATHER):                                                │
│    • PRIMARY SOURCE  : Open-Meteo Historical Weather API (ERA5)          │
│    • BACKUP SOURCE   : NOAA ISD (WMO Station 48820 – Nội Bài Airport)   │
│    • UNUSED          : PAM Air Portal (Lý do: Không đủ 6 biến số)       │
└──────────────────────────────────────────────────────────────────────────┘
```

### 12.1. Nguồn Dữ Liệu Ô Nhiễm Không Khí (Air Quality)

- **Nguồn Chính (Primary Source): OpenAQ REST API v3 / S3 Archive (location_id=2178)**
  - *Lý do chọn:*
    1. Cung cấp dữ liệu quan trắc từ thiết bị đo Met One BAM-1020 đạt chuẩn tương đương liên bang (US EPA FEM), bảo đảm tính chuẩn xác khoa học cao nhất tại Hà Nội.
    2. Profiling thực tế: **14,424 bản ghi pm25** trong giai đoạn 2023–2024 (82.2% completeness: 69.1% năm 2023, 95.3% năm 2024).
    3. Kho S3 công khai (`openaq-data-archive.s3.amazonaws.com`) cho phép tải file CSV.gz theo ngày mà không cần API key — tăng tính tái lập.
    4. **Phát hiện mới:** Location 2178 cũng cung cấp `pm10` và các thông số khác (no2, co, so2, o3, no, nox) — mở rộng khả năng phân tích.
    5. Giấy phép bản quyền mở ODC-BY v1.0 cho phép khai thác học thuật minh bạch.
  - *Lưu ý về completeness:* pm25 2023 chỉ đạt 69.1% (6,049/8,760 giờ). Pipeline Issue #3 cần xử lý khoảng khuyết bằng `NaN` (không impute tự động) và kiểm đếm row sau khi tải để phát hiện dropout kéo dài.

- **Nguồn Dự Phòng (Backup Source): AirNow US Department of State Historical CSV**
  - *Lý do chọn:* Lưu trữ dữ liệu từ cùng trạm BAM-1020. Đóng vai trò kiểm chứng đối chuẩn (*cross-validation*) và phương án dự phòng ngoại tuyến nếu API/S3 OpenAQ gặp sự cố. Chỉ có đến cuối 2023.

- **Nguồn Tham Chiếu (Reference Only): Kaggle Hanoi Datasets**
  - *Lý do:* Chỉ dùng để đối sánh các chỉ số phân phối thống kê đã công bố; tuyệt đối không dùng làm nguồn nạp chính.

- **Nguồn Loại Bỏ (Unused): PAM Air Portal**
  - *Lý do:* Không có API công khai miễn phí; giấy phép dữ liệu đóng; cảm biến quang học dễ bị trôi và nhiễu ẩm mà không có trạm hiệu chuẩn kèm theo.

### 12.2. Nguồn Dữ Liệu Khí Tượng Bề Mặt (Weather)

- **Nguồn Chính (Primary Source): Open-Meteo Historical Weather API (ERA5 Reanalysis)**
  - *Lý do chọn:*
    1. Cung cấp đầy đủ 6/6 biến số khí tượng Canonical Schema tại đúng tọa độ gần trạm OpenAQ.
    2. **0% missing** cho toàn bộ 17,544 giờ (2023–2024) – xác nhận thực nghiệm từ API call trực tiếp.
    3. API công khai hoàn toàn, không yêu cầu key, không cần xác thực.
    4. Giấy phép mở CC BY 4.0.

- **Nguồn Dự Phòng (Backup Source): NOAA Integrated Surface Database (ISD – Station 48820099999 Nội Bài Airport)**
  - *Hồ sơ profiling thực tế:*
    - Tệp file 2023: 17,178 bản ghi, 365/365 ngày, trung bình 47.1 obs/ngày (~30 phút/lần).
    - Tệp file 2024: 16,704 bản ghi, 359/366 ngày (7 ngày thiếu dữ liệu).
    - TMP missing 2023: 0/17,178 (0.0%). SLP missing 2023: 0/17,178 (0.0%).
    - **Thiếu:** `precipitation` (AA1/AA2 không có trong phần lớn bản ghi), `surface_pressure` trực tiếp (chỉ có SLP cần hiệu chỉnh).
    - **Tần suất không đều:** cần resampling về 1 giờ (e.g. lấy giá trị gần nhất trong cửa sổ ±30 phút).
    - **Vị trí lệch:** Nội Bài (21.221°N, 105.807°E) cách trạm PM2.5 ~20km về phía Bắc — sai số vi khí hậu đô thị đáng kể.
  - *Lý do xếp là Backup:* Open-Meteo hoàn toàn đáp ứng yêu cầu; NOAA chỉ dự phòng nếu ERA5 không khả dụng.

---

## 13. Hạn Chế & Bất Định Kỹ Thuật Chưa Giải Quyết (Limitations & Uncertainties)

1. **PM2.5 completeness 2023 thấp (69.1%):** Giai đoạn 2023 có nhiều khoảng khuyết lớn tại trạm OpenAQ location_id=2178. Pipeline Issue #3 phải kiểm đếm row sau tải và lập báo cáo khoảng khuyết chi tiết (ngày/tháng bị missing). Không impute tự động.
2. **PM10 completeness chưa xác định:** Location 2178 xác nhận có PM10 nhưng completeness năm 2023 chưa được đếm riêng trong profiling phase này. Cần kiểm tra thêm tại Issue #3.
3. **Đại diện không gian đơn trạm:** Dữ liệu $\text{PM}_{2.5}$ phản ánh nồng độ tại khu vực lõi nội thành Hà Nội (Ba Đình / Đống Đa), chưa phản ánh toàn diện các khu vực ngoại thành hoặc khu công nghiệp ven đô. Hạn chế này cần nêu rõ trong Datasheet for Dataset tại Issue #14.
4. **Độ phân giải không gian của ERA5:** Dữ liệu khí tượng Open-Meteo xuất phát từ lưới ERA5 kích thước $\approx 25\,\text{km} \times 25\,\text{km}$. Điểm lưới thực tế ($21.054^\circ\text{N}, 105.898^\circ\text{E}$) cách trạm PM2.5 ($21.022^\circ\text{N}, 105.818^\circ\text{E}$) khoảng **8 km** – chấp nhận được trong nghiên cứu tầm đô thị.
5. **Giới hạn Rate Limit OpenAQ v3 REST API:** Cần API key và áp dụng rate limit. Pipeline Issue #3 ưu tiên dùng S3 archive (không cần key) cho dữ liệu lịch sử; REST API chỉ dùng cho dữ liệu real-time.
6. **NOAA ISD thiếu 2 biến Canonical:** `precipitation` và `surface_pressure` không đầy đủ trong file ISD 48820. NOAA chỉ dùng làm backup thời tiết, không thể thay thế Open-Meteo.

---

## 14. Yêu Cầu Bàn Giao Kỹ Thuật Cho Issue #3 & Issue #4 (Handoff Requirements)

Quyết định tại Issue #19 chuyển giao các yêu cầu đặc tả kỹ thuật bắt buộc cho hai issue tiếp theo:

### 14.1. Handoff cho Issue #3 (Pipeline Thu thập & Chuẩn hóa Dữ liệu Ô nhiễm)

- **Endpoint S3 (ưu tiên cho lịch sử):** `s3://openaq-data-archive/records/csv.gz/locationid=2178/year={YYYY}/month={MM}/location-2178-{YYYYMMDD}.csv.gz`.
- **Endpoint REST API (cho real-time):** `https://api.openaq.org/v3/sensors/{id}/hours` — cần `X-API-Key`.
- **Trạm quan trắc:** location_id=2178 (`US Diplomatic Post: Hanoi`).
- **Thông số:** Lọc `parameter == 'pm25'`; cũng tải `pm10` để kiểm tra completeness.
- **Dải thời gian:** `2023-01-01` đến `2024-12-31`.
- **Yêu cầu adapter:**
  - Parse `datetime` với timezone từ S3 (ISO 8601 có offset `+07:00`).
  - Lọc dòng theo `parameter`; kiểm tra giá trị âm → `NaN`.
  - **Kiểm đếm row bắt buộc:** Assert tổng dòng pm25 ≥ 14,000 (baseline từ profiling này).
  - Lưu tệp thô bất biến vào `data/raw/openaq_raw_2023_2024.parquet` (chế độ chỉ đọc).
  - Cập nhật `data/raw/metadata.json` với source URL, extraction date, và license.

### 14.2. Handoff cho Issue #4 (Pipeline Thu thập & Đồng Bộ Dữ liệu Khí Tượng)

- **Endpoint mục tiêu:** `https://archive-api.open-meteo.com/v1/archive`.
- **Tọa độ truy vấn:** `latitude=21.0285&longitude=105.8542`.
- **Dải thời gian:** `start_date=2023-01-01` đến `end_date=2024-12-31`.
- **Tham số biến số:**
  `hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,surface_pressure`.
- **Tham số kỹ thuật:**
  `&wind_speed_unit=ms&timezone=Asia%2FHo_Chi_Minh`.
- **Yêu cầu adapter:**
  - Tải toàn bộ khối 2 năm trong một hoặc hai batch request.
  - **Kiểm đếm row bắt buộc:** Assert `len(df) == 17,544` (365 ngày × 24h + 366 ngày × 24h = 8,760 + 8,784 = **17,544** – xác nhận từ API call thực tế).
  - Assert 0 missing values trên tất cả 6 biến trước khi lưu.
  - Lưu tệp thô bất biến vào `data/raw/open_meteo_raw_2023_2024.json` (chế độ chỉ đọc).
  - Cập nhật `data/raw/metadata.json` với thông tin truy vấn và giấy phép CC BY 4.0.
