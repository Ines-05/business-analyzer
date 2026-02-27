from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
CHART_FILES = {
    "trend": "chart_trend.png",
    "products": "chart_products.png",
    "share": "chart_share.png",
    "region": "chart_region.png",
    "rep": "chart_rep.png",
    "daily": "chart_daily.png",
    "quantity": "chart_quantity.png",
    "category": "chart_category.png",
}
REPORT_FILENAME = "report.pdf"
MANIFEST_FILENAME = "charts_manifest.json"

BASE_DIR = Path(__file__).resolve().parent.parent
SKILL_DIR = BASE_DIR / ".codex" / "skills" / "business-analyzer"
SCRIPTS_DIR = SKILL_DIR / "scripts"


class AnalysisError(RuntimeError):
    pass


@dataclass
class AnalysisResult:
    metrics: dict
    dashboard_data: dict
    charts: dict[str, Path]
    charts_manifest: dict


def _run_script(script_name: str, args: list[str], timeout: int = 180) -> None:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise AnalysisError(f"Required script not found: {script_path}")

    command = [sys.executable, str(script_path), *args]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if completed.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part and part.strip()
        )
        raise AnalysisError(
            f"{script_name} failed with exit code {completed.returncode}.\n{output}"
        )


def _load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise AnalysisError(f"Expected output file missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"Output file is not valid JSON: {path}") from exc


def run_analysis(upload_path: Path, run_dir: Path) -> AnalysisResult:
    tmp_dir = run_dir / "tmp"
    output_dir = run_dir / "output"
    charts_dir = output_dir / "charts"
    manifest_path = tmp_dir / MANIFEST_FILENAME

    tmp_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    parsed_path = tmp_dir / "parsed_data.json"
    metrics_path = tmp_dir / "metrics.json"
    dashboard_path = tmp_dir / "dashboard_data.json"

    _run_script(
        "parse_data.py",
        ["--input", str(upload_path), "--output", str(parsed_path)],
    )
    _run_script(
        "compute_metrics.py",
        ["--input", str(parsed_path), "--output", str(metrics_path)],
    )
    _run_script(
        "build_dashboard_json.py",
        ["--input", str(metrics_path), "--output", str(dashboard_path)],
    )
    _run_script(
        "generate_charts.py",
        [
            "--input",
            str(metrics_path),
            "--output-dir",
            str(charts_dir),
            "--manifest",
            str(manifest_path),
        ],
    )

    metrics = _load_json(metrics_path)
    dashboard_data = _load_json(dashboard_path)
    charts_manifest = _load_json(manifest_path)

    charts = {
        chart_id: charts_dir / filename for chart_id, filename in CHART_FILES.items()
    }
    return AnalysisResult(
        metrics=metrics,
        dashboard_data=dashboard_data,
        charts=charts,
        charts_manifest=charts_manifest,
    )


def run_report(run_dir: Path, timeout: int = 240) -> Path:
    tmp_dir = run_dir / "tmp"
    output_dir = run_dir / "output"
    metrics_path = tmp_dir / "metrics.json"
    manifest_path = tmp_dir / MANIFEST_FILENAME
    result_payload_path = output_dir / "analysis_result.json"
    report_metrics_path = tmp_dir / "report_metrics.json"

    if not metrics_path.exists():
        raise AnalysisError(f"Metrics file not found for report: {metrics_path}")
    if not manifest_path.exists():
        raise AnalysisError(
            f"Charts manifest not found for report: {manifest_path}. "
            "Run analysis first to generate chart selections."
        )

    # Prefer the persisted API payload recommendations (LLM when available),
    # so the PDF stays consistent with what the dashboard shows.
    metrics_for_report = _load_json(metrics_path)
    if result_payload_path.exists():
        try:
            result_payload = _load_json(result_payload_path)
            recommendations = result_payload.get("recommendations")
            if isinstance(recommendations, list):
                metrics_for_report["recommendations"] = recommendations
        except AnalysisError:
            # Keep report generation resilient; fall back to metrics.json recommendations.
            pass

    with report_metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics_for_report, handle, indent=2)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / REPORT_FILENAME

    _run_script(
        "export_pdf.py",
        [
            "--metrics",
            str(report_metrics_path),
            "--manifest",
            str(manifest_path),
            "--output",
            str(report_path),
        ],
        timeout=timeout,
    )

    return report_path
