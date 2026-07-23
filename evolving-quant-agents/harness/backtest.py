"""Shared backtest core — identical engine behind BOTH evaluators.

The whole thesis rests on this being honest and being the SAME code for the naive and the
honest run: the only difference between the two is which window it scores and whether it
charges transaction costs. Everything here is deliberately plain and auditable.

Method (stated on air):
  * `signal(ohlcv)` is called per coin over the FULL history (so the 200-day SMA is warm at
    every window's start); positions are clipped to [-1, 1].
  * Lookahead is enforced by the engine, not trusted to the strategy: positions are shifted
    forward one bar, so a decision on close[t] earns the return t -> t+1.
  * Portfolio = equal-weight mean across coins that have data that bar (a flat coin holds
    cash on its sleeve). Cross-sectional, so no cherry-picking one asset.
  * Transaction cost = fee_bps per side on turnover |Δposition| (10 bps honest, 0 naive).
  * Metric = annualized Sharpe (crypto trades 365 d/yr). combined_score = Sharpe, finite-guarded.
    No hand-tuned penalties — "we just used Sharpe."
"""
from __future__ import annotations

import importlib.util
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ohlcv.parquet"
FIELDS = ["open", "high", "low", "close", "volume"]
FEE_BPS = 10.0  # honest evaluator, per side; naive uses 0

# Contiguous train / validation / sealed-test split (constrained-factor-paper discipline).
# Signals are computed over ALL history; a window only slices the SCORING period.
WINDOWS = {
    "naive_full": ("2021-07-01", "2026-07-20"),  # naive: score everything, no split
    "train": ("2022-07-01", "2024-12-31"),
    "val": ("2025-01-01", "2025-09-30"),          # honest combined_score = Sharpe here
    "test": ("2025-10-01", "2026-07-20"),          # SEALED — opened once on the champion
}

# Best-effort source scan: block filesystem/network/exec and obvious future-peeking. Not a
# sandbox — a determined program could still cheat; the 1-bar shift + val-only fitness are the
# real protections. Documented as a caveat.
_DENY = [
    "import os", "import sys", "import subprocess", "import requests", "import socket",
    "import urllib", "import pickle", "open(", "eval(", "exec(", "__import__",
    "read_parquet", "read_csv", "[::-1]", "shift(-", "center=true",
]


class SourceViolation(Exception):
    pass


def scan_source(src: str) -> str | None:
    low = src.lower()
    for token in _DENY:
        if token in low:
            return f"blocked pattern in evolved source: {token!r}"
    return None


def load_signal(program_path: str):
    src = Path(program_path).read_text(encoding="utf-8")
    viol = scan_source(src)
    if viol:
        raise SourceViolation(viol)
    spec = importlib.util.spec_from_file_location("evolved_program", program_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {program_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "signal", None)
    if not callable(fn):
        raise AttributeError("evolved program has no callable signal(ohlcv)")
    return fn


def load_panel() -> dict:
    df = pd.read_parquet(DATA_PATH)
    return {f: df.pivot(index="date", columns="symbol", values=f).sort_index() for f in FIELDS}


def _positions(signal_fn, panel: dict) -> pd.DataFrame:
    close = panel["close"]
    dates, syms = close.index, close.columns
    pos = pd.DataFrame(index=dates, columns=syms, dtype=float)
    for s in syms:
        ohlcv = {f: panel[f][s].to_numpy(dtype=float) for f in FIELDS}
        raw = np.asarray(signal_fn(ohlcv), dtype=float).reshape(-1)
        if raw.shape[0] != len(dates):
            raise ValueError(f"signal returned length {raw.shape[0]} != {len(dates)} for {s}")
        pos[s] = np.clip(np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)
    return pos


def _portfolio(signal_fn, panel: dict, fee_bps: float):
    close = panel["close"]
    pos = _positions(signal_fn, panel)
    shifted = pos.shift(1)                       # decide on close[t], hold over t->t+1
    ret = close.pct_change()
    mask = ret.notna() & shifted.notna()         # a coin contributes only with a real return
    strat = shifted * ret
    dpos = shifted.diff().abs()
    cost = (fee_bps / 1e4) * dpos
    net = (strat - cost).where(mask)
    port = net.mean(axis=1, skipna=True)         # equal-weight across active coins
    turn = dpos.where(mask).mean(axis=1, skipna=True)
    inmkt = (shifted.abs() > 0).where(mask).mean(axis=1, skipna=True)
    return port, turn, inmkt


def _metrics(port, turn, inmkt, window) -> dict:
    start, end = window
    w = port.loc[start:end].dropna()
    n = int(len(w))
    if n < 5:
        return {"sharpe": float("nan"), "n_days": n, "insufficient": True}
    mu, sd = float(w.mean()), float(w.std(ddof=1))
    sharpe = mu / sd * math.sqrt(365) if (sd > 0 and math.isfinite(sd)) else float("nan")
    cum = (1.0 + w).cumprod()
    max_dd = float((cum / cum.cummax() - 1.0).min())
    total_return = float(cum.iloc[-1] - 1.0)
    years = n / 365.0
    tw = turn.loc[start:end].dropna()
    ann_turnover = float(tw.sum() / years) if years > 0 else float("nan")
    pct_in_market = float(inmkt.loc[start:end].mean())
    return {
        "sharpe": round(sharpe, 4) if math.isfinite(sharpe) else float("nan"),
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd, 4),
        "ann_turnover": round(ann_turnover, 3),
        "pct_in_market": round(pct_in_market, 3),
        "n_days": n,
    }


def run_backtest(signal_fn, panel: dict, window, fee_bps: float) -> dict:
    """Score one window at one fee. Returns a metrics dict (Sharpe etc.)."""
    port, turn, inmkt = _portfolio(signal_fn, panel, fee_bps)
    return _metrics(port, turn, inmkt, window)


def run_all_windows(signal_fn, panel: dict, fee_bps: float) -> dict:
    """Score train/val/test in one portfolio pass (for score_champion / findings)."""
    port, turn, inmkt = _portfolio(signal_fn, panel, fee_bps)
    return {name: _metrics(port, turn, inmkt, WINDOWS[name]) for name in ("train", "val", "test")}


def combined_score_from(metrics: dict) -> float:
    s = metrics.get("sharpe", float("nan"))
    return float(s) if isinstance(s, (int, float)) and math.isfinite(s) else -10.0
