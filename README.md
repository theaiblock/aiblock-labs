# AI Block — Labs

Open, reproducible **code** behind [AI Block](https://www.youtube.com/@theaiblock) — a
data-driven research channel about crypto AI agents: trading, payments, identity, and
on-chain automation.

The promise of the channel is the moat: **transparent, data-backed research**. Every
video is a real experiment — thesis, data, honest verdict (wins *and* blowups). This repo
holds the code so you can re-run the experiments and check the numbers yourself.

> This is **code only** — no datasets, no rendered charts, no video assets. Each project
> fetches its own public data and regenerates its own outputs when you run it.

## Disclaimer

⚠️ **For education and research only. Not financial advice. Not production-ready.**

This code exists to *measure and demonstrate* — it is not a trading product. In fact the
strategies here **lose money** in the backtest; that's the whole point of the videos. Nothing
in this repo is an investment recommendation or a signal to trade real funds.

- Backtested or past performance does **not** predict future results.
- Crypto trading carries a substantial risk of loss; you can lose everything.
- The code is provided "as is", with no warranty (see [LICENSE](./LICENSE)). It is a research
  prototype — unaudited, not hardened, and not meant for live trading as-is.
- Do your own research. Any decision you make is solely your own responsibility; the authors
  accept no liability for any loss arising from use of this code.

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
