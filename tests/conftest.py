"""
Shared fixtures and a minimal MusicXML builder.

Real scores live in tests/fixtures/. For edge cases that no real file covers (a
<forward> at the start of a measure, a change of divisions, a TAB staff...) tests build
a synthetic score with ``make_score`` and the helpers below, so each case is small,
explicit and readable in the test itself.

Example::

    xml = make_score(measures=[
        attributes(divisions=2) + note("E", 2, 4) + backup(4) + note("B", 3, 4, voice=2),
    ])
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence
from xml.sax.saxutils import escape, quoteattr

import pytest
from lxml import etree

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
BASELINE_DIR = TESTS_DIR / "baseline"
SCHEMA_DIR = TESTS_DIR / "schema"

# Real scores from many editors (plan, F8). Not versioned: they may be copyrighted.
# ISPOG_CORPUS points the corpus tests and tools at another folder.
CORPUS_DIR = Path(os.environ.get("ISPOG_CORPUS") or TESTS_DIR / "corpus")
CORPUS_OUTPUT = "_output"                      # written by tests/tools/corpus_run.py
SCORE_SUFFIXES = frozenset({".musicxml", ".xml", ".mxl"})


def corpus_files() -> list[Path]:
    """Scores in the corpus folder and its subfolders, except the tool output."""
    if not CORPUS_DIR.is_dir():
        return []
    return sorted(
        path for path in CORPUS_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SCORE_SUFFIXES
        and CORPUS_OUTPUT not in path.relative_to(CORPUS_DIR).parts
    )

DOCTYPE_PARTWISE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)
DOCTYPE_TIMEWISE = (
    '<!DOCTYPE score-timewise PUBLIC "-//Recordare//DTD MusicXML 4.0 Timewise//EN" '
    '"http://www.musicxml.org/dtds/timewise.dtd">'
)


# ---------------------------------------------------------------------------
# Real scores
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test01_path() -> Path:
    """Single-part guitar score (MuseScore), reference for the 0.9.x baseline."""
    return FIXTURES_DIR / "Test01.musicxml"


@pytest.fixture(scope="session")
def test_poli_path() -> Path:
    """Four-part score: P1, P2 not guitar; P3, P4 classical guitars."""
    return FIXTURES_DIR / "test_poli.musicxml"


@pytest.fixture
def test_ispog_path() -> Path:
    """Three measures (MuseScore, .mxl) checked by hand on the guitar: fingering cases."""
    return FIXTURES_DIR / "test_ISPOG.mxl"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class _LocalSchemaResolver(etree.Resolver):
    """Serve the schema imports (xml.xsd, xlink.xsd) from tests/schema, never the network."""

    def resolve(self, url, pubid, context):
        local = SCHEMA_DIR / url.rsplit("/", 1)[-1]
        return self.resolve_filename(str(local), context) if local.is_file() else None


@pytest.fixture(scope="session")
def musicxml_schema() -> etree.XMLSchema:
    """MusicXML 4.0 XSD (tests/schema, see THIRD_PARTY_NOTICES.md)."""
    parser = etree.XMLParser(no_network=True, load_dtd=False, resolve_entities=False)
    parser.resolvers.add(_LocalSchemaResolver())
    return etree.XMLSchema(etree.parse(str(SCHEMA_DIR / "musicxml.xsd"), parser))


@pytest.fixture(scope="session")
def assert_valid(musicxml_schema) -> Callable[[bytes], None]:
    """Assert that serialized MusicXML validates against the 4.0 schema."""

    def _check(data: bytes) -> None:
        parser = etree.XMLParser(no_network=True, load_dtd=False, resolve_entities=False)
        tree = etree.parse(io.BytesIO(data), parser)
        if not musicxml_schema.validate(tree):
            errors = "\n".join(f"  line {e.line}: {e.message}"
                               for e in list(musicxml_schema.error_log)[:10])
            pytest.fail(f"MusicXML 4.0 schema violations:\n{errors}")

    return _check


# ---------------------------------------------------------------------------
# Synthetic scores
# ---------------------------------------------------------------------------

@dataclass
class PartSpec:
    """One part of a synthetic score. ``measures`` holds the inner XML of each measure."""

    measures: Sequence[str]
    part_id: str = "P1"
    name: str = "Classical Guitar"
    instrument_sound: Optional[str] = "pluck.guitar.nylon-string"
    midi_program: Optional[int] = 25
    extra_attrs: dict = field(default_factory=dict)


def attributes(
    divisions: Optional[int | str] = 1,
    *,
    beats: Optional[int] = 4,
    beat_type: int = 4,
    clefs: Sequence[tuple[str, int]] = (("G", 2),),
    staves: Optional[int] = None,
    transpose: Optional[tuple[int, int]] = None,
) -> str:
    """
    ``<attributes>`` element. ``clefs`` is a list of (sign, line); with more than one
    clef each gets ``number=1..n``. ``transpose`` is (chromatic, octave-change).
    Pass ``divisions=None`` or ``beats=None`` to omit that child.
    """
    parts = []
    if divisions is not None:
        parts.append(f"<divisions>{divisions}</divisions>")
    if beats is not None:
        parts.append(f"<time><beats>{beats}</beats><beat-type>{beat_type}</beat-type></time>")
    if staves is not None:
        parts.append(f"<staves>{staves}</staves>")
    numbered = len(clefs) > 1
    for i, (sign, line) in enumerate(clefs, start=1):
        number = f' number="{i}"' if numbered else ""
        line_xml = f"<line>{line}</line>" if sign != "TAB" else "<line>5</line>"
        parts.append(f"<clef{number}><sign>{sign}</sign>{line_xml}</clef>")
    if transpose is not None:
        chromatic, octave_change = transpose
        parts.append(
            f"<transpose><diatonic>0</diatonic><chromatic>{chromatic}</chromatic>"
            f"<octave-change>{octave_change}</octave-change></transpose>"
        )
    return f"<attributes>{''.join(parts)}</attributes>"


def note(
    step: Optional[str],
    octave: Optional[int],
    duration: int | str | None,
    *,
    alter: Optional[float] = None,
    voice: int | str = 1,
    staff: Optional[int] = None,
    chord: bool = False,
    grace: bool = False,
    cue: bool = False,
    tie: Sequence[str] = (),
    harmonic: bool = False,
) -> str:
    """
    ``<note>`` element. ``step=None`` makes a rest. ``tie`` is a subset of
    ("stop", "start"), written both as <tie> and <notations><tied>.
    Grace notes have no <duration>: pass ``duration=None``.
    """
    children = []
    if grace:
        children.append('<grace slash="yes"/>')
    if cue:
        children.append("<cue/>")
    if chord:
        children.append("<chord/>")
    if step is None:
        children.append("<rest/>")
    else:
        alter_xml = f"<alter>{alter:g}</alter>" if alter is not None else ""
        children.append(f"<pitch><step>{step}</step>{alter_xml}<octave>{octave}</octave></pitch>")
    if duration is not None:
        children.append(f"<duration>{duration}</duration>")
    for kind in tie:
        children.append(f'<tie type="{kind}"/>')
    children.append(f"<voice>{voice}</voice>")
    if staff is not None:
        children.append(f"<staff>{staff}</staff>")
    notations = [f'<tied type="{kind}"/>' for kind in tie]
    if harmonic:
        notations.append("<technical><harmonic><natural/></harmonic></technical>")
    if notations:
        children.append(f"<notations>{''.join(notations)}</notations>")
    return f"<note>{''.join(children)}</note>"


def backup(duration: int | str) -> str:
    return f"<backup><duration>{duration}</duration></backup>"


def forward(duration: int | str) -> str:
    return f"<forward><duration>{duration}</duration></forward>"


def _part_list(parts: Sequence[PartSpec]) -> str:
    items = []
    for p in parts:
        inner = [f"<part-name>{escape(p.name)}</part-name>"]
        if p.instrument_sound is not None:
            inner.append(
                f'<score-instrument id="{p.part_id}-I1">'
                f"<instrument-name>{escape(p.name)}</instrument-name>"
                f"<instrument-sound>{p.instrument_sound}</instrument-sound>"
                f"</score-instrument>"
            )
        if p.midi_program is not None:
            inner.append(
                f'<midi-instrument id="{p.part_id}-I1">'
                f"<midi-program>{p.midi_program}</midi-program></midi-instrument>"
            )
        items.append(f'<score-part id="{p.part_id}">{"".join(inner)}</score-part>')
    return f"<part-list>{''.join(items)}</part-list>"


def make_score(
    measures: Optional[Sequence[str]] = None,
    parts: Optional[Sequence[PartSpec]] = None,
    *,
    timewise: bool = False,
    version: str = "4.0",
    encoding: str = "UTF-8",
) -> bytes:
    """
    Minimal valid MusicXML score, as bytes.

    Either ``measures`` (one guitar part, P1) or ``parts`` (any number of parts).
    Measures are numbered from 1. ``timewise=True`` writes the same content as
    ``score-timewise``; ``encoding`` controls both the declaration and the bytes
    (e.g. "UTF-16", as exported by Finale).
    """
    if (measures is None) == (parts is None):
        raise ValueError("pass exactly one of 'measures' or 'parts'")
    if parts is None:
        parts = [PartSpec(measures=measures)]
    counts = {len(p.measures) for p in parts}
    if len(counts) != 1:
        raise ValueError("all parts must have the same number of measures")
    n_measures = counts.pop()

    body = []
    if timewise:
        for i in range(n_measures):
            inner = "".join(f'<part id="{p.part_id}">{p.measures[i]}</part>' for p in parts)
            body.append(f'<measure number="{i + 1}">{inner}</measure>')
        root, doctype = "score-timewise", DOCTYPE_TIMEWISE
    else:
        for p in parts:
            inner = "".join(
                f'<measure number="{i + 1}">{m}</measure>' for i, m in enumerate(p.measures)
            )
            body.append(f'<part id="{p.part_id}">{inner}</part>')
        root, doctype = "score-partwise", DOCTYPE_PARTWISE

    xml = (
        f'<?xml version="1.0" encoding={quoteattr(encoding)}?>\n{doctype}\n'
        f'<{root} version="{version}">{_part_list(parts)}{"".join(body)}</{root}>\n'
    )
    return xml.encode(encoding)


@pytest.fixture
def write_score(tmp_path) -> Callable[..., Path]:
    """Write a synthetic score to a temporary file; returns its path."""

    def _write(data: bytes, name: str = "score.musicxml") -> Path:
        path = tmp_path / name
        path.write_bytes(data)
        return path

    return _write
