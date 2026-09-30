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
WINDOW_RESIZABLE = False       # the window takes the size of its content (gui/main_window.py)
MAX_NAME_CHARS = 34            # longer file names are shortened with an ellipsis

REPOSITORY_URL = "https://github.com/StefanoMancuso/ISPOG"
LICENSE_NAME = "GNU GPL v3.0 or later"
PAPER_CITATION = (
    "Crecchi N., Mancuso S. (2026). Dealing with a Guitar's Historical Limit through "
    "Computer-Assisted Composition. Proceedings of the 25th Colloquium on Music "
    "Informatics (CIM 2026), L'Aquila."
)

# ============================================================================
# GUITAR CONFIGURATION
# ============================================================================

# Default values
DEFAULT_NUM_STRINGS = 6
DEFAULT_NUM_FRETS = 19
MIN_FRETS = 12
MAX_FRETS = 24
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
    ('MusicXML files', '*.musicxml *.mxl *.xml'),
    ('MusicXML (uncompressed)', '*.musicxml *.xml'),
    ('MusicXML (compressed)', '*.mxl'),
    ('All files', '*.*')
)

# ============================================================================
# COLOR SCHEME
# ============================================================================

NOTE_COLORS = {
    'playable': 'green',
    'difficult': 'orange', 
    'unplayable': 'red',
    'default': 'black',
}

# Notehead colors written to MusicXML. The schema requires upper-case hex (#RRGGBB).
COLOR_CODES = {
    'red': '#CF0000',
    'green': '#005000',
    'orange': '#FF8C00',
    'black': '#000000',
}

# ============================================================================
# UI TEXT
# ============================================================================

UI_TEXT = {
    'no_file_loaded': 'No file loaded',
    'no_file_drop': 'No file loaded: browse or drop a score',
    'drop_active': 'Release to load the score',
    'file_loaded': 'File loaded. Ready!',
    'file_error': 'File Error',
    'no_file_selected': 'No file was loaded',
    'select_file': 'Select a file first',
    'processing': 'Processing...',
    'complete': 'Analysis complete!',
    'error_occurred': 'An error occurred during processing',
    'unexpected_error': 'Unexpected error: {error}\n\nDetails are in the log file:\n{log}',
    'save_title': 'Save analyzed score',
    'saved': 'Saved:\n{score}\n{report}',
    'parts_found': '{guitars} of {total} parts are guitars',
    'no_guitar_found': 'No guitar found: select the parts',
    'no_parts_selected': 'Select at least one part to analyze',
    'choose_folder': 'Choose a folder for the separate parts',
    'overwrite_title': 'Replace files?',
    'overwrite': 'These files already exist and will be replaced:\n{files}',
    'report_title': 'Report a problem',
    'report_intro': ('Send a report to the ISPOG developer. Nothing is sent until you '
                     'press Send.'),
    'report_always': 'Always included: log file and system information.',
    'report_analysis': 'Include last analysis (colored score and report)',
    'report_score': 'Include score file',
    'report_email': 'Your e-mail (optional, to be contacted):',
    'report_comment': 'What were you doing? What did you expect?',
    'report_send': 'Send',
    'report_sending': 'Sending…',
    'report_sent': 'Report sent. Thank you!',
    'report_failed': ('The report could not be sent:\n{error}\n\nOpen an e-mail with the details '
                      'instead? The log folder will open too, to attach the log file.'),
    'report_offer': '{message}\n\nSend a report to the developer?',
    'report_menu': 'Report a problem…',
    'about_title': 'About ISPOG',
    'about': ('{name}\nVersion {version}\n\n© 2026 Stefano Mancuso\nLicense: {license}\n'
              '{repository}\n\nIf you use ISPOG in research, please cite:\n{citation}'),
}

# Playability report (core/report.py)
REPORT_TEXT = {
    'title': 'ISPOG {version} — Playability report',
    'file': 'File:',
    'tuning': 'Tuning:',
    'tuning_value': '{tuning} · {frets} frets',
    'date': 'Date:',
    'part': '== {name} ({part_id}) ==',
    'summary': ('Notes analyzed {analyzed} · playable {green} ({percent}%) · difficult {orange}'
                ' · unplayable {red} · not analyzed {black}'),
    'point': 'm. {measure}, beat {beat} — {status}',
    'grace': ' (grace notes)',
    'unplayable': 'UNPLAYABLE',
    'difficult': 'DIFFICULT',
    'notes': 'Notes:',
    'held': 'Held:',
    'reason': 'Reason:',
    'closest': 'Closest:',
    'no_problems': 'No difficult or unplayable passages.',
    'not_analyzed': 'Not analyzed',
    'not_analyzed_item': 'm. {measure}, beat {beat} — {pitch}: {reason}',
    # One line per part in the end-of-analysis message (desktop dialog, web page)
    'short_summary': '{name}: {total} notes · {orange} difficult · {red} unplayable{where}',
    'short_summary_where': ' (m. {measures})',
}

# Short labels written above difficult and unplayable points in the score
# (core/writer.py, annotate). Keys are core.analyzer.Issue values.
LABEL_TEXT = {
    'fingers': '{fingers} fingers',
    'span': 'span {span}',
    'out_of_range': 'out of range',
    'strings': 'no free string',
    'conflict': 'string conflict',
    'pinky_barre': 'pinky barré',
    'stretch': 'stretch',
}

# ============================================================================
# BUG REPORTS (core/bugreport.py, server/bugreport.gs)
# ============================================================================

# Google Apps Script web app that e-mails the report to the maintainer.
BUGREPORT_URL = ("https://script.google.com/macros/s/"
                 "AKfycbxCdniXIp1lKOZCMFyS5F98UMhGLptcOIiOC5wMSt6m2hw81lzrR_LYvrPAwFO-tYg/exec")
# Spam filter shared with the script, not a secret: it ships in the app.
BUGREPORT_TOKEN = "ispog-c9261c2fe7321e7c"
# Address of the e-mail fallback when the report cannot be sent.
BUGREPORT_EMAIL = "stefanomancuso88@gmail.com"
BUGREPORT_MAX_BYTES = 15 * 1024 * 1024       # zip size; the script refuses larger ones
BUGREPORT_MAX_LOG_BYTES = 2 * 1024 * 1024    # only the end of a longer log is sent
BUGREPORT_TIMEOUT = 60                       # seconds

# ============================================================================
# WEB APP (app.py, render.yaml)
# ============================================================================

WEB_DEFAULT_PORT = 7860             # local runs; on Render the PORT variable decides
WEB_MAX_FILE_SIZE = '10mb'          # uploads above this size are refused by Gradio
WEB_FILE_MAX_AGE = 3600             # seconds: uploads and results are deleted after this
WEB_QUEUE_SIZE = 16                 # analyses waiting; further requests are turned away
WEB_SHOW_REPOSITORY = False         # link to the sources in the footer (public repository)

WEB_TEXT = {
    'title': 'ISPOG — Is it Playable on Guitar?',
    'intro': ('Upload a MusicXML score to check which notes and chords can be played on the '
              'guitar. Notes are colored in the score: **green** playable, **orange** '
              'difficult, **red** unplayable, black not analyzed.'),
    'score': 'Score (.musicxml, .mxl, .xml)',
    'parts': 'Parts to analyze',
    'output': 'Output',
    'output_full': 'Full score',
    'output_split': 'Separate parts',
    'labels': 'Add labels to score',
    'tuning': 'Tuning',
    'custom': 'Custom',
    'strings': 'Strings',
    'string': 'String {number}',
    'frets': 'Frets',
    'analyze': 'Analyze Playability',
    'results': 'Colored score and report',
    'report': 'Report',
    'summary_title': '**Analysis complete**',
    'unexpected_error': 'Unexpected error. The analysis could not be completed.',
    'privacy': ('Scores are analyzed on the server only to produce the results shown here: '
                'uploaded files and results are deleted within an hour and are not shared. '
                'On the free server the first analysis after a pause can take up to a minute.'),
    'footer': 'ISPOG {version} · {license}',
    'footer_repository': '[Source code]({url})',
    'cite': 'Please cite: {citation}',
}

# ============================================================================
# LOGGING
# ============================================================================

LOG_DIR = 'logs'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
