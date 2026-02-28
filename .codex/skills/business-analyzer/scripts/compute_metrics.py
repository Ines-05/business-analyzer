"""
compute_metrics.py - Step 2: Compute KPIs, data quality profile, and
structural metrics using AI-assigned column roles from chart_plan.json.

No hardcoded column names. All roles (primary_measure, primary_date,
dimensions, secondary_measures) come from the AI plan produced by
plan_charts.py.

Usage:
    python scripts/compute_metrics.py \
        --input  /home/claude/parsed_data.json \
        --plan   /home/claude/chart_plan.json \
        --output /home/claude/metrics.json

Output:
    /home/claude/metrics.json
    {
      "kpis": {
        "total_revenue": 120500.0,
        "total_orders":  340,
        "avg_order_value": 354.4,
        "period_growth_pct": 12.3,
        "top_item": { "name": "Gamma", "revenue": 50000, "share_pct": 41.5 }
      },
      "revenue_trend":   [...],   # grouped by primary_date
      "top_items":       [...],   # ranked by primary_measure
      "item_share":      [...],   # donut-ready share of top items
      "dimensions":      {        # one entry per AI-assigned dimension
        "technicien":  [...],
        "type_service": [...]
      },
      "data_quality":    { "summary": {...}, "completeness": {...}, ... },
      "roles":           { ... }, # the roles block from chart_plan.json
      "meta":            { "source_file": "...", "row_count": ..., ... }
    }
"""

import argparse
import json
import math
import re
from collections import defaultdict
from statistics import mean, pstdev


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATE_MONTH_RE  = re.compile(r"^\d{4}-\d{2}$")
DATE_DAY_RE    = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MISSING_STRINGS = {"", "na", "n/a", "none", "null", "nan", "nat"}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------

def resolve_roles(plan: dict) -> dict:
    """
    Extract column roles from chart_plan.json.
    Returns a normalized roles dict with safe defaults.
    """
    roles = plan.get("roles", {})
    return {
        "primary_measure":    roles.get("primary_measure"),
        "primary_date":       roles.get("primary_date"),
        "dimensions":         roles.get("dimensions", []),
        "secondary_measures": roles.get("secondary_measures", []),
        "ignore":             roles.get("ignore", []),
    }


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------

def compute_kpis(rows: list, measure_col: str) -> dict:
    values = [as_float(r.get(measure_col)) for r in rows]
    values = [v for v in values if v is not None]

    total     = sum(values)
    count     = len(values)
    avg_value = total / count if count else 0.0

    return {
        "total_revenue":    round(total, 2),
        "total_orders":     count,
        "avg_order_value":  round(avg_value, 2),
    }


def compute_trend(rows: list, date_col: str, measure_col: str) -> list:
    """Group measure by date period (day or month)."""
    if not date_col or not measure_col:
        return []

    by_period: dict[str, float] = defaultdict(float)
    for row in rows:
        period  = row.get(date_col)
        value   = as_float(row.get(measure_col))
        if is_missing(period) or value is None:
            continue
        by_period[str(period)] += value

    return sorted(
        [{"period": p, "revenue": round(v, 2)} for p, v in by_period.items()],
        key=lambda item: item["period"],
    )


def compute_period_growth(trend: list) -> float:
    """% change between last two periods."""
    if len(trend) < 2:
        return 0.0
    prev = trend[-2]["revenue"]
    curr = trend[-1]["revenue"]
    if prev == 0:
        return 0.0
    return round(((curr - prev) / prev) * 100, 1)


def compute_top_items(rows: list, measure_col: str, dim_col: str, n: int = 10) -> list:
    """Rank items in dim_col by sum of measure_col."""
    if not dim_col or not measure_col:
        return []

    by_item: dict[str, float] = defaultdict(float)
    for row in rows:
        item  = row.get(dim_col)
        value = as_float(row.get(measure_col))
        if value is None:
            continue
        key = str(item).strip() if not is_missing(item) else "Unknown"
        by_item[key] += value

    if not by_item:
        return []

    total = sum(by_item.values()) or 1.0
    top   = sorted(by_item.items(), key=lambda x: x[1], reverse=True)[:n]
    return [
        {
            "name":      name,
            "revenue":   round(value, 2),
            "share_pct": round((value / total) * 100, 1),
        }
        for name, value in top
    ]


def compute_item_share(top_items: list, max_slices: int = 6) -> list:
    """Collapse tail items into 'Other' for donut chart."""
    if not top_items:
        return []

    slices       = top_items[:max_slices]
    tail_revenue = sum(i["revenue"] for i in top_items[max_slices:])
    total        = sum(i["revenue"] for i in top_items) or 1.0

    share = [{"name": i["name"], "value": i["share_pct"]} for i in slices]
    if tail_revenue > 0:
        share.append({"name": "Other", "value": round((tail_revenue / total) * 100, 1)})
    return share


def aggregate_by_dimension(rows: list, measure_col: str, dim_col: str, limit: int = 25) -> list:
    """Sum measure by a single dimension column."""
    if not dim_col or not measure_col:
        return []

    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        value = as_float(row.get(measure_col))
        label = row.get(dim_col)
        if value is None or is_missing(label):
            continue
        totals[str(label).strip()] += value

    if not totals:
        return []

    sorted_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:limit]
    grand_total  = sum(v for _, v in sorted_items) or 1.0

    return [
        {
            "label":     label,
            "dimension": dim_col,
            "revenue":   round(value, 2),
            "share_pct": round((value / grand_total) * 100, 1),
        }
        for label, value in sorted_items
    ]


# ---------------------------------------------------------------------------
# Data quality profile
# ---------------------------------------------------------------------------

def variance_stats(values: list) -> dict:
    if len(values) < 2:
        return {"mean": 0.0, "std": 0.0, "cv": 0.0}
    m  = mean(values)
    sd = pstdev(values)
    return {
        "mean": round(m, 4),
        "std":  round(sd, 4),
        "cv":   round(sd / m, 4) if m else 0.0,
    }


def outlier_stats(values: list) -> dict:
    if len(values) < 4:
        return {"count": 0, "pct": 0.0}
    m    = mean(values)
    sd   = pstdev(values)
    if sd == 0:
        return {"count": 0, "pct": 0.0}
    outs = sum(1 for v in values if abs(v - m) > 3 * sd)
    return {
        "count": outs,
        "pct":   round((outs / len(values)) * 100, 1),
    }


def profile_completeness(rows: list, roles: dict) -> dict:
    total = len(rows)
    result = {}
    cols_to_check = {}

    if roles.get("primary_measure"):
        cols_to_check["primary_measure"] = roles["primary_measure"]
    if roles.get("primary_date"):
        cols_to_check["primary_date"] = roles["primary_date"]
    for dim in roles.get("dimensions", []):
        cols_to_check[f"dim_{dim}"] = dim

    for role, col in cols_to_check.items():
        non_null = sum(0 if is_missing(row.get(col)) else 1 for row in rows)
        result[role] = {
            "column":   col,
            "non_null": non_null,
            "total":    total,
            "pct":      round_pct(non_null, total),
        }
    return result


def profile_valid_dates(rows: list, date_col: str) -> dict:
    if not date_col:
        return {"present": False}

    total   = len(rows)
    valid   = 0
    granularity = "unknown"

    for row in rows:
        v = row.get(date_col)
        if is_missing(v):
            continue
        s = str(v)
        if DATE_DAY_RE.match(s):
            valid += 1
            granularity = "day"
        elif DATE_MONTH_RE.match(s):
            valid += 1
            if granularity != "day":
                granularity = "month"

    return {
        "present":     True,
        "column":      date_col,
        "valid_count": valid,
        "total":       total,
        "pct_valid":   round_pct(valid, total),
        "granularity": granularity,
    }


def quality_grade(score: float) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    if score >= 40: return "D"
    return "E"


def build_data_quality_profile(rows: list, roles: dict) -> dict:
    measure_col = roles.get("primary_measure")
    date_col    = roles.get("primary_date")

    measure_values = []
    if measure_col:
        measure_values = [v for v in (as_float(r.get(measure_col)) for r in rows) if v is not None]

    completeness = profile_completeness(rows, roles)
    valid_dates  = profile_valid_dates(rows, date_col)

    variance = {}
    outliers = {}
    if measure_values:
        variance["primary_measure"] = variance_stats(measure_values)
        outliers["primary_measure"] = outlier_stats(measure_values)

    # Component scores
    completeness_values = [s["pct"] for s in completeness.values()]
    completeness_score  = (sum(completeness_values) / len(completeness_values)
                           if completeness_values else 0.0)

    date_score = (float(valid_dates.get("pct_valid", 0.0))
                  if valid_dates.get("present") else 100.0)

    row_score      = min(100.0, (len(rows) / 200.0) * 100.0)
    measure_cv     = float(variance.get("primary_measure", {}).get("cv", 0.0))
    variance_score = min(100.0, measure_cv * 400.0)
    outlier_pct    = float(outliers.get("primary_measure", {}).get("pct", 0.0))
    outlier_score  = max(0.0, 100.0 - (outlier_pct * 2.5))

    component_scores = {
        "completeness": round(completeness_score, 1),
        "valid_dates":  round(date_score, 1),
        "row_volume":   round(row_score, 1),
        "variance":     round(variance_score, 1),
        "outliers":     round(outlier_score, 1),
    }

    weighted = (
        component_scores["completeness"] * 0.40
        + component_scores["valid_dates"] * 0.20
        + component_scores["row_volume"]  * 0.15
        + component_scores["variance"]    * 0.10
        + component_scores["outliers"]    * 0.15
    )

    notes = []
    if component_scores["completeness"] < 90:
        notes.append("Some key columns have missing values.")
    if valid_dates.get("present") and component_scores["valid_dates"] < 90:
        notes.append("Date validity is low; time-based charts may be incomplete.")
    if outlier_pct > 10:
        notes.append("Primary measure contains many outliers that may distort charts.")
    if measure_cv < 0.03:
        notes.append("Primary measure has very low variance; trend charts may add little insight.")

    summary = {
        "score":            round(weighted, 1),
        "grade":            quality_grade(weighted),
        "component_scores": component_scores,
        "notes":            notes,
    }

    return {
        "summary":      summary,
        "completeness": completeness,
        "variance":     variance,
        "outliers":     outliers,
        "valid_dates":  valid_dates,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compute KPIs and data quality profile using AI-assigned column roles."
    )
    parser.add_argument("--input",  default="/home/claude/parsed_data.json")
    parser.add_argument("--plan",   default="/home/claude/chart_plan.json",
                        help="chart_plan.json from plan_charts.py (provides column roles)")
    parser.add_argument("--output", default="/home/claude/metrics.json")
    args = parser.parse_args()

    # ── Load inputs ──────────────────────────────────────────────────────────
    print(f"[compute_metrics] Loading data: {args.input}")
    data = load(args.input)
    rows = data.get("rows", [])

    print(f"[compute_metrics] Loading plan: {args.plan}")
    plan  = load(args.plan)
    roles = resolve_roles(plan)

    measure_col = roles["primary_measure"]
    date_col    = roles["primary_date"]
    dimensions  = roles["dimensions"]

    print(f"[compute_metrics] Roles resolved:")
    print(f"  primary_measure    : {measure_col}")
    print(f"  primary_date       : {date_col}")
    print(f"  dimensions         : {dimensions}")
    print(f"  secondary_measures : {roles['secondary_measures']}")
    print(f"  ignore             : {roles['ignore']}")
    print(f"[compute_metrics] Processing {len(rows)} rows...")

    if not measure_col:
        print("[compute_metrics] WARNING: No primary_measure found. KPIs will be empty.")

    # ── KPIs ─────────────────────────────────────────────────────────────────
    kpis = compute_kpis(rows, measure_col) if measure_col else {
        "total_revenue": 0.0, "total_orders": 0, "avg_order_value": 0.0
    }

    # ── Trend ─────────────────────────────────────────────────────────────────
    trend = compute_trend(rows, date_col, measure_col) if measure_col else []
    kpis["period_growth_pct"] = compute_period_growth(trend)

    # ── Top items (use first dimension as the "product" equivalent) ───────────
    primary_dim = dimensions[0] if dimensions else None
    top_items   = compute_top_items(rows, measure_col, primary_dim) if measure_col else []
    item_share  = compute_item_share(top_items)

    if top_items:
        kpis["top_item"] = top_items[0]

    # ── Dimension breakdowns (one per AI-assigned dimension) ──────────────────
    dim_breakdowns = {}
    for dim in dimensions:
        breakdown = aggregate_by_dimension(rows, measure_col, dim)
        if breakdown:
            dim_breakdowns[dim] = breakdown

    # ── Data quality profile ──────────────────────────────────────────────────
    data_quality = build_data_quality_profile(rows, roles)

    # ── Date range metadata ───────────────────────────────────────────────────
    date_range  = {"min": None, "max": None}
    date_values = []
    if date_col:
        date_values = [str(r.get(date_col)) for r in rows
                       if not is_missing(r.get(date_col))]
        if date_values:
            date_range = {"min": min(date_values), "max": max(date_values)}

    # ── Build output ──────────────────────────────────────────────────────────
    output = {
        "kpis":          kpis,
        "revenue_trend": trend,
        "top_items":     top_items,
        "item_share":    item_share,
        "dimensions":    dim_breakdowns,
        "data_quality":  data_quality,
        "roles":         roles,
        "meta": {
            "source_file":  data.get("source_file", ""),
            "row_count":    data.get("row_count", len(rows)),
            "date_range":   date_range,
            "plan_source":  plan.get("plan_source", "unknown"),
            "model_used":   plan.get("model_used"),
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    # ── Summary log ──────────────────────────────────────────────────────────
    print(f"\n[compute_metrics] Done → {args.output}")
    print(f"  Total measure   : {kpis['total_revenue']:,.2f}")
    print(f"  Total orders    : {kpis['total_orders']:,}")
    print(f"  Avg order value : {kpis['avg_order_value']:,.2f}")
    print(f"  Period growth   : {kpis['period_growth_pct']}%")
    print(f"  Trend periods   : {len(trend)}")
    print(f"  Top items       : {len(top_items)}")
    print(f"  Dimensions computed: {list(dim_breakdowns.keys())}")
    print(f"  Data quality    : {data_quality['summary']['score']} ({data_quality['summary']['grade']})")
    if data_quality["summary"]["notes"]:
        for note in data_quality["summary"]["notes"]:
            print(f"    ⚠ {note}")


if __name__ == "__main__":
    main()