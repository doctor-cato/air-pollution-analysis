"""
Generate report figures from processed data.

This script reads data/processed/air_pollution_final.parquet and generates
publication-quality figures for the project report.

Usage:
    python scripts/generate_report_figures.py

Requirements:
    - data/processed/air_pollution_final.parquet must exist
    - Run after Milestone 2 pipeline is complete
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Setup paths
project_root = Path(__file__).parent.parent
output_dir = project_root / "figures" / "report"
output_dir.mkdir(parents=True, exist_ok=True)

# Setup plotting style
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["font.size"] = 10
plt.rcParams["figure.dpi"] = 300
sns.set_theme(style="whitegrid")


def load_data() -> pd.DataFrame:
    """Load processed dataset."""
    data_path = project_root / "data" / "processed" / "air_pollution_final.parquet"
    if not data_path.exists():
        print(f"ERROR: {data_path} not found.")
        print("Please run the Milestone 2 pipeline first:")
        print("  python scripts/fetch_dataset.py")
        print("  jupyter nbconvert --execute notebooks/01_data_collection.ipynb")
        print("  jupyter nbconvert --execute notebooks/02_quality_audit.ipynb")
        sys.exit(1)
    return pd.read_parquet(data_path)


def plot_pm25_timeseries(df: pd.DataFrame) -> None:
    """Figure 1: PM2.5 over time."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df["timestamp"], df["pm25"], linewidth=0.8, alpha=0.8, color="#c0392b")
    ax.set_title("PM2.5 Concentration Over Time", fontsize=12, fontweight="bold")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("PM2.5 (µg/m³)")
    plt.tight_layout()
    fig.savefig(output_dir / "fig01_pm25_timeseries.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("✓ Figure 1: PM2.5 timeseries")


def plot_pm25_distribution(df: pd.DataFrame) -> None:
    """Figure 2: PM2.5 distribution."""
    fig, ax = plt.subplots(figsize=(10, 5))
    df["pm25"].dropna().hist(bins=50, ax=ax, edgecolor="black", alpha=0.7, color="#3498db")
    ax.set_title("PM2.5 Distribution", fontsize=12, fontweight="bold")
    ax.set_xlabel("PM2.5 (µg/m³)")
    ax.set_ylabel("Frequency")
    plt.tight_layout()
    fig.savefig(output_dir / "fig02_pm25_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("✓ Figure 2: PM2.5 distribution")


def plot_pm25_boxplot(df: pd.DataFrame) -> None:
    """Figure 3: PM2.5 boxplot by month."""
    df["month"] = df["timestamp"].dt.month
    fig, ax = plt.subplots(figsize=(10, 6))
    df.boxplot(column="pm25", by="month", ax=ax)
    ax.set_title("PM2.5 by Month", fontsize=12, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("PM2.5 (µg/m³)")
    plt.suptitle("")
    plt.tight_layout()
    fig.savefig(output_dir / "fig03_pm25_boxplot.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("✓ Figure 3: PM2.5 boxplot by month")


def plot_correlation(df: pd.DataFrame) -> None:
    """Figure 4: Correlation heatmap."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    corr = df[numeric_cols].corr()
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax)
    ax.set_title("Correlation Heatmap", fontsize=12, fontweight="bold")
    plt.tight_layout()
    fig.savefig(output_dir / "fig04_correlation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("✓ Figure 4: Correlation heatmap")


def plot_train_test_split(df: pd.DataFrame) -> None:
    """Figure 5: Train/Test timeline."""
    # Use 70% as default split for visualization
    split_idx = int(len(df) * 0.7)
    split_ts = df["timestamp"].iloc[split_idx]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df["timestamp"], df["pm25"], linewidth=0.8, alpha=0.8, color="#c0392b")
    ax.axvline(x=split_ts, color="green", linestyle="--", linewidth=2, label=f"Split: {split_ts}")
    ax.set_title("Train/Test Split Timeline", fontsize=12, fontweight="bold")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("PM2.5 (µg/m³)")
    ax.legend()
    plt.tight_layout()
    fig.savefig(output_dir / "fig05_train_test_split.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("✓ Figure 5: Train/Test split timeline")


def plot_missingness(df: pd.DataFrame) -> None:
    """Figure 6: Missingness heatmap."""
    missing = df.isnull().astype(int)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(missing.T, cbar=True, ax=ax, cmap="YlOrRd")
    ax.set_title("Missingness Heatmap", fontsize=12, fontweight="bold")
    ax.set_xlabel("Row Index")
    ax.set_ylabel("Column")
    plt.tight_layout()
    fig.savefig(output_dir / "fig06_missingness_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("✓ Figure 6: Missingness heatmap")


def main():
    print("=" * 60)
    print("Generating report figures...")
    print("=" * 60)

    df = load_data()
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    plot_pm25_timeseries(df)
    plot_pm25_distribution(df)
    plot_pm25_boxplot(df)
    plot_correlation(df)
    plot_train_test_split(df)
    plot_missingness(df)

    print("=" * 60)
    print(f"All figures saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
