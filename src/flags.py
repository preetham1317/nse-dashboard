# Fixed 8-flag bullish checklist. Flag count only - never a composite/weighted score
# (see CLAUDE.md "Ranking philosophy — the one hard rule").

FLAG_DEFINITIONS = [
    ("price_above_ema20", "Price above EMA20"),
    ("ema20_above_ema50", "EMA20 above EMA50"),
    ("ema50_above_ema200", "EMA50 above EMA200"),
    ("rsi_above_50", "RSI(14) above 50"),
    ("macd_bullish", "MACD line above signal line"),
    ("adx_trending_up", "ADX(14) above 20 with +DI above -DI"),
    ("price_above_vwap20", "Price above 20-day rolling VWAP"),
    ("price_above_bb_mid", "Price above Bollinger mid band (20,2)"),
]


def evaluate_flags(snapshot: dict) -> dict:
    """Takes a latest-indicator snapshot (see indicators.latest_indicator_snapshot) and
    returns which of the fixed 8 flags fired, plus the count. Never collapse this into
    a single weighted score.
    """
    close = snapshot["close"]

    fired = {
        "price_above_ema20": close > snapshot["ema20"],
        "ema20_above_ema50": snapshot["ema20"] > snapshot["ema50"],
        "ema50_above_ema200": snapshot["ema50"] > snapshot["ema200"],
        "rsi_above_50": snapshot["rsi14"] > 50,
        "macd_bullish": snapshot["macd"] > snapshot["macd_signal"],
        "adx_trending_up": snapshot["adx14"] > 20 and snapshot["adx_pos"] > snapshot["adx_neg"],
        "price_above_vwap20": close > snapshot["vwap20"],
        "price_above_bb_mid": close > snapshot["bb_mid"],
    }

    flags_on = [key for key, is_on in fired.items() if is_on]
    return {
        "flags": fired,
        "flags_on": flags_on,
        "flag_count": len(flags_on),
        "flag_total": len(FLAG_DEFINITIONS),
    }
