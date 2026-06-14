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
  the open corner of the goal.
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
