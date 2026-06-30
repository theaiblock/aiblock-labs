#!/usr/bin/env python3
"""Fetch + cache Hyperliquid candles (deterministic, extract-once).

Hyperliquid public info endpoint, `candleSnapshot`. No API key. Returns up to ~5000
candles per request. We drop the final (possibly unclosed) candle so a re-run yields
identical closed bars, and record the exact fetch window in meta.json for reproducibility.

    .venv/bin/python experiments/004_claude_hyperliquid_backtest/fetch_hyperliquid.py
    .venv/bin/python .../fetch_hyperliquid.py --coins BTC,ETH --interval 1h --candles 5000

Output: data/<COIN>_<interval>.parquet  +  data/meta.json
Columns: time (open ms, UTC), datetime, open, high, low, close, volume, trades, coin, interval
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://api.hyperliquid.xyz/info"
DATA_DIR = Path(__file__).parent / "data"

# Interval length in milliseconds (for windowing the request).
INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000,
    "4h": 14_400_000, "1d": 86_400_000,
}


def fetch_candles(coin: str, interval: str, n_candles: int) -> pd.DataFrame:
    """Pull the most recent `n_candles` closed candles for `coin`."""
    step = INTERVAL_MS[interval]
    end = int(time.time() * 1000)
    start = end - n_candles * step
    body = {
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval, "startTime": start, "endTime": end},
    }
    resp = requests.post(API_URL, json=body, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    if not raw:
        raise RuntimeError(f"No candles returned for {coin} {interval}")

    df = pd.DataFrame(raw)
    # Hyperliquid keys: t=open ms, T=close ms, s=coin, i=interval, o/c/h/l, v=vol, n=trades
    df = df.rename(columns={
        "t": "time", "o": "open", "h": "high", "l": "low",
        "c": "close", "v": "volume", "n": "trades",
    })
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="raise")
    df["trades"] = pd.to_numeric(df["trades"], errors="coerce").astype("Int64")
    df["time"] = df["time"].astype("int64")
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)

    # Drop the last candle if it isn't closed yet (close time in the future).
    now_ms = int(time.time() * 1000)
    if int(df.iloc[-1]["T"]) > now_ms:
        df = df.iloc[:-1].reset_index(drop=True)

    df["datetime"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df["coin"] = coin
    df["interval"] = interval
    return df[["time", "datetime", "open", "high", "low", "close", "volume", "trades", "coin", "interval"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coins", default="BTC,ETH", help="comma-separated, e.g. BTC,ETH")
    ap.add_argument("--interval", default="1h", choices=list(INTERVAL_MS))
    ap.add_argument("--candles", type=int, default=5000, help="most recent N candles")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]
    meta = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "hyperliquid /info candleSnapshot",
        "interval": args.interval,
        "requested_candles": args.candles,
        "markets": {},
    }

    for coin in coins:
        df = fetch_candles(coin, args.interval, args.candles)
        out = DATA_DIR / f"{coin}_{args.interval}.parquet"
        df.to_parquet(out, index=False)
        first, last = df.iloc[0]["datetime"], df.iloc[-1]["datetime"]
        meta["markets"][coin] = {
            "rows": len(df),
            "first": first.isoformat(),
            "last": last.isoformat(),
            "file": out.name,
        }
        span_days = (last - first).total_seconds() / 86400
        print(f"{coin} {args.interval}: {len(df)} candles  "
              f"{first:%Y-%m-%d} -> {last:%Y-%m-%d}  (~{span_days:.0f}d)  -> {out.name}")

    (DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\nmeta -> {DATA_DIR / 'meta.json'}")


if __name__ == "__main__":
    main()
