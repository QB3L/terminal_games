#!/usr/bin/env python3
"""
snake.py — classic Snake for the terminal (Textual).

    pip install textual
    python3 snake.py [--wrap]      # --wrap: pass through walls instead of dying

Keys:  arrows / hjkl / wasd  steer      p pause      r restart      q quit
"""
from __future__ import annotations

import json
import random
import sys
from collections import deque
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.widgets import Static

W, H = 32, 20                     # board size in cells (each cell = 2 columns)
SAVE_PATH = Path.home() / ".snake_tui.json"

C_BG = "#0b0e14"
C_BOARD = "#141a26"
C_HEAD = "#9be36d"
C_BODY = "#5fbf3f"
C_FOOD = "#ff6b6b"
C_WALL = "#3a4256"
C_DIM = "#8a93a6"
C_ACCENT = "#6fa8ff"

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def load_best() -> int:
    try:
        return int(json.loads(SAVE_PATH.read_text())["best"])
    except Exception:
        return 0


def save_best(best: int) -> None:
    try:
        SAVE_PATH.write_text(json.dumps({"best": best}))
    except OSError:
        pass


class Board(Static):
    DEFAULT_CSS = f"Board {{ width: {W * 2 + 2}; height: {H + 2}; }}"

    def render(self) -> Text:
        app: SnakeApp = self.app  # type: ignore[assignment]
        body = set(app.snake)
        head = app.snake[0]
        out = Text(no_wrap=True)
        wall = "·" if app.wrap else "▒"
        out.append(wall * (W * 2 + 2), style=C_WALL)
        out.append("\n")
        for y in range(H):
            out.append(wall, style=C_WALL)
            for x in range(W):
                p = (x, y)
                if p == head:
                    out.append("██", style=C_HEAD)
                elif p in body:
                    out.append("██", style=C_BODY)
                elif p == app.food:
                    out.append("●", style=f"bold {C_FOOD} on {C_BOARD}")
                    out.append(" ", style=f"on {C_BOARD}")
                else:
                    out.append("  ", style=f"on {C_BOARD}")
            out.append(wall, style=C_WALL)
            out.append("\n")
        out.append(wall * (W * 2 + 2), style=C_WALL)
        if app.state != "playing":
            lines = out.split("\n")
            if app.state == "paused":
                label = " PAUSED — p to resume "
            elif app.state == "dead":
                label = f" GAME OVER · {app.score} pts · r to restart "
            else:
                label = " SNAKE · press any arrow to start "
            start = (W * 2 + 2 - len(label)) // 2
            lines[H // 2 + 1] = Text(" " * start) + Text(label, style="bold #ffffff on #2d6cdf")
            out = Text("\n").join(lines)
        return out


class Hud(Static):
    DEFAULT_CSS = f"Hud {{ width: {W * 2 + 2}; height: 2; }}"

    def render(self) -> Text:
        app: SnakeApp = self.app  # type: ignore[assignment]
        cols = [("Score", str(app.score), "#f2f2f2"),
                ("Best", str(app.best), C_ACCENT),
                ("Length", str(len(app.snake)), "#f2f2f2"),
                ("Speed", f"{app.level}", "#f2f2f2"),
                ("Walls", "wrap" if app.wrap else "solid", C_DIM)]
        w = (W * 2 + 2) // len(cols)
        top, bot = Text(no_wrap=True), Text(no_wrap=True)
        for label, val, color in cols:
            top.append(label.ljust(w), style=C_DIM)
            bot.append(val.ljust(w), style=f"bold {color}")
        return top + Text("\n") + bot


class SnakeApp(App):
    TITLE = "Snake"
    CSS = f"""
    Screen {{ background: {C_BG}; align: center top; }}
    #root {{ width: auto; height: auto; padding: 1 2; }}
    #help {{ color: {C_DIM}; margin-top: 1; }}
    """
    BINDINGS = [
        Binding("q", "quit", show=False),
        Binding("p", "pause", show=False),
        Binding("r", "restart", show=False),
        Binding("up,k,w", "turn('up')", show=False),
        Binding("down,j,s", "turn('down')", show=False),
        Binding("left,h,a", "turn('left')", show=False),
        Binding("right,l,d", "turn('right')", show=False),
    ]

    def __init__(self, wrap: bool) -> None:
        super().__init__()
        self.wrap = wrap
        self.best = load_best()
        self._timer = None
        self.reset()

    def reset(self) -> None:
        cx, cy = W // 2, H // 2
        self.snake: deque[tuple[int, int]] = deque([(cx, cy), (cx - 1, cy), (cx - 2, cy)])
        self.dir = (1, 0)
        self.queue: deque[tuple[int, int]] = deque()
        self.score = 0
        self.level = 1
        self.state = "ready"          # ready | playing | paused | dead
        self.food = self._spawn_food()

    def _spawn_food(self) -> tuple[int, int]:
        free = [(x, y) for x in range(W) for y in range(H) if (x, y) not in self.snake]
        return random.choice(free)

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="root"):
                yield Hud()
                yield Board()
                yield Static("arrows / hjkl / wasd steer · p pause · r restart · q quit", id="help")

    def _interval(self) -> float:
        return max(0.05, 0.16 - (self.level - 1) * 0.012)

    def _start_timer(self) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = self.set_interval(self._interval(), self.tick)

    def refresh_all(self) -> None:
        self.query_one(Board).refresh()
        self.query_one(Hud).refresh()

    def tick(self) -> None:
        if self.state != "playing":
            return
        while self.queue:
            d = self.queue.popleft()
            if (d[0] + self.dir[0], d[1] + self.dir[1]) != (0, 0):   # not a reversal
                self.dir = d
                break
        hx, hy = self.snake[0]
        nx, ny = hx + self.dir[0], hy + self.dir[1]
        if self.wrap:
            nx, ny = nx % W, ny % H
        elif not (0 <= nx < W and 0 <= ny < H):
            return self._die()
        tail = self.snake[-1]
        if (nx, ny) in self.snake and (nx, ny) != tail:
            return self._die()
        self.snake.appendleft((nx, ny))
        if (nx, ny) == self.food:
            self.score += 10 * self.level
            if len(self.snake) % 5 == 0:
                self.level += 1
                self._start_timer()
            self.food = self._spawn_food()
        else:
            self.snake.pop()
        self.refresh_all()

    def _die(self) -> None:
        self.state = "dead"
        if self.score > self.best:
            self.best = self.score
            save_best(self.best)
        self.refresh_all()

    def action_turn(self, name: str) -> None:
        if self.state == "ready":
            self.state = "playing"
            self._start_timer()
        if self.state == "playing" and len(self.queue) < 3:
            self.queue.append(DIRS[name])

    def action_pause(self) -> None:
        if self.state == "playing":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "playing"
        self.refresh_all()

    def action_restart(self) -> None:
        self.reset()
        self.refresh_all()


if __name__ == "__main__":
    SnakeApp(wrap="--wrap" in sys.argv).run()
