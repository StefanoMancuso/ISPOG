"""
core.writer: colors, credit, part extraction, serialization (plan, F4).

The end-to-end checks run reader → playability → writer on the fixtures and read the
colors back from the written file with tests/tools/extract_colors.py, the same tool that
produced the pre-refactor baseline.
"""

import re
import sys
from fractions import Fraction
from pathlib import Path

import pytest
from lxml import etree

from config.settings import COLOR_CODES, LABEL_TEXT
from config.version import __version__
from conftest import BASELINE_DIR, TESTS_DIR, PartSpec, attributes, backup, make_score, note
from core.analyzer import FingeringAnalysis, Issue, Playability
from core.fretboard import Fretboard
from core.playability import ChordEvent, analyze_notes
from core.reader import list_parts, load_score, read_part
from core.writer import (
    CREDIT_ID,
    LABEL_ID_PREFIX,
    add_ispog_credit,
    annotate,
    colorize,
    extract_part,
    label_text,
    remove_annotations,
    serialize,
    set_notehead_color,
)

sys.path.insert(0, str(TESTS_DIR / "tools"))
from extract_colors import extract_colors, read_csv  # noqa: E402

STANDARD = Fretboard(["E4", "B3", "G3", "D3", "A2", "E2"], 19)


def _analyze(path: Path) -> etree._ElementTree:
    """reader → playability → writer on every guitar part (F5 will own this pipeline)."""
    tree = load_score(path)
    for part in list_parts(tree):
        if part.is_guitar:
            colorize(_colored(part))
    add_ispog_credit(tree)
    return tree


def _colored(part):
    notes = read_part(part)
    analyze_notes(notes, STANDARD)
    return notes


def _write(tmp_path: Path, data: bytes, name: str = "out.musicxml") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _c14n(tree_or_element) -> bytes:
    return etree.tostring(tree_or_element, method="c14n")


def _note_el(xml: str) -> etree._Element:
    return etree.fromstring(xml)


# ---------------------------------------------------------------------------
# Notehead color
# ---------------------------------------------------------------------------

def test_notehead_is_inserted_before_its_schema_successors():
    el = _note_el("<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>"
                  "<type>quarter</type><stem>up</stem><staff>1</staff><beam number='1'>begin"
                  "</beam><notations/></note>")
    set_notehead_color(el, "#005000")
    assert [c.tag for c in el][-5:] == ["stem", "notehead", "staff", "beam", "notations"]
    assert el.find("notehead").text == "normal"
    assert el.find("notehead").get("color") == "#005000"


def test_notehead_is_appended_without_successors():
    el = _note_el("<note><rest/><duration>1</duration><voice>1</voice></note>")
    set_notehead_color(el, "#CF0000")
    assert el[-1].tag == "notehead"


def test_existing_notehead_keeps_its_shape_and_gets_the_new_color():
    el = _note_el('<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>'
                  '<notehead color="#FF8C00" filled="no">diamond</notehead></note>')
    set_notehead_color(el, "#CF0000")
    head = el.find("notehead")
    assert (head.text, head.get("filled"), head.get("color")) == ("diamond", "no", "#CF0000")
    assert len(el.findall("notehead")) == 1


@pytest.mark.parametrize("xml, expected", [
    # inserted before <staff>: the new line takes the siblings' indentation
    ("<note>\n  <pitch>x</pitch>\n  <staff>1</staff>\n  </note>",
     "<note>\n  <pitch>x</pitch>\n  <notehead color=\"#005000\">normal</notehead>\n"
     "  <staff>1</staff>\n  </note>"),
    # appended as last child: the closing tag keeps its own indentation
    ("<note>\n    <pitch>x</pitch>\n    <type>quarter</type>\n  </note>",
     "<note>\n    <pitch>x</pitch>\n    <type>quarter</type>\n"
     "    <notehead color=\"#005000\">normal</notehead>\n  </note>"),
])
def test_notehead_insertion_keeps_indentation(xml, expected):
    el = _note_el(xml)
    set_notehead_color(el, "#005000")
    assert etree.tostring(el, encoding="unicode") == expected


def test_color_codes_match_the_schema():
    # MusicXML 4.0: color = #RRGGBB or #AARRGGBB, upper-case hex digits
    assert all(re.fullmatch(r"#[0-9A-F]{6}([0-9A-F]{2})?", c) for c in COLOR_CODES.values())


def test_colorize_skips_black_notes_and_rests(write_score):
    tree = load_score(write_score(make_score(measures=[
        attributes() + note(None, None, 1) + note("E", 4, 1, alter=0.5) + note("E", 4, 2)])))
    notes = read_part(list_parts(tree)[0])
    analyze_notes(notes, STANDARD)
    assert colorize(notes) == 1
    rest, micro, e4 = notes
    assert rest.element.find("notehead") is None
    assert micro.element.find("notehead") is None
    assert e4.element.find("notehead").get("color") == COLOR_CODES["green"]


# ---------------------------------------------------------------------------
# End to end on the fixtures
# ---------------------------------------------------------------------------

def test_test01_written_colors_match_the_analysis(test01_path, tmp_path, assert_valid):
    tree = load_score(test01_path)
    notes = _colored(list_parts(tree)[0])
    colorize(notes)
    data = serialize(tree)
    assert_valid(data)
    rows = extract_colors(_write(tmp_path, data))
    assert [r["color"] for r in rows] == ["-" if n.is_rest else n.color for n in notes]


def test_test01_written_file_against_the_baseline(test01_path, tmp_path):
    # same accepted differences as test_playability.EXPECTED_DIFFERENCES
    rows = extract_colors(_write(tmp_path, serialize(_analyze(test01_path))))
    baseline = read_csv(BASELINE_DIR / "Test01_baseline_colors.csv")
    differences = [(r["measure"], r["index"], r["pitch"], b["color"], r["color"])
                   for r, b in zip(rows, baseline, strict=True) if r["color"] != b["color"]]
    assert differences == [("1", "23", "B2", "red", "purple"), ("1", "31", "D3", "red", "green")]


def test_the_0_9_output_was_not_schema_valid(musicxml_schema):
    # why 0.10 writes upper-case colors and inserts <notehead> in place (CHANGELOG, Fixed)
    tree = etree.parse(str(BASELINE_DIR / "Test01_baseline.musicxml"))
    assert not musicxml_schema.validate(tree)
    messages = {e.message for e in musicxml_schema.error_log}
    assert any("'color'" in m and "pattern" in m for m in messages)          # lower-case hex
    assert any("'notehead'" in m and "not expected" in m for m in messages)  # after notations


def test_test_poli_only_guitars_change(test_poli_path, assert_valid):
    original = load_score(test_poli_path)
    analyzed = _analyze(test_poli_path)
    assert_valid(serialize(analyzed))
    for part_id in ("P1", "P2"):
        path = f"part[@id='{part_id}']"
        assert _c14n(analyzed.getroot().find(path)) == _c14n(original.getroot().find(path))
    for part_id in ("P3", "P4"):
        heads = analyzed.getroot().findall(f"part[@id='{part_id}']//notehead[@color]")
        pitched = analyzed.getroot().findall(f"part[@id='{part_id}']//note/pitch")
        assert heads and len(heads) == len(pitched)


def test_analysis_is_idempotent(test_poli_path, tmp_path):
    first = serialize(_analyze(test_poli_path))
    second = serialize(_analyze(_write(tmp_path, first)))
    assert second == first


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["test01_path", "test_poli_path"])
def test_round_trip_without_analysis(fixture, request):
    path = request.getfixturevalue(fixture)
    data = serialize(load_score(path))
    original = etree.parse(str(path), etree.XMLParser(load_dtd=False, no_network=True))
    assert _c14n(etree.ElementTree(etree.fromstring(data))) == _c14n(original)
    assert data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE score-partwise')
    assert data.splitlines()[1] == path.read_bytes().splitlines()[1]      # same DOCTYPE


def test_timewise_input_is_written_partwise(write_score, assert_valid):
    tree = load_score(write_score(make_score(measures=[attributes() + note("E", 4, 4)],
                                             timewise=True)))
    data = serialize(tree)
    assert b"<!DOCTYPE score-partwise" in data
    assert_valid(data)


def test_utf16_input_is_written_utf8(write_score):
    tree = load_score(write_score(make_score(measures=[note("E", 4, 4)], encoding="UTF-16")))
    data = serialize(tree)
    assert data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    assert b"<step>E</step>" in data


def test_unresolved_entity_is_written_back(write_score):
    data = make_score(measures=[note("C", 4, 4)]).replace(
        b"<part-name>Classical Guitar", b"<part-name>Guitar &eacute;")
    assert b"Guitar &eacute;" in serialize(load_score(write_score(data)))


def test_synthetic_scores_are_schema_valid(assert_valid):
    assert_valid(make_score(measures=[
        attributes(divisions=2, staves=2, clefs=(("G", 2), ("TAB", 5)), transpose=(0, -1))
        + note("E", 4, 2, tie=("start",)) + note("G", 4, 2, chord=True)
        + note("B", 4, None, grace=True) + note("C", 5, 2, alter=1),
        note("E", 4, 2, tie=("stop",)) + note(None, None, 2),
    ]))


# ---------------------------------------------------------------------------
# Credit
# ---------------------------------------------------------------------------

def _credits(tree) -> list[etree._Element]:
    return tree.getroot().findall("credit")


def test_credit_names_the_version_and_precedes_part_list(test01_path, assert_valid):
    tree = load_score(test01_path)
    existing = len(_credits(tree))
    add_ispog_credit(tree)
    credits = _credits(tree)
    assert len(credits) == existing + 1
    ours = credits[-1]
    assert ours.get("id") == CREDIT_ID and ours.get("page") == "1"
    assert ours.findtext("credit-words") == f"Analyzed by ISPOG {__version__}"
    assert ours.getnext().tag == "part-list"
    assert_valid(serialize(tree))


def test_credit_is_placed_at_the_bottom_center_of_the_page(test01_path):
    tree = load_score(test01_path)
    width = float(tree.getroot().findtext("defaults/page-layout/page-width"))
    words = add_ispog_credit(tree).find("credit-words")
    assert float(words.get("default-x")) == pytest.approx(width / 2)
    assert 0 < float(words.get("default-y")) < 200


def test_credit_without_page_layout_has_no_position(write_score):
    tree = load_score(write_score(make_score(measures=[note("C", 4, 4)])))
    words = add_ispog_credit(tree).find("credit-words")
    assert words.get("default-x") is None and words.get("justify") == "center"


def test_credit_replaces_earlier_ones_including_0_9(write_score):
    # the 0.9 credit, as core.musicxml wrote it: no id, text "Analyzed by ISPOG"
    credit_0_9 = (b'<credit page="1"><credit-words default-x="600.24" default-y="507.692243" '
                  b'justify="center" valign="middle" font-style="italic" font-size="20">'
                  b'Analyzed by ISPOG</credit-words></credit>')
    data = make_score(measures=[note("C", 4, 4)]).replace(b"<part-list>",
                                                          credit_0_9 + b"<part-list>")
    tree = load_score(write_score(data))
    add_ispog_credit(tree)
    add_ispog_credit(tree)
    texts = [c.findtext("credit-words") for c in _credits(tree)]
    assert [t for t in texts if t.startswith("Analyzed by ISPOG")] == [
        f"Analyzed by ISPOG {__version__}"]


# ---------------------------------------------------------------------------
# Part extraction
# ---------------------------------------------------------------------------

def test_extract_part(test_poli_path, assert_valid):
    tree = _analyze(test_poli_path)
    before = serialize(tree)
    single = extract_part(tree, "P3")
    root = single.getroot()
    assert [p.get("id") for p in root.iterfind("part-list/score-part")] == ["P3"]
    assert [p.get("id") for p in root.iterfind("part")] == ["P3"]
    assert root.find("part-list/part-group") is None
    assert len(root.findall("credit")) == len(tree.getroot().findall("credit"))
    assert single.docinfo.doctype == tree.docinfo.doctype
    assert serialize(tree) == before                                  # input untouched
    assert_valid(serialize(single))


@pytest.mark.parametrize("part_id", ["P1", "P3", "P4"])        # first, middle, last
def test_extract_part_keeps_the_source_layout(test_poli_path, part_id):
    # every line of the extracted score, indentation included, exists in the source
    source = set(serialize(load_score(test_poli_path)).splitlines())
    extracted = serialize(extract_part(load_score(test_poli_path), part_id)).splitlines()
    assert [line for line in extracted[1:] if line not in source] == []


def test_extract_last_part_keeps_standard_indentation(write_score):
    # standard pretty-printing (closing tags one level out), unlike MuseScore's layout
    parts = [PartSpec(part_id=pid, measures=[note("C", 4, 4)]) for pid in ("P1", "P2")]
    tree = load_score(write_score(make_score(parts=parts)))
    etree.indent(tree, space="  ")
    source = set(serialize(tree).splitlines())
    extracted = serialize(extract_part(tree, "P1")).splitlines()
    assert [line for line in extracted[1:] if line not in source] == []


def test_extract_part_removes_part_groups(write_score):
    data = make_score(measures=[note("C", 4, 4)]).replace(
        b"<part-list>", b'<part-list><part-group type="start" number="1"/>').replace(
        b"</part-list>", b'<part-group type="stop" number="1"/></part-list>')
    single = extract_part(load_score(write_score(data)), "P1")
    assert single.getroot().find("part-list/part-group") is None


def test_extract_unknown_part(test_poli_path):
    with pytest.raises(ValueError, match="P9"):
        extract_part(load_score(test_poli_path), "P9")


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

SEVEN = [("E", 2), ("A", 2), ("D", 3), ("G", 3), ("B", 3), ("E", 4), ("A", 4)]


def _chord(pitches, duration=4, **kwargs):
    return "".join(note(step, octave, duration, chord=i > 0, **kwargs)
                   for i, (step, octave) in enumerate(pitches))


def _annotated(write_score, measures):
    tree = load_score(write_score(make_score(measures=measures)))
    part = list_parts(tree)[0]
    notes = read_part(part)
    result = analyze_notes(notes, STANDARD)
    count = annotate(part.element, result.events)
    return tree, part, notes, count


def _label_elements(tree):
    return [d for d in tree.iter("direction") if d.get("id", "").startswith(LABEL_ID_PREFIX)]


def test_label_goes_before_the_chord_it_describes(write_score, assert_valid):
    tree, _, notes, count = _annotated(write_score, [
        attributes() + note("E", 4, 4), _chord(SEVEN)])
    assert count == 1
    (label,) = _label_elements(tree)
    assert label.getnext() is notes[1].element                     # first note of the chord
    assert label.get("placement") == "above"
    words = label.find("direction-type/words")
    assert words.text == "no free string"
    assert words.get("color") == COLOR_CODES["red"]
    assert label.find("staff") is None
    assert_valid(serialize(tree))


@pytest.mark.parametrize("grace, main, label", [
    (("C", 2), [("E", 4)], "out of range"),        # red grace note, green chord
    (("E", 4), SEVEN, "no free string"),            # green grace note, red chord
])
def test_one_label_per_onset_with_the_worst_result(write_score, grace, main, label):
    # grace notes and the chord they precede are two analyzer events at the same onset
    tree, _, notes, _ = _annotated(write_score, [
        attributes() + note(*grace, None, grace=True) + _chord(main)])
    (element,) = _label_elements(tree)
    words = element.find("direction-type/words")
    assert (words.text, words.get("color")) == (label, COLOR_CODES["red"])
    assert element.getnext() is notes[0].element                  # before the grace note


def test_label_never_splits_a_chord(write_score, assert_valid):
    # the chord starts with a tied continuation (not analyzed again): the label must still
    # go before the chord's first note, not before the first attacked one
    tree, _, notes, _ = _annotated(write_score, [
        attributes() + note("E", 2, 4, tie=("start",)),
        note("E", 2, 4, tie=("stop",))
        + "".join(note(step, octave, 4, chord=True) for step, octave in SEVEN[1:])])
    (label,) = _label_elements(tree)
    continuation = notes[1]
    assert continuation.tie_stop and label.getnext() is continuation.element
    assert_valid(serialize(tree))


def test_label_on_the_second_staff_names_it(write_score, assert_valid):
    tree, _, notes, _ = _annotated(write_score, [
        attributes(staves=2, clefs=(("G", 2), ("F", 4)))
        + note(None, None, 4, staff=1) + backup(4) + _chord(SEVEN, staff=2, voice=5)])
    (label,) = _label_elements(tree)
    assert label.findtext("staff") == "2"
    assert label.getnext() is notes[1].element
    assert_valid(serialize(tree))


def test_labels_are_replaced_not_duplicated(write_score):
    tree, part, notes, _ = _annotated(write_score, [attributes() + _chord(SEVEN)])
    events = analyze_notes(read_part(part), STANDARD).events
    assert annotate(part.element, events) == 1
    assert len(_label_elements(tree)) == 1
    assert remove_annotations(part.element) == 1
    assert _label_elements(tree) == []


def test_playable_score_gets_no_label(write_score):
    _, _, _, count = _annotated(write_score, [attributes() + note("E", 4, 4)])
    assert count == 0


def test_label_follows_the_source_indentation(test01_path):
    tree = load_score(test01_path)
    part = list_parts(tree)[0]
    annotate(part.element, analyze_notes(read_part(part), STANDARD).events)
    label = _label_elements(tree)[0]
    indent = label.tail
    assert label.getprevious().tail == indent
    assert label.text == indent + "  "
    assert label.find("direction-type").text == indent + "    "


@pytest.mark.parametrize("issue, fingers, span, expected", [
    (Issue.FINGERS, 5, 3, "5 fingers"),
    (Issue.SPAN, 3, 6, "span 6"),
    (Issue.OUT_OF_RANGE, 0, 0, "out of range"),
    (Issue.STRINGS, 0, 0, "no free string"),
    (Issue.CONFLICT, 0, 0, "string conflict"),
    (Issue.PINKY_BARRE, 3, 2, "pinky barré"),
    (Issue.STRETCH, 2, 4, "stretch"),
    (Issue.CROSSING, 3, 0, "crossed fingers"),
    (Issue.FINGER_CONFLICT, 4, 3, "no free finger"),
    (Issue.NO_SHAPE, 3, 2, "no hand position"),
])
def test_label_text(issue, fingers, span, expected):
    analysis = FingeringAnalysis(playability=Playability.UNPLAYABLE, positions=[],
                                 fingers_used=fingers, has_barre=False, span=span, issue=issue)
    event = ChordEvent(onset=Fraction(0), measure_number="1", notes=[], held=[],
                       analysis=analysis)
    assert label_text(event) == expected


def test_every_issue_has_a_label():
    issues = {v for k, v in vars(Issue).items() if not k.startswith("_") and v}
    assert issues == set(LABEL_TEXT)
