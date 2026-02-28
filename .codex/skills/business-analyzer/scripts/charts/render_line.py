"""
render_line.py — Line chart renderer (time series trend).

Called by chart_runner.py via subprocess.

Usage:
    python scripts/charts/render_line.py \
        --spec   '{"x": "date_col", "y": "measure_col"}' \
        --title  "Revenue Over Time" \
        --data   /home/claude/parsed_data.json \
        --output /home/claude/charts/chart_revenue_trend.png

Spec fields:
    x       (required) : date/time column name
    y       (required) : numeric column name
"""

import argparse
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

# ── Design tokens (shared across all renderers) ───────────────────────────────
BG      = "#0a0e1a"
SURFACE = "#111827"
ACCENT  = "#3b82f6"
TEXT    = "#f9fafb"
MUTED   = "#9ca3af"
BORDER  = "#1f2937"
DPI     = 150


def apply_theme(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
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
    parser.add_argument("--title",  default="Trend Over Time")
    parser.add_argument("--data",   required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec)
    x_col = spec.get("x")
    y_col = spec.get("y")

    if not x_col or not y_col:
        print(f"[render_line] ERROR: spec must include 'x' and 'y'. Got: {spec}", file=sys.stderr)
        sys.exit(1)

    # ── Load data ─────────────────────────────────────────────────────────────
    with open(args.data, encoding="utf-8") as f:
        parsed = json.load(f)
    df = pd.DataFrame(parsed["rows"])

    if x_col not in df.columns or y_col not in df.columns:
        print(f"[render_line] ERROR: columns '{x_col}' or '{y_col}' not in data.", file=sys.stderr)
        sys.exit(1)

    # ── Prepare data ──────────────────────────────────────────────────────────
    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
    df = df.dropna(subset=[x_col, y_col])

    if df.empty:
        print("[render_line] ERROR: No valid rows after cleaning.", file=sys.stderr)
        sys.exit(1)

    # Group by period (sum)
    df["_period"] = pd.to_datetime(df[x_col], errors="coerce")
    df = df.dropna(subset=["_period"])
    df = df.sort_values("_period")

    # Detect granularity for aggregation
    date_range_days = (df["_period"].max() - df["_period"].min()).days
    if date_range_days <= 90:
        df["_label"] = df["_period"].dt.strftime("%b %d")
        grouped = df.groupby("_label", sort=False)[y_col].sum()
        # Preserve chronological order
        order = df.drop_duplicates("_label")["_label"].tolist()
        grouped = grouped.reindex(order)
    elif date_range_days <= 730:
        df["_label"] = df["_period"].dt.strftime("%b %Y")
        grouped = df.groupby("_label", sort=False)[y_col].sum()
        order = df.drop_duplicates("_label")["_label"].tolist()
        grouped = grouped.reindex(order)
    else:
        df["_label"] = df["_period"].dt.strftime("%Y")
        grouped = df.groupby("_label")[y_col].sum().sort_index()

    labels  = grouped.index.tolist()
    values  = grouped.values.tolist()
    x_pos   = list(range(len(labels)))

    if len(values) < 2:
        print("[render_line] ERROR: Need at least 2 data points for a line chart.", file=sys.stderr)
        sys.exit(1)

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(11, 4))
    apply_theme(ax, fig)

    ax.grid(axis="y", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="x", visible=False)

    ax.plot(x_pos, values, color=ACCENT, linewidth=2.5,
            marker="o", markersize=5, zorder=3)
    ax.fill_between(x_pos, values, alpha=0.12, color=ACCENT)

    # Rotate labels if many periods
    rotation = 45 if len(labels) > 8 else 0
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, rotation=rotation, ha="right" if rotation else "center",
                       color=MUTED, fontsize=9)

    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: fmt_value(v)))
    ax.set_title(args.title, color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(x_col, color=MUTED, fontsize=10)
    ax.set_ylabel(y_col, color=MUTED, fontsize=10)

    plt.tight_layout()
    plt.savefig(args.output, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[render_line] saved: {args.output}")


if __name__ == "__main__":
    main()