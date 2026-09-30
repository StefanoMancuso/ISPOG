# -*- coding: utf-8 -*-
"""
ISPOG - Self-test of the desktop app

    ISPOG --self-test [report.json]          (executable)
    python main.py --self-test [report.json]

Checks, without showing any window, that everything the executable bundles works: the
analysis of a small score (plain, compressed and timewise, so lxml, zip and the bundled
XSLT), writing, the log folder, the CA certificates for bug reports, Tk and drag and drop.
The release workflow runs it on every executable before publishing (plan, F7): an
executable that cannot start or misses a component is not released.

Exit code 0 if every check passes, 1 otherwise. The report (JSON) says which check failed
and why; it is written to a file because a windowed executable has no console.
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

STANDARD = ('E4', 'B3', 'G3', 'D3', 'A2', 'E2')

_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'
_PARTS = ('<part-list><score-part id="P1"><part-name>Guitar</part-name>'
          '<score-instrument id="P1-I1"><instrument-name>Guitar</instrument-name>'
          '<instrument-sound>pluck.guitar</instrument-sound></score-instrument>'
          '</score-part></part-list>')
_ATTRIBUTES = ('<attributes><divisions>1</divisions><time><beats>4</beats>'
               '<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line>'
               '<clef-octave-change>-1</clef-octave-change></clef></attributes>')


def _note(step: str, octave: int, chord: bool = False) -> str:
    return (f'<note>{"<chord/>" if chord else ""}<pitch><step>{step}</step>'
            f'<octave>{octave}</octave></pitch><duration>4</duration><voice>1</voice>'
            '<type>whole</type></note>')


# Measure 1: one playable note. Measure 2: seven notes at once, more than six strings.
_MEASURES = (_ATTRIBUTES + _note('E', 4),
             ''.join(_note(step, 3, chord=i > 0) for i, step in enumerate('CDEFGAB')))

PARTWISE = (_HEAD + '<score-partwise version="4.0">' + _PARTS + '<part id="P1">'
            + ''.join(f'<measure number="{i + 1}">{m}</measure>' for i, m in enumerate(_MEASURES))
            + '</part></score-partwise>')
TIMEWISE = (_HEAD + '<score-timewise version="4.0">' + _PARTS
            + ''.join(f'<measure number="{i + 1}"><part id="P1">{m}</part></measure>'
                      for i, m in enumerate(_MEASURES))
            + '</score-timewise>')
MXL_CONTAINER = ('<?xml version="1.0" encoding="UTF-8"?><container><rootfiles>'
                 '<rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/>'
                 '</rootfiles></container>')
EXPECTED_COUNTS = {'green': 1, 'red': 7}


# ---------------------------------------------------------------------------
# Checks: each returns a short detail, or raises
# ---------------------------------------------------------------------------

def check_analysis(folder: Path) -> str:
    from core import AnalysisConfig, analyze, render_report

    plain = folder / 'selftest.musicxml'
    plain.write_text(PARTWISE, encoding='utf-8')
    result = analyze(AnalysisConfig(plain, tuning=STANDARD))
    counts = result.reports[0].counts
    found = {color: counts[color] for color in EXPECTED_COUNTS}
    if found != EXPECTED_COUNTS:
        raise AssertionError(f'colors {found}, expected {EXPECTED_COUNTS}')
    output = folder / 'selftest_ispog.musicxml'
    output.write_bytes(result.outputs['full'])
    if b'#CF0000' not in output.read_bytes():
        raise AssertionError('no red notehead in the output')
    render_report(result)
    return f'{found}'


def check_compressed(folder: Path) -> str:
    from core import list_parts, load_score

    path = folder / 'selftest.mxl'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('mimetype', 'application/vnd.recordare.musicxml')
        archive.writestr('META-INF/container.xml', MXL_CONTAINER)
        archive.writestr('score.xml', PARTWISE)
    parts = list_parts(load_score(path))
    return f'{len(parts)} part'


def check_timewise(folder: Path) -> str:
    from core import load_score

    path = folder / 'selftest_timewise.musicxml'
    path.write_text(TIMEWISE, encoding='utf-8')
    root = load_score(path).getroot()
    if root.tag != 'score-partwise':
        raise AssertionError(f'converted to <{root.tag}>')
    return 'converted with resources/timepart.xsl'


def check_log_folder(folder: Path) -> str:
    from utils import log_dir

    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / '.selftest'
    probe.write_text('ok', encoding='utf-8')
    probe.unlink()
    return str(directory)


def check_certificates(folder: Path) -> str:
    from core.bugreport import _ssl_context

    context = _ssl_context()
    count = len(context.get_ca_certs()) or context.cert_store_stats().get('x509_ca', 0)
    if not count:
        raise AssertionError('no CA certificates')
    return f'{count} CA certificates'


def check_window(folder: Path, require_drop: bool) -> str:
    """Tk starts and, in the executable, drag and drop loads (tkDnD native library)."""
    import tkinter as tk
    from tkinter import ttk

    from .dnd import enable_file_drop

    root = tk.Tk()
    try:
        root.withdraw()
        frame = ttk.Frame(root)
        frame.pack()
        drop = enable_file_drop([frame], on_drop=lambda path: None)
        if require_drop and not drop:
            raise AssertionError('drag and drop not available (see the log)')
        version = root.tk.call('info', 'patchlevel')
    finally:
        root.destroy()
    return f'Tk {version}, drag and drop {"on" if drop else "off"}'


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_self_test(report_path: Optional[Path] = None,
                  require_drop: Optional[bool] = None) -> int:
    """
    Run every check, write the JSON report (if ``report_path``), return the exit code.
    ``require_drop`` defaults to True in the executable: there tkinterdnd2 must be bundled.
    """
    from config.version import __version__
    from utils import is_frozen

    if require_drop is None:
        require_drop = is_frozen()
    checks: dict[str, Callable[[Path], str]] = {
        'analysis': check_analysis,
        'compressed': check_compressed,
        'timewise': check_timewise,
        'log_folder': check_log_folder,
        'certificates': check_certificates,
        'window': lambda folder: check_window(folder, require_drop),
    }
    results = {}
    with tempfile.TemporaryDirectory(prefix='ispog-selftest-') as tmp:
        for name, check in checks.items():
            try:
                results[name] = {'ok': True, 'detail': check(Path(tmp))}
            except Exception as e:                      # every failure goes in the report
                logger.error('Self-test %s failed', name, exc_info=True)
                results[name] = {'ok': False, 'detail': f'{type(e).__name__}: {e}',
                                 'traceback': traceback.format_exc()}
    passed = all(r['ok'] for r in results.values())
    report = {'ispog': __version__, 'frozen': is_frozen(), 'platform': sys.platform,
              'passed': passed, 'checks': results}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if report_path is not None:
        report_path.write_text(text, encoding='utf-8')
    if sys.stdout is not None:                          # None in a windowed executable
        print(text)
    logger.info('Self-test %s', 'passed' if passed else 'FAILED')
    return 0 if passed else 1
