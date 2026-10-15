"""Sanity checks on pulled data. Returns a summary dict + human-readable issues (stored in the manifest)."""
from __future__ import annotations

import pandas as pd


def validate_prices(df: pd.DataFrame, jump: float = 0.5, max_gap_days: int = 10) -> dict:
    if df.empty:
        return {"rows": 0, "tickers": 0, "issues": ["no data"]}
    issues: list[str] = []
    dups = int(df.duplicated(["ticker", "date"]).sum())
    if dups:
        issues.append(f"{dups} duplicate (ticker,date) rows")
    bad_px = df[(df["close"] <= 0) | (df["adj_close"] <= 0)]
    if len(bad_px):
        issues.append(f"{len(bad_px)} rows with non-positive close/adj_close ({sorted(bad_px['ticker'].unique())[:5]})")
    tol = 1e-6
    bad_range = df[(df["high"] < df["low"] - tol) | (df["close"] > df["high"] * 1.001 + tol) | (df["close"] < df["low"] * 0.999 - tol)]
    if len(bad_range):
        issues.append(f"{len(bad_range)} rows where high/low do not bracket close")
    zero_vol = float((df["volume"].fillna(0) == 0).mean())
    if zero_vol > 0.02:
        issues.append(f"{zero_vol:.1%} of rows have zero/NaN volume")

    d = df.sort_values(["ticker", "date"])
    ret = d.groupby("ticker")["adj_close"].pct_change()
    big = d[ret.abs() > jump]
    if len(big):
        issues.append(f"{len(big)} daily moves > {jump:.0%} in adj_close (check splits/bonuses): "
                      f"{sorted(big['ticker'].unique())[:8]}")
    gaps = d.groupby("ticker")["date"].diff().dt.days
    gapped = d[gaps > max_gap_days]["ticker"].unique()
    if len(gapped):
        issues.append(f"gaps > {max_gap_days} calendar days in: {sorted(gapped)[:8]}")
    return {"rows": int(len(df)), "tickers": int(df["ticker"].nunique()),
            "min_date": str(df["date"].min().date()), "max_date": str(df["date"].max().date()),
            "issues": issues}


def validate_macro(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"rows": 0, "series": 0, "issues": ["no data"]}
    per = df.groupby("series")["date"].agg(["min", "max", "count"])
    return {"rows": int(len(df)), "series": int(per.shape[0]),
            "by_series": {k: {"from": str(v["min"].date()), "to": str(v["max"].date()), "n": int(v["count"])}
                          for k, v in per.iterrows()},
            "issues": [f"{s}: only {int(c)} rows" for s, c in per["count"].items() if c < 100 and s != "india_10y_monthly"]}
