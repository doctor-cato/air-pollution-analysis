"""
Unit tests cho bộ công cụ thẩm định Issue #8 (`scripts/validate_issue8.py`).

Kiểm thử toàn diện 6 khía cạnh:
1. `verify_file_checksum`: Kiểm tra chính xác 4 trường hợp (khớp, không khớp, tệp không tồn tại, không có hash kỳ vọng).
2. `checksum_verdict`: Định tuyến TẤT CẢ trạng thái — không trạng thái nào bị bỏ qua im lặng.
3. Đồng bộ hóa Notebook & Generator: Khẳng định 37 cells (15 code, 22 markdown) khớp 100% từng ký tự.
4. Thống kê Hướng học (Circular Statistics): Kiểm chứng toán học của `circmean` và đối chiếu với sai số của `linear mean`.
5. Tính toàn vẹn của Bảng Hồ sơ Thống kê (`reports/statistical_profile.csv`): Cột circular và cảnh báo.
6. Tính nhất quán của các con số trong markdown takeaway so với output thật của code cell,
   cùng LaTeX escaping trong các cell markdown.
"""

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from scripts.validate_issue8 import (
    CHECKSUM_STATUSES,
    checksum_verdict,
    check_notebook_sync,
    verify_file_checksum,
)
import scripts.generate_04_notebook as gen_04

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestVerifyFileChecksum(unittest.TestCase):
    """Kiểm thử hàm verify_file_checksum cho mọi nhánh điều kiện."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = Path(self.temp_dir.name) / "sample_payload.bin"
        self.sample_bytes = b"Hanoi_Air_Pollution_Verification_Token_2026"
        self.test_file.write_bytes(self.sample_bytes)
        self.expected_sha = hashlib.sha256(self.sample_bytes).hexdigest()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_checksum_match_returns_true(self):
        """Trường hợp 1: Checksum khớp tuyệt đối -> status 'MATCH', match True."""
        result = verify_file_checksum(self.test_file, self.expected_sha)
        self.assertEqual(result["status"], "MATCH")
        self.assertTrue(result["match"])
        self.assertEqual(result["actual_sha"], self.expected_sha)
        self.assertIn("khớp tuyệt đối", result["message"])

    def test_checksum_mismatch_returns_false(self):
        """Trường hợp 2: Checksum sai -> status 'MISMATCH', match False."""
        wrong_sha = "0" * 64
        result = verify_file_checksum(self.test_file, wrong_sha)
        self.assertEqual(result["status"], "MISMATCH")
        self.assertFalse(result["match"])
        self.assertEqual(result["actual_sha"], self.expected_sha)
        self.assertEqual(result["expected_sha"], wrong_sha)
        self.assertIn("không khớp", result["message"])

    def test_checksum_file_not_found_returns_false(self):
        """Trường hợp 3: Tệp không tồn tại -> status 'NOT_FOUND', match False."""
        non_existent = Path(self.temp_dir.name) / "does_not_exist.bin"
        result = verify_file_checksum(non_existent, self.expected_sha)
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertFalse(result["match"])
        self.assertIsNone(result["actual_sha"])
        self.assertIn("không tồn tại", result["message"])

    def test_checksum_no_expected_hash_returns_false(self):
        """Trường hợp 4: Không có checksum kỳ vọng để đối chiếu -> status 'NO_EXPECTED_HASH'."""
        result = verify_file_checksum(self.test_file, None)
        self.assertEqual(result["status"], "NO_EXPECTED_HASH")
        self.assertFalse(result["match"])
        self.assertEqual(result["actual_sha"], self.expected_sha)
        self.assertIn("Không có checksum kỳ vọng", result["message"])

    def test_checksum_on_directory_path_reports_not_found(self):
        """
        Regression: đường dẫn trỏ tới một THƯ MỤC (không phải tệp) phải trả
        NOT_FOUND thay vì ném IsADirectoryError.

        Bối cảnh: nếu metadata.json thiếu khóa 'raw_file' thì
        `ROOT / ""` hội tụ về chính thư mục repo. `Path.exists()` trả True cho
        thư mục nên `read_bytes()` sẽ ném IsADirectoryError và làm sập toàn bộ
        validation script giữa chừng.
        """
        result = verify_file_checksum(REPO_ROOT, "0" * 64)
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertIsNone(result["actual_sha"])
        self.assertIn("không tồn tại", result["message"])


class TestChecksumVerdictRouting(unittest.TestCase):
    """
    `checksum_verdict` phải ánh xạ TẤT CẢ trạng thái của `verify_file_checksum`.

    Mục tiêu của PR review: "mọi trường hợp không có checksum kỳ vọng đều được
    ghi nhận rõ là WARN/SKIP, không tính là xác minh thành công", và "giữ nguyên
    việc phân biệt rõ MATCH, MISMATCH, NOT_FOUND và NO_EXPECTED_HASH".
    """

    def _result(self, status):
        return {
            "status": status,
            "actual_sha": "a" * 64,
            "expected_sha": "a" * 64,
            "match": status == "MATCH",
            "message": "synthetic",
        }

    def test_every_status_is_routed(self):
        """Mỗi status trong CHECKSUM_STATUSES đều cho verdict hợp lệ."""
        for status in CHECKSUM_STATUSES:
            kind, label, detail = checksum_verdict(self._result(status))
            self.assertIn(kind, ("PASS", "WARN", "FAIL"), f"status={status} -> kind={kind}")
            self.assertTrue(label, f"status={status} thiếu label")
            self.assertIn(status, label, f"status={status} không được nêu trong label")
            self.assertTrue(
                detail.startswith("synthetic"),
                f"status={status} phải giữ nguyên message gốc, nhận được: {detail!r}",
            )

    def test_only_match_is_a_pass(self):
        """Chỉ MATCH mới được coi là xác minh thành công."""
        self.assertEqual(checksum_verdict(self._result("MATCH"))[0], "PASS")
        for status in ("MISMATCH", "NOT_FOUND", "NO_EXPECTED_HASH"):
            self.assertNotEqual(
                checksum_verdict(self._result(status))[0],
                "PASS",
                f"{status} KHÔNG BAO GIỜ được báo là PASS",
            )

    def test_no_expected_hash_is_warn_and_states_the_limitation(self):
        """NO_EXPECTED_HASH -> WARN, và thông điệp phải nói rõ chưa xác minh được."""
        kind, label, detail = checksum_verdict(self._result("NO_EXPECTED_HASH"))
        self.assertEqual(kind, "WARN")
        self.assertIn("NO_EXPECTED_HASH", label)
        self.assertIn("KHÔNG được tính là một kiểm tra checksum thành công", detail)

    def test_not_found_is_warn(self):
        """NOT_FOUND -> WARN (không có gì để hash)."""
        kind, label, detail = checksum_verdict(self._result("NOT_FOUND"))
        self.assertEqual(kind, "WARN")
        self.assertIn("NOT_FOUND", label)
        self.assertIn("không thể xác minh", detail)

    def test_mismatch_defaults_to_warn_not_fail(self):
        """
        MISMATCH mặc định là WARN vì dữ liệu thô của dự án không byte-reproducible
        (docs/history/02), nhưng KHÔNG BAO GIỜ được báo là đã xác minh.
        """
        kind, label, detail = checksum_verdict(self._result("MISMATCH"))
        self.assertEqual(kind, "WARN")
        self.assertIn("MISMATCH", label)
        self.assertIn("KHÔNG được tính là đã xác minh tính toàn vẹn dữ liệu", detail)

        kind_fail, _, _ = checksum_verdict(self._result("MISMATCH"), mismatch_severity="FAIL")
        self.assertEqual(kind_fail, "FAIL")

    def test_unknown_status_raises_instead_of_falling_through(self):
        """
        Một trạng thái lạ phải ném lỗi chứ không được rơi qua im lặng.

        Đây là guard chống lại việc thêm status mới vào `verify_file_checksum`
        mà quên xử lý — dạng lỗi khiến bước kiểm tra bị báo im lặng là "đạt".
        """
        with self.assertRaises(ValueError):
            checksum_verdict({"status": "SOMETHING_NEW", "message": "x"})

    def test_checklist_matches_verify_file_checksum_docstring(self):
        """CHECKSUM_STATUSES phải liệt kê đủ 4 trạng thái mà hàm gốc trả về."""
        self.assertEqual(
            set(CHECKSUM_STATUSES),
            {"MATCH", "MISMATCH", "NOT_FOUND", "NO_EXPECTED_HASH"},
        )


class TestNotebookGeneratorSync(unittest.TestCase):
    """Kiểm thử tính đồng bộ tuyệt đối giữa generator script và notebook đã commit."""

    def test_cell_counts_match_exact_specification(self):
        """Khẳng định số lượng cell là 37 (15 code cells, 22 markdown cells)."""
        gen_dict = gen_04.build_notebook_dict()
        gen_cells = gen_dict["cells"]
        self.assertEqual(len(gen_cells), 37, f"Generator phải sinh đúng 37 cells, hiện có {len(gen_cells)}")

        code_cells = [c for c in gen_cells if c["cell_type"] == "code"]
        md_cells = [c for c in gen_cells if c["cell_type"] == "markdown"]
        self.assertEqual(len(code_cells), 15, f"Phải có đúng 15 code cells, hiện có {len(code_cells)}")
        self.assertEqual(len(md_cells), 22, f"Phải có đúng 22 markdown cells, hiện có {len(md_cells)}")

    def test_notebook_disk_is_synchronized_with_generator(self):
        """Khẳng định notebook trên đĩa khớp 100% từng cell với generator script."""
        nb_path = REPO_ROOT / "notebooks" / "04_descriptive_stats.ipynb"
        self.assertTrue(nb_path.exists(), "Notebook 04_descriptive_stats.ipynb chưa tồn tại trên đĩa")

        gen_dict = gen_04.build_notebook_dict()
        is_synced, msg = check_notebook_sync(nb_path, gen_dict["cells"])
        self.assertTrue(is_synced, f"Notebook bị lệch pha so với generator: {msg}")


class TestCircularWindDirectionMath(unittest.TestCase):
    """Kiểm chứng toán học của phương pháp thống kê góc (Circular Statistics)."""

    def test_circular_mean_avoids_linear_boundary_discontinuity(self):
        """
        Chứng minh sai lệch bản chất của trung bình số học:
        Góc 350° (Bắc - Tây Bắc) và 10° (Bắc - Đông Bắc) phải có trung bình hướng là 0° (Bắc),
        trong khi trung bình số học (linear mean) cho ra 180° (hướng Nam - ngược 180°).
        """
        angles = np.array([350.0, 10.0])
        linear_mean = angles.mean()
        self.assertAlmostEqual(linear_mean, 180.0, places=2)

        circular_mean = float(stats.circmean(angles, high=360, low=0))
        # 0° hoặc 360° là cùng một điểm trên S1
        self.assertTrue(
            abs(circular_mean - 0.0) < 1e-4 or abs(circular_mean - 360.0) < 1e-4,
            f"Circular mean phải là 0° hoặc 360°, nhận được: {circular_mean}",
        )

    def test_statistical_profile_csv_contains_circular_columns(self):
        """Kiểm tra tệp statistical_profile.csv có đủ cột circular và giá trị đúng."""
        csv_path = REPO_ROOT / "reports" / "statistical_profile.csv"
        self.assertTrue(csv_path.exists(), "Tệp statistical_profile.csv chưa tồn tại")

        df_prof = pd.read_csv(csv_path)
        self.assertIn("circular_mean", df_prof.columns)
        self.assertIn("circular_std", df_prof.columns)
        self.assertIn("notes", df_prof.columns)

        wd_row = df_prof[df_prof["variable"] == "wind_direction"].iloc[0]
        # Circular mean ~107.12°, Circular std ~82.32°
        self.assertAlmostEqual(float(wd_row["circular_mean"]), 107.12, places=1)
        self.assertAlmostEqual(float(wd_row["circular_std"]), 82.32, places=1)
        self.assertTrue(len(str(wd_row["notes"])) > 20)

        # Các biến tuyến tính khác phải có circular_mean và circular_std là NaN
        non_circ = df_prof[df_prof["variable"] != "wind_direction"]
        self.assertTrue(non_circ["circular_mean"].isna().all())
        self.assertTrue(non_circ["circular_std"].isna().all())


class TestNotebookExecutionOutputs(unittest.TestCase):
    """Kiểm tra notebook đã thực thi có đầy đủ outputs và không có lỗi."""

    def test_all_code_cells_have_outputs_and_no_errors(self):
        """Mọi code cell trong notebook phải có outputs và 0 cell bị lỗi."""
        nb_path = REPO_ROOT / "notebooks" / "04_descriptive_stats.ipynb"
        if not nb_path.exists():
            self.skipTest("Notebook chưa tồn tại")

        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)

        code_cells = [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]
        self.assertEqual(len(code_cells), 15)

        for idx, cell in enumerate(code_cells):
            outputs = cell.get("outputs", [])
            self.assertTrue(
                len(outputs) > 0,
                f"Code cell #{idx} chưa có output (chưa thực thi)",
            )
            for out in outputs:
                self.assertNotEqual(
                    out.get("output_type"),
                    "error",
                    f"Code cell #{idx} gặp lỗi: {out.get('ename')}: {out.get('evalue')}",
                )

    def test_live_restart_kernel_and_run_all(self):
        """
        Kiểm chứng khả năng tái tạo thực tế: chạy Restart Kernel & Run All trực tiếp.

        Nếu chạy trên môi trường CI không có data/processed/air_pollution_final.parquet,
        test này sẽ skip (unittest.SkipTest) với thông điệp rõ ràng:
        'Môi trường CI không có data/processed/air_pollution_final.parquet (bước chưa được xác minh trong CI)'.

        Nếu có dataset (local Windows hoặc môi trường có data), test sẽ thực sự khởi chạy
        NotebookClient và xác nhận notebook thực thi 100% không phát sinh bất kỳ cell lỗi nào.
        """
        parquet_path = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
        if not parquet_path.exists():
            self.skipTest(
                "Môi trường CI không có data/processed/air_pollution_final.parquet "
                "(bước thực thi notebook chưa được xác minh trong CI)"
            )

        nb_path = REPO_ROOT / "notebooks" / "04_descriptive_stats.ipynb"
        self.assertTrue(nb_path.exists(), "Notebook không tồn tại trên đĩa")

        import nbformat
        from nbclient import NotebookClient

        nb_obj = nbformat.read(nb_path, as_version=4)
        client = NotebookClient(nb_obj, timeout=600, kernel_name="python3")
        executed_nb = client.execute()

        error_cells = []
        code_cells = [c for c in executed_nb.cells if c.cell_type == "code"]
        for idx, cell in enumerate(code_cells):
            for out in cell.get("outputs", []):
                if out.get("output_type") == "error":
                    error_cells.append((idx, out.get("ename"), out.get("evalue")))

        self.assertEqual(len(error_cells), 0, f"Phát hiện cell lỗi khi chạy Restart Kernel: {error_cells}")


# ---------------------------------------------------------------------------
# Markdown takeaway của notebook 04 viết TAY các con số thống kê. Nếu ai đó
# chạy lại notebook trên dataset khác (hoặc chỉ đơn giản là làm tròn 2 lần),
# markdown sẽ lệch khỏi output thật của code cell mà không có gì báo lỗi.
#
# Hai lớp test dưới đây chạy được trên CI KHÔNG cần dataset: chúng chỉ đọc
# notebook JSON đã commit.
# ---------------------------------------------------------------------------

#: (tên claim, chỉ số code cell, regex trong output, chỉ số markdown cell,
#:  regex trong markdown, sai số cho phép)
NOTEBOOK_CLAIMS = [
    ("pm25.skewness", 6, r"Skewness:\s+(-?[\d.]+)", 8,
     r"Skewness\} = \+(-?[\d,]+)", 0.005),
    ("pm25.kurtosis", 6, r"Excess Kurtosis:\s+(-?[\d.]+)", 8,
     r"Excess Kurtosis\} = \+(-?[\d,]+)", 0.005),
    ("pm25.mean", 6, r"\n  Mean:\s+(-?[\d.]+)", 8,
     r"Mean\} \((-?[\d,]+)\)", 0.005),
    ("pm25.median", 6, r"Median \(P50\):\s+(-?[\d.]+)", 8,
     r"Median\} \((-?[\d,]+)", 0.005),
    ("pm25.kde_peak", 6, r"KDE Peak \(Modal area\):\s+(-?[\d.]+)", 8,
     r"KDE Peak\} \((-?[\d,]+)", 0.005),
    ("diurnal.peak_09h", 7, r"09:00 \(Median = (-?[\d.]+)", 10,
     r"09:00 sáng\*\* \(Median \$(-?[\d,]+)", 0.005),
    ("diurnal.trough_14h", 7, r"14:00 \(Median = (-?[\d.]+)", 10,
     r"\*\*14:00\*\* \(Median \$(-?[\d,]+)", 0.005),
    ("dow.weekend_minus_weekday", 8, r"Chênh lệch: \+(-?[\d.]+)", 12,
     r"chênh lệch \$\+(-?[\d,]+)", 0.005),
    ("dow.saturday_median", 8, r"Saturday\s+\d+\s+[\d.]+\s+(-?[\d.]+)", 12,
     r"Thứ Bảy là ngày có trung vị cao nhất \(\$(-?[\d,]+)", 0.005),
    ("season.winter_median", 9, r"Dong\s+\d+\s+[\d.]+\s+(-?[\d.]+)\s+[\d.]+\s+[\d.]+", 14,
     r"Mùa Đông có trung vị \$(-?[\d,]+)", 0.005),
    ("season.summer_median", 9, r"\bHe\s+\d+\s+[\d.]+\s+(-?[\d.]+)\s+[\d.]+\s+[\d.]+", 14,
     r"Mùa Hè \(\$(-?[\d,]+)", 0.005),
    ("season.winter_p90", 9, r"Dong\s+\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+(-?[\d.]+)", 14,
     r"Mùa Đông có trung vị \$[\d,]+.*?\$P_\{90\} = (-?[\d,]+)", 0.005),
    ("season.summer_p90", 9, r"\bHe\s+\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+(-?[\d.]+)", 14,
     r"Mùa Hè \(\$[\d,]+.*?\$P_\{90\} = (-?[\d,]+)", 0.005),
    ("corr.pm25_pm10", 12, r"\npm10\s+(-?[\d.]+)\s+(-?[\d.]+)", 21,
     r"_\{10\}\) = (-?[\d,]+)", 0.0005),
]


def _join_source(cell):
    """Gộp `source` dạng list-of-lines của nbformat về một chuỗi."""
    src = cell.get("source", "")
    return src if isinstance(src, str) else "".join(src)


def _cell_output_text(cell):
    """Gộp mọi output của một code cell thành chuỗi để regex bắt được."""
    parts = []
    for out in cell.get("outputs", []) or []:
        kind = out.get("output_type")
        if kind == "stream":
            parts.append("".join(out.get("text", [])))
        elif kind in ("display_data", "execute_result"):
            text = out.get("data", {}).get("text/plain", "")
            parts.append("".join(text) if isinstance(text, list) else text)
    return "\n".join(parts)


def _to_float(viet_text):
    """'2,91' -> 2.91 (notebook dùng dấu phẩy thập phân kiểu Việt Nam)."""
    return float(viet_text.replace(",", "."))


class TestNotebookClaimConsistency(unittest.TestCase):
    """
    Mọi con số viết tay trong markdown takeaway phải khớp output thật của code cell.

    Regression cụ thể: takeaway "Day-of-Week" từng ghi `+2,92` — đó là
    39,48 - 36,56, tức là làm tròn HAI LẦN. Chênh lệch thật là 2.912242, và
    chính code cell trong notebook đã in ra `+2.91`.
    """

    @classmethod
    def setUpClass(cls):
        nb_path = REPO_ROOT / "notebooks" / "04_descriptive_stats.ipynb"
        if not nb_path.exists():
            raise unittest.SkipTest("Notebook chưa tồn tại")
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        cls.code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
        cls.md_cells = [c for c in nb["cells"] if c["cell_type"] == "markdown"]

    def test_markdown_claims_match_code_outputs(self):
        failures = []
        for name, ci, code_re, mi, md_re, tol in NOTEBOOK_CLAIMS:
            self.assertLess(
                ci, len(self.code_cells), f"{name}: chỉ số code cell {ci} vượt biên"
            )
            self.assertLess(
                mi, len(self.md_cells), f"{name}: chỉ số markdown cell {mi} vượt biên"
            )

            m_code = re.search(code_re, _cell_output_text(self.code_cells[ci]))
            m_md = re.search(md_re, _join_source(self.md_cells[mi]))

            if m_code is None:
                failures.append(f"{name}: không tìm thấy giá trị trong output code cell {ci}")
                continue
            if m_md is None:
                failures.append(f"{name}: không tìm thấy giá trị trong markdown cell {mi}")
                continue

            from_code = _to_float(m_code.group(1))
            from_md = _to_float(m_md.group(1))
            if abs(from_code - from_md) > tol:
                failures.append(
                    f"{name}: markdown ghi {from_md} nhưng code cell in ra {from_code} "
                    f"(sai số cho phép {tol})"
                )

        self.assertEqual(failures, [], "\n".join(failures))

    def test_claim_table_covers_a_non_trivial_number_of_claims(self):
        """Bảng claim phải đủ rộng để thực sự bảo vệ (chống rỗng dần theo thời gian)."""
        self.assertGreaterEqual(len(NOTEBOOK_CLAIMS), 14)
        names = [c[0] for c in NOTEBOOK_CLAIMS]
        self.assertEqual(len(names), len(set(names)), "Trùng tên claim")


class TestNotebookMarkdownLaTeX(unittest.TestCase):
    """
    Markdown không được chứa `\\command` (hai dấu gạch chéo).

    `\\text` / `\\approx` / `\\rho` trong inline math bị MathJax hiểu là lệnh
    xuống dòng chứ không phải lệnh LaTeX, nên công thức hiển thị sai. Cell tiêu
    đề (md[0]) từng mắc lỗi này trong khi 21 cell còn lại đều viết đúng.
    """

    #: Lệnh LaTeX hay bị viết nhầm thành `\\cmd`.
    LATEX_COMMANDS = ("text", "approx", "rho", "sqrt", "frac", "times", "mod", "circ")

    @classmethod
    def setUpClass(cls):
        nb_path = REPO_ROOT / "notebooks" / "04_descriptive_stats.ipynb"
        if not nb_path.exists():
            raise unittest.SkipTest("Notebook chưa tồn tại")
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        cls.md_cells = [c for c in nb["cells"] if c["cell_type"] == "markdown"]

    def test_no_doubled_backslash_latex_commands(self):
        offenders = []
        for idx, cell in enumerate(self.md_cells):
            for match in re.finditer(r"\\\\[a-zA-Z]+", _join_source(cell)):
                cmd = match.group(0).lstrip("\\")
                if cmd in self.LATEX_COMMANDS:
                    offenders.append(f"markdown cell {idx}: {match.group(0)}")
        self.assertEqual(
            offenders, [],
            "Phát hiện LaTeX escape sai (dùng 1 dấu gạch chéo):\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
