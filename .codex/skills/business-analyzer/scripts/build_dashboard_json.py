"""
build_dashboard_json.py — Step 4: Shape metrics into the React dashboard payload.

Reads metrics.json (produced by compute_metrics.py) and outputs dashboard_data.json
which is injected into dashboard_template.jsx.

Changes from previous version:
  - top_products → top_items  (domain-agnostic naming)
  - product_share → item_share
  - by_region / by_rep / by_category removed — replaced by dynamic `dimensions` dict
  - DIMENSIONS key added: first 3 dimensions from the AI plan, each with label + data
  - roles key forwarded so the dashboard can label axes correctly

Usage:
    python scripts/build_dashboard_json.py \
        --input  /home/claude/metrics.json \
        --output /home/claude/dashboard_data.json
"""

import argparse
import datetime
import json


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_currency(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def fmt_value(value: float, measure_col: str = "") -> str:
    """
    Format a numeric value. Uses currency formatting by default.
    Falls back to plain number for non-revenue measures.
    """
    col_lower = measure_col.lower()
    is_currency = any(k in col_lower for k in
                      ["revenue", "sales", "amount", "total", "price",
                       "facture", "montant", "chiffre", "cost", "income"])
    if is_currency or not measure_col:
        return fmt_currency(value)
    # Plain number with K/M suffix
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:,.1f}"


def fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


# ---------------------------------------------------------------------------
# KPI block
# ---------------------------------------------------------------------------

def build_kpi_data(kpis: dict, roles: dict) -> dict:
    measure_col   = roles.get("primary_measure", "")
    top_item      = kpis.get("top_item", {})
    growth        = kpis.get("period_growth_pct", 0.0)
    primary_dim   = (roles.get("dimensions") or ["Item"])[0]

    return {
        "totalRevenue": {
            "label":    measure_col or "Total",
            "value":    fmt_value(kpis.get("total_revenue", 0), measure_col),
            "raw":      kpis.get("total_revenue", 0),
            "delta":    fmt_pct(growth),
            "positive": growth >= 0,
        },
        "totalOrders": {
            "label": "Total Records",
            "value": f"{kpis.get('total_orders', 0):,}",
            "raw":   kpis.get("total_orders", 0),
            "delta": None,
        },
        "avgOrderValue": {
            "label": f"Avg per Record",
            "value": fmt_value(kpis.get("avg_order_value", 0), measure_col),
            "raw":   kpis.get("avg_order_value", 0),
            "delta": None,
        },
        "topItem": {
            "label": f"Top {primary_dim}",
            "value": top_item.get("name", "N/A"),
            "share": f"{top_item.get('share_pct', 0):.1f}% of total",
            "delta": None,
        },
        "periodGrowth": {
            "label":    "Period Growth",
            "value":    fmt_pct(growth),
            "raw":      growth,
            "positive": growth >= 0,
        },
    }


# ---------------------------------------------------------------------------
# Trend data
# ---------------------------------------------------------------------------

def build_trend_data(trend: list) -> list:
    """Shorten period labels for display."""
    result = []
    for t in trend:
        period = str(t.get("period", ""))
        try:
            dt    = datetime.datetime.strptime(period, "%Y-%m")
            label = dt.strftime("%b %y")
        except ValueError:
            try:
                dt    = datetime.datetime.strptime(period, "%Y-%m-%d")
                label = dt.strftime("%d %b")
            except ValueError:
                label = period
        result.append({"period": label, "revenue": t.get("revenue", 0)})
    return result


# ---------------------------------------------------------------------------
# Dimension blocks
# ---------------------------------------------------------------------------

def build_dimension_blocks(dimensions: dict, roles: dict) -> list:
    """
    Convert the dynamic dimensions dict into a list of blocks
    the dashboard template can iterate over.

    Each block:
    {
      "key":   "technicien",
      "label": "Technicien",
      "data":  [ { "label": "Moussa", "revenue": 4200, "share_pct": 34.5 }, ... ]
    }
    """
    blocks = []
    # Respect AI dimension order
    dim_order = roles.get("dimensions", list(dimensions.keys()))

    for dim_col in dim_order[:4]:  # max 4 dimension charts
        data = dimensions.get(dim_col, [])
        if not data:
            continue
        # Normalize entry keys for the template
        normalized = []
        for entry in data[:12]:
            normalized.append({
                "label":     entry.get("label", entry.get(dim_col, "?")),
                "revenue":   entry.get("revenue", 0),
                "share_pct": entry.get("share_pct", 0),
            })
        blocks.append({
            "key":   dim_col,
            "label": dim_col.replace("_", " ").title(),
            "data":  normalized,
        })
    return blocks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Shape metrics.json into the React dashboard payload."
    )
    parser.add_argument("--input",  default="/home/claude/metrics.json")
    parser.add_argument("--output", default="/home/claude/dashboard_data.json")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        metrics = json.load(f)

    kpis       = metrics.get("kpis", {})
    roles      = metrics.get("roles", {})
    dimensions = metrics.get("dimensions", {})

    # Build payload
    payload = {
        # KPI cards — labelled with actual column names
        "KPI_DATA":        build_kpi_data(kpis, roles),

        # Trend line
        "TREND_DATA":      build_trend_data(metrics.get("revenue_trend", [])),

        # Top items ranked bar (domain-agnostic, was TOP_PRODUCTS)
        "TOP_ITEMS":       metrics.get("top_items", []),

        # Donut share (domain-agnostic, was PRODUCT_SHARE)
        "ITEM_SHARE":      metrics.get("item_share", []),

        # Dynamic dimension breakdowns (replaces by_region / by_rep / by_category)
        "DIMENSIONS":      build_dimension_blocks(dimensions, roles),

        # Recommendations (filled by LLM in main.py, placeholder here)
        "RECOMMENDATIONS": metrics.get("recommendations", []),

        # Roles — so the dashboard can label axes with real column names
        "ROLES":           roles,

        # Meta
        "META":            metrics.get("meta", {}),

        # Data quality summary
        "DATA_QUALITY":    metrics.get("data_quality", {}).get("summary", {}),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[build_dashboard_json] Done → {args.output}")
    print(f"  KPIs          : {list(payload['KPI_DATA'].keys())}")
    print(f"  Trend periods : {len(payload['TREND_DATA'])}")
    print(f"  Top items     : {len(payload['TOP_ITEMS'])}")
    print(f"  Item share    : {len(payload['ITEM_SHARE'])} slices")
    print(f"  Dimensions    : {[b['key'] for b in payload['DIMENSIONS']]}")
    print(f"  Data quality  : {payload['DATA_QUALITY'].get('score')} ({payload['DATA_QUALITY'].get('grade')})")


if __name__ == "__main__":
    main()