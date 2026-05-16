"""Fetch and clean U.S. total-market returns + CPI, write to parquet."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

KEN_FRENCH_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_CSV.zip"
)
FRED_CPI_SERIES = "CPIAUCNS"  # not seasonally adjusted; history back to 1913
FRED_CPI_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={FRED_CPI_SERIES}"


def _download(url: str, dest: Path, refresh: bool = False) -> bytes:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not refresh:
        return dest.read_bytes()
    resp = requests.get(url, timeout=60, headers={"User-Agent": "stockhistory/0.1"})
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return resp.content


def fetch_ken_french(refresh: bool = False) -> pd.DataFrame:
    """Monthly U.S. total-market return from the Fama/French 3-Factors file.

    Returns a DataFrame with columns date (month-end), mkt_rf, rf, mkt_total.
    All return columns are in decimal (e.g., 0.025 = 2.5%), already divided
    by 100 from the source's percent format.
    """
    raw_path = RAW_DIR / "ff_factors.zip"
    blob = _download(KEN_FRENCH_URL, raw_path, refresh=refresh)

    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        csv_name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(csv_name).decode("latin-1")

    lines = text.splitlines()
    # The monthly block begins at a header line starting with ",Mkt-RF"
    # and ends at the first blank line OR the " Annual Factors" marker.
    header_idx = next(
        i for i, line in enumerate(lines) if line.strip().startswith(",Mkt-RF")
    )
    end_idx = next(
        i for i in range(header_idx + 1, len(lines))
        if not lines[i].strip() or "Annual" in lines[i]
    )
    monthly_text = "\n".join(lines[header_idx:end_idx])

    df = pd.read_csv(io.StringIO(monthly_text))
    df = df.rename(columns={df.columns[0]: "yyyymm"})
    df["yyyymm"] = df["yyyymm"].astype(int)
    df = df[df["yyyymm"] >= 192607].copy()

    df["date"] = pd.to_datetime(df["yyyymm"].astype(str), format="%Y%m") \
        + pd.offsets.MonthEnd(0)
    df["mkt_rf"] = df["Mkt-RF"].astype(float) / 100.0
    df["rf"] = df["RF"].astype(float) / 100.0
    df["mkt_total"] = df["mkt_rf"] + df["rf"]

    return df[["date", "mkt_rf", "rf", "mkt_total"]].sort_values("date").reset_index(drop=True)


def fetch_fred_cpi(refresh: bool = False) -> pd.DataFrame:
    """Monthly CPI-U (CPIAUCSL) from FRED. Returns date (month-end) + cpi."""
    raw_path = RAW_DIR / "cpi.csv"
    blob = _download(FRED_CPI_URL, raw_path, refresh=refresh)

    df = pd.read_csv(io.BytesIO(blob))
    # FRED has shipped the date column as either DATE or observation_date over time.
    date_col = df.columns[0]
    cpi_col = next(c for c in df.columns[1:] if c.upper() == FRED_CPI_SERIES.upper())

    df = df.rename(columns={date_col: "date", cpi_col: "cpi"})
    df["date"] = pd.to_datetime(df["date"]) + pd.offsets.MonthEnd(0)
    df["cpi"] = pd.to_numeric(df["cpi"], errors="coerce")
    return df[["date", "cpi"]].dropna().sort_values("date").reset_index(drop=True)


def build(refresh: bool = False) -> Path:
    """Build the merged monthly returns parquet. Returns the output path."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    ff = fetch_ken_french(refresh=refresh)
    cpi = fetch_fred_cpi(refresh=refresh)

    df = ff.merge(cpi, on="date", how="inner").sort_values("date").reset_index(drop=True)
    df["inflation"] = df["cpi"].pct_change()
    df["nominal_return"] = df["mkt_total"]
    df["real_return"] = (1.0 + df["nominal_return"]) / (1.0 + df["inflation"]) - 1.0

    # The first row has NaN inflation (no prior CPI); drop it so downstream math is clean.
    df = df.dropna(subset=["inflation"]).reset_index(drop=True)

    out_path = PROCESSED_DIR / "monthly_returns.parquet"
    df[["date", "nominal_return", "real_return", "rf", "cpi", "inflation"]] \
        .to_parquet(out_path, index=False)

    span = f"{df['date'].min().date()} to {df['date'].max().date()}"
    print(f"Wrote {len(df):,} rows ({span}) to {out_path}")
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-download raw data")
    args = parser.parse_args()
    build(refresh=args.refresh)
