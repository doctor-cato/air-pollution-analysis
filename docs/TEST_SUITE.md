# Test Suite — Cấu hình, Đếm & Giới hạn

> Tài liệu tham chiếu cho **bộ kiểm thử tất định** của repository.
> `AGENTS.md` chỉ trỏ tới đây; con số kiểm thử thay đổi theo từng Issue nên
> không nhân bản vào file hướng dẫn agent.
>
> **Cập nhật lần cuối:** 2026-10-15, tại commit `7a1ccf8`.

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
| `tests/test_pipeline_runtime_log.py` | 40 | Nhật ký thực thi pipeline, dấu phân cách Windows |
| `tests/test_validate_issue8.py` | 28 | Checksum, đồng bộ generator, circular stats, smoke fixture, canh số liệu tài liệu |
| `tests/test_verify_claims_rolling.py` | 7 | Biên rolling 24h — dữ liệu đồng nhất che lỗi |
| **Tổng** | **430** | |

Đếm lại sau mỗi thay đổi:

```bash
python -m unittest discover tests 2>&1 | grep "^Ran"
```

---

## 3. ⚠ Ba con số khác nhau — đừng nhầm

Đây là điểm hay gây sai lệch nhất khi báo cáo kết quả kiểm thử.

| Con số | Ý nghĩa |
|---|---|
| **430** | Số **test method được định nghĩa** trong mã nguồn |
| **426** | Số unittest **thực sự chạy và báo cáo** trên CI (thiếu `data/`) |
| **421** | Số **pass thực sự** trên CI (426 − 5 skip) |

### Kết quả thực tế theo môi trường

| Môi trường | Lệnh | Kết quả |
|---|---|---|
| Windows local, **có `data/`** | `python -m unittest discover tests` | `Ran 430 tests` + `OK` → **430 pass, 0 skip** |
| Ubuntu CI `ubuntu-latest`, **không `data/`** | `python -m unittest discover tests -v` | `Ran 426 tests` + `OK (skipped=5)` → **421 pass, 5 skip** |

> `data/` bị `.gitignore` loại khỏi repository, nên **CI không bao giờ có dataset**.

### Vì sao 430 − 426 = 4

`TestDocumentedReproduction.setUpClass` trong `tests/test_flag_evidence.py` raise
`unittest.SkipTest` khi thiếu `data/interim/*.parquet`. unittest bỏ qua **cả class**,
và **4 method** của class đó không bao giờ được tính vào bộ đếm `Ran`.

Phân biệt rõ: chúng **không chạy** (không tính vào `Ran`) chứ không phải **chạy rồi bị skip**.

---

## 4. Năm skip trên CI

| # | Test | Lý do |
|---|---|---|
| 1 | `setUpClass (test_flag_evidence::TestDocumentedReproduction)` | Thiếu `data/interim/*.parquet` |
| 2 | `test_progress_report_bullet_carries_the_computed_f_statistic` | Cùng lý do |
| 3 | `test_windows_separators_in_payload_are_preserved_verbatim` | `skipUnless(os.name == "nt")` |
| 4 | `test_metadata_block_and_runtime_log_disagree_on_separators` | `skipUnless(os.name == "nt")` |
| 5 | `TestNotebookExecutionOutputs.test_live_restart_kernel_and_run_all` | Thiếu `data/processed/air_pollution_final.parquet` |

Skip 3 và 4 là **giới hạn nền tảng có chủ đích**: bất biến dấu phân cách chỉ tồn tại
trên Windows. Chạy trên Windows thì 2 test này **chạy thật**, nên máy local báo
`skipped=0`, còn CI báo `skipped=5`. Không phải regression.

Không skip nào là do lỗi. Không có test nào skip vì "chưa viết xong".

### Chạy lại nhóm cần dataset

```bash
python scripts/fetch_dataset.py          # cần network, một lần
python -m unittest tests.test_flag_evidence -v
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