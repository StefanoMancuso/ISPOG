# -*- coding: utf-8 -*-
"""
ISPOG - GUI Widgets
Contains all custom widget classes for the GUI.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Optional

from config.settings import (
    TUNING_PRESETS, NOTE_LIST, STANDARD_TUNING_INDICES, MIN_STRINGS, MAX_STRINGS,
    UI_TEXT, DEFAULT_NUM_STRINGS, LOG_DIR
)
from core import (AnalysisConfig, AnalysisResult, IspogError, analyze, render_report,
                  write_notes_logs)
from utils.io import writable_path
from utils.logger import current_log_file, get_logger
from .dialogs import ask_open_file, ask_save_file

logger = get_logger(__name__)


class FileSelectorWidget(ttk.LabelFrame):
    """
    Widget for selecting MusicXML files.
    Provides file dialog and displays selection status.
    """
    
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, text="File Selection", *args, **kwargs)
        
        self.filepath = tk.StringVar(self, '')
        self.status_text = tk.StringVar(self, UI_TEXT['no_file_loaded'])
        
        # Load button
        self.load_button = ttk.Button(
            self,
            text='Load MusicXML File',
            command=self._select_file
        )
        self.load_button.pack(pady=10, padx=15)
        
        # Status label
        self.status_label = ttk.Label(
            self,
            textvariable=self.status_text,
            anchor='center',
            foreground='gray'
        )
        self.status_label.pack(fill='x', padx=15, pady=(0, 10))
        
        logger.debug('FileSelectorWidget initialized')
    
    def _select_file(self):
        """Open file dialog and handle file selection."""
        logger.info('Opening file selection dialog')
        
        try:
            current = self.get_filepath()
            path = ask_open_file(Path(current).parent if current else Path.home())

            if path:
                self.filepath.set(str(path))
                self.status_text.set(path.name)
                self.status_label.config(foreground='green')
                logger.info(f'File selected: {path}')
            else:
                logger.info('File selection cancelled by user')
                
        except Exception as e:
            logger.error(f'Error selecting file: {e}', exc_info=True)
            messagebox.showerror(
                title='Error',
                message=f'Failed to open file:\n{str(e)}'
            )
    
    def get_filepath(self) -> Optional[str]:
        """Returns the selected file path, or None if no file selected."""
        path = self.filepath.get()
        return path if path else None
    
    def has_file(self) -> bool:
        """Returns True if a file has been selected."""
        return bool(self.filepath.get())


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
        
        self._create_preset_selection()
        self._create_string_count_selector()
        self._create_tuning_spinboxes()
        
        # Apply initial tuning
        self._apply_preset_tuning()
        
        logger.debug('TuningWidget initialized')
    
    def _create_preset_selection(self):
        """Create radio buttons for preset tunings."""
        preset_frame = ttk.Frame(self)
        preset_frame.grid(row=0, column=0, rowspan=4, sticky='W', padx=15, pady=5)
        
        # Radio buttons for each preset
        self.preset_buttons = {}
        for idx, (key, preset) in enumerate(TUNING_PRESETS.items()):
            rb = ttk.Radiobutton(
                preset_frame,
                text=preset.name,
                variable=self.tuning_mode,
                value=key,
                command=self._on_tuning_change
            )
            rb.grid(row=idx, column=0, sticky='W', pady=2)
            self.preset_buttons[key] = rb
        
        # Custom tuning option
        custom_rb = ttk.Radiobutton(
            preset_frame,
            text='Custom',
            variable=self.tuning_mode,
            value='custom',
            command=self._on_tuning_change
        )
        custom_rb.grid(row=len(TUNING_PRESETS), column=0, sticky='W', pady=2)
    
    def _create_string_count_selector(self):
        """Create spinbox for number of strings."""
        self.string_count_spinbox = ttk.Spinbox(
            self,
            from_=MIN_STRINGS,
            to=MAX_STRINGS,
            textvariable=self.num_strings,
            width=4,
            state='disabled',
            command=self._on_string_count_change
        )
        self.string_count_spinbox.grid(row=0, column=1, padx=10, sticky='E')
        
        ttk.Label(self, text='Number of strings').grid(
            row=0, column=2, sticky='W'
        )
    
    def _create_tuning_spinboxes(self):
        """Create spinboxes for individual string tuning."""
        self.tuning_spinboxes = []
        
        # Layout: 6 strings in 3x2 grid, 7-8 strings in additional column
        positions = [
            (1, 1, 2), (2, 1, 2), (3, 1, 2),  # Strings 1-3
            (1, 2, 3), (2, 2, 3), (3, 2, 3),  # Strings 4-6
            (1, 5, 6), (2, 5, 6)               # Strings 7-8
        ]
        
        for idx, (row, col_spinbox, col_label) in enumerate(positions):
            # Spinbox
            spinbox = ttk.Spinbox(
                self,
                values=NOTE_LIST,
                textvariable=self.string_vars[idx],
                width=4,
                state='disabled'
            )
            spinbox.grid(row=row, column=col_spinbox, padx=10, sticky='E')
            self.tuning_spinboxes.append(spinbox)
            
            # Label
            ttk.Label(self, text=f'{idx+1}°').grid(
                row=row, column=col_label, sticky='W'
            )
    
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


class ProcessButton(ttk.LabelFrame):
    """
    Widget containing the Run button and processing logic.
    """
    
    def __init__(
        self,
        parent,
        file_selector: FileSelectorWidget,
        tuning_widget: TuningWidget,
        *args,
        **kwargs
    ):
        super().__init__(parent, text="Analysis", *args, **kwargs)
        
        self.file_selector = file_selector
        self.tuning_widget = tuning_widget
        
        # Run button
        self.run_button = ttk.Button(
            self,
            text='Analyze Playability',
            command=self._run_analysis
        )
        self.run_button.pack(pady=(15, 5), padx=15)

        # Progress bar indeterminata (inizialmente ferma/nascosta)
        self.progress = ttk.Progressbar(
            self,
            mode='indeterminate'
        )
        self.progress.pack(fill='x', padx=15, pady=(0, 10))
        self.progress.stop()
        self.progress.pack_forget()  # la nascondiamo all'inizio        

        logger.debug('ProcessButton initialized')
    
    POLL_MS = 50                                   # worker result polling interval

    def _run_analysis(self):
        """Run the analysis in a worker thread; results are handled in the Tk thread."""
        logger.info('=== Analysis started ===')

        if not self.file_selector.has_file():
            logger.warning('Analysis attempted without file selection')
            messagebox.showwarning(
                title=UI_TEXT['file_error'],
                message=UI_TEXT['no_file_selected']
            )
            return

        try:
            config = AnalysisConfig(self.file_selector.get_filepath(),
                                    tuning=self.tuning_widget.get_tuning())
        except ValueError as e:
            logger.warning(f'Invalid configuration: {e}')
            messagebox.showerror(title='Error', message=str(e))
            return

        self.run_button.config(state='disabled', text=UI_TEXT['processing'])
        self.progress.pack(fill='x', padx=15, pady=(0, 10))
        self.progress.start(10)

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

    def _on_analysis_finished(self, config: AnalysisConfig,
                              result: Optional[AnalysisResult],
                              error: Optional[Exception]) -> None:
        """Tk thread: stop the progress bar, then save the outputs or show the error."""
        self.progress.stop()
        self.progress.pack_forget()
        self.run_button.config(state='normal', text='Analyze Playability')

        if error is not None:
            messagebox.showerror(title='Error', message=self._error_message(error))
        else:
            self._save(config, result)
        logger.info('=== Analysis finished ===')

    def _save(self, config: AnalysisConfig, result: AnalysisResult) -> None:
        source = config.filepath
        target = ask_save_file(f'{source.stem}_ispog.musicxml', source.parent)
        if target is None:
            logger.info('Save cancelled by user')
            return
        report_path = target.with_name(f'{target.stem}_report.txt')
        try:
            target.write_bytes(result.outputs['full'])
            report_path.write_text(render_report(result), encoding='utf-8')
            write_notes_logs(result, writable_path(LOG_DIR))
        except OSError as e:
            logger.error('Saving failed', exc_info=True)
            messagebox.showerror(title='Error', message=f'Could not save the files:\n{e}')
            return
        logger.info(f'Saved {target} and {report_path}')
        summary = '\n'.join(self._part_summary(report) for report in result.reports)
        saved = UI_TEXT['saved'].format(score=target.name, report=report_path.name)
        messagebox.showinfo(title=UI_TEXT['complete'], message=f'{summary}\n\n{saved}')

    @staticmethod
    def _part_summary(report) -> str:
        counts = report.counts
        red_measures = report.red_measures
        where = ''
        if red_measures:
            where = UI_TEXT['part_summary_where'].format(measures=', '.join(red_measures[:8])
                                                         + (' …' if len(red_measures) > 8 else ''))
        total = counts['green'] + counts['orange'] + counts['red']
        return UI_TEXT['part_summary'].format(name=report.name, total=total,
                                              orange=counts['orange'], red=counts['red'],
                                              where=where)

    @staticmethod
    def _error_message(error: Exception) -> str:
        if isinstance(error, IspogError):
            return str(error)
        return UI_TEXT['unexpected_error'].format(error=error, log=current_log_file() or '-')
