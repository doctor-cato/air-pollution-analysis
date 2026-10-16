"""
Unit tests for `src/visualizer.py` (Issue #9 — Explanatory Visualization Suite).

Covers all 11 mandatory verification areas:
  1. Figure return types and 300 DPI PNG export metadata (pHYs chunk).
  2. `generate_all_figures()` batch orchestrator and memory cleanup (`plt.close`).
  3. Edward Tufte Data-Ink style (`top`/`right` spines hidden, subtle gridlines).
  4. Strict zero baseline (`ylim[0] == 0.0`) on bar charts (`FIG-07`).
  5. Data-driven dynamic takeaway titles (no hard-coded conclusions).
  6. Defensive input validation (`Empty`, `MissingColumnError`, all-NaN, bad timestamps).
  7. Strict non-mutation of caller DataFrames.
  8. Causal, time-aware, station-grouped rolling window semantics.
  9. Regulatory averaging-period compatibility (`rolling_24h` vs. QCVN 05:2023 & WHO 2021 24h).
 10. Runtime Vietnamese font resolution & `fig.canvas.draw()` glyph warning checks.
 11. Verification of committed `figures/FIG-01.png` .. `figures/FIG-07.png` artifacts.
"""

from __future__ import annotations

import struct
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from src.visualizer import (  # noqa: E402
    DEFAULT_DPI,
    DEFAULT_FIGURES_DIR,
    MissingColumnError,
    apply_tufte_style,
    compute_causal_rolling_pm25,
    configure_vietnamese_fonts,
    generate_all_figures,
    main as visualizer_main,
    plot_fig01_time_series,
    plot_fig02_distribution,
    plot_fig03_seasonal_monthly_boxplots,
    plot_fig04_diurnal_weekly_heatmap,
    plot_fig05_weather_lowess,
    plot_fig06_correlation_heatmap,
    plot_fig07_air_quality_categories,
)


def _make_synthetic_df(
    n_hours: int = 240,
    *,
    base_pm25: float = 35.0,
    seed: int = 42,
    start_ts: str = "2025-12-01 00:00:00",
) -> pd.DataFrame:
    """Create a deterministic synthetic air-pollution + meteorology DataFrame."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start_ts, periods=n_hours, freq="h", tz="Asia/Ho_Chi_Minh")
    hours = ts.hour.to_numpy(dtype=float)

    wind_speed = np.clip(2.2 + 1.1 * np.sin(hours * np.pi / 12.0) + rng.normal(0, 0.5, n_hours), 0.1, 9.0)
    temperature = 21.0 + 4.5 * np.sin((hours - 6.0) * np.pi / 12.0) + rng.normal(0, 1.0, n_hours)
    relative_humidity = np.clip(75.0 - 10.0 * np.sin((hours - 6.0) * np.pi / 12.0) + rng.normal(0, 4.0, n_hours), 30.0, 100.0)
    surface_pressure = 1014.0 + rng.normal(0, 2.5, n_hours)
    precipitation = np.where(rng.random(n_hours) < 0.1, rng.exponential(1.2, n_hours), 0.0)
    wind_direction = (110.0 + rng.normal(0, 35.0, n_hours)) % 360.0

    # Right-skewed PM2.5 inversely related to wind speed
    noise = rng.lognormal(mean=0.0, sigma=0.35, size=n_hours) * 10.0
    pm25 = np.clip(base_pm25 - 4.0 * (wind_speed - 2.0) + noise, 2.0, 240.0)
    pm10 = pm25 * 1.35 + rng.normal(0, 3.0, n_hours)

    df = pd.DataFrame(
        {
            "timestamp": ts,
            "station_id": "VN001_HANOI_556_NGUYEN_VAN_CU",
            "location": "556 Nguyen Van Cu",
            "pm25": pm25,
            "pm10": pm10,
            "temperature": temperature,
            "relative_humidity": relative_humidity,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "precipitation": precipitation,
            "surface_pressure": surface_pressure,
        }
    )
    return df


def _read_png_dimensions_and_dpi(path: Path) -> Tuple[int, int, float, float]:
    """Parse PNG header (IHDR) and physical pixel resolution (pHYs) chunk directly."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"File {path} does not have a valid PNG signature.")

    width = height = 0
    dpi_x = dpi_y = 0.0
    pos = 8
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length

        if chunk_type == b"IHDR":
            width, height = struct.unpack(">II", chunk_data[:8])
        elif chunk_type == b"pHYs":
            ppu_x, ppu_y, unit = struct.unpack(">IIB", chunk_data[:9])
            if unit == 1:  # pixels per meter -> convert to dots per inch
                dpi_x = ppu_x * 0.0254
                dpi_y = ppu_y * 0.0254
        elif chunk_type == b"IEND":
            break

    return width, height, dpi_x, dpi_y


def _collect_all_figure_text(fig: Figure) -> str:
    """Gather suptitle, axes titles (center/left/right), axis labels, tick labels, legends, and text artists."""
    pieces = []
    if fig._suptitle is not None:
        pieces.append(fig._suptitle.get_text())
    for text_obj in fig.texts:
        pieces.append(text_obj.get_text())
    for ax in fig.axes:
        for loc in ("center", "left", "right"):
            pieces.append(ax.get_title(loc=loc))
        pieces.append(ax.get_xlabel())
        pieces.append(ax.get_ylabel())
        for t in ax.texts:
            pieces.append(t.get_text())
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            pieces.append(lbl.get_text())
        leg = ax.get_legend()
        if leg is not None:
            for t in leg.get_texts():
                pieces.append(t.get_text())
    return "\n".join(p for p in pieces if p)


class TestVisualizerSuite(unittest.TestCase):
    """Comprehensive unit tests for `src/visualizer.py`."""

    def tearDown(self) -> None:
        plt.close("all")

    # ------------------------------------------------------------------
    # 1. Return Types & 300 DPI PNG Export
    # ------------------------------------------------------------------

    def test_all_seven_functions_return_figure_and_save_300_dpi_png(self) -> None:
        df = _make_synthetic_df(n_hours=240)
        functions = [
            ("FIG-01", plot_fig01_time_series),
            ("FIG-02", plot_fig02_distribution),
            ("FIG-03", plot_fig03_seasonal_monthly_boxplots),
            ("FIG-04", plot_fig04_diurnal_weekly_heatmap),
            ("FIG-05", plot_fig05_weather_lowess),
            ("FIG-06", plot_fig06_correlation_heatmap),
            ("FIG-07", plot_fig07_air_quality_categories),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            for fig_id, func in functions:
                out_path = tmp_root / f"{fig_id}.png"
                fig = func(df, output_path=out_path)
                try:
                    self.assertIsInstance(fig, Figure, f"{fig_id} did not return a Figure")
                    self.assertTrue(out_path.exists(), f"{fig_id} PNG was not created")
                    self.assertGreater(out_path.stat().st_size, 10_000, f"{fig_id} PNG is unexpectedly small")
                    w, h, dpi_x, dpi_y = _read_png_dimensions_and_dpi(out_path)
                    self.assertGreater(w, 1500, f"{fig_id} width too small: {w}")
                    self.assertGreater(h, 800, f"{fig_id} height too small: {h}")
                    self.assertAlmostEqual(dpi_x, float(DEFAULT_DPI), delta=1.0)
                    self.assertAlmostEqual(dpi_y, float(DEFAULT_DPI), delta=1.0)
                finally:
                    plt.close(fig)

    def test_generate_all_figures_creates_seven_files_and_closes_figures(self) -> None:
        df = _make_synthetic_df(n_hours=240)
        plt.close("all")
        with tempfile.TemporaryDirectory() as tmpdir:
            saved = generate_all_figures(df=df, output_dir=tmpdir)
            self.assertEqual(
                set(saved.keys()),
                {"FIG-01", "FIG-02", "FIG-03", "FIG-04", "FIG-05", "FIG-06", "FIG-07"},
            )
            for fig_id, path in saved.items():
                self.assertTrue(path.exists(), f"Missing {fig_id} at {path}")
                _, _, dpi_x, _ = _read_png_dimensions_and_dpi(path)
                self.assertAlmostEqual(dpi_x, 300.0, delta=1.0)
            # Verify no Figure objects were left open in memory
            self.assertEqual(len(plt.get_fignums()), 0)

    def test_cli_main_generates_figures_from_parquet(self) -> None:
        df = _make_synthetic_df(n_hours=200)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            parquet_path = tmp_root / "synthetic.parquet"
            out_dir = tmp_root / "out_figs"
            df.to_parquet(parquet_path, index=False)

            exit_code = visualizer_main(
                ["--data-path", str(parquet_path), "--output-dir", str(out_dir), "--dpi", "300"]
            )
            self.assertEqual(exit_code, 0)
            for idx in range(1, 8):
                self.assertTrue((out_dir / f"FIG-0{idx}.png").exists())

    def test_generate_all_figures_raises_file_not_found_for_missing_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_parquet = Path(tmpdir) / "does_not_exist.parquet"
            with self.assertRaises(FileNotFoundError):
                generate_all_figures(df=None, data_path=missing_parquet, output_dir=tmpdir)

    # ------------------------------------------------------------------
    # 2. Tufte Style & Zero-Baseline Enforcement
    # ------------------------------------------------------------------

    def test_tufte_style_removes_top_and_right_spines(self) -> None:
        df = _make_synthetic_df(n_hours=200)
        for builder in (
            plot_fig01_time_series,
            plot_fig02_distribution,
            plot_fig03_seasonal_monthly_boxplots,
            plot_fig05_weather_lowess,
            plot_fig07_air_quality_categories,
        ):
            fig = builder(df)
            try:
                for ax in fig.axes:
                    self.assertFalse(ax.spines["top"].get_visible())
                    self.assertFalse(ax.spines["right"].get_visible())
            finally:
                plt.close(fig)

    def test_apply_tufte_style_despine_left_and_no_grid(self) -> None:
        fig, ax = plt.subplots()
        try:
            apply_tufte_style(ax, grid_axis="none", despine_left=True)
            self.assertFalse(ax.spines["top"].get_visible())
            self.assertFalse(ax.spines["right"].get_visible())
            self.assertFalse(ax.spines["left"].get_visible())
        finally:
            plt.close(fig)

    def test_fig07_bar_chart_enforces_strict_zero_baseline(self) -> None:
        df = _make_synthetic_df(n_hours=200, base_pm25=65.0)
        fig = plot_fig07_air_quality_categories(df)
        try:
            ax = fig.axes[0]
            y_bottom, y_top = ax.get_ylim()
            self.assertEqual(y_bottom, 0.0, f"Bar chart y-axis must start at 0.0, got {y_bottom}")
            self.assertGreater(y_top, 0.0)
        finally:
            plt.close(fig)

    # ------------------------------------------------------------------
    # 3. Data-Driven Dynamic Titles (No Hard-Coded Conclusions)
    # ------------------------------------------------------------------

    def test_titles_change_dynamically_when_input_data_changes(self) -> None:
        df_low = _make_synthetic_df(n_hours=240, base_pm25=18.0, seed=10)
        df_high = _make_synthetic_df(n_hours=240, base_pm25=95.0, seed=20)

        for builder in (
            plot_fig01_time_series,
            plot_fig02_distribution,
            plot_fig03_seasonal_monthly_boxplots,
            plot_fig04_diurnal_weekly_heatmap,
            plot_fig05_weather_lowess,
            plot_fig07_air_quality_categories,
        ):
            fig_a = builder(df_low)
            fig_b = builder(df_high)
            try:
                text_a = _collect_all_figure_text(fig_a)
                text_b = _collect_all_figure_text(fig_b)
                self.assertNotEqual(
                    text_a,
                    text_b,
                    f"{builder.__name__} produced identical figure text for two distinct datasets!",
                )
            finally:
                plt.close(fig_a)
                plt.close(fig_b)

    def test_fig06_title_reflects_empirical_correlations(self) -> None:
        df_a = _make_synthetic_df(n_hours=120, seed=1)
        df_b = df_a.copy()
        # Invert wind_speed relationship in df_b
        df_b["wind_speed"] = df_b["pm25"] * 0.5
        fig_a = plot_fig06_correlation_heatmap(df_a)
        fig_b = plot_fig06_correlation_heatmap(df_b)
        try:
            self.assertNotEqual(_collect_all_figure_text(fig_a), _collect_all_figure_text(fig_b))
        finally:
            plt.close(fig_a)
            plt.close(fig_b)

    # ------------------------------------------------------------------
    # 4. Defensive Input Validation & Error Handling
    # ------------------------------------------------------------------

    def test_non_dataframe_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            plot_fig02_distribution([1, 2, 3])  # type: ignore[arg-type]

    def test_empty_dataframe_raises_value_error(self) -> None:
        empty_df = pd.DataFrame(columns=["timestamp", "pm25", "wind_speed"])
        for builder in (
            plot_fig01_time_series,
            plot_fig02_distribution,
            plot_fig03_seasonal_monthly_boxplots,
            plot_fig04_diurnal_weekly_heatmap,
            plot_fig05_weather_lowess,
            plot_fig06_correlation_heatmap,
            plot_fig07_air_quality_categories,
        ):
            with self.assertRaises(ValueError):
                builder(empty_df)

    def test_missing_required_columns_raises_key_and_value_error(self) -> None:
        df_no_pm25 = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=30, freq="h")})
        with self.assertRaises(KeyError):
            plot_fig01_time_series(df_no_pm25)
        with self.assertRaises(ValueError):
            plot_fig01_time_series(df_no_pm25)
        with self.assertRaises(MissingColumnError):
            plot_fig05_weather_lowess(df_no_pm25, weather_col="wind_speed")

    def test_all_nan_pm25_raises_value_error(self) -> None:
        df = _make_synthetic_df(n_hours=60)
        df["pm25"] = np.nan
        for builder in (
            plot_fig01_time_series,
            plot_fig02_distribution,
            plot_fig03_seasonal_monthly_boxplots,
            plot_fig04_diurnal_weekly_heatmap,
            plot_fig05_weather_lowess,
            plot_fig07_air_quality_categories,
        ):
            with self.assertRaises(ValueError):
                builder(df)

    def test_invalid_timestamps_raise_value_error(self) -> None:
        df_bad_str = _make_synthetic_df(n_hours=40)
        df_bad_str["timestamp"] = "not-a-timestamp"
        with self.assertRaises(ValueError):
            plot_fig01_time_series(df_bad_str)

        df_numeric_ts = _make_synthetic_df(n_hours=40)
        df_numeric_ts["timestamp"] = np.arange(40)
        with self.assertRaises(ValueError):
            plot_fig01_time_series(df_numeric_ts)

        df_nat = _make_synthetic_df(n_hours=40)
        df_nat.loc[5, "timestamp"] = pd.NaT
        with self.assertRaises(ValueError):
            plot_fig01_time_series(df_nat)

    def test_edge_case_parameter_validation(self) -> None:
        df = _make_synthetic_df(n_hours=48)
        with self.assertRaises(ValueError):
            compute_causal_rolling_pm25(df, min_periods_24h=0)
        with self.assertRaises(ValueError):
            compute_causal_rolling_pm25(df, min_periods_7d=200)
        with self.assertRaises(ValueError):
            plot_fig04_diurnal_weekly_heatmap(df, agg_func="invalid_agg")
        with self.assertRaises(MissingColumnError):
            plot_fig06_correlation_heatmap(df, columns=["pm25"])

        df_sparse = df.iloc[:10].copy()
        with self.assertRaises(ValueError):
            plot_fig07_air_quality_categories(df_sparse, min_periods_24h=24)

    # ------------------------------------------------------------------
    # 5. Non-Mutation of Caller DataFrame
    # ------------------------------------------------------------------

    def test_plotting_functions_do_not_mutate_input_dataframe(self) -> None:
        df = _make_synthetic_df(n_hours=120)
        snapshot = df.copy(deep=True)

        for builder in (
            compute_causal_rolling_pm25,
            plot_fig01_time_series,
            plot_fig02_distribution,
            plot_fig03_seasonal_monthly_boxplots,
            plot_fig04_diurnal_weekly_heatmap,
            plot_fig05_weather_lowess,
            plot_fig06_correlation_heatmap,
            plot_fig07_air_quality_categories,
        ):
            res = builder(df)
            if isinstance(res, Figure):
                plt.close(res)
            pd.testing.assert_frame_equal(df, snapshot)

    # ------------------------------------------------------------------
    # 6. Time-Series & Multi-Station Rolling Semantics
    # ------------------------------------------------------------------

    def test_unsorted_timestamps_are_sorted_chronologically_before_rolling(self) -> None:
        df_sorted = _make_synthetic_df(n_hours=96, seed=99)
        df_shuffled = df_sorted.sample(frac=1.0, random_state=42).reset_index(drop=True)

        roll_from_sorted = compute_causal_rolling_pm25(df_sorted)
        roll_from_shuffled = compute_causal_rolling_pm25(df_shuffled)

        pd.testing.assert_frame_equal(roll_from_sorted, roll_from_shuffled)

    def test_multi_station_rolling_does_not_bleed_across_stations(self) -> None:
        ts = pd.date_range("2026-01-01 00:00", periods=48, freq="h", tz="Asia/Ho_Chi_Minh")
        df_a = pd.DataFrame({"timestamp": ts, "station_id": "ST_A", "pm25": 200.0})
        df_b = pd.DataFrame({"timestamp": ts, "station_id": "ST_B", "pm25": 10.0})
        combined = pd.concat([df_a, df_b], ignore_index=True)

        rolled = compute_causal_rolling_pm25(combined, min_periods_24h=24, min_periods_7d=24)
        st_b_r24 = rolled.loc[rolled["station_id"] == "ST_B", "rolling_24h"].dropna()
        self.assertTrue((st_b_r24 == 10.0).all(), "Station A values bled into Station B rolling window!")

    def test_rolling_window_is_strictly_causal_and_time_gap_aware(self) -> None:
        # 1. Causal check: a huge future spike at t=24 must not affect rolling_24h at t=23
        ts = pd.date_range("2026-01-01 00:00", periods=30, freq="h", tz="Asia/Ho_Chi_Minh")
        pm = np.full(30, 20.0)
        pm[24] = 500.0
        df = pd.DataFrame({"timestamp": ts, "pm25": pm})
        rolled = compute_causal_rolling_pm25(df, min_periods_24h=24, min_periods_7d=24)
        self.assertAlmostEqual(float(rolled.loc[23, "rolling_24h"]), 20.0, places=6)

        # 2. Time-gap check: 23 hours before a 10-day gap + 1 hour after the gap
        # is only 1 observation in the trailing 24 hours, so min_periods_24h=24 must yield NaN.
        ts_gap = list(pd.date_range("2026-01-01 00:00", periods=23, freq="h", tz="Asia/Ho_Chi_Minh")) + [
            pd.Timestamp("2026-01-15 00:00", tz="Asia/Ho_Chi_Minh")
        ]
        df_gap = pd.DataFrame({"timestamp": ts_gap, "pm25": np.full(24, 60.0)})
        rolled_gap = compute_causal_rolling_pm25(df_gap, min_periods_24h=24, min_periods_7d=24)
        self.assertTrue(
            pd.isna(rolled_gap.loc[23, "rolling_24h"]),
            "Time-indexed rolling window failed to invalidate across a 14-day timestamp gap!",
        )

    # ------------------------------------------------------------------
    # 7. Regulatory Averaging-Period Semantics (FIG-01 & FIG-07)
    # ------------------------------------------------------------------

    def test_fig01_and_fig07_explicitly_label_pollutant_period_and_standards(self) -> None:
        df = _make_synthetic_df(n_hours=240)
        fig1 = plot_fig01_time_series(df)
        fig7 = plot_fig07_air_quality_categories(df)
        try:
            text1 = _collect_all_figure_text(fig1)
            self.assertIn("PM2.5", text1)
            self.assertIn("QCVN 05:2023/BTNMT", text1)
            self.assertIn("WHO 2021", text1)
            self.assertIn("24", text1)
            self.assertIn("µg/Nm³", text1)

            text7 = _collect_all_figure_text(fig7)
            self.assertIn("PM2.5", text7)
            self.assertIn("QCVN 05:2023/BTNMT", text7)
            self.assertIn("WHO 2021", text7)
            self.assertIn("min_periods=", text7)
        finally:
            plt.close(fig1)
            plt.close(fig7)

    def test_fig07_classifies_24h_rolling_mean_not_raw_hourly_spikes(self) -> None:
        """A single-hour spike of 120 µg/m³ amidst 20 µg/m³ hours keeps 24h mean < 50 µg/m³."""
        ts = pd.date_range("2026-01-01 00:00", periods=72, freq="h", tz="Asia/Ho_Chi_Minh")
        pm = np.full(72, 20.0)
        pm[30] = 120.0  # 1-hour spike; 24h mean is (23*20 + 120)/24 = 24.17 < 50.0
        df = pd.DataFrame({"timestamp": ts, "pm25": pm})

        fig = plot_fig07_air_quality_categories(df, min_periods_24h=24)
        try:
            ax = fig.axes[0]
            heights = [int(round(patch.get_height())) for patch in ax.patches[:6]]
            # Bins 4 and 5 correspond to [50, 75) and [75, inf)
            self.assertEqual(heights[4], 0, "Single-hour spike was falsely counted in 50-75 24h tier!")
            self.assertEqual(heights[5], 0, "Single-hour spike was falsely counted in >=75 24h tier!")
            self.assertIn("0.0% cửa sổ TB trượt 24h hợp lệ (0/", ax.get_title(loc="left"))
        finally:
            plt.close(fig)

    # ------------------------------------------------------------------
    # 8. Vietnamese Font Resolution & Canvas Draw Glyph Check (Task 2.2)
    # ------------------------------------------------------------------

    def test_vietnamese_font_renders_without_missing_glyph_warnings_on_canvas_draw(self) -> None:
        selected_family = configure_vietnamese_fonts()
        resolved_path = fm.findfont(selected_family, fallback_to_default=False)
        self.assertTrue(Path(resolved_path).exists(), f"Font file not found: {resolved_path}")

        df = _make_synthetic_df(n_hours=240)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for builder in (
                plot_fig01_time_series,
                plot_fig02_distribution,
                plot_fig03_seasonal_monthly_boxplots,
                plot_fig04_diurnal_weekly_heatmap,
                plot_fig05_weather_lowess,
                plot_fig06_correlation_heatmap,
                plot_fig07_air_quality_categories,
            ):
                fig = builder(df)
                try:
                    fig.canvas.draw()
                finally:
                    plt.close(fig)

        glyph_warnings = [
            str(w.message)
            for w in caught
            if "missing from font" in str(w.message).lower()
            or "glyph" in str(w.message).lower()
        ]
        self.assertEqual(
            glyph_warnings,
            [],
            f"Matplotlib emitted missing-glyph warnings during canvas.draw(): {glyph_warnings}",
        )

    # ------------------------------------------------------------------
    # 9. Committed Canonical Figures Verification (FIG-01..FIG-07)
    # ------------------------------------------------------------------

    def test_committed_figures_exist_and_have_300_dpi_metadata(self) -> None:
        for idx in range(1, 8):
            fig_path = DEFAULT_FIGURES_DIR / f"FIG-0{idx}.png"
            self.assertTrue(fig_path.exists(), f"Missing canonical figure {fig_path}")
            self.assertGreater(fig_path.stat().st_size, 50_000, f"Canonical figure {fig_path} is too small")
            width, height, dpi_x, dpi_y = _read_png_dimensions_and_dpi(fig_path)
            self.assertGreater(width, 2000)
            self.assertGreater(height, 1000)
            self.assertAlmostEqual(dpi_x, 300.0, delta=1.0)
            self.assertAlmostEqual(dpi_y, 300.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
