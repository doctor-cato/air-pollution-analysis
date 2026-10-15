"""
Unit tests cho bộ công cụ thẩm định Issue #8 (`scripts/validate_issue8.py`).

Kiểm thử toàn diện 4 khía cạnh:
1. `verify_file_checksum`: Kiểm tra chính xác 4 trường hợp (khớp, không khớp, tệp không tồn tại, không có hash kỳ vọng).
2. Đồng bộ hóa Notebook & Generator: Khẳng định 37 cells (15 code, 22 markdown) khớp 100% từng ký tự.
3. Thống kê Hướng học (Circular Statistics): Kiểm chứng toán học của `circmean` và đối chiếu với sai số của `linear mean`.
4. Tính toàn vẹn của Bảng Hồ sơ Thống kê (`reports/statistical_profile.csv`): Cột circular và cảnh báo.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from scripts.validate_issue8 import check_notebook_sync, verify_file_checksum
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


if __name__ == "__main__":
    unittest.main()
