"""
gui.outputs: output names and part preselection, without Tkinter (plan, F6).
"""

from pathlib import Path

import pytest

from conftest import PartSpec, make_score, note
from core import list_parts, load_score
from gui.outputs import (full_output_name, preselected_part_ids, report_path_for, safe_name,
                         shorten, split_output_names, split_report_name)


def _parts(write_score, specs):
    return list_parts(load_score(write_score(make_score(parts=specs))))


def _spec(part_id, name, guitar=True):
    return PartSpec(part_id=part_id, name=name, measures=[note("C", 4, 4)],
                    instrument_sound="pluck.guitar" if guitar else "pluck.banjo",
                    midi_program=25 if guitar else 106)


def test_guitars_are_preselected(test_poli_path):
    assert preselected_part_ids(list_parts(load_score(test_poli_path))) == ["P3", "P4"]


def test_single_part_is_preselected_even_if_not_a_guitar(write_score):
    assert preselected_part_ids(_parts(write_score, [_spec("P1", "Banjo", False)])) == ["P1"]


def test_nothing_preselected_without_guitars(write_score):
    parts = _parts(write_score, [_spec("P1", "Banjo", False), _spec("P2", "Flute", False)])
    assert preselected_part_ids(parts) == []


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


@pytest.mark.parametrize("text, max_chars, expected", [
    ("short.mxl", 20, "short.mxl"),
    ("abcdefghij", 10, "abcdefghij"),
    ("abcdefghijk", 10, "abcd…ghijk"),
    ("Suite for guitar quartet No. 3.musicxml", 20, "Suite for…3.musicxml"),
])
def test_shorten(text, max_chars, expected):
    result = shorten(text, max_chars)
    assert result == expected and len(result) <= max_chars
