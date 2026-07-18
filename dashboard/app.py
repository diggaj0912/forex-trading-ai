"""
dashboard/app.py

Live signal scanner (Streamlit web dashboard).

IMPORTANT — what this tool actually is:
    It fetches recent price data, computes the RSI mean-reversion signal
    (the only strategy that showed a real, if modest, edge in our
    walk-forward validation), and shows you whether that signal is
    currently active -- alongside the HISTORICAL performance of that
    exact signal, so you can judge it yourself.

    It does NOT predict the future. It does NOT guarantee profit.
    A "BUY SIGNAL" here means "RSI just crossed up out of oversold
    territory, matching the pattern that historically had ~48% winning
    windows with asymmetric win/loss sizes" -- not "this will go up."

Run with:
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))
from data.fetcher import fetch_yfinance
from strategies.rsi_meanreversion import compute_rsi

st.set_page_config(page_title="Strategy Signal Scanner", layout="wide")

WATCHLIST = {
    "USD/INR": "USDINR=X",
    "Nifty 50": "^NSEI",
    "EUR/INR": "EURINR=X",
    "GBP/INR": "GBPINR=X",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Infosys": "INFY.NS",
}

RSI_PERIOD = 14
OVERSOLD = 30
OVERBOUGHT = 70


@st.cache_data(ttl=900)  # cache 15 min so we don't hammer yfinance
def get_recent_data(symbol: str, days: int = 120) -> pd.DataFrame:
    end = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = fetch_yfinance(symbol, start=start, end=end, interval="1d")
    df["rsi"] = compute_rsi(df["close"], period=RSI_PERIOD)
    return df


def get_signal(df: pd.DataFrame) -> dict:
    if len(df) < RSI_PERIOD + 2:
        return {"signal": "NOT ENOUGH DATA", "rsi": None, "close": None}

    latest_rsi = df["rsi"].iloc[-1]
    prev_rsi = df["rsi"].iloc[-2]
    latest_close = df["close"].iloc[-1]

    if pd.isna(latest_rsi) or pd.isna(prev_rsi):
        return {"signal": "NOT ENOUGH DATA", "rsi": latest_rsi, "close": latest_close}

    if prev_rsi <= OVERSOLD and latest_rsi > OVERSOLD:
        signal = "SIGNAL: RSI exiting oversold"
    elif prev_rsi >= OVERBOUGHT and latest_rsi < OVERBOUGHT:
        signal = "SIGNAL: RSI exiting overbought"
    elif latest_rsi < OVERSOLD:
        signal = "Watch: currently oversold, no cross yet"
    elif latest_rsi > OVERBOUGHT:
        signal = "Watch: currently overbought, no cross yet"
    else:
        signal = "No signal (RSI in neutral zone)"

    return {"signal": signal, "rsi": latest_rsi, "close": latest_close}


st.title("Strategy Signal Scanner")
st.caption(
    "Live RSI mean-reversion signals, shown alongside historical backtest context. "
    "This is a decision-support tool, not financial advice — see disclaimer at the bottom."
)

st.warning(
    "⚠️ This tool shows a rule-based technical signal with a **modest, unproven historical edge** "
    "(48% of walk-forward windows profitable on Nifty, small sample size — 14 trades over 6 years). "
    "It is not a prediction and does not guarantee profit. Never invest money you can't afford to lose, "
    "and consider this alongside fundamentals, news, and your own risk tolerance — not as a standalone signal."
)

cols = st.columns(2)
selected_instruments = []
for i, (name, symbol) in enumerate(WATCHLIST.items()):
    col = cols[i % 2]
    with col:
        checked = st.checkbox(name, value=True, key=f"chk_{symbol}")
        if checked:
            selected_instruments.append((name, symbol))

st.divider()

if st.button("🔍 Scan selected instruments", type="primary"):
    results = []
    progress = st.progress(0, text="Scanning...")

    for idx, (name, symbol) in enumerate(selected_instruments):
        try:
            df = get_recent_data(symbol)
            sig = get_signal(df)
            results.append({
                "Instrument": name,
                "Symbol": symbol,
                "Last Close": round(sig["close"], 4) if sig["close"] else None,
                "RSI (14)": round(sig["rsi"], 1) if sig["rsi"] else None,
                "Current Reading": sig["signal"],
            })
        except Exception as e:
            results.append({
                "Instrument": name,
                "Symbol": symbol,
                "Last Close": None,
                "RSI (14)": None,
                "Current Reading": f"Error: {e}",
            })
        progress.progress((idx + 1) / len(selected_instruments), text=f"Scanned {name}")

    progress.empty()

    results_df = pd.DataFrame(results)

    def highlight_signal(row):
        if "SIGNAL" in str(row["Current Reading"]):
            return ["background-color: #1e4620"] * len(row)
        elif "Watch" in str(row["Current Reading"]):
            return ["background-color: #4a3b1a"] * len(row)
        return [""] * len(row)

    st.dataframe(
        results_df.style.apply(highlight_signal, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    active_signals = results_df[results_df["Current Reading"].str.contains("SIGNAL", na=False)]
    if not active_signals.empty:
        st.success(f"{len(active_signals)} instrument(s) showing an active RSI cross signal right now.")
    else:
        st.info("No active cross signals right now — most instruments are in neutral/watch zones.")

st.divider()
st.markdown("""
### How to actually use this
- **"SIGNAL"** = RSI just crossed the oversold/overbought threshold today — this is the exact
  entry condition that was walk-forward tested earlier.
- **"Watch"** = in the extreme zone but hasn't crossed back yet — a signal may trigger soon.
- This tool does **not** place trades, does **not** know your position sizing or risk tolerance,
  and reflects only ONE strategy (RSI mean-reversion) out of many possible approaches.
- Past performance (even the honestly-validated kind from walk-forward testing) does not
  guarantee future results. Markets change regimes; a pattern that worked 2019-2024 may stop working.

**This is not investment advice.** If you're putting real capital behind this, consider
paper-trading it first for a few months to confirm the signal still behaves as backtested
in live conditions before risking money.
""")
