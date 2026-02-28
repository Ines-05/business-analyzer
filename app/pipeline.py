"""
pipeline.py — Orchestrate the full analysis pipeline.

New sequence:
    1. parse_data.py        → parsed_data.json      (domain-agnostic column profiling)
    2. plan_charts.py       → chart_plan.json        (AI role assignment + chart selection)
    3. compute_metrics.py   → metrics.json           (KPIs using AI-assigned roles)
    4. build_dashboard_json.py → dashboard_data.json (React payload)
    5. chart_runner.py      → chart PNGs + charts_manifest.json

Charts are now stored as:
    output/charts/chart_<id>.png
where <id> comes from the AI plan (e.g. chart_revenue_trend.png, chart_by_technician.png).

charts_manifest.json contract is unchanged — same "generated" / "skipped" keys
as the old generate_charts.py, so main.py and export_pdf.py need minimal changes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
REPORT_FILENAME    = "report.pdf"
MANIFEST_FILENAME  = "charts_manifest.json"

BASE_DIR    = Path(__file__).resolve().parent.parent
SKILL_DIR   = BASE_DIR / ".codex" / "skills" / "business-analyzer"
SCRIPTS_DIR = SKILL_DIR / "scripts"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AnalysisError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    metrics:         dict
    dashboard_data:  dict
    charts:          dict[str, Path]          # chart_id → PNG path
    charts_manifest: dict


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_script(candidates: str | list[str] | tuple[str, ...]) -> tuple[str, Path]:
    if isinstance(candidates, str):
        names = [candidates]
    else:
        names = list(candidates)

    for name in names:
        path = SCRIPTS_DIR / name
        if path.exists():
            return name, path

    checked = ", ".join(str(SCRIPTS_DIR / name) for name in names)
    raise AnalysisError(f"Required script not found. Checked: {checked}")


def _run_script(
    script_candidates: str | list[str] | tuple[str, ...],
    args: list[str],
    timeout: int = 180,
) -> None:
    """Run a skill script as a subprocess. Raises AnalysisError on failure."""
    script_name, script_path = _resolve_script(script_candidates)

    command = [sys.executable, str(script_path), *args]
    env = os.environ.copy()
    # Force UTF-8 in child process stdout/stderr to avoid Windows cp1252 crashes.
    env.setdefault("PYTHONIOENCODING", "utf-8")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )

    if completed.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part and part.strip()
        )
        raise AnalysisError(
            f"{script_name} failed (exit {completed.returncode}).\n{output}"
        )

    # Echo stdout for logging
    if completed.stdout.strip():
        for line in completed.stdout.strip().splitlines():
            try:
                print(f"  {line}")
            except UnicodeEncodeError:
                # Keep pipeline robust on Windows terminals using cp1252.
                safe = line.encode("ascii", errors="replace").decode("ascii")
                print(f"  {safe}")


def _load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise AnalysisError(f"Expected output file missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"Output file is not valid JSON: {path}") from exc


def _charts_from_manifest(manifest: dict, charts_dir: Path) -> dict[str, Path]:
    """
    Build chart_id → Path mapping from the manifest's generated list.
    Compatible with both old (fixed ids) and new (AI-assigned ids) manifests.
    """
    charts = {}
    for entry in manifest.get("generated", []):
        chart_id = entry.get("id")
        # Prefer the path recorded in manifest; fall back to convention
        recorded_path = entry.get("path")
        if recorded_path and Path(recorded_path).exists():
            charts[chart_id] = Path(recorded_path)
        else:
            # Fallback: look in charts_dir by convention
            candidate = charts_dir / f"chart_{chart_id}.png"
            if candidate.exists():
                charts[chart_id] = candidate
    return charts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_analysis(upload_path: Path, run_dir: Path) -> AnalysisResult:
    """
    Run the full analysis pipeline for a single uploaded file.

    Directory layout:
        run_dir/
          tmp/
            parsed_data.json
            chart_plan.json
            metrics.json
            dashboard_data.json
            charts_manifest.json
          output/
            charts/
              chart_<id>.png ...
            analysis_result.json   (written by main.py after this returns)
    """
    tmp_dir    = run_dir / "tmp"
    output_dir = run_dir / "output"
    charts_dir = output_dir / "charts"

    tmp_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    parsed_path    = tmp_dir / "parsed_data.json"
    plan_path      = tmp_dir / "chart_plan.json"
    metrics_path   = tmp_dir / "metrics.json"
    dashboard_path = tmp_dir / "dashboard_data.json"
    manifest_path  = tmp_dir / MANIFEST_FILENAME

    # ── Step 1: Parse ────────────────────────────────────────────────────────
    print("\n[pipeline] Step 1 — parse_data.py")
    _run_script("parse_data.py", [
        "--input",  str(upload_path),
        "--output", str(parsed_path),
    ])

    # ── Step 2: AI chart plan ────────────────────────────────────────────────
    print("\n[pipeline] Step 2 — plan_charts.py")
    _run_script(("plan_charts.py", "plan_chart.py"), [
        "--input",  str(parsed_path),
        "--output", str(plan_path),
    ], timeout=60)   # AI call — shorter timeout, has its own retry + fallback

    # ── Step 3: Compute metrics ──────────────────────────────────────────────
    print("\n[pipeline] Step 3 — compute_metrics.py")
    _run_script("compute_metrics.py", [
        "--input",  str(parsed_path),
        "--plan",   str(plan_path),
        "--output", str(metrics_path),
    ])

    # ── Step 4: Build dashboard JSON ─────────────────────────────────────────
    print("\n[pipeline] Step 4 — build_dashboard_json.py")
    _run_script("build_dashboard_json.py", [
        "--input",  str(metrics_path),
        "--output", str(dashboard_path),
    ])

    # ── Step 5: Render charts ────────────────────────────────────────────────
    print("\n[pipeline] Step 5 — chart_runner.py")
    _run_script(("chart_runner.py", "chat_runner.py"), [
        "--plan",       str(plan_path),
        "--data",       str(parsed_path),
        "--output-dir", str(charts_dir),
        "--manifest",   str(manifest_path),
    ], timeout=300)   # rendering can be slow for many charts

    # ── Load results ──────────────────────────────────────────────────────────
    metrics         = _load_json(metrics_path)
    dashboard_data  = _load_json(dashboard_path)
    charts_manifest = _load_json(manifest_path)
    charts          = _charts_from_manifest(charts_manifest, charts_dir)

    print(f"\n[pipeline] Analysis complete.")
    print(f"  Charts generated : {len(charts_manifest.get('generated', []))}")
    print(f"  Charts skipped   : {len(charts_manifest.get('skipped', []))}")

    return AnalysisResult(
        metrics=metrics,
        dashboard_data=dashboard_data,
        charts=charts,
        charts_manifest=charts_manifest,
    )


def run_report(run_dir: Path, timeout: int = 240) -> Path:
    """
    Generate a PDF report from a previously completed analysis.
    Reuses the existing charts and metrics — does not re-run the pipeline.
    """
    tmp_dir              = run_dir / "tmp"
    output_dir           = run_dir / "output"
    metrics_path         = tmp_dir / "metrics.json"
    manifest_path        = tmp_dir / MANIFEST_FILENAME
    result_payload_path  = output_dir / "analysis_result.json"
    report_metrics_path  = tmp_dir / "report_metrics.json"

    if not metrics_path.exists():
        raise AnalysisError(f"Metrics not found: {metrics_path}. Run analysis first.")
    if not manifest_path.exists():
        raise AnalysisError(f"Charts manifest not found: {manifest_path}. Run analysis first.")

    # Prefer LLM recommendations from the saved API payload if available
    metrics_for_report = _load_json(metrics_path)
    if result_payload_path.exists():
        try:
            payload = _load_json(result_payload_path)
            recs = payload.get("recommendations")
            if isinstance(recs, list):
                metrics_for_report["recommendations"] = recs
        except AnalysisError:
            pass  # keep metrics.json recommendations as fallback

    with report_metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics_for_report, f, indent=2)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / REPORT_FILENAME

    print("\n[pipeline] Generating PDF report...")
    _run_script("export_pdf.py", [
        "--metrics",  str(report_metrics_path),
        "--manifest", str(manifest_path),
        "--output",   str(report_path),
    ], timeout=timeout)

    return report_path
