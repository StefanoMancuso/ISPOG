# -*- coding: utf-8 -*-
"""
ISPOG - Configuration and Constants
Centralizes all configuration values and presets.
"""

from typing import Dict, List

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

APP_TITLE = "ISPOG"
APP_FULL_NAME = "Is it Playable on Guitar?"
WINDOW_SIZE = "400x420"  
WINDOW_RESIZABLE = True

# ============================================================================
# GUITAR CONFIGURATION
# ============================================================================

# Default values
DEFAULT_NUM_STRINGS = 6
DEFAULT_NUM_FRETS = 19
MIN_STRINGS = 4
MAX_STRINGS = 8

# Fret span for playability (maximum stretch)
MAX_FRET_SPAN = 4

# ============================================================================
# TUNING PRESETS
# ============================================================================

class TuningPreset:
    """Represents a guitar tuning preset."""
    
    def __init__(self, name: str, strings: int, notes: List[str]):
        self.name = name
        self.strings = strings
        self.notes = notes
    
    def get_tuning(self) -> List[str]:
        """Returns the tuning as a list of note strings."""
        return self.notes[:self.strings]

# Standard tunings (from highest to lowest string)
TUNING_PRESETS: Dict[str, TuningPreset] = {
    'standard': TuningPreset(
        name='Standard',
        strings=6,
        notes=['E4', 'B3', 'G3', 'D3', 'A2', 'E2', 'B1', 'F#1']
    ),
    'drop_d': TuningPreset(
        name='Drop D',
        strings=6,
        notes=['E4', 'B3', 'G3', 'D3', 'A2', 'D2', 'B1', 'F#1']
    ),
    'open_g': TuningPreset(
        name='Open G',
        strings=6,
        notes=['D4', 'B3', 'G3', 'D3', 'G2', 'D2', 'B1', 'F#1']
    ),
}

# Full note list for spinboxes (C0 to B8)
NOTE_LIST = tuple(
    f'{note}{octave}'
    for octave in range(9)
    for note in ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
)

# Note indices for standard tuning (E4, B3, G3, D3, A2, E2, B1, F#1)
STANDARD_TUNING_INDICES = [52, 47, 43, 38, 33, 28, 23, 18]

# ============================================================================
# FILE HANDLING
# ============================================================================

SUPPORTED_FILE_TYPES = (
    ('MusicXML files', '*.musicxml *.mxl'),
    ('MusicXML (uncompressed)', '*.musicxml'),
    ('MusicXML (compressed)', '*.mxl'),
    ('All files', '*.*')
)

FILE_EXTENSIONS = {
    'musicxml': 'MusicXML',
    'mxl': 'Compressed MusicXML',
}

# ============================================================================
# COLOR SCHEME
# ============================================================================

NOTE_COLORS = {
    'playable': 'green',
    'difficult': 'orange', 
    'unplayable': 'red',
    'default': 'black',
}

# Color codes for MusicXML
COLOR_CODES = {
    'red': '"#cf0000"',
    'green': '"#005000"',
    'orange': '"#ff8c00"',
    'black': '"#000000"'
}

# ============================================================================
# UI TEXT
# ============================================================================

UI_TEXT = {
    'no_file_loaded': 'No file loaded',
    'file_loaded': 'File loaded.. Ready!',
    'file_error': 'File Error',
    'no_file_selected': 'No file was loaded',
    'invalid_format': 'Not a MusicXML file. Maybe it is compressed?',
    'select_file': 'Select a file first',
    'processing': 'Processing...',
    'complete': 'Analysis complete!',
    'error_occurred': 'An error occurred during processing',
}

# ============================================================================
# LOGGING
# ============================================================================

LOG_DIR = 'logs'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
