"""
render_bar_horizontal.py — Horizontal bar chart (ranked breakdown by category).

Spec fields:
    group_by (required) : categorical column to group by
    y        (required) : numeric column to aggregate (sum)
    top_n    (optional) : max bars to show (default 10)
"""

import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

BG      = "#0a0e1a"
SURFACE = "#111827"
TEXT    = "#f9fafb"
MUTED   = "#9ca3af"
BORDER  = "#1f2937"
PALETTE = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16","#f97316","#a78bfa"]
DPI     = 150


def apply_theme(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)


def fmt_value(value):
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec",   required=True)
    parser.add_argument("--title",  default="Breakdown")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec     = json.loads(args.spec)
    grp_col  = spec.get("group_by")
    y_col    = spec.get("y")
    top_n    = int(spec.get("top_n", 10))

    if not grp_col or not y_col:
        print(f"[render_bar_horizontal] ERROR: spec needs 'group_by' and 'y'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    if grp_col not in df.columns or y_col not in df.columns:
        print(f"[render_bar_horizontal] ERROR: columns missing in data.", file=sys.stderr)
        sys.exit(1)

    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df = df.dropna(subset=[grp_col, y_col])

    if df.empty:
        print("[render_bar_horizontal] ERROR: No valid rows.", file=sys.stderr)
        sys.exit(1)

    grouped = (
        df.groupby(grp_col)[y_col]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
    )

    # Reverse so largest is at top of horizontal bar chart
    labels  = grouped.index.tolist()[::-1]
    values  = grouped.values.tolist()[::-1]
    colors  = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
    max_val = max(values) if values else 1

    fig_height = max(4, len(labels) * 0.55)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    apply_theme(ax, fig)

    ax.grid(axis="x", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="y", visible=False)

    bars = ax.barh(labels, values, color=colors, height=0.6)

    # Value labels on bars
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            fmt_value(value),
            va="center", color=TEXT, fontsize=9,
        )

    ax.set_xlim(0, max_val * 1.18)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: fmt_value(v)))
    ax.tick_params(axis="y", colors=MUTED)
    ax.tick_params(axis="x", colors=MUTED)
    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(y_col, color=MUTED, fontsize=10)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_bar_horizontal] saved: {args.output}")


if __name__ == "__main__":
    main()