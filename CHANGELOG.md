# Changelog

All notable changes to NetSpeedTray are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.18.3] - 2026-10-18

The "Release Pipeline" maintenance release — no application changes, but
the repository could not produce a release: pushing to GitHub neither built
the `.exe` nor created a Release, because the `.github/workflows/` folder
(removed from the source distribution) was missing from the repo. The
automation is restored and the docs now describe the real flow.

### Fixed
- **Release automation was missing entirely** — with no
  `.github/workflows/` in the repo, no CI ran and pushing a `v*` tag did
  nothing (README still promised it would). Two workflows are back:
  - `release.yml` — triggered by pushing a `v*` tag; runs on a Windows
    runner, checks the tag against `VERSION`, runs the test suite, builds
    `NetSpeedTray.exe` with PyInstaller, computes its SHA-256, extracts
    this version's section from `CHANGELOG.md` into the release notes and
    attaches the `.exe` + `SHA256SUMS.txt` to a **draft** GitHub Release
    (draft on purpose: the in-app updater only sees published releases).
    Re-running the workflow for the same tag re-uploads the assets with
    `--clobber` instead of failing.
  - `ci.yml` — pyflakes + the pytest suite on every push to main/master
    and every pull request (Windows runner, where the Windows-only tests
    also execute).
- **Tag/VERSION mismatch can no longer silently ship** — the release
  workflow fails fast with a copy-paste fix-it hint when the pushed tag
  (e.g. `v2.18.3`) does not match the `VERSION` file, closing the hole
  the README warns about (an update loop where every installed copy keeps
  offering the same update).
- **Version fallbacks track 2.18.3** — `_read_version()` in
  `src/netspeedtray.py`, `netspeedtray.spec` (`FALLBACK_VERSION` and the
  `version=` literal) and `build_exe.bat` (three literals) follow the
  rule introduced in 2.18.2.

### Changed
- **README "Publishing a release" section describes the automated flow**
  — the old text explained how to build and upload the `.exe` by hand;
  the new one documents the tag-push flow (`git tag v2.18.3 && git push
  origin v2.18.3`), the draft-review step, the tag/VERSION guard and the
  automatic changelog-derived release notes.
- **CI status badge** added to the README header, pointing at the new
  `ci.yml` workflow.
- **`.github/` is now part of the distribution** — previous notes marked
  the folder as repository-only; it is now shipped in the source ZIP so
  a fresh `git init && push` immediately has working CI and releases.

## [2.18.2] - 2026-10-18

The "Full Panel" follow-up to the 2.18.1 code review — every finding from the
second, whole-project audit is fixed. One user-visible restoration (three
documented settings were unreachable) plus static-analysis and
documentation-vs-reality corrections. No behaviour changes beyond the
restored menu rows.

### Fixed
- **Three documented settings were unreachable from the UI** — "Corner
  style", "Set ping target…" and "Alert threshold" were defined on the
  classic `tk.Menu` widget, but the right-click path posts only the modern
  `ModernContextPanel`; the classic menu is never shown. README documented
  all three as features, the config keys persisted, yet no user could
  reach them. All three are now rows in the modern panel (Corner style and
  Alert threshold post their existing submenus next to Theme / Font size /
  Network adapter; Set ping target opens the existing prompt), so what the
  README promises is what the app delivers.
- **Reserved speed-field width was marginal in proportional fonts** — the
  v2.18.1 fix reserved the width of a single sample (`"99.9 GB/s"`). In
  proportional fonts (Segoe UI) the all-digit `"1023 KB/s"` renders a
  couple of pixels wider than the dotted sample, because the decimal point
  is narrower than a digit, leaving the 1000–1023 KB/s case marginal by
  2–3 px. The card now measures *every* near-maximal sample
  (`VALUE_SAMPLES`) and reserves the widest.
- **Stale version fallback** — the hard-coded fallbacks in
  `_read_version()` (`src/netspeedtray.py`), `netspeedtray.spec` and
  `build_exe.bat` all said `2.7.0`, a half-year-old release; a frozen
  build whose VERSION file went missing would report (and the updater
  would compare against) that ancient version. All fallbacks now track
  the shipped version.

### Changed
- **Dead imports removed** — `format_bytes_compact` and `_maybe_int` were
  imported into `netspeedtray.py` but never used there (they remain public
  helpers of `net_speed.utils`); `datetime.date` was imported and unused
  in `utils.py`; `PIL.ImageFilter` was imported and unused in
  `make_icon.py`.
- **`BG_HOVER` / `SHADOW_COLOR` are declared at module level** — the two
  palette entries previously existed only inside the `THEMES` dicts and
  reached module scope through `apply_theme()`'s `globals()` injection,
  so static checkers (pyflakes) flagged every use site as an undefined
  name. They are now declared like the rest of the palette; the theme
  switcher still rebinds them.
- **Documentation matches reality** —
  - README *Controls* table: `Esc` no longer quits (it hides the tooltip)
    and double-click toggles compact mode rather than quitting; the
    right-click row now lists the restored settings.
  - README *Tests* section: the suite covers version parsing, config
    migration, unit formatting and the speed monitor's delta sampling +
    daily-totals tracker — it never covered the per-process sampler or
    the sparkline ring buffer as previously claimed.
  - README 2.7.0 release notes: the six-module `net_speed` split was
    later consolidated; the note now says so and points at the real
    structure.
  - README / CONTRIBUTING `.github/` references are marked as
    GitHub-repository-only (the folder is not part of the source ZIP).
  - CONTRIBUTING project structure: now shows the actual single-module
    `net_speed` package (the old tree listed five modules that do not
    exist) and the example test file name is real.
  - `net_speed/utils.py` module docstring no longer claims to be
    "dependency-free" with a "lazy psutil import" — `psutil` is a
    module-level import (the only third-party one).

## [2.18.1] - 2026-10-17

The "Smooth Sample" maintenance release — a code review pass that fixes real
defects in performance, thread-safety, rendering and packaging. No new
features; every existing behaviour is preserved.

### Fixed
- **UI froze for a moment every second** — `_sample_proc_speed()` walked the
  entire process table (`psutil.process_iter()` with `io_counters`) *on the Tk
  main thread* once per second; on a busy Windows box that is tens to
  hundreds of milliseconds during which the card, the drag and every popup
  were frozen. The in-code comment even claimed it "only iterates the
  connection-holder names" — it iterated every process. The scan now runs on
  a daemon worker thread; the UI thread only ever reads lock-protected
  snapshots (`proc_rows()` / the tooltip's top-3 list). The follow-up
  "drop exited processes" scan moved off the UI thread with it.
- **Update dialog could crash at shutdown** — the download worker called
  `window.after(0, …)` directly from its own thread; tkinter is not
  thread-safe and the codebase already had `_safe_after()` for exactly this
  hop. The worker now routes through it (and re-checks `_closing`).
- **Readings could overlap the ↓/↑ arrow icons** — the card reserved the
  width of a `"999 MB/s"` sample (7 chars), but `format_speed()` produces up
  to 9 characters (`"1023 KB/s"`, `"99.9 GB/s"`), so those speeds drew past
  the reserved field into the icon column. The reserved sample is now
  `"99.9 GB/s"`, the widest string the formatter can emit.
- **Sparkline was fed per-tick byte deltas, not rates** —
  `_sparkline_push(down_bytes, up_bytes)` is only numerically equal to
  bytes/s while the tick stays exactly 1.0 s; `after()` timer drift silently
  skewed the chart. It now receives the true rates.
- **`format_bytes` overflow at 1 PiB** — the unit ladder stopped at TB, so a
  full PiB printed `"1024.00 PB"`. PB now participates in the ladder
  (`"1.00 PB"`); the pinned test that documented the old behaviour was
  updated accordingly.
- **Single-instance check read a possibly-stale error code** —
  `windll.kernel32.GetLastError()` after another ctypes call can return a
  clobbered value; the mutex probe now uses `WinDLL(..., use_last_error=True)`
  + `ctypes.get_last_error()` (the documented-safe pattern) and fails open
  if the mutex could not be created.
- **Updater broke for non-ASCII Windows usernames** — the swap `.bat` was
  written as UTF-8 while `cmd.exe` parses batch files in the ANSI/OEM
  codepage, so a Persian (or any non-ASCII) `%APPDATA%`/`%TEMP%` path garbled
  every path in the script and the update silently failed. The updater now
  prefers 8.3 short paths (pure ASCII) via `GetShortPathNameW`, falling back
  to writing the script in the ANSI codepage.
- **Dashboard said "no active connections" while connections existed** —
  when the connection scan found holders but no app showed sampled I/O
  deltas in the last second, the empty-state line was simply wrong. It now
  says "no sampled traffic in the last second".

### Changed
- **Per-app session totals are bounded** (`PROC_TOTAL_LIMIT = 512`) — a
  days-long session churning through many apps used to grow the totals map
  without limit; the busiest entries are kept when the cap is hit.
- **Emoji label dropped from the right-click panel** — Tk renders colour
  emoji as monochrome (or tofu) on many Windows font stacks; the
  "App Network Usage" row is plain text now.
- **`requirements.txt` contains only the runtime dependency** (`psutil`);
  the dev-only extras (Pillow for the icon, pytest) moved to
  `requirements-dev.txt` so end users do not install them by accident.
- **`net_speed/__init__.py` matches reality** — its `__all__`/docstring
  advertised six submodules (`constants`, `win32`, `config`, `monitors`,
  `updates`) that do not exist in this tree; it now truthfully exports only
  `utils`. The README project-structure section was corrected the same way.

## [2.17.0] - 2026-10-16

The "Steady Glass" release — three direct user requests: the locked card no
longer trembles on the taskbar, per-app live rates are always named in
KB/s / MB/s, and the card gets a modern frosted-glass repaint at the *exact*
same size.

### Fixed
- **Locked-on-taskbar bounce** — while the widget was locked and docked on the
  taskbar it could jump up and down a few pixels every second. Root cause: two
  independent per-tick movers. `_enforce_taskbar_dock()` re-aligned the card to
  the live taskbar rectangle and then `_enforce_locked_position()` moved it back
  to the saved config position — whenever the two targets disagreed by even a
  pixel (taskbar rect drift, DPI rounding, a stale saved position), each tick
  produced two opposing moves. The fix is architectural:
  - a **single position arbiter** (`_enforce_position`) runs per tick — when
    locked, the saved position wins and dock re-alignment is skipped entirely;
    otherwise dock enforcement keeps the card glued to the taskbar;
  - a **2px deadband** (`POSITION_DEADBAND`) on both enforcers absorbs the
    ±1px `geometry()` → `winfo_y()` round-trip error that per-monitor DPI
    scaling (125% / 150%) introduces, so no mover re-issues the same move every
    tick;
  - locking a docked card now saves the **dock-ideal** position (not whatever
    ±1px value the last round-trip produced), so the lock target and the dock
    target can never disagree;
  - dock enforcement reads the authoritative `window_width` / `_card_h` instead
    of `winfo_width()/winfo_height()`, which could lag one update behind during
    a relayout and feed a stale height into the clamp.

### Changed
- **Per-app live rates always in KB/s / MB/s** — the app-usage dashboard and the
  tooltip's top-app rows now use `format_speed_live`: the unit is always named
  and one decimal is always kept, so lightly-active programs read `0.1 KB/s`
  instead of a dead `0 KB/s`, and `235000 B/s` reads `229.5 KB/s`. The taskbar
  card keeps the compact integer formatting (its width is reserved for
  `999 MB/s`-wide samples).

### Visual
- **Glass card repaint (same size)** — the card surface is now a vertical
  3-stop gradient (`GLASS_SHEEN` → `GLASS_TOP` → `GLASS_BOTTOM`) rendered with
  1px scanlines that are horizontally inset inside the corner arcs, so the
  frosted look follows the rounded silhouette exactly. A brighter top band
  acts as the glass sheen; both themes (Midnight / Classic) ship their own
  stops and High-Contrast mode stays flat. **Geometry is untouched** — same
  width formula, same `2·row + borders` height, same fonts and paddings; only
  the paint changed. Shape reuse (recolor-in-place) is preserved so theme
  switches and the lock flash do not flicker, and stale shapes are now deleted
  on count changes (no canvas item leaks across compact toggles).

## [2.16.0] - 2026-10-16

The "Minimal Four" release — per user request, the card now shows **exactly
four values and nothing else**: download speed, upload speed, CPU and RAM.

### Removed
- **Status strip** — the v2.14 line under the readings (connection dot +
  live ping on the left, today's traffic totals on the right) is gone from
  the card, together with its *Show ping & status* / *Show today's totals*
  menu entries and the `show_ping` / `show_totals` config keys (existing
  configs are migrated, `ui_version` 25).
- **Offline paint on the card** — the red border ring and the red dot that
  2.14 drew while the internet was down no longer appear on the card. The
  connection verdict itself is still computed (link state + probe rounds);
  it now surfaces only in the **hover tooltip** (STATUS cell + LIVE/OFFLINE
  badge) and in the **app-usage dashboard** LIVE badge, keeping the card
  itself perfectly minimal. With the internet down the card simply reads
  `0 KB/s`.

### Unchanged on purpose
- The hover tooltip (sparkline, ping/jitter, IPs, session totals, top apps)
  and the per-app usage dashboard keep all their information — the
  "nothing else" rule applies to the always-visible card only.

## [2.15.0] - 2026-10-16

The "Live & Compact" release — direct response to user feedback on 2.14.0:
per-app traffic is now shown **live**, the speed chart was removed from below
the card, and the whole widget is noticeably smaller.

### Added
- **Live per-app upload/download dashboard** — *App Network Usage* now shows,
  for every running app: the live download rate (cyan), the live upload rate
  (amber), the session total and the active connection count — refreshed
  **every second** with a green `● LIVE` badge that flips to red `● OFFLINE`
  with the connection state. The old dashboard only listed static connection
  counts every 2.5 s. The hover tooltip keeps its top-3 live app rows.

### Changed
- **Compact card** — the row padding was tightened and the status-strip
  reservation slimmed, so the card is ~35% shorter than 2.14.0 and no longer
  stretches wider than its content: the strip width now follows the *actual*
  ping/totals text (growing instantly, shrinking only past an 8px hysteresis
  so the card edge never jitters), which removes the dead space that used to
  sit between the speed readings and the CPU/RAM badges. Today's totals
  render in a compact form (`↓1.2G ↑335M`); while offline, the totals yield
  their spot to the red `OFFLINE` label.
- The sparkline history (60 s) keeps feeding the **hover tooltip chart** — the
  graph moved out of the card, it did not disappear.

### Removed
- **In-card speed graph** — per user request, the speed chart that 2.14.0 drew
  below the readings inside the card was removed (it made the widget taller);
  the menu entry *Show speed graph* and the `show_graph` config key are gone
  with it (existing configs are migrated, `ui_version` 24).

## [2.14.0] - 2026-10-16

The "Modern Glass" release — a visual and information upgrade for the card
itself, built on the exact same single-file core (no new dependencies).

### Added
- **Modern "Midnight" theme** (new default) — a deeper glass-navy card with
  brighter cyan/amber readings and an explicit green/red connection palette.
  The previous look remains available as **Classic** (right-click → Theme).
- **In-card speed graph** — a live dual-line sparkline (download + upload) is
  now drawn inside the card, under the speed readings. Toggle: *Show speed
  graph*. Fades together with the card via the transparency slider while the
  curves stay crisp.
- **Status strip** — a slim line under the graph with a connection dot and the
  live latency on the left (`● 12 ms`) and today's traffic totals on the right
  (`↓ 3.48 GB ↑ 876 MB`). Toggle each half via *Show ping & status* and
  *Show today's totals*.
- **Explicit offline detection** — the card now tells you *the internet is
  down* instead of silently reading 0 KB/s: two independent signals (network
  link state + failed probe rounds against Cloudflare/Google DNS with a
  fast retry cadence) turn the border ring, the status dot and the ping text
  red with an `OFFLINE` label, clearly distinct from "no traffic" (green dot,
  plain 0 KB/s). The tooltip gains a STATUS cell and a LIVE/OFFLINE badge.
- **Card rendering fix** — the rounded-card painter lowered its shapes in an
  order that flipped the canvas stack, painting the whole card in the border
  colour and hiding the intended surface colour (and the new graph band).
  Shapes are now lowered in reverse, so the border ring and surface render
  exactly as designed.
- New config keys: `theme`, `show_graph`, `show_ping`, `show_totals`
  (`ui_version` 23; existing configs migrate automatically).

## [2.13.0] - 2026-10-16

Maintenance release — **no application changes**. The widget itself is exactly
the 2.12.0 code; this release restores the repository infrastructure that went
missing (which had stopped automated releases and `.exe` builds from appearing
on GitHub).

### Added
- **`.github/workflows/release.yml`** — pushing a `v*` tag now builds
  `NetSpeedTray.exe` on a Windows runner with PyInstaller (from
  `netspeedtray.spec`), writes a `NetSpeedTray.exe.sha256` checksum, and opens
  a **draft GitHub release** with auto-generated notes (`Full Changelog: …`)
  and the executable attached — the same automation that produced the
  v1.1.0 → v2.12.0 releases.

## [2.7.0] - Unreleased

A focus release on richer at-a-glance information, multi-monitor robustness, and
accessibility. The backend is now a small `src/net_speed/` package with a `pytest`
suite; the entry point `src/netspeedtray.py` holds the UI only.

### Added
- **Speed sparkline** — a mini line chart of recent download/upload speed is drawn inside
  the hover tooltip, so trends are visible at a glance alongside the current value.
- **Custom ping target** — a new config option lets you pick the `host:port` used for the
  latency measurement shown in the tooltip (default is a well-known HTTPS endpoint).
- **Local & public IP** — the tooltip now reports both the LAN address and the
  public-facing IP (looked up once on start-up against a public echo service and
  refreshed lazily).
- **Wi-Fi signal strength badge** — when the active adapter is wireless, a small badge
  in the tooltip reports the current signal quality (0–100%).
- **Per-process network speed** — a new per-app dashboard lists every process with live
  download/upload speed sampled from `psutil`'s per-IO counters. (Needs administrator
  rights to see other users' / SYSTEM processes.)
- **High-contrast mode** — Windows High Contrast / accessibility themes are detected and
  the card recolours itself from the system palette so it stays legible; the dark text
  shadow is disabled in this mode by design.
- **Adaptive corner radius** — an appearance option lets the card's rounded corners scale
  with system DPI instead of a fixed pixel value.
- **Font auto-fallback** — on older Windows builds where the default UI font is missing,
  the app falls back to a nearby installed font instead of throwing.
- **Graceful shutdown on logoff** — the app traps the Windows logoff/sign-out/shutdown
  messages, flushes its config and exits cleanly, so no settings are lost and no zombie
  process is left behind.
- **Taskbar-cache module-level caching** — repeated Win32 taskbar/enumeration calls are
  memoised at module level for the duration of a tick, cutting redundant work on the
  refresh path.
- **Adaptive z-order re-assertion** — the card's top-most z-order is re-asserted on an
  adaptive schedule (faster right after a display change, slower when stable) instead of
  a fixed cadence.
- **Per-app network dashboard speed column** — the dashboard gained a live
  download/upload speed column alongside the existing connection count.
- **`pytest` test suite** — a new `tests/` directory covers version parsing (including
  pre-release tags), config migration, unit formatting, the per-process speed sampler
  and the sparkline ring buffer. Windows-only Win32 helpers are skipped on non-Windows
  runners.

### Changed
- **`APP_VERSION` is now read from a `VERSION` file** at the repo root instead of being
  hard-coded in `src/netspeedtray.py`. The PyInstaller build copies it into the bundle,
  so the running `.exe` and the source tree can never drift apart.
- **Win32 magic numbers converted to named constants** — every bare `0x…` / integer
  passed to `ctypes.windll.*` now lives in `src/net_speed/constants.py` with a comment,
  making the Win32 glue readable and greppable.
- **`UpdateChecker` no longer fabricates a fake "latest release"** when GitHub returns no
  newer tag — it now reports "no newer release found" instead of synthesising a payload
  equal to the current version.
- **`compare_versions` now parses pre-release tags** (`-alpha`, `-beta`, `-rc.1`) per
  SemVer, so `2.7.0-rc.1` correctly compares as older than `2.7.0`.
- **`install_update` uses rename-and-retry instead of `del`** — the updater writes the
  new binary to a temp path and renames it over the running exe, retrying briefly if the
  file is still locked, which is more robust than the previous `copy` + `del` sequence.
- **`Config` supports batch writes** — a context manager / `begin()` … `commit()` pair
  lets the refresh path update several keys and persist them in a single atomic write,
  reducing config-file churn.
- **Tooltip fonts scale with system DPI** — the tooltip text now picks up the same DPI
  scaling as the main card, so it does not look tiny on a 4K / 150% display.
- **Modularised into a `net_speed/` package** — the monolithic `netspeedtray.py` was
  split into `src/net_speed/{constants,win32,utils,config,monitors,updates}.py` with
  `src/netspeedtray.py` as the thin UI-only entry point. The package has no UI
  dependency, which is what makes the new test suite possible.

### Fixed
- **"Start with Windows" showed ON but the app never launched after reboot** —
  the autostart state is now checked against *both* registry keys Windows uses:
  `HKCU\...\CurrentVersion\Run` (the launch command) and the `StartupApproved`
  flag Task Manager / Settings > Apps > Startup writes. When the entry is
  flagged disabled there, Windows silently skips it at logon even though the
  Run value still exists; enabling autostart now clears that flag, and the
  tray-menu toggle reflects the *effective* state instead of just "value
  exists".
- **Stale autostart path after moving/renaming the exe** — the Run value used
  to keep the path captured when the toggle was first switched on, so moving
  the app to another folder left Windows launching a file that no longer
  existed (with no error shown). A new `ensure_autostart_healthy()` pass runs
  at every app start and re-registers the entry with the current path when the
  recorded target is missing.
- **Added `--check-startup`** — a diagnostic command that prints (or shows in
  a message box for the windowed exe build) the registered command, whether
  the target file exists and whether Windows has the entry disabled, with the
  exact fix for each problem. `--enable-autostart` now doubles as the repair
  command: it rewrites the Run value *and* clears any Task Manager disable
  flag.
- **Startup crash visibility + launch evidence** — every launch now writes a
  `startup: launched` line (with exe path and timestamp) to
  `%APPDATA%\NetSpeedTray\netspeedtray.log`, the default log level is INFO
  (debug stays opt-in via `NETSPEEDTRAY_DEBUG=1`), the widget logs where it
  was shown, and fatal start-up errors now pop a message box in windowed exe
  builds instead of dying invisibly at logon. `--check-startup` also reports
  the last recorded launch, so "Windows never ran the app" (antivirus block)
  is cleanly distinguishable from "ran and crashed later".
- **Widget hidden behind a secondary taskbar when the primary display is swapped** —
  a z-order keep-alive now re-asserts `HWND_TOPMOST` after display configuration changes,
  so the card no longer slips under the taskbar on the newly-primary monitor.
- **Multi-monitor DPI change re-measurement** — when a monitor's DPI scaling changes
  (or the card is dragged between monitors at different DPIs), the card width and font
  size are re-measured instead of staying at the launch-time values, so the layout no
  longer clips or stretches.
- **Config corruption on clock rollback** — `Config` writes are now guarded so a system
  clock rollback (NTP correction, time-zone change) can no longer produce a
  half-overwritten `config.json`. The previous content is kept until the new one is fully
  serialised, then atomically swapped.
- **Install update race when the exe is still locked** — the swap step now retries a few
  times with back-off and falls back to a rename-on-restart if the running binary is
  still locked, instead of failing outright.

## [1.1.0] - 2026-09-17

### Added
- **Custom app icon** — a green rounded square with an upward arrow (and a dot on top,
  evoking a human figure) between `<>` brackets. Generated by `make_icon.py` into
  `assets/icon.png` (window icon) and `assets/icon.ico` (multi-resolution, embedded into
  the `.exe` by PyInstaller). The icon is loaded at runtime and also bundled inside the
  frozen executable via `--add-data`.
- **Dark text outline** — every reading (download/upload speed, CPU/RAM badge, direction
  arrows) is now drawn on a transparent canvas with an 8-direction dark shadow so it stays
  perfectly legible on **any** desktop background — light or dark — even when the card
  background is faded to 20% transparency.
- `make_icon.py` script and `assets/` directory added to the repository.
- GitHub Actions workflow now installs Pillow and regenerates the icon before building the
  exe, so a freshly-cloned repo produces a correctly-iconised binary.

### Changed
- **Dynamic value-column width** — the speed field no longer reserves space for the widest
  possible reading. It now tracks the actual width of the current download/upload values
  (capped at `999.99 MB/s`), so the card is always as narrow as the current speeds require.
  The card grows/shrinks a few pixels when the speed crosses a digit threshold (e.g. 9 → 10 KB/s).
- **Dynamic card width when CPU/RAM is hidden** — when "Show CPU / RAM" is turned off, the
  badge column (separator + CPU/RAM badges) is now removed entirely instead of left empty.
  The card shrinks to just the download/upload column, taking up significantly less screen space.
- **Tighter live window** — reduced content padding (6px / 3px), smaller icon gap (4px),
  smaller separator padding (5px), and a slightly smaller corner radius (6px).
- Speed readings, icons, and badges are now canvas text items (with shadow) instead of
  `tk.Label` widgets — this removes the intermediate Frame / grid layer and lets the text
  float directly on the transparent foreground window.
- UI version bumped to 7.

### Fixed
- **Empty space when CPU/RAM disabled** — the card width was still forced to a 178px minimum
  even after disabling CPU/RAM, leaving a large blank area on the right. The minimum-width
  floor has been removed so the card now shrinks to exactly its content width (~74px without
  badges, ~135px with badges).
- **Card drifting when not locked** — every 1-second refresh was re-clamping the card position
  to the work area, which pushed the card left whenever the speed value width changed even
  slightly (e.g. "0 KB/s" → "2 KB/s"). Position clamping has been removed from the geometry
  update path; the card now stays exactly where the user placed it. Clamping only happens on
  initial placement and position reset.
- **Text visibility at low transparency** — previously, reducing the background opacity also
  made the speed text hard to read on bright desktops. Now only the card background fades;
  the text is drawn on a separate always-opaque foreground window with a dark outline, so it
  remains crisp at every transparency level.
- **Cross-drive update** — the auto-updater helper script now uses `copy /y` + `del` instead
  of `move /y`, which could fail when the temp directory and the executable are on different
  drives.
- **Transparency popup stability** — the popup no longer auto-closes when focus briefly moves
  to the Scale widget; it only closes on explicit *done* / *cancel* / *Escape* / right-click,
  or when focus genuinely leaves the popup for another application.

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
