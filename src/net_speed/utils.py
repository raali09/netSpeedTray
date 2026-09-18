"""Pure, dependency-free helper functions.

Nothing in this module imports :mod:`tkinter`, :mod:`ctypes`, or :mod:`psutil`,
so it is safe to unit-test on any platform and cheap to import. The network
adapter helpers do import :mod:`psutil` lazily inside the function body.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

import psutil

ALL_ADAPTERS = "__all__"


def list_adapters() -> List[str]:
    """Return up interfaces first, down interfaces last, sorted within each."""
    try:
        counters = psutil.net_io_counters(pernic=True) or {}
        stats = psutil.net_if_stats() or {}
    except Exception:
        return []
    names = list(counters)
    up = [n for n in names if getattr(stats.get(n), "isup", True)]
    return sorted(up) + sorted(n for n in names if n not in up)


def adapter_status_map() -> dict:
    """Single snapshot of link state; call once per menu rebuild."""
    try:
        return {name: bool(getattr(entry, "isup", True))
                for name, entry in (psutil.net_if_stats() or {}).items()}
    except Exception:
        return {}


def format_speed(value: float) -> str:
    """Compact, stable speed text suitable for a taskbar-sized widget."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = 0.0
    kb = max(0.0, val) / 1024.0
    if kb >= 1023.5 * 1024.0:
        gb = kb / (1024.0 * 1024.0)
        return f"{gb:.1f} GB/s" if gb < 100 else f"{gb:.0f} GB/s"
    if kb >= 1023.5:
        mb = kb / 1024.0
        return f"{mb:.0f} MB/s" if mb >= 100 else f"{mb:.1f} MB/s"
    if kb < 0.5:
        return "0 KB/s"
    return f"{kb:.0f} KB/s"


def format_bytes(total: float) -> str:
    """Human-readable byte total with a sensible unit."""
    if total < 1024:
        return f"{int(total)} B"
    for unit in ("KB", "MB", "GB", "TB"):
        total /= 1024.0
        if total < 1024:
            return f"{total:.{0 if unit == 'KB' else 2}f} {unit}"
    return f"{total:.2f} PB"


def format_duration(seconds: float) -> str:
    """Compact ``Hh MMm`` / ``Mm SSs`` / ``Ss`` duration."""
    seconds = int(max(0, seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def shorten(name: str, width: int = 32) -> str:
    """Truncate ``name`` to ``width`` chars with an ellipsis."""
    return name if len(name) <= width else name[:width - 1] + "\u2026"


def _maybe_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except ValueError:
        return None


def compare_versions(a: str, b: str) -> int:
    """Compare two semantic version strings.

    Handles an optional leading ``v``/``V`` and a pre-release suffix
    (``-alpha.1``, ``-beta.2``, ``-rc.1``) following semver precedence rules:
    a version with a pre-release tag is *lower* than the same version without
    one (``2.6.0-rc.1 < 2.6.0``), and pre-release identifiers are compared with
    numeric > string precedence among the same numeric base.

    Returns -1, 0 or +1.
    """

    def parse(v: str) -> Tuple[List[int], List[str]]:
        s = v.strip().lstrip("vV")
        base, _, pre = s.partition("-")
        nums: List[int] = []
        for part in base.split("."):
            digits = ""
            for ch in part:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            try:
                nums.append(int(digits) if digits else 0)
            except ValueError:
                nums.append(0)
        pre_parts = [p for p in pre.replace("_", ".").split(".") if p] if pre else []
        return nums, pre_parts

    pa_num, pa_pre = parse(a)
    pb_num, pb_pre = parse(b)
    while len(pa_num) < len(pb_num):
        pa_num.append(0)
    while len(pb_num) < len(pa_num):
        pb_num.append(0)
    for x, y in zip(pa_num, pb_num):
        if x != y:
            return -1 if x < y else 1
    if not pa_pre and not pb_pre:
        return 0
    if not pa_pre:
        return 1
    if not pb_pre:
        return -1
    for x, y in zip(pa_pre, pb_pre):
        if x == y:
            continue
        xi, yi = _maybe_int(x), _maybe_int(y)
        if xi is not None and yi is not None:
            if xi != yi:
                return -1 if xi < yi else 1
        elif xi is not None:
            return -1
        elif yi is not None:
            return 1
        else:
            return -1 if x < y else 1
    if len(pa_pre) != len(pb_pre):
        return -1 if len(pa_pre) < len(pb_pre) else 1
    return 0
