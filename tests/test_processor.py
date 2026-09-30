"""
core.processor: configuration, part selection, full and split outputs (plan, F5).
"""

import sys

import pytest
from lxml import etree

from conftest import BASELINE_DIR, TESTS_DIR, PartSpec, attributes, make_score, note
from core.errors import NoGuitarPartError, UnsupportedFileError
from core.processor import AnalysisConfig, analyze, select_targets, write_notes_logs
from core.reader import list_parts, load_score
from core.writer import CREDIT_ID, LABEL_ID_PREFIX

sys.path.insert(0, str(TESTS_DIR / "tools"))
from extract_colors import extract_colors, read_csv  # noqa: E402

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")


def _config(path, **kwargs) -> AnalysisConfig:
    return AnalysisConfig(path, tuning=kwargs.pop("tuning", STANDARD), **kwargs)


def _tree(data: bytes) -> etree._ElementTree:
    return etree.ElementTree(etree.fromstring(data, etree.XMLParser(load_dtd=False)))


def _labels(tree) -> list[etree._Element]:
    return [d for d in tree.iter("direction") if d.get("id", "").startswith(LABEL_ID_PREFIX)]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_config_normalizes_its_values(test01_path):
    config = _config(str(test01_path), tuning=list(STANDARD), part_ids=["P1"])
    assert config.filepath == test01_path
    assert config.tuning == STANDARD and config.num_strings == 6
    assert config.part_ids == ("P1",)


@pytest.mark.parametrize("kwargs, message", [
    ({"tuning": ("E4", "B3", "G3")}, "strings"),
    ({"tuning": STANDARD * 2}, "strings"),
    ({"num_frets": 11}, "frets"),
    ({"num_frets": 25}, "frets"),
    ({"output_mode": "parts"}, "output mode"),
    ({"tuning": ("E4", "B3", "G3", "D3", "A2", "H2")}, "note name"),
])
def test_config_rejects_invalid_values(test01_path, kwargs, message):
    with pytest.raises(ValueError, match=message):
        _config(test01_path, **kwargs)


# ---------------------------------------------------------------------------
# Part selection
# ---------------------------------------------------------------------------

def _parts(write_score, specs):
    return list_parts(load_score(write_score(make_score(parts=specs))))


def _spec(part_id, guitar):
    return PartSpec(part_id=part_id, measures=[note("C", 4, 4)],
                    name="Guitar" if guitar else "Flute",
                    instrument_sound="pluck.guitar" if guitar else "wind.flutes.flute",
                    midi_program=25 if guitar else 74)


def test_guitars_are_selected_by_default(write_score):
    parts = _parts(write_score, [_spec("P1", False), _spec("P2", True), _spec("P3", True)])
    assert [p.part_id for p in select_targets(parts, None)] == ["P2", "P3"]


def test_a_single_part_is_always_analyzed(write_score):
    parts = _parts(write_score, [_spec("P1", False)])
    assert [p.part_id for p in select_targets(parts, None)] == ["P1"]


def test_explicit_parts_in_score_order(write_score):
    parts = _parts(write_score, [_spec("P1", False), _spec("P2", True), _spec("P3", True)])
    assert [p.part_id for p in select_targets(parts, ("P3", "P1"))] == ["P1", "P3"]


def test_unknown_part_id(write_score):
    parts = _parts(write_score, [_spec("P1", True)])
    with pytest.raises(ValueError, match="P7"):
        select_targets(parts, ("P7",))


def test_no_guitar(write_score):
    path = write_score(make_score(parts=[_spec("P1", False), _spec("P2", False)]), "duo.xml")
    with pytest.raises(NoGuitarPartError, match="duo.xml"):
        analyze(_config(path))


def test_unreadable_file_is_reported(write_score):
    with pytest.raises(UnsupportedFileError):
        analyze(_config(write_score(b"not xml")))


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def poli_full(test_poli_path):
    return analyze(_config(test_poli_path))


def test_full_output_changes_only_the_guitars(poli_full, test_poli_path, assert_valid):
    data = poli_full.outputs["full"]
    assert list(poli_full.outputs) == ["full"]
    assert_valid(data)
    original, analyzed = load_score(test_poli_path).getroot(), _tree(data).getroot()
    for pid in ("P1", "P2"):
        path = f"part[@id='{pid}']"
        assert (etree.tostring(analyzed.find(path), method="c14n")
                == etree.tostring(original.find(path), method="c14n"))
    for pid in ("P3", "P4"):
        pitched = analyzed.findall(f"part[@id='{pid}']//note/pitch")
        colored = analyzed.findall(f"part[@id='{pid}']//notehead[@color]")
        assert pitched and len(colored) == len(pitched)
    assert len(analyzed.findall(f"credit[@id='{CREDIT_ID}']")) == 1
    assert [r.part_id for r in poli_full.reports] == ["P3", "P4"]


def test_split_output(test_poli_path, assert_valid):
    result = analyze(_config(test_poli_path, output_mode="split"))
    assert list(result.outputs) == ["P3", "P4"]
    for pid, data in result.outputs.items():
        assert_valid(data)
        root = _tree(data).getroot()
        assert [p.get("id") for p in root.iterfind("part")] == [pid]
        assert root.find(f"credit[@id='{CREDIT_ID}']") is not None


def test_test01_colors_and_labels(test01_path, tmp_path, assert_valid):
    result = analyze(_config(test01_path))
    data = result.outputs["full"]
    assert_valid(data)
    path = tmp_path / "out.musicxml"
    path.write_bytes(data)
    rows, baseline = extract_colors(path), read_csv(BASELINE_DIR / "Test01_baseline_colors.csv")
    assert [(r["index"], r["pitch"], b["color"], r["color"]) for r, b in zip(rows, baseline)
            if r["color"] != b["color"]] == [("31", "D3", "red", "green")]      # plan §5.1
    labels = _labels(_tree(data))
    assert [d.findtext("direction-type/words") for d in labels] == ["no free string"] * 3

    report = result.reports[0]
    assert report.counts == {"green": 36, "orange": 0, "red": 8, "black": 0}
    assert report.red_measures == ["1"]


def test_labels_can_be_turned_off_and_are_removed(test01_path, tmp_path):
    labeled = tmp_path / "labeled.musicxml"
    labeled.write_bytes(analyze(_config(test01_path)).outputs["full"])
    assert _labels(_tree(labeled.read_bytes()))
    plain = analyze(_config(labeled, labels=False)).outputs["full"]
    assert _labels(_tree(plain)) == []


def test_analyzing_the_output_again_gives_the_same_file(test_poli_path, tmp_path):
    first = analyze(_config(test_poli_path)).outputs["full"]
    again = tmp_path / "again.musicxml"
    again.write_bytes(first)
    assert analyze(_config(again)).outputs["full"] == first


def test_multi_staff_part_is_analyzed_with_explicit_selection(test_poli_path):
    # the piano is not a guitar, but the user may select it
    result = analyze(_config(test_poli_path, part_ids=("P2",)))
    assert [r.part_id for r in result.reports] == ["P2"]
    assert result.reports[0].counts["green"] > 0


def test_write_notes_logs(poli_full, tmp_path):
    paths = write_notes_logs(poli_full, tmp_path / "logs")
    assert [p.name for p in paths] == ["test_poli_P3_notes.tsv", "test_poli_P4_notes.tsv"]
    lines = paths[0].read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t")[:4] == ["measure", "beat", "onset", "pitch"]
    assert len(lines) == 1 + len(poli_full.reports[0].notes)


def test_microtones_are_listed_not_colored(write_score):
    path = write_score(make_score(measures=[attributes() + note("E", 4, 2, alter=0.5)
                                            + note("E", 4, 2)]))
    report = analyze(_config(path)).reports[0]
    assert report.counts == {"green": 1, "orange": 0, "red": 0, "black": 1}
    assert [n.reason for n in report.not_analyzed] == ["microtone not analyzed"]
