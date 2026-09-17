# NetSpeedTray

A tiny always-on-top network monitor for Windows 10/11 that shows live download and
upload speed — plus optional CPU and RAM load — in a translucent, rounded glass card
that sits in the corner of your screen.

![NetSpeedTray live window](screenshots/main.png)

No installer, no background service: it is a single Python file that samples `psutil`
once per second. The transparency slider fades the **card background only** — the speed
readings always stay crisp and fully readable, even at maximum transparency, thanks to a
dark text outline drawn behind every reading.

## Download

Grab the ready-to-run **NetSpeedTray.exe** (no Python needed) from the
[Releases page](https://github.com/raali09/NetSpeedTray/releases/latest) and double-click
it. Windows may show a SmartScreen prompt for an unsigned binary — *More info ▸ Run anyway*.
Prefer to run from source? See below.

## Features

- **Live up/down speed** in a card with a genuinely fixed size: the width is measured once at
  start-up and the readings sit in fixed, right-aligned fields, so the window never grows or
  shifts as the numbers change.
- **Automatic units** — readings switch between **KB/s** and **MB/s** on their own, based
  on the current speed. There is no unit selector to configure.
- **Background-only transparency** — a draggable slider (right-click ▸ **Background
  transparency…**) fades the card background from 20% to 100% while the speed text always
  stays 100% opaque and crisp. A dark outline is drawn behind every reading so it stays
  readable on **any** desktop background, light or dark.
- **CPU / RAM badges** next to the speed readings, toggleable from the right-click menu.
- **Custom app icon** — a green rounded square with an upward arrow (and a dot on top,
  evoking a human figure) between `<>` brackets, representing network traffic flowing
  upward. Run `python make_icon.py` to regenerate it.
- **Hover tooltip** with session and daily traffic totals, uptime and the processes
  holding the most network connections.
- **Network adapter picker** — all adapters combined (total) or one interface.
- **In-app update check** — right-click ▸ **Check for updates…** compares the running
  version against the latest GitHub release and, for the packaged `.exe`, downloads and
  swaps in the new build automatically on the next launch.
- **Extras**: speed alert threshold, position lock, snap to screen edges, auto-hide when
  idle, start with Windows.

## Requirements

- Windows 10 or Windows 11
- Python 3.9 or newer (developed against 3.14)
- [psutil](https://pypi.org/project/psutil/) — the only runtime dependency
- [Pillow](https://pypi.org/project/Pillow/) — only needed to regenerate the app icon

## Install and run

```bash
git clone https://github.com/raali09/NetSpeedTray.git
cd NetSpeedTray
py -m pip install -r requirements.txt
py src/netspeedtray.py
```

To start it without a console window, use `pythonw`:

```bash
pythonw src/netspeedtray.py
```

### Controls

| Action | Result |
| --- | --- |
| Left-click + drag | Move the card (snaps to screen edges) |
| Right-click | Open the menu (transparency, adapter, toggles, updates) |
| Double-click / `Esc` | Quit |
| Hover | Tooltip with totals and top connections |

### Background transparency slider

Right-click the card and choose **Background transparency…** — a small popup opens with a
horizontal slider. Drag it left for a more transparent card background, or right for a more
solid one. The change is applied live, remembered between runs, and **only the background
fades** — the speed text and badges stay fully opaque at every setting, reinforced by a dark
outline so they are always legible.

### Command line flags

```bash
py src/netspeedtray.py --enable-autostart    # start with Windows
py src/netspeedtray.py --disable-autostart
py src/netspeedtray.py --reset-config        # remove the saved settings
py src/netspeedtray.py --check-updates       # print latest vs. current version
```

Windows Defender / SmartScreen may warn about auto-start entries; nothing is installed
outside of `%APPDATA%\NetSpeedTray\config.json`.

## In-app updates

The app checks the latest GitHub release on startup (silently) and from the right-click menu
(**Check for updates…**). When a newer version is found:

- Running the packaged `NetSpeedTray.exe`: click **Update now** — the new `.exe` is
  downloaded to a temp folder and swapped in on the next launch (a small helper script
  waits for the app to exit, replaces the file, then restarts it).
- Running from source: clicking **Update now** opens the GitHub release page in your
  browser so you can pull the new code with `git pull`.

Update checks can be turned off by setting `check_updates_on_start` to `false` in
`%APPDATA%\NetSpeedTray\config.json`.

## App icon

The icon is a green rounded square containing an upward arrow with a dot on top (a stylized
human figure) between `<>` brackets — symbolising network traffic flowing upward through a
code-like container.

To regenerate or tweak the icon:

```bash
py -m pip install pillow
py make_icon.py          # writes assets/icon.png and assets/icon.ico
```

The `.ico` is embedded into the `.exe` by PyInstaller (`--icon=assets/icon.ico`). The `.png`
is bundled inside the exe (`--add-data`) so the taskbar / window icon loads at runtime.

## Build a standalone .exe

> Building overwrites `dist\NetSpeedTray.exe`. The binary is **not** committed to the
> repository — it is attached to the GitHub release (see *Releasing* below).

```bash
build_exe.bat
```

That installs PyInstaller + Pillow, regenerates the icon if missing, and produces
`dist\NetSpeedTray.exe` — a single file with the custom icon embedded. The same thing
by hand:

```bash
py -m pip install pyinstaller pillow
py make_icon.py
py -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name NetSpeedTray ^
    --icon=assets/icon.ico ^
    --add-data="assets/icon.png;." ^
    src/netspeedtray.py
```

A ready-made GitHub Actions workflow (`.github/workflows/release.yml`) builds the exe on
Windows automatically whenever you push a `v*` tag, and attaches it to a draft release.

## Configuration

Settings are stored in `%APPDATA%\NetSpeedTray\config.json` (window position, opacity,
adapter, alert threshold, toggles, daily totals, update check). Delete the file — or run
`--reset-config` — to start fresh. Useful keys:

| Key | Meaning |
| --- | --- |
| `opacity` | Card background opacity, `0.20`–`1.0` (also driven by the slider) |
| `x`, `y` | Saved window position |
| `adapter` | Adapter name, or `__all__` for the combined total |
| `show_sysload` | Show the CPU / RAM badges |
| `alert_mbps` | Highlight the readings above this speed, `0` turns it off |
| `check_updates_on_start` | Silently check GitHub for a newer release on launch |

## Project structure

```
NetSpeedTray/
├── src/
│   └── netspeedtray.py     # the whole application
├── assets/
│   ├── icon.png            # window / taskbar icon
│   └── icon.ico            # embedded .exe icon (multi-resolution)
├── make_icon.py            # regenerates assets/icon.{png,ico}
├── requirements.txt        # runtime dependency (psutil)
├── README.md
├── LICENSE                 # MIT
├── screenshots/
│   └── main.png
├── build_exe.bat           # optional: build dist\NetSpeedTray.exe
├── .github/workflows/
│   └── release.yml         # build + attach exe on tag push
├── CHANGELOG.md
└── .gitignore
```

The ready-made `NetSpeedTray.exe` is attached to the [latest release](https://github.com/raali09/NetSpeedTray/releases/latest).

## Releasing

The repository stays source-only; the executable is attached to the GitHub release.

```bash
build_exe.bat
git add -A
git commit -m "NetSpeedTray 1.1.0"
git tag -a v1.1.0 -m "NetSpeedTray 1.1.0"
git push origin main --tags
```

If you push the tag from a clone where the `release.yml` workflow is present, GitHub
Actions builds the exe on a Windows runner and attaches it to a draft release for you
to review and publish. With the [GitHub CLI](https://cli.github.com/) you can also do
it locally:

```bash
gh release create v1.1.0 dist/NetSpeedTray.exe --title "NetSpeedTray 1.1.0" --notes-file CHANGELOG.md
```

## License

MIT — see [LICENSE](LICENSE).

Design and developer: **Ali Rahmani** — [github.com/raali09](https://github.com/raali09)
Contact: rahmaniali09@gmail.com
