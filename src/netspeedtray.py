from __future__ import annotations

import ctypes
import json
import logging
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import simpledialog
import urllib.error
import urllib.request
import webbrowser
from datetime import date
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
from contextlib import contextmanager

try:
    import psutil
except ImportError:
    _MSG = "psutil is required.\n\nInstall it with:\n    pip install psutil"
    try:
        # 0x10 == MB_ICONERROR. The named constant is defined later in the
        # module, so the literal is used here (this runs at import time).
        ctypes.windll.user32.MessageBoxW(0, _MSG, "NetSpeedTray", 0x10)
    except Exception:
        print(_MSG, file=sys.stderr)
    raise SystemExit(1)

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "NetSpeedTray"
DEVELOPER_LINE = "Design and Developer: Ali Rahmani  (github.com/raali09)"
CONTACT_EMAIL = "rahmaniali09@gmail.com"
GITHUB_REPO = "raali09/NetSpeedTray"
GITHUB_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


def _read_version() -> str:
    """Read the application version from the VERSION file next to the source.

    Falls back to a sane default if the file is missing (e.g. running from a
    stripped checkout) so the app never fails to start over a version string.
    """
    candidates: List[str] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, "VERSION"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "VERSION"))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(os.path.join(script_dir, "..", "VERSION")))
    candidates.append(os.path.join(script_dir, "VERSION"))
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                ver = fh.read().strip()
            if ver:
                return ver
        except OSError:
            continue
    return "2.7.0"


APP_VERSION = _read_version()

IS_WINDOWS = sys.platform == "win32"
REFRESH_MS = 1000
TOOLTIP_DELAY_MS = 320
PROCESS_SCAN_INTERVAL = 5.0
ADAPTER_REFRESH_INTERVAL = 30.0
TOOLTIP_REFRESH_INTERVAL = 2.0
SYSTEM_REFRESH_MS = 3000
TOTALS_SAVE_INTERVAL = 30.0
EDGE_MARGIN = 10
SNAP_DISTANCE = 24
UPDATE_CHECK_DELAY_MS = 1800
CONFIG_SAVE_DEBOUNCE_MS = 700
PING_INTERVAL = 8.0
TASKBAR_PROBE_INTERVAL = 1.0
ZORDER_INTERVAL = 0.25
TASKBAR_CACHE_TTL = 2.0
# Adaptive z-order: run fast while the widget keeps losing z-order (e.g. right
# after a primary-display swap or while dragging), then throttle back to idle.
ZORDER_INTERVAL_ACTIVE = 0.15
ZORDER_INTERVAL_IDLE = 0.75
ZORDER_IDLE_GRACE = 5.0

BG_CARD = "#101820"
BG_SPEED_ROW = "#1B2733"
BORDER_COLOR = "#344354"
BORDER_SOFT = "#2A3745"
FG_DOWN = "#55C7F3"
FG_UP = "#F3AA55"
FG_CPU = "#B9C4D0"
FG_RAM = "#B9C4D0"
FG_LABEL = "#8290A0"
FG_TEXT = "#EAF0F6"
FG_ALERT = "#F27585"
FG_LOCK_FLASH = "#F0B45A"
FG_DIM = "#AAB5C1"
FG_CHECK = "#55C7F3"

BG_TRANSPARENT_KEY = "#0A0B0C"
FG_TRANSPARENT_KEY = "#0D0E0F"
SHADOW_COLOR = "#071019"
TEXT_SHADOW_OFFSET = 1


def _resolve_font_family() -> str:
    """Pick the best available UI font on this Windows install.

    "Segoe UI Variable Text" only ships with Windows 11; on Windows 10 we fall
    back to "Segoe UI", then "Tahoma" (present since XP), then tkinter's
    default so the widget never renders in an ugly bitmap font.

    Returns the Windows-11 font eagerly at import time (before a Tk root
    exists); the real selection is re-run lazily from ``SpeedWidget.__init__``
    once a root window is available, via :func:`refresh_font_family`.
    """
    candidates = ("Segoe UI Variable Text", "Segoe UI", "Tahoma",
                  "Microsoft YaHei UI", "DejaVu Sans")
    try:
        available = set(tkfont.families())
    except Exception:
        # No Tk root yet (import time). Return the best-guess; the widget
        # re-resolves after its root window is created.
        return candidates[0]
    for name in candidates:
        if name in available:
            return name
    return "TkDefaultFont"


def refresh_font_family() -> str:
    """Re-resolve the UI font once a Tk root exists and cache it globally."""
    global FONT_FAMILY, FONT_MENU
    FONT_FAMILY = _resolve_font_family()
    FONT_MENU = (FONT_FAMILY, 9)
    return FONT_FAMILY


FONT_FAMILY = _resolve_font_family()
FONT_SIZE_PROFILES = {
    "small": {"value": 8, "icon": 8, "system": 7},
    "medium": {"value": 10, "icon": 9, "system": 8},
    "large": {"value": 11, "icon": 10, "system": 8},
    "xlarge": {"value": 12, "icon": 11, "system": 9},
}
DEFAULT_FONT_SIZE = "medium"

FONT_MENU = (FONT_FAMILY, 9)
BG_HOVER = "#243343"

DEFAULT_OPACITY = 0.94
MIN_OPACITY = 0.20
MAX_OPACITY = 1.00
IDLE_FACTOR = 0.28
IDLE_BPS = 1024
IDLE_TICKS = 5
ALL_ADAPTERS = "__all__"
ALERT_CHOICES = (0.0, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0)
UI_VERSION = 22

# Corner-radius appearance choices (user-selectable from the menu).
CORNER_RADIUS_CHOICES = {
    "sharp": 0,
    "small": 4,
    "medium": 7,   # historic default
    "large": 11,
    "pill": 16,
}
DEFAULT_CORNER_RADIUS = "medium"

# Sparkline (mini speed chart) configuration.
SPARKLINE_SAMPLES = 60          # 60 seconds of history at 1 Hz
SPARKLINE_WIDTH = 150
SPARKLINE_HEIGHT = 38

WINDOW_WIDTH = 0
CARD_BORDER = 1
CORNER_RADIUS = CORNER_RADIUS_CHOICES[DEFAULT_CORNER_RADIUS]
CONTENT_PAD_X = 2
CONTENT_PAD_Y = 0
ICON_GAP = 1
SEP_PAD = 1
VALUE_SAMPLE = "999 MB/s"
# Padding that used to come free from tk.Label defaults; explicit now that
# text is measured with font metrics, so the card keeps its old proportions.
GLYPH_PAD_X = 4
GLYPH_PAD_Y = 4
GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
MONITOR_DEFAULTTONEAREST = 2
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
# Win32 magic numbers used elsewhere in the file, named for readability.
CREATE_NO_WINDOW = 0x08000000      # subprocess creation flag (no console flash)
MB_ICONERROR = 0x00000010          # MessageBox: error icon
MB_ICONINFORMATION = 0x00000040    # MessageBox: info icon
ERROR_ALREADY_EXISTS = 183         # CreateMutex: mutex already existed
# DPI awareness context values (SetProcessDpiAwarenessContext).
DPI_AWARENESS_PER_MONITOR_V2 = -4
DPI_AWARENESS_PER_MONITOR = 2
# High-contrast: SystemParametersInfo action codes.
SPI_GETHIGHCONTRAST = 0x0042
HCF_HIGHCONTRASTON = 0x00000001

CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_CONFIG: Dict[str, Any] = {
    "x": None, "y": None, "locked": False, "opacity": DEFAULT_OPACITY,
    "adapter": ALL_ADAPTERS, "show_sysload": True, "compact": False, "ui_version": UI_VERSION,
    "auto_hide": False, "snap_edges": True, "alert_mbps": 0.0, "font_size": DEFAULT_FONT_SIZE,
    "corner_radius": DEFAULT_CORNER_RADIUS,
    "ping_host": "", "ping_port": 53,
    "daily_date": "", "daily_down": 0, "daily_up": 0,
    "check_updates_on_start": True,
}
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
LOG_PATH = os.path.join(CONFIG_DIR, "netspeedtray.log")

log = logging.getLogger(APP_NAME)


class _StopLoop(Exception):
    """Internal control-flow signal to break out of a nested adapter scan."""


def setup_logging() -> None:
    """Quiet by default; NETSPEEDTRAY_DEBUG=1 writes a rotating-ish log next to the config."""
    if log.handlers:
        return
    log.setLevel(logging.DEBUG if os.environ.get("NETSPEEDTRAY_DEBUG") else logging.WARNING)
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 512 * 1024:
            os.replace(LOG_PATH, LOG_PATH + ".old")
        handler: logging.Handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]


MONITOR_ENUM_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(RECT), ctypes.c_ssize_t) if IS_WINDOWS else None

_USER32: Any = None
_USER32_READY = False


def user32():
    """Cached user32 handle with explicit argtypes (64-bit HWNDs must not truncate)."""
    global _USER32, _USER32_READY
    if not IS_WINDOWS:
        return None
    if _USER32_READY:
        return _USER32
    _USER32_READY = True
    try:
        u = ctypes.windll.user32
    except Exception:
        return None
    vp, ci, cl, cu = ctypes.c_void_p, ctypes.c_int, ctypes.c_long, ctypes.c_uint
    try:
        u.FindWindowW.restype, u.FindWindowW.argtypes = vp, [ctypes.c_wchar_p, ctypes.c_wchar_p]
        u.FindWindowExW.restype = vp
        u.FindWindowExW.argtypes = [vp, vp, ctypes.c_wchar_p, ctypes.c_wchar_p]
        u.GetWindowRect.argtypes = [vp, ctypes.POINTER(RECT)]
        u.GetParent.restype, u.GetParent.argtypes = vp, [vp]
        u.MonitorFromPoint.restype, u.MonitorFromPoint.argtypes = vp, [POINT, cu]
        u.GetMonitorInfoW.argtypes = [vp, ctypes.POINTER(MONITORINFO)]
        u.GetWindowLongW.restype, u.GetWindowLongW.argtypes = cl, [vp, ci]
        u.SetWindowLongW.restype, u.SetWindowLongW.argtypes = cl, [vp, ci, cl]
        if hasattr(u, "SetWindowLongPtrW"):
            u.SetWindowLongPtrW.restype, u.SetWindowLongPtrW.argtypes = vp, [vp, ci, vp]
        else:
            u.SetWindowLongPtrW = u.SetWindowLongW
        u.SetWindowPos.argtypes = [vp, vp, ci, ci, ci, ci, cu]
        u.EnumDisplayMonitors.argtypes = [vp, vp, MONITOR_ENUM_PROC, ctypes.c_ssize_t]
        u.GetForegroundWindow.restype = vp
    except Exception:
        pass
    _USER32 = u
    return u


def monitor_work_area(x: int, y: int) -> Optional[Tuple[int, int, int, int]]:
    u = user32()
    if u is None:
        return None
    try:
        handle = u.MonitorFromPoint(POINT(x, y), MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not u.GetMonitorInfoW(handle, ctypes.byref(info)):
            return None
        w = info.rcWork
        return w.left, w.top, w.right, w.bottom
    except Exception:
        return None


def enum_monitor_bounds() -> List[Tuple[int, int, int, int]]:
    u = user32()
    if u is None:
        return []
    bounds: List[Tuple[int, int, int, int]] = []

    def callback(_hmon, _hdc, rect_ptr, _data):
        r = rect_ptr.contents
        bounds.append((r.left, r.top, r.right, r.bottom))
        return 1
    cb = MONITOR_ENUM_PROC(callback)
    try:
        u.EnumDisplayMonitors(None, None, cb, 0)
    except Exception:
        return []
    return bounds


def _window_rect(u, hwnd) -> Optional[Tuple[int, int, int, int]]:
    if not hwnd:
        return None
    rect = RECT()
    try:
        if not u.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
    except Exception:
        return None
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return None
    return rect.left, rect.top, rect.right, rect.bottom


# Module-level cache for taskbar HWNDs/rects. ``taskbar_entries()`` does up to
# 17 FindWindow(Ex) calls; during a drag it ran several times per second and
# showed up in profiling. Cache it for TASKBAR_CACHE_TTL seconds.
_taskbar_cache: Tuple[float, List[Tuple[Any, Tuple[int, int, int, int]]]] = (0.0, [])


def taskbar_entries(force: bool = False) -> List[Tuple[Any, Tuple[int, int, int, int]]]:
    """Every taskbar HWND and its bounding rect (primary + secondary monitors).

    Results are cached for :data:`TASKBAR_CACHE_TTL` seconds; pass
    ``force=True`` to bypass the cache (used right after a display change).
    """
    global _taskbar_cache
    now = time.monotonic()
    cached_at, cached = _taskbar_cache
    if not force and cached and now - cached_at < TASKBAR_CACHE_TTL:
        return cached
    u = user32()
    if u is None:
        return []
    entries: List[Tuple[Any, Tuple[int, int, int, int]]] = []
    try:
        primary_hwnd = u.FindWindowW("Shell_TrayWnd", None)
        if primary_hwnd:
            rect = _window_rect(u, primary_hwnd)
            if rect:
                entries.append((primary_hwnd, rect))
        sec_hwnd = None
        for _ in range(16):
            sec_hwnd = u.FindWindowExW(None, sec_hwnd, "Shell_SecondaryTrayWnd", None)
            if not sec_hwnd:
                break
            rect = _window_rect(u, sec_hwnd)
            if rect:
                entries.append((sec_hwnd, rect))
    except Exception:
        log.debug("taskbar_entries failed", exc_info=True)
    _taskbar_cache = (now, entries)
    return entries


def is_high_contrast() -> bool:
    """True when the Windows High Contrast accessibility theme is active.

    In that mode our dark card palette clashes with the system colors, so the
    widget falls back to the system "BUTTONFACE"/window colors for the card
    background and uses the system text color for readings.
    """
    if not IS_WINDOWS:
        return False
    u = user32()
    if u is None:
        return False
    try:
        class HIGHCONTRASTW(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint),
                        ("lpszDefaultScheme", ctypes.c_void_p)]
        hc = HIGHCONTRASTW()
        hc.cbSize = ctypes.sizeof(HIGHCONTRASTW)
        if u.SystemParametersInfoW(SPI_GETHIGHCONTRAST, ctypes.sizeof(hc),
                                   ctypes.byref(hc), 0):
            return bool(hc.dwFlags & HCF_HIGHCONTRASTON)
    except Exception:
        log.debug("high-contrast probe failed", exc_info=True)
    return False


def taskbar_entry_near(near_x: Optional[int] = None,
                       near_y: Optional[int] = None) -> Optional[Tuple[Any, Tuple[int, int, int, int]]]:
    entries = taskbar_entries()
    if not entries:
        return None
    if near_x is None or near_y is None or len(entries) == 1:
        return entries[0]
    for hwnd, (left, top, right, bottom) in entries:
        if left <= near_x < right and top <= near_y < bottom:
            return hwnd, (left, top, right, bottom)

    def distance(entry: Tuple[Any, Tuple[int, int, int, int]]) -> float:
        left, top, right, bottom = entry[1]
        dx = max(left - near_x, 0, near_x - right)
        dy = max(top - near_y, 0, near_y - bottom)
        return float(dx * dx + dy * dy)
    return min(entries, key=distance)


def taskbar_bounds_all() -> List[Tuple[int, int, int, int]]:
    return [rect for _hwnd, rect in taskbar_entries()]


def taskbar_bounds(near_x: Optional[int] = None,
                   near_y: Optional[int] = None) -> Optional[Tuple[int, int, int, int]]:
    entry = taskbar_entry_near(near_x, near_y)
    return entry[1] if entry else None


class Config:
    def __init__(self, path: str = CONFIG_PATH) -> None:
        self.path = path
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.loaded_keys: set[str] = set()
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self.loaded_keys = set(loaded)
                for key in DEFAULT_CONFIG:
                    if key in loaded:
                        self.data[key] = loaded[key]
        except (OSError, ValueError):
            self.loaded_keys = set()
        self._sanitize()

    def _sanitize(self) -> None:
        if self.data.get("font_size") not in FONT_SIZE_PROFILES:
            self.data["font_size"] = DEFAULT_FONT_SIZE
        if not isinstance(self.data.get("adapter"), str):
            self.data["adapter"] = ALL_ADAPTERS
        for flag in ("locked", "show_sysload", "compact", "auto_hide",
                     "snap_edges", "check_updates_on_start"):
            if not isinstance(self.data.get(flag), bool):
                self.data[flag] = bool(DEFAULT_CONFIG[flag])
        try:
            self.data["alert_mbps"] = max(0.0, float(self.data.get("alert_mbps", 0.0)))
        except (TypeError, ValueError):
            self.data["alert_mbps"] = 0.0
        try:
            opacity = float(self.data.get("opacity", DEFAULT_OPACITY))
        except (TypeError, ValueError):
            opacity = DEFAULT_OPACITY
        self.data["opacity"] = min(MAX_OPACITY, max(MIN_OPACITY, opacity))
        for key in ("daily_down", "daily_up"):
            try:
                self.data[key] = max(0, int(self.data.get(key, 0)))
            except (TypeError, ValueError):
                self.data[key] = 0
        if not isinstance(self.data.get("daily_date"), str):
            self.data["daily_date"] = ""
        for key in ("x", "y"):
            value = self.data.get(key)
            if value is None:
                continue
            try:
                self.data[key] = int(value)
            except (TypeError, ValueError):
                self.data[key] = None

    def migrate(self) -> None:
        """Run forward-only schema migrations keyed on ``ui_version``.

        Each step is guarded by its own version check so that a brand-new
        install (version 0) and an upgrade from an older release both land on
        the current schema. New keys are added here as ``elif old_version < N``.
        """
        try:
            old_version = int(self.data.get("ui_version", 0))
        except (TypeError, ValueError):
            old_version = 0
        if old_version >= UI_VERSION:
            return
        if "show_sysload" not in self.loaded_keys or old_version < 2:
            self.data["show_sysload"] = True
        if old_version < 6:
            self.data["check_updates_on_start"] = True
        if old_version < 22:
            # v2.7.0: new appearance & ping options. Keep existing values when
            # present so a user's saved radius is not clobbered on upgrade.
            self.data.setdefault("corner_radius", DEFAULT_CORNER_RADIUS)
            self.data.setdefault("ping_host", "")
            self.data.setdefault("ping_port", 53)
        self.data["ui_version"] = UI_VERSION
        self.save()

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2)
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("config save failed: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, save: bool = False) -> None:
        self.data[key] = value
        if save and not getattr(self, "_batch_suspended", False):
            self.save()

    def set_many(self, items: Dict[str, Any], save: bool = True) -> None:
        """Set several keys in one shot, persisting at most once.

        Replaces the common pattern of several ``set(..., save=True)`` calls
        back-to-back (e.g. on reset_totals) which used to hit the disk per key.
        """
        self.data.update(items)
        if save and not getattr(self, "_batch_suspended", False):
            self.save()

    @contextmanager
    def batch(self) -> "Iterator[Config]":
        """Context manager that coalesces all ``set`` calls into one save.

        >>> with config.batch() as cfg:
        ...     cfg.set("daily_down", 0)
        ...     cfg.set("daily_up", 0)
        # one disk write at exit
        """
        self._batch_suspended = True
        try:
            yield self
        finally:
            self._batch_suspended = False
            self.save()


# --- Pure utility functions live in the net_speed package ---------------------
# The format_*/compare_versions/shorten/list_adapters helpers have no tkinter
# or Win32 dependencies, so they were extracted into net_speed.utils for
# unit-testability and a smaller top-level module. They are re-exported here so
# existing ``netspeedtray.format_speed`` style access keeps working.
from net_speed.utils import (
    list_adapters, adapter_status_map,
    format_speed, format_bytes, format_duration, shorten,
    compare_versions, _maybe_int,
)

class SpeedMonitor:
    def __init__(self, adapter: str = ALL_ADAPTERS) -> None:
        self.adapter = adapter
        self._last_recv = self._last_sent = 0
        self._last_recv, self._last_sent = self._read_counters()
        self._last_time = time.monotonic()

    def set_adapter(self, adapter: str) -> None:
        self.adapter = adapter
        self._last_recv, self._last_sent = self._read_counters()
        self._last_time = time.monotonic()

    def _read_counters(self) -> Tuple[int, int]:
        try:
            if self.adapter == ALL_ADAPTERS:
                c = psutil.net_io_counters()
                return (c.bytes_recv, c.bytes_sent) if c else (0, 0)
            entry = (psutil.net_io_counters(pernic=True) or {}).get(self.adapter)
            return (entry.bytes_recv, entry.bytes_sent) if entry else (self._last_recv, self._last_sent)
        except Exception:
            return self._last_recv, self._last_sent

    def sample(self) -> Tuple[float, float, int, int]:
        recv, sent = self._read_counters()
        now = time.monotonic()
        elapsed = now - self._last_time
        if elapsed <= 0:
            return 0.0, 0.0, 0, 0
        down_bytes, up_bytes = max(0, recv - self._last_recv), max(0, sent - self._last_sent)
        self._last_recv, self._last_sent, self._last_time = recv, sent, now
        return down_bytes / elapsed, up_bytes / elapsed, down_bytes, up_bytes


class TotalsTracker:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.peak_down = self.peak_up = 0.0
        self.session_down = self.session_up = 0
        self.session_start = time.monotonic()
        today = date.today().isoformat()
        if config.get("daily_date") != today:
            config.set("daily_date", today)
            config.set("daily_down", 0)
            config.set("daily_up", 0)
        self.daily_down = int(config.get("daily_down", 0))
        self.daily_up = int(config.get("daily_up", 0))
        self._last_save = time.monotonic()

    def add(self, down_bytes: int, up_bytes: int) -> None:
        today = date.today().isoformat()
        stored = str(self.config.get("daily_date", ""))
        # Only roll over when the calendar genuinely advanced. If the system
        # clock was wound *backwards* (stored == future, or today < stored
        # lexicographically for ISO dates) we keep accumulating into the stored
        # day instead of zeroing the counters, so a clock correction cannot
        # silently wipe a session's totals.
        if stored and today > stored:
            self.config.set_many({"daily_date": today,
                                  "daily_down": 0, "daily_up": 0}, save=False)
            self.daily_down = self.daily_up = 0
        elif not stored:
            self.config.set("daily_date", today, save=False)
        self.session_down += down_bytes
        self.session_up += up_bytes
        self.daily_down += down_bytes
        self.daily_up += up_bytes
        if time.monotonic() - self._last_save >= TOTALS_SAVE_INTERVAL:
            self.flush()

    def note_speed(self, down: float, up: float) -> None:
        self.peak_down = max(self.peak_down, down)
        self.peak_up = max(self.peak_up, up)

    def reset_today(self) -> None:
        self.daily_down = self.daily_up = 0
        self.session_down = self.session_up = 0
        self.peak_down = self.peak_up = 0.0
        self.session_start = time.monotonic()
        # Persist the date change and the zeroed totals in a single write.
        self.config.set_many({"daily_date": date.today().isoformat(),
                              "daily_down": 0, "daily_up": 0}, save=True)
        self._last_save = time.monotonic()

    def flush(self) -> None:
        # Coalesce the two counter writes + the save into one disk hit.
        self.config.set_many({"daily_down": self.daily_down,
                              "daily_up": self.daily_up}, save=True)
        self._last_save = time.monotonic()

    @property
    def session_seconds(self) -> float:
        return time.monotonic() - self.session_start


class SystemLoad:
    def __init__(self) -> None:
        self.cpu = self.ram_percent = 0.0
        self.ram_used = self.ram_total = 0
        self.error = ""
        try:
            psutil.cpu_percent(interval=None)
        except Exception as exc:
            self.error = str(exc)

    def sample(self) -> bool:
        try:
            self.cpu = max(0.0, min(100.0, float(psutil.cpu_percent(interval=None))))
            mem = psutil.virtual_memory()
            self.ram_percent = max(0.0, min(100.0, float(mem.percent)))
            self.ram_used, self.ram_total = mem.total - mem.available, mem.total
            self.error = ""
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def text_short(self) -> Tuple[str, str]:
        return ("CPU --", "RAM --") if self.error else (f"CPU {self.cpu:2.0f}%", f"RAM {self.ram_percent:2.0f}%")

    def text_full(self) -> str:
        if self.error:
            return "CPU/RAM unavailable"
        return f"CPU {self.cpu:>3.0f}%   RAM {self.ram_percent:>3.0f}%  ({format_bytes(self.ram_used)} / {format_bytes(self.ram_total)})"


class ProcessScanner:
    def __init__(self, top_n: int = 5) -> None:
        self.top_n, self.rows = top_n, ["scanning\u2026"]
        self._lock, self._busy, self._last_scan = threading.Lock(), False, 0.0
        self._name_cache: Dict[int, str] = {}

    def _name_for(self, pid: int) -> str:
        cached = self._name_cache.get(pid)
        if cached is not None:
            return cached
        try:
            name = psutil.Process(pid).name()
        except Exception:
            name = f"pid {pid}"
        if len(self._name_cache) > 512:
            self._name_cache.clear()
        self._name_cache[pid] = name
        return name

    def maybe_scan(self, force: bool = False) -> None:
        if self._busy or (not force and time.monotonic() - self._last_scan < PROCESS_SCAN_INTERVAL):
            return
        self._busy = True
        threading.Thread(target=self._scan, daemon=True).start()

    def snapshot(self) -> List[str]:
        with self._lock:
            return list(self.rows)

    def _scan(self) -> None:
        rows: List[str] = []
        try:
            counts: Dict[int, int] = {}
            denied = False
            try:
                connections = psutil.net_connections(kind="inet")
            except psutil.AccessDenied:
                connections, denied = [], True
            except Exception:
                connections = []
            for conn in connections:
                if conn.pid and conn.raddr:
                    counts[conn.pid] = counts.get(conn.pid, 0) + 1
            if not counts:
                rows = ["run as administrator for details"] if denied else ["no active connections"]
            else:
                merged: Dict[str, int] = {}
                for pid, count in counts.items():
                    name = self._name_for(pid)
                    merged[name] = merged.get(name, 0) + count
                ranked = sorted(merged.items(), key=lambda item: item[1], reverse=True)
                rows = [f"  {shorten(name, 22).ljust(22)}{count:>3} conn" for name, count in ranked[:self.top_n]]
                if len(ranked) > self.top_n:
                    rows.append(f"  +{len(ranked) - self.top_n} more")
        except Exception:
            rows = ["unavailable"]
        finally:
            with self._lock:
                self.rows = rows
            self._last_scan, self._busy = time.monotonic(), False


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pythonw):
        exe = pythonw
    return f'"{exe}" "{os.path.abspath(__file__)}"'


def is_autostart_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except (OSError, FileNotFoundError):
        return False


def set_autostart(enabled: bool) -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


class UpdateChecker:
    def __init__(self) -> None:
        self.latest: Optional[Dict[str, Any]] = None
        self.error = ""

    def fetch_latest(self) -> Optional[Dict[str, Any]]:
        """Fetch the latest release metadata from GitHub.

        Returns ``None`` (and sets :attr:`error`) when there is no published
        release at all — previously a *fake* release echoing the current
        version was synthesised, which was misleading because ``is_newer``
        then always returned False and the dialog showed phantom release notes
        that did not actually exist on GitHub.
        """
        # GitHub /releases/latest returns 404 if no release is published or only pre-releases exist.
        headers = {"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"}
        # Try latest release endpoint first
        try:
            req = urllib.request.Request(GITHUB_LATEST_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("tag_name"):
                    self.latest = data
                    self.error = ""
                    return self.latest
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                # Fallback: check all releases (includes pre-releases/drafts)
                try:
                    rel_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
                    req2 = urllib.request.Request(rel_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=10) as resp2:
                        releases = json.loads(resp2.read().decode("utf-8"))
                        if isinstance(releases, list) and releases:
                            self.latest = releases[0]
                            self.error = ""
                            return self.latest
                except Exception:
                    log.debug("releases fallback failed", exc_info=True)
                # No published releases found on the repo. Surface this as an
                # explicit state instead of fabricating a fake "latest".
                self.latest = None
                self.error = "No releases published yet."
                return None
            self.error = f"HTTP Error {exc.code}: {exc.reason}"
            return None
        except Exception as exc:
            self.error = str(exc)
            return None

    def check_async(self, callback: Callable[[Optional[Dict[str, Any]]], None]) -> None:
        def worker() -> None:
            data = self.fetch_latest()
            try:
                callback(data)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def latest_version(data: Dict[str, Any]) -> str:
        tag = data.get("tag_name") or data.get("name") or ""
        return str(tag).lstrip("vV")

    @staticmethod
    def find_exe_asset(data: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        for asset in data.get("assets", []) or []:
            name = asset.get("name", "")
            if name.lower().endswith(".exe"):
                return name, asset.get("browser_download_url", "")
        return None

    @staticmethod
    def is_newer(latest: str, current: str) -> bool:
        return compare_versions(latest, current) > 0


def download_update(asset_url: str, dest_path: str,
                    progress_cb: Optional[Callable[[float], None]] = None) -> bool:
    try:
        req = urllib.request.Request(asset_url, headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", "0") or 0)
            read = 0
            with open(dest_path, "wb") as fh:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
                    read += len(chunk)
                    if progress_cb and total:
                        try:
                            progress_cb(read / total)
                        except Exception:
                            pass
        return True
    except Exception:
        return False


def install_update(temp_exe: str) -> bool:
    """Spawn a helper batch that swaps the running exe for the downloaded one.

    The previous version ``del /f /q``'d the live exe and then ``copy``'d; if
    the app had not fully released the file handle yet (the quit path is
    async), the delete silently failed and the copy overwrote a half-locked
    file, leaving a broken binary. We now rename the running exe to ``.old``
    first (rename succeeds even on a running exe), copy the new one in, then
    delete the ``.old`` on the next launch. A retry loop also covers the rare
    case where an antivirus briefly holds the file.
    """
    if not getattr(sys, "frozen", False):
        return False
    current_exe = sys.executable
    if not current_exe or not os.path.exists(current_exe):
        return False
    # Keep the updater in the user's AppData (not shared %TEMP%) so another
    # user on the machine cannot plant a replacement batch file.
    updater_dir = os.path.join(CONFIG_DIR, "updater")
    try:
        os.makedirs(updater_dir, exist_ok=True)
    except OSError:
        updater_dir = tempfile.gettempdir()
    updater_path = os.path.join(updater_dir, "netspeedtray_updater.bat")
    backup_exe = current_exe + ".old"
    cur_name = os.path.basename(current_exe)
    backup_name = os.path.basename(backup_exe)
    try:
        with open(updater_path, "w", encoding="utf-8") as fh:
            fh.write("@echo off\r\n")
            fh.write("timeout /t 2 /nobreak >nul\r\n")
            # Best-effort cleanup of a previous backup from an older update.
            fh.write(f'del /f /q "{backup_exe}" >nul 2>&1\r\n')
            # Move the running binary aside (works even while it is running),
            # then install the new one. Rename is atomic on the same volume.
            fh.write('rename "' + current_exe + '" "' + backup_name + '" >nul 2>&1\r\n')
            # Retry the copy a few times in case AV still holds a brief lock.
            fh.write("set /a tries=0\r\n")
            fh.write(":copyloop\r\n")
            fh.write(f'copy /y "{temp_exe}" "{current_exe}" >nul 2>&1\r\n')
            fh.write(f'if exist "{current_exe}" goto copied\r\n')
            fh.write("set /a tries+=1\r\n")
            fh.write("if %tries% lss 10 (timeout /t 1 /nobreak >nul & goto copyloop)\r\n")
            # If copy never succeeded, restore the backup so the app still runs.
            fh.write('if not exist "' + current_exe + '" rename "' + backup_exe + '" "' + cur_name + '" >nul 2>&1\r\n')
            fh.write(":copied\r\n")
            fh.write(f'start "" "{current_exe}"\r\n')
            fh.write(f'del /f /q "{backup_exe}" >nul 2>&1\r\n')
            fh.write(f'del /f /q "{temp_exe}" >nul 2>&1\r\n')
            fh.write('del /f /q "%~f0" >nul 2>&1\r\n')
    except OSError:
        log.warning("updater script write failed", exc_info=True)
        return False
    try:
        subprocess.Popen(["cmd", "/c", updater_path],
                         creationflags=CREATE_NO_WINDOW, close_fds=True)
        return True
    except Exception:
        return False


class PingMonitor:
    """Non-blocking, cached latency probe using a fast TCP handshake.

    Uses a TCP ``connect()`` round-trip rather than raw ICMP because ICMP needs
    administrator privileges on Windows. The connect time is a good proxy for
    network latency to a well-known anycast endpoint (Cloudflare/Google DNS by
    default), but it is *not* identical to an ICMP ping — see Known Limitations
    in the README. The user can override the target host/port from the menu.
    """
    DEFAULT_TARGETS: List[Tuple[str, int]] = [("1.1.1.1", 53), ("8.8.8.8", 53)]

    def __init__(self, host: str = "", port: int = 53) -> None:
        self.value = "--"
        self._last = 0.0
        self._busy = False
        self._lock = threading.Lock()
        self.set_target(host, port)

    def set_target(self, host: str, port: int) -> None:
        """Configure a custom ping target, or revert to the defaults when empty."""
        host = (host or "").strip()
        if host:
            try:
                port = int(port)
            except (TypeError, ValueError):
                port = 53
            self._targets: List[Tuple[str, int]] = [(host, max(1, min(65535, port)))]
        else:
            self._targets = list(self.DEFAULT_TARGETS)

    def maybe_probe(self, force: bool = False) -> None:
        now = time.monotonic()
        if self._busy or (not force and now - self._last < PING_INTERVAL):
            return
        self._busy = True
        threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self) -> None:
        result = "--"
        try:
            for host, port in self._targets:
                # with-block closes the socket even when connect() times out.
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.settimeout(0.75)
                        t0 = time.perf_counter()
                        sock.connect((host, port))
                        result = f"{(time.perf_counter() - t0) * 1000.0:.0f} ms"
                    break
                except OSError:
                    continue
        finally:
            with self._lock:
                self.value = result
                self._last = time.monotonic()
                self._busy = False

class Tooltip:
    """Hover flyout with live metrics, a mini speed sparkline and net info.

    Fonts scale with the system DPI (older builds used fixed size-7/9 which was
    nearly unreadable on a 150% display). The sparkline is a tiny Canvas that
    redraws from the widget's rolling 60-sample history each refresh.
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.parent, self.window = parent, None
        self.value_labels: Dict[str, tk.Label] = {}
        self.spark_canvas: Optional[tk.Canvas] = None
        self.net_label: Optional[tk.Label] = None
        self.proc_label: Optional[tk.Label] = None

    @property
    def visible(self) -> bool:
        return self.window is not None and self.window.winfo_exists()

    def _scale(self, pts: int) -> int:
        """Scale a font point size by the system DPI (1.0 at 96 DPI)."""
        try:
            scale = max(1.0, float(self.parent.winfo_fpixels("1i")) / 96.0)
        except Exception:
            scale = 1.0
        return max(6, int(round(pts * scale)))

    def _metric(self, parent: tk.Misc, key: str, title: str, color: str) -> None:
        cell = tk.Frame(parent, bg=BG_SPEED_ROW, padx=7, pady=5)
        cell.pack(side="left", fill="both", expand=True, padx=(0, 3))
        tk.Label(cell, text=title, bg=BG_SPEED_ROW, fg=FG_LABEL,
                 font=(FONT_FAMILY, self._scale(7)), anchor="w").pack(anchor="w")
        label = tk.Label(cell, text="--", bg=BG_SPEED_ROW, fg=color,
                         font=(FONT_FAMILY, self._scale(9), "bold"), anchor="w")
        label.pack(anchor="w", pady=(1, 0))
        self.value_labels[key] = label

    def show(self, data: Dict[str, Any], anchor: tk.Misc) -> None:
        if self.window is not None and not self.window.winfo_exists():
            self.window, self.value_labels = None, {}
            self.spark_canvas = None
        if self.window is None:
            self.window = tk.Toplevel(self.parent)
            self.window.overrideredirect(True)
            self.window.attributes("-topmost", True)
            self.window.configure(bg=BORDER_COLOR)
            inner = tk.Frame(self.window, bg=BG_CARD, padx=9, pady=8)
            inner.pack(padx=1, pady=1)
            head = tk.Frame(inner, bg=BG_CARD)
            head.pack(fill="x", pady=(0, 7))
            tk.Label(head, text=APP_NAME, bg=BG_CARD, fg=FG_TEXT,
                     font=(FONT_FAMILY, self._scale(9), "bold")).pack(side="left")
            tk.Label(head, text="LIVE", bg=BG_CARD, fg=FG_DOWN,
                     font=(FONT_FAMILY, self._scale(7), "bold")).pack(side="right")
            self.speed_row = tk.Frame(inner, bg=BG_CARD)
            self.speed_row.pack(fill="x", pady=(0, 4))
            self._metric(self.speed_row, "down", "DOWNLOAD", FG_DOWN)
            self._metric(self.speed_row, "up", "UPLOAD", FG_UP)
            # Sparkline (mini line chart of the last 60s of download speed).
            spark_holder = tk.Frame(inner, bg=BG_SPEED_ROW, padx=4, pady=4)
            spark_holder.pack(fill="x", pady=(0, 4))
            tk.Label(spark_holder, text="speed (last 60s)", bg=BG_SPEED_ROW,
                     fg=FG_LABEL, font=(FONT_FAMILY, self._scale(7)),
                     anchor="w").pack(anchor="w")
            self.spark_canvas = tk.Canvas(spark_holder, bg=BG_SPEED_ROW,
                                          highlightthickness=0, bd=0,
                                          width=SPARKLINE_WIDTH,
                                          height=SPARKLINE_HEIGHT)
            self.spark_canvas.pack(fill="x", pady=(2, 0))
            self.system_row = tk.Frame(inner, bg=BG_CARD)
            self.system_row.pack(fill="x", pady=(0, 5))
            self._metric(self.system_row, "cpu", "CPU", FG_CPU)
            self._metric(self.system_row, "ram", "RAM", FG_RAM)
            self._metric(self.system_row, "ping", "PING", FG_DIM)
            # Network info row (local IP / public IP / Wi-Fi signal).
            self.net_label = tk.Label(inner, text="", bg=BG_CARD, fg=FG_DIM,
                                      font=(FONT_FAMILY, self._scale(7)),
                                      anchor="w", justify="left")
            self.net_label.pack(fill="x", pady=(0, 4))
            sep = tk.Frame(inner, height=1, bg=BORDER_SOFT)
            sep.pack(fill="x", pady=(2, 6))
            # Per-process speed row (top apps by sampled bandwidth).
            self.proc_label = tk.Label(inner, text="", bg=BG_CARD, fg=FG_TEXT,
                                       font=("Consolas", self._scale(8)),
                                       anchor="w", justify="left")
            self.proc_label.pack(fill="x", pady=(0, 4))
            foot = tk.Frame(inner, bg=BG_CARD)
            foot.pack(fill="x")
            self.foot = tk.Label(foot, text="", bg=BG_CARD, fg=FG_LABEL,
                                 font=(FONT_FAMILY, self._scale(7)), anchor="w")
            self.foot.pack(side="left")
            self.hint = tk.Label(foot, text="right-click: settings", bg=BG_CARD,
                                 fg=FG_LABEL, font=(FONT_FAMILY, self._scale(7)),
                                 anchor="e")
            self.hint.pack(side="right")
        for key, value in data.items():
            if not isinstance(value, str):
                continue
            label = self.value_labels.get(key)
            if label is not None:
                label.config(text=value)
        self.foot.config(text=f"{data.get('adapter','')}  ·  {data.get('session','')}")
        # Redraw the sparkline from the rolling history (passed in _spark).
        if self.spark_canvas is not None:
            self._draw_sparkline(data.get("_spark"))
        if self.net_label is not None:
            self.net_label.config(text=data.get("_net", ""))
        if self.proc_label is not None:
            self.proc_label.config(text=data.get("_proc", ""))
        try:
            self._place(anchor)
        except tk.TclError:
            self.hide()

    def _draw_sparkline(self, spark: Any) -> None:
        """Render a 2-line mini chart (download + upload) onto the tooltip canvas."""
        c = self.spark_canvas
        if c is None or not isinstance(spark, tuple) or len(spark) != 2:
            return
        down, up = spark
        c.delete("spark")
        w = int(c.winfo_width() or SPARKLINE_WIDTH)
        h = int(c.winfo_height() or SPARKLINE_HEIGHT)
        peak = max([1.0] + list(down) + list(up))
        n = max(len(down), len(up))
        if n < 2:
            return

        def pts(series: List[float]) -> List[Tuple[float, float]]:
            out = []
            for i, v in enumerate(series):
                x = (i / (n - 1)) * w
                y = h - (max(0.0, v) / peak) * (h - 2) - 1
                out.append((x, y))
            return out

        c.create_line(pts(down), fill=FG_DOWN, width=1, tags="spark", smooth=True)
        c.create_line(pts(up), fill=FG_UP, width=1, tags="spark", smooth=True)

    def _place(self, anchor: tk.Misc) -> None:
        if self.window is None:
            return
        self.window.update_idletasks()
        w, h = self.window.winfo_width(), self.window.winfo_height()
        ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
        aw, ah = anchor.winfo_width(), anchor.winfo_height()
        area = monitor_work_area(ax + aw // 2, ay + ah // 2)
        if area:
            left, top, right, bottom = area
            x = max(left + 6, min(ax + aw - w, right - w - 6))
            y = ay - h - 8
            if y < top + 6:
                y = min(ay + ah + 8, bottom - h - 6)
        else:
            x, y = ax + aw - w, max(4, ay - h - 8)
        self.window.geometry(f"+{int(x)}+{int(y)}")

    def hide(self) -> None:
        if self.window is not None:
            try: self.window.destroy()
            except tk.TclError: pass
        self.window = None
        self.value_labels = {}


class AppUsageDashboard:
    """Modern flyout dashboard displaying real-time per-app active network connections."""
    def __init__(self, parent: tk.Misc, widget: "SpeedWidget") -> None:
        self.parent = parent
        self.widget = widget
        self.window: Optional[tk.Toplevel] = None
        self._timer: Optional[str] = None

    def close(self) -> None:
        if self._timer is not None:
            try: self.parent.after_cancel(self._timer)
            except Exception: pass
            self._timer = None
        if self.window is not None:
            try: self.window.destroy()
            except tk.TclError: pass
            self.window = None

    def show(self, x: int, y: int) -> None:
        self.close()
        self.widget.scanner.maybe_scan(force=True)
        self.window = tk.Toplevel(self.parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=BORDER_COLOR)

        inner = tk.Frame(self.window, bg=BG_CARD, padx=12, pady=10)
        inner.pack(padx=1, pady=1)

        head = tk.Frame(inner, bg=BG_CARD)
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text="Network Activity Dashboard", bg=BG_CARD, fg=FG_TEXT,
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left")
        close_btn = tk.Label(head, text="✕", bg=BG_CARD, fg=FG_LABEL,
                             font=(FONT_FAMILY, 9, "bold"), cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda _e: self.close())

        desc = tk.Label(inner, text="Active processes with network connections:",
                        bg=BG_CARD, fg=FG_LABEL, font=(FONT_FAMILY, 7), anchor="w")
        desc.pack(fill="x", pady=(0, 6))

        self.list_frame = tk.Frame(inner, bg=BG_SPEED_ROW, padx=8, pady=8)
        self.list_frame.pack(fill="both", expand=True)
        self._row_labels = []
        self._last_rows: List[str] = []

        self._refresh_list()

        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.bind("<FocusOut>", lambda _e: self._deferred_close())
        self.window.update_idletasks()
        ww, wh = self.window.winfo_width(), self.window.winfo_height()
        area = monitor_work_area(x, y)
        if area:
            left, top, right, bottom = area
            x = max(left + 6, min(x, right - ww - 6))
            y = max(top + 6, min(y, bottom - wh - 6))
        self.window.geometry(f"+{x}+{y}")
        self.window.focus_force()

        # Auto refresh while open
        self._schedule_refresh()

    def _deferred_close(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        try:
            self.window.after(200, self.close)
        except tk.TclError:
            self.close()

    def _schedule_refresh(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self._timer = self.parent.after(2500, self._tick_refresh)

    def _tick_refresh(self) -> None:
        self.widget.scanner.maybe_scan(force=True)
        self._refresh_list()
        self._schedule_refresh()

    def _refresh_list(self) -> None:
        """Reuse labels: rebuilding the tree every 2.5s flickered and churned widgets."""
        if self.window is None or not self.window.winfo_exists():
            return
        rows = self.widget.scanner.snapshot() or ["No active network connections"]
        if rows == self._last_rows:
            return
        self._last_rows = list(rows)
        while len(self._row_labels) < len(rows):
            label = tk.Label(self.list_frame, text="", bg=BG_SPEED_ROW, fg=FG_TEXT,
                             font=("Consolas", 8), anchor="w", justify="left")
            label.pack(fill="x", pady=1)
            self._row_labels.append(label)
        for index, label in enumerate(self._row_labels):
            if index < len(rows):
                label.config(text=rows[index])
                if not label.winfo_ismapped():
                    label.pack(fill="x", pady=1)
            else:
                label.pack_forget()


class ModernContextPanel:
    def __init__(self, widget: "SpeedWidget") -> None:
        self.widget = widget
        self.window: Optional[tk.Toplevel] = None
        self.dashboard: Optional[AppUsageDashboard] = None

    def close(self) -> None:
        if self.dashboard is not None:
            self.dashboard.close()
        self._close()

    def _close(self) -> None:
        if self.window is not None:
            try: self.window.destroy()
            except tk.TclError: pass
            self.window = None

    def _row(self, parent: tk.Misc, title: str, value: str, command: Callable[[], None],
             accent: Optional[str] = None) -> None:
        row = tk.Frame(parent, bg=BG_CARD, cursor="hand2")
        row.pack(fill="x", pady=1)
        tk.Label(row, text=title, bg=BG_CARD, fg=accent or FG_TEXT,
                 font=(FONT_FAMILY, 8), anchor="w").pack(side="left", padx=8, pady=5)
        tk.Label(row, text=value, bg=BG_CARD, fg=FG_LABEL,
                 font=(FONT_FAMILY, 7), anchor="e").pack(side="right", padx=8)
        def paint(color: str) -> None:
            row.config(bg=color)
            for child in row.winfo_children():
                try:
                    child.config(bg=color)
                except tk.TclError:
                    pass

        for item in (row, *row.winfo_children()):
            item.bind("<Button-1>", lambda _e: (self._close(), command()))
            item.bind("<Enter>", lambda _e: paint(BG_SPEED_ROW))
            item.bind("<Leave>", lambda _e: paint(BG_CARD))

    def _deferred_close(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        try:
            self.window.after(140, self._close)
        except tk.TclError:
            self._close()

    def _open_dashboard(self, x: int, y: int) -> None:
        if self.dashboard is None:
            self.dashboard = AppUsageDashboard(self.widget.root, self.widget)
        self.dashboard.show(x, y)

    def _open_github(self) -> None:
        webbrowser.open_new_tab("https://github.com/raali09/NetSpeedTray")

    def show(self, x: int, y: int) -> None:
        self._close()
        w = self.widget
        self.window = tk.Toplevel(w.root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=BORDER_COLOR)

        inner = tk.Frame(self.window, bg=BG_CARD, padx=6, pady=7)
        inner.pack(padx=1, pady=1)

        # Header with App Name and Version
        head = tk.Frame(inner, bg=BG_CARD)
        head.pack(fill="x", padx=8, pady=(2, 4))
        tk.Label(head, text=APP_NAME, bg=BG_CARD, fg=FG_TEXT,
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left")
        tk.Label(head, text=f"v{APP_VERSION}", bg=BG_CARD, fg=FG_LABEL,
                 font=(FONT_FAMILY, 7)).pack(side="right")

        # Developer badge card (Ali Rahmani - github.com/raali09)
        dev_frame = tk.Frame(inner, bg=BG_SPEED_ROW, cursor="hand2", padx=8, pady=5)
        dev_frame.pack(fill="x", padx=4, pady=(2, 6))
        tk.Label(dev_frame, text="Developer: Ali Rahmani", bg=BG_SPEED_ROW, fg=FG_DOWN,
                 font=(FONT_FAMILY, 8, "bold"), anchor="w").pack(anchor="w")
        tk.Label(dev_frame, text="  github.com/raali09", bg=BG_SPEED_ROW, fg=FG_DIM,
                 font=(FONT_FAMILY, 7), anchor="w").pack(anchor="w", pady=(1, 0))
        def paint_dev(color: str) -> None:
            dev_frame.config(bg=color)
            for child in dev_frame.winfo_children():
                try:
                    child.config(bg=color)
                except tk.TclError:
                    pass

        for item in (dev_frame, *dev_frame.winfo_children()):
            item.bind("<Button-1>", lambda _e: (self._close(), self._open_github()))
            item.bind("<Enter>", lambda _e: paint_dev(BG_HOVER))
            item.bind("<Leave>", lambda _e: paint_dev(BG_SPEED_ROW))

        # Features & Settings Rows
        self._row(inner, "📊 App Network Usage", "Open", lambda: self._open_dashboard(x, y), accent=FG_DOWN)
        self._row(inner, "Lock position", "ON" if w.locked else "OFF", w.toggle_lock)
        self._row(inner, "Show CPU / RAM", "ON" if w.sysload_var.get() else "OFF",
                  lambda: (w.sysload_var.set(not w.sysload_var.get()), w._on_toggle_sysload()))
        self._row(inner, "Compact taskbar mode", "ON" if w.compact_var.get() else "OFF",
                  lambda: (w.compact_var.set(not w.compact_var.get()), w._on_toggle_compact()))
        self._row(inner, "Auto-hide when idle", "ON" if w.autohide_var.get() else "OFF",
                  lambda: (w.autohide_var.set(not w.autohide_var.get()), w._on_toggle_autohide()))
        self._row(inner, "Start with Windows", "ON" if is_autostart_enabled() else "OFF",
                  lambda: (w.autostart_var.set(not is_autostart_enabled()), w._on_toggle_autostart()))
        self._row(inner, "Snap to Taskbar", "ON" if w.snap_var.get() else "OFF",
                  lambda: (w.snap_var.set(not w.snap_var.get()), w._on_toggle_snap()))
        self._row(inner, "Font size", w.font_size_key.capitalize(),
                  lambda: w.font_menu.post(x, y))
        self._row(inner, "Network adapter", shorten(w.adapter if w.adapter != ALL_ADAPTERS else "All adapters", 18),
                  lambda: w.adapter_menu.post(x, y))
        self._row(inner, "Transparency", f"{int(w.opacity * 100)}%", w._open_opacity_popup)

        sep = tk.Frame(inner, height=1, bg=BORDER_SOFT)
        sep.pack(fill="x", padx=6, pady=5)

        self._row(inner, "Reset position", "", w.reset_position)
        self._row(inner, "Reset today's totals",
                  format_bytes(w.totals.daily_down + w.totals.daily_up), w.reset_totals)
        self._row(inner, "Check for updates", "", w._check_for_updates_manual)
        self._row(inner, "Exit", "", w.quit)

        self.window.bind("<Escape>", lambda _e: self._close())
        self.window.bind("<FocusOut>", lambda _e: self._deferred_close())
        self.window.update_idletasks()
        area = monitor_work_area(x, y)
        ww, wh = self.window.winfo_width(), self.window.winfo_height()
        if area:
            left, top, right, bottom = area
            x = max(left + 5, min(x, right - ww - 5))
            y = max(top + 5, min(y, bottom - wh - 5))
        self.window.geometry(f"+{x}+{y}")
        self.window.focus_force()

class OpacityPopup:
    def __init__(self, parent: tk.Misc, widget: "SpeedWidget") -> None:
        self.parent = parent
        self.widget = widget
        self.window: Optional[tk.Toplevel] = None
        self.scale: Optional[tk.Scale] = None
        self.value_label: Optional[tk.Label] = None
        self.fill_bar: Optional[tk.Frame] = None
        self.var: Optional[tk.DoubleVar] = None
        self._original_opacity: float = widget.opacity

    @property
    def visible(self) -> bool:
        return self.window is not None and self.window.winfo_exists()

    def toggle(self) -> None:
        if self.visible:
            self.close()
            return
        self._original_opacity = self.widget.opacity
        self._build()
        self._place()

    def _build(self) -> None:
        self.window = tk.Toplevel(self.parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=BORDER_COLOR)
        inner = tk.Frame(self.window, bg=BG_CARD, padx=12, pady=10)
        inner.pack(padx=1, pady=1)

        head_row = tk.Frame(inner, bg=BG_CARD)
        head_row.pack(fill="x", pady=(0, 6))
        tk.Label(head_row, text="Background transparency", bg=BG_CARD, fg=FG_TEXT,
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left")
        pct = int(round(self.widget.opacity * 100))
        self.value_label = tk.Label(head_row, text=f"{pct}%", bg=BG_CARD, fg=FG_DOWN,
                                    font=(FONT_FAMILY, 9, "bold"))
        self.value_label.pack(side="right")

        track_holder = tk.Frame(inner, bg=BG_SPEED_ROW, height=8, bd=0, relief="flat")
        track_holder.pack(fill="x", pady=(2, 2))
        track_holder.pack_propagate(False)
        self.fill_bar = tk.Frame(track_holder, bg=FG_DOWN, width=int(180 * self.widget.opacity))
        self.fill_bar.pack(side="left", fill="y")

        # The DoubleVar must be referenced; an inline one gets garbage collected.
        self.var = tk.DoubleVar(value=self.widget.opacity)
        self.scale = tk.Scale(inner, from_=MIN_OPACITY, to=MAX_OPACITY,
                             resolution=0.01, orient="horizontal",
                             variable=self.var,
                             bg=BG_CARD, fg=FG_TEXT, troughcolor=BG_SPEED_ROW,
                             highlightthickness=0, bd=0,
                             activebackground=BG_SPEED_ROW,
                             font=(FONT_FAMILY, 8), sliderrelief="flat",
                             length=180, showvalue=False, command=self._on_change)
        self.scale.pack(fill="x")

        hint = tk.Label(inner, text="drag left = more transparent  ·  right = more solid",
                        bg=BG_CARD, fg=FG_LABEL, font=(FONT_FAMILY, 7), anchor="w")
        hint.pack(fill="x", pady=(4, 0))

        btn_row = tk.Frame(inner, bg=BG_CARD)
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="done", bg=BG_SPEED_ROW, fg=FG_TEXT,
                  activebackground=BG_CARD, activeforeground=FG_TEXT,
                  font=(FONT_FAMILY, 8, "bold"), bd=0, relief="flat",
                  cursor="hand2", padx=12, pady=3, command=self.close).pack(side="left")
        tk.Button(btn_row, text="cancel", bg=BG_CARD, fg=FG_LABEL,
                  activebackground=BG_SPEED_ROW, activeforeground=FG_TEXT,
                  font=(FONT_FAMILY, 8), bd=0, relief="flat",
                  cursor="hand2", padx=10, pady=3,
                  command=self._cancel).pack(side="right")

        for w in (self.window, inner, head_row):
            w.bind("<Button-3>", lambda _e: self.close())
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.bind("<FocusOut>", lambda _e: self._maybe_close_on_focus_loss())
        self.window.after(60, lambda: self.window.focus_force())

    def _place(self) -> None:
        if self.window is None:
            return
        self.window.update_idletasks()
        w = self.window.winfo_width()
        h = self.window.winfo_height()
        rx = self.widget.root.winfo_x()
        ry = self.widget.root.winfo_y()
        rw = self.widget.root.winfo_width()
        rh = self.widget.root.winfo_height()
        x = rx + rw - w
        y = ry + rh + 6
        area = monitor_work_area(rx + rw // 2, ry + rh // 2)
        if area:
            left, top, right, bottom = area
            x = max(left + 4, min(x, right - w - 4))
            if y + h > bottom - 4:
                y = max(top + 4, ry - h - 6)
        self.window.geometry(f"+{int(x)}+{int(y)}")

    def _on_change(self, _value: str) -> None:
        if self.scale is None:
            return
        value = float(self.scale.get())
        self.widget.set_opacity(value)
        if self.value_label is not None:
            self.value_label.config(text=f"{int(round(value * 100))}%")
        if self.fill_bar is not None:
            self.fill_bar.config(width=max(1, int(180 * value)))

    def _maybe_close_on_focus_loss(self) -> None:
        if self.window is None or self.scale is None:
            return
        self.window.after(200, self._delayed_close_check)

    def _delayed_close_check(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        try:
            focused = self.window.focus_get()
        except tk.TclError:
            focused = None
        if focused is None:
            self.close()

    def _cancel(self) -> None:
        self.widget.set_opacity(self._original_opacity)
        self.close()

    def close(self) -> None:
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
        self.widget.flush_config()
        self.scale = None
        self.value_label = None
        self.fill_bar = None
        self.var = None


class UpdateDialog:
    def __init__(self, parent: tk.Misc, widget: "SpeedWidget",
                 latest_data: Dict[str, Any], current_version: str) -> None:
        self.parent = parent
        self.widget = widget
        self.latest_data = latest_data
        self.current_version = current_version
        self.window: Optional[tk.Toplevel] = None

    def show(self) -> None:
        latest_version = UpdateChecker.latest_version(self.latest_data)
        is_newer = UpdateChecker.is_newer(latest_version, self.current_version)
        title_text = "Update available" if is_newer else "You're up to date"
        self.window = tk.Toplevel(self.parent)
        self.window.title(title_text)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=BG_CARD)
        self.window.resizable(False, False)
        container = tk.Frame(self.window, bg=BG_CARD, padx=18, pady=16)
        container.pack()
        tk.Label(container, text=title_text, bg=BG_CARD, fg=FG_TEXT,
                 font=(FONT_FAMILY, 11, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        info_lines = [f"Current version : {self.current_version}",
                      f"Latest version  : {latest_version}"]
        if not is_newer:
            info_lines.append("")
            info_lines.append("No newer release is available.")
        tk.Label(container, text="\n".join(info_lines), bg=BG_CARD, fg=FG_DIM,
                 font=(FONT_FAMILY, 9), justify="left", anchor="w").pack(fill="x", pady=(0, 10))
        body = self.latest_data.get("body") or ""
        if body:
            preview = body if len(body) <= 600 else body[:600] + "\u2026"
            tk.Label(container, text=preview, bg=BG_CARD, fg=FG_TEXT,
                     font=(FONT_FAMILY, 9), justify="left", anchor="w",
                     wraplength=360).pack(fill="x", pady=(0, 10))
        btns = tk.Frame(container, bg=BG_CARD)
        btns.pack(fill="x")
        if is_newer:
            tk.Button(btns, text="Update now", bg=BG_SPEED_ROW, fg=FG_TEXT,
                      activebackground=BG_CARD, activeforeground=FG_TEXT,
                      font=(FONT_FAMILY, 9, "bold"), bd=0, relief="flat",
                      cursor="hand2", padx=14, pady=5,
                      command=self._do_update).pack(side="left")
            tk.Button(btns, text="Open in browser", bg=BG_CARD, fg=FG_DIM,
                      activebackground=BG_SPEED_ROW, activeforeground=FG_TEXT,
                      font=(FONT_FAMILY, 9), bd=0, relief="flat",
                      cursor="hand2", padx=10, pady=5,
                      command=self._open_browser).pack(side="left", padx=(8, 0))
        else:
            tk.Button(btns, text="OK", bg=BG_SPEED_ROW, fg=FG_TEXT,
                      activebackground=BG_CARD, activeforeground=FG_TEXT,
                      font=(FONT_FAMILY, 9, "bold"), bd=0, relief="flat",
                      cursor="hand2", padx=18, pady=5,
                      command=self.close).pack(side="left")
            tk.Button(btns, text="Open in browser", bg=BG_CARD, fg=FG_DIM,
                      activebackground=BG_SPEED_ROW, activeforeground=FG_TEXT,
                      font=(FONT_FAMILY, 9), bd=0, relief="flat",
                      cursor="hand2", padx=10, pady=5,
                      command=self._open_browser).pack(side="left", padx=(8, 0))
        tk.Button(btns, text="Close", bg=BG_CARD, fg=FG_LABEL,
                  activebackground=BG_SPEED_ROW, activeforeground=FG_TEXT,
                  font=(FONT_FAMILY, 9), bd=0, relief="flat",
                  cursor="hand2", padx=12, pady=5,
                  command=self.close).pack(side="right")
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.after(60, lambda: self.window.focus_force())
        self._center()

    def _center(self) -> None:
        if self.window is None:
            return
        self.window.update_idletasks()
        w = self.window.winfo_width()
        h = self.window.winfo_height()
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.window.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _do_update(self) -> None:
        asset = UpdateChecker.find_exe_asset(self.latest_data)
        if asset is None or not getattr(sys, "frozen", False):
            self._open_browser()
            self.close()
            return
        name, url = asset
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"{APP_NAME}_update_{name}")
        self._show_progress(f"Downloading {name}\u2026")

        def worker() -> None:
            ok = download_update(url, temp_path)
            if self.window is None or not self.window.winfo_exists():
                return
            self.window.after(0, lambda: self._after_download(ok, temp_path))

        threading.Thread(target=worker, daemon=True).start()

    def _show_progress(self, text: str) -> None:
        if self.window is None:
            return
        for child in list(self.window.winfo_children()):
            child.destroy()
        container = tk.Frame(self.window, bg=BG_CARD, padx=18, pady=16)
        container.pack()
        tk.Label(container, text=text, bg=BG_CARD, fg=FG_TEXT,
                 font=(FONT_FAMILY, 10, "bold")).pack(pady=10)
        tk.Label(container, text="please wait\u2026", bg=BG_CARD, fg=FG_DIM,
                 font=(FONT_FAMILY, 9)).pack()
        self.window.update_idletasks()
        self._center()

    def _after_download(self, ok: bool, temp_path: str) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        if not ok:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            self._show_error("Download failed. Please try again from the browser.")
            return
        self.close()
        if install_update(temp_path):
            self.widget.quit()
        else:
            self._open_browser()

    def _show_error(self, text: str) -> None:
        if self.window is None:
            return
        for child in list(self.window.winfo_children()):
            child.destroy()
        container = tk.Frame(self.window, bg=BG_CARD, padx=18, pady=16)
        container.pack()
        tk.Label(container, text=text, bg=BG_CARD, fg=FG_ALERT,
                 font=(FONT_FAMILY, 9), wraplength=320, justify="left").pack(pady=10)
        tk.Button(container, text="Close", bg=BG_SPEED_ROW, fg=FG_TEXT,
                  font=(FONT_FAMILY, 9, "bold"), bd=0, relief="flat",
                  cursor="hand2", padx=14, pady=4, command=self.close).pack()
        self.window.update_idletasks()
        self._center()

    def _open_browser(self) -> None:
        url = self.latest_data.get("html_url") or GITHUB_RELEASES_URL
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def close(self) -> None:
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class SpeedWidget:
    def __init__(self) -> None:
        self.config = Config()
        self.config.migrate()
        self.locked = bool(self.config.get("locked", False))
        self.compact = bool(self.config.get("compact", False))
        self.font_size_key = str(self.config.get("font_size", DEFAULT_FONT_SIZE))
        if self.font_size_key not in FONT_SIZE_PROFILES:
            self.font_size_key = DEFAULT_FONT_SIZE
        self._apply_font_profile(self.font_size_key)
        self.opacity = float(self.config.get("opacity", DEFAULT_OPACITY))
        self.adapter = str(self.config.get("adapter", ALL_ADAPTERS))
        self.adapters = list_adapters()
        if self.adapter != ALL_ADAPTERS and self.adapter not in self.adapters:
            self.adapter = ALL_ADAPTERS
            self.config.set("adapter", ALL_ADAPTERS, save=True)
        # Corner-radius appearance choice (v2.7.0). The numeric CORNER_RADIUS
        # constant is recomputed from this key whenever the user changes it.
        self.corner_radius_key = str(self.config.get("corner_radius", DEFAULT_CORNER_RADIUS))
        if self.corner_radius_key not in CORNER_RADIUS_CHOICES:
            self.corner_radius_key = DEFAULT_CORNER_RADIUS

        self.monitor, self.totals = SpeedMonitor(self.adapter), TotalsTracker(self.config)
        self.sysload, self.scanner = SystemLoad(), ProcessScanner()
        self.ping = PingMonitor(str(self.config.get("ping_host", "")),
                                int(self.config.get("ping_port", 53) or 53))
        self.update_checker = UpdateChecker()
        # Sparkline: rolling 60-sample window of download/upload speeds (bytes/s).
        self._spark_down: List[float] = [0.0] * SPARKLINE_SAMPLES
        self._spark_up: List[float] = [0.0] * SPARKLINE_SAMPLES
        # Network info cache (local/public IP, Wi-Fi signal) refreshed lazily.
        self._net_info: Dict[str, str] = {"local_ip": "--", "public_ip": "--", "wifi": "--"}
        self._net_info_last: float = 0.0
        # Per-process speed sampling (best-effort, sampled, not exact).
        self._proc_speed: Dict[str, Tuple[int, int]] = {}  # name -> (down_bps, up_bps)
        self._proc_io_last: Dict[int, Tuple[int, int]] = {}  # pid -> (last_recv_bytes, last_sent_bytes)
        self.last_down = self.last_up = 0.0
        self._idle_ticks, self._faded, self._closing = 0, False, False
        self._last_system_sample = 0.0
        self._taskbar_docked = False
        self._current_owner_tray: Any = None
        self._last_raise = 0.0
        self._last_tooltip_refresh = 0.0
        self._last_adapter_refresh = time.monotonic()
        self._last_taskbar_probe = 0.0
        self._cached_taskbar: Optional[Tuple[int, int, int, int]] = None
        self._drag_offset: Optional[Tuple[int, int]] = None
        self._after_id = self._tip_after_id = self._hide_after_id = None
        self._flash_after_id = self._save_after_id = None
        self._zorder_after_id = None
        # Adaptive z-order bookkeeping. _zorder_busy tracks the last time we had
        # to fight for z-order; once quiet for ZORDER_IDLE_GRACE we throttle.
        self._zorder_last_active = time.monotonic()
        self._lock_flash = False
        self._high_contrast = False
        self._alert_bps = float(self.config.get("alert_mbps", 0.0)) * 1024.0 * 1024.0
        self._card_shapes: List[int] = []
        self._card_w, self._card_h = WINDOW_WIDTH, 48
        self._suppress_bg_sync = False
        self._text_items: Dict[str, List[int]] = {}
        self._sep_line: Optional[int] = None
        self._icon_photos: List[tk.PhotoImage] = []
        self._font_cache: Dict[Tuple, tkfont.Font] = {}
        self._current_texts: Dict[str, str] = {
            "down_icon": "\u2193", "up_icon": "\u2191",
            "down_value": "0 KB/s", "up_value": "0 KB/s",
            "cpu_badge": "CPU --", "ram_badge": "RAM --",
        }
        self._current_colors: Dict[str, str] = {
            "down_icon": FG_DOWN, "up_icon": FG_UP,
            "down_value": FG_DOWN, "up_value": FG_UP,
            "cpu_badge": FG_CPU, "ram_badge": FG_RAM,
        }

        self.root = tk.Tk()
        # Now that a Tk root exists, re-resolve the font family for real so
        # Windows 10 (which lacks "Segoe UI Variable Text") gets "Segoe UI".
        refresh_font_family()
        self._apply_font_profile(self.font_size_key)
        self.bg_window: Optional[tk.Toplevel] = None
        self.bg_canvas: Optional[tk.Canvas] = None
        self.canvas: Optional[tk.Canvas] = None
        self._build_window()
        self._measure_layout()
        self._build_labels()
        self._build_menu()
        self.tooltip = Tooltip(self.root)
        self.context_panel = ModernContextPanel(self)
        self.opacity_popup = OpacityPopup(self.root, self)
        self._restore_position()
        self._bind_to_taskbar_owner(force=True)
        self._update_lock_indicator()
        self._refresh_layout()
        self._bind_events()
        # Re-measure layout when the window moves to a monitor with a different
        # DPI (WM_DPICHANGED is not exposed to tkinter; we approximate by
        # re-measuring on each <Configure> after the dpi scale may have moved).
        self.root.bind("<Configure>", self._on_configure, add="+")
        self._last_dpi_scale = self.ui_scale
        self.root.after(80, self._first_system_sample)
        self.root.after(UPDATE_CHECK_DELAY_MS, self._maybe_check_updates_on_start)
        # Graceful shutdown on Windows logoff / shutdown / task close. The
        # WM_QUERYENDSESSION/WM_ENDSESSION messages arrive as a WM_CLOSE-equivalent
        # which tkinter routes to WM_DELETE_WINDOW; we also catch atexit as a
        # belt-and-braces flush of the daily totals.
        import atexit
        atexit.register(self._atexit_flush)
        self._tick()
        # Dedicated, fast z-order keep-alive. The 1-second _tick is too slow:
        # the secondary taskbar (Shell_SecondaryTrayWnd) re-asserts its topmost
        # position on tray/clock/hover events and, between ticks, jumps above
        # the widget and stays there. Re-raising keeps the widget visible on
        # multi-monitor setups where it ends up on a secondary taskbar (e.g.
        # after swapping the primary display). Frequency is adaptive: fast
        # right after a fight, throttled once the widget has been stable.
        self._zorder_loop()

    def _build_window(self) -> None:
        # One opaque, layered taskbar window. The old two-window transparent
        # stack could lose z-order and slip behind the Windows taskbar.
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=FG_TRANSPARENT_KEY)
        self.root.resizable(False, False)
        try:
            self.root.attributes("-transparentcolor", FG_TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.root.update_idletasks()
        self._apply_toolwindow_style(self.root)
        self._set_window_icon(self.root)

        self.bg_window = tk.Toplevel(self.root)
        self.bg_window.overrideredirect(True)
        self.bg_window.attributes("-topmost", True)
        self.bg_window.attributes("-alpha", self._window_alpha())
        self.bg_window.configure(bg=BG_TRANSPARENT_KEY)
        self.bg_window.resizable(False, False)
        try:
            self.bg_window.attributes("-transparentcolor", BG_TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.bg_window.update_idletasks()
        self._apply_toolwindow_style(self.bg_window)
        self._set_window_icon(self.bg_window)

    def _set_window_icon(self, window: tk.Misc) -> None:
        icon = self._icon_path()
        if icon is None:
            return
        try:
            photo = tk.PhotoImage(file=icon)
            window.iconphoto(False, photo)
            if not hasattr(self, "_icon_photos"):
                self._icon_photos: List[tk.PhotoImage] = []
            self._icon_photos.append(photo)
        except (tk.TclError, OSError):
            pass

    def _icon_path(self) -> Optional[str]:
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                p = os.path.join(meipass, "icon.png")
                if os.path.exists(p):
                    return p
            p = os.path.join(os.path.dirname(sys.executable), "icon.png")
            if os.path.exists(p):
                return p
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            for rel in (os.path.join("..", "assets", "icon.png"),
                        os.path.join("assets", "icon.png"),
                        "icon.png"):
                p = os.path.normpath(os.path.join(script_dir, rel))
                if os.path.exists(p):
                    return p
        return None

    def _hwnd(self, window: tk.Misc) -> int:
        u = user32()
        if u is None:
            return 0
        try:
            hwnd = window.winfo_id()
            return u.GetParent(hwnd) or hwnd
        except Exception:
            return 0

    def _bind_to_taskbar_owner(self, force: bool = False) -> None:
        """Dynamically set the owner to the specific taskbar on this monitor.
        On multi-monitor setups, secondary monitors use Shell_SecondaryTrayWnd,
        which has an independent z-order. If we don't own that specific tray,
        clicking monitor 2's taskbar will bury the widget!"""
        u = user32()
        if u is None:
            return
        try:
            cx = self.root.winfo_x() + self.window_width // 2
            cy = self.root.winfo_y() + self._card_h // 2
        except tk.TclError:
            cx = cy = None
        entry = taskbar_entry_near(cx, cy)
        target_tray = entry[0] if entry else u.FindWindowW("Shell_TrayWnd", None)
        if not target_tray or (not force and target_tray == self._current_owner_tray):
            return
        self._current_owner_tray = target_tray
        for window in (self.bg_window, self.root):
            if window is None:
                continue
            try:
                hwnd = self._hwnd(window)
                if hwnd:
                    u.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, target_tray)
            except Exception:
                pass

    def _apply_toolwindow_style(self, window: tk.Misc) -> None:
        u = user32()
        if u is None:
            return
        try:
            hwnd = self._hwnd(window)
            style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
            u.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
            window.withdraw()
            window.after(10, window.deiconify)
        except Exception:
            pass

    def _apply_font_profile(self, key: str) -> None:
        profile = FONT_SIZE_PROFILES.get(key, FONT_SIZE_PROFILES[DEFAULT_FONT_SIZE])
        self.font_icon = (FONT_FAMILY, profile["icon"], "bold")
        self.font_value = (FONT_FAMILY, profile["value"], "bold")
        self.font_system = (FONT_FAMILY, profile["system"], "bold")

    def set_font_size(self, key: str) -> None:
        if key not in FONT_SIZE_PROFILES:
            return
        self.font_size_key = key
        self.config.set("font_size", key, save=True)
        if hasattr(self, "font_size_var"):
            self.font_size_var.set(key)
        self._apply_font_profile(key)
        self._measure_layout()
        self._refresh_layout()

    def _font_for(self, font: Tuple[str, int, str]) -> tkfont.Font:
        cached = self._font_cache.get(font)
        if cached is None:
            cached = tkfont.Font(root=self.root, font=font)
            self._font_cache[font] = cached
        return cached

    def _text_size(self, text: str, font: Tuple[str, int, str]) -> Tuple[int, int]:
        # Cached font metrics: creating/destroying a Label per measurement was
        # dozens of widget round-trips on every font or layout change.
        measured = self._font_for(font)
        return measured.measure(text), measured.metrics("linespace")

    def _measure_layout(self) -> None:
        self.ui_scale = max(1.0, float(self.root.winfo_fpixels("1i")) / 96.0)
        # Corner radius derives from the user's appearance choice so the menu
        # can switch between sharp / small / medium / large / pill at runtime.
        radius_pts = CORNER_RADIUS_CHOICES.get(self.corner_radius_key,
                                               CORNER_RADIUS_CHOICES[DEFAULT_CORNER_RADIUS])
        self.radius = int(round(radius_pts * self.ui_scale))
        self.border = max(1, int(round(CARD_BORDER * self.ui_scale)))
        pad_x = int(round(GLYPH_PAD_X * self.ui_scale))
        pad_y = int(round(GLYPH_PAD_Y * self.ui_scale))
        self.icon_px = self._text_size("\u2193", self.font_icon)[0] + pad_x
        self._value_px_max = self._text_size(VALUE_SAMPLE, self.font_value)[0] + pad_x
        self.badge_px = max(self._text_size("CPU 100%", self.font_system)[0],
                            self._text_size("RAM 100%", self.font_system)[0]) + pad_x
        self.row_h = max(self._text_size("0 KB/s", self.font_value)[1],
                         self._text_size("\u2193", self.font_icon)[1],
                         self._text_size("CPU --", self.font_system)[1]) + pad_y
        self.value_px = self._value_px_max
        self._recompute_width()

    def set_corner_radius(self, key: str) -> None:
        """Change the card corner radius at runtime from a menu choice."""
        if key not in CORNER_RADIUS_CHOICES:
            return
        self.corner_radius_key = key
        self.config.set("corner_radius", key, save=True)
        # Force the shape list to rebuild (different radius => different shape
        # count when crossing the r<2 threshold), then redraw.
        self._card_shapes = []
        self._measure_layout()
        self._refresh_layout()

    def _include_sysload(self) -> bool:
        if self.compact:
            return False
        if hasattr(self, "sysload_var"):
            return bool(self.sysload_var.get())
        return bool(self.config.get("show_sysload", True))

    def _recompute_width(self) -> None:
        speed_width = self.icon_px + ICON_GAP + self.value_px
        if self.compact:
            # One tight row: download | upload.
            content = speed_width * 2 + SEP_PAD + 1
        else:
            # Two rows: download/upload | CPU/RAM. Do not reserve a second
            # speed column here, it was the source of the large empty gap.
            content = speed_width
            if self._include_sysload():
                content += SEP_PAD + 1 + self.badge_px
        self.window_width = int(max(WINDOW_WIDTH,
                                    content + 2 * (self.border + CONTENT_PAD_X)))

    def _relayout(self) -> None:
        self._recompute_width()
        self._rebuild_text_items()
        self._apply_geometry()

    def _rebuild_text_items(self) -> None:
        if self.canvas is None:
            return
        for items in self._text_items.values():
            for item in items:
                self.canvas.delete(item)
        self._text_items = {}
        if self.bg_canvas is not None:
            self.bg_canvas.delete("dynamic_sep")
        self._sep_line = None

        left = self.border + CONTENT_PAD_X
        speed_right = left + self.icon_px + ICON_GAP + self.value_px
        if self.compact:
            self._make_text("down_icon", left, self._row_y(0), self._current_texts["down_icon"], self.font_icon, self._current_colors["down_icon"], "w")
            self._make_text("down_value", speed_right, self._row_y(0), self._current_texts["down_value"], self.font_value, self._current_colors["down_value"], "e")
            up_left = speed_right + SEP_PAD
            up_right = up_left + self.icon_px + ICON_GAP + self.value_px
            self._make_text("up_icon", up_left, self._row_y(0), self._current_texts["up_icon"], self.font_icon, self._current_colors["up_icon"], "w")
            self._make_text("up_value", up_right, self._row_y(0), self._current_texts["up_value"], self.font_value, self._current_colors["up_value"], "e")
        else:
            self._make_text("down_icon", left, self._row_y(0), self._current_texts["down_icon"], self.font_icon, self._current_colors["down_icon"], "w")
            self._make_text("down_value", speed_right, self._row_y(0), self._current_texts["down_value"], self.font_value, self._current_colors["down_value"], "e")
            self._make_text("up_icon", left, self._row_y(1), self._current_texts["up_icon"], self.font_icon, self._current_colors["up_icon"], "w")
            self._make_text("up_value", speed_right, self._row_y(1), self._current_texts["up_value"], self.font_value, self._current_colors["up_value"], "e")

        if self._include_sysload():
            sep_x = speed_right + SEP_PAD
            badge_right = self.window_width - self.border - CONTENT_PAD_X
            self._make_text("cpu_badge", badge_right, self._row_y(0),
                            self._current_texts["cpu_badge"], self.font_system,
                            self._current_colors["cpu_badge"], "e")
            self._make_text("ram_badge", badge_right, self._row_y(1),
                            self._current_texts["ram_badge"], self.font_system,
                            self._current_colors["ram_badge"], "e")
            self._draw_separator(self._card_h)

    def _draw_separator(self, height: int) -> None:
        if self.bg_canvas is None:
            return
        self.bg_canvas.delete("dynamic_sep")
        self._sep_line = None
        if not self._include_sysload():
            return
        sep_x = (self.border + CONTENT_PAD_X + self.icon_px + ICON_GAP + self.value_px + SEP_PAD)
        self._sep_line = self.bg_canvas.create_line(
            sep_x, self.border + CONTENT_PAD_Y + 2,
            sep_x, height - self.border - CONTENT_PAD_Y - 2,
            fill=BORDER_SOFT, width=1, tags="dynamic_sep")

    def _row_y(self, row: int) -> float:
        return self.border + CONTENT_PAD_Y + row * self.row_h + self.row_h / 2.0

    def _make_text(self, key: str, x: float, y: float, text: str,
                   font: Tuple[str, int, str], fill: str, anchor: str) -> None:
        self._current_texts[key] = text
        self._current_colors[key] = fill
        shadow = self.canvas.create_text(
            x + TEXT_SHADOW_OFFSET, y + TEXT_SHADOW_OFFSET,
            text=text, font=font, fill=SHADOW_COLOR, anchor=anchor)
        text_item = self.canvas.create_text(x, y, text=text, font=font, fill=fill, anchor=anchor)
        self._text_items[key] = [shadow, text_item]

    def _set_text(self, key: str, text: str, fill: Optional[str] = None) -> None:
        old_text = self._current_texts.get(key)
        old_fill = self._current_colors.get(key)
        next_fill = old_fill if fill is None else fill
        if old_text == text and old_fill == next_fill:
            return
        self._current_texts[key] = text
        if fill is not None:
            self._current_colors[key] = fill
        items = self._text_items.get(key)
        if not items:
            return
        main = items[-1]
        for item in items[:-1]:
            self.canvas.itemconfig(item, text=text)
        if fill is not None:
            self.canvas.itemconfig(main, text=text, fill=fill)
        else:
            self.canvas.itemconfig(main, text=text)

    def _build_labels(self) -> None:
        self.bg_canvas = tk.Canvas(self.bg_window, bg=BG_TRANSPARENT_KEY,
                                  highlightthickness=0, bd=0,
                                  width=self.window_width, height=self._card_h)
        self.bg_canvas.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.root, bg=FG_TRANSPARENT_KEY,
                                highlightthickness=0, bd=0,
                                width=self.window_width, height=self._card_h)
        self.canvas.pack(fill="both", expand=True)

        self._text_items = {}
        self._sep_line = None
        self._rebuild_text_items()

    def _rounded_rect(self, canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
                      radius: float, fill: str) -> List[int]:
        r = max(0.0, min(radius, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
        if r < 2.0:
            return [canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")]
        items = [
            canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=""),
            canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=""),
        ]
        for bx, by, start in ((x1, y1, 90), (x2 - 2 * r, y1, 0),
                              (x1, y2 - 2 * r, 180), (x2 - 2 * r, y2 - 2 * r, 270)):
            items.append(canvas.create_arc(bx, by, bx + 2 * r, by + 2 * r,
                                            start=start, extent=90,
                                            style="pieslice", fill=fill, outline=""))
        return items

    def _window_alpha(self) -> float:
        return max(MIN_OPACITY, min(MAX_OPACITY, float(self.opacity)))

    def _surface_color(self) -> str:
        """Card fill color, swapped to the system window color in High Contrast."""
        if getattr(self, "_high_contrast", False):
            return "#F0F0F0"
        return BG_CARD

    def _draw_card(self, width: int, height: int) -> None:
        """Paint the rounded card background.

        Shapes are reused across redraws (the old code deleted and recreated
        ~8 canvas items on every layout change); we now reconfigure their fill
        in place, which removes a noticeable flicker when toggling compact mode
        or the lock flash.
        """
        if self.bg_canvas is None:
            return
        inset = float(self.border)
        radius = min(self.radius, height / 2.0)
        border_fill = self._border_color()
        surface_fill = self._surface_color()
        outer = self._rounded_rect(self.bg_canvas, 0.0, 0.0, float(width), float(height),
                                   radius, border_fill)
        inner = self._rounded_rect(self.bg_canvas, inset, inset,
                                   width - inset, height - inset,
                                   max(2.0, radius - inset), surface_fill)
        # If we already had shapes, recolor them and delete the new temp ones;
        # this keeps the z-order stable and avoids the delete/recreate churn.
        if self._card_shapes and len(self._card_shapes) == len(outer) + len(inner):
            for old, new in zip(self._card_shapes, outer + inner):
                try:
                    fill = self.bg_canvas.itemcget(new, "fill")
                    self.bg_canvas.itemconfig(old, fill=fill)
                except tk.TclError:
                    pass
            for item in outer + inner:
                self.bg_canvas.delete(item)
        else:
            self._card_shapes = outer + inner
        for item in self._card_shapes:
            self.bg_canvas.tag_lower(item)

    def _border_color(self) -> str:
        """Border color: amber flash when a locked drag is attempted, else neutral.

        In High Contrast mode the border is forced to the system window-frame
        color so the card outline remains visible against the high-contrast
        desktop.
        """
        if getattr(self, "_high_contrast", False):
            return "#000000"
        return FG_LOCK_FLASH if self._lock_flash else BORDER_COLOR

    def _sync_layer_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """Move both layers atomically enough to avoid a one-frame ghost/offset."""
        self.root.geometry(f"{width}x{height}+{int(x)}+{int(y)}")
        if self.bg_window is not None:
            self.bg_window.geometry(f"{width}x{height}+{int(x)}+{int(y)}")

    def _apply_geometry(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        rows = 1 if self.compact else 2
        height = max(rows * self.row_h + 2 * (self.border + CONTENT_PAD_Y),
                     2 * self.radius + 4)
        self._card_w, self._card_h = self.window_width, height
        if x is None or y is None:
            x, y = self.root.winfo_x(), self.root.winfo_y()
        self._sync_layer_geometry(int(x), int(y), self.window_width, height)
        if self.canvas is not None:
            self.canvas.config(width=self.window_width, height=height)
        if self.bg_window is not None and self.bg_canvas is not None:
            self.bg_canvas.config(width=self.window_width, height=height)
            self._draw_card(self.window_width, height)
            self._draw_separator(height)
        self.root.update_idletasks()
        self._raise_windows(force=True)

    def _all_widgets(self) -> List[tk.Misc]:
        def collect(widget: tk.Misc) -> List[tk.Misc]:
            result = [widget]
            for child in widget.winfo_children():
                result.extend(collect(child))
            return result
        return collect(self.root)

    def _refresh_layout(self) -> None:
        self._relayout()
        if self._include_sysload():
            self._update_system_labels()
        if self.locked:
            self._enforce_locked_position()

    def _first_system_sample(self) -> None:
        if not self._closing:
            self._update_system_labels()

    def _update_system_labels(self) -> None:
        self.sysload.sample()
        self._last_system_sample = time.monotonic()
        if not self._include_sysload():
            return
        cpu_text, ram_text = self.sysload.text_short()
        self._set_text("cpu_badge", cpu_text)
        self._set_text("ram_badge", ram_text)

    def _build_menu(self) -> None:
        menu_opts = dict(tearoff=0, bg=BG_CARD, fg=FG_TEXT,
                         activebackground=BG_SPEED_ROW, activeforeground=FG_TEXT,
                         selectcolor=FG_CHECK, font=FONT_MENU,
                         disabledforeground=FG_LABEL)
        self.menu = tk.Menu(self.root, **menu_opts)
        self.menu.add_command(label=DEVELOPER_LINE, state="disabled")
        self.menu.add_separator()
        self.lock_var = tk.BooleanVar(value=self.locked)
        self.menu.add_checkbutton(label="Lock position", variable=self.lock_var,
                                   command=self.toggle_lock, selectcolor=FG_CHECK)
        self.adapter_var = tk.StringVar(value=self.adapter)
        self.adapter_menu = tk.Menu(self.menu, **menu_opts)
        self.menu.add_cascade(label="Network adapter", menu=self.adapter_menu)
        self._populate_adapter_menu()
        self.menu.add_separator()
        self.sysload_var = tk.BooleanVar(value=bool(self.config.get("show_sysload", True)))
        self.menu.add_checkbutton(label="Show CPU / RAM", variable=self.sysload_var,
                                   command=self._on_toggle_sysload, selectcolor=FG_CHECK)
        self.compact_var = tk.BooleanVar(value=self.compact)
        self.menu.add_checkbutton(label="Compact taskbar mode", variable=self.compact_var,
                                   command=self._on_toggle_compact, selectcolor=FG_CHECK)
        self.font_size_var = tk.StringVar(value=self.font_size_key)
        self.font_menu = tk.Menu(self.menu, **menu_opts)
        for fkey in ("small", "medium", "large", "xlarge"):
            self.font_menu.add_radiobutton(
                label=fkey.capitalize(), value=fkey,
                variable=self.font_size_var,
                command=lambda k=fkey: self.set_font_size(k),
                selectcolor=FG_CHECK)
        self.menu.add_cascade(label="Font size", menu=self.font_menu)
        # Corner-radius appearance choice (v2.7.0).
        self.corner_var = tk.StringVar(value=self.corner_radius_key)
        self.corner_menu = tk.Menu(self.menu, **menu_opts)
        for ckey in ("sharp", "small", "medium", "large", "pill"):
            self.corner_menu.add_radiobutton(
                label=ckey.capitalize(), value=ckey,
                variable=self.corner_var,
                command=lambda k=ckey: self.set_corner_radius(k),
                selectcolor=FG_CHECK)
        self.menu.add_cascade(label="Corner style", menu=self.corner_menu)
        self.menu.add_command(label="Background transparency\u2026", command=self._open_opacity_popup)
        # Custom ping target (v2.7.0): opens a small prompt to set host[:port].
        self.menu.add_command(label="Set ping target\u2026", command=self._set_ping_target)
        self.autohide_var = tk.BooleanVar(value=bool(self.config.get("auto_hide")))
        self.menu.add_checkbutton(label="Auto-hide when idle", variable=self.autohide_var,
                                   command=self._on_toggle_autohide, selectcolor=FG_CHECK)
        self.snap_var = tk.BooleanVar(value=bool(self.config.get("snap_edges")))
        self.menu.add_checkbutton(label="Snap to screen edges", variable=self.snap_var,
                                   command=self._on_toggle_snap, selectcolor=FG_CHECK)
        self.alert_var = tk.DoubleVar(value=float(self.config.get("alert_mbps", 0.0)))
        self.alert_menu = tk.Menu(self.menu, **menu_opts)
        for value in ALERT_CHOICES:
            self.alert_menu.add_radiobutton(
                label="Off" if value == 0 else f"above {value:g} MB/s",
                value=value, variable=self.alert_var,
                command=self._on_select_alert, selectcolor=FG_CHECK)
        self.menu.add_cascade(label="Alert threshold", menu=self.alert_menu)
        self.menu.add_separator()
        self.menu.add_command(label="Check for updates\u2026", command=self._check_for_updates_manual)
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        self.menu.add_checkbutton(label="Start with Windows", variable=self.autostart_var,
                                   command=self._on_toggle_autostart, selectcolor=FG_CHECK)
        self.menu.add_separator()
        self.menu.add_command(label="Reset position", command=self.reset_position)
        self.menu.add_command(label="Reset today's totals", command=self.reset_totals)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.quit)

    def _populate_adapter_menu(self) -> None:
        status = adapter_status_map()
        self.adapter_menu.delete(0, "end")
        self.adapter_menu.add_radiobutton(
            label="All adapters (total)", value=ALL_ADAPTERS,
            variable=self.adapter_var, command=self._on_select_adapter,
            selectcolor=FG_CHECK)
        self.adapter_menu.add_separator()
        if not self.adapters:
            self.adapter_menu.add_command(label="No adapters found", state="disabled")
        for name in self.adapters:
            marker = "" if status.get(name, True) else "   (down)"
            self.adapter_menu.add_radiobutton(
                label=shorten(name) + marker, value=name,
                variable=self.adapter_var, command=self._on_select_adapter,
                selectcolor=FG_CHECK)
        self.adapter_menu.add_separator()
        self.adapter_menu.add_command(label="Refresh list", command=self.refresh_adapters)

    def refresh_adapters(self) -> None:
        adapters = list_adapters()
        if adapters == self.adapters:
            return
        self.adapters = adapters
        self._populate_adapter_menu()
        if self.adapter != ALL_ADAPTERS and self.adapter not in self.adapters:
            self.adapter = ALL_ADAPTERS
            self.adapter_var.set(ALL_ADAPTERS)
            self.config.set("adapter", ALL_ADAPTERS, save=True)
            self.monitor.set_adapter(ALL_ADAPTERS)

    def _on_select_adapter(self) -> None:
        self.adapter = self.adapter_var.get()
        self.config.set("adapter", self.adapter, save=True)
        self.monitor.set_adapter(self.adapter)
        self._refresh_labels(0.0, 0.0)

    def _set_ping_target(self) -> None:
        """Prompt for a custom ping target (``host`` or ``host:port``).

        Empty input reverts to the built-in Cloudflare/Google DNS defaults so
        the user can always get back to a known-good state.
        """
        current = str(self.config.get("ping_host", ""))
        if current:
            current = f"{current}:{self.config.get('ping_port', 53)}"
        else:
            current = ""
        value = simpledialog.askstring("Ping target",
                                       "Host or host:port (empty = Cloudflare/Google DNS):",
                                       initialvalue=current, parent=self.root)
        if value is None:
            return  # cancelled
        value = value.strip()
        host, port = "", 53
        if value:
            if ":" in value:
                host, _, port_s = value.rpartition(":")
                try:
                    port = int(port_s)
                except ValueError:
                    port = 53
            else:
                host = value
        self.config.set_many({"ping_host": host, "ping_port": port}, save=True)
        self.ping.set_target(host, port)
        self.ping.maybe_probe(force=True)

    def _on_toggle_sysload(self) -> None:
        enabled = bool(self.sysload_var.get())
        self.config.set("show_sysload", enabled, save=True)
        self._refresh_layout()

    def _on_toggle_compact(self) -> None:
        self.compact = bool(self.compact_var.get())
        self.config.set("compact", self.compact, save=True)
        self._refresh_layout()

    def _open_opacity_popup(self) -> None:
        self.opacity_popup.toggle()

    def _schedule_config_save(self) -> None:
        """Coalesce writes: dragging the opacity slider used to hit the disk per pixel."""
        if self._save_after_id is not None:
            return
        self._save_after_id = self.root.after(CONFIG_SAVE_DEBOUNCE_MS, self.flush_config)

    def flush_config(self) -> None:
        if self._save_after_id is not None:
            try: self.root.after_cancel(self._save_after_id)
            except tk.TclError: pass
            self._save_after_id = None
        self.config.save()

    def set_opacity(self, value: float) -> None:
        value = min(MAX_OPACITY, max(MIN_OPACITY, float(value)))
        if abs(value - self.opacity) < 0.005:
            return
        self.opacity = value
        self.config.set("opacity", self.opacity)
        self._schedule_config_save()
        try:
            self.root.attributes("-alpha", 1.0)
            if self.bg_window is not None:
                self.bg_window.attributes("-alpha", self._window_alpha())
        except tk.TclError:
            pass

    def _on_toggle_autohide(self) -> None:
        enabled = bool(self.autohide_var.get())
        self.config.set("auto_hide", enabled, save=True)
        if not enabled:
            self._idle_ticks = 0
            self._set_faded(False)

    def _on_toggle_snap(self) -> None:
        self.config.set("snap_edges", bool(self.snap_var.get()), save=True)

    def _on_select_alert(self) -> None:
        self._alert_bps = float(self.alert_var.get()) * 1024.0 * 1024.0
        self.config.set("alert_mbps", float(self.alert_var.get()), save=True)
        self._refresh_labels(self.last_down, self.last_up)

    def _safe_after(self, callback: Callable[[], None], delay: int = 0) -> None:
        """Hop a worker-thread result back onto the Tk loop without racing shutdown."""
        if self._closing:
            return
        try:
            self.root.after(delay, callback)
        except (tk.TclError, RuntimeError):
            pass

    def _maybe_check_updates_on_start(self) -> None:
        if not self.config.get("check_updates_on_start", True):
            return
        self.update_checker.check_async(self._on_updates_checked_silent)

    def _on_updates_checked_silent(self, data: Optional[Dict[str, Any]]) -> None:
        if data is None or self._closing:
            return
        latest_version = UpdateChecker.latest_version(data)
        if UpdateChecker.is_newer(latest_version, APP_VERSION):
            self._safe_after(lambda: self._show_update_dialog(data))

    def _check_for_updates_manual(self) -> None:
        if self._closing:
            return
        menu_index = self._find_menu_index("Check for updates\u2026")
        if menu_index is not None:
            try:
                self.menu.entryconfig(menu_index, label="Checking\u2026", state="disabled")
            except tk.TclError:
                pass

        def cb(data: Optional[Dict[str, Any]]) -> None:
            self._safe_after(lambda: self._after_manual_check(data, menu_index))

        self.update_checker.check_async(cb)

    def _find_menu_index(self, label: str) -> Optional[int]:
        try:
            end = self.menu.index("end")
            if end is None:
                return None
            for i in range(end + 1):
                if self.menu.type(i) == "command" and self.menu.entrycget(i, "label") == label:
                    return i
        except tk.TclError:
            return None
        return None

    def _after_manual_check(self, data: Optional[Dict[str, Any]], menu_index: Optional[int]) -> None:
        if menu_index is not None:
            try:
                self.menu.entryconfig(menu_index, label="Check for updates\u2026", state="normal")
            except tk.TclError:
                pass
        if data is None:
            self._show_simple_message(
                "Update check failed",
                f"Could not check for updates.\n{self.update_checker.error}")
            return
        self._show_update_dialog(data)

    def _show_update_dialog(self, data: Dict[str, Any]) -> None:
        if self._closing:
            return
        UpdateDialog(self.root, self, data, APP_VERSION).show()

    def _show_simple_message(self, title: str, text: str) -> None:
        if self._closing:
            return
        win = tk.Toplevel(self.root)
        win.title(title)
        win.attributes("-topmost", True)
        win.configure(bg=BG_CARD)
        win.resizable(False, False)
        f = tk.Frame(win, bg=BG_CARD, padx=18, pady=16)
        f.pack()
        tk.Label(f, text=title, bg=BG_CARD, fg=FG_TEXT,
                 font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", pady=(0, 6))
        tk.Label(f, text=text, bg=BG_CARD, fg=FG_DIM,
                 font=(FONT_FAMILY, 9), justify="left", wraplength=320).pack(anchor="w")
        tk.Button(f, text="OK", bg=BG_SPEED_ROW, fg=FG_TEXT,
                  font=(FONT_FAMILY, 9, "bold"), bd=0, relief="flat",
                  cursor="hand2", padx=18, pady=4,
                  command=win.destroy).pack(pady=(10, 0))
        win.bind("<Escape>", lambda _e: win.destroy())
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{(sw - win.winfo_width()) // 2}+{(sh - win.winfo_height()) // 2}")
        win.after(60, lambda: win.focus_force())

    def _window_rect_overlaps(self, x: int, y: int, w: int, h: int,
                              rect: Tuple[int, int, int, int]) -> bool:
        left, top, right, bottom = rect
        return x < right and x + w > left and y < bottom and y + h > top

    def _taskbar_rect_cached(self, force: bool = False) -> Optional[Tuple[int, int, int, int]]:
        now = time.monotonic()
        if force or self._cached_taskbar is None or now - self._last_taskbar_probe >= TASKBAR_PROBE_INTERVAL:
            try:
                cx = self.root.winfo_x() + self.window_width // 2
                cy = self.root.winfo_y() + self._card_h // 2
            except tk.TclError:
                cx = cy = None
            self._cached_taskbar = taskbar_bounds(cx, cy)
            self._last_taskbar_probe = now
        return self._cached_taskbar

    def _position_in_taskbar(self, x: int, y: int) -> bool:
        taskbar = taskbar_bounds(x + self.window_width // 2, y + self._card_h // 2)
        if not taskbar:
            return False
        return self._window_rect_overlaps(x, y, self.window_width, self._card_h, taskbar)

    def _raise_windows(self, force: bool = False) -> None:
        """Keep both layers above an always-on-top Taskbar without stealing focus.

        Two complementary techniques are used so the widget survives the
        aggressive z-order re-assertion of the *secondary* taskbar
        (Shell_SecondaryTrayWnd), which buries a plain HWND_TOPMOST widget:

          1. Re-bind each window's owner to the *nearest* taskbar HWND so an
             owned window always rides above its owner.
          2. Re-assert WS_EX_TOPMOST (top of the topmost band) and *then* park
             the window immediately above that specific taskbar via
             SetWindowPos(hWndInsertAfter = taskbar_hwnd). Inserting above the
             concrete taskbar — instead of only HWND_TOPMOST — is what keeps the
             widget visible when the shell re-asserts the taskbar on top.
        """
        now = time.monotonic()
        if not force and now - self._last_raise < 0.12:
            return
        self._last_raise = now
        # Mark the adaptive z-order loop as "active" so it keeps re-raising
        # fast for a grace period after an explicit raise (drag, display swap).
        if force:
            self._zorder_last_active = now
        self._bind_to_taskbar_owner()
        try:
            self.root.attributes("-topmost", True)
            if self.bg_window is not None:
                self.bg_window.attributes("-topmost", True)
        except tk.TclError:
            pass
        u = user32()
        if u is None:
            return
        # The specific taskbar HWND on this monitor (primary or secondary).
        # _bind_to_taskbar_owner() keeps this cached/updated.
        target_tray = self._current_owner_tray
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
        # Background first, root second so the text layer ends up on top.
        for window in (self.bg_window, self.root):
            if window is None:
                continue
            try:
                hwnd = self._hwnd(window)
                if not hwnd:
                    continue
                # 1) Guarantee WS_EX_TOPMOST membership of the topmost band.
                u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                # 2) Reorder to sit directly above THIS monitor's taskbar so
                #    the shell's own topmost re-assertion can no longer jump
                #    in between the widget and the taskbar.
                if target_tray:
                    u.SetWindowPos(hwnd, target_tray, 0, 0, 0, 0, flags)
            except Exception:
                pass
        try:
            if self.bg_window is not None:
                self.bg_window.lift()
            self.root.lift()
        except tk.TclError:
            pass

    def _zorder_loop(self) -> None:
        """High-frequency, adaptive re-assertion of the taskbar z-order.

        Runs on its own timer independently of the 1-second ``_tick`` so the
        widget can no longer be permanently buried by the secondary taskbar's
        re-assertion between ticks. The interval is **adaptive**: right after
        the widget had to fight for z-order (drag, primary-display swap,
        manual ``force=True`` raise) it re-asserts at
        :data:`ZORDER_INTERVAL_ACTIVE`; once it has been stable for
        :data:`ZORDER_IDLE_GRACE` seconds it throttles to
        :data:`ZORDER_INTERVAL_IDLE` to save CPU. A hidden widget (iconified
        or fully buried) still gets re-raised so it pops back on top.
        """
        if self._closing:
            return
        try:
            self._raise_windows()
        except Exception:
            log.debug("zorder loop failed", exc_info=True)
        now = time.monotonic()
        active = now - self._zorder_last_active < ZORDER_IDLE_GRACE
        interval = ZORDER_INTERVAL_ACTIVE if active else ZORDER_INTERVAL_IDLE
        self._zorder_after_id = self.root.after(
            int(interval * 1000), self._zorder_loop)

    def _on_configure(self, _event: "tk.Event") -> None:
        """Re-measure the layout when the window lands on a different-DPI monitor.

        Tkinter does not expose ``WM_DPICHANGED``; instead we poll the effective
        DPI scale on every ``<Configure>`` (which fires when the window moves)
        and re-measure the card if the scale changed. This keeps the card crisp
        when dragged between a 100% and a 150% monitor.
        """
        if self._closing:
            return
        try:
            current = max(1.0, float(self.root.winfo_fpixels("1i")) / 96.0)
        except tk.TclError:
            return
        if abs(current - self._last_dpi_scale) > 0.05:
            self._last_dpi_scale = current
            self._measure_layout()
            self._refresh_layout()
            self._raise_windows(force=True)

    def _atexit_flush(self) -> None:
        """Belt-and-braces flush of daily totals on interpreter exit.

        Covers the case where Windows sends ``WM_QUERYENDSESSION`` (logoff /
        shutdown) which routes through ``WM_DELETE_WINDOW`` → :meth:`quit`;
        if the normal quit path is skipped (hard kill), atexit still runs and
        persists the last known totals so no more than ~1s of traffic is lost.
        """
        try:
            if getattr(self, "_closing", True):
                return
            self.totals.flush()
        except Exception:
            pass

    def _sparkline_push(self, down_bps: float, up_bps: float) -> None:
        """Append one sample to the rolling speed history (called each tick)."""
        self._spark_down.append(max(0.0, down_bps))
        self._spark_up.append(max(0.0, up_bps))
        if len(self._spark_down) > SPARKLINE_SAMPLES:
            self._spark_down.pop(0)
            self._spark_up.pop(0)

    def _refresh_net_info(self) -> None:
        """Refresh cached local/public IP and Wi-Fi signal (off the UI thread).

        Runs at most every ~30s; public IP is fetched from ipify (best-effort,
        fails silently to "--"). Wi-Fi signal uses ``netsh wlan`` parsing which
        is the only dependency-free way to read it on Windows without admin.
        """
        now = time.monotonic()
        if now - self._net_info_last < 30.0:
            return
        self._net_info_last = now
        threading.Thread(target=self._fetch_net_info, daemon=True).start()

    def _fetch_net_info(self) -> None:
        info = dict(self._net_info)
        # Local IPv4 of the active adapter.
        try:
            if self.adapter == ALL_ADAPTERS:
                # Pick the first non-loopback IPv4 across all interfaces.
                for _name, addrs in psutil.net_if_addrs().items():
                    for a in addrs:
                        if a.family == socket.AF_INET and not a.address.startswith("127."):
                            info["local_ip"] = a.address
                            raise _StopLoop
            else:
                addrs = psutil.net_if_addrs().get(self.adapter, [])
                for a in addrs:
                    if a.family == socket.AF_INET:
                        info["local_ip"] = a.address
                        break
        except _StopLoop:
            pass
        except Exception:
            log.debug("local ip read failed", exc_info=True)
        # Public IP (best-effort; never block the UI).
        try:
            req = urllib.request.Request("https://api.ipify.org",
                                         headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(req, timeout=4) as resp:
                info["public_ip"] = resp.read().decode("ascii", "ignore").strip() or "--"
        except Exception:
            info["public_ip"] = "--"
        # Wi-Fi signal strength (%) via netsh — Windows-only, no admin needed.
        if IS_WINDOWS:
            try:
                out = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                                     capture_output=True, text=True, timeout=4,
                                     creationflags=CREATE_NO_WINDOW)
                for line in (out.stdout or "").splitlines():
                    if "Signal" in line and "%" in line:
                        info["wifi"] = line.split(":", 1)[1].strip()
                        break
            except Exception:
                info["wifi"] = "--"
        else:
            info["wifi"] = "--"
        self._net_info = info

    def _sample_proc_speed(self) -> None:
        """Best-effort per-process network speed sampling.

        Exact per-process bandwidth needs ETW (admin + complex). Instead we
        sample each process's cumulative IO byte counters (``io_read_bytes``
        and ``io_write_bytes`` approximate network+disk IO; for network-heavy
        apps they correlate well) and derive a bytes/sec delta. This is a
        *sampled approximation*, not a precise per-process speed — see Known
        Limitations in the README. Runs on the tick thread, cheap because we
        only scan the top-N connection holders from the ProcessScanner.
        """
        try:
            now = time.monotonic()
            rows = self.scanner.snapshot()
            names = []
            for row in rows:
                # rows look like "  chrome.exe                12 conn"
                stripped = row.strip()
                if not stripped or stripped.startswith("+") or "conn" not in stripped:
                    continue
                parts = stripped.split()
                if parts:
                    names.append(parts[0])
            if not names:
                self._proc_speed.clear()
                return
            result: Dict[str, Tuple[int, int]] = {}
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    pname = proc.info["name"] or ""
                    if not any(pname.startswith(n) or n in pname for n in names):
                        continue
                    io = proc.io_counters()
                    pid = proc.pid
                    last = self._proc_io_last.get(pid)
                    self._proc_io_last[pid] = (io.read_bytes, io.write_bytes)
                    if last is None:
                        continue
                    dt = max(0.001, now - getattr(self, "_proc_speed_last", now))
                    down_bps = max(0, io.read_bytes - last[0]) / dt
                    up_bps = max(0, io.write_bytes - last[1]) / dt
                    prev = result.get(pname, (0, 0))
                    result[pname] = (int(prev[0] + down_bps), int(prev[1] + up_bps))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            self._proc_speed = result
            self._proc_speed_last = now
        except Exception:
            log.debug("per-process speed sample failed", exc_info=True)

    def _enforce_taskbar_dock(self) -> None:
        if not self._taskbar_docked or not self.config.get("snap_edges"):
            return
        taskbar = self._taskbar_rect_cached()
        if not taskbar:
            return
        tl, tt, tr, tb = taskbar
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if tr - tl >= tb - tt:
            x = max(tl, min(self.root.winfo_x(), tr - w))
            # Keep the widget inside the Taskbar, aligned to its inner bottom edge.
            y = tt if tt == 0 else max(tt, tb - h)
        else:
            x = tl if tl == 0 else tr - w
            y = max(tt, min(self.root.winfo_y(), tb - h))
        if (self.root.winfo_x(), self.root.winfo_y()) != (x, y):
            self._move_windows(x, y)

    def _move_windows(self, x: int, y: int) -> None:
        self._suppress_bg_sync = True
        try:
            self._sync_layer_geometry(int(x), int(y), self._card_w, self._card_h)
        finally:
            self._suppress_bg_sync = False

    def _default_position(self) -> Tuple[int, int]:
        w, h = self.window_width, self._card_h
        taskbar = taskbar_bounds(self.root.winfo_screenwidth() // 2,
                                self.root.winfo_screenheight() - 1)
        work = monitor_work_area(self.root.winfo_screenwidth() // 2,
                                 self.root.winfo_screenheight() // 2)
        if taskbar and work:
            tl, tt, tr, tb = taskbar
            wl, wt, wr, wb = work
            # Bottom/top taskbar: center vertically inside its real rectangle.
            if tb - tt >= h and tr - tl > w * 2:
                target_y = tt + ((tb - tt - h) // 2 if h <= tb - tt else tb - h)
                return max(tl, min(tr - w - 190, wr - w)), target_y
            # Left/right taskbar: center horizontally inside its real rectangle.
            if tr - tl >= w and tb - tt > h * 2:
                target_x = tl + (tr - tl - w) // 2 if w <= tr - tl else (tl if tl == 0 else tr - w)
                return target_x, max(tt, min(tb - h - 12, wb - h))
        if work:
            return work[2] - w - EDGE_MARGIN, work[3] - h - EDGE_MARGIN
        return (self.root.winfo_screenwidth() - w - EDGE_MARGIN,
                self.root.winfo_screenheight() - h - EDGE_MARGIN)

    def _restore_position(self) -> None:
        self._apply_geometry()
        x, y = self.config.get("x"), self.config.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or not self._on_screen(x, y):
            x, y = self._default_position()
        x, y = self._clamp_to_work_area(int(x), int(y))
        if self.config.get("snap_edges"):
            x, y = self._snap_position(x, y)
        self._apply_geometry(x, y)
        self._taskbar_docked = self._position_in_taskbar(x, y)
        self._raise_windows(force=True)

    def _on_screen(self, x: int, y: int) -> bool:
        bounds = enum_monitor_bounds()
        return not bounds or any(left <= x < right and top <= y < bottom for left, top, right, bottom in bounds)

    def _clamp_to_work_area(self, x: int, y: int) -> Tuple[int, int]:
        area = monitor_work_area(x + self.window_width // 2, y + self._card_h // 2)
        if area is None:
            return x, y
        left, top, right, bottom = area
        return max(left, min(x, right - self.window_width)), max(top, min(y, bottom - self._card_h))

    def _snap_position(self, x: int, y: int) -> Tuple[int, int]:
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        taskbar = taskbar_bounds(x + w // 2, y + h // 2)
        if taskbar:
            tl, tt, tr, tb = taskbar
            overlap = x < tr and x + w > tl and y < tb and y + h > tt
            near = (x + w > tl and x < tr and
                    (abs(y + h - tt) <= SNAP_DISTANCE or abs(y - tt) <= SNAP_DISTANCE or
                     abs(x + w - tl) <= SNAP_DISTANCE or abs(x - tr) <= SNAP_DISTANCE))
            if overlap or near:
                if tr - tl > tb - tt:
                    return max(tl, min(x, tr - w)), tt if tt == 0 else max(tt, tb - h)
                target_x = tl if tl == 0 else tr - w
                return target_x, max(tt, min(y, tb - h))
        area = monitor_work_area(x + w // 2, y + h // 2)
        if area is None:
            return x, y
        left, top, right, bottom = area
        if abs(x - left) <= SNAP_DISTANCE: x = left + EDGE_MARGIN
        elif abs(x + w - right) <= SNAP_DISTANCE: x = right - w - EDGE_MARGIN
        if abs(y - top) <= SNAP_DISTANCE: y = top + EDGE_MARGIN
        elif abs(y + h - bottom) <= SNAP_DISTANCE: y = bottom - h - EDGE_MARGIN
        return max(left, min(x, right - w)), max(top, min(y, bottom - h))

    def reset_position(self) -> None:
        x, y = self._default_position()
        x, y = self._snap_position(x, y)
        self._apply_geometry(x, y)
        self._taskbar_docked = self._position_in_taskbar(x, y)
        self._raise_windows(force=True)
        self._save_position()

    def _save_position(self) -> None:
        self.config.set("x", int(self.root.winfo_x()))
        self.config.set("y", int(self.root.winfo_y()), save=True)

    def reset_totals(self) -> None:
        self.totals.reset_today()
        if self.tooltip.visible:
            self.tooltip.show(self._tooltip_data(), self.root)

    def toggle_lock(self) -> None:
        self.locked = not self.locked
        self.lock_var.set(self.locked)
        self.config.set("locked", self.locked, save=True)
        self._update_lock_indicator()
        if self.locked:
            self._save_position()

    def _update_lock_indicator(self) -> None:
        self._draw_card(self._card_w, self._card_h)

    def _flash_lock(self) -> None:
        if self._flash_after_id is not None:
            try: self.root.after_cancel(self._flash_after_id)
            except tk.TclError: pass
            self._flash_after_id = None
        self._lock_flash = True
        self._draw_card(self._card_w, self._card_h)
        self._flash_after_id = self.root.after(450, self._clear_lock_flash)

    def _clear_lock_flash(self) -> None:
        self._flash_after_id = None
        self._lock_flash = False
        self._draw_card(self._card_w, self._card_h)

    def _bind_events(self) -> None:
        # Double-click used to quit the app instantly and Escape killed it too;
        # both were far too easy to trigger by accident. Double-click now
        # toggles compact mode and exit lives in the right-click menu only.
        for widget in self._all_widgets():
            widget.bind("<Button-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_move)
            widget.bind("<ButtonRelease-1>", self._on_drag_end)
            widget.bind("<Button-3>", self._on_right_click)
            widget.bind("<Double-Button-1>", self._on_double_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
        self.root.bind("<FocusIn>", lambda _event: self._raise_windows(force=True))
        self.root.bind("<Visibility>", lambda _event: self._raise_windows(force=True))
        if self.bg_window is not None:
            self.bg_window.bind("<FocusIn>", lambda _event: self._raise_windows(force=True))
            self.bg_window.bind("<Visibility>", lambda _event: self._raise_windows(force=True))
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.bind("<Escape>", lambda _event: self.tooltip.hide())

    def _on_double_click(self, _event: "tk.Event") -> None:
        self.tooltip.hide()
        self.compact_var.set(not self.compact_var.get())
        self._on_toggle_compact()

    def _on_enter(self, _event: "tk.Event") -> None:
        self._cancel_tip_timers()
        self._set_faded(False)
        self._tip_after_id = self.root.after(TOOLTIP_DELAY_MS, self._show_tooltip)

    def _on_leave(self, _event: "tk.Event") -> None:
        self._cancel_tip_timers()
        self._hide_after_id = self.root.after(120, self.tooltip.hide)

    def _cancel_tip_timers(self) -> None:
        for attr in ("_tip_after_id", "_hide_after_id"):
            handle = getattr(self, attr)
            if handle is not None:
                try: self.root.after_cancel(handle)
                except tk.TclError: pass
                setattr(self, attr, None)

    def _show_tooltip(self) -> None:
        # net_connections() is expensive and the tooltip never showed the
        # process list; only the dashboard needs a scan.
        self.tooltip.show(self._tooltip_data(), self.root)

    def _tooltip_data(self) -> Dict[str, Any]:
        cpu_text, ram_text = self.sysload.text_short()
        self.ping.maybe_probe()
        info = self._net_info
        net_line = (f"local {info.get('local_ip','--')}   "
                    f"public {info.get('public_ip','--')}   "
                    f"wifi {info.get('wifi','--')}")
        # Top-3 processes by sampled download bandwidth.
        proc_rows = sorted(self._proc_speed.items(), key=lambda kv: kv[1][0], reverse=True)[:3]
        proc_text = "\n".join(
            f"  {shorten(name,18).ljust(18)} \u2193{format_speed(d):>9}  \u2191{format_speed(u):>9}"
            for name, (d, u) in proc_rows) or "  --"
        return {
            "down": format_speed(self.last_down),
            "up": format_speed(self.last_up),
            "cpu": cpu_text.replace("CPU ", ""),
            "ram": ram_text.replace("RAM ", ""),
            "ping": self.ping.value,
            "adapter": shorten("All adapters" if self.adapter == ALL_ADAPTERS else self.adapter, 22),
            "session": (f"today {format_bytes(self.totals.daily_down + self.totals.daily_up)}"
                        f"  ·  up {format_duration(self.totals.session_seconds)}"
                        f"  ·  peak {format_speed(self.totals.peak_down)}"),
            "_spark": (list(self._spark_down), list(self._spark_up)),
            "_net": net_line,
            "_proc": proc_text,
        }

    def _on_drag_start(self, event: "tk.Event") -> None:
        if self.locked:
            self._flash_lock()
            return
        self._drag_offset = event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y()

    def _on_drag_move(self, event: "tk.Event") -> None:
        if self.locked or self._drag_offset is None: return
        self.tooltip.hide()
        dx, dy = self._drag_offset
        x = event.x_root - dx
        y = event.y_root - dy
        self._move_windows(x, y)

    def _on_drag_end(self, _event: "tk.Event") -> None:
        if self._drag_offset is None: return
        self._drag_offset = None
        if self.config.get("snap_edges"):
            x, y = self._snap_position(self.root.winfo_x(), self.root.winfo_y())
            self._move_windows(x, y)
        self._bind_to_taskbar_owner(force=True)
        self._taskbar_docked = self._position_in_taskbar(self.root.winfo_x(), self.root.winfo_y())
        self._raise_windows(force=True)
        self._save_position()

    def _on_right_click(self, event: "tk.Event") -> None:
        self.tooltip.hide()
        self.context_panel.show(event.x_root, event.y_root)

    def _on_toggle_autostart(self) -> None:
        wanted = bool(self.autostart_var.get())
        if not set_autostart(wanted): self.autostart_var.set(not wanted)

    def _tick(self) -> None:
        if self._closing: return
        try:
            down, up, down_bytes, up_bytes = self.monitor.sample()
            self.last_down, self.last_up = down, up
            self.totals.add(down_bytes, up_bytes)
            self.totals.note_speed(down, up)
            # Feed the rolling sparkline history (bytes/s -> keep raw).
            self._sparkline_push(down_bytes, up_bytes)
            self._refresh_labels(down, up)
            self._update_idle_state(down, up)
        except Exception:
            log.debug("sample failed", exc_info=True)
        now = time.monotonic()
        needs_system = self._include_sysload() or self.tooltip.visible
        if needs_system and now - self._last_system_sample >= SYSTEM_REFRESH_MS / 1000.0:
            try:
                self._update_system_labels()
            except Exception:
                log.debug("system sample failed", exc_info=True)
        try:
            # Latency probe runs on its own throttle (non-blocking).
            self.ping.maybe_probe()
            # Refresh local/public IP + Wi-Fi signal lazily (~30s).
            self._refresh_net_info()
            # Per-process speed sampling (~every tick is fine; it is cheap
            # because we only iterate the connection-holder names).
            if now - getattr(self, "_proc_speed_last", 0.0) >= 1.0:
                self._sample_proc_speed()
            # React to the Windows High Contrast accessibility theme being
            # toggled while the app runs; the card repaints with system colors.
            hc = is_high_contrast()
            if hc != self._high_contrast:
                self._high_contrast = hc
                self._card_shapes = []
                self._draw_card(self._card_w, self._card_h)
            self._enforce_taskbar_dock()
            self._raise_windows()
            if self.bg_window is not None and not self._suppress_bg_sync:
                rx, ry = self.root.winfo_x(), self.root.winfo_y()
                if (self.bg_window.winfo_x(), self.bg_window.winfo_y()) != (rx, ry):
                    self._sync_layer_geometry(rx, ry, self._card_w, self._card_h)
            if now - self._last_adapter_refresh >= ADAPTER_REFRESH_INTERVAL:
                self.refresh_adapters()
                self._last_adapter_refresh = now
            if self.locked: self._enforce_locked_position()
            if self.tooltip.visible and now - self._last_tooltip_refresh >= TOOLTIP_REFRESH_INTERVAL:
                self.tooltip.show(self._tooltip_data(), self.root)
                self._last_tooltip_refresh = now
        except Exception:
            log.debug("tick housekeeping failed", exc_info=True)
        self._after_id = self.root.after(REFRESH_MS, self._tick)

    def _update_idle_state(self, down: float, up: float) -> None:
        if not self.config.get("auto_hide"): return
        if max(down, up) < IDLE_BPS:
            self._idle_ticks += 1
            if self._idle_ticks >= IDLE_TICKS: self._set_faded(True)
        else:
            self._idle_ticks = 0
            self._set_faded(False)

    def _idle_alpha(self) -> float:
        return max(0.12, round(self.opacity * IDLE_FACTOR, 2))

    def _set_faded(self, faded: bool) -> None:
        if faded == self._faded: return
        self._faded = faded
        try:
            # Fade the text layer too: fading only the card left the numbers
            # at full strength, so auto-hide barely did anything.
            self.root.attributes("-alpha", self._idle_alpha() if faded else 1.0)
            if self.bg_window is not None:
                self.bg_window.attributes("-alpha", self._idle_alpha() if faded else self._window_alpha())
        except tk.TclError:
            pass

    def _enforce_locked_position(self) -> None:
        x, y = self.config.get("x"), self.config.get("y")
        if isinstance(x, int) and isinstance(y, int) and (self.root.winfo_x(), self.root.winfo_y()) != (x, y):
            self._move_windows(x, y)

    def _refresh_labels(self, down: float, up: float) -> None:
        alert_bps = self._alert_bps
        down_text = format_speed(down)
        up_text = format_speed(up)
        self._set_text("down_value", down_text,
                       FG_ALERT if alert_bps and down >= alert_bps else FG_DOWN)
        self._set_text("up_value", up_text,
                       FG_ALERT if alert_bps and up >= alert_bps else FG_UP)

    def render_state(self) -> Dict[str, Any]:
        """Return the geometry/opacity contract used by visual regression tests."""
        return {
            "version": APP_VERSION,
            "width": int(self._card_w),
            "height": int(self._card_h),
            "text_alpha": 1.0,
            "background_alpha": float(self._window_alpha()),
            "layers_aligned": (
                self.bg_window is None or
                (self.root.winfo_x(), self.root.winfo_y()) ==
                (self.bg_window.winfo_x(), self.bg_window.winfo_y())
            ),
        }

    def quit(self) -> None:
        if self._closing: return
        self._closing = True
        for handle in (self._after_id, self._tip_after_id, self._hide_after_id,
                       self._flash_after_id, self._save_after_id,
                       self._zorder_after_id):
            if handle is not None:
                try: self.root.after_cancel(handle)
                except tk.TclError: pass
        self._after_id = self._tip_after_id = self._hide_after_id = None
        self._flash_after_id = self._save_after_id = None
        self._zorder_after_id = None
        self.tooltip.hide()
        self.context_panel.close()
        self.opacity_popup.close()
        self._save_position()
        self.totals.flush()
        try:
            if self.bg_window is not None:
                self.bg_window.destroy()
        except tk.TclError:
            pass
        try: self.root.destroy()
        except tk.TclError: pass

    def run(self) -> None:
        try: self.root.mainloop()
        except KeyboardInterrupt: self.quit()


_instance_mutex: Any = None


def claim_single_instance() -> bool:
    """A second launch used to stack another widget on the taskbar."""
    global _instance_mutex
    if not IS_WINDOWS:
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        _instance_mutex = kernel32.CreateMutexW(None, 1, f"Local\\{APP_NAME}_singleton")
        return kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    except Exception:
        return True


def main() -> int:
    setup_logging()
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    # NetSpeedTray is Windows-only: the z-order/taskbar glue, the autostart
    # registry key and the high-contrast/DPI helpers all call into user32.
    # Bail out cleanly on macOS/Linux instead of crashing inside Tk.
    if not IS_WINDOWS:
        print(f"{APP_NAME} {APP_VERSION} is Windows-only.", file=sys.stderr)
        print("It uses the Windows taskbar/DPI/registry APIs and does not run "
              "on macOS or Linux.", file=sys.stderr)
        return 1
    # Multi-DPI V2 awareness for crisp rendering across multi-monitor setups.
    # Named constants kept next to their use; the values are documented in the
    # constants block at the top of the file.
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(DPI_AWARENESS_PER_MONITOR_V2))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(DPI_AWARENESS_PER_MONITOR)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    if "--enable-autostart" in sys.argv:
        print("Auto-start enabled" if set_autostart(True) else "Failed")
        return 0
    if "--disable-autostart" in sys.argv:
        print("Auto-start disabled" if set_autostart(False) else "Failed")
        return 0
    if "--reset-config" in sys.argv:
        try:
            os.remove(CONFIG_PATH)
            print(f"Removed {CONFIG_PATH}")
        except OSError:
            print("No config file to remove")
        return 0
    if "--check-updates" in sys.argv:
        checker = UpdateChecker()
        data = checker.fetch_latest()
        if data is None:
            print(f"Update check failed: {checker.error}")
            return 1
        latest = UpdateChecker.latest_version(data)
        print(f"Current: {APP_VERSION}  Latest: {latest}")
        if UpdateChecker.is_newer(latest, APP_VERSION):
            print("Update available.")
            return 2
        print("Up to date.")
        return 0
    if not claim_single_instance():
        log.warning("another instance is already running")
        try:
            ctypes.windll.user32.MessageBoxW(
                0, f"{APP_NAME} is already running.", APP_NAME, MB_ICONINFORMATION)
        except Exception:
            pass
        return 0
    try:
        SpeedWidget().run()
    except Exception:
        log.exception("fatal error")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
