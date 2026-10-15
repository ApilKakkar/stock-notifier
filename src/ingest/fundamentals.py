"""US fundamentals from SEC EDGAR (XBRL company facts) -> long Parquet, point-in-time.

SEC requires a User-Agent that identifies you. Set it yourself, e.g.
    export SEC_USER_AGENT="Your Name your.email@example.com"
(nothing is sent to SEC unless you set it).

Rows keep EVERY filed version (restatements included) with its `filed` date, so a backtest can
use only what was public on each date: join on `filed`, never on `period_end`.
Notes for feature building later:
  * flow items (revenue, income, EPS) have period_start; Q4 is not filed separately (derive FY - 9M YTD)
  * balance-sheet items (assets, equity, debt) are instants (no period_start)
  * ratios (P/E, P/B, ROE, D/E, EV/EBITDA) are computed from these + prices, not stored here
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pandas as pd

from . import config
from .http import session

log = logging.getLogger(__name__)
COLUMNS = ["ticker", "cik", "field", "concept", "unit", "period_start", "period_end",
           "fy", "fp", "form", "filed", "value", "accn"]


def ticker_to_cik(tickers_json: dict) -> dict[str, str]:
    return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in tickers_json.values()}


def extract_facts(ticker: str, cik: str, facts_json: dict) -> pd.DataFrame:
    rows = []
    for field, candidates in config.EDGAR_FIELDS.items():
        for taxonomy, concept in candidates:
            node = facts_json.get("facts", {}).get(taxonomy, {}).get(concept)
            if not node:
                continue
            for unit, items in node.get("units", {}).items():
                for it in items:
                    if it.get("form") not in config.EDGAR_FORMS:
                        continue
                    rows.append({"ticker": ticker, "cik": cik, "field": field, "concept": concept,
                                 "unit": unit, "period_start": it.get("start"), "period_end": it.get("end"),
                                 "fy": it.get("fy"), "fp": it.get("fp"), "form": it.get("form"),
                                 "filed": it.get("filed"), "value": it.get("val"), "accn": it.get("accn")})
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows, columns=COLUMNS)
    for c in ("period_start", "period_end", "filed"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df.drop_duplicates(["ticker", "field", "concept", "unit", "period_start", "period_end", "filed", "accn"])


def update(tickers: list[str], data_dir: Path, user_agent: str | None = None,
           pause: float = 0.15) -> tuple[pd.DataFrame, list[str], Path]:
    from .io import write_parquet

    user_agent = user_agent or os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise RuntimeError('Set SEC_USER_AGENT first, e.g. export SEC_USER_AGENT="Your Name you@example.com"')
    s = session(user_agent)
    r = s.get("https://www.sec.gov/files/company_tickers.json", timeout=30); r.raise_for_status()
    cik_map = ticker_to_cik(r.json())

    frames, missing = [], []
    for i, t in enumerate(tickers, 1):
        cik = cik_map.get(t.upper())
        if not cik:
            missing.append(t); continue
        try:
            time.sleep(pause)  # SEC fair-access: <= 10 requests/second
            resp = s.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", timeout=60)
            resp.raise_for_status()
            df = extract_facts(t, cik, resp.json())
            (frames if not df.empty else missing).append(df if not df.empty else t)
        except Exception as e:
            log.warning("EDGAR %s failed: %s", t, e); missing.append(t)
        if i % 20 == 0:
            log.info("fundamentals %d/%d", i, len(tickers))
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    path = data_dir / "fundamentals" / "us_edgar_facts.parquet"
    if not out.empty:
        write_parquet(out, path)
    return out, missing, path
