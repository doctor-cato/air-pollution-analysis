# Tài Liệu Chuẩn Bị Phản Biện Hội Đồng (Viva QA Prep — 15 Câu Hỏi Trọng Tâm)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (Trường Đại học CMC)  
> **Phạm vi:** Issue #16 (Task 10.4 & Task D23 trong [`docs/TASK_LIST_M3_M6.md`](TASK_LIST_M3_M6.md))  
> **Nguyên tắc học thuật:** Mọi con số dưới đây được trích xuất trực tiếp từ các artifact đã kiểm chứng trên `main`; tuyệt đối không đưa khẳng định nhân quả hoặc số liệu chưa chạy.

---

## Nhóm 1 — Suy Luận Thống Kê, Phụ Thuộc Thời Gian & Kiểm Định Giả Thuyết (W9 / #11)

### Q1. Vì sao nhóm tổng hợp về trung bình ngày ($\ge 18/24\text{h}$) thay vì chạy kiểm định trực tiếp trên $9.044$ dòng theo giờ?
**Trả lời mẫu:**  
Chuỗi giờ `pm25` có hệ số tự tương quan bậc 1 rất cao ($\text{ACF}(1) = 0,9403$; $\text{ACF}(24) = 0,5988$; [`reports/inference_results.md`](../reports/inference_results.md) §1, §4.1), nên $9.044$ giờ không phải $9.044$ quan sát độc lập; áp dụng các kiểm định giả định độc lập trên dữ liệu giờ sẽ làm cỡ mẫu ảo phình to và tạo ra $p$-value lạc quan giả tạo. Tổng hợp về trung bình ngày (yêu cầu $\ge 18/24$ giờ hợp lệ — lựa chọn phân tích độ phủ $75\%$ của dự án, cho $n = 299$ ngày trên $378$ ngày lịch) vừa giảm tự tương quan, vừa khớp chu kỳ lấy mẫu 24 giờ của QCVN 05:2023/BTNMT ($50\,\mu\text{g/m}^3$). Ngay cả ở mức ngày, chuỗi vẫn có $\rho_1 = 0,7276 \Rightarrow n_{\text{eff}} \approx 47,1$ (hệ số lạm phát $\times 6,34$), do đó nhóm phải hiệu chỉnh phụ thuộc thời gian bằng Newey–West HAC (lag 28 ngày) và circular moving-block bootstrap theo lịch ngày (block 28 ngày lịch, giữ nguyên mặt nạ ngày thiếu).

### Q2. Khi hiệu chỉnh phụ thuộc thời gian và Holm–Bonferroni, kết luận W9 thay đổi như thế nào so với kiểm định giả định độc lập?
**Trả lời mẫu:**  
Nếu chạy kiểm định giả định độc lập thông thường của SciPy, $3/4$ kiểm định trong family xác nhận bác bỏ $H_0$ ([`reports/inference_results.md`](../reports/inference_results.md) §8). Sau khi dựng lại $p$-value dưới $H_0$ có xét tự tương quan thời gian và hiệu chỉnh Holm–Bonferroni (family 4 kiểm định cố định trước khi xem dữ liệu):
1. **Trung bình giai đoạn vs $25\,\mu\text{g/m}^3$:** $t_{\text{HAC}} = 4,354$, $p_{\text{HAC}} = 1,84\cdot 10^{-5}$, $p_{\text{Holm}} = 7,38\cdot 10^{-5}$, Cohen's $d = 0,848$ → **Bác bỏ $H_0$ (XÁC NHẬN)** (chỉ báo mức nền giai đoạn 07/2025–07/2026, không phải phán quyết tuân thủ năm dương lịch).
2. **Ngưỡng 24h ($50\,\mu\text{g/m}^3$):** $t_{\text{HAC}} = -2,656$, $p_{\text{HAC}} = 0,0083$, $p_{\text{Holm}} = 0,0250$, $r = -0,410$ → **Bác bỏ $H_0$ (XÁC NHẬN)** (`84/299 = 28,09%` ngày vượt $50\,\mu\text{g/m}^3$, trung vị $37,20\,\mu\text{g/m}^3$ nằm dưới $50$).
3. **Ngày làm việc vs cuối tuần:** $t_{\text{HAC}} = 1,611$, $p_{\text{HAC}} = 0,1082$, $p_{\text{Holm}} = 0,1082$, $r_{rb} = -0,117$, chênh lệch trung vị $-2,74\,\mu\text{g/m}^3$, CI 95% $[-11,13;\ 3,05]$ → **Không bác bỏ $H_0$ (XÁC NHẬN)**.
4. **Biến thiên 4 mùa:** $H = 61,534$, $p_{\text{boot}} = 0,0280$, $p_{\text{Holm}} = 0,0560$, $\varepsilon^2 = 0,206$ → **Không bác bỏ $H_0$ sau Holm**, và theo quy tắc R5 luôn giữ trạng thái **THĂM DÒ (EXPLORATORY)** vì chỉ có một chu kỳ mùa duy nhất (4 mùa là 4 đoạn thời gian liên tiếp nên mùa bị trộn lẫn với xu hướng thời gian).

### Q3. Nêu 4 sai lầm phổ biến khi đọc $p$-value, ý nghĩa đúng của Khoảng tin cậy (CI 95%), Type I/II và Power/MDE trong bài toán cảnh báo ô nhiễm?
**Trả lời mẫu:**  
- **4 sai lầm $p$-value:** (1) Nhầm $p$ là $P(H_0 \mid D)$ — thực tế $p = P(\text{thống kê cực đoan bằng hoặc hơn} \mid H_0 \text{ đúng})$; (2) Nhầm $p$ nhỏ là hiệu ứng lớn (cần đọc kèm effect size $r_{rb}$, $\varepsilon^2$, Cohen's $d$); (3) Coi $p > 0,05$ là chứng minh $H_0$ đúng (trong kiểm định weekday/weekend, $n_1=213, n_2=86$ chỉ đạt $\text{MDE} \approx 7,75\,\mu\text{g/m}^3$ ở power $80\%$ ngay cả khi giả định độc lập, nên chênh lệch $-2,74\,\mu\text{g/m}^3$ nằm dưới ngưỡng phân giải); (4) Đọc đồng thời nhiều kiểm định mà không hiệu chỉnh FWER (Holm–Bonferroni).
- **CI 95%:** Trong tần suất luận, nếu lặp lại quy trình lấy mẫu và dựng khoảng tin cậy theo cùng thiết kế, $95\%$ số khoảng tin cậy sẽ chứa tham số tổng thể thực. Trong [`src/inference.py`](../src/inference.py), CI 95% của hiệu ứng (`calendar_contrast_ci()`) và $p$-value dưới $H_0$ là hai câu hỏi khác nhau nên được dựng tách biệt.
- **Sai lầm loại I ($\alpha$) vs loại II ($\beta$) & Power ($1-\beta$):** Báo động giả (False Positive, loại I) gây phiền toái vận hành, nhưng **bỏ sót đợt ô nhiễm độc hại** (False Negative, loại II) gây rủi ro sức khỏe cộng đồng trực tiếp. Vì vậy ở phân loại cảnh báo (#13), nhóm tối ưu ngưỡng theo $F_2$ (ưu tiên Recall cao hơn Precision).

---

## Nhóm 2 — Hồi Quy Tuyến Tính OLS, Chẩn Đoán LINE & Diễn Giải Phi Nhân Quả (W10 / #12)

### Q4. Mô hình OLS đạt Train $R^2 = 0,3747$ trên `VN001_baseline` nhưng Test $R^2 = -1,9540$: nguyên nhân kỹ thuật là gì và vì sao không được dùng $R^2$ để kết luận dự báo?
**Trả lời mẫu:**  
Có hai nguyên nhân đã được chứng minh thực nghiệm trong [`docs/regression_findings.md`](regression_findings.md) §4–§5:
1. **Lỗi ngoại suy mùa vụ (*Seasonal Extrapolation Bug*) khi Train chỉ dài ~6,4 tháng:** Tập Train của `VN001_baseline` (`07/2025–01/2026`) chỉ phủ nửa chu kỳ năm, khiến **$65,0\%$ mẫu Test (`01–07/2026`) rơi hoàn toàn ngoài dải `month_sin` đã học**, đẩy trung bình dự báo lên $75,24$ so với thực tế $41,46\,\mu\text{g/m}^3$ ($\text{bias} = +33,78\,\mu\text{g/m}^3$, Test $\text{RMSE} = 41,46\,\mu\text{g/m}^3$). Khi bỏ `month_sin`/`month_cos`, Test $R^2$ cải thiện từ $-1,9540$ lên $-0,1604$; còn trên chuỗi đa năm `VN003_extended` (`0,0%` Test ngoài dải `month_sin`), OLS đạt Test $R^2 = +0,1498$ ($\text{RMSE} = 32,82$ vs Dummy $37,73\,\mu\text{g/m}^3$).
2. **Vi phạm cả 4 giả định LINE:** Trên cả 3 cohort, Ramsey RESET ($p < 10^{-48}$), Durbin–Watson ($0,2079\text{–}0,3033$, $\text{ACF}(1) = 0,848\text{–}0,896$), Jarque–Bera ($p \le 5,32\cdot 10^{-86}$), và Breusch–Pagan ($p \le 6,44\cdot 10^{-136}$) đều vi phạm mạnh. Vì vậy OLS chỉ mô tả xu hướng tuyến tính tổng quát trên Train, phải suy luận bằng sai số chuẩn HAC Newey–West ($L = 24\text{h}$ và độ nhạy tới $168\text{h}$), và tuyệt đối không dùng $R^2$ làm thước đo dự báo vận hành.

### Q5. Giải thích biến `wind_speed` trong mô hình OLS theo đúng 3 nghĩa vụ diễn giải, và vì sao giữ lại các điểm có Cook's $D > 4/n$?
**Trả lời mẫu:**  
- **Diễn giải đúng 3 nghĩa vụ** ([`docs/regression_findings.md`](regression_findings.md) §3.4): Trên cả 3 phạm vi, hệ số `wind_speed` âm và bền vững qua mọi độ trễ HAC tới $168\text{h}$: $\beta = -6,0673$ ($p_{\text{HAC-24}} = 5,63\cdot 10^{-8}$) trên `VN001_baseline`, $\beta = -7,2891$ ($p_{\text{HAC-24}} = 6,48\cdot 10^{-21}$) trên `VN001_extended`, và $\beta = -6,2864$ ($p_{\text{HAC-24}} = 1,09\cdot 10^{-44}$) trên `VN003_extended`. Diễn giải chuẩn: *trong miền giá trị khí tượng quan sát của tập Train, mỗi $1\text{ m/s}$ tốc độ gió tăng thêm **liên hệ với** mức giảm $6,07\text{–}7,29\,\mu\text{g/m}^3$ nồng độ $\text{PM}_{2.5}$ trung bình giờ trong điều kiện giữ nguyên các biến còn lại (ceteris paribus)* — đây là **liên hệ thống kê quan sát**, không phải can thiệp nhân quả độc lập.
- **Giữ điểm Cook's $D > 4/n$:** Dù có $267$ điểm (`VN001_baseline`), $353$ điểm (`VN001_extended`), và $591$ điểm (`VN003_extended`) vượt $4/n$, giá trị cực đại $D_{\max}$ chỉ đạt **$0,0072\text{–}0,0174 \ll 0,5$** (`0` điểm vượt ngưỡng $0,5$ hoặc $1,0$). Các điểm này tương ứng với các đợt nghịch nhiệt mùa Đông thực tế nên được giữ nguyên $100\%$ để tránh xóa mất cực trị ô nhiễm.

### Q6. Nhóm đã xử lý đa cộng tuyến (VIF) và biến đổi $\log(1+\text{PM}_{2.5})$ như thế nào?
**Trả lời mẫu:**  
- **Loại `pm10` & kiểm tra VIF:** Tương quan Pearson giữa `pm25` và `pm10` là $r = 0,9727$ ($r^2 = 0,9462$), nên `pm10` bị loại trước khi huấn luyện. Trong 9 biến giải thích còn lại, không biến nào vượt ngưỡng nghiêm trọng $\text{VIF} \ge 10$; cặp `surface_pressure` ($\text{VIF} = 5,955\text{–}8,061$) và `temperature` ($\text{VIF} = 5,730\text{–}7,655$) nằm trong vùng cảnh báo $[5,\ 10)$ do quan hệ nghịch biến nhiệt–áp đặc trưng gió mùa Bắc Bộ, nên nhóm huấn luyện song song Ridge ($L_2$) và Lasso ($L_1$) với $\alpha$ dò tìm hoàn toàn trên Train qua 5-fold `TimeSeriesSplit`.
- **Biến đổi mục tiêu `log1p(pm25)`:** Được khảo sát trên Train (`VN001_baseline`) nhưng làm đảo dấu độ lệch thành lệch trái ($\text{skew} = -0,958$) và không khắc phục được vi phạm LINE nên báo cáo chính giữ đơn vị gốc $\mu\text{g/m}^3$ để bảo toàn tính diễn giải trực tiếp ([`docs/regression_findings.md`](regression_findings.md) §4).

---

## Nhóm 3 — Mô Hình Phân Loại Cảnh Báo Sớm, Ngưỡng Quyết Định & Chồng Lấn Cửa Sổ (W11 / #13)

### Q7. Vì sao Accuracy của `DummyClassifier` ($71,07\%$) gây hiểu lầm, và bài toán chọn thước đo & tối ưu ngưỡng như thế nào?
**Trả lời mẫu:**  
Trên tập Test hợp lệ của `VN001_baseline` ($n_{\text{eval}} = 2.302$ giờ, $666$ ca dương, tỷ lệ dương tính = **$28,93\%$**), `DummyClassifier(strategy='prior')` luôn dự báo lớp âm nên đạt Accuracy **$71,07\%$** nhưng **Recall = $0,00\%$** và **PR-AUC = $0,2893$** ([`docs/classification_findings.md`](classification_findings.md) §2). Nhóm sử dụng **PR-AUC** (đối chiếu trực tiếp với đường cơ sở prevalence $0,2893$) thay cho Accuracy/ROC thuần túy, đồng thời tối ưu ngưỡng $\tau^*$ hoàn toàn trên dự báo OOF của 5-fold `TimeSeriesSplit` trong Train theo hàm mục tiêu $F_2$ ($\beta = 2$, ưu tiên Recall để hạn chế bỏ sót đợt ô nhiễm) trước khi khóa cứng ngưỡng để đánh giá 1 lần trên Test. Kết quả trên Test `VN001_baseline`: Random Forest ($\tau^* = 0,32$) đạt **Recall = $100,00\%$** ($666/666$), Precision = $96,10\%$, $F_2 = 0,9920$, FAR = $1,65\%$, PR-AUC = $0,9985$; Logistic Regression ($\tau^* = 0,43$) đạt Recall = $99,55\%$ ($663/666$), Precision = $94,18\%$, PR-AUC = $0,9989$.

### Q8. Theo cảnh báo W11 (*"nghi ngờ ngay nếu điểm > 99%"*), vì sao Recall và PR-AUC tại $h=0$ đạt $\approx 99,8\%$–$100\%$? Có phải do rò rỉ dữ liệu không?
**Trả lời mẫu:**  
Đây **không phải rò rỉ dữ liệu tương lai**, mà là hệ quả toán học tất định của **chồng lấn cửa sổ trượt 23/24 giờ ($95,8\%$)** tại tầm truy hồi $h = 0\text{h}$ ([`docs/leakage_audit.md`](leakage_audit.md) §3):
- Đặc trưng `pm25_rolling_mean_24h` chỉ đọc quá khứ $[t-24,\ t-1]$ (tuyệt đối không đọc $t$), trong khi nhãn mục tiêu $y_t$ tính trên $[t-23,\ t]$. Hai cửa sổ dùng chung $23/24$ giờ, ngay cả `PersistenceRuleClassifier` đơn biến cũng đạt PR-AUC = $0,9992$ và Recall = $98,50\%$.
- Nhóm chứng minh không có rò rỉ bằng ablation đa tầm có purge gap (`t + h < split_timestamp`) trong [`reports/classification_leakage_audit.md`](../reports/classification_leakage_audit.md) §3: khi loại bỏ rolling 24h (`Lag24 + Met`), PR-AUC giảm từ $0,9989 \to 0,7908$ (LogReg) và $0,9985 \to 0,7364$ (RF); khi chỉ dùng khí tượng (không có $\text{PM}_{2.5}$ quá khứ), PR-AUC còn $0,4338$ (LogReg) / $0,5954$ (RF); và khi dự báo xa tới $h = 24\text{h}$ (chồng lấn $0/24$ giờ), PR-AUC giảm về $0,7513$ (LogReg) và $0,5876$ (RF).

### Q9. Vì sao có hai tỷ lệ prevalence $31,13\%$ và $18,30\%$ (và $28,93\%$ trên tập Test đánh giá) — có mâu thuẫn số liệu không?
**Trả lời mẫu:**  
Không mâu thuẫn; đó là **các mẫu số khác nhau trên cùng tử số** và đã được đối soát nhất quán qua 4 quần thể trong [`docs/data_dictionary.md`](data_dictionary.md) §10.2 và [`reports/classification_results.md`](../reports/classification_results.md) §1:
1. Toàn lưới thời gian: `1.655 / 9.044 = 18,30%` (Train `986/4.682 = 21,06%`, Test `669/4.362 = 15,34%`).
2. Đủ nhãn 24h hợp lệ (`min_periods=24`): `1.655 / 5.317 = 31,13%` (Train `986/2.994 = 32,93%`, Test `669/2.323 = 28,80%`).
3. Đủ cả nhãn 24h và đặc trưng trễ 24h quá khứ (`Evaluable` trong mô hình): `1.644 / 5.267` (Train `978/2.965 = 32,98%`, Test `666/2.302 = 28,93%`).
Mọi chỉ số baseline PR-AUC đều đối chiếu đúng với mẫu số evaluable của chính tập đó (`0,2893` trên Test `VN001_baseline`), không trộn mẫu số giữa Train và Test.

---

## Nhóm 4 — Kiểm Toán Rò Rỉ Dữ Liệu (4 Dạng Rò Rỉ) & Loại Trừ Biến / SMOTE (#7, #12, #13)

### Q10. Nhóm kiểm soát 4 dạng rò rỉ dữ liệu như thế nào, và vì sao `validate_no_leakage()` không tự bắt được rò rỉ của `pm25_was_missing`?
**Trả lời mẫu:**  
Cơ chế kiểm soát 4 dạng rò rỉ được ghi trong [`docs/leakage_audit.md`](leakage_audit.md) §1 và [`src/cleaning_pipeline.py`](../src/cleaning_pipeline.py):
1. **Target Leakage:** Cấm `pm25`, `pm10`, `pm25_was_missing`, `is_high_humidity_fog` khỏi ma trận đặc trưng (`FORBIDDEN_CLASSIFICATION_COLS` / `TARGET_DERIVED_FLAGS`), và mọi đặc trưng trượt đều dùng `shift(1)` (kiểm chứng bằng unit test đột biến `pm25[t] = 999` không làm đổi $X_t$).
2. **Train-Test Contamination:** `SimpleImputer(median)` và `RobustScaler` nằm trong `sklearn.pipeline.Pipeline`, chỉ `fit()` trên Train (hoặc bên trong từng fold của `TimeSeriesSplit`) và kiểm tra sau fit bằng `validate_no_leakage()`.
3. **Temporal Leakage:** Chia tuyến tính `train_max < test_min`, kèm purge gap `t + h < split_timestamp` cho $h > 0$.
4. **Group / Station Leakage:** Áp dụng Protocol A đơn trạm (`_select_single_station()` fail-closed nếu trộn nhiều trạm) và `groupby("station_id")` trước mọi phép `shift`/`rolling`.
- **Vì sao `validate_no_leakage()` không bắt được `pm25_was_missing`:** Vì imputer và scaler vẫn chỉ học từ Train một cách hợp lệ, nhưng `SimpleImputer` điền đúng `median` vào các dòng `pm25_was_missing == 1`, tạo rò rỉ cấu trúc `flag == 1 ⇒ pm25 == median` ($100\%$ ở cả $256/256$ dòng Train lẫn $1.033/1.033$ dòng Test). Do đó phải loại ở tầng danh sách đặc trưng (`TARGET_DERIVED_FLAGS`), chứ không chỉ kiểm tham số sau fit.

### Q11. Vì sao loại `is_high_humidity_fog` khỏi feature mặc định dù F-test `fog × mùa` có $p = 7,4\cdot 10^{-11}$, và vì sao không dùng SMOTE cho mất cân bằng lớp?
**Trả lời mẫu:**  
- **Về `is_high_humidity_fog`:** Ở mức đơn biến/marginal, `corr(pm25, RH) = -0,0365` và trung bình nhóm có cờ ($41,65\,\mu\text{g/m}^3$, $n=2.384$) thấp hơn nhóm không cờ ($44,75\,\mu\text{g/m}^3$, $n=5.111$). Tuy nhiên [`src/flag_evidence.py`](../src/flag_evidence.py) chứng minh cờ có tương tác đảo chiều theo mùa ($F(3, 7487) = 16,78$, $p = 7,38\cdot 10^{-11}$; Đông $+2,79$ vs Xuân $-8,91\,\mu\text{g/m}^3$), nên giữ cờ trong dataset như cột chẩn đoán và loại khỏi tập feature tuyến tính mặc định (`NON_PREDICTIVE_FLAGS`) thay vì lẫn lộn lý do loại với target leakage.
- **Về SMOTE:** SMOTE nội suy tuyến tính giữa các mẫu không liền kề theo thời gian trong không gian đa biến, dễ ghép hai bối cảnh synop/mùa khác nhau, tạo tổ hợp khí tượng phi vật lý và phá vỡ cấu trúc tự tương quan thời gian. Thay vào đó, nhóm dùng `class_weight='balanced'` kết hợp tối ưu ngưỡng $\tau^*$ trên OOF của Train ([`docs/leakage_audit.md`](leakage_audit.md) §2).

---

## Nhóm 5 — Đạo Đức Dữ Liệu, Quy Mô vs Spark (#14) & Mở Rộng Lịch Sử (#44, #50)

### Q12. Tập dữ liệu có cần Apache Spark không, và vì sao các khái niệm như `k-anonymity` hay Nghị định 13/2023/NĐ-CP được ghi là không áp dụng?
**Trả lời mẫu:**  
- **Về quy mô & Spark:** Theo khung ngưỡng tài liệu W12 (`< 10 GB`: Pandas/Polars, `10–100 GB`: DuckDB/PostgreSQL, `> 100 GB`: Spark), tập baseline chỉ có **`9.044 × 18` (~261 KB)** và tập mở rộng `2.0.0-issue44-extended` có **`37.722 × 23`** — nhỏ hơn ngưỡng $10\text{ GB}$ khoảng $4$ bậc độ lớn, xử lý hoàn chỉnh trên máy đơn lẻ với Pandas/NumPy/Scikit-Learn mà không cần cụm phân tán Spark/Hadoop (vốn còn bị loại trừ khỏi kiến trúc dự án để tránh dư thừa công nghệ). Lưu ý bảng benchmark đo đạc chi tiết trước/sau tối ưu thuộc phần việc còn lại của Issue #14.
- **Về `k-anonymity`, `Fairness–Accuracy`, `Anonymisation/Pseudonymisation` & Nghị định 13/2023/NĐ-CP:** Theo quy định chuẩn Issue #14 (Task 1.24, tài liệu hóa tại `docs/datasheet.md`), dữ liệu hoàn toàn là phép đo vật lý môi trường công khai (`ODC-BY v1.0`, `US Public Domain`, `CC BY 4.0`) từ 2 trạm quan trắc cố định và ô lưới ERA5; không có đối tượng cá nhân, quasi-identifier hay thuộc tính nhạy cảm nhân khẩu học nên không phát sinh dữ liệu cá nhân theo Khoản 1 Điều 2 Nghị định 13/2023/NĐ-CP.

### Q13. Vì sao không gộp `VN003` (2022–2025) và `VN001` (2025–2026) thành một chuỗi đơn trạm (Protocol B), và vì sao từ chối mirror GitHub `VN002` lẫn dữ liệu giao thông cho `FIG-04`?
**Trả lời mẫu:**  
- **Từ chối Protocol B (station effect & rò rỉ thời gian):** Hai trạm cách nhau **$7,324\text{ km}$** (`VN003` tại `21.0219°N, 105.8188°E`, cách lưới ERA5 `9,026 km`; `VN001` tại `21.0491°N, 105.8831°E`, cách lưới ERA5 `1,704 km`), thiết bị/mạng lưới khác nhau (`AirNow Gov Monitor` vs `NCEM/VEA`), và cửa sổ thời gian **không chồng lấp** (cách nhau `2.040` giờ trống). Nếu gộp chuỗi sẽ trộn *station effect* với biến động liên năm; nếu dùng `Protocol B` pooled với split theo trạm sẽ rò rỉ tương lai `VN001` (2025–2026) sang `VN003` Test (2024–2025), còn split cắt ngang toàn cục sẽ đẩy `VN003` sang toàn bộ Train và `VN001` sang toàn bộ Test ([`docs/issue44_dataset_contract.md`](issue44_dataset_contract.md) §4).
- **Từ chối mirror `VN002` & giao thông (`NO-GO`):** Mirror GitHub bên thứ ba có `repository_license: null`, `3` tệp tháng 12 xếp sai thư mục năm, `4` tệp chứa bản ghi chéo năm và `1` xung đột `conflicting_duplicate` ([`reports/issue44_mirror_manifest.json`](../reports/issue44_mirror_manifest.json)). Dữ liệu giao thông Hà Nội theo giờ 2022–2026 không có nguồn công khai hợp lệ về tọa độ/giấy phép ([`docs/issue44_traffic_source_assessment.md`](issue44_traffic_source_assessment.md)).

### Q14. Phản hồi của giảng viên về nội suy giờ thiếu được kiểm chứng thế nào, và vì sao nhánh nội suy không dùng làm ground truth hay feature cảnh báo sớm?
**Trả lời mẫu:**  
Thí nghiệm *masking-validation* trên các giá trị quan trắc thật ([`src/issue44_preparation.py`](../src/issue44_preparation.py), [`reports/issue44_interpolation_evaluation.csv`](../reports/issue44_interpolation_evaluation.csv), `160` dòng đánh giá `max_gap` $\in \{1,2,3,6\}\text{h}$) cho thấy nội suy tuyến tính $\le 2\text{h}$ chỉ khôi phục được **$1,85\%$** số giờ thiếu của `VN003` (`194/10.470`) và **$9,55\%$** của `VN001` (`148/1.549`), trong khi tạo sai số RMSE tổng thể `6,55–10,91 µg/m³` và lên tới **`12,40–17,24 µg/m³` vào mùa Đông**. Quan trọng hơn, nội suy tuyến tính giữa $t-1$ và $t+1$ sử dụng **điểm cuối tương lai ($t+1$)** nên gây rò rỉ nếu đưa vào bài toán cảnh báo sớm. Do đó, cột quan trắc `pm25` giữ nguyên `NaN`, giá trị nội suy cô lập ở `pm25_derived_interpolated` / `pm25_is_derived`, và chỉ dùng trong nhánh phân tích độ nhạy có dán nhãn.

### Q15. Những giới hạn về khái quát hóa theo thời gian (*chronological generalization*), độ trễ ERA5 và tính tái lập của bản mở rộng cần nêu trung thực là gì?
**Trả lời mẫu:**  
1. **Khái quát hóa phân loại trên `VN001_extended_80_20`:** Khi cắt 80/20 tại `2026-05-01 09:00+07:00`, tập Test rơi vào mùa Hè ít ô nhiễm kèm sự cố gián đoạn **630 giờ** (`2026-06-19 → 2026-07-15`), kết quả chỉ còn `242` giờ đánh giá và **`0` ca dương tính**. Hệ thống báo cáo trung thực `PR-AUC`, `ROC-AUC`, `Recall`, `Calibration` là **`UNESTIMABLE`** thay vì ép tính điểm số ([`docs/classification_findings.md`](classification_findings.md) §4).
2. **Độ trễ ~5 ngày của ERA5:** Dữ liệu tái phân tích ERA5 không có sẵn theo thời gian thực ở thời điểm $t$, nên thiết lập $h=0$ là *retrospective nowcast*; triển khai thực tế đòi hỏi thay bằng nguồn NWP forecast có *issue time* hợp lệ.
3. **Giới hạn tái lập snapshot ERA5 cũ (`Issue #50`):** Tệp JSON thô Open-Meteo 2022–2025 gốc (SHA-256 `303aacb6...`) không có trên máy cục bộ khi chạy Issue #50; bản tải lại có đủ `28.680` bản ghi nhưng SHA-256 khác (`a0d841fc...`), nên sự đồng nhất giá trị từng ô ERA5 với snapshot cũ được gắn nhãn **`UNVERIFIED`** ([`docs/issue50_reproducibility.md`](issue50_reproducibility.md)). Các kiểm định mùa vụ trên cả `VN001` và `VN003` giữ nguyên nhãn `exploratory`.
