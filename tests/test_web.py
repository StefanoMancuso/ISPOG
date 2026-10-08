"""
app.py: the web version (plan, F9). Runs where gradio is installed (CI job ``web``):

    pip install -e ".[dev,web]"
    pytest -m web

The logic is called directly, without starting the server; the DoD is that web and
desktop deliver identical files for the same input and options.
"""

import os
import time
from pathlib import Path

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


def test_each_part_with_its_instrument(test_poli_path, tmp_path):
    from core import PartSettings
    drop_d = PartSettings(("E4", "B3", "G3", "D3", "A2", "D2"), 12)
    web = app.run_analysis(test_poli_path, ["P3", "P4"], STANDARD, 19, "full", True,
                           staging_root=tmp_path, part_settings={"P4": drop_d})
    desktop = analyze(AnalysisConfig(test_poli_path, tuning=STANDARD, part_ids=["P3", "P4"],
                                     part_settings={"P4": drop_d}))
    assert web.files[0].read_bytes() == desktop.outputs["full"]
    assert "Tuning:  E4 B3 G3 D3 A2 D2 · 12 frets" in web.report


def test_problem_rows_are_the_desktop_list(tmp_path):
    from conftest import FIXTURES_DIR
    from core import problem_points
    path = FIXTURES_DIR / "test_ISPOG.mxl"
    web = app.run_analysis(path, ["P1"], STANDARD, 19, "full", True, staging_root=tmp_path)
    points = problem_points(analyze(AnalysisConfig(path, tuning=STANDARD)).reports[0])
    assert len(web.problems) == len(points)
    first = web.problems[0]
    assert first[0] == "🟠 m. 1, beat 1" and first[1] == "DIFFICULT · stretch"
    assert first[2] == "Chitarra classica" and first[3].startswith(points[0].reason)
    assert all(row[0].startswith("🔴") for row in web.problems[1:])


# ---------------------------------------------------------------------------
# Part table
# ---------------------------------------------------------------------------

def test_read_parts(test_poli_path):
    rows, part_ids, status = app.read_parts(test_poli_path)
    assert part_ids == ["P1", "P2", "P3", "P4"]
    assert rows[2] == [True, "Chitarra classica 1 (P3)", "E4 B3 G3 D3 A2 E2", 19]
    assert [row[0] for row in rows] == [False, False, True, True]
    assert status == "2 of 4 parts are guitars"


def test_settings_from_rows():
    rows = [[True, "Guitar (P1)", "E4 B3 G3 D3 A2 D2", 12.0],
            ["false", "Flute (P2)", "nonsense", 19],
            ["true", "Lute (P3)", "G4, D4; A3 F3 C3 G2", "19"]]
    settings = app.settings_from_rows(rows, ["P1", "P2", "P3"])
    assert list(settings) == ["P1", "P3"]
    assert settings["P1"].tuning[-1] == "D2" and settings["P1"].num_frets == 12
    assert settings["P3"].tuning == ("G4", "D4", "A3", "F3", "C3", "G2")
    with pytest.raises(ValueError, match="Guitar \\(P1\\): invalid number of strings"):
        app.settings_from_rows([[True, "Guitar (P1)", "E4 B3", 19]], ["P1"])
    with pytest.raises(ValueError, match="Guitar \\(P1\\).*frets"):
        app.settings_from_rows([[True, "Guitar (P1)", " ".join(STANDARD), "x"]], ["P1"])


def test_preset_fills_the_ticked_parts():
    rows = [[True, "A (P1)", "x", 19], [False, "B (P2)", "y", 19]]
    filled = app.apply_preset(rows, "drop_d")
    assert filled[0][2] == "E4 B3 G3 D3 A2 D2" and filled[1][2] == "y"
    assert [value for _, value in app.preset_choices()] == ["standard", "drop_d", "open_g"]


def test_tuning_written_in_the_score_is_used(write_score):
    from conftest import attributes, make_score, note
    details = ("<staff-details><staff-lines>6</staff-lines>" + "".join(
        f'<staff-tuning line="{line}"><tuning-step>{step}</tuning-step>'
        f"<tuning-octave>{octave}</tuning-octave></staff-tuning>"
        for line, (step, octave) in enumerate(
            [("D", 2), ("G", 2), ("D", 3), ("G", 3), ("B", 3), ("D", 4)], start=1))
        + "</staff-details>")
    path = write_score(make_score(measures=[
        attributes().replace("</attributes>", details + "</attributes>") + note("D", 2, 4)]))
    rows, _, _ = app.read_parts(path)
    assert rows[0][2] == "D4 B3 G3 D3 G2 D2"


# ---------------------------------------------------------------------------
# Handlers: errors become messages on the page
# ---------------------------------------------------------------------------

def test_unreadable_score_is_reported_on_the_page(write_score):
    bad = write_score(b"<html>no</html>", "bad.musicxml")
    table, part_ids, status, *cleared = app.on_score_change(str(bad))
    assert table.value["data"] == [] and part_ids == []
    assert status.startswith("⚠") and "bad.musicxml" in status
    assert cleared == [None, "", "", []]


def test_new_score_clears_the_previous_results(test01_path):
    table, part_ids, status, *cleared = app.on_score_change(str(test01_path))
    assert part_ids == ["P1"] and table.value["data"][0][0] is True
    assert cleared == [None, "", "", []]


def test_analysis_from_the_page(test01_path):
    rows, part_ids, _ = app.read_parts(test01_path)
    files, report, summary, problems, workdir = app.on_analyze(str(test01_path), rows, part_ids,
                                                               "full", True)
    assert [Path(f).name for f in files] == ["Test01_ispog.musicxml", "Test01_ispog_report.txt"]
    assert "7 unplayable" in summary and len(problems) == 3
    app.discard(workdir)


def test_refused_analysis_raises_a_page_error(write_score):
    bad = write_score(b"<html>no</html>", "bad.musicxml")
    with pytest.raises(gr.Error, match="not a MusicXML score"):
        app.on_analyze(str(bad), [[True, "Guitar (P1)", " ".join(STANDARD), 19]], ["P1"],
                       "full", True)


def test_invalid_tuning_raises_a_page_error(test01_path):
    with pytest.raises(gr.Error, match="note name"):
        app.on_analyze(str(test01_path), [[True, "Guitar (P1)", "E4 B3 G3 D3 A2 H2", 19]],
                       ["P1"], "full", True)


def test_unexpected_error_hides_details(test01_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret path /srv/x")
    monkeypatch.setattr(app, "run_analysis", boom)
    with pytest.raises(gr.Error) as error:
        app.on_analyze(str(test01_path), [[True, "Guitar (P1)", " ".join(STANDARD), 19]],
                       ["P1"], "full", True)
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
