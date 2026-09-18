from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.error
import urllib.request
import webbrowser
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import psutil
except ImportError:
    _MSG = "psutil is required.\n\nInstall it with:\n    pip install psutil"
    try:
        ctypes.windll.user32.MessageBoxW(0, _MSG, "NetSpeedTray", 0x10)
    except Exception:
        print(_MSG, file=sys.stderr)
    raise SystemExit(1)

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "NetSpeedTray"
APP_VERSION = "2.5.0"
DEVELOPER_LINE = "Design and Developer: Ali Rahmani  (github.com/raali09)"
CONTACT_EMAIL = "rahmaniali09@gmail.com"
GITHUB_REPO = "raali09/NetSpeedTray"
GITHUB_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

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
TASKBAR_ALLOWANCE = 48
UPDATE_CHECK_DELAY_MS = 1800

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
FG_LOCK_ACTIVE = "#E9B85D"
FG_DIM = "#AAB5C1"
FG_CHECK = "#55C7F3"

BG_TRANSPARENT_KEY = "#0A0B0C"
FG_TRANSPARENT_KEY = "#0D0E0F"
SHADOW_COLOR = "#071019"
TEXT_SHADOW_OFFSET = 1

FONT_FAMILY = "Segoe UI Variable Text"
FONT_ICON = (FONT_FAMILY, 8, "bold")
FONT_VALUE = (FONT_FAMILY, 8, "bold")
FONT_SYSTEM = (FONT_FAMILY, 7, "bold")
FONT_TIP = (FONT_FAMILY, 8)
FONT_MENU = (FONT_FAMILY, 9)

DEFAULT_OPACITY = 0.94
MIN_OPACITY = 0.20
MAX_OPACITY = 1.00
IDLE_FACTOR = 0.28
IDLE_BPS = 1024
IDLE_TICKS = 5
ALL_ADAPTERS = "__all__"
ALERT_CHOICES = (0.0, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0)
UI_VERSION = 21

WINDOW_WIDTH = 0
CARD_BORDER = 1
CORNER_RADIUS = 7
CONTENT_PAD_X = 2
CONTENT_PAD_Y = 0
ICON_GAP = 1
SEP_PAD = 1
VALUE_SAMPLE = "999 MB/s"
BADGE_SAMPLE = "CPU 100%"
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
MONITOR_DEFAULTTONEAREST = 2
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_CONFIG: Dict[str, Any] = {
    "x": None, "y": None, "locked": False, "opacity": DEFAULT_OPACITY,
    "adapter": ALL_ADAPTERS, "show_sysload": True, "compact": False, "ui_version": UI_VERSION,
    "auto_hide": False, "snap_edges": True, "alert_mbps": 0.0,
    "daily_date": "", "daily_down": 0, "daily_up": 0,
    "check_updates_on_start": True,
}
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]


def user32():
    if not IS_WINDOWS:
        return None
    try:
        return ctypes.windll.user32
    except Exception:
        return None


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
    proto = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulonglong, ctypes.c_ulonglong,
                              ctypes.POINTER(RECT), ctypes.c_double)

    def callback(_hmon, _hdc, rect_ptr, _data):
        r = rect_ptr.contents
        bounds.append((r.left, r.top, r.right, r.bottom))
        return 1
    try:
        u.EnumDisplayMonitors(0, 0, proto(callback), 0)
    except Exception:
        return []
    return bounds


def taskbar_bounds() -> Optional[Tuple[int, int, int, int]]:
    """Return the actual taskbar bounds, including vertical taskbars."""
    u = user32()
    if u is None:
        return None
    try:
        hwnd = u.FindWindowW("Shell_TrayWnd", None)
        if not hwnd:
            return None
        rect = RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None


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
        if not isinstance(self.data.get("adapter"), str):
            self.data["adapter"] = ALL_ADAPTERS
        for flag in ("locked", "show_sysload", "auto_hide", "snap_edges", "check_updates_on_start"):
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

    def migrate(self) -> None:
        try:
            old_version = int(self.data.get("ui_version", 0))
        except (TypeError, ValueError):
            old_version = 0
        if old_version < UI_VERSION:
            if "show_sysload" not in self.loaded_keys or old_version < 2:
                self.data["show_sysload"] = True
            if old_version < 6:
                self.data["check_updates_on_start"] = True
            self.data["ui_version"] = UI_VERSION
            self.save()

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, save: bool = False) -> None:
        self.data[key] = value
        if save:
            self.save()


def list_adapters() -> List[str]:
    try:
        counters = psutil.net_io_counters(pernic=True) or {}
        stats = psutil.net_if_stats() or {}
    except Exception:
        return []
    names = list(counters)
    up = [n for n in names if getattr(stats.get(n), "isup", True)]
    return sorted(up) + sorted(n for n in names if n not in up)


def adapter_is_up(name: str) -> bool:
    try:
        entry = (psutil.net_if_stats() or {}).get(name)
        return bool(getattr(entry, "isup", True)) if entry else False
    except Exception:
        return True


def format_speed(value: float) -> str:
    """Compact, stable speed text suitable for a taskbar-sized widget."""
    kb = max(0.0, value) / 1024.0
    if kb >= 1024.0:
        mb = kb / 1024.0
        return f"{mb:.0f} MB/s" if mb >= 100 else f"{mb:.1f} MB/s"
    if kb < 0.5:
        return "0 KB/s"
    return f"{kb:.0f} KB/s"


def format_bytes(total: float) -> str:
    if total < 1024:
        return f"{int(total)} B"
    for unit in ("KB", "MB", "GB", "TB"):
        total /= 1024.0
        if total < 1024:
            return f"{total:.{0 if unit == 'KB' else 2}f} {unit}"
    return f"{total:.2f} PB"


def format_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}h {minutes:02d}m" if hours else (f"{minutes}m {secs:02d}s" if minutes else f"{secs}s")


def shorten(name: str, width: int = 32) -> str:
    return name if len(name) <= width else name[:width - 1] + "\u2026"


def compare_versions(a: str, b: str) -> int:
    def parts(v: str) -> List[int]:
        out: List[int] = []
        for part in v.lstrip("vV").split("."):
            digits = ""
            for ch in part:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            try:
                out.append(int(digits) if digits else 0)
            except ValueError:
                out.append(0)
        return out
    pa, pb = parts(a), parts(b)
    while len(pa) < len(pb):
        pa.append(0)
    while len(pb) < len(pa):
        pb.append(0)
    for x, y in zip(pa, pb):
        if x != y:
            return -1 if x < y else 1
    return 0


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
        if self.config.get("daily_date") != today:
            self.config.set("daily_date", today)
            self.daily_down = self.daily_up = 0
        self.session_down += down_bytes
        self.session_up += up_bytes
        self.daily_down += down_bytes
        self.daily_up += up_bytes
        if time.monotonic() - self._last_save >= TOTALS_SAVE_INTERVAL:
            self.flush()

    def flush(self) -> None:
        self.config.set("daily_down", self.daily_down)
        self.config.set("daily_up", self.daily_up)
        self.config.save()
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
                    try:
                        name = psutil.Process(pid).name()
                    except Exception:
                        name = f"pid {pid}"
                    merged[name] = merged.get(name, 0) + count
                ranked = sorted(merged.items(), key=lambda item: item[1], reverse=True)
                rows = [f"  {shorten(name, 22).ljust(22)}{count:>3} conn" for name, count in ranked[:self.top_n]]
                if len(ranked) > self.top_n:
                    rows.append(f"  +{len(ranked) - self.top_n} more")
        except Exception:
            rows = ["unavailable"]
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
        try:
            req = urllib.request.Request(
                GITHUB_LATEST_URL,
                headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.latest = data if isinstance(data, dict) else None
            self.error = ""
            return self.latest
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
    if not getattr(sys, "frozen", False):
        return False
    current_exe = sys.executable
    if not current_exe or not os.path.exists(current_exe):
        return False
    updater_path = os.path.join(tempfile.gettempdir(), "netspeedtray_updater.bat")
    try:
        with open(updater_path, "w", encoding="utf-8") as fh:
            fh.write("@echo off\r\n")
            fh.write("timeout /t 2 /nobreak >nul\r\n")
            fh.write(f'del /f /q "{current_exe}" >nul 2>&1\r\n')
            fh.write(f'copy /y "{temp_exe}" "{current_exe}" >nul 2>&1\r\n')
            fh.write(f'del /f /q "{temp_exe}" >nul 2>&1\r\n')
            fh.write(f'start "" "{current_exe}"\r\n')
            fh.write('del /f /q "%~f0" >nul 2>&1\r\n')
    except OSError:
        return False
    try:
        subprocess.Popen(["cmd", "/c", updater_path],
                         creationflags=0x08000000, close_fds=True)
        return True
    except Exception:
        return False


class PingMonitor:
    """Non-blocking, cached latency probe using fast TCP handshake without subprocess overhead."""
    def __init__(self) -> None:
        self.value = "--"
        self._last = 0.0
        self._busy = False
        self._lock = threading.Lock()

    def maybe_probe(self, force: bool = False) -> None:
        now = time.monotonic()
        if self._busy or (not force and now - self._last < 8.0):
            return
        self._busy = True
        threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self) -> None:
        import socket
        result = "--"
        targets = [("1.1.1.1", 53), ("8.8.8.8", 53)]
        for host, port in targets:
            try:
                t0 = time.perf_counter()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.75)
                s.connect((host, port))
                latency = (time.perf_counter() - t0) * 1000.0
                s.close()
                result = f"{latency:.0f} ms"
                break
            except Exception:
                pass
        with self._lock:
            self.value = result
            self._last = time.monotonic()
            self._busy = False

class Tooltip:
    def __init__(self, parent: tk.Misc) -> None:
        self.parent, self.window = parent, None
        self.value_labels: Dict[str, tk.Label] = {}

    @property
    def visible(self) -> bool:
        return self.window is not None and self.window.winfo_exists()

    def _metric(self, parent: tk.Misc, key: str, title: str, color: str) -> None:
        cell = tk.Frame(parent, bg=BG_SPEED_ROW, padx=7, pady=5)
        cell.pack(side="left", fill="both", expand=True, padx=(0, 3))
        tk.Label(cell, text=title, bg=BG_SPEED_ROW, fg=FG_LABEL,
                 font=(FONT_FAMILY, 7), anchor="w").pack(anchor="w")
        label = tk.Label(cell, text="--", bg=BG_SPEED_ROW, fg=color,
                         font=(FONT_FAMILY, 9, "bold"), anchor="w")
        label.pack(anchor="w", pady=(1, 0))
        self.value_labels[key] = label

    def show(self, data: Dict[str, str], anchor: tk.Misc) -> None:
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
                     font=(FONT_FAMILY, 9, "bold")).pack(side="left")
            tk.Label(head, text="LIVE", bg=BG_CARD, fg=FG_DOWN,
                     font=(FONT_FAMILY, 7, "bold")).pack(side="right")
            self.speed_row = tk.Frame(inner, bg=BG_CARD)
            self.speed_row.pack(fill="x", pady=(0, 4))
            self._metric(self.speed_row, "down", "DOWNLOAD", FG_DOWN)
            self._metric(self.speed_row, "up", "UPLOAD", FG_UP)
            self.system_row = tk.Frame(inner, bg=BG_CARD)
            self.system_row.pack(fill="x", pady=(0, 5))
            self._metric(self.system_row, "cpu", "CPU", FG_CPU)
            self._metric(self.system_row, "ram", "RAM", FG_RAM)
            self._metric(self.system_row, "ping", "PING", FG_DIM)
            sep = tk.Frame(inner, height=1, bg=BORDER_SOFT)
            sep.pack(fill="x", pady=(2, 6))
            foot = tk.Frame(inner, bg=BG_CARD)
            foot.pack(fill="x")
            self.foot = tk.Label(foot, text="", bg=BG_CARD, fg=FG_LABEL,
                                 font=(FONT_FAMILY, 7), anchor="w")
            self.foot.pack(side="left")
            self.hint = tk.Label(foot, text="right-click: settings", bg=BG_CARD,
                                 fg=FG_LABEL, font=(FONT_FAMILY, 7), anchor="e")
            self.hint.pack(side="right")
        for key, value in data.items():
            label = self.value_labels.get(key)
            if label is not None:
                label.config(text=value)
        self.foot.config(text=f"{data.get('adapter','')}  ·  {data.get('session','')}")
        self._place(anchor)

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

        self._refresh_list()

        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.bind("<FocusOut>", lambda _e: self.window.after(200, self.close))
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

    def _schedule_refresh(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self._timer = self.parent.after(2500, self._tick_refresh)

    def _tick_refresh(self) -> None:
        self.widget.scanner.maybe_scan(force=True)
        self._refresh_list()
        self._schedule_refresh()

    def _refresh_list(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        rows = self.widget.scanner.snapshot()
        if not rows:
            rows = ["No active network connections"]
        for row_text in rows:
            line = tk.Frame(self.list_frame, bg=BG_SPEED_ROW)
            line.pack(fill="x", pady=1)
            tk.Label(line, text=row_text, bg=BG_SPEED_ROW, fg=FG_TEXT,
                     font=("Consolas", 8)).pack(anchor="w")


class ModernContextPanel:
    def __init__(self, widget: "SpeedWidget") -> None:
        self.widget = widget
        self.window: Optional[tk.Toplevel] = None
        self.dashboard: Optional[AppUsageDashboard] = None

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
        for item in (row, *row.winfo_children()):
            item.bind("<Button-1>", lambda _e: (command(), self._close()))
            item.bind("<Enter>", lambda _e, r=row: r.config(bg=BG_SPEED_ROW))
            item.bind("<Leave>", lambda _e, r=row: r.config(bg=BG_CARD))

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
        for item in (dev_frame, *dev_frame.winfo_children()):
            item.bind("<Button-1>", lambda _e: (self._open_github(), self._close()))
            item.bind("<Enter>", lambda _e: dev_frame.config(bg="#243343"))
            item.bind("<Leave>", lambda _e: dev_frame.config(bg=BG_SPEED_ROW))

        # Features & Settings Rows
        self._row(inner, "📊 App Network Usage", "Open", lambda: self._open_dashboard(x, y), accent=FG_DOWN)
        self._row(inner, "Lock position", "ON" if w.locked else "OFF", w.toggle_lock)
        self._row(inner, "Show CPU / RAM", "ON" if w.sysload_var.get() else "OFF",
                  lambda: (w.sysload_var.set(not w.sysload_var.get()), w._on_toggle_sysload()))
        self._row(inner, "Snap to Taskbar", "ON" if w.snap_var.get() else "OFF",
                  lambda: (w.snap_var.set(not w.snap_var.get()), w._on_toggle_snap()))
        self._row(inner, "Network adapter", shorten(w.adapter if w.adapter != ALL_ADAPTERS else "All adapters", 18),
                  lambda: w.adapter_menu.post(x, y))
        self._row(inner, "Transparency", f"{int(w.opacity * 100)}%", w._open_opacity_popup)

        sep = tk.Frame(inner, height=1, bg=BORDER_SOFT)
        sep.pack(fill="x", padx=6, pady=5)

        self._row(inner, "Reset position", "", w.reset_position)
        self._row(inner, "Check for updates", "", w._check_for_updates_manual)
        self._row(inner, "Exit", "", w.quit)

        self.window.bind("<Escape>", lambda _e: self._close())
        self.window.bind("<FocusOut>", lambda _e: self.window.after(120, self._close))
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

        self.scale = tk.Scale(inner, from_=MIN_OPACITY, to=MAX_OPACITY,
                             resolution=0.01, orient="horizontal",
                             variable=tk.DoubleVar(value=self.widget.opacity),
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
        self.scale = None
        self.value_label = None
        self.fill_bar = None


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
        self.opacity = float(self.config.get("opacity", DEFAULT_OPACITY))
        self.adapter = str(self.config.get("adapter", ALL_ADAPTERS))
        self.adapters = list_adapters()
        if self.adapter != ALL_ADAPTERS and self.adapter not in self.adapters:
            self.adapter = ALL_ADAPTERS
            self.config.set("adapter", ALL_ADAPTERS, save=True)

        self.monitor, self.totals = SpeedMonitor(self.adapter), TotalsTracker(self.config)
        self.sysload, self.scanner = SystemLoad(), ProcessScanner()
        self.ping = PingMonitor()
        self.update_checker = UpdateChecker()
        self.last_down = self.last_up = 0.0
        self._idle_ticks, self._faded, self._closing = 0, False, False
        self._last_system_sample = 0.0
        self._taskbar_docked = False
        self._last_raise = 0.0
        self._last_tooltip_refresh = 0.0
        self._last_adapter_refresh = time.monotonic()
        self._last_taskbar_probe = 0.0
        self._cached_taskbar: Optional[Tuple[int, int, int, int]] = None
        self._drag_offset: Optional[Tuple[int, int]] = None
        self._after_id = self._tip_after_id = self._hide_after_id = None
        self._lock_flash = False
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
        self._update_lock_indicator()
        self._refresh_layout()
        self._bind_events()
        self.root.after(80, self._first_system_sample)
        self.root.after(UPDATE_CHECK_DELAY_MS, self._maybe_check_updates_on_start)
        self._tick()

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

    def _text_size(self, text: str, font: Tuple[str, int, str]) -> Tuple[int, int]:
        probe = tk.Label(self.root, text=text, font=font)
        size = probe.winfo_reqwidth(), probe.winfo_reqheight()
        probe.destroy()
        return size

    def _measure_layout(self) -> None:
        self.ui_scale = max(1.0, float(self.root.winfo_fpixels("1i")) / 96.0)
        self.radius = int(round(CORNER_RADIUS * self.ui_scale))
        self.border = max(1, int(round(CARD_BORDER * self.ui_scale)))
        self.icon_px = self._text_size("\u2193", FONT_ICON)[0]
        self._value_px_max = self._text_size(VALUE_SAMPLE, FONT_VALUE)[0]
        self.badge_px = max(self._text_size("CPU 100%", FONT_SYSTEM)[0],
                            self._text_size("RAM 100%", FONT_SYSTEM)[0])
        self.row_h = max(self._text_size("0 KB/s", FONT_VALUE)[1],
                         self._text_size("\u2193", FONT_ICON)[1],
                         self._text_size("CPU --", FONT_SYSTEM)[1])
        self.value_px = self._value_px_max
        self._recompute_width()

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

    def _measure_text_width(self, text: str, font: Tuple[str, int, str]) -> int:
        if font not in self._font_cache:
            self._font_cache[font] = tkfont.Font(font=font)
        return self._font_cache[font].measure(text)

    def _update_value_width(self, down_text: str, up_text: str) -> None:
        # Fixed columns prevent distracting horizontal jumps.
        return

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
            self._make_text("down_icon", left, self._row_y(0), self._current_texts["down_icon"], FONT_ICON, self._current_colors["down_icon"], "w")
            self._make_text("down_value", speed_right, self._row_y(0), self._current_texts["down_value"], FONT_VALUE, self._current_colors["down_value"], "e")
            up_left = speed_right + SEP_PAD
            up_right = up_left + self.icon_px + ICON_GAP + self.value_px
            self._make_text("up_icon", up_left, self._row_y(0), self._current_texts["up_icon"], FONT_ICON, self._current_colors["up_icon"], "w")
            self._make_text("up_value", up_right, self._row_y(0), self._current_texts["up_value"], FONT_VALUE, self._current_colors["up_value"], "e")
        else:
            self._make_text("down_icon", left, self._row_y(0), self._current_texts["down_icon"], FONT_ICON, self._current_colors["down_icon"], "w")
            self._make_text("down_value", speed_right, self._row_y(0), self._current_texts["down_value"], FONT_VALUE, self._current_colors["down_value"], "e")
            self._make_text("up_icon", left, self._row_y(1), self._current_texts["up_icon"], FONT_ICON, self._current_colors["up_icon"], "w")
            self._make_text("up_value", speed_right, self._row_y(1), self._current_texts["up_value"], FONT_VALUE, self._current_colors["up_value"], "e")

        if self._include_sysload():
            sep_x = speed_right + SEP_PAD
            badge_right = self.window_width - self.border - CONTENT_PAD_X
            self._make_text("cpu_badge", badge_right, self._row_y(0),
                            self._current_texts["cpu_badge"], FONT_SYSTEM,
                            self._current_colors["cpu_badge"], "e")
            self._make_text("ram_badge", badge_right, self._row_y(1),
                            self._current_texts["ram_badge"], FONT_SYSTEM,
                            self._current_colors["ram_badge"], "e")
            if self.bg_canvas is not None:
                sep_top = self.border + CONTENT_PAD_Y + 2
                sep_bot = self._card_h - self.border - CONTENT_PAD_Y - 2
                self._sep_line = self.bg_canvas.create_line(
                    sep_x, sep_top, sep_x, sep_bot,
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
        return BG_CARD

    def _draw_card(self, width: int, height: int) -> None:
        if self.bg_canvas is None:
            return
        for item in self._card_shapes:
            self.bg_canvas.delete(item)
        inset = float(self.border)
        radius = min(self.radius, height / 2.0)
        shapes = self._rounded_rect(self.bg_canvas, 0.0, 0.0, float(width), float(height),
                                    radius, self._border_color())
        shapes += self._rounded_rect(self.bg_canvas, inset, inset, width - inset, height - inset,
                                     max(2.0, radius - inset), self._surface_color())
        self._card_shapes = shapes
        for item in shapes:
            self.bg_canvas.tag_lower(item)

    def _border_color(self) -> str:
        if self._lock_flash:
            return FG_ALERT
        return FG_LOCK_ACTIVE if self.locked else BORDER_COLOR

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
        self.canvas.config(width=self.window_width, height=height)
        if x is None or y is None:
            x, y = self.root.winfo_x(), self.root.winfo_y()
        self._sync_layer_geometry(int(x), int(y), self.window_width, height)
        if self.canvas is not None:
            self.canvas.config(width=self.window_width, height=height)
        if self.bg_window is not None and self.bg_canvas is not None:
            self.bg_canvas.config(width=self.window_width, height=height)
            self.bg_window.geometry(f"{self.window_width}x{height}+{int(x)}+{int(y)}")
            self._draw_card(self.window_width, height)
            if self._include_sysload():
                self.bg_canvas.delete("dynamic_sep")
                sep_x = (self.border + CONTENT_PAD_X + self.icon_px +
                         ICON_GAP + self.value_px + SEP_PAD)
                self._sep_line = self.bg_canvas.create_line(
                    sep_x, self.border + CONTENT_PAD_Y + 2,
                    sep_x, height - self.border - CONTENT_PAD_Y - 2,
                    fill=BORDER_SOFT, width=1, tags="dynamic_sep")
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
        if not self._closing and self.sysload_var.get():
            self._update_system_labels()

    def _update_system_labels(self) -> None:
        self.sysload.sample()
        self._last_system_sample = time.monotonic()
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
        self.menu.add_command(label="Background transparency\u2026", command=self._open_opacity_popup)
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
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.quit)

    def _populate_adapter_menu(self) -> None:
        self.adapter_menu.delete(0, "end")
        self.adapter_menu.add_radiobutton(
            label="All adapters (total)", value=ALL_ADAPTERS,
            variable=self.adapter_var, command=self._on_select_adapter,
            selectcolor=FG_CHECK)
        self.adapter_menu.add_separator()
        if not self.adapters:
            self.adapter_menu.add_command(label="No adapters found", state="disabled")
        for name in self.adapters:
            marker = "" if adapter_is_up(name) else "   (down)"
            self.adapter_menu.add_radiobutton(
                label=shorten(name) + marker, value=name,
                variable=self.adapter_var, command=self._on_select_adapter,
                selectcolor=FG_CHECK)
        self.adapter_menu.add_separator()
        self.adapter_menu.add_command(label="Refresh list", command=self.refresh_adapters)

    def refresh_adapters(self) -> None:
        self.adapters = list_adapters()
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

    def set_opacity(self, value: float) -> None:
        self.opacity = min(MAX_OPACITY, max(MIN_OPACITY, float(value)))
        self.config.set("opacity", self.opacity, save=True)
        try:
            self.root.attributes("-alpha", 1.0)
            if self.bg_window is not None:
                self.bg_window.attributes("-alpha", self._window_alpha())
                self._draw_card(self._card_w, self._card_h)
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
        self.config.set("alert_mbps", float(self.alert_var.get()), save=True)
        self._refresh_labels(self.last_down, self.last_up)

    def _maybe_check_updates_on_start(self) -> None:
        if not self.config.get("check_updates_on_start", True):
            return
        self.update_checker.check_async(self._on_updates_checked_silent)

    def _on_updates_checked_silent(self, data: Optional[Dict[str, Any]]) -> None:
        if data is None or self._closing:
            return
        latest_version = UpdateChecker.latest_version(data)
        if UpdateChecker.is_newer(latest_version, APP_VERSION):
            self.root.after(0, lambda: self._show_update_dialog(data))

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
            if self._closing:
                return
            self.root.after(0, lambda: self._after_manual_check(data, menu_index))

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
        if force or self._cached_taskbar is None or now - self._last_taskbar_probe >= 1.0:
            self._cached_taskbar = taskbar_bounds()
            self._last_taskbar_probe = now
        return self._cached_taskbar

    def _position_in_taskbar(self, x: int, y: int) -> bool:
        taskbar = self._taskbar_rect_cached(force=True)
        if not taskbar:
            return False
        return self._window_rect_overlaps(x, y, self.window_width, self._card_h, taskbar)

    def _raise_windows(self, force: bool = False) -> None:
        """Keep both transparent layers above an always-on-top Taskbar without focus stealing."""
        now = time.monotonic()
        if not force and now - self._last_raise < 0.10:
            return
        self._last_raise = now
        u = user32()
        if u is None:
            try:
                self.root.attributes("-topmost", True)
                if self.bg_window is not None:
                    self.bg_window.attributes("-topmost", True)
            except tk.TclError:
                pass
            return
        # Paint/background first, text layer second. Windows may reorder the
        # Taskbar after a click, so restore both HWNDs without stealing focus.
        for window in (self.bg_window, self.root):
            if window is None:
                continue
            try:
                hwnd = self._hwnd(window)
                if hwnd:
                    u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                   SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
            except Exception:
                pass
        try:
            self.root.lift()
            if self.bg_window is not None:
                self.bg_window.lift()
                self.root.lift()
        except tk.TclError:
            pass

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
        taskbar = taskbar_bounds()
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
        taskbar = taskbar_bounds()
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
        self._lock_flash = True
        self._draw_card(self._card_w, self._card_h)
        self.root.after(450, self._clear_lock_flash)

    def _clear_lock_flash(self) -> None:
        self._lock_flash = False
        self._draw_card(self._card_w, self._card_h)

    def _bind_events(self) -> None:
        for widget in self._all_widgets():
            widget.bind("<Button-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_move)
            widget.bind("<ButtonRelease-1>", self._on_drag_end)
            widget.bind("<Button-3>", self._on_right_click)
            widget.bind("<Double-Button-1>", lambda _event: self.quit())
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
        if self.bg_window is not None:
            self.bg_window.bind("<Button-1>", self._on_drag_start)
            self.bg_window.bind("<B1-Motion>", self._on_drag_move)
            self.bg_window.bind("<ButtonRelease-1>", self._on_drag_end)
            self.bg_window.bind("<Button-3>", self._on_right_click)
            self.bg_window.bind("<Double-Button-1>", lambda _event: self.quit())
        self.root.bind("<FocusIn>", lambda _event: self._raise_windows(force=True))
        self.root.bind("<Visibility>", lambda _event: self._raise_windows(force=True))
        if self.bg_window is not None:
            self.bg_window.bind("<FocusIn>", lambda _event: self._raise_windows(force=True))
            self.bg_window.bind("<Visibility>", lambda _event: self._raise_windows(force=True))
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.bind("<Escape>", lambda _event: self.quit())

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
        self.scanner.maybe_scan(force=True)
        self.tooltip.show(self._tooltip_data(), self.root)

    def _tooltip_data(self) -> Dict[str, str]:
        cpu_text, ram_text = self.sysload.text_short()
        self.ping.maybe_probe()
        return {
            "down": format_speed(self.last_down),
            "up": format_speed(self.last_up),
            "cpu": cpu_text.replace("CPU ", ""),
            "ram": ram_text.replace("RAM ", ""),
            "ping": self.ping.value,
            "adapter": shorten("All adapters" if self.adapter == ALL_ADAPTERS else self.adapter, 22),
            "session": f"today {format_bytes(self.totals.daily_down + self.totals.daily_up)}",
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
            self._refresh_labels(down, up)
            self._update_idle_state(down, up)
        except Exception:
            pass
        now = time.monotonic()
        if self.sysload_var.get() and now - self._last_system_sample >= SYSTEM_REFRESH_MS / 1000.0:
            try:
                self._update_system_labels()
            except Exception:
                pass
        try:
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
                self.scanner.maybe_scan()
                self.tooltip.show(self._tooltip_data(), self.root)
                self._last_tooltip_refresh = now
        except Exception:
            pass
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
            self.root.attributes("-alpha", 1.0)
            if self.bg_window is not None:
                self.bg_window.attributes("-alpha", self._idle_alpha() if faded else self._window_alpha())
        except tk.TclError:
            pass

    def _enforce_locked_position(self) -> None:
        x, y = self.config.get("x"), self.config.get("y")
        if isinstance(x, int) and isinstance(y, int) and (self.root.winfo_x(), self.root.winfo_y()) != (x, y):
            self._move_windows(x, y)

    def _refresh_labels(self, down: float, up: float) -> None:
        alert_bps = float(self.config.get("alert_mbps", 0.0)) * 1024 * 1024
        down_text = format_speed(down)
        up_text = format_speed(up)
        self._set_text("down_value", down_text,
                       FG_ALERT if alert_bps and down >= alert_bps else FG_DOWN)
        self._set_text("up_value", up_text,
                       FG_ALERT if alert_bps and up >= alert_bps else FG_UP)
        self._update_value_width(down_text, up_text)

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
        for handle in (self._after_id, self._tip_after_id, self._hide_after_id):
            if handle is not None:
                try: self.root.after_cancel(handle)
                except tk.TclError: pass
        self.tooltip.hide()
        self.context_panel._close()
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


def main() -> int:
    # Multi-DPI V2 awareness for crisp rendering across multi-monitor setups
    if IS_WINDOWS:
        try:
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor aware
            except Exception:
                try: ctypes.windll.user32.SetProcessDPIAware()
                except Exception: pass
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
    SpeedWidget().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
