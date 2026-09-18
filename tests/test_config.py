"""Tests for the Config class (load / save / sanitize / migrate / batch)."""
from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("tkinter")

import netspeedtray as nst  # noqa: E402


class TestConfigDefaults:
    def test_loads_defaults_when_no_file(self, temp_config_path):
        assert not os.path.exists(temp_config_path)
        cfg = nst.Config(temp_config_path)
        for key, value in nst.DEFAULT_CONFIG.items():
            assert cfg.get(key) == value, f"default mismatch for {key!r}"
        # ui_version should reflect the current schema.
        assert cfg.get("ui_version") == nst.UI_VERSION


class TestConfigSaveReload:
    def test_save_then_reload(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        cfg.set("x", 123)
        cfg.set("y", 456)
        cfg.set("opacity", 0.5)
        cfg.save()
        # File should exist now.
        assert os.path.exists(temp_config_path)

        cfg2 = nst.Config(temp_config_path)
        assert cfg2.get("x") == 123
        assert cfg2.get("y") == 456
        assert cfg2.get("opacity") == 0.5

    def test_save_writes_valid_json(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        cfg.set("x", 1)
        cfg.save()
        with open(temp_config_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict)
        assert data["x"] == 1


class TestConfigSanitize:
    def test_clamps_opacity_to_max(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"opacity": 5.0}, fh)
        cfg = nst.Config(temp_config_path)
        assert cfg.get("opacity") == nst.MAX_OPACITY

    def test_clamps_opacity_to_min(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"opacity": 0.01}, fh)
        cfg = nst.Config(temp_config_path)
        assert cfg.get("opacity") == nst.MIN_OPACITY

    def test_keeps_valid_opacity(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"opacity": 0.5}, fh)
        cfg = nst.Config(temp_config_path)
        assert cfg.get("opacity") == 0.5

    def test_bad_opacity_string_falls_back_to_default(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"opacity": "not-a-number"}, fh)
        cfg = nst.Config(temp_config_path)
        assert cfg.get("opacity") == nst.DEFAULT_OPACITY

    def test_bad_opacity_none_falls_back_to_default(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"opacity": None}, fh)
        cfg = nst.Config(temp_config_path)
        assert cfg.get("opacity") == nst.DEFAULT_OPACITY

    def test_bad_font_size_falls_back_to_default(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"font_size": "enormous"}, fh)
        cfg = nst.Config(temp_config_path)
        assert cfg.get("font_size") == nst.DEFAULT_FONT_SIZE

    def test_bad_adapter_coerced_to_all(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"adapter": 12345}, fh)
        cfg = nst.Config(temp_config_path)
        assert cfg.get("adapter") == nst.ALL_ADAPTERS

    def test_bad_bool_coerced_to_default(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"locked": "yes"}, fh)
        cfg = nst.Config(temp_config_path)
        # "yes" is not a bool -> falls back to default (False).
        assert cfg.get("locked") is False

    def test_corrupt_json_falls_back_to_defaults(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            fh.write("{ this is not valid json")
        cfg = nst.Config(temp_config_path)
        for key, value in nst.DEFAULT_CONFIG.items():
            assert cfg.get(key) == value


class TestConfigSetMany:
    def test_writes_multiple_keys_in_one_save(self, temp_config_path, monkeypatch):
        cfg = nst.Config(temp_config_path)
        calls = []
        monkeypatch.setattr(cfg, "save", lambda: calls.append(1))
        cfg.set_many({"x": 10, "y": 20, "opacity": 0.5})
        assert len(calls) == 1
        assert cfg.get("x") == 10
        assert cfg.get("y") == 20
        assert cfg.get("opacity") == 0.5

    def test_set_many_no_save(self, temp_config_path, monkeypatch):
        cfg = nst.Config(temp_config_path)
        calls = []
        monkeypatch.setattr(cfg, "save", lambda: calls.append(1))
        cfg.set_many({"x": 1, "y": 2}, save=False)
        assert calls == []
        assert cfg.get("x") == 1


class TestConfigBatch:
    def test_batch_coalesces_into_single_save(self, temp_config_path, monkeypatch):
        cfg = nst.Config(temp_config_path)
        calls = []
        monkeypatch.setattr(cfg, "save", lambda: calls.append(1))
        with cfg.batch() as c:
            c.set("x", 10)
            c.set("y", 20)
            c.set("opacity", 0.5)
            c.set("daily_down", 999)
        # Exactly one save at context exit.
        assert len(calls) == 1
        assert cfg.get("x") == 10
        assert cfg.get("y") == 20
        assert cfg.get("opacity") == 0.5
        assert cfg.get("daily_down") == 999

    def test_batch_save_flag_inside_ignored(self, temp_config_path, monkeypatch):
        """Even set(..., save=True) inside batch() must NOT trigger an extra save."""
        cfg = nst.Config(temp_config_path)
        calls = []
        monkeypatch.setattr(cfg, "save", lambda: calls.append(1))
        with cfg.batch() as c:
            c.set("x", 1, save=True)
            c.set("y", 2, save=True)
        assert len(calls) == 1

    def test_batch_writes_to_disk(self, temp_config_path):
        cfg = nst.Config(temp_config_path)
        with cfg.batch() as c:
            c.set("x", 77)
            c.set("y", 88)
        # Reload from disk to confirm the batched save persisted.
        cfg2 = nst.Config(temp_config_path)
        assert cfg2.get("x") == 77
        assert cfg2.get("y") == 88


class TestConfigMigrate:
    def test_migrate_bumps_ui_version_and_adds_v2_7_0_keys(self, temp_config_path):
        # Start with an old v1 config file on disk.
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"ui_version": 1, "x": 10, "y": 20}, fh)
        cfg = nst.Config(temp_config_path)
        # Simulate a genuinely old config that lacks the v2.7.0 keys
        # (DEFAULT_CONFIG pre-populates them, so pop them explicitly).
        for key in ("corner_radius", "ping_host", "ping_port"):
            cfg.data.pop(key, None)
        cfg.data["ui_version"] = 1

        cfg.migrate()

        assert cfg.get("ui_version") == nst.UI_VERSION
        assert cfg.get("corner_radius") == nst.DEFAULT_CORNER_RADIUS
        assert cfg.get("ping_host") == ""
        assert cfg.get("ping_port") == 53
        # Existing keys are preserved.
        assert cfg.get("x") == 10
        assert cfg.get("y") == 20

    def test_migrate_persists_to_disk(self, temp_config_path):
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"ui_version": 1}, fh)
        cfg = nst.Config(temp_config_path)
        cfg.data["ui_version"] = 1
        cfg.migrate()
        # Reload from disk.
        cfg2 = nst.Config(temp_config_path)
        assert cfg2.get("ui_version") == nst.UI_VERSION

    def test_migrate_noop_when_already_current(self, temp_config_path, monkeypatch):
        cfg = nst.Config(temp_config_path)
        cfg.data["ui_version"] = nst.UI_VERSION
        # If already current, migrate() should return early and NOT save.
        saved = []
        monkeypatch.setattr(cfg, "save", lambda: saved.append(1))
        cfg.migrate()
        assert saved == []

    def test_migrate_preserves_user_corner_radius(self, temp_config_path):
        # A user who already chose "pill" should keep it after migrate.
        with open(temp_config_path, "w", encoding="utf-8") as fh:
            json.dump({"ui_version": 5, "corner_radius": "pill"}, fh)
        cfg = nst.Config(temp_config_path)
        # Migrate uses setdefault, so a saved value survives.
        cfg.migrate()
        assert cfg.get("corner_radius") == "pill"
        assert cfg.get("ui_version") == nst.UI_VERSION
