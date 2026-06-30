# Claude strategy response (the receipt — shown on screen)

> Claude's answer to `claude_strategy_prompt.md`, frozen before the backtest.
> Three mechanically distinct, OHLCV-only, long/flat strategies with textbook default
> parameters chosen a priori (no tuning). Implemented verbatim in `../strategies.py`.

All three: long/flat only, no leverage, **size = ~100% of equity per entry** (all-in long
or fully in cash). Decisions use bar *t*'s close and earlier; orders fill at bar *t+1*'s
open (handled by the framework — no same-bar lookahead).

---

## Strategy 1 — Donchian Breakout (trend-following)

- **Thesis:** crypto trends; ride a genuine breakout to a new high, cut when it breaks down.
- **Entry:** go long when Close > the highest High of the prior **20** bars (excluding the
  current bar).
- **Exit:** close the long when Close < the lowest Low of the prior **10** bars.
- **Params:** entry channel 20, exit channel 10 (classic Turtle-style asymmetry).
- **Known weakness:** whipsaws in choppy, sideways markets — buys false breakouts, gets
  stopped on the pullback, repeatedly.

## Strategy 2 — RSI(2) Mean-Reversion with trend filter (Connors-style)

- **Thesis:** short-term oversold dips inside an uptrend tend to bounce.
- **Entry:** go long when RSI(2) < **10** **and** Close > SMA(**200**) (only dip-buy when the
  long-term trend is up).
- **Exit:** close the long when Close > SMA(**5**).
- **Params:** RSI length 2, oversold threshold 10, trend filter SMA 200, exit SMA 5.
- **Known weakness:** "catches a falling knife" if a real downtrend starts — the SMA(200)
  filter lags, so it can keep buying dips that keep dipping.

## Strategy 3 — MACD Momentum (zero-line confirmed)

- **Thesis:** trade only confirmed positive momentum; exit when momentum rolls over.
- **Entry:** go long when the MACD line (EMA12 − EMA26) crosses **above** its signal
  (EMA9 of MACD) **and** the MACD line is above **0**.
- **Exit:** close the long when the MACD line crosses **below** its signal.
- **Params:** MACD 12 / 26 / 9, zero-line confirmation on entry.
- **Known weakness:** MACD is laggy — it enters late after a move is underway and exits
  late after the top, giving back gains in sharp reversals.

---

### Why these three (for the script)

They are three different *families* on purpose: **breakout** (Donchian), **mean-reversion**
(RSI2), and **momentum** (MACD). If trend-following and mean-reversion can't both be right
in the same window, at most one should look good — which is itself a useful tell about
whether any edge is real or just the regime. Every parameter is the well-known default for
its method, picked before seeing results, so nothing here is curve-fit.
