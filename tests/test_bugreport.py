"""
core.bugreport: content, privacy and delivery of bug reports (plan, F6b).

Delivery is tested against a local server that behaves like the Apps Script endpoint:
the POST is answered with a redirect, and the JSON result is served to the GET that
follows it. No request leaves the machine.
"""

import base64
import io
import json
import threading
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from core import bugreport
from core.bugreport import (ReportContent, build_payload, build_zip, mailto_url,
                            read_log_tail, sanitize, send)
from core.errors import ReportNotSentError

HOME = Path("/home/tester")


def _zip_members(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: HOME))
    path = tmp_path / "ispog.log"
    path.write_text("\n".join(f"line {i}: loaded {HOME}/Desktop/score{i}.mxl" for i in range(200)),
                    encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Content and privacy
# ---------------------------------------------------------------------------

def test_sanitize_hides_the_home_folder():
    assert sanitize("/home/tester/Desktop/a.mxl", HOME) == "~/Desktop/a.mxl"
    windows = Path("C:/Users/stefa")
    assert sanitize("File C:/Users/stefa/Desktop/a.mxl", windows) == "File ~/Desktop/a.mxl"
    assert sanitize("nothing personal", HOME) == "nothing personal"


def test_zip_contains_log_and_system_info(log_file):
    content = ReportContent(summary="Crash", error="Traceback: /home/tester/x.py",
                            context={"score": "a.mxl", "tuning": ["E4"]}, log_file=log_file)
    members = _zip_members(build_zip(content))
    assert set(members) == {"system.json", "error.txt", "ispog.log"}
    info = json.loads(members["system.json"])
    assert info["summary"] == "Crash" and info["context"]["score"] == "a.mxl"
    assert set(info["system"]) >= {"ispog", "os", "python", "lxml"}
    assert b"/home/tester" not in members["ispog.log"] + members["error.txt"]
    assert b"~/Desktop/score199.mxl" in members["ispog.log"]


def test_score_and_analysis_only_when_given(log_file, tmp_path):
    score = tmp_path / "piece.musicxml"
    score.write_bytes(b"<score-partwise/>")
    content = ReportContent(summary="False red", log_file=log_file, score_file=score,
                            analysis_files={"piece_ispog.musicxml": b"<x/>",
                                            "piece_ispog_report.txt": b"report"})
    members = _zip_members(build_zip(content))
    assert members["score/piece.musicxml"] == b"<score-partwise/>"
    assert members["analysis/piece_ispog_report.txt"] == b"report"
    plain = _zip_members(build_zip(ReportContent(summary="x", log_file=log_file)))
    assert not any(name.startswith(("score/", "analysis/")) for name in plain)


def test_only_the_end_of_a_long_log_is_sent(log_file):
    tail = read_log_tail(log_file, max_bytes=100)
    assert len(tail.encode()) <= 100 and tail.endswith("score199.mxl")
    assert read_log_tail(None) == "" and read_log_tail(log_file.with_name("missing")) == ""


def test_too_large_report(log_file, monkeypatch):
    monkeypatch.setattr(bugreport, "BUGREPORT_MAX_BYTES", 10)
    with pytest.raises(ReportNotSentError, match="without the score"):
        build_zip(ReportContent(summary="x", log_file=log_file))


def test_payload(log_file):
    content = ReportContent(summary="Crash in /home/tester/a", email=" me@example.org ",
                            comment=" measure 12 ", log_file=log_file)
    payload = json.loads(build_payload(content, token="t0k"))
    assert payload["token"] == "t0k"
    assert payload["summary"] == "Crash in ~/a"
    assert (payload["email"], payload["comment"]) == ("me@example.org", "measure 12")
    assert payload["filename"].startswith("ispog_report_") and payload["filename"].endswith(".zip")
    assert "ispog.log" in _zip_members(base64.b64decode(payload["zip"]))


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

class FakeEndpoint:
    """Local stand-in for the Apps Script web app."""

    def __init__(self, answer: dict | None = None, body: bytes | None = None):
        self.answer = answer or {"status": "ok"}
        self.body = body
        self.received: list[dict] = []
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                endpoint.received.append(json.loads(self.rfile.read(length)))
                self.send_response(302)                  # like script.google.com
                self.send_header("Location", "/echo")
                self.end_headers()

            def do_GET(self):
                data = endpoint.body or json.dumps(endpoint.answer).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/exec"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def endpoint():
    servers = []

    def make(**kwargs):
        server = FakeEndpoint(**kwargs)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def test_report_is_delivered(endpoint, log_file):
    server = endpoint()
    send(ReportContent(summary="Crash", log_file=log_file), url=server.url, token="t0k")
    (payload,) = server.received
    assert payload["token"] == "t0k" and payload["summary"] == "Crash"


def test_refusal_is_reported(endpoint, log_file):
    server = endpoint(answer={"status": "error", "reason": "daily limit reached"})
    with pytest.raises(ReportNotSentError, match="daily limit reached"):
        send(ReportContent(summary="x", log_file=log_file), url=server.url)


def test_unexpected_answer(endpoint, log_file):
    server = endpoint(body=b"<html>Sign in</html>")
    with pytest.raises(ReportNotSentError, match="Unexpected answer"):
        send(ReportContent(summary="x", log_file=log_file), url=server.url)


def test_no_connection(log_file):
    server = FakeEndpoint()
    url = server.url
    server.close()                                       # nothing listens any more
    with pytest.raises(ReportNotSentError, match="No connection"):
        send(ReportContent(summary="x", log_file=log_file), url=url, timeout=5)


# ---------------------------------------------------------------------------
# E-mail fallback
# ---------------------------------------------------------------------------

def test_mailto_fits_and_carries_the_essentials(log_file):
    content = ReportContent(summary="Crash", comment="Measure 12 is red",
                            error="ValueError: bad", log_file=log_file)
    link = mailto_url(content, to="dev@example.org", max_chars=1800)
    assert link.startswith("mailto:dev@example.org?") and len(link) <= 1800
    query = urllib.parse.parse_qs(link.split("?", 1)[1])
    assert query["subject"][0].startswith("[ISPOG report]")
    body = query["body"][0]
    assert "Measure 12 is red" in body and "ValueError: bad" in body
    assert "Last log lines:" in body and "/home/tester" not in body


def test_mailto_without_log(tmp_path):
    link = mailto_url(ReportContent(summary="x", comment="c" * 5000), max_chars=500)
    assert len(link) <= 500
