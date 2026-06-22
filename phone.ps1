# World Cup '26 dashboard — phone launcher (Windows PowerShell).
# Starts the server + live updater, then prints the URL to open on your iPhone
# (same Wi-Fi). If cloudflared is installed, also opens a public tunnel so you
# can reach it from anywhere.
#
# Run it with:  powershell -ExecutionPolicy Bypass -File .\phone.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- find Python -----------------------------------------------------------
$py = $null
foreach ($c in @("py", "python", "python3")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
    Write-Host "Python not found. Install from https://www.python.org/downloads/ (tick 'Add to PATH')." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# --- API key (env -> apikey.txt -> prompt) ---------------------------------
$key = $env:FOOTBALL_API_KEY
if (-not $key -and (Test-Path ".\apikey.txt")) { $key = (Get-Content ".\apikey.txt" -Raw).Trim() }
if (-not $key) {
    Write-Host "Live scores need a free token from https://www.football-data.org/client/register"
    $key = Read-Host "Paste your FOOTBALL_API_KEY (or press Enter to skip live updates)"
    if ($key) { $key.Trim() | Set-Content ".\apikey.txt"; Write-Host "Saved to apikey.txt (gitignored)." -ForegroundColor Green }
}
# odds key (env -> odds_key.txt -> prompt) for the FanDuel Value tab
$okey = $env:ODDS_API_KEY
if (-not $okey -and (Test-Path ".\odds_key.txt")) { $okey = (Get-Content ".\odds_key.txt" -Raw).Trim() }
if (-not $okey) { $okey = Read-Host "Paste your ODDS_API_KEY for FanDuel odds (or press Enter to skip)" }
if ($okey) { $okey = $okey.Trim(); $okey | Set-Content ".\odds_key.txt" }

# --- ensure data exists ----------------------------------------------------
if (-not (Test-Path ".\sim_results.js")) {
    Write-Host "Generating initial predictions (one-time, ~30-60s)..." -ForegroundColor Cyan
    & $py simulate_worldcup.py | Out-Null
}
Write-Host "Fetching latest news..." -ForegroundColor Cyan
& $py news_update.py 2>$null | Out-Null

# --- open the firewall for port 8000 (best effort; needs admin) ------------
try {
    if (-not (Get-NetFirewallRule -DisplayName "WC Dashboard" -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName "WC Dashboard" -Direction Inbound -LocalPort 8000 `
            -Protocol TCP -Action Allow -Profile Private,Domain -ErrorAction Stop | Out-Null
        Write-Host "Opened firewall for port 8000 (private networks)." -ForegroundColor Green
    }
} catch {
    Write-Host "Could not add the firewall rule automatically (needs Admin). If your phone can't" -ForegroundColor Yellow
    Write-Host "connect, run PowerShell as Administrator once and paste:" -ForegroundColor Yellow
    Write-Host '  New-NetFirewallRule -DisplayName "WC Dashboard" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private' -ForegroundColor Yellow
}

# --- start server (bind to all interfaces so the LAN can reach it) ----------
Write-Host "Starting web server on port 8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$py -m http.server 8000 --bind 0.0.0.0" -WorkingDirectory $PSScriptRoot

# --- start live updater -----------------------------------------------------
if ($key) {
    Write-Host "Starting live updater ..." -ForegroundColor Cyan
    $cmd = "`$env:FOOTBALL_API_KEY='$key';"
    if ($okey) { $cmd += " `$env:ODDS_API_KEY='$okey';" }
    $cmd += " $py live_update.py --watch 60"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WorkingDirectory $PSScriptRoot
} else {
    Write-Host "No API key - snapshot mode (no live score updates)." -ForegroundColor Yellow
}

# --- find this PC's LAN IP and print the iPhone URL ------------------------
$ip = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" } |
       Select-Object -First 1).IPv4Address.IPAddress
if (-not $ip) {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 |
           Where-Object { $_.IPAddress -match '^(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[0-1]))\.' } |
           Select-Object -First 1).IPAddress
}
Start-Sleep -Seconds 2
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
if ($ip) {
    Write-Host "  On your iPhone (same Wi-Fi), open Safari and go to:" -ForegroundColor Green
    Write-Host ""
    Write-Host "        http://$($ip):8000/worldcup.html" -ForegroundColor White -BackgroundColor DarkGreen
    Write-Host ""
    Write-Host "  Tip: Share -> Add to Home Screen to use it like an app." -ForegroundColor Green
} else {
    Write-Host "  Could not auto-detect your LAN IP. Run 'ipconfig', find the" -ForegroundColor Yellow
    Write-Host "  IPv4 Address (like 192.168.x.x), then open http://THAT-IP:8000/worldcup.html" -ForegroundColor Yellow
}
Write-Host "==================================================================" -ForegroundColor Green

# --- optional: public tunnel for off-network access ------------------------
if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "cloudflared detected -> opening a public tunnel for access from anywhere." -ForegroundColor Cyan
    Write-Host "Look in the new window for a https://...trycloudflare.com link, then open" -ForegroundColor Cyan
    Write-Host "that link + /worldcup.html on your phone (works on cellular too)." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cloudflared tunnel --url http://localhost:8000" -WorkingDirectory $PSScriptRoot
} else {
    Write-Host ""
    Write-Host "(Optional) For access from ANY network, install cloudflared and re-run this -" -ForegroundColor DarkGray
    Write-Host "it will auto-open a public link. https://github.com/cloudflare/cloudflared/releases" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Keep the helper windows open. Also opening on this PC..." -ForegroundColor Green
Start-Process "http://localhost:8000/worldcup.html"
