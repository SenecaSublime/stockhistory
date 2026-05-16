# Design

How the system is built and why. Paired with [plan.md](plan.md), which covers
what's being built and when.

## Architecture at a glance

```
┌─────────────────────┐  ┌──────────────┐  ┌──────────────────┐
│ Ken French zip      │  │              │  │ monthly_returns  │
│ (1926+ market ret.) │─►│  src/ingest  │─►│ .parquet         │
└─────────────────────┘  │              │  │ (local working   │
┌─────────────────────┐  │              │  │  artifact)       │
│ FRED CPIAUCNS CSV   │─►│              │  │                  │
│ (1913+ CPI)         │  └──────────────┘  └────────┬─────────┘
└─────────────────────┘                             │
                                                    ▼
                    ┌────────────────────────────────────────────────┐
                    │   src/scenarios/ — registered analyses         │
                    │   (lump_sum, annual_dca, …)                    │
                    │   Each .compute_windows() over the parquet     │
                    └───┬─────────────────┬──────────────────────┬───┘
                        │                 │                      │
                        ▼                 ▼                      ▼
              ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
              │ src/export.py    │ │ src/report.py +  │ │ notebooks/       │
              │                  │ │ report_template  │ │ NN_<slug>.ipynb  │
              └────────┬─────────┘ └────────┬─────────┘ └──────────────────┘
                       ▼                    ▼                 (dev-only)
              ┌──────────────────┐ ┌──────────────────┐
              │ docs/data/       │ │ reports/         │
              │   <slug>.json    │ │   <slug>.pdf     │
              │ (one per         │ │ (one per         │
              │  scenario,       │ │  scenario,       │
              │  committed)      │ │  gitignored)     │
              └────────┬─────────┘ └──────────────────┘
                       ▼
              ┌──────────────────┐
              │ docs/index.html  │  landing page → docs/scenarios/<slug>.html
              │ + shared app.js  │  (one page per scenario)
              └──────────────────┘
              ◄─── offline (Python) ─────►  ◄── live (JS) ──►
```

The parquet feeds the **scenario registry** in `src/scenarios/`. Each scenario
declares its metadata (slug, title, metric name, contribution schedule) and a
`compute_windows()` method. Three downstream consumers iterate over the
registry independently: `src/export.py` (one JSON per scenario for the live
site), `src/report.py` (one PDF per scenario, via `src/report_template.py`),
and `notebooks/NN_<slug>.ipynb` (developer-only exploration). Adding a new
scenario means adding a module + one HTML page + one notebook; the rest is
picked up automatically by the loops in `export.py` and `report.py`.

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
   - Scenario-agnostic: reused by `src/scenarios/lump_sum.py` directly and by
     `src/scenarios/annual_dca.py` via cumulative log-sums.

3. **`src/scenarios/`** — registry of analyses
   - `base.py` defines `ScenarioMeta` (slug, title, description,
     total_invested, metric_name, horizons, methodology_lines) and the
     `Scenario` protocol with `compute_windows(monthly, horizon)`. Also exposes
     `solve_annual_irr` (bisection IRR solver — no scipy dependency).
   - `lump_sum.py` — Scenario 1: $1,000 invested at the start of each rolling
     N-year window; metric is annualized CAGR. Wraps `rolling_window_returns`.
   - `annual_dca.py` — Scenario 2: $100 invested on each yearly anniversary of
     the window start (ten deposits, $1,000 total); metric is money-weighted
     IRR. Terminal value computed by compounding each deposit from its own
     start month to the end of the window via cumulative log-sums.
   - `__init__.py` exports the `SCENARIOS` list. Adding a scenario means
     creating a module here and appending an instance.

4. **`src/export.py`**
   - Loops over `SCENARIOS`. For each scenario × each declared horizon,
     calls `compute_windows` and writes `docs/data/<slug>.json`.
   - The JSON shape is scenario-agnostic so a single `docs/app.js` renders any
     scenario page:
     ```json
     {
       "scenario": {
         "slug": "annual_dca",
         "title": "$100 annual DCA",
         "short_title": "Annual DCA",
         "description": "...",
         "total_invested": 1000,
         "metric_name": "IRR",
         "horizons": [10]
       },
       "monthly": [{ "date", "nominal", "real" }, ...],
       "rolling": {
         "10": [{ "start", "end", "nominal_terminal", "real_terminal",
                  "nominal_metric", "real_metric" }, ...],
         "5": [...], "15": [...], "20": [...]
       }
     }
     ```
   - Terminal values are in **dollars** (already scaled by `total_invested`);
     metric values are decimal annual rates. The `metric_name` field labels
     what the metric column means ("CAGR" or "IRR").

5. **`docs/app.js` + `docs/index.html` + `docs/scenarios/<slug>.html`**
   - `docs/index.html` is a static landing page with a hand-authored list of
     scenarios linking to their detail pages.
   - Each `docs/scenarios/<slug>.html` is a thin shell with a
     `<meta name="scenario-slug" content="<slug>">` tag, headings, and empty
     containers for charts. The shared `docs/app.js` reads the slug, fetches
     `../data/<slug>.json`, and bootstraps the horizon dropdown (from
     `scenario.horizons`), the metric labels (from `scenario.metric_name`),
     and the break-even reference (from `scenario.total_invested`).
   - All compute in the browser is slicing and mapping over precomputed
     fields — no time-series math.

6. **`src/report_template.py` + `src/report.py`**
   - `report_template.py` exposes per-page builders (`add_cover`,
     `add_rolling_metric_chart`, `add_distribution_page`,
     `add_best_worst_tables`, `add_terminal_chart`, `add_methodology_page`).
     Each takes a `ScenarioMeta` and the windows DataFrame and renders one
     page using `PdfPages`. Style conventions are documented in the "PDF
     report layout" section below.
   - `report.py` loops over `SCENARIOS`, picks the 10-year horizon (or each
     scenario's longest available horizon if 10 is not declared), and writes
     `reports/<slug>.pdf` via the template helpers. Each non-cover page
     carries a short footer citing Ken French + FRED.
   - No new dependencies — matplotlib only.
   - Output dir is gitignored; per-scenario PDFs are regenerable, not
     committed deliverables. Rebuild with `python -m src.report`.

7. **`notebooks/NN_<slug>.ipynb`** — one per scenario
   - Exploratory, developer-only consumers of `monthly_returns.parquet`. Each
     notebook validates and explores one scenario, calling the same
     `compute_windows` that `src/export.py` and `src/report.py` use. Nothing
     is exported, committed, or consumed downstream.
   - Role: prototype new analyses and double-check scenario math before/after
     touching `src/scenarios/`. Findings worth keeping graduate into a new
     scenario module, the report template, or `design.md`; the notebooks
     themselves are not part of the shipped pipeline.
   - Run with `jupyter notebook notebooks/<file>.ipynb` from the project root
     after activating `.venv`.

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
├── reports/                         # per-scenario PDFs (gitignored)
├── src/
│   ├── __init__.py
│   ├── ingest.py                    # raw → parquet
│   ├── analysis.py                  # rolling-window math (scenario-agnostic)
│   ├── scenarios/
│   │   ├── __init__.py              # SCENARIOS registry
│   │   ├── base.py                  # ScenarioMeta + protocol + IRR helper
│   │   ├── lump_sum.py              # Scenario 1
│   │   └── annual_dca.py            # Scenario 2
│   ├── export.py                    # parquet → one JSON per scenario
│   ├── report_template.py           # shared PDF page builders
│   └── report.py                    # parquet → one PDF per scenario
├── notebooks/
│   ├── 01_lump_sum.ipynb            # validation + exploration for scenario 1
│   └── 02_annual_dca.ipynb          # validation + exploration for scenario 2
├── docs/                            # GitHub Pages root
│   ├── index.html                   # landing page with scenario links
│   ├── scenarios/
│   │   ├── lump-sum.html            # one page per scenario
│   │   └── annual-dca.html
│   ├── app.js                       # shared renderer (reads <meta name="scenario-slug">)
│   ├── style.css                    # small overrides
│   └── data/
│       ├── lump_sum.json            # committed; written by src/export.py
│       └── annual_dca.json          # committed; written by src/export.py
├── .github/
│   └── copilot-instructions.md      # pointer file for GitHub Copilot CLI
├── .venv/                           # local Python env (gitignored)
├── requirements.txt
├── plan.md
├── design.md
├── CLAUDE.md
└── README.md
```

`data/processed/` is **not** committed — it's a regenerable local artifact.
`docs/data/<slug>.json` (one per registered scenario) **is** committed — it's
the data the live site needs. `reports/<slug>.pdf` is gitignored and
regenerable.

## PDF report layout

All scenario reports share the same six-page structure, produced by
`src/report_template.py`. Per-scenario specifics (titles, the metric column
name, the deposit-schedule blurb on the methodology page) come from each
scenario's `ScenarioMeta`. Layout conventions:

- **Page size**: 8.5 × 11 inches portrait, matplotlib `PdfPages`.
- **Typography**: matplotlib defaults (Helvetica/DejaVu Sans). Cover uses a
  two-line title — 18 pt bold project name plus a 14 pt scenario subtitle.
  Content pages use a single 14 pt bold title. Body text 9–11 pt. Lighter
  accents at `#444444`–`#777777`; table header fill `#eeeeee`.
- **Margins**: titles sit at y=0.93 (≈ 0.77 in from the top), and chart /
  table axes use x-margins of 0.10–0.12 (≈ 0.85–1.00 in) on the left and
  right. Long titles must fit at the chosen font size with at least 1 in of
  side margin — split into two lines or shorten before increasing font size.
- **Header / footer**: title centered at the top of each page. Footer
  centered with the standard sources blurb plus `N / total` at the right.
- **Page sequence** (`src/report.py` calls these in order):
  1. **Cover** — project title + scenario subtitle; data span and generation
     date; then a summary block with: full-history nominal & real market
     CAGR; rolling-metric mean, highest, and lowest (each split nominal &
     real); count and share of windows with metric ≤ 0; total windows;
     window labeling; total contributed per window; and a description blurb
     at the bottom.
  2. **Rolling metric chart** — nominal vs. real line chart of the metric
     across all window starts, plus a six-row summary stats table.
  3. **Distribution** — side-by-side nominal and real histograms with a
     callout for share ≤ 0.
  4. **Best & worst** — top 5 best and worst windows by metric, separately
     for nominal and real, in a 2×2 table grid.
  5. **Terminal value** — line chart of dollar terminals across window
     starts, with a horizontal break-even reference at `total_invested`.
  6. **Sources and methodology** — five blocks: data sources, series
     construction, the scenario's deposit schedule and metric definition
     (`ScenarioMeta.methodology_lines`), full-history market CAGR formula,
     reproducibility commands.
- **Adding a new chart type**: add a helper to `report_template.py` with the
  same signature shape (`pdf`, `meta`, `windows`, `horizon`, `page_num`,
  `total_pages`), bump `TOTAL_PAGES` in `report.py`, and call it from the
  sequence. Keep all chart styling decisions in the template; never inline
  matplotlib styling in `report.py`.
- **Terminal-value scaling**: terminal columns from `compute_windows()` are
  already in dollars (scaled by `total_invested`). Never re-multiply.

## Cross-tool compatibility

The project is intended to be worked on with either Claude Code or GitHub
Copilot CLI. `CLAUDE.md` and `design.md` are the canonical instructions;
`.github/copilot-instructions.md` is a short pointer file that tells Copilot
to read them and lists the most important "do not" rules. Keep the pointer
file thin — long-form content stays here and in `CLAUDE.md`. When the
top-level rules change, update both files in the same commit.

## Site stack

- **Pico.css 2** (via jsDelivr CDN). Classless / semantic-HTML-friendly,
  ~10 KB. The site is mostly `<main>`, `<article>`, `<table>` with no class soup.
- **Plotly.js 2** (via Plotly CDN). Larger (~3 MB) but interactive
  out-of-the-box (zoom, hover, range selection). For exploratory charts with
  three views, it pays for itself in lines of code saved versus Chart.js or D3.
- **No build step.** No bundler, no transpilation, no node_modules. The site
  is three files plus a JSON.

## Versioning the data

`docs/data/<slug>.json` for every registered scenario is committed to the
repo. Each refresh produces fresh JSONs; git history serves as the changelog.
The raw downloads in `data/raw/` are gitignored — they're re-fetchable from
the canonical URLs.

This means: visitors get whatever was last committed. To refresh:

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.ingest --refresh    # force re-download
python -m src.export              # writes docs/data/*.json
git add docs/data/*.json
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
