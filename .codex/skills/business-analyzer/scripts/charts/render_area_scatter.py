"""
render_area_stacked.py — Stacked area chart (part-of-whole over time).

Spec fields:
    x        (required) : date/time column
    y        (required) : numeric column
    stack_by (required) : categorical column to stack by
    top_n    (optional) : limit stack_by to top N categories (default 6)
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
PALETTE = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]
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
    parser.add_argument("--title",  default="Stacked Trend")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec     = json.loads(args.spec)
    x_col    = spec.get("x")
    y_col    = spec.get("y")
    stack_col = spec.get("stack_by")
    top_n    = int(spec.get("top_n", 6))

    if not x_col or not y_col or not stack_col:
        print(f"[render_area_stacked] ERROR: spec needs 'x', 'y', 'stack_by'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    for col in [x_col, y_col, stack_col]:
        if col not in df.columns:
            print(f"[render_area_stacked] ERROR: column '{col}' not in data.", file=sys.stderr)
            sys.exit(1)

    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df["_period"] = pd.to_datetime(df[x_col], errors="coerce")
    df = df.dropna(subset=["_period", y_col, stack_col])

    if df.empty:
        print("[render_area_stacked] ERROR: No valid rows.", file=sys.stderr)
        sys.exit(1)

    # Keep top N categories
    top_cats = (
        df.groupby(stack_col)[y_col].sum()
        .sort_values(ascending=False)
        .head(top_n)
        .index.tolist()
    )
    df_filtered = df[df[stack_col].isin(top_cats)].copy()

    # Determine aggregation granularity
    days = (df["_period"].max() - df["_period"].min()).days
    if days <= 90:
        df_filtered["_label"] = df_filtered["_period"].dt.strftime("%b %d")
    elif days <= 730:
        df_filtered["_label"] = df_filtered["_period"].dt.strftime("%b %Y")
    else:
        df_filtered["_label"] = df_filtered["_period"].dt.strftime("%Y")

    pivot = (
        df_filtered.pivot_table(index="_label", columns=stack_col, values=y_col, aggfunc="sum")
        .fillna(0)
    )
    # Sort index chronologically using the original date
    label_order = (
        df_filtered.drop_duplicates("_label")
        .sort_values("_period")["_label"]
        .tolist()
    )
    pivot = pivot.reindex([l for l in label_order if l in pivot.index])

    if pivot.empty or len(pivot) < 2:
        print("[render_area_stacked] ERROR: Not enough time periods to plot.", file=sys.stderr)
        sys.exit(1)

    fig, ax = plt.subplots(figsize=(11, 5))
    apply_theme(ax, fig)
    ax.grid(axis="y", color=BORDER, linewidth=0.5, linestyle="--", alpha=0.4)

    x_pos = list(range(len(pivot)))
    ax.stackplot(
        x_pos,
        [pivot[cat].values for cat in pivot.columns],
        labels=pivot.columns.tolist(),
        colors=PALETTE[:len(pivot.columns)],
        alpha=0.85,
    )

    rotation = 45 if len(pivot) > 8 else 0
    ax.set_xticks(x_pos)
    ax.set_xticklabels(pivot.index.tolist(), rotation=rotation,
                       ha="right" if rotation else "center", color=MUTED, fontsize=9)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: fmt_value(v)))
    ax.legend(frameon=False, labelcolor=MUTED, fontsize=8,
              loc="upper left", title=stack_col, title_fontsize=8)
    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_area_stacked] saved: {args.output}")


if __name__ == "__main__":
    main()