import yfinance as yf

from src.logging_utils import get_logger, log_skip

logger = get_logger(__name__)

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


def _first_available(row_names: list[str], statement) -> float | None:
    for name in row_names:
        if name in statement.index:
            series = statement.loc[name].dropna()
            if not series.empty:
                return series
    return None


def fetch_fundamentals(symbol: str) -> dict | None:
    """Fetch PE/EPS/ROE/margins/market cap from yfinance, plus ROCE and revenue growth
    computed by hand from raw statements (per CLAUDE.md: not pulled pre-built).
    Returns None (and logs) if yfinance has nothing for this symbol.
    """
    ticker = yf.Ticker(f"{symbol}.NS")

    try:
        info = ticker.info
    except Exception as exc:
        log_skip(logger, symbol, "fetch_fundamentals", f"yfinance .info raised {exc!r}")
        return None

    if not info or info.get("currentPrice") is None:
        log_skip(logger, symbol, "fetch_fundamentals", "yfinance returned no usable info")
        return None

    result: dict = {}
    for yf_key, out_key in INFO_FIELDS.items():
        value = info.get(yf_key)
        if value is None:
            log_skip(logger, symbol, "fetch_fundamentals", f"missing info field {yf_key}")
        result[out_key] = value

    result["roce"] = _compute_roce(symbol, ticker)
    result["revenue_growth_yoy"] = _compute_revenue_growth(symbol, ticker)

    return result


def _compute_roce(symbol: str, ticker: yf.Ticker) -> float | None:
    try:
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet
    except Exception as exc:
        log_skip(logger, symbol, "compute_roce", f"raw statements raised {exc!r}")
        return None

    ebit = _first_available(["EBIT"], income_stmt)
    total_assets = _first_available(["Total Assets"], balance_sheet)
    current_liabilities = _first_available(["Current Liabilities"], balance_sheet)

    if ebit is None or total_assets is None or current_liabilities is None:
        log_skip(symbol=symbol, logger=logger, stage="compute_roce", reason="missing EBIT/Total Assets/Current Liabilities")
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


def _compute_revenue_growth(symbol: str, ticker: yf.Ticker) -> float | None:
    try:
        income_stmt = ticker.income_stmt
    except Exception as exc:
        log_skip(logger, symbol, "compute_revenue_growth", f"raw statements raised {exc!r}")
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
        data = fetch_fundamentals(test_symbol)
        logger.info("%s fundamentals: %s", test_symbol, data)
