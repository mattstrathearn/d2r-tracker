"""Exercise the parts of the vision layer that don't need a live game."""
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
import d2r_vision as v

fails = []


def check(label, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {got!r}")
    if not ok:
        fails.append(f"{label}: got {got!r}, want {want!r}")


print("VISION_AVAILABLE:", v.VISION_AVAILABLE, "| missing:", v.MISSING_DEPS)
print()

# --- item matching against the real 740-name vocabulary -------------------
sys.argv = ["x"]
import re
src = open(os.path.join(ROOT, "revised_d2r_mf_tracker_v10.py"), encoding="utf-8").read()
items = re.findall(r'^\s*"([^"]+\[(?:unique|set|misc)[^\]]*\])",', src, re.M)
print(f"parsed {len(items)} items from the tracker\n")
index = v.build_item_index(items)

print("--- exact names ---")
check("Shako", v.match_item("Harlequin Crest", index)[0], "Harlequin Crest [unique #248]")
check("Occy", v.match_item("The Oculus", index)[0], "The Oculus [unique #284]")

print("\n--- OCR-mangled names (the realistic case) ---")
for garbled, expect_contains in [
    ("Harleouin Crest", "Harlequin Crest"),
    ("HARLEQUIN CREST", "Harlequin Crest"),
    ("Tha Oculus", "The Oculus"),
    ("Stone of J0rdan", "The Stone of Jordan"),
    ("Vex Rune", "Vex Rune"),
    ("Tal Rasha's Adjudication", "Tal Rasha"),
]:
    name, score = v.match_item(garbled, index)
    ok = name is not None and expect_contains.lower() in name.lower()
    print(f"{'PASS' if ok else 'FAIL'}  {garbled!r} -> {name!r} ({score:.0f}%)")
    if not ok:
        fails.append(f"garbled {garbled!r} -> {name!r}")

print("\n--- junk must NOT match ---")
for junk in ["", "xxxxxxx", "43 21 %%%"]:
    name, score = v.match_item(junk, index)
    ok = name is None
    print(f"{'PASS' if ok else 'FAIL'}  {junk!r} -> {name!r} ({score:.0f}%)")
    if not ok:
        fails.append(f"junk {junk!r} matched {name!r}")

# --- area name -> run type ------------------------------------------------
print("\n--- area name -> run type ---")
RUN_TYPES = re.search(r"RUN_TYPES = \[(.*?)\n\]", src, re.S).group(1)
run_types = re.findall(r'"([^"]+)"', RUN_TYPES)
print(f"parsed {len(run_types)} run types")

for area_text, difficulty, want in [
    ("Durance of Hate Level 3", "Hell", "Hell - Mephisto"),
    ("durance of hate level 3", "NM", "NM - Mephisto"),
    ("Tower Cellar Level 5", "Hell", "Hell - Countess"),
    ("Chaos Sanctuary", "Hell", "Hell - Chaos Sanctuary"),
    ("Throne of Destruction", "Hell", "Hell - Baal"),
    ("Ancient Tunnels", "Hell", "Hell - Ancient Tunnels"),
    ("Pit Level 2", "Hell", "Hell - The Pit"),
    # OCR noise
    ("Duranee of Hate Leve1 3", "Hell", "Hell - Mephisto"),
    ("TRAVINCAL", "Hell", "Hell - Travincal"),
]:
    area, suffix = v.match_area(area_text)
    got = v.resolve_run_type(suffix, difficulty, run_types) if suffix else None
    check(f"{area_text!r} @ {difficulty}", got, want)

print("\n--- town must yield no run ---")
for town in ["Rogue Encampment", "Harrogath", "Lut Gholein"]:
    area, suffix = v.match_area(town)
    ok = area is not None and suffix is None
    print(f"{'PASS' if ok else 'FAIL'}  {town!r} -> area={area!r} suffix={suffix!r}")
    if not ok:
        fails.append(f"town {town!r} -> {area!r}/{suffix!r}")

# --- colour masking -------------------------------------------------------
print("\n--- colour masking ---")
img = np.zeros((20, 60, 3), dtype=np.uint8)
img[:, :] = (40, 30, 90)                      # background
img[5:15, 5:30] = v.QUALITY_COLORS["unique"]  # gold text
img[5:15, 35:55] = v.QUALITY_COLORS["magic"]  # blue text, should be dropped

masked = v.mask_colors(img, [v.QUALITY_COLORS["unique"]], tolerance=60, upscale=1)
arr = np.array(masked)
gold_kept = (arr[5:15, 5:30] == 0).all()
blue_dropped = (arr[5:15, 35:55] == 255).all()
bg_dropped = (arr[0:4, :] == 255).all()
check("gold text kept (black)", bool(gold_kept), True)
check("blue text dropped", bool(blue_dropped), True)
check("background dropped", bool(bg_dropped), True)

none_result = v.mask_colors(np.full((10, 10, 3), 7, dtype=np.uint8), [v.QUALITY_COLORS["set"]])
check("no matching colour -> None", none_result, None)

# --- brightness / region helpers -----------------------------------------
print("\n--- brightness + regions ---")
check("black frame brightness", v.mean_brightness(np.zeros((10, 10, 3), np.uint8)), 0.0)
check("white frame brightness", v.mean_brightness(np.full((10, 10, 3), 255, np.uint8)), 255.0)
check("tuple region", v.normalize_region((1, 2, 3, 4)),
      {"left": 1, "top": 2, "width": 3, "height": 4})
check("x/y/w/h dict", v.normalize_region({"x": 1, "y": 2, "w": 3, "h": 4}),
      {"left": 1, "top": 2, "width": 3, "height": 4})
check("zero-size region", v.normalize_region({"left": 0, "top": 0, "width": 0, "height": 5}), None)
check("None region", v.normalize_region(None), None)
check("garbage region", v.normalize_region({"left": "a"}), None)
check("strip_suffix", v.strip_suffix("Harlequin Crest [unique #248]"), "Harlequin Crest")

print("\n" + "=" * 60)
if fails:
    print(f"{len(fails)} FAILURE(S):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL CHECKS PASSED")
