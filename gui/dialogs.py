# -*- coding: utf-8 -*-
"""
ISPOG - Dialogs
File dialogs of the desktop app. Called only from the Tk main thread.
"""

from pathlib import Path
from tkinter import filedialog
from typing import Optional

from config.settings import SUPPORTED_FILE_TYPES, UI_TEXT


def ask_open_file(initial_dir: Path) -> Optional[Path]:
    """Score to analyze, or None if cancelled."""
    path = filedialog.askopenfilename(
        title='Open a MusicXML file',
        initialdir=initial_dir,
        filetypes=SUPPORTED_FILE_TYPES,
    )
    return Path(path) if path else None


def ask_save_file(default_name: str, initial_dir: Path) -> Optional[Path]:
    """Where to save the analyzed score, or None if cancelled."""
    path = filedialog.asksaveasfilename(
        title=UI_TEXT['save_title'],
        initialdir=initial_dir,
        initialfile=default_name,
        defaultextension='.musicxml',
        filetypes=(('MusicXML', '*.musicxml'), ('All files', '*.*')),
    )
    return Path(path) if path else None
