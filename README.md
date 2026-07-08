# NSE Stock Intelligence Dashboard

Personal-use research dashboard for a tracked NSE watchlist. Answers one question daily:
"Out of everything I track, what deserves my attention today, and why?"

Not a trading signal generator, not a recommendation service, not for distribution.
See [CLAUDE.md](CLAUDE.md) for the full project brief and build order.

## Phase 1 (this phase)
- Editable watchlist/portfolio config (`config/`)
- Daily OHLCV collection via Angel One SmartAPI (`src/fetch_ohlcv.py`)
- Technical indicators computed locally: EMA 20/50/200, RSI, MACD, ATR, VWAP, ADX, Bollinger (`src/indicators.py`)
- Flag-count ranking, never a composite score (`src/flags.py`)
- Fundamentals via yfinance, shareholding via nsepython (`src/fetch_fundamentals.py`, `src/fetch_shareholding.py`)
- Static dashboard (`dashboard/`) reading generated JSON (`data/output/`)
- Scheduled GitHub Actions run + GitHub Pages hosting (`.github/workflows/daily-run.yml`)

## Local setup
```
pip install -r requirements.txt
cp .env.example .env   # fill in Angel One credentials
python -m src.pipeline
```

## Secrets
Set as GitHub Actions repo secrets (never commit `.env`):
`ANGEL_API_KEY`, `ANGEL_CLIENT_ID`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET`.
