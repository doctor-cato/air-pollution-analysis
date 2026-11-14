# Báo Cáo Kết Quả Mô Hình Hóa Hồi Quy OLS & Chẩn Đoán LINE — Issue #12

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 10 (kèm Scope Extension 2022–2026)
> **Biến mục tiêu:** `pm25` (µg/m³, giữ nguyên giá trị quan trắc thực)
- **Tuân thủ Protocol A vs Protocol B (Issue #44):** `VN003` (2022-01..2025-04) và `VN001` (2025-07..2026-07) có khoảng thời gian tách rời hoàn toàn và cách nhau khoảng trống 85 ngày; do đó bị CẤM gộp vào một phép chia Train/Test chung (Protocol B bị từ chối fail-closed), và được đánh giá độc lập theo từng trạm.

---

## 0. Tóm Tắt Nguồn Dữ Liệu & Đối Chiếu Đa Phạm Vi (Protocol A)

### Metadata Các Lượt Chạy Thực Nghiệm

| Run | Station | Date Window | Obs Hours | Grid Hours | Missing PM2.5 | Split Cut | Train / Test | Dataset SHA-256 (prefix) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | VN001_HANOI_556_NGUYEN_VAN_CU | 2025-07-03 22:00:00 .. 2026-07-15 17:00:00 | 7,495 | 9044 | 17.1% | 2026-01-15 00:00:00+07:00 | 4,279 / 3,216 | 866f39de1720 |
| VN001_extended_80_20 | VN001_HANOI_556_NGUYEN_VAN_CU | 2025-07-03 22:00:00 .. 2026-07-15 17:00:00 | 7,495 | 9044 | 17.1% | split=='train'/'test' (grid cut > 2026-05-01 08:00:00, last obs: 2026-05-01 08:00:00) | 6,749 / 746 | 6930557fbfc8 |
| VN003_extended_2022_2025 | VN003_HANOI_OPENAQ_7441 | 2022-01-01 01:00:00 .. 2025-04-09 22:00:00 | 18,208 | 28678 | 36.5% | split=='train'/'test' (grid cut > 2024-08-13 22:00:00, last obs: 2024-08-07 10:00:00) | 13,835 / 4,373 | 6930557fbfc8 |

### Bảng Đối Chiếu Hiệu Năng Tổng Hợp Trên Tập Test Độc Lập

| Run | Station | Train / Test | Dummy RMSE | OLS MAE | OLS RMSE | OLS Test R² | RESET(2) p | DW |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | VN001_HANOI_556_NGUYEN_VAN_CU | 4,279 / 3,216 | 24.46 | 37.32 | 41.46 | -1.954 | 3.02e-49 | 0.243 |
| VN001_extended_80_20 | VN001_HANOI_556_NGUYEN_VAN_CU | 6,749 / 746 | 24.15 | 15.63 | 21.12 | -0.1073 | 4.40e-130 | 0.208 |
| VN003_extended_2022_2025 | VN003_HANOI_OPENAQ_7441 | 13,835 / 4,373 | 37.73 | 23.98 | 32.82 | 0.1498 | 2.35e-54 | 0.303 |

---

## 1. Kết Quả Chi Tiết — `VN001_baseline_2026_01_15`

- **Trạm & Phạm vi:** `VN001_HANOI_556_NGUYEN_VAN_CU` | Nhãn chạy: `VN001_baseline_2026_01_15` | Chế độ split: `timestamp` (`2026-01-15 00:00:00+07:00`)
- **Kích thước mẫu:** Train = 4,279 giờ | Test = 3,216 giờ | Imputed feature cells = 0 (Train), 0 (Test)

### Kiểm Toán Đa Cộng Tuyến VIF
- Không có biến nào vượt ngưỡng đa cộng tuyến nghiêm trọng $\text{VIF} \ge 10$; tuy nhiên có 2 biến ở mức trung bình ($5 \le \text{VIF} < 10$): `surface_pressure` (8.06), `temperature` (7.66) (chấp nhận giữ lại có giám sát do mang thông tin nhiệt động lực học nền), các biến còn lại đều $< 5,0$.

| Feature | VIF |
| --- | --- |
| surface_pressure | 8.061 |
| temperature | 7.655 |
| month_cos | 4.47 |
| relative_humidity | 2.456 |
| month_sin | 2.301 |
| hour_cos | 2.063 |
| hour_sin | 1.404 |
| wind_speed | 1.138 |
| precipitation | 1.13 |

### Bảng Hệ Số OLS (Classical vs HAC Newey-West 24 lags)

| Feature | Coefficient (Beta) | SE (Classical) | p-Value (Classical) | SE (HAC-24) | p-Value (HAC-24) | 95% CI Lower (HAC) | 95% CI Upper (HAC) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| const | 309.9997 | 139.7387 | 0.0266 | 589.6235 | 0.5991 | -845.641 | 1465.6404 |
| temperature | 0.1664 | 0.1984 | 0.4017 | 0.7805 | 0.8312 | -1.3634 | 1.6961 |
| relative_humidity | 0.0638 | 0.0407 | 0.1173 | 0.1219 | 0.6005 | -0.1751 | 0.3027 |
| wind_speed | -6.0673 | 0.3029 | 2.27e-85 | 1.1173 | 5.63e-08 | -8.2572 | -3.8774 |
| precipitation | -0.9471 | 0.3448 | 0.0060 | 0.5424 | 0.0808 | -2.0102 | 0.116 |
| surface_pressure | -0.245 | 0.1345 | 0.0685 | 0.5659 | 0.6651 | -1.3542 | 0.8643 |
| hour_sin | 3.516 | 0.6141 | 1.10e-08 | 1.2907 | 0.0064 | 0.9862 | 6.0458 |
| hour_cos | 3.4884 | 0.7454 | 2.96e-06 | 1.4025 | 0.0129 | 0.7396 | 6.2373 |
| month_sin | 28.8563 | 1.2786 | 1.22e-106 | 5.0855 | 1.39e-08 | 18.889 | 38.8236 |
| month_cos | 12.3294 | 1.1395 | 6.15e-27 | 3.9078 | 0.0016 | 4.6702 | 19.9886 |

### Độ Nhạy HAC Newey-West Theo Độ Trễ L (plug-in NW = 9 giờ)

| lag_label | precipitation | relative_humidity | surface_pressure | temperature | wind_speed |
| --- | --- | --- | --- | --- | --- |
| 0 (HC1) | 0.0004 | 0.1568 | 0.1389 | 0.5092 | 7.14e-66 |
| 9 (NW plug-in) | 0.0477 | 0.5172 | 0.5599 | 0.7829 | 2.98e-12 |
| 12 | 0.0583 | 0.5422 | 0.5938 | 0.7984 | 1.14e-10 |
| 24 | 0.0808 | 0.6005 | 0.6651 | 0.8312 | 5.63e-08 |
| 48 | 0.0814 | 0.6490 | 0.7122 | 0.8537 | 1.76e-06 |
| 72 | 0.0807 | 0.6593 | 0.7254 | 0.8578 | 4.59e-06 |
| 168 | 0.0790 | 0.6658 | 0.7416 | 0.8523 | 7.38e-05 |

### Diễn Giải Hệ Số Theo 3 Nghĩa Vụ Học Thuật

- **Nhiệt độ (`temperature`) (dải quan sát Train [8.90; 36.60] °C):**
  - $\beta = +0.1664$ (SE HAC-24 = 0.7805, $p_{\text{HAC}} = 0.8312$, 95% CI $[-1.3634; 1.6961]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([8.90; 36.60] °C), mỗi khi biến tăng 1 °C, PM2.5 trung bình giờ **liên hệ với mức tăng** 0.17 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh độ ổn định nhiệt động lực học và đối lưu thẳng đứng của lớp biên.
- **Độ ẩm tương đối (`relative_humidity`) (dải quan sát Train [30.00; 100.00] %):**
  - $\beta = +0.0638$ (SE HAC-24 = 0.1219, $p_{\text{HAC}} = 0.6005$, 95% CI $[-0.1751; 0.3027]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([30.00; 100.00] %), mỗi khi biến tăng 1 %, PM2.5 trung bình giờ **liên hệ với mức tăng** 0.06 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh điều kiện ẩm bề mặt và khả năng hình thành sol khí thứ cấp.
- **Tốc độ gió (`wind_speed`) (dải quan sát Train [0.00; 9.55] m/s):**
  - $\beta = -6.0673$ (SE HAC-24 = 1.1173, $p_{\text{HAC}} = 5.63e-08$, 95% CI $[-8.2572; -3.8774]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([0.00; 9.55] m/s), mỗi khi biến tăng 1 m/s, PM2.5 trung bình giờ **liên hệ với mức giảm** 6.07 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh cơ chế khuếch tán ngang và thông gió khí quyển trong đô thị.
- **Lượng mưa (`precipitation`) (dải quan sát Train [0.00; 20.50] mm):**
  - $\beta = -0.9471$ (SE HAC-24 = 0.5424, $p_{\text{HAC}} = 0.0808$, 95% CI $[-2.0102; 0.1160]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([0.00; 20.50] mm), mỗi khi biến tăng 1 mm, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.95 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh quá trình rửa trôi ướt các hạt bụi mịn theo giờ.
- **Áp suất bề mặt (`surface_pressure`) (dải quan sát Train [986.50; 1028.40] hPa):**
  - $\beta = -0.2450$ (SE HAC-24 = 0.5659, $p_{\text{HAC}} = 0.6651$, 95% CI $[-1.3542; 0.8643]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([986.50; 1028.40] hPa), mỗi khi biến tăng 1 hPa, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.24 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh trạng thái xoáy thuận/khối khí áp cao quy mô synop.
- **Thành phần sin chu kỳ giờ (`hour_sin`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +3.5160$ (SE HAC-24 = 1.2907, $p_{\text{HAC}} = 0.0064$, 95% CI $[0.9862; 6.0458]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 3.52 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh biến thiên phát thải giao thông và co giãn chiều cao lớp trộn ngày đêm.
- **Thành phần cos chu kỳ giờ (`hour_cos`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +3.4884$ (SE HAC-24 = 1.4025, $p_{\text{HAC}} = 0.0129$, 95% CI $[0.7396; 6.2373]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 3.49 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh nhịp điều hòa pha ngày đêm giữa ban ngày và ban đêm.
- **Thành phần sin chu kỳ mùa (`month_sin`) (dải quan sát Train [-1.00; 0.50] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +28.8563$ (SE HAC-24 = 5.0855, $p_{\text{HAC}} = 1.39e-08$, 95% CI $[18.8890; 38.8236]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 0.50] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 28.86 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh biến thiên pha mùa trong năm (gió mùa Đông Bắc / Đông Nam).
- **Thành phần cos chu kỳ mùa (`month_cos`) (dải quan sát Train [-0.87; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +12.3294$ (SE HAC-24 = 3.9078, $p_{\text{HAC}} = 0.0016$, 95% CI $[4.6702; 19.9886]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-0.87; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 12.33 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh mức nền phân tầng nghịch nhiệt mùa đông so với mùa hè.

### Chẩn Đoán 4 Giả Định LINE & Điểm Ảnh Hưởng

| Giả Định | Kiểm Định / Chỉ Số | Giá Trị Đo Được | Kết Luận |
|---|---|---|---|
| **L – Linearity** | Ramsey RESET & Residuals Mean | Power=2: F = 223.27, p = 3.02e-49; Power=3: F = 116.26, p = 6.86e-50; mean = 2.51e-13 | **VI PHẠM:** Kiểm định Ramsey RESET bác bỏ tuyến tính bậc một nghiêm trọng ($p < 10^{-10}$); dù $\bar{e}$ và $\text{corr}(\hat{e}, \hat{y}) \approx 0$ theo đại số OLS. |
| **I – Independence** | Durbin-Watson & ACF | DW = 0.2430, ACF(1) = 0.8785, ACF(24) = 0.4019 | **VI PHẠM NẶNG:** Tự tương quan phần dư mạnh; bắt buộc dùng sai số chuẩn HAC. |
| **N – Normality** | Jarque-Bera & Skew/Kurtosis | JB = 392.7 (p = 5.32e-86), Skew = 0.554, Excess Kurtosis = 0.988, Shapiro W = 0.9791 (p = 1.27e-24) | **VI PHẠM:** Phân phối phần dư lệch phải và có đuôi dày trong các đợt ô nhiễm. |
| **E – Equal Variance** | Breusch-Pagan LM test | LM = 658.27 (p = 6.44e-136) | **VI PHẠM:** Phương sai sai số thay đổi theo điều kiện khí tượng và mùa vụ. |

- **Điểm đòn bẩy & Cook's Distance:** Regression Outliers ($|\text{stud\_resid}| > 3$) = 42; High Leverage ($h_{ii} > 0.00467$) = 137; Cook's $D > 4/n$ (0.000935) = 267 điểm (6.24%), $D > 0,5$ = 0, $D > 1,0$ = 0, $D_{\max} = 0.0174$. Giữ nguyên các điểm cực trị vì phản ánh các đợt nghịch nhiệt thực tế.
- **Khảo sát `log(1 + PM2.5)` trên Train:** Độ lệch phần dư chuyển từ `+0.554` ($|\text{skew}| = 0.554$) sang `-0.958` ($|\text{skew}| = 0.958$). Độ lệch tuyệt đối tăng lên nên giữ nguyên đơn vị gốc µg/m³.

### Top 10 Quan Sát Có Cook's Distance Cao Nhất Trên Train

| timestamp | pm25_obs | fitted | residual | stud_resid | leverage | cooks_d |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-07-22 05:00:00+07:00 | 72.66 | 0.93 | 71.72 | 3.021 | 0.01875 | 0.01741 |
| 2025-07-22 08:00:00+07:00 | 96.25 | 2.93 | 93.32 | 3.918 | 0.01091 | 0.01688 |
| 2025-07-22 09:00:00+07:00 | 86.81 | -2.28 | 89.09 | 3.741 | 0.01154 | 0.01629 |
| 2025-07-22 07:00:00+07:00 | 91.69 | 1.37 | 90.32 | 3.792 | 0.01113 | 0.01614 |
| 2025-07-22 06:00:00+07:00 | 89.0 | 2.38 | 86.62 | 3.636 | 0.01116 | 0.01488 |
| 2025-07-22 01:00:00+07:00 | 66.67 | 3.49 | 63.18 | 2.654 | 0.01345 | 0.00959 |
| 2025-11-29 03:00:00+07:00 | 153.56 | 69.95 | 83.61 | 3.501 | 0.00622 | 0.00765 |
| 2025-07-22 02:00:00+07:00 | 68.66 | 6.52 | 62.14 | 2.606 | 0.01045 | 0.00717 |
| 2025-11-29 02:00:00+07:00 | 156.54 | 67.65 | 88.9 | 3.721 | 0.00515 | 0.00714 |
| 2025-11-29 04:00:00+07:00 | 138.74 | 67.17 | 71.56 | 2.997 | 0.00698 | 0.0063 |

### Hiệu Năng Tập Test Độc Lập (MAE vs RMSE)

| Model | MAE (µg/m³) | RMSE (µg/m³) | R² | Adjusted R² |
| --- | --- | --- | --- | --- |
| Baseline (Dummy Mean) | 18.91 | 24.46 | -0.028 | -0.028 |
| OLS Linear Regression | 37.32 | 41.46 | -1.954 | -1.9623 |
| Ridge (alpha=754.312) | 35.89 | 39.97 | -1.7457 | -1.7534 |
| Lasso (alpha=1.526) | 38.02 | 41.91 | -2.0182 | -2.0267 |

- **Lý do dùng cả MAE và RMSE:** MAE đo sai số tuyệt đối điển hình ít nhạy với điểm cực trị đơn lẻ, trong khi RMSE phạt bình phương các sai số lớn ở đỉnh ô nhiễm (đặc trưng của phân phối lệch phải).

### Thử Nghiệm Ablation (Bỏ Chu Kỳ Mùa & Bổ Sung Autoregressive Lag 24h)

| Specification | n_train | n_test | Train R² | Test MAE (µg/m³) | Test RMSE (µg/m³) | Test R² | Mean Bias (Pred−Obs) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (Dummy Mean) | 4279 | 3216 | 0.0 | 18.91 | 24.46 | -0.028 | 4.04 |
| OLS Full (9 biến: khí tượng + giờ + mùa) | 4279 | 3216 | 0.3747 | 37.32 | 41.46 | -1.954 | 33.78 |
| OLS Bỏ chu kỳ mùa (7 biến: bỏ month_sin/cos) | 4279 | 3216 | 0.279 | 19.51 | 25.99 | -0.1604 | 1.35 |
| OLS Chỉ khí tượng (5 biến) | 4279 | 3216 | 0.2782 | 19.52 | 25.95 | -0.1568 | 1.31 |
| OLS Khí tượng + Giờ + pm25_lag24 (8 biến, AR) | 4013 | 3010 | 0.5277 | 15.31 | 21.12 | 0.2245 | -1.25 |

- **Giải phẫu dịch chuyển phân phối & hiệu ứng mùa vụ:** Mean PM2.5 Train = 45.50 vs Test = 41.46 µg/m³; Mean Pred OLS Full trên Test = 75.24 µg/m³ (bias = +33.78 µg/m³). Tỷ lệ Test nằm ngoài dải `month_sin` của Train = 65.0%. Khi bỏ `month_sin`/`month_cos`, Test $R^2$ đổi từ -1.9540 thành -0.1604; khi thêm trễ nội trạm `pm25_lag24`, Test $R^2$ đạt 0.2245.

### Rolling-Origin CV Trong Tập Train (5 Expanding Folds)

| Fold | n_train_fold | n_val_fold | Val Window | Dummy RMSE | OLS MAE | OLS RMSE | OLS R² |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 714 | 713 | 2025-08-03 → 2025-09-05 | 16.63 | 14.58 | 18.41 | -0.6382 |
| 2 | 1427 | 713 | 2025-09-05 → 2025-10-07 | 17.29 | 13.82 | 18.84 | -0.189 |
| 3 | 2140 | 713 | 2025-10-07 → 2025-11-08 | 20.79 | 18.03 | 23.45 | -0.278 |
| 4 | 2853 | 713 | 2025-11-08 → 2025-12-11 | 47.84 | 38.35 | 48.13 | -0.7649 |
| 5 | 3566 | 713 | 2025-12-12 → 2026-01-14 | 47.41 | 27.82 | 34.26 | 0.0738 |

### Độ Ổn Định Hệ Số Phân Tầng Theo Năm & Mùa (kèm n_eff)

| Stratum | n_obs | rho1_resid | n_eff | Train R² | wind_speed Beta | wind_speed p(HAC) | precip Beta | precip p(HAC) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Year 2025 | 3966 | 0.899 | 212 | 0.2364 | -6.18 | 4.72e-08 | -1.919 | 5.30e-06 |
| Year 2026 | 313 | 0.751 | 45 | 0.3795 | -19.916 | 3.70e-12 | 1.815 | 0.9119 |

---

## 2. Kết Quả Chi Tiết — `VN001_extended_80_20`

- **Trạm & Phạm vi:** `VN001_HANOI_556_NGUYEN_VAN_CU` | Nhãn chạy: `VN001_extended_80_20` | Chế độ split: `split_column_80_20` (`split=='train'/'test' (grid cut > 2026-05-01 08:00:00, last obs: 2026-05-01 08:00:00)`)
- **Kích thước mẫu:** Train = 6,749 giờ | Test = 746 giờ | Imputed feature cells = 0 (Train), 0 (Test)

### Kiểm Toán Đa Cộng Tuyến VIF
- Không có biến nào vượt ngưỡng đa cộng tuyến nghiêm trọng $\text{VIF} \ge 10$; tuy nhiên có 2 biến ở mức trung bình ($5 \le \text{VIF} < 10$): `surface_pressure` (5.96), `temperature` (5.73) (chấp nhận giữ lại có giám sát do mang thông tin nhiệt động lực học nền), các biến còn lại đều $< 5,0$.

| Feature | VIF |
| --- | --- |
| surface_pressure | 5.955 |
| temperature | 5.73 |
| month_cos | 3.068 |
| relative_humidity | 2.403 |
| hour_cos | 2.02 |
| hour_sin | 1.461 |
| month_sin | 1.392 |
| wind_speed | 1.121 |
| precipitation | 1.106 |

### Bảng Hệ Số OLS (Classical vs HAC Newey-West 24 lags)

| Feature | Coefficient (Beta) | SE (Classical) | p-Value (Classical) | SE (HAC-24) | p-Value (HAC-24) | 95% CI Lower (HAC) | 95% CI Upper (HAC) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| const | 839.7609 | 104.5664 | 1.13e-15 | 419.5346 | 0.0453 | 17.4882 | 1662.0337 |
| temperature | -0.4541 | 0.1415 | 0.0013 | 0.5923 | 0.4433 | -1.615 | 0.7068 |
| relative_humidity | -0.1144 | 0.0336 | 0.0007 | 0.1042 | 0.2725 | -0.3186 | 0.0899 |
| wind_speed | -7.2891 | 0.2408 | 8.03e-189 | 0.7769 | 6.48e-21 | -8.8118 | -5.7663 |
| precipitation | -0.9748 | 0.3182 | 0.0022 | 0.5218 | 0.0617 | -1.9975 | 0.0478 |
| surface_pressure | -0.7528 | 0.1003 | 7.11e-14 | 0.4009 | 0.0604 | -1.5385 | 0.0329 |
| hour_sin | 1.6003 | 0.5088 | 0.0017 | 1.1112 | 0.1498 | -0.5776 | 3.7781 |
| hour_cos | 1.1337 | 0.5989 | 0.0584 | 1.318 | 0.3897 | -1.4495 | 3.7168 |
| month_sin | 7.7003 | 0.4598 | 1.05e-61 | 1.4263 | 6.71e-08 | 4.9047 | 10.4958 |
| month_cos | 18.8838 | 0.8428 | 2.66e-107 | 2.7478 | 6.32e-12 | 13.4981 | 24.2694 |

### Độ Nhạy HAC Newey-West Theo Độ Trễ L (plug-in NW = 10 giờ)

| lag_label | precipitation | relative_humidity | surface_pressure | temperature | wind_speed |
| --- | --- | --- | --- | --- | --- |
| 0 (HC1) | 9.80e-05 | 0.0021 | 7.72e-11 | 0.0095 | 8.13e-171 |
| 10 (NW plug-in) | 0.0354 | 0.1796 | 0.0134 | 0.3167 | 1.67e-30 |
| 12 | 0.0414 | 0.1976 | 0.0195 | 0.3427 | 5.24e-28 |
| 24 | 0.0617 | 0.2725 | 0.0604 | 0.4433 | 6.48e-21 |
| 48 | 0.0633 | 0.3546 | 0.1194 | 0.5279 | 1.83e-16 |
| 72 | 0.0610 | 0.3879 | 0.1458 | 0.5556 | 5.95e-15 |
| 168 | 0.0537 | 0.4436 | 0.1841 | 0.5841 | 6.55e-12 |

### Diễn Giải Hệ Số Theo 3 Nghĩa Vụ Học Thuật

- **Nhiệt độ (`temperature`) (dải quan sát Train [8.90; 38.60] °C):**
  - $\beta = -0.4541$ (SE HAC-24 = 0.5923, $p_{\text{HAC}} = 0.4433$, 95% CI $[-1.6150; 0.7068]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([8.90; 38.60] °C), mỗi khi biến tăng 1 °C, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.45 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh độ ổn định nhiệt động lực học và đối lưu thẳng đứng của lớp biên.
- **Độ ẩm tương đối (`relative_humidity`) (dải quan sát Train [30.00; 100.00] %):**
  - $\beta = -0.1144$ (SE HAC-24 = 0.1042, $p_{\text{HAC}} = 0.2725$, 95% CI $[-0.3186; 0.0899]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([30.00; 100.00] %), mỗi khi biến tăng 1 %, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.11 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh điều kiện ẩm bề mặt và khả năng hình thành sol khí thứ cấp.
- **Tốc độ gió (`wind_speed`) (dải quan sát Train [0.00; 9.55] m/s):**
  - $\beta = -7.2891$ (SE HAC-24 = 0.7769, $p_{\text{HAC}} = 6.48e-21$, 95% CI $[-8.8118; -5.7663]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([0.00; 9.55] m/s), mỗi khi biến tăng 1 m/s, PM2.5 trung bình giờ **liên hệ với mức giảm** 7.29 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh cơ chế khuếch tán ngang và thông gió khí quyển trong đô thị.
- **Lượng mưa (`precipitation`) (dải quan sát Train [0.00; 20.50] mm):**
  - $\beta = -0.9748$ (SE HAC-24 = 0.5218, $p_{\text{HAC}} = 0.0617$, 95% CI $[-1.9975; 0.0478]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([0.00; 20.50] mm), mỗi khi biến tăng 1 mm, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.97 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh quá trình rửa trôi ướt các hạt bụi mịn theo giờ.
- **Áp suất bề mặt (`surface_pressure`) (dải quan sát Train [986.50; 1028.40] hPa):**
  - $\beta = -0.7528$ (SE HAC-24 = 0.4009, $p_{\text{HAC}} = 0.0604$, 95% CI $[-1.5385; 0.0329]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([986.50; 1028.40] hPa), mỗi khi biến tăng 1 hPa, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.75 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh trạng thái xoáy thuận/khối khí áp cao quy mô synop.
- **Thành phần sin chu kỳ giờ (`hour_sin`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +1.6003$ (SE HAC-24 = 1.1112, $p_{\text{HAC}} = 0.1498$, 95% CI $[-0.5776; 3.7781]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 1.60 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh biến thiên phát thải giao thông và co giãn chiều cao lớp trộn ngày đêm.
- **Thành phần cos chu kỳ giờ (`hour_cos`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +1.1337$ (SE HAC-24 = 1.3180, $p_{\text{HAC}} = 0.3897$, 95% CI $[-1.4495; 3.7168]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 1.13 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh nhịp điều hòa pha ngày đêm giữa ban ngày và ban đêm.
- **Thành phần sin chu kỳ mùa (`month_sin`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +7.7003$ (SE HAC-24 = 1.4263, $p_{\text{HAC}} = 6.71e-08$, 95% CI $[4.9047; 10.4958]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 7.70 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh biến thiên pha mùa trong năm (gió mùa Đông Bắc / Đông Nam).
- **Thành phần cos chu kỳ mùa (`month_cos`) (dải quan sát Train [-0.87; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +18.8838$ (SE HAC-24 = 2.7478, $p_{\text{HAC}} = 6.32e-12$, 95% CI $[13.4981; 24.2694]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-0.87; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 18.88 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh mức nền phân tầng nghịch nhiệt mùa đông so với mùa hè.

### Chẩn Đoán 4 Giả Định LINE & Điểm Ảnh Hưởng

| Giả Định | Kiểm Định / Chỉ Số | Giá Trị Đo Được | Kết Luận |
|---|---|---|---|
| **L – Linearity** | Ramsey RESET & Residuals Mean | Power=2: F = 615.42, p = 4.40e-130; Power=3: F = 330.60, p = 1.09e-137; mean = -1.14e-12 | **VI PHẠM:** Kiểm định Ramsey RESET bác bỏ tuyến tính bậc một nghiêm trọng ($p < 10^{-10}$); dù $\bar{e}$ và $\text{corr}(\hat{e}, \hat{y}) \approx 0$ theo đại số OLS. |
| **I – Independence** | Durbin-Watson & ACF | DW = 0.2079, ACF(1) = 0.8960, ACF(24) = 0.4475 | **VI PHẠM NẶNG:** Tự tương quan phần dư mạnh; bắt buộc dùng sai số chuẩn HAC. |
| **N – Normality** | Jarque-Bera & Skew/Kurtosis | JB = 1641.1 (p = 0.00e+00), Skew = 0.932, Excess Kurtosis = 1.536 (n > 5000 nên dùng Jarque-Bera) | **VI PHẠM:** Phân phối phần dư lệch phải và có đuôi dày trong các đợt ô nhiễm. |
| **E – Equal Variance** | Breusch-Pagan LM test | LM = 513.49 (p = 7.41e-105) | **VI PHẠM:** Phương sai sai số thay đổi theo điều kiện khí tượng và mùa vụ. |

- **Điểm đòn bẩy & Cook's Distance:** Regression Outliers ($|\text{stud\_resid}| > 3$) = 84; High Leverage ($h_{ii} > 0.00296$) = 216; Cook's $D > 4/n$ (0.000593) = 353 điểm (5.23%), $D > 0,5$ = 0, $D > 1,0$ = 0, $D_{\max} = 0.0174$. Giữ nguyên các điểm cực trị vì phản ánh các đợt nghịch nhiệt thực tế.
- **Khảo sát `log(1 + PM2.5)` trên Train:** Độ lệch phần dư chuyển từ `+0.932` ($|\text{skew}| = 0.932$) sang `-0.807` ($|\text{skew}| = 0.807$). Độ lệch tuyệt đối giảm nhẹ nhưng mô hình chính giữ đơn vị gốc µg/m³ để diễn giải trực tiếp với QCVN 05:2023.

### Top 10 Quan Sát Có Cook's Distance Cao Nhất Trên Train

| timestamp | pm25_obs | fitted | residual | stud_resid | leverage | cooks_d |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-07-22 05:00:00+07:00 | 72.66 | -10.95 | 83.61 | 3.445 | 0.01449 | 0.01742 |
| 2025-07-22 08:00:00+07:00 | 96.25 | -7.13 | 103.38 | 4.247 | 0.00771 | 0.01397 |
| 2025-07-22 07:00:00+07:00 | 91.69 | -10.38 | 102.07 | 4.193 | 0.00768 | 0.01357 |
| 2025-07-22 09:00:00+07:00 | 86.81 | -12.92 | 99.72 | 4.097 | 0.00791 | 0.01336 |
| 2025-07-22 06:00:00+07:00 | 89.0 | -9.63 | 98.64 | 4.052 | 0.00774 | 0.01278 |
| 2025-07-22 01:00:00+07:00 | 66.67 | -9.35 | 76.02 | 3.124 | 0.00983 | 0.00968 |
| 2025-07-22 02:00:00+07:00 | 68.66 | -6.21 | 74.88 | 3.073 | 0.0071 | 0.00674 |
| 2025-07-21 08:00:00+07:00 | 96.25 | 4.41 | 91.84 | 3.764 | 0.00354 | 0.00502 |
| 2025-07-22 00:00:00+07:00 | 67.4 | -3.08 | 70.48 | 2.89 | 0.00529 | 0.00444 |
| 2026-04-06 15:00:00+07:00 | 122.0 | 44.5 | 77.5 | 3.177 | 0.00435 | 0.0044 |

### Hiệu Năng Tập Test Độc Lập (MAE vs RMSE)

| Model | MAE (µg/m³) | RMSE (µg/m³) | R² | Adjusted R² |
| --- | --- | --- | --- | --- |
| Baseline (Dummy Mean) | 20.4 | 24.15 | -0.4487 | -0.4487 |
| OLS Linear Regression | 15.63 | 21.12 | -0.1073 | -0.1209 |
| Ridge (alpha=1000.000) | 16.6 | 21.11 | -0.1069 | -0.1205 |
| Lasso (alpha=1.151) | 15.87 | 20.61 | -0.0549 | -0.0678 |

- **Lý do dùng cả MAE và RMSE:** MAE đo sai số tuyệt đối điển hình ít nhạy với điểm cực trị đơn lẻ, trong khi RMSE phạt bình phương các sai số lớn ở đỉnh ô nhiễm (đặc trưng của phân phối lệch phải).

### Thử Nghiệm Ablation (Bỏ Chu Kỳ Mùa & Bổ Sung Autoregressive Lag 24h)

| Specification | n_train | n_test | Train R² | Test MAE (µg/m³) | Test RMSE (µg/m³) | Test R² | Mean Bias (Pred−Obs) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (Dummy Mean) | 6749 | 746 | 0.0 | 20.4 | 24.15 | -0.4487 | 13.44 |
| OLS Full (9 biến: khí tượng + giờ + mùa) | 6749 | 746 | 0.2541 | 15.63 | 21.12 | -0.1073 | -3.15 |
| OLS Bỏ chu kỳ mùa (7 biến: bỏ month_sin/cos) | 6749 | 746 | 0.1855 | 17.67 | 22.17 | -0.2201 | 5.37 |
| OLS Chỉ khí tượng (5 biến) | 6749 | 746 | 0.1847 | 17.78 | 22.28 | -0.2324 | 5.63 |
| OLS Khí tượng + Giờ + pm25_lag24 (8 biến, AR) | 6402 | 621 | 0.4512 | 13.44 | 17.5 | 0.0587 | 0.51 |

- **Giải phẫu dịch chuyển phân phối & hiệu ứng mùa vụ:** Mean PM2.5 Train = 45.10 vs Test = 31.66 µg/m³; Mean Pred OLS Full trên Test = 28.51 µg/m³ (bias = -3.15 µg/m³). Tỷ lệ Test nằm ngoài dải `month_sin` của Train = 0.0%. Khi bỏ `month_sin`/`month_cos`, Test $R^2$ đổi từ -0.1073 thành -0.2201; khi thêm trễ nội trạm `pm25_lag24`, Test $R^2$ đạt 0.0587.

### Rolling-Origin CV Trong Tập Train (5 Expanding Folds)

| Fold | n_train_fold | n_val_fold | Val Window | Dummy RMSE | OLS MAE | OLS RMSE | OLS R² |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1129 | 1124 | 2025-08-23 → 2025-10-12 | 17.69 | 19.98 | 25.93 | -1.1628 |
| 2 | 2253 | 1124 | 2025-10-12 → 2025-12-02 | 32.85 | 29.17 | 40.11 | -0.6507 |
| 3 | 3377 | 1124 | 2025-12-02 → 2026-01-25 | 47.04 | 26.68 | 33.12 | 0.0686 |
| 4 | 4501 | 1124 | 2026-01-25 → 2026-03-14 | 28.51 | 33.95 | 38.41 | -0.8334 |
| 5 | 5625 | 1124 | 2026-03-14 → 2026-05-01 | 19.65 | 14.71 | 20.06 | -0.2059 |

### Độ Ổn Định Hệ Số Phân Tầng Theo Năm & Mùa (kèm n_eff)

| Stratum | n_obs | rho1_resid | n_eff | Train R² | wind_speed Beta | wind_speed p(HAC) | precip Beta | precip p(HAC) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Year 2025 | 3966 | 0.899 | 212 | 0.2364 | -6.18 | 4.72e-08 | -1.919 | 5.30e-06 |
| Year 2026 | 2783 | 0.904 | 141 | 0.1915 | -9.132 | 2.23e-17 | -0.938 | 0.1277 |
| Season Summer (Jun-Aug) | 1326 | 0.855 | 104 | 0.1385 | -0.036 | 0.9728 | -1.026 | 0.0523 |
| Season Autumn (Sep-Nov) | 2017 | 0.861 | 150 | 0.2105 | -7.863 | 1.83e-10 | -1.467 | 0.0023 |
| Season Winter (Dec-Feb) | 1958 | 0.902 | 100 | 0.2571 | -12.464 | 1.07e-20 | -2.132 | 0.2167 |
| Season Spring (Mar-May) | 1448 | 0.862 | 108 | 0.2633 | -5.409 | 4.59e-09 | -0.621 | 0.2598 |

### Độ Nhạy Nội Suy Phái Sinh `pm25_derived_interpolated` (Chỉ Trong Train)

- Train quan trắc gốc: 6,749 giờ | Train + nội suy phái sinh ngắn: 6,866 giờ (+117 giờ); Test ground truth LUÔN giữ 100% quan trắc gốc (746 giờ).
- Sai khác hệ số lớn nhất (`max |ΔBeta|`) = 17.7253; Test RMSE (Observed vs Derived Train) = 21.12 vs 21.14 µg/m³ (R² = -0.1073 vs -0.1095).

| Feature | Beta (Observed Train) | Beta (Derived Train) | Abs Diff |
| --- | --- | --- | --- |
| const | 839.7609 | 857.4862 | 17.7253 |
| temperature | -0.4541 | -0.4115 | 0.0426 |
| relative_humidity | -0.1144 | -0.1007 | 0.0137 |
| wind_speed | -7.2891 | -7.3278 | 0.0387 |
| precipitation | -0.9748 | -0.9319 | 0.0429 |
| surface_pressure | -0.7528 | -0.7726 | 0.0198 |
| hour_sin | 1.6003 | 1.658 | 0.0577 |
| hour_cos | 1.1337 | 1.0389 | 0.0947 |
| month_sin | 7.7003 | 8.0063 | 0.306 |
| month_cos | 18.8838 | 19.1372 | 0.2534 |

---

## 3. Kết Quả Chi Tiết — `VN003_extended_2022_2025`

- **Trạm & Phạm vi:** `VN003_HANOI_OPENAQ_7441` | Nhãn chạy: `VN003_extended_2022_2025` | Chế độ split: `split_column_80_20` (`split=='train'/'test' (grid cut > 2024-08-13 22:00:00, last obs: 2024-08-07 10:00:00)`)
- **Kích thước mẫu:** Train = 13,835 giờ | Test = 4,373 giờ | Imputed feature cells = 0 (Train), 0 (Test)

### Kiểm Toán Đa Cộng Tuyến VIF
- Không có biến nào vượt ngưỡng đa cộng tuyến nghiêm trọng $\text{VIF} \ge 10$; tuy nhiên có 2 biến ở mức trung bình ($5 \le \text{VIF} < 10$): `surface_pressure` (6.24), `temperature` (5.82) (chấp nhận giữ lại có giám sát do mang thông tin nhiệt động lực học nền), các biến còn lại đều $< 5,0$.

| Feature | VIF |
| --- | --- |
| surface_pressure | 6.241 |
| temperature | 5.818 |
| month_cos | 3.362 |
| relative_humidity | 2.076 |
| hour_cos | 1.735 |
| month_sin | 1.461 |
| hour_sin | 1.367 |
| wind_speed | 1.124 |
| precipitation | 1.098 |

### Bảng Hệ Số OLS (Classical vs HAC Newey-West 24 lags)

| Feature | Coefficient (Beta) | SE (Classical) | p-Value (Classical) | SE (HAC-24) | p-Value (HAC-24) | 95% CI Lower (HAC) | 95% CI Upper (HAC) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| const | 746.2263 | 71.4609 | 1.97e-25 | 244.8736 | 0.0023 | 266.2829 | 1226.1697 |
| temperature | -0.238 | 0.0862 | 0.0057 | 0.3284 | 0.4685 | -0.8816 | 0.4055 |
| relative_humidity | -0.348 | 0.021 | 4.95e-61 | 0.0598 | 5.87e-09 | -0.4652 | -0.2308 |
| wind_speed | -6.2864 | 0.181 | 1.58e-253 | 0.4482 | 1.09e-44 | -7.1649 | -5.4079 |
| precipitation | -0.5524 | 0.2082 | 0.0080 | 0.2328 | 0.0177 | -1.0087 | -0.0961 |
| surface_pressure | -0.6476 | 0.0689 | 6.74e-21 | 0.2348 | 0.0058 | -1.1077 | -0.1875 |
| hour_sin | 1.1174 | 0.3479 | 0.0013 | 0.6273 | 0.0748 | -0.112 | 2.3468 |
| hour_cos | 3.0621 | 0.3923 | 6.30e-15 | 0.862 | 0.0004 | 1.3725 | 4.7516 |
| month_sin | 8.3053 | 0.3901 | 5.30e-99 | 1.1592 | 7.81e-13 | 6.0332 | 10.5773 |
| month_cos | 16.0745 | 0.511 | 8.30e-210 | 1.549 | 3.14e-25 | 13.0385 | 19.1105 |

### Độ Nhạy HAC Newey-West Theo Độ Trễ L (plug-in NW = 11 giờ)

| lag_label | precipitation | relative_humidity | surface_pressure | temperature | wind_speed |
| --- | --- | --- | --- | --- | --- |
| 0 (HC1) | 0.0001 | 1.00e-54 | 2.69e-18 | 0.0197 | 1.09e-280 |
| 11 (NW plug-in) | 0.0107 | 2.04e-11 | 0.0006 | 0.3621 | 2.41e-57 |
| 12 | 0.0114 | 4.26e-11 | 0.0008 | 0.3742 | 1.32e-55 |
| 24 | 0.0177 | 5.87e-09 | 0.0058 | 0.4685 | 1.09e-44 |
| 48 | 0.0288 | 4.25e-07 | 0.0231 | 0.5613 | 2.62e-36 |
| 72 | 0.0341 | 3.34e-06 | 0.0375 | 0.6033 | 5.73e-33 |
| 168 | 0.0505 | 3.72e-05 | 0.0717 | 0.6591 | 4.75e-26 |

### Diễn Giải Hệ Số Theo 3 Nghĩa Vụ Học Thuật

- **Nhiệt độ (`temperature`) (dải quan sát Train [6.70; 40.20] °C):**
  - $\beta = -0.2380$ (SE HAC-24 = 0.3284, $p_{\text{HAC}} = 0.4685$, 95% CI $[-0.8816; 0.4055]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([6.70; 40.20] °C), mỗi khi biến tăng 1 °C, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.24 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh độ ổn định nhiệt động lực học và đối lưu thẳng đứng của lớp biên.
- **Độ ẩm tương đối (`relative_humidity`) (dải quan sát Train [21.00; 100.00] %):**
  - $\beta = -0.3480$ (SE HAC-24 = 0.0598, $p_{\text{HAC}} = 5.87e-09$, 95% CI $[-0.4652; -0.2308]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([21.00; 100.00] %), mỗi khi biến tăng 1 %, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.35 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh điều kiện ẩm bề mặt và khả năng hình thành sol khí thứ cấp.
- **Tốc độ gió (`wind_speed`) (dải quan sát Train [0.00; 9.52] m/s):**
  - $\beta = -6.2864$ (SE HAC-24 = 0.4482, $p_{\text{HAC}} = 1.09e-44$, 95% CI $[-7.1649; -5.4079]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([0.00; 9.52] m/s), mỗi khi biến tăng 1 m/s, PM2.5 trung bình giờ **liên hệ với mức giảm** 6.29 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh cơ chế khuếch tán ngang và thông gió khí quyển trong đô thị.
- **Lượng mưa (`precipitation`) (dải quan sát Train [0.00; 24.10] mm):**
  - $\beta = -0.5524$ (SE HAC-24 = 0.2328, $p_{\text{HAC}} = 0.0177$, 95% CI $[-1.0087; -0.0961]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([0.00; 24.10] mm), mỗi khi biến tăng 1 mm, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.55 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh quá trình rửa trôi ướt các hạt bụi mịn theo giờ.
- **Áp suất bề mặt (`surface_pressure`) (dải quan sát Train [991.20; 1032.20] hPa):**
  - $\beta = -0.6476$ (SE HAC-24 = 0.2348, $p_{\text{HAC}} = 0.0058$, 95% CI $[-1.1077; -0.1875]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([991.20; 1032.20] hPa), mỗi khi biến tăng 1 hPa, PM2.5 trung bình giờ **liên hệ với mức giảm** 0.65 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh trạng thái xoáy thuận/khối khí áp cao quy mô synop.
- **Thành phần sin chu kỳ giờ (`hour_sin`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +1.1174$ (SE HAC-24 = 0.6273, $p_{\text{HAC}} = 0.0748$, 95% CI $[-0.1120; 2.3468]$). Chưa đủ bằng chứng thống kê độc lập ở mức 5% dưới HAC (*ceteris paribus*).
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 1.12 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh biến thiên phát thải giao thông và co giãn chiều cao lớp trộn ngày đêm.
- **Thành phần cos chu kỳ giờ (`hour_cos`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +3.0621$ (SE HAC-24 = 0.8620, $p_{\text{HAC}} = 0.0004$, 95% CI $[1.3725; 4.7516]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 3.06 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh nhịp điều hòa pha ngày đêm giữa ban ngày và ban đêm.
- **Thành phần sin chu kỳ mùa (`month_sin`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +8.3053$ (SE HAC-24 = 1.1592, $p_{\text{HAC}} = 7.81e-13$, 95% CI $[6.0332; 10.5773]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 8.31 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh biến thiên pha mùa trong năm (gió mùa Đông Bắc / Đông Nam).
- **Thành phần cos chu kỳ mùa (`month_cos`) (dải quan sát Train [-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]):**
  - $\beta = +16.0745$ (SE HAC-24 = 1.5490, $p_{\text{HAC}} = 3.14e-25$, 95% CI $[13.0385; 19.1105]$). Đạt ý nghĩa thống kê ở mức 5% dưới HAC.
  - *Diễn giải:* Trong miền giá trị quan sát trên Train ([-1.00; 1.00] đơn vị chuẩn hóa [-1, 1]), mỗi khi biến tăng 1 đơn vị chuẩn hóa [-1, 1], PM2.5 trung bình giờ **liên hệ với mức tăng** 16.07 µg/m³ trong điều kiện giữ nguyên các biến còn lại (*ceteris paribus*), phản ánh mức nền phân tầng nghịch nhiệt mùa đông so với mùa hè.

### Chẩn Đoán 4 Giả Định LINE & Điểm Ảnh Hưởng

| Giả Định | Kiểm Định / Chỉ Số | Giá Trị Đo Được | Kết Luận |
|---|---|---|---|
| **L – Linearity** | Ramsey RESET & Residuals Mean | Power=2: F = 243.15, p = 2.35e-54; Power=3: F = 122.83, p = 1.33e-53; mean = -1.37e-13 | **VI PHẠM:** Kiểm định Ramsey RESET bác bỏ tuyến tính bậc một nghiêm trọng ($p < 10^{-10}$); dù $\bar{e}$ và $\text{corr}(\hat{e}, \hat{y}) \approx 0$ theo đại số OLS. |
| **I – Independence** | Durbin-Watson & ACF | DW = 0.3033, ACF(1) = 0.8484, ACF(24) = 0.3451 | **VI PHẠM NẶNG:** Tự tương quan phần dư mạnh; bắt buộc dùng sai số chuẩn HAC. |
| **N – Normality** | Jarque-Bera & Skew/Kurtosis | JB = 51355.1 (p = 0.00e+00), Skew = 2.060, Excess Kurtosis = 8.492 (n > 5000 nên dùng Jarque-Bera) | **VI PHẠM:** Phân phối phần dư lệch phải và có đuôi dày trong các đợt ô nhiễm. |
| **E – Equal Variance** | Breusch-Pagan LM test | LM = 701.19 (p = 3.84e-145) | **VI PHẠM:** Phương sai sai số thay đổi theo điều kiện khí tượng và mùa vụ. |

- **Điểm đòn bẩy & Cook's Distance:** Regression Outliers ($|\text{stud\_resid}| > 3$) = 246; High Leverage ($h_{ii} > 0.00145$) = 441; Cook's $D > 4/n$ (0.000289) = 591 điểm (4.27%), $D > 0,5$ = 0, $D > 1,0$ = 0, $D_{\max} = 0.0072$. Giữ nguyên các điểm cực trị vì phản ánh các đợt nghịch nhiệt thực tế.
- **Khảo sát `log(1 + PM2.5)` trên Train:** Độ lệch phần dư chuyển từ `+2.060` ($|\text{skew}| = 2.060$) sang `-0.349` ($|\text{skew}| = 0.349$). Độ lệch tuyệt đối giảm nhẹ nhưng mô hình chính giữ đơn vị gốc µg/m³ để diễn giải trực tiếp với QCVN 05:2023.

### Top 10 Quan Sát Có Cook's Distance Cao Nhất Trên Train

| timestamp | pm25_obs | fitted | residual | stud_resid | leverage | cooks_d |
| --- | --- | --- | --- | --- | --- | --- |
| 2024-03-05 19:00:00+07:00 | 280.0 | 57.04 | 222.96 | 9.035 | 0.00089 | 0.0072 |
| 2022-12-20 07:00:00+07:00 | 225.0 | 58.89 | 166.11 | 6.725 | 0.0014 | 0.00631 |
| 2022-01-04 06:00:00+07:00 | 286.0 | 63.11 | 222.89 | 9.032 | 0.00074 | 0.00598 |
| 2022-01-04 09:00:00+07:00 | 283.0 | 63.19 | 219.81 | 8.906 | 0.0007 | 0.00555 |
| 2022-01-04 07:00:00+07:00 | 262.0 | 61.71 | 200.29 | 8.112 | 0.00078 | 0.00514 |
| 2022-01-04 08:00:00+07:00 | 270.0 | 61.52 | 208.48 | 8.445 | 0.00072 | 0.00508 |
| 2024-02-10 00:00:00+07:00 | 230.0 | 65.94 | 164.06 | 6.64 | 0.00111 | 0.00487 |
| 2022-12-16 05:00:00+07:00 | 232.0 | 59.99 | 172.01 | 6.963 | 0.001 | 0.00485 |
| 2022-12-16 22:00:00+07:00 | 241.0 | 56.67 | 184.33 | 7.463 | 0.00076 | 0.00422 |
| 2023-12-27 04:00:00+07:00 | 251.0 | 57.85 | 193.15 | 7.821 | 0.00069 | 0.00421 |

### Hiệu Năng Tập Test Độc Lập (MAE vs RMSE)

| Model | MAE (µg/m³) | RMSE (µg/m³) | R² | Adjusted R² |
| --- | --- | --- | --- | --- |
| Baseline (Dummy Mean) | 26.42 | 37.73 | -0.1235 | -0.1235 |
| OLS Linear Regression | 23.98 | 32.82 | 0.1498 | 0.1481 |
| Ridge (alpha=59.636) | 24.0 | 32.91 | 0.1456 | 0.1438 |
| Lasso (alpha=0.281) | 23.98 | 33.06 | 0.1377 | 0.1359 |

- **Lý do dùng cả MAE và RMSE:** MAE đo sai số tuyệt đối điển hình ít nhạy với điểm cực trị đơn lẻ, trong khi RMSE phạt bình phương các sai số lớn ở đỉnh ô nhiễm (đặc trưng của phân phối lệch phải).

### Thử Nghiệm Ablation (Bỏ Chu Kỳ Mùa & Bổ Sung Autoregressive Lag 24h)

| Specification | n_train | n_test | Train R² | Test MAE (µg/m³) | Test RMSE (µg/m³) | Test R² | Mean Bias (Pred−Obs) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (Dummy Mean) | 13835 | 4373 | 0.0 | 26.42 | 37.73 | -0.1235 | -12.51 |
| OLS Full (9 biến: khí tượng + giờ + mùa) | 13835 | 4373 | 0.2329 | 23.98 | 32.82 | 0.1498 | -3.79 |
| OLS Bỏ chu kỳ mùa (7 biến: bỏ month_sin/cos) | 13835 | 4373 | 0.1723 | 24.86 | 34.27 | 0.0735 | -5.81 |
| OLS Chỉ khí tượng (5 biến) | 13835 | 4373 | 0.1703 | 24.88 | 34.26 | 0.0738 | -5.86 |
| OLS Khí tượng + Giờ + pm25_lag24 (8 biến, AR) | 12871 | 4206 | 0.3476 | 20.27 | 28.7 | 0.349 | -2.69 |

- **Giải phẫu dịch chuyển phân phối & hiệu ứng mùa vụ:** Mean PM2.5 Train = 42.82 vs Test = 55.33 µg/m³; Mean Pred OLS Full trên Test = 51.54 µg/m³ (bias = -3.79 µg/m³). Tỷ lệ Test nằm ngoài dải `month_sin` của Train = 0.0%. Khi bỏ `month_sin`/`month_cos`, Test $R^2$ đổi từ 0.1498 thành 0.0735; khi thêm trễ nội trạm `pm25_lag24`, Test $R^2$ đạt 0.3490.

### Rolling-Origin CV Trong Tập Train (5 Expanding Folds)

| Fold | n_train_fold | n_val_fold | Val Window | Dummy RMSE | OLS MAE | OLS RMSE | OLS R² |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2310 | 2305 | 2022-11-29 → 2023-06-03 | 38.47 | 24.7 | 36.19 | -0.016 |
| 2 | 4615 | 2305 | 2023-06-03 → 2023-09-11 | 28.28 | 16.1 | 19.76 | -0.3906 |
| 3 | 6920 | 2305 | 2023-09-11 → 2024-01-23 | 26.71 | 19.34 | 25.44 | 0.0837 |
| 4 | 9225 | 2305 | 2024-01-23 → 2024-05-01 | 24.97 | 19.17 | 26.13 | -0.1083 |
| 5 | 11530 | 2305 | 2024-05-01 → 2024-08-07 | 23.71 | 12.14 | 18.56 | -0.0472 |

### Độ Ổn Định Hệ Số Phân Tầng Theo Năm & Mùa (kèm n_eff)

| Stratum | n_obs | rho1_resid | n_eff | Train R² | wind_speed Beta | wind_speed p(HAC) | precip Beta | precip p(HAC) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Year 2022 | 3079 | 0.874 | 207 | 0.1718 | -9.507 | 1.05e-16 | -1.696 | 0.0075 |
| Year 2023 | 5646 | 0.836 | 504 | 0.2685 | -5.447 | 1.49e-13 | -1.722 | 8.17e-05 |
| Year 2024 | 5110 | 0.863 | 376 | 0.064 | -2.958 | 7.40e-06 | -1.753 | 6.53e-06 |
| Season Winter (Dec-Feb) | 3979 | 0.878 | 259 | 0.1687 | -10.689 | 2.51e-25 | -12.092 | 0.0103 |
| Season Spring (Mar-May) | 3462 | 0.855 | 270 | 0.0886 | -2.574 | 0.0002 | -1.351 | 0.0026 |
| Season Summer (Jun-Aug) | 3799 | 0.779 | 472 | 0.0315 | -2.589 | 3.02e-06 | -0.543 | 0.0309 |
| Season Autumn (Sep-Nov) | 2595 | 0.789 | 305 | 0.1798 | -8.601 | 2.02e-21 | -1.241 | 0.1365 |

### Độ Nhạy Nội Suy Phái Sinh `pm25_derived_interpolated` (Chỉ Trong Train)

- Train quan trắc gốc: 13,835 giờ | Train + nội suy phái sinh ngắn: 13,985 giờ (+150 giờ); Test ground truth LUÔN giữ 100% quan trắc gốc (4,373 giờ).
- Sai khác hệ số lớn nhất (`max |ΔBeta|`) = 2.6827; Test RMSE (Observed vs Derived Train) = 32.82 vs 32.83 µg/m³ (R² = 0.1498 vs 0.1496).

| Feature | Beta (Observed Train) | Beta (Derived Train) | Abs Diff |
| --- | --- | --- | --- |
| const | 746.2263 | 748.909 | 2.6827 |
| temperature | -0.238 | -0.2277 | 0.0104 |
| relative_humidity | -0.348 | -0.3503 | 0.0023 |
| wind_speed | -6.2864 | -6.2998 | 0.0134 |
| precipitation | -0.5524 | -0.5358 | 0.0166 |
| surface_pressure | -0.6476 | -0.6503 | 0.0027 |
| hour_sin | 1.1174 | 1.1668 | 0.0494 |
| hour_cos | 3.0621 | 3.0607 | 0.0014 |
| month_sin | 8.3053 | 8.4516 | 0.1464 |
| month_cos | 16.0745 | 16.151 | 0.0766 |
