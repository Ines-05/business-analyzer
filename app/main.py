"""
main.py — FastAPI backend for the PME Business Analyzer.

Changes from previous version:
  - CHART_FILES import removed (charts are now dynamic from manifest)
  - response_payload updated: top_products → top_items, product_share → item_share,
    by_region/by_rep/by_category → dimensions dict
  - roles + plan_source added to response for frontend context
  - chart listing reads directly from charts_manifest["generated"]
    (already done in the old version's fallback path — now the primary path)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import uuid
import importlib.util
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .insights import build_visual_insights
    from .llm_recommendations import (
        RecommendationGenerationError,
        generate_recommendations_with_debug,
        resolve_model,
    )
    from .pipeline import (
        ALLOWED_EXTENSIONS,
        REPORT_FILENAME,
        AnalysisError,
        run_analysis,
        run_report,
    )
except ImportError:
    from insights import build_visual_insights
    from llm_recommendations import (
        RecommendationGenerationError,
        generate_recommendations_with_debug,
        resolve_model,
    )
    from pipeline import (
        ALLOWED_EXTENSIONS,
        REPORT_FILENAME,
        AnalysisError,
        run_analysis,
        run_report,
    )

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR     = Path(__file__).resolve().parent.parent
ANALYSES_DIR = BASE_DIR / "runtime" / "analyses"
ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env", override=False)

logger      = logging.getLogger(__name__)
CHART_ID_RE = re.compile(r"^[a-z0-9_-]+$")
ANALYSIS_STEPS = [
    {"id": "parse_data", "label": "Import du fichier et profilage des colonnes"},
    {"id": "plan_charts", "label": "Planification IA des graphiques"},
    {"id": "compute_metrics", "label": "Calcul des metriques et KPIs"},
    {"id": "build_dashboard_json", "label": "Preparation des donnees dashboard"},
    {"id": "chart_runner", "label": "Generation des graphiques"},
    {"id": "recommendations", "label": "Generation des recommandations IA"},
]

app = FastAPI(title="PME Business Analyzer", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _result_file_path(analysis_id: str) -> Path:
    return ANALYSES_DIR / analysis_id / "output" / "analysis_result.json"


def _chart_file_path(analysis_id: str, chart_id: str) -> Path:
    if not CHART_ID_RE.match(chart_id):
        raise HTTPException(status_code=404, detail="Chart not found.")
    return ANALYSES_DIR / analysis_id / "output" / "charts" / f"chart_{chart_id}.png"


def _build_chart_list(analysis_id: str, charts_manifest: dict) -> list[dict]:
    """
    Build the charts list for the API response from the manifest.
    Reads directly from manifest["generated"] — no hardcoded chart IDs.
    """
    charts = []
    for item in charts_manifest.get("generated", []):
        chart_id = str(item.get("id", "")).strip().lower()
        if not chart_id or not CHART_ID_RE.match(chart_id):
            continue

        path      = _chart_file_path(analysis_id, chart_id)
        available = path.exists()
        title     = str(item.get("title") or chart_id.replace("_", " ").title())

        charts.append({
            "id":           chart_id,
            "label":        title,
            "title":        title,
            "type":         item.get("type"),
            "spec":         item.get("spec"),
            "rationale":    item.get("rationale"),
            "plan_source":  item.get("plan_source"),
            "available":    available,
            "url":          f"/api/analyses/{analysis_id}/charts/{chart_id}" if available else None,
            "download_url": (
                f"/api/analyses/{analysis_id}/charts/{chart_id}?download=true"
                if available else None
            ),
        })
    return charts


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def home() -> dict:
    return {"message": "PME Business Analyzer API is running"}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/analysis-steps")
def analysis_steps() -> dict:
    return {"items": ANALYSIS_STEPS}


@app.get("/api/analyses")
def list_analyses(limit: int = 20) -> dict:
    limit = max(1, min(limit, 100))
    rows: list[dict] = []

    for analysis_dir in sorted(
        ANALYSES_DIR.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        if not analysis_dir.is_dir():
            continue
        result_path = analysis_dir / "output" / "analysis_result.json"
        if not result_path.exists():
            continue
        try:
            with result_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        meta = data.get("meta", {})
        rows.append({
            "analysis_id":          data.get("analysis_id", analysis_dir.name),
            "company_name":         data.get("company_name", ""),
            "source_file":          meta.get("source_file", ""),
            "row_count":            meta.get("row_count", 0),
            "date_range":           meta.get("date_range", {}),
            "kpis":                 data.get("kpis", {}),
            "roles":                data.get("roles", {}),
            "plan_source":          data.get("plan_source", "unknown"),
            "model_used":           data.get("model_used", ""),
            "recommendations_source": data.get("recommendations_source", ""),
            "created_at":           analysis_dir.stat().st_mtime,
        })
        if len(rows) >= limit:
            break

    return {"items": rows}


@app.post("/api/analyze")
def analyze(
    company_name: str  = Form(default=""),
    file:         UploadFile = File(...),
) -> dict:
    # ── Validate file type ────────────────────────────────────────────────────
    filename  = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload .csv, .xlsx, or .xls.",
        )
    if extension in {".xlsx", ".xls"} and importlib.util.find_spec("openpyxl") is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Excel upload requires openpyxl, which is not installed. "
                "Install openpyxl or upload a CSV instead."
            ),
        )

    # ── Save upload ───────────────────────────────────────────────────────────
    analysis_id = uuid.uuid4().hex[:12]
    run_dir     = ANALYSES_DIR / analysis_id
    upload_dir  = run_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"input{extension}"

    with upload_path.open("wb") as dest:
        shutil.copyfileobj(file.file, dest)

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        result = run_analysis(upload_path=upload_path, run_dir=run_dir)
    except AnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc
    finally:
        file.file.close()

    # ── Build chart list from manifest ────────────────────────────────────────
    charts = _build_chart_list(analysis_id, result.charts_manifest)

    # ── LLM recommendations ───────────────────────────────────────────────────
    recommendations        = []
    recommendations_source = "llm"
    recommendations_warning = None
    recommendations_debug  = {}
    model_used             = resolve_model()

    try:
        recommendations, recommendations_debug = generate_recommendations_with_debug(
            metrics=result.metrics,
            company_name=company_name,
            model=model_used,
        )
        logger.info(
            "Analysis %s: %d recommendations | model=%s",
            analysis_id, len(recommendations), model_used,
        )
    except RecommendationGenerationError as exc:
        recommendations_source  = "llm_error"
        recommendations_warning = str(exc)
        recommendations_debug   = getattr(exc, "debug", {})
        logger.warning(
            "Analysis %s: LLM recommendations failed | %s",
            analysis_id, recommendations_warning,
        )

    # ── Build response payload ────────────────────────────────────────────────
    metrics = result.metrics
    roles   = metrics.get("roles", {})

    response_payload = {
        # Identity
        "analysis_id":  analysis_id,
        "company_name": company_name.strip(),

        # Meta
        "meta":         metrics.get("meta", {}),
        "roles":        roles,
        "plan_source":  metrics.get("meta", {}).get("plan_source", "unknown"),

        # KPIs
        "kpis":         metrics.get("kpis", {}),
        "kpi_display":  result.dashboard_data.get("KPI_DATA", {}),

        # Trend
        "revenue_trend": metrics.get("revenue_trend", []),

        # Top items (was top_products)
        "top_items":    metrics.get("top_items", []),
        "item_share":   metrics.get("item_share", []),

        # Dynamic dimension breakdowns (was by_region / by_rep / by_category)
        "dimensions":   metrics.get("dimensions", {}),

        # Data quality
        "data_quality": metrics.get("data_quality", {}).get("summary", {}),

        # Recommendations
        "recommendations":        recommendations,
        "recommendations_source": recommendations_source,
        "recommendations_warning": recommendations_warning,
        "recommendations_debug":  recommendations_debug,

        # Model info
        "model_provider": "vercel-ai-gateway",
        "model_used":     model_used,

        # Visual insights (built from metrics + recommendations)
        "visual_insights": build_visual_insights(metrics, recommendations),

        # Charts
        "charts":           charts,
        "chart_selection":  result.charts_manifest.get("summary", {}),
    }

    # ── Persist result ────────────────────────────────────────────────────────
    result_path = _result_file_path(analysis_id)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(response_payload, f, indent=2, default=str)

    return response_payload


@app.get("/api/analyses/{analysis_id}/result")
def get_analysis_result(analysis_id: str) -> dict:
    result_path = _result_file_path(analysis_id)
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    try:
        with result_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        # Rebuild visual insights dynamically (keeps wording current)
        metrics_for_insights = {
            "kpis":          payload.get("kpis", {}),
            "revenue_trend": payload.get("revenue_trend", []),
            "top_items":     payload.get("top_items", []),
        }
        payload["visual_insights"] = build_visual_insights(
            metrics_for_insights,
            payload.get("recommendations", []),
        )
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read result: {exc}") from exc


@app.get("/api/analyses/{analysis_id}/raw")
def get_raw_rows(analysis_id: str) -> dict:
    parsed_path = ANALYSES_DIR / analysis_id / "tmp" / "parsed_data.json"
    if not parsed_path.exists():
        raise HTTPException(status_code=404, detail="Raw data not found.")
    try:
        with parsed_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "rows":           data.get("rows", []),
            "column_profile": data.get("column_profile", []),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read raw data: {exc}") from exc


@app.get("/api/analyses/{analysis_id}/plan")
def get_chart_plan(analysis_id: str) -> dict:
    """Return the AI chart plan for debugging / transparency."""
    plan_path = ANALYSES_DIR / analysis_id / "tmp" / "chart_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Chart plan not found.")
    try:
        with plan_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read chart plan: {exc}") from exc


@app.get("/api/analyses/{analysis_id}/charts/{chart_id}")
def get_chart(analysis_id: str, chart_id: str, download: bool = False) -> FileResponse:
    chart_path = _chart_file_path(analysis_id, chart_id)
    if not chart_path.exists():
        raise HTTPException(status_code=404, detail="Chart file not found.")

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="chart_{chart_id}.png"'

    return FileResponse(
        path=str(chart_path),
        media_type="image/png",
        headers=headers,
    )


@app.post("/api/analyses/{analysis_id}/report")
def generate_report(analysis_id: str) -> dict:
    run_dir = ANALYSES_DIR / analysis_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Analysis not found.")
    try:
        report_path = run_report(run_dir=run_dir)
    except AnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}") from exc

    return {
        "analysis_id": analysis_id,
        "report_url":  f"/api/analyses/{analysis_id}/report/download",
        "available":   report_path.exists(),
    }


@app.get("/api/analyses/{analysis_id}/report")
def get_report(analysis_id: str, download: bool = False):
    """
    Backward-compatible endpoint:
    - GET /report                -> ensure report exists and return metadata
    - GET /report?download=true  -> ensure report exists and stream PDF
    """
    run_dir = ANALYSES_DIR / analysis_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Analysis not found.")

    report_path = run_dir / "output" / REPORT_FILENAME
    if not report_path.exists():
        try:
            report_path = run_report(run_dir=run_dir)
        except AnalysisError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}") from exc

    if download:
        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{analysis_id}.pdf"'},
        )

    return {
        "analysis_id": analysis_id,
        "report_url":  f"/api/analyses/{analysis_id}/report/download",
        "available":   report_path.exists(),
    }


@app.get("/api/analyses/{analysis_id}/report/download")
def download_report(analysis_id: str) -> FileResponse:
    report_path = ANALYSES_DIR / analysis_id / "output" / REPORT_FILENAME
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report not found. Call POST /report first.",
        )
    return FileResponse(
        path=str(report_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{analysis_id}.pdf"'},
    )


# ---------------------------------------------------------------------------
# Static file serving (frontend build)
# ---------------------------------------------------------------------------

_frontend_dist = BASE_DIR / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
