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
> Dự án đang ở giai đoạn **Milestone 1 (Thiết lập dự án, khảo sát nguồn & thu thập dữ liệu — Tuần 01–02)**. Đã hoàn tất phần thu thập và chuẩn hóa dữ liệu. Toàn bộ các phân tích thống kê, mô hình học máy và các giai đoạn kiểm toán/làm sạch phía sau vẫn là kế hoạch đặc tả trong [`docs/roadmap.md`](docs/roadmap.md) và **chưa được hiện thực hóa**.

### 2.1. Hiện trạng Triển khai (Milestone 1–2)

> [!IMPORTANT]
> **Trạng thái hiện tại sau review:** **Issue #1–#5 đều DONE** (kể cả #4, PR #26 đã merge vào `main`).
> - **Issue #1, #2, #19, #3:** Đã hoàn tất và nghiệm thu (**DONE**).
> - **Issue #4:** PR #26 đã merge vào `main` (**DONE**).
> - **Issue #5:** Bộ kiểm toán chất lượng 6 chiều đã hoàn thành và merge qua PR #27 (`src/data_quality.py`, `docs/data_quality_audit.md`, `notebooks/02_quality_audit.ipynb`) (**DONE**).
> - Toàn bộ các phân tích thống kê nâng cao, mô hình học máy và pipeline tiền xử lý chống rò rỉ phía sau thuộc Milestone 2–6 và **chưa bắt đầu**.

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
- [x] Bộ **71** unit tests tất định cho pipeline thu thập (`tests/test_data_collection.py`) và pipeline kiểm định tự động bằng GitHub Actions (`.github/workflows/ci.yml`).

> [!NOTE]
> **Về dữ liệu thô:** tệp thô tải từ API **không được Git-track** — đây là chính sách kho dữ liệu của repository, không phải thiếu sót. Tính toàn vẹn được kiểm chứng bằng mã băm SHA-256 ghi trong `data/raw/metadata.json`. Xem [Mục 3.2 của roadmap](docs/roadmap.md#32-cổng-quyết-định-nguồn-dữ-liệu-issue-19-as-source-selection-gate).

### 2.2. Kế hoạch thực hiện tiếp theo (Theo `docs/roadmap.md`)
- **Tuần 03–05 (Milestone 2):** ~~Kiểm toán 6 chiều chất lượng dữ liệu~~ ([Issue #5] — **đã xong**, PR #27). Còn lại: làm sạch tất định và lập cleaning log ([Issue #6]), tích hợp dữ liệu, đóng băng tập dữ liệu, phân chia chuỗi thời gian tuyến tính và đóng gói Pipeline chống rò rỉ sang định dạng Parquet ([Issue #7]).
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
│   ├── interim/                        # Dữ liệu trung gian canonical Parquet sau nạp & chuẩn hóa
│   │   └── .gitkeep
│   └── processed/                      # Dữ liệu sạch hoàn chỉnh đóng băng lưu Parquet
│       └── .gitkeep
├── docs/
│   ├── roadmap.md                      # Lộ trình và đặc tả yêu cầu chi tiết 15 tuần (Authoritative Plan)
│   ├── ROADMAP_INFO3020_Air_Pollution.md # Bản sao tham chiếu đề cương gốc (Đã thay thế một phần)
│   ├── research_questions.md           # Câu hỏi nghiên cứu & khung phân tích SQ1–SQ4 [Issue #2]
│   ├── data_dictionary.md              # Từ điển dữ liệu chuẩn hóa Canonical Schema [Issue #2]
│   ├── source_profiling.md             # Mục lục tài liệu thẩm định hồ sơ đa nguồn [Issue #19]
│   ├── source_profiling_decision.md    # Báo cáo thẩm định & quyết định cổng nguồn dữ liệu [Issue #19]
│   ├── data_quality_audit.md           # Báo cáo kiểm toán chất lượng 6 chiều [Issue #5]
│   └── air_quality_project_overview.md # Tài liệu tổng quan định hướng đề tài
├── notebooks/
│   ├── 00_environment_test.ipynb       # Notebook kiểm thử môi trường và nạp thư viện [Issue #1]
│   ├── 01_data_collection.ipynb        # Thực thi pipeline thu thập & kiểm định dữ liệu [Issue #3, #4]
│   └── 02_quality_audit.ipynb          # Trình bày kết quả kiểm toán 6 chiều [Issue #5]
├── scripts/
│   └── fetch_dataset.py                # Tải & kiểm chứng tập dữ liệu từ nguồn công khai (không cần API key)
├── src/
│   ├── __init__.py
│   ├── data_collection.py              # Adapter OpenAQ, Open-Meteo, AirNow và validation [Issue #3, #4]
│   └── data_quality.py                 # Hàm kiểm toán chất lượng 6 chiều & phân tích khuyết thiếu [Issue #5]
├── tests/
│   ├── test_data_collection.py         # 57 unit tests kiểm thử pipeline thu thập và validation [Issue #3, #4]
│   ├── test_data_quality.py            # 14 unit tests cho bộ kiểm toán 6 chiều [Issue #5]
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

6. **Chạy bộ Unit Tests kiểm định toàn trình (80 tests tất định):**
   ```bash
   python -m unittest discover tests -v
   ```
   Bộ gồm **57** unit tests trong `tests/test_data_collection.py` (kiểm chứng adapter OpenAQ, Open-Meteo, AirNow, logic lọc địa lý Hà Nội, kiểm định chất lượng khí tượng `validate_weather_canonical()`, cơ chế đồng bộ thời gian động), **14** unit tests trong `tests/test_data_quality.py` (bộ kiểm toán chất lượng 6 chiều) và **9** unit tests trong `tests/test_fetch_dataset.py` (cơ chế thu thập & kiểm chứng tập dữ liệu) — **tổng cộng 80 test**. Tất cả độc lập với mạng Internet và thực thi tất định trong CI.

7. **Kiểm tra cú pháp và quy chuẩn diff:**
   ```bash
   python -m compileall -q src tests scripts
   python -c "import src.data_collection"
   git diff --check
   ```

8. **Thực thi các notebook phân tích:**
   ```bash
   jupyter nbconvert --to notebook --execute notebooks/01_data_collection.ipynb
   jupyter nbconvert --to notebook --execute notebooks/02_quality_audit.ipynb
   ```
   > [!NOTE]
   > Các notebook này gọi `run_collection_pipeline()`, tải dữ liệu thực tế từ AWS S3 OpenAQ và Open-Meteo API, ghi payload vào `data/raw/` và xuất Parquet vào `data/interim/`. Do phụ thuộc vào kết nối mạng bên ngoài và tệp thô không commit vào Git, quy trình này **chỉ chạy cục bộ** và cố ý không đưa vào CI GitHub Actions tự động (`.github/workflows/ci.yml`).

### Tóm tắt chuỗi tái lập cho người đánh giá

```text
git clone
  → pip install -r requirements.txt                (bước 2–3)
  → python scripts/fetch_dataset.py                (bước 5, cần mạng, có đối chiếu metadata)
  → python -m unittest discover tests              (bước 6, 80 test, offline)
  → jupyter nbconvert --execute notebooks/01_data_collection.ipynb
  → jupyter nbconvert --execute notebooks/02_quality_audit.ipynb
  → dữ liệu canonical trong data/interim/ đã sẵn sàng cho mọi phân tích phía sau
```

---

## 5. Nguyên tắc Quản trị Dữ liệu & Kỹ thuật

- **Bảo toàn dữ liệu thô theo chính sách ba tầng (`data/raw/`):** Tệp thô tải từ API được ghi nguyên trạng dưới `data/raw/` trong quá trình pipeline thực thi (không sửa đổi thủ công, không chuyển đổi giá trị trước khi lưu). Mã băm SHA-256 của từng tệp được lưu trong `data/raw/metadata.json` để kiểm chứng toàn vẹn độc lập. Tệp thô không commit vào Git theo chính sách kho dữ liệu (`.gitignore`: `data/raw/*.json`, `data/raw/*.parquet`) và có thể tái tạo từ nguồn qua pipeline (xem [Mục 3.2 của roadmap](docs/roadmap.md#32-cổng-quyết-định-nguồn-dữ-liệu-issue-19-as-source-selection-gate)).
- **Ngăn chặn rò rỉ dữ liệu chuỗi thời gian (*Temporal Leakage*):** Phân chia tập huấn luyện/kiểm tra phải thực hiện nghiêm ngặt theo trình tự thời gian ($T_{\text{train}} < T_{\text{test}}$). Điểm cắt phải được luận giải từ đặc tính thực nghiệm của tập dữ liệu đã đóng băng (độ bao phủ, kích thước mẫu, tính liên tục, tính đại diện theo mùa), **không** đặt trước một tỷ lệ hay năm cố định. Tuyệt đối không sử dụng phép chia ngẫu nhiên.
- **Tính tiền định (*Determinism*):** Tất cả các phép biến đổi ngẫu nhiên, mô hình hóa đều phải cố định hạt giống số ngẫu nhiên (`random_state=42`). Mọi notebook phải thực thi tuần tự, trơn tru qua thao tác **Restart Kernel & Run All**.
- **Không đưa công nghệ quá mức cần thiết (*No Over-Engineering*):** Với quy mô dữ liệu quan trắc thực tế hiện tại (chuỗi khí tượng 9.072 mốc giờ, chuỗi chất lượng không khí 8.022 bản ghi, tập giao thoa thời gian 8.022 mốc giờ; tổng dung lượng dưới $20\text{ MB}$), dự án sử dụng định dạng cột nén Snappy **Parquet** và thư viện **Pandas**. Tuyệt đối không sử dụng Apache Spark hay Deep Learning phức tạp làm mất đi tính minh bạch và khả năng giải trình thống kê.

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

