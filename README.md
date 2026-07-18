# Forex/Stock Trading Signal Framework

A backtesting, validation, and live-signal-scanning system for technical
trading strategies on Indian markets (NSE stocks, Nifty, INR currency pairs).

**Read this before trusting any signal it gives you:** this project does not
predict the future and does not guarantee profit. It tests trading rules
against historical data honestly, tells you when a strategy doesn't have a
real edge, and surfaces the same tested rule live so you're not guessing.
That's it. Treat every signal as one input among many, not a verdict.

---

## What's in this project

```
forex-trading-ai/
├── data/
│   └── fetcher.py          # Pulls historical OHLCV data (yfinance + Zerodha Kite scaffold)
├── strategies/
│   ├── sma_crossover.py    # Trend-following strategy (fast/slow moving average cross)
│   └── rsi_meanreversion.py# Mean-reversion strategy (RSI oversold/overbought)
├── backtests/
│   ├── engine.py           # Runs a strategy against historical data, reports stats
│   └── walk_forward.py     # Rolling-window validation to catch overfitting/luck
├── dashboard/
│   └── app.py              # Streamlit web dashboard -- live signal scanner
├── browser-extension/
│   └── ...                 # Edge/Chrome extension -- shows live signal on Angel One pages
└── requirements.txt         # Trimmed dependencies for the deployed dashboard
```

---

## Setup (local)

```powershell
# from the project root
python -m venv venv
venv\Scripts\Activate.ps1
pip install pandas numpy yfinance vectorbt backtrader scikit-learn xgboost matplotlib jupyter python-dotenv streamlit kiteconnect
```

## 1. Fetch historical data

```powershell
python data/fetcher.py --symbol USDINR=X --start 2018-01-01 --end 2025-01-01
```

Swap `--symbol` for any yfinance ticker: `^NSEI` (Nifty 50), `RELIANCE.NS`,
`EURINR=X`, etc. Saves to `data/raw/`.

## 2. Backtest a strategy

```powershell
python backtests/engine.py --symbol USDINR=X --strategy sma_crossover
python backtests/engine.py --symbol USDINR=X --strategy rsi_meanreversion
```

Reports trades, win rate, profit factor, Sharpe ratio, max drawdown, total
return.

## 3. Walk-forward validate (the important step)

A single backtest number can be misleading -- it can look great by chance on
one slice of history. This splits the data into rolling windows and re-tests
independently on each one.

```powershell
python backtests/walk_forward.py --symbol USDINR=X --strategy rsi_meanreversion
```

Look at the **% of windows profitable** and the **consistency** of returns,
not just the aggregate number.

## 4. Run the live dashboard

```powershell
streamlit run dashboard/app.py
```

Opens a browser tab showing a checklist of instruments and a live RSI signal
scan, with the same honest disclaimers baked into the page.

## 5. Browser extension (Angel One)

See `browser-extension/` -- load unpacked in Edge/Chrome via
`edge://extensions` or `chrome://extensions` with Developer mode on. Shows a
floating signal widget on Angel One stock pages. Symbol auto-detection is
best-effort (Angel One's exact page structure wasn't visible during
development) -- use the manual input if it doesn't detect correctly.

---

## What we've actually found so far (as of this build)

| Strategy | Instrument | Aggregate backtest | Walk-forward reality |
|---|---|---|---|
| SMA Crossover | USD/INR | Weak (0% return, PF 1.00) | No edge (9% windows profitable on Nifty too) |
| RSI Mean-Reversion | USD/INR | Looked strong (77.8% win rate) | **No edge** -- 29% windows profitable, avg return ~0% |
| RSI Mean-Reversion | Nifty 50 | Looked strong | **Modest, plausible edge** -- 48% windows profitable, but small sample (14 trades/6yr) |

**Bottom line:** RSI mean-reversion on Nifty-like instruments shows the most
promise, but the sample size is still too small to bet real money on with
confidence. Next validation step: test across a larger basket of stocks
before trusting it further.

---

## Honest limitations

- No strategy here has been proven to reliably beat the market.
- Backtests don't account for slippage, real bid-ask spreads, or liquidity
  constraints -- live results will be worse than backtested ones.
- Retail forex trading (non-INR pairs) through offshore brokers is a FEMA
  compliance grey area for Indian residents -- only INR currency pairs
  (USD-INR, EUR-INR, GBP-INR, JPY-INR) are legally tradable via SEBI-registered
  exchanges.
- Past performance, even honestly walk-forward-validated, does not guarantee
  future results. Markets change regimes.

## Suggested next steps

1. Multi-instrument batch validation (test RSI mean-reversion across 30-50
   NSE stocks to see if the edge generalizes)
2. Paper-trade the strategy live for a few months before risking capital
3. ML-based signal model (combine multiple features instead of one fixed rule)
4. Tighten browser extension symbol detection against real Angel One DOM