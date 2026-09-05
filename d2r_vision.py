#!/usr/bin/env python3
"""
Screen-reading helpers for the D2R MF tracker.

Everything here is passive: it screenshots regions of your own display and reads
them. Nothing touches the game process, its memory, or its network traffic.

All of the heavy dependencies are optional. If they are missing the module still
imports cleanly and `VISION_AVAILABLE` is False, so the tracker can degrade to
manual entry instead of failing to start.
"""

import re
import threading

MISSING_DEPS = []

try:
    import numpy as np
except ImportError:
    np = None
    MISSING_DEPS.append("numpy")

try:
    import mss
except ImportError:
    mss = None
    MISSING_DEPS.append("mss")

try:
    from PIL import Image
except ImportError:
    Image = None
    MISSING_DEPS.append("Pillow")

try:
    import pytesseract
except ImportError:
    pytesseract = None
    MISSING_DEPS.append("pytesseract")

try:
    from rapidfuzz import fuzz, process as fuzz_process
except ImportError:
    fuzz = None
    fuzz_process = None
    MISSING_DEPS.append("rapidfuzz")

VISION_AVAILABLE = not MISSING_DEPS


# --------------------------------------------------------------------------
# Item quality colours
# --------------------------------------------------------------------------
# D2R renders item names in a fixed palette. Masking to just these colours
# throws away the background art before OCR ever sees it, which is the single
# biggest accuracy win available here.
QUALITY_COLORS = {
    "unique": (199, 179, 119),   # gold / tan
    "set": (0, 255, 0),          # green
    "rune": (255, 168, 0),       # orange
    "rare": (255, 255, 100),     # yellow
    "magic": (105, 105, 255),    # blue
    "crafted": (255, 168, 0),    # orange, same family as runes
}

# Sensible default for magic finding: the qualities worth logging as a drop.
DEFAULT_CAPTURE_QUALITIES = ("unique", "set", "rune")

# Area-name text in the automap header is an off-white/grey.
AREA_NAME_COLOR = (222, 222, 222)


# --------------------------------------------------------------------------
# Screen capture
# --------------------------------------------------------------------------
_thread_local = threading.local()


def _sct():
    """mss instances are not thread-safe, so keep one per thread."""
    if mss is None:
        raise RuntimeError("mss is not installed")
    inst = getattr(_thread_local, "sct", None)
    if inst is None:
        inst = mss.mss()
        _thread_local.sct = inst
    return inst


def normalize_region(region):
    """Accept a dict or a 4-tuple and return a {left, top, width, height} dict."""
    if region is None:
        return None
    if isinstance(region, dict):
        try:
            left = int(region.get("left", region.get("x", 0)))
            top = int(region.get("top", region.get("y", 0)))
            width = int(region.get("width", region.get("w", 0)))
            height = int(region.get("height", region.get("h", 0)))
        except (TypeError, ValueError):
            return None
    else:
        try:
            left, top, width, height = (int(v) for v in region)
        except (TypeError, ValueError):
            return None
    if width <= 0 or height <= 0:
        return None
    return {"left": left, "top": top, "width": width, "height": height}


def grab(region):
    """Screenshot a region and return it as an RGB uint8 array."""
    box = normalize_region(region)
    if box is None:
        return None
    raw = _sct().grab(box)
    arr = np.asarray(raw, dtype=np.uint8)  # BGRA from mss
    return arr[:, :, 2::-1]  # -> RGB


def get_cursor_pos():
    """Current mouse position in screen coordinates, or None."""
    try:
        import ctypes
        from ctypes import wintypes

        point = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return int(point.x), int(point.y)
    except (ImportError, AttributeError, OSError):
        return None


def region_at_cursor(width, height, offset_x=0, offset_y=0, cursor=None):
    """
    A capture box anchored near the cursor.

    D2R draws the item tooltip above and slightly right of the pointer, so the
    default anchor puts the cursor at the bottom-centre of the box. The offsets
    let calibration nudge that per-resolution.
    """
    pos = cursor or get_cursor_pos()
    if pos is None:
        return None
    x, y = pos
    return {
        "left": int(x - width // 2 + offset_x),
        "top": int(y - height + offset_y),
        "width": int(width),
        "height": int(height),
    }


# --------------------------------------------------------------------------
# Preprocessing
# --------------------------------------------------------------------------
def mask_colors(img, colors, tolerance=60, upscale=3):
    """
    Keep only pixels close to `colors`, and return a high-contrast black-on-white
    image ready for OCR.

    Tesseract is dramatically more accurate on clean black text on white than on
    coloured text over Diablo's background art, so this step matters more than
    any OCR tuning.
    """
    if img is None or np is None or Image is None:
        return None

    pixels = img.astype(np.int16)
    keep = np.zeros(img.shape[:2], dtype=bool)
    for color in colors:
        diff = np.abs(pixels - np.array(color, dtype=np.int16))
        keep |= (diff.max(axis=2) <= tolerance)

    if not keep.any():
        return None

    # Black text on a white field.
    out = np.where(keep, 0, 255).astype(np.uint8)
    pil = Image.fromarray(out, mode="L")
    if upscale and upscale > 1:
        pil = pil.resize((pil.width * upscale, pil.height * upscale), Image.LANCZOS)
    return pil


def mean_brightness(img):
    """Average luminance 0-255. Used for loading-screen detection."""
    if img is None or np is None:
        return None
    return float(img.astype(np.float32).mean())


# --------------------------------------------------------------------------
# OCR
# --------------------------------------------------------------------------
# psm 7 = one text line, psm 6 = a uniform block of text.
_OCR_SINGLE_LINE = "--psm 7"
_OCR_BLOCK = "--psm 6"


def set_tesseract_path(path):
    """Point pytesseract at a bundled or user-specified tesseract.exe."""
    if pytesseract and path:
        pytesseract.pytesseract.tesseract_cmd = path


def tesseract_available():
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr(pil_image, single_line=True):
    """Run OCR and return the raw text, or '' on any failure."""
    if pil_image is None or pytesseract is None:
        return ""
    config = _OCR_SINGLE_LINE if single_line else _OCR_BLOCK
    try:
        return pytesseract.image_to_string(pil_image, config=config).strip()
    except Exception:
        return ""


_CLEAN_RE = re.compile(r"[^A-Za-z0-9' \-]+")


def clean_text(text):
    """Strip OCR noise and collapse whitespace."""
    if not text:
        return ""
    text = _CLEAN_RE.sub(" ", text)
    return " ".join(text.split())


def ocr_lines(pil_image):
    """OCR a block and return cleaned non-empty lines."""
    raw = ocr(pil_image, single_line=False)
    lines = []
    for line in raw.splitlines():
        cleaned = clean_text(line)
        if len(cleaned) >= 3:
            lines.append(cleaned)
    return lines


# --------------------------------------------------------------------------
# Matching OCR output against a known vocabulary
# --------------------------------------------------------------------------
_SUFFIX_RE = re.compile(r"\s*\[[^\]]*\]\s*$")


def strip_suffix(name):
    """'Shako [unique #310]' -> 'Shako'"""
    return _SUFFIX_RE.sub("", name).strip()


def build_item_index(items):
    """
    Map bare item name -> original list entry.

    The tracker stores the full 'Name [unique #n]' string, but OCR only ever
    sees the bare name, so match on one and return the other.
    """
    index = {}
    for entry in items:
        bare = strip_suffix(entry)
        if bare:
            index.setdefault(bare.lower(), entry)
    return index


DEFAULT_ITEM_SCORE = 75

# fuzz.ratio, deliberately. WRatio folds in partial_token_set_ratio, which
# scores on a shared token alone - so "Stone of Jordan" matches "Burning
# Essence of Terror" at 86% purely on the word "of". Benchmarked over the full
# item list against OCR-style manglings, plain ratio was the only scorer with
# no false positives on tooltip noise like "Required Level 69".


def match_item(text, item_index, min_score=DEFAULT_ITEM_SCORE):
    """
    Resolve OCR text to a known item.

    The vocabulary is closed and small (~740 names), so fuzzy matching recovers
    the right entry even from fairly mangled OCR.
    """
    cleaned = clean_text(text)
    if not cleaned or fuzz_process is None or not item_index:
        return None, 0

    result = fuzz_process.extractOne(
        cleaned.lower(),
        item_index.keys(),
        scorer=fuzz.ratio,
    )
    if not result:
        return None, 0

    key, score = result[0], result[1]
    if score < min_score:
        return None, score
    return item_index[key], score


def match_items_in_lines(lines, item_index, min_score=DEFAULT_ITEM_SCORE):
    """Resolve several OCR lines, dropping duplicates and keeping the best score."""
    found = {}
    for line in lines:
        name, score = match_item(line, item_index, min_score)
        if name and score > found.get(name, 0):
            found[name] = score
    return sorted(found.items(), key=lambda kv: -kv[1])


# --------------------------------------------------------------------------
# Area name -> run type
# --------------------------------------------------------------------------
# The automap prints the actual game area, which is not what the run is called.
# This maps the area you land in to the run-type suffix used in RUN_TYPES.
# Difficulty is not shown on screen, so the caller supplies that prefix.
AREA_TO_RUN = {
    # Act 1
    "black marsh": "Countess",
    "forgotten tower": "Countess",
    "tower cellar level 1": "Countess",
    "tower cellar level 2": "Countess",
    "tower cellar level 3": "Countess",
    "tower cellar level 4": "Countess",
    "tower cellar level 5": "Countess",
    "outer cloister": "Andariel",
    "catacombs level 1": "Andariel",
    "catacombs level 2": "Andariel",
    "catacombs level 3": "Andariel",
    "catacombs level 4": "Andariel",
    "tamoe highland": "The Pit",
    "pit level 1": "The Pit",
    "pit level 2": "The Pit",
    "the pit level 1": "The Pit",
    "the pit level 2": "The Pit",
    "moo moo farm": "Cows",
    "the secret cow level": "Cows",
    # Act 2
    "lost city": "Ancient Tunnels",
    "ancient tunnels": "Ancient Tunnels",
    "rocky waste": "Stony Tomb",
    "stony tomb level 1": "Stony Tomb",
    "stony tomb level 2": "Stony Tomb",
    "far oasis": "Maggot Lair",
    "maggot lair level 1": "Maggot Lair",
    "maggot lair level 2": "Maggot Lair",
    "maggot lair level 3": "Maggot Lair",
    "canyon of the magi": "Summoner",
    "arcane sanctuary": "Arcane Sanctuary",
    # Act 3
    "spider forest": "Arachnid Lair",
    "spider cavern": "Arachnid Lair",
    "arachnid lair": "Arachnid Lair",
    "kurast bazaar": "Lower Kurast",
    "lower kurast": "Lower Kurast",
    "travincal": "Travincal",
    "durance of hate level 1": "Mephisto",
    "durance of hate level 2": "Mephisto",
    "durance of hate level 3": "Mephisto",
    # Act 4
    "river of flame": "River of Flame",
    "city of the damned": "River of Flame",
    "chaos sanctuary": "Chaos Sanctuary",
    # Act 5
    "bloody foothills": "Shenk / Eldritch",
    "frigid highlands": "Frigid Highlands",
    "nihlathak's temple": "Nihlathak",
    "nihlathaks temple": "Nihlathak",
    "halls of anguish": "Nihlathak",
    "halls of pain": "Nihlathak",
    "halls of vaught": "Nihlathak",
    "worldstone keep level 1": "Worldstone Keep",
    "worldstone keep level 2": "Worldstone Keep",
    "worldstone keep level 3": "Worldstone Keep",
    "throne of destruction": "Baal",
    "the worldstone chamber": "Baal",
    "worldstone chamber": "Baal",
}

# Areas that mean "not in a run" — town and the waypoint hubs you pass through.
TOWN_AREAS = {
    "rogue encampment",
    "lut gholein",
    "kurast docks",
    "the pandemonium fortress",
    "pandemonium fortress",
    "harrogath",
}

_AREA_INDEX = None


def _area_index():
    global _AREA_INDEX
    if _AREA_INDEX is None:
        _AREA_INDEX = list(AREA_TO_RUN.keys()) + list(TOWN_AREAS)
    return _AREA_INDEX


def match_area(text, min_score=80):
    """
    Resolve OCR'd area text to (area_name, run_suffix_or_None).

    A run suffix of None with a non-None area means you are somewhere known but
    not in a tracked run — town, typically.
    """
    cleaned = clean_text(text).lower()
    if not cleaned or fuzz_process is None:
        return None, None

    result = fuzz_process.extractOne(cleaned, _area_index(), scorer=fuzz.ratio)
    if not result or result[1] < min_score:
        return None, None

    area = result[0]
    return area, AREA_TO_RUN.get(area)


def resolve_run_type(run_suffix, difficulty, run_types):
    """
    Combine 'Countess' + 'Hell' into the matching 'Hell - Countess' entry.

    Falls back to any difficulty that has the area if the preferred one is not
    in the list.
    """
    if not run_suffix:
        return None
    target = f"{difficulty} - {run_suffix}".lower()
    for entry in run_types:
        if entry.lower() == target:
            return entry
    suffix = f"- {run_suffix}".lower()
    for entry in run_types:
        if entry.lower().endswith(suffix):
            return entry
    return None
