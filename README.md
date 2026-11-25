# Phân Tích Mức Độ Ô Nhiễm Không Khí Theo Chuỗi Thời Gian

## Time-Series Air Pollution Analysis – Hà Nội, Việt Nam

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)  
> **Đơn vị:** Khoa Công nghệ Thông tin & Truyền thông, Trường Đại học CMC  
> **Giảng viên hướng dẫn:** ThS. Phạm Ngọc Đông  
> **Phương pháp luận:** Vòng đời CRISP-DM (6 giai đoạn)  
> **Nhóm thực hiện:** Nhóm Chủ đề 6 (*Topic 6 Team*)

### Thành viên Nhóm

| STT | Thành viên | Tài khoản GitHub | Vai trò |
|:---:|---|---|---|
| 1 | Huy | [@doctor-cato](https://github.com/doctor-cato) | Nhóm trưởng (*Leader*) |
| 2 | Khương | [@lekhuong123456798-cpu](https://github.com/lekhuong123456798-cpu) | Thành viên |
| 3 | Khánh | [@nguyenphanminhkhanh9a-netizen](https://github.com/nguyenphanminhkhanh9a-netizen) | Thành viên |
| 4 | Hưng | [@ViolaPeracia](https://github.com/ViolaPeracia) | Thành viên |
| 5 | Hùng | [@Izuki-1780N](https://github.com/Izuki-1780N) | Thành viên |

---

## 1. Tổng quan Đề tài

Dự án nghiên cứu biến thiên nồng độ bụi mịn $\text{PM}_{2.5}$ và mối liên hệ với các yếu tố khí tượng bề mặt tại Hà Nội theo vòng đời **CRISP-DM**, tập trung vào bốn câu hỏi nghiên cứu ([`docs/research_questions.md`](docs/research_questions.md)):

1. **Quy luật chu kỳ thời gian (EDA):** Phân tích biến động $\text{PM}_{2.5}$ theo chu kỳ ngày đêm (*diurnal*), ngày trong tuần (*weekday vs. weekend*) và mùa vụ (*seasonal*), đi kèm 4 họ chỉ số thống kê và bộ 7 biểu đồ ấn phẩm chuẩn Tufte/Cleveland.
2. **Suy luận thống kê có xét phụ thuộc thời gian:** Kiểm định giả thuyết ở cấp độ trung bình ngày ($\ge 18/24$ giờ) với **calendar block bootstrap** (khối 28 ngày lịch), hiệp phương sai HAC Newey–West, hiệu chỉnh đa kiểm định Holm–Bonferroni, kích thước hiệu ứng và kiểm chứng sai lầm loại I bằng mô phỏng Monte Carlo.
3. **Mô hình hóa hồi quy giải thích (OLS & Điều chuẩn):** Định lượng mối liên hệ quan sát (*associational, ceteris paribus*) giữa khí tượng và $\text{PM}_{2.5}$ bằng OLS (kèm sai số chuẩn HAC-24, kiểm tra 4 giả định LINE, VIF) và Ridge/Lasso qua `TimeSeriesSplit`.
4. **Phân loại cảnh báo đợt ô nhiễm:** Xây dựng bài toán phân loại nhị phân trên trung bình trượt 24 giờ $\overline{\text{PM}_{2.5}}_{[t-23, t]} \ge 50{,}0\,\mu\text{g/m}^3$ (tham chiếu ngưỡng QCVN 05:2023/BTNMT), tối ưu Recall và PR-AUC, hiệu chuẩn xác suất và kiểm toán 4 lớp rò rỉ dữ liệu. Lưu ý: dữ liệu khí tượng ERA5 có độ trễ phát hành ~5 ngày nên thiết lập tại $h=0$ mang bản chất truy hồi tức thời (*retrospective nowcast*), không phải dự báo vận hành thời gian thực.

---

## 2. Hiện trạng Triển khai & Lộ trình

### 2.1. Tổng hợp theo Milestone

| Giai đoạn | Phạm vi & Issue | Trạng thái | Thành phần chính |
|---|---|---|---|
| **Milestone 1** | Thiết lập dự án, Canonical Schema, Nguồn & Thu thập (#1, #2, #19, #3, #4) | **Hoàn thành** | `src/data_collection.py`, `notebooks/00`–`01`, `docs/data_dictionary.md`, `docs/source_profiling_decision.md` |
| **Milestone 2** | Kiểm toán 6 chiều, Làm sạch tất định, Pipeline chống rò rỉ (#5, #6, #7, #38) | **Hoàn thành** | `src/data_quality.py`, `src/cleaning.py`, `src/cleaning_pipeline.py`, `src/flag_evidence.py`, `notebooks/02`–`03` |
| **Milestone 3** | EDA 4 họ chỉ số & 7 biểu đồ ấn phẩm (#8, #9) | **Hoàn thành** | `src/visualizer.py`, `notebooks/04_descriptive_stats.ipynb`, `figures/FIG-01..07.png`, `reports/statistical_profile.csv` |
| **Mở rộng & Tái phân tích** | Mở rộng lịch sử 2022–2025 tách trạm & Tái phân tích M2/M3/W9 (#44, #50) | **Hoàn thành** | `src/issue44_preparation.py`, `src/extended_audit.py`, `src/reanalysis_validation.py`, `reports/extended_*`, `figures/extended/` |
| **Milestone 4** | Suy luận W9 (#11), Hồi quy OLS (#12), Phân loại cảnh báo (#13); (#10 đã đóng) | **Hoàn thành** | `src/inference.py`, `src/regression.py`, `src/classification.py`, `notebooks/05`–`07`, `reports/*_results.md` |
| **Milestones 5–6** | Bias Audit, Tài nguyên vs Spark, Datasheet, Model Card 1 trang, Bảo vệ (#14–#17) | **Kế hoạch** | Theo [`docs/roadmap.md`](docs/roadmap.md) và [`docs/TASK_LIST_M3_M6.md`](docs/TASK_LIST_M3_M6.md) |

### 2.2. Các điểm nhấn Kỹ thuật & Kiểm chứng

- **Làm sạch tất định vs. Tiền xử lý chống rò rỉ:** `src/cleaning.py` thực thi `assert_no_imputation()` (so từng ô theo khóa `(station_id, timestamp)` — không tự ý điền khuyết). `src/cleaning_pipeline.py` tách rạch ròi `TARGET_DERIVED_FLAGS` (`pm25_was_missing` — rò rỉ cấu trúc) và `NON_PREDICTIVE_FLAGS` (`is_high_humidity_fog` — bằng chứng tái lập tại `src/flag_evidence.py`), đồng thời kiểm chứng `validate_no_leakage()` và tầng kiểm tra thứ tự thời gian bắt buộc `verify_chronology()`.
- **Tách trạm nghiêm ngặt (Protocol A vs. Protocol B):** Tập baseline `VN001_HANOI_556_NGUYEN_VAN_CU` (07/2025–07/2026; `9.044` giờ lưới) và tập lịch sử mở rộng `VN003_HANOI_OPENAQ_7441` (01/2022–04/2025; `28.678` giờ lưới) không có quan sát chồng lấp; mọi phân tích và mô hình hóa đều khóa đơn trạm theo Protocol A, bảo toàn bất biến SHA-256 của baseline `VN001`.
- **Bộ kiểm thử tự động (832 test methods):**
  - Toàn bộ suite định nghĩa **832** test method trong `tests/` (xem bảng phân bổ chi tiết và giới hạn từng môi trường tại [`docs/TEST_SUITE.md`](docs/TEST_SUITE.md)).
  - Do `data/` được `.gitignore` loại khỏi Git, **CI GitHub Actions** không có dữ liệu thật nên bỏ qua 5 lớp phụ thuộc dữ liệu (`TestDocumentedReproduction` 4, `TestRealDataset` 12, `TestSemanticMutations` 8, `TestRegressionRealDataset` 2, `TestClassificationRealDataset` 2 — tổng **28** method không vào `Ran`, dự kiến `Ran = 804`). Kết luận trên số liệu thật phải được kiểm chứng bằng lần chạy local có `data/` hoặc `scripts/validate_extended_reanalysis.py --real-data`.

---

## 3. Cấu trúc Repository

```text
air-pollution-analysis/
├── .github/workflows/ci.yml              # Pipeline CI GitHub Actions (syntax, unittests, smoke test)
├── .agents/                              # Quy tắc, kỹ năng và quy trình chuẩn hóa cho agent
├── AGENTS.md                             # Chỉ dẫn kiến trúc & quy tắc kỹ thuật cốt lõi
├── CONTRIBUTING.md                       # Hướng dẫn đóng góp, quy trình Git và chuẩn mã nguồn
├── LICENSE                               # Giấy phép mã nguồn mở MIT
├── README.md                             # Tài liệu tổng quan và hướng dẫn tái lập
├── requirements.txt                      # Thư viện phụ thuộc cố định (Python 3.10+)
├── data/
│   ├── raw/                              # Dữ liệu gốc tải từ API (không Git-track) + metadata.json (SHA-256)
│   ├── interim/                          # Dữ liệu trung gian canonical Parquet (sau nạp & làm sạch tất định)
│   └── processed/                        # Tập dữ liệu đóng băng Parquet (gitignored)
│       ├── air_pollution_final.parquet               # 9.044 dòng × 18 cột (baseline VN001, Issue #7)
│       └── air_pollution_extended_2022_2026.parquet  # 37.722 dòng × 23 cột (VN003 + VN001, Issue #44)
├── docs/
│   ├── roadmap.md                        # Lộ trình tổng thể Week 01–15 (nguồn chuẩn)
│   ├── TEST_SUITE.md                     # Nguồn chuẩn số liệu kiểm thử, skip và giới hạn CI
│   ├── TASK_LIST_M3_M6.md                # Danh mục tác vụ M3–M6
│   ├── research_questions.md             # Câu hỏi nghiên cứu SQ1–SQ4 [Issue #2]
│   ├── data_dictionary.md                # Từ điển dữ liệu Canonical Schema [Issue #2]
│   ├── source_profiling_decision.md      # Thẩm định & quyết định cổng nguồn dữ liệu [Issue #19]
│   ├── data_quality_audit.md             # Báo cáo kiểm toán chất lượng 6 chiều [Issue #5]
│   ├── cleaning_log.md                   # Nhật ký làm sạch tất định (sinh tự động) [Issue #6]
│   ├── issue44_*.md                      # Hợp đồng dữ liệu, provenance & quyết định mở rộng [Issue #44]
│   ├── issue50_reproducibility.md        # Hướng dẫn & giới hạn tái lập Issue #50
│   ├── regression_findings.md            # Tổng kết phát hiện hồi quy OLS & LINE [Issue #12]
│   ├── classification_findings.md        # Tổng kết phát hiện phân loại cảnh báo [Issue #13]
│   └── leakage_audit.md                  # Biên bản kiểm toán rò rỉ 4 lớp [Issue #13]
├── notebooks/
│   ├── 00_environment_test.ipynb         # Kiểm thử môi trường và thư viện [Issue #1]
│   ├── 01_data_collection.ipynb          # Thu thập & kiểm định dữ liệu [Issue #3, #4]
│   ├── 02_quality_audit.ipynb            # Kiểm toán chất lượng 6 chiều [Issue #5]
│   ├── 03_data_cleaning.ipynb            # Làm sạch tất định & sinh Cleaning Log [Issue #6]
│   ├── 03_transformation_pipeline.ipynb  # Merge → freeze → split → fit chống rò rỉ [Issue #7]
│   ├── 03_processed_data_preview.ipynb   # Kiểm tra nhanh artifact đóng băng (không thuộc chuỗi chính)
│   ├── 04_descriptive_stats.ipynb        # EDA 4 họ chỉ số + chu kỳ thời gian [Issue #8]
│   ├── 05_statistical_inference.ipynb    # Suy luận thống kê W9 có xét phụ thuộc thời gian [Issue #11]
│   ├── 06_regression_modeling.ipynb      # Hồi quy OLS, LINE, HAC-24 & Ridge/Lasso [Issue #12]
│   └── 07_classification_alerts.ipynb    # Phân loại cảnh báo 24h, hiệu chuẩn & ablation [Issue #13]
├── scripts/
│   ├── fetch_dataset.py                  # Tải & đối chiếu tập dữ liệu baseline (không cần API key)
│   ├── build_extended_historical_dataset.py # Dựng tập dữ liệu mở rộng 2022–2026 [Issue #44]
│   ├── profile_airnow_mirror.py          # Kiểm toán độc lập mirror AirNow GitHub (NO-GO) [Issue #44]
│   ├── run_extended_reanalysis.py        # Chạy tái phân tích tách trạm M2/M3/W9 [Issue #50]
│   ├── validate_extended_reanalysis.py   # Thẩm định cấu trúc & ngữ nghĩa độc lập [Issue #50]
│   ├── generate_04_notebook.py .. generate_07_notebook.py  # Script sinh notebook chuẩn 04–07
│   ├── validate_issue8.py                # Thẩm định deliverables Issue #8
│   ├── validate_inference_montecarlo.py  # Mô phỏng Monte Carlo kiểm soát sai lầm loại I [Issue #11]
│   ├── verify_claims.py                  # Tái lập claim định lượng từ dữ liệu thật
│   └── build_progress_report.py          # Sinh báo cáo tiến độ DOCX M1–M2
├── src/
│   ├── data_collection.py                # Adapter OpenAQ, Open-Meteo, AirNow & validation
│   ├── data_loader.py                    # Nạp Parquet chuẩn hóa cohort & kiểm tra station_id [Issue #15/#56]
│   ├── data_quality.py                   # Kiểm toán chất lượng 6 chiều & khuyết thiếu Rubin
│   ├── cleaning.py                       # Làm sạch tất định, kẹt cảm biến, reindex đa trạm
│   ├── cleaning_pipeline.py              # Merge, freeze, split thời gian, Pipeline chống rò rỉ
│   ├── flag_evidence.py                  # Tái lập bằng chứng F-test cho is_high_humidity_fog
│   ├── visualizer.py                     # Xuất bản 7 biểu đồ ấn phẩm FIG-01..FIG-07 [Issue #9]
│   ├── inference.py                      # Suy luận thống kê W9 [Issue #11]
│   ├── issue44_preparation.py            # Chuẩn bị mở rộng & masking-validation [Issue #44]
│   ├── extended_audit.py                 # Kiểm toán & phân tích mở rộng tách trạm [Issue #50]
│   ├── reanalysis_validation.py          # Bộ validator cho tái phân tích Issue #50
│   ├── regression.py                     # Hồi quy OLS, chẩn đoán LINE, HAC-24 & Ridge/Lasso [Issue #12]
│   └── classification.py                 # Phân loại cảnh báo ô nhiễm & kiểm toán rò rỉ [Issue #13]
├── tests/                                # 832 unit tests tất định (xem docs/TEST_SUITE.md)
├── figures/
│   ├── FIG-01.png .. FIG-07.png          # 7 biểu đồ ấn phẩm chính (300 DPI) [Issue #9]
│   ├── FIG-08.png .. FIG-12.png          # Hình bổ sung suy luận W9 [Issue #11]
│   ├── FIG-01-extended-historical.png    # Biểu đồ đa năm 2022–2026 tách trạm [Issue #44]
│   ├── extended/                         # FIG-02-extended, FIG-03-extended, FIG-03b-winter-coverage [Issue #50]
│   ├── regression_line_diagnostics*.png  # Chẩn đoán LINE theo 3 phạm vi [Issue #12]
│   └── precision_recall_curve*.png · feature_importance*.png · calibration_reliability*.png  # [Issue #13]
└── reports/                              # Báo cáo Markdown, CSV & JSON sinh tự động từ mã nguồn
```

---

## 4. Hướng dẫn Thiết lập & Tái lập

### Yêu cầu Tiên quyết
- **Python:** 3.10 trở lên (khuyến nghị 3.10 – 3.14).
- **Git:** Đã cài đặt trên hệ thống.
- **Kết nối Internet:** Chỉ cần thiết khi tải tập dữ liệu ở bước 5; toàn bộ kiểm thử và phân tích sau đó chạy offline.

### Các bước Cài đặt & Chạy kiểm thử

1. **Sao chép kho lưu trữ:**
   ```bash
   git clone https://github.com/doctor-cato/air-pollution-analysis.git
   cd air-pollution-analysis
   ```

2. **Khởi tạo và kích hoạt môi trường ảo (`venv`):**
   - *Windows (PowerShell):*
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - *macOS / Linux:*
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Cài đặt thư viện phụ thuộc:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Kiểm tra môi trường (Smoke Test):**
   ```bash
   jupyter nbconvert --to notebook --execute notebooks/00_environment_test.ipynb
   ```

5. **Thu thập & kiểm chứng tập dữ liệu baseline (cần mạng, không cần API key):**
   ```bash
   python scripts/fetch_dataset.py
   ```

   | Nguồn | Vai trò | Giấy phép | Cần API key? |
   |---|---|---|---|
   | OpenAQ S3 (`location_id=4946811`, `VN001`) | Chất lượng không khí baseline (07/2025–07/2026) | ODC-BY v1.0 | Không |
   | OpenAQ S3 (`location_id=7441`, `VN003`) | Dữ liệu lịch sử mở rộng (01/2022–04/2025, Issue #44) | US Public Domain | Không |
   | Open-Meteo ERA5 Reanalysis | Khí tượng bề mặt (2022–2026) | CC BY 4.0 | Không |
   | AirNow DOS CSV (`VN002_HANOI_US_EMBASSY`) | Nguồn dự phòng qua `AirNowDOSAdapter` | US Public Domain | Có (cung cấp CSV) |

   > [!NOTE]
   > Dữ liệu thô và Parquet trong `data/` không nằm trong Git theo chính sách ba tầng ([`docs/roadmap.md`](docs/roadmap.md)). Vì Parquet không tái lập theo byte giữa các phiên bản thư viện, `fetch_dataset.py` đối chiếu theo **nội dung** (số bản ghi, dải thời gian, độ phủ) với `data/raw/metadata.json`.

6. **Chạy bộ Unit Tests (832 test methods) & kiểm tra cú pháp:**
   ```bash
   python -m unittest discover tests -v
   python -m compileall -q src tests scripts
   git diff --check
   ```

### Chuỗi Tái lập Toàn trình (Local có `data/`)

Thực thi tuần tự các notebook theo đúng thứ tự phụ thuộc:

```text
python scripts/fetch_dataset.py
  → notebooks/01_data_collection.ipynb
  → notebooks/02_quality_audit.ipynb            # PHẢI chạy trước 03_data_cleaning
  → notebooks/03_data_cleaning.ipynb            # ghi đè data/interim/ & sinh docs/cleaning_log.md
  → notebooks/03_transformation_pipeline.ipynb  # sinh data/processed/air_pollution_final.parquet
  → notebooks/04_descriptive_stats.ipynb        # sinh reports/statistical_profile.csv
  → notebooks/05_statistical_inference.ipynb    # sinh reports/inference_results.md & FIG-08..12
  → notebooks/06_regression_modeling.ipynb      # sinh reports/regression_results.md & diagnostics
  → notebooks/07_classification_alerts.ipynb    # sinh reports/classification_*.md & PR/calibration plots
```

**Tái lập nhánh dữ liệu lịch sử mở rộng (Issues #44 & #50):**
```bash
python scripts/build_extended_historical_dataset.py
python scripts/run_extended_reanalysis.py
python scripts/validate_extended_reanalysis.py --real-data
```

> [!IMPORTANT]
> - Để chạy lại `03_data_cleaning.ipynb` đúng chuẩn, cần khôi phục `data/interim/` từ `data/raw/` trước (nếu không `docs/cleaning_log.md` sẽ ghi sai trạng thái trước làm sạch).
> - Không sửa tay file JSON của `notebooks/04`–`07`; hãy cập nhật script nguồn `scripts/generate_04_notebook.py`..`generate_07_notebook.py` rồi sinh lại để giữ ổn định serialization.
> - Để sinh báo cáo tiến độ M1–M2: `python scripts/build_progress_report.py` (yêu cầu đã có `data/interim/*.parquet`).

---

## 5. Nguyên tắc Quản trị Dữ liệu & Kỹ thuật

- **Bảo toàn dữ liệu thô (`data/raw/`):** Dữ liệu tải từ API được lưu nguyên trạng, ghi nhận xuất xứ và mã băm SHA-256 trong `data/raw/metadata.json`, không sửa thủ công và không commit vào Git.
- **Ngăn chặn rò rỉ dữ liệu (*Leakage Prevention*):** Mọi phép chia Train/Test đều theo trình tự thời gian ($T_{\text{train}} < T_{\text{test}}$); mọi bộ biến đổi (`SimpleImputer`, `RobustScaler`) chỉ `fit` trên tập Train.
- **Tính tiền định (*Determinism*):** Cố định `random_state=42` và hỗ trợ thực thi **Restart Kernel & Run All** trên toàn bộ notebook.
- **Kiến trúc vừa đủ (*No Over-Engineering*):** Sử dụng Parquet (nén Snappy) và ngăn xếp Python khoa học chuẩn (`pandas`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`, `matplotlib`, `seaborn`), không đưa vào Spark hay Deep Learning không cần thiết.

---

## 6. Cam kết Liêm chính Học thuật (Academic Integrity)

Dự án tuân thủ chuẩn đầu ra CLO4 và quy chế học thuật của Trường Đại học CMC:
- **Dữ liệu thật – Nguồn xác thực:** Sử dụng dữ liệu công khai từ OpenAQ và Open-Meteo ERA5, đối chiếu QCVN 05:2023/BTNMT và WHO 2021.
- **Không ngụy tạo số liệu hay độ đo:** Không bịa đặt quan trắc để điền khuyết, không xóa dị biệt vật lý thiếu căn cứ, báo cáo trung thực mọi kết quả kiểm định và mô hình trên tập kiểm tra độc lập.
- **Minh bạch giả định:** Công bố đầy đủ các trường hợp vi phạm giả định (ví dụ: vi phạm 4 giả định LINE trong OLS) cùng phương pháp hiệu chỉnh tương ứng (HAC Newey–West, block bootstrap).

---

## 7. Tuyên bố Sử dụng Trí tuệ Nhân tạo (AI Usage Declaration)

Tuân thủ hướng dẫn về tính minh bạch học thuật trong môn học INFO3020, dự án công khai mức độ hỗ trợ của các công cụ AI trong quá trình thực hiện:

- **Phạm vi hỗ trợ của AI:** Các công cụ AI (Google Gemini, GitHub Copilot) được sử dụng làm công cụ trợ giúp kỹ thuật cho:
  - Sinh mã khung, script tạo/đồng bộ các notebook phân tích (`notebooks/04_descriptive_stats.ipynb`–`07_classification_alerts.ipynb`) và các module xử lý, trực quan hóa, kiểm thử đơn vị trong `src/` và `tests/`.
  - Hỗ trợ gỡ lỗi (*debugging*), rà soát cú pháp, kiểm tra tương thích gói thư viện đa nền tảng và bổ sung ca kiểm thử hồi quy cho các biên rò rỉ dữ liệu.
  - Hỗ trợ biên tập, chuẩn hóa cấu trúc Markdown và rà soát tính nhất quán của tài liệu kỹ thuật trong `docs/` và `README.md`.
- **Vai trò và trách nhiệm của nhóm sinh viên:**
  - Nhóm sinh viên trực tiếp xác định câu hỏi nghiên cứu, thiết kế phương pháp luận, lựa chọn mô hình, chốt giả thuyết thống kê, quy ước kiểm soát rò rỉ dữ liệu và diễn giải khoa học.
  - Toàn bộ mã nguồn, notebook và tài liệu có sự hỗ trợ của AI đều được nhóm sinh viên rà soát, thực thi trực tiếp trên dữ liệu thật, kiểm chứng bằng bộ unit test/script xác minh độc lập và tự chịu hoàn toàn trách nhiệm học thuật đối với sản phẩm cuối cùng.

---

## 8. Hướng dẫn Đóng góp

Xem quy trình nhánh, quy ước commit và chuẩn mã nguồn tại **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## 9. Giấy phép & Bản quyền

Mã nguồn dự án được phân phối theo **[MIT License](LICENSE)**.
