"""
audit_defense_readiness.py — Kiểm toán cấu trúc CRISP-DM, liên kết tài liệu,
đồ thị phụ thuộc issue (DAG) và toàn vẹn dữ liệu thực (Issue #17 / #58).

Nguyên tắc:
  - CHỈ ĐỌC (không sửa data/ hay tạo file tạm vào repo).
  - Phân tách rạch ròi kiểm tra cấu trúc (chạy được trên CI không có data/) và
    kiểm tra dữ liệu thật (--real-data; báo SKIPPED nếu thiếu Parquet/raw).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT: Path = Path(__file__).resolve().parent.parent

REQUIRED_DIRS: Tuple[str, ...] = (
    "src",
    "notebooks",
    "data/raw",
    "data/interim",
    "data/processed",
    "figures",
    "reports",
    "docs",
    "tests",
    "scripts",
)

REQUIRED_FILES: Tuple[str, ...] = (
    "README.md",
    "requirements.txt",
    "LICENSE",
    ".gitignore",
    "data/raw/metadata.json",
    "reports/defense_minutes.md",
)

#: Đồ thị phụ thuộc có hướng (issue -> tập các issue tiền đề mà nó phụ thuộc)
ISSUE_DEPENDENCY_GRAPH: Dict[int, Tuple[int, ...]] = {
    1: (),
    2: (1,),
    19: (1, 2),
    3: (2, 19),
    4: (2, 19),
    5: (3, 4),
    6: (5,),
    7: (6,),
    8: (7,),
    9: (8,),
    10: (8, 9),
    11: (7, 8),
    44: (2, 3, 4, 5, 6, 7, 8, 9, 19),
    50: (44,),
    38: (7,),
    12: (7, 11, 44),
    13: (7, 12, 44),
    14: (12, 13, 44),
    15: (11, 12, 13, 14, 44),
    16: (9, 11, 12, 13, 14, 15, 44, 50),
    17: (15, 16, 44, 50),
}


def sha256_file(path: Path) -> str:
    """Tính SHA-256 hex lowercase cho một tệp trên đĩa."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_crisp_dm_structure(root: Path = REPO_ROOT) -> List[str]:
    """Kiểm tra thư mục chuẩn CRISP-DM và các tệp bắt buộc."""
    errors: List[str] = []
    for rel_dir in REQUIRED_DIRS:
        if not (root / rel_dir).is_dir():
            errors.append(f"Missing required directory: {rel_dir}")
    for rel_file in REQUIRED_FILES:
        if not (root / rel_file).is_file():
            errors.append(f"Missing required file: {rel_file}")
    return errors


def check_markdown_links(root: Path = REPO_ROOT) -> Tuple[int, List[str]]:
    """Kiểm tra mọi liên kết tệp tương đối trong tài liệu Markdown cốt lõi."""
    md_files: List[Path] = []
    for top_name in ("README.md", "CONTRIBUTING.md", "AGENTS.md"):
        p = root / top_name
        if p.is_file():
            md_files.append(p)
    md_files.extend(sorted((root / "docs").rglob("*.md")))

    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    checked = 0
    errors: List[str] = []

    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        # Bỏ qua nội dung bên trong code block ``` ... ```
        cleaned_lines: List[str] = []
        in_fence = False
        for line in text.splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence:
                cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines)

        for match in link_re.finditer(cleaned):
            raw_target = match.group(1).strip()
            if (
                not raw_target
                or raw_target.startswith(("http://", "https://", "mailto:", "#"))
            ):
                continue
            file_part = raw_target.split("#", 1)[0].strip()
            if not file_part:
                continue
            checked += 1
            resolved = (md_path.parent / file_part).resolve()
            if not resolved.exists():
                rel_md = md_path.relative_to(root)
                errors.append(f"Broken relative link in {rel_md}: {raw_target}")

    return checked, errors


def check_issue_dependency_dag(
    graph: Dict[int, Tuple[int, ...]] = ISSUE_DEPENDENCY_GRAPH,
) -> List[str]:
    """Xác minh đồ thị phụ thuộc issue hợp lệ và không có chu trình (DAG)."""
    errors: List[str] = []
    known: Set[int] = set(graph.keys())
    for node, deps in graph.items():
        for dep in deps:
            if dep not in known:
                errors.append(f"Issue #{node} depends on unknown issue #{dep}")

    visiting: Set[int] = set()
    visited: Set[int] = set()

    def dfs(u: int) -> None:
        if u in visited:
            return
        if u in visiting:
            errors.append(f"Cycle detected involving issue #{u}")
            return
        visiting.add(u)
        for v in graph.get(u, ()):
            if v in known:
                dfs(v)
        visiting.remove(u)
        visited.add(u)

    for node in sorted(known):
        dfs(node)

    return errors


def check_metadata_provenance(root: Path = REPO_ROOT) -> List[str]:
    """Kiểm tra schema metadata.json và mã băm gốc."""
    errors: List[str] = []
    meta_path = root / "data" / "raw" / "metadata.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid JSON in data/raw/metadata.json: {exc}"]

    exec_block = meta.get("collection_pipeline_execution", {})
    aq_hash = exec_block.get("openaq_ingestion", {}).get("raw_sha256", "")
    wx_hash = exec_block.get("open_meteo_ingestion", {}).get("raw_sha256", "")
    if len(aq_hash) != 64:
        errors.append("Missing or invalid 64-char openaq_ingestion.raw_sha256 in metadata.json")
    if len(wx_hash) != 64:
        errors.append("Missing or invalid 64-char open_meteo_ingestion.raw_sha256 in metadata.json")
    return errors


def check_real_data(root: Path = REPO_ROOT) -> Tuple[str, List[str], List[str]]:
    """
    Kiểm tra dữ liệu thật trên máy cục bộ.
    Trả về (status, notes, errors), trong đó status in {'PASS', 'SKIPPED', 'FAIL'}.
    """
    base_pq = root / "data" / "processed" / "air_pollution_final.parquet"
    ext_pq = root / "data" / "processed" / "air_pollution_extended_2022_2026.parquet"
    if not base_pq.exists() or not ext_pq.exists():
        return (
            "SKIPPED",
            ["Local processed Parquet files not present (expected on CI)."],
            [],
        )

    import pandas as pd  # Lazy import so structural mode has minimal dependencies

    notes: List[str] = []
    errors: List[str] = []

    df_base = pd.read_parquet(base_pq)
    if df_base.shape != (9044, 18):
        errors.append(f"Baseline shape mismatch: expected (9044, 18), got {df_base.shape}")
    else:
        notes.append("Baseline shape verified: (9044, 18)")

    if df_base.duplicated(subset=["station_id", "timestamp"]).any():
        errors.append("Baseline contains duplicate (station_id, timestamp) keys")

    df_ext = pd.read_parquet(ext_pq)
    if df_ext.shape != (37722, 23):
        errors.append(f"Extended shape mismatch: expected (37722, 23), got {df_ext.shape}")
    else:
        notes.append("Extended shape verified: (37722, 23)")

    if df_ext.duplicated(subset=["station_id", "timestamp"]).any():
        errors.append("Extended dataset contains duplicate (station_id, timestamp) keys")

    for st_id, grp in df_ext.groupby("station_id"):
        tr_max = grp.loc[grp["split"] == "train", "timestamp"].max()
        te_min = grp.loc[grp["split"] == "test", "timestamp"].min()
        if not (tr_max < te_min):
            errors.append(f"Chronological leakage in {st_id}: train_max={tr_max} >= test_min={te_min}")
    notes.append("Chronological split verified per station (train_max < test_min)")

    # Verify raw SHA-256 hashes if raw files exist on disk:
    # - Baseline OpenAQ Parquet & Open-Meteo JSON are non-byte-reproducible when refetched
    #   (Parquet compression/metadata & API generationtime_ms), so mismatch is WARN per validate_issue8.py.
    # - VN003 raw_7441 is a pinned snapshot (F-03), so mismatch is FAIL.
    meta = json.loads((root / "data" / "raw" / "metadata.json").read_text(encoding="utf-8"))
    exec_block = meta["collection_pipeline_execution"]
    for label, sub in (
        ("openaq_4946811_raw", exec_block["openaq_ingestion"]),
        ("open_meteo_baseline_raw", exec_block["open_meteo_ingestion"]),
    ):
        raw_p = root / sub["raw_file"]
        expected = sub["raw_sha256"]
        if raw_p.is_file():
            actual = sha256_file(raw_p)
            if actual != expected:
                notes.append(
                    f"WARN: Raw SHA-256 differs for rebuilt {label} "
                    f"(actual={actual[:16]}... vs recorded={expected[:16]}...; expected for refetched Parquet/API JSON)"
                )
            else:
                notes.append(f"Raw SHA-256 exact match for {label}")

    manifest_7441 = root / "reports" / "issue44_openaq_7441_manifest.json"
    if manifest_7441.is_file():
        m = json.loads(manifest_7441.read_text(encoding="utf-8"))
        raw_7441 = root / m["raw_parquet_path"]
        if raw_7441.is_file():
            actual = sha256_file(raw_7441)
            if actual != m["raw_parquet_sha256"]:
                errors.append(f"Pinned raw SHA-256 mismatch for VN003 openaq_raw_7441: {actual} != {m['raw_parquet_sha256']}")
            else:
                notes.append("Pinned raw SHA-256 exact match for VN003 openaq_raw_7441")

    status = "FAIL" if errors else "PASS"
    return status, notes, errors


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit repository defense readiness (Issue #17)")
    parser.add_argument(
        "--real-data",
        action="store_true",
        help="Verify local Parquet schema, split chronology, and raw SHA-256 when data/ exists.",
    )
    args = parser.parse_args(argv)

    all_errors: List[str] = []

    struct_errs = check_crisp_dm_structure()
    all_errors.extend(struct_errs)
    print(f"[CRISP-DM Structure] {'PASS' if not struct_errs else 'FAIL'} ({len(struct_errs)} errors)")

    n_links, link_errs = check_markdown_links()
    all_errors.extend(link_errs)
    print(f"[Markdown Links]     {'PASS' if not link_errs else 'FAIL'} ({n_links} checked, {len(link_errs)} broken)")

    dag_errs = check_issue_dependency_dag()
    all_errors.extend(dag_errs)
    print(f"[Issue DAG]          {'PASS' if not dag_errs else 'FAIL'} ({len(ISSUE_DEPENDENCY_GRAPH)} nodes, {len(dag_errs)} errors)")

    meta_errs = check_metadata_provenance()
    all_errors.extend(meta_errs)
    print(f"[Metadata Schema]    {'PASS' if not meta_errs else 'FAIL'} ({len(meta_errs)} errors)")

    if args.real_data:
        rd_status, rd_notes, rd_errs = check_real_data()
        all_errors.extend(rd_errs)
        print(f"[Real-Data Audit]    {rd_status}")
        for note in rd_notes:
            print(f"  - {note}")

    for err in all_errors:
        print(f"ERROR: {err}", file=sys.stderr)

    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
