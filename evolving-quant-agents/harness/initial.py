"""Seed strategy — the program ShinkaEvolve evolves.

Only the code between EVOLVE-BLOCK-START/END mutates. The causal helpers above the block
are fixed utilities (kept in this file so every evolved copy is self-contained — the eval
subprocess imports this file directly, so no external imports must be relied on).

The seed is a CONVENTIONAL, un-tuned dual rule: the golden/death cross (SMA50 vs SMA200)
gated by ~90-day momentum. The 50/200/90 windows and the thresholds are the standard
textbook values on purpose — we did NOT optimize them; the agent's job is to evolve them.

Contract for `signal(ohlcv)` (READ THIS, it is the editable region below):
  * Input `ohlcv`: dict of 1-D float arrays 'open','high','low','close','volume'. Price +
    volume ONLY — no other data exists.
  * Return: a 1-D array, one target position per bar in [-1, 1] (long/flat/short), same
    length as close.
  * The evaluator shifts positions forward one bar (a decision on close[t] earns the return
    t -> t+1) and enforces it — do NOT index future bars here.
  * Use the causal helpers (_sma, _shift, _momentum) or write your own, but keep them causal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _sma(x: np.ndarray, n: int) -> np.ndarray:
    """Causal trailing simple moving average; leading (n-1) values are NaN."""
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def _shift(x: np.ndarray, n: int) -> np.ndarray:
    """Shift forward by n bars (past values); leading n values NaN. No future peeking."""
    return pd.Series(x).shift(n).to_numpy()


def _momentum(x: np.ndarray, n: int) -> np.ndarray:
    """Trailing n-bar return."""
    return x / _shift(x, n) - 1.0


# EVOLVE-BLOCK-START
def signal(ohlcv):
    close = ohlcv["close"]
    sma50 = _sma(close, 50)
    sma200 = _sma(close, 200)
    mom90 = _momentum(close, 90)
    trend = sma50 > sma200                        # golden cross
    momo = mom90 > 0.0                            # positive 90-day momentum
    return np.where(trend & momo, 1.0, 0.0)       # long only when both agree
# EVOLVE-BLOCK-END
