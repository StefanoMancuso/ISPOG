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

from config.settings import LOG_DIR

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
    if is_frozen():
        return Path(sys._MEIPASS) / relative_path
    return PROJECT_ROOT / relative_path


def app_data_dir() -> Path:
    """
    Per-user folder of the installed application:
    Windows ``%APPDATA%\\ISPOG``, macOS ``~/Library/Application Support/ISPOG``,
    Linux ``$XDG_STATE_HOME/ISPOG`` (default ``~/.local/state/ISPOG``).
    """
    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or home / ".local" / "state")
    return base / APP_DIR_NAME


def is_frozen() -> bool:
    """True inside a PyInstaller executable."""
    return hasattr(sys, "_MEIPASS")


def writable_path(relative_path: StrPath) -> Path:
    """
    Absolute path of a location the application may write to.

    Inside a PyInstaller executable the bundle is read-only, so writable data goes to
    ``app_data_dir()``; otherwise it is resolved from the project root.
    """
    if is_frozen():
        base = app_data_dir()
        base.mkdir(parents=True, exist_ok=True)
        return base / relative_path
    return PROJECT_ROOT / relative_path


def log_dir() -> Path:
    """
    Folder of the log files: ``logs/`` in the project, or in the executable the usual place
    of each system (macOS ``~/Library/Logs/ISPOG``, elsewhere ``app_data_dir()/logs``).
    """
    if is_frozen() and sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_DIR_NAME
    return writable_path(LOG_DIR)
