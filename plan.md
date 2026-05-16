# Plan

A living document tracking what this project is, where it stands, and what's next.

## Goal

Analyze long-run U.S. stock returns using free, publicly available data via
**rolling N-year windows** under multiple contribution schedules ("scenarios").
Each scenario asks the same family of questions — "for every month in history,
if I followed this schedule for N years, what's the terminal value and what's
the annualized return?" — and produces its own interactive page, JSON file,
PDF report, and validation notebook.

Scenarios currently registered:
- **`lump_sum`** — invest $1,000 at the start of each rolling window. Metric:
  annualized CAGR. Horizons: 5/10/15/20 years.
- **`annual_dca`** — invest $100 on each yearly anniversary of the window
  start (10 deposits, $1,000 total). Metric: money-weighted IRR. Horizon: 10
  years.

The deliverable is a simple interactive website hosted free on GitHub Pages
that lets a visitor pick a scenario, scrub the window length, and toggle
between nominal and inflation-adjusted (real) returns.

## Status

**Phase 1 — Data pipeline + rolling-window analysis + initial site:** ✅ Complete.

**Phase 2 — Multi-scenario architecture + Scenario 2 (Annual DCA):** ✅ Complete (2026-05-16).

End-to-end pipeline runs cleanly across both scenarios. All sanity checks pass:

| Check | Expected | Actual |
|---|---|---|
| Full-history nominal CAGR (market) | ~9.5–10.5% | 10.20% |
| Full-history real CAGR (market) | ~6.5–7.5% | 6.99% |
| 1929–1938 (Depression) 10-yr lump-sum nominal CAGR | low/negative | −2.10% |
| 1990–1999 (bull) 10-yr lump-sum nominal CAGR | ~17–18% | 17.99% |
| 2000–2009 (lost decade) 10-yr lump-sum nominal CAGR | near zero | −0.38% |
| Oct 1987 monthly return | ~−21.5% | −22.59% |
| Mar 2020 monthly return | ~−13% | −13.25% |
| 2000–2009 10-yr annual-DCA nominal terminal | > $1,000 (textbook DCA win) | _see notebook_ |

Data spans **August 1926 → March 2026**, 1,195 monthly observations. Lump-sum
exports cover 5/10/15/20-year horizons; annual DCA covers 10 years.

Per-scenario PDF reports (`python -m src.report` → `reports/<slug>.pdf`)
share a six-page template (cover, rolling-metric chart, distribution,
best/worst tables, terminal-value chart, sources + methodology). Output is
gitignored / regenerable.

## Backlog

### Near-term (next session candidates)
- **Push to GitHub and enable Pages.** Initialize a repo, push, set Pages to
  serve from `main` branch `/docs` folder. Verify the live URL works.
- **Add a "starting amount" input to the site.** Currently hard-coded to $1,000;
  trivial to make user-adjustable.
- **Add risk-free rate overlay.** The dataset already has `rf`; plot the
  rolling N-year T-bill CAGR alongside equity for a quick equity-premium view.
- **Add drawdown chart.** Maximum drawdown within each rolling window — captures
  pain of a window, not just the endpoint.

### Medium-term
- **More statistics:** rolling Sharpe ratio, Sortino, percentile bands by horizon.
- **Bonds / gold comparison.** Damodaran's spreadsheet has matching annual series
  for 10-yr Treasury and Baa corporate; FRED has gold (`GOLDAMGBD228NLBM`).
  Useful for asset-class comparisons.
- **Pre-1926 extension.** Splice in Shiller's S&P composite for an 1871-onward
  view. Must be clearly labeled as a reconstructed/different series.
- **GitHub Action to refresh data.** Monthly cron that runs `src.ingest` +
  `src.export` and commits new `returns.json`. Keeps the live site fresh
  without manual work.

### Longer-term / speculative
- **Withdrawal-rate analysis (SWR / "Trinity study" style).** Rolling 30-year
  windows, but instead of buy-and-hold, simulate a 4% inflation-adjusted
  withdrawal — what's the survival rate by start date?
- **Factor decomposition.** The Ken French file already has SMB and HML; could
  add a "what would a tilted portfolio have done" view.
- **Cohort comparison.** "If you started investing at age 25 in year X, what
  did your portfolio look like at age 65?" — basically a 40-year rolling window
  with story framing.

## Open questions

- **CPI choice.** We use `CPIAUCNS` (not seasonally adjusted) so coverage extends
  back to 1913 and aligns with Ken French's 1926 start. The seasonally adjusted
  version (`CPIAUCSL`) is more conventional for some contexts but only goes back
  to 1947. Sticking with NSA unless someone makes a case otherwise.
- **What to do with the very first month of data.** Currently dropped because
  inflation requires a prior CPI value, costing us July 1926. Could carry it
  with `NaN` inflation and just leave real return undefined that month. Low
  stakes — one row.

## Recent decisions

- **2026-05-16:** Introduced multi-scenario architecture and added Scenario 2 (annual DCA). New `src/scenarios/` package with a registry (`SCENARIOS`), a `Scenario` protocol in `base.py` (plus a bisection IRR helper, no scipy dependency), and two scenario modules: `lump_sum.py` (refactor of the existing analysis) and `annual_dca.py` ($100 × 10 yearly anniversaries, terminal at month 120, money-weighted IRR). Refactored `src/export.py` and `src/report.py` to loop over the registry, writing one JSON and one PDF per scenario. Extracted page builders into `src/report_template.py`. Renamed `docs/data/returns.json` → `docs/data/lump_sum.json` and added `docs/data/annual_dca.json`. Restructured the site: `docs/index.html` is now a landing page and each scenario lives at `docs/scenarios/<slug>.html`, with `docs/app.js` reading the slug from a `<meta>` tag. Notebook 01 was renamed to `01_lump_sum.ipynb`; added `02_annual_dca.ipynb`. Added `.github/copilot-instructions.md` as a pointer file for GitHub Copilot CLI, and a "Cross-tool compatibility" section to `CLAUDE.md`. Rationale: extending the project to multiple scenarios was approaching, and introducing the registry on the second scenario is cheaper than on the third.
- **2026-05-15:** Added `src/report.py`, a standalone PDF report generator that
  reads `data/processed/monthly_returns.parquet` and writes
  `reports/rolling_returns.pdf` via matplotlib's `PdfPages` (no new dependencies).
  Six pages: cover with headline stats, rolling-CAGR chart, distribution
  histograms, best/worst tables, terminal-value chart, and a sources +
  methodology footnote page. Output dir is gitignored — the PDF is treated as
  a regenerable artifact, not a committed deliverable. Rationale: gives a
  shareable static summary without forcing the recipient to run anything.
- **2026-05-15:** Switched FRED CPI series from `CPIAUCSL` to `CPIAUCNS` after
  discovering the SA series starts in 1947 and was truncating Ken French's
  pre-1947 history.
- **2026-05-15:** Chose to keep the two-layer architecture (Python pipeline +
  static JS site) over a pure-JS rewrite, on the basis that pandas keeps future
  statistical analysis cheap and the current setup is already free to host.
  Reconsidered explicitly; see [design.md](design.md) for the rationale.
- **2026-05-15:** Chose Plotly.js + Pico.css over Chart.js / Bulma / Tailwind
  for the static site. Rationale: Plotly gives interactivity out of the box;
  Pico is classless and stays out of the way.
