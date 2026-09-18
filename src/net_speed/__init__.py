"""NetSpeedTray internal package.

Holds the dependency-light layers (constants, pure utilities, Win32 helpers,
config, monitors, update logic) so that ``src/netspeedtray.py`` can shrink to
the UI/widget code plus the entry point. Importing the submodules directly is
the preferred style for new code::

    from net_speed.utils import format_speed, compare_versions
    from net_speed.monitors import SpeedMonitor, PingMonitor

The top-level :mod:`netspeedtray` module re-exports the public names for
backwards compatibility with the single-file layout.
"""

__all__ = [
    "constants", "utils", "win32", "config",
    "monitors", "updates",
]
