"""
chart_runner.py - Step 3: Orchestrate chart rendering from AI chart plan.

Reads chart_plan.json (produced by plan_charts.py) and dispatches each chart
to its dedicated renderer script in scripts/charts/.

Produces charts_manifest.json with the same contract as the old generate_charts.py
so that build_dashboard_json.py, export_pdf.py, and main.py need no changes.

Usage:
    python scripts/chart_runner.py \
        --plan       /home/claude/chart_plan.json \
        --data       /home/claude/parsed_data.json \
        --output-dir /home/claude/charts \
        --manifest   /home/claude/charts_manifest.json

Output:
    - One PNG per chart in --output-dir
    - charts_manifest.json:
      {
        "generated": [
          {
            "id":              "revenue_trend",
            "path":            "/home/claude/charts/chart_revenue_trend.png",
            "title":           "Revenue Over Time",
            "type":            "line",
            "spec":            { "x": "date_intervention", "y": "montant_facture" },
            "rationale":       "Shows billing evolution over time.",
            "plan_source":     "llm"
          },
          ...
        ],
        "skipped": [
          {
            "id":     "payment_status",
            "type":   "donut",
            "reason": "Render error: column 'statut' has only 1 unique value"
          }
        ],
        "summary": {
          "total_planned":  5,
          "generated":      4,
          "skipped":        1,
          "plan_source":    "llm",
          "model_used":     "openai/gpt-5.2"
        }
      }

Renderer scripts live in:
    scripts/charts/render_line.py
    scripts/charts/render_bar_horizontal.py
    scripts/charts/render_donut.py
    scripts/charts/render_bar_grouped.py
    scripts/charts/render_scatter.py
    scripts/charts/render_area_stacked.py
    scripts/charts/render_heatmap.py
    scripts/charts/render_funnel.py

Each renderer is called as a subprocess:
    python scripts/charts/render_<type>.py \
        --spec   '<json>'          \
        --data   /path/parsed_data.json \
        --output /path/chart_<id>.png

Each renderer exits 0 on success, non-zero on failure (stderr contains reason).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Renderer registry — maps chart type → renderer script filename
# ---------------------------------------------------------------------------

RENDERER_REGISTRY: dict[str, tuple[str, ...]] = {
    "line":           ("render_line.py",),
    "bar_horizontal": ("render_bar_horizontal.py",),
    "donut":          ("render_donut.py",),
    "bar_grouped":    ("render_bar_grouped.py",),
    "scatter":        ("render_scatter.py",),
    # Backward-compatible fallback for renamed renderer file.
    "area_stacked":   ("render_area_stacked.py", "render_area_scatter.py"),
    "heatmap":        ("render_heatmap.py",),
    "funnel":         ("render_funnel.py",),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_charts_dir(runner_path: Path) -> Path:
    """
    Locate the scripts/charts/ directory relative to this script.
    Works whether called from project root or from scripts/.
    """
    # chart_runner.py lives in scripts/, charts/ is scripts/charts/
    return runner_path.parent / "charts"


def resolve_renderer_path(chart_type: str, charts_dir: Path) -> tuple[Path | None, str | None]:
    renderer_candidates = RENDERER_REGISTRY.get(chart_type)
    if not renderer_candidates:
        return None, f"No renderer registered for chart type '{chart_type}'"

    for renderer_name in renderer_candidates:
        renderer_path = charts_dir / renderer_name
        if renderer_path.exists():
            return renderer_path, None

    checked = ", ".join(str(charts_dir / name) for name in renderer_candidates)
    return None, f"Renderer script not found. Checked: {checked}"


def run_renderer(
    renderer_script: Path,
    chart: dict,
    data_path: str,
    output_path: str,
    timeout: int = 60,
) -> tuple[bool, str]:
    """
    Call a renderer script as a subprocess.
    Returns (success: bool, message: str).
    """
    spec_json = json.dumps(chart.get("spec", {}), ensure_ascii=False)

    cmd = [
        sys.executable,
        str(renderer_script),
        "--spec",   spec_json,
        "--title",  chart.get("title", chart["id"]),
        "--data",   data_path,
        "--output", output_path,
    ]

    try:
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=env,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            error_msg = (result.stderr or result.stdout or "unknown error").strip()
            # Keep only the last meaningful line for brevity
            error_lines = [l for l in error_msg.splitlines() if l.strip()]
            short_error = error_lines[-1] if error_lines else error_msg
            return False, short_error
    except subprocess.TimeoutExpired:
        return False, f"Renderer timed out after {timeout}s"
    except Exception as exc:
        return False, f"Failed to launch renderer: {exc}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Chart runner: dispatch AI chart plan to dedicated renderer scripts."
    )
    parser.add_argument("--plan",       default="/home/claude/chart_plan.json",
                        help="Path to chart_plan.json from plan_charts.py")
    parser.add_argument("--data",       default="/home/claude/parsed_data.json",
                        help="Path to parsed_data.json from parse_data.py")
    parser.add_argument("--output-dir", default="/home/claude/charts",
                        help="Directory where chart PNGs will be written")
    parser.add_argument("--manifest",   default="/home/claude/charts_manifest.json",
                        help="Path to write charts_manifest.json")
    parser.add_argument("--timeout",    type=int, default=60,
                        help="Per-renderer timeout in seconds")
    args = parser.parse_args()

    # ── Load inputs ──────────────────────────────────────────────────────────
    print(f"[chart_runner] Loading plan:  {args.plan}")
    plan = load_json(args.plan)

    print(f"[chart_runner] Loading data:  {args.data}")
    data = load_json(args.data)  # used for validation only; passed by path to renderers

    charts       = plan.get("charts", [])
    plan_source  = plan.get("plan_source", "unknown")
    model_used   = plan.get("model_used",  "unknown")
    roles        = plan.get("roles", {})

    print(f"[chart_runner] Plan source: {plan_source} | Model: {model_used}")
    print(f"[chart_runner] Charts to render: {len(charts)}")

    # ── Locate charts renderer directory ─────────────────────────────────────
    runner_path = Path(__file__).resolve()
    charts_dir  = find_charts_dir(runner_path)

    if not charts_dir.exists():
        print(f"[chart_runner] ERROR: Renderer directory not found: {charts_dir}")
        print(f"[chart_runner] Expected: scripts/charts/render_*.py")
        sys.exit(1)

    # ── Prepare output directory ──────────────────────────────────────────────
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Validate column names against data profile ────────────────────────────
    available_columns = {col["name"] for col in data.get("column_profile", [])}

    def validate_spec_columns(spec: dict) -> list[str]:
        """Return list of missing column names referenced in a chart spec."""
        missing = []
        for key, value in spec.items():
            if key in ("top_n",) or value is None:
                continue
            if isinstance(value, str) and value not in available_columns:
                missing.append(value)
        return missing

    # ── Render each chart ─────────────────────────────────────────────────────
    generated = []
    skipped   = []

    for chart in charts:
        chart_id   = chart.get("id", f"chart_{len(generated)}")
        chart_type = chart.get("type", "")
        title      = chart.get("title", chart_id)
        spec       = chart.get("spec", {})
        rationale  = chart.get("rationale", "")

        print(f"\n[chart_runner] → [{chart_type:16s}] {title}")

        # Resolve renderer script with backward-compatible filename fallback.
        renderer_path, reason = resolve_renderer_path(chart_type, charts_dir)
        if reason:
            print(f"  skip: {reason}")
            skipped.append({"id": chart_id, "type": chart_type, "reason": reason})
            continue

        # Validate spec columns exist in data
        missing_cols = validate_spec_columns(spec)
        if missing_cols:
            reason = f"Spec references columns not in data: {missing_cols}"
            print(f"  skip: {reason}")
            skipped.append({"id": chart_id, "type": chart_type, "reason": reason})
            continue

        # Build output path
        output_path = str(output_dir / f"chart_{chart_id}.png")

        # Call renderer
        t0 = time.perf_counter()
        success, message = run_renderer(
            renderer_script=renderer_path,
            chart=chart,
            data_path=args.data,
            output_path=output_path,
            timeout=args.timeout,
        )
        duration_ms = round((time.perf_counter() - t0) * 1000)

        if success:
            print(f"  ✓ saved: {output_path}  ({duration_ms}ms)")
            generated.append({
                "id":          chart_id,
                "path":        output_path,
                "title":       title,
                "type":        chart_type,
                "spec":        spec,
                "rationale":   rationale,
                "plan_source": plan_source,
                "duration_ms": duration_ms,
            })
        else:
            print(f"  ✗ failed: {message}")
            skipped.append({
                "id":     chart_id,
                "type":   chart_type,
                "reason": f"Render error: {message}",
            })

    # ── Build manifest ────────────────────────────────────────────────────────
    manifest = {
        "generated": generated,
        "skipped":   skipped,
        "summary": {
            "total_planned": len(charts),
            "generated":     len(generated),
            "skipped":       len(skipped),
            "plan_source":   plan_source,
            "model_used":    model_used,
            "roles":         roles,
        },
    }

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n[chart_runner] ══════════════════════════════════════")
    print(f"[chart_runner] Done.")
    print(f"  Planned  : {len(charts)}")
    print(f"  Generated: {len(generated)}")
    print(f"  Skipped  : {len(skipped)}")
    print(f"  Manifest : {args.manifest}")

    if skipped:
        print(f"\n  Skipped details:")
        for s in skipped:
            print(f"    [{s['type']:16s}] {s['id']} — {s['reason']}")

    if len(generated) == 0:
        print("\n[chart_runner] WARNING: No charts were generated.")
        sys.exit(1)


if __name__ == "__main__":
    main()
