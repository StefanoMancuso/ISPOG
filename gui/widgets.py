# -*- coding: utf-8 -*-
"""
ISPOG - GUI Widgets
File selection, tuning, part selection and the analysis button.

The analysis runs in a worker thread that never touches Tk; the Tk thread polls its
outcome, then saves the files and shows the summary (plan, D6).
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional, Sequence

from config.settings import (
    DEFAULT_NUM_FRETS, DEFAULT_NUM_STRINGS, LOG_DIR, MAX_FRETS, MAX_NAME_CHARS, MAX_STRINGS,
    MIN_FRETS, MIN_STRINGS, NOTE_LIST, STANDARD_TUNING_INDICES, TUNING_PRESETS, UI_TEXT
)
from core import (AnalysisConfig, AnalysisResult, IspogError, PartInfo, PartReport, analyze,
                  render_report, write_notes_logs)
from utils.io import writable_path
from utils.logger import current_log_file, get_logger
from .dialogs import ask_open_file, ask_output_dir, ask_save_file
from .dnd import enable_file_drop
from .outputs import (full_output_name, preselected_part_ids, report_path_for, shorten,
                      split_output_names, split_report_name)

logger = get_logger(__name__)


class FileSelectorWidget(ttk.LabelFrame):
    """
    Score selection: Browse button, or a file dropped on the window. The path is passed
    to ``on_file_loaded``, which reads the score and returns False if it cannot be used;
    the selection is then reverted.
    """

    def __init__(self, parent, on_file_loaded: Callable[[Path], bool], *args, **kwargs):
        super().__init__(parent, text="Score", *args, **kwargs)
        self._on_file_loaded = on_file_loaded

        self.filepath = tk.StringVar(self, '')
        self.status_text = tk.StringVar(self, UI_TEXT['no_file_loaded'])

        self.load_button = ttk.Button(self, text='Browse…', command=self._select_file)
        self.load_button.pack(pady=(6, 2))

        self.status_label = ttk.Label(self, textvariable=self.status_text, anchor='center',
                                      foreground='gray')
        self.status_label.pack(fill='x', padx=10, pady=(2, 6))
        self.drop_enabled = False

        logger.debug('FileSelectorWidget initialized')

    def enable_drop(self, targets: Sequence[tk.Misc]) -> bool:
        """Accept a score dropped on ``targets`` (e.g. the whole window)."""
        self.drop_enabled = enable_file_drop([self, *targets], self.load, self._on_hover)
        if self.drop_enabled and not self.has_file():
            self.status_text.set(UI_TEXT['no_file_drop'])
        return self.drop_enabled

    def _on_hover(self, active: bool) -> None:
        self.config(text=UI_TEXT['drop_active'] if active else 'Score')

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
        if self._on_file_loaded(path):
            self.filepath.set(str(path))
            self.status_text.set(shorten(path.name, MAX_NAME_CHARS))
            self.status_label.config(foreground='green')
            return True
        self.filepath.set('')
        self.status_text.set(UI_TEXT['no_file_drop' if self.drop_enabled else 'no_file_loaded'])
        self.status_label.config(foreground='gray')
        return False

    def get_filepath(self) -> Optional[str]:
        """Returns the selected file path, or None if no file selected."""
        path = self.filepath.get()
        return path if path else None

    def has_file(self) -> bool:
        """Returns True if a file has been selected."""
        return bool(self.filepath.get())


class PartSelectorWidget(ttk.LabelFrame):
    """
    Parts of the loaded score: every part can be selected, guitars are preselected.
    Also the output options: one full score or one file per part, labels in the score.
    """

    LIST_HEIGHT = 4
    LIST_WIDTH = 28                                # characters; longer names are cut

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="Parts and Output", *args, **kwargs)
        self._parts: list[PartInfo] = []
        self.output_mode = tk.StringVar(self, 'full')
        self.labels = tk.BooleanVar(self, True)
        self.status_text = tk.StringVar(self, '')

        frame = ttk.Frame(self)
        frame.pack(fill='x', padx=10, pady=(6, 0))
        self.listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, exportselection=False,
                                  height=self.LIST_HEIGHT, width=self.LIST_WIDTH,
                                  activestyle='none')
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.pack(side='left', fill='x', expand=True)
        scrollbar.pack(side='right', fill='y')

        ttk.Label(self, textvariable=self.status_text, foreground='gray').pack(
            fill='x', padx=10, pady=(2, 4))

        options = ttk.Frame(self)
        options.pack(fill='x', padx=10, pady=(0, 6))
        ttk.Radiobutton(options, text='Full score', variable=self.output_mode,
                        value='full').grid(row=0, column=0, sticky='W')
        ttk.Radiobutton(options, text='Separate parts', variable=self.output_mode,
                        value='split').grid(row=0, column=1, sticky='W', padx=(15, 0))
        ttk.Checkbutton(options, text='Add labels to score', variable=self.labels).grid(
            row=1, column=0, columnspan=2, sticky='W', pady=(4, 0))

        logger.debug('PartSelectorWidget initialized')

    def set_parts(self, parts: Sequence[PartInfo]) -> None:
        """Show the parts of a newly loaded score, with the guitars selected."""
        self._parts = list(parts)
        self.listbox.delete(0, tk.END)
        preselected = set(preselected_part_ids(self._parts))
        for index, part in enumerate(self._parts):
            self.listbox.insert(tk.END, f'{part.name} ({part.part_id})')
            if part.part_id in preselected:
                self.listbox.selection_set(index)
        guitars = sum(p.is_guitar for p in self._parts)
        self.status_text.set(UI_TEXT['parts_found'].format(guitars=guitars,
                                                           total=len(self._parts))
                             if preselected else UI_TEXT['no_guitar_found'])

    def clear(self) -> None:
        self.set_parts([])
        self.status_text.set('')

    def selected_parts(self) -> list[PartInfo]:
        return [self._parts[i] for i in self.listbox.curselection()]

    def get_output_mode(self) -> str:
        return self.output_mode.get()

    def get_labels(self) -> bool:
        return self.labels.get()


class TuningWidget(ttk.LabelFrame):
    """
    Widget for selecting guitar tuning.
    Supports preset tunings and custom configurations.
    """
    
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="Tuning Configuration", *args, **kwargs)
        
        # Current tuning mode
        self.tuning_mode = tk.StringVar(self, 'standard')
        
        # Number of strings
        self.num_strings = tk.IntVar(self, DEFAULT_NUM_STRINGS)
        
        # Initialize tuning variables for each string (max 8)
        self.string_vars = [
            tk.StringVar(self, NOTE_LIST[idx])
            for idx in STANDARD_TUNING_INDICES
        ]
        
        # Number of frets (all tunings)
        self.num_frets = tk.IntVar(self, DEFAULT_NUM_FRETS)

        self._create_preset_selection()
        self._create_tuning_spinboxes()
        self._create_count_selectors()
        
        # Apply initial tuning
        self._apply_preset_tuning()
        
        logger.debug('TuningWidget initialized')
    
    def _create_preset_selection(self):
        """Radio buttons for the preset tunings and Custom (left column)."""
        preset_frame = ttk.Frame(self)
        preset_frame.grid(row=0, column=0, sticky='NW', padx=(10, 8), pady=(4, 0))

        self.preset_buttons = {}
        for idx, (key, preset) in enumerate(TUNING_PRESETS.items()):
            rb = ttk.Radiobutton(preset_frame, text=preset.name, variable=self.tuning_mode,
                                 value=key, command=self._on_tuning_change)
            rb.grid(row=idx, column=0, sticky='W', pady=2)
            self.preset_buttons[key] = rb

        ttk.Radiobutton(preset_frame, text='Custom', variable=self.tuning_mode, value='custom',
                        command=self._on_tuning_change).grid(
            row=len(TUNING_PRESETS), column=0, sticky='W', pady=2)

    def _create_tuning_spinboxes(self):
        """One spinbox per string: strings 1–4 in the first column, 5–8 in the second."""
        strings_frame = ttk.Frame(self)
        strings_frame.grid(row=0, column=1, sticky='NW', padx=(0, 10), pady=(4, 0))
        strings_frame.columnconfigure(2, minsize=16)            # gap between the two columns

        self.tuning_spinboxes = []
        for idx in range(MAX_STRINGS):
            row, block = idx % 4, idx // 4
            label_col, spin_col = 3 * block, 3 * block + 1
            ttk.Label(strings_frame, text=f'{idx + 1}°').grid(
                row=row, column=label_col, sticky='E', padx=(0, 4), pady=2)
            spinbox = ttk.Spinbox(strings_frame, values=NOTE_LIST,
                                  textvariable=self.string_vars[idx], width=4, state='disabled')
            spinbox.grid(row=row, column=spin_col, sticky='W', pady=2)
            self.tuning_spinboxes.append(spinbox)

    def _create_count_selectors(self):
        """Number of strings (Custom only) and number of frets, on one row."""
        counts = ttk.Frame(self)
        counts.grid(row=1, column=0, columnspan=2, sticky='W', padx=10, pady=(6, 8))

        ttk.Label(counts, text='Strings').grid(row=0, column=0, sticky='W', padx=(0, 4))
        self.string_count_spinbox = ttk.Spinbox(
            counts, from_=MIN_STRINGS, to=MAX_STRINGS, textvariable=self.num_strings,
            width=3, state='disabled', command=self._on_string_count_change)
        self.string_count_spinbox.grid(row=0, column=1, sticky='W')

        ttk.Label(counts, text='Frets').grid(row=0, column=2, sticky='W', padx=(16, 4))
        ttk.Spinbox(counts, from_=MIN_FRETS, to=MAX_FRETS, textvariable=self.num_frets,
                    width=3, state='readonly').grid(row=0, column=3, sticky='W')

    def _on_tuning_change(self):
        """Handle tuning preset change."""
        mode = self.tuning_mode.get()
        logger.debug(f'Tuning mode changed to: {mode}')
        
        if mode == 'custom':
            # Enable custom configuration
            self.string_count_spinbox.config(state='readonly')
            for i in range(self.num_strings.get()):
                self.tuning_spinboxes[i].config(state='readonly')
        else:
            # Disable custom controls and apply preset
            self.string_count_spinbox.config(state='disabled')
            for spinbox in self.tuning_spinboxes:
                spinbox.config(state='disabled')
            
            self._apply_preset_tuning()
    
    def _apply_preset_tuning(self):
        """Apply the currently selected preset tuning."""
        mode = self.tuning_mode.get()
        
        if mode in TUNING_PRESETS:
            preset = TUNING_PRESETS[mode]
            self.num_strings.set(preset.strings)
            
            # Set tuning for each string
            for idx, note in enumerate(preset.notes):
                self.string_vars[idx].set(note)
            
            logger.debug(f'Applied preset tuning: {preset.name}')
    
    def _on_string_count_change(self):
        """Handle change in number of strings."""
        count = self.num_strings.get()
        logger.debug(f'String count changed to: {count}')
        
        # Enable/disable spinboxes based on string count
        for i in range(MAX_STRINGS):
            if i < count:
                self.tuning_spinboxes[i].config(state='readonly')
            else:
                self.tuning_spinboxes[i].config(state='disabled')
    
    def get_tuning(self) -> list[str]:
        """Returns current tuning as list of note strings."""
        count = self.num_strings.get()
        return [self.string_vars[i].get() for i in range(count)]
    
    def get_num_strings(self) -> int:
        """Returns current number of strings."""
        return self.num_strings.get()

    def get_num_frets(self) -> int:
        """Returns the number of frets."""
        return self.num_frets.get()


class ProcessButton(ttk.Frame):
    """
    The Analyze button: runs the analysis, then saves the outputs and the report. While the
    analysis runs, a progress bar takes the button's place, so the window keeps its size.
    """

    POLL_MS = 50                                   # worker result polling interval

    def __init__(
        self,
        parent,
        file_selector: FileSelectorWidget,
        tuning_widget: TuningWidget,
        part_selector: PartSelectorWidget,
        *args,
        **kwargs
    ):
        super().__init__(parent, *args, **kwargs)

        self.file_selector = file_selector
        self.tuning_widget = tuning_widget
        self.part_selector = part_selector

        self.run_button = ttk.Button(self, text='Analyze Playability', command=self._run_analysis)
        self.run_button.grid(row=0, column=0, pady=4)
        self.progress = ttk.Progressbar(self, mode='indeterminate')
        self.progress.grid(row=0, column=0, sticky='EW', padx=20)
        self.progress.grid_remove()                 # shown only while analyzing
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, minsize=self.run_button.winfo_reqheight() + 8)

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
            self.run_button.config(state='normal', text='Analyze Playability')

    def _run_analysis(self):
        """Run the analysis in a worker thread; results are handled in the Tk thread."""
        logger.info('=== Analysis started ===')

        if not self.file_selector.has_file():
            logger.warning('Analysis attempted without file selection')
            messagebox.showwarning(title=UI_TEXT['file_error'],
                                   message=UI_TEXT['no_file_selected'])
            return
        parts = self.part_selector.selected_parts()
        if not parts:
            messagebox.showwarning(title='ISPOG', message=UI_TEXT['no_parts_selected'])
            return

        try:
            config = AnalysisConfig(self.file_selector.get_filepath(),
                                    tuning=self.tuning_widget.get_tuning(),
                                    num_frets=self.tuning_widget.get_num_frets(),
                                    part_ids=[p.part_id for p in parts],
                                    output_mode=self.part_selector.get_output_mode(),
                                    labels=self.part_selector.get_labels())
        except ValueError as e:
            logger.warning(f'Invalid configuration: {e}')
            messagebox.showerror(title='Error', message=str(e))
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
        self._poll(config, parts, outcome)

    def _poll(self, config: AnalysisConfig, parts: list[PartInfo], outcome: queue.Queue) -> None:
        try:
            result, error = outcome.get_nowait()
        except queue.Empty:
            self.after(self.POLL_MS, self._poll, config, parts, outcome)
            return
        self._on_analysis_finished(config, parts, result, error)

    def _on_analysis_finished(self, config: AnalysisConfig, parts: list[PartInfo],
                              result: Optional[AnalysisResult],
                              error: Optional[Exception]) -> None:
        """Tk thread: stop the progress bar, then save the outputs or show the error."""
        self._set_busy(False)

        if error is not None:
            messagebox.showerror(title='Error', message=self._error_message(error))
        elif config.output_mode == 'split':
            self._save_split(config, parts, result)
        else:
            self._save_full(config, result)
        logger.info('=== Analysis finished ===')

    def _save_full(self, config: AnalysisConfig, result: AnalysisResult) -> None:
        source = config.filepath
        target = ask_save_file(full_output_name(source), source.parent)
        if target is None:
            logger.info('Save cancelled by user')
            return
        report = report_path_for(target)
        if self._write({target: result.outputs['full']}, report, result):
            self._show_summary(result, [target.name], report.name)

    def _save_split(self, config: AnalysisConfig, parts: list[PartInfo],
                    result: AnalysisResult) -> None:
        source = config.filepath
        folder = ask_output_dir(source.parent)
        if folder is None:
            logger.info('Save cancelled by user')
            return
        names = split_output_names(source, parts)
        files = {folder / names[pid]: data for pid, data in result.outputs.items()}
        report = folder / split_report_name(source)
        existing = [p.name for p in [*files, report] if p.exists()]
        if existing and not messagebox.askyesno(
                title=UI_TEXT['overwrite_title'],
                message=UI_TEXT['overwrite'].format(files='\n'.join(existing))):
            logger.info('Overwrite declined by user')
            return
        if self._write(files, report, result):
            self._show_summary(result, [p.name for p in files], report.name)

    def _write(self, files: dict[Path, bytes], report: Path, result: AnalysisResult) -> bool:
        try:
            for path, data in files.items():
                path.write_bytes(data)
            report.write_text(render_report(result), encoding='utf-8')
            write_notes_logs(result, writable_path(LOG_DIR))
        except OSError as e:
            logger.error('Saving failed', exc_info=True)
            messagebox.showerror(title='Error', message=f'Could not save the files:\n{e}')
            return False
        logger.info(f'Saved {", ".join(str(p) for p in files)} and {report}')
        return True

    def _show_summary(self, result: AnalysisResult, scores: list[str], report: str) -> None:
        summary = '\n'.join(self._part_summary(r) for r in result.reports)
        saved = UI_TEXT['saved'].format(score='\n'.join(scores), report=report)
        messagebox.showinfo(title=UI_TEXT['complete'], message=f'{summary}\n\n{saved}')

    @staticmethod
    def _part_summary(report: PartReport) -> str:
        counts = report.counts
        red_measures = report.red_measures
        where = ''
        if red_measures:
            shown = ', '.join(red_measures[:8]) + (' …' if len(red_measures) > 8 else '')
            where = UI_TEXT['part_summary_where'].format(measures=shown)
        total = counts['green'] + counts['orange'] + counts['red']
        return UI_TEXT['part_summary'].format(name=report.name, total=total,
                                              orange=counts['orange'], red=counts['red'],
                                              where=where)

    @staticmethod
    def _error_message(error: Exception) -> str:
        if isinstance(error, IspogError):
            return str(error)
        return UI_TEXT['unexpected_error'].format(error=error, log=current_log_file() or '-')
