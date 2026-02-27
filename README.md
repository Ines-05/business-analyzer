# PME Startup Business Analyzer

Web app for SME/PME clients to upload sales data (`.csv`, `.xlsx`, `.xls`) and receive:

- KPI dashboard
- chart visuals
- AI-style business recommendations
- explanation of insights behind each visual
- downloadable chart images
- LLM recommendations through Vercel AI Gateway (default model: `openai/gpt-5.2`)

React interface includes:
- Upload page with multi-file batch processing
- Dashboard page to reopen previously generated analyses

## Architecture

- Backend API: FastAPI (`app/main.py`) on `http://127.0.0.1:8000`
- Frontend: React + Vite (`frontend/`) on `http://127.0.0.1:5173`
- Frontend uses Vite proxy to call backend `/api/*`

The analytics engine reuses the local `business-analyzer` skill scripts in:
`E:/Analysis/.codex/skills/business-analyzer/scripts`

## Run

1. Backend setup (Python/uv):

```powershell
uv venv .venv --python 3.11
uv sync
```

2. Frontend setup (Node):

```powershell
cd frontend
npm install
```

3. Configure backend environment (`.env` at project root):

```env
AI_GATEWAY_API_KEY=your_vercel_ai_gateway_key
# Optional override:
# RECOMMENDATION_MODEL=openai/gpt-5.2
```

4. Start backend API (from project root):

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

5. Start frontend (from `frontend/`):

```powershell
npm run dev
```

6. Open:

`http://127.0.0.1:5173`

## API

- `POST /api/analyze` (form-data)
  - `file`: uploaded CSV/Excel file (required)
  - `company_name`: optional text
- `GET /api/analyses?limit=20`
  - Returns recent saved analyses for dashboard history
- `GET /api/analyses/{analysis_id}/result`
  - Returns full saved dashboard payload for a previous run
- `GET /api/analyses/{analysis_id}/charts/{chart_id}`
  - `chart_id`: `trend`, `products`, `share`
  - add `?download=true` to force download

## Notes

- Uploads and generated outputs are stored in `runtime/analyses/<analysis_id>/`.
- Excel parsing uses `openpyxl`.
- Recommendation generation uses Vercel AI Gateway at `https://ai-gateway.vercel.sh/v1`.
- Recommendations are LLM-only. If generation fails, the API returns `recommendations_source: "llm_error"` with `recommendations_warning` and `recommendations_debug` for troubleshooting.
- PDF export is not enabled in this UI yet, but the underlying skill scripts support it.
- Backend dependencies are managed with `uv` via `pyproject.toml` and `uv.lock`.
