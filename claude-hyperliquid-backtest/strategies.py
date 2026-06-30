"""The 3 frozen Claude strategies (see prompts/claude_strategy_response.md).

OHLCV-only, long/flat, no leverage, ~100% equity per entry. Decisions use the current
bar's close and earlier; Backtesting.py fills orders on the next bar's open, so there is
no same-bar lookahead. Parameters are textbook defaults chosen a priori (no tuning).

These run through the SAME deterministic harness (backtest.py) as the baselines
(baselines.py) — identical data, fees, and split — so the comparison is apples-to-apples.
"""
import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover

# ~all-in long as a fraction of available equity (works at any price scale).
SIZE = 0.999


# --- indicator helpers (pure, no lookahead) ---------------------------------
def _sma(arr, n):
    return pd.Series(arr).rolling(n).mean().to_numpy()


def _ema(arr, n):
    return pd.Series(arr).ewm(span=n, adjust=False).mean().to_numpy()


def _rsi(arr, n):
    s = pd.Series(arr)
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).to_numpy()


def _prior_high(high, n):
    # highest high of the PRIOR n bars (excludes the current bar)
    return pd.Series(high).rolling(n).max().shift(1).to_numpy()


def _prior_low(low, n):
    return pd.Series(low).rolling(n).min().shift(1).to_numpy()


# --- Strategy 1: Donchian breakout (trend) ----------------------------------
class DonchianBreakout(Strategy):
    n_entry = 20
    n_exit = 10

    def init(self):
        self.upper = self.I(_prior_high, self.data.High, self.n_entry, name="upper20")
        self.lower = self.I(_prior_low, self.data.Low, self.n_exit, name="lower10")

    def next(self):
        price = self.data.Close[-1]
        if not self.position and price > self.upper[-1]:
            self.buy(size=SIZE)
        elif self.position and price < self.lower[-1]:
            self.position.close()


# --- Strategy 2: RSI(2) mean-reversion with SMA200 trend filter -------------
class RSI2Reversion(Strategy):
    rsi_n = 2
    rsi_buy = 10
    trend_n = 200
    exit_n = 5

    def init(self):
        self.rsi = self.I(_rsi, self.data.Close, self.rsi_n, name="rsi2")
        self.trend = self.I(_sma, self.data.Close, self.trend_n, name="sma200")
        self.exit_sma = self.I(_sma, self.data.Close, self.exit_n, name="sma5")

    def next(self):
        price = self.data.Close[-1]
        if not self.position:
            if self.rsi[-1] < self.rsi_buy and price > self.trend[-1]:
                self.buy(size=SIZE)
        elif price > self.exit_sma[-1]:
            self.position.close()


# --- Strategy 3: MACD momentum, zero-line confirmed -------------------------
class MACDMomentum(Strategy):
    fast = 12
    slow = 26
    signal = 9

    def init(self):
        macd = _ema(self.data.Close, self.fast) - _ema(self.data.Close, self.slow)
        self.macd = self.I(lambda: macd, name="macd")
        self.signal_line = self.I(_ema, macd, self.signal, name="signal")

    def next(self):
        if not self.position:
            if crossover(self.macd, self.signal_line) and self.macd[-1] > 0:
                self.buy(size=SIZE)
        elif crossover(self.signal_line, self.macd):
            self.position.close()


STRATEGIES = {
    "donchian_breakout": DonchianBreakout,
    "rsi2_reversion": RSI2Reversion,
    "macd_momentum": MACDMomentum,
}
