"""
generate_charts.py - Step 3: Evaluate chart eligibility + data-quality score,
then render only the best charts for the dataset.

Usage:
    python scripts/generate_charts.py \
        --input /home/claude/metrics.json \
        --output-dir /home/claude \
        --min-score 55 \
        --max-charts 6

Output:
    /home/claude/charts_manifest.json with generated and skipped charts,
    including scores and concrete skip reasons.
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


BG = "#0a0e1a"
SURFACE = "#111827"
ACCENT = "#3b82f6"
EMERALD = "#10b981"
AMBER = "#f59e0b"
DANGER = "#ef4444"
PURPLE = "#8b5cf6"
PINK = "#ec4899"
CYAN = "#06b6d4"
TEXT = "#f9fafb"
MUTED = "#9ca3af"
BORDER = "#1f2937"

PALETTE = [ACCENT, EMERALD, AMBER, DANGER, PURPLE, PINK, CYAN]
DPI = 150


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def average(values: list, default: float = 0.0) -> float:
    if not values:
        return default
    return sum(values) / len(values)


def apply_dark_theme(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)


def fmt_currency(value):
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def save(fig, path):
    plt.tight_layout()
    plt.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  saved: {path}")


def quality_summary_score(metrics: dict) -> float:
    return float(metrics.get("data_quality", {}).get("summary", {}).get("score", 70.0))


def completeness_pct(metrics: dict, role: str, fallback: float = None) -> float:
    if fallback is None:
        fallback = quality_summary_score(metrics)
    return float(metrics.get("data_quality", {}).get("completeness", {}).get(role, {}).get("pct", fallback))


def valid_dates(metrics: dict) -> dict:
    return metrics.get("data_quality", {}).get("valid_dates", {})


def outlier_pct(metrics: dict, field: str = "revenue") -> float:
    return float(metrics.get("data_quality", {}).get("outliers", {}).get(field, {}).get("pct", 0.0))


def variance_cv(metrics: dict, field: str = "revenue") -> float:
    return float(metrics.get("data_quality", {}).get("variance", {}).get(field, {}).get("cv", 0.0))


def base_quality_score(metrics: dict, roles: list = None) -> float:
    summary = quality_summary_score(metrics)
    if not roles:
        return summary

    role_scores = [completeness_pct(metrics, role, summary) for role in roles]
    return clamp((summary * 0.60) + (average(role_scores, summary) * 0.40))


def result(eligible: bool, reason: str, score: float, details: dict = None) -> dict:
    return {
        "eligible": eligible,
        "reason": reason,
        "score": round(clamp(score), 1),
        "details": details or {},
    }


# Eligibility and scoring

def check_trend(metrics: dict) -> dict:
    trend = metrics.get("revenue_trend", [])
    if len(trend) < 2:
        return result(False, f"Need >=2 periods, found {len(trend)}", 0.0)

    date_stats = valid_dates(metrics)
    date_pct = float(date_stats.get("pct_valid") or 0.0) if date_stats.get("present") else 100.0
    if date_stats.get("present") and date_pct < 70:
        return result(False, f"Date validity too low for trend chart ({date_pct:.1f}%)", date_pct)

    base = base_quality_score(metrics, ["revenue", "date"])
    period_bonus = min(18.0, len(trend) * 2.2)
    variance_bonus = min(8.0, variance_cv(metrics, "revenue") * 100.0)
    outlier_penalty = min(20.0, outlier_pct(metrics, "revenue") * 0.8)
    date_penalty = max(0.0, (90.0 - date_pct) * 0.6)

    score = (base * 0.65) + period_bonus + variance_bonus - outlier_penalty - date_penalty
    reason = f"{len(trend)} periods, date validity {date_pct:.1f}%"
    return result(True, reason, score, {"period_count": len(trend), "date_valid_pct": date_pct})


def check_products(metrics: dict) -> dict:
    products = metrics.get("top_products", [])
    if len(products) < 2:
        return result(False, f"Need >=2 products, found {len(products)}", 0.0)

    top_share = float(products[0].get("share_pct", 0.0))
    base = base_quality_score(metrics, ["revenue", "product", "category"])
    diversity_bonus = min(12.0, max(0, len(products) - 1) * 1.8)
    dominance_penalty = max(0.0, top_share - 70.0) * 0.7
    outlier_penalty = min(15.0, outlier_pct(metrics, "revenue") * 0.5)

    score = (base * 0.70) + diversity_bonus - dominance_penalty - outlier_penalty
    reason = f"{len(products)} products, top share {top_share:.1f}%"
    return result(True, reason, score, {"product_count": len(products), "top_share_pct": top_share})


def check_share(metrics: dict) -> dict:
    products = metrics.get("top_products", [])
    if len(products) < 3:
        return result(False, f"Need >=3 products for donut, found {len(products)}", 0.0)

    top_share = float(products[0].get("share_pct", 0.0))
    if top_share >= 95:
        return result(False, f"Top product dominates at {top_share:.1f}%", 0.0)

    base = base_quality_score(metrics, ["revenue", "product", "category"])
    slice_bonus = min(10.0, len(products) * 1.5)
    dominance_penalty = max(0.0, top_share - 55.0) * 1.1

    score = (base * 0.68) + slice_bonus - dominance_penalty
    reason = f"{len(products)} slices, concentration acceptable"
    return result(True, reason, score, {"product_count": len(products), "top_share_pct": top_share})


def check_region(metrics: dict) -> dict:
    region_data = metrics.get("by_region", [])
    if len(region_data) < 2:
        return result(False, "No region breakdown or only one region", 0.0)

    if len(region_data) > 25:
        return result(False, f"Too many regions for readable chart ({len(region_data)})", 0.0)

    base = base_quality_score(metrics, ["revenue", "region"])
    spread_bonus = min(12.0, len(region_data) * 1.4)
    crowd_penalty = max(0.0, len(region_data) - 10) * 1.2

    score = (base * 0.68) + spread_bonus - crowd_penalty
    reason = f"{len(region_data)} regions available"
    return result(True, reason, score, {"region_count": len(region_data)})


def check_rep(metrics: dict) -> dict:
    rep_data = metrics.get("by_rep", [])
    if len(rep_data) < 2:
        return result(False, "No sales rep breakdown or only one rep", 0.0)

    if len(rep_data) > 25:
        return result(False, f"Too many reps for readable chart ({len(rep_data)})", 0.0)

    base = base_quality_score(metrics, ["revenue", "rep"])
    spread_bonus = min(10.0, len(rep_data) * 1.2)
    crowd_penalty = max(0.0, len(rep_data) - 12) * 1.1

    score = (base * 0.66) + spread_bonus - crowd_penalty
    reason = f"{len(rep_data)} reps available"
    return result(True, reason, score, {"rep_count": len(rep_data)})


def check_daily(metrics: dict) -> dict:
    trend = metrics.get("revenue_trend", [])
    if not trend:
        return result(False, "No trend data", 0.0)

    date_stats = valid_dates(metrics)
    granularity = str(date_stats.get("granularity", "unknown"))
    if granularity not in {"day", "mixed"}:
        return result(False, f"Date granularity is '{granularity}', not daily", 0.0)

    if len(trend) < 7:
        return result(False, f"Need >=7 daily points, found {len(trend)}", 0.0)

    date_pct = float(date_stats.get("pct_valid") or 0.0)
    if date_pct < 80:
        return result(False, f"Date validity too low for daily chart ({date_pct:.1f}%)", date_pct)

    base = base_quality_score(metrics, ["revenue", "date"])
    depth_bonus = min(15.0, len(trend) * 0.8)
    outlier_penalty = min(18.0, outlier_pct(metrics, "revenue") * 0.8)

    score = (base * 0.68) + depth_bonus - outlier_penalty
    reason = f"Daily-ready trend with {len(trend)} points"
    return result(True, reason, score, {"point_count": len(trend), "granularity": granularity})


def check_quantity(metrics: dict) -> dict:
    quantity_data = metrics.get("by_quantity", [])
    if len(quantity_data) < 2:
        return result(False, "Need quantity + product columns with >=2 products", 0.0)

    base = base_quality_score(metrics, ["quantity", "product", "category"])
    spread_bonus = min(12.0, len(quantity_data) * 1.4)
    variance_bonus = min(10.0, variance_cv(metrics, "quantity") * 120.0)

    score = (base * 0.65) + spread_bonus + variance_bonus
    reason = f"Quantity data available for {len(quantity_data)} products"
    return result(True, reason, score, {"product_count": len(quantity_data)})


def check_category(metrics: dict) -> dict:
    category_data = metrics.get("by_category", [])
    products = metrics.get("top_products", [])
    if len(category_data) < 2:
        return result(False, "Need >=2 categories", 0.0)

    category_names = {str(item.get("category", "")).strip() for item in category_data}
    product_names = {str(item.get("product", "")).strip() for item in products}
    if category_names and category_names == product_names:
        return result(False, "Category labels duplicate product labels", 0.0)

    base = base_quality_score(metrics, ["revenue", "category"])
    spread_bonus = min(10.0, len(category_data) * 1.3)
    crowd_penalty = max(0.0, len(category_data) - 12) * 0.8

    score = (base * 0.67) + spread_bonus - crowd_penalty
    reason = f"{len(category_data)} distinct categories"
    return result(True, reason, score, {"category_count": len(category_data)})


CHART_REGISTRY = [
    ("trend", check_trend),
    ("products", check_products),
    ("share", check_share),
    ("region", check_region),
    ("rep", check_rep),
    ("daily", check_daily),
    ("quantity", check_quantity),
    ("category", check_category),
]


# Renderers

def render_trend(metrics, path):
    trend = metrics["revenue_trend"]
    periods = [item["period"] for item in trend]
    revenues = [item["revenue"] for item in trend]
    x = list(range(len(periods)))

    fig, ax = plt.subplots(figsize=(11, 4))
    apply_dark_theme(ax, fig)
    ax.grid(axis="y", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="x", visible=False)

    ax.plot(x, revenues, color=ACCENT, linewidth=2.5, marker="o", markersize=5, zorder=3)
    ax.fill_between(x, revenues, alpha=0.12, color=ACCENT)
    ax.set_xticks(x)
    ax.set_xticklabels(periods, rotation=45 if len(periods) > 8 else 0, ha="right")

    ax.annotate(
        fmt_currency(revenues[-1]),
        xy=(x[-1], revenues[-1]),
        xytext=(0, 12),
        textcoords="offset points",
        color=TEXT,
        fontsize=9,
        ha="center",
        fontweight="bold",
    )

    ax.set_title("Revenue Trend", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: fmt_currency(value)))
    save(fig, path)
    return "Revenue Trend"


def render_products(metrics, path):
    data = metrics["top_products"][:8]
    labels = [item["product"] for item in reversed(data)]
    values = [item["revenue"] for item in reversed(data)]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(data) - 1, -1, -1)]
    max_value = max(values) if values else 1

    fig, ax = plt.subplots(figsize=(10, max(4, len(data) * 0.6)))
    apply_dark_theme(ax, fig)
    ax.grid(axis="x", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="y", visible=False)

    bars = ax.barh(labels, values, color=colors, height=0.6)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            fmt_currency(value),
            va="center",
            color=TEXT,
            fontsize=8.5,
        )

    ax.set_xlim(0, max_value * 1.2)
    ax.set_title("Top Products by Revenue", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: fmt_currency(value)))
    save(fig, path)
    return "Top Products by Revenue"


def render_share(metrics, path):
    share = metrics["product_share"]
    labels = [item["name"] for item in share]
    values = [item["value"] for item in share]
    colors = PALETTE[: len(labels)]

    fig, (ax_pie, ax_legend) = plt.subplots(
        1,
        2,
        figsize=(10, 5),
        gridspec_kw={"width_ratios": [1.3, 0.7]},
    )
    for axis in (ax_pie, ax_legend):
        axis.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    ax_legend.axis("off")

    ax_pie.pie(
        values,
        colors=colors,
        startangle=90,
        wedgeprops={"width": 0.55, "edgecolor": BG, "linewidth": 2},
    )
    ax_pie.text(0, 0, "Revenue\nMix", ha="center", va="center", color=TEXT, fontsize=11, fontweight="bold")

    handles = [
        mpatches.Patch(facecolor=colors[i], label=f"{labels[i]}  {values[i]:.1f}%")
        for i in range(len(labels))
    ]
    ax_legend.legend(handles=handles, loc="center left", frameon=False, labelcolor=TEXT, fontsize=9.5, handlelength=1.2)

    ax_pie.set_title("Product Mix", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    save(fig, path)
    return "Product Mix"


def render_region(metrics, path):
    data = sorted(metrics["by_region"], key=lambda item: item["revenue"], reverse=True)
    labels = [item["region"] for item in data]
    values = [item["revenue"] for item in data]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(data))]
    max_value = max(values) if values else 1

    fig, ax = plt.subplots(figsize=(8, max(3, len(data) * 0.7)))
    apply_dark_theme(ax, fig)
    ax.grid(axis="x", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="y", visible=False)

    bars = ax.barh(labels, values, color=colors, height=0.55)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            fmt_currency(value),
            va="center",
            color=TEXT,
            fontsize=9,
        )

    ax.set_xlim(0, max_value * 1.2)
    ax.set_title("Revenue by Region", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: fmt_currency(value)))
    save(fig, path)
    return "Revenue by Region"


def render_rep(metrics, path):
    data = sorted(metrics["by_rep"], key=lambda item: item["revenue"], reverse=True)
    labels = [item["rep"] for item in data]
    values = [item["revenue"] for item in data]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(data))]
    max_value = max(values) if values else 1

    fig, ax = plt.subplots(figsize=(9, max(3, len(data) * 0.65)))
    apply_dark_theme(ax, fig)
    ax.grid(axis="x", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="y", visible=False)

    bars = ax.barh(labels, values, color=colors, height=0.55)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            fmt_currency(value),
            va="center",
            color=TEXT,
            fontsize=9,
        )

    ax.set_xlim(0, max_value * 1.2)
    ax.set_title("Revenue by Sales Rep", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: fmt_currency(value)))
    save(fig, path)
    return "Revenue by Sales Rep"


def render_daily(metrics, path):
    trend = metrics["revenue_trend"]
    labels = [item["period"].split("-")[2] if len(item["period"].split("-")) == 3 else item["period"] for item in trend]
    values = [item["revenue"] for item in trend]
    month_label = trend[0]["period"][:7] if trend else ""

    fig, ax = plt.subplots(figsize=(12, 4))
    apply_dark_theme(ax, fig)
    ax.grid(axis="y", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="x", visible=False)

    ax.bar(labels, values, color=ACCENT, width=0.7, alpha=0.85)
    avg_value = average(values, 0.0)
    ax.axhline(avg_value, color=AMBER, linewidth=1.5, linestyle="--", alpha=0.8, label=f"Avg {fmt_currency(avg_value)}")
    ax.legend(frameon=False, labelcolor=TEXT, fontsize=9)

    ax.set_title(f"Daily Revenue - {month_label}", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Day of Month", color=MUTED, fontsize=10)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: fmt_currency(value)))
    save(fig, path)
    return f"Daily Revenue - {month_label}"


def render_quantity(metrics, path):
    data = sorted(metrics["by_quantity"], key=lambda item: item["quantity"], reverse=True)[:8]
    labels = [item["product"] for item in reversed(data)]
    values = [item["quantity"] for item in reversed(data)]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(data) - 1, -1, -1)]
    max_value = max(values) if values else 1

    fig, ax = plt.subplots(figsize=(10, max(4, len(data) * 0.6)))
    apply_dark_theme(ax, fig)
    ax.grid(axis="x", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="y", visible=False)

    bars = ax.barh(labels, values, color=colors, height=0.6)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(int(round(value))),
            va="center",
            color=TEXT,
            fontsize=9,
        )

    ax.set_xlim(0, max_value * 1.15)
    ax.set_title("Units Sold by Product", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    save(fig, path)
    return "Units Sold by Product"


def render_category(metrics, path):
    data = sorted(metrics["by_category"], key=lambda item: item["revenue"], reverse=True)
    labels = [item["category"] for item in data]
    values = [item["revenue"] for item in data]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(data))]
    max_value = max(values) if values else 1

    fig, ax = plt.subplots(figsize=(9, max(4, len(data) * 0.7)))
    apply_dark_theme(ax, fig)
    ax.grid(axis="x", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.grid(axis="y", visible=False)

    bars = ax.barh(labels, values, color=colors, height=0.55)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            fmt_currency(value),
            va="center",
            color=TEXT,
            fontsize=9,
        )

    ax.set_xlim(0, max_value * 1.2)
    ax.set_title("Revenue by Category", color=TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value, _: fmt_currency(value)))
    save(fig, path)
    return "Revenue by Category"


RENDER_FNS = {
    "trend": render_trend,
    "products": render_products,
    "share": render_share,
    "region": render_region,
    "rep": render_rep,
    "daily": render_daily,
    "quantity": render_quantity,
    "category": render_category,
}


def skip_entry(chart_id: str, reason: str, score: float = None, details: dict = None) -> dict:
    item = {"id": chart_id, "reason": reason}
    if score is not None:
        item["score"] = round(score, 1)
    if details:
        item["details"] = details
    return item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/home/claude/metrics.json")
    parser.add_argument("--output-dir", default="/home/claude")
    parser.add_argument("--manifest", default="/home/claude/charts_manifest.json")
    parser.add_argument("--min-score", type=float, default=55.0)
    parser.add_argument("--max-charts", type=int, default=6)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        metrics = json.load(f)

    generated = []
    skipped = []
    candidates = []

    print("\n[generate_charts] Evaluating chart eligibility and quality scores...\n")

    for chart_id, check_fn in CHART_REGISTRY:
        evaluation = check_fn(metrics)
        eligible = evaluation["eligible"]
        score = float(evaluation["score"])

        if not eligible:
            skipped.append(skip_entry(chart_id, evaluation["reason"], score, evaluation.get("details")))
            print(f"  skip {chart_id:>8}: {evaluation['reason']}")
            continue

        if score < args.min_score:
            reason = (
                f"Score {score:.1f} below threshold {args.min_score:.1f}. "
                f"{evaluation['reason']}"
            )
            skipped.append(skip_entry(chart_id, reason, score, evaluation.get("details")))
            print(f"  skip {chart_id:>8}: score {score:.1f} < {args.min_score:.1f}")
            continue

        candidates.append(
            {
                "id": chart_id,
                "score": score,
                "reason": evaluation["reason"],
                "details": evaluation.get("details", {}),
            }
        )
        print(f"  keep {chart_id:>8}: score {score:.1f} ({evaluation['reason']})")

    candidates.sort(key=lambda item: item["score"], reverse=True)
    max_charts = args.max_charts if args.max_charts > 0 else len(candidates)
    selected = candidates[:max_charts]
    deferred = candidates[max_charts:]

    for entry in deferred:
        skipped.append(
            skip_entry(
                entry["id"],
                f"Eligible but not selected: lower score than top {max_charts} charts.",
                entry["score"],
                entry.get("details"),
            )
        )
        print(f"  skip {entry['id']:>8}: below top-{max_charts} cutoff")

    for entry in selected:
        chart_id = entry["id"]
        output_path = os.path.join(args.output_dir, f"chart_{chart_id}.png")
        try:
            title = RENDER_FNS[chart_id](metrics, output_path)
            generated.append(
                {
                    "id": chart_id,
                    "path": output_path,
                    "title": title,
                    "score": round(entry["score"], 1),
                    "selection_reason": entry["reason"],
                    "details": entry.get("details", {}),
                }
            )
        except Exception as error:
            skipped.append(
                skip_entry(
                    chart_id,
                    f"Render error: {error}",
                    entry["score"],
                    entry.get("details"),
                )
            )
            print(f"  error {chart_id:>8}: {error}")

    manifest = {
        "selection": {
            "min_score": args.min_score,
            "max_charts": args.max_charts,
            "evaluated": len(CHART_REGISTRY),
            "eligible_after_threshold": len(candidates),
            "selected_for_render": len(selected),
        },
        "data_quality": metrics.get("data_quality", {}).get("summary", {}),
        "generated": generated,
        "skipped": skipped,
    }

    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"\n[generate_charts] Done. {len(generated)} charts generated, "
        f"{len(skipped)} skipped. Manifest: {args.manifest}"
    )


if __name__ == "__main__":
    main()
