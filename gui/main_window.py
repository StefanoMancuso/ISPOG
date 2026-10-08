# -*- coding: utf-8 -*-
"""
ISPOG - Main Window
Main application window that assembles all widgets.
"""

import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from config import (APP_FULL_NAME, APP_TITLE, LICENSE_NAME, PAPER_CITATION, REPOSITORY_URL,
                    UI_TEXT, WINDOW_MIN_SIZE, WINDOW_SIZE)
from config.version import __version__
from core import IspogError, list_parts, load_score, output_names, render_report, report_name
from core.bugreport import ReportContent
from utils import get_logger, log_dir
from utils.logger import current_log_file
from . import theme
from .dialogs import open_folder
from .report_dialog import ReportDialog
from .widgets import (FileSelectorWidget, OptionsWidget, PartsWidget, ProcessButton,
                      ResultsPanel)

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
        theme.apply_theme(self)

        self._version = tk.StringVar(self, '')

        # Everything below the menu lives in one frame: the whole window is a drop target
        self.body = ttk.Frame(self, padding=theme.PAD)
        self.body.pack(fill='both', expand=True)

        self._create_menu()
        self._create_header()
        self._create_widgets()
        self._set_size()

        if sys.platform == 'darwin':
            # Finder sends a score dropped on the app icon, or opened with ISPOG, as an
            # Apple event, both at launch and while running; Tk passes it to this command.
            self.createcommand('::tk::mac::OpenDocument', self.open_documents)

        logger.info('Main window initialized successfully')

    def _create_menu(self):
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label=UI_TEXT['report_menu'], command=self.open_report)
        help_menu.add_command(label='Open log folder', command=lambda: open_folder(log_dir()))
        help_menu.add_separator()
        help_menu.add_command(label='About ISPOG', command=self._show_about)
        menubar.add_cascade(label='Help', menu=help_menu)
        self.config(menu=menubar)

    def _create_header(self):
        """Title and version."""
        header = ttk.Frame(self.body)
        header.pack(fill='x', pady=(0, 8))
        ttk.Label(header, text=APP_FULL_NAME, style='Title.TLabel').pack(side='left')
        ttk.Label(header, textvariable=self._version, style='Small.TLabel').pack(
            side='left', padx=(10, 0), pady=(6, 0))

    def _create_widgets(self):
        """Score, parts, output, Analyze, results: top to bottom."""
        body = self.body
        self.file_selector = FileSelectorWidget(body, on_file_loaded=self._on_file_loaded)
        self.file_selector.pack(fill='x')

        self.parts = PartsWidget(body, on_change=self._on_settings_changed)
        self.parts.pack(fill='x', pady=(8, 0))

        self.options = OptionsWidget(body)
        self.options.pack(fill='x', pady=(8, 0))
        for variable in (self.options.output_mode, self.options.labels):
            variable.trace_add('write', lambda *a: self._on_settings_changed())

        self.process_button = ProcessButton(body, self.file_selector, self.parts, self.options,
                                            on_result=self._on_result, on_error=self.offer_report)
        self.process_button.pack(fill='x', pady=(10, 8))

        self.results = ResultsPanel(body, on_save=self.process_button.save)
        self.results.pack(fill='both', expand=True)

        # A score can be dropped anywhere in the window
        self.file_selector.enable_drop([body])

    def _set_size(self) -> None:
        """Start at WINDOW_SIZE, within the screen; the window can be resized above the minimum."""
        self.update_idletasks()
        width, height = WINDOW_SIZE
        height = min(height, self.winfo_screenheight() - 80)
        self.minsize(*WINDOW_MIN_SIZE)
        self.geometry(f'{max(width, self.body.winfo_reqwidth())}x{max(height, WINDOW_MIN_SIZE[1])}')

    def _on_result(self, result) -> None:
        self.results.show(result)

    def _on_settings_changed(self) -> None:
        """Results on screen no longer match the settings: say so until the next analysis."""
        if self.process_button.last_result is not None and hasattr(self, 'results'):
            self.results.set_stale(True)

    def open_documents(self, *paths: str) -> None:
        """Files opened from the system (macOS Finder): the first one is loaded."""
        if paths:
            logger.info(f'Opened from the system: {", ".join(paths)}')
            self.file_selector.load(Path(paths[0]))

    def _on_file_loaded(self, path: Path) -> bool:
        """Read the score and list its parts; show why if it cannot be used."""
        try:
            parts = list_parts(load_score(path))
        except IspogError as e:
            logger.warning(f'File refused: {e}')
            self.parts.clear()
            self.results.clear()
            self.offer_report(str(e), e, title=UI_TEXT['file_error'])
            return False
        logger.info(f'{path.name}: {len(parts)} part(s), '
                    f'{sum(p.is_guitar for p in parts)} guitar(s)')
        self.parts.set_parts(parts)
        self.results.clear()
        return True

    def _show_about(self):
        messagebox.showinfo(title=UI_TEXT['about_title'], message=UI_TEXT['about'].format(
            name=f'{APP_TITLE} — {APP_FULL_NAME}', version=__version__, license=LICENSE_NAME,
            repository=REPOSITORY_URL, citation=PAPER_CITATION))

    # ------------------------------------------------------------------
    # Bug reports
    # ------------------------------------------------------------------

    def offer_report(self, message: str, error: Exception, title: str = 'Error') -> None:
        """Show an error and offer to send a report about it."""
        if messagebox.askyesno(title=title, icon='error',
                               message=UI_TEXT['report_offer'].format(message=message)):
            detail = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            self.open_report(summary=message.splitlines()[0], error=detail)

    def open_report(self, summary: str = 'User report', error: str = '') -> ReportDialog:
        """The report dialog, filled with what the window knows about the last analysis."""
        current = self.file_selector.get_filepath()
        content = ReportContent(summary=summary, error=error, context=self._report_context(),
                                log_file=current_log_file())
        return ReportDialog(self, content, analysis_files=self._last_analysis_files(),
                            score_file=Path(current) if current else None)

    def _report_context(self) -> dict:
        current = self.file_selector.get_filepath()
        return {
            'score': Path(current).name if current else None,
            'parts': [f'{p.part_id} {p.name}' + (' (guitar)' if p.is_guitar else '')
                      for p in self.parts.parts],
            'selected': [p.part_id for p in self.parts.selected_parts()],
            'instruments': {row.part.part_id: f'{row.tuning.get()} · {row.frets.get()} frets'
                            for row in self.parts.rows if row.analyze.get()},
            'output': self.options.get_output_mode(),
            'labels': self.options.get_labels(),
        }

    def _last_analysis_files(self) -> dict[str, bytes]:
        """Outputs and report of the last analysis of the current score, if any."""
        config = self.process_button.last_config
        result = self.process_button.last_result
        current: Optional[str] = self.file_selector.get_filepath()
        if config is None or result is None or current is None or config.filepath != Path(current):
            return {}
        names = output_names(result)
        files = {names[key]: data for key, data in result.outputs.items()}
        files[report_name(result)] = render_report(result).encode('utf-8')
        return files

    def set_version(self, version_string: str):
        """
        Set the version shown in the window title and under the header.

        Args:
            version_string: Version string to display
        """
        self.title(f'{APP_TITLE} {version_string}')
        self._version.set(f'{APP_TITLE} {version_string}')
        logger.debug(f'Version set to: {version_string}')
