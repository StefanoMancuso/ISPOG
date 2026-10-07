"""
core.unison and its use by the playability engine, the writer and the report.

Two voices writing the same pitch at the same time are one note (a graphic doubling)
unless the score marks them as distinct; a re-attack of a sounding unison is played as one
note on one string and marked purple; hidden notes are ignored.
"""

from fractions import Fraction

import pytest
from lxml import etree

from config.settings import COLOR_CODES
from conftest import attributes, backup, make_score, note
from core.fretboard import Fretboard
from core.playability import analyze_notes, is_analyzable
from core.processor import AnalysisConfig, analyze
from core.reader import list_parts, load_score, read_part
from core.report import render_report
from core.unison import resolve_unisons
from core.writer import LABEL_ID_PREFIX

TUNING = ("E4", "B3", "G3", "D3", "A2", "E2")
STANDARD = Fretboard(list(TUNING), 19)

# E minor, every string: (step, octave)
E_MINOR = [("E", 2), ("B", 2), ("E", 3), ("G", 3), ("B", 3), ("E", 4)]


def _chord(duration, voice=1, **top):
    """The E minor chord, low to high; ``top`` goes to its E4."""
    return "".join(note(step, octave, duration, voice=voice, chord=i > 0,
                        **(top if i == len(E_MINOR) - 1 else {}))
                   for i, (step, octave) in enumerate(E_MINOR))


def _notes(write_score, measures):
    return read_part(list_parts(load_score(write_score(make_score(measures=measures))))[0])


def _resolve(write_score, measures):
    notes = _notes(write_score, measures)
    heads = sorted((n for n in notes if is_analyzable(n)), key=lambda n: n.onset)
    return notes, resolve_unisons(heads)


def _analyze(write_score, measures):
    notes = _notes(write_score, measures)
    return notes, analyze_notes(notes, STANDARD)


def _pitched(notes):
    return [n for n in notes if n.midi is not None]


# ---------------------------------------------------------------------------
# Graphic doublings
# ---------------------------------------------------------------------------

def test_doubling_in_another_voice_is_one_note(write_score):
    notes, result = _analyze(write_score, [
        attributes() + _chord(4) + backup(4) + note("E", 4, 4, voice=2)])
    *chord, doubling = _pitched(notes)
    assert all(n.color == "green" for n in chord + [doubling])
    assert doubling.fret == chord[-1].fret == (1, 0)
    assert doubling.finger == chord[-1].finger and doubling.reason == chord[-1].reason
    assert len(result.events) == 1 and doubling not in result.events[0].notes
    assert result.unisons == []


def test_the_longest_doubling_is_fingered(write_score):
    notes, unisons = _resolve(write_score, [
        attributes() + note("E", 4, 1) + note(None, None, 3)
        + backup(4) + note("E", 4, 4, voice=2)])
    short, long_ = _pitched(notes)
    assert unisons.merged == {short: long_}
    assert unisons.heads == [long_]
    assert unisons.reattacks == {} and unisons.ends == {}


@pytest.mark.parametrize("marks, distinct", [
    (({"string": 1}, {"string": 2}), True),
    (({"string": 2, "fingering": "1"}, {"string": 2, "fingering": "4"}), False),
    (({"string": 1}, {}), False),
    (({"fingering": "0"}, {"fingering": "4"}), True),
    (({"fingering": "4"}, {"fingering": "4"}), False),
    (({"fingering": "4"}, {}), False),
])
def test_marks_decide_whether_a_unison_is_two_notes(write_score, marks, distinct):
    upper, lower = marks
    notes, unisons = _resolve(write_score, [
        attributes() + note("E", 4, 4, **upper) + backup(4) + note("E", 4, 4, voice=2, **lower)])
    assert (unisons.merged == {}) is distinct
    assert len(unisons.heads) == (2 if distinct else 1)


def test_different_spelling_is_two_notes(write_score):
    notes, unisons = _resolve(write_score, [
        attributes() + note("E", 4, 4) + backup(4) + note("F", 4, 4, alter=-1, voice=2)])
    assert [n.midi for n in _pitched(notes)] == [64, 64]
    assert unisons.merged == {} and len(unisons.heads) == 2


def test_unison_in_one_voice_is_two_notes(write_score):
    _, unisons = _resolve(write_score, [
        attributes() + note("E", 4, 4) + note("E", 4, 4, chord=True)])
    assert unisons.merged == {} and len(unisons.heads) == 2


def test_explicit_strings_keep_the_unison_unplayable_in_a_full_chord(write_score):
    notes, result = _analyze(write_score, [
        attributes() + _chord(4, string=1) + backup(4) + note("E", 4, 4, voice=2, string=2)])
    assert {n.color for n in _pitched(notes)} == {"red"}
    assert result.events[0].analysis.reason == "7 notes on 6 strings"


def test_grace_note_is_not_merged_with_the_main_note(write_score):
    _, unisons = _resolve(write_score, [
        attributes() + note("E", 4, None, grace=True) + note(None, None, 4)
        + backup(4) + note("E", 4, 4, voice=2)])
    assert unisons.merged == {} and len(unisons.heads) == 2


# ---------------------------------------------------------------------------
# Re-attacks of a sounding unison
# ---------------------------------------------------------------------------

def test_reattack_releases_the_sounding_note_and_keeps_its_end(write_score):
    notes, unisons = _resolve(write_score, [
        attributes() + note("E", 4, 4)
        + backup(4) + note(None, None, 1, voice=2) + note("E", 4, 1, voice=2)
        + note(None, None, 2, voice=2)])
    held, reattack = _pitched(notes)
    assert unisons.reattacks == {reattack: held}
    assert unisons.end(held) == 1                 # released by the re-attack
    assert unisons.end(reattack) == 4             # sounds as long as written in voice 1


def test_reattack_is_purple(write_score):
    notes, result = _analyze(write_score, [
        attributes() + note("E", 4, 4)
        + backup(4) + note(None, None, 1, voice=2) + note("E", 4, 3, voice=2)])
    held, reattack = _pitched(notes)
    assert held.color == "green"
    assert reattack.color == "purple" and reattack.fret == (1, 0)
    assert reattack.reason == "re-attacks E4 still sounding in voice 1: one note on one string"
    assert result.unisons == [reattack]


def test_new_attack_against_a_tied_note_is_purple(write_score):
    notes, result = _analyze(write_score, [
        attributes() + note("E", 4, 4, tie=("start",)) + backup(4) + note(None, None, 4, voice=2),
        note("E", 4, 4, tie=("stop",)) + backup(4) + note("E", 4, 4, voice=2),
    ])
    head, continuation, reattack = _pitched(notes)
    assert head.color == continuation.color == "green"
    assert reattack.color == "purple" and result.unisons == [reattack]


def test_reattack_on_explicit_other_string_is_played_as_written(write_score):
    notes, result = _analyze(write_score, [
        attributes() + note("E", 4, 4, string=1)
        + backup(4) + note(None, None, 1, voice=2) + note("E", 4, 3, voice=2, string=2)])
    held, second = _pitched(notes)
    assert (held.color, second.color) == ("green", "green")
    assert (held.fret, second.fret) == ((1, 0), (2, 5))
    assert result.unisons == []


def test_unplayable_reattack_stays_red(write_score):
    # the chord holds every string: E4 re-plucks string 1, F4 finds no string left
    notes, result = _analyze(write_score, [
        attributes() + _chord(4)
        + backup(4) + note(None, None, 1, voice=2) + note("E", 4, 3, voice=2)
        + note("F", 4, 3, voice=2, chord=True)])
    reattack, f4 = _pitched(notes)[-2:]
    assert (reattack.color, f4.color) == ("red", "red")
    assert result.unisons == []


def test_reattack_honors_the_written_end_of_the_held_note(write_score):
    # B3 re-plucked in voice 2 for a quarter, but voice 1 holds it for the whole measure:
    # string 2 stays busy, so C4 at beat 3 cannot take it
    notes, result = _analyze(write_score, [
        attributes() + _chord(4)
        + backup(4) + note(None, None, 1, voice=2) + note("B", 3, 1, voice=2)
        + note("C", 4, 2, voice=2)])
    reattack, c4 = _pitched(notes)[-2:]
    assert reattack.color == "purple"
    assert c4.color == "red"
    assert next(e for e in result.events if e.onset == Fraction(2)).held


# ---------------------------------------------------------------------------
# Hidden notes
# ---------------------------------------------------------------------------

def test_hidden_notes_are_ignored(write_score):
    notes, result = _analyze(write_score, [
        attributes() + _chord(4)
        + backup(4) + note("E", 4, 4, voice=2, hidden=True)
        + backup(4) + note("F", 4, 4, voice=3, hidden=True)])
    *chord, e4, f4 = _pitched(notes)
    assert all(n.color == "green" for n in chord)
    assert (e4.color, f4.color) == ("black", "black")
    assert f4.reason == "hidden note (timing only)"
    assert result.not_analyzed == [] and result.unisons == []


def test_hidden_notes_keep_the_timing(write_score):
    notes = _notes(write_score, [
        attributes() + note("E", 4, 2, hidden=True) + note("G", 4, 2)])
    assert [n.onset for n in notes] == [0, 2]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def test_output_report_and_counts(write_score, assert_valid):
    path = write_score(make_score(measures=[
        attributes() + _chord(4)
        + backup(4) + note(None, None, 1, voice=2) + note("E", 4, 3, voice=2)
        + backup(4) + note("G", 4, 4, voice=3, hidden=True)]))
    result = analyze(AnalysisConfig(path, tuning=TUNING))
    data = result.outputs["full"]
    assert_valid(data)

    report = result.reports[0]
    assert report.counts == {"green": 6, "orange": 0, "red": 0, "purple": 1, "black": 0}
    assert [n.pitch_name for n in report.unisons] == ["E4"]

    root = etree.fromstring(data)
    labels = [d for d in root.iter("direction") if d.get("id", "").startswith(LABEL_ID_PREFIX)]
    assert [d.findtext("direction-type/words") for d in labels] == ["unison"]
    assert labels[0].find("direction-type/words").get("color") == COLOR_CODES["purple"]
    hidden = root.find(".//note[@print-object='no']")
    assert hidden.find("notehead") is None          # not colored

    text = render_report(result)
    assert ("Not playable as written: unisons played as one note\n"
            "  m. 1, beat 2 — E4: re-attacks E4 still sounding in voice 1") in text
