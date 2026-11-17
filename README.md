# Stopline

**Free trading risk calculators and prop firm tools, with no signup.**
Live site: **https://stoplineinvestor.org**

Stopline helps traders plan a trade before they place it: how big, where to stop, what it needs to win, and how much room an account has left. The prop firm tools turn each firm's published rules into calculators and plain-English guides, with the source and the date each rule was last checked shown on every page.

## Features

**Calculators**
- **Position size**: size a trade from account, risk %, entry and stop. Also available as an embeddable widget (`/embed/`).
- **Risk/reward**, **expectancy and Kelly**, **drawdown recovery**, **compounding growth**, **margin and leverage**
- **Options P&L** and **futures P&L**
- **Risk of ruin simulator**
- **Trade journal** with streaks (stored in the visitor's own browser; optional Google sign-in syncs it across devices)

**Prop firm tools**
- **Consistency rule**: best-day share of total profit against a firm's limit, and how much more profit is needed to fix it
- **Trailing drawdown**: liquidation level and room left, including where the drawdown locks
- **Profit target pace**: what a daily pace has to look like to hit a target
- **Firm presets** for Apex, Topstep, My Funded Futures Rapid, Tradeify, Take Profit Trader, and Lucid, with each rule's source linked and dated
- **Rules guides** for each firm, plus a **side-by-side comparison** page (`/prop-firm-rules-comparison/`)

**Site quality**: static, fast pages, per-page structured data (Article, FAQ, Breadcrumb), sitemap and canonical URLs, lazy-loaded market ticker with reserved height (no layout shift), and a custom 404 page.

Calculator inputs are processed in the browser and are not sent to a server. Educational only; not financial advice.

## Tech

- **Cloudflare Workers + static assets**: pages are plain HTML, CSS and vanilla JS in `site/` (no framework, no build step needed to serve). Cloudflare serves them from its edge.
- **Worker (`worker/worker.js`)**: handles only `/api/*`: config, Google Identity Services sign-in (ID token verified in-Worker with Web Crypto, RS256 and Google's JWKS), session cookies, and per-user sync. Origin and `X-Requested-With` checks guard writes against CSRF.
- **Cloudflare D1** (SQLite) stores users, sessions, and the synced JSON blob (see `schema.sql`). Sign-in and sync are optional.
- **Security headers** in `site/_headers` (nosniff, referrer policy, frame protection, permissions policy).

## Repository layout

```
site/            static site (HTML/CSS/JS, sitemap, robots, _headers, 404)
worker/worker.js Worker for /api/* (sign-in and sync)
wrangler.jsonc   Cloudflare config (placeholders for account and D1 ids)
schema.sql       D1 tables used by the Worker
tools/serve.py   tiny local static server that mimics 404 handling
tests/test.py    Playwright smoke test: every sitemap URL loads, plus calculator cases
```

## Run locally

Static pages only:

```bash
python3 tools/serve.py site 8811      # then open http://127.0.0.1:8811
```

With the Worker and assets together (including `/api/*`):

```bash
npm install
cp .dev.vars.example .dev.vars        # optional, for sign-in testing
npx wrangler dev
```

Tests (needs `pip install playwright` and a browser):

```bash
python3 tools/serve.py site 8811 &
python3 tests/test.py
```

## Deploy

1. Edit `wrangler.jsonc`: set `account_id`, and, if you want sign-in and sync, create a D1 database (`npx wrangler d1 create stopline`), paste its `database_id`, apply `schema.sql`, and set `GOOGLE_CLIENT_ID` to your own Google OAuth client id. To run as pure static pages, remove the `d1_databases` and `vars` blocks; `/api/config` then returns an empty client id and accounts stay off.
2. Authenticate: `npx wrangler login`, or export `CLOUDFLARE_API_TOKEN` (Workers Scripts: Edit, D1: Read). See `.env.example`.
3. `npx wrangler deploy`
4. Smoke test: sitemap URLs return 200, an unknown path returns the 404 page, and `/api/config` responds.

Rollback: `npx wrangler rollback <version-id>`.

## A note on how it was built

Built with AI-assisted development. The design, the product decisions, the choice of which rules to cover, and the domain judgment are Jamie's; AI tools helped write and test the code. Firm rules are read from each firm's own help center and dated, and anything unclear is flagged rather than guessed.

## About the author

Jamie Urena is a disabled U.S. Army veteran and former intelligence analyst who has traded stocks, perpetual futures and crypto since 2018. Stopline applies an analyst's habits to trading tools: verify the source, date every rule, and size the risk first.

## Disclaimer

Stopline is educational. Nothing here is financial, investment or legal advice, and trading involves substantial risk of loss. Stopline is independent and is not affiliated with any prop firm, broker or exchange. Firm rules change often, so always confirm with the firm.
