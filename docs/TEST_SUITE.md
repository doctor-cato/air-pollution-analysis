# Test Suite — Cấu hình, Đếm & Giới hạn

> Tài liệu tham chiếu cho **bộ kiểm thử tất định** của repository.
> `AGENTS.md` chỉ trỏ tới đây; con số kiểm thử thay đổi theo từng Issue nên
> không nhân bản vào file hướng dẫn agent.
>
> **Cập nhật lần cuối:** 2026-10-20, sau Issue #11 (W9 — suy luận thống kê).

---

## 1. Cách chạy

```bash
# Toàn bộ suite
python -m unittest discover tests

# Một module
python -m unittest tests.test_validate_issue8 -v

# Một test cụ thể
python -m unittest tests.test_validate_issue8.TestNotebookFixtureSmoke -v
```

Không test nào gọi mạng. Không test nào phụ thuộc thứ tự chạy.

---

## 2. Bố cục theo module

| Module | Test methods | Phạm vi |
|---|---|---|
| `tests/test_data_collection.py` | 57 | Ingest OpenAQ / Open-Meteo / AirNow, provenance, SHA-256 |
| `tests/test_cleaning.py` | 114 | Làm sạch tất định, `assert_no_imputation()`, cờ chẩn đoán |
| `tests/test_data_quality.py` | 44 | Kiểm toán chất lượng 6 chiều |
| `tests/test_cleaning_pipeline.py` | 44 | Merge, freeze, split tuần tự, chống rò rỉ |
| `tests/test_cleaning_pipeline_guards.py` | 43 | Guard chống rò rỉ (`validate_no_leakage`) |
| `tests/test_fetch_dataset.py` | 9 | `scripts/fetch_dataset.py` |
| `tests/test_flag_evidence.py` | 44 | Bằng chứng tái lập được cho `is_high_humidity_fog` |
| `tests/test_inference.py` | 155 | W9 — Holm, block bootstrap, effect size, chẩn đoán phân phối, QCVN; **hiệu chỉnh phụ thuộc thời gian** (HAC/Newey–West, null block bootstrap, mô phỏng size, chẩn đoán khái quát hóa) — số liệu thật: `TestRealDataset` |
| `tests/test_pipeline_runtime_log.py` | 40 | Nhật ký thực thi pipeline, dấu phân cách Windows |
| `tests/test_validate_issue8.py` | 29 | Checksum, đồng bộ generator, circular stats, smoke fixture, canh số liệu tài liệu |
| `tests/test_verify_claims_rolling.py` | 7 | Biên rolling 24h — dữ liệu đồng nhất che lỗi |
| `tests/test_visualizer.py` | 35 | Bộ 7 biểu đồ ấn phẩm FIG-01..FIG-07 (300 DPI, Tufte, zero-baseline, chuỳ 24h, font tiếng Việt) |
| **Tổng** | **621** | |

Đếm lại sau mỗi thay đổi:

```bash
python -m unittest discover tests 2>&1 | grep "^Ran"
```

---

## 3. ⚠ Ba con số khác nhau — đừng nhầm

Đây là điểm hay gây sai lệch nhất khi báo cáo kết quả kiểm thử.

| Con số | Ý nghĩa |
|---|---|
| **621** | Số **test method được định nghĩa** trong mã nguồn |
| **607** | Số unittest **thực sự chạy và báo cáo** trên CI (thiếu `data/`) |
| **603** | Số test **chạy và pass** trên CI (607 − 4 skip nằm trong `Ran`) |

> ⚠ **`skipped=6` không trừ thẳng vào `Ran`.** Hai trong sáu dòng skip là *class holder*
> (`setUpClass` raise `SkipTest`): unittest bỏ qua cả class nên các method của nó **không
> bao giờ vào `Ran`**, nhưng vẫn hiện một dòng trong `skipped=`. Vì vậy
> `pass = Ran − (skipped − holders) = 607 − (6 − 2) = 603`, **không phải** `607 − 6`.
>
> Đính chính: bản trước của tài liệu này ghi `462 − 5 = 457`, tức đã trừ cả holder và
> **đếm thiếu 1** so với số test thật sự chạy-pass (đúng phải là `462 − 4 = 458`).
> Định nghĩa "pass" nay được viết rõ để lỗi đó không lặp lại.

### Kết quả thực tế theo môi trường

| Môi trường | Lệnh | Kết quả |
|---|---|---|
| Windows local, **có `data/`** | `python -m unittest discover tests` | `Ran 621 tests` + `OK` → **621 pass, 0 skip** |
| Ubuntu CI `ubuntu-latest`, **không `data/`** | `python -m unittest discover tests -v` | `Ran 607 tests` + `OK (skipped=6)` → **603 pass, 6 skip (2 holder)** |

> `data/` bị `.gitignore` loại khỏi repository, nên **CI không bao giờ có dataset**.

### Vì sao 621 − 607 = 14

Hai lớp có `setUpClass` raise `unittest.SkipTest` khi thiếu dữ liệu, và unittest bỏ qua
**cả class** — mọi method của chúng không bao giờ được tính vào bộ đếm `Ran`:

| Lớp | File | Method không vào `Ran` | Điều kiện |
|---|---|---|---|
| `TestDocumentedReproduction` | `tests/test_flag_evidence.py` | 4 | thiếu `data/interim/*.parquet` |
| `TestRealDataset` | `tests/test_inference.py` | 10 | thiếu `data/processed/air_pollution_final.parquet` |
| | | **14** | |

Phân biệt rõ: chúng **không chạy** (không tính vào `Ran`) chứ không phải **chạy rồi bị skip**.

---

## 4. Sáu skip trên CI

| # | Test | Lý do |
|---|---|---|
| 1 | `setUpClass (test_flag_evidence::TestDocumentedReproduction)` | Thiếu `data/interim/*.parquet` |
| 2 | `setUpClass (test_inference::TestRealDataset)` | Thiếu `data/processed/air_pollution_final.parquet` |
| 3 | `test_progress_report_bullet_carries_the_computed_f_statistic` | Cùng lý do thiếu `data/interim/` |
| 4 | `test_windows_separators_in_payload_are_preserved_verbatim` | `skipUnless(os.name == "nt")` |
| 5 | `test_metadata_block_and_runtime_log_disagree_on_separators` | `skipUnless(os.name == "nt")` |
| 6 | `TestNotebookExecutionOutputs.test_live_restart_kernel_and_run_all` | Thiếu `data/processed/air_pollution_final.parquet` |

Dòng 1 và 2 là **class holder**: chúng đại diện cho cả lớp bị bỏ qua, và các method
bên trong **không** được tính vào `Ran` (xem §3).

Skip 4 và 5 là **giới hạn nền tảng có chủ đích**: bất biến dấu phân cách chỉ tồn tại
trên Windows. Chạy trên Windows thì 2 test này **chạy thật**, nên máy local báo
`skipped=0`, còn CI báo `skipped=6`. Không phải regression.

Không skip nào là do lỗi. Không có test nào skip vì "chưa viết xong".

### Chạy lại nhóm cần dataset

```bash
python scripts/fetch_dataset.py          # cần network, một lần
python -m unittest tests.test_flag_evidence -v
python -m unittest tests.test_inference -v
```

---

## 5. CI KHÔNG kiểm chứng được những gì

Đây là giới hạn thật, cần nói rõ khi báo cáo:

| Không được CI xác minh | Ai xác minh được |
|---|---|
| `F = 16,78` / `p = 7,4·10⁻¹¹` của fog × mùa | Local có `data/interim/` |
| Notebook 04 chạy trên **9.044 dòng thật** | `test_live_restart_kernel_and_run_all` (local) |
| Con số trong markdown takeaway của notebook 04 | `scripts/validate_issue8.py` (local) |
| `reports/statistical_profile.csv` khớp dữ liệu thật | `scripts/validate_issue8.py` (local) |
| Toàn bộ số liệu suy luận W9 (`H`, `p`, effect size, bootstrap CI) | `test_inference::TestRealDataset` (local) |
| Số liệu W9 trong notebook 05 và `reports/inference_results.md` khớp dữ liệu thật | `test_inference::TestRealDataset` (local) |
| Notebook 05 chạy trên **9.044 dòng thật** | `test_live_restart_kernel_and_run_all` (local) |

> **Ngược lại — những gì CI *có* kiểm chứng được cho W9:** các phép kiểm hiệu chỉnh phụ
> thuộc thời gian chạy trên dữ liệu **tổng hợp** nên CI kiểm được: hiệp phương sai HAC
> khớp `statsmodels` (`TestNeweyWestCovariance`), null bootstrap dựng dưới H₀ và bất biến
> dịch chuyển (`TestNullImposedTest`), **kiểm soát sai lầm loại I** bằng mô phỏng
> (`TestTypeIErrorControl`), hiệu chỉnh Holm khớp `statsmodels`
> (`TestHolmMatchesStatsmodels`), và cấu trúc notebook ↔ generator
> (`TestNotebookGeneratorMatchesNotebook`). CI **không** kiểm được *số liệu thật* của W9.

`TestNotebookFixtureSmoke` (3 test) chạy **cả 37 cell** của notebook 04 trên dữ liệu
**tổng hợp** tất định (seed 42, 4 cửa sổ 14 ngày theo 4 mùa, 1.344 dòng, schema 18 cột
canonical) → CI chứng minh notebook **chạy được**. Nó **không** chứng minh bất kỳ con
số nào là đúng, và không thay thế được bước kiểm chứng trên dữ liệu thật.

---

## 6. Quy tắc bất di bất dịch

1. **Không báo số method định nghĩa như số test đã pass.** Luôn nói rõ nền tảng và
   trạng thái `data/`.
2. **Không thêm test mà không kiểm chứng nó bắt được lỗi.** Inject lỗi có chủ đích,
   xem test FAIL, rồi hoàn nguyên. Một test chưa từng fail là một test chưa được chứng minh.
3. **Skip phải có lý do viết rõ trong thông điệp** — không bao giờ skip để né lỗi.
4. **Con số trong tài liệu này được test canh, đừng sửa tay.** `TestDocumentedTestCounts`
   đọc số `def test_` thật trong `tests/` rồi đối chiếu với bảng §2 và với con số
   trong `AGENTS.md`. Thêm test mà quên cập nhật tài liệu → test FAIL, có chủ đích.

---

## 7. Bảo trì

Sau khi thêm hoặc bỏ test:

1. `python -m unittest discover tests 2>&1 | grep "^Ran"`
2. Mô phỏng điều kiện CI trong clone sạch không có `data/`, chạy lại, lấy `Ran` và `skipped=`
3. Cập nhật §2 và §3 của tài liệu này
4. Cập nhật dòng "Test count semantics" trong `AGENTS.md` nếu con số thay đổi