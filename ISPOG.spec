# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build of the desktop app (plan, F7).

    pip install -e ".[build]"
    pyinstaller --noconfirm ISPOG.spec
    dist/ISPOG.exe --self-test report.json                          (Windows)
    dist/ISPOG.app/Contents/MacOS/ISPOG --self-test report.json     (macOS)

Windows: one windowed .exe. macOS: ISPOG.app (a folder bundle: one-file apps are
deprecated on macOS). Linux builds a folder, for local checks only.

- lxml, certifi and tkinterdnd2 (with the tkDnD library of the platform) are collected by
  the hooks of PyInstaller and pyinstaller-hooks-contrib; the self-test checks them.
- UPX is off: compressed executables trigger more antivirus false positives.
- gradio is excluded: the web app (app.py) is not part of the desktop build.
- macOS: no argv emulation. Files dropped on the app icon arrive as Apple events, which Tk
  passes to MainWindow.open_documents, also while the app is running.
- Data files: resources/timepart.xsl (timewise scores), config/finger_stretch.csv (finger
  stretch table); the self-test analysis needs both.
- Icons, if present: resources/ispog.ico (Windows), resources/ispog.icns (macOS).
"""

import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))
from config.settings import APP_FULL_NAME, APP_TITLE  # noqa: E402
from config.version import __version__  # noqa: E402

NAME = APP_TITLE
BUNDLE_ID = 'it.unito.ispog'
COPYRIGHT = 'Copyright (C) 2026 Stefano Mancuso. GNU GPL v3.0 or later.'


def _icon(suffix):
    path = ROOT / 'resources' / f'ispog{suffix}'
    return str(path) if path.is_file() else None


def _numeric_version():
    """(major, minor, micro, 0) from a PEP 440 version: 0.10.0b1 -> (0, 10, 0, 0)."""
    numbers = [int(n) for n in re.match(r'\d+(?:\.\d+)*', __version__).group(0).split('.')]
    return tuple((numbers + [0, 0, 0, 0])[:4])


def _windows_version_info():
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo,
                                                     StringStruct, StringTable, VarFileInfo,
                                                     VarStruct, VSVersionInfo)
    numbers = _numeric_version()
    strings = [
        StringStruct('CompanyName', 'Stefano Mancuso'),
        StringStruct('FileDescription', f'{NAME} - {APP_FULL_NAME}'),
        StringStruct('FileVersion', __version__),
        StringStruct('InternalName', NAME),
        StringStruct('LegalCopyright', COPYRIGHT),
        StringStruct('OriginalFilename', f'{NAME}.exe'),
        StringStruct('ProductName', NAME),
        StringStruct('ProductVersion', __version__),
    ]
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[StringFileInfo([StringTable('040904B0', strings)]),
              VarFileInfo([VarStruct('Translation', [0x0409, 1200])])],
    )


a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        ('resources/timepart.xsl', 'resources'),
        ('config/finger_stretch.csv', 'config'),     # core/stretch.py
        ('LICENSE', '.'),
        ('THIRD_PARTY_NOTICES.md', '.'),
    ],
    hiddenimports=['gui.selftest'],              # imported only with --self-test
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['gradio', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=NAME,
        debug=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)
    app = BUNDLE(
        coll,
        name=f'{NAME}.app',
        icon=_icon('.icns'),
        bundle_identifier=BUNDLE_ID,
        version=__version__,
        info_plist={
            'CFBundleName': NAME,
            'CFBundleDisplayName': NAME,
            'CFBundleShortVersionString': __version__,
            'CFBundleVersion': '.'.join(map(str, _numeric_version()[:3])),
            'NSHumanReadableCopyright': COPYRIGHT,
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
            # Scores can be dropped on the icon or opened with ISPOG; never the default app
            'CFBundleDocumentTypes': [{
                'CFBundleTypeName': 'MusicXML score',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'CFBundleTypeExtensions': ['musicxml', 'mxl', 'xml'],
            }],
        },
    )
elif sys.platform == 'win32':
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        icon=_icon('.ico'),
        version=_windows_version_info(),
    )
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, strip=False, upx=False,
              console=True)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)
