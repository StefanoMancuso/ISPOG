# -*- coding: utf-8 -*-
"""
ISPOG - Output names
Names of the files an analysis produces, shared by the desktop app and the web app so that
both deliver the same files:

    piece.mxl, full   →  piece_ispog.musicxml               + piece_ispog_report.txt
    piece.mxl, split  →  piece_<part name>_ispog.musicxml … + piece_ispog_report.txt
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Protocol

from .model import AnalysisResult

OUTPUT_SUFFIX = '_ispog'
_UNSAFE = re.compile(r'[^\w\-]+')


class _NamedPart(Protocol):
    """PartInfo or PartReport: anything with a part id and a name."""

    part_id: str
    name: str


def safe_name(text: str) -> str:
    """A file-name-safe version of a part name: ``Chitarra classica 1`` → ``Chitarra_classica_1``."""
    return _UNSAFE.sub('_', text).strip('_')


def full_output_name(source: Path) -> str:
    """Default name of the analyzed score: ``piece.mxl`` → ``piece_ispog.musicxml``."""
    return f'{source.stem}{OUTPUT_SUFFIX}.musicxml'


def report_path_for(score: Path) -> Path:
    """The report next to a saved score: ``piece_ispog.musicxml`` → ``piece_ispog_report.txt``."""
    return score.with_name(f'{score.stem}_report.txt')


def split_output_names(source: Path, parts: Iterable[_NamedPart]) -> dict[str, str]:
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


def output_names(result: AnalysisResult) -> dict[str, str]:
    """Default file name of every output of ``result`` (same keys as ``result.outputs``)."""
    source = Path(result.source_name)
    if result.output_mode == 'full':
        return {'full': full_output_name(source)}
    names = split_output_names(source, result.reports)
    return {key: names[key] for key in result.outputs}


def report_name(result: AnalysisResult) -> str:
    """Default name of the report of ``result``."""
    return split_report_name(Path(result.source_name))
