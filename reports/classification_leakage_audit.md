# Biên Bản Kiểm Toán Rò Rỉ Dữ Liệu Phân Loại (Data Leakage Audit) — Issue #13 & Task D14

> **Căn cứ học thuật:** Slide W11 & Quy định liêm chính học thuật INFO3020.
> **Mốc chia thời gian kiểm chứng:** `2026-01-15 00:00:00+07:00`
> **Kích thước tập hợp lệ kiểm chứng:** Train = 2,965 giờ (ô thiếu đầu vào: 0) | Test = 2,302 giờ (ô thiếu đầu vào: 0)

---

## 1. Kiểm toán 4 Dạng Rò rỉ Dữ liệu Cốt lõi & Bằng chứng Thực thi

| Dạng Rò Rỉ | Rủi ro Tiềm ẩn | Biện pháp Phòng ngừa & Bằng chứng Kiểm chứng | Kết luận |
|---|---|---|:---:|
| **1. Target Leakage (Rò rỉ Mục tiêu)** | Dùng biến phái sinh trực tiếp từ mục tiêu (`pm25_was_missing`), dùng biến đồng thời `pm10`, hoặc để đặc trưng trượt nhìn thấy giá trị tại $t$. | Cấm tuyệt đối `pm25`, `pm10`, `pm25_was_missing`, `is_high_humidity_fog` trong `FORBIDDEN_CLASSIFICATION_COLS` (raise `ValueError`). Đặc trưng trượt bắt buộc `shift(1)` (từ $t-1$ trở về trước) trên lưới giờ liên tục; kiểm chứng bằng unit test thay đổi `pm25[t] = 999` không làm biến thiên bất kỳ đặc trưng nào tại $t$. | **PASS** |
| **2. Train-Test Contamination (Nhiễm chéo Train-Test)** | Tham số imputer, scaler hoặc ngưỡng $\tau$ học từ tập Test hoặc impute toàn cục trước CV. | Không còn impute trong `prepare_classification_data`. `SimpleImputer(median)` và `RobustScaler()` nằm bên trong `Pipeline([('preprocessor', ColumnTransformer(...)), ('clf', ...)])`; từng fold của `TimeSeriesSplit(5)` chỉ fit trên `X_train.iloc[tr_idx]`; ngưỡng $\tau^*$ bất biến trước đột biến `y_test`; kiểm chứng sau fit bằng `src.cleaning_pipeline.validate_no_leakage()`. | **PASS** |
| **3. Temporal Leakage (Rò rỉ Thứ tự Thời gian)** | Chia ngẫu nhiên hoặc để nhãn $y_{t+h}$ ở cuối Train chồng lấn sang miền Test. | Phân chia tuyến tính kiểm chứng `ts_train.max() < ts_test.min()`. Khi tầm dự báo $h > 0$, áp dụng purge gap `t + h < split_timestamp` loại bỏ mọi mẫu cuối Train có cửa sổ nhãn chạm Test. | **PASS** |
| **4. Group / Station Leakage (Rò rỉ Cụm trạm)** | Gộp nhiều trạm lệch pha thời gian (`VN001` vs `VN003`) làm nhiễu rolling hoặc làm lộ ranh giới thời gian trạm khác. | Áp dụng Protocol A đơn trạm (`station_id` rõ ràng). `_select_single_station()` từ chối fail-closed nếu phát hiện > 1 trạm khi chưa chỉ định `station_id`. `engineer_classification_features()` nhóm độc lập theo `station_id` bảo đảm 24h đầu trạm B luôn là `NaN`, không tràn từ trạm A. | **PASS** |

---

## 2. Giải trình Loại trừ Kỹ thuật Tổng hợp Mẫu SMOTE

- **Nguyên nhân loại trừ:** SMOTE (*Synthetic Minority Over-sampling Technique*) nội suy tuyến tính giữa các hàng không kề nhau theo thời gian trong không gian đa biến.
- **Hệ quả trên chuỗi thời gian khí tượng:** Nội suy lân cận ghép cặp hai ngày khác mùa/khác bối cảnh synop, tạo ra bước nhảy phi vật lý giữa gió, áp suất và nhiệt-ẩm, đồng thời phá vỡ cấu trúc tự tương quan và ranh giới thời gian giữa các đợt ô nhiễm.
- **Giải pháp thay thế chuẩn mực:** Áp dụng `class_weight='balanced'` kết hợp tinh chỉnh ngưỡng $\tau$ trên OOF của Train theo $F_2$ và `Recall` dưới ràng buộc `Precision >= 0.60`.

---

## 3. Giải trình Chồng lấn Cửa sổ (Window Overlap) tại $h=0$ & Độ trễ Reanalysis ERA5

- **Tiêu chí cảnh giác (Slide W11 Takeaway #4):** *"Nghi ngờ ngay lập tức nếu PR-AUC hoặc Recall đạt > 99%"*.
- **Kết quả thực nghiệm tại tầm truy hồi tức thời ($h=0$):**
  - Logistic Regression: Recall = 99.55%, PR-AUC = 0.9989
  - Random Forest: Recall = 100.00%, PR-AUC = 0.9985
- **Giải thích toán học:** Tại $h=0$, đặc trưng `pm25_rolling_mean_24h` tổng hợp $[t-24, t-1]$ còn nhãn $y_t$ tổng hợp $[t-23, t]$. Hai cửa sổ chia sẻ **23/24 giờ (95,8%)** nên trạng thái nhãn chủ yếu được suy trực tiếp từ 23 giờ giao thoa với hệ số tự tương quan $\rho_1 \approx 0,73$. Khi dịch chuyển sang dự báo tương lai thật tại $h = 24\text{h}$ (giao thoa **0/24 giờ**) hoặc cắt bỏ đặc trưng PM2.5 quá khứ (chỉ dùng khí tượng), hiệu năng giảm mạnh theo đúng quy luật vật lý — đây là **bằng chứng trực tiếp khẳng định không có rò rỉ dữ liệu tương lai**.
- **Giới hạn vận hành (ERA5 Latency):** Khí tượng Open-Meteo ERA5 là dữ liệu tái phân tích (reanalysis) có độ trễ phát hành ~5 ngày; do đó thiết lập tại h = 0 giờ mang bản chất truy hồi tức thời lịch sử (retrospective nowcast), không phải vận hành thời gian thực trừ khi thay bằng dữ liệu quan trắc/dự báo NWP trực tuyến.

### Bằng chứng định lượng qua Feature Ablation & Dự báo đa tầm (Purge Gap)

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| h=0h | Full (Rolling24 + Lag24 + Met) | 2965 | 2302 | 666 | 0.2893 | 0.9989 | 0.9955 | 0.9985 | 1.0 | 0.992 | OK |
| h=0h | Lag24 + Met (No 24h Rolling) | 2965 | 2302 | 666 | 0.2893 | 0.7908 | 0.8529 | 0.7364 | 0.994 | 0.6904 | OK |
| h=0h | Meteorology + Time Only (No PM2.5) | 2994 | 2323 | 669 | 0.288 | 0.4338 | 1.0 | 0.5954 | 0.9985 | 0.6708 | OK |
| h=1h | Full Feature Set | 2936 | 2281 | 663 | 0.2907 | 0.9966 | 0.9804 | 0.9951 | 0.994 | 0.978 | OK |
| h=6h | Full Feature Set | 2803 | 2186 | 647 | 0.296 | 0.9696 | 0.8887 | 0.9509 | 1.0 | 0.7352 | OK |
| h=12h | Full Feature Set | 2647 | 2084 | 619 | 0.297 | 0.9094 | 0.7205 | 0.8586 | 0.9984 | 0.7423 | OK |
| h=24h | Full Feature Set | 2369 | 1893 | 543 | 0.2868 | 0.7513 | 0.6041 | 0.5876 | 1.0 | 0.7158 | OK |

### Ghi chú bão hòa ngưỡng trên OOF
- Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).
- Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).
