# Câu Hỏi Nghiên Cứu & Khung Phân Tích (Research Questions & Analytical Framework)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)  
> **Căn cứ kỹ thuật:** Lộ trình đồ án [`docs/roadmap.md`](roadmap.md), GitHub Issue #2, và phương pháp luận CRISP-DM.  
> **Tài liệu tham chiếu:** [`docs/data_dictionary.md`](data_dictionary.md)  
> **Nguyên tắc cốt lõi:** Liêm chính học thuật (CLO4), tính trung lập khoa học, không đưa ra kết luận định trước (*No predetermined conclusions*).

---

## 1. Mục Tiêu Nghiên Cứu (Research Objective)

Dự án hướng tới việc phân tích có hệ thống dữ liệu chuỗi thời gian về nồng độ bụi mịn $\text{PM}_{2.5}$ tại khu vực đô thị Hà Nội cùng các yếu tố khí tượng bề mặt liên quan. 

Mục tiêu khoa học của nghiên cứu bao gồm:
1. Khám phá và mô tả trung thực hình thái phân phối thực nghiệm của $\text{PM}_{2.5}$ dựa trên dữ liệu thu thập thực tế.
2. Định lượng các biến thiên chuỗi thời gian ở nhiều thang đo (giờ trong ngày, ngày trong tuần, tháng, mùa) và kiểm định ý nghĩa thống kê của các khác biệt quan sát được.
3. Đánh giá mối liên hệ quan sát được giữa các thông số thời tiết và nồng độ bụi mịn thông qua mô hình hồi quy OLS tuyến tính cổ điển, kiểm tra nghiêm ngặt 4 giả định chẩn đoán LINE trên phần dư mà không gán nghĩa nhân quả.
4. Xây dựng bài toán phân loại cảnh báo sớm ô nhiễm theo mục tiêu tối ưu vận hành bảo vệ sức khỏe cộng đồng, xử lý mất cân bằng lớp và tuân thủ nguyên tắc không rò rỉ dữ liệu (*Data Leakage*).

---

## 2. Câu Hỏi Nghiên Cứu Mục Tiêu (Main Research Question)

> **"Khảo sát quy luật biến thiên theo thời gian của nồng độ PM2.5 tại Hà Nội, định lượng mối liên hệ quan sát được với các yếu tố khí tượng bề mặt và xây dựng mô hình cảnh báo sớm nồng độ ô nhiễm dựa trên dữ liệu thực nghiệm được thu thập."**

Câu hỏi trung tâm này kết nối xuyên suốt các giai đoạn của quy trình CRISP-DM: từ hiểu bài toán (*Business/Research Understanding*), khám phá dữ liệu (*Data Understanding*), mô hình hóa giải thích (*Exploratory & Inferential Modeling*) đến xây dựng giải pháp cảnh báo sớm (*Predictive & Operational Modeling*).

---

## 3. Các Câu Hỏi Nghiên Cứu Thành Phần (Sub-Questions)

Để giải quyết thấu đáo câu hỏi trung tâm, nghiên cứu chia thành 4 câu hỏi thành phần độc lập nhưng có mối liên hệ logic chặt chẽ:

```text
               ┌────────────────────────────────────────────────────────┐
               │              MAIN RESEARCH QUESTION                    │
               │  Biến thiên thời gian, liên hệ khí tượng & cảnh báo    │
               └───────────────────────────┬────────────────────────────┘
                                           │
         ┌───────────────────┬─────────────┴───────┬───────────────────┐
         ▼                   ▼                     ▼                   ▼
    ┌─────────┐         ┌─────────┐           ┌─────────┐         ┌─────────┐
    │   SQ1   │         │   SQ2   │           │   SQ3   │         │   SQ4   │
    │Phân phối│         │ Chu kỳ  │           │Liên hệ  │         │Cảnh báo │
    │thực     │ ──────► │thời gian│ ────────► │khí tượng│ ──────► │sớm      │
    │nghiệm   │         │& so sánh│           │& OLS    │         │(Classi- │
    │4 họ đo  │         │đối chứng│           │LINE     │         │fication)│
    └─────────┘         └─────────┘           └─────────┘         └─────────┘
```

---

### SQ1 — Phân phối Thực nghiệm của Bụi mịn PM2.5 (Empirical Distribution)

* **Nội dung câu hỏi:**  
  *Hình thái phân phối thực nghiệm của nồng độ $\text{PM}_{2.5}$ tại Hà Nội có đặc điểm như thế nào về khuynh hướng trung tâm (central tendency), độ phân tán (spread), độ lệch (skewness), và độ nhọn/đuôi dày (kurtosis)? Các chỉ số thống kê mô tả nào là đại diện phù hợp nhất cho mức độ phơi nhiễm điển hình của người dân?*

* **Khung phân tích & Yêu cầu phương pháp luận:**
  1. **Khảo sát đủ 4 họ chỉ số thống kê mô tả:**
     - *Họ vị trí (Location):* Trung bình cộng (Mean), Trung vị (Median / $P_{50}$).
     - *Họ phân tán (Spread):* Độ lệch chuẩn (Standard Deviation), Độ trải giữa (Interquartile Range - $\text{IQR} = Q_3 - Q_1$), Khoảng biến thiên (Range $= \max - \min$).
     - *Họ hình dạng (Shape):* Hệ số bất đối xứng (Skewness), Hệ số độ nhọn (Kurtosis).
     - *Họ phân vị (Quantiles):* $P_{10}, P_{25}, P_{50}, P_{75}, P_{90}, P_{95}, P_{99}$.
  2. **Nguyên tắc "Hình dạng phân phối quyết định chỉ số" (*Shape Picks the Statistic*):**
     - Dự án **tuyệt đối không giả định trước** rằng dữ liệu có phân phối chuẩn hay bị lệch.
     - Việc lựa chọn giữa cặp chỉ số **Mean / Standard Deviation** (thích hợp với phân phối đối xứng, tiệm cận chuẩn) hay cặp chỉ số **Median / IQR** (bền vững trước phân phối lệch và các giá trị cực trị/đột biến) phải được quyết định hoàn toàn dựa trên bằng chứng dữ liệu thực tế sau khi thu thập và kiểm định.
     - Nếu phân phối quan sát thực tế bị lệch phải mạnh và có đuôi dày, tài liệu phân tích phải giải thích rõ lý do Mean có thể bị kéo lệch bởi các đợt bùng phát ô nhiễm ngắn hạn và vì sao Median phản ánh chân thực hơn mức độ phơi nhiễm điển hình hàng ngày.

---

### SQ2 — Biến thiên theo Các Thang Đo Thời Gian (Temporal Variation & Hypothesis Testing)

* **Nội dung câu hỏi:**  
  *Nồng độ $\text{PM}_{2.5}$ biến thiên như thế nào qua các chu kỳ thời gian khác nhau (theo giờ trong ngày, ngày trong tuần, các tháng và các mùa trong năm)? Các khác biệt quan sát được giữa các nhóm thời gian (ví dụ: ngày làm việc so với ngày cuối tuần, các mùa trong chuỗi quan sát) có đạt ý nghĩa thống kê hay không?*

* **Khung phân tích & Yêu cầu phương pháp luận:**
  1. **Khảo sát đa tầng chu kỳ thời gian:**
     - *Chu kỳ ngày đêm (Diurnal / Hourly):* Phân tích biến động nồng độ theo từng giờ trong 24 giờ.
     - *Chu kỳ ngày trong tuần (Day-of-Week):* Đối chiếu chuỗi thời gian giữa các ngày làm việc (Thứ Hai – Thứ Sáu) và ngày cuối tuần (Thứ Bảy – Chủ Nhật).
     - *Chu kỳ tháng & mùa vụ (Monthly & Seasonal):* Theo dõi diễn biến nồng độ qua các tháng và các mùa trong chuỗi dữ liệu thực tế thu thập được.
  2. **Kiểm định giả thuyết thống kê có đối chứng:**
     - Xác lập rõ ràng giả thuyết vô hiệu ($H_0$) và giả thuyết đối ($H_1$) trước khi thực hiện kiểm định.
     - Kiểm tra giả định phân phối trước khi chọn phép kiểm định (nếu dữ liệu không tuân theo phân phối chuẩn, bắt buộc sử dụng kiểm định phi tham số như Mann-Whitney U hoặc Wilcoxon signed-rank thay vì Student's t-test).
     - Báo cáo đầy đủ bộ bốn kết quả bắt buộc: Thống kê kiểm định + Giá trị $p$-value + Kích thước hiệu ứng (*Effect size*, ví dụ: tương quan hạng lưỡng điểm $r_{rb}$ hoặc Cliff's delta) + Khoảng tin cậy 95% Bootstrap ($\ge 1.000$ lần lặp).
  3. **Nguyên tắc trung lập thời gian:**
     - **Không khẳng định định kiến trước** rằng giờ nào, ngày nào trong tuần, tháng nào hay mùa nào có nồng độ ô nhiễm cao nhất hoặc thấp nhất.
     - Toàn bộ kết luận về chu kỳ và đỉnh ô nhiễm phải được dẫn xuất từ số liệu quan trắc thực tế của tập dữ liệu sau khi kiểm toán chất lượng.

---

### SQ3 — Mối Liên Hệ Quan Sát Được Với Các Yếu Tố Khí Tượng (Relationship with Weather Variables & OLS Diagnostics)

* **Nội dung câu hỏi:**  
  *Mối liên hệ thống kê quan sát được giữa nồng độ bụi mịn $\text{PM}_{2.5}$ và các biến khí tượng bề mặt (nhiệt độ, độ ẩm tương đối, tốc độ gió, hướng gió, lượng mưa, áp suất khí quyển bề mặt) biểu hiện như thế nào khi áp dụng mô hình hồi quy tuyến tính OLS? Các giả định chẩn đoán nền tảng của mô hình OLS có được thỏa mãn trên phần dư hay không?*

* **Khung phân tích & Yêu cầu phương pháp luận:**
  1. **Các biến khí tượng ứng viên:**
     - Nhiệt độ bề mặt (`temperature`).
     - Độ ẩm tương đối (`relative_humidity`).
     - Tốc độ gió (`wind_speed`).
     - Hướng gió (`wind_direction`).
     - Lượng mưa (`precipitation`).
     - Áp suất bề mặt (`surface_pressure`).
  2. **Quy trình kiểm tra 4 giả định chẩn đoán LINE trên phần dư (Residuals):**
     - **L (Linearity - Tuyến tính):** Đánh giá đồ thị Residuals vs. Fitted values để kiểm tra sự tồn tại của quan hệ phi tuyến; xem xét biến đổi logarit $\log(1 + \text{PM}_{2.5})$ nếu cần ổn định mối liên hệ.
     - **I (Independence - Độc lập):** Kiểm tra hiện tượng tự tương quan chuỗi thời gian của phần dư thông qua hệ số Durbin-Watson; khảo sát việc bổ sung biến trễ nếu có tự tương quan.
     - **N (Normality - Phân phối chuẩn):** Đánh giá đồ thị Q-Q plot và kiểm định độ chuẩn (Shapiro-Wilk) trên phần dư.
     - **E (Equal Variance / Homoscedasticity - Phương sai đồng nhất):** Kiểm tra hiện tượng phương sai thay đổi (hình phễu trên đồ thị phần dư) thông qua kiểm định Breusch-Pagan.
  3. **Kiểm tra đa cộng tuyến & Điểm ảnh hưởng:**
     - Đo lường hệ số phóng đại phương sai (Variance Inflation Factor - VIF) cho từng biến dự báo khí tượng để phát hiện hiện tượng cộng tuyến nghiêm trọng ($\text{VIF} > 5.0$).
     - Đánh giá khoảng cách Cook's distance để nhận diện các điểm dữ liệu có sức ảnh hưởng bất thường tới mặt phẳng hồi quy.
  4. **Quy tắc diễn giải phi nhân quả (*Non-causal interpretation*):**
     - **Tuyệt đối không sử dụng ngôn từ mang tính nhân quả** như: "nhiệt độ gây ra ô nhiễm", "gió làm giảm bụi mịn", "độ ẩm dẫn tới tăng $\text{PM}_{2.5}$".
     - **Bắt buộc sử dụng ngôn từ thống kê mô tả mối liên hệ quan sát được**, ví dụ: "mối liên hệ quan sát được" (*observed association*), "quan hệ thống kê" (*statistical relationship*), "hệ số liên hệ trong điều kiện giữ nguyên không đổi các yếu tố khác" (*association holding all other variables constant - ceteris paribus*).
     - Diễn giải hệ số hồi quy $\beta$ luôn phải kèm theo phạm vi giá trị quan sát thực tế của các biến khí tượng trong dữ liệu.

---

### SQ4 — Phân Loại Cảnh Báo Sớm Ô Nhiễm (Early-Warning Classification)

* **Nội dung câu hỏi:**  
  *Làm thế nào để xây dựng bài toán phân loại cảnh báo sớm nồng độ $\text{PM}_{2.5}$ vượt ngưỡng an toàn dựa trên các thông số trễ trong quá khứ, giải quyết vấn đề mất cân bằng lớp và tối ưu hóa ngưỡng quyết định theo mục tiêu vận hành bảo vệ sức khỏe cộng đồng mà không gây rò rỉ dữ liệu?*

* **Khung phân tích & Yêu cầu phương pháp luận:**
  1. **Quy trình xây dựng bài toán phân loại:**
     - *Xác lập ngưỡng cảnh báo vận hành:* Định nghĩa ngưỡng phân loại nồng độ $\text{PM}_{2.5}$ (tham chiếu quy chuẩn kỹ thuật quốc gia QCVN 05:2023/BTNMT với ngưỡng trung bình 24 giờ là $50\,\mu\text{g/m}^3$ hoặc các ngưỡng phân cấp tương thích), được cố định chính thức trước khi huấn luyện mô hình.
     - *Tạo nhãn phân loại (Binary Target):* Chuyển đổi chuỗi quan sát liên tục thành nhãn nhị phân: Lớp 1 (Nguy cơ vượt ngưỡng / Cảnh báo ô nhiễm) và Lớp 0 (Mức an toàn / Bình thường).
     - *Tách tập dữ liệu chống rò rỉ (Leakage Prevention):* Áp dụng phương pháp phân chia tập huấn luyện (Train) và kiểm tra (Test) nghiêm ngặt theo thứ tự thời gian tuyến tính (*Chronological Split*). Tuyệt đối không dùng chia ngẫu nhiên.
     - *Huấn luyện & Tinh chỉnh:* Huấn luyện mô hình tiền xử lý và thuật toán phân loại hoàn toàn trên tập Train; tinh chỉnh siêu tham số và tối ưu ngưỡng quyết định trên tập Validation (hoặc Time-Series Cross-Validation trên Train).
     - *Đánh giá độc lập:* Kiểm chứng hiệu năng cuối cùng một lần duy nhất trên tập Test độc lập chưa từng được tiếp xúc.
  2. **Xác định mục tiêu tối ưu trước khi thực nghiệm (*Pre-defined Optimization Objective*):**
     - Do số lượng ngày/giờ có ô nhiễm vượt ngưỡng thường chiếm tỷ lệ nhỏ (mất cân bằng lớp), chỉ số **Accuracy (Độ chính xác tổng thể) bị cấm sử dụng đơn độc** để đánh giá mô hình (tránh "Accuracy Trap").
     - Mục tiêu tối ưu vận hành hướng tới việc bảo vệ sức khỏe cộng đồng: Báo động trượt (False Negative - bỏ sót đợt ô nhiễm nguy hại) gây hậu quả nghiêm trọng hơn nhiều so với Báo động giả (False Positive - khuyến cáo đeo khẩu trang phòng ngừa).
     - Hướng tối ưu ưu tiên:
       - **Tối đa hóa $F_\beta$ với $\beta > 1$** (ví dụ: $F_2$-score, coi trọng Recall gấp đôi Precision).
       - Hoặc **Tối đa hóa Recall với điều kiện ràng buộc mức Precision tối thiểu** (ví dụ: $\text{Recall}$ đạt tối đa trong khi $\text{Precision} \ge 0.50$).
  3. **Không lựa chọn trước kết quả:**
     - Không dự đoán trước giá trị Recall, Precision hay PR-AUC khi chưa thực hiện huấn luyện và kiểm thử thực tế trên dữ liệu.

---

## 4. Phạm Vi & Tính Trung Lập Khoa Học (Scope & Scientific Neutrality)

Tài liệu này xác lập "bản khế ước nghiên cứu" (*Research Contract*) tuân thủ các nguyên tắc liêm chính học thuật:

1. **Tính chất nghiên cứu quan sát (Observational Study):**  
   Dữ liệu thu thập từ các trạm quan trắc mặt đất và mô hình tái phân tích khí tượng là dữ liệu quan sát tự nhiên. Nhóm nghiên cứu không can thiệp vào môi trường phát thải hay điều kiện thời tiết, do đó mọi mô hình hóa đều mang tính mô tả và dự báo liên hệ, không mang giá trị can thiệp nhân quả.
2. **Không kết luận trước dữ liệu (Zero Predetermined Conclusions):**  
   Mọi khẳng định về xu hướng, mức độ chênh lệch, độ phù hợp của mô hình và tính hiệu quả của cảnh báo phải được chứng minh bằng con số, đồ thị và kiểm định thống kê trên tập dữ liệu thực tế.
3. **Phân định rõ ràng giữa Kế hoạch và Hiện trạng:**  
   Tại thời điểm ban hành tài liệu này (Tuần 01 – Milestone 1), các câu hỏi nghiên cứu là **định hướng phân tích kế hoạch**, chưa có bất kỳ mô hình hay phân tích nào được thực thi.

---

## 5. Lộ Trình Hiện Thực Hóa Phân Tích (Planned Analytical Direction)

| Câu hỏi thành phần | Giai đoạn CRISP-DM | Issue thực hiện | Sản phẩm dự kiến |
|---|---|:---:|---|
| **SQ1 (Phân phối thực nghiệm)** | Data Understanding | #8 (Tuần 6–7) | Bảng 4 họ chỉ số thống kê mô tả; biểu đồ phân phối Histogram & KDE; quyết định lựa chọn cặp đại lượng trung tâm. |
| **SQ2 (Biến thiên thời gian)** | Data Understanding & Evaluation | #8, #9, #11 (Tuần 6–9) | Biểu đồ chu kỳ giờ, ngày trong tuần, tháng, mùa (FIG-01, FIG-02, FIG-03); Bảng kết quả kiểm định phi tham số bộ bốn (Stat, $p$-val, $r_{rb}$, 95% Bootstrap CI). |
| **SQ3 (Liên hệ khí tượng & OLS)** | Modeling & Evaluation | #12 (Tuần 10) | Mô hình OLS; Bảng hệ số $\beta$ kèm khoảng tin cậy; Bộ 4 đồ thị chẩn đoán LINE trên phần dư; Chỉ số VIF và Cook's distance. |
| **SQ4 (Cảnh báo sớm)** | Modeling & Evaluation | #13 (Tuần 11) | Pipeline phân loại; Đường cong Precision-Recall; Bảng hiệu năng phân loại trên tập Test độc lập; Báo cáo kiểm toán 4 dạng rò rỉ dữ liệu. |
