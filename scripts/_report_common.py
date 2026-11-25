"""Shared helpers for build_final_report.py and build_defense_slides.py.

Integrity rule: every number printed in the report/slides is paired with a
(source file, verbatim needle) check that is executed at build time. If an
upstream artifact changes and the needle disappears, the build fails instead
of silently publishing a stale number.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

BASELINE = "VN001_HANOI_556_NGUYEN_VAN_CU"
EXTENDED = "VN003_HANOI_OPENAQ_7441"
V_BASE = "1.0.0-m2-baseline"
V_EXT = "2.0.0-issue44-extended"

# (relative source path, verbatim needle) pairs backing every cited number.
CHECKS: list[tuple[str, str]] = [
    ("reports/statistical_profile.csv", "37.31583333333334"),
    ("reports/statistical_profile.csv", "1.2947296017947536"),
    ("reports/inference_results.md", "H = 61,534"),
    ("reports/inference_results.md", "ε² = 0,2065"),
    ("reports/inference_results.md", "t (HAC) = 1,611"),
    ("reports/inference_results.md", "−2,656"),
    ("reports/inference_results.md", "r (cặp) = −0,410"),
    ("reports/inference_results.md", "Cohen's d = 0,848"),
    ("reports/inference_results.md", "7,38·10⁻⁵"),
    ("reports/inference_results.md", "MDE ≈ 7,75"),
    ("reports/inference_results.md", "[−11,13; 3,05]"),
    ("reports/inference_results.md", "0,9403"),
    ("reports/inference_results.md", "size 30–55%"),
    ("reports/inference_montecarlo.csv", "independent"),
    ("reports/extended_reanalysis_comparison.md", "0.728 / 47.1"),
    ("reports/extended_reanalysis_comparison.md", "0.749 / 108.7"),
    ("reports/extended_reanalysis_comparison.md", "[0.119, 0.443]"),
    ("reports/extended_reanalysis_comparison.md", "2.171e-12"),
    ("reports/extended_reanalysis_comparison.md", "164.2"),
    ("reports/extended_inference_results.md", "238/756"),
    ("reports/extended_inference_results.md", "84/299"),
    ("reports/regression_results.md", "VN001_extended_80_20"),
    ("docs/regression_findings.md", "8.061"),
    ("docs/regression_findings.md", "223.27"),
    ("docs/regression_findings.md", "DW=0.2430"),
    ("docs/regression_findings.md", "JB=392.7"),
    ("docs/regression_findings.md", "LM=658.27"),
    ("docs/regression_findings.md", "6.07–7.29"),
    ("docs/regression_findings.md", "p = 0.0808"),
    ("docs/classification_findings.md", "[[1609, 27], [0, 666]]"),
    ("docs/classification_findings.md", "96.10%"),
    ("docs/classification_findings.md", "0.9985"),
    ("docs/classification_findings.md", "0.0134"),
    ("docs/classification_findings.md", "71.07%"),
    ("docs/classification_findings.md", "23/24"),
    ("docs/classification_findings.md", "630 giờ"),
    ("docs/classification_findings.md", "~5 ngày"),
    ("reports/classification_results.md", "h=24h — Full Feature Set | 2369"),
    ("reports/classification_results.md", "UNESTIMABLE (0 positives in Test)"),
    ("docs/leakage_audit.md", "SMOTE"),
    ("docs/issue44_dataset_contract.md", "7.324 km"),
    ("docs/issue44_dataset_contract.md", "2,040"),
    ("reports/issue44_legacy_vs_extended_comparison.md", "NO-GO"),
    ("reports/issue44_legacy_vs_extended_comparison.md", "1.85%"),
    ("reports/issue44_interpolation_evaluation.csv", "9.55"),
    ("reports/issue44_multiyear_eda_summary.csv", "VN003"),
    ("docs/issue50_reproducibility.md", "VN003"),
    ("reports/sensitivity_analysis.md", "technical_sensitivity_threshold"),
    ("reports/sensitivity_analysis.md", "-1.954"),
    ("reports/sensitivity_analysis.md", "0.1498"),
    ("reports/sensitivity_analysis.md", "-7.2891"),
    ("reports/sensitivity_analysis.md", "0.9433"),
    ("reports/data_scale_benchmark.md", "1.0453 MB"),
    ("reports/data_scale_benchmark.md", "10.6435 MB"),
    ("reports/data_scale_benchmark.md", "14.57×"),
    ("reports/data_scale_benchmark.md", "66.694"),
    ("docs/bias_assessment.md", "630 giờ"),
    ("docs/bias_assessment.md", "2.568 giờ"),
    ("docs/model_card.md", "VN001"),
    ("docs/project_charter.md", "SQ4"),
    ("docs/mentoring_feedback.md", "#"),
]

FIGURES = {
    "FIG-01": "figures/FIG-01.png", "FIG-02": "figures/FIG-02.png",
    "FIG-03": "figures/FIG-03.png", "FIG-04": "figures/FIG-04.png",
    "FIG-05": "figures/FIG-05.png", "FIG-06": "figures/FIG-06.png",
    "FIG-07": "figures/FIG-07.png",
    "FIG-01-EXT": "figures/FIG-01-extended-historical.png",
    "FIG-02-EXT": "figures/extended/FIG-02-extended.png",
    "FIG-03-EXT": "figures/extended/FIG-03-extended.png",
    "FIG-03B-EXT": "figures/extended/FIG-03b-winter-coverage.png",
    "REG-DIAG": "figures/regression_line_diagnostics.png",
    "PR": "figures/precision_recall_curve.png",
    "FI": "figures/feature_importance.png",
    "CAL": "figures/calibration_reliability.png",
}


def parse_args(desc: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--input-root", type=Path, default=REPO_ROOT,
                   help="Root holding reports/ and docs/ inputs (default: repo root).")
    p.add_argument("--output-dir", type=Path, default=REPO_ROOT / "reports",
                   help="Where HTML/PDF are written (default: <repo>/reports).")
    p.add_argument("--no-pdf", action="store_true", help="Write HTML only.")
    return p.parse_args()


def read_text(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def verify_sources(root: Path) -> None:
    """Fail the build if any cited artifact or verbatim needle is missing."""
    cache: dict[str, str] = {}
    missing: list[str] = []
    for rel, needle in CHECKS:
        if rel not in cache:
            path = root / rel
            if not path.exists():
                missing.append(f"MISSING FILE {rel}")
                cache[rel] = ""
                continue
            cache[rel] = path.read_text(encoding="utf-8")
        if cache[rel] and needle not in cache[rel]:
            missing.append(f"NEEDLE NOT FOUND in {rel}: {needle!r}")
    if missing:
        raise SystemExit("Source verification failed:\n  " + "\n  ".join(dict.fromkeys(missing)))
    print(f"[verify] {len(CHECKS)} (artifact, needle) checks passed against {root}")


def figure_dir_prefix(output_dir: Path) -> str:
    """Relative path from output_dir to REPO_ROOT/figures (posix)."""
    rel = os.path.relpath(REPO_ROOT / "figures", output_dir)
    return Path(rel).as_posix()


def fig_src(key: str, output_dir: Path) -> str:
    target = REPO_ROOT / FIGURES[key]
    if not target.exists():
        raise SystemExit(f"Figure missing: {target}")
    return Path(os.path.relpath(target, output_dir)).as_posix()


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    """Rows/headers are trusted HTML fragments."""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    if not CHROME.exists():
        raise SystemExit(f"Chrome not found at {CHROME}")
    cmd = [str(CHROME), "--headless", "--disable-gpu", "--no-pdf-header-footer",
           "--allow-file-access-from-files", "--virtual-time-budget=20000",
           f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
    subprocess.run(cmd, check=True, capture_output=True, timeout=240)
    if not pdf_path.exists() or pdf_path.read_bytes()[:5] != b"%PDF-":
        raise SystemExit(f"PDF render failed: {pdf_path}")


def pdf_page_count(pdf_path: Path) -> int:
    data = pdf_path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", data))


def report_pdf(pdf_path: Path) -> None:
    size = pdf_path.stat().st_size
    print(f"[pdf] {pdf_path} bytes={size} pages={pdf_page_count(pdf_path)}")
    if size < 500_000:
        print("[warn] PDF < 500 KB: embedded figures may not have loaded", file=sys.stderr)
