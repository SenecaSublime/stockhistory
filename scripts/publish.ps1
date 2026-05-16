# Refresh every artifact the live site needs, then show what changed in docs/.
#
# Runs the offline pipeline in order: optional source re-download, scenario
# JSON export, scenario PDF build. Each scenario's JSON lives at
# docs/data/<slug>.json and its PDF at docs/reports/<slug>.pdf — both are
# committed and served by GitHub Pages.
#
# Usage:
#     .\scripts\publish.ps1           # uses cached raw data in data/raw/
#     .\scripts\publish.ps1 -Refresh  # re-download Ken French + FRED first
#
# This script does NOT commit or push — review the diff with `git status` /
# `git diff -- docs/` and commit when you're ready.

param(
    [switch]$Refresh
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

Push-Location $root
try {
    if ($Refresh) {
        Write-Host "==> python -m src.ingest --refresh"
        & $python -m src.ingest --refresh
    } else {
        # The parquet must exist for export and report; build it if missing.
        $parquet = Join-Path $root "data\processed\monthly_returns.parquet"
        if (-not (Test-Path $parquet)) {
            Write-Host "==> python -m src.ingest  (parquet missing)"
            & $python -m src.ingest
        }
    }

    Write-Host "==> python -m src.export"
    & $python -m src.export

    Write-Host "==> python -m src.report"
    & $python -m src.report

    Write-Host ""
    Write-Host "Changes in docs/:"
    & git status --short -- docs/

    Write-Host ""
    Write-Host "When ready to publish:"
    Write-Host "    git add docs/"
    Write-Host "    git commit -m 'data: refresh through <month>'"
    Write-Host "    git push"
}
finally {
    Pop-Location
}
