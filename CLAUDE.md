# NSE Stock Intelligence Dashboard — Project Brief

## What this is
A personal-use stock analysis dashboard for the Indian NSE market, built for one user
(Subramanya). It answers one question daily: "Out of everything I track, what deserves
my attention today, and why?" It is a research/explanation tool, not a trading signal
generator, and not a recommendation service.

**This is NOT the options trading bot.** That's a separate, already-running system
(bot_v26.py, intraday options signals via Angel One + Telegram/Discord). Do not merge
code, credentials, repos, or Telegram bots between the two projects. They may share
some API credentials (Angel One account) but are otherwise independent.

## Scope & constraints
- Personal use only. No friends, no distribution, no public sharing of output.
  This keeps it outside SEBI research-analyst territory — do not add multi-user
  features, sharing, or "give advice to others" functionality without this being
  explicitly re-discussed.
- Sequencing: this project's build only starts once bot_v26's paper-trading
  validation window is complete. If that's still open when a build session starts,
  say so and confirm before proceeding — don't assume it's done.

## Build order (do not skip ahead)
1. **Phase 1 — Foundation** (build and validate fully before Phase 2):
   watchlist config, daily data collection, technical indicators (EMA 20/50/200,
   RSI, MACD, ATR, VWAP, ADX, Bollinger), portfolio page.
2. **Phase 2 — Ranking & Alerts**: sector strength, flag-based ranking, Telegram briefings.
3. **Phase 3 — AI Explanation Layer**: Claude Haiku explains flags in plain language,
   lightweight news summaries.
4. **Phase 4 — Optional, later**: backtesting flag combinations, historical flag charts,
   custom flag weighting. Do not build this until explicitly asked.

## Ranking philosophy — the one hard rule
**Never build a composite/weighted score (no 0–100 number, no single "verdict").**
Rank and explain everything by **flag count** (e.g. "6/8 bullish conditions met") and
name which specific flags fired. This was a deliberate correction from an earlier
ChatGPT-authored plan that used weighted composite scores — do not reintroduce that
pattern even if it seems like a simplification. If asked to add scoring later, flag
the tension with this rule before proceeding.

**Exception, by explicit decision (2026-07-09):** the stock detail panel shows an
*external* analyst-consensus block (yfinance `recommendationKey`/target prices, e.g.
"Buy · 21 analysts"). This is **not** a rule violation: it is third-party opinion
displayed as-is and clearly labelled "external · not this dashboard's" — the dashboard
never derives its own buy/hold/sell verdict from the flags or anything else. Keep that
labelling; do not let this grow into a dashboard-generated verdict.

## Data sources (all free — do not introduce paid data sources without asking)
| Data | Source | Notes |
|---|---|---|
| Price/volume/OHLCV | Angel One SmartAPI | Reuse bot's existing account/auth. Use `getMarketData` bulk endpoint for equities; avoid `ltpData()` patterns known to be unreliable for options (not relevant here, but keep the lesson in mind). |
| Technical indicators | Computed locally from OHLCV | No external service. |
| Fundamentals (PE, EPS, ROE, margins, market cap, statements) | `yfinance` (ticker format: `SYMBOL.NS`) | No API key needed. |
| ROCE, multi-year growth | Computed from `yfinance` raw financial statements | Not pulled pre-built — this is intentional (builds real judgment instead of trusting an opaque number). |
| Promoter/FII/DII shareholding, corporate filings, quarterly results | `nsepython` / `nselib` / `jugaad_data` | Public NSE data, no key needed. |
| AI explanations | Claude Haiku via Anthropic API | Explains flags already computed in code. Never invents a signal, score, or verdict — it explains, it doesn't decide. |
| Explicitly NOT used | Screener.in (free tier disables export; paid tier not needed since the above covers the same fields) | Don't reintroduce this dependency. |

## Hosting & delivery
- **Default hosting: GitHub Actions (scheduled workflow) + GitHub Pages.** Fully free,
  no server to maintain, fits the periodic (not continuously-live) nature of this data.
- Alternative considered: running alongside the existing Railway app (blogwizard.in) —
  only if GitHub Actions/Pages turns out insufficient, and only after checking Railway
  usage headroom first.
- Do not use the bot's PythonAnywhere always-on task slot — that's a known binding
  constraint for the bot and should not be contended for.
- Delivery: responsive single web dashboard (mobile + desktop from one build, no
  native app) + Telegram briefings (morning/evening) via a **new, separate** Telegram
  bot — do not reuse the trading bot's token or channels.
- Domain: no new domain purchase needed. Use the free GitHub Pages URL, or a
  subdomain of the already-owned domain (e.g. `stocks.blogwizard.in`) via a CNAME
  record — optional, low priority, do last.

## Watchlist — must be editable, never hardcoded
- Store as a simple config (JSON/CSV file in the repo, or a DB table) — not baked
  into code.
- Adding a stock must "just work" on the next scheduled run: fetch OHLCV history
  (yfinance backfills historical data instantly, so EMA/RSI/etc. can compute
  immediately, no multi-day wait), pull fundamentals, and include it in ranking/alerts
  automatically.
- Removing a stock just drops it from the config; no cleanup of historical data required.
- Start with a rough/partial list (20–30 names) rather than waiting for the full
  120–150 stock universe to be finalized.

## Secrets — never hardcode
Store all of these as GitHub Actions repo secrets (Settings → Secrets and variables
→ Actions), read only as environment variables at runtime:
- `ANGEL_API_KEY`, `ANGEL_CLIENT_ID`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET` (reused from bot)
- `ANTHROPIC_API_KEY` (reused from bot, or a separate key for isolated usage tracking)
- `TELEGRAM_BOT_TOKEN` (new bot, separate from the trading bot)
- No keys needed for `yfinance`, `nsepython`/`nselib`/`jugaad_data`

## Logging discipline (carried over from the bot's hard-won lessons)
Every skip, rejection, fallback, or missing-data path must emit an explicit log line.
No silent failures, no fake placeholder values (e.g. never silently substitute a
fallback RSI/ADX value on a fetch failure — log it and skip that stock's ranking
for that cycle instead). This was the single most costly bug class in the trading
bot's history (v25 forensic analysis) — do not repeat it here.

## Visual style
- **Light background only. No dark mode, ever, anywhere.**
- Glassmorphism: translucent white cards, backdrop blur, soft shadows, cool
  light-blue/mint gradient background.
- Color meaning is functional, not decorative: teal = bullish/positive flag,
  amber = caution/neutral, rose = bearish/weak — reserved for flag/status
  indicators only.
- Fonts used in the approved guide/mockup: Sora (headings), Inter (body),
  JetBrains Mono (tickers, prices, numeric data).

## Reference
The full build guide, cost breakdown, and visual mockup were already produced and
approved: `stock-dashboard-guide.html`. Check it for the agreed-on look and feel
before making independent visual design decisions.
