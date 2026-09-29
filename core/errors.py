# -*- coding: utf-8 -*-
"""
ISPOG - Errors
Typed exceptions raised by the core (plan, D7).

The core never shows dialogs: it raises one of these and the caller (desktop GUI or
web app) presents the message. Messages are user-facing, in English, and must make
sense without the traceback.
"""


class IspogError(Exception):
    """Base class for every error the user is expected to read."""


class UnsupportedFileError(IspogError):
    """The file is not a MusicXML score ISPOG can read."""


class NoGuitarPartError(IspogError):
    """The score has no guitar part and no part was selected explicitly."""
