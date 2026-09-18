"""Tests for SpeedMonitor and TotalsTracker logic.

psutil is mocked where needed so the tests are deterministic and do not
depend on real network traffic. ``time.monotonic`` is patched locally so
elapsed-time math is exact (no flaky sleeps).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("tkinter")

import netspeedtray as nst  # noqa: E402


# ---------------------------------------------------------------------------
# Small helpers shared by the monitor tests.
# ---------------------------------------------------------------------------
class _FakeCounters:
    """Mimics the psutil net_io_counters() return value (pernic=False)."""

    def __init__(self, recv: int = 0, sent: int = 0) -> None:
        self.bytes_recv = recv
        self.bytes_sent = sent


class _FakeClock:
    """A controllable replacement for time.monotonic."""

    def __init__(self, start: float = 1000.0) -> None:
        self._t = start

    def monotonic(self) -> float:
        return self._t

    def advance(self, dt: float = 1.0) -> None:
        self._t += dt


# ===========================================================================
# SpeedMonitor
# ===========================================================================
class TestSpeedMonitorSample:
    def test_sample_returns_zero_when_no_elapsed(self, monkeypatch):
        """If elapsed <= 0 (e.g. two reads in the same tick), sample is 0,0,0,0."""
        fc = _FakeCounters(recv=1000, sent=2000)
        monkeypatch.setattr(nst.psutil, "net_io_counters", lambda pernic=False: fc)

        clock = _FakeClock(start=1000.0)
        monkeypatch.setattr(nst.time, "monotonic", clock.monotonic)

        sm = nst.SpeedMonitor()
        # Advance counters but NOT the clock -> elapsed == 0 -> zero sample.
        fc.bytes_recv = 5000
        fc.bytes_sent = 6000
        down, up, dbytes, ubytes = sm.sample()
        assert (down, up, dbytes, ubytes) == (0.0, 0.0, 0, 0)

    def test_sample_returns_delta_when_counters_advance(self, monkeypatch):
        fc = _FakeCounters(recv=1000, sent=2000)
        monkeypatch.setattr(nst.psutil, "net_io_counters", lambda pernic=False: fc)

        clock = _FakeClock(start=1000.0)
        monkeypatch.setattr(nst.time, "monotonic", clock.monotonic)

        sm = nst.SpeedMonitor()  # reads 1000/2000 at t=1000
        # Advance counters by 2000 each, advance clock by 1 second.
        fc.bytes_recv = 3000
        fc.bytes_sent = 4000
        clock.advance(1.0)

        down, up, dbytes, ubytes = sm.sample()  # at t=1001, elapsed=1
        assert dbytes == 2000
        assert ubytes == 2000
        assert down == 2000.0   # bytes / second
        assert up == 2000.0

    def test_sample_clamps_negative_delta_to_zero(self, monkeypatch):
        """If counters go backwards (e.g. adapter reset), deltas clamp to 0."""
        fc = _FakeCounters(recv=5000, sent=5000)
        monkeypatch.setattr(nst.psutil, "net_io_counters", lambda pernic=False: fc)
        clock = _FakeClock(start=100.0)
        monkeypatch.setattr(nst.time, "monotonic", clock.monotonic)

        sm = nst.SpeedMonitor()
        fc.bytes_recv = 1000  # went backwards
        fc.bytes_sent = 500   # went backwards
        clock.advance(1.0)
        down, up, dbytes, ubytes = sm.sample()
        assert dbytes == 0
        assert ubytes == 0
        assert down == 0.0
        assert up == 0.0

    def test_sample_updates_internal_state(self, monkeypatch):
        """After a sample, the next sample is relative to the new baseline."""
        fc = _FakeCounters(recv=0, sent=0)
        monkeypatch.setattr(nst.psutil, "net_io_counters", lambda pernic=False: fc)
        clock = _FakeClock(start=0.0)
        monkeypatch.setattr(nst.time, "monotonic", clock.monotonic)

        sm = nst.SpeedMonitor()
        fc.bytes_recv = 100
        fc.bytes_sent = 200
        clock.advance(1.0)
        sm.sample()
        # Second sample: another +100/+200 over 1s.
        fc.bytes_recv = 200
        fc.bytes_sent = 400
        clock.advance(1.0)
        down, up, dbytes, ubytes = sm.sample()
        assert dbytes == 100
        assert ubytes == 200


# ===========================================================================
# TotalsTracker
# ===========================================================================
class TestTotalsTracker:
    def test_add_accumulates(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        tt = nst.TotalsTracker(cfg)
        tt.add(100, 200)
        assert tt.daily_down == 100
        assert tt.daily_up == 200
        assert tt.session_down == 100
        assert tt.session_up == 200

        tt.add(50, 50)
        assert tt.daily_down == 150
        assert tt.daily_up == 250
        assert tt.session_down == 150
        assert tt.session_up == 250

    def test_add_rolls_over_when_date_advances(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        tt = nst.TotalsTracker(cfg)
        tt.add(100, 200)
        assert tt.daily_down == 100

        # Simulate a day passing: stored date is yesterday.
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        cfg.data["daily_date"] = yesterday
        tt.add(50, 50)

        # Counters should have been zeroed by rollover, then 50/50 added.
        assert tt.daily_down == 50
        assert tt.daily_up == 50
        # And the config date should have been updated to today.
        assert cfg.get("daily_date") == date.today().isoformat()

    def test_clock_rollback_does_not_zero_counters(self, temp_config_path):
        """If the stored date is in the future (clock rolled back),
        TotalsTracker must NOT zero the counters; it keeps accumulating."""
        cfg = nst.Config(temp_config_path)
        tt = nst.TotalsTracker(cfg)
        tt.add(500, 0)
        assert tt.daily_down == 500

        # Simulate the system clock being wound backwards: the stored daily
        # date is now in the future relative to today.
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        cfg.data["daily_date"] = tomorrow
        tt.add(100, 0)

        # Not zeroed: previous 500 plus the new 100.
        assert tt.daily_down == 600
        assert tt.daily_up == 0
        # Stored date is NOT overwritten when today < stored.
        assert cfg.get("daily_date") == tomorrow

    def test_note_speed_tracks_peak(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        tt = nst.TotalsTracker(cfg)
        tt.note_speed(100.0, 50.0)
        tt.note_speed(150.0, 30.0)
        tt.note_speed(120.0, 80.0)
        assert tt.peak_down == 150.0
        assert tt.peak_up == 80.0

    def test_reset_today_zeroes_and_persists(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        tt = nst.TotalsTracker(cfg)
        tt.add(100, 200)
        tt.note_speed(99.0, 88.0)
        tt.reset_today()
        assert tt.daily_down == 0
        assert tt.daily_up == 0
        assert tt.session_down == 0
        assert tt.session_up == 0
        assert tt.peak_down == 0.0
        assert tt.peak_up == 0.0
        # And persisted to disk.
        cfg2 = nst.Config(temp_config_path)
        assert cfg2.get("daily_down") == 0
        assert cfg2.get("daily_up") == 0
        assert cfg2.get("daily_date") == date.today().isoformat()

    def test_flush_persists_totals(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        tt = nst.TotalsTracker(cfg)
        tt.add(123, 456)
        tt.flush()
        cfg2 = nst.Config(temp_config_path)
        assert cfg2.get("daily_down") == 123
        assert cfg2.get("daily_up") == 456
