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


@pytest.mark.parametrize("name, version", [
    ("ISPOG-0.10.0-windows.exe", "0.10.0"), ("ISPOG-0.10.0b2-macos-arm64.zip", "0.10.0b2"),
    ("ISPOG-1.0.0rc1-musescore.zip", "1.0.0rc1"), ("ISPOG_0.9.1.zip", "0.9.1"),
    ("README.md", None), (".gitattributes", None), ("ISPOG.zip", None), ("ISPOG-notes.md", None),
])
def test_artifact_version(name, version):
    assert release.artifact_version(name) == version


ROOT_FILES = [".gitattributes", "README.md", "ISPOG_0.9.1.zip"]
NEW = ["ISPOG-1.0.0-macos-arm64.zip", "ISPOG-1.0.0-windows.exe"]


def test_a_release_archives_the_previous_ones():
    existing = ROOT_FILES + ["ISPOG-0.10.0-windows.exe", "ISPOG-0.10.0-macos-arm64.zip"]
    plan = release.plan_hf_upload("1.0.0", NEW, existing)
    assert plan["add"] == NEW
    assert plan["archive"] == [
        ("ISPOG_0.9.1.zip", "archive/0.9.1/ISPOG_0.9.1.zip"),
        ("ISPOG-0.10.0-windows.exe", "archive/0.10.0/ISPOG-0.10.0-windows.exe"),
        ("ISPOG-0.10.0-macos-arm64.zip", "archive/0.10.0/ISPOG-0.10.0-macos-arm64.zip"),
    ]
    assert plan["delete"] == ["ISPOG_0.9.1.zip", "ISPOG-0.10.0-windows.exe",
                              "ISPOG-0.10.0-macos-arm64.zip"]


def test_a_prerelease_replaces_the_previous_beta():
    existing = ["beta/ISPOG-0.10.0b2-windows.exe", "beta/notes.md"]
    plan = release.plan_hf_upload("1.0.0b1", ["ISPOG-1.0.0b1-windows.exe"], existing)
    assert plan == {"add": ["beta/ISPOG-1.0.0b1-windows.exe"], "archive": [],
                    "delete": ["beta/ISPOG-0.10.0b2-windows.exe"]}


def test_uploading_a_version_again_replaces_its_files():
    existing = ROOT_FILES[:2] + NEW + ["ISPOG-1.0.0-linux.zip"]
    plan = release.plan_hf_upload("1.0.0", NEW, existing)
    assert plan == {"add": NEW, "archive": [], "delete": ["ISPOG-1.0.0-linux.zip"]}


def test_upload_hf(tmp_path, monkeypatch):
    commits = []

    class RepoFile(types.SimpleNamespace):
        pass

    class FakeApi:
        def list_repo_tree(self, repo_id, path_in_repo=None, repo_type=None):
            assert (repo_id, path_in_repo, repo_type) == (release.HF_REPO, None, "model")
            return [RepoFile(path=path) for path in ROOT_FILES] + [types.SimpleNamespace(path="beta")]

        def create_commit(self, **kwargs):
            commits.append(kwargs)

    def operation(kind):
        return lambda **kwargs: (kind, kwargs)

    hub = types.SimpleNamespace(HfApi=FakeApi, CommitOperationAdd=operation("add"),
                                CommitOperationCopy=operation("copy"),
                                CommitOperationDelete=operation("delete"))
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.hf_api", types.SimpleNamespace(RepoFile=RepoFile))
    for name in NEW + ["notes.md"]:
        (tmp_path / name).write_bytes(b"x")
    release.upload_hf(tmp_path, "1.0.0")

    archive, upload = commits
    assert archive["commit_message"] == "Archive ISPOG 0.9.1"
    assert archive["operations"] == [("copy", {"src_path_in_repo": "ISPOG_0.9.1.zip",
                                               "path_in_repo": "archive/0.9.1/ISPOG_0.9.1.zip"})]
    assert upload["repo_id"] == release.HF_REPO and upload["commit_message"] == "ISPOG 1.0.0"
    assert upload["operations"] == [
        ("add", {"path_in_repo": name, "path_or_fileobj": str(tmp_path / name)}) for name in NEW
    ] + [("delete", {"path_in_repo": "ISPOG_0.9.1.zip"})]
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


def test_plugin_carries_the_version(repo):
    plugin = repo / "musescore" / "ISPOG"
    plugin.mkdir(parents=True)
    (plugin / "ispog.qml").write_text('MuseScore {\n    version: "0.1.0"\n}\n', encoding="utf-8")
    (plugin / "ispog_engine.js").write_text('var ENGINE_VERSION = "0.1.0";\n', encoding="utf-8")
    release.start_dev("1.0.0b1", repo)
    assert set(release.plugin_versions(repo).values()) == {"1.0.0b1.dev0"}
    assert '    version: "1.0.0b1.dev0"\n' in (plugin / "ispog.qml").read_text(encoding="utf-8")


def test_real_plugin_has_the_version_of_ispog():
    from config.version import __version__
    versions = release.plugin_versions()
    assert versions and set(versions.values()) == {__version__}
