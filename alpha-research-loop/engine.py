"""The locked engine. Candidates write signal(close, volume, universe); everything else lives here.

Weekly rebalance on a point-in-time universe of the 100 most-traded Binance coins. The signal returns
target weights; the engine trades them at the next close, charges liquidity-tiered fees and marks the
book daily with vectorbt. Two windows: `dev` (everything the loop sees) and `sealed` (opened once)."""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
DATA = Path(os.environ.get("ALPHA_DATA_DIR", ROOT / "data"))  # fetch_data.py writes here
WINDOWS = {"dev": ("2021-01-01", "2025-08-31"), "sealed": ("2025-09-01", "2026-08-31")}
DEV_END = WINDOWS["dev"][1]
FIRST_ROW = "2020-01-01"            # history available to signals before the first scored day
ANCHOR, REBALANCE = pd.Timestamp("2021-01-01"), 7   # decide every 7th day from the anchor
TOP_N, MIN_VOLUME, MIN_HISTORY, VOLUME_WINDOW = 100, 2e6, 60, 30
MAX_WEIGHT = 0.10                   # per coin; anything above is left in cash
FEE_TIERS = ((20, 0.001), (50, 0.002))  # volume rank <= 20: 10bp, <= 50: 20bp, else 40bp
FEE_OTHER = 0.004
YEAR = 365
ALLOWED_IMPORTS = {"numpy", "pandas", "math"}
BANNED_NAMES = {"open", "eval", "exec", "compile", "__import__", "input", "globals", "locals", "vars", "breakpoint"}


@dataclass
class Data:
    close: pd.DataFrame     # daily close in USDT, NaN when not trading
    volume: pd.DataFrame    # daily USDT volume
    universe: pd.DataFrame  # True where the coin is tradable that day (point-in-time)
    avg_volume: pd.DataFrame

    def upto(self, end) -> "Data":
        return Data(*(getattr(self, f).loc[:end] for f in ("close", "volume", "universe", "avg_volume")))


def build_universe(close: pd.DataFrame, volume: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each day: trading, >= 60 days of closes, 30-day average volume >= $2M, top 100 by that average.
    Uses only data up to that day."""
    avg = volume.rolling(VOLUME_WINDOW, min_periods=20).mean()
    eligible = close.notna() & (close.notna().cumsum() >= MIN_HISTORY) & (avg >= MIN_VOLUME)
    rank = avg.where(eligible).rank(axis=1, ascending=False, method="first")
    return eligible & (rank <= TOP_N), avg


def load(end: str | None = DEV_END) -> Data:
    """Data to `end` (default: the end of the dev window). `end=None` includes the sealed year."""
    close = pd.read_csv(DATA / "close.csv.gz", index_col=0, parse_dates=True)
    volume = pd.read_csv(DATA / "volume.csv.gz", index_col=0, parse_dates=True)
    if end:
        close, volume = close.loc[:end], volume.loc[:end]
    universe, avg = build_universe(close, volume)
    rows = close.index >= FIRST_ROW
    ever = universe.loc[rows].any()  # coins that are never tradable are dropped
    cols = ever[ever].index
    return Data(close.loc[rows, cols], volume.loc[rows, cols].fillna(0.0), universe.loc[rows, cols], avg.loc[rows, cols])


# --- validation --------------------------------------------------------------------------------

def static_check(source: str) -> list[str]:
    errors = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax error: {exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [(node.module or "").split(".")[0]]
        else:
            mods = []
        errors += [f"import not allowed: {m}" for m in mods if m not in ALLOWED_IMPORTS]
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            errors.append(f"name not allowed: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            errors.append(f"dunder attribute not allowed: {node.attr}")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "signal" for n in tree.body):
        errors.append("no top-level function named signal")
    return errors


def load_signal(source: str):
    namespace: dict = {}
    exec(compile(source, "candidate.py", "exec"), namespace)  # only after static_check passed
    return namespace["signal"]


def run_signal(fn, data: Data) -> pd.DataFrame:
    return fn(data.close.copy(), data.volume.copy(), data.universe.copy())


def check_output(w, data: Data) -> list[str]:
    if not isinstance(w, pd.DataFrame):
        return [f"signal must return a DataFrame, got {type(w).__name__}"]
    errors = []
    if not w.index.equals(data.close.index):
        errors.append("index differs from close.index")
    if list(w.columns) != list(data.close.columns):
        errors.append("columns differ from close.columns")
    if errors:
        return errors
    v = w.to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(v).any():
        return ["contains inf"]
    v = np.nan_to_num(v)
    if v.min() < -1e-9:
        errors.append(f"negative weight {v.min():.4g} (long-only)")
    sums = v.sum(axis=1)
    if sums.max() > 1 + 1e-6:
        day = data.close.index[int(sums.argmax())].date()
        errors.append(f"weights sum to {sums.max():.4f} on {day}; a day's weights must sum to at most 1")
    outside = (v > 1e-9) & ~data.universe.to_numpy()
    if outside.any():
        r, c = np.argwhere(outside)[0]
        errors.append(f"{int(outside.sum())} weights on coins outside the universe, first {data.close.columns[c]} "
                      f"on {data.close.index[r].date()}; weight must be 0 where universe is False")
    return errors


def lookahead_check(fn, data: Data, cuts=(0.5, 0.75, 0.9)) -> list[str]:
    """Weights up to a date must not change when later data is removed."""
    full = run_signal(fn, data).astype(float).fillna(0.0)
    errors = []
    for frac in cuts:
        cut = data.close.index[int(len(data.close) * frac)]
        part = run_signal(fn, data.upto(cut)).astype(float).fillna(0.0)
        diff = (full.loc[:cut] - part).abs()
        if (diff > 1e-9).to_numpy().any():
            first = diff[(diff > 1e-9).any(axis=1)].index[0]
            errors.append(f"look-ahead: weights on {first.date()} change when data after {cut.date()} is removed")
    return errors


def validate(source: str, data: Data) -> tuple[list[str], object]:
    """All checks a candidate must pass. Returns (errors, weights)."""
    errors = static_check(source)
    if errors:
        return errors, None
    try:
        fn = load_signal(source)
        w = run_signal(fn, data)
    except Exception as exc:
        return [f"signal raised {type(exc).__name__}: {exc}"], None
    errors = check_output(w, data)
    if errors:
        return errors, None
    try:
        errors = lookahead_check(fn, data)
    except Exception as exc:
        errors = [f"signal raised on truncated data {type(exc).__name__}: {exc}"]
    return errors, w.astype(float).fillna(0.0)


# --- scoring -----------------------------------------------------------------------------------

def schedule(index: pd.DatetimeIndex, window: str) -> tuple[pd.DatetimeIndex, list, list]:
    start, end = (pd.Timestamp(x) for x in WINDOWS[window])
    days = index[(index >= start) & (index <= end)]
    decide = [d for d in days if (d - ANCHOR).days % REBALANCE == 0 and d < end]
    trade = [index[index.get_loc(d) + 1] for d in decide]
    return days, decide, trade


def fees_for(data: Data, decide) -> np.ndarray:
    rank = data.avg_volume.loc[decide].where(data.universe.loc[decide]).rank(axis=1, ascending=False, method="first")
    r = rank.to_numpy()
    return np.select([r <= FEE_TIERS[0][0], r <= FEE_TIERS[1][0]], [FEE_TIERS[0][1], FEE_TIERS[1][1]], FEE_OTHER)


def score(w: pd.DataFrame, data: Data, window: str = "dev") -> dict:
    os.environ.setdefault("NUMBA_CACHE_DIR", str(ROOT / ".numba_cache"))
    import vectorbt as vbt

    if data.close.index[-1] < pd.Timestamp(WINDOWS[window][1]):
        raise ValueError(f"data ends {data.close.index[-1].date()}, before the {window} window; load(end=None)")
    days, decide, trade = schedule(data.close.index, window)
    close = data.close.loc[:days[-1]]
    target = w.reindex_like(close).fillna(0.0).clip(0, MAX_WEIGHT).loc[decide].to_numpy()
    tradable = close.loc[trade].notna().to_numpy()
    target = np.where(tradable, target, 0.0)  # nothing to buy at; a delisted holding is sold at its last close

    size = pd.DataFrame(np.nan, days, close.columns)
    size.loc[trade] = target
    fees = pd.DataFrame(0.0, days, close.columns)
    fees.loc[trade] = fees_for(data, decide)
    # mark-to-market price: last close carried forward; before listing, the first close (never held there)
    price = close.ffill().loc[days].bfill()
    pf = vbt.Portfolio.from_orders(price, size, size_type="targetpercent", group_by=True, cash_sharing=True,
                                   call_seq="auto", fees=fees, freq="1D", init_cash=1.0)
    r = pf.returns()
    value = pf.value()
    sharpe = lambda x: float(x.mean() / x.std() * np.sqrt(YEAR)) if x.std() > 0 else 0.0
    weekly_target = pd.DataFrame(target, trade, close.columns)
    return {
        "window": window, "period": [str(days[0].date()), str(days[-1].date())],
        "sharpe": sharpe(r),
        "annual_return": float(pf.annualized_return()),
        "max_drawdown": float(pf.max_drawdown()),
        "exposure": float((pf.asset_value() / value).mean()),
        "coins_held": float((weekly_target > 0).sum(axis=1).mean()),
        "turnover_week": float(weekly_target.diff().abs().sum(axis=1).iloc[1:].mean()),
        "fees_per_year": float(pf.orders.fees.sum() / value.mean() * YEAR / len(days)),
        "years": {str(y): sharpe(g) for y, g in r.groupby(r.index.year)},
        "year_returns": {str(y): float((1 + g).prod() - 1) for y, g in r.groupby(r.index.year)},
        "daily_returns": {d.date().isoformat(): float(v) for d, v in r.items()},
    }
