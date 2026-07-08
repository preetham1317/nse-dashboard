from datetime import datetime, timedelta

import pandas as pd
from SmartApi import SmartConnect

from src.logging_utils import get_logger, log_skip

logger = get_logger(__name__)

LOOKBACK_DAYS = 450  # comfortably covers EMA200 + ATR/ADX warmup on trading days
OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def fetch_daily_ohlcv(smart_connect: SmartConnect, symbol: str, symboltoken: str) -> pd.DataFrame | None:
    """Fetch daily OHLCV candles for one symbol. Returns None (and logs) on any failure."""
    to_date = datetime.now()
    from_date = to_date - timedelta(days=LOOKBACK_DAYS)

    params = {
        "exchange": "NSE",
        "symboltoken": symboltoken,
        "interval": "ONE_DAY",
        "fromdate": from_date.strftime("%Y-%m-%d 09:00"),
        "todate": to_date.strftime("%Y-%m-%d 15:30"),
    }

    try:
        response = smart_connect.getCandleData(params)
    except Exception as exc:  # SmartAPI raises assorted exceptions on network/auth failure
        log_skip(logger, symbol, "fetch_ohlcv", f"getCandleData raised {exc!r}")
        return None

    if not response or not response.get("status"):
        message = response.get("message") if response else "no response"
        log_skip(logger, symbol, "fetch_ohlcv", f"API returned failure: {message}")
        return None

    rows = response.get("data") or []
    if not rows:
        log_skip(logger, symbol, "fetch_ohlcv", "API returned zero candles")
        return None

    df = pd.DataFrame(rows, columns=OHLCV_COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col])
    df = df.sort_values("date").reset_index(drop=True)

    logger.info(
        "fetched %d daily candles for symbol=%s (%s -> %s)",
        len(df),
        symbol,
        df["date"].iloc[0].date(),
        df["date"].iloc[-1].date(),
    )
    return df


if __name__ == "__main__":
    from src.angel_auth import login
    from src.instrument_master import build_nse_equity_token_map, get_token

    conn, _ = login()
    token_map = build_nse_equity_token_map()

    for test_symbol in ("RELIANCE", "TCS", "INFY"):
        tok = get_token(test_symbol, token_map)
        if tok is None:
            continue
        candles = fetch_daily_ohlcv(conn, test_symbol, tok)
        if candles is not None:
            logger.info("%s tail:\n%s", test_symbol, candles.tail(3).to_string(index=False))
