# -*- coding: utf-8 -*-
"""
ISPOG - Finger stretch table
How far apart, in frets, two fingers of the fretting hand can be.

The table is read from ``config/finger_stretch.csv`` so that it can be edited in a
spreadsheet without touching the code:

- one row per pair of fingers (``1-2`` … ``3-4``), and a second row with the suffix ``>7``
  used when the hand is in high position (lowest fretted note at fret
  ``HIGH_POSITION_FRET`` or above, where the frets are narrower);
- one column per pair of strings ``a-b``: ``a`` is the string of the lower finger, ``b``
  the string of the higher finger (strings numbered from 1, the highest);
- each cell is ``G/O``: a distance up to ``G`` frets is comfortable, up to ``O`` difficult,
  beyond ``O`` impossible. ``G`` may be 0: then even one fret is difficult.

Distance 0 (two fingers on the same fret) is not in the table: see ``core.fingering``.
Strings beyond the sixth (7- and 8-string guitars) use the limits of the sixth.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from config.settings import HIGH_POSITION_FRET, STRETCH_TABLE_FILE
from utils.io import resource_path

logger = logging.getLogger(__name__)

FINGERS = (1, 2, 3, 4)
TABLE_STRINGS = 6
HIGH_SUFFIX = '>7'
DEFAULT_PATH = resource_path(f'config/{STRETCH_TABLE_FILE}')


class StretchTableError(ValueError):
    """The stretch table file is missing a row or column, or has an invalid cell."""


@dataclass(frozen=True)
class StretchLimit:
    """Largest comfortable (``green``) and largest playable (``orange``) distance in frets."""

    green: int
    orange: int


class StretchTable:
    """Stretch limits per (lower finger, higher finger, their strings, hand position)."""

    def __init__(self, limits: dict[tuple[int, int, bool, int, int], StretchLimit]):
        self._limits = dict(limits)

    @classmethod
    def load(cls, path: Path | str = DEFAULT_PATH) -> StretchTable:
        """
        Read and validate a table file.

        Raises:
            StretchTableError: a row, a column or a cell is missing or invalid.
        """
        path = Path(path)
        try:
            with open(path, encoding='utf-8-sig', newline='') as f:
                rows = [row for row in csv.reader(f) if any(cell.strip() for cell in row)]
        except OSError as exc:
            raise StretchTableError(f'cannot read {path}: {exc}') from exc
        if not rows:
            raise StretchTableError(f'{path.name}: empty file')

        header = [_compact(cell) for cell in rows[0][1:]]
        columns = {}
        for index, name in enumerate(header, start=1):
            columns[_string_pair(name, path.name)] = index
        expected_columns = {(a, b) for a in range(1, TABLE_STRINGS + 1)
                            for b in range(1, TABLE_STRINGS + 1)}
        missing = sorted(expected_columns - set(columns))
        if missing:
            raise StretchTableError(
                f'{path.name}: missing columns ' + ', '.join(f'{a}-{b}' for a, b in missing))

        limits = {}
        seen_rows = set()
        for line, row in enumerate(rows[1:], start=2):
            key = _row_key(row[0], path.name, line)
            if key in seen_rows:
                raise StretchTableError(f'{path.name}, line {line}: row {row[0]!r} repeated')
            seen_rows.add(key)
            low, high, is_high = key
            for (a, b), index in columns.items():
                cell = row[index] if index < len(row) else ''
                limits[(low, high, is_high, a, b)] = _cell(cell, path.name, line, f'{a}-{b}')

        expected_rows = {(lo, hi, h) for lo, hi in combinations(FINGERS, 2) for h in (False, True)}
        missing_rows = expected_rows - seen_rows
        if missing_rows:
            names = sorted(f'{lo}-{hi}{" " + HIGH_SUFFIX if h else ""}'
                           for lo, hi, h in missing_rows)
            raise StretchTableError(f'{path.name}: missing rows ' + ', '.join(names))
        logger.debug('Stretch table loaded from %s', path)
        return cls(limits)

    def limit(self, finger_a: int, string_a: int, finger_b: int, string_b: int,
              position: int) -> StretchLimit:
        """
        Limits for two fingers (any order) on their strings, with the hand at ``position``
        (its lowest fretted fret).
        """
        if finger_a > finger_b:
            finger_a, string_a, finger_b, string_b = finger_b, string_b, finger_a, string_a
        return self._limits[(finger_a, finger_b, position >= HIGH_POSITION_FRET,
                             min(string_a, TABLE_STRINGS), min(string_b, TABLE_STRINGS))]


@lru_cache(maxsize=1)
def default_table() -> StretchTable:
    """The table shipped with ISPOG, read once."""
    return StretchTable.load(DEFAULT_PATH)


def _compact(text: str) -> str:
    return ''.join(text.split())


def _string_pair(name: str, file: str) -> tuple[int, int]:
    parts = name.split('-')
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise StretchTableError(f'{file}: invalid column {name!r} (expected e.g. 1-2)')
    a, b = int(parts[0]), int(parts[1])
    if not (1 <= a <= TABLE_STRINGS and 1 <= b <= TABLE_STRINGS):
        raise StretchTableError(f'{file}: column {name!r} outside strings 1-{TABLE_STRINGS}')
    return a, b


def _row_key(name: str, file: str, line: int) -> tuple[int, int, bool]:
    text = _compact(name)
    is_high = text.endswith(HIGH_SUFFIX)
    if is_high:
        text = text[:-len(HIGH_SUFFIX)]
    parts = text.split('-')
    if (len(parts) != 2 or not all(p.isdigit() for p in parts)
            or (int(parts[0]), int(parts[1])) not in combinations(FINGERS, 2)):
        raise StretchTableError(
            f'{file}, line {line}: invalid row {name!r} (expected e.g. 1-2 or 1-2 {HIGH_SUFFIX})')
    return int(parts[0]), int(parts[1]), is_high


def _cell(text: str, file: str, line: int, column: str) -> StretchLimit:
    where = f'{file}, line {line}, column {column}'
    parts = _compact(text).split('/')
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise StretchTableError(f'{where}: invalid cell {text!r} (expected G/O, e.g. 1/2)')
    green, orange = int(parts[0]), int(parts[1])
    if orange < green:
        raise StretchTableError(f'{where}: {text!r} has O smaller than G')
    return StretchLimit(green, orange)
