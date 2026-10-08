# -*- coding: utf-8 -*-
"""
ISPOG MuseScore plugin - tests of ispog.qml outside MuseScore.

Loads the plugin in Qt Quick (offscreen) with a test double of the MuseScore plugin API
(``plugin/MuseScore``, ``plugin/mockscore.js``) and of a score built from the fixture
scores of the Python core, then checks, as a user would see them:

- opening the dialog analyzes nothing; after Analyze every notehead has the color the
  Python core gives it (green, orange, red, purple), non-guitar parts are untouched, one
  undoable command at most, nothing written when nothing changed;
- the problem list matches the difficult and unplayable points of the Python report;
- clicking a problem selects its notes; settings are saved in the score;
- per-part tunings; a settings change only marks the results out of date; an edited note
  is checked at the next analysis; disabling a part and Clear colors remove the colors;
- "Selected measures": only the notes attacked in the range, as the Python core colors
  them on their own; nothing changes outside the range.

It does not replace a test in MuseScore: the API double follows the 4.7 headers, not
MuseScore's behavior.

    pip install PySide6-Essentials lxml
    python musescore/tests/run_plugin_tests.py

The Python core is the repository this folder is in (``ISPOG_SOFTWARE`` overrides it).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from fractions import Fraction
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = Path(__file__).resolve().parent
SOFTWARE = Path(os.environ.get('ISPOG_SOFTWARE') or HERE.parents[1])
PLUGIN = HERE.parent / 'ISPOG' / 'ispog.qml'
sys.path.insert(0, str(SOFTWARE))

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from config.settings import COLOR_CODES, TUNING_PRESETS  # noqa: E402
from core.fretboard import Fretboard, note_name_to_midi  # noqa: E402
from core.playability import analyze_notes  # noqa: E402
from core.reader import list_parts, load_score, read_part  # noqa: E402

DIVISION = 480
FIFTHS = {'F': -1, 'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5}
STANDARD = tuple(TUNING_PRESETS['standard'].get_tuning())
GUITAR_ID = 'guitar-nylon'


# ---------------------------------------------------------------------------
# Score spec from a MusicXML file, with the colors of the Python core
# ---------------------------------------------------------------------------

def expected_colors(path: Path, part_index: int, tuning, frets: int,
                    before_tick: int | None = None) -> dict[str, str]:
    """
    Colors the Python core gives the notes of one part with a tuning and a neck; with
    ``before_tick``, only the notes attacked before it, analyzed on their own.
    """
    part = list_parts(load_score(path))[part_index]
    notes = read_part(part)
    keys = {id(n): f'{part_index}:{i}' for i, n in enumerate(notes)}
    if before_tick is not None:
        notes = [n for n in notes if n.onset * DIVISION < before_tick]
    analyze_notes(notes, Fretboard(tuning, frets))
    return {keys[id(n)]: COLOR_CODES['black' if n.is_hidden else n.color]
            for n in notes if not n.is_rest and n.midi is not None}


def edited_pitch(spec: dict, key: str) -> tuple[int, int]:
    """Original (pitch, tpc1) of a note of the spec."""
    for chord in spec['chords']:
        for note in chord['notes'] + [n for g in chord['graceBefore'] for n in g['notes']]:
            if note['key'] == key:
                return note['pitch'], note['tpc1']
    raise KeyError(key)


def build_spec(path: Path) -> tuple[dict, dict, list]:
    """(spec for mockscore.js, expected color per note key, expected problem rows)."""
    spec = {'parts': [], 'chords': [], 'measures': [], 'staves': 0, 'duration': 0}
    expected: dict[str, str] = {}
    problems: list[dict] = []
    measure_starts: dict[str, Fraction] = {}
    first_staff = 0

    for part_index, part in enumerate(list_parts(load_score(path))):
        notes = read_part(part)
        for n in notes:
            measure_starts[n.measure_number] = min(measure_starts.get(n.measure_number, n.onset),
                                                   n.onset)
        if part.is_guitar:
            result = analyze_notes(notes, Fretboard(STANDARD, 19))
            for event in result.events:
                if event.analysis.playability.value != 'green':
                    first = min(event.notes, key=lambda n: n.midi)
                    problems.append({'part': part.name, 'measure': event.measure_number,
                                     'beat': first.beat_label, 'reason': event.analysis.reason})
            for note in result.unisons:
                problems.append({'part': part.name, 'measure': note.measure_number,
                                 'beat': note.beat_label, 'reason': note.reason})
        staves = max((n.staff for n in notes), default=1)
        spec['parts'].append({
            'name': part.name, 'instrumentId': GUITAR_ID if part.is_guitar else 'violin',
            'strings': sorted(note_name_to_midi(n) for n in STANDARD) if part.is_guitar else [],
            'frets': 19 if part.is_guitar else 0, 'staves': staves})

        chords: list[dict] = []
        graces: dict[tuple, list[list[dict]]] = {}
        for i, n in enumerate(notes):
            if n.is_rest or n.midi is None:
                continue
            key = f'{part_index}:{i}'
            alter = int(n.alter)
            item = {'key': key, 'pitch': n.midi, 'tpc1': 14 + FIFTHS[n.step] + 7 * alter,
                    'visible': not n.is_hidden, 'tieForward': n.tie_start, 'tieBack': n.tie_stop}
            black = n.color == 'black' or n.is_hidden or not part.is_guitar
            expected[key] = COLOR_CODES['black'] if black else COLOR_CODES[n.color]
            staff, voice = first_staff + n.staff - 1, int(n.voice) - 1
            track = (staff, voice)
            if n.is_grace:
                group = graces.setdefault(track, [])
                if n.is_chord and group:
                    group[-1].append(item)
                else:
                    group.append([item])
                continue
            if n.is_chord and chords and chords[-1]['_track'] == track:
                chords[-1]['notes'].append(item)
                continue
            chords.append({'_track': track, 'staff': staff, 'voice': voice,
                           'tick': int(n.onset * DIVISION), 'duration': int(n.duration * DIVISION),
                           'notes': [item],
                           'graceBefore': [{'notes': g} for g in graces.pop(track, [])]})
        for chord in chords:
            del chord['_track']
            spec['duration'] = max(spec['duration'], chord['tick'] + chord['duration'])
        spec['chords'] += chords
        first_staff += staves

    spec['staves'] = first_staff
    spec['measures'] = [{'no': int(number) - 1, 'start': int(start * DIVISION), 'beatType': 4}
                        for number, start in sorted(measure_starts.items(), key=lambda m: m[1])]
    return spec, expected, problems


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class PluginTest:
    def __init__(self, engine: QQmlApplicationEngine, root):
        self.engine = engine
        self.root = root
        self.failures: list[str] = []
        self.checks = 0

    def call(self, method: str, *args) -> dict:
        from PySide6.QtCore import QMetaObject, Q_RETURN_ARG, Q_ARG
        q_args = [Q_ARG('QVariant', a) for a in args]
        value = QMetaObject.invokeMethod(self.root, method, Q_RETURN_ARG('QVariant'), *q_args)
        return json.loads(value)

    def analyze(self, selection_only: bool = False, timeout: float = 30.0) -> dict:
        """Press Analyze (or Selected measures) and wait for the analysis to end."""
        from PySide6.QtCore import QEventLoop, QTimer
        self.call('call', 'requestAnalysis', [selection_only])
        waited = 0.0
        while True:
            loop = QEventLoop()
            QTimer.singleShot(20, loop.quit)
            loop.exec()
            waited += 0.02
            state = self.call('snapshot')
            if not state['busy'] or waited > timeout:
                return state

    def check(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(message)


def run_score(test: PluginTest, path: Path) -> None:
    name = path.name
    spec, expected, expected_problems = build_spec(path)
    opened = test.call('setUp', json.dumps(spec))
    test.check(opened['startCmd'] == 0 and not opened['problems'],
               f'{name}: opening the dialog analyzed the score')

    state = test.analyze()
    wrong = {k: (state['colors'].get(k), v) for k, v in expected.items()
             if state['colors'].get(k) != v}
    test.check(not wrong, f'{name}: {len(wrong)} notes with another color than the Python core, '
                          f'e.g. {list(wrong.items())[:3]}')
    test.check(state['writesOutsideCmd'] == 0, f'{name}: colors written outside startCmd/endCmd')
    test.check(state['startCmd'] <= 1, f'{name}: {state["startCmd"]} commands for one analysis')
    test.check('Analysis failed' not in state['status'], f'{name}: {state["status"]}')

    got = sorted((p['part'], p['measure'], p['beat'], p['reason']) for p in state['problems'])
    want = sorted((p['part'], p['measure'], p['beat'], p['reason']) for p in expected_problems)
    test.check(got == want, f'{name}: problems differ\n  got  {got}\n  want {want}')

    # analyzing again without changes writes nothing
    again = test.analyze()
    test.check(again['startCmd'] == state['startCmd'], f'{name}: re-analysis wrote unchanged colors')

    if state['problems']:
        selected = test.call('call', 'selectProblem', [0])
        test.check(bool(selected['selection']) and selected['shown'] == selected['selection'][0],
                   f'{name}: clicking a problem does not select its notes')

    # settings in the score
    saved = test.call('call', 'saveSettings', [])
    settings = json.loads(saved['metaTags'].get('ispogSettings', '{}'))
    test.check(settings.get('version') == 1 and len(settings.get('parts', {})) == len(spec['parts']),
               f'{name}: settings not saved: {saved["metaTags"]}')

    guitars = [p for p in spec['parts'] if p['instrumentId'] == GUITAR_ID]
    if not guitars:
        return

    # every part with its own settings: a guitar in Drop D on 12 frets, a non-guitar part
    # enabled by hand in standard tuning; a change only marks the results out of date
    custom = {spec['parts'].index(guitars[-1]): (tuple(TUNING_PRESETS['drop_d'].get_tuning()), 12)}
    others = [i for i, p in enumerate(spec['parts']) if p['instrumentId'] != GUITAR_ID]
    if others:
        custom[others[0]] = (STANDARD, 19)
    before = saved
    for index, (tuning, frets) in custom.items():
        changed = test.call('setPart', index, True, ' '.join(tuning), frets)
        test.check(changed['stale'] and changed['startCmd'] == before['startCmd'],
                   f'{name}: a settings change analyzed at once')
    state = test.analyze()
    test.check(not state['stale'], f'{name}: results still marked out of date')
    for index, (tuning, frets) in custom.items():
        want = expected_colors(path, index, tuning, frets)
        wrong = {k: (state['colors'][k], v) for k, v in want.items() if state['colors'][k] != v}
        test.check(not wrong, f'{name}: part {index} with {" ".join(tuning)}, {frets} frets: '
                              f'{len(wrong)} notes differ, e.g. {list(wrong.items())[:3]}')
    if others:
        test.call('setPart', others[0], False, ' '.join(STANDARD), 19)

    # an edited note is checked at the next analysis, in one undoable command
    key = next(k for k, v in state['colors'].items()
               if expected[k] != COLOR_CODES['black']
               and v not in (COLOR_CODES['black'], COLOR_CODES['red']))
    test.call('editNote', key, 30, 18)                    # F#1, below the lowest string
    edited = test.analyze()
    test.check(edited['colors'][key] == COLOR_CODES['red'],
               f'{name}: edited note {key} is {edited["colors"][key]}, expected red')
    test.check(edited['startCmd'] == state['startCmd'] + 1, f'{name}: edit not applied in one command')

    # disabling a guitar part removes its colors at the next analysis
    first = guitars[0]['name']
    test.call('toggle', first)
    disabled = test.analyze()
    part_keys = [k for k in expected if k.startswith(f"{spec['parts'].index(guitars[0])}:")]
    left = [k for k in part_keys if disabled['colors'][k] != COLOR_CODES['black']]
    test.check(not left, f'{name}: {len(left)} notes still colored after disabling {first}')
    test.call('toggle', first)

    # Clear colors
    cleared = test.call('call', 'clearColors', [])
    left = [k for k, v in cleared['colors'].items() if v != COLOR_CODES['black']]
    test.check(not left, f'{name}: {len(left)} notes still colored after Clear colors')

    # selected measures only: the notes attacked in measure 1, analyzed on their own
    test.call('editNote', key, *edited_pitch(spec, key))  # restore the edited note
    measures = spec['measures']
    end = measures[1]['start'] if len(measures) > 1 else spec['duration'] + 1
    test.call('selectRange', 0, end)
    ranged = test.analyze(selection_only=True)
    test.check('Selected measures only' in ranged['status'], f'{name}: {ranged["status"]}')
    for index, part in enumerate(spec['parts']):
        if part['instrumentId'] != GUITAR_ID:
            continue
        tuning, frets = custom.get(index, (STANDARD, 19))
        want = expected_colors(path, index, tuning, frets, before_tick=end)
        wrong = {k: (ranged['colors'][k], v) for k, v in want.items() if ranged['colors'][k] != v}
        test.check(not wrong, f'{name}: part {index}, measure 1 only: {len(wrong)} notes differ, '
                              f'e.g. {list(wrong.items())[:3]}')
        outside = [k for k in ranged['colors'] if k.startswith(f'{index}:') and k not in want
                   and ranged['colors'][k] != COLOR_CODES['black']]
        test.check(not outside, f'{name}: part {index}: {len(outside)} notes colored outside the range')


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841
    fixtures = sorted(p for p in (SOFTWARE / 'tests' / 'fixtures').glob('*')
                      if p.suffix.lower() in ('.musicxml', '.xml', '.mxl'))
    failures = checks = 0
    for path in fixtures:
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(HERE / 'plugin'))
        messages: list[str] = []
        engine.warnings.connect(lambda warnings: messages.extend(w.toString() for w in warnings))
        engine.setInitialProperties({'pluginUrl': QUrl.fromLocalFile(str(PLUGIN))})
        engine.load(QUrl.fromLocalFile(str(HERE / 'plugin' / 'PluginTest.qml')))
        if not engine.rootObjects():
            print('FAIL cannot load the test window:\n  ' + '\n  '.join(messages))
            return 1
        test = PluginTest(engine, engine.rootObjects()[0])
        try:
            run_score(test, path)
        except Exception:
            test.failures.append(f'{path.name}: {traceback.format_exc()}')
        plugin_warnings = [m for m in messages if 'ispog' in m.lower()]
        test.check(not plugin_warnings, f'{path.name}: QML warnings\n  ' + '\n  '.join(plugin_warnings))
        for failure in test.failures:
            print(f'FAIL {failure}')
        print(f'{path.name}: {test.checks - len(test.failures)}/{test.checks} checks passed')
        failures += len(test.failures)
        checks += test.checks
        engine.deleteLater()
    print(f'{failures} of {checks} checks FAILED' if failures else f'all {checks} checks passed')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
