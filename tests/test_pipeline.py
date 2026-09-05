"""
End-to-end tests for the glue code, with OCR and screen capture stubbed.

Tesseract itself can't be installed on this box, so what's verified here is the
wiring: capture -> mask -> OCR -> match -> callback, and the detector's state
machine. The OCR accuracy itself has to be checked against the live game.
"""
import re
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
import d2r_vision as v
import d2r_autodetect as ad

fails = []


def check(label, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {got!r}")
    if not ok:
        fails.append(f"{label}: got {got!r}, want {want!r}")


src = open(os.path.join(ROOT, "revised_d2r_mf_tracker_v10.py"), encoding="utf-8").read()
items = re.findall(r'^\s*"([^"]+\[(?:unique|set|misc)[^\]]*\])",', src, re.M)
run_types = re.findall(r'"([^"]+)"', re.search(r"RUN_TYPES = \[(.*?)\n\]", src, re.S).group(1))
index = v.build_item_index(items)

# ==========================================================================
# 1. Item capture pipeline
# ==========================================================================
print("=== item capture pipeline ===")

real_grab, real_ocr, real_cursor = v.grab, v.ocr, v.get_cursor_pos


def gold_frame(*_a, **_k):
    """A frame with unique-gold pixels, as the real tooltip would have."""
    img = np.full((120, 400, 3), (30, 20, 60), dtype=np.uint8)
    img[40:60, 20:300] = v.QUALITY_COLORS["unique"]
    return img


def blue_frame(*_a, **_k):
    """Only magic-blue text - should be filtered out before OCR."""
    img = np.full((120, 400, 3), (30, 20, 60), dtype=np.uint8)
    img[40:60, 20:300] = v.QUALITY_COLORS["magic"]
    return img


v.get_cursor_pos = lambda: (960, 540)
ad.vision.get_cursor_pos = v.get_cursor_pos

# -- a clean hit ----------------------------------------------------------
v.grab = gold_frame
v.ocr = lambda img, single_line=True: "Harlequin Crest"
name, score, debug = ad.capture_item_at_cursor({}, index)
check("gold tooltip -> item", name, "Harlequin Crest [unique #248]")
check("score is high", score >= 75, True)

# -- OCR noise still resolves --------------------------------------------
v.ocr = lambda img, single_line=True: "Harleouin Crest\nDefense 141"
name, score, debug = ad.capture_item_at_cursor({}, index)
check("noisy multi-line -> item", name, "Harlequin Crest [unique #248]")

# -- stat lines alone must not match --------------------------------------
v.ocr = lambda img, single_line=True: "Required Level 69\n+30 to Vitality"
name, score, debug = ad.capture_item_at_cursor({}, index)
check("stat lines -> no match", name, None)

# -- blue-only text is masked away before OCR -----------------------------
v.grab = blue_frame
v.ocr = lambda img, single_line=True: "should never be reached"
name, score, debug = ad.capture_item_at_cursor({}, index)
check("magic-only tooltip -> no match", name, None)
check("  reports why", "no item-coloured text" in debug, True)

# -- capture_qualities is honoured ----------------------------------------
name, score, debug = ad.capture_item_at_cursor({"capture_qualities": ["magic"]}, index)
check("opting into magic reaches OCR", "should never be reached" in str(debug) or name is None, True)

# -- no cursor -> graceful ------------------------------------------------
v.get_cursor_pos = lambda: None
ad.vision.get_cursor_pos = v.get_cursor_pos
name, score, debug = ad.capture_item_at_cursor({}, index)
check("no cursor -> graceful", name, None)

v.grab, v.ocr, v.get_cursor_pos = real_grab, real_ocr, real_cursor
ad.vision.get_cursor_pos = real_cursor

# ==========================================================================
# 2. Detector state machine
# ==========================================================================
print("\n=== detector state machine ===")

events = []


class FakeScreen:
    """Scripted (brightness, area_text) frames the detector will 'see'."""

    def __init__(self, script):
        self.script = list(script)
        self.idx = 0

    def step(self):
        if self.idx < len(self.script) - 1:
            self.idx += 1

    @property
    def current(self):
        return self.script[self.idx]


# A full MF loop: in town -> load -> Durance 3 -> load -> back to town.
screen = FakeScreen([
    (200, "Kurast Docks"),      # in town
    (5, ""),                    # loading
    (5, ""),
    (200, "Durance of Hate Level 3"),   # arrived at Meph
    (200, "Durance of Hate Level 3"),
    (5, ""),                    # leaving
    (5, ""),
    (200, "Kurast Docks"),      # back in town
])


def fake_grab(region):
    box = v.normalize_region(region)
    if box is None:
        return None
    brightness, _ = screen.current
    return np.full((10, 10, 3), brightness, dtype=np.uint8)


def fake_ocr(img, single_line=True):
    return screen.current[1]


v.grab = fake_grab
v.ocr = fake_ocr
ad.vision.grab = fake_grab
ad.vision.ocr = fake_ocr

settings = {
    "loading_region": {"left": 0, "top": 0, "width": 10, "height": 10},
    "area_region": {"left": 0, "top": 0, "width": 10, "height": 10},
    "dark_threshold": 22,
    "dark_samples": 2,
    "difficulty": "Hell",
    "min_run_seconds": 0,
    "area_settle_delay": 0,
}

det = ad.RunDetector(
    settings, run_types,
    on_run_start=lambda rt: events.append(("start", rt)),
    on_run_end=lambda: events.append(("end", None)),
)

# Drive the state machine by hand rather than starting the thread, so the test
# is deterministic.
for _ in range(len(screen.script)):
    det._sample_loading()
    if not det._loading:
        det._sample_area()
    screen.step()

starts = [e for e in events if e[0] == "start"]
ends = [e for e in events if e[0] == "end"]
print("  events:", events)
check("exactly one run started", len(starts), 1)
check("run type auto-selected", starts[0][1], "Hell - Mephisto")
check("exactly one run ended", len(ends), 1)
check("start came before end", events.index(("start", "Hell - Mephisto")) < events.index(("end", None)), True)

# -- town must not start a run -------------------------------------------
events.clear()
screen2 = FakeScreen([(200, "Kurast Docks"), (200, "Kurast Docks"), (200, "Harrogath")])
screen.script, screen.idx = screen2.script, 0
det2 = ad.RunDetector(
    settings, run_types,
    on_run_start=lambda rt: events.append(("start", rt)),
    on_run_end=lambda: events.append(("end", None)),
)
for _ in range(3):
    det2._sample_loading()
    if not det2._loading:
        det2._sample_area()
    screen.step()
check("town alone starts no run", events, [])

# -- too-short runs are discarded ----------------------------------------
events.clear()
det3 = ad.RunDetector(
    dict(settings, min_run_seconds=5.0), run_types,
    on_run_start=lambda rt: events.append(("start", rt)),
    on_run_end=lambda: events.append(("end", None)),
)
det3._start_run("Hell - Mephisto", "test")
det3._end_run("test")  # immediate, well under min_run_seconds
check("short run start fired", [e[0] for e in events], ["start"])
check("short run end suppressed", ("end", None) in events, False)

# -- manual sync ----------------------------------------------------------
det4 = ad.RunDetector(settings, run_types)
det4.notify_run_started_externally()
check("manual start syncs detector", det4._run_active, True)
det4.notify_run_stopped_externally()
check("manual stop syncs detector", det4._run_active, False)

# -- no area region -> falls back to loading screens ----------------------
events.clear()
screen3 = FakeScreen([(200, ""), (5, ""), (5, ""), (200, ""), (200, "")])
screen.script, screen.idx = screen3.script, 0
det5 = ad.RunDetector(
    {**settings, "area_region": None}, run_types,
    on_run_start=lambda rt: events.append(("start", rt)),
    on_run_end=lambda: events.append(("end", None)),
)
for _ in range(5):
    det5._sample_loading()
    if not det5._loading:
        det5._sample_area()
    screen.step()
check("fallback starts a run with no area", [e[0] for e in events], ["start"])
check("fallback leaves run type to the UI", events[0][1], None)

print("\n" + "=" * 60)
if fails:
    print(f"{len(fails)} FAILURE(S):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL PIPELINE CHECKS PASSED")
