# -*- coding: utf-8 -*-
"""
ISPOG - Reports
The readable playability report for composers, and the technical note list (TSV) for
development. Both are returned as text: saving them is the caller's job.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from config.settings import REPORT_TEXT as T
from config.version import __version__

from .analyzer import Playability
from .model import DEFAULT_COLOR, NOT_AS_WRITTEN_COLOR, AnalysisResult, Note, PartReport
from .playability import ChordEvent

_STATUS = {Playability.DIFFICULT: T['difficult'], Playability.UNPLAYABLE: T['unplayable']}
_LABEL_WIDTH = 8                    # longest labels: 'Closest:', 'Fingers:'


def render_report(result: AnalysisResult, now: Optional[datetime] = None) -> str:
    """
    Playability report: header, a summary per part, then only the difficult and unplayable
    points in score order (notes attacked, notes held, reason, closest fingering found),
    then the notes playable only as one note (unisons), then the notes that were not
    analyzed and why.
    """
    now = now or datetime.now()
    lines = [
        T['title'].format(version=__version__),
        _field(T['file'], result.source_name),
        _field(T['tuning'], T['tuning_value'].format(tuning=' '.join(result.tuning),
                                                     frets=result.num_frets)),
        _field(T['date'], now.strftime('%Y-%m-%d %H:%M')),
        _field(T['positions'], T['positions_value']),
    ]
    for report in result.reports:
        lines += ['', *_part_section(report)]
    return '\n'.join(lines) + '\n'


def render_summary(report: PartReport, max_measures: int = 8) -> str:
    """
    One line for the end-of-analysis message:
    ``Guitar: 120 notes · 3 difficult · 1 unplayable (m. 12)``.
    """
    counts = report.counts
    red_measures = report.red_measures
    where = ''
    if red_measures:
        shown = ', '.join(red_measures[:max_measures])
        if len(red_measures) > max_measures:
            shown += ' …'
        where = T['short_summary_where'].format(measures=shown)
    total = _analyzed(counts)
    purple = (T['short_summary_purple'].format(purple=counts[NOT_AS_WRITTEN_COLOR])
              if counts[NOT_AS_WRITTEN_COLOR] else '')
    return T['short_summary'].format(name=report.name, total=total, orange=counts['orange'],
                                     red=counts['red'], purple=purple, where=where)


def _analyzed(counts: dict[str, int]) -> int:
    return sum(n for color, n in counts.items() if color != DEFAULT_COLOR)


def _part_section(report: PartReport) -> list[str]:
    counts = report.counts
    analyzed = _analyzed(counts)
    percent = round(100 * counts['green'] / analyzed) if analyzed else 0
    lines = [
        T['part'].format(name=report.name, part_id=report.part_id),
        T['summary'].format(analyzed=analyzed, percent=percent, **counts),
    ]
    problems = [e for e in report.events
                if e.analysis.playability is not Playability.PLAYABLE]
    if not problems:
        lines += ['', T['no_problems']]
    for event in problems:
        lines += ['', *_event_block(event)]
    for title, notes in ((T['unisons'], report.unisons),
                         (T['not_analyzed'], report.not_analyzed)):
        if notes:
            lines += ['', title, *('  ' + _note_item(n) for n in notes)]
    return lines


def _note_item(note: Note) -> str:
    return T['not_analyzed_item'].format(measure=note.measure_number, beat=note.beat_label,
                                         pitch=note.pitch_name, reason=note.reason)


def _event_block(event: ChordEvent) -> list[str]:
    analysis = event.analysis
    notes = sorted(event.notes, key=lambda n: n.midi)             # low to high
    status = _STATUS[analysis.playability] + (T['grace'] if event.grace else '')
    block = [
        T['point'].format(measure=event.measure_number, beat=notes[0].beat_label,
                          status=status),
        _field(T['notes'], ' '.join(n.pitch_name for n in notes), indent=2),
    ]
    if event.held:
        held = ' '.join(f'{n.pitch_name} ({_position(n)})'
                        for n in sorted(event.held, key=lambda n: n.midi))
        block.append(_field(T['held'], held, indent=2))
    block.append(_field(T['reason'], analysis.reason, indent=2))
    if any(n.fret != (-1, -1) for n in notes):
        block.append(_field(T['closest'], ' '.join(_position(n) for n in notes), indent=2))
    return block


def _position(note: Note, finger: bool = True) -> str:
    """``string/fret:finger`` (finger only on fretted notes), or ``-`` without a position."""
    string, fret = note.fret
    if string <= 0:
        return '-'
    if finger and fret > 0 and note.finger:
        return f'{string}/{fret}:{note.finger}'
    return f'{string}/{fret}'


def _field(label: str, value: str, indent: int = 0) -> str:
    """``label`` padded so that values line up, always followed by a space."""
    return f"{' ' * indent}{label:<{_LABEL_WIDTH}} {value}"


# ---------------------------------------------------------------------------
# Technical log
# ---------------------------------------------------------------------------

NOTES_TSV_FIELDS = ('measure', 'beat', 'onset', 'pitch', 'midi', 'voice', 'staff',
                    'string/fret', 'finger', 'color', 'reason')


def render_notes_tsv(report: PartReport) -> str:
    """Every note of a part, one per line, tab-separated: for debugging, not for composers."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter='\t', lineterminator='\n')
    writer.writerow(NOTES_TSV_FIELDS)
    for n in report.notes:
        writer.writerow([n.measure_number, n.beat_label, n.onset, n.pitch_name,
                         '' if n.midi is None else n.midi, n.voice, n.staff,
                         _position(n, finger=False) if n.step is not None else '',
                         '' if n.finger is None else n.finger, n.color, n.reason])
    return buffer.getvalue()
