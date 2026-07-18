/**
 * background.js
 *
 * Runs as the extension's service worker. Handles all network requests
 * (Yahoo Finance) so we don't hit CSP restrictions from Angel One's page,
 * and computes the RSI signal server-side (well, extension-side) before
 * sending the result back to the content script for display.
 */

const RSI_PERIOD = 14;
const OVERSOLD = 30;
const OVERBOUGHT = 70;

// Map common NSE symbols as they might appear on Angel One's UI to
// yfinance-style tickers. Extend this as you find mismatches.
const SYMBOL_OVERRIDES = {
  "NIFTY": "^NSEI",
  "NIFTY50": "^NSEI",
  "BANKNIFTY": "^NSEBANK",
};

function toYahooSymbol(rawSymbol) {
  const cleaned = rawSymbol.trim().toUpperCase().replace(/[^A-Z0-9&\-]/g, "");
  if (SYMBOL_OVERRIDES[cleaned]) return SYMBOL_OVERRIDES[cleaned];
  // Default assumption: NSE-listed equity -> add .NS suffix (yfinance convention)
  if (!cleaned.includes(".") && !cleaned.startsWith("^")) {
    return `${cleaned}.NS`;
  }
  return cleaned;
}

function computeRSI(closes, period = RSI_PERIOD) {
  if (closes.length < period + 1) return null;

  let gains = 0;
  let losses = 0;

  // initial average over first `period` diffs
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff;
    else losses += Math.abs(diff);
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;
  const rsiSeries = [];

  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);
    rsiSeries.push(rsi);
  }

  return rsiSeries;
}

function classifySignal(latestRsi, prevRsi) {
  if (latestRsi == null || prevRsi == null) {
    return { label: "Not enough data", tone: "neutral" };
  }
  if (prevRsi <= OVERSOLD && latestRsi > OVERSOLD) {
    return { label: "SIGNAL: RSI exiting oversold", tone: "signal" };
  }
  if (prevRsi >= OVERBOUGHT && latestRsi < OVERBOUGHT) {
    return { label: "SIGNAL: RSI exiting overbought", tone: "signal" };
  }
  if (latestRsi < OVERSOLD) {
    return { label: "Watch: oversold, no cross yet", tone: "watch" };
  }
  if (latestRsi > OVERBOUGHT) {
    return { label: "Watch: overbought, no cross yet", tone: "watch" };
  }
  return { label: "No signal (neutral zone)", tone: "neutral" };
}

async function fetchSignalForSymbol(rawSymbol) {
  const yahooSymbol = toYahooSymbol(rawSymbol);
  const range = "6mo";
  const interval = "1d";
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahooSymbol)}?range=${range}&interval=${interval}`;

  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Yahoo Finance request failed (${resp.status}) for ${yahooSymbol}`);
  }
  const data = await resp.json();

  const result = data?.chart?.result?.[0];
  if (!result) {
    throw new Error(`No data returned for ${yahooSymbol}. Check the symbol.`);
  }

  const closes = result.indicators?.quote?.[0]?.close?.filter((c) => c != null);
  if (!closes || closes.length < RSI_PERIOD + 2) {
    throw new Error(`Not enough price history for ${yahooSymbol}.`);
  }

  const rsiSeries = computeRSI(closes, RSI_PERIOD);
  const latestRsi = rsiSeries[rsiSeries.length - 1];
  const prevRsi = rsiSeries[rsiSeries.length - 2];
  const latestClose = closes[closes.length - 1];

  const signal = classifySignal(latestRsi, prevRsi);

  return {
    symbol: rawSymbol,
    yahooSymbol,
    close: latestClose,
    rsi: latestRsi,
    signal: signal.label,
    tone: signal.tone,
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_SIGNAL") {
    fetchSignalForSymbol(message.symbol)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // keep the message channel open for async sendResponse
  }
});
