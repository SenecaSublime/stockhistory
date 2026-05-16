"""Export rolling-window analysis to a JSON file for the static site."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .analysis import rolling_window_returns

ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = ROOT / "data" / "processed" / "monthly_returns.parquet"
JSON_PATH = ROOT / "docs" / "data" / "returns.json"

HORIZONS = (5, 10, 15, 20)


def build() -> Path:
    df = pd.read_parquet(PARQUET_PATH).set_index("date").sort_index()

    monthly = [
        {
            "date": d.strftime("%Y-%m-%d"),
            "nominal": round(float(n), 6),
            "real": round(float(r), 6),
        }
        for d, n, r in zip(df.index, df["nominal_return"], df["real_return"])
    ]

    rolling: dict[str, list[dict]] = {}
    for years in HORIZONS:
        nom = rolling_window_returns(df["nominal_return"], years).rename(
            columns={"terminal_value": "nominal_terminal", "cagr": "nominal_cagr"}
        )
        real = rolling_window_returns(df["real_return"], years).rename(
            columns={"terminal_value": "real_terminal", "cagr": "real_cagr"}
        )
        joined = nom.join(real[["real_terminal", "real_cagr"]])

        rolling[str(years)] = [
            {
                "start": idx.strftime("%Y-%m-%d"),
                "end": row.end_date.strftime("%Y-%m-%d"),
                "nominal_cagr": round(float(row.nominal_cagr), 6),
                "real_cagr": round(float(row.real_cagr), 6),
                "nominal_terminal": round(float(row.nominal_terminal), 6),
                "real_terminal": round(float(row.real_terminal), 6),
            }
            for idx, row in joined.iterrows()
        ]

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump({"monthly": monthly, "rolling": rolling}, f, separators=(",", ":"))

    size_kb = JSON_PATH.stat().st_size / 1024
    print(f"Wrote {JSON_PATH} ({size_kb:,.1f} KB)")
    return JSON_PATH


if __name__ == "__main__":
    build()
