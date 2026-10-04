# -*- coding: utf-8 -*-
"""
ISPOG - Chord Analyzer
Fingerings of the notes attacked at one onset, with the notes still held as constraints.

For every assignment of the attacked notes to free strings, ``core.fingering`` assigns the
fingers (held notes keep string, fret and finger) and grades the hand shape. The choice
among the candidates is made by the playability engine over the whole part
(``core.playability``), not here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Sequence, Tuple

from config.settings import MAX_FINGERS

from .fingering import RANK, HandShape, Issue, Playability, Problem, ShapeSearch, hand_shapes
from .fretboard import Fretboard
from .model import NO_FRET, Note
from .stretch import StretchTable, default_table

__all__ = ['ChordAnalyzer', 'FingeringAnalysis', 'FretPosition', 'Issue', 'Placement',
           'Playability']

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FretPosition:
    """A string and a fret (0 = open string)."""
    string: int
    fret: int

    def is_open(self) -> bool:
        return self.fret == 0


@dataclass(frozen=True)
class Placement:
    """Where a held note is played: string, fret and finger (0 = open string)."""
    string: int
    fret: int
    finger: int


@dataclass
class FingeringAnalysis:
    """One fingering of the notes attacked at an onset."""
    playability: Playability
    positions: List[FretPosition]        # held notes first (``fixed``), then the attacked ones
    fingers_used: int
    has_barre: bool
    barre_fret: Optional[int] = None
    span: int = 0                        # highest - lowest fretted fret
    reason: str = ""                     # why difficult or unplayable
    issue: str = Issue.NONE              # machine-readable cause, see Issue
    fixed: List[FretPosition] = field(default_factory=list)   # positions of the held notes
    held: List[Note] = field(default_factory=list)            # the notes behind ``fixed``
    fingers: List[Optional[int]] = field(default_factory=list)  # per position, None: unknown
    attacked: List[Note] = field(default_factory=list)        # in the order of the positions
    cost: float = 0.0                    # ergonomic cost of the hand shape

    @property
    def new_positions(self) -> List[FretPosition]:
        return self.positions[len(self.fixed):]

    @property
    def new_fingers(self) -> List[Optional[int]]:
        return self.fingers[len(self.fixed):]


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


class ChordAnalyzer:
    """
    Fingerings of attacked notes given the held ones:

    - every attacked note on a free string;
    - fingers assigned by ``core.fingering`` (order, barrés, stretch table, crossings);
    - held notes keep string, fret and finger.
    """

    MAX_FINGERS = MAX_FINGERS

    def __init__(self, fretboard: Optional[Fretboard] = None,
                 table: Optional[StretchTable] = None):
        """
        Args:
            fretboard: used only to explain why a note has no position
                (``below the lowest string``, ``above fret 19``).
            table: stretch limits; the table shipped with ISPOG by default.
        """
        self._fretboard = fretboard
        self._table = table or default_table()
        self._cache: dict[tuple, list[FingeringAnalysis]] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def candidates(self, notes: Sequence[Note],
                   held: Sequence[tuple[Note, Placement]] = ()) -> List[FingeringAnalysis]:
        """
        Every playable or difficult fingering of ``notes`` (best first) or, if there is
        none, a single unplayable analysis with the closest fingering and the reason.
        Empty without pitched notes.

        Args:
            notes: notes attacked at the current onset.
            held: notes still sounding, with the placement they keep.
        """
        attacked = self.sort_notes_by_pitch([n for n in notes if n.midi is not None])
        if not attacked:
            return []
        key = (tuple(map(id, attacked)), tuple((id(n), p) for n, p in held))
        cached = self._cache.get(key)
        if cached is None:
            cached = self._candidates(attacked, list(held))
            self._cache[key] = cached
        return cached

    def analyze_positions(self, positions: Sequence[FretPosition]) -> FingeringAnalysis:
        """The best fingering of a fixed set of positions (no notes, nothing held)."""
        pairs = [(p.string, p.fret) for p in positions]
        search = hand_shapes(pairs, table=self._table)
        if search.valid:
            return self._from_shape(list(positions), search.valid[0], fixed=[])
        return self._unplayable_from_search(list(positions), search, fixed=[])

    @staticmethod
    def apply(analysis: FingeringAnalysis) -> None:
        """Write string, fret, finger, color and reason of ``analysis`` to its notes."""
        color = analysis.playability.value
        positions, fingers = analysis.new_positions, analysis.new_fingers
        for i, note in enumerate(analysis.attacked):
            pos = positions[i] if i < len(positions) else None
            note.set_fret((pos.string, pos.fret) if pos else NO_FRET)
            note.set_finger(fingers[i] if pos and i < len(fingers) else None)
            note.set_color(color)
            note.set_reason(analysis.reason)

    @staticmethod
    def sort_notes_by_pitch(notes: Sequence[Note]) -> List[Note]:
        """Sort by sounding pitch, highest first; stable for equal pitches."""
        return sorted(notes, key=lambda n: n.midi, reverse=True)

    # ------------------------------------------------------------------
    # Candidates
    # ------------------------------------------------------------------

    def _candidates(self, attacked: List[Note],
                    held: List[tuple[Note, Placement]]) -> List[FingeringAnalysis]:
        fixed = [FretPosition(p.string, p.fret) for _, p in held]
        pins = [p.finger for _, p in held]
        options = list(self._string_options(attacked, {p.string for p in fixed}))

        found: list[FingeringAnalysis] = []
        for option in options:
            positions = fixed + option
            search = hand_shapes([(p.string, p.fret) for p in positions],
                                 pins + [None] * len(option), self._table)
            for shape in search.valid:
                found.append(self._from_shape(positions, shape, fixed, held, attacked))
        if found:
            found.sort(key=lambda a: (RANK[a.playability], a.cost))
            return found

        analysis = self._unplayable(attacked, held, fixed, options)
        logger.debug('No fingering for %s: %s',
                     ' '.join(n.pitch_name for n in attacked), analysis.reason)
        return [analysis]

    @staticmethod
    def _string_options(notes: List[Note], used: set[int]) -> Iterator[List[FretPosition]]:
        """Every assignment of the notes to distinct free strings."""
        current: List[FretPosition] = []

        def recurse(i: int):
            if i == len(notes):
                yield list(current)
                return
            for string, fret in notes[i].get_fret_pos():
                if string in used:
                    continue
                used.add(string)
                current.append(FretPosition(string, fret))
                yield from recurse(i + 1)
                current.pop()
                used.discard(string)

        yield from recurse(0)

    def _from_shape(self, positions: List[FretPosition], shape: HandShape,
                    fixed: List[FretPosition], held: Sequence[tuple[Note, Placement]] = (),
                    attacked: Sequence[Note] = ()) -> FingeringAnalysis:
        if shape.playability is Playability.PLAYABLE:
            reason = 'playable' if shape.fingers_used else 'open strings'
        else:
            reason = self._problems_text(shape.problems, len(fixed))
        return FingeringAnalysis(
            playability=shape.playability, positions=positions,
            fingers_used=shape.fingers_used, has_barre=shape.barre_finger is not None,
            barre_fret=shape.barre_fret, span=shape.span, reason=reason, issue=shape.issue,
            fixed=fixed, held=[n for n, _ in held], fingers=list(shape.fingers),
            attacked=list(attacked), cost=shape.cost)

    # ------------------------------------------------------------------
    # Unplayable: closest fingering and reason
    # ------------------------------------------------------------------

    def _unplayable(self, attacked: List[Note], held: List[tuple[Note, Placement]],
                    fixed: List[FretPosition],
                    options: List[List[FretPosition]]) -> FingeringAnalysis:
        pins: List[Optional[int]] = [p.finger for _, p in held]
        if not options:
            reason, issue = self._explain_no_strings(attacked, held, fixed)
            return FingeringAnalysis(playability=Playability.UNPLAYABLE, positions=[],
                                     fingers_used=0, has_barre=False, reason=reason, issue=issue,
                                     fixed=fixed, held=[n for n, _ in held],
                                     attacked=attacked)

        # without pins: is the conflict only with the fingers of the held notes?
        free = [(option, hand_shapes([(p.string, p.fret) for p in fixed + option],
                                     table=self._table))
                for option in options]
        with_shape = [(option, s.valid[0]) for option, s in free if s.valid]
        if with_shape:
            # the new notes would need fingers that the held notes keep: no finger shown
            option, shape = min(with_shape, key=lambda o: (RANK[o[1].playability], o[1].cost))
            analysis = self._from_shape(fixed + option, shape, fixed, held, attacked)
            analysis.playability = Playability.UNPLAYABLE
            analysis.issue = Issue.FINGER_CONFLICT
            analysis.reason = self._finger_conflict_text(held)
            analysis.fingers = pins + [None] * len(option)
            return analysis

        option, search = min(free, key=lambda o: self._closeness(fixed + o[0], o[1]))
        analysis = self._unplayable_from_search(fixed + option, search, fixed)
        analysis.held = [n for n, _ in held]
        analysis.attacked = attacked
        if held:
            # the explanation is geometric; the held notes keep their own fingers
            analysis.fingers = pins + [None] * len(option)
        return analysis

    @staticmethod
    def _closeness(positions: List[FretPosition], search: ShapeSearch) -> tuple:
        """The closest impossible fingering: the most compact hand, then the smallest excess."""
        frets = [p.fret for p in positions if p.fret > 0]
        span = max(frets) - min(frets) if frets else 0
        if search.invalid:
            best = search.invalid[0]
            return (span, 0, best.excess, best.cost)
        return (span, 1, search.min_fingers, 0.0)

    def _unplayable_from_search(self, positions: List[FretPosition], search: ShapeSearch,
                                fixed: List[FretPosition]) -> FingeringAnalysis:
        if search.invalid:
            shape = search.invalid[0]
            return FingeringAnalysis(
                playability=Playability.UNPLAYABLE, positions=positions,
                fingers_used=shape.fingers_used, has_barre=shape.barre_finger is not None,
                barre_fret=shape.barre_fret, span=shape.span,
                reason=f'fret span {shape.span}: '
                       + self._problems_text(shape.problems[:1], len(fixed)),
                issue=Issue.SPAN, fixed=fixed, fingers=list(shape.fingers), cost=shape.cost)

        frets = [p.fret for p in positions if p.fret > 0]
        span = max(frets) - min(frets) if frets else 0
        needed = search.min_fingers
        if needed > self.MAX_FINGERS:
            reason, issue = f'requires {needed} fingers (max {self.MAX_FINGERS})', Issue.FINGERS
        else:
            reason = 'no hand position (open string under a barré, or crossed fingers)'
            issue = Issue.NO_SHAPE
        return FingeringAnalysis(
            playability=Playability.UNPLAYABLE, positions=positions, fingers_used=needed,
            has_barre=False, span=span, reason=reason, issue=issue, fixed=fixed,
            fingers=[None] * len(positions))

    @staticmethod
    def _problems_text(problems: Sequence[Problem], held_count: int) -> str:
        held = frozenset(range(held_count))
        return '; '.join(p.text + (' (held notes)' if p.indices and p.indices <= held else '')
                         for p in problems)

    @staticmethod
    def _finger_conflict_text(held: Sequence[tuple[Note, Placement]]) -> str:
        fretted = [f'{n.pitch_name} ({p.string}/{p.fret}:{p.finger})'
                   for n, p in sorted(held, key=lambda h: h[0].midi) if p.finger]
        return 'no free finger, held: ' + ' '.join(fretted)

    def _explain_no_strings(self, notes: List[Note], held: Sequence[tuple[Note, Placement]],
                            fixed: List[FretPosition]) -> Tuple[str, str]:
        """Why no string assignment exists for the attacked notes: (reason, issue)."""
        unreachable = [n for n in notes if not n.get_fret_pos()]
        if unreachable:
            return '; '.join(self._out_of_range(n) for n in unreachable), Issue.OUT_OF_RANGE

        if self._fretboard is not None:
            strings = self._fretboard.num_strings
        else:
            strings = len({s for n in notes for s, _ in n.get_fret_pos()}
                          | {p.string for p in fixed})
        if len(notes) + len(fixed) > strings:
            held_text = f" + {_count(len(fixed), 'held note')}" if fixed else ''
            return (f"{_count(len(notes), 'note')}{held_text} on {strings} strings",
                    Issue.STRINGS)

        if fixed:
            held_list = ', '.join(f'{n.pitch_name} ({p.string}/{p.fret})' for n, p in held)
            return f"string conflict with held notes: {held_list}", Issue.CONFLICT
        return "string conflict: " + ' '.join(n.pitch_name for n in notes), Issue.CONFLICT

    def _out_of_range(self, note: Note) -> str:
        if self._fretboard is None:
            return f"{note.pitch_name} out of range"
        detail = self._fretboard.out_of_range_reason(note.midi)
        return f"{note.pitch_name} out of range ({detail})"
