"""
strategies/rsi_meanreversion.py

Mean-reversion strategy: buy when RSI drops into oversold territory
(signals price may bounce back up), sell when it climbs into overbought
territory (signals price may pull back down).

Works best in ranging/choppy markets. Tends to get chopped up badly
in strong trends -- that's exactly why you backtest across different
market conditions instead of trusting one number.
"""

import pandas as pd
import numpy as np


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def generate_signals(df: pd.DataFrame, period: int = 14, oversold: int = 30, overbought: int = 70):
    """
    Returns (entries, exits) as boolean pandas Series aligned with df.index.
    """
    close = df["close"]
    rsi = compute_rsi(close, period)

    # Entry: RSI crosses up out of oversold zone
    entries = (rsi > oversold) & (rsi.shift(1) <= oversold)

    # Exit: RSI crosses down out of overbought zone
    exits = (rsi < overbought) & (rsi.shift(1) >= overbought)

    return entries.fillna(False), exits.fillna(False)
