# -*- coding: utf-8 -*-
"""
ISPOG - Playability engine
Walks the notes of one part in time order and chooses a fingering for every onset.

At every onset the attacked notes are fingered together, with the notes still sounding
from earlier onsets as fixed constraints: string, fret and finger already taken. Voices
play no role (plan, D4): only onsets and durations do. Tied continuations are not new
attacks: they extend the sounding duration of the note that starts the tie and inherit its
result.

The choice is not made onset by onset: a beam search keeps the best ``BEAM_WIDTH`` partial
fingerings of the part and the final choice is traced back from the best complete one. A
chord can thus take a fingering that is not its own best when that leaves the hand free for
what follows. Fingerings are compared by unplayable notes, then difficult notes, then
(at equal counts) unplayable notes as late as possible, then ergonomic cost: hand shape and
movement along the neck.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import groupby
from typing import Optional

from config.settings import BEAM_CANDIDATES, BEAM_WIDTH, POSITION_SHIFT_COST

from .analyzer import ChordAnalyzer, FingeringAnalysis, Placement, Playability
from .fretboard import Fretboard
from .model import Note

logger = logging.getLogger(__name__)


@dataclass
class ChordEvent:
    """One fingered onset: what was attacked, what was held, and the outcome."""

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
    Color every analyzable note of one part (``color``, ``fret``, ``finger``, ``reason``).

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

    search = _BeamSearch(ChordAnalyzer(fretboard))
    for onset, group in groupby(heads, key=lambda n: n.onset):
        search.step(onset, list(group))

    for choice in search.best_choices():
        ChordAnalyzer.apply(choice.analysis)
        result.events.append(ChordEvent(onset=choice.onset,
                                        measure_number=choice.notes[0].measure_number,
                                        notes=choice.notes, held=choice.analysis.held,
                                        analysis=choice.analysis, grace=choice.grace))

    _propagate_tie_results(continuations)
    logger.info('Analyzed %d notes in %d events (%d tied continuations, %d not analyzed)',
                len(candidates), len(result.events), len(continuations),
                len(result.not_analyzed))
    return result


# ---------------------------------------------------------------------------
# Beam search over the onsets
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Choice:
    onset: Fraction
    notes: list[Note]
    analysis: FingeringAnalysis
    grace: bool = False


# (unplayable notes, difficult notes, earliness of unplayable events, ergonomic cost)
_Cost = tuple[int, int, int, float]


@dataclass(frozen=True)
class _Path:
    """A partial fingering of the part: the last onset's choices and a link to the rest."""

    cost: _Cost
    state: tuple[tuple[Note, Placement], ...]        # held notes that constrain
    position: Optional[int]                          # lowest fretted fret of the hand
    parent: Optional[_Path] = None
    choices: tuple[_Choice, ...] = ()


class _BeamSearch:
    def __init__(self, analyzer: ChordAnalyzer):
        self._analyzer = analyzer
        self._paths = [_Path(cost=(0, 0, 0, 0.0), state=(), position=None)]
        self._active: list[tuple[Fraction, Note]] = []        # (end, note) still sounding
        self._index = 0                                        # onsets seen

    def step(self, onset: Fraction, group: list[Note]) -> None:
        """Extend every path with the notes attacked at ``onset``."""
        self._active = [(end, n) for end, n in self._active if end > onset]
        sounding = {n for _, n in self._active}
        self._index += 1

        graces = _grace_chords(n for n in group if n.is_grace)
        attacks = [n for n in group if not n.is_grace]

        extended: list[_Path] = []
        for path in self._merged(sounding):
            cost, choices = path.cost, []
            held = list(path.state)
            for chord in graces:                  # fingered alone: they do not constrain
                options = self._analyzer.candidates(chord, held)
                if options:
                    cost = self._add(cost, options[0], len(chord))
                    choices.append(_Choice(onset, chord, options[0], grace=True))
            if not attacks:
                extended.append(_Path(cost, path.state, path.position, path, tuple(choices)))
                continue
            for option in self._analyzer.candidates(attacks, held)[:BEAM_CANDIDATES]:
                extended.append(_Path(
                    cost=self._add(cost, option, len(attacks), path.position),
                    state=path.state + self._placements(option),
                    position=_hand_position(option, path.position),
                    parent=path,
                    choices=tuple(choices) + (_Choice(onset, attacks, option),)))

        extended.sort(key=lambda p: p.cost)
        self._paths = extended[:BEAM_WIDTH]
        if attacks:
            self._active += [(n.onset + n.sounding_duration, n) for n in attacks]

    def best_choices(self) -> list[_Choice]:
        """The choices of the best complete path, in onset order."""
        path: Optional[_Path] = min(self._paths, key=lambda p: p.cost)
        chain: list[tuple[_Choice, ...]] = []
        while path is not None:
            chain.append(path.choices)
            path = path.parent
        return [choice for choices in reversed(chain) for choice in choices]

    def _merged(self, sounding: set[Note]) -> list[_Path]:
        """Drop released notes from the states; equal states keep only their best path."""
        best: dict[tuple, _Path] = {}
        for path in self._paths:
            state = tuple((n, p) for n, p in path.state if n in sounding)
            key = (frozenset(state), path.position)
            if key not in best or path.cost < best[key].cost:
                best[key] = _Path(path.cost, state, path.position, path.parent, path.choices)
        return sorted(best.values(), key=lambda p: p.cost)

    def _add(self, cost: _Cost, analysis: FingeringAnalysis, count: int,
             position: Optional[int] = None) -> _Cost:
        red, orange, earliness, ergonomic = cost
        if analysis.playability is Playability.UNPLAYABLE:
            red += count
            earliness -= self._index
        elif analysis.playability is Playability.DIFFICULT:
            orange += count
        ergonomic += analysis.cost
        new_position = _hand_position(analysis, None)
        if position is not None and new_position is not None:
            ergonomic += POSITION_SHIFT_COST * abs(new_position - position)
        return red, orange, earliness, ergonomic

    @staticmethod
    def _placements(analysis: FingeringAnalysis) -> tuple[tuple[Note, Placement], ...]:
        """Placements of the attacked notes; unplayable notes do not constrain."""
        if analysis.playability is Playability.UNPLAYABLE:
            return ()
        return tuple((note, Placement(pos.string, pos.fret, finger or 0))
                     for note, pos, finger in zip(analysis.attacked, analysis.new_positions,
                                                  analysis.new_fingers))


def _hand_position(analysis: FingeringAnalysis, previous: Optional[int]) -> Optional[int]:
    """Lowest fretted fret of a playable fingering; the previous one otherwise."""
    if analysis.playability is Playability.UNPLAYABLE:
        return previous
    frets = [p.fret for p in analysis.positions if p.fret > 0]
    return min(frets) if frets else previous


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
    """Tied continuations take the color, string, fret, finger and reason of their head."""
    for note, head in continuations.items():
        note.set_color(head.color)
        note.set_fret(head.fret)
        note.set_finger(head.finger)
        note.set_reason(head.reason)
