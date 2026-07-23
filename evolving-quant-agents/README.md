# Evolving quant agents — can an LLM evolve a trading strategy?

An AI agent that writes a trading strategy, backtests it, reads its own score, and rewrites
its own code to do better — over and over. This is the full harness behind that experiment,
run on a Claude subscription with **no per-token API bill**.

The whole point of the lab: **the search loop is a commodity; the evaluator is the research.**
So we changed exactly one thing between two otherwise identical runs — the scoreboard the
agent was scored on — and measured what that alone did to the result.

## What we found

Same agent, same seed, same 30 coins, same engine. Only the scoreboard differed.

| Strategy | In-sample Sharpe (0 cost) | Validation | **Sealed test Sharpe** | Test total return |
|---|---:|---:|---:|---:|
| **Seed** (un-tuned 50/200 golden cross + 90d momentum) | — | −0.70 | **−1.19** | −15.1% |
| **Champion-Naive** (evolved on in-sample Sharpe, no fees) | **0.90** | 0.53 | **0.23** | +0.1% |
| **Champion-Honest** (evolved on validation Sharpe after fees) | — | −0.14 | **0.60** | +0.4% |

Sealed test = 2025-10 → 2026-07, opened once, after the champions were final. 10 bps per side.

Three things worth stating plainly:

1. **The mechanism is real.** From a trivial golden cross the agent evolved genuine machinery
   — multi-timeframe EMA-slope consensus, a Donchian channel, volatility targeting, a
   drawdown brake, turnover smoothing. All written by the model.
2. **The good-looking number didn't survive.** 0.90 in-sample became 0.23 on data it had
   never seen. And that 0.90 was itself ~6.5% total return over ~4 years — the search learned
   to raise a *ratio* by cutting risk, not by earning more.
3. **Nobody found edge.** Test-period returns of +0.1% and +0.4% over ten months are flat.
   On price and volume alone, evolving harder did not find alpha. Both champions sit on very
   little risk, so treat the gap between them as directional, not as proof.

That last point is a statement about **one configuration**, not about the method: one seed,
one framework, daily bars, price and volume only, ten generations — and the search hit its
best program at generation four. Change any of those and you're somewhere nobody has looked.

## Reproduce it

```bash
pip install -r requirements.txt

# 1. Fetch the data (Binance public REST, no API key). Writes data/ohlcv.parquet
python fetch.py

# 2. Score the seed and both champions on the sealed test set
python harness/score_champion.py --program harness/initial.py       --label "Seed"
python harness/score_champion.py --program champions/champion_naive.py  --label "Champion-Naive" --naive
python harness/score_champion.py --program champions/champion_honest.py --label "Champion-Honest"
```

That reproduces every number in the table above without running an LLM.

To run the evolution yourself (needs ShinkaEvolve — see `RUNNING_SHINKA.md`):

```bash
python run_evolve.py --mode naive  --generations 10   # the open-book scoreboard
python run_evolve.py --mode honest --generations 10   # the closed-book scoreboard
python resume.py --target 10                          # resume after a subscription limit
```

## The two evaluators (this is the interesting part)

Both call the **same** `harness/backtest.py`. The only differences are which window they score
and whether they charge costs:

| | `evaluate_naive.py` | `evaluate_honest.py` |
|---|---|---|
| Scored on | the **whole** history — same bars it learned from | a **validation** window held out of training |
| Transaction costs | none | 10 bps per side |
| Sealed test | never used during the search | never used during the search |
| What it rewards | fitting the past | generalizing past the training window |

`combined_score` is what the search maximizes. The naive evaluator is a faithful reproduction
of the default in the one off-the-shelf trading-evolution project we could find: in-sample
Sharpe over the entire dataset, no split, no fees. It's the foil, not a straw man.

## Method, and where it can be wrong

- **Universe:** ~30 liquid USDT pairs, daily bars. **Survivorship-biased on purpose** — it's
  today's liquid list applied to the past. Real alpha claims would need a point-in-time universe.
- **No lookahead:** the evaluator shifts positions forward one bar (a decision on `close[t]`
  earns the `t → t+1` return) and enforces it; `backtest.py` also rejects a handful of
  peeking patterns in the evolved source.
- **Costs:** flat 10 bps/side. No slippage model, no market impact, no funding.
- **Low-exposure Sharpes are noisy.** Both champions drifted to near-cash. A Sharpe computed
  on very little risk is a noisy statistic — directional, not precise.
- **One run per scoreboard, one seed.** No repeated seeds, no confidence intervals. Treat the
  naive-vs-honest gap as an illustration of the mechanism, not as a measured effect size.
- **Ten generations is a short search.** The best program appeared at generation four.

## Layout

```
fetch.py                     Binance daily OHLCV -> data/ohlcv.parquet (the only data dependency)
run_evolve.py                drives ShinkaEvolve against ONE evaluator (--mode naive|honest)
resume.py                    resumes a run after the Claude subscription limit stops it
harness/
  backtest.py                the shared engine — position shift, costs, metrics, anti-lookahead
  initial.py                 the seed strategy the agent starts from (untuned on purpose)
  evaluate_naive.py          open-book scoreboard: in-sample Sharpe, zero costs
  evaluate_honest.py         closed-book scoreboard: validation Sharpe after costs
  score_champion.py          opens the sealed test set once and prints the scorecard
champions/
  champion_naive.py          what the open-book run produced
  champion_honest.py         what the closed-book run produced
```

`data/` and `runs/` are gitignored: both regenerate, and the run directory is a few megabytes
of logs, model responses and a population database.

The champion files are the **actual evolved artifacts**: the strategy code between the
`EVOLVE-BLOCK` markers is exactly what the agent wrote, untouched. The only edits anywhere in
this folder are to docstrings — internal file paths and naming normalized for publication.
No logic, parameter or metric was changed, which is why a fresh clone reproduces the table
above to the digit.

## Not financial advice

None of these strategies made money. This is a method, not a product. Research and education
only.
