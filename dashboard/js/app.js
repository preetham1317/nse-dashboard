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

function createStockBlock(stock, rank, flagDefinitions) {
  const { flag_count, flag_total, flags_on } = stock.flags;
  const change = formatChangePct(stock.indicators.change_pct);
  const topFlags = flags_on.slice(0, 3).map((k) => flagShortLabel(flagDefinitions, k)).join(" · ");

  const block = document.createElement("div");
  block.className = "stock-block";

  const row = document.createElement("div");
  row.className = "stock-row";
  row.innerHTML = `
    <div class="left">
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

function renderStockListInto(container, stocks, flagDefinitions) {
  container.innerHTML = "";
  stocks.forEach((stock, index) => {
    container.appendChild(createStockBlock(stock, index + 1, flagDefinitions));
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
    sectorStocks.forEach((stock, index) => list.appendChild(createStockBlock(stock, index + 1, flagDefinitions)));
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
  createStockBlock,
  renderStockListInto,
  renderSectorGroupsInto,
  initTabs,
  initRefreshButton,
  formatUpdatedAt,
};
