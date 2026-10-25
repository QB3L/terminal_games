#!/usr/bin/env python3
"""
sudoku.py — a sudoku.com-style Sudoku for the terminal (Textual).

    pip install textual
    python3 sudoku.py [easy|medium|hard|expert]

Mouse:  click a cell to select it, click the number pad, click the controls.
Keys:   1-9 place (or note, in Notes mode)   n  toggle Notes
        arrows / hjkl move                   e / backspace / delete  erase
        u / ctrl+z undo                      ?  hint
        p pause      ctrl+n new game         d  change difficulty
        q quit (game is auto-saved and resumed next launch)
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

# --------------------------------------------------------------------------- #
#  Puzzle generation / solving
# --------------------------------------------------------------------------- #

DIFFICULTIES = {  # name -> number of clues to leave on the board
    "easy": 40,
    "medium": 34,
    "hard": 28,
    "expert": 24,
}


def _box(i: int) -> int:
    return (i // 3) * 3


def _peers(r: int, c: int):
    for k in range(9):
        yield r, k
        yield k, c
    for rr in range(_box(r), _box(r) + 3):
        for cc in range(_box(c), _box(c) + 3):
            yield rr, cc


def _candidates(g: list[list[int]], r: int, c: int) -> set[int]:
    used = {g[rr][cc] for rr, cc in _peers(r, c)}
    return {d for d in range(1, 10) if d not in used}


def _fill(g: list[list[int]]) -> bool:
    """Backtracking fill of a (partially) empty grid, randomized."""
    for r in range(9):
        for c in range(9):
            if g[r][c] == 0:
                cands = list(_candidates(g, r, c))
                random.shuffle(cands)
                for d in cands:
                    g[r][c] = d
                    if _fill(g):
                        return True
                g[r][c] = 0
                return False
    return True


def _count_solutions(g: list[list[int]], limit: int = 2) -> int:
    """Count solutions up to `limit` (MRV ordering keeps this fast)."""
    best = None
    best_c: set[int] = set()
    for r in range(9):
        for c in range(9):
            if g[r][c] == 0:
                cands = _candidates(g, r, c)
                if not cands:
                    return 0
                if best is None or len(cands) < len(best_c):
                    best, best_c = (r, c), cands
                    if len(cands) == 1:
                        break
        else:
            continue
        break
    if best is None:
        return 1
    r, c = best
    total = 0
    for d in best_c:
        g[r][c] = d
        total += _count_solutions(g, limit - total)
        g[r][c] = 0
        if total >= limit:
            break
    return total


def generate(clues: int) -> tuple[list[list[int]], list[list[int]]]:
    """Return (puzzle, solution). Removes cells while the solution stays unique."""
    sol = [[0] * 9 for _ in range(9)]
    _fill(sol)
    puz = [row[:] for row in sol]
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)
    remaining = 81
    for r, c in cells:
        if remaining <= clues:
            break
        keep = puz[r][c]
        puz[r][c] = 0
        if _count_solutions(puz) != 1:
            puz[r][c] = keep
        else:
            remaining -= 1
    return puz, sol


# --------------------------------------------------------------------------- #
#  Game state
# --------------------------------------------------------------------------- #

SAVE_PATH = Path.home() / ".sudoku_tui.json"
MAX_MISTAKES = 3


@dataclass
class Game:
    difficulty: str
    puzzle: list[list[int]]
    solution: list[list[int]]
    values: list[list[int]] = field(default_factory=list)
    notes: list[list[set[int]]] = field(default_factory=list)
    mistakes: int = 0
    elapsed: float = 0.0
    hints: int = 0
    undo: list = field(default_factory=list)

    @classmethod
    def new(cls, difficulty: str) -> "Game":
        puz, sol = generate(DIFFICULTIES[difficulty])
        g = cls(difficulty, puz, sol)
        g.values = [row[:] for row in puz]
        g.notes = [[set() for _ in range(9)] for _ in range(9)]
        return g

    # -- helpers ----------------------------------------------------------- #
    def is_given(self, r: int, c: int) -> bool:
        return self.puzzle[r][c] != 0

    def is_wrong(self, r: int, c: int) -> bool:
        v = self.values[r][c]
        return v != 0 and v != self.solution[r][c]

    def solved(self) -> bool:
        return self.values == self.solution

    def lost(self) -> bool:
        return self.mistakes >= MAX_MISTAKES

    def count_of(self, d: int) -> int:
        return sum(row.count(d) for row in self.values)

    def _snapshot(self):
        self.undo.append(
            ([row[:] for row in self.values],
             [[set(s) for s in row] for row in self.notes])
        )
        if len(self.undo) > 200:
            self.undo.pop(0)

    # -- moves ------------------------------------------------------------- #
    def place(self, r: int, c: int, d: int) -> bool:
        """Place a value. Returns True if the move was a mistake."""
        if self.is_given(r, c) or self.values[r][c] == d:
            return False
        self._snapshot()
        self.values[r][c] = d
        self.notes[r][c].clear()
        wrong = d != self.solution[r][c]
        if wrong:
            self.mistakes += 1
        else:
            for rr, cc in _peers(r, c):          # auto-clear notes like sudoku.com
                self.notes[rr][cc].discard(d)
        return wrong

    def toggle_note(self, r: int, c: int, d: int) -> None:
        if self.is_given(r, c) or self.values[r][c] != 0:
            return
        self._snapshot()
        self.notes[r][c] ^= {d}

    def erase(self, r: int, c: int) -> None:
        if self.is_given(r, c):
            return
        if self.values[r][c] == 0 and not self.notes[r][c]:
            return
        self._snapshot()
        self.values[r][c] = 0
        self.notes[r][c].clear()

    def undo_move(self) -> None:
        if self.undo:
            self.values, self.notes = self.undo.pop()

    def hint(self, r: int, c: int) -> tuple[int, int] | None:
        """Fill the selected cell if it's empty/wrong, else a random one."""
        if self.is_given(r, c) or self.values[r][c] == self.solution[r][c]:
            empties = [(rr, cc) for rr in range(9) for cc in range(9)
                       if self.values[rr][cc] != self.solution[rr][cc]]
            if not empties:
                return None
            r, c = random.choice(empties)
        self._snapshot()
        self.values[r][c] = self.solution[r][c]
        self.notes[r][c].clear()
        for rr, cc in _peers(r, c):
            self.notes[rr][cc].discard(self.values[r][c])
        self.hints += 1
        return r, c

    # -- persistence ------------------------------------------------------- #
    def save(self) -> None:
        try:
            SAVE_PATH.write_text(json.dumps({
                "difficulty": self.difficulty,
                "puzzle": self.puzzle,
                "solution": self.solution,
                "values": self.values,
                "notes": [[sorted(s) for s in row] for row in self.notes],
                "mistakes": self.mistakes,
                "elapsed": self.elapsed,
                "hints": self.hints,
            }))
        except OSError:
            pass

    @classmethod
    def load(cls) -> "Game | None":
        try:
            d = json.loads(SAVE_PATH.read_text())
            g = cls(d["difficulty"], d["puzzle"], d["solution"])
            g.values = d["values"]
            g.notes = [[set(s) for s in row] for row in d["notes"]]
            g.mistakes = d["mistakes"]
            g.elapsed = d["elapsed"]
            g.hints = d.get("hints", 0)
            if g.solved() or g.lost():
                return None
            return g
        except Exception:
            return None


# --------------------------------------------------------------------------- #
#  Styling
# --------------------------------------------------------------------------- #

CELL_W, CELL_H = 7, 3          # inner size of a cell
STEP_X, STEP_Y = CELL_W + 1, CELL_H + 1
BOARD_W, BOARD_H = 9 * STEP_X + 1, 9 * STEP_Y + 1

C_BG_SELECTED = "#2d6cdf"
C_BG_PEER = "#1c2740"          # same row / column / box
C_BG_SAME = "#2a3e6b"          # same digit as selected
C_BG_WRONG = "#5a1d1d"
C_GIVEN = "bold #f2f2f2"
C_USER = "bold #6fa8ff"
C_WRONG = "bold #ff6b6b"
C_NOTE = "#8a93a6"
C_NOTE_HI = "bold #1a1030 on #c9a7ff"   # note matching the selected digit (light purple)
C_FRAME = "#5d6678"
C_FRAME_HEAVY = "#aab2c4"
C_DIM = "#8a93a6"
C_ACCENT = "#6fa8ff"


def _frame_char(x: int, y: int) -> str:
    """Box-drawing char for a frame position in the 9x9 grid."""
    vx = x % STEP_X == 0
    hy = y % STEP_Y == 0
    heavy_v = vx and (x // STEP_X) % 3 == 0
    heavy_h = hy and (y // STEP_Y) % 3 == 0
    if vx and hy:
        top, bot = y > 0, y < BOARD_H - 1
        left, right = x > 0, x < BOARD_W - 1
        if heavy_v and heavy_h:
            table = {
                (True, True, True, True): "╋", (False, True, True, True): "┳",
                (True, False, True, True): "┻", (True, True, False, True): "┣",
                (True, True, True, False): "┫", (False, True, False, True): "┏",
                (False, True, True, False): "┓", (True, False, False, True): "┗",
                (True, False, True, False): "┛",
            }
        elif heavy_v:
            table = {(True, True, True, True): "╂", (True, True, False, True): "┠",
                     (True, True, True, False): "┨"}
        elif heavy_h:
            table = {(True, True, True, True): "┿", (False, True, True, True): "┯",
                     (True, False, True, True): "┷"}
        else:
            table = {(True, True, True, True): "┼"}
        return table.get((top, bot, left, right), "┼")
    if vx:
        return "┃" if heavy_v else "│"
    if hy:
        return "━" if heavy_h else "─"
    return " "


def _frame_style(x: int, y: int) -> Style:
    heavy = (x % STEP_X == 0 and (x // STEP_X) % 3 == 0) or \
            (y % STEP_Y == 0 and (y // STEP_Y) % 3 == 0)
    return Style.parse(C_FRAME_HEAVY if heavy else C_FRAME)


# --------------------------------------------------------------------------- #
#  Widgets
# --------------------------------------------------------------------------- #

class Board(Static):
    """The 9x9 grid. Renders as one block of text; clicks map to cells."""

    DEFAULT_CSS = f"""
    Board {{ width: {BOARD_W}; height: {BOARD_H}; }}
    """

    def __init__(self) -> None:
        super().__init__()
        self.sel = (4, 4)

    @property
    def game(self) -> Game:
        return self.app.game  # type: ignore[attr-defined]

    def on_click(self, event: events.Click) -> None:
        x, y = event.x, event.y
        if x % STEP_X == 0 or y % STEP_Y == 0:
            return
        r, c = y // STEP_Y, x // STEP_X
        if 0 <= r < 9 and 0 <= c < 9:
            self.sel = (r, c)
            self.app.refresh_all()  # type: ignore[attr-defined]

    def _cell_bg(self, r: int, c: int, paused: bool) -> str | None:
        if paused:
            return None
        g = self.game
        sr, sc = self.sel
        if (r, c) == (sr, sc):
            return C_BG_SELECTED
        if g.is_wrong(r, c):
            return C_BG_WRONG
        sv = g.values[sr][sc]
        if sv and g.values[r][c] == sv:
            return C_BG_SAME
        if r == sr or c == sc or (_box(r) == _box(sr) and _box(c) == _box(sc)):
            return C_BG_PEER
        return None

    def _cell_lines(self, r: int, c: int, paused: bool) -> list[Text]:
        g = self.game
        bg = self._cell_bg(r, c, paused)
        base = Style(bgcolor=bg) if bg else Style()
        blank = Text(" " * CELL_W, style=base)
        if paused:
            return [blank, blank, blank]
        v = g.values[r][c]
        if v:
            fg = C_WRONG if g.is_wrong(r, c) else (C_GIVEN if g.is_given(r, c) else C_USER)
            if (r, c) == self.sel:
                fg = "bold #ffffff"
            mid = Text(" " * 3, style=base)
            mid.append(str(v), style=Style.parse(fg) + base)
            mid.append(" " * 3, style=base)
            return [blank, mid, blank]
        notes = g.notes[r][c]
        if not notes:
            return [blank, blank, blank]
        sr, sc = self.sel
        hi = g.values[sr][sc]
        lines = []
        for row in range(3):
            t = Text(" ", style=base)
            for k in range(3):
                d = row * 3 + k + 1
                if d in notes:
                    st = Style.parse(C_NOTE_HI if d == hi else C_NOTE) + base
                    t.append(str(d), style=st)
                else:
                    t.append(" ", style=base)
                if k < 2:
                    t.append(" ", style=base)
            t.append(" ", style=base)
            lines.append(t)
        return lines

    def render(self) -> Text:
        paused = self.app.paused  # type: ignore[attr-defined]
        out = Text(no_wrap=True)
        cell_cache = {}
        for y in range(BOARD_H):
            if y % STEP_Y == 0:
                for x in range(BOARD_W):
                    out.append(_frame_char(x, y), style=_frame_style(x, y))
            else:
                r = y // STEP_Y
                line = (y % STEP_Y) - 1
                for c in range(9):
                    out.append(_frame_char(c * STEP_X, y), style=_frame_style(c * STEP_X, y))
                    key = (r, c)
                    if key not in cell_cache:
                        cell_cache[key] = self._cell_lines(r, c, paused)
                    out.append_text(cell_cache[key][line])
                out.append(_frame_char(BOARD_W - 1, y), style=_frame_style(BOARD_W - 1, y))
            if y < BOARD_H - 1:
                out.append("\n")
        if paused:
            # overlay a centered "PAUSED" on the middle line
            mid_line = BOARD_H // 2
            lines = out.split("\n")
            label = " ▐▌ PAUSED — press p to resume "
            start = (BOARD_W - len(label)) // 2
            lines[mid_line] = Text(" " * start) + Text(label, style="bold #ffffff on #2d6cdf")
            out = Text("\n").join(lines)
        return out


class NumPad(Static):
    """1-9 keys with remaining-count under each; aligned to board columns."""

    DEFAULT_CSS = f"""
    NumPad {{ width: {BOARD_W}; height: 2; margin-top: 1; }}
    """

    def on_click(self, event: events.Click) -> None:
        c = event.x // STEP_X
        if 0 <= c < 9 and event.x % STEP_X != 0:
            self.app.input_digit(c + 1)  # type: ignore[attr-defined]

    def render(self) -> Text:
        g: Game = self.app.game  # type: ignore[attr-defined]
        notes_mode = self.app.notes_mode  # type: ignore[attr-defined]
        top, bot = Text(no_wrap=True), Text(no_wrap=True)
        for d in range(1, 10):
            left = sum(row.count(d) for row in g.values)
            remaining = 9 - left
            top.append(" ")
            bot.append(" ")
            if remaining <= 0:
                top.append(" " * CELL_W, style=C_DIM)
                bot.append(" " * CELL_W)
            else:
                style = f"bold {C_NOTE}" if notes_mode else f"bold {C_ACCENT}"
                top.append(f"   {d}   ", style=style)
                bot.append(f"   {remaining}   ", style=C_DIM)
        return top + Text("\n") + bot


class ControlBar(Static):
    """Undo / Erase / Notes / Hint / New — clickable, with hotkeys."""

    DEFAULT_CSS = f"""
    ControlBar {{ width: {BOARD_W}; height: 1; margin-top: 1; }}
    """

    def _items(self) -> list[tuple[str, str, str]]:
        notes_on = self.app.notes_mode  # type: ignore[attr-defined]
        return [
            ("undo", "↶ Undo", "u"),
            ("erase", "⌫ Erase", "e"),
            ("notes", f"✎ Notes {'ON ' if notes_on else 'OFF'}", "n"),
            ("hint", "✦ Hint", "?"),
            ("new", "⟳ New", "^n"),
        ]

    def _layout(self) -> list[tuple[str, int, int, Text]]:
        items = self._items()
        notes_on = self.app.notes_mode  # type: ignore[attr-defined]
        texts = []
        for key, label, hot in items:
            style = "bold #ffffff on #2d6cdf" if (key == "notes" and notes_on) else f"bold {C_ACCENT}"
            t = Text(f" {label} ", style=style)
            t.append(f"{hot}", style=C_DIM)
            texts.append((key, t))
        total = sum(t.cell_len for _, t in texts)
        gap = max(1, (BOARD_W - total) // (len(texts) + 1))
        out, x = [], gap
        for key, t in texts:
            out.append((key, x, x + t.cell_len, t))
            x += t.cell_len + gap
        return out

    def on_click(self, event: events.Click) -> None:
        for key, x0, x1, _ in self._layout():
            if x0 <= event.x < x1:
                self.app.run_control(key)  # type: ignore[attr-defined]
                return

    def render(self) -> Text:
        out, x = Text(no_wrap=True), 0
        for _, x0, x1, t in self._layout():
            out.append(" " * (x0 - x))
            out.append_text(t)
            x = x1
        return out


class Header(Static):
    DEFAULT_CSS = f"""
    Header {{ width: {BOARD_W}; height: 2; }}
    """

    def on_click(self, event: events.Click) -> None:
        if event.x >= BOARD_W - 8:
            self.app.action_pause()  # type: ignore[attr-defined]

    def render(self) -> Text:
        app = self.app
        g: Game = app.game  # type: ignore[attr-defined]
        mins, secs = divmod(int(g.elapsed), 60)
        cols = [
            ("Difficulty", g.difficulty.capitalize(), C_ACCENT),
            ("Mistakes", f"{g.mistakes}/{MAX_MISTAKES}",
             C_WRONG if g.mistakes else "#f2f2f2"),
            ("Hints", str(g.hints), "#f2f2f2"),
            ("Time", f"{mins:02d}:{secs:02d}", "#f2f2f2"),
        ]
        pause = "▶ p " if app.paused else "‖ p "  # type: ignore[attr-defined]
        w = (BOARD_W - len(pause)) // len(cols)
        top, bot = Text(no_wrap=True), Text(no_wrap=True)
        for label, val, color in cols:
            top.append(label.ljust(w), style=C_DIM)
            bot.append(val.ljust(w), style=f"bold {color}")
        top.append(" " * len(pause))
        bot.append(pause, style=f"bold {C_ACCENT}")
        return top + Text("\n") + bot


class StatusLine(Static):
    DEFAULT_CSS = f"""
    StatusLine {{ width: {BOARD_W}; height: 1; margin-top: 1; color: {C_DIM}; }}
    """


# --------------------------------------------------------------------------- #
#  Modal: end of game / new game
# --------------------------------------------------------------------------- #

class EndScreen(ModalScreen[str]):
    """Shown on win, loss, or when asking for a new game. Returns a difficulty or ''."""

    DEFAULT_CSS = """
    EndScreen { align: center middle; background: rgba(0,0,0,0.6); }
    EndScreen > Vertical {
        width: 46; height: auto; padding: 1 2;
        border: round #6fa8ff; background: #10141c;
    }
    EndScreen Static { width: 100%; content-align: center middle; }
    EndScreen .title { text-style: bold; color: #f2f2f2; }
    EndScreen .pick  { color: #6fa8ff; margin-top: 1; }
    EndScreen .dim   { color: #8a93a6; }
    """

    BINDINGS = [
        Binding("1", "pick('easy')", "Easy"),
        Binding("2", "pick('medium')", "Medium"),
        Binding("3", "pick('hard')", "Hard"),
        Binding("4", "pick('expert')", "Expert"),
        Binding("escape", "pick('')", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, title: str, subtitle: str, allow_back: bool) -> None:
        super().__init__()
        self._title, self._sub, self._back = title, subtitle, allow_back

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, classes="title")
            if self._sub:
                yield Static(self._sub, classes="dim")
            yield Static("New game — pick a difficulty", classes="pick")
            yield Static("[1] Easy   [2] Medium   [3] Hard   [4] Expert")
            yield Static(("[esc] back   " if self._back else "") + "[q] quit", classes="dim")

    def action_pick(self, diff: str) -> None:
        if diff == "" and not self._back:
            return
        self.dismiss(diff)

    def action_quit_app(self) -> None:
        self.app.exit()

    def on_click(self, event: events.Click) -> None:
        # click outside the panel = back (when allowed)
        if self._back and not isinstance(event.widget, Static):
            self.dismiss("")


# --------------------------------------------------------------------------- #
#  App
# --------------------------------------------------------------------------- #

class SudokuApp(App):
    TITLE = "Sudoku"
    CSS = """
    Screen { background: #0b0e14; align: center top; }
    #root { width: auto; height: auto; padding: 1 2; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("n", "toggle_notes", "Notes"),
        Binding("u,ctrl+z", "undo", "Undo"),
        Binding("e,backspace,delete,0", "erase", "Erase"),
        Binding("question_mark", "hint", "Hint"),
        Binding("p", "pause", "Pause"),
        Binding("ctrl+n,d", "new_game", "New"),
        Binding("up,k", "move(-1,0)", show=False),
        Binding("down,j", "move(1,0)", show=False),
        Binding("left,h", "move(0,-1)", show=False),
        Binding("right,l", "move(0,1)", show=False),
    ] + [Binding(str(d), f"digit({d})", show=False) for d in range(1, 10)]

    def __init__(self, difficulty: str | None) -> None:
        super().__init__()
        saved = None if difficulty else Game.load()
        self.game: Game = saved or Game.new(difficulty or "medium")
        self.resumed = saved is not None
        self.notes_mode = False
        self.paused = False
        self._status = ""

    # -- layout ------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="root"):
                yield Header()
                yield Board()
                yield ControlBar()
                yield NumPad()
                yield StatusLine()

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)
        self.set_interval(30.0, self.game.save)
        if self.resumed:
            self.status("Resumed your saved game.")
        else:
            self.status("Click a cell or use arrows · 1-9 to fill · n for notes")

    # -- helpers ----------------------------------------------------------- #
    @property
    def board(self) -> Board:
        return self.query_one(Board)

    def refresh_all(self) -> None:
        for w in (Header, Board, ControlBar, NumPad):
            self.query_one(w).refresh()

    def status(self, msg: str) -> None:
        self.query_one(StatusLine).update(msg)

    def _tick(self) -> None:
        if not self.paused and not self.game.solved() and not self.game.lost():
            self.game.elapsed += 1
            self.query_one(Header).refresh()

    def _check_end(self) -> None:
        g = self.game
        if g.solved():
            g.save()
            mins, secs = divmod(int(g.elapsed), 60)
            self.push_screen(
                EndScreen("🎉 Solved!", f"{g.difficulty.capitalize()} in {mins:02d}:{secs:02d}"
                          f" · {g.mistakes} mistakes · {g.hints} hints", False),
                self._start_new)
        elif g.lost():
            g.save()
            self.push_screen(EndScreen("✖ Game over", "Three mistakes.", False), self._start_new)

    def _start_new(self, diff: str | None) -> None:
        if not diff:
            return
        self.game = Game.new(diff)
        self.paused = False
        self.notes_mode = False
        self.board.sel = (4, 4)
        self.game.save()
        self.status(f"New {diff} game. Good luck!")
        self.refresh_all()

    # -- input ------------------------------------------------------------- #
    def input_digit(self, d: int) -> None:
        if self.paused or self.game.lost() or self.game.solved():
            return
        r, c = self.board.sel
        g = self.game
        if g.is_given(r, c):
            self.status("That's a given cell.")
            return
        if self.notes_mode:
            if g.values[r][c]:
                self.status("Erase the value first to add notes.")
            else:
                g.toggle_note(r, c, d)
        else:
            if g.place(r, c, d):
                self.status(f"✖ {d} doesn't go there.  Mistakes: {g.mistakes}/{MAX_MISTAKES}")
            else:
                self.status("")
        self.refresh_all()
        self._check_end()

    def run_control(self, key: str) -> None:
        {"undo": self.action_undo, "erase": self.action_erase, "notes": self.action_toggle_notes,
         "hint": self.action_hint, "new": self.action_new_game}[key]()

    # -- actions ----------------------------------------------------------- #
    def action_digit(self, d: int) -> None:
        self.input_digit(d)

    def action_move(self, dr: int, dc: int) -> None:
        if self.paused:
            return
        r, c = self.board.sel
        self.board.sel = ((r + dr) % 9, (c + dc) % 9)
        self.refresh_all()

    def action_toggle_notes(self) -> None:
        self.notes_mode = not self.notes_mode
        self.status("Notes ON — digits go in as pencil marks." if self.notes_mode else "Notes OFF")
        self.refresh_all()

    def action_undo(self) -> None:
        if self.paused:
            return
        self.game.undo_move()
        self.refresh_all()

    def action_erase(self) -> None:
        if self.paused:
            return
        r, c = self.board.sel
        self.game.erase(r, c)
        self.refresh_all()

    def action_hint(self) -> None:
        if self.paused or self.game.lost():
            return
        r, c = self.board.sel
        res = self.game.hint(r, c)
        if res:
            self.board.sel = res
            self.status(f"Hint: {self.game.values[res[0]][res[1]]} goes at row {res[0]+1}, col {res[1]+1}.")
        self.refresh_all()
        self._check_end()

    def action_pause(self) -> None:
        if self.game.lost() or self.game.solved():
            return
        self.paused = not self.paused
        self.status("Paused." if self.paused else "")
        self.refresh_all()

    def action_new_game(self) -> None:
        self.push_screen(EndScreen("Start a new game?", "Current game will be lost.", True),
                         self._start_new)

    def action_quit(self) -> None:
        self.game.save()
        self.exit()


def main() -> None:
    diff = sys.argv[1].lower() if len(sys.argv) > 1 else None
    if diff and diff not in DIFFICULTIES:
        print(f"Unknown difficulty '{diff}'. Choose from: {', '.join(DIFFICULTIES)}")
        sys.exit(1)
    SudokuApp(diff).run()


if __name__ == "__main__":
    main()
