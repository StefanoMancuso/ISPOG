"""
Real scores from many editors (plan, F8).

Every file in tests/corpus (MuseScore 3/4, Sibelius, Finale, Dorico, Guitar Pro, .mxl,
ensembles...) must be read, analyzed and written back as valid MusicXML, with every guitar
note colored and the other parts untouched. The folder is not versioned (the scores may be
copyrighted): without files these tests are skipped, as in CI.

    pytest -m corpus -v                       # only the corpus
    ISPOG_CORPUS=D:/scores pytest -m corpus   # another folder (PowerShell: $env:ISPOG_CORPUS=...)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from lxml import etree

from config.settings import COLOR_CODES
from conftest import CORPUS_DIR, corpus_files
from core import (AnalysisConfig, AnalysisResult, PartInfo, analyze, list_parts, load_score,
                  render_report)

pytestmark = pytest.mark.corpus

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")
ANALYSIS_COLORS = {COLOR_CODES[c] for c in ("green", "orange", "red")}
FILES = corpus_files()


@dataclass
class Case:
    path: Path
    parts: list[PartInfo]
    result: AnalysisResult

    @property
    def targets(self) -> set[str]:
        return {r.part_id for r in self.result.reports}


def _id(path: Path) -> str:
    return path.relative_to(CORPUS_DIR).as_posix()


@pytest.fixture(
    scope="module",
    params=FILES or [pytest.param(None, marks=pytest.mark.skip(
        reason=f"no scores in {CORPUS_DIR}"))],
    ids=[_id(p) for p in FILES] or ["empty"],
)
def case(request) -> Case:
    path = request.param
    parts = list_parts(load_score(path))
    result = analyze(AnalysisConfig(path, tuning=STANDARD))
    return Case(path=path, parts=parts, result=result)


def _parse(data: bytes) -> etree._Element:
    return etree.fromstring(data, etree.XMLParser(load_dtd=False, no_network=True,
                                                  resolve_entities=False, huge_tree=True))


def test_guitars_are_found(case):
    guitars = [p.part_id for p in case.parts if p.is_guitar]
    assert guitars or len(case.parts) == 1, (
        "no guitar detected; parts: " + ", ".join(f"{p.part_id} {p.name!r}" for p in case.parts))
    assert case.targets == set(guitars or [case.parts[0].part_id])


def test_every_guitar_note_is_colored_or_explained(case):
    for report in case.result.reports:
        left_out = set(map(id, report.not_analyzed))
        for note in report.pitched:
            where = f"{report.part_id} m. {note.measure_number} beat {note.beat_label}"
            if note.color == "black":
                assert id(note) in left_out and note.reason, f"{where}: {note.pitch_name} black"
            else:
                assert note.color in ("green", "orange", "red"), where


def test_report_is_coherent(case):
    for report in case.result.reports:
        assert sum(report.counts.values()) == len(report.pitched)
        measures = {n.measure_number for n in report.notes}
        assert set(report.red_measures) <= measures
    text = render_report(case.result)
    assert all(f"({r.part_id}) ==" in text for r in case.result.reports)


def test_output_is_valid_musicxml(case, assert_valid):
    assert_valid(case.result.outputs["full"])


def test_written_colors_match_the_analysis(case):
    root = _parse(case.result.outputs["full"])
    for report in case.result.reports:
        written = [n for n in root.iterfind(f"part[@id='{report.part_id}']//note")
                   if n.find("pitch") is not None]
        colored = sum(1 for n in written
                      if (n.find("notehead") is not None
                          and n.find("notehead").get("color") in ANALYSIS_COLORS))
        counts = report.counts
        assert colored >= counts["green"] + counts["orange"] + counts["red"]


def test_other_parts_are_untouched(case):
    original = load_score(case.path).getroot()
    written = _parse(case.result.outputs["full"])
    for part in case.parts:
        if part.part_id in case.targets:
            continue
        path = f"part[@id='{part.part_id}']"
        assert (etree.tostring(written.find(path), method="c14n")
                == etree.tostring(original.find(path), method="c14n")), part.part_id


def test_separate_parts_are_valid(case, assert_valid):
    split = analyze(AnalysisConfig(case.path, tuning=STANDARD, output_mode="split"))
    assert set(split.outputs) == case.targets
    for data in split.outputs.values():
        assert_valid(data)


def test_analysis_is_idempotent(case, tmp_path):
    first = case.result.outputs["full"]
    again = tmp_path / "again.musicxml"
    again.write_bytes(first)
    assert analyze(AnalysisConfig(again, tuning=STANDARD)).outputs["full"] == first
