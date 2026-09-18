"""Daily candles for every Binance spot USDT pair, delisted pairs included, from the public archive
(data.binance.vision). No API key.

Writes data/close.csv.gz and data/volume.csv.gz (date x coin; volume = USDT traded that day).
Empty = not trading that day. Stablecoins, fiat, leveraged tokens, wrapped BTC/ETH and tokenised
stocks are left out: the universe is crypto assets.

    python fetch_data.py
"""
import io
import os
import re
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ARCHIVE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DATA = Path(os.environ.get("ALPHA_DATA_DIR", Path(__file__).parent / "data"))
RAW = DATA / "raw"
LAST_MONTH = "2026-08"
NOT_CRYPTO = {"USDC", "BUSD", "TUSD", "USDP", "PAX", "DAI", "FDUSD", "UST", "USTC", "SUSD", "EUR", "GBP", "AUD",
              "TRY", "BRL", "RUB", "UAH", "NGN", "BIDR", "IDRT", "BVND", "USDS", "USDSB", "PAXG", "EURI", "AEUR",
              "XUSD", "USD1", "BFUSD", "RLUSD", "U", "WBTC", "WBETH", "BETH", "BTCST"}


def get(url: str) -> bytes:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise


def list_archive(prefix: str, tag: str) -> list[str]:
    out, marker = [], ""
    while True:
        xml = get(f"{ARCHIVE}?delimiter=/&prefix={prefix}&marker={marker}").decode()
        items = re.findall(f"<{tag}>([^<]*)</{tag}>", xml)
        out += items
        if "<IsTruncated>true" not in xml:
            return out
        nxt = re.findall(r"<NextMarker>([^<]*)</NextMarker>", xml)
        marker = nxt[0] if nxt else items[-1]


def fetch_pair(pair: str) -> None:
    dest = RAW / f"{pair}.csv"
    if dest.exists():
        return
    keys = [k for k in list_archive(f"data/spot/monthly/klines/{pair}/1d/", "Key")
            if k.endswith(".zip") and k[-11:-4] <= LAST_MONTH]
    frames = []
    for key in keys:
        z = zipfile.ZipFile(io.BytesIO(get(f"https://data.binance.vision/{key}")))
        df = pd.read_csv(z.open(z.namelist()[0]), header=None)
        if not str(df.iloc[0, 0]).isdigit():  # some files carry a header row
            df = df.iloc[1:]
        frames.append(df.iloc[:, [0, 4, 7]].astype(float))  # open time, close, quote volume
    if not frames:
        return
    df = pd.concat(frames)
    df.columns = ["t", "close", "volume"]
    ms = df.t.where(df.t < 1e14, df.t / 1000)  # the archive switched to microseconds in 2025
    df["date"] = pd.to_datetime(ms, unit="ms").dt.normalize()
    df[["date", "close", "volume"]].drop_duplicates("date").to_csv(dest, index=False)


def is_crypto_pair(pair: str) -> bool:
    base = pair[:-4]
    return (pair.isascii() and pair.isalnum() and pair.endswith("USDT") and base not in NOT_CRYPTO
            and not re.search(r"(UP|DOWN|BULL|BEAR)$", base))


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    pairs = [p.split("/")[-2] for p in list_archive("data/spot/monthly/klines/", "Prefix")]
    pairs = [p for p in pairs if is_crypto_pair(p)]
    print(f"{len(pairs)} USDT pairs")
    with ThreadPoolExecutor(24) as pool:
        list(pool.map(fetch_pair, pairs))
    close, volume = {}, {}
    for f in sorted(RAW.glob("*.csv")):
        if not is_crypto_pair(f.stem):
            continue
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date").rename(columns={"qv": "volume"})
        close[f.stem[:-4]], volume[f.stem[:-4]] = d.close, d.volume
    close, volume = pd.DataFrame(close).sort_index(), pd.DataFrame(volume).sort_index()
    # tokenised stocks (AAPLB, NVDAB, ...) list on Binance from mid-2026: an equity, not a crypto asset
    first = close.apply(lambda s: s.first_valid_index())
    stocks = [c for c in close if c.endswith("B") and first[c] >= pd.Timestamp("2026-05-01")]
    close, volume = close.drop(columns=stocks), volume.drop(columns=stocks)
    close.to_csv(DATA / "close.csv.gz")
    volume.to_csv(DATA / "volume.csv.gz")
    print(f"{close.shape[1]} coins, {close.index[0].date()} → {close.index[-1].date()}, "
          f"{int((close.apply(lambda s: s.last_valid_index()) < close.index[-1]).sum())} delisted; "
          f"left out {len(stocks)} tokenised stocks")


if __name__ == "__main__":
    main()
