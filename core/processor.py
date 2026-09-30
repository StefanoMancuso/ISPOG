# -*- coding: utf-8 -*-
"""
ISPOG - Processor
One analysis, from file to results: load, select parts, finger, color, label, credit,
serialize. Nothing is saved and no dialog is shown (plan, D6): the caller (desktop GUI or
web app) decides where the outputs go. Errors the user must read are IspogError.

    result = analyze(AnalysisConfig('score.mxl', tuning=('E4', 'B3', 'G3', 'D3', 'A2', 'E2')))
    Path('score_ispog.musicxml').write_bytes(result.outputs['full'])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union

from config.settings import MAX_FRETS, MAX_STRINGS, MIN_FRETS, MIN_STRINGS

from .errors import NoGuitarPartError
from .fretboard import Fretboard
from .model import AnalysisResult, PartInfo, PartReport
from .playability import analyze_notes
from .reader import list_parts, load_score, read_part
from .report import render_notes_tsv
from .writer import (add_ispog_credit, annotate, colorize, extract_part,
                     remove_annotations, serialize)

logger = logging.getLogger(__name__)

OUTPUT_MODES = ('full', 'split')


@dataclass(frozen=True)
class AnalysisConfig:
    """
    Parameters of one analysis.

    Attributes:
        filepath: .musicxml, .xml or .mxl score.
        tuning: open strings, string 1 (highest) first; its length is the number of strings.
        num_frets: frets on the neck.
        part_ids: parts to analyze; None = the guitar parts found in the score.
        output_mode: 'full' (one score) or 'split' (one score per analyzed part).
        labels: write a short label above difficult and unplayable points.
    """

    filepath: Union[str, Path]
    tuning: Sequence[str]
    num_frets: int = 19
    part_ids: Optional[Sequence[str]] = None
    output_mode: str = 'full'
    labels: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, 'filepath', Path(self.filepath))
        object.__setattr__(self, 'tuning', tuple(self.tuning))
        if self.part_ids is not None:
            object.__setattr__(self, 'part_ids', tuple(self.part_ids))
        if not MIN_STRINGS <= len(self.tuning) <= MAX_STRINGS:
            raise ValueError(f'invalid number of strings: {len(self.tuning)}')
        if not MIN_FRETS <= self.num_frets <= MAX_FRETS:
            raise ValueError(f'invalid number of frets: {self.num_frets}')
        if self.output_mode not in OUTPUT_MODES:
            raise ValueError(f'invalid output mode: {self.output_mode!r}')
        Fretboard(self.tuning, self.num_frets)          # validates the note names

    @property
    def num_strings(self) -> int:
        return len(self.tuning)


def analyze(config: AnalysisConfig) -> AnalysisResult:
    """
    Analyze a score and return the colored MusicXML and a report for every analyzed part.

    Raises:
        UnsupportedFileError: the file is not a readable MusicXML score.
        NoGuitarPartError: no part was selected and the score has no guitar part.
    """
    logger.info('Analysis of %s: tuning %s, %d frets, parts %s, output %s, labels %s',
                config.filepath.name, ' '.join(config.tuning), config.num_frets,
                config.part_ids or 'auto', config.output_mode, config.labels)
    tree = load_score(config.filepath)
    targets = select_targets(list_parts(tree), config.part_ids, config.filepath.name)
    fretboard = Fretboard(config.tuning, config.num_frets)

    reports = []
    for part in targets:
        notes = read_part(part)
        playability = analyze_notes(notes, fretboard)
        colorize(notes)
        if config.labels:
            annotate(part.element, playability.events)
        else:
            remove_annotations(part.element)
        report = PartReport(part_id=part.part_id, name=part.name, notes=notes,
                            events=playability.events, not_analyzed=playability.not_analyzed)
        logger.info('Part %s %r: %s', part.part_id, part.name, report.counts)
        reports.append(report)

    add_ispog_credit(tree)
    if config.output_mode == 'full':
        outputs = {'full': serialize(tree)}
    else:
        outputs = {part.part_id: serialize(extract_part(tree, part.part_id)) for part in targets}

    return AnalysisResult(source_name=config.filepath.name, tuning=config.tuning,
                          num_frets=config.num_frets, outputs=outputs, reports=reports,
                          output_mode=config.output_mode)


def select_targets(parts: list[PartInfo], part_ids: Optional[Sequence[str]],
                   source_name: str = '') -> list[PartInfo]:
    """
    Parts to analyze:
    - explicit ``part_ids``, in score order;
    - otherwise a single-part score is always analyzed (guitar or not, as in 0.9);
    - otherwise the parts detected as guitars.

    Raises:
        ValueError: an explicit part id is not in the score.
        NoGuitarPartError: nothing to analyze.
    """
    if part_ids is not None:
        known = {p.part_id for p in parts}
        unknown = [pid for pid in part_ids if pid not in known]
        if unknown:
            raise ValueError(f'unknown part id(s): {", ".join(unknown)}')
        targets = [p for p in parts if p.part_id in part_ids]
    elif len(parts) == 1:
        targets = parts
    else:
        targets = [p for p in parts if p.is_guitar]
    if not targets:
        raise NoGuitarPartError(
            f"No guitar part found in '{source_name}'. Select the parts to analyze.")
    return targets


def preselected_part_ids(parts: Sequence[PartInfo]) -> list[str]:
    """
    Parts ticked when a score is loaded, in the desktop and web apps: those ``analyze``
    would choose by itself (the guitars, or the only part of the score); none otherwise.
    """
    try:
        return [p.part_id for p in select_targets(list(parts), None)]
    except NoGuitarPartError:
        return []


def write_notes_logs(result: AnalysisResult, directory: Path) -> list[Path]:
    """Save the technical note list of every part as ``<stem>_<part>_notes.tsv``."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(result.source_name).stem
    paths = []
    for report in result.reports:
        path = directory / f'{stem}_{report.part_id}_notes.tsv'
        path.write_text(render_notes_tsv(report), encoding='utf-8')
        paths.append(path)
    return paths
