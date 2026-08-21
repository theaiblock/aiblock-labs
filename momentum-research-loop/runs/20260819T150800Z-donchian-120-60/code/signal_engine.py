"""Daily asymmetric Donchian breakout momentum for BTC."""

import pandas as pd


class SignalEngine:
    """Long on a prior 120-day high; flat on a prior 60-day low."""

    ENTRY_WINDOW = 120
    EXIT_WINDOW = 60

    def __init__(self):
        self.entry_window = 120
        self.exit_window = 60

    def generate(self, data_map):
        signals = {}
        for symbol, frame in data_map.items():
            close = frame["close"].astype(float)
            prior_close = close.shift(1)
            entry_high = prior_close.rolling(
                self.entry_window, min_periods=self.entry_window
            ).max()
            exit_low = prior_close.rolling(
                self.exit_window, min_periods=self.exit_window
            ).min()

            signal = pd.Series(0.0, index=frame.index, dtype=float)
            is_long = False
            for position in range(len(frame)):
                if not is_long and pd.notna(entry_high.iloc[position]):
                    if close.iloc[position] >= entry_high.iloc[position]:
                        is_long = True
                elif is_long and pd.notna(exit_low.iloc[position]):
                    if close.iloc[position] <= exit_low.iloc[position]:
                        is_long = False
                signal.iloc[position] = 1.0 if is_long else 0.0
            signals[symbol] = signal
        return signals
