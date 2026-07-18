/**
 * content.js
 *
 * Runs on Angel One's web pages. Tries to detect the currently-open stock
 * symbol using a few heuristics (page title, common DOM patterns), then
 * asks the background worker for the RSI signal and shows it in a floating
 * widget.
 *
 * IMPORTANT: Angel One's exact page structure isn't something I can see
 * from here, so the DETECT_SYMBOL heuristics below are best-effort guesses.
 * If auto-detection doesn't find the right symbol, use the widget's manual
 * input to type it in directly -- and tell me what you see so I can tighten
 * the detection logic.
 */

let widgetEl = null;
let lastDetectedSymbol = null;

function createWidget() {
  if (widgetEl) return widgetEl;

  widgetEl = document.createElement("div");
  widgetEl.id = "sss-widget";
  widgetEl.innerHTML = `
    <div id="sss-header">
      <span id="sss-title">Signal Scanner</span>
      <button id="sss-close" title="Close">&times;</button>
    </div>
    <div id="sss-body">
      <div id="sss-symbol-row">
        <input id="sss-symbol-input" type="text" placeholder="e.g. RELIANCE" />
        <button id="sss-scan-btn">Scan</button>
      </div>
      <div id="sss-result">Detecting symbol...</div>
      <div id="sss-disclaimer">
        Rule-based technical signal, not a prediction. Not financial advice.
      </div>
    </div>
  `;
  document.body.appendChild(widgetEl);

  document.getElementById("sss-close").addEventListener("click", () => {
    widgetEl.style.display = "none";
  });

  document.getElementById("sss-scan-btn").addEventListener("click", () => {
    const val = document.getElementById("sss-symbol-input").value.trim();
    if (val) scanSymbol(val);
  });

  document.getElementById("sss-symbol-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const val = e.target.value.trim();
      if (val) scanSymbol(val);
    }
  });

  return widgetEl;
}

function setResult(html, tone = "neutral") {
  const resultEl = document.getElementById("sss-result");
  if (!resultEl) return;
  resultEl.innerHTML = html;
  resultEl.className = `sss-tone-${tone}`;
}

function scanSymbol(symbol) {
  setResult(`Scanning ${symbol}...`, "neutral");
  chrome.runtime.sendMessage({ type: "GET_SIGNAL", symbol }, (response) => {
    if (!response) {
      setResult("No response from background worker.", "neutral");
      return;
    }
    if (!response.ok) {
      setResult(`Error: ${response.error}`, "neutral");
      return;
    }
    const r = response.result;
    setResult(
      `<strong>${r.symbol}</strong> (${r.yahooSymbol})<br/>
       Close: ${r.close?.toFixed(2)} &nbsp; RSI(14): ${r.rsi?.toFixed(1)}<br/>
       <span class="sss-signal-label">${r.signal}</span>`,
      r.tone
    );
  });
}

/**
 * Heuristic symbol detection. Tries, in order:
 *   1. A page title pattern like "RELIANCE - Angel One" or similar
 *   2. Common Angel One DOM selectors (guessed -- likely to need adjustment)
 * Falls back to null if nothing matches, and the widget just waits for
 * manual entry.
 */
function detectSymbol() {
  // Heuristic 1: document title often contains the symbol
  const title = document.title || "";
  const titleMatch = title.match(/^([A-Z][A-Z0-9&\-]{1,15})\b/);
  if (titleMatch) return titleMatch[1];

  // Heuristic 2: look for elements that commonly hold a scrip/symbol name
  // (class names are guesses -- adjust once you inspect the actual page)
  const candidateSelectors = [
    "[class*='scripName']",
    "[class*='symbol-name']",
    "[class*='instrument-name']",
    "[data-testid*='symbol']",
    "h1",
  ];

  for (const sel of candidateSelectors) {
    const el = document.querySelector(sel);
    if (el && el.textContent) {
      const text = el.textContent.trim();
      const match = text.match(/^([A-Z][A-Z0-9&\-]{1,15})\b/);
      if (match) return match[1];
    }
  }

  return null;
}

function tryAutoDetect() {
  const symbol = detectSymbol();
  if (symbol && symbol !== lastDetectedSymbol) {
    lastDetectedSymbol = symbol;
    document.getElementById("sss-symbol-input").value = symbol;
    scanSymbol(symbol);
  } else if (!symbol) {
    setResult("Couldn't auto-detect a symbol. Type one above and hit Scan.", "neutral");
  }
}

function init() {
  createWidget();
  tryAutoDetect();

  // Angel One is likely a single-page app -- URL/DOM changes without full
  // reload when you switch stocks. Re-check periodically for a new symbol.
  setInterval(tryAutoDetect, 4000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
