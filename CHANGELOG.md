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
- MusicXML reader based on lxml (`core/reader.py`, `core/model.py`): `.musicxml`, `.xml`
  and `.mxl` recognized from the content, UTF-16 files, timewise scores (converted with the
  official MusicXML 4.0 stylesheet), multi-part scores with guitar detection, exact onsets
  from `<backup>`, `<forward>`, `<chord/>` and changing `<divisions>`, transposing
  instruments, TAB staves doubling the notation skipped. Not yet used by the analysis.
- MIDI-based fretboard (`core/fretboard.py`) and playability engine (`core/playability.py`):
  notes are fingered onset by onset, with the notes still sounding as constraints, for any
  number of voices. Not yet used by the application.
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff`, `README.md`.

### Changed
- Playability engine (effective once the application uses it):
  - a tied note is no longer analyzed again where the tie ends: it keeps the color of the
    note that starts the tie and holds its string for the whole tied duration;
  - positions at the edge of the neck follow the real pitch: no fret beyond the last one;
    flats on the last fret and altered open strings (e.g. F#1) are found;
  - voices beyond the fourth are analyzed;
  - every colored note records why (e.g. "fret span 6 (max 4)", "7 notes on 6 strings",
    "C2 out of range (below the lowest string E2)").
- Notes in a chord are ordered by sounding pitch, sharps and flats included (0.9 ignored
  them): the fingering chosen can change, and with it the constraints on later notes.
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
