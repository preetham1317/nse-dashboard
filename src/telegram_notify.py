import argparse
import json

import requests

from src import config
from src.logging_utils import get_logger

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TOP_N = 5


def _load_output():
    meta = json.loads((config.OUTPUT_DIR / "meta.json").read_text(encoding="utf-8"))
    sectors = json.loads((config.OUTPUT_DIR / "sectors.json").read_text(encoding="utf-8"))
    portfolio = json.loads((config.OUTPUT_DIR / "portfolio.json").read_text(encoding="utf-8"))

    stocks = []
    for symbol, info in meta["symbols"].items():
        if info["status"] != "ok":
            continue
        stock_path = config.STOCKS_OUTPUT_DIR / f"{symbol}.json"
        stocks.append(json.loads(stock_path.read_text(encoding="utf-8")))
    stocks.sort(key=lambda s: s["flags"]["flag_count"], reverse=True)

    return meta, sectors, portfolio, stocks


def _format_stock_line(rank: int, stock: dict) -> str:
    flags = stock["flags"]
    top_flag_labels = ", ".join(flags["flags_on"][:2]) or "no bullish flags"
    return f"{rank}. {stock['symbol']} ({stock['sector']}) — {flags['flag_count']}/{flags['flag_total']} · {top_flag_labels}"


def build_evening_message(meta, sectors, portfolio, stocks) -> str:
    lines = ["📊 *Stock Intelligence — Evening Wrap*", ""]
    lines.append(f"{meta['summary']['ok']}/{meta['summary']['total']} symbols updated.")
    if meta["summary"]["skipped"]:
        lines.append(f"⚠️ {meta['summary']['skipped']} skipped this run (see dashboard for reasons).")
    lines.append("")

    lines.append("*Top flag counts today:*")
    for i, stock in enumerate(stocks[:TOP_N], start=1):
        lines.append(_format_stock_line(i, stock))
    lines.append("")

    if sectors:
        top_sectors = ", ".join(f"{s['sector']} {s['avg_flag_pct']}%" for s in sectors[:3])
        lines.append(f"*Strongest sectors:* {top_sectors}")
        lines.append("")

    if portfolio["holdings"]:
        lines.append("*Portfolio:*")
        for h in portfolio["holdings"]:
            if h["pnl_pct"] is None:
                lines.append(f"{h['symbol']}: no data this cycle")
            else:
                arrow = "▲" if h["pnl_pct"] >= 0 else "▼"
                lines.append(f"{h['symbol']}: {arrow} {abs(h['pnl_pct']):.2f}% (₹{h['pnl']:,.0f})")
        lines.append("")

    lines.append(f"Full dashboard: {config.DASHBOARD_URL}")
    lines.append("_Not a recommendation service — you make every decision._")
    return "\n".join(lines)


def build_morning_message(meta, sectors, portfolio, stocks) -> str:
    lines = ["☀️ *Good morning — Stock Intelligence recap*", ""]
    lines.append(f"Based on the {meta['run_at'][:10]} close.")
    lines.append("")

    lines.append("*Top flag counts:*")
    for i, stock in enumerate(stocks[:3], start=1):
        lines.append(_format_stock_line(i, stock))
    lines.append("")

    if sectors:
        lines.append(f"*Strongest sector:* {sectors[0]['sector']} ({sectors[0]['avg_flag_pct']}%)")
        lines.append("")

    lines.append(f"Full dashboard: {config.DASHBOARD_URL}")
    return "\n".join(lines)


def send_message(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("SKIP telegram_notify: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not configured")
        return False

    url = TELEGRAM_API.format(token=config.TELEGRAM_BOT_TOKEN)
    try:
        response = requests.post(
            url,
            data={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=30,
        )
    except Exception as exc:
        logger.warning("SKIP telegram_notify: request raised %r", exc)
        return False

    if not response.ok or not response.json().get("ok"):
        logger.warning("SKIP telegram_notify: Telegram API returned failure: %s", response.text)
        return False

    logger.info("Telegram message sent successfully")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["morning", "evening"], required=True)
    args = parser.parse_args()

    meta, sectors, portfolio, stocks = _load_output()
    if args.mode == "evening":
        text = build_evening_message(meta, sectors, portfolio, stocks)
    else:
        text = build_morning_message(meta, sectors, portfolio, stocks)

    # Best-effort: a Telegram delivery failure should never fail the workflow job
    # (data collection + Pages deploy matter more than the notification).
    send_message(text)


if __name__ == "__main__":
    main()
