"""
Project metadata and architectural boundaries.

- The version is a valid PEP 440 string, coherent with CHANGELOG.md and CITATION.cff.
- The core never loads Tkinter (plan, D6).
- Paths do not depend on the folder ISPOG is launched from (plan, D9).

Import checks run in a fresh interpreter: in this process other tests may already have
imported Tkinter or changed the working directory.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.version import InvalidVersion, Version

from config.version import __version__
from utils.io import PROJECT_ROOT

CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"
CITATION = PROJECT_ROOT / "CITATION.cff"

# "## [0.10.0b1] - 2026-10-01" or "## [Unreleased]"
_SECTION = re.compile(r"^## \[(?P<name>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$", re.M)


def _changelog_sections() -> list[tuple[str, str | None]]:
    text = CHANGELOG.read_text(encoding="utf-8")
    return [(m["name"], m["date"]) for m in _SECTION.finditer(text)]


def _released_sections() -> list[tuple[Version, str | None]]:
    return [(Version(name), date) for name, date in _changelog_sections() if name != "Unreleased"]


def _citation_field(name: str) -> str:
    text = CITATION.read_text(encoding="utf-8")
    match = re.search(rf'^{name}:\s*"?([^"\n]+?)"?\s*$', text, re.M)
    assert match, f"CITATION.cff has no top-level '{name}'"
    return match.group(1)


def _run_python(code: str, cwd: Path) -> str:
    """Run ``code`` in a new interpreter from ``cwd``; the project is importable."""
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd, env=env, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip().splitlines()[-1]


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def test_version_is_pep440():
    try:
        version = Version(__version__)
    except InvalidVersion:
        pytest.fail(f"__version__ {__version__!r} is not a valid PEP 440 version")
    assert str(version) == __version__, f"use the normalized form {str(version)!r}"


def test_changelog_has_unreleased_section_first():
    sections = _changelog_sections()
    assert sections, "CHANGELOG.md has no '## [...]' section"
    assert sections[0][0] == "Unreleased", "the first section must be '## [Unreleased]'"


def test_changelog_releases_are_dated_and_in_descending_order():
    released = _released_sections()
    assert released, "CHANGELOG.md has no released version"
    for version, date in released:
        assert date, f"section [{version}] has no date"
    versions = [v for v, _ in released]
    assert versions == sorted(versions, reverse=True), "released sections are not newest first"


def test_version_matches_changelog_and_citation():
    version = Version(__version__)
    latest, latest_date = _released_sections()[0]
    cited = Version(_citation_field("version"))

    if version.is_devrelease:
        # Between releases: the next version is in [Unreleased], CITATION still describes
        # the latest release.
        upcoming = Version(re.sub(r"\.dev\d+$", "", __version__))
        assert upcoming > latest, (
            f"development version {version} does not follow the latest release {latest}"
        )
        assert cited == latest, f"CITATION.cff version {cited} is not the latest release {latest}"
        assert _citation_field("date-released") == latest_date
    else:
        # Release commit: the version has its own dated section and CITATION matches it.
        assert latest == version, (
            f"CHANGELOG.md has no '## [{version}] - <date>' section as latest release"
        )
        assert cited == version, f"CITATION.cff version {cited} differs from {version}"
        assert _citation_field("date-released") == latest_date


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

def test_core_does_not_import_tkinter():
    probe = "import sys, core; print('tkinter' in sys.modules or 'gui' in sys.modules)"
    assert _run_python(probe, PROJECT_ROOT) == "False", "importing core loads Tkinter or gui"


def test_paths_do_not_depend_on_working_directory(tmp_path):
    probe = (
        "import json; from utils.io import resource_path, writable_path; "
        "print(json.dumps([str(resource_path('resources')), str(writable_path('logs'))]))"
    )
    from_root = json.loads(_run_python(probe, PROJECT_ROOT))
    from_elsewhere = json.loads(_run_python(probe, tmp_path))
    assert from_root == from_elsewhere
    assert Path(from_root[0]) == PROJECT_ROOT / "resources"
    assert Path(from_root[1]) == PROJECT_ROOT / "logs"
