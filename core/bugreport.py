# -*- coding: utf-8 -*-
"""
ISPOG - Bug reports
Builds the report a tester chooses to send and posts it to the report endpoint
(``server/bugreport.gs``), which e-mails it to the maintainer. No Tk here: the consent
dialog lives in ``gui/report_dialog.py``.

The zip contains the log (with the user's home folder replaced by ``~``), system
information and, only if the tester agrees, the score and the last analysis. Nothing is
sent without an explicit click (plan, F6b).
"""

from __future__ import annotations

import base64
import io
import json
import logging
import platform
import ssl
import sys
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lxml import etree

from config.settings import (BUGREPORT_EMAIL, BUGREPORT_MAX_BYTES, BUGREPORT_MAX_LOG_BYTES,
                             BUGREPORT_TIMEOUT, BUGREPORT_TOKEN, BUGREPORT_URL)
from config.version import __version__

from .errors import ReportNotSentError

logger = logging.getLogger(__name__)

MAILTO_MAX_CHARS = 1800          # mail clients truncate or refuse longer mailto: links


@dataclass
class ReportContent:
    """What the tester agreed to send."""

    summary: str                                       # one line: the error, or "User report"
    comment: str = ''
    email: str = ''
    error: str = ''                                    # message and traceback, if any
    context: dict = field(default_factory=dict)        # tuning, parts, options of the analysis
    log_file: Optional[Path] = None
    score_file: Optional[Path] = None                  # only with the tester's consent
    analysis_files: dict[str, bytes] = field(default_factory=dict)   # name -> content


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def system_info() -> dict:
    return {
        'ispog': __version__,
        'os': platform.platform(),
        'python': sys.version.split()[0],
        'lxml': '.'.join(map(str, etree.LXML_VERSION)),
        'frozen': hasattr(sys, '_MEIPASS'),
    }


def sanitize(text: str, home: Optional[Path] = None) -> str:
    """Replace the user's home folder (and so the user name) with ``~``."""
    home = home or Path.home()
    variants = {str(home), home.as_posix(), str(home).replace('\\', '/')}
    for variant in sorted(variants, key=len, reverse=True):
        if len(variant) > 1:
            text = text.replace(variant, '~')
            if sys.platform == 'win32':                # Windows paths are case-insensitive
                text = _replace_ignoring_case(text, variant, '~')
    return text


def _sanitize_values(value):
    """``sanitize`` applied to every string of a JSON-like structure."""
    if isinstance(value, str):
        return sanitize(value)
    if isinstance(value, dict):
        return {k: _sanitize_values(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_values(v) for v in value]
    return value


def _replace_ignoring_case(text: str, old: str, new: str) -> str:
    lower, target, start, parts = text.lower(), old.lower(), 0, []
    while (index := lower.find(target, start)) >= 0:
        parts += [text[start:index], new]
        start = index + len(old)
    return ''.join(parts) + text[start:]


def read_log_tail(path: Optional[Path], max_bytes: int = BUGREPORT_MAX_LOG_BYTES) -> str:
    """The end of the log file (at most ``max_bytes``), sanitized; '' if unavailable."""
    if path is None or not path.is_file():
        return ''
    with path.open('rb') as f:
        size = f.seek(0, io.SEEK_END)
        f.seek(max(0, size - max_bytes))
        data = f.read()
    return sanitize(data.decode('utf-8', errors='replace'))


def build_zip(content: ReportContent) -> bytes:
    """
    The report archive.

    Raises:
        ReportNotSentError: the archive exceeds the size the endpoint accepts.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        info = {'summary': content.summary, 'system': system_info(),
                'context': content.context,
                'created': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        archive.writestr('system.json',
                         json.dumps(_sanitize_values(info), indent=2, ensure_ascii=False))
        if content.error:
            archive.writestr('error.txt', sanitize(content.error))
        log = read_log_tail(content.log_file)
        if log:
            archive.writestr('ispog.log', log)
        if content.score_file is not None and content.score_file.is_file():
            archive.write(content.score_file, f'score/{content.score_file.name}')
        for name, data in content.analysis_files.items():
            archive.writestr(f'analysis/{name}', data)
    data = buffer.getvalue()
    if len(data) > BUGREPORT_MAX_BYTES:
        raise ReportNotSentError(
            f'The report is too large ({len(data) // 1024 // 1024} MB). '
            'Try again without the score file.')
    return data


def build_payload(content: ReportContent, token: str = BUGREPORT_TOKEN) -> bytes:
    """JSON body for the endpoint (see ``server/bugreport.gs``)."""
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return json.dumps({
        'token': token,
        'version': __version__,
        'summary': sanitize(content.summary)[:200],
        'email': content.email.strip(),
        'comment': content.comment.strip(),
        'error': sanitize(content.error)[:5000],
        'filename': f'ispog_report_{stamp}.zip',
        'zip': base64.b64encode(build_zip(content)).decode('ascii'),
    }).encode('utf-8')


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def send(content: ReportContent, url: str = BUGREPORT_URL, token: str = BUGREPORT_TOKEN,
         timeout: float = BUGREPORT_TIMEOUT) -> None:
    """
    Post the report. The Apps Script endpoint answers with a redirect to the result, which
    ``urllib`` follows with a GET, as a browser would.

    Raises:
        ReportNotSentError: no connection, timeout, or the endpoint refused the report.
    """
    request = urllib.request.Request(url, data=build_payload(content, token), method='POST',
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as reply:
            body = reply.read().decode('utf-8', errors='replace')
    except OSError as e:                     # URLError, timeouts, refused connections
        reason = getattr(e, 'reason', e)
        raise ReportNotSentError(f'No connection to the report service ({reason}).') from e
    try:
        answer = json.loads(body)
    except ValueError as e:
        raise ReportNotSentError('Unexpected answer from the report service.') from e
    if answer.get('status') != 'ok':
        raise ReportNotSentError(f"The report service refused the report ({answer.get('reason')}).")
    logger.info('Bug report sent')


def _ssl_context() -> ssl.SSLContext:
    """System certificates; certifi's where available (python.org macOS, frozen apps)."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def mailto_url(content: ReportContent, to: str = BUGREPORT_EMAIL,
               max_chars: int = MAILTO_MAX_CHARS) -> str:
    """
    Fallback when the report cannot be sent: a ``mailto:`` link with the summary, the
    comment, the error and the end of the log, within the length mail clients accept.
    The log file itself must be attached by hand.
    """
    subject = f'[ISPOG report] {__version__} - {content.summary}'[:120]
    head = '\n\n'.join(part for part in (
        content.comment.strip(),
        sanitize(content.error.strip()),
        'System: ' + json.dumps(system_info()),
        '(Please attach the log file from the folder that just opened.)',
    ) if part)
    log = read_log_tail(content.log_file, 20_000).splitlines()

    def link(body: str) -> str:
        query = urllib.parse.urlencode({'subject': subject, 'body': body},
                                       quote_via=urllib.parse.quote)
        return f'mailto:{to}?{query}'

    body = head
    for keep in range(min(len(log), 40), 0, -1):        # as many log lines as fit
        candidate = head + '\n\nLast log lines:\n' + '\n'.join(log[-keep:])
        if len(link(candidate)) <= max_chars:
            body = candidate
            break
    while len(link(body)) > max_chars and body:
        body = body[:int(len(body) * 0.9)]
    return link(body)
