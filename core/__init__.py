# -*- coding: utf-8 -*-
"""
ISPOG - Core Package
MusicXML reading, playability analysis and writing. No GUI dependency (plan, D6).

    tree = load_score(path)
    for part in list_parts(tree):
        if part.is_guitar:
            notes = read_part(part)
            analyze_notes(notes, Fretboard(tuning, num_frets))
            colorize(notes)
    add_ispog_credit(tree)
    data = serialize(tree)
"""

# Errors
from .errors import IspogError, UnsupportedFileError, NoGuitarPartError

# Model
from .model import Note, PartInfo

# Reader
from .reader import load_score, to_partwise, list_parts, read_part

# Analysis
from .fretboard import Fretboard, note_name_to_midi
from .analyzer import ChordAnalyzer
from .playability import analyze_notes, ChordEvent, PlayabilityResult

# Writer
from .writer import colorize, set_notehead_color, add_ispog_credit, extract_part, serialize

# 0.9 pipeline, still used by the GUI; replaced in F5 (processor) and F6 (GUI)
from .processor import analyze_file, PlayabilityAnalyzer, AnalysisConfig

__all__ = [
    # Errors
    'IspogError',
    'UnsupportedFileError',
    'NoGuitarPartError',
    # Model
    'Note',
    'PartInfo',
    # Reader
    'load_score',
    'to_partwise',
    'list_parts',
    'read_part',
    # Analysis
    'Fretboard',
    'note_name_to_midi',
    'ChordAnalyzer',
    'analyze_notes',
    'ChordEvent',
    'PlayabilityResult',
    # Writer
    'colorize',
    'set_notehead_color',
    'add_ispog_credit',
    'extract_part',
    'serialize',
    # 0.9 pipeline
    'analyze_file',
    'PlayabilityAnalyzer',
    'AnalysisConfig',
]
