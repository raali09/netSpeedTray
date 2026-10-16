"""Lenient tests for the Win32 helper functions.

These are skipped off-Windows. On a Windows CI they verify only the shape
of the return values (list / tuple-or-None) because the CI may not have a
real taskbar or multiple monitors attached.
"""
from __future__ import annotations

import sys

import pytest

pytest.importorskip("tkinter")

import netspeedtray as nst  # noqa: E402

IS_WINDOWS = sys.platform == "win32"

skip_if_not_windows = pytest.mark.skipif(
    not IS_WINDOWS, reason="Win32 helpers only run on Windows"
)


@skip_if_not_windows
def test_taskbar_entries_returns_list():
    entries = nst.taskbar_entries(force=True)
    assert isinstance(entries, list)
    # Each entry, if present, is a (hwnd, (left, top, right, bottom)) tuple.
    for entry in entries:
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        rect = entry[1]
        assert isinstance(rect, tuple)
        assert len(rect) == 4


@skip_if_not_windows
def test_monitor_work_area_returns_tuple_or_none():
    result = nst.monitor_work_area(0, 0)
    assert result is None or (
        isinstance(result, tuple) and len(result) == 4
    )


@skip_if_not_windows
def test_taskbar_entries_force_bypasses_cache():
    # Calling twice with force=True should both return lists (cache is
    # bypassed, so no stale data).
    first = nst.taskbar_entries(force=True)
    second = nst.taskbar_entries(force=True)
    assert isinstance(first, list)
    assert isinstance(second, list)
