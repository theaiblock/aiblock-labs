#!/usr/bin/env python3
"""The one deterministic harness — runs every strategy + baseline through identical
config (same data, fees, split) so the comparison is apples-to-apples.

Outputs:
  results.json                 — every metric, every market/strategy/scenario
  charts/specs/*.json          — branded chart specs (render with viz/)
Prints a clean scorecard.

    .venv/bin/python experiments/004_claude_hyperliquid_backtest/backtest.py
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from backtesting import Backtest

import strategies as S
import baselines as B

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent
DATA = HERE / "data"
SPECS = HERE / "charts" / "specs"
MARKETS = ["BTC", "ETH"]

# --- cost model -------------------------------------------------------------
# Hyperliquid taker fee ~0.045%/side. Slippage added as extra per-side cost.
# Funding is NOT modeled (long/flat on a price series) -> stated as a caveat.
TAKER = 0.00045
FEE_SCENARIOS = {            # per-side commission (entry and exit each)
    "gross": 0.0,                       # no costs at all
    "fee_only": TAKER,                  # exchange fee, no slippage
    "realistic": TAKER + 0.0002,        # fee + 2 bps slippage  (HEADLINE)
    "harsh": TAKER + 0.0005,            # fee + 5 bps slippage
}
HEADLINE = "realistic"
TRAIN_FRAC = 0.70
RANDOM_SEEDS = 200
START_CASH = 1_000_000


def load(market):
    df = pd.read_parquet(DATA / f"{market}_1h.parquet")
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"}).set_index("datetime")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def run(df, strat, commission, **params):
    bt = Backtest(df, strat, cash=START_CASH, commission=commission, trade_on_close=False)
    return bt.run(**params)


def metrics(stats):
    return {
        "return_pct": float(stats["Return [%]"]),
        "trades": int(stats["# Trades"]),
        "max_dd_pct": float(stats["Max. Drawdown [%]"]),
        "win_rate_pct": float(stats["Win Rate [%]"]) if stats["# Trades"] else float("nan"),
        "exposure_pct": float(stats["Exposure Time [%]"]),
        "sharpe": float(stats["Sharpe Ratio"]),
    }


def equity_norm(stats, n_points=210):
    eq = stats["_equity_curve"]["Equity"]
    eq = eq / eq.iloc[0] * 100.0
    step = max(1, len(eq) // n_points)
    eq = eq.iloc[::step]
    return eq


def main():
    SPECS.mkdir(parents=True, exist_ok=True)
    results = {"cost_model": FEE_SCENARIOS, "headline_scenario": HEADLINE,
               "train_frac": TRAIN_FRAC, "random_seeds": RANDOM_SEEDS, "markets": {}}

    named = {**S.STRATEGIES, "buy_hold": B.BuyHold, "sma_cross": B.SMACross}
    claude = list(S.STRATEGIES)

    for mkt in MARKETS:
        df = load(mkt)
        split = int(len(df) * TRAIN_FRAC)
        df_train, df_test = df.iloc[:split], df.iloc[split:]
        mres = {}

        # --- named strategies + baselines, all fee scenarios + train/test ---
        equity_curves = {}
        for name, strat in named.items():
            row = {"net": {}}
            for sc, comm in FEE_SCENARIOS.items():
                st = run(df, strat, comm)
                row["net"][sc] = metrics(st)
                if sc == HEADLINE:
                    row.update(metrics(st))
                    equity_curves[name] = equity_norm(st)
            # train / test at headline costs
            row["train"] = metrics(run(df_train, strat, FEE_SCENARIOS[HEADLINE]))
            row["test"] = metrics(run(df_test, strat, FEE_SCENARIOS[HEADLINE]))
            mres[name] = row

        # --- random Monte-Carlo cloud, matched to the Claude strategies ------
        exp = np.mean([mres[c]["exposure_pct"] for c in claude]) / 100.0
        trades = np.mean([mres[c]["trades"] for c in claude])
        mean_hold = (exp * len(df)) / max(trades, 1.0)
        rnd = []
        for seed in range(RANDOM_SEEDS):
            sig = B.random_signal(len(df), exp, mean_hold, seed)
            d2 = df.copy()
            d2["LongSig"] = sig
            st = run(d2, B.FollowSignal, FEE_SCENARIOS[HEADLINE])
            rnd.append(float(st["Return [%]"]))
        rnd = np.array(rnd)
        # percentile rank of best claude strategy vs the random cloud
        best_claude = max(claude, key=lambda c: mres[c]["return_pct"])
        best_ret = mres[best_claude]["return_pct"]
        pct_rank = float((rnd < best_ret).mean() * 100)
        mres["_random"] = {
            "exposure_target_pct": exp * 100, "mean_hold_bars": mean_hold,
            "mean": float(rnd.mean()), "p5": float(np.percentile(rnd, 5)),
            "p50": float(np.percentile(rnd, 50)), "p95": float(np.percentile(rnd, 95)),
            "best_claude": best_claude, "best_claude_return": best_ret,
            "best_claude_percentile_vs_random": pct_rank,
        }
        results["markets"][mkt] = mres
        _emit_specs(mkt, mres, equity_curves, best_claude, rnd)

    (HERE / "results.json").write_text(json.dumps(results, indent=2))
    _print_scorecard(results)
    print(f"\nresults -> {HERE/'results.json'}\nspecs   -> {SPECS}")


# --- chart specs ------------------------------------------------------------
LABELS = {"donchian_breakout": "Donchian breakout", "rsi2_reversion": "RSI(2) reversion",
          "macd_momentum": "MACD momentum", "buy_hold": "Buy & hold",
          "sma_cross": "SMA 50/200", "_randmean": "Random (avg)"}


def _emit_specs(mkt, mres, equity_curves, best_claude, rnd):
    order = ["donchian_breakout", "rsi2_reversion", "macd_momentum", "sma_cross", "buy_hold"]
    # 1. scorecard: net return of all approaches (+ random mean), best highlighted
    rows = [(LABELS[k], mres[k]["return_pct"]) for k in order]
    rows.append((LABELS["_randmean"], float(rnd.mean())))
    rows.sort(key=lambda r: r[1], reverse=True)
    best_val = max(r[1] for r in rows)
    _write(f"scorecard_{mkt.lower()}", {
        "type": "hbar",
        "title": f"{mkt}: did any bot actually beat the baselines?",
        "subtitle": f"net return after realistic fees + slippage, {mkt} 1h, ~208 days (a down market)",
        "x": [r[0] for r in rows],
        "series": [{"name": "net return", "data": [round(r[1], 1) for r in rows]}],
        "valueFormat": "pct",
        "highlightIndex": [r[1] for r in rows].index(best_val),
        "highlightColor": "teal" if best_val > 0 else "red",
        "footer": "source: Hyperliquid 1h candles × Backtesting.py — same harness, all strategies",
    })
    # 1b. random distribution: where the best Claude bot lands in the random cloud
    lo, hi = float(rnd.min()), float(rnd.max())
    nb = 12
    edges = np.linspace(lo, hi, nb + 1)
    counts, _ = np.histogram(rnd, bins=edges)
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(nb)]
    best_ret = mres[best_claude]["return_pct"]
    _write(f"random_{mkt.lower()}", {
        "type": "stackedbar",
        "title": f"{mkt}: is the best bot better than luck?",
        "subtitle": f"net return of 200 random bots (same time-in-market) — {LABELS[best_claude]} marked",
        "x": [f"{c:.0f}%" for c in centers],
        "series": [{"name": "random bots", "data": counts.tolist()}],
        "valueFormat": "int",
        "footer": f"{LABELS[best_claude]} ({best_ret:+.1f}%) beats "
                  f"{float((rnd < best_ret).mean()*100):.0f}% of random bots — better than luck, still a loss",
    })
    # 2. equity curves: best Claude strat vs buy&hold vs SMA baseline
    pick = [best_claude, "buy_hold", "sma_cross"]
    x = [d.strftime("%Y-%m-%d") for d in equity_curves[best_claude].index]
    _write(f"equity_{mkt.lower()}", {
        "type": "line",
        "title": f"{mkt}: the best Claude bot vs the dumb baselines",
        "subtitle": "equity (start = 100), net of realistic costs",
        "x": x,
        "series": [{"name": LABELS[p], "data": [round(v, 1) for v in equity_curves[p].tolist()]}
                   for p in pick],
        "valueFormat": "int",
        "footer": "source: Hyperliquid 1h candles × Backtesting.py (event-driven, no lookahead)",
    })


def _write(name, spec):
    (SPECS / f"{name}.json").write_text(json.dumps(spec, indent=2))


def _print_scorecard(results):
    for mkt, m in results["markets"].items():
        print(f"\n=== {mkt}  (net after {results['headline_scenario']} costs) ===")
        order = ["donchian_breakout", "rsi2_reversion", "macd_momentum", "sma_cross", "buy_hold"]
        print(f"  {'strategy':22s} {'net%':>7} {'gross%':>7} {'trades':>6} {'maxDD%':>7} {'win%':>5} {'expo%':>6} {'test%':>7}")
        for k in order:
            r = m[k]
            print(f"  {LABELS[k]:22s} {r['return_pct']:7.1f} {r['net']['gross']['return_pct']:7.1f} "
                  f"{r['trades']:6d} {r['max_dd_pct']:7.1f} {r['win_rate_pct']:5.0f} "
                  f"{r['exposure_pct']:6.0f} {r['test']['return_pct']:7.1f}")
        rd = m["_random"]
        print(f"  {'Random cloud (200)':22s}  mean {rd['mean']:.1f}%  p5..p95 [{rd['p5']:.1f}, {rd['p95']:.1f}]"
              f"  | best={LABELS[rd['best_claude']]} beats {rd['best_claude_percentile_vs_random']:.0f}% of random")


if __name__ == "__main__":
    main()
