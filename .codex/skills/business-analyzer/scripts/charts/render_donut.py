"""
render_donut.py — Donut chart (share / composition by category).

Spec fields:
    group_by (required) : categorical column
    y        (required) : numeric column to aggregate (sum)
"""

import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BG      = "#0a0e1a"
SURFACE = "#111827"
TEXT    = "#f9fafb"
MUTED   = "#9ca3af"
BORDER  = "#1f2937"
PALETTE = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899","#06b6d4","#84cc16"]
DPI     = 150


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec",   required=True)
    parser.add_argument("--title",  default="Share")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec    = json.loads(args.spec)
    grp_col = spec.get("group_by")
    y_col   = spec.get("y")

    if not grp_col or not y_col:
        print(f"[render_donut] ERROR: spec needs 'group_by' and 'y'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    if grp_col not in df.columns or y_col not in df.columns:
        print("[render_donut] ERROR: columns missing in data.", file=sys.stderr)
        sys.exit(1)

    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df = df.dropna(subset=[grp_col, y_col])

    if df.empty:
        print("[render_donut] ERROR: No valid rows.", file=sys.stderr)
        sys.exit(1)

    grouped = df.groupby(grp_col)[y_col].sum().sort_values(ascending=False)

    # Collapse small slices into "Other" if more than 8 categories
    if len(grouped) > 8:
        top     = grouped.head(7)
        other   = grouped.iloc[7:].sum()
        grouped = pd.concat([top, pd.Series({"Other": other})])

    labels = grouped.index.tolist()
    values = grouped.values.tolist()
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
    total  = sum(values)

    fig, ax = plt.subplots(figsize=(7, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        colors=colors,
        autopct=lambda pct: f"{pct:.1f}%" if pct > 3 else "",
        startangle=140,
        wedgeprops={"width": 0.55, "edgecolor": BG, "linewidth": 2},
        pctdistance=0.75,
    )
    for at in autotexts:
        at.set_color(TEXT)
        at.set_fontsize(9)

    # Center text: total
    def fmt_center(v):
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}K"
        return f"{v:.0f}"

    ax.text(0, 0, fmt_center(total), ha="center", va="center",
            color=TEXT, fontsize=14, fontweight="bold")

    # Legend
    ax.legend(
        wedges, [f"{l}" for l in labels],
        loc="center left", bbox_to_anchor=(1, 0.5),
        frameon=False,
        labelcolor=MUTED,
        fontsize=9,
    )

    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_donut] saved: {args.output}")


if __name__ == "__main__":
    main()