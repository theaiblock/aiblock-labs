"""The dumb baselines every strategy must beat — run through the SAME harness.

- BuyHold      : long from bar 1 to the end (the market itself).
- SMACross     : classic golden-cross, SMA(50/200), long/flat (the "dumb MA" baseline).
- FollowSignal : generic long/flat that obeys a precomputed boolean column `LongSig`,
                 used for the random Monte-Carlo cloud (random_signal() below).

If a "smart" strategy can't beat buy-and-hold, a moving-average cross, AND a cloud of
random bots with the same exposure, it has no demonstrated edge.
"""
import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover

SIZE = 0.999


def _sma(arr, n):
    return pd.Series(arr).rolling(n).mean().to_numpy()


class BuyHold(Strategy):
    def init(self):
        pass

    def next(self):
        if not self.position:
            self.buy(size=SIZE)


class SMACross(Strategy):
    fast = 50
    slow = 200

    def init(self):
        self.f = self.I(_sma, self.data.Close, self.fast, name="sma50")
        self.s = self.I(_sma, self.data.Close, self.slow, name="sma200")

    def next(self):
        if not self.position and crossover(self.f, self.s):
            self.buy(size=SIZE)
        elif self.position and crossover(self.s, self.f):
            self.position.close()


class FollowSignal(Strategy):
    """Long when self.data.LongSig == 1, flat otherwise."""

    def init(self):
        pass

    def next(self):
        want_long = self.data.LongSig[-1] > 0.5
        if want_long and not self.position:
            self.buy(size=SIZE)
        elif not want_long and self.position:
            self.position.close()


def random_signal(n, exposure, mean_hold, seed):
    """Two-state Markov long/flat signal calibrated to a target time-in-market
    (`exposure`) and average holding length (`mean_hold`, in bars). Seeded → deterministic.
    Gives a random bot with the SAME shape as the real strategies but no skill."""
    rng = np.random.default_rng(seed)
    exposure = min(max(exposure, 1e-3), 0.999)
    b = 1.0 / max(mean_hold, 1.0)              # long -> flat probability
    a = min(b * exposure / (1.0 - exposure), 1.0)  # flat -> long probability
    sig = np.zeros(n, dtype=np.float64)
    state = False
    for i in range(n):
        if state:
            if rng.random() < b:
                state = False
        else:
            if rng.random() < a:
                state = True
        sig[i] = 1.0 if state else 0.0
    return sig
