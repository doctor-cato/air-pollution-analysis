"""Build reports/defense_slides.html (14 slides, 16:9) and render
reports/defense_slides.pdf via headless Chrome for the 10-12 minute Viva.

Usage:
    py -3.14 scripts/build_defense_slides.py
    py -3.14 scripts/build_defense_slides.py --input-root <main-workspace>

HTML mode: Left/Right arrows (also PageUp/PageDown, Space) navigate; print
mode (Chrome PDF) shows one slide per 13.333in x 7.5in page.
All numbers are checked against their source artifacts at build time.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _report_common import (V_BASE, V_EXT, fig_src, parse_args, render_pdf,  # noqa: E402
                            report_pdf, table, verify_sources)

CSS = """
@page { size: 13.333in 7.5in; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #0f172a; }
body { font-family: 'Segoe UI', Arial, sans-serif; color: #111827; }
.slide { width: 13.333in; height: 7.5in; background: #fff; position: relative; overflow: hidden;
         padding: 0.45in 0.6in 0.55in; break-after: page; page-break-after: always; }
.slide:last-child { break-after: auto; page-break-after: auto; }
.slide h2 { margin: 0 0 0.18in; font-size: 28pt; line-height: 1.15; color: #0b3d5c; border-bottom: 3px solid #0b3d5c; padding-bottom: 0.08in; }
.slide .n { position: absolute; right: 0.5in; bottom: 0.22in; font-size: 11pt; color: #6b7280; }
.slide .foot { position: absolute; left: 0.6in; bottom: 0.22in; font-size: 10pt; color: #6b7280; }
.cols { display: flex; gap: 0.35in; height: 5.6in; align-items: flex-start; }
.cols > div { flex: 1; min-width: 0; }
.cols .w2 { flex: 1.4; }
ul { margin: 0; padding-left: 0.28in; font-size: 16.5pt; line-height: 1.32; }
li { margin-bottom: 0.09in; }
.sm ul, ul.sm { font-size: 14.5pt; }
b { color: #0b3d5c; }
code { font-family: Consolas, monospace; font-size: 0.82em; background: #eef2f7; padding: 0 3px; }
table { border-collapse: collapse; width: 100%; font-size: 12.5pt; }
th, td { border: 1px solid #94a3b8; padding: 4px 7px; text-align: left; vertical-align: top; }
th { background: #e2ecf4; }
figure { margin: 0; text-align: center; }
figure img { max-width: 100%; max-height: 4.9in; border: 1px solid #cbd5e1; }
figcaption { font-size: 10.5pt; color: #4b5563; margin-top: 4px; }
.tag { display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 3px; padding: 1px 8px; font-size: 10.5pt; }
.warn { border-left: 6px solid #b91c1c; background: #fef2f2; padding: 8px 14px; margin-top: 10px; font-size: 14.5pt; }
.ok { border-left: 6px solid #047857; background: #ecfdf5; padding: 8px 14px; margin-top: 10px; font-size: 14.5pt; }
.big { font-size: 40pt; font-weight: 700; color: #0b3d5c; line-height: 1.1; }
.title { background: #0b3d5c; color: #fff; }
.title h1 { font-size: 36pt; margin: 1.1in 0 0.2in; line-height: 1.2; }
.title p { font-size: 18pt; margin: 0.08in 0; }
.title .tag { background: #164e63; color: #e0f2fe; font-size: 13pt; }
@media screen {
  body { overflow: hidden; }
  .slide { position: absolute; left: 50%; top: 50%; display: none; transform-origin: center; }
  .slide.active { display: block; }
}
@media print { html, body { background: #fff; } .slide { display: block !important; } }
"""

JS = """
(function () {
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var i = 0;
  function fit() {
    var s = Math.min(window.innerWidth / (13.333 * 96), window.innerHeight / (7.5 * 96));
    slides.forEach(function (el) { el.style.transform = 'translate(-50%,-50%) scale(' + s + ')'; });
  }
  function show(k) {
    i = Math.max(0, Math.min(slides.length - 1, k));
    slides.forEach(function (el, j) { el.classList.toggle('active', j === i); });
    location.hash = '#' + (i + 1);
  }
  document.addEventListener('keydown', function (e) {
    if (['ArrowRight', 'PageDown', ' '].indexOf(e.key) >= 0) { show(i + 1); e.preventDefault(); }
    if (['ArrowLeft', 'PageUp'].indexOf(e.key) >= 0) { show(i - 1); e.preventDefault(); }
    if (e.key === 'Home') show(0);
    if (e.key === 'End') show(slides.length - 1);
  });
  window.addEventListener('resize', fit);
  fit();
  show((parseInt(location.hash.slice(1), 10) || 1) - 1);
})();
"""


def build(out: Path) -> str:
    slides: list[str] = []
    n = {"i": 0}

    def slide(title: str, body: str, foot: str = "") -> None:
        n["i"] += 1
        slides.append(f'<section class="slide"><h2>{title}</h2>{body}'
                      f'<div class="foot">{foot}</div><div class="n">{n["i"]} / 14</div></section>')

    def img(key: str, cap: str) -> str:
        return f'<figure><img src="{fig_src(key, out)}" alt="{cap}"><figcaption>{cap}</figcaption></figure>'

    # 1 Title
    n["i"] += 1
    slides.append(f"""<section class="slide title"><h1>PM<sub>2,5</sub> Hà Nội: suy luận có xét phụ thuộc thời gian và mô hình cảnh báo sớm</h1>
<p>INFO3020 – Nhập môn Khoa học Dữ liệu · Đại học CMC · <b style="color:#fff">Nhóm 6</b></p>
<p>Giảng viên: ThS. Phạm Ngọc Đông</p>
<p style="margin-top:0.5in"><span class="tag">VN001 · {V_BASE}</span> &nbsp; <span class="tag">VN003 · {V_EXT}</span> &nbsp; <span class="tag">Protocol A – không gộp trạm</span></p>
<p style="font-size:14pt;margin-top:0.4in">Bảo vệ cuối kỳ · 10–12 phút · điều hướng: ← / →</p>
<div class="n" style="color:#bae6fd">1 / 14</div></section>""")

    # 2 SCQA
    slide("Cấu trúc SCQA", """<div class="cols sm"><div><ul>
<li><b>S – Bối cảnh:</b> PM<sub>2,5</sub> đô thị Hà Nội; chuẩn QCVN 05:2023: 50 µg/m³ (24 giờ), 25 µg/m³ (năm). Baseline <code>VN001</code> 9.044 giờ; mở rộng <code>VN003</code> 28.678 giờ.</li>
<li><b>C – Phức tạp:</b> lệch phải; ρ₁ ≈ 0,73 ⇒ n<sub>eff</sub> ≈ 47,1 / 108,7; khuyết thiếu cụm (630 / 2.568 giờ); OLS vi phạm 4 giả định LINE; chồng lấn 23/24 giờ; ERA5 trễ ~5 ngày.</li></ul></div>
<div><ul>
<li><b>Q – Câu hỏi:</b> đặc trưng thống kê và liên hệ khí tượng nào xác lập được một cách trung thực, và hỗ trợ cảnh báo sớm vượt 50 µg/m³ đến đâu? (SQ1–SQ4)</li>
<li><b>A – Trả lời:</b> 2/4 kiểm định xác nhận (baseline); mùa chỉ thăm dò; OLS chỉ mô tả; phân loại tốt ở h = 0 nhưng là nowcast hồi cứu, giảm theo h.</li></ul></div></div>""",
          "Nguồn: docs/project_charter.md; reports/final_report.pdf §1–4")

    # 3 governance
    slide("Quản trị dữ liệu: Protocol A, tách trạm", "<div class=\"cols\"><div class=\"w2\">" + table(
        ["", "VN001 – baseline", "VN003 – mở rộng"],
        [["Phiên bản", f"<code>{V_BASE}</code>", f"<code>{V_EXT}</code>"],
         ["Thời gian", "07/2025–07/2026", "01/2022–04/2025"],
         ["Lưới giờ", "9.044", "28.678"],
         ["PM2,5 hợp lệ", "7.495 (82,87%)", "18.208 (63,49%)"],
         ["Ngày ≥ 18/24 giờ", "299", "756"],
         ["SHA-256", "<code>866f39de…</code>", "<code>6930557f…</code>"]]) +
        "</div><div class=\"sm\"><ul><li>SHA-256 theo dõi; baseline bất biến trước/sau Issue #15 (PASS).</li>"
        "<li><b>FIG-01…07 chỉ thuộc baseline VN001</b>; hình mở rộng ghi rõ trạm + phiên bản.</li>"
        "<li><b>VN002</b> (mirror US Embassy): <b>NO-GO</b>.</li><li>Biến giao thông: NO-GO.</li></ul></div></div>",
          "reports/extended_reanalysis_comparison.md · docs/issue44_dataset_contract.md")

    # 4 station effect
    slide("Hiệu ứng trạm và nhiễu thời gian", "<div class=\"cols\"><div class=\"sm\"><ul>"
          "<li><b>0 giờ</b> chồng lấn giữa VN003 (đến 04/2025) và VN001 (từ 07/2025).</li>"
          "<li>Khoảng <b>2.040 giờ</b> không báo cáo; hai trạm cách <b>7,324 km</b>.</li>"
          "<li>⇒ Chênh lệch hai trạm = <b>trạm + thời gian</b> lẫn nhau; không suy ra xu hướng 2022–2026 tại một điểm.</li>"
          "<li>Protocol B (mô hình gộp, <code>station_id</code> cố định) bị bác bỏ: rò rỉ thời gian chéo trạm.</li></ul>"
          "<div class=\"warn\">So sánh hai trạm chỉ ở mức “cùng chiều / chồng lấn CI”, không phải “cùng hiệu ứng”.</div></div>"
          "<div>" + img("FIG-01-EXT", f"Chuỗi PM2,5 mở rộng – VN003 và VN001 tách riêng · {V_EXT}") + "</div></div>",
          "docs/issue44_dataset_contract.md · figures/FIG-01-extended-historical.png")

    # 5 descriptive
    slide("Mô tả: phân phối lệch phải, đuôi dày", "<div class=\"cols\"><div class=\"sm\"><ul>"
          "<li>VN001: trung vị <b>37,32</b>, trung bình 43,76 µg/m³; SD 27,89, IQR 30,73.</li>"
          "<li>Độ lệch 1,295; P95 = 101,87; P99 = 133,79; max 198,95.</li>"
          "<li>⇒ Dùng <b>trung vị/IQR</b> làm thước đo điển hình.</li>"
          "<li>VN003: trung vị 38,00, trung bình 45,83; SD 30,65.</li>"
          "<li>Ngày > 50 µg/m³: 84/299 (VN001), 238/756 (VN003).</li></ul></div>"
          "<div>" + img("FIG-02", f"FIG-02 · baseline VN001 · {V_BASE}") + "</div></div>",
          "reports/statistical_profile.csv · reports/extended_inference_results.md")

    # 6 interpolation
    slide("Vì sao bác bỏ nội suy khoảng trống ngắn", "<div class=\"cols\"><div class=\"sm\"><ul>"
          "<li><b>Rò rỉ điểm đầu mút tương lai (t+1):</b> nội suy tuyến tính dùng giá trị sau khoảng trống.</li>"
          "<li><b>Phục hồi rất ít:</b> chỉ <b>1,85%</b> (VN003) – <b>9,55%</b> (VN001) giờ thiếu thật.</li>"
          "<li><b>Sai số mùa đông lớn:</b> RMSE lên tới <b>13,08 µg/m³</b> (VN003, khoảng 1 giờ).</li>"
          "<li>Quyết định: giữ <code>NaN</code>; nội suy chỉ là độ nhạy trên Train.</li></ul></div>"
          "<div>" + table(["Trạm", "Giờ thiếu", "Giờ phục hồi", "% thiếu"],
                          [["VN001", "1.549", "148", "9,55%"], ["VN003", "10.470", "194", "1,85%"]]) +
          "<div class=\"ok\">Nội suy phái sinh (Train): ΔMAE Test ≤ 0,018; PR-AUC VN003 không đổi 0,9995.</div></div></div>",
          "reports/issue44_interpolation_evaluation.csv (max_gap = 2 giờ) · reports/sensitivity_analysis.md §8")

    # 7 dependence-aware
    slide("Suy luận có xét phụ thuộc: n_eff và bootstrap lịch", "<div class=\"cols\"><div class=\"sm\"><ul>"
          "<li>ACF giờ bậc 1 = 0,9403; ρ₁ ngày = 0,728 / 0,749 ⇒ <b>n<sub>eff</sub> = 47,1 / 108,7</b> (299 / 756 ngày).</li>"
          "<li>Bootstrap khối <b>theo lịch ngày</b> (28 ngày), mặt nạ thiếu đi theo bản sao, nhãn ở vị trí đích; null dựng <b>dưới H₀</b>.</li>"
          "<li>Holm cố định 4 kiểm định; CI 95% block-bootstrap (B = 1.000), null B = 5.000, seed 42.</li>"
          "<li><b>Monte Carlo:</b> Wald HAC cho mùa có size thực 30–55% (nominal 5%) ⇒ mùa luôn <b>thăm dò</b> (R5).</li></ul></div>"
          "<div><div class=\"big\">47,1</div><p style=\"font-size:15pt;margin:0 0 14px\">ngày độc lập tương đương (VN001) so với 299 ngày danh nghĩa</p>"
          "<div class=\"big\">108,7</div><p style=\"font-size:15pt\">VN003 trên 756 ngày</p>"
          "<div class=\"warn\">p giả định độc lập (vd 2,76·10⁻¹³ cho mùa) là phản bảo thủ – không dùng để kết luận.</div></div></div>",
          "reports/inference_results.md · reports/inference_montecarlo.csv")

    # 8 W9 results
    slide("Kết quả W9: xác nhận so với thăm dò", table(
        ["Kiểm định (VN001 baseline)", "Thống kê", "p Holm", "Effect size", "Mức"],
        [["Mùa (4 nhóm)", "H = 61,534", "0,0560", "ε² = 0,206", "<b>THĂM DÒ</b>"],
         ["Ngày làm việc vs cuối tuần", "t = 1,611", "0,1082", "|r<sub>rb</sub>| = 0,117; CI [−11,13; 3,05]", "Không bác bỏ (MDE 7,75)"],
         ["TB ngày vs 50 µg/m³", "t = −2,656", "0,0250", "r = −0,410; share 0,2809 [0,119; 0,443]", "<b>XÁC NHẬN</b>"],
         ["TB giai đoạn vs 25 µg/m³", "t = 4,354", "7,38·10⁻⁵", "d = 0,848; 43,38 [35,1; 51,7]", "<b>XÁC NHẬN</b>"]]) +
          "<div class=\"sm\"><ul style=\"margin-top:14px\"><li><b>Mở rộng VN003</b> (thăm dò theo trạm): QCVN 24 giờ Holm 0,0003162; năm 2,171·10⁻¹²; ngày làm việc −0,256 [−3,86; 3,34] (hướng khác VN001).</li>"
          "<li>“Cùng chiều” ≠ “cùng hiệu ứng”; so với 25 µg/m³ không phải kết luận tuân thủ pháp lý.</li></ul></div>",
          f"reports/inference_results.md · reports/extended_reanalysis_comparison.md · VN001 {V_BASE}")

    # 9 OLS LINE
    slide("OLS: cả 4 giả định LINE đều bị vi phạm", "<div class=\"cols\"><div class=\"w2\">" + table(
        ["LINE", "Kiểm định", "VN001 baseline", "VN003 mở rộng"],
        [["L", "Ramsey RESET", "F = 223,27", "F = 243,15"],
         ["I", "Durbin–Watson", "0,2430", "0,3033"],
         ["N", "Jarque–Bera", "392,7", "51.355,1"],
         ["E", "Breusch–Pagan LM", "658,27", "701,19"]]) +
        "<div class=\"sm\"><ul style=\"margin-top:14px\"><li>VIF max 8,061 (surface_pressure) &lt; 10; HAC-24 đổi p của <code>precipitation</code> 0,0060 → 0,0808.</li></ul></div></div>"
        "<div class=\"sm\"><ul><li>Gió <b>liên hệ với</b> PM2,5 thấp hơn <b>6,07–7,29</b> µg/m³ mỗi 1 m/s, giữ nguyên biến khác (β = −6,0673; −7,2891; −6,2864).</li></ul>"
        "<div class=\"warn\"><b>Chỉ là liên hệ quan sát</b> trong miền Train – <b>không</b> kết luận nhân quả.</div></div></div>",
          "docs/regression_findings.md §3–4 · notebooks/06_regression_modeling.ipynb")

    # 10 chronological generalisation
    slide("OLS khái quát hóa theo thời gian", "<div class=\"cols\"><div>" + table(
        ["Phạm vi", "Test R² (không lag)", "RMSE"],
        [["VN001 baseline", "<b>−1,954</b>", "41,4604"],
         ["VN001 mở rộng 80/20", "−0,1073", "21,1167"],
         ["VN003 mở rộng 80/20", "<b>+0,1498</b>", "32,8238"]]) +
        "<div class=\"sm\"><ul style=\"margin-top:14px\"><li>R² âm ở baseline: ngoại suy mùa (Train thu–đông, Test đông–hạ).</li>"
        "<li>Cắt Train 50/75/100%: β gió −11,84 → −6,07; R² −0,62 → −1,95.</li>"
        "<li>OLS khí tượng <b>không</b> đủ để dự báo vận hành.</li></ul></div></div>"
        "<div>" + img("REG-DIAG", f"Chẩn đoán LINE · baseline VN001 · {V_BASE}") + "</div></div>",
          "reports/sensitivity_analysis.md §5–6 · figures/regression_line_diagnostics.png")

    # 11 classification
    slide("Phân loại cảnh báo: kết quả trên Test độc lập", "<div class=\"cols\"><div>" + table(
        ["Mô hình (VN001, 666 dương)", "PR-AUC", "Recall", "Prec."],
        [["Dummy (prior)", "0,2893", "0%", "—"],
         ["LogReg (τ 0,43)", "0,9989", "99,55%", "94,18%"],
         ["RF (τ 0,32)", "0,9985", "100%", "96,10%"]]) +
        "<div class=\"sm\"><ul style=\"margin-top:12px\"><li>RF: F1 0,9801, F2 0,9920, Brier 0,0134; CM [[1609, 27], [0, 666]].</li>"
        "<li>Accuracy Dummy 71,07% nhưng Recall 0% – bẫy Accuracy.</li></ul></div>"
        "<div class=\"warn\"><b>VN001_extended_80_20: UNESTIMABLE</b> – Test 0/242 ca dương (sau đợt mất dữ liệu 630 giờ).</div></div>"
        "<div>" + img("PR", f"Precision–Recall · baseline VN001 · {V_BASE}") + "</div></div>",
          "docs/classification_findings.md · reports/classification_results.md")

    # 12 overlap / horizon / leakage
    slide("Chồng lấn 23/24 giờ, suy giảm theo h và rò rỉ", "<div class=\"cols\"><div class=\"sm\"><ul>"
          "<li>h = 0: trung bình trượt 24 giờ quá khứ chia sẻ <b>23/24 giờ</b> (95,8%) với nhãn ⇒ PR-AUC gần 1,0 phản ánh kế thừa cửa sổ.</li>"
          "<li>Bỏ trung bình trượt: 0,7908; chỉ khí tượng: 0,4338.</li>"
          "<li><b>Kiểm toán rò rỉ 4 lớp:</b> Target, Train–Test, Temporal, Group; purge gap; không SMOTE.</li></ul>"
          "<div class=\"warn\">ERA5 trễ ~5 ngày ⇒ <b>nowcast hồi cứu</b>, không phải cảnh báo thời gian thực.</div></div>"
          "<div>" + table(["Tầm h", "PR-AUC", "Recall"],
                          [["0", "0,9989", "0,9955"], ["1", "0,9966", "0,9804"], ["6", "0,9696", "0,8887"],
                           ["12", "0,9094", "0,7205"], ["24", "0,7513", "0,6041"]]) +
          "<p style=\"font-size:11pt;color:#4b5563\">LogReg, đặc trưng đầy đủ, VN001 baseline</p></div></div>",
          "reports/classification_results.md · docs/leakage_audit.md")

    # 13 sensitivity + benchmark
    slide("Độ nhạy và đo đạc Pandas so với Spark", "<div class=\"cols\"><div>" + table(
        ["Ngưỡng", "Nhãn", "PR-AUC", "Recall", "FAR"],
        [["40", "độ nhạy kỹ thuật", "0,9991", "0,9971", "0,063"], ["45", "độ nhạy kỹ thuật", "0,998", "0,9894", "0,0179"],
         ["<b>50</b>", "<b>QCVN 24 giờ</b>", "0,9989", "0,9955", "0,0251"], ["55", "độ nhạy kỹ thuật", "0,9981", "1,0", "0,1133"]]) +
        "<div class=\"sm\"><ul style=\"margin-top:12px\"><li><code>min_periods</code> 12/18/24: PR-AUC 0,9986/0,9988/0,9989 (VN001).</li>"
        "<li>Lag/rolling: roll_mean_24h R² 0,3541 (là tín hiệu tự hồi quy).</li></ul></div></div>"
        "<div class=\"sm\"><ul><li><b>Đo thực nghiệm:</b> Parquet <b>1,0453 MB</b>, CSV 10,6435 MB, so với ngưỡng Spark &gt; <b>100 GB</b>.</li>"
        "<li>3 tối ưu: ép kiểu (RAM −70,26%), Parquet/Zstd (−91,9%), vector hóa (14,57×; 66,694 ms).</li>"
        "<li>Spark bị bác bỏ dựa trên số đo; Polars: chưa đo.</li></ul></div></div>",
          "reports/sensitivity_analysis.md · reports/data_scale_benchmark.md")

    # 14 conclusion
    slide("Giới hạn và kết luận", "<div class=\"cols sm\"><div><ul>"
          "<li><b>Giới hạn:</b> 2 trạm không chồng lấn; một chu kỳ mùa; OLS vi phạm LINE; Test mở rộng VN001 không ước lượng được.</li>"
          "<li><b>Âm tính giữ lại:</b> VN002 NO-GO; biến giao thông NO-GO; nội suy ngắn bị bác.</li>"
          "<li><b>Đạo đức:</b> 4 định kiến được kiểm toán; không nhân quả; không kết luận tuân thủ pháp lý.</li></ul></div>"
          "<div><ul><li><b>Kết luận:</b> trên baseline, 2/4 kiểm định vượt Holm; mùa thăm dò.</li>"
          "<li>Cảnh báo hữu ích như <b>nowcast hồi cứu</b> (PR-AUC 0,9989 ở h = 0) nhưng giảm còn 0,7513 ở h = 24.</li>"
          "<li>Triển khai thực cần khí tượng dự báo NWP hợp lệ + PM2,5 liên tục.</li></ul>"
          "<div class=\"ok\">Truy vết đầy đủ: <code>docs/final_report_traceability.md</code></div></div></div>",
          "reports/final_report.pdf · docs/model_card.md · docs/bias_assessment.md")

    assert len(slides) == 14, len(slides)
    return "\n".join(slides)


def main() -> None:
    args = parse_args("Build the Issue #16 defense slides (HTML + PDF).")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    verify_sources(args.input_root.resolve())
    body = build(out)
    doc = ('<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">'
           "<title>Bảo vệ INFO3020 – PM2,5 Hà Nội (Nhóm 6)</title>"
           f"<style>{CSS}</style></head><body>{body}<script>{JS}</script></body></html>")
    html_path = out / "defense_slides.html"
    html_path.write_text(doc, encoding="utf-8", newline="\n")
    print(f"[html] {html_path} ({html_path.stat().st_size} bytes)")
    if not args.no_pdf:
        pdf_path = out / "defense_slides.pdf"
        render_pdf(html_path, pdf_path)
        report_pdf(pdf_path)


if __name__ == "__main__":
    main()
