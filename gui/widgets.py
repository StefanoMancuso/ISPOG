# -*- coding: utf-8 -*-
"""
ISPOG - GUI Widgets
Score selection, parts with their own instrument, output options, the analysis button
and the results (problem list, report, saving).

The analysis runs in a worker thread that never touches Tk; the Tk thread polls its
outcome and shows the results (plan, D6). Saving is a separate step, from the results.
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional, Sequence

from config.settings import (DEFAULT_NUM_FRETS, MAX_FRETS, MAX_NAME_CHARS, MIN_FRETS,
                             TUNING_PRESETS, UI_TEXT)
from core import (AnalysisConfig, AnalysisResult, IspogError, PartInfo, PartSettings, analyze,
                  output_names, parse_tuning, preselected_part_ids, problem_points,
                  render_report, render_summary, report_name, write_notes_logs)
from core.naming import report_path_for
from utils.io import log_dir
from utils.logger import current_log_file, get_logger
from utils.text import shorten
from . import theme
from .dialogs import ask_open_file, ask_output_dir, ask_save_file
from .dnd import enable_file_drop

logger = get_logger(__name__)

FROM_SCORE = 'from_score'
CUSTOM = 'custom'
DEFAULT_PRESET = 'standard'


class Card(ttk.Frame):
    """A white panel with a title, as in the MuseScore plugin."""

    def __init__(self, parent, title: str = '', hint: str = '', **kwargs):
        super().__init__(parent, style='Card.TFrame', padding=theme.PAD, **kwargs)
        self.columnconfigure(0, weight=1)
        if title:
            header = ttk.Frame(self, style='Plain.TFrame')
            header.grid(row=0, column=0, sticky='EW', pady=(0, 6))
            ttk.Label(header, text=title, style='Card.TLabel',
                      font=theme.fonts(self)[0]).pack(side='left')
            if hint:
                ttk.Label(header, text=hint, style='CardMuted.TLabel').pack(side='left', padx=(8, 0))
        self.body = ttk.Frame(self, style='Plain.TFrame')
        self.body.grid(row=1, column=0, sticky='NSEW')
        self.body.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

class FileSelectorWidget(Card):
    """
    Score selection: Browse button, or a file dropped on the window. The path is passed
    to ``on_file_loaded``, which reads the score and returns False if it cannot be used;
    the selection is then reverted.
    """

    def __init__(self, parent, on_file_loaded: Callable[[Path], bool], **kwargs):
        super().__init__(parent, title='Score', **kwargs)
        self._on_file_loaded = on_file_loaded

        self.filepath = tk.StringVar(self, '')
        self.status_text = tk.StringVar(self, UI_TEXT['no_file_loaded'])

        self.load_button = ttk.Button(self.body, text='Browse…', command=self._select_file)
        self.load_button.grid(row=0, column=0, sticky='W')
        self.status_label = ttk.Label(self.body, textvariable=self.status_text,
                                      style='CardMuted.TLabel')
        self.status_label.grid(row=0, column=1, sticky='W', padx=(10, 0))
        self.body.columnconfigure(0, weight=0)
        self.body.columnconfigure(1, weight=1)
        self.drop_enabled = False

        logger.debug('FileSelectorWidget initialized')

    def enable_drop(self, targets: Sequence[tk.Misc]) -> bool:
        """Accept a score dropped on ``targets`` (e.g. the whole window)."""
        self.drop_enabled = enable_file_drop([self, *targets], self.load, self._on_hover)
        if self.drop_enabled and not self.has_file():
            self.status_text.set(UI_TEXT['no_file_drop'])
        return self.drop_enabled

    def _on_hover(self, active: bool) -> None:
        if active:
            self.status_text.set(UI_TEXT['drop_active'])
        else:
            self._show_status()

    def _select_file(self):
        """Open the file dialog."""
        logger.info('Opening file selection dialog')
        current = self.get_filepath()
        path = ask_open_file(Path(current).parent if current else Path.home())
        if path is None:
            logger.info('File selection cancelled by user')
            return
        self.load(path)

    def load(self, path: Path) -> bool:
        """Use ``path`` as the score if it can be read; returns whether it was accepted."""
        logger.info(f'File selected: {path}')
        accepted = self._on_file_loaded(path)
        self.filepath.set(str(path) if accepted else '')
        self._show_status()
        return accepted

    def _show_status(self) -> None:
        current = self.get_filepath()
        if current:
            self.status_text.set(shorten(Path(current).name, MAX_NAME_CHARS))
            self.status_label.configure(style='Card.TLabel')
        else:
            self.status_text.set(UI_TEXT['no_file_drop' if self.drop_enabled else 'no_file_loaded'])
            self.status_label.configure(style='CardMuted.TLabel')

    def get_filepath(self) -> Optional[str]:
        """Returns the selected file path, or None if no file selected."""
        path = self.filepath.get()
        return path if path else None

    def has_file(self) -> bool:
        """Returns True if a file has been selected."""
        return bool(self.filepath.get())


# ---------------------------------------------------------------------------
# Parts, each with its own instrument
# ---------------------------------------------------------------------------

class PartRow(ttk.Frame):
    """
    One part: analyze it or not, and the instrument it is analyzed for (tuning, string 1
    first, and number of frets). Presets fill the tuning; editing it selects Custom.
    """

    NAME_CHARS = 26                        # longer part names are shortened

    def __init__(self, parent, part: PartInfo, analyze: bool, on_change: Callable[[], None]):
        super().__init__(parent, style='Plain.TFrame', padding=(0, 3))
        self.part = part
        self._on_change = on_change
        self.on_layout: Callable[[], None] = lambda: None     # the row changed height
        self._presets = {TUNING_PRESETS[key].name: key for key in TUNING_PRESETS}
        if part.tuning:
            self._presets = {UI_TEXT['preset_from_score']: FROM_SCORE, **self._presets}
        self._presets[UI_TEXT['preset_custom']] = CUSTOM

        default = FROM_SCORE if part.tuning else DEFAULT_PRESET
        self.analyze = tk.BooleanVar(self, analyze)
        self.preset = tk.StringVar(self, self._name_of(default))
        self.tuning = tk.StringVar(self, ' '.join(self._preset_tuning(default)))
        self.frets = tk.StringVar(self, str(DEFAULT_NUM_FRETS))
        self.error = tk.StringVar(self, '')

        # one line: [x] name | preset | tuning | Frets n; a second line only for an error
        name = shorten(f'{part.name} ({part.part_id})', self.NAME_CHARS)
        self.check = ttk.Checkbutton(self, text=name, variable=self.analyze, width=self.NAME_CHARS,
                                     style='Card.TCheckbutton' if part.is_guitar
                                     else 'Other.TCheckbutton', command=self._on_toggle)
        self.check.grid(row=0, column=0, sticky='W', padx=(0, 6))
        self.preset_box = ttk.Combobox(self, textvariable=self.preset, state='readonly', width=10,
                                       values=list(self._presets))
        self.preset_box.grid(row=0, column=1, sticky='W', padx=(0, 6))
        self.preset_box.bind('<<ComboboxSelected>>', lambda e: self._on_preset())
        self.tuning_entry = ttk.Entry(self, textvariable=self.tuning, width=20)
        self.tuning_entry.grid(row=0, column=2, sticky='EW')
        ttk.Label(self, text='Frets', style='Card.TLabel').grid(row=0, column=3, padx=(8, 4))
        self.frets_box = ttk.Spinbox(self, from_=MIN_FRETS, to=MAX_FRETS, textvariable=self.frets,
                                     width=3, command=self._changed)
        self.frets_box.grid(row=0, column=4, sticky='W')
        self.error_label = ttk.Label(self, textvariable=self.error, style='CardError.TLabel')
        self.error_label.grid(row=1, column=1, columnspan=4, sticky='W')
        self.error_label.grid_remove()
        self.columnconfigure(2, weight=1)

        self.tuning.trace_add('write', lambda *a: self._on_tuning_typed())
        self.frets.trace_add('write', lambda *a: self._changed())
        self._update_state()

    # --- settings ---------------------------------------------------------

    def settings(self) -> PartSettings:
        """
        The instrument of this part.

        Raises:
            ValueError: invalid tuning or number of frets (the message names the part).
        """
        try:
            frets = int(self.frets.get())
        except ValueError:
            raise ValueError(f'{self.part.name}: invalid number of frets '
                             f'({MIN_FRETS} to {MAX_FRETS})') from None
        try:
            return PartSettings(parse_tuning(self.tuning.get()), frets)
        except ValueError as e:
            raise ValueError(f'{self.part.name}: {e}') from None

    def set_settings(self, tuning: Sequence[str], frets: int) -> None:
        self.tuning.set(' '.join(tuning))
        self.frets.set(str(frets))

    def _name_of(self, key: str) -> str:
        return next(name for name, k in self._presets.items() if k == key)

    def _preset_tuning(self, key: str) -> tuple[str, ...]:
        if key == FROM_SCORE:
            return tuple(self.part.tuning)
        return tuple(TUNING_PRESETS[key].get_tuning())

    def _on_preset(self) -> None:
        key = self._presets[self.preset.get()]
        if key != CUSTOM:
            self.tuning.set(' '.join(self._preset_tuning(key)))
        else:
            self.tuning_entry.focus_set()

    def _on_tuning_typed(self) -> None:
        typed = parse_tuning(self.tuning.get())
        match = next((name for name, key in self._presets.items()
                      if key != CUSTOM and self._preset_tuning(key) == typed),
                     UI_TEXT['preset_custom'])
        if self.preset.get() != match:
            self.preset.set(match)
        self._changed()

    def _on_toggle(self) -> None:
        self._update_state()
        self._changed()

    def _changed(self) -> None:
        self.validate()
        self._on_change()

    def validate(self) -> bool:
        """Show the problem with the settings, if any; True if they are valid."""
        error = ''
        if self.analyze.get():
            try:
                self.settings()
            except ValueError as e:
                error = str(e).split(': ', 1)[-1]
        if error != self.error.get():
            self.error.set(error)
            if error:
                self.error_label.grid()
            else:
                self.error_label.grid_remove()
            self.on_layout()
        self.tuning_entry.configure(style='Invalid.TEntry' if error else 'TEntry')
        return not error

    def _update_state(self) -> None:
        enabled = self.analyze.get()
        self.preset_box.configure(state='readonly' if enabled else 'disabled')
        self.tuning_entry.configure(state='normal' if enabled else 'disabled')
        self.frets_box.configure(state='normal' if enabled else 'disabled')
        self.validate()


class PartsWidget(Card):
    """
    The parts of the loaded score, each with its own instrument. Guitars are ticked; any
    part can be ticked and analyzed as a guitar with the tuning given here.
    """

    VISIBLE_ROWS = 4                       # more parts: the list scrolls

    def __init__(self, parent, on_change: Callable[[], None] = lambda: None, **kwargs):
        super().__init__(parent, title=UI_TEXT['parts_title'], hint=UI_TEXT['tuning_hint'],
                         **kwargs)
        self._on_change = on_change
        self._parts: list[PartInfo] = []
        self.rows: list[PartRow] = []
        self.status_text = tk.StringVar(self, UI_TEXT['no_parts_yet'])

        frame = ttk.Frame(self.body, style='Plain.TFrame')
        frame.grid(row=0, column=0, sticky='NSEW')
        frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(frame, background=theme.CARD, highlightthickness=0,
                                borderwidth=0, height=1)
        self.scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky='NSEW')
        self.inner = ttk.Frame(self.canvas, style='Plain.TFrame')
        self.inner.columnconfigure(0, weight=1)
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda e: self._fit())
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(
            self._window, width=e.width))
        for widget in (self.canvas, self.inner):
            widget.bind('<Enter>', lambda e: self._bind_wheel(True))
            widget.bind('<Leave>', lambda e: self._bind_wheel(False))

        ttk.Label(self.body, textvariable=self.status_text, style='CardMuted.TLabel').grid(
            row=1, column=0, sticky='W', pady=(4, 0))

    # --- content ----------------------------------------------------------

    def set_parts(self, parts: Sequence[PartInfo]) -> None:
        """Show the parts of a newly loaded score, with the guitars ticked."""
        for row in self.rows:
            row.destroy()
        self._parts = list(parts)
        preselected = set(preselected_part_ids(self._parts))
        self.rows = []
        for index, part in enumerate(self._parts):
            row = PartRow(self.inner, part, part.part_id in preselected, self._on_change)
            row.grid(row=index, column=0, sticky='EW')
            row.on_layout = self._fit
            self.rows.append(row)
        guitars = sum(p.is_guitar for p in self._parts)
        if not self._parts:
            self.status_text.set(UI_TEXT['no_parts_yet'])
        elif preselected:
            self.status_text.set(UI_TEXT['parts_found'].format(guitars=guitars,
                                                               total=len(self._parts)))
        else:
            self.status_text.set(UI_TEXT['no_guitar_found'])
        self._fit()

    def clear(self) -> None:
        self.set_parts([])

    @property
    def parts(self) -> list[PartInfo]:
        """All parts of the loaded score, in score order."""
        return list(self._parts)

    def row(self, part_id: str) -> PartRow:
        return next(r for r in self.rows if r.part.part_id == part_id)

    def selected_parts(self) -> list[PartInfo]:
        return [r.part for r in self.rows if r.analyze.get()]

    def part_settings(self) -> dict[str, PartSettings]:
        """
        The instrument of every ticked part, by part id.

        Raises:
            ValueError: a ticked part has invalid settings (the message names it).
        """
        return {r.part.part_id: r.settings() for r in self.rows if r.analyze.get()}

    # --- scrolling --------------------------------------------------------

    def _fit(self) -> None:
        """Show up to VISIBLE_ROWS parts; a scroll bar for the others."""
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox('all') or (0, 0, 0, 0))
        heights = [r.winfo_reqheight() for r in self.rows]
        visible = sum(heights[:self.VISIBLE_ROWS]) if heights else 1
        self.canvas.configure(height=visible)
        if len(self.rows) > self.VISIBLE_ROWS:
            self.scrollbar.grid(row=0, column=1, sticky='NS')
        else:
            self.scrollbar.grid_remove()
            self.canvas.yview_moveto(0)

    def _bind_wheel(self, active: bool) -> None:
        if not active:
            self.canvas.unbind_all('<MouseWheel>')
            self.canvas.unbind_all('<Button-4>')
            self.canvas.unbind_all('<Button-5>')
            return
        if len(self.rows) <= self.VISIBLE_ROWS:
            return
        self.canvas.bind_all('<MouseWheel>', self._on_wheel)
        self.canvas.bind_all('<Button-4>', lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind_all('<Button-5>', lambda e: self.canvas.yview_scroll(1, 'units'))

    def _on_wheel(self, event) -> None:
        # Windows: multiples of 120; macOS: small steps
        step = -int(event.delta / 120) if abs(event.delta) >= 120 else -event.delta
        self.canvas.yview_scroll(step or (-1 if event.delta > 0 else 1), 'units')


class OptionsWidget(Card):
    """Output: one full score or one file per part, labels in the score."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, title='Output', **kwargs)
        self.output_mode = tk.StringVar(self, 'full')
        self.labels = tk.BooleanVar(self, True)
        ttk.Radiobutton(self.body, text='Full score', variable=self.output_mode, value='full',
                        style='Card.TRadiobutton').grid(row=0, column=0, sticky='W')
        ttk.Radiobutton(self.body, text='Separate parts', variable=self.output_mode,
                        value='split', style='Card.TRadiobutton').grid(row=0, column=1, sticky='W',
                                                                      padx=(16, 0))
        ttk.Checkbutton(self.body, text='Add labels to score', variable=self.labels,
                        style='Option.TCheckbutton').grid(row=0, column=2, sticky='W',
                                                          padx=(16, 0))
        self.body.columnconfigure(0, weight=0)
        self.body.columnconfigure(3, weight=1)

    def get_output_mode(self) -> str:
        return self.output_mode.get()

    def get_labels(self) -> bool:
        return self.labels.get()


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

class ProcessButton(ttk.Frame):
    """
    The Analyze button: runs the analysis and hands the result to ``on_result``. While the
    analysis runs, a progress bar takes the button's place. ``save`` writes the outputs of
    the last analysis where the user chooses.
    """

    POLL_MS = 50                                   # worker result polling interval

    def __init__(
        self,
        parent,
        file_selector: FileSelectorWidget,
        parts: PartsWidget,
        options: OptionsWidget,
        on_result: Callable[[AnalysisResult], None] = lambda result: None,
        on_error: Optional[Callable[[str, Exception], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)

        self.file_selector = file_selector
        self.parts = parts
        self.options = options
        self._on_result = on_result
        self._on_error = on_error                    # e.g. offer to send a bug report
        self.last_config: Optional[AnalysisConfig] = None
        self.last_result: Optional[AnalysisResult] = None

        self.run_button = ttk.Button(self, text=UI_TEXT['analyze'], style='Accent.TButton',
                                     command=self._run_analysis)
        self.run_button.grid(row=0, column=0, sticky='EW')
        self.progress = ttk.Progressbar(self, mode='indeterminate')
        self.progress.grid(row=0, column=0, sticky='EW', padx=40)
        self.progress.grid_remove()                 # shown only while analyzing
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, minsize=self.run_button.winfo_reqheight() + 4)

        logger.debug('ProcessButton initialized')

    def _set_busy(self, busy: bool) -> None:
        """Swap the button and the progress bar."""
        if busy:
            self.run_button.config(state='disabled', text=UI_TEXT['processing'])
            self.run_button.grid_remove()
            self.progress.grid()
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.grid_remove()
            self.run_button.grid()
            self.run_button.config(state='normal', text=UI_TEXT['analyze'])

    def is_busy(self) -> bool:
        return str(self.run_button['state']) == 'disabled'

    def _run_analysis(self):
        """Run the analysis in a worker thread; results are handled in the Tk thread."""
        logger.info('=== Analysis started ===')

        if not self.file_selector.has_file():
            logger.warning('Analysis attempted without file selection')
            messagebox.showwarning(title=UI_TEXT['file_error'],
                                   message=UI_TEXT['no_file_selected'])
            return
        parts = self.parts.selected_parts()
        if not parts:
            messagebox.showwarning(title='ISPOG', message=UI_TEXT['no_parts_selected'])
            return

        try:
            settings = self.parts.part_settings()
            first = settings[parts[0].part_id]
            config = AnalysisConfig(self.file_selector.get_filepath(),
                                    tuning=first.tuning, num_frets=first.num_frets,
                                    part_ids=[p.part_id for p in parts],
                                    output_mode=self.options.get_output_mode(),
                                    labels=self.options.get_labels(),
                                    part_settings=settings)
        except ValueError as e:
            logger.warning(f'Invalid configuration: {e}')
            messagebox.showwarning(title=UI_TEXT['invalid_settings'], message=str(e))
            return

        self._set_busy(True)

        outcome: queue.Queue = queue.Queue(maxsize=1)

        def worker() -> None:
            # No Tk calls here: Tkinter is not thread-safe. The Tk thread polls the queue.
            try:
                outcome.put((analyze(config), None))
            except IspogError as e:
                logger.warning(f'Analysis refused: {e}')
                outcome.put((None, e))
            except Exception as e:
                logger.error('Analysis failed', exc_info=True)
                outcome.put((None, e))

        threading.Thread(target=worker, daemon=True).start()
        self._poll(config, outcome)

    def _poll(self, config: AnalysisConfig, outcome: queue.Queue) -> None:
        try:
            result, error = outcome.get_nowait()
        except queue.Empty:
            self.after(self.POLL_MS, self._poll, config, outcome)
            return
        self._on_analysis_finished(config, result, error)

    def _on_analysis_finished(self, config: AnalysisConfig, result: Optional[AnalysisResult],
                              error: Optional[Exception]) -> None:
        """Tk thread: stop the progress bar, then show the results or the error."""
        self._set_busy(False)
        if error is not None:
            if self._on_error is not None:
                self._on_error(self._error_message(error), error)
            else:
                messagebox.showerror(title='Error', message=self._error_message(error))
        else:
            self.last_config, self.last_result = config, result
            self._on_result(result)
        logger.info('=== Analysis finished ===')

    # --- saving -----------------------------------------------------------

    def save(self) -> Optional[list[Path]]:
        """
        Save the outputs and the report of the last analysis where the user chooses.
        Returns the files written, or None if nothing was saved.
        """
        config, result = self.last_config, self.last_result
        if config is None or result is None:
            return None
        if config.output_mode == 'split':
            return self._save_split(config, result)
        return self._save_full(config, result)

    def _save_full(self, config: AnalysisConfig, result: AnalysisResult) -> Optional[list[Path]]:
        target = ask_save_file(output_names(result)['full'], config.filepath.parent)
        if target is None:
            logger.info('Save cancelled by user')
            return None
        report = report_path_for(target)
        return self._write({target: result.outputs['full']}, report, result)

    def _save_split(self, config: AnalysisConfig, result: AnalysisResult) -> Optional[list[Path]]:
        folder = ask_output_dir(config.filepath.parent)
        if folder is None:
            logger.info('Save cancelled by user')
            return None
        names = output_names(result)
        files = {folder / names[key]: data for key, data in result.outputs.items()}
        report = folder / report_name(result)
        existing = [p.name for p in [*files, report] if p.exists()]
        if existing and not messagebox.askyesno(
                title=UI_TEXT['overwrite_title'],
                message=UI_TEXT['overwrite'].format(files='\n'.join(existing))):
            logger.info('Overwrite declined by user')
            return None
        return self._write(files, report, result)

    def _write(self, files: dict[Path, bytes], report: Path,
               result: AnalysisResult) -> Optional[list[Path]]:
        try:
            for path, data in files.items():
                path.write_bytes(data)
            report.write_text(render_report(result), encoding='utf-8')
            write_notes_logs(result, log_dir())
        except OSError as e:
            logger.error('Saving failed', exc_info=True)
            messagebox.showerror(title='Error', message=f'Could not save the files:\n{e}')
            return None
        logger.info(f'Saved {", ".join(str(p) for p in files)} and {report}')
        return [*files, report]

    @staticmethod
    def _error_message(error: Exception) -> str:
        if isinstance(error, IspogError):
            return str(error)
        return UI_TEXT['unexpected_error'].format(error=error, log=current_log_file() or '-')


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class ResultsPanel(ttk.Frame):
    """
    The last analysis: summary, problem list (click a point for its notes and fingering),
    full report, and the button that saves the colored score.
    """

    COLUMNS = (('where', 'Where', 130), ('problem', 'Problem', 200), ('part', 'Part', 130))

    def __init__(self, parent, on_save: Callable[[], Optional[list[Path]]], **kwargs):
        super().__init__(parent, **kwargs)
        self._on_save = on_save
        self.points = []
        self.summary_text = tk.StringVar(self, UI_TEXT['results_empty'])
        self.saved_text = tk.StringVar(self, '')
        self.stale = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(self, textvariable=self.summary_text, style='Muted.TLabel',
                  justify='left').grid(row=0, column=0, sticky='W', pady=(0, 2))
        self.stale_label = ttk.Label(self, text=UI_TEXT['results_stale'], style='Warning.TLabel')
        self.stale_label.grid(row=1, column=0, sticky='W')
        self.stale_label.grid_remove()

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=2, column=0, sticky='NSEW', pady=(4, 0))
        self._build_problems()
        self._build_report()

        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky='EW', pady=(8, 0))
        self.save_button = ttk.Button(actions, text=UI_TEXT['save_score'], state='disabled',
                                      command=self._save)
        self.save_button.pack(side='left')
        ttk.Label(actions, textvariable=self.saved_text, style='Muted.TLabel').pack(
            side='left', padx=(10, 0))

    def _build_problems(self) -> None:
        frame = ttk.Frame(self.notebook, style='Plain.TFrame', padding=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in self.COLUMNS], show='headings',
                                 selectmode='browse', height=6)
        for key, title, width in self.COLUMNS:
            self.tree.heading(key, text=title, anchor='w')
            self.tree.column(key, width=width, minwidth=60, stretch=True, anchor='w')
        for color, code in theme.STATUS_COLORS.items():
            self.tree.tag_configure(color, foreground=code)
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky='NSEW')
        scrollbar.grid(row=0, column=1, sticky='NS')
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._show_details())

        self.details = tk.Text(frame, height=5, wrap='word', relief='flat', borderwidth=0,
                               background=theme.WINDOW, foreground=theme.TEXT,
                               font=theme.monospace(), padx=8, pady=6, state='disabled')
        self.details.grid(row=1, column=0, columnspan=2, sticky='EW')
        self.notebook.add(frame, text=UI_TEXT['problems_tab'].format(count=0))

    def _build_report(self) -> None:
        frame = ttk.Frame(self.notebook, style='Plain.TFrame', padding=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.report = tk.Text(frame, wrap='none', relief='flat', borderwidth=0,
                              background=theme.CARD, foreground=theme.TEXT,
                              font=theme.monospace(), padx=8, pady=6, state='disabled')
        y = ttk.Scrollbar(frame, orient='vertical', command=self.report.yview)
        x = ttk.Scrollbar(frame, orient='horizontal', command=self.report.xview)
        self.report.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.report.grid(row=0, column=0, sticky='NSEW')
        y.grid(row=0, column=1, sticky='NS')
        x.grid(row=1, column=0, sticky='EW')
        self.notebook.add(frame, text=UI_TEXT['report_tab'])

    # --- content ----------------------------------------------------------

    def show(self, result: AnalysisResult) -> None:
        """Show a new analysis; nothing is saved yet."""
        self.points = [p for report in result.reports for p in problem_points(report)]
        self.tree.delete(*self.tree.get_children())
        for index, point in enumerate(self.points):
            self.tree.insert('', 'end', iid=str(index), tags=(point.color,), values=(
                f'm. {point.measure}, beat {point.beat}', f'{point.status} · {point.label}',
                point.part_name))
        self.notebook.tab(0, text=UI_TEXT['problems_tab'].format(count=len(self.points)))
        self.summary_text.set('\n'.join(render_summary(r) for r in result.reports))
        self._set_text(self.report, render_report(result))
        self._set_text(self.details, UI_TEXT['no_problems'] if not self.points
                       else UI_TEXT['click_problem'])
        self.set_stale(False)
        self.saved_text.set(UI_TEXT['not_saved'])
        self.save_button.configure(state='normal', style='Accent.TButton')

    def clear(self) -> None:
        self.points = []
        self.tree.delete(*self.tree.get_children())
        self.notebook.tab(0, text=UI_TEXT['problems_tab'].format(count=0))
        self.summary_text.set(UI_TEXT['results_empty'])
        self._set_text(self.report, '')
        self._set_text(self.details, '')
        self.set_stale(False)
        self.saved_text.set('')
        self.save_button.configure(state='disabled', style='TButton')

    def set_stale(self, stale: bool) -> None:
        """The settings changed since the analysis shown: say so until the next one."""
        self.stale = stale
        if stale:
            self.stale_label.grid()
        else:
            self.stale_label.grid_remove()

    def select(self, index: int) -> None:
        self.tree.selection_set(str(index))
        self.tree.see(str(index))
        self._show_details()

    def _show_details(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        point = self.points[int(selected[0])]
        lines = [f'{point.title} · {point.part_name}', f'Reason:  {point.reason}', *point.details]
        self._set_text(self.details, '\n'.join(lines))

    def _save(self) -> None:
        saved = self._on_save()
        if saved:
            self.saved_text.set(UI_TEXT['saved_line'].format(
                files=', '.join(shorten(p.name, MAX_NAME_CHARS) for p in saved)))
            self.save_button.configure(style='TButton')

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')
