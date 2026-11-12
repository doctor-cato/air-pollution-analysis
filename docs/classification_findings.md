# Tổng Hợp Phát Hiện Khoa Học: Mô Hình Cảnh Báo Ô Nhiễm PM2.5 (Issue #13)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Chủ đề:** Hệ thống Phân loại Cảnh báo Ô nhiễm Thời gian thực (Nowcasting) & Tối ưu Ngưỡng Y tế Công cộng

---

## 1. Bản Chất Khoa Học của Bài Toán Cảnh Báo Ô Nhiễm (Nowcasting)

1. **Chu kỳ lấy mẫu theo QCVN 05:2023/BTNMT:**
   - Quy chuẩn môi trường quốc gia quy định ngưỡng nồng độ PM₂.₅ trung bình 24 giờ là 50 µg/m³.
   - Việc chuyển đổi từ bài toán hồi quy nồng độ sang phân loại nhị phân cảnh báo nguy hại cho phép các nhà quản lý đô thị kích hoạt các hành động can thiệp y tế cộng đồng (khuyến cáo đeo khẩu trang, hạn chế hoạt động ngoài trời, điều tiết giao thông).
2. **Nowcasting vs Forecasting 24h:**
   - Hệ thống được định nghĩa chính xác là **Nowcasting** (cảnh báo tức thời tại thời điểm hiện tại $t$).
   - Sử dụng nồng độ bụi kết thúc tại $t-1$ kết hợp các biến khí tượng quan trắc tại thời điểm $t$ giúp đưa ra cảnh báo chính xác mà không gặp phải độ trễ thông báo 24 giờ của các trạm truyền thống.

---

## 2. Quản Trị Đánh Đổi Giữa Precision và Recall trong Y Tế Công Cộng

- **Chi phí của sai lầm (Cost Asymmetry):**
  - **False Negative (Bỏ sót cảnh báo):** Người dân không được cảnh báo khi không khí ô nhiễm nguy hại, dẫn đến gia tăng nhập viện vì bệnh hô hấp/tim mạch. Chi phí xã hội là **rất cao**.
  - **False Positive (Báo động giả):** Gây phiền toái hoặc cảnh giác quá mức nhưng không tổn hại trực tiếp tới sức khỏe. Chi phí xã hội là **thấp hơn**.
- **Hàm mục tiêu $F_2$ Score:**
  - Bằng cách chọn tối ưu hóa $F_2$ score thay vì $F_1$ hay Accuracy, ngưỡng quyết định $\tau$ được hạ thấp (0.32 đối với Random Forest), giúp tăng độ nhạy Recall lên **100.00%** (bắt được 666/666 ca ô nhiễm).

---

## 3. Động Lực Khí Tượng & Tương Tác Giữ Bụi

- **Gió lặng (Calm wind) & Áp suất cao:** Khi tốc độ gió thấp (< 0,5 m/s) và áp suất bề mặt cao, lớp biên khí quyển bị nén chặt, cản trở sự phát tán của bụi mịn.
- **Tương tác Nhiệt - Ẩm (`temp_humidity_interaction`):** Sự kết hợp giữa nhiệt độ thấp và độ ẩm tương đối cao thúc đẩy quá trình ngưng tụ hơi ẩm lên các hạt nhân sol khí (aerosol hygroscopic growth) và tạo sương mù giữ bụi, là cơ chế đặc trưng của các đợt ô nhiễm mùa đông tại Hà Nội.

---

## 4. Kiểm Toán Rò Rỉ Dữ Liệu & Bài Học Thực Tiễn

- Bốn dạng rò rỉ (Target, Contamination, Temporal, Group) đã được kiểm soát nghiêm ngặt bằng quy trình xử lý thuần thời gian và kỹ thuật `shift(1)`.
- Loại trừ SMOTE trên chuỗi thời gian là bài học phương pháp luận quan trọng: SMOTE tạo ra các điểm ngoại suy phi vật lý phá vỡ cấu trúc chuỗi liên tục.
- Hiệu năng vượt trội (> 99%) được giải trình khoa học bằng hiện tượng chồng lấn cửa sổ trượt (95,8% overlap), khẳng định tính trung thực học thuật và xác lập ranh giới rõ ràng cho các bài toán dự báo trong tương lai.
