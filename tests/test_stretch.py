"""
core.stretch: the finger stretch table (config/finger_stretch.csv).
"""

import pytest

from config.settings import HIGH_POSITION_FRET
from core.stretch import DEFAULT_PATH, StretchLimit, StretchTable, StretchTableError, default_table

HEADER = "fingers," + ",".join(f"{a}-{b}" for a in range(1, 7) for b in range(1, 7))
PAIRS = ["1-2", "1-3", "1-4", "2-3", "2-4", "3-4"]


def _table_text(cell="1/2", rows=None, header=HEADER) -> str:
    rows = rows if rows is not None else [p + suffix for p in PAIRS for suffix in ("", " >7")]
    return "\n".join([header] + [f"{row}," + ",".join([cell] * 36) for row in rows]) + "\n"


def _load(tmp_path, text) -> StretchTable:
    path = tmp_path / "stretch.csv"
    path.write_text(text, encoding="utf-8")
    return StretchTable.load(path)


def test_shipped_table_loads():
    assert DEFAULT_PATH.is_file()
    assert default_table() is default_table()               # read once


@pytest.mark.parametrize("fingers, strings, position, expected", [
    ((1, 2), (1, 1), 1, StretchLimit(2, 2)),
    ((1, 2), (1, 5), HIGH_POSITION_FRET, StretchLimit(2, 3)),   # '>7 3 max diff.'
    ((1, 4), (6, 1), 1, StretchLimit(3, 4)),                    # 3 ok, 4 difficult
    ((1, 4), (6, 1), HIGH_POSITION_FRET, StretchLimit(3, 4)),
    ((1, 4), (1, 1), HIGH_POSITION_FRET, StretchLimit(4, 4)),
    ((2, 3), (1, 1), 1, StretchLimit(1, 1)),
    ((2, 4), (5, 1), HIGH_POSITION_FRET, StretchLimit(3, 4)),
    ((3, 4), (1, 5), 1, StretchLimit(0, 1)),                    # '1 diff'
])
def test_shipped_values(fingers, strings, position, expected):
    (a, b), (sa, sb) = fingers, strings
    assert default_table().limit(a, sa, b, sb, position) == expected


def test_high_position_starts_at_fret_7():
    table = default_table()
    assert table.limit(1, 1, 2, 1, HIGH_POSITION_FRET - 1) == StretchLimit(2, 2)
    assert table.limit(1, 1, 2, 1, HIGH_POSITION_FRET) == StretchLimit(3, 3)


def test_finger_order_does_not_matter():
    table = default_table()
    assert table.limit(4, 1, 1, 6, 3) == table.limit(1, 6, 4, 1, 3)


def test_strings_beyond_the_sixth_use_the_sixth():
    table = default_table()
    assert table.limit(1, 8, 2, 7, 3) == table.limit(1, 6, 2, 6, 3)


def test_spaces_in_names_are_ignored(tmp_path):
    header = HEADER.replace("1-2,", "1 - 2,").replace("fingers", "↓ fingers | strings →")
    table = _load(tmp_path, _table_text("2 / 3", header=header))
    assert table.limit(1, 1, 2, 2, 1) == StretchLimit(2, 3)


@pytest.mark.parametrize("text, message", [
    (_table_text("2"), "line 2, column 1-1: invalid cell '2'"),
    (_table_text("3/2"), "O smaller than G"),
    (_table_text(header=HEADER.replace(",6-6", "")), "missing columns 6-6"),
    (_table_text(rows=[p for p in PAIRS]), "missing rows 1-2 >7"),
    (_table_text(rows=["1-5"]), "invalid row '1-5'"),
    (_table_text(rows=["1-2", "1-2"]), "row '1-2' repeated"),
    ("", "empty file"),
])
def test_invalid_tables(tmp_path, text, message):
    with pytest.raises(StretchTableError, match=message):
        _load(tmp_path, text)


def test_missing_file(tmp_path):
    with pytest.raises(StretchTableError, match="cannot read"):
        StretchTable.load(tmp_path / "none.csv")
