"""Reusable PDF page builders for per-scenario reports.

Page contract: each ``add_*`` helper takes a ``PdfPages`` handle, the
``ScenarioMeta``, the windows DataFrame (already scaled — terminals are in
dollars, metrics are decimal annual rates), the horizon in years, and the
page-number pair. It draws one page and ``plt.close``s the figure.

Style conventions (matching ``design.md`` § "PDF report layout"):
- Letter portrait, 8.5×11 inches.
- Title at top (centered, 15pt bold for content pages; 22pt on the cover).
- Footer at bottom: sources blurb left/center, page N / total right.
- Helvetica via matplotlib defaults; light gray accents at #555555 / #eeeeee.
- ``ScenarioMeta.metric_name`` drives all "CAGR" vs "IRR" labels.
"""
from __future__ import annotations

import textwrap
from datetime import date

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from .scenarios import ScenarioMeta

# Disable mathtext parsing so literal "$1,000" / "$100" in titles, descriptions,
# and the methodology lines don't get treated as math delimiters and rendered
# in italic. We don't use mathtext anywhere in these reports.
plt.rcParams["text.parse_math"] = False

PAGE_SIZE = (8.5, 11)
# Horizontal margin band used for titles, footers, and the cover summary axes.
# Constraining everything to [MARGIN_LEFT, MARGIN_RIGHT] keeps long scenario
# titles off the page edge.
MARGIN_LEFT = 0.10
MARGIN_RIGHT = 0.90
TITLE_CENTER = (MARGIN_LEFT + MARGIN_RIGHT) / 2
TITLE_WIDTH = MARGIN_RIGHT - MARGIN_LEFT
PAGE_FOOTER = (
    "Sources: Fama/French Research Data Factors (Ken French Data Library, Tuck) "
    "and FRED CPIAUCNS. See final page for full methodology."
)


def full_history_cagr(returns: pd.Series) -> float:
    n_months = len(returns)
    terminal = np.exp(np.log1p(returns).sum())
    return terminal ** (12 / n_months) - 1


def _format_month(ts: pd.Timestamp) -> str:
    return ts.strftime("%b %Y")


def _add_footer(fig: plt.Figure, page_num: int, total_pages: int) -> None:
    fig.text(
        TITLE_CENTER, 0.025, PAGE_FOOTER,
        ha="center", va="bottom", fontsize=7, color="#555555",
    )
    fig.text(
        MARGIN_RIGHT, 0.025, f"{page_num} / {total_pages}",
        ha="right", va="bottom", fontsize=7, color="#555555",
    )


def _add_title(fig: plt.Figure, y: float, text: str, *, fontsize: int,
               weight: str = "bold") -> None:
    """Centered title clipped to the [MARGIN_LEFT, MARGIN_RIGHT] band so long
    scenario titles cannot run to the page edge."""
    fig.text(
        TITLE_CENTER, y, text,
        ha="center", va="top",
        fontsize=fontsize, weight=weight, wrap=True,
    )


def add_cover(
    pdf: PdfPages,
    meta: ScenarioMeta,
    monthly: pd.DataFrame,
    windows: pd.DataFrame,
    horizon: int,
    page_num: int,
    total_pages: int,
) -> None:
    nom_cagr = full_history_cagr(monthly["nominal_return"])
    real_cagr = full_history_cagr(monthly["real_return"])
    nom_m = windows["nominal_metric"]
    real_m = windows["real_metric"]
    nom_mean, real_mean = nom_m.mean(), real_m.mean()
    nom_max, real_max = nom_m.max(), real_m.max()
    nom_min, real_min = nom_m.min(), real_m.min()
    nom_neg = (nom_m <= 0)
    real_neg = (real_m <= 0)
    metric = meta.metric_name

    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.93, "Rolling-window U.S. stock returns",
             ha="center", fontsize=18, weight="bold")
    fig.text(0.5, 0.895, meta.title,
             ha="center", fontsize=14, color="#333333")
    fig.text(0.5, 0.865,
             f"Monthly data, {_format_month(monthly.index.min())} – "
             f"{_format_month(monthly.index.max())} ({len(monthly):,} months)",
             ha="center", fontsize=10, color="#444444")
    fig.text(0.5, 0.845, f"Generated {date.today().isoformat()}",
             ha="center", fontsize=9, color="#777777")

    ax = fig.add_axes([0.13, 0.17, 0.74, 0.65])
    ax.axis("off")

    lines = [
        ("Full-history compound annual growth rate (market)", None, None),
        ("  Nominal", f"{nom_cagr:.2%}", "[1]"),
        ("  Real (CPI-deflated)", f"{real_cagr:.2%}", "[1][2]"),
        ("", "", ""),
        (f"Mean {horizon}-year rolling {metric}", None, None),
        ("  Nominal", f"{nom_mean:.2%}", "[3]"),
        ("  Real", f"{real_mean:.2%}", "[3]"),
        ("", "", ""),
        (f"Highest {horizon}-year rolling {metric}", None, None),
        ("  Nominal", f"{nom_max:+.2%}", "[3]"),
        ("  Real", f"{real_max:+.2%}", "[3]"),
        ("", "", ""),
        (f"Lowest {horizon}-year rolling {metric}", None, None),
        ("  Nominal", f"{nom_min:+.2%}", "[3]"),
        ("  Real", f"{real_min:+.2%}", "[3]"),
        ("", "", ""),
        (f"{horizon}-year rolling windows with {metric} ≤ 0", None, None),
        ("  Nominal",
         f"{nom_neg.mean():.2%}  ({nom_neg.sum():,} of {len(windows):,})", "[3]"),
        ("  Real",
         f"{real_neg.mean():.2%}  ({real_neg.sum():,} of {len(windows):,})", "[3]"),
        ("", "", ""),
        (f"Total {horizon}-year rolling windows", f"{len(windows):,}", "[3]"),
        ("Window labeling", "by start date", "[3]"),
        ("Total contributed per window", f"${meta.total_invested:,.0f}", None),
    ]

    y = 0.97
    for label, value, ref in lines:
        if not label and not value:
            y -= 0.018
            continue
        is_header = value is None
        ax.text(0.02, y, label,
                fontsize=11 if is_header else 10,
                weight="bold" if is_header else "normal",
                transform=ax.transAxes)
        if value:
            ax.text(0.92, y, value, fontsize=10,
                    ha="right", transform=ax.transAxes)
        if ref:
            ax.text(0.95, y, ref, fontsize=8.5, color="#666666",
                    ha="left", transform=ax.transAxes)
        y -= 0.042

    wrapped = textwrap.fill(meta.description, width=95)
    fig.text(0.13, 0.13, wrapped,
             fontsize=9.5, color="#333333", va="top")

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def add_rolling_metric_chart(
    pdf: PdfPages,
    meta: ScenarioMeta,
    windows: pd.DataFrame,
    horizon: int,
    page_num: int,
    total_pages: int,
) -> None:
    metric = meta.metric_name
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.93, f"{horizon}-year rolling {metric} by window start date",
             ha="center", fontsize=14, weight="bold")
    fig.text(0.5, 0.905,
             f"Each point is the annualized return of a {horizon}-year window "
             "beginning on that month.",
             ha="center", fontsize=9, color="#555555")

    ax = fig.add_axes([0.12, 0.55, 0.78, 0.32])
    ax.plot(windows.index, windows["nominal_metric"], label="Nominal", linewidth=1)
    ax.plot(windows.index, windows["real_metric"], label="Real",
            linewidth=1, color="C1")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_xlabel("Window start")
    ax.set_ylabel(f"Annualized return ({metric})")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    summary_ax = fig.add_axes([0.12, 0.12, 0.78, 0.35])
    summary_ax.axis("off")
    summary_ax.text(0, 1.0, "Summary statistics", fontsize=12, weight="bold",
                     transform=summary_ax.transAxes)

    def _stats(s: pd.Series) -> list[tuple[str, str]]:
        return [
            ("Mean", f"{s.mean():.2%}"),
            ("Median", f"{s.median():.2%}"),
            ("Std. dev.", f"{s.std():.2%}"),
            ("Min", f"{s.min():.2%}"),
            ("Max", f"{s.max():.2%}"),
            ("Share ≤ 0", f"{(s <= 0).mean():.2%}"),
        ]

    headers = ["", "Nominal", "Real"]
    nstats = _stats(windows["nominal_metric"])
    rstats = _stats(windows["real_metric"])
    rows = [[lab, nv, rv] for (lab, nv), (_, rv) in zip(nstats, rstats)]

    table = summary_ax.table(
        cellText=rows, colLabels=headers,
        cellLoc="center", colLoc="center",
        loc="upper center",
        bbox=[0.1, 0.15, 0.8, 0.7],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for col in range(3):
        cell = table[0, col]
        cell.set_text_props(weight="bold")
        cell.set_facecolor("#eeeeee")
    for row in range(1, len(rows) + 1):
        table[row, 0].set_text_props(weight="bold", ha="left")

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def add_distribution_page(
    pdf: PdfPages,
    meta: ScenarioMeta,
    windows: pd.DataFrame,
    horizon: int,
    page_num: int,
    total_pages: int,
) -> None:
    metric = meta.metric_name
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.93, f"Distribution of {horizon}-year rolling {metric}s",
             ha="center", fontsize=14, weight="bold")
    fig.text(0.5, 0.905,
             f"Histogram of every {horizon}-year window in the sample.",
             ha="center", fontsize=9, color="#555555")

    ax1 = fig.add_axes([0.1, 0.5, 0.38, 0.34])
    ax1.hist(windows["nominal_metric"], bins=40, edgecolor="white")
    ax1.set_title("Nominal")
    ax1.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax1.set_xlabel(f"Annualized return ({metric})")
    ax1.set_ylabel("Window count")
    ax1.axvline(0, color="black", linewidth=0.7, linestyle="--")

    ax2 = fig.add_axes([0.55, 0.5, 0.38, 0.34])
    ax2.hist(windows["real_metric"], bins=40, edgecolor="white", color="C1")
    ax2.set_title("Real")
    ax2.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax2.set_xlabel(f"Annualized return ({metric})")
    ax2.axvline(0, color="black", linewidth=0.7, linestyle="--")

    nom_neg = (windows["nominal_metric"] <= 0)
    real_neg = (windows["real_metric"] <= 0)

    txt_ax = fig.add_axes([0.12, 0.12, 0.76, 0.3])
    txt_ax.axis("off")
    txt_ax.text(0, 1.0, f"Share of windows with {metric} ≤ 0", fontsize=12,
                weight="bold", transform=txt_ax.transAxes)
    txt_ax.text(
        0, 0.82,
        f"Nominal:  {nom_neg.mean():.2%}   ({nom_neg.sum():,} of {len(windows):,} windows)",
        fontsize=11, transform=txt_ax.transAxes,
    )
    txt_ax.text(
        0, 0.7,
        f"Real:     {real_neg.mean():.2%}   ({real_neg.sum():,} of {len(windows):,} windows)",
        fontsize=11, transform=txt_ax.transAxes,
    )
    txt_ax.text(
        0, 0.5,
        f"“≤ 0” means an investor who followed this schedule over the full "
        f"{horizon}-year window would have ended at or below their total "
        "contributions, after compounding (and after inflation, for the real series).",
        fontsize=9, color="#444444", wrap=True, transform=txt_ax.transAxes,
    )
    txt_ax.text(0, 0.35, "[3]", fontsize=8, color="#666666",
                transform=txt_ax.transAxes)

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def add_best_worst_tables(
    pdf: PdfPages,
    meta: ScenarioMeta,
    windows: pd.DataFrame,
    horizon: int,
    page_num: int,
    total_pages: int,
) -> None:
    metric = meta.metric_name
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.93, f"Best and worst {horizon}-year windows",
             ha="center", fontsize=14, weight="bold")
    fig.text(0.5, 0.905,
             f"Top 5 highest and lowest annualized returns ({metric}), ranked by "
             "window-start month.",
             ha="center", fontsize=9, color="#555555")

    def _make_rows(df: pd.DataFrame, metric_col: str, term_col: str,
                   ascending: bool) -> list[list[str]]:
        picks = df.nsmallest(5, metric_col) if ascending else df.nlargest(5, metric_col)
        return [
            [
                _format_month(idx),
                _format_month(row["end_date"]),
                f"{row[metric_col]:.2%}",
                f"${row[term_col]:,.0f}",
            ]
            for idx, row in picks.iterrows()
        ]

    final_label = f"${meta.total_invested:,.0f} → "

    def _draw_table(ax, title: str, rows: list[list[str]]) -> None:
        ax.axis("off")
        ax.text(0, 1.0, title, fontsize=11, weight="bold", transform=ax.transAxes)
        headers = ["Start", "End", metric, final_label]
        table = ax.table(
            cellText=rows, colLabels=headers,
            cellLoc="center", colLoc="center",
            loc="upper center",
            bbox=[0.0, 0.05, 1.0, 0.85],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for col in range(len(headers)):
            cell = table[0, col]
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#eeeeee")

    ax = fig.add_axes([0.08, 0.66, 0.4, 0.22])
    _draw_table(ax, "Best nominal",
                _make_rows(windows, "nominal_metric", "nominal_terminal", False))

    ax = fig.add_axes([0.55, 0.66, 0.4, 0.22])
    _draw_table(ax, "Worst nominal",
                _make_rows(windows, "nominal_metric", "nominal_terminal", True))

    ax = fig.add_axes([0.08, 0.36, 0.4, 0.22])
    _draw_table(ax, "Best real",
                _make_rows(windows, "real_metric", "real_terminal", False))

    ax = fig.add_axes([0.55, 0.36, 0.4, 0.22])
    _draw_table(ax, "Worst real",
                _make_rows(windows, "real_metric", "real_terminal", True))

    fig.text(0.5, 0.28,
             f"“${meta.total_invested:,.0f} →” is the terminal value of the full "
             f"contribution schedule, held to the end of the {horizon}-year window. [4]",
             ha="center", fontsize=9, color="#444444")

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def add_terminal_chart(
    pdf: PdfPages,
    meta: ScenarioMeta,
    windows: pd.DataFrame,
    horizon: int,
    page_num: int,
    total_pages: int,
) -> None:
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.93,
             f"Terminal value of ${meta.total_invested:,.0f} after {horizon} years",
             ha="center", fontsize=14, weight="bold")
    fig.text(0.5, 0.905,
             f"Where ${meta.total_invested:,.0f} contributed under this schedule "
             "would have landed, by start month.",
             ha="center", fontsize=9, color="#555555")

    ax = fig.add_axes([0.12, 0.18, 0.78, 0.66])
    ax.plot(windows.index, windows["nominal_terminal"], label="Nominal", linewidth=1)
    ax.plot(windows.index, windows["real_terminal"], label="Real",
            linewidth=1, color="C1")
    ax.axhline(meta.total_invested, color="black", linewidth=0.5, linestyle="--",
                label=f"Break-even (${meta.total_invested:,.0f})")
    ax.set_xlabel("Window start")
    ax.set_ylabel("Terminal value")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def add_methodology_page(
    pdf: PdfPages,
    meta: ScenarioMeta,
    monthly: pd.DataFrame,
    horizon: int,
    page_num: int,
    total_pages: int,
) -> None:
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.93, "Sources and methodology",
             ha="center", fontsize=14, weight="bold")

    ax = fig.add_axes([0.12, 0.08, 0.76, 0.82])
    ax.axis("off")

    scenario_section = [
        f"[3] Rolling {horizon}-year window math — {meta.title}",
        *meta.methodology_lines,
    ]

    sections: list[tuple[str, list[str]]] = [
        ("Data sources", [
            "[1] Fama/French Research Data Factors, monthly file. Ken French Data Library,",
            "    Tuck School of Business, Dartmouth.",
            "    https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
            "    Columns used: Mkt-RF (market excess return), RF (risk-free rate).",
            "    Values are published as percent (2.50 = 2.5%) and divided by 100 on ingest.",
            "",
            "[2] U.S. CPI for All Urban Consumers, not seasonally adjusted (CPIAUCNS).",
            "    Federal Reserve Bank of St. Louis (FRED).",
            "    https://fred.stlouisfed.org/series/CPIAUCNS",
            "    The not-seasonally-adjusted series is used deliberately — the SA series",
            "    (CPIAUCSL) only begins in 1947 and would truncate 21 years of history.",
        ]),
        ("Series construction", [
            "    nominal_return = (Mkt-RF + RF) / 100  — total U.S. market return.",
            "    inflation      = CPI.pct_change()    — month-over-month CPI change.",
            "    real_return    = (1 + nominal) / (1 + inflation) − 1   (Fisher equation).",
            "    The first observation (Jul 1926) is dropped because monthly inflation",
            "    requires a prior CPI reading.",
        ]),
        (scenario_section[0], scenario_section[1:]),
        ("[4] Full-history market CAGR", [
            "    terminal = exp( Σ log(1 + r_t) ) over the full sample of monthly returns.",
            "    CAGR     = terminal ^ (12 / n_months) − 1.",
            "    Shown on the cover for context; independent of the scenario schedule.",
        ]),
        ("Reproducibility", [
            "    python -m src.ingest      # rebuild data/processed/monthly_returns.parquet",
            "    python -m src.export      # rebuild docs/data/*.json",
            "    python -m src.report      # rebuild reports/*.pdf",
            f"    Sample window: {_format_month(monthly.index.min())} – "
            f"{_format_month(monthly.index.max())}"
            f"  ({len(monthly):,} monthly observations).",
        ]),
    ]

    y = 0.98
    for heading, lines in sections:
        ax.text(0, y, heading, fontsize=11, weight="bold", transform=ax.transAxes)
        y -= 0.025
        for line in lines:
            ax.text(0, y, line, fontsize=8.5, family="monospace",
                     transform=ax.transAxes)
            y -= 0.022
        y -= 0.015

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)
