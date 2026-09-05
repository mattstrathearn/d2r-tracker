# D2R MF Run Tracker

A fixed-size, borderless overlay for tracking Diablo II: Resurrected magic-find runs —
run timing, run type, player count (P1–P8), and item drops — backed by a local SQLite
database.

## Features

- Borderless overlay main window plus a separate borderless stats window
- Run timer with start/stop, run type selection, and P1–P8 player-count tracking
- Item entry with autocomplete over a baked-in unique/set/misc item list
- **Automatic run detection** — starts and stops the timer off loading screens and
  the automap area name, and picks the run type for you
- **Item capture under the cursor** — hover a drop, press a key, and it is logged
- Per-run drop logging and aggregate stats
- Local SQLite storage (`d2r_mf_tracker.db`), with a file picker to choose or move the database

## Hotkeys

| Key | Action |
| --- | --- |
| `Alt+1` | Start / stop run |
| `Alt+2` | Focus item entry |
| `Alt+3` | Open stats window |
| `Alt+4` | Capture the item under the cursor |

Global (out-of-focus) hotkeys require the optional [`keyboard`](https://pypi.org/project/keyboard/)
package. Without it the app falls back to in-window bindings only.

## Requirements

- Python 3.x with `tkinter` (bundled on Windows/macOS; on Debian/Ubuntu install `python3-tk`)
- Optional extras in [requirements.txt](requirements.txt) — `keyboard` for global
  hotkeys, and `mss` / `numpy` / `Pillow` / `pytesseract` / `rapidfuzz` for the
  screen-reading features

The core tracker needs only the standard library. Every optional dependency
degrades gracefully: without them the auto-detect controls report what is
missing and manual entry keeps working.

```bash
pip install -r requirements.txt
```

`pytesseract` is only a wrapper — it also needs the Tesseract binary:

- **Windows:** <https://github.com/UB-Mannheim/tesseract/wiki>
- **Debian/Ubuntu:** `sudo apt install tesseract-ocr`

If Tesseract is not on `PATH`, point the tracker at it with the **Locate…**
button in the Auto-Detect settings window.

## Running

```bash
python3 revised_d2r_mf_tracker_v10.py
```

## Auto-detect setup

Everything here reads your own screen. Nothing touches the game process, its
memory, or its network traffic.

D2R must be running in **windowed** or **borderless windowed** mode —
fullscreen-exclusive breaks both screen capture and the always-on-top overlay.

Open **⚙ Calibrate…** on the auto-detect bar and set two regions:

1. **Loading-screen probe** — a small box somewhere that is bright during play
   and black during a loading screen. The middle of the screen works well. This
   is what drives the timer, and it needs no OCR.
2. **Automap area name** — the area name the automap prints at the top of the
   screen. This is what selects the run type and keeps town time out of your
   run times. Leave it unset to time runs purely off loading screens, using
   whatever run type is selected in the dropdown.

Then pick your **difficulty** — the on-screen area name doesn't include it, so
"Durance of Hate Level 3" becomes `Hell - Mephisto` or `NM - Mephisto` depending
on this setting.

Use **🔍 Test area-name OCR** to check what the tracker is actually reading
before you start a session. If runs are missed or town triggers a run, adjust
the **Loading-screen darkness** slider.

### Capturing items

Hover the item — on the ground or in your inventory — and press `Alt+4`. The
tracker grabs a box at the cursor, keeps only the unique-gold / set-green /
rune-orange pixels, OCRs what's left, and fuzzy-matches it against the built-in
item list. The status line shows what it captured, or what it read if nothing
matched, which is what makes the capture box easy to tune.

Because the item list is a closed vocabulary of ~740 names, matching recovers
the right item from fairly mangled OCR. Note that a few entries in that list
differ from what the game renders (`Gorerider` vs "Gore Rider", `Wartraveler`
vs "War Traveler", `Deaths's Web` vs "Death's Web"); fuzzy matching absorbs
this, but those drops are logged under the list's spelling.

## Tests

```bash
python3 tests/test_matching.py    # item + area matching against the real item list
python3 tests/test_pipeline.py    # capture pipeline and run-detector state machine
```

These cover the logic that can be checked without a running game: fuzzy
matching, colour masking, area→run-type mapping, and the detector's state
machine (OCR and screen capture are stubbed). They need the optional
dependencies installed, but not Tesseract.

### Limitations

- Regions are resolution- and UI-scale-dependent, so recalibrate if you change
  either.
- Area-name detection needs the automap on.
- OCR accuracy against the live game has not been verified by the author on
  Windows; expect a tuning pass on the darkness threshold and capture box.

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
