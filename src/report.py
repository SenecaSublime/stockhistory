"""Generate per-scenario PDF reports from the processed monthly returns parquet.

Run: ``python -m src.report``. Writes one PDF per registered scenario to
``docs/reports/<slug>.pdf`` so each report is served alongside the live site
and is reachable from the scenario page's download link. Reports use the
standard layout from ``src.report_template``; per-scenario specifics (titles,
metric labels, methodology blurb) come from each ``ScenarioMeta``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from . import report_template as tpl
from .scenarios import SCENARIOS, Scenario

ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = ROOT / "data" / "processed" / "monthly_returns.parquet"
REPORTS_DIR = ROOT / "docs" / "reports"

# All current scenarios include 10 years in their horizons. If a future scenario
# doesn't, fall back to that scenario's longest horizon.
REPORT_HORIZON_YEARS = 10
TOTAL_PAGES = 6


def _horizon_for(scenario: Scenario) -> int:
    if REPORT_HORIZON_YEARS in scenario.meta.horizons:
        return REPORT_HORIZON_YEARS
    return max(scenario.meta.horizons)


def _build_one(scenario: Scenario, monthly: pd.DataFrame, output_path: Path) -> None:
    horizon = _horizon_for(scenario)
    windows = scenario.compute_windows(monthly, horizon).dropna()

    with PdfPages(output_path) as pdf:
        tpl.add_cover(pdf, scenario.meta, monthly, windows, horizon, 1, TOTAL_PAGES)
        tpl.add_rolling_metric_chart(pdf, scenario.meta, windows, horizon, 2, TOTAL_PAGES)
        tpl.add_distribution_page(pdf, scenario.meta, windows, horizon, 3, TOTAL_PAGES)
        tpl.add_best_worst_tables(pdf, scenario.meta, windows, horizon, 4, TOTAL_PAGES)
        tpl.add_terminal_chart(pdf, scenario.meta, windows, horizon, 5, TOTAL_PAGES)
        tpl.add_methodology_page(pdf, scenario.meta, monthly, horizon, 6, TOTAL_PAGES)

        pdf.infodict()["Title"] = (
            f"Fubar Analytics — Rolling-window U.S. stock returns — {scenario.meta.title}"
        )
        pdf.infodict()["Author"] = "Fubar Analytics"
        pdf.infodict()["Subject"] = (
            f"{horizon}-year rolling {scenario.meta.metric_name} and distribution "
            "of U.S. total-market returns"
        )


def build() -> list[Path]:
    if not PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"{PARQUET_PATH} not found. Run `python -m src.ingest` first."
        )
    monthly = pd.read_parquet(PARQUET_PATH).set_index("date").sort_index()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for scenario in SCENARIOS:
        out = REPORTS_DIR / f"{scenario.meta.slug}.pdf"
        _build_one(scenario, monthly, out)
        print(f"Wrote {out}")
        written.append(out)
    return written


if __name__ == "__main__":
    build()
