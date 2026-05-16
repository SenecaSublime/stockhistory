# Serve docs/ on http://localhost:<port>/ and open the default browser.
#
# Reason this exists: opening docs/scenarios/*.html via file:// triggers a
# Chrome CORS block on the fetch() call in app.js (it refuses to load the
# JSON from a file:// origin). Running a tiny local server avoids that.
#
# Usage:
#     .\scripts\serve.ps1            # port 8000
#     .\scripts\serve.ps1 -Port 8080
# Stop with Ctrl+C.

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$docs = Join-Path $root "docs"

if (-not (Test-Path $docs)) {
    Write-Error "docs/ folder not found at $docs"
    exit 1
}

# Prefer the project venv if it exists; fall back to whatever 'python' resolves to.
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$url = "http://localhost:$Port/"

Write-Host "Serving $docs on $url"
Write-Host "Press Ctrl+C to stop."

Start-Process $url
& $python -m http.server $Port --directory $docs --bind 127.0.0.1
