# LỘ TRÌNH THỰC HIỆN ĐỒ ÁN MÔN HỌC: INFO3020 – INTRODUCTION TO DATA SCIENCE

> **Đề tài:** Phân tích mức độ ô nhiễm không khí theo thời gian (*Time-Series Air Pollution Analysis*)  
> **Căn cứ tài liệu:** Đề cương môn học INFO3020, Bài giảng ThS. Phạm Ngọc Đông – Khoa CNTT & Truyền thông, Trường Đại học CMC, và hệ thống 17 GitHub Issues (#1–#17, #19) làm đặc tả kỹ thuật có thẩm quyền.  
> **Nơi lưu trữ:** `docs/roadmap.md`

---

## 1. PHÂN TÍCH YÊU CẦU ĐỒ ÁN MÔN HỌC INFO3020

### 1.1. Các khối kiến thức INFO3020 cần thể hiện trong đồ án
Đồ án là bức tranh thu nhỏ của toàn bộ chương trình học, bám sát **5 Chương – 15 Tuần** và hệ thống 17 GitHub Issues chuẩn mực:
1. **Chương 1 (Nền tảng, Khảo sát nguồn & Thu thập):** Vòng đời CRISP-DM, cấu trúc repo chuẩn, quy tắc dữ liệu thô ba tầng (`data/raw/`, Mục 3.2) [Issue #1]; xác lập câu hỏi nghiên cứu và chuẩn hóa lược đồ Canonical Schema trung lập nguồn [Issue #2]; khảo sát hồ sơ dữ liệu đa nguồn (Data Profiling), kiểm chứng phạm vi Hà Nội, xác định độ bao phủ thời gian thực tế và ban hành quyết định nguồn dữ liệu [Issue #19]; triển khai các adapter thu thập và chuẩn hóa dữ liệu ô nhiễm không khí [Issue #3] và dữ liệu khí tượng bề mặt [Issue #4] theo nguồn được duyệt; lưu trữ an toàn và xuất tối ưu sang định dạng Parquet (Week 1–2).
2. **Chương 2 (Chất lượng, Làm sạch tất định & Tiền xử lý chống rò rỉ):** Xây dựng bộ kiểm toán 6 chiều chất lượng dữ liệu, bóc trần missing ngụy trang, khảo sát các giả thuyết cơ chế khuyết thiếu (MCAR/MAR/MNAR) kèm tính bất định nếu chưa đủ bằng chứng [Issue #5]; thực hiện làm sạch tất định (Deterministic Cleaning) trước khi chia tập: ràng buộc logic vật lý ($\text{PM}_{2.5} \le \text{PM}_{10}$), xử lý kẹt cảm biến, gắn nhãn điều kiện độ ẩm cao, reindex chuỗi thời gian liên tục theo từng trạm quan trắc và lập Cleaning Log [Issue #6]; tích hợp hai nguồn dữ liệu có kiểm soát số dòng ngăn chặn lỗi bùng nổ (Row Explosion), đóng băng tập dữ liệu sạch, phân chia Train/Test theo chuỗi thời gian tuyến tính, đóng gói Scikit-Learn Pipeline (`ColumnTransformer`) huấn luyện tiền xử lý strictly trên Train [Issue #7] (Week 3–5).
3. **Chương 3 (EDA & Trực quan hóa giải thích):** Phân tích 4 họ thống kê mô tả (Location, Spread, Shape, Quantiles), nguyên tắc "Hình dạng phân phối quyết định chỉ số" (*Shape picks the statistic*), phân tích quy luật thời gian đa tầng (giờ, ngày trong tuần, tháng, mùa) dựa trên số liệu thực tế [Issue #8]; thiết kế và xuất bản bộ 7 biểu đồ ấn phẩm giải thích (FIG-01 đến FIG-07) theo nguyên tắc Edward Tufte (Data-Ink Ratio) và William Cleveland, tuân thủ nghiêm ngặt ngữ nghĩa quy chuẩn về chu kỳ lấy mẫu trung bình, tiêu đề dạng kết luận rút ra từ dữ liệu [Issue #9]; biên soạn Báo cáo Giữa kỳ theo cấu trúc kể chuyện **SCQA** và thuyết trình giữa kỳ [Issue #10] (Week 6–8).
4. **Chương 4 (Suy luận & Mô hình hóa):** 
   - *Suy luận thống kê:* Thực hiện các phép kiểm định giả thuyết phi tham số so sánh các khoảng thời gian và đối chiếu quy chuẩn kỹ thuật quốc gia, bắt buộc báo cáo bộ bốn: Thống kê kiểm định + $p$-value + Kích thước hiệu ứng (*Effect size* $r_{rb}$) + 95% Bootstrap CI [Issue #11] (Week 9).
   - *Hồi quy OLS:* Mô hình hóa mối liên hệ giữa các yếu tố thời tiết và bụi mịn, khảo sát biến đổi mục tiêu ứng viên, quy trình chẩn đoán 4 giả định **LINE** trên phần dư, phân tích chỉ số chẩn đoán đa cộng tuyến VIF và điểm ảnh hưởng Cook's distance, tối ưu siêu tham số điều hòa Ridge/Lasso hoàn toàn trên Train, diễn giải hệ số $\beta$ phi nhân quả kèm điều kiện *ceteris paribus* [Issue #12] (Week 10).
   - *Phân loại cảnh báo sớm:* Định nghĩa nhãn nguy hại tương thích toán học với quy chuẩn, kỹ nghệ đặc trưng trễ/trượt từ quá khứ, xử lý mất cân bằng lớp thực tế, tối ưu ngưỡng quyết định theo mục tiêu vận hành ($F_\beta$ với $\beta > 1$ hoặc Recall có ràng buộc Precision tối thiểu) trên Train/Validation, đánh giá độc lập trên Test và kiểm toán 4 dạng rò rỉ dữ liệu [Issue #13] (Week 11).
5. **Chương 5 (Hạ tầng, Đạo đức & Bàn giao đồ án):** Đo đạc thực nghiệm các chỉ số tài nguyên thực tế (dung lượng đĩa, RAM chiếm dụng, thông lượng I/O, thời gian thực thi) để đánh giá khách quan nhu cầu kiến trúc xử lý (Pandas vs Spark), khảo sát 4 giả thuyết định kiến (*Sensor, Spatial, Survivorship/Weather-related missingness, Missing vs Zero*), lập **Datasheet for Dataset** và **Model Card** 1 trang [Issue #14]; tái cấu trúc module hóa mã nguồn vào `src/`, phân tích độ nhạy với các ngưỡng cảnh báo kỹ thuật (40, 45, 50, 55 $\mu\text{g/m}^3$) và cửa sổ trễ, theo dõi tiếp thu ý kiến cố vấn [Issue #15]; hoàn thiện Báo cáo Đồ án Cuối kỳ SCQA, thiết kế slide bảo vệ và tài liệu chuẩn bị vấn đáp Viva [Issue #16]; kiểm toán kỹ thuật toàn diện repository, kiểm chứng tính tái lập tự động của chuỗi notebooks và bàn giao bảo vệ [Issue #17] (Week 12–15).

---

### 1.2. Phân loại yêu cầu & Kỹ thuật
* **Bắt buộc theo chuẩn mực môn học:**
  - Thư mục `data/raw/` được giữ nguyên trạng trong suốt pipeline: mọi biến đổi thực hiện bằng code và ghi kết quả ra `data/processed/`; tệp thô có mã băm SHA-256 để kiểm chứng toàn vẹn (Mục 3.2).
  - Có **Data Dictionary** (Từ điển dữ liệu chuẩn hóa Canonical Schema) [Issue #2] và **Cleaning Log** chi tiết [Issue #6].
  - Toàn bộ chuỗi Notebook chạy thông suốt từ đầu đến cuối sau khi bấm **Restart Kernel & Run All** [Issue #10, #17].
  - Kiểm tra giả định thống kê trước khi thực hiện test hoặc hồi quy (chẩn đoán 4 giả định LINE trên Residuals trước khi tin $R^2$) [Issue #12].
  - Nộp kèm **Datasheet for Dataset**, **Model Card** (1 trang), **Project Charter** và mục **Tuyên bố sử dụng AI** trong README [Issue #14].
* **Phù hợp đặc thù với đề tài ô nhiễm không khí theo thời gian:**
  - Khảo sát biến thiên chuỗi thời gian đa tầng: Chu kỳ ngày đêm (*Diurnal pattern*), ngày trong tuần (*Weekday vs. Weekend*), chu kỳ tháng và mùa vụ dựa trên số liệu thực tế [Issue #8].
  - Kỹ thuật tính trung bình trượt (*Rolling averages*: 24h, 7 ngày) để khử nhiễu ngắn hạn và phục vụ đối chiếu quy chuẩn tương thích về chu kỳ lấy mẫu trung bình [Issue #8, #9].
  - Tích hợp dữ liệu chất lượng không khí với dữ liệu khí tượng theo đơn vị quan trắc `(station_id, timestamp)` hoặc `timestamp`, kiểm soát nghiêm ngặt số dòng để ngăn chặn lỗi bùng nổ số hàng (Row Explosion bug) [Issue #7].
  - Kiểm định phi tham số (*Mann-Whitney U / Wilcoxon signed-rank*) kèm kích thước hiệu ứng và khoảng tin cậy Bootstrap [Issue #11].
* **Kỹ thuật THỰC SỰ CẦN THIẾT:**
  - Chuẩn hóa múi giờ địa phương (`Asia/Ho_Chi_Minh` UTC+7) và reindex chuỗi thời gian liên tục 1 giờ theo từng trạm quan trắc [Issue #6].
  - Phân chia tập dữ liệu theo thứ tự thời gian tuyến tính (*Chronological Train-Test Split*), điểm cắt được xác định dựa trên bằng chứng dữ liệu thực tế sau khi đóng băng tập dữ liệu; tuyệt đối không dùng `train_test_split` ngẫu nhiên để triệt tiêu Temporal Leakage [Issue #7].
  - Huấn luyện tiền xử lý (*Imputer, Scaler*) strictly trên Train; đóng gói thành Scikit-Learn Pipeline và ColumnTransformer để đảm bảo tính tái lập và ngăn ngừa rò rỉ dữ liệu [Issue #7].
* **Đánh giá Công nghệ & Phạm vi Phù hợp:**
  - **Apache Spark / Hadoop vs Pandas:** Việc có sử dụng Apache Spark hay không phải được kết luận dựa trên kết quả đo đạc thực nghiệm các chỉ số tài nguyên thực tế (dung lượng đĩa theo MB, RAM chiếm dụng, thông lượng I/O và thời gian xử lý) trên tập dữ liệu đã thu thập và chuyển đổi [Issue #14]. Tránh đưa ra các khẳng định định kiến trước khi có số liệu đo lường.
  - ❌ **Deep Learning (LSTM / GRU / Transformer):** Không thuộc phạm vi kiến thức cốt lõi INFO3020; biến đồ án thành "hộp đen", làm mất đi tính giải trình (*Explainability*) và không kiểm chứng được các giả định thống kê nền tảng.
  - ❌ **Thử nghiệm A/B can thiệp (RCT):** Không khả thi vì con người không thể can thiệp làm thay đổi thời tiết ngẫu nhiên; bài toán mang bản chất nghiên cứu quan sát (*Observational study*).
  - ❌ **Kỹ thuật nặc danh hóa cá nhân ($k$-anonymity / Hashing):** Dữ liệu quan trắc từ trạm đo môi trường công cộng không chứa thông tin định danh cá nhân (PII), do đó không cần làm mờ danh tính.

---

### 1.3. Các Milestone chính trong tiến trình môn học
* **Milestone 1 – Project Setup, Schema & Source Decision (Week 1–2):** Khởi tạo repository [Issue #1], xác lập câu hỏi nghiên cứu và Canonical Schema [Issue #2], thẩm định hồ sơ đa nguồn và quyết định chiến lược nguồn dữ liệu [Issue #19], hiện thực hóa adapter thu thập dữ liệu ô nhiễm [Issue #3] và khí tượng [Issue #4].
* **Milestone 2 – Data Quality Audit, Cleaning & Leakage-Safe Pipeline (Week 3–5):** Kiểm toán 6 chiều chất lượng dữ liệu [Issue #5], làm sạch tất định & ghi Cleaning Log [Issue #6], tích hợp an toàn không nổ dòng, đóng băng dữ liệu, phân chia chuỗi thời gian và đóng gói Pipeline chống rò rỉ lưu Parquet [Issue #7].
* **Milestone 3 – Báo cáo Giữa kỳ Midterm (Week 6–8):** Phân tích thống kê mô tả 4 họ chỉ số & chu kỳ thời gian [Issue #8], bộ 7 biểu đồ ấn phẩm giải thích FIG-01 đến FIG-07 [Issue #9], Báo cáo Giữa kỳ SCQA 8–10 trang, slide thuyết trình 7 phút + 3 phút viva, gắn tag `midterm-submission` [Issue #10].
* **Milestone 4 – Phân tích Nâng cao & Modeling (Week 9–11):** Kiểm định giả thuyết phi tham số bộ bốn [Issue #11], mô hình hóa hồi quy OLS kèm chẩn đoán LINE và điều hòa [Issue #12], phân loại cảnh báo ô nhiễm với tối ưu ngưỡng vận hành và kiểm toán rò rỉ [Issue #13].
* **Milestone 5 – Đạo đức Dữ liệu, Refactor & Báo cáo Cuối kỳ (Week 12–14):** Đo đạc tài nguyên vs Spark, kiểm toán 4 loại định kiến, lập Datasheet for Dataset & Model Card 1 trang, Project Charter [Issue #14], module hóa `src/`, phân tích độ nhạy và theo dõi phản biện cố vấn [Issue #15], hoàn thiện Báo cáo Cuối kỳ SCQA, slide bảo vệ và bộ câu hỏi vấn đáp Viva [Issue #16].
* **Milestone 6 – Final Defense & Handoff (Week 15):** Kiểm toán kỹ thuật toàn diện repository, kiểm chứng thực thi tự động chuỗi notebooks trong môi trường sạch, chuẩn bị biên bản đánh giá, gắn tag `final-defense-submission` và bảo vệ đồ án [Issue #17].

---

## 2. RESEARCH QUESTIONS (CÂU HỎI NGHIÊN CỨU)

> Toàn bộ các câu hỏi nghiên cứu được xác lập tại **Issue #2** theo nguyên tắc khách quan và liêm chính học thuật: không đưa ra câu trả lời hay kết luận định trước trước khi phân tích dữ liệu thực tế.

### 2.1. Đề xuất 4 câu hỏi nghiên cứu ứng viên
1. **RQ1 (Xu hướng & Chu kỳ thời gian):** Nồng độ bụi mịn $\text{PM}_{2.5}$ biến thiên như thế nào theo các chu kỳ thời gian (theo giờ trong ngày, ngày trong tuần, các tháng và mùa trong năm), và có xu hướng tăng/giảm dài hạn trong chuỗi quan sát thực tế hay không?
2. **RQ2 (So sánh thống kê có đối chứng):** Có sự khác biệt có ý nghĩa thống kê về mức độ ô nhiễm giữa các ngày làm việc so với ngày cuối tuần, giữa các mùa quan sát hay không? Độ lớn hiệu ứng (*Effect size*) và khoảng tin cậy 95% Bootstrap của chênh lệch là bao nhiêu? Mức độ ô nhiễm có vượt ngưỡng quy chuẩn kỹ thuật quốc gia tương thích về thời gian lấy mẫu trung bình không?
3. **RQ3 (Quan hệ giữa Ô nhiễm & Khí tượng - Regression):** Các yếu tố khí tượng bề mặt (nhiệt độ, độ ẩm tương đối, tốc độ gió, lượng mưa, áp suất) liên hệ như thế nào với nồng độ $\text{PM}_{2.5}$ trong điều kiện giữ nguyên không đổi các yếu tố khác (*ceteris paribus*)? Mô hình hồi quy OLS giải thích được bao nhiêu phần trăm phương sai và các giả định LINE có được thỏa mãn không?
4. **RQ4 (Cảnh báo sớm - Classification):** Liệu có thể sử dụng các đặc trưng trễ của ô nhiễm kết hợp với thông số khí tượng quá khứ để phân loại chính xác các đợt có nguy cơ vượt ngưỡng cảnh báo ô nhiễm (dựa trên quy chuẩn tương thích về chu kỳ lấy mẫu) hay không? Sự đánh đổi giữa Precision và Recall được giải quyết thế nào thông qua tối ưu hóa ngưỡng quyết định theo mục tiêu vận hành?

---

### 2.2. Lựa chọn Câu hỏi Nghiên cứu Mục tiêu

* **MAIN RESEARCH QUESTION:**
  > *"Nồng độ bụi mịn $\text{PM}_{2.5}$ tại khu vực nghiên cứu biến động theo những quy luật chu kỳ thời gian nào, chịu sự liên hệ ra sao bởi các yếu tố khí tượng bề mặt, và làm thế nào để xây dựng mô hình cảnh báo sớm các đợt ô nhiễm vượt ngưỡng an toàn dựa trên dữ liệu chuỗi thời gian mà không vi phạm rò rỉ dữ liệu?"*

* **CÁC SUB-QUESTIONS HỖ TRỢ:**
  - **SQ1 (Phân phối & Đo lường):** Phân phối thực nghiệm của nồng độ $\text{PM}_{2.5}$ có hình dạng lệch (*skewness*) và đuôi dày (*kurtosis*) như thế nào? Cặp đại lượng nào (Mean/Std hay Median/IQR) phản ánh trung thực nhất mức độ phơi nhiễm điển hình của người dân dựa trên hình dạng phân phối quan sát được?
  - **SQ2 (Chu kỳ & Suy luận):** Sự khác biệt về mức độ ô nhiễm giữa ngày làm việc và ngày cuối tuần, cũng như giữa các mùa trong năm có đạt ý nghĩa thống kê ở mức $\alpha = 0.05$ hay không? Kích thước hiệu ứng và khoảng tin cậy 95% Bootstrap phản ánh độ tin cậy của phát hiện ra sao?
  - **SQ3 (Mô hình hóa liên hệ):** Trong điều kiện kiểm soát các yếu tố khác không đổi (*ceteris paribus*), các biến thời tiết liên hệ như thế nào với nồng độ bụi mịn? Biến đổi mục tiêu có hỗ trợ thỏa mãn các giả định LINE hay không, và mức độ đa cộng tuyến được kiểm soát ra sao?
  - **SQ4 (Cảnh báo & Đánh đổi):** Khi xây dựng mô hình phân loại cảnh báo ô nhiễm, bài toán mất cân bằng lớp được xử lý như thế nào và ngưỡng quyết định được tối ưu theo mục tiêu vận hành nào ($F_\beta$ hoặc Recall có ràng buộc Precision) để giảm thiểu rủi ro sức khỏe cộng đồng mà vẫn kiểm soát được tỷ lệ báo động giả?

---

## 3. THIẾT KẾ DATA PLAN (KẾ HOẠCH DỮ LIỆU)

### 3.1. Bảng đặc tả Canonical Schema
> Lược đồ dữ liệu chuẩn hóa trung lập (Canonical Schema) được thiết lập tại **Issue #2**, độc lập với định dạng raw của từng nhà cung cấp dữ liệu:

| Tên biến chuẩn hóa | Kiểu dữ liệu | Đơn vị | Tần suất đo | Vai trò & Ý nghĩa | Nguồn dữ liệu | Khóa ghép nối |
|---|---|---|---|---|---|---|
| `timestamp` | Datetime (ISO 8601) | `Asia/Ho_Chi_Minh` (UTC+7) | 1 giờ | Trục thời gian chuẩn, dùng để trích xuất đặc trưng chu kỳ và làm khóa nối | Quyết định tại #19 | Khóa chính (*Primary Key*) |
| `station_id` | String | Danh mục mã trạm | Cố định | Định danh trạm đo mặt đất tại Hà Nội, bảo toàn đơn vị quan trắc | Quyết định tại #19 | Khóa phân nhóm / Khóa ghép |
| `pm25` | Float64 | $\mu\text{g/m}^3$ | 1 giờ | **Biến mục tiêu cốt lõi**; nồng độ bụi mịn đo đạc thực tế | Nguồn ô nhiễm duyệt tại #19 | Nối theo khóa quan sát |
| `pm10` | Float64 | $\mu\text{g/m}^3$ | 1 giờ | Bụi thô (nếu khả dụng); kiểm tra logic vật lý $\text{PM}_{2.5} \le \text{PM}_{10} + \epsilon$ | Nguồn ô nhiễm duyệt tại #19 | Nối theo khóa quan sát |
| `temperature` | Float64 | $^\circ\text{C}$ | 1 giờ | Nhiệt độ bề mặt; ảnh hưởng đối lưu không khí và phát tán bụi | Nguồn khí tượng duyệt tại #19 | Nối theo khóa quan sát |
| `relative_humidity` | Float64 | $\%$ | 1 giờ | Độ ẩm tương đối; liên quan đến hút ẩm và chẩn đoán sương mù | Nguồn khí tượng duyệt tại #19 | Nối theo khóa quan sát |
| `wind_speed` | Float64 | $\text{m/s}$ | 1 giờ | Tốc độ gió; động lực phát tán và pha loãng chất ô nhiễm | Nguồn khí tượng duyệt tại #19 | Nối theo khóa quan sát |
| `wind_direction` | Float64 | Độ ($0^\circ - 360^\circ$) | 1 giờ | Hướng gió; hướng vận chuyển chất ô nhiễm theo không gian | Nguồn khí tượng duyệt tại #19 | Nối theo khóa quan sát |
| `precipitation` | Float64 | $\text{mm}$ | 1 giờ | Lượng mưa; hiệu ứng rửa trôi (*Wet scavenging*) bụi mịn | Nguồn khí tượng duyệt tại #19 | Nối theo khóa quan sát |
| `surface_pressure` | Float64 | $\text{hPa}$ | 1 giờ | Áp suất khí quyển bề mặt; liên quan đến điều kiện tĩnh đọng | Nguồn khí tượng duyệt tại #19 | Nối theo khóa quan sát |

---

### 3.2. Cổng Quyết định Nguồn Dữ liệu (Issue #19 as Source-Selection Gate)

Quy trình thẩm định và lựa chọn nguồn dữ liệu tuân thủ nghiêm ngặt nguyên tắc: **Khảo sát hồ sơ trước → Ra quyết định nguồn → Triển khai adapter thu thập**.

```text
DANH MỤC NGUỒN ỨNG VIÊN (CANDIDATE SOURCES)
• Tập dữ liệu Kaggle Hà Nội
• OpenAQ REST API v3
• Open-Meteo Historical Weather API (ERA5 Reanalysis)
• AirNow US Dept of State Historical CSV
• PAM Air Open Portal & các nguồn môi trường mở khác
                    │
                    ▼
     [ ISSUE #19: SOURCE PROFILING & DECISION GATE ]
     1. Data Profiling (Số dòng, số cột, tần suất, missing, duplicates)
     2. Hanoi Validation (Kiểm chứng tọa độ/địa giới hành chính Hà Nội)
     3. Temporal Coverage Validation (Xác định mốc min, max, latest thực tế)
     4. Schema Comparison & Quality Assessment
     5. Multi-Criteria Source Decision Matrix
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
[ ISSUE #3: AIR QUALITY ]   [ ISSUE #4: WEATHER ]
Triển khai adapter theo     Triển khai adapter theo
nguồn ô nhiễm được duyệt   nguồn khí tượng được duyệt
         │                     │
         │  thiết kế &         │  tiêu thụ chuỗi thời gian
         │  hiện thực hóa      │  canonical từ #3
         │  SONG SONG          │  để suy diễn dải
         │                     │  truy vấn khí tượng
```

> **Ghi chú về tính song song:** Sau khi #19 ban hành quyết định nguồn, phần việc *thiết kế và hiện thực hóa* của #3 và #4 có thể tiến hành **song song**. Tuy nhiên khi *thực thi pipeline*, #4 phải tiêu thụ chuỗi thời gian canonical do #3 sản xuất, nên #4 chạy sau #3. Cơ chế đồng bộ thời gian động đã được hiện thực hóa tại PR #25 — #4 **không** yêu cầu hiện thực hóa lại, chỉ tiêu thụ kết quả. #4 không sở hữu logic nạp ô nhiễm; #3 không phải hiện thực hóa logic khí tượng.

1. **Khảo sát Nguồn Ứng viên (Candidate Sources):**
   - Trước Issue #19, toàn bộ các nhà cung cấp dữ liệu đều là nguồn ứng viên bình đẳng. Tuyệt đối không mặc định hoặc coi bất kỳ nhà cung cấp nào (Kaggle, OpenAQ, Open-Meteo, AirNow, PAM Air) là bắt buộc.
   - Không áp đặt trước bất kỳ khung thời gian quan trắc định trước nào; độ bao phủ thời gian thực tế (mốc bắt đầu, mốc kết thúc, mốc quan sát mới nhất có thể truy xuất) được xác định từ chính dữ liệu thực sau khi khảo sát.
2. **Quyết định Chiến lược Nguồn (Source Decision):**
   - Dựa trên ma trận so sánh đa tiêu chí (độ mới, độ đầy đủ, tính toàn vẹn phạm vi Hà Nội, tính minh bạch xuất xứ và giấy phép bản quyền), Issue #19 ban hành quyết định chính thức phân định vai trò: Primary (nguồn chính), Secondary (nguồn phụ), Reference (tham chiếu), Fallback (dự phòng), hoặc Unused (không dùng).
   - Quyết định tại Issue #19 là căn cứ kỹ thuật và pháp lý bắt buộc đối với Issue #3 (Pipeline thu thập chất lượng không khí) và Issue #4 (Pipeline thu thập khí tượng).
3. **Tính toàn vẹn xuất xứ & Dữ liệu thô — Chính sách ba tầng:**
   - Toàn bộ thông tin xuất xứ (*provenance*), tham số truy vấn, ngày truy xuất, mã băm SHA-256 và giấy phép bản quyền (ODC-BY, CC BY, Open Data,...) được ghi nhận đầy đủ vào `data/raw/metadata.json`.
   - Yêu cầu về dữ liệu thô được tách thành **ba tầng kiểm chứng độc lập**, không suy diễn lẫn nhau:
     - **Tầng A — Thu thập & lưu trữ khi chạy:** payload thô tải từ API phải được ghi dưới `data/raw/` trong quá trình pipeline thực thi.
     - **Tầng B — Bảo toàn & truy vết xuất xứ:** nội dung tệp thô được giữ nguyên trạng (không chỉnh sửa, không chuyển đổi giá trị trước khi ghi) và có mã băm SHA-256 khớp tệp trên đĩa, đủ để kiểm chứng toàn vẹn độc lập.
     - **Tầng C — Chính sách theo dõi phiên bản:** tệp thô tải từ API **không bắt buộc phải được Git-track**; `.gitignore` loại trừ `data/raw/*.json` và `data/raw/*.parquet` là hành vi đúng theo chính sách kho dữ liệu, và tệp thô có thể tái tạo lại từ nguồn.
   - Tầng B là tiêu chuẩn kiểm chứng **thay thế** cho tuyên bố "bất biến". Repository không thực thi khoá chế độ chỉ đọc ở tầng hệ thống tập tin, nên các tài liệu và tiêu chí nghiệm thu **không** dùng cụm "dữ liệu thô bất biến / ở chế độ chỉ đọc" như một yêu cầu không kiểm chứng được. Định nghĩa đầy đủ: Issue #4 § "Chính sách dữ liệu thô ba tầng".
   - **Cơ chế tái tạo thực thi (bổ sung cho Tầng C):** `python scripts/fetch_dataset.py` tải lại tập dữ liệu từ hai nguồn công khai — OpenAQ S3 public archive (ODC-BY v1.0) và Open-Meteo ERA5 (CC BY 4.0), **không cần API key** — rồi tự đối chiếu nội dung với `data/raw/metadata.json`. Cờ `--skip-fetch` dùng để kiểm chứng dữ liệu đang có sẵn trên đĩa mà không gọi mạng. Chi tiết về giới hạn tái lập byte (kho S3 là kho sống; Parquet không tái lập được theo byte) tại `README.md` §4.

---

### 3.3. Đánh giá rủi ro kỹ thuật
* **Bản quyền & Giấy phép (License):** Đảm bảo giấy phép của các nguồn được chọn cho phép sử dụng cho mục đích nghiên cứu học thuật; trích dẫn nguồn đầy đủ trong `README.md` và `data/raw/metadata.json`.
* **API Rate Limit & Phân trang (Pagination):** Áp dụng chiến lược gửi request theo khối thời gian hợp lý, xử lý phân trang bằng vòng lặp kiểm tra mã phản hồi HTTP, chèn khoảng nghỉ `time.sleep()` giữa các request và lưu cache thô xuống đĩa ngay khi tải.
* **Thời gian & Múi giờ (Timezone):** Ép kiểu `datetime` có nhận thức múi giờ và chuyển đổi đồng nhất toàn bộ chuỗi về giờ địa phương Việt Nam: `Asia/Ho_Chi_Minh` (UTC+7).
* **Missing Data & Bất định Schema:** Ghi nhận cấu trúc payload nguyên bản và xử lý ánh xạ sang Canonical Schema thông qua các adapter module hóa.

---

## 4. BỘ TIÊU CHUẨN KIỂM TOÁN VÀ LÀM SẠCH DỮ LIỆU

### 4.1. Quy trình Tuần tự Chống Rò rỉ Dữ liệu Tuyệt đối
Roadmap phân định rạch ròi giữa **Làm sạch tất định** [Issue #6] và **Tiền xử lý phụ thuộc dữ liệu** [Issue #7] để bảo đảm tính liêm chính và ngăn ngừa rò rỉ dữ liệu:

```text
Dữ liệu thô (Raw Data trong data/raw/)
               │
               ▼
[ 1. LÀM SẠCH TẤT ĐỊNH - ISSUE #6 ]
├── Chuẩn hóa schema & múi giờ UTC+7 (Asia/Ho_Chi_Minh)
├── Khử trùng lặp tại khóa quan sát (station_id, timestamp)
├── Lọc bỏ giá trị âm & vi phạm giới hạn vật lý tự nhiên
├── Thực thi ràng buộc vật lý: PM2.5 <= PM10 + epsilon (khi có PM10)
├── Nhận diện lỗi kẹt cảm biến (> 6h không đổi -> NaN)
├── Cảnh báo độ ẩm cao (is_high_humidity_fog cho RH > 90%)
├── Reindex chuỗi thời gian liên tục 1h theo từng trạm quan trắc (giữ NaN)
└── Ghi nhận minh bạch mọi thao tác vào docs/cleaning_log.md
               │
               ▼
[ 2. ĐÓNG BĂNG TẬP DỮ LIỆU SẠCH (DATASET FREEZE) - ISSUE #7 ]
Chốt số lượng bản ghi và dải thời gian thực tế quan sát được
               │
               ▼
[ 3. PHÂN CHIA THEO CHUỖI THỜI GIAN (CHRONOLOGICAL SPLIT) - ISSUE #7 ]
Xác định điểm cắt thời gian khách quan (T_train < T_test) dựa trên độ bao phủ thực tế
Tuyệt đối không dùng tỷ lệ cố định trước; nghiêm cấm phân chia ngẫu nhiên
               │
               ▼
[ 4. HUẤN LUYỆN TIỀN XỬ LÝ STRICTLY TRÊN TRAIN (TRAIN-ONLY FIT) - ISSUE #7 ]
Fit các biến đổi phụ thuộc dữ liệu (SimpleImputer median, RobustScaler) duy nhất trên Train
               │
               ▼
[ 5. CHUYỂN ĐỔI DỮ LIỆU (TRANSFORM) - ISSUE #7 ]
Áp dụng tham số học từ Train để transform tập Train và tập Test
Lưu tập dữ liệu sạch hoàn chỉnh ra data/processed/air_pollution_final.parquet
               │
               ▼
[ 6. ĐÁNH GIÁ ĐỘC LẬP (EVALUATION) - ISSUE #7, #12, #13 ]
Tập Test được bảo lưu nguyên vẹn cho đo lường hiệu năng cuối cùng
```

---

### 4.2. Bộ tiêu chuẩn kiểm toán chất lượng 6 chiều (Issue #5)
Hàm kiểm toán tự động `audit_dataframe(df)` kiểm tra Canonical Schema theo 6 chiều kích thước quốc tế:
1. **Completeness (Độ đầy đủ):** Đo lường tỷ lệ missing trên từng cột và tính đầy đủ của hồ sơ xuất xứ dữ liệu.
2. **Accuracy (Độ chính xác):** Kiểm tra giới hạn vật lý và khí quyển thực tế (nhiệt độ, độ ẩm, tốc độ gió, nồng độ bụi không âm).
3. **Consistency (Độ nhất quán):** Tính nhất quán về đơn vị đo lường ($\mu\text{g/m}^3, ^\circ\text{C}, \%, \text{m/s}, \text{hPa}$) và tính nhất quán giữa các mốc thời gian.
4. **Validity (Tính hợp lệ):** Dải giá trị và kiểu dữ liệu tuân thủ đúng quy cách của Canonical Schema (`datetime64[ns]`, `float64`, `string`).
5. **Uniqueness (Tính duy nhất):** Mọi khóa quan sát `(station_id, timestamp)` hoặc `timestamp` là duy nhất, không có dòng lặp.
6. **Timeliness (Tính kịp thời):** Tần suất lấy mẫu thực tế và độ trễ dữ liệu đối chiếu với mốc thời gian mới nhất.

* **Chẩn đoán cơ chế khuyết thiếu (Rubin: MCAR, MAR, MNAR):**
  - Khảo sát các hình thái khuyết thiếu, mẫu hình phân bố, sự cụm hóa theo thời gian và mức độ khuyết thiếu theo từng trạm/nguồn quan trắc.
  - Các cơ chế MCAR, MAR, MNAR được đặt ra dưới dạng **giả định chẩn đoán cần kiểm chứng**, không khẳng định võ đoán khi chưa đủ bằng chứng thực nghiệm.
  - Trường hợp dữ liệu không cho phép kết luận dứt khoát, bắt buộc phải ghi nhận minh bạch sự không chắc chắn (*uncertainty*) trong `docs/data_quality_audit.md`.

---

### 4.3. Tiêu chuẩn làm sạch tất định & Bảo toàn dữ liệu (Issue #6)
- [ ] **Missing ngụy trang:** Rà soát và chuyển đổi các ký tự lỗi trạm (`"-999"`, `"-9999"`, `"N/A"`, `"None"`, `"null"`, `""`) thành `NaN`.
- [ ] **Giá trị âm hoặc phi lý:** Chuyển các giá trị nồng độ $\text{PM}_{2.5} < 0$ hoặc tốc độ gió âm thành `NaN`.
- [ ] **Lỗi kẹt cảm biến (Stuck values):** Nồng độ giữ nguyên không đổi suốt $> 6$ giờ liên tiếp $\to$ Chuyển thành `NaN`.
- [ ] **Cảnh báo độ ẩm cao:** Khi $\text{RH} > 90\%$, gắn cờ cảnh báo `is_high_humidity_fog = 1` phục vụ phân tích chẩn đoán; **tuyệt đối không tự ý xóa bỏ bản ghi**.
- [ ] **Reindex chuỗi thời gian liên tục:** 
  - Thực hiện tạo lưới 1 giờ liên tục (`freq='h'`) từ mốc bắt đầu đến mốc kết thúc của dải dữ liệu thực tế.
  - **Quy tắc an toàn đa trạm:** Nếu dữ liệu gồm nhiều trạm quan trắc, reindex bắt buộc thực hiện độc lập cho từng trạm (thông qua `groupby('station_id')` hoặc MultiIndex `(station_id, timestamp)`), không áp đặt một trục thời gian đơn nhất chung cho mọi trạm.
  - Các khoảng trống thời gian sau reindex giữ nguyên dạng `NaN` để bộc lộ trung thực khoảng khuyết; gắn cờ `pm25_was_missing = 1` cho các khoảng khuyết lớn ($> 6$ giờ).
- [ ] **Ràng buộc logic vật lý:** Khi trường `pm10` khả dụng, kiểm tra ràng buộc $\text{PM}_{2.5} \le \text{PM}_{10} + \epsilon$. Bản ghi vi phạm được chuyển thành `NaN`.
- [ ] **Ứng xử với Outliers:** Bảo toàn nguyên vẹn các giá trị cực trị thực tế (đợt bùng phát ô nhiễm, nghịch nhiệt, giao thừa pháo hoa); chỉ xử lý các giá trị bất thường do lỗi phần cứng đã được chứng minh.
- [ ] **Nhật ký làm sạch:** Mọi phép biến đổi, căn cứ logic và số dòng bị tác động được ghi nhận đầy đủ vào `docs/cleaning_log.md`.

---

## 5. THIẾT KẾ PHÂN TÍCH CHUỖI THỜI GIAN (TIME-SERIES)

> Phân tích chuỗi thời gian tại **Issue #8** được thực hiện theo định hướng khám phá số liệu thực nghiệm, không đưa ra kết luận hay quy luật áp đặt trước:

1. **Phân tích theo Giờ trong ngày (Diurnal Pattern - Hourly Aggregation):**
   - *Cách làm:* Nhóm theo giờ trong ngày qua 24 khung giờ, tính toán trung vị, trung bình và khoảng phân vị IQR: `df.groupby('hour')['pm25'].agg(['median', 'mean', lambda x: x.quantile(0.75) - x.quantile(0.25)])`.
   - *Mục tiêu khám phá:* Khảo sát diễn biến nồng độ $\text{PM}_{2.5}$ qua 24 giờ và nhận diện các khoảng thời gian tập trung nồng độ cao/thấp thực tế trong dữ liệu mà không áp đặt trước khung giờ đỉnh/đáy.
2. **Phân tích theo Ngày trong tuần (Day-of-Week Effect):**
   - *Cách làm:* So sánh phân phối nồng độ bụi từ Thứ Hai đến Chủ Nhật và giữa ngày làm việc (*Weekday*) với ngày cuối tuần (*Weekend*).
   - *Mục tiêu khám phá:* Đánh giá sự khác biệt về mức độ ô nhiễm giữa các ngày trong tuần dưới tác động của nhịp sinh hoạt và giao thông đô thị dựa trên bằng chứng dữ liệu.
3. **Phân tích theo Tháng và Mùa vụ (Monthly & Seasonal Pattern):**
   - *Cách làm:* Lập biểu đồ phân bố (Boxplot) nồng độ bụi theo các tháng và mùa trong phạm vi chuỗi dữ liệu thực tế thu thập được.
   - *Mục tiêu khám phá:* Nhận diện quy luật biến động nồng độ bụi giữa các tháng và mùa trong năm (mùa khô/lạnh vs mùa mưa/nóng) từ số liệu thực nghiệm.
4. **Phân tích Xu hướng dài hạn & Lọc nhiễu (Trend & Rolling Smoothing):**
   - *Cách làm:* Tính đường trung bình trượt 24 giờ (`rolling_24h`) để triệt tiêu biến động ngày đêm và đường trung bình trượt 7 ngày (`rolling_7d`) để theo dõi xu hướng các đợt tích tụ ô nhiễm.
   - *Phân rã chuỗi thời gian:* Kỹ thuật phân rã chuỗi thời gian (*Trend + Seasonal + Residual*) bằng `seasonal_decompose` (statsmodels) chỉ được áp dụng khi chuỗi dữ liệu quan sát thực tế đáp ứng đầy đủ tính đều đặn (*regularity*) và độ phủ chu kỳ liên tục.

---

## 6. THỐNG KÊ MÔ TẢ (DESCRIPTIVE STATISTICS)

Tuân thủ nguyên tắc Week 6: **"Hình dạng quyết định chỉ số" (Shape picks the statistic)** [Issue #8].

### 6.1. Bảng cấu trúc 4 họ đại lượng thống kê

| Họ đại lượng | Chỉ số tính toán | Ý nghĩa đối với biến $\text{PM}_{2.5}$ | Nguyên tắc lựa chọn chỉ số |
|---|---|---|---|
| **1. Đo lường Vị trí (Location)** | - **Median (Trung vị)**<br>- Mean (Trung bình)<br>- Mode (Yếu vị) | Phản ánh mức độ ô nhiễm của một thời điểm điển hình trong chuỗi quan sát. | Nếu phân phối thực nghiệm lệch mạnh (Skewness đáng kể), **Median** là đại lượng đại diện trung thực hơn Mean, tránh bị kéo lệch bởi các cực trị. |
| **2. Đo lường Phân tán (Spread)** | - **IQR ($Q_3 - Q_1$)**<br>- Độ lệch chuẩn ($s$)<br>- Range ($\max - \min$) | Đo lường độ biến thiên nồng độ bụi trong khoảng 50% số quan sát ở trung tâm. | Khi phân phối lệch và có cực trị thực tế, **IQR** là thước đo độ phân tán bền vững (*robust*), không bị thổi phồng như độ lệch chuẩn $s$. |
| **3. Đo lường Hình dạng (Shape)** | - **Skewness (Độ lệch)**<br>- **Kurtosis (Độ nhọn/đuôi)** | Định lượng mức độ bất đối xứng và độ dày của đuôi phân phối thực nghiệm. | Đo lường hình dạng phân phối thực tế để biện luận khách quan cho việc lựa chọn chỉ số mô tả và kiểm tra điều kiện áp dụng các phép kiểm thống kê. |
| **4. Phân vị (Percentiles)** | - $P_{10}, P_{25}, P_{50}, P_{75}$<br>- $P_{90}, P_{95}, P_{99}$ | Cung cấp thông tin ngưỡng nồng độ phơi nhiễm thực tế của cộng đồng tại các phân vị cao. | Hỗ trợ phân tích ngưỡng rủi ro phơi nhiễm cho y tế công cộng mà các chỉ số trung tâm đơn lẻ không phản ánh được. |

### 6.2. Đo lường tương quan hai biến (Correlation Analysis)
- Lập ma trận tương quan kép bao gồm cả **Pearson $r$** (bắt quan hệ tuyến tính) và **Spearman $\rho$** (bắt quan hệ đơn điệu phi tuyến).
- Luôn đối chiếu hệ số tương quan với biểu đồ phân tán (Scatter plot) để nhận diện các mối quan hệ phi tuyến tiềm năng và tránh ngụy biện tương quan (bài học Anscombe's Quartet & Datasaurus Dozen).

---

## 7. BỘ THIẾT KẾ TRỰC QUAN HÓA (DATA VISUALIZATION PLAN)

> Bộ 7 biểu đồ ấn phẩm giải thích (Explanatory plots) từ **FIG-01 đến FIG-07** được hiện thực hóa tại **Issue #9** theo chuẩn mực Tufte và Cleveland, tuân thủ nghiêm ngặt ngữ nghĩa quy chuẩn pháp lý và tiêu đề phát biểu kết luận khoa học rút ra từ dữ liệu thực tế (Data-driven Takeaway titles):

### 7.1. Bảng chi tiết 7 biểu đồ ấn phẩm giải thích (FIG-01 đến FIG-07)

| Mã Chart | Câu hỏi trả lời | Loại Chart | Biến trục X | Biến trục Y | Mức tổng hợp | Đơn vị | Quy cách Tiêu đề & Ngưỡng Quy chuẩn |
|---|---|---|---|---|---|---|---|
| **FIG-01** | Ô nhiễm biến thiên dài hạn như thế nào và diễn biến các đợt bùng phát ra sao? | Line chart kết hợp Rolling Mean | Thời gian | $\text{PM}_{2.5}$ trung bình | Chuỗi thời gian (kèm đường trượt 24h & 7d) | $\mu\text{g/m}^3$ | Tiêu đề: Phát biểu kết luận về diễn biến thực tế. Đường ngưỡng 24h của QCVN 05:2023/BTNMT ($50\,\mu\text{g/m}^3$) chỉ hiển thị cùng chuỗi trung bình trượt 24h tương thích toán học. |
| **FIG-02** | Hình dạng phân phối thực nghiệm của bụi mịn có lệch chuẩn không? | Histogram + đường KDE | Nồng độ $\text{PM}_{2.5}$ | Mật độ xác suất (Density) | Toàn bộ mẫu quan sát | $\mu\text{g/m}^3$ | Tiêu đề: Phát biểu kết luận về độ lệch phân phối và sự phù hợp của đại lượng thống kê đại diện (Median vs Mean). |
| **FIG-03** | Mức độ ô nhiễm biến động giữa các tháng và mùa trong chuỗi quan sát ra sao? | Boxplot | Tháng / Mùa | Nồng độ $\text{PM}_{2.5}$ | Phân bố theo tháng/mùa | Tháng / $\mu\text{g/m}^3$ | Tiêu đề: Phát biểu kết luận về sự khác biệt nồng độ bụi giữa các khoảng thời gian dựa trên bằng chứng dữ liệu. |
| **FIG-04** | Khung thời gian nào trong ngày và tuần tập trung nồng độ ô nhiễm cao/thấp? | 2D Heatmap | Giờ trong ngày ($0 - 23\text{h}$) | Thứ trong tuần (T2 - CN) | Median theo từng ô (Hour $\times$ Day) | $\mu\text{g/m}^3$ | Tiêu đề: Phát biểu kết luận về các khung thời gian tập trung mật độ ô nhiễm quan sát được. |
| **FIG-05** | Yếu tố khí tượng (tốc độ gió hoặc nhiệt độ) liên hệ thực nghiệm thế nào với bụi mịn? | Scatter plot + đường làm mượt LOWESS | Biến khí tượng quan sát | $\text{PM}_{2.5}$ | Quan sát theo giờ | $\text{m/s}$ hoặc $^\circ\text{C}$ vs $\mu\text{g/m}^3$ | Tiêu đề: Phát biểu kết luận về dạng quan hệ thực nghiệm giữa yếu tố thời tiết và bụi mịn. |
| **FIG-06** | Mức độ tương quan giữa các chất ô nhiễm và biến thời tiết quan sát được là bao nhiêu? | Correlation Heatmap | Ma trận các biến | Ma trận các biến | Toàn bộ mẫu quan sát | Hệ số $r$ ($-1$ đến $+1$) | Tiêu đề: Phát biểu kết luận về hướng và độ lớn tương quan từ dữ liệu thực tế. |
| **FIG-07** | Tỷ lệ thời gian quan sát được tại các mức chất lượng không khí theo quy chuẩn? | Bar chart (Trục tung bắt đầu từ 0) | Các mức chất lượng không khí | Tỷ lệ phần trăm thời gian | Tổng hợp chuỗi dữ liệu | $\%$ thời gian | Tiêu đề: Phát biểu kết luận về tỷ lệ thời gian quan sát được. Việc phân loại bắt buộc sử dụng chỉ số và ngưỡng có chu kỳ lấy mẫu tương thích toán học với quy chuẩn viện dẫn. |

* **Quy chuẩn nghiêm ngặt về biểu diễn các ngưỡng quy chuẩn / khuyến nghị:**
  1. Khi biểu diễn bất kỳ đường ngưỡng quy chuẩn nào (QCVN 05:2023/BTNMT hoặc WHO 2021), bắt buộc phải xác định rõ: chất ô nhiễm ($\text{PM}_{2.5}$), chu kỳ lấy mẫu trung bình (24 giờ hay trung bình năm), văn bản quy chuẩn/hướng dẫn và phiên bản áp dụng.
  2. **Tương thích toán học tuyệt đối (Mathematical compatibility):** Tuyệt đối không so sánh trực tiếp số đo tức thời theo giờ với ngưỡng giới hạn trung bình 24 giờ ($50\,\mu\text{g/m}^3$) hoặc trung bình năm ($25\,\mu\text{g/m}^3$); đường ngưỡng 24 giờ phải được áp dụng trên chuỗi trung bình trượt 24 giờ (`rolling_24h`) hoặc trung bình ngày.
  3. Giữ tách bạch rõ ràng giữa quy chuẩn bắt buộc của Việt Nam (QCVN) và khuyến nghị hướng dẫn quốc tế (WHO).
  4. Trục tung của biểu đồ cột bắt buộc bắt đầu từ 0; tuyệt đối không sử dụng biểu đồ 3D hay pie chart.

---

## 8. SUY LUẬN THỐNG KÊ (STATISTICAL INFERENCE)

Áp dụng bài học Week 9: **"Inference is a leap"** [Issue #11]. Không báo cáo $p$-value đơn độc! Bắt buộc trình bày đầy đủ bộ bốn: **Thống kê kiểm định + $p$-value + Kích thước hiệu ứng (Effect Size) + Khoảng tin cậy Bootstrap 95%**.

### 8.1. Kiểm định 1: So sánh Ô nhiễm giữa các Mùa trong năm
* **Câu hỏi nghiên cứu:** Nồng độ $\text{PM}_{2.5}$ giữa các mùa quan sát (ví dụ Mùa khô/lạnh vs Mùa mưa/nóng) có sự khác biệt có ý nghĩa thống kê hay không?
* **Giả thuyết:**
  - $H_0: \tilde{\mu}_{\text{Mùa 1}} = \tilde{\mu}_{\text{Mùa 2}}$ (Trung vị nồng độ $\text{PM}_{2.5}$ hai mùa là như nhau).
  - $H_1: \tilde{\mu}_{\text{Mùa 1}} \ne \tilde{\mu}_{\text{Mùa 2}}$ (hoặc kiểm định một phía nếu có giả thuyết hướng).
* **Lựa chọn phép kiểm định & Kiểm tra giả định:**
  - Kiểm tra tính chuẩn bằng Shapiro-Wilk test trên từng mùa quan sát.
  - Khi phân phối vi phạm tính chuẩn, áp dụng **Kiểm định phi tham số Mann-Whitney U** (`scipy.stats.mannwhitneyu`).
* **Mức ý nghĩa:** $\alpha = 0.05$.
* **Kích thước hiệu ứng & Khoảng tin cậy:**
  - Tính hệ số tương quan hạng lưỡng phân (*Rank-Biserial Correlation* $r_{rb} = 1 - \frac{2U}{n_1 n_2}$).
  - Ước lượng khoảng tin cậy 95% cho chênh lệch trung vị bằng kỹ thuật **Bootstrap resampling** (1.000 lần lặp, cố định `np.random.seed(42)` để tái lập).
* **Quy cách kết luận chuẩn:** Báo cáo trung thực kết quả kiểm định từ dữ liệu thực: Thống kê $U$, giá trị $p$, chỉ số $r_{rb}$ và 95% Bootstrap CI.

---

### 8.2. Kiểm định 2: So sánh Ngày làm việc (Weekday) vs Ngày cuối tuần (Weekend)
* **Câu hỏi nghiên cứu:** Sự khác biệt về nồng độ $\text{PM}_{2.5}$ giữa ngày làm việc (Thứ Hai – Thứ Sáu) và ngày cuối tuần (Thứ Bảy – Chủ Nhật) có đạt ý nghĩa thống kê hay không?
* **Giả thuyết:**
  - $H_0: \text{Median}_{\text{Weekday}} = \text{Median}_{\text{Weekend}}$.
  - $H_1: \text{Median}_{\text{Weekday}} \ne \text{Median}_{\text{Weekend}}$.
* **Phép kiểm:** Mann-Whitney U test hai phía (`scipy.stats.mannwhitneyu`).
* **Ý nghĩa thực tiễn vs Ý nghĩa Thống kê:** Phân tích rạch ròi giữa mức độ ý nghĩa thống kê ($p < \alpha$) và quy mô hiệu ứng thực tế ($r_{rb}$ và chênh lệch nồng độ tuyệt đối) để tránh ngụy biện do cỡ mẫu lớn.

---

### 8.3. Kiểm định 3: Đối chiếu với Quy chuẩn Kỹ thuật Quốc gia QCVN
* **Câu hỏi nghiên cứu:** Nồng độ $\text{PM}_{2.5}$ quan sát được có vượt quá Quy chuẩn kỹ thuật quốc gia QCVN 05:2023/BTNMT hay không?
* **Quy chuẩn đối chiếu:** Áp dụng đúng chỉ số trung bình tương thích toán học với ngưỡng giới hạn tương ứng của QCVN 05:2023/BTNMT (ví dụ trung bình năm so với ngưỡng năm $25\,\mu\text{g/m}^3$, hoặc trung bình 24 giờ so với ngưỡng 24 giờ $50\,\mu\text{g/m}^3$; tuyệt đối không so sánh số đo giờ đơn lẻ với ngưỡng năm).
* **Phép kiểm:** Phép kiểm phi tham số phù hợp (One-sample Wilcoxon signed-rank test trên chuỗi giá trị tổng hợp tương thích). Báo cáo khoảng tin cậy 95% của nồng độ trung bình chuỗi quan sát.

---

## 9. PHÂN TÍCH HỒI QUY (REGRESSION ANALYSIS)

> Xây dựng mô hình hồi quy tuyến tính OLS đa biến khảo sát mối liên hệ giữa thời tiết và $\text{PM}_{2.5}$ tại **Issue #12**, thực hiện chẩn đoán toàn diện giả định LINE và điều hòa:

### 9.1. Thiết lập bài toán Hồi quy
* **Biến mục tiêu ($Y$):** Khảo sát biến đổi logarit $Y = \log(1 + \text{PM}_{2.5})$ (`np.log1p`) như một phép biến đổi ứng viên trên tập Train. Hiệu quả cải thiện tính tuyến tính và phân phối phần dư bắt buộc phải được kiểm chứng qua quy trình chẩn đoán sau khi khớp (post-fit diagnostics), không xem biến đổi là bảo chứng tiên nghiệm.
* **Các biến độc lập ($X$):** Các biến khí tượng bề mặt quan sát được (`temperature`, `relative_humidity`, `wind_speed`, `surface_pressure` nếu có) kết hợp biến trễ hợp lệ (`pm25_lag24`).
* **Mô hình Baseline:** Dummy Regressor (dự báo trung vị hoặc trung bình của tập Train) làm chuẩn đối sánh bắt buộc.
* **Phân chia Train / Test:** Kế thừa điểm cắt phân chia thời gian tuyến tính từ Issue #7 sau khi đóng băng dữ liệu; tuyệt đối không áp đặt tỷ lệ chia cố định. Tập Test được bảo lưu nguyên vẹn cho đo lường hiệu năng cuối cùng.

---

### 9.2. Chẩn đoán 4 Giả định OLS (LINE Diagnostic Framework)

```text
Fit mô hình OLS trên Train
            │
            ▼
Chẩn đoán 4 Giả định LINE trên Phần dư (Residuals)
├── L (Linearity): Đồ thị Residuals vs Fitted values (kiểm tra phi tuyến)
├── I (Independence): Thống kê Durbin-Watson & ACF (kiểm tra tự tương quan)
├── N (Normality): Biểu đồ Q-Q Plot & kiểm định tính chuẩn phần dư
└── E (Equal Variance): Kiểm định Breusch-Pagan & đồ thị Scale-Location
            │
            ▼
Đánh giá Heuristics Đa cộng tuyến & Điểm ảnh hưởng
├── VIF: Đánh giá VIF > 5.0 dưới dạng chỉ báo gợi ý chẩn đoán (heuristic)
└── Cook's Distance: Rà soát quan sát có ảnh hưởng lớn bất thường (D_i > 0.5)
            │
            ▼
Thỏa mãn? ──► [Có] ──► Giữ mô hình, giải thích hệ số beta
   │
   └──► [Không] ──► Thử nghiệm điều hòa Ridge / Lasso (tune trên Train)
                      Báo cáo trung thực hạn chế mô hình nếu vi phạm vẫn tồn tại
```

* **Mô hình điều hòa (Ridge / Lasso):** Dò tìm siêu tham số ($\alpha$) hoàn toàn trên tập Train (Time-Series Split / Cross-Validation cục bộ trên Train); **tuyệt đối không sử dụng tập Test để lựa chọn siêu tham số hay lựa chọn mô hình**.

---

### 9.3. Đánh giá và Diễn giải Hệ số $\beta$
* **Thước đo đánh giá trên tập TEST độc lập:** Báo cáo **MAE**, **RMSE**, và **$R^2$** đặt cạnh Baseline Dummy Regressor. Nếu giả định LINE bị vi phạm, giải trình khách quan các giới hạn của mô hình OLS trên chuỗi thời gian ô nhiễm.
* **Mẫu câu diễn giải 3 nghĩa vụ bắt buộc (Phi nhân quả):**
  > *"Mỗi mét/giây ($\text{m/s}$) tốc độ gió tăng thêm **liên hệ với** mức thay đổi trung bình $\beta\%$ nồng độ $\text{PM}_{2.5}$, **trong điều kiện giữ nguyên không đổi tất cả các biến số khác trong mô hình**, trong phạm vi tốc độ gió quan sát được từ $[\min, \max]\,\text{m/s}$."*
  > *(Tuyệt đối không dùng từ "gây ra" hay khẳng định quan hệ nhân quả từ mô hình quan sát).*

---

## 10. PHÂN LOẠI & KỸ NGHỆ ĐẶC TRƯNG (CLASSIFICATION & FEATURE ENGINEERING)

> Xây dựng pipeline phân loại cảnh báo sớm ô nhiễm tại **Issue #13**, tối ưu ngưỡng quyết định theo mục tiêu vận hành và kiểm toán rò rỉ dữ liệu:

### 10.1. Đặt bài toán & Nhãn nhị phân
* **Định nghĩa nhãn ($Y \in \{0, 1\}$):** 
  - Nhãn mục tiêu được xác định rõ chất ô nhiễm, chu kỳ lấy mẫu trung bình và quy chuẩn áp dụng tương thích toán học (ví dụ nồng độ trung bình 24 giờ $\text{PM}_{2.5} \ge 50\,\mu\text{g/m}^3$ theo ngưỡng 24h của QCVN 05:2023/BTNMT).
  - Lớp 1: Ngày ô nhiễm vượt ngưỡng cảnh báo; Lớp 0: Mức chấp nhận được.

---

### 10.2. Kỹ nghệ đặc trưng từ quá khứ (Feature Engineering)
Tạo các đặc trưng miền ứng dụng chỉ sử dụng thông tin quá khứ ($t \le t_{\text{current}}$):
1. `pm25_rolling_mean_24h`, `pm25_rolling_std_24h`: Quán tính và độ biến động ô nhiễm trong 24 giờ qua.
2. `pm25_lag24`: Nồng độ tại cùng thời điểm ngày hôm trước.
3. `temp_humidity_index`: Chỉ số tương tác nhiệt ẩm (khi khả dụng).
4. `wind_stagnant`: Cờ nhị phân báo hiệu điều kiện lặng gió.
5. `hour_sin`, `hour_cos`, `month_sin`, `month_cos`: Biến đổi tuần hoàn lượng giác của thời gian.

---

### 10.3. Xử lý Mất cân bằng & Tối ưu Ngưỡng Quyết định
* **Mất cân bằng lớp (Class Imbalance):** Tỷ lệ nhãn thực tế được đo đạc khách quan từ dữ liệu, không áp đặt giả định trước. Tránh bẫy Accuracy trên dữ liệu mất cân bằng.
* **Thước đo chính:** Bắt buộc báo cáo **Recall**, **PR-AUC**, **Precision**, **F-beta**, và **Confusion Matrix** trên tập Test độc lập.
* **Khung tối ưu ngưỡng quyết định (Threshold Tuning trên Train/Validation):**
  - Việc dò tìm và lựa chọn ngưỡng quyết định tối ưu thực hiện hoàn toàn trên tập Train/Validation theo mục tiêu vận hành cụ thể:
    - Phương án A: Tối đa hóa điểm $F_\beta$ với $\beta > 1$ (ví dụ $\beta = 2$, nhấn mạnh tầm quan trọng của Recall).
    - Phương án B: Tối đa hóa Recall dưới ràng buộc Precision tối thiểu (ví dụ $\text{Precision} \ge P_{\min}$).
  - Sau khi chốt mô hình và ngưỡng trên tập huấn luyện, thực hiện đo lường hiệu năng một lần duy nhất trên tập Test độc lập đã đóng băng.
* **Mô hình so sánh:** Baseline (DummyClassifier) vs Logistic Regression (`class_weight='balanced'`) vs Random Forest Classifier.

---

### 10.4. Kiểm toán chống Rò rỉ Dữ liệu (Data Leakage Audit)
Lập biên bản kiểm toán rà soát 4 dạng rò rỉ dữ liệu:
1. **Target Leakage:** Loại trừ toàn bộ các biến phái sinh trực tiếp từ mục tiêu (như chỉ số AQI tổng hợp).
2. **Train-Test Contamination:** Scaler và Imputer chỉ `fit` trên tập Train qua Scikit-Learn Pipeline.
3. **Temporal Leakage:** Dữ liệu phân chia theo thời gian tuyến tính ($T_{\text{train}} < T_{\text{test}}$); kỹ nghệ đặc trưng chỉ nhìn về quá khứ.
4. **Group Leakage:** Bảo đảm không có sự chồng lấn phụ thuộc thời gian hay đơn vị quan sát giữa hai tập.

---

## 11. ĐẠO ĐỨC DỮ LIỆU, ĐỊNH KIẾN & GIỚI HẠN (ETHICS, BIAS & LIMITATIONS)

> Đo đạc thực nghiệm quy mô dữ liệu vs Spark, khảo sát các giả thuyết định kiến và lập hồ sơ chuẩn hóa tại **Issue #14**:

### 11.1. Sổ tay Định kiến (Field Guide to Bias Hypotheses)
* **Giả thuyết Sensor Bias:** Khảo sát độ tin cậy của cảm biến quang học trong các điều kiện độ ẩm rất cao ($\text{RH} > 90\%$).
* **Giả thuyết Spatial Representation Bias:** Khảo sát tính đại diện địa lý của mạng lưới trạm quan trắc trên địa bàn Hà Nội đối với mức độ phơi nhiễm thực tế của toàn bộ dân cư.
* **Giả thuyết Survivorship / Weather-related Missingness Bias:** Khảo sát xem hiện tượng gián đoạn dữ liệu quan trắc có tương quan với các sự kiện thời tiết cực đoan (mưa bão, ngập lụt) hay không.
* **Quy ước biểu diễn:** Phân định rạch ròi giữa "không quan sát được" (`NaN`) và "nồng độ bằng 0" (`0.0`).

---

### 11.2. Đo đạc Thực nghiệm Quy mô Dữ liệu vs Apache Spark
* Bắt buộc tiến hành đo đạc trực tiếp các chỉ số tài nguyên thực tế trên tập dữ liệu đã thu thập và chuyển đổi:
  1. Dung lượng lưu trữ trên đĩa (Disk size theo MB của tệp Parquet và CSV).
  2. Lượng bộ nhớ RAM chiếm dụng khi nạp DataFrame.
  3. Thời gian đọc/ghi dữ liệu (I/O throughput).
  4. Thời gian thực thi tiền xử lý, tính toán đặc trưng và huấn luyện mô hình.
  5. Đặc tính khối lượng công việc thực tế (Workload characteristics).
* **Đánh giá kiến trúc xử lý:** Lập luận về việc có hay không sử dụng Apache Spark/Hadoop phải được dẫn xuất chặt chẽ từ kết quả đo đạc thực nghiệm nói trên, tránh đưa ra kết luận trước khi có dữ liệu đo đạc.

---

### 11.3. Hồ sơ Chuẩn hóa Datasheet, Model Card & Project Charter
1. **Datasheet for Dataset (`docs/datasheet.md` - 1 trang):** Biên soạn theo khung chuẩn Timnit Gebru: Mục đích, thành phần, quy trình thu thập, tiền xử lý, phạm vi sử dụng hợp lệ và bảo trì dữ liệu.
2. **Model Card (`docs/model_card.md` - 1 trang):** Tên mô hình cảnh báo sớm, kiến trúc, hiệu năng phân tầng, giới hạn hoạt động và khuyến cáo an toàn khi triển khai thực tế.
3. **Tuyên bố AI trong `README.md`:** Khai báo minh bạch các nội dung có AI hỗ trợ và cam kết sinh viên tự giải trình logic toán học trong buổi phản biện (*Viva*).
4. **Project Charter (`docs/project_charter.md`):** Bản điều lệ dự án quy chuẩn theo yêu cầu môn học.

---

## 12. CÔNG NGHỆ VÀ CẤU TRÚC DỰ ÁN (PROJECT STRUCTURE)

### 12.1. Tech Stack chuẩn mực
* **Ngôn ngữ:** Python 3.10+
* **Thao tác & Lưu trữ:** Pandas, NumPy, PyArrow / FastParquet (định dạng Snappy Parquet).
* **Trực quan hóa:** Matplotlib (hướng đối tượng `fig, ax`), Seaborn.
* **Thống kê & Suy luận:** SciPy (`scipy.stats`), Statsmodels (`statsmodels.api`, `statsmodels.tsa`).
* **Học máy & Pipeline:** Scikit-Learn (`sklearn.pipeline`, `sklearn.compose`).
* **Quản lý mã nguồn:** Git, GitHub repository.

---

### 12.2. Cấu trúc Repository chuẩn mực

```text
air-pollution-analysis/
├── .gitignore                          # Loại trừ data/raw, cache, .env, venv
├── LICENSE                             # Giấy phép mã nguồn mở MIT
├── README.md                           # Giới thiệu dự án, cách tái lập, bảng phân công, AI usage
├── requirements.txt                    # Danh sách thư viện và phiên bản cố định
├── data/
│   ├── raw/                            # DỮ LIỆU GỐC (giữ nguyên trạng, không sửa tay, không Git-track)
│   │   ├── metadata.json               # Xuất xứ nguồn, query params, ngày tải, schema gốc, bản quyền
│   │   └── .gitkeep
│   ├── interim/                        # Dữ liệu trung gian sau làm sạch tất định
│   │   └── .gitkeep
│   └── processed/                      # Dữ liệu sạch đóng băng lưu dạng Snappy Parquet
│       ├── air_pollution_final.parquet # Tệp dữ liệu hoàn chỉnh sau tích hợp và pipeline
│       └── .gitkeep
├── docs/
│   ├── roadmap.md                      # Lộ trình và đặc tả yêu cầu chi tiết 15 tuần
│   ├── data_dictionary.md              # Từ điển dữ liệu chuẩn hóa Canonical Schema [Issue #2]
│   ├── source_profiling_decision.md    # Báo cáo thẩm định & quyết định chiến lược nguồn [Issue #19]
│   ├── cleaning_log.md                 # Nhật ký làm sạch dữ liệu tất định [Issue #6]
│   ├── datasheet.md                    # Datasheet for Dataset chuẩn Timnit Gebru [Issue #14]
│   ├── model_card.md                   # Model Card 1 trang cho mô hình cảnh báo [Issue #14]
│   ├── project_charter.md              # Điều lệ dự án quy chuẩn môn học [Issue #14]
│   ├── mentoring_feedback.md           # Bảng theo dõi tiếp thu ý kiến cố vấn [Issue #15]
│   └── viva_qa_prep.md                 # 15 câu hỏi chuẩn bị vấn đáp phản biện [Issue #16]
├── notebooks/
│   ├── 00_environment_test.ipynb       # Kiểm thử môi trường và nạp thư viện [Issue #1]
│   ├── 01_data_collection.ipynb        # Thực thi adapter thu thập dữ liệu ô nhiễm & khí tượng [Issue #3, #4]
│   ├── 02_quality_audit.ipynb          # Kiểm toán 6 chiều chất lượng dữ liệu [Issue #5]
│   ├── 03_data_cleaning.ipynb          # Làm sạch tất định và reindex chuỗi thời gian [Issue #6]
│   ├── 03_transformation_pipeline.ipynb# Tích hợp, đóng băng, split và đóng gói Pipeline [Issue #7]
│   ├── 04_descriptive_stats.ipynb      # Thống kê mô tả 4 họ chỉ số & phân tích chu kỳ [Issue #8]
│   ├── 05_statistical_inference.ipynb  # Kiểm định phi tham số, Effect Size, Bootstrap CI [Issue #11]
│   ├── 06_regression_modeling.ipynb    # Hồi quy OLS, chẩn đoán LINE, Ridge/Lasso [Issue #12]
│   └── 06_classification_alerts.ipynb  # Phân loại cảnh báo sớm, PR-AUC, Threshold tuning [Issue #13]
├── src/
│   ├── __init__.py
│   ├── data_loader.py                  # Module nạp file Parquet, adapter dữ liệu [Issue #3, #4, #15]
│   ├── cleaning_pipeline.py            # Scikit-Learn Pipeline đóng gói tiền xử lý [Issue #7, #15]
│   └── visualizer.py                   # Hàm vẽ biểu đồ chuẩn phong cách Tufte/Cleveland [Issue #9, #15]
├── figures/                            # 7 Biểu đồ ấn phẩm giải thích (FIG-01 đến FIG-07, PNG 300 DPI) [Issue #9]
│   └── .gitkeep
└── reports/
    ├── statistical_profile.csv         # Bảng hồ sơ thống kê mô tả 4 họ chỉ số [Issue #8]
    ├── midterm_report.pdf              # Báo cáo giữa kỳ EDA (8–10 trang, Tuần 8) [Issue #10]
    ├── final_report.pdf                # Báo cáo đồ án cuối kỳ SCQA (Tuần 14–15) [Issue #16]
    ├── defense_minutes.md              # Biểu mẫu biên bản đánh giá bảo vệ đồ án [Issue #17]
    └── .gitkeep
```

---

## 13. XUẤT KẾT QUẢ TỔNG QUAN THEO YÊU CẦU

### A. Project Scope
* **Tên dự án:** Phân tích mức độ ô nhiễm không khí theo thời gian và xây dựng mô hình cảnh báo sớm bụi mịn $\text{PM}_{2.5}$ tại Hà Nội.
* **Main Research Question:** Nồng độ bụi mịn $\text{PM}_{2.5}$ biến động theo những quy luật chu kỳ thời gian nào, liên hệ ra sao với các yếu tố khí tượng bề mặt, và làm thế nào để cảnh báo sớm các đợt ô nhiễm vượt ngưỡng an toàn dựa trên dữ liệu chuỗi thời gian mà không vi phạm rò rỉ dữ liệu?
* **Sub-questions:**
  - SQ1: Hình dạng phân phối thực nghiệm của $\text{PM}_{2.5}$ có đặc tính lệch ra sao và đại lượng thống kê nào phản ánh trung thực nhất?
  - SQ2: Sự khác biệt nồng độ ô nhiễm giữa ngày làm việc vs cuối tuần, giữa các mùa có đạt ý nghĩa thống kê kèm effect size và khoảng tin cậy ra sao?
  - SQ3: Các biến thời tiết liên hệ thế nào với nồng độ bụi trong mô hình hồi quy OLS, và các giả định LINE có được thỏa mãn không?
  - SQ4: Mô hình phân loại cảnh báo sớm giải quyết bài toán mất cân bằng lớp và tối ưu hóa ngưỡng quyết định theo mục tiêu vận hành như thế nào?
* **Dataset:** Chuỗi thời gian quan trắc theo giờ trên địa bàn Hà Nội, tích hợp giữa dữ liệu chất lượng không khí và dữ liệu khí tượng bề mặt theo chiến lược nguồn được phê duyệt tại Issue #19. Dải thời gian thực tế bắt đầu và kết thúc được dẫn xuất từ độ phủ thực tế của nguồn dữ liệu sau khi khảo sát và đóng băng.
* **Expected Outputs:** 1 Repo GitHub hoàn chỉnh (chạy thông suốt từ đầu đến cuối không lỗi), 1 Báo cáo EDA Giữa kỳ (8–10 trang), 1 Báo cáo Đồ án Cuối kỳ (SCQA), 7 biểu đồ ấn phẩm chuẩn mực in ấn (FIG-01 đến FIG-07), 1 Datasheet for Dataset, 1 Model Card, bộ câu hỏi vấn đáp Viva.

---

### B. Skill Mapping (Ma trận Ánh xạ Kiến thức INFO3020)

| Chủ đề INFO3020 | Nội dung áp dụng cụ thể trong Project | Issue phụ trách | Bắt buộc? |
|---|---|:---:|:---:|
| **W1: What is Data Science** | Vòng đời CRISP-DM, cấu trúc repo chuẩn, quy tắc dữ liệu thô & provenance, câu hỏi nghiên cứu & Canonical Schema | #1, #2 | **Bắt buộc** |
| **W2: Multi-source Collection** | Khảo sát nguồn ứng viên, profiling, kiểm chứng Hà Nội, quyết định nguồn #19; adapter thu thập ô nhiễm & khí tượng | #19, #3, #4 | **Bắt buộc** |
| **W3: Data Quality & Processing** | Kiểm toán 6 chiều chất lượng, khảo sát giả định cơ chế MCAR/MAR/MNAR, missing ngụy trang | #5 | **Bắt buộc** |
| **W4: Practical Cleaning** | Làm sạch tất định, logic $\text{PM}_{2.5} \le \text{PM}_{10}$, kẹt sensor, reindex theo trạm, Cleaning Log | #6 | **Bắt buộc** |
| **W5: Transformation & Integration** | Ghép nối tránh nổ dòng, đóng băng dữ liệu, split thời gian tuyến tính, Sklearn Pipeline fit trên Train, Parquet | #7 | **Bắt buộc** |
| **W6: Descriptive Statistics** | 4 họ chỉ số, hình dạng phân phối quyết định chỉ số, Pearson & Spearman, Anscombe check | #8 | **Bắt buộc** |
| **W7: Data Visualization** | Nguyên tắc Tufte (Data-ink), Cleveland ranking, SCQA storytelling, tiêu đề kết luận, quy chuẩn chu kỳ lấy mẫu | #9 | **Bắt buộc** |
| **W8: Midterm Project** | Báo cáo giữa kỳ 8–10 trang, slide thuyết trình 7 phút + 3 phút viva, gắn tag nộp bài | #10 | **Bắt buộc** |
| **W9: Statistical Inference** | Kiểm định Mann-Whitney U, so sánh quy chuẩn, báo cáo bộ bốn: Thống kê, $p$-value, Effect Size, 95% Bootstrap CI | #11 | **Bắt buộc** |
| **W10: Regression Analysis** | Hồi quy OLS, biến đổi mục tiêu ứng viên, chẩn đoán LINE, VIF, Cook's dist, điều hòa Ridge/Lasso trên Train | #12 | **Bắt buộc** |
| **W11: Classification & Features** | Dự báo cảnh báo ô nhiễm, đặc trưng trễ/trượt, xử lý imbalance, threshold tuning Train/Val, kiểm toán 4 dạng leakage | #13 | **Bắt buộc** |
| **W12: Big Data, Ethics & Bias** | Đo đạc tài nguyên thực tế vs Spark, kiểm toán 4 loại bias, lập Datasheet & Model Card, Project Charter | #14 | **Bắt buộc** |
| **W13: Code Refactoring & Mentoring** | Module hóa `src/`, phân tích độ nhạy ngưỡng kỹ thuật (40, 45, 50, 55 $\mu\text{g/m}^3$), theo dõi cố vấn | #15 | **Bắt buộc** |
| **W14: Storytelling & Final Report** | Báo cáo tổng thể SCQA, slide bảo vệ đồ án, 15 câu hỏi phản biện Viva | #16 | **Bắt buộc** |
| **W15: Final Defense & Audit** | Kiểm toán kỹ thuật toàn diện repo, kiểm chứng notebook sạch tự động, tag commit, bàn giao bảo vệ | #17 | **Bắt buộc** |

---

### C. Weekly Roadmap (Bảng Tóm tắt Lộ trình 15 Tuần)

| Week | Giai đoạn & Mục tiêu | Tasks chính | Deliverables | Issue sở hữu | Definition of Done |
|:---:|---|---|---|:---:|---|
| **W01** | **Khởi động & Chuẩn hóa**<br>Thiết lập chuẩn dự án CRISP-DM | Khởi tạo repo GitHub, file cấu trúc, `.gitignore`, môi trường `requirements.txt`, xác lập RQ và Canonical Schema | Repo GitHub skeleton, `README.md`, `docs/data_dictionary.md` | #1, #2 | Clone repo về máy sạch chạy `pip install` thành công 100%; Canonical Schema chuẩn hóa 100% các biến |
| **W02** | **Thẩm định & Thu thập**<br>Khảo sát nguồn và thu thập dữ liệu | Khảo sát hồ sơ đa nguồn, kiểm chứng Hà Nội & dải thời gian thực tế, ban hành quyết định nguồn; viết adapter thu thập ô nhiễm & khí tượng | `docs/source_profiling_decision.md`, script adapter, file raw data, `data/raw/metadata.json` | #19, #3, #4 | Quyết định nguồn hoàn tất trước khi thu thập; payload thô lưu trong `data/raw/` kèm SHA-256, xuất xứ và giấy phép |
| **W03** | **Kiểm toán Chất lượng**<br>Định lượng 6 chiều chất lượng | Viết hàm audit 6 chiều, bóc trần missing ngụy trang, khảo sát giả định cơ chế khuyết thiếu (MCAR/MAR/MNAR) | Notebook kiểm toán, báo cáo `docs/data_quality_audit.md` | #5 | Mọi chiều chất lượng đều có số liệu minh chứng định lượng; tính bất định cơ chế khuyết được ghi nhận rõ |
| **W04** | **Làm sạch Tất định**<br>Xử lý lỗi trạm và reindex theo trạm | Lọc $\text{PM}_{2.5} > \text{PM}_{10}$, xử lý kẹt sensor, gắn cờ sương mù độ ẩm cao, reindex chuỗi liên tục theo từng trạm, lập Cleaning Log | Notebook cleaning, file `docs/cleaning_log.md`, dữ liệu `data/interim/` | #6 | Không còn giá trị âm vô lý; reindex độc lập theo trạm bảo toàn cấu trúc dữ liệu; không điền khuyết toàn cục |
| **W05** | **Tích hợp & Pipeline**<br>Ghép nối an toàn và chống rò rỉ | Merge tránh nổ dòng, đóng băng dữ liệu, split thời gian tuyến tính, đóng gói Scikit-Learn Pipeline fit trên Train, xuất Parquet | File `air_pollution_final.parquet`, script `src/cleaning_pipeline.py` | #7 | Kiểm soát số dòng sau merge (`len <= len_air`); phân chia thời gian nghiêm ngặt; pipeline fit strictly trên Train |
| **W06** | **Thống kê Mô tả**<br>Xác lập hồ sơ 4 họ chỉ số & chu kỳ | Tính 4 họ chỉ số cho $\text{PM}_{2.5}$ & khí tượng, phân tích chu kỳ giờ/ngày/tháng/mùa từ số liệu thực tế, ma trận tương quan kép | Notebook EDA thống kê, bảng `reports/statistical_profile.csv` | #8 | 4 họ chỉ số đầy đủ; chứng minh khách quan lựa chọn Median/IQR dựa trên hình dạng phân phối thực nghiệm |
| **W07** | **Trực quan hóa Ấn phẩm**<br>Thiết kế 7 biểu đồ giải thích | Lập trình FIG-01 đến FIG-07 theo Tufte/Cleveland, đối chiếu ngưỡng quy chuẩn tương thích thời gian, viết tiêu đề kết luận | 7 biểu đồ PNG 300 DPI trong `figures/`, module `src/visualizer.py` | #9 | 100% biểu đồ có tiêu đề kết luận dẫn xuất từ dữ liệu; đường ngưỡng quy chuẩn tương thích về chu kỳ tính toán |
| **W08** | **MIDTERM MILESTONE**<br>Báo cáo & Thuyết trình giữa kỳ | Hoàn thiện báo cáo giữa kỳ SCQA 8–10 trang, slide thuyết trình 7 phút, kiểm chứng tái lập notebook W1–W3, gắn git tag | `reports/midterm_report.pdf`, slide deck, git tag `midterm-submission` | #10 | Báo cáo nộp đúng hạn; toàn bộ notebook Milestone 1–3 chạy Restart & Run All thành công không lỗi |
| **W09** | **Suy luận Thống kê**<br>Kiểm định giả thuyết có đối chứng | Chạy kiểm định phi tham số (mùa, ngày làm việc vs cuối tuần, quy chuẩn), tính Effect Size ($r_{rb}$) và 95% Bootstrap CI | Notebook inference, bảng tổng hợp kết quả kiểm định | #11 | 100% kết luận kiểm định có đủ bộ bốn: thống kê, $p$-value, Effect Size ($r_{rb}$) và 95% Bootstrap CI |
| **W10** | **Phân tích Hồi quy**<br>Hồi quy OLS & Chẩn đoán LINE | Fit OLS trên Train, chẩn đoán 4 giả định LINE trên phần dư, phân tích VIF, Cook's dist, điều hòa Ridge/Lasso trên Train | Notebook regression, biểu đồ chẩn đoán LINE, câu diễn giải $\beta$ phi nhân quả | #12 | Đánh giá độc lập trên Test; chẩn đoán đủ 4 giả định LINE; diễn giải $\beta$ chuẩn 3 nghĩa vụ, không ngụy biện nhân quả |
| **W11** | **Phân loại Cảnh báo**<br>Dự báo ngày ô nhiễm vượt ngưỡng | Tạo đặc trưng trễ/trượt, train Random Forest, tuning threshold theo mục tiêu vận hành trên Train/Val, kiểm toán rò rỉ | Notebook classification, đường cong PR, biên bản kiểm toán rò rỉ | #13 | Đánh giá trên Test độc lập bằng Recall, PR-AUC, Confusion Matrix; biên bản kiểm toán 4 dạng rò rỉ đạt chuẩn |
| **W12** | **Đạo đức, Quy mô & Charter**<br>Đo đạc tài nguyên & Định kiến | Đo đạc dung lượng đĩa, RAM, I/O vs Spark; khảo sát 4 giả thuyết bias; viết Datasheet, Model Card, Project Charter | `docs/datasheet.md`, `docs/model_card.md`, `docs/project_charter.md`, AI declaration | #14 | Lập luận Spark dẫn xuất từ số liệu đo đạc thực nghiệm; hoàn thành 100% checklist đạo đức và Project Charter |
| **W13** | **Refactor & Độ nhạy**<br>Module hóa code & Tiếp thu cố vấn | Đưa hàm dùng chung vào `src/`, phân tích độ nhạy ngưỡng kỹ thuật (40, 45, 50, 55 $\mu\text{g/m}^3$), lập bảng theo dõi feedback | Mã nguồn `src/`, tài liệu `docs/mentoring_feedback.md`, notebook dọn sạch | #15 | Import module độc lập không lỗi; phân tích độ nhạy dán nhãn kỹ thuật minh bạch; 100% góp ý được truy vết đối chiếu |
| **W14** | **Data Storytelling**<br>Soạn thảo Báo cáo & Slide cuối kỳ | Soạn thảo báo cáo đồ án cuối kỳ SCQA, thiết kế slide bảo vệ 10–12 phút, soạn 15 câu hỏi vấn đáp Viva | `reports/final_report.pdf`, slide bảo vệ, tài liệu `docs/viva_qa_prep.md` | #16 | Báo cáo hoàn chỉnh, bằng chứng thực nghiệm chặt chẽ, không có khẳng định nhân quả; slide và viva prep hoàn tất |
| **W15** | **FINAL DEFENSE & AUDIT**<br>Kiểm toán Repo & Bàn giao | Kiểm toán toàn diện repo, kiểm chứng tự động toàn bộ chuỗi notebook từ môi trường sạch, gắn tag chính thức, bảo vệ | Tag `final-defense-submission`, biểu mẫu `reports/defense_minutes.md` | #17 | 100% notebook thực thi tuần tự không lỗi unhandled exception; repo sạch, diff sạch, cấu trúc chuẩn mực |

---

### D. Research Pipeline (Sơ đồ Luồng Nghiên cứu Toàn diện)

Quy trình nghiên cứu đồ án tuân thủ nghiêm ngặt cấu trúc luồng phụ thuộc đơn hướng:
```text
#1 → #2 → #19 → {#3, #4} → #5 → #6 → #7 → #8 → #9 → #10 → #11 → #12 → #13 → #14 → #15 → #16 → #17
```

Chi tiết luồng thực hiện:

```text
[ GIAI ĐOẠN 1: THIẾT LẬP & THU THẬP NGUỒN DỮ LIỆU ]
  Khởi tạo Dự án & Môi trường CRISP-DM (#1)
       │
       ▼
  Xác lập Câu hỏi Nghiên cứu & Canonical Schema (#2)
       │
       ▼
  Khảo sát Hồ sơ Đa nguồn, Kiểm chứng Hà Nội & Quyết định Nguồn Dữ liệu (#19)
       │
       ├────────────────────────────────────────┐
       ▼                                        ▼
  Thu thập & Chuẩn hóa Dữ liệu Ô nhiễm (#3)   Thu thập & Đồng bộ Dữ liệu Khí tượng (#4)
       │                                        │
       └───────────────────┬────────────────────┘
                           ▼
[ GIAI ĐOẠN 2: CHẤT LƯỢNG, LÀM SẠCH & TIỀN XỬ LÝ CHỐNG RÒ RỈ ]
  Kiểm toán Chất lượng 6 Chiều & Phân loại Cơ chế Khuyết thiếu (#5)
       │
       ▼
  Làm sạch Tất định, Logic Vật lý, Reindex theo Trạm & Cleaning Log (#6)
       │
       ▼
  Tích hợp Ô nhiễm - Khí tượng, Đóng băng Dữ liệu, Split Thời gian & Pipeline (#7)
       │
       ▼
[ GIAI ĐOẠN 3: KHÁM PHÁ DỮ LIỆU (EDA) & BÁO CÁO GIỮA KỲ ]
  Thống kê Mô tả 4 Họ Chỉ số & Quy luật Chu kỳ Thời gian Đa tầng (#8)
       │
       ▼
  Bộ 7 Biểu đồ Ấn phẩm Giải thích FIG-01 đến FIG-07 (#9)
       │
       ▼
  MIDTERM MILESTONE: Báo cáo EDA Giữa kỳ, Slide SCQA & Tag Nộp bài (#10)
       │
       ▼
[ GIAI ĐOẠN 4: SUY LUẬN THỐNG KÊ & MÔ HÌNH HÓA ]
  Kiểm định Giả thuyết Phi tham số kèm Effect Size & Bootstrap CI (#11)
       │
       ▼
  Hồi quy Tuyến tính OLS với Chẩn đoán 4 Giả định LINE & Điều hòa (#12)
       │
       ▼
  Pipeline Phân loại Cảnh báo Ô nhiễm với Tối ưu Ngưỡng & Kiểm toán Rò rỉ (#13)
       │
       ▼
[ GIAI ĐOẠN 5: ĐẠO ĐỨC DỮ LIỆU, REFACTOR & BẢO VỆ ĐỒ ÁN ]
  Kiểm toán Định kiến, Phân tích Quy mô vs Spark, Datasheet, Model Card, Charter (#14)
       │
       ▼
  Module hóa Mã nguồn vào src/, Phân tích Độ nhạy & Tiếp thu Cố vấn (#15)
       │
       ▼
  Báo cáo Đồ án Cuối kỳ SCQA, Slide Thuyết trình & Tài liệu Vấn đáp Viva (#16)
       │
       ▼
  FINAL DEFENSE: Kiểm toán Toàn diện Repo, Kiểm chứng Notebook & Bàn giao (#17)
```

---

### E. Final Deliverables (Danh mục Sản phẩm Bàn giao Cuối cùng)
1. **Repository GitHub chuẩn mực [Issue #1, #15, #17]:**
   - Hoàn chỉnh cấu trúc thư mục CRISP-DM, mã nguồn module hóa trong `src/` (`data_loader.py`, `cleaning_pipeline.py`, `visualizer.py`).
   - Chuỗi notebooks đánh số thứ tự từ `00_` đến `06_`, bảo đảm chạy thông suốt từ đầu đến cuối không lỗi unhandled exception trong môi trường sạch.
   - File `requirements.txt` cố định phiên bản các thư viện tương thích Python 3.10+.
   - Git tag chính thức `midterm-submission` [Issue #10] và `final-defense-submission` [Issue #17].
2. **Bộ dữ liệu & Hồ sơ Quản trị [Issue #3, #4, #6, #7, #19]:**
   - Dữ liệu thô trong `data/raw/` được bảo toàn nguyên trạng kèm `metadata.json` ghi chép xuất xứ, tham số truy vấn, mã băm SHA-256 và giấy phép bản quyền; tệp thô không Git-track theo chính sách kho dữ liệu của repository (Mục 3.2).
   - Dữ liệu trung gian sau làm sạch tất định trong `data/interim/`.
   - Dữ liệu sạch hoàn chỉnh đóng băng lưu dạng Snappy Parquet `data/processed/air_pollution_final.parquet`.
   - `docs/data_dictionary.md` (Từ điển dữ liệu Canonical Schema) [Issue #2].
   - `docs/source_profiling_decision.md` (Báo cáo thẩm định & quyết định nguồn dữ liệu) [Issue #19].
   - `docs/cleaning_log.md` (Nhật ký làm sạch dữ liệu tất định) [Issue #6].
3. **Các Báo cáo Khoa học & Thẻ Chuẩn hóa [Issue #10, #14, #15, #16, #17]:**
   - **Báo cáo Giữa kỳ (Midterm EDA Report):** 8–10 trang PDF theo chuẩn Rubric môn học `reports/midterm_report.pdf` [Issue #10].
   - **Báo cáo Đồ án Cuối kỳ (Final Capstone Report):** Định dạng PDF hoàn chỉnh cấu trúc SCQA `reports/final_report.pdf` [Issue #16].
   - **Datasheet for Dataset (1 trang)** theo chuẩn Timnit Gebru `docs/datasheet.md` [Issue #14].
   - **Model Card (1 trang)** mô tả hiệu năng phân tầng và giới hạn mô hình `docs/model_card.md` [Issue #14].
   - **Project Charter** quy chuẩn `docs/project_charter.md` [Issue #14].
   - **Tài liệu theo dõi phản biện cố vấn** `docs/mentoring_feedback.md` [Issue #15].
   - **Tài liệu chuẩn bị vấn đáp Viva** (15 câu hỏi trọng tâm) `docs/viva_qa_prep.md` [Issue #16].
   - **Biểu mẫu biên bản đánh giá bảo vệ đồ án** `reports/defense_minutes.md` [Issue #17].
   - **Slide thuyết trình:** Bản trình chiếu Giữa kỳ (7 phút) và Cuối kỳ (10–12 phút).
4. **Bộ Biểu đồ Ấn phẩm & Bảng Thống kê [Issue #8, #9, #12, #13]:**
   - Thư mục `figures/` chứa đầy đủ 7 biểu đồ ấn phẩm giải thích (FIG-01 đến FIG-07, PNG 300 DPI), biểu đồ chẩn đoán LINE và đường cong PR.
   - Bảng hồ sơ thống kê 4 họ chỉ số `reports/statistical_profile.csv` [Issue #8].

---

### F. Risk Register (Bảng Quản trị Rủi ro Đồ án)

| Rủi ro tiềm ẩn | Xác suất | Tác động | Chiến lược Giảm thiểu (Mitigation) | Kế hoạch Dự phòng (Backup Plan) |
|---|:---:|:---:|---|---|
| **1. API bị lỗi mạng / Rate Limit hoặc thay đổi schema** | Trung bình | Cao | Thêm khoảng nghỉ `time.sleep()` giữa các request; lưu cache thô từng block xuống đĩa; adapter cách ly định dạng raw [Issue #3, #4] | Chuyển đổi sang nguồn dự phòng (Fallback) đã được phê duyệt trong ma trận quyết định nguồn [Issue #19] |
| **2. Tỷ lệ Missing Data tập trung trong các đợt thời tiết xấu** | Cao | Cao | Khảo sát hình thái khuyết thiếu, ghi nhận tính bất định cơ chế MAR/MNAR; không xóa dòng bừa bãi; tạo cờ `pm25_was_missing` [Issue #5, #6] | Đối chiếu dữ liệu trạm tham chiếu lân cận hoặc đưa vào phân tích giới hạn trong Datasheet/Model Card [Issue #14] |
| **3. Lệch múi giờ giữa dữ liệu ô nhiễm và khí tượng** | Trung bình | Cực cao | Ép kiểu `datetime` có nhận thức múi giờ, chuyển đổi đồng nhất về `Asia/Ho_Chi_Minh` (UTC+7) ngay tại adapter [Issue #3, #4, #6] | Viết assert test kiểm tra đỉnh nhiệt độ ngày luôn rơi vào khung giờ chiều thực tế [Issue #6] |
| **4. Lỗi bùng nổ số hàng khi Merge (Row Explosion)** | Thấp | Cực cao | Kiểm tra tính duy nhất của khóa quan sát `(station_id, timestamp)` hoặc `timestamp` trên cả hai bảng; kiểm tra `len(df_merged) <= len(df_air)` [Issue #7] | Dừng quy trình và kiểm tra lại khóa ghép nối nếu phát hiện số dòng sau merge vượt quá bảng gốc [Issue #7] |
| **5. Vi phạm giả định LINE trong mô hình Hồi quy OLS** | Cao | Trung bình | Khảo sát biến đổi logarit $Y = \log(1 + \text{PM}_{2.5})$, bổ sung biến trễ hợp lệ; thử nghiệm Ridge/Lasso [Issue #12] | Báo cáo trung thực vi phạm giả định và giới hạn của mô hình OLS trong báo cáo cuối kỳ, không ngụy biện [Issue #12, #16] |
| **6. Rò rỉ dữ liệu chuỗi thời gian (Data Leakage)** | Trung bình | Cực cao | Phân chia Train/Test theo thời gian tuyến tính sau khi đóng băng dữ liệu; fit Scaler/Imputer strictly trên Train qua Scikit-Learn Pipeline [Issue #7, #13] | Thực hiện kiểm toán độc lập 4 dạng rò rỉ dữ liệu và lập biên bản trước khi đánh giá cuối cùng [Issue #13] |
| **7. Ôm đồm kiến trúc phức tạp không cần thiết (Spark / Deep Learning)** | Trung bình | Cao | Đo đạc tài nguyên thực tế để đánh giá khách quan nhu cầu Spark [Issue #14]; kiên quyết loại bỏ Deep Learning dạng hộp đen khỏi đồ án | Tập trung tối đa vào độ sâu phân tích EDA, tính chặt chẽ của giả định thống kê và khả năng giải trình mô hình |

---

## 13.G. SNAPSHOT TRẠNG THÁI TRIỂN KHAI (IMPLEMENTATION STATUS SNAPSHOT)

> **Ngày chốt snapshot:** 2026-09-29 · **Phạm vi:** Milestone 1 (Issue #1, #2, #19, #3, #4).
> Đây là ảnh chụp trạng thái tại thời điểm kiểm toán, **không phải** kế hoạch. Trạng thái
> được đối chiếu với bằng chứng thực tế (mã nguồn, test, artifact dữ liệu, metadata,
> notebook, CI, tài liệu), **không** dựa vào việc pull request đã được merge hay issue
> đã được đóng.

### G.1. Bản đồ phụ thuộc thực tế

```text
                   [ #19  SOURCE DECISION GATE ]
                    profiling → Hanoi validation
                    → temporal coverage → decision matrix
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   [ #3  AIR QUALITY ]              [ #4  WEATHER ]
   OpenAQ 4946811 (AWS S3)          Open-Meteo ERA5 (PRIMARY)
   AirNow DOS Hanoi                  NOAA ISD 48820 (FALLBACK, chưa kích hoạt)
   nạp thô → canonical AQ           tiêu thụ timeline canonical của #3
   làm sạch → kiểm định AQ          nạp thô → canonical WX
   kiểm định địa lý Hà Nội          làm sạch → kiểm định WX + địa lý
              │                               │
              │        THIẾT KẾ & HIỆN THỰC HÓA SONG SONG
              │        (thực thi pipeline: #3 chạy trước #4)
              └───────────────┬───────────────┘
                              ▼
              [ #5  QUALITY AUDIT 6 CHIỀU ]
              đọc data/interim/*.parquet — đo lường, không sửa dữ liệu
                              ▼
              [ #6  DETERMINISTIC CLEANING ]
              cleaning log, giải quyết giá trị kẹt, reindex theo trạm
                              ▼
              [ #7  MERGE / DATASET FREEZE / SPLIT / PIPELINE ]
              ghép AQ + WX → đóng băng → phân chia thời gian → Parquet
                              ▼
        [ #8 EDA ] → [ #9 FIGURES ] → [ #10 MIDTERM ]
                              ▼
        [ #11 INFERENCE ] → [ #12 OLS/LINE ] → [ #13 CLASSIFICATION ]
                              ▼
                    [ #14 → #15 → #16 → #17 ]
```

**Quy tắc phụ thuộc:**
- `#3` và `#4` **có thể phát triển song song** sau `#19`; nhưng khi *thực thi*, `#4` phải
  tiêu thụ chuỗi thời gian canonical từ `#3`. Cơ chế đồng bộ thời gian động đã hiện
  thực hóa tại PR #25 — `#4` chỉ tiêu thụ, không hiện thực hóa lại.
- `#5`, `#6`, `#7` **tiêu thụ artifact đã có** trong `data/interim/`. Không issue nào trong
  chuỗi hậu-Milestone-1 yêu cầu thu thập hoặc chuẩn hóa lại dữ liệu.
- `#7` là nơi **duy nhất** thực hiện phép ghép AQ + WX và tạo tập dữ liệu đặc trưng.

### G.2. Trạng thái từng Issue của Milestone 1

| Issue | Phạm vi | Hiện thực trạng | Bằng chứng | Trạng thái | Khoảng trống còn lại |
|:---:|---|---|---|:---:|---|
| #1 | Khởi tạo repo, môi trường, `.gitignore` | Cấu trúc CRISP-DM, `requirements.txt`, notebook `00_environment_test.ipynb` | Repo khởi tạo, CI cài đặt thành công | **DONE** | — |
| #2 | Câu hỏi nghiên cứu + Canonical Schema | `docs/research_questions.md`, `docs/data_dictionary.md` | Từ điển định nghĩa 6 trường khí tượng + ranh giới vật lý tại §4.3 | **DONE** | — |
| #19 | Cổng quyết định nguồn | `docs/source_profiling_decision.md`, `data/raw/metadata.json` | Ma trận đa tiêu chí §12.2; vai trò nguồn ghi trong metadata | **DONE** | Không có. Quyết định nguồn giữ nguyên, không bị đảo ngược |
| #3 | Pipeline chất lượng không khí | `OpenAQAdapter` trong `src/data_collection.py` | 8.022 bản ghi canonical, tz `Asia/Ho_Chi_Minh`, mã băm SHA-256 trong metadata | **DONE** | Adapter AirNow DOS chưa thực thi (cần thông tin xác thực AirNow-Tech) |
| #4 | Pipeline khí tượng + đồng bộ thời gian | `OpenMeteoAdapter`, `validate_weather_canonical` | 9.072 bản ghi/giờ, 0 trùng lặp, 0 khoảng trống, 0 khuyết thiếu; PR #26 đã merge | **DONE** | — |
| #5 | Kiểm toán chất lượng 6 chiều | `src/data_quality.py`, `docs/data_quality_audit.md`, `notebooks/02_quality_audit.ipynb` | PR #27 đã merge; `docs/data_quality_audit.md` đã hiệu chỉnh theo dữ liệu thực tế trên đĩa | **DONE** | — |
| #6 | Làm sạch tất định, cleaning log | `src/cleaning.py`, `docs/cleaning_log.md`, `notebooks/03_data_cleaning.ipynb` | 9.044 dòng ô nhiễm + 9.072 dòng khí tượng canonical; `assert_no_imputation()` PASS; 107 unit test | **DONE** | Việc chạy lại `03_data_cleaning.ipynb` cần khôi phục `data/interim/` từ `data/raw/` trước |
| #7 | Ghép dữ liệu, đóng băng, split, pipeline | `src/cleaning_pipeline.py`, `notebooks/03_transformation_pipeline.ipynb` | 9/9 AC + 2 validation PASS; `data/processed/air_pollution_final.parquet` 9.044×18; 72 unit test; mutation score 21/21 = 100% | **DONE (chưa merge)** | Nằm trên nhánh `feat/issue-6-deterministic-cleaning`, **chưa merge vào `main`** — xem [cảnh báo mốc cắt](#bang-ghi-chinh-thuc--cac-quyet-dinh-da-chot-cho-issue-7) về `2026-01-01` |

### G.3. Kết luận trạng thái Milestone 1

> [!IMPORTANT]
> **Milestone 1 đã đóng.** Trạng thái thực tế: **5/5 issue DONE** (`#1`, `#2`, `#19`, `#3`, `#4`).
>
> - `#4` đã hoàn tất: PR #26 **đã merge vào `main`**, toàn bộ tiêu chí nghiệm thu
>   AC4-1 → AC4-20 đã được tick sau khi AC được chuẩn hóa theo chính sách ba tầng (Mục 3.2).
> - **Milestone 2:** `#5` (kiểm toán chất lượng 6 chiều) **DONE** qua PR #27;
>   `#6` (làm sạch tất định + cleaning log) và `#7` (ghép dữ liệu, đóng băng, split,
>   pipeline) đều **đã triển khai** và đã vượt qua 259 unit test + kiểm chứng AC 9/9.
>   Cả hai nằm trên nhánh `feat/issue-6-deterministic-cleaning`, **chưa merge vào
>   `main`**. Các issue phụ thuộc (`#8`, `#11`, `#12`, `#13`) bị chặn cho tới khi nhánh đó được merge.
> - Các số liệu thực nghiệm nêu trong các báo cáo (#4, #5) là **kết quả của một lần thực thi cụ thể**
>   trên tập dữ liệu hiện tại, **không phải** bảo đảm của pipeline cho mọi lần chạy tương lai.
> - Bộ kiểm thử hiện gồm **57 + 14 + 107 + 38 + 34 + 9 = 259 unit test tất định**,
>   tất cả PASS (`test_data_collection` + `test_data_quality` + `test_cleaning` +
>   `test_cleaning_pipeline` + `test_cleaning_pipeline_guards` + `test_fetch_dataset`).
>   Trong đó 34 test hồi quy của #7 **FAIL trên bản gốc** và PASS sau khi sửa, và
>   mutation score của `src/cleaning_pipeline.py` là **21/21 = 100%**.

> [!WARNING]
> **Khoảng trống độ phủ thời gian (DATA COVERAGE GAP) — chưa được giải quyết, cần theo dõi ở M2:**
> Khung thời gian mục tiêu của dự án là **2023-01-01 → 2024-12-31** (`temporal_coverage` trong
> `data/raw/metadata.json`), nhưng tập dữ liệu vận hành thực tế chỉ phủ **2025-07-03 → 2026-07-15**,
> vì trạm OpenAQ `4946811` chỉ được tích hợp lưu trữ từ 07/2025. Việc mở rộng phủ về 2023–2024
> phụ thuộc nguồn dữ liệu lịch sử (AirNow DOS cần thông tin xác thực của tổ chức/State Dept) và
> **không được giải quyết bằng cách tự tạo hoặc nội suy dữ liệu**. Khung nghiên cứu **không** bị
> thay đổi để làm pipeline chạy; khoảng trống này được ghi nhận minh bạch và chuyển giao cho M2.

---

## 14. LỘ TRÌNH THỰC HIỆN CHI TIẾT TỪNG TUẦN (WEEK 1 ĐẾN WEEK 15)

### Week 01 – Khởi động Dự án, Xác lập Nghiên cứu & Canonical Schema
* **Phân loại tuần:** Học / Chuẩn bị & Kickoff.
* **Mục tiêu tuần:** Thiết lập môi trường lập trình chuẩn mực, khởi tạo GitHub repository theo cấu trúc khuyến nghị CRISP-DM; xác lập câu hỏi nghiên cứu không thiên kiến và chuẩn hóa lược đồ Canonical Schema trung lập nguồn.
* **Kiến thức INFO3020 áp dụng:** Slide W1 – Ba trụ cột Data Science, Vòng đời 6 bước CRISP-DM, 4 vai trò nhóm dữ liệu, Quy tắc dữ liệu thô & provenance (`data/raw/`), Quy ước nộp bài qua GitHub; Slide W2 – Data Dictionary & I/O.
* **Mã Issue sở hữu:** **#1, #2**.
* **Tasks chi tiết:**
  1. Khởi tạo repository GitHub `air-pollution-analysis`, thiết lập khung cây thư mục chuẩn: `data/raw/`, `data/interim/`, `data/processed/`, `notebooks/`, `src/`, `figures/`, `reports/`, `docs/` [Issue #1].
  2. Tạo file `.gitignore` nghiêm ngặt (chặn tracking dữ liệu thô, binary cache, virtual environment).
  3. Thiết lập môi trường ảo Python 3.10+, cố định phiên bản các thư viện trong `requirements.txt`.
  4. Xây dựng notebook `notebooks/00_environment_test.ipynb` kiểm thử tự động toàn bộ thư viện cốt lõi, kiểm tra I/O Parquet và Scikit-Learn Pipeline [Issue #1].
  5. Soạn thảo `README.md` với cam kết liêm chính học thuật, phân công vai trò thành viên và tuyên bố mức độ sử dụng AI [Issue #1].
  6. Xác lập Main RQ và 4 Sub-questions (SQ1–SQ4) tuân thủ tính khách quan khoa học, không giả định kết quả [Issue #2].
  7. Thiết lập bảng đặc tả Canonical Schema trung lập nguồn và biên soạn `docs/data_dictionary.md` định nghĩa 8 thuộc tính chuẩn [Issue #2].
* **Deliverables:** Repo GitHub skeleton, file `requirements.txt`, notebook `00_environment_test.ipynb`, `README.md`, tài liệu `docs/data_dictionary.md`.
* **Definition of Done:** Bất kỳ thành viên nào clone repo về máy sạch, chạy `pip install -r requirements.txt` đều kích hoạt kernel Jupyter thành công; `docs/data_dictionary.md` định nghĩa đầy đủ 100% các biến trong Canonical Schema.
* **Dependencies:** Không.

---

### Week 02 – Khảo sát Hồ sơ Đa nguồn, Quyết định Nguồn & Pipeline Thu thập
* **Phân loại tuần:** Thẩm định Nguồn & Thu thập Dữ liệu.
* **Mục tiêu tuần:** Thực hiện khảo sát hồ sơ dữ liệu đa nguồn (Kaggle, OpenAQ, Open-Meteo, AirNow, PAM Air,...), kiểm chứng phạm vi Hà Nội và độ bao phủ thời gian thực tế, ban hành quyết định nguồn tại Issue #19; hiện thực hóa các adapter thu thập và chuẩn hóa dữ liệu ô nhiễm không khí và khí tượng theo quyết định nguồn được duyệt.
* **Kiến thức INFO3020 áp dụng:** Slide W2 – 4 con đường lấy dữ liệu, REST API (Headers, Pagination, Rate limits), Múi giờ UTC vs Local, Data Provenance, Ưu thế của định dạng Parquet, 6 câu hỏi I/O bắt buộc của Pandas.
* **Mã Issue sở hữu:** **#19, #3, #4** (Luồng: `#19 → {#3, #4}`).
* **Tasks chi tiết:**
  1. Tiến hành profiling khách quan danh mục nguồn ứng viên: đo lường số dòng, số cột, tần suất đo, missingness, duplicates, kiểm tra tính khả dụng của PM2.5, PM10 và các biến thời tiết [Issue #19].
  2. Kiểm chứng phạm vi địa lý: thiết lập bộ lọc không gian bảo đảm toàn bộ quan sát thuộc địa giới hành chính Hà Nội [Issue #19].
  3. Đo đạc mốc thời gian thực tế (min, max, latest timestamp có thể truy xuất); không áp đặt khung thời gian cứng [Issue #19].
  4. Lập ma trận so sánh đa tiêu chí và ban hành quyết định phân định vai trò nguồn (Primary, Secondary, Reference, Fallback, Unused) trong `docs/source_profiling_decision.md` [Issue #19].
  5. Xây dựng adapter thu thập/chuẩn hóa dữ liệu chất lượng không khí trong `src/data_collection.py` theo nguồn ô nhiễm được duyệt, bảo toàn đơn vị quan trắc `(station_id, timestamp)` [Issue #3].
  6. Xây dựng adapter thu thập/chuẩn hóa dữ liệu khí tượng bề mặt trong `src/data_collection.py` theo nguồn khí tượng được duyệt [Issue #4].
  7. Ghi payload thô nguyên bản vào `data/raw/` khi pipeline thực thi và cập nhật metadata, xuất xứ, mã băm SHA-256, giấy phép vào `data/raw/metadata.json` theo **Chính sách ba tầng** tại Mục 3.2 [Issue #3, #4].
  8. Kiểm thử quy trình nạp và ánh xạ Canonical Schema qua notebook `notebooks/01_data_collection.ipynb`.
* **Deliverables:** Tài liệu `docs/source_profiling_decision.md`, module adapter trong `src/`, notebook `01_data_collection.ipynb`, tệp dữ liệu thô trong `data/raw/`, `data/raw/metadata.json`.
* **Definition of Done:** Báo cáo quyết định nguồn hoàn thành và phê duyệt trước khi thu thập; payload thô được ghi dưới `data/raw/` khi pipeline chạy, giữ nguyên nội dung, có mã băm SHA-256 khớp tệp trên đĩa cùng metadata xuất xứ và giấy phép; ánh xạ thành công sang Canonical Schema.
* **Dependencies:** Hoàn thành Week 01 (#1, #2).

---

### Week 03 – Kiểm toán Chất lượng Dữ liệu & Phân loại Cơ chế Khuyết thiếu
* **Phân loại tuần:** Kiểm toán Chất lượng Dữ liệu.
* **Mục tiêu tuần:** Đo lường định lượng chất lượng chuỗi dữ liệu Canonical Schema theo 6 chiều kích thước quốc tế; nhận diện missing ngụy trang và khảo sát các giả thuyết cơ chế khuyết thiếu (MCAR/MAR/MNAR) dựa trên số liệu thực tế.
* **Kiến thức INFO3020 áp dụng:** Slide W3 – 6 Chiều chất lượng (Completeness, Accuracy, Consistency, Validity, Uniqueness, Timeliness), 3 cấp độ lỗi dữ liệu (Value, Record, Relationship), Missing ngụy trang ("-999", "None"), Cơ chế khuyết thiếu Rubin (MCAR, MAR, MNAR), Quy luật chi phí chất lượng 1–10–100.
* **Mã Issue sở hữu:** **#5**.
* **Tasks chi tiết:**
  1. Xây dựng hàm kiểm toán tự động `audit_dataframe(df)` trong `src/` hoặc notebook `notebooks/02_quality_audit.ipynb`, báo cáo chi tiết: dtypes, missing count, missing pct, nunique, min, max, quantiles, duplicate keys [Issue #5].
  2. Rà soát phát hiện toàn bộ chuỗi missing ngụy trang (`"-999"`, `"N/A"`, `"null"`, `"0.00"` kéo dài do sensor lỗi) [Issue #5].
  3. Lập bảng đánh giá định lượng kèm minh chứng số liệu thực tế cho cả 6 chiều chất lượng dữ liệu [Issue #5].
  4. Khảo sát hình thái khuyết thiếu, mẫu hình phân bố và sự cụm hóa theo thời gian; phân tích các cơ chế MCAR, MAR, MNAR dưới dạng các giả định chẩn đoán và ghi nhận tính bất định nếu chưa đủ bằng chứng [Issue #5].
  5. Soạn thảo Báo cáo Kiểm toán Chất lượng Dữ liệu `docs/data_quality_audit.md` [Issue #5].
* **Deliverables:** Hàm kiểm toán `audit_dataframe(df)`, notebook `02_quality_audit.ipynb`, báo cáo `docs/data_quality_audit.md`.
* **Definition of Done:** Báo cáo kiểm toán hoàn tất với số liệu định lượng cho 6 chiều chất lượng; toàn bộ missing ngụy trang được phát hiện; cơ chế khuyết thiếu được phân tích khoa học không võ đoán. Tuyệt đối không xóa dòng hay điền khuyết trong tuần này.
* **Dependencies:** Dữ liệu thô và Canonical Schema từ Week 02 (#3, #4).

---

### Week 04 – Làm sạch Tất định & Lập Cleaning Log
* **Phân loại tuần:** Làm sạch Dữ liệu Thực chiến (Deterministic Cleaning).
* **Mục tiêu tuần:** Thực hiện làm sạch tất định ở các cấp độ giá trị, bản ghi và quan hệ; thực thi logic vật lý và nhận diện lỗi cảm biến; reindex chuỗi thời gian liên tục theo từng trạm quan trắc; bảo đảm không thực hiện bất kỳ bước điền khuyết phụ thuộc dữ liệu nào trước khi chia tập; ghi chép chi tiết Cleaning Log.
* **Kiến thức INFO3020 áp dụng:** Slide W3 & W4 – Bẫy xóa dòng (`dropna`), Bẫy điền trung bình toàn cục, Reindex chuỗi thời gian, Cột chỉ báo khuyết thiếu (*Missing indicator*), Ràng buộc vật lý hạt bụi, Quy tắc bảo toàn outlier thực tế.
* **Mã Issue sở hữu:** **#6**.
* **Tasks chi tiết:**
  1. Chuẩn hóa múi giờ đồng nhất về `Asia/Ho_Chi_Minh` (UTC+7) và sắp xếp tăng dần theo thời gian [Issue #6].
  2. Khử trùng lặp tại đúng đơn vị quan trắc: khóa `(station_id, timestamp)` hoặc `timestamp` [Issue #6].
  3. Reindex chuỗi thời gian theo lưới 1 giờ liên tục (`freq='h'`) độc lập cho từng trạm quan trắc (`groupby('station_id')` nếu đa trạm); các khoảng trống giữ nguyên dạng `NaN` [Issue #6].
  4. Thực thi ràng buộc logic vật lý: Chuyển các giá trị vi phạm $\text{PM}_{2.5} > \text{PM}_{10} + \epsilon$ thành `NaN` (khi có trường `pm10`) [Issue #6].
  5. Lọc bỏ các giá trị âm phi lý ($	ext{PM}_{2.5} < 0$, tốc độ gió âm) [Issue #6].
  6. Xử lý lỗi cảm biến: Chuyển các chuỗi giá trị kẹt không đổi suốt $> 6$ giờ thành `NaN`; gắn cờ cảnh báo sương mù độ ẩm cao `is_high_humidity_fog = 1` khi $\text{RH} > 90\%$ (không xóa dòng) [Issue #6].
  7. Tạo cờ chỉ báo khuyết thiếu `pm25_was_missing = 1` cho các khoảng khuyết lớn $> 6$ giờ liên tiếp [Issue #6].
  8. Lưu dữ liệu trung gian sau làm sạch tất định vào `data/interim/` và ghi chép chi tiết vào `docs/cleaning_log.md` [Issue #6].
* **Deliverables:** Notebook `03_data_cleaning.ipynb`, tài liệu `docs/cleaning_log.md`, tập dữ liệu trung gian trong `data/interim/`.
* **Definition of Done:** Không còn giá trị âm hay mâu thuẫn vật lý; reindex chuỗi liên tục bảo toàn cấu trúc trạm; không chứa bất kỳ phép điền khuyết hay tính toán thống kê toàn cục nào; file `docs/cleaning_log.md` ghi nhận 100% các phép biến đổi kèm số dòng bị ảnh hưởng.
* **Dependencies:** Báo cáo kiểm toán từ Week 03 (#5).

---

### Week 05 – Tích hợp Dữ liệu, Đóng băng & Đóng gói Pipeline Chống Rò rỉ
* **Phân loại tuần:** Tích hợp Dữ liệu & Pipeline Tiền xử lý.
* **Mục tiêu tuần:** Ghép nối dữ liệu chất lượng không khí và khí tượng theo khóa quan sát không gây bùng nổ số hàng; đóng băng tập dữ liệu sạch; thiết lập phân chia Train/Test theo chuỗi thời gian tuyến tính dựa trên dữ liệu thực nghiệm; đóng gói Scikit-Learn Pipeline tiền xử lý huấn luyện strictly trên Train; lưu dữ liệu sạch ra định dạng Snappy Parquet.
* **Kiến thức INFO3020 áp dụng:** Slide W5 – Chuẩn hóa thang đo (RobustScaler), Biến đổi logarit ứng viên (`np.log1p`), Lỗi bùng nổ số hàng khi Merge (*Row Explosion Bug*), Đóng gói `ColumnTransformer` & `Pipeline`, Nguyên tắc chống rò rỉ dữ liệu (*Leakage Prevention*).
* **Mã Issue sở hữu:** **#7**.
* **Tasks chi tiết:**
  1. Kiểm tra tính duy nhất của khóa quan sát trên từng bảng; thực hiện phép nối `merge` an toàn kèm kiểm tra đối chứng: `assert len(df_merged) <= len(df_air)` để triệt tiêu hoàn toàn lỗi Row Explosion [Issue #7].
  2. **Đóng băng tập dữ liệu (Dataset Freeze):** Chốt tập dữ liệu sau làm sạch tất định, xác định chính xác số lượng bản ghi và dải thời gian thực tế [Issue #7].
  3. **Phân chia chuỗi thời gian (Chronological Split):** Xác định điểm cắt thời gian khách quan ($T_{\text{train}} < T_{\text{test}}$) dựa trên độ bao phủ thực tế, kích thước mẫu, tính liên tục và tính đại diện theo mùa; không áp đặt tỷ lệ cố định; nghiêm cấm chia ngẫu nhiên [Issue #7].
  4. Khảo sát biến đổi mục tiêu ứng viên $Y = \log(1 + \text{PM}_{2.5})$ trên tập Train, kiểm chứng qua chẩn đoán sau khớp [Issue #7].
  5. Xây dựng Scikit-Learn `Pipeline` kết hợp `ColumnTransformer`: Biến số học điền khuyết (`SimpleImputer(strategy='median')`) và chuẩn hóa (`RobustScaler()`), fit strictly trên Train [Issue #7].
  6. Áp dụng pipeline đã fit trên Train để transform cho cả tập Train và Test [Issue #7].
  7. Xuất tập dữ liệu sạch hoàn chỉnh ra định dạng Snappy Parquet: `data/processed/air_pollution_final.parquet` và module hóa `src/cleaning_pipeline.py` [Issue #7].
* **Deliverables:** File dữ liệu sạch `data/processed/air_pollution_final.parquet`, module `src/cleaning_pipeline.py`, notebook `03_transformation_pipeline.ipynb`.
* **Definition of Done:** Số dòng sau merge được kiểm soát (`assert len <= len_air`); tập dữ liệu được đóng băng; phân chia thời gian tuyến tính không rò rỉ; Pipeline fit duy nhất trên Train; tệp Parquet đọc lại nguyên vẹn cấu trúc và kiểu dữ liệu.
* **Dependencies:** Dữ liệu làm sạch tất định từ Week 04 (#6).

#### Bản ghi chính thức — Các quyết định đã chốt cho Issue #7

Ba quyết định dưới đây được chốt trên dữ liệu thực nghiệm (9044 quan sát giờ, `station_id = VN001_HANOI_556_NGUYEN_VAN_CU` tại 556 Nguyễn Văn Cừ, Hà Nội, 2025-07-03 → 2026-07-15) chứ không phải từ tỷ lệ quy ước. Bằng chứng đầy đủ nằm trong `notebooks/03_transformation_pipeline.ipynb` mục 5.

**Quyết định 1 — Điểm cắt Train/Test = `2026-01-15 00:00:00+07:00`.**

> **Đây là lựa chọn phương pháp luận phù hợp với dữ liệu hiện có, KHÔNG phải tối ưu
> tuyệt đối.** Xem *Hạn chế đã biết* ngay dưới bảng so sánh.

Căn cứ: **temporal representativeness + event coverage**, theo đúng task 3 của tuần này. Dữ liệu chỉ có **một chu kỳ mùa** (07/2025–07/2026) nên mọi tỷ lệ chia theo số dòng đều hỏng:

| Điểm cắt | Train/Test | `train_gio>100` | `test_gio>100` | Tỉ lệ trong Test | $p90_{test}/p90_{train}$ |
|---|---|---|---|---|---|
| `2026-05-01` (80/20) | 79,9 / 20,1 | 388 | **6** | 0,33% | 0,66 |
| `2026-03-24` (70/30) | 69,8 / 30,2 | 371 | 23 | 0,84% | 0,69 |
| `2026-02-15` (60/40) | 60,0 / 40,0 | 364 | 30 | 0,83% | 0,66 |
| **`2026-01-15` (đã chọn)** | **51,8 / 48,2** | 295 | **99** | **2,27%** | 0,80 |
| `2026-01-01` | 48,1 / 51,9 | 213 | 181 | 3,85% | **0,97** |

Cột cuối là **tỷ lệ p90 Test/Train** — đo trực tiếp *temporal representativeness*: càng gần `1.00` càng giống. Với 80/20, Test có 6 giờ vượt 100 µg/m³ trong 1818 giờ → mô hình đoán "không cảnh báo" cho mọi giờ vẫn đạt ~99,7% accuracy. Đó là **Accuracy Trap** mà `.agents/rules/analysis.md` cấm, và làm Recall / PR-AUC ở Issue #11–#13 mất hết ý nghĩa.

> [!IMPORTANT]
> **Đã chốt: giữ `2026-01-15`. Không đổi sang `2026-01-01`.**
>
> **Lý do — tính đại diện theo thời gian.** Mốc `2026-01-15` cắt **giữa mùa đông**, nên **cả Train lẫn Test đều chứa giai đoạn mùa đông**. Điều này quyết định vì tập dữ liệu hiện chỉ có **đúng một chu kỳ mùa** (07/2025–07/2026): nếu Test chỉ chứa một mùa mà Train chưa từng trải qua, mọi kết quả ở Issue #11–#13 sẽ đo trên phép dịch phân phối chứ không phải trên cùng một thế giới khí quyển.
>
> **Đây là lựa chọn phương pháp luận phù hợp với dữ liệu hiện có — KHÔNG phải tối ưu tuyệt đối.** Nó **không** phải mốc cắt điểm cao nhất trên mọi tiêu chí, và không nên được mô tả như vậy.
>
> **Hạn chế đã biết, ghi lại để Issues #11–#13 cân nhắc:**
>
> | Hạn chế | Số liệu |
> |---|---|
> | Mốc `2026-01-01` có event coverage cao hơn | `test_gio>100` 181 so với 99 |
> | Mốc `2026-01-01` có $p90$ ratio gần 1 hơn | 0,97 so với 0,80 |
> | Tỷ lệ nhãn nặng ở Test thấp hơn Train khoảng **2,8 lần** | Test 2,27% so với Train 6,30% |
>
> Hệ quả cụ thể: **có dịch chuyển tỷ lệ lớp giữa Train và Test**. Khi đánh giá mô hình ở Issue #11–#13, Recall và PR-AUC phải được diễn giải cẩn thận với sự dịch chuyển này; nếu cần, có thể báo cáo thêm chỉ số trên một tập con Test đã cân bằng nhãn. Việc chốt lại mốc cắt **không thuộc phạm vi Issue #7** và chỉ nên xem xét khi có thêm một chu kỳ mùa nữa trong dữ liệu.

**Vì sao giữ CẢ HAI phép kiểm tra số dòng (`<=` và `==`).**

Issue #7 §Yêu cầu kỹ thuật và AC1 chỉ định `assert len(df_merged) <= len(df_air)`. Phép này được **giữ nguyên** để không lệch khỏi tiêu chí nghiệm thu. Nhưng với `how="left"` + khoá unique hai phía + `validate="1:1"`, `<=` là **điều kiện cần mà không phân biệt được** — nó luôn đúng và không bắt được lỗi nào. Vì vậy `merge_air_weather()` kiểm tra **cả hai**:

| Phép | Vai trò | Bắt được gì |
|---|---|---|
| `len(df_merged) <= len(df_air)` | **Giữ nguyên theo AC1** | Điều kiện cần: không được sinh thêm dòng |
| `len(df_merged) == len(df_air)` | **Bất biến thật của pipeline** | Không được **mất** dòng ô nhiễm nào |

**Cơ sở của bất biến `==`.** Theo định nghĩa của Issue #7, phép ghép là `merge(how="left")` theo khoá quan sát: **mọi dòng của bảng ô nhiễm đều được giữ lại**. Nếu một giờ không có bản ghi khí tượng tương ứng thì dòng ô nhiễm đó vẫn còn, chỉ mang `NaN` ở các cột khí tượng — đó chính là hành vi được `SimpleImputer` xử lý sau đó, chứ không phải lý do để xoá dòng. Pipeline này **không được phép loại bỏ air row trong bất kỳ trường hợp hợp lệ nào**, nên `==` là bất biến đúng.

**Nếu trong tương lai pipeline được phép loại air row** (ví dụ thêm bước loại quan sát không đạt kiểm định chất lượng trước khi freeze), thì bất biến trở thành `len(df_merged) <= len(df_air)` và phép `==` **phải được nới lỏng** — kèm ghi chú lý do trong mã. Đó là lý do hai phép cùng tồn tại thay vì một phép bị xoá: phép `==` gắn với *định nghĩa hiện tại* của pipeline, và sẽ tự báo động nếu định nghĩa đó đổi.

Cắt giữa mùa đông là cách để **cả hai** tập đều chứa regime ô nhiễm:

```
cut   = 2026-01-15 00:00:00+07:00
train = 4.682 dòng (51,8%)   test = 4.362 dòng (48,2%)
train: 1.425 giờ > 50,  295 giờ > 100
test :   878 giờ > 50,   99 giờ > 100
tổng 394 giờ > 100  →  Train 74,9% | Test 25,1%
```

Tỷ lệ 51,8/48,2 trông "lệch chuẩn" nhưng là **hệ quả tất yếu** của việc chia theo mùa, không phải lựa chọn tùy tiện.

**Quyết định 2 — `log1p` chỉ chẩn đoán, KHÔNG transform target.**

Đo trên Train ($n = 4.279$ quan sát có $\text{PM}_{2.5}$): skew $1{,}148 \to -0{,}656$, kurtosis $1{,}068 \to 0{,}726$. Task 4 của tuần này chỉ yêu cầu *khảo sát*, không yêu cầu áp dụng. Giữ target ở µg/m³ để ngưỡng cảnh báo còn nghĩa trực tiếp với bối cảnh chất lượng không khí và phần downstream dễ đọc hơn.

**Quyết định 3 — Trong 3 cột cờ chẩn đoán của Issue #5/#6, chỉ 2 cột được làm feature; `pm25_was_missing` bị loại vì là rò rỉ target theo cấu trúc.**

| cột | nunique | tổng | nghĩa | làm feature? |
|---|---|---|---|---|
| `pm25_was_missing` | 2 | 1.289 | trạm ngừng báo cáo (khối khuyết $> 6$ giờ) | ❌ **không** |
| `pm25_was_stuck` | **1** | **0** | cảm biến kẹt — **hằng số trên tập này** | ✅ có |
| `is_high_humidity_fog` | 2 | 2.834 | sương mù quang học, cảm biến đọc sai | ✅ có |

**Vì sao loại `pm25_was_missing`.** Nó là `pm25.isna()` **với ngưỡng khối khuyết $> 6$ giờ**. Mà `SimpleImputer(strategy="median")` lại điền median cho **đúng những hàng đó**. Hệ quả: mọi hàng `flag == 1` có target bằng **đúng** median của tập học — đo trên dữ liệu thật là **100%**, ở cả Train (256/256, median 37,83) lẫn Test (1.033/1.033). Mô hình học được quy tắc `flag == 1 ⇒ pm25 == median` và đúng 100%: đó là rò rỉ target theo **cấu trúc**.

Con số cần đọc đúng: tổng số hàng `pm25` bị `NaN` là **1.549**, trong đó **1.289** mang cờ `pm25_was_missing` (khối dài) và **260** là khối ngắn không mang cờ. Dòng rò rỉ đo được là **256** hàng ở Train — không phải 1.289 — vì cờ chỉ bắt khối dài, còn khối ngắn cũng được impute nhưng không ai nhìn thấy qua cờ.

Điểm mấu chốt: `validate_no_leakage()` **không** bắt được lỗi này, vì imputer và scaler vẫn học đúng trên Train. Guard kiểm tham số học vô dụng ở đây — phải loại ở mức danh sách feature. Cờ vẫn được **giữ trong dataset** như tài liệu chẩn đoán; nó chỉ không được đưa vào `X`. Xem `TARGET_DERIVED_FLAGS` và `DIAGNOSTIC_FEATURES` trong `src/cleaning_pipeline.py`, và ô 15 của `notebooks/03_transformation_pipeline.ipynb` (nơi cơ chế này được **đo lại** trên dữ liệu thật, không phải khẳng định suông).

`pm25_was_stuck` bằng 0 toàn bộ là **phát hiện thực nghiệm, không phải lỗi**: Issue #5 đã kết luận chuỗi 0.0 dài ở Hà Nội là hiện tượng tự nhiên chứ không phải cảm biến hỏng. Cột này không mang thông tin phân biệt nhưng vẫn an toàn về kỹ thuật (`RobustScaler` cho `scale_ = 1.0`, `center_ = 0.0`, output `0.0` — không NaN), nên giữ lại để các notebook sau dùng chung một bộ cột.

**Hai điểm cần lưu ý cho Issue #11–#13.**

- **Target không được đưa vào feature — và giờ module tự chặn.** `NUMERIC_FEATURES` của `src/cleaning_pipeline.py` **không** còn liệt kê `pm25`, và `build_preprocessing_pipeline()` ném `ValueError` nếu target lọt vào danh sách. Bản gốc liệt kê sẵn `pm25`, nên gọi hàm không tham số là đưa chính câu trả lời vào `X`: bài toán dự báo biến thành bài toán đọc lại đáp án, và mọi chỉ số ở Issues #11–#13 sau này trở nên vô nghĩa.
- **`pm25` vẫn là `NaN` ở 1.549 hàng** (1.289 khối dài có cờ, 260 khối ngắn). Việc điền median của `SimpleImputer` chỉ xảy ra bên trong `ColumnTransformer` lúc `transform()`, bằng tham số học từ Train — **không ghi đè giá trị nào trong dataset** (`assert_no_imputation()` của Issue #6 vẫn PASS). Khi đánh giá mô hình phải chốt riêng cách xử lý `NaN` ở target.

---

### Week 06 – Thống kê Mô tả & Phân tích Chu kỳ Thời gian Đa tầng
* **Phân loại tuần:** Khám phá Dữ liệu (EDA) – Thống kê & Chuỗi Thời gian.
* **Mục tiêu tuần:** Xác lập hồ sơ thống kê toán học toàn diện cho Canonical Schema dựa trên 4 họ đại lượng; chứng minh bằng số liệu thực nghiệm việc lựa chọn đại lượng đo lường phù hợp (Mean vs Median); phân tích các quy luật chu kỳ thời gian đa tầng và ma trận tương quan kép.
* **Kiến thức INFO3020 áp dụng:** Slide W6 – Định lý giới hạn trung tâm (CLT), 4 họ thống kê (Location, Spread, Shape, Quantiles), Nguyên tắc "Hình dạng quyết định chỉ số", Tương quan Pearson vs Spearman, Bài học Anscombe's Quartet & Datasaurus Dozen.
* **Mã Issue sở hữu:** **#8**.
* **Tasks chi tiết:**
  1. Tính toán đầy đủ 4 họ chỉ số cho $\text{PM}_{2.5}$ và các biến khí tượng: Mean, Median, Mode, Phương sai, Độ lệch chuẩn, IQR, Skewness, Kurtosis, các phân vị ($P_{10}, P_{25}, P_{50}, P_{75}, P_{90}, P_{95}, P_{99}$) [Issue #8].
  2. Đo lường hình dạng phân phối thực nghiệm, biện luận khách quan việc lựa chọn cặp chỉ số Location/Spread phù hợp (Median/IQR thay vì Mean/Std nếu phân phối lệch mạnh) [Issue #8].
  3. Phân tích biến thiên theo giờ trong ngày qua 24 khung giờ, nhận diện các khoảng thời gian tập trung nồng độ cao/thấp thực tế mà không áp đặt trước khung giờ [Issue #8].
  4. Phân tích phân phối theo ngày trong tuần (ngày làm việc vs cuối tuần) và theo các tháng/mùa trong dải dữ liệu thực tế [Issue #8].
  5. Tính đường trung bình trượt 24h và 7 ngày; áp dụng phân rã chuỗi thời gian (`seasonal_decompose`) nếu chuỗi dữ liệu đáp ứng tính đều đặn và chu kỳ liên tục [Issue #8].
  6. Lập ma trận tương quan kép Pearson và Spearman giữa các biến, đối chiếu đồ thị phân tán để phát hiện quan hệ phi tuyến [Issue #8].
  7. Xuất hồ sơ thống kê định lượng vào `reports/statistical_profile.csv`.
* **Deliverables:** Notebook `notebooks/04_descriptive_stats.ipynb`, bảng hồ sơ thống kê `reports/statistical_profile.csv`.
* **Definition of Done:** Bảng thống kê có đủ 4 họ đại lượng; biện luận lựa chọn chỉ số dựa trên phân phối thực nghiệm; toàn bộ phát hiện chu kỳ xuất phát từ số liệu thực tế; không đưa ra kết luận võ đoán.
* **Dependencies:** Dữ liệu Parquet hoàn chỉnh từ Week 05 (#7).

---

### Week 07 – Thiết kế Bộ 7 Biểu đồ Ấn phẩm Giải thích (FIG-01 đến FIG-07)
* **Phân loại tuần:** Trực quan hóa Dữ liệu (Data Visualization).
* **Mục tiêu tuần:** Thiết kế và xuất bản bộ 7 biểu đồ ấn phẩm giải thích (Explanatory plots) từ FIG-01 đến FIG-07 chuẩn mực theo nguyên tắc Tufte và Cleveland; tuân thủ nghiêm ngặt ngữ nghĩa quy chuẩn về chu kỳ lấy mẫu trung bình; viết tiêu đề phát biểu kết luận khoa học rút ra từ số liệu thực tế.
* **Kiến thức INFO3020 áp dụng:** Slide W7 – Thứ bậc kênh thị giác Cleveland & McGill, Tỷ lệ Data-Ink của Edward Tufte, Bảng màu thân thiện người khiếm thị màu, Trục tung bar chart bắt đầu từ 0, Tiêu đề phát biểu kết luận (*Takeaway titles*), Ngữ nghĩa quy chuẩn môi trường (QCVN 05:2023/BTNMT, WHO 2021).
* **Mã Issue sở hữu:** **#9**.
* **Tasks chi tiết:**
  1. Lập trình module `src/visualizer.py` bằng Matplotlib Object-Oriented API (`fig, ax = plt.subplots()`), loại bỏ spines thừa, làm mờ lưới phụ, chuẩn hóa nhãn trục và đơn vị đo [Issue #9].
  2. Vẽ FIG-01 (Line chart chuỗi thời gian kèm đường trượt 24h & 7d, hiển thị đường ngưỡng 24h của QCVN tương thích toán học trên chuỗi trượt 24h) [Issue #9].
  3. Vẽ FIG-02 (Histogram + KDE thể hiện hình dạng phân phối thực nghiệm của $\text{PM}_{2.5}$) [Issue #9].
  4. Vẽ FIG-03 (Boxplot nồng độ $\text{PM}_{2.5}$ theo các tháng/mùa trong chuỗi quan sát thực tế) [Issue #9].
  5. Vẽ FIG-04 (2D Heatmap Giờ trong ngày $\times$ Thứ trong tuần) [Issue #9].
  6. Vẽ FIG-05 (Scatter plot biến thời tiết vs $\text{PM}_{2.5}$ kết hợp đường làm mượt LOWESS) [Issue #9].
  7. Vẽ FIG-06 (Correlation Heatmap ma trận các chất ô nhiễm và biến thời tiết) [Issue #9].
  8. Vẽ FIG-07 (Bar chart phân bố tần suất theo các mức chất lượng không khí, trục tung bắt đầu từ 0, phân loại theo chỉ số và ngưỡng tương thích chu kỳ tính toán) [Issue #9].
  9. Đặt tiêu đề cho 100% biểu đồ là **kết luận khoa học dẫn xuất từ dữ liệu thực nghiệm** [Issue #9].
  10. Xuất toàn bộ 7 biểu đồ chất lượng cao (PNG, 300 DPI) vào thư mục `figures/`.
* **Deliverables:** Module `src/visualizer.py`, 7 tệp hình ảnh `figures/FIG-01.png` đến `figures/FIG-07.png`.
* **Definition of Done:** Cả 7 biểu đồ được xuất bản ở 300 DPI; đường ngưỡng quy chuẩn tuân thủ nghiêm ngặt tính tương thích chu kỳ tính toán; trục tung bar chart bắt đầu từ 0; 100% tiêu đề là Takeaway Conclusion.
* **Dependencies:** Kết quả phân tích thống kê mô tả từ Week 06 (#8).

---

### Week 08 – BÁO CÁO & ĐÁNH GIÁ GIỮA KỲ (MIDTERM PROJECT MILESTONE)
* **Phân loại tuần:** Milestone Báo cáo & Thuyết trình Giữa kỳ.
* **Mục tiêu tuần:** Hoàn thiện và nộp Báo cáo Khám phá Dữ liệu (Midterm EDA Report) dung lượng 8–10 trang PDF theo cấu trúc SCQA; thiết kế slide thuyết trình 7 phút; kiểm chứng tính tái lập của toàn bộ các notebook thuộc phạm vi giữa kỳ (Milestone 1–3); gắn git tag nộp bài.
* **Kiến thức INFO3020 áp dụng:** Toàn bộ kiến thức Chương 1, Chương 2, Chương 3; Rubric đánh giá Midterm trên slide W7 (Làm sạch tất định 25%, Độ sâu EDA 25%, Chất lượng biểu đồ ấn phẩm 20%, Diễn giải thống kê trung thực 20%, Thuyết trình & Báo cáo 10%); Cấu trúc kể chuyện SCQA.
* **Mã Issue sở hữu:** **#10** (Phụ thuộc: #8, #9; Chặn: #11, #12, #13).
* **Tasks chi tiết:**
  1. Soạn thảo Báo cáo Giữa kỳ `reports/midterm_report.pdf` (8–10 trang) bao gồm: Đặt vấn đề & câu hỏi nghiên cứu, Nguồn dữ liệu & giấy phép, Kết quả kiểm toán 6 chiều & mẫu hình khuyết thiếu (nêu rõ tính bất định), Quy trình làm sạch tất định & trích lược Cleaning Log, Hồ sơ thống kê 4 họ chỉ số, Bộ biểu đồ ấn phẩm FIG-01 đến FIG-05 lồng ghép mạch kể chuyện SCQA, Ý nghĩa thực tiễn ban đầu [Issue #10].
  2. Thiết kế slide thuyết trình (8–10 slides) tập trung vào các phát hiện rút ra từ dữ liệu thực tế [Issue #10].
  3. Luyện tập căn chuẩn thời lượng thuyết trình 7 phút và chuẩn bị câu trả lời cho các câu hỏi phản biện kỹ thuật (Viva) [Issue #10].
  4. Kiểm chứng tính tái lập tự động đối với các notebook thuộc phạm vi Milestone 1–3 (từ `00_` đến `04_`), bảo đảm Restart Kernel & Run All thành công 100% không lỗi [Issue #10].
  5. Tạo và đẩy git tag chính thức `midterm-submission` lên GitHub repository [Issue #10].
* **Deliverables:** File `reports/midterm_report.pdf`, slide thuyết trình giữa kỳ, git tag `midterm-submission`.
* **Definition of Done:** Báo cáo nộp đúng hạn, đáp ứng đầy đủ rubric; toàn bộ notebook Milestone 1–3 thực thi thông suốt từ đầu đến cuối; git tag `midterm-submission` được tạo thành công trên commit nộp bài.
* **Dependencies:** Kết quả làm sạch, EDA và trực quan hóa từ Week 05, 06, 07 (#7, #8, #9).

---

### Week 09 – Suy luận Thống kê & Kiểm định Giả thuyết Phi tham số
* **Phân loại tuần:** Phân tích Thống kê Suy luận (Statistical Inference).
* **Mục tiêu tuần:** Thực hiện các phép kiểm định giả thuyết phi tham số có đối chứng trên dữ liệu chuỗi thời gian; kiểm tra tính chuẩn phân phối; báo cáo đầy đủ bộ bốn: Thống kê kiểm định, $p$-value, Kích thước hiệu ứng ($r_{rb}$) và Khoảng tin cậy Bootstrap 95%; đối chiếu nồng độ với quy chuẩn tương thích toán học.
* **Kiến thức INFO3020 áp dụng:** Slide W9 – Bước nhảy nhận thức từ mẫu sang tổng thể, 4 sai lầm kinh điển khi đọc $p$-value, Sai lầm loại I ($\alpha$) vs Loại II ($\beta$), Kích thước hiệu ứng (*Effect size*), Kỹ thuật Bootstrap resampling, Cây quyết định chọn phép kiểm thống kê.
* **Mã Issue sở hữu:** **#11**.
* **Tasks chi tiết:**
  1. Kiểm định 1: So sánh nồng độ $\text{PM}_{2.5}$ giữa các mùa quan sát (Mùa khô/lạnh vs Mùa mưa/nóng). Kiểm tra tính chuẩn bằng Shapiro-Wilk; khi vi phạm tính chuẩn, áp dụng Mann-Whitney U test [Issue #11].
  2. Tính toán kích thước hiệu ứng Rank-Biserial Correlation ($r_{rb} = 1 - 2U / (n_1 n_2)$) và ước lượng 95% Bootstrap CI cho chênh lệch trung vị (1.000 mẫu lặp, cố định `np.random.seed(42)`) [Issue #11].
  3. Kiểm định 2: So sánh Ngày làm việc (Weekday) vs Ngày cuối tuần (Weekend) bằng Mann-Whitney U test; phân tích rạch ròi giữa ý nghĩa thống kê và ý nghĩa thực tiễn [Issue #11].
  4. Kiểm định 3: Đối chiếu nồng độ với Quy chuẩn QCVN 05:2023/BTNMT bằng phép kiểm phi tham số phù hợp trên chuỗi tổng hợp tương thích toán học về chu kỳ lấy mẫu trung bình; báo cáo 95% CI [Issue #11].
  5. Soạn thảo notebook `notebooks/05_statistical_inference.ipynb` và bảng tổng hợp kết quả kiểm định [Issue #11].
* **Deliverables:** Notebook `05_statistical_inference.ipynb`, bảng kết quả kiểm định giả thuyết.
* **Definition of Done:** 100% các kết luận kiểm định đều trình bày đầy đủ bộ bốn: thống kê, $p$-value, Effect Size ($r_{rb}$), 95% Bootstrap CI; kiểm định quy chuẩn áp dụng đúng chỉ số tương thích toán học về chu kỳ lấy mẫu; không báo cáo $p$-value đơn độc.
* **Dependencies:** Dữ liệu sạch đóng băng từ Week 05 (#7) và kết quả EDA từ Week 06 (#8).

---

### Week 10 – Phân tích Hồi quy OLS, Chẩn đoán LINE & Điều hòa
* **Phân loại tuần:** Mô hình hóa – Hồi quy Tuyến tính OLS.
* **Mục tiêu tuần:** Xây dựng mô hình hồi quy tuyến tính OLS đa biến khảo sát mối liên hệ giữa các yếu tố khí tượng và $\text{PM}_{2.5}$ trên dữ liệu phân chia theo chuỗi thời gian; thực hiện quy trình chẩn đoán toàn diện 4 giả định LINE trên phần dư; phân tích heuristics VIF và Cook's distance; tối ưu mô hình điều hòa Ridge/Lasso strictly trên Train; diễn giải hệ số $\beta$ phi nhân quả.
* **Kiến thức INFO3020 áp dụng:** Slide W10 – Hồi quy OLS, 4 Giả định LINE (Linearity, Independence, Normality, Equal Variance), Biến đổi mục tiêu ứng viên, Đa cộng tuyến & VIF, Điểm ảnh hưởng Cook's distance, Điều hòa Ridge ($L_2$) & Lasso ($L_1$), Ba nghĩa vụ khi diễn giải hệ số $\beta$.
* **Mã Issue sở hữu:** **#12**.
* **Tasks chi tiết:**
  1. Kế thừa điểm cắt phân chia Train/Test theo chuỗi thời gian tuyến tính từ Issue #7; bảo lưu tập Test cho đánh giá độc lập cuối cùng [Issue #12].
  2. Khảo sát biến đổi logarit $Y = \log(1 + \text{PM}_{2.5})$ trên tập Train; tính tuyến tính và phân phối phần dư phải được kiểm chứng qua chẩn đoán thực nghiệm sau khớp [Issue #12].
  3. Huấn luyện Dummy Regressor Baseline và mô hình OLS trên tập Train bằng `statsmodels.api.OLS` và Scikit-Learn [Issue #12].
  4. Chẩn đoán 4 giả định LINE trên phần dư: Linearity (Residuals vs Fitted), Independence (Durbin-Watson & ACF), Normality (Q-Q plot & Shapiro-Wilk), Equal Variance (Breusch-Pagan & Scale-Location) [Issue #12].
  5. Tính toán chỉ số VIF (xem xét VIF > 5.0 như chỉ báo heuristic gợi ý điều chỉnh đặc trưng) và khoảng cách Cook's Distance ($D_i$) [Issue #12].
  6. Huấn luyện mô hình điều hòa Ridge/Lasso; dò tìm siêu tham số ($\alpha$) hoàn toàn trên tập Train (Time-Series Split / CV cục bộ trên Train); tuyệt đối không dùng Test để tune [Issue #12].
  7. Đánh giá trên tập TEST độc lập: Đo lường MAE, RMSE, $R^2$ cạnh Baseline; nếu giả định LINE bị vi phạm, giải trình khách quan giới hạn của mô hình [Issue #12].
  8. Diễn giải hệ số $\beta$ chuẩn 3 nghĩa vụ: liên hệ quan sát (*associated with*), giữ nguyên biến khác (*ceteris paribus*), giới hạn trong miền giá trị thực nghiệm; tuyệt đối không khẳng định quan hệ nhân quả [Issue #12].
* **Deliverables:** Notebook `notebooks/06_regression_modeling.ipynb`, biểu đồ chẩn đoán LINE `figures/regression_line_diagnostics.png`, bảng tham số hồi quy.
* **Definition of Done:** Đánh giá độc lập trên tập Test; toàn bộ 4 giả định LINE được chẩn đoán chi tiết; siêu tham số điều hòa được tune hoàn toàn trên Train; hệ số $\beta$ được diễn giải đúng chuẩn phi nhân quả.
* **Dependencies:** Dữ liệu sạch và split thời gian từ Week 05 (#7), kết quả suy luận từ Week 09 (#11).

---

### Week 11 – Phân loại Cảnh báo Ô nhiễm, Tối ưu Ngưỡng & Kiểm toán Rò rỉ
* **Phân loại tuần:** Mô hình hóa – Phân loại Nhị phân & Feature Engineering.
* **Mục tiêu tuần:** Xây dựng mô hình phân loại nhị phân cảnh báo sớm đợt ô nhiễm vượt ngưỡng an toàn; kỹ nghệ đặc trưng từ quá khứ; xử lý mất cân bằng lớp thực tế; tối ưu hóa ngưỡng quyết định theo mục tiêu vận hành trên Train/Validation; đánh giá độc lập trên Test; kiểm toán 4 dạng rò rỉ dữ liệu.
* **Kiến thức INFO3020 áp dụng:** Slide W11 – Mô hình Logistic Regression & Random Forest, Bẫy Accuracy trên dữ liệu mất cân bằng, Ma trận nhầm lẫn (Confusion Matrix), Đánh đổi Precision vs Recall, Đường cong PR-AUC, Threshold Tuning, Kỹ nghệ đặc trưng thời gian từ quá khứ, 4 dạng rò rỉ dữ liệu.
* **Mã Issue sở hữu:** **#13**.
* **Tasks chi tiết:**
  1. Định nghĩa nhãn mục tiêu nhị phân tương thích toán học về chu kỳ tính toán với quy chuẩn (ví dụ nồng độ trung bình 24h $\text{PM}_{2.5} \ge 50\,\mu\text{g/m}^3$ theo QCVN 05:2023/BTNMT); đo đạc tỷ lệ mất cân bằng thực tế [Issue #13].
  2. Tạo các đặc trưng trễ và thống kê trượt từ quá khứ (`pm25_rolling_mean_24h`, `pm25_rolling_std_24h`, `pm25_lag24`, nhiệt-ẩm, cờ lặng gió, sin/cos giờ/tháng); xác nhận không truy xuất thông tin tương lai [Issue #13].
  3. Huấn luyện Baseline DummyClassifier, Logistic Regression (`class_weight='balanced'`) và Random Forest Classifier trên tập Train [Issue #13].
  4. Vẽ đường cong Precision-Recall (PR Curve), đo đạc chỉ số PR-AUC [Issue #13].
  5. Tinh chỉnh ngưỡng quyết định trên tập Train/Validation theo mục tiêu vận hành cụ thể (tối đa hóa $F_\beta$ với $\beta > 1$ hoặc tối đa hóa Recall dưới ràng buộc Precision tối thiểu) [Issue #13].
  6. Đo lường hiệu năng cuối cùng trên tập TEST độc lập với ngưỡng đã chốt: Báo cáo Recall, Precision, F1/F-beta, PR-AUC, ROC-AUC và Confusion Matrix [Issue #13].
  7. Lập biên bản kiểm toán rà soát 4 dạng rò rỉ dữ liệu (Target, Train-Test contamination, Temporal, Group) [Issue #13].
* **Deliverables:** Notebook `notebooks/06_classification_alerts.ipynb`, biểu đồ PR Curve `figures/precision_recall_curve.png`, biên bản kiểm toán rò rỉ dữ liệu.
* **Definition of Done:** Đánh giá trên tập Test độc lập sau khi đóng băng mô hình và ngưỡng; ngưỡng quyết định được tối ưu hoàn toàn trên Train/Val theo mục tiêu vận hành; biên bản kiểm toán 4 dạng rò rỉ dữ liệu đạt chuẩn.
* **Dependencies:** Dữ liệu hoàn chỉnh từ Week 05 (#7) và mô hình hồi quy từ Week 10 (#12).

---

### Week 12 – Đạo đức Dữ liệu, Quy mô vs Spark, Datasheet & Model Card
* **Phân loại tuần:** Đạo đức Dữ liệu, Đánh giá Hạ tầng & Quản trị Dự án.
* **Mục tiêu tuần:** Thực hiện đo đạc thực nghiệm các chỉ số tài nguyên thực tế để đánh giá khách quan nhu cầu sử dụng Apache Spark vs Pandas; khảo sát 4 giả thuyết định kiến (Bias); biên soạn Datasheet for Dataset, Model Card 1 trang; hoàn thiện Project Charter và tuyên bố minh bạch AI.
* **Kiến thức INFO3020 áp dụng:** Slide W12 – Ngưỡng Big Data thực tế, Nghị định 13/2023/NĐ-CP, Sổ tay định kiến (*Sensor bias, Spatial bias, Survivorship bias, Missing vs Zero*), Tính giải trình (*Explainability*), Khung chuẩn Datasheet for Datasets & Model Cards.
* **Mã Issue sở hữu:** **#14**.
* **Tasks chi tiết:**
  1. Tiến hành đo đạc trực tiếp các chỉ số tài nguyên thực tế: dung lượng đĩa (MB của Parquet và CSV), lượng RAM chiếm dụng khi nạp DataFrame, thông lượng I/O, thời gian thực thi tiền xử lý và huấn luyện [Issue #14].
  2. Dẫn xuất kết luận về việc có/không sử dụng Apache Spark từ chính các số liệu đo đạc thực nghiệm; lập bảng đối sánh trong báo cáo [Issue #14].
  3. Khảo sát 4 giả thuyết định kiến: Sensor bias (độ ẩm cao $\text{RH} > 90\%$), Spatial bias (tính đại diện mạng lưới trạm tại Hà Nội), Survivorship / weather-related missingness bias (tương quan mất dữ liệu khi bão), phân định rạch ròi `NaN` vs `0.0` [Issue #14].
  4. Soạn thảo tài liệu `docs/datasheet.md` (Datasheet for Dataset) theo khung chuẩn Timnit Gebru [Issue #14].
  5. Soạn thảo tài liệu `docs/model_card.md` (Model Card 1 trang) mô tả hiệu năng phân tầng và giới hạn mô hình [Issue #14].
  6. Cập nhật tuyên bố minh bạch mức độ sử dụng AI vào `README.md` [Issue #14].
  7. Hoàn thiện tài liệu `docs/project_charter.md` quy chuẩn môn học [Issue #14].
* **Deliverables:** Báo cáo đo đạc tài nguyên vs Spark, `docs/datasheet.md`, `docs/model_card.md`, `docs/project_charter.md`, mục tuyên bố AI trong `README.md`.
* **Definition of Done:** Số liệu tài nguyên được đo đạc thực tế từ tập dữ liệu; lập luận về Spark được dẫn xuất từ số liệu đo đạc; 4 giả thuyết định kiến được khảo sát khách quan; Datasheet, Model Card và Project Charter hoàn tất 100%.
* **Dependencies:** Kết quả phân tích và mô hình từ Week 10 và 11 (#12, #13).

---

### Week 13 – Tái cấu trúc Mã nguồn, Phân tích Độ nhạy & Tiếp thu Cố vấn
* **Phân loại tuần:** Tái cấu trúc Mã nguồn & Phân tích Độ nhạy.
* **Mục tiêu tuần:** Tái cấu trúc và module hóa mã nguồn vào thư mục `src/`; thực hiện các phân tích độ nhạy (Sensitivity Analysis) đối với ngưỡng phân loại kỹ thuật và cửa sổ trễ; dọn dẹp chuỗi notebooks; ghi nhận và theo dõi việc tiếp thu ý kiến cố vấn kỹ thuật một cách có hệ thống.
* **Kiến thức INFO3020 áp dụng:** Vòng lặp phi tuyến CRISP-DM, Chuẩn hóa mã nguồn tái lập (PEP 8, docstrings, modularization), Phân tích độ nhạy (*Sensitivity Analysis*), Quản trị phản biện khoa học.
* **Mã Issue sở hữu:** **#15**.
* **Tasks chi tiết:**
  1. Module hóa các hàm dùng chung vào thư mục `src/`: `src/data_loader.py` (nạp dữ liệu, kiểm tra schema, Parquet I/O), `src/cleaning_pipeline.py` (pipeline tiền xử lý), `src/visualizer.py` (hàm vẽ biểu đồ chuẩn Tufte/Cleveland) [Issue #15].
  2. Bổ sung docstrings, type hints và bọc xử lý ngoại lệ theo chuẩn PEP 8 [Issue #15].
  3. Thực hiện phân tích độ nhạy đối với các ngưỡng cảnh báo kỹ thuật ứng viên (ví dụ dải ngưỡng 40, 45, 50, 55 $\mu\text{g/m}^3$), dán nhãn minh bạch đây là các kịch bản phân tích độ nhạy kỹ thuật, không tự ý đồng nhất với ngưỡng pháp lý khi chưa có cùng chu kỳ tính toán và văn bản quy định [Issue #15].
  4. Khảo sát độ nhạy của hệ số hồi quy khi thay đổi cửa sổ tính trễ và trung bình trượt [Issue #15].
  5. Dọn dẹp chuỗi notebooks: xóa cell rác tạm thời, cell debug thừa; sắp xếp các ô mã lệnh và markdown giải thích tuần tự, mạch lạc [Issue #15].
  6. Soạn thảo tài liệu theo dõi phản biện kỹ thuật `docs/mentoring_feedback.md`: Lập bảng đối chiếu gồm nội dung góp ý, hành động kỹ thuật đã thực hiện trong mã nguồn/notebook và bằng chứng kiểm chứng [Issue #15].
* **Deliverables:** Các tệp module trong `src/` (`data_loader.py`, `cleaning_pipeline.py`, `visualizer.py`), tài liệu `docs/mentoring_feedback.md`, kết quả phân tích độ nhạy trong notebooks.
* **Definition of Done:** Các module trong `src/` import độc lập không lỗi phụ thuộc vòng tròn; phân tích độ nhạy dán nhãn kỹ thuật minh bạch; chuỗi notebooks sạch sẽ; 100% các mục góp ý kỹ thuật được ghi nhận và truy vết trong `docs/mentoring_feedback.md`.
* **Dependencies:** Kết quả phân tích và mô hình từ Week 09–12 (#11, #12, #13, #14).

---

### Week 14 – Kể chuyện Dữ liệu, Soạn thảo Báo cáo Cuối kỳ & Slide Bảo vệ
* **Phân loại tuần:** Báo cáo Tổng kết & Chuẩn bị Bảo vệ.
* **Mục tiêu tuần:** Hoàn thiện Báo cáo Đồ án Cuối kỳ (Final Capstone Report) định dạng PDF theo cấu trúc kể chuyện SCQA dựa hoàn toàn trên bằng chứng thực nghiệm đã kiểm chứng; thiết kế bộ slide bảo vệ đồ án 10–12 phút; xây dựng tài liệu chuẩn bị 15 câu hỏi phản biện kỹ thuật (Viva QA).
* **Kiến thức INFO3020 áp dụng:** Slide W7 & W14 – Nghệ thuật kể chuyện bằng dữ liệu (*Data Storytelling*), Cấu trúc SCQA (Situation, Complication, Question, Answer), Nguyên tắc thiết kế slide khoa học, Kỹ năng giải trình phản biện cá nhân (*Viva*).
* **Mã Issue sở hữu:** **#16**.
* **Tasks chi tiết:**
  1. Soạn thảo Báo cáo Đồ án Cuối kỳ `reports/final_report.pdf` theo bố cục SCQA chặt chẽ:
     - **S (Situation):** Bối cảnh chất lượng không khí đô thị Hà Nội và đặc tính thực tế của chuỗi dữ liệu quan sát được đóng băng [Issue #16].
     - **C (Complication):** Biến cố dẫn xuất từ bằng chứng dữ liệu thực tế (các đợt bùng phát ô nhiễm, tính phi tuyến, sự thiếu hụt dữ liệu hoặc rào cản cảnh báo kịp thời), tuyệt đối không gán ghép nguyên nhân giả định khi chưa chứng minh [Issue #16].
     - **Q (Question):** Hệ thống hóa Main RQ và 4 Sub-questions [Issue #16].
     - **A (Answer):** Tổng hợp hệ thống chứng cứ định lượng từ phân tích mô tả 4 họ chỉ số, kiểm định giả thuyết bộ bốn, hồi quy OLS kèm báo cáo trung thực giả định LINE (nêu rõ hạn chế nếu vi phạm, không biến tương quan thành quan hệ nhân quả), hiệu năng mô hình phân loại trên tập Test độc lập, kết quả đo đạc tài nguyên thực tế và khuyến nghị chính sách dựa trên số liệu [Issue #16].
  2. Thiết kế bộ slide thuyết trình bảo vệ đồ án (12–15 slides) chuẩn hóa thời lượng 10–12 phút [Issue #16].
  3. Soạn thảo tài liệu `docs/viva_qa_prep.md`: 15 câu hỏi trọng tâm hội đồng có thể chất vấn (cơ sở chọn phép kiểm, chẩn đoán LINE, lý do chọn mục tiêu tối ưu ngưỡng, rò rỉ dữ liệu, đạo đức dữ liệu) kèm câu trả lời mẫu chi tiết [Issue #16].
  4. Nhúng toàn bộ 7 biểu đồ ấn phẩm (FIG-01 đến FIG-07) và các đồ thị chẩn đoán vào báo cáo [Issue #16].
* **Deliverables:** File `reports/final_report.pdf`, slide thuyết trình bảo vệ đồ án, tài liệu `docs/viva_qa_prep.md`.
* **Definition of Done:** Báo cáo phản ánh trung thực toàn bộ kết quả phân tích thực nghiệm; không chứa khẳng định nhân quả trái với bản chất nghiên cứu quan sát; slide bảo vệ và tài liệu viva hoàn tất.
* **Dependencies:** Kết quả nghiên cứu và mã nguồn hoàn thiện từ Week 07, 09, 10, 11, 12, 13 (#9, #11, #12, #13, #14, #15).

---

### Week 15 – KIỂM TOÁN REPOSITORY, KIỂM CHỨNG TÁI LẬP & BẢO VỆ CUỐI KỲ
* **Phân loại tuần:** Milestone Kiểm toán Toàn diện, Bàn giao & Bảo vệ Cuối kỳ.
* **Mục tiêu tuần:** Thực hiện kiểm toán kỹ thuật toàn diện repository trước giai đoạn bảo vệ; kiểm chứng tính tái lập tự động của toàn bộ chuỗi notebooks từ môi trường sạch; rà soát tính toàn vẹn của mã nguồn, dữ liệu và tài liệu; tạo git tag chính thức; chuẩn bị biểu mẫu biên bản đánh giá và bàn giao bảo vệ trước hội đồng.
* **Kiến thức INFO3020 áp dụng:** Tích hợp toàn diện 15 tuần học; Chuẩn mực kỹ thuật tái lập mã nguồn; Tiêu chuẩn liêm chính học thuật CLO4; Năng lực làm chủ phương pháp luận khoa học dữ liệu.
* **Mã Issue sở hữu:** **#17**.
* **Tasks chi tiết:**
  1. Kiểm toán kỹ thuật toàn diện repository: Rà soát cấu trúc cây thư mục chuẩn CRISP-DM, kiểm tra sự hiện diện đầy đủ của các tệp bắt buộc (`README.md`, `requirements.txt`, `LICENSE`, `.gitignore`, `data/raw/metadata.json`) [Issue #17].
  2. Kiểm tra tính toàn vẹn tài liệu và tính hợp lệ của toàn bộ liên kết nội bộ (`docs/data_dictionary.md`, `docs/source_profiling_decision.md`, `docs/cleaning_log.md`, `docs/datasheet.md`, `docs/model_card.md`, `docs/project_charter.md`, `docs/mentoring_feedback.md`, `docs/viva_qa_prep.md`) [Issue #17].
  3. Xác thực hồ sơ xuất xứ dữ liệu trong `data/raw/metadata.json`, tính toàn vẹn của `data/raw/` (đối chiếu mã băm SHA-256), tính hợp lệ của tệp Snappy Parquet trong `data/processed/`, và kiểm tra không có rò rỉ giữa Train và Test [Issue #17].
  4. Thực thi kiểm chứng tự động toàn bộ chuỗi notebooks từ `00_environment_test.ipynb` đến `06_classification_alerts.ipynb` trong môi trường ảo sạch: Bảo đảm 100% các ô mã lệnh thực thi tuần tự, không phát sinh lỗi ngoại lệ unhandled exception [Issue #17].
  5. Chuẩn bị biểu mẫu biên bản đánh giá bảo vệ đồ án `reports/defense_minutes.md` [Issue #17].
  6. Tạo commit hoàn thiện và gắn git tag chính thức `final-defense-submission` trên nhánh chính [Issue #17].
  7. Thực hiện bảo vệ đồ án trước Hội đồng chấm thi môn học và trả lời phản biện cá nhân (Oral Defense / Viva) [Issue #17].
* **Deliverables:** Toàn bộ repository hoàn chỉnh, git tag `final-defense-submission`, biểu mẫu biên bản bảo vệ `reports/defense_minutes.md`.
* **Definition of Done (Tiêu chuẩn Kỹ thuật Khách quan):** 
  - Toàn bộ chuỗi notebook từ 00 đến 06 thực thi thông suốt từ đầu đến cuối không có lỗi unhandled exception.
  - Cấu trúc repository hợp lệ, không có liên kết hỏng trong tài liệu.
  - Dữ liệu thô được bảo toàn nguyên trạng và có mã băm SHA-256 trong metadata; không có rò rỉ dữ liệu Train/Test.
  - Git tag `final-defense-submission` được tạo thành công và đẩy lên GitHub repository.
* **Dependencies:** Toàn bộ kết quả từ Week 01 đến Week 14 (#15, #16).

---

## 15. LỜI KHUYÊN THỰC CHIẾN DÀNH CHO BẠN (PRO-TIPS)

1. **Giữ gìn thư mục `data/raw/` như một "hiện trường vụ án":** Tuyệt đối không bao giờ dùng chuột mở file CSV/JSON trong Excel rồi bấm Save. Excel sẽ tự ý chuyển đổi định dạng ngày tháng và làm hỏng encoding tiếng Việt! Mọi thao tác làm sạch phải được thực thi bằng mã nguồn có thể tái lập và ghi log minh bạch vào `docs/cleaning_log.md`.
2. **Quy tắc vàng về kiểm tra giả định:** *"Không bao giờ tự hào vì $R^2$ cao khi chưa soi biểu đồ phần dư Residual Plot và kiểm tra VIF"*. Trong chuỗi thời gian, $R^2$ cao bất thường thường chỉ là hệ quả của việc rò rỉ dữ liệu (Temporal Leakage) hoặc hiện tượng tương quan giả (*Spurious correlation*). Luôn chẩn đoán đủ 4 giả định LINE trước khi diễn giải mô hình.
3. **Thước đo là một quyết định nghiệp vụ:** Trong bài toán cảnh báo ô nhiễm, đừng bao giờ báo cáo mỗi chỉ số Accuracy trên dữ liệu mất cân bằng. Hãy chủ động tối ưu hóa ngưỡng quyết định dựa trên sự đánh đổi chi phí thực tế giữa Recall và Precision (thông qua điểm $F_\beta$ hoặc ràng buộc nghiệp vụ cụ thể), bởi vì cái giá của việc bỏ sót một đợt ô nhiễm độc hại ảnh hưởng nghiêm trọng đến sức khỏe cộng đồng là không thể bù đắp được! Đó chính là tư duy cốt lõi của một **Data Scientist thực thụ**.
