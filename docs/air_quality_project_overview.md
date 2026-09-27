# Phân tích mức độ ô nhiễm không khí theo thời gian

## 1. Giới thiệu

Đề tài tập trung phân tích mức độ ô nhiễm không khí tại **Hà Nội** dựa trên dữ liệu PM2.5 và các yếu tố khí tượng theo thời gian.

Mục tiêu chính là tìm ra các **xu hướng, thời điểm và giai đoạn có mức độ ô nhiễm cao/thấp**, từ đó hiểu rõ hơn sự thay đổi của chất lượng không khí theo giờ, ngày, tháng và mùa.

Dataset được sử dụng là **Hanoi Air Quality (PM2.5) + Weather Data 2024-2026** trên Kaggle. Dataset được mô tả là gồm các quan sát PM2.5 theo giờ cùng với các đặc trưng khí tượng. 

Nguồn dữ liệu:
- Kaggle: https://www.kaggle.com/datasets/diabolicfox/hanoi-air-quality-pm2-5-weather-data-2024-2026/data

---

## 2. Mục tiêu của project

Project hướng tới các mục tiêu:

1. Làm sạch và chuẩn bị dữ liệu để phân tích.
2. Khám phá sự thay đổi của PM2.5 theo thời gian.
3. Xác định các khoảng thời gian có mức PM2.5 cao hoặc thấp.
4. Phân tích sự khác biệt về ô nhiễm giữa:
   - Các giờ trong ngày.
   - Các ngày trong tuần.
   - Các tháng trong năm.
   - Các mùa.
5. Khảo sát mối quan hệ giữa PM2.5 và một số yếu tố thời tiết nếu dataset có đầy đủ dữ liệu.
6. Trực quan hóa kết quả bằng các biểu đồ phù hợp.
7. Đưa ra kết luận dựa trên dữ liệu thay vì chỉ dựa trên nhận xét trực quan.

---

## 3. Dữ liệu

### Biến chính

**PM2.5** là biến trung tâm của project, được sử dụng để biểu diễn nồng độ bụi mịn trong không khí.

Các biến thời gian có thể được tạo thêm từ timestamp:

- Year
- Month
- Day
- Hour
- Day of Week
- Season

Nếu dataset có các biến khí tượng phù hợp, có thể sử dụng thêm:

- Temperature
- Humidity
- Wind Speed
- Precipitation
- Pressure
- Các biến thời tiết khác có trong dataset

> **Lưu ý:** PM2.5 không đồng nghĩa với AQI. PM2.5 là nồng độ của một loại chất ô nhiễm, trong khi AQI là một chỉ số được tính theo quy chuẩn/phương pháp cụ thể.

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

Sau khi hoàn thành project, nhóm có thể đưa ra:

- Xu hướng PM2.5 theo thời gian.
- Các giờ có mức PM2.5 trung bình cao/thấp.
- Các tháng hoặc mùa có mức ô nhiễm khác nhau.
- Những giai đoạn xuất hiện PM2.5 tăng cao.
- Mối quan hệ giữa PM2.5 và các yếu tố thời tiết.
- Các biểu đồ trực quan giúp giải thích kết quả.

**Không đưa ra kết luận trước khi phân tích dữ liệu thực tế.** Các nhận xét cuối cùng phải dựa trên kết quả tính toán từ dataset.

---

## 8. Công cụ dự kiến

Project có thể được thực hiện bằng:

- **Python**
- **Pandas** — xử lý dữ liệu
- **NumPy** — tính toán
- **Matplotlib** — trực quan hóa
- **Seaborn** — biểu đồ thống kê
- **Jupyter Notebook / Google Colab** — môi trường thực hiện

---

## 9. Phạm vi project

Project tập trung vào **phân tích dữ liệu và tìm hiểu xu hướng ô nhiễm theo thời gian**.

Dự báo PM2.5 bằng các mô hình Machine Learning hoặc Time Series như ARIMA/LSTM **không phải phần bắt buộc của giai đoạn này** và chỉ nên bổ sung nếu môn học yêu cầu hoặc nhóm muốn mở rộng project.

---

## 10. Kết luận định hướng

Thông qua dữ liệu PM2.5 theo giờ kết hợp với dữ liệu thời tiết, project hướng tới việc biến dữ liệu thô thành những thông tin dễ hiểu về **mức độ và xu hướng ô nhiễm không khí tại Hà Nội theo thời gian**.

Trọng tâm của project là:

> **“Ô nhiễm không khí thay đổi như thế nào theo thời gian và những yếu tố nào có thể liên quan đến sự thay đổi đó?”**
