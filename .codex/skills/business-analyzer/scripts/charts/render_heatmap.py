"""
render_heatmap.py — Heatmap (intensity matrix across two categorical dimensions).

Spec fields:
    row   (required) : categorical column for rows
    col   (required) : categorical column for columns
    value (required) : numeric column to aggregate (sum)
    top_n (optional) : limit each axis to top N values (default 10)
"""

import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import numpy as np

BG      = "#0a0e1a"
SURFACE = "#111827"
TEXT    = "#f9fafb"
MUTED   = "#9ca3af"
BORDER  = "#1f2937"
DPI     = 150


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec",   required=True)
    parser.add_argument("--title",  default="Heatmap")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec    = json.loads(args.spec)
    row_col = spec.get("row")
    col_col = spec.get("col")
    val_col = spec.get("value")
    top_n   = int(spec.get("top_n", 10))

    if not row_col or not col_col or not val_col:
        print(f"[render_heatmap] ERROR: spec needs 'row', 'col', 'value'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    for c in [row_col, col_col, val_col]:
        if c not in df.columns:
            print(f"[render_heatmap] ERROR: column '{c}' not in data.", file=sys.stderr)
            sys.exit(1)

    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    df = df.dropna(subset=[row_col, col_col, val_col])

    if df.empty:
        print("[render_heatmap] ERROR: No valid rows.", file=sys.stderr)
        sys.exit(1)

    # Limit to top N per axis
    top_rows = df.groupby(row_col)[val_col].sum().nlargest(top_n).index
    top_cols = df.groupby(col_col)[val_col].sum().nlargest(top_n).index
    df = df[df[row_col].isin(top_rows) & df[col_col].isin(top_cols)]

    pivot = df.pivot_table(index=row_col, columns=col_col, values=val_col, aggfunc="sum").fillna(0)

    if pivot.empty:
        print("[render_heatmap] ERROR: Pivot table is empty.", file=sys.stderr)
        sys.exit(1)

    fig_h = max(4, len(pivot) * 0.5)
    fig_w = max(6, len(pivot.columns) * 0.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)

    im = ax.imshow(pivot.values, aspect="auto", cmap="Blues", interpolation="nearest")

    # Axis labels
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.tolist(), rotation=45, ha="right",
                       color=MUTED, fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist(), color=MUTED, fontsize=8)

    # Cell annotations
    max_val = pivot.values.max()
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            v = pivot.values[i, j]
            text_color = "white" if v > max_val * 0.6 else MUTED
            label = f"{v/1000:.0f}K" if v >= 1000 else f"{v:.0f}"
            ax.text(j, i, label, ha="center", va="center",
                    color=text_color, fontsize=7)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.ax.tick_params(colors=MUTED, labelsize=7)

    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_heatmap] saved: {args.output}")


if __name__ == "__main__":
    main()