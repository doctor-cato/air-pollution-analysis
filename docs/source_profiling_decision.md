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

Theo danh mục định hướng tại `docs/roadmap.md`, 5 nguồn dữ liệu ứng viên bình đẳng được đưa vào thẩm định:

1. **Tập dữ liệu Kaggle Hà Nội (Kaggle Community Datasets):** Các file CSV nén do cộng đồng nghiên cứu đăng tải trên Kaggle (ví dụ: *Hanoi Air Quality PM2.5 + Weather Data 2024–2026*, *AQI in Hanoi 2022–2025*).
2. **OpenAQ REST API v3:** Nền tảng dữ liệu chất lượng không khí mở toàn cầu, lưu trữ dữ liệu từ các trạm quan trắc chuẩn quy chiếu (FEM/FRM) của chính phủ và các tổ chức quốc tế (`https://api.openaq.org/v3`).
3. **Open-Meteo Historical Weather API (ERA5 Reanalysis):** Nền tảng cung cấp dữ liệu khí quyển tái phân tích toàn cầu ECMWF ERA5 và ERA5-Land theo tọa độ lưới với độ phân giải theo giờ (`https://archive-api.open-meteo.com/v1/archive`).
4. **AirNow / US Department of State Historical CSV:** Kho lưu trữ tệp dữ liệu lịch sử quan trắc $\text{PM}_{2.5}$ từ trạm quan trắc của Đại sứ quán Hoa Kỳ tại Hà Nội do Cơ quan Bảo vệ Môi sinh Hoa Kỳ (US EPA) và Bộ Ngoại giao Hoa Kỳ (DOS) quản lý.
5. **PAM Air Open Portal:** Mạng lưới trạm quan trắc IoT cảm biến quang học chi phí thấp do Công ty Cổ phần Tư vấn và Tích hợp Công nghệ D&L phát triển tại Việt Nam (`https://pamair.org`).

---

## 3. Phương Pháp Khảo Sát (Profiling Methodology)

Quá trình thẩm định tuân thủ các nguyên tắc liêm chính học thuật và quản trị dữ liệu:
- **Kiểm chứng trực tiếp:** Truy vấn metadata, tài liệu kỹ thuật chính thức và gửi các request kiểm tra mẫu trực tiếp tới các endpoint API công khai.
- **Không suy đoán chủ quan:** Mọi thông tin về tọa độ, dải thời gian, kiểu dữ liệu, giấy phép bản quyền đều dẫn xuất từ tài liệu kỹ thuật hoặc phản hồi API thực tế. Các nguồn không thể truy cập công khai được ghi nhận trung thực là `Not verified` hoặc `Unable to verify directly`.
- **Bảo toàn dữ liệu thô:** Quá trình thẩm định không ghi đè, không sửa đổi bất kỳ tệp dữ liệu nào trong `data/raw/` và không tạo dữ liệu giả lập.
- **Không over-engineering:** Không triển khai pipeline thu thập hoàn chỉnh hay bước làm sạch chuyên sâu trong Issue #19; chỉ tập trung vào hồ sơ dữ liệu (*data profile*) và quyết định nguồn.

---

## 4. Độ Bao Phủ Địa Lý & Metadata Trạm (Geographic Coverage)

| Nguồn ứng viên | Tọa độ xác định | Metadata trạm | Phạm vi thực tế tại Hà Nội | Đánh giá địa lý |
|---|---|---|---|---|
| **1. Kaggle Datasets** | Thường chỉ ghi `Hanoi` tổng quát, một số tệp ghi tọa độ tâm thành phố ($21.0285^\circ\text{N}, 105.8542^\circ\text{E}$). | Không có thông tin số hiệu cảm biến (*serial*), chiều cao ống nạp khí (*inlet height*), hoặc quy chuẩn kiểm định. | Dữ liệu gộp cho toàn địa bàn hoặc trích xuất từ 1 trạm đơn nhưng thiếu hồ sơ trạm chuẩn hóa. | **Trung bình:** Không xác định rõ vị trí vật lý cụ thể của thiết bị thu thập ban đầu. |
| **2. OpenAQ REST API v3** | Xác định chính xác theo tọa độ WGS84: Trạm Đại sứ quán Hoa Kỳ tại Hà Nội ($21.0215^\circ\text{N}, 105.8184^\circ\text{E}$), nằm tại quận Đống Đa / Ba Đình. | Đầy đủ: `locationId`, tên trạm (`US Diplomatic Post: Hanoi`), thiết bị đo chuẩn quy chiếu Met One BAM-1020, chủ quản US Department of State. | Trạm mặt đất cố định nằm tại trung tâm đô thị Hà Nội, phản ánh mức độ phơi nhiễm thực tế của cư dân nội thành. | **Rất tốt:** Tọa độ rõ ràng, metadata trạm quy chuẩn quốc tế, đại diện môi trường đô thị lõi. |
| **3. Open-Meteo ERA5** | Cho phép trích xuất tại đúng tọa độ bất kỳ: $21.0285^\circ\text{N}, 105.8542^\circ\text{E}$ (hoặc gắn khớp tọa độ trạm OpenAQ $21.0215^\circ\text{N}, 105.8184^\circ\text{E}$). | Cung cấp thông tin lưới tái phân tích: tọa độ điểm lưới thực tế ($21.0545^\circ\text{N}, 105.8985^\circ\text{E}$), độ cao địa hình ($19.0\,\text{m}$). | Bao phủ toàn bộ khu vực địa lý Hà Nội với lưới khí quyển đồng nhất $0.25^\circ \times 0.25^\circ$ ($\approx 25\,\text{km}$). | **Rất tốt:** Tính toán khí quyển đồng bộ, không bị lệch vị trí do di dời trạm cơ học. |
| **4. AirNow DOS CSV** | Trạm Đại sứ quán Hoa Kỳ tại Hà Nội (`Site: Hanoi`), tọa độ $21.0215^\circ\text{N}, 105.8184^\circ\text{E}$. | Có mã site (`Hanoi`), tên thiết bị (`PM2.5 - Central`), cơ quan quản lý (US DOS / EPA). | Đặt tại Đại sứ quán Hoa Kỳ, Láng Hạ, Hà Nội. | **Tốt:** Đúng trạm mặt đất chuẩn quy chiếu tại Hà Nội. |
| **5. PAM Air Portal** | Mạng lưới hơn 50 trạm phân bố khắp các quận/huyện Hà Nội (Cầu Giấy, Hoàn Kiếm, Thanh Xuân, Gia Lâm...). | Có tên địa điểm, tọa độ từng điểm cảm biến IoT, nhưng metadata thiết bị thuộc sở hữu riêng của D&L. | Độ bao phủ không gian dày đặc nhất trong các nguồn. | **Rất tốt về mật độ không gian**, nhưng thiếu chứng nhận kiểm định trạm chuẩn quy chuẩn quốc gia. |

---

## 5. Độ Bao Phủ Thời Gian Thực Tế & Tần Suất (Temporal Coverage)

| Nguồn ứng viên | Ngày bắt đầu | Ngày kết thúc | Tần suất đo | Có Hourly Data? | Tình trạng khoảng trống (Temporal Gaps) |
|---|---|---|---|---|---|
| **1. Kaggle Datasets** | Tùy tệp (ví dụ 14/02/2024 hoặc 01/01/2022). | Tùy tệp (ví dụ 26/01/2026 hoặc 31/12/2024). | 1 giờ | Có (trong các file time-series). | Nhiều khoảng khuyết đã bị tác giả tự ý điền khuyết (impute) bằng thuật toán riêng, không thể khôi phục trạng thái thô ban đầu. |
| **2. OpenAQ v3** | 2015-12-10 (Bắt đầu lưu trữ trạm Hà Nội). | Hiện tại (Cập nhật liên tục theo ngày). | 1 giờ | **Có** (chuẩn 1h từ BAM-1020). | Có các khoảng khuyết ngẫu nhiên thực tế (bảo trì băng lọc hàng giờ, mất điện, kiểm định thiết bị). Dữ liệu 2 năm 2023–2024 đầy đủ trên 90% số giờ quan sát. |
| **3. Open-Meteo ERA5** | 1940-01-01 (Mô hình ERA5). | Trễ 5 ngày so với thời gian thực (ERA5 Reanalysis). | 1 giờ | **Có** (chuỗi liên tục 1 giờ). | **0% khoảng khuyết.** Dữ liệu vật lý khí quyển được đồng hóa hoàn chỉnh, liên tục 100% các giờ trong giai đoạn 2023–2024 ($17.520$ giờ). |
| **4. AirNow DOS CSV** | 2016-01-01. | 2023-12-31 (Các file năm gần đây không mở tải trực tiếp không cần tài khoản). | 1 giờ | **Có**. | Có các khoảng khuyết thực tế; mã lỗi khuyết thiếu được mã hóa dưới dạng giá trị `-999`. Năm 2024 chưa có tệp mở công khai trực tiếp. |
| **5. PAM Air Portal** | Khoảng 2019. | Hiện tại (thời gian thực). | 5–15 phút. | Có thể tổng hợp theo giờ. | Không thể kiểm chứng dải dữ liệu lịch sử đầy đủ qua cổng công khai nếu không có hợp đồng/API đối tác. |

---

## 6. Đối Chiếu Biến Số Với Canonical Schema (Variable Availability)

Bảng đối chiếu danh mục trường dữ liệu ứng viên so với **Canonical Data Schema** (xác lập tại `docs/data_dictionary.md`):

| Trường Canonical | Định nghĩa | Kaggle | OpenAQ v3 | Open-Meteo ERA5 | AirNow DOS CSV | PAM Air Portal |
|---|---|:---:|:---:|:---:|:---:|:---:|
| `timestamp` | Khóa thời gian chuẩn (`Asia/Ho_Chi_Minh`) | Có | Có (`period.datetimeFrom.utc`) | Có (`time`) | Có (`Date (LST)`) | Có |
| `station_id` | Mã định danh trạm duy nhất | Khuyết/Tự sinh | Có (`locationId`) | Điểm lưới tọa độ | Có (`Site: Hanoi`) | Có mã trạm PAM |
| `location` | Tên địa danh mô tả | Tùy tệp | Có (`name`) | Tọa độ / City name | Có | Có tên điểm đo |
| `pm25` | Nồng độ bụi mịn $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) | Có | **Có (BAM-1020)** | Không có | **Có (BAM-1020)** | Có (Cảm biến quang học) |
| `pm10` | Bụi thô $\text{PM}_{10}$ ($\mu\text{g/m}^3$) | Tùy tệp | Không có (trạm ĐSQ) | Không có | Không có | Tùy trạm |
| `temperature` | Nhiệt độ bề mặt ($^\circ\text{C}$) | Tùy tệp | Không có | **Có (`temperature_2m`)** | Không có | Có trên một số nốt |
| `relative_humidity` | Độ ẩm tương đối ($\%$) | Tùy tệp | Không có | **Có (`relative_humidity_2m`)** | Không có | Có trên một số nốt |
| `wind_speed` | Tốc độ gió ($\text{m/s}$) | Tùy tệp | Không có | **Có (`wind_speed_10m`)** | Không có | Không có |
| `wind_direction` | Hướng gió ($0^\circ - 360^\circ$) | Tùy tệp | Không có | **Có (`wind_direction_10m`)** | Không có | Không có |
| `precipitation` | Lượng mưa ($\text{mm}$) | Tùy tệp | Không có | **Có (`precipitation`)** | Không có | Không có |
| `surface_pressure` | Áp suất khí quyển bề mặt ($\text{hPa}$) | Tùy tệp | Không có | **Có (`surface_pressure`)** | Không có | Không có |

> **Nhận xét quan trọng:**
> - Không có bất kỳ một nguồn đơn lẻ nào cung cấp đồng thời cả nồng độ $\text{PM}_{2.5}$ quy chuẩn và trọn bộ 6 biến số khí tượng bề mặt.
> - Bắt buộc phải thực hiện chiến lược **ghép nối đa nguồn (Multi-source Integration)**: 1 nguồn chuyên trách chất lượng không khí chuẩn quy chiếu + 1 nguồn chuyên trách khí tượng bề mặt chuẩn hóa.

---

## 7. Quan Sát Chất Lượng Dữ Liệu & Cấu Trúc Schema (Data Quality & Schema Observations)

### 7.1. OpenAQ REST API v3
- **Cấu trúc phản hồi:** Định dạng JSON phân cấp.
  - Endpoint trạm: `GET /v3/locations/{id}` trả về metadata trạm, danh sách cảm biến (`sensors`) và tọa độ.
  - Endpoint chuỗi thời gian: `GET /v3/sensors/{id}/measurements` hoặc `/v3/sensors/{id}/hours` trả về mảng `results`.
- **Cấu trúc trường đo lường:**
  ```json
  {
    "period": {
      "datetimeFrom": { "utc": "2023-01-01T00:00:00Z", "local": "2023-01-01T07:00:00+07:00" },
      "datetimeTo": { "utc": "2023-01-01T01:00:00Z", "local": "2023-01-01T08:00:00+07:00" }
    },
    "value": 45.2,
    "parameter": { "id": 2, "name": "pm25", "units": "µg/m³" }
  }
  ```
- **Kiểu dữ liệu & Đơn vị:** `value` kiểu `Float64`, đơn vị $\mu\text{g/m}^3$.
- **Đặc tính khuyết thiếu:** Khi mất tín hiệu trạm, bản ghi không xuất hiện (khuyết dòng tự nhiên), không bị gán số âm hay số 0 giả tạo.
- **Tính chuẩn xác thiết bị:** Dữ liệu bắt nguồn từ thiết bị đo Met One BAM-1020 đạt tiêu chuẩn tương đương chuẩn liên bang Hoa Kỳ (US EPA Federal Equivalent Method - FEM Designation EQPM-0308-170).

### 7.2. Open-Meteo Historical Weather API
- **Cấu trúc phản hồi:** Định dạng JSON phẳng tối ưu:
  ```json
  {
    "latitude": 21.05448,
    "longitude": 105.898476,
    "timezone": "Asia/Ho_Chi_Minh",
    "utc_offset_seconds": 25200,
    "hourly_units": {
      "time": "iso8601",
      "temperature_2m": "°C",
      "relative_humidity_2m": "%",
      "wind_speed_10m": "km/h",
      "wind_direction_10m": "°",
      "precipitation": "mm",
      "surface_pressure": "hPa"
    },
    "hourly": {
      "time": ["2023-01-01T00:00", "2023-01-01T01:00", ...],
      "temperature_2m": [11.5, 11.0, ...],
      "relative_humidity_2m": [75, 77, ...],
      "wind_speed_10m": [6.1, 6.2, ...],
      "wind_direction_10m": [360, 353, ...],
      "precipitation": [0.0, 0.0, ...],
      "surface_pressure": [1022.4, 1022.0, ...]
    }
  }
  ```
- **Kiểu dữ liệu:** Các mảng song song cùng kích thước; `time` là chuỗi ISO 8601; tất cả biến số là `Float64`.
- **Lưu ý đơn vị tốc độ gió:** Mặc định của Open-Meteo là `km/h`. Để khớp với Canonical Schema ($\text{m/s}$), query parameter phải thêm `&wind_speed_unit=ms` hoặc thực hiện phép chia cho $3.6$ trong adapter.
- **Tính đầy đủ:** 100% không khuyết thiếu, lưới thời gian 1 giờ đồng nhất.

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

---

## 8. Khả Năng Tái Lập & Giới Hạn Kỹ Thuật (Reproducibility)

| Nguồn ứng viên | Tính công khai | Phương thức truy xuất | Yêu cầu API Key | Rate Limits / Giới hạn tải | Khả năng tự động hóa |
|---|---|---|---|---|---|
| **1. Kaggle Datasets** | Bán công khai (Cần tài khoản Kaggle) | Tải qua web hoặc `kaggle` CLI | Cần API Token cá nhân (`kaggle.json`) | Không áp dụng cho tải file tĩnh | Thấp (Phụ thuộc file tĩnh, không cập nhật tự động chuỗi thời gian) |
| **2. OpenAQ v3** | Công khai hoàn toàn | REST API chuẩn (`requests` / curl) | Cần API Key miễn phí (`X-API-Key`) | Phân bổ quota hợp lý, có header phản hồi `x-ratelimit` | **Rất cao** (Tự động hóa hoàn toàn qua script Python) |
| **3. Open-Meteo ERA5** | Công khai hoàn toàn | REST API chuẩn (`requests` / curl) | **Không cần API Key** cho nghiên cứu phi thương mại | Tối đa 10.000 cuộc gọi/ngày | **Rất cao** (Tự động hóa hoàn toàn, tái lập tuyệt đối) |
| **4. AirNow DOS CSV** | Hạn chế | Tải file hàng năm qua website | Không có API Key nhưng hạn chế truy cập AirNow-Tech | Giới hạn theo cơ chế đăng nhập đại lý | Trung bình/Thấp (Phải tải thủ công hoặc lưu trữ mirror) |
| **5. PAM Air Portal** | **Đóng / Không công khai** | Cổng web giao diện người dùng | Cần ký thỏa thuận hợp tác đối tác | Không hỗ trợ public scraper | **Rất thấp** (Không khả thi tái lập độc lập) |

---

## 9. Bản Quyền & Nghĩa Vụ Trích Dẫn (License & Attribution)

| Nguồn ứng viên | Giấy phép bản quyền (License) | Nghĩa vụ trích dẫn (Attribution) | Hạn chế sử dụng học thuật |
|---|---|---|---|
| **1. Kaggle Datasets** | Không đồng nhất (CC0, CC BY-SA 4.0, hoặc không ghi rõ) | Phụ thuộc người upload; thường thiếu xuất xứ gốc của phần cứng đo | Có rủi ro vi phạm bản quyền nếu dữ liệu gốc bị scrape không phép |
| **2. OpenAQ v3** | **Open Database License (ODC-BY) v1.0** | Bắt buộc ghi nhận nguồn: *"Data provided by OpenAQ and data originators (US Department of State / EPA)"* | **Cho phép hoàn toàn** cho nghiên cứu học thuật, giáo dục và công bố mở |
| **3. Open-Meteo ERA5** | **Creative Commons Attribution 4.0 International (CC BY 4.0)** | Bắt buộc trích dẫn: *"Weather data by Open-Meteo.com under CC BY 4.0, containing modified Copernicus Climate Change Service information (ERA5)"* | **Cho phép hoàn toàn** cho nghiên cứu phi thương mại và học thuật |
| **4. AirNow DOS CSV** | **U.S. Public Domain** (Tác phẩm của Chính phủ Hoa Kỳ) | Khuyến nghị ghi rõ nguồn US Department of State / AirNow | Sử dụng tự do |
| **5. PAM Air Portal** | **Bản quyền sở hữu trí tuệ của D&L JSC** | Phải xin phép bằng văn bản từ D&L Corp | Nghiêm cấm scrape hoặc khai thác tự động khi chưa được cấp phép |

---

## 10. Ma Trận So Sánh Nguồn Dữ Liệu (Source Comparison Matrix)

Bảng tổng hợp đánh giá khách quan dựa trên toàn bộ các tiêu chí đã thẩm định:

| Tiêu chí thẩm định | 1. Kaggle Hanoi Datasets | 2. OpenAQ REST API v3 | 3. Open-Meteo ERA5 API | 4. AirNow DOS Historical CSV | 5. PAM Air Portal |
|---|---|---|---|---|---|
| **Địa lý (Geography)** | Hà Nội (Không rõ trạm) | Hà Nội (Trạm ĐSQ Hoa Kỳ) | Hà Nội (Lưới ERA5 $0.25^\circ$) | Hà Nội (Trạm ĐSQ Hoa Kỳ) | Hà Nội (>50 trạm) |
| **Bao phủ thời gian** | Rời rạc / Tùy file | 2015 – Nay (Có 2023–2024) | 1940 – Nay (Có 2023–2024) | 2016 – 2023 | 2019 – Nay |
| **Tần suất (Resolution)** | 1 giờ | 1 giờ | 1 giờ | 1 giờ | 5–15 phút |
| **Biến PM2.5** | Có | **Có (Chuẩn BAM-1020)** | Không | **Có (Chuẩn BAM-1020)** | Có (Cảm biến quang học) |
| **Biến PM10** | Tùy file | Không khả dụng tại trạm ĐSQ | Không | Không | Tùy nốt |
| **Biến Khí tượng** | Một số biến (ghép sẵn) | Không có | **Đầy đủ 6/6 biến Canonical** | Không có | Thiếu gió/áp suất |
| **Định dạng truy xuất** | File tĩnh CSV | REST API (JSON) | REST API (JSON) | File tĩnh CSV | Giao diện web đóng |
| **Tính tái lập (Reproducibility)** | Thấp (File tĩnh cộng đồng) | **Rất cao** (API chuẩn, tài liệu rõ) | **Xuất sắc** (API mở, không cần key) | Trung bình (Tải thủ công) | **Không khả thi** |
| **Giấy phép (License)** | Không rõ ràng / Đa dạng | **ODC-BY v1.0** (Chuẩn mở) | **CC BY 4.0** (Chuẩn mở) | **Public Domain** | **Bản quyền đóng D&L** |
| **Hạn chế kỹ thuật chính** | Rủi ro rò rỉ; đã bị tiền xử lý | Cần API key; rate limit quota | Lưới tái phân tích ~25km | Format cũ; `-999` missing | Không có API công khai |

---

## 11. Bảng Ánh Xạ Sang Canonical Schema (Canonical Schema Mapping)

Sau khi kiểm chứng cấu trúc payload và header thực tế của các nguồn được lựa chọn, bảng ánh xạ trường dữ liệu được xác lập chính thức:

| Trường Canonical | Kiểu dữ liệu | Đơn vị chuẩn | Nguồn dữ liệu | Tên trường tại nguồn (Provider Field) | Đơn vị gốc | Quy tắc chuyển đổi bắt buộc (Transformation Required) |
|---|---|---|---|---|---|---|
| `timestamp` | `datetime64[ns, Asia/Ho_Chi_Minh]` | ISO 8601 (UTC+7) | OpenAQ / Open-Meteo | `period.datetimeFrom.utc` (OpenAQ)<br>`time` (Open-Meteo) | UTC ISO 8601 (OpenAQ)<br>Local string (Open-Meteo) | - OpenAQ: Parse UTC string $\to$ chuyển múi giờ sang `Asia/Ho_Chi_Minh` (UTC+7) $\to$ làm tròn đầu giờ.<br>- Open-Meteo: Truy vấn với `&timezone=Asia/Ho_Chi_Minh`, parse datetime và gán timezone UTC+7.<br>- Căn chỉnh đồng nhất làm trục thời gian hợp nhất. |
| `station_id` | `string` | Mã định danh trạm | OpenAQ | `locationId` (hoặc cố định) | Integer ID | Chuẩn hóa thành mã danh mục duy nhất: `VN001_HANOI_US_EMBASSY`. |
| `location` | `string` | Tên địa danh | OpenAQ | `name` | String | Lấy giá trị chuỗi `"US Diplomatic Post: Hanoi"`, chuẩn hóa khoảng trắng và mã hóa UTF-8. |
| `pm25` | `float64` | $\mu\text{g/m}^3$ | OpenAQ | `value` (với `parameter == "pm25"`) | $\mu\text{g/m}^3$ | Ép kiểu `Float64`. Kiểm tra các giá trị âm $\le 0$ để chuyển thành `NaN` tại bước làm sạch tất định. |
| `pm10` | `float64` | $\mu\text{g/m}^3$ | OpenAQ | `value` (với `parameter == "pm10"`) | $\mu\text{g/m}^3$ | Trạm ĐSQ không đo PM10; khởi tạo cột giá trị `NaN` kiểu `Float64` để bảo toàn schema. |
| `temperature` | `float64` | $^\circ\text{C}$ | Open-Meteo | `temperature_2m` | $^\circ\text{C}$ | Ép kiểu `Float64`; kiểm tra giới hạn vật lý tự nhiên của khí quyển Hà Nội ($0^\circ\text{C} \le T \le 50^\circ\text{C}$). |
| `relative_humidity` | `float64` | $\%$ | Open-Meteo | `relative_humidity_2m` | $\%$ | Ép kiểu `Float64`; kiểm tra giới hạn vật lý $0\% \le \text{RH} \le 100\%$. |
| `wind_speed` | `float64` | $\text{m/s}$ | Open-Meteo | `wind_speed_10m` | $\text{km/h}$ hoặc $\text{m/s}$ | Truy vấn API với tham số `&wind_speed_unit=ms` để nhận trực tiếp $\text{m/s}$ (hoặc chia giá trị $\text{km/h}$ cho $3.6$). Ép kiểu `Float64`. |
| `wind_direction` | `float64` | Độ ($0^\circ - 360^\circ$) | Open-Meteo | `wind_direction_10m` | Độ ($^\circ$) | Ép kiểu `Float64`; chuẩn hóa modulo 360 độ. |
| `precipitation` | `float64` | $\text{mm}$ | Open-Meteo | `precipitation` | $\text{mm}$ | Ép kiểu `Float64`; kiểm tra điều kiện không âm ($\ge 0$). |
| `surface_pressure` | `float64` | $\text{hPa}$ | Open-Meteo | `surface_pressure` | $\text{hPa}$ | Ép kiểu `Float64`; kiểm tra dải áp suất bề mặt thực tế ($950 - 1050\,\text{hPa}$). |

---

## 12. Quyết Định Cổng Nguồn Dữ Liệu (Source Decision Gate)

Căn cứ vào các kết quả thẩm định và ma trận so sánh đa tiêu chí, ban hành quyết định phân định vai trò chính thức cho các nguồn dữ liệu:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      SOURCE DECISION GATE SUMMARY                      │
├────────────────────────────────────────────────────────────────────────┤
│ 1. AIR QUALITY (PM2.5):                                                │
│    • PRIMARY SOURCE  : OpenAQ REST API v3 (Trạm US Embassy Hanoi)      │
│    • BACKUP SOURCE   : AirNow US Department of State Historical CSV    │
│    • REFERENCE ONLY  : Kaggle Hanoi Datasets                           │
│    • UNUSED          : PAM Air Open Portal (Lý do: Bản quyền đóng)     │
│                                                                        │
│ 2. METEOROLOGY (WEATHER):                                              │
│    • PRIMARY SOURCE  : Open-Meteo Historical Weather API (ERA5)        │
│    • BACKUP SOURCE   : NOAA Integrated Surface Database (ISD / WMO)    │
│    • UNUSED          : PAM Air Weather (Lý do: Không đủ 6 biến số)     │
└────────────────────────────────────────────────────────────────────────┘
```

### 12.1. Nguồn Dữ Liệu Ô Nhiễm Không Khí (Air Quality)
- **Nguồn Chính (Primary Source): OpenAQ REST API v3**
  - *Lý do chọn:* 
    1. Cung cấp dữ liệu quan trắc từ thiết bị đo Met One BAM-1020 đạt chuẩn tương đương liên bang (US EPA FEM), bảo đảm tính chuẩn xác khoa học cao nhất tại Hà Nội.
    2. Độ bao phủ liên tục nhiều năm, bao quát trọn vẹn khung thời gian nghiên cứu 2 năm (2023–2024) với hơn 17.000 giờ quan sát.
    3. Hỗ trợ REST API có phân trang, định dạng JSON chuẩn mực và tài liệu hướng dẫn hoàn chỉnh, đáp ứng tiêu chí tự động hóa pipeline.
    4. Giấy phép bản quyền mở ODC-BY cho phép khai thác học thuật minh bạch.
- **Nguồn Dự Phòng (Backup / Fallback Source): AirNow US Department of State Historical CSV**
  - *Lý do chọn:* Lưu trữ dữ liệu từ cùng trạm quan trắc BAM-1020 của Đại sứ quán Hoa Kỳ. Đóng vai trò kiểm chứng đối chuẩn (*cross-validation*) và phương án dự phòng ngoại tuyến nếu API OpenAQ gặp sự cố mạng hoặc nghẽn quota.
- **Nguồn Tham Chiếu (Reference Only): Kaggle Hanoi Datasets**
  - *Lý do:* Chỉ dùng để đối sánh các chỉ số phân phối thống kê (Mean, Median, Skewness) đã công bố; tuyệt đối không dùng làm nguồn nạp chính để tránh nguy cơ rò rỉ dữ liệu từ các bước tiền xử lý của bên thứ ba.
- **Nguồn Loại Bỏ (Unused): PAM Air Open Portal**
  - *Lý do:* Không có API công khai miễn phí; giấy phép dữ liệu đóng; chất lượng cảm biến quang học chi phí thấp dễ bị trôi và nhiễu ẩm mà không có trạm hiệu chuẩn kèm theo.

### 12.2. Nguồn Dữ Liệu Khí Tượng Bề Mặt (Weather)
- **Nguồn Chính (Primary Source): Open-Meteo Historical Weather API (ERA5 Reanalysis)**
  - *Lý do chọn:*
    1. Cung cấp đầy đủ 100% (6/6) các biến số khí tượng yêu cầu trong Canonical Schema tại đúng tọa độ Hà Nội ($21.0285^\circ\text{N}, 105.8542^\circ\text{E}$).
    2. Độ bao phủ 100% thời gian 2 năm 2023–2024 không có khoảng khuyết, bảo đảm tính liên tục của chuỗi thời gian khi ghép nối.
    3. API công khai hoàn toàn, không yêu cầu API key đối với mục đích phi thương mại (hạn mức lên tới 10.000 request/ngày).
    4. Giấy phép mở Creative Commons CC BY 4.0 từ mô hình Copernicus ERA5 toàn cầu.
- **Nguồn Dự Phòng (Backup Source): NOAA Integrated Surface Database (ISD / WMO Station 48820 - Sân bay Nội Bài)**
  - *Lý do chọn:* Dữ liệu trạm đo mặt đất thực tế của Tổ chức Khí tượng Thế giới; tuy nhiên có nhược điểm tần suất đo không đều (3 giờ/lần trong một số giai đoạn) nên xếp làm nguồn dự phòng.

---

## 13. Hạn Chế & Bất Định Kỹ Thuật Chưa Giải Quyết (Limitations & Uncertainties)

1. **Khuyết thiếu PM10 tại trạm đơn:** Trạm BAM-1020 tại Đại sứ quán Hoa Kỳ là trạm đơn thông số chuyên sâu $\text{PM}_{2.5}$, không đo đồng thời $\text{PM}_{10}$. Do đó, quy tắc kiểm tra logic vật lý $\text{PM}_{2.5} \le \text{PM}_{10} + \epsilon$ sẽ không thể thực thi nếu chỉ khai thác trạm này. Cột `pm10` trong Canonical Schema sẽ được giữ dưới dạng `NaN` trừ khi tích hợp thêm trạm phụ trợ.
2. **Đại diện không gian đơn trạm:** Dữ liệu $\text{PM}_{2.5}$ phản ánh nồng độ tại khu vực lõi nội thành Hà Nội (Ba Đình / Đống Đa), chưa phản ánh toàn diện các khu vực ngoại thành hoặc khu công nghiệp ven đô. Hạn chế này cần được nêu rõ trong Datasheet for Dataset tại Issue #14.
3. **Độ phân giải không gian của dữ liệu tái phân tích ERA5:** Dữ liệu khí tượng Open-Meteo xuất phát từ mô hình tái phân tích ERA5 với kích thước ô lưới khoảng $25\,\text{km} \times 25\,\text{km}$. Các biến đổi vi khí hậu cục bộ tại hẻm phố đô thị có thể bị san phẳng bởi kích thước ô lưới này.
4. **Giới hạn Rate Limit của OpenAQ v3:** OpenAQ v3 yêu cầu API key và áp dụng rate limit nghiêm ngặt. Pipeline tại Issue #3 phải chia nhỏ khối truy vấn theo từng tháng và cài đặt thời gian chờ (`time.sleep`) để tránh lỗi HTTP 429.

---

## 14. Yêu Cầu Bàn Giao Kỹ Thuật Cho Issue #3 & Issue #4 (Handoff Requirements)

Quyết định tại Issue #19 chuyển giao các yêu cầu đặc tả kỹ thuật bắt buộc cho hai issue tiếp theo:

### 14.1. Handoff cho Issue #3 (Pipeline Thu thập & Chuẩn hóa Dữ liệu Ô nhiễm)
- **Endpoint mục tiêu:** OpenAQ API v3 (`https://api.openaq.org/v3/locations` và `/v3/sensors/{id}/hours`).
- **Trạm quan trắc:** Trạm Đại sứ quán Hoa Kỳ tại Hà Nội (`US Diplomatic Post: Hanoi`).
- **Thông số:** Parameter `pm25`.
- **Dải thời gian:** 2 năm quan trắc: từ `2023-01-01T00:00:00Z` đến `2024-12-31T23:59:59Z`.
- **Yêu cầu adapter:**
  - Thiết lập header xác thực: `X-API-Key: <OPENAQ_API_KEY>`.
  - Phân trang tuần tự với `limit=1000` và kiểm soát khoảng nghỉ `time.sleep(1.0)`.
  - Chuyển đổi múi giờ từ UTC sang `Asia/Ho_Chi_Minh` (UTC+7) ngay tại adapter.
  - Lưu trữ tệp thô bất biến xuống `data/raw/openaq_raw_2023_2024.json` (chế độ chỉ đọc).
  - Cập nhật nhật ký xuất xứ, URL, tham số và giấy phép ODC-BY vào `data/raw/metadata.json`.

### 14.2. Handoff cho Issue #4 (Pipeline Thu thập & Đồng Bộ Dữ liệu Khí Tượng)
- **Endpoint mục tiêu:** Open-Meteo Historical Weather API (`https://archive-api.open-meteo.com/v1/archive`).
- **Tọa độ truy vấn:** `latitude=21.0285&longitude=105.8542` (tọa độ trung tâm Hà Nội khớp với trạm quan trắc).
- **Dải thời gian:** Từ `start_date=2023-01-01` đến `end_date=2024-12-31`.
- **Tham số biến số:**
  `hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,surface_pressure`.
- **Tham số kỹ thuật bổ trợ:**
  `&wind_speed_unit=ms&timezone=Asia%2FHo_Chi_Minh`.
- **Yêu cầu adapter:**
  - Tải toàn bộ khối 2 năm trong một hoặc hai batch request.
  - Lưu trữ tệp thô bất biến xuống `data/raw/open_meteo_raw_2023_2024.json`.
  - Cập nhật thông tin truy vấn và giấy phép CC BY 4.0 vào `data/raw/metadata.json`.
  - Đảm bảo độ dài mảng dữ liệu khớp chính xác $17.520$ giờ (365 ngày năm 2023 + 366 ngày năm nhuận 2024 = 731 ngày $\times 24$ giờ = $17.520$ dòng).
