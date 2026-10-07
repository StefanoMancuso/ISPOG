"""
core.playability and core.analyzer (plan, F3).

Test01 is compared with the pre-refactor baseline: the only accepted difference is listed
in EXPECTED_DIFFERENCES, with its reason from plan §5. Synthetic scores cover ties, held
notes, grace notes and notes that are not analyzed.
"""

import csv
import logging
from fractions import Fraction

import pytest

from conftest import BASELINE_DIR, attributes, backup, make_score, note
from core.analyzer import ChordAnalyzer, FretPosition, Issue, Placement, Playability
from core.fretboard import Fretboard
from core.model import Note
from core.playability import analyze_notes
from core.reader import list_parts, load_score, read_part

STANDARD = Fretboard(["E4", "B3", "G3", "D3", "A2", "E2"], 19)

# (index in the part, pitch, baseline color, new color, plan §5 reason)
EXPECTED_DIFFERENCES = [
    (23, "B2", "red", "purple", "0.10.0b3 unison re-attacked while the chord still sounds"),
    (31, "D3", "red", "green", "§5.1 tied continuation inherits its head"),
]


def _analyze(write_score, measures, fretboard=STANDARD):
    notes = read_part(list_parts(load_score(write_score(make_score(measures=measures))))[0])
    return notes, analyze_notes(notes, fretboard)


def _by_name(notes):
    return {f"{n.pitch_name}@{n.onset}": n for n in notes}


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test01(test01_path):
    notes = read_part(list_parts(load_score(test01_path))[0])
    return notes, analyze_notes(notes, STANDARD)


def test_test01_matches_baseline_except_expected_differences(test01):
    notes, _ = test01
    with open(BASELINE_DIR / "Test01_baseline_colors.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    differences = [
        (i, n.pitch_name, row["color"], "-" if n.is_rest else n.color)
        for i, (row, n) in enumerate(zip(rows, notes, strict=True))
        if row["color"] != ("-" if n.is_rest else n.color)
    ]
    assert differences == [d[:4] for d in EXPECTED_DIFFERENCES]


def test_test01_tied_continuation(test01):
    notes, _ = test01
    head, continuation = [n for n in notes if n.tie_start or n.tie_stop]
    assert (head.pitch_name, continuation.pitch_name) == ("D3", "D3")
    assert (continuation.color, continuation.fret) == (head.color, head.fret)
    assert head.sounding_duration == head.duration + continuation.duration


def test_test01_held_chord_blocks_later_attacks(test01):
    # measure 1: the E minor chord is still sounding when B2 and C3 are attacked; B2 is a
    # note of the chord, re-plucked on its string (not as written), C3 has no string left
    _, result = test01
    reattack, blocked = [e for e in result.events
                         if e.onset in (Fraction(5, 2), Fraction(11, 4))]
    assert [n.pitch_name for n in reattack.notes] == ["B2"]
    assert reattack.analysis.playability is Playability.PLAYABLE
    assert len(reattack.held) == 5
    assert reattack.notes[0].color == "purple" and reattack.notes[0].fret == (5, 2)
    assert result.unisons == reattack.notes

    assert [n.pitch_name for n in blocked.notes] == ["C3"]
    assert blocked.analysis.playability is Playability.UNPLAYABLE
    assert len(blocked.held) == 6
    assert blocked.analysis.reason == "1 note + 6 held notes on 6 strings"


def test_test01_every_pitched_note_is_colored(test01):
    notes, result = test01
    assert result.not_analyzed == []
    assert all(n.color in ("green", "orange", "red", "purple") for n in notes if not n.is_rest)
    assert all(n.reason for n in notes if not n.is_rest)


# ---------------------------------------------------------------------------
# Ties and held notes
# ---------------------------------------------------------------------------

def test_tied_note_is_not_reattacked(write_score):
    # E2 tied over the bar line; F2 (only on string 6) is attacked under the tie
    notes, result = _analyze(write_score, [
        attributes() + note("E", 2, 4, tie=("start",)),
        note("E", 2, 4, tie=("stop",)) + backup(4) + note("F", 2, 4, voice=2),
    ])
    head, continuation, f2 = notes
    assert head.color == continuation.color == "green"
    assert continuation.fret == head.fret == (6, 0)
    assert f2.color == "red"
    assert f2.reason == "string conflict with held notes: E2 (6/0)"
    assert all(continuation not in e.notes for e in result.events)


def test_tie_chain_extends_the_sounding_duration(write_score):
    notes, _ = _analyze(write_score, [
        attributes() + note("A", 2, 4, tie=("start",)),
        note("A", 2, 4, tie=("stop", "start")),
        note("A", 2, 2, tie=("stop",)) + note("F", 2, 2),
    ])
    head = notes[0]
    assert head.sounding_duration == 10
    assert notes[-1].color == "green"            # A2 released: F2 is free


def test_tie_across_voice_change(write_score):
    notes, _ = _analyze(write_score, [
        attributes() + note("E", 2, 4, tie=("start",), voice=1),
        note("E", 2, 4, tie=("stop",), voice=2),
    ])
    assert notes[0].sounding_duration == 8


def test_tie_stop_without_start_is_analyzed(write_score, caplog):
    with caplog.at_level(logging.WARNING, logger="core.playability"):
        notes, result = _analyze(write_score, [attributes() + note("E", 2, 4, tie=("stop",))])
    assert notes[0].color == "green" and len(result.events) == 1
    assert "Tie stop without start" in caplog.text


def test_held_note_constrains_until_it_ends(write_score):
    # E2 half note held; F2 attacked while it sounds (red), then after it ends (green)
    notes, _ = _analyze(write_score, [
        attributes() + note("E", 2, 2) + note(None, None, 2)
        + backup(4) + note("F", 2, 1, voice=2) + note(None, None, 1, voice=2)
        + note("F", 2, 2, voice=2),
    ])
    named = _by_name(notes)
    assert named["F2@0"].color == "red"
    assert named["F2@2"].color == "green"


# ---------------------------------------------------------------------------
# Grace notes and notes left out
# ---------------------------------------------------------------------------

def test_grace_chord_is_fingered_alone_and_does_not_constrain(write_score):
    notes, result = _analyze(write_score, [
        attributes()
        + note("E", 2, None, grace=True) + note("B", 2, None, grace=True, chord=True)
        + note("E", 2, 4) + note("F", 3, 4, chord=True),
    ])
    grace_events = [e for e in result.events if e.grace]
    assert [[n.pitch_name for n in e.notes] for e in grace_events] == [["E2", "B2"]]
    assert all(n.color == "green" for n in notes)


def test_grace_note_is_not_held(write_score):
    # grace F2 takes string 6; E2 right after needs string 6 too and must stay free
    notes, _ = _analyze(write_score, [
        attributes(divisions=2) + note("F", 2, None, grace=True)
        + note("C", 4, 1) + note("E", 2, 1),
    ])
    assert _by_name(notes)["E2@1/2"].color == "green"


def test_out_of_range(write_score):
    notes, _ = _analyze(write_score, [attributes() + note("C", 2, 2) + note("E", 6, 2)],
                        Fretboard(["E4", "B3", "G3", "D3", "A2", "E2"], 12))
    low, high = notes
    assert low.color == high.color == "red"
    assert low.fret == (-1, -1)
    assert low.reason == "C2 out of range (below the lowest string E2)"
    assert high.reason == "E6 out of range (above fret 12)"


def test_more_notes_than_strings(write_score):
    chord = note("E", 2, 4) + "".join(
        note(step, octave, 4, chord=True)
        for step, octave in [("A", 2), ("D", 3), ("G", 3), ("B", 3), ("E", 4), ("A", 4)])
    notes, _ = _analyze(write_score, [attributes() + chord])
    assert all(n.color == "red" for n in notes)
    assert notes[0].reason == "7 notes on 6 strings"


def test_notes_left_out_stay_black(write_score):
    notes, result = _analyze(write_score, [
        attributes() + note(None, None, 1) + note("E", 4, 1, alter=0.5)
        + note("E", 5, 1, harmonic=True) + note("G", 4, 1, cue=True),
    ])
    rest, micro, harmonic, cue = notes
    assert all(n.color == "black" for n in notes)
    assert result.not_analyzed == [micro, harmonic, cue]
    assert [n.reason for n in result.not_analyzed] == [
        "microtone not analyzed", "harmonic (not supported)", "cue note"]
    assert result.events == []


# ---------------------------------------------------------------------------
# ChordAnalyzer
# ---------------------------------------------------------------------------

def _p(*pairs):
    return [FretPosition(s, f) for s, f in pairs]


@pytest.mark.parametrize("positions, playability, reason", [
    (_p((1, 0), (2, 0)), Playability.PLAYABLE, "open strings"),
    (_p((5, 3), (4, 2), (2, 1)), Playability.PLAYABLE, "playable"),
    (_p((6, 1), (5, 2), (4, 3), (3, 4), (2, 5)), Playability.UNPLAYABLE,
     "requires 5 fingers (max 4)"),
    (_p((6, 1), (1, 7)), Playability.UNPLAYABLE,
     "fret span 6: fingers 1–4 over 6 frets (max 4)"),
    (_p((6, 5), (5, 6), (4, 7), (2, 8), (1, 8)), Playability.DIFFICULT,
     "pinky barré on fret 8, strings 1–2"),
    (_p((6, 1), (1, 5)), Playability.DIFFICULT, "stretch: fingers 1–4 over 4 frets"),
    (_p((6, 1), (4, 3), (3, 2), (2, 1), (1, 5)), Playability.DIFFICULT,
     "stretch: fingers 1–4 over 4 frets; stretch: fingers 2–4 over 3 frets; "
     "stretch: fingers 3–4 over 2 frets"),
])
def test_fingering_reasons(positions, playability, reason):
    analysis = ChordAnalyzer().analyze_positions(positions)
    assert (analysis.playability, analysis.reason) == (playability, reason)


def test_difficulty_of_held_notes_is_named():
    # pinky barré held on strings 1-2, index attacked on fret 5: the problem is not the C4
    b4, f_sharp4, c4 = (_note("B", 4, midi=71), _note("F", 4, 1, midi=66),
                        _note("C", 4, midi=60))
    for n in (b4, f_sharp4, c4):
        n.set_fret_pos(STANDARD.positions(n.midi))
    held = [(b4, Placement(1, 7, 4)), (f_sharp4, Placement(2, 7, 4))]
    best = ChordAnalyzer(STANDARD).candidates([c4], held)[0]
    assert best.playability is Playability.DIFFICULT
    assert best.reason == "pinky barré on fret 7, strings 1–2 (held notes)"
    assert (best.new_positions, best.new_fingers) == ([FretPosition(3, 5)], [2])


# ---------------------------------------------------------------------------
# test_ISPOG: fingerings checked by hand on the guitar
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_ispog():
    from conftest import FIXTURES_DIR
    notes = read_part(list_parts(load_score(FIXTURES_DIR / "test_ISPOG.mxl"))[0])
    return notes, analyze_notes(notes, STANDARD)


def _event(result, measure, beat):
    events = [e for e in result.events
              if e.measure_number == measure and e.notes[0].beat == Fraction(beat)]
    assert len(events) == 1
    return events[0]


def test_ispog_barre_chord_with_a_wide_pinky(test_ispog):
    # m. 1, b. 1: F2 needs 6/1 (index barré), A4 1/5 with the pinky: difficult, not impossible
    event = _event(test_ispog[1], "1", 1)
    assert event.analysis.playability is Playability.DIFFICULT
    assert event.analysis.issue == Issue.STRETCH
    assert event.analysis.has_barre


def test_ispog_earlier_chord_is_fingered_for_what_follows(test_ispog):
    # m. 2: A3 E4 A4 + A2, then F3 under the held chord. Fingered onset by onset the
    # first chord took A3 on 3/2 and F3 needed a pinky barré; the whole passage is playable.
    result = test_ispog[1]
    first, f3 = _event(result, "2", 1), _event(result, "2", Fraction(3, 2))
    assert first.analysis.playability is Playability.PLAYABLE
    assert f3.analysis.playability is Playability.PLAYABLE
    assert [n.pitch_name for n in f3.held] == ["A4", "E4", "A3"]
    assert f3.notes[0].finger in (1, 2, 3, 4)


def test_ispog_held_fingers_block_the_bass(test_ispog):
    # m. 2, b. 4 1/2: D4 F4 B4 held with the fingers of b. 4 (E3 included); G#2 6/4 needs
    # a finger behind the index. The later onset is the unplayable one.
    result = test_ispog[1]
    chord, bass = _event(result, "2", 4), _event(result, "2", Fraction(9, 2))
    assert chord.analysis.playability is Playability.PLAYABLE
    assert bass.analysis.playability is Playability.UNPLAYABLE
    assert bass.analysis.issue == Issue.FINGER_CONFLICT
    assert bass.analysis.reason.startswith("no free finger, held: ")
    assert [n.color for n in bass.notes] == ["red"]


def test_ispog_unchanged_points(test_ispog):
    result = test_ispog[1]
    assert _event(result, "2", Fraction(5, 2)).analysis.issue == Issue.SPAN     # C4, span 7
    assert _event(result, "2", 3).analysis.issue == Issue.SPAN
    assert _event(result, "3", 1).analysis.issue == Issue.STRINGS
    assert _event(result, "3", 3).analysis.playability is Playability.PLAYABLE


def test_held_notes_keep_their_finger(test_ispog):
    for event in test_ispog[1].events:
        held = [(n.fret, n.finger) for n in event.held]
        fixed = [((p.string, p.fret), f) for p, f in zip(event.analysis.fixed,
                                                          event.analysis.fingers)]
        assert held == fixed


def _note(step, octave, alter=0, midi=None):
    return Note(element=None, part_id="P1", measure_number="1", step=step, octave=octave,
                alter=Fraction(alter), midi=midi)


def test_sort_by_sounding_pitch_uses_alterations():
    # the 0.9 bubble sort ignored alterations: F#3 and F3 kept their order
    f3, f_sharp3, e4 = _note("F", 3, midi=53), _note("F", 3, 1, midi=54), _note("E", 4, midi=64)
    ordered = ChordAnalyzer.sort_notes_by_pitch([f3, f_sharp3, e4])
    assert ordered == [e4, f_sharp3, f3]


def test_analysis_reports_held_positions(write_score):
    _, result = _analyze(write_score, [
        attributes() + note("E", 2, 4) + backup(4) + note(None, None, 1, voice=2)
        + note("G", 3, 1, voice=2),
    ])
    event = result.events[-1]
    assert [n.pitch_name for n in event.held] == ["E2"]
    assert event.analysis.fixed == [FretPosition(6, 0)]
    assert event.analysis.positions[0] == FretPosition(6, 0)
