#!/usr/bin/env python3
"""The curve-fit trap — the video's HOOK and the harness's villain.

We deliberately OVERFIT a tunable EMA-cross by grid-searching its parameters to maximize
return on the data, so it beats buy-and-hold in a down market. Then the harness exposes it:
optimize on the TRAIN half only, run those frozen params on the TEST half -> it collapses.

This is shown ON SCREEN, labeled as overfitting. It is NOT presented as a real edge — it's
the cautionary demo that proves why the train/test split and baselines exist.

    .venv/bin/python experiments/004_claude_hyperliquid_backtest/overfit.py
"""
import json
import warnings
from pathlib import Path

import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent
DATA = HERE / "data"
SPECS = HERE / "charts" / "specs"
COMMISSION = 0.00045 + 0.0002      # realistic: taker + 2bps slippage (same as headline)
TRAIN_FRAC = 0.70
START_CASH = 1_000_000

GRID = dict(
    fast=[3, 4, 5, 6, 7, 8, 10, 12, 15, 18, 21, 25, 30],
    slow=[20, 25, 30, 35, 40, 50, 60, 80, 100, 120, 150, 200],
    trend=[100, 150, 200, 250],
    use_trend=[0, 1],
)


def _ema(arr, n):
    return pd.Series(arr).ewm(span=n, adjust=False).mean().to_numpy()


class TunableEMA(Strategy):
    fast = 10
    slow = 50
    trend = 200
    use_trend = 1

    def init(self):
        self.ef = self.I(_ema, self.data.Close, self.fast, name="ef")
        self.es = self.I(_ema, self.data.Close, self.slow, name="es")
        self.et = self.I(_ema, self.data.Close, self.trend, name="et")

    def next(self):
        up = self.ef[-1] > self.es[-1]
        trend_ok = (self.data.Close[-1] > self.et[-1]) if self.use_trend else True
        if not self.position and crossover(self.ef, self.es) and trend_ok:
            self.buy(size=0.999)
        elif self.position and crossover(self.es, self.ef):
            self.position.close()


def load(market):
    df = pd.read_parquet(DATA / f"{market}_1h.parquet")
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"}).set_index("datetime")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def optimize(df):
    bt = Backtest(df, TunableEMA, cash=START_CASH, commission=COMMISSION, trade_on_close=False)
    stats = bt.optimize(maximize="Return [%]", constraint=lambda p: p.fast < p.slow, **GRID)
    s = stats._strategy
    params = {"fast": int(s.fast), "slow": int(s.slow), "trend": int(s.trend),
              "use_trend": int(s.use_trend)}
    return params, stats


def run_fixed(df, params):
    bt = Backtest(df, TunableEMA, cash=START_CASH, commission=COMMISSION, trade_on_close=False)
    return bt.run(**params)


def equity_norm(stats, n=210):
    eq = stats["_equity_curve"]["Equity"]
    eq = eq / eq.iloc[0] * 100.0
    return eq.iloc[::max(1, len(eq) // n)]


def main():
    SPECS.mkdir(parents=True, exist_ok=True)
    out = {"commission": COMMISSION, "grid": GRID, "markets": {}}

    for mkt in ["BTC", "ETH"]:
        df = load(mkt)
        split = int(len(df) * TRAIN_FRAC)
        df_train, df_test = df.iloc[:split], df.iloc[split:]

        # 1) THE HOOK: overfit on the FULL window -> dazzling number
        full_params, full_stats = optimize(df)
        hook_ret = float(full_stats["Return [%]"])

        # 2) THE REVEAL: fit on TRAIN only, run frozen on TEST -> collapse
        train_params, train_stats = optimize(df_train)
        test_stats = run_fixed(df_test, train_params)
        train_ret = float(train_stats["Return [%]"])
        test_ret = float(test_stats["Return [%]"])

        # buy & hold over the same windows (just the price change)
        bh_full = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
        bh_test = (df_test["Close"].iloc[-1] / df_test["Close"].iloc[0] - 1) * 100

        out["markets"][mkt] = {
            "hook_overfit_full": {"params": full_params, "return_pct": hook_ret,
                                  "buy_hold_pct": bh_full},
            "honest_walk_forward": {"train_params": train_params,
                                    "train_return_pct": train_ret,
                                    "test_return_pct": test_ret,
                                    "test_buy_hold_pct": float(bh_test)},
        }
        print(f"\n=== {mkt} ===")
        print(f"  HOOK   overfit-on-full: {hook_ret:+.1f}%   (buy&hold {bh_full:+.1f}%)   params={full_params}")
        print(f"  REVEAL train {train_ret:+.1f}%  ->  TEST {test_ret:+.1f}%   (test buy&hold {bh_test:+.1f}%)   train_params={train_params}")

        _emit_equity_chart(mkt, df, full_params, hook_ret, bh_full)
        _emit_reveal_chart(mkt, out["markets"][mkt])

    (HERE / "overfit_results.json").write_text(json.dumps(out, indent=2))
    print(f"\nresults -> {HERE/'overfit_results.json'}")


def _emit_equity_chart(mkt, df, params, hook_ret, bh_full):
    over = equity_norm(run_fixed(df, params))
    bh = df["Close"] / df["Close"].iloc[0] * 100.0
    bh = bh.iloc[::max(1, len(bh) // 210)]
    x = [d.strftime("%Y-%m-%d") for d in over.index]
    gap = round(hook_ret - bh_full)
    (SPECS / f"overfit_hook_{mkt.lower()}.json").write_text(json.dumps({
        "type": "line",
        "title": f"This Claude bot beat the market by {gap} points. Don't believe it.",
        "subtitle": f"overfit EMA cross vs buy & hold, {mkt} — fit on the same data it's tested on",
        "x": x,
        "series": [
            {"name": "Overfit bot", "data": [round(v, 1) for v in over.tolist()]},
            {"name": "Buy & hold", "data": [round(v, 1) for v in bh.tolist()]},
        ],
        "valueFormat": "int",
        "footer": "source: Hyperliquid 1h × Backtesting.py — parameters grid-searched to maximize return (curve-fit)",
    }, indent=2))


def _emit_reveal_chart(mkt, m):
    wf = m["honest_walk_forward"]
    (SPECS / f"overfit_reveal_{mkt.lower()}.json").write_text(json.dumps({
        "type": "hbar",
        "title": "Same bot, fit honestly: the edge vanishes",
        "subtitle": f"{mkt} — optimized on the train half, then run on data it never saw",
        "x": ["In-sample (train)", "Out-of-sample (test)"],
        "series": [{"name": "net return", "data": [round(wf["train_return_pct"], 1),
                                                   round(wf["test_return_pct"], 1)]}],
        "valueFormat": "pct",
        "highlightIndex": 1,
        "highlightColor": "red",
        "footer": "source: Hyperliquid 1h × Backtesting.py — train/test split exposes the overfit",
    }, indent=2))


if __name__ == "__main__":
    main()
