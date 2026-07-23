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
    high = ohlcv["high"]
    low = ohlcv["low"]
    n = len(close)
    # --- 1. Multi-timeframe EMA slope consensus ---
    spans = [8, 21, 55, 144]
    trend_score = np.zeros(n)
    total_weight = 0.0
    for i, sp in enumerate(spans):
        ema = pd.Series(close).ewm(span=sp).mean().to_numpy()
        ema_lag = _shift(ema, 3)
        slope = (ema - ema_lag) / np.maximum(np.abs(ema_lag), 1e-10)
        valid = ~np.isnan(slope)
        w = 1.0 / (i + 1)
        trend_score[valid] += np.tanh(slope[valid] * 150.0) * w
        total_weight += w
    trend_score /= total_weight
    # --- 2. Donchian channel position ---
    period = 20
    hh = pd.Series(high).rolling(period, min_periods=period).max().to_numpy()
    ll = pd.Series(low).rolling(period, min_periods=period).min().to_numpy()
    ch_width = hh - ll
    ch_pos = np.where(ch_width > 1e-10,
                      2.0 * (close - ll) / ch_width - 1.0,
                      0.0)
    # --- 2b. Medium-term momentum ---
    mom = _momentum(close, 60)
    mom_sig = np.tanh(np.where(np.isnan(mom), 0.0, mom) * 5.0)
    # --- 3. Combine signals & amplify ---
    raw = 0.40 * trend_score + 0.30 * ch_pos + 0.30 * mom_sig
    raw = np.tanh(raw * 2.5)
    # --- 4. Volatility targeting (~12% annualized) ---
    log_ret = np.diff(np.log(np.maximum(close, 1e-10)), prepend=0.0)
    log_ret[0] = 0.0
    ann_vol = np.sqrt(
        pd.Series(log_ret ** 2).ewm(span=21).mean().to_numpy()
    ) * np.sqrt(252)
    vol_scale = np.clip(0.18 / np.maximum(ann_vol, 0.05), 0.15, 3.5)
    pos = raw * vol_scale
    # --- 5. Drawdown brake (price-based) ---
    peak = np.maximum.accumulate(close)
    dd = close / peak - 1.0
    brake = np.clip((dd + 0.40) / 0.30, 0.0, 1.0)
    pos *= brake
    # --- 6. Smooth to control turnover & clip ---
    pos = pd.Series(pos).ewm(span=3).mean().to_numpy()
    pos = np.clip(pos, -1.0, 1.0)
    pos = np.where(np.isnan(pos), 0.0, pos)
    return pos
# EVOLVE-BLOCK-END