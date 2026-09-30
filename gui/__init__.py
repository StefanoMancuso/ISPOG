# -*- coding: utf-8 -*-
"""
GUI package for ISPOG.

Widgets are imported on first use, so that modules without Tkinter (``gui.outputs``) can
be imported, and tested, where Tkinter is not installed.
"""

__all__ = ['MainWindow', 'FileSelectorWidget', 'TuningWidget', 'PartSelectorWidget',
           'ProcessButton']


def __getattr__(name: str):
    if name == 'MainWindow':
        from .main_window import MainWindow
        return MainWindow
    if name in __all__:
        from . import widgets
        return getattr(widgets, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
