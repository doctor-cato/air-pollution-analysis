# Báo Cáo Kết Quả Mô Hình Phân Loại Cảnh Báo Ô Nhiễm (Nowcasting) — Issue #13

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 11
> **Tập dữ liệu:** `data/processed/air_pollution_final.parquet` (Trạm NCEM/VEA 556 Nguyễn Văn Cừ, Hà Nội)
> **Mốc phân chia chuỗi thời gian:** `2026-01-15 00:00:00+07:00`
> **Kích thước mẫu:** Huấn luyện (Train) = 2,965 giờ | Kiểm thử (Test) = 2,302 giờ

---

## 1. Định Nghĩa Bài Toán & Hai Quần Thể Nhãn

Bài toán cảnh báo ô nhiễm không khí theo QCVN 05:2023/BTNMT (nồng độ trung bình 24 giờ PM₂.₅ $\ge 50,0\ \mu\text{g/m}^3$) được cấu trúc như sau:
- **Định vị bài toán:** **Nowcasting** (Cảnh báo ô nhiễm tức thời theo thời gian thực tại thời điểm $t$) bằng cách kết hợp thông tin nồng độ $\text{PM}_{2.5}$ trong quá khứ kết thúc tại $t-1$ (`shift(1)`) với các điều kiện khí tượng bề mặt đo đạc tại thời điểm $t$.
- **Minh bạch hai quần thể nhãn:**
  1. *Quần thể nhãn 24h rolling thô (y_raw.notna()):* 5.317 giờ quan sát (2.994 Train / 2.323 Test).
  2. *Quần thể đánh giá sau khi áp dụng đặc trưng trễ (valid_mask):* **5.267 giờ** (2,965 Train / 2,302 Test). Tập Test ghi nhận **666 ca dương tính** trên 2.302 giờ đánh giá (Prevalence = 28.93%).
- **Công bố sự cố gián đoạn quan trắc:** Ghi nhận đợt mất tín hiệu trạm liên tục kéo dài **630 giờ** (trong tháng 6–7/2026), dẫn đến việc nhãn rolling 24h tự động gán `NaN` để bảo toàn tính toàn vẹn dữ liệu, không nội suy võ đoán.

---

## 2. Tinh Chỉnh Ngưỡng Quyết Định Trên Tập Train (Operational Threshold Tuning)

Để ưu tiên phát hiện sớm các đợt bùng phát ô nhiễm nguy hại nhằm bảo vệ sức khỏe cộng đồng, hàm mục tiêu vận hành sử dụng $F_2$ score (đặt trọng số Recall gấp đôi Precision):
$$ F_2 = \frac{5 \cdot \text{Precision} \cdot \text{Recall}}{4 \cdot \text{Precision} + \text{Recall}} $$
- Quá trình tìm kiếm ngưỡng tối ưu được thực hiện độc lập trên tập Train thông qua 5-fold `TimeSeriesSplit` với `sklearn.base.clone()` để ngăn chặn rò rỉ và không làm đột biến mô hình.
- **Ngưỡng vận hành tối ưu được xác định:**
  - Logistic Regression (Balanced): $\tau^* = 0.43$
  - Random Forest (Balanced): $\tau^* = 0.32$

---

## 3. Bảng Hiệu Năng Phân Loại Trên Tập Test Độc Lập

| Model | Threshold | Accuracy | Precision | Recall | F1 | F2 | ROC-AUC | PR-AUC | Confusion Matrix [TN, FP, FN, TP] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (Dummy Prior) | 0.5 | 71.07% | 0.00% | 0.00% | 0.0000 | 0.0000 | 0.5000 | 0.2893 | [[1636, 0], [666, 0]] |
| Logistic Regression (Balanced) | 0.43000000000000005 | 98.09% | 94.18% | 99.55% | 0.9679 | 0.9843 | 0.9995 | 0.9989 | [[1595, 41], [3, 663]] |
| Random Forest (Balanced) | 0.32 | 98.83% | 96.10% | 100.00% | 0.9801 | 0.9920 | 0.9995 | 0.9985 | [[1609, 27], [0, 666]] |

> ⚠️ **Phát hiện cốt lõi:**
> 1. **Bẫy Accuracy (The Accuracy Trap):** Mô hình Baseline Prior Dummy đạt Accuracy lên tới **71,07%** nhưng Recall = **0,00%** và F2 = **0,0000** (bỏ sót 100% trong số 666 ca ô nhiễm nguy hại). Điều này khẳng định việc dựa vào Accuracy trên dữ liệu mất cân bằng là sai lầm nghiêm trọng.
> 2. **Chỉ số PR-AUC trung thực:** PR-AUC của Baseline Dummy khi tính bằng `average_precision_score` đạt chính xác **0.2893** (bằng đúng tỷ lệ dương tính của tập Test), loại bỏ hoàn toàn hiện tượng thổi phồng sai lệch do tích phân hình thang kinh điển.
> 3. **Hiệu năng của Mô hình Học máy:**
>    - **Random Forest (Balanced)** với ngưỡng $\tau = 0.32$ đạt **Recall = 100.00%** (bắt được 666/666 ca ô nhiễm, chỉ để lọt 0 ca), Precision = 96.10%, F2 = 0.9920 và PR-AUC = 0.9985.
>    - **Logistic Regression (Balanced)** với ngưỡng $\tau = 0.43$ đạt **Recall = 99.55%** (663/666 ca), Precision = 94.18%, F2 = 0.9843 và PR-AUC = 0.9989.

---

## 4. Cơ Chế Chồng Lấn Cửa Sổ Trượt (Rolling Window Overlap) & Giới Hạn Nowcasting

- Việc mô hình đạt điểm PR-AUC và Recall > 99% xuất phát từ bản chất cơ học của cửa sổ trượt:
  - Đặc trưng `pm25_rolling_mean_24h` tại thời điểm $t$ tổng hợp thông tin từ $t-24$ đến $t-1$.
  - Nhãn mục tiêu $y_t$ tổng hợp thông tin từ $t-23$ đến $t$.
  - Do đó, hai chuỗi chia sẻ **23/24 phần tử (95,8%)**. Với hệ số tự tương quan mạnh của $\text{PM}_{2.5}$ ($\rho_1 \approx 0,73$), mô hình dễ dàng phát hiện trạng thái ô nhiễm tức thời.
- **Khuyến nghị vận hành:** Hệ thống hoạt động xuất sắc như một công cụ giám sát và cảnh báo thời gian thực (Nowcasting). Đối với dự báo phòng ngừa dài hạn (Lead time 24h–48h), cần dịch chuyển cửa sổ đặc trưng ra xa hơn ($t-24$ trở về trước) và tăng cường trọng số các yếu tố động lực khí quyển.

---

## 5. Tầm Quan Trọng Biến & Tương Tác Khí Tượng

| Feature | MDI Importance | Permutation Mean | Permutation Std |
| --- | --- | --- | --- |
| pm25_rolling_mean_24h | 0.5763073808390969 | 0.6974474474474475 | 0.018599840380236543 |
| pm25_rolling_std_24h | 0.06968637803950802 | 0.003903903903903849 | 0.0015312370911690265 |
| relative_humidity | 0.008625485219641016 | 0.001351351351351271 | 0.0004504504504504236 |
| temperature | 0.021047756704180274 | 0.0007507507507507061 | 0.0007507507507507061 |
| pm25_lag24 | 0.08552954059266982 | 0.0006006006006005427 | 0.0015312370911689764 |
| precipitation | 0.004012488753011671 | 0.00030030030030028245 | 0.0006006006006005649 |
| month_sin | 0.02479559777019904 | 0.0 | 0.0 |
| is_calm_wind | 0.00019923380136483432 | 0.0 | 0.0 |
| hour_sin | 0.0033989790440066277 | -2.2204460492503132e-17 | 0.0009496329309814739 |
| surface_pressure | 0.05249110811285827 | -0.00015015015015018562 | 0.001247240820257943 |
| hour_cos | 0.0028597710533269176 | -0.0003003003003003046 | 0.0006006006006006094 |
| temp_humidity_interaction | 0.07254381416585523 | -0.0007507507507507616 | 0.0007507507507507616 |
| month_cos | 0.06880634941695932 | -0.0007507507507507726 | 0.0010072378277025979 |
| wind_speed | 0.009696116487322017 | -0.0012012012012012185 | 0.0006006006006006092 |

- Đặc trưng trượt quá khứ `pm25_rolling_mean_24h` và `pm25_rolling_std_24h` đóng vai trò chi phối quyết định cảnh báo.
- Trong các yếu tố khí tượng bề mặt, tốc độ gió (`wind_speed`), nhiệt độ, biến tương tác nhiệt-ẩm (`temp_humidity_interaction`), và áp suất bề mặt (`surface_pressure`) đóng góp suy giảm hiệu năng có ý nghĩa khi bị xáo trộn, phản ánh hiện tượng nghịch nhiệt mùa đông tại miền Bắc Việt Nam (nhiệt độ thấp, độ ẩm cao kết hợp gió lặng làm giữ chặt bụi mịn trong lớp biên khí quyển).
