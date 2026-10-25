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

### Sudoku — `sudoku.py`

A sudoku.com-style Sudoku with notes, hints, undo, a timer, and a 3-mistake limit.

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

## Adding a new game

1. Drop the game in the repo root as `<name>.py` with a `#!/usr/bin/env python3`
   shebang (and `chmod +x <name>.py`).
2. Add any new third-party packages to `requirements.txt`.
3. Add a section under **Games** above with how to launch it and its controls.
