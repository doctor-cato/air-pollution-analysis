# Test Suite — Cấu hình, Đếm & Giới hạn

> Tài liệu tham chiếu cho **bộ kiểm thử tất định** của repository.
> `AGENTS.md` chỉ trỏ tới đây; con số kiểm thử thay đổi theo từng Issue nên
> không nhân bản vào file hướng dẫn agent.
>
> **Cập nhật lần cuối:** sau Issue #50, Issue #12 (W10 — hồi quy OLS) và Issue #13 (W11 — phân loại cảnh báo).

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
| `tests/test_classification.py` | 24 | Phân loại cảnh báo ô nhiễm (Issue #13): nhãn 24h, 2 mẫu số & 4 quần thể, past-only features trên lưới 1h, PR-AUC average precision, tuning F2 không đột biến mô hình, ablation đa phạm vi & horizon có purge gap, xử lý 1 lớp (`UNESTIMABLE`), 4-fold leakage audit |
| `tests/test_cleaning.py` | 114 | Làm sạch tất định, `assert_no_imputation()`, cờ chẩn đoán |
| `tests/test_cleaning_pipeline.py` | 44 | Merge, freeze, split tuần tự, chống rò rỉ |
| `tests/test_cleaning_pipeline_guards.py` | 43 | Guard chống rò rỉ (`validate_no_leakage`) |
| `tests/test_data_collection.py` | 72 | Ingest OpenAQ / Open-Meteo / AirNow, provenance, SHA-256, fail-closed S3 cache preservation |
| `tests/test_data_quality.py` | 44 | Kiểm toán chất lượng 6 chiều |
| `tests/test_extended_reanalysis.py` | 22 | Hợp đồng Issue #50: tách trạm, rolling theo trạm, QC sáu chiều, bootstrap, FIG-03 full-calendar và đối chiếu artifact |
| `tests/test_extended_validation_mutations.py` | 16 | Kiểm thử mutation: structural không cần dữ liệu, semantic chỉ với Parquet thật; kiểm tra status, CI, provenance và so sánh |
| `tests/test_fetch_dataset.py` | 9 | `scripts/fetch_dataset.py` |
| `tests/test_flag_evidence.py` | 44 | Bằng chứng tái lập được cho `is_high_humidity_fog` |
| `tests/test_inference.py` | 218 | W9 — Holm, effect size, chẩn đoán phân phối, QCVN; **bootstrap theo lịch ngày** (mặt nạ thiếu, nhãn theo vị trí đích), **HAC/Newey–West**, kiểm chứng **Monte Carlo đa kịch bản**, chẩn đoán khái quát hóa, guard `station_id` — số liệu thật: `TestRealDataset` |
| `tests/test_issue44_preparation.py` | 17 | CP2/CP3 derived interpolation, masking metrics, winter/station boundaries, comparison report verification & mutation tests |
| `tests/test_pipeline_runtime_log.py` | 40 | Nhật ký thực thi pipeline, dấu phân cách Windows |
| `tests/test_profile_airnow_mirror.py` | 8 | CP0 pinned blobs, path preservation, period-aware duplicates/conflicts, QC and source-window gaps (synthetic) |
| `tests/test_regression.py` | 23 | Hồi quy OLS & LINE (Issue #12): split tuần tự tách trạm Protocol A, từ chối Protocol B, VIF, Ramsey RESET + 4 giả định LINE, Outliers/Leverage/Cook's D, Ridge/Lasso TimeSeriesSplit fold-level không rò rỉ, HAC lag sensitivity, ablation, derived interpolation sensitivity |
| `tests/test_validate_issue8.py` | 29 | Checksum, đồng bộ generator, circular stats, smoke fixture, canh số liệu tài liệu |
| `tests/test_verify_claims_rolling.py` | 9 | Biên rolling 24h — dữ liệu đồng nhất che lỗi |
| `tests/test_visualizer.py` | 35 | Bộ 7 biểu đồ ấn phẩm FIG-01..FIG-07 (300 DPI, Tufte, zero-baseline, chuỳ 24h, font tiếng Việt) |
| **Tổng** | **811** | |

Đếm lại sau mỗi thay đổi:

```bash
python -m unittest discover tests 2>&1 | grep "^Ran"
```

---

## 3. ⚠ Ba con số khác nhau — đừng nhầm

Đây là điểm hay gây sai lệch nhất khi báo cáo kết quả kiểm thử.

| Con số | Ý nghĩa |
|---|---|
| **811** | Số **test method được định nghĩa** trong mã nguồn |
| **785** | Số unittest **dự kiến chạy và báo cáo** trên CI (thiếu `data/`; 811 − 26 trong 5 lớp skip) |
| **781** | Số test **dự kiến chạy và pass** trên CI (785 − 4 skip nằm trong `Ran`) |

> ⚠ **`skipped=9` không trừ thẳng vào `Ran`.** Năm trong chín dòng skip là *class holder*
> (`setUpClass` raise `SkipTest`): unittest bỏ qua cả class nên các method của nó **không
> bao giờ vào `Ran`**, nhưng vẫn hiện một dòng trong `skipped=`. Vì vậy
> `pass = Ran − (skipped − holders)`. Ví dụ ở snapshot Issue #50 trước khi thêm #12–#13: `740 − (7 − 3) = 736`, **không phải** `740 − 7`.
>
> Đính chính: bản trước của tài liệu này ghi `462 − 5 = 457`, tức đã trừ cả holder và
> **đếm thiếu 1** so với số test thật sự chạy-pass (đúng phải là `462 − 4 = 458`).
> Định nghĩa "pass" nay được viết rõ để lỗi đó không lặp lại.

### Kết quả thực tế theo môi trường

| Môi trường | Lệnh | Kết quả |
|---|---|---|
| Windows local, **có `data/`**, 2026-11-11 (Issue #50 baseline) | `.venv\Scripts\python.exe -W ignore::DeprecationWarning -m unittest discover tests -q` | **Thực chạy** `Ran 764 tests in 194.248s` + `OK` → **764 pass, 0 skip** |
| Ubuntu CI `ubuntu-latest`, **không `data/`**, run 43051282775 (Issue #50 baseline) | `python -m unittest discover tests -v` | **Thực chạy** `Ran 740 tests in 152.400s` + `OK (skipped=7)` → **736 pass, 7 skip (3 holder)** |

> `data/` bị `.gitignore` loại khỏi repository, nên **CI không bao giờ có dataset**.

### Vì sao 811 − 785 = 26

Năm lớp có `setUpClass` raise `unittest.SkipTest` khi thiếu dữ liệu, và unittest bỏ qua
**cả class** — mọi method của chúng không bao giờ được tính vào bộ đếm `Ran`:

| Lớp | File | Method không vào `Ran` | Điều kiện |
|---|---|---|---|
| `TestDocumentedReproduction` | `tests/test_flag_evidence.py` | 4 | thiếu `data/interim/*.parquet` |
| `TestRealDataset` | `tests/test_inference.py` | 12 | thiếu `data/processed/air_pollution_final.parquet` |
| `TestSemanticMutations` | `tests/test_extended_validation_mutations.py` | 8 | thiếu `data/processed/air_pollution_extended_2022_2026.parquet` |
| `TestRegressionRealDataset` | `tests/test_regression.py` | 1 | thiếu `data/processed/air_pollution_final.parquet` |
| `TestClassificationRealDataset` | `tests/test_classification.py` | 1 | thiếu `data/processed/air_pollution_final.parquet` |
| | | **26** | |

Phân biệt rõ: chúng **không chạy** (không tính vào `Ran`) chứ không phải **chạy rồi bị skip**.

---

## 4. Chín skip trên CI

| # | Test | Lý do |
|---|---|---|
| 1 | `setUpClass (test_flag_evidence::TestDocumentedReproduction)` | Thiếu `data/interim/*.parquet` |
| 2 | `setUpClass (test_inference::TestRealDataset)` | Thiếu `data/processed/air_pollution_final.parquet` |
| 3 | `setUpClass (test_extended_validation_mutations::TestSemanticMutations)` | Thiếu extended Parquet |
| 4 | `setUpClass (test_regression::TestRegressionRealDataset)` | Thiếu `data/processed/air_pollution_final.parquet` |
| 5 | `setUpClass (test_classification::TestClassificationRealDataset)` | Thiếu `data/processed/air_pollution_final.parquet` |
| 6 | `test_progress_report_bullet_carries_the_computed_f_statistic` | Cùng lý do thiếu `data/interim/` |
| 7 | `test_windows_separators_in_payload_are_preserved_verbatim` | `skipUnless(os.name == "nt")` |
| 8 | `test_metadata_block_and_runtime_log_disagree_on_separators` | `skipUnless(os.name == "nt")` |
| 9 | `TestNotebookExecutionOutputs.test_live_restart_kernel_and_run_all` | Thiếu `data/processed/air_pollution_final.parquet` |

Dòng 1–5 là **class holder**: chúng đại diện cho cả lớp bị bỏ qua, và các method
bên trong **không** được tính vào `Ran` (xem §3).

Skip 7 và 8 là **giới hạn nền tảng có chủ đích**: bất biến dấu phân cách chỉ tồn tại
trên Windows. Chạy trên Windows thì 2 test này **chạy thật**, nên máy local báo
`skipped=0`, còn CI báo `skipped=9`. Không phải regression.
Job `validate` (ubuntu) luôn skip hai test này; job CI riêng `windows-paths`
(`windows-latest`) chạy `tests.test_pipeline_runtime_log` để chúng **thực sự được kiểm**
trên mỗi push/PR.

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
| Mutation tests và tính lại toàn bộ QC/profile/inference Issue #50 trên Parquet thật | `test_extended_validation_mutations::TestSemanticMutations` và `scripts/validate_extended_reanalysis.py --real-data` (local) |
| Số liệu W9 trong notebook 05 và `reports/inference_results.md` khớp dữ liệu thật | `test_inference::TestRealDataset` (local) |
| Notebook 05 chạy trên **9.044 dòng thật** | `test_live_restart_kernel_and_run_all` (local) |
| Mô hình OLS/LINE W10 trên dữ liệu thật (`VN001` & `VN003`) trong notebook 06 & `reports/regression_results.md` | `test_regression::TestRegressionRealDataset` (local) |
| Mô hình phân loại cảnh báo W11 trên dữ liệu thật (`VN001` & `VN003`) trong notebook 07 & `reports/classification_results.md` | `test_classification::TestClassificationRealDataset` (local) |

> **Ngược lại — những gì CI *có* kiểm chứng được cho W9:** các phép kiểm hiệu chỉnh phụ
> thuộc thời gian chạy trên dữ liệu **tổng hợp** nên CI kiểm được: hiệp phương sai HAC
> khớp `statsmodels` (`TestNeweyWestCovariance`), null bootstrap dựng dưới H₀ và bất biến
> dịch chuyển (`TestNullImposedTest`), **bootstrap theo lịch** giữ mặt nạ thiếu và không
> tạo quan sát giả (`TestCalendarBlockIndices`, `TestCalendarReplicates`,
> `TestCalendarNullTestWithGaps`), hợp đồng của kiểm chứng Monte Carlo
> (`TestMonteCarloValidation`), hiệu chỉnh Holm khớp `statsmodels`
> (`TestHolmMatchesStatsmodels`), và cấu trúc notebook ↔ generator
> (`TestNotebookGeneratorMatchesNotebook`). CI **không** kiểm được *số liệu thật* của W9.
>
> **Kiểm chứng Monte Carlo đầy đủ** (1.000 lần × 9 kịch bản) là **công việc khoa học có
> chi phí**, chạy bằng `python scripts/validate_inference_montecarlo.py --n-sim 1000`; kết quả
> được commit ở `reports/inference_montecarlo.csv` và **không** chạy lại trong CI.

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
