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
  instruments, TAB staves doubling the notation skipped.
- MIDI-based fretboard (`core/fretboard.py`) and playability engine (`core/playability.py`):
  notes are fingered onset by onset, with the notes still sounding as constraints, for any
  number of voices.
- MusicXML writer (`core/writer.py`): noteheads colored in place, schema-valid; credit
  "Analyzed by ISPOG <version>" at the bottom of page 1, replacing earlier ISPOG credits;
  single-part copies of a score; UTF-8 output keeping the original DOCTYPE and layout.
- Labels in the score: a short italic text (e.g. "span 6", "5 fingers", "no free string")
  above every difficult or unplayable point, in the color of the point. Replaced, not
  duplicated, when an analyzed score is analyzed again.
- Playability report saved next to the score (`<name>_report.txt`): summary per part, then
  only the difficult and unplayable points with measure, beat, notes, held notes, reason
  and closest fingering found, then the notes that were not analyzed and why.
- Summary after the analysis: notes, difficult and unplayable per part, with the measures
  containing unplayable notes.
- Technical note list per part (`logs/<name>_<part>_notes.tsv`), for bug reports.
- Multi-part scores: guitar parts are detected and analyzed; the other parts are left
  untouched (part selection in the window comes in a later beta).
- `.xml` files can be opened.
- Output validated against the MusicXML 4.0 schema in the test suite.
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff`, `README.md`.

### Changed
- The analysis runs on the new reader, engine and writer; the 0.9 string-based pipeline
  is removed.
- The save dialog opens after the analysis, from the main window; cancelling it no
  longer loses the analysis silently. The analysis thread no longer touches the window.
- Error messages say what is wrong with the file instead of "Analysis failed".
- Playability engine:
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

### Fixed
- `.mxl` files exported by MuseScore 4 (score stored as `score.xml`) were rejected with
  "No .musicxml file found in .mxl archive".
- The "Analyzed by ISPOG" credit was never written (0.9 defined it but did not call it);
  the new writer adds it with the version.
- Colored scores were not valid MusicXML: colors were written in lower-case hex (the schema
  requires upper case) and, when a note had no notehead, the new `<notehead>` was placed
  after `<notations>`. Colors are now upper case; the placement is fixed by the new writer.
- Analyzing an already analyzed score kept the old colors; the new writer overwrites them.

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
