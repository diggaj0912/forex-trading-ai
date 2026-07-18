"""
data/fetcher.py

Pulls historical OHLCV data for backtesting and (later) live trading.

Two sources:
  1. yfinance  -> free, good enough for backtesting/research (daily/hourly data,
                  works for indices, USD-INR, stocks, crypto, etc.)
  2. KiteConnect -> Zerodha's paid API, needed for real intraday/live data and
                     for actually placing orders. Scaffolded but requires your
                     own API key + access token (get from developers.kite.trade).

Usage:
    python data/fetcher.py --symbol USDINR=X --start 2018-01-01 --end 2025-01-01
"""

import argparse
import os
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_yfinance(symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    """
    Fetch historical OHLCV data via yfinance.

    symbol examples:
        "USDINR=X"   -> USD/INR forex pair
        "^NSEI"      -> Nifty 50 index
        "RELIANCE.NS"-> Reliance on NSE
        "BTC-USD"    -> Bitcoin

    interval: "1d", "1h", "15m", "5m", "1m"
              Note: intraday intervals only go back a limited window
              (e.g. 1m data is capped at ~7 days by Yahoo Finance).
    """
    df = yf.download(symbol, start=start, end=end, interval=interval, progress=False)

    if df.empty:
        raise ValueError(f"No data returned for symbol={symbol}. Check the ticker or date range.")

    df.reset_index(inplace=True)

    # yfinance returns MultiIndex columns like ('Close', 'USDINR=X') even for
    # a single ticker. Flatten to just the field name (Close, Open, etc.)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

    return df


def save_data(df: pd.DataFrame, symbol: str, interval: str) -> Path:
    safe_symbol = symbol.replace("=", "_").replace("^", "")
    out_path = DATA_DIR / f"{safe_symbol}_{interval}.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")
    return out_path


def load_data(symbol: str, interval: str) -> pd.DataFrame:
    safe_symbol = symbol.replace("=", "_").replace("^", "")
    path = DATA_DIR / f"{safe_symbol}_{interval}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No cached data at {path}. Run fetch_yfinance() first.")
    return pd.read_csv(path, parse_dates=["date"] if "date" in pd.read_csv(path, nrows=0).columns else None)


# ---------------------------------------------------------------------------
# Kite Connect scaffold (Zerodha) — for live/intraday data + order placement
# Requires: pip install kiteconnect
# Docs: https://kite.trade/docs/connect/v3/
# ---------------------------------------------------------------------------
class KiteDataFetcher:
    def __init__(self, api_key: str = None, access_token: str = None):
        """
        api_key / access_token come from your Kite Connect developer app.
        Store them in a .env file, never hardcode:
            KITE_API_KEY=xxx
            KITE_ACCESS_TOKEN=xxx
        """
        from kiteconnect import KiteConnect  # imported here so yfinance-only users don't need it

        self.api_key = api_key or os.getenv("KITE_API_KEY")
        self.access_token = access_token or os.getenv("KITE_ACCESS_TOKEN")

        if not self.api_key or not self.access_token:
            raise ValueError("KITE_API_KEY and KITE_ACCESS_TOKEN must be set (env vars or passed in).")

        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)

    def get_historical(self, instrument_token: int, from_date: str, to_date: str, interval: str = "day"):
        """
        interval: "minute", "3minute", "5minute", "15minute", "30minute", "60minute", "day"
        instrument_token: get this from self.kite.instruments() for your symbol
        """
        data = self.kite.historical_data(instrument_token, from_date, to_date, interval)
        return pd.DataFrame(data)

    def get_instrument_token(self, tradingsymbol: str, exchange: str = "NSE") -> int:
        instruments = self.kite.instruments(exchange)
        for inst in instruments:
            if inst["tradingsymbol"] == tradingsymbol:
                return inst["instrument_token"]
        raise ValueError(f"Instrument {tradingsymbol} not found on {exchange}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch historical OHLCV data")
    parser.add_argument("--symbol", type=str, default="USDINR=X", help="Ticker symbol (yfinance format)")
    parser.add_argument("--start", type=str, default="2018-01-01")
    parser.add_argument("--end", type=str, default="2025-01-01")
    parser.add_argument("--interval", type=str, default="1d")
    args = parser.parse_args()

    df = fetch_yfinance(args.symbol, args.start, args.end, args.interval)
    print(df.head())
    print(f"\nTotal rows: {len(df)}")
    save_data(df, args.symbol, args.interval)
