"""ml_ops_finance web app.

For now it only serves the Data Laboratory page. Any request to the root
("/") redirects to /data-lab. Future API routes (signals, backtests, health
of the daily pipeline) will be added here.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse

ROOT = Path(os.getenv("WEB_ROOT", Path(__file__).resolve().parent.parent))
DATA_LAB = ROOT / "data-lab.html"

app = FastAPI(title="ml_ops_finance", docs_url="/api/docs", redoc_url=None)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    # No route given -> default to the Data Laboratory (for now).
    return RedirectResponse(url="/data-lab", status_code=307)


@app.get("/data-lab", include_in_schema=False)
def data_lab() -> FileResponse:
    return FileResponse(DATA_LAB, media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "data_lab": DATA_LAB.exists()}
