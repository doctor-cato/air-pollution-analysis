# Báo Cáo Kết Quả Mô Hình Phân Loại Cảnh Báo Ô Nhiễm (Truy Hồi Tức Thời & Đa Tầm) — Issue #13

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 11
> **Phạm vi chính:** `VN001_baseline_2026_01_15` (`VN001_HANOI_556_NGUYEN_VAN_CU`) | **Version:** `1.0.0-m2-baseline` | **SHA-256:** `866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd`
> **Mốc phân chia chuỗi thời gian:** `2026-01-15 00:00:00+07:00` | **Kích thước Evaluable:** Train = 2,965 giờ | Test = 2,302 giờ (666 ca dương tính)

---

## 0. Provenance Dữ Liệu & Đặc Tả Cohort

| Cohort | Station ID | Dataset Version | Dataset SHA-256 | Split Cut | Horizon | Feature Availability | Label Window & QCVN Standard | Train Valid / Grid (Pos) | Test Valid / Grid (Pos) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | VN001_HANOI_556_NGUYEN_VAN_CU | `1.0.0-m2-baseline` | `866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd` | 2026-01-15 00:00:00+07:00 | h=0h (ablation 0,1,6,12,24h) | 14 retrospective features: past-only PM2.5 (`t-1..t-24`, no `pm25_derived_interpolated` in primary) + Open-Meteo ERA5 (~5d reanalysis latency) + cyclic time; excludes `pm10`, `pm25_was_missing`, `is_high_humidity_fog` | Observed 24h rolling mean `pm25` (`min_periods=24`) >= 50.0 ug/m3 (QCVN 05:2023/BTNMT) | 2,965 / 4,682 (978 pos) | 2,302 / 4,362 (666 pos) |
| VN001_extended_80_20 | VN001_HANOI_556_NGUYEN_VAN_CU | `2.0.0-issue44-extended` | `6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02` | 2026-05-01 09:00:00+07:00 | h=0h (ablation 0,1,6,12,24h) | 14 retrospective features: past-only PM2.5 (`t-1..t-24`, no `pm25_derived_interpolated` in primary) + Open-Meteo ERA5 (~5d reanalysis latency) + cyclic time; excludes `pm10`, `pm25_was_missing`, `is_high_humidity_fog` | Observed 24h rolling mean `pm25` (`min_periods=24`) >= 50.0 ug/m3 (QCVN 05:2023/BTNMT) | 5,025 / 7,235 (1,644 pos) | 242 / 1,809 (0 pos) |
| VN003_extended_2022_2025 | VN003_HANOI_OPENAQ_7441 | `2.0.0-issue44-extended` | `6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02` | 2024-08-13 23:00:00+07:00 | h=0h (ablation 0,1,6,12,24h) | 14 retrospective features: past-only PM2.5 (`t-1..t-24`, no `pm25_derived_interpolated` in primary) + Open-Meteo ERA5 (~5d reanalysis latency) + cyclic time; excludes `pm10`, `pm25_was_missing`, `is_high_humidity_fog` | Observed 24h rolling mean `pm25` (`min_periods=24`) >= 50.0 ug/m3 (QCVN 05:2023/BTNMT) | 10,636 / 22,942 (2,677 pos) | 3,439 / 5,736 (1,713 pos) |

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

**Độ phủ & tỷ lệ thiếu dữ liệu theo năm & split:**

| Station | Year | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025 | train | 4346 | 3966 | 380 | 2808 | 2781 | 882 | 876 | 91.3 | 8.7 | 64.6 | 64.0 | 882/2,808 (31.41%) | 876/2,781 (31.50%) | 31.41 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026 | train | 336 | 313 | 23 | 186 | 184 | 104 | 102 | 93.2 | 6.8 | 55.4 | 54.8 | 104/186 (55.91%) | 102/184 (55.43%) | 55.91 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026 | test | 4362 | 3216 | 1146 | 2323 | 2302 | 669 | 666 | 73.7 | 26.3 | 53.3 | 52.8 | 669/2,323 (28.80%) | 666/2,302 (28.93%) | 28.8 |

**Độ phủ & tỷ lệ thiếu dữ liệu theo mùa khí tượng & split:**

| Station | Season | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_HANOI_556_NGUYEN_VAN_CU | Winter (Dec-Feb) | train | 1080 | 936 | 144 | 723 | 719 | 541 | 537 | 86.7 | 13.3 | 66.9 | 66.6 | 541/723 (74.83%) | 537/719 (74.69%) | 74.83 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Winter (Dec-Feb) | test | 1080 | 1022 | 58 | 841 | 835 | 411 | 409 | 94.6 | 5.4 | 77.9 | 77.3 | 411/841 (48.87%) | 409/835 (48.98%) | 48.87 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Spring (Mar-May) | test | 2208 | 2042 | 166 | 1482 | 1467 | 258 | 257 | 92.5 | 7.5 | 67.1 | 66.4 | 258/1,482 (17.41%) | 257/1,467 (17.52%) | 17.41 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Summer (Jun-Aug) | train | 1418 | 1326 | 92 | 1037 | 1028 | 67 | 66 | 93.5 | 6.5 | 73.1 | 72.5 | 67/1,037 (6.46%) | 66/1,028 (6.42%) | 6.46 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Summer (Jun-Aug) | test | 1074 | 152 | 922 | 0 | 0 | 0 | 0 | 14.2 | 85.8 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN001_HANOI_556_NGUYEN_VAN_CU | Autumn (Sep-Nov) | train | 2184 | 2017 | 167 | 1234 | 1218 | 378 | 375 | 92.4 | 7.6 | 56.5 | 55.8 | 378/1,234 (30.63%) | 375/1,218 (30.79%) | 30.63 |

**Độ phủ & tỷ lệ thiếu dữ liệu theo tháng & split:**

| Station | YearMonth | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-07 | train | 674 | 643 | 31 | 503 | 499 | 58 | 57 | 95.4 | 4.6 | 74.6 | 74.0 | 58/503 (11.53%) | 57/499 (11.42%) | 11.53 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-08 | train | 744 | 683 | 61 | 534 | 529 | 9 | 9 | 91.8 | 8.2 | 71.8 | 71.1 | 9/534 (1.69%) | 9/529 (1.70%) | 1.69 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-09 | train | 720 | 667 | 53 | 368 | 363 | 29 | 29 | 92.6 | 7.4 | 51.1 | 50.4 | 29/368 (7.88%) | 29/363 (7.99%) | 7.88 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-10 | train | 744 | 698 | 46 | 466 | 460 | 156 | 155 | 93.8 | 6.2 | 62.6 | 61.8 | 156/466 (33.48%) | 155/460 (33.70%) | 33.48 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-11 | train | 720 | 652 | 68 | 400 | 395 | 193 | 191 | 90.6 | 9.4 | 55.6 | 54.9 | 193/400 (48.25%) | 191/395 (48.35%) | 48.25 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-12 | train | 744 | 623 | 121 | 537 | 535 | 437 | 435 | 83.7 | 16.3 | 72.2 | 71.9 | 437/537 (81.38%) | 435/535 (81.31%) | 81.38 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-01 | train | 336 | 313 | 23 | 186 | 184 | 104 | 102 | 93.2 | 6.8 | 55.4 | 54.8 | 104/186 (55.91%) | 102/184 (55.43%) | 55.91 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-01 | test | 408 | 371 | 37 | 260 | 256 | 202 | 200 | 90.9 | 9.1 | 63.7 | 62.7 | 202/260 (77.69%) | 200/256 (78.12%) | 77.69 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-02 | test | 672 | 651 | 21 | 581 | 579 | 209 | 209 | 96.9 | 3.1 | 86.5 | 86.2 | 209/581 (35.97%) | 209/579 (36.10%) | 35.97 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-03 | test | 744 | 736 | 8 | 657 | 654 | 80 | 80 | 98.9 | 1.1 | 88.3 | 87.9 | 80/657 (12.18%) | 80/654 (12.23%) | 12.18 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-04 | test | 720 | 703 | 17 | 567 | 562 | 178 | 177 | 97.6 | 2.4 | 78.8 | 78.1 | 178/567 (31.39%) | 177/562 (31.49%) | 31.39 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-05 | test | 744 | 603 | 141 | 258 | 251 | 0 | 0 | 81.0 | 19.0 | 34.7 | 33.7 | 0/258 (0.00%) | 0/251 (0.00%) | 0.0 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-06 | test | 720 | 151 | 569 | 0 | 0 | 0 | 0 | 21.0 | 79.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-07 | test | 354 | 1 | 353 | 0 | 0 | 0 | 0 | 0.3 | 99.7 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |

**Top đợt gián đoạn PM2.5 liên tục dài nhất:**

| Start | End | Duration (hours) | Split |
| --- | --- | --- | --- |
| 2026-06-19 11:00:00+07:00 | 2026-07-15 16:00:00+07:00 | 630 | test |
| 2025-12-14 10:00:00+07:00 | 2025-12-16 13:00:00+07:00 | 52 | train |
| 2025-11-30 00:00:00+07:00 | 2025-12-01 12:00:00+07:00 | 37 | train |
| 2025-09-30 09:00:00+07:00 | 2025-10-01 08:00:00+07:00 | 24 | train |
| 2025-08-19 01:00:00+07:00 | 2025-08-19 23:00:00+07:00 | 23 | train |

---

## 2. Tổng Hợp Hiệu Năng Phân Loại Trên Tập Test Độc Lập (`VN001_baseline_2026_01_15`)

- **Bẫy Accuracy & Baseline tham chiếu:**
  - `DummyClassifier(strategy='prior')` đạt Accuracy = **71.07%**, nhưng Recall = **0.00%** và PR-AUC = **0.2893** (bằng đúng tỷ lệ dương tính của tập Test).
  - `PersistenceRuleClassifier` (ngưỡng cơ học 1 biến `pm25_rolling_mean_24h >= 50`) đạt Recall = **98.50%**, PR-AUC = **0.9992**.
- **Mô hình Học máy (ngưỡng $F_2$ tinh chỉnh hoàn toàn trên Train OOF & khóa trước khi chạm Test):**
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

### Đánh giá hiệu chuẩn xác suất (Calibration / Brier / ECE — `OK`)

- Ước lượng hợp lệ trên 2,302 mẫu (666 dương tính). Các bin có cỡ mẫu < 10 được đánh dấu thưa trên đường cong hiệu chuẩn (Reliability plot).

| Model | Brier Score | ECE (10 bins) | Bins (n >= 10) | Calibration Status |
| --- | --- | --- | --- | --- |
| Persistence Rule (>=50) | 0.0845 | 0.2592 | 10/10 non-empty | OK |
| Logistic Regression | 0.0143 | 0.0351 | 10/10 non-empty | OK |
| Random Forest | 0.0134 | 0.075 | 7/10 non-empty | OK |

---

## 3. Phân Tích Chồng Lấn Cửa Sổ (Window Overlap), Ablation & Tầm Dự Báo Tương Lai ($h \ge 1\text{h}$)

- Tại $h=0$, `pm25_rolling_mean_24h` ($[t-24, t-1]$) và nhãn mục tiêu $y_t$ ($[t-23, t]$) chồng lấn **23/24 (95,8%)** phần tử. Hiệu năng tiệm cận 1,0 phản ánh tính kế thừa của cửa sổ 24h hơn là khả năng dự báo dài hạn.
- Bảng thực nghiệm dưới đây tách riêng vai trò của đặc trưng tự hồi quy so với biến khí tượng thuần túy và kiểm tra sự suy giảm PR-AUC theo từng tầm dự báo $h \in \{0, 1, 6, 12, 24\}$ giờ (có áp dụng purge gap $t+h < t_{test}$):

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| h=0h — Full (Rolling24 + Lag24 + Met) | 2965 | 2302 | 666 | 0.2893 | 0.9989 | 0.9955 | 0.9985 | 1.0 | 0.992 | OK |
| h=0h — Lag24 + Met (No 24h Rolling) | 2965 | 2302 | 666 | 0.2893 | 0.7908 | 0.8529 | 0.7364 | 0.994 | 0.6904 | OK |
| h=0h — Meteorology + Time Only (No PM2.5) | 2994 | 2323 | 669 | 0.288 | 0.4338 | 1.0 | 0.5954 | 0.9985 | 0.6708 | OK |
| h=1h — Full Feature Set | 2936 | 2281 | 663 | 0.2907 | 0.9966 | 0.9804 | 0.9951 | 0.994 | 0.978 | OK |
| h=6h — Full Feature Set | 2803 | 2186 | 647 | 0.296 | 0.9696 | 0.8887 | 0.9509 | 1.0 | 0.7352 | OK |
| h=12h — Full Feature Set | 2647 | 2084 | 619 | 0.297 | 0.9094 | 0.7205 | 0.8586 | 0.9984 | 0.7423 | OK |
| h=24h — Full Feature Set | 2369 | 1893 | 543 | 0.2868 | 0.7513 | 0.6041 | 0.5876 | 1.0 | 0.7158 | OK |

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

### Logistic Regression Odds Ratios (trên không gian chuẩn hóa Train)

| Feature | LogReg Coef (RobustScaler) | Odds Ratio (exp(beta)) |
| --- | --- | --- |
| pm25_rolling_mean_24h | 11.5228 | 100990.2253 |
| month_cos | 0.6283 | 1.8744 |
| temp_humidity_interaction | 0.5578 | 1.7469 |
| is_calm_wind | -0.465 | 0.6281 |
| wind_speed | -0.3781 | 0.6852 |
| pm25_rolling_std_24h | 0.2653 | 1.3039 |
| hour_cos | -0.2601 | 0.7709 |
| temperature | -0.1931 | 0.8244 |
| relative_humidity | -0.1592 | 0.8528 |
| pm25_lag24 | -0.1148 | 0.8916 |
| month_sin | 0.0754 | 1.0783 |
| hour_sin | -0.0475 | 0.9536 |
| surface_pressure | 0.0252 | 1.0255 |
| precipitation | -0.0073 | 0.9928 |

---

## 5. Khả Năng Tổng Quát Hóa Thời Gian (Temporal Backtest), Dịch Chuyển & Độ Nhạy Nội Suy Ngắn Hạn

| Fold | Train N | Val N | Val Positives / N | Val Prevalence | Fold Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fold 1 | 495 | 494 | 9/494 | 0.0182 | 0.17 / 0.31 | 0.9627 | 1.0 | 0.0124 | 0.0062 | 0.6856 | 1.0 | OK |
| Fold 2 | 989 | 494 | 50/494 | 0.1012 | 0.20 / 0.36 | 0.9908 | 0.98 | 0.0068 | 0.0261 | 0.9899 | 1.0 | OK |
| Fold 3 | 1483 | 494 | 139/494 | 0.2814 | 0.45 / 0.75 | 0.9834 | 0.8633 | 0.0169 | 0.0627 | 0.9901 | 0.8417 | OK |
| Fold 4 | 1977 | 494 | 411/494 | 0.832 | 0.29 / 0.45 | 0.9981 | 1.0 | 0.0723 | 0.1012 | 0.9999 | 1.0 | OK |
| Fold 5 | 2471 | 494 | 312/494 | 0.6316 | 0.24 / 0.41 | 0.9887 | 1.0 | 0.5055 | 0.0375 | 0.9997 | 1.0 | OK |

### Dịch chuyển theo năm trên tập Test (dùng ngưỡng khóa chính thức)

| Test Year | Positives / N | Prevalence | Locked Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF Precision | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026 | 666/2302 | 0.2893 | 0.32 / 0.43 | 0.9985 | 1.0 | 0.961 | 0.0165 | 0.0134 | 0.9989 | 0.9955 | OK |

### Dịch chuyển theo tháng trên tập Test (dùng ngưỡng khóa chính thức)

| Test Month | Positives / N | Prevalence | Locked Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF Precision | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-01 | 200/256 | 0.7812 | 0.32 / 0.43 | 1.0 | 1.0 | 0.9901 | 0.0357 | 0.0104 | 1.0 | 1.0 | OK |
| 2026-02 | 209/579 | 0.361 | 0.32 / 0.43 | 0.9981 | 1.0 | 0.9414 | 0.0351 | 0.0192 | 0.999 | 1.0 | OK |
| 2026-03 | 80/654 | 0.1223 | 0.32 / 0.43 | 0.9987 | 1.0 | 0.9639 | 0.0052 | 0.0077 | 0.9976 | 0.9875 | OK |
| 2026-04 | 177/562 | 0.3149 | 0.32 / 0.43 | 0.9994 | 1.0 | 0.9516 | 0.0234 | 0.0179 | 0.9985 | 0.9887 | OK |
| 2026-05 | 0/251 | 0.0 | 0.32 / 0.43 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0 | 0.0075 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |


---

## Phạm vi `VN001_extended_80_20` (`VN001_HANOI_556_NGUYEN_VAN_CU`)

- **Dataset Version:** `2.0.0-issue44-extended` | **Dataset SHA-256:** `6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02`
- **Mốc cắt thời gian:** `2026-05-01 09:00:00+07:00` | **Tầm dự báo:** `h = 0h`
- **Kích thước evaluable:** Train = 5,025 / 7,235 giờ (Prevalence = 32.72% hợp lệ; 22.72% toàn lưới) | Test = 242 / 1,809 giờ (Prevalence = 0.00% hợp lệ; 0.00% toàn lưới)
- **Ngưỡng tối ưu OOF trên Train (khóa trước Test):** LogReg ($F_2$) $\tau^* = 0.47$, LogReg (`Prec>=0.60`) $\tau^* = 0.10$ | RF ($F_2$) $\tau^* = 0.28$, RF (`Prec>=0.60`) $\tau^* = 0.10$

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

- [LogReg (Prec>=0.60)] Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).
- [RF (Prec>=0.60)] Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).

### Đánh giá hiệu chuẩn xác suất (Calibration / Brier / ECE)

- **Trạng thái hiệu chuẩn:** `UNESTIMABLE` — UNESTIMABLE: Tập Test có 0/242 ca dương tính (đơn lớp); chỉ tính được Brier Score trên lớp âm, không thể dựng độ tin cậy thực nghiệm theo bin (Reliability curve) hay ECE.

| Model | Brier Score | ECE (10 bins) | Bins (n >= 10) | Calibration Status |
| --- | --- | --- | --- | --- |
| Persistence Rule (>=50) | 0.0696 | UNESTIMABLE | 0/10 | UNESTIMABLE (0 positives in Test) |
| Logistic Regression | 0.0008 | UNESTIMABLE | 0/10 | UNESTIMABLE (0 positives in Test) |
| Random Forest | 0.0013 | UNESTIMABLE | 0/10 | UNESTIMABLE (0 positives in Test) |

### Đối soát 4 quần thể dữ liệu & gián đoạn quan trắc

| Quần thể | Total (giờ) | Train (giờ) | Test (giờ) | Positives Total | Positives Train | Positives Test | Prevalence (Train / Test) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Toàn bộ lưới thời gian (All grid) | 9044 | 7235 | 1809 | 1655 | 1655 | 0 | 22.87% / 0.00% |
| 2. Có quan trắc PM2.5 hợp lệ | 7495 | 6749 | 746 | 1655 | 1655 | 0 | 24.52% / 0.00% |
| 3. Đủ nhãn cửa sổ 24h (y_raw.notna()) | 5317 | 5068 | 249 | 1655 | 1655 | 0 | 32.66% / 0.00% |
| 4. Đủ nhãn & đặc trưng trễ 24h (Evaluable) | 5267 | 5025 | 242 | 1644 | 1644 | 0 | 32.72% / 0.00% |

**Độ phủ & tỷ lệ thiếu dữ liệu theo năm & split:**

| Station | Year | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025 | train | 4346 | 3966 | 380 | 2808 | 2781 | 882 | 876 | 91.3 | 8.7 | 64.6 | 64.0 | 882/2,808 (31.41%) | 876/2,781 (31.50%) | 31.41 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026 | train | 2889 | 2783 | 106 | 2260 | 2244 | 773 | 768 | 96.3 | 3.7 | 78.2 | 77.7 | 773/2,260 (34.20%) | 768/2,244 (34.22%) | 34.2 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026 | test | 1809 | 746 | 1063 | 249 | 242 | 0 | 0 | 41.2 | 58.8 | 13.8 | 13.4 | 0/249 (0.00%) | 0/242 (0.00%) | 0.0 |

**Độ phủ & tỷ lệ thiếu dữ liệu theo mùa khí tượng & split:**

| Station | Season | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_HANOI_556_NGUYEN_VAN_CU | Winter (Dec-Feb) | train | 2160 | 1958 | 202 | 1564 | 1554 | 952 | 946 | 90.6 | 9.4 | 72.4 | 71.9 | 952/1,564 (60.87%) | 946/1,554 (60.88%) | 60.87 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Spring (Mar-May) | train | 1473 | 1448 | 25 | 1233 | 1225 | 258 | 257 | 98.3 | 1.7 | 83.7 | 83.2 | 258/1,233 (20.92%) | 257/1,225 (20.98%) | 20.92 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Spring (Mar-May) | test | 735 | 594 | 141 | 249 | 242 | 0 | 0 | 80.8 | 19.2 | 33.9 | 32.9 | 0/249 (0.00%) | 0/242 (0.00%) | 0.0 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Summer (Jun-Aug) | train | 1418 | 1326 | 92 | 1037 | 1028 | 67 | 66 | 93.5 | 6.5 | 73.1 | 72.5 | 67/1,037 (6.46%) | 66/1,028 (6.42%) | 6.46 |
| VN001_HANOI_556_NGUYEN_VAN_CU | Summer (Jun-Aug) | test | 1074 | 152 | 922 | 0 | 0 | 0 | 0 | 14.2 | 85.8 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN001_HANOI_556_NGUYEN_VAN_CU | Autumn (Sep-Nov) | train | 2184 | 2017 | 167 | 1234 | 1218 | 378 | 375 | 92.4 | 7.6 | 56.5 | 55.8 | 378/1,234 (30.63%) | 375/1,218 (30.79%) | 30.63 |

**Độ phủ & tỷ lệ thiếu dữ liệu theo tháng & split:**

| Station | YearMonth | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-07 | train | 674 | 643 | 31 | 503 | 499 | 58 | 57 | 95.4 | 4.6 | 74.6 | 74.0 | 58/503 (11.53%) | 57/499 (11.42%) | 11.53 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-08 | train | 744 | 683 | 61 | 534 | 529 | 9 | 9 | 91.8 | 8.2 | 71.8 | 71.1 | 9/534 (1.69%) | 9/529 (1.70%) | 1.69 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-09 | train | 720 | 667 | 53 | 368 | 363 | 29 | 29 | 92.6 | 7.4 | 51.1 | 50.4 | 29/368 (7.88%) | 29/363 (7.99%) | 7.88 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-10 | train | 744 | 698 | 46 | 466 | 460 | 156 | 155 | 93.8 | 6.2 | 62.6 | 61.8 | 156/466 (33.48%) | 155/460 (33.70%) | 33.48 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-11 | train | 720 | 652 | 68 | 400 | 395 | 193 | 191 | 90.6 | 9.4 | 55.6 | 54.9 | 193/400 (48.25%) | 191/395 (48.35%) | 48.25 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2025-12 | train | 744 | 623 | 121 | 537 | 535 | 437 | 435 | 83.7 | 16.3 | 72.2 | 71.9 | 437/537 (81.38%) | 435/535 (81.31%) | 81.38 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-01 | train | 744 | 684 | 60 | 446 | 440 | 306 | 302 | 91.9 | 8.1 | 59.9 | 59.1 | 306/446 (68.61%) | 302/440 (68.64%) | 68.61 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-02 | train | 672 | 651 | 21 | 581 | 579 | 209 | 209 | 96.9 | 3.1 | 86.5 | 86.2 | 209/581 (35.97%) | 209/579 (36.10%) | 35.97 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-03 | train | 744 | 736 | 8 | 657 | 654 | 80 | 80 | 98.9 | 1.1 | 88.3 | 87.9 | 80/657 (12.18%) | 80/654 (12.23%) | 12.18 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-04 | train | 720 | 703 | 17 | 567 | 562 | 178 | 177 | 97.6 | 2.4 | 78.8 | 78.1 | 178/567 (31.39%) | 177/562 (31.49%) | 31.39 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-05 | train | 9 | 9 | 0 | 9 | 9 | 0 | 0 | 100.0 | 0.0 | 100.0 | 100.0 | 0/9 (0.00%) | 0/9 (0.00%) | 0.0 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-05 | test | 735 | 594 | 141 | 249 | 242 | 0 | 0 | 80.8 | 19.2 | 33.9 | 32.9 | 0/249 (0.00%) | 0/242 (0.00%) | 0.0 |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-06 | test | 720 | 151 | 569 | 0 | 0 | 0 | 0 | 21.0 | 79.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN001_HANOI_556_NGUYEN_VAN_CU | 2026-07 | test | 354 | 1 | 353 | 0 | 0 | 0 | 0 | 0.3 | 99.7 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |

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
| h=0h — Full (Rolling24 + Lag24 + Met) | 5025 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=0h — Lag24 + Met (No 24h Rolling) | 5025 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=0h — Meteorology + Time Only (No PM2.5) | 5068 | 249 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=1h — Full Feature Set | 4982 | 234 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=6h — Full Feature Set | 4779 | 204 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=12h — Full Feature Set | 4545 | 174 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| h=24h — Full Feature Set | 4123 | 127 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |

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

| Fold | Train N | Val N | Val Positives / N | Val Prevalence | Fold Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fold 1 | 840 | 837 | 110/837 | 0.1314 | 0.10 / 0.17 | 0.9735 | 0.9909 | 0.0206 | 0.036 | 0.9551 | 1.0 | OK |
| Fold 2 | 1677 | 837 | 533/837 | 0.6368 | 0.21 / 0.42 | 0.987 | 1.0 | 0.0428 | 0.0663 | 0.9999 | 1.0 | OK |
| Fold 3 | 2514 | 837 | 577/837 | 0.6894 | 0.21 / 0.42 | 0.9965 | 0.9983 | 0.6923 | 0.0262 | 0.9996 | 1.0 | OK |
| Fold 4 | 3351 | 837 | 173/837 | 0.2067 | 0.28 / 0.47 | 0.9859 | 1.0 | 0.0151 | 0.0118 | 0.9985 | 1.0 | OK |
| Fold 5 | 4188 | 837 | 185/837 | 0.221 | 0.23 / 0.29 | 0.9993 | 1.0 | 0.0215 | 0.0117 | 0.9982 | 1.0 | OK |

### Dịch chuyển theo năm trên tập Test (dùng ngưỡng khóa chính thức)

| Test Year | Positives / N | Prevalence | Locked Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF Precision | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026 | 0/242 | 0.0 | 0.28 / 0.47 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0 | 0.0013 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |

### Dịch chuyển theo tháng trên tập Test (dùng ngưỡng khóa chính thức)

| Test Month | Positives / N | Prevalence | Locked Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF Precision | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05 | 0/242 | 0.0 | 0.28 / 0.47 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0 | 0.0013 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |

### Kiểm tra độ nhạy dùng `pm25_derived_interpolated` (`max_gap_hours=2` hai phía — chỉ cho đặc trưng Train, nhãn luôn giữ observed)

- **Lưu ý phương pháp:** Cột `pm25_derived_interpolated` sử dụng nội suy tuyến tính hai phía `max_gap_hours=2` từ Issue #44 (chế độ retrospective offline-only; không dùng cho vận hành real-time và không bao giờ thay nhãn quan trắc).

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status | Train Recovered Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Observed-Only Features & Labels (Chính thức) | 5025 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) | 0 |
| Train Derived Features (max_gap_hours=2) + Observed Labels | 5051 | 242 | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) | 26 |


---

## Phạm vi `VN003_extended_2022_2025` (`VN003_HANOI_OPENAQ_7441`)

- **Dataset Version:** `2.0.0-issue44-extended` | **Dataset SHA-256:** `6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02`
- **Mốc cắt thời gian:** `2024-08-13 23:00:00+07:00` | **Tầm dự báo:** `h = 0h`
- **Kích thước evaluable:** Train = 10,636 / 22,942 giờ (Prevalence = 25.17% hợp lệ; 11.67% toàn lưới) | Test = 3,439 / 5,736 giờ (Prevalence = 49.81% hợp lệ; 29.86% toàn lưới)
- **Ngưỡng tối ưu OOF trên Train (khóa trước Test):** LogReg ($F_2$) $\tau^* = 0.36$, LogReg (`Prec>=0.60`) $\tau^* = 0.10$ | RF ($F_2$) $\tau^* = 0.30$, RF (`Prec>=0.60`) $\tau^* = 0.10$

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

- [LogReg (Prec>=0.60)] Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).
- [RF (Prec>=0.60)] Cảnh báo bão hòa biên lưới (recall_constrained): tau*=0.10 chạm cận dưới 0.10 trên OOF (phổ xác suất phân tách mạnh hoặc đồng phẳng quanh cực trị hàm mục tiêu).

### Đánh giá hiệu chuẩn xác suất (Calibration / Brier / ECE)

- **Trạng thái hiệu chuẩn:** `OK` — Ước lượng hợp lệ trên 3,439 mẫu (1,713 dương tính). Các bin có cỡ mẫu < 10 được đánh dấu thưa trên đường cong hiệu chuẩn (Reliability plot).

| Model | Brier Score | ECE (10 bins) | Bins (n >= 10) | Calibration Status |
| --- | --- | --- | --- | --- |
| Persistence Rule (>=50) | 0.0732 | 0.216 | 10/10 non-empty | OK |
| Logistic Regression | 0.012 | 0.0176 | 10/10 non-empty | OK |
| Random Forest | 0.0135 | 0.0343 | 8/10 non-empty | OK |

### Đối soát 4 quần thể dữ liệu & gián đoạn quan trắc

| Quần thể | Total (giờ) | Train (giờ) | Test (giờ) | Positives Total | Positives Train | Positives Test | Prevalence (Train / Test) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Toàn bộ lưới thời gian (All grid) | 28678 | 22942 | 5736 | 4435 | 2708 | 1727 | 11.80% / 30.11% |
| 2. Có quan trắc PM2.5 hợp lệ | 18208 | 13835 | 4373 | 4435 | 2708 | 1727 | 19.57% / 39.49% |
| 3. Đủ nhãn cửa sổ 24h (y_raw.notna()) | 14207 | 10737 | 3470 | 4435 | 2708 | 1727 | 25.22% / 49.77% |
| 4. Đủ nhãn & đặc trưng trễ 24h (Evaluable) | 14075 | 10636 | 3439 | 4390 | 2677 | 1713 | 25.17% / 49.81% |

**Độ phủ & tỷ lệ thiếu dữ liệu theo năm & split:**

| Station | Year | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN003_HANOI_OPENAQ_7441 | 2022 | train | 8759 | 3079 | 5680 | 2311 | 2284 | 1067 | 1056 | 35.2 | 64.8 | 26.4 | 26.1 | 1,067/2,311 (46.17%) | 1,056/2,284 (46.23%) | 46.17 |
| VN003_HANOI_OPENAQ_7441 | 2023 | train | 8760 | 5646 | 3114 | 4384 | 4343 | 1045 | 1034 | 64.5 | 35.5 | 50.0 | 49.6 | 1,045/4,384 (23.84%) | 1,034/4,343 (23.81%) | 23.84 |
| VN003_HANOI_OPENAQ_7441 | 2024 | train | 5423 | 5110 | 313 | 4042 | 4009 | 596 | 587 | 94.2 | 5.8 | 74.5 | 73.9 | 596/4,042 (14.75%) | 587/4,009 (14.64%) | 14.75 |
| VN003_HANOI_OPENAQ_7441 | 2024 | test | 3361 | 2108 | 1253 | 1592 | 1576 | 879 | 873 | 62.7 | 37.3 | 47.4 | 46.9 | 879/1,592 (55.21%) | 873/1,576 (55.39%) | 55.21 |
| VN003_HANOI_OPENAQ_7441 | 2025 | test | 2375 | 2265 | 110 | 1878 | 1863 | 848 | 840 | 95.4 | 4.6 | 79.1 | 78.4 | 848/1,878 (45.15%) | 840/1,863 (45.09%) | 45.15 |

**Độ phủ & tỷ lệ thiếu dữ liệu theo mùa khí tượng & split:**

| Station | Season | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN003_HANOI_OPENAQ_7441 | Winter (Dec-Feb) | train | 5759 | 3979 | 1780 | 3103 | 3075 | 1437 | 1423 | 69.1 | 30.9 | 53.9 | 53.4 | 1,437/3,103 (46.31%) | 1,423/3,075 (46.28%) | 46.31 |
| VN003_HANOI_OPENAQ_7441 | Winter (Dec-Feb) | test | 2160 | 1579 | 581 | 1231 | 1218 | 688 | 681 | 73.1 | 26.9 | 57.0 | 56.4 | 688/1,231 (55.89%) | 681/1,218 (55.91%) | 55.89 |
| VN003_HANOI_OPENAQ_7441 | Spring (Mar-May) | train | 6624 | 3462 | 3162 | 2287 | 2249 | 495 | 485 | 52.3 | 47.7 | 34.5 | 34.0 | 495/2,287 (21.64%) | 485/2,249 (21.57%) | 21.64 |
| VN003_HANOI_OPENAQ_7441 | Spring (Mar-May) | test | 959 | 930 | 29 | 787 | 782 | 242 | 241 | 97.0 | 3.0 | 82.1 | 81.5 | 242/787 (30.75%) | 241/782 (30.82%) | 30.75 |
| VN003_HANOI_OPENAQ_7441 | Summer (Jun-Aug) | train | 6191 | 3799 | 2392 | 3241 | 3223 | 133 | 132 | 61.4 | 38.6 | 52.4 | 52.1 | 133/3,241 (4.10%) | 132/3,223 (4.10%) | 4.1 |
| VN003_HANOI_OPENAQ_7441 | Summer (Jun-Aug) | test | 433 | 0 | 433 | 0 | 0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN003_HANOI_OPENAQ_7441 | Autumn (Sep-Nov) | train | 4368 | 2595 | 1773 | 2106 | 2089 | 643 | 637 | 59.4 | 40.6 | 48.2 | 47.8 | 643/2,106 (30.53%) | 637/2,089 (30.49%) | 30.53 |
| VN003_HANOI_OPENAQ_7441 | Autumn (Sep-Nov) | test | 2184 | 1864 | 320 | 1452 | 1439 | 797 | 791 | 85.3 | 14.7 | 66.5 | 65.9 | 797/1,452 (54.89%) | 791/1,439 (54.97%) | 54.89 |

**Độ phủ & tỷ lệ thiếu dữ liệu theo tháng & split:**

| Station | YearMonth | Split | Grid Hours | Valid PM2.5 | Missing PM2.5 | Valid Label 24h | Evaluable | Positives (Valid y) | Positives (Eval) | Valid PM2.5 (%) | Missing PM2.5 (%) | Valid Label 24h (%) | Evaluable (%) | Positives / Valid y | Positives / Evaluable (Prevalence) | Positive Rate (% valid y) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN003_HANOI_OPENAQ_7441 | 2022-01 | train | 743 | 642 | 101 | 504 | 498 | 236 | 232 | 86.4 | 13.6 | 67.8 | 67.0 | 236/504 (46.83%) | 232/498 (46.59%) | 46.83 |
| VN003_HANOI_OPENAQ_7441 | 2022-02 | train | 672 | 97 | 575 | 51 | 49 | 1 | 0 | 14.4 | 85.6 | 7.6 | 7.3 | 1/51 (1.96%) | 0/49 (0.00%) | 1.96 |
| VN003_HANOI_OPENAQ_7441 | 2022-03 | train | 744 | 189 | 555 | 75 | 72 | 8 | 7 | 25.4 | 74.6 | 10.1 | 9.7 | 8/75 (10.67%) | 7/72 (9.72%) | 10.67 |
| VN003_HANOI_OPENAQ_7441 | 2022-04 | train | 720 | 0 | 720 | 0 | 0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN003_HANOI_OPENAQ_7441 | 2022-05 | train | 744 | 338 | 406 | 197 | 191 | 0 | 0 | 45.4 | 54.6 | 26.5 | 25.7 | 0/197 (0.00%) | 0/191 (0.00%) | 0.0 |
| VN003_HANOI_OPENAQ_7441 | 2022-06 | train | 720 | 97 | 623 | 74 | 73 | 0 | 0 | 13.5 | 86.5 | 10.3 | 10.1 | 0/74 (0.00%) | 0/73 (0.00%) | 0.0 |
| VN003_HANOI_OPENAQ_7441 | 2022-07 | train | 744 | 0 | 744 | 0 | 0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN003_HANOI_OPENAQ_7441 | 2022-08 | train | 744 | 0 | 744 | 0 | 0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN003_HANOI_OPENAQ_7441 | 2022-09 | train | 720 | 197 | 523 | 157 | 156 | 60 | 60 | 27.4 | 72.6 | 21.8 | 21.7 | 60/157 (38.22%) | 60/156 (38.46%) | 38.22 |
| VN003_HANOI_OPENAQ_7441 | 2022-10 | train | 744 | 79 | 665 | 53 | 52 | 40 | 39 | 10.6 | 89.4 | 7.1 | 7.0 | 40/53 (75.47%) | 39/52 (75.00%) | 75.47 |
| VN003_HANOI_OPENAQ_7441 | 2022-11 | train | 720 | 712 | 8 | 589 | 585 | 282 | 280 | 98.9 | 1.1 | 81.8 | 81.2 | 282/589 (47.88%) | 280/585 (47.86%) | 47.88 |
| VN003_HANOI_OPENAQ_7441 | 2022-12 | train | 744 | 728 | 16 | 611 | 608 | 440 | 438 | 97.8 | 2.2 | 82.1 | 81.7 | 440/611 (72.01%) | 438/608 (72.04%) | 72.01 |
| VN003_HANOI_OPENAQ_7441 | 2023-01 | train | 744 | 604 | 140 | 429 | 425 | 386 | 383 | 81.2 | 18.8 | 57.7 | 57.1 | 386/429 (89.98%) | 383/425 (90.12%) | 89.98 |
| VN003_HANOI_OPENAQ_7441 | 2023-02 | train | 672 | 80 | 592 | 57 | 56 | 33 | 33 | 11.9 | 88.1 | 8.5 | 8.3 | 33/57 (57.89%) | 33/56 (58.93%) | 57.89 |
| VN003_HANOI_OPENAQ_7441 | 2023-03 | train | 744 | 0 | 744 | 0 | 0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN003_HANOI_OPENAQ_7441 | 2023-04 | train | 720 | 262 | 458 | 155 | 151 | 115 | 113 | 36.4 | 63.6 | 21.5 | 21.0 | 115/155 (74.19%) | 113/151 (74.83%) | 74.19 |
| VN003_HANOI_OPENAQ_7441 | 2023-05 | train | 744 | 521 | 223 | 360 | 354 | 50 | 50 | 70.0 | 30.0 | 48.4 | 47.6 | 50/360 (13.89%) | 50/354 (14.12%) | 13.89 |
| VN003_HANOI_OPENAQ_7441 | 2023-06 | train | 720 | 670 | 50 | 599 | 597 | 18 | 18 | 93.1 | 6.9 | 83.2 | 82.9 | 18/599 (3.01%) | 18/597 (3.02%) | 3.01 |
| VN003_HANOI_OPENAQ_7441 | 2023-07 | train | 744 | 708 | 36 | 529 | 524 | 31 | 31 | 95.2 | 4.8 | 71.1 | 70.4 | 31/529 (5.86%) | 31/524 (5.92%) | 5.86 |
| VN003_HANOI_OPENAQ_7441 | 2023-08 | train | 744 | 738 | 6 | 652 | 649 | 24 | 23 | 99.2 | 0.8 | 87.6 | 87.2 | 24/652 (3.68%) | 23/649 (3.54%) | 3.68 |
| VN003_HANOI_OPENAQ_7441 | 2023-09 | train | 720 | 715 | 5 | 634 | 631 | 52 | 52 | 99.3 | 0.7 | 88.1 | 87.6 | 52/634 (8.20%) | 52/631 (8.24%) | 8.2 |
| VN003_HANOI_OPENAQ_7441 | 2023-10 | train | 744 | 736 | 8 | 585 | 579 | 185 | 183 | 98.9 | 1.1 | 78.6 | 77.8 | 185/585 (31.62%) | 183/579 (31.61%) | 31.62 |
| VN003_HANOI_OPENAQ_7441 | 2023-11 | train | 720 | 156 | 564 | 88 | 86 | 24 | 23 | 21.7 | 78.3 | 12.2 | 11.9 | 24/88 (27.27%) | 23/86 (26.74%) | 27.27 |
| VN003_HANOI_OPENAQ_7441 | 2023-12 | train | 744 | 456 | 288 | 296 | 291 | 127 | 125 | 61.3 | 38.7 | 39.8 | 39.1 | 127/296 (42.91%) | 125/291 (42.96%) | 42.91 |
| VN003_HANOI_OPENAQ_7441 | 2024-01 | train | 744 | 700 | 44 | 606 | 603 | 142 | 141 | 94.1 | 5.9 | 81.5 | 81.0 | 142/606 (23.43%) | 141/603 (23.38%) | 23.43 |
| VN003_HANOI_OPENAQ_7441 | 2024-02 | train | 696 | 672 | 24 | 549 | 545 | 72 | 71 | 96.6 | 3.4 | 78.9 | 78.3 | 72/549 (13.11%) | 71/545 (13.03%) | 13.11 |
| VN003_HANOI_OPENAQ_7441 | 2024-03 | train | 744 | 721 | 23 | 413 | 403 | 135 | 130 | 96.9 | 3.1 | 55.5 | 54.2 | 135/413 (32.69%) | 130/403 (32.26%) | 32.69 |
| VN003_HANOI_OPENAQ_7441 | 2024-04 | train | 720 | 703 | 17 | 519 | 515 | 157 | 155 | 97.6 | 2.4 | 72.1 | 71.5 | 157/519 (30.25%) | 155/515 (30.10%) | 30.25 |
| VN003_HANOI_OPENAQ_7441 | 2024-05 | train | 744 | 728 | 16 | 568 | 563 | 30 | 30 | 97.8 | 2.2 | 76.3 | 75.7 | 30/568 (5.28%) | 30/563 (5.33%) | 5.28 |
| VN003_HANOI_OPENAQ_7441 | 2024-06 | train | 720 | 710 | 10 | 625 | 621 | 60 | 60 | 98.6 | 1.4 | 86.8 | 86.2 | 60/625 (9.60%) | 60/621 (9.66%) | 9.6 |
| VN003_HANOI_OPENAQ_7441 | 2024-07 | train | 744 | 721 | 23 | 607 | 604 | 0 | 0 | 96.9 | 3.1 | 81.6 | 81.2 | 0/607 (0.00%) | 0/604 (0.00%) | 0.0 |
| VN003_HANOI_OPENAQ_7441 | 2024-08 | train | 311 | 155 | 156 | 155 | 155 | 0 | 0 | 49.8 | 50.2 | 49.8 | 49.8 | 0/155 (0.00%) | 0/155 (0.00%) | 0.0 |
| VN003_HANOI_OPENAQ_7441 | 2024-08 | test | 433 | 0 | 433 | 0 | 0 | 0 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0/0 (UNESTIMABLE) | 0/0 (UNESTIMABLE) | UNESTIMABLE |
| VN003_HANOI_OPENAQ_7441 | 2024-09 | test | 720 | 476 | 244 | 298 | 293 | 37 | 36 | 66.1 | 33.9 | 41.4 | 40.7 | 37/298 (12.42%) | 36/293 (12.29%) | 12.42 |
| VN003_HANOI_OPENAQ_7441 | 2024-10 | test | 744 | 678 | 66 | 560 | 556 | 299 | 297 | 91.1 | 8.9 | 75.3 | 74.7 | 299/560 (53.39%) | 297/556 (53.42%) | 53.39 |
| VN003_HANOI_OPENAQ_7441 | 2024-11 | test | 720 | 710 | 10 | 594 | 590 | 461 | 458 | 98.6 | 1.4 | 82.5 | 81.9 | 461/594 (77.61%) | 458/590 (77.63%) | 77.61 |
| VN003_HANOI_OPENAQ_7441 | 2024-12 | test | 744 | 244 | 500 | 140 | 137 | 82 | 82 | 32.8 | 67.2 | 18.8 | 18.4 | 82/140 (58.57%) | 82/137 (59.85%) | 58.57 |
| VN003_HANOI_OPENAQ_7441 | 2025-01 | test | 744 | 669 | 75 | 517 | 511 | 390 | 384 | 89.9 | 10.1 | 69.5 | 68.7 | 390/517 (75.44%) | 384/511 (75.15%) | 75.44 |
| VN003_HANOI_OPENAQ_7441 | 2025-02 | test | 672 | 666 | 6 | 574 | 570 | 216 | 215 | 99.1 | 0.9 | 85.4 | 84.8 | 216/574 (37.63%) | 215/570 (37.72%) | 37.63 |
| VN003_HANOI_OPENAQ_7441 | 2025-03 | test | 744 | 716 | 28 | 613 | 610 | 187 | 187 | 96.2 | 3.8 | 82.4 | 82.0 | 187/613 (30.51%) | 187/610 (30.66%) | 30.51 |
| VN003_HANOI_OPENAQ_7441 | 2025-04 | test | 215 | 214 | 1 | 174 | 172 | 55 | 54 | 99.5 | 0.5 | 80.9 | 80.0 | 55/174 (31.61%) | 54/172 (31.40%) | 31.61 |

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
| h=0h — Full (Rolling24 + Lag24 + Met) | 10636 | 3439 | 1713 | 0.4981 | 0.9995 | 0.9977 | 0.9983 | 0.993 | 0.9884 | OK |
| h=0h — Lag24 + Met (No 24h Rolling) | 10636 | 3439 | 1713 | 0.4981 | 0.8811 | 0.9842 | 0.8762 | 0.9988 | 0.8423 | OK |
| h=0h — Meteorology + Time Only (No PM2.5) | 10737 | 3470 | 1727 | 0.4977 | 0.6839 | 0.9716 | 0.7169 | 0.9983 | 0.8333 | OK |
| h=1h — Full Feature Set | 10541 | 3408 | 1699 | 0.4985 | 0.998 | 0.9947 | 0.9953 | 0.9929 | 0.9815 | OK |
| h=6h — Full Feature Set | 10075 | 3253 | 1626 | 0.4998 | 0.9841 | 0.9889 | 0.9771 | 0.9908 | 0.9481 | OK |
| h=12h — Full Feature Set | 9535 | 3070 | 1542 | 0.5023 | 0.9589 | 0.9773 | 0.9483 | 0.9747 | 0.9149 | OK |
| h=24h — Full Feature Set | 8582 | 2754 | 1376 | 0.4996 | 0.8852 | 0.9462 | 0.8479 | 0.9273 | 0.8605 | OK |

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

| Fold | Train N | Val N | Val Positives / N | Val Prevalence | Fold Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fold 1 | 1776 | 1772 | 1035/1772 | 0.5841 | 0.38 / 0.60 | 0.9988 | 0.9826 | 0.0149 | 0.0531 | 0.997 | 0.8995 | OK |
| Fold 2 | 3548 | 1772 | 101/1772 | 0.057 | 0.21 / 0.26 | 0.9504 | 0.9802 | 0.0281 | 0.0128 | 0.9549 | 0.9406 | OK |
| Fold 3 | 5320 | 1772 | 395/1772 | 0.2229 | 0.36 / 0.29 | 0.9942 | 0.9924 | 0.0174 | 0.0139 | 0.9983 | 1.0 | OK |
| Fold 4 | 7092 | 1772 | 451/1772 | 0.2545 | 0.27 / 0.35 | 0.9956 | 0.9956 | 0.0204 | 0.013 | 0.999 | 1.0 | OK |
| Fold 5 | 8864 | 1772 | 77/1772 | 0.0435 | 0.27 / 0.24 | 0.9723 | 0.961 | 0.0041 | 0.0052 | 0.9963 | 1.0 | OK |

### Dịch chuyển theo năm trên tập Test (dùng ngưỡng khóa chính thức)

| Test Year | Positives / N | Prevalence | Locked Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF Precision | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 873/1576 | 0.5539 | 0.30 / 0.36 | 0.9986 | 0.9931 | 0.972 | 0.0356 | 0.0145 | 0.9995 | 0.9977 | OK |
| 2025 | 840/1863 | 0.4509 | 0.30 / 0.36 | 0.998 | 0.9929 | 0.9686 | 0.0264 | 0.0126 | 0.9994 | 0.9976 | OK |

### Dịch chuyển theo tháng trên tập Test (dùng ngưỡng khóa chính thức)

| Test Month | Positives / N | Prevalence | Locked Tau (RF / LogReg) | RF PR-AUC | RF Recall | RF Precision | RF FAR | RF Brier | LogReg PR-AUC | LogReg Recall | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-09 | 36/293 | 0.1229 | 0.30 / 0.36 | 0.9958 | 0.9722 | 0.8974 | 0.0156 | 0.0111 | 0.9966 | 1.0 | OK |
| 2024-10 | 297/556 | 0.5342 | 0.30 / 0.36 | 0.9991 | 0.9933 | 0.9801 | 0.0232 | 0.0101 | 0.9998 | 0.9966 | OK |
| 2024-11 | 458/590 | 0.7763 | 0.30 / 0.36 | 0.9992 | 0.9978 | 0.9786 | 0.0758 | 0.016 | 0.9997 | 0.9978 | OK |
| 2024-12 | 82/137 | 0.5985 | 0.30 / 0.36 | 0.9965 | 0.9756 | 0.9412 | 0.0909 | 0.0331 | 0.9961 | 1.0 | OK |
| 2025-01 | 384/511 | 0.7515 | 0.30 / 0.36 | 0.9993 | 0.9948 | 0.9671 | 0.1024 | 0.0159 | 0.9997 | 0.9974 | OK |
| 2025-02 | 215/570 | 0.3772 | 0.30 / 0.36 | 0.9969 | 0.986 | 0.9725 | 0.0169 | 0.0129 | 0.9991 | 0.9953 | OK |
| 2025-03 | 187/610 | 0.3066 | 0.30 / 0.36 | 1.0 | 1.0 | 0.9842 | 0.0071 | 0.0056 | 1.0 | 1.0 | OK |
| 2025-04 | 54/172 | 0.314 | 0.30 / 0.36 | 0.9772 | 0.9815 | 0.9138 | 0.0424 | 0.0268 | 0.9972 | 1.0 | OK |

### Kiểm tra độ nhạy dùng `pm25_derived_interpolated` (`max_gap_hours=2` hai phía — chỉ cho đặc trưng Train, nhãn luôn giữ observed)

- **Lưu ý phương pháp:** Cột `pm25_derived_interpolated` sử dụng nội suy tuyến tính hai phía `max_gap_hours=2` từ Issue #44 (chế độ retrospective offline-only; không dùng cho vận hành real-time và không bao giờ thay nhãn quan trắc).

| Setting | n_train | n_test | Test Positives | Dummy PR-AUC | LogReg PR-AUC | LogReg Recall | RF PR-AUC | RF Recall | RF F2 | Status | Train Recovered Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Observed-Only Features & Labels (Chính thức) | 10636 | 3439 | 1713 | 0.4981 | 0.9995 | 0.9977 | 0.9983 | 0.993 | 0.9884 | OK | 0 |
| Train Derived Features (max_gap_hours=2) + Observed Labels | 10702 | 3439 | 1713 | 0.4981 | 0.9995 | 0.9977 | 0.9985 | 0.993 | 0.9886 | OK | 66 |
