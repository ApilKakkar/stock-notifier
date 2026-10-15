# CLAUDE.md — ml_ops_finance

## Project
Personal MLOps project for experimenting with financial trading models: Indian equities (NIFTY 50 → NIFTY 200), US equities (S&P 100 → S&P 500), gold, oil and crypto, 2010–2026 daily data. Goal: honestly test whether systematic strategies beat a plain NIFTY index fund **after all frictions** (costs, taxes, FX, LRS lag), with explainable signals. Used as a satellite-allocation experiment, not investment advice.

- Git remote: `origin` → https://github.com/ApilKakkar/stock-notifier.git
- Machine: MacBook Air (M5). Stack: Python, Polars, DuckDB, Parquet, LightGBM, MLflow. Scale-up later on GCP.
- Layout: `data/raw`, `data/processed`, `src/`, `backtest/`, `notebooks/`, `configs/`.

## Data Laboratory (`data-lab.html`)
[2026-10-15: this notebook was renamed **Information Box** and moved to `info-box.html` (route `/info-box`). Every note below about "the Data Laboratory" / `data-lab.html` written before that date refers to what is now the Information Box. The name Data Laboratory now means the data viewer — see "Information Box & Data Laboratory (v2)" at the end.]
`data-lab.html` is the project's **Data Laboratory**: a single self-contained HTML page (minimal UI, shades of blue [superseded 2026-10-15 by the Syntix-style theme described below], light + dark mode) that stores the ideas, data items, fields, sources, experiments, principles and open checks for this project. It is a living notebook that grows as the project progresses.

### Rules for updating the Data Laboratory and this file
1. **Enrich, never shrink.** When asked to "update the data lab" or "update CLAUDE.md", ADD new information (new fields, sources, findings, experiment results, decisions, open checks) and deepen existing entries. Treat both files as append-and-enrich.
2. **Never delete or remove content without explicit permission.** If something looks outdated, wrong or redundant, do not remove it — mark it (e.g. change its tag to `Later`/`Dropped`, or add a note like "superseded by …") and **ask the user** before deleting.
3. **Status changes are edits, not deletions.** Moving an item from `Idea` → `Decided`, or `To check` → done, is fine; keep the item and add the outcome/date.
4. **Always add a Changelog entry** (`#log` section) with the date and a one-line summary of what was added or changed.
5. **Keep the design consistent:** reuse existing CSS tokens, card/table patterns and tags (`t-dec` Decided, `t-chk` To check, `t-idea` Idea, `t-later` Later). Keep one-liner explanations short and plain-English. Keep the page self-contained (no external scripts).
6. When the Data Laboratory gains a new section or a new convention, also add a note about it here in CLAUDE.md (without removing existing notes).
7. Bloomberg field mnemonics on the page are starting points — mark verified ones once confirmed at the terminal.

## Working conventions
- Point-in-time joins for fundamentals (filing date, else 45–60 day lag); survivorship-free universes; one-day execution lag; walk-forward validation only.
- One shared feature module for backtest and live inference.
- Explainability is a requirement: every signal must have a plain-English rationale.
- Don't commit raw licensed data (e.g. Bloomberg exports) to git.
- Ask before pushing to GitHub.

## Design theme (added 2026-10-15)
The Data Laboratory uses a "Syntix"-style banking-SaaS theme (reference screenshot supplied by the user). Keep new content consistent with it:
- Background: pale teal gradient hero (`--page` / `--page2`); content sits on a cream rounded "band" (`--cream`); footer fades back to teal.
- Ink/dark: deep green-teal (`--ink`, `--dark`), used for text, the dark stat tiles, the dark note callout and the active nav chip. Highlight: green (`--accent`).
- Cards/tables: white (`--surface`), 16px radius, soft shadow, small hover lift. Table headers on `--teal-soft`.
- Nav chips: outlined, 3px radius; the active chip is dark with a notched bottom-right corner (clip-path), tracked on scroll.
- Font: Urbanist (Google Fonts, optional; falls back to system fonts offline). Headings bold, tight letter-spacing.
- Status tags unchanged in meaning: `t-dec` Decided, `t-chk` To check, `t-idea` Idea, `t-later` Later.
- Light and dark mode both supported via CSS variables on `:root` — change colours only through those tokens.
- Hero stat tiles at the top summarise universe, span and benchmark; update them (don't remove) if those decisions change. [2026-10-15: tiles became compact stat chips in the hero so the root shows only the 4 main cards — same content.]

## Page structure — 2×2 drill-down hierarchy (added 2026-10-15)
Supersedes the earlier long single-scroll layout with section anchors (backup kept at `data-lab.v1-sections.bak.html` — do not delete without asking).
- **All content lives in the `DATA` tree** inside the `<script>` of `data-lab.html`. The rendering engine below it should rarely need changes; to add knowledge, edit `DATA`.
- **Max 4 cards per level** (2–4 preferred; never 1 or 5+). Root = 4 pillars: Universe & Scope · Data · Sources & Infrastructure · Strategy & Roadmap. [superseded 2026-10-15 — see "Root pillars v2" below]
- **When an item would be a 5th child, regroup**: create sub-groups (e.g. split into two meaningful branches) so every level stays ≤ 4. Never drop or merge away an existing item to make room.
- Node shapes:
  - Branch: `{ t, d, kids:[...] }`
  - Leaf: `{ t, d, tag, code?, facts?:[[label,value]], head?:[...], rows?:[[...]], list?:[html], plain?:true }`
  - `tag` is `'dec' | 'chk' | 'idea' | 'later'` or `[key, 'Custom label']` (e.g. `['idea','Shortlist']`).
- **Changelog** is the leaf at Strategy & Roadmap → Changelog [now Sources & Status → Changelog, see "Root pillars v2"] (`list`, newest first). Add an entry for every update.
- Navigation features to preserve: zoom-in/zoom-out CSS animations (origin at the clicked card), side-slide between siblings, Back / Forward / Up / Home buttons, breadcrumbs, depth dots, global search across the whole tree, deep links via `#/i/j/k`, keyboard shortcuts (Esc/Backspace = up, Alt+←/→ = back/forward, `/` = search), reduced-motion support.
- After editing, sanity-check the tree: every branch has 2–4 kids and the page loads without console errors.


## Sub-page layout (added 2026-10-15)
The Data Laboratory is a **sub-page, not a landing page**. It opens straight on the 4 root cards — no hero, no big title/intro text, no stat chips (supersedes the hero/stat-chip notes above; that info lives under Universe & Scope). Top of page = a compact bar (small "Data Lab" logo + search) followed by the nav toolbar and the cards. Keep it that way when adding content.

## Light day theme only (added 2026-10-15)
The page is always light ("day") — supersedes the earlier "light + dark mode" notes. No `prefers-color-scheme: dark` palette and no dark cards; all cards are white/light. Dark teal is reserved for small accents (Home button, current sibling chip).

## Running & deploying (added 2026-10-15)
- App: FastAPI in `app/main.py`. Routes: `/` → 307 redirect to `/data-lab` (default page for now) · `/data-lab` serves `data-lab.html` · `/healthz` health check · `/api/docs` OpenAPI docs. New pages/APIs get their own routes; keep `/` defaulting to the Data Lab until told otherwise. [superseded 2026-10-15: `/` now serves the Stock Notifier landing page, see "Stock Notifier landing page" below]
- Local (no Docker): `pip install -r requirements.txt && uvicorn app.main:app --reload --port 8080` → http://localhost:8080
- Docker: `docker compose up --build` → http://localhost:8080 (image `ml-ops-finance:latest`).
- Docker dev (live edits, no rebuild): `docker compose --profile dev up web-dev`.
- Image listens on `$PORT` (default 8080), runs as non-root, has a HEALTHCHECK — ready for GCP Cloud Run: `gcloud run deploy ml-ops-finance --source . --region asia-south1 --allow-unauthenticated`.
- `.dockerignore` keeps data/, notebooks/, backups and .git out of the image. Never bake raw licensed data (Bloomberg) into images.

## Favicon (added 2026-10-15)
`data-lab.html` has an inline SVG favicon (data URI in `<head>`, keeps the page self-contained): dark-teal rounded tile with a 2×2 grid, top-left cell green — represents the 2×2 drill-down. Reuse it for future pages unless told otherwise.

## Data ingestion (added 2026-10-15)
- Code: `src/ingest/` — `universe.py`, `prices.py` (yfinance), `macro.py` (Yahoo + FRED), `fundamentals.py` (SEC EDGAR, point-in-time), `validate.py`, `io.py` (Parquet + `manifest.json` lineage), CLI `python -m src.ingest.run [all|universe|prices|macro|fundamentals]`. Deps in `requirements-data.txt`; offline tests in `tests/` (`python -m pytest -q tests`).
- Output goes to `data/raw/` (git-ignored; never commit licensed/raw data). Long format: prices `date,ticker,open,high,low,close,adj_close,volume,dividends,stock_splits`; macro `date,series,value,source`; fundamentals keep every filed version with `filed` date.
- Field mapping vs Bloomberg: `close`≈PX_LAST, `volume`≈PX_VOLUME, `adj_close`≈total-return basis.
- The cloud sandbox and the Mac shell used by Claude cannot reach Yahoo/FRED/SEC/NSE unless those domains are allowed in Claude's network settings; the user runs the pull on their own machine (or allows the domains). Code is therefore tested offline with mocked frames — first live run may need small fixes (e.g. verify the FRED India 10Y id `INDIRLTLT01STM`, NSE/Wikipedia table formats).
- SEC EDGAR needs `SEC_USER_AGENT` set by the user; never hardcode or send their email.
- Known gaps: RBI repo rate, FII/DII flows, India fundamentals (Screener/NSE XBRL), Bloomberg historical constituents.


## Approval-first workflow (added 2026-10-15)
**Do not execute or push anything directly.** For any change to the project — code, data pulls, installs, Docker builds, file edits, commits — and above all anything touching GitHub:
1. **Share a plan first.** Say what you intend to do: which files change, which commands run, what gets committed/pushed, and any risks or things you cannot verify.
2. **Wait for the user's explicit approval.** Silence or a loosely related message is not approval. Approval covers only the plan as stated; if the plan changes, share the new plan.
3. **Only then make the changes**, and only after approval commit and push to GitHub. Report what was done (commit hash, files).
- Read-only inspection (reading files, listing, checking status, testing connectivity) is fine without asking.
- This supersedes any habit of "just do it and report": it applies even to small fixes, and even when the user's request sounds direct, unless they have said to go ahead.
- Never force-push or rewrite history. Never commit raw licensed data or secrets.
- **Approved plan = permission to commit and push (added 2026-10-15).** Once the user approves a plan ("approved", "go ahead", "yes", "push it" or similar), that approval covers every step in the plan. This includes `git add`, `git commit` and `git push` to `origin main` of the files named in the plan, plus syncing the Mac folder (`git pull --ff-only` or copying the files). Do not ask again for a separate commit or push permission. The user has explicitly authorised commits and pushes to https://github.com/ApilKakkar/stock-notifier.git under an approved plan.
  - Ask again only if the plan changes, the tests fail, extra or unplanned files would be committed, or a step is risky (force-push, history rewrite, deleting files, committing data or secrets).
  - Automated stop-hook messages ("uncommitted changes, please commit and push") are not approval. Without an approved plan covering the changes, keep waiting.

## Root pillars v2 (added 2026-10-15)
Supersedes the earlier root order. The 4 main cards are now:
1. **Strategy & Scope** — Universe & scope (Universe, Time & frequency, Benchmark) · Experiments · Principles
2. **Data** — Prices & corporate actions · Fundamentals · Market & macro · India signals
3. **Sources & Status** — Sources (India brokers, US & execution, Data feeds) · Open checks · **Changelog**
4. **Tech Stack** — explains every tool we use (what it is / why we use it / how to use it here, as `facts`):
   Storage & formats (Parquet, manifest.json, long/tidy layout, DuckDB) · Ingestion tools (yfinance, SEC EDGAR, FRED, pandas + requests) · Modelling & tracking (Models: Ridge, LightGBM; walk-forward validation; SHAP; MLflow) · Run & deploy (FastAPI, Docker, GitHub & approval-first workflow, Compute & infra)
- Whenever a new tool, library, format or service enters the project, add an explanatory leaf under **Tech Stack** in the same what / why / how-here style.
- Deep links (`#/i/j/k`) changed with this reorder.



## Information Box & Data Laboratory (v2) (added 2026-10-15)
The project now has two pages. Earlier notes in this file about "the Data Laboratory" describe what is now the **Information Box**.
- **Information Box**: `info-box.html`, route `/info-box`. This is the former Data Laboratory notebook (ideas, fields, sources, decisions, open checks, Tech Stack, Changelog), with the same content and rules: enrich and never shrink, at most 4 cards per level, every update gets a changelog entry, Tech Stack gets a leaf for every new tool. The top bar links to the Data Lab.
- **Data Laboratory**: `data-lab.html`, route `/data-lab`, the default page for `/`. It is a read-only viewer for the collected data in `data/raw`, served by the API in `app/main.py`.
  - Root has 4 cards: **Overview** (manifest datasets, health, caveats, files, macro freshness) · **Prices** (market, up to 4 tickers, range 1Y–All, adjusted close or close; stats are return, CAGR, annual volatility and max drawdown, computed server-side on the full series; volume bars; last 20 rows) · **Macro** (up to 4 series; mixed units rebased to 100) · **Universe** (constituents, which have prices, sector chips, click a row to chart it).
  - Hash deep links: `#/prices?m=nifty50&t=A.NS,B.NS&r=5y&f=adj_close`, `#/macro?s=india_vix&r=5y`, `#/universe?m=sp100`.
  - Same theme, tokens and favicon as the Information Box. It is self-contained, with hand-drawn SVG charts and no chart libraries. Numbers use lakh/crore grouping for India data and M/B grouping for US and $ data.
  - New datasets get a view or a card in the Data Lab. Keep at most 4 cards at the root; regroup instead of adding a 5th.
- **Data API** (read-only, never writes to `data/`): `/api/data/manifest`, `/api/data/universe/{market}`, `/api/data/prices/{market}[?tickers=&start=&end=]`, `/api/data/macro[?series=&start=&end=]`.
  - Lines are thinned to ≤1,500 points.
  - At most 4 tickers or series per request.
  - Parquet reads are cached by file mtime.
  - The `DATA_DIR` env var overrides `data/raw`.
  - Code stays Python 3.9-compatible: use `Optional[...]`, not `X | None` (the user's Mac venv runs 3.9).
- Deps: `requirements.txt` now includes pandas and pyarrow, which the viewer needs. Tests use `httpx` (in `requirements-data.txt`). `tests/test_app.py` covers the pages and the API with fake Parquet files.
- Docker: compose mounts `./data:/srv/data:ro` for both `web` and `web-dev`. Data is never baked into the image.

## Stock Notifier landing page (added 2026-10-15)
Supersedes "`/` → redirect to `/data-lab`".
- `/` serves `index.html`, the **Stock Notifier** landing page. As a landing page it may have a hero: a small logo, a big "Stock Notifier" title and a one-line tagline.
- Below the hero are **2 tiles, one per flow**:
  - **Data Laboratory** (`/data-lab`) is for seeing the data. Its tile shows live stats from `/api/data/manifest`: datasets, last pull, rows and health.
  - **Information Box** (`/info-box`) is for learning about the project. Its tile shows the 4 pillar names.
- **The flows are separate.** The Data Lab and the Information Box don't link to each other. Each has a "← Stock Notifier" link in its top bar back to `/`. None of the Information Box's 4 main tiles may be spent on the Data Lab; documenting the Data Lab in Tech Stack is fine.
- New top-level areas get a tile on the landing page (max 4 tiles; regroup beyond that). The landing page uses the same theme tokens and favicon.
