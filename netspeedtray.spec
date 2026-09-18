# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for NetSpeedTray.

Build a single-file, windowed (no-console) Windows executable:

    pyinstaller --noconfirm --clean netspeedtray.spec

Output: dist/NetSpeedTray.exe

The application version is read from the VERSION file in the project root and
embedded into the executable's Windows VS_VERSION_INFO resource. A standalone
copy of the same version-info text is shipped in `version_info.txt` so that the
CLI form (`pyinstaller --version-file=version_info.txt ...`) can be used too.
"""

import os
import tempfile

from PyInstaller.utils.hooks import collect_data_files

# ---------------------------------------------------------------------------
# Resolve project paths (SPEC is the absolute path to this .spec file).
# ---------------------------------------------------------------------------
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
PROJECT_ROOT = SPEC_DIR
ENTRY_SCRIPT = os.path.join(PROJECT_ROOT, 'src', 'netspeedtray.py')
ICON_ICO = os.path.join(PROJECT_ROOT, 'assets', 'icon.ico')
ICON_PNG = os.path.join(PROJECT_ROOT, 'assets', 'icon.png')
VERSION_PATH = os.path.join(PROJECT_ROOT, 'VERSION')

FALLBACK_VERSION = '2.7.0'


def _read_version():
    """Read the version string from the VERSION file, with a safe fallback."""
    try:
        with open(VERSION_PATH, 'r', encoding='utf-8') as fh:
            ver = fh.read().strip()
    except OSError:
        ver = FALLBACK_VERSION
    if not ver:
        ver = FALLBACK_VERSION
    return ver


APP_VERSION = _read_version()
# Normalize to a 4-tuple of ints for the fixed file info (ffi) block.
_ver_parts = [int(p) if p.isdigit() else 0 for p in APP_VERSION.split('.')]
_ver_parts = (_ver_parts + [0, 0, 0, 0])[:4]
VER_FILE = '.'.join(str(p) for p in _ver_parts)


def _build_version_info_text(version_str, file_ver):
    """Return PyInstaller version-info text (VS_VERSION_INFO) for this build."""
    parts = [str(p) for p in _ver_parts]
    return f"""# UTF-8
#
# PyInstaller version-info file for NetSpeedTray.
# Generated from the VERSION file ({version_str}).
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers / prodvers are 4-tuples of unsigned short (word).
    filevers=({parts[0]}, {parts[1]}, {parts[2]}, {parts[3]}),
    prodvers=({parts[0]}, {parts[1]}, {parts[2]}, {parts[3]}),
    # mask=0x3f, flags=0x0, OS=0x40004 (Windows NT), fileType=0x1 (app).
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Ali Rahmani'),
        StringStruct(u'FileDescription', u'NetSpeedTray'),
        StringStruct(u'FileVersion', u'{file_ver}'),
        StringStruct(u'InternalName', u'NetSpeedTray'),
        StringStruct(u'LegalCopyright', u'MIT License'),
        StringStruct(u'OriginalFilename', u'NetSpeedTray.exe'),
        StringStruct(u'ProductName', u'NetSpeedTray'),
        StringStruct(u'ProductVersion', u'{file_ver}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x409, 1200])])
  ]
)
"""


# Write the embedded version-info to a temporary file so PyInstaller's
# EXE(version=...) can consume it. Falls back to the literal version string if
# file generation fails for any reason.
version_info_text = _build_version_info_text(APP_VERSION, VER_FILE)
try:
    _vfd, version_file = tempfile.mkstemp(
        prefix='netspeedtray_version_', suffix='.txt'
    )
    with os.fdopen(_vfd, 'w', encoding='utf-8') as fh:
        fh.write(version_info_text)
except OSError:
    version_file = ''

# ---------------------------------------------------------------------------
# Datas / hidden imports / excludes
# ---------------------------------------------------------------------------
datas = []
if os.path.exists(ICON_PNG):
    datas.append((ICON_PNG, '.'))

# psutil ships some data files on Windows; collect them to be safe.
datas += collect_data_files('psutil')

hiddenimports = ['psutil']
excludes = ['tkinter.test', 'unittest']

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# EXE (single-file, windowed / no console)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NetSpeedTray',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_ICO if os.path.exists(ICON_ICO) else None,
    # version_file is the path to the generated version-info text. The literal
    # '2.7.0' below is the fallback used if version_file could not be created.
    version=version_file if version_file else '2.7.0',
)
