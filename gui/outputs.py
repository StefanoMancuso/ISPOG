# -*- coding: utf-8 -*-
"""
ISPOG - Output naming and part preselection
Decisions of the desktop app that need no window, kept apart from Tkinter so they can be
tested anywhere.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

from core import NoGuitarPartError, PartInfo, select_targets

OUTPUT_SUFFIX = '_ispog'
_UNSAFE = re.compile(r'[^\w\-]+')


def preselected_part_ids(parts: Sequence[PartInfo]) -> list[str]:
    """Parts ticked when a score is loaded: the guitars, or the only part of the score."""
    try:
        return [p.part_id for p in select_targets(list(parts), None)]
    except NoGuitarPartError:
        return []


def safe_name(text: str) -> str:
    """A file-name-safe version of a part name: ``Chitarra classica 1`` → ``Chitarra_classica_1``."""
    return _UNSAFE.sub('_', text).strip('_')


def full_output_name(source: Path) -> str:
    """Default name of the analyzed score: ``piece.mxl`` → ``piece_ispog.musicxml``."""
    return f'{source.stem}{OUTPUT_SUFFIX}.musicxml'


def report_path_for(score: Path) -> Path:
    """The report next to a saved score: ``piece_ispog.musicxml`` → ``piece_ispog_report.txt``."""
    return score.with_name(f'{score.stem}_report.txt')


def split_output_names(source: Path, parts: Iterable[PartInfo]) -> dict[str, str]:
    """
    One file per part: ``<score>_<part name>_ispog.musicxml``. Parts with the same name
    (e.g. two "Guitar") are told apart by their id.
    """
    parts = list(parts)
    names = [safe_name(p.name) or p.part_id for p in parts]
    result = {}
    for part, name in zip(parts, names):
        if names.count(name) > 1:
            name = f'{name}_{part.part_id}'
        result[part.part_id] = f'{source.stem}_{name}{OUTPUT_SUFFIX}.musicxml'
    return result


def split_report_name(source: Path) -> str:
    return f'{source.stem}{OUTPUT_SUFFIX}_report.txt'


def shorten(text: str, max_chars: int) -> str:
    """``text`` cut in the middle with an ellipsis if longer than ``max_chars``."""
    if len(text) <= max_chars:
        return text
    head = (max_chars - 1) // 2
    tail = max_chars - 1 - head
    return f'{text[:head]}…{text[len(text) - tail:]}'
