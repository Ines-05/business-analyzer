"""
render_bar_grouped.py — Grouped bar chart (two categorical dimensions + numeric).

Spec fields:
    group_by  (required) : primary categorical column (X axis groups)
    color_by  (required) : secondary categorical column (bar colors within group)
    y         (required) : numeric column to aggregate (sum)
    top_n     (optional) : limit group_by to top N values by total y (default 8)
"""

import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

BG      = "#0a0e1a"
SURFACE = "#111827"
TEXT    = "#f9fafb"
MUTED   = "#9ca3af"
BORDER  = "#1f2937"
PALETTE = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16"]
DPI     = 150


def apply_theme(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)


def fmt_value(v):
    if abs(v) >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:     return f"{v/1_000:.0f}K"
    return f"{v:.0f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec",   required=True)
    parser.add_argument("--title",  default="Grouped Breakdown")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec     = json.loads(args.spec)
    grp_col  = spec.get("group_by")
    color_col = spec.get("color_by")
    y_col    = spec.get("y")
    top_n    = int(spec.get("top_n", 8))

    if not grp_col or not color_col or not y_col:
        print(f"[render_bar_grouped] ERROR: spec needs 'group_by', 'color_by', 'y'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    for col in [grp_col, color_col, y_col]:
        if col not in df.columns:
            print(f"[render_bar_grouped] ERROR: column '{col}' not in data.", file=sys.stderr)
            sys.exit(1)

    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df = df.dropna(subset=[grp_col, color_col, y_col])

    if df.empty:
        print("[render_bar_grouped] ERROR: No valid rows.", file=sys.stderr)
        sys.exit(1)

    # Limit groups to top_n by total y
    top_groups = (
        df.groupby(grp_col)[y_col].sum()
        .sort_values(ascending=False)
        .head(top_n)
        .index.tolist()
    )
    df = df[df[grp_col].isin(top_groups)]

    pivot = df.pivot_table(index=grp_col, columns=color_col, values=y_col, aggfunc="sum").fillna(0)
    pivot = pivot.loc[top_groups]  # keep original sort order

    groups    = pivot.index.tolist()
    sub_cats  = pivot.columns.tolist()
    n_groups  = len(groups)
    n_subs    = len(sub_cats)
    x         = np.arange(n_groups)
    bar_width = 0.8 / n_subs

    fig, ax = plt.subplots(figsize=(max(8, n_groups * 1.2), 5))
    apply_theme(ax, fig)
    ax.grid(axis="y", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)

    for i, sub in enumerate(sub_cats):
        offset = (i - n_subs / 2 + 0.5) * bar_width
        ax.bar(x + offset, pivot[sub].values, bar_width * 0.9,
               label=str(sub), color=PALETTE[i % len(PALETTE)], alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(groups, color=MUTED, fontsize=9,
                       rotation=30 if n_groups > 5 else 0, ha="right")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: fmt_value(v)))
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=8, title=color_col,
              title_fontsize=8)
    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_bar_grouped] saved: {args.output}")


if __name__ == "__main__":
    main()