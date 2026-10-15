"""Offline tests: no network. Fixtures mimic what yfinance / FRED / EDGAR / NSE / Wikipedia return."""
import json
import numpy as np
import pandas as pd
import pytest

from src.ingest import fundamentals, macro, prices, universe, validate
from src.ingest.io import update_manifest

IDX = pd.bdate_range("2024-01-01", periods=10, tz="Asia/Kolkata")


def _frame(base=100.0):
    return pd.DataFrame({
        "Open": base, "High": base + 2, "Low": base - 2, "Close": base + 1, "Adj Close": base + 0.5,
        "Volume": 1000.0, "Dividends": 0.0, "Stock Splits": 0.0}, index=pd.Index(IDX, name="Date"))


def _wide(orient):
    wide = pd.concat({"AAA.NS": _frame(100), "BBB.NS": _frame(200)}, axis=1)  # (ticker, field)
    return wide if orient == "ticker_first" else wide.swaplevel(axis=1)


@pytest.mark.parametrize("orient", ["ticker_first", "field_first"])
def test_normalise_both_orientations(orient):
    out = prices.normalise(_wide(orient), ["AAA.NS", "BBB.NS"])
    assert list(out.columns) == prices.COLUMNS
    assert len(out) == 20 and set(out.ticker) == {"AAA.NS", "BBB.NS"}
    assert out["date"].dt.tz is None                      # tz stripped, normalised to midnight
    assert (out["date"] == out["date"].dt.normalize()).all()
    assert out.loc[out.ticker == "BBB.NS", "close"].iloc[0] == 201.0


def test_normalise_single_ticker_flat_columns():
    out = prices.normalise(_frame(50), ["ZZZ"])
    assert len(out) == 10 and (out.ticker == "ZZZ").all()


def test_normalise_empty_and_all_nan_ticker():
    assert prices.normalise(pd.DataFrame(), ["X"]).empty
    wide = _wide("ticker_first")
    wide["BBB.NS"] = np.nan                                 # ticker with no data -> dropped
    out = prices.normalise(wide, ["AAA.NS", "BBB.NS"])
    assert set(out.ticker) == {"AAA.NS"}


def test_merge_dedupes_keep_latest():
    a = prices.normalise(_wide("ticker_first"), ["AAA.NS", "BBB.NS"])
    b = a[a.date >= a.date.max() - pd.Timedelta(days=3)].copy()
    b["adj_close"] = 999.0                                  # restated values should win
    m = prices.merge(a, b)
    assert len(m) == len(a)
    assert (m[m.date >= b.date.min()]["adj_close"] == 999.0).all()


def test_update_incremental_start(tmp_path, monkeypatch):
    calls = []

    def fake_download(tickers, start, end=None, batch=40):
        calls.append(start)
        return prices.normalise(_wide("ticker_first"), ["AAA.NS", "BBB.NS"]), []
    monkeypatch.setattr(prices, "download", fake_download)
    prices.update("t", ["AAA.NS", "BBB.NS"], "2010-01-01", tmp_path)
    prices.update("t", ["AAA.NS", "BBB.NS"], "2010-01-01", tmp_path)
    assert calls[0] == "2010-01-01" and calls[1] == "2024-01-05"      # last date (Jan 12) - 7d
    prices.update("t", ["AAA.NS", "BBB.NS"], "2010-01-01", tmp_path, full=True)
    assert calls[2] == "2010-01-01"
    assert len(pd.read_parquet(tmp_path / "prices" / "t.parquet")) == 20


def test_validate_flags_problems():
    df = prices.normalise(_wide("ticker_first"), ["AAA.NS", "BBB.NS"])
    assert validate.validate_prices(df)["issues"] == []
    bad = df.copy()
    bad.loc[3, "adj_close"] = bad.loc[2, "adj_close"] * 3   # +200% jump (unadjusted split?)
    bad.loc[5, "close"] = -1
    bad = pd.concat([bad, bad.iloc[[0]]])                   # duplicate
    text = " | ".join(validate.validate_prices(bad)["issues"])
    assert "duplicate" in text and "non-positive" in text and "daily moves" in text


def test_parse_fred_csv_handles_dots_and_headers():
    txt = "observation_date,DGS10\n2024-01-02,3.95\n2024-01-03,.\n2024-01-04,4.01\n"
    out = macro.parse_fred_csv(txt, "us_10y")
    assert list(out.value) == [3.95, 4.01] and (out.series == "us_10y").all() and (out.source == "fred").all()
    assert len(macro.parse_fred_csv(txt.replace("observation_date", "DATE"), "x")) == 2


def test_parse_nifty50():
    csv = ("Company Name,Industry,Symbol,Series,ISIN Code\n"
           "Reliance Industries Ltd.,Oil Gas & Consumable Fuels,RELIANCE,EQ,INE002A01018\n"
           "HDFC Bank Ltd.,Financial Services,HDFCBANK,EQ,INE040A01034\n")
    out = universe.parse_nifty50(csv)
    assert list(out.ticker) == ["RELIANCE.NS", "HDFCBANK.NS"]


def test_parse_sp100_converts_class_shares():
    html = ("<table><tr><th>Symbol</th><th>Name</th><th>Sector</th></tr>"
            "<tr><td>AAPL</td><td>Apple</td><td>Tech</td></tr>"
            "<tr><td>BRK.B</td><td>Berkshire</td><td>Financials</td></tr></table>")
    assert list(universe.parse_sp100(html).ticker) == ["AAPL", "BRK-B"]


def test_universe_override_and_snapshot_fallback(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"; (cfg / "universe").mkdir(parents=True)
    (cfg / "universe" / "nifty50.csv").write_text("ticker\nTCS.NS\n")
    assert list(universe.get_universe("nifty50", tmp_path, cfg).ticker) == ["TCS.NS"]

    monkeypatch.setattr(universe, "_fetch", lambda n: pd.DataFrame({"ticker": ["AAPL"], "name": ["Apple"], "sector": ["T"]}))
    assert list(universe.get_universe("sp100", tmp_path, tmp_path / "none").ticker) == ["AAPL"]
    assert list((tmp_path / "universe").glob("sp100_*.csv"))          # dated snapshot saved

    def boom(n): raise RuntimeError("offline")
    monkeypatch.setattr(universe, "_fetch", boom)
    assert list(universe.get_universe("sp100", tmp_path, tmp_path / "none").ticker) == ["AAPL"]  # snapshot used
    with pytest.raises(RuntimeError, match="no snapshot"):
        universe.get_universe("nifty50", tmp_path / "empty", tmp_path / "none")


FACTS = {"facts": {
    "us-gaap": {
        "Revenues": {"units": {"USD": [
            {"start": "2023-01-01", "end": "2023-03-31", "val": 100, "accn": "a1", "fy": 2023, "fp": "Q1", "form": "10-Q", "filed": "2023-05-01"},
            {"start": "2023-01-01", "end": "2023-03-31", "val": 101, "accn": "a2", "fy": 2023, "fp": "Q1", "form": "10-Q/A", "filed": "2023-06-01"},
            {"start": "2023-01-01", "end": "2023-03-31", "val": 100, "accn": "a1", "fy": 2023, "fp": "Q1", "form": "10-Q", "filed": "2023-05-01"},  # dup
            {"start": "2023-01-01", "end": "2023-03-31", "val": 5, "accn": "x", "fy": 2023, "fp": "Q1", "form": "8-K", "filed": "2023-05-02"},    # ignored form
        ]}},
        "Assets": {"units": {"USD": [{"end": "2023-03-31", "val": 900, "accn": "a1", "fy": 2023, "fp": "Q1", "form": "10-Q", "filed": "2023-05-01"}]}},
    },
    "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2023-04-20", "val": 15e9, "accn": "a1", "fy": 2023, "fp": "Q1", "form": "10-Q", "filed": "2023-05-01"}]}}},
}}


def test_extract_facts_keeps_restatements_drops_noise():
    df = fundamentals.extract_facts("AAPL", "0000320193", FACTS)
    rev = df[df.field == "revenue"]
    assert sorted(rev.value) == [100, 101]                  # original + 10-Q/A restatement, dup removed, 8-K dropped
    assert set(df.field) == {"revenue", "total_assets", "shares_outstanding"}
    assert df["filed"].dt.tz is None and df.loc[df.field == "total_assets", "period_start"].isna().all()


def test_ticker_to_cik_pads():
    m = fundamentals.ticker_to_cik({"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}})
    assert m == {"AAPL": "0000320193"}


def test_fundamentals_requires_user_agent(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        fundamentals.update(["AAPL"], tmp_path)


def test_manifest_roundtrip(tmp_path):
    update_manifest(tmp_path, "a", {"rows": 1}); update_manifest(tmp_path, "b", {"rows": 2})
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert set(m) == {"a", "b"} and "fetched_at" in m["a"]
