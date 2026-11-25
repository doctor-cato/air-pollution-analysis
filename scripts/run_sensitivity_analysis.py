"""
scripts/run_sensitivity_analysis.py — CLI chạy Phân tích Độ nhạy Đa chiều (Issue #15).

Hỗ trợ `--data-dir` (mặc định `REPO_ROOT / "data"`) ở chế độ CHỈ ĐỌC (không bao giờ sửa đổi `data/`),
xuất đồng bộ:
  - `reports/sensitivity_analysis.csv`
  - `reports/sensitivity_analysis.md`
và kiểm chứng SHA-256 bất biến của các artifact baseline trước/sau khi chạy.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.sensitivity import render_sensitivity_markdown, run_full_sensitivity_suite


def _configure_stdio_utf8() -> None:
    """Bảo đảm in UTF-8 an toàn trên console Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8")
            except Exception:
                pass


def _write_lf_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.replace("\r\n", "\n").rstrip("\n") + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(normalized)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chạy phân tích độ nhạy đa chiều Issue #15 và xuất CSV + Markdown."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Đường dẫn thư mục data/ chứa processed/*.parquet (chỉ đọc; mặc định: REPO_ROOT/data).",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=REPO_ROOT / "reports" / "sensitivity_analysis.csv",
        help="Đường dẫn xuất bảng CSV tổng hợp (mặc định: reports/sensitivity_analysis.csv).",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=REPO_ROOT / "reports" / "sensitivity_analysis.md",
        help="Đường dẫn xuất báo cáo Markdown (mặc định: reports/sensitivity_analysis.md).",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Tùy chọn chỉ định run_id cố định cho lần chạy.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _configure_stdio_utf8()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    args = parse_args(argv)

    results = run_full_sensitivity_suite(
        data_dir=args.data_dir,
        repo_root=REPO_ROOT,
        run_id=args.run_id,
    )

    out_csv = Path(args.output_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    csv_text = results.combined_df.to_csv(index=False, lineterminator="\n")
    _write_lf_text(out_csv, csv_text)

    md_text = render_sensitivity_markdown(results)
    _write_lf_text(Path(args.output_md), md_text)

    print(f"[OK] Run ID: {results.run_id}")
    print(f"[OK] CSV written: {out_csv} ({len(results.combined_df)} rows)")
    print(f"[OK] Markdown written: {args.output_md}")
    print("[OK] Baseline SHA-256 immutability verified (zero change across all baseline artifacts).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
