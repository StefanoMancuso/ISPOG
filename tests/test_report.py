"""
core.report: the readable playability report (plan, F5).
"""

from datetime import datetime

from config.version import __version__
from conftest import attributes, make_score, note
from core.processor import AnalysisConfig, analyze
from core.report import render_notes_tsv, render_report

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
        "\n"
        "== Chitarra classica (P1) ==\n"
        "Notes analyzed 44 · playable 36 (82%) · difficult 0 · unplayable 8 · not analyzed 0\n"
        "\n"
        "m. 1, beat 3 1/2 — UNPLAYABLE\n"
        "  Notes:   B2\n"
        "  Held:    E2 (6/0) B2 (5/2) E3 (4/2) G3 (3/0) B3 (2/0) E4 (1/0)\n"
        "  Reason:  1 note + 6 held notes on 6 strings\n"
    )
    assert text.count("— UNPLAYABLE") == 3
    assert "DIFFICULT" not in text


def test_closest_fingering_is_listed_low_to_high(write_score):
    # E2 + F2 both need string 6: E2 gets it, F2 has none
    path = write_score(make_score(measures=[attributes() + note("F", 2, 4)
                                            + note("E", 2, 4, chord=True)]))
    block = _report(path).split("\n\n")[2].rstrip("\n")
    assert block == ("m. 1, beat 1 — UNPLAYABLE\n"
                     "  Notes:   E2 F2\n"
                     "  Reason:  string conflict: F2 E2")


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
    assert lines[0] == "measure\tbeat\tonset\tpitch\tmidi\tvoice\tstaff\tstring/fret\tcolor\treason"
    assert lines[1] == "1\t1\t0\trest\t\t1\t1\t\tblack\t"
    assert lines[2] == "1\t2\t1\tE2\t40\t1\t1\t6/0\tgreen\tplayable"
