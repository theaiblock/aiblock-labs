"""Slow daily time-series momentum baseline for BTC."""

import pandas as pd


class SignalEngine:
    """Long/flat 50/200-day simple moving-average trend rule."""

    FAST_WINDOW = 50
    SLOW_WINDOW = 200

    def __init__(self):
        self.fast_window = 50
        self.slow_window = 200

    def generate(self, data_map):
        signals = {}
        for symbol, frame in data_map.items():
            close = frame["close"].astype(float)
            fast = close.rolling(self.fast_window, min_periods=self.fast_window).mean()
            slow = close.rolling(self.slow_window, min_periods=self.slow_window).mean()
            ready = fast.notna() & slow.notna()
            signal = pd.Series(0.0, index=frame.index, dtype=float)
            signal.loc[ready & (fast > slow)] = 1.0
            signals[symbol] = signal
        return signals
