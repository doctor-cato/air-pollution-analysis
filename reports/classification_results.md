# Báo Cáo Kết Quả Mô Hình Phân Loại Cảnh Báo Ô Nhiễm (Truy Hồi Tức Thời & Đa Tầm) — Issue #13

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 11
> **Phạm vi chính:** `VN001_baseline_2026_01_15` (`VN001_HANOI_556_NGUYEN_VAN_CU`) | **SHA-256:** `866f39de1720c727...`
> **Mốc phân chia chuỗi thời gian:** `2026-01-15 00:00:00+07:00` | **Kích thước Evaluable:** Train = 2,965 giờ | Test = 2,302 giờ (666 ca dương tính)

---

## 1. Bản Chất Bài Toán, Độ Trễ ERA5 & Đối Soát Quần Thể Dữ Liệu

- **Định vị khoa học:** Bài toán đánh giá khả năng phân loại vượt ngưỡng trung bình 24 giờ QCVN 05:2023/BTNMT ($\text{PM}_{2.5} \ge 50,0\ \mu\text{g/m}^3$). Khí tượng Open-Meteo ERA5 là dữ liệu tái phân tích (reanalysis) có độ trễ phát hành ~5 ngày; do đó thiết lập tại h = 0 giờ mang bản chất truy hồi tức thời lịch sử (retrospective nowcast), không phải vận hành thời gian thực trừ khi thay bằng dữ liệu quan trắc/dự báo NWP trực tuyến.
- **Minh bạch mẫu số & tỷ lệ mất cân bằng (Prevalence):**
  - Tập Train hợp lệ: **2,965 / 4,682** giờ lưới (Prevalence = **32.98%** trên mẫu hợp lệ; **20.89%** trên tổng lưới).
  - Tập Test hợp lệ: **2,302 / 4,362** giờ lưới (Prevalence = **28.93%** trên mẫu hợp lệ; **15.27%** trên tổng lưới).

| Quần thể | Total (giờ) | Train (giờ) | Test (giờ) | Positives Total | Positives Train | Positives Test | Prevalence (Train / Test) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Toàn bộ lưới thời gian (All grid) | 9044 | 4682 | 4362 | 1655 | 986 | 669 | 21.06% / 15.34% |
| 2. Có quan trắc PM2.5 hợp lệ | 7495 | 4279 | 3216 | 1655 | 986 | 669 | 23.04% / 20.80% |
| 3. Đủ nhãn cửa sổ 24h (y_raw.notna()) | 5317 | 2994 | 2323 | 1655 | 986 | 669 | 32.93% / 28.80% |
| 4. Đủ nhãn & đặc trưng trễ 24h (Evaluable) | 5267 | 2965 | 2302 | 1644 | 978 | 666 | 32.98% / 28.93% |

---

## 2. Tổng Hợp Hiệu Năng Phân Loại Trên Tập Test Độc Lập (`VN001_baseline_2026_01_15`)

- **Bẫy Accuracy & Baseline tham chiếu:**
  - `DummyClassifier(strategy='prior')` đạt Accuracy = **71.07%**, nhưng Recall = **0.00%** và PR-AUC = **0.2893** (bằng đúng tỷ lệ dương tính của tập Test).
  - `PersistenceRuleClassifier` (ngưỡng cơ học 1 biến `pm25_rolling_mean_24h >= 50`) đạt Recall = **98.50%**, PR-AUC = **0.9992**.
- **Mô hình Học máy (ngưỡng $F_2$ tinh chỉnh hoàn toàn trên Train OOF):**
  - **Logistic Regression (Balanced, $\tau^*=0.43$):** Recall = **99.55%** (663/666 ca dương), Precision = **94.18%**, F2 = **0.9843**, PR-AUC = **0.9989**, FAR = **2.51%**.
  - **Random Forest (Balanced, $\tau^*=0.32$):** Recall = **100.00%** (666/666 ca dương, bỏ sót 0 ca), Precision = **96.10%**, F2 = **0.9920**, PR-AUC = **0.9985**, FAR = **1.65%**.

| Model | Threshold | Accuracy | Precision | Recall | FAR | F1 | F2 | Brier | ROC-AUC | PR-AUC | Confusion Matrix [TN, FP, FN, TP] | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (Prior Dummy) | 0.5 | 0.7107 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2073 | 0.5 | 0.2893 | [[1636, 0], [666, 0]] | OK |
| Baseline (Persistence Rule >=50) | 0.5 | 0.9917 | 0.9865 | 0.985 | 0.0055 | 0.9857 | 0.9853 | 0.0845 | 0.9997 | 0.9992 | [[1627, 9], [10, 656]] | OK |
| Logistic Regression (Balanced, F2) | 0.43 | 0.9809 | 0.9418 | 0.9955 | 0.0251 | 0.9679 | 0.9843 | 0.0143 | 0.9995 | 0.9989 | [[1595, 41], [3, 663]] | OK |
| Logistic Regression (Prec>=0.60) | 0.1 | 0.9014 | 0.7458 | 1.0 | 0.1388 | 0.8544 | 0.9362 | 0.0143 | 0.9995 | 0.9989 | [[1409, 227], [0, 666]] | OK |
| Random Forest (Balanced, F2) | 0.32 | 0.9883 | 0.961 | 1.0 | 0.0165 | 0.9801 | 0.992 | 0.0134 | 0.9995 | 0.9985 | [[1609, 27], [0, 666]] | OK |
| Random Forest (Prec>=0.60) | 0.1 | 0.8097 | 0.6033 | 1.0 | 0.2677 | 0.7525 | 0.8838 | 0.0134 | 0.9995 | 0.9985 | [[1198, 438], [0, 666]] | OK |

---

## 3. Phân Tích Chồng Lấn Cửa Sổ (Window Overlap), Ablation & Tầm Dự Báo Tương Lai ($h \ge 1\text{h}$)

- Tại $h=0$, `pm25_rolling_mean_24h` ($[t-24, t-1]$) và nhãn mục tiêu $y_t$ ($[t-23, t]$) chồng lấn **23/24 (95,8%)** phần tử. Hiệu năng tiệm cận 1,0 phản ánh tính kế thừa của cửa sổ 24h hơn là khả năng dự báo dài hạn.
- Bảng thực nghiệm dưới đây tách riêng vai trò của đặc trưng tự hồi quy so với biến khí tượng thuần túy và kiểm tra sự suy giảm PR-AUC theo từng tầm dự báo $h \in \{0, 1, 6, 12, 24\}$ giờ (có áp dụng purge gap $t+h < t_{test}$):

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| h=0h | Full (Rolling24 + Lag24 + Met) | 2965 | 2302 | 666 | 0.2893 | 0.9989 | 0.9955 | 0.9985 | 1.0 | 0.992 | OK |
| h=0h | Lag24 + Met (No 24h Rolling) | 2965 | 2302 | 666 | 0.2893 | 0.7908 | 0.8529 | 0.7364 | 0.994 | 0.6904 | OK |
| h=0h | Meteorology + Time Only (No PM2.5) | 2994 | 2323 | 669 | 0.288 | 0.4338 | 1.0 | 0.5954 | 0.9985 | 0.6708 | OK |
| h=1h | Full Feature Set | 2936 | 2281 | 663 | 0.2907 | 0.9966 | 0.9804 | 0.9951 | 0.994 | 0.978 | OK |
| h=6h | Full Feature Set | 2803 | 2186 | 647 | 0.296 | 0.9696 | 0.8887 | 0.9509 | 1.0 | 0.7352 | OK |
| h=12h | Full Feature Set | 2647 | 2084 | 619 | 0.297 | 0.9094 | 0.7205 | 0.8586 | 0.9984 | 0.7423 | OK |
| h=24h | Full Feature Set | 2369 | 1893 | 543 | 0.2868 | 0.7513 | 0.6041 | 0.5876 | 1.0 | 0.7158 | OK |

---

## 4. Tầm Quan Trọng Biến (`average_precision`) & Logistic Regression Odds Ratios

- **3 đặc trưng đứng đầu theo Permutation PR-AUC:** pm25_rolling_mean_24h, pm25_lag24, pm25_rolling_std_24h.
- **Đánh giá trung thực về biến khí tượng ở $h=0$:** Các biến khí tượng/chu kỳ có Permutation Mean dương theo `average_precision`: wind_speed, month_cos, surface_pressure, temperature, relative_humidity, is_calm_wind; trong khi month_sin, precipitation, temp_humidity_interaction, hour_cos, hour_sin có đóng góp `<= 0` do bị biến tự hồi quy `pm25_rolling_mean_24h` che khuất ở tầm h=0.

| Feature | MDI Importance | Permutation Mean | Permutation Std | CI95 Low | CI95 High | LogReg Coef (RobustScaler) | Odds Ratio (exp(beta)) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pm25_rolling_mean_24h | 0.5763 | 0.474302 | 0.015432 | 0.467538 | 0.481065 | 11.5228 | 100990.2253 |
| pm25_lag24 | 0.0855 | 0.001424 | 0.000715 | 0.00111 | 0.001737 | -0.1148 | 0.8916 |
| pm25_rolling_std_24h | 0.0697 | 0.001 | 0.000623 | 0.000727 | 0.001273 | 0.2653 | 1.3039 |
| wind_speed | 0.0097 | 0.000407 | 0.000379 | 0.000241 | 0.000573 | -0.3781 | 0.6852 |
| month_cos | 0.0688 | 0.000192 | 0.000593 | -6.8e-05 | 0.000452 | 0.6283 | 1.8744 |
| surface_pressure | 0.0525 | 0.000139 | 0.000113 | 9e-05 | 0.000189 | 0.0252 | 1.0255 |
| temperature | 0.021 | 8.1e-05 | 0.000265 | -3.5e-05 | 0.000197 | -0.1931 | 0.8244 |
| relative_humidity | 0.0086 | 3.1e-05 | 6.2e-05 | 4e-06 | 5.9e-05 | -0.1592 | 0.8528 |
| is_calm_wind | 0.0002 | 1e-06 | 3e-06 | 0.0 | 3e-06 | -0.465 | 0.6281 |
| month_sin | 0.0248 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0754 | 1.0783 |
| precipitation | 0.004 | -1.2e-05 | 0.000124 | -6.6e-05 | 4.2e-05 | -0.0073 | 0.9928 |
| temp_humidity_interaction | 0.0725 | -3.5e-05 | 0.000384 | -0.000203 | 0.000134 | 0.5578 | 1.7469 |
| hour_cos | 0.0029 | -3.5e-05 | 6.1e-05 | -6.2e-05 | -9e-06 | -0.2601 | 0.7709 |
| hour_sin | 0.0034 | -0.000153 | 0.000143 | -0.000216 | -9e-05 | -0.0475 | 0.9536 |

---

## 5. Khả Năng Tổng Quát Hóa Thời Gian (Temporal Backtest) & Độ Nhạy Nội Suy Ngắn Hạn

| Fold | Train N | Val N | Val Positives | Val Prevalence | RF PR-AUC | RF Recall | RF Brier | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fold 1 | 495 | 494 | 9 | 0.0182 | 0.9627 | 1.0 | 0.0062 | OK |
| Fold 2 | 989 | 494 | 50 | 0.1012 | 0.9908 | 0.48 | 0.0261 | OK |
| Fold 3 | 1483 | 494 | 139 | 0.2814 | 0.9834 | 0.8129 | 0.0627 | OK |
| Fold 4 | 1977 | 494 | 411 | 0.832 | 0.9981 | 1.0 | 0.1012 | OK |
| Fold 5 | 2471 | 494 | 312 | 0.6316 | 0.9887 | 0.9936 | 0.0375 | OK |




---

## Phạm vi `VN001_extended_80_20` (`VN001_HANOI_556_NGUYEN_VAN_CU`)

- **Mốc cắt thời gian:** `2026-05-01 09:00:00+07:00` | **Tầm dự báo:** `h = 0h`
- **Kích thước evaluable:** Train = 5,025 / 7,235 giờ (Prevalence = 32.72% hợp lệ; 22.72% toàn lưới) | Test = 242 / 1,809 giờ (Prevalence = 0.00% hợp lệ; 0.00% toàn lưới)
- **Ngưỡng tối ưu OOF trên Train:** LogReg ($F_2$) $\tau^* = 0.47$, LogReg (`Prec>=0.60`) $\tau^* = 0.10$ | RF ($F_2$) $\tau^* = 0.28$, RF (`Prec>=0.60`) $\tau^* = 0.10$

### Bảng hiệu năng trên tập Test độc lập

| Model | Threshold | Accuracy | Precision | Recall | FAR | F1 | F2 | Brier | ROC-AUC | PR-AUC | Confusion Matrix [TN, FP, FN, TP] | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (Prior Dummy) | 0.5 | 1.0 | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE | UNESTIMABLE | 0.107 | UNESTIMABLE | UNESTIMABLE | [[242, 0], [0, 0]] | UNESTIMABLE (0 positives in Test) |
| Baseline (Persistence Rule >=50) | 0.5 | 1.0 | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE | UNESTIMABLE | 0.0696 | UNESTIMABLE | UNESTIMABLE | [[242, 0], [0, 0]] | UNESTIMABLE (0 positives in Test) |
| Logistic Regression (Balanced, F2) | 0.47 | 1.0 | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE | UNESTIMABLE | 0.0008 | UNESTIMABLE | UNESTIMABLE | [[242, 0], [0, 0]] | UNESTIMABLE (0 positives in Test) |
| Logistic Regression (Prec>=0.60) | 0.1 | 0.9669 | 0.0 | UNESTIMABLE | 0.0331 | UNESTIMABLE | UNESTIMABLE | 0.0008 | UNESTIMABLE | UNESTIMABLE | [[234, 8], [0, 0]] | UNESTIMABLE (0 positives in Test) |
| Random Forest (Balanced, F2) | 0.28 | 1.0 | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE | UNESTIMABLE | 0.0013 | UNESTIMABLE | UNESTIMABLE | [[242, 0], [0, 0]] | UNESTIMABLE (0 positives in Test) |
| Random Forest (Prec>=0.60) | 0.1 | 0.9876 | 0.0 | UNESTIMABLE | 0.0124 | UNESTIMABLE | UNESTIMABLE | 0.0013 | UNESTIMABLE | UNESTIMABLE | [[239, 3], [0, 0]] | UNESTIMABLE (0 positives in Test) |

### Ghi chú chẩn đoán ngưỡng trên OOF

- Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).
- Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).

### Đối soát 4 quần thể dữ liệu & gián đoạn quan trắc

| Quần thể | Total (giờ) | Train (giờ) | Test (giờ) | Positives Total | Positives Train | Positives Test | Prevalence (Train / Test) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Toàn bộ lưới thời gian (All grid) | 9044 | 7235 | 1809 | 1655 | 1655 | 0 | 22.87% / 0.00% |
| 2. Có quan trắc PM2.5 hợp lệ | 7495 | 6749 | 746 | 1655 | 1655 | 0 | 24.52% / 0.00% |
| 3. Đủ nhãn cửa sổ 24h (y_raw.notna()) | 5317 | 5068 | 249 | 1655 | 1655 | 0 | 32.66% / 0.00% |
| 4. Đủ nhãn & đặc trưng trễ 24h (Evaluable) | 5267 | 5025 | 242 | 1644 | 1644 | 0 | 32.72% / 0.00% |

**Top đợt gián đoạn PM2.5 liên tục dài nhất:**

| Start | End | Duration (hours) | Split |
| --- | --- | --- | --- |
| 2026-06-19 11:00:00+07:00 | 2026-07-15 16:00:00+07:00 | 630 | test |
| 2025-12-14 10:00:00+07:00 | 2025-12-16 13:00:00+07:00 | 52 | train |
| 2025-11-30 00:00:00+07:00 | 2025-12-01 12:00:00+07:00 | 37 | train |
| 2025-09-30 09:00:00+07:00 | 2025-10-01 08:00:00+07:00 | 24 | train |
| 2025-08-19 01:00:00+07:00 | 2025-08-19 23:00:00+07:00 | 23 | train |

### Thực nghiệm Cắt giảm Đặc trưng (Ablation) & Tầm dự báo $h \in \{0,1,6,12,24\}$

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| h=0h | Full (Rolling24 + Lag24 + Met) | 5025 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=0h | Lag24 + Met (No 24h Rolling) | 5025 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=0h | Meteorology + Time Only (No PM2.5) | 5068 | 249 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=1h | Full Feature Set | 4982 | 234 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=6h | Full Feature Set | 4779 | 204 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=12h | Full Feature Set | 4545 | 174 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=24h | Full Feature Set | 4123 | 127 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |

### Permutation Importance (`average_precision`) & Logistic Odds Ratios

| Feature | MDI Importance | Permutation Mean | Permutation Std | CI95 Low | CI95 High | LogReg Coef (RobustScaler) | Odds Ratio (exp(beta)) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pm25_rolling_mean_24h | 0.5874 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 13.8534 | 1038575.0091 |
| pm25_rolling_std_24h | 0.1369 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.4842 | 1.6228 |
| pm25_lag24 | 0.1055 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | -0.369 | 0.6914 |
| month_cos | 0.0519 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 1.0964 | 2.9935 |
| temp_humidity_interaction | 0.0346 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.2194 | 1.2453 |
| surface_pressure | 0.0294 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | -0.6741 | 0.5096 |
| temperature | 0.0163 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | -0.2437 | 0.7837 |
| month_sin | 0.0131 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.1231 | 1.131 |
| wind_speed | 0.0093 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | -0.284 | 0.7528 |
| relative_humidity | 0.0063 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | -0.2347 | 0.7908 |
| precipitation | 0.004 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | -0.1272 | 0.8806 |
| hour_cos | 0.0026 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0997 | 1.1048 |
| hour_sin | 0.0024 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.2319 | 1.261 |
| is_calm_wind | 0.0002 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | -0.3175 | 0.7279 |

### Expanding-Window Temporal Backtest (trên Train)

| Fold | Train N | Val N | Val Positives | Val Prevalence | RF PR-AUC | RF Recall | RF Brier | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fold 1 | 840 | 837 | 110 | 0.1314 | 0.9735 | 0.5182 | 0.036 | OK |
| Fold 2 | 1677 | 837 | 533 | 0.6368 | 0.987 | 0.9981 | 0.0663 | OK |
| Fold 3 | 2514 | 837 | 577 | 0.6894 | 0.9965 | 0.9965 | 0.0262 | OK |
| Fold 4 | 3351 | 837 | 173 | 0.2067 | 0.9859 | 0.9884 | 0.0118 | OK |
| Fold 5 | 4188 | 837 | 185 | 0.221 | 0.9993 | 0.9784 | 0.0117 | OK |

### Dịch chuyển theo năm trên tập Test

| Test Year | N (hours) | Positives | Prevalence | RF PR-AUC | RF Recall | RF FAR | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026 | 242 | 0 | 0.0 | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE (0 positives in Test) |

### Kiểm tra độ nhạy dùng `pm25_derived_interpolated` chỉ cho đặc trưng Train (nhãn luôn giữ observed)

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status | Train Recovered Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Observed-Only Features & Labels (Chính thức) | 5025 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) | 0 |
| Train Derived Features (<=3h) + Observed Labels | 5051 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) | 26 |


---

## Phạm vi `VN003_extended_2022_2025` (`VN003_HANOI_OPENAQ_7441`)

- **Mốc cắt thời gian:** `2024-08-13 23:00:00+07:00` | **Tầm dự báo:** `h = 0h`
- **Kích thước evaluable:** Train = 10,636 / 22,942 giờ (Prevalence = 25.17% hợp lệ; 11.67% toàn lưới) | Test = 3,439 / 5,736 giờ (Prevalence = 49.81% hợp lệ; 29.86% toàn lưới)
- **Ngưỡng tối ưu OOF trên Train:** LogReg ($F_2$) $\tau^* = 0.36$, LogReg (`Prec>=0.60`) $\tau^* = 0.10$ | RF ($F_2$) $\tau^* = 0.30$, RF (`Prec>=0.60`) $\tau^* = 0.10$

### Bảng hiệu năng trên tập Test độc lập

| Model | Threshold | Accuracy | Precision | Recall | FAR | F1 | F2 | Brier | ROC-AUC | PR-AUC | Confusion Matrix [TN, FP, FN, TP] | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (Prior Dummy) | 0.5 | 0.5019 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.3107 | 0.5 | 0.4981 | [[1726, 0], [1713, 0]] | OK |
| Baseline (Persistence Rule >=50) | 0.5 | 0.986 | 0.986 | 0.986 | 0.0139 | 0.986 | 0.986 | 0.0732 | 0.9992 | 0.9992 | [[1702, 24], [24, 1689]] | OK |
| Logistic Regression (Balanced, F2) | 0.36 | 0.9756 | 0.9553 | 0.9977 | 0.0463 | 0.976 | 0.9889 | 0.012 | 0.9994 | 0.9995 | [[1646, 80], [4, 1709]] | OK |
| Logistic Regression (Prec>=0.60) | 0.1 | 0.9529 | 0.9145 | 0.9988 | 0.0927 | 0.9548 | 0.9807 | 0.012 | 0.9994 | 0.9995 | [[1566, 160], [2, 1711]] | OK |
| Random Forest (Balanced, F2) | 0.3 | 0.9814 | 0.9703 | 0.993 | 0.0301 | 0.9815 | 0.9884 | 0.0135 | 0.9983 | 0.9983 | [[1674, 52], [12, 1701]] | OK |
| Random Forest (Prec>=0.60) | 0.1 | 0.9256 | 0.8707 | 0.9988 | 0.1472 | 0.9304 | 0.9703 | 0.0135 | 0.9983 | 0.9983 | [[1472, 254], [2, 1711]] | OK |

### Ghi chú chẩn đoán ngưỡng trên OOF

- Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).
- Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).

### Đối soát 4 quần thể dữ liệu & gián đoạn quan trắc

| Quần thể | Total (giờ) | Train (giờ) | Test (giờ) | Positives Total | Positives Train | Positives Test | Prevalence (Train / Test) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Toàn bộ lưới thời gian (All grid) | 28678 | 22942 | 5736 | 4435 | 2708 | 1727 | 11.80% / 30.11% |
| 2. Có quan trắc PM2.5 hợp lệ | 18208 | 13835 | 4373 | 4435 | 2708 | 1727 | 19.57% / 39.49% |
| 3. Đủ nhãn cửa sổ 24h (y_raw.notna()) | 14207 | 10737 | 3470 | 4435 | 2708 | 1727 | 25.22% / 49.77% |
| 4. Đủ nhãn & đặc trưng trễ 24h (Evaluable) | 14075 | 10636 | 3439 | 4390 | 2677 | 1713 | 25.17% / 49.81% |

**Top đợt gián đoạn PM2.5 liên tục dài nhất:**

| Start | End | Duration (hours) | Split |
| --- | --- | --- | --- |
| 2022-06-07 01:00:00+07:00 | 2022-09-22 00:00:00+07:00 | 2568 | train |
| 2023-02-16 08:00:00+07:00 | 2023-04-01 00:00:00+07:00 | 1049 | train |
| 2022-03-28 02:00:00+07:00 | 2022-05-09 21:00:00+07:00 | 1028 | train |
| 2024-08-07 11:00:00+07:00 | 2024-09-10 14:00:00+07:00 | 820 | train+test |
| 2023-11-07 16:00:00+07:00 | 2023-12-08 01:00:00+07:00 | 730 | train |

### Thực nghiệm Cắt giảm Đặc trưng (Ablation) & Tầm dự báo $h \in \{0,1,6,12,24\}$

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| h=0h | Full (Rolling24 + Lag24 + Met) | 10636 | 3439 | 1713 | 0.4981 | 0.9995 | 0.9977 | 0.9983 | 0.993 | 0.9884 | OK |
| h=0h | Lag24 + Met (No 24h Rolling) | 10636 | 3439 | 1713 | 0.4981 | 0.8811 | 0.9842 | 0.8762 | 0.9988 | 0.8423 | OK |
| h=0h | Meteorology + Time Only (No PM2.5) | 10737 | 3470 | 1727 | 0.4977 | 0.6839 | 0.9716 | 0.7169 | 0.9983 | 0.8333 | OK |
| h=1h | Full Feature Set | 10541 | 3408 | 1699 | 0.4985 | 0.998 | 0.9947 | 0.9953 | 0.9929 | 0.9815 | OK |
| h=6h | Full Feature Set | 10075 | 3253 | 1626 | 0.4998 | 0.9841 | 0.9889 | 0.9771 | 0.9908 | 0.9481 | OK |
| h=12h | Full Feature Set | 9535 | 3070 | 1542 | 0.5023 | 0.9589 | 0.9773 | 0.9483 | 0.9747 | 0.9149 | OK |
| h=24h | Full Feature Set | 8582 | 2754 | 1376 | 0.4996 | 0.8852 | 0.9462 | 0.8479 | 0.9273 | 0.8605 | OK |

### Permutation Importance (`average_precision`) & Logistic Odds Ratios

| Feature | MDI Importance | Permutation Mean | Permutation Std | CI95 Low | CI95 High | LogReg Coef (RobustScaler) | Odds Ratio (exp(beta)) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pm25_rolling_mean_24h | 0.6225 | 0.273909 | 0.009325 | 0.269822 | 0.277996 | 17.4469 | 37766535.5152 |
| pm25_rolling_std_24h | 0.1364 | 0.002201 | 0.000392 | 0.002029 | 0.002372 | 0.1587 | 1.172 |
| pm25_lag24 | 0.0768 | 0.000914 | 0.000199 | 0.000827 | 0.001001 | -0.8033 | 0.4479 |
| wind_speed | 0.0078 | 0.000312 | 0.000115 | 0.000262 | 0.000363 | -0.2716 | 0.7621 |
| temp_humidity_interaction | 0.0468 | 0.00029 | 0.000153 | 0.000223 | 0.000357 | -0.1469 | 0.8634 |
| precipitation | 0.0084 | 0.000157 | 0.000108 | 0.00011 | 0.000205 | -0.0031 | 0.9969 |
| temperature | 0.0175 | 7.9e-05 | 8.7e-05 | 4.1e-05 | 0.000117 | -0.0647 | 0.9374 |
| month_sin | 0.011 | 3.3e-05 | 9.1e-05 | -7e-06 | 7.3e-05 | 0.1268 | 1.1352 |
| relative_humidity | 0.0097 | 8e-06 | 6.8e-05 | -2.2e-05 | 3.8e-05 | -0.3653 | 0.694 |
| hour_sin | 0.0016 | 7e-06 | 4.5e-05 | -1.2e-05 | 2.7e-05 | -0.0573 | 0.9443 |
| hour_cos | 0.0018 | 7e-06 | 3.6e-05 | -8e-06 | 2.3e-05 | 0.1896 | 1.2087 |
| is_calm_wind | 0.0 | 1e-06 | 1e-06 | 0.0 | 1e-06 | -0.0199 | 0.9803 |
| surface_pressure | 0.0173 | -4.6e-05 | 6.1e-05 | -7.3e-05 | -1.9e-05 | -0.4641 | 0.6287 |
| month_cos | 0.0424 | -7.9e-05 | 0.000104 | -0.000125 | -3.4e-05 | 0.4117 | 1.5093 |

### Expanding-Window Temporal Backtest (trên Train)

| Fold | Train N | Val N | Val Positives | Val Prevalence | RF PR-AUC | RF Recall | RF Brier | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fold 1 | 1776 | 1772 | 1035 | 0.5841 | 0.9988 | 0.9043 | 0.0531 | OK |
| Fold 2 | 3548 | 1772 | 101 | 0.057 | 0.9504 | 0.9307 | 0.0128 | OK |
| Fold 3 | 5320 | 1772 | 395 | 0.2229 | 0.9942 | 0.9899 | 0.0139 | OK |
| Fold 4 | 7092 | 1772 | 451 | 0.2545 | 0.9956 | 0.9845 | 0.013 | OK |
| Fold 5 | 8864 | 1772 | 77 | 0.0435 | 0.9723 | 0.9481 | 0.0052 | OK |

### Dịch chuyển theo năm trên tập Test

| Test Year | N (hours) | Positives | Prevalence | RF PR-AUC | RF Recall | RF FAR | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 1576 | 873 | 0.5539 | 0.9986 | 0.992 | 0.0284 | OK |
| 2025 | 1863 | 840 | 0.4509 | 0.998 | 0.9917 | 0.0166 | OK |

### Kiểm tra độ nhạy dùng `pm25_derived_interpolated` chỉ cho đặc trưng Train (nhãn luôn giữ observed)

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status | Train Recovered Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Observed-Only Features & Labels (Chính thức) | 10636 | 3439 | 1713 | 0.4981 | 0.9995 | 0.9977 | 0.9983 | 0.993 | 0.9884 | OK | 0 |
| Train Derived Features (<=3h) + Observed Labels | 10702 | 3439 | 1713 | 0.4981 | 0.9995 | 0.9977 | 0.9985 | 0.993 | 0.9886 | OK | 66 |
