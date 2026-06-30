# AI Block — Labs

Open, reproducible **code** behind [AI Block](https://www.youtube.com/@theaiblock) — a
data-driven research channel about crypto AI agents: trading, payments, identity, and
on-chain automation.

The promise of the channel is the moat: **transparent, data-backed research**. Every
video is a real experiment — thesis, data, honest verdict (wins *and* blowups). This repo
holds the code so you can re-run the experiments and check the numbers yourself.

> This is **code only** — no datasets, no rendered charts, no video assets. Each project
> fetches its own public data and regenerates its own outputs when you run it.

## Projects

| Folder | What it is |
|---|---|
| [`claude-hyperliquid-backtest/`](./claude-hyperliquid-backtest) | Let an LLM (Claude) write trading strategies, then judge them honestly: one deterministic, event-driven backtest on real Hyperliquid history — same data, fees, slippage, and out-of-sample split for every strategy, against dumb baselines. |

More projects land here as the channel ships them.

## Philosophy

- **One deterministic harness, every strategy, frozen before testing.** Same code + same
  cached data ⇒ the same result, forever. No live demos that can't be checked.
- **Honest costs and out-of-sample data.** A backtest only counts if it survives realistic
  fees and data the model never saw.
- **Negative results, shown straight.** A clean method and a negative result is still the
  point.

## License

MIT — see [LICENSE](./LICENSE). Use it, fork it, check our work.
