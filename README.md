# Pitch Kings — 7-a-side ⚽

A fast, arcade-style **7-a-side soccer** game that runs in any browser — no install.
Big scrolling pitch with a camera that follows the action, two teams of seven with
formations, a smart-ish AI opponent, and FIFA-style controls: you always control the
player on the ball, with passing, shooting, sprinting, and a switch-player button on
defense.

## Play it

It's a single self-contained file (`index.html`) — open it in any modern browser.

- **On your computer:** download `index.html` and double-click it, or open the hosted
  link (see below).
- **No Python or install required.**

## Controls

| Action  | Keys                         |
| ------- | ---------------------------- |
| Move    | `W A S D` or Arrow keys      |
| Sprint  | hold `Shift`                 |
| Pass    | `J`                          |
| Shoot   | `K` or `Space`               |
| Tackle (when you don't have the ball) | `K` or `Space` |
| Switch player (on defense) | `L`           |
| Pause   | `P`                          |
| Start / restart | `Enter` (or tap / click) |

On touchscreens, use the on-screen joystick (drag the left side) and the
**SPRINT / PASS / SHOOT / SWITCH** buttons.

## How it plays

- You control the highlighted player (yellow ring). When your team wins the ball,
  control **auto-switches to whoever is on the ball**.
- On defense, tap **Switch** (`L`) to take control of a different defender.
- Carry the ball by moving; **Pass** finds a teammate ahead of you; **Shoot** fires at
  the open corner of the goal. **Sprinting helps you keep the ball** — hold it too long
  and a defender will tackle it off you, so move it on.
- On defense, the **Shoot button doubles as Tackle** (`K`/`Space`): lunge at the carrier
  to win the ball. Players hold their roles, mark up, and spread across the pitch.
- A **minimap** at the top shows the whole pitch so you can see off-screen players.
- Matches are 2 minutes — most goals wins.

## Tweak it

The knobs are grouped at the top of the `<script>` in `index.html`:

- `MATCH_SECONDS` — match length
- `WORLD_W` / `WORLD_H` — pitch size
- `PLAYER_SPEED` / `SPRINT_SPEED` — movement
- `SHOOT_POWER` / `PASS_MAX` / `SHOOT_RANGE` — attacking feel
- `FORM` — the 7-player formation
- `POSSESS_DIST` — how tightly players control the ball

## Also included

`main.py` is an earlier **Pygame** desktop version (1-on-1). It needs Python 3 +
`pip install -r requirements.txt`, then `python main.py`. The browser version above
is the current, full-featured game.

## World Cup '26 predictor dashboard

A self-contained **Monte Carlo** predictor for the 2026 World Cup, just for fun.

- `simulate_worldcup.py` — pure-Python (stdlib only) simulation engine. Each match
  uses Elo-style power ratings (seeded from bookmaker title odds + FIFA/Elo +
  early results) → Poisson goals, with every goal attributed to a scorer by squad
  scoring-share. Already-played games are held to their real scores; only the
  remaining games are simulated. Runs thousands of sims per game plus thousands of
  full-tournament runs, then writes `sim_results.js`.
  Run it with `python3 simulate_worldcup.py`.
- `worldcup.html` — a dashboard (open in any browser) that reads `sim_results.js`:
  latest scores, news, per-game picks with **confidence + likely scorers**,
  qualification odds per group, and a Monte Carlo title race.
- `live_update.py` — pulls **real** match data from a football API, overlays live
  scores/minutes on the dashboard, and re-runs the simulation so predictions track
  reality.
- `odds_update.py` — pulls **real FanDuel odds** from the-odds-api.com (free key)
  and writes `odds_data.js`; the dashboard's **Value** tab compares them to the
  model to show edges/EV. Run `python3 odds_update.py` (add `--props` for
  anytime-goalscorer odds — costs one request per game). **Note:** a positive
  "edge" almost always means the model is wrong, not that FanDuel mispriced a
  game. It's a curiosity, not a betting signal.

### How to open the dashboard

**Quick look (static snapshot):** just **double-click `worldcup.html`** — it opens
in your browser and runs off the committed simulation. No install, no server.

**One-command launcher (recommended):** starts the live updater + web server and
opens the page for you.

- **Windows:** `powershell -ExecutionPolicy Bypass -File .\start.ps1`
- **macOS / Linux:** `./start.sh`  (run `chmod +x start.sh` once first)

The first run asks for your free football-data.org API token and saves it to
`apikey.txt` (gitignored) so you won't be asked again. Press Enter to skip and run
in snapshot mode. To stop, close the helper windows (Windows) or press Ctrl+C
(macOS/Linux).

**Live / real-time mode** (auto-refreshing scores + re-simulated predictions):

1. Get a free API token at <https://www.football-data.org/client/register>.
2. Make sure you're **inside this project folder** first (`cd path\to\hayden`), then
   start the updater. Pick the snippet for your shell:

   **macOS / Linux (bash/zsh):**
   ```bash
   export FOOTBALL_API_KEY=your_token
   python3 live_update.py --watch 60         # fetches + re-simulates every 60s
   ```
   **Windows PowerShell:**
   ```powershell
   $env:FOOTBALL_API_KEY = "your_token"
   python live_update.py --watch 60
   ```
   **Windows cmd.exe:**
   ```bat
   set FOOTBALL_API_KEY=your_token
   python live_update.py --watch 60
   ```
3. In a **second** terminal (also `cd`'d into this folder), serve the page so it can
   poll for updates:
   ```bash
   python3 -m http.server 8000     # Windows: python -m http.server 8000
   ```
4. Open <http://localhost:8000/worldcup.html>. It auto-refreshes every 45s, shows
   live scores, and predictions update as games finish.

> The env var only lasts for that terminal window, so set it in the same window you
> run the updater from. Run `dir` (Windows) or `ls` to confirm you can see
> `live_update.py` — if you can't, you're in the wrong folder.

### View it on your phone

Run `powershell -ExecutionPolicy Bypass -File .\phone.ps1` on the PC. It starts the
server + updater, opens the firewall for port 8000, and prints a
`http://<your-PC-IP>:8000/worldcup.html` URL — open that in Safari on an iPhone on
the **same Wi-Fi**. (Add to Home Screen for an app-like icon.) If `cloudflared` is
installed it also opens a public `trycloudflare.com` link so you can reach it from
any network.

> Why the server? Browsers block a file opened with `file://` from fetching local
> files, so auto-refresh only works over `http://`. Without the API key it simply
> keeps showing the latest snapshot.

> ⚠️ Predictions are for entertainment only — a model cannot make uncertain events
> certain. Never bet money you can't afford to lose. Help: **1-800-GAMBLER**.
