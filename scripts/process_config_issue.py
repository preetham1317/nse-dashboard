"""Parses a GitHub Issue Form submission and applies it to config/watchlist.json or
config/portfolio.json. Invoked from .github/workflows/process-config-issue.yml with
ISSUE_LABEL and ISSUE_BODY set from the triggering issue. Never fails silently: any
validation problem raises with a message the workflow posts back as an issue comment,
and no config file is touched.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT_DIR / "config" / "watchlist.json"
PORTFOLIO_PATH = ROOT_DIR / "config" / "portfolio.json"

KNOWN_LABELS = {"add-stock", "remove-stock", "add-holding", "remove-holding"}


class ConfigIssueError(Exception):
    pass


def parse_issue_form(body: str) -> dict[str, str]:
    sections = re.split(r"\n?### ", body.strip())
    fields: dict[str, str] = {}
    for section in sections:
        if not section.strip():
            continue
        label, _, rest = section.partition("\n")
        value = rest.strip()
        if value == "_No response_":
            value = ""
        fields[label.strip()] = value
    return fields


def _require(fields: dict[str, str], label: str) -> str:
    value = fields.get(label, "").strip()
    if not value:
        raise ConfigIssueError(f"Missing required field: {label}")
    return value


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def handle_add_stock(fields: dict[str, str]) -> str:
    symbol = _require(fields, "Symbol").upper()
    name = _require(fields, "Name")
    sector = _require(fields, "Sector")

    watchlist = _load_json(WATCHLIST_PATH)
    existing = next((row for row in watchlist if row["symbol"] == symbol), None)
    if existing:
        existing["name"], existing["sector"] = name, sector
        action = "Updated"
    else:
        watchlist.append({"symbol": symbol, "name": name, "sector": sector})
        action = "Added"

    _write_json(WATCHLIST_PATH, watchlist)
    return f"{action} {symbol} ({name}, {sector}) in the watchlist."


def handle_remove_stock(fields: dict[str, str]) -> str:
    symbol = _require(fields, "Symbol").upper()
    watchlist = _load_json(WATCHLIST_PATH)
    filtered = [row for row in watchlist if row["symbol"] != symbol]

    if len(filtered) == len(watchlist):
        raise ConfigIssueError(f"{symbol} isn't in the watchlist - nothing to remove.")

    _write_json(WATCHLIST_PATH, filtered)
    return f"Removed {symbol} from the watchlist."


def handle_add_holding(fields: dict[str, str]) -> str:
    symbol = _require(fields, "Symbol").upper()
    quantity_raw = _require(fields, "Quantity")
    buy_price_raw = _require(fields, "Buy price")
    buy_date = _require(fields, "Buy date")

    try:
        quantity = int(quantity_raw)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        raise ConfigIssueError(f"Quantity must be a positive whole number, got: {quantity_raw!r}")

    try:
        buy_price = float(buy_price_raw)
        if buy_price <= 0:
            raise ValueError
    except ValueError:
        raise ConfigIssueError(f"Buy price must be a positive number, got: {buy_price_raw!r}")

    try:
        datetime.strptime(buy_date, "%Y-%m-%d")
    except ValueError:
        raise ConfigIssueError(f"Buy date must be in YYYY-MM-DD format, got: {buy_date!r}")

    portfolio = _load_json(PORTFOLIO_PATH)
    holdings = portfolio.setdefault("holdings", [])
    existing = next((h for h in holdings if h["symbol"] == symbol), None)
    new_holding = {"symbol": symbol, "quantity": quantity, "buy_price": buy_price, "buy_date": buy_date}
    if existing:
        existing.update(new_holding)
        action = "Updated"
    else:
        holdings.append(new_holding)
        action = "Added"

    _write_json(PORTFOLIO_PATH, portfolio)
    return f"{action} holding: {symbol} x{quantity} @ ₹{buy_price} ({buy_date})."


def handle_remove_holding(fields: dict[str, str]) -> str:
    symbol = _require(fields, "Symbol").upper()
    portfolio = _load_json(PORTFOLIO_PATH)
    holdings = portfolio.get("holdings", [])
    filtered = [h for h in holdings if h["symbol"] != symbol]

    if len(filtered) == len(holdings):
        raise ConfigIssueError(f"{symbol} isn't in the portfolio - nothing to remove.")

    portfolio["holdings"] = filtered
    _write_json(PORTFOLIO_PATH, portfolio)
    return f"Removed {symbol} from the portfolio."


HANDLERS = {
    "add-stock": handle_add_stock,
    "remove-stock": handle_remove_stock,
    "add-holding": handle_add_holding,
    "remove-holding": handle_remove_holding,
}


def main() -> None:
    import os

    label = os.environ.get("ISSUE_LABEL", "")
    body = os.environ.get("ISSUE_BODY", "")

    if label not in KNOWN_LABELS:
        print(f"Not a recognized config-management label: {label!r}", file=sys.stderr)
        sys.exit(1)

    fields = parse_issue_form(body)
    try:
        result = HANDLERS[label](fields)
    except ConfigIssueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(result)


if __name__ == "__main__":
    main()
