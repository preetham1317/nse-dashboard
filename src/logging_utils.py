import logging
import sys

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_skip(logger: logging.Logger, symbol: str, stage: str, reason: str) -> None:
    """Every skip/rejection/fallback path must call this. No silent failures."""
    logger.warning("SKIP symbol=%s stage=%s reason=%s", symbol, stage, reason)
