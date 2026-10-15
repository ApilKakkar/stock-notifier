"""Offline tests for the web app: pages (landing, Data Lab, Info Box) and the read-only /api/data/* endpoints."""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "raw"
    (d / "prices").mkdir(parents=True); (d / "macro").mkdir(); (d / "universe").mkdir()
    dates = pd.bdate_range("2015-01-01", "2024-12-31")
    rows = []
    for t, base in [("AAA.NS", 100.0), ("BBB.NS", 50.0)]:
        px = base * np.cumprod(1 + np.full(len(dates), 0.0003))
        rows.append(pd.DataFrame({"date": dates, "ticker": t, "open": px, "high": px * 1.01, "low": px * .99,
                                  "close": px, "adj_close": px, "volume": 1000.0, "dividends": 0.0, "stock_splits": 0.0}))
    pd.concat(rows).to_parquet(d / "prices" / "nifty50.parquet", index=False)
    pd.DataFrame({"date": dates, "series": "india_vix", "value": 15.0, "source": "yahoo"}).to_parquet(
        d / "macro" / "macro_daily.parquet", index=False)
    (d / "universe" / "nifty50_2026-10-15.csv").write_text(
        "ticker,name,sector\nAAA.NS,Aaa Ltd,Energy\nBBB.NS,Bbb Ltd,IT\nCCC.NS,Ccc Ltd,IT\n")
    (d / "manifest.json").write_text(json.dumps({"prices/nifty50": {"source": "yahoo/yfinance",
                                                                    "validation": {"rows": len(dates) * 2, "issues": []}}}))
    monkeypatch.setattr(main, "DATA_DIR", d)
    main._read.cache_clear()
    return d


client = TestClient(main.app)


def test_pages_and_redirect():
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200 and "<title>Stock Notifier</title>" in r.text
    assert 'href="data-lab"' in r.text and 'href="info-box"' in r.text
    assert "<title>Data Laboratory</title>" in client.get("/data-lab").text
    info, lab = client.get("/info-box").text, client.get("/data-lab").text
    assert "<title>Information Box</title>" in info
    assert 'href="data-lab"' not in info and 'href="info-box"' not in lab       # separate flows
    assert 'href="./"' in info and 'href="./"' in lab                         # both link home
    h = client.get("/healthz").json()
    assert h["status"] == "ok" and h["index"] and h["data_lab"] and h["info_box"]


def test_pages_use_relative_urls_only():
    """Absolute links/fetches break when served under BASE_PATH behind a reverse proxy."""
    import re
    for page in (main.INDEX, main.DATA_LAB, main.INFO_BOX):
        html = page.read_text()
        assert 'href="/"' not in html and 'href="/data-lab"' not in html and 'href="/info-box"' not in html, page
        assert not re.search(r"""(fetch|api)\(\s*['"`]/""", html), page            # no fetch('/...') or api('/...')


@pytest.mark.parametrize("base", ["/stock-notifier", "stock-notifier/", "/stock-notifier/"])
def test_base_path_serves_everything_under_prefix(data_dir, base):
    c = TestClient(main.create_app(base))
    r = c.get("/stock-notifier", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/stock-notifier/"
    assert "<title>Stock Notifier</title>" in c.get("/stock-notifier/").text
    assert "<title>Data Laboratory</title>" in c.get("/stock-notifier/data-lab").text
    assert "<title>Information Box</title>" in c.get("/stock-notifier/info-box").text
    assert c.get("/stock-notifier/api/data/manifest").json()["exists"]
    assert c.get("/stock-notifier/api/data/prices/nifty50").status_code == 200
    assert c.get("/stock-notifier/api/docs").status_code == 200
    assert c.get("/healthz").json()["status"] == "ok"                     # root health check for Docker
    assert c.get("/stock-notifier/healthz").json()["status"] == "ok"
    assert c.get("/data-lab").status_code == 404 and c.get("/api/data/manifest").status_code == 404


@pytest.mark.parametrize("raw,norm", [(None, ""), ("", ""), ("/", ""), ("  /a/b/ ", "/a/b"), ("x", "/x")])
def test_normalise_base_path(raw, norm):
    assert main.normalise_base_path(raw) == norm


def test_manifest(data_dir):
    m = client.get("/api/data/manifest").json()
    assert m["exists"] and "prices/nifty50" in m["manifest"]
    assert {f["path"] for f in m["files"]} >= {"prices/nifty50.parquet", "macro/macro_daily.parquet"}


def test_manifest_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "nothing")
    m = client.get("/api/data/manifest").json()
    assert m == {"data_dir": str(tmp_path / "nothing"), "exists": False, "files": [], "manifest": {}}


def test_prices_summary_and_series(data_dir):
    s = client.get("/api/data/prices/nifty50").json()
    assert [t["ticker"] for t in s["tickers"]] == ["AAA.NS", "BBB.NS"]
    r = client.get("/api/data/prices/nifty50?tickers=AAA.NS,BBB.NS&start=2020-01-01").json()["series"]
    a = r["AAA.NS"]
    assert a["from"] >= "2020-01-01" and a["to"] == "2024-12-31"
    assert len(a["points"]) <= main.MAX_POINTS + 1 and a["points"][-1]["date"] == "2024-12-31"
    assert len(a["tail"]) == main.TAIL_ROWS and a["tail"][0]["date"] == "2024-12-31"   # newest first
    st = a["stats"]
    assert st["total_return"] > 0 and st["max_drawdown"] == 0 and st["cagr"] > 0


def test_prices_thinning_keeps_last(data_dir, monkeypatch):
    monkeypatch.setattr(main, "MAX_POINTS", 100)
    a = client.get("/api/data/prices/nifty50?tickers=AAA.NS").json()["series"]["AAA.NS"]
    assert len(a["points"]) <= 101 and a["points"][-1]["date"] == "2024-12-31" and a["rows"] > 2000


def test_prices_errors(data_dir):
    assert client.get("/api/data/prices/nasdaq").status_code == 404
    assert client.get("/api/data/prices/sp100").status_code == 404            # not pulled
    assert client.get("/api/data/prices/nifty50?tickers=A,B,C,D,E").status_code == 400
    assert client.get("/api/data/prices/nifty50?tickers=ZZZ").json()["series"]["ZZZ"]["rows"] == 0


def test_macro(data_dir):
    assert client.get("/api/data/macro").json()["series"][0] == {
        "series": "india_vix", "from": "2015-01-01", "to": "2024-12-31", "rows": 2609, "source": "yahoo"}
    v = client.get("/api/data/macro?series=india_vix&start=2024-01-01").json()["series"]["india_vix"]
    assert v["stats"]["last"] == 15.0 and v["stats"]["change"] == 0 and v["from"] == "2024-01-01"


def test_universe_flags_pulled(data_dir):
    u = client.get("/api/data/universe/nifty50").json()
    assert u["count"] == 3 and u["with_prices"] == 2
    ccc = next(r for r in u["rows"] if r["ticker"] == "CCC.NS")
    assert ccc["has_prices"] is False and ccc["from"] is None
