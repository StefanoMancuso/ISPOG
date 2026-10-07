# -*- coding: utf-8 -*-
"""
ISPOG - Version
Single source of the application version (PEP 440).

Read by main.py (window title), pyproject.toml (dynamic version), the report, the score
credit, bug reports, the log, the PyInstaller spec and the web app. Keep this module free
of imports: setuptools reads it statically.

Between releases the version carries a ``.devN`` suffix; the release commit removes it
and updates CHANGELOG.md and CITATION.cff (checked by tests/test_meta.py).
"""

__version__ = "0.10.0b4.dev0"
