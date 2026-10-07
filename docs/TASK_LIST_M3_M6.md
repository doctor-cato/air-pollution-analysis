# Task List — Đối chiếu Slide Bài Giảng & Roadmap (M3 → M6)

> Sinh ra từ việc đối chiếu 6 slide tóm tắt trong Obsidian vault `CMC/datascience`
> (W6, W7, W9, W10, W11, W12) với `docs/roadmap.md` và nội dung issue #8–#17 trên GitHub.
>
> **Ngày lập:** 2026-10-07 · **Sửa đợt 2:** 2026-10-07 (hiệu chỉnh sau khi đối chiếu số liệu thật).
> **Trạng thái repo:** nhánh `docs/audit-delivery`.
>
> **Ký hiệu ưu tiên:** 🔴 bắt buộc (thay đổi kết luận khoa học hoặc là điểm chấm) ·
> 🟡 nên có (điểm cộng ở viva) · ⚪ housekeeping.

### Tổng quan: 153 task

| Phase | Nội dung | Task | Ước lượng |
|---|---|---|---|
| 0 | Dọn nhà trước M3 | 8 | ~40 phút |
| 1 | Vá issue body | 27 | ~1 giờ |
| **1B** | **Cập nhật tài liệu đồng bộ (xen kẽ)** | **29** | **~1 buổi** |
| 2 | #8 Thống kê mô tả | 12 | ~1–2 buổi |
| 3 | #9 7 biểu đồ | 13 | ~2 buổi |
| 4 | #10 Midterm | 8 | ~1 buổi |
| 5 | #11 Suy luận | 9 | ~1–2 buổi |
| 6 | #12 Hồi quy | 9 | ~2 buổi |
| 7 | #13 Phân loại | 11 | ~2 buổi |
| 8 | #14 Đạo đức & quy mô | 9 | ~1 buổi |
| 9 | #15 Module hoá & độ nhạy | 7 | ~1 buổi |
| 10 | #16 Báo cáo cuối kỳ | 4 | ~1–2 buổi |
| 11 | #17 Audit & bảo vệ | 7 | ~1 buổi |

⚠️ M3 (Phase 0–4 + 1B.1) chiếm ~20% điểm rubric riêng giữa kỳ nhưng chỉ ~4 buổi — đây là mốc có deadline
riêng, **không nên hoãn để làm M4 trước**.

### Số liệu thực tế đã kiểm chứng (đọc trực tiếp từ `data/processed/air_pollution_final.parquet`)

```text
9.044 dòng × 18 cột · 261 KB · 1 trạm · 1 địa điểm · 376 ngày (~12,5 tháng) · 1.005 dòng/giờ
pm25 NaN 1.549 (17,1%) · pm10 NaN 1.469 · 5 biến khí tượng NaN 0 · complete-case 7.372 dòng
corr(pm25, pm10) = 0,9727 · R² đơn biến pm25~pm10 = 0,9462
ĐÃ CÓ SẴN trong Parquet: hour_sin, hour_cos, month_sin, month_cos
Prevalence cảnh báo (trung bình trượt 24h ≥ 50 µg/m³):
  toàn bộ  1.655/5.317 = 18,30%
  Train     986/2.994 = 21,06%
  Test      669/2.323 = 15,34%
```

> ⚠️ **Con số trong roadmap cần xác minh.** `docs/roadmap.md:933` ghi tỷ lệ **3,08% (Train) vs 6,89% (Test)**,
> nhưng tính lại từ Parquet cho **21,06% vs 15,34%**. Chênh lệch ~7×. Hoặc roadmap dùng định nghĩa khác,
> hoặc con số đã cũ từ trước khi chốt split. Xem task **0.7**.

### Các mục đã bị hạ cấp sau khi đối chiếu số liệu thật

| Mục | Ký hiệu cũ | Mới | Lý do |
|---|---|---|---|
| Bonferroni / multiple testing | 🔴 | 🟡 | Chỉ 3 kiểm định trên **các câu hỏi khác nhau**, không phải "đo 20 chỉ số gần giống nhau" như slide W9 cảnh báo. Hiệu ứng lớn trên n=7.372 → p-value hiệu chỉnh vẫn < 0,001. **Không thay đổi kết luận.** |
| Base Rate Fallacy | 🔴 | 🟡 *(viết lại)* | Slide dùng ví dụ bệnh **0,1%**. Thực tế prevalence **21%** → bẫy Accuracy 99% **không nguy hiểm** (Dummy đạt ~79%). Vấn đề thật là **dịch chuyển prevalence Train → Test**. |
| 4 sai lầm p-value, CI, Type I/II, Power | 🔴 | ⚪ *(chuyển)* | Là **kiến thức viva**, thuộc `docs/viva_qa_prep.md` (#16). Không phải deliverable của #11 — ép vào notebook là sai chỗ. |
| 5V + ngưỡng GB | 🔴 | 🟡 *(nhẹ)* | 261 KB vs ngưỡng 10 GB — lệch 4 bậc độ lớn. Ghi thẳng con số, không diễn giải dài. |
| Tối ưu trước khi kết luận Spark | 🔴 | 🟡 *(gộp)* | Vấn đề đạo đức học thuật có thật (slide W12 takeaway #1), nhưng thực tế 261 KB nên kết luận đã biết trước. Gộp thành **một** bảng so sánh tài nguyên. |

---

## Phase 0 — Dọn nhà trước khi làm M3 (~30 phút)

Không làm được gì nếu chưa có nền tảng sạch. 8 việc này phải xong trước M3.

- [ ] **0.1** ⚪ Về `main`, kiểm tra đồng bộ với `origin/main`, xử lý 13 nhánh local/remote tồn đọng
      (`backup/`, `chore/`, `docs/sync-m2-state`, `feat/issue-3-…` đã merge…) — nếu không cần thì xoá sau khi
      xác nhận đã merge.
- [x] **0.2** ✅ **Đã giải quyết — giữ lại notebook, đã đăng ký vào roadmap.**
      `notebooks/03_processed_data_preview.ipynb` (35 ô) là notebook **có giá trị**: assert schema canonical,
      kiểm tra kết quả cleaning (mã lỗi số ẩn, PM2.5 ⊆ PM10, trùng khóa, cờ chẩn đoán), in thông tin
      Train/Test split, trực quan hoá kiểm tra. Đây là lớp kiểm tra cuối trước khi M3 đọc artifact.
      Đã thêm vào cây `notebooks/` trong `docs/roadmap.md` §12 với nhãn `[Issue #7]`.
      ⚠️ Thay đổi cục bộ còn lại trên file này là **churn định dạng thuần** (72 dòng = cell `id` đánh số lại
      + dấu phẩy cuối JSON do `nbformat` ghi lại) — **không có thay đổi nội dung hay output**, nên
      không commit. Còn lại: xác nhận thứ tự `nbconvert` glob `03_*.ipynb` (task 4.4).
- [x] **0.3** 🔴 **Đã xong trong `docs/roadmap.md`** — còn lại: `README.md` + `AGENTS.md`.
      Roadmap hiện dùng tiền tố `06_` cho CẢ HAI `06_regression_modeling.ipynb` và
      `06_classification_alerts.ipynb` → yêu cầu "chạy tuần tự `00_` → `06_`" ở Issue #17 không xác định
      được thứ tự. Đã đổi thành `07_classification_alerts.ipynb` ở 4 chỗ trong roadmap: cây `notebooks/` (§12),
      Deliverables tuần 11, Task 4 của tuần 15, và Final Deliverables "chuỗi `00_` đến `07_`".
      Còn lại: cập nhật `README.md` (cây thư mục + §2) và `AGENTS.md` (mục Notebook Execution Order) —
      làm cùng task D2/D7.
- [ ] **0.4** ⚪ Chốt ngày nộp midterm và deadline nộp Project Charter theo thông báo GV
      (roadmap có nhắc "23:59 ngày quy định" nhưng không ghi ngày).
- [ ] **0.5** ✅ **Đã giải quyết — KHÔNG thêm `shap`.** Kiểm tra env cho thấy `shap` chưa cài, nhưng
      **không cần thêm**. Issue #13 dùng `RandomForestClassifier` — `feature_importances_` kèm
      `sklearn.inspection.permutation_importance` đã cho biến quan trọng có giải thích được, mà
      scikit-learn **đã có sẵn** trong `requirements.txt`. Thêm `shap` (dự phòng ~60 MB + phụ thuộc) chỉ để
      lấy cùng một thông tin là YAGNI. Nếu sau này cần SHAP cho mô hình hộp đen thì thêm lúc đó.
- [ ] **0.6** ✅ **Đã kiểm chứng** — `nbclient`, `nbconvert`, `nbformat` đều có trong env.
      Lệnh `nbconvert --execute` của task 4.5 chạy được ngay.
- [ ] **0.7** 🔴 **Xác minh lại con số prevalence 3,08% / 6,89% trong `docs/roadmap.md:933`.**
      Tính lại từ Parquet ra **21,06% (Train) / 15,34% (Test)**. Phải xác định: (a) roadmap dùng định nghĩa
      nào — trung bình trượt 24h hay nồng độ tức thời theo giờ? (b) con số có còn đúng sau khi chốt split
      không? **Đây là con số GV sẽ nhìn thấy trong báo cáo** — sai là mất điểm ở cả midterm lẫn final.
      Sửa roadmap sau khi xác minh.
- [ ] **0.8** 🔴 **Sửa Task 2 của Issue #13 — 4 cột `sin`/`cos` đã có sẵn trong Parquet.**
      `hour_sin`, `hour_cos`, `month_sin`, `month_cos` đã được tạo ở Issue #7 và nằm trong
      `air_pollution_final.parquet`. Nếu làm lại sẽ sinh `hour_sin_x`/`hour_sin_y` hoặc ghi đè.
      Sửa thành: *dùng lại 4 cột có sẵn; chỉ tạo `pm25_rolling_mean_24h`, `pm25_rolling_std_24h`,
      `pm25_lag24`, nhiệt-ẩm, cờ lặng gió.*

---

## Phase 1 — Vá issue body (~1 giờ, làm TRƯỚC khi code)

Sau khi đối chiếu số liệu thật, **5 mục 🔴 bị hạ xuống** (xem bảng ở đầu file). Còn lại **4 mục 🔴**
đều thay đổi *kết luận khoa học*, không phải chỉ cách trình bày. Sửa issue body trước khi viết notebook,
vì khi đã viết xong thì phải viết lại cả notebook.

- [ ] **1.1** 🟡 **Issue #11 — hiệu chỉnh multiple testing (đã hạ cấp).**
      Slide W9 cảnh báo "đo 20 chỉ số gần giống nhau mà không hiệu chỉnh Bonferroni". Ở đây chỉ có **3 kiểm
      định trên các câu hỏi khác nhau** (mùa / ngày trong tuần / QCVN) → không thuộc tình huống slide mô tả.
      Thêm AC *nhẹ*: báo cáo p-value thô **và** p-value hiệu chỉnh Holm cạnh nhau, ghi rõ lý do
      "hiệu chỉnh không làm thay đổi kết luận" (kiểm chứng được, không phải khẳng định suông).
- [ ] **1.2** 🟡 **Issue #11 + #13 — Base Rate / prior probability (viết lại cho đúng bối cảnh).**
      Slide W6 dùng ví dụ bệnh **0,1%** → dương tính chỉ ~9% là thật. Ở đây prevalence thực tế là **18,3%**
      (rolling 24h ≥ 50), DummyClassifier đã đạt ~81,7% → **bẫy Accuracy 99% không nguy hiểm**, không
      được diễn giải quá mức. Vấn đề **thật** là **dịch chuyển prevalence Train 21,06% → Test 15,34%**
      (chênh 5,7 điểm phần trăm): mô hình có PPV/recall khác nhau trên hai kỳ, nên **mọi chỉ số tỷ lệ
      phải nêu mẫu số và dùng cùng một mẫu số cho cả Train lẫn Test**.
      Thêm AC: báo cáo PPV (precision) cùng prevalence của tập, không dùng chung một con số.
- [ ] **1.3** ⚪ ~~**Issue #11 — 4 sai lầm khi đọc p-value + CI + Type I/II + Power**~~ → **chuyển sang
      Phase 10, task 10.4** (`docs/viva_qa_prep.md`). Đây là **kiến thức viva**, không phải deliverable
      của notebook #11. Nội dung cần phủ: định nghĩa p-value đúng (có điều kiện $H_0$) · 4 sai lầm phổ biến ·
      cách hiểu đúng của CI theo nghĩa lặp mẫu · phân biệt sai lầm loại I (α) và loại II (β) · Power = 1 − β
      trong bối cảnh cảnh báo sớm (bỏ lọt 1 đợt tệ hơn báo động giả).
- [ ] **1.4** 🔴 **Issue #12 — Adjusted $R^2$.**
      Slide W10 cảnh báo: `$R^2` luôn tăng khi thêm biến rác → phải dùng Adjusted `$R^2$`.
      Roadmap không có chỗ nào nhắc (grep rỗng). Thêm vào Task 7 (đánh giá trên Test).
- [ ] **1.5** 🔴 **Issue #13 — Feature Selection + tuyên bố xử lý đa cộng tuyến.**
      Issue #8 đã đo `corr(pm25, pm10) = 0,9727`, `$R^2` đơn biến = 0,9462.
      Slide W11 xử lý việc này bằng Feature Selection (loại biến tương quan cao / RF importance / Lasso).
      Thêm AC: hoặc loại `pm10`, hoặc tuyên bố rõ cách xử lý và giải thích trong notebook.
- [ ] **1.6** 🔴 **Issue #13 — PR-AUC phải đối chiếu với baseline = tỷ lệ dương tính (prevalence).**
      PR-AUC không có nghĩa nếu không so với prevalence. Slide W11 cảnh báo ROC gây cảm giác lạc quan ảo.
- [ ] **1.7** 🟡 **Issue #14 — "Tối ưu trước, kết luận sau" (gộp với 1.8 thành MỘT task).**
      Slide W12 takeaway #1: tối ưu code / Parquet / index / float32 **trước khi** nghĩ đến Spark.
      Vấn đề đạo đức học thuật có thật — roadmap `:41` nói kết luận Spark phải dẫn xuất từ số liệu đo.
      Nhưng dataset chỉ 261 KB nên kết luận đã biết trước. Đủ làm **1 bảng**: đo trước, đo lại sau
      float64→float32 + Parquet compression, đo lại sau vectorization, rồi kết luận.
- [ ] **1.8** 🟡 **Issue #14 — 5V + ngưỡng GB + Scale Up vs Scale Out (gộp với 1.7).**
      Slide W12 đưa ngưỡng: `<10 GB` Pandas/Polars · `10–100 GB` DuckDB/PostgreSQL · `>100 GB` Spark.
      Dataset hiện tại **261 KB — lệch ngưỡng 10 GB khoảng 4 bậc độ lớn**. Ghi thẳng con số, không diễn
      giải dài; thêm 1 dòng mô tả Scale Up (thêm RAM, trần vật lý) vs Scale Out (cụm, cần phần mềm phân tán).
- [ ] **1.9** 🔴 **Issue #14 — Explainability (feature importance).**
      Slide W12 takeaway #4: khả năng giải thích **quan trọng hơn** thêm 0,5% accuracy.
      Roadmap không có deliverable giải thích mô hình nào ở #13 lẫn #14. Với bài cảnh báo ô nhiễm, "vì sao hệ thống cảnh báo
      đợt này?" là câu hỏi vận hành thực tế.
      Dùng công cụ **đã có sẵn**, không thêm dependency (xem task 0.5): `feature_importances_` +
      `sklearn.inspection.permutation_importance` (đo trên **tập Test**). Deliverable:
      `figures/feature_importance.png` + bảng xếp hạng trong `docs/classification_findings.md` (task D13).
- [ ] **1.10** 🟡 **Issue #8** — mỗi chỉ số phải kèm `n` quan sát + `n_missing`.
      Roadmap `:1038`: `pm25` còn NaN ở **1.549 hàng** (1.289 khối dài + 260 khối ngắn). Không có AC nào nói
      thống kê mô tả dựa trên 7.495 dòng hay 5.946 dòng.
- [ ] **1.11** 🟡 **Issue #8** — báo cáo độ bao phủ từng biến khí tượng trước khi tính tương quan.
      Ma trận Pearson/Spearman trên tập thiếu dữ liệu không phải ma trận trên Parquet đã đóng băng.
- [ ] **1.12** 🟡 **Issue #8** — quy tắc 3 vế `Mean > Median > Mode` để đọc chiều lệch (slide W6 §BLOCK 2).
- [ ] **1.13** 🟡 **Issue #8** — CLT, `SE = σ/√n`, quy tắc thực nghiệm 68–95–99.7 (slide W6 §BLOCK 1).
- [ ] **1.14** 🟡 **Issue #8** — Spurious correlation & Confounders (slide W6 §BLOCK 3). Nghịch lý Simpson đã có
      trong phần addendum (fog × mùa đảo dấu) — giữ nguyên.
- [ ] **1.15** 🟡 **Issue #9** — thang đo (Nominal/Ordinal/Interval/Ratio) quyết định loại biểu đồ (slide W7 §BLOCK 1).
- [ ] **1.16** 🟡 **Issue #9** — thứ bậc kênh thị giác Cleveland–McGill (vị trí > độ dài > hướng > góc >
      diện tích > thể tích > màu). Kèm **câu trả lời sẵn** cho câu hỏi "vì sao chọn heatmap (dùng màu,
      kênh hạng 7/7)?" → vì mục đích là tìm mẫu hình cục bộ, không phải so sánh giá trị từng ô.
- [ ] **1.17** 🟡 **Issue #9** — 3 cách bóp méo còn lại ngoài truncated Y: trục tung kép, cắt xén cửa sổ thời gian,
      bóp méo bin width histogram (slide W7 §BLOCK 1).
- [ ] **1.18** 🟡 **Issue #9** — chọn loại bảng màu theo loại dữ liệu (Qualitative / Sequential / Diverging).
- [ ] **1.19** 🟡 **Issue #12** — phân biệt Outlier vs High Leverage vs Influencing Point (slide W10 §BLOCK 2).
- [ ] **1.20** 🟡 **Issue #12** — lý do chọn MAE vs RMSE theo ngữ cảnh (slide W10 takeaway #3):
      MAE để giải thích cho người không chuyên môn, RMSE khi sai số lớn gây hậu quả nghiêm trọng.
- [ ] **1.21** 🟡 **Issue #12** — AC chuẩn hóa trước Ridge/Lasso (slide W10 takeaway #4). Hiện thoả qua #7
      (`RobustScaler`) nhưng chưa được ghi thành tiêu chí nghiệm thu.
- [ ] **1.22** 🟡 **Issue #13** — biên bản audit Task 7 liệt kê đủ 4 dạng rò rỉ + phủ trường hợp SMOTE
      (dù đang dùng `class_weight` nên không cần SMOTE, phải nói rõ lý do không dùng).
- [ ] **1.23** 🟡 **Issue #13** — heuristic "nghi ngờ ngay nếu điểm > 99%" (slide W11 takeaway #4) và
      diễn giải Odds Ratio `$e^β` cho Logistic Regression.
- [ ] **1.24** ⚪ **Issue #14** — ghi bằng văn bản lý do loại trừ 3 khái niệm slide W12 dạy nhưng roadmap loại:
      k-anonymity (`:44`), Fairness–Accuracy Trade-off, Anonymisation vs Pseudonymisation.
      Loại trừ là hợp lý (1 trạm, không có thuộc tính nhạy cảm) — nhưng **phải có đoạn văn giải thích trong
      `docs/datasheet.md`**, nếu không GV sẽ hỏi "sao không làm?".
- [ ] **1.25** ⚪ Sửa roadmap `:1196` — trích "Slide W7 & W14" nhưng vault không có slide W14 (tuần 14 là
      mentoring, không có slide riêng). Trích dẫn không kiểm chứng được.
- [x] **1.26** ✅ **Đã xong** — thêm `TASK_LIST_M3_M6.md` vào cây `docs/` trong `docs/roadmap.md` §12,
      và `03_processed_data_preview.ipynb` vào cây `notebooks/` (task 0.2).

---

## Phase 1B — Cập nhật tài liệu đồng bộ (~1 buổi, xen kẽ theo từng issue)

Repo này coi tài liệu là **artifact bàn giao ngang hàng với mã nguồn**, không phải phần phụ. M1–M2 đã
thực hiện tốt: mỗi issue đều kèm 1 tài liệu sinh ra từ code thật (`data_dictionary.md` 36,9 KB,
`data_quality_audit.md` 30,3 KB, `cleaning_log.md` 32,3 KB, `source_profiling_decision.md` 73,5 KB).
**M3–M6 phải giữ đúng nhịp đó** — GV và hội đồng đọc docs nhiều hơn đọc notebook.

### 1B.1 — Ngay sau Phase 2–3 (M3)

- [ ] **D1** 🔴 `docs/roadmap.md` — cập nhật §2 trạng thái triển khai: đánh dấu Issue #8, #9 DONE,
      sửa mục "notebooks 04–06 chưa hiện thực hoá", thêm tên notebook mới sau task 0.3.
- [ ] **D2** 🔴 `README.md` §2 — cập nhảy trạng thái từ "Milestone 2" sang "Milestone 3"; bổ sung
      `notebooks/04_descriptive_stats.ipynb`, `src/visualizer.py`, `figures/FIG-01…07.png`,
      `reports/statistical_profile.csv` vào cây thư mục; sửa trạng thái issue #7 "chưa merge" nếu đã merge.
- [ ] **D3** 🔴 `README.md` — thêm mục thống kê chuỗi dữ liệu thật vào phần mô tả: 9.044 dòng × 18 cột ·
      1 trạm (`556 Nguyễn Văn Cừ`) · 376 ngày (2025-07-03 → 2026-07-15) · 1.005 dòng/giờ ·
      `pm25` NaN 17,1%. Hiện README chủ yếu mô tả *quy trình*, chưa mô tả *đặc tính chuỗi*.
- [ ] **D4** 🔴 `docs/data_dictionary.md` — bổ sung mục "Đặc tính quan sát thực tế" cho 18 cột: tỷ lệ
      NaN, min/max/P50, tỷ lệ cờ nhị phân. Là nền cho cả báo cáo giữa kỳ lẫn cuối kỳ.
- [ ] **D5** 🔴 Tạo **`docs/descriptive_findings.md`** — kết quả EDA của Issue #8 dạng văn xuôi: 4 họ chỉ số,
      lựa chọn Mean vs Median kèm lý do, phát hiện chu kỳ thời gian, ma trận tương quan kép, kết luận
      về `fog × mùa` (addendum issue #8), VIF sớm cho cặp `pm25`/`pm10`.
      **Không có tài liệu này thì báo cáo giữa kỳ sẽ phải viết lại từ notebook** — và số liệu sẽ lệch.
- [ ] **D6** 🟡 `docs/data_dictionary.md` hoặc `docs/descriptive_findings.md` — đính chính con số
      prevalence sau task 0.7.
- [ ] **D7** 🟡 `AGENTS.md` — cập nhật mục "Architecture Notice" (hiện ghi notebooks `04`–`06` chưa có;
      cần nói rõ thứ tự chạy sau khi thêm `04`–`07`) và mục "Notebook Execution Order".

### 1B.2 — Sau Phase 4 (Midterm)

- [ ] **D8** 🔴 `docs/roadmap.md` §14 — tick trạng thái Issue #10, ghi ngày nộp thực tế thay vì "23:59 ngày quy định".
- [ ] **D9** 🔴 `scripts/build_progress_report.py` — mở rộng phạm vi sinh báo cáo tiến độ từ `M1_M2`
      sang `M1_M3`, sinh `docs/bao_cao_tiendo_M1_M3.docx`. Hiện tên file cứng `bao_cao_tien_do_M1_M2.docx`
      và nội dung chỉ đọc trạng thái M1–M2.
      ⚠️ Lưu ý: `.docx` **không tái lập được theo byte** (`python-docx` ghi timestamp vào `docProps/core.xml`)
      → sinh lại rồi commit thẳng, không dùng `git diff` để kết luận (README:260 đã ghi nhận).
- [ ] **D10** ⚪ `README.md` §7 — kiểm tra tuyên bố AI còn khớp thực tế sau khi dùng AI viết
      notebook #4–#7 và tài liệu M3–M5.

### 1B.3 — Sau Phase 5–7 (M4)

- [ ] **D11** 🔴 `docs/inference_results.md` — bảng đầy đủ bộ bốn (thống kê kiểm định · p-value thô + hiệu chỉnh ·
      `$r_{rb}$` · Bootstrap CI 95%) cho cả 3 kiểm định, kèm diễn giải **không nhân quả**.
      Roadmap cũ (`ROADMAP_INFO3020…:713`) đã từng quy định tên file này → giữ đúng tên.
- [ ] **D12** 🔴 `docs/regression_findings.md` — bảng tham số OLS/Ridge/Lasso, kết quả 4 giả định LINE,
      VIF, Cook's Distance, Adjusted `$R^2`, và **bảng đối chiếu Train/Test**.
      Phải ghi rõ: nếu LINE bị vi phạm thì **giới hạn** kết luận thay vì báo cáo `$R^2` trần.
- [ ] **D13** 🔴 `docs/classification_findings.md` — Confusion Matrix, Precision/Recall/F1/PR-AUC/ROC-AUC
      trên Test với ngưỡng đã chốt, **kèm prevalence của tập để mọi tỷ lệ có mẫu số**; kết quả
      feature importance; nêu rõ cách xử lý đa cộng tuyến `pm25`/`pm10`.
- [ ] **D14** 🔴 `docs/leakage_audit.md` — biên bản kiểm toán 4 dạng rò rỉ (Target · Train-Test contamination ·
      Temporal · Group), mỗi mục kèm **bằng chứng kiểm chứng** chứ không chỉ khẳng định.
- [ ] **D15** 🔴 `docs/roadmap.md` §14 — tick Issue #11, #12, #13; sửa cây thư mục cho khớp tên notebook mới.

### 1B.4 — Sau Phase 8 (M5)

- [ ] **D16** 🔴 `docs/resource_measurement.md` — bảng đo tài nguyên (đĩa / RAM / I/O / runtime) trước và sau
      tối ưu, định vị 5V, đối chiếu ngưỡng `<10 GB` / `10–100 GB` / `>100 GB`, và **kết luận về Spark chỉ
      dẫn xuất từ số liệu này**.
- [ ] **D17** 🔴 `docs/bias_assessment.md` — 4 giả thuyết định kiến (Sensor · Spatial · Survivorship/missingness
      · `NaN` vs `0.0`), mỗi cái kèm cách kiểm chứng và mức độ bằng chứng.
- [ ] **D18** 🔴 `docs/datasheet.md` — 1 trang theo khung Timnit Gebru. **Bắt buộc kèm đoạn văn giải thích
      lý do loại trừ** k-anonymity · Fairness–Accuracy Trade-off · Anonymisation vs Pseudonymisation
      (task 1.24). Thiếu đoạn này thì GV hỏi "sao không làm?" mà không có câu trả lời.
- [ ] **D19** 🔴 `docs/model_card.md` — 1 trang: hiệu năng phân tầng, giới hạn, điều kiện sử dụng.
- [ ] **D20** 🔴 `docs/project_charter.md` — theo biểu mẫu GV (nộp trước deadline; xem task 0.4).
- [ ] **D21** ⚪ `docs/source_profiling.md` chỉ 1,5 KB — có vẻ là file rỗng/khung. Kiểm tra xem còn giá trị
      hay nên gộp vào `source_profiling_decision.md` (73,5 KB) để tránh hai nguồn sự thật.

### 1B.5 — Sau Phase 9–10 (M5–M6)

- [ ] **D22** 🔴 `docs/mentoring_feedback.md` — bảng: nội dung góp ý · hành động kỹ thuật đã thực hiện ·
      bằng chứng kiểm chứng (file + dòng + test).
- [ ] **D23** 🔴 `docs/viva_qa_prep.md` — **15 câu**, kèm câu trả lời mẫu. Bắt buộc phủ 5 nhóm:
      cơ sở chọn phép kiểm (task 1.3) · chẩn đoán LINE · lý do chọn mục tiêu tối ưu ngưỡng ·
      rò rỉ dữ liệu · đạo đức dữ liệu. Thêm câu hỏi cho **9 khoảng trống slide đã biết** (1.1–1.9)
      vì đó là các lỗ hổng đã được nhận diện sẵn — nếu không chuẩn bị thì chắc chắn bị hỏi.
- [ ] **D24** ⚪ `README.md` — thêm mục "Kết quả chính" tóm tắt 5 phát hiện mấu chốt + link tới
      `reports/final_report.pdf`. README hiện 30,9 KB nhưng toàn bộ là mô tả quy trình.

### 1B.6 — Trước khi nộp (M6)

- [ ] **D25** 🔴 Kiểm tra tính hợp lệ **toàn bộ liên kết nội bộ** trong tất cả docs (Issue #17 Task 2 liệt kê
      8 file, nhưng sau M3–M6 repo sẽ có **~18 file .md** trong `docs/` — danh sách phải cập nhật).
- [ ] **D26** ⚪ Đồng bộ số liệu xuyên suốt: cùng một con số phải xuất hiện giống nhau ở README, roadmap,
      notebook và báo cáo. Dùng script đọc Parquet để sinh số liệu thay vì gõ tay.
- [ ] **D27** ⚪ `docs/ROADMAP_INFO3020_Air_Pollution.md` (90,6 KB) đã bị thay thế một phần — cân nhắc
      ghi rõ ở đầu file "tài liệu tham chiếu lịch sử, không dùng làm nguồn chuẩn" để tránh nhầm lẫn.

### 1B.7 — Vấn đề kỹ thuật về `.gitignore`

- [ ] **D28** 🔴 **Quyết định tracking cho artifact M3–M6.** `.gitignore` hiện **không có mục nào** cho
      `reports/` hay `figures/` (grep rỗng). Đây là câu hỏi bắt buộc trả lời, không phải tuỳ chọn:

      | Artifact | Nên track? | Lý do |
      |---|---|---|
      | `figures/FIG-01…07.png` | ✅ **CÓ** | Là bằng chứng chấm điểm (20% rubric). Hội đồng cần mở repo xem được. 7 file 300 DPI ≈ 2–4 MB — chấp nhận được. |
      | `figures/*_diagnostics.png`, `feature_importance.png` | ✅ **CÓ** | Cùng lý do, và là bằng chứng chẩn đoán LINE. |
      | `reports/statistical_profile.csv` | ✅ **CÓ** | Nhỏ, là deliverable trực tiếp của #8. |
      | `reports/*.pdf` | ⚠️ **tùy** | `midterm_report.pdf` / `final_report.pdf` nên commit vì là bài nộp — nhưng nếu nặng thì link release. |
      | `reports/*_minutes.md` | ✅ **CÓ** | Biên bản bảo vệ là artifact học thuật. |
      | `docs/*.docx` | ⚠️ **tùy** | Đã commit `bao_cao_tien_do_M1_M2.docx`. Nhất quán thì giữ, nhưng nhớ giới hạn byte-tái-lập ở D9. |
- [ ] **D29** ⚪ Nếu chọn **không** track `reports/` hoặc `figures/` → phải ghi rõ trong `README.md` và
      `docs/data_dictionary.md` cách tái tạo (vì policy dữ liệu 3 tầng của roadmap chỉ áp dụng cho `data/`,
      không áp dụng cho artifact phân tích).

---

## Phase 2 — Issue #8: Thống kê mô tả & chu kỳ thời gian (~1–2 buổi)

Input: `data/processed/air_pollution_final.parquet` (9.044 dòng × 18 cột, gitignored).

- [ ] **2.1** ⚪ Khôi phục pipeline nếu cần: chạy `00` → `01` → `02` → `03_transformation_pipeline`.
      `03_data_cleaning` cần `data/interim/` ở trạng thái **trước** làm sạch.
- [ ] **2.2** 🟡 Cấu hình font tiếng Việt **một lần, có kiểm chứng tự động** — đặt trong notebook `04` và
      `src/visualizer.py`. `DejaVu Sans` (mặc định Matplotlib) **không** render được dấu tiếng Việt.
      Máy đã có: `Segoe UI`, `Arial`, `Calibri`, `Tahoma`, `Verdana`.
      Kiểm chứng bằng script đọc `artist.get_text()` và assert không có `\ufffd`/ô vuông — **không kiểm bằng mắt**.
- [ ] **2.3** Tính 4 họ chỉ số cho `pm25` + tất cả biến khí tượng: Mean/Median/Mode; Variance/Std/IQR/Range;
      Skewness/Kurtosis; P10/P25/P50/P75/P90/P95/P99. Mỗi dòng kèm `n` và `n_missing`.
- [ ] **2.4** Biện luận Mean vs Median dựa trên phân phối thực nghiệm (slide W6: "Shape picks the statistic").
- [ ] **2.5** Biến thiên theo 24 khung giờ — **không áp đặt trước** khung đỉnh/đáy.
- [ ] **2.6** Phân phối theo ngày trong tuần (weekday vs weekend) và theo tháng/mùa trong dải dữ liệu thực tế.
- [ ] **2.7** Trung bình trượt 24h và 7d; kiểm chứng **không gây dịch pha thời gian** (`center=False` hay
      ghi rõ phương pháp). `seasonal_decompose` chỉ dùng nếu chuỗi đều đặn + có chu kỳ liên tục.
- [ ] **2.8** Ma trận tương quan kép Pearson + Spearman, kèm scatter plot kiểm chứng quan hệ phi tuyến.
- [ ] **2.9** 🟡 Xử lý tương tác `fog × mùa` theo addendum của Issue #8: kiểm tra tương tác cho **mọi cờ
      chẩn đoán**; nếu dùng thì dùng dạng tương tác, không dùng cờ trần (marginal `corr(pm25, RH) = −0,0365` rất
      dễ gây kết luận sai). Ghi rõ `pm25_was_stuck` là hằng số 0 → không phân biệt thông tin.
- [ ] **2.10** 🟡 Kiểm tra VIF sớm cho cặp `pm25`/`pm10` (`r = 0,9727`) để chuẩn bị cho #12–#13.
- [ ] **2.11** Xuất `reports/statistical_profile.csv` — khớp **chính xác** với kết quả trong notebook.
- [ ] **2.12** Phân định rõ 3 tầng: mô tả / sinh giả thuyết / suy luận (suy luận → #11).
- [ ] **2.13** ⚪ `reports/statistical_profile.csv` chưa được `.gitignore` — kiểm tra trước khi commit.

**Deliverable:** `notebooks/04_descriptive_stats.ipynb`, `reports/statistical_profile.csv`

---

## Phase 3 — Issue #9: 7 biểu đồ ấn phẩm (~2 buổi)

- [ ] **3.1** Tạo `src/visualizer.py` — Matplotlib OO API (`fig, ax = plt.subplots()`), bỏ spines top/right,
      làm mờ lưới phụ, chuẩn hóa nhãn trục + đơn vị đo, bảng màu `viridis`/`colorblind`, hàm có tham số hoá.
      Bao gồm cấu hình font tiếng Việt (task 2.2).
- [ ] **3.2** ⚪ Tạo `tests/test_visualizer.py` — mọi module `src/` hiện có đều có test; `visualizer.py` là
      module đầu tiên không có. Test tối thiểu: mỗi hàm trả về `Figure`, DPI = 300, không có ô vuông
      trong text, `bar chart` ylim bắt đầu từ 0.
- [ ] **3.3** FIG-01 — Line chart + trượt 24h & 7d, ngưỡng QCVN 24h **chỉ vẽ trên chuỗi trượt 24h**.
- [ ] **3.4** FIG-02 — Histogram + KDE, hình dạng phân phối thực nghiệm của `pm25`.
- [ ] **3.5** FIG-03 — Boxplot `pm25` theo tháng/mùa trong chuỗi quan sát thực tế.
- [ ] **3.6** FIG-04 — 2D heatmap giờ trong ngày × thứ trong tuần.
- [ ] **3.7** FIG-05 — Scatter biến khí tượng vs `pm25` + LOWESS.
- [ ] **3.8** FIG-06 — Correlation heatmap chất ô nhiễm × biến khí tượng.
- [ ] **3.9** FIG-07 — Bar chart phân bố tần suất theo mức chất lượng không khí, **trục tung từ 0**,
      phân loại bằng chỉ số có chu kỳ lấy mẫu tương thích toán học.
- [ ] **3.10** 100% tiêu đề là **Takeaway Conclusion dẫn xuất từ kết quả #8** — không hard-code trước khi có số.
- [ ] **3.11** Mỗi đường ngưỡng phải ghi rõ: chất ô nhiễm · chu kỳ lấy mẫu · văn bản + phiên bản · đại lượng
      toán học tương thích. Không gộp chung QCVN và WHO thành "quy chuẩn" chung chung.
- [ ] **3.12** Xuất 7 PNG, 300 DPI, `figures/FIG-01.png` … `FIG-07.png`.
- [ ] **3.13** ⚪ Mở từng file PNG và **kiểm tra bằng mắt** lần cuối (tiếng Việt, không tràn nhãn, ngưỡng đúng
      chuỳ) — bước tự động không thay thế được bước này.

**Deliverable:** `src/visualizer.py`, `figures/FIG-01…07.png`, `tests/test_visualizer.py`

---

## Phase 4 — Issue #10: Báo cáo giữa kỳ (~1 buổi)

- [ ] **4.1** Soạn `reports/midterm_report.pdf` — 8–10 trang, đủ 7 phần: đặt vấn đề & câu hỏi nghiên cứu ·
      nguồn dữ liệu & giấy phép · kiểm toán 6 chiều & mẫu hình khuyết thiếu (nêu rõ bất định) ·
      quy trình làm sạch tất định & trích lược Cleaning Log · hồ sơ 4 họ chỉ số ·
      FIG-01→FIG-05 lồng ghép SCQA · ý nghĩa thực tiến ban đầu.
- [ ] **4.2** Slide thuyết trình 8–10 slide theo SCQA, chuẩn bị trình bày **7 phút**.
- [ ] **4.3** Chuẩn bị câu trả lời phản biện kỹ thuật (Viva 3 phút). Câu hỏi chắc chắn: thống kê mô tả
      dựa trên bao nhiêu dòng (task 1.10) · vì sao thiếu 2023–2024 · vì sao không dùng `pm10`.
- [ ] **4.4** ⚪ Xác định rõ **3 file `03_`** và thứ tự chạy. Lệnh glob `notebooks/03_*.ipynb` hiện sẽ nuốt cả
      `03_processed_data_preview.ipynb`.
- [ ] **4.5** Kiểm chứng tái lập tự động: `jupyter nbconvert --to notebook --execute notebooks/00_*.ipynb
      notebooks/01_*.ipynb notebooks/02_*.ipynb notebooks/03_*.ipynb notebooks/04_*.ipynb` — Restart Kernel
      & Run All 100% không lỗi.
- [ ] **4.6** ⚪ Kiểm tra 7 PNG tồn tại, đúng 300 DPI, tiêu đề lấy từ kết quả #8 (roadmap `:1075` yêu cầu
      **điều kiện thời gian**: phải chạy #8 trước, không hard-code tiêu đề).
- [ ] **4.7** Cập nhật `README.md` §2 (trạng thái triển khai) và trạng thái issue #7 "chưa merge" nếu đã merge.
- [ ] **4.8** Tạo & đẩy git tag `midterm-submission`.

---

## Phase 5 — Issue #11: Suy luận thống kê (~1–2 buổi)

- [ ] **5.1** Kiểm định 1 — `pm25` giữa 2 mùa: Shapiro-Wilk trước, Mann-Whitney U sau nếu vi phạm chuẩn.
- [ ] **5.2** Tính `$r_{rb} = 1 − 2U/(n_1n_2)` + Bootstrap CI 95% cho chênh lệch trung vị
      (1.000 lặp, `np.random.seed(42)`).
- [ ] **5.3** 🔴 Hiệu chỉnh multiple testing cho **toàn bộ** các kiểm định trong notebook (task 1.1).
- [ ] **5.4** Kiểm định 2 — weekday vs weekend, Mann-Whitney U; biện luận khoảng cách giữa ý nghĩa thống kê
      và ý nghĩa thực tiện.
- [ ] **5.5** Kiểm định 3 — đối chiếu `pm25` với QCVN 05:2023/BTNMT bằng phép phi tham số trên chuỗi
      **tương thích toán học** về chu kỳ lấy mẫu; báo cáo 95% CI.
- [ ] **5.6** 🔴 Bảng kết quả: **100% kết luận** trình bày đủ bộ bốn — thống kê kiểm định, p-value (thô + đã
      hiệu chỉnh), effect size `$r_{rb}$`, Bootstrap CI 95%. Tuyệt đối không báo cáo p-value đơn độc.
- [ ] **5.7** 🔴 Giải thích p-value theo đúng 4 sai lầm kinhiển (task 1.3); nêu Power = 1 − β trong ngữ cảnh
      cảnh báo sớm.
- [ ] **5.8** ⚪ Base rate fallacy: diễn giải mọi tỷ lệ khớp quy chuẩn qua prior probability (task 1.2).
- [ ] **5.9** Tạo `notebooks/05_statistical_inference.ipynb` + bảng tổng hợp kết quả kiểm định.

**Deliverable:** `notebooks/05_statistical_inference.ipynb`, bảng kết quả kiểm định

---

## Phase 6 — Issue #12: Hồi quy OLS (~2 buổi)

- [ ] **6.1** Kế thừa điểm cắt Train/Test từ #7 (`2026-01-15 00:00:00+07:00`), giữ Test cho đánh giá độc lập.
- [ ] **6.2** Khảo sát `$Y = \log(1 + pm25)$ trên Train; kiểm chứng qua chẩn đoán sau khớp.
- [ ] **6.3** Dummy Regressor baseline + OLS (`statsmodels.api.OLS`).
- [ ] **6.4** Chẩn đoán đủ 4 giả định LINE: Residuals vs Fitted · Durbin-Watson + ACF · Q-Q + Shapiro-Wilk ·
      Breusch-Pagan + Scale-Location.
- [ ] **6.5** VIF (ngưỡng > 5.0) + Cook's Distance. Xử lý `pm10` theo phát hiện của #8 (task 2.10).
- [ ] **6.6** Ridge/Lasso, tune `α` **hoàn toàn trên Train** (Time-Series Split). Không dùng Test để tune.
- [ ] **6.7** Đánh giá trên **Test độc lập**: MAE, RMSE, `$R^2`, **Adjusted `$R^2$** so với baseline.
- [ ] **6.8** 🔴 Diễn giải hệ số theo 3 nghĩa vụ: *liên hệ với* (không "gây ra") · *ceteris paribus* ·
      *giới hạn trong miền giá trị quan sát*. Không ngoại suy.
- [ ] **6.9** Tạo `notebooks/06_regression_modeling.ipynb` + `figures/regression_line_diagnostics.png` +
      bảng tham số.

**Deliverable:** `notebooks/06_regression_modeling.ipynb`, `figures/regression_line_diagnostics.png`, bảng tham số

---

## Phase 7 — Issue #13: Phân loại cảnh báo (~2 buổi)

- [ ] **7.1** Định nghĩa nhãn nhị phân tương thích toán học về chu kỳ (vd trung bình 24h `pm25 ≥ 50 µg/m³`);
      đo tỷ lệ mất cân bằng thực tế (3,08% Train vs 6,89% Test — **phải nêu mẫu số, dùng cùng mẫu số**).
- [ ] **7.2** Đặc trưng trễ & trượt từ quá khứ: `pm25_rolling_mean_24h`, `pm25_rolling_std_24h`, `pm25_lag24`,
      nhiệt-ẩm, cờ lặng gió, sin/cos giờ & tháng. Xác nhận không truy xuất thông tin tương lai.
- [ ] **7.3** 🔴 Xử lý đa cộng tuyến `pm25`/`pm10` **trước khi** huấn luyện (task 1.5) — hoặc loại `pm10`,
      hoặc tuyên bố rõ cách xử lý.
- [ ] **7.4** DummyClassifier baseline + Logistic Regression (`class_weight='balanced'`) + Random Forest.
- [ ] **7.5** PR Curve + PR-AUC, **đối chiếu với baseline = prevalence** (task 1.6).
- [ ] **7.6** Threshold tuning trên Train/Val theo mục tiêu vận hành (maximize `$F_\beta$` với `β > 1`, hoặc
      maximize Recall dưới ràng buộc Precision tối thiểu). **Tuyệt đối không tune trên Test.**
- [ ] **7.7** Đánh giá trên **Test** với ngưỡng đã chốt: Recall, Precision, F1/F-beta, PR-AUC, ROC-AUC,
      Confusion Matrix. Dùng **cùng mẫu số** cho Train và Test.
- [ ] **7.8** 🔴 Biên bản audit đủ 4 dạng rò rỉ: Target · Train-Test contamination · Temporal · Group.
      Phủ cả trường hợp SMOTE (nói rõ lý do không dùng) (task 1.22).
- [ ] **7.9** 🔴 Feature importance: `feature_importances_` + `permutation_importance` trên **tập Test**
      → `figures/feature_importance.png` (task 1.9). Không dùng SHAP — xem task 0.5.
- [ ] **7.10** ⚠️ Nếu điểm bất thường > 99% → dừng, kiểm tra rò rỉ (slide W11 takeaway #4).
- [ ] **7.11** Tạo `notebooks/07_classification_alerts.ipynb` (tên mới sau task 0.3) +
      `figures/precision_recall_curve.png`.

**Deliverable:** `notebooks/07_classification_alerts.ipynb`, `figures/precision_recall_curve.png`, biên bản audit rò rỉ

---

## Phase 8 — Issue #14: Đạo đức, quy mô, datasheet (~1 buổi)

- [ ] **8.1** Đo tài nguyên: dung lượng đĩa (Parquet vs CSV), RAM khi nạp DataFrame, thông lượng I/O,
      thời gian tiền xử lý + huấn luyện.
- [ ] **8.2** 🔴 Đo **lần 2** sau khi áp dụng ≥2 tối ưu (float64→float32/category, Parquet compression,
      đổi vòng lặp `for` sang vectorization). So sánh trước–sau (task 1.7).
- [ ] **8.3** 🔴 Định vị dataset vào mô hình 5V và đối chiếu ngưỡng `<10 GB` / `10–100 GB` / `>100 GB`;
      lập bảng Scale Up vs Scale Out (task 1.8).
- [ ] **8.4** 🔴 **Kết luận về Spark chỉ được rút ra từ số liệu đo** ở 8.1–8.3. Tuyệt đối không khẳng định
      định kiến trước khi có số (roadmap `:41`).
- [ ] **8.5** Khảo sát 4 giả thuyết định kiến: Sensor (RH > 90%) · Spatial (đại diện mạng lưới trạm HN) ·
      Survivorship/missingness liên quan thời tiết · phân định rõ `NaN` vs `0.0`.
- [ ] **8.6** Soạn `docs/datasheet.md` (1 trang) theo khung Timnit Gebru — **kèm đoạn văn giải thích lý do
      loại trừ k-anonymity / Fairness–Accuracy / Anonymisation** (task 1.24).
- [ ] **8.7** Soạn `docs/model_card.md` (1 trang): hiệu năng phân tầng + giới hạn mô hình.
- [ ] **8.8** ⚪ Cập nhật tuyên bố minh bạch AI trong `README.md` (đã có §7 — kiểm tra còn khớp thực tế sau M3–M4).
- [ ] **8.9** Soạn `docs/project_charter.md`.

**Deliverable:** báo cáo đo đạc tài nguyên, `docs/datasheet.md`, `docs/model_card.md`, `docs/project_charter.md`

---

## Phase 9 — Issue #15: Module hoá & độ nhạy (~1 buổi)

> Issue đầy đủ nhất sau M2 — không tìm thấy khoảng trống so với slide.

- [ ] **9.1** Tạo `src/data_loader.py` (nạp dữ liệu, kiểm tra schema, Parquet I/O).
- [ ] **9.2** Bổ sung docstrings, type hints, bọc xử lý ngoại lệ theo PEP 8.
- [ ] **9.3** Kiểm tra import độc lập, không phụ thuộc vòng tròn.
- [ ] **9.4** Phân tích độ nhạy ngưỡng 40 / 45 / 50 / 55 µg/m³ — **dán nhãn là kịch bản kỹ thuật, không đồng nhất
      với ngưỡng pháp lý** khi chưa có cùng chu kỳ tính toán và văn bản quy định.
- [ ] **9.5** Khảo sát độ nhạy hệ số hồi quy khi đổi cửa sổ trễ và trung bình trượt.
- [ ] **9.6** Dọn chuỗi notebooks: xoá cell debug, sắp xếp lại ô mã + markdown tuần tự mạch lạc.
- [ ] **9.7** Soạn `docs/mentoring_feedback.md`: bảng đối chiếu nội dung góp ý · hành động kỹ thuật đã thực
      hiện · bằng chứng kiểm chứng.

**Deliverable:** `src/data_loader.py`, `docs/mentoring_feedback.md`, kết quả phân tích độ nhạy

---

## Phase 10 — Issue #16: Báo cáo cuối kỳ (~1–2 buổi)

> Cũng đầy đủ so với slide.

- [ ] **10.1** Soạn `reports/final_report.pdf` theo SCQA chặt chẽ: S (bối cảnh + đặc tính chuỗi đã đóng băng) ·
      C (biến cố từ bằng chứng thực tế, **không gán nguyên nhân giả định**) · Q (Main RQ + 4 SQ) ·
      A (chứng cứ định lượng từ 4 họ chỉ số, kiểm định bộ bốn, OLS + báo cáo trung thực LINE,
      hiệu năng phân loại trên Test, kết quả đo đạc tài nguyên, khuyến nghị chính sách).
- [ ] **10.2** Nhúng **toàn bộ** FIG-01→FIG-07 + các đồ thị chẩn đoán vào báo cáo.
- [ ] **10.3** Slide bảo vệ 12–15 slide, chuẩn hoá 10–12 phút.
- [ ] **10.4** Soạn `docs/viva_qa_prep.md`: 15 câu trọng tâm kèm câu trả lời mẫu — cơ sở chọn phép kiểm ·
      chẩn đoán LINE · lý do chọn mục tiêu tối ưu ngưỡng · rò rỉ dữ liệu · đạo đức dữ liệu.
      Bổ sung câu hỏi cho các task 1.1–1.9 vì đó là các lỗ hổng đã biết.

**Deliverable:** `reports/final_report.pdf`, slide bảo vệ, `docs/viva_qa_prep.md`

---

## Phase 11 — Issue #17: Audit & bảo vệ (~1 buổi)

- [ ] **11.1** Audit cây thư mục CRISP-DM + file bắt buộc (`README.md`, `requirements.txt`, `LICENSE`, `.gitignore`,
      `data/raw/metadata.json`).
- [ ] **11.2** Kiểm tra tính hợp lệ của toàn bộ liên kết nội bộ trong 8 docs.
- [ ] **11.3** Xác thực SHA-256 trong `data/raw/metadata.json`, Parquet hợp lệ trong `data/processed/`,
      không rò rỉ Train/Test.
- [ ] **11.4** Chạy tuần tự `00_environment_test.ipynb` → `07_classification_alerts.ipynb` trong môi trường
      sạch — **tên file sau task 0.3**. 100% không unhandled exception.
- [ ] **11.5** Chuẩn bị `reports/defense_minutes.md`.
- [ ] **11.6** Commit hoàn thiện + đẩy git tag `final-defense-submission`.
- [ ] **11.7** Bảo vệ đồ án + trả lời phản biện cá nhân.

---

## Appendix — Bản đồ khái niệm slide ↔ issue

| Slide | Khái niệm bắt buộc | Issue | Task |
|---|---|---|---|
| W6 | 4 họ chỉ số, Shape picks the statistic | #8 | 2.3–2.4 |
| W6 | CLT, SE = σ/√n, 68–95–99.7 | #8 | 1.13 🟡 |
| W6 | Mean>Median>Mode | #8 | 1.12 🟡 |
| W6 | Pearson vs Spearman, r≈0 cảnh báo | #8 | 2.8 |
| W6 | Nghịch lý Simpson | #8 | 2.9 ✅ |
| W6 | Confounder, Spurious correlation | #8 | 1.14 🟡 |
| W6 | **Base Rate Fallacy** | #11, #13 | 1.2 🔴 |
| W7 | OO API, Data-Ink, spines, lưới | #9 | 3.1 |
| W7 | Bar từ 0, không pie/3D | #9 | 3.9 |
| W7 | Bảng màu `viridis`/`colorblind` | #9 | 3.1 |
| W7 | Takeaway titles 100% | #9 | 3.10 |
| W7 | **Thang đo → loại biểu đồ** | #9 | 1.15 🟡 |
| W7 | **Cleveland–McGill perceptual hierarchy** | #9 | 1.16 🟡 |
| W7 | **5 cách bóp méo (3 cách còn lại)** | #9 | 1.17 🟡 |
| W7 | SCQA | #10, #16 | 4.1, 10.1 |
| W9 | Shapiro → Mann-Whitney | #11 | 5.1 |
| W9 | Effect size, Bootstrap CI | #11 | 5.2 |
| W9 | **Bộ bốn bắt buộc** | #11 | 5.6 🔴 |
| W9 | **Multiple Testing / Bonferroni** | #11 | 1.1 🔴 |
| W9 | **4 sai lầm p-value, CI, Type I/II, Power** | #11 | 1.3 🔴 |
| W10 | 4 giả định LINE (đủ) | #12 | 6.4 |
| W10 | VIF, Cook's Distance | #12 | 6.5 |
| W10 | Ridge/Lasso tune trên Train | #12 | 6.6 |
| W10 | 3 nghĩa vụ diễn giải hệ số | #12 | 6.8 |
| W10 | **Adjusted R²** | #12 | 1.4 🔴 |
| W10 | Outlier vs Leverage vs Influence | #12 | 1.19 🟡 |
| W10 | MAE vs RMSE theo ngữ cảnh | #12 | 1.20 🟡 |
| W10 | Chuẩn hoá trước Ridge/Lasso | #12 | 1.21 🟡 |
| W11 | Logistic + Random Forest | #13 | 7.4 |
| W11 | DummyClassifier baseline | #13 | 7.4 |
| W11 | Confusion Matrix, P/R/F1 | #13 | 7.7 |
| W11 | PR-Curve thay ROC | #13 | 7.5 |
| W11 | Threshold tuning | #13 | 7.6 |
| W11 | 4 dạng rò rỉ dữ liệu | #13 | 7.8 |
| W11 | Feature Engineering từ timestamp | #13 | 7.2 |
| W11 | **Feature Selection** | #13 | 1.5 🔴 |
| W11 | **PR-AUC vs prevalence** | #13 | 1.6 🔴 |
| W12 | 4 giả thuyết bias | #14 | 8.5 |
| W12 | Datasheet + Model Card | #14 | 8.6–8.7 |
| W12 | **5V + ngưỡng GB + Scale Up/Out** | #14 | 1.8 🔴 |
| W12 | **"Tối ưu trước, kết luận sau"** | #14 | 1.7 🔴 |
| W12 | **Explainability (feature importance)** | #14 | 1.9 🔴 |
| W12 | Anonym. vs Pseudonym., k-anonymity | #14 | 1.24 ⚪ (loại có lý do) |
| W12 | Fairness–Accuracy Trade-off | #14 | 1.24 ⚪ (loại có lý do) |
| W12 | HDFS, Lazy Evaluation, OOM/Data Skew | #14 | 🟡 mức ôn thi |

---

## Phụ lục 2 — Task cập nhật tài liệu (Phase 1B)

| Nhóm | Task | Tài liệu bị tác động | Khi nào |
|---|---|---|---|
| 1B.1 | D1–D2 | `docs/roadmap.md`, `README.md` §2 | Sau M3 |
| 1B.1 | D3–D4 | `README.md`, `docs/data_dictionary.md` | Sau M3 |
| 1B.1 | **D5** | **tạo mới `docs/descriptive_findings.md`** | Sau #8 — **chặn báo cáo giữa kỳ** |
| 1B.1 | D6–D7 | `docs/descriptive_findings.md`, `AGENTS.md` | Sau M3 |
| 1B.2 | D8 | `docs/roadmap.md` §14 | Sau #10 |
| 1B.2 | **D9** | **`scripts/build_progress_report.py`** → `bao_cao_tien_do_M1_M3.docx` | Sau #10 |
| 1B.3 | **D11** | **tạo mới `docs/inference_results.md`** | Sau #11 |
| 1B.3 | **D12** | **tạo mới `docs/regression_findings.md`** | Sau #12 |
| 1B.3 | **D13** | **tạo mới `docs/classification_findings.md`** | Sau #13 |
| 1B.3 | **D14** | **tạo mới `docs/leakage_audit.md`** | Sau #13 |
| 1B.4 | **D16** | **tạo mới `docs/resource_measurement.md`** | Sau #14 |
| 1B.4 | **D17** | **tạo mới `docs/bias_assessment.md`** | Sau #14 |
| 1B.4 | D18–D20 | `docs/datasheet.md`, `docs/model_card.md`, `docs/project_charter.md` | Sau #14 |
| 1B.4 | D21 | `docs/source_profiling.md` (1,5 KB — có vẻ là khung rỗng) | Rà soát |
| 1B.5 | D22–D24 | `docs/mentoring_feedback.md`, `docs/viva_qa_prep.md`, `README.md` | Sau #15–16 |
| 1B.6 | D25–D27 | Toàn bộ docs; `docs/ROADMAP_INFO3020…` | Trước #17 |
| 1B.7 | **D28–D29** | **`.gitignore`** — quyết định tracking cho `figures/` + `reports/` | **Trước M3** |

### Quy tắc bất di bất dịch cho tài liệu

1. **Không gõ tay số liệu.** Mọi con số trong docs phải truy được về một ô notebook hoặc một script.
   Nếu không tái tạo được từ Parquet → số đó không được viết ra.
2. **Docs là bằng chứng, không phải phần phụ.** Issue #11–#14 hiện ghi Deliverable là "bảng kết quả" /
   "bảng tham số" — nhưng một bảng rời rạc không ai đọc được ý nghĩa. Task D11–D17 yêu cầu **văn bản kèm bảng**.
3. **Mỗi số liệu phải kèm mẫu số.** Đặc biệt các tỷ lệ phân loại — xem task 1.2.
4. **Không đổi số liệu qua các phase khác nhau.** Đây là nguyên nhân phổ biến nhất khiến báo cáo cuối kỳ
   mâu thuẫn báo cáo giữa kỳ. Task D26 kiểm tra việc này.

---

## Phụ lục 3 — Việc phát sinh ngoài scope: đã xử lý

Ba việc này không thuộc M3–M6 nhưng phát sinh khi rà soát repo. Đã xử lý trong phiên làm việc 2026-10-07:

| # | Vấn đề | Xử lý | Trạng thái |
|---|---|---|---|
| 1 | `git status` hiện `?? .opencode/agents/` + `?? .opencode/opencode.json` (10 file, ~48 KB) chưa track | Thêm vào `.gitignore`: `.opencode/agents/`, `.opencode/command/`, `.opencode/opencode.json`. **Không ignore `.opencode/skills/`** — xem bảng bên dưới. `git rm --cached .opencode/command/ocr-review.md` để dọn nốt phần đã track. | ✅ xong |
| 2 | `notebooks/03_processed_data_preview.ipynb` không có issue nào sở hữu | **Giữ lại** — notebook 35 ô có giá trị kiểm tra thật (assert schema, kiểm tra cleaning, thông tin split). Đã đăng ký vào cây `notebooks/` của roadmap §12. Thay đổi cục bộ trên file là churn định dạng thuần → không commit. Còn lại: xác nhận thứ tự `nbconvert` (task 4.4). | ✅ xong |
| 3 | `requirements.txt` thiếu `shap` cho task Explainability | **Không thêm.** `feature_importances_` + `permutation_importance` của scikit-learn (đã có sẵn) cho cùng thông tin. Thêm `shap` chỉ để lấy dữ liệu tương đương là YAGNI. Task 0.5 + 1.9 + 7.9 đã cập nhật. | ✅ xong |

### Vì sao `.opencode/skills/` phải ở lại trong repo

`.githooks/pre-commit` là file **đã track**, và dòng 41 của nó nạp skill:

```
Load the open-code-review-delegate skill, run 'ocr delegate rule --format json <those paths>'
```

Skill đó nằm ở `.opencode/skills/open-code-review-delegate/SKILL.md`. Nếu gỡ track, một fresh clone sẽ có
hook nhưng không có skill → review **im lặng suy giảm** thay vì báo lỗi. `.gitattributes` còn pin
`.githooks/**` về LF chính vì hook chạy bằng `sh` — cho thấy hook được coi là thành phần bàn giao thật.

Phân tách cuối cùng:

| Đường dẫn | Quyết định | Lý do |
|---|---|---|
| `.opencode/skills/open-code-review-delegate/SKILL.md` | ✅ **track** | Phụ thuộc cứng của `.githooks/pre-commit:41` |
| `.opencode/command/ocr-review.md` | 🚫 bỏ track | Lệnh tương tác, hook không dùng |
| `.opencode/agents/*.md` (8 file) | 🚫 ignore | Agent definitions viết tay cho repo này nhưng thuộc tầng công cụ, không phải bàn giao học thuật |
| `.opencode/opencode.json` | 🚫 ignore | Config cục bộ (`default_agent`, `subagent_depth`) |

### Kết quả kiểm chứng

```text
$ git ls-files .opencode
.opencode/skills/open-code-review-delegate/SKILL.md      ← chỉ còn đúng 1 file, hook còn dùng được

$ git check-ignore -v .opencode/opencode.json .opencode/agents/orchestrator.md .opencode/command/ocr-review.md
.gitignore:67:.opencode/opencode.json	.opencode/opencode.json
.gitignore:65:.opencode/agents/	.opencode/agents/orchestrator.md
.gitignore:66:.opencode/command/	.opencode/command/ocr-review.md

$ git check-ignore -v .opencode/skills/open-code-review-delegate/SKILL.md
exit=1                                                 ← KHÔNG bị ignore nhầm

$ python -c "import importlib.util as u; ..."
nbclient True · nbconvert True · nbformat True      ← task 0.6 xác nhận
shap False                                          ← nhưng không cần (task 0.5)
```
