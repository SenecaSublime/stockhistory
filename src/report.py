"""Generate a curated PDF report from the processed monthly returns parquet.

Run: `python -m src.report` (writes reports/rolling_returns.pdf).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from src.analysis import rolling_window_returns

ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = ROOT / "data" / "processed" / "monthly_returns.parquet"
REPORTS_DIR = ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "rolling_returns.pdf"

WINDOW_YEARS = 10
PAGE_SIZE = (8.5, 11)
PAGE_FOOTER = (
    "Sources: Fama/French Research Data Factors (Ken French Data Library, Tuck) "
    "and FRED CPIAUCNS. See final page for full methodology."
)


def _full_history_cagr(returns: pd.Series) -> float:
    n_months = len(returns)
    terminal = np.exp(np.log1p(returns).sum())
    return terminal ** (12 / n_months) - 1


def _add_footer(fig: plt.Figure, page_num: int, total_pages: int) -> None:
    fig.text(
        0.5, 0.025, PAGE_FOOTER,
        ha="center", va="bottom", fontsize=7, color="#555555",
    )
    fig.text(
        0.95, 0.025, f"{page_num} / {total_pages}",
        ha="right", va="bottom", fontsize=7, color="#555555",
    )


def _format_month(ts: pd.Timestamp) -> str:
    return ts.strftime("%b %Y")


def _page_cover(pdf: PdfPages, df: pd.DataFrame, nom10: pd.DataFrame, real10: pd.DataFrame,
                page_num: int, total_pages: int) -> None:
    nom_cagr = _full_history_cagr(df["nominal_return"])
    real_cagr = _full_history_cagr(df["real_return"])
    nom_neg = (nom10["cagr"] <= 0)
    real_neg = (real10["cagr"] <= 0)

    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.93, "Rolling-window U.S. stock returns",
             ha="center", fontsize=22, weight="bold")
    fig.text(0.5, 0.895,
             f"Monthly data, {_format_month(df.index.min())} – {_format_month(df.index.max())} "
             f"({len(df):,} months)",
             ha="center", fontsize=11, color="#444444")
    fig.text(0.5, 0.87, f"Generated {date.today().isoformat()}",
             ha="center", fontsize=9, color="#777777")

    ax = fig.add_axes([0.1, 0.18, 0.8, 0.62])
    ax.axis("off")

    lines = [
        ("Full-history compound annual growth rate (CAGR)", None, None),
        ("  Nominal", f"{nom_cagr:.2%}", "[1]"),
        ("  Real (CPI-deflated)", f"{real_cagr:.2%}", "[1][2]"),
        ("", "", ""),
        (f"{WINDOW_YEARS}-year rolling windows with CAGR ≤ 0", None, None),
        ("  Nominal",
         f"{nom_neg.mean():.2%}  ({nom_neg.sum():,} of {len(nom10):,})", "[3]"),
        ("  Real",
         f"{real_neg.mean():.2%}  ({real_neg.sum():,} of {len(real10):,})", "[3]"),
        ("", "", ""),
        (f"Total {WINDOW_YEARS}-year rolling windows", f"{len(nom10):,}", "[3]"),
        ("Window labeling", "by start date", "[3]"),
    ]

    y = 0.95
    for label, value, ref in lines:
        if not label and not value:
            y -= 0.04
            continue
        is_header = value is None
        ax.text(0.02, y, label,
                fontsize=13 if is_header else 11,
                weight="bold" if is_header else "normal",
                transform=ax.transAxes)
        if value:
            ax.text(0.72, y, value, fontsize=11, transform=ax.transAxes)
        if ref:
            ax.text(0.96, y, ref, fontsize=9, color="#666666",
                    ha="right", transform=ax.transAxes)
        y -= 0.07

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def _page_rolling_cagr(pdf: PdfPages, nom10: pd.DataFrame, real10: pd.DataFrame,
                        page_num: int, total_pages: int) -> None:
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.94, f"{WINDOW_YEARS}-year rolling CAGR by window start date",
             ha="center", fontsize=15, weight="bold")
    fig.text(0.5, 0.915,
             f"Each point is the annualized return of a {WINDOW_YEARS}-year window "
             "beginning on that month.",
             ha="center", fontsize=9, color="#555555")

    ax = fig.add_axes([0.1, 0.55, 0.82, 0.32])
    ax.plot(nom10.index, nom10["cagr"], label="Nominal", linewidth=1)
    ax.plot(real10.index, real10["cagr"], label="Real", linewidth=1, color="C1")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_xlabel("Window start")
    ax.set_ylabel("Annualized return")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    summary_ax = fig.add_axes([0.1, 0.12, 0.82, 0.35])
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
    rows = []
    nstats = _stats(nom10["cagr"])
    rstats = _stats(real10["cagr"])
    for (label, nval), (_, rval) in zip(nstats, rstats):
        rows.append([label, nval, rval])

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


def _page_distributions(pdf: PdfPages, nom10: pd.DataFrame, real10: pd.DataFrame,
                         page_num: int, total_pages: int) -> None:
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.94, f"Distribution of {WINDOW_YEARS}-year rolling CAGRs",
             ha="center", fontsize=15, weight="bold")
    fig.text(0.5, 0.915,
             f"Histogram of every {WINDOW_YEARS}-year window in the sample.",
             ha="center", fontsize=9, color="#555555")

    ax1 = fig.add_axes([0.08, 0.5, 0.4, 0.36])
    ax1.hist(nom10["cagr"], bins=40, edgecolor="white")
    ax1.set_title("Nominal")
    ax1.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax1.set_xlabel("Annualized return")
    ax1.set_ylabel("Window count")
    ax1.axvline(0, color="black", linewidth=0.7, linestyle="--")

    ax2 = fig.add_axes([0.55, 0.5, 0.4, 0.36])
    ax2.hist(real10["cagr"], bins=40, edgecolor="white", color="C1")
    ax2.set_title("Real")
    ax2.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax2.set_xlabel("Annualized return")
    ax2.axvline(0, color="black", linewidth=0.7, linestyle="--")

    nom_neg = (nom10["cagr"] <= 0)
    real_neg = (real10["cagr"] <= 0)

    txt_ax = fig.add_axes([0.1, 0.12, 0.8, 0.3])
    txt_ax.axis("off")
    txt_ax.text(0, 1.0, "Share of windows with CAGR ≤ 0", fontsize=12,
                weight="bold", transform=txt_ax.transAxes)
    txt_ax.text(
        0, 0.82,
        f"Nominal:  {nom_neg.mean():.2%}   ({nom_neg.sum():,} of {len(nom10):,} windows)",
        fontsize=11, transform=txt_ax.transAxes,
    )
    txt_ax.text(
        0, 0.7,
        f"Real:     {real_neg.mean():.2%}   ({real_neg.sum():,} of {len(real10):,} windows)",
        fontsize=11, transform=txt_ax.transAxes,
    )
    txt_ax.text(
        0, 0.5,
        "“≤ 0” means an investor who held the U.S. total market over the full "
        f"{WINDOW_YEARS}-year window would have ended at or below their starting "
        "balance, after compounding (and after inflation, for the real series).",
        fontsize=9, color="#444444", wrap=True, transform=txt_ax.transAxes,
    )
    txt_ax.text(
        0, 0.35,
        "[3]", fontsize=8, color="#666666", transform=txt_ax.transAxes,
    )

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def _page_best_worst(pdf: PdfPages, nom10: pd.DataFrame, real10: pd.DataFrame,
                      page_num: int, total_pages: int) -> None:
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.94, f"Best and worst {WINDOW_YEARS}-year windows",
             ha="center", fontsize=15, weight="bold")
    fig.text(0.5, 0.915,
             "Top 5 highest and lowest annualized returns, ranked by window-start month.",
             ha="center", fontsize=9, color="#555555")

    def _make_rows(df: pd.DataFrame, ascending: bool) -> list[list[str]]:
        picks = df.nsmallest(5, "cagr") if ascending else df.nlargest(5, "cagr")
        return [
            [
                _format_month(idx),
                _format_month(row["end_date"]),
                f"{row['cagr']:.2%}",
                f"${row['terminal_value'] * 1000:,.0f}",
            ]
            for idx, row in picks.iterrows()
        ]

    def _draw_table(ax, title: str, rows: list[list[str]]) -> None:
        ax.axis("off")
        ax.text(0, 1.0, title, fontsize=11, weight="bold",
                transform=ax.transAxes)
        headers = ["Start", "End", "CAGR", "$1k → "]
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
    _draw_table(ax, "Best nominal", _make_rows(nom10, ascending=False))

    ax = fig.add_axes([0.55, 0.66, 0.4, 0.22])
    _draw_table(ax, "Worst nominal", _make_rows(nom10, ascending=True))

    ax = fig.add_axes([0.08, 0.36, 0.4, 0.22])
    _draw_table(ax, "Best real", _make_rows(real10, ascending=False))

    ax = fig.add_axes([0.55, 0.36, 0.4, 0.22])
    _draw_table(ax, "Worst real", _make_rows(real10, ascending=True))

    fig.text(0.5, 0.28,
             "“$1k →” is the terminal value of $1,000 invested at the window start, "
             f"held for the full {WINDOW_YEARS} years. [4]",
             ha="center", fontsize=9, color="#444444")

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def _page_terminal_value(pdf: PdfPages, nom10: pd.DataFrame, real10: pd.DataFrame,
                          page_num: int, total_pages: int) -> None:
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.94,
             f"Terminal value of $1,000 after {WINDOW_YEARS} years",
             ha="center", fontsize=15, weight="bold")
    fig.text(0.5, 0.915,
             "Where $1,000 invested in the U.S. total market would have landed, "
             "by start month.",
             ha="center", fontsize=9, color="#555555")

    ax = fig.add_axes([0.1, 0.18, 0.82, 0.68])
    ax.plot(nom10.index, nom10["terminal_value"] * 1000, label="Nominal", linewidth=1)
    ax.plot(real10.index, real10["terminal_value"] * 1000, label="Real",
            linewidth=1, color="C1")
    ax.axhline(1000, color="black", linewidth=0.5, linestyle="--",
                label="Break-even ($1,000)")
    ax.set_xlabel("Window start")
    ax.set_ylabel("Terminal value")
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def _page_methodology(pdf: PdfPages, df: pd.DataFrame,
                       page_num: int, total_pages: int) -> None:
    fig = plt.figure(figsize=PAGE_SIZE)
    fig.text(0.5, 0.94, "Sources and methodology",
             ha="center", fontsize=15, weight="bold")

    ax = fig.add_axes([0.08, 0.08, 0.84, 0.82])
    ax.axis("off")

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
        (f"[3] Rolling {WINDOW_YEARS}-year window math", [
            f"    For each month t, compound the next {12 * WINDOW_YEARS} monthly returns:",
            "      terminal_value(t) = exp( Σ log(1 + r_i) )   for i in [t, t+N−1]",
            "      CAGR(t)           = terminal_value(t) ^ (1 / years) − 1",
            "    Log-returns are summed (not products chained) for numerical stability over",
            "    long horizons. Each window is labeled by its START month, not its end.",
            "    Windows lacking a full N months are dropped from the tail.",
        ]),
        ("[4] Full-history CAGR", [
            "    terminal = exp( Σ log(1 + r_t) ) over the full sample.",
            "    CAGR     = terminal ^ (12 / n_months) − 1.",
        ]),
        ("Reproducibility", [
            "    python -m src.ingest      # rebuild data/processed/monthly_returns.parquet",
            "    python -m src.report      # rebuild reports/rolling_returns.pdf",
            f"    Sample window: {_format_month(df.index.min())} – {_format_month(df.index.max())}"
            f"  ({len(df):,} monthly observations).",
        ]),
    ]

    y = 0.98
    for heading, lines in sections:
        ax.text(0, y, heading, fontsize=11, weight="bold",
                 transform=ax.transAxes)
        y -= 0.025
        for line in lines:
            ax.text(0, y, line, fontsize=8.5, family="monospace",
                     transform=ax.transAxes)
            y -= 0.022
        y -= 0.015

    _add_footer(fig, page_num, total_pages)
    pdf.savefig(fig)
    plt.close(fig)


def build(output_path: Path = OUTPUT_PATH) -> Path:
    if not PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"{PARQUET_PATH} not found. Run `python -m src.ingest` first."
        )

    df = (
        pd.read_parquet(PARQUET_PATH)
        .set_index("date")
        .sort_index()
    )
    nom10 = rolling_window_returns(df["nominal_return"], years=WINDOW_YEARS)
    real10 = rolling_window_returns(df["real_return"], years=WINDOW_YEARS)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 6
    with PdfPages(output_path) as pdf:
        _page_cover(pdf, df, nom10, real10, 1, total)
        _page_rolling_cagr(pdf, nom10, real10, 2, total)
        _page_distributions(pdf, nom10, real10, 3, total)
        _page_best_worst(pdf, nom10, real10, 4, total)
        _page_terminal_value(pdf, nom10, real10, 5, total)
        _page_methodology(pdf, df, 6, total)

        pdf.infodict()["Title"] = "Rolling-window U.S. stock returns"
        pdf.infodict()["Author"] = "stockhistory"
        pdf.infodict()["Subject"] = (
            f"{WINDOW_YEARS}-year rolling CAGR and distribution of U.S. total-market returns"
        )

    print(f"Wrote {output_path}")
    return output_path


if __name__ == "__main__":
    build()
