# -*- coding: utf-8 -*-
"""
ISPOG - Release helper (plan, F7). Standard library only, except ``upload-hf``.

Before a release, on your computer:

    python scripts/release.py prepare 0.10.0b1        # version, CHANGELOG, CITATION
    ruff check . && pytest                            # then commit "Release 0.10.0b1"
    git tag -a v0.10.0b1 -m "..." && git push origin v0.10.0b1

After it:

    python scripts/release.py start-dev 0.10.0b2      # version 0.10.0b2.dev0

In the release workflow (.github/workflows/release.yml):

    python scripts/release.py check v0.10.0b1         # prints version=..., prerelease=...
    python scripts/release.py version                 # the same, without checks (dry run)
    python scripts/release.py notes 0.10.0b1          # CHANGELOG section, for the release page
    python scripts/release.py upload-hf dist 0.10.0b1 # executables to Hugging Face
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

# "## [0.10.0b1] - 2026-10-01" or "## [Unreleased]"
_SECTION = re.compile(r'^## \[(?P<name>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?[ \t]*$',
                      re.M)
_VERSION_LINE = re.compile(r'^__version__ = "(?P<version>[^"]+)"$', re.M)
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
    path = root / 'config' / 'version.py'
    text = _VERSION_LINE.sub(f'__version__ = "{version}"', path.read_text(encoding='utf-8'))
    path.write_text(text, encoding='utf-8')


def hf_folder(version: str) -> str:
    """Where the executables go on Hugging Face: ``beta/`` for pre-releases, else the root."""
    return 'beta' if is_prerelease(version) else ''


def upload_hf(folder: Path, version: str, repo: str = HF_REPO) -> None:
    """
    Upload the executables of ``version`` (``ISPOG-<version>-*``) to Hugging Face, replacing
    those of the previous version in the same folder. Token: HF_TOKEN.
    """
    from huggingface_hub import HfApi

    files = sorted(folder.glob(f'{ARTIFACT_PREFIX}{version}-*'))
    if not files:
        raise ReleaseError(f'no {ARTIFACT_PREFIX}{version}-* file in {folder}')
    target = hf_folder(version)
    HfApi().upload_folder(
        repo_id=repo, repo_type='model', folder_path=str(folder),
        path_in_repo=target or None,
        allow_patterns=[f.name for f in files],
        delete_patterns=[f'{ARTIFACT_PREFIX}*'],       # the previous version, same folder
        commit_message=f'ISPOG {version}',
    )
    print(f'Uploaded to {repo}/{target or "(root)"}: {", ".join(f.name for f in files)}')


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
