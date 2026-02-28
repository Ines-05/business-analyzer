"""
parse_data.py - Step 1: Load and profile ALL columns from any CSV or Excel file.

No hardcoded column names. No domain assumptions.
Every column is analyzed and described so the AI can assign roles
and select the right charts in the next step (plan_charts.py).

Usage:
    python scripts/parse_data.py --input /mnt/user-data/uploads/sales.csv
    python scripts/parse_data.py --input /mnt/user-data/uploads/clinic.xlsx

Output:
    /home/claude/parsed_data.json

    Schema:
    {
      "rows": [...],                     # all rows, all columns, nulls as None
      "column_profile": [                # one entry per column — fed to AI planner
        {
          "name": "date_intervention",
          "dtype": "object",
          "inferred_type": "date",       # numeric | date | categorical | id | boolean | text
          "cardinality": 120,
          "null_pct": 0.5,
          "sample": ["2024-01-03", "2024-01-07", "2024-01-09"],   # top 3 non-null values
          # numeric only:
          "min": 50.0, "max": 4200.0, "mean": 380.2, "std": 290.1,
          # date only:
          "date_min": "2024-01-03", "date_max": "2024-12-28", "granularity": "day"
        },
        ...
      ],
      "row_count": 340,
      "source_file": "clinic.csv"
    }

Notes:
- The old `columns` role-mapping key is gone. Roles are now assigned by the AI in plan_charts.py.
- `rows` contains ALL columns from the original file (not just detected ones).
- Currency symbols are cleaned from numeric-looking columns automatically.
"""

import argparse
import json
import os
import sys

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# A column is considered an "id" (ignore for charts) if its cardinality
# relative to row count exceeds this threshold AND it isn't numeric/date.
ID_CARDINALITY_RATIO = 0.7

# Max sample values to include per column in the profile
SAMPLE_SIZE = 3

# Strings that represent missing values
MISSING_STRINGS = {"", "na", "n/a", "none", "null", "nan", "nat", "#n/a", "n.a."}


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_file(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".csv":
        # Try utf-8 first, fall back to latin-1 for French/accented characters
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="latin-1")
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Expected .csv, .xlsx, or .xls")

    # Normalize column names: strip whitespace only, preserve original name
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Currency cleaning
# ---------------------------------------------------------------------------

def try_clean_numeric(series: pd.Series) -> pd.Series:
    """
    Strip currency symbols, thousands separators, and whitespace,
    then coerce to float. Returns NaN where conversion fails.
    """
    cleaned = (
        series.astype(str)
        .str.replace(r"[\$,€£¥\s]", "", regex=True)
        .str.replace(r"[^\d.\-]", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce")


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def try_parse_dates(series: pd.Series):
    """
    Try to parse a series as dates.
    Returns (parsed_series_or_None, granularity, valid_count, invalid_count).
    """
    parsed = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
    valid = parsed.dropna()

    if len(valid) < max(2, len(series) * 0.5):
        # Less than 50% parseable — not a date column
        return None, "unknown", 0, len(series)

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


# ---------------------------------------------------------------------------
# Column type inference
# ---------------------------------------------------------------------------

def infer_column_type(series: pd.Series, row_count: int) -> dict:
    """
    Analyze a single column and return a profile dict describing its type and stats.

    Inferred types:
      - "date"        : parseable as datetime (>=50% valid)
      - "numeric"     : numeric values (int or float, or string with currency symbols)
      - "boolean"     : only 2 distinct non-null values (e.g. True/False, Yes/No, 0/1)
      - "id"          : high-cardinality string/int, not useful for charts
      - "categorical" : low-to-medium cardinality string column
      - "text"        : high-cardinality free text (long strings)
    """
    dtype_str = str(series.dtype)
    non_null = series.dropna()
    null_count = int(series.isna().sum())
    null_pct = round(null_count / row_count * 100, 1) if row_count else 0.0
    cardinality = int(series.nunique(dropna=True))

    # Replace known missing-string representations with NaN for analysis
    if series.dtype == object:
        series_clean = series.copy()
        series_clean = series_clean.where(
            ~series_clean.astype(str).str.strip().str.lower().isin(MISSING_STRINGS),
            other=np.nan
        )
        non_null = series_clean.dropna()
    else:
        series_clean = series

    profile = {
        "name": series.name,
        "dtype": dtype_str,
        "cardinality": cardinality,
        "null_pct": null_pct,
    }

    # ── 1. Try date ──────────────────────────────────────────────────────────
    if series.dtype == object or "datetime" in dtype_str:
        parsed, granularity, valid_count, invalid_count = try_parse_dates(non_null)
        if parsed is not None:
            date_values = pd.to_datetime(non_null, errors="coerce").dropna()
            profile.update({
                "inferred_type": "date",
                "granularity": granularity,
                "date_min": str(date_values.min().date()) if not date_values.empty else None,
                "date_max": str(date_values.max().date()) if not date_values.empty else None,
                "valid_date_pct": round(valid_count / (valid_count + invalid_count) * 100, 1) if (valid_count + invalid_count) else 0,
                "sample": [str(v) for v in non_null.head(SAMPLE_SIZE).tolist()],
            })
            return profile

    # ── 2. Try numeric ───────────────────────────────────────────────────────
    if pd.api.types.is_numeric_dtype(series):
        numeric_vals = series.dropna()
        profile.update({
            "inferred_type": "numeric",
            "min": round(float(numeric_vals.min()), 4) if not numeric_vals.empty else None,
            "max": round(float(numeric_vals.max()), 4) if not numeric_vals.empty else None,
            "mean": round(float(numeric_vals.mean()), 4) if not numeric_vals.empty else None,
            "std": round(float(numeric_vals.std()), 4) if not numeric_vals.empty else None,
            "sample": [round(float(v), 2) for v in numeric_vals.head(SAMPLE_SIZE).tolist()],
        })
        return profile

    # Try cleaning currency strings → numeric
    if series.dtype == object:
        cleaned_numeric = try_clean_numeric(non_null)
        valid_numeric = cleaned_numeric.dropna()
        if len(valid_numeric) >= len(non_null) * 0.7:
            profile.update({
                "inferred_type": "numeric",
                "min": round(float(valid_numeric.min()), 4) if not valid_numeric.empty else None,
                "max": round(float(valid_numeric.max()), 4) if not valid_numeric.empty else None,
                "mean": round(float(valid_numeric.mean()), 4) if not valid_numeric.empty else None,
                "std": round(float(valid_numeric.std()), 4) if not valid_numeric.empty else None,
                "sample": [round(float(v), 2) for v in valid_numeric.head(SAMPLE_SIZE).tolist()],
                "note": "currency/string cleaned to numeric",
            })
            return profile

    # ── 3. Boolean ───────────────────────────────────────────────────────────
    if cardinality <= 2:
        profile.update({
            "inferred_type": "boolean",
            "sample": [str(v) for v in non_null.unique().tolist()],
        })
        return profile

    # ── 4. ID vs Categorical vs Text ─────────────────────────────────────────
    if series.dtype == object:
        avg_len = float(non_null.astype(str).str.len().mean()) if not non_null.empty else 0
        cardinality_ratio = cardinality / row_count if row_count else 0

        if cardinality_ratio > ID_CARDINALITY_RATIO and avg_len < 40:
            # High cardinality, short strings → likely an ID column
            profile.update({
                "inferred_type": "id",
                "sample": [],
                "note": f"cardinality ratio {cardinality_ratio:.2f} — likely identifier, skip for charts",
            })
        elif avg_len > 60:
            # Long strings → free text
            profile.update({
                "inferred_type": "text",
                "sample": [str(v)[:80] for v in non_null.head(SAMPLE_SIZE).tolist()],
            })
        else:
            # Categorical
            top_values = non_null.value_counts().head(SAMPLE_SIZE).index.tolist()
            profile.update({
                "inferred_type": "categorical",
                "sample": [str(v) for v in top_values],
            })
        return profile

    # Fallback
    profile.update({
        "inferred_type": "unknown",
        "sample": [str(v) for v in non_null.head(SAMPLE_SIZE).tolist()],
    })
    return profile


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Profile all columns in a CSV/Excel file for AI-driven chart planning."
    )
    parser.add_argument("--input",  required=True, help="Path to input CSV or Excel file")
    parser.add_argument("--output", default="/home/claude/parsed_data.json")
    args = parser.parse_args()

    print(f"[parse_data] Loading: {args.input}")
    df = load_file(args.input)
    print(f"[parse_data] Shape: {df.shape} | Columns: {df.columns.tolist()}")

    if df.empty:
        sys.exit("[parse_data] ERROR: File is empty.")

    if len(df.columns) < 2:
        sys.exit("[parse_data] ERROR: File must have at least 2 columns.")

    row_count = len(df)

    # ── Build column profiles ──────────────────────────────────────────────
    column_profile = []
    cleaned_columns = {}  # track columns we cleaned (currency → numeric)

    for col_name in df.columns:
        series = df[col_name].copy()
        series.name = col_name
        profile = infer_column_type(series, row_count)
        column_profile.append(profile)

        # If currency was cleaned to numeric, apply it to the dataframe for rows output
        if profile.get("note") == "currency/string cleaned to numeric":
            df[col_name] = try_clean_numeric(df[col_name])
            cleaned_columns[col_name] = True

    # ── Build rows (all columns, nulls as None) ────────────────────────────
    rows = df.where(pd.notnull(df), None).to_dict("records")

    # ── Summarize for logs ─────────────────────────────────────────────────
    type_counts = {}
    for p in column_profile:
        t = p["inferred_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"[parse_data] Column types detected: {type_counts}")
    if cleaned_columns:
        print(f"[parse_data] Currency-cleaned columns: {list(cleaned_columns.keys())}")

    # ── Output ─────────────────────────────────────────────────────────────
    output = {
        "rows": rows,
        "column_profile": column_profile,
        "row_count": row_count,
        "source_file": os.path.basename(args.input),
    }

    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[parse_data] Done. {row_count} rows, {len(column_profile)} columns profiled → {args.output}")

    # Print a quick profile summary for debugging
    print("\n[parse_data] Column profile summary:")
    for p in column_profile:
        t = p["inferred_type"]
        card = p["cardinality"]
        sample = p.get("sample", [])
        extra = ""
        if t == "numeric":
            extra = f"  min={p.get('min')}  max={p.get('max')}  mean={p.get('mean')}"
        elif t == "date":
            extra = f"  {p.get('date_min')} → {p.get('date_max')}  granularity={p.get('granularity')}"
        elif t == "categorical":
            extra = f"  samples={sample}"
        elif t == "id":
            extra = f"  (skipped — {p.get('note', '')})"
        print(f"  {p['name']:30s} [{t:12s}]  cardinality={card:4d}{extra}")


if __name__ == "__main__":
    main()