# stock-notifier · ml_ops_finance

Personal MLOps project for experimenting with systematic trading models on Indian equities (NIFTY 50 → 200), US equities (S&P 100 → 500), gold, oil and crypto, using daily data from 2010 to 2026.

The goal is to test honestly whether a strategy beats a plain NIFTY 50 index fund **after all frictions**: costs, taxes, FX and LRS lag. Every signal must also be explainable.

> Research project only, not investment advice.

The app opens on the **Stock Notifier** landing page (`/`), which has two tiles leading to two separate flows. The two pages don't link to each other; each links back to `/`.

- **Data Laboratory** (`/data-lab`): a viewer for the data actually collected. It shows what was pulled, price charts, macro series and the stock lists.
- **Information Box** (`/info-box`): the project notebook of data items, fields, sources, experiments, decisions and open checks, organised as a 2×2 drill-down. This was called the Data Laboratory until 2026-10-15.

---

## Quick start

### Option 1 — Docker (recommended)

Requires Docker Desktop.

```bash
git clone https://github.com/ApilKakkar/stock-notifier.git
cd stock-notifier
docker compose up --build
```

Open http://localhost:8080 to reach the Stock Notifier landing page. Docker mounts your local `data/` folder read-only, so the Data Lab shows whatever you've pulled.

Stop with `Ctrl+C`, or `docker compose down`.

### Option 2 — Docker in dev mode (live edits)

Mounts `index.html`, `data-lab.html`, `info-box.html`, `app/` and `data/` into the container, so edits show up on refresh without a rebuild:

```bash
docker compose --profile dev up web-dev
```

### Option 3 — Plain Python (no Docker)

Requires Python 3.10+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Open http://localhost:8080.

### Option 4 — Just view the notebook

`info-box.html` is self-contained, so you can open it directly in a browser. In VS Code, the **Live Server** extension (`ritwickdey.LiveServer`, recommended in `.vscode/extensions.json`) gives auto-reload: right-click `info-box.html` → **Open with Live Server**.

`data-lab.html` (and the live stats on `index.html`) need the app running (Options 1–3), because it reads data through the `/api/data/*` endpoints.

---

## Getting data

Free-data ingestion lives in `src/ingest/` and writes Parquet to `data/raw/` (git-ignored). Every run updates `data/raw/manifest.json` with source, row counts, date range, missing tickers and validation issues (data lineage).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-data.txt

python -m src.ingest.run all --limit 5     # smoke test: 5 tickers per market
python -m src.ingest.run all               # prototype: NIFTY 50 + S&P 100 from 2010, plus macro
```

| Command | Pulls | Output |
|---|---|---|
| `... universe` | NIFTY 50 (NSE) and S&P 100 (Wikipedia) constituents, saved as dated snapshots | `data/raw/universe/` |
| `... prices` | Daily OHLCV + adj close + dividends/splits (Yahoo) | `data/raw/prices/{nifty50,sp100}.parquet` |
| `... macro` | India VIX, NIFTY/Bank NIFTY, S&P, VIX, USD/INR, gold, silver, Brent/WTI, GOLDBEES, BTC/ETH (Yahoo); US 3M T-bill, US 10Y, India 10Y monthly (FRED) | `data/raw/macro/macro_daily.parquet` |
| `... fundamentals` | US filings, every filed version, point-in-time (SEC EDGAR) | `data/raw/fundamentals/us_edgar_facts.parquet` |

Options: `--markets india us`, `--start 2010-01-01`, `--end`, `--limit N`, `--full` (refetch whole history), `--data-dir`.

- **Incremental:** reruns fetch only the last 7 days and merge. Yahoo restates `adj_close` for the whole history at each dividend, so run `--full` occasionally (e.g. monthly).
- **SEC EDGAR** requires you to identify yourself: `export SEC_USER_AGENT="Your Name you@example.com"` (skipped with a warning if unset).
- **Survivorship bias:** universes are *current* constituents. To use a fixed list instead, put `configs/universe/nifty50.csv` or `sp100.csv` (with a `ticker` column) in place. Replace with Bloomberg historical constituents when available.
- **Not automated yet:** RBI repo rate, FII/DII flows, India fundamentals (Screener / NSE XBRL).
- **Tests (offline):** `python -m pytest -q tests`

### Seeing the data

After a pull, start the app (`uvicorn app.main:app --reload --port 8080`; install `requirements.txt` in the same venv first) and open http://localhost:8080/data-lab. It has four cards:

| Card | Shows |
|---|---|
| **Overview** | Every dataset from `manifest.json` (rows, date range, health, when it was pulled), problems and caveats, files on disk, and how fresh each macro series is |
| **Prices** | NIFTY 50 / S&P 100. One stock shows price + volume, return, CAGR, volatility, max drawdown and the last 20 days. 2–4 stocks are rebased to 100. Ranges 1Y–All; adjusted close or close |
| **Macro** | Any of the 18 series, up to 4 at once (mixed units are rebased to 100) |
| **Universe** | Constituent list with sector, filterable, showing which stocks already have prices. Click a row to chart it |

Use **Refresh** after re-running the ingest. Deep links work, e.g. `/data-lab#/prices?m=nifty50&t=RELIANCE.NS,TCS.NS&r=5y`.

---

## Routes

| Route | What it does |
|---|---|
| `/` | Stock Notifier landing page (`index.html`): tiles for the Data Laboratory and the Information Box |
| `/data-lab` | Data Laboratory: viewer for the collected data |
| `/info-box` | Information Box: the project notebook |
| `/api/data/manifest` | `manifest.json` plus the list of data files |
| `/api/data/universe/{nifty50\|sp100}` | Constituents, flagged with whether prices exist |
| `/api/data/prices/{market}` | Per-ticker summary; with `?tickers=A,B&start=&end=` it returns series (≤1,500 points each), stats and the last 20 rows |
| `/api/data/macro` | Per-series summary; with `?series=a,b&start=&end=` it returns series and stats |
| `/healthz` | Health check → `{"status":"ok","index":true,"data_lab":true,"info_box":true,"data_dir":…}` |
| `/api/docs` | OpenAPI docs |

The data API is read-only. It reads `data/raw/` (override with `DATA_DIR`).

---

## Base path / reverse proxy

To serve the app under a sub-path of another domain (for example `https://example.com/stock-notifier/`), set `BASE_PATH`:

```bash
BASE_PATH=/stock-notifier uvicorn app.main:app --port 8080
# or in docker-compose.yml: environment: - BASE_PATH=/stock-notifier
```

Then everything lives under the prefix: `/stock-notifier/` (landing page), `/stock-notifier/data-lab`, `/stock-notifier/info-box`, `/stock-notifier/api/data/*` and `/stock-notifier/api/docs`. The bare `/stock-notifier` redirects to `/stock-notifier/`. `/healthz` is also served at the root for the Docker HEALTHCHECK.

Example nginx rule that passes the prefix through to the container:

```nginx
location /stock-notifier/ {
    proxy_pass http://stock-notifier:8080;   # no trailing slash: keeps /stock-notifier/ in the path
    proxy_set_header Host $host;
}
```

The pages use **relative URLs only** (`data-lab`, `info-box`, `./`, `api/data/...`), so they also work when a proxy strips the prefix and the app runs with no `BASE_PATH`. Keep new links relative.

---

## Deploy (GCP Cloud Run)

The image listens on `$PORT` (default `8080`), runs as a non-root user and has a `HEALTHCHECK`, so it runs on Cloud Run as is:

```bash
gcloud run deploy ml-ops-finance \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated
```

Any other container host works too:

```bash
docker build -t ml-ops-finance .
docker run -p 8080:8080 ml-ops-finance
```

---

## Project layout

```
.
├── app/
│   └── main.py            # FastAPI app: pages, read-only /api/data/*, /healthz
├── index.html             # Stock Notifier landing page (/): two tiles → two flows
├── data-lab.html          # Data Laboratory: viewer for the collected data (needs the app)
├── info-box.html          # Information Box: project notebook (single self-contained page)
├── data-lab.v1-sections.bak.html   # earlier single-scroll version (kept for reference)
├── Dockerfile             # python:3.12-slim, uvicorn, non-root, healthcheck
├── docker-compose.yml     # `web` (prod-like) and `web-dev` (live reload) services
├── requirements.txt       # web app: fastapi, uvicorn, pandas, pyarrow
├── requirements-data.txt  # ingestion + tests: pandas, pyarrow, yfinance, requests, lxml, pytest, httpx
├── src/ingest/            # universe, prices, macro, fundamentals, validate, CLI (run.py)
├── tests/                 # offline tests for the ingestion code and the web app
├── CLAUDE.md              # project conventions + rules for updating the Information Box and Data Lab
└── .vscode/               # Live Server recommendation
```

Planned folders for the modelling work (not in git yet): `data/processed`, `backtest/`, `notebooks/`, `configs/`.

---

## Using the Information Box

- It opens on 4 cards: **Strategy & Scope · Data · Sources & Status · Tech Stack**.
- Click a card to zoom in; each level shows at most 4 cards, and the last level is a detail card.
- Navigation: **Back / Forward / Up / Home** buttons and clickable breadcrumbs.
- Keyboard: `Esc` = up · `Alt+←/→` = back/forward · `/` = search.
- Search covers the whole tree; click a result to jump to it.
- Deep links: the URL hash tracks your position (e.g. `/info-box#/1/1/0/2`), so views can be bookmarked.

### Adding content

All content lives in the `DATA` tree inside the `<script>` of `info-box.html`:

```js
// Branch
{ t: 'Title', d: 'One-line description', kids: [ /* 2–4 children */ ] }

// Leaf
{ t: 'P/E', tag: 'dec', code: 'PE_RATIO', d: 'Plain-English one-liner',
  facts: [['Label', 'Value']], head: [...], rows: [[...]], list: ['html'] }
```

Rules (full version in `CLAUDE.md`):

- Every level has **2–4 children**. When a 5th item arrives, regroup into sub-groups; never drop items.
- Enrich, never delete. Mark outdated items instead of removing them.
- Add a dated entry to **Sources & Status → Changelog** for every update.
- Tags:
  - `dec` = Decided
  - `chk` = To check
  - `idea` = Idea
  - `later` = Later
  - A custom label is also allowed, e.g. `['idea','Shortlist']`.

---

## Data & licensing note

Never commit raw licensed data (for example, Bloomberg exports) to git or bake it into Docker images. `data/` is git-ignored and excluded from the image by `.dockerignore`.
