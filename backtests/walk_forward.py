"""
backtests/walk_forward.py

Walk-forward validation: splits historical data into rolling windows and
re-runs the backtest on each window independently. This is how you tell
the difference between a strategy with a real edge vs. one that just got
lucky on a specific stretch of history.

How it works:
    Window 1: train on months 1-12,  test on months 13-15
    Window 2: train on months 4-15,  test on months 16-18
    Window 3: train on months 7-18,  test on months 19-21
    ... and so on, rolling forward through the full dataset.

"Train" here doesn't mean fitting parameters (our strategies use fixed
rules), it means: this is the window whose stats you'd have seen live if
you were running the strategy at that point in time. "Test" is the next
chunk forward -- data the strategy has never touched.

A strategy with a real edge should show reasonably consistent (if not
identical) performance across most test windows. A strategy that looks
great in one aggregate backtest but falls apart or flips sign across
walk-forward windows was probably just fit to noise in that one period.

Usage:
    python backtests/walk_forward.py --symbol USDINR=X --strategy rsi_meanreversion
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

sys.path.append(str(Path(__file__).resolve().parent.parent))
from data.fetcher import load_data
from backtests.engine import STRATEGY_REGISTRY, run_backtest, print_report


def make_windows(n_rows: int, train_size: int, test_size: int, step: int):
    """
    Yields (train_start, train_end, test_start, test_end) index tuples,
    rolling forward through the dataset.
    """
    windows = []
    start = 0
    while True:
        train_start = start
        train_end = train_start + train_size
        test_start = train_end
        test_end = test_start + test_size

        if test_end > n_rows:
            break

        windows.append((train_start, train_end, test_start, test_end))
        start += step

    return windows


def run_walk_forward(
    df: pd.DataFrame,
    strategy_name: str,
    train_size: int = 252,   # ~1 trading year
    test_size: int = 63,     # ~1 trading quarter
    step: int = 63,          # roll forward by 1 quarter each time
    init_cash: float = 100_000,
):
    windows = make_windows(len(df), train_size, test_size, step)

    if not windows:
        raise ValueError(
            f"Not enough data for these window sizes. "
            f"Have {len(df)} rows, need at least {train_size + test_size}."
        )

    results = []

    for i, (tr_s, tr_e, te_s, te_e) in enumerate(windows, start=1):
        test_df = df.iloc[te_s:te_e].reset_index(drop=True)

        if len(test_df) < 20:
            continue  # too short a slice to mean anything

        try:
            portfolio = run_backtest(test_df, strategy_name, init_cash=init_cash)
            trades = portfolio.trades

            n_trades = trades.count()
            win_rate = trades.win_rate() * 100 if n_trades > 0 else np.nan
            profit_factor = trades.profit_factor() if n_trades > 0 else np.nan
            sharpe = portfolio.sharpe_ratio()
            total_return = portfolio.total_return() * 100

            results.append({
                "window": i,
                "test_start_date": df["date"].iloc[te_s] if "date" in df.columns else te_s,
                "test_end_date": df["date"].iloc[te_e - 1] if "date" in df.columns else te_e - 1,
                "n_trades": n_trades,
                "win_rate_pct": win_rate,
                "profit_factor": profit_factor,
                "sharpe": sharpe,
                "return_pct": total_return,
            })
        except Exception as e:
            results.append({
                "window": i,
                "test_start_date": df["date"].iloc[te_s] if "date" in df.columns else te_s,
                "test_end_date": df["date"].iloc[te_e - 1] if "date" in df.columns else te_e - 1,
                "n_trades": 0,
                "win_rate_pct": np.nan,
                "profit_factor": np.nan,
                "sharpe": np.nan,
                "return_pct": np.nan,
                "error": str(e),
            })

    return pd.DataFrame(results)


def summarize(results_df: pd.DataFrame, strategy_name: str, symbol: str):
    print(f"\n{'='*70}")
    print(f"WALK-FORWARD VALIDATION — {strategy_name} on {symbol}")
    print(f"{'='*70}")
    print(results_df.to_string(index=False))
    print(f"{'='*70}")

    valid = results_df.dropna(subset=["return_pct"])
    if valid.empty:
        print("No valid windows produced results.")
        return

    total_windows = len(valid)
    profitable_windows = (valid["return_pct"] > 0).sum()
    pct_profitable_windows = profitable_windows / total_windows * 100

    avg_return = valid["return_pct"].mean()
    std_return = valid["return_pct"].std()
    avg_sharpe = valid["sharpe"].mean()
    total_trades = valid["n_trades"].sum()

    print(f"\nSUMMARY ACROSS {total_windows} WINDOWS:")
    print(f"  Windows profitable:     {profitable_windows}/{total_windows} ({pct_profitable_windows:.0f}%)")
    print(f"  Avg return per window:  {avg_return:.2f}%  (std dev: {std_return:.2f}%)")
    print(f"  Avg Sharpe per window:  {avg_sharpe:.2f}")
    print(f"  Total trades across all windows: {int(total_trades)}")

    print(f"\n{'='*70}")
    print("HOW TO READ THIS:")
    if pct_profitable_windows >= 60 and std_return < abs(avg_return) * 2:
        print("  Reasonably consistent across time windows.")
        print("  This suggests a real, if modest, edge -- not pure luck.")
    elif pct_profitable_windows >= 50:
        print("  Mixed results. Edge may be weak, regime-dependent, or")
        print("  concentrated in a few outlier windows. Investigate which")
        print("  windows won/lost before trusting this live.")
    else:
        print("  Inconsistent / mostly unprofitable across windows.")
        print("  The aggregate backtest number was likely misleading --")
        print("  this strategy does not show a reliable edge over time.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run walk-forward validation for a strategy")
    parser.add_argument("--symbol", type=str, default="USDINR=X")
    parser.add_argument("--interval", type=str, default="1d")
    parser.add_argument("--strategy", type=str, default="rsi_meanreversion", choices=list(STRATEGY_REGISTRY.keys()))
    parser.add_argument("--train_size", type=int, default=252, help="Rows per train window (approx trading days)")
    parser.add_argument("--test_size", type=int, default=63, help="Rows per test window (approx trading days)")
    parser.add_argument("--step", type=int, default=63, help="Rows to roll forward each iteration")
    parser.add_argument("--cash", type=float, default=100_000)
    args = parser.parse_args()

    df = load_data(args.symbol, args.interval)
    results_df = run_walk_forward(
        df, args.strategy,
        train_size=args.train_size,
        test_size=args.test_size,
        step=args.step,
        init_cash=args.cash,
    )
    summarize(results_df, args.strategy, args.symbol)
