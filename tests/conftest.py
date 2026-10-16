"""Shared pytest fixtures for the NetSpeedTray test suite.

This conftest makes the ``src/`` directory importable so that test modules
can do ``import netspeedtray as nst`` without installing the package, and
provides an isolated config-file fixture so Config tests never touch the
real user configuration under ``%APPDATA%/NetSpeedTray``.
"""
from __future__ import annotations

import os
import sys

import pytest

# --- Make src/ importable ---------------------------------------------------
# The application is a single-file module at ``src/netspeedtray.py``; we don't
# install it as a package, so tests reach it via sys.path manipulation here.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# --- Fixtures ---------------------------------------------------------------
@pytest.fixture
def temp_config_path(tmp_path, monkeypatch):
    """Return an isolated config file path under a fake APPDATA.

    - Sets ``APPDATA`` to a tmp_path subdir so any code that reads
      ``os.environ["APPDATA"]`` at *call* time (rather than import time)
      lands inside the temporary directory.
    - Re-points the module-level ``netspeedtray.CONFIG_DIR`` and
      ``CONFIG_PATH`` to the same tmp location, so a stray ``Config()`` with
      no explicit path still writes inside the sandbox instead of the user's
      home directory.

    Tests should construct ``Config(str(temp_config_path))`` to use it.
    """
    import netspeedtray as nst

    appdata = tmp_path / "AppData"
    appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(appdata))

    cfg_dir = appdata / nst.APP_NAME
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"

    # Re-point the module-level defaults in case code uses them directly.
    monkeypatch.setattr(nst, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(nst, "CONFIG_PATH", str(cfg_path))

    return str(cfg_path)
