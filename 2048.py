#!/usr/bin/env python3
"""
2048.py — the sliding-tile game for the terminal (Textual).

    pip install textual
    python3 2048.py

Keys:  arrows / hjkl / wasd  slide      u undo      r new game      q quit
Your best score is saved to ~/.2048_tui.json.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.widgets import Static

N = 4
TILE_W, TILE_H = 9, 3
SAVE_PATH = Path.home() / ".2048_tui.json"

C_BG = "#0b0e14"
C_EMPTY = "#1c2230"
C_DIM = "#8a93a6"
C_ACCENT = "#6fa8ff"

# value -> (background, foreground)
COLORS = {
    2: ("#3a4256", "#f2f2f2"), 4: ("#4a5570", "#f2f2f2"),
    8: ("#e3885a", "#1a1a1a"), 16: ("#eb7041", "#1a1a1a"),
    32: ("#f05f3f", "#1a1a1a"), 64: ("#f03d1f", "#ffffff"),
    128: ("#edcf72", "#1a1a1a"), 256: ("#edcc61", "#1a1a1a"),
    512: ("#edc850", "#1a1a1a"), 1024: ("#edc53f", "#1a1a1a"),
    2048: ("#edc22e", "#1a1a1a"),
}
C_BIG = ("#c9a7ff", "#1a1030")


def _slide_row(row: list[int]) -> tuple[list[int], int]:
    """Slide/merge a row to the left. Returns (new_row, score_gained)."""
    tiles = [v for v in row if v]
    out, gained, i = [], 0, 0
    while i < len(tiles):
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            out.append(tiles[i] * 2)
            gained += tiles[i] * 2
            i += 2
        else:
            out.append(tiles[i])
            i += 1
    return out + [0] * (N - len(out)), gained


class Game:
    def __init__(self) -> None:
        self.grid = [[0] * N for _ in range(N)]
        self.score = 0
        self.undo: list[tuple[list[list[int]], int]] = []
        self.spawn(); self.spawn()

    def spawn(self) -> None:
        empty = [(r, c) for r in range(N) for c in range(N) if not self.grid[r][c]]
        if empty:
            r, c = random.choice(empty)
            self.grid[r][c] = 4 if random.random() < 0.1 else 2

    def move(self, d: str) -> bool:
        """Apply a move. Returns True if anything changed."""
        g = self.grid
        if d in ("up", "down"):
            g = [list(col) for col in zip(*g)]
        if d in ("right", "down"):
            g = [row[::-1] for row in g]
        new, gained = [], 0
        for row in g:
            nr, s = _slide_row(row)
            new.append(nr); gained += s
        if d in ("right", "down"):
            new = [row[::-1] for row in new]
        if d in ("up", "down"):
            new = [list(col) for col in zip(*new)]
        if new == self.grid:
            return False
        self.undo.append(([row[:] for row in self.grid], self.score))
        self.undo = self.undo[-50:]
        self.grid, self.score = new, self.score + gained
        self.spawn()
        return True

    def can_move(self) -> bool:
        for r in range(N):
            for c in range(N):
                v = self.grid[r][c]
                if not v:
                    return True
                if c + 1 < N and self.grid[r][c + 1] == v:
                    return True
                if r + 1 < N and self.grid[r + 1][c] == v:
                    return True
        return False

    def won(self) -> bool:
        return any(v >= 2048 for row in self.grid for v in row)

    def undo_move(self) -> None:
        if self.undo:
            self.grid, self.score = self.undo.pop()


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


BOARD_W = N * (TILE_W + 1) + 1


class Board(Static):
    DEFAULT_CSS = f"Board {{ width: {BOARD_W}; height: {N * (TILE_H + 1) + 1}; }}"

    def render(self) -> Text:
        app: App2048 = self.app  # type: ignore[assignment]
        g = app.game.grid
        out = Text(no_wrap=True)
        gap = Text(" " * BOARD_W + "\n", style=f"on {C_BG}")
        out.append_text(gap)
        for r in range(N):
            for line in range(TILE_H):
                out.append(" ")
                for c in range(N):
                    v = g[r][c]
                    if v:
                        bg, fg = COLORS.get(v, C_BIG)
                        txt = str(v).center(TILE_W) if line == TILE_H // 2 else " " * TILE_W
                        out.append(txt, style=f"bold {fg} on {bg}")
                    else:
                        out.append(" " * TILE_W, style=f"on {C_EMPTY}")
                    out.append(" ")
                out.append("\n")
            out.append_text(gap)
        if app.message:
            lines = out.split("\n")
            label = f" {app.message} "
            start = (BOARD_W - len(label)) // 2
            lines[len(lines) // 2] = Text(" " * start) + Text(label, style="bold #ffffff on #2d6cdf")
            out = Text("\n").join(lines)
        return out


class Hud(Static):
    DEFAULT_CSS = f"Hud {{ width: {BOARD_W}; height: 2; }}"

    def render(self) -> Text:
        app: App2048 = self.app  # type: ignore[assignment]
        cols = [("Score", str(app.game.score), "#f2f2f2"), ("Best", str(app.best), C_ACCENT),
                ("Moves", str(app.moves), "#f2f2f2")]
        w = BOARD_W // len(cols)
        top, bot = Text(no_wrap=True), Text(no_wrap=True)
        for label, val, color in cols:
            top.append(label.ljust(w), style=C_DIM)
            bot.append(val.ljust(w), style=f"bold {color}")
        return top + Text("\n") + bot


class App2048(App):
    TITLE = "2048"
    CSS = f"""
    Screen {{ background: {C_BG}; align: center top; }}
    #root {{ width: auto; height: auto; padding: 1 2; }}
    #help {{ color: {C_DIM}; margin-top: 1; }}
    """
    BINDINGS = [
        Binding("q", "quit", show=False),
        Binding("u", "undo", show=False),
        Binding("r", "restart", show=False),
        Binding("up,k,w", "move('up')", show=False),
        Binding("down,j,s", "move('down')", show=False),
        Binding("left,h,a", "move('left')", show=False),
        Binding("right,l,d", "move('right')", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.game = Game()
        self.best = load_best()
        self.moves = 0
        self.message = ""
        self.won_shown = False

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="root"):
                yield Hud()
                yield Board()
                yield Static("arrows / hjkl / wasd slide · u undo · r new · q quit", id="help")

    def refresh_all(self) -> None:
        self.query_one(Board).refresh()
        self.query_one(Hud).refresh()

    def action_move(self, d: str) -> None:
        if self.message and "over" in self.message:
            return
        if self.game.move(d):
            self.moves += 1
            self.message = ""
            if self.game.score > self.best:
                self.best = self.game.score
                save_best(self.best)
            if self.game.won() and not self.won_shown:
                self.won_shown = True
                self.message = "🎉 2048! keep going"
            elif not self.game.can_move():
                self.message = f"Game over · {self.game.score} pts · r to restart"
        self.refresh_all()

    def action_undo(self) -> None:
        self.game.undo_move()
        self.message = ""
        self.refresh_all()

    def action_restart(self) -> None:
        self.game = Game()
        self.moves = 0
        self.message = ""
        self.won_shown = False
        self.refresh_all()


if __name__ == "__main__":
    App2048().run()
