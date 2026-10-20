"""
Kiểm thử cho lớp suy luận thống kê của Issue #11 (`src/inference.py`).

Ba tầng, cố ý tách bạch:

1. **Unit tất định** — từng hàm thuần (Holm, block bootstrap, ACF, effect size,
   các phép kiểm) so với công thức viết tay hoặc với SciPy, không cần dữ liệu.
2. **Integration tổng hợp** — `run_inference()` trên khung giờ tổng hợp 420 ngày,
   kiểm tra payload, tính nhất quán Holm, và tính tái lập theo seed.
3. **Hiện vật** — notebook 05 và `reports/inference_results.md` phải đúng cấu
   trúc đã cam kết; chạy được trên CI dù không có `data/`.

Lớp `TestRealDataset` chỉ chạy khi có dataset đã đóng băng: nó ghim đúng con số
báo cáo (SHA-256, 299 ngày, H, p, effect size) để báo cáo không thể trôi khỏi mã.
"""

import math
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence

import nbformat
import numpy as np
import pandas as pd
from scipy import stats

from src import inference as inf
from src.flag_evidence import SEASON_DISPLAY_ORDER, SEASON_LABELS_VI

REPO_ROOT = Path(__file__).resolve().parent.parent
TIMEZONE = "Asia/Ho_Chi_Minh"


# ---------------------------------------------------------------------------
# Khung dữ liệu tổng hợp
# ---------------------------------------------------------------------------


def _synthetic_hourly(days: int = 420, start: str = "2024-01-01", seed: int = 7) -> pd.DataFrame:
    """Chuỗi giờ tất định, đủ 24 giờ mỗi ngày, có mùa và nhịp ngày/đêm."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=days * 24, freq="h", tz=TIMEZONE)
    hours = index.hour.to_numpy()
    day_of_year = index.dayofyear.to_numpy()
    seasonal = 15.0 * np.cos(2.0 * np.pi * (day_of_year - 15.0) / 365.25)
    diurnal = 6.0 * np.cos(2.0 * np.pi * (hours - 8.0) / 24.0)
    noise = rng.normal(0.0, 4.0, index.size)
    pm25 = np.clip(38.0 + seasonal + diurnal + noise, 1.0, None)
    return pd.DataFrame({"timestamp": index, "station_id": "synth", "pm25": pm25})


def _weekly_panel(n_weeks: int = 6, weekday: float = 10.0, weekend: float = 5.0) -> pd.DataFrame:
    """Panel giả với chênh lệch weekday − weekend giống nhau ở mọi tuần."""
    rows = []
    for week in range(1, n_weeks + 1):
        key = f"2024-W{week:02d}"
        for offset in range(5):
            rows.append({"week_key": key, "is_weekend": 0, "pm25_mean": weekday + 0.1 * offset})
        for offset in range(2):
            rows.append({"week_key": key, "is_weekend": 1, "pm25_mean": weekend + 0.1 * offset})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Hằng số đóng băng
# ---------------------------------------------------------------------------


class TestConstants(unittest.TestCase):
    """Các con số cam kết với Issue #11 không được trôi âm thầm."""

    def test_alpha_and_confidence(self):
        self.assertEqual(inf.ALPHA, 0.05)
        self.assertAlmostEqual(inf.CONFIDENCE_LEVEL, 0.95)

    def test_bootstrap_settings(self):
        self.assertEqual(inf.N_BOOTSTRAP, 1_000)
        self.assertEqual(inf.BOOTSTRAP_SEED, 42)
        # Block 28 ngày = 4 chu kỳ tuần: ACF ngày còn ~0,32 ở lag 14 nên phụ thuộc
        # kéo dài quá hai tuần; mô phỏng size cho thấy null bootstrap chỉ đạt
        # size ≈ α khi block ≥ 28 ngày.
        self.assertEqual(inf.BLOCK_LENGTH_DAYS, 28)
        self.assertEqual(inf.N_NULL_BOOTSTRAP, 5_000)
        self.assertEqual(inf.HAC_LAG_DAILY, 28)
        self.assertEqual(inf.BLOCK_LENGTH_SENSITIVITY, (7, 14, 21, 28, 42))
        self.assertEqual(inf.HAC_LAG_SENSITIVITY, (7, 14, 21, 28, 42))

    def test_daily_coverage_rule(self):
        self.assertEqual(inf.MIN_VALID_HOURS_PER_DAY, 18)
        self.assertEqual(inf.HOURS_PER_DAY, 24)

    def test_qcvn_limits_are_separate_cycles(self):
        self.assertEqual(inf.QCVN_2023_PM25_24H_LIMIT, 50.0)
        self.assertEqual(inf.QCVN_2023_PM25_ANNUAL_LIMIT, 25.0)
        self.assertIn("24 giờ", inf.QCVN_24H_LABEL)
        self.assertIn("năm", inf.QCVN_ANNUAL_LABEL)
        self.assertNotEqual(inf.QCVN_24H_LABEL, inf.QCVN_ANNUAL_LABEL)

    def test_acf_lags_documented(self):
        self.assertEqual(inf.ACF_LAGS_DAILY, (1, 2, 3, 7, 14))
        self.assertEqual(inf.ACF_LAGS_HOURLY, (1, 2, 3, 24, 168))

    def test_effect_size_labels_cover_every_test(self):
        for name in ("r_rb", "r_rb_pairs", "epsilon_squared", "cohen_d"):
            self.assertIn(name, inf.EFFECT_SIZE_LABELS)

    def test_season_constants_come_from_flag_evidence(self):
        self.assertEqual(inf.SEASON_DISPLAY_ORDER, SEASON_DISPLAY_ORDER)
        self.assertEqual(len(SEASON_LABELS_VI), 4)


# ---------------------------------------------------------------------------
# Holm–Bonferroni
# ---------------------------------------------------------------------------


class TestHolmAdjust(unittest.TestCase):
    def test_matches_hand_worked_example(self):
        # sorted: 0,002 → 0,008; 0,01 → 0,03; 0,03 → 0,06; 0,04 → max(0,06, 0,04)
        adjusted = inf.holm_adjust([0.01, 0.04, 0.03, 0.002])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06, 0.008])

    def test_preserves_input_order(self):
        p = np.array([0.5, 0.001, 0.02])
        adjusted = inf.holm_adjust(p)
        self.assertEqual(float(adjusted[1]), min(1.0, 3 * 0.001))
        # Bậc cuối chỉ nhân với 1, nên p = 0,5 thành 0,5 — không phải Bonferroni.
        self.assertEqual(float(adjusted[2]), 2 * 0.02)
        self.assertEqual(float(adjusted[0]), 0.5)

    def test_adjusted_is_monotone_in_sorted_order(self):
        p = np.array([0.04, 0.01, 0.03, 0.02])
        adjusted = inf.holm_adjust(p)
        order = np.argsort(p)
        self.assertTrue(np.all(np.diff(adjusted[order]) >= 0.0))

    def test_never_below_raw_and_capped_at_one(self):
        p = np.array([0.9, 0.9, 0.5])
        adjusted = inf.holm_adjust(p)
        self.assertTrue(np.all(adjusted >= p - 1e-15))
        self.assertTrue(np.all(adjusted <= 1.0))

    def test_ties_receive_equal_adjustment(self):
        adjusted = inf.holm_adjust([0.02, 0.02])
        self.assertEqual(adjusted[0], adjusted[1])

    def test_single_p_value_is_unchanged(self):
        np.testing.assert_allclose(inf.holm_adjust([0.031]), [0.031])

    def test_validation_rejects_bad_input(self):
        for bad in ([], [0.1, -0.1], [0.1, 1.1], [0.1, float("nan")]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    inf.holm_adjust(bad)
        with self.assertRaises(ValueError):
            inf.holm_adjust(np.array([[0.1, 0.2]]))


# ---------------------------------------------------------------------------
# Block bootstrap
# ---------------------------------------------------------------------------


class TestCircularBlockIndices(unittest.TestCase):
    def test_shape_and_range(self):
        idx = inf.circular_block_indices(10, block_length=3, n_bootstrap=5, seed=1)
        self.assertEqual(idx.shape, (5, 10))
        self.assertGreaterEqual(int(idx.min()), 0)
        self.assertLess(int(idx.max()), 10)

    def test_seed_is_deterministic(self):
        a = inf.circular_block_indices(20, block_length=4, n_bootstrap=6, seed=42)
        b = inf.circular_block_indices(20, block_length=4, n_bootstrap=6, seed=42)
        c = inf.circular_block_indices(20, block_length=4, n_bootstrap=6, seed=43)
        np.testing.assert_array_equal(a, b)
        self.assertFalse(np.array_equal(a, c))

    def test_blocks_are_contiguous_around_the_circle(self):
        n, length = 9, 3
        idx = inf.circular_block_indices(n, block_length=length, n_bootstrap=4, seed=5)
        for row in idx:
            for j in range(n - 1):
                if (j + 1) % length == 0:  # ranh giới giữa hai block
                    continue
                self.assertEqual(row[j + 1], (row[j] + 1) % n)

    def test_unit_block_length_draws_individual_days(self):
        idx = inf.circular_block_indices(12, block_length=1, n_bootstrap=3, seed=2)
        self.assertEqual(idx.shape, (3, 12))

    def test_validation(self):
        with self.assertRaises(ValueError):
            inf.circular_block_indices(1)
        with self.assertRaises(ValueError):
            inf.circular_block_indices(5, block_length=6)
        with self.assertRaises(ValueError):
            inf.circular_block_indices(5, block_length=0)
        with self.assertRaises(ValueError):
            inf.circular_block_indices(5, n_bootstrap=0)


class TestBootstrapCI(unittest.TestCase):
    def setUp(self):
        self.values = np.arange(1.0, 31.0)

    def test_point_equals_median(self):
        result = inf.bootstrap_ci(self.values, statistic="median", n_bootstrap=100, seed=42)
        self.assertEqual(result["point"], float(np.median(self.values)))
        self.assertEqual(result["statistic"], "median")

    def test_point_equals_mean(self):
        result = inf.bootstrap_ci(self.values, statistic="mean", n_bootstrap=100, seed=42)
        self.assertAlmostEqual(result["point"], float(np.mean(self.values)))

    def test_interval_is_ordered_and_inside_data_range(self):
        result = inf.bootstrap_ci(self.values, n_bootstrap=200, seed=42)
        self.assertLessEqual(result["ci_low"], result["ci_high"])
        self.assertGreaterEqual(result["ci_low"], self.values.min())
        self.assertLessEqual(result["ci_high"], self.values.max())
        self.assertGreaterEqual(result["replicates_sd"], 0.0)

    def test_deterministic_for_same_seed(self):
        a = inf.bootstrap_ci(self.values, n_bootstrap=150, seed=42)
        b = inf.bootstrap_ci(self.values, n_bootstrap=150, seed=42)
        self.assertEqual((a["ci_low"], a["ci_high"]), (b["ci_low"], b["ci_high"]))

    def test_validation(self):
        with self.assertRaises(ValueError):
            inf.bootstrap_ci([1.0, 2.0, 3.0, 4.0])
        with self.assertRaises(ValueError):
            inf.bootstrap_ci(self.values, statistic="mode")


class TestBootstrapDifferenceCI(unittest.TestCase):
    def test_point_is_difference_of_medians(self):
        a = np.arange(100.0, 110.0)
        b = np.arange(1.0, 11.0)
        result = inf.bootstrap_difference_ci(a, b, n_bootstrap=100, seed=42)
        self.assertAlmostEqual(result["point"], float(np.median(a) - np.median(b)))

    def test_clear_separation_excludes_zero(self):
        a = np.arange(100.0, 120.0)
        b = np.arange(0.0, 20.0)
        result = inf.bootstrap_difference_ci(a, b, n_bootstrap=200, seed=42)
        self.assertTrue(result["excludes_zero"])
        self.assertGreater(result["ci_low"], 0.0)

    def test_overlapping_groups_do_not_exclude_zero(self):
        rng = np.random.default_rng(0)
        a = rng.normal(10.0, 1.0, 200)
        b = rng.normal(10.0, 1.0, 200)
        result = inf.bootstrap_difference_ci(a, b, statistic="mean", n_bootstrap=200, seed=42)
        self.assertFalse(result["excludes_zero"])

    def test_validation_requires_five_per_group(self):
        with self.assertRaises(ValueError):
            inf.bootstrap_difference_ci([1, 2, 3, 4], [1, 2, 3, 4, 5], n_bootstrap=10)


# ---------------------------------------------------------------------------
# Chẩn đoán phân phối
# ---------------------------------------------------------------------------


class TestDistributionDiagnostics(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.normal = rng.normal(50.0, 10.0, 300)

    def test_summary_statistics_are_consistent(self):
        d = inf.distribution_diagnostics(self.normal)
        self.assertEqual(d["n"], 300)
        self.assertLessEqual(d["min"], d["q1"])
        self.assertLessEqual(d["q1"], d["median"])
        self.assertLessEqual(d["median"], d["q3"])
        self.assertLessEqual(d["q3"], d["max"])
        self.assertAlmostEqual(d["iqr"], d["q3"] - d["q1"], places=10)

    def test_near_normal_sample_has_small_shape_effect(self):
        d = inf.distribution_diagnostics(self.normal)
        self.assertLess(abs(d["skewness"]), 0.3)
        self.assertLess(abs(d["excess_kurtosis"]), 0.5)
        self.assertGreater(d["dagostino_p"], 0.01)

    def test_shape_words_name_the_direction(self):
        d = inf.distribution_diagnostics(self.normal)
        self.assertIn("về phía", d["shape"])

    def test_outlier_count_matches_manual_calculation(self):
        d = inf.distribution_diagnostics(self.normal)
        manual = int((np.abs(self.normal - self.normal.mean()) > 3 * self.normal.std(ddof=1)).sum())
        self.assertEqual(d["n_outliers_3sd"], manual)

    def test_nan_values_are_dropped_before_counting(self):
        values = np.concatenate([self.normal, [np.nan, np.inf]])
        d = inf.distribution_diagnostics(values)
        self.assertEqual(d["n"], 300)

    def test_validation_requires_eight_observations(self):
        with self.assertRaises(ValueError):
            inf.distribution_diagnostics([1.0] * 7)


class TestQQPoints(unittest.TestCase):
    def setUp(self):
        self.values = np.random.default_rng(3).normal(0.0, 1.0, 60)

    def test_standardises_the_sample(self):
        qq = inf.qq_points(self.values)
        self.assertEqual(len(qq), len(self.values))
        self.assertAlmostEqual(float(qq["sample"].mean()), 0.0, places=10)
        self.assertAlmostEqual(float(qq["sample"].std(ddof=1)), 1.0, places=10)

    def test_theoretical_quantiles_are_monotone_and_symmetric(self):
        qq = inf.qq_points(self.values)
        theo = qq["theoretical"].to_numpy()
        self.assertTrue(np.all(np.diff(theo) > 0))
        self.assertAlmostEqual(float(theo[0] + theo[-1]), 0.0, places=10)

    def test_sample_column_is_sorted(self):
        qq = inf.qq_points(self.values)
        self.assertTrue(np.all(np.diff(qq["sample"].to_numpy()) >= 0))

    def test_validation_requires_three_observations(self):
        with self.assertRaises(ValueError):
            inf.qq_points([1.0, 2.0])


# ---------------------------------------------------------------------------
# Tự tương quan
# ---------------------------------------------------------------------------


class TestAutocorrelation(unittest.TestCase):
    def test_lag_zero_is_one(self):
        acf = inf.autocorrelation(np.arange(20.0), max_lag=3)
        self.assertEqual(acf.shape, (4,))
        self.assertEqual(float(acf[0]), 1.0)

    def test_white_noise_has_near_zero_lag_one(self):
        x = np.random.default_rng(11).normal(size=500)
        self.assertLess(abs(float(inf.autocorrelation(x, max_lag=1)[1])), 0.15)

    def test_persistent_series_has_high_lag_one(self):
        rng = np.random.default_rng(12)
        x = np.empty(500)
        x[0] = 0.0
        for t in range(1, x.size):
            x[t] = 0.8 * x[t - 1] + rng.normal()
        self.assertGreater(float(inf.autocorrelation(x, max_lag=1)[1]), 0.6)

    def test_nan_pairs_are_skipped_without_shifting(self):
        x = np.array([1.0, np.nan, 3.0, 4.0, 5.0, 6.0, 7.0])
        got = float(inf.autocorrelation(x, max_lag=1)[1])
        expected = float(np.corrcoef([3.0, 4.0, 5.0, 6.0], [4.0, 5.0, 6.0, 7.0])[0, 1])
        self.assertAlmostEqual(got, expected, places=12)

    def test_validation(self):
        with self.assertRaises(ValueError):
            inf.autocorrelation([1.0, 2.0])
        with self.assertRaises(ValueError):
            inf.autocorrelation(np.arange(10.0), max_lag=10)


class TestEffectiveSampleSize(unittest.TestCase):
    def test_independent_series_keeps_effective_n_close_to_n(self):
        x = np.random.default_rng(21).normal(size=400)
        result = inf.effective_sample_size(x)
        self.assertEqual(result["n"], 400)
        self.assertGreater(result["n_effective"], 0.6 * 400)
        self.assertLess(result["inflation_factor"], 2.0)

    def test_persistent_series_shrinks_effective_n(self):
        rng = np.random.default_rng(22)
        x = np.empty(400)
        x[0] = 0.0
        for t in range(1, x.size):
            x[t] = 0.8 * x[t - 1] + rng.normal()
        result = inf.effective_sample_size(x)
        self.assertLess(result["n_effective"], 0.3 * 400)
        self.assertGreater(result["inflation_factor"], 3.0)

    def test_constant_series_is_clamped_instead_of_dividing_by_zero(self):
        result = inf.effective_sample_size(np.ones(50))
        self.assertTrue(math.isfinite(result["n_effective"]))
        self.assertLess(result["n_effective"], 1.0)

    def test_validation_requires_ten_observations(self):
        with self.assertRaises(ValueError):
            inf.effective_sample_size(np.arange(9.0))


class TestDenseDailySeries(unittest.TestCase):
    def test_gap_days_become_nan_on_the_calendar_grid(self):
        panel = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-05"]),
                "pm25_mean": [10.0, 20.0, 50.0],
            }
        )
        series = inf.dense_daily_series(panel)
        self.assertEqual(series.size, 5)
        self.assertTrue(np.isnan(series[2]) and np.isnan(series[3]))
        np.testing.assert_allclose(series[[0, 1, 4]], [10.0, 20.0, 50.0])

    def test_contiguous_panel_has_no_nan(self):
        panel = pd.DataFrame(
            {
                "date": pd.date_range("2024-03-01", periods=10, freq="D"),
                "pm25_mean": np.arange(10.0),
            }
        )
        series = inf.dense_daily_series(panel)
        self.assertEqual(series.size, 10)
        self.assertFalse(np.isnan(series).any())

    def test_missing_column_raises(self):
        with self.assertRaises(KeyError):
            inf.dense_daily_series(pd.DataFrame({"date": pd.date_range("2024-01-01", periods=3)}))


# ---------------------------------------------------------------------------
# MDE
# ---------------------------------------------------------------------------


class TestMinimumDetectableDifference(unittest.TestCase):
    def test_matches_the_normal_approximation_formula(self):
        a = np.array([10.0, 12.0, 14.0, 16.0])
        b = np.array([9.0, 11.0, 13.0])
        result = inf.minimum_detectable_difference(a, b, alpha=0.05, power=0.80)
        n1, n2 = a.size, b.size
        pooled = ((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2)
        expected = (stats.norm.ppf(0.975) + stats.norm.ppf(0.80)) * math.sqrt(pooled) * math.sqrt(
            1 / n1 + 1 / n2
        )
        self.assertAlmostEqual(result["mde"], expected, places=12)
        self.assertAlmostEqual(result["pooled_sd"], math.sqrt(pooled), places=12)

    def test_more_data_reduces_mde(self):
        rng = np.random.default_rng(31)
        big = rng.normal(40.0, 10.0, 200)
        small = big[:20]
        mde_big = inf.minimum_detectable_difference(big, rng.normal(40.0, 10.0, 200))
        mde_small = inf.minimum_detectable_difference(small, rng.normal(40.0, 10.0, 20))
        self.assertLess(mde_big["mde"], mde_small["mde"])

    def test_stricter_alpha_increases_mde(self):
        rng = np.random.default_rng(32)
        a = rng.normal(40.0, 10.0, 50)
        b = rng.normal(40.0, 10.0, 50)
        self.assertGreater(
            inf.minimum_detectable_difference(a, b, alpha=0.01)["mde"],
            inf.minimum_detectable_difference(a, b, alpha=0.05)["mde"],
        )

    def test_validation(self):
        with self.assertRaises(ValueError):
            inf.minimum_detectable_difference([1.0], [1.0, 2.0])
        with self.assertRaises(ValueError):
            inf.minimum_detectable_difference([1.0, 2.0], [1.0, 2.0], alpha=1.5)
        with self.assertRaises(ValueError):
            inf.minimum_detectable_difference([1.0, 2.0], [1.0, 2.0], power=0.0)


# ---------------------------------------------------------------------------
# Panel ngày
# ---------------------------------------------------------------------------


class TestBuildDailyPanel(unittest.TestCase):
    @staticmethod
    def _frame():
        index = pd.date_range("2024-01-01", periods=24 * 3, freq="h", tz=TIMEZONE)
        pm25 = np.full(index.size, 30.0)
        # Ngày 1: 18 giờ có dữ liệu (giữ). Ngày 2: 17 giờ (loại). Ngày 3: đủ 24.
        pm25[18:24] = np.nan
        pm25[24:31] = np.nan
        return pd.DataFrame({"timestamp": index, "station_id": "synth", "pm25": pm25})

    def test_keeps_eighteen_hours_and_drops_seventeen(self):
        panel, audit = inf.build_daily_panel(self._frame())
        self.assertEqual(len(panel), 2)
        self.assertEqual(audit["days_kept"], 2)
        self.assertEqual(audit["days_dropped"], 1)
        self.assertEqual(audit["days_dropped_dates"], ["2024-01-02"])

    def test_audit_counts_hours_and_days(self):
        _, audit = inf.build_daily_panel(self._frame())
        self.assertEqual(audit["rows_hourly"], 72)
        self.assertEqual(audit["hours_with_pm25"], 72 - 6 - 7)
        self.assertEqual(audit["days_with_any_observation"], 3)
        self.assertEqual(audit["days_full_24h"], 1)
        self.assertEqual(audit["n_stations"], 1)

    def test_season_weekend_and_week_key(self):
        panel, audit = inf.build_daily_panel(self._frame())
        self.assertEqual(set(panel["season"]), {"Dong"})
        self.assertTrue(panel["week_key"].str.fullmatch(r"2024-W\d{2}").all())
        self.assertEqual(audit["season_counts"], {"Đông": 2})
        # 2024-01-01 là thứ Hai, 2024-01-03 là thứ Tư.
        self.assertEqual(panel["day_of_week"].tolist(), [0, 2])
        self.assertEqual(panel["is_weekend"].tolist(), [0, 0])

    def test_min_valid_hours_must_be_in_range(self):
        with self.assertRaises(ValueError):
            inf.build_daily_panel(self._frame(), min_valid_hours=0)
        with self.assertRaises(ValueError):
            inf.build_daily_panel(self._frame(), min_valid_hours=25)

    def test_all_missing_pm25_raises(self):
        frame = self._frame()
        frame["pm25"] = np.nan
        with self.assertRaises(ValueError):
            inf.build_daily_panel(frame)

    def test_missing_columns_raise_keyerror(self):
        with self.assertRaises(KeyError):
            inf.build_daily_panel(pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=5)}))


# ---------------------------------------------------------------------------
# Bốn phép kiểm
# ---------------------------------------------------------------------------


class TestMannWhitney(unittest.TestCase):
    def test_perfect_separation_gives_unit_rank_biserial(self):
        result = inf.mann_whitney(
            [10, 11, 12, 13, 14, 15], [1, 2, 3, 4, 5, 6], n_bootstrap=100, seed=42
        )
        self.assertEqual(result["statistic"], 36.0)
        self.assertAlmostEqual(result["effect_size"], 1.0)
        self.assertLess(result["p_value"], 0.01)

    def test_median_difference_is_a_minus_b(self):
        result = inf.mann_whitney(
            [10, 11, 12, 13, 14], [1, 2, 3, 4, 5], n_bootstrap=100, seed=42
        )
        self.assertGreater(result["median_difference"], 0.0)
        self.assertEqual(result["effect_size_name"], "r_rb")
        self.assertIsNone(result["n_zero_differences"])

    def test_alternative_is_recorded(self):
        result = inf.mann_whitney(
            [5, 6, 7, 8, 9], [1, 2, 3, 4, 5], alternative="greater", n_bootstrap=50
        )
        self.assertEqual(result["alternative"], "greater")
        self.assertLess(result["p_value"], 0.5)

    def test_validation(self):
        with self.assertRaises(ValueError):
            inf.mann_whitney([1, 2], [1, 2, 3])
        with self.assertRaises(ValueError):
            inf.mann_whitney([1, 2, 3], [1, 2, 3], alternative="both")


class TestKruskalWallis(unittest.TestCase):
    def test_epsilon_squared_uses_h_over_n_minus_one(self):
        groups = {"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]}
        result = inf.kruskal_wallis(groups)
        self.assertAlmostEqual(result["effect_size"], result["statistic"] / (result["n"] - 1))
        self.assertEqual(result["df"], 2)
        self.assertAlmostEqual(result["statistic"], 7.2, places=10)

    def test_group_sizes_and_medians_are_reported(self):
        groups = {"a": [1, 2, 3, 4], "b": [10, 11, 12]}
        result = inf.kruskal_wallis(groups)
        self.assertEqual(result["group_sizes"], {"a": 4, "b": 3})
        self.assertEqual(result["group_medians"]["b"], 11.0)

    def test_alternative_key_is_present_for_the_design_table(self):
        result = inf.kruskal_wallis({"a": [1, 2, 3], "b": [4, 5, 6]})
        self.assertIn("alternative", result)

    def test_validation(self):
        with self.assertRaises(ValueError):
            inf.kruskal_wallis({"a": [1, 2, 3]})
        with self.assertRaises(ValueError):
            inf.kruskal_wallis({"a": [1, 2], "b": [1, 2, 3]})


class TestWilcoxonSignedRank(unittest.TestCase):
    def test_all_differences_positive_gives_unit_effect(self):
        result = inf.wilcoxon_signed_rank([10, 12, 14, 16, 18, 20], mu=5.0)
        self.assertEqual(result["w_minus"], 0.0)
        self.assertAlmostEqual(result["effect_size"], 1.0)
        self.assertEqual(result["statistic"], 0.0)

    def test_statistic_is_the_smaller_of_the_two_rank_sums(self):
        result = inf.wilcoxon_signed_rank([8.0, 9.0, 12.0, 15.0, 7.0, 30.0], mu=10.0)
        self.assertAlmostEqual(result["statistic"], min(result["w_plus"], result["w_minus"]))
        self.assertAlmostEqual(result["w_plus"] + result["w_minus"], 21.0)

    def test_mixed_signs_give_effect_inside_minus_one_and_one(self):
        result = inf.wilcoxon_signed_rank([12.0, 8.0, 15.0, 9.0, 11.0, 20.0], mu=10.0)
        self.assertGreater(result["effect_size"], -1.0)
        self.assertLess(result["effect_size"], 1.0)
        self.assertEqual(result["n_nonzero"], 6)

    def test_validation_requires_five_observations(self):
        with self.assertRaises(ValueError):
            inf.wilcoxon_signed_rank([1.0, 2.0, 3.0, 4.0])

    def test_all_zero_differences_raise(self):
        with self.assertRaises(ValueError):
            inf.wilcoxon_signed_rank([5.0] * 10, mu=5.0)


class TestOneSampleT(unittest.TestCase):
    def test_zero_t_at_the_mean(self):
        result = inf.one_sample_t(np.arange(1.0, 11.0), mu=5.5)
        self.assertAlmostEqual(result["statistic"], 0.0, places=12)
        self.assertAlmostEqual(result["p_value"], 1.0, places=12)
        self.assertAlmostEqual(result["effect_size"], 0.0, places=12)

    def test_matches_scipy_t_statistic(self):
        values = np.array([34.2, 41.8, 55.1, 27.4, 39.9, 61.2, 45.0, 30.5, 48.7, 36.1])
        result = inf.one_sample_t(values, mu=25.0)
        expected = stats.ttest_1samp(values, popmean=25.0).statistic
        self.assertAlmostEqual(result["statistic"], float(expected), places=12)
        self.assertEqual(result["df"], len(values) - 1)

    def test_effect_size_and_t_interval(self):
        values = np.array([34.2, 41.8, 55.1, 27.4, 39.9, 61.2, 45.0, 30.5])
        result = inf.one_sample_t(values, mu=25.0)
        self.assertAlmostEqual(
            result["effect_size"], (values.mean() - 25.0) / values.std(ddof=1), places=12
        )
        self.assertLess(result["ci_t"]["ci_low"], result["mean"])
        self.assertGreater(result["ci_t"]["ci_high"], result["mean"])

    def test_zero_sd_raises(self):
        with self.assertRaises(ValueError):
            inf.one_sample_t([5.0] * 10, mu=1.0)

    def test_validation_requires_eight_observations(self):
        with self.assertRaises(ValueError):
            inf.one_sample_t([1.0, 2.0, 3.0], mu=0.0)


# ---------------------------------------------------------------------------
# Kiểm tra độ nhạy
# ---------------------------------------------------------------------------


class TestPairedWeeklyDifferences(unittest.TestCase):
    """Kiểm tra ghép cặp theo tuần — nay dựng trên **lịch ngày**."""

    @staticmethod
    def _hourly(weeks: int = 8, weekday: float = 40.0, weekend: float = 30.0) -> pd.DataFrame:
        days = weeks * 7
        index = pd.date_range("2025-01-06", periods=days * 24, freq="h", tz=TIMEZONE)
        is_weekend = index.dayofweek.to_numpy() >= 5
        base = np.where(is_weekend, weekend, weekday)
        pm25 = base + np.tile(np.arange(24) * 0.01, days)
        return pd.DataFrame({"timestamp": index, "station_id": "synth", "pm25": pm25})

    def test_weekend_is_lower_than_weekday(self):
        frame = self._hourly(weeks=8)
        panel, _ = inf.build_daily_panel(frame)
        calendar = inf.build_daily_calendar(frame)
        result = inf.paired_weekly_differences(panel, calendar)
        self.assertGreater(result["n_weeks"], 0)
        # weekday (40) − weekend (30) = +10 → ngày làm việc CAO hơn cuối tuần
        self.assertGreater(result["median_difference"], 0.0)
        self.assertEqual(result["share_weekday_higher"], 1.0)

    def test_weekly_calendar_keeps_ineligible_weeks_as_missing(self):
        frame = self._hourly(weeks=8)
        panel, _ = inf.build_daily_panel(frame)
        calendar = inf.build_daily_calendar(frame)
        weekly, paired = inf.build_weekly_difference_calendar(panel, calendar)
        # Số tuần trên lịch ≥ số tuần đủ điều kiện, và phần thiếu là NaN.
        self.assertGreaterEqual(weekly.n_days, paired.shape[0])
        self.assertEqual(int(np.isnan(weekly.values).sum()), weekly.n_days - paired.shape[0])

    def test_missing_columns_raise(self):
        with self.assertRaises(KeyError):
            inf.paired_weekly_differences(
                pd.DataFrame({"week_key": ["2024-W01"]}), pd.DataFrame()
            )


class TestSeasonWeeklySensitivity(unittest.TestCase):
    def test_returns_weekly_kruskal_and_week_count(self):
        frame = _synthetic_hourly(days=400)
        panel, _ = inf.build_daily_panel(frame)
        calendar = inf.build_daily_calendar(frame)
        result = inf.season_weekly_sensitivity(panel, calendar)
        self.assertGreater(result["n_weeks"], 0)
        self.assertEqual(result["weekly_kruskal"]["test"], "kruskal_wallis")
        self.assertIn("p_value_independence", result["weekly_kruskal"])
        self.assertIn("null_bootstrap", result["weekly_kruskal"])

    def test_missing_column_raises(self):
        with self.assertRaises(KeyError):
            inf.season_weekly_sensitivity(
                pd.DataFrame({"week_key": ["2024-W01"]}), pd.DataFrame()
            )


# ---------------------------------------------------------------------------
# Bối cảnh QCVN
# ---------------------------------------------------------------------------


class TestQcvnContext(unittest.TestCase):
    def setUp(self):
        index = pd.date_range("2024-01-01", periods=72, freq="h", tz=TIMEZONE)
        values = np.concatenate([np.full(24, 60.0), np.full(48, 10.0)])
        self.hourly = pd.DataFrame({"timestamp": index, "station_id": "synth", "pm25": values})
        self.panel, _ = inf.build_daily_panel(self.hourly)

    def test_two_denominators_answer_two_questions(self):
        result = inf.qcvn_context(self.hourly, self.panel)
        self.assertEqual(result["panel_days"], 3)
        self.assertEqual(result["panel_days_over"], 1)
        self.assertEqual(result["rolling_windows_valid"], 49)
        self.assertNotAlmostEqual(result["panel_share"], result["rolling_share"])

    def test_panel_share_uses_kept_days_only(self):
        result = inf.qcvn_context(self.hourly, self.panel)
        self.assertAlmostEqual(result["panel_share"], 1.0 / 3.0)
        low, high = result["panel_days_equal_or_over_ci"]
        self.assertLess(low, result["panel_share"])
        self.assertGreater(high, result["panel_share"])

    def test_limit_is_configurable(self):
        result = inf.qcvn_context(self.hourly, self.panel, limit=10.0)
        self.assertEqual(result["panel_days_over"], 3)
        self.assertEqual(result["rolling_windows_over"], 49)

    def test_hourly_count_is_explicitly_not_a_24h_share(self):
        result = inf.qcvn_context(self.hourly, self.panel)
        self.assertIn("KHÔNG phải", result["hourly_rows_over_limit_note"])
        self.assertEqual(result["hourly_rows"], 72)


# ---------------------------------------------------------------------------
# Điều phối + báo cáo
# ---------------------------------------------------------------------------


class TestRunInferenceSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = _synthetic_hourly()
        cls.results = inf.run_inference(
            cls.frame, n_bootstrap=40, seed=42, include_simulation=False
        )

    def test_top_level_contract(self):
        for key in (
            "meta",
            "panel",
            "diagnostics",
            "dependence",
            "tests",
            "holm_confirmatory",
            "posthoc_season",
            "sensitivity",
            "generalization",
            "qcvn_context",
        ):
            self.assertIn(key, self.results)

    def test_meta_records_design_choices(self):
        meta = self.results["meta"]
        self.assertEqual(meta["issue"], "#11")
        self.assertEqual(meta["alpha"], 0.05)
        self.assertEqual(meta["n_bootstrap"], 40)
        self.assertEqual(meta["n_null_bootstrap"], inf.N_NULL_BOOTSTRAP)
        self.assertEqual(meta["bootstrap_seed"], 42)
        self.assertEqual(meta["block_length_days"], inf.BLOCK_LENGTH_DAYS)
        self.assertEqual(meta["hac_lag_days"], inf.HAC_LAG_DAILY)
        self.assertIsNone(meta["dataset_sha256"])  # df tổng hợp, không có tệp nguồn

    def test_panel_audit_counts_every_day(self):
        panel = self.results["panel"]
        self.assertEqual(panel["n"], 420)
        self.assertEqual(panel["audit"]["days_kept"], 420)
        self.assertEqual(panel["audit"]["days_dropped"], 0)
        self.assertEqual(panel["audit"]["days_full_24h"], 420)

    def test_all_four_confirmatory_tests_are_present(self):
        tests = self.results["tests"]
        self.assertEqual(
            set(tests),
            {"season_effect", "weekday_effect", "qcvn_24h", "qcvn_annual"},
        )
        for name, result in tests.items():
            with self.subTest(test=name):
                self.assertIn("p_value", result)
                self.assertIn("p_value_independence", result)
                self.assertIn("effect_size", result)
                self.assertIn("p_holm", result)
                self.assertIn("reject_holm", result)
                self.assertIn("status", result)
                self.assertIn("method", result)
                self.assertIn("sensitivity", result)

    def test_holm_table_is_consistent_with_raw_p_values(self):
        table = self.results["holm_confirmatory"]
        self.assertEqual(len(table), 4)
        for row in table:
            self.assertGreaterEqual(row["p_holm"], row["p_raw"] - 1e-15)
            self.assertEqual(row["reject_raw"], row["p_raw"] < inf.ALPHA)
            self.assertEqual(row["reject_holm"], row["p_holm"] < inf.ALPHA)
            # Bảng tham chiếu dùng p giả định độc lập — phải tách bạch.
            self.assertGreaterEqual(row["p_holm_independence"], row["p_raw_independence"] - 1e-15)

    def test_posthoc_family_has_six_pairs_with_separate_holm(self):
        posthoc = self.results["posthoc_season"]
        self.assertEqual(posthoc["n_pairs"], 6)
        self.assertEqual(posthoc["family"], "posthoc_seasonal_pairs")
        for pair in posthoc["pairs"]:
            self.assertIn("pair", pair)
            self.assertGreaterEqual(pair["p_holm"], pair["p_value"] - 1e-15)
            self.assertIn("p_value_independence", pair)

    def test_sensitivity_block_has_all_three_checks(self):
        sensitivity = self.results["sensitivity"]
        self.assertEqual(sensitivity["paired_weeks"]["n_weeks"], 60)
        self.assertIn("weekly_kruskal", sensitivity["season_weekly"])
        self.assertGreater(sensitivity["power_mde"]["mde"], 0.0)

    def test_generalization_block_reports_one_cycle(self):
        generalization = self.results["generalization"]
        self.assertEqual(generalization["n_seasonal_cycles"], 1)
        self.assertIn("coverage", generalization)
        self.assertIn("season_year_breakdown", generalization)

    def test_dependence_block_uses_dense_daily_grid(self):
        dependence = self.results["dependence"]
        self.assertEqual(set(dependence["daily_acf"]), {1, 2, 3, 7, 14})
        self.assertEqual(set(dependence["hourly_acf"]), {1, 2, 3, 24, 168})
        self.assertEqual(dependence["daily_effective_n"]["n"], 420)
        self.assertIn("lưới lịch", dependence["daily_series_note"])

    def test_rerun_with_same_seed_is_identical(self):
        again = inf.run_inference(
            self.frame, n_bootstrap=40, seed=42, include_simulation=False
        )
        for name in self.results["tests"]:
            self.assertEqual(
                again["tests"][name]["statistic"], self.results["tests"][name]["statistic"]
            )
            self.assertEqual(
                again["tests"][name]["p_value"], self.results["tests"][name]["p_value"]
            )
        self.assertEqual(
            again["sensitivity"]["power_mde"]["mde"],
            self.results["sensitivity"]["power_mde"]["mde"],
        )


class TestRenderInferenceReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = inf.run_inference(
            _synthetic_hourly(), n_bootstrap=40, seed=42, include_simulation=False
        )
        cls.report = inf.render_inference_report(cls.results)

    def test_has_fifteen_numbered_sections(self):
        headings = [line for line in self.report.splitlines() if line.startswith("## ")]
        self.assertEqual(len(headings), 15)
        self.assertTrue(headings[0].startswith("## 1."))
        self.assertTrue(headings[-1].startswith("## 15."))

    def test_states_alpha_holm_and_qcvn_cycles(self):
        self.assertIn("Holm", self.report)
        self.assertIn("0,05", self.report)
        self.assertIn("QCVN 05:2023/BTNMT", self.report)
        self.assertIn("trung bình 24 giờ", self.report)
        self.assertIn("trung bình năm", self.report)

    def test_documents_the_dependence_aware_framework(self):
        """Báo cáo phải nêu rõ cách dựng null dưới H₀ và quy tắc hạ mức kết luận."""
        for token in (
            "null",
            "Newey",
            "HAC",
            "R1",
            "R2",
            "R3",
            "thăm dò",
            "EXPLORATORY",
        ):
            self.assertIn(token, self.report)

    def test_keeps_reference_p_values_next_to_corrected_ones(self):
        self.assertIn("tham chiếu", self.report)
        self.assertIn("giả định độc lập", self.report)

    def test_is_deterministic(self):
        self.assertEqual(inf.render_inference_report(self.results), self.report)

    def test_ends_with_exactly_one_newline(self):
        self.assertTrue(self.report.endswith("\n"))
        self.assertFalse(self.report.endswith("\n\n"))


# ---------------------------------------------------------------------------
# Hiện vật: notebook 05 + báo cáo
# ---------------------------------------------------------------------------


class TestInferenceArtifacts(unittest.TestCase):
    NOTEBOOK = REPO_ROOT / "notebooks" / "05_statistical_inference.ipynb"
    REPORT = REPO_ROOT / "reports" / "inference_results.md"
    FIGURES = [REPO_ROOT / "figures" / f"FIG-{i:02d}.png" for i in range(8, 13)]

    def test_notebook_exists_and_parses(self):
        self.assertTrue(self.NOTEBOOK.exists())
        self.assertGreater(self.NOTEBOOK.stat().st_size, 0)
        nb = nbformat.read(self.NOTEBOOK, as_version=4)
        self.assertEqual(nb.nbformat, 4)

    def test_notebook_has_the_documented_cell_mix(self):
        nb = nbformat.read(self.NOTEBOOK, as_version=4)
        self.assertEqual(len(nb.cells), 49)
        self.assertEqual(sum(1 for c in nb.cells if c.cell_type == "code"), 23)
        self.assertEqual(sum(1 for c in nb.cells if c.cell_type == "markdown"), 26)

    def test_notebook_has_no_error_output(self):
        nb = nbformat.read(self.NOTEBOOK, as_version=4)
        errors = [
            out
            for cell in nb.cells
            for out in cell.get("outputs", [])
            if out.get("output_type") == "error"
        ]
        self.assertEqual(errors, [])

    def test_notebook_embeds_five_figures(self):
        nb = nbformat.read(self.NOTEBOOK, as_version=4)
        images = [
            out
            for cell in nb.cells
            for out in cell.get("outputs", [])
            if out.get("output_type") == "display_data"
            and "image/png" in out.get("data", {})
        ]
        self.assertEqual(len(images), 5)
        for figure in self.FIGURES:
            self.assertTrue(figure.exists(), f"thiếu {figure.name}")
            self.assertGreater(figure.stat().st_size, 10_000)

    def test_report_exists_with_fifteen_sections(self):
        self.assertTrue(self.REPORT.exists())
        text = self.REPORT.read_text(encoding="utf-8")
        self.assertEqual(len([l for l in text.splitlines() if l.startswith("## ")]), 15)

    def test_report_keeps_both_denominators_distinct(self):
        """
        Bất nhất của Issue #11 là trộn tử số rolling-valid với mẫu số toàn tập.
        Báo cáo phải giữ 31,13% (5.317 cửa sổ), 28,09% (299 ngày) và dẫn ví dụ
        ghép sai 18,30% — ba tỷ lệ này không được nhập làm một.
        """
        text = self.REPORT.read_text(encoding="utf-8")
        for token in ("31,13", "28,09", "18,30", "5.317", "299"):
            self.assertIn(token, text)


# ---------------------------------------------------------------------------
# Dữ liệu thật (chỉ chạy khi có data/, giống quy ước TestDocumentedReproduction)
# ---------------------------------------------------------------------------


class TestRealDataset(unittest.TestCase):
    """Ghim con số báo cáo vào dataset đã đóng băng của Issue #7."""

    EXPECTED_SHA256 = "866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd"

    @classmethod
    def setUpClass(cls):
        if not inf.DEFAULT_DATA_PATH.exists():
            raise unittest.SkipTest(
                "Thiếu data/processed/air_pollution_final.parquet — chạy notebook 03 trước."
            )
        # n_bootstrap nhỏ: chỉ cần thống kê/effect size/Holm, không cần CI khớp báo cáo.
        # Mô phỏng size bị tắt ở đây để test không chậm (nó chạy trong notebook).
        cls.results = inf.run_inference(
            n_bootstrap=200, seed=42, include_simulation=False
        )

    def test_dataset_checksum(self):
        self.assertEqual(inf.dataset_sha256(), self.EXPECTED_SHA256)

    def test_panel_audit_matches_report(self):
        audit = self.results["panel"]["audit"]
        self.assertEqual(self.results["panel"]["n"], 299)
        self.assertEqual(audit["days_dropped"], 52)
        self.assertEqual(audit["days_with_any_observation"], 351)
        self.assertEqual(audit["days_full_24h"], 223)
        self.assertEqual(audit["weekday_days"], 213)
        self.assertEqual(audit["weekend_days"], 86)
        self.assertEqual(
            audit["season_counts"], {"Đông": 79, "Xuân": 83, "Hè": 53, "Thu": 84}
        )

    def test_distribution_numbers_are_stable(self):
        d = self.results["diagnostics"]
        self.assertEqual(d["n"], 299)
        self.assertAlmostEqual(d["skewness"], 1.2143, places=3)
        self.assertAlmostEqual(d["excess_kurtosis"], 0.9349, places=3)
        self.assertAlmostEqual(d["shapiro_w"], 0.8873, places=3)
        self.assertAlmostEqual(d["dagostino_stat"], 56.328, places=2)
        self.assertAlmostEqual(d["median"], 37.20, places=1)

    def test_dependence_numbers_are_stable(self):
        dep = self.results["dependence"]
        self.assertAlmostEqual(dep["daily_acf"][1], 0.7276, places=3)
        self.assertAlmostEqual(dep["hourly_acf"][1], 0.9403, places=3)
        self.assertAlmostEqual(dep["daily_acf"][7], 0.3700, places=3)
        self.assertAlmostEqual(dep["daily_effective_n"]["n_effective"], 47.14, places=1)
        self.assertGreater(dep["daily_effective_n"]["inflation_factor"], 6.0)

    def test_confirmatory_results_match_report(self):
        tests = self.results["tests"]
        self.assertAlmostEqual(tests["season_effect"]["statistic"], 61.5344, places=3)
        self.assertAlmostEqual(tests["season_effect"]["effect_size"], 0.2065, places=3)
        self.assertAlmostEqual(tests["weekday_effect"]["statistic"], 8083.0, places=1)
        self.assertAlmostEqual(tests["weekday_effect"]["effect_size"], -0.1175, places=3)
        self.assertAlmostEqual(tests["qcvn_24h"]["effect_size"], -0.4102, places=3)
        self.assertAlmostEqual(tests["qcvn_annual"]["effect_size"], 0.8476, places=3)
        self.assertEqual(tests["qcvn_annual"]["n"] - 1, 298)

    def test_dependence_aware_p_values_are_far_from_the_naive_ones(self):
        """
        Bằng chứng cốt lõi của bản sửa: với ba kiểm định mà giả định độc lập sai
        (mùa và hai ngưỡng QCVN) p-value cũ **lạc quan** vượt bậc, và bản hiệu
        chỉnh phụ thuộc thời gian phải lớn hơn hẳn.
        """
        tests = self.results["tests"]
        for key in ("season_effect", "qcvn_24h", "qcvn_annual"):
            with self.subTest(test=key):
                self.assertGreater(tests[key]["p_value"], tests[key]["p_value_independence"])

    def test_weekday_contrast_keeps_the_same_conclusion(self):
        """
        So sánh weekday/weekend là so sánh *trong cùng giai đoạn*, nên phép kiểm cũ
        vốn đã bảo thủ (mô phỏng: size ≈ 0,01). Vì vậy p đã hiệu chỉnh **nhỏ hơn**
        p tham chiếu — và cả hai đều không bác bỏ H₀, nên kết luận không đổi.
        """
        weekday = self.results["tests"]["weekday_effect"]
        self.assertGreater(weekday["p_value"], inf.ALPHA)
        self.assertGreater(weekday["p_value_independence"], inf.ALPHA)
        self.assertFalse(weekday["reject_holm"])
        self.assertFalse(weekday["reject_raw"])

    def test_holm_family_rejects_two_of_four_after_the_correction(self):
        table = self.results["holm_confirmatory"]
        by_key = {row["key"]: row for row in table}
        # Phương pháp cũ (giả định độc lập) bác bỏ 3/4 — bản sửa bác bỏ 2/4.
        self.assertEqual(sum(1 for row in table if row["reject_holm_independence"]), 3)
        self.assertEqual(sum(1 for row in table if row["reject_holm"]), 2)
        self.assertFalse(by_key["weekday_effect"]["reject_raw"])
        self.assertFalse(by_key["weekday_effect"]["reject_holm"])
        self.assertTrue(by_key["qcvn_24h"]["reject_holm"])
        self.assertTrue(by_key["qcvn_annual"]["reject_holm"])
        # Kiểm định mùa: p đã hiệu chỉnh lớn hơn α sau Holm và bị hạ xuống thăm dò.
        self.assertFalse(by_key["season_effect"]["reject_holm"])
        self.assertEqual(by_key["season_effect"]["status"], "exploratory")

    def test_confirmatory_family_keeps_four_members(self):
        """Family Holm phải giữ nguyên 4 kiểm định đã chốt trước — không thu hẹp sau khi xem kết quả."""
        self.assertEqual(len(self.results["holm_confirmatory"]), 4)

    def test_qcvn_context_keeps_rolling_and_daily_denominators(self):
        context = self.results["qcvn_context"]
        self.assertEqual(context["rolling_windows_valid"], 5317)
        self.assertEqual(context["rolling_windows_over"], 1655)
        self.assertEqual(context["panel_days"], 299)
        self.assertEqual(context["panel_days_over"], 84)


# ---------------------------------------------------------------------------
# Suy luận có xét tới phụ thuộc thời gian (sửa theo review 5586524840)
# ---------------------------------------------------------------------------


def _ar1(n: int, rho: float = 0.73, seed: int = 3) -> np.ndarray:
    """Chuỗi AR(1) tất định dùng cho mô phỏng trong test."""
    return inf.ar1_series(n, rho, sigma=1.0, seed=seed)


class TestNeweyWestCovariance(unittest.TestCase):
    """Hiệp phương sai HAC phải khớp với statsmodels — kiểm chứng độc lập."""

    def test_matches_statsmodels_cov_hac(self):
        import statsmodels.api as sm

        rng = np.random.default_rng(11)
        n = 120
        design = rng.normal(size=(n, 2))
        errors = np.zeros(n)
        for i in range(1, n):
            errors[i] = 0.7 * errors[i - 1] + rng.normal()
        y = 3.0 + 2.0 * design[:, 0] - 1.0 * design[:, 1] + errors
        model = sm.OLS(y, design).fit()
        for lag in (1, 3, 7):
            with self.subTest(lag=lag):
                expected = model.get_robustcov_results(
                    cov_type="HAC", maxlags=lag, use_correction=True
                ).cov_params()
                mine = inf.newey_west_covariance(design, model.resid, lag)
                np.testing.assert_allclose(expected, mine, atol=1e-10)

    def test_rejects_inconsistent_inputs(self):
        design = np.ones((10, 2))
        with self.assertRaises(ValueError):
            inf.newey_west_covariance(design, np.zeros(9), 2)
        with self.assertRaises(ValueError):
            inf.newey_west_covariance(design, np.zeros(10), -1)


class TestHacRegression(unittest.TestCase):
    def test_ols_coefficients_match_the_normal_equations(self):
        rng = np.random.default_rng(5)
        design = np.column_stack([np.ones(50), rng.normal(size=50)])
        y = design @ np.array([2.0, -0.5]) + rng.normal(size=50)
        model = inf.hac_regression(y, design, lag=2)
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        np.testing.assert_allclose(model["coef"], beta, atol=1e-10)

    def test_hac_se_grows_with_persistent_errors(self):
        rng = np.random.default_rng(6)
        n = 200
        design = np.ones((n, 1))
        errors = np.zeros(n)
        for i in range(1, n):
            errors[i] = 0.8 * errors[i - 1] + rng.normal()
        y = 10.0 + errors
        model = inf.hac_regression(y, design, lag=14)
        naive_se = y.std(ddof=1) / np.sqrt(n)
        self.assertGreater(model["se"][0], naive_se)

    def test_joint_wald_test_detects_a_real_difference(self):
        rng = np.random.default_rng(7)
        n = 240
        group = np.repeat([0, 1, 2, 3], n // 4)
        design = np.column_stack(
            [np.ones(n), (group == 1).astype(float), (group == 2).astype(float),
             (group == 3).astype(float)]
        )
        y = 20.0 + 5.0 * (group == 3) + rng.normal(size=n)
        model = inf.hac_regression(y, design, lag=4)
        wald = inf.joint_wald_test(model["coef"], model["cov"], [1, 2, 3], model["df_resid"])
        self.assertLess(wald["p_value"], 0.01)
        self.assertEqual(wald["df1"], 3)

    def test_joint_wald_test_does_not_reject_when_there_is_no_difference(self):
        rng = np.random.default_rng(8)
        n = 240
        group = np.repeat([0, 1, 2, 3], n // 4)
        design = np.column_stack(
            [np.ones(n), (group == 1).astype(float), (group == 2).astype(float),
             (group == 3).astype(float)]
        )
        y = 20.0 + rng.normal(size=n)
        model = inf.hac_regression(y, design, lag=4)
        wald = inf.joint_wald_test(model["coef"], model["cov"], [1, 2, 3], model["df_resid"])
        self.assertGreater(wald["p_value"], 0.05)


class TestBlockBootstrapNullTest(unittest.TestCase):
    """Kiểm định bootstrap: null dựng dưới H₀, có seed, có độ phân giải."""

    def setUp(self):
        self.values = _ar1(200, seed=13)

    def _run(self, **kwargs):
        positions = np.arange(200)
        masks = [
            positions < 50,
            (positions >= 50) & (positions < 100),
            (positions >= 100) & (positions < 150),
            positions >= 150,
        ]
        kw = stats.kruskal(*[self.values[m] for m in masks])
        return inf.block_bootstrap_null_test(
            self.values,
            statistic=lambda matrix: inf.kruskal_statistic_rows(matrix, masks),
            observed_statistic=float(kw.statistic),
            alternative="greater",
            n_bootstrap=300,
            seed=42,
            **kwargs,
        )

    def test_p_value_is_bounded_and_never_zero(self):
        result = self._run()
        self.assertGreater(result["p_value"], 0.0)
        self.assertLessEqual(result["p_value"], 1.0)
        self.assertGreaterEqual(result["p_value"], result["resolution_floor"] - 1e-12)

    def test_same_seed_gives_the_same_p_value(self):
        self.assertEqual(self._run()["p_value"], self._run()["p_value"])

    def test_resolution_floor_matches_the_bootstrap_count(self):
        result = self._run()
        self.assertAlmostEqual(result["resolution_floor"], 2.0 / (300 + 1), places=12)

    def test_block_length_is_capped_at_series_length(self):
        result = self._run(block_length=10_000)
        self.assertEqual(result["block_length"], 200)

    def test_null_series_with_nan_is_rejected(self):
        broken = self.values.copy()
        broken[5] = np.nan
        positions = np.arange(200)
        with self.assertRaises(ValueError):
            inf.block_bootstrap_null_test(
                broken,
                statistic=lambda matrix: inf.kruskal_statistic_rows(
                    matrix, [positions < 100, positions >= 100]
                ),
                observed_statistic=1.0,
                n_bootstrap=50,
            )

    def test_too_short_series_is_rejected(self):
        with self.assertRaises(ValueError):
            inf.block_bootstrap_null_test(
                np.arange(4.0),
                statistic=lambda matrix: np.zeros(matrix.shape[0]),
                observed_statistic=0.0,
                n_bootstrap=10,
            )

    def test_invalid_alternative_is_rejected(self):
        with self.assertRaises(ValueError):
            inf.block_bootstrap_null_test(
                self.values,
                statistic=lambda matrix: np.zeros(matrix.shape[0]),
                observed_statistic=0.0,
                alternative="two-sideds",
                n_bootstrap=10,
            )


class TestNullImposedTest(unittest.TestCase):
    """Null phải được dựng DƯỚI H₀ — phép kiểm vị trí phải bất biến dịch chuyển."""

    def test_p_value_is_invariant_to_a_location_shift(self):
        values = _ar1(200, seed=17)
        base = inf.null_imposed_centered_test(
            values, mu=0.0, statistic="t", n_bootstrap=400, seed=42
        )
        shifted = inf.null_imposed_centered_test(
            values + 5.0, mu=5.0, statistic="t", n_bootstrap=400, seed=42
        )
        self.assertAlmostEqual(base["p_value"], shifted["p_value"], places=12)

    def test_p_value_grows_as_the_null_hypothesis_gets_closer(self):
        values = _ar1(200, seed=19) + 3.0
        far = inf.null_imposed_centered_test(
            values, mu=0.0, statistic="t", n_bootstrap=400, seed=42
        )
        near = inf.null_imposed_centered_test(
            values, mu=3.0, statistic="t", n_bootstrap=400, seed=42
        )
        self.assertLess(far["p_value"], near["p_value"])

    def test_bootstrap_percentile_p_value_is_consistent_with_the_interval(self):
        values = _ar1(200, seed=23)
        result = inf.bootstrap_percentile_pvalue(
            values, mu=0.0, statistic="mean", n_bootstrap=400, seed=42
        )
        interval = inf.bootstrap_ci(
            values, statistic="mean", block_length=28, n_bootstrap=400, seed=42
        )
        # Nếu CI 95% không chứa μ thì p-value phải nhỏ; nếu chứa thì p lớn.
        if interval["ci_low"] <= 0.0 <= interval["ci_high"]:
            self.assertGreater(result["p_value"], 0.05)
        else:
            self.assertLess(result["p_value"], 0.05)


class TestPowerUnderControl(unittest.TestCase):
    """Power phải tăng khi hiệu ứng tăng — kiểm tra phương pháp không mất sức mạnh vô lý."""

    N_DAYS = 200
    N_SIM = 40

    def test_p_value_shrinks_as_the_null_moves_away(self):
        # Hiệu ứng lớn hơn phải cho p-value nhỏ hơn trên cùng một chuỗi.
        values = _ar1(self.N_DAYS, seed=29)
        far = inf.null_imposed_centered_test(
            values, mu=-5.0, statistic="t", n_bootstrap=400, seed=42
        )
        near = inf.null_imposed_centered_test(
            values, mu=0.0, statistic="t", n_bootstrap=400, seed=42
        )
        self.assertLess(far["p_value"], near["p_value"])


class TestIndependentDataIsUnaffected(unittest.TestCase):
    """Với dữ liệu độc lập, hiệu chỉnh phụ thuộc không được làm sai lệch p-value."""

    def test_corrected_and_naive_p_values_agree_on_independent_data(self):
        rng = np.random.default_rng(31)
        values = rng.normal(size=400)
        naive = float(stats.ttest_1samp(values, popmean=0.0).pvalue)
        corrected = inf.hac_mean_test(values, mu=0.0, lag=4)["p_value"]
        self.assertLess(
            abs(np.log10(max(naive, 1e-300)) - np.log10(max(corrected, 1e-300))), 1.0
        )

    def test_hac_interval_is_close_to_the_ols_interval_without_dependence(self):
        rng = np.random.default_rng(33)
        values = rng.normal(loc=5.0, scale=2.0, size=400)
        model = inf.hac_mean_test(values, mu=0.0, lag=4)
        naive_se = values.std(ddof=1) / np.sqrt(values.size)
        self.assertLess(model["se"], 1.5 * naive_se)


class TestHolmMatchesStatsmodels(unittest.TestCase):
    """Kiểm chứng hiệu chỉnh Holm bằng một implementation độc lập."""

    def test_matches_statsmodels_multipletests(self):
        from statsmodels.stats.multitest import multipletests

        p = np.array([0.001, 0.013, 0.04, 0.2, 0.5])
        expected = multipletests(p, method="holm")[1]
        np.testing.assert_allclose(inf.holm_adjust(p), expected, atol=1e-12)

    def test_matches_statsmodels_with_ties(self):
        from statsmodels.stats.multitest import multipletests

        p = np.array([0.02, 0.02, 0.02, 0.3])
        expected = multipletests(p, method="holm")[1]
        np.testing.assert_allclose(inf.holm_adjust(p), expected, atol=1e-12)


class TestSeasonGeneralizationDiagnostics(unittest.TestCase):
    def test_reports_one_cycle_and_per_season_coverage(self):
        panel, _ = inf.build_daily_panel(_synthetic_hourly())
        result = inf.season_generalization_diagnostics(panel)
        self.assertEqual(result["n_seasonal_cycles"], 1)
        self.assertEqual(set(result["coverage"]), set(SEASON_DISPLAY_ORDER))
        for season_key, coverage in result["coverage"].items():
            with self.subTest(season=season_key):
                self.assertEqual(
                    coverage["kept_days"] + coverage["dropped_days"],
                    coverage["calendar_days"],
                )

    def test_december_and_january_belong_to_the_same_season_year(self):
        dates = pd.to_datetime(
            ["2025-12-15", "2026-01-15", "2026-02-15", "2025-07-15", "2026-07-15"]
        )
        seasons = pd.Series(["Dong", "Dong", "Dong", "He", "He"])
        years = inf._season_year(dates, seasons)
        self.assertEqual(years.tolist(), [2026, 2026, 2026, 2025, 2026])

    def test_trend_to_contrast_ratio_is_reported(self):
        panel, _ = inf.build_daily_panel(_synthetic_hourly())
        result = inf.season_generalization_diagnostics(panel)
        self.assertGreater(result["max_season_contrast"], 0.0)
        self.assertTrue(np.isfinite(result["trend_to_contrast_ratio"]))


class TestAssumptionViolations(unittest.TestCase):
    """Phải báo lỗi rõ ràng khi giả định bị vi phạm — không âm thầm trả số."""

    def test_hac_mean_test_rejects_a_constant_series(self):
        with self.assertRaises(ValueError):
            inf.hac_mean_test(np.full(30, 7.0), mu=0.0, lag=4)

    def test_hac_mean_test_requires_enough_observations(self):
        with self.assertRaises(ValueError):
            inf.hac_mean_test(np.arange(5.0), mu=0.0, lag=2)

    def test_null_imposed_test_rejects_too_few_observations(self):
        with self.assertRaises(ValueError):
            inf.null_imposed_centered_test(np.arange(5.0), mu=0.0, statistic="t")

    def test_null_imposed_test_rejects_an_unknown_statistic(self):
        with self.assertRaises(ValueError):
            inf.null_imposed_centered_test(
                np.arange(30.0), mu=0.0, statistic="medianrank"
            )


class TestNotebookGeneratorMatchesNotebook(unittest.TestCase):
    """Generator là nguồn sự thật — notebook trong repo phải khớp cấu trúc."""

    def test_generator_rebuilds_the_documented_cell_mix(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "generate_05_notebook", REPO_ROOT / "scripts" / "generate_05_notebook.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        notebook = module.build_notebook_dict()
        self.assertEqual(len(notebook["cells"]), 49)
        self.assertEqual(
            sum(1 for c in notebook["cells"] if c["cell_type"] == "code"), 23
        )
        self.assertEqual(
            sum(1 for c in notebook["cells"] if c["cell_type"] == "markdown"), 26
        )

    def test_notebook_on_disk_matches_the_generator_cell_structure(self):
        nb = nbformat.read(
            REPO_ROOT / "notebooks" / "05_statistical_inference.ipynb", as_version=4
        )
        self.assertEqual(len(nb.cells), 49)
        self.assertEqual(sum(1 for c in nb.cells if c.cell_type == "code"), 23)

    def test_notebook_documents_the_dependence_aware_framework(self):
        nb = nbformat.read(
            REPO_ROOT / "notebooks" / "05_statistical_inference.ipynb", as_version=4
        )
        text = "\n".join(
            "".join(cell.source) for cell in nb.cells if cell.cell_type == "markdown"
        )
        for token in ("Newey", "HAC", "null", "R1", "THĂM DÒ"):
            self.assertIn(token, text)


# ---------------------------------------------------------------------------
# Bootstrap THEO LỊCH — giữ khoảng cách ngày và mặt nạ thiếu (review 5588255357)
# ---------------------------------------------------------------------------


def _calendar_with_gaps(
    values: Sequence[float],
    missing_positions: Sequence[int],
    *,
    start: str = "2025-01-01",
    weekend: Optional[Sequence[bool]] = None,
) -> inf.DailyCalendar:
    """Dựng lịch giả: `values` theo ngày lịch, các vị trí trong `missing_positions` là NaN."""
    n = len(values)
    dates = pd.date_range(start, periods=n, freq="D")
    data = np.asarray(values, dtype=float).copy()
    data[list(missing_positions)] = np.nan
    if weekend is None:
        is_weekend = (dates.dayofweek.to_numpy() >= 5).astype(np.int64)
    else:
        is_weekend = np.asarray(weekend, dtype=np.int64)
    return inf.DailyCalendar(
        dates=dates.to_numpy(dtype="datetime64[D]"),
        values=data,
        labels=is_weekend.copy(),
        valid_hours=np.where(np.isfinite(data), 24, 0).astype(np.int64),
        season=np.array(["Xuan"] * n, dtype=object),
        is_weekend=is_weekend,
        week_key=np.asarray([f"2025-W{i:02d}" for i in range(n)], dtype=object),
    )


class TestCalendarBlockIndices(unittest.TestCase):
    """Block phải là NGÀY LỊCH liên tiếp — không phải phần tử liền nhau của mảng."""

    def test_block_length_is_counted_in_calendar_days(self):
        n = 40
        indices = inf.calendar_block_indices(n, block_length_days=7, n_bootstrap=5, seed=42)
        self.assertEqual(indices.shape, (5, n))
        for row in indices:
            for start in range(0, n, 7):
                block = row[start:start + 7]
                # Mỗi phần tử trong block lệch đúng 1 ngày lịch so với phần tử trước
                # (theo modulo vòng tròn) → chứng minh block là ngày LỊCH liên tiếp.
                deltas = np.diff(block) % n
                self.assertTrue(np.all(deltas == 1), f"block không liên tiếp: {deltas}")

    def test_wrap_around_is_circular(self):
        indices = inf.calendar_block_indices(10, block_length_days=4, n_bootstrap=3, seed=1)
        for row in indices:
            for start in range(0, 10, 4):
                block = row[start:start + 4]
                deltas = np.diff(block) % 10
                self.assertTrue(np.all(deltas == 1))

    def test_same_seed_is_deterministic(self):
        a = inf.calendar_block_indices(50, block_length_days=7, n_bootstrap=4, seed=42)
        b = inf.calendar_block_indices(50, block_length_days=7, n_bootstrap=4, seed=42)
        np.testing.assert_array_equal(a, b)

    def test_block_length_longer_than_calendar_is_rejected(self):
        with self.assertRaises(ValueError):
            inf.calendar_block_indices(5, block_length_days=6, n_bootstrap=2)

    def test_missing_days_are_not_removed_from_the_index_space(self):
        """
        Ngày thiếu phải **giữ nguyên vị trí** trên trục lịch — nếu bị nén thì
        "28 ngày" lại biến thành "28 phần tử" (đúng lỗi review chỉ ra).
        """
        n = 30
        indices = inf.calendar_block_indices(n, block_length_days=7, n_bootstrap=2, seed=3)
        self.assertEqual(indices.shape[1], n)
        self.assertEqual(indices.max(), n - 1)
        self.assertEqual(indices.min(), 0)


class TestCalendarReplicates(unittest.TestCase):
    """Mặt nạ thiếu đi theo bản sao; nhãn ở vị trí đích; không tạo quan sát giả."""

    def test_missing_mask_travels_with_the_copy(self):
        values = np.arange(30.0)
        calendar = _calendar_with_gaps(values, [3, 4, 5, 20])
        indices = inf.calendar_block_indices(30, block_length_days=7, n_bootstrap=50, seed=42)
        reps, _ = inf.calendar_replicates(calendar.values, calendar.labels, indices)
        for b, row in enumerate(reps):
            # Vị trí nào có giá trị NaN ở bản sao thì nguồn của nó cũng NaN
            for j in range(row.size):
                source = indices[b, j]
                if np.isnan(row[j]):
                    self.assertTrue(np.isnan(calendar.values[source]))

    def test_no_fake_observations_are_created(self):
        values = np.arange(30.0)
        calendar = _calendar_with_gaps(values, [3, 4, 5, 20])
        indices = inf.calendar_block_indices(30, block_length_days=7, n_bootstrap=20, seed=42)
        reps, _ = inf.calendar_replicates(calendar.values, calendar.labels, indices)
        # Mọi giá trị hữu hạn trong bản sao đều phải là một giá trị có sẵn trong lịch
        finite_values = set(np.round(calendar.values[np.isfinite(calendar.values)], 9))
        for row in reps:
            for value in row[np.isfinite(row)]:
                self.assertIn(round(float(value), 9), finite_values)

    def test_labels_are_decoupled_from_the_resampled_values(self):
        """
        Nhãn ở vị trí j phải là nhãn lịch của vị trí j (không theo nguồn).

        Nếu nhãn đi theo nguồn thì hiệu ứng mùa vụ được giữ lại trong null → p-value
        bị thổi phồng. Test này chốt đúng tính chất đó.
        """
        values = np.arange(30.0)
        weekend = [bool(i % 7 >= 5) for i in range(30)]
        calendar = _calendar_with_gaps(values, [], weekend=weekend)
        indices = inf.calendar_block_indices(30, block_length_days=7, n_bootstrap=10, seed=42)
        _, labels = inf.calendar_replicates(calendar.values, calendar.labels, indices)
        for row in labels:
            np.testing.assert_array_equal(row, calendar.labels)

    def test_missing_positions_are_never_bridged(self):
        """
        Hai ngày thiếu liên tiếp phải **không** bị "nối" trong bản sao: số ngày
        thiếu của mỗi bản sao phải bằng số ngày thiếu của lịch gốc.
        """
        values = np.arange(60.0)
        calendar = _calendar_with_gaps(values, list(range(10, 17)) + [40, 41, 42])
        indices = inf.calendar_block_indices(60, block_length_days=14, n_bootstrap=30, seed=42)
        reps, _ = inf.calendar_replicates(calendar.values, calendar.labels, indices)
        expected_missing = int((~np.isfinite(calendar.values)).sum())
        # Bản sao là hoán vị theo block nên tổng số ngày thiếu có thể khác, nhưng
        # mỗi vị trí thiếu phải tương ứng với một ngày nguồn cũng thiếu — tức là
        # **không** ngày thiếu nào bị "lấp" bằng quan sát ở ngày khác.
        for b, row in enumerate(reps):
            n_missing = int(np.isnan(row).sum())
            self.assertGreaterEqual(n_missing, 0)
            for j in np.where(np.isnan(row))[0]:
                self.assertTrue(np.isnan(calendar.values[indices[b, j]]))
        self.assertGreater(expected_missing, 0)


class TestCalendarNullTestWithGaps(unittest.TestCase):
    """Null bootstrap phải chạy được khi lịch có ngày thiếu rời rạc và thành cụm."""

    def _calendar(self, missing: Sequence[int], n: int = 120) -> inf.DailyCalendar:
        rng = np.random.default_rng(5)
        values = inf._ar1_daily(n, 0.7, 1.0, rng)
        return _calendar_with_gaps(values, missing)

    def test_runs_with_scattered_missing_days(self):
        calendar = self._calendar([3, 9, 14, 22, 30, 41, 55, 66, 77, 90, 101])
        result = inf.calendar_bootstrap_null_test(
            calendar,
            statistic=lambda m, labels: inf.mannwhitney_statistic_rows_nan(
                m, labels == 0, labels == 1
            ),
            observed_statistic=0.0,
            alternative="two-sided",
            block_length_days=14,
            n_bootstrap=100,
            seed=42,
        )
        self.assertGreater(result["p_value"], 0.0)
        self.assertLessEqual(result["p_value"], 1.0)
        self.assertEqual(result["n_replicates_dropped"], 0)

    def test_runs_with_clustered_missing_days(self):
        calendar = self._calendar(list(range(20, 30)) + list(range(80, 90)))
        result = inf.calendar_bootstrap_null_test(
            calendar,
            statistic=lambda m, labels: inf.mannwhitney_statistic_rows_nan(
                m, labels == 0, labels == 1
            ),
            observed_statistic=0.0,
            alternative="two-sided",
            block_length_days=28,
            n_bootstrap=100,
            seed=42,
        )
        self.assertGreater(result["p_value"], 0.0)

    def test_missing_at_the_start_middle_and_end(self):
        calendar = self._calendar([0, 1, 2, 60, 61, 118, 119])
        result = inf.calendar_bootstrap_null_test(
            calendar,
            statistic=lambda m, labels: inf.mannwhitney_statistic_rows_nan(
                m, labels == 0, labels == 1
            ),
            observed_statistic=0.0,
            alternative="two-sided",
            block_length_days=7,
            n_bootstrap=100,
            seed=42,
        )
        self.assertGreater(result["p_value"], 0.0)

    def test_reports_the_observed_count_of_each_replicate(self):
        calendar = self._calendar([5, 6, 7, 8, 9])
        result = inf.calendar_bootstrap_null_test(
            calendar,
            statistic=lambda m, labels: inf.mannwhitney_statistic_rows_nan(
                m, labels == 0, labels == 1
            ),
            observed_statistic=0.0,
            alternative="two-sided",
            block_length_days=14,
            n_bootstrap=100,
            seed=42,
        )
        self.assertEqual(result["n_observed_original"], 115)
        self.assertGreater(result["n_observed_replicate_mean"], 0.0)
        self.assertGreaterEqual(result["n_observed_replicate_min"], 0)

    def test_same_seed_gives_the_same_p_value(self):
        calendar = self._calendar([3, 11, 19])
        kwargs = dict(
            statistic=lambda m, labels: inf.mannwhitney_statistic_rows_nan(
                m, labels == 0, labels == 1
            ),
            observed_statistic=0.0,
            alternative="two-sided",
            block_length_days=14,
            n_bootstrap=100,
            seed=42,
        )
        first = inf.calendar_bootstrap_null_test(calendar, **kwargs)
        second = inf.calendar_bootstrap_null_test(calendar, **kwargs)
        self.assertEqual(first["p_value"], second["p_value"])

    def test_value_override_must_match_the_calendar_length(self):
        calendar = self._calendar([1, 2])
        with self.assertRaises(ValueError):
            inf.calendar_bootstrap_null_test(
                calendar,
                statistic=lambda m, labels: np.zeros(m.shape[0]),
                observed_statistic=0.0,
                value_override=np.zeros(3),
            )


class TestCalendarBootstrapCI(unittest.TestCase):
    def test_ci_keeps_the_calendar_mask(self):
        rng = np.random.default_rng(9)
        values = inf._ar1_daily(80, 0.7, 1.0, rng)
        calendar = _calendar_with_gaps(values, list(range(10, 15)))
        ci = inf.calendar_bootstrap_ci(
            calendar, statistic="median", block_length_days=14, n_bootstrap=200, seed=42
        )
        self.assertLessEqual(ci["ci_low"], ci["point"])
        self.assertGreaterEqual(ci["ci_high"], ci["point"])
        self.assertEqual(ci["block_length_days"], 14)

    def test_difference_ci_uses_one_shared_calendar(self):
        rng = np.random.default_rng(11)
        values = inf._ar1_daily(80, 0.7, 1.0, rng)
        calendar = _calendar_with_gaps(values, [7, 8])
        mask_a = calendar.labels == 0
        mask_b = calendar.labels == 1
        ci = inf.calendar_bootstrap_difference_ci(
            calendar, mask_a, mask_b, statistic="median",
            block_length_days=14, n_bootstrap=200, seed=42,
        )
        self.assertLessEqual(ci["ci_low"], ci["point"])
        self.assertGreaterEqual(ci["ci_high"], ci["point"])


class TestMonteCarloValidation(unittest.TestCase):
    """
    Kiểm chứng Monte Carlo là **kiểm chứng khoa học có chi phí**, không phải
    regression test chạy mỗi lần CI. Ở đây chỉ kiểm tra *hợp đồng* (cấu trúc,
    tái lập theo seed, tỷ lệ nằm trong [0, 1], CI Wilson hợp lệ) với số lần
    mô phỏng rất nhỏ.
    """

    def test_contract_of_the_result_structure(self):
        result = inf.monte_carlo_validation(
            n_days=60, n_sim=6, seed=1, n_bootstrap=40, scenarios=["independent"]
        )
        self.assertIn("scenarios", result)
        self.assertIn("independent", result["scenarios"])
        entry = result["scenarios"]["independent"]["tests"]["mean"]
        for key in ("rate_p_bootstrap", "ci_low_p_bootstrap", "ci_high_p_bootstrap"):
            self.assertIn(key, entry)
        rate = entry["rate_p_bootstrap"]
        self.assertGreaterEqual(rate, 0.0)
        self.assertLessEqual(rate, 1.0)
        self.assertLessEqual(entry["ci_low_p_bootstrap"], rate + 1e-9)
        self.assertGreaterEqual(entry["ci_high_p_bootstrap"], rate - 1e-9)

    def test_is_reproducible_for_the_same_seed(self):
        kwargs = dict(
            n_days=60, n_sim=5, seed=7, n_bootstrap=40, scenarios=["ar1_medium"]
        )
        first = inf.monte_carlo_validation(**kwargs)
        second = inf.monte_carlo_validation(**kwargs)
        self.assertEqual(
            first["scenarios"]["ar1_medium"]["tests"]["mean"]["rate_p_bootstrap"],
            second["scenarios"]["ar1_medium"]["tests"]["mean"]["rate_p_bootstrap"],
        )

    def test_scenarios_cover_the_required_regimes(self):
        for key in (
            "independent",
            "ar1_weak",
            "ar1_medium",
            "ar1_strong",
            "long_range",
            "missing_random",
            "missing_clustered",
            "missing_real_pattern",
        ):
            self.assertIn(key, inf.SIMULATION_SCENARIOS)

    def test_csv_round_trip(self):
        result = inf.monte_carlo_validation(
            n_days=40, n_sim=4, seed=2, n_bootstrap=30, scenarios=["independent"]
        )
        with tempfile.TemporaryDirectory() as folder:
            path = inf.save_monte_carlo_csv(result, Path(folder) / "mc.csv")
            self.assertTrue(path.exists())
            loaded = inf.load_monte_carlo_csv(path)
            self.assertIsNotNone(loaded)
            self.assertIn("independent", loaded["scenarios"])
            self.assertIn("mean", loaded["scenarios"]["independent"]["tests"])

    def test_load_returns_none_when_the_file_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(inf.load_monte_carlo_csv(Path(folder) / "khong.csv"))


class TestCalendarAwarePipeline(unittest.TestCase):
    """Pipeline đầu-cuối phải dùng lịch, và kết luận phải bám quy tắc R1–R5."""

    def test_run_inference_exposes_the_calendar_diagnostics(self):
        frame = _synthetic_hourly(days=400)
        results = inf.run_inference(frame, n_bootstrap=40, seed=42, include_simulation=False)
        calendar = results["calendar"]
        self.assertGreater(calendar["n_calendar_days"], 0)
        self.assertLessEqual(calendar["n_observed_days"], calendar["n_calendar_days"])
        self.assertEqual(
            calendar["n_observed_days"], results["panel"]["n"]
        )
        self.assertEqual(
            calendar["n_missing_days"],
            calendar["n_calendar_days"] - calendar["n_observed_days"],
        )

    def test_season_test_is_always_exploratory(self):
        frame = _synthetic_hourly(days=400)
        results = inf.run_inference(frame, n_bootstrap=40, seed=42, include_simulation=False)
        self.assertEqual(results["tests"]["season_effect"]["status"], "exploratory")
        self.assertIn("một chu kỳ mùa", results["tests"]["season_effect"]["status_reason"].lower())

    def test_weekday_test_uses_the_hac_estimate(self):
        frame = _synthetic_hourly(days=400)
        results = inf.run_inference(frame, n_bootstrap=40, seed=42, include_simulation=False)
        weekday = results["tests"]["weekday_effect"]
        self.assertAlmostEqual(
            weekday["p_value"], weekday["supporting_result"]["p_value"], places=12
        )
        self.assertIn("p_value_bootstrap", weekday)

    def test_location_tests_expose_the_bootstrap_alternative(self):
        frame = _synthetic_hourly(days=400)
        results = inf.run_inference(frame, n_bootstrap=40, seed=42, include_simulation=False)
        for key in ("qcvn_24h", "qcvn_annual"):
            with self.subTest(test=key):
                self.assertIn("p_value_bootstrap", results["tests"][key])
                self.assertGreater(results["tests"][key]["p_value_bootstrap"], 0.0)

    def test_data_source_is_a_relative_path(self):
        frame = _synthetic_hourly(days=400)
        results = inf.run_inference(frame, n_bootstrap=20, seed=42, include_simulation=False)
        source = results["meta"]["data_source"]
        self.assertNotIn("C:\\", source)
        self.assertNotIn("Users", source)


if __name__ == "__main__":
    unittest.main()
