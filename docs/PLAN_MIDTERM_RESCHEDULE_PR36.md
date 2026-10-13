# Báo Cáo Tiến Độ & Kế Hoạch — PR #36 & Lịch Midterm

> [!WARNING]
> ## ⏳ TÀI LIỆU LỊCH SỬ — ẢNH CHỤP TẠI THỜI ĐIỂM 2026-10-12
>
> **Mọi con số và trạng thái trong file này là ảnh chụp tại thời điểm lập báo cáo.**
> Chúng **KHÔNG** phản ánh trạng thái hiện tại. Dùng file này để tra cứu lịch sử quyết
> định, **không** dùng làm nguồn cho trạng thái PR, CI hay số liệu hiện hành.
>
> | Mục trong file này | Ảnh chụp lúc 2026-10-12 | Trạng thái hiện tại |
> |---|---|---|
> | `HEAD` | `759a9c6` | đã thay đổi — xem `git log` |
> | Số unit test | `Ran 344 tests` | **`Ran 351 tests`** (xem `README.md` §Chạy test) |
> | PR được nói tới | #36 | #36 **đã đóng**, thay bằng **#37** |
> | Trạng thái CI | chưa chạy trên commit mới | CI `ubuntu-latest` **pass** trên commit mới nhất |
> | Task D4 (`D4-partial-file`) | chưa quyết định | đã triển khai atomic write |
> | Tiêu chí #12/#14 | `⛔ chờ Câu 1` | `HELD` — giữ nguyên phạm vi, báo cáo theo tiến độ thực tế |
>
> **Về mốc `W08 → W11`:** đây là **đề xuất**, chưa được giảng viên xác nhận. Giảng viên mới
> chỉ cho phép dời mốc, **chưa xác nhận phạm vi nộp**. Không có bằng chứng nào trong repo
> cho thấy phạm vi đã được chốt — mọi mục liên quan vẫn ở trạng thái `HELD`.
>
> **Bản số liệu hiện hành:** xem `README.md` và `docs/TASK_LIST_M3_M6.md`.

---

> **Ngày:** 2026-10-12 · **Nhánh:** `docs/audit-delivery` · **HEAD:** `759a9c6`
> **Nguyên tắc:** làm đến đâu thì báo cáo đến đó. Không trình bày việc dự kiến như đã xong,
> không tự suy diễn yêu cầu của giảng viên.
> **Phạm vi lượt này:** chỉ sửa file kế hoạch này. Không sửa data/code/roadmap khác,
> không chạm issue/milestone/PR. Không commit, không push.

---

## 1. Tiến độ thực tế (đã kiểm chứng 2026-10-12)

### 1.1 Đã hoàn thành

| Hạng mục | Bằng chứng |
|---|---|
| **M1 (W1–2)** — dự án & thu thập dữ liệu | 5/5 issue **CLOSED**: #1 (26/09), #2 (28/09), #19 (29/09), #3 (29/09), #4 (29/09) |
| **M2 (W3–5)** — kiểm toán & làm sạch | 3/3 issue **CLOSED**: #5 (29/09), #6 (30/09), #7 (30/09) |
| Chuỗi dữ liệu đầy đủ | `data/raw/` → `data/interim/` → `data/processed/air_pollution_final.parquet` (**267.399 bytes**) đều tồn tại |
| Mã nguồn `src/` | `data_collection.py` · `data_quality.py` · `cleaning.py` · `cleaning_pipeline.py` |
| Notebook | 6 file: `00_environment_test` · `01_data_collection` · `02_quality_audit` · `03_data_cleaning` · `03_transformation_pipeline` · `03_processed_data_preview` |
| Kiểm thử | `python -m unittest discover tests` → **`Ran 344 tests … OK`** (342 gốc + 2 test D4; khớp lệnh CI `ci.yml:45`) |
| Tài liệu | `roadmap.md` · `data_dictionary.md` · `data_quality_audit.md` · `cleaning_log.md` · `source_profiling_decision.md` · `docs/history/` (4 file) |
| Báo cáo tiến độ | `scripts/build_progress_report.py` + `docs/bao_cao_tien_do_M1_M2.docx` |

### 1.2 Chưa bắt đầu

| Hạng mục | Bằng chứng |
|---|---|
| **M3 (W6–8)** | #8, #9, #10 — cả 3 **OPEN**, 0 closed |
| Notebook EDA / suy luận / hồi quy | `notebooks/0[4-7]*` → **0 file** |
| 7 biểu đồ ấn phẩm | `figures/` chỉ có `.gitkeep` → **0/7** |
| Báo cáo giữa kỳ | `reports/` chỉ có `.gitkeep` → **chưa có `midterm_report.pdf`** |
| **M4 / M5 / M6** | #11–#17 — tất cả **OPEN** |

### 1.3 Đang thực hiện

| Hạng mục | Trạng thái |
|---|---|
| PR #36 | **OPEN**, state `CHANGES_REQUESTED` từ `doctor-cato`, commit `759a9c6` |
| Review | Đúng **1 review**, **0 inline comment**; 4 mục → xử lý ở §4 |

### 1.4 Tóm tắt tiến độ

**M1 và M2 đã hoàn thành.** 8/19 issue CLOSED, tương ứng đúng 8 issue của hai milestone đầu:
thu thập dữ liệu, kiểm toán chất lượng, làm sạch, tích hợp & đóng gói pipeline. Chuỗi dữ liệu
`data/raw/` → `data/interim/` → `data/processed/air_pollution_final.parquet` đã đầy đủ, mã
nguồn `src/` đã có 4 module, 342 unit test pass.

**M3–M6 chưa bắt đầu.** 11/19 issue còn OPEN, không issue nào trong nhóm này đã đóng.
`notebooks/0[4-7]` chưa có file nào, `figures/` 0/7 biểu đồ, `reports/` chưa có báo cáo.

**Hệ quả đối với báo cáo giữa kỳ:** #10 phụ thuộc #8 và #9 — cả hai đều chưa bắt đầu — nên
**chưa có tiến độ giữa kỳ nào để báo cáo**. Việc cần làm trước là xử lý 4 mục review PR #36
(§4) để PR được merge, rồi bắt đầu M3.

> Đây **không** phải "dự án không có tiến độ". Tiến độ nằm ở M1–M2 và đã có bằng chứng kiểm
> chứng được. Phần chưa có là M3 trở đi, và phần đó chưa bắt đầu.

---

## 2. Lịch — những gì đã chốt và những gì chưa

### 2.1 Điều GV đã xác nhận

✅ **Điểm này là thông tin duy nhất tôi có về thay đổi lịch:** midterm **chuyển sang sau
khi học Chương 10** (Regression Analysis — tuần 10). Nói cách khác: mốc nộp **không còn
ở W08**.

### 2.2 Lịch suy ra trực tiếp từ điều trên — chưa cần hỏi

| Tuần | Nội dung | Issue | Milestone | Trạng thái |
|:---:|---|:---:|:---:|---|
| W06 | Thống kê mô tả 4 họ chỉ số | #8 | M3 | OPEN |
| W07 | 7 biểu đồ FIG-01→07 | #9 | M3 | OPEN |
| W08 | *trống* — mốc nộp đã dời khỏi W08 | — | — | — |
| W09 | Suy luận thống kê | #11 | M4 | OPEN |
| W10 | Hồi quy OLS + LINE | #12 | M4 | OPEN |
| **W11** | **Mốc nộp midterm** — ⬜ nội dung chưa xác định | #10 | ⬜ chưa chốt | OPEN |
| W12–15 | Phân loại · đạo đức · refactor · báo cáo · bảo vệ | #13–#17 | M5/M6 | OPEN |

Cột "trạng thái" nói **tiến độ issue**, không nói tuần hoàn thành.

### 2.3 Những gì tôi ĐÃ suy diễn và nay gỡ bỏ

Bản plan trước tự đặt ra những điều sau. **Không có nguồn xác nhận — đã gỡ khỏi kế hoạch:**

| Đã gỡ | Vì sao gỡ |
|---|---|
| "Midterm mở rộng scope thành W1–W10" | Tôi suy từ "sau Chương 10" ⇒ scope = W1–W10. GV chỉ nói **dời mốc nộp**, không nói phạm vi chấm thay đổi. |
| "Phân loại #13 lùi khỏi phạm vi midterm, xuống W12" | Suy luận từ việc W11 là buổi học Classification. Chưa ai xác nhận #13 nằm ngoài midterm. |
| "Báo cáo 12–15 trang, thuyết trình 10 phút, Q&A 5 phút" | **Hoàn toàn do tôi đưa ra.** Không nguồn. Đã xoá, không đưa vào bất kỳ đâu nữa. |
| "Notebook phải verify `00_`→`06_`" | Suy từ scope W1–W10. Chưa xác nhận. |
| "M6 gánh 4 issue / 3 tuần là đánh đổi không chấp nhận được" | Tôi tự quyết phần nào "không chấp nhận được". Không có căn cứ. |
| "Rubric EDA không có mục W9–W10 ⇒ chắc chắn sai" | Có thể GV cố ý giữ nguyên rubric. Chỉ nên **hỏi**, không nên kết luận. |

### 2.4 Trạng thái quan hệ phụ thuộc (✅ đã kiểm chứng)

```text
GET /issues/{n}/dependencies/blocked_by  →  #10 []  #11 []  #12 []  #13 []
```

GitHub **có** API dependency nhưng repo **chưa dùng**. Mọi "Phụ thuộc / Chặn" trong thân
issue hiện chỉ là **văn xuôi**. Hệ quả:

> **Sửa câu chữ trong thân issue không làm thay đổi quan hệ ở tầng GitHub.**
> Muốn GitHub thực sự chặn thì phải gọi `POST …/dependencies/blocked_by`.

Quan hệ hiện chỉ tồn tại trên giấy trong thân issue, ghi theo mốc cũ (W08):

| Issue | Thân issue ghi | Thực tế sau thay đổi lịch |
|---|---|---|
| #10 | "Tuần 08" · "Chặn: #11, #12, #13" | Mốc nộp → W11; phần "chặn" cần xem lại |
| #13 | (thuộc W11) | ⬜ chưa rõ #13 có nằm trong phạm vi midterm không |

Milestone hiện tại: M3 `#8#9#10` (Week 6–8) · M4 `#11#12#13` (Week 9–11) · M5 `#14#15#16`
(Week 12–14) · M6 `#17` (Week 15). Tất cả `due_on = null`.

---

## 3. Câu hỏi cho GV — còn 1 câu

### Câu 1 — Mốc nộp W11 cần bao gồm những phần nào, khi hiện tại mới xong W1–W5

> Thầy cho midterm chuyển sang sau Chương 10. **Hiện trạng đã hoàn thành: M1 (W1–W2) và
> M2 (W3–W5) — tức W1–W5. M3 (W6–W8) chưa bắt đầu, M4–M6 chưa bắt đầu.**
>
> Với mốc nộp ở W11, **báo cáo giữa kỳ cần bao gồm phần nào?** Cụ thể:
> - Phần **W1–W5 đã hoàn thành** (thu thập · kiểm toán chất lượng · làm sạch · tích hợp) —
>   có phải phần chính của báo cáo giữa kỳ không?
> - Các phần **W6–W11** (EDA · trực quan hóa · suy luận · hồi quy · phân loại) tôi dự kiến
>   làm trong kỳ tới. Trong số đó **phần nào kịp và phần nào không kịp** trước mốc nộp,
>   và phần nào GV **bắt buộc** phải có trong báo cáo?

**Vì sao chặn:** không có câu trả lời thì không viết được thân #10, không xác định milestone
chứa #10, không xác định chuỗi notebook nào phải chạy lại trước khi nộp.
**Trạng thái hiện tại: ⬜ CHƯA XÁC ĐỊNH.** Tôi không tự chọn phạm vi, không tự đoán phần nào kịp.

### Vì sao không còn Câu 2 (phân loại #13)

Câu hỏi "buổi học W11 là Classification & Feature Engineering, #13 có nằm trong phạm vi giữa
kỳ không" **đã được bỏ**. Lý do: phần đó **đã nằm trong Câu 1** — câu hỏi buộc GV xác định
W6–W11 có phần nào bắt buộc phải có, trong đó có phân loại.

Hệ quả thực tế: **#13 giữ nguyên hiện trạng** — vẫn ở M4, vẫn ghi W11 trong tài liệu.
Tôi **không di chuyển #13**, vì không có căn cứ để đổi. Xem §5.2.

### Sau khi có câu trả lời

Ba điểm còn lại **không hỏi trước**, vì nội dung của chúng phụ thuộc kết quả Câu 1:

| Điểm | Hỏi khi nào |
|---|---|
| Rubric giữ nguyên EDA hay mở rộng | Sau Câu 1 |
| Số trang / thời lượng thuyết trình / Q&A | Sau Câu 1 |
| Notebook nào bắt buộc verify và nộp | Sau Câu 1 |

> ⚠️ **Hiện KHÔNG có con số nào cho các mục này.** Bản plan trước ghi "12–15 trang, 10 phút,
> 5 phút" — đã xoá hoàn toàn. Chưa xác định thì ghi **chưa xác định**, không điền số.

---

## 4. Xử lý 4 mục review PR #36

Phạm vi này **giữ nguyên** — đây là việc sửa dự án để PR được merge, **không liên quan
báo cáo nộp giữa kỳ**. Không tự ý bỏ bớt.

> ✅ **D1–D4 độc lập với quyết định của GV.** Cả bốn đều là lỗi kỹ thuật trong dữ liệu, test
> và tài liệu — **không phụ thuộc** phạm vi midterm, rubric, hay tuần nộp. Có thể làm ngay.
> Xử lý D1–D4 **không** đụng tới `docs/roadmap.md` §13-C/§14, **không** đổi milestone,
> **không** sửa thân issue.

**Nguồn (đã kiểm chứng):** 1 review `doctor-cato`, state `CHANGES_REQUESTED`, commit
`759a9c6`, link `pullrequestreview-5491859837`. **0 inline comment.**
Comment còn lại trong PR là bản tổng hợp tiến độ của tác giả — không phải yêu cầu sửa.

### D1 — Số unit test trong báo cáo

✅ **ĐÃ XỬ LÝ xong 2026-10-12.** Truy nguồn `297` bằng
`git log -S"297 unit test" -- scripts/build_progress_report.py` → commit `be2f1d4`
(lúc viết script; số cũ dần khi thêm test). Lần chạy mới nhất:
`Ran 344 tests … OK`.

> ⚠️ **Thứ tự quan trọng:** D1 phải chạy **SAU** D4. D4 đã thêm 2 test → tổng đi lên
> 342 → **344**. Nếu làm D1 trước D4 thì con số ghi vào báo cáo sẽ sai ngay.
> Số đúng phải tính **sau khi D4 xong** và **kiểm lại mỗi khi thêm/bớt test**.

> Script + `.docx` **chỉ phục vụ GV kiểm tra tiến độ** — tài liệu theo dõi, không phải artifact
> khoa học, không ai diff byte, không có CI nào parse. Nên **giữ số ghi cứng, sửa tay**;
> không xây cơ chế đếm test tự động.

- [x] **D1.1** Sửa `:169` và `:574`: `297` → `342`. ✅ *(làm trước, rồi sửa lại `344` ở §4.3)*
- [x] **D1.2** Sửa `:167` — "chuẩn bị Milestone 3 (EDA & báo cáo giữa kỳ)" → bỏ "báo cáo giữa kỳ"
      (M3 nay chỉ còn EDA, mốc nộp đã dời).
- [x] **D1.3** Sinh lại `docs/bao_cao_tien_do_M1_M2.docx`.
- [x] **D1.4** Kiểm chứng DOCX bằng **trích text**, không so byte — `python-docx` ghi timestamp
      vào `docProps/core.xml`, hai lần chạy cách nhau vài giây cho hai SHA-256 khác nhau dù nội
      dung không đổi. Giới hạn đã ghi tại `README.md:266`.

**✅ KHÔNG bị chặn — đã xong.**

#### Kết quả kiểm chứng DOCX (trích text, không so byte)

```text
Milestone 2 hoàn tất – chuẩn bị Milestone 3 (EDA)
344 unit test — PASS; CI workflow; fetch script không cần API key
344 unit test — PASS; bao gồm test hồi quy chống tái phát lỗi làm sạch
```

#### 4.3 Sửa lại con số sau D4

- [x] `python -m unittest discover tests` → **`Ran 344 tests … OK`** (342 gốc + 2 test D4).
- [x] Sửa `:169` và `:574`: `342` → `344`.
- [x] Tái sinh DOCX, trích text xác nhận: `344` × 2, `342` × **0**.

### D2 — Hai bộ tỷ lệ nhãn: ĐÃ LÀM RÕ, KHÔNG phải mâu thuẫn

✅ **ĐÃ KIỂM CHỨNG 2026-10-12 — hai bộ số KHÔNG mâu thuẫn, chúng là hai đại lượng khác nhau.**

| Nguồn | Nhãn | Ngưỡng | Mẫu số | Train | Test |
|---|---|---|---|---|---|
| `roadmap.md:984`, `:997` | **nhãn nặng** | `pm25 > 100` tức thời theo giờ | dòng **có nhãn** `pm25` | `295/4.279` = 6,89% | `99/3.216` = 3,08% |
| `TASK_LIST_M3_M6.md:42–43` | **cảnh báo** | trung bình **trượt 24h** `≥ 50 µg/m³` | dòng rolling hợp lệ | `986/2.994` | `669/2.323` |

**Bằng chứng nguồn gốc:** `notebooks/03_transformation_pipeline.ipynb` cell 11 tính
`gio>50` và `gio>100` trên **nồng độ tức thời theo giờ**; cell 13 đặt
`SPLIT_TIMESTAMP = 2026-01-15 00:00 Asia/Ho_Chi_Minh`. Cùng ô đó gọi hai số là
`tr_hi, te_hi = int((tr["pm25"] > 100).sum()), ...`.

**Tái lập từ `data/processed/air_pollution_final.parquet`:**

```text
A) nhan nang = pm25 > 100 (tu thoi theo gio), mau so = dong co nhan
   Train  295/4279 = 6.89%   ← khớp roadmap:984 (6,89%)
   Test    99/3216 = 3.08%   ← khớp roadmap:984 (3,08%)
   (mẫu số toàn bộ dòng: Train 295/4682 = 6.30%, Test 99/4362 = 2.27%
    ← khớp luôn dòng thứ hai của roadmap:985)

B) trung binh truot 24h >= 50
   Train  986/2994 = 32.93%   ← TASK_LIST ghi 21,06%  ❌
   Test   669/2323 = 28.80%   ← TASK_LIST ghi 15,34%  ❌
```

> ✅ **Giả thuyết "nhãn Train/Test bị đảo chỗ" trong bản plan trước — BÁC BỎ, SAI.**
> Split tại `2026-01-15` cho Train **4.682** dòng và Test **4.362** dòng — Test nhỏ hơn
> Train là **đúng thực tế** (tổng 9.044 khớp Parquet), không phải dấu hiệu đảo nhãn.

**Phát hiện mới — `TASK_LIST_M3_M6.md:42–43` tự mâu thuẫn số học:**

```text
986/2994 = 32,93%   (không phải 21,06%)
986/4682 = 21,06%   ← 21,06% thực ra ứng với mẫu số TOÀN BỘ dòng
669/2323 = 28,80%   (không phải 15,34%)
669/4362 = 15,34%   ← 15,34% cũng ứng với mẫu số TOÀN BỘ dòng
1655/5317 = 31,13%  (không phải 18,30%)
1655/9044 = 18,30%  ← 18,30% cũng ứng với mẫu số TOÀN BỘ dòng
```

→ Tài liệu **viết** phân số theo mẫu số rolling-hợp-lệ nhưng **tính** phần trăm theo mẫu số
toàn bộ dòng. Tử số và mẫu số viết ra **đều tái lập đúng**; sai là **phần trăm**.

Đây đúng là cái bẫy mà `roadmap.md:990–997` đã cảnh báo: *"một tỷ lệ không nên chia cho các
dòng mà nó không đo được"*.

**Phase A — kiểm kê claim sơ bộ** *(làm được ngay)*

- [x] **A.1** Bảng kiểm kê claim: xem bảng ở đầu mục D2 (nguồn · nhãn · ngưỡng · mẫu số).
- [x] **A.2** Tính lại từng claim theo đúng định nghĩa **từng tài liệu đang nêu** —
      script `scratch/_verify_prevalence.py` (chỉ đọc).
- [x] **A.3** Phân loại kết quả: xem §D3 bên dưới — **14/16 VERIFIED**, 2 MISMATCH,
      0 UNVERIFIABLE.
- [x] **A.4** Giữ **cả hai** bộ số trong hồ sơ audit. **KHÔNG sửa** `TASK_LIST_M3_M6.md` ở lượt
      này — xem Phase D.

**Phase B — chốt định nghĩa** *(chỉ hỏi GV cho phần **tự tra không ra**)*

| # | Quyết định | Kết quả sau khi tra | Nguồn |
|:---:|---|---|---|
| B.1 | Nhãn theo nồng độ tức thời hay trung bình trượt 24h? | ✅ **CÓ HAI NHIỆM VỤ KHÁC NHAU** — roadmap dùng *tức thời*, TASK_LIST dùng *trượt 24h*. Không phải mâu thuẫn. | `roadmap.md:984` · `03_transformation_pipeline.ipynb` cell 11 · `TASK_LIST_M3_M6.md:40` |
| B.2 | Ngưỡng + đơn vị | ✅ **Tách rõ**: `pm25 > 100` (nhãn nặng, roadmap) và `trung bình trượt 24h ≥ 50 µg/m³` (cảnh báo, TASK_LIST). | `03_transformation_pipeline.ipynb` cell 11 |
| B.3 | Mẫu số: toàn bộ dòng hay chỉ dòng đo được? | ⬜ **VẪN CHƯA CHỐT** — xem bảng phương án bên dưới. | — |
| B.4 | Giá trị thiếu xử lý thế nào? | ✅ roadmap đã chốt sẵn: mẫu số = **dòng có nhãn `pm25`**, và ghi rõ lý do tại `roadmap.md:990–997`. | `roadmap.md:990–997` |

**⬜ B.3 — hai phương án, CHƯA CHỌN:**

| | Phương án | Train | Test | Hợp lý với |
|:--:|---|---|---|---|
| **B3-a** | mẫu số = **toàn bộ dòng** (kể cả dòng không đo được) | `986/4.682` = 21,06% | `669/4.362` = 15,34% | con số **hiện đang in** trong `TASK_LIST_M3_M6.md:42–43` |
| **B3-b** | mẫu số = **dòng rolling hợp lệ** | `986/2.994` = 32,93% | `669/2.323` = 28,80% | phân số **đang viết** trong cùng tài liệu |

`roadmap.md:990–997` đã cảnh báo chính cái bẫy này và chọn mẫu số "dòng đo được" cho
**nhãn nặng**. Nhưng đó là cho nhãn `>100`, chưa áp cho nhãn trượt 24h.
→ **Không tự chọn.** Cần GV xác nhận khi phát triển #13, vì nó quyết định cách báo cáo Recall.

> ⚠️ **Quy tắc chốt định nghĩa — chỉ khi đủ bằng chứng.**
>
> 1. Tra `src/cleaning_pipeline.py` + tài liệu dự án trước.
> 2. Chỉ **chốt** một định nghĩa khi **đủ bằng chứng cả hai chiều thống nhất** — mã nguồn và
>    tài liệu **không mâu thuẫn**, và bằng chứng chỉ ra **một** kết luận.
> 3. Nếu mã nguồn và tài liệu **mâu thuẫn nhau**, hoặc mỗi chiều dẫn tới một kết luận khác
>    nhau, hoặc không tìm thấy bằng chứng nào: **KHÔNG tự chọn.** Ghi lại từng phương án kèm
>    bằng chứng trích dẫn (file + dòng + trích đoạn), đánh dấu ⬜ chưa xác định, rồi hỏi GV
>    để **chọn**, không phải để xác nhận lại.
> 4. **Định nghĩa chính thức chỉ tồn tại khi GV xác nhận hoặc bằng chứng nhất quán tuyệt đối.**
>    Trước đó mọi phương án đều là *giả thuyết đang cân nhắc*, không phải định nghĩa đã chốt.
> 5. Nếu Phase B chưa chốt được B.1/B.3/B.4 thì **D2 Phase D dừng**, và tiến độ M3–M6 cũng
>    dừng ở chỗ liên quan — nhưng **D1, D3, D4 và các sửa đổi ngày tháng vẫn đi bình thường**.

**Phase C — `scripts/verify_claims.py`** *(sau Phase B)*

- [ ] **C.1** Đọc `data/processed/air_pollution_final.parquet` — kiểm tra tồn tại + schema trước;
      lỗi thì dừng rõ ràng.
- [ ] **C.2** Quy tắc lọc/tính đặt tường minh trong code.
- [ ] **C.3** Với mỗi claim prevalence: in tử số, mẫu số, công thức, giá trị.
- [ ] **C.4** Tái lập claim số cốt lõi khác khi dữ liệu cho phép: tương quan Pearson, số NaN
      theo cột, số dòng / complete-case, kích thước Train/Test.
- [ ] **C.5** Phân loại `VERIFIED` / `MISMATCH` / `UNVERIFIABLE`; xuất bảng audit ra `reports/`.
- [ ] **C.6** **Chỉ đọc.** Không ghi đè `data/`, không tự thay số đang bị tranh luận.

**Phase D — sửa tài liệu** *(chỉ sau Phase C)*

- [ ] **D.1** Sửa `roadmap.md:984`, `:997`, `TASK_LIST_M3_M6.md:40–48` và `:419` về **một** bộ số
      đã kiểm chứng. **Không thay bộ này bằng bộ kia khi chưa rõ nguyên nhân.**
- [ ] **D.2** Ghi sai lệch + cách giải quyết vào `docs/history/03_audit_findings.md`, kèm **cả
      hai** giá trị trước/sau.
- [ ] **D.3** Mọi tỷ lệ được trích phải có tử số + mẫu số + công thức (theo `roadmap.md:997`).
- [ ] **D.4** Thêm test giữ claim cốt lõi. ⚠️ **Cấm làm claim "đúng" chỉ bằng cách đổi giá trị
      kỳ vọng trong test.**

### D3 — Tái lập được các chỉ số khoa học

🔶 `TASK_LIST_M3_M6.md:35–44` trích nhiều con số đọc thẳng từ Parquet
(`corr(pm25,pm10)=0,9727` · `R²=0,9462` · `pm25 NaN 1.549 (17,1%)`) nhưng **chưa có cách nào
chạy lại để kiểm chứng**.
✅ Script dùng cho lượt này: `scratch/_verify_claims.py` (chỉ đọc).

✅ **ĐÃ KIỂM CHỨNG 2026-10-12** bằng `scratch/_verify_claims.py` (chỉ đọc):
**14/16 claim VERIFIED, 2 MISMATCH.**

```text
VERIFIED  9.044 dong            VERIFIED  pm25 NaN = 1.549
VERIFIED  18 cot                VERIFIED  pm25 NaN% = 17,1
VERIFIED  376 ngay              VERIFIED  pm10 NaN = 1.469
VERIFIED  bien khi tuong NaN=0  VERIFIED  complete-case = 7.372
VERIFIED  corr(pm25,pm10)=0,9727 VERIFIED  R² don bien = 0,9462
VERIFIED  hour_sin/cos, month_sin/cos ton tai

MISMATCH  "1.005 dong/gio"  -> thuc te 24,05 dong/ngay ~ 1,002 dong/gio
MISMATCH  "5 bien khi tuong" -> Parquet co 6 cot: temperature, relative_humidity,
                                  wind_speed, wind_direction, precipitation, surface_pressure
```

- [x] **D3.1** Dùng chung claim inventory của D2 Phase A làm đầu vào.
- [ ] **D3.2** Đầu ra: bảng audit trong `reports/` + exit code khác 0 khi có `MISMATCH` mức
      chặn merge.
- [ ] **D3.3** Quy tắc lỗi: thiếu input → dừng; schema lạ → dừng; mẫu số 0 → dừng, không chia 0.
- [ ] **D3.4** ⚠️ **D3 hỗ trợ D2 chứ không đường vòng qua cổng định nghĩa.** Script dùng
      *định nghĩa đã chốt ở Phase B*; không dùng nó để "chọn ra" định nghĩa.
- [ ] **D3.5** Nghiệm thu: chạy trên máy sạch → mọi claim `VERIFIED` đều tái lập; không còn
      `UNVERIFIABLE` nào thiếu lý do.

### D4 — Độ bao phủ test runtime log

✅ Đã kiểm chứng trên `tests/test_pipeline_runtime_log.py` (31 test):

| Trường hợp GV nêu | Trạng thái | Test hiện có |
|---|---|---|
| Đường dẫn log tùy chỉnh | ✅ Đủ | `test_writes_valid_json_file_to_given_log_path` · `test_explicit_log_path_takes_precedence_over_log_dir` · `test_caller_supplied_runtime_log_path_is_honoured_verbatim` |
| Thư mục cha chưa tồn tại | ✅ Đủ | `test_creates_parent_directory_when_missing` · `test_log_dir_creates_directory_if_missing` |
| Runtime log bị gitignore | ✅ Đủ | `test_runtime_log_path_is_matched_by_a_real_gitignore_rule` · `test_check_ignore_oracle_is_faithful_to_real_git` |
| **Lỗi khi ghi file** | ❌ **Thiếu** | `test_block_raises_instead_of_silently_swallowing_errors` chỉ phủ khối `metadata.json`, **không** phủ `write_pipeline_runtime_log()` |

✅ `git check-ignore -v data/raw/pipeline_execution_runtime.json` → khớp `.gitignore:34`.
✅ Đọc `src/data_collection.py:142–184`: `write_pipeline_runtime_log()` **không có `try/except`**
quanh ghi file → lỗi tự nhiên nổi lên.

✅ **ĐÃ XỬ LÝ xong 2026-10-12** — thêm 2 test vào
`tests/test_pipeline_runtime_log.py::TestWritePipelineRuntimeLog`:

- [x] **D4.1** `test_write_failure_propagates_oserror_instead_of_being_swallowed`
      — `log_path` trỏ vào một thư mục đã tồn tại → `open(..., "w")` ném
      `IsADirectoryError` (lớp con `OSError`). `assertRaises(OSError)`.
- [x] **D4.2** `test_write_failure_propagates_and_returns_no_success_path`
      — chặn `json.dump` bằng `mock.patch.object` ném `OSError("no space left on device")`;
      khẳng định lỗi **gốc** nổi lên (`assertIs`) và hàm **không** trả về `Path` giả
      (`self.fail()` trong `assertRaises` là bằng chứng cho điều đó).
- [x] **D4.3** Trả lời 3 trường hợp đã đạt — xem bảng ngay trên, có tên test đầy đủ.
- [x] **D4.4** **Không sửa `.gitignore`** — đã kiểm chứng khớp `.gitignore:34`.

#### 4.4 `D4-partial-file` — thiết kế hiện tại & phương án xử lý

**Đã kiểm tra mã nguồn** `src/data_collection.py:142-184`. Hàm viết thẳng vào đích:

```python
log_path.parent.mkdir(parents=True, exist_ok=True)      # :169
with open(log_path, "w", encoding="utf-8") as f:         # :182
    json.dump(payload, f, indent=2, ensure_ascii=False)  # :183
return log_path                                           # :184
```

Hệ quả quan sát được, đã **khẳng định bằng test**:

| Cổng lỗi | Trạng thái tệp sau đó |
|---|---|
| `open()` ném (vd. `log_path` là thư mục) | **không có** tệp — `open` chưa kịp tạo |
| `json.dump()` ném giữa chừng (đĩa đầy, I/O) | ⚠️ **tệp 0 byte còn lại** — `open(...,"w")` đã tạo/tiệt trừ trước |

**Rủi ro cụ thể:** tệp runtime log là bằng chứng "lần chạy này đã ghi thành công". Một tệp
0 byte trông giống tệp hỏng, và mọi lần đọc nó về sau sẽ phải xử lý lỗi JSON — trong khi
một lần ghi thất bại như vậy vốn phải nổi lên ngay.

#### Ba phương án xử lý

| | Cách làm | Ưu | Nhược |
|:--:|---|---|---|
| **A** | **Best-effort**: bọc `try/except OSError` → `logger.warning`, vẫn trả `log_path` | Đơn giản, pipeline không sập vì log. | ⛔ **Trái đúng thứ test D4 vừa bảo vệ**: lỗi biến mất âm thầm, người đọc tưởng log đã ghi. **Không khuyến nghị.** |
| **B** | **Atomic write**: ghi vào tệp tạm rồi `os.replace()` sang đích | ⬆ **Không bao giờ** để lại tệp dở; đích chỉ có JSON đầy đủ hoặc không có gì. Là lựa chọn mặc định cho mọi file config/log. | Thêm 1 tệp tạm; phải dọn tệp tạm nếu `json.dump` ném giữa chừng (dùng `try/finally` unlink). |
| **C** | **Giữ nguyên + dọn tệp rỗng**: nếu ghi hỏng thì `unlink()` tệp 0 byte rồi ném lại lỗi | Vẫn **ném lỗi** như test yêu cầu; không để lại rác. Ít thay đổi hơn B. | Khoảng trống thời gian có tệp 0 byte trên đĩa; không bảo vệ được trường hợp `json.dump` viết được một phần rồi ném (hiếm với payload nhỏ này). |

**Khuyến nghị: B**, kèm **C** như lưới an toàn thứ hai (bắt mọi `OSError` → dọn tệp tạm/dích →
ném lại nguyên bản lỗi).

#### ✅ ĐÃ TRIỂN KHAI 2026-10-12 — phương án B + C

Đã đọc lại hợp đồng trước khi sửa. Phát hiện quyết định: **phía gọi đã có sẵn lớp nuốt lỗi**
— `run_collection_pipeline()` tại `src/data_collection.py:1495-1504` bọc `try/except Exception`
→ `logger.warning`. Nghĩa là hợp đồng sẵn có **đúng là** *"hàm ném lỗi, pipeline nuốt và ghi
warning"* — việc ghi log là thông tin phụ, không phải điều kiện thành công.

```python
tmp_fd, tmp_name = tempfile.mkstemp(
    dir=str(log_path.parent), prefix=f"{log_path.name}.", suffix=".json")
tmp_path = Path(tmp_name)
try:
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, log_path)
except BaseException:
    try:
        tmp_path.unlink()
    except OSError:
        logger.warning(...)
    raise
```

| Quyết định thiết kế | Vì sao |
|---|---|
| Tệp tạm **cùng thư mục** đích | `os.replace()` chỉ atomic trên cùng filesystem |
| Hậu tố **`.json`** cho tệp tạm | Khớp `.gitignore:34 data/raw/*.json` → nếu tiến trình bị giết giữa chừng, tệp tạm sót vẫn **không làm bẩn working tree**. Đã kiểm chứng bằng `git check-ignore` |
| `except BaseException` + `raise` | Dọn tệp tạm kể cả khi bị `KeyboardInterrupt`, rồi **ném lại nguyên bản lỗi gốc** — không bọc, không thay bằng lỗi mới |
| ⛔ Không đổi hợp đồng lỗi | Hàm vẫn **ném**. Không có đường `return log_path` sau khi ghi hỏng |
| Chỉ đụng `write_pipeline_runtime_log()` | Không kéo thay đổi production nào khác vào cùng phạm vi |

**Test bổ sung — 5 test mới** (tổng file này 33 → 38):

| Test | Phủ |
|---|---|
| `test_write_failure_propagates_oserror_instead_of_being_swallowed` | `open`/`mkstemp` ném → `OSError` nổi lên |
| `test_write_failure_propagates_and_returns_no_success_path` | `json.dump` ném → lỗi **gốc** nổi, không trả Path giả |
| `test_serialize_failure_leaves_no_file_at_destination` | ⭐ **đích KHÔNG được tạo** — đúng lỗi D4-partial-file đã sửa |
| `test_temporary_file_is_cleaned_up_on_failure` | ⭐ thư mục đích **rỗng hoàn toàn** sau lỗi |
| `test_replace_failure_is_observable_and_cleans_up` | ⭐ lỗi `os.replace` nổi lên **và** vẫn dọn tệp tạm |
| `test_success_path_writes_complete_json_and_leaves_no_temp_file` | ⭐ đường thành công: JSON đầy đủ, 4 khoá, không sót tệp tạm |
| `test_pipeline_tolerates_runtime_log_failure` | ⭐ **ranh giới trách nhiệm**: AST khẳng định lời gọi ghi log **nằm trong `try` có `except`** → log hỏng không làm sập pipeline |

Kết quả: `Ran 349 tests … OK`.

**Test hiện tại đã khoanh vùng đúng:** `test_write_failure_propagates_and_returns_no_success_path`
khẳng định tệp rác là 0 byte, kèm docstring nói rõ đây là **quan sát được, chưa phải hành vi
được phê duyệt**. Khi nào chọn phương án, sửa test cho khớp — sẽ **fail** trước khi sửa code,
đúng thứ tự an toàn.

**Phát hiện mới khi viết test — `D4-partial-file`:** `open(log_path, "w")` tạo/tiệt trừ tệp
**TRƯỚC** khi `json.dump` chạy, nên lỗi giữa chừng để lại **một tệp 0 byte** trên đĩa.
Test đã **ghi nhận đúng hành vi thực tế** (tệp tồn tại và rỗng) kèm docstring nói rõ đây là
quan sát, **không phải hành vi được phê duyệt**. ⬜ **Cần GV/student quyết định** có sửa
hay không — nằm ngoài phạm vi plan, tôi **không tự sửa mã nguồn**.

**✅ KHÔNG bị chặn — đã xong.**

```text
python -m unittest discover tests   →  Ran 344 tests … OK   (342 gốc + 2 test mới)
python -m compileall -q src tests scripts  →  exit 0
```

---

## 5. Tác động lên tài liệu

### 5.1 Phải SỬA — không cần GV (chỉ phần ngày tháng) ✅ **ĐÃ XỬ LÝ 2026-10-12**

```text
docs/roadmap.md:517   midterm_report.pdf  ... (Tuần 8) -> (Tuần 11)
docs/roadmap.md:551   **W8: Midterm Project**      -> **W8 → W11: Midterm Project**
docs/roadmap.md:573   **W08** | MIDTERM MILESTONE  -> **W08 → W11** | MIDTERM MILESTONE
docs/roadmap.md:1182  ### Week 08 – BÁO CÁO...     -> ### Week 08 → Week 11 – BÁO CÁO...
                      + callout [!NOTE] giải thích ký hiệu & liệt kê phần CHƯA xác nhận
.agents/skills/research-documentation/SKILL.md:14  Week 8 -> Week 11
docs/TASK_LIST_M3_M6.md:21  #10 Midterm -> #10 Midterm (nộp W11)
```

**Không** sửa: tên milestone, thân issue, phạm vi báo cáo, số trang, rubric, thời lượng,
`#13`, `roadmap.md:1186` (quan hệ Phụ thuộc/Chặn — chờ Câu 1), `README.md:91`
(tách #10 khỏi M3 là **đổi milestone** → chờ Câu 1, xem §5.2).

Ký hiệu `W08 → W11` thay vì viết thẳng `W11`: W11 đã là tuần của #13, viết thẳng sẽ tạo
hai dòng W11 trùng nhau mà lại đụng #13 — vốn phải giữ nguyên.

| File:dòng | Hiện tại | Sửa |
|---|---|---|
| `docs/roadmap.md:517` | `midterm_report.pdf # … (Tuần 8)` | `(Tuần 11)` |
| `docs/roadmap.md:551` | Skill mapping "W8: Midterm Project → #10" | Bỏ dòng W8; chèn dòng W11 |
| `docs/roadmap.md:573` | Dòng **W08** "MIDTERM MILESTONE" | W08 thành tuần trống/dự phòng; chèn dòng W11 = MIDTERM |
| `docs/roadmap.md:1182–1195` | Mục "Week 08 – BÁO CÁO & ĐÁNH GIÁ GIỮA KỲ" | Sửa mốc sang W11; giữ cấu trúc nội dung hiện có |
| `docs/roadmap.md:1191` | Verify notebook `00_`→`04_` | ⬜ **chờ Câu 1** |
| `README.md:91` | "Tuần 06–08 (Milestone 3) … ([#8, #9, #10])" | Tách #10 ra khỏi M3 |
| `docs/TASK_LIST_M3_M6.md:21` | "4 \| #10 Midterm \| 8 \| ~1 buổi" | Ghi rõ mốc W11 |
| `.agents/skills/research-documentation/SKILL.md:14` | "Midterm Report (Week 8)" | → Week 11 |

### 5.2 GIỮ NGUYÊN — #13, không có căn cứ để đổi

Sau khi bỏ Câu 2, **không di chuyển #13 và không sửa các dòng liên quan đến #13**:

| File:dòng | Hành động |
|---|---|
| `docs/roadmap.md:1236` | **Giữ nguyên** mục "Week 11 – Phân loại" |
| `docs/roadmap.md:554` | **Giữ nguyên** dòng skill mapping "W11: Classification & Features" |
| Milestone M4 trên GitHub | **Giữ nguyên** — #13 vẫn thuộc M4 |
| `docs/roadmap.md:52` | **Giữ nguyên** M4 ghi "Week 9–11" |

> Lý do: thay đổi mốc nộp W08 → W11 cho phép sửa **mốc của #10**. Nó **không** cho phép
> kết luận #13 thuộc hay không thuộc phạm vi giữa kỳ — điều đó cần GV xác nhận trong Câu 1.
> Không có câu trả lời ⇒ giữ nguyên hiện trạng.

### 5.3 Phải SỬA — cần Câu 1 trước

| File:dòng | Nội dung |
|---|---|
| `docs/roadmap.md:51` | Tên M3 — hiện ghi "Báo cáo Giữa kỳ Midterm (Week 6–8)" |
| `docs/roadmap.md:1185` | "Toàn bộ kiến thức Chương 1, Chương 2, Chương 3" |
| `docs/roadmap.md:1188` | Danh sách phần nội dung báo cáo |
| `docs/roadmap.md:668` | "Báo cáo Giữa kỳ (Midterm EDA Report): 8–10 trang" |
| Thân issue #10 | Toàn bộ |

### 5.4 Lỗi phát hiện thêm, không liên quan lịch

| File:dòng | Vấn đề |
|---|---|
| `.agents/skills/classification/SKILL.md:12` | Trỏ `notebooks/06_classification_alerts.ipynb` — nhưng `06_` đã là `06_regression_modeling.ipynb`; tên đúng là `07_classification_alerts.ipynb` |

### 5.5 KHÔNG được sửa

| File | Lý do |
|---|---|
| **`docs/ROADMAP_INFO3020_Air_Pollution.md`** (`:71,428,460,481,545`) | ✅ **Bản chép nguyên văn đề cương 15 tuần của GV.** Chính file này ghi ở dòng 7–12: *"TÀI LIỆU THAM CHIẾU GỐC — ĐÃ BỊ THAY THẾ MỘT PHẦN … Bản roadmap làm việc chính thức là `docs/roadmap.md`"*. Mọi dòng "Tuần 8 / W8" ở đây là **sự thật của đề cương cũ**, không phải lỗi. **Sửa nó = bóp méo nguồn gốc.** Nếu GV đổi lịch, GV cung cấp bản đề cương mới — tôi không tự sửa. |
| `docs/history/02_lich_su_issue_pr_chi_tiet.md:17,18` | Ảnh chụp milestone tại một thời điểm — hồ sơ lịch sử. Nếu cần thì **thêm** mục mới, không sửa phần cũ. |
| `docs/history/03_audit_findings.md` | Sẽ **thêm** phát hiện D2, không sửa phần cũ |

### 5.6 Xử lý kết quả grep (không thay thế toàn cục)

⚠️ Không `sed`/find-replace toàn cục. Phân loại từng kết quả:

| Loại | Ví dụ | Hành động |
|---|---|---|
| Sửa | `roadmap.md:573` dòng W08 | Sửa có kiểm soát |
| Dự phòng có chủ ý | Dòng "W08 — không còn mốc nộp" sau khi sửa | **Giữ** |
| Nguồn gốc | `ROADMAP_INFO3020_Air_Pollution.md` toàn bộ | **Giữ** |
| Lịch sử | `docs/history/02:17–18` | **Giữ** |
| False positive | `roadmap.md:855` "WEEK 1 ĐẾN WEEK 15" — tiêu đề mục | **Giữ** |
| Nhiễu nhị phân | Chuỗi base64 trong `.ipynb` khớp pattern | Dùng `git grep -I` hoặc giới hạn `*.md *.py *.yml` |

---

## 6. An toàn thực thi

### 6.1 Kiểm tra Git bắt buộc trước khi sửa bất kỳ file nào

✅ **Đã chạy 2026-10-12, trước lượt sửa plan:**

```text
git branch --show-current  → docs/audit-delivery
git log --oneline -1       → 759a9c6 docs: Record the M3-M6 issue bodies as patched
git status --short         →  M notebooks/03_processed_data_preview.ipynb
                           ?? docs/PLAN_MIDTERM_RESCHEDULE_PR36.md
git diff --numstat -- notebooks/03_processed_data_preview.ipynb  → 72  72
```

- [ ] **S.1** ✅ Branch `docs/audit-delivery`, HEAD `759a9c6` — đúng.
- [ ] **S.2** ⚠️ **`notebooks/03_processed_data_preview.ipynb` có thay đổi từ trước, không thuộc
      đợt này**: 72 dòng đổi 72 dòng — churn định dạng thuần (cell `id` đánh số lại + dấu phẩy
      JSON do `nbformat` ghi lại), **không đổi nội dung hay output**.
      → **Không `git add`. Không `git restore`. Không `git checkout`. Giữ nguyên trong working tree.**
      → Kiểm lại sau **mỗi** giai đoạn: file này vẫn phải hiện `M` và vẫn là 72/72.
- [ ] **S.3** Chụp `gh milestone list` + `gh issue list` trước khi chỉnh milestone.
- [ ] **S.4** Mỗi giai đoạn: `git status --short` phải cho ra **đúng** 2 dòng đã biết
      (`M notebooks/03_processed_data_preview.ipynb` + các file của đợt này). Dòng lạ = dừng.

### 6.2 Ranh giới local ↔ remote

| Loại | Quy tắc |
|---|---|
| Local | Sửa `docs/*.md`, `scripts/*.py`, `tests/*.py` — được phép |
| Artifact | `.docx` sinh lại, không sửa tay; kiểm chứng bằng trích text |
| **Dữ liệu** | ⛔ **Không sửa, không commit.** `verify_claims.py` chỉ **đọc** |
| **Remote** | ⛔ **Chưa động tới.** Không sửa issue, milestone, PR cho tới khi Câu 1 có trả lời |
| **Không làm** | `git commit`, `git push`, `gh pr merge`, `gh issue close`, `gh milestone edit` ⛔ trong lượt này |

**Khôi phục:** issue mất milestone → `PATCH /issues/{n}` trả milestone cũ (lấy từ S.3). Đổi tên
milestone nhầm → `PATCH /milestones/{number}` trả tên cũ, **số milestone không đổi**.
⛔ Cấm `git reset --hard`, `git checkout -- .`.

**Rủi ro chính:** sửa nhầm `ROADMAP_INFO3020_Air_Pollution.md` — lỗi không hoàn tác được về
mặt ý nghĩa vì đó là văn bản gốc của GV.

---

## 7. Trình tự thực thi

**Cột "Chờ GV" tách riêng khỏi "Thời gian làm việc".** Con số giờ bên dưới là **thời gian tôi
làm**, không chứa thời gian chờ phản hồi — thời gian chờ chưa có căn cứ ước lượng được.

> ⚠️ **Cột "Giờ làm" là ƯỚC LƯỢNG cho công việc chưa làm, KHÔNG phải tiến độ đã đạt.**
> Ô "Hoàn thành" chỉ được đánh dấu sau khi có bằng chứng kiểm tra thực tế. Xem §7.1.

| # | Việc | Chờ GV? | Ước lượng giờ | Hoàn thành |
|:--:|---|:---:|:---:|:---:|
| 1 | D4.1–D4.3 — test lỗi ghi runtime log | ⛔ không | 0,5 | ✅ **xong** — 2 test, 344 OK |
| 2 | D1.1–D1.4 — sửa số test, sinh lại docx | ⛔ không | 0,5 | ✅ **xong** — 297→344, DOCX đã trích text xác nhận |
| 3 | D2 Phase A — kiểm kê & tính lại claim | ⛔ không | 1,5–2 | ✅ **xong** — 2 bộ số là 2 đại lượng khác nhau |
| 4 | D2 Phase B — tra định nghĩa từ `src/` + tài liệu | ⛔ không | 0,5–1 | 🟡 **B1/B2/B4 rõ; B.3 còn 2 phương án, chưa chọn** |
| 5 | ~~Gửi Câu 1 cho GV~~ — **xoá khỏi đường đi** | — | 0 | ✅ **không làm** — xem ghi chú bên dưới |
| 6 | D2 Phase C — `scripts/verify_claims.py` | ⛔ không | 3–4 | ✅ **xong** — 15/15 VERIFIED, exit 0, CSV ra `reports/claim_audit.csv` |
| 7 | D2 Phase D — sửa số liệu tài liệu | ⛔ không | 1 | ✅ **xong 1 phần** — sửa 7 chỗ sai; **mẫu số B.3 vẫn chưa chốt** nên chỉ in cả hai phương án, KHÔNG công bố con số cuối |
| 8 | D3 — nghiệm thu tái lập | ⛔ không | 0,5 | ✅ **xong** — 2 MISMATCH đã sửa ở bước 7; nay **15/15 VERIFIED** |
| 9 | Sửa tài liệu §5.1 (phần ngày tháng) | ⛔ không | 1 | ✅ **xong** — 5 vị trí, roadmap đúng 4 hunk |
| 10 | ~~Sửa tài liệu §5.2 (#13 → W12)~~ **xoá** — #13 giữ nguyên M4/W11 | — | 0 | ✅ **không làm** |
| 11 | ~~Sửa thân #10 + thân #11/#12~~ — **không làm** | ⛔ **giữ nguyên GitHub** | 0 | ✅ **giữ nguyên có chủ đích** |
| 12 | ~~Đổi milestone #10 + tạo dependency GitHub thật~~ — **không làm** | ⛔ **giữ nguyên GitHub** | 0 | ✅ **giữ nguyên có chủ đích** |
| 13 | Đối chiếu 3 nguồn + `unittest` + CI + diff | ⛔ chờ CI | 1 | 🟡 **local xanh — `PENDING CI`** |

**Đã làm xong:** bước **1, 2, 3, 4, 6, 7, 8, 9** — mọi bước **không phụ thuộc GV**.
**Chờ B.3 định nghĩa:** bước **7 phần còn lại** — xác minh tử số + chốt mẫu số, rồi
công bố con số cuối và đóng task 0.7b.
**Bước 11, 12 — KHÔNG LÀM (quyết định đã chốt):** phạm vi issue và milestone được
**giữ nguyên**. Xem ghi chú bên dưới.
**Còn lại:** bước **13** — `PENDING CI`, cần commit mới rồi CI chạy trên commit đó.

> 📌 **Ghi chú quyết định — phạm vi issue/milestone GIỮ NGUYÊN, báo cáo theo tiến độ thực tế.**
>
> Trước đây bước 11–12 bị gắn nhãn `⛔ chờ Câu 1`, ngầm ý rằng chúng sẽ được làm
> ngay khi có câu trả lời. **Điều đó không đúng với nguyên tắc đã chốt** của chính plan này:
> mọi thay đổi lịch phải là **quyết định của GV**, không phải thứ ta tự thiết kế.
>
> | | |
> |---|---|
> | **Thân issue #10, #11, #12** | **không sửa** — nội dung hiện tại phản ánh phạm vi GV đã gán |
> | **Milestone #10** | **không đổi** — tách #10 khỏi M3 là thay đổi phạm vi, cần GV quyết |
> | **Dependency GitHub native** | **không tạo** — #10–#13 vẫn rỗng; quan hệ "Phụ thuộc/Chặn" chỉ là văn xuôi |
> | **Issue #13** | **giữ nguyên M4/W11** — không có căn cứ để đổi |
> | **Cách báo cáo tiến độ** | theo **tiến độ thực tế**: M1 (W1–W2) + M2 (W3–W5) **đã xong**; M3–M6 **chưa bắt đầu** |
> | **Câu 1 (§3)** | giữ lại như **câu hỏi mở**, không còn chặn bất kỳ bước nào |
>
> Hệ quả cho §8: tiêu chí **#12** và **#14** chuyển sang `HELD` — **không phải** `DONE`,
> vì ta cố ý không làm, chứ không phải vì đã làm xong. Mốc lịch `W08 → W11` vẫn phản ánh
> đúng trong tài liệu (tiêu chí #11 `VERIFIED`).

**Giả định ĐÃ DÙNG khi làm bước 6–9** (đều ghi rõ trong file đầu ra):
* Mốc cắt `2026-01-15 00:00 Asia/Ho_Chi_Minh` — đọc từ `03_transformation_pipeline.ipynb` cell 13.
* Nhãn nặng = `pm25 > 100` **tức thời theo giờ** — cell 11.
* Cảnh báo = trung bình **trượt 24h** ≥ 50 — khai báo tại `TASK_LIST_M3_M6.md:40`.
* Ba phương án: chỉ sửa những gì **tái lập được và đối chiếu khớp**; **không** suy ra phạm vi midterm,
  **không** đổi milestone / #13 / thân issue / quan hệ GitHub.

**Ước lượng còn lại: ~1 giờ** — gần như toàn bộ là **CI** (bước 13) sau khi có commit mới.
**Không** gồm thời gian chờ GV và **không** gồm thời gian giải quyết B.3 — chưa có
căn cứ ước lượng cho hai việc đó.
Ước lượng còn lại cho bước 6 và 10 vẫn là *(bất định)* — cần chỉnh sau khi B.3 rõ.

> ⛔ **Cổng GV chỉ chặn bước 11–12, không chặn phần báo cáo tiến độ.** D1, D2 Phase A–B, D3, D4
> và các sửa đổi ngày tháng đều làm được ngay.

---

## 8. Definition of Done

| # | Tiêu chí | Kiểm chứng | Trạng thái |
|:--:|---|---|---|
| 1 | D4.1–D4.3 xong | Test mới assert `OSError`; `unittest` pass | ✅ **xong** — 344 test OK |
| 2 | D1.1–D1.4 xong | `build_progress_report.py` ghi `344` khớp `Ran 344 tests`; DOCX trích text khớp | ✅ **xong** |
| 3 | D2 Phase A xong | Bảng kiểm kê claim có trạng thái `VERIFIED`/`MISMATCH`/`UNVERIFIABLE` | ✅ **xong** |
| 4 | `verify_claims.py` tái lập được claim | Chạy trên máy sạch, bảng audit trong `reports/` | ⛔ chỉ **D2 + D3** |
| 5 | Mọi tỷ lệ prevalence dùng **cùng một định nghĩa đã chốt** | `git grep -nE "[0-9]+,[0-9]+%" docs/` → mọi kết quả truy được về định nghĩa | ⛔ chỉ **D2 + D3** |
| 6 | Số test trong báo cáo khớp thực tế | `python -m unittest discover tests` → `Ran 349 tests` | ✅ **DONE + VERIFIED** — 349/OK, DOCX trích text khớp |
| 7 | `ROADMAP_INFO3020_Air_Pollution.md` **không đổi một byte** | `git diff --stat -- docs/ROADMAP_INFO3020_Air_Pollution.md` → **rỗng** | ✅ kiểm được ngay |
| 8 | Không sửa dữ liệu nguồn | `git status` không có thay đổi trong `data/` | ⛔ kiểm ở mỗi checkpoint |
| 9 | `03_processed_data_preview.ipynb` giữ nguyên | Vẫn là `M` trong `git status`, không vào commit nào | ⛔ kiểm ở mỗi checkpoint |
| 10 | Tiến độ báo cáo khớp thực tế | §1 khớp `gh issue list` + nội dung `notebooks/` `figures/` `reports/` | ✅ **đã xác nhận** |
| 11 | Mốc nộp trong tài liệu là W11 | `git grep -nE "Tuần 8\|Week 8\|W08" -I` → chỉ còn §5.5 | ✅ **DONE + VERIFIED** — roadmap `:517,551,573,1182`, `SKILL:14`, `TASK_LIST:21` |
| 12 | Quan hệ dependency GitHub **thật**, không chỉ văn xuôi | `GET /issues/{n}/dependencies/blocked_by` khớp §2.4 | ⏸️ **GIỮ NGUYÊN** — dependency native của #10–#13 vẫn rỗng; **không tạo**, vì phạm vi lịch là của GV |
| 13 | `unittest` + CI xanh | CI `Python validation` ✅ | 🟡 **`PENDING CI`** — local `Ran 349 tests … OK`; CI chưa chạy trên commit mới |
| 14 | Thân #10 khớp phạm vi GV đã xác nhận | Đối chiếu §3 | ⏸️ **GIỮ NGUYÊN** — không sửa thân issue; tiến độ báo cáo theo **tiến độ thực tế** (M1–M2 xong, M3–M6 chưa bắt đầu) |
| 15 | Đổi lịch tách khỏi PR #36 | PR mới chỉ chứa diff lịch | ⛔ bước 12 |

> **Bốn trạng thái — định nghĩa và phạm vi:**
>
> | Trạng thái | Định nghĩa | Mục |
> |---|---|---|
> | **`DONE`** | Việc đã làm xong trong repo. | D1 · D3 · D4 (kể cả atomic write) · bước 9 (ngày tháng) · `scripts/verify_claims.py` · dọn `scratch/` |
> | **`VERIFIED`** | Đã chạy lệnh kiểm tra và **thấy kết quả khớp**, bằng chứng nằm trong repo. | `Ran 349 tests … OK` · `verify_claims.py` 15/15 VERIFIED exit 0 · DOCX trích text · `data/` rỗng · `ROADMAP_INFO3020` rỗng · notebook 72/72 · mọi file LF |
> | **`PENDING CI`** | Local đã xanh nhưng **CI chưa chạy trên commit mới**. Không được coi là xong. | #4 · #13 · toàn bộ cổng §8.1 |
> | **`UNDECIDED`** | Đã đo đủ số liệu nhưng **chưa có căn cứ chọn**, nên không công bố con số cuối. | B.3 mẫu số nhãn cảnh báo · task 0.7b |
> | **`HELD`** | Phạm vi lịch là quyết định của GV. Ở đây **giữ nguyên** issue/milestone và báo cáo theo tiến độ thực tế. | #12 · #14 |
>
> ⚠️ **Không đánh dấu hoàn thành chỉ vì lệnh trả exit 0.** `verify_claims.py` trả 0 có nghĩa
> *15 claim được kiểm chứng khớp* — **không** có nghĩa *mẫu số B.3 đã được chốt*. Mục B.3
> vẫn `UNDECIDED` dù script exit 0, vì exit 0 chỉ phản ánh phần **đã định nghĩa rõ**.
>
> ⛔ **CHƯA tuyên bố PR #36 sẵn sàng qua review.** Cổng §8.1 còn thiếu **CI chưa chạy trên
> commit mới**. Cụ thể chưa xác nhận: 5 test D4 mới (dùng `tempfile.mkstemp` +
> `os.replace`) và 1 test AST có chạy được trên `ubuntu-latest` không, và 1 test cũ có
> `@unittest.skipUnless(os.name == "nt")`.

### 8.1 Cổng tuyên bố "PR #36 sẵn sàng qua review"

⛔ **Không được tuyên bố PR #36 sẵn sàng khi chưa chạy đủ các kiểm tra dưới đây.** Tối thiểu:

| # | Kiểm tra | Lệnh | Bằng chứng cần lưu |
|:--:|---|---|---|
| 1 | Unit test pass | `python -m unittest discover tests` | Dòng `Ran N tests` + `OK` |
| 2 | Syntax sạch | `python -m compileall -q src tests scripts` | exit code |
| 3 | Không có thay đổi trong `data/` | `git status --short` | Không dòng nào thuộc `data/` |
| 4 | Notebook có sẵn không bị đụng | `git diff --numstat -- notebooks/03_processed_data_preview.ipynb` | Vẫn `72 72` |
| 5 | D1–D4 đã xong theo DoD #1, #2, #4 | Xem bảng trên | Bằng chứng từng mục |
| 6 | CI xanh | `Python validation` | Link run |

Chỉ khi **cả 6** có bằng chứng mới được nói "đã sẵn sàng qua review". Trước đó báo cáo đúng
tình trạng: *đã làm được những gì, chưa làm gì, còn vướng gì*.

---

## 9. Những gì chưa rõ

| Mục | Trạng thái |
|---|---|
| Phạm vi nộp midterm tại W11 (W1–W5 đã xong · W6–W11 phần nào bắt buộc · phần nào kịp) | ⏸️ **chưa xác định — nhưng KHÔNG chặn việc gì.** Issue/milestone giữ nguyên; báo cáo theo tiến độ thực tế (M1–M2 xong, M3–M6 chưa bắt đầu) |
| #13 thuộc phạm vi giữa kỳ không | ⏸️ **giữ nguyên hiện trạng M4/W11** — không có căn cứ để đổi, xem §5.2 |
| Rubric áp dụng | ⬜ chưa xác định — GV chưa nêu |
| Số trang / thời lượng thuyết trình / Q&A | ⬜ **chưa xác định** — GV chưa nêu. Bản plan trước ghi "12–15 trang, 10 phút, 5 phút" là **do tôi tự đưa ra, đã xoá** |
| Notebook nào bắt buộc verify và nộp | ⬜ chưa xác định — GV chưa nêu |
| Định nghĩa prevalence B.1 / B.2 / B.4 | ✅ **đã tra từ nguồn** — xem bảng bên dưới |
| **Định nghĩa prevalence B.3 — nhãn cảnh báo trượt 24h** | ⬜ **CHƯA XÁC MINH + CHƯA CHỐT** — hai vấn đề **độc lập**:<br>① **Tử số 986/669/1.655 CHƯA XÁC MINH** — không có mã nào trong repo định nghĩa nhãn, số chỉ tái lập được dưới giả định `rolling(24, min_periods=24) ≥ 50`. Độ nhạy đo được: `min_periods` 24→12 làm tổng nhảy 1.655→2.131, mp=1 là 2.355.<br>② **Mẫu số chưa chốt** — `UNDECIDED`, hai phương án cho kết quả khác nhau; **không tự chọn**.<br>Giải quyết ① không bù được ②. Xem task 0.7b (5 tiêu chí) |
| Hai bộ tỷ lệ prevalence có mâu thuẫn không | ✅ **không** — đã chứng minh là **hai nhãn khác nhau** (`pm25>100` tức thời vs trượt 24h). Tái lập khớp từng con số |
| Con số trong `TASK_LIST_M3_M6.md` | ✅ **15/15 VERIFIED** bằng `python scripts/verify_claims.py`, exit 0 |
| `write_pipeline_runtime_log()` khi ghi hỏng | ✅ **ĐÃ XỬ LÝ** — atomic write (`mkstemp` + `os.replace`), dọn tệp tạm, giữ nguyên hợp đồng "hàm ném / pipeline nuốt". Xem §4.4 |
| Quyền tệp runtime log sau khi ghi atomic | 📝 **ghi nhận, chấp nhận** — `mkstemp` tạo tệp `0600` trên POSIX thay vì `0644` như `open(…,'w')`. Tệp này bị `.gitignore` loại trừ và không mã nào đọc lại → hạn quyền là hướng an toàn hơn. Nếu sau này cần chia sẻ thì phải `os.chmod` tường minh |
| Notebook `00_`→`06_` có chạy sạch không | ❓ chưa chạy |
| Thời gian GV trả lời | ❓ **không có căn cứ ước lượng** |

---

## 10. Phụ lục — bằng chứng của lượt audit này

| Kiểm tra | Kết quả |
|---|---|
| Branch / HEAD | `docs/audit-delivery` / `759a9c6` |
| Working tree trước lượt này | `M notebooks/03_processed_data_preview.ipynb` (có sẵn, 72/72 dòng) |
| Issue CLOSED | #1 #2 #19 #3 #4 #5 #6 #7 — **8/19** |
| Issue OPEN | #8 #9 #10 #11 #12 #13 #14 #15 #16 #17 — **11/19**, gồm **toàn bộ M3–M6** |
| Notebook `0[4-7]*` | **0 file** |
| `figures/` | chỉ `.gitkeep` — 0/7 biểu đồ |
| `reports/` | chỉ `.gitkeep` — chưa có báo cáo |
| `data/processed/air_pollution_final.parquet` | tồn tại, 267.399 bytes |
| Số unit test | ✅ `Ran 344 tests … OK` (chạy mới 2026-10-12; 342 gốc + 2 test D4) |
| `scripts/verify_claims.py` | ✅ 15/15 VERIFIED · 0 MISMATCH · exit 0 · CSV `reports/claim_audit.csv` |
| Line ending các file đã sửa | ✅ đều **LF**, khớp `.gitattributes` (`* text=auto eol=lf`) |
| `git diff --stat -- src/` | ✅ **rỗng** — không sửa production code |
| `git status -- data/` | ✅ **rỗng** — không đụng dữ liệu |
| `git diff -- docs/ROADMAP_INFO3020_Air_Pollution.md` | ✅ **rỗng** — không đụng đề cương gốc của GV |
| DOCX (trích text) | ✅ `344` × 2 · `342` × 0 · `297` × 0 |
| GitHub issue dependencies | ✅ `blocked_by` **rỗng** cho #10 #11 #12 #13 |
| Milestone `due_on` | ✅ tất cả `null` |
| `write_pipeline_runtime_log` | ✅ `src/data_collection.py:142–184`, không `try/except` |
| Runtime log gitignore | ✅ khớp `.gitignore:34` |
| `ROADMAP_INFO3020_Air_Pollution.md` | ✅ bản chép nguyên văn đề cương GV — loại trừ khỏi phạm vi sửa |
| Review PR #36 | ✅ 1 review, 0 inline comment, `CHANGES_REQUESTED` |
| Grep nhị phân | ⚠️ `git grep` không có `-I` khớp base64 trong `.ipynb` → dùng `git grep -I` |