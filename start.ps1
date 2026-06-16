# World Cup '26 dashboard launcher (Windows PowerShell).
# Starts the live updater + web server in their own windows and opens the page.
#
# Run it with:   powershell -ExecutionPolicy Bypass -File .\start.ps1
# (or just  .\start.ps1  if your execution policy already allows scripts)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- find Python -----------------------------------------------------------
$py = $null
foreach ($c in @("py", "python", "python3")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
    Write-Host "Python not found. Install it from https://www.python.org/downloads/ (tick 'Add to PATH')." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# --- resolve the API key (env var -> apikey.txt -> prompt) ------------------
$key = $env:FOOTBALL_API_KEY
if (-not $key -and (Test-Path ".\apikey.txt")) { $key = (Get-Content ".\apikey.txt" -Raw).Trim() }
if (-not $key) {
    Write-Host "Live scores need a free token from https://www.football-data.org/client/register"
    $key = Read-Host "Paste your FOOTBALL_API_KEY (or press Enter to skip live updates)"
    if ($key) { $key.Trim() | Set-Content ".\apikey.txt"; Write-Host "Saved to apikey.txt (gitignored)." -ForegroundColor Green }
}

# --- ensure predictions exist (generate once if missing) -------------------
if (-not (Test-Path ".\sim_results.js")) {
    Write-Host "Generating initial predictions (one-time, ~30-60s)..." -ForegroundColor Cyan
    & $py simulate_worldcup.py | Out-Null
}
Write-Host "Fetching latest news..." -ForegroundColor Cyan
& $py news_update.py 2>$null | Out-Null

# --- launch the web server in its own window -------------------------------
Write-Host "Starting web server on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$py -m http.server 8000" -WorkingDirectory $PSScriptRoot

# --- launch the live updater in its own window (only if we have a key) ------
if ($key) {
    Write-Host "Starting live updater (refresh every 60s) ..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:FOOTBALL_API_KEY='$key'; $py live_update.py --watch 60" -WorkingDirectory $PSScriptRoot
} else {
    Write-Host "No API key - running in snapshot mode (no live score updates)." -ForegroundColor Yellow
}

# --- open the dashboard ----------------------------------------------------
Start-Sleep -Seconds 2
Start-Process "http://localhost:8000/worldcup.html"
Write-Host ""
Write-Host "Dashboard opening at http://localhost:8000/worldcup.html" -ForegroundColor Green
Write-Host "Two helper windows are now running. Close them (or Ctrl+C) to stop." -ForegroundColor Green
