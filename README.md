# Terminal Games

A collection of games written in Python that run right in your terminal.

## Requirements

- **Python 3.9+** (`python3 --version` to check)
- A modern terminal with Unicode and true-color support (iTerm2, Windows Terminal,
  GNOME Terminal, Kitty, WezTerm, VS Code's terminal, etc.). Mouse support is used
  where available.
- Dependencies listed in [`requirements.txt`](requirements.txt).

## Setup

It's best to use a virtual environment so the game dependencies stay separate from
your system Python:

```bash
git clone https://github.com/QB3L/terminal_games.git
cd terminal_games

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Running a game

Each game is a single, self-contained Python file in the repository root. Run it
with Python:

```bash
python3 <game>.py
```

On macOS/Linux the files are executable, so `./<game>.py` works too.

Most games quit with `q`. If a game ever gets stuck, `Ctrl+C` will exit.

## Games

| Game   | File        | Python | Packages  | Min. terminal size | Save file              |
| ------ | ----------- | ------ | --------- | ------------------ | ---------------------- |
| Sudoku | `sudoku.py` | 3.9+   | `textual` | 80 × 48            | `~/.sudoku_tui.json`   |
| 2048   | `2048.py`   | 3.9+   | `textual` | 56 × 24            | `~/.2048_tui.json`     |
| Snake  | `snake.py`  | 3.9+   | `textual` | 70 × 30            | `~/.snake_tui.json`    |
| Tetris | `tetris.py` | 3.9+   | `textual` | 68 × 32            | `~/.tetris_tui.json`   |

`pip install -r requirements.txt` covers every game. To install for a single
game only, install the packages in its row (for example, `pip install textual`).

### Sudoku — `sudoku.py`

A sudoku.com-style Sudoku with notes, hints, undo, a timer, and a 3-mistake limit.

**Requires:** Python 3.9+, `textual`, a terminal at least 80 × 48. Mouse optional.

```bash
python3 sudoku.py                # resume your saved game, or start a medium one
python3 sudoku.py easy           # start a new game: easy | medium | hard | expert
```

| Action                | Keys                               | Mouse                  |
| --------------------- | ---------------------------------- | ---------------------- |
| Select a cell         | arrows or `h` `j` `k` `l`          | click a cell           |
| Place a digit / note  | `1`–`9`                            | click the number pad   |
| Toggle Notes mode     | `n`                                | click **Notes**        |
| Erase                 | `e`, `Backspace`, `Delete`, `0`    | click **Erase**        |
| Undo                  | `u` or `Ctrl+Z`                    | click **Undo**         |
| Hint                  | `?`                                | click **Hint**         |
| Pause                 | `p`                                | click the pause icon   |
| New game / difficulty | `Ctrl+N` or `d`                    | click **New**          |
| Quit (auto-saves)     | `q`                                |                        |

Progress is saved to `~/.sudoku_tui.json` and resumed the next time you launch
without a difficulty argument.

### 2048 — `2048.py`

Slide tiles to merge matching numbers and reach 2048, then keep going.

**Requires:** Python 3.9+, `textual`, a terminal at least 56 × 24.

```bash
python3 2048.py
```

| Action    | Keys                           |
| --------- | ------------------------------ |
| Slide     | arrows, `h` `j` `k` `l`, or `w` `a` `s` `d` |
| Undo      | `u`                            |
| New game  | `r`                            |
| Quit      | `q`                            |

Your best score is saved to `~/.2048_tui.json`.

### Snake — `snake.py`

Classic Snake. Speed goes up every few apples you eat.

**Requires:** Python 3.9+, `textual`, a terminal at least 70 × 30.

```bash
python3 snake.py            # solid walls: hitting one ends the game
python3 snake.py --wrap     # wrap-around walls: exit one side, come back on the other
```

| Action    | Keys                                        |
| --------- | ------------------------------------------- |
| Steer     | arrows, `h` `j` `k` `l`, or `w` `a` `s` `d` (any steer key starts the game) |
| Pause     | `p`                                         |
| Restart   | `r`                                         |
| Quit      | `q`                                         |

Your best score is saved to `~/.snake_tui.json`.

### Tetris — `tetris.py`

Tetris with a ghost piece, hold, a three-piece preview, and levels that speed up
every 10 lines.

**Requires:** Python 3.9+, `textual`, a terminal at least 68 × 32.

```bash
python3 tetris.py
```

| Action            | Keys                       |
| ----------------- | -------------------------- |
| Move left / right | `←` `→`, `a` `d`, or `h` `l` |
| Soft drop         | `↓`, `s`, or `j`           |
| Hard drop         | `Space`                    |
| Rotate clockwise  | `↑`, `x`, or `k`           |
| Rotate counter-cw | `z`                        |
| Hold piece        | `c`                        |
| Pause             | `p`                        |
| Restart           | `r`                        |
| Quit              | `q`                        |

Your best score is saved to `~/.tetris_tui.json`.

## Adding a new game

1. Drop the game in the repo root as `<name>.py` with a `#!/usr/bin/env python3`
   shebang (and `chmod +x <name>.py`).
2. Add any new third-party packages to `requirements.txt`.
3. Add a row to the **Games** table with its requirements, and a section with how
   to launch it and its controls.
