"""Scenario 1 — $1,000 lump-sum at the start of each rolling N-year window.

Reuses ``rolling_window_returns`` from ``src/analysis.py`` and scales the
per-$1 terminal multipliers into dollar terminals at the scenario's
``total_invested`` amount.
"""
from __future__ import annotations

import pandas as pd

from ..analysis import rolling_window_returns
from .base import ScenarioMeta


class LumpSum1k:
    meta = ScenarioMeta(
        slug="lump_sum",
        title="$1,000 lump sum",
        short_title="Lump sum",
        description=(
            "Invest $1,000 at the start of each rolling N-year window and hold "
            "to the end. The metric is annualized CAGR — the constant annual "
            "rate that grows $1,000 to the terminal value over N years."
        ),
        total_invested=1000.0,
        metric_name="CAGR",
        horizons=(5, 10, 15, 20),
        methodology_lines=(
            "    For each month t, compound the next N*12 monthly returns:",
            "      terminal(t) = $1,000 * exp( Σ log(1 + r_i) )   for i in [t, t+N*12-1]",
            "      CAGR(t)     = (terminal(t) / $1,000) ^ (1 / N) - 1",
            "    Log-returns are summed (not products chained) for numerical stability",
            "    over long horizons. Each window is labeled by its START month, not its",
            "    end. Windows lacking a full N*12 months are dropped from the tail.",
        ),
    )

    def total_invested(self, horizon: int) -> float:
        """Lump-sum is $1,000 regardless of horizon (the same $1,000 just compounds
        for longer)."""
        return self.meta.total_invested

    def compute_windows(self, monthly: pd.DataFrame, horizon: int) -> pd.DataFrame:
        nom = rolling_window_returns(monthly["nominal_return"], years=horizon)
        real = rolling_window_returns(monthly["real_return"], years=horizon)
        scale = self.meta.total_invested

        return pd.DataFrame({
            "end_date": nom["end_date"],
            "nominal_terminal": nom["terminal_value"] * scale,
            "real_terminal": real["terminal_value"] * scale,
            "nominal_metric": nom["cagr"],
            "real_metric": real["cagr"],
        })
