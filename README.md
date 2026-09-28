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
> Dự án đang ở giai đoạn **Tuần 01 (Khởi tạo dự án & Thiết lập môi trường)**. Toàn bộ các phân tích thống kê, mô hình học máy và tập dữ liệu là kế hoạch đặc tả trong [`docs/roadmap.md`](docs/roadmap.md) và sẽ được hiện thực hóa tuần tự theo từng tuần học.

### 2.1. Đã triển khai (Tuần 01 – Milestone 1)
- [x] Thiết lập khung cây thư mục chuẩn mực theo vòng đời CRISP-DM.
- [x] Cấu hình file `.gitignore` nghiêm ngặt, cách ly tuyệt đối dữ liệu thô, cache nhị phân, môi trường ảo và thông tin xác thực.
- [x] Tạo file `requirements.txt` cố định phiên bản tương thích với Python 3.10+ (hỗ trợ pre-built wheels cho Windows/Linux/macOS).
- [x] Xây dựng notebook `notebooks/00_environment_test.ipynb` kiểm thử tự động toàn bộ thư viện cốt lõi, kiểm tra I/O Parquet, Matplotlib và Scikit-Learn Pipeline.
- [x] Biên soạn tài liệu `README.md` tiếng Việt với cam kết liêm chính học thuật và hướng dẫn tái lập.
- [x] Xác lập Câu hỏi nghiên cứu mục tiêu và 4 câu hỏi thành phần SQ1–SQ4 đảm bảo tính trung lập khoa học ([`docs/research_questions.md`](docs/research_questions.md)) [Issue #2].
- [x] Xây dựng Từ điển dữ liệu chuẩn hóa trung lập nguồn Canonical Data Schema với 11 trường dữ liệu và 8 thuộc tính chuẩn hóa ([`docs/data_dictionary.md`](docs/data_dictionary.md)) [Issue #2].

### 2.2. Kế hoạch thực hiện tiếp theo (Theo `docs/roadmap.md`)
- **Tuần 02:** Thẩm định hồ sơ đa nguồn và ban hành quyết định nguồn dữ liệu ([Issue #19]); xây dựng pipeline thu thập dữ liệu tự động cho ô nhiễm không khí ([Issue #3]) và khí tượng ([Issue #4]). *(Chưa thu thập dữ liệu)*.
- **Tuần 03–05:** Kiểm toán 6 chiều chất lượng dữ liệu, làm sạch logic vật lý, nội suy chuỗi thời gian có kiểm soát, tích hợp dữ liệu và đóng gói Pipeline chống rò rỉ dữ liệu sang định dạng Parquet.
- **Tuần 06–08:** Phân tích khám phá dữ liệu (EDA), tính toán 4 họ chỉ số thống kê, thiết kế 7 biểu đồ ấn phẩm giải thích theo nguyên tắc Tufte/Cleveland, hoàn thành Báo cáo Giữa kỳ.
- **Tuần 09–11:** Thực hiện kiểm định giả thuyết phi tham số, xây dựng mô hình hồi quy OLS (chẩn đoán LINE), phát triển mô hình phân loại cảnh báo ô nhiễm với điều chỉnh ngưỡng quyết định (*Threshold tuning*).
- **Tuần 12–15:** Đánh giá định kiến dữ liệu (*Bias Audit*), lập Datasheet for Dataset, Model Card 1 trang, hoàn thiện mã nguồn và bảo vệ đồ án cuối kỳ.

---

## 3. Cấu trúc Repository

```text
air-pollution-analysis/
├── .gitignore                          # Quy tắc loại trừ dữ liệu thô, cache, môi trường ảo
├── CONTRIBUTING.md                     # Hướng dẫn đóng góp, quy trình Git và chuẩn mã nguồn
├── LICENSE                             # Giấy phép mã nguồn mở MIT
├── README.md                           # Tài liệu tổng quan, hướng dẫn thiết lập và quản trị
├── requirements.txt                    # Danh sách thư viện phụ thuộc tương thích Python 3.10+
├── data/
│   ├── raw/                            # DỮ LIỆU GỐC BẤT BIẾN (Chỉ đọc, không commit vào Git)
│   │   └── .gitkeep
│   ├── interim/                        # Dữ liệu trung gian sau kiểm toán và tiền xử lý
│   │   └── .gitkeep
│   └── processed/                      # Dữ liệu sạch hoàn chỉnh lưu định dạng Parquet
│       └── .gitkeep
├── docs/
│   ├── roadmap.md                      # Lộ trình và đặc tả yêu cầu chi tiết 15 tuần
│   ├── ROADMAP_INFO3020_Air_Pollution.md
│   ├── research_questions.md           # Câu hỏi nghiên cứu & khung phân tích SQ1–SQ4 [Issue #2]
│   └── data_dictionary.md              # Từ điển dữ liệu chuẩn hóa Canonical Schema [Issue #2]
├── notebooks/
│   └── 00_environment_test.ipynb       # Notebook kiểm thử môi trường và nạp thư viện
├── src/
│   └── __init__.py                     # Package chứa các module mã nguồn Python tái sử dụng
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

4. **Kiểm chứng môi trường bằng Notebook tự động:**
   ```bash
   jupyter nbconvert --to notebook --execute notebooks/00_environment_test.ipynb
   ```
   Nếu lệnh chạy với mã thoát `0` và hiển thị thông báo `ALL ENVIRONMENT TESTS PASSED`, môi trường đã sẵn sàng phục vụ các giai đoạn tiếp theo.

---

## 5. Nguyên tắc Quản trị Dữ liệu & Kỹ thuật

- **Dữ liệu thô bất biến (`data/raw/`):** Tuyệt đối không chỉnh sửa thủ công tệp dữ liệu thô. Mọi thao tác làm sạch và biến đổi phải được thực thi hoàn toàn bằng code có tính tái lập và lưu vào `data/interim/` hoặc `data/processed/`.
- **Ngăn chặn rò rỉ dữ liệu chuỗi thời gian (*Temporal Leakage*):** Phân chia tập huấn luyện/kiểm tra phải thực hiện nghiêm ngặt theo trình tự thời gian (ví dụ: năm 2023 dùng huấn luyện, năm 2024 dùng đánh giá độc lập). Tuyệt đối không sử dụng phép chia ngẫu nhiên.
- **Tính tiền định (*Determinism*):** Tất cả các phép biến đổi ngẫu nhiên, mô hình hóa đều phải cố định hạt giống số ngẫu nhiên (`random_state=42`). Mọi notebook phải thực thi tuần tự, trơn tru qua thao tác **Restart Kernel & Run All**.
- **Không đưa công nghệ quá mức cần thiết (*No Over-Engineering*):** Với quy mô dữ liệu quan trắc 2 năm ($\approx 17.500$ dòng, dung lượng $< 20\text{ MB}$), dự án sử dụng định dạng cột nén Snappy **Parquet** và thư viện **Pandas**. Tuyệt đối không sử dụng Apache Spark hay Deep Learning phức tạp làm mất đi tính minh bạch và khả năng giải trình thống kê.

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

