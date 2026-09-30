# -*- coding: utf-8 -*-
"""
ISPOG - Paths
Locations of bundled (read-only) and writable resources.

Paths are anchored to the project root, never to the current working directory (plan, D9):
the result is the same whether ISPOG is launched from VS Code, pytest, a terminal or Render.
Scores are read by ``core.reader.load_score``; save dialogs live in ``gui/dialogs.py``.
"""

import os
import sys
from pathlib import Path
from typing import Union

PROJECT_ROOT = Path(__file__).resolve().parents[1]
"""Folder containing ``core/``, ``config/``, ``gui/`` and ``utils/``."""

APP_DIR_NAME = "ISPOG"

StrPath = Union[str, os.PathLike]


def resource_path(relative_path: StrPath) -> Path:
    """
    Absolute path of a read-only resource shipped with the application.

    Inside a PyInstaller executable resources are unpacked to ``sys._MEIPASS``;
    otherwise they are resolved from the project root.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return PROJECT_ROOT / relative_path


def writable_path(relative_path: StrPath) -> Path:
    """
    Absolute path of a location the application may write to (logs, reports).

    Inside a PyInstaller executable the bundle is read-only, so writable data goes to
    ``%APPDATA%/ISPOG`` (home folder where APPDATA is undefined; macOS is fixed in F6b).
    Otherwise it is resolved from the project root.
    """
    if hasattr(sys, "_MEIPASS"):
        app_data = Path(os.environ.get("APPDATA", Path.home())) / APP_DIR_NAME
        app_data.mkdir(parents=True, exist_ok=True)
        return app_data / relative_path
    return PROJECT_ROOT / relative_path
