# Từ Điển Dữ Liệu Chuẩn Hóa (Canonical Data Dictionary)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)  
> **Căn cứ kỹ thuật:** Lộ trình đồ án [`docs/roadmap.md`](roadmap.md), GitHub Issue #2, và phương pháp luận CRISP-DM.  
> **Tài liệu tham chiếu:** [`docs/research_questions.md`](research_questions.md)  
> **Nguyên tắc thiết kế:** Trung lập với nguồn cung cấp dữ liệu (*Source-Independent Canonical Schema*), bảo toàn đơn vị quan trắc, không giả định trước ánh xạ cột khi chưa kiểm chứng thực tế qua Issue #19.

---

## 1. Mục Đích & Nguyên Tắc Thiết Kế Lược Đồ (Purpose & Design Principles)

### 1.1. Mục đích
Trong các dự án khoa học dữ liệu môi trường và chuỗi thời gian thực tế, dữ liệu thường được thu thập từ nhiều nhà cung cấp khác nhau (ví dụ: các trạm quan trắc mặt đất thương mại, API chính phủ, nền tảng cộng đồng hoặc các mô hình tái phân tích khí hậu toàn cầu). Mỗi nguồn dữ liệu sở hữu định dạng cấu trúc, quy ước đặt tên cột, đơn vị đo lường và định dạng mốc thời gian riêng biệt:
- Một nguồn có thể đặt tên là `PM2.5`, nguồn khác đặt là `pm25`, `pm2_5`, hoặc `value` đi kèm metadata tham số.
- Đơn vị đo nhiệt độ có thể là $^\circ\text{C}$ hoặc Kelvin; áp suất có thể là $\text{hPa}$ hoặc $\text{Pa}$; múi giờ có thể là UTC hoặc giờ địa phương chưa khai báo.

Để đảm bảo tính module hóa, khả năng bảo trì và ngăn ngừa việc mã nguồn phân tích phụ thuộc chặt chẽ vào một tập dữ liệu thô đơn lẻ, dự án thiết lập **Lược đồ Dữ liệu Chuẩn hóa Trung lập (Canonical Data Schema)**. 

### 1.2. Luồng chuẩn hóa qua Adapter (Source Data Ingestion Flow)

Lược đồ chuẩn hóa đóng vai trò là "bản khế ước giao diện" (Interface Contract). Mọi nguồn dữ liệu thô khi thu thập vào dự án sẽ được ánh xạ thông qua các bộ chuyển đổi chuyên biệt (*Source-specific Adapters*):

```text
┌─────────────────────────────────┐
│ Nguồn thô 1: Trạm quan trắc     │
│ (VD: OpenAQ, AirNow, PAM Air)   │──┐
└─────────────────────────────────┘  │
                                     ▼
┌─────────────────────────────────┐ ┌───────────────────────────┐      ┌─────────────────────────────┐
│ Nguồn thô 2: Khí tượng bề mặt   │─► Adapter chuyên biệt       │ ───► │ CANONICAL DATA SCHEMA       │
│ (VD: Open-Meteo, ERA5)          │  │ (Đổi tên, ép kiểu,     │      │ (Bảng dữ liệu chuẩn hóa,     │
└─────────────────────────────────┘  │  chuyển đơn vị, múi giờ)  │      │  độc lập nguồn cung cấp)    │
                                     └───────────────────────────┘      └──────────────┬──────────────┘
┌─────────────────────────────────┐  ▲                                                 │
│ Nguồn thô 3: Tập dữ liệu mở     │  │                                                 ▼
│ (VD: File CSV lưu trữ Kaggle)   │──┘                                  ┌─────────────────────────────┐
└─────────────────────────────────┘                                     │ Phân tích EDA, OLS,         │
                                                                        │ Mô hình phân loại cảnh báo  │
                                                                        └─────────────────────────────┘
```

Mọi phân tích khám phá dữ liệu (EDA), kiểm định thống kê và huấn luyện mô hình học máy phía sau chỉ tương tác duy nhất với các trường thuộc Canonical Schema này, không bao giờ truy cập trực tiếp vào định dạng thô của từng nhà cung cấp.

---

## 2. Lược Đồ Dữ Liệu Chuẩn Hóa Tổng Thể (Canonical Schema Overview)

Bảng tổng hợp các trường chuẩn hóa tối thiểu trong dự án:

| STT | Tên trường chuẩn hóa (Canonical Field) | Kiểu dữ liệu (Datatype) | Đơn vị chuẩn (Unit) | Vai trò phân tích (Analytical Role) | Tính sẵn sàng (Availability) | Khóa quan trắc (Observation Key) |
|:---:|---|---|---|---|---|---|
| 1 | `timestamp` | `datetime64[ns, Asia/Ho_Chi_Minh]` | ISO 8601 (UTC+7) | Trục thời gian chuẩn | Bắt buộc (Mandatory) | Khóa chính thời gian |
| 2 | `station_id` | `string` | Định danh trạm | Định danh thực thể quan trắc | Bắt buộc (Mandatory) | Khóa phân nhóm / Ghép nối |
| 3 | `location` | `string` | Tên địa danh | Metadata mô tả người đọc | Tùy chọn (Descriptive) | Không làm khóa ghép |
| 4 | `pm25` | `float64` | $\mu\text{g/m}^3$ | **Biến mục tiêu cốt lõi** ($Y$) | Bắt buộc (Mandatory) | Biến đo lường chất lượng |
| 5 | `pm10` | `float64` | $\mu\text{g/m}^3$ | Biến bổ trợ / Kiểm toán logic | Tùy chọn (Optional) | Biến đo lường chất lượng |
| 6 | `temperature` | `float64` | $^\circ\text{C}$ | Biến giải thích thời tiết ($X_1$) | Nguồn phụ thuộc (Weather) | Biến khí tượng |
| 7 | `relative_humidity` | `float64` | $\%$ | Biến giải thích thời tiết ($X_2$) | Nguồn phụ thuộc (Weather) | Biến khí tượng |
| 8 | `wind_speed` | `float64` | $\text{m/s}$ | Biến giải thích thời tiết ($X_3$) | Nguồn phụ thuộc (Weather) | Biến khí tượng |
| 9 | `wind_direction` | `float64` | Độ ($0^\circ - 360^\circ$) | Biến giải thích thời tiết ($X_4$) | Nguồn phụ thuộc (Weather) | Biến khí tượng |
| 10 | `precipitation` | `float64` | $\text{mm}$ | Biến giải thích thời tiết ($X_5$) | Nguồn phụ thuộc (Weather) | Biến khí tượng |
| 11 | `surface_pressure` | `float64` | $\text{hPa}$ | Biến giải thích thời tiết ($X_6$) | Nguồn phụ thuộc (Weather) | Biến khí tượng |

---

## 3. Các Quy Ước Kỹ Thuật Trọng Tâm (Key Conventions)

### 3.1. Quy ước Mốc Thời Gian (Timestamp Convention)
- **Vai trò:** `timestamp` là khóa thời gian chính (*Primary Temporal Key*) của mọi chuỗi dữ liệu trong dự án.
- **Múi giờ chuẩn:** Toàn bộ dữ liệu trong Canonical Schema bắt buộc phải được chuyển đổi đồng nhất về múi giờ địa phương Việt Nam: **`Asia/Ho_Chi_Minh` (UTC+7)**.
- **Phân định rõ ràng múi giờ:**
  - Nếu nguồn cung cấp chuỗi thời gian ở dạng UTC (ví dụ: mốc thời gian kết thúc bằng `Z` hoặc ISO 8601 UTC), adapter nạp dữ liệu có trách nhiệm chuyển đổi sang UTC+7 trước khi đưa vào lược đồ chuẩn.
  - Tuyệt đối không để xảy ra tình trạng "mập mờ múi giờ" (naive datetime) dẫn đến hiện tượng trượt pha 7 tiếng giữa dữ liệu ô nhiễm và khí tượng (ví dụ: nhiệt độ cực đại buổi chiều bị lệch sang nửa đêm).
- **Trường hợp nguồn không ghi rõ múi giờ:** Adapter phải gắn cờ cần kiểm chứng tại Issue #19, đối chiếu quy luật nhiệt độ ngày đêm (đỉnh nhiệt độ thực tế phải rơi vào khung giờ $13:00 - 15:00$) trước khi kết luận độ lệch múi giờ.

### 3.2. Quy ước Định Danh Trạm Quan Trắc (Station ID Convention)
- **Vai trò:** `station_id` là mã định danh kỹ thuật (machine-oriented identifier), có tính ổn định và duy nhất cho từng trạm quan trắc mặt đất hoặc điểm lưới trích xuất.
- **Tập dữ liệu đơn trạm (Single-station Dataset):**  
  Nếu tập dữ liệu thô chỉ thu thập từ một trạm duy nhất (hoặc nguồn không cung cấp cột mã trạm rõ ràng), adapter có trách nhiệm gán một mã trạm cố định, nhất quán và được tài liệu hóa rõ ràng trong cấu hình (ví dụ: `VN001_HANOI_US_EMBASSY` hoặc theo mã trạm quy định tại Issue #19).
- **Tập dữ liệu đa trạm (Multi-station Dataset):**  
  Mỗi trạm quan trắc phải được định danh bằng một `station_id` chuẩn hóa độc lập, không trùng lặp.
- **Khác biệt cốt lõi giữa `station_id` và `location`:**
  - `station_id`: Khóa kỹ thuật dùng cho việc lập chỉ mục, phân nhóm (`groupby`), phân chia tập dữ liệu và thực hiện phép ghép nối dữ liệu (`join/merge`).
  - `location`: Chuỗi văn bản mang tính mô tả vị trí cho con người đọc (ví dụ: "7 Lang Ha, Ba Dinh, Hanoi"). **Tuyệt đối không sử dụng `location` làm khóa chính ghép nối**, vì văn bản địa danh dễ bị thay đổi định dạng, lỗi dấu tiếng Việt hoặc sai khác khoảng trắng.

### 3.3. Quy ước Khóa Quan Trắc Duy Nhất (Observation Key)
- **Tập quan sát đa trạm:** Cặp khóa định danh duy nhất cho một dòng quan sát là:
  $$\text{Observation Key} = (\texttt{station\_id}, \texttt{timestamp})$$
- **Tập quan sát đơn trạm:** Khóa duy nhất là `timestamp`.
- **Ràng buộc toàn vẹn:**  
  Trên mỗi trạm, mỗi mốc thời gian 1 giờ chỉ được phép tồn tại đúng một dòng quan sát duy nhất. Mọi bản ghi trùng lặp khóa phải được phát hiện và xử lý ở tầng làm sạch tất định.

---

## 4. Chi Tiết Các Trường Dữ Liệu Chuẩn Hóa (8 Thuộc Tính Bắt Buộc Mỗi Trường)

Tuân thủ nghiêm ngặt yêu cầu quản trị dữ liệu học thuật, mỗi trường trong Canonical Schema được định nghĩa chi tiết thông qua **8 thuộc tính chuẩn hóa**:

```text
1. Tên trường chuẩn hóa (Canonical Field Name)
2. Tên trường tại nguồn (Source Field Name)
3. Định nghĩa khoa học & nghiệp vụ (Definition)
4. Đơn vị đo lường chuẩn (Unit)
5. Kiểu dữ liệu chuẩn (Datatype)
6. Quy tắc chuyển đổi (Transformation)
7. Nguồn gốc dữ liệu (Source Origin)
8. Tính sẵn sàng & Quy tắc khuyết thiếu (Missingness/Availability)
```

---

### 4.1. Nhóm Trường Định Danh Thời Gian & Không Gian

#### 1. `timestamp`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `timestamp` |
| **Source Field Name** | `datetime` (OpenAQ S3 archive) / `period.datetimeFrom.utc` (OpenAQ REST API v3); `time` (Open-Meteo ERA5) |
| **Definition** | Mốc thời gian ghi nhận quan trắc theo chu kỳ 1 giờ tại địa phương. |
| **Unit** | ISO 8601 (Định dạng chuẩn: `YYYY-MM-DD HH:00:00+07:00`) |
| **Datatype** | `datetime64[ns, Asia/Ho_Chi_Minh]` |
| **Transformation** | - OpenAQ S3: Parse chuỗi ISO 8601 đã có offset `+07:00` thành tz-aware datetime.<br>- Open-Meteo: Truy vấn với `&timezone=Asia/Ho_Chi_Minh`, parse chuỗi ngày giờ local và gán múi giờ `Asia/Ho_Chi_Minh` (UTC+7). Căn chỉnh làm tròn đầu giờ chuẩn (`freq='h'`). |
| **Source Origin** | Nguồn chính: OpenAQ (Chất lượng không khí) & Open-Meteo ERA5 (Khí tượng bề mặt) – đã thẩm định và phê duyệt tại Issue #19. |
| **Missingness/Availability** | **Bắt buộc 100% (Mandatory)**; không cho phép `NaN / null`. Các mốc thời gian bị khuyết trong chuỗi sẽ được reindex để tạo dòng khuyết thiếu có chủ đích. |

#### 2. `station_id`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `station_id` |
| **Source Field Name** | `location_id` (OpenAQ: giá trị số nguyên `4946811`); `Site` (AirNow DOS CSV: `"Hanoi"`); Điểm lưới Open-Meteo (`lat=21.05448, lon=105.89848`) |
| **Definition** | Mã định danh kỹ thuật duy nhất cho trạm đo hoặc tọa độ lưới trích xuất tại khu vực Hà Nội. |
| **Unit** | Danh mục mã (Categorical / Code String) |
| **Datatype** | `string` |
| **Transformation** | Chuẩn hóa mã trạm quan trắc mặt đất duy nhất thành: `VN001_HANOI_556_NGUYEN_VAN_CU` (cho trạm OpenAQ location_id=4946811) hoặc `VN002_HANOI_US_EMBASSY` (cho trạm AirNow DOS CSV `Site == "Hanoi"`).<br>*(Lưu ý đính chính Issue #19: location_id=2178 thuộc Del Norte, Albuquerque, NM, Hoa Kỳ đã bị loại bỏ/disqualified do trích dẫn nhầm mã ví dụ tài liệu OpenAQ).* |
| **Source Origin** | Nguồn chính hiện hành: OpenAQ (Metadata trạm 556 Nguyễn Văn Cừ, NCEM/VEA, location_id=4946811); Nguồn chuẩn lịch sử 2023: AirNow US Embassy (Site: Hanoi, BAM-1020) – thẩm định và đính chính tại Issue #19. |
| **Missingness/Availability** | **Bắt buộc 100% (Mandatory)**; không cho phép `NaN / null`. |

#### 3. `location`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `location` |
| **Source Field Name** | `location` (OpenAQ S3 archive / API: `"556 Nguyễn Văn Cừ"`); `Site` (AirNow DOS CSV: `"Hanoi"`) |
| **Definition** | Tên địa danh hoặc mô tả bằng ngôn ngữ tự nhiên về vị trí đặt trạm quan trắc mặt đất. |
| **Unit** | Văn bản mô tả (Text String) |
| **Datatype** | `string` |
| **Transformation** | Chuẩn hóa chuỗi ký tự UTF-8, loại bỏ khoảng trắng thừa: `"556 Nguyễn Văn Cừ"` (hoặc `"US Diplomatic Post: Hanoi"` đối với trạm AirNow). |
| **Source Origin** | Nguồn chính hiện hành: OpenAQ (Trạm quan trắc chuẩn quốc gia 556 Nguyễn Văn Cừ); Nguồn chuẩn lịch sử: AirNow US Embassy – thẩm định tại Issue #19. |
| **Missingness/Availability** | **Bắt buộc 100% (Mandatory)** trên tập canonical hợp nhất; phản ánh trạm quan trắc quy chiếu nội thành Hà Nội. |

---

### 4.2. Nhóm Trường Nồng Độ Chất Ô Nhiễm (Pollution Variables)

#### 4. `pm25`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `pm25` |
| **Source Field Name** | `value` khi `parameter == 'pm25'` (OpenAQ S3 / API cảm biến 13502150); `Value` (AirNow DOS CSV) |
| **Definition** | Nồng độ khối lượng của các hạt bụi mịn có đường kính khí động học nhỏ hơn hoặc bằng 2.5 micromet lơ lửng trong không khí theo chu kỳ 1 giờ (hourly).<br><br>*(Lưu ý về tần suất đo & quy chuẩn: Dữ liệu canonical được ghi nhận theo từng giờ. Để đối chiếu với các quy chuẩn kỹ thuật như QCVN 05:2023/BTNMT với giới hạn trung bình 24 giờ là $45\,\mu\text{g/Nm}^3$ áp dụng từ 01/01/2026, dữ liệu cần được tổng hợp theo chu kỳ 24 giờ tương thích ở các bước phân tích sau; tuyệt đối không áp trực tiếp ngưỡng trung bình 24 giờ lên từng quan sát đơn lẻ theo giờ).*<br><br>*(Lưu ý về phân biệt đơn vị đo $\mu\text{g/m}^3$ vs. $\mu\text{g/Nm}^3$: Đơn vị canonical của tập dữ liệu là $\mu\text{g/m}^3$ đo ở điều kiện môi trường thực tế từ thiết bị quan trắc chuẩn. Quy chuẩn QCVN 05:2023/BTNMT sử dụng đơn vị $\mu\text{g/Nm}^3$ ở điều kiện chuẩn nhiệt độ và áp suất. Hai đơn vị này **không thể so sánh trực tiếp như cùng một đơn vị đo** mà cần được xử lý/chuẩn hóa phù hợp dựa trên thông số khí tượng thực tế nếu đối chiếu).* |
| **Unit** | $\mu\text{g/m}^3$ (Microgam trên mét khối không khí thực tế đo ở điều kiện môi trường - actual/ambient conditions; phân biệt với đơn vị quy chuẩn $\mu\text{g/Nm}^3$) |
| **Datatype** | `float64` |
| **Transformation** | Lọc theo `parameter == 'pm25'`; ép kiểu `float64`; áp dụng quy tắc kiểm tra giá trị vật lý: giá trị âm ($< 0\,\mu\text{g/m}^3$) là bất thường vật lý $\to$ gán `NaN`; giá trị bằng 0 ($= 0.0\,\mu\text{g/m}^3$) được giữ nguyên nếu là quan trắc hợp lệ từ cảm biến (chỉ gán `NaN` nếu đi kèm QC invalid flag từ trạm); bóc trần mã lỗi ngụy trang (ví dụ `-999` từ AirNow) thành `NaN`. |
| **Source Origin** | Nguồn chính hiện hành: OpenAQ REST API v3 / S3 Archive (location_id=4946811 - 556 Nguyễn Văn Cừ, cảm biến 13502150). Nguồn chuẩn lịch sử 2023: AirNow DOS CSV (Site: Hanoi, BAM-1020). Phê duyệt và đính chính chính thức tại Issue #19. |
| **Missingness/Availability** | **Biến mục tiêu cốt lõi**.<br>*(Lưu ý đính chính Issue #19: Số liệu 14,424 dòng của location 2178 trước đây đã bị thu hồi do đo đạc tại Albuquerque, NM, Hoa Kỳ).*<br>Dữ liệu thực tế tại Hà Nội: Trạm OpenAQ 4946811 có 352 tệp S3 lưu trữ từ 03/07/2025 đến 15/07/2026 (0 bản ghi trong 2023–2024 do OpenAQ mới tích hợp mạng lưới từ 07/2025). Đối với mốc lịch sử 2023, nguồn AirNow DOS CSV cung cấp chuỗi đo hourly liên tục (cần bóc trần mã ngụy trang `-999`). Giá trị khuyết thiếu tự nhiên biểu diễn bằng `NaN`, không tự ý điền 0. |

#### 5. `pm10`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `pm10` |
| **Source Field Name** | `value` khi `parameter == 'pm10'` (OpenAQ S3 / API cảm biến 13502165) |
| **Definition** | Nồng độ khối lượng của các hạt bụi thô có đường kính khí động học nhỏ hơn hoặc bằng 10 micromet lơ lửng trong không khí theo chu kỳ 1 giờ (hourly). |
| **Unit** | $\mu\text{g/m}^3$ (Microgam trên mét khối không khí) |
| **Datatype** | `float64` |
| **Transformation** | Lọc theo `parameter == 'pm10'`; ép kiểu `float64`; dùng để kiểm tra tính hợp lý vật lý với `pm25` ($\text{PM}_{2.5} \le \text{PM}_{10} + \epsilon$). |
| **Source Origin** | Nguồn chính: OpenAQ (location_id=4946811 – trạm 556 Nguyễn Văn Cừ, cảm biến 13502165 – thẩm định thực nghiệm tại Issue #19). |
| **Missingness/Availability** | **Tùy chọn bổ trợ (Secondary variable)**; độ bao phủ và tính đầy đủ đồng hành cùng chuỗi đo `pm25` của trạm 4946811. Nếu các khung giờ không có đo đạc, giá trị là `NaN`. |

---

### 4.3. Nhóm Trường Yếu Tố Khí Tượng Bề Mặt (Surface Weather Variables)

#### 6. `temperature`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `temperature` |
| **Source Field Name** | `temperature_2m` (Open-Meteo ERA5); `TMP` (NOAA ISD 48820 - Fallback) |
| **Definition** | Nhiệt độ không khí khô đo tại độ cao tiêu chuẩn (2 mét so với mặt đất). |
| **Unit** | $^\circ\text{C}$ (Độ Celsius) |
| **Datatype** | `float64` |
| **Transformation** | Open-Meteo trả về trực tiếp đơn vị $^\circ\text{C}$; ép kiểu `float64`; kiểm tra giới hạn vật lý tự nhiên ($0^\circ\text{C} \le T \le 50^\circ\text{C}$). (Nếu dùng NOAA ISD fallback: lấy phần số và chia 10). |
| **Source Origin** | Nguồn chính: Open-Meteo Historical Weather API (ERA5 Reanalysis) – phê duyệt tại Issue #19. Nguồn dự phòng (Fallback): NOAA ISD 48820. |
| **Missingness/Availability** | Biến thời tiết chính; kết quả profiling ban đầu (khung 2023–2024): **0/17,544 khuyết (0.00% missing)**. Khi chạy thực tế theo cơ chế Dynamic Temporal Synchronization (khung trạm OpenAQ 4946811 từ 03/07/2025 đến 15/07/2026), tập dữ liệu thu nhận **9,072 giờ đầy đủ (0/9,072 khuyết, 0.00% missing)**. |

#### 7. `relative_humidity`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `relative_humidity` |
| **Source Field Name** | `relative_humidity_2m` (Open-Meteo ERA5) |
| **Definition** | Tỷ số phần trăm giữa áp suất hơi nước thực tế và áp suất hơi nước bão hòa ở cùng nhiệt độ và áp suất khí quyển tại độ cao 2m. |
| **Unit** | $\%$ (Phần trăm, miền giá trị vật lý $0\% - 100\%$) |
| **Datatype** | `float64` |
| **Transformation** | Open-Meteo trả về trực tiếp thang $\%$; ép kiểu `float64`; kiểm tra giới hạn vật lý $0\% \le \text{RH} \le 100\%$. |
| **Source Origin** | Nguồn chính: Open-Meteo Historical Weather API (ERA5 Reanalysis) – phê duyệt tại Issue #19. |
| **Missingness/Availability** | Biến thời tiết chính; profiling ban đầu (khung 2023–2024): **0.00% missing** (17,544/17,544 giờ). Khung chạy thực tế Dynamic Temporal Synchronization: **0.00% missing** (9,072/9,072 giờ đầy đủ). |

#### 8. `wind_speed`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `wind_speed` |
| **Source Field Name** | `wind_speed_10m` (Open-Meteo ERA5, với `&wind_speed_unit=ms`); `WND` (NOAA ISD - Fallback) |
| **Definition** | Tốc độ chuyển động của luồng không khí theo phương nằm ngang đo tại độ cao chuẩn (10 mét). |
| **Unit** | $\text{m/s}$ (Mét trên giây) |
| **Datatype** | `float64` |
| **Transformation** | API được truy vấn kèm tham số `&wind_speed_unit=ms` để nhận trực tiếp $\text{m/s}$; ép kiểu `float64`; kiểm tra điều kiện không âm ($\ge 0\,\text{m/s}$). |
| **Source Origin** | Nguồn chính: Open-Meteo Historical Weather API (ERA5 Reanalysis) – phê duyệt tại Issue #19. |
| **Missingness/Availability** | Biến thời tiết chính; profiling ban đầu (khung 2023–2024): **0.00% missing** (17,544/17,544 giờ). Khung chạy thực tế Dynamic Temporal Synchronization: **0.00% missing** (9,072/9,072 giờ đầy đủ). |

#### 9. `wind_direction`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `wind_direction` |
| **Source Field Name** | `wind_direction_10m` (Open-Meteo ERA5) |
| **Definition** | Hướng gió thổi tới, tính theo độ góc từ hướng Bắc thực theo chiều kim đồng hồ ($0^\circ - 360^\circ$, với $0^\circ = 360^\circ$ là hướng Bắc, $90^\circ$ là hướng Đông). |
| **Unit** | Độ ($^\circ$, Góc độ $0^\circ - 360^\circ$) |
| **Datatype** | `float64` |
| **Transformation** | Chuẩn hóa modulo 360 độ; ép kiểu `float64`. |
| **Source Origin** | Nguồn chính: Open-Meteo Historical Weather API (ERA5 Reanalysis) – phê duyệt tại Issue #19. |
| **Missingness/Availability** | Biến thời tiết; profiling ban đầu (khung 2023–2024): **0.00% missing** (17,544/17,544 giờ). Khung chạy thực tế Dynamic Temporal Synchronization: **0.00% missing** (9,072/9,072 giờ đầy đủ). |

#### 10. `precipitation`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `precipitation` |
| **Source Field Name** | `precipitation` (Open-Meteo ERA5) |
| **Definition** | Tổng lượng nước (mưa lỏng hoặc tương đương nước) rơi xuống bề mặt đất tích lũy trong khoảng thời gian quan sát 1 giờ. |
| **Unit** | $\text{mm}$ (Milimét) |
| **Datatype** | `float64` |
| **Transformation** | Ép kiểu `float64`; kiểm tra điều kiện không âm ($\ge 0.0\,\text{mm}$). |
| **Source Origin** | Nguồn chính: Open-Meteo Historical Weather API (ERA5 Reanalysis) – phê duyệt tại Issue #19. |
| **Missingness/Availability** | Biến thời tiết; profiling ban đầu (khung 2023–2024): **0.00% missing** (17,544/17,544 giờ). Khung chạy thực tế Dynamic Temporal Synchronization: **0.00% missing** (9,072/9,072 giờ đầy đủ). |

#### 11. `surface_pressure`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `surface_pressure` |
| **Source Field Name** | `surface_pressure` (Open-Meteo ERA5) |
| **Definition** | Áp suất khí quyển tác động lên bề mặt đất tại cao độ thực tế của trạm đo/điểm lưới. |
| **Unit** | $\text{hPa}$ (Hectopascal, tương đương $\text{mbar}$) |
| **Datatype** | `float64` |
| **Transformation** | Open-Meteo trả về trực tiếp đơn vị $\text{hPa}$; ép kiểu `float64`; kiểm tra dải áp suất bề mặt thực tế ($950 - 1050\,\text{hPa}$). |
| **Source Origin** | Nguồn chính: Open-Meteo Historical Weather API (ERA5 Reanalysis) – phê duyệt tại Issue #19. |
| **Missingness/Availability** | Biến thời tiết; profiling ban đầu (khung 2023–2024): **0.00% missing** (17,544/17,544 giờ). Khung chạy thực tế Dynamic Temporal Synchronization: **0.00% missing** (9,072/9,072 giờ đầy đủ). |

---

## 5. Quy Ước Về Dữ Liệu Khuyết Thiếu (Missingness Conventions)

Để đảm bảo tính trung thực khoa học và ngăn chặn sai lệch phân tích, toàn bộ chuỗi xử lý dữ liệu phải tuân thủ nghiêm ngặt các nguyên tắc sau:

1. **Chuẩn biểu diễn khuyết thiếu thống nhất:**
   - Mọi giá trị khuyết ở tầng Canonical Schema bắt buộc phải được biểu diễn bằng chuẩn **`NaN` (Not a Number)** của NumPy / Pandas (hoặc `null` trong JSON).
2. **Cấm tuyệt đối điền số 0 ngầm định (No Silent Zero Imputation):**
   - Tuyệt đối không thay thế dữ liệu khuyết bằng số `0` hoặc `0.0`.
   - Trong khí tượng và môi trường, giá trị `0` mang ý nghĩa vật lý rõ rệt: nồng độ $\text{PM}_{2.5} = 0\,\mu\text{g/m}^3$ là môi trường chân không lý tưởng (hoàn toàn không khả thi tại Hà Nội); tốc độ gió $= 0\,\text{m/s}$ là lặng gió tuyệt đối; lượng mưa $= 0\,\text{mm}$ là trạng thái không mưa. Việc điền số 0 bừa bãi sẽ làm sai lệch nghiêm trọng phân phối và các ước lượng hồi quy.
   - **Phân biệt giữa số 0 gán ép bừa bãi và số 0 quan trắc hợp lệ (Valid Observed Zero):** Nếu thiết bị quan trắc/trạm đo ghi nhận giá trị bằng 0 hợp lệ mà không có cờ báo lỗi từ trạm (QC invalid flag), giá trị 0 được giữ nguyên như một quan trắc thực tế, không tự ý biến thành `NaN`. Chỉ loại bỏ hoặc gán `NaN` đối với các giá trị âm ($< 0$) hoặc các giá trị được nguồn/QC xác định là lỗi/calibration.
3. **Phân loại rõ ràng 3 trạng thái khuyết thiếu:**
   - **Biến không được nguồn cung cấp (Variable Unavailable from Source):** Trường dữ liệu không hề tồn tại trong cấu hình đầu ra của nhà cung cấp (ví dụ: trạm quan trắc không trang bị cảm biến $\text{PM}_{10}$).
   - **Dữ liệu quan trắc bị khuyết (Measurement Missing):** Cảm biến gặp sự cố gián đoạn nguồn điện, tắc nghẽn đường ống lấy mẫu, bảo trì định kỳ hoặc nghẽn mạng truyền tin.
   - **Giá trị không áp dụng (Not Applicable):** Ví dụ như hướng gió khi tốc độ gió bằng 0 (lặng gió).
4. **Bóc trần Missing ngụy trang (Disguised Missing Markers):**
   - Nhiều API và phần mềm trạm quan trắc mã hóa lỗi hoặc giá trị thiếu bằng các con số ngoại lai đặc biệt như `-999`, `-9999`, `999.0`, hoặc các chuỗi ký tự `"N/A"`, `"None"`, `"null"`, `"missing"`.
   - Adapter nạp dữ liệu có trách nhiệm nhận diện và chuyển đổi toàn bộ các giá trị này thành `np.nan` trước khi đưa vào DataFrame chuẩn hóa.

---

## 6. Hiện Trạng Ánh Xạ Nguồn & Thẩm Định Tại Issue #19 (Source Mapping Status)

> [!NOTE]
> **Toàn bộ ánh xạ trường nguồn ĐÃ ĐƯỢC XÁC THỰC THỰC NGHIỆM (Validated Source Mappings):**  
> 1. **Cổng thẩm định nguồn Issue #19:** Issue #19 đã hoàn tất khảo sát hồ sơ dữ liệu (*Data Profiling*), kiểm chứng thực nghiệm tại Hà Nội và ban hành quyết định Cổng Nguồn Dữ liệu tại [`docs/source_profiling_decision.md`](source_profiling_decision.md) (bao gồm đính chính loại bỏ location 2178 tại Mỹ và xác thực trạm chuẩn 4946811 tại Long Biên, Hà Nội).  
> 2. **Phân định vai trò nguồn:**  
>    - **Chất lượng không khí:** Primary hiện hành = OpenAQ REST API v3 / S3 Archive (location_id=4946811, trạm 556 Nguyễn Văn Cừ, Long Biên, Hà Nội); Primary lịch sử 2023 / Fallback = AirNow US Department of State Historical CSV (Site: Hanoi, trạm ĐSQ Hoa Kỳ, Met One BAM-1020).  
>    - **Khí tượng bề mặt:** Primary = Open-Meteo Historical Weather API (ERA5 Reanalysis, điểm lưới Hà Nội cách trạm 556 Nguyễn Văn Cừ 1.7 km); Fallback = NOAA Integrated Surface Database (ISD, Trạm WMO 48820 - Sân bay Nội Bài).  
> 3. **Ánh xạ trường chính thức:** Bảng dưới đây thể hiện ánh xạ đã được xác thực trực tiếp qua phản hồi API và cấu trúc tệp thực tế.

### 6.1. Danh mục các nguồn ứng viên đã thẩm định (Candidate Sources Profiled)
Tại Issue #19, 6 nhà cung cấp dữ liệu đã được thẩm định thực nghiệm:
1. **OpenAQ REST API v3 / S3 Archive (location_id=4946811 - 556 Nguyễn Văn Cừ)**: Nguồn chính chất lượng không khí hiện hành (PM2.5, PM10). *(Đính chính: location_id=2178 Del Norte, Albuquerque, NM, Hoa Kỳ đã bị loại bỏ/disqualified)*.
2. **Open-Meteo Historical Weather API (ERA5)**: Nguồn chính khí tượng bề mặt (6 biến Canonical).
3. **AirNow (US Department of State)**: Nguồn chuẩn lịch sử (2023) / Dự phòng (Fallback source) chất lượng không khí.
4. **NOAA ISD (WMO Station 48820 - Sân bay Nội Bài)**: Nguồn dự phòng (Fallback source) khí tượng bề mặt.
5. **Tập dữ liệu Kaggle Hà Nội (CSV)**: Nguồn tham chiếu phân phối thống kê ngoài (Reference only).
6. **PAM Air Portal**: Nguồn loại bỏ do bản quyền đóng và thiếu REST API mở (Unused).

### 6.2. Bảng ánh xạ trường đã thẩm định (Validated Field Mapping Matrix)

| Trường Canonical | Đơn vị chuẩn | Nguồn chính Ô nhiễm (OpenAQ 4946811 / AirNow) | Nguồn chính Khí tượng (Open-Meteo ERA5) | Tình trạng thẩm định (Validation Status) |
|---|---|---|---|:---:|
| `timestamp` | UTC+7 | `datetime` (S3) / `Date (LST)` (AirNow) | `time` (với `&timezone=Asia/Ho_Chi_Minh`) | **Đã xác thực (Validated tại #19)** |
| `station_id` | String | `location_id` (`4946811` $\to$ `VN001_HANOI_556_NGUYEN_VAN_CU`) / `Site` (`"Hanoi"` $\to$ `VN002_HANOI_US_EMBASSY`) | Tọa độ lưới `21.05448N, 105.89848E` | **Đã xác thực (Validated tại #19)** |
| `location` | String | `location` (`"556 Nguyễn Văn Cừ"`) / `Site` (`"Hanoi"`) | Metadata vị trí lưới Hà Nội | **Đã xác thực (Validated tại #19)** |
| `pm25` | $\mu\text{g/m}^3$ | `value` khi `parameter == "pm25"` (Cảm biến 13502150 / BAM-1020) | Không áp dụng | **Đã xác thực (Validated tại #19)** |
| `pm10` | $\mu\text{g/m}^3$ | `value` khi `parameter == "pm10"` (Cảm biến 13502165) | Không áp dụng | **Đã xác thực (Validated tại #19)** |
| `temperature` | $^\circ\text{C}$ | Không có cảm biến | `temperature_2m` | **Đã xác thực (Validated tại #19)** |
| `relative_humidity` | $\%$ | Không có cảm biến | `relative_humidity_2m` | **Đã xác thực (Validated tại #19)** |
| `wind_speed` | $\text{m/s}$ | Không có cảm biến | `wind_speed_10m` (`&wind_speed_unit=ms`) | **Đã xác thực (Validated tại #19)** |
| `wind_direction` | Độ ($^\circ$) | Không có cảm biến | `wind_direction_10m` | **Đã xác thực (Validated tại #19)** |
| `precipitation` | $\text{mm}$ | Không có cảm biến | `precipitation` | **Đã xác thực (Validated tại #19)** |
| `surface_pressure` | $\text{hPa}$ | Không có cảm biến | `surface_pressure` | **Đã xác thực (Validated tại #19)** |

> [!NOTE]
> Chi tiết toàn văn khảo sát hồ sơ dữ liệu, bảng profiling metrics thực nghiệm và biên bản quyết định phân định vai trò nguồn được lưu trữ tại [`docs/source_profiling_decision.md`](source_profiling_decision.md) và thông số nguồn được quản lý tại [`data/raw/metadata.json`](../data/raw/metadata.json).

---

## 7. Nguyên Tắc Biến Đổi & Chuẩn Hóa Đơn Vị (Transformation Principles)

Khi triển khai các module adapter trong `src/data_collection.py` (tại Issue #3 và #4) cũng như các loader kế tiếp (`src/data_loader.py`), các kỹ sư dữ liệu phải tuân thủ nghiêm ngặt các nguyên tắc biến đổi sau:

1. **Chính sách dữ liệu thô ba tầng (Three-tier Raw Data Policy - Mục 3.2 Roadmap):**
   - **Tầng A (Lưu trữ độc lập):** Dữ liệu thô tải về từ API hoặc nguồn ngoài được lưu trữ nguyên bản payload trong thư mục `data/raw/` (JSON/Parquet).
   - **Tầng B (Bảo toàn & Băm kiểm tra):** Không chỉnh sửa nội dung tệp thô bằng tay; mã băm SHA-256 được tính toán và ghi nhận trong `data/raw/metadata.json` để kiểm toán tính toàn vẹn độc lập. Mọi phép làm sạch và chuẩn hóa chỉ diễn ra trên bộ nhớ thông qua mã nguồn xác định và xuất ra `data/processed/` (hoặc `data/interim/`).
   - **Tầng C (Quản lý phiên bản Git):** Thư mục `data/raw/` chứa các tệp dữ liệu thô dung lượng lớn được loại trừ khỏi Git qua `.gitignore` (`data/raw/*.json`, `data/raw/*.parquet`), cho phép tái tạo độc lập qua pipeline nạp mà không làm phình repository.
2. **Quy tắc chuyển đổi đơn vị đo (Unit Conversion Formulas):**
   - *Nhiệt độ:* 
     $$T_{^\circ\text{C}} = T_K - 273.15$$
     $$T_{^\circ\text{C}} = (T_{^\circ\text{F}} - 32) \times \frac{5}{9}$$
   - *Tốc độ gió:*
     $$v_{\text{m/s}} = \frac{v_{\text{km/h}}}{3.6}$$
     $$v_{\text{m/s}} = v_{\text{mph}} \times 0.44704$$
   - *Áp suất:*
     $$p_{\text{hPa}} = \frac{p_{\text{Pa}}}{100}$$
     $$p_{\text{hPa}} = p_{\text{inHg}} \times 33.8639$$
   - *Lượng mưa:*
     $$P_{\text{mm}} = P_{\text{inch}} \times 25.4$$
3. **Tính đơn điệu và idempotent (Idempotency):**
   - Hàm chuyển đổi của adapter phải đảm bảo tính xác định (*deterministic*): cùng một payload đầu vào luôn cho ra chính xác cùng một DataFrame đầu ra chuẩn hóa.
4. **Kiểm tra biên giới hạn vật lý sơ bộ (Sanity Checks):**
   - Khi chuyển đổi, adapter cảnh báo hoặc gán `NaN` đối với các giá trị vi phạm quy luật tự nhiên hiển nhiên (ví dụ: độ ẩm $> 100\%$ hoặc $< 0\%$, tốc độ gió $< 0\,\text{m/s}$, nồng độ bụi âm $< 0\,\mu\text{g/m}^3$).
5. **Nguyên tắc phân biệt đơn vị quan trắc ($\mu\text{g/m}^3$) và đơn vị quy chuẩn ($\mu\text{g/Nm}^3$):**
   - Đơn vị canonical của tập dữ liệu là $\mu\text{g/m}^3$ (nồng độ khối lượng thực tế đo trong 1 mét khối không khí tại điều kiện nhiệt độ và áp suất môi trường xung quanh trạm đo - *ambient/volumetric conditions*).
   - Đơn vị quy chuẩn môi trường QCVN 05:2023/BTNMT là $\mu\text{g/Nm}^3$ (nồng độ khối lượng tính trên 1 mét khối khí chuẩn - *normal cubic meter*, quy đổi về điều kiện chuẩn: nhiệt độ 25°C và áp suất 760 mmHg).
   - **Tuyệt đối không so sánh trực tiếp hai giá trị này như cùng một đơn vị đo**.
   - Nếu trong các bài toán phân tích hoặc mô hình hóa cảnh báo ở các giai đoạn sau (Issue #7, #13) cần đối chiếu nồng độ quan sát với các ngưỡng của QCVN, nhóm nghiên cứu bắt buộc phải thực hiện bước xử lý/chuẩn hóa đơn vị đo phù hợp dựa trên thông số nhiệt độ và áp suất thực tế.
   - **Không tự ý ấn định một công thức chuyển đổi cố định tại thời điểm Issue #2**, vì việc chuyển đổi đòi hỏi phải có căn cứ xác thực từ Issue #19 về điều kiện đo kỹ thuật của cảm biến nguồn (cảm biến báo cáo theo volumetric concentration hay đã chuẩn hóa sẵn).

