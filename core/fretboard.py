# -*- coding: utf-8 -*-
"""
ISPOG - Fretboard
String and fret positions of a MIDI pitch for a given tuning.

Strings are numbered from 1 (highest, first in the tuning list) as on the guitar;
fret 0 is the open string.
"""

from __future__ import annotations

import re
from typing import Sequence

from .model import STEP_SEMITONES

_NOTE_NAME = re.compile(r'^([A-Ga-g])(##|#|bb|b|x)?(-?\d+)$')
_ACCIDENTAL_SEMITONES = {None: 0, '#': 1, '##': 2, 'x': 2, 'b': -1, 'bb': -2}


def note_name_to_midi(name: str) -> int:
    """
    MIDI number of a note name such as ``E4``, ``F#1`` or ``Bb3`` (C4 = 60).

    Raises:
        ValueError: the name is not a valid note name.
    """
    match = _NOTE_NAME.match(name.strip())
    if match is None:
        raise ValueError(f'invalid note name {name!r}')
    step, accidental, octave = match.groups()
    return 12 * (int(octave) + 1) + STEP_SEMITONES[step.upper()] + _ACCIDENTAL_SEMITONES[accidental]


def midi_to_note_name(midi: int) -> str:
    """Note name with sharps, e.g. ``54`` → ``F#3``."""
    names = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
    return f'{names[midi % 12]}{midi // 12 - 1}'


class Fretboard:
    """
    A guitar neck: open-string pitches (string 1 first) and number of frets.

    Example:
        >>> Fretboard(['E4', 'B3', 'G3', 'D3', 'A2', 'E2'], 19).positions(64)
        [(1, 0), (2, 5), (3, 9), (4, 14), (5, 19)]
    """

    def __init__(self, tuning: Sequence[str], num_frets: int):
        if not tuning:
            raise ValueError('tuning must name at least one string')
        if num_frets < 0:
            raise ValueError(f'invalid number of frets: {num_frets}')
        self.tuning = list(tuning)
        self.open_midi = [note_name_to_midi(n) for n in self.tuning]
        self.num_frets = num_frets

    @property
    def num_strings(self) -> int:
        return len(self.open_midi)

    def positions(self, midi: int) -> list[tuple[int, int]]:
        """All (string, fret) positions of a pitch, string 1 first."""
        return [(string, midi - open_midi)
                for string, open_midi in enumerate(self.open_midi, start=1)
                if 0 <= midi - open_midi <= self.num_frets]

    def out_of_range_reason(self, midi: int) -> str:
        """Why a pitch has no position: ``below the lowest string E2`` or ``above fret 19``."""
        if midi < min(self.open_midi):
            return f'below the lowest string {midi_to_note_name(min(self.open_midi))}'
        return f'above fret {self.num_frets}'

    def __repr__(self) -> str:
        return f'Fretboard({" ".join(self.tuning)}, {self.num_frets} frets)'
