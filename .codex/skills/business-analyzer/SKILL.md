---
name: sales-bi-dashboard
description: Transform structured sales data (CSV or Excel files) into a strategic, executive-grade business intelligence dashboard built as a React (.jsx) artifact, with an optional PDF report export for sharing or archiving. Use this skill whenever the user wants to visualize sales data, generate a BI dashboard, get executive insights from sales reports, analyze KPIs or revenue trends, break down performance by product or SKU, or receive AI-powered strategic recommendations from their data - even if they do not use the word dashboard. Also trigger when the user wants to export or download a sales report as a PDF. Trigger for requests like "analyze my sales file", "show me trends in my data", "give me a PDF I can share with leadership", or "export this as a PDF report".
---

# Sales BI Dashboard Skill

Transform structured sales data into a polished React dashboard with KPI cards, trend charts, product/SKU breakdowns, quality-aware chart selection, and strategic recommendations. Optionally export a downloadable PDF report.

## Output modes
- React Dashboard (default)
- PDF Report (optional)
- Both

## Skill structure

```text
sales-bi-dashboard/
|- SKILL.md
|- scripts/
|  |- parse_data.py
|  |- compute_metrics.py
|  |- generate_charts.py
|  |- build_dashboard_json.py
|  `- export_pdf.py
|- references/
|  `- pdf-integration.md
`- templates/
   `- dashboard_template.jsx
```

Read the relevant script before editing behavior.

## Workflow

### Step 1 - Parse input

```bash
ls /mnt/user-data/uploads/
python scripts/parse_data.py --input /mnt/user-data/uploads/<filename>
```

Output: `/home/claude/parsed_data.json`

`parse_data.py` detects columns, normalizes revenue, parses dates, and writes:
- `rows`
- `columns`
- `date_range`
- `date_stats` (`granularity`, `valid_count`, `invalid_count`, `valid_pct`)
- `row_count`
- `source_file`

### Step 2 - Compute metrics + data quality profile

```bash
python scripts/compute_metrics.py --input /home/claude/parsed_data.json
```

Output: `/home/claude/metrics.json`

`compute_metrics.py` computes:
- KPI block (`total_revenue`, `total_orders`, `avg_order_value`, `period_growth_pct`, `top_product`)
- trend/product breakdowns (`revenue_trend`, `top_products`, `product_share`)
- optional dimensions (`by_region`, `by_rep`, `by_quantity`, `by_category`)
- recommendations
- `data_quality` profile used by chart selection:
  - `completeness`
  - `variance`
  - `cardinality`
  - `valid_dates`
  - `outliers`
  - `summary` (score, grade, component scores, notes)

### Step 3 - Generate quality-aware charts (not fixed)

```bash
python scripts/generate_charts.py \
  --input /home/claude/metrics.json \
  --output-dir /home/claude \
  --min-score 55 \
  --max-charts 6
```

Output: chart PNGs + `/home/claude/charts_manifest.json`

Selection rules:
- A chart must pass structural eligibility checks.
- A chart must meet score threshold (`--min-score`) from quality + chart-specific heuristics.
- If more charts are eligible than `--max-charts`, only top-scored charts are rendered.

Manifest contract:
- `generated`: list of rendered charts with `id`, `path`, `title`, `score`, `selection_reason`
- `skipped`: list of skipped charts with explicit `reason` and score/details when available
- `selection`: threshold/cap metadata
- `data_quality`: summary score copied from metrics

Always read `charts_manifest.json` before building downstream assets. Do not assume chart files exist.

### Step 4 - Build React dashboard payload

```bash
python scripts/build_dashboard_json.py --input /home/claude/metrics.json
```

Output: `/home/claude/dashboard_data.json`

Then inject payload into `templates/dashboard_template.jsx` at the data injection block and save to:
- `/mnt/user-data/outputs/sales-dashboard.jsx`

### Step 5 - Export PDF (optional)

Use the `pdf` skill guidance from `references/pdf-integration.md`.

```bash
python scripts/export_pdf.py \
  --metrics /home/claude/metrics.json \
  --manifest /home/claude/charts_manifest.json \
  --output /mnt/user-data/outputs/sales-report.pdf
```

PDF generator must include chart sections only for charts present in `manifest["generated"]`.

## Quality checklist

Dashboard:
- All charts show real data
- KPI sign formatting is correct
- Currency formatting is consistent
- Recommendations cite concrete numbers
- Responsive layout

Chart selection:
- Quality profile exists in `metrics.json`
- Manifest includes score-based selection metadata
- Every skipped chart has a concrete reason

PDF (if generated):
- Consistent margins and section headers
- Chart images not clipped
- KPI values match dashboard metrics
- No placeholder text

## Deliver

Present outputs:
- `/mnt/user-data/outputs/sales-dashboard.jsx`
- `/mnt/user-data/outputs/sales-report.pdf` (if requested)

Close with a short executive summary (3-5 sentences):
- most important finding
- top recommended action
