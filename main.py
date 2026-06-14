"""
Pitch Kings — a fast, arcade-style soccer game built with Pygame.

Top-down 1-on-1 soccer. Charge into the ball to kick it, smash it past the
keeper-less goal, and outscore your opponent before the clock runs out.

Controls:
    Player 1 (blue):  WASD to move,  Left Shift to sprint
    Player 2 (red):   Arrow keys to move,  Right Shift to sprint
                      (in 1-player mode the red side is the AI)

    1 / 2   - choose 1-player (vs AI) or 2-player on the menu
    Enter   - start / restart
    P       - pause
    Esc     - quit

Bumping the ball kicks it; sprinting into it kicks it harder.
"""

import math
import random
import sys

import pygame

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 900, 600
FPS = 60

# Pitch layout
MARGIN = 40                       # border around the playing field
GOAL_DEPTH = 28                   # how far the goal recess sits behind the line
GOAL_WIDTH = 200                  # vertical size of each goal mouth

MATCH_SECONDS = 90                # length of a match

# Colors
GRASS_DARK = (34, 120, 52)
GRASS_LIGHT = (40, 138, 60)
LINE = (235, 235, 235)
BLUE = (60, 130, 240)
BLUE_DARK = (30, 80, 180)
RED = (235, 70, 70)
RED_DARK = (170, 35, 35)
WHITE = (245, 245, 245)
BLACK = (15, 18, 22)
SHADOW = (0, 0, 0, 70)
YELLOW = (255, 220, 80)
NET = (210, 210, 210)

# Physics
PLAYER_SPEED = 3.6
SPRINT_SPEED = 5.6
PLAYER_RADIUS = 18
BALL_RADIUS = 12
BALL_FRICTION = 0.985
WALL_BOUNCE = 0.7
KICK_POWER = 7.5
SPRINT_KICK_BONUS = 4.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Field geometry helpers
# ---------------------------------------------------------------------------
FIELD = pygame.Rect(MARGIN, MARGIN, WIDTH - 2 * MARGIN, HEIGHT - 2 * MARGIN)
GOAL_TOP = HEIGHT // 2 - GOAL_WIDTH // 2
GOAL_BOTTOM = HEIGHT // 2 + GOAL_WIDTH // 2


# ---------------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------------
class Player:
    def __init__(self, x, y, color, dark, controls, name):
        self.start = (x, y)
        self.x = x
        self.y = y
        self.color = color
        self.dark = dark
        self.controls = controls  # dict of pygame keys, or None for AI
        self.name = name
        self.facing = 1 if color == BLUE else -1

    @property
    def pos(self):
        return pygame.Vector2(self.x, self.y)

    def reset(self):
        self.x, self.y = self.start

    def move(self, dx, dy, sprint):
        if dx or dy:
            length = math.hypot(dx, dy)
            dx, dy = dx / length, dy / length
            self.facing = 1 if dx >= 0 else -1
        speed = SPRINT_SPEED if sprint else PLAYER_SPEED
        self.x += dx * speed
        self.y += dy * speed
        self.x = clamp(self.x, FIELD.left + PLAYER_RADIUS, FIELD.right - PLAYER_RADIUS)
        self.y = clamp(self.y, FIELD.top + PLAYER_RADIUS, FIELD.bottom - PLAYER_RADIUS)

    def draw(self, surface):
        # Shadow
        shadow = pygame.Surface((PLAYER_RADIUS * 2 + 6, PLAYER_RADIUS + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, SHADOW, shadow.get_rect())
        surface.blit(shadow, (self.x - PLAYER_RADIUS - 3, self.y + PLAYER_RADIUS - 6))
        # Body
        pygame.draw.circle(surface, self.dark, (int(self.x), int(self.y)), PLAYER_RADIUS + 2)
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), PLAYER_RADIUS)
        # Little direction marker (which way they're facing).
        eye_x = self.x + self.facing * (PLAYER_RADIUS - 6)
        pygame.draw.circle(surface, WHITE, (int(eye_x), int(self.y)), 4)


class Ball:
    def __init__(self):
        self.x = WIDTH / 2
        self.y = HEIGHT / 2
        self.vx = 0.0
        self.vy = 0.0
        self.spin = 0.0

    @property
    def pos(self):
        return pygame.Vector2(self.x, self.y)

    def reset(self, direction=0):
        self.x = WIDTH / 2
        self.y = HEIGHT / 2
        self.vx = direction * 2.0
        self.vy = 0.0
        self.spin = 0.0

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= BALL_FRICTION
        self.vy *= BALL_FRICTION
        self.spin += math.hypot(self.vx, self.vy) * 0.1
        if abs(self.vx) < 0.02:
            self.vx = 0.0
        if abs(self.vy) < 0.02:
            self.vy = 0.0

    def bounce_walls(self):
        # Top / bottom walls.
        if self.y - BALL_RADIUS < FIELD.top:
            self.y = FIELD.top + BALL_RADIUS
            self.vy = -self.vy * WALL_BOUNCE
        elif self.y + BALL_RADIUS > FIELD.bottom:
            self.y = FIELD.bottom - BALL_RADIUS
            self.vy = -self.vy * WALL_BOUNCE

        in_goal_mouth = GOAL_TOP < self.y < GOAL_BOTTOM
        # Left / right walls — but let the ball through inside the goal mouth.
        if self.x - BALL_RADIUS < FIELD.left and not in_goal_mouth:
            self.x = FIELD.left + BALL_RADIUS
            self.vx = -self.vx * WALL_BOUNCE
        elif self.x + BALL_RADIUS > FIELD.right and not in_goal_mouth:
            self.x = FIELD.right - BALL_RADIUS
            self.vx = -self.vx * WALL_BOUNCE

    def draw(self, surface):
        # Shadow
        shadow = pygame.Surface((BALL_RADIUS * 2 + 4, BALL_RADIUS + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, SHADOW, shadow.get_rect())
        surface.blit(shadow, (self.x - BALL_RADIUS - 2, self.y + BALL_RADIUS - 5))
        # Ball body
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), BALL_RADIUS)
        pygame.draw.circle(surface, BLACK, (int(self.x), int(self.y)), BALL_RADIUS, 2)
        # Spinning pentagon-ish marks so motion is visible.
        for i in range(5):
            angle = self.spin + i * math.tau / 5
            px = self.x + math.cos(angle) * BALL_RADIUS * 0.5
            py = self.y + math.sin(angle) * BALL_RADIUS * 0.5
            pygame.draw.circle(surface, BLACK, (int(px), int(py)), 2)


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------
MENU, PLAYING, PAUSED, GOAL, FULLTIME = "menu", "playing", "paused", "goal", "fulltime"


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Pitch Kings")
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("arialblack,arial", 72, bold=True)
        self.font_mid = pygame.font.SysFont("arialblack,arial", 36, bold=True)
        self.font_small = pygame.font.SysFont("consolas,arial", 22)
        self.two_player = False
        self.state = MENU
        self.build_grass()
        self.setup_match()

    def build_grass(self):
        """Pre-render the striped pitch once."""
        self.pitch = pygame.Surface((WIDTH, HEIGHT))
        self.pitch.fill(GRASS_DARK)
        stripes = 10
        sw = FIELD.width / stripes
        for i in range(stripes):
            if i % 2 == 0:
                rect = pygame.Rect(FIELD.left + i * sw, FIELD.top, sw + 1, FIELD.height)
                pygame.draw.rect(self.pitch, GRASS_LIGHT, rect)
        # Field markings
        pygame.draw.rect(self.pitch, LINE, FIELD, 3)
        pygame.draw.line(self.pitch, LINE, (WIDTH // 2, FIELD.top), (WIDTH // 2, FIELD.bottom), 3)
        pygame.draw.circle(self.pitch, LINE, (WIDTH // 2, HEIGHT // 2), 70, 3)
        pygame.draw.circle(self.pitch, LINE, (WIDTH // 2, HEIGHT // 2), 6)
        # Penalty boxes
        box_w, box_h = 90, 260
        pygame.draw.rect(self.pitch, LINE,
                         (FIELD.left, HEIGHT // 2 - box_h // 2, box_w, box_h), 3)
        pygame.draw.rect(self.pitch, LINE,
                         (FIELD.right - box_w, HEIGHT // 2 - box_h // 2, box_w, box_h), 3)

    def setup_match(self):
        self.left_player = Player(WIDTH * 0.28, HEIGHT / 2, BLUE, BLUE_DARK,
                                  {"up": pygame.K_w, "down": pygame.K_s,
                                   "left": pygame.K_a, "right": pygame.K_d,
                                   "sprint": pygame.K_LSHIFT}, "BLUE")
        self.right_player = Player(WIDTH * 0.72, HEIGHT / 2, RED, RED_DARK,
                                   {"up": pygame.K_UP, "down": pygame.K_DOWN,
                                    "left": pygame.K_LEFT, "right": pygame.K_RIGHT,
                                    "sprint": pygame.K_RSHIFT}, "RED")
        self.ball = Ball()
        self.score = [0, 0]   # [left, right]
        self.time_left = MATCH_SECONDS
        self.last_tick = pygame.time.get_ticks()
        self.state_timer = 0
        self.goal_text = ""
        self.particles = []

    # -- input ------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit()
                if event.key == pygame.K_1 and self.state == MENU:
                    self.two_player = False
                if event.key == pygame.K_2 and self.state == MENU:
                    self.two_player = True
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.state in (MENU, FULLTIME):
                        self.setup_match()
                        self.state = PLAYING
                        self.last_tick = pygame.time.get_ticks()
                if event.key == pygame.K_p and self.state in (PLAYING, PAUSED):
                    self.state = PAUSED if self.state == PLAYING else PLAYING

    def read_input(self, player):
        keys = pygame.key.get_pressed()
        c = player.controls
        dx = keys[c["right"]] - keys[c["left"]]
        dy = keys[c["down"]] - keys[c["up"]]
        sprint = keys[c["sprint"]]
        return dx, dy, sprint

    def ai_input(self, player):
        """Simple but lively AI for the red side."""
        ball = self.ball
        # Defend if the ball is on the AI's half and moving toward goal, else attack.
        own_goal = pygame.Vector2(FIELD.right, HEIGHT / 2)
        target = ball.pos

        # Aim to get on the far side of the ball so a bump sends it left.
        approach = pygame.Vector2(ball.x + BALL_RADIUS + PLAYER_RADIUS, ball.y)
        if player.x < ball.x:
            # Ball is to the right of the AI — circle around it.
            target = pygame.Vector2(ball.x + 40, ball.y + (30 if player.y < ball.y else -30))
        else:
            target = approach

        # Stay goal-side if ball is deep in AI territory.
        if ball.x > WIDTH * 0.7 and ball.vx > 0:
            target = pygame.Vector2((ball.x + own_goal.x) / 2, ball.y)

        diff = target - player.pos
        dx = 0 if abs(diff.x) < 4 else (1 if diff.x > 0 else -1)
        dy = 0 if abs(diff.y) < 4 else (1 if diff.y > 0 else -1)
        sprint = player.pos.distance_to(ball.pos) < 90
        return dx, dy, sprint

    # -- simulation -------------------------------------------------------
    def update(self):
        now = pygame.time.get_ticks()

        if self.state == PLAYING:
            # Clock
            if now - self.last_tick >= 1000:
                self.time_left -= 1
                self.last_tick = now
                if self.time_left <= 0:
                    self.time_left = 0
                    self.state = FULLTIME

            # Movement
            self.left_player.move(*self.read_input(self.left_player))
            if self.two_player:
                self.right_player.move(*self.read_input(self.right_player))
            else:
                self.right_player.move(*self.ai_input(self.right_player))

            self.ball.update()
            self.ball.bounce_walls()
            self.resolve_kick(self.left_player)
            self.resolve_kick(self.right_player)
            self.check_goal()

        elif self.state == GOAL:
            self.ball.update()
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.kickoff()

        # Particles always animate.
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.15
            p[4] -= 1
        self.particles = [p for p in self.particles if p[4] > 0]

    def resolve_kick(self, player):
        ball = self.ball
        diff = ball.pos - player.pos
        dist = diff.length()
        min_dist = PLAYER_RADIUS + BALL_RADIUS
        if dist < min_dist and dist > 0:
            normal = diff / dist
            # Push the ball out so they don't overlap.
            ball.x = player.x + normal.x * min_dist
            ball.y = player.y + normal.y * min_dist
            # Kick: base power plus the player's current motion.
            keys = pygame.key.get_pressed()
            sprinting = keys[player.controls["sprint"]]
            power = KICK_POWER + (SPRINT_KICK_BONUS if sprinting else 0)
            ball.vx = normal.x * power
            ball.vy = normal.y * power

    def check_goal(self):
        ball = self.ball
        in_mouth = GOAL_TOP < ball.y < GOAL_BOTTOM
        if not in_mouth:
            return
        if ball.x - BALL_RADIUS < FIELD.left:
            self.score[1] += 1
            self.score_goal("RED")
        elif ball.x + BALL_RADIUS > FIELD.right:
            self.score[0] += 1
            self.score_goal("BLUE")

    def score_goal(self, scorer):
        self.goal_text = f"{scorer} SCORES!"
        self.state = GOAL
        self.state_timer = 90  # ~1.5s celebration
        color = BLUE if scorer == "BLUE" else RED
        for _ in range(60):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(2, 8)
            self.particles.append([
                self.ball.x, self.ball.y,
                math.cos(angle) * speed, math.sin(angle) * speed - 3,
                random.randint(25, 50), color,
            ])

    def kickoff(self):
        self.left_player.reset()
        self.right_player.reset()
        # Ball goes toward whoever just conceded.
        self.ball.reset(direction=0)
        self.state = PLAYING
        self.last_tick = pygame.time.get_ticks()

    # -- rendering --------------------------------------------------------
    def draw(self):
        self.screen.blit(self.pitch, (0, 0))
        self.draw_goals()

        if self.state == MENU:
            self.draw_menu()
            pygame.display.flip()
            return

        for p in self.particles:
            pygame.draw.circle(self.screen, p[5], (int(p[0]), int(p[1])), max(1, p[4] // 10))

        self.ball.draw(self.screen)
        self.left_player.draw(self.screen)
        self.right_player.draw(self.screen)
        self.draw_hud()

        if self.state == PAUSED:
            self.banner("PAUSED", "Press P to resume")
        elif self.state == GOAL:
            self.banner(self.goal_text, "")
        elif self.state == FULLTIME:
            self.draw_fulltime()

        pygame.display.flip()

    def draw_goals(self):
        # Net pattern on each goal recess.
        left_goal = pygame.Rect(FIELD.left - GOAL_DEPTH, GOAL_TOP, GOAL_DEPTH, GOAL_WIDTH)
        right_goal = pygame.Rect(FIELD.right, GOAL_TOP, GOAL_DEPTH, GOAL_WIDTH)
        for goal in (left_goal, right_goal):
            pygame.draw.rect(self.screen, (25, 28, 32), goal)
            for gx in range(goal.left, goal.right, 8):
                pygame.draw.line(self.screen, NET, (gx, goal.top), (gx, goal.bottom), 1)
            for gy in range(goal.top, goal.bottom, 8):
                pygame.draw.line(self.screen, NET, (goal.left, gy), (goal.right, gy), 1)
            pygame.draw.rect(self.screen, WHITE, goal, 3)
        # Goal posts highlight on the goal line.
        pygame.draw.line(self.screen, YELLOW, (FIELD.left, GOAL_TOP), (FIELD.left, GOAL_BOTTOM), 4)
        pygame.draw.line(self.screen, YELLOW, (FIELD.right, GOAL_TOP), (FIELD.right, GOAL_BOTTOM), 4)

    def draw_hud(self):
        # Scoreboard
        board = pygame.Rect(WIDTH // 2 - 110, 6, 220, 46)
        panel = pygame.Surface(board.size, pygame.SRCALPHA)
        panel.fill((0, 0, 0, 140))
        self.screen.blit(panel, board.topleft)
        score_surf = self.font_mid.render(f"{self.score[0]}  -  {self.score[1]}", True, WHITE)
        self.screen.blit(score_surf, score_surf.get_rect(center=board.center))
        pygame.draw.circle(self.screen, BLUE, (board.left + 18, board.centery), 10)
        pygame.draw.circle(self.screen, RED, (board.right - 18, board.centery), 10)
        # Timer
        mins, secs = divmod(self.time_left, 60)
        timer = self.font_small.render(f"{mins}:{secs:02d}", True, WHITE)
        self.screen.blit(timer, timer.get_rect(center=(WIDTH // 2, 66)))

    def draw_menu(self):
        title = self.font_big.render("PITCH KINGS", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 150)))
        sub = self.font_small.render("arcade soccer", True, YELLOW)
        self.screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 205)))

        mode1 = "> 1 Player (vs AI) <" if not self.two_player else "  1 Player (vs AI)  "
        mode2 = "> 2 Players <" if self.two_player else "  2 Players  "
        m1 = self.font_mid.render(mode1, True, BLUE if not self.two_player else WHITE)
        m2 = self.font_mid.render(mode2, True, RED if self.two_player else WHITE)
        self.screen.blit(m1, m1.get_rect(center=(WIDTH // 2, 290)))
        self.screen.blit(m2, m2.get_rect(center=(WIDTH // 2, 340)))

        lines = [
            "Press 1 or 2 to pick a mode",
            "",
            "Blue: WASD + L-Shift to sprint",
            "Red:  Arrows + R-Shift to sprint",
            "Bump the ball to kick it",
            "",
            "Press ENTER to kick off",
        ]
        for i, line in enumerate(lines):
            color = YELLOW if "ENTER" in line else WHITE
            surf = self.font_small.render(line, True, color)
            self.screen.blit(surf, surf.get_rect(center=(WIDTH // 2, 400 + i * 26)))

    def draw_fulltime(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        if self.score[0] > self.score[1]:
            result, color = "BLUE WINS!", BLUE
        elif self.score[1] > self.score[0]:
            result, color = "RED WINS!", RED
        else:
            result, color = "DRAW!", WHITE
        title = self.font_big.render("FULL TIME", True, WHITE)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 90)))
        res = self.font_mid.render(result, True, color)
        self.screen.blit(res, res.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
        sc = self.font_mid.render(f"{self.score[0]} - {self.score[1]}", True, WHITE)
        self.screen.blit(sc, sc.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30)))
        prompt = self.font_small.render("Press ENTER for a rematch", True, YELLOW)
        self.screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 90)))

    def banner(self, big, small):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 90))
        self.screen.blit(overlay, (0, 0))
        big_surf = self.font_big.render(big, True, YELLOW)
        self.screen.blit(big_surf, big_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10)))
        if small:
            small_surf = self.font_small.render(small, True, WHITE)
            self.screen.blit(small_surf, small_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50)))

    # -- loop -------------------------------------------------------------
    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

    def quit(self):
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
