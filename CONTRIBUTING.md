# Hướng Dẫn Đóng Góp (Contributing Guide)

Tài liệu này quy định quy trình làm việc, chuẩn mực mã nguồn và an toàn dữ liệu cho dự án Phân tích mức độ ô nhiễm không khí theo chuỗi thời gian (môn học INFO3020 – Trường Đại học CMC).

---

## 1. Nguyên Tắc Cốt Lõi

- **Tuân thủ vòng đời CRISP-DM:** Mọi thay đổi phải bám sát mục tiêu nghiên cứu và tiến độ môn học trong [`docs/roadmap.md`](docs/roadmap.md).
- **Dữ liệu thô bất biến:** Thư mục `data/raw/` là chỉ đọc. Tuyệt đối không chỉnh sửa thủ công hoặc commit file dữ liệu thô vào Git.
- **Không rò rỉ dữ liệu chuỗi thời gian:** Chia tập dữ liệu (train/test split) bắt buộc theo thứ tự thời gian. Không dùng random split. Transformer phải fit trên tập train.
- **Tính tái lập:** Cố định `random_state=42`. Toàn bộ notebook phải chạy thành công từ đầu đến cuối qua **Restart Kernel & Run All**.
- **Không over-engineering:** Không đưa vào các công nghệ không cần thiết (Apache Spark, Deep Learning hộp đen) khi dữ liệu có thể xử lý hiệu quả bằng Pandas và Parquet.

---

## 2. Quy Trình Làm Việc (Git Workflow)

Dự án áp dụng mô hình Feature Branch trên GitHub:

```text
main ───────────────────────────────────────────► (ổn định)
       \                                       /
        └── feat/issue-X-mo-ta ───► PR review ─┘
```

### Bước 1: Tạo nhánh làm việc
Luôn cập nhật nhánh `main` mới nhất trước khi tạo nhánh:
```bash
git checkout main
git pull origin main
git checkout -b <loại-nhánh>/<mã-issue>-<mô-tả-ngắn>
```

**Quy ước tiền tố nhánh:**
- `feat/`: Tính năng mới (pipeline thu thập, làm sạch, mô hình hóa).
- `fix/`: Sửa lỗi logic, sửa rò rỉ dữ liệu, sửa bug code.
- `docs/`: Cập nhật tài liệu (`README.md`, `docs/`, `CONTRIBUTING.md`).
- `refactor/`: Tái cấu trúc mã nguồn (chuyển code từ notebook sang `src/`).
- `chore/`: Cấu hình môi trường, cập nhật dependencies, bảo trì Git.

*Ví dụ:* `feat/issue-2-data-dictionary`, `fix/issue-6-timestamp-reindex`.

### Bước 2: Phát triển và kiểm thử cục bộ
- Viết code sạch, tuân thủ PEP 8.
- Chuyển các hàm tái sử dụng hoặc có độ dài > 30 dòng từ notebook vào thư mục `src/`.
- Kiểm tra tính tương thích của môi trường:
  ```bash
  pip install -r requirements.txt
  jupyter nbconvert --to notebook --execute notebooks/<tên_notebook>.ipynb
  ```

### Bước 3: Quy ước Commit
Dự án sử dụng chuẩn [Conventional Commits](https://www.conventionalcommits.org/):

```text
<loại>(<phạm-vi>): <mô tả ngắn gọn bằng mệnh lệnh>

- Chi tiết các thay đổi cụ thể
- Kết quả kiểm chứng đạt được
```

*Ví dụ:*
```text
feat(pipeline): thêm hàm reindex chuỗi thời gian theo lưới 1 giờ

- Bổ sung reindex_hourly_grid trong src/cleaning_pipeline.py
- Nội suy tuyến tính cho khoảng khuyết <= 2 giờ
- Tạo cột missing indicator pm25_was_missing cho khoảng khuyết lớn
```

### Bước 4: Kiểm tra Diff trước khi Push
Trước khi commit và push, luôn chạy:
```bash
git status
git diff
```
**Kiểm tra an toàn:**
- [ ] Không có file dữ liệu thô (`.json`, `.csv`, `.parquet` trong `data/raw/`).
- [ ] Không có secret, API key hay file `.env`.
- [ ] Không có cache (`__pycache__/`, `.ipynb_checkpoints/`) hay môi trường ảo.

### Bước 5: Mở Pull Request (PR)
1. Đẩy nhánh lên GitHub:
   ```bash
   git push -u origin <tên-nhánh>
   ```
2. Tạo Pull Request trỏ vào nhánh `main`.
3. Điền mô tả PR:
   - Tóm tắt mục đích và nội dung thay đổi.
   - Dẫn chiếu Issue liên quan (ví dụ: `Closes #2`).
   - Bằng chứng kiểm chứng (lệnh test và kết quả thực tế).
4. Nhận review từ thành viên nhóm, chỉnh sửa nếu cần trước khi merge.
5. Merge bằng phương thức **Squash and merge** để giữ lịch sử nhánh `main` gọn gàng.

---

## 3. Tiêu Chuẩn Tài Liệu Hóa

- **Ngôn ngữ:** Toàn bộ tài liệu báo cáo, từ điển dữ liệu, nhật ký làm sạch và giải thích biểu đồ viết bằng **Tiếng Việt**.
- **Trung thực:** Báo cáo đúng hiện trạng triển khai, không tuyên bố hoàn thành các hạng mục còn nằm trong lộ trình kế hoạch.
