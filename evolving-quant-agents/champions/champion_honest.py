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
def _trend_ensemble(close: np.ndarray) -> np.ndarray:
    """Vote across several SMA-pair horizons; each vote is a smooth tanh score in
    [-1, 1] rather than a hard boolean cross, so borderline crossings contribute
    partial conviction instead of flipping the whole signal on a single tick."""
    horizons = ((10, 40), (20, 80), (50, 150))
    votes = []
    for fast_n, slow_n in horizons:
        fast = _sma(close, fast_n)
        slow = _sma(close, slow_n)
        with np.errstate(divide="ignore", invalid="ignore"):
            strength = (fast - slow) / slow
        votes.append(np.tanh(np.nan_to_num(strength, nan=0.0) * 15.0))
    return np.mean(votes, axis=0)
def _momentum_ensemble(close: np.ndarray) -> np.ndarray:
    """Same voting idea applied to trailing returns at multiple horizons."""
    horizons = (20, 60, 120)
    votes = [np.tanh(np.nan_to_num(_momentum(close, n), nan=0.0) * 4.0) for n in horizons]
    return np.mean(votes, axis=0)
def _regime_gate(close: np.ndarray, score: np.ndarray) -> np.ndarray:
    """Long-term SMA200 sign defines the allowed direction: only long entries in an
    uptrend regime, only short entries in a downtrend regime. This structurally
    prevents counter-trend bets rather than relying on the ensemble to self-correct."""
    sma200 = _sma(close, 200)
    up_regime = close > sma200
    down_regime = ~up_regime
    gated = np.where(up_regime, np.maximum(score, 0.0), score)
    gated = np.where(down_regime, np.minimum(gated, 0.0), gated)
    return np.nan_to_num(gated, nan=0.0)
def _vol_target_size(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                      raw_score: np.ndarray, target_vol: float = 0.012) -> np.ndarray:
    """Size by true-range volatility (gap-aware) rather than close-to-close std."""
    prev_close = _shift(close, 1)
    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
    )
    atr = pd.Series(tr).rolling(20, min_periods=20).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        atr_pct = atr / close
        vol_scale = target_vol / atr_pct
    vol_scale = np.nan_to_num(vol_scale, nan=0.0, posinf=0.0, neginf=0.0)
    vol_scale = np.clip(vol_scale, 0.0, 1.5)
    return raw_score * vol_scale
def _hold_lock(target: np.ndarray, min_hold: int = 10, change_thresh: float = 0.25) -> np.ndarray:
    """Causal state machine: position only updates once accumulated conviction
    (|target - current| > change_thresh) exceeds threshold AND at least
    `min_hold` bars have passed since the last change. This bounds trade
    frequency directly, replacing EMA smoothing as the turnover-control device."""
    n = len(target)
    position = np.zeros(n)
    current = 0.0
    bars_since_change = min_hold
    for i in range(n):
        t = target[i]
        if not np.isfinite(t):
            t = 0.0
        if bars_since_change >= min_hold and abs(t - current) > change_thresh:
            current = t
            bars_since_change = 0
        else:
            bars_since_change += 1
        position[i] = current
    return position
def signal(ohlcv):
    close = ohlcv["close"]
    high = ohlcv["high"]
    low = ohlcv["low"]
    trend_score = _trend_ensemble(close)
    momo_score = _momentum_ensemble(close)
    raw_score = 0.6 * trend_score + 0.4 * momo_score
    gated_score = _regime_gate(close, raw_score)
    # Deadband: kill weak-conviction signals outright so the book can be flat,
    # instead of always carrying a small nonzero exposure.
    deadband = 0.12
    gated_score = np.where(np.abs(gated_score) < deadband, 0.0, gated_score)
    sized = _vol_target_size(close, high, low, gated_score)
    position = _hold_lock(sized, min_hold=10, change_thresh=0.25)
    position = np.nan_to_num(position, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(position, -1.0, 1.0)
# EVOLVE-BLOCK-END
