# Claude × Hyperliquid — an honest backtest

Can an LLM write a crypto trading strategy that actually holds up? This project lets
**Claude** design three fully-mechanical strategies, freezes them, and runs them — plus
dumb baselines — through **one deterministic, event-driven backtest** on real Hyperliquid
price history. Same data, same fees, same slippage, same out-of-sample split for every
strategy, so nothing can quietly cheat.

**The method is the point.** Same code + the same cached candles ⇒ the same numbers,
forever. Clone it, run it, and you should reproduce the result exactly.

## What's here (code only)

```
fetch_hyperliquid.py   # cache real candles from Hyperliquid's public candleSnapshot (no API key)
strategies.py          # the 3 frozen Claude strategies (OHLCV-only, long/flat, no leverage)
baselines.py           # buy & hold, SMA cross, and a random-entry Monte-Carlo cloud
backtest.py            # the ONE deterministic harness: fees/slippage, train/test split, scoring
overfit.py             # the curve-fit trap, shown on purpose: optimize on the data it's tested on
prompts/               # the verbatim prompt given to Claude + its response (the frozen spec)
```

Running the code regenerates everything else (`data/`, `results.json`, chart specs) locally.

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python fetch_hyperliquid.py     # cache BTC + ETH 1h candles -> data/
python backtest.py              # -> results.json (the headline numbers) + chart specs
python overfit.py               # the train/test curve-fit demonstration
```

## Method notes (so the numbers are honest)

- **Framework:** [Backtesting.py](https://kernc.github.io/backtesting.py/) — event-driven,
  so `next()` only ever sees bars up to "now". No-lookahead is guaranteed by design.
- **Costs:** Hyperliquid taker ≈ 0.045%/side; the headline scenario adds 2 bps slippage
  (`realistic` ≈ 0.065%/side, charged on entry and exit). Funding is **not** modeled — a
  stated caveat, not a result.
- **Split:** first 70% in-sample / last 30% out-of-sample. Parameters are textbook defaults
  chosen *before* seeing the data, so the split tests robustness, not tuning.
- **Data limit:** Hyperliquid's public `candleSnapshot` caps each request at ~5,000 candles,
  which at 1h is ~208 days — a single regime. More data → more statistical confidence; treat
  results as a strong method on a thin sample.

Strategies and parameters are frozen in `strategies.py` exactly as Claude wrote them
(`prompts/`). From there, Claude doesn't get a vote — the data does.
