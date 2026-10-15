"""Daily OHLCV from Yahoo Finance (yfinance) -> long Parquet.

Columns: date, ticker, open, high, low, close, adj_close, volume, dividends, stock_splits
  close     = Bloomberg PX_LAST equivalent (split-adjusted by Yahoo, NOT dividend-adjusted)
  adj_close = split + dividend adjusted (use for returns)
  volume    = PX_VOLUME

Incremental updates re-fetch the last 7 days and merge. Yahoo RESTATES adj_close for the whole
history at every dividend, so run with --full now and then (e.g. monthly) to refresh history.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

FIELDS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Adj Close": "adj_close",
          "Volume": "volume", "Dividends": "dividends", "Stock Splits": "stock_splits"}
COLUMNS = ["date", "ticker", *FIELDS.values()]
_PRICE_COLS = ["open", "high", "low", "close", "adj_close", "volume"]


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def normalise(raw: pd.DataFrame | None, tickers: list[str]) -> pd.DataFrame:
    """yfinance wide frame (either column orientation, or single ticker) -> long frame."""
    if raw is None or raw.empty:
        return _empty()
    if not isinstance(raw.columns, pd.MultiIndex):
        if len(tickers) != 1:
            raise ValueError("flat columns only expected for a single ticker")
        raw = pd.concat({tickers[0]: raw}, axis=1)
    elif set(raw.columns.get_level_values(0)) & set(FIELDS):  # fields on level 0 -> swap
        raw = raw.swaplevel(axis=1)

    frames = []
    for t in raw.columns.get_level_values(0).unique():
        sub = raw[t].rename(columns=FIELDS)
        for c in COLUMNS[2:]:
            if c not in sub.columns:
                sub[c] = float("nan")
        sub = sub[COLUMNS[2:]].dropna(how="all", subset=_PRICE_COLS)
        if sub.empty:
            continue
        idx = pd.to_datetime(sub.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        sub = sub.copy()
        sub.index = idx.normalize()
        sub.index.name = "date"
        sub = sub.reset_index()
        sub.insert(1, "ticker", t)
        frames.append(sub)
    if not frames:
        return _empty()
    out = pd.concat(frames, ignore_index=True)
    out[["dividends", "stock_splits"]] = out[["dividends", "stock_splits"]].fillna(0.0)
    return out[COLUMNS].astype({c: "float64" for c in COLUMNS[2:]})


def download(tickers: list[str], start: str, end: str | None = None, batch: int = 40
             ) -> tuple[pd.DataFrame, list[str]]:
    """Download in batches with retries. Returns (long frame, tickers that returned nothing)."""
    import yfinance as yf  # imported lazily so tests/offline use don't need network libs

    frames, missing = [], []
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        raw = None
        for attempt in range(3):
            try:
                raw = yf.download(chunk, start=start, end=end, auto_adjust=False, actions=True,
                                  group_by="ticker", progress=False, threads=True)
                if raw is not None and not raw.empty:
                    break
            except Exception as e:
                log.warning("yfinance batch %d attempt %d failed: %s", i // batch, attempt + 1, e)
            time.sleep(2 * (attempt + 1))
        long = normalise(raw, chunk)
        got = set(long["ticker"].unique()) if not long.empty else set()
        missing += [t for t in chunk if t not in got]
        frames.append(long)
        log.info("prices batch %d/%d: %d/%d tickers", i // batch + 1, -(-len(tickers) // batch), len(got), len(chunk))
    out = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else _empty()
    return out, missing


def merge(existing: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    combined = new if existing is None or existing.empty else pd.concat([existing, new], ignore_index=True)
    return (combined.drop_duplicates(["ticker", "date"], keep="last")
            .sort_values(["ticker", "date"]).reset_index(drop=True))


def update(name: str, tickers: list[str], start: str, data_dir: Path, end: str | None = None,
           full: bool = False) -> tuple[pd.DataFrame, list[str], Path]:
    from .io import write_parquet

    path = data_dir / "prices" / f"{name}.parquet"
    existing = None
    start_eff = start
    if path.exists() and not full:
        existing = pd.read_parquet(path)
        if not existing.empty:
            start_eff = (existing["date"].max() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
            log.info("%s: incremental from %s", name, start_eff)
    new, missing = download(tickers, start_eff, end)
    combined = merge(existing, new)
    if not combined.empty:
        write_parquet(combined, path)
    return combined, missing, path
