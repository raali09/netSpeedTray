"""NetSpeedTray internal package.

Currently holds only the dependency-light :mod:`net_speed.utils` layer —
pure formatting / adapter helpers with no UI dependency, kept unit-testable
on any platform. Everything else (constants, Win32 glue, config, monitors,
update logic and the whole UI) still lives in ``src/netspeedtray.py``,
which re-exports the helpers for backwards compatibility with the
single-file layout::

    from net_speed.utils import format_speed, compare_versions
"""

__all__ = ["utils"]
