#!/usr/bin/env python3
"""Fetch daily OHLCV for a cross-section of liquid coins from Binance (public, no key).

Datasource for this lab. Self-contained by design: this
script is the experiment's only data dependency. Binance's public REST klines endpoint
needs no API key for market data.

Scope / caveats (state on air):
  * Price + volume ONLY (daily OHLCV). Everything else — on-chain fundamentals, Hyperliquid
    microstructure — is deliberately held for later videos. That boundary is itself a finding.
  * SURVIVORSHIP BIAS: the symbol list is "liquid coins as of 2026-07", i.e. ones that
    survived. Coins that died are absent, which flatters any long-biased backtest. We name
    this on screen; it does not change the thesis (the OOS collapse is about overfitting, not
    coin selection), but it is an honest caveat.
  * Later-listed coins (e.g. ARB, APT, OP) have leading gaps; the backtest masks a coin on
    bars where it has no data. History starts 2021-01-01 to give a warmup buffer for the
    200-day SMA before the 2022-07 train window.

Output: data/ohlcv.parquet — long format, columns: date, symbol, open, high, low, close,
volume. Regenerable; gitignored (raw data is never pushed to the public repo).

Usage:
    python fetch.py
    python fetch.py --start 2021-01-01 --end 2026-07-20
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.binance.com/api/v3/klines"
INTERVAL = "1d"
LIMIT = 1000  # Binance max klines per request
QUOTE = "USDT"

# ~30 liquid coins as of 2026-07 (base assets; paired vs USDT). Survivorship-biased on purpose
# (see caveat above); any symbol that errors or returns too little data is skipped with a warning.
BASES = [
    "BTC", "ETH", "BNB", "XRP", "SOL", "ADA", "DOGE", "TRX", "AVAX", "DOT",
    "LINK", "LTC", "BCH", "ATOM", "XLM", "ETC", "UNI", "FIL", "NEAR", "ICP",
    "APT", "ARB", "OP", "INJ", "AAVE", "ALGO", "VET", "GRT", "SAND", "AXS",
]

DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_PATH = DATA_DIR / "ohlcv.parquet"

# Binance kline columns (12 fields per row)
_KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
]


def _to_ms(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def fetch_symbol(symbol: str, start_ms: int, end_ms: int, session: requests.Session) -> pd.DataFrame:
    """Fetch all daily klines for one symbol between start and end (paginated)."""
    rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        params = {
            "symbol": symbol,
            "interval": INTERVAL,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": LIMIT,
        }
        resp = session.get(BASE_URL, params=params, timeout=30)
        if resp.status_code != 200:
            # 400 with "Invalid symbol" -> symbol not tradeable; surface it to the caller
            raise RuntimeError(f"{symbol}: HTTP {resp.status_code} {resp.text[:120]}")
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        last_open = batch[-1][0]
        nxt = last_open + 86_400_000  # +1 day
        if nxt <= cursor:  # no progress -> stop
            break
        cursor = nxt
        if len(batch) < LIMIT:  # reached the end
            break
        time.sleep(0.15)  # be polite to the public endpoint

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=_KLINE_COLS)
    df = df.drop_duplicates(subset="open_time")
    out = pd.DataFrame({
        "date": pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize(),
        "symbol": symbol,
        "open": pd.to_numeric(df["open"]),
        "high": pd.to_numeric(df["high"]),
        "low": pd.to_numeric(df["low"]),
        "close": pd.to_numeric(df["close"]),
        "volume": pd.to_numeric(df["volume"]),
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2021-01-01", help="UTC start date YYYY-MM-DD (warmup buffer)")
    ap.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"), help="UTC end date YYYY-MM-DD")
    args = ap.parse_args()

    start_ms, end_ms = _to_ms(args.start), _to_ms(args.end)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "aiblock-labs/1.0"})

    frames: list[pd.DataFrame] = []
    print(f"Fetching {len(BASES)} symbols, {INTERVAL} bars, {args.start} -> {args.end}\n")
    print(f"{'symbol':<12}{'bars':>6}  {'first':<12}{'last':<12}")
    print("-" * 44)
    for base in BASES:
        symbol = f"{base}{QUOTE}"
        try:
            df = fetch_symbol(symbol, start_ms, end_ms, session)
        except Exception as e:  # noqa: BLE001
            print(f"{symbol:<12}{'SKIP':>6}  {e}")
            continue
        if df.empty:
            print(f"{symbol:<12}{'0':>6}  (no data)")
            continue
        frames.append(df)
        first, last = df["date"].min().date(), df["date"].max().date()
        print(f"{symbol:<12}{len(df):>6}  {str(first):<12}{str(last):<12}")

    if not frames:
        print("\nNo data fetched.", file=sys.stderr)
        return 1

    alldf = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    alldf.to_parquet(OUT_PATH, index=False)

    n_symbols = alldf["symbol"].nunique()
    print("-" * 44)
    print(f"\nWrote {OUT_PATH.relative_to(Path(__file__).resolve().parent.parent.parent)}")
    print(f"  {len(alldf):,} rows | {n_symbols} symbols | "
          f"{alldf['date'].min().date()} -> {alldf['date'].max().date()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
