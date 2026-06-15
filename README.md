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
- `worldcup.html` — a live-style dashboard (open in any browser) that reads
  `sim_results.js`: latest scores, news, per-game picks with **confidence + likely
  scorers**, qualification odds per group, and a Monte Carlo title race.

> ⚠️ Predictions are for entertainment only — a model cannot make uncertain events
> certain. Never bet money you can't afford to lose. Help: **1-800-GAMBLER**.
