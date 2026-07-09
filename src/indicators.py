import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice

from src.logging_utils import get_logger, log_skip

logger = get_logger(__name__)

MIN_ROWS_REQUIRED = 210  # EMA200 needs 200 periods; keep a small warmup buffer


def compute_indicators(symbol: str, ohlcv: pd.DataFrame) -> pd.DataFrame | None:
    """Appends indicator columns to a copy of the OHLCV frame. Returns None (and logs) if
    there isn't enough history to compute the long-window indicators (EMA200 in particular).
    """
    if len(ohlcv) < MIN_ROWS_REQUIRED:
        log_skip(
            logger,
            symbol,
            "compute_indicators",
            f"only {len(ohlcv)} rows available, need at least {MIN_ROWS_REQUIRED}",
        )
        return None

    df = ohlcv.copy()
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]

    df["ema20"] = EMAIndicator(close, window=20).ema_indicator()
    df["ema50"] = EMAIndicator(close, window=50).ema_indicator()
    df["ema200"] = EMAIndicator(close, window=200).ema_indicator()

    df["rsi14"] = RSIIndicator(close, window=14).rsi()

    macd = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    df["atr14"] = AverageTrueRange(high, low, close, window=14).average_true_range()

    adx = ADXIndicator(high, low, close, window=14)
    df["adx14"] = adx.adx()
    df["adx_pos"] = adx.adx_pos()
    df["adx_neg"] = adx.adx_neg()

    bollinger = BollingerBands(close, window=20, window_dev=2)
    df["bb_high"] = bollinger.bollinger_hband()
    df["bb_low"] = bollinger.bollinger_lband()
    df["bb_mid"] = bollinger.bollinger_mavg()

    # Literal same-day VWAP resets intraday and isn't meaningful on daily EOD candles;
    # this is a 20-day rolling volume-weighted average price used as the swing-trading proxy.
    df["vwap20"] = VolumeWeightedAveragePrice(high, low, close, volume, window=20).volume_weighted_average_price()

    return df


TRADING_DAYS_52W = 252  # ~52 weeks of trading sessions


def latest_indicator_snapshot(df: pd.DataFrame) -> dict:
    row = df.iloc[-1]
    prev_close = float(df.iloc[-2]["close"]) if len(df) >= 2 else None
    close = float(row["close"])
    change_pct = ((close - prev_close) / prev_close * 100) if prev_close else None

    # 52-week range and volume context, computed locally from the OHLCV we already have
    # (more reliable than a second data source, per CLAUDE.md's "compute locally" preference).
    window_52w = df.tail(TRADING_DAYS_52W)
    high_52w = float(window_52w["high"].max())
    low_52w = float(window_52w["low"].min())
    volume = float(row["volume"])
    avg_volume20 = float(df["volume"].tail(20).mean())

    return {
        "date": row["date"].strftime("%Y-%m-%d"),
        "close": close,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "ema20": float(row["ema20"]),
        "ema50": float(row["ema50"]),
        "ema200": float(row["ema200"]),
        "rsi14": float(row["rsi14"]),
        "macd": float(row["macd"]),
        "macd_signal": float(row["macd_signal"]),
        "atr14": float(row["atr14"]),
        "adx14": float(row["adx14"]),
        "adx_pos": float(row["adx_pos"]),
        "adx_neg": float(row["adx_neg"]),
        "bb_high": float(row["bb_high"]),
        "bb_low": float(row["bb_low"]),
        "bb_mid": float(row["bb_mid"]),
        "vwap20": float(row["vwap20"]),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "volume": volume,
        "avg_volume20": avg_volume20,
    }


def recent_price_history(df: pd.DataFrame, days: int = 120) -> list[dict]:
    """Last `days` daily closes (with EMA50 for context) for the dashboard mini-chart.
    Returns [{date, close, ema50}], oldest first. Kept small so each stock JSON stays light."""
    tail = df.tail(days)
    history = []
    for _, row in tail.iterrows():
        ema50 = row["ema50"]
        history.append(
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "close": round(float(row["close"]), 2),
                "ema50": None if pd.isna(ema50) else round(float(ema50), 2),
            }
        )
    return history


if __name__ == "__main__":
    from src.angel_auth import login
    from src.fetch_ohlcv import fetch_daily_ohlcv
    from src.instrument_master import build_nse_equity_token_map, get_token

    conn, _ = login()
    token_map = build_nse_equity_token_map()
    tok = get_token("RELIANCE", token_map)
    candles = fetch_daily_ohlcv(conn, "RELIANCE", tok)
    enriched = compute_indicators("RELIANCE", candles)
    if enriched is not None:
        logger.info("RELIANCE snapshot: %s", latest_indicator_snapshot(enriched))
