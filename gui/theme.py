# -*- coding: utf-8 -*-
"""
ISPOG - Look of the desktop window
One light theme on every system (ttk "clam" with the colors below), the same as the
MuseScore plugin: white cards on a light grey window, one accent color, the notehead
colors of the analysis in the problem list.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from config.settings import COLOR_CODES

WINDOW = '#f5f5f5'
CARD = '#ffffff'
BORDER = '#c8c8c8'
TEXT = '#1e1e1e'
MUTED = '#6b6b6b'
ACCENT = '#2e6db4'
ACCENT_ACTIVE = '#255a96'
ERROR = '#b00020'
WARNING = '#b35c00'
SELECTION = '#dbe7f6'

# Problem list: one color per status (the notehead colors)
STATUS_COLORS = {color: COLOR_CODES[color] for color in ('orange', 'red', 'purple')}

PAD = 10                                   # outer padding of the window and of the cards


def apply_theme(root: tk.Tk) -> ttk.Style:
    """Configure the ttk styles used by the window; returns the style object."""
    style = ttk.Style(root)
    style.theme_use('clam')
    root.configure(background=WINDOW)

    base = tkfont.nametofont('TkDefaultFont')
    size = base.cget('size') or 10                # negative: pixels, positive: points
    bold = base.copy()
    bold.configure(weight='bold')
    title = base.copy()
    title.configure(size=round(size * 1.4), weight='bold')
    small = base.copy()
    small.configure(size=max(size - 1, 8) if size > 0 else min(size + 1, -10))
    root._ispog_fonts = (bold, title, small)      # keep references: fonts die with them

    style.configure('.', background=WINDOW, foreground=TEXT, bordercolor=BORDER,
                    focuscolor=ACCENT, lightcolor=WINDOW, darkcolor=WINDOW)
    style.configure('TFrame', background=WINDOW)
    style.configure('TLabel', background=WINDOW, foreground=TEXT)
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Small.TLabel', foreground=MUTED, font=small)
    style.configure('Title.TLabel', font=title)
    style.configure('Section.TLabel', font=bold)
    style.configure('Error.TLabel', foreground=ERROR)
    style.configure('Warning.TLabel', foreground=WARNING)

    style.configure('Card.TFrame', background=CARD, relief='solid', borderwidth=1)
    style.configure('Plain.TFrame', background=CARD, relief='flat', borderwidth=0)
    style.configure('Card.TLabel', background=CARD)
    style.configure('CardMuted.TLabel', background=CARD, foreground=MUTED)
    style.configure('CardError.TLabel', background=CARD, foreground=ERROR)
    style.configure('Card.TCheckbutton', background=CARD, font=bold)
    style.map('Card.TCheckbutton', background=[('active', CARD)])
    style.configure('Other.TCheckbutton', background=CARD, foreground=MUTED)
    style.map('Other.TCheckbutton', background=[('active', CARD)])
    style.configure('Card.TRadiobutton', background=CARD)
    style.map('Card.TRadiobutton', background=[('active', CARD)])
    style.configure('Option.TCheckbutton', background=CARD)
    style.map('Option.TCheckbutton', background=[('active', CARD)])

    style.configure('TButton', padding=(10, 4), background='#e8e8e8')
    style.map('TButton', background=[('active', '#dcdcdc'), ('disabled', '#efefef')])
    style.configure('Accent.TButton', padding=(14, 6), background=ACCENT, foreground='#ffffff',
                    font=bold, bordercolor=ACCENT_ACTIVE)
    style.map('Accent.TButton', background=[('active', ACCENT_ACTIVE), ('disabled', '#9fb7d6')],
              foreground=[('disabled', '#eef2f8')])

    style.configure('TEntry', fieldbackground=CARD, padding=3)
    style.configure('Invalid.TEntry', fieldbackground='#fdecee', foreground=ERROR)
    style.configure('TSpinbox', fieldbackground=CARD, padding=2, arrowsize=10)
    style.configure('TCombobox', fieldbackground=CARD, padding=2)
    style.map('TCombobox', fieldbackground=[('readonly', CARD)])

    style.configure('TNotebook', background=WINDOW, borderwidth=0)
    style.configure('TNotebook.Tab', padding=(12, 4), background='#e8e8e8')
    style.map('TNotebook.Tab', background=[('selected', CARD)])

    style.configure('Treeview', background=CARD, fieldbackground=CARD, rowheight=int(
        tkfont.Font(font=base).metrics('linespace') * 1.6), borderwidth=0)
    style.configure('Treeview.Heading', background='#ececec', font=bold, relief='flat')
    style.map('Treeview', background=[('selected', SELECTION)], foreground=[('selected', TEXT)])

    style.configure('TProgressbar', background=ACCENT, troughcolor='#e3e3e3')
    style.configure('TScrollbar', background='#e3e3e3', troughcolor=WINDOW, arrowcolor=MUTED)
    return style


def fonts(root: tk.Misc) -> tuple:
    """(bold, title, small) fonts created by ``apply_theme``."""
    return root.winfo_toplevel()._ispog_fonts


def monospace() -> tkfont.Font:
    return tkfont.nametofont('TkFixedFont')
