#!/usr/bin/env python3
"""
Automatic run start/stop detection for the D2R MF tracker.

Two signals drive this:

  1. Loading screens. Every run boundary in D2R is a loading screen, and a
     loading screen is just a dark frame. Watching a small region for the
     fade-to-black is cheap and does not need OCR, so it runs at a few hertz
     and provides the precise timing edges.

  2. The automap area name. OCR'ing it tells us *which* area we landed in, so
     the run type can be selected automatically and town time is not counted
     as a run.

Callbacks fire on the detector thread. The caller is responsible for marshalling
them onto the Tk main loop.
"""

import threading
import time

import d2r_vision as vision


class RunDetector:
    """Watches the screen and calls back when a run starts or stops."""

    def __init__(
        self,
        settings,
        run_types,
        on_run_start=None,
        on_run_end=None,
        on_status=None,
    ):
        self.settings = dict(settings or {})
        self.run_types = list(run_types)
        self.on_run_start = on_run_start
        self.on_run_end = on_run_end
        self.on_status = on_status

        self._thread = None
        self._stop = threading.Event()

        # Detector's own view of the world, independent of the tracker's state.
        self._loading = False
        self._dark_streak = 0
        self._bright_streak = 0
        self._run_active = False
        self._current_area = None
        self._area_misses = 0
        self._run_started_at = 0.0

    # -- lifecycle ---------------------------------------------------------
    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return True
        if not vision.VISION_AVAILABLE:
            self._status("Auto-detect unavailable: missing " + ", ".join(vision.MISSING_DEPS))
            return False
        if vision.normalize_region(self.settings.get("loading_region")) is None:
            self._status("Auto-detect needs a calibrated loading region")
            return False

        self._stop.clear()
        self._reset_state()
        self._thread = threading.Thread(target=self._loop, name="d2r-run-detector", daemon=True)
        self._thread.start()
        self._status("Auto-detect running")
        return True

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._status("Auto-detect stopped")

    def update_settings(self, settings):
        """Apply new calibration. Restarts the thread if it was running."""
        was_running = self.running
        if was_running:
            self.stop()
        self.settings = dict(settings or {})
        if was_running:
            self.start()

    def notify_run_stopped_externally(self):
        """Tell the detector the user stopped the run by hand, so it stays in sync."""
        self._run_active = False

    def notify_run_started_externally(self):
        self._run_active = True
        self._run_started_at = time.time()

    # -- internals ---------------------------------------------------------
    def _reset_state(self):
        self._loading = False
        self._dark_streak = 0
        self._bright_streak = 0
        self._run_active = False
        self._current_area = None
        self._area_misses = 0
        self._run_started_at = 0.0

    def _status(self, message):
        if self.on_status:
            try:
                self.on_status(message)
            except Exception:
                pass

    def _setting(self, key, default):
        value = self.settings.get(key, default)
        return default if value is None else value

    def _loop(self):
        poll = float(self._setting("poll_interval", 0.25))
        area_poll = float(self._setting("area_poll_interval", 1.5))
        last_area_check = 0.0

        while not self._stop.is_set():
            try:
                self._sample_loading()

                # Only read the area name while actually in a game.
                if not self._loading and time.time() - last_area_check >= area_poll:
                    last_area_check = time.time()
                    self._sample_area()
            except Exception as exc:  # never let the watcher thread die
                self._status(f"Auto-detect error: {exc}")

            self._stop.wait(poll)

    def _sample_loading(self):
        """Track the dark/bright edge that marks a loading screen."""
        threshold = float(self._setting("dark_threshold", 22))
        needed = int(self._setting("dark_samples", 2))

        frame = vision.grab(self.settings.get("loading_region"))
        brightness = vision.mean_brightness(frame)
        if brightness is None:
            return

        if brightness <= threshold:
            self._dark_streak += 1
            self._bright_streak = 0
        else:
            self._bright_streak += 1
            self._dark_streak = 0

        if not self._loading and self._dark_streak >= needed:
            self._loading = True
            self._on_loading_started()
        elif self._loading and self._bright_streak >= needed:
            self._loading = False
            self._on_loading_ended()

    def _on_loading_started(self):
        self._status("Loading screen")
        if self._run_active:
            self._end_run("left the area")

    def _on_loading_ended(self):
        self._status("In game")
        self._current_area = None
        self._area_misses = 0
        # The area name needs a moment to render after the load completes.
        settle = float(self._setting("area_settle_delay", 0.6))
        if settle > 0:
            self._stop.wait(settle)
        self._sample_area(first_after_load=True)

    def _sample_area(self, first_after_load=False):
        """OCR the automap area name and start/stop the run to match."""
        region = self.settings.get("area_region")
        if vision.normalize_region(region) is None:
            # No area region calibrated: fall back to treating every loaded
            # game as a run, using whatever run type is selected in the UI.
            if first_after_load and not self._run_active:
                self._start_run(None, "game loaded")
            return

        frame = vision.grab(region)
        tolerance = int(self._setting("area_tolerance", 90))
        masked = vision.mask_colors(frame, [vision.AREA_NAME_COLOR], tolerance=tolerance)
        text = vision.ocr(masked, single_line=True)
        area, run_suffix = vision.match_area(text, int(self._setting("area_min_score", 80)))

        if area is None:
            self._area_misses += 1
            # If the automap is off we will never read an area. After a few
            # misses following a load, fall back to plain loading-screen timing
            # so the timer still works.
            if (
                first_after_load or self._area_misses >= int(self._setting("area_miss_limit", 3))
            ) and not self._run_active and bool(self._setting("fallback_without_area", True)):
                self._start_run(None, "no area read, using selected run type")
            return

        self._area_misses = 0
        if area == self._current_area:
            return
        self._current_area = area
        self._status(f"Area: {area.title()}")

        if run_suffix:
            run_type = vision.resolve_run_type(
                run_suffix, self._setting("difficulty", "Hell"), self.run_types
            )
            if not self._run_active:
                self._start_run(run_type, f"entered {area.title()}")
            elif bool(self._setting("restart_on_area_change", False)):
                self._end_run("changed area")
                self._start_run(run_type, f"entered {area.title()}")
        elif self._run_active and bool(self._setting("stop_in_town", True)):
            self._end_run(f"entered {area.title()}")

    def _start_run(self, run_type, reason):
        if self._run_active:
            return
        self._run_active = True
        self._run_started_at = time.time()
        self._status(f"Run started ({reason})")
        if self.on_run_start:
            try:
                self.on_run_start(run_type)
            except Exception:
                pass

    def _end_run(self, reason):
        if not self._run_active:
            return
        min_seconds = float(self._setting("min_run_seconds", 3.0))
        if time.time() - self._run_started_at < min_seconds:
            # Too short to be a real run - almost always a misread, so drop the
            # detector's state without telling the tracker to log anything.
            self._run_active = False
            self._status("Discarded a too-short run")
            return
        self._run_active = False
        self._status(f"Run ended ({reason})")
        if self.on_run_end:
            try:
                self.on_run_end()
            except Exception:
                pass


def capture_item_at_cursor(settings, item_index):
    """
    Grab the tooltip under the cursor and resolve it to a known item.

    Returns (item_name, score, debug_text). item_name is None if nothing
    matched, in which case debug_text holds whatever OCR did read - which is
    what makes calibration tractable.
    """
    if not vision.VISION_AVAILABLE:
        return None, 0, "missing: " + ", ".join(vision.MISSING_DEPS)

    settings = settings or {}
    region = vision.region_at_cursor(
        int(settings.get("tooltip_width", 460)),
        int(settings.get("tooltip_height", 130)),
        int(settings.get("tooltip_offset_x", 0)),
        int(settings.get("tooltip_offset_y", 0)),
    )
    if region is None:
        return None, 0, "could not read cursor position"

    frame = vision.grab(region)
    if frame is None:
        return None, 0, "capture failed"

    qualities = settings.get("capture_qualities") or list(vision.DEFAULT_CAPTURE_QUALITIES)
    colors = [vision.QUALITY_COLORS[q] for q in qualities if q in vision.QUALITY_COLORS]
    if not colors:
        colors = [vision.QUALITY_COLORS["unique"], vision.QUALITY_COLORS["set"]]

    masked = vision.mask_colors(frame, colors, tolerance=int(settings.get("tooltip_tolerance", 60)))
    if masked is None:
        return None, 0, "no item-coloured text in capture box"

    lines = vision.ocr_lines(masked)
    if not lines:
        return None, 0, "no text read"

    min_score = int(settings.get("item_min_score", vision.DEFAULT_ITEM_SCORE))
    matches = vision.match_items_in_lines(lines, item_index, min_score)
    if not matches:
        return None, 0, " / ".join(lines[:3])

    name, score = matches[0]
    return name, score, " / ".join(lines[:3])
