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

function formatVolume(value) {
  if (value === null || value === undefined) return "—";
  if (value >= 1e7) return `${(value / 1e7).toFixed(2)} Cr`;
  if (value >= 1e5) return `${(value / 1e5).toFixed(2)} L`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)} K`;
  return `${Math.round(value)}`;
}

// Inline SVG line chart (close + EMA50). No chart library — keeps the dashboard
// dependency-free and works offline on GitHub Pages. Non-scaling strokes keep the
// line crisp even though the SVG stretches to the panel width.
function buildPriceChartSvg(history) {
  if (!Array.isArray(history) || history.length < 2) return "";
  const closes = history.map((h) => h.close);
  const emas = history.map((h) => (h.ema50 === null || h.ema50 === undefined ? null : h.ema50));
  const values = closes.concat(emas.filter((v) => v !== null));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 320, H = 90, pad = 4;
  const xAt = (i) => pad + (i / (history.length - 1)) * (W - 2 * pad);
  const yAt = (v) => pad + (1 - (v - min) / span) * (H - 2 * pad);
  const closePts = closes.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
  const emaPts = emas
    .map((v, i) => (v === null ? null : `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`))
    .filter(Boolean)
    .join(" ");
  const rising = closes[closes.length - 1] >= closes[0];
  const stroke = rising ? "var(--teal)" : "var(--rose)";
  const areaFill = rising ? "rgba(31,122,99,0.10)" : "rgba(168,64,58,0.10)";
  const area = `${pad},${H - pad} ${closePts} ${(W - pad).toFixed(1)},${H - pad}`;
  return `<svg class="price-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Recent price line chart">
    <polygon points="${area}" fill="${areaFill}"></polygon>
    ${emaPts ? `<polyline points="${emaPts}" fill="none" stroke="var(--amber)" stroke-width="1" stroke-dasharray="3 3" opacity="0.75" vector-effect="non-scaling-stroke"></polyline>` : ""}
    <polyline points="${closePts}" fill="none" stroke="${stroke}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"></polyline>
  </svg>`;
}

function priceChartSectionHtml(stock) {
  const history = stock.price_history;
  if (!Array.isArray(history) || history.length < 2) {
    return `<div class="detail-section"><h6>Price trend</h6><span class="empty-note">Chart available after the next pipeline run.</span></div>`;
  }
  const first = history[0].date;
  const last = history[history.length - 1].date;
  return `<div class="detail-section">
    <h6>Price trend · last ${history.length} sessions</h6>
    <div class="chart-wrap">${buildPriceChartSvg(history)}</div>
    <div class="chart-legend">
      <span><i class="swatch close"></i> Close</span>
      <span><i class="swatch ema"></i> EMA50</span>
      <span class="range mono">${first} → ${last}</span>
    </div>
  </div>`;
}

function rangeSectionHtml(ind) {
  if (ind.low_52w === null || ind.low_52w === undefined || ind.high_52w === null || ind.high_52w === undefined) {
    return "";
  }
  const span = ind.high_52w - ind.low_52w || 1;
  const pos = Math.max(0, Math.min(100, ((ind.close - ind.low_52w) / span) * 100));
  const fromLow = (((ind.close - ind.low_52w) / ind.low_52w) * 100).toFixed(1);
  const fromHigh = (((ind.close - ind.high_52w) / ind.high_52w) * 100).toFixed(1);
  return `<div class="detail-section">
    <h6>52-week range</h6>
    <div class="range-row">
      <span class="range-end mono">${formatPrice(ind.low_52w)}</span>
      <div class="range-track"><div class="range-marker" style="left:${pos.toFixed(1)}%"></div></div>
      <span class="range-end mono">${formatPrice(ind.high_52w)}</span>
    </div>
    <div class="range-sub">Now ${formatPrice(ind.close)} · <span class="up">+${fromLow}%</span> from low · <span class="down">${fromHigh}%</span> from high</div>
  </div>`;
}

const ANALYST_LABELS = {
  strong_buy: "Strong Buy",
  buy: "Buy",
  hold: "Hold",
  underperform: "Underperform",
  sell: "Sell",
};

function analystClass(rec) {
  if (rec === "strong_buy" || rec === "buy") return "ok";
  if (rec === "hold") return "watch";
  if (rec === "underperform" || rec === "sell") return "review";
  return "watch";
}

// External third-party analyst consensus, shown as-is and clearly labelled. The dashboard
// never turns this (or the flags) into its own buy/hold/sell verdict — CLAUDE.md hard rule.
function analystSectionHtml(stock) {
  const a = stock.analyst;
  if (!a) {
    return `<div class="detail-section"><h6>Analyst view <span class="ext-tag">external</span></h6><span class="empty-note">No analyst coverage available this run.</span></div>`;
  }
  const label = ANALYST_LABELS[a.recommendation] || (a.recommendation || "—");
  const cls = analystClass(a.recommendation);
  const close = stock.indicators.close;

  let targetHtml = "";
  if (a.target_low != null && a.target_high != null && a.target_mean != null) {
    const span = a.target_high - a.target_low || 1;
    const meanPos = Math.max(0, Math.min(100, ((a.target_mean - a.target_low) / span) * 100));
    const nowPos = Math.max(0, Math.min(100, ((close - a.target_low) / span) * 100));
    const upside = (((a.target_mean - close) / close) * 100).toFixed(1);
    const upsideCls = a.target_mean >= close ? "up" : "down";
    targetHtml = `
      <div class="target-row">
        <span class="range-end mono">${formatPrice(a.target_low)}</span>
        <div class="range-track target">
          <div class="range-tick now" style="left:${nowPos.toFixed(1)}%" title="Current price"></div>
          <div class="range-marker mean" style="left:${meanPos.toFixed(1)}%" title="Mean target"></div>
        </div>
        <span class="range-end mono">${formatPrice(a.target_high)}</span>
      </div>
      <div class="range-sub">Mean target ${formatPrice(a.target_mean)} · <span class="${upsideCls}">${a.target_mean >= close ? "+" : ""}${upside}%</span> vs current · ● now ◆ target</div>`;
  }

  return `<div class="detail-section">
    <h6>Analyst view <span class="ext-tag">external · third-party opinion, not this dashboard's</span></h6>
    <div class="analyst-head">
      <span class="pill-status ${cls}">${label}</span>
      <span class="analyst-meta mono">${a.num_analysts != null ? `${a.num_analysts} analysts` : ""}${a.recommendation_mean != null ? ` · mean ${a.recommendation_mean.toFixed(2)}/5` : ""}</span>
    </div>
    ${targetHtml}
  </div>`;
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
    ["Volume", formatVolume(ind.volume)],
    ["Avg vol (20d)", formatVolume(ind.avg_volume20)],
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
    ${priceChartSectionHtml(stock)}
    ${rangeSectionHtml(ind)}
    <div class="detail-section"><h6>Why ${stock.flags.flag_count}/${stock.flags.flag_total}</h6>${checkRows}</div>
    <div class="detail-section"><h6>Indicators (${ind.date})</h6>${indicatorsHtml}</div>
    ${fundamentalsHtml}
    ${analystSectionHtml(stock)}
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

const FAVORITES_KEY = "nse-dashboard-favorites";

function getFavorites() {
  try {
    return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function isFavorite(symbol) {
  return getFavorites().has(symbol);
}

function toggleFavorite(symbol) {
  const favs = getFavorites();
  if (favs.has(symbol)) {
    favs.delete(symbol);
  } else {
    favs.add(symbol);
  }
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(Array.from(favs)));
  return favs.has(symbol);
}

function filterFavorites(stocks) {
  const favs = getFavorites();
  return stocks.filter((stock) => favs.has(stock.symbol));
}

function createStockBlock(stock, rank, flagDefinitions, options = {}) {
  const { flag_count, flag_total, flags_on } = stock.flags;
  const change = formatChangePct(stock.indicators.change_pct);
  const topFlags = flags_on.slice(0, 3).map((k) => flagShortLabel(flagDefinitions, k)).join(" · ");

  const block = document.createElement("div");
  block.className = "stock-block";

  const row = document.createElement("div");
  row.className = "stock-row";
  row.innerHTML = `
    <div class="left">
      <button type="button" class="star-btn" aria-label="Toggle favorite" title="Favorite"></button>
      <div class="rank">${rank}</div>
      <div>
        <div class="name">${stock.symbol}<span class="sector">${stock.sector || ""}</span></div>
        <div class="flags-mini">
          <span class="flag-count ${flagCountClass(flag_count, flag_total)}">${flag_count}/${flag_total}</span>
          ${topFlags ? " · " + topFlags : " · no bullish flags fired"}
        </div>
      </div>
    </div>
    <div class="right">
      <div class="price">${formatPrice(stock.indicators.close)}</div>
      <div class="chg ${change.cls}">${change.text}</div>
    </div>
  `;

  const starBtn = row.querySelector(".star-btn");
  const applyStarState = (fav) => {
    starBtn.textContent = fav ? "★" : "☆";
    starBtn.classList.toggle("active", fav);
  };
  applyStarState(isFavorite(stock.symbol));
  starBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const nowFav = toggleFavorite(stock.symbol);
    applyStarState(nowFav);
    if (options.onFavoriteToggle) options.onFavoriteToggle(stock.symbol, nowFav);
  });

  block.appendChild(row);
  attachRowToggle(block, row, stock, flagDefinitions);
  return block;
}

function filterStocksByQuery(stocks, query) {
  if (!query) return stocks;
  const q = query.toLowerCase();
  return stocks.filter(
    (stock) =>
      stock.symbol.toLowerCase().includes(q) ||
      (stock.name && stock.name.toLowerCase().includes(q)) ||
      (stock.sector && stock.sector.toLowerCase().includes(q))
  );
}

function renderStockListInto(container, stocks, flagDefinitions, options = {}) {
  container.innerHTML = "";
  stocks.forEach((stock, index) => {
    container.appendChild(createStockBlock(stock, index + 1, flagDefinitions, options));
  });
}

function renderSectorGroupsInto(container, stocks, flagDefinitions, options = {}) {
  const forceExpand = !!options.forceExpand;
  container.innerHTML = "";
  const groups = new Map();
  stocks.forEach((stock) => {
    const sector = stock.sector || "Uncategorized";
    if (!groups.has(sector)) groups.set(sector, []);
    groups.get(sector).push(stock);
  });

  const sectorNames = Array.from(groups.keys()).sort((a, b) => {
    const avgA = groups.get(a).reduce((s, st) => s + st.flags.flag_count / st.flags.flag_total, 0) / groups.get(a).length;
    const avgB = groups.get(b).reduce((s, st) => s + st.flags.flag_count / st.flags.flag_total, 0) / groups.get(b).length;
    return avgB - avgA;
  });

  sectorNames.forEach((sector) => {
    const sectorStocks = groups.get(sector).sort((a, b) => b.flags.flag_count - a.flags.flag_count);
    const group = document.createElement("div");
    group.className = "sector-group" + (forceExpand ? "" : " collapsed");

    const header = document.createElement("div");
    header.className = "sector-group-header";
    header.innerHTML = `
      <span class="name"><span class="chevron">▸</span> ${sector}</span>
      <span class="meta">${sectorStocks.length} stock${sectorStocks.length === 1 ? "" : "s"}</span>
    `;
    header.addEventListener("click", () => group.classList.toggle("collapsed"));
    group.appendChild(header);

    const list = document.createElement("div");
    list.className = "sector-group-body";
    sectorStocks.forEach((stock, index) => list.appendChild(createStockBlock(stock, index + 1, flagDefinitions, options)));
    group.appendChild(list);
    container.appendChild(group);
  });
}

function initTabs(tabBarEl, onChange) {
  const buttons = Array.from(tabBarEl.querySelectorAll(".tab-btn"));
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("active")) return;
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      onChange(btn.dataset.tab);
    });
  });
}

function initRefreshButton(buttonEl, renderFn) {
  buttonEl.addEventListener("click", async () => {
    if (buttonEl.classList.contains("is-loading")) return;
    const icon = buttonEl.querySelector(".icon");
    const label = buttonEl.querySelector(".label");
    const originalLabel = label ? label.textContent : "";
    buttonEl.classList.add("is-loading");
    if (icon) icon.classList.add("spin");
    if (label) label.textContent = "Refreshing…";
    try {
      await renderFn();
    } catch (err) {
      console.error(err);
    } finally {
      buttonEl.classList.remove("is-loading");
      if (icon) icon.classList.remove("spin");
      if (label) label.textContent = originalLabel;
    }
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
  filterStocksByQuery,
  filterFavorites,
  isFavorite,
  toggleFavorite,
  createStockBlock,
  renderStockListInto,
  renderSectorGroupsInto,
  initTabs,
  initRefreshButton,
  formatUpdatedAt,
};
