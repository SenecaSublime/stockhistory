"""Export each registered scenario to its own JSON file for the static site.

Writes ``docs/data/<slug>.json`` for every scenario in
``src/scenarios.SCENARIOS``. The JSON shape is scenario-agnostic so a single
``docs/app.js`` can render any scenario page.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .scenarios import SCENARIOS, Scenario

ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = ROOT / "data" / "processed" / "monthly_returns.parquet"
JSON_DIR = ROOT / "docs" / "data"


def _build_one(scenario: Scenario, monthly: pd.DataFrame) -> dict:
    rolling: dict[str, list[dict]] = {}
    for years in scenario.meta.horizons:
        df = scenario.compute_windows(monthly, years).dropna()
        rolling[str(years)] = [
            {
                "start": idx.strftime("%Y-%m-%d"),
                "end": row.end_date.strftime("%Y-%m-%d"),
                "nominal_terminal": round(float(row.nominal_terminal), 2),
                "real_terminal": round(float(row.real_terminal), 2),
                "nominal_metric": round(float(row.nominal_metric), 6),
                "real_metric": round(float(row.real_metric), 6),
            }
            for idx, row in df.iterrows()
        ]

    monthly_rows = [
        {
            "date": d.strftime("%Y-%m-%d"),
            "nominal": round(float(n), 6),
            "real": round(float(r), 6),
        }
        for d, n, r in zip(monthly.index, monthly["nominal_return"], monthly["real_return"])
    ]

    return {
        "scenario": {
            "slug": scenario.meta.slug,
            "title": scenario.meta.title,
            "short_title": scenario.meta.short_title,
            "description": scenario.meta.description,
            "total_invested": scenario.meta.total_invested,
            "metric_name": scenario.meta.metric_name,
            "horizons": list(scenario.meta.horizons),
        },
        "monthly": monthly_rows,
        "rolling": rolling,
    }


def build() -> list[Path]:
    monthly = pd.read_parquet(PARQUET_PATH).set_index("date").sort_index()
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for scenario in SCENARIOS:
        payload = _build_one(scenario, monthly)
        out = JSON_DIR / f"{scenario.meta.slug}.json"
        with open(out, "w") as f:
            json.dump(payload, f, separators=(",", ":"))
        size_kb = out.stat().st_size / 1024
        print(f"Wrote {out} ({size_kb:,.1f} KB)")
        written.append(out)

    return written


if __name__ == "__main__":
    build()
