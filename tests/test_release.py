"""
scripts/release.py: release commit, tag check, release notes, Hugging Face upload (plan, F7).

Every test works on a copy of CHANGELOG.md, CITATION.cff and config/version.py.
"""

import datetime as dt
import importlib.util
import shutil
import sys
import types

import pytest

from utils.io import PROJECT_ROOT

_spec = importlib.util.spec_from_file_location("release", PROJECT_ROOT / "scripts" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)

DATE = dt.date(2026, 10, 5)

CHANGELOG = """\
# Changelog

## [Unreleased]

### Added
- Web version.

## [0.9.1] - 2026-02-23

First public alpha.

[Unreleased]: https://github.com/StefanoMancuso/ISPOG/compare/v0.9.1...HEAD
[0.9.1]: https://github.com/StefanoMancuso/ISPOG/releases/tag/v0.9.1
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "version.py").write_text(
        '"""Single source of the version."""\n\n__version__ = "0.10.0b1.dev0"\n',
        encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    shutil.copy(PROJECT_ROOT / "CITATION.cff", tmp_path / "CITATION.cff")
    return tmp_path


def test_real_repository_version_is_readable():
    from config.version import __version__
    assert release.read_version() == __version__


def test_prepare_makes_the_release_commit(repo):
    release.prepare("0.10.0b1", DATE, repo)
    assert release.read_version(repo) == "0.10.0b1"
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("## [Unreleased]") < text.index("## [0.10.0b1] - 2026-10-05") < text.index(
        "### Added")
    assert ("[Unreleased]: https://github.com/StefanoMancuso/ISPOG/compare/v0.10.0b1...HEAD\n"
            "[0.10.0b1]: https://github.com/StefanoMancuso/ISPOG/compare/v0.9.1...v0.10.0b1\n"
            "[0.9.1]:") in text
    citation = (repo / "CITATION.cff").read_text(encoding="utf-8")
    assert "\nversion: 0.10.0b1\n" in citation and "\ndate-released: 2026-10-05\n" in citation
    assert "preferred-citation:" in citation                      # the rest is untouched
    assert release.check("v0.10.0b1", repo) == {"version": "0.10.0b1", "prerelease": "true"}


def test_notes_are_the_changelog_section(repo):
    release.prepare("0.10.0b1", DATE, repo)
    assert release.changelog_section("0.10.0b1", repo) == "### Added\n- Web version.\n"
    assert release.changelog_section("0.9.1", repo) == "First public alpha.\n"


def test_start_dev_reopens_development(repo):
    release.prepare("0.10.0b1", DATE, repo)
    release.start_dev("0.10.0b2", repo)
    assert release.read_version(repo) == "0.10.0b2.dev0"
    with pytest.raises(release.ReleaseError, match="not a release version"):
        release.start_dev("0.10.0b2.dev0", repo)


@pytest.mark.parametrize("version, tag, message", [
    ("0.10.0b1.dev0", "v0.10.0b1.dev0", "not a release version"),
    ("0.10.0b1", "v0.10.0", "does not match"),
    ("0.10.0b1", "0.10.0b1", "does not match"),
])
def test_check_refuses_a_wrong_tag_or_a_development_version(repo, version, tag, message):
    (repo / "config" / "version.py").write_text(f'__version__ = "{version}"\n')
    with pytest.raises(release.ReleaseError, match=message):
        release.check(tag, repo)


def test_check_needs_the_changelog_section(repo):
    (repo / "config" / "version.py").write_text('__version__ = "0.10.0b1"\n')
    with pytest.raises(release.ReleaseError, match=r"no '## \[0.10.0b1\]"):
        release.check("v0.10.0b1", repo)


def test_prepare_refuses_a_version_that_is_not_the_one_in_development(repo):
    with pytest.raises(release.ReleaseError, match="0.10.0b2.devN"):
        release.prepare("0.10.0b2", DATE, repo)
    assert release.read_version(repo) == "0.10.0b1.dev0"


@pytest.mark.parametrize("version, prerelease, folder", [
    ("0.10.0b1", True, "beta"), ("0.10.0rc1", True, "beta"), ("0.10.0a2", True, "beta"),
    ("0.10.0", False, ""), ("1.0.0", False, ""),
])
def test_prereleases_go_to_the_beta_folder(version, prerelease, folder):
    assert release.is_prerelease(version) is prerelease
    assert release.hf_folder(version) == folder


def test_upload_hf(tmp_path, monkeypatch):
    calls = []

    class FakeApi:
        def upload_folder(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(HfApi=FakeApi))
    for name in ("ISPOG-0.10.0b1-windows.exe", "ISPOG-0.10.0b1-macos-arm64.zip", "notes.md"):
        (tmp_path / name).write_bytes(b"x")
    release.upload_hf(tmp_path, "0.10.0b1")
    (call,) = calls
    assert call["repo_id"] == release.HF_REPO and call["path_in_repo"] == "beta"
    assert call["allow_patterns"] == ["ISPOG-0.10.0b1-macos-arm64.zip",
                                      "ISPOG-0.10.0b1-windows.exe"]
    assert call["delete_patterns"] == ["ISPOG-*"]
    with pytest.raises(release.ReleaseError, match="no ISPOG-0.10.0-"):
        release.upload_hf(tmp_path, "0.10.0")


def test_command_line(repo, monkeypatch, capsys):
    monkeypatch.setattr(release, "ROOT", repo)
    assert release.main(["version"]) == 0                    # dry run: no checks
    assert capsys.readouterr().out == "version=0.10.0b1.dev0\nprerelease=false\n"
    assert release.main(["check", "v0.10.0b1.dev0"]) == 1
    assert "not a release version" in capsys.readouterr().err

    assert release.main(["prepare", "0.10.0b1", "--date", "2026-10-05"]) == 0
    capsys.readouterr()
    assert release.main(["check", "v0.10.0b1"]) == 0
    assert capsys.readouterr().out == "version=0.10.0b1\nprerelease=true\n"
    assert release.main(["notes", "0.10.0b1"]) == 0
    assert capsys.readouterr().out == "### Added\n- Web version.\n"
    assert release.main(["start-dev", "0.10.0b2"]) == 0
    assert release.read_version(repo) == "0.10.0b2.dev0"
