"""
backtests/engine.py

Core backtesting engine. Takes a strategy's buy/sell signals and historical
price data, runs a simulated portfolio through it, and reports real
performance metrics.

Metrics you actually care about (not just raw % return):
    - Win rate           -> % of trades that were profitable
    - Profit factor       -> gross profit / gross loss (>1.5 is decent, >2 is good)
    - Sharpe ratio         -> risk-adjusted return (>1 is good, >2 is very good)
    - Max drawdown          -> worst peak-to-trough loss (smaller = safer)
    - Total return vs Buy & Hold -> is your strategy even beating doing nothing?

Usage:
    python backtests/engine.py --symbol USDINR=X --strategy sma_crossover
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

sys.path.append(str(Path(__file__).resolve().parent.parent))
from data.fetcher import load_data
from strategies.sma_crossover import generate_signals as sma_signals
from strategies.rsi_meanreversion import generate_signals as rsi_signals

STRATEGY_REGISTRY = {
    "sma_crossover": sma_signals,
    "rsi_meanreversion": rsi_signals,
}


def run_backtest(df: pd.DataFrame, strategy_name: str, init_cash: float = 100_000, fees: float = 0.001):
    """
    df must have a 'close' column (and 'date' if available).
    fees = 0.001 -> 0.1% per trade, a rough stand-in for broker/spread costs.
    """
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy '{strategy_name}'. Options: {list(STRATEGY_REGISTRY.keys())}")

    signal_fn = STRATEGY_REGISTRY[strategy_name]
    entries, exits = signal_fn(df)

    close = df["close"]

    portfolio = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=init_cash,
        fees=fees,
        freq="1D",
    )

    return portfolio


def print_report(portfolio: vbt.Portfolio, strategy_name: str, symbol: str):
    stats = portfolio.stats()

    print(f"\n{'='*60}")
    print(f"BACKTEST REPORT — {strategy_name} on {symbol}")
    print(f"{'='*60}")

    total_return = portfolio.total_return() * 100
    bh_return = portfolio.total_benchmark_return() * 100 if hasattr(portfolio, "total_benchmark_return") else None

    trades = portfolio.trades
    win_rate = trades.win_rate() * 100 if trades.count() > 0 else 0.0
    profit_factor = trades.profit_factor() if trades.count() > 0 else float("nan")
    sharpe = portfolio.sharpe_ratio()
    max_dd = portfolio.max_drawdown() * 100

    print(f"Total trades:        {trades.count()}")
    print(f"Win rate:            {win_rate:.1f}%")
    print(f"Profit factor:       {profit_factor:.2f}")
    print(f"Sharpe ratio:        {sharpe:.2f}")
    print(f"Max drawdown:        {max_dd:.1f}%")
    print(f"Total return:        {total_return:.1f}%")
    print(f"{'='*60}")
    print("\nReality check: win rate alone means nothing without profit factor.")
    print("A 40% win rate with 3:1 reward:risk beats a 70% win rate with 1:3.")
    print(f"{'='*60}\n")

    return {
        "trades": trades.count(),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "total_return": total_return,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a backtest for a given strategy")
    parser.add_argument("--symbol", type=str, default="USDINR=X")
    parser.add_argument("--interval", type=str, default="1d")
    parser.add_argument("--strategy", type=str, default="sma_crossover", choices=list(STRATEGY_REGISTRY.keys()))
    parser.add_argument("--cash", type=float, default=100_000)
    args = parser.parse_args()

    df = load_data(args.symbol, args.interval)
    portfolio = run_backtest(df, args.strategy, init_cash=args.cash)
    print_report(portfolio, args.strategy, args.symbol)
