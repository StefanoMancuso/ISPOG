# -*- coding: utf-8 -*-
"""
ISPOG - Data model
Plain data objects shared by the reader, the playability engine and the writer.

Time is measured in quarter notes as ``fractions.Fraction`` (plan, D3); pitch is the
sounding MIDI number, with ``<transpose>`` already applied (plan, D5). Each ``Note`` keeps a
reference to its ``<note>`` element (plan, D2), so the writer colors the element directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING, Optional

from lxml import etree

if TYPE_CHECKING:
    from .playability import ChordEvent

STEP_SEMITONES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_ACCIDENTALS = {-2: 'bb', -1: 'b', 0: '', 1: '#', 2: '##'}

NO_FRET = (-1, -1)
DEFAULT_COLOR = 'black'


def format_beat(beat: Fraction) -> str:
    """``3`` if the beat is whole, ``2 1/2`` otherwise."""
    whole, rest = divmod(beat, 1)
    if rest == 0:
        return str(int(whole))
    return f'{int(whole)} {rest}' if whole else str(rest)


@dataclass(frozen=True, eq=False)
class PartInfo:
    """A ``<part>`` of the score, as listed in ``<part-list>``."""

    part_id: str
    name: str
    is_guitar: bool
    element: etree._Element = field(repr=False)


@dataclass(eq=False)
class Note:
    """
    One ``<note>`` element: a pitched note, a rest or an unpitched note.

    Identity semantics (``eq=False``): two notes with the same pitch and onset are still
    different objects, as the analyzer uses them as keys and compares them in lists.
    """

    # Source
    element: Optional[etree._Element] = field(repr=False)
    part_id: str
    measure_number: str
    voice: str = '1'
    staff: int = 1

    # Time, in quarter notes from the start of the part
    onset: Fraction = Fraction(0)
    duration: Fraction = Fraction(0)
    beat: Fraction = Fraction(1)                  # 1-based, in units of the time signature

    # Pitch (written pitch as in the file; ``midi`` is sounding)
    step: Optional[str] = None
    octave: Optional[int] = None
    alter: Fraction = Fraction(0)
    midi: Optional[int] = None

    # Kind
    is_rest: bool = False
    is_unpitched: bool = False
    is_chord: bool = False
    is_grace: bool = False
    is_cue: bool = False
    is_harmonic: bool = False
    tie_start: bool = False
    tie_stop: bool = False

    # Analysis state, filled by the playability engine
    fret_pos: list[tuple[int, int]] = field(default_factory=list)
    fret: tuple[int, int] = NO_FRET
    color: str = DEFAULT_COLOR
    reason: str = ''
    sounding_duration: Optional[Fraction] = None  # duration including tied continuations

    def __post_init__(self) -> None:
        if self.sounding_duration is None:
            self.sounding_duration = self.duration

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_element(
        cls,
        el: etree._Element,
        *,
        part_id: str,
        measure_number: str,
        onset: Fraction,
        duration: Fraction,
        beat: Fraction,
        transpose: int = 0,
    ) -> Note:
        """
        Build a note from its ``<note>`` element. Timing comes from the reader, which
        tracks the position in the measure; ``transpose`` is the written-to-sounding
        interval in semitones.
        """
        note = cls(
            element=el,
            part_id=part_id,
            measure_number=measure_number,
            voice=(el.findtext('voice') or '1').strip(),
            staff=int(el.findtext('staff') or 1),
            onset=onset,
            duration=duration,
            beat=beat,
            is_rest=el.find('rest') is not None,
            is_unpitched=el.find('unpitched') is not None,
            is_chord=el.find('chord') is not None,
            is_grace=el.find('grace') is not None,
            is_cue=el.find('cue') is not None,
            is_harmonic=el.find('notations/technical/harmonic') is not None,
        )
        note._read_ties(el)
        pitch = el.find('pitch')
        if pitch is not None:
            note._read_pitch(pitch, transpose)
        elif note.is_unpitched:
            note.reason = 'unpitched note'
        if note.is_harmonic and not note.reason:
            note.reason = 'harmonic (not supported)'
        return note

    def _read_pitch(self, pitch: etree._Element, transpose: int) -> None:
        self.step = (pitch.findtext('step') or '').strip().upper()
        self.octave = int(pitch.findtext('octave'))
        self.alter = Fraction((pitch.findtext('alter') or '0').strip())
        if self.step not in STEP_SEMITONES:
            raise ValueError(f'invalid pitch step {self.step!r}')
        if self.alter.denominator != 1:
            self.reason = 'microtone not analyzed'
            return
        self.midi = (12 * (self.octave + 1) + STEP_SEMITONES[self.step]
                     + int(self.alter) + transpose)

    def _read_ties(self, el: etree._Element) -> None:
        types = {t.get('type') for t in el.iterfind('tie')}
        if not types:
            types = {t.get('type') for t in el.iterfind('notations/tied')}
        self.tie_start = bool(types & {'start', 'continue'})
        self.tie_stop = bool(types & {'stop', 'continue'})

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    @property
    def pitch_name(self) -> str:
        """Written pitch, e.g. ``G#3``; ``rest`` for rests and unpitched notes."""
        if self.step is None:
            return 'rest'
        if self.alter.denominator == 1 and int(self.alter) in _ACCIDENTALS:
            accidental = _ACCIDENTALS[int(self.alter)]
        else:
            accidental = f'({float(self.alter):+g})'
        return f'{self.step}{accidental}{self.octave}'

    @property
    def beat_label(self) -> str:
        return format_beat(self.beat)

    # ------------------------------------------------------------------
    # Interface used by ChordAnalyzer (same names as the 0.9 Note)
    # ------------------------------------------------------------------

    def get_pitch(self) -> list[str]:
        """``['rest', '0']`` without a pitch, else ``['C4', '<alter>']``."""
        if self.step is None:
            return ['rest', '0']
        return [f'{self.step}{self.octave}', f'{self.alter}']

    def get_fret_pos(self) -> list[tuple[int, int]]:
        return self.fret_pos

    def set_fret_pos(self, positions: list[tuple[int, int]]) -> None:
        self.fret_pos = list(positions)

    def get_fret(self) -> tuple[int, int]:
        return self.fret

    def set_fret(self, fret: tuple[int, int]) -> None:
        self.fret = fret

    def get_color(self) -> str:
        return self.color

    def set_color(self, color: str) -> None:
        self.color = color

    def set_reason(self, reason: str) -> None:
        self.reason = reason


# ---------------------------------------------------------------------------
# Analysis results
# ---------------------------------------------------------------------------

@dataclass
class PartReport:
    """Outcome of the analysis of one part."""

    part_id: str
    name: str
    notes: list[Note] = field(repr=False)
    events: list[ChordEvent] = field(repr=False)     # analyzer calls, in onset order
    not_analyzed: list[Note] = field(repr=False)     # pitched notes left black, with reason

    @property
    def pitched(self) -> list[Note]:
        return [n for n in self.notes if n.step is not None]

    @property
    def counts(self) -> dict[str, int]:
        """Pitched notes per color: green, orange, red, black (not analyzed)."""
        counts = dict.fromkeys(('green', 'orange', 'red', 'black'), 0)
        for note in self.pitched:
            counts[note.color] += 1
        return counts

    def measures_with(self, color: str) -> list[str]:
        """Measure numbers containing a note of ``color``, in score order, without repeats."""
        return list(dict.fromkeys(n.measure_number for n in self.pitched if n.color == color))

    @property
    def red_measures(self) -> list[str]:
        return self.measures_with('red')


@dataclass
class AnalysisResult:
    """
    Everything an analysis produces; nothing is saved. ``outputs`` maps ``'full'``, or each
    part id in split mode, to the MusicXML file content.
    """

    source_name: str
    tuning: tuple[str, ...]
    num_frets: int
    outputs: dict[str, bytes] = field(repr=False)
    reports: list[PartReport]
