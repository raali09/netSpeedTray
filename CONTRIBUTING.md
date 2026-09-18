# Contributing to NetSpeedTray

Thanks for taking the time to contribute! NetSpeedTray is a small project, so the process
is deliberately lightweight. This guide explains how to set up a dev environment, where
things live, and what a good pull request looks like.

The maintainer is **Ali Rahmani** ([github.com/raali09](https://github.com/raali09),
rahmaniali09@gmail.com). Be kind, be patient, and remember this is a hobby project —
reviews happen in spare time.

## Code of conduct

Be excellent to each other. Personal attacks, harassment and discrimination are not
tolerated and will get you blocked. Assume good faith; ask clarifying questions before
disagreeing.

## Setting up a dev environment

You need **Windows 10 or 11** (NetSpeedTray uses Win32 layered windows and
`ctypes.windll`, so it will not run elsewhere — though the pure-Python parts of
`src/net_speed/` can be unit-tested on any OS). Python 3.9 or newer is required; the
project is developed against 3.14.

```bash
git clone https://github.com/raali09/NetSpeedTray.git
cd NetSpeedTray

# runtime dependency
py -m pip install -r requirements.txt

# dev dependencies: PyInstaller (build the exe), Pillow (regenerate the icon),
# pytest (run the tests)
py -m pip install pyinstaller pillow pytest

# run from source
py src/netspeedtray.py
```

To run without a console window during development, use `pythonw src/netspeedtray.py`.

## Project structure

```
src/
├── netspeedtray.py        # entry point + all UI classes:
│                          #   NetSpeedTray (main card), Tooltip, UpdateDialog,
│                          #   per-process dashboard, transparency slider popup
└── net_speed/             # backend package — pure Python, no UI, unit-testable
    ├── constants.py       # Win32 magic numbers as named constants, colours, defaults
    ├── win32.py           # raw ctypes calls: taskbar z-order, signal strength,
    │                      #   high-contrast detection, logoff/shutdown hooks
    ├── utils.py           # unit formatting, version parsing (incl. pre-release tags),
    │                      #   DPI helpers, font fallback
    ├── config.py          # JSON config load / save with batch writes + migration
    ├── monitors.py        # speed / CPU / RAM / per-process / IP / Wi-Fi / ping sampling
    └── updates.py         # GitHub release check + auto-swap installer
tests/                     # pytest suite
assets/                    # icon.png, icon.ico
make_icon.py               # regenerates the icon
build_exe.bat              # one-shot PyInstaller build
.github/                   # workflows, issue templates, PR template
```

When adding a new feature, prefer putting reusable logic in `src/net_speed/` (so it can
be unit-tested) and only the UI glue in `src/netspeedtray.py`.

## Code style

There is no linter config enforced, but please follow these conventions:

- **Type hints** on every function signature. The codebase uses them throughout.
- **Docstrings** on public methods and module-level functions — one short summary line,
  optionally followed by a blank line and more detail.
- 4-space indentation, UTF-8, LF line endings.
- Keep functions short. If a method grows past ~60 lines, factor a helper out.
- No `print()` in library code — use the project's logging helpers if you need to.
- Imports: stdlib, then third-party, then `net_speed.*` — each group alphabetical,
  separated by a blank line.

Before opening a PR, make sure your code compiles and the tests still pass:

```bash
python -m py_compile src/netspeedtray.py
pytest tests/
```

## Tests

The `tests/` directory is a plain `pytest` suite. Run it from the repo root:

```bash
pytest tests/                  # full suite
pytest tests/test_utils.py -v  # one file
pytest -k "version"            # by name pattern
```

Windows-only Win32 helpers are skipped automatically on non-Windows runners, so the suite
is safe to run in CI on Linux/macOS too. When you add a feature to `src/net_speed/`,
please add a matching test under `tests/`. UI code in `src/netspeedtray.py` is not
covered by automated tests — it gets eyeballed instead.

## Building the exe

The standalone `NetSpeedTray.exe` is built with PyInstaller. The simplest path is the
batch file:

```bash
build_exe.bat
```

That installs PyInstaller + Pillow, regenerates the icon if missing, and produces
`dist\NetSpeedTray.exe`. The equivalent by hand:

```bash
py -m pip install pyinstaller pillow
py make_icon.py
py -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name NetSpeedTray ^
    --icon=assets/icon.ico ^
    --add-data="assets/icon.png;." ^
    src/netspeedtray.py
```

You do **not** need to build the exe to contribute — running from source is enough for
most changes.

## Proposing features

1. Open a [Feature request](https://github.com/raali09/NetSpeedTray/issues/new/choose)
   first so we can discuss scope before you write code. Small, focused features land
   quickly; large scope changes are better broken into multiple PRs.
2. Keep one feature per PR. Mixing a bug fix, a refactor and a feature in one PR makes
   review slow.
3. If your feature adds a new dependency, call it out explicitly in the PR description and
   explain why it is necessary. Runtime dependencies are kept minimal on purpose.

## Reporting bugs

Open a [Bug report](https://github.com/raali09/NetSpeedTray/issues/new/choose) and fill
in the form. Please attach the log file at
`%APPDATA%\NetSpeedTray\netspeedtray.log` — it captures the last error and makes
triage dramatically faster. Screenshots of the card and the menu help too.

## Pull request checklist

Before you hit **Create pull request**:

- [ ] Code compiles: `python -m py_compile src/netspeedtray.py`
- [ ] Tests pass: `pytest tests/`
- [ ] You have added tests for any new `net_speed/` logic
- [ ] `CHANGELOG.md` has an entry under the `## [Unreleased]` section (Added / Changed /
      Fixed)
- [ ] Docs updated if you touched user-visible behaviour (`README.md`, config table,
      feature list)
- [ ] No new runtime dependencies unless absolutely necessary — and if so, added to
      `requirements.txt` and called out in the PR description
- [ ] Branch is up to date with `main` and the commit history is clean (rebase if it
      got messy)
- [ ] PR description links the related issue (e.g. `Closes #42`)

## Commit messages

A short subject line in the imperative mood ("Add Wi-Fi signal badge", not "Added"),
optionally a blank line and a body explaining *why*. Reference the issue number if there
is one:

```
Add Wi-Fi signal strength badge to tooltip

Closes #18.
```

## Licensing

By contributing, you agree that your changes will be released under the project's
[MIT License](LICENSE).

---

Questions? Open a [Discussion](https://github.com/raali09/NetSpeedTray/discussions) or
email the maintainer at rahmaniali09@gmail.com. Happy hacking!
