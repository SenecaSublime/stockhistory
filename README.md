# U.S. Stock Returns — Rolling Window Analysis

Long-run analysis of U.S. total-market returns using free public data:

- **Ken French Data Library** — monthly value-weighted U.S. total-market returns (July 1926 onward), derived from CRSP.
- **FRED CPIAUCNS** — monthly CPI (not seasonally adjusted) for inflation-adjusting nominal returns into real returns. NSA chosen over SA so coverage extends back to 1913 and aligns with Ken French's 1926-07 start.

The project supports multiple **scenarios** — different contribution schedules applied to the same monthly returns. Each scenario produces an interactive website page, a JSON file consumed by the live site, a PDF report, and a validation notebook. Currently registered:

- **`lump_sum`** — $1,000 invested at the start of each rolling N-year window. Metric: annualized CAGR.
- **`annual_dca`** — $100 invested on each yearly anniversary of the window start (10 deposits, $1,000 total). Metric: money-weighted IRR.

The Python pipeline computes per-scenario rolling-window outputs and exports a compact JSON per scenario. The static site in `docs/` reads those JSONs and renders interactive charts; it is hosted on GitHub Pages directly from `docs/`.

## Setup (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the pipeline

```powershell
python -m src.ingest    # downloads raw data, writes data/processed/monthly_returns.parquet
python -m src.export    # writes docs/data/<slug>.json for every registered scenario
python -m src.report    # writes reports/<slug>.pdf for every registered scenario (gitignored)
```

## Notebooks

```powershell
jupyter notebook notebooks/01_lump_sum.ipynb
jupyter notebook notebooks/02_annual_dca.ipynb
```

## Local site preview

Open `docs/index.html` directly in a browser to see the landing page, or open any `docs/scenarios/<slug>.html` to see one scenario. Or serve the `docs/` folder with any static file server. No build step.

## Adding a new scenario

See the "Adding a new scenario" section in [`CLAUDE.md`](CLAUDE.md) for the full checklist. The short version:

1. Add `src/scenarios/<slug>.py` implementing the `Scenario` protocol from `src/scenarios/base.py`.
2. Append an instance to `SCENARIOS` in `src/scenarios/__init__.py`.
3. Add `docs/scenarios/<slug>.html` and link it from `docs/index.html`.
4. Add `notebooks/NN_<slug>.ipynb`.
5. Run `python -m src.export` and `python -m src.report`.

## Project docs

- [`CLAUDE.md`](CLAUDE.md) — project conventions and "do not" rules (read first if working with an LLM coding agent).
- [`design.md`](design.md) — architecture, data flow, rolling-window math, PDF report layout.
- [`plan.md`](plan.md) — current goals, status, backlog, recent decisions.
- [`.github/copilot-instructions.md`](.github/copilot-instructions.md) — pointer file for GitHub Copilot CLI.

## Layout

```
src/         Python pipeline (ingest, analysis, scenarios, export, report, report_template)
notebooks/   Per-scenario Jupyter notebooks for validation and exploration
docs/        Static site (HTML + JS + CSS + per-scenario JSONs), served by GitHub Pages
data/        Local working data (gitignored; regenerable)
reports/     Per-scenario PDF outputs (gitignored; regenerable)
.github/     Cross-tool instruction file for GitHub Copilot CLI
```
