"""Scenario protocol + shared helpers.

A scenario describes a deposit schedule and a per-window computation that
produces terminal value (nominal & real) and a return metric (CAGR for
lump-sum, IRR for DCA) over rolling windows of monthly returns.

The protocol uses a single ``nominal_metric`` / ``real_metric`` field name
rather than scenario-specific ``cagr`` / ``irr`` columns so that downstream
consumers (export.py, report_template.py, docs/app.js) stay generic.
Each scenario's ``meta.metric_name`` labels what the metric is in human terms.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class ScenarioMeta:
    slug: str                          # filesystem/URL slug: "lump_sum", "annual_dca"
    title: str                         # display title: "$1,000 lump sum"
    short_title: str                   # nav label: "Lump sum"
    description: str                   # one-paragraph blurb for landing page + scenario page
    total_invested: float              # total dollars contributed across the window
    metric_name: str                   # "CAGR" or "IRR" — what the metric column means
    horizons: tuple[int, ...] = field(default=(5, 10, 15, 20))
    # Lines used in section [3] of the PDF methodology page. Each scenario
    # explains its own deposit schedule and metric definition here.
    methodology_lines: tuple[str, ...] = field(default=())


class Scenario(Protocol):
    meta: ScenarioMeta

    def compute_windows(self, monthly: pd.DataFrame, horizon: int) -> pd.DataFrame:
        """Return a DataFrame indexed by window-start date with columns:
        ``end_date``, ``nominal_terminal``, ``real_terminal``,
        ``nominal_metric``, ``real_metric``. Terminal values are in dollars
        (not per-$1 multipliers); metrics are annualized decimal rates.
        """
        ...


def solve_annual_irr(
    amounts: list[float],
    years_to_end: list[float],
    terminal: float,
    *,
    lo: float = -0.99,
    hi: float = 10.0,
    tol: float = 1e-10,
    max_iter: int = 100,
) -> float:
    """Find the annual rate R such that
    ``sum(amount_i * (1 + R) ** years_to_end_i) == terminal``.

    Bisection over ``[lo, hi]``. Returns NaN if the bracket doesn't contain a
    sign change. Kept here so multiple DCA-style scenarios can reuse it
    without adding a scipy dependency.
    """
    def f(r: float) -> float:
        return sum(a * (1.0 + r) ** t for a, t in zip(amounts, years_to_end)) - terminal

    f_lo, f_hi = f(lo), f(hi)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if f_lo * f_hi > 0:
        return float("nan")

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if abs(f_mid) < tol or (hi - lo) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)
