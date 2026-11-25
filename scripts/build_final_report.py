"""Build reports/final_report.html (+ PDF via headless Chrome) and
docs/final_report_traceability.md for Issue #16.

Usage:
    py -3.14 scripts/build_final_report.py                       # in-repo
    py -3.14 scripts/build_final_report.py --input-root <main>   # worktree

Every cited number is backed by a (source, needle) check in
scripts/_report_common.py::CHECKS; the build aborts if any is missing.
OLS coefficients are reported strictly as observational associations.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _report_common import (BASELINE, EXTENDED, REPO_ROOT, V_BASE, V_EXT, fig_src,  # noqa: E402
                            parse_args, render_pdf, report_pdf, table, verify_sources)

B_ST, E_ST = "VN001", "VN003"
TRACE: list[tuple[str, str, str, str, str, str]] = []
_counters = {"Bảng": 0, "Hình": 0}


def trace(label: str, item: str, source: str, station: str, version: str, repro: str) -> None:
    TRACE.append((label, item, source, station, version, repro))


def tbl(caption: str, headers, rows, source: str, station: str, version: str, repro: str,
        cls: str = "") -> str:
    _counters["Bảng"] += 1
    label = f"Bảng {_counters['Bảng']}"
    trace(label, caption, source, station, version, repro)
    return (f'<div class="tbl"><p class="cap"><b>{label}.</b> {caption} '
            f'<span class="tag">{station} · {version}</span></p>{table(headers, rows, cls)}</div>')


def fig(key: str, caption: str, out: Path, source: str, station: str, version: str,
        repro: str, width: str = "100%") -> str:
    _counters["Hình"] += 1
    label = f"Hình {_counters['Hình']}"
    trace(label, caption, source, station, version, repro)
    return (f'<figure><img src="{fig_src(key, out)}" style="max-width:{width}" alt="{label}">'
            f'<figcaption><b>{label}.</b> {caption} '
            f'<span class="tag">{station} · {version}</span></figcaption></figure>')


CSS = """
@page { size: A4; margin: 16mm 15mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1b1f24; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4mm; color: #0b3d5c; }
h2 { font-size: 14pt; color: #0b3d5c; border-bottom: 1.5px solid #0b3d5c; padding-bottom: 1mm; margin: 7mm 0 3mm; break-after: avoid; }
h3 { font-size: 11.5pt; color: #164e63; margin: 4mm 0 1.5mm; break-after: avoid; }
p { margin: 0 0 2.5mm; text-align: justify; }
ul, ol { margin: 0 0 3mm 5mm; padding-left: 4mm; }
li { margin-bottom: 1mm; }
.cover { text-align: center; padding: 28mm 0 10mm; }
.cover .sub { font-size: 12pt; color: #374151; }
.cover .meta { margin-top: 12mm; font-size: 11pt; }
.pb { break-before: page; }
.tbl, figure { break-inside: avoid; margin: 3mm 0 4mm; }
table { border-collapse: collapse; width: 100%; font-size: 8.8pt; break-inside: avoid; }
th, td { border: 0.6pt solid #9aa5b1; padding: 1.2mm 1.8mm; vertical-align: top; text-align: left; }
th { background: #e6eef4; }
tr:nth-child(even) td { background: #f7f9fb; }
.cap, figcaption { font-size: 9pt; color: #374151; margin: 1mm 0 1.5mm; }
figure { text-align: center; }
figure img { height: auto; border: 0.5pt solid #d1d5db; }
figcaption { text-align: left; }
.tag { background: #eef2ff; color: #3730a3; border-radius: 2px; padding: 0 1.5mm; font-size: 8pt; white-space: nowrap; }
.box { border-left: 3pt solid #b45309; background: #fff7ed; padding: 2mm 3mm; margin: 3mm 0; break-inside: avoid; }
.box.ok { border-color: #047857; background: #ecfdf5; }
.box.bad { border-color: #b91c1c; background: #fef2f2; }
code { font-family: Consolas, monospace; font-size: 8.8pt; background: #f1f5f9; padding: 0 1mm; }
"""


def build_html(out: Path) -> str:
    h: list[str] = []
    A = h.append

    A(f"""<div class="cover">
<p class="sub">Đại học CMC · INFO3020 – Nhập môn Khoa học Dữ liệu</p>
<h1>Phân tích PM<sub>2,5</sub> đô thị Hà Nội và mô hình cảnh báo sớm<br>dựa trên dữ liệu quan trắc OpenAQ và khí tượng ERA5</h1>
<p class="sub">Báo cáo cuối kỳ (Issue #16) · cấu trúc SCQA · CRISP-DM</p>
<div class="meta"><p><b>Nhóm 6</b> · Giảng viên hướng dẫn: ThS. Phạm Ngọc Đông</p>
<p>Phạm vi dữ liệu: trạm cơ sở <code>VN001</code> (<code>{V_BASE}</code>) và trạm lịch sử <code>VN003</code> (<code>{V_EXT}</code>) – phân tích tách trạm (Protocol A), không gộp.</p></div>
</div>
<div class="box"><b>Nguyên tắc liêm chính.</b> Mọi con số trong báo cáo được trích nguyên văn từ các tệp kết quả đã lưu trong kho (xem <code>docs/final_report_traceability.md</code>);
bản dựng tự động từ chối xuất báo cáo nếu một số liệu dẫn nguồn không còn khớp tệp gốc. Hệ số hồi quy chỉ là <b>liên hệ quan sát</b> (<i>ceteris paribus</i>), không phải hiệu ứng nhân quả.
Kiểm định giả thuyết xác nhận (baseline <code>VN001</code>) được tách bạch với kết quả <b>thăm dò</b> (mùa, mở rộng đa năm).</div>""")

    # ---------------- S ----------------
    A('<h2 class="pb">1. Bối cảnh (Situation)</h2>')
    A("""<p>PM<sub>2,5</sub> là chỉ tiêu bụi mịn gắn với rủi ro hô hấp–tim mạch; Quy chuẩn QCVN 05:2023/BTNMT quy định ngưỡng trung bình 24 giờ 50 µg/m³ và trung bình năm 25 µg/m³.
Đồ án phân tích chuỗi thời gian PM<sub>2,5</sub> đô thị Hà Nội kết hợp tái phân tích khí tượng bề mặt Open-Meteo/ERA5 và xây dựng mô hình giải thích (hồi quy) cùng mô hình cảnh báo vượt ngưỡng (phân loại), theo CRISP-DM.</p>""")
    A(tbl("Hai phạm vi dữ liệu được đóng băng và tách trạm (Protocol A)",
          ["Hạng mục", f"<code>{B_ST}</code> – baseline", f"<code>{E_ST}</code> – mở rộng lịch sử"],
          [["Trạm", f"<code>{BASELINE}</code> (556 Nguyễn Văn Cừ)", f"<code>{EXTENDED}</code> (OpenAQ S3 Location 7441)"],
           ["Phiên bản dữ liệu", f"<code>{V_BASE}</code>", f"<code>{V_EXT}</code>"],
           ["Khoảng thời gian", "07/2025 – 07/2026", "01/2022 – 04/2025"],
           ["Lưới giờ / giờ PM2,5 hợp lệ", "9.044 / 7.495", "28.678 / 18.208"],
           ["Giờ thiếu (tỷ lệ)", "1.549 (17,13%)", "10.470 (36,51%)"],
           ["Ngày đủ ≥ 18/24 giờ", "299", "756"],
           ["SHA-256 (tệp dữ liệu)", "<code>866f39de…2586efd</code>", "<code>6930557f…9a1f9b02</code> (snapshot lưu)"]],
          "reports/extended_reanalysis_comparison.md; docs/issue44_dataset_contract.md; reports/classification_results.md",
          "VN001 / VN003", f"{V_BASE} / {V_EXT}", "scripts/build_extended_historical_dataset.py; scripts/run_extended_reanalysis.py"))
    A(f"""<ul>
<li><b>Quản trị nguồn (provenance):</b> SHA-256 của dữ liệu baseline được kiểm chứng bất biến trước/sau Issue #15; với dữ liệu mở rộng, báo cáo Issue #50 ghi rõ SHA thực tế khác snapshot lưu (<i>byte match: False</i>), do đó đối sánh với snapshot thời tiết gốc ở mức nội dung được ghi <b>UNVERIFIED</b>.</li>
<li><b>Tách trạm, không gộp (Protocol A):</b> hai trạm cách nhau <b>7,324 km</b>, <b>0 giờ</b> chồng lấn thời gian và cách quãng <b>2.040 giờ</b> không báo cáo; vì vậy chênh lệch giữa hai trạm không thiết lập được xu hướng theo thời gian tại một địa điểm (Protocol B – gộp nhóm – bị bác bỏ vì rò rỉ thời gian chéo trạm).</li>
<li><b>VN002 (US Embassy mirror):</b> kết luận <b>NO-GO</b>; không dùng làm nguồn dữ liệu trong báo cáo này.</li></ul>""")

    # ---------------- C ----------------
    A('<h2>2. Phức tạp (Complication)</h2>')
    A("""<p>Các phức tạp dưới đây đều được rút từ bằng chứng thực nghiệm của dự án, không phải giả định:</p>
<ol>
<li><b>Phân phối lệch phải, đuôi dày:</b> trên <code>VN001</code> PM<sub>2,5</sub> có trung vị 37,32, trung bình 43,76 µg/m³, độ lệch 1,295; trung bình–SD không đại diện cho mức phơi nhiễm điển hình.</li>
<li><b>Tự tương quan mạnh:</b> ACF bậc 1 chuỗi giờ là 0,9403; chuỗi ngày có ρ₁ = 0,728 (<code>VN001</code>) và 0,749 (<code>VN003</code>) ⇒ cỡ mẫu hiệu dụng chỉ n<sub>eff</sub> ≈ 47,1 (trên 299 ngày) và 108,7 (trên 756 ngày); p-value giả định độc lập là phản bảo thủ.</li>
<li><b>Khuyết thiếu thành cụm, không MCAR:</b> cụm gián đoạn dài nhất 630 giờ (<code>VN001</code>, mùa hè 2026) và 2.568 giờ (<code>VN003</code>, 2022).</li>
<li><b>Bốn giả định LINE của OLS đều bị vi phạm</b> trên cả ba phạm vi hồi quy ⇒ R² và p-value cổ điển không được dùng như bằng chứng dự báo hoặc nhân quả.</li>
<li><b>Chồng lấn nhãn–đặc trưng và độ trễ dữ liệu:</b> ở h = 0, trung bình trượt 24 giờ quá khứ chia sẻ 23/24 giờ (95,8%) với nhãn; ERA5 có độ trễ phát hành ~5 ngày nên mô hình ở h = 0 là <i>nowcast hồi cứu</i>, không phải cảnh báo thời gian thực.</li></ol>""")

    # ---------------- Q ----------------
    A('<h2>3. Câu hỏi nghiên cứu (Question)</h2>')
    A("""<p><b>Câu hỏi chính (RQ).</b> Với dữ liệu quan trắc hiện có của Hà Nội, những đặc trưng thống kê, chu kỳ thời gian và liên hệ khí tượng nào của PM<sub>2,5</sub> có thể được xác lập một cách trung thực (có xét tự tương quan, rò rỉ thời gian và khuyết thiếu), và chúng hỗ trợ đến đâu cho việc cảnh báo sớm vượt ngưỡng QCVN 24 giờ?</p>
<ul>
<li><b>SQ1 – Phân phối &amp; thước đo:</b> độ lệch, đuôi, và thống kê mô tả nào (trung vị/IQR so với trung bình/SD) đại diện tốt nhất?</li>
<li><b>SQ2 – Chu kỳ &amp; suy luận:</b> PM<sub>2,5</sub> có khác biệt theo mùa, ngày làm việc/cuối tuần không, và so với QCVN 50/25 µg/m³ ra sao sau khi xử lý tự tương quan?</li>
<li><b>SQ3 – Hồi quy giải thích:</b> biến khí tượng liên hệ thế nào với PM<sub>2,5</sub> giờ (<i>ceteris paribus</i>) và 4 giả định LINE có thỏa mãn không?</li>
<li><b>SQ4 – Phân loại cảnh báo:</b> làm sao xử lý mất cân bằng lớp, chọn ngưỡng xác suất và ngăn bốn dạng rò rỉ để phát hiện trung bình 24 giờ ≥ 50 µg/m³?</li></ul>""")

    # ---------------- A ----------------
    A('<h2 class="pb">4. Câu trả lời (Answer)</h2>')
    A('<h3>4.1. Thống kê mô tả bốn họ và chu kỳ (Issue #8, #9)</h3>')
    A(tbl("Mô tả PM2,5 – hai trạm tách biệt (đơn vị µg/m³)",
          ["Trạm", "Trung vị / Trung bình", "SD / IQR", "ρ₁ ngày / n<sub>eff</sub>", "Liên hệ tuyến tính khí tượng mạnh nhất"],
          [[f"<code>{B_ST}</code>", "37,32 / 43,76", "27,89 / 30,73", "0,728 / 47,1", "surface_pressure: r = 0,291 (n = 7.495)"],
           [f"<code>{E_ST}</code>", "38,00 / 45,83", "30,65 / 32,00", "0,749 / 108,7", "surface_pressure: r = 0,298 (n = 18.208)"]],
          "reports/extended_reanalysis_comparison.md; reports/statistical_profile.csv (VN001)",
          "VN001 / VN003", f"{V_BASE} / {V_EXT}", "notebooks/04_descriptive_stats.ipynb; scripts/run_extended_reanalysis.py"))
    A("""<p>Trên <code>VN001</code>, phân vị 95 và 99 của PM<sub>2,5</sub> lần lượt là 101,87 và 133,79 µg/m³, cực đại 198,95; độ nhọn dư 1,913. Hai trạm có trung vị gần nhau nhưng là hai địa điểm vật lý khác nhau, nên không suy ra xu hướng 2022–2026 tại một điểm.</p>""")
    A(fig("FIG-01", "Chuỗi thời gian PM2,5 đa thang đo kèm đường tham chiếu QCVN (baseline).", out,
          "figures/FIG-01.png", B_ST, V_BASE, "notebooks/04_descriptive_stats.ipynb (src/visualizer.py)", "92%"))
    A(fig("FIG-02", "Phân phối PM2,5 lệch phải (histogram + KDE + boxplot, baseline).", out,
          "figures/FIG-02.png", B_ST, V_BASE, "notebooks/04_descriptive_stats.ipynb (src/visualizer.py)", "85%"))
    A(fig("FIG-03", "Boxplot theo tháng và theo mùa (baseline; một chu kỳ mùa duy nhất).", out,
          "figures/FIG-03.png", B_ST, V_BASE, "notebooks/04_descriptive_stats.ipynb (src/visualizer.py)", "85%"))
    A(fig("FIG-04", "Bản đồ nhiệt giờ trong ngày × thứ trong tuần (UTC+7, baseline).", out,
          "figures/FIG-04.png", B_ST, V_BASE, "notebooks/04_descriptive_stats.ipynb (src/visualizer.py)", "85%"))
    A(fig("FIG-05", "Quan hệ biến khí tượng – PM2,5 với đường LOWESS phi tham số (baseline).", out,
          "figures/FIG-05.png", B_ST, V_BASE, "notebooks/04_descriptive_stats.ipynb (src/visualizer.py)", "80%"))
    A(fig("FIG-06", "Ma trận tương quan kép Pearson và Spearman (baseline).", out,
          "figures/FIG-06.png", B_ST, V_BASE, "notebooks/04_descriptive_stats.ipynb (src/visualizer.py)", "85%"))
    A(fig("FIG-07", "Phân bố tần suất theo hạng chất lượng không khí (baseline).", out,
          "figures/FIG-07.png", B_ST, V_BASE, "notebooks/04_descriptive_stats.ipynb (src/visualizer.py)", "85%"))
    A('<div class="box">Các Hình 1–7 là bộ 7 hình công bố của <b>baseline <code>VN001</code></b> (<code>' + V_BASE + '</code>); chúng <b>không</b> được gán nhãn là dữ liệu mở rộng. Các hình mở rộng bên dưới ghi rõ trạm và phiên bản <code>' + V_EXT + '</code>.</div>')
    A(fig("FIG-01-EXT", "Chuỗi PM2,5 lịch sử mở rộng, hai trạm tách riêng, không nối thành một chuỗi.", out,
          "figures/FIG-01-extended-historical.png", f"{E_ST} + {B_ST} (tách)", V_EXT,
          "scripts/build_extended_historical_dataset.py", "92%"))
    A(fig("FIG-02-EXT", "Phân phối PM2,5 mở rộng theo trạm.", out,
          "figures/extended/FIG-02-extended.png", f"{E_ST} / {B_ST}", V_EXT,
          "scripts/run_extended_reanalysis.py", "80%"))
    A(fig("FIG-03-EXT", "Mùa và năm mở rộng theo trạm (thăm dò, chu kỳ chưa đủ để tách mùa khỏi xu hướng).", out,
          "figures/extended/FIG-03-extended.png", f"{E_ST} / {B_ST}", V_EXT,
          "scripts/run_extended_reanalysis.py", "80%"))
    A(fig("FIG-03B-EXT", "Độ phủ các mùa đông theo trạm – minh họa giới hạn dữ liệu mùa đông.", out,
          "figures/extended/FIG-03b-winter-coverage.png", f"{E_ST} / {B_ST}", V_EXT,
          "scripts/run_extended_reanalysis.py", "80%"))

    # --- 4.2 inference
    A('<h3 class="pb">4.2. Suy luận thống kê có xét phụ thuộc thời gian (Issue #11, #50)</h3>')
    A("""<p>Đơn vị phân tích là trung bình ngày (≥ 18/24 giờ có dữ liệu; n = 299 ngày trên <code>VN001</code>). Mọi p-value xác nhận được dựng lại <b>dưới H₀ có phụ thuộc</b>: bootstrap khối trên <b>lịch ngày</b> (khối 28 ngày lịch, mặt nạ ngày thiếu đi theo bản sao, nhãn nhóm ở vị trí đích), 5.000 lần cho null và 1.000 lần cho CI, seed 42; họ Holm cố định 4 kiểm định, không thu hẹp sau khi xem kết quả. Monte Carlo đa kịch bản cho thấy kiểm định Wald HAC cho mùa có kích thước thực 30–55% thay vì 5% (kịch bản độc lập: 0,304), nên kiểm định mùa luôn được hạ xuống <b>thăm dò</b> theo quy tắc R5 (một chu kỳ mùa, mùa lẫn với xu hướng).</p>""")
    A(tbl("Bốn kiểm định W9 – baseline (bộ bốn: thống kê, p hiệu chỉnh phụ thuộc → p Holm, effect size, CI 95% block-bootstrap)",
          ["Kiểm định", "Thống kê", "p (hiệu chỉnh phụ thuộc)", "p Holm", "Effect size", "CI 95%", "Trạng thái"],
          [["Khác biệt 4 mùa", "H = 61,534", "0,0280", "0,0560", "ε² = 0,206", "—(omnibus; xem tương phản đông–hè ở báo cáo nguồn)", "<b>THĂM DÒ</b> (R5)"],
           ["Ngày làm việc vs cuối tuần", "t (HAC) = 1,611", "0,1082", "0,1082", "|r<sub>rb</sub>| = 0,117", "Δ trung vị −2,74: [−11,13; 3,05]", "Không bác bỏ H₀ (MDE ≈ 7,75)"],
           ["Trung bình ngày vs 50 µg/m³ (24 giờ)", "t (tỷ lệ, HAC) = −2,656", "0,0083", "0,0250", "r (cặp) = −0,410", "Tỷ lệ ngày > 50: 0,2809 [0,119; 0,443]", "<b>XÁC NHẬN</b>"],
           ["Trung bình giai đoạn vs 25 µg/m³", "t (HAC) = 4,354", "1,84·10⁻⁵", "7,38·10⁻⁵", "Cohen's d = 0,848", "Trung bình ngày 43,38 [35,1; 51,7]", "<b>XÁC NHẬN</b>"]],
          "reports/inference_results.md; reports/extended_reanalysis_comparison.md (CI)",
          "VN001", V_BASE, "notebooks/05_statistical_inference.ipynb; src/inference.py::run_inference",
          cls="wide"))
    A("""<div class="box">Giá trị p “tham chiếu” giả định độc lập (ví dụ 2,76·10⁻¹³ cho mùa) <b>không</b> được dùng để kết luận. Kiểm định so với 25 µg/m³ là phép so sánh thống kê trên tập ngày đủ độ phủ, <b>không</b> phải xác định tuân thủ pháp lý QCVN. Hiệu ứng ngày làm việc/cuối tuần nhỏ hơn MDE nên dữ liệu không đủ độ phân giải để khẳng định “không khác biệt”.</div>""")
    A(tbl("Tái phân tích mở rộng W9 (Issue #50) – tách trạm, thăm dò theo mức bằng chứng đã định",
          ["Kiểm định", "Ước lượng chính [CI 95%] – VN001", "Ước lượng chính [CI 95%] – VN003", "Holm p (VN001 / VN003)", "Phân loại"],
          [["Mùa (omnibus)", "61,53 (H)", "164,2 (H)", "0,05599 / 0,0003999", "THĂM DÒ / KHÔNG SO SÁNH ĐƯỢC"],
           ["Ngày làm việc vs cuối tuần", "3,709 [−0,822; 8,24]", "−0,256 [−3,86; 3,34]", "0,1082 / 0,889", "Hướng hiệu ứng khác nhau giữa hai trạm"],
           ["QCVN 24 giờ (tỷ lệ ngày vượt)", "0,2809 [0,119; 0,443]", "0,3148 [0,222; 0,408]", "0,02501 / 0,0003162", "Cùng chiều; CI chồng lấn"],
           ["QCVN trung bình năm", "43,38 [35,1; 51,7]", "45,8 [40,2; 51,4]", "7,375e-05 / 2,171e-12", "Cùng chiều; CI chồng lấn"]],
          "reports/extended_reanalysis_comparison.md; reports/extended_inference_results.md",
          "VN001 / VN003", V_EXT, "scripts/run_extended_reanalysis.py; scripts/validate_extended_reanalysis.py"))
    A("""<p>Số ngày có trung bình ngày > 50 µg/m³ là 84/299 (<code>VN001</code>) và 238/756 (<code>VN003</code>). “Cùng chiều” chỉ nghĩa là cả hai trạm bác bỏ H₀ sau Holm với cùng dấu, <b>không</b> có nghĩa hai trạm chia sẻ một hiệu ứng. Cỡ mẫu hiệu dụng của <code>VN003</code> (108,7) vẫn nhỏ hơn nhiều so với 756 ngày danh nghĩa.</p>""")

    # --- 4.3 regression
    A('<h3 class="pb">4.3. Hồi quy OLS, HAC-24 và chẩn đoán LINE (Issue #12)</h3>')
    A("""<p>Mô hình giải thích dùng 9 biến (5 khí tượng và 4 hạng điều hòa chu kỳ), sai số chuẩn HAC Newey–West (24 giờ), kèm Ridge/Lasso, VIF và khoảng cách Cook. Loại <code>pm10</code>, <code>pm25_was_missing</code>, <code>is_high_humidity_fog</code> khỏi ma trận đặc trưng. Mọi hệ số mang nghĩa <b>liên hệ quan sát trong miền giá trị huấn luyện, giữ nguyên các biến khác</b>; không diễn giải nhân quả.</p>""")
    A(tbl("Bốn giả định LINE – cả bốn đều bị vi phạm (kiểm định trên Train)",
          ["Giả định", "Kiểm định", "VN001 baseline (n = 4.279)", "VN001 mở rộng (n = 6.749)", "VN003 mở rộng (n = 13.835)", "Kết luận"],
          [["L – Tuyến tính", "Ramsey RESET (p = 2)", "F = 223,27 (p = 3,02e-49)", "F = 615,42 (p = 4,40e-130)", "F = 243,15 (p = 2,35e-54)", "Vi phạm nghiêm trọng"],
           ["I – Độc lập", "Durbin–Watson, ACF(1)", "DW = 0,2430; ACF(1) = 0,8785", "DW = 0,2079; ACF(1) = 0,8960", "DW = 0,3033; ACF(1) = 0,8484", "Vi phạm nặng"],
           ["N – Chuẩn", "Jarque–Bera", "JB = 392,7", "JB = 1641,1", "JB = 51355,1", "Vi phạm"],
           ["E – Phương sai đều", "Breusch–Pagan LM", "LM = 658,27", "LM = 513,49", "LM = 701,19", "Vi phạm"]],
          "docs/regression_findings.md §4; reports/regression_results.md",
          "VN001 / VN003", f"{V_BASE} / {V_EXT}", "notebooks/06_regression_modeling.ipynb; src/regression.py", cls="wide"))
    A("""<ul>
<li><b>Đa cộng tuyến:</b> VIF cao nhất ở baseline là <code>surface_pressure</code> = 8,061 (trung bình–cao, 5 ≤ VIF &lt; 10), không vượt 10.</li>
<li><b>HAC thay đổi suy luận:</b> với <code>precipitation</code> ở baseline, p cổ điển 0,0060 trở thành 0,0808 khi dùng HAC-24 (mất ý nghĩa mức 5%).</li>
<li><b>Tốc độ gió bền vững:</b> trong miền quan sát, mỗi 1 m/s tăng của gió <i>liên hệ với</i> mức PM<sub>2,5</sub> thấp hơn 6,07–7,29 µg/m³ (β = −6,0673 ở <code>VN001</code> baseline; −7,2891 ở <code>VN001</code> mở rộng; −6,2864 ở <code>VN003</code>), giữ nguyên các biến khác. Đây là liên hệ quan sát, không phải hiệu ứng nhân quả của gió.</li></ul>""")
    A(tbl("Khái quát hóa theo thời gian của OLS (không trễ, tập Test theo trình tự thời gian)",
          ["Phạm vi", "Hệ số wind_speed (HAC-24 SE)", "Test R²", "Test RMSE (µg/m³)", "Ghi chú"],
          [["VN001 baseline (cắt 2026-01-15)", "−6,0673 (1,1173)", "−1,954", "41,4604", "R² âm: kém hơn dự báo bằng trung bình Train – ngoại suy mùa"],
           ["VN001 mở rộng 80/20", "−7,2891 (0,7769)", "−0,1073", "21,1167", "Test rơi vào mùa hè–đợt mất dữ liệu"],
           ["VN003 mở rộng 80/20", "−6,2864 (0,4482)", "+0,1498", "32,8238", "Giải thích được phần nhỏ phương sai"]],
          "reports/sensitivity_analysis.md §5", "VN001 / VN003", f"{V_BASE} / {V_EXT}",
          "scripts/run_sensitivity_analysis.py"))
    A(fig("REG-DIAG", "Bảng chẩn đoán LINE: phần dư–giá trị khớp, Q–Q, scale–location, Cook's D (baseline).", out,
          "figures/regression_line_diagnostics.png", B_ST, V_BASE, "notebooks/06_regression_modeling.ipynb", "100%"))
    A("""<p>R² ngoài mẫu âm ở baseline cho thấy mô hình tuyến tính khí tượng không đủ để dự báo vận hành; hệ số chỉ có giá trị mô tả xu hướng liên hệ cục bộ. Thêm trung bình trượt 24 giờ cải thiện R² (0,3541 ở baseline; 0,4981 ở <code>VN003</code>) nhưng bản chất là thông tin tự hồi quy, không phải bằng chứng cho vai trò khí tượng.</p>""")

    # --- 4.4 classification
    A('<h3 class="pb">4.4. Phân loại cảnh báo vượt ngưỡng (Issue #13)</h3>')
    A("""<p>Nhãn: trung bình trượt 24 giờ quan sát ≥ 50 µg/m³ (QCVN 24 giờ), không nội suy nhãn. Chia theo thời gian, tinh chỉnh ngưỡng xác suất theo F₂ trên Train (TimeSeriesSplit), pipeline chống rò rỉ, <b>không dùng SMOTE</b> (dùng trọng số lớp). Chỉ số trọng tâm là Recall và PR-AUC so với tỷ lệ dương (đường cơ sở), không dùng Accuracy đơn lẻ.</p>""")
    A(tbl("Hiệu năng trên tập Test độc lập – baseline VN001 (2.302 giờ hợp lệ; 666 ca dương; tỷ lệ dương 28,93%)",
          ["Mô hình", "PR-AUC", "Recall", "Precision", "F1 / F2", "Brier"],
          [["Dummy (prior)", "0,2893 (= tỷ lệ dương)", "0,00%", "—", "—", "—"],
           ["Logistic Regression (τ* = 0,43)", "0,9989", "99,55% (663/666)", "94,18%", "—", "0,0143"],
           ["Random Forest (τ* = 0,32)", "0,9985", "100,00%", "96,10%", "0,9801 / 0,9920", "0,0134"]],
          "docs/classification_findings.md §2; reports/classification_results.md",
          "VN001", V_BASE, "notebooks/07_classification_alerts.ipynb; src/classification.py"))
    A("""<p>Dummy đạt Accuracy 71,07% nhưng Recall 0% – minh chứng cho “bẫy Accuracy”. Ma trận nhầm lẫn của Random Forest [[TN, FP], [FN, TP]] = [[1609, 27], [0, 666]]. Hiệu chuẩn xác suất được đánh giá trên 2.302 mẫu (Brier ở bảng trên).</p>
<div class="box bad"><b>Giải thích đúng hiệu năng ở h = 0.</b> Hiệu năng gần 1,0 chủ yếu phản ánh <b>23/24 giờ (95,8%)</b> chồng lấn giữa đặc trưng <code>pm25_rolling_mean_24h</code> và nhãn, cộng với việc ERA5 có độ trễ ~5 ngày: đây là <i>nowcast hồi cứu</i>, <b>không phải</b> hệ thống cảnh báo thời gian thực.</div>""")
    A(tbl("Suy giảm PR-AUC theo tầm dự báo h (Logistic Regression, đặc trưng đầy đủ, có purge gap) và các kịch bản ablation – baseline",
          ["Kịch bản", "n Test", "Dương", "PR-AUC", "Recall"],
          [["h = 0 – đầy đủ", "2.302", "666", "0,9989", "0,9955"],
           ["h = 0 – bỏ trung bình trượt 24h (Lag24 + khí tượng)", "2.302", "666", "0,7908", "0,8529"],
           ["h = 0 – chỉ khí tượng + thời gian (không PM2,5)", "2.323", "669", "0,4338", "1,0"],
           ["h = 1", "2.281", "663", "0,9966", "0,9804"],
           ["h = 6", "2.186", "647", "0,9696", "0,8887"],
           ["h = 12", "2.084", "619", "0,9094", "0,7205"],
           ["h = 24", "1.893", "543", "0,7513", "0,6041"]],
          "reports/classification_results.md (bảng horizon/ablation)", "VN001", V_BASE,
          "notebooks/07_classification_alerts.ipynb"))
    A(tbl("Ba phạm vi phân loại (Protocol A) – kể cả phạm vi KHÔNG ƯỚC LƯỢNG ĐƯỢC",
          ["Phạm vi", "Trạm / phiên bản", "Test hợp lệ (tỷ lệ dương)", "Dummy PR-AUC", "LogReg PR-AUC / Recall", "RF PR-AUC / Recall", "Hiệu chuẩn"],
          [["VN001_baseline_2026_01_15", f"VN001 / {V_BASE}", "2.302 (28,93%)", "0,2893", "0,9989 / 99,55%", "0,9985 / 100,00%", "OK"],
           ["VN001_extended_80_20", f"VN001 / {V_EXT}", "242 (0,00%)", "UNESTIMABLE", "UNESTIMABLE", "UNESTIMABLE", "UNESTIMABLE"],
           ["VN003_extended_2022_2025", f"VN003 / {V_EXT}", "3.439 (49,81%)", "0,4981", "0,9995 / 99,77%", "0,9983 / 99,30%", "OK"]],
          "docs/classification_findings.md §4; reports/classification_results.md",
          "VN001 / VN003", f"{V_BASE} / {V_EXT}", "notebooks/07_classification_alerts.ipynb", cls="wide"))
    A("""<div class="box bad"><b>VN001_extended_80_20 = UNESTIMABLE.</b> Tập Test (242 giờ hợp lệ, từ 01/05/2026) rơi vào mùa hè sạch kèm đợt mất dữ liệu 630 giờ nên có <b>0/242 ca dương</b>; PR-AUC, ROC-AUC, Recall và hiệu chuẩn không xác định và <b>không</b> được thay bằng số khác. Không có kết luận hiệu năng nào được rút ra từ phạm vi này.</div>""")
    A("""<p><b>Kiểm toán rò rỉ bốn lớp</b> (Target, nhiễm chéo Train–Test, Temporal, Group) có bằng chứng unit test, <code>validate_no_leakage()</code>, purge gap ở h &gt; 0 và biên bản loại SMOTE; loại bắt buộc <code>pm10</code> (r = 0,9727 với <code>pm25</code>), <code>pm25_was_missing</code> và <code>is_high_humidity_fog</code>. Ở h = 0, độ quan trọng hoán vị của các biến khí tượng đơn lẻ gần 0 vì bị biến tự hồi quy che khuất; vì vậy không khẳng định chúng “gây ra” cảnh báo.</p>""")
    A(fig("PR", "Đường Precision–Recall trên tập Test (baseline).", out,
          "figures/precision_recall_curve.png", B_ST, V_BASE, "notebooks/07_classification_alerts.ipynb", "70%"))
    A(fig("FI", "Độ quan trọng đặc trưng (hoán vị theo average_precision, baseline).", out,
          "figures/feature_importance.png", B_ST, V_BASE, "notebooks/07_classification_alerts.ipynb", "75%"))
    A(fig("CAL", "Đường hiệu chuẩn xác suất (reliability, baseline).", out,
          "figures/calibration_reliability.png", B_ST, V_BASE, "notebooks/07_classification_alerts.ipynb", "70%"))

    # --- 4.5 sensitivity
    A('<h3 class="pb">4.5. Phân tích độ nhạy (Issue #15)</h3>')
    A("""<p>Chỉ mức 50 µg/m³ (trung bình trượt 24 giờ) tham chiếu QCVN 05:2023/BTNMT; các mức 40, 45, 55 µg/m³ là <b>ngưỡng độ nhạy kỹ thuật</b> (<code>technical_sensitivity_threshold</code>), không phải quy chuẩn pháp lý. Kiểm chứng SHA-256 trước/sau cho thấy artifact baseline bất biến (PASS).</p>""")
    A(tbl("Độ nhạy ngưỡng cảnh báo – VN001 baseline (Logistic Regression, Test cố định 2.302 giờ)",
          ["Ngưỡng (µg/m³)", "Nhãn", "Tỷ lệ dương Test", "PR-AUC", "Recall", "Precision", "F2", "FAR"],
          [["40", "độ nhạy kỹ thuật", "0,4557", "0,9991", "0,9971", "0,9298", "0,9829", "0,063"],
           ["45", "độ nhạy kỹ thuật", "0,3684", "0,998", "0,9894", "0,9699", "0,9854", "0,0179"],
           ["<b>50</b>", "<b>QCVN 24 giờ</b>", "0,2893", "0,9989", "0,9955", "0,9418", "0,9843", "0,0251"],
           ["55", "độ nhạy kỹ thuật", "0,2328", "0,9981", "1,0", "0,7283", "0,9306", "0,1133"]],
          "reports/sensitivity_analysis.md §3; reports/sensitivity_analysis.csv", "VN001", V_BASE,
          "scripts/run_sensitivity_analysis.py"))
    A(tbl("Độ nhạy min_periods của cửa sổ trượt (ngưỡng 50 µg/m³)",
          ["Phạm vi", "min_periods", "Test hợp lệ", "Tỷ lệ dương Test", "PR-AUC", "Recall"],
          [["VN001 baseline", "12 / 18 / 24", "3.236 / 3.016 / 2.302", "0,2376 / 0,243 / 0,2893", "0,9986 / 0,9988 / 0,9989", "1,0 / 1,0 / 0,9955"],
           ["VN003 mở rộng 80/20", "12 / 18 / 24", "4.423 / 4.368 / 3.439", "0,4956 / 0,4991 / 0,4981", "0,9994 / 0,9994 / 0,9995", "0,9977 (cả ba)"],
           ["VN001 mở rộng 80/20", "12 / 18 / 24", "724 / 561 / 242", "0,0276 / 0,0125 / 0,0", "0,9433 / 0,8163 / UNESTIMABLE", "0,95 / 1,0 / UNESTIMABLE"]],
          "reports/sensitivity_analysis.md §4", "VN001 / VN003", f"{V_BASE} / {V_EXT}",
          "scripts/run_sensitivity_analysis.py"))
    A("""<p>Với <code>VN001</code> mở rộng, PR-AUC ở <code>min_periods</code> = 12/18 dựa trên rất ít ca dương (tỷ lệ dương 2,76% và 1,25%) nên chỉ mang tính tham khảo. Độ nhạy cửa sổ huấn luyện (50/75/100% đuôi Train) ở baseline cho PR-AUC 0,9948/0,9981/0,9989, nhưng hồi quy tuyến tính không lag không ổn định: Test R² là −0,6223, −1,8433, −1,954 tương ứng, hệ số <code>wind_speed</code> từ −11,8421 xuống −6,0673 – một cảnh báo về phụ thuộc cỡ mẫu và mùa. Nội suy phái sinh (chỉ trên Train; Test bất biến) thay đổi MAE Test không quá 0,018 ở <code>VN001</code> và 0,0103 ở <code>VN003</code>, PR-AUC <code>VN003</code> không đổi (0,9995).</p>""")

    # --- 4.6 resource & bias
    A('<h3>4.6. Quy mô dữ liệu, tài nguyên và định kiến (Issue #14)</h3>')
    A(tbl("Đo đạc thực nghiệm tài nguyên trước/sau tối ưu (Pandas + Parquet) – không dùng Spark",
          ["Tập", "Dung lượng đĩa", "RAM", "Đọc (median)", "Workload phân tích"],
          [["Baseline VN001 (9.044 × 18)", "1,8483 MB CSV → 0,2131 MB (−88,5%)", "1,6820 → 0,5263 MB (−68,71%)", "5,252 → 2,622 ms", "235,649 → 30,400 ms (7,75×)"],
           ["Mở rộng (37.722 × 23)", "8,7952 MB CSV → 0,7103 MB (−91,9%)", "9,3147 → 2,7704 MB (−70,26%)", "28,419 → 7,532 ms", "971,582 → 66,694 ms (14,57×)"]],
          "reports/data_scale_benchmark.md; reports/data_scale_benchmark.json", "VN001 / VN001+VN003",
          f"{V_BASE} / {V_EXT}", "scripts/run_issue14_audit.py"))
    A("""<p>Tổng dung lượng thực tế là 1,0453 MB Parquet (10,6435 MB CSV), thấp hơn ngưỡng khuyến nghị &gt; 100 GB của Spark hơn bốn bậc độ lớn; Spark bị bác bỏ dựa trên số đo, tối ưu hóa gồm ép kiểu, nén cột Parquet và vector hóa. <code>polars</code> không được cài đặt nên ghi là <i>chưa đo</i>.</p>""")
    A("""<p><b>Kiểm toán bốn định kiến:</b> (1) <b>cảm biến</b> – tương tác cờ độ ẩm cao với mùa và khác biệt hai trạm không chồng lấn; (2) <b>không gian</b> – chỉ hai điểm đo ở Hà Nội, không đại diện toàn đô thị; (3) <b>sống sót/khuyết thiếu liên quan thời tiết</b> – khuyết thiếu không MCAR (cụm tới 630 và 2.568 giờ); (4) <b>NaN so với 0,0</b> – bảo toàn <code>NaN</code>, loại sentinel. Chi tiết trong tài liệu đánh giá định kiến và model card của dự án.</p>""")

    # --- 4.7 negatives
    A('<h3>4.7. Kết quả âm tính và khuyến nghị giới hạn theo bằng chứng</h3>')
    A(tbl("Các kết quả âm tính được giữ lại",
          ["Hướng thử", "Kết quả", "Bằng chứng"],
          [["Nguồn mirror US Embassy (<code>VN002</code>)", "NO-GO", "reports/issue44_legacy_vs_extended_comparison.md"],
           ["Biến giao thông theo giờ", "NO-GO (không có chuỗi công khai theo giờ cho Hà Nội)", "docs/issue44_checkpoint_status.md (CP4)"],
           ["Nội suy khoảng trống ngắn", "Bác bỏ làm giải pháp chính: nội suy tuyến tính dùng điểm đầu mút tương lai (t+1) nên rò rỉ; chỉ phục hồi 1,85% (VN003) – 9,55% (VN001) giờ thiếu; RMSE mùa đông lên tới 13,08 µg/m³ (VN003, L = 1 giờ)", "reports/issue44_interpolation_evaluation.csv"]],
          "reports/issue44_interpolation_evaluation.csv; reports/issue44_legacy_vs_extended_comparison.md",
          "VN001 / VN003", V_EXT, "src/issue44_preparation.py; scripts/build_extended_historical_dataset.py"))
    A("""<p><b>Khuyến nghị (bị chặn bởi bằng chứng):</b> (i) giữ dữ liệu thiếu là <code>NaN</code>, không nội suy; (ii) báo cáo suy luận luôn kèm n<sub>eff</sub> và phân biệt xác nhận/thăm dò; (iii) dùng mô hình phân loại chỉ như công cụ nowcast hồi cứu, và muốn triển khai cảnh báo thực cần nguồn khí tượng dự báo NWP với thời điểm phát hành hợp lệ cùng dữ liệu PM2,5 liên tục; (iv) không suy nguồn phát thải hay hành vi giao thông từ các hệ số hồi quy.</p>""")

    # --- limits
    A('<h2 class="pb">5. Hạn chế, đạo đức và kết luận</h2>')
    A("""<ul>
<li><b>Chỉ hai trạm, không chồng lấn:</b> không thiết lập được xu hướng đa năm tại một điểm; không đánh giá độc lập độ chính xác thiết bị (<code>UNVERIFIED</code>).</li>
<li><b>Một chu kỳ mùa baseline:</b> mọi kết luận về mùa là thăm dò; mẫu mùa đông có độ phủ thấp.</li>
<li><b>OLS vi phạm cả bốn giả định LINE:</b> hệ số chỉ mô tả liên hệ quan sát, không nhân quả; R² ngoài mẫu âm ở baseline.</li>
<li><b>Phân loại:</b> hiệu năng h = 0 bị chi phối bởi chồng lấn 23/24 giờ; dữ liệu khí tượng ERA5 trễ ~5 ngày; <code>VN001</code> mở rộng 80/20 không ước lượng được.</li>
<li><b>Tuân thủ QCVN:</b> tiêu chí 18/24 giờ là quy tắc nghiên cứu, không phải định nghĩa pháp lý; báo cáo không đưa ra kết luận tuân thủ pháp lý.</li></ul>""")
    A("""<p><b>Kết luận.</b> Với cách xử lý phụ thuộc thời gian, trên baseline chỉ hai trong bốn kiểm định vượt Holm (so sánh với 50 và 25 µg/m³), kiểm định mùa là thăm dò, và kiểm định ngày làm việc/cuối tuần không đủ độ phân giải. Mô hình hồi quy chỉ có giá trị mô tả; mô hình cảnh báo hữu ích như nowcast hồi cứu nhưng hiệu năng suy giảm rõ khi h tăng (PR-AUC 0,9966 ở h = 1 xuống 0,7513 ở h = 24 trên baseline).</p>
<p><b>Tuyên bố sử dụng AI.</b> Báo cáo được soạn bằng công cụ trợ lý AI trên cơ sở các tệp kết quả đã lưu; mọi số liệu được kiểm tra tự động với tệp nguồn và mọi quyết định thống kê do nhóm chịu trách nhiệm. Truy vết đầy đủ: <code>docs/final_report_traceability.md</code>.</p>""")
    return "\n".join(h)


def write_traceability(path: Path, pdf_rel: str) -> None:
    lines = [
        "# Final Report Traceability (Issue #16)",
        "",
        f"Maps every table, figure and headline claim of [`reports/final_report.pdf`]({pdf_rel}) "
        "to its source artifact, station, dataset version and reproducing script/notebook. "
        "Generated by `scripts/build_final_report.py`; each cited number is checked against its "
        "source artifact at build time (`scripts/_report_common.py::CHECKS`).",
        "",
        "Protocol A: `VN001` (baseline) and `VN003` (extended) are never pooled. "
        "`FIG-01`–`FIG-07` are baseline `VN001` / `1.0.0-m2-baseline` only.",
        "",
        "| Item | Description | Source artifact(s) | Station | Dataset version | Reproduced by |",
        "|---|---|---|---|---|---|",
    ]
    for label, item, source, station, version, repro in TRACE:
        lines.append(f"| {label} | {item} | {md_links(source)} | {station} | {version} | {repro} |")
    lines += ["", "## Headline quantitative claims", "",
              "| Claim | Value | Source | Station | Version |", "|---|---|---|---|---|"]
    for claim, val, src, st, ver in HEADLINES:
        lines.append(f"| {claim} | {val} | {md_links(src)} | {st} | {ver} |")
    lines += ["", "## Reproduction", "",
              "```text", "py -3.14 scripts/build_final_report.py", "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def md_links(src: str) -> str:
    """Turn 'a/b.md; c.png (note)' into relative Markdown links from docs/."""
    out = []
    for part in [p.strip() for p in src.split(";")]:
        token = part.split(" ")[0]
        rest = part[len(token):]
        if "/" in token and "." in token.split("/")[-1] and token.split("/")[0] in {"reports", "docs", "figures"}:
            target = token if token.startswith("docs/") is False else token[len("docs/"):]
            if token.startswith("docs/"):
                out.append(f"[`{token}`]({target}){rest}")
            else:
                out.append(f"[`{token}`](../{token}){rest}")
        else:
            out.append(part)
    return "; ".join(out)


HEADLINES = [
    ("Daily rho1 / n_eff", "0.728 / 47.1 (VN001); 0.749 / 108.7 (VN003)", "reports/extended_reanalysis_comparison.md", "VN001 / VN003", V_EXT),
    ("W9 season H, Holm p, epsilon²", "61.534; 0.0560; 0.206 (exploratory)", "reports/inference_results.md", "VN001", V_BASE),
    ("W9 QCVN 24h t, Holm p", "-2.656; 0.0250 (confirmatory)", "reports/inference_results.md", "VN001", V_BASE),
    ("W9 QCVN annual t, Holm p, d", "4.354; 7.38e-5; 0.848 (confirmatory)", "reports/inference_results.md", "VN001", V_BASE),
    ("Weekday t (HAC), p, MDE", "1.611; 0.1082; MDE 7.75 ug/m3", "reports/inference_results.md", "VN001", V_BASE),
    ("Season Wald HAC empirical size", "30-55% vs 5% nominal", "reports/inference_results.md; reports/inference_montecarlo.csv", "synthetic AR(1) simulation", "n/a"),
    ("Extended Holm p (QCVN 24h / annual)", "0.0003162 / 2.171e-12 (VN003)", "reports/extended_reanalysis_comparison.md", "VN003", V_EXT),
    ("Days > 50 ug/m3 / eligible", "84/299 (VN001); 238/756 (VN003)", "reports/extended_inference_results.md", "VN001 / VN003", V_EXT),
    ("OLS wind_speed beta range", "-6.0673 to -7.2891 (associational)", "docs/regression_findings.md; reports/sensitivity_analysis.md", "VN001 / VN003", f"{V_BASE} / {V_EXT}"),
    ("OLS test R² (no lag)", "-1.954 (VN001 baseline); -0.1073 (VN001 ext); 0.1498 (VN003)", "reports/sensitivity_analysis.md", "VN001 / VN003", f"{V_BASE} / {V_EXT}"),
    ("LINE violations", "all 4 violated on 3 scopes", "docs/regression_findings.md", "VN001 / VN003", f"{V_BASE} / {V_EXT}"),
    ("VIF max (baseline)", "surface_pressure 8.061", "docs/regression_findings.md", "VN001", V_BASE),
    ("Classification RF PR-AUC / Recall / F2", "0.9985 / 100.00% / 0.9920 (Test 2,302h, 666 pos)", "docs/classification_findings.md", "VN001", V_BASE),
    ("Dummy PR-AUC / Accuracy", "0.2893 / 71.07%", "docs/classification_findings.md", "VN001", V_BASE),
    ("PR-AUC h=1 / 6 / 12 / 24 (LogReg)", "0.9966 / 0.9696 / 0.9094 / 0.7513", "reports/classification_results.md", "VN001", V_BASE),
    ("VN001_extended_80_20", "UNESTIMABLE (0/242 positives)", "reports/classification_results.md; docs/classification_findings.md", "VN001", V_EXT),
    ("Label/feature overlap; ERA5 latency", "23/24 h (95.8%); ~5 days (retrospective nowcast)", "docs/classification_findings.md", "VN001", V_BASE),
    ("Threshold sensitivity", "40/45/50/55; only 50 is QCVN reference", "reports/sensitivity_analysis.md", "VN001", V_BASE),
    ("Parquet / CSV total size; Spark rejection", "1.0453 MB / 10.6435 MB vs >100 GB threshold", "reports/data_scale_benchmark.md", "VN001 + VN003", f"{V_BASE} / {V_EXT}"),
    ("Station separation", "7.324 km; 0 h overlap; 2,040 h gap", "docs/issue44_dataset_contract.md", "VN001 / VN003", V_EXT),
    ("Longest gaps", "630 h (VN001); 2,568 h (VN003)", "docs/bias_assessment.md", "VN001 / VN003", f"{V_BASE} / {V_EXT}"),
    ("Interpolation recovery of real gaps", "1.85% (VN003) to 9.55% (VN001)", "reports/issue44_interpolation_evaluation.csv", "VN001 / VN003", V_EXT),
    ("VN002 mirror; traffic covariates", "NO-GO; NO-GO", "reports/issue44_legacy_vs_extended_comparison.md; docs/issue44_checkpoint_status.md", "VN002 / n/a", V_EXT),
]


def main() -> None:
    args = parse_args("Build the Issue #16 final report (HTML + PDF) and its traceability table.")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    verify_sources(args.input_root.resolve())
    body = build_html(out)
    html_doc = ('<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">'
                "<title>Báo cáo cuối kỳ INFO3020 – PM2,5 Hà Nội (Nhóm 6)</title>"
                f"<style>{CSS}</style></head><body>{body}</body></html>")
    html_path = out / "final_report.html"
    html_path.write_text(html_doc, encoding="utf-8", newline="\n")
    print(f"[html] {html_path} ({html_path.stat().st_size} bytes)")
    trace_path = REPO_ROOT / "docs" / "final_report_traceability.md"
    write_traceability(trace_path, "../reports/final_report.pdf")
    print(f"[trace] {trace_path} ({len(TRACE)} items, {len(HEADLINES)} headline claims)")
    if not args.no_pdf:
        pdf_path = out / "final_report.pdf"
        render_pdf(html_path, pdf_path)
        report_pdf(pdf_path)


if __name__ == "__main__":
    main()
