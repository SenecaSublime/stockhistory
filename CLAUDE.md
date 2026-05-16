# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

`plan.md` and `design.md` in the repo root are the canonical project-tracking docs. Read them before non-trivial work:
- `plan.md` — current goals, status, backlog, recent decisions. Living document.
- `design.md` — architecture, data-source gotchas, rolling-window math, why-this-not-that. Update it when an architectural decision changes.

**Keep these docs in sync with the code.** When you change the data flow, add or remove a module, change dependencies, change what's committed vs. regenerated, or add a new command a developer would run, update `plan.md`, `design.md`, and this file (`CLAUDE.md`) in the same turn as the code change — not as a follow-up, and not only when asked. Specifically:
- `plan.md` — add a dated entry under "Recent decisions" with the rationale; update Status if scope changed.
- `design.md` — update the architecture diagram, data flow section, and project layout.
- `CLAUDE.md` — update Common commands, the architecture summary, and the committed-vs-regenerated list.

## Common commands (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1                # activate the local venv
python -m src.ingest                        # fetch raw → data/processed/monthly_returns.parquet
python -m src.ingest --refresh              # force re-download (otherwise cached in data/raw/)
python -m src.export                        # parquet → docs/data/returns.json
python -m src.report                        # parquet → reports/rolling_returns.pdf (gitignored)
jupyter notebook notebooks/01_rolling_returns.ipynb
```

No test suite, no linter, no build step for the site. Preview the site by opening `docs/index.html` directly, or serve `docs/` with any static file server.

## Architecture

Two deliberately separated layers:

1. **Offline Python pipeline** (`src/`) — runs on the developer's machine, ingests raw data, computes rolling windows, exports a compact JSON.
2. **Static JS site** (`docs/`) — fetches the precomputed JSON and renders Plotly charts. No server, no build step, hosted on GitHub Pages directly from `/docs`.

```
src/ingest.py   → data/processed/monthly_returns.parquet  (gitignored, regenerable)
src/analysis.py → rolling-window math (pure functions over pd.Series)
src/export.py   → docs/data/returns.json                  (COMMITTED — this is what the live site reads)
src/report.py   → reports/rolling_returns.pdf             (gitignored, regenerable — multi-page PDF)
notebooks/*.ipynb → developer-only exploration; reads the parquet, no shipped output
docs/app.js     → fetch returns.json, render Plotly charts
```

The split is intentional and was reconsidered explicitly (see `design.md` "Why this architecture"). Don't propose collapsing to pure-JS without re-reading that section — pandas keeps future stats analysis cheap, and Ken French's server has no CORS so the browser can't fetch sources directly anyway.

## Data-source gotchas

- **Ken French values are in percent** (`2.50` means 2.5%, not 0.025). `ingest.py` divides by 100. Easy to forget.
- **CPI series is `CPIAUCNS` (not seasonally adjusted) by design.** The SA series `CPIAUCSL` only goes back to 1947 and silently truncates 21 years of Ken French history. Don't "fix" this to SA.
- **Total market return** = `(Mkt-RF + RF) / 100` from the Fama/French file.
- **Real return** uses the Fisher equation: `(1 + nominal) / (1 + inflation) − 1`.
- **First row (July 1926) drops** because monthly inflation needs a prior CPI value. This is deliberate.

## Rolling-window convention

`rolling_window_returns` in `src/analysis.py` labels each window by its **start** date, not its end. Pandas' `rolling(N).sum()` labels at end-of-window, so the code shifts by `-(N-1)`. If you touch this function or its callers, preserve the start-date convention — `docs/app.js` and the JSON schema (`start`, `end` keys) depend on it.

Math uses log-returns + rolling sum rather than chained multiplication, both for numerical stability over long horizons and because pandas has a well-tested `rolling().sum()` but no rolling product.

## What's committed vs. regenerated

- **Committed:** `docs/data/returns.json` — this is the data the live site needs. Each pipeline refresh produces a new one; commit it explicitly.
- **Gitignored / regenerable:** `data/raw/` (downloaded source files), `data/processed/` (the parquet), and `reports/` (PDF output). Anyone can rebuild them with `python -m src.ingest` + `python -m src.report`.

## Site stack

CDN-loaded **Pico.css 2** (classless) and **Plotly.js 2**. No bundler, no node_modules. The site is `index.html` + `app.js` + `style.css` + the JSON. If you find yourself adding a build step, stop and check `design.md` "Things that would change this design" first.

## Sanity checks

Before declaring a pipeline change correct, the full-history nominal CAGR should land around 9.5–10.5% and real around 6.5–7.5%. `plan.md` has the current expected values and several era-specific spot checks (1929–38, 1990–99, 2000–09, Oct 1987, Mar 2020) — re-running those is a fast way to catch regressions.
