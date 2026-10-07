# ISPOG - Is it Playable on Guitar?

ISPOG checks whether a score can be played on the guitar. It reads a MusicXML file,
finds string and fret positions for every note, fingers simultaneous and held notes
together, and returns the score with each notehead colored:

| color | meaning |
|---|---|
| green | playable |
| orange | difficult (e.g. pinky barré, wide stretch, crossed fingers) |
| red | unplayable |
| purple | playable only as one note: a unison re-attacked while the other voice still holds it |

Unisons across voices: two voices writing the same pitch at the same time are read as one
note written twice, unless the score marks them as two (different string numbers, different
spelling such as E4/F♭4, or different fingerings on both). Hidden notes are ignored.

Each note gets a string, a fret and a finger of the fretting hand; held notes keep theirs.
How far two fingers can stretch, per pair of fingers and strings, is set in
`config/finger_stretch.csv` and can be edited in a spreadsheet (format in `core/stretch.py`).

Current release: **0.9.1** (alpha). Version 0.10 (in development) moves to a real XML
parser, analyzes multi-part scores and adds a readable report. See the
[CHANGELOG](CHANGELOG.md).

## Download

- Desktop (Windows, macOS): <https://huggingface.co/StefanoMancuso88/ISPOG>
- Web version: <https://ispog.onrender.com>

| System | File |
|---|---|
| Windows 10/11 | `ISPOG-<version>-windows.exe` |
| macOS, Apple Silicon (M1 and later) | `ISPOG-<version>-macos-arm64.zip` |
| macOS, Intel | `ISPOG-<version>-macos-x86_64.zip` |

Beta versions are in the `beta` folder. No installation and no Python needed: on Windows
run the `.exe`; on macOS unzip and move `ISPOG.app` to Applications.

### First launch

The executables are not digitally signed, so the system asks for one extra confirmation
the first time:

- **Windows** (SmartScreen, "Windows protected your PC"): "More info" → "Run anyway".
- **macOS** ("ISPOG can't be opened" or "Apple could not verify…"): close the message, open
  System Settings → Privacy & Security, scroll down, "Open Anyway", then confirm.

### Security scan warning on Hugging Face

Hugging Face may mark the macOS `.zip` files as "unsafe" (scanner: Protect AI). This is a
false positive (under review with Hugging Face): PyInstaller bundles pack the Python libraries, including `pickle`-related
modules, and the scanner flags them inside the archive. The files are built from this
repository by the release workflow (`.github/workflows/release.yml`), and each executable
passes `ISPOG --self-test` before publishing. To verify a download, compare its SHA-256
with the one shown on the file's page on Hugging Face.

A score can be opened with the Browse button, dropped on the window, or dropped on the
ISPOG icon (the program file on Windows, the app or its Dock icon on macOS).

## Input

MusicXML (`.musicxml`, `.xml`) and compressed MusicXML (`.mxl`), exported from any
notation program (MuseScore, Sibelius, Finale, Dorico, Guitar Pro).

## Reporting a problem

"Help → Report a problem…", or the button offered with an error, sends a report to the
developer. Nothing is sent until you press **Send**. The report always contains the log
file (with your user folder replaced by `~`) and system information (ISPOG, operating system
and Python versions, tuning and parts chosen). The last analysis (colored score and report)
is included unless you untick it; your score only if you tick "Include score file". Your
e-mail is optional. If the report cannot be sent, ISPOG offers to open an e-mail instead.

## Development

Requires Python 3.11+.

```bash
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -e ".[dev]"          # core, desktop app (with drag and drop), pytest, ruff
pip install -e ".[dev,web]"      # + web version (Gradio)
python main.py                   # desktop app
python app.py                    # web version, http://127.0.0.1:7860
```

Always install with `-e`: resources and logs are located from the source folder.

Before every push:

```bash
ruff check .
pytest
```

GitHub runs the same checks at every push to `main`. Web tests (`tests/test_web.py`) run only
where Gradio is installed: `pytest -m web`.

Real scores from many editors go in `tests/corpus/` (not versioned: they may be
copyrighted). `pytest -m corpus -v` checks them; `python tests/tools/corpus_run.py` writes
the analyzed scores and reports to `tests/corpus/_output/` for a visual check.

## Versioning

[PEP 440](https://peps.python.org/pep-0440/): `0.10.0b1` is the first beta of 0.10.0.
The version lives in one place, `config/version.py`; between releases it carries a
`.devN` suffix. Every analyzed score records the ISPOG version that produced it.

### Releasing

```bash
python scripts/release.py prepare 0.10.0b1     # version, CHANGELOG and CITATION for the release
ruff check . && pytest                         # commit "Release 0.10.0b1", push
git tag -a v0.10.0b1 -m "Beta 1" && git push origin v0.10.0b1
python scripts/release.py start-dev 0.10.0b2   # commit "Start 0.10.0b2 development"
```

The tag starts `.github/workflows/release.yml`: tests, executables for Windows and macOS
(each checked with `ISPOG --self-test` before publishing), GitHub release, upload to
Hugging Face, deploy of the web version. Secrets: `HF_TOKEN`, `RENDER_DEPLOY_HOOK`.
To build locally: `pip install -e ".[build]"`, then `pyinstaller --noconfirm ISPOG.spec`.

## Related publications

- Crecchi N., Mancuso S. (2026). *Dealing with a Guitar's Historical Limit through
  Computer-Assisted Composition*. In *Sounding the Posthuman: Proceedings of the 25th
  Colloquium on Music Informatics*, L'Aquila. Forthcoming.

## Citing

If you use ISPOG in research, please cite it as described in
[CITATION.cff](CITATION.cff).

## License

© 2026 Stefano Mancuso — [GNU GPL v3.0 or later](LICENSE).
Third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Version 0.9.1 remains under the terms it was released with.
