"""Universe lists: NIFTY 50 and S&P 100.

CAVEAT — survivorship bias: these are CURRENT constituents. Backtests on them overstate
returns (names that were dropped/delisted are missing). Each pull is saved as a dated
snapshot so history accumulates from today; the real fix is historical constituents from
Bloomberg (INDX_MWEIGHT_HIST) — see the Data Lab.

Override: put a CSV at configs/universe/<name>.csv with a `ticker` column (Yahoo tickers,
e.g. RELIANCE.NS / AAPL, optional `name`, `sector`) and it is used instead of fetching.
"""
from __future__ import annotations

import logging
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd

from . import config
from .http import session

log = logging.getLogger(__name__)
NAMES = ("nifty50", "sp100")


def parse_nifty50(csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(StringIO(csv_text))
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame({
        "ticker": df["Symbol"].str.strip().str.upper() + ".NS",
        "name": df.get("Company Name"),
        "sector": df.get("Industry"),
    })
    return out.dropna(subset=["ticker"]).reset_index(drop=True)


def parse_sp100(html: str) -> pd.DataFrame:
    for t in pd.read_html(StringIO(html)):
        if "Symbol" in t.columns:
            out = pd.DataFrame({
                "ticker": t["Symbol"].astype(str).str.strip().str.replace(".", "-", regex=False),  # BRK.B -> BRK-B
                "name": t.get("Name"),
                "sector": t.get("Sector"),
            })
            return out.reset_index(drop=True)
    raise ValueError("No table with a 'Symbol' column found for S&P 100")


def _fetch(name: str) -> pd.DataFrame:
    s = session()
    if name == "nifty50":
        last = None
        for url in config.NIFTY50_URLS:
            try:
                r = s.get(url, timeout=30); r.raise_for_status()
                return parse_nifty50(r.text)
            except Exception as e:  # try next mirror
                last = e; log.warning("NIFTY 50 source failed (%s): %s", url, e)
        raise RuntimeError(f"All NIFTY 50 sources failed: {last}")
    r = s.get(config.SP100_URL, timeout=30); r.raise_for_status()
    return parse_sp100(r.text)


def get_universe(name: str, data_dir: Path = config.DATA_DIR, config_dir: Path = config.CONFIG_DIR) -> pd.DataFrame:
    """Return the universe (ticker, name, sector). Override file > live fetch > latest snapshot."""
    if name not in NAMES:
        raise ValueError(f"unknown universe {name!r}; choose from {NAMES}")
    override = config_dir / "universe" / f"{name}.csv"
    if override.exists():
        log.info("Using override universe %s", override)
        return pd.read_csv(override)
    snap_dir = data_dir / "universe"
    try:
        df = _fetch(name)
    except Exception as e:
        snaps = sorted(snap_dir.glob(f"{name}_*.csv"))
        if not snaps:
            raise RuntimeError(f"Could not fetch {name} and no snapshot exists ({e}). "
                               f"Create {override} with a 'ticker' column to proceed.") from e
        log.warning("Fetch failed (%s); using latest snapshot %s", e, snaps[-1].name)
        return pd.read_csv(snaps[-1])
    snap_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(snap_dir / f"{name}_{date.today().isoformat()}.csv", index=False)
    return df
