"""Central settings: where data lands, which series we pull, which EDGAR concepts we keep."""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", REPO / "data" / "raw"))  # git-ignored
CONFIG_DIR = REPO / "configs"
DEFAULT_START = "2010-01-01"

# --- Universe sources (current constituents; see survivorship caveat in universe.py) ---
NIFTY50_URLS = [
    "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
]
SP100_URL = "https://en.wikipedia.org/wiki/S%26P_100"

# --- Daily market / macro series from Yahoo Finance (name -> yahoo ticker) ---
YAHOO_MACRO = {
    "nifty50": "^NSEI",
    "bank_nifty": "^NSEBANK",
    "india_vix": "^INDIAVIX",
    "sp500": "^GSPC",
    "sp100": "^OEX",
    "vix": "^VIX",
    "usdinr": "INR=X",
    "gold_usd": "GC=F",
    "silver_usd": "SI=F",
    "brent": "BZ=F",
    "wti": "CL=F",
    "goldbees_inr": "GOLDBEES.NS",
    "btc_usd": "BTC-USD",
    "eth_usd": "ETH-USD",
}

# --- FRED series (name -> FRED id); CSV endpoint, no API key needed ---
FRED_SERIES = {
    "us_3m_tbill": "DTB3",      # daily, % p.a.
    "us_10y": "DGS10",          # daily, % p.a.
    "vix_fred": "VIXCLS",       # daily, cross-check for ^VIX
    "india_10y_monthly": "INDIRLTLT01STM",  # monthly, OECD long-term gov bond yield (verify id on first run)
}

# --- SEC EDGAR concepts kept per field (several candidates: companies tag the same thing differently) ---
# Raw rows keep EVERY filed version (incl. restatements) so joins can be point-in-time on `filed`.
EDGAR_FIELDS: dict[str, list[tuple[str, str]]] = {
    "revenue": [("us-gaap", "Revenues"),
                ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
                ("us-gaap", "SalesRevenueNet")],
    "gross_profit": [("us-gaap", "GrossProfit")],
    "operating_income": [("us-gaap", "OperatingIncomeLoss")],
    "net_income": [("us-gaap", "NetIncomeLoss")],
    "eps_diluted": [("us-gaap", "EarningsPerShareDiluted")],
    "total_assets": [("us-gaap", "Assets")],
    "total_liabilities": [("us-gaap", "Liabilities")],
    "equity": [("us-gaap", "StockholdersEquity")],
    "long_term_debt": [("us-gaap", "LongTermDebt"), ("us-gaap", "LongTermDebtNoncurrent")],
    "shares_outstanding": [("dei", "EntityCommonStockSharesOutstanding")],
}
EDGAR_FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A"}
