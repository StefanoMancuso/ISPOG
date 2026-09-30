# -*- coding: utf-8 -*-
"""
ISPOG - File drag and drop
Tk has no native drag and drop: tkinterdnd2 (tkDnD) adds it. It is optional: without it,
or if its native library cannot be loaded, the app works with the Browse button only.
"""

import logging
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional, Sequence

logger = logging.getLogger(__name__)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:                                  # optional dependency
    TkinterDnD = None
    DND_FILES = None


def enable_file_drop(
    widgets: Sequence[tk.Misc],
    on_drop: Callable[[Path], None],
    on_hover: Optional[Callable[[bool], None]] = None,
) -> bool:
    """
    Accept files dropped on ``widgets``: ``on_drop`` receives the first file,
    ``on_hover(True/False)`` is called when a drag enters or leaves.

    Returns False when drag and drop is not available on this system.
    """
    if TkinterDnD is None or not widgets:
        logger.info('Drag and drop not available: tkinterdnd2 is not installed')
        return False
    try:
        # Loads tkDnD into the existing interpreter (what TkinterDnD.Tk does at start-up).
        TkinterDnD._require(widgets[0].winfo_toplevel())
    except (tk.TclError, RuntimeError) as e:
        logger.warning(f'Drag and drop not available: {e}')
        return False

    def drop(event):
        paths = dropped_paths(event.widget, event.data)
        if on_hover:
            on_hover(False)
        if paths:
            if len(paths) > 1:
                logger.info(f'{len(paths)} files dropped, loading the first')
            on_drop(paths[0])
        return event.action

    def hover(active: bool):
        def handler(event):
            if on_hover:
                on_hover(active)
            return event.action
        return handler

    for widget in widgets:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind('<<Drop>>', drop)
        widget.dnd_bind('<<DropEnter>>', hover(True))
        widget.dnd_bind('<<DropLeave>>', hover(False))
    return True


def dropped_paths(widget: tk.Misc, data: str) -> list[Path]:
    """
    Paths in tkDnD drop data: a Tcl list, where names with spaces are in braces,
    e.g. ``{C:/My Scores/a b.mxl} C:/c.xml``.
    """
    return [Path(p) for p in widget.tk.splitlist(data) if p]
