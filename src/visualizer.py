"""
src/visualizer.py — Publication-Quality Explanatory Visualization Suite (Issue #9).

Implements the 7 canonical figures (FIG-01 through FIG-07) specified in
`docs/roadmap.md` (Week 07, Section 7.1) following Edward Tufte's Data-Ink
maximization principles and William Cleveland's perceptual accuracy hierarchy:

- FIG-01: Multi-scale PM2.5 time series (hourly observations, causal 24-hour
  rolling mean, causal 7-day rolling mean) with averaging-period-matched
  regulatory reference lines (QCVN 05:2023/BTNMT 24h = 50 µg/m³, WHO 2021
  24h AQG = 15 µg/m³) and explicit missing-data outage shading.
- FIG-02: Empirical PM2.5 distribution (Histogram + Gaussian KDE + aligned
  horizontal Boxplot) illustrating right-skewness, leptokurtic tail behavior,
  and the "Shape Picks the Statistic" principle (Mean > Median > KDE Peak).
- FIG-03: Multi-tier Monthly (1–12) and Seasonal (Đông, Xuân, Hè, Thu) PM2.5
  boxplots with sample-size disclosures and non-parametric spread comparisons.
- FIG-04: 2D Diurnal × Day-of-Week Heatmap (7 days × 24 hours, UTC+7) of
  median PM2.5 concentrations using a colorblind-safe sequential palette.
- FIG-05: Bivariate Scatter Plot of meteorological drivers (default: wind_speed)
  vs. PM2.5 with non-parametric LOWESS smoothing and decile median profiles.
- FIG-06: Dual Correlation Matrix Heatmap (Pearson r & Spearman rho) across
  pollutant and meteorological variables, highlighting PM2.5–PM10 collinearity
  and circular-variable caveats for wind_direction.
- FIG-07: Air Quality Category Frequency Distribution Bar Chart computed on
  mathematically compatible causal 24-hour rolling averages against WHO 2021
  (24h AQG & Interim Targets) and QCVN 05:2023/BTNMT (24h limit = 50 µg/m³),
  enforcing a strict zero baseline (ylim bottom = 0) and dual-denominator
  reporting (valid 24h windows vs. total study hours).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import matplotlib
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.flag_evidence import (  # noqa: E402
    SEASON_COLUMN,
    SEASON_DISPLAY_ORDER,
    SEASON_LABELS_VI,
    SEASON_MONTHS,
    TIMESTAMP_COLUMN,
)

# ---------------------------------------------------------------------------
# Constants & Canonical Paths
# ---------------------------------------------------------------------------

DEFAULT_DPI: int = 300
DEFAULT_DATA_PATH: Path = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
DEFAULT_FIGURES_DIR: Path = REPO_ROOT / "figures"

STATION_COLUMN: str = "station_id"
TARGET_COLUMN: str = "pm25"
LOCAL_TZ: str = "Asia/Ho_Chi_Minh"

# Cross-platform Vietnamese-capable font priority list (Task 2.2).
# DejaVu Sans is bundled with Matplotlib on all platforms and covers all 77
# Vietnamese diacritics plus scientific symbols (°, µ, ², −, –).
FONT_FALLBACK_ORDER: Tuple[str, ...] = (
    "DejaVu Sans",
    "Segoe UI",
    "Liberation Sans",
    "DejaVu Serif",
    "sans-serif",
)

# Regulatory thresholds (µg/m³) with explicit averaging periods and standards.
# Note: QCVN 05:2023/BTNMT defines limits at standard reference conditions
# (25 °C, 760 mmHg, µg/Nm³), whereas OpenAQ stations report ambient µg/m³.
QCVN_2023_PM25_24H_LIMIT: float = 50.0
QCVN_2023_PM25_ANNUAL_LIMIT: float = 25.0
WHO_2021_PM25_24H_AQG: float = 15.0
WHO_2021_PM25_ANNUAL_AQG: float = 5.0

# WHO 2021 24-hour Interim Targets & AQG boundaries (µg/m³)
WHO_QCVN_24H_BINS: Tuple[float, ...] = (0.0, 15.0, 25.0, 37.5, 50.0, 75.0, float("inf"))

# Default causal rolling window parameters
DEFAULT_ROLLING_24H_WINDOW: int = 24
DEFAULT_ROLLING_24H_MIN_PERIODS: int = 24
DEFAULT_ROLLING_7D_WINDOW: int = 168
DEFAULT_ROLLING_7D_MIN_PERIODS: int = 126

# Colorblind-safe Okabe-Ito & Viridis-derived semantic palette
PALETTE: Dict[str, str] = {
    "hourly_raw": "#9ecae1",
    "rolling_24h": "#0072B2",      # Okabe-Ito Blue
    "rolling_7d": "#D55E00",       # Okabe-Ito Vermilion
    "qcvn_24h": "#E69F00",         # Okabe-Ito Orange
    "who_24h": "#009E73",          # Okabe-Ito Bluish Green
    "mean_line": "#D55E00",        # Vermilion
    "median_line": "#0072B2",      # Blue
    "kde_peak": "#CC79A7",         # Reddish Purple
    "quantile_line": "#56B4E9",    # Sky Blue
    "outage_shade": "#d9d9d9",
    "spine": "#4a4a4a",
    "grid": "#d0d0d0",
}

WEATHER_LABELS_VI: Dict[str, Tuple[str, str]] = {
    "wind_speed": ("Tốc độ gió", "m/s"),
    "temperature": ("Nhiệt độ không khí", "°C"),
    "relative_humidity": ("Độ ẩm tương đối", "%"),
    "surface_pressure": ("Áp suất bề mặt", "hPa"),
    "precipitation": ("Lượng mưa tích lũy giờ", "mm"),
    "wind_direction": ("Hướng gió (biến góc tuần hoàn)", "°"),
    "pm10": ("Nồng độ bụi PM10", "µg/m³"),
    "pm25": ("Nồng độ bụi PM2.5", "µg/m³"),
}

CORRELATION_VARIABLES: Tuple[str, ...] = (
    "pm25",
    "pm10",
    "wind_speed",
    "temperature",
    "surface_pressure",
    "relative_humidity",
    "precipitation",
    "wind_direction",
)

CORRELATION_SHORT_LABELS_VI: Dict[str, str] = {
    "pm25": "PM2.5\n(µg/m³)",
    "pm10": "PM10\n(µg/m³)",
    "wind_speed": "Tốc độ gió\n(m/s)",
    "temperature": "Nhiệt độ\n(°C)",
    "surface_pressure": "Áp suất\n(hPa)",
    "relative_humidity": "Độ ẩm\n(%)",
    "precipitation": "Lượng mưa\n(mm)",
    "wind_direction": "Hướng gió*\n(° chu kỳ)",
}

DOW_LABELS_VI: Tuple[str, ...] = (
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
)


class MissingColumnError(KeyError, ValueError):
    """Exception raised when required DataFrame columns are missing.

    Inherits from both ``KeyError`` and ``ValueError`` so callers catching
    either standard exception type handle it seamlessly.
    """


# ---------------------------------------------------------------------------
# Font, Style, and Output Helpers
# ---------------------------------------------------------------------------


def configure_vietnamese_fonts() -> str:
    """Configure Matplotlib rcParams with a verified Vietnamese-capable font.

    Returns
    -------
    str
        The primary font family name selected on the current platform.
    """
    available_fonts = {f.name for f in fm.fontManager.ttflist}
    ordered_families: List[str] = []
    for candidate in FONT_FALLBACK_ORDER:
        if candidate == "sans-serif" or candidate in available_fonts:
            ordered_families.append(candidate)
    if not ordered_families:
        ordered_families = ["DejaVu Sans", "sans-serif"]

    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = ordered_families
    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["figure.dpi"] = 100
    matplotlib.rcParams["savefig.dpi"] = DEFAULT_DPI
    return ordered_families[0]


def apply_tufte_style(
    ax: plt.Axes,
    *,
    grid_axis: str = "y",
    despine_left: bool = False,
) -> None:
    """Apply Edward Tufte's Data-Ink optimization to a Matplotlib Axes.

    Removes non-data ink (top and right spines), softens remaining axis spines,
    and configures subtle background gridlines behind data artists.
    """
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if despine_left:
        ax.spines["left"].set_visible(False)
    else:
        ax.spines["left"].set_color(PALETTE["spine"])
        ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_color(PALETTE["spine"])
    ax.spines["bottom"].set_linewidth(0.8)

    ax.tick_params(axis="both", colors="#2b2b2b", labelsize=9.5)
    if grid_axis in ("x", "y", "both"):
        ax.grid(
            True,
            axis=grid_axis,
            linestyle="--",
            linewidth=0.6,
            color=PALETTE["grid"],
            alpha=0.55,
        )
        ax.set_axisbelow(True)
    else:
        ax.grid(False)


def _save_figure(
    fig: Figure,
    output_path: Optional[Union[str, Path]],
    dpi: int = DEFAULT_DPI,
) -> Optional[Path]:
    """Save a Matplotlib Figure at publication resolution (300 DPI) if requested."""
    if output_path is None:
        return None
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        out,
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.15,
        facecolor="white",
        edgecolor="none",
    )
    return out


# ---------------------------------------------------------------------------
# Input Validation & Time-Series Preparation Helpers
# ---------------------------------------------------------------------------


def _validate_and_prepare_df(
    df: pd.DataFrame,
    required_cols: Sequence[str],
    *,
    require_timestamp: bool = True,
    require_valid_pm25: bool = True,
) -> pd.DataFrame:
    """Validate input DataFrame and return a clean copy without mutating the caller's frame."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}.")
    if df.empty:
        raise ValueError("Input DataFrame is empty; cannot generate visualization.")

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise MissingColumnError(
            f"Missing required column(s): {missing}. Available columns: {list(df.columns)}"
        )

    work = df.copy()

    if require_timestamp and TIMESTAMP_COLUMN in work.columns:
        ts_raw = work[TIMESTAMP_COLUMN]
        if pd.api.types.is_numeric_dtype(ts_raw) or pd.api.types.is_bool_dtype(ts_raw):
            raise ValueError(
                f"Column '{TIMESTAMP_COLUMN}' must contain datetime or ISO timestamp strings, "
                f"got dtype '{ts_raw.dtype}'."
            )
        try:
            ts = pd.to_datetime(ts_raw, errors="raise")
        except Exception as exc:
            raise ValueError(
                f"Column '{TIMESTAMP_COLUMN}' contains unparseable timestamps: {exc}"
            ) from exc

        if ts.isna().any():
            raise ValueError(
                f"Column '{TIMESTAMP_COLUMN}' contains {int(ts.isna().sum())} NaT values."
            )

        if ts.dt.tz is None:
            ts = ts.dt.tz_localize(LOCAL_TZ)
        else:
            ts = ts.dt.tz_convert(LOCAL_TZ)

        work[TIMESTAMP_COLUMN] = ts
        sort_cols = (
            [STATION_COLUMN, TIMESTAMP_COLUMN]
            if STATION_COLUMN in work.columns
            else [TIMESTAMP_COLUMN]
        )
        work = work.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)

    if require_valid_pm25 and TARGET_COLUMN in work.columns:
        pm25_numeric = pd.to_numeric(work[TARGET_COLUMN], errors="coerce")
        if pm25_numeric.dropna().empty:
            raise ValueError(
                f"Column '{TARGET_COLUMN}' contains no valid (non-NaN) numeric observations."
            )
        work[TARGET_COLUMN] = pm25_numeric

    return work


def compute_causal_rolling_pm25(
    df: pd.DataFrame,
    *,
    min_periods_24h: int = DEFAULT_ROLLING_24H_MIN_PERIODS,
    min_periods_7d: int = DEFAULT_ROLLING_7D_MIN_PERIODS,
) -> pd.DataFrame:
    """Compute station-grouped, time-aware causal trailing 24h and 7d rolling means.

    Uses time-indexed windows ``"24h"`` and ``"168h"`` with ``closed="right"``
    (strictly causal: ``(t - window, t]``, never ``center=True``) within each
    ``station_id`` so irregular timestamp gaps never pull distant observations
    into the same fixed row count window. On a regular hourly grid without
    timestamp gaps, ``rolling("24h", min_periods=k)`` is mathematically
    identical to ``rolling(window=24, min_periods=k)``.
    """
    work = _validate_and_prepare_df(
        df,
        [TIMESTAMP_COLUMN, TARGET_COLUMN],
        require_timestamp=True,
        require_valid_pm25=True,
    )

    if min_periods_24h < 1 or min_periods_24h > DEFAULT_ROLLING_24H_WINDOW:
        raise ValueError(
            f"min_periods_24h must be in [1, {DEFAULT_ROLLING_24H_WINDOW}], got {min_periods_24h}."
        )
    if min_periods_7d < 1 or min_periods_7d > DEFAULT_ROLLING_7D_WINDOW:
        raise ValueError(
            f"min_periods_7d must be in [1, {DEFAULT_ROLLING_7D_WINDOW}], got {min_periods_7d}."
        )

    def _roll_group(group: pd.DataFrame) -> pd.DataFrame:
        indexed = group.set_index(TIMESTAMP_COLUMN)[TARGET_COLUMN]
        r24 = indexed.rolling(
            "24h", min_periods=min_periods_24h, closed="right"
        ).mean()
        r7d = indexed.rolling(
            "168h", min_periods=min_periods_7d, closed="right"
        ).mean()
        out = group.copy()
        out["rolling_24h"] = r24.to_numpy()
        out["rolling_7d"] = r7d.to_numpy()
        return out

    if STATION_COLUMN in work.columns and work[STATION_COLUMN].nunique() > 1:
        parts = [
            _roll_group(grp)
            for _, grp in work.groupby(STATION_COLUMN, sort=False)
        ]
        result = pd.concat(parts, axis=0).sort_index().reset_index(drop=True)
    else:
        result = _roll_group(work)

    return result


def _find_missing_spans(
    df: pd.DataFrame,
    min_span_hours: int = 24,
) -> List[Tuple[pd.Timestamp, pd.Timestamp, int]]:
    """Identify contiguous NaN spans in ``pm25`` lasting at least ``min_span_hours`` rows."""
    is_na = df[TARGET_COLUMN].isna()
    if not is_na.any():
        return []

    run_id = is_na.ne(is_na.shift()).cumsum()
    spans: List[Tuple[pd.Timestamp, pd.Timestamp, int]] = []
    for _, grp in df[is_na].groupby(run_id[is_na]):
        n_hours = len(grp)
        if n_hours >= min_span_hours:
            spans.append(
                (
                    grp[TIMESTAMP_COLUMN].iloc[0],
                    grp[TIMESTAMP_COLUMN].iloc[-1],
                    n_hours,
                )
            )
    return spans


# ---------------------------------------------------------------------------
# FIG-01: Multi-Scale Time Series & Regulatory Reference Lines
# ---------------------------------------------------------------------------


def plot_fig01_time_series(
    df: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    *,
    min_periods_24h: int = DEFAULT_ROLLING_24H_MIN_PERIODS,
    min_periods_7d: int = DEFAULT_ROLLING_7D_MIN_PERIODS,
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """Generate FIG-01: Hourly PM2.5, causal 24h & 7d rolling trends, and 24h limits.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataset containing ``timestamp`` and ``pm25`` (and optionally ``station_id``).
    output_path : str or Path, optional
        Destination path to save the 300 DPI PNG.
    min_periods_24h : int, default 24
        Minimum valid hourly observations required inside a trailing 24-hour window.
    min_periods_7d : int, default 126
        Minimum valid hourly observations required inside a trailing 168-hour (7-day) window.
    dpi : int, default 300
        Output resolution in dots per inch.

    Returns
    -------
    matplotlib.figure.Figure
    """
    configure_vietnamese_fonts()
    work = compute_causal_rolling_pm25(
        df,
        min_periods_24h=min_periods_24h,
        min_periods_7d=min_periods_7d,
    )

    n_total = len(work)
    n_valid_hourly = int(work[TARGET_COLUMN].notna().sum())
    n_missing_hourly = n_total - n_valid_hourly

    r24_valid = work["rolling_24h"].dropna()
    n_valid_24h = len(r24_valid)
    n_exceed_qcvn = int((r24_valid >= QCVN_2023_PM25_24H_LIMIT).sum())
    pct_exceed_qcvn_valid = (
        (n_exceed_qcvn / n_valid_24h) * 100.0 if n_valid_24h > 0 else 0.0
    )
    pct_exceed_qcvn_all = (n_exceed_qcvn / n_total) * 100.0 if n_total > 0 else 0.0

    r24_peak_val = float(r24_valid.max()) if not r24_valid.empty else float("nan")
    if not r24_valid.empty:
        peak_idx = int(work["rolling_24h"].idxmax())
        r24_peak_ts = work.loc[peak_idx, TIMESTAMP_COLUMN]
        peak_date_str = r24_peak_ts.strftime("%d/%m/%Y")
    else:
        r24_peak_ts = work[TIMESTAMP_COLUMN].iloc[0]
        peak_date_str = "N/A"

    r7d_valid = work["rolling_7d"].dropna()
    r7d_peak_val = float(r7d_valid.max()) if not r7d_valid.empty else float("nan")

    fig, ax = plt.subplots(figsize=(14, 6.2))
    apply_tufte_style(ax, grid_axis="y")

    # 1. Shade major missing-data spans (>= 24h) to preserve missingness transparency
    long_spans = _find_missing_spans(work, min_span_hours=24)
    for idx_span, (t_start, t_end, span_h) in enumerate(long_spans):
        ax.axvspan(
            t_start,
            t_end,
            color=PALETTE["outage_shade"],
            alpha=0.55,
            zorder=1,
            label=(
                f"Khoảng trống quan trắc ≥24h (không nội suy; đợt dài nhất {max(s[2] for s in long_spans)}h)"
                if idx_span == 0
                else None
            ),
        )

    # 2. Plot hourly raw series (background context), 24h rolling mean, and 7d rolling trend
    ax.plot(
        work[TIMESTAMP_COLUMN],
        work[TARGET_COLUMN],
        color=PALETTE["hourly_raw"],
        alpha=0.45,
        linewidth=0.65,
        zorder=2,
        label=f"PM2.5 quan trắc theo giờ (n = {n_valid_hourly:,}/{n_total:,} giờ; thiếu {n_missing_hourly:,} giờ)",
    )
    ax.plot(
        work[TIMESTAMP_COLUMN],
        work["rolling_24h"],
        color=PALETTE["rolling_24h"],
        linewidth=1.35,
        alpha=0.90,
        zorder=3,
        label=(
            f"Trung bình trượt nhân quả 24h (window=24h, min_periods={min_periods_24h}; "
            f"n={n_valid_24h:,} cửa sổ hợp lệ)"
        ),
    )
    ax.plot(
        work[TIMESTAMP_COLUMN],
        work["rolling_7d"],
        color=PALETTE["rolling_7d"],
        linewidth=2.3,
        zorder=4,
        label=f"Xu hướng trượt nhân quả 7 ngày (168h, min_periods={min_periods_7d})",
    )

    # 3. Averaging-period-matched 24-hour reference thresholds (explicitly tied to rolling_24h)
    ax.axhline(
        QCVN_2023_PM25_24H_LIMIT,
        color=PALETTE["qcvn_24h"],
        linestyle="--",
        linewidth=1.6,
        zorder=3,
        label=(
            f"QCVN 05:2023/BTNMT — Giới hạn TB 24 giờ PM2.5: {QCVN_2023_PM25_24H_LIMIT:.0f} µg/m³ "
            "(chỉ đối chiếu với đường trượt 24h)"
        ),
    )
    ax.axhline(
        WHO_2021_PM25_24H_AQG,
        color=PALETTE["who_24h"],
        linestyle=":",
        linewidth=1.5,
        zorder=3,
        label=(
            f"WHO 2021 AQG — Khuyến nghị TB 24 giờ PM2.5: {WHO_2021_PM25_24H_AQG:.0f} µg/m³ "
            "(chỉ đối chiếu với đường trượt 24h)"
        ),
    )

    # 4. Annotate empirical 24h rolling peak and longest station outage
    if not r24_valid.empty:
        ax.scatter(
            [r24_peak_ts],
            [r24_peak_val],
            color=PALETTE["rolling_7d"],
            s=45,
            zorder=5,
        )
        ax.annotate(
            f"Đỉnh TB trượt 24h: {r24_peak_val:.1f} µg/m³\n({peak_date_str})",
            xy=(r24_peak_ts, r24_peak_val),
            xytext=(15, 10),
            textcoords="offset points",
            fontsize=8.8,
            fontweight="bold",
            color="#2b2b2b",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#fff8dc", edgecolor="#d9a441", alpha=0.9),
            arrowprops=dict(arrowstyle="->", color="#555555", lw=0.9),
        )

    if long_spans:
        longest_start, longest_end, longest_h = max(long_spans, key=lambda item: item[2])
        mid_ts = longest_start + (longest_end - longest_start) / 2
        y_top = float(work[TARGET_COLUMN].max())
        ax.annotate(
            f"Trạm ngừng gửi dữ liệu\n({longest_h} giờ liên tiếp:\n"
            f"{longest_start.strftime('%d/%m')}–{longest_end.strftime('%d/%m/%Y')})",
            xy=(mid_ts, y_top * 0.55),
            ha="center",
            va="center",
            fontsize=8.2,
            color="#444444",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#999999", alpha=0.92),
        )

    t_min_str = work[TIMESTAMP_COLUMN].min().strftime("%d/%m/%Y")
    t_max_str = work[TIMESTAMP_COLUMN].max().strftime("%d/%m/%Y")

    # Data-driven takeaway title & methodology subtitle
    title_text = (
        f"FIG-01: Chuỗi trượt 24h PM2.5 vượt ngưỡng 24h QCVN 05:2023/BTNMT (50 µg/m³) trong "
        f"{pct_exceed_qcvn_valid:.1f}% cửa sổ hợp lệ ({n_exceed_qcvn:,}/{n_valid_24h:,}; "
        f"đỉnh 24h đạt {r24_peak_val:.1f} µg/m³)"
    )
    subtitle_text = (
        f"Trạm 556 Nguyễn Văn Cừ ({t_min_str}–{t_max_str}, UTC+7) | "
        f"Vượt QCVN 24h tính trên tổng {n_total:,} giờ: {pct_exceed_qcvn_all:.1f}% | "
        f"Đỉnh trượt 7 ngày: {r7d_peak_val:.1f} µg/m³ | "
        "Lưu ý đơn vị: OpenAQ đo µg/m³ thực tế, QCVN quy định µg/Nm³ (25 °C, 760 mmHg)"
    )

    ax.set_title(title_text, fontsize=11.5, fontweight="bold", loc="left", pad=22)
    ax.text(
        0.0,
        1.015,
        subtitle_text,
        transform=ax.transAxes,
        fontsize=8.6,
        color="#4a4a4a",
        ha="left",
        va="bottom",
    )

    ax.set_xlabel("Thời gian quan trắc (Giờ địa phương Asia/Ho_Chi_Minh, UTC+7)", fontsize=10, fontweight="bold")
    ax.set_ylabel("Nồng độ bụi mịn PM2.5 (µg/m³)", fontsize=10, fontweight="bold")
    ax.set_ylim(bottom=0, top=max(float(work[TARGET_COLUMN].max()) * 1.12, 65.0))

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.legend(
        loc="upper left",
        frameon=True,
        facecolor="white",
        edgecolor="#dcdcdc",
        fontsize=8.4,
        ncol=2,
    )

    fig.tight_layout()
    _save_figure(fig, output_path, dpi=dpi)
    return fig


# ---------------------------------------------------------------------------
# FIG-02: Empirical Distribution (Histogram + KDE + Boxplot)
# ---------------------------------------------------------------------------


def plot_fig02_distribution(
    df: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    *,
    bins: int = 55,
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """Generate FIG-02: Empirical PM2.5 distribution (Histogram + KDE + Boxplot).

    Focuses strictly on the empirical hourly distribution shape and the 4 metric
    families without overlaying 24-hour regulatory thresholds onto hourly bars.
    """
    configure_vietnamese_fonts()
    work = _validate_and_prepare_df(
        df,
        [TARGET_COLUMN],
        require_timestamp=False,
        require_valid_pm25=True,
    )

    pm25 = work[TARGET_COLUMN].dropna()
    n_valid = len(pm25)
    n_missing = int(work[TARGET_COLUMN].isna().sum())
    n_total = len(work)

    mean_val = float(pm25.mean())
    median_val = float(pm25.median())
    std_val = float(pm25.std(ddof=1)) if n_valid > 1 else 0.0
    q1 = float(pm25.quantile(0.25))
    q3 = float(pm25.quantile(0.75))
    iqr_val = q3 - q1
    p90 = float(pm25.quantile(0.90))
    p95 = float(pm25.quantile(0.95))
    p99 = float(pm25.quantile(0.99))
    max_val = float(pm25.max())

    skew_val = float(stats.skew(pm25, bias=False)) if n_valid > 2 else 0.0
    kurt_val = float(stats.kurtosis(pm25, bias=False, fisher=True)) if n_valid > 3 else 0.0

    # Continuous modal density proxy via Gaussian KDE (exact discrete mode is NaN for continuous float)
    if n_valid >= 5 and std_val > 0:
        kde = stats.gaussian_kde(pm25)
        x_grid = np.linspace(float(pm25.min()), max_val, 1000)
        kde_vals = kde(x_grid)
        kde_peak = float(x_grid[int(np.argmax(kde_vals))])
    else:
        x_grid = np.linspace(float(pm25.min()), max_val + 1.0, 100)
        kde_vals = np.zeros_like(x_grid)
        kde_peak = median_val

    pct_mean_above_median = (
        ((mean_val - median_val) / median_val) * 100.0 if median_val != 0 else 0.0
    )

    fig, (ax_hist, ax_box) = plt.subplots(
        2,
        1,
        figsize=(12.5, 6.8),
        sharex=True,
        gridspec_kw={"height_ratios": [3.6, 1.0]},
    )
    apply_tufte_style(ax_hist, grid_axis="y")
    apply_tufte_style(ax_box, grid_axis="x")

    # 1. Histogram + KDE curve
    ax_hist.hist(
        pm25,
        bins=bins,
        density=True,
        color="#6baed6",
        edgecolor="white",
        linewidth=0.45,
        alpha=0.65,
        label=f"Mật độ thực nghiệm PM2.5 theo giờ (n = {n_valid:,})",
    )
    if np.any(kde_vals > 0):
        ax_hist.plot(
            x_grid,
            kde_vals,
            color="#08306b",
            linewidth=2.0,
            label="Ước lượng mật độ hạt nhân Gaussian KDE",
        )

    # 2. Central tendency & tail quantile lines
    ax_hist.axvline(
        kde_peak,
        color=PALETTE["kde_peak"],
        linestyle=":",
        linewidth=2.0,
        label=f"Đỉnh mật độ KDE (Mode proxy): {kde_peak:.2f} µg/m³ (Mode rời rạc = NaN)",
    )
    ax_hist.axvline(
        median_val,
        color=PALETTE["median_line"],
        linestyle="-",
        linewidth=2.4,
        label=f"Trung vị (Median / P50): {median_val:.2f} µg/m³ (IQR = {iqr_val:.2f} µg/m³)",
    )
    ax_hist.axvline(
        mean_val,
        color=PALETTE["mean_line"],
        linestyle="--",
        linewidth=2.1,
        label=f"Trung bình (Mean): {mean_val:.2f} µg/m³ (Độ lệch chuẩn s = {std_val:.2f} µg/m³)",
    )
    ax_hist.axvline(
        p90,
        color="#2ca25f",
        linestyle="-.",
        linewidth=1.5,
        label=f"Phân vị P90: {p90:.2f} µg/m³ (P95 = {p95:.2f}, P99 = {p99:.2f} µg/m³)",
    )

    # 3. Summary stats box inside upper right of histogram
    stats_box_text = (
        "Bốn họ chỉ số thống kê (Shape Picks the Statistic):\n"
        f"• Cỡ mẫu: n = {n_valid:,} hợp lệ | n_missing = {n_missing:,} ({n_missing / n_total * 100:.1f}%)\n"
        f"• Vị trí: Mean ({mean_val:.2f}) > Median ({median_val:.2f}) > KDE Peak ({kde_peak:.2f} µg/m³)\n"
        f"• Phân tán: IQR = {iqr_val:.2f} µg/m³ (Q1 = {q1:.2f}, Q3 = {q3:.2f}) | s = {std_val:.2f} µg/m³\n"
        f"• Hình dạng: Skewness = {skew_val:+.3f} (lệch phải) | Excess Kurtosis = {kurt_val:+.3f} (đuôi dày)\n"
        f"• Đuôi cực trị: P90 = {p90:.1f} | P95 = {p95:.1f} | P99 = {p99:.1f} | Max = {max_val:.1f} µg/m³"
    )
    ax_hist.text(
        0.985,
        0.52,
        stats_box_text,
        transform=ax_hist.transAxes,
        fontsize=8.6,
        va="top",
        ha="right",
        bbox=dict(
            boxstyle="round,pad=0.45",
            facecolor="#f8f9fa",
            edgecolor="#b0b0b0",
            alpha=0.94,
        ),
    )

    title_text = (
        f"FIG-02: Phân phối PM2.5 lệch phải mạnh (Skewness = {skew_val:+.2f}, Kurtosis = {kurt_val:+.2f}) "
        f"kéo Mean ({mean_val:.2f}) cao hơn Median ({median_val:.2f} µg/m³) {pct_mean_above_median:+.1f}%"
    )
    subtitle_text = (
        f"Quy tắc 3 vế thực nghiệm: Mean ({mean_val:.2f}) > Median ({median_val:.2f}) > KDE Peak ({kde_peak:.2f} µg/m³) "
        f"| 50% quan sát trung tâm nằm trong Q1–Q3 [{q1:.1f}; {q3:.1f}] µg/m³ (IQR = {iqr_val:.2f} µg/m³)"
    )

    ax_hist.set_title(title_text, fontsize=11.5, fontweight="bold", loc="left", pad=22)
    ax_hist.text(
        0.0,
        1.018,
        subtitle_text,
        transform=ax_hist.transAxes,
        fontsize=8.7,
        color="#4a4a4a",
        ha="left",
        va="bottom",
    )
    ax_hist.set_ylabel("Mật độ xác suất (Density)", fontsize=10, fontweight="bold")
    ax_hist.legend(
        loc="upper right",
        frameon=True,
        facecolor="white",
        edgecolor="#dcdcdc",
        fontsize=8.4,
    )

    # 4. Aligned Horizontal Boxplot below (compatible across Matplotlib 3.8..3.11+)
    import inspect

    boxplot_orient_kw = (
        {"orientation": "horizontal"}
        if "orientation" in inspect.signature(ax_box.boxplot).parameters
        else {"vert": False}
    )
    bp = ax_box.boxplot(
        pm25,
        widths=0.52,
        patch_artist=True,
        showmeans=True,
        boxprops=dict(facecolor="#bdd7e7", edgecolor="#08519c", linewidth=1.2),
        medianprops=dict(color=PALETTE["median_line"], linewidth=2.4),
        meanprops=dict(
            marker="D",
            markerfacecolor=PALETTE["mean_line"],
            markeredgecolor="white",
            markersize=6.5,
        ),
        whiskerprops=dict(color="#08519c", linewidth=1.1),
        capprops=dict(color="#08519c", linewidth=1.1),
        flierprops=dict(
            marker="o",
            markerfacecolor="#d95f02",
            markeredgecolor="none",
            markersize=3.2,
            alpha=0.35,
        ),
        **boxplot_orient_kw,
    )
    _ = bp
    ax_box.axvline(median_val, color=PALETTE["median_line"], linestyle="-", linewidth=1.6, alpha=0.8)
    ax_box.axvline(mean_val, color=PALETTE["mean_line"], linestyle="--", linewidth=1.6, alpha=0.8)
    ax_box.set_yticks([1])
    ax_box.set_yticklabels(["Boxplot\n(IQR & Outliers)"], fontsize=9, fontweight="bold")
    ax_box.set_xlabel("Nồng độ bụi mịn PM2.5 theo giờ (µg/m³)", fontsize=10, fontweight="bold")
    ax_box.set_xlim(left=0, right=max_val * 1.04)

    fig.tight_layout()
    _save_figure(fig, output_path, dpi=dpi)
    return fig


# ---------------------------------------------------------------------------
# FIG-03: Monthly & Seasonal Boxplots
# ---------------------------------------------------------------------------


def plot_fig03_seasonal_monthly_boxplots(
    df: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    *,
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """Generate FIG-03: Monthly (1–12) and Seasonal (Đông/Xuân/Hè/Thu) PM2.5 boxplots."""
    configure_vietnamese_fonts()
    work = _validate_and_prepare_df(
        df,
        [TIMESTAMP_COLUMN, TARGET_COLUMN],
        require_timestamp=True,
        require_valid_pm25=True,
    )

    work["month"] = work[TIMESTAMP_COLUMN].dt.month
    if SEASON_COLUMN not in work.columns:
        work[SEASON_COLUMN] = work["month"].map(SEASON_MONTHS)

    valid_work = work.dropna(subset=[TARGET_COLUMN]).copy()
    n_valid_total = len(valid_work)
    n_missing_total = len(work) - n_valid_total

    # Monthly aggregations
    month_stats = (
        valid_work.groupby("month")[TARGET_COLUMN]
        .agg(
            n="count",
            mean="mean",
            median="median",
            q1=lambda s: s.quantile(0.25),
            q3=lambda s: s.quantile(0.75),
        )
        .reset_index()
    )
    max_m_row = month_stats.loc[month_stats["median"].idxmax()]
    min_m_row = month_stats.loc[month_stats["median"].idxmin()]
    peak_month = int(max_m_row["month"])
    peak_month_med = float(max_m_row["median"])
    low_month = int(min_m_row["month"])
    low_month_med = float(min_m_row["median"])

    # Seasonal aggregations in canonical meteorological order
    present_seasons = [
        s for s in SEASON_DISPLAY_ORDER if s in valid_work[SEASON_COLUMN].unique()
    ]
    season_stats = (
        valid_work.groupby(SEASON_COLUMN)[TARGET_COLUMN]
        .agg(
            n="count",
            mean="mean",
            median="median",
            q1=lambda s: s.quantile(0.25),
            q3=lambda s: s.quantile(0.75),
        )
        .reindex(present_seasons)
        .reset_index()
    )
    max_s_row = season_stats.loc[season_stats["median"].idxmax()]
    min_s_row = season_stats.loc[season_stats["median"].idxmin()]
    max_s_name = SEASON_LABELS_VI.get(str(max_s_row[SEASON_COLUMN]), str(max_s_row[SEASON_COLUMN]))
    min_s_name = SEASON_LABELS_VI.get(str(min_s_row[SEASON_COLUMN]), str(min_s_row[SEASON_COLUMN]))
    max_s_med = float(max_s_row["median"])
    min_s_med = float(min_s_row["median"])
    season_ratio = max_s_med / min_s_med if min_s_med > 0 else float("nan")

    fig, (ax_month, ax_season) = plt.subplots(
        1,
        2,
        figsize=(15.2, 6.4),
        sharey=True,
        gridspec_kw={"width_ratios": [2.05, 1.05]},
    )
    apply_tufte_style(ax_month, grid_axis="y")
    apply_tufte_style(ax_season, grid_axis="y")

    season_colors: Dict[str, str] = {
        "Dong": "#2b5c8f",  # Winter deep blue
        "Xuan": "#3690c0",  # Spring teal-blue
        "He": "#67a9cf",    # Summer sky blue
        "Thu": "#e69f00",   # Autumn amber
    }

    # Panel A: Monthly boxplots
    months_present = sorted(month_stats["month"].astype(int).tolist())
    month_groups = [
        valid_work.loc[valid_work["month"] == m, TARGET_COLUMN].to_numpy()
        for m in months_present
    ]
    bp_m = ax_month.boxplot(
        month_groups,
        positions=range(len(months_present)),
        widths=0.58,
        patch_artist=True,
        showmeans=True,
        medianprops=dict(color="#111111", linewidth=2.0),
        meanprops=dict(
            marker="D",
            markerfacecolor="#D55E00",
            markeredgecolor="white",
            markersize=5.2,
        ),
        flierprops=dict(
            marker="o",
            markerfacecolor="#7f7f7f",
            markeredgecolor="none",
            markersize=2.5,
            alpha=0.30,
        ),
    )
    for patch, m in zip(bp_m["boxes"], months_present):
        s_code = SEASON_MONTHS.get(m, "Dong")
        patch.set_facecolor(season_colors.get(s_code, "#67a9cf"))
        patch.set_alpha(0.78)
        patch.set_edgecolor("#2b2b2b")

    month_tick_labels = [
        f"T{m:02d}\n(n={int(month_stats.loc[month_stats['month'] == m, 'n'].iloc[0])})"
        for m in months_present
    ]
    ax_month.set_xticks(range(len(months_present)))
    ax_month.set_xticklabels(month_tick_labels, fontsize=8.4)
    ax_month.set_xlabel("Chu kỳ 12 Tháng trong năm (kèm cỡ mẫu quan sát n mỗi tháng)", fontsize=9.8, fontweight="bold")
    ax_month.set_ylabel("Nồng độ bụi mịn PM2.5 theo giờ (µg/m³)", fontsize=10, fontweight="bold")
    ax_month.set_title(
        f"A. Phân phối theo Tháng: Đỉnh Tháng {peak_month:02d} (Median {peak_month_med:.1f} µg/m³) "
        f"vs Đáy Tháng {low_month:02d} ({low_month_med:.1f} µg/m³)",
        fontsize=10.2,
        fontweight="bold",
        loc="left",
        pad=8,
    )

    # Panel B: Seasonal boxplots
    season_groups = [
        valid_work.loc[valid_work[SEASON_COLUMN] == s, TARGET_COLUMN].to_numpy()
        for s in present_seasons
    ]
    bp_s = ax_season.boxplot(
        season_groups,
        positions=range(len(present_seasons)),
        widths=0.52,
        patch_artist=True,
        showmeans=True,
        medianprops=dict(color="#111111", linewidth=2.2),
        meanprops=dict(
            marker="D",
            markerfacecolor="#D55E00",
            markeredgecolor="white",
            markersize=6.0,
        ),
        flierprops=dict(
            marker="o",
            markerfacecolor="#7f7f7f",
            markeredgecolor="none",
            markersize=2.5,
            alpha=0.30,
        ),
    )
    for patch, s_code in zip(bp_s["boxes"], present_seasons):
        patch.set_facecolor(season_colors.get(s_code, "#67a9cf"))
        patch.set_alpha(0.82)
        patch.set_edgecolor("#2b2b2b")

    season_month_note = {
        "Dong": "Th12–Th02",
        "Xuan": "Th03–Th05",
        "He": "Th06–Th08",
        "Thu": "Th09–Th11",
    }
    season_tick_labels = []
    for idx_s, s_code in enumerate(present_seasons):
        row_s = season_stats.loc[season_stats[SEASON_COLUMN] == s_code].iloc[0]
        s_vi = SEASON_LABELS_VI.get(s_code, s_code)
        m_range = season_month_note.get(s_code, "")
        season_tick_labels.append(
            f"Mùa {s_vi}\n({m_range})\n(n={int(row_s['n']):,})"
        )
        # Direct data label for median and IQR above each seasonal box
        ax_season.text(
            idx_s,
            float(row_s["q3"]) + 6.0,
            f"Med: {float(row_s['median']):.1f}\n(IQR: {float(row_s['q3'] - row_s['q1']):.1f})",
            ha="center",
            va="bottom",
            fontsize=8.1,
            fontweight="bold",
            color="#1f1f1f",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#cccccc", alpha=0.88),
        )

    ax_season.set_xticks(range(len(present_seasons)))
    ax_season.set_xticklabels(season_tick_labels, fontsize=8.5)
    ax_season.set_xlabel("Chu kỳ 4 Mùa Khí tượng Bắc Bộ (kèm cỡ mẫu n)", fontsize=9.8, fontweight="bold")
    ax_season.set_title(
        f"B. Phân phối theo Mùa: Mùa {max_s_name} ({max_s_med:.1f} µg/m³) "
        f"gấp {season_ratio:.2f}× Mùa {min_s_name} ({min_s_med:.1f} µg/m³)",
        fontsize=10.2,
        fontweight="bold",
        loc="left",
        pad=8,
    )
    ax_month.set_ylim(bottom=0, top=float(valid_work[TARGET_COLUMN].max()) * 1.12)

    legend_handles = [
        Patch(facecolor=season_colors["Dong"], edgecolor="#2b2b2b", alpha=0.8, label="Mùa Đông (Th12–Th02)"),
        Patch(facecolor=season_colors["Xuan"], edgecolor="#2b2b2b", alpha=0.8, label="Mùa Xuân (Th03–Th05)"),
        Patch(facecolor=season_colors["He"], edgecolor="#2b2b2b", alpha=0.8, label="Mùa Hè (Th06–Th08)"),
        Patch(facecolor=season_colors["Thu"], edgecolor="#2b2b2b", alpha=0.8, label="Mùa Thu (Th09–Th11)"),
        plt.Line2D([0], [0], color="#111111", lw=2.0, label="Trung vị (Median / P50)"),
        plt.Line2D(
            [0],
            [0],
            marker="D",
            color="w",
            markerfacecolor="#D55E00",
            markersize=6,
            label="Trung bình số học (Mean)",
        ),
    ]
    ax_month.legend(
        handles=legend_handles,
        loc="upper right",
        ncol=3,
        fontsize=8.2,
        frameon=True,
        facecolor="white",
        edgecolor="#dcdcdc",
    )

    fig.suptitle(
        f"FIG-03: Trung vị PM2.5 Mùa {max_s_name} ({max_s_med:.2f} µg/m³) cao gấp {season_ratio:.2f} lần "
        f"Mùa {min_s_name} ({min_s_med:.2f} µg/m³); cực đại tại Tháng {peak_month:02d} ({peak_month_med:.2f} µg/m³)",
        fontsize=12.0,
        fontweight="bold",
        x=0.01,
        y=0.99,
        ha="left",
    )
    fig.text(
        0.01,
        0.935,
        f"Tổng mẫu quan sát hợp lệ: n = {n_valid_total:,} giờ (loại {n_missing_total:,} giờ thiếu PM2.5; "
        "Tháng 07/2026 bị ảnh hưởng bởi đợt trạm ngừng gửi dữ liệu 630 giờ từ 19/06–15/07/2026)",
        fontsize=8.8,
        color="#4a4a4a",
        ha="left",
    )

    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.92])
    _save_figure(fig, output_path, dpi=dpi)
    return fig


# ---------------------------------------------------------------------------
# FIG-04: 2D Diurnal × Day-of-Week Heatmap
# ---------------------------------------------------------------------------


def plot_fig04_diurnal_weekly_heatmap(
    df: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    *,
    agg_func: str = "median",
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """Generate FIG-04: 2D Heatmap of Hour-of-Day (0–23) × Day-of-Week (Mon–Sun) PM2.5."""
    configure_vietnamese_fonts()
    if agg_func not in ("median", "mean"):
        raise ValueError(f"agg_func must be 'median' or 'mean', got '{agg_func}'.")

    work = _validate_and_prepare_df(
        df,
        [TIMESTAMP_COLUMN, TARGET_COLUMN],
        require_timestamp=True,
        require_valid_pm25=True,
    )

    valid_work = work.dropna(subset=[TARGET_COLUMN]).copy()
    valid_work["hour"] = valid_work[TIMESTAMP_COLUMN].dt.hour
    valid_work["dayofweek"] = valid_work[TIMESTAMP_COLUMN].dt.dayofweek

    pivot = valid_work.pivot_table(
        index="dayofweek",
        columns="hour",
        values=TARGET_COLUMN,
        aggfunc=agg_func,
    )
    pivot = pivot.reindex(index=range(7), columns=range(24))

    hourly_marginal = valid_work.groupby("hour")[TARGET_COLUMN].agg(agg_func)
    peak_hour = int(hourly_marginal.idxmax())
    peak_hour_val = float(hourly_marginal.max())
    trough_hour = int(hourly_marginal.idxmin())
    trough_hour_val = float(hourly_marginal.min())

    is_weekend = valid_work["dayofweek"].isin([5, 6])
    weekend_val = (
        float(valid_work.loc[is_weekend, TARGET_COLUMN].agg(agg_func))
        if is_weekend.any()
        else float("nan")
    )
    weekday_val = (
        float(valid_work.loc[~is_weekend, TARGET_COLUMN].agg(agg_func))
        if (~is_weekend).any()
        else float("nan")
    )
    ww_diff = weekend_val - weekday_val

    arr = pivot.to_numpy(dtype=float)
    if np.all(np.isnan(arr)):
        raise ValueError("Heatmap pivot table contains only NaN values.")
    max_pos = np.unravel_index(int(np.nanargmax(arr)), arr.shape)
    min_pos = np.unravel_index(int(np.nanargmin(arr)), arr.shape)
    cell_max_val = float(arr[max_pos])
    cell_min_val = float(arr[min_pos])
    cell_max_day = DOW_LABELS_VI[int(max_pos[0])]
    cell_max_hour = int(max_pos[1])
    cell_min_day = DOW_LABELS_VI[int(min_pos[0])]
    cell_min_hour = int(min_pos[1])

    metric_label_vi = "Trung vị (Median)" if agg_func == "median" else "Trung bình (Mean)"

    fig, ax = plt.subplots(figsize=(14.5, 5.8))
    sns.heatmap(
        pivot,
        ax=ax,
        cmap="viridis",
        annot=True,
        fmt=".0f",
        annot_kws={"size": 7.8, "weight": "bold"},
        linewidths=0.45,
        linecolor="white",
        cbar_kws={
            "label": f"{metric_label_vi} nồng độ PM2.5 (µg/m³)",
            "shrink": 0.92,
            "pad": 0.02,
        },
    )

    dow_counts = valid_work.groupby("dayofweek")[TARGET_COLUMN].count().reindex(range(7), fill_value=0)
    y_labels = [
        f"{DOW_LABELS_VI[d]}\n(n={int(dow_counts.loc[d]):,})"
        for d in range(7)
    ]
    ax.set_yticklabels(y_labels, rotation=0, fontsize=9.0, fontweight="bold")
    ax.set_xticklabels([f"{h:02d}:00" for h in range(24)], rotation=0, fontsize=8.4)

    ax.set_xlabel(
        "Khung giờ trong ngày (00:00 – 23:00, Giờ địa phương Asia/Ho_Chi_Minh UTC+7)",
        fontsize=10,
        fontweight="bold",
    )
    ax.set_ylabel("Thứ trong tuần (Thứ Hai – Chủ Nhật)", fontsize=10, fontweight="bold")

    title_text = (
        f"FIG-04: {metric_label_vi} PM2.5 đạt đỉnh chu kỳ ngày lúc {peak_hour:02d}:00 ({peak_hour_val:.1f} µg/m³), "
        f"thấp nhất lúc {trough_hour:02d}:00 ({trough_hour_val:.1f} µg/m³); "
        f"Cuối tuần chênh {ww_diff:+.1f} µg/m³ so với Ngày thường"
    )
    subtitle_text = (
        f"Ma trận 7 ngày × 24 giờ (n = {len(valid_work):,} giờ hợp lệ) | "
        f"Ô cao nhất: {cell_max_day} {cell_max_hour:02d}:00 ({cell_max_val:.1f} µg/m³) | "
        f"Ô thấp nhất: {cell_min_day} {cell_min_hour:02d}:00 ({cell_min_val:.1f} µg/m³) | "
        f"Cuối tuần ({weekend_val:.1f}) vs Ngày thường ({weekday_val:.1f} µg/m³)"
    )

    ax.set_title(title_text, fontsize=11.3, fontweight="bold", loc="left", pad=22)
    ax.text(
        0.0,
        1.022,
        subtitle_text,
        transform=ax.transAxes,
        fontsize=8.6,
        color="#4a4a4a",
        ha="left",
        va="bottom",
    )

    fig.tight_layout()
    _save_figure(fig, output_path, dpi=dpi)
    return fig


# ---------------------------------------------------------------------------
# FIG-05: Meteorological Driver vs. PM2.5 Scatter + Non-Parametric LOWESS
# ---------------------------------------------------------------------------


def plot_fig05_weather_lowess(
    df: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    *,
    weather_col: str = "wind_speed",
    lowess_frac: float = 0.25,
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """Generate FIG-05: Bivariate Scatter of a meteorological variable vs. PM2.5 with LOWESS.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame containing ``pm25`` and ``weather_col``.
    output_path : str or Path, optional
        Output PNG file path.
    weather_col : str, default ``"wind_speed"``
        Meteorological predictor column name.
    lowess_frac : float, default 0.25
        Smoothing span fraction for ``statsmodels`` LOWESS smoother.
    dpi : int, default 300
        Output resolution in dots per inch.
    """
    configure_vietnamese_fonts()
    work = _validate_and_prepare_df(
        df,
        [TARGET_COLUMN, weather_col],
        require_timestamp=False,
        require_valid_pm25=True,
    )

    work[weather_col] = pd.to_numeric(work[weather_col], errors="coerce")
    paired = work[[weather_col, TARGET_COLUMN]].dropna().copy()
    if len(paired) < 3:
        raise ValueError(
            f"Need at least 3 valid paired observations for '{weather_col}' and '{TARGET_COLUMN}', "
            f"got {len(paired)}."
        )

    x = paired[weather_col].to_numpy(dtype=float)
    y = paired[TARGET_COLUMN].to_numpy(dtype=float)
    n_paired = len(paired)
    n_dropped = len(work) - n_paired

    r_pearson = float(paired[weather_col].corr(paired[TARGET_COLUMN], method="pearson"))
    rho_spearman = float(paired[weather_col].corr(paired[TARGET_COLUMN], method="spearman"))

    # Compute non-parametric LOWESS smoothing curve on sorted unique/paired data
    lowess_xy = lowess(y, x, frac=lowess_frac, it=2, return_sorted=True)
    lx = lowess_xy[:, 0]
    ly = lowess_xy[:, 1]
    lowess_start_val = float(ly[0])
    lowess_end_val = float(ly[-1])

    var_name_vi, var_unit = WEATHER_LABELS_VI.get(weather_col, (weather_col, ""))
    unit_suffix = f" ({var_unit})" if var_unit else ""

    fig, ax = plt.subplots(figsize=(11.8, 6.2))
    apply_tufte_style(ax, grid_axis="both")

    # 1. Scatter plot with transparent alpha to mitigate overplotting
    ax.scatter(
        x,
        y,
        color="#4393c3",
        alpha=0.18,
        s=14,
        edgecolors="none",
        zorder=2,
        label=f"Quan trắc đồng thời theo giờ (n = {n_paired:,} cặp hợp lệ)",
    )

    # 2. Binned decile medians + IQR error bars for clear structural reading
    if pd.Series(x).nunique() >= 6 and n_paired >= 30:
        paired["bin"] = pd.qcut(paired[weather_col], q=10, duplicates="drop")
        bin_stats = (
            paired.groupby("bin", observed=True)
            .agg(
                x_med=(weather_col, "median"),
                y_med=(TARGET_COLUMN, "median"),
                y_q1=(TARGET_COLUMN, lambda s: s.quantile(0.25)),
                y_q3=(TARGET_COLUMN, lambda s: s.quantile(0.75)),
            )
            .dropna()
        )
        ax.errorbar(
            bin_stats["x_med"],
            bin_stats["y_med"],
            yerr=[
                bin_stats["y_med"] - bin_stats["y_q1"],
                bin_stats["y_q3"] - bin_stats["y_med"],
            ],
            fmt="o",
            color="#08306b",
            ecolor="#08306b",
            elinewidth=1.2,
            capsize=3,
            markersize=5.2,
            zorder=4,
            label="Trung vị PM2.5 theo 10 phân vị (kèm thanh sai số IQR: Q1–Q3)",
        )

    # 3. Non-parametric LOWESS curve
    ax.plot(
        lx,
        ly,
        color=PALETTE["rolling_7d"],
        linewidth=2.8,
        zorder=5,
        label=(
            f"Đường làm mượt phi tham số LOWESS (frac={lowess_frac:.2f}): "
            f"{lowess_start_val:.1f} → {lowess_end_val:.1f} µg/m³"
        ),
    )

    direction_vi = (
        "nghịch biến" if rho_spearman < -0.05 else ("đồng biến" if rho_spearman > 0.05 else "gần như độc lập biên")
    )
    title_text = (
        f"FIG-05: {var_name_vi} liên hệ {direction_vi} phi tuyến với PM2.5 "
        f"(Spearman rho = {rho_spearman:+.2f}, Pearson r = {r_pearson:+.2f}); "
        f"xu hướng LOWESS từ {lowess_start_val:.1f} xuống {lowess_end_val:.1f} µg/m³"
        if lowess_end_val <= lowess_start_val
        else (
            f"FIG-05: {var_name_vi} liên hệ {direction_vi} phi tuyến với PM2.5 "
            f"(Spearman rho = {rho_spearman:+.2f}, Pearson r = {r_pearson:+.2f}); "
            f"xu hướng LOWESS từ {lowess_start_val:.1f} lên {lowess_end_val:.1f} µg/m³"
        )
    )
    subtitle_text = (
        f"Phân tích cặp biến hoàn chỉnh (Pairwise complete-case: n = {n_paired:,} giờ; "
        f"loại {n_dropped:,} giờ thiếu dữ liệu) | "
        "Quan hệ quan sát thực nghiệm (observational association), không suy diễn nhân quả trực tiếp"
    )

    ax.set_title(title_text, fontsize=11.3, fontweight="bold", loc="left", pad=22)
    ax.text(
        0.0,
        1.018,
        subtitle_text,
        transform=ax.transAxes,
        fontsize=8.6,
        color="#4a4a4a",
        ha="left",
        va="bottom",
    )

    ax.set_xlabel(f"{var_name_vi}{unit_suffix}", fontsize=10, fontweight="bold")
    ax.set_ylabel("Nồng độ bụi mịn PM2.5 theo giờ (µg/m³)", fontsize=10, fontweight="bold")
    ax.set_ylim(bottom=0, top=float(paired[TARGET_COLUMN].max()) * 1.06)

    ax.legend(
        loc="upper right",
        frameon=True,
        facecolor="white",
        edgecolor="#dcdcdc",
        fontsize=8.8,
    )

    fig.tight_layout()
    _save_figure(fig, output_path, dpi=dpi)
    return fig


# ---------------------------------------------------------------------------
# FIG-06: Dual Correlation Matrix Heatmap (Pearson r & Spearman rho)
# ---------------------------------------------------------------------------


def plot_fig06_correlation_heatmap(
    df: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    *,
    columns: Optional[Sequence[str]] = None,
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """Generate FIG-06: Dual Pearson (r) & Spearman (rho) Correlation Heatmap."""
    configure_vietnamese_fonts()
    if columns is None:
        selected_cols = [c for c in CORRELATION_VARIABLES if c in df.columns]
        if TARGET_COLUMN not in selected_cols:
            selected_cols = [TARGET_COLUMN] + selected_cols
    else:
        selected_cols = list(columns)

    if len(selected_cols) < 2:
        raise MissingColumnError(
            f"Need at least 2 numeric columns for correlation matrix, found {selected_cols}."
        )

    work = _validate_and_prepare_df(
        df,
        selected_cols,
        require_timestamp=False,
        require_valid_pm25=(TARGET_COLUMN in selected_cols),
    )

    for col in selected_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    cc_df = work[selected_cols].dropna()
    n_total = len(work)
    n_complete = len(cc_df)
    if n_complete < 3:
        raise ValueError(
            f"Need at least 3 complete-case rows across {selected_cols}, got {n_complete}."
        )

    corr_pearson = cc_df.corr(method="pearson")
    corr_spearman = cc_df.corr(method="spearman")

    labels = [CORRELATION_SHORT_LABELS_VI.get(c, c) for c in selected_cols]

    # Identify strongest correlations with pm25
    if TARGET_COLUMN in selected_cols:
        pm25_p = corr_pearson[TARGET_COLUMN].drop(labels=[TARGET_COLUMN], errors="ignore")
        pm25_s = corr_spearman[TARGET_COLUMN].drop(labels=[TARGET_COLUMN], errors="ignore")
        top_pos_col = str(pm25_p.idxmax()) if not pm25_p.empty else selected_cols[0]
        top_pos_r = float(pm25_p.max()) if not pm25_p.empty else float("nan")
        weather_subset = pm25_s.drop(labels=["pm10"], errors="ignore")
        if not weather_subset.empty:
            top_neg_col = str(weather_subset.idxmin())
            top_neg_rho = float(weather_subset.min())
        else:
            top_neg_col = top_pos_col
            top_neg_rho = float(pm25_s.min())
    else:
        top_pos_col = selected_cols[0]
        top_pos_r = float(corr_pearson.iloc[0, 1])
        top_neg_col = selected_cols[1]
        top_neg_rho = float(corr_spearman.iloc[0, 1])

    fig, (ax_p, ax_s) = plt.subplots(1, 2, figsize=(15.5, 6.8))

    sns.heatmap(
        corr_pearson,
        ax=ax_p,
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        center=0.0,
        annot=True,
        fmt=".2f",
        annot_kws={"size": 8.3, "weight": "bold"},
        xticklabels=labels,
        yticklabels=labels,
        linewidths=0.6,
        linecolor="white",
        cbar=False,
    )
    ax_p.set_title(
        f"A. Ma trận Tương quan Tuyến tính Pearson (r)\n(Complete-case N = {n_complete:,}/{n_total:,} dòng)",
        fontsize=10.5,
        fontweight="bold",
        pad=10,
    )
    ax_p.tick_params(axis="x", rotation=30, labelsize=8.6)
    ax_p.tick_params(axis="y", rotation=0, labelsize=8.6)

    sns.heatmap(
        corr_spearman,
        ax=ax_s,
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        center=0.0,
        annot=True,
        fmt=".2f",
        annot_kws={"size": 8.3, "weight": "bold"},
        xticklabels=labels,
        yticklabels=labels,
        linewidths=0.6,
        linecolor="white",
        cbar_kws={
            "label": "Hệ số tương quan (-1.0 đến +1.0)",
            "shrink": 0.88,
            "pad": 0.03,
        },
    )
    ax_s.set_title(
        f"B. Ma trận Tương quan Hạng Đơn điệu Spearman (rho)\n(Bền vững trước ngoại lai & quan hệ phi tuyến)",
        fontsize=10.5,
        fontweight="bold",
        pad=10,
    )
    ax_s.tick_params(axis="x", rotation=30, labelsize=8.6)
    ax_s.tick_params(axis="y", rotation=0, labelsize=8.6)

    r2_collinear = (top_pos_r ** 2) * 100.0 if not np.isnan(top_pos_r) else float("nan")
    fig.suptitle(
        f"FIG-06: PM2.5 cộng tuyến rất mạnh với {top_pos_col.upper()} (Pearson r = {top_pos_r:+.2f}, "
        f"R² = {r2_collinear:.1f}%) và tương quan nghịch với {top_neg_col} (Spearman rho = {top_neg_rho:+.2f})",
        fontsize=12.0,
        fontweight="bold",
        x=0.01,
        y=0.99,
        ha="left",
    )
    fig.text(
        0.01,
        0.935,
        f"Cỡ mẫu Complete-case: N = {n_complete:,}/{n_total:,} giờ ({n_complete / n_total * 100:.1f}%) | "
        "*Lưu ý phương pháp luận: Hướng gió (wind_direction) là biến góc tuần hoàn (0° ≡ 360°; Circular Mean = 107.1° ESE) "
        "nên hệ số r/rho tuyến tính chỉ mang tính tham khảo hình thức.",
        fontsize=8.6,
        color="#4a4a4a",
        ha="left",
    )

    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.91])
    _save_figure(fig, output_path, dpi=dpi)
    return fig


# ---------------------------------------------------------------------------
# FIG-07: Air Quality Category Frequency Distribution Bar Chart (Zero Baseline)
# ---------------------------------------------------------------------------


def plot_fig07_air_quality_categories(
    df: pd.DataFrame,
    output_path: Optional[Union[str, Path]] = None,
    *,
    min_periods_24h: int = DEFAULT_ROLLING_24H_MIN_PERIODS,
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """Generate FIG-07: Bar chart of 24-hour rolling PM2.5 across WHO 2021 & QCVN 05:2023 tiers.

    Enforces a strict zero baseline (``ylim(bottom=0)``) and classifies only
    mathematically compatible trailing 24-hour rolling averages (never raw
    single-hour observations) against 24-hour regulatory thresholds.
    """
    configure_vietnamese_fonts()
    work = compute_causal_rolling_pm25(
        df,
        min_periods_24h=min_periods_24h,
        min_periods_7d=min(DEFAULT_ROLLING_7D_MIN_PERIODS, len(df)),
    )

    n_total = len(work)
    r24 = work["rolling_24h"]
    valid_r24 = r24.dropna()
    if valid_r24.empty:
        raise ValueError(
            f"No valid 24-hour rolling windows found with min_periods_24h={min_periods_24h}."
        )

    n_valid = len(valid_r24)
    n_excluded = n_total - n_valid

    tier_labels = [
        "< 15 µg/m³\nĐạt WHO 2021\n24h AQG",
        "15 – <25 µg/m³\nWHO 2021\n24h IT-4",
        "25 – <37.5 µg/m³\nWHO 2021\n24h IT-3",
        "37.5 – <50 µg/m³\nĐạt QCVN 05:2023\n24h (WHO IT-2)",
        "50 – <75 µg/m³\nVượt QCVN 24h\n(WHO 2021 IT-1)",
        "≥ 75 µg/m³\nVượt WHO IT-1 &\nQCVN 24h (Rất cao)",
    ]
    tier_colors = [
        "#009E73",  # Bluish green (meets WHO AQG)
        "#56B4E9",  # Sky blue (IT-4)
        "#9ecae1",  # Light blue (IT-3)
        "#F0E442",  # Yellow (IT-2 / meets QCVN <=50)
        "#E69F00",  # Orange (Exceeds QCVN 24h)
        "#D55E00",  # Vermilion (Severe exceedance >=75)
    ]

    categories = pd.cut(
        valid_r24,
        bins=list(WHO_QCVN_24H_BINS),
        labels=tier_labels,
        right=False,
        include_lowest=True,
    )
    counts = categories.value_counts(sort=False).reindex(tier_labels, fill_value=0)
    pct_valid = (counts / n_valid) * 100.0
    pct_all = (counts / n_total) * 100.0

    n_exceed_qcvn = int((valid_r24 >= QCVN_2023_PM25_24H_LIMIT).sum())
    pct_exceed_qcvn_valid = (n_exceed_qcvn / n_valid) * 100.0
    pct_exceed_qcvn_all = (n_exceed_qcvn / n_total) * 100.0

    n_meet_who = int((valid_r24 < WHO_2021_PM25_24H_AQG).sum())
    pct_meet_who_valid = (n_meet_who / n_valid) * 100.0

    fig, ax = plt.subplots(figsize=(13.2, 6.4))
    apply_tufte_style(ax, grid_axis="y")

    x_pos = np.arange(len(tier_labels))
    bars = ax.bar(
        x_pos,
        counts.to_numpy(dtype=float),
        width=0.62,
        color=tier_colors,
        edgecolor="#2b2b2b",
        linewidth=0.9,
        zorder=3,
    )

    # Vertical divider separating compliant (< 50 µg/m³) vs exceedance (>= 50 µg/m³) QCVN 24h tiers
    ax.axvline(
        3.5,
        color="#b30000",
        linestyle="--",
        linewidth=1.6,
        zorder=4,
    )
    max_bar_height = float(counts.max()) if len(counts) > 0 else 1.0
    ax.text(
        3.56,
        max_bar_height * 0.96,
        "Ranh giới QCVN 05:2023/BTNMT\n"
        "(Giới hạn TB 24h = 50 µg/m³)\n"
        f"→ Vượt ngưỡng: {n_exceed_qcvn:,}/{n_valid:,} cửa sổ\n"
        f"  • {pct_exceed_qcvn_valid:.1f}% trên mẫu hợp lệ\n"
        f"  • {pct_exceed_qcvn_all:.1f}% trên tổng {n_total:,} giờ",
        fontsize=8.3,
        fontweight="bold",
        color="#8c0000",
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.32", facecolor="#fff5f0", edgecolor="#d95f02", alpha=0.94),
    )

    # Direct labels (n, % of valid windows, % of all rows) on top of each bar
    for bar, count_val, pv, pa in zip(bars, counts, pct_valid, pct_all):
        height = float(bar.get_height())
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + max_bar_height * 0.018,
            f"n = {int(count_val):,}\n{pv:.1f}% (hợp lệ)\n({pa:.1f}% toàn chuỗi)",
            ha="center",
            va="bottom",
            fontsize=8.2,
            fontweight="bold",
            color="#1f1f1f",
        )

    ax.set_xticks(x_pos)
    ax.set_xticklabels(tier_labels, fontsize=8.8, fontweight="bold")
    ax.set_xlim(-0.55, len(tier_labels) - 0.35)
    ax.set_xlabel(
        "Bậc phân loại nồng độ PM2.5 trung bình trượt 24 giờ (µg/m³) theo WHO 2021 (AQG & Interim Targets) và QCVN 05:2023/BTNMT",
        fontsize=9.8,
        fontweight="bold",
    )
    ax.set_ylabel("Số lượng cửa sổ trượt 24 giờ hợp lệ (n)", fontsize=10, fontweight="bold")

    # Non-negotiable zero baseline for bar chart quantitative axis
    ax.set_ylim(bottom=0.0, top=max_bar_height * 1.24)

    title_text = (
        f"FIG-07: {pct_exceed_qcvn_valid:.1f}% cửa sổ TB trượt 24h hợp lệ ({n_exceed_qcvn:,}/{n_valid:,}) "
        f"vượt ngưỡng 24h QCVN 05:2023/BTNMT (50 µg/m³); chỉ {pct_meet_who_valid:.2f}% đạt WHO 2021 (15 µg/m³)"
    )
    subtitle_text = (
        f"Đại lượng phân loại: TB trượt nhân quả 24h PM2.5 (window=24h, min_periods={min_periods_24h}, center=False) | "
        f"Mẫu số 1: N_valid = {n_valid:,} cửa sổ 24h hợp lệ | "
        f"Mẫu số 2: N_all = {n_total:,} giờ (loại {n_excluded:,} cửa sổ thiếu dữ liệu, không nội suy)"
    )

    ax.set_title(title_text, fontsize=11.2, fontweight="bold", loc="left", pad=22)
    ax.text(
        0.0,
        1.018,
        subtitle_text,
        transform=ax.transAxes,
        fontsize=8.5,
        color="#4a4a4a",
        ha="left",
        va="bottom",
    )

    fig.tight_layout()
    _save_figure(fig, output_path, dpi=dpi)
    return fig


# ---------------------------------------------------------------------------
# Batch Orchestrator & CLI Entrypoint
# ---------------------------------------------------------------------------


def generate_all_figures(
    df: Optional[pd.DataFrame] = None,
    *,
    data_path: Union[str, Path] = DEFAULT_DATA_PATH,
    output_dir: Union[str, Path] = DEFAULT_FIGURES_DIR,
    dpi: int = DEFAULT_DPI,
) -> Dict[str, Path]:
    """Generate and save all 7 canonical explanatory figures (FIG-01..FIG-07) at 300 DPI.

    Closes every generated ``Figure`` via ``plt.close(fig)`` after saving to
    prevent memory leaks during batch execution or test runs.

    Returns
    -------
    dict[str, Path]
        Mapping from figure identifier (``"FIG-01"`` .. ``"FIG-07"``) to its saved PNG path.
    """
    if df is None:
        resolved_data = Path(data_path)
        if not resolved_data.exists():
            raise FileNotFoundError(
                f"Processed dataset not found at '{resolved_data}'. "
                "Run notebook 03_transformation_pipeline.ipynb or supply a DataFrame."
            )
        source_df = pd.read_parquet(resolved_data)
    else:
        source_df = df.copy()

    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    builders = [
        ("FIG-01", plot_fig01_time_series),
        ("FIG-02", plot_fig02_distribution),
        ("FIG-03", plot_fig03_seasonal_monthly_boxplots),
        ("FIG-04", plot_fig04_diurnal_weekly_heatmap),
        ("FIG-05", plot_fig05_weather_lowess),
        ("FIG-06", plot_fig06_correlation_heatmap),
        ("FIG-07", plot_fig07_air_quality_categories),
    ]

    saved_paths: Dict[str, Path] = {}
    for fig_id, builder in builders:
        target_path = out_root / f"{fig_id}.png"
        fig = builder(source_df, output_path=target_path, dpi=dpi)
        plt.close(fig)
        saved_paths[fig_id] = target_path

    return saved_paths


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint to generate FIG-01 through FIG-07 from the canonical Parquet dataset."""
    parser = argparse.ArgumentParser(
        description="Generate publication-ready figures FIG-01..FIG-07 (300 DPI PNG)."
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Path to processed Parquet file (default: data/processed/air_pollution_final.parquet).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_FIGURES_DIR,
        help="Directory to write FIG-01.png .. FIG-07.png (default: figures/).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help="Output PNG resolution in DPI (default: 300).",
    )
    args = parser.parse_args(argv)

    saved = generate_all_figures(
        data_path=args.data_path,
        output_dir=args.output_dir,
        dpi=args.dpi,
    )
    for fig_id, path in saved.items():
        size_kb = path.stat().st_size / 1024.0
        print(f"[OK] {fig_id}: {path} ({size_kb:.1f} KB, {args.dpi} DPI)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
