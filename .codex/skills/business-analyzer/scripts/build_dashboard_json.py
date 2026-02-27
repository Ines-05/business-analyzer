"""
build_dashboard_json.py — Step 4: Shape metrics into the exact JSON payload
expected by dashboard_template.jsx.

Usage:
    python scripts/build_dashboard_json.py \
        --input /home/claude/metrics.json \
        --output /home/claude/dashboard_data.json

Output schema (matches placeholder names in dashboard_template.jsx):
    {
      "KPI_DATA": { ... },
      "TREND_DATA": [ ... ],
      "TOP_PRODUCTS": [ ... ],
      "PRODUCT_SHARE": [ ... ],
      "RECOMMENDATIONS": [ ... ],
      "META": { ... }
    }

After running this script:
1. Open templates/dashboard_template.jsx
2. Find the comment:  // ── DATA INJECTION ──
3. Replace the placeholder constants with the values from dashboard_data.json
4. Save as /mnt/user-data/outputs/sales-dashboard.jsx
"""

import argparse
import json


def fmt_currency(value: float) -> str:
    """Format a float as a display currency string."""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def build_kpi_data(kpis: dict) -> dict:
    top_prod = kpis.get("top_product", {})
    return {
        "totalRevenue":    {"value": fmt_currency(kpis["total_revenue"]),   "raw": kpis["total_revenue"],   "delta": fmt_pct(kpis["period_growth_pct"]), "positive": kpis["period_growth_pct"] >= 0},
        "totalOrders":     {"value": f"{kpis['total_orders']:,}",            "raw": kpis["total_orders"],    "delta": None},
        "avgOrderValue":   {"value": fmt_currency(kpis["avg_order_value"]),  "raw": kpis["avg_order_value"], "delta": None},
        "topProduct":      {"value": top_prod.get("name", top_prod.get("product", "N/A")), "share": f"{top_prod.get('share_pct', 0):.1f}% of revenue", "delta": None},
        "periodGrowth":    {"value": fmt_pct(kpis["period_growth_pct"]),     "raw": kpis["period_growth_pct"], "positive": kpis["period_growth_pct"] >= 0},
    }


def build_trend_data(trend: list) -> list:
    """Shorten period labels for display (e.g. '2024-01' → 'Jan 24')."""
    import datetime
    result = []
    for t in trend:
        period = t["period"]
        try:
            dt = datetime.datetime.strptime(period, "%Y-%m")
            label = dt.strftime("%b %y")
        except Exception:
            label = period
        result.append({"period": label, "revenue": t["revenue"]})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/home/claude/metrics.json")
    parser.add_argument("--output", default="/home/claude/dashboard_data.json")
    args = parser.parse_args()

    with open(args.input) as f:
        metrics = json.load(f)

    payload = {
        "KPI_DATA":        build_kpi_data(metrics["kpis"]),
        "TREND_DATA":      build_trend_data(metrics.get("revenue_trend", [])),
        "TOP_PRODUCTS":    metrics.get("top_products", []),
        "PRODUCT_SHARE":   metrics.get("product_share", []),
        "RECOMMENDATIONS": metrics.get("recommendations", []),
        "META":            metrics.get("meta", {}),
    }

    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"[build_dashboard_json] Dashboard payload written to {args.output}")
    print("Next: inject this data into templates/dashboard_template.jsx")


if __name__ == "__main__":
    main()
