"""
Kiểm chứng Monte Carlo cho các phương pháp suy luận của Issue #11.

Đây là **kiểm chứng khoa học có chi phí** — tách khỏi regression test chạy mỗi
lần CI. Script đo tỷ lệ bác bỏ H₀ (sai lầm loại I) của từng phương pháp trên
nhiều **kịch bản dữ liệu** và ghi ra CSV để báo cáo dựng lại.

Cách dùng:
    python scripts/validate_inference_montecarlo.py --n-sim 1000
    python scripts/validate_inference_montecarlo.py --n-sim 200 --quick

Kết quả ghi vào `reports/inference_montecarlo.csv` (được commit) — notebook 05 và
`reports/inference_results.md` đọc lại tệp này, không chạy lại mô phỏng.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import inference as inf  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Kiểm chứng Monte Carlo W9")
    parser.add_argument("--n-sim", type=int, default=1_000, help="số lần mô phỏng mỗi kịch bản")
    parser.add_argument("--n-days", type=int, default=299, help="độ dài chuỗi mô phỏng")
    parser.add_argument("--n-bootstrap", type=int, default=200, help="số lặp null bootstrap")
    parser.add_argument("--seed", type=int, default=inf.BOOTSTRAP_SEED, help="seed")
    parser.add_argument(
        "--output", type=Path, default=None, help="đường dẫn CSV đầu ra"
    )
    parser.add_argument(
        "--quick", action="store_true", help="chạy nhanh (ít kịch bản) để thử"
    )
    args = parser.parse_args(argv)

    # Mặt nạ thiếu của dữ liệu thật — dùng cho kịch bản "missing_real_pattern".
    real_mask = None
    if inf.DEFAULT_DATA_PATH.exists():
        hourly = inf.load_analysis_frame()
        calendar = inf.build_daily_calendar(hourly)
        real_mask = ~np.isfinite(calendar.values)
        print(f"✓ Đọc mặt nạ thiếu thật: {int(real_mask.sum())}/{calendar.n_days} ngày thiếu")

    scenarios = None
    if args.quick:
        scenarios = ["independent", "ar1_strong", "missing_real_pattern"]

    print(
        f"→ Monte Carlo: n_sim={args.n_sim}, n_days={args.n_days}, "
        f"n_bootstrap={args.n_bootstrap}, seed={args.seed}"
    )
    started = time.time()
    result = inf.monte_carlo_validation(
        n_days=args.n_days,
        n_sim=args.n_sim,
        seed=args.seed,
        n_bootstrap=args.n_bootstrap,
        scenarios=scenarios,
        real_missing_mask=real_mask,
    )
    elapsed = time.time() - started

    path = inf.save_monte_carlo_csv(result, args.output)
    print(f"✓ Đã ghi {path} ({path.stat().st_size} bytes) sau {elapsed:.0f}s")

    header = f"{'kịch bản':<22}{'phép kiểm':<10}{'độc lập':>12}{'bootstrap':>12}{'HAC':>12}"
    print(header)
    print("-" * len(header))
    for scenario_key, scenario in result["scenarios"].items():
        for test_name, entry in scenario["tests"].items():
            def cell(suffix: str) -> str:
                key = f"rate_{suffix}"
                if key not in entry:
                    return "—"
                return (
                    f"{entry[key] * 100:5.1f}% "
                    f"[{entry[f'ci_low_{suffix}'] * 100:4.1f},"
                    f"{entry[f'ci_high_{suffix}'] * 100:4.1f}]"
                )

            print(
                f"{scenario_key:<22}{test_name:<10}"
                f"{cell('p_independence'):>12}{cell('p_bootstrap'):>12}{cell('p_hac'):>12}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
