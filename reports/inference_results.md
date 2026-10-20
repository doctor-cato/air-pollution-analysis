# Kết quả Suy luận Thống kê — Issue #11 (W9)

> **Tệp này được sinh tự động** bởi `src/inference.py::render_inference_report()`
> từ `notebooks/05_statistical_inference.ipynb`. Không sửa tay: mọi con số
> dưới đây lấy trực tiếp từ `run_inference()` trên dataset đã đóng băng.

| Trường | Giá trị |
|---|---|
| Issue | #11 |
| Mức ý nghĩa α (chốt trước khi xem dữ liệu) | 0,05 |
| Bootstrap | 1.000 lặp · block 7 ngày · seed 42 · CI percentile 95% |
| Đơn vị phân tích | Trung bình ngày (≥ 18/24 giờ có `pm25`) |
| Nguồn dữ liệu | `C:\Users\Admin\Documents\code_workspace\khdl\data\processed\air_pollution_final.parquet` |
| SHA-256 dataset | `866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd` |
| NumPy / SciPy | 2.5.3 / 1.18.1 |

---

## 1. Đơn vị phân tích và nhật ký lọc mẫu

- Chuỗi giờ: **9.044** dòng, trong đó **7.495** giờ có `pm25` và **1.549** giờ thiếu.
- Dải quan sát (giờ có `pm25`): **2025-07-03 → 2026-07-15** (378 ngày lịch, 1 trạm); ngày đủ độ phủ đầu–cuối: 2025-07-04 → 2026-05-29.
- Ngày có ít nhất một giờ đo: **351**; ngày đủ 24/24 giờ: **223**.
- Ngày đạt tiêu chí ≥ 18/24 giờ: **299** — đây là cỡ mẫu của mọi kiểm định (n = 299).
- Ngày bị loại vì thiếu độ phủ: **52**.
- Ngày làm việc / cuối tuần trong panel: **213** / **86**.

**Vì sao không dùng từng giờ làm đơn vị phân tích.** ACF bậc 1 của chuỗi giờ là 0,9403 — 9.044 giờ không phải bấy nhiêu quan sát độc lập. Tổng hợp về ngày là bước giảm tự tương quan **bắt buộc**, không phải tuỳ chọn trình bày. Tiêu chí ≥ 18/24 giờ là **lựa chọn phân tích của dự án** (độ phủ 75%), không phải điều khoản của QCVN 05:2023/BTNMT.

**Vì sao không dùng Train/Test split.** Các phép kiểm dưới đây không fit mô hình, không chọn siêu tham số và không đánh giá năng lực dự báo, nên không có đường rò rỉ Test → Train. Chạy trên toàn bộ giai đoạn quan sát để tận dụng cỡ mẫu và để kiểm định trung bình năm có trọn chu kỳ. Điểm cắt `2026-01-15 00:00+07:00` của Issue #7 **không bị thay đổi**.

---

## 2. Chẩn đoán phân phối (không mặc định chuẩn / không chuẩn)

| Chỉ số | Giá trị |
|---|---|
| n (ngày) | 299 |
| Trung bình ± SD | 43,38 ± 21,68 µg/m³ |
| Trung vị [IQR] | 37,20 [28,83; 51,83] µg/m³ |
| Min – Max | 8,33 – 115,09 µg/m³ |
| Skewness (hiệu chỉnh mẫu) | 1,2143 |
| Excess kurtosis | 0,9349 |
| Hình dạng (mô tả định lượng) | lệch mạnh về phía phải, đuôi dày hơn chuẩn |
| Shapiro-Wilk | W = 0,8873, p = 4,59·10⁻¹⁴ |
| D'Agostino K² | K² = 56,328, p = 5,87·10⁻¹³ |
| Số ngày ngoài ±3 SD | 2 |

Cả hai kiểm định chuẩn tắc đều bác bỏ tính chuẩn, nhưng **đó không phải lý do duy nhất** để chọn phép kiểm phi tham số. Với n cỡ này, Shapiro-Wilk có power đủ để phát hiện lệch nhỏ không có ý nghĩa thực tiễn; vì vậy quyết định dựa thêm vào (a) skewness và kurtosis quan sát được, (b) bản chất thang đo — nồng độ bị chặn dưới 0, phân phối lệch phải, có outlier đợt ô nhiễm, và (c) các phép kiểm phi tham số so sánh **trung vị/hạng**, đúng với câu hỏi về mức nền phơi nhiễm hơn là về trung bình số học. Q-Q plot: `figures/FIG-08.png`.

---

## 3. Tự tương quan và cỡ mẫu hiệu dụng

- ACF chuỗi **giờ**: lag 1 = 0,9403 · lag 2 = 0,8371 · lag 3 = 0,7432 · lag 24 = 0,5988 · lag 168 = 0,3449.
- ACF chuỗi **ngày**: lag 1 = 0,7276 · lag 2 = 0,5484 · lag 3 = 0,4239 · lag 7 = 0,3700 · lag 14 = 0,3172.
- AR(1) của chuỗi ngày: ρ = 0,7276 → n_eff ≈ **47,1** so với n = 299 (hệ số lạm phát ×6,34).

**Hệ quả và cách xử lý.** Mann-Whitney, Kruskal-Wallis, Wilcoxon và t-test đều giả định quan sát độc lập. Ở mức ngày, giả định đó **không** được bảo đảm (ρ = 0,73), nên p-value của chúng là **lạc quan** — đây là giới hạn được nêu thẳng, không được che. Biện pháp đã áp dụng: (1) hạ đơn vị phân tích từ giờ xuống ngày; (2) mọi CI dùng **block bootstrap 7 ngày**, không resample từng quan sát; (3) thêm hai **kiểm tra độ nhạy** ở mức tuần (mục 8) — nơi tự tương quan thấp hơn nhiều; (4) không dùng p-value để tuyên bố 'hiệu ứng lớn': mọi kết luận đọc kèm effect size và CI.

---

## 4. Kiểm định 1 — Khác biệt giữa các mùa

**H₀:** trung vị `pm25` trung bình ngày bằng nhau giữa bốn mùa. **H₁:** có ít nhất một mùa khác biệt. **α = 0,05, hai phía.**

**Vì sao Kruskal-Wallis:** bốn nhóm (không phải hai) nên dùng KW omnibus giữ sai lầm loại I ở mức α; sau đó mới khảo sát sáu cặp bằng Mann-Whitney trong một family hậu định riêng.

| Mùa | n (ngày) | Trung vị (µg/m³) |
|---|---|---|
| Đông | 79 | 60,46 |
| Xuân | 83 | 32,81 |
| Hè | 53 | 31,14 |
| Thu | 84 | 36,30 |

- **H = 61,5344**, df = 3, n = 299, **p thô = 2,76·10⁻¹³**, **p Holm = 8,29·10⁻¹³** → bác bỏ H₀.
- Effect size **ε² = 0,2065** (tỷ lệ phương sai hạng giải thích bởi mùa).
- CI 95% block bootstrap cho chênh lệch trung vị **Đông − Hè**: 29,32 µg/m³, [9,93; 42,75].

### 4.1. Hậu định sáu cặp mùa (exploratory — family Holm riêng)

Sáu cặp này **không** thuộc family xác nhận: chúng được khảo sát sau khi KW bác bỏ H₀, nên mang nhãn *exploratory* và được hiệu chỉnh Holm trong family riêng. Kết luận của Issue #11 chỉ dựa vào KW ở trên; bảng dưới đây để định vị khác biệt nằm ở đâu.

| Cặp | Trung vị A | Trung vị B | U | p thô | p Holm | r_rb | CI 95% (A−B) | Kết luận |
|---|---|---|---|---|---|---|---|---|
| Đông – Xuân | 60,46 | 32,81 | 5191 | 1,49·10⁻¹⁰ | 7,44·10⁻¹⁰ | 0,583 | [7,77; 41,48] | bác bỏ H₀ |
| Đông – Hè | 60,46 | 31,14 | 3519 | 3,72·10⁻¹¹ | 2,23·10⁻¹⁰ | 0,681 | [9,93; 42,75] | bác bỏ H₀ |
| Đông – Thu | 60,46 | 36,30 | 4951 | 5,93·10⁻⁸ | 2,37·10⁻⁷ | 0,492 | [5,06; 38,89] | bác bỏ H₀ |
| Xuân – Hè | 32,81 | 31,14 | 2512 | 0,1639 | 0,3277 | 0,142 | [−4,11; 8,44] | không bác bỏ H₀ |
| Xuân – Thu | 32,81 | 36,30 | 3140 | 0,2688 | 0,3277 | −0,099 | [−9,09; 4,53] | không bác bỏ H₀ |
| Hè – Thu | 31,14 | 36,30 | 1731 | 0,0289 | 0,0866 | −0,222 | [−10,19; 0,85] | không bác bỏ H₀ |

---

## 5. Kiểm định 2 — Ngày làm việc vs ngày cuối tuần

**H₀:** trung vị `pm25` trung bình ngày của ngày làm việc bằng của ngày cuối tuần. **H₁:** hai trung vị khác nhau. **α = 0,05, hai phía.**

**Vì sao Mann-Whitney:** hai nhóm độc lập về mặt thiết kế (một ngày chỉ thuộc một nhóm), phân phối lệch và có outlier; MW so sánh hạng nên không bị chi phối bởi vài ngày ô nhiễm nặng.

- Ngày làm việc: n = 213, trung vị 36,72 µg/m³.
- Ngày cuối tuần: n = 86, trung vị 39,45 µg/m³.
- **U = 8083,0**, **p thô = 0,1120**, **p Holm = 0,1120** → không bác bỏ H₀.
- Chênh lệch trung vị: **−2,74 µg/m³**, CI 95% block bootstrap [−15,01; 4,19].
- Effect size **r_rb = −0,1175** (dương = ngày làm việc cao hơn).

**Ý nghĩa thống kê ≠ ý nghĩa thực tiễn — và power có giới hạn.** Với SD gộp 21,65 µg/m³, n₁ = 213, n₂ = 86, chênh lệch nhỏ nhất phát hiện được ở power 80%, α = 0,05 là **MDE ≈ 7,75 µg/m³** (xấp xỉ chuẩn, tính hậu nghiệm từ SD quan sát). Con số này là ngưỡng phân giải của phép kiểm, không phải kết luận về hiệu ứng:

- Chênh lệch quan sát được là −2,74 µg/m³, **nhỏ hơn MDE**, và CI 95% block bootstrap [−15,01; 4,19] chứa 0; |r_rb| = 0,117. Vì vậy dữ liệu **không đủ độ phân giải** để phân biệt 'không có khác biệt' với 'khác biệt nhỏ hơn MDE' — đây không phải bằng chứng khẳng định hai nhóm bằng nhau.
- Mọi kết luận trong báo cáo đọc theo **CI và effect size**, không theo p đơn độc. Ước lượng điểm nằm trong khoảng sai số thực hành của một trạm đo, nên không được dùng để quy kết nguồn phát thải hay hành vi giao thông.

---

## 6. Kiểm định 3 — Đối chiếu QCVN 05:2023/BTNMT (đúng chu kỳ lấy mẫu)

Hai ngưỡng được kiểm định **tách biệt**, mỗi ngưỡng đi với đúng chu kỳ trung bình của nó. Không có phép so sánh nào giữa một giờ đơn lẻ với ngưỡng ngày hoặc ngưỡng năm.

### 6.1. Ngưỡng trung bình 24 giờ — 50 µg/m³

**H₀:** trung vị của trung bình ngày bằng 50 µg/m³. **H₁:** khác 50. **α = 0,05, hai phía.**

**Vì sao Wilcoxon signed-rank một mẫu:** so sánh một chuỗi với một hằng số, không giả định chuẩn; mỗi ngày là một cặp (giá trị, 50).

- n = 299 ngày; trung vị 37,20 µg/m³.
- **W = 13227,0** (W⁺ = 13227,0, W⁻ = 31623,0), **p thô = 7,88·10⁻¹⁰**, **p Holm = 1,58·10⁻⁹** → bác bỏ H₀.
- Effect size **r = −0,4102** (âm = trung vị nằm dưới ngưỡng).
- CI 95% block bootstrap cho trung vị: [34,13; 40,24].
- Số ngày có trung bình ≥ 50 µg/m³: **84/299 = 28,09%** (CI 95% Wilson: 23,30% – 33,44%).

> **Hai mẫu số, hai câu hỏi.** Trong 5.317 cửa sổ trượt 24 giờ hợp lệ, có 1.655 cửa sổ ≥ 50 (31,13%). Con số này **không** thay thế được tỷ lệ theo ngày (84/299 = 28,09%), vì tử số và mẫu số khác đơn vị. Ghép 1.655 cửa sổ với 9.044 dòng giờ sẽ cho 18,30% — một tỷ lệ không ứng với đơn vị nào và không được dùng trong báo cáo.

> **Không kết luận 'đạt/không đạt QCVN'.** Quy chuẩn quy định cách đánh giá tuân thủ (số ngày vượt được phép trong một năm) mà dự án **không** mã hoá và không có văn bản gốc đối chiếu. Kết quả trên chỉ nói: vị trí trung tâm của phân phối trung bình ngày nằm dưới 50 µg/m³, nhưng gần ba phần mười số ngày vượt ngưỡng — hai sự thật không mâu thuẫn.

### 6.2. Ngưỡng trung bình năm — 25 µg/m³

**H₀:** trung bình của trung bình ngày bằng 25 µg/m³. **H₁:** khác 25. **α = 0,05, hai phía.**

**Vì sao t-test một mẫu:** ngưỡng năm là ngưỡng của **trung bình**, không phải trung vị, nên phép kiểm phải so trung bình. Đây **không** phải ngưỡng áp cho một giờ hay một ngày.

- n = 299 ngày; trung bình 43,38 ± 21,68 µg/m³.
- **t = 14,6563**, df = 298, **p thô = 5,33·10⁻³⁷**, **p Holm = 2,13·10⁻³⁶** → bác bỏ H₀.
- Cohen's d = **0,8476** (đơn vị: độ lệch chuẩn của trung bình ngày, không phải của một quan sát năm).
- CI 95% theo phân phối t (giả định độc lập): [40,91; 45,85].
- CI 95% block bootstrap (tôn trọng tự tương quan): [38,81; 48,29].

> **Giới hạn thiết kế:** dải dữ liệu là 07/2025–07/2026, **không** trùng năm dương lịch. Vì vậy đại lượng trên là trung bình **giai đoạn quan sát**, không phải 'trung bình năm' theo định nghĩa quy chuẩn. Nó là chỉ báo mức nền, không phải một phán quyết tuân thủ.

---

## 7. Tổng hợp family xác nhận — p thô và p Holm cạnh nhau

| Kiểm định | Thống kê | p thô | p Holm | Effect size | Kết luận (Holm) |
|---|---|---|---|---|---|
| Mùa (Kruskal-Wallis, 4 nhóm) | H = 61,534 | 2,76·10⁻¹³ | 8,29·10⁻¹³ | ε² = 0,206 | bác bỏ H₀ |
| Ngày làm việc vs cuối tuần (Mann-Whitney) | U = 8083,000 | 0,1120 | 0,1120 | r_rb = −0,117 | không bác bỏ H₀ |
| Trung bình 24h vs 50 µg/m³ (Wilcoxon) | W = 13227,000 | 7,88·10⁻¹⁰ | 1,58·10⁻⁹ | r (cặp) = −0,410 | bác bỏ H₀ |
| Trung bình giai đoạn vs 25 µg/m³ (t một mẫu) | t = 14,656 | 5,33·10⁻³⁷ | 2,13·10⁻³⁶ | Cohen's d = 0,848 | bác bỏ H₀ |

Holm được chọn thay Bonferroni vì kiểm soát FWER **không cần giả định độc lập** và luôn mạnh hơn hoặc bằng. Family xác nhận gồm đúng **4** kiểm định — mỗi kiểm định trả lời một câu hỏi khác nhau, nên hiệu chỉnh ở đây là biện pháp phòng ngừa, không phải để 'cứu' kết luận. Cột p thô được giữ nguyên để người đọc tự kiểm tra hiệu chỉnh có làm đổi kết luận hay không.

---

## 8. Kiểm tra độ nhạy (exploratory, không thuộc family nào)

### 8.1. Ghép cặp theo tuần cho weekday/weekend

- Số tuần đủ điều kiện (≥ 3 ngày trong tuần và ≥ 2 ngày cuối tuần): **40**.
- Trung vị chênh lệch (weekday − weekend): **−2,70 µg/m³**, CI 95% bootstrap [−8,61; 3,13].
- Tỷ lệ tuần có weekday cao hơn: 37,5%.
- Wilcoxon signed-rank trên 40 chênh lệch tuần: W = 315,0, p = 0,2064, r = −0,2317 → không bác bỏ H₀ ở α = 0,05.

Phép thử này loại bỏ biến thiên giữa các tuần và không dựa vào giả định các ngày độc lập. Nếu kết luận khác với Mann-Whitney ở mục 5, kết luận đúng là **không ổn định** — và đó phải là điều được viết ra.

### 8.2. Kruskal-Wallis trên trung bình tuần theo mùa

- Số tuần dùng được: 48; H = 19,310, df = 3, p = 0,0002, ε² = 0,4109.
- Ở mức tuần, cỡ mẫu nhỏ hơn nhiều nên power thấp; p không có ý nghĩa **không** phủ định kết quả mức ngày, và p có ý nghĩa thì củng cố. Mục đích duy nhất là kiểm tra kết luận mùa có phụ thuộc vào giả định độc lập của từng ngày hay không.

---

## 9. Đọc p-value cho đúng (task 5.7)

p-value là xác suất **của dữ liệu, có điều kiện H₀ đúng** — không phải xác suất H₀ đúng, cũng không phải xác suất kết quả lặp lại. Bốn sai lầm thường gặp và cách đọc đúng:

| Sai lầm | Vì sao sai | Cách đọc đúng trong báo cáo này |
|---|---|---|
| p là xác suất H₀ đúng | p tính dưới giả định H₀; nó không phải xác suất hậu nghiệm | Chỉ nói 'dữ liệu không tương thích với H₀ ở mức α' |
| 1 − p là xác suất H₁ đúng | H₁ thường là hợp, không có phân phối tiên nghiệm | Không gán xác suất cho H₁ |
| p nhỏ = hiệu ứng lớn | p phụ thuộc cỡ mẫu; n ≈ 300 đủ làm hiệu ứng nhỏ có ý nghĩa | Luôn đọc kèm effect size và CI |
| p > α = 'không có hiệu ứng' | Đó là 'không đủ bằng chứng', không phải bằng chứng không | Nêu rõ giới hạn power của từng phép kiểm |

**Power = 1 − β, và độ phân giải của phép kiểm có giới hạn cụ thể.** Với SD gộp 21,65 µg/m³, n₁ = 213, n₂ = 86, chênh lệch nhỏ nhất phát hiện được ở power 80%, α = 0,05 là **MDE ≈ 7,75 µg/m³**. Chênh lệch trung vị quan sát ở mục 5 là 2,74 µg/m³, tức nhỏ hơn MDE. Vì thế kết quả ở mục 5 (không bác bỏ H₀) **không** chứng minh hai nhóm bằng nhau: nó chỉ cho thấy dữ liệu không đủ độ phân giải để tách 'không có khác biệt' khỏi 'khác biệt nhỏ hơn MDE'. Ở mức tuần (mục 8) n nhỏ hơn nên độ phân giải còn thô hơn; một kết quả không ý nghĩa ở đó không được dùng để bác bỏ kết quả mức ngày. Với bài toán cảnh báo, sai lầm loại II (bỏ lọt một đợt ô nhiễm) tốn kém hơn sai lầm loại I, nên ngưỡng vận hành của mô hình ở Issue #13 sẽ được chọn theo Recall chứ không theo Accuracy.

---

## 10. Prior probability và bẫy base-rate (task 5.8)

Trong 299 ngày đủ độ phủ, 84 ngày có trung bình ≥ 50 µg/m³ → **prior ≈ 28,1%**. Đó là xác suất tiên nghiệm mà một bộ phân loại 'ngày ô nhiễm' phải đối mặt: nếu nó luôn dự đoán 'không ô nhiễm', Accuracy đã ≈ 71,9% mà không học được gì.

Vì vậy mọi tỷ lệ trong báo cáo này đều nêu rõ **tử số và mẫu số**, và không có tỷ lệ nào được trình bày như một 'độ chính xác'. Prior cũng **dịch chuyển** giữa Train và Test do điểm cắt rơi vào giữa mùa đông; hệ quả đó thuộc Issue #13 và phải được xử lý bằng Recall và PR-AUC, không bằng Accuracy.

---

## 11. Giới hạn khoa học

1. **Một chu kỳ mùa, một trạm.** Dải 07/2025–07/2026 chỉ chứa một vòng mùa và toàn bộ dữ liệu đến từ một trạm đô thị. Khác biệt theo mùa là mô tả của **giai đoạn này**, không ngoại suy được sang năm khác hay trạm khác.
2. **Tự tương quan chưa được hiệu chỉnh vào p-value.** p của bốn kiểm định xác nhận vẫn dựa trên giả định độc lập; block bootstrap chỉ sửa khoảng tin cậy. Vì vậy p được đọc là **chỉ báo độ tương thích**, không phải bằng chứng chính xác tuyệt đối.
3. **Block bootstrap là xấp xỉ.** Block 7 ngày giữ cấu trúc tuần nhưng không mô phỏng được phụ thuộc dài hạn (lag 14 vẫn còn tương quan). Với so sánh hai nhóm, resample theo từng nhóm bỏ qua tương quan chéo nhóm — kiểm tra ghép cặp theo tuần ở mục 8.1 là biện pháp bù.
4. **Ngưỡng 18/24 giờ** là quy ước phân tích (độ phủ 75%), không phải điều khoản QCVN. Đổi ngưỡng sẽ đổi n; notebook in bảng nhật ký lọc để việc đổi ngưỡng là minh bạch.
5. **QCVN 05:2023/BTNMT quy định ở điều kiện chuẩn (µg/Nm³, 25 °C, 760 mmHg)**, còn trạm OpenAQ báo nồng độ môi trường (µg/m³). So sánh định lượng với ngưỡng vì vậy là xấp xỉ.
6. **Không có kết luận nhân quả.** Khác biệt theo mùa/ngày trong tuần là liên hệ thống kê; nguồn phát thải, khí tượng và điều kiện biên không được phân tách ở đây.

---

## 12. Tái lập

```bash
python -m unittest tests.test_inference -v          # kiểm thử tất định
python -c "from src.inference import run_inference, render_inference_report, DEFAULT_REPORT_PATH; " \
          "DEFAULT_REPORT_PATH.write_text(render_inference_report(run_inference()), encoding='utf-8')"
```

Mọi con số tái lập được với seed 42 và 1.000 lặp bootstrap. Sai khác duy nhất có thể có là phiên bản NumPy/SciPy (đã ghi ở đầu báo cáo).
