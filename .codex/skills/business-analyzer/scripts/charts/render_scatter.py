"""
render_scatter.py — Scatter plot (correlation between two numeric columns).

Spec fields:
    x      (required) : first numeric column (X axis)
    y      (required) : second numeric column (Y axis)
    label  (optional) : categorical column to color-code points
"""

import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
    parser.add_argument("--title",  default="Correlation")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec      = json.loads(args.spec)
    x_col     = spec.get("x")
    y_col     = spec.get("y")
    label_col = spec.get("label")

    if not x_col or not y_col:
        print(f"[render_scatter] ERROR: spec needs 'x' and 'y'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    for col in [x_col, y_col]:
        if col not in df.columns:
            print(f"[render_scatter] ERROR: column '{col}' not found.", file=sys.stderr)
            sys.exit(1)

    df[x_col] = pd.to_numeric(df[x_col], errors="coerce")
    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df = df.dropna(subset=[x_col, y_col])

    if len(df) < 3:
        print("[render_scatter] ERROR: Need at least 3 valid rows.", file=sys.stderr)
        sys.exit(1)

    fig, ax = plt.subplots(figsize=(8, 6))
    apply_theme(ax, fig)
    ax.grid(color=BORDER, linewidth=0.5, linestyle="--", alpha=0.5)

    if label_col and label_col in df.columns:
        categories = df[label_col].dropna().unique()
        for i, cat in enumerate(categories[:8]):
            mask = df[label_col] == cat
            ax.scatter(df.loc[mask, x_col], df.loc[mask, y_col],
                       color=PALETTE[i % len(PALETTE)], alpha=0.75,
                       s=50, label=str(cat), zorder=3)
        ax.legend(frameon=False, labelcolor=MUTED, fontsize=8,
                  title=label_col, title_fontsize=8)
    else:
        ax.scatter(df[x_col], df[y_col], color=ACCENT, alpha=0.65, s=50, zorder=3)

    # Trend line
    try:
        z = np.polyfit(df[x_col], df[y_col], 1)
        p = np.poly1d(z)
        x_line = np.linspace(df[x_col].min(), df[x_col].max(), 100)
        ax.plot(x_line, p(x_line), color=MUTED, linewidth=1.2,
                linestyle="--", alpha=0.6, zorder=2)
    except Exception:
        pass

    ax.set_xlabel(x_col, color=MUTED, fontsize=10)
    ax.set_ylabel(y_col, color=MUTED, fontsize=10)
    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_scatter] saved: {args.output}")


if __name__ == "__main__":
    main()