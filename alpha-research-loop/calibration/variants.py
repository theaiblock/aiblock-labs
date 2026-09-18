"""Hand-written signals scored before any model runs: does the engine rank a known-good and a known-bad
change the way the power check did? Dev window only."""
import numpy as np
import pandas as pd

BENCHMARK = """
import pandas as pd
def signal(close, volume, universe):
    up = close / close.shift(28) - 1 > 0
    n = universe.sum(axis=1)
    return (up & universe).astype(float).div(n, axis=0).fillna(0.0)
"""
GOOD_IVOL = """
import pandas as pd
def signal(close, volume, universe):
    up = close / close.shift(28) - 1 > 0
    vol = close.pct_change(fill_method=None).rolling(30, min_periods=20).std()
    inv = (1 / vol).where(universe)
    w = inv.where(up).div(inv.sum(axis=1), axis=0)
    return w.fillna(0.0)
"""
GOOD_IVOL60 = GOOD_IVOL.replace("rolling(30, min_periods=20)", "rolling(60, min_periods=40)")
GOOD_VOLTARGET = """
import numpy as np
import pandas as pd
def signal(close, volume, universe):
    up = close / close.shift(28) - 1 > 0
    vol = close.pct_change(fill_method=None).rolling(30, min_periods=20).std() * np.sqrt(365)
    raw = (0.5 / vol).clip(upper=1.0).where(up & universe)
    n = universe.sum(axis=1)
    return raw.div(n, axis=0).fillna(0.0)
"""
BAD_WINNERS = """
import pandas as pd
def signal(close, volume, universe):
    r7 = (close / close.shift(7) - 1).where(universe)
    top = r7.rank(axis=1, ascending=False, method="first") <= 20
    return (top & universe).astype(float) / 20
"""
BAD_WINNERS_1D = BAD_WINNERS.replace("shift(7)", "shift(1)")
VARIANTS = {"benchmark": BENCHMARK, "good: inverse-vol 30d": GOOD_IVOL, "good: inverse-vol 60d": GOOD_IVOL60,
            "good: vol target": GOOD_VOLTARGET, "bad: last week's top 20": BAD_WINNERS,
            "bad: yesterday's top 20": BAD_WINNERS_1D}

def main():
    import sys, time
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[1]))
    import engine
    t0 = time.time()
    data = engine.load()
    print(f"data {data.close.shape}, load {time.time()-t0:.1f}s")
    for name, src in VARIANTS.items():
        t = time.time()
        errors, w = engine.validate(src, data)
        if errors:
            print(name, errors); continue
        s = engine.score(w, data)
        print(f"{name:26} SR {s['sharpe']:.2f} ann {s['annual_return']:7.1%} DD {s['max_drawdown']:5.0%} "
              f"exp {s['exposure']:.0%} held {s['coins_held']:.0f} turn {s['turnover_week']:.2f} fees/yr {s['fees_per_year']:.1%} "
              f"({time.time()-t:.0f}s)  years {dict((k, round(v, 2)) for k, v in s['years'].items())}")


def paired_table():
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[1]))
    import engine, stats
    data = engine.load()
    res = {}
    for name, src in VARIANTS.items():
        _, w = engine.validate(src, data)
        res[name] = pd.Series(engine.score(w, data)["daily_returns"])
    for name, r in res.items():
        if name != "benchmark":
            p = stats.paired(r, res["benchmark"])
            print(f"{name:26} ΔSR {p['delta_sharpe']:+.2f}  CI [{p['ci_low']:+.2f}, {p['ci_high']:+.2f}]  {p['verdict']}")


if __name__ == "__main__":
    main()
    paired_table()
