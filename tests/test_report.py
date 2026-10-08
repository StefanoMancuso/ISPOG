"""
core.report: the readable playability report (plan, F5).
"""

from datetime import datetime

from config.version import __version__
from conftest import attributes, make_score, note
from core.processor import AnalysisConfig, analyze
from core.report import render_notes_tsv, render_report, render_summary

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")
NOW = datetime(2026, 9, 30, 7, 45)


def _report(path, **kwargs) -> str:
    return render_report(analyze(AnalysisConfig(path, tuning=STANDARD, **kwargs)), now=NOW)


def test_test01_report(test01_path):
    text = _report(test01_path)
    assert text.startswith(
        f"ISPOG {__version__} — Playability report\n"
        "File:    Test01.musicxml\n"
        "Tuning:  E4 B3 G3 D3 A2 E2 · 19 frets\n"
        "Date:    2026-09-30 07:45\n"
        "Fingers: string/fret:finger (1 index, 2 middle, 3 ring, 4 pinky)\n"
        "\n"
        "== Chitarra classica (P1) ==\n"
        "Notes analyzed 44 · playable 36 (82%) · difficult 0 · unplayable 7 · not as written 1"
        " · not analyzed 0\n"
        "\n"
        "m. 1, beat 3 3/4 — UNPLAYABLE\n"
        "  Notes:   C3\n"
        "  Held:    E2 (6/0) B2 (5/2:1) E3 (4/2:2) G3 (3/0) B3 (2/0) E4 (1/0)\n"
        "  Reason:  1 note + 6 held notes on 6 strings\n"
    )
    assert text.count("— UNPLAYABLE") == 2
    assert "DIFFICULT" not in text
    assert text.endswith(
        "Not playable as written: unisons played as one note\n"
        "  m. 1, beat 3 1/2 — B2: re-attacks B2 still sounding in voice 1: "
        "one note on one string\n")


def test_closest_fingering_is_listed_low_to_high(write_score):
    # E2 + F2 both need string 6: E2 gets it, F2 has none
    path = write_score(make_score(measures=[attributes() + note("F", 2, 4)
                                            + note("E", 2, 4, chord=True)]))
    block = _report(path).split("\n\n")[2].rstrip("\n")
    assert block == ("m. 1, beat 1 — UNPLAYABLE\n"
                     "  Notes:   E2 F2\n"
                     "  Reason:  string conflict: F2 E2")


def test_held_fingers_and_finger_conflict(test_ispog_path):
    text = _report(test_ispog_path)
    block = next(b for b in text.split("\n\n") if b.startswith("m. 2, beat 4 1/2"))
    assert block == ("m. 2, beat 4 1/2 — UNPLAYABLE\n"
                     "  Notes:   G#2\n"
                     "  Held:    D4 (3/7:3) F4 (2/6:1) B4 (1/7:4)\n"
                     "  Reason:  no free finger, held: D4 (3/7:3) F4 (2/6:1) B4 (1/7:4)\n"
                     "  Closest: 6/4")


def test_part_without_problems(test_poli_path):
    text = _report(test_poli_path)
    assert text.count("No difficult or unplayable passages.") == 2
    assert "== Chitarra classica 1 (P3) ==" in text and "== Chitarra classica 2 (P4) ==" in text


def test_grace_notes_and_notes_not_analyzed(write_score):
    path = write_score(make_score(measures=[
        attributes() + note("C", 2, None, grace=True) + note("E", 4, 2)
        + note("E", 5, 2, harmonic=True)]))
    text = _report(path)
    assert "m. 1, beat 1 — UNPLAYABLE (grace notes)\n  Notes:   C2\n" in text
    assert "  Reason:  C2 out of range (below the lowest string E2)\n" in text
    assert text.endswith("Not analyzed\n  m. 1, beat 3 — E5: harmonic (not supported)\n")


def test_notes_tsv(test01_path):
    result = analyze(AnalysisConfig(test01_path, tuning=STANDARD))
    lines = render_notes_tsv(result.reports[0]).splitlines()
    assert lines[0] == ("measure\tbeat\tonset\tpitch\tmidi\tvoice\tstaff\tstring/fret\tfinger"
                        "\tcolor\treason")
    assert lines[1] == "1\t1\t0\trest\t\t1\t1\t\t\tblack\t"
    assert lines[2] == "1\t2\t1\tE2\t40\t1\t1\t6/0\t0\tgreen\tplayable"


# ---------------------------------------------------------------------------
# One-line summary (end-of-analysis message, desktop and web)
# ---------------------------------------------------------------------------

def test_summary_line(test01_path, test_poli_path):
    report = analyze(AnalysisConfig(test01_path, tuning=STANDARD)).reports[0]
    assert render_summary(report) == (
        "Chitarra classica: 44 notes · 0 difficult · 7 unplayable · 1 not as written (m. 1)")
    poli = analyze(AnalysisConfig(test_poli_path, tuning=STANDARD)).reports[0]
    assert render_summary(poli).endswith("0 unplayable")


def test_summary_line_lists_at_most_max_measures(write_score):
    # seven notes at once: more than six strings, unplayable in every measure
    chord = "".join(note(step, 3, 4, chord=i > 0) for i, step in enumerate("CDEFGAB"))
    path = write_score(make_score(measures=[attributes() + chord] + [chord] * 3))
    report = analyze(AnalysisConfig(path, tuning=STANDARD)).reports[0]
    assert report.red_measures == ["1", "2", "3", "4"]
    assert render_summary(report, max_measures=2).endswith("(m. 1, 2 …)")
    assert render_summary(report, max_measures=4).endswith("(m. 1, 2, 3, 4)")


def test_tuning_per_part(test_poli_path):
    from core.processor import PartSettings
    text = _report(test_poli_path, part_settings={
        "P4": PartSettings(("E4", "B3", "G3", "D3", "A2", "D2"), 12)})
    assert "Tuning:  per part (below)\n" in text
    assert ("== Chitarra classica 1 (P3) ==\nTuning:  E4 B3 G3 D3 A2 E2 · 19 frets\n") in text
    assert ("== Chitarra classica 2 (P4) ==\nTuning:  E4 B3 G3 D3 A2 D2 · 12 frets\n") in text


def test_problem_points(test01_path):
    from core.report import problem_points
    result = analyze(AnalysisConfig(test01_path, tuning=STANDARD))
    points = problem_points(result.reports[0])
    assert [(p.title, p.color, p.label) for p in points] == [
        ("m. 1, beat 3 1/2 — NOT AS WRITTEN", "purple", "unison"),
        ("m. 1, beat 3 3/4 — UNPLAYABLE", "red", "no free string"),
        ("m. 1, beat 4 1/2 — UNPLAYABLE", "red", "no free string"),
    ]
    unplayable = points[1]
    assert unplayable.reason == "1 note + 6 held notes on 6 strings"
    assert unplayable.details[0] == "Notes:   C3"
    assert unplayable.details[1].startswith("Held:    E2 (6/0)")
    assert all(p.part_name == "Chitarra classica" for p in points)
