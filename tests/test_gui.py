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
from core.processor import AnalysisConfig, analyze  # noqa: E402
from gui import main_window, widgets  # noqa: E402
from gui.widgets import ProcessButton  # noqa: E402

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")


# ---------------------------------------------------------------------------
# Without a window
# ---------------------------------------------------------------------------

def test_part_summary(test01_path, test_poli_path):
    report = analyze(AnalysisConfig(test01_path, tuning=STANDARD)).reports[0]
    assert ProcessButton._part_summary(report) == (
        "Chitarra classica: 44 notes · 0 difficult · 8 unplayable (m. 1)")
    poli = analyze(AnalysisConfig(test_poli_path, tuning=STANDARD)).reports[0]
    assert ProcessButton._part_summary(poli).endswith("0 unplayable")


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
        self.overwrite = True
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
    monkeypatch.setattr(widgets, "writable_path", lambda rel: stubs.logs / rel)
    for kind in ("showinfo", "showerror", "showwarning"):
        monkeypatch.setattr(tkinter.messagebox, kind,
                            lambda kind=kind.removeprefix("show"), **k:
                            stubs.messages.append((kind, k["message"])))
    monkeypatch.setattr(tkinter.messagebox, "askyesno",
                        lambda **k: stubs.messages.append(("ask", k["message"]))
                        or stubs.overwrite)
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
    while str(window.process_button.run_button["state"]) == "disabled":
        assert time.monotonic() - start < timeout, "analysis did not finish"
        window.update()
        time.sleep(0.02)


def test_loading_a_score_lists_its_parts(app, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    selector = window.part_selector
    assert selector.listbox.get(0, "end") == (
        "Flauto (P1)", "Piano (P2)", "Chitarra classica 1 (P3)", "Chitarra classica 2 (P4)")
    assert [p.part_id for p in selector.selected_parts()] == ["P3", "P4"]
    assert selector.status_text.get() == "2 of 4 parts are guitars"


def test_unreadable_file_is_refused_at_loading(app, tmp_path, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    bad = tmp_path / "bad.xml"
    bad.write_text("hello")
    _load(window, stubs, bad)
    assert stubs.messages[-1][0] == "error" and "bad.xml" in stubs.messages[-1][1]
    assert window.file_selector.get_filepath() is None
    assert window.part_selector.listbox.size() == 0


def test_full_score(app, tmp_path, test_poli_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test_poli_path)
    stubs.save.append(tmp_path / "out_ispog.musicxml")
    _analyze(window)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "logs", "out_ispog.musicxml", "out_ispog_report.txt"]
    kind, message = stubs.messages[-1]
    assert kind == "info" and message.startswith("Chitarra classica 1: 28 notes")


def test_separate_parts_and_overwrite(app, tmp_path, test_poli_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test_poli_path)
    window.part_selector.output_mode.set("split")
    stubs.folder.append(tmp_path)
    _analyze(window)
    expected = ["test_poli_Chitarra_classica_1_ispog.musicxml",
                "test_poli_Chitarra_classica_2_ispog.musicxml", "test_poli_ispog_report.txt"]
    assert sorted(p.name for p in tmp_path.glob("test_poli*")) == expected
    before = {p: p.stat().st_mtime_ns for p in tmp_path.glob("test_poli*")}

    stubs.overwrite = False
    stubs.folder.append(tmp_path)
    _analyze(window)
    assert stubs.messages[-1][0] == "ask"
    assert {p: p.stat().st_mtime_ns for p in tmp_path.glob("test_poli*")} == before


def test_options_reach_the_analysis(app, tmp_path, write_score):
    from conftest import attributes, make_score, note
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    path = write_score(make_score(measures=[attributes() + note("E", 6, 4)]))
    _load(window, stubs, path)
    window.part_selector.labels.set(False)
    window.tuning_widget.num_frets.set(24)
    stubs.save.append(tmp_path / "out.musicxml")
    _analyze(window)
    report = (tmp_path / "out_report.txt").read_text(encoding="utf-8")
    assert "· 24 frets" in report and "No difficult or unplayable passages." in report
    assert b"ispog-label" not in (tmp_path / "out.musicxml").read_bytes()


def test_nothing_selected(app, test_poli_path):
    window, stubs = app
    _load(window, stubs, test_poli_path)
    window.part_selector.listbox.selection_clear(0, "end")
    window.process_button._run_analysis()
    assert stubs.messages[-1] == ("warning", "Select at least one part to analyze")


def test_cancelled_save_writes_nothing(app, tmp_path, test01_path):
    window, stubs = app
    stubs.logs = tmp_path / "logs"
    _load(window, stubs, test01_path)
    _analyze(window)                                    # no answer queued: dialog cancelled
    assert list(tmp_path.iterdir()) == []
    assert stubs.messages == []


def _size(window):
    window.update()
    return window.winfo_width(), window.winfo_height()


def test_window_fits_its_content_and_never_grows(app, tmp_path, test_poli_path):
    window, stubs = app
    window.deiconify()
    assert window.resizable() == (False, False)
    size = _size(window)
    assert size == (window.body.winfo_reqwidth(), window.body.winfo_reqheight())

    _load(window, stubs, test_poli_path)                      # parts listed
    window.tuning_widget.tuning_mode.set("custom")            # all tuning controls enabled
    window.tuning_widget._on_tuning_change()
    assert _size(window) == size
    window.process_button._set_busy(True)                     # progress bar instead of button
    assert _size(window) == size
    window.process_button._set_busy(False)

    long_name = tmp_path / ("a very long score name for a guitar quartet " * 3 + ".musicxml")
    long_name.write_bytes(test_poli_path.read_bytes())
    _load(window, stubs, long_name)
    assert window.file_selector.status_text.get().count("…") == 1
    assert _size(window) == size
    assert window.body.winfo_reqwidth() <= size[0]


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
