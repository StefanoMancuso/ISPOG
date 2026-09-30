"""
gui.selftest: the check run on every executable before a release (plan, F7).

The window check needs a display (locally, or ``xvfb-run`` in CI).
"""

import json
import subprocess
import sys

import pytest
from lxml import etree

from gui import selftest
from utils.io import PROJECT_ROOT

tkinter = pytest.importorskip("tkinter")


def _display_available() -> bool:
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError:
        return False
    return True


needs_display = pytest.mark.skipif(not _display_available(), reason="no display")


@pytest.mark.parametrize("xml", [selftest.PARTWISE, selftest.TIMEWISE],
                         ids=["partwise", "timewise"])
def test_embedded_scores_are_valid_musicxml(xml, musicxml_schema):
    tree = etree.ElementTree(etree.fromstring(xml.encode("utf-8")))
    assert musicxml_schema.validate(tree), musicxml_schema.error_log


@needs_display
def test_self_test_passes(tmp_path):
    report = tmp_path / "report.json"
    assert selftest.run_self_test(report, require_drop=True) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["passed"] is True
    assert set(data["checks"]) == {"analysis", "compressed", "timewise", "log_folder",
                                   "certificates", "window"}
    assert "drag and drop on" in data["checks"]["window"]["detail"]


@needs_display
def test_a_failed_check_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(selftest, "EXPECTED_COUNTS", {"green": 8, "red": 0})
    report = tmp_path / "report.json"
    assert selftest.run_self_test(report) == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["passed"] is False
    analysis = data["checks"]["analysis"]
    assert analysis["ok"] is False and "expected" in analysis["detail"]
    assert data["checks"]["timewise"]["ok"] is True          # the other checks still run


@needs_display
def test_missing_drag_and_drop_fails_only_when_required(tmp_path, monkeypatch):
    from gui import dnd
    monkeypatch.setattr(dnd, "TkinterDnD", None)
    assert selftest.run_self_test(tmp_path / "a.json", require_drop=False) == 0
    assert selftest.run_self_test(tmp_path / "b.json", require_drop=True) == 1


@needs_display
def test_command_line(tmp_path):
    report = tmp_path / "report.json"
    result = subprocess.run([sys.executable, "main.py", "--self-test", str(report)],
                            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(report.read_text(encoding="utf-8"))["passed"] is True


def test_command_line_never_raises(monkeypatch):
    # a windowed executable would show an error dialog and hang the release build
    import main

    def crash(*args, **kwargs):
        raise RuntimeError("broken bundle")
    monkeypatch.setattr(selftest, "run_self_test", crash)
    assert main.self_test([]) == 1
