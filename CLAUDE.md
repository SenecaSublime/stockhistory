# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

`plan.md` and `design.md` in the repo root are the canonical project-tracking docs. Read them before non-trivial work:
- `plan.md` — current goals, status, backlog, recent decisions. Living document.
- `design.md` — architecture, data-source gotchas, rolling-window math, why-this-not-that. Update it when an architectural decision changes.

**Keep these docs in sync with the code.** When you change the data flow, add or remove a module, change dependencies, change what's committed vs. regenerated, or add a new command a developer would run, update `plan.md`, `design.md`, this file (`CLAUDE.md`), and `.github/copilot-instructions.md` in the same turn as the code change — not as a follow-up, and not only when asked. Specifically:
- `plan.md` — add a dated entry under "Recent decisions" with the rationale; update Status if scope changed.
- `design.md` — update the architecture diagram, data flow section, and project layout.
- `CLAUDE.md` — update Common commands, the architecture summary, and the committed-vs-regenerated list.
- `.github/copilot-instructions.md` — only when the top-level "do not" rules change; it points at this file as the source of truth.

## Common commands (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1                # activate the local venv
python -m src.ingest                        # fetch raw → data/processed/monthly_returns.parquet
python -m src.ingest --refresh              # force re-download (otherwise cached in data/raw/)
python -m src.export                        # parquet → docs/data/<slug>.json   (one per scenario)
python -m src.report                        # parquet → reports/<slug>.pdf      (one per scenario, gitignored)
jupyter notebook notebooks/01_lump_sum.ipynb
jupyter notebook notebooks/02_annual_dca.ipynb
```

No test suite, no linter, no build step for the site. Preview the site by opening `docs/index.html` directly (landing page), or any `docs/scenarios/<slug>.html`. The site can also be served from `docs/` with any static file server.

## Architecture

Two deliberately separated layers:

1. **Offline Python pipeline** (`src/`) — runs on the developer's machine, ingests raw data, runs each registered scenario, exports one JSON per scenario.
2. **Static JS site** (`docs/`) — landing page plus one HTML page per scenario; `app.js` is shared and reads the scenario slug from a `<meta>` tag. No server, no build step, hosted on GitHub Pages from `/docs`.

```
src/ingest.py                → data/processed/monthly_returns.parquet  (gitignored, regenerable)
src/analysis.py              → rolling-window math (pure functions over pd.Series)
src/scenarios/__init__.py    → SCENARIOS registry — add a scenario by editing this
src/scenarios/base.py        → ScenarioMeta + Scenario protocol + solve_annual_irr helper
src/scenarios/lump_sum.py    → Scenario 1: $1,000 lump sum at window start
src/scenarios/annual_dca.py  → Scenario 2: $100 × 10 yearly anniversaries
src/export.py                → docs/data/<slug>.json                    (COMMITTED — site reads these)
src/report_template.py       → shared PDF page builders
src/report.py                → reports/<slug>.pdf                       (gitignored, regenerable)
notebooks/NN_<slug>.ipynb    → per-scenario exploration; reads the parquet, no shipped output
docs/index.html              → landing page with scenario links
docs/scenarios/<slug>.html   → one page per scenario; <meta name="scenario-slug"> drives app.js
docs/app.js                  → fetch ../data/<slug>.json, render Plotly charts
.github/copilot-instructions.md → pointer file for Copilot CLI (see Cross-tool below)
```

The split is intentional and was reconsidered explicitly (see `design.md` "Why this architecture"). Don't propose collapsing to pure-JS without re-reading that section — pandas keeps future stats analysis cheap, and Ken French's server has no CORS so the browser can't fetch sources directly anyway.

## Adding a new scenario

1. Create `src/scenarios/<slug>.py` with a class whose `meta` is a `ScenarioMeta` (slug, title, description, total_invested, metric_name, horizons, methodology_lines) and which implements `compute_windows(monthly, horizon)` returning a DataFrame with columns `end_date`, `nominal_terminal`, `real_terminal`, `nominal_metric`, `real_metric`.
2. Append an instance to `SCENARIOS` in `src/scenarios/__init__.py`.
3. Create `docs/scenarios/<slug>.html` (copy an existing one and update the `<meta name="scenario-slug">` + headings).
4. Link it from `docs/index.html`.
5. Create `notebooks/NN_<slug>.ipynb` for validation/exploration.
6. Run `python -m src.export` and `python -m src.report`.
7. Update `plan.md`, `design.md`, this file, and `.github/copilot-instructions.md` in the same commit.

Terminal-value columns are in **dollars** (already multiplied by `total_invested`); metric columns are decimal annual rates. The frontend and report template assume this — don't re-introduce per-$1 multipliers.

## Cross-tool compatibility (Claude Code + Copilot CLI)

The project supports both Claude Code and GitHub Copilot CLI. `CLAUDE.md` and `design.md` are the canonical project instructions; `.github/copilot-instructions.md` is a short pointer file that tells Copilot to read them. When you change top-level rules here (the "Data-source gotchas" section, the "do not" list, the workflow for adding scenarios), update the Copilot file too. Don't let the two files duplicate long-form content — keep the pointer file thin.

GitHub-level repository instructions (configurable in repo settings on github.com) should also point at `CLAUDE.md` and `design.md`. These are not version-controlled in this repo.

## Data-source gotchas

- **Ken French values are in percent** (`2.50` means 2.5%, not 0.025). `ingest.py` divides by 100. Easy to forget.
- **CPI series is `CPIAUCNS` (not seasonally adjusted) by design.** The SA series `CPIAUCSL` only goes back to 1947 and silently truncates 21 years of Ken French history. Don't "fix" this to SA.
- **Total market return** = `(Mkt-RF + RF) / 100` from the Fama/French file.
- **Real return** uses the Fisher equation: `(1 + nominal) / (1 + inflation) − 1`.
- **First row (July 1926) drops** because monthly inflation needs a prior CPI value. This is deliberate.

## Rolling-window convention

`rolling_window_returns` in `src/analysis.py` labels each window by its **start** date, not its end. Pandas' `rolling(N).sum()` labels at end-of-window, so the code shifts by `-(N-1)`. If you touch this function or its callers, preserve the start-date convention — `docs/app.js` and the JSON schema (`start`, `end` keys) depend on it, as does every scenario's `compute_windows` output.

Math uses log-returns + rolling sum rather than chained multiplication, both for numerical stability over long horizons and because pandas has a well-tested `rolling().sum()` but no rolling product. The DCA scenario reuses this convention via cumulative log-sums (see `src/scenarios/annual_dca.py`).

## What's committed vs. regenerated

- **Committed:** `docs/data/<slug>.json` for every registered scenario — this is the data the live site needs. Each pipeline refresh produces fresh JSONs; commit them explicitly.
- **Gitignored / regenerable:** `data/raw/` (downloaded source files), `data/processed/` (the parquet), and `reports/` (per-scenario PDFs). Anyone can rebuild them with `python -m src.ingest` + `python -m src.export` + `python -m src.report`.

## Site stack

CDN-loaded **Pico.css 2** (classless) and **Plotly.js 2**. No bundler, no node_modules. The site is `index.html` + `app.js` + `style.css` + the JSON. If you find yourself adding a build step, stop and check `design.md` "Things that would change this design" first.

## Sanity checks

Before declaring a pipeline change correct, the full-history nominal CAGR should land around 9.5–10.5% and real around 6.5–7.5%. `plan.md` has the current expected values and several era-specific spot checks (1929–38, 1990–99, 2000–09, Oct 1987, Mar 2020) — re-running those is a fast way to catch regressions.
