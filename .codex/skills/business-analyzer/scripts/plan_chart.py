"""
plan_charts.py - Step 2: AI-powered chart planner.

Reads the column profile produced by parse_data.py and calls the LLM to:
  1. Assign a semantic role to each column (primary_measure, primary_date,
     dimensions, secondary_measures, ignore)
  2. Select 4-6 charts that best represent the dataset
  3. Provide a concrete spec for each chart (columns to use, chart type, title)

This step is fully domain-agnostic — it works for sales, clinic, logistics,
restaurant, or any other CSV/Excel file without any hardcoded column names.

Usage:
    python scripts/plan_charts.py \
        --input  /home/claude/parsed_data.json \
        --output /home/claude/chart_plan.json

    # With explicit API key (overrides env var):
    python scripts/plan_charts.py \
        --input  /home/claude/parsed_data.json \
        --output /home/claude/chart_plan.json \
        --api-key sk-...

Output:
    /home/claude/chart_plan.json

    Schema:
    {
      "roles": {
        "primary_measure":     "montant_facture",
        "primary_date":        "date_intervention",
        "dimensions":          ["technicien", "type_service", "statut"],
        "secondary_measures":  ["duree_heures"],
        "ignore":              ["client_id", "notes"]
      },
      "charts": [
        {
          "id":        "revenue_trend",
          "type":      "line",
          "title":     "Revenue Over Time",
          "spec": {
            "x":       "date_intervention",
            "y":       "montant_facture"
          },
          "rationale": "Shows billing evolution over the full date range."
        },
        {
          "id":        "by_technician",
          "type":      "bar_horizontal",
          "title":     "Revenue by Technician",
          "spec": {
            "group_by": "technicien",
            "y":        "montant_facture",
            "top_n":    10
          },
          "rationale": "8 technicians — ideal for ranked comparison."
        },
        ...
      ],
      "plan_source": "llm" | "fallback",
      "model_used":  "openai/gpt-5.2",
      "warning":     null | "..."   # set when fallback was used
    }

Available chart types for the AI to choose from:
    line              — time series trend (needs date + numeric)
    bar_horizontal    — ranked comparison by category (needs categorical + numeric)
    donut             — share / composition (needs categorical + numeric, ≤8 slices)
    bar_grouped       — comparison across two dimensions (needs 2 categoricals + numeric)
    scatter           — correlation (needs 2 numeric columns)
    area_stacked      — part-of-whole over time (needs date + categorical + numeric)
    heatmap           — intensity matrix (needs 2 categoricals + numeric)
    funnel            — sequential stages (needs ordered categorical + numeric)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from typing import Any

from openai import OpenAI


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GATEWAY_BASE_URL     = "https://ai-gateway.vercel.sh/v1"
DEFAULT_MODEL        = "openai/gpt-5.2"
DEFAULT_TIMEOUT      = 30.0
DEFAULT_RETRY        = 1
MAX_CHARTS           = 6
MIN_CHARTS           = 3

AVAILABLE_CHART_TYPES = [
    "line",
    "bar_horizontal",
    "donut",
    "bar_grouped",
    "scatter",
    "area_stacked",
    "heatmap",
    "funnel",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(parsed_data: dict) -> str:
    """
    Build a compact but complete prompt for the AI planner.
    Includes column profile + sample rows — nothing more.
    """
    column_profile = parsed_data.get("column_profile", [])
    row_count      = parsed_data.get("row_count", 0)
    source_file    = parsed_data.get("source_file", "unknown")
    sample_rows    = parsed_data.get("rows", [])[:5]  # first 5 rows only

    # Compact column profile for the prompt
    compact_columns = []
    for col in column_profile:
        entry: dict[str, Any] = {
            "name":          col["name"],
            "dtype":         col.get("dtype", ""),
            "inferred_type": col.get("inferred_type", "unknown"),
            "cardinality":   col.get("cardinality", 0),
            "null_pct":      col.get("null_pct", 0),
        }
        t = col.get("inferred_type")
        if t == "numeric":
            entry["min"]  = col.get("min")
            entry["max"]  = col.get("max")
            entry["mean"] = col.get("mean")
        elif t == "date":
            entry["date_min"]    = col.get("date_min")
            entry["date_max"]    = col.get("date_max")
            entry["granularity"] = col.get("granularity")
        elif t in ("categorical", "boolean"):
            entry["sample"] = col.get("sample", [])
        elif t == "id":
            entry["note"] = col.get("note", "high cardinality identifier")
        compact_columns.append(entry)

    prompt = f"""You are a senior data analyst. A client has uploaded a file called "{source_file}" with {row_count} rows.

Below is the column profile (inferred from df.dtypes() and statistics) and 5 sample rows.

## Column Profile
{json.dumps(compact_columns, indent=2, ensure_ascii=False)}

## Sample Rows (first 5)
{json.dumps(sample_rows, indent=2, ensure_ascii=False, default=str)}

---

Your task has TWO parts.

### PART 1 — Assign column roles
Assign each column to exactly one of these roles:
- "primary_measure"    : the main numeric value to analyze (revenue, amount, cost, etc.) — pick the most business-relevant one
- "secondary_measures" : other numeric columns worth showing (list, can be empty)
- "primary_date"       : the main time column for trend analysis (null if none)
- "dimensions"         : categorical columns useful for grouping/breakdown (max 5, exclude IDs and free text)
- "ignore"             : IDs, free text, or columns with no analytical value

### PART 2 — Select {MIN_CHARTS}–{MAX_CHARTS} charts
Choose the most insightful charts for this specific dataset.
Available chart types: {json.dumps(AVAILABLE_CHART_TYPES)}

Rules:
- Only suggest a chart if the required columns exist in the profile
- "line" or "area_stacked" require a primary_date column
- "donut" requires a dimension with ≤ 8 distinct values
- "scatter" requires 2 numeric columns
- "heatmap" requires 2 categorical dimensions
- "funnel" requires an ordered categorical + numeric (e.g. sales pipeline stages)
- "bar_grouped" requires 2 categorical dimensions + 1 numeric
- Prefer variety — do not suggest 5 bar charts
- Each chart must have a unique "id" (snake_case, no spaces)

For each chart provide:
- "id"        : unique snake_case identifier
- "type"      : one of the available chart types above
- "title"     : a clear, human-readable title (use the actual column names, not generic names)
- "spec"      : object with the exact column names to use — keys depend on chart type:
    line / area_stacked → {{"x": "<date_col>", "y": "<measure_col>", "stack_by": "<dim_col or null>"}}
    bar_horizontal      → {{"group_by": "<dim_col>", "y": "<measure_col>", "top_n": 10}}
    donut               → {{"group_by": "<dim_col>", "y": "<measure_col>"}}
    bar_grouped         → {{"group_by": "<dim_col1>", "color_by": "<dim_col2>", "y": "<measure_col>"}}
    scatter             → {{"x": "<measure_col1>", "y": "<measure_col2>", "label": "<dim_col or null>"}}
    heatmap             → {{"row": "<dim_col1>", "col": "<dim_col2>", "value": "<measure_col>"}}
    funnel              → {{"stage": "<dim_col>", "value": "<measure_col>"}}
- "rationale" : one sentence explaining why this chart is valuable for this data

---

Respond ONLY with a valid JSON object. No markdown, no explanation outside the JSON.

{{
  "roles": {{
    "primary_measure":    "<column_name>",
    "primary_date":       "<column_name or null>",
    "dimensions":         ["<col1>", "<col2>", ...],
    "secondary_measures": ["<col1>", ...],
    "ignore":             ["<col1>", ...]
  }},
  "charts": [
    {{
      "id":        "<snake_case_id>",
      "type":      "<chart_type>",
      "title":     "<Human Readable Title>",
      "spec":      {{ ... }},
      "rationale": "<one sentence>"
    }}
  ]
}}
"""
    return prompt


# ---------------------------------------------------------------------------
# JSON extraction (robust — handles markdown fences)
# ---------------------------------------------------------------------------

def extract_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end   = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


# ---------------------------------------------------------------------------
# Validation & normalization of AI response
# ---------------------------------------------------------------------------

def validate_plan(plan: dict, column_names: set[str]) -> dict:
    """
    Validate AI response structure. Fix minor issues silently.
    Raises ValueError if the plan is fundamentally unusable.
    """
    if "roles" not in plan or "charts" not in plan:
        raise ValueError("Plan missing 'roles' or 'charts' key.")

    roles = plan["roles"]

    # Ensure all role keys exist
    roles.setdefault("primary_measure",    None)
    roles.setdefault("primary_date",       None)
    roles.setdefault("dimensions",         [])
    roles.setdefault("secondary_measures", [])
    roles.setdefault("ignore",             [])

    # Validate primary_measure exists in data
    if roles["primary_measure"] and roles["primary_measure"] not in column_names:
        raise ValueError(
            f"primary_measure '{roles['primary_measure']}' not found in column profile."
        )

    # Validate charts
    valid_charts = []
    for chart in plan.get("charts", []):
        if not isinstance(chart, dict):
            continue
        if chart.get("type") not in AVAILABLE_CHART_TYPES:
            logger.warning("Skipping chart with unknown type: %s", chart.get("type"))
            continue
        if not chart.get("id") or not chart.get("spec"):
            continue
        # Ensure chart id is safe
        chart["id"] = str(chart["id"]).strip().replace(" ", "_").lower()
        valid_charts.append(chart)

    if len(valid_charts) < MIN_CHARTS:
        raise ValueError(
            f"AI returned only {len(valid_charts)} valid charts, minimum is {MIN_CHARTS}."
        )

    plan["charts"] = valid_charts[:MAX_CHARTS]
    return plan


# ---------------------------------------------------------------------------
# Fallback plan (when AI is unavailable)
# ---------------------------------------------------------------------------

def build_fallback_plan(parsed_data: dict) -> dict:
    """
    Simple heuristic fallback when the AI call fails.
    Picks the most likely numeric column as measure,
    the most likely date column as time axis,
    and generates basic charts.
    """
    profile = parsed_data.get("column_profile", [])

    numerics    = [c for c in profile if c.get("inferred_type") == "numeric"]
    dates       = [c for c in profile if c.get("inferred_type") == "date"]
    categoricals = [c for c in profile if c.get("inferred_type") == "categorical"]

    # Pick primary measure: highest max value among numerics (likely revenue/amount)
    primary_measure = None
    if numerics:
        primary_measure = max(numerics, key=lambda c: c.get("max") or 0)["name"]

    primary_date = dates[0]["name"] if dates else None

    dims = [c["name"] for c in categoricals[:5]]
    ignore = [c["name"] for c in profile if c.get("inferred_type") in ("id", "text")]

    charts = []

    if primary_date and primary_measure:
        charts.append({
            "id":        "trend",
            "type":      "line",
            "title":     f"{primary_measure} Over Time",
            "spec":      {"x": primary_date, "y": primary_measure},
            "rationale": "Fallback: time series of primary measure.",
        })

    for i, dim in enumerate(dims[:3]):
        charts.append({
            "id":        f"by_{dim.lower().replace(' ', '_')}",
            "type":      "bar_horizontal" if i < 2 else "donut",
            "title":     f"{primary_measure} by {dim}",
            "spec":      {"group_by": dim, "y": primary_measure},
            "rationale": f"Fallback: breakdown by {dim}.",
        })

    return {
        "roles": {
            "primary_measure":    primary_measure,
            "primary_date":       primary_date,
            "dimensions":         dims,
            "secondary_measures": [c["name"] for c in numerics[1:3]],
            "ignore":             ignore,
        },
        "charts":       charts,
        "plan_source":  "fallback",
        "model_used":   None,
        "warning":      "AI plan generation failed. Using heuristic fallback.",
    }


# ---------------------------------------------------------------------------
# Main LLM call
# ---------------------------------------------------------------------------

def call_ai_planner(
    parsed_data: dict,
    api_key: str,
    model: str     = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int   = DEFAULT_RETRY,
) -> tuple[dict, str]:
    """
    Call the AI gateway to get roles + chart plan.
    Returns (plan_dict, model_used).
    """
    client = OpenAI(api_key=api_key, base_url=GATEWAY_BASE_URL, timeout=timeout)
    prompt = build_prompt(parsed_data)

    column_names = {c["name"] for c in parsed_data.get("column_profile", [])}

    last_error = None
    for attempt in range(retries + 1):
        try:
            t0 = time.perf_counter()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data analyst assistant. "
                            "You respond ONLY with valid JSON. "
                            "No markdown, no explanation outside the JSON object."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,   # low temp for consistent structured output
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            content = response.choices[0].message.content or ""
            print(f"[plan_charts] AI response received in {duration_ms}ms ({len(content)} chars)")

            raw_plan  = extract_json(content)
            validated = validate_plan(raw_plan, column_names)
            return validated, model

        except Exception as exc:
            last_error = exc
            logger.warning(
                "[plan_charts] Attempt %d/%d failed: %s",
                attempt + 1, retries + 1, exc,
            )
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"AI planner failed after {retries + 1} attempts: {last_error}") from last_error


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AI-powered chart planner: assigns column roles and selects charts."
    )
    parser.add_argument("--input",   default="/home/claude/parsed_data.json")
    parser.add_argument("--output",  default="/home/claude/chart_plan.json")
    parser.add_argument("--api-key", default=None, help="Override AI_GATEWAY_API_KEY env var")
    parser.add_argument("--model",   default=None, help="Override DEFAULT_MODEL")
    args = parser.parse_args()

    # Load parsed data
    print(f"[plan_charts] Loading: {args.input}")
    with open(args.input, encoding="utf-8") as f:
        parsed_data = json.load(f)

    row_count      = parsed_data.get("row_count", 0)
    source_file    = parsed_data.get("source_file", "?")
    column_count   = len(parsed_data.get("column_profile", []))
    print(f"[plan_charts] {source_file} | {row_count} rows | {column_count} columns")

    # Resolve API key and model
    api_key = (args.api_key or os.getenv("AI_GATEWAY_API_KEY", "")).strip()
    model   = (args.model   or os.getenv("RECOMMENDATION_MODEL", DEFAULT_MODEL)).strip()

    # Try AI plan — fall back to heuristic if unavailable
    plan_source = "llm"
    warning     = None
    model_used  = model

    if not api_key:
        print("[plan_charts] WARNING: No API key found. Using heuristic fallback.")
        plan       = build_fallback_plan(parsed_data)
        plan_source = "fallback"
        warning     = "AI_GATEWAY_API_KEY not set. Using heuristic fallback."
        model_used  = None
    else:
        try:
            plan, model_used = call_ai_planner(
                parsed_data,
                api_key=api_key,
                model=model,
                timeout=float(os.getenv("AI_GATEWAY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT)),
                retries=int(os.getenv("AI_GATEWAY_RETRY_ATTEMPTS", DEFAULT_RETRY)),
            )
            plan_source = "llm"
            print(f"[plan_charts] AI plan: {len(plan['charts'])} charts selected by {model_used}")
        except Exception as exc:
            print(f"[plan_charts] AI call failed ({exc}). Using heuristic fallback.")
            plan        = build_fallback_plan(parsed_data)
            plan_source = "fallback"
            warning     = f"AI plan generation failed: {exc}. Using heuristic fallback."
            model_used  = None

    # Enrich plan with metadata
    plan["plan_source"] = plan_source
    plan["model_used"]  = model_used
    plan["warning"]     = warning

    # Print summary
    print(f"\n[plan_charts] === Chart Plan Summary ===")
    print(f"  Source file    : {source_file}")
    print(f"  Plan source    : {plan_source}")
    print(f"  Model used     : {model_used or 'n/a (fallback)'}")
    print(f"\n  Column roles:")
    roles = plan.get("roles", {})
    print(f"    primary_measure    : {roles.get('primary_measure')}")
    print(f"    primary_date       : {roles.get('primary_date')}")
    print(f"    dimensions         : {roles.get('dimensions', [])}")
    print(f"    secondary_measures : {roles.get('secondary_measures', [])}")
    print(f"    ignore             : {roles.get('ignore', [])}")
    print(f"\n  Charts selected ({len(plan.get('charts', []))}):")
    for chart in plan.get("charts", []):
        print(f"    [{chart['type']:16s}] {chart['title']}")
        print(f"                       spec: {chart.get('spec')}")
        print(f"                       → {chart.get('rationale', '')}")

    if warning:
        print(f"\n  ⚠ Warning: {warning}")

    # Write output
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    print(f"\n[plan_charts] Done → {args.output}")


if __name__ == "__main__":
    main()