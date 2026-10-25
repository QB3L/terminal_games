#!/usr/bin/env python3
"""
tetris.py — Tetris for the terminal (Textual).

    pip install textual
    python3 tetris.py

Keys:  ← → / a d  move      ↓ / s  soft drop      space  hard drop
       ↑ / x  rotate cw     z  rotate ccw         c  hold
       p pause     r restart     q quit
Best score saved to ~/.tetris_tui.json.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.widgets import Static

COLS, ROWS = 10, 20
SAVE_PATH = Path.home() / ".tetris_tui.json"

C_BG = "#0b0e14"
C_WELL = "#141a26"
C_WALL = "#3a4256"
C_DIM = "#8a93a6"
C_ACCENT = "#6fa8ff"
C_GHOST = "#2c3650"

# piece -> (color, list of rotation states as (x, y) offsets)
def _rots(shape: list[str]) -> list[list[tuple[int, int]]]:
    """Generate 4 rotations of an ASCII shape by rotating its bounding box."""
    cells = [(x, y) for y, row in enumerate(shape) for x, ch in enumerate(row) if ch == "#"]
    n = len(shape)
    out = []
    for _ in range(4):
        out.append(sorted(cells))
        cells = [(n - 1 - y, x) for x, y in cells]
    return out


PIECES = {
    "I": ("#5fd3f0", _rots(["....", "####", "....", "...."])),
    "O": ("#f5d547", _rots(["##", "##"])),
    "T": ("#c9a7ff", _rots([".#.", "###", "..."])),
    "S": ("#7ee081", _rots([".##", "##.", "..."])),
    "Z": ("#ff6b6b", _rots(["##.", ".##", "..."])),
    "J": ("#6fa8ff", _rots(["#..", "###", "..."])),
    "L": ("#ffa94d", _rots(["..#", "###", "..."])),
}
KICKS = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (-1, -1), (1, -1)]
LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}


class Piece:
    def __init__(self, kind: str) -> None:
        self.kind, self.rot = kind, 0
        size = max(x for x, _ in PIECES[kind][1][0]) + 1
        self.x, self.y = (COLS - size) // 2, 0

    def cells(self, x: int | None = None, y: int | None = None, rot: int | None = None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        rot = self.rot if rot is None else rot
        return [(x + dx, y + dy) for dx, dy in PIECES[self.kind][1][rot % 4]]


class Game:
    def __init__(self) -> None:
        self.grid: list[list[str | None]] = [[None] * COLS for _ in range(ROWS)]
        self.bag: list[str] = []
        self.queue = [self._draw() for _ in range(3)]
        self.hold: str | None = None
        self.hold_used = False
        self.score = self.lines = 0
        self.level = 1
        self.over = False
        self.cur = self._next_piece()

    def _draw(self) -> str:
        if not self.bag:
            self.bag = list(PIECES)
            random.shuffle(self.bag)
        return self.bag.pop()

    def _next_piece(self) -> Piece:
        p = Piece(self.queue.pop(0))
        self.queue.append(self._draw())
        if not self.fits(p.cells()):
            self.over = True
        return p

    def fits(self, cells) -> bool:
        return all(0 <= x < COLS and 0 <= y < ROWS and self.grid[y][x] is None for x, y in cells)

    def move(self, dx: int, dy: int) -> bool:
        if self.fits(self.cur.cells(self.cur.x + dx, self.cur.y + dy)):
            self.cur.x += dx; self.cur.y += dy
            return True
        return False

    def rotate(self, d: int) -> None:
        rot = (self.cur.rot + d) % 4
        for kx, ky in KICKS:
            if self.fits(self.cur.cells(self.cur.x + kx, self.cur.y + ky, rot)):
                self.cur.x += kx; self.cur.y += ky; self.cur.rot = rot
                return

    def ghost_y(self) -> int:
        y = self.cur.y
        while self.fits(self.cur.cells(y=y + 1)):
            y += 1
        return y

    def hard_drop(self) -> None:
        gy = self.ghost_y()
        self.score += 2 * (gy - self.cur.y)
        self.cur.y = gy
        self.lock()

    def swap_hold(self) -> None:
        if self.hold_used:
            return
        self.hold_used = True
        kind = self.cur.kind
        if self.hold is None:
            self.hold = kind
            self.cur = self._next_piece()
        else:
            self.hold, kind = kind, self.hold
            self.cur = Piece(kind)
            if not self.fits(self.cur.cells()):
                self.over = True

    def lock(self) -> None:
        for x, y in self.cur.cells():
            self.grid[y][x] = self.cur.kind
        full = [y for y in range(ROWS) if all(self.grid[y])]
        for y in full:
            del self.grid[y]
            self.grid.insert(0, [None] * COLS)
        if full:
            self.lines += len(full)
            self.score += LINE_SCORES[len(full)] * self.level
            self.level = self.lines // 10 + 1
        self.hold_used = False
        self.cur = self._next_piece()

    def gravity(self) -> None:
        if not self.move(0, 1):
            self.lock()


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


def _mini(kind: str | None, label: str) -> Text:
    """4-line preview of a piece for the side panel."""
    t = Text(no_wrap=True)
    t.append(label + "\n", style=C_DIM)
    grid = [["  "] * 4 for _ in range(2)]
    if kind:
        color = PIECES[kind][0]
        cells = PIECES[kind][1][0]
        miny = min(y for _, y in cells)
        for x, y in cells:
            if y - miny < 2:
                grid[y - miny][x] = "██"
        for row in grid:
            for ch in row:
                t.append(ch, style=color)
            t.append("\n")
    else:
        t.append("\n\n")
    return t


class Well(Static):
    DEFAULT_CSS = f"Well {{ width: {COLS * 2 + 2}; height: {ROWS + 1}; }}"

    def render(self) -> Text:
        app: TetrisApp = self.app  # type: ignore[assignment]
        g = app.game
        cur = {c: g.cur.kind for c in g.cur.cells()} if not g.over else {}
        ghost = set(g.cur.cells(y=g.ghost_y())) if not g.over else set()
        out = Text(no_wrap=True)
        for y in range(ROWS):
            out.append("▌", style=C_WALL)
            for x in range(COLS):
                k = cur.get((x, y)) or g.grid[y][x]
                if k:
                    out.append("██", style=PIECES[k][0])
                elif (x, y) in ghost:
                    out.append("░░", style=f"{C_GHOST} on {C_WELL}")
                else:
                    out.append("  ", style=f"on {C_WELL}")
            out.append("▐", style=C_WALL)
            out.append("\n")
        out.append("▀" * (COLS * 2 + 2), style=C_WALL)
        label = None
        if g.over:
            label = f" GAME OVER · {g.score} · r "
        elif app.paused:
            label = " PAUSED · p "
        elif not app.started:
            label = " any key to start "
        if label:
            lines = out.split("\n")
            start = (COLS * 2 + 2 - len(label)) // 2
            lines[ROWS // 2] = Text(" " * start) + Text(label, style="bold #ffffff on #2d6cdf")
            out = Text("\n").join(lines)
        return out


class Side(Static):
    DEFAULT_CSS = "Side { width: 14; height: auto; margin-left: 2; }"

    def render(self) -> Text:
        app: TetrisApp = self.app  # type: ignore[assignment]
        g = app.game
        t = Text(no_wrap=True)
        for label, val, color in [("Score", g.score, "#f2f2f2"), ("Best", app.best, C_ACCENT),
                                  ("Level", g.level, "#f2f2f2"), ("Lines", g.lines, "#f2f2f2")]:
            t.append(f"{label}\n", style=C_DIM)
            t.append(f"{val}\n\n", style=f"bold {color}")
        t.append_text(_mini(g.hold, "Hold  c"))
        t.append("\n")
        t.append("Next\n", style=C_DIM)
        for k in g.queue:
            t.append_text(_mini(k, ""))
        return t


class TetrisApp(App):
    TITLE = "Tetris"
    CSS = f"""
    Screen {{ background: {C_BG}; align: center top; }}
    #root {{ width: auto; height: auto; padding: 1 2; }}
    #help {{ color: {C_DIM}; margin-top: 1; }}
    """
    BINDINGS = [
        Binding("q", "quit", show=False),
        Binding("p", "pause", show=False),
        Binding("r", "restart", show=False),
        Binding("left,a,h", "shift(-1)", show=False),
        Binding("right,d,l", "shift(1)", show=False),
        Binding("down,s,j", "soft", show=False),
        Binding("up,x,k", "rotate(1)", show=False),
        Binding("z", "rotate(-1)", show=False),
        Binding("space", "hard", show=False),
        Binding("c", "hold", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.game = Game()
        self.best = load_best()
        self.paused = False
        self.started = False
        self._timer = None

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="root"):
                with Horizontal():
                    yield Well()
                    yield Side()
                yield Static("←→ move · ↓ soft · space hard · ↑/x z rotate · c hold · p pause",
                             id="help")

    def _interval(self) -> float:
        return max(0.06, 0.8 * (0.85 ** (self.game.level - 1)))

    def _start_timer(self) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = self.set_interval(self._interval(), self.tick)

    def refresh_all(self) -> None:
        self.query_one(Well).refresh()
        self.query_one(Side).refresh()

    def _active(self) -> bool:
        if not self.started:
            self.started = True
            self._start_timer()
        return not self.paused and not self.game.over

    def _after(self) -> None:
        g = self.game
        if g.score > self.best:
            self.best = g.score
            save_best(self.best)
        if self._timer and abs(self._timer._interval - self._interval()) > 1e-6:
            self._start_timer()
        self.refresh_all()

    def tick(self) -> None:
        if self.paused or self.game.over:
            return
        self.game.gravity()
        self._after()

    def action_shift(self, dx: int) -> None:
        if self._active():
            self.game.move(dx, 0); self._after()

    def action_soft(self) -> None:
        if self._active():
            if self.game.move(0, 1):
                self.game.score += 1
            self._after()

    def action_hard(self) -> None:
        if self._active():
            self.game.hard_drop(); self._after()

    def action_rotate(self, d: int) -> None:
        if self._active():
            self.game.rotate(d); self._after()

    def action_hold(self) -> None:
        if self._active():
            self.game.swap_hold(); self._after()

    def action_pause(self) -> None:
        if self.started and not self.game.over:
            self.paused = not self.paused
            self.refresh_all()

    def action_restart(self) -> None:
        self.game = Game()
        self.paused = False
        self.started = False
        if self._timer:
            self._timer.stop(); self._timer = None
        self.refresh_all()


if __name__ == "__main__":
    TetrisApp().run()
