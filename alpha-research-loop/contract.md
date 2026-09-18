# Backtest contract

What a signal idea can and cannot control. The engine is fixed; ideas only change the signal.

## Data you get

Three pandas DataFrames with the same index (one row per day) and the same columns (one per coin):

- `close`: daily closing price in USDT. **NaN when the coin is not trading** (before listing, after
  delisting).
- `volume`: USDT traded that day (0 when not trading).
- `universe`: True where the coin is tradable that day. Point-in-time: the 100 coins with the highest
  30-day average volume among those trading, with at least 60 days of history and at least $2M
  average daily volume. Coins enter and leave it; delisted coins are included while they traded.

Binance spot, USDT pairs, from 2020-01-01. No open/high/low, no order book, no other data. You are
shown data to 2025-08-31.

## What you write

One function:

```python
def signal(close: pd.DataFrame, volume: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Same index and columns as close. Each value is the target weight of that coin in the
    portfolio, as a fraction of total equity."""
```

- Weights are between 0 and 1, **0 wherever `universe` is False**, and each day's weights sum to at
  most 1. Whatever is not allocated is held in cash (earning nothing).
- The value on day `t` may use only data up to and including day `t`.
- Allowed libraries: `numpy`, `pandas`. No files, no network, no other data.
- NaN is treated as 0.

## What the engine does (you cannot change it)

1. **Weekly rebalance.** Every 7th day it reads your weights for that day and trades to them at the
   next day's close. Weights on the other six days are ignored. Between rebalances, positions drift
   with prices.
2. Caps any single coin at 10% of equity; the excess stays in cash.
3. Long only, no leverage.
4. Charges fees on every trade by liquidity: 0.10% for the 20 most-traded coins in the universe,
   0.20% for ranks 21–50, 0.40% for the rest. A coin that is delisted while held is sold at its last
   close.
5. Marks the portfolio daily (vectorbt `Portfolio.from_orders`, target percent, shared cash) and
   reports annualised Sharpe (365 days), return, drawdown, exposure, turnover and fees.

## Benchmark (Sharpe 0.87, 2021-01-01 → 2025-08-31)

Hold every coin in the universe whose 28-day return is positive, each at an equal share of the
universe (1/number of coins in the universe); coins in a downtrend are left in cash.

```python
def signal(close, volume, universe):
    up = close / close.shift(28) - 1 > 0
    n = universe.sum(axis=1)
    return (up & universe).astype(float).div(n, axis=0).fillna(0.0)
```
