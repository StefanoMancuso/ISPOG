"""
app.py: the web version (plan, F9). Runs where gradio is installed (CI job ``web``):

    pip install -e ".[dev,web]"
    pytest -m web

The logic is called directly, without starting the server; the DoD is that web and
desktop deliver identical files for the same input and options.
"""

import os
import time

import pytest

gr = pytest.importorskip("gradio")

import app  # noqa: E402
from core import AnalysisConfig, analyze, render_report  # noqa: E402

pytestmark = pytest.mark.web

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")


def _without_date(report: str) -> str:
    return "\n".join(line for line in report.splitlines() if not line.startswith("Date:"))


# ---------------------------------------------------------------------------
# Same files as the desktop app
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture, part_ids, mode, labels, expected_names", [
    ("test01_path", ["P1"], "full", True,
     ["Test01_ispog.musicxml", "Test01_ispog_report.txt"]),
    ("test_poli_path", ["P3", "P4"], "split", True,
     ["test_poli_Chitarra_classica_1_ispog.musicxml",
      "test_poli_Chitarra_classica_2_ispog.musicxml", "test_poli_ispog_report.txt"]),
    ("test_poli_path", ["P1", "P3"], "full", False,
     ["test_poli_ispog.musicxml", "test_poli_ispog_report.txt"]),
])
def test_web_and_desktop_outputs_are_identical(request, tmp_path, fixture, part_ids, mode,
                                               labels, expected_names):
    score = request.getfixturevalue(fixture)
    web = app.run_analysis(score, part_ids, STANDARD, 19, mode, labels, staging_root=tmp_path)
    desktop = analyze(AnalysisConfig(score, tuning=STANDARD, num_frets=19, part_ids=part_ids,
                                     output_mode=mode, labels=labels))

    assert [p.name for p in web.files] == expected_names
    assert all(p.parent == web.workdir and web.workdir.parent == tmp_path for p in web.files)
    assert [p.read_bytes() for p in web.files[:-1]] == list(desktop.outputs.values())
    assert _without_date(web.files[-1].read_text(encoding="utf-8")) == _without_date(
        render_report(desktop))
    assert web.report == web.files[-1].read_text(encoding="utf-8")


def test_summary_is_the_desktop_text(test01_path, tmp_path):
    web = app.run_analysis(test01_path, ["P1"], STANDARD, 19, "full", True, staging_root=tmp_path)
    assert web.summary.endswith(
        "- Chitarra classica: 44 notes · 0 difficult · 7 unplayable · 1 not as written (m. 1)")


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

def test_tuning_choices_are_the_desktop_presets_and_custom():
    values = [value for _, value in app.tuning_choices()]
    assert values == ["standard", "drop_d", "open_g", app.CUSTOM]


def test_resolve_tuning():
    assert app.resolve_tuning("standard", 8, ["C4"] * 8) == STANDARD
    assert app.resolve_tuning("drop_d", 6, [])[-1] == "D2"
    notes = ["E4", "B3", "G3", "D3", "A2", "E2", "B1", "F#1"]
    assert app.resolve_tuning(app.CUSTOM, 7, notes) == tuple(notes[:7])
    with pytest.raises(ValueError, match="note for each"):
        app.resolve_tuning(app.CUSTOM, 6, ["E4", "B3", None, "D3", "A2", "E2"])
    with pytest.raises(ValueError, match="unknown tuning"):
        app.resolve_tuning("lute", 6, notes)


def test_default_custom_notes_are_the_desktop_ones():
    assert app.DEFAULT_CUSTOM_NOTES == ("E4", "B3", "G3", "D3", "A2", "E2", "B1", "F#1")


def test_read_parts(test_poli_path):
    choices, preselected, status = app.read_parts(test_poli_path)
    assert choices[2] == ("Chitarra classica 1 (P3)", "P3")
    assert preselected == ["P3", "P4"] and status == "2 of 4 parts are guitars"


# ---------------------------------------------------------------------------
# Handlers: errors become messages on the page
# ---------------------------------------------------------------------------

def test_unreadable_score_is_reported_on_the_page(write_score):
    bad = write_score(b"<html>no</html>", "bad.musicxml")
    parts, status, *cleared = app.on_score_change(str(bad))
    assert parts.choices == [] and status.startswith("⚠") and "bad.musicxml" in status
    assert cleared == [None, "", ""]


def test_new_score_clears_the_previous_results(test01_path):
    parts, status, *cleared = app.on_score_change(str(test01_path))
    assert parts.value == ["P1"] and cleared == [None, "", ""]


def test_refused_analysis_raises_a_page_error(write_score):
    bad = write_score(b"<html>no</html>", "bad.musicxml")
    with pytest.raises(gr.Error, match="not a MusicXML score"):
        app.on_analyze(str(bad), ["P1"], "standard", 6, 19, "full", True)


def test_invalid_custom_tuning_raises_a_page_error(test01_path):
    with pytest.raises(gr.Error, match="note name"):
        app.on_analyze(str(test01_path), ["P1"], app.CUSTOM, 6, 19, "full", True,
                       "E4", "B3", "G3", "D3", "A2", "H2", "B1", "F#1")


def test_unexpected_error_hides_details(test01_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret path /srv/x")
    monkeypatch.setattr(app, "run_analysis", boom)
    with pytest.raises(gr.Error) as error:
        app.on_analyze(str(test01_path), ["P1"], "standard", 6, 19, "full", True)
    assert "secret" not in str(error.value)


# ---------------------------------------------------------------------------
# Temporary files
# ---------------------------------------------------------------------------

def test_discard_removes_the_analysis_folder(test01_path, tmp_path):
    web = app.run_analysis(test01_path, ["P1"], STANDARD, 19, "full", True, staging_root=tmp_path)
    app.discard(str(web.workdir))
    app.discard(None)
    assert not web.workdir.exists()


def test_leftovers_are_removed_at_the_next_analysis(test01_path, tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    (old / "x.musicxml").write_text("x")
    past = time.time() - app.STAGING_MAX_AGE - 1
    os.utime(old, (past, past))
    recent = tmp_path / "recent"
    recent.mkdir()
    app.run_analysis(test01_path, ["P1"], STANDARD, 19, "full", True, staging_root=tmp_path)
    assert not old.exists() and recent.exists()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def test_page_builds_without_starting_the_server():
    demo = app.build_demo()
    assert isinstance(demo, gr.Blocks) and demo.analytics_enabled is False
    assert all(fn.api_visibility == "private" for fn in demo.fns.values())


@pytest.mark.parametrize("public", [False, True])
def test_footer(monkeypatch, public):
    monkeypatch.setattr(app, "WEB_SHOW_REPOSITORY", public)
    text = app.footer()
    assert app.__version__ in text and "GPL" in text and "Crecchi" in text
    assert "deleted" in text
    assert (app.REPOSITORY_URL in text) is public
