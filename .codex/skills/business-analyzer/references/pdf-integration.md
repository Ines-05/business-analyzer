# PDF Integration Notes

This skill delegates PDF standards to the installed `pdf` skill:

- Path: `C:/Users/HP/.codex/skills/pdf/SKILL.md`
- Core rule: use `reportlab.platypus` for creation
- Visual QA: render pages to PNG and inspect layout before delivery

## Inputs and Outputs

- Input metrics: `.codex/skills/business-analyzer/tmp/metrics.json`
- Input charts: `.codex/skills/business-analyzer/tmp/chart_*.png`
- Output report: `.codex/skills/business-analyzer/output/sales-report.pdf`

## Required Steps

1. Run `generate_charts.py` before `export_pdf.py`.
2. Ensure chart files exist:
   - `chart_trend.png`
   - `chart_products.png`
   - `chart_share.png`
3. Run `export_pdf.py` with `--metrics`, `--charts`, and `--output`.
4. Render the final PDF using `pdftoppm -png` and inspect:
   - clipped or overlapping text
   - unreadable axis labels
   - incorrect page breaks
   - missing headers or section spacing
