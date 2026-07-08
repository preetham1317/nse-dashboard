import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"
STOCKS_OUTPUT_DIR = OUTPUT_DIR / "stocks"
CACHE_DIR = DATA_DIR / "cache"

WATCHLIST_PATH = CONFIG_DIR / "watchlist.json"
PORTFOLIO_PATH = CONFIG_DIR / "portfolio.json"

ANGEL_API_KEY = os.environ.get("ANGEL_API_KEY")
ANGEL_CLIENT_ID = os.environ.get("ANGEL_CLIENT_ID")
ANGEL_PIN = os.environ.get("ANGEL_PIN")
ANGEL_TOTP_SECRET = os.environ.get("ANGEL_TOTP_SECRET")

for _dir in (OUTPUT_DIR, STOCKS_OUTPUT_DIR, CACHE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
