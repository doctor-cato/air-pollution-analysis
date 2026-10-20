# Kết quả Suy luận Thống kê — Issue #11 (W9)

> **Tệp này được sinh tự động** bởi `src/inference.py::render_inference_report()`
> từ `notebooks/05_statistical_inference.ipynb`. Không sửa tay: mọi con số
> dưới đây lấy trực tiếp từ `run_inference()` trên dataset đã đóng băng.

> **Phiên bản 3 — sửa theo review `5588255357` của PR #43.** Mọi resample giờ
> chạy trên **lịch ngày đầy đủ** (block = ngày LỊCH liên tiếp, mặt nạ ngày
> thiếu đi theo bản sao), và phần p-value được kiểm chứng bằng **Monte Carlo
> đa kịch bản** (mục 9). Kết luận: **2/4** kiểm định bác bỏ H₀ sau Holm; kiểm
> định mùa ở trạng thái **THĂM DÒ**.

| Trường | Giá trị |
|---|---|
| Issue | #11 |
| Mức ý nghĩa α (chốt trước khi xem dữ liệu) | 0,05 |
| CI bootstrap | 1.000 lặp · block 28 NGÀY LỊCH · seed 42 · CI percentile 95% |
| Null bootstrap (p-value) | 5.000 lặp · block 28 NGÀY LỊCH · seed 42 |
| HAC (Newey–West) | lag 28 ngày |
| Lịch ngày (đơn vị resample) | 378 ngày lịch · 299 ngày có trung bình · 79 ngày thiếu |
| Đơn vị phân tích | Trung bình ngày (≥ 18/24 giờ có `pm25`) |
| Nguồn dữ liệu | `data/processed/air_pollution_final.parquet (đường dẫn tương đối tới repo)` |
| SHA-256 dataset | `866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd` |
| NumPy / SciPy | 2.5.3 / 1.18.1 |

---

## 1. Đơn vị phân tích và nhật ký lọc mẫu

- Chuỗi giờ: **9.044** dòng, trong đó **7.495** giờ có `pm25` và **1.549** giờ thiếu.
- Dải quan sát (giờ có `pm25`): **2025-07-03 → 2026-07-15** (378 ngày lịch, 1 trạm); ngày đủ độ phủ đầu–cuối: 2025-07-04 → 2026-05-29.
- Ngày có ít nhất một giờ đo: **351**; ngày đủ 24/24 giờ: **223**; ngày **không có** giờ đo nào: **27**.
- Ngày đạt tiêu chí ≥ 18/24 giờ: **299** — đây là cỡ mẫu của mọi kiểm định (n = 299).
- Ngày có quan sát nhưng thiếu độ phủ (bị loại khỏi panel): **52**.
- Ngày làm việc / cuối tuần trong panel: **213** / **86**.

**Vì sao không dùng từng giờ làm đơn vị phân tích.** ACF bậc 1 của chuỗi giờ là 0,9403 — 9.044 giờ không phải bấy nhiêu quan sát độc lập. Tổng hợp về ngày là bước giảm tự tương quan **bắt buộc**, không phải tuỳ chọn trình bày. Tiêu chí ≥ 18/24 giờ là **lựa chọn phân tích của dự án** (độ phủ 75%), không phải điều khoản của QCVN 05:2023/BTNMT.

**Vì sao không dùng Train/Test split.** Các phép kiểm dưới đây không fit mô hình, không chọn siêu tham số và không đánh giá năng lực dự báo, nên không có đường rò rỉ Test → Train. Chạy trên toàn bộ giai đoạn quan sát để tận dụng cỡ mẫu và để kiểm định trung bình năm có trọn chu kỳ. Điểm cắt `2026-01-15 00:00+07:00` của Issue #7 **không bị thay đổi**.

---

## 2. Lịch ngày và mặt nạ thiếu — đơn vị của mọi resample

Đây là phần **quan trọng nhất** của bản sửa: mọi bootstrap trước đây resample **mảng trung bình ngày đã lọc**, nên hai phần tử liền nhau của mảng **không** phải hai ngày lịch liên tiếp. Với 79 ngày thiếu trong 378 ngày lịch, "block 28 phần tử" thực tế trải tới **52 ngày lịch** — sai lệch đúng cái mà tham số phụ thuộc cần giữ.

| Đại lượng lịch | Giá trị |
|---|---|
| Số ngày lịch trong dải quan sát | 378 |
| Ngày có trung bình ngày (dùng được) | 299 |
| Ngày thiếu (không đủ độ phủ hoặc không có quan sát) | 79 (20,9%) |
| Số cụm ngày thiếu liên tiếp | 17 |
| Cụm thiếu dài nhất | 47 ngày |
| Ngày lịch đầu – cuối | 2025-07-02 → 2026-07-14 |

**Ba điều kiện của thuật toán mới.**

1. **Block = ngày LỊCH liên tiếp.** `calendar_block_indices()` chọn các khối gồm `block_length_days` ngày lịch liên tiếp (cuộn vòng ở cuối lịch), nên tham số luôn mang nghĩa **ngày**, không phải **phần tử mảng**.
2. **Mặt nạ thiếu đi theo bản sao.** Một khối chứa 3 ngày thiếu thì bản sao cũng thiếu đúng 3 ngày đó. **Không** nội suy, **không** tạo quan sát giả, **không** nối hai khoảng thời gian bị ngắt.
3. **Nhãn nhóm ở vị trí j của bản sao là nhãn lịch của vị trí j**; *giá trị* tại vị trí j được lấy ngẫu nhiên từ chuỗi gộp. Nhờ vậy null H₀ (các nhóm cùng phân phối) được dựng **đúng**, còn phụ thuộc trong block vẫn được giữ vì block là ngày lịch liên tiếp. Nếu nhãn đi theo **ngày nguồn** thì cấu trúc mùa vụ được giữ lại và null biến thành chứa hiệu ứng — p-value bị thổi phồng.

**Hệ quả phải nói rõ:** vì mặt nạ đi theo bản sao, số ngày quan sát của mỗi bản sao **không cố định** (TB 299,7 ± 29,5 ngày, khoảng 165–365 so với 299 ngày gốc). Các thống kê kiểm dùng **NaN-aware** nên tự tính đúng số quan sát của từng bản sao; phân phối null vì vậy **đã bao hàm** cả biến động cỡ mẫu này. Đổi lại, khoảng tin cậy bootstrap rộng hơn một chút so với CI trên mẫu cố định.

---

## 3. Chẩn đoán phân phối (không mặc định chuẩn / không chuẩn)

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

Cả hai kiểm định chuẩn tắc đều bác bỏ tính chuẩn, nhưng **đó không phải lý do duy nhất** để chọn phép kiểm phi tham số. Với n cỡ này, Shapiro-Wilk có power đủ để phát hiện lệch nhỏ không có ý nghĩa thực tiễn; vì vậy quyết định dựa thêm vào (a) skewness và kurtosis quan sát được, (b) bản chất thang đo — nồng độ bị chặn dưới 0, phân phối lệch phải, có outlier đợt ô nhiễm, và (c) các phép kiểm so sánh **trung vị/hạng**, đúng với câu hỏi về mức nền phơi nhiễm hơn là về trung bình số học. Q-Q plot: `figures/FIG-08.png`.

---

## 4. Tự tương quan, cỡ mẫu hiệu dụng và khung phương pháp

### 4.1. Tự tương quan

- ACF chuỗi **giờ**: lag 1 = 0,9403 · lag 2 = 0,8371 · lag 3 = 0,7432 · lag 24 = 0,5988 · lag 168 = 0,3449.
- ACF chuỗi **ngày**: lag 1 = 0,7276 · lag 2 = 0,5484 · lag 3 = 0,4239 · lag 7 = 0,3700 · lag 14 = 0,3172.
- AR(1) của chuỗi ngày: ρ = 0,7276 → n_eff ≈ **47,1** so với n = 299 (hệ số lạm phát ×6,34).

### 4.2. Khung phương pháp: null dựng DƯỚI H₀ có xét phụ thuộc

Bốn kiểm định xác nhận dùng **bốn cách dựng null khác nhau**, mỗi cách được chọn vì hợp với cấu trúc dữ liệu và với H₀ của chính kiểm định đó:

| Kiểm định | H₀ | Phương pháp **chính** | Đối chứng | Tham số phụ thuộc |
|---|---|---|---|---|
| Mùa | 4 mùa cùng phân phối (quá trình ổn định) | Kruskal-Wallis + **null block bootstrap THEO LỊCH** trên chuỗi **gộp** | Hồi quy HAC có xu hướng (**không dùng để quyết định** — xem 4.3) | block 28 ngày lịch |
| Weekday vs cuối tuần | Hai nhóm cùng phân phối | Hồi quy **HAC/Newey–West** `[1, xu hướng, dummy cuối tuần]` | Mann-Whitney + **null block bootstrap THEO LỊCH** | lag 28 ngày |
| QCVN 24h (trung vị = 50) | P(trung bình ngày > 50) = 0,5 | **HAC/Newey–West** cho tỷ lệ vượt ngưỡng | Null áp đặt H₀ **theo lịch** (signed-rank) + p đảo CI | lag 28 ngày |
| QCVN năm (trung bình = 25) | E(trung bình ngày) = 25 | **HAC/Newey–West** (hệ số chặn) | Null áp đặt H₀ **theo lịch** (t) + p đảo CI | lag 28 ngày |

**Ba nguyên tắc mà phương pháp này tuân thủ.**

1. **Null được dựng DƯỚI H₀.** Với kiểm định theo nhóm, null là chuỗi **gộp** (H₀: các nhóm cùng phân phối). Với kiểm định vị trí, H₀ được **áp đặt** bằng cách dựng bản sao `x* = μ + resample(x − θ̂)` trên lịch — mốc của H₀ nằm trong bản sao. **Không** dùng bootstrap trên chuỗi quan sát rồi đếm tỷ lệ thống kê cực đoan.
2. **Nhãn nhóm theo vị trí lịch của bản sao, không theo nguồn.** Hoán đổi nhãn mùa ngẫu nhiên sẽ phá vỡ cấu trúc mùa vụ; giữ nhãn theo nguồn sẽ giữ cả hiệu ứng mùa trong null. Cách đúng là giữ nhãn theo **vị trí lịch của bản sao** và lấy giá trị ngẫu nhiên từ chuỗi gộp.
3. **CI ≠ p-value.** CI là khoảng tin cậy của ước lượng; p-value là xác suất của dữ liệu **có điều kiện H₀ đúng**. Báo cáo luôn in cả hai và không dùng CI để suy ra p (hay ngược lại).

### 4.3. Quy tắc hạ mức kết luận — chốt trước khi xem kết quả

| Quy tắc | Điều kiện | Hệ quả |
|---|---|---|
| R1 — Ổn định | Kết luận đổi chiều khi đổi độ dài block hoặc lag HAC trong lưới độ nhạy | Hạ xuống **THĂM DÒ** |
| R2 — Đồng thuận | Phương pháp đối chứng cho kết luận **khác chiều** phương pháp chính | Hạ xuống **THĂM DÒ** |
| R3 — Tính được | Không dựng được p hợp lệ | **KHÔNG XÁC NHẬN ĐƯỢC** |
| R4 — Hiệu lực | Tỷ lệ bác bỏ dưới H₀ của phương pháp chính vượt **2,5α** ở kịch bản áp dụng được (mục 9) | Hạ xuống **THĂM DÒ** |
| R5 — Một chu kỳ mùa | Bốn mùa là bốn **đoạn thời gian liên tiếp** trong **một** chu kỳ mùa duy nhất ⇒ không tách được 'mùa' khỏi 'xu hướng' | Kiểm định mùa **luôn** là **THĂM DÒ** |

> **Family hiệu chỉnh Holm vẫn gồm đúng 4 kiểm định** như đã chốt trước khi xem dữ liệu.
> Việc một kiểm định bị hạ xuống *thăm dò* **không** làm thay đổi family — thay đổi family
> sau khi nhìn kết quả là p-hacking.

> **Vì sao kiểm định mùa không dùng hồi quy HAC làm đối chứng.** Với bốn mùa là bốn đoạn thời gian liên tiếp, ba dummy mùa gần **cộng tuyến** với xu hướng ⇒ ma trận hiệp phương sai của ba hệ số mùa gần suy biến ⇒ kiểm định Wald **thổi phồng** (Monte Carlo: size 30–55% thay vì 5%). Đây là lý do R5 hạ kiểm định mùa xuống thăm dò và vì sao hồi quy HAC chỉ được in ra như **chẩn đoán**, không quyết định trạng thái.

---

## 5. Kiểm định 1 — Khác biệt giữa bốn mùa

- **H₀:** Phân phối trung bình ngày giống nhau ở cả bốn mùa (trong một quá trình ổn định trong giai đoạn quan sát).
- **H₁:** Có ít nhất một mùa khác.
- **α = 0,05, omnibus (đuôi trên của H).**

**Phương pháp chính:** Kruskal-Wallis + null circular moving block bootstrap THEO LỊCH (chuỗi gộp trên lịch ngày đầy đủ) (block 28 ngày lịch, 5.000 lặp, seed 42).

| Mùa | n (ngày) | Trung vị (µg/m³) |
|---|---|---|
| Đông | 79 | 60,46 |
| Xuân | 83 | 32,81 |
| Hè | 53 | 31,14 |
| Thu | 84 | 36,30 |

- **H = 61,5344**, df = 3, n = 299.
- **p (hiệu chỉnh phụ thuộc thời gian) = 0,0280** → bác bỏ H₀; **p Holm = 0,0560** → không bác bỏ H₀.
- p tham chiếu (giả định độc lập) = 2,76·10⁻¹³; hồi quy HAC (chẩn đoán, xem 4.3) p = 2,36·10⁻¹⁰.
- Effect size **ε² = 0,2065** (tỷ lệ phương sai hạng giải thích bởi mùa).
- CI 95% block bootstrap (theo lịch) cho chênh lệch trung vị **Đông − Hè**: 29,32 µg/m³, [−29,80; 24,99].

**Độ nhạy theo độ dài block (ngày lịch).**

| Block (ngày lịch) | p | Kết luận |
|---|---|---|
| block = 7 | 0,0002 | bác bỏ H₀ |
| block = 14 | 0,0032 | bác bỏ H₀ |
| block = 21 | 0,0136 | bác bỏ H₀ |
| block = 28 | 0,0280 | bác bỏ H₀ |
| block = 42 | 0,0550 | không bác bỏ H₀ |

> **Trạng thái kết luận: THĂM DÒ (EXPLORATORY).** Một chu kỳ mùa duy nhất và mùa là các đoạn thời gian liên tiếp → không tách được 'mùa' khỏi 'xu hướng'; hồi quy HAC dùng làm đối chứng **không** kiểm soát được sai lầm loại I trong cấu trúc này (Monte Carlo: size 30–55% vì dummy mùa gần cộng tuyến với xu hướng) nên không dùng để quyết định trạng thái.

### 5.1. Hậu định sáu cặp mùa (exploratory — family Holm riêng)

Sáu cặp này **không** thuộc family xác nhận: chúng được khảo sát sau khi kiểm định omnibus, nên mang nhãn *exploratory* và được hiệu chỉnh Holm trong family riêng. p-value của mỗi cặp cũng được dựng lại dưới H₀ có xét phụ thuộc (null block bootstrap **theo lịch** trên chuỗi gộp, hạng tính trong tập A ∪ B).

| Cặp | Trung vị A | Trung vị B | U | p (hiệu chỉnh) | p Holm | p tham chiếu | r_rb | CI 95% (A−B) |
|---|---|---|---|---|---|---|---|---|
| Đông – Xuân | 60,46 | 32,81 | 5191 | 0,0084 | 0,0504 | 1,49·10⁻¹⁰ | 0,583 | [8,82; 36,68] |
| Đông – Hè | 60,46 | 31,14 | 3519 | 0,5975 | 1,0000 | 3,72·10⁻¹¹ | 0,681 | [9,95; 38,65] |
| Đông – Thu | 60,46 | 36,30 | 4951 | 0,0192 | 0,0960 | 5,93·10⁻⁸ | 0,492 | [5,31; 33,82] |
| Xuân – Hè | 32,81 | 31,14 | 2512 | 0,6623 | 1,0000 | 0,1639 | 0,142 | [−4,31; 7,81] |
| Xuân – Thu | 32,81 | 36,30 | 3140 | 0,6055 | 1,0000 | 0,2688 | −0,099 | [−8,65; 3,55] |
| Hè – Thu | 31,14 | 36,30 | 1731 | 0,2464 | 0,9854 | 0,0289 | −0,222 | [−9,59; 0,50] |

---

## 6. Kiểm định 2 — Ngày làm việc vs ngày cuối tuần

- **H₀:** Phân phối PM2.5 trung bình ngày của ngày làm việc và cuối tuần giống nhau.
- **H₁:** Hai phân phối khác nhau.
- **α = 0,05, hai phía.**

**Phương pháp chính:** OLS + HAC (Newey–West), hệ số dummy cuối tuần (lag 28 ngày).
**Đối chứng:** Mann-Whitney U + null circular moving block bootstrap THEO LỊCH (chuỗi gộp trên lịch ngày đầy đủ) (block 28 ngày lịch).

- Ngày làm việc: n = 213, trung vị 36,72 µg/m³.
- Ngày cuối tuần: n = 86, trung vị 39,45 µg/m³.
- **U = 8083,0**, **p (hiệu chỉnh phụ thuộc) = 0,1082** → không bác bỏ H₀; **p Holm = 0,1082** → không bác bỏ H₀.
- p tham chiếu (giả định độc lập) = 0,1120; null block bootstrap theo lịch p = 0,5379.
- Chênh lệch trung vị: **−2,74 µg/m³**, CI 95% block bootstrap (theo lịch) [−6,62; 5,07].
- Effect size **r_rb = −0,1175** (dương = ngày làm việc cao hơn).

**Độ nhạy theo lag HAC (phương pháp chính).**

| Lag (ngày) | p | Kết luận |
|---|---|---|
| lag = 7 | 0,1089 | không bác bỏ H₀ |
| lag = 14 | 0,1121 | không bác bỏ H₀ |
| lag = 21 | 0,1144 | không bác bỏ H₀ |
| lag = 28 | 0,1082 | không bác bỏ H₀ |
| lag = 42 | 0,1318 | không bác bỏ H₀ |

> **Trạng thái kết luận: XÁC NHẬN.** Phương pháp chính và phương pháp đối chứng cùng chiều.

**Ý nghĩa thống kê ≠ ý nghĩa thực tiễn — và power có giới hạn.** Với SD gộp 21,65 µg/m³, n₁ = 213, n₂ = 86, chênh lệch nhỏ nhất phát hiện được ở power 80%, α = 0,05 là **MDE ≈ 7,75 µg/m³** (xấp xỉ chuẩn, tính hậu nghiệm từ SD quan sát — lưu ý: công thức này **giả định độc lập**, nên với chuỗi tự tương quan nó **đánh giá thấp** ngưỡng phân giải thực tế).

- Chênh lệch quan sát được là −2,74 µg/m³, nhỏ hơn MDE, và CI 95% block bootstrap [−6,62; 5,07] chứa 0; |r_rb| = 0,117. Vì vậy dữ liệu **không đủ độ phân giải** để phân biệt 'không có khác biệt' với 'khác biệt nhỏ hơn MDE' — đây không phải bằng chứng khẳng định hai nhóm bằng nhau.
- Ước lượng điểm nằm trong khoảng sai số thực hành của một trạm đo, nên không được dùng để quy kết nguồn phát thải hay hành vi giao thông.

---

## 7. Kiểm định 3 — Đối chiếu QCVN 05:2023/BTNMT (đúng chu kỳ lấy mẫu)

Hai ngưỡng được kiểm định **tách biệt**, mỗi ngưỡng đi với đúng chu kỳ trung bình của nó. Không có phép so sánh nào giữa một giờ đơn lẻ với ngưỡng ngày hoặc ngưỡng năm.

### 7.1. Ngưỡng trung bình 24 giờ — 50 µg/m³

- **H₀:** Trung vị của trung bình ngày bằng 50 µg/m³.
- **H₁:** Trung vị khác 50 µg/m³.
- **α = 0,05, hai phía.**

**Phương pháp chính:** H₀ 'trung vị = μ' tương đương 'P(trung bình ngày > μ) = 0,5' với phân phối liên tục; thống kê là tỷ lệ ngày vượt ngưỡng, SE là sandwich HAC.
**Đối chứng:** Bootstrap áp đặt H₀ resample theo lịch + p-value đảo CI (cùng phân phối bootstrap).

- n = 299 ngày; trung vị 37,20 µg/m³; trung bình 43,38 ± 21,68 µg/m³.
- **t = −2,6558** (tỷ lệ ngày vượt ngưỡng, SE HAC), **p (hiệu chỉnh phụ thuộc) = 0,0083** → bác bỏ H₀; **p Holm = 0,0250** → bác bỏ H₀.
- p tham chiếu (Wilcoxon giả định độc lập) = 7,88·10⁻¹⁰; null áp đặt H₀ theo lịch p = 0,0444.
- Effect size **r = −0,4102** (âm = trung vị nằm dưới ngưỡng).
- CI 95% block bootstrap (theo lịch) cho trung vị: [32,78; 44,83].
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

- **H₀:** Trung bình của trung bình ngày bằng 25 µg/m³.
- **H₁:** Trung bình khác 25 µg/m³.
- **α = 0,05, hai phía.**

**Phương pháp chính:** t-test một mẫu với sai số chuẩn HAC: mô hình chỉ có hệ số chặn, SE là ước lượng sandwich của phương sai dài hạn.
**Đối chứng:** Bootstrap áp đặt H₀ resample theo lịch + p-value đảo CI (cùng phân phối bootstrap).

- n = 299 ngày; trung bình 43,38 ± 21,68 µg/m³.
- **t = 4,3535** (HAC), **p (hiệu chỉnh phụ thuộc) = 1,84·10⁻⁵** → bác bỏ H₀; **p Holm = 7,38·10⁻⁵** → bác bỏ H₀.
- p tham chiếu (t-test giả định độc lập) = 5,33·10⁻³⁷; null áp đặt H₀ theo lịch p = 0,0004.
- Cohen's d = **0,8476** (đơn vị: độ lệch chuẩn của trung bình ngày, không phải của một quan sát năm).
- CI 95% theo HAC (tôn trọng tự tương quan): [35,07; 51,69]; CI 95% block bootstrap theo lịch: [36,11; 51,76]; CI 95% theo t (giả định độc lập — tham chiếu): [40,91; 45,85].

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
| Mùa (4 nhóm, có xét phụ thuộc thời gian) | H = 61,534 | 0,0280 | 0,0560 | ε² = 0,206 | THĂM DÒ (EXPLORATORY) |
| Ngày làm việc vs cuối tuần (có xét phụ thuộc thời gian) | U = 8083,000 | 0,1082 | 0,1082 | r_rb = −0,117 | XÁC NHẬN |
| Trung bình 24h vs 50 µg/m³ (có xét phụ thuộc thời gian) | t (share, HAC) = −2,656 | 0,0083 | 0,0250 | r (cặp) = −0,410 | XÁC NHẬN |
| Trung bình giai đoạn vs 25 µg/m³ (có xét phụ thuộc thời gian) | t (HAC) = 4,354 | 1,84·10⁻⁵ | 7,38·10⁻⁵ | Cohen's d = 0,848 | XÁC NHẬN |

**Kết luận sau hiệu chỉnh Holm: 2/4 kiểm định bác bỏ H₀** (α = 0,05), trong đó 1 kiểm định bị hạ xuống *thăm dò* theo quy tắc R1–R5 của mục 4.3.

**Đối chiếu với phương pháp cũ (giả định quan sát độc lập).**

| Kiểm định | p tham chiếu | p Holm (tham chiếu) | Kết luận (tham chiếu) |
|---|---|---|---|
| Mùa (4 nhóm, có xét phụ thuộc thời gian) | 2,76·10⁻¹³ | 8,29·10⁻¹³ | bác bỏ H₀ |
| Ngày làm việc vs cuối tuần (có xét phụ thuộc thời gian) | 0,1120 | 0,1120 | không bác bỏ H₀ |
| Trung bình 24h vs 50 µg/m³ (có xét phụ thuộc thời gian) | 7,88·10⁻¹⁰ | 1,58·10⁻⁹ | bác bỏ H₀ |
| Trung bình giai đoạn vs 25 µg/m³ (có xét phụ thuộc thời gian) | 5,33·10⁻³⁷ | 2,13·10⁻³⁶ | bác bỏ H₀ |

Phương pháp cũ cho **3/4 bác bỏ H₀**; phương pháp có xét phụ thuộc thời gian cho **2/4**. Đây là **thay đổi kết luận do phương pháp**, không phải do dữ liệu thay đổi: p-value của SciPy coi 299 ngày như 299 quan sát độc lập, trong khi thực tế n_eff ≈ 47,1 (lạm phát ×6,34) — p-value cũ vì vậy **lạc quan**. Mục 9 đo trực tiếp mức lạc quan đó bằng Monte Carlo.

---

## 9. Kiểm soát sai lầm loại I bằng Monte Carlo đa kịch bản

Kiểm chứng **có chi phí**, chạy bằng `python scripts/validate_inference_montecarlo.py --n-sim 1.000`; kết quả lưu ở `reports/inference_montecarlo.csv` và được báo cáo này đọc lại (không chạy lại trong notebook).

- Số lần mô phỏng **mỗi kịch bản**: 1.000; n = 299 ngày; null bootstrap 200 lặp; HAC lag 28 ngày; seed 42.
- Sai số Monte Carlo chuẩn tại p̂ = α: ±0,69 điểm phần trăm; khoảng tin cậy Wilson 95% được in kèm mỗi tỷ lệ.
- **Cột 'độc lập'** là phép kiểm SciPy giả định quan sát độc lập — tham chiếu để thấy mức lạc quan.

| Kịch bản | Phép kiểm | Độc lập | Null bootstrap (lịch) | HAC |
|---|---|---|---|---|
| Quan sát độc lập (i.i.d.) | season | 4,8% [3,6–6,3] | 2,7% [1,9–3,9] | 30,4% [27,6–33,3] |
| Quan sát độc lập (i.i.d.) | weekday | 4,9% [3,7–6,4] | 4,5% [3,4–6,0] | 7,4% [5,9–9,2] |
| Quan sát độc lập (i.i.d.) | median | 6,0% [4,7–7,6] | 13,1% [11,1–15,3] | 9,2% [7,6–11,2] |
| Quan sát độc lập (i.i.d.) | mean | 6,1% [4,8–7,8] | 8,7% [7,1–10,6] | 9,4% [7,7–11,4] |
| AR(1) yếu (ρ = 0,3) | season | 22,6% [20,1–25,3] | 3,7% [2,7–5,1] | 31,6% [28,8–34,5] |
| AR(1) yếu (ρ = 0,3) | weekday | 6,3% [5,0–8,0] | 4,8% [3,6–6,3] | 7,4% [5,9–9,2] |
| AR(1) yếu (ρ = 0,3) | median | 15,7% [13,6–18,1] | 11,7% [9,9–13,8] | 9,4% [7,7–11,4] |
| AR(1) yếu (ρ = 0,3) | mean | 16,6% [14,4–19,0] | 9,2% [7,6–11,2] | 9,9% [8,2–11,9] |
| AR(1) trung bình (ρ = 0,6) | season | 56,0% [52,9–59,0] | 4,6% [3,5–6,1] | 34,5% [31,6–37,5] |
| AR(1) trung bình (ρ = 0,6) | weekday | 4,1% [3,0–5,5] | 3,5% [2,5–4,8] | 7,0% [5,6–8,8] |
| AR(1) trung bình (ρ = 0,6) | median | 33,2% [30,4–36,2] | 10,7% [8,9–12,8] | 9,4% [7,7–11,4] |
| AR(1) trung bình (ρ = 0,6) | mean | 33,4% [30,5–36,4] | 9,5% [7,8–11,5] | 10,3% [8,6–12,3] |
| AR(1) mạnh (ρ = 0,9) | season | 94,2% [92,6–95,5] | 15,6% [13,5–18,0] | 49,5% [46,4–52,6] |
| AR(1) mạnh (ρ = 0,9) | weekday | 0,0% [0,0–0,4] | 0,8% [0,4–1,6] | 4,2% [3,1–5,6] |
| AR(1) mạnh (ρ = 0,9) | median | 65,3% [62,3–68,2] | 14,9% [12,8–17,2] | 16,8% [14,6–19,2] |
| AR(1) mạnh (ρ = 0,9) | mean | 66,1% [63,1–69,0] | 14,4% [12,4–16,7] | 16,6% [14,4–19,0] |
| AR(1) mạnh (ρ = 0,73) + xu hướng tuyến tính (mùa trùng với thời gian) | season | 100,0% [99,6–100,0] | 100,0% [99,6–100,0] | 37,8% [34,8–40,8] |
| AR(1) mạnh (ρ = 0,73) + xu hướng tuyến tính (mùa trùng với thời gian) | weekday | 0,0% [0,0–0,4] | 0,8% [0,4–1,6] | 7,3% [5,8–9,1] |
| AR(1) mạnh (ρ = 0,73) + xu hướng tuyến tính (mùa trùng với thời gian) | median | 100,0% [99,6–100,0] | 100,0% [99,6–100,0] | 100,0% [99,6–100,0] |
| AR(1) mạnh (ρ = 0,73) + xu hướng tuyến tính (mùa trùng với thời gian) | mean | 100,0% [99,6–100,0] | 100,0% [99,6–100,0] | 100,0% [99,6–100,0] |
| Phụ thuộc kéo dài (MA, cửa sổ 30 ngày) | season | 98,0% [96,9–98,7] | 21,7% [19,3–24,4] | 55,5% [52,4–58,6] |
| Phụ thuộc kéo dài (MA, cửa sổ 30 ngày) | weekday | 0,0% [0,0–0,4] | 0,2% [0,1–0,7] | 3,0% [2,1–4,3] |
| Phụ thuộc kéo dài (MA, cửa sổ 30 ngày) | median | 1,7% [1,1–2,7] | 0,0% [0,0–0,4] | 0,0% [0,0–0,4] |
| Phụ thuộc kéo dài (MA, cửa sổ 30 ngày) | mean | 0,0% [0,0–0,4] | 0,0% [0,0–0,4] | 0,0% [0,0–0,4] |
| AR(1) mạnh + thiếu ngẫu nhiên 20% | season | 66,8% [63,8–69,6] | 5,5% [4,2–7,1] | 42,9% [39,9–46,0] |
| AR(1) mạnh + thiếu ngẫu nhiên 20% | weekday | 1,8% [1,1–2,8] | 0,5% [0,2–1,2] | 8,8% [7,2–10,7] |
| AR(1) mạnh + thiếu ngẫu nhiên 20% | median | 39,3% [36,3–42,4] | 9,8% [8,1–11,8] | 10,2% [8,5–12,2] |
| AR(1) mạnh + thiếu ngẫu nhiên 20% | mean | 39,3% [36,3–42,4] | 9,3% [7,7–11,3] | 11,6% [9,8–13,7] |
| AR(1) mạnh + thiếu thành cụm 20% | season | 64,6% [61,6–67,5] | 6,4% [5,0–8,1] | 48,6% [45,5–51,7] |
| AR(1) mạnh + thiếu thành cụm 20% | weekday | 3,0% [2,1–4,3] | 0,2% [0,1–0,7] | 8,8% [7,2–10,7] |
| AR(1) mạnh + thiếu thành cụm 20% | median | 37,1% [34,2–40,1] | 6,8% [5,4–8,5] | 11,0% [9,2–13,1] |
| AR(1) mạnh + thiếu thành cụm 20% | mean | 36,9% [34,0–39,9] | 9,1% [7,5–11,0] | 12,0% [10,1–14,2] |
| AR(1) mạnh + mặt nạ thiếu GIỐNG dữ liệu thật | season | 72,3% [69,4–75,0] | 5,6% [4,3–7,2] | 40,3% [37,3–43,4] |
| AR(1) mạnh + mặt nạ thiếu GIỐNG dữ liệu thật | weekday | 1,7% [1,1–2,7] | 0,4% [0,2–1,0] | 7,6% [6,1–9,4] |
| AR(1) mạnh + mặt nạ thiếu GIỐNG dữ liệu thật | median | 41,5% [38,5–44,6] | 10,5% [8,7–12,6] | 11,9% [10,0–14,1] |
| AR(1) mạnh + mặt nạ thiếu GIỐNG dữ liệu thật | mean | 42,3% [39,3–45,4] | 10,3% [8,6–12,3] | 12,0% [10,1–14,2] |

**Đọc kết quả — đây là bằng chứng hiệu lực, không phải phỏng đoán.**

1. Cột **độc lập** vỡ tung khi có tự tương quan: kiểm định mùa bác bỏ H₀ tới 94–100% số lần, kiểm định vị trí tới 65%, chỉ với dữ liệu **không** có hiệu ứng. Đây là lý do phải hiệu chỉnh — và là lý do p-value của SciPy trên bộ dữ liệu này không được dùng để kết luận.
2. Cột **null bootstrap theo lịch** giữ tỷ lệ bác bỏ gần α cho kiểm định mùa (2,7–6,4% ở các kịch bản có ρ gần với dữ liệu thật) và weekday (0,2–4,8%); nó **bảo thủ** khi phụ thuộc rất mạnh (ρ = 0,9 → 15,6%) hoặc phụ thuộc kéo dài (21,7%) — mất sức mạnh chứ không sai hướng.
3. Cột **HAC** giữ tỷ lệ bác bỏ gần α cho kiểm định vị trí (9,2–12,0%) và weekday (3,0–8,8%), nhưng **vỡ** cho kiểm định mùa (30–55%): ba dummy mùa là bốn **đoạn thời gian liên tiếp** nên gần cộng tuyến với xu hướng ⇒ ma trận hiệp phương sai của ba hệ số mùa gần suy biến. Đây là lý do kiểm định mùa **luôn** ở trạng thái thăm dò (R5) và hồi quy HAC cho mùa không dùng để quyết định trạng thái.
4. Kịch bản **“xu hướng tuyến tính”** cố tình làm H₀ **sai** cho các kiểm định vị trí (xu hướng dịch trung bình khỏi 0) — nên tỷ lệ 100% ở đó là **hành vi đúng**, không phải lỗi hiệu lực. Kịch bản này dùng để kiểm tra nhiễu *mùa ↔ xu hướng* ở kiểm định mùa.
5. Quy tắc **R4** (size ≤ 2,5α ở các kịch bản áp dụng được cho dữ liệu này: ρ gần với ρ quan sát và mặt nạ thiếu tương ứng) được áp dụng cho từng kiểm định; kết quả áp dụng nêu ở từng mục.

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

> **Kết luận về khả năng khái quát hóa.** Kết quả mùa trong báo cáo này là **mô tả của một giai đoạn quan sát duy nhất**, ở một trạm duy nhất, với điều kiện khí tượng của chính năm đó. Không có bằng chứng nào trong bộ dữ liệu cho phép nói rằng đây là quy luật mùa vụ ổn định nhiều năm. Vì vậy kiểm định mùa ở mục 5 ở trạng thái **THĂM DÒ** và kết luận mùa được trình bày như **hiệu ứng mô tả**, không phải xác nhận.

---

## 11. Kiểm tra độ nhạy (exploratory, không thuộc family nào)

### 11.1. Ghép cặp theo tuần cho weekday/weekend

- Số tuần đủ điều kiện (≥ 3 ngày trong tuần và ≥ 2 ngày cuối tuần): **40**.
- Trung vị chênh lệch (weekday − weekend): **−2,70 µg/m³**, CI 95% bootstrap [−7,92; 2,69].
- Tỷ lệ tuần có weekday cao hơn: 37,5%.
- Signed-rank có HAC (Newey–West, lag 4 tuần) trên 40 chênh lệch tuần: t = 315,000, p = 0,9838 → không bác bỏ H₀ ở α = 0,05 (tham chiếu, giả định độc lập: p = 0,2064).

Phép thử này loại bỏ biến thiên giữa các tuần và không dựa vào giả định các ngày độc lập. Nếu kết luận khác với kiểm định ở mục 6, kết luận đúng là **không ổn định** — và đó phải là điều được viết ra.

### 11.2. Kruskal-Wallis trên trung bình tuần theo mùa

- Số tuần dùng được: 55; H = 19,310, df = 3, p (hiệu chỉnh theo lịch tuần) = 0,0190, p tham chiếu = 0,0002, ε² = 0,4109.
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

**Power = 1 − β, và độ phân giải của phép kiểm có giới hạn cụ thể.** Với SD gộp 21,65 µg/m³, n₁ = 213, n₂ = 86, chênh lệch nhỏ nhất phát hiện được ở power 80%, α = 0,05 là **MDE ≈ 7,75 µg/m³** (xấp xỉ chuẩn, giả định độc lập). Chênh lệch trung vị quan sát ở mục 6 là 2,74 µg/m³, tức nhỏ hơn MDE. Vì thế kết luận ở mục 6 **không** chứng minh hai nhóm bằng nhau: nó chỉ cho thấy dữ liệu không đủ độ phân giải để tách 'không có khác biệt' khỏi 'khác biệt nhỏ hơn MDE'. Với bài toán cảnh báo, sai lầm loại II (bỏ lọt một đợt ô nhiễm) tốn kém hơn sai lầm loại I, nên ngưỡng vận hành của mô hình ở Issue #13 sẽ được chọn theo Recall chứ không theo Accuracy.

---

## 13. Prior probability và bẫy base-rate (task 5.8)

Trong 299 ngày đủ độ phủ, 84 ngày có trung bình ≥ 50 µg/m³ → **prior ≈ 28,1%**. Đó là xác suất tiên nghiệm mà một bộ phân loại 'ngày ô nhiễm' phải đối mặt: nếu nó luôn dự đoán 'không ô nhiễm', Accuracy đã ≈ 71,9% mà không học được gì.

Vì vậy mọi tỷ lệ trong báo cáo này đều nêu rõ **tử số và mẫu số**, và không có tỷ lệ nào được trình bày như một 'độ chính xác'. Prior cũng **dịch chuyển** giữa Train và Test do điểm cắt rơi vào giữa mùa đông; hệ quả đó thuộc Issue #13 và phải được xử lý bằng Recall và PR-AUC, không bằng Accuracy.

---

## 14. Giới hạn khoa học

1. **Một chu kỳ mùa, một trạm.** Dải 07/2025–07/2026 chỉ chứa một vòng mùa và toàn bộ dữ liệu đến từ một trạm đô thị. Khác biệt theo mùa là mô tả của **giai đoạn này**, không ngoại suy được sang năm khác hay trạm khác (mục 10).
2. **Thiếu dữ liệu không ngẫu nhiên.** 79 ngày trong 378 ngày lịch không tạo được trung bình ngày, tập trung thành 17 cụm (cụm dài nhất 47 ngày). Cơ chế thiếu **không** được biết là ngẫu nhiên; nếu độ phủ phụ thuộc thời tiết (ngày mưa nhiều mây thì thiếu dữ liệu) thì mức nền ước lượng có thể bị lệch. Báo cáo **không** giả định MCAR.
3. **Hiệu chỉnh phụ thuộc là xấp xỉ, không phải định nghĩa.** Mọi phương pháp ở mục 4 đều là phương pháp bậc cao với giả định ổn định; Monte Carlo (mục 9) cho thấy tỷ lệ bác bỏ dưới H₀ có kịch bản vượt 2,5α. p-value vì vậy là **chỉ báo độ tương thích**, không phải xác suất chính xác tuyệt đối.
4. **Block bootstrap không mô phỏng được phụ thuộc dài hạn hơn 4 tuần**; kịch bản phụ thuộc kéo dài (mục 9) cho thấy phương pháp **bảo thủ** ở đó (size thấp hơn α), tức mất sức mạnh chứ không sai hướng.
5. **Ngưỡng 18/24 giờ** là quy ước phân tích (độ phủ 75%), không phải điều khoản QCVN. Đổi ngưỡng sẽ đổi n; bảng nhật ký lọc ở mục 1 làm việc đổi ngưỡng trở nên minh bạch.
6. **QCVN 05:2023/BTNMT quy định ở điều kiện chuẩn (µg/Nm³, 25 °C, 760 mmHg)**, còn trạm OpenAQ báo nồng độ môi trường (µg/m³). So sánh định lượng với ngưỡng vì vậy là xấp xỉ.
7. **Không có kết luận nhân quả.** Khác biệt theo mùa/ngày trong tuần là liên hệ thống kê; nguồn phát thải, khí tượng và điều kiện biên không được phân tách ở đây.
8. **Kết quả mô phỏng không thay thế lý thuyết** — mô phỏng dùng mô hình AR(1)/MA và một mặt nạ thiếu lấy từ dữ liệu thật; nó không bao hàm mọi cơ chế sinh dữ liệu có thể có.

---

## 15. Tái lập

```bash
python -m unittest tests.test_inference -v          # kiểm thử tất định
python scripts/validate_inference_montecarlo.py --n-sim 1000   # kiểm chứng Monte Carlo
python -c "from src.inference import run_inference, render_inference_report, DEFAULT_REPORT_PATH; " \
          "DEFAULT_REPORT_PATH.write_text(render_inference_report(run_inference()), encoding='utf-8')"
```

Mọi con số tái lập được với seed 42, 1.000 lặp CI bootstrap và 5.000 lặp null bootstrap. Sai khác duy nhất có thể có là phiên bản NumPy/SciPy (đã ghi ở đầu báo cáo).
