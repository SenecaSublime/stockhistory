"""Scenario 2 — $100 invested on each yearly anniversary of the window start.

For an N-year horizon: N deposits of $100 each at months 0, 12, ..., 12*(N-1),
terminal measured at month 12*N. Total contributed = $100 * N (so $500 at the
5-year horizon, $1,000 at 10, $2,000 at 20).

Each deposit compounds from its own start month to the end of the window using
the same monthly-return convention as ``rolling_window_returns``: a deposit
made at month ``m`` earns the returns at indices ``m, m+1, ..., end-1``.

The metric is the money-weighted IRR — the annual rate that grows each $100
deposit by its own time-to-end and sums to the terminal value. Computed by
bisection in ``base.solve_annual_irr`` to avoid a scipy dependency.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import ScenarioMeta, solve_annual_irr

DEPOSIT_AMOUNT = 100.0
PERIOD_MONTHS = 12  # one year between deposits
HORIZONS = (5, 10, 15, 20)


class AnnualDCA100:
    meta = ScenarioMeta(
        slug="annual_dca",
        title="$100 annual DCA",
        short_title="Annual DCA",
        description=(
            "Invest $100 on each yearly anniversary of the window start. Total "
            "contributed scales with the horizon — $500 over 5 years, $1,000 "
            "over 10, $2,000 over 20. The metric is the money-weighted "
            "internal rate of return (IRR) — the annual rate that discounts "
            "the deposits to the terminal value. Comparing IRR here to CAGR "
            "in the lump-sum scenario shows how much the timing of deployed "
            "capital matters."
        ),
        # Reference value used in scenario-level metadata. The PDF report
        # picks one horizon (10 years), so $1,000 lines up with the printed
        # totals there. The website reads per-horizon values from the JSON.
        total_invested=DEPOSIT_AMOUNT * 10,
        metric_name="IRR",
        horizons=HORIZONS,
        methodology_lines=(
            "    For each window start t and N-year horizon, deposit $100 at months",
            "    t+0, t+12, ..., t+12*(N-1) (N yearly anniversaries). Each deposit at",
            "    month m grows by the product of monthly returns from m to the end of",
            "    the window (month t+12*N):",
            "      grown_k     = $100 * exp( Σ log(1 + r_i) )   for i in [t+12k, t+12N-1]",
            "      terminal(t) = sum of grown_0 ... grown_{N-1}",
            "    IRR(t) is the annual rate R solving:",
            "      Σ $100 * (1+R) ^ (N-k) = terminal(t)   for k in 0..N-1",
            "    Solved by bisection. Same start-month labeling and tail-drop rules as",
            "    the lump-sum scenario. Total contributed per window = $100 * N.",
        ),
    )

    def total_invested(self, horizon: int) -> float:
        """Per-horizon total contributions: $100 per yearly deposit, N deposits."""
        return DEPOSIT_AMOUNT * horizon

    def compute_windows(self, monthly: pd.DataFrame, horizon: int) -> pd.DataFrame:
        horizon_months = horizon * 12
        num_deposits = horizon  # one deposit per year

        idx = monthly.index
        n = len(monthly)
        nominal = monthly["nominal_return"].to_numpy()
        real = monthly["real_return"].to_numpy()

        # Precompute cumulative log-returns so each deposit's growth factor
        # over its sub-window is a difference of two cumulative sums.
        cum_log_nom = np.concatenate(([0.0], np.cumsum(np.log1p(nominal))))
        cum_log_real = np.concatenate(([0.0], np.cumsum(np.log1p(real))))

        years_to_end = [horizon - k for k in range(num_deposits)]  # [N, N-1, ..., 1]
        amounts = [DEPOSIT_AMOUNT] * num_deposits

        starts: list[pd.Timestamp] = []
        end_dates: list[pd.Timestamp] = []
        nom_terms: list[float] = []
        real_terms: list[float] = []
        nom_irrs: list[float] = []
        real_irrs: list[float] = []

        last_start = n - horizon_months
        for i in range(last_start + 1):
            window_end_idx = i + horizon_months - 1
            starts.append(idx[i])
            end_dates.append(idx[window_end_idx])

            nom_terminal = 0.0
            real_terminal = 0.0
            for k in range(num_deposits):
                m = i + k * PERIOD_MONTHS
                end_excl = i + horizon_months  # exclusive index into return array
                # Growth factor = exp(sum_{j=m..end_excl-1} log(1 + r_j))
                #               = exp(cum_log[end_excl] - cum_log[m])
                nom_factor = np.exp(cum_log_nom[end_excl] - cum_log_nom[m])
                real_factor = np.exp(cum_log_real[end_excl] - cum_log_real[m])
                nom_terminal += DEPOSIT_AMOUNT * nom_factor
                real_terminal += DEPOSIT_AMOUNT * real_factor

            nom_terms.append(nom_terminal)
            real_terms.append(real_terminal)
            nom_irrs.append(solve_annual_irr(amounts, years_to_end, nom_terminal))
            real_irrs.append(solve_annual_irr(amounts, years_to_end, real_terminal))

        return pd.DataFrame({
            "end_date": end_dates,
            "nominal_terminal": nom_terms,
            "real_terminal": real_terms,
            "nominal_metric": nom_irrs,
            "real_metric": real_irrs,
        }, index=pd.Index(starts))
