"""CLI entry point for Issue #14 Data Scale Benchmark & Ethics/Bias Audit.

Usage:
    py -3.14 scripts/run_issue14_audit.py
    py -3.14 scripts/run_issue14_audit.py --data-dir "C:\\path\\to\\data"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ethics_audit import run_bias_audit, run_data_scale_benchmark


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run Issue #14 Data Scale Benchmark (vs Spark) and 4-Hypothesis Bias Audit."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Read-only directory containing processed Parquet datasets (default: <repo>/data).",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPO_ROOT / "reports",
        help="Directory for existing metadata inputs and benchmark report outputs (default: <repo>/reports).",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=REPO_ROOT / "docs",
        help="Directory for bias_assessment.md output (default: <repo>/docs).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Number of repetitions for benchmark timings (default: 5).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Execute Issue #14 benchmark and bias audit."""
    args = parse_args(argv)
    data_dir = args.data_dir.resolve()
    reports_dir = args.reports_dir.resolve()
    docs_dir = args.docs_dir.resolve()

    bench_md = reports_dir / "data_scale_benchmark.md"
    bench_json = reports_dir / "data_scale_benchmark.json"
    bias_md = docs_dir / "bias_assessment.md"

    bench = run_data_scale_benchmark(
        data_dir=data_dir,
        output_md=bench_md,
        output_json=bench_json,
        repeats=args.repeats,
    )
    bias = run_bias_audit(
        data_dir=data_dir,
        reports_dir=reports_dir,
        output_md=bias_md,
    )

    ds_base = bench["datasets"]["baseline_vn001"]
    ds_ext = bench["datasets"]["extended_2022_2026"]
    print("[Issue #14] Data Scale Benchmark completed:")
    print(
        f"  Baseline VN001: Parquet={ds_base['storage']['parquet_snappy_mb']:.4f} MB, "
        f"CSV={ds_base['storage']['csv_mb']:.4f} MB, "
        f"RAM={ds_base['memory']['before_mb']:.4f} -> {ds_base['memory']['after_mb']:.4f} MB "
        f"(-{ds_base['memory']['reduction_pct']:.2f}%), "
        f"Workload={ds_base['workload']['naive_loop_ms']:.2f} -> {ds_base['workload']['vectorized_opt_ms']:.2f} ms "
        f"({ds_base['workload']['speedup_x']:.2f}x)"
    )
    print(
        f"  Extended 2022-2026: Parquet={ds_ext['storage']['parquet_snappy_mb']:.4f} MB, "
        f"CSV={ds_ext['storage']['csv_mb']:.4f} MB, "
        f"RAM={ds_ext['memory']['before_mb']:.4f} -> {ds_ext['memory']['after_mb']:.4f} MB "
        f"(-{ds_ext['memory']['reduction_pct']:.2f}%), "
        f"Workload={ds_ext['workload']['naive_loop_ms']:.2f} -> {ds_ext['workload']['vectorized_opt_ms']:.2f} ms "
        f"({ds_ext['workload']['speedup_x']:.2f}x)"
    )
    print(f"  Written: {bench_md}, {bench_json}")

    fog_ev = bias["sensor_bias"]["baseline_vn001_flag_evidence"]["seasonal"]
    overlap = bias["sensor_bias"]["inter_station_overlap"]
    print("[Issue #14] Bias Audit completed:")
    print(
        f"  Fog x Season F({fog_ev['f_df_num']}, {int(fog_ev['f_df_denom'])}) = "
        f"{fog_ev['f_statistic']:.4f}, p = {fog_ev['f_p_value']:.2e}"
    )
    print(
        f"  VN003 vs VN001 overlap = {overlap['overlap_hours']} h, "
        f"gap = {overlap['gap_hours']} h ({overlap['gap_days']} d), "
        f"distance = {overlap['inter_station_distance_km']} km"
    )
    print(f"  Written: {bias_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
