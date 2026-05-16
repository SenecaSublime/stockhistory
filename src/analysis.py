"""Rolling-window return calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_window_returns(returns: pd.Series, years: int = 10) -> pd.DataFrame:
    """For each month t, compute the terminal value of $1 invested for
    `years` years starting at t, plus the annualized CAGR.

    Parameters
    ----------
    returns : pd.Series
        Monthly returns in decimal form (0.025 = 2.5%), with a DatetimeIndex.
    years : int
        Window length in years.

    Returns
    -------
    pd.DataFrame
        Indexed by window *start* date with columns:
        end_date, terminal_value, cagr.
        Only rows with a complete window are kept (incomplete tails dropped).
    """
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise ValueError("returns must have a DatetimeIndex")

    months = 12 * years
    log_r = np.log1p(returns)

    # rolling(N).sum() labels at the END of each window. To label by the
    # START of the window, shift the result back by (N - 1) positions.
    rolling_log_sum = log_r.rolling(months).sum().shift(-(months - 1))
    terminal = np.exp(rolling_log_sum)
    cagr = terminal ** (1.0 / years) - 1.0

    end_date = pd.Series(returns.index, index=returns.index).shift(-(months - 1))

    out = pd.DataFrame({
        "end_date": end_date,
        "terminal_value": terminal,
        "cagr": cagr,
    })
    return out.dropna()
