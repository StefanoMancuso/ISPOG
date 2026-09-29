"""
core.fretboard: note names, positions, parity with the 0.9.2 string matrix (plan, F3).
"""

import json

import pytest

from conftest import BASELINE_DIR
from core.fretboard import Fretboard, midi_to_note_name, note_name_to_midi

STANDARD = ["E4", "B3", "G3", "D3", "A2", "E2"]


@pytest.mark.parametrize("name, midi", [
    ("C4", 60), ("E2", 40), ("E4", 64), ("F#1", 30), ("Bb3", 58), ("B#3", 60),
    ("Cb4", 59), ("F##2", 43), ("Fx2", 43), ("Ebb4", 62), ("c-1", 0), (" A4 ", 69),
])
def test_note_name_to_midi(name, midi):
    assert note_name_to_midi(name) == midi


@pytest.mark.parametrize("name", ["", "H2", "E", "E#", "#E4", "E4b", "Es4", "E 4"])
def test_invalid_note_name(name):
    with pytest.raises(ValueError):
        note_name_to_midi(name)


@pytest.mark.parametrize("midi, name", [(60, "C4"), (54, "F#3"), (40, "E2"), (0, "C-1")])
def test_midi_to_note_name(midi, name):
    assert midi_to_note_name(midi) == name


def test_positions_standard_tuning():
    board = Fretboard(STANDARD, 19)
    assert board.num_strings == 6
    assert board.positions(64) == [(1, 0), (2, 5), (3, 9), (4, 14), (5, 19)]
    assert board.positions(40) == [(6, 0)]
    assert board.positions(39) == []
    assert board.positions(64 + 19) == [(1, 19)]
    assert board.positions(64 + 20) == []


def test_out_of_range_reason():
    board = Fretboard(STANDARD, 19)
    assert board.out_of_range_reason(36) == "below the lowest string E2"
    assert board.out_of_range_reason(90) == "above fret 19"


@pytest.mark.parametrize("tuning, frets", [([], 19), (["E4"], -1), (["X4"], 19)])
def test_invalid_fretboard(tuning, frets):
    with pytest.raises(ValueError):
        Fretboard(tuning, frets)


def _baseline_cases():
    with open(BASELINE_DIR / "fretboard_0.9.2.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("case", _baseline_cases(),
                         ids=lambda c: f"{'-'.join(c['tuning'])}/{c['frets']}")
def test_parity_with_0_9_2(case):
    """
    Same positions as the 0.9.2 string matrix, except at the edges of the neck
    (plan §5.3):
    - 0.9.2 reached fret ``frets + 1`` through the alteration (e.g. A#4 at fret 20);
    - 0.9.2 missed a flat on the last fret (Cb4 at fret 19) and an altered open string
      (F#1 on an 8-string), because it matched natural note names only.
    """
    board = Fretboard(case["tuning"], case["frets"])
    frets = case["frets"]
    for name, old in case["positions"].items():
        old = {tuple(p) for p in old}
        new = set(board.positions(note_name_to_midi(name)))
        assert all(fret == frets + 1 for _, fret in old - new), (name, old - new)
        assert all(fret in (0, frets) for _, fret in new - old), (name, new - old)
