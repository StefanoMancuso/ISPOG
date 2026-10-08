# -*- coding: utf-8 -*-
"""
ISPOG - Release helper (plan, F7). Standard library only, except ``upload-hf``.

Before a release, on your computer:

    python scripts/release.py prepare 0.10.0b1        # version, CHANGELOG, CITATION
    ruff check . && pytest                            # then commit "Release 0.10.0b1"
    git tag -a v0.10.0b1 -m "..." && git push origin v0.10.0b1

After it:

    python scripts/release.py start-dev 0.10.0b2      # version 0.10.0b2.dev0

``prepare`` and ``start-dev`` also write the version in the MuseScore plugin
(musescore/ISPOG/ispog.qml, ispog_engine.js).

In the release workflow (.github/workflows/release.yml):

    python scripts/release.py check v0.10.0b1         # prints version=..., prerelease=...
    python scripts/release.py version                 # the same, without checks (dry run)
    python scripts/release.py notes 0.10.0b1          # CHANGELOG section, for the release page
    python scripts/release.py upload-hf dist 0.10.0b1 # executables to Hugging Face

On Hugging Face a release replaces the executables in the root and moves the previous ones
to archive/<version>/; a pre-release replaces the previous one in beta/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_URL = 'https://github.com/StefanoMancuso/ISPOG'
HF_REPO = 'StefanoMancuso88/ISPOG'
ARTIFACT_PREFIX = 'ISPOG-'
HF_ARCHIVE = 'archive'                     # earlier releases on Hugging Face: archive/<version>/
# A published executable: ISPOG-<version>-<platform>.<ext>, or ISPOG_<version>.zip (0.9.1)
_ARTIFACT = re.compile(r'^ISPOG[-_](?P<version>\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?'
                       r'(?:\.post\d+)?)(?=[-_.])')

# "## [0.10.0b1] - 2026-10-01" or "## [Unreleased]"
_SECTION = re.compile(r'^## \[(?P<name>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?[ \t]*$',
                      re.M)
_VERSION_LINE = re.compile(r'^__version__ = "(?P<version>[^"]+)"$', re.M)
# The MuseScore plugin carries the version of ISPOG: (file, line pattern, line template)
PLUGIN_VERSION_LINES = (
    ('musescore/ISPOG/ispog.qml', re.compile(r'^    version: "(?P<version>[^"]*)"$', re.M),
     '    version: "{version}"'),
    ('musescore/ISPOG/ispog_engine.js',
     re.compile(r'^var ENGINE_VERSION = "(?P<version>[^"]*)";$', re.M),
     'var ENGINE_VERSION = "{version}";'),
)
# Release versions only: 1.2.3, 1.2.3a1, 1.2.3b2, 1.2.3rc1 (no .devN, .postN, local)
_RELEASE = re.compile(r'^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$')


class ReleaseError(Exception):
    """The repository is not in the state a release needs; the message says why."""


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def read_version(root: Path = ROOT) -> str:
    match = _VERSION_LINE.search((root / 'config' / 'version.py').read_text(encoding='utf-8'))
    if not match:
        raise ReleaseError('config/version.py has no __version__ = "..." line')
    return match['version']


def is_prerelease(version: str) -> bool:
    return re.search(r'(a|b|rc)\d+$', version) is not None


def changelog_section(version: str, root: Path = ROOT) -> str:
    """Body of the CHANGELOG section of ``version``, without its heading."""
    text = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
    headings = list(_SECTION.finditer(text))
    for i, heading in enumerate(headings):
        if heading['name'] == version:
            end = headings[i + 1].start() if i + 1 < len(headings) else _links_start(text)
            return text[heading.end():end].strip() + '\n'
    raise ReleaseError(f"CHANGELOG.md has no '## [{version}] - <date>' section")


def _links_start(text: str) -> int:
    """Start of the link definitions at the end of the CHANGELOG (``[x]: url``)."""
    match = re.search(r'^\[[^\]]+\]: ', text, re.M)
    return match.start() if match else len(text)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def check(tag: str, root: Path = ROOT) -> dict[str, str]:
    """
    The tag matches the version of the commit, which is a release (no ``.devN``) with its
    CHANGELOG section. The rest (dates, CITATION) is checked by tests/test_meta.py.
    """
    version = read_version(root)
    if tag != f'v{version}':
        raise ReleaseError(f'tag {tag} does not match config/version.py (v{version})')
    if not _RELEASE.match(version):
        raise ReleaseError(f'{version} is not a release version (e.g. 0.10.0b1, 0.10.0)')
    changelog_section(version, root)
    return outputs(root)


def outputs(root: Path = ROOT) -> dict[str, str]:
    """Version of the commit, without checks: builds that publish nothing (dry run)."""
    version = read_version(root)
    return {'version': version, 'prerelease': str(is_prerelease(version)).lower()}


def prepare(version: str, date: dt.date, root: Path = ROOT) -> None:
    """Release commit: version without .devN, dated CHANGELOG section, CITATION."""
    if not _RELEASE.match(version):
        raise ReleaseError(f'{version} is not a release version (e.g. 0.10.0b1, 0.10.0)')
    current = read_version(root)
    if not current.startswith(f'{version}.dev'):
        raise ReleaseError(f'the current version is {current}, not {version}.devN')

    changelog = root / 'CHANGELOG.md'
    text = changelog.read_text(encoding='utf-8')
    released = [m['name'] for m in _SECTION.finditer(text) if m['name'] != 'Unreleased']
    previous = released[0] if released else None
    if '## [Unreleased]' not in text:
        raise ReleaseError("CHANGELOG.md has no '## [Unreleased]' section")
    text = text.replace('## [Unreleased]', f'## [Unreleased]\n\n## [{version}] - {date}', 1)
    link = (f'{REPOSITORY_URL}/compare/v{previous}...v{version}' if previous
            else f'{REPOSITORY_URL}/releases/tag/v{version}')
    text, found = re.subn(r'^\[Unreleased\]: .*$',
                          f'[Unreleased]: {REPOSITORY_URL}/compare/v{version}...HEAD\n'
                          f'[{version}]: {link}', text, count=1, flags=re.M)
    if not found:
        text = text.rstrip('\n') + (f'\n\n[Unreleased]: {REPOSITORY_URL}/compare/v{version}'
                                    f'...HEAD\n[{version}]: {link}\n')
    changelog.write_text(text, encoding='utf-8')

    citation = root / 'CITATION.cff'
    text = citation.read_text(encoding='utf-8')
    text = re.sub(r'^version: .*$', f'version: {version}', text, count=1, flags=re.M)
    text = re.sub(r'^date-released: .*$', f'date-released: {date}', text, count=1, flags=re.M)
    citation.write_text(text, encoding='utf-8')

    _write_version(version, root)


def start_dev(version: str, root: Path = ROOT) -> None:
    """After a release: the next version, as ``<version>.dev0``."""
    if not _RELEASE.match(version):
        raise ReleaseError(f'{version} is not a release version (e.g. 0.10.0b2, 0.10.0)')
    _write_version(f'{version}.dev0', root)


def _write_version(version: str, root: Path) -> None:
    """The version in config/version.py and in the MuseScore plugin (if present)."""
    path = root / 'config' / 'version.py'
    text = _VERSION_LINE.sub(f'__version__ = "{version}"', path.read_text(encoding='utf-8'))
    path.write_text(text, encoding='utf-8')
    for relative, pattern, line in PLUGIN_VERSION_LINES:
        plugin = root / relative
        if plugin.is_file():
            text, found = pattern.subn(line.format(version=version),
                                       plugin.read_text(encoding='utf-8'), count=1)
            if not found:
                raise ReleaseError(f'{relative} has no version line to update')
            plugin.write_text(text, encoding='utf-8')


def plugin_versions(root: Path = ROOT) -> dict[str, str]:
    """The version written in each file of the MuseScore plugin, by file."""
    versions = {}
    for relative, pattern, _ in PLUGIN_VERSION_LINES:
        plugin = root / relative
        if plugin.is_file():
            match = pattern.search(plugin.read_text(encoding='utf-8'))
            versions[relative] = match['version'] if match else ''
    return versions


def hf_folder(version: str) -> str:
    """Where the executables go on Hugging Face: ``beta/`` for pre-releases, else the root."""
    return 'beta' if is_prerelease(version) else ''


def artifact_version(name: str) -> str | None:
    """
    The version in the name of a published executable, None for other files:
    ``ISPOG-0.10.0-windows.exe`` -> 0.10.0; also the 0.9.1 naming, ``ISPOG_0.9.1.zip``.
    """
    match = _ARTIFACT.match(name)
    return match['version'] if match else None


def plan_hf_upload(version: str, uploads: list[str], existing: list[str]) -> dict[str, list]:
    """
    What an upload of ``version`` does in its Hugging Face folder (``hf_folder``).

    ``uploads``: names of the new files; ``existing``: paths of the files now in the folder.
    Returns ``add`` (path of each upload), ``archive`` (source, destination) and ``delete``
    (paths). The executables of other versions leave the folder: a release moves them to
    ``archive/<their version>/`` (published versions stay downloadable, e.g. for citations);
    a pre-release deletes them (``beta/`` holds only the latest beta). Files of the same
    version that are not uploaded again are deleted; other files are kept.
    """
    target = hf_folder(version)
    keep_old = not is_prerelease(version)
    plan = {'add': [_join(target, name) for name in uploads], 'archive': [], 'delete': []}
    for path in existing:
        name = path.rpartition('/')[2]
        old = artifact_version(name)
        if old is None or path != _join(target, name):
            continue                                   # not an executable of this folder
        if old != version and keep_old:
            plan['archive'].append((path, f'{HF_ARCHIVE}/{old}/{name}'))
        if path not in plan['add']:                    # same path: overwritten by the upload
            plan['delete'].append(path)
    return plan


def upload_hf(folder: Path, version: str, repo: str = HF_REPO) -> None:
    """
    Upload the executables of ``version`` (``ISPOG-<version>-*``) to Hugging Face, in the
    folder of ``hf_folder``, as ``plan_hf_upload`` says. Token: HF_TOKEN.
    Two commits: first the archive copies, then the new files with the deletions, so that a
    failure never leaves a published version only in the history.
    """
    from huggingface_hub import (CommitOperationAdd, CommitOperationCopy,
                                 CommitOperationDelete, HfApi)
    from huggingface_hub.hf_api import RepoFile

    files = sorted(folder.glob(f'{ARTIFACT_PREFIX}{version}-*'))
    if not files:
        raise ReleaseError(f'no {ARTIFACT_PREFIX}{version}-* file in {folder}')
    api = HfApi()
    target = hf_folder(version)
    existing = [entry.path for entry in api.list_repo_tree(
        repo, path_in_repo=target or None, repo_type='model') if isinstance(entry, RepoFile)]
    plan = plan_hf_upload(version, [f.name for f in files], existing)

    if plan['archive']:
        archived = sorted({dst.split('/')[1] for _, dst in plan['archive']})
        api.create_commit(
            repo_id=repo, repo_type='model',
            operations=[CommitOperationCopy(src_path_in_repo=src, path_in_repo=dst)
                        for src, dst in plan['archive']],
            commit_message=f'Archive ISPOG {", ".join(archived)}',
        )
    api.create_commit(
        repo_id=repo, repo_type='model',
        operations=[CommitOperationAdd(path_in_repo=path, path_or_fileobj=str(file))
                    for path, file in zip(plan['add'], files)]
        + [CommitOperationDelete(path_in_repo=path) for path in plan['delete']],
        commit_message=f'ISPOG {version}',
    )
    print(f'Uploaded to {repo}/{target or "(root)"}: {", ".join(f.name for f in files)}')
    for src, dst in plan['archive']:
        print(f'Archived {src} -> {dst}')


def _join(folder: str, name: str) -> str:
    return f'{folder}/{name}' if folder else name


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check').add_argument('tag')
    commands.add_parser('version')
    commands.add_parser('notes').add_argument('version')
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('version')
    prepare_parser.add_argument('--date', type=dt.date.fromisoformat, default=dt.date.today())
    commands.add_parser('start-dev').add_argument('version')
    upload = commands.add_parser('upload-hf')
    upload.add_argument('folder', type=Path)
    upload.add_argument('version')
    upload.add_argument('--repo', default=HF_REPO)
    args = parser.parse_args(argv)

    try:
        if args.command in ('check', 'version'):
            values = check(args.tag, ROOT) if args.command == 'check' else outputs(ROOT)
            for key, value in values.items():
                print(f'{key}={value}')             # GitHub Actions step outputs
        elif args.command == 'notes':
            print(changelog_section(args.version, ROOT), end='')
        elif args.command == 'prepare':
            prepare(args.version, args.date, ROOT)
            print(f'Version {args.version} ({args.date}): config/version.py, CHANGELOG.md, '
                  'CITATION.cff updated. Check them, run the tests, commit.')
        elif args.command == 'start-dev':
            start_dev(args.version, ROOT)
            print(f'Version {args.version}.dev0. Commit "Start {args.version} development".')
        elif args.command == 'upload-hf':
            upload_hf(args.folder, args.version, args.repo)
    except ReleaseError as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
