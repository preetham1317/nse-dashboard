import nsepython

from src.logging_utils import get_logger, log_skip

logger = get_logger(__name__)

# NSE's public endpoints (wrapped by nsepython) are known to be flaky - they frequently
# block non-browser/datacenter traffic with a non-JSON response. Per CLAUDE.md, this is
# treated as best-effort: log the failure explicitly and skip this section for the
# stock this cycle rather than fabricating a shareholding figure.

SHAREHOLDING_FIELDS = {
    "pPromoterChangePerc": "promoter_holding_change_pct",
    "pFIIChangePerc": "fii_holding_change_pct",
    "pDIIChangePerc": "dii_holding_change_pct",
}


def fetch_shareholding(symbol: str) -> dict | None:
    try:
        data = nsepython.nse_eq(symbol)
    except Exception as exc:
        log_skip(logger, symbol, "fetch_shareholding", f"nsepython.nse_eq raised {exc!r}")
        return None

    if not data:
        log_skip(logger, symbol, "fetch_shareholding", "nsepython.nse_eq returned no data")
        return None

    security_info = data.get("securityWiseDP") or {}
    result = {}
    for nse_key, out_key in SHAREHOLDING_FIELDS.items():
        value = security_info.get(nse_key)
        if value is None:
            log_skip(logger, symbol, "fetch_shareholding", f"missing field {nse_key}")
        result[out_key] = value

    if all(v is None for v in result.values()):
        log_skip(logger, symbol, "fetch_shareholding", "no shareholding fields present in response")
        return None

    return result


if __name__ == "__main__":
    for test_symbol in ("RELIANCE", "TCS", "INFY"):
        logger.info("%s shareholding: %s", test_symbol, fetch_shareholding(test_symbol))
