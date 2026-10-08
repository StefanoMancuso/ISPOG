# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [PEP 440](https://peps.python.org/pep-0440/) (`0.10.0b1` = first beta of 0.10.0).

## [Unreleased]

## [1.0.0b1] - 2026-10-08

First beta of 1.0: desktop app, web version and MuseScore plugin, with one instrument per
part and the problem list.

### Added
- MuseScore Studio plugin (`musescore/`): the analysis inside MuseScore 4.6+, on request
  (whole score or selected measures), with one instrument per part, problem list (a click
  selects the notes), report and settings saved in the score. Its engine is a JavaScript
  port of the core, checked against it at every push (job `musescore`: identical colors,
  positions, fingers and reasons on the test scores and on 400 random passages). Every
  release attaches it as `ISPOG-<version>-musescore.zip`; `scripts/release.py` keeps its
  version equal to ISPOG's.
- Web version: one row per part in a table (tick, tuning, frets; a preset fills the ticked
  parts; the tuning written in the score is used when present) and the problem table, as
  in the desktop app.
- Each part has its own instrument: tuning and number of frets per part
  (`core.processor.PartSettings`, `AnalysisConfig.part_settings`). In the desktop app every
  part has one row: tick it, choose a preset (Standard, Drop D, Open G, *From score* when
  the MusicXML writes the tuning in `<staff-tuning>`, Custom) or type the tuning, string 1
  first, and set the frets; an invalid setting is shown on its row. Non-guitar parts can be
  ticked and analyzed with the tuning given.
- The report gives the tuning of every part when the parts are analyzed with different
  instruments.
- Problem list in the window after the analysis (`core.report.problem_points`): difficult,
  unplayable and not-as-written points in score order, in their color, with the short
  label; a click shows the reason, the notes, the held notes and the closest fingering.
  The full report is in a second tab.
- `PartInfo.tuning`: open strings read from `<staff-details>/<staff-tuning>`.

### Changed
- Desktop window: new look (`gui/theme.py`, the same as the MuseScore plugin), resizable
  with a minimum size; the parts list scrolls beyond four parts.
- The analysis no longer opens the save dialog: the results are shown in the window and
  "Save colored score…" saves the score (or the parts) and the report, as before. No
  summary message box: the summary is above the results. Changing a setting after the
  analysis says that the results are out of date.
- Hugging Face: a release moves the executables of the earlier releases to
  `archive/<version>/` instead of deleting them, so that every published version stays
  downloadable (`scripts/release.py upload-hf`); a beta still replaces the previous one.

### Removed
- The tuning panels shared by all parts: eight note spinboxes in the desktop app, preset,
  strings and eight note menus in the web version. `NOTE_LIST`, `STANDARD_TUNING_INDICES`,
  `DEFAULT_NUM_STRINGS` (config/settings.py).

## [0.10.0] - 2026-10-08

Stable release of 0.10.0b3, unchanged: the version tested by its users.

## [0.10.0b3] - 2026-10-07

### Added
- Unisons across voices (`core/unison.py`). Two voices writing the same pitch at the same
  time are one note written twice (graphic doubling): it is fingered once and both noteheads
  take its color. They stay two notes, on two strings, only when the score says so:
  different string numbers (`<string>`, this decides even with different fingerings),
  different spelling (E4 / F♭4), or fingerings on both notes with different numbers. Notes
  of the same voice are always distinct.
- New color **purple**, "not as written": a note re-attacking a unison that another voice
  still holds (or a new attack against a tied note) is played as one note on one string.
  The held note keeps its written end. Unplayable re-attacks stay red. Purple label
  "unison" in the score, its own section in the report, count in the summaries.
- `Note.string_mark`, `Note.fingering_mark` (read from `<technical>`), `Note.is_hidden`.

### Changed
- Hidden notes (`print-object="no"`) are ignored by the analysis: they keep the timing of
  the measure but are not fingered, colored, counted or listed as not analyzed.
- Test01 m. 1, beat 3 1/2: B2 re-plucks the B2 of the chord (purple, was red).

## [0.10.0b2] - 2026-10-04

### Added
- Fingers of the fretting hand (`core/fingering.py`): every fretted note gets a finger
  (1 index … 4 pinky) and held notes keep string, fret **and finger**. Rules: finger order
  follows the frets; on one fret the lower finger goes on the lower-pitched string, crossed
  fingers are difficult on adjacent strings and impossible otherwise; barré only with the
  index (no open string under it) or the pinky (strings 1–4, difficult).
- Finger stretch table `config/finger_stretch.csv` (`core/stretch.py`): comfortable and
  maximum distance in frets per pair of fingers and pair of strings, wider from fret 7,
  with or without a barré.
- Report: fingers in the positions (`string/fret:finger`); TSV note list: `finger` column.
- New reasons and labels: "no free finger" (the held notes keep the fingers a new note
  needs), "crossed fingers", "no hand position"; a difficulty caused only by held notes says
  "(held notes)".
- Fixture `tests/fixtures/test_ISPOG.mxl` with the cases checked by hand on the guitar.

### Changed
- The fingering of a part is chosen over all its onsets (beam search), not onset by onset:
  a chord may take a fingering that is not its own best when that leaves the hand free for
  the notes that follow. At equal counts, the unplayable point is the later one.
- Stretch: the fixed limit (span 4 difficult, 5 with open strings) is replaced by the table,
  checked for every pair of fingers.

### Fixed
- A note attacked under a held chord was marked "pinky barré" because the chord had been
  fingered without looking ahead (test_ISPOG m. 2).
- A bass note needing a finger already holding another note was marked playable
  (test_ISPOG m. 2, beat 4 1/2).

### Removed
- `ChordAnalyzer.analyze_chord` and `_analyze_fingering` (replaced by `candidates` and
  `analyze_positions`); `MAX_FRET_SPAN` in `config/settings.py`.

## [0.10.0b1] - 2026-09-30

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
- Multi-part scores: every part is listed when the score is loaded, guitars are selected;
  any part can be selected (e.g. a banjo, with its tuning set as Custom). Parts not
  selected are left untouched.
- Output as one full score or as separate parts (one file per part, in a folder), with
  a confirmation before replacing existing files.
- Options "Add labels to score" and "Number of frets" (12–24, default 19).
- Help menu: "About ISPOG" (version, license, repository, how to cite) and "Open log
  folder".
- Drag and drop: a score dropped anywhere on the window is loaded (needs the optional
  `tkinterdnd2`; without it the Browse button remains). A score passed on the command line,
  or dropped on the program icon on Windows, is loaded at start-up.
- `.xml` files can be opened.
- Bug reports: "Help → Report a problem…" and a "Send a report?" offer with every error
  send the log, system information and, if the tester agrees, the last analysis and the
  score, by e-mail to the developer through a Google Apps Script endpoint
  (`server/bugreport.gs`). Nothing is sent without a click; without network, an e-mail
  with the details is prepared instead.
- Output validated against the MusicXML 4.0 schema in the test suite.
- Corpus tests for real scores from many editors (`tests/test_corpus.py`) and a tool that
  analyzes the whole corpus for a visual check (`tests/tools/corpus_run.py`).
- Web version on the same code as the desktop app (`app.py`, Gradio 6, `render.yaml`):
  part selection, tunings including Custom, number of frets, full score or separate parts,
  labels; the same files and report as the desktop app, the report also shown on the page.
  Uploaded scores and results are deleted within an hour.
- Executables for Windows, macOS Apple Silicon and macOS Intel, built and published from
  version tags by the release workflow (GitHub release, Hugging Face, web deploy). Each
  executable is checked with `ISPOG --self-test` before it is published.
- macOS: a score dropped on the ISPOG icon (Finder or Dock) or opened with ISPOG is loaded,
  also while ISPOG is running.
- `scripts/release.py`: prepares the release commit and the next development version.
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff`, `README.md`.

### Changed
- Windows executable: no UPX compression (fewer antivirus false alarms), with version
  information in the file properties.
- Web version: it no longer has its own, older copy of the analysis, and gets the fixes of
  the desktop app (held notes, rests shifting the colors). It is deployed only with a
  release, at the same version as the desktop app. Python 3.12.
- The analysis runs on the new reader, engine and writer; the 0.9 string-based pipeline
  is removed.
- The save dialog opens after the analysis, from the main window; cancelling it no
  longer loses the analysis silently. The analysis thread no longer touches the window.
- Error messages say what is wrong with the file instead of "Analysis failed".
- A score is read as soon as it is chosen: an unreadable file is reported right away.
- Compact fixed-size window, sized to its content (about 320×540 on Linux, smaller with
  the Windows fonts): tuning in two columns of four strings, number of strings and frets
  on one row; during the analysis a progress bar takes the place of the button.
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
- Logs of the installed app: `%APPDATA%\ISPOG\logs` (Windows), `~/Library/Logs/ISPOG`
  (macOS, previously `~/ISPOG/logs`), `~/.local/state/ISPOG/logs` (Linux).

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

[Unreleased]: https://github.com/StefanoMancuso/ISPOG/compare/v1.0.0b1...HEAD
[1.0.0b1]: https://github.com/StefanoMancuso/ISPOG/compare/v0.10.0...v1.0.0b1
[0.10.0]: https://github.com/StefanoMancuso/ISPOG/compare/v0.10.0b3...v0.10.0
[0.10.0b3]: https://github.com/StefanoMancuso/ISPOG/compare/v0.10.0b2...v0.10.0b3
[0.10.0b2]: https://github.com/StefanoMancuso/ISPOG/compare/v0.10.0b1...v0.10.0b2
[0.10.0b1]: https://github.com/StefanoMancuso/ISPOG/compare/v0.9.1...v0.10.0b1
[0.9.1]: https://github.com/StefanoMancuso/ISPOG/releases/tag/v0.9.1
