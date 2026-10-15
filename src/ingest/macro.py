"""Market & macro context -> one long Parquet: date, series, value, source.

Yahoo: India VIX, NIFTY/Bank NIFTY, S&P 500/100, VIX, USD/INR, gold, silver, oil, GOLDBEES, BTC, ETH
FRED : US 3M T-bill, US 10Y, VIX cross-check, India 10Y (monthly)
Not free/automatable yet (see Data Lab): RBI repo rate, FII/DII flows, India 10Y daily.
"""
from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path

import pandas as pd

from . import config
from .http import session
from .prices import download

log = logging.getLogger(__name__)
COLUMNS = ["date", "series", "value", "source"]


def parse_fred_csv(text: str, series: str) -> pd.DataFrame:
    df = pd.read_csv(StringIO(text))
    date_col, val_col = df.columns[0], df.columns[1]  # 'observation_date'/'DATE', '<id>'
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col]),
        "series": series,
        "value": pd.to_numeric(df[val_col], errors="coerce"),  # FRED uses '.' for missing
        "source": "fred",
    })
    return out.dropna(subset=["value"])


def fetch_fred(start: str) -> tuple[pd.DataFrame, list[str]]:
    s, frames, failed = session(), [], []
    for name, sid in config.FRED_SERIES.items():
        try:
            r = s.get("https://fred.stlouisfed.org/graph/fredgraph.csv",
                      params={"id": sid, "cosd": start}, timeout=30)
            r.raise_for_status()
            frames.append(parse_fred_csv(r.text, name))
        except Exception as e:
            log.warning("FRED %s (%s) failed: %s", name, sid, e); failed.append(name)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)), failed


def fetch_yahoo(start: str, end: str | None = None) -> tuple[pd.DataFrame, list[str]]:
    tickers = list(config.YAHOO_MACRO.values())
    long, missing = download(tickers, start, end)
    inv = {v: k for k, v in config.YAHOO_MACRO.items()}
    if long.empty:
        return pd.DataFrame(columns=COLUMNS), [inv[t] for t in missing]
    out = pd.DataFrame({"date": long["date"], "series": long["ticker"].map(inv),
                        "value": long["adj_close"].fillna(long["close"]), "source": "yahoo"})
    return out.dropna(subset=["value"]), [inv[t] for t in missing]


def update(start: str, data_dir: Path, end: str | None = None) -> tuple[pd.DataFrame, list[str], Path]:
    from .io import write_parquet

    y, y_missing = fetch_yahoo(start, end)
    f, f_failed = fetch_fred(start)
    parts = [d for d in (y, f) if not d.empty]
    out = (pd.concat(parts, ignore_index=True).drop_duplicates(["series", "date"], keep="last")
           .sort_values(["series", "date"]).reset_index(drop=True)) if parts else pd.DataFrame(columns=COLUMNS)
    path = data_dir / "macro" / "macro_daily.parquet"
    if not out.empty:
        write_parquet(out, path)
    return out, y_missing + f_failed, path
