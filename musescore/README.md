# ISPOG for MuseScore Studio

The ISPOG playability analysis inside MuseScore Studio (4.6 or later): the guitar parts
of the open score are checked on request, and every notehead is colored as in the
desktop app.

| color | meaning |
|---|---|
| green | playable (can be hidden) |
| orange | difficult (stretch, pinky barré, crossed fingers) |
| red | unplayable |
| purple | playable only as one note (a unison re-attacked while it still sounds) |

## Install

1. Download `ISPOG-<version>-musescore.zip` from the releases and unzip it, or take the
   folder `ISPOG` of this directory. Copy the folder `ISPOG` (with `ispog.qml` and
   `ispog_engine.js`) to
   `Documents\MuseScore4\Plugins\` (macOS/Linux: `~/Documents/MuseScore4/Plugins/`).
   Remove the folder of the proof of concept (`ISPOG_PoC`) if you installed it.
2. Restart MuseScore, then Home → Plugins → enable **ISPOG**.
3. Open a score, then Plugins → Color notes → **ISPOG**.

## Use

- **Parts**: every guitar part is found and ticked. Each part has its own tuning
  (string 1 first, e.g. `E4 B3 G3 D3 A2 E2`; presets: Instrument, Standard, Drop D,
  Open G) and number of frets (12–24). *Instrument* is the tuning of the part in
  MuseScore (Staff/Part properties → String data). Other parts can be ticked by hand and
  analyzed as a guitar with the tuning you give.
- **Analyze**: analyzes the ticked parts of the whole score. Nothing is analyzed when the
  dialog opens or when a setting changes (the dialog says the colors are out of date):
  on a large score an analysis takes seconds and MuseScore waits for it.
- **Selected measures**: analyzes only the notes attacked in the selected range (click a
  measure, Shift+click another), much faster; notes still sounding from before the range
  are not taken into account, nothing changes outside it.
- **Problems**: difficult, unplayable and not-as-written points, in score order, with the
  reason. Click one to select its notes in the score. **Report**: the same text report as
  the desktop app (summary, points, closest fingering `string/fret:finger`).
- **Save settings**: stores tuning, frets and options in the score (saved with it).
- **Clear colors**: removes the ISPOG colors.

Every coloring is one undoable step (Edit → Undo).

## Limits

- No automatic check while you write: MuseScore does not notify plugins of score changes
  and cannot run them in the background, so a check after every edit blocked MuseScore on
  large scores. An analysis takes about 1 s per 500 chords.
- Analysis colors overwrite the color of the notes of the ticked parts; **Clear colors**
  resets ISPOG colors to black (other colors are kept).
- Not read from the score (the desktop app reads them from MusicXML): string numbers and
  fingerings written on the notes, used to tell two unisons apart; capo. Microtonal notes
  (tuning ≥ 25 cents) are not analyzed.
- Note names are sounding pitches, as in the MusicXML exported by MuseScore.

## How it works

```
ISPOG/ispog.qml         MuseScore plugin: reads the notes (cursor), settings, colors, UI
ISPOG/ispog_engine.js   playability engine: JavaScript port of core/
tests/                  parity and plugin tests (not needed to use the plugin)
```

The Python core (`../core`) is the reference implementation. The engine is a
line-by-line port of `fretboard.py`, `stretch.py` (the table `finger_stretch.csv` is
embedded), `fingering.py`, `analyzer.py`, `unison.py`, `playability.py` and the report
blocks of `report.py`, with the same arithmetic and the same orderings, so that it gives
the same results. Rules change in Python first; then the change is ported and the tests
below must pass again.

## Tests

From the root of the repository (Python 3.11+, Node 18+); GitHub runs them at every push
(`.github/workflows/tests.yml`, job `musescore`):

```bash
pip install -e ".[dev]" PySide6-Essentials
python musescore/tests/make_fixtures.py       # Python core -> musescore/tests/fixtures/*.json
node   musescore/tests/run_tests.js           # engine in Node: same results as Python
python musescore/tests/run_tests_qt.py        # engine in the Qt JavaScript engine (MuseScore's)
python musescore/tests/run_plugin_tests.py    # ispog.qml with a test double of MuseScore
```

- `make_fixtures.py` runs the Python core on the test scores of `tests/fixtures`,
  on synthetic scores (ties, grace notes, held notes, unisons, notes left out) and on 400
  random passages (chords, several voices, ties, grace notes, doublings, tunings, necks),
  and saves notes and results. The fixtures are generated: regenerate them after every
  change to the core.
- `run_tests.js` / `run_tests_qt.py` compare color, string/fret, finger and reason of
  every note, every fingered onset, the report blocks and the summaries. The Qt runner
  freezes the built-in objects as QML does.
- `run_plugin_tests.py` loads the plugin offscreen against `tests/plugin` (a test double
  of the MuseScore 4.7 plugin API) and checks colors against the Python core, per-part
  tunings, the problem list, selection, saved settings, an edited note, Selected measures,
  disabling a part and Clear colors. It does not replace a check in MuseScore.

## Version

The plugin has the version of ISPOG (`config/version.py`): `scripts/release.py` writes it
in `ispog.qml` and `ispog_engine.js`, and every release attaches the plugin as
`ISPOG-<version>-musescore.zip`.

## License

GNU GPL v3.0 or later, as ISPOG (`../LICENSE`). © 2026 Stefano Mancuso.
