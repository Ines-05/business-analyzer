---
name: business-bi-dashboard
description: Transform any structured data file (CSV or Excel) from any business domain into a strategic, executive-grade business intelligence dashboard built as a React (.jsx) artifact, with an optional PDF report export. This skill is fully domain-agnostic — it works for sales, clinics, logistics, restaurants, services, or any other domain without hardcoded column names. The AI analyzes the data profile, assigns column roles, and selects the most appropriate charts automatically. Use this skill whenever the user wants to visualize data, generate a BI dashboard, get executive insights, analyze KPIs or trends, or receive AI-powered strategic recommendations from their data. Also trigger when the user wants to export a report as a PDF. Trigger for requests like "analyze my file", "show me trends in my data", "give me a dashboard", or "export this as a PDF report".
---

# Business BI Dashboard Skill

Transform any structured CSV or Excel file into a polished React dashboard with KPI cards,
AI-selected charts, dynamic dimension breakdowns, and strategic recommendations.
Fully domain-agnostic — no hardcoded column names anywhere in the pipeline.

## Output modes
- React Dashboard (default)
- PDF Report (optional)
- Both

## Skill structure

```text
business-analyzer/
|- SKILL.md
|- scripts/
|  |- parse_data.py           # Step 1 — profile all columns (domain-agnostic)
|  |- plan_charts.py          # Step 2 — AI assigns roles + selects charts
|  |- compute_metrics.py      # Step 3 — KPIs using AI-assigned roles
|  |- build_dashboard_json.py # Step 4 — React payload
|  |- chart_runner.py         # Step 5 — dispatches to dedicated renderers
|  |- export_pdf.py           # Step 6 — PDF report (optional)
|  `- charts/
|     |- render_line.py
|     |- render_bar_horizontal.py
|     |- render_donut.py
|     |- render_bar_grouped.py
|     |- render_scatter.py
|     |- render_area_stacked.py
|     |- render_heatmap.py
|     `- render_funnel.py
|- references/
|  `- pdf-integration.md
`- templates/
   `- dashboard_template.jsx
```

Always read the relevant script before editing its behavior.

---

## Pipeline overview

```
CSV/Excel
    ↓
parse_data.py       → parsed_data.json     (all columns profiled, no role assumptions)
    ↓
plan_charts.py      → chart_plan.json      (AI: role assignment + chart selection)
    ↓
compute_metrics.py  → metrics.json         (KPIs using AI-assigned roles)
    ↓
build_dashboard_json.py → dashboard_data.json
    ↓
chart_runner.py     → chart PNGs + charts_manifest.json
    ↓
dashboard_template.jsx  → sales-dashboard.jsx  (inject data, deliver)
```

---

## Workflow

### Step 1 — Parse input (domain-agnostic profiling)

```bash
ls /mnt/user-data/uploads/
python scripts/parse_data.py \
    --input  /mnt/user-data/uploads/<filename> \
    --output /home/claude/parsed_data.json
```

Output: `/home/claude/parsed_data.json`

`parse_data.py` profiles **every column** using `df.dtypes()` and statistics.
No hardcoded column name hints. No role assumptions.

Output schema:
```json
{
  "rows": [...],
  "column_profile": [
    {
      "name": "date_intervention",
      "dtype": "object",
      "inferred_type": "date",
      "cardinality": 120,
      "null_pct": 0.5,
      "date_min": "2024-01-03",
      "date_max": "2024-12-28",
      "granularity": "day"
    },
    {
      "name": "montant_facture",
      "dtype": "float64",
      "inferred_type": "numeric",
      "min": 50.0, "max": 4200.0, "mean": 380.2, "std": 290.1
    },
    {
      "name": "technicien",
      "dtype": "object",
      "inferred_type": "categorical",
      "cardinality": 8,
      "sample": ["Moussa", "Ismail", "Sara"]
    },
    {
      "name": "client_id",
      "dtype": "int64",
      "inferred_type": "id",
      "cardinality": 280,
      "note": "cardinality ratio 0.82 — likely identifier, skip for charts"
    }
  ],
  "row_count": 340,
  "source_file": "clinic.csv"
}
```

Inferred types:
- `date`        — ≥50% of values parse as datetime
- `numeric`     — numeric dtype, OR string that cleans to float (currency symbols stripped)
- `categorical` — low-to-medium cardinality string column
- `boolean`     — only 2 distinct non-null values
- `id`          — cardinality > 70% of row count → ignored for charts
- `text`        — average string length > 60 chars → ignored for charts

### Step 2 — AI chart planning

```bash
python scripts/plan_charts.py \
    --input  /home/claude/parsed_data.json \
    --output /home/claude/chart_plan.json
```

Output: `/home/claude/chart_plan.json`

Calls the AI gateway (same `AI_GATEWAY_API_KEY` as recommendations).
The AI receives the full `column_profile` + first 5 sample rows and returns:

**Part 1 — Role assignment:**
- `primary_measure`    : main numeric column to analyze
- `primary_date`       : time column for trends (null if none)
- `dimensions`         : categorical columns for breakdowns (max 5)
- `secondary_measures` : other numeric columns worth showing
- `ignore`             : IDs, free text, useless columns

**Part 2 — Chart selection (3–6 charts):**

Available chart types:
| Type              | Required columns                          |
|-------------------|-------------------------------------------|
| `line`            | date + numeric                            |
| `bar_horizontal`  | categorical + numeric                     |
| `donut`           | categorical (≤8 values) + numeric         |
| `bar_grouped`     | 2 categoricals + numeric                  |
| `scatter`         | 2 numeric columns                         |
| `area_stacked`    | date + categorical + numeric              |
| `heatmap`         | 2 categoricals + numeric                  |
| `funnel`          | ordered categorical + numeric             |

Each chart has: `id`, `type`, `title`, `spec` (exact column names), `rationale`.

**Fallback:** If the AI call fails or no API key is set, a heuristic fallback
automatically picks the most likely measure/date columns and generates basic charts.
Check `plan_source` in the output: `"llm"` or `"fallback"`.

Output schema:
```json
{
  "roles": {
    "primary_measure":    "montant_facture",
    "primary_date":       "date_intervention",
    "dimensions":         ["technicien", "type_service", "statut"],
    "secondary_measures": [],
    "ignore":             ["client_id"]
  },
  "charts": [
    {
      "id":        "revenue_trend",
      "type":      "line",
      "title":     "Montant Facture Over Time",
      "spec":      { "x": "date_intervention", "y": "montant_facture" },
      "rationale": "Shows billing evolution over the full date range."
    }
  ],
  "plan_source": "llm",
  "model_used":  "openai/gpt-5.2",
  "warning":     null
}
```

### Step 3 — Compute metrics

```bash
python scripts/compute_metrics.py \
    --input  /home/claude/parsed_data.json \
    --plan   /home/claude/chart_plan.json \
    --output /home/claude/metrics.json
```

Output: `/home/claude/metrics.json`

`compute_metrics.py` reads column roles from `chart_plan.json` — no hardcoded names.

Computes:
- `kpis`: `total_revenue`, `total_orders`, `avg_order_value`, `period_growth_pct`, `top_item`
- `revenue_trend`: grouped by `primary_date`
- `top_items`: ranked by `primary_measure` (was `top_products`)
- `item_share`: donut-ready share (was `product_share`)
- `dimensions`: dict keyed by actual column names, one entry per AI dimension
- `data_quality`: completeness, variance, outliers, valid_dates, summary (score + grade)
- `roles`: forwarded from chart_plan.json
- `meta`: source_file, row_count, date_range, plan_source, model_used

### Step 4 — Build dashboard payload

```bash
python scripts/build_dashboard_json.py \
    --input  /home/claude/metrics.json \
    --output /home/claude/dashboard_data.json
```

Output: `/home/claude/dashboard_data.json`

Shapes metrics into the React template constants:
- `KPI_DATA`        — labelled with real column names from roles
- `TREND_DATA`      — period labels shortened for display
- `TOP_ITEMS`       — ranked items (was TOP_PRODUCTS)
- `ITEM_SHARE`      — donut data (was PRODUCT_SHARE)
- `DIMENSIONS`      — array of `{ key, label, data }` blocks, one per AI dimension
- `RECOMMENDATIONS` — placeholder (filled by LLM in main.py)
- `ROLES`           — real column names for axis labels
- `META`            — source file, date range, row count
- `DATA_QUALITY`    — score + grade for dashboard badge

### Step 5 — Render charts

```bash
python scripts/chart_runner.py \
    --plan       /home/claude/chart_plan.json \
    --data       /home/claude/parsed_data.json \
    --output-dir /home/claude/charts \
    --manifest   /home/claude/charts_manifest.json
```

Output: chart PNGs in `/home/claude/charts/` + `charts_manifest.json`

`chart_runner.py` reads the AI plan and dispatches each chart to its dedicated renderer:

```
chart type        → renderer script
─────────────────────────────────────────────────
line              → charts/render_line.py
bar_horizontal    → charts/render_bar_horizontal.py
donut             → charts/render_donut.py
bar_grouped       → charts/render_bar_grouped.py
scatter           → charts/render_scatter.py
area_stacked      → charts/render_area_stacked.py
heatmap           → charts/render_heatmap.py
funnel            → charts/render_funnel.py
```

Each renderer is called as a subprocess:
```bash
python scripts/charts/render_<type>.py \
    --spec   '<json spec from plan>' \
    --title  '<chart title>' \
    --data   /home/claude/parsed_data.py \
    --output /home/claude/charts/chart_<id>.png
```

Manifest contract (same as old generate_charts.py — downstream scripts unchanged):
```json
{
  "generated": [
    {
      "id":          "revenue_trend",
      "path":        "/home/claude/charts/chart_revenue_trend.png",
      "title":       "Montant Facture Over Time",
      "type":        "line",
      "spec":        { "x": "date_intervention", "y": "montant_facture" },
      "rationale":   "Shows billing evolution over the full date range.",
      "plan_source": "llm"
    }
  ],
  "skipped": [
    { "id": "scatter_xy", "type": "scatter", "reason": "Render error: ..." }
  ],
  "summary": {
    "total_planned": 5,
    "generated":     4,
    "skipped":       1,
    "plan_source":   "llm",
    "model_used":    "openai/gpt-5.2",
    "roles":         { ... }
  }
}
```

Always read `charts_manifest.json` before building downstream assets.
Do not assume chart files exist — check `manifest["generated"]` first.

### Step 6 — Build React dashboard

Inject `dashboard_data.json` values into `templates/dashboard_template.jsx`
at the `── DATA INJECTION ──` block:

Replace these constants:
- `KPI_DATA`        ← `dashboard_data["KPI_DATA"]`
- `TREND_DATA`      ← `dashboard_data["TREND_DATA"]`
- `TOP_ITEMS`       ← `dashboard_data["TOP_ITEMS"]`
- `ITEM_SHARE`      ← `dashboard_data["ITEM_SHARE"]`
- `DIMENSIONS`      ← `dashboard_data["DIMENSIONS"]`
- `RECOMMENDATIONS` ← `dashboard_data["RECOMMENDATIONS"]`
- `ROLES`           ← `dashboard_data["ROLES"]`
- `META`            ← `dashboard_data["META"]`
- `DATA_QUALITY`    ← `dashboard_data["DATA_QUALITY"]`

Save completed file to:
- `/mnt/user-data/outputs/dashboard.jsx`

### Step 7 — Export PDF (optional)

Use the `pdf` skill guidance from `references/pdf-integration.md`.

```bash
python scripts/export_pdf.py \
    --metrics  /home/claude/metrics.json \
    --manifest /home/claude/charts_manifest.json \
    --output   /mnt/user-data/outputs/report.pdf
```

PDF generator must include chart sections **only** for charts present in `manifest["generated"]`.
Chart IDs are now dynamic (AI-assigned) — do not hardcode `chart_trend.png` etc.

---

## Environment variables

| Variable                      | Required | Default            | Description                          |
|-------------------------------|----------|--------------------|--------------------------------------|
| `AI_GATEWAY_API_KEY`          | Yes      | —                  | Vercel AI Gateway key                |
| `RECOMMENDATION_MODEL`        | No       | `openai/gpt-5.2`   | Model for both plan + recommendations|
| `AI_GATEWAY_TIMEOUT_SECONDS`  | No       | `30`               | Per-call timeout                     |
| `AI_GATEWAY_RETRY_ATTEMPTS`   | No       | `1`                | Retry count on transient errors      |

If `AI_GATEWAY_API_KEY` is missing, `plan_charts.py` falls back to heuristic mode
and logs `plan_source: "fallback"`. The pipeline still completes.

---

## Quality checklist

### Before delivering

Parse + plan:
- `column_profile` contains all columns from the CSV
- `plan_source` is `"llm"` (not `"fallback"`) for best results
- All spec column names exist in `column_profile`
- At least 3 charts in `chart_plan.json`

Metrics:
- `primary_measure` is not null
-  KPI values are non-zero and make sense for the domain
- `data_quality.summary.score` is present

Charts:
- All `manifest["generated"]` PNGs exist on disk
- No chart uses hardcoded "Revenue" / "Product" labels — uses actual column names
- Skipped charts have a concrete reason

Dashboard:
- All 9 data constants injected (KPI_DATA, TREND_DATA, TOP_ITEMS, ITEM_SHARE,
      DIMENSIONS, RECOMMENDATIONS, ROLES, META, DATA_QUALITY)
- KPI card labels reflect actual column names (not hardcoded "Total Revenue")
- Trend axis labels use `primary_date` and `primary_measure` column names
- DIMENSIONS array renders correct number of breakdown charts
- Data quality badge visible in header
- Responsive layout

PDF (if generated):
- Chart sections only for charts in `manifest["generated"]`
- No hardcoded chart filenames
- KPI values match dashboard
- No placeholder text

---

## Deliver

Present outputs:
- `/mnt/user-data/outputs/dashboard.jsx`
- `/mnt/user-data/outputs/report.pdf` (if requested)

Close with a short executive summary (3–5 sentences):
- domain detected (sales / clinic / logistics / etc.)
- most important finding from the data
- top recommended action
- data quality grade and any notable warnings