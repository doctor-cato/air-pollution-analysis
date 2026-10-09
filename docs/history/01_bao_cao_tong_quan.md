# 01 — Báo cáo tổng quan: cách repo hoạt động & lịch sử phiên bản

> Ngày audit: 2026-10-03 · Base: `origin/main` = `76a6a61` (sau PR #34)

## 0. Trạng thái repo tại thời điểm đọc

| Mục | Giá trị |
|---|---|
| `origin/main` | `76a6a61` — đã merge PR #34 |
| Worktree audit | branch `docs/repo-history-audit`, base `origin/main` |
| Worktree gốc | branch `fix/pr33-processed-preview` @ `8681dee` — **stale, thiếu PR #32/#33/#34** |
| `main` cục bộ ở worktree gốc | `962457c` — **stale hơn nữa, chỉ tới PR #28-revert** |
| Số commit | 59 trên branch gốc |
| Unit test | **311 PASS** (`python -m unittest discover tests` → OK 6.5s) |
| Working tree gốc | `notebooks/03_processed_data_preview.ipynb` sửa chưa commit; `scripts/build_progress_report.py` + `docs/bao_cao_tien_do_M1_M2.docx` untracked |

**Milestone:** M1 đóng (5 issue) · M2 đóng (3 issue) · M3–M6 mở (10 issue). Tổng 18 issue: 8 đóng, 10 mở.

---

## 1. Kiến trúc — CRISP-DM với 3 tầng dữ liệu

```
data/raw/        Tầng A: payload thô tải về lúc chạy          (KHÔNG git-track)
                 Tầng B: data/raw/metadata.json               (git-track)
                          provenance · SHA-256 · URL · license · attribution
                 Tầng C: tệp thô không bắt buộc Git-track,
                          tái tạo qua scripts/fetch_dataset.py
   ↓
data/interim/    canonical parquet sau ingestion  (PR #24, #26)
                 canonical parquet sau cleaning   (PR #32)
   ↓
data/processed/  air_pollution_final.parquet sau pipeline #7 (gitignored)
```

Mọi `data/raw/*.parquet` và `data/processed/*.parquet` đều gitignore →
**fresh clone phải chạy `python scripts/fetch_dataset.py`** (không cần API key) trước khi chạy notebook 01+.

### 4 module `src/` (đo tại `origin/main`)

| Module | LOC | Vai trò | Entry point |
|---|---:|---|---|
| `src/data_collection.py` | 1233 | Thu thập + chuẩn hóa AQ & khí tượng | `run_collection_pipeline()`, `OpenAQAdapter`, `OpenMeteoAdapter`, `AirNowDOSAdapter` |
| `src/data_quality.py` | 724 | Kiểm toán 6 chiều, taxonomy missingness | `run_quality_audit_pipeline()`, `audit_six_dimensions()` |
| `src/cleaning.py` | 1805 | 16 bước làm sạch tất định | `run_deterministic_cleaning()`, `assert_no_imputation()` |
| `src/cleaning_pipeline.py` | 1069 | Merge AQ↔WX, split thời gian, sklearn pipeline chống rò rỉ | `freeze_dataset_with_audit()`, `validate_no_leakage()` |
| **Tổng** | **4832** | | |

### 6 file test (311 test)

| File | Test | LOC |
|---|---:|---:|
| `tests/test_cleaning.py` | 114 | 1211 |
| `tests/test_data_collection.py` | 57 | 803 |
| `tests/test_cleaning_pipeline.py` | 44 | 578 |
| `tests/test_data_quality.py` | 44 | 555 |
| `tests/test_cleaning_pipeline_guards.py` | 43 | 593 |
| `tests/test_fetch_dataset.py` | 9 | 183 |
| **Tổng** | **311** | **3923** |

---

## 2. Trình tự process thực thi

```
[0] pip install -r requirements.txt
[1] python scripts/fetch_dataset.py            # tải raw → data/raw/  (nếu chưa có)
[2] notebooks/00_environment_test.ipynb        # smoke test môi trường
[3] notebooks/01_data_collection.ipynb         # → data/interim/*_canonical.parquet
[4] notebooks/02_quality_audit.ipynb           # audit 6 chiều, READ-ONLY, TRƯỚC cleaning
[5] notebooks/03_data_cleaning.ipynb          # → data/interim/*_cleaned.parquet + docs/cleaning_log.md
[6] notebooks/03_transformation_pipeline.ipynb # → data/processed/air_pollution_final.parquet
[7] notebooks/03_processed_data_preview.ipynb  # xem dữ liệu đã xử lý (read-only)
```

**Bẫy đã ghi trong `AGENTS.md`:** muốn chạy lại `03_data_cleaning` phải khôi phục `data/interim/` từ `data/raw/` trước —
`reindex_hourly_grid()` cần trạng thái **trước cleaning**, không dùng được output của chính nó.

**Lưu ý đặt tên:** ba notebook khác nhau cùng mang tiền tố `03_` —
`03_data_cleaning`, `03_transformation_pipeline`, `03_processed_data_preview`.

### CI (`.github/workflows/ci.yml`)

```
compileall -q src tests scripts
  ↓
import sanity: src.data_collection · src.data_quality · src.cleaning · src.cleaning_pipeline
  ↓
python -m unittest discover tests -v
  ↓
validate mọi .ipynb là JSON hợp lệ (nbformat.read)
```

**Cố tình KHÔNG chạy:** `run_collection_pipeline()` (cần network OpenAQ S3 / Open-Meteo / AirNow, không deterministic),
và chỉ smoke-test notebook 00 chứ không execute notebook 01+.

---

## 3. Lịch sử theo từng phiên bản (diff theo merge commit)

| Version | Commit | PR | Nội dung | Dòng |
|---|---|---|---|---|
| v0.1 | `1e93df3` | — | Roadmap doc duy nhất | — |
| v0.2 | `e4a3e28` | #18 | Khởi tạo CRISP-DM: cây thư mục, `.gitignore`, `requirements.txt` pin PEP 508, notebook 00 | +382 / 10 files |
| v0.3 | `6ef5b7c`→`9486d1f` | — | MIT license, CONTRIBUTING, roster, project overview | ~6 commits |
| v0.4 | `025ea66`, `cc87d2c` | — | Đồng bộ roadmap 17-issue; thêm `.agents/` rules + workflows + skills | 2 commits |
| **M1** | | | | |
| v1.1 | `acd9a95` | #20 | `docs/research_questions.md` (Main RQ + SQ1–4), `docs/data_dictionary.md` (11 field × 8 thuộc tính) | +526 −5 / 3 files |
| v1.2 | `98c0ba4` | #21 | **Source Decision Gate**: `data/raw/metadata.json`, `docs/source_profiling_decision.md` (440 dòng) | +715 −77 / 5 files |
| v1.3 ⚠️ | `1985b3d` | #22 | Pipeline AQ — **merge trong 35 giây, 0 comment, 0 review** | +1438 −8 / 3 files |
| v1.4 ⚠️ | `c099622` | #23 | **REVERT #22 sau 16 giây** | −1438 +8 / 3 files |
| v1.5 | `6d6a10b` | #24 | Re-land #3 đúng: OpenAQ **4946811**, `AirNowDOSAdapter`, `filter_hanoi_bounds()`, `resolve_station_metadata()`, 7 test | +2075 −160 / 6 files |
| v1.6 | `818f410` | #25 | Dynamic temporal sync: cửa sổ khí tượng suy từ timeline AQ | +495 −139 / 6 files |
| v1.7 | `750e312` | #26 | Hoàn thiện khí tượng #4: validate units + tz IANA, **thêm GitHub Actions** | +1989 −361 / **20 files** |
| v1.8 | `38b9e5c` | #27 | **M2 khởi động**: `src/data_quality.py`, notebook 02, `docs/data_quality_audit.md` | +2403 / 4 files |
| v1.9 | `131dc86` | #28 | M1 cleanup: 14 test adapter + tách runtime log khỏi metadata | +462 −19 / 5 files |
| v1.10 ⚠️ | `962457c` | #28-revert | **REVERT #28** (theo PR #29) — mất 14 test adapter | −462 +19 / 5 files |
| v1.11 | `cef9ef9` | #30 | Sửa số liệu audit + `scripts/fetch_dataset.py` + 9 test | +583 −63 / 8 files |
| **M2** | | | | |
| v2.1 | `b3f0740` | #32 | **#6 + #7 ship chung**: `cleaning.py` + `cleaning_pipeline.py` + 3 test file + 2 notebook + `cleaning_log.md` | **+9921 −43 / 16 files** |
| v2.2 | `8681dee` | #33 | Notebook preview processed data (sau khi bị chặn vì stale base) | +718 / 1 file |
| v2.3 | `76a6a61` | #34 | Fix 1 bug thật + 2 sai số HIGH; loại `is_high_humidity_fog`; 259→311 test | +1505 −113 / 14 files |
| v2.4 | `33e7488` | #35 | **OPEN** — đồng bộ docs, xoá claim "mutation 100%" không tái lập được | +222 −94 / 17 files |

---

## 4. Ba sự cố nghiêm trọng nhất trong toàn bộ lịch sử

### ① OpenAQ `location_id=2178` — dữ liệu Mỹ, không phải Hà Nội (PR #22→#23→#24)

`2178` thực chất là **Del Norte High School, Albuquerque, New Mexico** (`35.1353, −106.584702`),
sao chép nhầm từ mã ví dụ trong tài liệu OpenAQ. PR #21 đã chốt nó là AQ Primary với khẳng định
"đã kiểm chứng là trạm Ba Đình, Hà Nội (21.0215N/105.8184E)".

- 29/09 07:06 — #22 merge, 35 giây, không review
- 29/09 07:08 — #23 revert, 16 giây
- 29/09 07:29 — #24 commit `a222766`: **thu hồi 100%**, thay bằng `4946811` (556 Nguyễn Văn Cừ, Long Biên, NCEM/VEA, 21.0491N/105.8831E)

Hệ quả dây chuyền: mất **14.424 dòng** dữ liệu Mỹ khỏi bài toán; mất toàn bộ **cửa sổ 2023–2024**
(OpenAQ chỉ tích hợp trạm này từ 07/2025); phải thêm `AirNowDOSAdapter` làm fallback cho lịch sử 2023;
cửa sổ thực tế còn lại **2025-07-03 → 2026-07-15**; code trong `src/data_collection.py` giờ có hằng số
`DISQUALIFIED_OPENAQ_LOCATION_ID = 2178` để chặn fail-fast nếu ai đó gọi lại.

### ② `assert_no_imputation()` là tautology (PR #32, phát hiện trong review đối kháng)

Cả `clean_air_quality()` lẫn `clean_weather()` đều gọi `assert_no_imputation(df, df, …)` —
so một DataFrame với chính nó. Tệ hơn: phép so số lượng ô cho phép một giá trị **bịa ra** đi qua
nếu số quan sát bị xoá đủ bù. Viết lại thành so **từng ô** trên khoá `(station_id, timestamp)`,
với snapshot thật chụp trước khi chạy: ô `NaN` trước phải `NaN` sau; ô có giá trị phải giữ nguyên
hoặc thành `NaN`; quan sát chỉ được biến mất, không được xuất hiện hay đổi giá trị.

### ③ Rò rỉ target có cấu trúc qua `pm25_was_missing` (PR #32 → phát hiện ở PR #34)

`pm25_was_missing == pm25.isna()`, mà `SimpleImputer(strategy="median")` lại điền median
**đúng những hàng đó** → mô hình học quy tắc `flag == 1 ⇒ pm25 == median` và đúng 100%.
Đo trên dữ liệu thật: **256/256 hàng Train**, **1033/1033 hàng Test**.

`validate_no_leakage()` **không thể bắt** vì nó chỉ so tham số học với refit trên Train —
cả hai đều học median một cách "đúng". Vì vậy phải chuyển cờ sang nhóm `TARGET_DERIVED_FLAGS`,
tách riêng khỏi `NON_PREDICTIVE_FLAGS` vì hai lý do loại hoàn toàn khác nhau.

---

## 5. Trục review thống nhất xuyên suốt toàn bộ lịch sử

1. **Evidence-based, không descriptive.** Mọi claim định lượng phải truy được về dữ liệu thật.
   Bắt buộc phân biệt 3 nhóm: *Direct Measurement* / *Not verifiable directly* / *Documented|Provider-reported*.
2. **`actual_*_timestamp` phải suy từ dữ liệu**, không hardcode. Phân biệt `requested_study_window`
   (tham số truy vấn) với `actual_min/max_timestamp` (đo được).
3. **Không giá trị nào bị loại mà không để lại dấu vết** → `df.attrs`, `cleaning_totals`, `warnings`.
4. **Geography phải là filter thật + assert**, không phải boolean check.
5. **Timezone phải là IANA identity `Asia/Ho_Chi_Minh`**, không phải offset `+07:00`
   (pandas biểu diễn `date_range("+07:00")` thành fixed offset → phải reject).
6. **Units validate từ `hourly_units` của raw response**, không giả định theo request.
7. **Test phải RED-first.** 36 test của #7 commit cùng code nên chứng minh không được gì;
   mutation score đo được 44,7%, mutant nguy hiểm nhất là `transform_with_pipeline()` refit
   trên chính Test mà **0/36 test bắt** — vì hai hàm đó chưa từng được test.

### Quy mô review đối kháng

| Đợt | Kết quả |
|---|---|
| #6 (Issue #6 cleaning) | 3 BLOCKER + 8 MAJOR + 8 MINOR/NIT — 18/20 test hồi quy FAIL trên bản gốc |
| #7 (vòng 1, Issue #7 pipeline) | 4 MAJOR |
| #7 (vòng 2, 5 reviewer độc lập) | 7 BLOCKER + phần lớn MAJOR — 34 test hồi quy mới, viết RED-first |
| #34 (vòng 1) | 2 điểm |
| #34 (vòng 2) | 1 điểm còn lại → dẫn tới phát hiện tương tác theo mùa |
| #33 (PR preview notebook) | 2 BLOCKER + 3 MAJOR + 3 MINOR, verdict "DO NOT MERGE as-is" |