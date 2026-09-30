# ISPOG - Is it Playable on Guitar?

ISPOG checks whether a score can be played on the guitar. It reads a MusicXML file,
finds string and fret positions for every note, fingers simultaneous and held notes
together, and returns the score with each notehead colored:

| color | meaning |
|---|---|
| green | playable |
| orange | difficult (e.g. pinky barré, maximum stretch) |
| red | unplayable |

Current release: **0.9.1** (alpha). Version 0.10 (in development) moves to a real XML
parser, analyzes multi-part scores and adds a readable report. See the
[CHANGELOG](CHANGELOG.md).

## Download

- Desktop (Windows, macOS): <https://huggingface.co/StefanoMancuso88/ISPOG>
- Web version: <https://ispog.onrender.com>

Builds are not digitally signed: the first launch needs one extra confirmation
(Windows: "More info" → "Run anyway"; macOS: System Settings → Privacy & Security →
"Open Anyway").

## Input

MusicXML (`.musicxml`, `.xml`) and compressed MusicXML (`.mxl`), exported from any
notation program (MuseScore, Sibelius, Finale, Dorico, Guitar Pro).

## Development

Requires Python 3.11+.

```bash
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -e ".[dev]"          # core, desktop app (with drag and drop), pytest, ruff
pip install -e ".[dev,web]"      # + web version (Gradio)
python main.py                   # desktop app
```

Always install with `-e`: resources and logs are located from the source folder.

Before every push:

```bash
ruff check .
pytest
```

GitHub runs the same checks at every push to `main`.

Real scores from many editors go in `tests/corpus/` (not versioned: they may be
copyrighted). `pytest -m corpus -v` checks them; `python tests/tools/corpus_run.py` writes
the analyzed scores and reports to `tests/corpus/_output/` for a visual check.

## Versioning

[PEP 440](https://peps.python.org/pep-0440/): `0.10.0b1` is the first beta of 0.10.0.
The version lives in one place, `config/version.py`; between releases it carries a
`.devN` suffix. Every analyzed score records the ISPOG version that produced it.

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
