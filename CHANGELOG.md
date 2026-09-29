# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [PEP 440](https://peps.python.org/pep-0440/) (`0.10.0b1` = first beta of 0.10.0).

## [Unreleased]

### Added
- `pyproject.toml`: project metadata, dependencies (`lxml`), extras `web`, `dev`, `build`,
  ruff and pytest configuration.
- Single version source `config/version.py`, shown in the window title.
- Continuous integration: ruff and pytest on Linux (Python 3.11–3.13) at every push;
  Windows and macOS at release tags.
- Test suite scaffolding: metadata and architecture checks (`tests/test_meta.py`),
  synthetic MusicXML builder, pre-refactor baseline of `Test01`.
- Typed errors for the core (`core/errors.py`).
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff`, `README.md`.

### Changed
- License: GNU GPL v3.0 or later. Version 0.9.1 remains under the terms it was
  released with.
- Bundled resources, logs and reports are located from the project folder, no longer
  from the folder ISPOG is launched from.

### Removed
- macOS build at every push to `main` (it ran without tests). Executables will be built
  by the release workflow from version tags.

## [0.9.1] - 2026-02-23

First public alpha: desktop builds for Windows and macOS on Hugging Face and web
version at <https://ispog.onrender.com>.

### Added
- Analysis of `.musicxml` and `.mxl` scores; noteheads colored green (playable),
  orange (difficult), red (unplayable).
- Tunings: Standard, Drop D, Open G and custom; 4–8 strings; configurable number of frets.

[Unreleased]: https://github.com/StefanoMancuso/ISPOG/compare/v0.9.1...HEAD
[0.9.1]: https://github.com/StefanoMancuso/ISPOG/releases/tag/v0.9.1
