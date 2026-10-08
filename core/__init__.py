# -*- coding: utf-8 -*-
"""
ISPOG - Core Package
MusicXML reading, playability analysis and writing. No GUI dependency (plan, D6).

    result = analyze(AnalysisConfig('score.mxl', tuning=('E4', 'B3', 'G3', 'D3', 'A2', 'E2')))
    score_bytes = result.outputs['full']
    report_text = render_report(result)
    names = output_names(result)            # default file names, same keys as outputs

Building blocks: load_score → list_parts → read_part → analyze_notes → colorize /
annotate → add_ispog_credit → serialize.
"""

# Errors
from .errors import IspogError, UnsupportedFileError, NoGuitarPartError

# Model
from .model import Note, PartInfo

# Reader
from .reader import load_score, to_partwise, list_parts, read_part

# Analysis
from .fretboard import Fretboard, note_name_to_midi, parse_tuning
from .analyzer import ChordAnalyzer
from .playability import analyze_notes, ChordEvent, PlayabilityResult

# Writer
from .writer import (colorize, set_notehead_color, annotate, remove_annotations,
                     add_ispog_credit, extract_part, serialize)

# Processor and reports
from .model import PartReport, AnalysisResult
from .processor import (AnalysisConfig, PartSettings, analyze, select_targets,
                        preselected_part_ids, write_notes_logs)
from .report import ProblemPoint, problem_points, render_report, render_summary, render_notes_tsv
from .naming import output_names, report_name

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
    'parse_tuning',
    'ChordAnalyzer',
    'analyze_notes',
    'ChordEvent',
    'PlayabilityResult',
    # Writer
    'colorize',
    'set_notehead_color',
    'annotate',
    'remove_annotations',
    'add_ispog_credit',
    'extract_part',
    'serialize',
    # Processor and reports
    'PartReport',
    'AnalysisResult',
    'AnalysisConfig',
    'PartSettings',
    'analyze',
    'select_targets',
    'preselected_part_ids',
    'write_notes_logs',
    'ProblemPoint',
    'problem_points',
    'render_report',
    'render_summary',
    'render_notes_tsv',
    'output_names',
    'report_name',
]
