# stock-notifier · ml_ops_finance

Personal MLOps project for experimenting with systematic trading models on Indian equities (NIFTY 50 → 200), US equities (S&P 100 → 500), gold, oil and crypto, using daily data from 2010 to 2026.

The goal is to test honestly whether a strategy beats a plain NIFTY 50 index fund **after all frictions**: costs, taxes, FX and LRS lag. Every signal must also be explainable.

> Research project only, not investment advice.

For now the app serves the **Data Laboratory**: a living notebook of the data, signals, sources, experiments and open checks for the project, organised as a 2×2 drill-down.

---

## Quick start

### Option 1 — Docker (recommended)

Requires Docker Desktop.

```bash
git clone https://github.com/ApilKakkar/stock-notifier.git
cd stock-notifier
docker compose up --build
```

Open http://localhost:8080. It redirects to `/data-lab`.

Stop with `Ctrl+C`, or `docker compose down`.

### Option 2 — Docker in dev mode (live edits)

Mounts `data-lab.html` and `app/` into the container, so edits show up on refresh without a rebuild:

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

### Option 4 — Just view the page

`data-lab.html` is self-contained, so you can open it directly in a browser. In VS Code, the **Live Server** extension (`ritwickdey.LiveServer`, recommended in `.vscode/extensions.json`) gives auto-reload: right-click `data-lab.html` → **Open with Live Server**.

---

## Routes

| Route | What it does |
|---|---|
| `/` | Redirects (307) to `/data-lab`, the default page for now |
| `/data-lab` | The Data Laboratory page |
| `/healthz` | Health check → `{"status":"ok","data_lab":true}` |
| `/api/docs` | OpenAPI docs (for APIs added later) |

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
│   └── main.py            # FastAPI app: / → /data-lab, /healthz
├── data-lab.html          # Data Laboratory (single self-contained page)
├── data-lab.v1-sections.bak.html   # earlier single-scroll version (kept for reference)
├── Dockerfile             # python:3.12-slim, uvicorn, non-root, healthcheck
├── docker-compose.yml     # `web` (prod-like) and `web-dev` (live reload) services
├── requirements.txt       # fastapi, uvicorn
├── CLAUDE.md              # project conventions + rules for updating the Data Lab
└── .vscode/               # Live Server recommendation
```

Planned folders for the modelling work (not in git yet): `data/raw`, `data/processed`, `src/`, `backtest/`, `notebooks/`, `configs/`.

---

## Using the Data Laboratory

- It opens on 4 cards: **Universe & Scope · Data · Sources & Infrastructure · Strategy & Roadmap**.
- Click a card to zoom in; each level shows at most 4 cards, and the last level is a detail card.
- Navigation: **Back / Forward / Up / Home** buttons and clickable breadcrumbs.
- Keyboard: `Esc` = up · `Alt+←/→` = back/forward · `/` = search.
- Search covers the whole tree; click a result to jump to it.
- Deep links: the URL hash tracks your position (e.g. `/data-lab#/1/1/0/2`), so views can be bookmarked.

### Adding content

All content lives in the `DATA` tree inside the `<script>` of `data-lab.html`:

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
- Add a dated entry to **Strategy & Roadmap → Changelog** for every update.
- Tags:
  - `dec` = Decided
  - `chk` = To check
  - `idea` = Idea
  - `later` = Later
  - A custom label is also allowed, e.g. `['idea','Shortlist']`.

---

## Data & licensing note

Never commit raw licensed data (for example, Bloomberg exports) to git or bake it into Docker images. `data/` is git-ignored and excluded from the image by `.dockerignore`.
