# Lịch sử & Audit — INDEX

Ba tài liệu trong thư mục này được tạo ngày **2026-10-03** trên nhánh `docs/repo-history-audit`
(base `origin/main` = `76a6a61`, sau PR #34).

| File | Nội dung |
|---|---|
| [`01_bao_cao_tong_quan.md`](01_bao_cao_tong_quan.md) | Báo cáo tổng quan: kiến trúc 3 tầng dữ liệu, trình tự chạy 8 bước, bảng diff từng phiên bản, 3 sự cố nghiêm trọng nhất, trục review |
| [`02_lich_su_issue_pr_chi_tiet.md`](02_lich_su_issue_pr_chi_tiet.md) | Ghi lại **từng Issue (#1–#19)** và **từng PR (#18–#35)** như một nhật ký thời gian: trạng thái tại thời điểm đó, review/comment đã đưa ra, fix đáp ứng, sai sót còn lại tại thời điểm đó |
| [`03_audit_findings.md`](03_audit_findings.md) | Audit findings: các phần **chưa sửa xong**, **chưa phát hiện ra**, và **rủi ro còn mở** — kèm mức độ và hành động đề xuất |

## Nguồn dữ liệu

- Git history: `git log --merges`, `git show --stat` cho 14 merge commit
- GitHub API qua `gh`: 18 issue, 18 PR, 6 milestone, đầy đủ body + comments + reviews
- Đo đạc runtime tại thời điểm audit: `python -m unittest discover tests` → **311 test OK** trên `origin/main`

## Quy ước

- **Tại thời điểm đó** = trạng thái ngay sau khi PR được merge, trước khi các vòng review/fix sau đó diễn ra.
  Ví dụ: sau PR #22 (29/09 07:06) trạng thái là "14.424 dòng dữ liệu Mỹ được coi là Hà Nội, 0 review".
- Số liệu ghi trong báo cáo M1/M2 đã được **đối chiếu lại với dữ liệu thật trên đĩa** nhiều lần
  (PR #30 và PR #34), nên báo cáo cũ không phải lúc nào cũng khớp trạng thái hiện tại.