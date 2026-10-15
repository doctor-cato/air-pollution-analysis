---
name: data-visualization
description: Design publication-quality statistical and time-series graphics adhering to Edward Tufte and William Cleveland principles, maximizing data-ink ratio, enforcing zero-baselines for bar charts, and generating conclusion-driven titles.
---

# Data Visualization Skill

## Purpose
Design, construct, and export publication-ready explanatory graphics that communicate complex time-series and atmospheric relationships. Adheres strictly to **Edward Tufte's Data-Ink Maximization** and **William Cleveland's Visual Channel Hierarchy**, replacing decorative clutter with honest axes, explicit units, conclusion-driven titles, and 300 DPI outputs.

## When to Use
- When executing Milestone 3 (Week 7) in `notebooks/03_exploratory_data_analysis.ipynb`.
- When generating the 7 Headline Explanatory Figures (FIG-01 through FIG-07) for reports.
- When creating regression diagnostic plots or classification Precision-Recall curves.
- When exporting publication-ready figures to `figures/`.

## Preconditions
- Aggregated or processed observational data available in Pandas.
- Figure directory exists (`figures/`).

## Procedure

### 1. The 7 Authoritative Project Figures
Implement the 7 designated explanatory charts defined in [`docs/roadmap.md`](../../../docs/roadmap.md):

| Figure ID | Chart Type | X-Axis | Y-Axis | Core Analytical Insight |
|---|---|---|---|---|
| **FIG-01** | Line + 7d & 30d Rolling Mean | Date (2023–2024) | $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) | Long-term winter pollution episodes vs. WHO guidelines |
| **FIG-02** | Histogram + KDE Overlay | $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) | Probability Density | Heavy right-skewness and median vs. mean divergence |
| **FIG-03** | Monthly Boxplots (Jan–Dec) | Calendar Month | $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) | Winter thermal inversion vs. summer monsoon scavenging |
| **FIG-04** | 2D Heatmap (Hour $\times$ Day) | Hour of Day ($0–23$) | Day of Week (Mon–Sun) | Morning ($7–9$h) and evening ($18–21$h) traffic rush peaks |
| **FIG-05** | Scatter + LOWESS Curve | Wind Speed ($\text{m/s}$) | $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$) | Non-linear dispersion dynamics; stagnation hazard ($<1\text{m/s}$) |
| **FIG-06** | Correlation Matrix Heatmap | Environmental Metrics | Environmental Metrics | Divergence between linear (Pearson) and monotonic (Spearman) |
| **FIG-07** | Categorical Bar Chart | Air Quality Categories | Percentage of Days ($\%$) | Proportion of hazardous days per national QCVN standards |

### 2. Tufte & Cleveland Visual Standards
- **Maximize Data-Ink Ratio:**
  - Strip top and right frame spines: `ax.spines[['top', 'right']].set_visible(False)`.
  - Use light, thin gridlines along the primary axis only: `ax.grid(axis='y', alpha=0.3, linestyle='--')`.
  - Prohibit decorative background colors, artificial gradients, and 3D perspectives.
- **Cleveland Channel Ordering:**
  - Encode quantitative metrics using **Position along a common scale** (scatter, dot, line plots) over area, angle, or color intensity.
  - Prohibit pie charts and donut charts entirely.
- **Honest Axis Scaling:**
  - **Bar Chart Rule:** All quantitative bar charts must start at zero ($y=0$). Truncating bar chart baselines is strictly forbidden.
  - Scatter/line plots must encompass the full meaningful range without misleading zoomed-in distortions.

### 3. Conclusion-Driven Title Formulation
Every final figure must state its primary empirical finding in the title, not merely name the axes:
- *Reject:* "Boxplot of PM2.5 across 12 months"
- *Accept:* *"Winter records 2.8x higher median PM2.5 than summer due to atmospheric temperature inversion"*
- Subtitles provide technical details: sample size ($N$), date range (2023–2024), and data source (OpenAQ / Open-Meteo).

### 4. Matplotlib Object-Oriented Styling Protocol
Always use the object-oriented API (`fig, ax = plt.subplots()`):
```python
fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
# Plotting logic...
ax.set_title("Winter records 2.8x higher median PM2.5 than summer", fontsize=12, fontweight='bold', pad=12)
ax.set_xlabel("Month of Year", fontsize=10)
ax.set_ylabel("PM2.5 Concentration (µg/m³)", fontsize=10)
ax.spines[['top', 'right']].set_visible(False)
fig.savefig('../figures/fig03_monthly_boxplots.png', dpi=300, bbox_inches='tight')
plt.close(fig)
```

## Validation
- Inspect every saved `.png` in `figures/` to confirm that text labels, units, and legends are fully legible at 100% zoom.
- Verify that every bar chart quantitative axis starts strictly at 0.0.
- Confirm color palettes are colorblind-friendly (e.g. `viridis`, `plasma`, or Seaborn `colorblind`).

## Failure Modes
- Omitting units of measurement from axes ($\mu\text{g/m}^3$, $\text{m/s}$, $^\circ\text{C}$).
- Using rainbow / jet colormaps that distort perception across luminance boundaries.
- Generating decorative visualizations that fail to communicate an analytical insight.

## Expected Output
1. The 7 publication-quality PNG figures exported to `figures/` at 300 DPI.
2. Modular plotting helpers maintained cleanly in `src/visualizer.py`.
