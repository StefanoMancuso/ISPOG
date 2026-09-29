# -*- coding: utf-8 -*-
"""
ISPOG - Core Package
Contains the core business logic and processing workflow.
"""

# Processor
from .processor import (
    analyze_file,
    PlayabilityAnalyzer,
    AnalysisConfig,
)

# Errors
from .errors import IspogError, UnsupportedFileError, NoGuitarPartError

# Analyzer
from .analyzer import ChordAnalyzer

# Entities
from .entities import Note, Bar, Fretboard, NewNote

# MusicXML processing
from .musicxml import (
    parse_measures,
    merge_bars_to_score,
    analyze_score_playability,
    write_colored_score,
    add_ispog_credit,
    create_debug_note_list,
)

__all__ = [
    # Processor
    'analyze_file',
    'PlayabilityAnalyzer',
    'AnalysisConfig',
    # Errors
    'IspogError',
    'UnsupportedFileError',
    'NoGuitarPartError',
    # Analyzer
    'ChordAnalyzer',
    # Entities
    'Note',
    'Bar',
    'Fretboard',
    'NewNote',
    # MusicXML
    'parse_measures',
    'merge_bars_to_score',
    'analyze_score_playability',
    'write_colored_score',
    'add_ispog_credit',
    'create_debug_note_list'
]
