# Tổng Hợp Phát Hiện Khoa Học: Mô Hình Phân Loại Cảnh Báo Ô Nhiễm PM2.5 — Task D13 (Issue #13)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Phạm vi dữ liệu chính:** `VN001_baseline_2026_01_15` (`VN001_HANOI_556_NGUYEN_VAN_CU`, cắt thời gian `2026-01-15 00:00:00+07:00`)
> **Tập Test độc lập:** 2,302 giờ hợp lệ (trong 4,362 giờ lưới; **666 ca dương tính**, Prevalence = 28.93% trên mẫu hợp lệ / 15.27% trên tổng lưới)

---

## 1. Bản Chất Khoa Học: Truy Hồi Tức Thời ($h=0$) vs Dự Báo Tương Lai ($h > 0$)

1. **Tương thích chu kỳ quy chuẩn QCVN 05:2023/BTNMT:** Nhãn mục tiêu $y_t = \mathbb{I}(\overline{\text{PM}_{2.5}}_{[t-23, t]} \ge 50,0\ \mu\text{g/m}^3)$ giữ nguyên tính bất khả xâm phạm của giá trị quan trắc gốc (không nội suy nhãn).
2. **Minh bạch độ trễ dữ liệu ERA5 (Không gọi sai là real-time):** Khí tượng Open-Meteo ERA5 là dữ liệu tái phân tích (reanalysis) có độ trễ phát hành ~5 ngày; do đó thiết lập tại h = 0 giờ mang bản chất truy hồi tức thời lịch sử (retrospective nowcast), không phải vận hành thời gian thực trừ khi thay bằng dữ liệu quan trắc/dự báo NWP trực tuyến.
3. **Tách biệt tín hiệu tự hồi quy vs khí tượng:**
   - Ở $h=0$, `pm25_rolling_mean_24h` ($[t-24, t-1]$) chia sẻ **23/24 giờ (95,8%)** với $y_t$, giúp cả `PersistenceRuleClassifier` lẫn `LogisticRegression`/`RandomForest` đạt hiệu năng rất cao (`RF PR-AUC = 0.9985`, `Persistence PR-AUC = 0.9992`).
   - Khi chuyển sang dự báo tương lai $h \in \{1, 6, 12, 24\}$ giờ hoặc mô hình thuần khí tượng (Ablation không có PM2.5), PR-AUC phản ánh giới hạn vật lý thực sự khi không còn cửa sổ trượt chồng lấn.

---

## 2. Confusion Matrix & Đánh Đổi Precision–Recall–FAR Trên Tập Test Đã Chốt Ngưỡng

- **Baseline `DummyClassifier(strategy='prior')`:** Accuracy = **71.07%**, Recall = **0.00%**, PR-AUC = **0.2893** (khớp chính xác tỷ lệ dương tính của Test, chứng minh *Bẫy Accuracy*).
- **Random Forest (`Balanced`, $\tau^* = 0.32$ tối ưu $F_2$ trên Train OOF):**
  - Confusion Matrix `[[TN, FP], [FN, TP]]` = `[[1609, 27], [0, 666]]` (mẫu số dương: 666 ca; mẫu số âm: 1,636 giờ).
  - Precision = **96.10%**, Recall = **100.00%**, F1 = **0.9801**, F2 = **0.9920**, FAR = **1.65%**, Brier = **0.0134**, ROC-AUC = **0.9995**, PR-AUC = **0.9985**.
- **Logistic Regression (`Balanced`, $\tau^* = 0.43$):** bắt được 663/666 ca (bỏ sót 3 ca), Recall = **99.55%**, Precision = **94.18%**, PR-AUC = **0.9989**.

---

## 3. Feature Importance (`average_precision`) & Kiểm Soát Đa Cộng Tuyến `pm25`/`pm10`

- **Loại trừ bắt buộc `pm10`:** Trong bộ dữ liệu, tương quan Pearson giữa `pm25` và `pm10` rất cao ($r = 0,9727$); việc giữ `pm10` đồng thời ở thời điểm $t$ vừa gây đa cộng tuyến nghiêm trọng vừa tái tạo lại phép đo bụi đồng thời tại $t$. Do đó `pm10` bị cấm tuyệt đối trong `FORBIDDEN_CLASSIFICATION_COLS`.
- **Xếp hạng đặc trưng thực nghiệm (Permutation PR-AUC với 20 lần lặp trên Test):**
  - Nhóm tự hồi quy quá khứ (`pm25_rolling_mean_24h`, `pm25_rolling_std_24h`, `pm25_lag24`) giữ thứ hạng chi phối tuyệt đối.
  - Ở tầm $h=0$, Permutation Importance của các biến khí tượng đơn lẻ trong Random Forest gần 0 hoặc âm nhẹ do bị thông tin 23/24h của `pm25_rolling_mean_24h` che khuất; cấu trúc tác động của gió, nhiệt-ẩm và áp suất được quan sát bổ sung qua bảng **Odds Ratio của Logistic Regression** và kịch bản **Meteorology-Only** (xem bảng dưới).

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

## 4. Tổng Hợp Đa Phạm Vi (Protocol A: `VN001` & `VN003_OPENAQ_7441`)

- Khi đánh giá trên `VN001_extended_80_20` (mốc Test từ tháng 05–07/2026 là mùa sạch mưa nhiều kèm đợt mất dữ liệu dài **630 giờ**), tập Test ghi nhận **0 ca dương tính** (`Test positives = 0`); các chỉ số cần phân lớp dương (`PR-AUC`, `ROC-AUC`, `Recall`) được báo cáo minh bạch là **`UNESTIMABLE`** thay vì bị bóp méo.
- Tập lịch sử dài `VN003_extended_2022_2025` (14.207 giờ hợp lệ có nhãn) cung cấp bằng chứng kiểm chứng đa năm cho cả Train và Test có đủ cả hai lớp.

| Scope | Station | Train Valid (Prev) | Test Valid (Prev) | Dummy PR-AUC | LogReg PR-AUC / Rec | RF PR-AUC / Rec |
| --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | VN001_HANOI_556_NGUYEN_VAN_CU | 2,965 (32.98%) | 2,302 (28.93%) | 0.2893 | 0.9989 / 99.55% | 0.9985 / 100.00% |
| VN001_extended_80_20 | VN001_HANOI_556_NGUYEN_VAN_CU | 5,025 (32.72%) | 242 (0.00%) | UNESTIMABLE | UNESTIMABLE / UNESTIMABLE | UNESTIMABLE / UNESTIMABLE |
| VN003_extended_2022_2025 | VN003_HANOI_OPENAQ_7441 | 10,636 (25.17%) | 3,439 (49.81%) | 0.4981 | 0.9995 / 99.77% | 0.9983 / 99.30% |

---

## 5. Bài Học Kiểm Toán Rò Rỉ Dữ Liệu

Chi tiết 4 dạng rò rỉ (Target, Train-Test contamination, Temporal, Group) kèm bằng chứng unit test, `validate_no_leakage()`, kiểm soát purge gap ở $h > 0$ và giải trình loại trừ SMOTE được lập thành biên bản chính thức tại `docs/leakage_audit.md` và `reports/classification_leakage_audit.md`.
