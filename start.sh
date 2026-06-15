#!/usr/bin/env bash
# World Cup '26 dashboard launcher (macOS / Linux).
# Starts the live updater + web server, then opens the page.
#   chmod +x start.sh   (first time only)
#   ./start.sh
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then echo "Python not found. Install Python 3 first."; exit 1; fi

# resolve API key: env var -> apikey.txt -> prompt
KEY="${FOOTBALL_API_KEY:-}"
[ -z "$KEY" ] && [ -f apikey.txt ] && KEY=$(tr -d '\r\n' < apikey.txt)
if [ -z "$KEY" ]; then
  echo "Live scores need a free token from https://www.football-data.org/client/register"
  read -r -p "Paste your FOOTBALL_API_KEY (or press Enter to skip live updates): " KEY
  [ -n "$KEY" ] && echo "$KEY" > apikey.txt && echo "Saved to apikey.txt (gitignored)."
fi

# ensure predictions exist (generate once if missing)
if [ ! -f sim_results.js ]; then
  echo "Generating initial predictions (one-time, ~30-60s)..."
  "$PY" simulate_worldcup.py >/dev/null
fi

pids=()
cleanup() { echo; echo "Stopping..."; for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if [ -n "$KEY" ]; then
  echo "Starting live updater (refresh every 60s)..."
  FOOTBALL_API_KEY="$KEY" "$PY" live_update.py --watch 60 &
  pids+=($!)
else
  echo "No API key - snapshot mode (no live score updates)."
fi

echo "Starting web server on http://localhost:8000 ..."
"$PY" -m http.server 8000 &
pids+=($!)

sleep 2
URL="http://localhost:8000/worldcup.html"
( command -v open >/dev/null && open "$URL" ) || ( command -v xdg-open >/dev/null && xdg-open "$URL" ) || echo "Open $URL in your browser."

echo "Running. Press Ctrl+C to stop."
wait
