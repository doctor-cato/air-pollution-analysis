# Báo Cáo Đo Đạc Quy Mô Dữ Liệu & Tối Ưu Hóa Tài Nguyên (Pandas vs. Apache Spark) — Issue #14

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC  
> **Giai đoạn CRISP-DM:** Milestone 5 (Tuần 12 — Big Data, Tài nguyên & Đạo đức Dữ liệu)  
> **Thời điểm đo đạc (UTC):** `2026-11-20T07:20:22Z` | **Số lần lặp (`repeats`):** `5`  
> **Nguyên tắc liêm chính:** Toàn bộ số liệu dưới đây được đo trực tiếp từ tệp Parquet thật trên đĩa (tệp CSV chỉ ghi tạm trong `tempfile.TemporaryDirectory()`, không ghi vào `data/`). Thư viện `polars` **không** được cài đặt trong môi trường dự án nên được ghi nhận rõ là *chưa đo (unbenchmarked)*, không ngụy tạo con số.

---

## 1. Metadata Môi Trường & Phiên Bản Dữ Liệu

| Hạng mục | Giá trị ghi nhận |
|---|---|
| Hệ điều hành (OS) | `Windows-11-10.0.26200-SP0` |
| CPU / Số luồng logic | `AMD64 Family 25 Model 124 Stepping 0, AuthenticAMD` (12 logical cores) |
| Python | `3.14.10` |
| pandas / numpy / pyarrow / scikit-learn | `3.1.1` / `2.5.4` / `26.0.1` / `1.9.1` |
| `polars` / `pyspark` | Không cài đặt (`not installed` — không benchmark giả định) |
| Baseline Dataset (`1.0.0-m2-baseline`) | `air_pollution_final.parquet` — **9,044 × 18** (SHA-256: `866f39de1720c727...`) |
| Extended Dataset (`2.0.0-issue44-extended`) | `air_pollution_extended_2022_2026.parquet` — **37,722 × 23** (SHA-256: `6930557fbfc8e31d...`) |

---

## 2. Bảng So Sánh Hợp Nhất Trước vs. Sau Tối Ưu Hóa (Before vs. After)

Ba tối ưu hóa thực tế được áp dụng và đo kiểm chứng:
1. **Ép kiểu dữ liệu (`float64 -> float32`, cờ `int64 -> int8`, chuỗi danh mục `station_id/location/season/split -> category`)** nhằm giảm trực tiếp RAM chiếm dụng.
2. **Định dạng lưu trữ & nén cột (`CSV` -> `Parquet Snappy` vs. `Parquet Zstd`)** nhằm giảm dung lượng đĩa và tăng thông lượng I/O.
3. **Vector hóa chuỗi thời gian (`groupby().rolling(24)` + nhóm vector)** thay cho vòng lặp Python tuần tự khi tính trung bình trượt 24h và thống kê nhóm kết hợp fit Ridge/LogReg.

| Tập dữ liệu | Chỉ tiêu đo lường | Trước tối ưu (Before: CSV / `float64`+String / Loop) | Sau tối ưu (After: Parquet Snappy / Zstd / `float32`+`category` / Vectorized) | Mức cải thiện |
|---|---|---:|---:|---:|
| **Baseline `VN001`** (9,044×18) | Dung lượng đĩa (MB) | 1.8483 MB (CSV) | 0.2550 MB (Snappy) / **0.2131 MB** (Opt+Zstd) | **-88.5%** (8.67× nhỏ hơn) |
| **Baseline `VN001`** | RAM in-memory (`deep=True`) | 1.6820 MB | **0.5263 MB** | **-68.71%** |
| **Baseline `VN001`** | Độ trễ đọc (median, ms) | 5.252 ms (351.9 MB/s) | **2.622 ms** (Snappy, 97.2 MB/s) / 2.742 ms (Zstd) | **2.00× nhanh hơn** |
| **Baseline `VN001`** | Độ trễ ghi (median, ms) | 109.100 ms (16.9 MB/s) | **9.071 ms** (Snappy, 28.1 MB/s) / 9.666 ms (Zstd) | **12.03× nhanh hơn** |
| **Baseline `VN001`** | Workload phân tích (Groupby + Rolling 24h + OLS/LogReg) | 235.649 ms | **30.400 ms** | **7.75× nhanh hơn** |
| **Extended `VN003+VN001`** (37,722×23) | Dung lượng đĩa (MB) | 8.7952 MB (CSV) | 0.7903 MB (Snappy) / **0.7103 MB** (Opt+Zstd) | **-91.9%** (12.38× nhỏ hơn) |
| **Extended `VN003+VN001`** | RAM in-memory (`deep=True`) | 9.3147 MB | **2.7704 MB** | **-70.26%** |
| **Extended `VN003+VN001`** | Độ trễ đọc (median, ms) | 28.419 ms (309.5 MB/s) | **7.532 ms** (Snappy, 104.9 MB/s) / 6.812 ms (Zstd) | **3.77× nhanh hơn** |
| **Extended `VN003+VN001`** | Độ trễ ghi (median, ms) | 709.822 ms (12.4 MB/s) | **43.788 ms** (Snappy, 18.1 MB/s) / 42.988 ms (Zstd) | **16.21× nhanh hơn** |
| **Extended `VN003+VN001`** | Workload phân tích (Groupby + Rolling 24h + OLS/LogReg) | 971.582 ms | **66.694 ms** | **14.57× nhanh hơn** |

---

## 3. Định Vị Trong Khung 5V & Đối Chiếu Ngưỡng Quy Mô Tuần 12

### 3.1. Phân tích 5V của tập dữ liệu Ô nhiễm Không khí Hà Nội

| Chiều 5V | Đặc điểm định lượng trên tập dữ liệu thực tế | Hàm ý hạ tầng |
|---|---|---|
| **Volume (Khối lượng)** | Baseline: 0.2550 MB Parquet (9,044 dòng); Extended: 0.7903 MB Parquet (37,722 dòng). Tổng hai tệp Parquet = **1.0453 MB (0.001021 GB)**; quy đổi CSV = **10.6435 MB (0.010394 GB)**; RAM đỉnh = **9.31 MB**. | Nhỏ hơn ngưỡng 10 GB hơn **1.000 lần**; nằm gọn trong bộ nhớ đệm L3/RAM máy cá nhân. |
| **Velocity (Tốc độ sinh)** | Tần suất lấy mẫu 1 bản ghi/giờ/trạm (~8.760 dòng/năm/trạm); dữ liệu khí tượng Open-Meteo ERA5 cập nhật hồi cứu theo lô (độ trễ ~5 ngày). | Xử lý theo lô (*batch*), không phát sinh bài toán luồng tốc độ cao (*high-throughput streaming*). |
| **Variety (Đa dạng)** | Hai nguồn dữ liệu bảng/JSON bán cấu trúc (OpenAQ S3 CSV.gz và Open-Meteo ERA5 JSON) đã chuẩn hóa về Canonical Schema dạng bảng phẳng (18–23 cột số/chuỗi/thời gian). | Không có dữ liệu phi cấu trúc quy mô lớn (video, ảnh vệ tinh raw, đồ thị tỷ đỉnh). |
| **Veracity (Độ tin cậy)** | Thách thức lớn nhất của bài toán: khuyết thiếu thành cụm lớn (17,13% ở VN001; 36,51% ở VN003; cụm dài nhất 2.568 giờ), 3.193 bản ghi sentinel `-999/-1/-6`, cờ sương mù `RH > 90%`, và không chồng lấp giữa 2 trạm. | Nút thắt nằm ở **chất lượng & phương pháp thống kê**, không phải năng lực tính toán phân tán. |
| **Value (Giá trị)** | Phân tích quy luật phơi nhiễm PM2.5, kiểm định có xét tự tương quan, hồi quy giải thích và mô hình cảnh báo sớm vượt ngưỡng QCVN 05:2023/BTNMT ($50\,\mu\text{g/m}^3$). | Giá trị tối đa hóa nhờ mô hình giải trình được và pipeline tái lập hoàn chỉnh. |

### 3.2. Đối chiếu ngưỡng kiến trúc Tuần 12 (INFO3020)

| Ngưỡng dung lượng (W12) | Công cụ khuyến nghị | Vị trí dữ liệu dự án |
|---|---|---|
| **< 10 GB** | **Pandas / Polars (Single-node in-memory)** | **DỰ ÁN NẰM TẠI ĐÂY** (Tổng Parquet = **1.0453 MB**; CSV = **10.6435 MB**; RAM đỉnh = **9.31 MB**) |
| 10 – 100 GB | DuckDB / PostgreSQL / SQLite phân vùng | Chưa chạm ngưỡng (nhỏ hơn ngưỡng dưới > 1.000×) |
| > 100 GB (TB–PB) | Apache Spark / Hadoop phân tán | Chưa chạm ngưỡng (nhỏ hơn ngưỡng dưới > 10.000×) |

### 3.3. So sánh chiến lược Scale Up vs. Scale Out

| Tiêu chí | Scale Up (Nâng cấp đơn máy — Pandas + Parquet) | Scale Out (Phân tán cụm — Apache Spark) |
|---|---|---|
| Kiến trúc | Một máy tính cá nhân / máy trạm (CPU đa nhân, RAM 8–32 GB) | Cụm nhiều nút (Driver + Executors trên JVM, mạng shuffle) |
| Chi phí khởi tạo & độ trễ | Gần bằng 0; đọc Extended Parquet chỉ **7.53 ms**, chạy trọn workload vector chỉ **66.69 ms** | Khởi động JVM / SparkSession tốn 3–10 giây, lớn hơn **50–100×** toàn bộ thời gian chạy Pandas |
| Độ phức tạp vận hành | Rất thấp (`pip install -r requirements.txt`, chạy offline trên CI) | Cao (cài Java/JVM, Hadoop winutils trên Windows, cấu hình executor/shuffle) |
| Tương thích hệ sinh thái thống kê | Trực tiếp với `scipy`, `statsmodels` (HAC Newey-West), `scikit-learn` | Thiếu nhiều phép kiểm thống kê chuyên sâu (HAC, block bootstrap) nếu không kéo về driver |
| Phù hợp với dự án | **Tối ưu theo bằng chứng đo đạc** | **Không phù hợp** (lãng phí tài nguyên và tăng rủi ro kỹ thuật không cần thiết) |

---

## 4. Kết Luận Kiến Trúc Dẫn Xuất Từ Bằng Chứng Đo Đạc (Pandas vs. Polars vs. Apache Spark)

1. **Pandas + PyArrow Parquet (Đã đo & chọn dùng):** Trên tập lớn nhất (`extended_2022_2026`, 37,722 × 23), tệp Parquet Snappy chỉ chiếm **0.7903 MB** trên đĩa (Zstd sau ép kiểu giảm xuống **0.7103 MB**, nhỏ hơn CSV **12.38×**), RAM sau tối ưu chỉ còn **2.7704 MB** (giảm **70.26%**), thời gian đọc Parquet là **7.532 ms**, và toàn bộ workload phân tích sau vector hóa hoàn tất trong **66.694 ms** (nhanh hơn **14.57×** so với vòng lặp thuần Python).
2. **Polars (Chưa cài đặt / Unbenchmarked):** Polars là lựa chọn đơn nút hiện đại có hiệu năng đa luồng rất tốt cho dữ liệu bảng từ vài trăm MB tới ~10 GB. Tuy nhiên, trong môi trường dự án hiện tại `polars` **không được cài đặt** và **không được đo thực nghiệm** (tránh thêm phụ thuộc bên thứ ba không cần thiết khi Pandas đã hoàn thành toàn bộ tác vụ trong dưới một giây).
3. **Apache Spark (Không sử dụng — bác bỏ dựa trên số đo):** Với tổng dung lượng dữ liệu thực tế chỉ **10.64 MB** ở định dạng CSV và **1.05 MB** ở định dạng Parquet — thấp hơn ngưỡng khuyến nghị `> 100 GB` của Spark hơn bốn bậc độ lớn — việc triển khai Apache Spark sẽ gây ra chi phí khởi tạo JVM và tuần tự hóa (*serialization overhead*) lớn hơn toàn bộ thời gian xử lý của Pandas, đồng thời làm phức tạp hóa chuỗi kiểm thử CI và tích hợp `statsmodels`/`scikit-learn`. Do đó, kiến trúc **Scale Up đơn nút với Pandas + Parquet Snappy** là lựa chọn tối ưu và nhất quán với nguyên tắc *No Over-Engineering* của INFO3020.
