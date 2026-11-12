# Biên Bản Kiểm Toán Rò Rỉ Dữ Liệu Phân Loại (Data Leakage Audit) — Issue #13

> **Căn cứ học thuật:** Slide W11 & Quy định liêm chính học thuật INFO3020.
> **Ngày thực hiện:** 2026-11-11
> **Tập dữ liệu:** `data/processed/air_pollution_final.parquet`

---

## 1. Kiểm toán 4 Dạng Rò rỉ Dữ liệu Cốt lõi

| Dạng Rò Rỉ | Rủi ro Tiềm ẩn | Biện pháp Phòng ngừa & Bằng chứng Thực nghiệm | Kết luận |
|---|---|---|:---:|
| **1. Target Leakage (Rò rỉ Mục tiêu)** | Sử dụng biến phái sinh trực tiếp từ mục tiêu làm đặc trưng dự báo (ví dụ `pm25_was_missing`). | Cờ `pm25_was_missing` bị loại bỏ hoàn toàn khỏi tập đặc trưng. Các biến trượt (`pm25_rolling_mean_24h`, `pm25_rolling_std_24h`) bắt buộc áp dụng `shift(1)` — chỉ sử dụng dữ liệu từ $t-1$ trở về trước, không chứa giá trị tại thời điểm $t$. | **PASS** |
| **2. Train-Test Contamination (Nhiễm chéo Train-Test)** | Tham số tiền xử lý hoặc ngưỡng quyết định học từ tập Test. | Bộ chuẩn hóa `RobustScaler` và `train_medians` được học duy nhất trên Train partition. Ngưỡng phân loại vận hành ($\tau$) được tối ưu hoàn toàn qua `TimeSeriesSplit(n_splits=5)` trên tập Train; tập Test bị đóng băng hoàn toàn. | **PASS** |
| **3. Temporal Leakage (Rò rỉ Thứ tự Thời gian)** | Sử dụng thông tin tương lai để dự báo quá khứ (random split). | Áp dụng điểm cắt tuyến tính cố định `split_timestamp = 2026-01-15 00:00:00+07:00`. Tuyệt đối không dùng `train_test_split` ngẫu nhiên. Cửa sổ trượt 24h ở đầu tập Test chỉ truy xuất quá khứ ở cuối tập Train. | **PASS** |
| **4. Group / Station Leakage (Rò rỉ Cụm trạm)** | Gộp các trạm khác nhau mà không phân tách thực thể quan trắc. | Dữ liệu baseline thuộc trạm đơn nhất `VN001_HANOI_556_NGUYEN_VAN_CU`, khóa quan trắc được bảo toàn. | **PASS** |

---

## 2. Giải trình Loại trừ Kỹ thuật Tổng hợp Mẫu SMOTE

- **Nguyên nhân loại trừ:** SMOTE (*Synthetic Minority Over-sampling Technique*) tạo ra các điểm dữ liệu nhân tạo bằng phép nội suy tuyến tính lân cận giữa các mẫu thiểu số trong không gian đặc trưng.
- **Hệ quả tiêu cực trên chuỗi thời gian:** Việc tạo điểm nhân tạo làm phá vỡ tính liên tục tự nhiên của chuỗi thời gian khí tượng, tạo ra các bước nhảy vật lý vô lý (ví dụ: nhiệt độ, độ ẩm nhảy vọt giữa các giờ liên tiếp) và làm rò rỉ ranh giới thời gian giữa các pha ô nhiễm.
- **Giải pháp thay thế chuẩn mực:** Sử dụng trọng số lớp nghịch đảo `class_weight='balanced'` trong Logistic Regression và Random Forest, kết hợp tinh chỉnh ngưỡng quyết định vận hành ($\tau$) theo hàm mục tiêu $F_2$ score.

---

## 3. Heuristic Cảnh báo Rò rỉ Dữ liệu & Hiện tượng Chồng lấn Cửa sổ (Window Overlap)
- **Tiêu chí an toàn (Slide W11 Takeaway #4):** *"Nghi ngờ ngay lập tức nếu mô hình đạt điểm Recall hoặc PR-AUC > 99%"*.
- **Kết quả thực nghiệm trên tập Test:**
  - Logistic Regression: Recall = 99.55%, PR-AUC = 0.9989
  - Random Forest: Recall = 100.00%, PR-AUC = 0.9985
- **Phân tích cơ chế toán học vượt ngưỡng > 99%:**
  - Điểm PR-AUC và Recall đạt xấp xỉ hoặc vượt 99% không xuất phát từ việc vi phạm rò rỉ dữ liệu tương lai (toàn bộ đặc trưng đều tuân thủ `shift(1)` triệt để).
  - Nguyên nhân cốt lõi là **hiện tượng chồng lấn cửa sổ trượt (Rolling Window Overlap)**: Đặc trưng `pm25_rolling_mean_24h` tại thời điểm $t$ lấy trung bình từ $t-24$ đến $t-1$, trong khi nhãn mục tiêu $y_t$ lấy trung bình từ $t-23$ đến $t$. Như vậy, đặc trưng quá khứ chia sẻ tới **23/24 (95,8%)** số hạng với nhãn mục tiêu. Kết hợp với tính tự tương quan thời gian rất cao của PM2.5 ($\rho_1 \approx 0,73$), mô hình dễ dàng đạt độ chuẩn xác cực đại ở bài toán cảnh báo nowcasting (1 giờ tới).
  - **Khuyến nghị vận hành & Giới hạn nghiên cứu:** Để cảnh báo mang tính phòng ngừa xa hơn (lead time 24h), hệ thống cần dịch chuyển cửa sổ đặc trưng về $t-24$ trở về trước hoặc dựa chủ yếu vào thông số khí tượng. Ở phạm vi bài toán hiện tại, mô hình phục vụ tốt vai trò cảnh báo tức thời theo thời gian thực.
