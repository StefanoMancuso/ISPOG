# -*- coding: utf-8 -*-
"""
ISPOG MuseScore plugin - parity fixtures.

Runs the Python core (the reference implementation) on scores and on random note
sequences, and writes the notes it received and the results it produced to
``fixtures/*.json``. ``run_tests.js`` feeds the same notes to the JavaScript engine
(``ISPOG/ispog_engine.js``) and checks that every result is identical.

    python musescore/tests/make_fixtures.py            # from the ISPOG folder
    node musescore/tests/run_tests.js

Regenerate the fixtures after every change to the Python core, then port the change to
the engine until the tests pass again.

The Python core is the repository this folder is in (``ISPOG_SOFTWARE`` overrides it).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import tempfile
from fractions import Fraction
from math import lcm
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOFTWARE = Path(os.environ.get('ISPOG_SOFTWARE') or HERE.parents[1])
sys.path.insert(0, str(SOFTWARE))
sys.path.insert(0, str(SOFTWARE / 'tests'))

from config.settings import TUNING_PRESETS  # noqa: E402
from config.version import __version__  # noqa: E402
from core.fretboard import Fretboard, note_name_to_midi  # noqa: E402
from core.model import STEP_SEMITONES, Note, PartReport  # noqa: E402
from core.playability import analyze_notes  # noqa: E402
from core.reader import list_parts, load_score, read_part  # noqa: E402
from core.report import _event_block, render_summary  # noqa: E402

from conftest import attributes, backup, make_score, note  # noqa: E402

FIXTURES_OUT = HERE / 'fixtures'
STANDARD = tuple(TUNING_PRESETS['standard'].get_tuning())
STEPS = ('C', 'D', 'E', 'F', 'G', 'A', 'B')


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_case(name: str, notes: list[Note], tuning, frets: int) -> dict:
    """Analyze ``notes`` with the Python core and describe input and output as JSON."""
    ids = {id(n): i for i, n in enumerate(notes)}
    times = [n.onset for n in notes] + [n.duration for n in notes]
    scale = lcm(*(Fraction(t).denominator for t in times)) if times else 1

    def ticks(value: Fraction) -> int:
        result = Fraction(value) * scale
        assert result.denominator == 1
        return int(result)

    inputs = [{
        'id': ids[id(n)], 'onset': ticks(n.onset), 'duration': ticks(n.duration),
        'voice': n.voice, 'staff': n.staff, 'step': n.step,
        'alter': None if n.step is None else (int(n.alter) if n.alter.denominator == 1
                                              else float(n.alter)),
        'midi': n.midi, 'pitchName': n.pitch_name, 'measureNumber': n.measure_number,
        'beatLabel': n.beat_label, 'isRest': n.is_rest, 'isUnpitched': n.is_unpitched,
        'isChord': n.is_chord, 'isGrace': n.is_grace, 'isCue': n.is_cue,
        'isHarmonic': n.is_harmonic, 'isHidden': n.is_hidden, 'tieStart': n.tie_start,
        'tieStop': n.tie_stop, 'stringMark': n.string_mark, 'fingeringMark': n.fingering_mark,
        'reason': n.reason,
    } for n in notes]

    fretboard = Fretboard(tuning, frets)
    result = analyze_notes(notes, fretboard)
    report = PartReport(part_id='P1', name=name, notes=notes, events=result.events,
                        not_analyzed=result.not_analyzed, unisons=result.unisons)

    def ref(n: Note) -> int:
        return ids[id(n)]

    return {
        'name': name,
        'tuning': list(tuning),
        'frets': frets,
        'notes': inputs,
        'expected': {
            'notes': [{'id': ref(n), 'color': n.color, 'fret': list(n.fret), 'finger': n.finger,
                       'reason': n.reason} for n in notes],
            'events': [{
                'onset': ticks(e.onset), 'grace': e.grace,
                'notes': [ref(n) for n in e.notes], 'held': [ref(n) for n in e.held],
                'playability': e.analysis.playability.value, 'issue': e.analysis.issue,
                'reason': e.analysis.reason, 'span': e.analysis.span,
                'fingersUsed': e.analysis.fingers_used,
                'positions': [[p.string, p.fret] for p in e.analysis.positions],
                'fingers': list(e.analysis.fingers),
                'block': _event_block(e) if e.analysis.playability.value != 'green' else None,
            } for e in result.events],
            'notAnalyzed': [ref(n) for n in result.not_analyzed],
            'unisons': [ref(n) for n in result.unisons],
            'summary': render_summary(report),
        },
    }


# ---------------------------------------------------------------------------
# Cases: real scores
# ---------------------------------------------------------------------------

def score_cases() -> list[dict]:
    fixtures = SOFTWARE / 'tests' / 'fixtures'
    cases = []
    for path in sorted(fixtures.glob('*')):
        if path.suffix.lower() not in ('.musicxml', '.xml', '.mxl'):
            continue
        for part in list_parts(load_score(path)):
            notes = read_part(part)
            cases.append(export_case(f'{path.stem}:{part.part_id}', notes, STANDARD, 19))
    return cases


# ---------------------------------------------------------------------------
# Cases: synthetic scores (tests/test_playability.py)
# ---------------------------------------------------------------------------

SYNTHETIC = {
    'tie_under_held': [attributes() + note('E', 2, 4, tie=('start',)),
                       note('E', 2, 4, tie=('stop',)) + backup(4) + note('F', 2, 4, voice=2)],
    'tie_chain': [attributes() + note('A', 2, 4, tie=('start',)),
                  note('A', 2, 4, tie=('stop', 'start')),
                  note('A', 2, 2, tie=('stop',)) + note('F', 2, 2)],
    'tie_voice_change': [attributes() + note('E', 2, 4, tie=('start',), voice=1),
                         note('E', 2, 4, tie=('stop',), voice=2)],
    'tie_stop_alone': [attributes() + note('E', 2, 4, tie=('stop',))],
    'held_until_end': [attributes() + note('E', 2, 2) + note(None, None, 2) + backup(4)
                       + note('F', 2, 1, voice=2) + note(None, None, 1, voice=2)
                       + note('F', 2, 2, voice=2)],
    'grace_chord': [attributes() + note('E', 2, None, grace=True)
                    + note('B', 2, None, grace=True, chord=True)
                    + note('E', 2, 4) + note('F', 3, 4, chord=True)],
    'grace_not_held': [attributes(divisions=2) + note('F', 2, None, grace=True)
                       + note('C', 4, 1) + note('E', 2, 1)],
    'too_many_notes': [attributes() + note('E', 2, 4) + ''.join(
        note(step, octave, 4, chord=True)
        for step, octave in [('A', 2), ('D', 3), ('G', 3), ('B', 3), ('E', 4), ('A', 4)])],
    'left_out': [attributes() + note(None, None, 1) + note('E', 4, 1, alter=0.5)
                 + note('E', 5, 1, harmonic=True) + note('G', 4, 1, cue=True)],
    'unison_doubling': [attributes() + note('E', 3, 4) + backup(4) + note('E', 3, 2, voice=2)
                        + note('G', 3, 2, voice=2)],
    'unison_reattack': [attributes() + note('B', 2, 4) + backup(4) + note(None, None, 2, voice=2)
                        + note('B', 2, 2, voice=2)],
}


def synthetic_cases() -> list[dict]:
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, measures in SYNTHETIC.items():
            path = Path(tmp) / f'{name}.musicxml'
            path.write_bytes(make_score(measures=measures))
            notes = read_part(list_parts(load_score(path))[0])
            cases.append(export_case(f'synthetic:{name}', notes, STANDARD, 19))
        # out of range on a 12-fret neck
        path = Path(tmp) / 'range.musicxml'
        path.write_bytes(make_score(measures=[attributes() + note('C', 2, 2) + note('E', 6, 2)]))
        notes = read_part(list_parts(load_score(path))[0])
        cases.append(export_case('synthetic:out_of_range', notes, STANDARD, 12))
    return cases


# ---------------------------------------------------------------------------
# Cases: random note sequences
# ---------------------------------------------------------------------------

def _spelled(midi: int, rng: random.Random) -> tuple[str, int, int]:
    """A spelling of ``midi``: (step, alter, octave), sharps or flats at random."""
    options = []
    for step in STEPS:
        for alter in (-1, 0, 1):
            base = STEP_SEMITONES[step] + alter
            octave, rest = divmod(midi - base, 12)
            if rest == 0:
                options.append((step, alter, octave - 1))
    return rng.choice(options)


def _make(rng, *, onset, duration, midi, voice, measure_length, **kwargs) -> Note:
    step, alter, octave = _spelled(midi, rng)
    measure = int(onset // measure_length)
    return Note(element=None, part_id='P1', measure_number=str(measure + 1), voice=str(voice),
                staff=kwargs.pop('staff', 1), onset=onset, duration=duration,
                beat=1 + (onset - measure * measure_length), step=step, octave=octave,
                alter=Fraction(alter), midi=midi, **kwargs)


def random_case(seed: int) -> dict:
    """A short random passage: up to 3 voices, chords, ties, grace notes, unisons."""
    rng = random.Random(seed)
    preset = rng.choice(list(TUNING_PRESETS.values()))
    strings = rng.choice((6, 6, 6, 7))
    tuning = tuple(preset.notes[:strings])
    frets = rng.choice((12, 19, 19, 22, 24))
    low = min(note_name_to_midi(n) for n in tuning) - 2
    high = max(note_name_to_midi(n) for n in tuning) + frets + 2
    measure_length = Fraction(4)
    length = rng.choice((4, 8, 12)) * Fraction(1, 2)
    voices = rng.choice((1, 2, 2, 3))
    centre = rng.randint(low + 6, min(high - 6, low + 30))

    notes: list[Note] = []
    previous: dict[int, list[Note]] = {}
    for voice in range(1, voices + 1):
        t = Fraction(0)
        while t < length:
            duration = min(rng.choice((Fraction(1, 2), Fraction(1, 2), Fraction(1), Fraction(1, 4),
                                       Fraction(3, 2), Fraction(1, 3))), length - t)
            if rng.random() < 0.15:
                notes.append(Note(element=None, part_id='P1',
                                  measure_number=str(int(t // measure_length) + 1),
                                  voice=str(voice), onset=t, duration=duration,
                                  beat=1 + t % measure_length, is_rest=True))
                previous[voice] = []
                t += duration
                continue
            if rng.random() < 0.1:
                grace_midis = sorted(rng.sample(range(centre - 7, centre + 8), rng.choice((1, 1, 2))))
                for i, midi in enumerate(grace_midis):
                    notes.append(_make(rng, onset=t, duration=Fraction(0), midi=midi, voice=voice,
                                       measure_length=measure_length, is_grace=True,
                                       is_chord=i > 0))
            tied = [n for n in previous.get(voice, []) if rng.random() < 0.25]
            size = rng.choice((1, 1, 1, 2, 2, 3, 4, 5)) if voice == 1 else rng.choice((1, 1, 2))
            midis = {n.midi for n in tied}
            while len(midis) < size:
                midis.add(max(low, min(high, int(rng.gauss(centre, 6)))))
            chord = []
            for i, midi in enumerate(sorted(midis)):
                head = next((n for n in tied if n.midi == midi), None)
                kwargs = {}
                if head is not None:
                    head.tie_start = True
                    kwargs['tie_stop'] = True
                if rng.random() < 0.03:
                    kwargs['is_hidden'] = True
                if rng.random() < 0.05:
                    kwargs['fingering_mark'] = str(rng.randint(1, 4))
                if rng.random() < 0.05:
                    kwargs['string_mark'] = rng.randint(1, strings)
                n = _make(rng, onset=t, duration=duration, midi=midi, voice=voice,
                          measure_length=measure_length, is_chord=i > 0, **kwargs)
                if rng.random() < 0.02:                  # microtone: not analyzed
                    n.midi, n.alter, n.reason = None, Fraction(1, 2), 'microtone not analyzed'
                chord.append(n)
            notes.extend(chord)
            previous[voice] = [n for n in chord if n.midi is not None and not n.is_hidden]
            t += duration
    # a doubling in another voice now and then
    if voices > 1 and rng.random() < 0.5:
        sources = [n for n in notes if n.voice == '1' and n.midi is not None and not n.is_grace
                   and not n.tie_stop]
        for source in rng.sample(sources, min(len(sources), 2)):
            notes.append(_make(rng, onset=source.onset, duration=source.duration,
                               midi=source.midi, voice=2, measure_length=measure_length))
    notes.sort(key=lambda n: (n.voice, n.onset))         # score order: voice by voice
    return export_case(f'random:{seed}', notes, tuning, frets)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('--random', type=int, default=400, help='random cases (default 400)')
    parser.add_argument('--seed', type=int, default=1, help='first random seed')
    args = parser.parse_args()
    logging.getLogger('core').setLevel(logging.ERROR)   # synthetic cases warn on purpose

    FIXTURES_OUT.mkdir(exist_ok=True)
    groups = {
        'scores': score_cases(),
        'synthetic': synthetic_cases(),
        'random': [random_case(seed) for seed in range(args.seed, args.seed + args.random)],
    }
    for name, cases in groups.items():
        path = FIXTURES_OUT / f'{name}.json'
        path.write_text(json.dumps({'ispog': __version__, 'cases': cases}, ensure_ascii=False,
                                   separators=(',', ':')), encoding='utf-8')
        events = sum(len(c['expected']['events']) for c in cases)
        print(f'{path.name}: {len(cases)} cases, {events} events')
    return 0


if __name__ == '__main__':
    sys.exit(main())
