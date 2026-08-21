# Experiment journal

Append-only memory for the momentum research loop. Newest entries go directly below this introduction. Never rewrite an older result; add a correction entry instead.

## Current best candidate

Daily long/flat Donchian 120-day high entry / 60-day low exit (`runs/20260819T150800Z-donchian-120-60/`): 132.69% costed return, 0.700 Sharpe, -26.48% max drawdown, and 60% walk-forward consistency over 2022-2025. Best so far, but only five trades, nonsignificant permutation results, a bootstrap Sharpe interval crossing zero, and a slightly negative final window make it a tentative candidate rather than a robust conclusion.

## Coverage map

Completed: slow daily moving-average time-series momentum (SMA 50/200) and daily asymmetric breakout momentum (Donchian 120/60), both long/flat over 2022-2025 with explicit crypto costs and fixed funding. Covered bear, recovery, bull, and late-sample reversal regimes. Gaps: faster/slower absolute momentum, long/short, volatility or trend-strength filters, intraday intervals, and independent replication periods.

## Experiments

### 2026-08-19 15:08 UTC — asymmetric Donchian breakout — PASS

- Run: `runs/20260819T150800Z-donchian-120-60/`
- Fingerprint: `close>=prior 120D high enter long;close<=prior 60D low exit|required 120 complete prior closes|2022-01-01:2025-12-31|1D|long-flat 1x|maker 0.0002,taker 0.0005,slippage 0.0005/fill,fixed funding 0.0001/daily settlement`
- Hypothesis: On daily BTC, an asymmetric Donchian rule that enters long at the prior 120-day high and exits at the prior 60-day low will capture persistent upside trends while exiting prolonged reversals early enough to remain positive after explicit crypto costs and fixed funding.
- Why this next: Breakouts were an uncovered, materially different momentum family after the sole slow SMA baseline, and the previous entry identified this fixed 120/60 rule as the next useful test; this avoids tuning the latest winner.
- Data: BTC-USDT, 2022-01-01 to 2025-12-31, 1D, 1,461 bars fetched from Binance.
- Strategy: Channels exclude the current bar; enter 1.0 long when close is at or above the rolling high of the prior 120 complete closes, retain state until close is at or below the rolling low of the prior 60 complete closes, otherwise flat; native one-bar signal shift and next-bar-open execution; maximum 1x exposure.
- Costs: taker 0.05% on entry, maker 0.02% on exit, 0.05% adverse slippage on every fill, isolated 1x margin, fixed positive funding rate 0.01% per native daily fallback settlement while long.
- Result: return 132.69%, annual return 15.68%, Sharpe 0.700, max drawdown -26.48%, average turnover 0.003440, total turnover 5.025768, trades 5.
- Monte Carlo: 1,000 trade-PnL order permutations (seed 42), Sharpe p-value 0.617, drawdown p-value 0.945; only 5 trades, so this is weak path evidence. Bootstrap: 1,000 samples, 95% Sharpe CI [-0.091, 1.464], probability positive 0.954.
- Walk-forward: 5 non-overlapping fixed-rule windows, 3 profitable windows, consistency rate 60%; artifact window returns 0.00%, 10.20%, 57.38%, 31.82%, and -0.13%. This evaluates temporal consistency of the fixed rule, not walk-forward parameter optimization.
- Comparison: Versus the SMA baseline, return improved by 62.36 percentage points, Sharpe rose from 0.453 to 0.700, max drawdown improved from -39.42% to -26.48%, and benchmark excess return was +49.02 percentage points. Both have 60% profitable-window consistency and very few trades; this rule's bootstrap interval still crosses zero, permutation results are nonsignificant, and its final window is slightly negative. It becomes the tentative current best candidate on costed return and risk metrics, not a proven edge.
- Decision: candidate.
- Next useful test: Test a materially different daily volatility-managed absolute-momentum rule: long only when 180-day close-to-close return is positive, sized to a 40% annualized volatility target using trailing 30-day realized volatility and capped at 1x, with the same dates and costs.
- Notes/errors: The initial sandboxed data fetch failed because Binance, OKX, and Yahoo DNS were unavailable; preserved in `stdout.sandbox-attempt.log` and `stderr.sandbox-attempt.log`. Retrying the same immutable run with public-network access completed. Primary and standalone validation logs are preserved. Metrics and validation above come from `artifacts/metrics.csv` and `artifacts/validation.json`; Monte Carlo permutes only five realized trade PnLs and cannot establish freedom from parameter overfitting.

### 2026-08-19 15:00 UTC — slow SMA trend baseline — PASS

- Run: `runs/20260819T150036Z-sma-50-200/`
- Fingerprint: `SMA50>SMA200 long else flat|required 200 complete closes|2022-01-01:2025-12-31|1D|long-flat 1x|maker 0.0002,taker 0.0005,slippage 0.0005/fill,fixed funding 0.0001/daily settlement`
- Hypothesis: On daily BTC, a long/flat 50/200-day simple moving-average trend rule will reduce major bear-market exposure enough to remain positive after taker/maker fees, 5 bps slippage per fill, and fixed 1 bp daily funding.
- Why this next: The journal had no prior experiments, so a slow, canonical time-series momentum rule establishes a broad baseline without tuning or narrowing around a winner.
- Data: BTC-USDT, 2022-01-01 to 2025-12-31, 1D, 1,461 bars fetched from Binance.
- Strategy: Require 200 complete closes; target 1.0 long when SMA(50) > SMA(200), otherwise 0.0; native one-bar signal shift and next-bar-open execution; maximum 1x exposure.
- Costs: taker 0.05% on entry, maker 0.02% on exit, 0.05% adverse slippage on every fill, isolated 1x margin, fixed positive funding rate 0.01% per native daily fallback settlement while long.
- Result: return 70.33%, annual return 9.62%, Sharpe 0.453, max drawdown -39.42%, average turnover 0.002773, total turnover 4.052055, trades 4.
- Monte Carlo: 1,000 trade-PnL order permutations (seed 42), Sharpe p-value 0.337, drawdown p-value 0.529; only 4 trades, so this is weak path evidence. Bootstrap: 1,000 samples, 95% Sharpe CI [-0.386, 1.258], probability positive 0.857.
- Walk-forward: 5 non-overlapping windows, 3 profitable windows, consistency rate 60%; window returns 0.00%, 23.43%, 70.33%, 0.29%, and -22.59%. This is temporal evaluation of the fixed rule, not parameter-selection walk-forward optimization.
- Comparison: First completed baseline; positive after costs but lagged buy-and-hold by 13.33 percentage points, had a -39.42% drawdown, only four trades, nonsignificant permutation results, a bootstrap interval crossing zero, and a negative final window. It does not qualify as the current best candidate.
- Decision: vary.
- Next useful test: Test an untried daily Donchian breakout family: long on a 120-day high and flat on a 60-day low, with the same dates, exposure, and costs.
- Notes/errors: Initial sandboxed data fetch failed because Binance, OKX, and Yahoo DNS were unavailable; preserved in `stderr.sandbox-attempt.log`. The same immutable run was retried with public-network access and completed. Primary and standalone validation logs are preserved. Monte Carlo permutes the four realized trade PnLs and cannot establish freedom from parameter overfitting.

<!-- Copy this template for every attempt.

### YYYY-MM-DD HH:MM UTC — <short hypothesis> — PASS | FAIL | BLOCKED

- Run: `runs/<run-id>/`
- Fingerprint: `<canonical rule|params|dates|interval|exposure|costs>`
- Hypothesis: <one sentence written before running>
- Why this next: <gap in journal or user feedback>
- Data: BTC-USDT, <start> to <end>, <interval>, <bar count>
- Strategy: <rule and exact parameters>
- Costs: <maker/taker, slippage, funding mode/rate>
- Result: return <>, Sharpe <>, max drawdown <>, turnover <>, trades <>
- Monte Carlo: <N simulations>, Sharpe p-value <>, drawdown p-value <>
- Walk-forward: <window count>, profitable windows <>, consistency rate <>
- Comparison: <better/worse/different from current best, and why>
- Decision: discard | replicate | vary | candidate
- Next useful test: <one concrete untested hypothesis>
- Notes/errors: <include failures honestly>
-->
