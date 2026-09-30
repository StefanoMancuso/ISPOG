"""
core.reader: loading, part listing and note timing (plan, F2).

Real fixtures check the result against the pre-refactor baseline; synthetic scores from
conftest.make_score cover the cases no real file contains.
"""

import csv
import io
import zipfile
from fractions import Fraction

import pytest
from lxml import etree

from conftest import (
    BASELINE_DIR,
    PartSpec,
    attributes,
    backup,
    forward,
    make_score,
    note,
)
from core.errors import UnsupportedFileError
from core.model import Note, format_beat
from core.reader import list_parts, load_score, read_part

F = Fraction


def _notes(path, part_index=0) -> list[Note]:
    return read_part(list_parts(load_score(path))[part_index])


def _signature(notes: list[Note]) -> list[tuple]:
    """Everything the reader computes, without the element reference."""
    return [(n.part_id, n.measure_number, n.voice, n.staff, n.onset, n.duration, n.beat,
             n.pitch_name, n.midi, n.is_chord, n.is_grace, n.tie_start, n.tie_stop)
            for n in notes]


def _single(write_score, measures, **kwargs) -> list[Note]:
    return _notes(write_score(make_score(measures=measures, **kwargs)))


# ---------------------------------------------------------------------------
# Real fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test01_notes(test01_path):
    return _notes(test01_path)


@pytest.fixture(scope="module")
def poli_parts(test_poli_path):
    return list_parts(load_score(test_poli_path))


class TestTest01:
    def test_single_guitar_part(self, test01_path):
        parts = list_parts(load_score(test01_path))
        assert [(p.part_id, p.name, p.is_guitar) for p in parts] == [
            ("P1", "Chitarra classica", True)]

    def test_every_note_element_is_read_once(self, test01_notes):
        assert len(test01_notes) == 52
        assert len({id(n.element) for n in test01_notes}) == 52
        assert all(n.element.tag == "note" for n in test01_notes)
        assert sum(n.voice == "1" for n in test01_notes) == 32
        assert sum(n.voice == "2" for n in test01_notes) == 20

    def test_same_sequence_as_the_baseline(self, test01_notes):
        with open(BASELINE_DIR / "Test01_baseline_colors.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert [(r["measure"], r["voice"], r["pitch"]) for r in rows] == [
            (n.measure_number, n.voice, n.pitch_name) for n in test01_notes]

    def test_first_measure_onsets(self, test01_notes):
        voice1 = [n for n in test01_notes if n.measure_number == "1" and n.voice == "1"]
        assert voice1[0].is_rest and voice1[0].onset == 0
        chord = [n for n in voice1 if n.onset == 1]
        assert [n.midi for n in chord] == [40, 47, 52, 55, 59, 64]      # E2 B2 E3 G3 B3 E4
        assert [n.is_chord for n in chord] == [False] + [True] * 5
        assert all(n.beat == 2 for n in chord)

    def test_backup_returns_voice_2_to_the_measure_start(self, test01_notes):
        first_voice2 = next(n for n in test01_notes if n.voice == "2")
        assert (first_voice2.measure_number, first_voice2.onset) == ("1", 0)


class TestTestPoli:
    def test_guitars_are_detected(self, poli_parts):
        assert [(p.part_id, p.is_guitar) for p in poli_parts] == [
            ("P1", False), ("P2", False), ("P3", True), ("P4", True)]

    def test_all_parts_end_together(self, poli_parts):
        # divisions=2 everywhere: a wrong division would shift one part against the others
        ends = {p.part_id: max(n.onset + n.duration for n in read_part(p)) for p in poli_parts}
        assert len(set(ends.values())) == 1, ends

    def test_piano_second_staff_is_read(self, poli_parts):
        piano = read_part(poli_parts[1])
        voice5 = [n for n in piano if n.voice == "5"]
        assert len(voice5) == 8
        assert all(n.staff == 2 for n in voice5)


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def test_forward_at_measure_start(write_score):
    notes = _single(write_score, [attributes() + forward(2) + note("C", 4, 2)])
    assert (notes[0].onset, notes[0].beat) == (2, 3)


def test_divisions_change_mid_part(write_score):
    notes = _single(write_score, [
        attributes(divisions=1) + note("C", 4, 4),
        attributes(divisions=4, beats=None, clefs=()) + note("D", 4, 16),
        note("E", 4, 8) + note("F", 4, 8),
    ])
    assert [(n.onset, n.duration) for n in notes] == [(0, 4), (4, 4), (8, 2), (10, 2)]


def test_decimal_durations(write_score):
    notes = _single(write_score, [attributes(divisions=2) + note("C", 4, "1.5") + note("D", 4, 1)])
    assert [n.onset for n in notes] == [0, F(3, 4)]


def test_grace_notes_and_chords(write_score):
    notes = _single(write_score, [
        attributes()
        + note("G", 4, None, grace=True) + note("B", 4, None, grace=True, chord=True)
        + note("C", 5, 1) + note("E", 5, 1, chord=True)
        + note("D", 5, 1),
    ])
    assert [(n.pitch_name, n.onset, n.is_grace) for n in notes] == [
        ("G4", 0, True), ("B4", 0, True), ("C5", 0, False), ("E5", 0, False), ("D5", 1, False)]
    assert notes[0].duration == 0


def test_grace_note_with_duration_does_not_advance(write_score):
    # not allowed by the schema, but written by some exporters
    grace = ('<note><grace/><pitch><step>G</step><octave>4</octave></pitch>'
             '<duration>1</duration><voice>1</voice></note>')
    notes = _single(write_score, [attributes() + grace + note("C", 5, 1)])
    assert [n.onset for n in notes] == [0, 0]


def test_chord_after_backup_takes_its_voice_onset(write_score):
    notes = _single(write_score, [
        attributes() + note("C", 4, 4)
        + backup(4) + note("E", 3, 2, voice=2) + note("G", 3, 2, voice=2, chord=True)
        + note("A", 3, 2, voice=2),
    ])
    assert [(n.pitch_name, n.onset) for n in notes] == [
        ("C4", 0), ("E3", 0), ("G3", 0), ("A3", 2)]


def test_pickup_measure_lasts_as_its_content(write_score):
    notes = _single(write_score, [attributes() + note("G", 4, 1), note("C", 5, 4)])
    assert notes[1].onset == 1


def test_measure_without_notes_lasts_its_time_signature(write_score):
    notes = _single(write_score, [attributes(beats=3), note("C", 4, 3)])
    assert notes[0].onset == 3


def test_cue_notes_advance_the_cursor(write_score):
    notes = _single(write_score, [attributes() + note("C", 4, 2, cue=True) + note("D", 4, 2)])
    assert notes[0].is_cue and notes[1].onset == 2


@pytest.mark.parametrize("beats, beat_type, onset, expected", [
    (4, 4, F(3, 2), F(5, 2)),        # 4/4, off-beat
    (6, 8, F(3, 2), F(4)),           # 6/8, fourth eighth
    (2, 2, F(2), F(2)),              # 2/2, second half note
])
def test_beat_follows_the_time_signature(write_score, beats, beat_type, onset, expected):
    divisions = 2
    notes = _single(write_score, [
        attributes(divisions=divisions, beats=beats, beat_type=beat_type)
        + forward(int(onset * divisions)) + note("C", 4, 1),
    ])
    assert notes[0].beat == expected


@pytest.mark.parametrize("beat, label", [(F(3), "3"), (F(5, 2), "2 1/2"), (F(1, 3), "1/3")])
def test_format_beat(beat, label):
    assert format_beat(beat) == label


# ---------------------------------------------------------------------------
# Pitch and note kinds
# ---------------------------------------------------------------------------

def test_midi_numbers_and_names(write_score):
    notes = _single(write_score, [
        attributes() + note("E", 2, 1) + note("F", 3, 1, alter=1)
        + note("B", 3, 1, alter=-1) + note("C", 4, 1),
    ])
    assert [(n.pitch_name, n.midi) for n in notes] == [
        ("E2", 40), ("F#3", 54), ("Bb3", 58), ("C4", 60)]
    assert notes[1].get_pitch() == ["F3", "1"]


def test_transpose_octave_down(write_score):
    # Sibelius / Finale: guitar written an octave above sounding pitch
    notes = _single(write_score, [attributes(transpose=(0, -1)) + note("E", 4, 4)])
    assert (notes[0].pitch_name, notes[0].midi) == ("E4", 52)


def test_transpose_applies_from_its_measure(write_score):
    notes = _single(write_score, [
        attributes() + note("E", 4, 4),
        attributes(divisions=None, beats=None, clefs=(), transpose=(0, -1)) + note("E", 4, 4),
    ])
    assert [n.midi for n in notes] == [64, 52]


def test_rest_microtone_harmonic_unpitched(write_score):
    unpitched = ("<note><unpitched><display-step>E</display-step>"
                 "<display-octave>4</display-octave></unpitched>"
                 "<duration>1</duration><voice>1</voice></note>")
    notes = _single(write_score, [
        attributes() + note(None, None, 1) + note("E", 4, 1, alter=0.5)
        + note("E", 5, 1, harmonic=True) + unpitched,
    ])
    rest, micro, harmonic, perc = notes
    assert rest.is_rest and rest.midi is None and rest.get_pitch() == ["rest", "0"]
    assert micro.midi is None and micro.reason == "microtone not analyzed"
    assert harmonic.is_harmonic and harmonic.midi == 76 and "harmonic" in harmonic.reason
    assert perc.is_unpitched and perc.midi is None and perc.onset == 3


@pytest.mark.parametrize("tie, start, stop", [
    ((), False, False),
    (("start",), True, False),
    (("stop",), False, True),
    (("stop", "start"), True, True),
])
def test_ties(write_score, tie, start, stop):
    notes = _single(write_score, [attributes() + note("C", 4, 4, tie=tie)])
    assert (notes[0].tie_start, notes[0].tie_stop) == (start, stop)


def test_tied_notation_is_a_fallback_for_tie(write_score):
    xml = ('<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>'
           '<voice>1</voice><notations><tied type="stop"/></notations></note>')
    notes = _single(write_score, [attributes() + xml])
    assert notes[0].tie_stop and not notes[0].tie_start


# ---------------------------------------------------------------------------
# TAB staves
# ---------------------------------------------------------------------------

def test_tab_staff_doubling_notation_is_skipped(write_score):
    notes = _single(write_score, [
        attributes(staves=2, clefs=(("G", 2), ("TAB", 5)))
        + note("E", 3, 4, staff=1) + backup(4) + note("E", 3, 4, staff=2, voice=5),
    ])
    assert [(n.staff, n.pitch_name) for n in notes] == [(1, "E3")]


def test_tab_only_part_is_read(write_score):
    notes = _single(write_score, [attributes(clefs=(("TAB", 5),)) + note("E", 3, 4)])
    assert len(notes) == 1


# ---------------------------------------------------------------------------
# Guitar detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, sound, program, expected", [
    ("Guitar", "pluck.guitar.nylon-string", 25, True),
    ("Anything", "pluck.guitar.electric", None, True),
    ("Guitar", "keyboard.piano", 25, False),          # the sound id wins
    ("Electric Bass", "pluck.bass.electric", 34, False),
    ("Part 1", None, 26, True),
    ("Guitar", None, 1, False),                       # the MIDI program wins over the name
    ("Chitarra", None, None, True),
    ("Gitarre", None, None, True),
    ("Guitare", None, None, True),
    ("Bass Guitar", None, None, False),
    ("Violin", None, None, False),
])
def test_guitar_detection(write_score, name, sound, program, expected):
    spec = PartSpec(measures=[note("C", 4, 4)], name=name,
                    instrument_sound=sound, midi_program=program)
    parts = list_parts(load_score(write_score(make_score(parts=[spec]))))
    assert parts[0].is_guitar is expected


def test_score_part_without_part_is_skipped(write_score):
    data = make_score(parts=[PartSpec(part_id="P1", measures=[note("C", 4, 4)])])
    data = data.replace(b"</part-list>",
                        b'<score-part id="P9"><part-name>Ghost</part-name></score-part>'
                        b"</part-list>")
    assert [p.part_id for p in list_parts(load_score(write_score(data)))] == ["P1"]


# ---------------------------------------------------------------------------
# File formats
# ---------------------------------------------------------------------------

def _two_part_specs() -> list[PartSpec]:
    return [
        PartSpec(part_id="P1", name="Flute", instrument_sound="wind.flutes.flute",
                 midi_program=74,
                 measures=[attributes() + note("C", 5, 4), note("D", 5, 2) + note("E", 5, 2)]),
        PartSpec(part_id="P2",
                 measures=[attributes() + note("E", 2, 4) + note("E", 3, 4, chord=True),
                           note("A", 2, 4)]),
    ]


def test_timewise_equals_partwise(write_score):
    partwise = load_score(write_score(make_score(parts=_two_part_specs()), "p.musicxml"))
    timewise = load_score(write_score(make_score(parts=_two_part_specs(), timewise=True),
                                      "t.musicxml"))
    assert timewise.getroot().tag == "score-partwise"
    assert "Partwise" in timewise.docinfo.doctype
    p_parts, t_parts = list_parts(partwise), list_parts(timewise)
    assert [(p.part_id, p.is_guitar) for p in p_parts] == [(p.part_id, p.is_guitar)
                                                           for p in t_parts]
    for p, t in zip(p_parts, t_parts):
        assert _signature(read_part(p)) == _signature(read_part(t))


def _mxl(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _container(full_path: str, media_type: str = "") -> bytes:
    media = f' media-type="{media_type}"' if media_type else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?><container><rootfiles>'
            f'<rootfile full-path="{full_path}"{media}/></rootfiles></container>').encode()


@pytest.mark.parametrize("container, target", [
    pytest.param(_container("score.musicxml"), "score.musicxml", id="container"),
    pytest.param(_container("score.xml"), "score.xml", id="musescore-4"),
    pytest.param(_container("a/score.xml", "application/vnd.recordare.musicxml+xml"),
                 "a/score.xml", id="xml-with-media-type"),
    pytest.param(None, "score.xml", id="no-container"),
])
def test_mxl_equals_uncompressed(write_score, test01_path, container, target):
    members = {"META-INF/container.xml": container} if container else {}
    members[target] = test01_path.read_bytes()
    path = write_score(_mxl(members), "score.mxl")
    assert _signature(_notes(path)) == _signature(_notes(test01_path))


def test_mxl_skips_rootfiles_that_are_not_scores(write_score, test01_path):
    container = (b'<container><rootfiles>'
                 b'<rootfile full-path="cover.png" media-type="image/png"/>'
                 b'<rootfile full-path="score.musicxml"/></rootfiles></container>')
    path = write_score(_mxl({"META-INF/container.xml": container, "cover.png": b"\x89PNG",
                             "score.musicxml": test01_path.read_bytes()}), "score.mxl")
    assert len(_notes(path)) == 52


def test_format_is_recognized_from_content(write_score, test01_path):
    zipped = _mxl({"META-INF/container.xml": _container("score.musicxml"),
                   "score.musicxml": test01_path.read_bytes()})
    assert len(_notes(write_score(zipped, "misnamed.musicxml"))) == 52
    assert len(_notes(write_score(test01_path.read_bytes(), "plain.mxl"))) == 52


def test_utf16(write_score):
    notes = _notes(write_score(make_score(measures=[attributes() + note("E", 4, 1)],
                                          encoding="UTF-16")))
    assert notes[0].pitch_name == "E4"


def test_named_entity_declared_in_the_dtd_is_tolerated(write_score):
    # the DTD is never loaded (plan, D8): the entity stays unresolved but parsing succeeds
    data = make_score(measures=[note("C", 4, 4)]).replace(
        b"<part-name>Classical Guitar", b"<part-name>Guitar &eacute;")
    parts = list_parts(load_score(write_score(data)))
    assert parts[0].is_guitar


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("content, message", [
    (b"", "not a valid MusicXML"),
    (b"just text", "not a valid MusicXML"),
    (b"<html><body/></html>", "root element <html>"),
    (b'<?xml version="1.0"?><opus/>', "root element <opus>"),
    (b"PK\x03\x04 broken zip", "not a valid MusicXML"),
])
def test_unsupported_content(write_score, content, message):
    with pytest.raises(UnsupportedFileError, match=message):
        load_score(write_score(content))


def test_missing_file(tmp_path):
    with pytest.raises(UnsupportedFileError, match="Cannot read"):
        load_score(tmp_path / "missing.musicxml")


def test_mxl_without_score(write_score):
    path = write_score(_mxl({"META-INF/container.xml": _container("x.png", "image/png"),
                             "x.png": b"\x89PNG"}), "empty.mxl")
    with pytest.raises(UnsupportedFileError, match="contains no MusicXML score"):
        load_score(path)


def test_invalid_divisions(write_score):
    path = write_score(make_score(measures=[attributes(divisions=0) + note("C", 4, 1)]))
    part = list_parts(load_score(path))[0]
    with pytest.raises(UnsupportedFileError, match="measure 1"):
        read_part(part)


def test_errors_are_user_facing(write_score):
    with pytest.raises(UnsupportedFileError) as info:
        load_score(write_score(b"just text", "My Score.musicxml"))
    assert "'My Score.musicxml'" in str(info.value)
    assert isinstance(info.value.__cause__, etree.XMLSyntaxError)
