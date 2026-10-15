"""CLI:  python -m src.ingest.run [universe|prices|macro|fundamentals|all] [options]

Examples
  python -m src.ingest.run all --limit 5          # quick smoke test (5 tickers per market)
  python -m src.ingest.run prices --markets india
  python -m src.ingest.run prices --full          # refresh whole history (restated adj_close)
  SEC_USER_AGENT="Your Name you@example.com" python -m src.ingest.run fundamentals
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import config, fundamentals, macro, prices, universe, validate
from .io import update_manifest

log = logging.getLogger("ingest")
MARKETS = {"india": "nifty50", "us": "sp100"}
CAVEAT = "current constituents only (survivorship bias) — replace with Bloomberg historical constituents"


def run_prices(markets, start, end, limit, full, data_dir) -> bool:
    ok = True
    for m in markets:
        name = MARKETS[m]
        uni = universe.get_universe(name, data_dir)
        tickers = uni["ticker"].tolist()[: limit or None]
        log.info("== prices %s: %d tickers", name, len(tickers))
        df, missing, path = prices.update(name, tickers, start, data_dir, end, full)
        v = validate.validate_prices(df)
        for issue in v["issues"]:
            log.warning("[%s] %s", name, issue)
        update_manifest(data_dir, f"prices/{name}", {
            "path": str(path), "source": "yahoo/yfinance", "universe_caveat": CAVEAT,
            "requested": len(tickers), "missing_tickers": missing, "validation": v})
        ok &= not df.empty
    return ok


def run_macro(start, end, data_dir) -> bool:
    log.info("== macro")
    df, missing, path = macro.update(start, data_dir, end)
    v = validate.validate_macro(df)
    for issue in v["issues"]:
        log.warning("[macro] %s", issue)
    update_manifest(data_dir, "macro/macro_daily", {
        "path": str(path), "source": "yahoo + fred", "missing_series": missing, "validation": v})
    return not df.empty


def run_fundamentals(limit, data_dir) -> bool:
    if not os.getenv("SEC_USER_AGENT"):
        log.warning('Skipping fundamentals: set SEC_USER_AGENT="Your Name you@example.com" (SEC requires it)')
        return True
    uni = universe.get_universe("sp100", data_dir)
    tickers = uni["ticker"].tolist()[: limit or None]
    log.info("== fundamentals (EDGAR): %d tickers", len(tickers))
    df, missing, path = fundamentals.update(tickers, data_dir)
    update_manifest(data_dir, "fundamentals/us_edgar_facts", {
        "path": str(path), "source": "sec edgar xbrl", "rows": int(len(df)),
        "tickers": int(df["ticker"].nunique()) if not df.empty else 0, "missing_tickers": missing,
        "note": "all filed versions kept; join on `filed` for point-in-time"})
    return not df.empty


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ingest.run", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="?", default="all", choices=["all", "universe", "prices", "macro", "fundamentals"])
    ap.add_argument("--markets", nargs="+", choices=list(MARKETS), default=list(MARKETS))
    ap.add_argument("--start", default=config.DEFAULT_START)
    ap.add_argument("--end", default=None)
    ap.add_argument("--limit", type=int, default=0, help="only first N tickers per market (smoke test)")
    ap.add_argument("--full", action="store_true", help="ignore existing files, refetch full history")
    ap.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    results = {}
    if a.what in ("universe", "all"):
        for m in a.markets:
            u = universe.get_universe(MARKETS[m], a.data_dir)
            log.info("universe %s: %d tickers", MARKETS[m], len(u))
        results["universe"] = True
    if a.what in ("prices", "all"):
        results["prices"] = run_prices(a.markets, a.start, a.end, a.limit, a.full, a.data_dir)
    if a.what in ("macro", "all"):
        results["macro"] = run_macro(a.start, a.end, a.data_dir)
    if a.what in ("fundamentals", "all"):
        results["fundamentals"] = run_fundamentals(a.limit, a.data_dir)
    log.info("done: %s  (manifest: %s)", results, a.data_dir / "manifest.json")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
