"""
strategies/sma_crossover.py

Trend-following strategy: buy when fast SMA crosses above slow SMA,
sell when it crosses back below. Classic, simple, a good baseline to
compare everything else against.
"""

import pandas as pd


def generate_signals(df: pd.DataFrame, fast_window: int = 20, slow_window: int = 50):
    """
    Returns (entries, exits) as boolean pandas Series aligned with df.index.
    """
    close = df["close"]

    fast_sma = close.rolling(window=fast_window).mean()
    slow_sma = close.rolling(window=slow_window).mean()

    # Entry: fast SMA crosses above slow SMA (golden cross)
    entries = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))

    # Exit: fast SMA crosses below slow SMA (death cross)
    exits = (fast_sma < slow_sma) & (fast_sma.shift(1) >= slow_sma.shift(1))

    return entries.fillna(False), exits.fillna(False)
