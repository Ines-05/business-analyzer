from __future__ import annotations

import json
import os
import shutil
import uuid
import importlib.util
import logging
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

try:
    from .insights import build_visual_insights
    from .llm_recommendations import (
        RecommendationGenerationError,
        generate_recommendations_with_debug,
        resolve_model,
    )
    from .pipeline import (
        ALLOWED_EXTENSIONS,
        CHART_FILES,
        REPORT_FILENAME,
        AnalysisError,
        run_analysis,
        run_report,
    )
except ImportError:  # Supports running `python app/main.py`
    from insights import build_visual_insights
    from llm_recommendations import (
        RecommendationGenerationError,
        generate_recommendations_with_debug,
        resolve_model,
    )
    from pipeline import (
        ALLOWED_EXTENSIONS,
        CHART_FILES,
        REPORT_FILENAME,
        AnalysisError,
        run_analysis,
        run_report,
    )

BASE_DIR = Path(__file__).resolve().parent.parent
ANALYSES_DIR = BASE_DIR / "runtime" / "analyses"
ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env", override=False)
logger = logging.getLogger(__name__)
CHART_ID_RE = re.compile(r"^[a-z0-9_-]+$")

app = FastAPI(title="PME Startup Business Analyzer", version="1.0.0")
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

def _result_file_path(analysis_id: str) -> Path:
    return ANALYSES_DIR / analysis_id / "output" / "analysis_result.json"


def _chart_file_path(analysis_id: str, chart_id: str) -> Path:
    if not CHART_ID_RE.match(chart_id):
        raise HTTPException(status_code=404, detail="Chart not found.")
    return ANALYSES_DIR / analysis_id / "output" / "charts" / f"chart_{chart_id}.png"

@app.get("/", include_in_schema=False)
def home() -> dict:
    return {"message": "Aster Analytics API is running"}

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/analyses")
def list_analyses(limit: int = 20) -> dict:
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

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
            with result_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue

        meta = data.get("meta", {})
        rows.append(
            {
                "analysis_id": data.get("analysis_id", analysis_dir.name),
                "company_name": data.get("company_name", ""),
                "source_file": meta.get("source_file", ""),
                "row_count": meta.get("row_count", 0),
                "date_range": meta.get("date_range", {}),
                "kpis": data.get("kpis", {}),
                "model_used": data.get("model_used", ""),
                "recommendations_source": data.get("recommendations_source", ""),
                "created_at": analysis_dir.stat().st_mtime,
            }
        )
        if len(rows) >= limit:
            break

    return {"items": rows}


@app.post("/api/analyze")
def analyze(
    company_name: str = Form(default=""),
    file: UploadFile = File(...),
) -> dict:
    filename = file.filename or ""
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
                "Excel upload requires the openpyxl package, which is not available in this environment. "
                "Install openpyxl or upload CSV instead."
            ),
        )

    analysis_id = uuid.uuid4().hex[:12]
    run_dir = ANALYSES_DIR / analysis_id
    upload_dir = run_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"input{extension}"

    with upload_path.open("wb") as destination:
        shutil.copyfileobj(file.file, destination)

    try:
        result = run_analysis(upload_path=upload_path, run_dir=run_dir)
    except AnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc
    finally:
        file.file.close()

    charts = []
    generated_charts = result.charts_manifest.get("generated", [])
    if isinstance(generated_charts, list) and generated_charts:
        for item in generated_charts:
            chart_id = str(item.get("id", "")).strip().lower()
            if not chart_id or not CHART_ID_RE.match(chart_id):
                continue
            path = _chart_file_path(analysis_id, chart_id)
            available = path.exists()
            title = str(item.get("title") or chart_id.replace("_", " ").title())
            charts.append(
                {
                    "id": chart_id,
                    "label": title,
                    "title": title,
                    "available": available,
                    "score": item.get("score"),
                    "selection_reason": item.get("selection_reason"),
                    "url": f"/api/analyses/{analysis_id}/charts/{chart_id}" if available else None,
                    "download_url": (
                        f"/api/analyses/{analysis_id}/charts/{chart_id}?download=true"
                        if available
                        else None
                    ),
                }
            )
    else:
        # Backward-compatible fallback for older runs without a manifest.
        for chart_id, filename in CHART_FILES.items():
            path = result.charts[chart_id]
            available = path.exists()
            charts.append(
                {
                    "id": chart_id,
                    "label": chart_id.replace("_", " ").title(),
                    "available": available,
                    "url": f"/api/analyses/{analysis_id}/charts/{chart_id}" if available else None,
                    "download_url": (
                        f"/api/analyses/{analysis_id}/charts/{chart_id}?download=true"
                        if available
                        else None
                    ),
                }
            )

    recommendations = []
    recommendations_source = "llm"
    recommendations_warning = None
    recommendations_debug = {}
    model_used = resolve_model()
    try:
        recommendations, recommendations_debug = generate_recommendations_with_debug(
            metrics=result.metrics,
            company_name=company_name,
            model=model_used,
        )
        logger.info(
            "Analysis %s recommendations generated by LLM | model=%s count=%s",
            analysis_id,
            model_used,
            len(recommendations),
        )
    except RecommendationGenerationError as exc:
        recommendations_source = "llm_error"
        recommendations_warning = str(exc)
        recommendations_debug = getattr(exc, "debug", {})
        logger.warning(
            "Analysis %s LLM recommendation generation failed | model=%s warning=%s debug=%s",
            analysis_id,
            model_used,
            recommendations_warning,
            recommendations_debug,
        )

    response_payload = {
        "analysis_id": analysis_id,
        "company_name": company_name.strip(),
        "meta": result.metrics.get("meta", {}),
        "kpis": result.metrics.get("kpis", {}),
        "kpi_display": result.dashboard_data.get("KPI_DATA", {}),
        "revenue_trend": result.metrics.get("revenue_trend", []),
        "top_products": result.metrics.get("top_products", []),
        "product_share": result.metrics.get("product_share", []),
        "by_region": result.metrics.get("by_region", []),
        "by_category": result.metrics.get("by_category", []),
        "by_rep": result.metrics.get("by_rep", []),
        "by_quantity": result.metrics.get("by_quantity", []),
        "recommendations": recommendations,
        "recommendations_source": recommendations_source,
        "recommendations_warning": recommendations_warning,
        "recommendations_debug": recommendations_debug,
        "model_provider": "vercel-ai-gateway",
        "model_used": model_used,
        "visual_insights": build_visual_insights(result.metrics, recommendations),
        "charts": charts,
        "chart_selection": result.charts_manifest.get("selection", {}),
    }
    result_path = _result_file_path(analysis_id)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("w", encoding="utf-8") as handle:
        json.dump(response_payload, handle, indent=2)

    return response_payload


@app.get("/api/analyses/{analysis_id}/result")
def get_analysis_result(analysis_id: str) -> dict:
    result_path = _result_file_path(analysis_id)
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Analysis result not found.")

    try:
        with result_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        # Rebuild visual insights dynamically so wording updates (e.g., FR localization)
        # apply to both new and previously saved analyses.
        metrics_for_insights = {
            "kpis": payload.get("kpis", {}),
            "revenue_trend": payload.get("revenue_trend", []),
            "top_products": payload.get("top_products", []),
        }
        payload["visual_insights"] = build_visual_insights(
            metrics_for_insights,
            payload.get("recommendations", []),
        )
        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read analysis result: {exc}",
        ) from exc


@app.get("/api/analyses/{analysis_id}/raw")
def get_raw_rows(analysis_id: str) -> dict:
    parsed_path = ANALYSES_DIR / analysis_id / "tmp" / "parsed_data.json"
    if not parsed_path.exists():
        raise HTTPException(status_code=404, detail="Raw data not found.")
    try:
        with parsed_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return {"rows": data.get("rows", [])}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read raw data: {exc}") from exc


@app.get("/api/analyses/{analysis_id}/charts/{chart_id}")
def get_chart(analysis_id: str, chart_id: str, download: bool = False) -> FileResponse:
    chart_id = chart_id.strip().lower()
    chart_path = _chart_file_path(analysis_id, chart_id)
    if not chart_path.exists():
        raise HTTPException(status_code=404, detail="Chart file does not exist.")

    if download:
        return FileResponse(
            path=chart_path,
            media_type="image/png",
            filename=f"{analysis_id}-chart_{chart_id}.png",
        )
    return FileResponse(path=chart_path, media_type="image/png")


@app.get("/api/analyses/{analysis_id}/report")
def get_report(analysis_id: str, download: bool = False) -> FileResponse:
    run_dir = ANALYSES_DIR / analysis_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Analysis not found.")

    report_path = run_dir / "output" / REPORT_FILENAME
    if not report_path.exists():
        if importlib.util.find_spec("reportlab") is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "PDF report generation requires the reportlab package, which is not available in this "
                    "environment. Install reportlab to enable reports."
                ),
            )
        try:
            report_path = run_report(run_dir)
        except AnalysisError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"Failed to build report: {exc}") from exc

    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found.")

    if download:
        return FileResponse(
            path=report_path,
            media_type="application/pdf",
            filename=f"{analysis_id}-report.pdf",
        )
    return FileResponse(path=report_path, media_type="application/pdf")


if __name__ == "__main__":
    import uvicorn

    # Ensure `app.main` is importable by Uvicorn reload subprocesses.
    os.chdir(BASE_DIR)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
