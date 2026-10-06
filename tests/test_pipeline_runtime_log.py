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
            # datetime.fromisoform chấp nhận ISO-8601 — ném ValueError nếu sai định dạng.
            from datetime import datetime as _dt

            _dt.fromisoformat(stamp)

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
        """
        if not code.strip():
            raise AssertionError(
                "KHỐI ghi metadata.json được trích ra RỖNG (0 dòng): anchor `end` "
                "không còn đứng sau anchor `start`. `ast.parse('')`/`exec('')` đều "
                "thành công nên test sẽ PASS VACUOUSLY trên code không chạy. "
                "Sửa anchor trong `_extract_block`."
            )
        missing = [m for m in cls.REQUIRED_BLOCK_MARKERS if m not in code]
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
            "cleaning_totals": {"disguised_missing": 0},
            "weather_validation": {
                "validation_status": "SENTINEL_STATUS", "is_valid": True,
                "warnings": [], "timezone": "Asia/Ho_Chi_Minh",
                "is_continuous_hourly": True, "gap_count": 0, "max_missing_pct": 0.0,
            },
            "airnow_summary": {"adapter_status": "SENTINEL_ADAPTER"},
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