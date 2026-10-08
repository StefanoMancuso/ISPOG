"""
gui: the desktop window (plan, F5–F6).

Pure helpers run wherever Tkinter is installed; window tests also need a display (locally,
or ``xvfb-run`` in CI) and are skipped without one. Dialogs and message boxes are replaced
by stand-ins that record what the user would have seen.
"""

import gc
import time
from pathlib import Path

import pytest

tkinter = pytest.importorskip("tkinter")

from core.errors import NoGuitarPartError  # noqa: E402
from gui import main_window, widgets  # noqa: E402
from core import parse_tuning  # noqa: E402
from gui.widgets import ProcessButton  # noqa: E402

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")


# ---------------------------------------------------------------------------
# Without a window
# ---------------------------------------------------------------------------

def test_parse_tuning():
    assert parse_tuning(" E4 B3,G3;D3  A2 E2 ") == STANDARD
    assert parse_tuning("") == ()


def test_error_messages():
    assert ProcessButton._error_message(NoGuitarPartError("No guitar part")) == "No guitar part"
    message = ProcessButton._error_message(RuntimeError("boom"))
    assert message.startswith("Unexpected error: boom") and "log file" in message


# ---------------------------------------------------------------------------
# With a window
# ---------------------------------------------------------------------------

class Stubs:
    """Answers to the dialogs, and the messages shown."""

    def __init__(self):
        self.open: list[Path] = []
        self.save: list[Path] = []
        self.folder: list[Path] = []
        self.answer_yes = True            # answer to every yes/no question
        self.messages: list[tuple[str, str]] = []


@pytest.fixture
def app(monkeypatch):
    try:
        window = main_window.MainWindow()
    except tkinter.TclError as e:
        pytest.skip(f"no display: {e}")
    window.withdraw()
    stubs = Stubs()
    monkeypatch.setattr(widgets, "ask_open_file", lambda d: stubs.open.pop(0))
    monkeypatch.setattr(widgets, "ask_save_file",
                        lambda name, d: stubs.save.pop(0) if stubs.save else None)
    monkeypatch.setattr(widgets, "ask_output_dir",
                        lambda d: stubs.folder.pop(0) if stubs.folder else None)
    monkeypatch.setattr(widgets, "log_dir", lambda: stubs.logs)
    for kind in ("showinfo", "showerror", "showwarning"):
        monkeypatch.setattr(tkinter.messagebox, kind,
                            lambda kind=kind.removeprefix("show"), **k:
                            stubs.messages.append((kind, k["message"])))
    monkeypatch.setattr(tkinter.messagebox, "askyesno",
                        lambda **k: stubs.messages.append(("ask", k["message"]))
                        or stubs.answer_yes)
    yield window, stubs
    window.destroy()
    # Collect the Tk variables of this window now, in the main thread: collected later from
    # the next test's worker thread, their __del__ would call Tcl from the wrong thread.
    gc.collect()


def _load(window, stubs, path):
    stubs.open.append(Path(path))
    window.file_selector._select_file()


def _analyze(window, timeout=20.0):
    window.process_button._run_analysis()
    start = time.monotonic()
    while window.process_button.is_busy():
        assert time.monotonic() - start < timeout, "analysis did not finish"
        window.update()
        time.sleep(0.02)
    window.update()


def _save(window):
    window.results._save()
    window.update()


def test_loading_a_score_lists_its_parts(app, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    parts = window.parts
    assert [str(r.check["text"]) for r in parts.rows] == [
        "Flauto (P1)", "Piano (P2)", "Chitarra classica 1 (P3)", "Chitarra classica 2 (P4)"]
    assert [p.part_id for p in parts.selected_parts()] == ["P3", "P4"]
    assert parts.status_text.get() == "2 of 4 parts are guitars"
    assert all(r.tuning.get() == "E4 B3 G3 D3 A2 E2" and r.frets.get() == "19"
               for r in parts.rows)


def test_files_opened_from_the_system_are_loaded(app, test01_path, test_poli_path):
    # macOS: a score dropped on the app icon arrives through ::tk::mac::OpenDocument
    window, _ = app
    window.open_documents(str(test_poli_path), str(test01_path))
    assert window.file_selector.get_filepath() == str(test_poli_path)
    window.open_documents()
    assert window.file_selector.get_filepath() == str(test_poli_path)


def test_unreadable_file_is_refused_at_loading(app, tmp_path, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    bad = tmp_path / "bad.xml"
    bad.write_text("hello")
    _load(window, stubs, bad)
    assert stubs.messages[-1][0] == "ask" and "bad.xml" in stubs.messages[-1][1]
    assert window.file_selector.get_filepath() is None
    assert window.parts.rows == []


def test_presets_and_custom_tuning(app, test01_path):
    window, stubs = app
    _load(window, stubs, test01_path)
    row = window.parts.rows[0]
    row.preset.set("Drop D")
    row._on_preset()
    assert row.tuning.get() == "E4 B3 G3 D3 A2 D2"
    row.tuning.set("E4 B3 G3 D3 A2 E2")                       # typed: the preset follows
    assert row.preset.get() == "Standard"
    row.tuning.set("E4 B3 G3 D3 A2 C2")
    assert row.preset.get() == "Custom" and row.error.get() == ""
    row.tuning.set("E4 B3 X3")
    assert row.error.get().startswith("invalid")
    row.analyze.set(False)
    row._on_toggle()                                          # an unticked part is not checked
    assert row.error.get() == "" and str(row.tuning_entry["state"]) == "disabled"


def test_tuning_written_in_the_score_is_offered(app, write_score):
    from conftest import attributes, make_score, note
    window, stubs = app
    details = ("<staff-details><staff-lines>6</staff-lines>" + "".join(
        f'<staff-tuning line="{line}"><tuning-step>{step}</tuning-step>'
        f"<tuning-octave>{octave}</tuning-octave></staff-tuning>"
        for line, (step, octave) in enumerate(
            [("D", 2), ("A", 2), ("D", 3), ("G", 3), ("B", 3), ("E", 4)], start=1))
        + "</staff-details>")
    xml = make_score(measures=[attributes().replace("</attributes>", details + "</attributes>")
                               + note("D", 2, 4)])
    _load(window, stubs, write_score(xml))
    row = window.parts.rows[0]
    assert row.preset.get() == "From score" and row.tuning.get() == "E4 B3 G3 D3 A2 D2"


def test_analysis_shows_the_problems(app, tmp_path):
    from conftest import FIXTURES_DIR
    from core import AnalysisConfig, analyze, problem_points
    window, stubs = app
    path = FIXTURES_DIR / "test_ISPOG.mxl"
    _load(window, stubs, path)
    _analyze(window)
    expected = problem_points(analyze(AnalysisConfig(path, tuning=STANDARD)).reports[0])
    results = window.results
    assert [p.title for p in results.points] == [p.title for p in expected]
    assert len(results.tree.get_children()) == len(expected)
    assert results.notebook.tab(0, "text") == f"Problems ({len(expected)})"
    assert "Chitarra classica: 57 notes" in results.summary_text.get()
    results.select(1)
    details = results.details.get("1.0", "end")
    assert expected[1].title in details and expected[1].reason in details
    assert "Playability report" in results.report.get("1.0", "end")
    assert stubs.messages == []                               # nothing saved, no dialog


def test_full_score(app, tmp_path, test_poli_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test_poli_path)
    _analyze(window)
    assert str(window.results.save_button["state"]) == "normal"
    stubs.save.append(tmp_path / "out_ispog.musicxml")
    _save(window)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "logs", "out_ispog.musicxml", "out_ispog_report.txt"]
    assert window.results.saved_text.get() == "Saved: out_ispog.musicxml, out_ispog_report.txt"
    assert stubs.messages == []


def test_each_part_with_its_instrument(app, tmp_path, test_poli_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test_poli_path)
    window.parts.row("P4").set_settings(("E4", "B3", "G3", "D3", "A2", "D2"), 12)
    _analyze(window)
    config = window.process_button.last_config
    assert config.settings_for("P3").tuning == STANDARD
    assert config.settings_for("P4").tuning[-1] == "D2"
    assert config.settings_for("P4").num_frets == 12
    report = window.results.report.get("1.0", "end")
    assert "Tuning:  per part" in report
    assert "Tuning:  E4 B3 G3 D3 A2 D2 · 12 frets" in report


def test_settings_changed_after_the_analysis(app, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    _analyze(window)
    assert not window.results.stale
    window.parts.row("P3").frets.set("12")
    assert window.results.stale
    _analyze(window)
    assert not window.results.stale


def test_invalid_settings_are_named(app, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    window.parts.row("P4").tuning.set("E4 B3 G3")
    window.process_button._run_analysis()
    kind, message = stubs.messages[-1]
    assert kind == "warning" and message.startswith("Chitarra classica 2: invalid number of strings")
    assert window.process_button.last_result is None


def test_separate_parts_and_overwrite(app, tmp_path, test_poli_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test_poli_path)
    window.options.output_mode.set("split")
    _analyze(window)
    stubs.folder.append(tmp_path)
    _save(window)
    expected = ["test_poli_Chitarra_classica_1_ispog.musicxml",
                "test_poli_Chitarra_classica_2_ispog.musicxml", "test_poli_ispog_report.txt"]
    assert sorted(p.name for p in tmp_path.glob("test_poli*")) == expected
    before = {p: p.stat().st_mtime_ns for p in tmp_path.glob("test_poli*")}

    stubs.answer_yes = False
    stubs.folder.append(tmp_path)
    _save(window)
    assert stubs.messages[-1][0] == "ask"
    assert {p: p.stat().st_mtime_ns for p in tmp_path.glob("test_poli*")} == before


def test_options_reach_the_analysis(app, tmp_path, write_score):
    from conftest import attributes, make_score, note
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    path = write_score(make_score(measures=[attributes() + note("E", 6, 4)]))
    _load(window, stubs, path)
    window.options.labels.set(False)
    window.parts.rows[0].frets.set("24")
    _analyze(window)
    stubs.save.append(tmp_path / "out.musicxml")
    _save(window)
    report = (tmp_path / "out_report.txt").read_text(encoding="utf-8")
    assert "· 24 frets" in report and "No difficult or unplayable passages." in report
    assert b"ispog-label" not in (tmp_path / "out.musicxml").read_bytes()


def test_nothing_selected(app, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    for row in window.parts.rows:
        row.analyze.set(False)
    window.process_button._run_analysis()
    assert stubs.messages[-1] == ("warning", "Select at least one part to analyze")


def test_cancelled_save_writes_nothing(app, tmp_path, test01_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test01_path)
    _analyze(window)
    _save(window)                                       # no answer queued: dialog cancelled
    assert list(tmp_path.iterdir()) == []
    assert stubs.messages == [] and window.results.saved_text.get() == "Not saved yet"


def test_a_new_score_clears_the_results(app, test01_path, test_poli_path):
    window, stubs = app
    _load(window, stubs, test01_path)
    _analyze(window)
    _load(window, stubs, test_poli_path)
    assert window.results.points == [] and str(window.results.save_button["state"]) == "disabled"


def test_window_is_resizable_with_a_minimum(app, tmp_path, test_poli_path):
    from config.settings import WINDOW_MIN_SIZE
    window, stubs = app
    window.deiconify()
    window.update()
    assert window.resizable() == (True, True)
    assert window.minsize() == WINDOW_MIN_SIZE
    long_name = tmp_path / ("a very long score name for a guitar quartet " * 3 + ".musicxml")
    long_name.write_bytes(test_poli_path.read_bytes())
    _load(window, stubs, long_name)
    assert window.file_selector.status_text.get().count("…") == 1


def test_many_parts_scroll(app, write_score):
    from conftest import PartSpec, attributes, make_score, note
    window, stubs = app
    parts = [PartSpec(measures=[attributes() + note("E", 3, 4)], part_id=f"P{i}",
                      name=f"Guitar {i}") for i in range(1, 9)]
    _load(window, stubs, write_score(make_score(parts=parts)))
    window.update()
    assert len(window.parts.rows) == 8
    assert window.parts.scrollbar.winfo_manager() == "grid"            # shown


def test_dropped_paths(app):
    from gui.dnd import dropped_paths
    window, _ = app
    assert dropped_paths(window, "{C:/My Scores/a b.mxl} C:/c.xml") == [
        Path("C:/My Scores/a b.mxl"), Path("C:/c.xml")]
    assert dropped_paths(window, "") == []


def test_drop_is_enabled_when_tkinterdnd2_is_installed(app):
    window, _ = app
    status = window.file_selector.status_text.get()
    try:
        import tkinterdnd2  # noqa: F401
    except ImportError:
        assert not window.file_selector.drop_enabled and status == "No file loaded"
    else:
        assert window.file_selector.drop_enabled
        assert status == "No file loaded: browse or drop a score"


# ---------------------------------------------------------------------------
# Bug reports
# ---------------------------------------------------------------------------

@pytest.fixture
def reports(app, monkeypatch):
    """Record what the report dialog would send, open in the browser, or show."""
    from gui import report_dialog
    sent, opened = [], []
    monkeypatch.setattr(report_dialog, "webbrowser",
                        type("Browser", (), {"open": staticmethod(opened.append)}))
    monkeypatch.setattr(report_dialog, "open_folder", lambda folder: opened.append(folder))
    return sent, opened


def _wait_closed(window, dialog, timeout=10.0):
    start = time.monotonic()
    while dialog.winfo_exists():
        assert time.monotonic() - start < timeout, "report dialog still open"
        window.update()
        time.sleep(0.02)


def test_report_without_analysis(app, reports, test01_path):
    window, stubs = app
    _load(window, stubs, test01_path)
    dialog = window.open_report()
    content = dialog.final_content()
    assert content.summary == "User report" and content.analysis_files == {}
    assert content.score_file is None                             # score is opt-in
    assert content.context["score"] == "Test01.musicxml"
    assert content.context["selected"] == ["P1"]
    dialog.destroy()


def test_report_after_analysis_sends_what_the_tester_chose(app, reports, tmp_path,
                                                           test01_path):
    window, stubs = app
    sent, _ = reports
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test01_path)
    _analyze(window)
    stubs.save.append(tmp_path / "out.musicxml")
    _save(window)

    dialog = window.open_report()
    dialog._sender = sent.append
    assert dialog.include_analysis.get() is True
    dialog.include_analysis.set(False)
    assert dialog.final_content().analysis_files == {}
    dialog.include_analysis.set(True)
    dialog.include_score.set(True)
    dialog.email.set("tester@example.org")
    dialog.comment.insert("1.0", "Measure 1 should be playable")
    dialog._send()
    _wait_closed(window, dialog)

    (content,) = sent
    assert content.email == "tester@example.org"
    assert content.comment == "Measure 1 should be playable"
    assert content.score_file == test01_path
    assert set(content.analysis_files) == {"Test01_ispog.musicxml", "Test01_ispog_report.txt"}
    assert stubs.messages[-1] == ("info", "Report sent. Thank you!")


def test_failed_report_offers_an_email(app, reports, test01_path):
    from core.errors import ReportNotSentError
    window, stubs = app
    _, opened = reports
    _load(window, stubs, test01_path)
    dialog = window.open_report()

    def fail(content):
        raise ReportNotSentError("No connection to the report service (offline).")

    dialog._sender = fail
    stubs.answer_yes = True                                        # "Open an e-mail?" -> yes
    dialog._send()
    _wait_closed(window, dialog)
    assert stubs.messages[-1][0] == "ask" and "offline" in stubs.messages[-1][1]
    assert opened[0].startswith("mailto:") and isinstance(opened[1], Path)


def test_refused_file_offers_a_report(app, reports, tmp_path, monkeypatch):
    window, stubs = app
    opened = []
    monkeypatch.setattr(window, "open_report", lambda **k: opened.append(k))
    bad = tmp_path / "bad.xml"
    bad.write_text("hello")

    stubs.answer_yes = False                                       # "Send a report?" -> no
    _load(window, stubs, bad)
    assert opened == [] and "Send a report" in stubs.messages[-1][1]

    stubs.answer_yes = True
    _load(window, stubs, bad)
    (call,) = opened
    assert "bad.xml" in call["summary"] and "UnsupportedFileError" in call["error"]


def test_analysis_of_another_score_is_not_offered(app, reports, tmp_path, test01_path,
                                                  test_poli_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test01_path)
    _analyze(window)
    _load(window, stubs, test_poli_path)                          # a different score now
    dialog = window.open_report()
    assert dialog.final_content().analysis_files == {}
    assert dialog.include_analysis.get() is False
    dialog.destroy()
