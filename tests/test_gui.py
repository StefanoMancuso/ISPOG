"""
gui.widgets: the parts of the analysis flow that need no window (plan, F5).
Skipped where Tkinter is not installed.
"""

import pytest

pytest.importorskip("tkinter")

from core.errors import NoGuitarPartError  # noqa: E402
from core.processor import AnalysisConfig, analyze  # noqa: E402
from gui.widgets import ProcessButton  # noqa: E402

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")


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
