# LỘ TRÌNH THỰC HIỆN ĐỒ ÁN MÔN HỌC: INFO3020 – INTRODUCTION TO DATA SCIENCE

> **Đề tài:** Phân tích mức độ ô nhiễm không khí theo thời gian (*Time-Series Air Pollution Analysis*)  
> **Căn cứ tài liệu:** Toàn bộ slide bài giảng và tóm tắt chuyên đề từ **Week 1 đến Week 12**, Đề cương 15 tuần của ThS. Phạm Ngọc Đông – Khoa CNTT & Truyền thông, Trường Đại học CMC.  
> **Nơi lưu trữ:** `docs/ROADMAP_INFO3020_Air_Pollution.md`

> [!WARNING]
> **Tài liệu tham chiếu gốc — ĐÃ BỊ THAY THẾ MỘT PHẦN.** Đây là bản chép nguyên văn đề cương
> 15 tuần do giảng viên phát. Kể từ Issue #19 và Issue #3, một số nội dung dưới đây **không
> còn là yêu cầu kỹ thuật** của repository. Bản roadmap làm việc chính thức là
> [`docs/roadmap.md`](roadmap.md).
>
> **Các nội dung bị thay thế — dùng bản trong `docs/roadmap.md` thay thế:**
> | Nội dung trong tài liệu này | Quyết định hiện hành |
> |---|---|
> | Mục tiêu tuần thu thập trong "2 năm (2023–2024)", tệp `openaq_raw_2023_2024.json`, `weather_raw_2023_2024.json` | **Không còn yêu cầu.** Issue #3 và #19 cấm áp đặt khung thời gian lịch sử cố định; dải thời gian được suy diễn động từ độ phủ thực tế của nguồn. Xem `docs/roadmap.md` Mục 3.2. |
> | "Gọi API OpenAQ v3" trực tiếp | Issue #19 phê duyệt nguồn chính là **AWS S3 public bucket (OpenAQ `locationid=4946811`)**; AirNow DOS Hà Nội là nguồn tham chiếu. Xem `docs/source_profiling_decision.md` §12.2. |
> | "Dữ liệu thô bất biến / chế độ chỉ đọc" | Được thay bằng **Chính sách dữ liệu thô ba tầng** (Tầng A lưu trữ khi chạy, Tầng B bảo toàn + SHA-256, Tầng C không bắt buộc Git-track). Xem `docs/roadmap.md` Mục 3.2 và Issue #4. |
> | "giải thích đầy đủ 100% các cột thu thập" | Tiêu chuẩn kiểm chứng được là mọi trường Canonical Schema đều có định nghĩa, đơn vị và nguồn trong `docs/data_dictionary.md`; không dùng tỷ lệ phần trăm tuyệt đối. |
>
> Các phần về kiến thức INFO3020, kỹ thuật học và mốc nộp bài trong tài liệu này **vẫn có hiệu lực**.

---


---

## 1. PHÂN TÍCH YÊU CẦU ĐỒ ÁN MÔN HỌC INFO3020

### 1.1. Các khối kiến thức INFO3020 cần thể hiện trong đồ án
Đồ án là bức tranh thu nhỏ của toàn bộ chương trình học, bám sát **5 Chương – 15 Tuần**:
1. **Chương 1 (Nền tảng & Thu thập):** Vòng đời CRISP-DM, cấu trúc repo chuẩn, quy tắc dữ liệu thô bất biến (`data/raw/`), thu thập đa nguồn (API/Open Data), xử lý encoding và lưu trữ tối ưu sang **Parquet** (Week 1–2).
2. **Chương 2 (Chất lượng & Tiền xử lý):** Kiểm toán 6 chiều chất lượng dữ liệu, phát hiện missing ngụy trang, phân loại cơ chế khuyết thiếu (MCAR/MAR/MNAR), xử lý outlier chuỗi thời gian, chuẩn hóa thang đo (Scaling), tích hợp đa nguồn (Air Quality + Meteorology) không gây lỗi bùng nổ số hàng (Row Explosion bug) và đóng gói tiền xử lý thành **Pipeline** tránh rò rỉ dữ liệu (Week 3–5).
3. **Chương 3 (EDA & Trực quan hóa):** 4 họ thống kê mô tả (Location, Spread, Shape, Quantiles), hiểu rõ "Hình dạng phân phối quyết định chỉ số" (*Shape picks the statistic*), trực quan hóa chuẩn mực theo nguyên tắc Tufte (Data-Ink Ratio) và Cleveland, cấu trúc kể chuyện **SCQA** phục vụ Báo cáo giữa kỳ (Week 6–8).
4. **Chương 4 (Suy luận & Mô hình hóa):** 
   - *Suy luận thống kê:* Kiểm định giả thuyết (Hypothesis testing) so sánh các khoảng thời gian, bắt buộc báo cáo $p$-value kèm Kích thước hiệu ứng (*Effect size*) và Khoảng tin cậy (*Confidence Interval*) (Week 9).
   - *Hồi quy:* Mô hình hóa OLS tác động của thời tiết lên bụi mịn, tuân thủ quy trình 6 bước chẩn đoán giả định **LINE**, kiểm tra đa cộng tuyến VIF, điểm đòn bẩy Cook's distance và hiệu chỉnh Ridge/Lasso (Week 10).
   - *Phân loại:* Cảnh báo sớm ngày ô nhiễm cao, xử lý mất cân bằng lớp (*Imbalance*), tối ưu ngưỡng quyết định (*Threshold tuning*), đánh giá bằng PR-AUC/Recall thay vì Accuracy (Week 11).
5. **Chương 5 (Hạ tầng, Đạo đức & Đồ án):** Đánh giá dung lượng dữ liệu (giải trình tại sao không cần Spark), kiểm toán định kiến (*Sensor bias, Spatial bias, Temporal bias*), lập **Datasheet for Dataset** và **Model Card** 1 trang, tuyên bố mức độ hỗ trợ của AI trong README (Week 12–15).

---

### 1.2. Phân loại yêu cầu & Kỹ thuật
* **Bắt buộc theo chuẩn mực môn học:**
  - Thư mục `data/raw/` chỉ đọc, không chỉnh sửa thủ công; mọi biến đổi thực hiện bằng code và lưu ra `data/processed/`.
  - Có **Data Dictionary** (Từ điển dữ liệu) và **Cleaning Log** chi tiết (ghi rõ lý do cho từng quyết định xử lý).
  - Notebook chạy thông suốt từ đầu đến cuối sau khi bấm **Restart Kernel & Run All**.
  - Kiểm tra giả định thống kê trước khi thực hiện test hoặc hồi quy (vẽ Residual plot trước khi tin $R^2$).
  - Nộp kèm **Datasheet for Dataset**, **Model Card** (1 trang) và mục **Tuyên bố sử dụng AI** trong README.
* **Phù hợp đặc thù với đề tài ô nhiễm không khí theo thời gian:**
  - Phân tích chu kỳ thời gian đa tầng: Chu kỳ ngày đêm (*Diurnal pattern*), chu kỳ ngày trong tuần (*Weekday vs. Weekend*), chu kỳ mùa vụ (*Seasonal pattern*).
  - Kỹ thuật tính trung bình trượt (*Rolling averages*: 24h, 7 ngày) để khử nhiễu ngắn hạn.
  - Tích hợp dữ liệu chất lượng không khí với dữ liệu khí tượng (nhiệt độ, độ ẩm, hướng gió, tốc độ gió, áp suất).
  - Kiểm định phi tham số (*Mann-Whitney U / Kruskal-Wallis*) do nồng độ bụi thường bị lệch phải nặng (*Right-skewed*).
* **Kỹ thuật THỰC SỰ CẦN THIẾT:**
  - Pandas time-series resampling, forward fill / interpolation có chặn ngưỡng cho dữ liệu chuỗi thời gian.
  - RobustScaler / Log-transform (`np.log1p`) để làm mềm các giá trị cực đoan của bụi mịn.
  - Phép chia tập dữ liệu theo thời gian (*Temporal Train-Test Split*), tuyệt đối không dùng `train_test_split` ngẫu nhiên để tránh Temporal Leakage.
  - Đóng gói tiền xử lý thành scikit-learn Pipeline và ColumnTransformer để đảm bảo tính tái lập.
* **Kỹ thuật KHÔNG CẦN ĐƯA VÀO chỉ để làm "xịn":**
  - ❌ **Apache Spark / Hadoop:** Bộ dữ liệu quan trắc 1–3 năm theo giờ chỉ dao động từ 10.000 đến 30.000 dòng ($\approx 5 - 20\text{ MB}$). Slide Week 12 nhấn mạnh: *"Bạn nhiều khả năng KHÔNG CÓ Big Data. Spark chỉ đáng dùng trên 100 GB. Cố dùng Spark cho bài toán nhỏ là over-engineering"*. Pandas/Parquet xử lý trong vài mili-giây.
  - ❌ **Deep Learning (LSTM / GRU / Transformer):** Không thuộc phạm vi kiến thức INFO3020; biến đồ án thành "hộp đen", làm mất đi tính giải trình (*Explainability*) và không kiểm chứng được các giả định thống kê cốt lõi.
  - ❌ **Thử nghiệm A/B can thiệp (RCT):** Không khả thi vì con người không thể can thiệp làm thay đổi thời tiết ngẫu nhiên.
  - ❌ **Kỹ thuật nặc danh hóa cá nhân ($k$-anonymity / Hashing):** Dữ liệu quan trắc từ trạm đo môi trường công cộng không chứa thông tin định danh cá nhân (PII), do đó không cần làm mờ danh tính.

---

### 1.3. Các Milestone chính trong tiến trình môn học
* **Milestone 1 – Project Setup & Data Collection (Week 1–2):** Khởi tạo repository, thu thập dữ liệu thô từ OpenAQ & Open-Meteo, xây dựng Data Dictionary.
* **Milestone 2 – Data Audit & Cleaning Checkpoint (Week 3–5):** Hoàn thành hồ sơ kiểm toán chất lượng 6 chiều, xử lý missing/outliers, merge dữ liệu và tạo Pipeline.
* **Milestone 3 – Báo cáo Giữa kỳ Midterm (Week 8):** Nộp báo cáo EDA 8–10 trang, thuyết trình 7 phút + 3 phút hỏi đáp phản biện (*Viva*). Trọng số điểm: Cleaning 25%, EDA depth 25%, Chart 20%, Interpretation 20%, Presentation 10%.
* **Milestone 4 – Phân tích Nâng cao & Modeling (Week 9–11):** Thực hiện kiểm định giả thuyết, mô hình hóa hồi quy OLS (LINE diagnostics), phân loại cảnh báo ô nhiễm.
* **Milestone 5 – Project Charter & Storytelling (Week 12–14):** Đánh giá Bias/Ethics, viết Model Card, hoàn thiện cấu trúc SCQA và tinh chỉnh code cùng giảng viên.
* **Milestone 6 – Final Defense (Week 15):** Bảo vệ đồ án trước hội đồng, giải trình từng dòng code, nộp repo GitHub hoàn chỉnh và báo cáo cuối kỳ.

---

## 2. RESEARCH QUESTIONS (CÂU HỎI NGHIÊN CỨU)

### 2.1. Đề xuất 4 câu hỏi nghiên cứu ứng viên
1. **RQ1 (Xu hướng & Chu kỳ thời gian):** Nồng độ bụi mịn $\text{PM}_{2.5}$ biến thiên như thế nào theo các chu kỳ thời gian (theo giờ trong ngày, ngày trong tuần, và các tháng trong năm), và có xu hướng tăng/giảm dài hạn trong giai đoạn quan trắc hay không?
2. **RQ2 (So sánh thống kê có đối chứng):** Có sự khác biệt có ý nghĩa thống kê về mức độ ô nhiễm giữa các ngày làm việc (Thứ Hai – Thứ Sáu) so với ngày cuối tuần (Thứ Bảy – Chủ Nhật) hay không, và nồng độ ô nhiễm mùa đông có thực sự cao hơn mùa hè hay chỉ là ngẫu nhiên? Độ lớn hiệu ứng (*Effect size*) là bao nhiêu?
3. **RQ3 (Quan hệ giữa Ô nhiễm & Khí tượng - Regression):** Các yếu tố khí tượng (nhiệt độ, độ ẩm tương đối, tốc độ gió, lượng mưa, áp suất) liên hệ như thế nào với nồng độ $\text{PM}_{2.5}$, và chúng giải thích được bao nhiêu phần trăm phương sai biến thiên của chất lượng không khí?
4. **RQ4 (Cảnh báo sớm - Classification):** Liệu có thể sử dụng các đặc trưng trễ của ô nhiễm kết hợp với thông số khí tượng để phân loại chính xác các ngày có nguy cơ vượt ngưỡng cảnh báo ô nhiễm nghiêm trọng ($\text{PM}_{2.5} > 50\,\mu\text{g/m}^3$ theo quy chuẩn) nhằm phục vụ cảnh báo sức khỏe cộng đồng hay không?

---

### 2.2. Lựa chọn Câu hỏi Nghiên cứu Mục tiêu

* **MAIN RESEARCH QUESTION:**
  > *"Nồng độ bụi mịn $\text{PM}_{2.5}$ tại khu vực nghiên cứu biến động theo những quy luật chu kỳ thời gian nào, chịu sự liên hệ ra sao bởi các yếu tố khí tượng bề mặt, và làm thế nào để xây dựng mô hình cảnh báo sớm các đợt ô nhiễm vượt ngưỡng an toàn dựa trên dữ liệu chuỗi thời gian?"*

* **CÁC SUB-QUESTIONS HỖ TRỢ:**
  - **SQ1 (Phân phối & Đo lường):** Phân phối của nồng độ $\text{PM}_{2.5}$ có hình dạng lệch (*skewness*) và đuôi dày (*heavy tails*) như thế nào? Cặp đại lượng nào (Mean/Std hay Median/IQR) phản ánh trung thực nhất mức độ phơi nhiễm điển hình của người dân?
  - **SQ2 (Chu kỳ & Suy luận):** Sự sụt giảm ô nhiễm vào ngày cuối tuần (do giảm lưu lượng giao thông) và sự gia tăng ô nhiễm vào mùa đông (do hiện tượng nghịch nhiệt) có đạt ý nghĩa thống kê ở mức $\alpha = 0.05$ hay không?
  - **SQ3 (Mô hình hóa liên hệ):** Trong điều kiện kiểm soát các yếu tố khác không đổi (*ceteris paribus*), tốc độ gió và độ ẩm không khí liên hệ như thế nào với nồng độ bụi mịn? Có hiện tượng đa cộng tuyến giữa các biến thời tiết không?
  - **SQ4 (Cảnh báo & Đánh đổi):** Khi xây dựng mô hình phân loại cảnh báo ngày ô nhiễm cao, sự đánh đổi giữa Precision và Recall được giải quyết thế nào để giảm thiểu rủi ro sức khỏe cộng đồng (hạn chế tối đa False Negative)?

---

## 3. THIẾT KẾ DATA PLAN (KẾ HOẠCH DỮ LIỆU)

### 3.1. Bảng đặc tả các biến dữ liệu thu thập

| Tên biến | Kiểu dữ liệu | Đơn vị | Tần suất đo | Vai trò & Lý do thu thập | Nguồn phù hợp | Khả năng ghép nối (Integration) |
|---|---|---|---|---|---|---|
| `timestamp` | Datetime (ISO 8601) | `YYYY-MM-DD HH:mm:ss` | 1 giờ | Trục thời gian chuẩn, dùng để trích xuất giờ, ngày, thứ, tháng và làm khóa nối | OpenAQ / Open-Meteo | Khóa chính (*Primary Key*) để merge bảng |
| `station_id` | String | Danh mục mã trạm | Cố định | Định danh trạm đo mặt đất, kiểm soát tính đồng nhất không gian | OpenAQ | Khóa phân nhóm (*Group Key*) |
| `pm25` | Float64 | $\mu\text{g/m}^3$ | 1 giờ | **Biến mục tiêu cốt lõi**; chất gây ô nhiễm nguy hiểm nhất cho hô hấp | OpenAQ (US Embassy / Trạm chuẩn) | Nối theo `timestamp` |
| `pm10` | Float64 | $\mu\text{g/m}^3$ | 1 giờ | Bụi thô; dùng để kiểm tra tính hợp lệ quan hệ vật lý: $\text{PM}_{2.5} \le \text{PM}_{10}$ | OpenAQ | Nối theo `timestamp` |
| `temperature` | Float64 | $^\circ\text{C}$ | 1 giờ | Ảnh hưởng đến đối lưu không khí và phản ứng quang hóa | Open-Meteo API | Nối theo `timestamp` |
| `relative_humidity` | Float64 | $\%$ | 1 giờ | Độ ẩm cao kích thích hút ẩm làm nở hạt bụi và gây lỗi cảm biến quang học | Open-Meteo API | Nối theo `timestamp` |
| `wind_speed` | Float64 | $\text{m/s}$ | 1 giờ | Động lực phát tán và pha loãng chất ô nhiễm; gió lặng gây tích tụ | Open-Meteo API | Nối theo `timestamp` |
| `wind_direction` | Float64 | Độ ($0^\circ - 360^\circ$) | 1 giờ | Hướng vận chuyển bụi từ các vùng công nghiệp lân cận | Open-Meteo API | Nối theo `timestamp` |
| `precipitation` | Float64 | $\text{mm}$ | 1 giờ | Hiệu ứng "rửa trôi" (*Wet scavenging*), kéo bụi mịn lắng đọng xuống đất | Open-Meteo API | Nối theo `timestamp` |
| `surface_pressure` | Float64 | $\text{hPa}$ | 1 giờ | Áp suất cao thường gắn liền với nghịch nhiệt và thời tiết tĩnh đọng mùa đông | Open-Meteo API | Nối theo `timestamp` |

---

### 3.2. Phân tầng nguồn dữ liệu (Primary, Secondary, Backup)

```text
               PHÂN TẦNG NGUỒN DỮ LIỆU ĐỒ ÁN
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
NGUỒN CHÍNH             NGUỒN PHỤ               NGUỒN BACKUP
• OpenAQ REST API v3    • Open-Meteo API        • AirNow US Dept State CSV
• Trạm US Embassy HN    • ERA5 Reanalysis       • PAM Air Open Portal
• PM2.5, PM10 theo giờ  • T, RH, Wind, Rain     • Kaggle Hanoi Benchmark
```

1. **Nguồn chính (Primary Source): OpenAQ REST API v3**
   - *Lý do:* Nền tảng dữ liệu mở phi lợi nhuận lớn nhất thế giới về quan trắc chất lượng không khí. Cung cấp dữ liệu từ các thiết bị đo tham chiếu đạt chuẩn EPA (Beta Attenuation Monitor - BAM 1020).
   - *Khoảng thời gian:* Thu thập 2 năm trọn vẹn (ví dụ: từ 01/01/2023 đến 31/12/2024) để đủ chu kỳ 4 mùa và so sánh năm trước - năm sau.
   - *License:* Open Data Commons Attribution License (ODC-BY).
2. **Nguồn phụ (Secondary Source): Open-Meteo Historical Weather API**
   - *Lý do:* Cung cấp dữ liệu khí tượng tái phân tích lịch sử độ phân giải cao (ERA5 Reanalysis) dựa trên đúng tọa độ địa lý của trạm quan trắc mặt đất. Miễn phí cho nghiên cứu học thuật, không bắt buộc API key thương mại.
   - *License:* Creative Commons Attribution 4.0 International (CC BY 4.0).
3. **Nguồn Backup (Dự phòng rủi ro mạng/API):**
   - *Backup 1:* Tải trực tiếp kho lưu trữ CSV hàng năm từ **AirNow US Department of State Historical Files** (không phụ thuộc vào API rate limit).
   - *Backup 2:* Dữ liệu quan trắc trạm Hà Nội từ mạng lưới PAM Air hoặc cổng môi trường Hà Nội (Envidata).

---

### 3.3. Đánh giá rủi ro kỹ thuật theo yêu cầu Week 2
* **Bản quyền & Giấy phép (License):** Cả OpenAQ và Open-Meteo đều cho phép sử dụng tự do cho mục đích nghiên cứu học thuật với điều kiện ghi rõ nguồn trích dẫn (*Attribution*). Đưa tuyên bố bản quyền này vào `README.md`.
* **API Rate Limit & Phân trang (Pagination):**
  - OpenAQ v3 giới hạn số request/phút. Áp dụng chiến lược: Gửi request theo từng block tháng, phân trang qua tham số `page` và `limit=1000`, chèn khoảng nghỉ `time.sleep(1.0)` giữa các request.
  - Lưu kết quả trung gian theo từng file JSON/CSV nhỏ trong `data/raw/` trước khi gộp để phòng ngừa mất mạng giữa chừng.
* **Thời gian & Múi giờ (Timezone & Timeliness):** OpenAQ trả về cả `utc` và `local`. Cần quy chuẩn đồng nhất toàn bộ mốc thời gian về múi giờ Việt Nam: `Asia/Ho_Chi_Minh` (UTC+7).
* **Missing Data & Thay đổi Schema:** Ghi nhận metadata cấu trúc payload JSON của OpenAQ tại thời điểm thu thập vào file `data/raw/metadata.json`.

---

## 4. BỘ TIÊU CHUẨN KIỂM TOÁN VÀ LÀM SẠCH DỮ LIỆU (DATA CLEANING CHECKLIST)

### 4.1. Phân loại lỗi theo 3 cấp độ

#### A. Cấp độ giá trị (Value Level)
- [ ] **Missing ngụy trang:** Các chuỗi ký tự thể hiện trạm lỗi: `"-999"`, `"-9999"`, `"N/A"`, `"None"`, `"null"`, `""`. Khai báo ngay khi nạp file: `na_values=['-999', 'N/A', 'None']`.
- [ ] **Giá trị âm hoặc bằng 0 bất thường:** Về mặt vật lý, bụi mịn trong không khí đô thị không thể đạt giá trị âm ($\text{PM}_{2.5} < 0$) và cực kỳ khó duy trì mức $0.00\,\mu\text{g/m}^3$ liên tục nhiều giờ. Đổi các giá trị $\le 0$ thành `NaN`.
- [ ] **Lỗi kẹt cảm biến (Stuck values):** Nồng độ bụi giữ nguyên một giá trị đến từng chữ số thập phân suốt $> 6$ giờ liên tục. Đây là lỗi treo phần cứng của sensor $\to$ Cần đánh dấu và chuyển thành `NaN`.
- [ ] **Nhiễu do độ ẩm cực cao (Optical Sensor Fog Error):** Cảm biến quang học đo bụi bằng nguyên lý tán xạ ánh sáng. Khi độ ẩm không khí $\text{RH} > 90\%$, các hạt sương mù nước bị cảm biến đếm nhầm thành hạt bụi mịn, làm nồng độ $\text{PM}_{2.5}$ nhảy vọt ảo $\to$ Cần tạo cờ cảnh báo `is_high_humidity_fog`.

#### B. Cấp độ bản ghi (Record Level)
- [ ] **Trùng lặp mốc thời gian (Duplicate Timestamps):** Cùng một trạm đo nhưng xuất hiện 2 bản ghi cho cùng một giờ. Kiểm tra: `df.duplicated(subset=['timestamp', 'station_id']).sum()`. Xử lý bằng cách giữ bản ghi sau cùng hoặc lấy trung bình.
- [ ] **Dữ liệu đảo lộn thứ tự thời gian:** Chuỗi thời gian bị xáo trộn do ghép các đợt gọi API. Bắt buộc: `df = df.sort_values('timestamp').reset_index(drop=True)`.
- [ ] **Khoảng trống chuỗi thời gian (Gaps in Time Series):** Trạm đo bị mất nguồn điện hoặc bảo trì, khiến chuỗi giờ bị đứt quãng. Cần reindex lại theo khung giờ đầy đủ:
  ```python
  full_idx = pd.date_range(start=df['timestamp'].min(), end=df['timestamp'].max(), freq='h')
  df = df.set_index('timestamp').reindex(full_idx).rename_axis('timestamp').reset_index()
  ```

#### C. Cấp độ quan hệ & Logic nghiệp vụ (Relationship Level)
- [ ] **Vi phạm quy luật vật lý ($\text{PM}_{2.5} > \text{PM}_{10}$):** $\text{PM}_{2.5}$ là các hạt bụi có đường kính khí động học $\le 2.5\,\mu\text{m}$, vốn là một tập con của $\text{PM}_{10}$ ($\le 10\,\mu\text{m}$). Do đó, về mặt vật lý:
  $$\text{PM}_{2.5} \le \text{PM}_{10}$$
  Nếu tại bất kỳ thời điểm nào $\text{PM}_{2.5} > \text{PM}_{10} + \epsilon$ (sai số cho phép $1-2\,\mu\text{g/m}^3$), bản ghi đó chắc chắn bị lỗi thiết bị $\to$ Chuyển cả 2 thành `NaN`.
- [ ] **Quan hệ giữa hai nguồn dữ liệu:** Độ ẩm tương đối không được vượt quá $100\%$ hoặc nhỏ hơn $0\%$; Tốc độ gió không âm; Hướng gió nằm trong $[0^\circ, 360^\circ]$.

---

### 4.2. Đánh giá bộ dữ liệu theo 6 chiều chất lượng (6 Dimensions)
1. **Completeness (Độ đầy đủ):** Đo lường tỷ lệ missing trên từng cột. Nhận diện cơ chế: Nếu mất dữ liệu 1–2 giờ ngẫu nhiên do truyền sóng mạng $\to$ **MCAR**; nếu trạm đo mất điện hàng loạt trong đợt mưa bão lớn $\to$ **MAR** (phụ thuộc vào biến mưa); nếu sensor bị bão hòa ngừng đo trong đợt ô nhiễm lịch sử $\to$ **MNAR**.
2. **Accuracy (Độ chính xác):** Kiểm tra xem số đo có phản ánh đúng thực tế không qua việc so sánh đối chiếu giữa trạm US Embassy (trạm chuẩn) và các trạm cảm biến thương mại lân cận.
3. **Consistency (Độ nhất quán):** Đảm bảo đơn vị đo là $\mu\text{g/m}^3$ (tránh nhầm lẫn với đơn vị $ppm$ hay $ppb$ của các loại khí), mốc thời gian hoàn toàn là giờ địa phương Hà Nội (UTC+7).
4. **Validity (Tính hợp lệ):** Dữ liệu tuân thủ đúng định dạng `float64`, ngày tháng đúng `datetime64[ns]`, tọa độ địa lý hợp lệ.
5. **Uniqueness (Tính duy nhất):** Mọi cặp `(timestamp, station_id)` là duy nhất, không có dòng lặp.
6. **Timeliness (Tính kịp thời/Chuỗi liên tục):** Đảm bảo dữ liệu bao quát trọn vẹn cả 12 tháng của năm, không bị mất trắng cả một mùa quan trọng (ví dụ mất dữ liệu mùa đông sẽ làm sai lệch phân tích).

---

### 4.3. Chiến lược xử lý Missing Data & Cảnh báo Outlier
* **Chiến lược xử lý Missing trên chuỗi thời gian:**
  - Khoảng trống nhỏ ($1 - 2$ giờ liên tiếp): Sử dụng **Nội suy tuyến tính theo thời gian** (`df['pm25'].interpolate(method='time', limit=2)`).
  - Khoảng trống trung bình ($3 - 6$ giờ): Sử dụng **Group-wise median** theo khung giờ của tháng đó.
  - Khoảng trống lớn ($> 6$ giờ): **TUYỆT ĐỐI KHÔNG NỘI SUY BỪA BÃI**. Giữ nguyên `NaN` hoặc tạo cờ chỉ báo khuyết thiếu:
    ```python
    df['pm25_was_missing'] = df['pm25'].isna().astype(int)
    ```
* **Ứng xử với Outliers (Ngoại lai):**
  - **Quy tắc vàng số 8 của môn học:** *Không bao giờ xóa outlier chỉ vì nó "trông xấu"*.
  - *Outlier thực tế (Cần giữ lại):* Các đợt nồng độ $\text{PM}_{2.5}$ tăng vọt lên $250 - 350\,\mu\text{g/m}^3$ trong các đêm giao thừa đốt pháo hoa, đợt nghịch nhiệt kéo dài tháng 12 hoặc đợt đốt rơm rạ ngoại thành. Đây là những giá trị thực tế quan trọng nhất của bài toán môi trường.
  - *Outlier do lỗi đo (Cần loại bỏ):* Điểm đo tăng vọt lên hàng ngàn đơn vị trong đúng 1 giờ đơn lẻ trong khi giờ trước và sau đó hoàn toàn bình thường, đồng thời không có trạm đo lân cận nào ghi nhận.

---

## 5. THIẾT KẾ PHÂN TÍCH CHUỖI THỜI GIAN (TIME-SERIES)

1. **Phân tích theo Giờ trong ngày (Diurnal Cycle - Hourly Aggregation):**
   - *Cách làm:* Nhóm theo `df.groupby('hour')['pm25'].agg(['median', 'mean', lambda x: x.quantile(0.75) - x.quantile(0.25)])`.
   - *Quy luật cần tìm:* Phát hiện 2 đỉnh ô nhiễm trong ngày: Đỉnh sáng ($07:00 - 09:00$) và Đỉnh tối ($18:00 - 21:00$) trùng với giờ cao điểm phương tiện giao thông cá nhân di chuyển, cùng với sự sụt giảm vào đầu giờ chiều ($13:00 - 15:00$) do lớp biên khí quyển nâng cao làm pha loãng không khí.
2. **Phân tích theo Ngày trong tuần (Day-of-Week Effect):**
   - *Cách làm:* So sánh nồng độ trung bình/trung vị từ Thứ Hai đến Chủ Nhật.
   - *Quy luật cần tìm:* Hiệu ứng "ngày cuối tuần" (*Weekend effect*) — liệu thứ Bảy và Chủ Nhật nồng độ ô nhiễm có giảm đáng kể do học sinh nghỉ học, công sở giảm tải hoạt động?
3. **Phân tích theo Tháng và Mùa (Seasonal / Monthly Pattern):**
   - *Cách làm:* Boxplot nồng độ bụi của từng tháng từ Tháng 1 đến Tháng 12.
   - *Quy luật cần tìm:* Ô nhiễm không khí miền Bắc Việt Nam có tính mùa vụ rõ rệt: Mùa ô nhiễm cao điểm (Tháng 10 đến Tháng 3 năm sau - mùa hanh khô, gió mùa Đông Bắc mang bụi mịn, hiện tượng nghịch nhiệt giữ chất ô nhiễm sát mặt đất) đối lập với Mùa trong sạch (Tháng 5 đến Tháng 8 - mùa mưa rào dồi dào, đối lưu nhiệt mạnh mẽ đẩy bụi lên cao).
4. **Phân tích Xu hướng dài hạn & Lọc nhiễu (Trend & Rolling Averages):**
   - *Cách làm:* Tính đường trung bình động 24 giờ (`rolling_24h`) để triệt tiêu biến động ngày đêm, và đường trung bình động 7 ngày (`rolling_7d`) để quan sát xu hướng các đợt bùng phát không khí xấu (*Pollution episodes*). Phân rã chuỗi thời gian thành 3 thành phần: *Trend + Seasonal + Residual* bằng `seasonal_decompose` (statsmodels).

---

## 6. THỐNG KÊ MÔ TẢ (DESCRIPTIVE STATISTICS)

Tuân thủ nguyên tắc Week 6: **"Hình dạng quyết định chỉ số" (Shape picks the statistic)**.

### 6.1. Bảng cấu trúc 4 họ đại lượng thống kê

| Họ đại lượng | Chỉ số tính toán | Ý nghĩa đối với biến $\text{PM}_{2.5}$ | Rủi ro nếu chọn sai chỉ số |
|---|---|---|---|
| **1. Đo lường Vị trí (Location)** | - **Median (Trung vị)**<br>- Mean (Trung bình)<br>- Mode (Yếu vị) | Do $\text{PM}_{2.5}$ luôn lệch phải nặng ($\text{Mean} > \text{Median}$), **Median** phản ánh trung thực mức độ ô nhiễm của một ngày điển hình. | Nếu chỉ báo cáo Mean, các ngày nghịch nhiệt đột biến kéo chỉ số vọt lên, khiến bức tranh ô nhiễm bị thổi phồng so với phần lớn các ngày trong năm. |
| **2. Đo lường Phân tán (Spread)** | - **IQR ($Q_3 - Q_1$)**<br>- Độ lệch chuẩn ($s$)<br>- Range ($\max - \min$) | **IQR** đo độ biến thiên của 50% số ngày ở trung tâm, không bị méo mó bởi các ngày pháo hoa/đốt rơm rạ cực đoan. | Độ lệch chuẩn $s$ bị thổi phồng rất lớn khi có vài giá trị ngoại lai, làm sai lệch khoảng tin cậy cổ điển. |
| **3. Đo lường Hình dạng (Shape)** | - **Skewness (Độ lệch)**<br>- **Kurtosis (Độ nhọn/đuôi)** | - $\text{Skewness} > 1.0$: Khẳng định phân phối lệch phải mạnh.<br>- $\text{Kurtosis} > 3.0$: Phân phối có đuôi dày (*Leptokurtic*), cảnh báo sự hiện diện của các đợt ô nhiễm cực đoan. | Bỏ qua Skewness dẫn đến sai lầm nguy hiểm: dùng kiểm định tham số t-test khi dữ liệu vi phạm giả định chuẩn. |
| **4. Phân vị (Percentiles)** | - $P_{25}, P_{50}, P_{75}$<br>- $P_{90}, P_{95}, P_{99}$ | Cung cấp câu trả lời thiết thực cho y tế công cộng: $95\%$ số giờ trong năm người dân tiếp xúc với nồng độ bụi dưới bao nhiêu $\mu\text{g/m}^3$? | Không thể trả lời câu hỏi chính sách nếu chỉ nhìn vào Mean và Std. |

### 6.2. Đo lường tương quan (Correlation)
- Tính toán cả **Pearson $r$** (bắt quan hệ tuyến tính) và **Spearman $\rho$** (bắt quan hệ đơn điệu phi tuyến).
- Với quan hệ giữa Tốc độ gió và Bụi mịn, mối quan hệ mang tính nghịch biến phi tuyến $\to$ **Spearman $\rho$** thể hiện bản chất chính xác hơn Pearson.

---

## 7. BỘ THIẾT KẾ TRỰC QUAN HÓA (DATA VISUALIZATION PLAN)

### 7.1. Bảng chi tiết 7 biểu đồ ấn định cho đồ án

| Mã Chart | Câu hỏi trả lời | Loại Chart | Biến trục X | Biến trục Y | Mức tổng hợp | Đơn vị | Tiêu đề Explanatory chuẩn (State a Conclusion) |
|---|---|---|---|---|---|---|---|
| **FIG-01** | Ô nhiễm biến thiên dài hạn như thế nào và có các đợt ô nhiễm đột biến nào? | Line chart kết hợp Rolling Mean | Thời gian (Ngày) | $\text{PM}_{2.5}$ trung bình | Daily (kèm đường trượt 7d & 30d) | $\mu\text{g/m}^3$ | *"Ô nhiễm bụi mịn bùng phát thành từng đợt kéo dài từ tháng 11 đến tháng 2, vượt ngưỡng WHO gấp 4 lần"* |
| **FIG-02** | Hình dạng phân phối của bụi mịn có lệch chuẩn không? | Histogram + đường KDE | Nồng độ $\text{PM}_{2.5}$ | Mật độ xác suất (Density) | Hourly toàn bộ mẫu | $\mu\text{g/m}^3$ | *"Phân phối PM2.5 lệch phải nặng với trung vị 38 µg/m³, khẳng định sự cần thiết dùng Median thay vì Mean"* |
| **FIG-03** | Quy luật ô nhiễm biến động giữa các tháng trong năm ra sao? | Boxplot (kèm vạch ngưỡng chuẩn) | 12 Tháng trong năm | Nồng độ $\text{PM}_{2.5}$ | Monthly distribution | Tháng / $\mu\text{g/m}^3$ | *"Mùa đông ghi nhận nồng độ bụi trung vị cao gấp 2.8 lần mùa hè do hiện tượng nghịch nhiệt và gió mùa"* |
| **FIG-04** | Giờ nào trong ngày và ngày nào trong tuần có không khí độc hại nhất? | 2D Heatmap | Giờ trong ngày ($0 - 23\text{h}$) | Thứ trong tuần (T2 - CN) | Median theo từng ô (Hour $\times$ Day) | $\mu\text{g/m}^3$ | *"Đỉnh ô nhiễm tập trung vào khung giờ 7-9h sáng các ngày làm việc, phản ánh rõ nét áp lực giao thông đô thị"* |
| **FIG-05** | Tốc độ gió có thực sự giúp phân tán bụi mịn hay không? | Scatter plot + đường hồi quy LOWESS | Tốc độ gió (`wind_speed`) | $\text{PM}_{2.5}$ | Hourly | $\text{m/s}$ vs $\mu\text{g/m}^3$ | *"Tốc độ gió trên 3 m/s làm giảm 65% nồng độ bụi mịn; tình trạng lặng gió là điều kiện kích hoạt ô nhiễm tích tụ"* |
| **FIG-06** | Mức độ tương quan giữa các chất ô nhiễm và biến thời tiết là bao nhiêu? | Correlation Heatmap | Ma trận các biến | Ma trận các biến | Toàn bộ mẫu | Hệ số $r$ ($-1$ đến $+1$) | *"Nhiệt độ và tốc độ gió tương quan âm mạnh với PM2.5, trong khi áp suất khí quyển tương quan dương"* |
| **FIG-07** | Tỷ lệ số ngày vượt ngưỡng nguy hại cho sức khỏe theo tiêu chuẩn QCVN? | Bar chart (Bắt đầu từ 0) | 4 Mức độ chất lượng không khí | Tỷ lệ phần trăm số ngày | Phân loại theo năm | $\%$ số ngày | *"Hơn 42% số ngày trong năm ghi nhận chất lượng không khí ở mức Không lành mạnh cho nhóm nhạy cảm trở lên"* |

---

## 8. SUY LUẬN THỐNG KÊ (STATISTICAL INFERENCE)

Áp dụng đúng bài học Week 9: **"Inference is a leap"**. Không báo cáo $p$-value đơn độc! Bắt buộc trình bày bộ ba: **$p$-value + Kích thước hiệu ứng (Effect Size) + Khoảng tin cậy (Confidence Interval)**.

### 8.1. Kiểm định 1: So sánh Ô nhiễm Mùa Đông vs Mùa Hè
* **Câu hỏi nghiên cứu:** Nồng độ $\text{PM}_{2.5}$ trong Mùa Đông (Tháng 11–Tháng 2) có thực sự cao hơn Mùa Hè (Tháng 5–Tháng 8) hay sự khác biệt quan sát được chỉ do ngẫu nhiên?
* **Giả thuyết:**
  - $H_0: \tilde{\mu}_{\text{Đông}} = \tilde{\mu}_{\text{Hè}}$ (Trung vị nồng độ $\text{PM}_{2.5}$ hai mùa là như nhau).
  - $H_1: \tilde{\mu}_{\text{Đông}} > \tilde{\mu}_{\text{Hè}}$ (Nồng độ mùa Đông cao hơn có ý nghĩa thống kê – Kiểm định một phía).
* **Lựa chọn phép kiểm định & Giả định:**
  - Kiểm tra tính chuẩn bằng Shapiro-Wilk test: Cả 2 mùa đều vi phạm tính chuẩn ($p < 0.001$).
  - $\to$ Sử dụng **Kiểm định phi tham số Mann-Whitney U** (`scipy.stats.mannwhitneyu`).
* **Mức ý nghĩa:** $\alpha = 0.05$.
* **Kích thước hiệu ứng & Khoảng tin cậy:**
  - Tính hệ số tương quan hạng lưỡng phân (*Rank-Biserial Correlation* $r_{rb} = 1 - \frac{2U}{n_1 n_2}$).
  - Ước lượng khoảng tin cậy 95% cho chênh lệch trung vị bằng phương pháp **Bootstrap resampling** (1.000 lần lặp).
* **Mẫu câu kết luận chuẩn:** *"Kiểm định Mann-Whitney U cho thấy nồng độ $\text{PM}_{2.5}$ mùa Đông (Median = $52.4\,\mu\text{g/m}^3$) cao hơn có ý nghĩa thống kê so với mùa Hè (Median = $21.1\,\mu\text{g/m}^3$), $U = 142050, p < 0.001$. Kích thước hiệu ứng đạt mức lớn ($r_{rb} = 0.64$), với chênh lệch trung vị ước tính $31.3\,\mu\text{g/m}^3$ (95% CI: $[27.8, 34.9]\,\mu\text{g/m}^3$). Kết quả khẳng định tính mùa vụ là một quy luật thực tế mạnh mẽ, không phải do ngẫu nhiên."*

---

### 8.2. Kiểm định 2: So sánh Ngày làm việc (Weekday) vs Ngày cuối tuần (Weekend)
* **Câu hỏi nghiên cứu:** Áp lực giảm lưu lượng giao thông cuối tuần có tạo ra sự khác biệt có ý nghĩa thống kê đối với nồng độ $\text{PM}_{2.5}$ hay không?
* **Giả thuyết:**
  - $H_0: \text{Median}_{\text{Weekday}} = \text{Median}_{\text{Weekend}}$.
  - $H_1: \text{Median}_{\text{Weekday}} \ne \text{Median}_{\text{Weekend}}$.
* **Phép kiểm:** Mann-Whitney U test hai phía (`scipy.stats.mannwhitneyu`).
* **Ý nghĩa thực tiễn vs Thống kê:** Nếu chênh lệch nhỏ ($< 2\,\mu\text{g/m}^3$) nhưng $p < 0.05$ do cỡ mẫu lớn, cần phân tích rõ hiệu ứng này không mang ý nghĩa thực tiễn lớn.

---

### 8.3. Kiểm định 3: So sánh Nồng độ Trung bình năm với Quy chuẩn Quốc gia QCVN
* **Câu hỏi nghiên cứu:** Nồng độ $\text{PM}_{2.5}$ trung bình năm có vượt quá Quy chuẩn kỹ thuật quốc gia QCVN 05:2023/BTNMT (ngưỡng trung bình năm $25\,\mu\text{g/m}^3$) hay không?
* **Giả thuyết:** $H_0: \mu \le 25\,\mu\text{g/m}^3$ vs $H_1: \mu > 25\,\mu\text{g/m}^3$.
* **Phép kiểm:** One-sample Wilcoxon signed-rank test trên nồng độ trung bình ngày. Báo cáo 95% Confidence Interval của nồng độ trung bình năm.

---

## 9. PHÂN TÍCH HỒI QUY (REGRESSION ANALYSIS)

### 9.1. Thiết lập bài toán Hồi quy
* **Biến phụ thuộc ($Y$):** $Y = \log(1 + \text{PM}_{2.5})$ (`np.log1p`) để đảm bảo quan hệ tuyến tính và phần dư xấp xỉ phân phối chuẩn.
* **Các biến độc lập ($X$):** `temperature`, `relative_humidity`, `wind_speed`, `surface_pressure`, `pm25_lag24`.
* **Baseline so sánh:** Dummy Regressor luôn dự báo giá trị trung bình tập Train ($\hat{y} = \bar{y}_{\text{train}}$).
* **Train / Test Split:** **Phân chia theo mốc thời gian** (Train: 2023, Test: 2024), tỷ lệ $\approx 70/30$.

---

### 9.2. Chẩn đoán 4 Giả định OLS (LINE Checklist)

| Giả định | Tên giả định | Công cụ chẩn đoán | Dấu hiệu vi phạm & Cách khắc phục |
|---|---|---|---|
| **L** | **Linearity** (Tính tuyến tính) | Residuals vs Fitted values plot | Xuất hiện đường cong parabol $\to$ Thêm bậc 2 hoặc log transform |
| **I** | **Independence** (Độc lập phần dư) | Durbin-Watson statistic | $d \ll 2$ (tự tương quan) $\to$ Bổ sung biến trễ lag1 / lag24 |
| **N** | **Normality** (Phần dư chuẩn) | Q-Q Plot và Shapiro-Wilk test | Điểm lệch xa đường chéo ở 2 đầu $\to$ Dùng log-target |
| **E** | **Equal Variance** (Phương sai đồng nhất) | Breusch-Pagan test / Residuals plot | Dạng cái phễu (Funnel) $\to$ Dùng Huber Regressor / Ridge |

* **Kiểm tra Đa cộng tuyến:** Tính chỉ số **VIF (Variance Inflation Factor)**. Nếu $\text{VIF} > 5.0$, loại bỏ biến tương quan hoặc áp dụng **Ridge Regression ($L_2$)**.
* **Kiểm tra Điểm ảnh hưởng:** Tính khoảng cách **Cook's Distance**. Các điểm có $D_i > 0.5$ cần được rà soát lỗi nhập liệu.

---

### 9.3. Đánh giá và Diễn giải Hệ số $\beta$
* **Thước đo đánh giá trên tập TEST:** Báo cáo **MAE**, **RMSE**, và **$R^2$** đặt cạnh Baseline.
* **Mẫu câu diễn giải 3 nghĩa vụ bắt buộc:**
  > *"Mỗi mét/giây ($\text{m/s}$) tốc độ gió tăng thêm **liên hệ với** mức giảm trung bình 12% nồng độ $\text{PM}_{2.5}$, **trong điều kiện giữ nguyên không đổi tất cả các biến số khác trong mô hình**, trong phạm vi tốc độ gió quan sát được từ 0.2 đến 8.5 m/s."*
  > *(Tuyệt đối không dùng từ "gây ra" - causes).*

---

## 10. PHÂN LOẠI & KỸ NGHỆ ĐẶC TRƯNG (CLASSIFICATION & FEATURE ENGINEERING)

### 10.1. Đặt bài toán & Nhãn nhị phân
* **Định nghĩa nhãn ($Y \in \{0, 1\}$):**
  - Lớp 1 (Ô nhiễm nghiêm trọng - Unhealthy Day): $\text{PM}_{2.5} \ge 50\,\mu\text{g/m}^3$ (theo ngưỡng quy chuẩn QCVN).
  - Lớp 0 (Bình thường / Chấp nhận được): $\text{PM}_{2.5} < 50\,\mu\text{g/m}^3$.

---

### 10.2. Kỹ nghệ đặc trưng (Feature Engineering)
Tạo ít nhất 5 đặc trưng miền ứng dụng:
1. `pm25_rolling_mean_24h`: Trung bình trượt 24 giờ trước đó (quán tính ô nhiễm).
2. `pm25_rolling_std_24h`: Độ biến động bất thường trong 24 giờ qua.
3. `temp_humidity_index`: Chỉ số tương tác nhiệt ẩm ($\text{temp} \times \text{humidity}$).
4. `wind_stagnant`: Cờ nhị phân báo hiệu lặng gió (`wind_speed < 1.0 m/s`).
5. `is_winter`: Cờ báo mùa cao điểm ô nhiễm (Tháng 11, 12, 1, 2).
6. `hour_sin`, `hour_cos`: Biến đổi tuần hoàn lượng giác của khung giờ 24h.

---

### 10.3. Xử lý Mất cân bằng & Thước đo Đánh giá
* **Mất cân bằng lớp (Class Imbalance):** Ngày ô nhiễm nặng chỉ chiếm $15 - 25\%$ tổng số ngày. Bẫy Accuracy: Đoán mò toàn bộ lớp 0 vẫn đạt $80\%$ accuracy nhưng Recall = $0\%$!
* **Thước đo chính:** Bắt buộc sử dụng **Recall** và **PR-AUC**. Chi phí bỏ sót ngày ô nhiễm nặng (False Negative) khiến người dân hít phải khí độc và nhập viện nguy hiểm hơn nhiều việc cảnh báo nhầm (False Positive).
* **Threshold Tuning:** Hạ ngưỡng kích hoạt từ $0.5$ xuống $0.30$ để tối đa hóa Recall:
  ```python
  y_proba = model.predict_proba(X_test)[:, 1]
  y_pred_tuned = (y_proba >= 0.30).astype(int)
  ```
* **Mô hình so sánh:** Baseline (DummyClassifier) vs Logistic Regression (`class_weight='balanced'`) vs Random Forest Classifier.

---

### 10.4. Kiểm toán chống Rò rỉ Dữ liệu (Data Leakage Audit)
1. **Target Leakage:** Loại trừ biến `AQI` ra khỏi tập đặc trưng (vì AQI tính trực tiếp từ $\text{PM}_{2.5}$).
2. **Train-Test Contamination:** Scaler và Imputer chỉ `fit` trên tập Train qua Scikit-Learn Pipeline.
3. **Temporal Leakage:** Tập dữ liệu chia theo thứ tự thời gian tuyến tính ($T_{\text{train}} < T_{\text{test}}$), đặc trưng trễ chỉ tính trên dữ liệu quá khứ.
4. **Group Leakage:** Không có quan sát nào của cùng một ngày xuất hiện ở cả hai tập.

---

## 11. ĐẠO ĐỨC DỮ LIỆU, ĐỊNH KIẾN & GIỚI HẠN (ETHICS, BIAS & LIMITATIONS)

### 11.1. Sổ tay Định kiến (Field Guide to Bias)
* **Sensor Bias:** Cảm biến quang học đo bụi giá rẻ dễ bị lệch chuẩn khi độ ẩm cao ($\text{RH} > 90\%$). Dữ liệu trạm cần được đối chiếu định kỳ với trạm chuẩn quốc tế.
* **Spatial Representation Bias:** Trạm quan trắc thường đặt tại khu trung tâm, thiếu vắng trạm đo tại khu công nghiệp ngoại thành, dẫn đến việc đánh giá thấp mức độ phơi nhiễm thực tế của toàn bộ dân cư.
* **Survivorship / Missing-Data Bias:** Trạm đo dễ bị ngắt kết nối khi mưa bão ngập lụt. Xóa bỏ dòng missing vô tình xóa đi dữ liệu của những ngày thời tiết cực đoan nhất (*Abraham Wald's airplane lesson*).
* **Phân biệt "Không có dữ liệu" và "Ô nhiễm bằng 0":** Dữ liệu khuyết (`NaN`) tuyệt đối không gán bằng số `0`.

---

### 11.2. Mẫu Datasheet for Dataset & Model Card
1. **Datasheet for Dataset (1 trang):** Mô tả nguồn gốc OpenAQ & Open-Meteo, thời gian 2023–2024, đối tượng thiếu biểu đạt (nông thôn, ven khu công nghiệp), mục đích hợp lệ (nghiên cứu, cảnh báo cộng đồng), mục đích cấm (xử phạt doanh nghiệp).
2. **Model Card (1 trang):** Tên mô hình Early Air Quality Alert Classifier v1, kiến trúc Random Forest kết hợp threshold $0.30$, hiệu năng phân tầng theo mùa, giới hạn không áp dụng cho sự kiện thời tiết cực đoan chưa từng thấy (cháy rừng, siêu bão).
3. **Tuyên bố AI trong `README.md`:** Khai báo cụ thể các nội dung có AI hỗ trợ và cam kết sinh viên tự giải trình $100\%$ logic toán học trong buổi phản biện (*Viva*).

---

## 12. CÔNG NGHỆ VÀ CẤU TRÚC DỰ ÁN (PROJECT STRUCTURE)

### 12.1. Tech Stack khuyến nghị
* **Ngôn ngữ:** Python 3.10+
* **Thao tác & Lưu trữ:** Pandas, NumPy, PyArrow / FastParquet (định dạng Parquet).
* **Trực quan hóa:** Matplotlib (hướng đối tượng `fig, ax`), Seaborn.
* **Thống kê & Suy luận:** SciPy (`scipy.stats`), Statsmodels (`statsmodels.api`, `statsmodels.tsa`).
* **Học máy & Pipeline:** Scikit-Learn (`sklearn.pipeline`, `sklearn.compose`).
* **Quản lý mã nguồn:** Git, GitHub repository.

---

### 12.2. Cấu trúc Repository chuẩn mực

```text
air-pollution-analysis/
├── .gitignore               # Loại trừ data/raw, __pycache__, .env
├── README.md                # Giới thiệu dự án, cách tái lập, bảng phân công, AI usage
├── requirements.txt         # Danh sách thư viện và phiên bản cố định
├── data/
│   ├── raw/                 # DỮ LIỆU GỐC BẤT BIẾN (.json, .csv tải về từ API)
│   │   └── metadata.json    # Thông tin thời điểm cào, schema gốc, bản quyền
│   ├── interim/             # Dữ liệu sau khi kiểm toán, xử lý múi giờ
│   └── processed/           # Dữ liệu sạch hoàn chỉnh lưu dạng .parquet
├── docs/
│   ├── data_dictionary.md   # Từ điển dữ liệu (Tên cột, Kiểu, Đơn vị, Ý nghĩa)
│   ├── cleaning_log.md      # Nhật ký làm sạch (Mọi quyết định đều có lý do)
│   ├── datasheet.md         # Datasheet for Dataset chuẩn Week 12
│   └── model_card.md        # Model Card 1 trang chuẩn Week 12
├── notebooks/
│   ├── 01_data_collection.ipynb       # Script gọi API OpenAQ & Open-Meteo
│   ├── 02_quality_audit_cleaning.ipynb# 6 Chiều chất lượng, xử lý missing/outlier
│   ├── 03_exploratory_data_analysis.ipynb # Thống kê mô tả 4 họ chỉ số, Seaborn EDA
│   ├── 04_statistical_inference.ipynb # 3 Phép kiểm định giả thuyết, Effect sizes
│   ├── 05_regression_modeling.ipynb   # OLS, LINE diagnostics, Ridge/Lasso
│   └── 06_classification_alerts.ipynb # Random Forest, PR-AUC, Threshold tuning
├── src/
│   ├── __init__.py
│   ├── data_loader.py       # Hàm nạp file Parquet, kiểm tra schema
│   ├── cleaning_pipeline.py # Scikit-Learn Pipeline đóng gói tiền xử lý
│   └── visualizer.py        # Hàm vẽ biểu đồ chuẩn phong cách Tufte/Cleveland
├── figures/                 # Toàn bộ biểu đồ xuất ra chuẩn in ấn (.png, dpi=300)
└── reports/
    ├── midterm_report.pdf   # Báo cáo giữa kỳ EDA (8-10 trang, Tuần 8)
    └── final_report.pdf     # Báo cáo đồ án tốt nghiệp môn học (Tuần 15)
```

---

## 13. XUẤT KẾT QUẢ TỔNG QUAN THEO YÊU CẦU

### A. Project Scope
* **Tên dự án:** Phân tích mức độ ô nhiễm không khí theo thời gian và xây dựng mô hình cảnh báo sớm bụi mịn $\text{PM}_{2.5}$.
* **Main Research Question:** Nồng độ bụi mịn $\text{PM}_{2.5}$ biến động theo những quy luật chu kỳ thời gian nào, liên hệ ra sao với các yếu tố khí tượng bề mặt, và làm thế nào để cảnh báo sớm các đợt ô nhiễm vượt ngưỡng an toàn?
* **Sub-questions:**
  - SQ1: Hình dạng phân phối của $\text{PM}_{2.5}$ có đặc tính lệch ra sao và đại lượng thống kê nào phản ánh trung thực nhất?
  - SQ2: Sự khác biệt ô nhiễm giữa ngày làm việc vs cuối tuần, giữa mùa đông vs mùa hè có đạt ý nghĩa thống kê kèm effect size lớn không?
  - SQ3: Tốc độ gió và độ ẩm chi phối nồng độ bụi ra sao khi kiểm soát các biến khác trong mô hình hồi quy OLS (thỏa mãn giả định LINE)?
  - SQ4: Mô hình phân loại cảnh báo ngày ô nhiễm cao giải quyết bài toán mất cân bằng lớp và tối ưu hóa Recall như thế nào?
* **Dataset:** Chuỗi thời gian quan trắc 2 năm (2023–2024) theo giờ, tích hợp giữa trạm đo $\text{PM}_{2.5}$ OpenAQ (US Embassy) và dữ liệu khí tượng Open-Meteo tại Hà Nội.
* **Expected Outputs:** 1 Repo GitHub hoàn chỉnh (chạy thông suốt từ đầu đến cuối), 1 Báo cáo EDA Giữa kỳ (8–10 trang), 1 Báo cáo Đồ án Cuối kỳ, 7 biểu đồ Explanatory chuẩn mực in ấn, 1 Datasheet for Dataset, 1 Model Card.

---

### B. Skill Mapping (Ma trận Ánh xạ Kiến thức INFO3020)

| Chủ đề INFO3020 | Nội dung áp dụng cụ thể trong Project | Bắt buộc? |
|---|---|:---:|
| **W1: What is Data Science** | Vòng đời CRISP-DM, cấu trúc repo chuẩn, dữ liệu raw bất biến | **Bắt buộc** |
| **W2: Multi-source Data Collection** | Thu thập đa nguồn (API OpenAQ + Open-Meteo), Data Dictionary, lưu trữ Parquet | **Bắt buộc** |
| **W3: Data Quality & Processing** | Kiểm toán 6 chiều chất lượng, phân loại MCAR/MAR/MNAR, missing ngụy trang | **Bắt buộc** |
| **W4: Practical Cleaning** | Xử lý lỗi trạm đo, logic vật lý $\text{PM}_{2.5} \le \text{PM}_{10}$, lập Cleaning Log | **Bắt buộc** |
| **W5: Transformation & Integration** | RobustScaler, log-transform, merge theo timestamp không nổ dòng, Sklearn Pipeline | **Bắt buộc** |
| **W6: Descriptive Statistics** | 4 họ chỉ số, chứng minh phân phối lệch phải dùng Median/IQR, kiểm tra Anscombe | **Bắt buộc** |
| **W7: Data Visualization** | Nguyên tắc Tufte (Data-ink), Cleveland ranking, SCQA storytelling, tiêu đề kết luận | **Bắt buộc** |
| **W8: Midterm Project** | Báo cáo giữa kỳ 8–10 trang, thuyết trình 7 phút + 3 phút viva | **Bắt buộc** |
| **W9: Statistical Inference** | Kiểm định Mann-Whitney U mùa đông vs hè, ngày thường vs cuối tuần, báo cáo Effect size + CI | **Bắt buộc** |
| **W10: Regression Analysis** | Hồi quy OLS tác động khí tượng lên $\text{PM}_{2.5}$, chẩn đoán giả định LINE, VIF, Cook's dist | **Bắt buộc** |
| **W11: Classification & Features** | Dự báo cảnh báo ô nhiễm vượt ngưỡng, feature lags/rolling, xử lý imbalance, PR-AUC | **Bắt buộc** |
| **W12: Big Data, Ethics & Bias** | Giải trình tại sao không dùng Spark, kiểm toán 4 loại bias, lập Datasheet & Model Card | **Bắt buộc** |
| **W13-14: Project Work** | Tinh chỉnh Pipeline, hoàn thiện cấu trúc SCQA, tham vấn giảng viên | **Bắt buộc** |
| **W15: Final Defense** | Thuyết trình bảo vệ đồ án cuối kỳ, vấn đáp code viva trước hội đồng | **Bắt buộc** |

---

### C. Weekly Roadmap (Bảng Tóm tắt Lộ trình 15 Tuần)

| Week | Giai đoạn & Mục tiêu | Tasks chính | Deliverables | Definition of Done |
|:---:|---|---|---|---|
| **W01** | **Khởi động & Môi trường**<br>Thiết lập chuẩn dự án CRISP-DM | Khởi tạo repo GitHub, file cấu trúc, `.gitignore`, môi trường `requirements.txt` | Repo GitHub skeleton, `README.md` | Repo clone về máy khác chạy `pip install` thành công 100% |
| **W02** | **Thu thập Đa nguồn**<br>Thu thập dữ liệu thô và tài liệu hóa | Viết script gọi API OpenAQ & Open-Meteo (2023-2024), lưu vào `data/raw/` | Script cào, file raw data, `data_dictionary.md` | Dữ liệu thô lưu bất biến, từ điển dữ liệu đủ 100% các cột |
| **W03** | **Kiểm toán Chất lượng**<br>Định lượng 6 chiều chất lượng | Viết hàm audit, chấm điểm 1-5 cho 6 dimensions, bóc trần missing ngụy trang | Báo cáo kiểm toán 2 trang, bảng phân loại MCAR/MNAR | Mọi cột missing đều được gán nhãn cơ chế cụ thể |
| **W04** | **Làm sạch Thực chiến**<br>Xử lý lỗi trạm và chuỗi thời gian | Lọc $\text{PM}_{2.5} > \text{PM}_{10}$, xử lý kẹt sensor, reindex khung giờ đầy đủ | Notebook cleaning, file `cleaning_log.md` | Không còn giá trị âm vô lý, mọi phép xóa đều có lý do ghi log |
| **W05** | **Tích hợp & Pipeline**<br>Ghép nối 2 nguồn và đóng gói | Merge dữ liệu ô nhiễm + khí tượng theo timestamp, đóng gói ColumnTransformer | File `processed_air_weather.parquet`, Pipeline script | Số dòng trước và sau merge được kiểm soát, không rò rỉ dữ liệu |
| **W06** | **Thống kê Mô tả**<br>Xác lập hồ sơ thống kê 4 họ | Tính Mean/Median/IQR/Skewness/Kurtosis, Pearson/Spearman, Anscombe check | Notebook EDA thống kê, bảng profile 4 họ chỉ số | Chứng minh định lượng tại sao dùng Median/IQR thay vì Mean/Std |
| **W07** | **Trực quan hóa Dữ liệu**<br>Thiết kế 5 headline charts | Vẽ FIG-01 đến FIG-05 theo Tufte/Cleveland, tối ưu data-ink, viết tiêu đề kết luận | 5 biểu đồ `.png` (dpi=300), draft cấu trúc SCQA | 100% biểu đồ có tiêu đề là kết luận, bar chart bắt đầu từ 0 |
| **W08** | **MIDTERM MILESTONE**<br>Báo cáo & Thuyết trình giữa kỳ | Hoàn thiện báo cáo 8-10 trang, slide thuyết trình 7 phút, tập dượt viva | `midterm_report.pdf`, slide deck, repo commit | Báo cáo nộp trước deadline, notebook Restart & Run All thành công |
| **W09** | **Suy luận Thống kê**<br>Kiểm định giả thuyết có đối chứng | Chạy Mann-Whitney U test (Đông vs Hè, Ngày thường vs Cuối tuần), tính Effect size, CI | Notebook inference, bảng tổng hợp kết quả kiểm định | Bắt buộc có đủ: p-value, Effect Size (r_rb), 95% Bootstrap CI |
| **W10** | **Phân tích Hồi quy**<br>Hồi quy OLS & Chẩn đoán LINE | Train/test split theo thời gian, fit OLS log-target, vẽ Residual plots, tính VIF, Cook's dist | Notebook regression, biểu đồ chẩn đoán LINE, câu diễn giải $\beta$ | Đạt đủ 4 kiểm tra LINE, diễn giải $\beta$ đúng mẫu câu 3 nghĩa vụ |
| **W11** | **Phân loại Cảnh báo**<br>Dự báo ngày ô nhiễm vượt ngưỡng | Tạo lags/rolling features, train Random Forest, tuning threshold, vẽ PR-Curve | Notebook classification, bảng so sánh Baseline vs Models | Đánh giá bằng Recall và PR-AUC, kiểm toán 4 loại leakage |
| **W12** | **Đạo đức, Bias & Charter**<br>Đánh giá định kiến & Big Data | Đánh giá kích thước dữ liệu vs Spark, kiểm toán 4 loại bias, viết Datasheet & Model Card | `datasheet.md`, `model_card.md`, Project Charter | Hoàn thành checklist đạo đức nộp cùng đồ án môn học |
| **W13** | **Cố vấn & Tinh chỉnh**<br>Review đồ án cùng giảng viên | Họp phản biện cùng ThS. Phạm Ngọc Đông, rà soát lại toàn bộ pipeline và số liệu | Bản cập nhật đồ án theo feedback giảng viên | Giải quyết $100\%$ các điểm nghi vấn của giảng viên |
| **W14** | **Data Storytelling**<br>Hoàn thiện báo cáo & Slide cuối kỳ | Viết báo cáo toàn diện theo khung SCQA, hoàn thiện slide thuyết trình cuối kỳ | `final_report.pdf`, slide thuyết trình bảo vệ | Báo cáo đầy đủ các chương mục từ dữ liệu đến hành động |
| **W15** | **FINAL DEFENSE**<br>Bảo vệ Đồ án Tốt nghiệp Môn học | Thuyết trình bảo vệ trước hội đồng, vấn đáp trả lời câu hỏi phản biện từng dòng code | Repo GitHub hoàn chỉnh, Biên bản bảo vệ | Trả lời tự tin mọi câu hỏi viva, repo chạy độc lập trơn tru |

---

### D. Research Pipeline (Sơ đồ Luồng Nghiên cứu Toàn diện)

```text
  [ 1. DATA COLLECTION ]
  ├── OpenAQ REST API v3 (PM2.5, PM10 theo giờ) ────────► data/raw/openaq_raw.json
  └── Open-Meteo Historical API (T, RH, Wind, Rain) ────► data/raw/weather_raw.json
                                                                  │
                                                                  ▼
  [ 2. QUALITY AUDIT & CLEANING ]
  ├── Kiểm toán 6 Chiều chất lượng (Audit Function)
  ├── Nhận diện Missing ngụy trang ("-999", "None")
  ├── Xử lý lỗi vật lý (PM2.5 <= PM10), lỗi cảm biến kẹt
  └── Reindex chuỗi thời gian liên tục ─────────────────► docs/cleaning_log.md
                                                                  │
                                                                  ▼
  [ 3. TRANSFORMATION & INTEGRATION ]
  ├── Merge theo timestamp (UTC+7, kiểm tra unique key)
  └── Đóng gói Scikit-Learn Pipeline (RobustScaler) ─────► data/processed/air_weather.parquet
                                                                  │
                                                                  ▼
  [ 4. EXPLORATORY DATA ANALYSIS (EDA) ]
  ├── 4 Họ thống kê mô tả (Median, IQR, Skewness, Kurtosis)
  ├── Bộ 7 biểu đồ Explanatory (Tufte, Cleveland)
  └── MIDTERM MILESTONE (W8): Báo cáo EDA 8-10 trang ────► reports/midterm_report.pdf
                                                                  │
                                                                  ▼
  [ 5. MODELING & INFERENCE ]
  ├── Suy luận Thống kê: Mann-Whitney U, Effect Size, CI (W9)
  ├── Hồi quy OLS: Chẩn đoán 4 giả định LINE, VIF, Cook's (W10)
  └── Phân loại Cảnh báo: Random Forest, PR-AUC, Threshold (W11)
                                                                  │
                                                                  ▼
  [ 6. SYNTHESIS, ETHICS & DEFENSE ]
  ├── Đánh giá Định kiến (Sensor, Spatial, Survivorship Bias)
  ├── Lập Datasheet for Dataset & Model Card 1 trang (W12)
  ├── Tinh chỉnh theo Cố vấn Giảng viên (W13)
  ├── Viết Báo cáo Tổng thể SCQA & Slide Bảo vệ (W14)
  └── FINAL DEFENSE (W15): Bảo vệ Đồ án trước Hội đồng ──► reports/final_report.pdf
```

---

### E. Final Deliverables (Danh mục Sản phẩm Bàn giao Cuối cùng)
1. **Repository GitHub chuẩn mực:**
   - Hoàn chỉnh cấu trúc thư mục, code module hóa trong `src/`.
   - Notebooks đánh số thứ tự từ `01_` đến `06_`, bảo đảm **Restart Kernel & Run All** thành công không lỗi.
   - File `requirements.txt` cố định phiên bản các thư viện.
2. **Bộ dữ liệu & Tài liệu đi kèm:**
   - Dữ liệu thô nguyên vẹn trong `data/raw/` kèm `metadata.json`.
   - Dữ liệu sạch `air_weather.parquet` trong `data/processed/`.
   - `data_dictionary.md` (Từ điển dữ liệu đầy đủ).
   - `cleaning_log.md` (Nhật ký ghi lại mọi quyết định xử lý).
3. **Các báo cáo & Thẻ chuẩn hóa (Documents):**
   - **Báo cáo Giữa kỳ (Midterm EDA Report):** 8–10 trang PDF theo chuẩn Rubric Tuần 8.
   - **Báo cáo Đồ án Cuối kỳ (Final Capstone Report):** Định dạng PDF hoàn chỉnh cấu trúc SCQA.
   - **Datasheet for Dataset (1 trang)** theo chuẩn Timnit Gebru (Week 12).
   - **Model Card (1 trang)** mô tả hiệu năng và giới hạn mô hình (Week 12).
   - **Slide thuyết trình:** Bản trình chiếu Giữa kỳ (7 phút) và Cuối kỳ (10–12 phút).
4. **Bộ biểu đồ ấn phẩm:** Thư mục `figures/` chứa đầy đủ 7 biểu đồ chất lượng cao (PNG 300 DPI), tiêu đề là kết luận.

---

### F. Risk Register (Bảng Quản trị Rủi ro Đồ án)

| Rủi ro tiềm ẩn | Xác suất (P) | Tác động (I) | Chiến lược Giảm thiểu (Mitigation) | Kế hoạch Dự phòng (Backup Plan) |
|---|:---:|:---:|---|---|
| **1. API OpenAQ bị lỗi mạng / Rate Limit** | Trung bình | Cao | Thêm khoảng nghỉ `time.sleep(1.0)` giữa các request; lưu cache từng tháng xuống disk ngay khi tải | Sử dụng dữ liệu CSV lịch sử tải sẵn từ AirNow US Department of State hoặc PAM Air |
| **2. Tỷ lệ Missing Data quá lớn trong các tháng bão** | Cao | Cao | Kiểm toán xác định cơ chế khuyết (MAR do bão); tuyệt đối không xóa dòng bừa bãi; tạo cờ `is_missing` | Bổ sung dữ liệu đối chứng từ trạm quan trắc lân cận hoặc trạm môi trường Chi cục Hà Nội |
| **3. Múi giờ bị lệch giữa 2 nguồn dữ liệu (Lỗi UTC)** | Trung bình | Cực cao | Ép kiểu `datetime` có timezone nhận thức (`tz_localize('UTC').tz_convert('Asia/Ho_Chi_Minh')`) ngay lúc đọc raw | Viết assert test kiểm tra đỉnh nhiệt độ ngày luôn phải rơi vào khung giờ 12:00 – 14:00 |
| **4. Lỗi bùng nổ số hàng khi Merge (Row Explosion)** | Thấp | Cực cao | Kiểm tra `df['timestamp'].is_unique` trên cả 2 bảng trước khi thực hiện lệnh `merge` | Sử dụng phép nối `how='left'` có kiểm tra số dòng `len(df)` trước và sau merge |
| **5. Vi phạm giả định LINE nghiêm trọng trong Hồi quy** | Cao | Trung bình | Biến đổi logarit biến mục tiêu $\log(1 + \text{PM}_{2.5})$; bổ sung biến trễ để triệt tiêu tự tương quan chuỗi thời gian | Sử dụng hồi quy điều hòa Ridge / Lasso hoặc hồi quy bền vững Huber Regressor |
| **6. Rò rỉ dữ liệu chuỗi thời gian (Temporal Leakage)** | Trung bình | Cực cao | Tuyệt đối không dùng `train_test_split` ngẫu nhiên; luôn chia tập Train/Test theo mốc thời gian cố định | Đóng gói toàn bộ biến đổi vào `Pipeline` và kiểm toán 4 dạng leakage trước tuần 11 |
| **7. Câu hỏi nghiên cứu quá dàn trải, ôm đồm ML phức tạp** | Trung bình | Cao | Bám sát Main RQ và 4 Sub-questions; kiên quyết loại bỏ Deep Learning/LSTM và Spark ra khỏi đồ án | Tập trung tối đa vào độ sâu của EDA và tính chuẩn xác của các giả định thống kê |

---

## 14. LỘ TRÌNH THỰC HIỆN CHI TIẾT TỪNG TUẦN (WEEK 1 ĐẾN WEEK 15)

### Week 01 – Khởi động Dự án & Thiết lập Môi trường CRISP-DM
* **Phân loại tuần:** Học / Chuẩn bị & Kickoff.
* **Mục tiêu tuần:** Thiết lập môi trường lập trình chuẩn mực, khởi tạo GitHub repository theo cấu trúc khuyến nghị của môn học, hiểu rõ bài toán nghiệp vụ theo vòng đời CRISP-DM.
* **Kiến thức INFO3020 áp dụng:** Slide W1 – Ba trụ cột Data Science, Vòng đời 6 bước CRISP-DM, 4 vai trò nhóm dữ liệu, Quy tắc dữ liệu thô bất biến (`data/raw/`), Quy ước nộp bài qua GitHub.
* **Tasks chi tiết:**
  1. Họp nhóm xác định phân công vai trò (Data Analyst chính, Data Scientist chính).
  2. Tạo repository trên GitHub với tên `air-pollution-analysis`.
  3. Khởi tạo cây thư mục chuẩn: `data/raw/`, `data/processed/`, `notebooks/`, `src/`, `figures/`, `reports/`, `docs/`.
  4. Tạo file `.gitignore` (chặn tracking dữ liệu thô dung lượng lớn và file tạm `.ipynb_checkpoints`).
  5. Thiết lập môi trường ảo Python (`venv`), tạo file `requirements.txt`.
  6. Viết bản thảo đầu tiên của `README.md` mô tả mục tiêu đề tài và cam kết liêm chính học thuật.
* **Deliverables:** Repo GitHub online có cấu trúc thư mục hoàn chỉnh, file `requirements.txt`, notebook `00_environment_test.ipynb`.
* **Definition of Done:** Bất kỳ thành viên nào clone repo về một máy tính mới, chạy `pip install -r requirements.txt` đều kích hoạt được kernel Jupyter không gặp lỗi.
* **Dependencies:** Không.

---

### Week 02 – Thu thập Dữ liệu Đa nguồn (Multi-source Data Collection)
* **Phân loại tuần:** Thu thập Dữ liệu.
* **Mục tiêu tuần:** Thu thập thành công dữ liệu ô nhiễm không khí ($\text{PM}_{2.5}, \text{PM}_{10}$) từ OpenAQ REST API và dữ liệu khí tượng bề mặt từ Open-Meteo API trong 2 năm (2023–2024); lưu trữ bất biến và xây dựng Data Dictionary.
* **Kiến thức INFO3020 áp dụng:** Slide W2 – 4 con đường lấy dữ liệu, Kỹ thuật gọi REST API (Headers, Pagination, Rate limits), Bẫy mã hóa font tiếng Việt, Ưu thế của định dạng Parquet, 6 câu hỏi I/O bắt buộc của Pandas.
* **Tasks chi tiết:**
  1. Viết script `src/data_collection.py` gọi API OpenAQ v3 lấy dữ liệu trạm quan trắc Hà Nội (US Embassy), xử lý phân trang bằng vòng lặp `while` và chèn `time.sleep(1.0)`.
  2. Lưu toàn bộ dữ liệu phản hồi JSON nguyên gốc vào thư mục `data/raw/openaq_raw_2023_2024.json`.
  3. Viết script gọi Open-Meteo Historical API theo đúng tọa độ trạm OpenAQ để tải dữ liệu khí tượng; lưu vào `data/raw/weather_raw_2023_2024.json`.
  4. Chạy 6 câu hỏi I/O kiểm tra nhanh trên Pandas: `shape`, `head/tail`, `info()`, `describe()`, `isna().sum()`, `duplicated().sum()`.
  5. Biên soạn tài liệu `docs/data_dictionary.md` mô tả chi tiết: tên biến, kiểu dữ liệu, đơn vị đo, tần suất và định nghĩa nghiệp vụ.
* **Deliverables:** Script cào dữ liệu, 2 file raw data trong `data/raw/`, file `docs/data_dictionary.md`.
* **Definition of Done:** Dữ liệu thô được ghi nhận an toàn trong `data/raw/` ở chế độ chỉ đọc; file từ điển dữ liệu giải thích đầy đủ $100\%$ các cột thu thập.
* **Dependencies:** Môi trường hoàn thiện từ Week 1.

---

### Week 03 – Kiểm toán Chất lượng Dữ liệu (Data Quality Audit)
* **Phân loại tuần:** Kiểm toán Chất lượng Dữ liệu.
* **Mục tiêu tuần:** Đo lường định lượng chất lượng bộ dữ liệu dựa trên 6 chiều kích thước quốc tế; nhận diện toàn bộ các giá trị missing ngụy trang và phân loại chính xác cơ chế khuyết thiếu (MCAR/MAR/MNAR).
* **Kiến thức INFO3020 áp dụng:** Slide W3 – 6 Chiều chất lượng, 3 cấp độ lỗi dữ liệu (Value, Column, Table), Missing ngụy trang ("-999", "None"), Cơ chế Rubin (MCAR, MAR, MNAR), Quy luật chi phí chất lượng 1–10–100.
* **Tasks chi tiết:**
  1. Xây dựng hàm kiểm toán tự động `audit_dataframe(df)` xuất ra bảng thống kê: `dtype`, `missing_count`, `missing_pct`, `nunique`, `min`, `max`.
  2. Truy tìm các chuỗi missing ngụy trang trong dữ liệu API: `"-999"`, `"N/A"`, `"null"`, `"0.00"`.
  3. Chấm điểm bộ dữ liệu theo thang điểm 1–5 trên từng chiều trong 6 chiều chất lượng kèm minh chứng số liệu cụ thể.
  4. Phân tích ma trận mẫu khuyết thiếu: Xác định cơ chế MCAR, MAR, MNAR.
  5. Viết báo cáo kiểm toán chất lượng dữ liệu 2 trang theo bài tập EX3.1 của khóa học.
* **Deliverables:** Notebook `02_quality_audit.ipynb`, Báo cáo kiểm toán `docs/data_quality_audit.md`.
* **Definition of Done:** Báo cáo kiểm toán có đầy đủ điểm số cho 6 chiều chất lượng; từng cột có missing đều được gán nhãn cơ chế MCAR/MAR/MNAR có biện luận.
* **Dependencies:** Dữ liệu thô thu thập từ Week 2.

---

### Week 04 – Thực hành Làm sạch & Lập Cleaning Log
* **Phân loại tuần:** Làm sạch Dữ liệu thực chiến.
* **Mục tiêu tuần:** Thực hiện làm sạch triệt để các lỗi ở cấp độ giá trị, bản ghi và quan hệ; xử lý ngoại lai lỗi phần cứng và ghi chép nhật ký làm sạch (*Cleaning Log*).
* **Kiến thức INFO3020 áp dụng:** Slide W3 & W4 – Bẫy xóa dòng (`dropna`), Bẫy điền trung bình (`mean imputation`), Xử lý chuỗi thời gian bằng nội suy có kiểm soát, Cột chỉ báo khuyết thiếu (*Missing indicator*), Quy tắc không xóa outlier thực tế.
* **Tasks chi tiết:**
  1. Loại bỏ các bản ghi trùng lặp thời gian: `drop_duplicates(subset=['timestamp'])`.
  2. Chuyển đổi múi giờ đồng nhất về UTC+7 (`Asia/Ho_Chi_Minh`) và sắp xếp chuỗi thời gian tăng dần.
  3. Reindex chuỗi thời gian theo lưới 1 giờ liên tục để phát hiện các lỗ hổng thời gian (*Gaps*).
  4. Áp dụng điều kiện kiểm tra quan hệ vật lý: Chuyển các giá trị vi phạm $\text{PM}_{2.5} > \text{PM}_{10}$ thành `NaN`.
  5. Xử lý lỗi kẹt cảm biến (giá trị không đổi suốt $> 6$ giờ liên tiếp) và lỗi sương mù tán xạ ánh sáng khi độ ẩm $\text{RH} > 90\%$.
  6. Áp dụng nội suy tuyến tính (`interpolate`) cho các khoảng khuyết $\le 2$ giờ; tạo cột missing indicator `pm25_was_missing` cho các khoảng khuyết lớn hơn.
  7. Ghi chép từng thao tác xử lý vào file `docs/cleaning_log.md`.
* **Deliverables:** Notebook `03_data_cleaning.ipynb`, tài liệu `docs/cleaning_log.md`, bộ dữ liệu trung gian trong `data/interim/`.
* **Definition of Done:** Không còn bất kỳ giá trị âm hay mâu thuẫn vật lý nào; file `cleaning_log.md` ghi nhận đầy đủ mọi phép biến đổi, giải thích rõ lý do.
* **Dependencies:** Báo cáo kiểm toán từ Week 3.

---

### Week 05 – Biến đổi, Tích hợp & Đóng gói Pipeline
* **Phân loại tuần:** Biến đổi & Tích hợp Dữ liệu.
* **Mục tiêu tuần:** Ghép nối hoàn hảo dữ liệu chất lượng không khí và khí tượng theo mốc thời gian; chuẩn hóa thang đo và đóng gói toàn bộ quy trình tiền xử lý thành Scikit-Learn Pipeline không rò rỉ dữ liệu; lưu dữ liệu sạch ra định dạng Parquet.
* **Kiến thức INFO3020 áp dụng:** Slide W5 – Chuẩn hóa thang đo (Min-Max vs StandardScaler vs RobustScaler), Biến đổi logarit (`np.log1p`), Lỗi bùng nổ số hàng khi Merge (*Row Explosion Bug*), Đóng gói `ColumnTransformer` & `Pipeline` chuẩn mực.
* **Tasks chi tiết:**
  1. Kiểm tra tính duy nhất của khóa: Đảm bảo `df_air['timestamp'].is_unique` và `df_weather['timestamp'].is_unique`.
  2. Thực hiện phép nối `pd.merge(df_air, df_weather, on='timestamp', how='inner')`. Ghi nhận số dòng trước và sau khi merge để bảo đảm không xảy ra Row Explosion.
  3. Áp dụng biến đổi logarit $\log(1 + x)$ trên các cột nồng độ bụi để giảm độ lệch phải.
  4. Xây dựng Scikit-Learn `Pipeline` kết hợp `ColumnTransformer`: Xử lý riêng biệt cột số (RobustScaler / SimpleImputer median) và cột phân loại (OneHotEncoder).
  5. Xuất bộ dữ liệu sạch hoàn chỉnh ra định dạng nén Parquet: `data/processed/air_pollution_final.parquet`.
* **Deliverables:** File dữ liệu sạch `data/processed/air_pollution_final.parquet`, script đóng gói `src/cleaning_pipeline.py`.
* **Definition of Done:** Đọc file Parquet thành công với kiểu dữ liệu nguyên vẹn; Pipeline chạy thông suốt từ file raw đến output processed chỉ bằng 1 dòng lệnh mà không làm rò rỉ dữ liệu.
* **Dependencies:** Dữ liệu làm sạch từ Week 4.

---

### Week 06 – Xác suất & Thống kê Mô tả (Descriptive Statistics)
* **Phân loại tuần:** Khám phá Dữ liệu (EDA) – Thống kê.
* **Mục tiêu tuần:** Xác lập hồ sơ thống kê toán học toàn diện cho bộ dữ liệu dựa trên 4 họ đại lượng; chứng minh bằng số liệu tại sao Median và IQR là lựa chọn đúng đắn cho chất lượng không khí.
* **Kiến thức INFO3020 áp dụng:** Slide W6 – Định lý giới hạn trung tâm (CLT), 4 họ thống kê (Location, Spread, Shape, Quantiles), Nguyên tắc "Hình dạng quyết định chỉ số", Tương quan Pearson vs Spearman, Bài học Anscombe's Quartet & Datasaurus Dozen.
* **Tasks chi tiết:**
  1. Tính toán đầy đủ 4 họ chỉ số cho $\text{PM}_{2.5}$: Mean, Median, Mode, Phương sai, Độ lệch chuẩn, IQR, Skewness, Kurtosis, Percentiles ($P_{10}, P_{50}, P_{90}, P_{95}, P_{99}$).
  2. So sánh Mean ($54.2\,\mu\text{g/m}^3$) và Median ($38.5\,\mu\text{g/m}^3$), biện luận mối liên hệ $\text{Mean} > \text{Median}$ do Skewness $> 1.2$ để khẳng định dữ liệu lệch phải nặng.
  3. Lập ma trận tương quan kép: Pearson correlation và Spearman correlation giữa $\text{PM}_{2.5}$ và các biến thời tiết.
  4. Vẽ đồ thị phân tán trước khi kết luận về hệ số tương quan giữa nhiệt độ và bụi mịn (kiểm tra bài học Anscombe).
* **Deliverables:** Notebook `04_descriptive_stats.ipynb`, bảng tổng hợp chỉ số thống kê trong `reports/statistical_profile.csv`.
* **Definition of Done:** Bảng thống kê có đủ 4 họ đại lượng; có đoạn văn phân tích chuyên sâu chứng minh tại sao không dùng Mean/Std để báo cáo nồng độ bụi đô thị.
* **Dependencies:** Dữ liệu Parquet hoàn chỉnh từ Week 5.

---

### Week 07 – Thiết kế Trực quan hóa Dữ liệu & Kể chuyện SCQA
* **Phân loại tuần:** Trực quan hóa Dữ liệu (Data Visualization).
* **Mục tiêu tuần:** Thiết kế bộ 5–7 biểu đồ cốt lõi phục vụ Báo cáo Giữa kỳ theo chuẩn mực Tufte và Cleveland; chuyển dịch từ biểu đồ khám phá sang biểu đồ giải thích (*Explanatory plots*); viết tiêu đề biểu đồ dạng kết luận.
* **Kiến thức INFO3020 áp dụng:** Slide W7 – Thứ bậc kênh thị giác Cleveland & McGill, Tỷ lệ Data-Ink của Edward Tufte, 5 cách biểu đồ đánh lừa thị giác, Bảng màu thân thiện người mù màu, Cấu trúc kể chuyện SCQA.
* **Tasks chi tiết:**
  1. Lập trình bằng Matplotlib Object-Oriented API (`fig, ax = plt.subplots()`): Loại bỏ đường viền thừa (*spines* top và right), định dạng nhãn trục rõ ràng đơn vị đo.
  2. Vẽ biểu đồ FIG-01: Line chart chuỗi thời gian kèm đường trung bình trượt 7 ngày và 30 ngày.
  3. Vẽ biểu đồ FIG-02: Histogram kết hợp đường cong mật độ KDE thể hiện độ lệch chuẩn.
  4. Vẽ biểu đồ FIG-03: Boxplot nồng độ bụi theo 12 tháng, thể hiện rõ chu kỳ mùa vụ.
  5. Vẽ biểu đồ FIG-04: 2D Heatmap (Hour of Day $\times$ Day of Week) thể hiện đỉnh ô nhiễm giao thông.
  6. Tối ưu hóa tiêu đề biểu đồ: Thay thế toàn bộ tiêu đề mô tả trục bằng **tiêu đề phát biểu kết luận**.
  7. Phác thảo khung sườn bài báo cáo theo cấu trúc **SCQA** (Situation, Complication, Question, Answer).
* **Deliverables:** Các file biểu đồ chất lượng cao trong thư mục `figures/` (PNG, 300 DPI), bản nháp dàn ý báo cáo giữa kỳ.
* **Definition of Done:** $100\%$ biểu đồ tuân thủ quy tắc Bar chart bắt đầu từ 0, không có pie chart, tiêu đề nêu bật insight chính, màu sắc phân biệt rõ ràng.
* **Dependencies:** Kết quả thống kê mô tả từ Week 6.

---

### Week 08 – BÁO CÁO & ĐÁNH GIÁ GIỮA KỲ (MIDTERM PROJECT MILESTONE)
* **Phân loại tuần:** Milestone Báo cáo & Thuyết trình Giữa kỳ.
* **Mục tiêu tuần:** Hoàn thiện và nộp Báo cáo Khám phá Dữ liệu (EDA Report) dung lượng 8–10 trang; thực hiện thuyết trình 7 phút và trả lời phản biện 3 phút (*Viva*) trước giảng viên theo đúng Rubric môn học.
* **Kiến thức INFO3020 áp dụng:** Toàn bộ kiến thức Chương 1, Chương 2, Chương 3; Rubric đánh giá Midterm trên slide W7 (Data cleaning 25%, Depth of EDA 25%, Chart quality 20%, Interpretation 20%, Presentation 10%).
* **Tasks chi tiết:**
  1. Soạn thảo tài liệu `reports/midterm_report.pdf` (8–10 trang) gồm các phần: Đặt vấn đề nghiệp vụ, Nguồn dữ liệu & Bản quyền, Hồ sơ kiểm toán chất lượng 6 chiều, Quy trình làm sạch dữ liệu có đối chứng, Phân tích thống kê 4 họ chỉ số, Bộ biểu đồ kể chuyện SCQA và Hàm ý chính sách ban đầu.
  2. Thiết kế slide thuyết trình (khoảng 8–10 slide) tập trung vào insight phát hiện từ dữ liệu.
  3. Kiểm tra repository: Bấm **Restart Kernel & Run All** trên notebook nộp bài để đảm bảo chạy mượt mà không lỗi.
  4. Tập dượt thuyết trình căn chuẩn thời gian 7 phút và chuẩn bị câu trả lời cho các câu hỏi viva.
  5. Nộp link GitHub repo và file PDF báo cáo trước 23:59 ngày quy định.
* **Deliverables:** File `reports/midterm_report.pdf`, slide thuyết trình, commit Git đánh dấu tag `midterm-submission`.
* **Definition of Done:** Báo cáo nộp đúng hạn, notebook chạy không lỗi, bảo vệ thành công bài thuyết trình và trả lời thỏa đáng các câu hỏi viva của giảng viên.
* **Dependencies:** Kết quả làm sạch và trực quan hóa từ Week 4, 5, 6, 7.

---

### Week 09 – Suy luận Thống kê & Kiểm định Giả thuyết (Statistical Inference)
* **Phân loại tuần:** Phân tích Thống kê Suy luận.
* **Mục tiêu tuần:** Kiểm định tính có ý nghĩa thống kê của các quy luật chu kỳ thời gian đã phát hiện trong EDA; thực hiện kiểm định giả thuyết phi tham số và báo cáo đầy đủ bộ ba: $p$-value, Effect Size và 95% Confidence Interval.
* **Kiến thức INFO3020 áp dụng:** Slide W9 – Bước nhảy nhận thức từ mẫu sang tổng thể, 4 sai lầm kinh điển khi đọc $p$-value, Sai lầm loại I ($\alpha$) vs Loại II ($\beta$), Kích thước hiệu ứng (*Effect size*), Cây quyết định chọn kiểm định thống kê.
* **Tasks chi tiết:**
  1. Thiết lập bài kiểm định 1: So sánh nồng độ $\text{PM}_{2.5}$ giữa Mùa Đông và Mùa Hè ($H_0: \tilde{\mu}_{\text{Đông}} = \tilde{\mu}_{\text{Hè}}$).
  2. Kiểm tra tính chuẩn của phân phối bằng Shapiro-Wilk test. Xác nhận dữ liệu không chuẩn.
  3. Thực hiện kiểm định phi tham số Mann-Whitney U (`scipy.stats.mannwhitneyu`).
  4. Tính toán kích thước hiệu ứng Rank-Biserial Correlation ($r_{rb}$) và xây dựng khoảng tin cậy 95% cho chênh lệch trung vị bằng kỹ thuật Bootstrap (1.000 mẫu lặp).
  5. Thiết lập bài kiểm định 2: So sánh Ngày làm việc vs Ngày cuối tuần. Phân tích sự khác biệt giữa ý nghĩa thống kê và ý nghĩa thực tiễn.
  6. Viết kết luận thống kê chuẩn mực theo bài tập EX9.1 (tuyệt đối không báo cáo $p$-value đơn độc).
* **Deliverables:** Notebook `05_statistical_inference.ipynb`, Bảng tổng hợp kết quả kiểm định giả thuyết trong `reports/inference_results.md`.
* **Definition of Done:** 100% các kết luận kiểm định đều có đầy đủ: Thống kê kiểm định $U$, $p$-value, Effect size và Khoảng tin cậy 95%.
* **Dependencies:** Dữ liệu sạch và EDA từ các tuần trước.

---

### Week 10 – Phân tích Hồi quy & Chẩn đoán Giả định (Regression Analysis)
* **Phân loại tuần:** Mô hình hóa – Hồi quy Tuyến tính.
* **Mục tiêu tuần:** Xây dựng mô hình hồi quy tuyến tính đa biến OLS đánh giá tác động của các yếu tố khí tượng lên $\text{PM}_{2.5}$; thực hiện đầy đủ quy trình 6 bước chẩn đoán giả định LINE, kiểm tra đa cộng tuyến VIF và so sánh với Ridge/Lasso.
* **Kiến thức INFO3020 áp dụng:** Slide W10 – Hồi quy OLS, Ba nghĩa vụ khi diễn giải hệ số $\beta$, 4 Giả định LINE, Đa cộng tuyến & VIF, Điểm ảnh hưởng Cook's distance, Điều hòa Ridge ($L_2$) & Lasso ($L_1$).
* **Tasks chi tiết:**
  1. Phân chia dữ liệu theo mốc thời gian: Train (2023) / Test (2024).
  2. Biến đổi biến mục tiêu sang logarit: $Y = \log(1 + \text{PM}_{2.5})$.
  3. Huấn luyện mô hình hồi quy OLS trên tập Train bằng `statsmodels.api.OLS` và Scikit-Learn.
  4. Chẩn đoán giả định LINE trên phần dư (*Residuals*):
     - Linearity & Equal Variance: Vẽ biểu đồ Residuals vs Fitted values.
     - Independence: Tính thống kê Durbin-Watson.
     - Normality: Vẽ Q-Q plot và chạy Shapiro-Wilk trên phần dư.
  5. Tính toán chỉ số VIF cho các biến thời tiết, loại bỏ hiện tượng đa cộng tuyến.
  6. Đánh giá mô hình trên tập TEST độc lập: Báo cáo MAE, RMSE, $R^2$ cạnh Baseline Dummy Regressor.
  7. Viết diễn giải hệ số $\beta$ đúng cấu trúc 3 nghĩa vụ bắt buộc cho từng biến thời tiết.
  8. Thử nghiệm mở rộng với Ridge và Lasso để so sánh khả năng kiểm soát quá khớp.
* **Deliverables:** Notebook `06_regression_analysis.ipynb`, 4 biểu đồ chẩn đoán LINE trong `figures/`, bảng tham số hồi quy.
* **Definition of Done:** Mô hình được đánh giá trên tập Test độc lập; biểu đồ phần dư được phân tích cẩn thận; hệ số $\beta$ được diễn giải chuẩn xác, không mắc lỗi ngụy biện nhân quả.
* **Dependencies:** Pipeline tiền xử lý từ Week 5 và kết quả suy luận từ Week 9.

---

### Week 11 – Phân loại Cảnh báo Ô nhiễm & Kỹ nghệ Đặc trưng (Classification)
* **Phân loại tuần:** Mô hình hóa – Phân loại & Feature Engineering.
* **Mục tiêu tuần:** Xây dựng mô hình phân loại nhị phân cảnh báo sớm ngày ô nhiễm nghiêm trọng ($\text{PM}_{2.5} \ge 50\,\mu\text{g/m}^3$); tạo ít nhất 5 đặc trưng mới; xử lý mất cân bằng lớp; tối ưu ngưỡng quyết định theo chi phí y tế cộng đồng; kiểm toán chống rò rỉ dữ liệu.
* **Kiến thức INFO3020 áp dụng:** Slide W11 – Mô hình Logistic Regression & Random Forest, Bẫy Accuracy trên dữ liệu mất cân bằng, Ma trận nhầm lẫn (Confusion Matrix), Đánh đổi Precision vs Recall, Đường cong PR-AUC, Threshold Tuning, Kỹ nghệ đặc trưng thời gian, 4 dạng rò rỉ dữ liệu.
* **Tasks chi tiết:**
  1. Định nghĩa nhãn nhị phân: `y = (df['pm25'] >= 50).astype(int)`.
  2. Tạo 5 đặc trưng miền ứng dụng: Lags thời gian (`pm25_lag24`), Rolling statistics (mean 24h, std 24h), Cờ lặng gió (`wind_stagnant`), Chỉ số tương tác nhiệt ẩm.
  3. Phân chia Train/Test theo thời gian để phòng ngừa Temporal Leakage.
  4. Huấn luyện Baseline (DummyClassifier) và 2 mô hình: Logistic Regression (`class_weight='balanced'`) và Random Forest Classifier.
  5. Vẽ đường cong Precision-Recall (PR Curve), tính chỉ số PR-AUC.
  6. Tinh chỉnh ngưỡng xác suất: Hạ ngưỡng xuống $0.30$ để ưu tiên tối đa hóa **Recall**.
  7. Lập bảng kiểm toán phòng chống 4 dạng rò rỉ dữ liệu theo bài tập EX11.4.
* **Deliverables:** Notebook `07_classification_modeling.ipynb`, Bảng so sánh hiệu năng các mô hình, Bản kiểm toán chống rò rỉ dữ liệu.
* **Definition of Done:** Báo cáo so sánh mô hình có đầy đủ Precision, Recall, F1, PR-AUC đặt cạnh Baseline; ngưỡng quyết định được biện luận từ bài toán sức khỏe thực tế.
* **Dependencies:** Dữ liệu hoàn chỉnh từ Week 5 và các đặc trưng thời gian.

---

### Week 12 – Đạo đức Dữ liệu, Định kiến & Nộp Project Charter
* **Phân loại tuần:** Đạo đức Dữ liệu & Đánh giá Giới hạn (Bài giảng cuối cùng).
* **Mục tiêu tuần:** Thực hiện kiểm toán toàn diện về quy mô dữ liệu (giải trình tại sao không cần Spark), nhận diện 4 loại định kiến (*Bias*); viết **Datasheet for Dataset** và **Model Card** 1 trang; hoàn thiện **Project Charter** nộp trước thềm giai đoạn nước rút.
* **Kiến thức INFO3020 áp dụng:** Slide W12 – Ngưỡng Big Data thực tế, Nghị định 13/2023/NĐ-CP, Sổ tay định kiến (*Sensor bias, Spatial bias, Survivorship bias*), Tính giải trình (Explainability), Bản chuẩn Datasheet for Datasets & Model Cards.
* **Tasks chi tiết:**
  1. Đo lường kích thước dữ liệu trên đĩa (MB), RAM chiếm dụng và thời gian chạy 1 lượt; viết 1 đoạn văn khẳng định tại sao dữ liệu không cần dùng tới Apache Spark.
  2. Đo lường tỷ lệ nén và tốc độ đọc/ghi khi chuyển sang định dạng Parquet.
  3. Lập danh mục rà soát đạo đức theo Checklist slide W12.
  4. Soạn thảo tài liệu `docs/datasheet.md` (Datasheet for Dataset).
  5. Soạn thảo tài liệu `docs/model_card.md` (Model Card 1 trang).
  6. Bổ sung mục **Tuyên bố mức độ sử dụng AI** vào `README.md`.
  7. Nộp bản **Project Charter** hoàn chỉnh theo biểu mẫu của giảng viên trước 23:59 ngày quy định.
* **Deliverables:** File `docs/datasheet.md`, `docs/model_card.md`, Project Charter nộp giảng viên, mục AI declaration trong `README.md`.
* **Definition of Done:** Hoàn thành trọn vẹn $100\%$ các mục trong Checklist đạo đức; nộp Project Charter đúng hạn.
* **Dependencies:** Kết quả phân tích và mô hình từ Week 10 và 11.

---

### Week 13 – Cố vấn Đồ án & Tinh chỉnh Toàn diện (Project Mentoring)
* **Phân loại tuần:** Project Analysis & Cố vấn.
* **Mục tiêu tuần:** Làm việc trực tiếp với giảng viên hướng dẫn (ThS. Phạm Ngọc Đông) trong buổi cố vấn; tiếp thu góp ý phản biện để tinh chỉnh pipeline, khắc phục các điểm yếu trong mô hình và kiểm định.
* **Kiến thức INFO3020 áp dụng:** Vòng lặp phi tuyến của CRISP-DM, Tinh chỉnh mô hình dựa trên phản biện khoa học, Chuẩn hóa mã nguồn tái lập.
* **Tasks chi tiết:**
  1. Trình bày tổng thể tiến độ đồ án và các phát hiện chính với giảng viên trong buổi học Tuần 13.
  2. Ghi nhận nhận xét của giảng viên về kiểm định thống kê, giả định LINE, sự đánh đổi Precision-Recall.
  3. Tái cấu trúc mã nguồn: Đưa các hàm dùng chung vào các module `.py` trong thư mục `src/`.
  4. Bổ sung các phân tích độ nhạy (*Sensitivity Analysis*).
  5. Dọn dẹp notebooks: Xóa bỏ cell rác, thêm markdown chú thích chi tiết cho từng khối code.
* **Deliverables:** Mã nguồn đã được tái cấu trúc sạch sẽ, biên bản họp tiếp thu ý kiến cố vấn của giảng viên.
* **Definition of Done:** Toàn bộ code trong `src/` có docstrings rõ ràng; các điểm góp ý của giảng viên được phản hồi và chỉnh sửa đầy đủ trong code.
* **Dependencies:** Đồ án tổng thể từ Week 1 đến Week 12.

---

### Week 14 – Kể chuyện Dữ liệu & Soạn thảo Báo cáo Cuối kỳ (Data Storytelling)
* **Phân loại tuần:** Report & Presentation Preparation.
* **Mục tiêu tuần:** Hoàn thiện Báo cáo Đồ án Tốt nghiệp Môn học dạng văn bản (*Final Project Report*) theo cấu trúc kể chuyện SCQA mạch lạc; thiết kế slide bảo vệ đồ án chuyên nghiệp, ấn tượng.
* **Kiến thức INFO3020 áp dụng:** Slide W7 & W14 – Nghệ thuật kể chuyện bằng dữ liệu (*Data Storytelling*), Cấu trúc SCQA (Situation, Complication, Question, Answer), Nguyên tắc trình bày slide khoa học, Kỹ năng giải trình viva.
* **Tasks chi tiết:**
  1. Soạn thảo Báo cáo Đồ án Cuối kỳ `reports/final_report.pdf` theo bố cục SCQA chặt chẽ:
     - **S (Situation):** Bối cảnh phát triển đô thị và thực trạng chất lượng không khí tại Hà Nội/TP.HCM.
     - **C (Complication):** Ô nhiễm diễn biến thất thường, các đợt bụi mịn vượt ngưỡng nghiêm trọng ảnh hưởng sức khỏe nhưng khó dự báo nếu chỉ nhìn trực quan.
     - **Q (Question):** Quy luật chu kỳ thời gian chi phối ô nhiễm? Các yếu tố khí tượng tác động định lượng ra sao? Làm thế nào để cảnh báo sớm hiệu quả?
     - **A (Answer):** Trình bày hệ thống bằng chứng định lượng từ Kiểm định giả thuyết, Hồi quy OLS có chẩn đoán LINE, Phân loại cảnh báo sớm, kèm giải pháp khuyến nghị chính sách và Model Card.
  2. Thiết kế slide thuyết trình bảo vệ (12–15 slides).
  3. Luyện tập phân chia thời lượng trình bày giữa các thành viên nhóm (tổng thời gian 10–12 phút).
  4. Chuẩn bị tài liệu hỏi đáp (*Q&A Prep Document*): Dự liệu 15 câu hỏi hội đồng có thể chất vấn.
* **Deliverables:** File báo cáo cuối kỳ `reports/final_report.pdf`, slide thuyết trình bảo vệ đồ án.
* **Definition of Done:** Báo cáo hoàn chỉnh, in ấn đẹp, không lỗi chính tả; slide thuyết trình truyền tải trọn vẹn câu chuyện dữ liệu trong đúng 10–12 phút.
* **Dependencies:** Kết quả phân tích và mã nguồn hoàn thiện từ Week 13.

---

### Week 15 – BÁO CÁO ĐỒ ÁN TỐT NGHIỆP MÔN HỌC (FINAL DEFENSE)
* **Phân loại tuần:** Milestone Bảo vệ Đồ án Cuối kỳ (Final Viva).
* **Mục tiêu tuần:** Thuyết trình bảo vệ đồ án trước Hội đồng chấm thi môn học; giải trình tự tin, mạch lạc từng dòng code và mọi luận điểm khoa học trong buổi vấn đáp (*Oral Defense / Viva*); đóng gói bàn giao repository.
* **Kiến thức INFO3020 áp dụng:** Tích hợp toàn diện 15 tuần học; Quy tắc ứng xử và bảo vệ đồ án theo chuẩn đầu ra CLO4; Năng lực làm chủ phương pháp luận khoa học dữ liệu.
* **Tasks chi tiết:**
  1. Kiểm tra kỹ thuật lần cuối: Đẩy commit mới nhất lên GitHub, bảo đảm file `README.md` hiển thị đẹp mắt, link các tài liệu hoạt động chính xác.
  2. Bấm **Restart & Run All** trên tất cả các notebooks trước sự chứng kiến của cả nhóm để chắc chắn 100% không còn lỗi ngầm.
  3. Thực hiện thuyết trình trước hội đồng giảng viên (10–12 phút).
  4. Trả lời phản biện cá nhân (*Individual Viva*): Mỗi thành viên tự tin giải thích chi tiết logic toán học, lý do chọn mô hình, cơ chế xử lý dữ liệu của phần việc mình phụ trách.
  5. Tiếp thu đánh giá cuối cùng của hội đồng và lưu trữ biên bản bảo vệ.
* **Deliverables:** Link GitHub Repository chính thức, Báo cáo đồ án cuối kỳ, Model Card, Biên bản bảo vệ đồ án.
* **Definition of Done:** Hoàn thành xuất sắc bài bảo vệ đồ án trước hội đồng; toàn bộ thành viên vượt qua phần hỏi đáp phản biện cá nhân; đồ án đáp ứng toàn diện các tiêu chí khắt khe của môn INFO3020.
* **Dependencies:** Toàn bộ thành quả tích lũy từ Week 1 đến Week 14.

---

## 15. LỜI KHUYÊN THỰC CHIẾN DÀNH CHO BẠN (PRO-TIPS)

1. **Giữ gìn thư mục `data/raw/` như một "hiện trường vụ án":** Tuyệt đối không bao giờ dùng chuột mở file CSV/JSON trong Excel rồi bấm Save. Excel sẽ tự ý chuyển đổi định dạng ngày tháng và làm hỏng encoding tiếng Việt!
2. **Luôn nhớ câu thần chú của thầy Đông:** *"Không bao giờ tự hào vì $R^2 = 0.90$ khi chưa soi biểu đồ phần dư Residual Plot và kiểm tra VIF"*. Trong chuỗi thời gian, $R^2$ cao thường chỉ là do bạn bị rò rỉ dữ liệu hoặc hiện tượng tương quan giả (*Spurious correlation*).
3. **Thước đo là một quyết định nghiệp vụ:** Trong bài toán cảnh báo ô nhiễm, đừng bao giờ báo cáo mỗi chỉ số Accuracy. Hãy tự tin giải thích trước hội đồng: *"Nhóm em chấp nhận Precision thấp hơn một chút để đổi lấy Recall đạt 88%, bởi vì cái giá của việc một đứa trẻ bị hen suyễn do ra đường vào ngày không khí độc hại mà không được cảnh báo là không thể bù đắp được!"* — Đó chính là tư duy của một **Data Scientist thực thụ**.
