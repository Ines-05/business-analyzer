"""
export_pdf.py - Step 5: Build an executive PDF report from metrics + charts manifest.

Usage:
    python scripts/export_pdf.py \
      --metrics /home/claude/metrics.json \
      --manifest /home/claude/charts_manifest.json \
      --output /mnt/user-data/outputs/sales-report.pdf
"""

import argparse
import json
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#0a0e1a")
SURFACE = colors.HexColor("#111827")
ACCENT = colors.HexColor("#3b82f6")
WHITE = colors.HexColor("#ffffff")
TEXT_DARK = colors.HexColor("#111827")
MUTED = colors.HexColor("#4b5563")
BORDER = colors.HexColor("#d1d5db")


def load_json(path: str, default: dict = None) -> dict:
    if default is None:
        default = {}
    if not path or not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def currency(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except Exception:
        return "$0"


def percent(value) -> str:
    try:
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1f}%"
    except Exception:
        return "0.0%"


def style_pack():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=NAVY,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=MUTED,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=TEXT_DARK,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=TEXT_DARK,
            leftIndent=12,
            bulletIndent=0,
            spaceAfter=4,
        ),
        "section_band": ParagraphStyle(
            "SectionBand",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=WHITE,
            alignment=1,
        ),
        "card_label": ParagraphStyle(
            "CardLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=MUTED,
            alignment=1,
        ),
        "card_value": ParagraphStyle(
            "CardValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=22,
            textColor=NAVY,
            alignment=1,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MUTED,
        ),
    }


def section_header(title: str, styles: dict, width: float) -> Table:
    band = Table([[Paragraph(title, styles["section_band"])]], colWidths=[width])
    band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return band


def safe_image(path: str, width: float, height: float):
    if not path or not os.path.exists(path):
        return None
    image = Image(path)
    image._restrictSize(width, height)
    return image


def page_cover(story: list, metrics: dict, styles: dict, width: float):
    meta = metrics.get("meta", {})
    date_range = meta.get("date_range", {})

    story.append(Paragraph("Sales Performance Report", styles["title"]))
    story.append(Paragraph("Executive business intelligence dashboard export", styles["subtitle"]))
    story.append(Spacer(1, 0.2 * inch))

    meta_table = Table(
        [
            ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")],
            ["Date range", f"{date_range.get('min', 'N/A')} to {date_range.get('max', 'N/A')}"],
            ["Source file", meta.get("source_file", "N/A")],
        ],
        colWidths=[1.5 * inch, width - 1.5 * inch],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_DARK),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.35 * inch))

    kpis = metrics.get("kpis", {})
    summary = (
        f"Total revenue {currency(kpis.get('total_revenue', 0))}, "
        f"{kpis.get('total_orders', 0):,} orders, "
        f"average order value {currency(kpis.get('avg_order_value', 0))}, "
        f"latest period growth {percent(kpis.get('period_growth_pct', 0))}."
    )
    story.append(Paragraph(summary, styles["body"]))
    story.append(PageBreak())


def page_summary(story: list, metrics: dict, manifest: dict, styles: dict, width: float):
    kpis = metrics.get("kpis", {})
    trend = metrics.get("revenue_trend", [])
    top_products = metrics.get("top_products", [])
    recs = metrics.get("recommendations", [])
    quality = metrics.get("data_quality", {}).get("summary", {})
    generated_charts = manifest.get("generated", [])

    story.append(section_header("Executive Summary", styles, width))
    story.append(Spacer(1, 0.2 * inch))

    highlights = [
        f"Total revenue reached {currency(kpis.get('total_revenue', 0))} across {kpis.get('total_orders', 0):,} orders.",
        f"Average order value is {currency(kpis.get('avg_order_value', 0))}; latest period growth is {percent(kpis.get('period_growth_pct', 0))}.",
    ]

    if trend:
        highlights.append(
            f"Most recent period ({trend[-1].get('period', 'N/A')}) delivered {currency(trend[-1].get('revenue', 0))}."
        )

    if top_products:
        top = top_products[0]
        highlights.append(
            f"Top product is {top.get('product', 'N/A')} with {currency(top.get('revenue', 0))} ({top.get('share_pct', 0):.1f}% share)."
        )

    if quality:
        highlights.append(
            f"Data quality score is {quality.get('score', 'N/A')} ({quality.get('grade', 'N/A')})."
        )

    highlights.append(f"Charts included in report: {len(generated_charts)}.")

    if recs:
        priorities = ", ".join(sorted({str(item.get("priority", "Unknown")) for item in recs}))
        highlights.append(f"Recommendations generated with priorities: {priorities}.")

    for item in highlights[:6]:
        story.append(Paragraph(f"- {item}", styles["bullet"]))

    story.append(PageBreak())


def page_kpis(story: list, metrics: dict, styles: dict, width: float):
    kpis = metrics.get("kpis", {})
    top_product = kpis.get("top_product", {})

    story.append(section_header("KPI Overview", styles, width))
    story.append(Spacer(1, 0.2 * inch))

    cards = [
        [Paragraph("Total Revenue", styles["card_label"]), Paragraph(currency(kpis.get("total_revenue", 0)), styles["card_value"])],
        [Paragraph("Total Orders", styles["card_label"]), Paragraph(f"{kpis.get('total_orders', 0):,}", styles["card_value"])],
        [Paragraph("Avg Order Value", styles["card_label"]), Paragraph(currency(kpis.get("avg_order_value", 0)), styles["card_value"])],
        [Paragraph("Period Growth", styles["card_label"]), Paragraph(percent(kpis.get("period_growth_pct", 0)), styles["card_value"])],
    ]

    card_table = Table(cards, colWidths=[width * 0.45, width * 0.55])
    card_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(card_table)
    story.append(Spacer(1, 0.25 * inch))

    top_text = (
        f"Top product: {top_product.get('name', top_product.get('product', 'N/A'))} "
        f"with {currency(top_product.get('revenue', 0))} "
        f"and {top_product.get('share_pct', 0):.1f}% share."
    )
    story.append(Paragraph(top_text, styles["body"]))
    story.append(PageBreak())


def chart_page(story: list, styles: dict, width: float, title: str, chart_path: str):
    story.append(section_header(title, styles, width))
    story.append(Spacer(1, 0.2 * inch))
    image = safe_image(chart_path, width, 5.7 * inch)
    if image:
        story.append(image)
    else:
        story.append(Paragraph("Chart image not found for this section.", styles["body"]))
    story.append(PageBreak())


def add_generated_chart_pages(story: list, manifest: dict, styles: dict, width: float):
    generated = manifest.get("generated", [])
    if not generated:
        story.append(section_header("Charts", styles, width))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("No charts were generated for this dataset after quality scoring.", styles["body"]))
        story.append(PageBreak())
        return

    for chart in generated:
        title = str(chart.get("title") or chart.get("id", "Chart"))
        path = chart.get("path")
        chart_page(story, styles, width, title, path)


def page_products_table(story: list, metrics: dict, styles: dict, width: float):
    top_products = metrics.get("top_products", [])
    story.append(section_header("Top Products Table", styles, width))
    story.append(Spacer(1, 0.2 * inch))

    if not top_products:
        story.append(Paragraph("No product breakdown was detected in the source data.", styles["body"]))
        story.append(PageBreak())
        return

    rows = [["Product", "Revenue", "Share"]]
    for row in top_products[:10]:
        rows.append(
            [
                str(row.get("product", "N/A")),
                currency(row.get("revenue", 0)),
                f"{float(row.get('share_pct', 0)):.1f}%",
            ]
        )

    table = Table(rows, colWidths=[width * 0.5, width * 0.25, width * 0.25])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(PageBreak())


def page_recommendations(story: list, metrics: dict, styles: dict, width: float):
    recommendations = metrics.get("recommendations", [])
    story.append(section_header("Strategic Recommendations", styles, width))
    story.append(Spacer(1, 0.2 * inch))

    if not recommendations:
        story.append(Paragraph("No recommendations were generated.", styles["body"]))
        return

    priority_colors = {
        "high": colors.HexColor("#ef4444"),
        "medium": colors.HexColor("#f59e0b"),
        "low": ACCENT,
    }

    for rec in recommendations:
        priority = str(rec.get("priority", "Medium"))
        badge_color = priority_colors.get(priority.lower(), ACCENT)
        title = str(rec.get("title", "Recommendation"))
        insight = str(rec.get("insight", ""))
        action = str(rec.get("action", ""))

        header = Table([[f"{priority.upper()} PRIORITY", title]], colWidths=[1.5 * inch, width - 1.5 * inch])
        header.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), badge_color),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e5e7eb")),
                    ("TEXTCOLOR", (0, 0), (0, 0), WHITE),
                    ("TEXTCOLOR", (1, 0), (1, 0), NAVY),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        body = Table(
            [
                [Paragraph("<b>Insight</b>", styles["small"])],
                [Paragraph(insight, styles["body"])],
                [Paragraph("<b>Action</b>", styles["small"])],
                [Paragraph(action, styles["body"])],
            ],
            colWidths=[width],
        )
        body.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        story.append(header)
        story.append(body)
        story.append(Spacer(1, 0.15 * inch))


def build_report(metrics: dict, manifest: dict, output_pdf: str):
    os.makedirs(os.path.dirname(output_pdf) or ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Sales BI Report",
    )

    styles = style_pack()
    story = []
    width = doc.width

    page_cover(story, metrics, styles, width)
    page_summary(story, metrics, manifest, styles, width)
    page_kpis(story, metrics, styles, width)
    add_generated_chart_pages(story, manifest, styles, width)
    page_products_table(story, metrics, styles, width)
    page_recommendations(story, metrics, styles, width)

    doc.build(story)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default="/home/claude/metrics.json", help="Path to metrics.json")
    parser.add_argument("--manifest", default="/home/claude/charts_manifest.json", help="Path to charts_manifest.json")
    parser.add_argument("--output", required=True, help="Output PDF path")
    args = parser.parse_args()

    metrics = load_json(args.metrics, default={})
    manifest = load_json(args.manifest, default={"generated": [], "skipped": []})
    build_report(metrics, manifest, args.output)
    print(f"[export_pdf] Saved report to {args.output}")


if __name__ == "__main__":
    main()
