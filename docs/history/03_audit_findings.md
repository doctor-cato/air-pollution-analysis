# 03 — Audit findings: phần chưa sửa xong & phần chưa phát hiện ra

> Ngày audit: 2026-10-03 · Base: `origin/main` = `76a6a61`
> Phân loại: **A** = đã biết, chưa sửa · **B** = đã biết, cố ý giữ · **C** = chưa ai phát hiện (nghi vấn của audit này)
> Mỗi mục ghi **bằng chứng**, **mức độ**, **ai chịu trách nhiệm** và **hành động đề xuất**.

---

## Tổng kết nhanh

| Nhóm | Số lượng |
|---|---:|
| A — đã biết, chưa sửa | 9 |
| B — đã biết, cố ý giữ / hoãn có lý do | 6 |
| C — nghi vấn audit này, chưa ai ghi nhận | 7 |
| **Tổng** | **22** |

---

# NHÓM A — ĐÃ BIẾT, CHƯA SỬA

### A-1 🔴 HIGH — Số tỷ lệ nhãn nặng trong Issue #7 vẫn sai, chưa được sửa lại

**Bằng chứng:** PR #34 đã sửa con số trong Issue #13 (3,08% / 6,89% → **2,24×**) nhưng **Issue #7 body vẫn giữ
2,27% / 6,30% → ~2,8×**, chia nhầm mẫu số 4.362 dòng Test thay vì 3.216 dòng có nhãn.
`docs/roadmap.md` Quyết định 1 và `notebooks/03_transformation_pipeline.ipynb` §5 + tóm tắt
(cũng được sửa trong `b8b5009`) đã dùng con số đúng → **repo đang có hai con số mâu thuẫn nhau.**

**Mức độ:** HIGH — đây là con số sẽ được đưa vào báo cáo và bị phản biện ở #13/#16.
**Phụ trách:** Issue #7 (đã đóng).
**Hành động:** sửa body Issue #7 → 3,08% / 6,89% / ~2,24×; grep toàn repo tìm mọi `2,8×`, `2,27%`, `6,30%`.

### A-2 🔴 HIGH — 14 test adapter của PR #28 vẫn chưa được khôi phục

**Bằng chứng:** PR #28 thêm 14 test trực tiếp cho `OpenAQAdapter.to_canonical()`, bị mất khi PR #28 bị revert
(PR #29 → commit `962457c`). Tác giả PR #30 đã **tự thừa nhận**: *"14 adapter tests và fix
metadata-determinism từ #28 vẫn đang bị revert"*. Đến `origin/main` hiện tại vẫn chưa khôi phục.
`tests/test_data_collection.py` hiện có 57 test, không phải 71.

**Mức độ:** HIGH — `to_canonical()` là nơi xử lý timezone rollover UTC, sub-hourly averaging, sentinel
`-999/-9999` với `0.0` hợp lệ, bbox filter fail-loud. Đây là **ranh giới tin cậy** của toàn bộ pipeline.
**Phụ trách:** Issue #3 (đã đóng).
**Hành động:** `git show 131dc86 -- tests/test_data_collection.py` → lấy lại 14 test, chạy lại trên code hiện tại.

### A-3 🔴 HIGH — Fix metadata-determinism của PR #28 cũng mất

**Bằng chứng:** cùng PR #28, commit `460d2fd` *"keep tracked metadata provenance deterministic across runs"*.
Sau revert, `run_collection_pipeline()` lại ghi `last_updated_utc` / `execution_timestamp_utc` vào
`data/raw/metadata.json` — file **được git-track**. Mỗi lần chạy notebook 01 là `metadata.json` bị bẩn → dirty diff.

**Mức độ:** HIGH — vi phạm nguyên tắc "không có artifact được track nào bị biến đổi bởi lần chạy".
**Phụ trách:** Issue #3.
**Hành động:** khôi phục `PIPELINE_RUNTIME_LOG_FILENAME` + `write_pipeline_runtime_log()` ghi
`data/raw/pipeline_execution_runtime.json` (đã nằm trong `.gitignore` sẵn qua `data/raw/*.json`).

### A-4 🟠 MEDIUM — PR #35 (đồng bộ docs) chưa merge, README vẫn ghi 259 test

**Bằng chứng:** `origin/main` `README.md:50` ghi *"Tổng số unit test: 259 (`test_data_quality` 14, `test_cleaning` 107,
`test_cleaning_pipeline` 38, `test_cleaning_pipeline_guards` 34)"*. Đo thật trên `origin/main`:
**311 test** — `test_data_quality` **44**, `test_cleaning` **114**, `test_cleaning_pipeline` **44**,
`test_cleaning_pipeline_guards` **43**.

**Mức độ:** MEDIUM — số test sai là claim kiểm định sai ngay trong README, và README là tài liệu #16 dùng cho bảo vệ.
**Phụ trách:** PR #35 đang OPEN, chưa review.
**Hành động:** merge PR #35 sau khi có 1 vòng review; hoặc đóng và mở lại nếu đã lỗi thời.

### A-5 🟠 MEDIUM — Roadmap vẫn ghi Issue #7 "chưa merge" + claim mutation không tái lập được

**Bằng chứng:** `docs/roadmap.md:758` — `| #7 | ... | **DONE (chưa merge)** | Nằm trên nhánh feat/issue-6-deterministic-cleaning, **chưa merge vào main** ... |`.
`docs/roadmap.md:778` — `mutation score của src/cleaning_pipeline.py là **21/21 = 100%**.`
Cả hai đã được sửa trong PR #35 nhưng **PR #35 chưa merge**.

**Mức độ:** MEDIUM — roadmap là nguồn tra cứu bảo vệ; hai dòng này sẽ bị bắt ngay.
**Phụ trách:** PR #35.
**Hành động:** merge PR #35.

### A-6 🟠 MEDIUM — Issue #5 và #6 đã đóng nhưng AC trong body vẫn `- [ ]`

**Bằng chứng:** `gh issue view 5` → 7 ô `- [ ]` chưa tick (6 AC + 1 validation).
`gh issue view 6` → 10 ô `- [ ]` chưa tick (7 AC + 3 validation).
Trong khi #1, #2, #3, #4, #7, #19 đều tick AC trước khi đóng.

**Mức độ:** MEDIUM — Issue #17 (M6) yêu cầu *"đồ thị phụ thuộc của toàn bộ issues nhất quán"*;
người đọc issue #5/#6 sẽ thấy "chưa làm" dù đã merge.
**Phụ trách:** ViolaPeracia.
**Hành động:** tick AC #5/#6 kèm bằng chứng, hoặc ghi rõ ở body "AC đạt, xem `docs/data_quality_audit.md` / `docs/cleaning_log.md` §5".

### A-7 🟠 MEDIUM — `docs/roadmap.md` còn figure không tái lập được (PR #35 đã ghi nhận nhưng chưa sửa)

**Bằng chứng:** PR #35 ghi roadmap có figure *"31,2% / 24,2%"* cần tái suy, vì ngưỡng 50 cho 33,3/27,3
và ngưỡng 100 cho 6,9/3,1 → **không có ngưỡng nào ra 31,2/24,2**.
(Tìm kiếm trực tiếp trên `origin/main` hiện tại không thấy chuỗi `31,2`/`24,2` —
khả năng đã được gỡ ở một commit khác, nhưng PR #35 vẫn ghi là cần xác minh lại.)

**Mức độ:** MEDIUM — figure sai trong roadmap sẽ lan sang báo cáo #16.
**Phụ trách:** tác giả roadmap.
**Hành động:** grep `roadmap.md` cho mọi tỷ lệ phần trăm, đối chiếu lại bằng `src/data_quality.py` trên dữ liệu thật.

### A-8 🟡 LOW — Issue #11 vẫn ghi ngưỡng QCVN 24h = 50 µg/m³, mâu thuẫn với quyết định đã chốt

**Bằng chứng:** body Issue #11 (ghi chú kỹ thuật bắt buộc) ghi *"ngưỡng QCVN 24h = 50 µg/m³, ngưỡng năm = 25 µg/m³"*.
PR #20 (29/09) đã sửa #2 thành **45 µg/Nm³** theo QCVN 05:2023/BTNMT từ 01/01/2026;
PR #26 commit `eb0614e` cũng đã chốt 45 µg/Nm³.

**Mức độ:** LOW (chưa tới hạn) nhưng **HIGH nếu ai đó tick AC #11 mà không đọc `docs/data_dictionary.md`** —
đây chính xác là loại mâu thuẫn đã bị bắt ở PR #20.
**Phụ trách:** Issue #11 (M4).
**Hành động:** sửa body #11 → 45 µg/Nm³, kèm nhắc µg/m³ (đo) ≠ µg/Nm³ (QCVN).

### A-9 🟡 LOW — Issue #17 AC7 nói "17 issues", repo có 18

**Bằng chứng:** body Issue #17 AC7: *"đồ thị phụ thuộc của toàn bộ **17 issues** nhất quán"*;
repo có 18 issue (#1–#17 + **#19**, tạo 27/09 sau #17).

**Mức độ:** LOW — nhưng là kiểu inconsistency mà #17 chính thức sinh ra để bắt.
**Phụ trách:** Issue #17 (M6).
**Hành động:** sửa thành 18, hoặc giải thích #19 là issue bổ sung ngoài kế hoạch ban đầu.

---

# NHÓM B — ĐÃ BIẾT, CỐ Ý GIỮ / HOÃN CÓ LÝ DO

### B-1 AirNow DOS chưa bao giờ được ingest

`AirNowDOSAdapter` đã implement nhưng trạng thái tường minh `implemented / not_executed_pending_raw_input`
(PR #25). `doctor-cato` yêu cầu ở PR #24 rõ ràng phải ghi rõ điều này để không ai hiểu nhầm.
**Lý do hoãn:** cần credential AirNow-Tech (cơ quan Bộ Ngoại giao Mỹ).
**Hệ quả:** **không có dữ liệu AQ lịch sử 2023–2024** → cửa sổ nghiên cứu chỉ còn 2025-07-03 → 2026-07-15.
Đây là hạn chế lớn nhất của toàn bộ đồ án, cần nêu thẳng trong báo cáo #16.

### B-2 Dead code trong `merge_air_weather()` và `attach_high_humidity_flag()`

PR #34 ghi rõ: **cố ý không xoá** vì *"chạm các AC đã ghi nhận, cần quyết định riêng"*.
Đã xác minh trên `origin/main`: `attach_high_humidity_flag` vẫn còn ở `src/cleaning.py:986`;
`merge_air_weather` ở `src/cleaning_pipeline.py:561`.
**Trạng thái:** chờ một decision record riêng.

### B-3 `SimpleImputer` điền median cho 6 cột khí tượng toàn NaN — đã có guard nhưng chưa có test thực thi end-to-end

Đã thêm `keep_empty_features=True` ở `src/cleaning_pipeline.py:405` + all-NaN guard trong `merge_air_weather`
(sau MAJOR 5 của PR #33). **Đã sửa** — ghi ở đây để theo dõi: guard này chỉ được kiểm chứng bằng unit test,
chưa chạy trên tình huống lệch khoá thật với dữ liệu thật.

### B-4 Ba notebook cùng tiền tố `03_`

`03_data_cleaning.ipynb`, `03_transformation_pipeline.ipynb`, `03_processed_data_preview.ipynb`.
Trong khi `.agents/workflows/notebook.md:47-52` và `AGENTS.md` mô tả chuỗi `00`→`06` với
`02_quality_audit_cleaning.ipynb` và `03_exploratory_data_analysis.ipynb` — **không tồn tại trên đĩa**.

### B-5 `.agents/workflows/notebook.md` và `AGENTS.md` mô tả notebook không tồn tại

Đã xác minh: `.agents/workflows/notebook.md` dòng 42 nói *"Check if the notebook exists in `notebooks/` (`01_` through `06_`)"*
và dòng 48–52 liệt kê `02_quality_audit_cleaning`, `03_exploratory_data_analysis`, `04_statistical_inference`,
`05_regression_modeling`, `06_classification_alerts`.
Trên đĩa chỉ có 6 notebook: `00`, `01`, `02_quality_audit`, `03_data_cleaning`, `03_processed_data_preview`, `03_transformation_pipeline`.
→ **Issue #17 AC2 "chuỗi notebook 01→06 thực thi thông suốt" hiện không thể thực hiện được**, và AC4 của #17
*"README + docs đồng bộ 100%, không link hỏng"* đang vi phạm ở chính `.agents/workflows/notebook.md`.

### B-6 Mốc cắt `2026-01-15` không phải tối ưu tuyệt đối

Đã ghi rõ trong Quyết định 1: `2026-01-01` thắng ở **cả hai** tiêu chí đã nêu
(event coverage 181 vs 99; `p90_test/train` 0,97 vs 0,80). Giữ `2026-01-15` vì lý do
**tính đại diện theo mùa** (cả Train và Test đều chứa mùa đông; tập chỉ có **đúng một chu kỳ mùa**).
Đây là **quyết định có lý do**, không phải lỗi. Nhưng phải trả lời được khi phản biện ở #16.

---

# NHÓM C — CHƯA AI GHI NHẬN (nghi vấn của audit này)

> Đây là các điểm **audit này phát hiện**, chưa có bản ghi trong issue, PR hay comment nào.
> Mỗi mục đều cần người khác kiểm chứng độc lập trước khi hành động.

### C-1 🔴 CÓ THỂ CAO — Nhánh `cyc`/`passthrough` của ColumnTransformer **không được `validate_no_leakage()` bảo vệ**

**Bằng chứng:** `validate_no_leakage()` dựa trên `_learned_arrays()` duyệt cây `named_steps` để so tham số đã học.
Nhưng PR #34 tự ghi nhận: *"target/duplicate-column guards in the **cyclical** branch
(cyclical passes through `passthrough` so `validate_no_leakage()` cannot catch it)"*.
→ **Cột cyclical đi qua `passthrough`, không có tham số học nào để so.**
Nếu ai đó vô tình thêm `pm25` hoặc một biến phụ thuộc tương lai vào `CYCLICAL_FEATURES`,
guard sẽ **im lặng bỏ qua**.

**Mức độ:** CAO — đây là "ranh giới #1" (chronological split) mà review từng yêu cầu phải bắt được.
**Hành động:** thêm guard riêng cho nhánh passthrough: khẳng định `set(cyc_cols) ∩ {target, timestamp, station_id} = ∅`
và khẳng định mọi cột cyclical là hàm **thuần túy của timestamp** (không đọc được biến khác).

### C-2 🟠 CÓ THỆ CAO — Test 311 nhưng **không có công cụ đo coverage trong CI**

**Bằng chứng:** `python -c "import coverage"` → **Traceback: No module named 'coverage'**.
`requirements.txt` không có `coverage`/`pytest-cov`; `.github/workflows/ci.yml` không có bước đo coverage.
→ Số test tăng mạnh (14 → 39 → 57 → 80 → 259 → 311) nhưng **không biết tỉ lệ code được thực thi**.
Lịch sử cho thấy điều này quan trọng: mutation audit ở PR #34 phát hiện
`flag_stuck_values()`, `no_negative_values`, `temporal_grid_completeness` đều có **coverage 0 hoặc không test**.

**Mức độ:** CAO — là nguyên nhân gốc của cả họ lỗi "test có tên nhưng không kiểm chứng được".
**Hành động:** thêm `coverage.py` + `--cov=src --cov-report=term-missing --cov-fail-under=<ngưỡng>`
và `requirements-dev.txt`; đặt ngưỡng ban đầu bằng **giá trị hiện tại** (đo trước, rồi đặt) chứ không tự ý đặt 80%.

### C-3 🟠 CÓ THỆ CAO — `docs/data_quality_audit.md` chưa có cột "nguồn" (source) như AC #5 yêu cầu

**Bằng chứng:** AC #5 mục 4: *"Mẫu hình khuyết thiếu, cụm hóa theo thời gian, **khác biệt theo trạm/nguồn** phân tích chi tiết"*.
Review vòng 1 của PR #27 nêu đúng: *"Issue #5 requires missingness by station and source; reusable functions only covered
diurnal/missing-blocks/co-missingness"* → tác giả đã sửa *"station/source metrics added"*.
Nhưng dữ liệu hiện tại chỉ có **một trạm duy nhất** (`station_id.nunique() == 1`) và **một nguồn AQ duy nhất**
(OpenAQ 4946811; AirNow chưa ingest) → **chiều "nguồn" không thể kiểm chứng bằng dữ liệu thật**,
nên AC đó về mặt thực tiễn **không đạt dù code có hàm**.

**Mức độ:** CAO — AC được tick/đóng nhưng bất khả thi với dữ liệu hiện tại. Sẽ bị hỏi ở #17.
**Hành động:** ghi rõ trong `docs/data_quality_audit.md` §5: chiều source chỉ được *thiết kế*, chưa *kiểm chứng*;
AC #5 mục 4 đánh giá là **đạt một phần** (station: đạt vì đã audit timestamp-aware; source: chưa kiểm chứng được).

### C-4 🟠 TRUNG BÌNH — `pm25_was_stuck` là cột hằng 0 → `RobustScaler` trên nó là vô nghĩa

**Bằng chứng:** PR #32 ghi `pm25_was_stuck` **= 0 hàng**; PR #34 xác nhận `nunique = 1`.
Nhưng cột vẫn nằm trong dataset và được `RobustScaler` xử lý (`scale_=1.0, center_=0.0, output 0.0`).
Một hằng số sau scaler **không mang thông tin** nhưng vẫn **chiếm 1 chiều trong feature vector**
và có thể gây nhiễu khi VIF/coefficient được tính ở #12.

**Mức độ:** TRUNG BÌNH.
**Hành động:** giữ cột trong dataset (đúng — là bằng chứng), nhưng thêm vào nhóm **loại khỏi features mặc định**
với lý do riêng ("hằng số 0 trên tập Hà Nội"), tách khỏi `TARGET_DERIVED_FLAGS` và `NON_PREDICTIVE_FLAGS`.

### C-5 🟠 TRUNG BÌNH — Test `test_the_flag_group_documents_the_seasonal_interaction` **bảo vệ bằng chuỗi con**

**Bằng chứng:** PR #34 mô tả test này là bắt buộc khối giải thích chứa `marginal`, `F = 16,78`, `tương tác`.
→ Đây là **assert trên text**, không phải hành vi. Đổi `F = 16,78` thành `F = 16.8` là test fail
dù thông điệp vẫn đúng; giữ nguyên string nhưng xoá số liệu thì test vẫn xanh.

**Mức độ:** TRUNG BÌNH — không sai, nhưng không chống được rút gọn thông điệp theo kiểu mà chính PR #34 cảnh báo
(*"never write 'không dự báo được' for an absolute negation"*).
**Hành động:** giữ assert chuỗi, **bổ sung** một test hành vi tách theo mùu khẳng định dấu đảo chiều
(Đông dương, Xuân âm) với CI-friendly threshold thay vì p-value cứng.

### C-6 🟡 THẤP — `render_cleaning_log()` **đã có** test, nhưng không test nào đối chiếu với file đã commit

**Bằng chứng đã kiểm chứng:** `tests/test_cleaning.py` có **18 chỗ tham chiếu** `render_cleaning_log`,
trong đó có `test_log_is_deterministic_and_carries_no_wall_clock_timestamp` và
`test_log_uses_relative_paths_not_machine_specific_ones` → phần "tái lập byte-for-byte" **ĐÃ được test bảo vệ**.
Phần chưa có: **không test nào render rồi so với `docs/cleaning_log.md` đã commit trong repo.**
Nghĩa là nếu ai sửa tay file markdown, hoặc merge conflict làm lệch, không có gì phát hiện.

**Mức độ:** THẤP — nhỏ hơn nhiều so với nhận định ban đầu khi chưa đọc kỹ test.
**Hành động:** thêm test đối chiếu byte giữa output của `render_cleaning_log()` và file đã commit,
hoặc ghi rõ trong `docs/cleaning_log.md` rằng đây là **generated artifact — không sửa tay**.

### C-7 🟡 THẤP — CI không chạy notebook 00 trên PR nào chưa merge, nhưng **không chạy notebook 01+** vẫn để lọt lỗi JSON cấp tầng dữ liệu

**Bằng chứng:** PR #32 bổ sung bước "mọi `.ipynb` phải là JSON hợp lệ" sau khi
`03_transformation_pipeline.ipynb` có **hai chuỗi JSON nối vào nhau** khiến Jupyter không mở được —
và nó sống sót vì `notebook-smoke` chỉ chạy notebook 00.
Đây là fix đúng. **Nhưng** `03_processed_data_preview.ipynb` và `03_data_cleaning.ipynb` phụ thuộc
artifact gitignored (`data/raw/`, `data/interim/`, `data/processed/`) nên **không thể chạy trong CI**
mà không tải dữ liệu. Kết quả: **phần lớn logic cốt lõi chỉ được kiểm chứng bằng unit test, không có integration test trong CI.**

**Mức độ:** THẤP–TRUNG BÌNH.
**Hành động (nếu muốn nâng):** thêm job CI thứ hai tải dữ liệu qua `scripts/fetch_dataset.py` rồi
`nbconvert --execute` notebook 02 + 03_data_cleaning (offline sau khi tải) — ước ~10–15 phút/job.

---

## Phụ lục — Lệnh tái kiểm chứng toàn bộ findings trên

```powershell
# A-4 / A-5 — số test thật vs README
python -m unittest discover tests            # kỳ vọng: Ran 311 tests
git show origin/main:README.md | Select-String '259'   # kỳ vọng: còn dòng 259

# A-9 — issue #17 AC7
gh issue view 17 --json body --jq '.body' | Select-String '17 issues'

# A-8 — issue #11 ngưỡng QCVN
gh issue view 11 --json body --jq '.body' | Select-String '50 µg'

# A-6 — AC chưa tick
gh issue view 5  --json body --jq '.body' | Select-String '\[ \]' | Measure-Object
gh issue view 6  --json body --jq '.body' | Select-String '\[ \]' | Measure-Object

# C-1 — nhánh passthrough trong ColumnTransformer
Select-String -Path src/cleaning_pipeline.py -Pattern 'passthrough|CYCLICAL_FEATURES'

# C-2 — không có coverage
python -c "import coverage"

# C-4 — pm25_was_stuck là hằng số
Select-String -Path src/cleaning.py -Pattern 'pm25_was_stuck'

# C-6 — cleaning log tái lập byte-for-byte, test nào bảo vệ?
Select-String -Path tests/*.py -Pattern 'render_cleaning_log'

# B-4 / B-5 — notebook không tồn tại
Get-ChildItem notebooks -Name
Select-String -Path .agents/workflows/notebook.md -Pattern '0[0-9]_'
```

---

## Bối cảnh audit này chạy trên

| Mục | Giá trị |
|---|---|
| Ngày | 2026-10-03 |
| Base | `origin/main` = `76a6a61` (PR #34 merged 30/09 10:42 UTC) |
| PR đang mở | #35 (docs sync, chưa review) |
| Test suite | 311 test, 6.534s, OK |
| Coverage tool | **không có** |
| LOC `src/` | 4832 (cleaning 1805 · data_collection 1233 · cleaning_pipeline 1069 · data_quality 724) |
| LOC `tests/` | 3923 |
| Issue | 18 (8 đóng, 10 mở) · PR 18 (13 merged, 3 closed, 1 open, 1 chưa có nội dung) |