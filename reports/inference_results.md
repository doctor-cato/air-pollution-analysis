# Kết quả Suy luận Thống kê — Issue #11 (W9)

> **Tệp này được sinh tự động** bởi `src/inference.py::render_inference_report()`
> từ `notebooks/05_statistical_inference.ipynb`. Không sửa tay: mọi con số
> dưới đây lấy trực tiếp từ `run_inference()` trên dataset đã đóng băng.

> **Phiên bản 2 — sửa theo review `5586524840` của PR #43.** Toàn bộ p-value
> xác nhận được **dựng lại dưới H₀ có xét tới tự tương quan thời gian**;
> p-value cũ (giả định quan sát độc lập) được giữ lại **để đối chiếu**, và
> kết luận đã thay đổi — xem mục 8.

| Trường | Giá trị |
|---|---|
| Issue | #11 |
| Mức ý nghĩa α (chốt trước khi xem dữ liệu) | 0,05 |
| CI bootstrap | 1.000 lặp · block 28 ngày · seed 42 · CI percentile 95% |
| Null bootstrap (p-value) | 5.000 lặp · block 28 ngày · seed 42 |
| HAC (Newey–West) | lag 28 ngày |
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

## 3. Tự tương quan, cỡ mẫu hiệu dụng — giả định nào bị vi phạm

- ACF chuỗi **giờ**: lag 1 = 0,9403 · lag 2 = 0,8371 · lag 3 = 0,7432 · lag 24 = 0,5988 · lag 168 = 0,3449.
- ACF chuỗi **ngày**: lag 1 = 0,7276 · lag 2 = 0,5484 · lag 3 = 0,4239 · lag 7 = 0,3700 · lag 14 = 0,3172.
- AR(1) của chuỗi ngày: ρ = 0,7276 → n_eff ≈ **47,1** so với n = 299 (hệ số lạm phát ×6,34).

**Hệ quả — và cách xử lý sau review.** Mann-Whitney, Kruskal-Wallis, Wilcoxon và t-test đều giả định quan sát **độc lập**. Ở mức ngày, giả định đó **không** được bảo đảm (ρ = 0,73), nên p-value của chúng là **lạc quan**. Ở phiên bản trước, biện pháp duy nhất là block bootstrap cho **khoảng tin cậy** — **không** sửa p-value. Đó là thiếu sót mà review `5586524840` chỉ ra. Phiên bản này sửa đúng chỗ đó:

1. Hạ đơn vị phân tích từ **giờ** xuống **ngày** (vẫn giữ).
2. **Dựng lại phân phối null dưới H₀** cho từng kiểm định (mục 4) — đây mới là phần sửa p-value.
3. Mọi CI dùng **circular moving block bootstrap**, block 28 ngày (1.000 lặp, seed 42).
4. Kiểm soát sai lầm loại I bằng **mô phỏng dưới H₀** (mục 9).
5. Mọi kết luận đọc kèm **effect size + CI**, không đọc p đơn độc.

---

## 4. Khung phương pháp: dựng phân phối null dưới H₀ có xét phụ thuộc thời gian

Bốn kiểm định xác nhận dùng **bốn cách dựng null khác nhau**, mỗi cách được chọn vì hợp với cấu trúc dữ liệu và với H₀ của chính kiểm định đó:

| Kiểm định | H₀ | Cách dựng phân phối null | Tham số phụ thuộc | Giả định chính |
|---|---|---|---|---|
| Mùa | 4 mùa cùng phân phối (quá trình ổn định) | Null **circular moving block bootstrap** trên chuỗi **gộp**; nhãn mùa **giữ theo vị trí lịch**, KHÔNG hoán đổi nhãn | block 28 ngày | Chuỗi gộp ổn định; block bao trọn phụ thuộc còn lại |
| Weekday vs cuối tuần | Hai nhóm cùng phân phối | Null **circular moving block bootstrap** trên chuỗi **gộp**; nhãn nhóm giữ theo vị trí lịch | block 28 ngày | Như trên; xen kẽ tuần được giữ nguyên |
| QCVN 24h (trung vị = 50) | P(trung bình ngày > 50) = 0,5 | **HAC/Newey–West** cho tỷ lệ vượt ngưỡng (tương đương trung vị = 50 với phân phối liên tục) | lag 28 ngày | Sai số tự tương quan tới bậc L; phân phối liên tục |
| QCVN năm (trung bình = 25) | E(trung bình ngày) = 25 | **HAC/Newey–West** (mô hình chỉ có hệ số chặn) | lag 28 ngày | Như trên |

**Ba điều kiện mà phương pháp này tuân thủ (và phương pháp cũ không tuân thủ).**

1. **Null được dựng dưới H₀.** Với kiểm định theo nhóm, null là chuỗi **gộp** (H₀: các nhóm cùng phân phối). Với kiểm định vị trí, H₀ được **áp đặt** bằng cách dựng bản sao `x* = μ + resample(x − θ̂)` — tức mốc của H₀ nằm trong bản sao, không phải trong dữ liệu gốc.
2. **Nhãn nhóm đi theo vị trí lịch, không bị hoán đổi ngẫu nhiên.** Hoán đổi nhãn mùa sẽ phá vỡ cấu trúc mùa vụ (mùa là các đoạn thời gian liên tiếp, không phải nhãn rời rạc).
3. **CI ≠ p-value.** CI là khoảng tin cậy của ước lượng; p-value là xác suất của dữ liệu **có điều kiện H₀ đúng**. Báo cáo luôn in cả hai và không dùng CI để suy ra p (hay ngược lại).

### 4.1. Quy tắc hạ mức kết luận — chốt trước khi xem kết quả

Mỗi kiểm định mang một **trạng thái** được máy tính theo ba quy tắc cố định:

| Quy tắc | Điều kiện | Hệ quả |
|---|---|---|
| R1 — Ổn định | Kết luận (bác bỏ / không bác bỏ) **đổi chiều** khi đổi độ dài block hoặc lag HAC trong lưới độ nhạy | Hạ xuống **THĂM DÒ** |
| R2 — Đồng thuận | Phương pháp đối chứng cho kết luận **khác chiều** phương pháp chính tại tham số đã chốt | Hạ xuống **THĂM DÒ** |
| R3 — Tính được | Không dựng được p hợp lệ | **KHÔNG XÁC NHẬN ĐƯỢC** |

> **Family hiệu chỉnh Holm vẫn gồm đúng 4 kiểm định** như đã chốt trước khi xem dữ liệu.
> Việc một kiểm định bị hạ xuống *thăm dò* **không** làm thay đổi family — thay đổi family
> sau khi nhìn kết quả là p-hacking.

---

## 5. Kiểm định 1 — Khác biệt giữa bốn mùa

**H₀:** Phân phối trung bình ngày giống nhau ở cả bốn mùa (trong một quá trình ổn định trong giai đoạn quan sát).
**H₁:** Có ít nhất một mùa khác.
**α = 0,05, omnibus (đuôi trên của H).**

**Phương pháp chính:** Kruskal-Wallis + null circular moving block bootstrap (chuỗi gộp) (block 28 ngày, 5.000 lặp, seed 42).
**Phương pháp đối chứng:** OLS + HAC (Newey–West) với xu hướng thời gian, Wald đồng thời (lag 28 ngày) — dùng để **tách mùa khỏi xu hướng**.

| Mùa | n (ngày) | Trung vị (µg/m³) |
|---|---|---|
| Đông | 79 | 60,46 |
| Xuân | 83 | 32,81 |
| Hè | 53 | 31,14 |
| Thu | 84 | 36,30 |

- **H = 61,5344**, df = 3, n = 299.
- **p (hiệu chỉnh phụ thuộc thời gian) = 0,0444** → bác bỏ H₀; **p Holm = 0,0888** → không bác bỏ H₀.
- p tham chiếu (giả định độc lập) = 2,76·10⁻¹³.
- Effect size **ε² = 0,2065** (tỷ lệ phương sai hạng giải thích bởi mùa).
- Đối chứng (HAC, có xu hướng): F = 17,265 (3, 294), p = 2,36·10⁻¹⁰; với xu hướng bậc hai: p = 3,39·10⁻¹²; xu hướng tuyến tính ước lượng −2,29 µg/m³ mỗi tháng.
- CI 95% block bootstrap cho chênh lệch trung vị **Đông − Hè**: 29,32 µg/m³, [9,95; 38,65].

**Độ nhạy theo độ dài block (phương pháp chính).**

| Block (ngày) | p | Kết luận |
|---|---|---|
| block = 7 | 0,0004 | bác bỏ H₀ |
| block = 14 | 0,0064 | bác bỏ H₀ |
| block = 21 | 0,0186 | bác bỏ H₀ |
| block = 28 | 0,0444 | bác bỏ H₀ |
| block = 42 | 0,0788 | không bác bỏ H₀ |

**Độ nhạy theo lag HAC (phương pháp đối chứng).**

| Lag (ngày) | p | Kết luận |
|---|---|---|
| lag = 7 | 3,02·10⁻⁷ | bác bỏ H₀ |
| lag = 14 | 5,26·10⁻⁸ | bác bỏ H₀ |
| lag = 21 | 4,52·10⁻⁹ | bác bỏ H₀ |
| lag = 28 | 2,36·10⁻¹⁰ | bác bỏ H₀ |
| lag = 42 | 3,71·10⁻¹⁰ | bác bỏ H₀ |

> **Trạng thái kết luận: THĂM DÒ (EXPLORATORY).** Kết luận không ổn định theo độ dài block / lag HAC → hạ xuống thăm dò. p-value của kiểm định mùa nhạy với lựa chọn cách hiệu chỉnh phụ thuộc (từ 0,0004 ở block 7 ngày tới 0,0788 ở block 42 ngày) — nghĩa là bằng chứng thống kê cho H₀ 'các mùa bằng nhau' **không vững**; khác biệt mùa vẫn được báo cáo như **mô tả** của giai đoạn 07/2025–07/2026 (mục 10), không phải quy luật nhiều năm.

### 5.1. Hậu định sáu cặp mùa (exploratory — family Holm riêng)

Sáu cặp này **không** thuộc family xác nhận: chúng được khảo sát sau khi kiểm định omnibus bác bỏ H₀, nên mang nhãn *exploratory* và được hiệu chỉnh Holm trong family riêng. p-value của mỗi cặp cũng được dựng lại dưới H₀ có xét phụ thuộc (null block bootstrap trên chuỗi gộp, nhãn của hai mùa so sánh giữ theo vị trí lịch).

| Cặp | Trung vị A | Trung vị B | U | p (hiệu chỉnh) | p Holm | p tham chiếu | r_rb | CI 95% (A−B) |
|---|---|---|---|---|---|---|---|---|
| Đông – Xuân | 60,46 | 32,81 | 5191 | 0,0144 | 0,0720 | 1,49·10⁻¹⁰ | 0,583 | [8,82; 36,68] |
| Đông – Hè | 60,46 | 31,14 | 3519 | 0,0120 | 0,0720 | 3,72·10⁻¹¹ | 0,681 | [9,95; 38,65] |
| Đông – Thu | 60,46 | 36,30 | 4951 | 0,0624 | 0,2496 | 5,93·10⁻⁸ | 0,492 | [5,31; 33,82] |
| Xuân – Hè | 32,81 | 31,14 | 2512 | 0,6543 | 1,0000 | 0,1639 | 0,142 | [−4,31; 7,81] |
| Xuân – Thu | 32,81 | 36,30 | 3140 | 0,6887 | 1,0000 | 0,2688 | −0,099 | [−8,65; 3,55] |
| Hè – Thu | 31,14 | 36,30 | 1731 | 0,4471 | 1,0000 | 0,0289 | −0,222 | [−9,59; 0,50] |

---

## 6. Kiểm định 2 — Ngày làm việc vs ngày cuối tuần

**H₀:** Phân phối PM2.5 trung bình ngày của ngày làm việc và cuối tuần giống nhau.
**H₁:** Hai phân phối khác nhau.
**α = 0,05, hai phía.**

**Phương pháp chính:** Mann-Whitney U + null circular moving block bootstrap (chuỗi gộp) (block 28 ngày).
**Phương pháp đối chứng:** OLS + HAC (Newey–West), hệ số dummy cuối tuần (lag 28 ngày).

- Ngày làm việc: n = 213, trung vị 36,72 µg/m³.
- Ngày cuối tuần: n = 86, trung vị 39,45 µg/m³.
- **U = 8083,0**, **p (hiệu chỉnh phụ thuộc) = 0,0780** → không bác bỏ H₀; **p Holm = 0,0888** → không bác bỏ H₀.
- p tham chiếu (giả định độc lập) = 0,1120.
- Chênh lệch trung vị: **−2,74 µg/m³**, CI 95% block bootstrap [−20,12; 6,21].
- Effect size **r_rb = −0,1175** (dương = ngày làm việc cao hơn).
- Đối chứng (HAC): t = 1,611, p = 0,1082.

**Độ nhạy theo độ dài block.**

| Block (ngày) | p | Kết luận |
|---|---|---|
| block = 7 | 0,0788 | không bác bỏ H₀ |
| block = 14 | 0,0840 | không bác bỏ H₀ |
| block = 21 | 0,0828 | không bác bỏ H₀ |
| block = 28 | 0,0780 | không bác bỏ H₀ |
| block = 42 | 0,0792 | không bác bỏ H₀ |

> **Trạng thái kết luận: XÁC NHẬN.** Phương pháp chính và phương pháp đối chứng cùng chiều.

**Ý nghĩa thống kê ≠ ý nghĩa thực tiễn — và power có giới hạn.** Với SD gộp 21,65 µg/m³, n₁ = 213, n₂ = 86, chênh lệch nhỏ nhất phát hiện được ở power 80%, α = 0,05 là **MDE ≈ 7,75 µg/m³** (xấp xỉ chuẩn, tính hậu nghiệm từ SD quan sát — lưu ý: công thức này **giả định độc lập**, nên với chuỗi tự tương quan nó **đánh giá thấp** ngưỡng phân giải thực tế).

- Chênh lệch quan sát được là −2,74 µg/m³, nhỏ hơn MDE, và CI 95% block bootstrap [−20,12; 6,21] chứa 0; |r_rb| = 0,117. Vì vậy dữ liệu **không đủ độ phân giải** để phân biệt 'không có khác biệt' với 'khác biệt nhỏ hơn MDE' — đây không phải bằng chứng khẳng định hai nhóm bằng nhau.
- Ước lượng điểm nằm trong khoảng sai số thực hành của một trạm đo, nên không được dùng để quy kết nguồn phát thải hay hành vi giao thông.

---

## 7. Kiểm định 3 — Đối chiếu QCVN 05:2023/BTNMT (đúng chu kỳ lấy mẫu)

Hai ngưỡng được kiểm định **tách biệt**, mỗi ngưỡng đi với đúng chu kỳ trung bình của nó. Không có phép so sánh nào giữa một giờ đơn lẻ với ngưỡng ngày hoặc ngưỡng năm.

### 7.1. Ngưỡng trung bình 24 giờ — 50 µg/m³

**H₀:** Trung vị của trung bình ngày bằng 50 µg/m³.
**H₁:** Trung vị khác 50 µg/m³.
**α = 0,05, hai phía.**

**Phương pháp chính:** H₀ 'trung vị = μ' tương đương 'P(trung bình ngày > μ) = 0,5' với phân phối liên tục; thống kê là tỷ lệ ngày vượt ngưỡng, SE là sandwich HAC.
**Phương pháp đối chứng:** Bootstrap áp đặt H₀ + p-value đảo CI (cùng phân phối bootstrap).

- n = 299 ngày; trung vị 37,20 µg/m³; trung bình 43,38 ± 21,68 µg/m³.
- **t = −2,6558** (tỷ lệ ngày vượt ngưỡng, SE HAC), **p (hiệu chỉnh phụ thuộc) = 0,0083** → bác bỏ H₀; **p Holm = 0,0250** → bác bỏ H₀.
- p tham chiếu (Wilcoxon giả định độc lập) = 7,88·10⁻¹⁰.
- Đối chứng: bootstrap áp đặt H₀ p = 0,0064; p suy ra từ phân phối bootstrap của ước lượng (đảo CI) = 0,0072; Wilcoxon có HAC p = 0,0493.
- Effect size **r = −0,4102** (âm = trung vị nằm dưới ngưỡng).
- CI 95% block bootstrap cho trung vị: [32,81; 45,36].
- Số ngày có trung bình ≥ 50 µg/m³: **84/299 = 28,09%** (CI 95% Wilson: 23,30% – 33,44%).

**Độ nhạy theo lag HAC.**

| Lag (ngày) | p | Kết luận |
|---|---|---|
| lag = 7 | 4,16·10⁻⁵ | bác bỏ H₀ |
| lag = 14 | 0,0010 | bác bỏ H₀ |
| lag = 21 | 0,0040 | bác bỏ H₀ |
| lag = 28 | 0,0083 | bác bỏ H₀ |
| lag = 42 | 0,0190 | bác bỏ H₀ |

> **Trạng thái kết luận: XÁC NHẬN.** Phương pháp chính và phương pháp đối chứng cùng chiều. Lưu ý: bản **signed-rank** có HAC cho p lớn hơn bản tỷ lệ vượt ngưỡng, vì dãy chênh lệch lớn (ngày rất vượt ngưỡng) rất bền nên SE HAC của nó bị thổi phồng — đây là hạn chế **sức mạnh** của phép kiểm, không phải lỗi hiệu chỉnh.

> **Hai mẫu số, hai câu hỏi.** Trong 5.317 cửa sổ trượt 24 giờ hợp lệ, có 1.655 cửa sổ ≥ 50 (31,13%). Con số này **không** thay thế được tỷ lệ theo ngày (84/299 = 28,09%), vì tử số và mẫu số khác đơn vị. Ghép 1.655 cửa sổ với 9.044 dòng giờ sẽ cho 18,30% — một tỷ lệ không ứng với đơn vị nào và không được dùng trong báo cáo.

> **Không kết luận 'đạt/không đạt QCVN'.** Quy chuẩn quy định cách đánh giá tuân thủ (số ngày vượt được phép trong một năm) mà dự án **không** mã hoá và không có văn bản gốc đối chiếu. Kết quả trên chỉ nói: vị trí trung tâm của phân phối trung bình ngày nằm dưới 50 µg/m³, nhưng gần ba phần mười số ngày vượt ngưỡng — hai sự thật không mâu thuẫn.

### 7.2. Ngưỡng trung bình năm — 25 µg/m³

**H₀:** Trung bình của trung bình ngày bằng 25 µg/m³.
**H₁:** Trung bình khác 25 µg/m³.
**α = 0,05, hai phía.**

**Phương pháp chính:** t-test một mẫu với sai số chuẩn HAC: mô hình chỉ có hệ số chặn, SE là ước lượng sandwich của phương sai dài hạn.
**Phương pháp đối chứng:** Bootstrap áp đặt H₀ + p-value đảo CI (cùng phân phối bootstrap).

- n = 299 ngày; trung bình 43,38 ± 21,68 µg/m³.
- **t = 4,3535** (HAC), **p (hiệu chỉnh phụ thuộc) = 1,84·10⁻⁵** → bác bỏ H₀; **p Holm = 7,38·10⁻⁵** → bác bỏ H₀.
- p tham chiếu (t-test giả định độc lập) = 5,33·10⁻³⁷.
- Đối chứng: bootstrap áp đặt H₀ p = 0,0004; p suy ra từ phân phối bootstrap của ước lượng = 0,0006.
- Cohen's d = **0,8476** (đơn vị: độ lệch chuẩn của trung bình ngày, không phải của một quan sát năm).
- CI 95% theo HAC (tôn trọng tự tương quan): [35,07; 51,69]; CI 95% block bootstrap: [35,75; 52,32]; CI 95% theo t (giả định độc lập — tham chiếu): [40,91; 45,85].

**Độ nhạy theo lag HAC.**

| Lag (ngày) | p | Kết luận |
|---|---|---|
| lag = 7 | 3,75·10⁻¹¹ | bác bỏ H₀ |
| lag = 14 | 8,32·10⁻⁸ | bác bỏ H₀ |
| lag = 21 | 2,64·10⁻⁶ | bác bỏ H₀ |
| lag = 28 | 1,84·10⁻⁵ | bác bỏ H₀ |
| lag = 42 | 0,0001 | bác bỏ H₀ |

> **Trạng thái kết luận: XÁC NHẬN.** Phương pháp chính và phương pháp đối chứng cùng chiều.

> **Giới hạn thiết kế:** dải dữ liệu là 07/2025–07/2026, **không** trùng năm dương lịch. Vì vậy đại lượng trên là trung bình **giai đoạn quan sát**, không phải 'trung bình năm' theo định nghĩa quy chuẩn. Nó là chỉ báo mức nền, không phải một phán quyết tuân thủ.

---

## 8. Family xác nhận — p thô, p Holm và trạng thái kết luận

| Kiểm định | Thống kê | p (hiệu chỉnh phụ thuộc) | p Holm | Effect size | Trạng thái |
|---|---|---|---|---|---|
| Mùa (4 nhóm, có xét phụ thuộc thời gian) | H = 61,534 | 0,0444 | 0,0888 | ε² = 0,206 | THĂM DÒ (EXPLORATORY) |
| Ngày làm việc vs cuối tuần (có xét phụ thuộc thời gian) | U = 8083,000 | 0,0780 | 0,0888 | r_rb = −0,117 | XÁC NHẬN |
| Trung bình 24h vs 50 µg/m³ (có xét phụ thuộc thời gian) | t (share, HAC) = −2,656 | 0,0083 | 0,0250 | r (cặp) = −0,410 | XÁC NHẬN |
| Trung bình giai đoạn vs 25 µg/m³ (có xét phụ thuộc thời gian) | t (HAC) = 4,354 | 1,84·10⁻⁵ | 7,38·10⁻⁵ | Cohen's d = 0,848 | XÁC NHẬN |

**Kết luận sau hiệu chỉnh Holm: 2/4 kiểm định bác bỏ H₀** (α = 0,05), trong đó 1 kiểm định bị hạ xuống *thăm dò* theo quy tắc R1–R3 của mục 4.1.

**Đối chiếu với phương pháp cũ (giả định quan sát độc lập).**

| Kiểm định | p tham chiếu | p Holm (tham chiếu) | Kết luận (tham chiếu) |
|---|---|---|---|
| Mùa (4 nhóm, có xét phụ thuộc thời gian) | 2,76·10⁻¹³ | 8,29·10⁻¹³ | bác bỏ H₀ |
| Ngày làm việc vs cuối tuần (có xét phụ thuộc thời gian) | 0,1120 | 0,1120 | không bác bỏ H₀ |
| Trung bình 24h vs 50 µg/m³ (có xét phụ thuộc thời gian) | 7,88·10⁻¹⁰ | 1,58·10⁻⁹ | bác bỏ H₀ |
| Trung bình giai đoạn vs 25 µg/m³ (có xét phụ thuộc thời gian) | 5,33·10⁻³⁷ | 2,13·10⁻³⁶ | bác bỏ H₀ |

Phương pháp cũ cho **3/4 bác bỏ H₀**; phương pháp có xét phụ thuộc thời gian cho **2/4**. Đây là **thay đổi kết luận do phương pháp**, không phải do dữ liệu thay đổi: p-value của SciPy trên chuỗi tự tương quan coi 299 ngày như 299 quan sát độc lập, trong khi thực tế n_eff ≈ 47,1 (lạm phát ×6,34) — p-value cũ vì vậy **lạc quan**. Mục 9 định lượng mức lạc quan đó bằng mô phỏng.

---

## 9. Kiểm soát sai lầm loại I bằng mô phỏng dưới H₀

Mô phỏng trên chuỗi **AR(1)** có cùng mức tự tương quan như dữ liệu thật (ρ = 0,7276, n = 299 ngày, 100 lần lặp, seed 42). Cột **size** là tỷ lệ bác bỏ H₀ khi H₀ **đúng**; cột **power** là tỷ lệ bác bỏ khi có hiệu ứng +1 đơn vị.

| Phép kiểm | size (giả định độc lập) | size (phương pháp chính) | size (đối chứng) | power (độc lập) | power (chính) | power (đối chứng) |
|---|---|---|---|---|---|---|
| season | 75,0% | 8,0% | 31,0% | 93,0% | 34,0% | 58,0% |
| weekday | 2,0% | 2,0% | 5,0% | 100,0% | 100,0% | 100,0% |
| median | 36,0% | 5,0% | 3,0% | 100,0% | 100,0% | 100,0% |
| mean | 39,0% | 8,0% | 8,0% | 100,0% | 100,0% | 100,0% |

**Đọc kết quả.** Ở α = 0%, một phép kiểm hợp lệ phải bác bỏ khoảng 5% số lần dưới H₀. Các phép kiểm SciPy dùng trong phiên bản cũ bác bỏ **hàng chục tới gần 80%** số lần dưới H₀ — bằng chứng định lượng rằng chúng **không** kiểm soát được sai lầm loại I trên dữ liệu này. Phương pháp có xét phụ thuộc thời gian đưa tỷ lệ này về gần α (vẫn hơi lạc quan ở mức ~2–3 lần α do quá trình gần phân kỳ đơn vị và vì bản số hữu hạn).

> **Giới hạn của bằng chứng này:** mô phỏng dùng chuỗi AR(1) — một xấp xỉ của phụ thuộc quan sát được. Nó **không** thay thế lý thuyết: mọi phương pháp hiệu chỉnh đều là xấp xỉ, và cỡ mẫu hiệu dụng nhỏ (n_eff ≈ 47) giới hạn mọi phép kiểm.

## 10. Khả năng khái quát hóa kết quả theo mùa

Câu hỏi mà bốn kiểm định trên **không** trả lời được: khác biệt mùa quan sát được ở giai đoạn 07/2025–07/2026 có phải là quy luật mùa vụ ổn định nhiều năm không? Bốn dữ kiện dưới đây nói: **không thể khẳng định**.

1. **Chỉ một chu kỳ mùa.** Dải quan sát dài 378 ngày lịch và chứa **một** vòng mùa. Mỗi mùa là **một đoạn thời gian liên tiếp**, nên 'mùa' và 'thời gian' là hai cách gọi khác nhau của cùng một biến — không thể tách chúng ngoài một chu kỳ.
2. **Xu hướng thời gian cùng cỡ với khác biệt mùa.** Hồi quy HAC ước lượng xu hướng tuyến tính −2,29 µg/m³ mỗi tháng, tức 27,4 µg/m³ trên cả năm — bằng 94% độ lớn khác biệt lớn nhất giữa các mùa (29,3 µg/m³). Xu hướng tuyến tính **không giải thích** khác biệt mùa, nhưng nó cho thấy hai cấu phần cạnh tranh; một mô hình xu hướng phi tuyến khác sẽ cho kết luận khác.
3. **Mẫu không cân bằng và thiếu hụt không ngẫu nhiên.** Số ngày giữ lại khác nhau theo mùa, và phần thiếu rơi không đều (mùa Đông mất nhiều ngày nhất). Điều này làm giảm cỡ mẫu hiệu dụng của mùa Đông — mùa có hiệu ứng mạnh nhất cũng là mùa bị thiếu dữ liệu nhiều nhất.
4. **Số mùa có mặt ở hai mùa-vụ khác nhau:** **không mùa nào** xuất hiện ở hai mùa-vụ khác nhau — panel kết thúc ở 2026-05-29 nên mùa Hè 2026 chưa kịp vào panel. So sánh cùng một mùa giữa hai năm vì vậy **không khả thi** với bộ dữ liệu này.

| Mùa | Ngày lịch trong dải | Ngày giữ lại | Ngày bị loại | Tỷ lệ giữ lại |
|---|---|---|---|---|
| Đông | 90 | 79 | 11 | 87,8% |
| Xuân | 90 | 83 | 7 | 92,2% |
| Hè | 59 | 53 | 6 | 89,8% |
| Thu | 91 | 84 | 7 | 92,3% |

| Mùa | Mùa-vụ (năm bắt đầu của mùa) | n ngày | Trung vị |
|---|---|---|---|
| Đông | 2026 | 79 | 60,46 |
| Hè | 2025 | 53 | 31,14 |
| Thu | 2025 | 84 | 36,30 |
| Xuân | 2026 | 83 | 32,81 |

> **Kết luận về khả năng khái quát hóa.** Kết quả mùa trong báo cáo này là **mô tả của một giai đoạn quan sát duy nhất**, ở một trạm duy nhất, với điều kiện khí tượng của chính năm đó. Không có bằng chứng nào trong bộ dữ liệu cho phép nói rằng đây là quy luật mùa vụ ổn định nhiều năm. Vì vậy kiểm định mùa ở mục 5 bị hạ xuống **THĂM DÒ** và kết luận mùa được trình bày như **hiệu ứng mô tả**, không phải xác nhận.

---

## 11. Kiểm tra độ nhạy (exploratory, không thuộc family nào)

### 11.1. Ghép cặp theo tuần cho weekday/weekend

- Số tuần đủ điều kiện (≥ 3 ngày trong tuần và ≥ 2 ngày cuối tuần): **40**.
- Trung vị chênh lệch (weekday − weekend): **−2,70 µg/m³**, CI 95% bootstrap [−10,41; 2,69].
- Tỷ lệ tuần có weekday cao hơn: 37,5%.
- Signed-rank có HAC (Newey–West, lag 4 tuần) trên 40 chênh lệch tuần: t = −1,433, p = 0,1598 → không bác bỏ H₀ ở α = 0,05 (tham chiếu, giả định độc lập: p = 0,2064).

Phép thử này loại bỏ biến thiên giữa các tuần và không dựa vào giả định các ngày độc lập. Nếu kết luận khác với kiểm định ở mục 6, kết luận đúng là **không ổn định** — và đó phải là điều được viết ra.

### 11.2. Kruskal-Wallis trên trung bình tuần theo mùa

- Số tuần dùng được: 48; H = 19,310, df = 3, p (hiệu chỉnh phụ thuộc) = 0,0194, p tham chiếu = 0,0002, ε² = 0,4109.
- Ở mức tuần, cỡ mẫu nhỏ hơn nhiều nên power thấp; p không có ý nghĩa **không** phủ định kết quả mức ngày, và p có ý nghĩa thì củng cố. Mục đích duy nhất là kiểm tra kết luận mùa có phụ thuộc vào giả định độc lập của từng ngày hay không.

---

## 12. Đọc p-value cho đúng (task 5.7)

p-value là xác suất **của dữ liệu, có điều kiện H₀ đúng** — không phải xác suất H₀ đúng, cũng không phải xác suất kết quả lặp lại. Bốn sai lầm thường gặp và cách đọc đúng:

| Sai lầm | Vì sao sai | Cách đọc đúng trong báo cáo này |
|---|---|---|
| p là xác suất H₀ đúng | p tính dưới giả định H₀; nó không phải xác suất hậu nghiệm | Chỉ nói 'dữ liệu không tương thích với H₀ ở mức α' |
| 1 − p là xác suất H₁ đúng | H₁ thường là hợp, không có phân phối tiên nghiệm | Không gán xác suất cho H₁ |
| p nhỏ = hiệu ứng lớn | p phụ thuộc cỡ mẫu; n_eff ≈ 47 mới là cỡ mẫu có ý nghĩa ở đây | Luôn đọc kèm effect size và CI |
| p > α = 'không có hiệu ứng' | Đó là 'không đủ bằng chứng', không phải bằng chứng không | Nêu rõ giới hạn power của từng phép kiểm |

**Power = 1 − β, và độ phân giải của phép kiểm có giới hạn cụ thể.** Với SD gộp 21,65 µg/m³, n₁ = 213, n₂ = 86, chênh lệch nhỏ nhất phát hiện được ở power 80%, α = 0,05 là **MDE ≈ 7,75 µg/m³** (xấp xỉ chuẩn, giả định độc lập). Chênh lệch trung vị quan sát ở mục 6 là 2,74 µg/m³, tức nhỏ hơn MDE. Vì thế kết quả ở mục 6 **không** chứng minh hai nhóm bằng nhau: nó chỉ cho thấy dữ liệu không đủ độ phân giải để tách 'không có khác biệt' khỏi 'khác biệt nhỏ hơn MDE'. Với bài toán cảnh báo, sai lầm loại II (bỏ lọt một đợt ô nhiễm) tốn kém hơn sai lầm loại I, nên ngưỡng vận hành của mô hình ở Issue #13 sẽ được chọn theo Recall chứ không theo Accuracy.

---

## 13. Prior probability và bẫy base-rate (task 5.8)

Trong 299 ngày đủ độ phủ, 84 ngày có trung bình ≥ 50 µg/m³ → **prior ≈ 28,1%**. Đó là xác suất tiên nghiệm mà một bộ phân loại 'ngày ô nhiễm' phải đối mặt: nếu nó luôn dự đoán 'không ô nhiễm', Accuracy đã ≈ 71,9% mà không học được gì.

Vì vậy mọi tỷ lệ trong báo cáo này đều nêu rõ **tử số và mẫu số**, và không có tỷ lệ nào được trình bày như một 'độ chính xác'. Prior cũng **dịch chuyển** giữa Train và Test do điểm cắt rơi vào giữa mùa đông; hệ quả đó thuộc Issue #13 và phải được xử lý bằng Recall và PR-AUC, không bằng Accuracy.

---

## 14. Giới hạn khoa học

1. **Một chu kỳ mùa, một trạm.** Dải 07/2025–07/2026 chỉ chứa một vòng mùa và toàn bộ dữ liệu đến từ một trạm đô thị. Khác biệt theo mùa là mô tả của **giai đoạn này**, không ngoại suy được sang năm khác hay trạm khác (mục 10).
2. **Hiệu chỉnh phụ thuộc thời gian là xấp xỉ, không phải định nghĩa.** Mọi phương pháp ở mục 4 đều là phương pháp bậc cao với giả định ổn định; mô phỏng (mục 9) cho thấy tỷ lệ bác bỏ dưới H₀ còn cao hơn α khoảng 2–3 lần. p-value vì vậy là **chỉ báo độ tương thích**, không phải xác suất chính xác tuyệt đối.
3. **Kết luận mùa đã bị hạ xuống thăm dò** vì p-value của kiểm định omnibus mùa không ổn định theo độ dài block (mục 5). Đây là hạn chế thật, không phải khiêm tốn hình thức.
4. **Block bootstrap là xấp xỉ.** Block 28 ngày giữ cấu trúc theo tuần nhưng không mô phỏng được phụ thuộc dài hạn hơn nữa; với so sánh hai nhóm, resample trên chuỗi gộp bỏ qua tương quan chéo nhóm — kiểm tra ghép cặp theo tuần ở mục 11.1 là biện pháp bù.
5. **Ngưỡng 18/24 giờ** là quy ước phân tích (độ phủ 75%), không phải điều khoản QCVN. Đổi ngưỡng sẽ đổi n; bảng nhật ký lọc ở mục 1 làm việc đổi ngưỡng trở nên minh bạch.
6. **QCVN 05:2023/BTNMT quy định ở điều kiện chuẩn (µg/Nm³, 25 °C, 760 mmHg)**, còn trạm OpenAQ báo nồng độ môi trường (µg/m³). So sánh định lượng với ngưỡng vì vậy là xấp xỉ.
7. **Không có kết luận nhân quả.** Khác biệt theo mùa/ngày trong tuần là liên hệ thống kê; nguồn phát thải, khí tượng và điều kiện biên không được phân tách ở đây.
8. **Kết quả mô phỏng không thay thế lý thuyết và không được tái lập ngoài dữ liệu này** — mô phỏng dùng mô hình AR(1), không phải dữ liệu thật.

---

## 15. Tái lập

```bash
python -m unittest tests.test_inference -v          # kiểm thử tất định
python -c "from src.inference import run_inference, render_inference_report, DEFAULT_REPORT_PATH; " \
          "DEFAULT_REPORT_PATH.write_text(render_inference_report(run_inference()), encoding='utf-8')"
```

Mọi con số tái lập được với seed 42, 1.000 lặp CI bootstrap và 5.000 lặp null bootstrap. Sai khác duy nhất có thể có là phiên bản NumPy/SciPy (đã ghi ở đầu báo cáo).
