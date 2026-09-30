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

Dự án tập trung nghiên cứu biến thiên nồng độ bụi mịn $\text{PM}_{2.5}$ và mối liên hệ với các yếu tố khí tượng bề mặt tại khu vực Hà Nội. Đề tài tuân thủ chặt chẽ vòng đời khoa học dữ liệu **CRISP-DM**, giải quyết các câu hỏi nghiên cứu về:

1. **Quy luật chu kỳ thời gian:** Phân tích biến động $\text{PM}_{2.5}$ theo chu kỳ ngày đêm (*diurnal*), ngày trong tuần (*weekday vs. weekend*), và chu kỳ mùa vụ (*seasonal*).
2. **Suy luận thống kê có đối chứng:** Kiểm định giả thuyết so sánh mức độ ô nhiễm giữa các khoảng thời gian kèm kích thước hiệu ứng và khoảng tin cậy Bootstrap theo phương pháp kiểm định phù hợp với dữ liệu.
3. **Mô hình hóa hồi quy giải thích:** Định lượng mức độ liên hệ của nhiệt độ, độ ẩm, tốc độ gió, áp suất lên nồng độ bụi thông qua hồi quy OLS (kèm chẩn đoán 4 giả định LINE).
4. **Mô hình phân loại cảnh báo sớm:** Xây dựng bài toán phân loại cảnh báo đợt ô nhiễm dựa trên nồng độ $\text{PM}_{2.5}$ trung bình 24 giờ tổng hợp (tham chiếu ngưỡng quy chuẩn QCVN 05:2023/BTNMT là $45\,\mu\text{g/Nm}^3$ áp dụng từ 01/01/2026, kèm bước chuẩn hóa tương thích giữa đơn vị quan trắc $\mu\text{g/m}^3$ thực tế và $\mu\text{g/Nm}^3$ quy chuẩn), tối ưu hóa Recall và PR-AUC theo mục tiêu vận hành bảo vệ sức khỏe cộng đồng.

---

## 2. Hiện trạng Triển khai vs. Kế hoạch Lộ trình

> [!IMPORTANT]
> **Phân định rõ ràng giữa mã nguồn hiện có và kế hoạch tương lai:**  
> Dự án đang ở giai đoạn **Milestone 2 (Kiểm toán & Làm sạch dữ liệu — Tuần 03–05)**. Đã hoàn tất phần thu thập, chuẩn hóa, kiểm toán chất lượng 6 chiều và làm sạch tất định. Toàn bộ các phân tích thống kê, mô hình học máy và các giai đoạn tiền xử lý/làm mô hình phía sau vẫn là kế hoạch đặc tả trong [`docs/roadmap.md`](docs/roadmap.md) và **chưa được hiện thực hóa**.

### 2.1. Hiện trạng Triển khai (Milestone 1–2)

> [!IMPORTANT]
> **Trạng thái hiện tại sau review:** **Issue #1–#7 đều DONE và đã merge vào `main`.**
> - **Issue #1, #2, #19, #3:** Đã hoàn tất và nghiệm thu (**DONE**).
> - **Issue #4:** PR #26 đã merge vào `main` (**DONE**).
> - **Issue #5:** Bộ kiểm toán chất lượng 6 chiều đã hoàn thành và merge qua PR #27 (`src/data_quality.py`, `docs/data_quality_audit.md`, `notebooks/02_quality_audit.ipynb`) (**DONE**).
> - **Issue #6:** Làm sạch tất định đã triển khai (`src/cleaning.py`, `docs/cleaning_log.md`, `notebooks/03_data_cleaning.ipynb`) (**DONE**).
> - **Issue #7:** Tiền xử lý chống rò rỉ đã triển khai và kiểm chứng bằng `validate_no_leakage()` — so **mọi** tham số đã học với giá trị refit trên Train, kiểm tra `train.max() < test.min()`, và từ chối target trong feature (`src/cleaning_pipeline.py`, `notebooks/03_transformation_pipeline.ipynb`, `tests/test_cleaning_pipeline.py`, `tests/test_cleaning_pipeline_guards.py`).
> - **Lưu ý về lịch sử merge:** #6 và #7 được triển khai cùng nhau trên nhánh `feat/issue-6-deterministic-cleaning` và merge bằng **một** PR #32 (2026-09-30). Việc tách thành hai issue là đánh số bàn giao, không phải hai thay đổi độc lập: `clean_air_quality()` phụ thuộc bảng khí tượng **đã** làm sạch, nên #6 không thể tách khỏi #7 mà không viết lại kiến trúc.
> - **Mô hình học máy và phân tích thống kê nâng cao (Issues #11–#13) vẫn chưa bắt đầu** — notebook `04`–`06` chưa tồn tại.
> - **Tổng số unit test: 259** (`test_data_collection` 57, `test_data_quality` 14, `test_cleaning` 107, `test_cleaning_pipeline` 38, `test_cleaning_pipeline_guards` 34, `test_fetch_dataset` 9). Chạy: `python -m unittest discover tests`.
> - **Guard chống rò rỉ đã được kiểm chứng bằng 34 test hồi quy** trong `tests/test_cleaning_pipeline_guards.py`, mỗi test được viết để **FAIL trên bản gốc** (xoá guard, cho target lọt vào feature, cho `transform_with_pipeline()` refit trên chính Test, thêm nhánh `ColumnTransformer` thứ hai, đảo thứ tự đối số).
>
>   > [!NOTE]
>   > **Về con số "mutation score 21/21 = 100%":** đây là kết quả đếm **thủ công** trong một vòng review đối kháng của Issue #7, **không** phải báo cáo sinh tự động bởi công cụ mutation testing nào. Repo **không** có `mutmut`/`cosic-ray` trong `requirements.txt`, không có file cấu hình mutation, không có bước CI nào chạy nó, và không lưu artifact báo cáo. Vì vậy con số này **không tái lập được** từ repository và không nên được trích dẫn như bằng chứng kiểm định máy móc. Bằng chứng tái lập được là 34 test hồi quy nêu trên — chạy `python -m unittest tests.test_cleaning_pipeline_guards -v` là thấy ngay.

**Tuần 01 — Thiết lập dự án & Canonical Schema**
- [x] Thiết lập khung cây thư mục chuẩn mực theo vòng đời CRISP-DM [Issue #1].
- [x] Cấu hình file `.gitignore` nghiêm ngặt, cách ly dữ liệu thô, cache nhị phân, môi trường ảo và thông tin xác thực [Issue #1].
- [x] Tạo file `requirements.txt` cố định phiên bản tương thích với Python 3.10+ (hỗ trợ pre-built wheels cho Windows/Linux/macOS) [Issue #1].
- [x] Xây dựng notebook `notebooks/00_environment_test.ipynb` kiểm thử tự động toàn bộ thư viện cốt lõi, kiểm tra I/O Parquet, Matplotlib và Scikit-Learn Pipeline [Issue #1].
- [x] Biên soạn tài liệu `README.md` tiếng Việt với cam kết liêm chính học thuật và hướng dẫn tái lập [Issue #1].
- [x] Xác lập Câu hỏi nghiên cứu mục tiêu và 4 câu hỏi thành phần SQ1–SQ4 đảm bảo tính trung lập khoa học ([`docs/research_questions.md`](docs/research_questions.md)) [Issue #2].
- [x] Xây dựng Từ điển dữ liệu chuẩn hóa trung lập nguồn Canonical Data Schema với 11 trường dữ liệu và 8 thuộc tính chuẩn hóa ([`docs/data_dictionary.md`](docs/data_dictionary.md)) [Issue #2].

**Tuần 02 — Thẩm định nguồn & thu thập dữ liệu**
- [x] Khảo sát hồ sơ đa nguồn, kiểm chứng phạm vi địa lý Hà Nội và độ bao phủ thời gian thực tế; ban hành quyết định nguồn theo ma trận đa tiêu chí ([`docs/source_profiling_decision.md`](docs/source_profiling_decision.md)) [Issue #19].
- [x] Pipeline thu thập & chuẩn hóa dữ liệu chất lượng không khí từ OpenAQ (AWS S3 public bucket, `locationid=4946811` - 556 Nguyễn Văn Cừ, Long Biên, Hà Nội), giữ nguyên đơn vị quan trắc `(station_id, timestamp)` [Issue #3].
- [x] Hiện thực hóa `AirNowDOSAdapter` (`VN002_HANOI_US_EMBASSY`, Met One BAM-1020) trong `src/data_collection.py` sẵn sàng cho dữ liệu lịch sử khi có tệp thô [Issue #3].
- [x] Pipeline thu thập & chuẩn hóa 6 biến khí tượng từ Open-Meteo ERA5 Reanalysis, đồng bộ động dải thời gian với chuỗi quan trắc chất lượng không khí [Issue #4].
- [x] Lưu payload thô dưới `data/raw/` khi pipeline chạy, kèm `metadata.json` ghi nhận xuất xứ, tham số truy vấn, mã băm SHA-256 và giấy phép (theo [chính sách dữ liệu thô ba tầng](docs/roadmap.md#32-cổng-quyết-định-nguồn-dữ-liệu-issue-19-as-source-selection-gate)) [Issue #3, #4].
- [x] Bộ **57** unit tests tất định cho pipeline thu thập (`tests/test_data_collection.py`) và pipeline kiểm định tự động bằng GitHub Actions (`.github/workflows/ci.yml`).

**Tuần 03–04 — Kiểm toán & Làm sạch dữ liệu**
- [x] Kiểm toán chất lượng 6 chiều và phân tích cơ chế khuyết thiếu Rubin với **tuyên bố bất định** minh bạch ([Issue #5], `src/data_quality.py`, [`docs/data_quality_audit.md`](docs/data_quality_audit.md), `notebooks/02_quality_audit.ipynb`).
- [x] Làm sạch **tất định**: chuẩn hóa múi giờ UTC+7, khử trùng lặp, bóc trần missing ngụy trang, lọc giá trị âm phi lý, thực thi ràng buộc khí động học $\text{PM}_{2.5} \le \text{PM}_{10}$, reindex lưới 1 giờ liên tục **độc lập theo từng trạm** ([Issue #6], `src/cleaning.py`).
- [x] Nhận diện lỗi kẹt cảm biến và gắn cờ chẩn đoán `is_high_humidity_fog`, `pm25_was_missing` — **không** xóa bản ghi, **không** điền khuyết ([`docs/cleaning_log.md`](docs/cleaning_log.md)).
- [x] Biên soạn **Cleaning Log** tự động sinh từ mã nguồn, ghi nhận 100% phép biến đổi kèm số dòng bị tác động ([`docs/cleaning_log.md`](docs/cleaning_log.md)).
- [x] Bộ **107** unit tests tất định cho lớp làm sạch (`tests/test_cleaning.py`), bao gồm kiểm chứng **không điền khuyết** và **tính tất định** (idempotent).

> [!NOTE]
> **Về dữ liệu thô:** tệp thô tải từ API **không được Git-track** — đây là chính sách kho dữ liệu của repository, không phải thiếu sót. Tính toàn vẹn được kiểm chứng bằng mã băm SHA-256 ghi trong `data/raw/metadata.json`. Xem [Mục 3.2 của roadmap](docs/roadmap.md#32-cổng-quyết-định-nguồn-dữ-liệu-issue-19-as-source-selection-gate).

### 2.2. Kế hoạch thực hiện tiếp theo (Theo `docs/roadmap.md`)
- **Tuần 03–05 (Milestone 2):** ~~Kiểm toán 6 chiều chất lượng dữ liệu~~ ([Issue #5] — **đã xong**, PR #27), ~~làm sạch tất định & lập cleaning log~~ ([Issue #6] — **đã xong**) và ~~tích hợp dữ liệu, đóng băng, phân chia chuỗi thời gian tuyến tính, đóng gói Pipeline chống rò rỉ~~ ([Issue #7] — **đã xong**). Milestone 2 đã đủ.
- **Tuần 06–08 (Milestone 3):** Phân tích khám phá dữ liệu (EDA), tính toán 4 họ chỉ số thống kê, thiết kế 7 biểu đồ ấn phẩm giải thích theo nguyên tắc Tufte/Cleveland, hoàn thành Báo cáo Giữa kỳ ([Issue #8, #9, #10]).
- **Tuần 09–11 (Milestone 4):** Thực hiện kiểm định giả thuyết phi tham số, xây dựng mô hình hồi quy OLS (chẩn đoán LINE), phát triển mô hình phân loại cảnh báo ô nhiễm với điều chỉnh ngưỡng quyết định (*Threshold tuning*) ([Issue #11, #12, #13]).
- **Tuần 12–15 (Milestones 5 & 6):** Đánh giá định kiến dữ liệu (*Bias Audit*), đo đạc tài nguyên vs Spark, lập Datasheet for Dataset, Model Card 1 trang, hoàn thiện mã nguồn và bảo vệ đồ án cuối kỳ ([Issue #14, #15, #16, #17]).

---

## 3. Cấu trúc Repository

```text
air-pollution-analysis/
├── .github/
│   └── workflows/
│       └── ci.yml                      # Pipeline CI GitHub Actions (syntax, unittests, smoke test)
├── .agents/                            # Quy tắc, kỹ năng và quy trình chuẩn hoá cho tác nhân/người đóng góp
├── AGENTS.md                           # Chỉ dẫn kiến trúc & quy tắc kỹ thuật cho tác nhân
├── .gitignore                          # Quy tắc loại trừ dữ liệu thô, cache, môi trường ảo
├── CONTRIBUTING.md                     # Hướng dẫn đóng góp, quy trình Git và chuẩn mã nguồn
├── LICENSE                             # Giấy phép mã nguồn mở MIT
├── README.md                           # Tài liệu tổng quan, hướng dẫn thiết lập và quản trị
├── requirements.txt                    # Danh sách thư viện phụ thuộc tương thích Python 3.10+
├── data/
│   ├── raw/                            # Dữ liệu gốc lưu khi chạy pipeline (không Git-track)
│   │   ├── metadata.json               # Xuất xứ, tham số truy vấn, mã băm SHA-256, bản quyền
│   │   └── .gitkeep
│   ├── interim/                        # Dữ liệu trung gian canonical Parquet (sau nạp, chuẩn hóa và làm sạch tất định)
│   │   └── .gitkeep
│   └── processed/                      # Dữ liệu sạch hoàn chỉnh đóng băng lưu Parquet
│       ├── air_pollution_final.parquet  # 9.044 dòng × 18 cột — artifact đóng băng của Issue #7 (gitignored)
│       └── .gitkeep
├── docs/
│   ├── roadmap.md                      # Lộ trình và đặc tả yêu cầu chi tiết 15 tuần (Authoritative Plan)
│   ├── ROADMAP_INFO3020_Air_Pollution.md # Bản sao tham chiếu đề cương gốc (Đã thay thế một phần)
│   ├── research_questions.md           # Câu hỏi nghiên cứu & khung phân tích SQ1–SQ4 [Issue #2]
│   ├── data_dictionary.md              # Từ điển dữ liệu chuẩn hóa Canonical Schema [Issue #2]
│   ├── source_profiling.md             # Mục lục tài liệu thẩm định hồ sơ đa nguồn [Issue #19]
│   ├── source_profiling_decision.md    # Báo cáo thẩm định & quyết định cổng nguồn dữ liệu [Issue #19]
│   ├── data_quality_audit.md           # Báo cáo kiểm toán chất lượng 6 chiều [Issue #5]
│   ├── cleaning_log.md                 # Nhật ký làm sạch tất định (sinh tự động) [Issue #6]
│   └── air_quality_project_overview.md # Tài liệu tổng quan định hướng đề tài
├── notebooks/
│   ├── 00_environment_test.ipynb       # Notebook kiểm thử môi trường và nạp thư viện [Issue #1]
│   ├── 01_data_collection.ipynb        # Thực thi pipeline thu thập & kiểm định dữ liệu [Issue #3, #4]
│   ├── 02_quality_audit.ipynb          # Trình bày kết quả kiểm toán 6 chiều [Issue #5]
│   ├── 03_data_cleaning.ipynb         # Thực thi làm sạch tất định & sinh Cleaning Log [Issue #6]
│   └── 03_transformation_pipeline.ipynb # Merge → freeze → split → fit chống rò rỉ [Issue #7]
├── scripts/
│   └── fetch_dataset.py                # Tải & kiểm chứng tập dữ liệu từ nguồn công khai (không cần API key)
├── src/
│   ├── __init__.py
│   ├── data_collection.py              # Adapter OpenAQ, Open-Meteo, AirNow và validation [Issue #3, #4]
│   ├── data_quality.py                 # Hàm kiểm toán chất lượng 6 chiều & phân tích khuyết thiếu [Issue #5]
│   ├── cleaning.py                     # Làm sạch tất định, kẹt cảm biến, reindex & sinh Cleaning Log [Issue #6]
│   └── cleaning_pipeline.py            # Merge, freeze, split thời gian, sklearn Pipeline chống rò rỉ, xuất Parquet [Issue #7]
├── tests/
│   ├── test_data_collection.py         # 57 unit tests kiểm thử pipeline thu thập và validation [Issue #3, #4]
│   ├── test_data_quality.py            # 14 unit tests cho bộ kiểm toán 6 chiều [Issue #5]
│   ├── test_cleaning.py                # 107 unit tests cho lớp làm sạch tất định [Issue #6]
│   ├── test_cleaning_pipeline.py       # 38 unit tests cho merge/freeze/split/Pipeline của #7
│   ├── test_cleaning_pipeline_guards.py# 34 unit test hồi quy chặn rò rỉ — mỗi test FAIL trên bản gốc
│   └── test_fetch_dataset.py           # 9 unit tests cho cơ chế thu thập & kiểm chứng tập dữ liệu
├── figures/                            # Thư mục lưu biểu đồ xuất bản chất lượng cao (300 DPI)
│   └── .gitkeep
└── reports/                            # Báo cáo giữa kỳ và báo cáo tổng kết đồ án
    └── .gitkeep
```

---

## 4. Hướng dẫn Thiết lập & Tái lập Môi trường

### Yêu cầu Tiên quyết
- **Python:** Phiên bản 3.10 trở lên (khuyến nghị Python 3.10 – 3.14).
- **Git:** Cài đặt sẵn trên hệ thống.
- **Kết nối Internet:** Bắt buộc **chỉ ở bước 5** (tải tập dữ liệu). Các bước còn lại chạy offline.

### Các bước Cài đặt

1. **Sao chép kho lưu trữ về máy tính:**
   ```bash
   git clone https://github.com/doctor-cato/air-pollution-analysis.git
   cd air-pollution-analysis
   ```

2. **Khởi tạo và kích hoạt môi trường ảo (`venv`):**
   - *Trên Windows (PowerShell):*
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - *Trên macOS / Linux:*
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Cài đặt các gói phụ thuộc cố định:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Kiểm chứng môi trường bằng Notebook tự động (Smoke Test):**
   ```bash
   jupyter nbconvert --to notebook --execute notebooks/00_environment_test.ipynb
   ```
   Nếu lệnh chạy với mã thoát `0` và hiển thị thông báo `ALL ENVIRONMENT TESTS PASSED`, môi trường đã sẵn sàng.

5. **Thu thập & kiểm chứng tập dữ liệu (bước duy nhất cần mạng):**
   ```bash
   python scripts/fetch_dataset.py
   ```
   Lệnh này tải tập dữ liệu từ **hai nguồn công khai, không cần API key**, ghi payload thô vào `data/raw/`, sinh Parquet canonical vào `data/interim/`, rồi **tự đối chiếu nội dung với `data/raw/metadata.json`** (số bản ghi thô, số bản ghi canonical, dải thời gian thực tế, số bản ghi giao thoa và tỷ lệ độ phủ) để báo cáo tập dữ liệu có khớp bản đã kiểm toán hay không.

   | Nguồn | Vai trò | Giấy phép | Cần API key? |
   |---|---|---|---|
   | OpenAQ S3 public archive (`location_id=4946811`) | Chất lượng không khí | ODC-BY v1.0 | Không |
   | Open-Meteo Historical Weather API (ECMWF ERA5) | Khí tượng bề mặt | CC BY 4.0 | Không |

   > [!IMPORTANT]
   > **Vì sao tập dữ liệu không nằm trong Git?** Theo chính sách dữ liệu ba tầng ([`docs/roadmap.md` §3.2](docs/roadmap.md)), tệp thô tải từ API **không bắt buộc phải được Git-track** (Tầng C) — chúng được tái tạo từ nguồn công khai. Việc kiểm chứng toàn vẹn dựa trên mã băm SHA-256 ghi trong `data/raw/metadata.json` (Tầng B).
   >
   > **Giới hạn cần biết:** bucket OpenAQ S3 là **kho sống** — nhà cung cấp tiếp tục nạp dữ liệu mới, nên một lần tải ở thời điểm sau có thể nhiều dòng hơn bản đã kiểm toán. Ngoài ra, định dạng Parquet **không tái lập được theo byte** giữa các máy (khối nén và metadata nội bộ phụ thuộc phiên bản thư viện), nên SHA-256 kiểm chứng được *tính toàn vẹn của tệp đã lưu* chứ không dựng lại được *tập dữ liệu*. Vì vậy `scripts/fetch_dataset.py` kiểm chứng bằng **so khớp nội dung** (số bản ghi, dải thời gian, độ phủ giao thoa) thay vì so khớp byte.

6. **Chạy bộ Unit Tests kiểm định toàn trình (259 tests tất định):**
   ```bash
   python -m unittest discover tests -v
   ```
   Bộ gồm **57** unit tests trong `tests/test_data_collection.py` (kiểm chứng adapter OpenAQ, Open-Meteo, AirNow, logic lọc địa lý Hà Nội, kiểm định chất lượng khí tượng `validate_weather_canonical()`, cơ chế đồng bộ thời gian động), **14** unit tests trong `tests/test_data_quality.py` (bộ kiểm toán chất lượng 6 chiều), **107** unit tests trong `tests/test_cleaning.py` (làm sạch tất định: chuẩn hóa múi giờ, khử trùng lặp, ràng buộc khí động học, reindex đa trạm, kẹt cảm biến, cờ chẩn đoán, tính tất định, bảo toàn giá trị cực trị, và 20 test hồi quy cho các lỗi tìm ra khi review đối kháng) **38** unit tests trong `tests/test_cleaning_pipeline.py` (merge có guard, freeze, split thời gian, pipeline, xuất Parquet nguyên tử), **34** unit test hồi quy trong `tests/test_cleaning_pipeline_guards.py` — mỗi test trong đó **FAIL trên bản gốc** và PASS sau khi sửa, nên chúng chứng minh lỗi thật chứ không phải trang trí — và **9** unit tests trong `tests/test_fetch_dataset.py` (cơ chế thu thập & kiểm chứng tập dữ liệu) — **tổng cộng 259 test**. Tất cả độc lập với mạng Internet và thực thi tất định trong CI.

7. **Kiểm tra cú pháp và quy chuẩn diff:**
   ```bash
   python -m compileall -q src tests scripts
   python -c "import src.data_collection"
   python -c "import src.data_quality"
   python -c "import src.cleaning"
   python -c "import src.cleaning_pipeline"
   git diff --check
   ```

8. **Thực thi các notebook phân tích (theo đúng thứ tự tuần 03–04):**
   ```bash
   jupyter nbconvert --to notebook --execute notebooks/01_data_collection.ipynb
   jupyter nbconvert --to notebook --execute notebooks/02_quality_audit.ipynb
   jupyter nbconvert --to notebook --execute notebooks/03_data_cleaning.ipynb
   ```
   > [!NOTE]
   > Các notebook này gọi `run_collection_pipeline()`, tải dữ liệu thực tế từ AWS S3 OpenAQ và Open-Meteo API, ghi payload vào `data/raw/` và xuất Parquet vào `data/interim/`. Do phụ thuộc vào kết nối mạng bên ngoài và tệp thô không commit vào Git, quy trình này **chỉ chạy cục bộ** và cố ý không đưa vào CI GitHub Actions tự động (`.github/workflows/ci.yml`).
   >
   > **Thứ tự là bắt buộc.** `03_data_cleaning.ipynb` ghi đè hai tệp canonical trong `data/interim/`, nên `02_quality_audit.ipynb` phải chạy **trước** `03` để báo cáo kiểm toán mô tả đúng trạng thái trước làm sạch. Nếu chạy lại `03` trên artifact đã làm sạch, mã nguồn sẽ **cảnh báo tái lập** và [`docs/cleaning_log.md`](docs/cleaning_log.md) sẽ ghi rõ điều đó.

### Tóm tắt chuỗi tái lập cho người đánh giá

```text
git clone
  → pip install -r requirements.txt                (bước 2–3)
  → python scripts/fetch_dataset.py                (bước 5, cần mạng, có đối chiếu metadata)
  → python -m unittest discover tests              (bước 6, 259 test, offline)
  → jupyter nbconvert --execute notebooks/01_data_collection.ipynb
  → jupyter nbconvert --execute notebooks/02_quality_audit.ipynb
  → jupyter nbconvert --execute notebooks/03_data_cleaning.ipynb  (sinh docs/cleaning_log.md)
  → jupyter nbconvert --execute notebooks/03_transformation_pipeline.ipynb
  → dữ liệu canonical ĐÃ LÀM SẠCH trong data/interim/ sẵn sàng cho Issue #7
  → data/processed/air_pollution_final.parquet (9044 dòng × 18 cột, gitignored)
```

> **Lưu ý khi chạy lại:** `03_data_cleaning.ipynb` cần `data/interim/` ở trạng thái **trước** khi làm sạch. Nếu đã chạy notebook này một lần, hãy khôi phục lại interim từ `data/raw/` trước khi chạy lại — nếu không, `docs/cleaning_log.md` sẽ ghi sai số liệu "trước làm sạch".

---

## 5. Nguyên tắc Quản trị Dữ liệu & Kỹ thuật

- **Bảo toàn dữ liệu thô theo chính sách ba tầng (`data/raw/`):** Tệp thô tải từ API được ghi nguyên trạng dưới `data/raw/` trong quá trình pipeline thực thi (không sửa đổi thủ công, không chuyển đổi giá trị trước khi lưu). Mã băm SHA-256 của từng tệp được lưu trong `data/raw/metadata.json` để kiểm chứng toàn vẹn độc lập. Tệp thô không commit vào Git theo chính sách kho dữ liệu (`.gitignore`: `data/raw/*.json`, `data/raw/*.parquet`) và có thể tái tạo từ nguồn qua pipeline (xem [Mục 3.2 của roadmap](docs/roadmap.md#32-cổng-quyết-định-nguồn-dữ-liệu-issue-19-as-source-selection-gate)).
- **Ngăn chặn rò rỉ dữ liệu chuỗi thời gian (*Temporal Leakage*):** Phân chia tập huấn luyện/kiểm tra phải thực hiện nghiêm ngặt theo trình tự thời gian ($T_{\text{train}} < T_{\text{test}}$). Điểm cắt phải được luận giải từ đặc tính thực nghiệm của tập dữ liệu đã đóng băng (độ bao phủ, kích thước mẫu, tính liên tục, tính đại diện theo mùa), **không** đặt trước một tỷ lệ hay năm cố định. Tuyệt đối không sử dụng phép chia ngẫu nhiên.
- **Tính tiền định (*Determinism*):** Tất cả các phép biến đổi ngẫu nhiên, mô hình hóa đều phải cố định hạt giống số ngẫu nhiên (`random_state=42`). Mọi notebook phải thực thi tuần tự, trơn tru qua thao tác **Restart Kernel & Run All**.
- **Không đưa công nghệ quá mức cần thiết (*No Over-Engineering*):** Với quy mô dữ liệu quan trắc thực tế hiện tại (chuỗi khí tượng 9.072 mốc giờ, chuỗi chất lượng không khí 9.044 giờ lưới sau làm sạch tất định — 8.022 bản ghi quan sát thô trước #6, từ đó reindex chèn thêm 1.022 giờ trống; tập giao thoa thời gian 9.044 mốc giờ với độ phủ khí tượng 100%; tổng dung lượng dưới $20\text{ MB}$), dự án sử dụng định dạng cột nén Snappy **Parquet** và thư viện **Pandas**. Tuyệt đối không sử dụng Apache Spark hay Deep Learning phức tạp làm mất đi tính minh bạch và khả năng giải trình thống kê.

---

## 6. Cam kết Liêm chính Học thuật (Academic Integrity)

Dự án cam kết tuân thủ nghiêm ngặt chuẩn đầu ra CLO4 và quy chế học thuật của Trường Đại học CMC:

- **Dữ liệu thật – Nguồn xác thực:** Toàn bộ dữ liệu sẽ được thu thập từ các nguồn công khai chính thống có thể kiểm chứng sau khi hoàn tất quy trình thẩm định đa nguồn tại Issue #19, đối chiếu theo quy chuẩn Việt Nam (QCVN 05:2023/BTNMT) và khuyến cáo của Tổ chức Y tế Thế giới (WHO 2021).
- **Không ngụy tạo số liệu:** Tuyệt đối không tự ý bịa đặt, can thiệp hoặc sửa đổi dữ liệu thô. Không xóa bỏ các điểm dị biệt thực tế (như các đợt nghịch nhiệt mùa đông hay sự kiện pháo hoa) khi chưa có căn cứ vật lý.
- **Không ngụy tạo độ đo:** Mọi chỉ số thống kê ($R^2$, RMSE, Recall, Precision, PR-AUC, $p$-value, Effect Size) đều là kết quả thực tế thu được từ quá trình chạy mã nguồn trên tập kiểm tra độc lập, không điều chỉnh để tạo ra kết quả "đẹp" giả tạo.
- **Minh bạch giả định:** Luôn kiểm tra và báo cáo trung thực các giả định thống kê (kiểm định phân phối, chẩn đoán 4 giả định LINE trong hồi quy). Khi giả định bị vi phạm, giải trình nguyên nhân và áp dụng phương pháp điều chỉnh thích hợp.

---

## 7. Tuyên bố Sử dụng Trí tuệ Nhân tạo (AI Usage Declaration)

Tuân thủ hướng dẫn về tính minh bạch học thuật trong môn học INFO3020, dự án công khai mức độ hỗ trợ của các công cụ AI:

- **Phạm vi hỗ trợ của AI:** Công cụ AI (Google Gemini, GitHub Copilot) được sử dụng để hỗ trợ:
  - Sinh mã khung cấu trúc (*boilerplate code*) cho repository và cấu hình môi trường.
  - Hỗ trợ rà soát cú pháp, tối ưu hóa định dạng Markdown và biểu thức chính quy.
  - Gợi ý các kỹ thuật kiểm tra tương thích gói thư viện đa nền tảng.
- **Trách nhiệm của sinh viên:** Mọi quyết định về phương pháp luận nghiên cứu, lựa chọn mô hình, suy luận thống kê, kiểm soát rò rỉ dữ liệu, giải thích kết quả khoa học và bảo vệ mã nguồn trước hội đồng hoàn toàn do nhóm sinh viên trực tiếp chịu trách nhiệm và nắm vững từng dòng code.

---

## 8. Hướng Dẫn Đóng Góp

Xem chi tiết quy trình làm việc, quy ước nhánh, chuẩn commit và nguyên tắc bảo vệ dữ liệu tại **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## 9. Giấy phép & Bản quyền

Mã nguồn dự án được phân phối theo giấy phép mã nguồn mở **[MIT License](LICENSE)**. Toàn văn các điều khoản cấp phép được quy định chi tiết tại tệp `LICENSE`.

