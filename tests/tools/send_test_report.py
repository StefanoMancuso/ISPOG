# -*- coding: utf-8 -*-
"""
Send a test bug report to the real endpoint (config/settings.py, BUGREPORT_URL).

Checks the whole chain: this computer → Apps Script → e-mail with the zip attached.
From the repository root:
    python tests/tools/send_test_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config.settings import BUGREPORT_URL  # noqa: E402
from core.bugreport import ReportContent, send  # noqa: E402
from core.errors import ReportNotSentError  # noqa: E402
from utils.io import log_dir  # noqa: E402


def main() -> int:
    logs = sorted(log_dir().glob("ispog_*.log"))
    content = ReportContent(
        summary="Test report",
        comment="Sent by tests/tools/send_test_report.py to check the report chain.",
        context={"test": True},
        log_file=logs[-1] if logs else None,
    )
    print(f"Sending to {BUGREPORT_URL} ...")
    try:
        send(content)
    except ReportNotSentError as e:
        print(f"NOT SENT: {e}")
        return 1
    print("Sent: check Gmail, label 'ISPOG reports', subject '[ISPOG report] ... Test report'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
