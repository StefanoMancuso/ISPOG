"""
core.naming: names of the output files, shared by the desktop and web apps (plan, F6, F9).
"""

from pathlib import Path

import pytest

from conftest import PartSpec, make_score, note
from core import AnalysisConfig, analyze, list_parts, load_score
from core.naming import (full_output_name, output_names, report_name, report_path_for,
                         safe_name, split_output_names, split_report_name)

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")


def _parts(write_score, specs):
    return list_parts(load_score(write_score(make_score(parts=specs))))


def _spec(part_id, name):
    return PartSpec(part_id=part_id, name=name, measures=[note("C", 4, 4)],
                    instrument_sound="pluck.guitar", midi_program=25)


@pytest.mark.parametrize("name, safe", [
    ("Chitarra classica 1", "Chitarra_classica_1"),
    ("Guitar I/II", "Guitar_I_II"),
    ("Gitarre (Solo)", "Gitarre_Solo"),
    ("Guitarra à 6", "Guitarra_à_6"),
    ("***", ""),
])
def test_safe_name(name, safe):
    assert safe_name(name) == safe


def test_full_output_and_report_names():
    assert full_output_name(Path("/x/Suite No. 1.mxl")) == "Suite No. 1_ispog.musicxml"
    assert report_path_for(Path("/y/a_ispog.musicxml")) == Path("/y/a_ispog_report.txt")
    assert split_report_name(Path("/x/duo.musicxml")) == "duo_ispog_report.txt"


def test_split_names_are_unique(write_score):
    parts = _parts(write_score, [_spec("P1", "Guitar"), _spec("P2", "Guitar"),
                                 _spec("P3", "***")])
    assert split_output_names(Path("duo.xml"), parts) == {
        "P1": "duo_Guitar_P1_ispog.musicxml",
        "P2": "duo_Guitar_P2_ispog.musicxml",
        "P3": "duo_P3_ispog.musicxml",
    }


def test_output_names_of_a_full_analysis(test01_path):
    result = analyze(AnalysisConfig(test01_path, tuning=STANDARD))
    assert output_names(result) == {"full": "Test01_ispog.musicxml"}
    assert report_name(result) == "Test01_ispog_report.txt"


def test_output_names_of_a_split_analysis(test_poli_path):
    result = analyze(AnalysisConfig(test_poli_path, tuning=STANDARD, output_mode="split"))
    assert output_names(result) == {
        "P3": "test_poli_Chitarra_classica_1_ispog.musicxml",
        "P4": "test_poli_Chitarra_classica_2_ispog.musicxml",
    }
    assert report_name(result) == "test_poli_ispog_report.txt"


def test_split_of_a_part_called_full(write_score):
    # the key 'full' is a part id here, not the whole score
    path = write_score(make_score(parts=[_spec("full", "Guitar"), _spec("P2", "Guitar")]),
                       "duo.xml")
    result = analyze(AnalysisConfig(path, tuning=STANDARD, output_mode="split"))
    assert output_names(result) == {"full": "duo_Guitar_full_ispog.musicxml",
                                    "P2": "duo_Guitar_P2_ispog.musicxml"}
