# Research mandate

## Objective

Find a robust momentum strategy for Bitcoin using Vibe-Trading. Iteratively try meaningfully different strategy rules and parameter combinations, learn from every run, and preserve enough evidence that another agent can continue without repeating work.

“Profitable” is a research target, not a promised outcome. Prefer a repeatable edge with defensible validation over the highest in-sample return.

## Non-negotiable constraints

- Instrument: Bitcoin (`BTC-USDT` unless Vibe-Trading requires an equivalent).
- Use at least **two full years of market data** in every scored experiment.
- Include realistic fees and slippage in the primary result. If fixed funding is used, state the assumption. Never rank a zero-cost run as the winner.
- Change one coherent hypothesis at a time. Avoid blind combinatorial explosions.
- Do not repeat a fingerprint already in `JOURNAL.md` unless `FEEDBACK.md` asks for replication.
- After the main backtest, run Vibe-Trading's Monte Carlo validation and walk-forward analysis. Monte Carlo is useful evidence, but by itself does not prove a tuned signal is not overfit.
- Treat a high return with weak validation as a lead, not a winner.
- Write every completed, failed, or blocked attempt to `JOURNAL.md` before exiting.
- Keep exact configuration, strategy code, logs, and artifacts under `runs/`.

## Search space

Agents may explore time-series momentum, moving-average rules, breakouts, volatility filters, trend-strength filters, long/flat versus long/short exposure, and rebalance frequency. Broaden the search when the journal shows repeated tuning around one local optimum.

## Evidence required before calling something a candidate

- Positive result after stated fees, slippage, and funding assumptions.
- At least two years of data.
- Exact dates, interval, rule, and parameters recorded.
- Return, Sharpe, maximum drawdown, turnover, and trade count recorded.
- Monte Carlo result recorded, including simulation count and relevant p-values, plus walk-forward consistency across time windows.
- A comparison with the current best candidate in the journal.
