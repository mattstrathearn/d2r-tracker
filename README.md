# D2R MF Run Tracker

A fixed-size, borderless overlay for tracking Diablo II: Resurrected magic-find runs —
run timing, run type, player count (P1–P8), and item drops — backed by a local SQLite
database.

## Features

- Borderless overlay main window plus a separate borderless stats window
- Run timer with start/stop, run type selection, and P1–P8 player-count tracking
- Item entry with autocomplete over a baked-in unique/set/misc item list
- Per-run drop logging and aggregate stats
- Local SQLite storage (`d2r_mf_tracker.db`), with a file picker to choose or move the database

## Hotkeys

| Key | Action |
| --- | --- |
| `Alt+1` | Start / stop run |
| `Alt+2` | Focus item entry |
| `Alt+3` | Open stats window |

Global (out-of-focus) hotkeys require the optional [`keyboard`](https://pypi.org/project/keyboard/)
package. Without it the app falls back to in-window bindings only.

## Requirements

- Python 3.x with `tkinter` (bundled on Windows/macOS; on Debian/Ubuntu install `python3-tk`)
- Optional: `keyboard` for global hotkeys — `pip install keyboard`

Everything else (`json`, `os`, `sqlite3`, `time`, `datetime`) is standard library.

## Running

```bash
python3 revised_d2r_mf_tracker_v10.py
```

## Building a Windows executable

A PyInstaller spec is included:

```bash
pyinstaller revised_d2r_mf_tracker_v10.spec
```

The result lands in `dist/` as a windowed (no console), UPX-compressed single binary.

## Data locations

- **Database:** `d2r_mf_tracker.db` in the working directory by default; relocatable from the UI
- **Config:** `~/.d2r_mf_tracker_config.json`

Both are gitignored.
