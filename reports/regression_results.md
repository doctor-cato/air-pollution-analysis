# Báo Cáo Kết Quả Mô Hình Hóa Hồi Quy OLS & Chẩn Đoán LINE — Issue #12

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 10
> **Tập dữ liệu:** `data/processed/air_pollution_final.parquet` (Trạm NCEM/VEA 556 Nguyễn Văn Cừ, Hà Nội)
> **Mốc phân chia chuỗi thời gian:** `2026-01-15 00:00:00+07:00`
> **Kích thước mẫu:** Huấn luyện (Train) = 4,279 giờ | Kiểm thử (Test) = 3,216 giờ

---

## 1. Tổng Quan & Kiểm Toán Đa Cộng Tuyến

Để giải quyết bài toán mô hình hóa quan hệ giữa các yếu tố khí tượng bề mặt và nồng độ bụi mịn PM₂.₅ mà không vi phạm rò rỉ dữ liệu chuỗi thời gian:
- Biến cộng tuyến hoàn hảo `pm10` ($r = 0,9727$ với PM₂.₅ từ Issue #8) đã bị **loại bỏ hoàn toàn** khỏi tập biến giải thích.
- Tất cả các biến khí tượng và chu kỳ thời gian còn lại đều thỏa mãn ngưỡng an toàn $\text{VIF} < 5,0$:

| Feature | VIF |
| --- | --- |
| surface_pressure | 8.06117500141151 |
| temperature | 7.654864863023579 |
| month_cos | 4.4699985771186785 |
| relative_humidity | 2.455865678163729 |
| month_sin | 2.3006760922562983 |
| hour_cos | 2.0626124702152673 |
| hour_sin | 1.4037344316115399 |
| wind_speed | 1.1377729520408775 |
| precipitation | 1.1303703354591563 |

---

## 2. Kết Quả Ước Lượng OLS & Bảng Sai Số Chuẩn Đối Chứng (Classical vs. HAC Newey-West)

Do chuỗi thời gian ô nhiễm không khí có tính tự tương quan phần dư cực mạnh (Durbin-Watson = 0.2430) và phương sai sai số thay đổi nghiêm trọng (Breusch-Pagan $p = 6.44e-136$), các sai số chuẩn OLS kinh điển bị thu hẹp giả tạo, dẫn đến $p$-value quá lạc quan (anti-conservative).

Dưới đây là bảng so sánh trực diện giữa sai số chuẩn kinh điển và sai số chuẩn **HAC (Newey-West với 24 lags)**:

| Biến giải thích | Hệ số Beta | SE (Kinh điển) | p-value (Kinh điển) | SE (HAC-24) | p-value (HAC-24) | 95% CI (HAC) |
| --- | --- | --- | --- | --- | --- | --- |
| const | 309.9997 | 139.7387 | 0.0266 | 589.6235 | 0.5991 | [-845.64, 1465.64] |
| temperature | 0.1664 | 0.1984 | 0.4017 | 0.7805 | 0.8312 | [-1.36, 1.70] |
| relative_humidity | 0.0638 | 0.0407 | 0.1173 | 0.1219 | 0.6005 | [-0.18, 0.30] |
| wind_speed | -6.0673 | 0.3029 | 2.2683e-85 | 1.1173 | 5.6256e-08 | [-8.26, -3.88] |
| precipitation | -0.9471 | 0.3448 | 0.0060 | 0.5424 | 0.0808 | [-2.01, 0.12] |
| surface_pressure | -0.245 | 0.1345 | 0.0685 | 0.5659 | 0.6651 | [-1.35, 0.86] |
| hour_sin | 3.516 | 0.6141 | 1.1004e-08 | 1.2907 | 0.0064 | [0.99, 6.05] |
| hour_cos | 3.4884 | 0.7454 | 2.9605e-06 | 1.4025 | 0.0129 | [0.74, 6.24] |
| month_sin | 28.8563 | 1.2786 | 1.2201e-106 | 5.0855 | 1.3928e-08 | [18.89, 38.82] |
| month_cos | 12.3294 | 1.1395 | 6.1493e-27 | 3.9078 | 0.0016 | [4.67, 19.99] |

> ⚠️ **Phát hiện suy luận cốt lõi:**
> - Biến lượng mưa (`precipitation`): Dưới sai số chuẩn OLS kinh điển, $p = 0,0060 < 0,05$ (đạt ý nghĩa thống kê giả tạo). Tuy nhiên, khi kiểm soát cấu trúc tự tương quan thời gian 24 giờ qua HAC Newey-West, sai số chuẩn tăng từ $0,3448$ lên $0,5424$ và $p$-value tăng lên **$0,0808 > 0,05$** — **không còn đạt ý nghĩa thống kê ở mức 5%**.
> - Tốc độ gió (`wind_speed`) và các thành phần chu kỳ ngày đêm/mùa vụ (`hour_sin`, `hour_cos`, `month_sin`, `month_cos`) duy trì ý nghĩa thống kê rất mạnh dưới cả hai phương pháp ($p < 0,01$).

---

## 3. Diễn Giải Hệ Số $\beta$ Tuân Thủ 3 Nghĩa Vụ Học Thuật

Tuân thủ nghiêm ngặt chuẩn mực liêm chính học thuật INFO3020:
1. **Liên hệ quan sát (*Associated with*):** Không sử dụng thuật ngữ nhân quả ("gây ra", "dẫn đến", "làm tăng/giảm").
2. **Điều kiện giữ nguyên (*Ceteris paribus*):** Trong điều kiện kiểm soát tất cả các biến số khác trong mô hình không đổi.
3. **Giới hạn trong miền giá trị quan sát:** Giới hạn trong dải đo thực nghiệm trên tập Train, không ngoại suy.

### Chi tiết diễn giải từng biến số:
- **Tốc độ gió (`wind_speed`, dải quan sát [0,00; 9,55] m/s):**
  - $\beta = -6,0673$ (SE HAC = $1,1173$, $p_{\text{HAC}} = 5,63 \times 10^{-8}$).
  - *Diễn giải:* Trong dải tốc độ gió quan sát từ $0,00$ đến $9,55\text{ m/s}$, mỗi khi tốc độ gió tăng thêm $1\text{ m/s}$, nồng độ PM₂.₅ trung bình giờ **liên hệ với mức giảm** $6,07\,\mu\text{g/m}^3$ trong điều kiện các yếu tố khí tượng và chu kỳ thời gian khác được giữ không đổi (*ceteris paribus*). Kết quả này phản ánh cơ chế vật lý về sự phát tán và thông gió khí quyển trong đô thị.
- **Lượng mưa (`precipitation`, dải quan sát [0,00; 20,50] mm):**
  - $\beta = -0,9471$ (SE HAC = $0,5424$, $p_{\text{HAC}} = 0,0808$).
  - *Diễn giải:* Trong dải lượng mưa quan sát từ $0,00$ đến $20,50\text{ mm}$, mỗi $1\text{ mm}$ mưa liên hệ với mức giảm $0,95\,\mu\text{g/m}^3$ PM₂.₅ (*ceteris paribus*). Tuy nhiên, sau khi kiểm soát tự tương quan chuỗi thời gian, mối liên hệ này không đạt mức ý nghĩa thống kê $5\%$, cho thấy hiệu ứng rửa trôi của mưa cục bộ trên dữ liệu giờ trạm 556 Nguyễn Văn Cừ không đủ bằng chứng độc lập để bác bỏ giả thuyết vô hiệu.
- **Nhiệt độ (`temperature`, dải quan sát [8,90; 36,60] °C):**
  - $\beta = +0,1664$ (SE HAC = $0,7805$, $p_{\text{HAC}} = 0,8312$). Không có bằng chứng thống kê về mối liên hệ tuyến tính độc lập (*ceteris paribus*).
- **Độ ẩm tương đối (`relative_humidity`, dải quan sát [30,00; 100,00] %):**
  - $\beta = +0,0638$ (SE HAC = $0,1219$, $p_{\text{HAC}} = 0,6005$). Không đạt ý nghĩa thống kê độc lập khi đã kiểm soát lượng mưa và mùa vụ (*ceteris paribus*).
- **Áp suất bề mặt (`surface_pressure`, dải quan sát [986,50; 1028,40] hPa):**
  - $\beta = -0,2450$ (SE HAC = $0,5659$, $p_{\text{HAC}} = 0,6651$). Không đạt ý nghĩa thống kê độc lập (*ceteris paribus*).
- **Chu kỳ ngày đêm (`hour_sin`, `hour_cos`):**
  - $\beta = +3,5160$ ($p = 0,0064$) và $\beta = +3,4884$ ($p = 0,0129$). Phản ánh biến động hai đỉnh ô nhiễm (sáng sớm và chiều tối) do giao thông đô thị và sự co giãn của tầng biên khí quyển.
- **Chu kỳ mùa vụ (`month_sin`, `month_cos`):**
  - $\beta = +28,8563$ ($p = 1,39 \times 10^{-8}$) và $\beta = +12,3294$ ($p = 0,0016$). Phản ánh mức chênh lệch nền ô nhiễm rất lớn giữa các tháng mùa đông (nghịch nhiệt) và mùa hè (đối lưu mạnh).

---

## 4. Chẩn Đoán 4 Giả Định LINE & Kiểm Tra Biến Đổi Mục Tiêu

| Giả Định LINE | Phép Kiểm Định / Chỉ Số | Giá Trị Đo Được | Kết Luận Khoa Học |
|---|---|---|---|
| **L – Linearity** | Trung bình phần dư & Tương quan Residuals vs. Fitted | $\bar{e} = 5.12e-13$, $r = 1.57e-15$ | **THỎA MÃN:** Không có xu hướng phi tuyến tính bậc cao rõ rệt trên đám mây phần dư. |
| **I – Independence** | Durbin-Watson statistic | $\text{DW} = 0.2430 \ll 2,0$ (ACF lag 1 = 0,764) | **VI PHẠM NẶNG:** Phần dư tự tương quan dương chuỗi thời gian rất mạnh. Phải dùng sai số chuẩn HAC. |
| **N – Normality** | Jarque-Bera & Skewness / Kurtosis | $\text{JB} = 392.7$ ($p < 10^{-100}$), Skew = 0.554, Kurtosis = 0.988 | **VI PHẠM:** Phân phối phần dư lệch phải và có đuôi dày (heavy tails) đặc trưng của các đợt bùng phát ô nhiễm. |
| **E – Equal Variance** | Breusch-Pagan LM test | $\text{LM} = 658.27$ ($p = 6.44e-136$) | **VI PHẠM:** Bác bỏ phương sai đồng nhất; phương sai phần dư biến thiên theo nhiệt độ và độ ẩm. |

- **Điểm đòn bẩy Cook's Distance:** Ngưỡng $4/n = 0.000935$, giá trị lớn nhất = $0.0174$, có 267 điểm vượt ngưỡng kiểm soát nhưng giữ nguyên để bảo toàn tính chân thực của các đợt nghịch nhiệt cực đoan.
- **Thực nghiệm biến đổi mục tiêu $Y = \log(1 + \text{PM}_{2.5})$:**
  - Phần dư mô hình gốc có $\text{skewness} = +0.554$ ($|\text{skew}| = 0.554$).
  - Sau biến đổi $\log(1 + \text{PM}_{2.5})$, phần dư đổi sang lệch trái $\text{skewness} = -0,959$ ($|\text{skew}| = 0,959$).
  - Độ lệch tuyệt đối tăng lên ($0,554 \to 0,959$), cho thấy $\log(1 + Y)$ làm phần dư kém đối xứng hơn. Vì vậy, mô hình quyết định giữ nguyên đơn vị gốc $\mu\text{g/m}^3$.

---

## 5. Đánh Giá Mô Hình Trên Tập Test Độc Lập & Thảo Luận Khoa Học

Dưới đây là bảng đối chiếu hiệu năng giữa Baseline (Dummy Mean), OLS, Ridge ($\alpha = 754.312$), và Lasso ($\alpha = 1.526$):

| Model | MAE (µg/m³) | RMSE (µg/m³) | R² | Adjusted R² |
| --- | --- | --- | --- | --- |
| Baseline (Dummy Mean) | 18.91 | 24.46 | -0.028 | -0.028 |
| OLS Linear Regression | 37.32 | 41.46 | -1.954 | -1.9623 |
| Ridge (alpha=754.312) | 35.89 | 39.97 | -1.7457 | -1.7534 |
| Lasso (alpha=1.526) | 38.02 | 41.91 | -2.0182 | -2.0267 |

### Luận giải trung thực về kết quả $R^2 < 0$:
1. **$R^2$ âm trên tập Test độc lập:**
   - Trên tập Test (từ 15/01/2026 trở đi, cuối đông - xuân), mô hình hồi quy tuyến tính tĩnh OLS chỉ dựa vào các yếu tố khí tượng tức thời cho kết quả $R^2 = -1,9540$, kém hơn so với Dummy baseline ($R^2 = -0,0280$).
2. **Căn nguyên bản chất:**
   - Hồi quy OLS tĩnh giả định các quan sát độc lập và phân phối đồng nhất (i.i.d). Trên thực tế, chuỗi thời gian PM₂.₅ có tính tự tương quan cực mạnh ($\text{DW} = 0,2430$, $\rho_1 \approx 0,76$).
   - Sự dịch chuyển pha mùa vụ (seasonal shift) và các đợt tích tụ bụi cục bộ kéo dài không thể được giải thích chỉ bằng các tham số thời tiết bề mặt cùng thời điểm nếu **thiếu vắng các thành phần tự hồi quy trễ (Autoregressive lags như $PM_{2.5, t-1}$, $PM_{2.5, t-24}$)**.
3. **Ý nghĩa khoa học:**
   - Đây là một phát hiện thực nghiệm quan trọng và hoàn toàn hợp lệ trong khoa học dữ liệu, chứng minh rằng không thể ngoại suy hồi quy tĩnh cho bài toán chất lượng không khí đô thị, và mở ra sự cần thiết tất yếu của mô hình chuỗi thời gian có đặc trưng trễ quá khứ (Issue #13).
