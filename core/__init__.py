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
    main  # Legacy compatibility
)

# Analyzer
from .analyzer import ChordAnalyzer

# Entities
from .entities import Note, Bar, Fretboard, NewNote
from .entities import nota, bar, fretboard, newNote  # Legacy aliases

# MusicXML processing
from .musicxml import (
    parse_measures,
    merge_bars_to_score,
    analyze_score_playability,
    write_colored_score,
    add_ispog_credit,
    create_debug_note_list,
    # Legacy aliases
    makeBarList,
    mergeBarList,
    makeColor,
    rewriteScore,
    addMark,
    debugNoteList,
)

__all__ = [
    # Processor
    'analyze_file',
    'PlayabilityAnalyzer',
    'AnalysisConfig',
    'main',
    # Analyzer
    'ChordAnalyzer',
    # Entities
    'Note',
    'Bar',
    'Fretboard',
    'NewNote',
    'nota',
    'bar',
    'fretboard',
    'newNote',
    # MusicXML
    'parse_measures',
    'merge_bars_to_score',
    'analyze_score_playability',
    'write_colored_score',
    'add_ispog_credit',
    'create_debug_note_list',
    'makeBarList',
    'mergeBarList',
    'makeColor',
    'rewriteScore',
    'addMark',
    'debugNoteList',
]
