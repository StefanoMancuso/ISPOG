# -*- coding: utf-8 -*-
"""
ISPOG - Main Window
Main application window that assembles all widgets.
"""

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config import (APP_FULL_NAME, APP_TITLE, LICENSE_NAME, LOG_DIR, PAPER_CITATION,
                    REPOSITORY_URL, UI_TEXT, WINDOW_RESIZABLE)
from config.version import __version__
from core import IspogError, list_parts, load_score
from utils import get_logger, writable_path
from .widgets import FileSelectorWidget, PartSelectorWidget, ProcessButton, TuningWidget

logger = get_logger(__name__)


class MainWindow(tk.Tk):
    """
    Main application window for ISPOG.
    Orchestrates all GUI components.
    """

    def __init__(self):
        super().__init__()

        logger.info('Initializing main window')

        self.title(APP_TITLE)
        self.resizable(WINDOW_RESIZABLE, WINDOW_RESIZABLE)

        self._version = tk.StringVar(self, '')

        # Everything below the menu lives in one frame: the whole window is a drop target
        self.body = ttk.Frame(self)
        self.body.pack(fill='both', expand=True)

        self._create_menu()
        self._create_header()
        self._create_widgets()
        self._fit_to_content()

        logger.info('Main window initialized successfully')

    def _create_menu(self):
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label='Open log folder', command=self._open_log_folder)
        help_menu.add_separator()
        help_menu.add_command(label='About ISPOG', command=self._show_about)
        menubar.add_cascade(label='Help', menu=help_menu)
        self.config(menu=menubar)

    def _create_header(self):
        """Create application header with title and version."""
        ttk.Label(self.body, text=APP_FULL_NAME, font=('', 15), anchor='center').pack(
            fill="x", padx=10, pady=(8, 0))
        ttk.Label(self.body, textvariable=self._version, font=('', 8), anchor='center',
                  foreground='gray').pack(fill="x", padx=10, pady=(0, 4))

    def _create_widgets(self):
        """Create and layout all main widgets."""
        body = self.body
        self.file_selector = FileSelectorWidget(body, on_file_loaded=self._on_file_loaded)
        self.file_selector.pack(fill="x", padx=10, pady=(2, 6))

        self.part_selector = PartSelectorWidget(body)
        self.part_selector.pack(fill="x", padx=10, pady=(0, 6))

        self.tuning_widget = TuningWidget(body)
        self.tuning_widget.pack(fill='x', padx=10, pady=(0, 4))

        self.process_button = ProcessButton(body, self.file_selector, self.tuning_widget,
                                            self.part_selector)
        self.process_button.pack(fill="x", padx=10, pady=(0, 8))

        # A score can be dropped anywhere in the window
        self.file_selector.enable_drop([body])

    def _fit_to_content(self) -> None:
        """
        Size the window to its content, then keep that size: the layout is built so that
        nothing grows afterwards (short status texts, fixed-width part list, progress bar in
        place of the button). The size follows the fonts of each system.
        """
        self.update_idletasks()
        self.geometry(f'{self.winfo_reqwidth()}x{self.winfo_reqheight()}')

    def _on_file_loaded(self, path: Path) -> bool:
        """Read the score and list its parts; show why if it cannot be used."""
        try:
            parts = list_parts(load_score(path))
        except IspogError as e:
            logger.warning(f'File refused: {e}')
            messagebox.showerror(title=UI_TEXT['file_error'], message=str(e))
            self.part_selector.clear()
            return False
        logger.info(f'{path.name}: {len(parts)} part(s), '
                    f'{sum(p.is_guitar for p in parts)} guitar(s)')
        self.part_selector.set_parts(parts)
        return True

    def _show_about(self):
        messagebox.showinfo(title=UI_TEXT['about_title'], message=UI_TEXT['about'].format(
            name=f'{APP_TITLE} — {APP_FULL_NAME}', version=__version__, license=LICENSE_NAME,
            repository=REPOSITORY_URL, citation=PAPER_CITATION))

    def _open_log_folder(self):
        folder = writable_path(LOG_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(folder)], check=False)
            else:
                subprocess.run(['xdg-open', str(folder)], check=False)
        except OSError as e:
            messagebox.showerror(title='Error', message=f'{folder}\n\n{e}')

    def set_version(self, version_string: str):
        """
        Set the version shown in the window title and under the header.

        Args:
            version_string: Version string to display
        """
        self.title(f'{APP_TITLE} {version_string}')
        self._version.set(f'ver. {version_string}')
        logger.debug(f'Version set to: {version_string}')
