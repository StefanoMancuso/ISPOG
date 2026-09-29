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

# Reader (lxml)
from .model import PartInfo
from .reader import load_score, to_partwise, list_parts, read_part
from .playability import analyze_notes, ChordEvent, PlayabilityResult

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
    # Reader
    'PartInfo',
    'load_score',
    'to_partwise',
    'list_parts',
    'read_part',
    'analyze_notes',
    'ChordEvent',
    'PlayabilityResult',
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
