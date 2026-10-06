"""
Unit tests cho `write_pipeline_runtime_log()` — phục hồi phát hiện A-3
(M1 post-audit): tách trạng thái thực thi theo đồng hồ (wall-clock) ra khỏi hồ sơ
provenance tĩnh `data/raw/metadata.json`.

Bối cảnh: `data/raw/metadata.json` CÓ được git theo dõi. Trước đây
`run_collection_pipeline()` ghi `last_updated_utc` và
`collection_pipeline_execution.execution_timestamp_utc` (cả hai từ
`datetime.now(timezone.utc)`) vào chính tệp đó, nên mỗi lần chạy lại tạo ra một diff
chỉ chứa timestamp dù dữ liệu thô và provenance không hề thay đổi.

Nguyên tắc được bảo vệ ở đây: tệp runtime log phải (1) là JSON hợp lệ, (2) nằm
trong `data/raw/`, và (3) — mấu chốt — tên tệp phải KHỚP với một quy tắc thật
trong `.gitignore` của repo. Nếu không, việc tách trạng thái runtime chỉ là ẩn giấu
vấn đề: nó sẽ làm bẩn working tree y hệt trước đây.

Tất cả test chạy offline, không network, và ghi vào `tempfile.TemporaryDirectory()`
ngoài repo — không test nào chạm vào `data/`.
"""

import ast
import contextlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.data_collection import (
    METADATA_SCHEMA_VERSION,
    PIPELINE_RUNTIME_LOG_FILENAME,
    write_pipeline_runtime_log,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestWritePipelineRuntimeLog(unittest.TestCase):
    """Kiểm thử hàm ghi nhật ký runtime (wall-clock)."""

    def _summary(self, **overrides):
        summary = {
            "execution_time_seconds": 12.5,
            "query_start": "2025-07-03",
            "query_end": "2026-07-15",
            "openaq": {"raw_records": 10},
        }
        summary.update(overrides)
        return summary

    def test_writes_valid_json_file_to_given_log_path(self):
        """Tệp ghi ra phải là JSON hợp lệ và nằm đúng `log_path` yêu cầu."""
        summary = self._summary()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "custom_name.json"
            returned = write_pipeline_runtime_log(summary, log_path=target)

            self.assertEqual(returned, target, "Hàm phải trả về đúng log_path đã ghi.")
            self.assertTrue(target.exists(), "Tệp log phải được tạo trên đĩa.")

            # json.load nghiêm ngặt: tệp phải parse được, không phải chỉ "trông giống JSON".
            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIsInstance(payload, dict)

    def test_creates_parent_directory_when_missing(self):
        """Thư mục cha chưa tồn tại phải được tạo tự động (mkdir parents=True)."""
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b" / "c" / "runtime.json"
            self.assertFalse(nested.parent.exists(), "Tiền đề: thư mục cha chưa tồn tại.")

            returned = write_pipeline_runtime_log(self._summary(), log_path=nested)

            self.assertTrue(nested.parent.is_dir(), "Thư mục cha phải được tạo.")
            self.assertEqual(returned, nested)
            self.assertTrue(nested.is_file())

    def test_payload_contains_required_keys(self):
        """Payload phải có đủ 4 trường: timestamp, thời gian chạy, note, báo cáo."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / PIPELINE_RUNTIME_LOG_FILENAME
            write_pipeline_runtime_log(self._summary(), log_path=target)

            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)

            for key in (
                "execution_timestamp_utc",
                "execution_time_seconds",
                "note",
                "pipeline_report",
            ):
                self.assertIn(key, payload, f"Payload thiếu trường bắt buộc: {key}")

            self.assertTrue(
                isinstance(payload["note"], str) and payload["note"].strip(),
                "`note` phải là chuỗi không rỗng.",
            )

    def test_execution_timestamp_is_iso_utc(self):
        """`execution_timestamp_utc` phải là ISO-8601 có offset UTC (+00:00)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / PIPELINE_RUNTIME_LOG_FILENAME
            write_pipeline_runtime_log(self._summary(), log_path=target)

            with open(target, "r", encoding="utf-8") as f:
                stamp = json.load(f)["execution_timestamp_utc"]

            self.assertTrue(
                stamp.endswith("+00:00"),
                f"Timestamp phải ở UTC (hậu tố +00:00), thực tế: {stamp!r}",
            )
            # datetime.fromisoformat chấp nhận ISO-8601 — ném ValueError nếu sai định dạng.
            # Dùng `datetime` import ở cấp module (không import lại cục bộ) để tránh
            # hai tên cho cùng một thứ trong cùng module.
            datetime.fromisoformat(stamp)

    def test_execution_time_seconds_is_pulled_from_summary(self):
        """`execution_time_seconds` phải lấy từ `summary`, không tự tính lại."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / PIPELINE_RUNTIME_LOG_FILENAME
            summary = self._summary(execution_time_seconds=99.25)
            write_pipeline_runtime_log(summary, log_path=target)

            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload["execution_time_seconds"], 99.25)

    def test_pipeline_report_is_the_full_summary(self):
        """`pipeline_report` phải chứa TOÀN BỘ summary, không rút gọn."""
        summary = self._summary()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / PIPELINE_RUNTIME_LOG_FILENAME
            write_pipeline_runtime_log(summary, log_path=target)

            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload["pipeline_report"], summary)

    def test_execution_time_seconds_is_none_when_absent_from_summary(self):
        """Thiếu khoá trong summary -> None (không được ném lỗi, không được bịa số 0)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / PIPELINE_RUNTIME_LOG_FILENAME
            write_pipeline_runtime_log({"openaq": {}}, log_path=target)

            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertIsNone(
                payload["execution_time_seconds"],
                "Không có khoá trong summary thì phải là None, không phải 0 hay số bịa.",
            )

    def test_default_path_resolves_under_log_dir(self):
        """Không truyền `log_path` -> ghi vào `<log_dir>/pipeline_execution_runtime.json`."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "raw"
            returned = write_pipeline_runtime_log(self._summary(), log_dir=log_dir)

            expected = log_dir / PIPELINE_RUNTIME_LOG_FILENAME
            self.assertEqual(
                returned, expected,
                "Đường dẫn mặc định phải là <log_dir>/pipeline_execution_runtime.json.",
            )
            self.assertTrue(expected.is_file())

    def test_log_dir_creates_directory_if_missing(self):
        """`log_dir` chưa tồn tại cũng phải được tạo (chỉ truyền log_dir)."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "not_yet" / "raw"
            returned = write_pipeline_runtime_log(self._summary(), log_dir=log_dir)

            self.assertTrue(log_dir.is_dir(), "log_dir phải được tạo tự động.")
            self.assertTrue(returned.is_file())

    def test_explicit_log_path_takes_precedence_over_log_dir(self):
        """`log_path` thắng `log_dir` khi truyền cả hai."""
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp) / "explicit.json"
            returned = write_pipeline_runtime_log(
                self._summary(), log_path=explicit, log_dir=Path(tmp) / "ignored_dir"
            )
            self.assertEqual(returned, explicit)
            self.assertFalse((Path(tmp) / "ignored_dir").exists())

    # ---------------------------------------------------------------- GAP 1 ---

    def test_caller_supplied_runtime_log_path_is_honoured_verbatim(self):
        """
        GAP 1 — `run_collection_pipeline(runtime_log_path=X)` chuyển tiếp X
        nguyên vẹn (`:1497`), nên hàm ghi phải đúng vào X.

        Không gọi `run_collection_pipeline` (cần network); chỉ kiểm tra phần hợp
        đồng có thể kiểm offline: `write_pipeline_runtime_log(..., log_path=X)`
        ghi đúng X — kể cả khi X nằm NGOÀI `data/raw/` hoàn toàn.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "elsewhere" / "runtime.json"
            returned = write_pipeline_runtime_log(self._summary(), log_path=target)

            self.assertEqual(returned, target)
            self.assertTrue(target.is_file())
            with open(target, "r", encoding="utf-8") as f:
                self.assertIsInstance(json.load(f), dict)
            # Không có tệp nào khác dính vào thư mục cha (không rò sang mặc định).
            siblings = sorted(p.name for p in target.parent.iterdir())
            self.assertEqual(
                siblings, [target.name],
                "Ghi ra nhiều hơn một tệp — runtime log có thể đang rò sang mặc định.",
            )

    def test_metadata_runtime_log_pointer_is_a_hardcoded_default_literal(self):
        """
        GAP 1 — GHI NHẬN hành vi hiện tại (không phải hành vi được chấp nhận):
        con trỏ `collection_pipeline_execution.runtime_log.file` trong
        `src/data_collection.py` là literal CỨNG
        `f"data/raw/{PIPELINE_RUNTIME_LOG_FILENAME}"`.

        Hệ quả đã biết: nếu ai đó cấu hình `runtime_log_path` chỗ khác, tệp thật
        nằm ở X còn metadata vẫn trỏ `data/raw/...` — hai nơi không đồng ý. Test
        này chốt hành vi đó để nó không trôi đi âm thầm; KHÔNG sửa literal trong
        production (đã báo cáo như một phát hiện thiết kế riêng).

        Assert trên AST, không phải substring thô, để không đụng comment.
        """
        source = (REPO_ROOT / "src" / "data_collection.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        found = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Dict)):
                continue
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == "file"
                        and isinstance(value, ast.JoinedStr)):
                    literal_parts = [v.value for v in value.values
                                     if isinstance(v, ast.Constant)]
                    names = [v.value.id for v in value.values
                             if isinstance(v, ast.FormattedValue)
                             and isinstance(v.value, ast.Name)]
                    if literal_parts == ["data/raw/"] and names == [
                            "PIPELINE_RUNTIME_LOG_FILENAME"]:
                        found.append(node)

        self.assertTrue(
            found,
            "Không tìm thấy literal f\"data/raw/{PIPELINE_RUNTIME_LOG_FILENAME}\" cho "
            "con trỏ runtime_log.file — hoặc nó đã được đổi thành giá trị động, hoặc "
            "anchor đổi. Nếu đã đổi thành động, hãy CẬP NHẬT test này: con trỏ "
            "metadata và đường dẫn ghi thật phải khớp nhau.",
        )
        # Con trỏ này không được phụ thuộc `runtime_log_path`: nếu nó có, hành vi
        # "cấu hình ở chỗ khác làm metadata sai" đã không còn đúng.
        runtime_log_name_uses = sum(
            1 for n in ast.walk(found[0])
            if isinstance(n, ast.Name) and n.id == "runtime_log_path"
        )
        self.assertEqual(
            runtime_log_name_uses, 0,
            "Con trỏ runtime_log.file giờ đã phụ thuộc `runtime_log_path` — cập "
            "nhật trong docstring của test, vì phát hiện GAP 1 đã được xử lý.",
        )

    # ---------------------------------------------------------------- GAP 2 ---

    def test_default_path_is_relative_to_process_cwd(self):
        """
        GAP 2 — Hợp đồng hiện tại: khi `log_dir=None` và `log_path=None`, đường dẫn
        là `Path("data/raw") / PIPELINE_RUNTIME_LOG_FILENAME`, tức TƯƠNG ĐỐI với
        CWD của tiến trình (`src/data_collection.py:166`).

        `chdir` vào thư mục tạm rồi chạy: chứng minh (1) hợp đồng tương đối này,
        (2) khi CWD ở nơi khác thì KHÔNG gì rơi vào repo này.
        """
        # `os.chdir` phải được HOÀN TẤT TRƯỚC khi `TemporaryDirectory` dọn dẹp:
        # trên Windows, thư mục tạm đang là CWD thì `rmtree` nhận WinError 32.
        # `addCleanup` KHÔNG dùng được ở đây vì nó chạy SAU khi context manager
        # đã thoát (và thứ tự giữa nó và `rmtree` không bảo đảm được) — nên dùng
        # try/finally ngay trong thân test.
        expected_rel = Path("data/raw") / PIPELINE_RUNTIME_LOG_FILENAME
        # Bản mặc định trong repo (gitignored) có thể đã tồn tại từ lần chạy
        # notebook trước — nên "không rơi vào repo" được kiểm bằng MỐC THỜI GIAN
        # sửa đổi + byte, không bằng "tệp không tồn tại".
        repo_file = REPO_ROOT / expected_rel

        prev_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                before = (
                    repo_file.stat().st_mtime_ns if repo_file.exists() else None,
                    repo_file.read_bytes() if repo_file.exists() else None,
                )

                returned = write_pipeline_runtime_log(self._summary())

                self.assertEqual(
                    returned, expected_rel,
                    "Đường dẫn mặc định phải là ĐƯỜNG DẪN TƯƠNG ĐỐI so với CWD, không "
                    "phải đường dẫn tuyệt đối.",
                )
                self.assertFalse(returned.is_absolute(), "Đường dẫn mặc định phải là tương đối.")
                self.assertTrue(
                    (Path(tmp) / expected_rel).is_file(),
                    f"Không thấy tệp tại <tmp>/{expected_rel} — hàm không ghi theo CWD.",
                )
                # Không có gì được ghi vào repo này.
                after = (
                    repo_file.stat().st_mtime_ns if repo_file.exists() else None,
                    repo_file.read_bytes() if repo_file.exists() else None,
                )
                self.assertEqual(
                    after, before,
                    f"Tệp mặc định trong repo ({repo_file}) bị sửa dù CWD ở thư mục tạm "
                    "— hàm đang ghi theo CWD chứ không theo thư mục script.",
                )
            finally:
                os.chdir(prev_cwd)

    # ---------------------------------------------------------------- GAP 3 ---

    def test_explicit_log_path_named_metadata_json_is_unguarded(self):
        """
        GAP 3 — CHARACTERIZATION TEST, KHÔNG phải hành vi được chấp nhận.

        `write_pipeline_runtime_log` không nhận `metadata_path` và không so sánh
        với nó, nên `log_path=Path("data/raw/metadata.json")` sẽ GHI ĐÈ âm thầm lên
        hồ sơ provenance đang được git theo dõi. Test này chứng minh đúng điều đó
        để không ai hiểu nhầm là đã có chốt bảo vệ.

        Đã báo cáo như một vấn đề thiết kế riêng (đề xuất: chặn khi
        `log_path.name == "metadata.json"`). KHÔNG thêm chốt vào production code
        ở đây — việc đó thuộc thay đổi hành vi, cần quyết định riêng.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "metadata.json"  # tên collide, thư mục tạm
            target.write_text('{"sentinel": "ORIGINAL_PROVENANCE"}', encoding="utf-8")

            returned = write_pipeline_runtime_log(self._summary(), log_path=target)

            self.assertEqual(returned, target)
            self.assertTrue(
                target.is_file(),
                "Tiền đề hỏng: tệp tên metadata.json phải tồn tại trước khi ghi.",
            )
            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertNotIn(
                "sentinel", payload,
                "Hành vi ĐÃ thay đổi: log_path trùng tên metadata.json nay bị chặn "
                "— hãy cập nhật docstring test (vấn đề thiết kế GAP 3 đã được xử lý).",
            )
            self.assertIn(
                "execution_timestamp_utc", payload,
                "Hàm đã ghi đè lên tệp tên `metadata.json` mà không cảnh báo — "
                "đây là hành vi KHÔNG có chốt bảo vệ mà test này đang chốt lại.",
            )

    def test_default_path_never_resolves_to_metadata_json(self):
        """
        GAP 3 (phần an toàn) — đường dẫn MẶC ĐỊNH không bao giờ trùng
        `metadata.json`, với CWD bất kỳ: đó là carve-out duy nhất được `.gitignore`
        bảo vệ khỏi việc bị theo dõi nhầm.
        """
        # `os.chdir` phải được hoàn tất TRƯỚC `TemporaryDirectory.cleanup()`:
        # trên Windows, thư mục tạm còn là CWD thì `rmtree` nhận WinError 32.
        # `addCleanup` chạy sau context exit nên không bảo đảm được thứ tự này.
        prev_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                emitted = write_pipeline_runtime_log(self._summary())
                self.assertNotEqual(emitted.name, "metadata.json")
                self.assertEqual(emitted.name, PIPELINE_RUNTIME_LOG_FILENAME)
            finally:
                os.chdir(prev_cwd)

    # ---------------------------------------------------------------- GAP 5 ---

    def test_windows_separators_in_payload_are_preserved_verbatim(self):
        """
        GAP 5 — Chốt hành vi hiện tại: KHÔNG chuẩn hoá dấu phân cách.

        `summary["openaq"]["raw_file"]` / `["open_meteo"]["raw_file"]` được dựng
        bằng `str(Path)` nên trên Windows chứa `\\`; payload phải giữ nguyên
        (không `as_posix()`, không `resolve()` — đổi sang POSIX là thay đổi hành
        vi chưa có yêu cầu nào ở đây).

        Bất đẳng đẳng giữa hai writer (phát hiện để theo dõi, KHÔNG sửa ở test này):
        - khối metadata dùng `f"data/raw/{path.name}"` (`:1408`/`:1439`) -> luôn
          dấu `/`;
        - tệp runtime log chỉ sao chép nguyên văn `summary` -> giữ dấu `\\` của
          Windows. Cùng một tệp thô, hai nơi biểu diễn khác nhau.
        """
        windows_raw = str(Path("data") / "raw" / "openaq_2025.parquet")
        self.assertIn("\\", windows_raw, "Tiền đề: OS này phải sinh dấu `\\`.")

        summary = self._summary(
            openaq={"raw_file": windows_raw, "raw_records": 7},
            open_meteo={"raw_file": windows_raw},
        )
        with tempfile.TemporaryDirectory() as tmp:
            # log_path dạng Windows cũng phải xử lý không lỗi.
            target = Path(tmp) / "nested" / PIPELINE_RUNTIME_LOG_FILENAME
            returned = write_pipeline_runtime_log(summary, log_path=target)
            self.assertEqual(returned, target)
            self.assertTrue(target.is_file())

            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)

        report = payload["pipeline_report"]
        self.assertEqual(
            report["openaq"]["raw_file"], windows_raw,
            "Payload đã chuẩn hoá dấu phân cách trong raw_file — hành vi hiện tại "
            "là giữ nguyên văn; đổi sang POSIX cần một yêu cầu riêng.",
        )
        self.assertIn("\\", report["openaq"]["raw_file"])
        self.assertIn("\\", report["open_meteo"]["raw_file"])

    def test_metadata_block_and_runtime_log_disagree_on_separators(self):
        r"""
        GAP 5 (phần đối chiếu) — Xác nhận bất đẳng đẳng giữa hai writer: cùng một
        tên tệp thô, khối metadata luôn dùng `/` còn runtime log giữ dấu `\`.

        Chốt lại để sự lệch này không bị "sửa" một cách vô tình ở một trong hai
        bên mà không ai biết; hiện tại KHÔNG có yêu cầu nào buộc phải thống nhất.
        """
        raw_path = Path("data") / "raw" / "openaq_2025.parquet"
        metadata_side = f"data/raw/{raw_path.name}"
        self.assertNotIn("\\", metadata_side,
                         "Khối metadata dùng `.name` nên không bao giờ có `\\`.")
        self.assertIn(
            "\\", str(raw_path),
            "Bên runtime log, `str(Path)` trên Windows giữ dấu `\\`.",
        )
        self.assertNotEqual(
            metadata_side, str(raw_path),
            "Hai writer đang biểu diễn cùng một tệp khác nhau — đây là phát hiện "
            "đang mở (bất đẳng đẳng dấu phân cách), không phải hành vi đã chốt.",
        )


class _BlockMustNotSwallowHandler(logging.Handler):
    """
    Biến `except Exception -> logger.warning` của khối ghi thành lỗi thật.

    Vì sao: nếu khối ném exception, tệp metadata KHÔNG được ghi lại -> nội dung sau
    khi chạy y hệt đầu vào -> các test so sánh (schema_version, artifact_dtypes,
    byte-identical) PASS VACUOUSLY. Handler này chặn đúng lớp vacuity đó.

    Chỉ nổ ở WARNING trở lên: `logger.info("Đã cập nhật ... thành công")` ở cuối
    khối là log thành công bình thường, không phải đường nuốt lỗi. Ngưỡng đặt ở
    đây, không đặt ở `logging` level của logger, để không phụ thuộc cấu hình mức
    của logger (mặc định WARNING) và để handler tự quyết định.
    """

    MIN_LEVEL = logging.WARNING

    def emit(self, record):
        if record.levelno < self.MIN_LEVEL:
            return  # log thành công bình thường, không phải lỗi bị nuốt
        raise AssertionError(
            f"Khối ghi metadata.json nuốt lỗi (log {record.levelname}): "
            f"{record.getMessage()}"
        )


def _scratch_parent() -> Path:
    """
    Thư mục cha cho repo git sạch dùng làm oracle. Ưu tiên `<temp>/opencode`
    (được duyệt sẵn cho công cụ), fallback về thư mục tạm của hệ điều hành.
    """
    system_tmp = Path(tempfile.gettempdir())
    preferred = system_tmp / "opencode"
    parent = preferred if preferred.is_dir() else system_tmp
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def _check_ignore(root: Path, env: dict, rel_path: str) -> tuple[bool, str, str]:
    """
    Hỏi CHÍNH GIT tệp `rel_path` có bị `.gitignore` loại trừ không.

    Vì sao không tự viết matcher: ngữ nghĩa gitignore (rule cuối cùng thắng, `!`
    bật lại, pattern không có `/` khớp ở MỌI độ sâu, `*` không xuyên dấu `/`,
    rule kết thúc bằng `/` chỉ áp cho thư mục) quá dễ sai khi mô phỏng thủ công —
    một matcher sai có thể khiến carve-out `!data/raw/metadata.json` bị bỏ sót.
    `git check-ignore` là oracle không thể sai lệch.

    Trả về `(ignored, source, pattern)`; `ignored=False` khi không rule nào khớp
    HOẶC rule quyết định là negate.
    """
    proc = subprocess.run(
        ["git", "check-ignore", "--no-index", "-v", rel_path],
        cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode == 1:
        return False, "", ""  # không khớp rule nào -> KHÔNG bị ignore
    if proc.returncode != 0:
        raise AssertionError(
            f"`git check-ignore` thất bại (rc={proc.returncode}) cho {rel_path!r}: "
            f"{proc.stderr.strip()}"
        )
    # Định dạng -v: "<source>:<số dòng>:<pattern>\t<đường dẫn>"
    head = proc.stdout.strip().split("\t", 1)[0]
    source, _, lineno_and_pattern = head.partition(":")
    _, _, pattern = lineno_and_pattern.partition(":")
    # `-v` báo rc=0 cho cả rule negate; pattern `!` = KHÔNG bị ignore.
    return not pattern.startswith("!"), source, pattern


class TestRuntimeLogIsActuallyGitignored(unittest.TestCase):
    """
    Bảo vệ tính chất quan trọng nhất của A-3: tệp runtime log PHẢI bị `.gitignore`
    loại trừ. Nếu không, việc tách trạng thái runtime chỉ là ẩn giấu vấn đề —
    mỗi lần chạy lại vẫn làm bẩn working tree y hệt trước đây.

    Oracle là `git check-ignore` chạy trên một repo sạch CHỈ chứa bản sao
    `.gitignore` của repo này (trong thư mục tạm NGOÀI repo). `.gitignore` thật
    không bị đụng tới và không lệnh git nào ở đây mutate repo thật.
    """

    #: (đường dẫn tương đối, có bị ignore, rule phải quyết định) — chốt lại chính
    #: các ca mà matcher viết tay trước đây trả lời SAI.
    ORACLE_FIDELITY_CASES = (
        ("data/raw/some_payload.json", True, "data/raw/*.json"),
        # `*` của git KHÔNG xuyên dấu `/` — matcher cũ (fnmatch) cho là có.
        ("data/raw/nested/deep.json", False, None),
        # Rule kết thúc bằng `/` (chỉ thư mục) + khớp ở mọi độ sâu.
        (".pytest_cache/v/cache/lastfailed", True, ".pytest_cache/"),
        ("coverage/.coverage.abc123", True, ".coverage.*"),
        # Pattern không chứa `/` khớp ở BẤT KỲ độ sâu nào.
        ("data/desktop.ini", True, "desktop.ini"),
        ("data/raw/metadata.json", False, "!data/raw/metadata.json"),
    )

    @contextlib.contextmanager
    def _scratch_repo(self):
        """Yield `(root, env)` của một repo git sạch chứa bản sao `.gitignore`."""
        gitignore = REPO_ROOT / ".gitignore"
        if not gitignore.is_file():
            self.skipTest(f"Không tìm thấy .gitignore tại {gitignore}")
        with tempfile.TemporaryDirectory(dir=_scratch_parent()) as tmp:
            root = Path(tmp)
            shutil.copyfile(gitignore, root / ".gitignore")
            # Trung hoà global/system git config để kết quả chỉ phản ánh
            # `.gitignore` của repo, không phụ thuộc máy đang chạy test.
            env = dict(
                os.environ,
                GIT_CONFIG_GLOBAL=str(root / "__no_global_config__"),
                GIT_CONFIG_SYSTEM=str(root / "__no_system_config__"),
                GIT_CONFIG_NOSYSTEM="1",
            )
            try:
                init = subprocess.run(
                    ["git", "init", "-q"], cwd=root, env=env,
                    capture_output=True, text=True, encoding="utf-8",
                )
            except OSError as exc:  # git không có trong PATH
                self.skipTest(f"Không chạy được git ({exc}) — cần git làm oracle.")
            if init.returncode != 0:
                self.skipTest(f"`git init` thất bại: {init.stderr.strip()}")
            yield root, env

    def test_check_ignore_oracle_is_faithful_to_real_git(self):
        """
        Chính oracle phải đúng trước khi dùng nó để kết luận về tệp runtime log.
        Ca `data/raw/nested/deep.json` là ca NGUY HIỂM: matcher `fnmatch` cũ khớp
        sai ở đây và có thể che mất carve-out `!data/raw/metadata.json`.
        """
        with self._scratch_repo() as (root, env):
            for rel_path, expected_ignored, expected_rule in self.ORACLE_FIDELITY_CASES:
                with self.subTest(path=rel_path):
                    ignored, source, pattern = _check_ignore(root, env, rel_path)
                    self.assertEqual(ignored, expected_ignored)
                    if expected_rule is None:
                        self.assertEqual(
                            pattern, "",
                            f"{rel_path!r} không được rule nào khớp, "
                            "không được quy cho một rule.",
                        )
                    else:
                        self.assertEqual(pattern, expected_rule)
                        self.assertEqual(
                            source, ".gitignore",
                            "Rule phải đến từ .gitignore của repo, "
                            "không được từ global/system git config.",
                        )

    def test_runtime_log_path_is_matched_by_a_real_gitignore_rule(self):
        """
        Đường dẫn runtime log mặc định phải bị `.gitignore` loại trừ bởi một rule
        thật — và rule quyết định KHÔNG được là negate.
        """
        with self._scratch_repo() as (root, env):
            rel_path = f"data/raw/{PIPELINE_RUNTIME_LOG_FILENAME}"
            ignored, source, pattern = _check_ignore(root, env, rel_path)
            self.assertTrue(
                ignored,
                f"{rel_path!r} KHÔNG bị .gitignore loại trừ — tệp runtime log sẽ "
                "bị git theo dõi và làm bẩn working tree.",
            )
            self.assertTrue(
                source.endswith(".gitignore"),
                f"{rel_path!r} bị loại trừ bởi {source!r} chứ không phải .gitignore "
                "của repo — kết luận sẽ phụ thuộc cấu hình git trên máy này.",
            )
            self.assertFalse(
                pattern.startswith("!"),
                f"Rule quyết định cho {rel_path!r} là {pattern!r} (negate) — "
                "tệp sẽ bị git theo dõi, trái với mục đích của A-3.",
            )

    def test_metadata_json_is_not_ignored(self):
        """
        Đối lập với test trên: `metadata.json` là hồ sơ provenance tĩnh và PHẢI được
        git theo dõi. Nếu test này fail thì lớp bảo vệ dữ liệu thô đã bị hỏng.
        """
        with self._scratch_repo() as (root, env):
            rel_path = "data/raw/metadata.json"
            ignored, _, pattern = _check_ignore(root, env, rel_path)
            self.assertFalse(
                ignored,
                f"metadata.json phải được git theo dõi, nhưng git báo BỊ ignore "
                f"(rule quyết định: {pattern!r}).",
            )

    def test_emitted_filename_follows_gitignore_policy_not_metadata_carveout(self):
        """
        Không assert tên tệp bằng literal (thì test chỉ fail khi code và test
        cùng đổi — vô nghĩa). Ở đây hằng số bị ràng buộc bởi CHÍNH SÁCH
        `.gitignore` thật: tên mà `write_pipeline_runtime_log` thực sự ghi ra
        phải bị ignore, và khác với carve-out `data/raw/metadata.json`.
        Đổi hằng số mà không sửa `.gitignore` -> test đỏ.
        """
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "raw"
            emitted = write_pipeline_runtime_log(self._metadata_block_summary(), log_dir=log_dir)
            self.assertTrue(emitted.is_file(), "Phải ghi ra được tệp để lấy tên thật.")
            emitted_name = emitted.name

        self.assertEqual(
            emitted_name, PIPELINE_RUNTIME_LOG_FILENAME,
            "Tên tệp thực sự ghi ra lệch với PIPELINE_RUNTIME_LOG_FILENAME — "
            "hằng số không còn mô tả đúng hành vi.",
        )

        with self._scratch_repo() as (root, env):
            runtime_rel = f"data/raw/{emitted_name}"
            runtime_ignored, _, _ = _check_ignore(root, env, runtime_rel)
            metadata_rel = "data/raw/metadata.json"
            metadata_ignored, _, _ = _check_ignore(root, env, metadata_rel)

            self.assertFalse(
                metadata_ignored,
                f"Tiền đề hỏng: {metadata_rel!r} đang bị .gitignore loại trừ.",
            )
            self.assertTrue(
                runtime_ignored,
                f"Tệp runtime log ghi ra là {runtime_rel!r} nhưng .gitignore KHÔNG "
                "loại trừ nó — mỗi lần chạy pipeline lại làm bẩn working tree.",
            )
            self.assertNotEqual(
                emitted_name, "metadata.json",
                "Tệp runtime log không được ghi đè lên hồ sơ provenance tĩnh "
                f"{metadata_rel!r} (carve-out `!{metadata_rel}` trong .gitignore).",
            )

    @staticmethod
    def _metadata_block_summary() -> dict:
        """Summary tối thiểu cho `write_pipeline_runtime_log` (nội dung giả)."""
        return {
            "execution_time_seconds": 1.0,
            "query_start": "SENTINEL_START",
            "query_end": "SENTINEL_END",
            "openaq": {"raw_records": 0},
        }


class TestMetadataMutationBlockPreservesProvenance(unittest.TestCase):
    """
    Chốt chặn hai lỗi do khối ghi `data/raw/metadata.json` trong
    `run_collection_pipeline()` gây ra (phát hiện A-3, M1 post-audit).

    Lỗi 1 — DOWNGRADE: khối ghi cứng `schema_version = "1.2.0"` trong khi tệp
    đang được git theo dõi là `"1.3.0"`, nên MỌI lần chạy đều hạ phiên bản một
    trường provenance và làm bẩn working tree dù dữ liệu không đổi.

    Lỗi 2 — XÓA SILENT: khối gán đè `collection_pipeline_execution` bằng một dict
    MỚI không có `artifact_dtypes`, xoá vĩnh viễn provenance dtype/shape của cả
    ba tệp parquet (do `src/cleaning_pipeline.py` sinh ra).

    Các test dưới đây chạy khối MÃ THẬT (trích nguyên văn từ source, không viết
    lại), trong `tempfile.TemporaryDirectory()` ngoài repo, offline. Mọi giá trị
    đầu vào là sentinel tổng hợp, KHÔNG phải số đo Hà Nội.
    """

    #: Token BẮT BUỘC phải xuất hiện trong khối được trích. Anchor theo identifier
    #: chứ không theo số dòng/số ký tự, nên refactor hợp lệ không vô tình làm đỏ,
    #: còn block bị cắt thì đỏ kèm chẩn đoán thay vì xanh vacuous:
    #:   - `METADATA_SCHEMA_VERSION`, `schema_version` -> fix DOWNGRADE
    #:   - `recomputed_execution`, `existing_execution` -> fix XÓA SILENT (merge)
    #:   - `json.dump` -> thao tác ghi thật xuống đĩa (tính tất định byte-identical)
    REQUIRED_BLOCK_MARKERS = (
        "METADATA_SCHEMA_VERSION",
        "schema_version",
        "recomputed_execution",
        "existing_execution",
        "json.dump",
    )

    def _committed_metadata(self) -> dict:
        """Nội dung `data/raw/metadata.json` ở HEAD — nguồn chuẩn để so sánh."""
        try:
            proc = subprocess.run(
                ["git", "show", "HEAD:data/raw/metadata.json"],
                cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
            )
        except OSError as exc:  # git không có trong PATH -> lỗi môi trường, không phải lỗi code
            self.skipTest(f"Không chạy được git ({exc}) — bỏ qua để không fail vì môi trường.")
        if proc.returncode != 0:
            self.skipTest(
                "Không đọc được data/raw/metadata.json ở HEAD (git show thất bại) — "
                "bỏ qua để không phụ thuộc trạng thái git khi chạy test."
            )
        return json.loads(proc.stdout)

    def _committed_metadata_bytes(self) -> bytes:
        """
        Byte THÔ của `data/raw/metadata.json` ở HEAD (không parse) — dùng để so
        byte-identical, và để chứng minh chính test này không làm bẩn tệp đang
        được git theo dõi.
        """
        try:
            proc = subprocess.run(
                ["git", "show", "HEAD:data/raw/metadata.json"],
                cwd=REPO_ROOT, capture_output=True,
            )
        except OSError as exc:
            self.skipTest(f"Không chạy được git ({exc}) — bỏ qua để không fail vì môi trường.")
        if proc.returncode != 0:
            self.skipTest(
                "Không đọc được data/raw/metadata.json ở HEAD (git show thất bại) — "
                "bỏ qua để không phụ thuộc trạng thái git khi chạy test."
            )
        return proc.stdout

    @staticmethod
    def _extract_block() -> str:
        """
        Trích nguyên văn khối `if metadata_path.exists():` ... từ
        `src/data_collection.py`, dedent để exec độc lập. Cố tình KHÔNG viết lại
        logic: nếu khối trong source đổi, test phải đo đúng thứ đang chạy.

        Anchors là văn bản thuần nên KHÔNG tự bảo đảm cắt đúng khối; guard toàn
        vẹn nằm trong `_assert_capture_is_complete`.
        """
        source = Path(__file__).resolve().parent.parent / "src" / "data_collection.py"
        lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
        start = next(i for i, l in enumerate(lines)
                     if l.strip() == "if metadata_path.exists():")
        end = next(i for i, l in enumerate(lines) if "Ghi trạng thái runtime" in l)
        if end < start:
            raise AssertionError(
                f"Anchor `end` ({end}) nằm TRƯỚC anchor `start` ({start}) trong "
                f"{source} — comment kết thúc khối đã bị di chuyển/đổi câu. "
                "Sửa lại `_extract_block` cho khớp khối thật."
            )
        code = textwrap.dedent("".join(lines[start:end]))
        TestMetadataMutationBlockPreservesProvenance._assert_capture_is_complete(code)
        return code

    @staticmethod
    def _strip_comments(code: str) -> str:
        r"""
        Cùng văn bản nhưng ĐÃ BỎ comment và docstring, giữ nguyên mọi ký tự còn
        lại (kể cả thụt lề và newline) để marker nhiều token như `json.dump` vẫn
        khớp nguyên văn.

        Vì sao: kiểm tra marker gốc là `marker in code` — substring thô, nên một
        token CHỈ nằm trong comment vẫn thoả. Đó đúng là lớp vacuity mà guard này
        sinh ra để chặn: block bị cắt còn lại vài dòng comment thì guard vẫn xanh
        trong khi `exec` không làm gì.

        Docstring chỉ bị bỏ khi là string literal MỘT DÒNG chiếm trọn dòng —
        string nhiều dòng được giữ nguyên để không cắt nhầm vào giá trị chuỗi.
        """
        import io
        import tokenize

        lines = code.splitlines(keepends=True)
        blanked = set()
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.COMMENT:
                blanked.update(range(tok.start[0], tok.end[0] + 1))
            elif tok.type == tokenize.STRING and tok.start[0] == tok.end[0]:
                row = tok.start[0] - 1
                if 0 <= row < len(lines) and lines[row].strip() == tok.string:
                    blanked.add(row + 1)
        return "".join(
            line for idx, line in enumerate(lines, 1) if idx not in blanked
        )

    @classmethod
    def _assert_capture_is_complete(cls, code: str) -> None:
        """
        Chặn block bị trích CẮT/RỖNG — nguyên nhân gốc của PASS VACUOUS.

        Anchor `end` là chuỗi comment không kiểu: một refactor tương lai (đổi câu
        comment, thêm `if metadata_path.exists():` sớm hơn, đưa lệnh read ra
        ngoài) có thể làm `lines[start:end]` rỗng hoặc ngắn. `ast.parse("")`
        thành công và `exec("")` là no-op, nên các test đo hành vi sẽ xanh trên
        code KHÔNG còn chạy. Ở đây thì lỗi nổi lên kèm danh sách marker thiếu.

        Anchor theo IDENTIFIER/token, không theo số dòng hay độ dài ký tự, để
        refactor hợp lệ không vô tình làm đỏ.

        Ba cổng, theo thứ tự từ rẻ đến đắt:
        1. `code` không rỗng.
        2. `ast.parse(code)` — block phải là Python hợp lệ.
        3. Thân module phải có ít nhất MỘT câu lệnh thực thi khác docstring —
           `ast.parse("")` và `exec("")` đều thành công nên đây mới là cổng
           chống vacuity thật sự.
        Marker được kiểm trên bản ĐÃ BỎ COMMENT (`_strip_comments`), không
        phải trên thô: nếu không, token nằm trong comment sẽ thoả `in`.
        """
        if not code.strip():
            raise AssertionError(
                "KHỐI ghi metadata.json được trích ra RỖNG (0 dòng): anchor `end` "
                "không còn đứng sau anchor `start`. `ast.parse('')`/`exec('')` đều "
                "thành công nên test sẽ PASS VACUOUSLY trên code không chạy. "
                "Sửa anchor trong `_extract_block`."
            )
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise AssertionError(
                "KHỐI ghi metadata.json được trích ra KHÔNG parse được "
                f"({exc.__class__.__name__}: {exc}) — anchor `start`/`end` đang cắt "
                "giữa biểu thức, nên `exec` sẽ nổ lỗi khó đọc và test đo trên "
                "code không chạy. Sửa anchor trong `_extract_block`."
            ) from exc

        def _is_docstring(node) -> bool:
            return (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )

        executable = [n for n in tree.body if not _is_docstring(n)]
        if not executable:
            raise AssertionError(
                "KHỐI ghi metadata.json được trích ra chỉ còn docstring/comment, "
                "KHÔNG còn câu lệnh thực thi nào — `exec` sẽ là no-op và mọi test "
                "đo hành vi sẽ PASS VACUOUSLY. Sửa anchor trong `_extract_block`."
            )

        code_only = cls._strip_comments(code)
        missing = [m for m in cls.REQUIRED_BLOCK_MARKERS if m not in code_only]
        if missing:
            raise AssertionError(
                "KHỐI ghi metadata.json được trích ra KHÔNG ĐẦY ĐỦ — thiếu "
                f"marker gánh tải: {missing!r}. Block đã bị cắt/thu hẹp (anchor văn "
                "bản lệch), nên test đo trên code không chạy và sẽ PASS VACUOUSLY. "
                f"Đã bắt {len(code.splitlines())} dòng; marker còn thiếu: "
                + "; ".join(missing)
            )

    def _sentinel_frame(self, metadata_path: Path) -> dict:
        """Giá trị giả cho các biến cục bộ mà khối tham chiếu (không phải dữ liệu thật)."""
        import pandas as pd

        class _FakePath:
            def __init__(self, name): self.name = name

        return {
            # WHY `datetime`/`timezone` phải có mặt ở đây: nếu ai đó cài lại dòng
            # `meta["last_updated_utc"] = datetime.now(timezone.utc).isoformat()`
            # vào khối, khối phải chạy THẬT để `test_last_updated_utc_is_not_rewritten_
            # with_wall_clock` đỏ ĐÚNG ở assertion A-3 (kèm chẩn đoán viết tay ở
            # dòng assertEqual). Thiếu hai tên này, biểu thức đó ném NameError,
            # `except Exception -> logger.warning` của khối nuốt mất, và
            # `_BlockMustNotSwallowHandler` đổi thành AssertionError("Khối ghi
            # metadata.json nuốt lỗi") — chẩn đoán sai hướng, dẫn người đọc tới
            # `except` thay vì tới chỗ gán wall-clock thật sự.
            "datetime": datetime,
            "timezone": timezone,
            "metadata_path": metadata_path,
            "query_start": "SENTINEL_START",
            "query_end": "SENTINEL_END",
            "study_window_start": None, "study_window_end": None,
            "weather_request_url": "SENTINEL_URL",
            "openaq_raw_path": _FakePath("SENTINEL_openaq.parquet"),
            "weather_raw_path": _FakePath("SENTINEL_weather.json"),
            "openaq_sha256": "SENTINEL_SHA_A",
            "weather_sha256": "SENTINEL_SHA_B",
            "df_openaq_raw": pd.DataFrame({"sentinel_col": [1, 2, 3]}),
            "df_air_canonical": pd.DataFrame({"pm25": [1.0, None, 3.0]}),
            "df_weather_canonical": pd.DataFrame({"temperature": [20.0, 21.0, 22.0]}),
            "df_overlap": pd.DataFrame(
                {"timestamp": ["SENTINEL_T1", "SENTINEL_T2"]}),
            "geo_filter_stats": {"filtered_out_records": 0},
            "summary": {"openaq": {"pm25_valid_observations": 3,
                                   "pm25_missing_observations": 0,
                                   "pm25_missing_rate_pct": 0.0}},
            "actual_min_openaq": "SENTINEL_MIN_A",
            "actual_max_openaq": "SENTINEL_MAX_A",
            "actual_min_weather": "SENTINEL_MIN_W",
            "actual_max_weather": "SENTINEL_MAX_W",
            "weather_max_missing_pct": 0.0,
            "weather_validation": {
                "validation_status": "SENTINEL_STATUS", "is_valid": True,
                "warnings": [], "timezone": "Asia/Ho_Chi_Minh",
                "is_continuous_hourly": True, "gap_count": 0, "max_missing_pct": 0.0,
            },
            # WHY shape phải ĐỦ, không phải một khoá: khối gán THAY THẾ (không merge
            # sâu) `collection_pipeline_execution.open_meteo_ingestion` và
            # `.airnow_dos_ingestion` bằng giá trị nó tự tính. Nếu sentinel ở đây
            # chỉ có một khoá thì `test_full_run_does_not_dirty_tracked_metadata` báo
            # "xoá khoá lồng nhau" — nhưng đó là hệ quả của sentinel thiếu khoá, KHÔNG
            # phải provenance bị mất. Hai dict dưới đây mirror ĐÚNG shape mà
            # `run_collection_pipeline()` dựng ra (`cleaning_totals` ở
            # `data_collection.py:635`, `airnow_summary` nhánh not-executed ở `:1237`).
            "cleaning_totals": {
                "disguised_missing": 0, "out_of_bounds": 0, "unparseable": 0,
            },
            "airnow_summary": {
                "canonical_station_id": "SENTINEL_AIRNOW_STATION",
                "station_name": "SENTINEL_AIRNOW_NAME",
                "adapter_status": "implemented",
                "ingestion_status": "not_executed_pending_raw_input",
                "role": "historical_source_fallback",
                "raw_input": "unavailable_in_current_execution",
                "note": "SENTINEL_NOTE",
            },
            "sync_status": "SENTINEL_SYNC",
            "air_quality_coverage_pct": 100.0,
            "DISQUALIFIED_OPENAQ_LOCATION_ID": 2178,
            "HANOI_OPENAQ_LOCATION_ID": 4946811,
            "STATION_OPENAQ_HANOI": "SENTINEL_STATION_A",
            "LOCATION_OPENAQ_HANOI": "SENTINEL_NAME_A",
            "COORDS_OPENAQ_HANOI": (0.0, 0.0),
            "WEATHER_PHYSICAL_BOUNDS": {},
            "METADATA_SCHEMA_VERSION": METADATA_SCHEMA_VERSION,
            "PIPELINE_RUNTIME_LOG_FILENAME": PIPELINE_RUNTIME_LOG_FILENAME,
            "json": json, "logger": logging.getLogger("test-metadata-block"),
        }

    def _run_block(self, meta_dict: dict):
        """
        Ghi dict vào tệp tạm, chạy khối thật, trả về (bytes, dict sau khi chạy).

        Gắn `_BlockMustNotSwallowHandler` để `except Exception -> logger.warning`
        của khối trở thành lỗi thật: nếu khối ném exception thì tệp KHÔNG được ghi
        lại, nội dung sau khi chạy y hệt đầu vào và các test so sánh sẽ xanh
        vacuous. Handler được tháo qua addCleanup nên không rò sang test khác.
        """
        log = logging.getLogger("test-metadata-block")
        handler = _BlockMustNotSwallowHandler()
        log.addHandler(handler)
        self.addCleanup(log.removeHandler, handler)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.json"
            path.write_text(
                json.dumps(meta_dict, ensure_ascii=False, indent=2), encoding="utf-8")

            frame = self._sentinel_frame(path)
            code = self._extract_block()
            ast.parse(code)  # cổng cú pháp: exec trực tiếp sẽ báo lỗi khó đọc hơn
            exec(compile(code, "<test:metadata_block>", "exec"), frame)

            raw = path.read_bytes()
            return raw, json.loads(raw)

    def test_strip_comments_keeps_real_calls_and_drops_comment_only_tokens(self):
        """
        Chính `_strip_comments` phải đúng, nếu không `REQUIRED_BLOCK_MARKERS` vô
        nghĩa. Cụ thể bắt đúng lớp lỗi đã xảy ra: một bản hiện thực ghép token
        bằng `" "` biến `json.dump(...)` thành `json . dump (...)` thì marker
        `json.dump` không bao giờ khớp — guard đỏ với chẩn đoán sai hướng
        ("block bị cắt") dù block lành lặn.

        Ba phải chứng minh:
        1. `json.dump(meta, f, ...)` thật sống sót nguyên văn sau khi bỏ comment.
        2. Token CHỈ nằm trong comment thì biến mất (nếu không, marker trong
           comment vẫn làm `marker in code` xanh -> PASS VACUOUS).
        3. Docstring một dòng chiếm trọn dòng cũng bị bỏ.
        """
        snippet = textwrap.dedent(
            '''
            """Docstring một dòng, phải bị bỏ."""
            import json
            # json.dump chỉ nằm trong comment này, phải biến mất:
            # json.dump(FAKE, f)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            '''
        )
        stripped = self._strip_comments(snippet)

        self.assertIn(
            "json.dump(meta, f, indent=2, ensure_ascii=False)", stripped,
            "`json.dump` thật bị phá vỡ khi bỏ comment — marker `json.dump` sẽ "
            "không khớp dù block chạy đúng.",
        )
        self.assertNotIn(
            "FAKE", stripped,
            "Token nằm trong comment vẫn sống -> marker kiểm trên bản bỏ comment "
            "mất tác dụng chống PASS VACUOUS.",
        )
        self.assertNotIn("Docstring", stripped, "Docstring một dòng chưa bị bỏ.")

        # Marker thật của khối phải khớp trên bản đã bỏ comment.
        code_only = self._strip_comments(self._extract_block())
        for marker in self.REQUIRED_BLOCK_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, code_only)

    def test_schema_version_constant_matches_committed_metadata(self):
        """
        Hằng số trong code phải khớp `schema_version` đang được git theo dõi.
        Đây là cách bắt lỗi DOWNGRADE ngay tại nguồn, không cần chạy pipeline.
        """
        committed = self._committed_metadata()
        self.assertEqual(
            METADATA_SCHEMA_VERSION, committed["schema_version"],
            "METADATA_SCHEMA_VERSION trong src/data_collection.py lệch với "
            "schema_version đang được track trong data/raw/metadata.json — "
            "mọi lần chạy pipeline sẽ ghi đè (và có thể hạ phiên bản) trường này.",
        )

    def test_schema_version_is_not_downgraded_by_the_block(self):
        """Chạy khối trên bản metadata đã commit: `schema_version` phải giữ nguyên."""
        committed = self._committed_metadata()
        _, after = self._run_block(committed)

        self.assertEqual(
            after["schema_version"], committed["schema_version"],
            f"Khối đã đổi schema_version: {committed['schema_version']!r} -> "
            f"{after['schema_version']!r}. Đây là provenance downgrade và làm "
            "bẩn working tree ở mỗi lần chạy.",
        )

    def test_merge_preserves_preexisting_artifact_dtypes_byte_for_byte(self):
        """
        `collection_pipeline_execution.artifact_dtypes` phải sống sót nguyên vẹn:
        khối chạy pipeline KHÔNG tính lại dtype/shape (việc đó thuộc
        `src/cleaning_pipeline.py`), nên nó chỉ tồn tại trong tệp đã track.
        """
        committed = self._committed_metadata()
        before = committed["collection_pipeline_execution"].get("artifact_dtypes")
        self.assertIsNotNone(
            before,
            "Tiền đề: metadata.json ở HEAD phải có artifact_dtypes để test có ý nghĩa.",
        )

        _, after = self._run_block(committed)
        got = after["collection_pipeline_execution"].get("artifact_dtypes")

        self.assertIsNotNone(
            got, "artifact_dtypes bị XÓA khỏi collection_pipeline_execution — "
                 "khối đang gán đè dict thay vì hợp nhất vào giá trị trên đĩa.",
        )
        self.assertEqual(got, before, "artifact_dtypes bị thay đổi — provenance dtype/shape phải được giữ nguyên.")
        # So khớp byte-for-byte trên chuỗi JSON, không chỉ dict tương đương.
        self.assertEqual(
            json.dumps(got, sort_keys=True, ensure_ascii=False),
            json.dumps(before, sort_keys=True, ensure_ascii=False),
            "artifact_dtypes không giống nhau ở mức tuần tự hóa JSON.",
        )

    def test_block_removes_no_top_level_or_nested_keys(self):
        """
        Hợp đồng rộng hơn `artifact_dtypes`: khối được phép THÊM và SỬA (đó là
        công việc của nó) nhưng không được XÓA khoá nào — kể cả khoá lạ do
        người khác thêm vào.
        """
        committed = self._committed_metadata()
        _, after = self._run_block(committed)

        removed = set(committed) - set(after)
        self.assertEqual(removed, set(), f"Block xoá khoá cấp cao nhất: {sorted(removed)}")

        before_cpe = set(committed["collection_pipeline_execution"])
        after_cpe = set(after["collection_pipeline_execution"])
        removed_cpe = before_cpe - after_cpe
        self.assertEqual(
            removed_cpe, set(),
            f"Block xoá khoá trong collection_pipeline_execution: {sorted(removed_cpe)}",
        )

    def test_unrelated_preexisting_provenance_key_survives(self):
        """
        Khoá lạ do người dùng thêm vào phải sống sót — chứng minh cơ chế hợp nhất
        là chung, không phải một ngoại lệ hardcode cho `artifact_dtypes`.
        """
        committed = self._committed_metadata()
        committed["collection_pipeline_execution"]["sentinel_unknown_key"] = {
            "_synthetic": "SENTINEL_NOT_REAL_DATA"
        }
        _, after = self._run_block(committed)
        self.assertEqual(
            after["collection_pipeline_execution"]["sentinel_unknown_key"],
            {"_synthetic": "SENTINEL_NOT_REAL_DATA"},
            "Khoá provenance lạ bị mất — cơ chế merge không giữ được khoá "
            "mà pipeline không tính lại.",
        )

    def test_last_updated_utc_is_not_rewritten_with_wall_clock(self):
        """
        Trường A-3 cốt lõi: `last_updated_utc` là mốc rà soát provenance TĈNH, do
        con người đặt, KHÔNG phải dấu vết đồng hồ của lần chạy pipeline.

        `run_collection_pipeline()` KHÔNG được ghi đè nó bằng
        `datetime.now(...)`. Nếu làm vậy, mỗi lần chạy lại tạo diff chỉ chứa
        timestamp dù dữ liệu thô và provenance không đổi — đúng cái A-3 loại bỏ.
        Trạng thái wall-clock thuộc về `data/raw/<PIPELINE_RUNTIME_LOG_FILENAME>`.
        """
        committed = self._committed_metadata()
        self.assertIn(
            "last_updated_utc", committed,
            "Tiền đề: metadata.json ở HEAD phải có last_updated_utc để test có "
            "ý nghĩa.",
        )

        _, after = self._run_block(committed)

        self.assertEqual(
            after["last_updated_utc"], committed["last_updated_utc"],
            "Pipeline ĐÃ ghi đè `last_updated_utc` bằng datetime.now(...) — đây "
            "chính là lỗi A-3: trường provenance tĩnh bị biến thành dấu vết đồng "
            "hồ, nên mỗi lần chạy lại đều làm bẩn working tree dù dữ liệu không "
            "đổi. Hãy bỏ dòng gán đó và để trạng thái chạy nằm ở "
            f"data/raw/{PIPELINE_RUNTIME_LOG_FILENAME}.",
        )

    def test_full_run_does_not_dirty_tracked_metadata(self):
        """
        GAP: khẳng định đầu-cuối "một lần chạy KHÔNG làm bẩn hồ sơ provenance đang
        được git theo dõi" — chạy khối thật HAI lần trên bản sao tạm của chính tệp
        đã commit, rồi so từng khoá với bản HEAD.

        Ngoài ra kiểm (d): đọc lại `git show HEAD:data/raw/metadata.json` SAU khi
        test chạy và so với lần đọc đầu — chứng minh chính test này không làm bẩn
        tệp đang được track (nó chỉ ghi vào `TemporaryDirectory`).
        """
        head_before = self._committed_metadata_bytes()
        committed = json.loads(head_before.decode("utf-8"))

        first_bytes, after1 = self._run_block(committed)
        second_bytes, after2 = self._run_block(committed)

        # (a) không khoá nào bị xoá — ở mọi tầng lồng nhau, không chỉ cấp cao nhất.
        def _removed_keys(before, after, trail=()):
            gone = []
            if isinstance(before, dict):
                if not isinstance(after, dict):
                    return [trail or ("<root>",)]
                for k, v in before.items():
                    if k not in after:
                        gone.append(trail + (k,))
                    else:
                        gone.extend(_removed_keys(v, after[k], trail + (k,)))
            return gone

        gone = _removed_keys(committed, after1)
        self.assertEqual(
            gone, [],
            f"Khối ghi xoá khoá ở các tầng lồng nhau: {gone!r} — provenance đang "
            "được git theo dõi mất dữ liệu ở mỗi lần chạy.",
        )

        # (b) artifact_dtypes phải byte-identical, không phải "dict tương đương".
        cpe = after1["collection_pipeline_execution"]
        self.assertIn("artifact_dtypes", cpe, "artifact_dtypes bị xoá khỏi metadata.")
        self.assertEqual(
            json.dumps(cpe["artifact_dtypes"], sort_keys=True, ensure_ascii=False),
            json.dumps(
                committed["collection_pipeline_execution"]["artifact_dtypes"],
                sort_keys=True, ensure_ascii=False),
            "artifact_dtypes không còn giống bản HEAD.",
        )

        # (c) hai lần chạy cho cùng byte.
        self.assertEqual(
            first_bytes, second_bytes,
            "Hai lần chạy khối cho output khác nhau — còn phụ thuộc đồng hồ hoặc "
            "thứ tự khoá không ổn định.",
        )
        self.assertEqual(after1, after2, "Hai lần chạy cho nội dung dict khác nhau.")

        # (d) tệp đang được track không đổi trong lúc test này chạy.
        head_after = self._committed_metadata_bytes()
        self.assertEqual(
            head_after, head_before,
            "Bản `data/raw/metadata.json` ở HEAD đã đổi trong lúc test chạy — "
            "test này phải chỉ ghi vào thư mục tạm, không được chạm tệp tracked.",
        )

    def test_running_block_twice_is_byte_identical(self):
        """
        Tính tất định: chạy khối hai lần trên cùng đầu vào phải cho ra CÙNG BYTE.
        Đây là điều kiện để chạy lại notebook không làm bẩn working tree.
        """
        committed = self._committed_metadata()
        first_bytes, _ = self._run_block(committed)
        second_bytes, _ = self._run_block(committed)

        self.assertEqual(
            first_bytes, second_bytes,
            "Hai lần chạy cho output khác nhau — khối vẫn còn phụ thuộc đồng hồ "
            "hoặc thứ tự khóa không ổn định.",
        )

    def test_block_raises_instead_of_silently_swallowing_errors(self):
        """
        Khối có `except Exception` -> `logger.warning`. Với metadata hỏng, lỗi
        phải NỔI LÊN chứ không bị nuốt im lặng.
        """
        log = logging.getLogger("test-metadata-block")
        handler = _BlockMustNotSwallowHandler()
        log.addHandler(handler)
        self.addCleanup(log.removeHandler, handler)
        prev_level, log.level = log.level, logging.WARNING
        self.addCleanup(setattr, log, "level", prev_level)

        # metadata.json tồn tại nhưng không phải JSON hợp lệ -> json.load ném.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.json"
            path.write_text("{ this is not valid json", encoding="utf-8")
            frame = self._sentinel_frame(path)
            with self.assertRaises(AssertionError):
                exec(compile(self._extract_block(), "<test:metadata_block>", "exec"), frame)


if __name__ == "__main__":
    unittest.main(verbosity=2)