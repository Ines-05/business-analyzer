"""
parse_data.py - Step 1: Load, detect, and clean sales input data.

Usage:
    python scripts/parse_data.py --input /mnt/user-data/uploads/sales.csv
    python scripts/parse_data.py --input /mnt/user-data/uploads/sales.xlsx

Output:
    /home/claude/parsed_data.json
    Schema:
    {
      "rows": [...],
      "columns": {...},
      "date_range": {"min": "YYYY-MM", "max": "YYYY-MM"},
      "date_stats": {
        "granularity": "month|day|unknown",
        "valid_count": 120,
        "invalid_count": 3,
        "valid_pct": 97.6
      },
      "row_count": 1234,
      "source_file": "sales.csv"
    }
"""

import argparse
import json
import os
import sys

import pandas as pd


# Maps semantic role -> list of candidate column name patterns (case-insensitive)
COLUMN_HINTS = {
    "date": ["date", "order_date", "sale_date", "transaction_date", "period", "month", "week"],
    "revenue": ["revenue", "sales", "amount", "total", "gmv", "net_sales", "price", "value"],
    "product": ["product", "sku", "item", "product_name", "product_id", "name"],
    "category": ["category", "segment", "department", "family", "line"],
    "quantity": ["quantity", "qty", "units", "volume", "count"],
    "region": ["region", "territory", "country", "state", "area", "zone"],
    "rep": ["rep", "sales_rep", "salesperson", "agent", "owner", "assigned_to"],
    "target": ["target", "quota", "goal", "budget", "forecast"],
}


def detect_columns(df: pd.DataFrame) -> dict:
    """Return best-match column name for each semantic role (None if not found)."""
    cols_lower = {c.lower().strip(): c for c in df.columns}
    mapping = {}
    for role, hints in COLUMN_HINTS.items():
        match = None
        for hint in hints:
            for col_lower, col_orig in cols_lower.items():
                if hint in col_lower:
                    match = col_orig
                    break
            if match:
                break
        mapping[role] = match
    return mapping


def clean_currency(series: pd.Series) -> pd.Series:
    """Strip currency symbols and separators, then coerce to float."""
    return (
        series.astype(str)
        .str.replace(r"[\$,€£¥\s]", "", regex=True)
        .str.replace(r"[^\d.\-]", "", regex=True)
        .pipe(pd.to_numeric, errors="coerce")
    )


def parse_dates(series: pd.Series):
    """Parse dates and preserve month/day granularity when possible."""
    parsed = pd.to_datetime(series, errors="coerce")
    valid = parsed.dropna()

    if valid.empty:
        formatted = pd.Series([None] * len(parsed), index=parsed.index, dtype="object")
        return formatted, "unknown", 0, len(parsed)

    month_unique = valid.dt.to_period("M").nunique()
    day_unique = valid.dt.to_period("D").nunique()
    granularity = "day" if month_unique and (day_unique / month_unique) >= 1.5 else "month"

    if granularity == "day":
        formatted = parsed.dt.strftime("%Y-%m-%d")
    else:
        formatted = parsed.dt.to_period("M").astype(str)

    formatted = formatted.where(parsed.notna(), None)
    valid_count = int(parsed.notna().sum())
    invalid_count = int(parsed.isna().sum())
    return formatted, granularity, valid_count, invalid_count


def load_file(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Expected .csv or .xlsx/.xls")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input CSV or Excel file")
    parser.add_argument("--output", default="/home/claude/parsed_data.json")
    args = parser.parse_args()

    print(f"[parse_data] Loading: {args.input}")
    df = load_file(args.input)
    print(f"[parse_data] Shape: {df.shape} | Columns: {df.columns.tolist()}")

    col_map = detect_columns(df)
    print(f"[parse_data] Detected columns: {col_map}")

    if not col_map["revenue"]:
        sys.exit("[parse_data] ERROR: Could not detect a revenue/sales column. Rename it to 'revenue' or 'sales'.")

    df[col_map["revenue"]] = clean_currency(df[col_map["revenue"]])

    date_range = {"min": None, "max": None}
    date_stats = {
        "granularity": "unknown",
        "valid_count": 0,
        "invalid_count": 0,
        "valid_pct": None,
    }

    if col_map["date"]:
        (
            df[col_map["date"]],
            date_stats["granularity"],
            date_stats["valid_count"],
            date_stats["invalid_count"],
        ) = parse_dates(df[col_map["date"]])

        total_dates = date_stats["valid_count"] + date_stats["invalid_count"]
        if total_dates:
            date_stats["valid_pct"] = round((date_stats["valid_count"] / total_dates) * 100, 1)

        valid_dates = df[col_map["date"]].dropna()
        if not valid_dates.empty:
            date_range = {"min": valid_dates.min(), "max": valid_dates.max()}

    df = df.dropna(subset=[col_map["revenue"]])

    active_cols = list(dict.fromkeys(v for v in col_map.values() if v is not None))
    rows = df[active_cols].where(pd.notnull(df[active_cols]), None).to_dict("records")

    output = {
        "rows": rows,
        "columns": col_map,
        "date_range": date_range,
        "date_stats": date_stats,
        "row_count": len(rows),
        "source_file": os.path.basename(args.input),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[parse_data] Done. {len(rows)} rows written to {args.output}")


if __name__ == "__main__":
    main()
