# -*- coding: utf-8 -*-
"""
ISPOG - Fretting hand
Assigns the fingers of the fretting hand (1 index … 4 pinky) to a set of string/fret
positions and grades the result.

Rules (CHANGELOG 0.10.0b2):

- open strings take no finger; every fretted position takes one finger;
- a finger on a higher fret has a higher number (finger order);
- on the same fret the lower finger goes on the lower-pitched string; the opposite
  (crossed fingers) is difficult on adjacent strings and impossible otherwise;
- one finger on several strings (barré) only with the index (lowest fret, any strings, no
  open string inside the barré) or with the pinky (highest fret, contiguous strings from
  the first, at most ``PINKY_BARRE_MAX_STRINGS``; always difficult);
- the distance in frets between two fingers is graded by the stretch table
  (``core.stretch``), with or without a barré;
- positions may be *pinned* to a finger: notes still held from an earlier onset keep it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from itertools import combinations, permutations
from typing import Iterator, Optional, Sequence

from config.settings import MAX_FINGERS, PINKY_BARRE_MAX_STRINGS

from .stretch import StretchLimit, StretchTable, default_table

INDEX, PINKY = 1, MAX_FINGERS
OPEN = 0


class Playability(Enum):
    """Playability of a fingering, as a color."""
    PLAYABLE = "green"
    DIFFICULT = "orange"
    UNPLAYABLE = "red"


RANK = {Playability.PLAYABLE: 0, Playability.DIFFICULT: 1, Playability.UNPLAYABLE: 2}


class Issue:
    """Machine-readable cause of a result, for short labels (``reason`` is the long text)."""
    NONE = ""
    FINGERS = "fingers"                  # more than 4 fingers
    SPAN = "span"                        # two fingers too far apart
    OUT_OF_RANGE = "out_of_range"        # a note has no position on the neck
    STRINGS = "strings"                  # more notes than strings
    CONFLICT = "conflict"                # no string assignment (held notes or shared strings)
    FINGER_CONFLICT = "finger_conflict"  # held notes keep the fingers the new notes need
    PINKY_BARRE = "pinky_barre"
    STRETCH = "stretch"                  # difficult distance between two fingers
    CROSSING = "crossing"                # crossed fingers on the same fret
    NO_SHAPE = "no_shape"                # few enough fingers, but no hand position


@dataclass(frozen=True)
class Problem:
    """A difficulty of a playable shape, or the violation that makes a shape impossible."""

    playability: Playability
    issue: str
    text: str
    indices: frozenset[int]              # positions involved
    excess: int = 0                      # frets beyond the playable limit (violations)
    distance: int = 0                    # frets between the two fingers (stretch, span)


@dataclass(frozen=True)
class HandShape:
    """One assignment of fingers to positions, with its grade."""

    fingers: tuple[int, ...]             # per position, in input order; 0 = open string
    playability: Playability
    problems: tuple[Problem, ...]        # difficulties, or violations if UNPLAYABLE
    span: int                            # highest - lowest fretted fret
    fingers_used: int
    barre_finger: Optional[int] = None
    barre_fret: Optional[int] = None
    cost: float = 0.0                    # ergonomic cost, to rank shapes of the same grade
    excess: int = 0                      # frets beyond the playable limits (UNPLAYABLE)

    @property
    def issue(self) -> str:
        return self.problems[0].issue if self.problems else Issue.NONE


@dataclass(frozen=True)
class ShapeSearch:
    """All finger assignments of a set of positions."""

    valid: tuple[HandShape, ...]         # PLAYABLE or DIFFICULT, best first
    invalid: tuple[HandShape, ...]       # UNPLAYABLE, closest first
    min_fingers: int                     # fingers needed at least (with barrés)


def hand_shapes(positions: Sequence[tuple[int, int]],
                pinned: Optional[Sequence[Optional[int]]] = None,
                table: Optional[StretchTable] = None) -> ShapeSearch:
    """
    Every finger assignment of ``positions`` ((string, fret), fret 0 = open string).

    Args:
        pinned: per position, the finger it must keep (held notes), or None.
        table: stretch limits; the table shipped with ISPOG by default.
    """
    pins = tuple(pinned) if pinned is not None else (None,) * len(positions)
    if len(pins) != len(positions):
        raise ValueError('pinned must have one entry per position')
    return _search(tuple(positions), pins, table or default_table())


@lru_cache(maxsize=1 << 16)
def _search(positions: tuple[tuple[int, int], ...], pins: tuple[Optional[int], ...],
            table: StretchTable) -> ShapeSearch:
    groups = _fret_groups(positions)
    if any(fret == 0 and pin not in (None, OPEN) for (_, fret), pin in zip(positions, pins)):
        return ShapeSearch((), (), _min_fingers(positions, groups))

    valid, invalid = [], []
    for fingers, barre in _assignments(positions, pins, groups):
        shape = _grade(positions, fingers, barre, groups, table)
        if shape is None:
            continue
        (invalid if shape.playability is Playability.UNPLAYABLE else valid).append(shape)
    valid.sort(key=lambda s: (RANK[s.playability], s.cost))
    invalid.sort(key=lambda s: (s.excess, s.cost))
    return ShapeSearch(tuple(valid), tuple(invalid), _min_fingers(positions, groups))


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

def _fret_groups(positions) -> list[tuple[int, list[int]]]:
    """Fretted positions grouped by fret, lowest fret first; in a group, low strings first."""
    by_fret: dict[int, list[int]] = {}
    for i, (_, fret) in enumerate(positions):
        if fret > 0:
            by_fret.setdefault(fret, []).append(i)
    return [(fret, sorted(by_fret[fret], key=lambda i: -positions[i][0]))
            for fret in sorted(by_fret)]


def _assignments(positions, pins, groups) -> Iterator[tuple[list[int], Optional[int]]]:
    """(finger per position, barré finger or None) for every structurally valid choice."""
    fingers = [OPEN] * len(positions)
    last = len(groups) - 1

    def fits(indices, chosen) -> bool:
        return all(pins[i] is None or pins[i] == f for i, f in zip(indices, chosen))

    def recurse(g: int, lowest: int, barre: Optional[int]):
        if g > last:
            yield list(fingers), barre
            return
        _, indices = groups[g]
        size = len(indices)
        # one finger per position, in any order (crossings graded later)
        for chosen in combinations(range(lowest, MAX_FINGERS + 1), size):
            for order in permutations(chosen):
                if not fits(indices, order):
                    continue
                for i, f in zip(indices, order):
                    fingers[i] = f
                yield from recurse(g + 1, max(order) + 1, barre)
        if size < 2:
            return
        strings = sorted(positions[i][0] for i in indices)
        # index barré on the lowest fret
        if g == 0 and lowest == INDEX and fits(indices, [INDEX] * size):
            for i in indices:
                fingers[i] = INDEX
            yield from recurse(g + 1, INDEX + 1, INDEX)
        # pinky barré on the highest fret: strings 1, 2, … contiguous
        if (g == last and lowest <= PINKY and size <= PINKY_BARRE_MAX_STRINGS
                and strings == list(range(1, size + 1)) and fits(indices, [PINKY] * size)):
            for i in indices:
                fingers[i] = PINKY
            yield list(fingers), PINKY

    yield from recurse(0, INDEX, None)


def _min_fingers(positions, groups) -> int:
    """Fingers needed at least: an index barré on the lowest fret, a pinky barré on the top."""
    total = 0
    for g, (_, indices) in enumerate(groups):
        strings = sorted(positions[i][0] for i in indices)
        if len(indices) > 1 and (
                g == 0 or (g == len(groups) - 1 and len(indices) <= PINKY_BARRE_MAX_STRINGS
                           and strings == list(range(1, len(indices) + 1)))):
            total += 1
        else:
            total += len(indices)
    return total


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def _grade(positions, fingers, barre, groups, table) -> Optional[HandShape]:
    """Grade one assignment; None if it is not a hand position at all."""
    fretted = [i for i, f in enumerate(fingers) if f != OPEN]
    if not fretted:
        return HandShape(fingers=tuple(fingers), playability=Playability.PLAYABLE, problems=(),
                         span=0, fingers_used=0)

    strings_of: dict[int, list[int]] = {}
    indices_of: dict[int, list[int]] = {}
    fret_of: dict[int, int] = {}
    for i in fretted:
        f = fingers[i]
        strings_of.setdefault(f, []).append(positions[i][0])
        indices_of.setdefault(f, []).append(i)
        fret_of[f] = positions[i][1]

    barre_fret = fret_of[barre] if barre else None
    if barre == INDEX:
        low, high = min(strings_of[INDEX]), max(strings_of[INDEX])
        if any(fret == 0 and low <= string <= high for string, fret in positions):
            return None                              # open string under the barré

    difficult: list[Problem] = []
    violations: list[Problem] = []
    excess = 0
    position = groups[0][0]

    if barre == PINKY:
        strings = sorted(strings_of[PINKY])
        difficult.append(Problem(Playability.DIFFICULT, Issue.PINKY_BARRE,
                                 f'pinky barré on fret {barre_fret}, '
                                 f'strings {strings[0]}–{strings[-1]}',
                                 frozenset(indices_of[PINKY])))

    used = sorted(fret_of)
    for a, b in combinations(used, 2):
        involved = frozenset(indices_of[a] + indices_of[b])
        distance = fret_of[b] - fret_of[a]
        if distance == 0:
            crossing = _crossing(positions, indices_of[a], indices_of[b])
            if crossing is None:
                continue
            if not crossing:
                return None                          # crossed on strings that are not adjacent
            difficult.append(Problem(Playability.DIFFICULT, Issue.CROSSING,
                                     f'fingers {a} and {b} crossed on fret {fret_of[a]}',
                                     involved))
            continue
        limit = _best_limit(table, a, strings_of[a], b, strings_of[b], position)
        if distance <= limit.green:
            continue
        if distance <= limit.orange:
            difficult.append(Problem(Playability.DIFFICULT, Issue.STRETCH,
                                     f'stretch: fingers {a}–{b} over {distance} frets', involved,
                                     distance=distance))
        else:
            excess += distance - limit.orange
            violations.append(Problem(Playability.UNPLAYABLE, Issue.SPAN,
                                      f'fingers {a}–{b} over {distance} frets '
                                      f'(max {limit.orange})', involved,
                                      excess=distance - limit.orange, distance=distance))

    frets = [positions[i][1] for i in fretted]
    span = max(frets) - min(frets)
    if violations:
        # the worst violation first: it is the one the reason names
        playability = Playability.UNPLAYABLE
        problems = sorted(violations, key=lambda p: (-p.excess, -p.distance))
    elif difficult:
        playability, problems = Playability.DIFFICULT, _by_priority(difficult)
    else:
        playability, problems = Playability.PLAYABLE, []
    return HandShape(fingers=tuple(fingers), playability=playability, problems=tuple(problems),
                     span=span, fingers_used=len(used), barre_finger=barre,
                     barre_fret=barre_fret, cost=_cost(used, fret_of, span, barre, difficult),
                     excess=excess)


def _crossing(positions, indices_a, indices_b) -> Optional[bool]:
    """
    Two fingers on the same fret (a lower than b). None: natural order (a on the lower-pitched
    string); True: crossed on adjacent strings; False: crossed otherwise.
    """
    string_a = positions[indices_a[0]][0]
    string_b = positions[indices_b[0]][0]
    if string_a > string_b:
        return None
    return string_b - string_a == 1


def _best_limit(table: StretchTable, a: int, strings_a: list[int], b: int,
                strings_b: list[int], position: int) -> StretchLimit:
    """The most favorable limit over the strings of the two fingers (barrés cover several)."""
    return max((table.limit(a, sa, b, sb, position) for sa in strings_a for sb in strings_b),
               key=lambda limit: (limit.orange, limit.green))


_PRIORITY = {Issue.PINKY_BARRE: 0, Issue.STRETCH: 1, Issue.CROSSING: 2}


def _by_priority(problems: list[Problem]) -> list[Problem]:
    return sorted(problems, key=lambda p: _PRIORITY.get(p.issue, 9))


def _cost(used: list[int], fret_of: dict[int, int], span: int, barre: Optional[int],
          difficult: list[Problem]) -> float:
    """
    Lower is more natural: small span, few fingers, no barré (it costs more than three
    fingers on one fret, less than four), one finger per fret (fingers 1 and 3 on adjacent frets cost more
    than 1 and 2), starting with the index.
    """
    cost = span + 0.5 * len(used) + 2.0 * len(difficult)
    if barre == INDEX:
        cost += 1.5
    per_fret: dict[int, int] = {}
    for f in used:
        per_fret[fret_of[f]] = per_fret.get(fret_of[f], 0) + 1
    cost += 0.4 * sum(n - 2 for n in per_fret.values() if n > 2)   # 4 fingers on a fret
    for a, b in zip(used, used[1:]):
        frets = fret_of[b] - fret_of[a]
        if frets:
            cost += 0.3 * abs((b - a) - frets)
    cost += 0.1 * (used[0] - INDEX)
    return cost
