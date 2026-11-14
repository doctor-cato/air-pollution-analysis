# Tổng Kết Phát Hiện Hồi Quy Tuyến Tính OLS, Điều Chuẩn & Chẩn Đoán LINE (Issue #12 / D12)

> **Tài liệu nguồn đối chiếu:** Chi tiết từng bảng chạy thực nghiệm và hình ảnh chẩn đoán được lưu tại [reports/regression_results.md](../reports/regression_results.md), [figures/regression_line_diagnostics.png](../figures/regression_line_diagnostics.png), [figures/regression_line_diagnostics_vn001_extended.png](../figures/regression_line_diagnostics_vn001_extended.png) và [figures/regression_line_diagnostics_vn003_extended.png](../figures/regression_line_diagnostics_vn003_extended.png).
>
> **Cảnh báo giới hạn kết luận (Bắt buộc trước khi đọc `$R^2$`):** Trên cả 3 phạm vi dữ liệu thực nghiệm, **tất cả 4 giả định LINE (Linearity, Independence, Normality, Equal Variance) đều bị vi phạm có ý nghĩa thống kê rất mạnh**. Vì vậy, tuyệt đối **không** báo cáo `$R^2$` trần như một thước đo độ chính xác dự báo hay bằng chứng quan hệ nhân quả; mọi hệ số hồi quy chỉ có giá trị mô tả xu hướng liên hệ tuyến tính cục bộ (*associational, ceteris paribus*) trong miền giá trị quan sát của tập Train, phải dùng sai số chuẩn HAC Newey-West để suy luận, và cần kết hợp với mô hình phi tuyến hoặc thành phần tự hồi quy trễ thời gian cho bài toán dự báo.

---

## 1. Phạm Vi Thực Nghiệm & Giao Thức Đơn Trạm (Protocol A)

Nhằm kiểm chứng tính ổn định theo mùa và theo trạm quan trắc đồng thời chặn gộp đa trạm bất hợp lệ (Protocol B — `VN003` 2022–2025 và `VN001` 2025–2026 lệch pha thời gian), quy trình hồi quy `src/regression.py` khóa chặt thực nghiệm đơn trạm theo **Protocol A**:

| Phạm vi thực nghiệm | Trạm (`station_id`) | Khoảng thời gian | Số giờ `pm25` hợp lệ / Tổng lưới (Tỷ lệ thiếu) | Mốc chia Train / Test | Kích thước Train / Test | Dataset SHA-256 (prefix) |
| --- | --- | --- | --- | --- | --- | --- |
| **`VN001_baseline_2026_01_15`** | `VN001_HANOI_556_NGUYEN_VAN_CU` | `2025-07-03 22:00` → `2026-07-15 17:00` | `7,495 / 9,044` (17.1%) | `< 2026-01-15 00:00+07:00` | `4,279 / 3,216` | `866f39de1720` |
| **`VN001_extended_80_20`** | `VN001_HANOI_556_NGUYEN_VAN_CU` | `2025-07-03 22:00` → `2026-07-15 17:00` | `7,495 / 9,044` (17.1%) | Cột `split` 80/20 (cut `> 2026-05-01 08:00`) | `6,749 / 746` | `6930557fbfc8` |
| **`VN003_extended_2022_2025`** | `VN003_HANOI_OPENAQ_7441` | `2022-01-01 01:00` → `2025-04-09 22:00` | `18,208 / 28,678` (36.5%) | Cột `split` 80/20 (cut `> 2024-08-13 22:00`) | `13,835 / 4,373` | `6930557fbfc8` |

**Kiểm soát rò rỉ biến giải thích:** Tập 9 biến giải thích mặc định gồm 5 biến khí tượng (`temperature`, `relative_humidity`, `wind_speed`, `precipitation`, `surface_pressure`) và 4 biến điều hòa chu kỳ (`hour_sin`, `hour_cos`, `month_sin`, `month_cos`). Các cột `pm10` (đa cộng tuyến nguồn đồng phát thải), `pm25_was_missing` (rò rỉ cấu trúc mục tiêu) và `is_high_humidity_fog` (không có giá trị dự báo biên độc lập theo `src/flag_evidence.py`) bị loại khỏi ma trận đặc trưng trước khi huấn luyện. Mọi phép `SimpleImputer(strategy="median")` và `RobustScaler()` cho Ridge/Lasso được cô lập hoàn toàn trong từng fold của `TimeSeriesSplit(n_splits=5)` và được kiểm chứng bằng `validate_no_leakage()`.

---

## 2. Kiểm Toán Đa Cộng Tuyến (VIF)

| Biến giải thích | VIF (`VN001_baseline`) | VIF (`VN001_extended`) | VIF (`VN003_extended`) | Phân loại ngưỡng |
| --- | --- | --- | --- | --- |
| `surface_pressure` | **8.061** | **5.955** | **6.241** | Trung bình–cao (`5 <= VIF < 10`) |
| `temperature` | **7.655** | **5.730** | **5.818** | Trung bình–cao (`5 <= VIF < 10`) |
| `month_cos` | 4.470 | 3.068 | 3.362 | Thấp (`< 5`) |
| `relative_humidity` | 2.456 | 2.403 | 2.076 | Thấp (`< 5`) |
| `month_sin` | 2.301 | 1.392 | 1.461 | Thấp (`< 5`) |
| `hour_cos` | 2.063 | 2.020 | 1.735 | Thấp (`< 5`) |
| `hour_sin` | 1.404 | 1.461 | 1.367 | Thấp (`< 5`) |
| `wind_speed` | 1.138 | 1.121 | 1.124 | Rất thấp (`< 5`) |
| `precipitation` | 1.130 | 1.106 | 1.098 | Rất thấp (`< 5`) |

- **Kết luận VIF:** Không có biến nào vượt ngưỡng nghiêm trọng `VIF >= 10`, nhưng `surface_pressure` (`5.955–8.061`) và `temperature` (`5.730–7.655`) nằm trong vùng cảnh báo `[5, 10)` trên cả 3 phạm vi (phản ánh cặp nghịch biến nhiệt độ–khí áp đặc trưng của gió mùa lục địa Đông Á tại đồng bằng Bắc Bộ). Vì lý do này, Ridge/Lasso được đánh giá song song với OLS, và sai số chuẩn của hệ số nhiệt độ/khí áp khi suy luận riêng lẻ kém ổn định hơn `wind_speed`.

---

## 3. Bảng Tham Số OLS (Classical vs HAC-24) & Điều Chuẩn Ridge / Lasso

> **Lưu ý đơn vị:** Hệ số `OLS (Raw Beta)` ước lượng trên đơn vị vật lý gốc (°C, %, m/s, mm, hPa, [-1, 1]); trong khi hệ số `Ridge` và `Lasso` ước lượng trên không gian đặc trưng đã chuẩn hóa bằng `RobustScaler` (fit strictly trên Train) với siêu tham số $\alpha$ chọn qua 5-fold `TimeSeriesSplit`.

### 3.1. Phạm vi `VN001_baseline_2026_01_15` (`n_train = 4,279`)

| Biến giải thích | OLS Raw $\beta$ | SE (Classical) | $p$ (Classical) | SE (HAC-24) | $p$ (HAC-24) | 95% CI (HAC-24) | Ridge ($\alpha=754.312$, scaled) | Lasso ($\alpha=1.526$, scaled) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `const` (Intercept) | `309.9997` | `139.7387` | `0.0266` | `589.6235` | `0.5991` | `[-845.641; 1465.6404]` | `49.0410` | `48.3851` |
| `temperature` | `+0.1664` | `0.1984` | `0.4017` | `0.7805` | `0.8312` | `[-1.3634; 1.6961]` | `-2.7722` | `-3.5037` |
| `relative_humidity` | `+0.0638` | `0.0407` | `0.1173` | `0.1219` | `0.6005` | `[-0.1751; 0.3027]` | `+1.5974` | `0.0000` |
| `wind_speed` | **`-6.0673`** | `0.3029` | `2.27e-85` | `1.1173` | **`5.63e-08`** | `[-8.2572; -3.8774]` | `-7.8333` | `-7.8795` |
| `precipitation` | `-0.9471` | `0.3448` | `0.0060` | `0.5424` | `0.0808` | `[-2.0102; 0.1160]` | `-0.1466` | `-0.1332` |
| `surface_pressure` | `-0.2450` | `0.1345` | `0.0685` | `0.5659` | `0.6651` | `[-1.3542; 0.8643]` | `+2.1359` | `0.0000` |
| `hour_sin` | `+3.5160` | `0.6141` | `1.10e-08` | `1.2907` | `0.0064` | `[0.9862; 6.0458]` | `+1.7714` | `0.0000` |
| `hour_cos` | `+3.4884` | `0.7454` | `2.96e-06` | `1.4025` | `0.0129` | `[0.7396; 6.2373]` | `+2.0442` | `0.0000` |
| `month_sin` | `+28.8563` | `1.2786` | `1.22e-106` | `5.0855` | `1.39e-08` | `[18.8890; 38.8236]` | `+8.8848` | `+9.5058` |
| `month_cos` | `+12.3294` | `1.1395` | `6.15e-27` | `3.9078` | `0.0016` | `[4.6702; 19.9886]` | `+5.0814` | `+2.9178` |

### 3.2. Phạm vi `VN001_extended_80_20` (`n_train = 6,749`)

| Biến giải thích | OLS Raw $\beta$ | SE (Classical) | $p$ (Classical) | SE (HAC-24) | $p$ (HAC-24) | 95% CI (HAC-24) | Ridge ($\alpha=1000.000$, scaled) | Lasso ($\alpha=1.151$, scaled) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `const` (Intercept) | `839.7609` | `104.5664` | `1.13e-15` | `419.5346` | `0.0453` | `[17.4882; 1662.0337]` | `44.7535` | `44.1984` |
| `temperature` | `-0.4541` | `0.1415` | `0.0013` | `0.5923` | `0.4433` | `[-1.6150; 0.7068]` | `-4.0802` | `-2.7339` |
| `relative_humidity` | `-0.1144` | `0.0336` | `0.0007` | `0.1042` | `0.2725` | `[-0.3186; 0.0899]` | `-0.6815` | `0.0000` |
| `wind_speed` | **`-7.2891`** | `0.2408` | `8.03e-189` | `0.7769` | **`6.48e-21`** | `[-8.8118; -5.7663]` | `-9.3449` | `-9.8277` |
| `precipitation` | `-0.9748` | `0.3182` | `0.0022` | `0.5218` | `0.0617` | `[-1.9975; 0.0478]` | `-1.6112` | `-0.7495` |
| `surface_pressure` | `-0.7528` | `0.1003` | `7.11e-14` | `0.4009` | `0.0604` | `[-1.5385; 0.0329]` | `+1.8418` | `0.0000` |
| `hour_sin` | `+1.6003` | `0.5088` | `0.0017` | `1.1112` | `0.1498` | `[-0.5776; 3.7781]` | `-0.0126` | `0.0000` |
| `hour_cos` | `+1.1337` | `0.5989` | `0.0584` | `1.3180` | `0.3897` | `[-1.4495; 3.7168]` | `+0.3806` | `0.0000` |
| `month_sin` | `+7.7003` | `0.4598` | `1.05e-61` | `1.4263` | `6.71e-08` | `[4.9047; 10.4958]` | `+5.0392` | `+4.5770` |
| `month_cos` | `+18.8838` | `0.8428` | `2.66e-107` | `2.7478` | `6.32e-12` | `[13.4981; 24.2694]` | `+8.2849` | `+12.5848` |

### 3.3. Phạm vi `VN003_extended_2022_2025` (`n_train = 13,835`)

| Biến giải thích | OLS Raw $\beta$ | SE (Classical) | $p$ (Classical) | SE (HAC-24) | $p$ (HAC-24) | 95% CI (HAC-24) | Ridge ($\alpha=59.636$, scaled) | Lasso ($\alpha=0.281$, scaled) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `const` (Intercept) | `746.2263` | `71.4609` | `1.97e-25` | `244.8736` | `0.0023` | `[266.2829; 1226.1697]` | `43.3462` | `43.5212` |
| `temperature` | `-0.2380` | `0.0862` | `0.0057` | `0.3284` | `0.4685` | `[-0.8816; 0.4055]` | `-2.1291` | `0.0000` |
| `relative_humidity` | `-0.3480` | `0.0210` | `4.95e-61` | `0.0598` | `5.87e-09` | `[-0.4652; -0.2308]` | `-7.2715` | `-4.3990` |
| `wind_speed` | **`-6.2864`** | `0.1810` | `1.58e-253` | `0.4482` | **`1.09e-44`** | `[-7.1649; -5.4079]` | `-10.7998` | `-9.9276` |
| `precipitation` | `-0.5524` | `0.2082` | `0.0080` | `0.2328` | `0.0177` | `[-1.0087; -0.0961]` | `-0.0648` | `-0.0878` |
| `surface_pressure` | `-0.6476` | `0.0689` | `6.74e-21` | `0.2348` | `0.0058` | `[-1.1077; -0.1875]` | `-6.3481` | `0.0000` |
| `hour_sin` | `+1.1174` | `0.3479` | `0.0013` | `0.6273` | `0.0748` | `[-0.1120; 2.3468]` | `+1.1770` | `0.0000` |
| `hour_cos` | `+3.0621` | `0.3923` | `6.30e-15` | `0.8620` | `0.0004` | `[1.3725; 4.7516]` | `+3.9662` | `+2.0841` |
| `month_sin` | `+8.3053` | `0.3901` | `5.30e-99` | `1.1592` | `7.81e-13` | `[6.0332; 10.5773]` | `+7.8089` | `+6.4391` |
| `month_cos` | `+16.0745` | `0.5110` | `8.30e-210` | `1.5490` | `3.14e-25` | `[13.0385; 19.1105]` | `+25.5595` | `+20.9126` |

### 3.4. Ảnh hưởng của HAC Newey-West và Độ Nhạy Theo Độ Trễ $L$

Sai số chuẩn cổ điển OLS đánh giá thấp phương sai ước lượng nghiêm trọng do tự tương quan phần dư:
- Ví dụ với `precipitation` trên `VN001_baseline`: OLS cổ điển báo cáo $p = 0.0060$ (có ý nghĩa ở mức 1%), nhưng khi chuyển sang HAC Newey-West $L = 24$ giờ thì $p = 0.0808$ (mất ý nghĩa ở mức 5%). Khảo sát lưới độ trễ $L \in \{0\text{ (HC1)}, \text{NW plug-in}, 12, 24, 48, 72, 168\}$ cho thấy `precipitation` biến thiên từ `0.0004` (`HC1`) lên `0.0477` (`NW=9h`), `0.0583` (`12h`), `0.0808` (`24h`), `0.0790` (`168h`); trên `VN001_extended` từ `9.80e-05` (`HC1`) lên `0.0617` (`24h`); và trên `VN003_extended` duy trì `< 0.05` đến `72h` (`0.0341`) và chạm `0.0505` ở `168h`.
- Ngược lại, **tốc độ gió (`wind_speed`)** bền vững tuyệt đối trên mọi phạm vi và mọi độ trễ HAC tới `168` giờ: trên `VN001_baseline` $\beta = -6.0673$ ($p_{\text{HAC-168}} = 7.38 \times 10^{-5}$), trên `VN001_extended` $\beta = -7.2891$ ($p_{\text{HAC-168}} = 6.55 \times 10^{-12}$), và trên `VN003_extended` $\beta = -6.2864$ ($p_{\text{HAC-168}} = 4.75 \times 10^{-26}$). Theo nghĩa vụ diễn giải không nhân quả: *trong miền giá trị quan sát trên Train, mỗi 1 m/s tốc độ gió tăng thêm liên hệ với mức giảm 6.07–7.29 µg/m³ nồng độ $\text{PM}_{2.5}$ trung bình giờ trong điều kiện giữ nguyên các biến còn lại (ceteris paribus)*, phản ánh cơ chế khuếch tán và thông gió đô thị — **không** đồng nghĩa với tác động can thiệp nhân quả độc lập.

---

## 4. Kết Quả Kiểm Định 4 Giả Định LINE & Điểm Ảnh Hưởng (Cook's Distance)

| Giả định | Chỉ số kiểm định | `VN001_baseline` (`n=4,279`) | `VN001_extended` (`n=6,749`) | `VN003_extended` (`n=13,835`) | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| **L – Linearity** | Ramsey RESET (`p=2`, `p=3`) | `F=223.27 (p=3.02e-49)`; `p=3: F=116.26 (p=6.86e-50)` | `F=615.42 (p=4.40e-130)`; `p=3: F=330.60 (p=1.09e-137)` | `F=243.15 (p=2.35e-54)`; `p=3: F=122.83 (p=1.33e-53)` | **VI PHẠM NGHIÊM TRỌNG** |
| **I – Independence** | Durbin-Watson, `ACF(1)`, `ACF(24)` | `DW=0.2430`, `ACF(1)=0.8785`, `ACF(24)=0.4019` | `DW=0.2079`, `ACF(1)=0.8960`, `ACF(24)=0.4475` | `DW=0.3033`, `ACF(1)=0.8484`, `ACF(24)=0.3451` | **VI PHẠM NẶNG** |
| **N – Normality** | Jarque-Bera, Skewness, Excess Kurtosis | `JB=392.7 (p=5.32e-86)`, `Skew=0.554`, `Kurt=0.988`, `Shapiro W=0.9791 (p=1.27e-24)` | `JB=1641.1 (p=0.00e+00)`, `Skew=0.932`, `Kurt=1.536` | `JB=51355.1 (p=0.00e+00)`, `Skew=2.060`, `Kurt=8.492` | **VI PHẠM** |
| **E – Equal Variance** | Breusch-Pagan LM test | `LM=658.27 (p=6.44e-136)` | `LM=513.49 (p=7.41e-105)` | `LM=701.19 (p=3.84e-145)` | **VI PHẠM** |

- **Cảnh báo về phép kiểm tra `Linearity`:** Mặc dù theo đại số OLS $\bar{e} \approx 0$ (`2.51e-13` đến `-1.37e-13`) và $\text{corr}(\hat{e}, \hat{y}) = 0$, cả đường cong LOWESS trên biểu đồ Residuals vs Fitted lẫn kiểm định **Ramsey RESET** ($p < 10^{-48}$ trên cả 3 phạm vi) bác bỏ nghiêm trọng dạng tuyến tính bậc nhất. Ngoài ra, trên `VN001_baseline`, phép biến đổi `log1p(pm25)` không giải quyết triệt để phân phối do làm đảo dấu độ lệch thành lệch trái (`skew = -0.958`).
- **Giới hạn kết luận do vi phạm LINE:** Khi cả 4 giả định L-I-N-E đều không thỏa mãn, OLS mất tính hiệu quả (BLUE không còn đúng theo nghĩa tối ưu phương sai), $p$-value cổ điển bị lệch hướng lạc quan thái quá, phương sai dự báo không đồng đều (sai số phóng đại ở các đợt nghịch nhiệt mùa Đông), và mô hình **không** đủ tin cậy làm công cụ dự báo vận hành. Theo đúng kỷ luật báo cáo của đồ án, mọi kết luận chỉ dừng ở mức **mô tả định hướng xu hướng khí tượng học**.
- **Điểm đòn bẩy & Cook's Distance:**
  - `VN001_baseline`: Regression Outliers (`|stud_resid| > 3`) = `42`, High Leverage (`h_ii > 0.00467`) = `137`, Cook's `D > 4/n` (`0.000935`) = `267` điểm (`6.24%`), nhưng `D > 0.5` = `0`, `D > 1.0` = `0` (`D_max = 0.0174`).
  - `VN001_extended`: Outliers = `84`, High Leverage (`h_ii > 0.00296`) = `216`, `D > 4/n` (`0.000593`) = `353` điểm (`5.23%`), `D > 0.5` = `0`, `D > 1.0` = `0` (`D_max = 0.0174`).
  - `VN003_extended`: Outliers = `246`, High Leverage (`h_ii > 0.00145`) = `441`, `D > 4/n` (`0.000289`) = `591` điểm (`4.27%`), `D > 0.5` = `0`, `D > 1.0` = `0` (`D_max = 0.0072`).
  - **Quyết định xử lý:** Toàn bộ các điểm vượt ngưỡng `4/n` đều có `D_max <= 0.0174 << 0.5` (chủ yếu rơi vào các đợt ô nhiễm mùa Đông/nghịch nhiệt thực tế như `2025-11-29`, `2024-03-05`, `2022-01-04`), nên được **giữ nguyên 100%** để bảo toàn cấu trúc cực trị khí quyển.

---

## 5. Bảng Đối Chiếu Hiệu Năng Train / Test & Giải Phẫu Thất Bại Ngoại Suy Mùa Vụ

### 5.1. Đối chiếu trực tiếp Train vs Test theo mô hình

| Phạm vi | Mô hình | Train MAE | Train RMSE | Train $R^2$ | Train Adj $R^2$ | Test MAE (µg/m³) | Test RMSE (µg/m³) | Test $R^2$ | Test Adj $R^2$ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **`VN001_baseline`** | Baseline (Dummy Mean) | `23.49` | `30.30` | `0.0000` | `0.0000` | `18.91` | `24.46` | `-0.0280` | `-0.0280` |
| `4,279 / 3,216` | OLS Linear Regression | `18.23` | `23.96` | **`0.3747`** | `0.3734` | `37.32` | `41.46` | **`-1.9540`** | `-1.9623` |
| | Ridge ($\alpha=754.312$) | `18.37` | `24.25` | `0.3594` | `0.3581` | `35.89` | `39.97` | `-1.7457` | `-1.7534` |
| | Lasso ($\alpha=1.526$) | `18.59` | `24.51` | `0.3459` | `0.3445` | `38.02` | `41.91` | `-2.0182` | `-2.0267` |
| **`VN001_extended`** | Baseline (Dummy Mean) | `21.53` | `28.31` | `0.0000` | `0.0000` | `20.40` | `24.15` | `-0.4487` | `-0.4487` |
| `6,749 / 746` | OLS Linear Regression | `18.52` | `24.45` | `0.2541` | `0.2531` | `15.63` | `21.12` | `-0.1073` | `-0.1209` |
| | Ridge ($\alpha=1000.000$) | `18.89` | `25.05` | `0.2167` | `0.2156` | `16.60` | `21.11` | `-0.1069` | `-0.1205` |
| | Lasso ($\alpha=1.151$) | `18.83` | `24.96` | `0.2227` | `0.2217` | `15.87` | **`20.61`** | `-0.0549` | `-0.0678` |
| **`VN003_extended`** | Baseline (Dummy Mean) | `19.95` | `28.26` | `0.0000` | `0.0000` | `26.42` | `37.73` | `-0.1235` | `-0.1235` |
| `13,835 / 4,373` | OLS Linear Regression | `17.16` | `24.75` | `0.2329` | `0.2324` | `23.98` | **`32.82`** | **`+0.1498`** | **`+0.1481`** |
| | Ridge ($\alpha=59.636$) | `17.15` | `24.76` | `0.2324` | `0.2319` | `24.00` | `32.91` | `+0.1456` | `+0.1438` |
| | Lasso ($\alpha=0.281$) | `17.22` | `24.88` | `0.2249` | `0.2244` | `23.98` | `33.06` | `+0.1377` | `+0.1359` |

- **Lý do dùng cả MAE và RMSE:** Trên mọi phạm vi, RMSE cao hơn MAE khoảng `1.1–1.4x` (chẳng hạn `VN003` OLS Test `MAE = 23.98` vs `RMSE = 32.82 µg/m³`; Ridge `24.00` vs `32.91`) vì bình phương sai số trừng phạt nặng phần đuôi các đợt ô nhiễm nặng, trong khi MAE phản ánh sai số điển hình hàng giờ theo đúng đơn vị nồng độ vật lý µg/m³.

### 5.2. Giải phẫu nguyên nhân Test $R^2$ âm và vai trò của chu kỳ đa năm + tự hồi quy (`pm25_lag24`)

| Phạm vi | Spec thử nghiệm Ablation | Train $R^2$ | Test RMSE (µg/m³) | Test $R^2$ | Mean Bias (`Pred - Obs`) | % Test ngoài dải `month_sin` Train |
| --- | --- | --- | --- | --- | --- | --- |
| `VN001_baseline` | OLS Full (9 biến) | `0.3747` | `41.46` | `-1.9540` | `+33.78` | **`65.0%`** |
| `VN001_baseline` | OLS Bỏ `month_sin`/`month_cos` (7 biến) | `0.2790` | `25.99` | `-0.1604` | `+1.35` | — |
| `VN001_baseline` | OLS Chỉ khí tượng (5 biến) | `0.2782` | `25.95` | `-0.1568` | `+1.31` | — |
| `VN001_baseline` | OLS Khí tượng + Giờ + `pm25_lag24` (`4,013/3,010`) | `0.5277` | `21.12` | **`+0.2245`** | `-1.25` | — |
| `VN001_extended` | OLS Full (9 biến) | `0.2541` | `21.12` | `-0.1073` | `-3.15` | `0.0%` |
| `VN001_extended` | OLS Khí tượng + Giờ + `pm25_lag24` (`6,402/621`) | `0.4512` | `17.50` | **`+0.0587`** | `+0.51` | — |
| `VN003_extended` | OLS Full (9 biến) | `0.2329` | `32.82` | **`+0.1498`** | `-3.79` | `0.0%` |
| `VN003_extended` | OLS Bỏ `month_sin`/`month_cos` (7 biến) | `0.1723` | `34.27` | `+0.0735` | `-5.81` | — |
| `VN003_extended` | OLS Khí tượng + Giờ + `pm25_lag24` (`12,871/4,206`) | `0.3476` | `28.70` | **`+0.3490`** | `-2.69` | — |

1. **Bằng chứng ngoại suy mùa vụ (Seasonal Extrapolation Bug):** Trên `VN001_baseline`, tập Train chỉ bao phủ nửa năm 07/2025–01/2026 khiến **`65.0%` tập Test (01–07/2026) nằm hoàn toàn ngoài dải `month_sin` đã học**, đẩy Mean Prediction lên `75.24` so với Mean Observed `41.46 µg/m³` (`bias = +33.78 µg/m³`, `Test R² = -1.9540`). Khi loại bỏ cặp ngoại suy `month_sin`/`month_cos`, sai số lệch trung bình rơi về `+1.35 µg/m³` và `Test R²` cải thiện nhảy vọt từ `-1.9540` lên `-0.1604`.
2. **Xác nhận trên chuỗi đa năm `VN003_extended` (2022–2025):** Khi dữ liệu Train bao phủ đủ chu kỳ nhiều năm (`0.0%` Test ngoài dải `month_sin`), chính cặp `month_sin`/`month_cos` đóng vai trò thông tin thực (bỏ mùa khiến `Test R²` tụt từ `+0.1498` xuống `+0.0735`), vượt trội rõ rệt Dummy Baseline (`Test RMSE = 32.82` vs `37.73 µg/m³`).
3. **Sức mạnh của tính bền bỉ theo thời gian (`pm25_lag24`) & ổn định phân tầng:** Khi bổ sung trễ nội trạm `pm25_lag24` (khớp đúng `timestamp - 24h`, tránh nhảy cóc qua gap), `Test R²` tăng lên `+0.2245` (`VN001_baseline`) và `+0.3490` (`VN003_extended`). Phân tầng theo từng năm 2022–2024 và cả 4 mùa trên `VN003` cho thấy hệ số `wind_speed` giữ dấu âm bền vững (`-2.574` đến `-10.689`, $p_{\text{HAC}} \le 0.0002$ với $n_{\text{eff}} = 207\text{–}504$). Cuối cùng, thử nghiệm nhạy dùng `pm25_derived_interpolated` chỉ trong Train (`+117h` trên `VN001_extended`, `+150h` trên `VN003_extended`) giữ nguyên tập Test bằng `pm25` quan sát gốc cho RMSE gần như bất biến (`21.12` vs `21.14` và `32.82` vs `32.83 µg/m³`), khẳng định tập kết quả không phụ thuộc vào nội suy nhân tạo.
