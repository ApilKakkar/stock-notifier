"""ml_ops_finance web app.

Pages
  /            -> Stock Notifier landing page (index.html): two separate flows below
  /data-lab    -> Data Laboratory: viewer for the data we actually collected (data-lab.html)
  /info-box    -> Information Box: the project notebook of ideas, fields, sources, decisions (info-box.html)

Read-only data API (used by the Data Lab page; reads data/raw/*.parquet + manifest.json)
  /api/data/manifest
  /api/data/universe/{nifty50|sp100}
  /api/data/prices/{nifty50|sp100}            -> per-ticker summary (no ?tickers)
  /api/data/prices/{market}?tickers=A,B&start=&end=
  /api/data/macro                              -> per-series summary (no ?series)
  /api/data/macro?series=a,b&start=&end=

Base path (reverse proxy): set BASE_PATH=/stock-notifier to serve everything above under
that prefix (/stock-notifier/, /stock-notifier/data-lab, /stock-notifier/api/data/...). The bare
prefix redirects to the trailing-slash URL; /healthz is always also served at the root. The HTML
pages use relative URLs only, so they work at / and under any prefix (stripped or passed through).

The API never writes to the data folder. pandas/pyarrow are imported lazily so the
pages still load (and say "no data yet") when the data stack is not installed.
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

ROOT = Path(os.getenv("WEB_ROOT", Path(__file__).resolve().parent.parent))
INDEX = ROOT / "index.html"
DATA_LAB = ROOT / "data-lab.html"
INFO_BOX = ROOT / "info-box.html"
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data" / "raw"))

MARKETS = {"nifty50", "sp100"}
MAX_POINTS = 1500      # per line; long histories are thinned for the browser
MAX_TICKERS = 4        # compare at most 4 lines at once
TAIL_ROWS = 20
NO_CACHE = {"Cache-Control": "no-cache"}

router = APIRouter()   # all pages + API; mounted under BASE_PATH by create_app()


# ----------------------------------------------------------------- pages
@router.get("/", include_in_schema=False)
def root() -> FileResponse:
    # Landing page: links to the Data Laboratory and the Information Box (separate flows).
    return FileResponse(INDEX, media_type="text/html", headers=NO_CACHE)


@router.get("/data-lab", include_in_schema=False)
def data_lab() -> FileResponse:
    return FileResponse(DATA_LAB, media_type="text/html", headers=NO_CACHE)


@router.get("/info-box", include_in_schema=False)
def info_box() -> FileResponse:
    return FileResponse(INFO_BOX, media_type="text/html", headers=NO_CACHE)


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "index": INDEX.exists(), "data_lab": DATA_LAB.exists(), "info_box": INFO_BOX.exists(),
            "data_dir": DATA_DIR.exists()}


# ----------------------------------------------------------------- helpers
def _pd():
    try:
        import pandas as pd  # noqa: WPS433 (lazy on purpose)
        return pd
    except ImportError as e:  # pragma: no cover
        raise HTTPException(503, "pandas/pyarrow not installed: pip install -r requirements.txt") from e


@lru_cache(maxsize=16)
def _read(path: str, mtime: float):
    """Parquet read cached by (path, mtime): a re-run of the ingest invalidates it."""
    return _pd().read_parquet(path)


def _load(rel: str):
    p = DATA_DIR / rel
    if not p.exists():
        raise HTTPException(404, f"{rel} not found in {DATA_DIR} — run: python -m src.ingest.run all")
    return _read(str(p), p.stat().st_mtime)


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 6)
    if hasattr(v, "item"):  # numpy scalar
        return _clean(v.item())
    return v


def _records(df, cols):
    out = df[cols].copy()
    if "date" in out:
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return [{c: _clean(r[i]) for i, c in enumerate(cols)} for r in out.itertuples(index=False, name=None)]


def _thin(df, n: Optional[int] = None):
    """Keep every k-th row so a line has <= n points; always keep the last row."""
    n = n or MAX_POINTS
    if len(df) <= n:
        return df
    step = math.ceil(len(df) / n)
    idx = list(range(0, len(df), step))
    if idx[-1] != len(df) - 1:
        idx.append(len(df) - 1)
    return df.iloc[idx]


def _window(df, start: Optional[str], end: Optional[str]):
    pd = _pd()
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df


def _split(s: Optional[str]) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _summary(df, key: str) -> list[dict]:
    g = df.groupby(key)["date"].agg(["min", "max", "count"]).reset_index()
    return [{key: r[key], "from": r["min"].strftime("%Y-%m-%d"), "to": r["max"].strftime("%Y-%m-%d"),
             "rows": int(r["count"])} for _, r in g.iterrows()]


def _stats(d, col: str) -> dict:
    """Window stats on the full (unthinned) series: return, CAGR, annual vol, max drawdown."""
    s = d[col].astype(float).dropna()
    if len(s) < 2 or s.iloc[0] <= 0:
        return {}
    dates = d.loc[s.index, "date"]
    years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
    r = s.pct_change().dropna()
    return {"basis": col, "first": _clean(s.iloc[0]), "last": _clean(s.iloc[-1]),
            "total_return": _clean(s.iloc[-1] / s.iloc[0] - 1),
            "cagr": _clean((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1) if years >= 0.5 else None,
            "ann_vol": _clean(r.std() * math.sqrt(252)) if len(r) > 20 else None,
            "max_drawdown": _clean((s / s.cummax() - 1).min())}


def _market(market: str) -> str:
    if market not in MARKETS:
        raise HTTPException(404, f"unknown market {market!r}; use one of {sorted(MARKETS)}")
    return market


# ----------------------------------------------------------------- data API
@router.get("/api/data/manifest", tags=["data"])
def manifest() -> dict:
    """What has been pulled: manifest.json plus the data files actually on disk."""
    m = DATA_DIR / "manifest.json"
    files = [{"path": str(p.relative_to(DATA_DIR)), "bytes": p.stat().st_size}
             for p in sorted(DATA_DIR.rglob("*")) if p.is_file() and p.name != "manifest.json"
             ] if DATA_DIR.exists() else []
    return {"data_dir": str(DATA_DIR), "exists": DATA_DIR.exists(), "files": files,
            "manifest": json.loads(m.read_text()) if m.exists() else {}}


@router.get("/api/data/universe/{market}", tags=["data"])
def universe(market: str) -> dict:
    """Latest constituent snapshot, flagged with whether price data exists for each ticker."""
    pd = _pd()
    snaps = sorted((DATA_DIR / "universe").glob(f"{_market(market)}_*.csv"))
    if not snaps:
        raise HTTPException(404, f"no {market} universe snapshot — run: python -m src.ingest.run universe")
    u = pd.read_csv(snaps[-1])
    have = {}
    if (DATA_DIR / "prices" / f"{market}.parquet").exists():
        have = {r["ticker"]: r for r in _summary(_load(f"prices/{market}.parquet"), "ticker")}
    cols = [c for c in ("ticker", "name", "sector") if c in u.columns]
    rows = []
    for r in u[cols].fillna("").to_dict("records"):
        s = have.get(r["ticker"])
        rows.append({**r, "has_prices": bool(s), "from": s and s["from"], "to": s and s["to"],
                     "rows": s and s["rows"]})
    return {"market": market, "snapshot": snaps[-1].name, "count": len(rows),
            "with_prices": sum(r["has_prices"] for r in rows), "rows": rows}


@router.get("/api/data/prices/{market}", tags=["data"])
def prices(market: str,
           tickers: Optional[str] = Query(None, description="comma-separated, max 4; omit for a summary"),
           start: Optional[str] = None, end: Optional[str] = None) -> dict:
    df = _load(f"prices/{_market(market)}.parquet")
    want = _split(tickers)
    if not want:
        return {"market": market, "tickers": _summary(df, "ticker")}
    if len(want) > MAX_TICKERS:
        raise HTTPException(400, f"at most {MAX_TICKERS} tickers at once")
    cols = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    out = {}
    for t in want:
        d = _window(df[df["ticker"] == t].sort_values("date"), start, end)
        if d.empty:
            out[t] = {"rows": 0, "points": [], "tail": []}
            continue
        basis = "adj_close" if d["adj_close"].notna().any() else "close"
        out[t] = {"rows": int(len(d)), "from": d["date"].min().strftime("%Y-%m-%d"),
                  "to": d["date"].max().strftime("%Y-%m-%d"), "stats": _stats(d, basis),
                  "points": _records(_thin(d), cols),
                  "tail": _records(d.tail(TAIL_ROWS).iloc[::-1], cols)}
    return {"market": market, "series": out}


@router.get("/api/data/macro", tags=["data"])
def macro(series: Optional[str] = Query(None, description="comma-separated, max 4; omit for a summary"),
          start: Optional[str] = None, end: Optional[str] = None) -> dict:
    df = _load("macro/macro_daily.parquet")
    want = _split(series)
    if not want:
        s = _summary(df, "series")
        src = df.groupby("series")["source"].first().to_dict() if "source" in df else {}
        for r in s:
            r["source"] = src.get(r["series"])
        return {"series": s}
    if len(want) > MAX_TICKERS:
        raise HTTPException(400, f"at most {MAX_TICKERS} series at once")
    out = {}
    for name in want:
        d = _window(df[df["series"] == name].sort_values("date"), start, end)
        v = d["value"].astype(float)
        out[name] = {"rows": int(len(d)),
                     "stats": {"last": _clean(v.iloc[-1]) if len(v) else None,
                               "min": _clean(v.min()) if len(v) else None,
                               "max": _clean(v.max()) if len(v) else None,
                               "change": _clean(v.iloc[-1] - v.iloc[0]) if len(v) > 1 else None,
                               "pct_change": _clean(v.iloc[-1] / v.iloc[0] - 1) if len(v) > 1 and v.iloc[0] else None},
                     "from": d["date"].min().strftime("%Y-%m-%d") if len(d) else None,
                     "to": d["date"].max().strftime("%Y-%m-%d") if len(d) else None,
                     "points": _records(_thin(d), ["date", "value"]),
                     "tail": _records(d.tail(TAIL_ROWS).iloc[::-1], ["date", "value"])}
    return {"series": out}


# ----------------------------------------------------------------- app factory
def normalise_base_path(base: Optional[str]) -> str:
    """'' or '/' -> '' ; 'stock-notifier/' -> '/stock-notifier'."""
    base = (base or "").strip().strip("/")
    return f"/{base}" if base else ""


def create_app(base_path: Optional[str] = None) -> FastAPI:
    base = normalise_base_path(base_path)
    api = FastAPI(title="ml_ops_finance", docs_url=f"{base}/api/docs", openapi_url=f"{base}/openapi.json",
                  redoc_url=None)
    if base:
        @api.get(base, include_in_schema=False)
        def _bare_prefix() -> RedirectResponse:
            # /stock-notifier -> /stock-notifier/ so the pages' relative links resolve under the prefix
            return RedirectResponse(url=f"{base}/", status_code=307)

        api.add_api_route("/healthz", healthz, methods=["GET"])   # root health check (Docker HEALTHCHECK)
    api.include_router(router, prefix=base)
    api.state.base_path = base
    return api


BASE_PATH = normalise_base_path(os.getenv("BASE_PATH"))
app = create_app(BASE_PATH)
