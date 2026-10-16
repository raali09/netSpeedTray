"""Tests for compare_versions and UpdateChecker.is_newer.

``compare_versions`` implements semver precedence including pre-release
tags. ``UpdateChecker.is_newer`` is a thin wrapper that returns
``compare_versions(latest, current) > 0``.
"""
from __future__ import annotations

import pytest

pytest.importorskip("tkinter")

import netspeedtray as nst  # noqa: E402


# (a, b, expected_sign)  where expected_sign is -1, 0, or 1.
VERSION_PAIRS = [
    # Basic numeric precedence.
    ("2.6.0", "2.6.0", 0),
    ("2.6.0", "2.7.0", -1),
    ("2.7.0", "2.6.0", 1),
    # Leading 'v'/'V' stripped.
    ("v2.7.0", "2.7.0", 0),
    ("V2.7.0", "2.7.0", 0),
    # Missing parts treated as 0.
    ("2.7", "2.7.0", 0),
    ("2.7.0", "2.7", 0),
    ("2", "2.0.0", 0),
    ("2.7.0", "2.7.1", -1),
    # Pre-release is lower than the same release.
    ("2.7.0-rc.1", "2.7.0", -1),
    ("2.7.0", "2.7.0-rc.1", 1),
    # Pre-release ordering among the same base.
    ("2.7.0-rc.1", "2.7.0-rc.2", -1),
    # alpha < beta alphabetically.
    ("2.7.0-alpha.1", "2.7.0-beta.1", -1),
    # Equal pre-release tags compare equal.
    ("2.7.0-rc.1", "2.7.0-rc.1", 0),
    # Pure-numeric pre-release identifiers compared numerically.
    ("2.7.0-1", "2.7.0-2", -1),
    # Numeric (not lexical) comparison: rc.10 > rc.9.
    ("2.7.0-rc.10", "2.7.0-rc.9", 1),
]


class TestCompareVersions:
    @pytest.mark.parametrize("a, b, expected", VERSION_PAIRS)
    def test_compare_versions(self, a, b, expected):
        assert nst.compare_versions(a, b) == expected

    def test_sign_is_only_minus_one_zero_or_one(self):
        for a, b, _ in VERSION_PAIRS:
            result = nst.compare_versions(a, b)
            assert result in (-1, 0, 1)


class TestUpdateCheckerIsNewer:
    """UpdateChecker.is_newer(latest, current) -> compare_versions(latest, current) > 0."""
    @pytest.mark.parametrize(
        "latest, current, expected",
        [
            ("2.7.0", "2.6.0", True),
            ("2.6.0", "2.7.0", False),
            ("2.7.0", "2.7.0", False),
            ("v2.7.0", "2.6.0", True),
            ("2.7.0-rc.1", "2.7.0", False),   # pre-release is NOT newer than release
            ("2.7.0", "2.7.0-rc.1", True),    # release IS newer than its rc
            ("2.7.0-rc.2", "2.7.0-rc.1", True),
            ("2.7.0-rc.1", "2.7.0-rc.2", False),
        ],
    )
    def test_is_newer(self, latest, current, expected):
        assert nst.UpdateChecker.is_newer(latest, current) is expected

    def test_is_newer_matches_compare_versions_sign(self):
        # Cross-check: is_newer == (compare_versions > 0)
        for latest, current, sign in VERSION_PAIRS:
            assert nst.UpdateChecker.is_newer(latest, current) == (sign > 0)
