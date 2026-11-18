# Biên Bản Đánh Giá Bảo Vệ Đồ Án (Defense Minutes)

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*)  
> **Đơn vị:** Khoa Công nghệ Thông tin & Truyền thông, Trường Đại học CMC  
> **Đề tài:** Phân Tích Mức Độ Ô Nhiễm Không Khí Theo Chuỗi Thời Gian ($\text{PM}_{2.5}$) & Khí Tượng Bề Mặt tại Hà Nội  
> **Nhóm thực hiện:** Nhóm Chủ đề 6 (*Topic 6 Team*)  
> **Trạng thái biểu mẫu:** Biểu mẫu chuẩn bị cho Issue #17 (Task 11.5) — **chưa diễn ra buổi bảo vệ chính thức; mọi thông tin hội đồng để trống để ghi nhận tại buổi chấm**.

---

## 1. Thông Tin Hành Chính Buổi Bảo Vệ

| Hạng mục | Nội dung ghi nhận |
|---|---|
| **Ngày bảo vệ** | `[Chưa điền — ghi nhận tại buổi bảo vệ]` |
| **Thời gian bắt đầu – kết thúc** | `[Chưa điền]` |
| **Phòng / Hình thức** | `[Chưa điền]` |
| **Giảng viên hướng dẫn / Chủ tịch hội đồng** | ThS. Phạm Ngọc Đông *(cập nhật danh sách hội đồng thực tế khi chấm)* |
| **Thành viên hội đồng khác** | `[Chưa điền]` |
| **Thành viên nhóm tham gia** | Huy (`@doctor-cato`), Khương (`@lekhuong123456798-cpu`), Khánh (`@nguyenphanminhkhanh9a-netizen`), Hưng (`@ViolaPeracia`), Hùng (`@Izuki-1780N`) |
| **Commit / Tag tham chiếu** | `[Chưa gắn tag final-defense-submission]` |

---

## 2. Danh Mục Kiểm Tra Bàn Giao Trước Bảo Vệ (Pre-Defense Checklist)

| Tiêu chí kỹ thuật (Issue #17) | Lệnh / Tệp đối chiếu | Trạng thái tại buổi bảo vệ |
|---|---|---|
| Cấu trúc CRISP-DM, liên kết Markdown & DAG 21 issues | `python scripts/audit_defense_readiness.py` | `[ ] Đạt / [ ] Cần bổ sung` |
| Xác thực SHA-256 `metadata.json` & Parquet tách trạm | `python scripts/audit_defense_readiness.py --real-data` | `[ ] Đạt / [ ] Cần bổ sung` |
| Bộ kiểm thử tự động (`unittest`) | `python -m unittest discover tests` (xem [`docs/TEST_SUITE.md`](../docs/TEST_SUITE.md)) | `[ ] Đạt / [ ] Cần bổ sung` |
| Chuỗi notebook `00` → `07` chạy thông suốt | `Restart Kernel & Run All` | `[ ] Đạt / [ ] Cần bổ sung` |
| Hồ sơ Đạo đức, Tài liệu tổng kết & Viva QA (#14–#16) | `docs/datasheet.md`, `docs/viva_qa_prep.md`, `reports/final_report.pdf` | `[ ] Đạt / [ ] Cần bổ sung` |

---

## 3. Nội Dung Thuyết Trình & Phản Biện Hội Đồng (Oral Defense / Viva)

### 3.1. Tóm tắt phần trình bày của nhóm
- `[Ghi nhận diễn biến trình bày, thời lượng thực tế, các kết quả trọng tâm được trình bày]`

### 3.2. Câu hỏi chất vấn của Hội đồng & Phần trả lời của sinh viên

| STT | Thành viên hội đồng | Nội dung câu hỏi | Thành viên trả lời | Tóm tắt câu trả lời & Đánh giá |
|:---:|---|---|---|---|
| 1 | `[Chưa điền]` | `[Chưa điền]` | `[Chưa điền]` | `[Chưa điền]` |
| 2 | `[Chưa điền]` | `[Chưa điền]` | `[Chưa điền]` | `[Chưa điền]` |
| 3 | `[Chưa điền]` | `[Chưa điền]` | `[Chưa điền]` | `[Chưa điền]` |

---

## 4. Kết Luận & Yêu Cầu Chỉnh Sửa Sau Bảo Vệ (Nếu Có)

- **Yêu cầu chỉnh sửa từ Hội đồng:** `[Chưa điền]`
- **Hạn hoàn thiện chỉnh sửa (nếu có):** `[Chưa điền]`
- **Đánh giá chung / Điểm tổng kết (theo biên bản riêng của Khoa):** `[Chưa điền — ghi nhận theo kết quả chính thức từ Hội đồng]`

---

**Xác nhận thư ký / đại diện nhóm:**  
- Thư ký buổi bảo vệ: `__________________________`  
- Đại diện Nhóm Chủ đề 6: `__________________________`
