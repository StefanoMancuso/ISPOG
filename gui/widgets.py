# -*- coding: utf-8 -*-
"""
ISPOG - GUI Widgets
Contains all custom widget classes for the GUI.
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional, Callable

from config.settings import (
    SUPPORTED_FILE_TYPES, TUNING_PRESETS, NOTE_LIST,
    STANDARD_TUNING_INDICES, MIN_STRINGS, MAX_STRINGS,
    UI_TEXT, DEFAULT_NUM_STRINGS
)
from utils.logger import get_logger
from core.processor import analyze_file

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
            file = filedialog.askopenfile(
                title='Open a MusicXML file (uncompressed)',
                initialdir=Path.home(),
                filetypes=SUPPORTED_FILE_TYPES
            )
            
            if file:
                self.filepath.set(file.name)
                self.status_text.set(UI_TEXT['file_loaded'])
                self.status_label.config(foreground='green')
                logger.info(f'File selected: {file.name}')
                
                messagebox.showinfo(
                    title='File Selected',
                    message=f'Selected:\n{Path(file.name).name}'
                )
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
    
    def _run_analysis(self):
        """Execute the playability analysis."""
        logger.info('=== Analysis started ===')
        
        # Validate file selection
        if not self.file_selector.has_file():
            logger.warning('Analysis attempted without file selection')
            messagebox.showwarning(
                title=UI_TEXT['file_error'],
                message=UI_TEXT['no_file_selected']
            )
            return
        
        filepath = self.file_selector.get_filepath()
        
        # Validate file extension
        if not filepath.endswith('.musicxml'):
            logger.warning(f'Invalid file extension: {filepath}')
            messagebox.showwarning(
                title=UI_TEXT['file_error'],
                message=UI_TEXT['invalid_format']
            )
            return
        
        # Get tuning configuration
        tuning = self.tuning_widget.get_tuning()
        num_strings = self.tuning_widget.get_num_strings()
        
        logger.info(f'Processing file: {filepath}')
        logger.info(f'Configuration: {num_strings} strings, tuning: {tuning}')
        
        # Disable button during processing, progress bar
        self.run_button.config(state='disabled', text=UI_TEXT['processing'])
        self.progress.pack(fill='x', padx=15, pady=(0, 10))
        self.progress.start(10)  # animation speed

        # thread function
        def worker():
            error = None
            try:
                analyze_file(filepath, num_strings, tuning)
            except Exception as e:
                error = e
                logger.error('Analysis failed', exc_info=True)

            # Back to main thread, upload GUI
            self.after(0, lambda: self._on_analysis_finished(error))

        threading.Thread(target=worker, daemon=True).start()

    def _on_analysis_finished(self, error: Exception | None):
        # Ferma e nascondi la progress bar
        self.progress.stop()
        self.progress.pack_forget()

        # Riabilita bottone
        self.run_button.config(state='normal', text='Analyze Playability')

        if error is None:
            logger.info('Analysis completed successfully')
            messagebox.showinfo(
                title='Success',
                message=UI_TEXT['complete']
            )
        else:
            messagebox.showerror(
                title='Error',
                message=f'{UI_TEXT["error_occurred"]}:\\n\\n{str(error)}'
            )
        logger.info('=== Analysis finished ===')
        