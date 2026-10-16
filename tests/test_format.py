"""Tests for the pure formatting helpers in netspeedtray.

These functions do not touch Tk, psutil, or the filesystem, so they are
completely OS-agnostic and run on any CI.
"""
from __future__ import annotations

import pytest

# tkinter is required to import the module (it calls tkfont.families() at
# import time, swallowed in a try/except). If the CI lacks libtk, skip the
# whole file rather than failing collection.
pytest.importorskip("tkinter")

import netspeedtray as nst  # noqa: E402


# --- format_speed -----------------------------------------------------------
class TestFormatSpeed:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (0, "0 KB/s"),
            (512, "0 KB/s"),             # 0.5 KB -> formatted as "0 KB/s"
            (1024, "1 KB/s"),            # exactly 1 KB
            (1536, "2 KB/s"),            # 1.5 KB -> rounds to 2 (banker's rounding)
            (1280, "1 KB/s"),            # 1.25 KB -> rounds down to 1
            (1048576, "1.0 MB/s"),       # 1 MiB
            (10485760, "10.0 MB/s"),     # 10 MiB -> one decimal place (< 100)
            (1073741824, "1.0 GB/s"),    # 1 GiB
            (-100, "0 KB/s"),            # negative clamped to 0
            (None, "0 KB/s"),            # None -> TypeError -> 0
            ("abc", "0 KB/s"),           # non-numeric -> ValueError -> 0
        ],
    )
    def test_format_speed(self, value, expected):
        assert nst.format_speed(value) == expected

    def test_format_speed_high_gb(self):
        # 100 GB/s boundary: at >= 100 GB/s the decimal is dropped.
        # 100 * 1024**3 bytes/s -> exactly 100 GB/s
        assert nst.format_speed(100 * 1024 ** 3) == "100 GB/s"


# --- format_bytes -----------------------------------------------------------
class TestFormatBytes:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (0, "0 B"),
            (512, "512 B"),
            (1023, "1023 B"),
            (1024, "1 KB"),              # KB has 0 decimals
            (1280, "1 KB"),              # 1.25 KB -> rounds down to "1 KB"
            (1536, "2 KB"),              # 1.5 KB -> banker's rounding to "2 KB"
            (1048576, "1.00 MB"),        # 1 MiB
            (1073741824, "1.00 GB"),     # 1 GiB
            (1099511627776, "1.00 TB"),  # 1 TiB
        ],
    )
    def test_format_bytes(self, value, expected):
        assert nst.format_bytes(value) == expected

    def test_format_bytes_petabyte_range(self):
        # The implementation's loop only divides through TB, so a full PiB
        # surfaces as "1024.00 PB" rather than "1.00 PB". Pin the actual
        # behaviour so a future fix to the loop is a visible test change.
        assert nst.format_bytes(1024 ** 5) == "1024.00 PB"


# --- format_duration --------------------------------------------------------
class TestFormatDuration:
    @pytest.mark.parametrize(
        "seconds, expected",
        [
            (0, "0s"),
            (45, "45s"),
            (59, "59s"),
            (60, "1m 00s"),
            (90, "1m 30s"),
            (3599, "59m 59s"),
            (3600, "1h 00m"),
            (3700, "1h 01m"),
            (3661, "1h 01m"),
            (-50, "0s"),  # negative clamped to 0
        ],
    )
    def test_format_duration(self, seconds, expected):
        assert nst.format_duration(seconds) == expected


# --- shorten ----------------------------------------------------------------
class TestShorten:
    def test_short_string_unchanged(self):
        assert nst.shorten("hello", width=32) == "hello"

    def test_exact_width_unchanged(self):
        s = "A" * 32
        assert nst.shorten(s, width=32) == s

    def test_long_string_truncated_with_ellipsis(self):
        s = "A" * 33
        out = nst.shorten(s, width=32)
        assert len(out) == 32
        assert out == "A" * 31 + "\u2026"
        assert out.endswith("\u2026")

    def test_custom_width(self):
        assert nst.shorten("abcdefghij", width=5) == "abcd\u2026"
