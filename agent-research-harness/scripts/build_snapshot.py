from __future__ import annotations

import csv
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "crypto_allocation"
API = "https://api.binance.com/api/v3/klines"
SYMBOLS = ("ADAUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "XRPUSDT", "BCHUSDT")
START = "2021-01-01"
SPLIT = "2024-01-01"
END = "2025-12-31"


def millis(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(symbol: str) -> list[tuple[str, str]]:
    cursor = millis(START)
    end = millis(END)
    rows: list[tuple[str, str]] = []
    while cursor <= end:
        query = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": "1d",
            "startTime": cursor,
            "endTime": end,
            "limit": 1000,
        })
        with urllib.request.urlopen(f"{API}?{query}", timeout=30) as response:
            page = json.load(response)
        if not page:
            break
        for candle in page:
            day = datetime.fromtimestamp(candle[0] / 1000, tz=UTC).date().isoformat()
            rows.append((day, candle[4]))
        cursor = int(page[-1][0]) + 86_400_000
        time.sleep(0.05)
    return rows


def write_prices(path: Path, dates: list[str], by_symbol: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("date", *SYMBOLS))
        for day in dates:
            writer.writerow((day, *(by_symbol[symbol][day] for symbol in SYMBOLS)))


def main() -> None:
    by_symbol = {symbol: dict(fetch(symbol)) for symbol in SYMBOLS}
    common = sorted(set.intersection(*(set(rows) for rows in by_symbol.values())))
    train_dates = [day for day in common if START <= day < SPLIT]
    holdout_dates = [day for day in common if SPLIT <= day <= END]
    if len(train_dates) < 1000 or len(holdout_dates) < 700:
        raise RuntimeError(f"Unexpected snapshot size: train={len(train_dates)}, holdout={len(holdout_dates)}")

    train_path = TASK / "train" / "prices.csv"
    holdout_path = TASK / "sealed" / "holdout_prices.csv"
    write_prices(train_path, train_dates, by_symbol)
    write_prices(holdout_path, holdout_dates, by_symbol)

    manifest = {
        "source": API,
        "venue": "binance",
        "market": "spot",
        "quote": "USDT",
        "symbols": list(SYMBOLS),
        "start": START,
        "split": SPLIT,
        "end": END,
        "train_rows": len(train_dates),
        "holdout_rows": len(holdout_dates),
        "train_sha256": sha256(train_path),
        "holdout_sha256": sha256(holdout_path),
        "evaluation": {"lookback_days": 252, "rebalance_days": 21, "taker_bps": 10},
    }
    (TASK / "train" / "manifest.json").write_text(
        json.dumps({k: v for k, v in manifest.items() if k != "holdout_sha256"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (TASK / "sealed" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
