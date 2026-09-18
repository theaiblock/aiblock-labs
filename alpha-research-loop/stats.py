"""Paired comparison against the benchmark. No model involved.

Two strategies that trade a similar book move together, so the difference between their Sharpe ratios
is measured far more precisely than either Sharpe on its own. Resampling the same blocks of days for
both keeps that pairing; blocks keep a month of autocorrelation intact."""
from __future__ import annotations

import numpy as np
import pandas as pd

BLOCK, SAMPLES, SEED, YEAR = 28, 2000, 7, 365


def sharpe(x: np.ndarray) -> np.ndarray:
    sd = x.std(axis=-1)
    return np.where(sd > 0, x.mean(axis=-1) / np.where(sd > 0, sd, 1) * np.sqrt(YEAR), 0.0)


def paired(returns: pd.Series, benchmark: pd.Series, block: int = BLOCK, samples: int = SAMPLES) -> dict:
    a, b = returns.align(benchmark, join="inner")
    a, b = a.fillna(0).to_numpy(), b.fillna(0).to_numpy()
    T = len(a)
    rng = np.random.default_rng(SEED)  # same blocks for every idea: comparable intervals
    starts = rng.integers(0, T - block, (samples, T // block + 1))
    idx = (starts[:, :, None] + np.arange(block)).reshape(samples, -1)[:, :T]
    diff = sharpe(a[idx]) - sharpe(b[idx])
    lo, hi = np.percentile(diff, [2.5, 97.5])
    return {"delta_sharpe": float(sharpe(a) - sharpe(b)), "ci_low": float(lo), "ci_high": float(hi),
            "p_not_better": float((diff <= 0).mean()),
            "verdict": "above" if lo > 0 else "below" if hi < 0 else "unclear"}
