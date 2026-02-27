from __future__ import annotations


def _currency(value: float) -> str:
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def build_visual_insights(
    metrics: dict, recommendations: list[dict] | None = None
) -> list[dict]:
    insights: list[dict] = []
    kpis = metrics.get("kpis", {})
    trend = metrics.get("revenue_trend", [])
    top_products = metrics.get("top_products", [])
    recommendations = recommendations or metrics.get("recommendations", [])

    if trend:
        highest = max(trend, key=lambda item: item.get("revenue", 0))
        lowest = min(trend, key=lambda item: item.get("revenue", 0))
        insights.append(
            {
                "title": "Signal de tendance du chiffre d'affaires",
                "explanation": (
                    f"Meilleure période : {highest.get('period', 'N/A')} avec "
                    f"{_currency(highest.get('revenue', 0))}. "
                    f"Période la plus faible : {lowest.get('period', 'N/A')} avec "
                    f"{_currency(lowest.get('revenue', 0))}."
                ),
                "takeaway": (
                    "Comparez ces deux périodes pour analyser les campagnes, le pricing et l'exécution commerciale."
                ),
            }
        )

    if top_products:
        top = top_products[0]
        top_3_share = sum(item.get("share_pct", 0) for item in top_products[:3])
        insights.append(
            {
                "title": "Concentration produit",
                "explanation": (
                    f"Le produit leader '{top.get('product', 'N/A')}' représente "
                    f"{top.get('share_pct', 0):.1f}% du CA "
                    f"({_currency(top.get('revenue', 0))}). "
                    f"Les 3 premiers produits totalisent {top_3_share:.1f}%."
                ),
                "takeaway": (
                    "Si la concentration est élevée, diversifiez la croissance sur les produits suivants."
                ),
            }
        )

    growth = float(kpis.get("period_growth_pct", 0))
    momentum = "positive" if growth >= 0 else "négative"
    insights.append(
        {
            "title": "Momentum récent",
            "explanation": (
                f"La croissance de la dernière période est de {_pct(growth)}, le momentum court terme est donc {momentum}."
            ),
            "takeaway": (
                "Identifiez ce qui a changé sur la dernière période pour amplifier ou corriger rapidement."
            ),
        }
    )

    if recommendations:
        first = recommendations[0]
        insights.append(
            {
                "title": "Action prioritaire",
                "explanation": (
                    f"Recommandation priorité {first.get('priority', 'Medium')} : "
                    f"{first.get('title', 'Sans titre')}."
                ),
                "takeaway": first.get("action", "Aucune action générée."),
            }
        )

    return insights[:4]
