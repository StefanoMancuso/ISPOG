"""
utils.text: display helpers.
"""

import pytest

from utils.text import shorten


@pytest.mark.parametrize("text, max_chars, expected", [
    ("short.mxl", 20, "short.mxl"),
    ("abcdefghij", 10, "abcdefghij"),
    ("abcdefghijk", 10, "abcd…ghijk"),
    ("Suite for guitar quartet No. 3.musicxml", 20, "Suite for…3.musicxml"),
])
def test_shorten(text, max_chars, expected):
    result = shorten(text, max_chars)
    assert result == expected and len(result) <= max_chars
