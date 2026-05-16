# U.S. Stock Returns — Rolling Window Analysis

Long-run analysis of U.S. total-market returns using free public data:

- **Ken French Data Library** — monthly value-weighted U.S. total-market returns (July 1926 onward), derived from CRSP.
- **FRED CPIAUCNS** — monthly CPI (not seasonally adjusted) for inflation-adjusting nominal returns into real returns. NSA chosen over SA so coverage extends back to 1913 and aligns with Ken French's 1926-07 start.

The Python pipeline computes rolling N-year returns and CAGRs starting at every month
in the series and exports a compact JSON file. The static site in `docs/` reads that
JSON and renders interactive charts; it is hosted on GitHub Pages directly from `docs/`.

## Setup (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the pipeline

```powershell
python -m src.ingest    # downloads raw data, writes data/processed/monthly_returns.parquet
python -m src.export    # computes rolling windows, writes docs/data/returns.json
```

## Notebook

```powershell
jupyter notebook notebooks/01_rolling_returns.ipynb
```

## Local site preview

Open `docs/index.html` directly in a browser, or serve the `docs/` folder with any
static file server. No build step.

## Layout

```
src/        Python pipeline (ingest, analysis, export)
notebooks/  Exploratory Jupyter notebooks
docs/       Static site (HTML + JS + CSS + exported JSON), served by GitHub Pages
data/       Local working data (gitignored; regenerable)
```
