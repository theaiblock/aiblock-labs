# alpha-research-loop

A research loop that turns one plain-English research question into a **population** of trading
strategies, scores every one of them on a locked engine, and writes the prompt for the next round.

```
ideas/<question>.md
   │  ideate.py      N independent model calls (Claude or Codex) → N structured theses
   ▼
populations/<question>/ideas/
   │  implement.py   an agent writes candidate.py per thesis, loops on ./check until it passes
   ▼
populations/<question>/implementations/
   │  backtest.py    locked engine, no model → one result per implementation, vs the benchmark
   ▼
populations/<question>/backtests/
   │  analyse.py     distribution, return clusters, per-year table, chart specs
   ▼
populations/<question>/analysis/
   │  synthesise.py  one model call reads the analysis only → conclusions + next_prompt.md
   ▼
populations/<question>/synthesis/next_prompt-<run>.md   → feed it back into ideate.py
```

The model only ever writes one function, `signal(close, volume, universe)`, which returns target
weights. Everything else (data, universe, rebalancing, fees, scoring, statistics) is fixed code the
model never touches. That split is what makes a population of 120 model-written strategies
comparable with each other.

## What's fixed

- **Data** (`fetch_data.py`): daily candles for every Binance spot USDT pair, delisted pairs
  included, from the public archive at data.binance.vision. No API key. Stablecoins, fiat,
  leveraged tokens, wrapped BTC/ETH and tokenised stocks are left out.
- **Universe** (`universe.md`): every day, the 100 most-traded coins by 30-day average volume, with
  at least 60 days of history and $2M average daily volume. Point-in-time, so coins enter and leave.
- **Engine** (`engine.py`): weekly rebalance, traded at the next day's close; long only; 10% cap per
  coin; fees by liquidity (0.10% / 0.20% / 0.40%); marked daily with vectorbt. Every candidate is
  statically checked and tested for look-ahead before it is scored.
- **Contract** (`contract.md`): exactly what a signal can see and return. It is sent verbatim to
  every model call.
- **Windows**: `dev` = 2021-01-01 → 2025-08-31, the only data the loop and the agents ever see.
  `sealed` = 2025-09-01 → 2026-08-31, scored only with `--window sealed`, and every opening is
  appended to `SEALED_LOG.jsonl`.
- **Benchmark**: hold every universe coin whose 28-day return is positive, at an equal share; the
  rest in cash. Dev Sharpe 0.87.
- **Verdict** (`stats.py`): a paired block bootstrap of the Sharpe difference vs the benchmark
  (28-day blocks, 2,000 samples, fixed seed) → `above` / `below` / `unclear`.

## Requirements

- Python 3.11+ (`pip install -r requirements.txt`; vectorbt pulls in pandas and numpy).
- For the model steps: the [Claude Code](https://claude.com/claude-code) CLI (`claude`) and/or the
  Codex CLI (`codex`), logged in. Both run headless (`claude -p`, `codex exec`); no API key is read
  by this code. Backtest and analysis need no model.
- Optional: `analyse.py --render` draws the charts with a `viz/` renderer (node + Chrome) if it finds
  one in a parent folder. Without it, the chart specs are still written as JSON.

## Reproduce

```bash
pip install -r requirements.txt
python fetch_data.py                          # ~590 pairs → data/close.csv.gz, data/volume.csv.gz

# test the rig with no model: hand-written good and bad variants
python calibration/make_population.py
python backtest.py populations/_calibration
python analyse.py populations/_calibration

# a real round
python ideate.py ideas/good.md --runner claude --n 20
python ideate.py ideas/good.md --runner codex --n 20
python implement.py populations/good --impls 3 --concurrency 6
python backtest.py populations/good
python analyse.py populations/good
python synthesise.py populations/good

# once, at the very end
python backtest.py populations/good --window sealed
```

Three research questions ship in `ideas/`: `good.md` (size positions by inverse volatility),
`bad.md` (buy last week's biggest gainers) and `broad.md` (any one change to the benchmark). Write
your own the same way: one paragraph, one question. Set `ALPHA_DATA_DIR` to keep the data outside
this folder.

## Calibration: the rig separates good from bad

Hand-written variants, no model, dev window:

| signal | Sharpe | Δ vs benchmark [95% interval] | verdict |
|---|---|---|---|
| inverse-vol 30d | 1.06 | +0.19 [+0.07, +0.29] | above |
| inverse-vol 60d | 1.03 | +0.15 [+0.06, +0.25] | above |
| portfolio vol target | 0.96 | +0.09 [−0.20, +0.41] | unclear |
| yesterday's top 20 | 0.47 | −0.40 [−0.91, +0.10] | unclear |
| last week's top 20 | 0.04 | −0.83 [−1.36, −0.28] | below |

## Caveats

- **Backtest, not live.** Daily closes only: no order book, no slippage model beyond the fee tiers,
  no borrow or funding (long only). The universe is Binance spot; delisted coins are sold at their
  last close.
- **Model runs are not deterministic.** Re-running `ideate.py` / `implement.py` gives a different
  population. The engine and the statistics are deterministic: same code and data, same scores.
- **The sealed year is only sealed if you keep it sealed.** Each opening is logged; open it once.
- For education and research only. Not financial advice.
