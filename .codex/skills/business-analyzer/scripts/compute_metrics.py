"""
compute_metrics.py - Step 2: Compute KPIs, trends, breakdowns, data-quality profile,
and strategic recommendations.

Usage:
    python scripts/compute_metrics.py --input /home/claude/parsed_data.json

Output:
    /home/claude/metrics.json
    Schema highlights:
    {
      "kpis": {...},
      "revenue_trend": [...],
      "top_products": [...],
      "product_share": [...],
      "by_region": [...],
      "by_rep": [...],
      "by_quantity": [...],
      "by_category": [...],
      "data_quality": {
        "summary": {"score": 87.3, "grade": "A", ...},
        "completeness": {...},
        "variance": {...},
        "cardinality": {...},
        "valid_dates": {...},
        "outliers": {...}
      },
      "recommendations": [...],
      "meta": {...}
    }
"""

import argparse
import json
import math
import re
from collections import defaultdict
from statistics import mean, pstdev


DATE_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
DATE_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MISSING_STRINGS = {"", "na", "n/a", "none", "null", "nan", "nat"}


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in MISSING_STRINGS:
        return True
    return False


def as_float(value):
    if is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def compute_kpis(rows: list, col: dict) -> dict:
    rev_col = col["revenue"]
    revenues = [as_float(r.get(rev_col)) for r in rows]
    revenues = [v for v in revenues if v is not None]

    total_revenue = sum(revenues)
    total_orders = len(revenues)
    avg_order_value = total_revenue / total_orders if total_orders else 0

    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "avg_order_value": round(avg_order_value, 2),
    }


def compute_trend(rows: list, col: dict) -> list:
    """Group revenue by parsed period string (month or day)."""
    date_col = col.get("date")
    rev_col = col["revenue"]
    if not date_col:
        return []

    by_period = defaultdict(float)
    for row in rows:
        period = row.get(date_col)
        revenue = as_float(row.get(rev_col))
        if is_missing(period) or revenue is None:
            continue
        by_period[str(period)] += revenue

    return sorted(
        [{"period": period, "revenue": round(value, 2)} for period, value in by_period.items()],
        key=lambda item: item["period"],
    )


def compute_period_growth(trend: list) -> float:
    """Compare latest period against previous period."""
    if len(trend) < 2:
        return 0.0
    previous = trend[-2]["revenue"]
    current = trend[-1]["revenue"]
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 1)


def aggregate_revenue(rows: list, rev_col: str, dim_col: str, dim_key: str, limit: int = None) -> list:
    if not dim_col:
        return []

    totals = defaultdict(float)
    for row in rows:
        revenue = as_float(row.get(rev_col))
        dimension = row.get(dim_col)
        if revenue is None or is_missing(dimension):
            continue
        totals[str(dimension).strip()] += revenue

    if not totals:
        return []

    sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    if limit:
        sorted_items = sorted_items[:limit]

    grand_total = sum(value for _, value in sorted_items) or 1.0
    result = []
    for label, value in sorted_items:
        result.append(
            {
                dim_key: label,
                "revenue": round(value, 2),
                "share_pct": round((value / grand_total) * 100, 1),
            }
        )
    return result


def compute_top_products(rows: list, col: dict, n: int = 10) -> list:
    product_col = col.get("product") or col.get("category")
    rev_col = col["revenue"]
    if not product_col:
        return []

    by_product = defaultdict(float)
    for row in rows:
        product = row.get(product_col)
        revenue = as_float(row.get(rev_col))
        if revenue is None:
            continue
        key = str(product).strip() if not is_missing(product) else "Unknown"
        by_product[key] += revenue

    if not by_product:
        return []

    total = sum(by_product.values()) or 1.0
    top = sorted(by_product.items(), key=lambda item: item[1], reverse=True)[:n]
    return [
        {
            "product": name,
            "revenue": round(value, 2),
            "share_pct": round((value / total) * 100, 1),
        }
        for name, value in top
    ]


def compute_product_share(top_products: list, max_slices: int = 6) -> list:
    """Collapse tail products into 'Other' for donut charts."""
    if not top_products:
        return []

    slices = top_products[:max_slices]
    tail_revenue = sum(item["revenue"] for item in top_products[max_slices:])
    total_revenue = sum(item["revenue"] for item in top_products) or 1.0

    share = [{"name": item["product"], "value": item["share_pct"]} for item in slices]
    if tail_revenue > 0:
        share.append({"name": "Other", "value": round((tail_revenue / total_revenue) * 100, 1)})
    return share


def compute_quantity_by_product(rows: list, col: dict, n: int = 12) -> list:
    qty_col = col.get("quantity")
    product_col = col.get("product") or col.get("category")
    if not qty_col or not product_col:
        return []

    by_product = defaultdict(float)
    for row in rows:
        quantity = as_float(row.get(qty_col))
        product = row.get(product_col)
        if quantity is None:
            continue
        key = str(product).strip() if not is_missing(product) else "Unknown"
        by_product[key] += quantity

    ranked = sorted(by_product.items(), key=lambda item: item[1], reverse=True)[:n]
    return [{"product": key, "quantity": round(value, 2)} for key, value in ranked]


def profile_completeness(rows: list, col: dict) -> dict:
    total_rows = len(rows)
    profile = {}

    for role, column in col.items():
        if not column:
            continue
        non_null = sum(0 if is_missing(row.get(column)) else 1 for row in rows)
        profile[role] = {
            "column": column,
            "non_null": non_null,
            "total": total_rows,
            "pct": round_pct(non_null, total_rows),
        }

    return profile


def profile_cardinality(rows: list, col: dict) -> dict:
    roles = ["date", "product", "category", "region", "rep"]
    profile = {}

    for role in roles:
        column = col.get(role)
        if not column:
            continue

        values = [str(row.get(column)).strip() for row in rows if not is_missing(row.get(column))]
        unique_values = set(values)
        non_null_count = len(values)

        profile[role] = {
            "column": column,
            "unique": len(unique_values),
            "non_null": non_null_count,
            "unique_ratio_pct": round_pct(len(unique_values), non_null_count),
        }

    return profile


def variance_stats(values: list) -> dict:
    if not values:
        return {"count": 0, "mean": 0.0, "std": 0.0, "cv": 0.0}

    avg = mean(values)
    std_dev = pstdev(values) if len(values) > 1 else 0.0
    coeff_var = abs(std_dev / avg) if avg else 0.0
    return {
        "count": len(values),
        "mean": round(avg, 4),
        "std": round(std_dev, 4),
        "cv": round(coeff_var, 4),
    }


def quantile(values: list, q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(sorted_values[int(index)])
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    return float(lower_value + (upper_value - lower_value) * (index - lower))


def outlier_stats(values: list) -> dict:
    if len(values) < 4:
        return {
            "method": "iqr",
            "count": 0,
            "pct": 0.0,
            "lower_bound": None,
            "upper_bound": None,
        }

    q1 = quantile(values, 0.25)
    q3 = quantile(values, 0.75)
    iqr = q3 - q1
    lower = q1 - (1.5 * iqr)
    upper = q3 + (1.5 * iqr)

    count = sum(1 for value in values if value < lower or value > upper)
    return {
        "method": "iqr",
        "count": count,
        "pct": round_pct(count, len(values)),
        "lower_bound": round(lower, 4),
        "upper_bound": round(upper, 4),
    }


def profile_valid_dates(rows: list, col: dict, parsed_date_stats: dict = None) -> dict:
    date_col = col.get("date")
    if not date_col:
        return {
            "present": False,
            "valid": 0,
            "invalid": 0,
            "pct_valid": None,
            "granularity": "none",
        }

    day_count = 0
    month_count = 0
    invalid_count = 0

    for row in rows:
        value = row.get(date_col)
        if is_missing(value):
            invalid_count += 1
            continue

        string_value = str(value).strip()
        if DATE_DAY_RE.match(string_value):
            day_count += 1
        elif DATE_MONTH_RE.match(string_value):
            month_count += 1
        else:
            invalid_count += 1

    valid_count = day_count + month_count
    granularity = "unknown"
    if day_count and month_count:
        granularity = "mixed"
    elif day_count:
        granularity = "day"
    elif month_count:
        granularity = "month"

    if parsed_date_stats and parsed_date_stats.get("granularity") in {"day", "month"}:
        if granularity == "unknown":
            granularity = parsed_date_stats["granularity"]

    return {
        "present": True,
        "valid": valid_count,
        "invalid": invalid_count,
        "pct_valid": round_pct(valid_count, valid_count + invalid_count),
        "granularity": granularity,
    }


def quality_grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def derive_quality_summary(
    row_count: int,
    completeness: dict,
    valid_dates: dict,
    variance: dict,
    outliers: dict,
) -> dict:
    completeness_values = [stats["pct"] for stats in completeness.values()]
    completeness_score = sum(completeness_values) / len(completeness_values) if completeness_values else 0.0

    date_score = 100.0
    if valid_dates.get("present"):
        date_score = float(valid_dates.get("pct_valid") or 0.0)

    row_score = min(100.0, (row_count / 200.0) * 100.0)

    revenue_cv = float(variance.get("revenue", {}).get("cv") or 0.0)
    variance_score = min(100.0, revenue_cv * 400.0)

    revenue_outlier_pct = float(outliers.get("revenue", {}).get("pct") or 0.0)
    outlier_score = max(0.0, 100.0 - (revenue_outlier_pct * 2.5))

    component_scores = {
        "completeness": round(completeness_score, 1),
        "valid_dates": round(date_score, 1),
        "row_volume": round(row_score, 1),
        "variance": round(variance_score, 1),
        "outliers": round(outlier_score, 1),
    }

    weighted_score = (
        component_scores["completeness"] * 0.40
        + component_scores["valid_dates"] * 0.20
        + component_scores["row_volume"] * 0.15
        + component_scores["variance"] * 0.10
        + component_scores["outliers"] * 0.15
    )

    notes = []
    if component_scores["completeness"] < 90:
        notes.append("Some key columns have missing values.")
    if valid_dates.get("present") and component_scores["valid_dates"] < 90:
        notes.append("Date validity is low; time-based charts may be reduced.")
    if revenue_outlier_pct > 10:
        notes.append("Revenue contains many outliers that can distort chart readability.")
    if revenue_cv < 0.03:
        notes.append("Revenue variance is very low; some trend charts may add little insight.")

    score = round(weighted_score, 1)
    return {
        "score": score,
        "grade": quality_grade(score),
        "component_scores": component_scores,
        "notes": notes,
    }


def build_data_quality_profile(rows: list, col: dict, parsed_date_stats: dict = None) -> dict:
    rev_col = col["revenue"]
    qty_col = col.get("quantity")

    revenue_values = [as_float(row.get(rev_col)) for row in rows]
    revenue_values = [value for value in revenue_values if value is not None]

    quantity_values = []
    if qty_col:
        quantity_values = [as_float(row.get(qty_col)) for row in rows]
        quantity_values = [value for value in quantity_values if value is not None]

    completeness = profile_completeness(rows, col)
    cardinality = profile_cardinality(rows, col)
    variance = {
        "revenue": variance_stats(revenue_values),
    }
    if qty_col:
        variance["quantity"] = variance_stats(quantity_values)

    outliers = {
        "revenue": outlier_stats(revenue_values),
    }
    if qty_col and quantity_values:
        outliers["quantity"] = outlier_stats(quantity_values)

    valid_dates = profile_valid_dates(rows, col, parsed_date_stats)
    summary = derive_quality_summary(len(rows), completeness, valid_dates, variance, outliers)

    return {
        "summary": summary,
        "completeness": completeness,
        "variance": variance,
        "cardinality": cardinality,
        "valid_dates": valid_dates,
        "outliers": outliers,
    }


def generate_recommendations(kpis: dict, trend: list, top_products: list, data_quality: dict) -> list:
    """Generate 3-5 data-specific strategic recommendations."""
    recommendations = []

    if top_products:
        top = top_products[0]
        if top["share_pct"] > 50:
            recommendations.append(
                {
                    "priority": "High",
                    "icon": "alert",
                    "title": "Revenue concentration risk",
                    "insight": (
                        f"{top['product']} accounts for {top['share_pct']}% of total revenue "
                        f"(${top['revenue']:,.0f}). This concentration increases downside risk."
                    ),
                    "action": (
                        f"Grow the next 2-3 products to reduce dependence on {top['product']}. "
                        "Target less than 40% share for any single product within 2 quarters."
                    ),
                }
            )

    if trend:
        growth = compute_period_growth(trend)
        latest = trend[-1]
        if growth < -5:
            recommendations.append(
                {
                    "priority": "High",
                    "icon": "alert",
                    "title": f"Revenue declined {abs(growth)}% in {latest['period']}",
                    "insight": (
                        f"Revenue dropped from ${trend[-2]['revenue']:,.0f} to ${latest['revenue']:,.0f} "
                        f"({growth}% period-over-period)."
                    ),
                    "action": "Run a pipeline review to isolate whether the decline is product, region, or rep-driven.",
                }
            )
        elif growth > 10:
            recommendations.append(
                {
                    "priority": "Low",
                    "icon": "idea",
                    "title": f"Strong momentum: +{growth}% in {latest['period']}",
                    "insight": (
                        f"Revenue grew from ${trend[-2]['revenue']:,.0f} to ${latest['revenue']:,.0f}. "
                        "Capture the drivers while momentum is strong."
                    ),
                    "action": "Document winning campaigns and replicate across the next sales cycle.",
                }
            )

    if len(top_products) >= 5:
        tail = top_products[-1]
        if tail["share_pct"] < 2:
            recommendations.append(
                {
                    "priority": "Medium",
                    "icon": "warning",
                    "title": f"Low-performing SKU: {tail['product']}",
                    "insight": (
                        f"{tail['product']} contributes only {tail['share_pct']}% of revenue "
                        f"(${tail['revenue']:,.0f})."
                    ),
                    "action": "Review margin, pricing, and packaging strategy for this SKU.",
                }
            )

    aov = kpis.get("avg_order_value", 0)
    if aov > 0:
        recommendations.append(
            {
                "priority": "Medium",
                "icon": "warning",
                "title": f"Average order value opportunity (${aov:,.0f})",
                "insight": "AOV can likely be improved through bundling and structured upsell plays.",
                "action": "Deploy bundles or tiered pricing and monitor AOV weekly.",
            }
        )

    quality_notes = data_quality.get("summary", {}).get("notes", [])
    if quality_notes:
        recommendations.append(
            {
                "priority": "Low",
                "icon": "idea",
                "title": "Improve data quality to unlock better insights",
                "insight": quality_notes[0],
                "action": "Tighten source validation rules for mandatory fields before export.",
            }
        )

    if len(recommendations) < 3:
        recommendations.append(
            {
                "priority": "Low",
                "icon": "idea",
                "title": "Expand tracking granularity",
                "insight": "Region, rep, and category coverage is required for deeper diagnostic analysis.",
                "action": "Include region, sales rep, and category in future exports.",
            }
        )

    return recommendations[:5]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/home/claude/parsed_data.json")
    parser.add_argument("--output", default="/home/claude/metrics.json")
    args = parser.parse_args()

    data = load(args.input)
    rows = data["rows"]
    col = data["columns"]

    print(f"[compute_metrics] Processing {len(rows)} rows...")

    kpis = compute_kpis(rows, col)
    trend = compute_trend(rows, col)
    kpis["period_growth_pct"] = compute_period_growth(trend)

    top_products = compute_top_products(rows, col)
    if top_products:
        kpis["top_product"] = top_products[0]

    product_share = compute_product_share(top_products)

    by_region = aggregate_revenue(rows, col["revenue"], col.get("region"), "region")
    by_rep = aggregate_revenue(rows, col["revenue"], col.get("rep"), "rep", limit=25)
    by_category = aggregate_revenue(rows, col["revenue"], col.get("category"), "category")
    by_quantity = compute_quantity_by_product(rows, col)

    data_quality = build_data_quality_profile(rows, col, data.get("date_stats"))
    recommendations = generate_recommendations(kpis, trend, top_products, data_quality)

    output = {
        "kpis": kpis,
        "revenue_trend": trend,
        "top_products": top_products,
        "product_share": product_share,
        "by_region": by_region,
        "by_rep": by_rep,
        "by_quantity": by_quantity,
        "by_category": by_category,
        "data_quality": data_quality,
        "recommendations": recommendations,
        "meta": {
            "date_range": data.get("date_range", {}),
            "date_stats": data.get("date_stats", {}),
            "source_file": data.get("source_file", ""),
            "row_count": data.get("row_count", len(rows)),
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[compute_metrics] Done. Metrics written to {args.output}")
    print(f"  Total revenue:  ${kpis['total_revenue']:,.2f}")
    print(f"  Total orders:   {kpis['total_orders']:,}")
    print(f"  Period growth:  {kpis['period_growth_pct']}%")
    print(f"  Data quality:   {data_quality['summary']['score']} ({data_quality['summary']['grade']})")
    print(f"  Recommendations: {len(recommendations)}")


if __name__ == "__main__":
    main()
