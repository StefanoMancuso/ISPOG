"""
Sanity checks for the synthetic MusicXML builder in conftest.py and for the fixtures.

If these fail, every test that relies on a synthetic score is meaningless.
"""

from lxml import etree

from conftest import BASELINE_DIR, PartSpec, attributes, backup, make_score, note

SAFE_PARSER = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)


def _parse(data: bytes) -> etree._Element:
    return etree.fromstring(data, SAFE_PARSER)


def test_fixtures_and_baseline_exist(test01_path, test_poli_path):
    for path in (test01_path, test_poli_path,
                 BASELINE_DIR / "Test01_baseline.musicxml",
                 BASELINE_DIR / "Test01_baseline_colors.csv"):
        assert path.is_file(), f"missing {path}"


def test_fixtures_are_partwise(test01_path, test_poli_path):
    assert etree.parse(str(test01_path), SAFE_PARSER).getroot().tag == "score-partwise"
    poli = etree.parse(str(test_poli_path), SAFE_PARSER).getroot()
    assert [p.get("id") for p in poli.iterfind("part")] == ["P1", "P2", "P3", "P4"]


def test_single_part_score():
    root = _parse(make_score(measures=[
        attributes(divisions=2) + note("E", 2, 4) + backup(4) + note(None, None, 4, voice=2),
    ]))
    assert root.tag == "score-partwise"
    assert root.findtext("part-list/score-part/score-instrument/instrument-sound") \
        == "pluck.guitar.nylon-string"
    measure = root.find("part/measure")
    assert measure.get("number") == "1"
    assert [c.tag for c in measure] == ["attributes", "note", "backup", "note"]
    assert measure.find("note[2]/rest") is not None


def test_timewise_has_same_content_as_partwise():
    parts = [
        PartSpec(part_id="P1", name="Piano", instrument_sound="keyboard.piano",
                 midi_program=1, measures=[note("C", 4, 1), note("D", 4, 1)]),
        PartSpec(part_id="P2", measures=[note("E", 3, 1), note("F", 3, 1)]),
    ]
    partwise = _parse(make_score(parts=parts))
    timewise = _parse(make_score(parts=parts, timewise=True))
    assert timewise.tag == "score-timewise"
    for part in partwise.iterfind("part"):
        pid = part.get("id")
        for i, measure in enumerate(part.iterfind("measure"), start=1):
            twin = timewise.find(f"measure[@number='{i}']/part[@id='{pid}']")
            assert etree.tostring(twin[0]) == etree.tostring(measure[0])


def test_note_options():
    xml = note("F", 4, 2, alter=1, chord=True, tie=("stop", "start"), staff=2, voice=5)
    el = etree.fromstring(xml)
    assert el.find("chord") is not None
    assert el.findtext("pitch/alter") == "1"
    assert [t.get("type") for t in el.iterfind("tie")] == ["stop", "start"]
    assert [t.get("type") for t in el.iterfind("notations/tied")] == ["stop", "start"]
    assert el.findtext("staff") == "2" and el.findtext("voice") == "5"
    grace = etree.fromstring(note("G", 4, None, grace=True))
    assert grace.find("grace") is not None and grace.find("duration") is None


def test_utf16_encoding():
    data = make_score(measures=[note("E", 4, 1)], encoding="UTF-16")
    assert data[:2] in (b"\xff\xfe", b"\xfe\xff")          # BOM
    assert _parse(data).findtext("part/measure/note/pitch/step") == "E"


def test_tab_staff_and_transpose():
    root = _parse(make_score(measures=[
        attributes(staves=2, clefs=(("G", 2), ("TAB", 5)), transpose=(0, -1)),
    ]))
    attrs = root.find("part/measure/attributes")
    assert attrs.findtext("clef[@number='2']/sign") == "TAB"
    assert attrs.findtext("transpose/octave-change") == "-1"
