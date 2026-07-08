import json
from datetime import datetime, timezone

from src import config
from src.angel_auth import AngelAuthError, login
from src.fetch_fundamentals import fetch_fundamentals
from src.fetch_ohlcv import fetch_daily_ohlcv
from src.fetch_shareholding import fetch_shareholding
from src.flags import FLAG_DEFINITIONS, evaluate_flags
from src.indicators import compute_indicators, latest_indicator_snapshot
from src.instrument_master import build_nse_equity_token_map, get_token
from src.logging_utils import get_logger, log_skip

logger = get_logger(__name__)


def load_watchlist() -> list[dict]:
    return json.loads(config.WATCHLIST_PATH.read_text(encoding="utf-8"))


def load_portfolio() -> dict:
    return json.loads(config.PORTFOLIO_PATH.read_text(encoding="utf-8"))


def _write_flag_definitions() -> None:
    definitions = [{"key": key, "label": label} for key, label in FLAG_DEFINITIONS]
    (config.OUTPUT_DIR / "flag_definitions.json").write_text(
        json.dumps(definitions, indent=2), encoding="utf-8"
    )


def run() -> None:
    _write_flag_definitions()
    watchlist = load_watchlist()
    portfolio = load_portfolio()
    holdings = portfolio.get("holdings", [])

    watch_by_symbol = {row["symbol"]: row for row in watchlist}
    all_symbols = sorted(set(watch_by_symbol) | {h["symbol"] for h in holdings})

    try:
        conn, _ = login()
    except AngelAuthError as exc:
        logger.error("aborting pipeline run: Angel One login failed: %s", exc)
        return

    token_map = build_nse_equity_token_map()

    meta = {"run_at": datetime.now(timezone.utc).isoformat(), "symbols": {}}
    stock_data_by_symbol: dict[str, dict] = {}

    for symbol in all_symbols:
        watch_info = watch_by_symbol.get(symbol, {})

        token = get_token(symbol, token_map)
        if token is None:
            meta["symbols"][symbol] = {"status": "skipped", "reason": "no symboltoken found"}
            continue

        ohlcv = fetch_daily_ohlcv(conn, symbol, token)
        if ohlcv is None:
            meta["symbols"][symbol] = {"status": "skipped", "reason": "ohlcv fetch failed"}
            continue

        enriched = compute_indicators(symbol, ohlcv)
        if enriched is None:
            meta["symbols"][symbol] = {"status": "skipped", "reason": "insufficient history for indicators"}
            continue

        snapshot = latest_indicator_snapshot(enriched)
        flag_result = evaluate_flags(snapshot)

        fundamentals = fetch_fundamentals(symbol)
        shareholding = fetch_shareholding(symbol)

        stock_json = {
            "symbol": symbol,
            "name": watch_info.get("name"),
            "sector": watch_info.get("sector"),
            "indicators": snapshot,
            "flags": flag_result,
            "fundamentals": fundamentals,
            "shareholding": shareholding,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        stock_data_by_symbol[symbol] = stock_json

        (config.STOCKS_OUTPUT_DIR / f"{symbol}.json").write_text(
            json.dumps(stock_json, indent=2), encoding="utf-8"
        )
        meta["symbols"][symbol] = {
            "status": "ok",
            "fundamentals_available": fundamentals is not None,
            "shareholding_available": shareholding is not None,
        }
        logger.info(
            "wrote output for symbol=%s flags=%d/%d",
            symbol,
            flag_result["flag_count"],
            flag_result["flag_total"],
        )

    _write_portfolio_output(holdings, stock_data_by_symbol, watch_by_symbol)

    meta["summary"] = {
        "total": len(all_symbols),
        "ok": sum(1 for v in meta["symbols"].values() if v["status"] == "ok"),
        "skipped": sum(1 for v in meta["symbols"].values() if v["status"] == "skipped"),
    }
    (config.OUTPUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("pipeline run complete: %s", meta["summary"])


def _write_portfolio_output(
    holdings: list[dict], stock_data_by_symbol: dict[str, dict], watch_by_symbol: dict[str, dict]
) -> None:
    portfolio_output = {"holdings": [], "updated_at": datetime.now(timezone.utc).isoformat()}

    for holding in holdings:
        symbol = holding["symbol"]
        stock = stock_data_by_symbol.get(symbol)
        if stock is None:
            log_skip(logger, symbol, "portfolio_join", "no stock data available for this holding this cycle")
            portfolio_output["holdings"].append(
                {**holding, "current_price": None, "pnl": None, "pnl_pct": None, "flags": None}
            )
            continue

        current_price = stock["indicators"]["close"]
        buy_price = holding["buy_price"]
        quantity = holding["quantity"]
        pnl = (current_price - buy_price) * quantity
        pnl_pct = (current_price - buy_price) / buy_price * 100 if buy_price else None

        portfolio_output["holdings"].append(
            {
                **holding,
                "current_price": current_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "flags": stock["flags"],
                "sector": watch_by_symbol.get(symbol, {}).get("sector"),
            }
        )

    (config.OUTPUT_DIR / "portfolio.json").write_text(json.dumps(portfolio_output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
