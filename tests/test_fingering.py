"""
core.fingering: finger assignment and grading of a hand shape.

Positions are (string, fret); fret 0 is an open string. Fingers: 1 index … 4 pinky.
"""

import pytest

from core.fingering import Issue, Playability, hand_shapes


def _best(positions, pinned=None):
    search = hand_shapes(positions, pinned)
    return search.valid[0] if search.valid else None


def test_open_strings_take_no_finger():
    shape = _best([(1, 0), (2, 0)])
    assert shape.playability is Playability.PLAYABLE
    assert shape.fingers == (0, 0) and shape.fingers_used == 0


def test_one_finger_per_fret():
    # C major: C3 5/3, E3 4/2, C4 2/1
    shape = _best([(5, 3), (4, 2), (2, 1)])
    assert shape.playability is Playability.PLAYABLE
    assert shape.fingers == (3, 2, 1)


def test_same_fret_lower_finger_on_lower_string():
    # A major: 4/2 3/2 2/2
    shape = _best([(4, 2), (3, 2), (2, 2)])
    assert shape.playability is Playability.PLAYABLE
    assert shape.fingers == (1, 2, 3)


def test_finger_order_follows_the_frets():
    for shape in hand_shapes([(6, 3), (1, 5), (3, 4)]).valid:
        fingers = dict(zip((3, 5, 4), shape.fingers))       # fret -> finger
        assert fingers[3] < fingers[4] < fingers[5]


def test_more_than_four_fingers():
    search = hand_shapes([(6, 1), (5, 2), (4, 3), (3, 4), (2, 5)])
    assert search.valid == () and search.invalid == ()
    assert search.min_fingers == 5


def test_index_barre_saves_fingers():
    # F major barré: 6/1 5/3 4/3 3/2 2/1 1/1
    shape = _best([(6, 1), (5, 3), (4, 3), (3, 2), (2, 1), (1, 1)])
    assert shape.playability is Playability.PLAYABLE
    assert shape.barre_finger == 1 and shape.barre_fret == 1
    assert shape.fingers == (1, 3, 4, 2, 1, 1)           # ring on string 5, pinky on 4


def test_no_open_string_under_the_index_barre():
    # 1/1 and 3/1 with string 2 open: two fingers, not a barré
    search = hand_shapes([(1, 1), (3, 1), (2, 0)])
    assert all(s.barre_finger is None for s in search.valid)
    assert search.valid[0].fingers == (2, 1, 0)


def test_pinky_barre_is_difficult():
    # 6/5 5/6 4/7 and the pinky on 2/8 1/8
    shape = _best([(6, 5), (5, 6), (4, 7), (2, 8), (1, 8)])
    assert shape.playability is Playability.DIFFICULT
    assert shape.issue == Issue.PINKY_BARRE
    assert shape.problems[0].text == "pinky barré on fret 8, strings 1–2"


def test_two_notes_on_the_top_fret_prefer_two_fingers_to_a_pinky_barre():
    shape = _best([(1, 7), (2, 7), (3, 5)])
    assert shape.playability is Playability.PLAYABLE
    assert shape.barre_finger is None


def test_stretch_is_difficult():
    shape = _best([(6, 1), (1, 5)])
    assert shape.playability is Playability.DIFFICULT
    assert shape.issue == Issue.STRETCH
    assert shape.problems[0].text == "stretch: fingers 1–4 over 4 frets"


def test_stretch_over_an_index_barre_is_difficult():
    # barré on strings 6-2, pinky 4 frets higher: the table decides, as without barré
    shape = _best([(6, 1), (2, 1), (1, 5)])
    assert shape.playability is Playability.DIFFICULT
    assert shape.barre_finger == 1
    assert shape.problems[0].text == "stretch: fingers 1–4 over 4 frets"


def test_every_pair_is_checked_in_a_barre_chord():
    # test_ISPOG m. 1: barré 1, middle 3/2, ring 4/3, pinky 1/5
    shape = _best([(6, 1), (4, 3), (3, 2), (2, 1), (1, 5)])
    assert shape.playability is Playability.DIFFICULT
    assert shape.barre_finger == 1 and shape.fingers == (1, 3, 2, 1, 4)
    assert [p.text for p in shape.problems] == [
        "stretch: fingers 1–4 over 4 frets", "stretch: fingers 2–4 over 3 frets",
        "stretch: fingers 3–4 over 2 frets"]


def test_high_position_allows_wider_stretches():
    assert _best([(6, 1), (1, 3), (2, 2)]).playability is Playability.PLAYABLE
    # fingers 1–2 over 3 frets: only from fret 7 up
    low = hand_shapes([(5, 2), (4, 5)])
    high = hand_shapes([(5, 8), (4, 11)])
    assert low.valid and high.valid
    assert all(s.fingers != (1, 2) for s in low.valid)
    assert any(s.fingers == (1, 2) for s in high.valid)


def test_too_far_apart():
    search = hand_shapes([(6, 1), (1, 7)])
    assert search.valid == ()
    shape = search.invalid[0]
    assert shape.span == 6 and shape.fingers == (1, 4)
    assert shape.problems[0].text == "fingers 1–4 over 6 frets (max 4)"


def test_pinned_fingers_are_kept():
    shape = _best([(2, 6), (3, 7)], pinned=[2, None])
    assert shape.fingers[0] == 2 and shape.fingers[1] in (3, 4)


def test_crossed_fingers_on_adjacent_strings_are_difficult():
    # index on 5/3, middle held on 2/5: string 3 on fret 5 needs a crossed finger
    shape = _best([(5, 3), (2, 5), (3, 5)], pinned=[1, 2, None])
    assert shape.playability is Playability.DIFFICULT
    assert shape.issue == Issue.CROSSING
    assert shape.fingers == (1, 2, 3)


def test_crossed_fingers_on_distant_strings_are_impossible():
    search = hand_shapes([(5, 3), (2, 5), (4, 5)], pinned=[1, 2, None])
    assert search.valid == () and search.invalid == ()
    assert search.min_fingers == 3


def test_open_string_cannot_be_pinned_to_a_finger():
    assert hand_shapes([(1, 0)], pinned=[2]).valid == ()


def test_pinned_must_match_positions():
    with pytest.raises(ValueError):
        hand_shapes([(1, 0)], pinned=[None, None])
