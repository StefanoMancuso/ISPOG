# -*- coding: utf-8 -*-
"""
ISPOG - Unisons across voices
Decides when notes of the same pitch in different voices are one note written twice (a
graphic doubling) and when they are distinct notes, to be played on different strings.

Rules (CHANGELOG 0.10.0b3):

- notes of the same pitch attacked together in different voices are one note, unless the
  score marks them as distinct (``are_distinct``). The longest is fingered; the others
  take its result;
- a note attacked while a note of the same pitch from another voice is still sounding (a
  re-attack, or a new attack against a tied note) cannot be played as written on one
  string. Unless the score marks the two as distinct, the string is re-plucked: the new
  note takes over the sound, which lasts as long as the longer of the two, and the
  playability engine marks it as *not as written*;
- notes of the same voice are always distinct: a unison chord written in one voice is
  deliberate.

Hidden notes (``print-object="no"``) never reach this module: the playability engine leaves
them out. Grace notes are passed through untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import groupby
from typing import Sequence

from .model import Note

logger = logging.getLogger(__name__)


@dataclass
class UnisonResolution:
    """
    Outcome of ``resolve_unisons``.

    Attributes:
        heads: the notes to finger, in onset order (graphic doublings removed).
        merged: graphic doubling -> the note fingered in its place.
        ends: notes whose sounding end is not ``onset + sounding_duration``: a re-attack
            sounding as long as the note it releases, or the note released.
        reattacks: note attacked over a sounding unison -> the note it releases.
    """

    heads: list[Note] = field(default_factory=list)
    merged: dict[Note, Note] = field(default_factory=dict)
    ends: dict[Note, Fraction] = field(default_factory=dict)
    reattacks: dict[Note, Note] = field(default_factory=dict)

    def end(self, note: Note) -> Fraction:
        """When ``note`` stops sounding."""
        return self.ends.get(note, note.onset + note.sounding_duration)


def are_distinct(a: Note, b: Note) -> bool:
    """
    Whether two notes of the same pitch are meant as two notes on different strings:

    - same staff and voice;
    - string numbers on both: they differ (this decides, whatever the fingering);
    - different spelling (E4 / Fb4);
    - fingerings on both, with different numbers.
    """
    if (a.staff, a.voice) == (b.staff, b.voice):
        return True
    if a.string_mark is not None and b.string_mark is not None:
        return a.string_mark != b.string_mark
    if (a.step, a.alter) != (b.step, b.alter):
        return True
    return (a.fingering_mark is not None and b.fingering_mark is not None
            and a.fingering_mark != b.fingering_mark)


def resolve_unisons(heads: Sequence[Note]) -> UnisonResolution:
    """
    Merge graphic doublings and find re-attacks of sounding unisons.

    Args:
        heads: analyzable notes that start a sound (tied continuations removed), in onset
            order, with ``sounding_duration`` covering their ties.
    """
    result = UnisonResolution()
    sounding: dict[int, list[Note]] = {}          # midi -> fingered notes, pruned lazily

    for onset, group in groupby(heads, key=lambda n: n.onset):
        group = list(group)
        kept = _merge_doublings([n for n in group if not n.is_grace], result)
        for note in kept:
            _check_reattack(note, onset, sounding, result)
        kept_ids = set(map(id, kept))
        result.heads.extend(n for n in group if n.is_grace or id(n) in kept_ids)

    if result.merged or result.reattacks:
        logger.info('Unisons: %d graphic doublings merged, %d re-attacks of a sounding note',
                    len(result.merged), len(result.reattacks))
    return result


def _merge_doublings(notes: list[Note], result: UnisonResolution) -> list[Note]:
    """The notes attacked at one onset with the doublings merged, in their order."""
    kept: list[Note] = []
    for cluster in _clusters(notes):
        primary = max(cluster, key=lambda n: n.sounding_duration)     # first among equals
        for note in cluster:
            if note is not primary:
                result.merged[note] = primary
                logger.debug('Unison merged: %s voice %s into voice %s, measure %s, beat %s',
                             note.pitch_name, note.voice, primary.voice,
                             note.measure_number, note.beat_label)
        kept.append(primary)
    order = {id(n): i for i, n in enumerate(notes)}
    return sorted(kept, key=lambda n: order[id(n)])


def _clusters(notes: list[Note]) -> list[list[Note]]:
    """Notes of the same pitch, grouped so that no two notes in a group are distinct."""
    clusters: list[list[Note]] = []
    for note in notes:
        for cluster in clusters:
            if cluster[0].midi == note.midi and not any(are_distinct(note, m) for m in cluster):
                cluster.append(note)
                break
        else:
            clusters.append([note])
    return clusters


def _check_reattack(note: Note, onset: Fraction, sounding: dict[int, list[Note]],
                    result: UnisonResolution) -> None:
    """
    Release the notes of the same pitch still sounding that ``note`` re-attacks; ``note``
    keeps sounding until the latest of their written ends (durations are honored).
    """
    active = [h for h in sounding.get(note.midi, []) if result.end(h) > onset]
    released = [h for h in active if not are_distinct(h, note)]
    if released:
        result.reattacks[note] = released[0]
        end = max(result.end(h) for h in released + [note])
        if end != note.onset + note.sounding_duration:
            result.ends[note] = end
        for held in released:
            result.ends[held] = onset
        logger.debug('Unison re-attacked: %s voice %s over voice %s, measure %s, beat %s',
                     note.pitch_name, note.voice, released[0].voice,
                     note.measure_number, note.beat_label)
    sounding[note.midi] = [h for h in active if h not in released] + [note]
