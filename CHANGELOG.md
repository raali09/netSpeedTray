# Changelog

All notable changes to NetSpeedTray are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-17

First public release.

### Added
- Always-on-top live download/upload speed card with optional CPU and RAM readings.
- Translucent rounded "glass" card: the window is painted with real quarter-circle arcs and
  the surrounding pixels are keyed out, so it is genuinely rounded rather than square.
- **Background-only transparency** — a draggable slider popup (right-click ▸
  **Background transparency…**) fades only the card background from 20% to 100%, while the
  speed text and CPU/RAM badges always stay fully opaque. The choice is remembered between
  runs (`opacity` in the config file) and applies to both the normal state and the auto-hide
  fade.
- Automatic units: readings switch between **KB/s** and **MB/s** on their own, so there is no
  unit selector to configure.
- Fixed, HiDPI-aware geometry: the window width is measured once at start-up and the readings
  sit in fixed-pixel, right-aligned fields, so the card never resizes or shifts as the numbers
  change (and toggling CPU/RAM does not resize it either).
- Network adapter picker (all adapters combined, or a single interface).
- Hover tooltip with session and daily traffic totals, uptime and the processes holding the
  most network connections.
- Speed alert threshold, position lock (shown as an amber outline), snap to screen edges,
  auto-hide when idle (fades to a share of the chosen opacity), start with Windows, and a
  custom position that is saved between runs.
- **In-app update check** — silent check on startup plus a manual **Check for updates…**
  menu entry that compares against the latest GitHub release. For the packaged `.exe`, the
  new build is downloaded and swapped in on the next launch; for source runs, the browser
  opens at the release page.
- Command line flags: `--enable-autostart`, `--disable-autostart`, `--reset-config`,
  `--check-updates`.
- GitHub Actions workflow (`.github/workflows/release.yml`) that builds the Windows `.exe`
  automatically on `v*` tag push and attaches it to a draft release.

### Changed
- Tighter live window: smaller content padding and a smaller corner radius so the card takes
  up less screen space.
- Transparency moved from a 40%–100% radio submenu to a single draggable slider popup.

### Fixed
- The card is no longer placed partly off-screen on displays with scaling above 100%: the
  default position uses the real card size, and a restored position is clamped into the
  current work area (for example after switching to a smaller resolution).
- Transparency no longer makes the speed text hard to read: only the card background fades,
  the readings stay crisp.
