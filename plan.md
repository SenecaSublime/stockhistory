# Plan

A living document tracking what this project is, where it stands, and what's next.

## Goal

Analyze long-run U.S. stock returns using free, publicly available data, starting
with **rolling N-year windows** — for every month in history, "if I invested
$1,000 starting here and held for N years, what's the terminal value and CAGR?"

The first deliverable is a simple interactive website hosted free on GitHub Pages
that lets a visitor scrub the window length and toggle between nominal and
inflation-adjusted (real) returns.

## Status

**Phase 1 — Data pipeline + rolling-window analysis + initial site:** ✅ Complete.

End-to-end pipeline runs cleanly. All sanity checks pass:

| Check | Expected | Actual |
|---|---|---|
| Full-history nominal CAGR | ~9.5–10.5% | 10.20% |
| Full-history real CAGR | ~6.5–7.5% | 6.99% |
| 1929–1938 (Depression) 10-yr nominal CAGR | low/negative | −2.10% |
| 1990–1999 (bull) 10-yr nominal CAGR | ~17–18% | 17.99% |
| 2000–2009 (lost decade) 10-yr nominal CAGR | near zero | −0.38% |
| Oct 1987 monthly return | ~−21.5% | −22.59% |
| Mar 2020 monthly return | ~−13% | −13.25% |

Data spans **August 1926 → March 2026**, 1,195 monthly observations, 1,076 rolling
10-year windows (5/15/20-year horizons also exported).

A standalone PDF report (`python -m src.report` → `reports/rolling_returns.pdf`)
summarizes the same headline stats, charts, and best/worst tables, with a
sources-and-methodology footnote page. Output is gitignored / regenerable.

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
