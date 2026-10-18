## What

<!-- One or two sentences: what does this PR change? -->

## Why

<!-- The motivation / the issue it fixes (e.g. "Fixes #12"). -->

## How

<!-- Bullet points of the important implementation decisions. -->

## Checklist

- [ ] `pytest tests/` passes (and the new logic has a test if it is testable without a display)
- [ ] `python -m pyflakes src/netspeedtray.py src/net_speed/utils.py make_icon.py` is clean
- [ ] No new runtime dependencies (`psutil` stays the only one)
- [ ] UI changes keep the card genuinely fixed-size (no growth as numbers change)
- [ ] `CHANGELOG.md` has an entry (under `## [Unreleased]` or the upcoming version)
- [ ] Version-sensitive changes: `VERSION`, `netspeedtray.spec`, `build_exe.bat` and
      `version_info.txt` fallbacks stay in sync
