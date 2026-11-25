# Đánh Giá Định Kiến & Đạo Đức Dữ Liệu (Ethics & Bias Assessment) — Issue #14

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC  
> **Giai đoạn CRISP-DM:** Milestone 5 (Tuần 12 — Kiểm toán 4 giả thuyết định kiến trên dữ liệu thực)  
> **Thời điểm kiểm toán (UTC):** `2026-11-20T07:20:23Z`  
> **Nguyên tắc kiểm chứng:** Mọi số đếm, thống kê kiểm định và tọa độ dưới đây được tính trực tiếp từ `air_pollution_final.parquet`, `air_pollution_extended_2022_2026.parquet` (chỉ đọc), `src/flag_evidence.py`, `reports/issue44_extended_dataset_metadata.json`, `reports/issue44_openaq_7441_manifest.json` và `reports/extended_data_quality_by_station_year_season.csv`.

---

## 1. Giả Thuyết 1 — Định Kiến Cảm Biến (Sensor Bias: Độ Ẩm Cao / Sương Mù & Sai Khác Giữa Hai Trạm)

### 1.1. Tương tác giữa cờ độ ẩm cao (`is_high_humidity_fog`, $\text{RH} > 90\%$) và $\text{PM}_{2.5}$ theo mùa

- **Bằng chứng tái lập từ `src/flag_evidence.py` trên `VN001` baseline (`n = 7,495` giờ có cả `pm25` và `relative_humidity`):**
  - Tương quan biên (*marginal*) `corr(pm25, relative_humidity)` = **-0.0365** (gần 0).
  - Kiểm định F đồng thời cho tương tác `fog × season` trong mô hình `pm25 ~ C(fog) + C(season) + C(fog):C(season)`: **F(3, 7487) = 16.7754**, **p = 7.38e-11**.
  - Hiệu ứng đổi dấu rõ rệt theo mùa: tại **Đông**, nhóm có cờ `RH > 90%` cao hơn trung bình **+2.79 µg/m³**, trong khi tại **Xuân** là **-8.91 µg/m³**, **Hè** **+0.28 µg/m³**, và **Thu** **-2.72 µg/m³**. Điều này phản ánh sự pha trộn giữa (i) nhiễu tán xạ quang học / hút ẩm sol khí khi sương mù mùa Đông và (ii) rửa trôi mưa ẩm vào mùa Xuân–Hè, lý giải vì sao không được xóa bản ghi `RH > 90%` và cũng không đưa `is_high_humidity_fog` vào đặc trưng tuyến tính mặc định nếu thiếu số hạng tương tác mùa.

**Thống kê cờ `is_high_humidity_fog` theo mùa — `VN001` (Baseline 2025–2026) và `VN003` (Extended 2022–2025):**

| Trạm | Mùa | Tổng giờ lưới | Giờ `RH > 90%` | Tỷ lệ `RH > 90%` (%) | `n` hợp lệ (Fog=1 / Fog=0) | Mean PM2.5 (Fog=1 / Fog=0) | Median PM2.5 (Fog=1 / Fog=0) | Chênh lệch Mean (Fog1 − Fog0) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `VN001_HANOI_556_NGUYEN_VAN_CU` | Winter (Dec-Feb) | 2,160 | 655 | 30.32% | 592 / 1,366 | 65.10 / 62.31 | 59.40 / 56.20 | +2.79 µg/m³ |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | Spring (Mar-May) | 2,208 | 654 | 29.62% | 621 / 1,421 | 30.30 / 39.21 | 28.26 / 35.91 | -8.91 µg/m³ |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | Summer (Jun-Aug) | 2,492 | 912 | 36.60% | 597 / 881 | 34.16 / 33.88 | 32.55 / 31.07 | +0.28 µg/m³ |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | Autumn (Sep-Nov) | 2,184 | 613 | 28.07% | 574 / 1,443 | 37.51 / 40.23 | 35.09 / 34.00 | -2.72 µg/m³ |
| `VN003_HANOI_OPENAQ_7441` | Winter (Dec-Feb) | 7,919 | 1,632 | 20.61% | 1,136 / 4,422 | 54.74 / 58.76 | 41.00 / 49.00 | -4.01 µg/m³ |
| `VN003_HANOI_OPENAQ_7441` | Spring (Mar-May) | 7,583 | 2,187 | 28.84% | 1,318 / 3,074 | 37.80 / 43.98 | 34.00 / 40.00 | -6.18 µg/m³ |
| `VN003_HANOI_OPENAQ_7441` | Summer (Jun-Aug) | 6,624 | 2,320 | 35.02% | 1,275 / 2,524 | 27.80 / 29.22 | 25.00 / 25.00 | -1.43 µg/m³ |
| `VN003_HANOI_OPENAQ_7441` | Autumn (Sep-Nov) | 6,552 | 1,824 | 27.84% | 1,170 / 3,289 | 44.30 / 50.58 | 36.00 / 43.00 | -6.27 µg/m³ |

### 1.2. Không chồng lấp thời gian giữa `VN001` và `VN003` (Cảnh báo nhiễu đồng biến)

- `VN003_HANOI_OPENAQ_7441` kết thúc tại `2025-04-09 22:00:00+07:00`; `VN001_HANOI_556_NGUYEN_VAN_CU` bắt đầu tại `2025-07-03 22:00:00+07:00`.
- **Số giờ chồng lấp (`overlap_hours`):** **0 giờ** | **Khoảng trống giữa hai chuỗi:** **2,040 giờ (85.0 ngày)** | **Khoảng cách không gian:** **7.324 km**.
- **Kết luận kiểm toán:** Vì không có bất kỳ giờ đo đồng thời (*co-located / concurrent*) nào giữa hai trạm và không có chuẩn đối chứng phòng thí nghiệm, **không thể kết luận** chênh lệch mức nền giữa `VN001` và `VN003` là do sai lệch hiệu chuẩn cảm biến (*sensor bias*) hay do biến thiên khí tượng giữa các năm và khác biệt vị trí địa lý (*temporal + spatial confounding*). Giao thức **Protocol A** (tách trạm tuyệt đối) được duy trì để ngăn chặn việc gộp hai chuỗi không đồng nhất.

---

## 2. Giả Thuyết 2 — Định Kiến Không Gian (Spatial Representation Bias)

| Trạm / Lưới | Tọa độ (Lat, Lon) | Vai trò dữ liệu | Khoảng cách tới tâm lưới ERA5 (`21.05448, 105.89848`) | Ghi chú đại diện không gian |
|---|---|---|---|---|
| `VN001_HANOI_556_NGUYEN_VAN_CU` (OpenAQ 4946811) | `21.0491, 105.8831` | Baseline chính (07/2025–07/2026) | **1.704 km** | Trạm đô thị trục giao thông Long Biên (556 Nguyễn Văn Cừ) |
| `VN003_HANOI_OPENAQ_7441` (OpenAQ 7441 / AirNow) | `21.021939, 105.818806` | Mở rộng lịch sử tách trạm (01/2022–04/2025) | **9.026 km** | Khu vực nội đô trung tâm (cách `VN001` **7.324 km**) |
| `VN002_HANOI_US_EMBASSY` (AirNow DOS / GitHub mirror) | Nội đô trung tâm (Đại sứ quán Hoa Kỳ) | **Dự phòng / NO-GO** (Issue #44) | — | Mirror GitHub bị từ chối (NO-GO) do thiếu chuẩn xác thực chính thức; chờ CSV chính thống |

- **Giới hạn đại diện đơn trạm:** Cả `VN001` và `VN003` đều đại diện cho môi trường đô thị trung tâm/ven trung tâm Hà Nội, **không** phản ánh đầy đủ độ phơi nhiễm vi môi trường tại các khu công nghiệp ngoại thành, làng nghề (tái chế, đốt mở) hoặc trục đường cao tốc có mật độ xe tải nặng. Ngoài ra, dữ liệu khí tượng ERA5 có độ phân giải ô lưới (~0,25° ≈ 25–28 km), làm mượt các hiện tượng vi khí hậu cục bộ (đảo nhiệt đô thị, hẻm gió, mưa rào cục bộ) đặc biệt khi khoảng cách từ `VN003` tới tâm lưới ERA5 lên tới **9,026 km**.

---

## 3. Giả Thuyết 3 — Định Kiến Sống Sót & Khuyết Thiếu Liên Quan Thời Tiết (Survivorship / Weather-Related Missingness)

### 3.1. Bảng độ phủ và đợt gián đoạn dài nhất theo `(station_id, year, season)`

| Station | Year | Season | Expected Hours | Observed Valid Hours | Missing Hours | Missing (%) | Longest Gap (h) |
|---|---:|---|---:|---:|---:|---:|---:|
| `VN001_HANOI_556_NGUYEN_VAN_CU` | 2025 | Winter (Dec-Feb) | 744 | 623 | 121 | 16.26% | 52 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | 2025 | Summer (Jun-Aug) | 1,418 | 1,326 | 92 | 6.49% | 23 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | 2025 | Autumn (Sep-Nov) | 2,184 | 2,017 | 167 | 7.65% | 24 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | 2026 | Winter (Dec-Feb) | 1,416 | 1,335 | 81 | 5.72% | 15 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | 2026 | Spring (Mar-May) | 2,208 | 2,042 | 166 | 7.52% | 17 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | 2026 | Summer (Jun-Aug) | 1,074 | 152 | 922 | 85.85% | 630 |
| `VN003_HANOI_OPENAQ_7441` | 2022 | Winter (Dec-Feb) | 2,159 | 1,467 | 692 | 32.05% | 504 |
| `VN003_HANOI_OPENAQ_7441` | 2022 | Spring (Mar-May) | 2,208 | 527 | 1,681 | 76.13% | 1,028 |
| `VN003_HANOI_OPENAQ_7441` | 2022 | Summer (Jun-Aug) | 2,208 | 97 | 2,111 | 95.61% | 2,063 |
| `VN003_HANOI_OPENAQ_7441` | 2022 | Autumn (Sep-Nov) | 2,184 | 988 | 1,196 | 54.76% | 665 |
| `VN003_HANOI_OPENAQ_7441` | 2023 | Winter (Dec-Feb) | 2,160 | 1,140 | 1,020 | 47.22% | 474 |
| `VN003_HANOI_OPENAQ_7441` | 2023 | Spring (Mar-May) | 2,208 | 783 | 1,425 | 64.54% | 745 |
| `VN003_HANOI_OPENAQ_7441` | 2023 | Summer (Jun-Aug) | 2,208 | 2,116 | 92 | 4.17% | 44 |
| `VN003_HANOI_OPENAQ_7441` | 2023 | Autumn (Sep-Nov) | 2,184 | 1,607 | 577 | 26.42% | 560 |
| `VN003_HANOI_OPENAQ_7441` | 2024 | Winter (Dec-Feb) | 2,184 | 1,616 | 568 | 26.01% | 490 |
| `VN003_HANOI_OPENAQ_7441` | 2024 | Spring (Mar-May) | 2,208 | 2,152 | 56 | 2.54% | 5 |
| `VN003_HANOI_OPENAQ_7441` | 2024 | Summer (Jun-Aug) | 2,208 | 1,586 | 622 | 28.17% | 589 |
| `VN003_HANOI_OPENAQ_7441` | 2024 | Autumn (Sep-Nov) | 2,184 | 1,864 | 320 | 14.65% | 231 |
| `VN003_HANOI_OPENAQ_7441` | 2025 | Winter (Dec-Feb) | 1,416 | 1,335 | 81 | 5.72% | 66 |
| `VN003_HANOI_OPENAQ_7441` | 2025 | Spring (Mar-May) | 959 | 930 | 29 | 3.02% | 19 |

### 3.2. Kiểm định liên hệ giữa khuyết thiếu `pm25.isna()` và các biến khí tượng

> **Lưu ý diễn giải dưới tự tương quan (`n_eff` caveats):** Chuỗi ngày có tự tương quan bậc 1 rất mạnh (`VN001`: $\rho_1 = 0.7276$, $n = 299$ ngày hợp lệ $\Rightarrow n_{\text{eff}} \approx 47.1$, VIF = 6.34×; `VN003`: $\rho_1 = 0.7487$, $n = 756$ ngày hợp lệ $\Rightarrow n_{\text{eff}} \approx 108.7$, VIF = 6.96×; nguồn `reports/inference_results.md` & `reports/extended_inference_results.md`). Ở cấp độ giờ ($\text{ACF}(1) \approx 0,94$), $p$-value danh định từ kiểm định Mann-Whitney U và tương quan point-biserial giả định độc lập bị **lạc quan quá mức**; do đó phải đánh giá chủ yếu bằng **kích thước hiệu ứng** (`r_rb`, `r_pb`) và chênh lệch trung vị thay vì dựa vào $p$-value đơn độc.

| Station | Biến khí tượng | `n` thiếu / `n` có đo | Trung vị (Thiếu / Có đo) | Mann-Whitney $U$ | $p_{\text{MW}}$ (nominal) | Rank-Biserial $r_{rb}$ | Point-Biserial $r_{pb}$ | $p_{\text{pb}}$ (nominal) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `VN001_HANOI_556_NGUYEN_VAN_CU` | `temperature` | 1,549 / 7,495 | 28.00 / 24.90 | 7,904,272.5 | 1.50e-111 | +0.3617 | +0.2144 | 1.71e-94 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | `relative_humidity` | 1,549 / 7,495 | 82.00 / 83.00 | 5,629,785.5 | 0.0612 | -0.0302 | -0.0183 | 0.0814 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | `wind_speed` | 1,549 / 7,495 | 2.30 / 2.31 | 5,756,394.0 | 0.6043 | -0.0084 | -0.0084 | 0.4229 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | `precipitation` | 1,549 / 7,495 | 0.00 / 0.00 | 6,551,019.5 | 2.67e-25 | +0.1285 | +0.0516 | 9.14e-07 |
| `VN001_HANOI_556_NGUYEN_VAN_CU` | `surface_pressure` | 1,549 / 7,495 | 1002.10 / 1008.90 | 3,450,918.5 | 9.97e-140 | -0.4055 | -0.2410 | 1.04e-119 |
| `VN003_HANOI_OPENAQ_7441` | `temperature` | 10,470 / 18,208 | 24.90 / 24.70 | 99,055,201.5 | 3.10e-08 | +0.0392 | +0.0421 | 1.04e-12 |
| `VN003_HANOI_OPENAQ_7441` | `relative_humidity` | 10,470 / 18,208 | 82.00 / 81.00 | 98,808,148.5 | 2.33e-07 | +0.0366 | +0.0343 | 6.20e-09 |
| `VN003_HANOI_OPENAQ_7441` | `wind_speed` | 10,470 / 18,208 | 2.35 / 2.47 | 92,440,549.0 | 2.01e-05 | -0.0302 | -0.0109 | 0.0650 |
| `VN003_HANOI_OPENAQ_7441` | `precipitation` | 10,470 / 18,208 | 0.00 / 0.00 | 96,260,878.0 | 0.0655 | +0.0099 | +0.0129 | 0.0295 |
| `VN003_HANOI_OPENAQ_7441` | `surface_pressure` | 10,470 / 18,208 | 1008.50 / 1009.60 | 90,917,081.0 | 6.97e-11 | -0.0462 | -0.0432 | 2.40e-13 |

- **Kết luận cơ chế khuyết thiếu (Rubin MCAR/MAR/MNAR):** Dữ liệu **không** thỏa mãn MCAR vì các khoảng khuyết tập trung thành từng khối kéo dài nhiều tuần/tháng (tối đa **630 giờ** ở `VN001` mùa Hè 2026 và **2.568 giờ** ở `VN003` năm 2022) và thể hiện sự khác biệt rõ rệt về điều kiện nhiệt độ/áp suất giữa giai đoạn mất tín hiệu và giai đoạn có đo (phản ánh gián đoạn bảo trì hoặc mùa vụ cụ thể, tương thích giả thuyết MAR theo thời gian/khí tượng hoặc MNAR khi mất điện/mạng trong thời tiết cực đoan). Mọi phân tích thống kê và phân loại trong dự án đều giữ nguyên `NaN` (không nội suy nhãn) và báo cáo minh bạch tỷ lệ độ phủ theo từng mùa/năm.

---

## 4. Giả Thuyết 4 — Định Kiến Biểu Diễn Dữ Liệu (`NaN` vs. `0.0` & Sàng Lọc Sentinel)

| Tập dữ liệu / Trạm | Tổng giờ lưới | Quan sát hợp lệ | `NaN` (Thiếu) | Chính xác `0.0` | Dương (`> 0.0`) | Min – Max (`pm25`) | Giờ bổ sung bởi `pm25_derived_interpolated` (`pm25_is_derived=True`) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline (`air_pollution_final.parquet`) — `VN001_HANOI_556_NGUYEN_VAN_CU` | 9,044 | 7,495 | 1,549 | **0** | 7,495 | 1.06 – 198.95 µg/m³ | 0 |
| Extended (`air_pollution_extended_2022_2026.parquet`) — `VN001_HANOI_556_NGUYEN_VAN_CU` | 9,044 | 7,495 | 1,549 | **0** | 7,495 | 1.06 – 198.95 µg/m³ | 148 |
| Extended (`air_pollution_extended_2022_2026.parquet`) — `VN003_HANOI_OPENAQ_7441` | 28,678 | 18,208 | 10,470 | **9** | 18,199 | 0.00 – 468.00 µg/m³ | 194 |

- **Sàng lọc giá trị âm / sentinel nguồn gốc (`VN003`, từ `reports/issue44_openaq_7441_manifest.json`):** Tổng cộng **3,193** bản ghi âm/sentinel trong tệp thô đã được chuyển thành `NaN` trước khi đóng băng (chi tiết: `-999.0`: **3,188**, `-1.0`: **4**, `-6.0`: **1**). Trong tệp đóng băng cuối cùng, cả `VN001` và `VN003` đều có **0** giá trị âm.
- **Phân tách nghiêm ngặt `NaN` vs. `0.0` và cột phái sinh:**
  - `NaN` biểu thị *không có phép đo hợp lệ* (mất kết nối, kẹt cảm biến, hoặc sentinel đã sàng lọc), tuyệt đối **không** được ép thành `0.0` vì sẽ kéo lệch trung bình phơi nhiễm xuống thấp giả tạo và làm sai lệch tỷ lệ vượt ngưỡng QCVN.
  - `0.0` µg/m³ trong `VN003` (9 giờ trong tổng số 18.208 giờ quan sát, chiếm 0,05%) là giá trị số đọc ở biên dưới thang đo số nguyên của nguồn AirNow/OpenAQ, được giữ tách bạch khỏi `NaN`.
  - Cột `pm25_derived_interpolated` (chỉ điền khoảng trống $\le 2$ giờ hai phía: **148 giờ** trên `VN001`, **194 giờ** trên `VN003`) luôn được lưu tách biệt khỏi cột quan sát gốc `pm25`, đánh dấu bởi `pm25_is_derived`, **không bao giờ** thay thế nhãn mục tiêu $y_t$, và chỉ dùng cho kiểm tra độ nhạy ngoại tuyến (*offline sensitivity*).

---

## 5. Ma Trận Tổng Hợp Rủi Ro Đạo Đức & Biện Pháp Kiểm Soát

| Loại định kiến | Bằng chứng định lượng cốt lõi | Biện pháp kiểm soát đã thực thi trong dự án |
|---|---|---|
| **1. Sensor Bias** | `fog × season` F(3, 7487) = 16.78 (p = 7.38e-11); 0 giờ chồng lấp giữa VN001 và VN003 | Giữ nguyên bản ghi `RH > 90%` kèm cờ `is_high_humidity_fog`; loại khỏi tập đặc trưng tuyến tính mặc định; áp dụng Protocol A đơn trạm |
| **2. Spatial Bias** | 2 trạm nội đô/ven trung tâm cách nhau 7,324 km; khoảng cách tới lưới ERA5 là 1,704 km (`VN001`) và 9,026 km (`VN003`) | Giới hạn rõ phạm vi diễn giải tại khu vực đô thị Hà Nội trong Model Card & Datasheet; không ngoại suy sang khu công nghiệp/làng nghề |
| **3. Survivorship / Missingness** | Thiếu 17,13% (`VN001`) và 36,51% (`VN003`); gap dài nhất 630h / 2.568h; $n_{\text{eff}} \approx 47,1$ / $108,7$ ngày | Bảo toàn `NaN` (`assert_no_imputation()`); dùng calendar block bootstrap giữ nguyên mặt nạ thiếu; ghi nhãn `UNESTIMABLE` khi Test không có ca dương |
| **4. Representation (`NaN` vs `0.0`)** | 1.549 / 10.470 `NaN` vs. 0 / 9 giá trị `0.0`; sàng lọc 3.193 sentinel `-999/-1/-6` | Tách biệt hoàn toàn `pm25` quan sát gốc với `pm25_derived_interpolated`; cấm gán `NaN = 0` trong toàn bộ pipeline |
