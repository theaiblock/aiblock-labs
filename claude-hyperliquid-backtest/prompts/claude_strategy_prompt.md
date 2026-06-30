# Claude strategy prompt (the receipt — shown on screen)

> Verbatim prompt given to Claude. Saved before any backtest so the rules are frozen
> and the test is not reverse-fitted to a result.

---

You are designing crypto trading strategies that will be tested in a **deterministic,
event-driven backtest** (Backtesting.py) on real Hyperliquid 1h candles for BTC and ETH.
You will **not** run the backtest, see the data, or revise the rules afterward — they are
frozen the moment you write them.

Give me **exactly 3** strategies. Hard constraints on every one:

- **OHLCV-only.** Inputs limited to open, high, low, close, volume. No news, no social
  sentiment, no order book, no funding rates, no external data.
- **Fully mechanical.** Exact entry rule, exact exit rule, exact numeric parameters.
  No discretionary language ("if it looks strong"), no "use judgment".
- **No lookahead.** A decision on bar *t* may only use information available at the close
  of bar *t* or earlier. Execution happens on the next bar's open.
- **Long/flat only.** Either fully long or in cash. No shorting, no leverage.
- **Position sizing defined.** State how much to allocate per entry.
- **Implementable in ~20 lines of Python** against an indicator library.
- **Pick textbook default parameters a priori.** Do NOT tune to any sample — choose the
  conventional defaults for each method so there is zero curve-fitting.

Make the 3 strategies **mechanically distinct** (different signal families), so the test
compares genuinely different ideas, not three flavors of the same thing.

For each: name, one-line thesis, exact entry, exact exit, parameters, position size, and
the single biggest way it could be fooled (its known weakness).
