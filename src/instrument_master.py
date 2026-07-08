import json
import time

import requests

from src import config
from src.logging_utils import get_logger

logger = get_logger(__name__)

SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
CACHE_PATH = config.CACHE_DIR / "scrip_master.json"
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60


class InstrumentLookupError(Exception):
    pass


def _download_scrip_master() -> list[dict]:
    logger.info("downloading Angel One scrip master from %s", SCRIP_MASTER_URL)
    response = requests.get(SCRIP_MASTER_URL, timeout=60)
    response.raise_for_status()
    data = response.json()
    CACHE_PATH.write_text(json.dumps(data), encoding="utf-8")
    logger.info("cached scrip master (%d instruments) at %s", len(data), CACHE_PATH)
    return data


def _load_scrip_master(force_refresh: bool = False) -> list[dict]:
    if not force_refresh and CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_MAX_AGE_SECONDS:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        logger.info("scrip master cache stale (age=%.0fs), refreshing", age)
    return _download_scrip_master()


def build_nse_equity_token_map(force_refresh: bool = False) -> dict[str, str]:
    """Maps bare NSE trading symbol (e.g. 'RELIANCE') -> Angel One symboltoken."""
    instruments = _load_scrip_master(force_refresh=force_refresh)
    token_map: dict[str, str] = {}
    for row in instruments:
        if row.get("exch_seg") != "NSE":
            continue
        symbol = row.get("symbol", "")
        if not symbol.endswith("-EQ"):
            continue
        bare_symbol = symbol[: -len("-EQ")]
        token_map[bare_symbol] = row["token"]
    logger.info("built NSE equity token map with %d symbols", len(token_map))
    return token_map


def get_token(symbol: str, token_map: dict[str, str]) -> str | None:
    token = token_map.get(symbol)
    if token is None:
        logger.warning("no Angel One symboltoken found for symbol=%s", symbol)
    return token


if __name__ == "__main__":
    mapping = build_nse_equity_token_map()
    for test_symbol in ("RELIANCE", "TCS", "INFY", "HDFCBANK", "DOES_NOT_EXIST"):
        logger.info("%s -> %s", test_symbol, get_token(test_symbol, mapping))
