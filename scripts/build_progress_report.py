"""Sinh báo cáo tiến độ M1 -> M2 ra định dạng DOCX.

Nguồn sự thật: docs/roadmap.md, docs/data_dictionary.md, docs/source_profiling_decision.md,
docs/data_quality_audit.md, docs/cleaning_log.md và data/raw/metadata.json.
Script chỉ đọc tài liệu, không sửa dữ liệu.

Chạy: python scripts/build_progress_report.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "bao_cao_tien_do_M1_M2.docx"

ACCENT = RGBColor(0x1F, 0x3B, 0x57)
MUTED = RGBColor(0x55, 0x5F, 0x6B)
BASELINE_FONT = "Calibri"
UNICODE_FONT = "Cambria"


# --------------------------------------------------------------------------- #
# Tien ich trinh bay
# --------------------------------------------------------------------------- #
def set_document_defaults(doc: Document) -> None:
    """Dat font mac dinh, co chong va margin A4 cho toan bo tai lieu."""
    section = doc.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.0)

    style = doc.styles["Normal"]
    style.font.name = BASELINE_FONT
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), UNICODE_FONT)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.15

    for name, size in (("Title", 22), ("Heading 1", 15), ("Heading 2", 13), ("Heading 3", 11.5)):
        heading = doc.styles[name]
        heading.font.name = BASELINE_FONT
        heading.font.size = Pt(size)
        heading.font.color.rgb = ACCENT
        heading.font.bold = True


def add_footer_page_numbers(doc: Document) -> None:
    """Them so trang vao chan trang cua tung section."""
    for section in doc.sections:
        paragraph = section.footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run("Báo cáo tiến độ M1 → M2  |  INFO3020  |  Trang ")
        run.font.size = Pt(8)
        run.font.color.rgb = MUTED
        _add_field(paragraph, "PAGE")


def _add_field(paragraph, instruction: str) -> None:
    """Chen field Word (PAGE/NUMPAGES) vao mot paragraph."""
    run = paragraph.add_run()
    begin = run._r.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "begin"})
    instr = run._r.makeelement(qn("w:instrText"), {qn("xml:space"): "preserve"})
    instr.text = instruction
    end = run._r.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "end"})
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)


def add_paragraph(doc: Document, text: str, *, style: str | None = None, italic: bool = False):
    paragraph = doc.add_paragraph(style=style)
    run = paragraph.add_run(text)
    run.italic = italic
    return paragraph


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def add_numbers(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Number")


def add_table(doc: Document, header: list[str], rows: list[list[str]], widths: list[float] | None = None):
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for cell, text in zip(table.rows[0].cells, header):
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(9.5)

    for row_values in rows:
        cells = table.add_row().cells
        for cell, text in zip(cells, row_values):
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(text))
            run.font.size = Pt(9.5)

    if widths:
        for row in table.rows:
            for cell, width in zip(row.cells, widths):
                cell.width = Cm(width)

    doc.add_paragraph()
    return table


def add_callout(doc: Document, title: str, body: str) -> None:
    """Khoi highlight 1 luận điểm quan trong."""
    table = doc.add_table(rows=1, cols=1)
    table.style = "Light List Accent 1"
    cell = table.rows[0].cells[0]
    cell.text = ""

    title_run = cell.paragraphs[0].add_run(f"{title}: ")
    title_run.bold = True
    title_run.font.size = Pt(10.5)
    body_run = cell.paragraphs[0].add_run(body)
    body_run.font.size = Pt(10.5)

    doc.add_paragraph()


# --------------------------------------------------------------------------- #
# Noi dung bao cao
# --------------------------------------------------------------------------- #
def build_cover(doc: Document) -> None:
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("BÁO CÁO TIẾN ĐỘ ĐỒ ÁN 1")

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run(
        "Phân tích mức độ ô nhiễm không khí theo thời gian tại Hà Nội\n"
        "Milestone 1 → Milestone 2 (Tuần 01 – Tuần 05)"
    )
    run.font.size = Pt(13)
    run.font.color.rgb = MUTED

    doc.add_paragraph()
    add_table(
        doc,
        ["Hạng mục", "Nội dung"],
        [
            ["Môn học", "INFO3020 – Nhập môn Khoa học Dữ liệu (Introduction to Data Science)"],
            ["Đề tài", "Time-Series Air Pollution Analysis – PM2.5 và khí tượng bề mặt Hà Nội"],
            ["Cơ sở dữ liệu thực nghiệm", "OpenAQ S3 (loc 4946811) + Open-Meteo ERA5"],
            ["Giai đoạn", "Milestone 2 hoàn tất – chuẩn bị Milestone 3 (EDA & Báo cáo giữa kỳ)"],
            ["Issues đã đóng", "#1, #2, #3, #4, #5, #6, #7, #19"],
            ["Kiểm thử tự động", "297 unit test — PASS; CI workflow; fetch script không cần API key"],
            ["Tài liệu chuẩn", "docs/roadmap.md, data_dictionary.md, source_profiling_decision.md, "
                              "data_quality_audit.md, cleaning_log.md"],
        ],
        widths=[4.2, 11.4],
    )


def build_summary(doc: Document) -> None:
    doc.add_heading("Tóm tắt điều hành", level=1)
    add_paragraph(
        doc,
        "Báo cáo này tổng hợp toàn bộ kết quả hai milestone đầu tiên của đồ án: xác lập "
        "nền tảng dữ liệu (M1) và chuẩn hóa dữ liệu chống rò rỉ (M2). Mục tiêu của giai đoạn "
        "này không phải là tìm ra kết luận, mà là bảo đảm mọi kết luận sau này dựa trên một "
        "nền dữ liệu còn nguyên vẹn, có nguồn gốc kiểm chứng được và không bị rò rỉ thống kê.",
    )
    add_bullets(
        doc,
        [
            "M1: khảo sát 6 nguồn dữ liệu ứng viên, ban hành quyết định nguồn, thu thập và chuẩn hóa "
            "8.022 giờ dữ liệu ô nhiễm cùng 9.072 giờ khí tượng về Canonical Schema trung lập nguồn.",
            "M1 đạt được phát hiện quan trọng nhất: một trạm OpenAQ từng bị gán nhầm nhãn “Hanoi” "
            "thực chất nằm tại Albuquerque, Hoa Kỳ — toàn bộ số liệu tương ứng bị thu hồi.",
            "M2: kiểm toán chất lượng 6 chiều trên 8.022 giờ dữ liệu thô, phát hiện 324 bản ghi "
            "vi phạm ràng buộc khí động học và 1.022 giờ trống trên lưới thời gian liên tục.",
            "M2: làm sạch tất định biến 8.022 × 5 thành 9.044 × 8, không xóa dòng và không điền khuyết.",
            "M2: chốt điểm cắt Train/Test theo chuỗi thời gian và phát hiện một dạng rò rỉ target "
            "theo cấu trúc mà các guard tham số thông thường không thể bắt.",
        ],
    )
    add_callout(
        doc,
        "Giá trị lớn nhất của giai đoạn này",
        "hai quyết định phương pháp luận — điểm cắt 2026-01-15 và loại bỏ cờ "
        "pm25_was_missing khỏi tập đặc trưng — được chốt dựa trên số liệu quan sát thực nghiệm "
        "thay vì tỷ lệ quy ước, và cả hai đều được công khai kèm hạn chế số liệu.",
    )


def build_m1_section(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("Milestone 1 — Thiết lập dự án, Canonical Schema & Quyết định nguồn", level=1)
    add_paragraph(
        doc,
        "M1 trải qua 4 Issue: #1 (khởi tạo repository), #2 (câu hỏi nghiên cứu và Data "
        "Dictionary), #19 (khảo sát đa nguồn và quyết định nguồn), #3 và #4 (adapter thu thập "
        "ô nhiễm và khí tượng).",
    )

    doc.add_heading("1.1. Cấu trúc repository và chính sách dữ liệu thô ba tầng", level=2)
    add_paragraph(
        doc,
        "Repository theo đúng vòng đời CRISP-DM: data/raw → data/interim → data/processed, "
        "kèm src/, tests/, notebooks/ và docs/. Chính sách dữ liệu thô được tách thành ba tầng "
        "kiểm chứng độc lập để tránh tuyên bố không kiểm chứng được:",
    )
    add_table(
        doc,
        ["Tầng", "Nội dung", "Cơ chế kiểm chứng"],
        [
            ["A — Thu thập & lưu trữ", "Payload thô tải từ nguồn được ghi dưới data/raw/ khi pipeline chạy",
             "Kiểm tra payload tồn tại sau mỗi lần thu thập"],
            ["B — Bảo toàn & truy vết", "Tệp thô giữ nguyên trạng, không chỉnh sửa trước khi ghi",
             "Mã băm SHA-256 ghi trong data/raw/metadata.json"],
            ["C — Chính sách phiên bản", "Tệp thô tải từ API không bắt buộc Git-track",
             ".gitignore loại data/raw/*.json và *.parquet; tái tạo bằng scripts/fetch_dataset.py"],
        ],
        widths=[3.6, 6.4, 5.6],
    )

    doc.add_heading("1.2. Câu hỏi nghiên cứu và Canonical Schema", level=2)
    add_paragraph(
        doc,
        "Câu hỏi nghiên cứu chính: nồng độ bụi mịn tại khu vực nghiên cứu biến động theo những "
        "quy luật chu kỳ thời gian nào, chịu sự liên hệ ra sao bởi các yếu tố khí tượng bề mặt, "
        "và làm thế nào để xây dựng mô hình cảnh báo sớm mà không vi phạm rò rỉ dữ liệu.",
    )
    add_table(
        doc,
        ["Mã", "Câu hỏi nghiên cứu"],
        [
            ["RQ1", "PM2.5 biến thiên thế nào theo giờ trong ngày, ngày trong tuần, tháng và mùa?"],
            ["RQ2", "Có khác biệt có ý nghĩa giữa ngày làm việc và cuối tuần, giữa các mùa không? "
                    "Kích thước hiệu ứng và 95% Bootstrap CI là bao nhiêu?"],
            ["RQ3", "Yếu tố khí tượng bề mặt liên hệ ra sao với PM2.5 trong điều kiện ceteris paribus?"],
            ["RQ4", "Có thể dùng đặc trưng trễ để phân loại các đợt vượt ngưỡng cảnh báo không?"],
        ],
        widths=[1.8, 13.8],
    )
    add_paragraph(
        doc,
        "Canonical Schema được thiết lập độc lập với định dạng raw của từng nhà cung cấp, gồm "
        "trục thời gian Asia/Ho_Chi_Minh (UTC+7), định danh trạm, hai kênh bụi và sáu biến khí tượng. "
        "Mọi quy tắc chuyển đổi từ trường nguồn sang trường chuẩn đều được ghi tường minh trong "
        "docs/data_dictionary.md.",
    )

    doc.add_heading("1.3. Cổng quyết định nguồn dữ liệu (Issue #19)", level=2)
    add_paragraph(
        doc,
        "Sáu nguồn ứng viên được khảo sát trên bốn tiêu chí: độ bao phủ địa lý Hà Nội, độ bao phủ "
        "thời gian thực tế, khả năng tái lập tự động và giấy phép bản quyền. Kết quả profiling được "
        "đo trực tiếp từ phản hồi API và tệp thô, không ước lượng.",
    )
    add_table(
        doc,
        ["Nguồn ứng viên", "Vai trò", "Bằng chứng thực nghiệm"],
        [
            ["OpenAQ S3 — loc 4946811 (556 Nguyễn Văn Cừ, Long Biên)",
             "Primary — ô nhiễm hiện hành",
             "352 tệp CSV.gz; 2025-07-03 → 2026-07-15; ~220 quan sát/ngày/param; ODC-BY v1.0; "
             "không cần API key qua S3"],
            ["AirNow DOS Historical CSV (BAM-1020, ĐSQ Hoa Kỳ)",
             "Primary lịch sử 2023 / Fallback",
             "Chuỗi PM2.5 theo giờ đến 31/12/2023; thiết bị US EPA FEM; marker −999 cần bóc trần"],
            ["Open-Meteo Historical Weather (ERA5)",
             "Primary — khí tượng",
             "17.544 giờ liên tục 2023–2024; 0% missing trên 6 biến; cách trạm 1,71 km; CC BY 4.0"],
            ["NOAA ISD — WMO 48820 Nội Bài",
             "Fallback — khí tượng",
             "17.178 bản ghi 2023 (~30 phút/lần); thiếu precipitation và surface_pressure; lệch ~22 km"],
            ["Kaggle Hanoi datasets", "Reference only",
             "Đã tiền xử lý sẵn, 0% missing là hệ quả điền khuyết nhân tạo; nguy cơ rò rỉ từ feature trễ"],
            ["PAM Air Portal", "Unused",
             "Không có REST API cộng đồng; bản quyền đóng; cảm biến quang học không kèm trạm hiệu chuẩn"],
        ],
        widths=[4.6, 3.6, 7.4],
    )

    add_callout(
        doc,
        "Đính chính học thuật — trạm OpenAQ 2178 bị loại bỏ",
        "Trong bản thảo ban đầu, location_id = 2178 được gán nhãn “US Diplomatic Post: Hanoi”. "
        "Kiểm chứng payload thô trên S3 cho thấy bản ghi chứa tọa độ 35.1353N, −106.5847W — tức "
        "trạm Del Norte High School, Albuquerque, New Mexico. Toàn bộ 14.424 dòng đo và các chỉ số "
        "phân tích kèm theo bị chính thức thu hồi. Trạm Hà Nội hợp thức là location_id = 4946811.",
    )

    doc.add_heading("1.4. Kết quả thu thập và chuẩn hóa (Issue #3, #4)", level=2)
    add_table(
        doc,
        ["Chỉ số", "Chất lượng không khí", "Khí tượng bề mặt"],
        [
            ["Nguồn", "OpenAQ S3 loc 4946811", "Open-Meteo ERA5 Reanalysis"],
            ["Tọa độ", "21.0491°N, 105.8831°E", "Lưới 21.05448°N, 105.89848°E (cao 19,0 m)"],
            ["Dải thời gian thực tế", "2025-07-03 22:00 → 2026-07-15 17:00 (+07:00)",
             "2025-07-03 00:00 → 2026-07-15 23:00 (+07:00)"],
            ["Số mốc giờ canonical", "8.022", "9.072"],
            ["Bản ghi thô trước chuẩn hóa", "349.463 (lọc 0 bản ghi)", "9.072 payload giờ"],
            ["Tỷ lệ khuyết thiếu", "PM2.5 2,53% (203 giờ); PM10 1,53% (123 giờ)", "0% trên cả 6 biến"],
            ["Kiểm định vật lý", "Không có giá trị âm", "Tất cả 6 biến trong dải khí hậu Hà Nội"],
            ["Tích hợp thời gian", "Inner join theo timestamp: 8.022 dòng — độ phủ 100,0%, không row explosion", ""],
        ],
        widths=[4.2, 6.4, 5.0],
    )
    add_paragraph(
        doc,
        "Cửa sổ truy vấn khí tượng được suy diễn động từ trục thời gian canonical của dữ liệu ô "
        "nhiễm thay vì hard-code, nên adapter không chứa bất kỳ khung ngày cố định nào; hành vi này "
        "được bảo vệ bằng unit test.",
    )


def build_m2_section(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("Milestone 2 — Kiểm toán chất lượng, Làm sạch tất định & Pipeline chống rò rỉ", level=1)

    doc.add_heading("2.1. Kiểm toán chất lượng dữ liệu 6 chiều (Issue #5)", level=2)
    add_paragraph(
        doc,
        "Kiểm toán chạy ở chế độ chỉ đọc trên 8.022 bản ghi ô nhiễm và 9.072 bản ghi khí tượng. "
        "Mọi con số dưới đây mô tả trạng thái TRƯỚC làm sạch.",
    )
    add_table(
        doc,
        ["Chiều chất lượng", "Bằng chứng định lượng", "Kết quả quan sát"],
        [
            ["1. Completeness",
             "Khí tượng 0/9.072 ô khuyết; PM2.5 thiếu 203/8.022 (2,53%); PM10 thiếu 123 (1,53%); "
             "thiếu 1.022 giờ trên lưới liên tục 9.044 giờ (11,30%)",
             "Khí tượng đạt 100%; ô nhiễm khả dụng 97,47% PM2.5; tồn tại khoảng trống do trạm ngừng phát"],
            ["2. Accuracy",
             "Nhiệt độ 8,9–38,6°C; RH 30–100%; gió 0,0–9,55 m/s; PM2.5 1,06–252,64 µg/m³; "
             "324 cặp PM2.5 > PM10 (4,21%), trong đó 282 cặp vượt sai số đo ε = 2,0 µg/m³; "
             "2.843 giờ RH > 90% (31,34%)",
             "0 vi phạm giới hạn đơn lẻ; sai lệch chủ yếu do sai số giữa hai cảm biến quang học"],
            ["3. Consistency",
             "Đơn vị nhất quán theo Data Dictionary; 100% bản ghi mang múi giờ Asia/Ho_Chi_Minh; "
             "timestamp đơn điệu tăng trên cả hai tập",
             "Không trượt pha thời gian; inner join 8.022 dòng với độ phủ 100%"],
            ["4. Validity",
             "timestamp: datetime64[ns, Asia/Ho_Chi_Minh]; biến đo: float64; định danh: object; "
             "không có inf hoặc mã lỗi ngụy trang",
             "100% cột hợp lệ theo Canonical Schema"],
            ["5. Uniqueness",
             "0 bản ghi trùng khóa (station_id, timestamp); 0 bản ghi trùng timestamp ở tập khí tượng",
             "Tính duy nhất đạt 100%"],
            ["6. Timeliness",
             "Khoảng cách lấy mẫu trung vị 1,0 giờ; khí tượng 9.071/9.071 khoảng cách đúng 1 giờ; "
             "ô nhiễm 98,84% khoảng cách đúng 1 giờ, đợt mất lớn nhất 626 giờ (≈ 26 ngày)",
             "Tần suất lấy mẫu ổn định; đợt 626 giờ cần rà soát ở bước reindex"],
        ],
        widths=[3.2, 6.6, 5.8],
    )

    doc.add_heading("2.2. Hình thái khuyết thiếu và chẩn đoán cơ chế (MCAR / MAR / MNAR)", level=2)
    add_bullets(
        doc,
        [
            "Khuyết thiếu tập trung vào khung giờ 00:00–04:00 (3,80%–4,79%) và thấp nhất vào "
            "10:00–17:00 (0,60%–1,80%) — MCAR thuần túy không giải thích được toàn bộ.",
            "67 khối khuyết; 35 khối đơn lẻ 1 giờ (52,2%) tương thích với giả thuyết suy giảm truyền "
            "dẫn viễn thông tạm thời (telemetry packet drop).",
            "Không có mốc giờ nào PM2.5 và PM10 cùng khuyết — hai kênh hoạt động độc lập.",
            "Khi PM2.5 khuyết, PM10 vẫn quan sát được với trung bình 15,42 µg/m³, thấp hơn nhiều so "
            "với 65,97 µg/m³ của toàn chuỗi → ủng hộ giả thuyết MAR.",
            "Không có bằng chứng MNAR (cảm biến bão hòa khi ô nhiễm cực cao) vì PM10 không tăng đột "
            "biến trước và trong các giờ khuyết.",
        ],
    )
    add_callout(
        doc,
        "Tuyên bố bất định",
        "Dữ liệu quan sát chưa đủ cơ sở để khẳng định dứt khoát một cơ chế khuyết thiếu duy nhất. "
        "Điều kiện kiểm định logistic giữa xác suất khuyết thiếu và biến khí tượng đã được thỏa mãn, "
        "nhưng phép kiểm định đó chưa được chạy; vì vậy MCAR/MAR/MNAR ở trên là giả thuyết chẩn đoán, "
        "không phải kết luận.",
    )

    doc.add_heading("2.3. Làm sạch tất định và nhật ký làm sạch (Issue #6)", level=2)
    add_paragraph(
        doc,
        "Mọi phép biến đổi đều tất định, thực hiện TRƯỚC khi đóng băng và chia tập, và đều được ghi "
        "lại trong docs/cleaning_log.md kèm số dòng bị tác động.",
    )
    add_table(
        doc,
        ["Bước", "Phép biến đổi", "Số dòng bị ảnh hưởng"],
        [
            ["1", "Chuẩn hóa múi giờ về Asia/Ho_Chi_Minh", "0 (dữ liệu đã đúng múi giờ)"],
            ["2", "Sắp xếp tăng dần theo (station_id, timestamp), mergesort ổn định", "0 (đã đơn điệu)"],
            ["3", "Khử trùng lặp tại khóa quan sát", "0 bản ghi trùng"],
            ["4", "Bóc trần missing ngụy trang (−999, −9999, N/A, null…)", "0 ô"],
            ["5", "Lọc giá trị âm phi lý (giữ nguyên giá trị 0,0 hợp lệ)", "0 dòng"],
            ["6", "Ràng buộc khí động học PM2.5 ≤ PM10 (chuyển NaN cả hai kênh)", "324 dòng (4,21% cặp)"],
            ["7", "Reindex lưới 1 giờ liên tục theo từng trạm", "+1.022 giờ trống (giữ NaN)"],
            ["8", "Nhận diện kẹt cảm biến (> 6 giờ không đổi)", "0 dòng"],
            ["9", "Gắn cờ pm25_was_missing cho khối khuyết > 6 giờ", "1.289 hàng được gắn cờ"],
            ["10", "Gắn cờ is_high_humidity_fog khi RH > 90%", "2.834 hàng được gắn cờ"],
        ],
        widths=[1.4, 8.4, 5.8],
    )
    add_paragraph(
        doc,
        "Kết quả: 8.022 dòng × 5 cột trở thành 9.044 dòng × 8 cột. Cả năm tiêu chí nghiệm thu "
        "(múi giờ chuẩn, không trùng lặp, lưới giờ liên tục, không giá trị âm, ràng buộc khí động học) "
        "đều đạt PASS. Hàm assert_no_imputation() chứng minh từng ô: ô trước là NaN thì sau vẫn "
        "NaN, ô có giá trị thì giữ nguyên hoặc thành NaN — không có quan sát nào biến mát vô lý do.",
    )
    add_callout(
        doc,
        "Vì sao đỉnh PM2.5 biến mất",
        "Đỉnh 252,6436 µg/m³ ngày 05/06/2026 16:00 có PM10 đo được chỉ 174,7982 µg/m³ — vượt PM10 "
        "tới 77,85 µg/m³, vi phạm ràng buộc khí động học, nên cả hai kênh chuyển NaN. Đỉnh biến mất "
        "là hệ quả của bằng chứng vật lý, không phải quy tắc cắt bỏ cực trị. Đỉnh PM10 339,99 µg/m³ "
        "được giữ nguyên.",
    )

    doc.add_heading("2.4. Đóng băng, chia chuỗi thời gian và Pipeline chống rò rỉ (Issue #7)", level=2)
    add_paragraph(
        doc,
        "Tập dữ liệu sạch được đóng băng tại 9.044 hàng quan sát, dải 2025-07-03 22:00 → "
        "2026-07-15 17:00 (+07:00). Điểm cắt Train/Test được chọn trên cơ sở tính đại diện theo thời "
        "gian và độ phủ sự kiện, không theo tỷ lệ quy ước.",
    )
    add_table(
        doc,
        ["Điểm cắt ứng viên", "Train / Test (%)", "Số giờ > 100 µg/m³ ở Test", "p90 Test / p90 Train"],
        [
            ["2026-05-01 (80/20)", "79,9 / 20,1", "6", "0,66"],
            ["2026-03-24 (70/30)", "69,8 / 30,2", "23", "0,69"],
            ["2026-02-15 (60/40)", "60,0 / 40,0", "30", "0,66"],
            ["2026-01-15 — ĐÃ CHỌT", "51,8 / 48,2", "99", "0,80"],
            ["2026-01-01", "48,1 / 51,9", "181", "0,97"],
        ],
        widths=[5.0, 3.8, 4.0, 3.0],
    )
    add_paragraph(
        doc,
        "Với tỷ lệ 80/20, tập Test chỉ có 6 giờ vượt 100 µg/m³; một mô hình dự báo “không cảnh báo” "
        "cho mọi giờ vẫn đạt khoảng 99,7% độ chính xác — đúng cái bẫy độ chính xác mà đề án cấm, và "
        "làm cho Recall và PR-AUC ở các giai đoạn sau mất hết ý nghĩa. Mốc 2026-01-15 cắt giữa mùa "
        "đông nên cả Train lẫn Test đều chứa giai đoạn mùa đông, cho phép đánh giá trong cùng một "
        "chế độ khí quyển thay vì trên phép dịch phân phối.",
    )

    doc.add_heading("Ba quyết định chính thức của Issue #7", level=3)
    add_bullets(
        doc,
        [
            "Quyết định 1 — Điểm cắt Train/Test = 2026-01-15 00:00:00+07:00. Train 4.682 dòng "
            "(1.425 giờ > 50, 295 giờ > 100); Test 4.362 dòng (878 giờ > 50, 99 giờ > 100).",
            "Quyết định 2 — Không biến đổi log1p cho target. Biến đổi làm skew giảm từ 1,148 "
            "xuống −0,656 nhưng giữ target ở µg/m³ giúp ngưỡng cảnh báo còn nghĩa trực tiếp với "
            "bối cảnh chất lượng không khí.",
            "Quyết định 3 — Trong 3 cờ chẩn đoán của Issue #5/#6 chỉ 1 cờ được làm đặc trưng. "
            "pm25_was_missing bị loại vì rò rỉ target theo cấu trúc; is_high_humidity_fog bị loại "
            "vì chưa có bằng chứng về giá trị dự báo marginal; còn lại là pm25_was_stuck. "
            "Module tự ném lỗi nếu target lọt vào danh sách đặc trưng.",
            "Lưu ý về is_high_humidity_fog — không viết là 'không dự báo được'. Tương quan "
            "marginal corr(pm25, RH) = −0,0365 và mutual information = 0,0024 (thấp nhất trong "
            "các biến khí tượng) chỉ chứng minh chưa có bằng chứng ở dạng cộng dồn. Tách theo mùa thì "
            "dấu đảo chiều: Đông +2,79 µg/m³ (p = 0,024), Xuân −8,91 (CI [−10,44; −7,38]), "
            "Hè +0,28, Thu −2,72. Hồi quy pm25 ~ fog + mùa + tương tác cho F = 16,78, p = 7,4·10⁻¹¹. "
            "Tức corr ≈ 0 là hệ quả của trung bình qua các mùa nơi tác dụng ngược nhau triệt tiêu. "
            "Khai thác được cần dạng mô hình tương tác fog × mùa — thuộc phạm vi Issue #8.",
        ],
    )
    add_callout(
        doc,
        "Phát hiện quan trọng — rò rỉ target theo cấu trúc",
        "Cờ pm25_was_missing chính là pm25.isna() với ngưỡng khối > 6 giờ, trong khi SimpleImputer lại "
        "điền median cho đúng những hàng đó. Đo trên dữ liệu thật, 100% hàng có cờ đều nhận target "
        "bằng đúng median (Train 256/256, median 37,83; Test 1.033/1.033). Mô hình học được quy tắc "
        "cờ = 1 thì pm25 = median và đúng 100% — đó là rò rỉ. Hàm validate_no_leakage() không bắt "
        "được lỗi này vì imputer và scaler vẫn học đúng trên Train; phải loại ở mức danh sách đặc trưng.",
    )
    add_paragraph(
        doc,
        "Artifact đầu ra data/processed/air_pollution_final.parquet gồm 9.044 dòng × 18 cột, trong "
        "đó có thêm bốn đặc trưng tuần hoàn lượng giác (hour_sin, hour_cos, month_sin, month_cos). "
        "Phép ghép ô nhiễm – khí tượng kiểm tra đồng thời cả hai bất biến: không sinh thêm dòng "
        "(len_merged ≤ len_air, theo tiêu chí nghiệm thu) và không mất dòng ô nhiễm nào "
        "(len_merged = len_air). Giá trị 0,0 hợp lệ được bảo toàn; sentinel −999/−9999 chuyển NaN.",
    )


def build_limitations(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("Hạn chế đã biết và hướng nghiên cứu cho Milestone 3", level=1)
    add_paragraph(
        doc,
        "Các hạn chế dưới đây được công khai chủ động vì chúng ảnh hưởng trực tiếp tới cách diễn "
        "giải kết quả ở những milestone sau.",
    )
    add_table(
        doc,
        ["Hạn chế", "Số liệu", "Hệ quả bắt buộc cho M3 – M4"],
        [
            ["Đuôi dữ liệu rỗng của tập Test",
             "1.146 / 4.362 dòng Test không có nhãn (26,3%); tháng 6 mất 79,03% nhãn, "
             "tháng 7 mất 99,72%",
             "Mọi chỉ số phải nêu số dòng thực sự dùng được (n có nhãn = 3.216); không được "
             "âm thầm lọc đuôi rỗng rồi báo Test có 4.362 dòng"],
            ["Dịch chuyển tỷ lệ lớp Train ↔ Test",
             "Tỷ lệ nhãn nặng ở dòng có nhãn: Train 6,89% (295/4.279) so với Test 3,08% (99/3.216) — "
             "chênh 2,24×",
             "Recall và PR-AUC phải diễn giải cẩn thận; có thể báo thêm chỉ số trên tập con Test "
             "đã cân bằng nhãn"],
            ["Chuỗi chỉ có một chu kỳ mùa",
             "Dải quan sát 07/2025 – 07/2026 là đúng một năm, không lặp lại mùa",
             "Mọi khẳng định về biến thiên mùa chỉ là giả thuyết cần được nêu rõ là giới hạn thiết kế"],
            ["Cơ chế khuyết thiếu chưa kiểm định",
             "Chưa chạy kiểm định logistic xác suất khuyết ~ biến khí tượng",
             "Không được khẳng định MCAR/MAR/MNAR như kết luận; giữ nguyên tuyên bố bất định"],
            ["ERA5 là lưới tái phân tích ~25 km",
             "Điểm lưới cách trạm 1,71 km, không nắm hiệu ứng vi khí hậu cục bộ (street canyon)",
             "Ghi nhận minh bạch khi diễn giải hệ số hồi quy ở Issue #12"],
            ["Độ bao phủ lịch sử không đạt kỳ vọng ban đầu",
             "OpenAQ chỉ tích hợp trạm Hà Nội từ 07/2025; 0 tệp cho giai đoạn 2023–2024; "
             "AirNow chỉ mở đến 31/12/2023",
             "Công khai sự lệch giữa cửa sổ nghiên cứu thiết kế (2023–2024) và độ bao phủ thực tế (2025–2026)"],
        ],
        widths=[3.6, 6.4, 5.6],
    )

    doc.add_heading("Khuyến nghị cho Milestone 3", level=2)
    add_numbers(
        doc,
        [
            "Báo cáo chỉ số trên tập Test có nhãn (n = 3.216) làm kết quả chính, công bố riêng độ "
            "phủ theo tháng như phụ lục minh bạch.",
            "Khi trích dẫn mọi tỷ lệ, nêu rõ mẫu số và dùng cùng một mẫu số cho cả Train lẫn Test.",
            "Chỉ số hàm ý dùng Median/IQR nếu phân phối quan sát được lệch; luôn đối chiếu tương "
            "quan với biểu đồ phân tán trước khi biện luận.",
            "Mọi ngưỡng quy chuẩn phải nêu rõ chu kỳ lấy mẫu tương thích toán học; tuyệt đối không "
            "so sánh số đo theo giờ đơn lẻ với ngưỡng trung bình 24 giờ hay trung bình năm.",
            "Trước khi xây dựng nhãn cảnh báo, đọc cả ba cờ chẩn đoán để quyết định có được phép "
            "điền khuyết hay không.",
        ],
    )


def build_appendix(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading("Phụ lục — Tài nguyên và khả năng tái lập", level=1)
    add_table(
        doc,
        ["Hạng mục", "Chi tiết"],
        [
            ["Mã nguồn", "src/data_collection.py, src/data_quality.py, src/cleaning.py, "
                         "src/cleaning_pipeline.py, scripts/fetch_dataset.py"],
            ["Notebook", "notebooks/00 (khảo sát), 01 (thu thập), 02 (kiểm toán), "
                        "03 (làm sạch + pipeline biến đổi)"],
            ["Kiểm thử", "297 unit test — PASS; bao gồm test hồi quy chống tái phát lỗi làm sạch"],
            ["CI", "GitHub Actions workflow kiểm tra tự động trên mỗi pull request"],
            ["Tái lập dữ liệu", "python scripts/fetch_dataset.py — tải lại từ OpenAQ S3 (ODC-BY) và "
                                "Open-Meteo ERA5 (CC BY 4.0) không cần API key; cờ --skip-fetch để "
                                "kiểm chứng dữ liệu sẵn có trên đĩa mà không gọi mạng"],
            ["Giới hạn tái lập", "Kho S3 OpenAQ là kho sống và Parquet không tái lập được theo byte; "
                                 "đối chiếu thực hiện trên số bản ghi, dải thời gian và độ phủ giao thoa"],
            ["Tài liệu chuẩn", "docs/roadmap.md, docs/data_dictionary.md, docs/source_profiling_decision.md, "
                               "docs/data_quality_audit.md, docs/cleaning_log.md, data/raw/metadata.json"],
        ],
        widths=[3.4, 12.2],
    )

    doc.add_heading("Các quyết định phương pháp luận cần bảo vệ khi phản biện", level=2)
    add_bullets(
        doc,
        [
            "Vì sao chọn 2026-01-15 mà không chọn 2026-01-01 dù tỷ lệ 48/52 trông ít lệch chuẩn hơn — "
            "câu trả lời nằm ở tính đại diện theo mùa, và mốc đã chọn không phải điểm tối ưu tuyệt đối.",
            "Vì sao xử lý 324 bản ghi nghịch đảo thay vì 282 như bàn giao của Issue #5 — tiêu chí "
            "nghiệm thu yêu cầu ràng buộc nghiêm ngặt; ε = 2,0 µg/m³ đóng vai trò mốc phân loại bằng chứng.",
            "Vì sao không dùng quy tắc kẹt cảm biến cho lượng mưa và tốc độ gió — chuỗi 0,0 dài là "
            "hiện tượng khí tượng tự nhiên ở miền Bắc Việt Nam, đã được kiểm toán và kết luận.",
            "Vì sao validate_no_leakage() không đủ — guard tham số học vô dụng với rò rỉ theo cấu trúc.",
        ],
    )


def main() -> None:
    doc = Document()
    set_document_defaults(doc)
    build_cover(doc)
    build_summary(doc)
    build_m1_section(doc)
    build_m2_section(doc)
    build_limitations(doc)
    build_appendix(doc)
    add_footer_page_numbers(doc)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT_PATH)
    print(f"Da tao: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
