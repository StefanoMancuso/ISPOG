# -*- coding: utf-8 -*-
"""
ISPOG - MusicXML reader
Loads a score as an lxml tree, lists its parts and reads the notes of one part with
their absolute onsets.

    tree = load_score(path)              # .musicxml / .xml / .mxl, partwise or timewise
    parts = list_parts(tree)             # PartInfo for every part, guitars detected
    notes = read_part(parts[0])          # Note objects, in document order

The tree is the only source of truth (plan, D1): nothing is parsed from strings, and every
Note points at its ``<note>`` element. Parsing is safe and offline (plan, D8).
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from fractions import Fraction
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Optional, Union

from lxml import etree

from utils.io import resource_path

from .errors import UnsupportedFileError
from .model import Note, PartInfo

logger = logging.getLogger(__name__)

StrPath = Union[str, Path]
ScoreLike = Union[etree._ElementTree, etree._Element]

TIMEPART_XSL = 'resources/timepart.xsl'
MUSICXML_MEDIA_TYPE = 'application/vnd.recordare.musicxml+xml'
MXL_CONTAINER = 'META-INF/container.xml'

# General MIDI programs 25-32: nylon, steel, jazz, clean, muted, overdriven,
# distortion guitar, guitar harmonics.
GUITAR_MIDI_PROGRAMS = range(25, 33)
GUITAR_NAME = re.compile(r'guit|chitarr|gitarr|guitare', re.IGNORECASE)
BASS_NAME = re.compile(r'bass', re.IGNORECASE)


def _make_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        remove_blank_text=False,
        huge_tree=True,
    )


def _root(score: ScoreLike) -> etree._Element:
    return score.getroot() if isinstance(score, etree._ElementTree) else score


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_score(path: StrPath) -> etree._ElementTree:
    """
    Load a MusicXML score as a partwise tree.

    Accepts uncompressed (``.musicxml``, ``.xml``) and compressed (``.mxl``) files; the
    format is recognized from the content, not the extension. Timewise scores are
    converted to partwise.

    Raises:
        UnsupportedFileError: the file cannot be read or is not a MusicXML score.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as e:
        raise UnsupportedFileError(f"Cannot read '{path.name}': {e.strerror or e}.") from e

    if zipfile.is_zipfile(io.BytesIO(data)):
        data = _read_mxl(data, path.name)

    try:
        tree = etree.parse(io.BytesIO(data), _make_parser())
    except etree.XMLSyntaxError as e:
        raise UnsupportedFileError(
            f"'{path.name}' is not a valid MusicXML file: {e}."
        ) from e

    root_tag = tree.getroot().tag
    if root_tag == 'score-timewise':
        logger.info("Converting timewise score '%s' to partwise", path.name)
        tree = to_partwise(tree)
    elif root_tag != 'score-partwise':
        raise UnsupportedFileError(
            f"'{path.name}' is not a MusicXML score (root element <{root_tag}>)."
        )

    logger.info("Loaded '%s': %d part(s)", path.name, len(tree.getroot().findall('part')))
    return tree


def _read_mxl(data: bytes, name: str) -> bytes:
    """Return the main score of a compressed MusicXML (.mxl) archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.namelist()
            target = _mxl_rootfile(archive, members) or _mxl_fallback(members)
            if target is None:
                raise UnsupportedFileError(f"'{name}' contains no MusicXML score.")
            logger.debug("MXL '%s': reading %s", name, target)
            return archive.read(target)
    except (zipfile.BadZipFile, KeyError) as e:
        raise UnsupportedFileError(f"'{name}' is a damaged compressed MusicXML file.") from e


def _mxl_rootfile(archive: zipfile.ZipFile, members: list[str]) -> Optional[str]:
    """First rootfile in META-INF/container.xml that is a MusicXML score."""
    if MXL_CONTAINER not in members:
        logger.warning('MXL without %s', MXL_CONTAINER)
        return None
    try:
        container = etree.fromstring(archive.read(MXL_CONTAINER), _make_parser())
    except etree.XMLSyntaxError:
        logger.warning('MXL with unreadable %s', MXL_CONTAINER)
        return None
    for rootfile in container.iter('{*}rootfile'):
        full_path = rootfile.get('full-path')
        media_type = rootfile.get('media-type')
        if full_path and media_type in (None, MUSICXML_MEDIA_TYPE):
            if full_path in members:
                return full_path
            logger.warning('MXL rootfile %s not found in the archive', full_path)
    return None


def _mxl_fallback(members: list[str]) -> Optional[str]:
    """First .musicxml or .xml file outside META-INF/."""
    for member in members:
        parts = PurePosixPath(member).parts
        if parts and parts[0] == 'META-INF':
            continue
        if member.lower().endswith(('.musicxml', '.xml')):
            return member
    return None


@lru_cache(maxsize=1)
def _timepart_transform() -> etree.XSLT:
    stylesheet = etree.parse(str(resource_path(TIMEPART_XSL)), _make_parser())
    return etree.XSLT(stylesheet, access_control=etree.XSLTAccessControl.DENY_ALL)


def to_partwise(tree: etree._ElementTree) -> etree._ElementTree:
    """
    Convert a timewise score to partwise with the official MusicXML 4.0 stylesheet
    (``resources/timepart.xsl``). The result carries the partwise DOCTYPE.

    Raises:
        UnsupportedFileError: the conversion fails or produces no part.
    """
    try:
        result = _timepart_transform()(tree)
    except etree.XSLTApplyError as e:
        raise UnsupportedFileError('Timewise score could not be converted.') from e
    root = result.getroot()
    if root is None or root.tag != 'score-partwise' or root.find('part') is None:
        raise UnsupportedFileError('Timewise score could not be converted.')
    return root.getroottree()


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------

def list_parts(score: ScoreLike) -> list[PartInfo]:
    """
    All parts of the score, in ``<part-list>`` order, with guitars detected.
    ``<part-group>`` elements are ignored; a ``<score-part>`` without its ``<part>`` is
    skipped.
    """
    root = _root(score)
    elements = {p.get('id'): p for p in root.iterfind('part')}
    parts = []
    for score_part in root.iterfind('part-list/score-part'):
        part_id = score_part.get('id')
        element = elements.get(part_id)
        if element is None:
            logger.warning('score-part %s has no <part>: skipped', part_id)
            continue
        info = PartInfo(
            part_id=part_id,
            name=_part_name(score_part),
            is_guitar=_is_guitar(score_part),
            element=element,
        )
        logger.debug('Part %s %r: guitar=%s', info.part_id, info.name, info.is_guitar)
        parts.append(info)
    return parts


def _part_name(score_part: etree._Element) -> str:
    for path in ('part-name', 'part-name-display/display-text',
                 'part-abbreviation', 'score-instrument/instrument-name'):
        text = (score_part.findtext(path) or '').strip()
        if text:
            return text
    return score_part.get('id', '')


def _is_guitar(score_part: etree._Element) -> bool:
    """
    Guitar detection, in order of reliability: the MusicXML sound id, then the General
    MIDI program, then the part or instrument name. The first source present decides.
    """
    sounds = [s.text.strip() for s in score_part.iterfind('score-instrument/instrument-sound')
              if s.text and s.text.strip()]
    if sounds:
        return any(s.startswith('pluck.guitar') for s in sounds)

    programs = [p.text.strip() for p in score_part.iterfind('midi-instrument/midi-program')
                if p.text and p.text.strip().isdigit()]
    if programs:
        return any(int(p) in GUITAR_MIDI_PROGRAMS for p in programs)

    names = ' '.join(filter(None, (
        score_part.findtext('part-name'),
        score_part.findtext('part-abbreviation'),
        *(n.text for n in score_part.iterfind('score-instrument/instrument-name')),
    )))
    return bool(GUITAR_NAME.search(names)) and not BASS_NAME.search(names)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

class _PartState:
    """Attributes that persist across measures until the file changes them."""

    def __init__(self) -> None:
        self.divisions = Fraction(1)
        self.beats: Optional[Fraction] = None          # None: no or free time signature
        self.beat_type = 4
        self.transpose: dict[Optional[int], int] = {}  # staff (None = all) -> semitones
        self.tab_staves: set[int] = set()
        self.notation_staves: set[int] = set()

    def update(self, attributes: etree._Element) -> None:
        if (divisions := attributes.findtext('divisions')) is not None:
            value = Fraction(divisions.strip())
            if value <= 0:
                raise ValueError(f'invalid divisions {divisions!r}')
            self.divisions = value
        time = attributes.find('time')
        if time is not None:
            self._update_time(time)
        for transpose in attributes.iterfind('transpose'):
            number = transpose.get('number')
            self.transpose[int(number) if number else None] = (
                int(transpose.findtext('chromatic') or 0)
                + 12 * int(transpose.findtext('octave-change') or 0)
            )
        for clef in attributes.iterfind('clef'):
            staff = int(clef.get('number', 1))
            if (clef.findtext('sign') or '').strip().upper() == 'TAB':
                self.tab_staves.add(staff)
                self.notation_staves.discard(staff)
            else:
                self.notation_staves.add(staff)
                self.tab_staves.discard(staff)

    def _update_time(self, time: etree._Element) -> None:
        if time.find('senza-misura') is not None:
            self.beats = None
            return
        beats = time.findtext('beats')
        beat_type = time.findtext('beat-type')
        try:
            # composite signatures such as "3+2"
            self.beats = sum(Fraction(b) for b in beats.split('+'))
            self.beat_type = int(beat_type)
        except (AttributeError, ValueError, ZeroDivisionError):
            logger.warning('Unsupported time signature %r/%r', beats, beat_type)
            self.beats = None

    def duration(self, element: etree._Element) -> Fraction:
        """``<duration>`` of an element, in quarter notes (0 if absent)."""
        text = element.findtext('duration')
        return Fraction(text.strip()) / self.divisions if text else Fraction(0)

    def nominal_measure_length(self) -> Fraction:
        if self.beats is None:
            return Fraction(0)
        return self.beats * Fraction(4, self.beat_type)

    def transpose_for(self, staff: int) -> int:
        return self.transpose.get(staff, self.transpose.get(None, 0))

    def is_skipped_staff(self, staff: int) -> bool:
        """TAB staves are skipped when the part also has a notation staff."""
        return staff in self.tab_staves and bool(self.notation_staves)


def read_part(part: PartInfo) -> list[Note]:
    """
    Read every note of a part, in document order, with absolute onsets.

    The position cursor follows ``<duration>``, ``<backup>``, ``<forward>`` and ``<chord/>``;
    grace notes do not advance it. A measure lasts as far as its longest voice (pickup
    measures included), or its nominal length when it contains no timed element.
    Notes on a TAB staff that doubles a notation staff are not returned.

    Raises:
        UnsupportedFileError: the part contains values ISPOG cannot interpret.
    """
    state = _PartState()
    notes: list[Note] = []
    measure_start = Fraction(0)

    for measure in part.element.iterfind('measure'):
        number = measure.get('number', '')
        try:
            length = _read_measure(measure, number, measure_start, state, part, notes)
        except (ValueError, TypeError, ZeroDivisionError) as e:
            raise UnsupportedFileError(
                f"Part '{part.name}', measure {number}: unreadable content ({e})."
            ) from e
        measure_start += length

    logger.info("Part %s: %d notes read", part.part_id, len(notes))
    return notes


def _read_measure(
    measure: etree._Element,
    number: str,
    measure_start: Fraction,
    state: _PartState,
    part: PartInfo,
    notes: list[Note],
) -> Fraction:
    """Append the notes of one measure; return the measure length."""
    cursor = last_onset = measure_start
    length = Fraction(0)
    timed = False

    for el in measure:
        tag = el.tag
        if tag == 'attributes':
            state.update(el)
            continue
        if tag == 'backup':
            cursor -= state.duration(el)
            timed = True
        elif tag == 'forward':
            cursor += state.duration(el)
            timed = True
        elif tag == 'note':
            timed = True
            is_chord = el.find('chord') is not None
            duration = state.duration(el)
            onset = last_onset if is_chord else cursor
            staff = int(el.findtext('staff') or 1)
            if not state.is_skipped_staff(staff):
                notes.append(Note.from_element(
                    el,
                    part_id=part.part_id,
                    measure_number=number,
                    onset=onset,
                    duration=duration,
                    beat=1 + (onset - measure_start) * state.beat_type / 4,
                    transpose=state.transpose_for(staff),
                ))
            if not is_chord:
                last_onset = onset
                if el.find('grace') is None:
                    cursor += duration
        else:
            continue
        length = max(length, cursor - measure_start)

    if not timed:
        return state.nominal_measure_length()
    return length
