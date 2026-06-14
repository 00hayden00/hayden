# Pitch Kings ⚽

A fast, arcade-style 1-on-1 soccer game built with [Pygame](https://www.pygame.org/).
Top-down pitch, a bouncy ball with simple physics, goal celebrations, and a match
clock. Play against a built-in AI or grab a friend for local 2-player.

![mode: arcade soccer](https://img.shields.io/badge/mode-arcade%20soccer-yellow)

## Run it

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. install the one dependency
pip install -r requirements.txt

# 3. kick off
python main.py
```

## How to play

Bump into the ball to kick it. Hold **sprint** while you make contact to smash
it harder. Knock the ball into your opponent's goal (the netted recess) before
the clock runs out. Most goals wins.

### Controls

| Action | Blue (Player 1) | Red (Player 2) |
| ------ | --------------- | -------------- |
| Move   | `W` `A` `S` `D` | Arrow keys     |
| Sprint | `Left Shift`    | `Right Shift`  |

| Key       | Menu / Game        |
| --------- | ------------------ |
| `1` / `2` | Choose 1P (vs AI) / 2P |
| `Enter`   | Start / restart    |
| `P`       | Pause              |
| `Esc`     | Quit               |

In 1-player mode the red side is controlled by the AI.

## Tweak it

All the knobs live near the top of `main.py`:

- `MATCH_SECONDS` — match length
- `PLAYER_SPEED` / `SPRINT_SPEED` — how fast players move
- `KICK_POWER` / `SPRINT_KICK_BONUS` — how hard the ball flies
- `BALL_FRICTION` / `WALL_BOUNCE` — ball feel
- `GOAL_WIDTH` — how big the goals are

Have fun, and feel free to make it your own.
