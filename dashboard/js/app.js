const DATA_BASE = "../data/output";

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`failed to fetch ${path}: ${response.status}`);
  }
  return response.json();
}

async function loadMeta() {
  return fetchJson(`${DATA_BASE}/meta.json`);
}

async function loadFlagDefinitions() {
  return fetchJson(`${DATA_BASE}/flag_definitions.json`);
}

async function loadPortfolio() {
  return fetchJson(`${DATA_BASE}/portfolio.json`);
}

async function loadSectors() {
  return fetchJson(`${DATA_BASE}/sectors.json`);
}

async function loadStock(symbol) {
  return fetchJson(`${DATA_BASE}/stocks/${symbol}.json`);
}

async function loadAllStocks(meta) {
  const symbols = Object.entries(meta.symbols)
    .filter(([, info]) => info.status === "ok")
    .map(([symbol]) => symbol);
  const stocks = await Promise.all(
    symbols.map((symbol) => fetchJson(`${DATA_BASE}/stocks/${symbol}.json`))
  );
  return stocks;
}

function flagCountClass(count, total) {
  const ratio = count / total;
  if (ratio >= 0.625) return "strong"; // 5/8+
  if (ratio >= 0.375) return "mid"; // 3-4/8
  return "weak";
}

function pillStatusClass(count, total) {
  const ratio = count / total;
  if (ratio >= 0.625) return "ok";
  if (ratio >= 0.375) return "watch";
  return "review";
}

function formatPrice(value) {
  if (value === null || value === undefined) return "—";
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function formatChangePct(value) {
  if (value === null || value === undefined) return { text: "—", cls: "flat" };
  const cls = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "→";
  return { text: `${arrow} ${Math.abs(value).toFixed(2)}%`, cls };
}

function flagShortLabel(flagDefinitions, key) {
  const def = flagDefinitions.find((d) => d.key === key);
  return def ? def.label : key;
}

function sectorBarClass(avgFlagPct) {
  if (avgFlagPct >= 62.5) return "";
  if (avgFlagPct >= 37.5) return "mid";
  return "weak";
}

function kvGridHtml(entries) {
  return `<div class="kv-grid">${entries
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([label, value]) => `<div class="kv"><div class="k">${label}</div><div class="v">${value}</div></div>`)
    .join("")}</div>`;
}

function renderDetailPanelHtml(stock, flagDefinitions) {
  const checkRows = flagDefinitions
    .map((def) => {
      const isOn = stock.flags.flags[def.key];
      const detail = stock.flags.flags_detail[def.key];
      return `<div class="check-row">
        <span class="mark ${isOn ? "pass" : "fail"}">${isOn ? "✓" : "✗"}</span>
        <span class="label">${def.label} — ${detail}</span>
      </div>`;
    })
    .join("");

  const ind = stock.indicators;
  const indicatorsHtml = kvGridHtml([
    ["Close", formatPrice(ind.close)],
    ["EMA20", formatPrice(ind.ema20)],
    ["EMA50", formatPrice(ind.ema50)],
    ["EMA200", formatPrice(ind.ema200)],
    ["RSI(14)", ind.rsi14?.toFixed(2)],
    ["MACD", ind.macd?.toFixed(2)],
    ["MACD signal", ind.macd_signal?.toFixed(2)],
    ["ATR(14)", ind.atr14?.toFixed(2)],
    ["ADX(14)", ind.adx14?.toFixed(2)],
    ["+DI", ind.adx_pos?.toFixed(2)],
    ["-DI", ind.adx_neg?.toFixed(2)],
    ["BB high", formatPrice(ind.bb_high)],
    ["BB mid", formatPrice(ind.bb_mid)],
    ["BB low", formatPrice(ind.bb_low)],
    ["VWAP(20)", formatPrice(ind.vwap20)],
  ]);

  let fundamentalsHtml = "";
  if (stock.fundamentals) {
    const f = stock.fundamentals;
    fundamentalsHtml = `<div class="detail-section"><h6>Fundamentals</h6>${kvGridHtml([
      ["PE (trailing)", f.pe_trailing?.toFixed(2)],
      ["PE (forward)", f.pe_forward?.toFixed(2)],
      ["EPS (trailing)", f.eps_trailing],
      ["ROE", f.roe !== null && f.roe !== undefined ? `${(f.roe * 100).toFixed(1)}%` : null],
      ["ROCE", f.roce !== null && f.roce !== undefined ? `${(f.roce * 100).toFixed(1)}%` : null],
      ["Profit margin", f.profit_margin !== null && f.profit_margin !== undefined ? `${(f.profit_margin * 100).toFixed(1)}%` : null],
      ["Revenue growth YoY", f.revenue_growth_yoy !== null && f.revenue_growth_yoy !== undefined ? `${(f.revenue_growth_yoy * 100).toFixed(1)}%` : null],
      ["Market cap", f.market_cap ? `₹${(f.market_cap / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr` : null],
    ])}</div>`;
  } else {
    fundamentalsHtml = `<div class="detail-section"><h6>Fundamentals</h6><span class="empty-note">Not available this run.</span></div>`;
  }

  let shareholdingHtml = "";
  if (stock.shareholding) {
    shareholdingHtml = `<div class="detail-section"><h6>Shareholding change</h6>${kvGridHtml([
      ["Promoter", stock.shareholding.promoter_holding_change_pct],
      ["FII", stock.shareholding.fii_holding_change_pct],
      ["DII", stock.shareholding.dii_holding_change_pct],
    ])}</div>`;
  } else {
    shareholdingHtml = `<div class="detail-section"><h6>Shareholding change</h6><span class="empty-note">Not available this run (NSE source often blocks automated requests).</span></div>`;
  }

  return `
    <div class="detail-section"><h6>Why ${stock.flags.flag_count}/${stock.flags.flag_total}</h6>${checkRows}</div>
    <div class="detail-section"><h6>Indicators (${ind.date})</h6>${indicatorsHtml}</div>
    ${fundamentalsHtml}
    ${shareholdingHtml}
  `;
}

function attachRowToggle(container, rowEl, stock, flagDefinitions) {
  rowEl.addEventListener("click", () => {
    const existingPanel = container.querySelector(".detail-panel");
    const wasOpen = existingPanel !== null;
    if (existingPanel) existingPanel.remove();
    container.classList.toggle("expanded", !wasOpen);
    if (wasOpen) return;

    const panel = document.createElement("div");
    panel.className = "detail-panel";
    panel.innerHTML = renderDetailPanelHtml(stock, flagDefinitions);
    container.appendChild(panel);
  });
}

function formatUpdatedAt(isoString) {
  if (!isoString) return "unknown";
  const date = new Date(isoString);
  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  });
}

window.dashboardUtils = {
  loadMeta,
  loadFlagDefinitions,
  loadPortfolio,
  loadSectors,
  loadStock,
  loadAllStocks,
  flagCountClass,
  pillStatusClass,
  sectorBarClass,
  formatPrice,
  formatChangePct,
  flagShortLabel,
  renderDetailPanelHtml,
  attachRowToggle,
  formatUpdatedAt,
};
