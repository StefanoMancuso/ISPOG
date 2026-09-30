# -*- coding: utf-8 -*-
"""
ISPOG - MusicXML writer
Writes the analysis back into the score tree and serializes it.

Every change is made on the lxml tree (plan, D1): notehead colors on the ``<note>``
elements the notes point at (plan, D2), a credit naming the ISPOG version, and, for
separate outputs, a copy of the score reduced to one part. Everything is idempotent:
analyzing an already analyzed score gives the same file.
"""

from __future__ import annotations

import copy
import logging
from typing import Iterable, Optional

from lxml import etree

from config.settings import COLOR_CODES
from config.version import __version__

from .model import DEFAULT_COLOR, Note

logger = logging.getLogger(__name__)

XML_DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'
CREDIT_ID = 'ispog-credit'
CREDIT_PREFIX = 'Analyzed by ISPOG'

# Children of <note> that follow <notehead> in the MusicXML 4.0 schema
NOTEHEAD_SUCCESSORS = frozenset(
    ('notehead-text', 'staff', 'beam', 'notations', 'lyric', 'play', 'listen'))


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

def set_notehead_color(note_el: etree._Element, hex_color: str) -> None:
    """
    Set the color of a note's ``<notehead>``, creating it (``normal``) where the schema
    wants it if missing. An existing color is overwritten; the notehead shape is kept.
    """
    notehead = note_el.find('notehead')
    if notehead is None:
        notehead = etree.Element('notehead')
        notehead.text = 'normal'
        anchor = next((c for c in note_el if c.tag in NOTEHEAD_SUCCESSORS), None)
        _insert_child(note_el, notehead, before=anchor)
    notehead.set('color', hex_color)


def _insert_child(parent: etree._Element, child: etree._Element,
                  before: Optional[etree._Element]) -> None:
    """Insert ``child`` keeping the indentation of the surrounding siblings."""
    if before is not None:
        previous = before.getprevious()
        indent = previous.tail if previous is not None else parent.text
        before.addprevious(child)
        child.tail = indent
        return
    children = list(parent)
    if not children:
        parent.append(child)
        return
    last = children[-1]
    closing = last.tail                                  # indentation before </note>
    inner = children[-2].tail if len(children) > 1 else parent.text
    parent.append(child)
    last.tail = inner
    child.tail = closing


def colorize(notes: Iterable[Note]) -> int:
    """
    Color the notehead of every analyzed note (``color`` other than black).
    Returns the number of notes colored.
    """
    count = 0
    for note in notes:
        if note.element is None or note.color == DEFAULT_COLOR or note.is_rest:
            continue
        set_notehead_color(note.element, COLOR_CODES[note.color])
        count += 1
    logger.debug('Colored %d noteheads', count)
    return count


# ---------------------------------------------------------------------------
# Credit
# ---------------------------------------------------------------------------

def add_ispog_credit(score: etree._ElementTree | etree._Element) -> etree._Element:
    """
    Add ``Analyzed by ISPOG <version>`` as a page-1 credit, centered at the bottom of the
    page when the score defines its page size. Credits from earlier analyses (0.9
    included) are removed first, so the credit is never duplicated.
    """
    root = _root(score)
    for credit in root.iterfind('credit'):
        if credit.get('id') == CREDIT_ID or _credit_text(credit).startswith(CREDIT_PREFIX):
            _remove(credit)

    credit = etree.Element('credit', page='1', id=CREDIT_ID)
    words = etree.SubElement(credit, 'credit-words')
    words.text = f'{CREDIT_PREFIX} {__version__}'
    position = _footer_position(root)
    if position is not None:
        words.set('default-x', _tenths(position[0]))
        words.set('default-y', _tenths(position[1]))
    words.set('justify', 'center')
    words.set('valign', 'bottom')
    words.set('font-style', 'italic')
    words.set('font-size', '8')

    part_list = root.find('part-list')
    if part_list is None:
        raise ValueError('score without <part-list>')
    _insert_child(root, credit, before=part_list)
    indent = credit.tail if credit.tail and not credit.tail.strip() else None
    if indent:                                    # pretty-printed source: follow its layout
        credit.text = indent + '  '
        words.tail = indent
    return credit


def _credit_text(credit: etree._Element) -> str:
    return ''.join(w.text or '' for w in credit.iterfind('credit-words')).strip()


def _footer_position(root: etree._Element) -> Optional[tuple[float, float]]:
    """Bottom center of page 1, in tenths, inside the bottom margin."""
    layout = root.find('defaults/page-layout')
    if layout is None:
        return None
    try:
        width = float(layout.findtext('page-width'))
        margins = layout.find('page-margins')
        bottom = float(margins.findtext('bottom-margin')) if margins is not None else 0.0
    except (TypeError, ValueError):
        return None
    return width / 2, max(bottom / 2, 10.0)


def _tenths(value: float) -> str:
    return f'{value:.2f}'.rstrip('0').rstrip('.')


# ---------------------------------------------------------------------------
# Parts and serialization
# ---------------------------------------------------------------------------

def extract_part(tree: etree._ElementTree, part_id: str) -> etree._ElementTree:
    """
    A copy of the score containing only ``part_id``: other ``<part>`` and
    ``<score-part>`` elements and every ``<part-group>`` are removed; header and credits
    are kept. The input tree is not modified.

    Raises:
        ValueError: the score has no part ``part_id``.
    """
    result = copy.deepcopy(tree)
    root = result.getroot()
    if root.find(f"part[@id='{part_id}']") is None:
        raise ValueError(f'no part {part_id!r} in the score')
    for element in root.findall('part-list/*'):
        if element.tag == 'part-group' or element.get('id') != part_id:
            _remove(element)
    for part in root.findall('part'):
        if part.get('id') != part_id:
            _remove(part)
    return result


def serialize(tree: etree._ElementTree) -> bytes:
    """
    The score as UTF-8 bytes: XML declaration, the original DOCTYPE, the tree.
    The declaration uses double quotes, as notation programs write it.
    """
    body = etree.tostring(tree, encoding='UTF-8', xml_declaration=False)
    return XML_DECLARATION + body + b'\n'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _root(score: etree._ElementTree | etree._Element) -> etree._Element:
    return score.getroot() if isinstance(score, etree._ElementTree) else score


def _remove(element: etree._Element) -> None:
    """Remove an element and the indentation that preceded it."""
    parent = element.getparent()
    previous = element.getprevious()
    if previous is not None:
        previous.tail = element.tail
    else:
        parent.text = element.tail
    parent.remove(element)
