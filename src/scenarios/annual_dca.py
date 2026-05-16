"""Scenario 2 — $100 invested on each yearly anniversary of the window start,
ten deposits, terminal measured at month 120.

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
NUM_DEPOSITS = 10
PERIOD_MONTHS = 12  # one year between deposits
HORIZON_YEARS = 10
HORIZON_MONTHS = HORIZON_YEARS * 12


class AnnualDCA100:
    meta = ScenarioMeta(
        slug="annual_dca",
        title="$100 annual DCA",
        short_title="Annual DCA",
        description=(
            "Invest $100 on each yearly anniversary of the window start — ten "
            "deposits over ten years, $1,000 total contributed. The metric is "
            "the money-weighted internal rate of return (IRR) — the annual "
            "rate that discounts the ten deposits to the terminal value. "
            "Comparing IRR here to CAGR in the lump-sum scenario shows how "
            "much the timing of deployed capital matters."
        ),
        total_invested=DEPOSIT_AMOUNT * NUM_DEPOSITS,
        metric_name="IRR",
        horizons=(HORIZON_YEARS,),
        methodology_lines=(
            "    For each window start t, deposit $100 at months t+0, t+12, ..., t+108",
            "    (ten yearly anniversaries). Each deposit at month m grows by the product",
            "    of monthly returns from m to the end of the window (month t+120):",
            "      grown_k     = $100 * exp( Σ log(1 + r_i) )   for i in [t+12k, t+120-1]",
            "      terminal(t) = sum of grown_0 ... grown_9",
            "    IRR(t) is the annual rate R solving:",
            "      Σ $100 * (1+R) ^ (10-k) = terminal(t)   for k in 0..9",
            "    Solved by bisection. Same start-month labeling and tail-drop rules as the",
            "    lump-sum scenario.",
        ),
    )

    def compute_windows(self, monthly: pd.DataFrame, horizon: int) -> pd.DataFrame:
        if horizon != HORIZON_YEARS:
            return pd.DataFrame(columns=[
                "end_date", "nominal_terminal", "real_terminal",
                "nominal_metric", "real_metric",
            ])

        idx = monthly.index
        n = len(monthly)
        nominal = monthly["nominal_return"].to_numpy()
        real = monthly["real_return"].to_numpy()

        # Precompute cumulative log-returns so each deposit's growth factor
        # over its sub-window is a difference of two cumulative sums.
        cum_log_nom = np.concatenate(([0.0], np.cumsum(np.log1p(nominal))))
        cum_log_real = np.concatenate(([0.0], np.cumsum(np.log1p(real))))

        years_to_end = [HORIZON_YEARS - k for k in range(NUM_DEPOSITS)]  # [10, 9, ..., 1]
        amounts = [DEPOSIT_AMOUNT] * NUM_DEPOSITS

        starts: list[pd.Timestamp] = []
        end_dates: list[pd.Timestamp] = []
        nom_terms: list[float] = []
        real_terms: list[float] = []
        nom_irrs: list[float] = []
        real_irrs: list[float] = []

        last_start = n - HORIZON_MONTHS
        for i in range(last_start + 1):
            window_end_idx = i + HORIZON_MONTHS - 1
            starts.append(idx[i])
            end_dates.append(idx[window_end_idx])

            nom_terminal = 0.0
            real_terminal = 0.0
            for k in range(NUM_DEPOSITS):
                m = i + k * PERIOD_MONTHS
                end_excl = i + HORIZON_MONTHS  # exclusive index into return array
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
