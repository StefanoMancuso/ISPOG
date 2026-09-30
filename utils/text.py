# -*- coding: utf-8 -*-
"""ISPOG - Text helpers for display."""


def shorten(text: str, max_chars: int) -> str:
    """``text`` cut in the middle with an ellipsis if longer than ``max_chars``."""
    if len(text) <= max_chars:
        return text
    head = (max_chars - 1) // 2
    tail = max_chars - 1 - head
    return f'{text[:head]}…{text[len(text) - tail:]}'
