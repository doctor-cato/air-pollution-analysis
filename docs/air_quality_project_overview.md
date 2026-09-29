# Phân Tích Mức Độ Ô Nhiễm Không Khí Theo Thời Gian (Project Overview)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)
> **Căn cứ tài liệu có thẩm quyền:** [`docs/roadmap.md`](roadmap.md) (Roadmap 15 tuần), [`docs/source_profiling_decision.md`](source_profiling_decision.md) (Quyết định cổng nguồn Issue #19), và [`docs/data_dictionary.md`](data_dictionary.md) (Canonical Schema Issue #2).
> **Lưu ý định hướng nguồn dữ liệu:** Tài liệu này khởi nguồn từ bản đề xuất sơ bộ ban đầu của nhóm. Qua quy trình thẩm định dữ liệu đa nguồn tại **Issue #19**, tập dữ liệu Kaggle đã được phân loại là **Tham chiếu ngoài (Reference Only)** do thiếu hồ sơ kiểm định phần cứng và nguy cơ rò rỉ dữ liệu từ việc tiền xử lý sẵn. Quyết định nguồn chính thức được phê duyệt tại Issue #19 bao gồm:
> - **Chất lượng không khí (Primary):** OpenAQ S3 Public Archive (`location_id = 4946811` – Trạm chuẩn quốc gia 556 Nguyễn Văn Cừ, Long Biên, Hà Nội do NCEM/VEA quản lý); nguồn chuẩn lịch sử / fallback: AirNow DOS Historical CSV (Trạm ĐSQ Hoa Kỳ, Met One BAM-1020).
> - **Khí tượng bề mặt (Primary):** Open-Meteo Historical Weather API (ECMWF ERA5 Reanalysis, điểm lưới cách trạm 556 Nguyễn Văn Cừ 1.71 km).
> - **Đồng bộ hóa thời gian động:** Cửa sổ khí tượng ERA5 được đồng bộ động theo chuỗi thời gian thực tế của dữ liệu chất lượng không khí.

---

## 1. Giới thiệu

Đề tài tập trung nghiên cứu và phân tích chuyên sâu biến thiên nồng độ bụi mịn $\text{PM}_{2.5}$ và mối liên hệ với các yếu tố khí tượng bề mặt tại khu vực **Hà Nội** theo chuỗi thời gian, tuân thủ phương pháp luận khoa học dữ liệu **CRISP-DM**.

Mục tiêu chính là tìm ra các **quy luật chu kỳ thời gian đa tầng (theo giờ trong ngày, ngày trong tuần, tháng và mùa)**, kiểm định ý nghĩa thống kê của các khác biệt quan sát được, mô hình hóa quan hệ thống kê với thời tiết (OLS kèm chẩn đoán LINE), và phát triển mô hình cảnh báo sớm các đợt ô nhiễm nguy hại dựa trên giá trị tổng hợp 24 giờ tương thích quy chuẩn QCVN 05:2023/BTNMT mà không gây rò rỉ dữ liệu chuỗi thời gian.

---

## 2. Mục tiêu của project

Project hướng tới 7 mục tiêu cụ thể:

1. Thu thập, chuẩn hóa đa nguồn và bảo toàn dữ liệu thô theo chính sách ba tầng (`data/raw/` kèm SHA-256 trong `metadata.json`).
2. Làm sạch tất định (xử lý missing ngụy trang, kẹt cảm biến, ràng buộc vật lý $\text{PM}_{2.5} \le \text{PM}_{10}$, cảnh báo độ ẩm cao $\text{RH} > 90\%$) và reindex chuỗi 1 giờ theo trạm quan trắc.
3. Khám phá phân phối thực nghiệm 4 họ chỉ số thống kê (Location, Spread, Shape, Quantiles) và biến thiên thời gian đa tầng của $\text{PM}_{2.5}$.
4. Kiểm định giả thuyết thống kê phi tham số có đối chứng (so sánh mùa, ngày làm việc vs cuối tuần, đối chiếu quy chuẩn), bắt buộc báo cáo bộ bốn: thống kê, $p$-value, Effect Size ($r_{rb}$) và 95% Bootstrap CI.
5. Mô hình hóa mối liên hệ giữa $\text{PM}_{2.5}$ và các yếu tố khí tượng bề mặt qua hồi quy OLS, kiểm tra 4 giả định chẩn đoán LINE, VIF và Cook's distance, diễn giải hệ số $\beta$ phi nhân quả.
6. Xây dựng pipeline phân loại cảnh báo sớm ô nhiễm vượt ngưỡng an toàn, xử lý mất cân bằng lớp và tối ưu hóa ngưỡng quyết định (Threshold tuning) theo mục tiêu vận hành bảo vệ sức khỏe cộng đồng (ưu tiên Recall và PR-AUC).
7. Trực quan hóa ấn phẩm theo chuẩn Edward Tufte và William Cleveland (bộ 7 biểu đồ FIG-01 đến FIG-07, tiêu đề dạng kết luận rút ra từ dữ liệu).

---

## 3. Dữ liệu & Canonical Schema

### Biến chính
**`pm25`** ($\mu\text{g/m}^3$) là biến mục tiêu cốt lõi của nghiên cứu, phản ánh nồng độ khối lượng bụi mịn trong điều kiện môi trường thực tế tại trạm đo.

### Lược đồ chuẩn hóa Canonical Schema (11 trường dữ liệu):
- **Định danh & Thời gian:** `timestamp` (`datetime64[ns, Asia/Ho_Chi_Minh]`), `station_id` (`string`), `location` (`string`).
- **Chất lượng không khí:** `pm25` (`float64`, $\mu\text{g/m}^3$), `pm10` (`float64`, $\mu\text{g/m}^3$).
- **Khí tượng bề mặt:** `temperature` ($^\circ\text{C}$), `relative_humidity` ($\%$), `wind_speed` ($\text{m/s}$), `wind_direction` (độ), `precipitation` ($\text{mm}$), `surface_pressure` ($\text{hPa}$).

> **Lưu ý về quy chuẩn & đơn vị:**
> - $\text{PM}_{2.5}$ không đồng nghĩa với AQI. AQI được tính từ $\text{PM}_{2.5}$ và không được đưa vào tập đặc trưng để tránh rò rỉ dữ liệu (Target Leakage).
> - Đơn vị canonical là $\mu\text{g/m}^3$ (thực tế môi trường). Giới hạn quy chuẩn QCVN 05:2023/BTNMT là $45\,\mu\text{g/Nm}^3$ (trung bình 24 giờ, áp dụng từ 01/01/2026; trước đó là $50\,\mu\text{g/Nm}^3$). Khi đối chiếu, cần tổng hợp chuỗi 24 giờ và kiểm tra tính tương thích đơn vị đo. Không áp trực tiếp ngưỡng 24h lên từng giờ đơn lẻ.

---

## 4. Các câu hỏi phân tích chính

Project sẽ tập trung trả lời các câu hỏi:

### Theo giờ
- PM2.5 trung bình thay đổi như thế nào trong 24 giờ?
- Những khung giờ nào thường có PM2.5 cao?

### Theo ngày
- PM2.5 có khác biệt giữa các ngày trong tuần không?
- Cuối tuần và ngày thường có xu hướng khác nhau không?

### Theo tháng
- Tháng nào có PM2.5 trung bình cao nhất?
- Tháng nào có PM2.5 thấp nhất?
- Mức độ ô nhiễm có xu hướng thay đổi theo các tháng như thế nào?

### Theo mùa
- Mùa nào có mức PM2.5 cao hơn?
- Sự biến động giữa các mùa có đáng kể không?

### Theo điều kiện thời tiết
- Nhiệt độ có liên quan đến PM2.5 không?
- Độ ẩm có liên quan đến PM2.5 không?
- Gió có ảnh hưởng đến mức PM2.5 không?
- Lượng mưa có mối quan hệ với PM2.5 không?

---

## 5. Quy trình phân tích dự kiến

```text
Raw Dataset
     ↓
Data Cleaning
     ↓
Data Preprocessing
     ↓
Exploratory Data Analysis (EDA)
     ↓
Time-based Analysis
     ↓
Weather Relationship Analysis
     ↓
Data Visualization
     ↓
Findings & Conclusion
```

### Bước 1 — Data Cleaning

- Kiểm tra kích thước dataset.
- Kiểm tra kiểu dữ liệu.
- Kiểm tra giá trị thiếu.
- Kiểm tra dữ liệu trùng lặp.
- Kiểm tra các giá trị bất thường/outlier.
- Chuyển cột thời gian về kiểu `datetime`.

### Bước 2 — Feature Engineering

Từ timestamp tạo thêm:

```text
year
month
day
hour
day_of_week
season
```

Các biến này giúp phân tích PM2.5 ở nhiều mức độ thời gian khác nhau.

### Bước 3 — Exploratory Data Analysis

Khảo sát:

- Phân bố PM2.5.
- Giá trị trung bình.
- Median.
- Min/Max.
- Standard deviation.
- Các giá trị bất thường.

### Bước 4 — Time Series Analysis

Phân tích PM2.5 theo:

- Giờ.
- Ngày.
- Tháng.
- Mùa.

Đặc biệt chú ý đến các xu hướng lặp lại theo thời gian.

### Bước 5 — Weather Analysis

Nếu các biến thời tiết đầy đủ, phân tích mối quan hệ giữa PM2.5 và:

- Temperature
- Humidity
- Wind Speed
- Precipitation
- Pressure

Có thể sử dụng correlation và scatter plot để hỗ trợ phân tích.

---

## 6. Các biểu đồ dự kiến

### 6.1. PM2.5 theo thời gian

Line chart thể hiện sự thay đổi PM2.5 theo timestamp.

**Mục đích:** quan sát xu hướng và các thời điểm tăng/giảm bất thường.

### 6.2. PM2.5 trung bình theo giờ

Bar chart hoặc line chart:

```text
Hour 0 → Hour 23
```

**Mục đích:** xác định các khung giờ có mức PM2.5 trung bình cao.

### 6.3. PM2.5 trung bình theo tháng

Biểu đồ thể hiện mức PM2.5 trung bình của từng tháng.

**Mục đích:** phát hiện xu hướng theo mùa/thời gian trong năm.

### 6.4. Heatmap Month × Hour

Trục:

- X = Hour
- Y = Month
- Value = Average PM2.5

**Mục đích:** tìm những thời điểm kết hợp giữa tháng và giờ có PM2.5 cao.

### 6.5. Boxplot theo tháng hoặc mùa

**Mục đích:** không chỉ xem giá trị trung bình mà còn xem mức độ phân tán và outlier.

### 6.6. Correlation Matrix

Dùng để quan sát mối quan hệ giữa PM2.5 và các biến thời tiết.

---

## 7. Kết quả đầu ra dự kiến

Theo chuẩn mực môn học INFO3020 và lộ trình tại [`docs/roadmap.md`](roadmap.md), sản phẩm bàn giao của đồ án bao gồm:

- Bộ dữ liệu sạch đóng băng lưu Snappy Parquet `data/processed/air_pollution_final.parquet` kèm `data/raw/metadata.json` ghi nhận xuất xứ và mã băm SHA-256.
- Từ điển dữ liệu chuẩn hóa (`docs/data_dictionary.md`) và Nhật ký làm sạch (`docs/cleaning_log.md`).
- Báo cáo phân tích chất lượng 6 chiều (`docs/data_quality_audit.md`).
- Báo cáo thống kê mô tả 4 họ chỉ số (`reports/statistical_profile.csv`) và kiểm định giả thuyết phi tham số bộ bốn (Thống kê, $p$-value, Effect Size $r_{rb}$, 95% Bootstrap CI).
- Bộ 7 biểu đồ ấn phẩm giải thích chuẩn Tufte/Cleveland (`figures/FIG-01.png` đến `FIG-07.png`, 300 DPI).
- Mô hình hồi quy OLS kèm báo cáo chẩn đoán 4 giả định LINE trên phần dư và diễn giải hệ số $\beta$ phi nhân quả.
- Mô hình phân loại cảnh báo sớm ô nhiễm với đường cong PR và tối ưu ngưỡng quyết định trên tập Train/Val, kiểm chứng độc lập trên Test.
- Báo cáo Giữa kỳ (`reports/midterm_report.pdf`), Báo cáo Cuối kỳ SCQA (`reports/final_report.pdf`), Datasheet for Dataset (`docs/datasheet.md`), và Model Card 1 trang (`docs/model_card.md`).

**Không đưa ra kết luận trước khi phân tích dữ liệu thực tế.** Mọi nhận xét và kết luận khoa học phải dựa trên bằng chứng định lượng kiểm chứng được từ mã nguồn và dữ liệu thực tế.

---

## 8. Công cụ & Tech Stack Chuẩn Mực

Project được thực hiện hoàn toàn bằng môi trường mã nguồn mở tái lập:

- **Ngôn ngữ:** Python 3.10+
- **Thao tác & Lưu trữ:** Pandas, NumPy, PyArrow (định dạng Snappy Parquet).
- **Trực quan hóa:** Matplotlib (hướng đối tượng `fig, ax`), Seaborn.
- **Thống kê & Suy luận:** SciPy (`scipy.stats`), Statsmodels (`statsmodels.api`, `statsmodels.tsa`).
- **Học máy & Pipeline:** Scikit-Learn (`sklearn.pipeline`, `sklearn.compose`, `sklearn.ensemble`).
- **Kiểm thử & CI:** Python `unittest`, GitHub Actions (`.github/workflows/ci.yml`).
- **Môi trường thực thi:** Jupyter Notebook (`notebooks/`), module hóa trong `src/`.

---

## 9. Phạm vi Đồ án (Project Scope)

- **Thuộc phạm vi:**
  - Thu thập, làm sạch tất định và quản trị xuất xứ dữ liệu thời gian thực tế tại Hà Nội.
  - Phân tích khám phá (EDA) chuỗi thời gian đa tầng (giờ, ngày, tháng, mùa).
  - Kiểm định giả thuyết phi tham số đối chứng có Effect Size và Bootstrap CI.
  - Hồi quy tuyến tính giải thích OLS kèm kiểm định 4 giả định LINE và kiểm soát đa cộng tuyến VIF.
  - Phân loại cảnh báo sớm nguy cơ ô nhiễm vượt ngưỡng an toàn, tối ưu hóa ngưỡng vận hành theo Recall và PR-AUC.
- **Ngoài phạm vi (Prohibited / Out of Scope):**
  - ❌ Deep Learning (LSTM, GRU, Transformers): Không thuộc phạm vi INFO3020; là mô hình hộp đen làm mất tính giải trình thống kê.
  - ❌ Apache Spark / Hadoop: Tập dữ liệu quan trắc chuỗi giờ có quy mô $\approx 5 - 20\text{ MB}$, Pandas và Parquet xử lý tối ưu trong vài mili-giây; sử dụng Spark là over-engineering.
  - ❌ Thử nghiệm can thiệp A/B (RCT): Bài toán mang bản chất nghiên cứu quan sát tự nhiên.

---

## 10. Kết luận định hướng

Thông qua việc kết hợp dữ liệu quan trắc nồng độ $\text{PM}_{2.5}$ theo giờ và dữ liệu khí tượng bề mặt ERA5 được đồng bộ hóa thời gian động, dự án áp dụng phương pháp luận CRISP-DM chặt chẽ để trả lời câu hỏi cốt lõi:

> **“Nồng độ bụi mịn $\text{PM}_{2.5}$ tại Hà Nội biến động theo những quy luật chu kỳ thời gian nào, chịu sự liên hệ ra sao bởi các yếu tố khí tượng bề mặt, và làm thế nào để xây dựng mô hình cảnh báo sớm các đợt ô nhiễm vượt ngưỡng an toàn mà không vi phạm rò rỉ dữ liệu?”**
