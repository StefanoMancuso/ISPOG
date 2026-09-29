# -*- coding: utf-8 -*-
"""
ISPOG - Playability engine
Walks the notes of one part in time order and asks ChordAnalyzer to finger each onset.

At every onset the attacked notes are fingered together, with the notes still sounding
from earlier onsets as fixed constraints (string and fret already taken). Voices play no
role (plan, D4): only onsets and durations do. Tied continuations are not new attacks:
they extend the sounding duration of the note that starts the tie and inherit its result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import groupby
from typing import Optional

from .analyzer import ChordAnalyzer, FingeringAnalysis
from .fretboard import Fretboard
from .model import Note

logger = logging.getLogger(__name__)


@dataclass
class ChordEvent:
    """One call to the analyzer: what was attacked, what was held, and the outcome."""

    onset: Fraction
    measure_number: str
    notes: list[Note]
    held: list[Note]
    analysis: FingeringAnalysis
    grace: bool = False


@dataclass
class PlayabilityResult:
    """Outcome of ``analyze_notes`` for one part."""

    events: list[ChordEvent] = field(default_factory=list)
    not_analyzed: list[Note] = field(default_factory=list)   # pitched notes left black


def is_analyzable(note: Note) -> bool:
    """Pitched, not a cue note, not a harmonic (harmonics: plan §7)."""
    return note.midi is not None and not (note.is_rest or note.is_cue or note.is_harmonic)


def analyze_notes(notes: list[Note], fretboard: Fretboard) -> PlayabilityResult:
    """
    Color every analyzable note of one part (``color``, ``fret``, ``reason``).

    ``notes`` is the output of ``reader.read_part``. Notes that cannot be analyzed keep
    the color ``black`` and are listed in ``PlayabilityResult.not_analyzed``, with the
    reason set by the reader (microtone, harmonic...) or ``cue note``.
    """
    result = PlayabilityResult()
    candidates = []
    for note in notes:
        if is_analyzable(note):
            note.set_fret_pos(fretboard.positions(note.midi))
            candidates.append(note)
        elif not note.is_rest and not note.is_unpitched:
            if note.is_cue and not note.reason:
                note.reason = 'cue note'
            result.not_analyzed.append(note)

    ordered = sorted(candidates, key=lambda n: n.onset)       # stable: document order kept
    heads, continuations = _link_ties(ordered)

    analyzer = ChordAnalyzer(fretboard)
    active: list[tuple[Fraction, Note]] = []                  # (end, note) still sounding

    for onset, group in groupby(heads, key=lambda n: n.onset):
        group = list(group)
        active = [(end, n) for end, n in active if end > onset]
        sustained = [n for _, n in active]

        for grace_chord in _grace_chords(n for n in group if n.is_grace):
            _analyze(analyzer, result, onset, grace_chord, sustained, grace=True)

        attacks = [n for n in group if not n.is_grace]
        if attacks:
            _analyze(analyzer, result, onset, attacks, sustained)
            active += [(n.onset + n.sounding_duration, n) for n in attacks]

    _propagate_tie_results(continuations)
    logger.info('Analyzed %d notes in %d events (%d tied continuations, %d not analyzed)',
                len(candidates), len(result.events), len(continuations),
                len(result.not_analyzed))
    return result


def _analyze(analyzer: ChordAnalyzer, result: PlayabilityResult, onset: Fraction,
             notes: list[Note], sustained: list[Note], grace: bool = False) -> None:
    analysis = analyzer.analyze_chord(notes, sustained)
    if analysis is None:
        return
    held = [n for n in sustained if n.get_fret() != (-1, -1) and n.color != 'red']
    result.events.append(ChordEvent(onset=onset, measure_number=notes[0].measure_number,
                                    notes=notes, held=held, analysis=analysis, grace=grace))


def _grace_chords(graces) -> list[list[Note]]:
    """Group grace notes into chords: a note with ``<chord/>`` joins the previous one."""
    chords: list[list[Note]] = []
    for note in graces:
        if note.is_chord and chords:
            chords[-1].append(note)
        else:
            chords.append([note])
    return chords


def _link_ties(ordered: list[Note]) -> tuple[list[Note], dict[Note, Note]]:
    """
    Split notes into heads (analyzed) and tied continuations (not analyzed).

    A note with ``tie_stop`` continues the open tie with the same (staff, voice, pitch),
    or failing that the same (staff, pitch): some editors change voice across a tie.
    Its duration is added to the head's ``sounding_duration``. A continuation that also
    has ``tie_start`` keeps the tie open. A ``tie_stop`` with no open tie becomes a head.

    Returns:
        (heads in onset order, {continuation: head})
    """
    heads: list[Note] = []
    continuations: dict[Note, Note] = {}
    open_by_voice: dict[tuple, Note] = {}
    open_by_pitch: dict[tuple, Note] = {}

    for note in ordered:
        voice_key = (note.staff, note.voice, note.midi)
        pitch_key = (note.staff, note.midi)
        head: Optional[Note] = None
        if note.tie_stop:
            head = open_by_voice.get(voice_key) or open_by_pitch.get(pitch_key)
            if head is None:
                logger.warning('Tie stop without start: %s, measure %s, beat %s',
                               note.pitch_name, note.measure_number, note.beat_label)

        if head is not None:
            continuations[note] = head
            head.sounding_duration += note.duration
            _close(head, open_by_voice, open_by_pitch)
            if note.tie_start:
                _open(head, voice_key, pitch_key, open_by_voice, open_by_pitch)
            continue

        heads.append(note)
        if note.tie_start:
            _open(note, voice_key, pitch_key, open_by_voice, open_by_pitch)

    for head in set(open_by_voice.values()) | set(open_by_pitch.values()):
        logger.debug('Tie left open at the end of the part: %s, measure %s',
                     head.pitch_name, head.measure_number)
    return heads, continuations


def _open(head: Note, voice_key: tuple, pitch_key: tuple,
          by_voice: dict[tuple, Note], by_pitch: dict[tuple, Note]) -> None:
    by_voice[voice_key] = head
    by_pitch[pitch_key] = head


def _close(head: Note, by_voice: dict[tuple, Note], by_pitch: dict[tuple, Note]) -> None:
    for table in (by_voice, by_pitch):
        for key in [k for k, v in table.items() if v is head]:
            del table[key]


def _propagate_tie_results(continuations: dict[Note, Note]) -> None:
    """Tied continuations take the color, string, fret and reason of their head."""
    for note, head in continuations.items():
        note.set_color(head.color)
        note.set_fret(head.fret)
        note.set_reason(head.reason)
