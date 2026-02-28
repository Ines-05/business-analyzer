"""
render_funnel.py — Funnel chart (sequential stages with drop-off).

Spec fields:
    stage (required) : categorical column representing ordered stages
    value (required) : numeric column to aggregate (sum per stage)

Note: stages are ordered by descending value (largest = top of funnel).
If the data has a natural order (e.g. pipeline stages), ensure the column
values sort correctly or pre-sort in the CSV.
"""

import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np

BG      = "#0a0e1a"
SURFACE = "#111827"
ACCENT  = "#3b82f6"
TEXT    = "#f9fafb"
MUTED   = "#9ca3af"
BORDER  = "#1f2937"
PALETTE = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16"]
DPI     = 150


def fmt_value(v):
    if abs(v) >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:     return f"{v/1_000:.0f}K"
    return f"{v:.0f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec",   required=True)
    parser.add_argument("--title",  default="Funnel")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec      = json.loads(args.spec)
    stage_col = spec.get("stage")
    value_col = spec.get("value")

    if not stage_col or not value_col:
        print(f"[render_funnel] ERROR: spec needs 'stage' and 'value'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    for col in [stage_col, value_col]:
        if col not in df.columns:
            print(f"[render_funnel] ERROR: column '{col}' not in data.", file=sys.stderr)
            sys.exit(1)

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[stage_col, value_col])

    if df.empty:
        print("[render_funnel] ERROR: No valid rows.", file=sys.stderr)
        sys.exit(1)

    grouped = (
        df.groupby(stage_col)[value_col]
        .sum()
        .sort_values(ascending=False)
        .head(8)
    )

    stages = grouped.index.tolist()
    values = grouped.values.tolist()
    n      = len(stages)
    max_v  = values[0] if values else 1

    fig, ax = plt.subplots(figsize=(8, max(4, n * 0.9)))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.axis("off")

    bar_height = 0.65
    gap        = 0.1
    y_positions = list(range(n - 1, -1, -1))  # top to bottom

    for i, (stage, value, y) in enumerate(zip(stages, values, y_positions)):
        width  = (value / max_v)          # normalized width [0,1]
        left   = (1 - width) / 2          # center the bar
        color  = PALETTE[i % len(PALETTE)]

        # Trapezoid using polygon
        next_width = (values[i + 1] / max_v) if i + 1 < n else width * 0.7
        next_left  = (1 - next_width) / 2

        x_pts = [left,          left + width,
                 next_left + next_width, next_left]
        y_pts = [y + bar_height, y + bar_height,
                 y,               y]
        ax.fill(x_pts, y_pts, color=color, alpha=0.85, zorder=2)

        # Stage label (left)
        ax.text(-0.02, y + bar_height / 2, stage,
                ha="right", va="center", color=MUTED, fontsize=9)

        # Value label (center)
        ax.text(0.5, y + bar_height / 2, fmt_value(value),
                ha="center", va="center", color=TEXT,
                fontsize=10, fontweight="bold", zorder=3)

        # Conversion rate (right)
        if i > 0:
            pct = value / values[0] * 100
            ax.text(1.02, y + bar_height / 2, f"{pct:.0f}%",
                    ha="left", va="center", color=MUTED, fontsize=8)

    ax.set_xlim(-0.35, 1.2)
    ax.set_ylim(-0.3, n + 0.1)
    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_funnel] saved: {args.output}")


if __name__ == "__main__":
    main()