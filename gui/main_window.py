# -*- coding: utf-8 -*-
"""
ISPOG - Main Window
Main application window that assembles all widgets.
"""

import tkinter as tk
from tkinter import ttk

from config import APP_TITLE, APP_FULL_NAME, WINDOW_SIZE, WINDOW_RESIZABLE
from utils import get_logger
from .widgets import FileSelectorWidget, TuningWidget, ProcessButton

logger = get_logger(__name__)


class MainWindow(tk.Tk):
    """
    Main application window for ISPOG.
    Orchestrates all GUI components.
    """
    
    def __init__(self):
        super().__init__()
        
        logger.info('Initializing main window')
        
        # Window configuration
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.resizable(WINDOW_RESIZABLE, WINDOW_RESIZABLE)
        #self.minsize(400, 400)  
        
        # Version display
        self._version = tk.StringVar(self, '')
        
        # Create UI
        self._create_header()
        self._create_widgets()
        
        logger.info('Main window initialized successfully')
    
    def _create_header(self):
        """Create application header with title and version."""
        # Title
        title_label = ttk.Label(
            self,
            text=APP_FULL_NAME,
            font=('', 15),
            anchor='center'
        )
        title_label.pack(fill="x", padx=15, pady=(15, 0))
        
        # Version
        version_label = ttk.Label(
            self,
            textvariable=self._version,
            font=('', 8),
            anchor='center',
            foreground='gray'
        )
        version_label.pack(fill="x", padx=15, pady=(0, 5))
    
    def _create_widgets(self):
        """Create and layout all main widgets."""
        # File selector
        self.file_selector = FileSelectorWidget(self)
        self.file_selector.pack(fill="x", padx=15, pady=(5, 10))
        
        # Tuning configuration
        self.tuning_widget = TuningWidget(self)
        self.tuning_widget.pack(fill='x', padx=15, pady=(0, 10))
        
        # Process button
        self.process_button = ProcessButton(
            self,
            self.file_selector,
            self.tuning_widget
        )
        self.process_button.pack(fill="x", padx=15, pady=(0, 15))
    
    def set_version(self, version_string: str):
        """
        Set the version string displayed in the UI.
        
        Args:
            version_string: Version string to display
        """
        self._version.set(f'ver. {version_string}')
        logger.debug(f'Version set to: {version_string}')
