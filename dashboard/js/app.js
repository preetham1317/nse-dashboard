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
  loadAllStocks,
  flagCountClass,
  pillStatusClass,
  formatPrice,
  formatChangePct,
  flagShortLabel,
  formatUpdatedAt,
};
