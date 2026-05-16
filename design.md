# Design

How the system is built and why. Paired with [plan.md](plan.md), which covers
what's being built and when.

## Architecture at a glance

```
┌─────────────────────┐  ┌──────────────┐  ┌──────────────────┐  ┌──────────┐
│ Ken French zip      │  │              │  │ monthly_returns  │  │          │
│ (1926+ market ret.) │─►│  src/ingest  │─►│ .parquet         │  │          │
└─────────────────────┘  │              │  │ (local working   │  │          │
┌─────────────────────┐  │              │  │  artifact)       │  │          │
│ FRED CPIAUCNS CSV   │─►│              │  │                  │  │          │
│ (1913+ CPI)         │  └──────────────┘  └────────┬─────────┘  │          │
└─────────────────────┘                             │            │ Browser  │
                                                    ▼            │ (static  │
                          ┌──────────────┐  ┌──────────────────┐ │  site)   │
                          │ src/analysis │  │ docs/data/       │ │          │
                          │ rolling math │─►│ returns.json     │►│ docs/    │
                          └──────────────┘  │ (~640 KB,        │ │ app.js   │
                          ┌──────────────┐  │  committed)      │ │          │
                          │ src/export   │  │                  │ │          │
                          └──────────────┘  └──────────────────┘ └──────────┘
                          ┌──────────────┐  ┌──────────────────┐
                          │ src/report   │─►│ reports/         │  (local, gitignored)
                          │ PDF builder  │  │ rolling_returns  │
                          └──────────────┘  │ .pdf             │
                                            └──────────────────┘
                          ┌──────────────┐
                          │ notebooks/   │  (dev-only; no shipped artifact —
                          │ exploratory  │   cell outputs in the .ipynb only)
                          └──────────────┘
                          ◄─── offline (Python) ─────►  ◄── live (JS) ──►
```

The parquet has three downstream consumers: `src/export.py` (feeds the live
site), `src/report.py` (produces a shareable static PDF), and the Jupyter
notebook under `notebooks/` (exploratory analysis, developer-only). All three
are independent — each can change without affecting the others. The notebook
is where new analyses are prototyped before they get formalized into
`report.py` or `export.py`; it deliberately produces no committed artifact.

Two layers, deliberately separated:

- **Offline (Python):** ingest raw data, compute rolling windows, export a
  compact JSON. Runs on the developer's machine (or eventually a GitHub Action).
- **Online (browser):** fetch the precomputed JSON and render charts. No
  server, no build step.

## Why this architecture (and not pure JS)

We considered three alternatives:

1. **Pure JS, browser fetches sources directly.** Dead on arrival — Ken French's
   server doesn't send CORS headers, so the browser refuses the request.
2. **Pure JS, raw CSVs committed to repo.** Viable. Trades the Python pipeline
   for JS that parses zip + multi-section CSV + computes rolling windows.
3. **Python pipeline + static JS site (chosen).**

We chose (3) because:

- **pandas is enormously better than vanilla JS at time-series math.** Future
  analyses (rolling Sharpe, drawdowns, factor decomposition, withdrawal-rate
  simulations) are 10 lines in pandas and 100+ in JS.
- **The Python layer is genuinely offline.** It runs once when data is refreshed;
  visitors never see it. So "the site requires no Python" is already true.
- **GitHub Pages hosting is free for both options.** The choice doesn't affect
  cost.

The cost is that refreshing data requires running a Python command. Acceptable
since the data only updates monthly (Ken French publishes with a ~1-month lag).
A monthly GitHub Action can automate this later.

## Data sources

### Ken French Data Library — Fama/French 3 Factors (monthly)

- URL: `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip`
- Coverage: July 1926 to two months prior to current
- Format: zipped CSV, multi-section (preamble + monthly block + annual block + footer)
- Values are in **percent** (e.g., `2.50` means 2.5%, not 0.025). Common gotcha.
- We use only the monthly block. Total market return is computed as `(Mkt-RF + RF) / 100`.

Why Ken French and not direct CRSP, S&P 500, or Yahoo:
- Free, public, no API keys.
- Derived from CRSP (the academic gold standard) — total-market, value-weighted,
  dividends included.
- Long history back to 1926, which is the standard academic starting point for
  U.S. equity studies.

### FRED — CPI for All Urban Consumers, Not Seasonally Adjusted (`CPIAUCNS`)

- URL: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS`
- Coverage: January 1913 to current
- Format: plain two-column CSV

Why `CPIAUCNS` over `CPIAUCSL` (seasonally adjusted):
- `CPIAUCSL` only goes back to 1947; using it truncated 21 years of Ken French
  history.
- For deflating returns over multi-year windows, seasonality is irrelevant — it
  averages out.
- Confirmed by the first dry run: pre-fix data spanned 1947–2026; post-fix
  spans 1926–2026, recovering the full Ken French range.

## Data flow

1. **`src/ingest.py`**
   - Downloads Ken French zip → caches to `data/raw/ff_factors.zip`.
   - Downloads FRED CPI CSV → caches to `data/raw/cpi.csv`.
   - Parses Ken French monthly block (locates header by `,Mkt-RF` prefix, ends
     at first blank line or `Annual Factors` marker).
   - Computes monthly inflation from CPI, real return via Fisher equation:
     `real = (1 + nominal) / (1 + inflation) − 1`.
   - Writes `data/processed/monthly_returns.parquet` with columns
     `[date, nominal_return, real_return, rf, cpi, inflation]`.
   - The first row (July 1926) drops out because inflation needs a prior CPI.

2. **`src/analysis.py`**
   - Provides `rolling_window_returns(returns: pd.Series, years: int)`.
   - Uses log-returns + rolling sum (cleaner than chained multiplication).
   - Pandas' `rolling(N).sum()` labels at end-of-window; we shift by `−(N−1)`
     to label by *start*-of-window — that's what the user mentally indexes by.
   - Returns DataFrame indexed by start date with `end_date`, `terminal_value`
     (per $1), and `cagr`.

3. **`src/export.py`**
   - Computes rolling windows for horizons `(5, 10, 15, 20)` years × `{nominal, real}`.
   - Writes `docs/data/returns.json` (~640 KB, compact format, six-digit rounded).
   - The JSON shape:
     ```json
     {
       "monthly": [{ "date", "nominal", "real" }, ...],
       "rolling": {
         "10": [{ "start", "end", "nominal_cagr", "real_cagr",
                  "nominal_terminal", "real_terminal" }, ...],
         "5": [...], "15": [...], "20": [...]
       }
     }
     ```

4. **`docs/app.js`**
   - Fetches `data/returns.json` on load.
   - Reads `horizon` and `returnType` selects; renders three Plotly charts
     and a summary table.
   - All compute in the browser is just slicing and mapping over precomputed
     fields — no time-series math.

5. **`src/report.py`**
   - Reads the same `monthly_returns.parquet`, calls `rolling_window_returns`
     for the 10-year horizon, and writes a six-page PDF to
     `reports/rolling_returns.pdf` via matplotlib's `PdfPages` backend.
   - Pages: cover with headline stats, rolling-CAGR line chart + summary
     stats table, distribution histograms with the share-of-negative-windows
     callout, best/worst-5 tables for nominal and real, terminal-value chart,
     and a sources + methodology footnote page. Each non-cover page also
     carries a short footer citing Ken French + FRED.
   - No new dependencies — uses matplotlib, which is already required.
   - Output dir is gitignored; the PDF is regenerable, not a committed
     deliverable. Rebuild with `python -m src.report`.

6. **`notebooks/01_rolling_returns.ipynb`** (and any future `notebooks/*.ipynb`)
   - Exploratory, developer-only consumer of `monthly_returns.parquet`. Reads
     the parquet, calls `src/analysis.py`, and renders charts/tables inline
     in cell outputs — nothing is exported, committed, or consumed downstream.
   - Role: prototype new analyses here before deciding whether they belong in
     `src/report.py` (shareable static output), `src/export.py` (live site),
     both, or neither. Findings worth keeping graduate into one of those
     modules; the notebook itself is not part of the shipped pipeline.
   - Run with `jupyter notebook notebooks/01_rolling_returns.ipynb` from the
     project root after activating `.venv`.

## Key algorithm: rolling-window returns

For a series of monthly returns `r[t]` (decimal) and a window of `N` years
(i.e., `M = 12 × N` months):

1. Log-transform: `lr[t] = ln(1 + r[t])`.
2. Rolling sum over `M` months: `L[t] = sum(lr[t−M+1 ... t])`. Pandas labels
   `L` at the *end* of the window.
3. Shift the label to the *start* of the window: `L_start[s] = L[s + M − 1]`
   (a backward shift by `M − 1` positions).
4. Terminal value of $1 invested at `s`: `T[s] = exp(L_start[s])`.
5. Annualized: `CAGR[s] = T[s]^(1/N) − 1`.

Why log-returns instead of cumulative product:
- Pandas' `rolling().sum()` is built-in and well-tested; rolling product is not.
- Numerically more stable over long horizons.
- The math is identical: `exp(Σ ln(1+r)) = Π (1+r)`.

## Project layout

```
stockhistory/
├── data/
│   ├── raw/                         # downloaded sources (gitignored)
│   └── processed/                   # cleaned parquet (gitignored)
├── reports/                         # PDF output (gitignored)
├── src/
│   ├── __init__.py
│   ├── ingest.py                    # raw → parquet
│   ├── analysis.py                  # rolling-window math
│   ├── export.py                    # parquet → JSON for the site
│   └── report.py                    # parquet → PDF report
├── notebooks/
│   └── 01_rolling_returns.ipynb     # exploratory analysis
├── docs/                            # GitHub Pages root
│   ├── index.html                   # Pico.css + Plotly.js, both via CDN
│   ├── app.js                       # fetch + render
│   ├── style.css                    # small overrides
│   └── data/
│       └── returns.json             # exported by src/export.py (committed)
├── .venv/                           # local Python env (gitignored)
├── requirements.txt
├── plan.md
├── design.md
└── README.md
```

`data/processed/` is **not** committed — it's a regenerable local artifact.
`docs/data/returns.json` **is** committed — it's the data the live site needs.

## Site stack

- **Pico.css 2** (via jsDelivr CDN). Classless / semantic-HTML-friendly,
  ~10 KB. The site is mostly `<main>`, `<article>`, `<table>` with no class soup.
- **Plotly.js 2** (via Plotly CDN). Larger (~3 MB) but interactive
  out-of-the-box (zoom, hover, range selection). For exploratory charts with
  three views, it pays for itself in lines of code saved versus Chart.js or D3.
- **No build step.** No bundler, no transpilation, no node_modules. The site
  is three files plus a JSON.

## Versioning the data

`docs/data/returns.json` is committed to the repo. Each refresh produces a
fresh JSON; git history serves as the changelog. The raw downloads in
`data/raw/` are gitignored — they're re-fetchable from the canonical URLs.

This means: visitors get whatever was last committed. To refresh:

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.ingest --refresh    # force re-download
python -m src.export
git add docs/data/returns.json
git commit -m "data: refresh through <month>"
git push
```

Future: a GitHub Action can do this on a monthly cron.

## Things that would change this design

- **If we add another data source** (bonds, gold, international): extend
  `src/ingest.py` with another fetch function, join into the same parquet,
  add asset selector to the site.
- **If JSON exceeds ~5 MB:** switch to per-horizon split files
  (`returns_10y.json`, etc.) and lazy-load on selector change. We're at 640 KB
  now, with plenty of headroom.
- **If we want server-side analysis** (Monte Carlo, factor regressions on
  demand): we'd need a backend, which breaks the "free GitHub Pages" model.
  Most such analyses can be precomputed offline and exported instead — push
  hard on that before considering a backend.
- **If we ever want to drop Python entirely:** see plan.md "longer-term."
  Would require porting the rolling-window math to JS (~50 lines), adding
  JSZip + Papa Parse for source parsing, and accepting that adding new
  statistical analyses gets harder.
