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
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ được đối chiếu và xác thực tại Issue #19, ví dụ: `datetime`, `date.local`, `time`, `timestamp`) |
| **Definition** | Mốc thời gian ghi nhận quan trắc theo chu kỳ 1 giờ tại địa phương. |
| **Unit** | ISO 8601 (Định dạng chuẩn: `YYYY-MM-DD HH:00:00+07:00`) |
| **Datatype** | `datetime64[ns, Asia/Ho_Chi_Minh]` |
| **Transformation** | Phân tích chuỗi ngày giờ, nhận biết múi giờ nguồn, chuyển đổi đồng nhất về `Asia/Ho_Chi_Minh` (UTC+7) và làm tròn/căn chỉnh về đầu giờ chuẩn (`freq='h'`). |
| **Source Origin** | Cả hai nguồn: Nguồn chất lượng không khí và Nguồn khí tượng bề mặt (được thẩm định tại Issue #19). |
| **Missingness/Availability** | **Bắt buộc 100% (Mandatory)**; không cho phép `NaN / null`. Các mốc thời gian bị khuyết trong chuỗi sẽ được reindex để tạo dòng khuyết thiếu có chủ đích. |

#### 2. `station_id`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `station_id` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `locationId`, `station_code`, hoặc gán mã cố định nếu là file trích xuất trạm đơn) |
| **Definition** | Mã định danh kỹ thuật duy nhất cho trạm đo hoặc tọa độ lưới trích xuất tại khu vực Hà Nội. |
| **Unit** | Danh mục mã (Categorical / Code String) |
| **Datatype** | `string` |
| **Transformation** | Chuẩn hóa dạng chuỗi viết hoa, loại bỏ khoảng trắng thừa; nếu nguồn là file đơn trạm khuyết cột này, adapter gán mã trạm cố định theo tài liệu nguồn. |
| **Source Origin** | Nguồn quan trắc chất lượng không khí (được thẩm định tại Issue #19). |
| **Missingness/Availability** | **Bắt buộc 100% (Mandatory)**; không cho phép `NaN / null`. |

#### 3. `location`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `location` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `location`, `site_name`, `station_name`) |
| **Definition** | Tên địa danh hoặc mô tả bằng ngôn ngữ tự nhiên về vị trí đặt trạm quan trắc mặt đất. |
| **Unit** | Văn bản mô tả (Text String) |
| **Datatype** | `string` |
| **Transformation** | Chuẩn hóa mã hóa ký tự UTF-8, loại bỏ ký tự lạ hoặc khoảng trắng đầu cuối; dùng phục vụ hiển thị báo cáo. |
| **Source Origin** | Metadata từ nguồn trạm quan trắc không khí (được thẩm định tại Issue #19). |
| **Missingness/Availability** | **Tùy chọn (Optional)**; có thể khuyết nếu nguồn chỉ cung cấp tọa độ hoặc mã trạm. |

---

### 4.2. Nhóm Trường Nồng Độ Chất Ô Nhiễm (Pollution Variables)

#### 4. `pm25`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `pm25` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `pm25`, `PM2.5`, `value` khi `parameter='pm25'`) |
| **Definition** | Nồng độ khối lượng của các hạt bụi mịn có đường kính khí động học nhỏ hơn hoặc bằng 2.5 micromet lơ lửng trong không khí. |
| **Unit** | $\mu\text{g/m}^3$ (Microgam trên mét khối không khí) |
| **Datatype** | `float64` |
| **Transformation** | Kiểm tra đơn vị nguồn; nếu nguồn dùng đơn vị khác (như $\text{mg/m}^3$ hay $\text{ppm}$), nhân hệ số chuyển đổi về $\mu\text{g/m}^3$; ép kiểu số thực 64-bit; chuyển các mã lỗi/marker ngụy trang thành `NaN`. |
| **Source Origin** | Nguồn dữ liệu chất lượng không khí được phê duyệt tại Issue #19 (ví dụ: trạm quan trắc tham chiếu BAM 1020). |
| **Missingness/Availability** | **Bắt buộc là biến mục tiêu cốt lõi**; tuy nhiên có thể khuyết trong các khung giờ trạm bảo trì hoặc lỗi truyền tín hiệu. Giá trị khuyết biểu diễn dưới dạng `NaN`, không được tự ý điền 0. |

#### 5. `pm10`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `pm10` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `pm10`, `PM10`, `value` khi `parameter='pm10'`) |
| **Definition** | Nồng độ khối lượng của các hạt bụi thô có đường kính khí động học nhỏ hơn hoặc bằng 10 micromet lơ lửng trong không khí. |
| **Unit** | $\mu\text{g/m}^3$ (Microgam trên mét khối không khí) |
| **Datatype** | `float64` |
| **Transformation** | Đổi đơn vị về $\mu\text{g/m}^3$ nếu cần; ép kiểu số thực 64-bit; dùng để kiểm tra tính hợp lý vật lý với `pm25` ($\text{PM}_{2.5} \le \text{PM}_{10} + \epsilon$). |
| **Source Origin** | Nguồn dữ liệu chất lượng không khí được phê duyệt tại Issue #19. |
| **Missingness/Availability** | **Tùy chọn (Optional)**; phụ thuộc vào việc trạm quan trắc nguồn có gắn đầu đo $\text{PM}_{10}$ hay không. Nếu nguồn không có, toàn bộ cột là `NaN`. |

---

### 4.3. Nhóm Trường Yếu Tố Khí Tượng Bề Mặt (Surface Weather Variables)

#### 6. `temperature`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `temperature` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `temperature_2m`, `temp`, `temperature`) |
| **Definition** | Nhiệt độ không khí khô đo tại độ cao tiêu chuẩn (thường là 2 mét so với mặt đất). |
| **Unit** | $^\circ\text{C}$ (Độ Celsius) |
| **Datatype** | `float64` |
| **Transformation** | Nếu nguồn dùng đơn vị Kelvin ($K$), chuyển đổi $T_{^\circ\text{C}} = T_K - 273.15$; nếu dùng độ Fahrenheit ($^\circ\text{F}$), chuyển đổi $T_{^\circ\text{C}} = (T_{^\circ\text{F}} - 32) \times 5/9$. Ép kiểu `float64`. |
| **Source Origin** | Nguồn dữ liệu khí tượng bề mặt được phê duyệt tại Issue #19 (ví dụ: Open-Meteo ERA5 Reanalysis). |
| **Missingness/Availability** | Biến thời tiết chính phục vụ mô hình hồi quy; giá trị khuyết biểu diễn dạng `NaN`. |

#### 7. `relative_humidity`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `relative_humidity` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `relative_humidity_2m`, `humidity`, `rh`) |
| **Definition** | Tỷ số phần trăm giữa áp suất hơi nước thực tế và áp suất hơi nước bão hòa ở cùng nhiệt độ và áp suất khí quyển. |
| **Unit** | $\%$ (Phần trăm, miền giá trị vật lý $0\% - 100\%$) |
| **Datatype** | `float64` |
| **Transformation** | Nếu nguồn lưu dưới dạng tỷ lệ thập phân ($0.0 - 1.0$), nhân với 100 để quy về thang $\%$; ép kiểu `float64`. |
| **Source Origin** | Nguồn dữ liệu khí tượng bề mặt được phê duyệt tại Issue #19. |
| **Missingness/Availability** | Biến thời tiết chính; giá trị khuyết biểu diễn dạng `NaN`. |

#### 8. `wind_speed`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `wind_speed` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `wind_speed_10m`, `wind_speed`, `wspd`) |
| **Definition** | Tốc độ chuyển động của luồng không khí theo phương nằm ngang đo tại độ cao chuẩn (10 mét). |
| **Unit** | $\text{m/s}$ (Mét trên giây) |
| **Datatype** | `float64` |
| **Transformation** | Nếu nguồn đo bằng $\text{km/h}$, chuyển đổi: $v_{\text{m/s}} = v_{\text{km/h}} / 3.6$; nếu đo bằng dặm/giờ (mph), nhân $0.44704$; nếu đo bằng hải lý (knots), nhân $0.514444$. Ép kiểu `float64`. |
| **Source Origin** | Nguồn dữ liệu khí tượng bề mặt được phê duyệt tại Issue #19. |
| **Missingness/Availability** | Biến thời tiết chính; giá trị khuyết biểu diễn dạng `NaN`. |

#### 9. `wind_direction`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `wind_direction` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `wind_direction_10m`, `wind_direction`, `wdir`) |
| **Definition** | Hướng gió thổi tới, tính theo độ góc từ hướng Bắc thực theo chiều kim đồng hồ ($0^\circ - 360^\circ$, với $0^\circ = 360^\circ$ là hướng Bắc, $90^\circ$ là hướng Đông). |
| **Unit** | Độ ($^\circ$, Góc độ $0^\circ - 360^\circ$) |
| **Datatype** | `float64` |
| **Transformation** | Kiểm tra quy ước góc của nguồn (chỉ xác thực khi kiểm tra payload tại Issue #19, không suy diễn định kiến). Ép kiểu `float64`. |
| **Source Origin** | Nguồn dữ liệu khí tượng bề mặt được phê duyệt tại Issue #19. |
| **Missingness/Availability** | Tùy chọn / Phụ thuộc nguồn; giá trị khuyết biểu diễn dạng `NaN`. Khi tốc độ gió bằng 0 (lặng gió), hướng gió có thể là không xác định (`NaN`). |

#### 10. `precipitation`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `precipitation` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `precipitation`, `rain`, `precip`) |
| **Definition** | Tổng lượng nước (mưa lỏng hoặc tương đương nước) rơi xuống bề mặt đất tích lũy trong khoảng thời gian quan sát 1 giờ. |
| **Unit** | $\text{mm}$ (Milimét) |
| **Datatype** | `float64` |
| **Transformation** | Nếu nguồn đo bằng inch, chuyển đổi $P_{\text{mm}} = P_{\text{inch}} \times 25.4$; nếu là lượng mưa tích lũy ngày, phân bổ theo giờ phải theo quy chuẩn xác thực. Ép kiểu `float64`. |
| **Source Origin** | Nguồn dữ liệu khí tượng bề mặt được phê duyệt tại Issue #19. |
| **Missingness/Availability** | Phụ thuộc nguồn; giá trị khuyết biểu diễn dạng `NaN`. **Lưu ý:** Không tự ý gán giá trị 0 khi nguồn khuyết số liệu mà chưa phân biệt được giữa "không có mưa" ($0.0\text{ mm}$) và "không có dữ liệu đo lường". |

#### 11. `surface_pressure`
| Thuộc tính | Đặc tả chi tiết |
|---|---|
| **Canonical Field Name** | `surface_pressure` |
| **Source Field Name** | *TBD / Phụ thuộc nguồn* (sẽ xác thực tại Issue #19, ví dụ: `surface_pressure`, `pressure`, `pres`) |
| **Definition** | Áp suất khí quyển tác động lên bề mặt đất tại cao độ thực tế của trạm đo. |
| **Unit** | $\text{hPa}$ (Hectopascal, tương đương $\text{mbar}$) |
| **Datatype** | `float64` |
| **Transformation** | Nếu nguồn dùng đơn vị Pascal ($\text{Pa}$), chuyển đổi $p_{\text{hPa}} = p_{\text{Pa}} / 100$; nếu dùng $\text{mmHg}$, nhân $1.33322$; nếu dùng $\text{inHg}$, nhân $33.8639$. Ép kiểu `float64`. |
| **Source Origin** | Nguồn dữ liệu khí tượng bề mặt được phê duyệt tại Issue #19. |
| **Missingness/Availability** | Phụ thuộc nguồn; giá trị khuyết biểu diễn dạng `NaN`. |

---

## 5. Quy Ước Về Dữ Liệu Khuyết Thiếu (Missingness Conventions)

Để đảm bảo tính trung thực khoa học và ngăn chặn sai lệch phân tích, toàn bộ chuỗi xử lý dữ liệu phải tuân thủ nghiêm ngặt các nguyên tắc sau:

1. **Chuẩn biểu diễn khuyết thiếu thống nhất:**
   - Mọi giá trị khuyết ở tầng Canonical Schema bắt buộc phải được biểu diễn bằng chuẩn **`NaN` (Not a Number)** của NumPy / Pandas (hoặc `null` trong JSON).
2. **Cấm tuyệt đối điền số 0 ngầm định (No Silent Zero Imputation):**
   - Tuyệt đối không thay thế dữ liệu khuyết bằng số `0` hoặc `0.0`.
   - Trong khí tượng và môi trường, giá trị `0` mang ý nghĩa vật lý rõ rệt: nồng độ $\text{PM}_{2.5} = 0\,\mu\text{g/m}^3$ là môi trường chân không lý tưởng (hoàn toàn không khả thi tại Hà Nội); tốc độ gió $= 0\,\text{m/s}$ là lặng gió tuyệt đối; lượng mưa $= 0\,\text{mm}$ là trạng thái không mưa. Việc điền số 0 bừa bãi sẽ làm sai lệch nghiêm trọng phân phối và các ước lượng hồi quy.
3. **Phân loại rõ ràng 3 trạng thái khuyết thiếu:**
   - **Biến không được nguồn cung cấp (Variable Unavailable from Source):** Trường dữ liệu không hề tồn tại trong cấu hình đầu ra của nhà cung cấp (ví dụ: trạm quan trắc không trang bị cảm biến $\text{PM}_{10}$).
   - **Dữ liệu quan trắc bị khuyết (Measurement Missing):** Cảm biến gặp sự cố gián đoạn nguồn điện, tắc nghẽn đường ống lấy mẫu, bảo trì định kỳ hoặc nghẽn mạng truyền tin.
   - **Giá trị không áp dụng (Not Applicable):** Ví dụ như hướng gió khi tốc độ gió bằng 0 (lặng gió).
4. **Bóc trần Missing ngụy trang (Disguised Missing Markers):**
   - Nhiều API và phần mềm trạm quan trắc mã hóa lỗi hoặc giá trị thiếu bằng các con số ngoại lai đặc biệt như `-999`, `-9999`, `999.0`, hoặc các chuỗi ký tự `"N/A"`, `"None"`, `"null"`, `"missing"`.
   - Adapter nạp dữ liệu có trách nhiệm nhận diện và chuyển đổi toàn bộ các giá trị này thành `np.nan` trước khi đưa vào DataFrame chuẩn hóa.

---

## 6. Hiện Trạng Ánh Xạ Nguồn & Thẩm Định Tại Issue #19 (Source Mapping Status)

Tuân thủ quy trình kiểm soát chất lượng của dự án: **Xác lập khung Canonical Schema (Issue #2) → Khảo sát hồ sơ và Ban hành quyết định nguồn (Issue #19) → Triển khai Adapter thu thập (Issue #3 & #4)**.

### 6.1. Danh mục các nguồn ứng viên (Candidate Sources)
Tại thời điểm Issue #2, các nhà cung cấp dữ liệu sau được xác định là nguồn ứng viên tiềm năng cần thẩm định tại Issue #19:
1. **Tập dữ liệu Kaggle Hà Nội (CSV)**: Dữ liệu ô nhiễm và thời tiết tổng hợp.
2. **OpenAQ REST API v3**: Dữ liệu quan trắc từ trạm tham chiếu chuẩn BAM 1020 (ví dụ: Đại sứ quán Hoa Kỳ tại Hà Nội).
3. **Open-Meteo Historical Weather API**: Dữ liệu khí tượng bề mặt từ mô hình tái phân tích ERA5.
4. **AirNow (US Department of State)**: Dữ liệu lịch sử quan trắc trạm ngoại giao.
5. **PAM Air Open Portal**: Dữ liệu mạng lưới cảm biến môi trường cộng đồng tại Việt Nam.

### 6.2. Trạng thái ánh xạ trường (Field Mapping Status)
Bảng theo dõi trạng thái thẩm định ánh xạ giữa các nguồn ứng viên và Canonical Schema:

| Trường Canonical | Đơn vị chuẩn | Nguồn ứng viên ô nhiễm (OpenAQ / Kaggle / AirNow) | Nguồn ứng viên khí tượng (Open-Meteo / ERA5) | Tình trạng thẩm định |
|---|---|---|---|:---:|
| `timestamp` | UTC+7 | Ánh xạ trường ngày giờ (TBD) | Ánh xạ trường ngày giờ (TBD) | **Chờ xác thực tại Issue #19** |
| `station_id` | String | Mã trạm / Identifier (TBD) | Tọa độ điểm lưới / Mã vị trí (TBD) | **Chờ xác thực tại Issue #19** |
| `location` | String | Tên trạm / Địa chỉ (TBD) | Metadata vị trí (TBD) | **Chờ xác thực tại Issue #19** |
| `pm25` | $\mu\text{g/m}^3$ | Tham số PM2.5 (TBD) | Không áp dụng | **Chờ xác thực tại Issue #19** |
| `pm10` | $\mu\text{g/m}^3$ | Tham số PM10 (TBD) | Không áp dụng | **Chờ xác thực tại Issue #19** |
| `temperature` | $^\circ\text{C}$ | Tùy chọn (nếu có cảm biến) | Tham số nhiệt độ 2m (TBD) | **Chờ xác thực tại Issue #19** |
| `relative_humidity` | $\%$ | Tùy chọn (nếu có cảm biến) | Tham số độ ẩm 2m (TBD) | **Chờ xác thực tại Issue #19** |
| `wind_speed` | $\text{m/s}$ | Tùy chọn (nếu có cảm biến) | Tham số tốc độ gió 10m (TBD) | **Chờ xác thực tại Issue #19** |
| `wind_direction` | Độ ($^\circ$) | Tùy chọn (nếu có cảm biến) | Tham số hướng gió 10m (TBD) | **Chờ xác thực tại Issue #19** |
| `precipitation` | $\text{mm}$ | Không khả dụng | Tham số lượng mưa tích lũy (TBD) | **Chờ xác thực tại Issue #19** |
| `surface_pressure` | $\text{hPa}$ | Không khả dụng | Tham số áp suất bề mặt (TBD) | **Chờ xác thực tại Issue #19** |

> [!NOTE]
> Để đảm bảo liêm chính học thuật, **dự án không tự bịa đặt tên cột cụ thể của các nguồn khi chưa thực hiện profiling thực tế**. Quyết định chính thức về việc lựa chọn nguồn nào làm Nguồn chính (*Primary*), Nguồn phụ (*Secondary*), hoặc Nguồn dự phòng (*Fallback*) sẽ được ban hành chi tiết trong tài liệu `docs/source_profiling_decision.md` của **Issue #19**.

---

## 7. Nguyên Tắc Biến Đổi & Chuẩn Hóa Đơn Vị (Transformation Principles)

Khi triển khai các module adapter trong `src/data_loader.py` (tại Issue #3 và #4), các kỹ sư dữ liệu phải tuân thủ nghiêm ngặt các nguyên tắc biến đổi sau:

1. **Bảo toàn dữ liệu gốc (Raw Immutability):**
   - Dữ liệu tải về từ API hoặc file gốc được lưu trữ nguyên vẹn ở chế độ chỉ đọc trong `data/raw/`. Mọi phép biến đổi chỉ diễn ra trên bộ nhớ (RAM) thông qua script và xuất ra `data/interim/` hoặc `data/processed/`.
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
