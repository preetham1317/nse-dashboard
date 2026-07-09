import json
import time
from datetime import datetime, timezone

import yfinance as yf

from src import config
from src.logging_utils import get_logger, log_skip

logger = get_logger(__name__)

# yfinance rate-limits hard when hammered in a tight loop (this was exactly why every
# symbol showed "fundamentals not available"). Three defences, all logged, no silent
# fallbacks (CLAUDE.md logging discipline):
#   1. throttle  - minimum gap between network hits so we never burst
#   2. retry     - exponential backoff on transient/rate-limit failures
#   3. disk cache- fundamentals change quarterly, so a ~7-day cache both slashes the
#                  request volume and lets us fall back to the last good values if a
#                  fetch fails this run instead of dropping the section entirely.
_MIN_INTERVAL_SEC = 1.5
_MAX_RETRIES = 3
_CACHE_TTL_SEC = 7 * 24 * 3600
_CACHE_DIR = config.CACHE_DIR / "fundamentals"

_last_call_ts = 0.0

INFO_FIELDS = {
    "trailingPE": "pe_trailing",
    "forwardPE": "pe_forward",
    "trailingEps": "eps_trailing",
    "forwardEps": "eps_forward",
    "returnOnEquity": "roe",
    "profitMargins": "profit_margin",
    "grossMargins": "gross_margin",
    "operatingMargins": "operating_margin",
    "marketCap": "market_cap",
    "currentPrice": "current_price",
    "sector": "sector",
    "longName": "name",
}

# External analyst consensus. This is third-party opinion shown as-is and clearly
# labelled in the UI - the dashboard never derives its own buy/hold/sell verdict from it
# (CLAUDE.md "never a single verdict" rule).
ANALYST_FIELDS = {
    "recommendationKey": "recommendation",
    "recommendationMean": "recommendation_mean",
    "numberOfAnalystOpinions": "num_analysts",
    "targetLowPrice": "target_low",
    "targetMeanPrice": "target_mean",
    "targetMedianPrice": "target_median",
    "targetHighPrice": "target_high",
}


def _throttle() -> None:
    global _last_call_ts
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < _MIN_INTERVAL_SEC:
        time.sleep(_MIN_INTERVAL_SEC - elapsed)
    _last_call_ts = time.monotonic()


def _cache_path(symbol: str):
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{symbol}.json"


def _read_cache(symbol: str) -> dict | None:
    path = _cache_path(symbol)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log_skip(logger, symbol, "fundamentals_cache", f"unreadable cache: {exc!r}")
        return None


def _write_cache(symbol: str, view: dict) -> None:
    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "view": view}
    try:
        _cache_path(symbol).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        log_skip(logger, symbol, "fundamentals_cache", f"could not write cache: {exc!r}")


def _fetch_info(symbol: str, ticker: yf.Ticker) -> dict | None:
    """ticker.info with throttle + retry/backoff. Returns None (and logs) if unusable."""
    for attempt in range(1, _MAX_RETRIES + 1):
        _throttle()
        try:
            info = ticker.info
        except Exception as exc:
            wait = _MIN_INTERVAL_SEC * (2 ** attempt)
            log_skip(logger, symbol, "fetch_fundamentals", f"info raised {exc!r} (attempt {attempt}/{_MAX_RETRIES}, backoff {wait:.1f}s)")
            time.sleep(wait)
            continue
        if info and info.get("currentPrice") is not None:
            return info
        wait = _MIN_INTERVAL_SEC * (2 ** attempt)
        log_skip(logger, symbol, "fetch_fundamentals", f"empty/unusable info (attempt {attempt}/{_MAX_RETRIES}, backoff {wait:.1f}s)")
        time.sleep(wait)
    return None


def fetch_market_view(symbol: str) -> dict:
    """Returns {"fundamentals": dict|None, "analyst": dict|None}.

    Serves the cached copy when it is fresh, otherwise fetches from yfinance and
    refreshes the cache. On a failed fetch it falls back to a stale cache (logged) so
    the dashboard keeps the last known fundamentals rather than showing nothing.
    """
    cached = _read_cache(symbol)
    if cached:
        try:
            age = time.time() - datetime.fromisoformat(cached["fetched_at"]).timestamp()
        except (KeyError, ValueError):
            age = None
        if age is not None and age < _CACHE_TTL_SEC:
            return cached["view"]

    ticker = yf.Ticker(f"{symbol}.NS")
    info = _fetch_info(symbol, ticker)

    if info is None:
        if cached:
            log_skip(logger, symbol, "fetch_fundamentals", "fetch failed; serving stale cached fundamentals")
            return cached["view"]
        return {"fundamentals": None, "analyst": None}

    fundamentals = _build_fundamentals(symbol, ticker, info)
    analyst = _build_analyst(info)
    view = {"fundamentals": fundamentals, "analyst": analyst}
    _write_cache(symbol, view)
    return view


def _build_fundamentals(symbol: str, ticker: yf.Ticker, info: dict) -> dict:
    result: dict = {}
    for yf_key, out_key in INFO_FIELDS.items():
        value = info.get(yf_key)
        if value is None:
            log_skip(logger, symbol, "fetch_fundamentals", f"missing info field {yf_key}")
        result[out_key] = value

    # Fetch the raw statements once and reuse for both ROCE and revenue growth.
    income_stmt, balance_sheet = _statements(symbol, ticker)
    result["roce"] = _compute_roce(symbol, income_stmt, balance_sheet)
    result["revenue_growth_yoy"] = _compute_revenue_growth(symbol, income_stmt)
    return result


def _build_analyst(info: dict) -> dict | None:
    num = info.get("numberOfAnalystOpinions")
    if not num:  # no coverage -> nothing to show, and no verdict to invent
        return None
    return {out_key: info.get(yf_key) for yf_key, out_key in ANALYST_FIELDS.items()}


def fetch_fundamentals(symbol: str) -> dict | None:
    """Backwards-compatible helper: just the fundamentals half of the market view."""
    return fetch_market_view(symbol)["fundamentals"]


def _first_available(row_names: list[str], statement) -> float | None:
    for name in row_names:
        if name in statement.index:
            series = statement.loc[name].dropna()
            if not series.empty:
                return series
    return None


def _statements(symbol: str, ticker: yf.Ticker) -> tuple:
    """(income_stmt, balance_sheet) with throttle; returns (None, None) on failure."""
    _throttle()
    try:
        return ticker.income_stmt, ticker.balance_sheet
    except Exception as exc:
        log_skip(logger, symbol, "raw_statements", f"raised {exc!r}")
        return None, None


def _compute_roce(symbol: str, income_stmt, balance_sheet) -> float | None:
    if income_stmt is None or balance_sheet is None:
        return None

    ebit = _first_available(["EBIT"], income_stmt)
    total_assets = _first_available(["Total Assets"], balance_sheet)
    current_liabilities = _first_available(["Current Liabilities"], balance_sheet)

    if ebit is None or total_assets is None or current_liabilities is None:
        log_skip(logger, symbol, "compute_roce", "missing EBIT/Total Assets/Current Liabilities")
        return None

    latest_period = ebit.index[0]
    if latest_period not in total_assets.index or latest_period not in current_liabilities.index:
        log_skip(logger, symbol, "compute_roce", "statement periods don't align")
        return None

    capital_employed = total_assets[latest_period] - current_liabilities[latest_period]
    if capital_employed <= 0:
        log_skip(logger, symbol, "compute_roce", f"non-positive capital employed: {capital_employed}")
        return None

    return float(ebit[latest_period] / capital_employed)


def _compute_revenue_growth(symbol: str, income_stmt) -> float | None:
    if income_stmt is None:
        return None

    revenue = _first_available(["Total Revenue"], income_stmt)
    if revenue is None or len(revenue) < 2:
        log_skip(logger, symbol, "compute_revenue_growth", "fewer than 2 years of Total Revenue")
        return None

    latest, previous = revenue.iloc[0], revenue.iloc[1]
    if previous == 0:
        log_skip(logger, symbol, "compute_revenue_growth", "previous year revenue is zero")
        return None

    return float((latest - previous) / previous)


if __name__ == "__main__":
    for test_symbol in ("RELIANCE", "TCS", "INFY"):
        view = fetch_market_view(test_symbol)
        logger.info("%s -> %s", test_symbol, view)
