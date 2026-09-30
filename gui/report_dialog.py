# -*- coding: utf-8 -*-
"""
ISPOG - Report dialog
The tester decides what to send and presses Send; nothing leaves the computer otherwise.
Sending runs in a worker thread (no Tk calls there); the dialog polls its outcome. If the
report cannot be sent, the tester can send an e-mail instead.
"""

import dataclasses
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional

from config.settings import UI_TEXT
from core.bugreport import ReportContent, mailto_url, send
from utils.io import log_dir
from utils.logger import get_logger
from .dialogs import open_folder

logger = get_logger(__name__)


class ReportDialog(tk.Toplevel):
    """Consent and sending of a bug report."""

    POLL_MS = 100

    def __init__(self, parent: tk.Misc, content: ReportContent,
                 analysis_files: Optional[dict[str, bytes]] = None,
                 score_file: Optional[Path] = None,
                 sender: Callable[[ReportContent], None] = send):
        super().__init__(parent)
        self.title(UI_TEXT['report_title'])
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)

        self._content = content
        self._analysis_files = analysis_files or {}
        self._score_file = score_file
        self._sender = sender
        self.include_analysis = tk.BooleanVar(self, bool(self._analysis_files))
        self.include_score = tk.BooleanVar(self, False)
        self.email = tk.StringVar(self, content.email)
        self.status_text = tk.StringVar(self, '')

        self._build()
        try:
            self.grab_set()                          # modal: the main window waits
        except tk.TclError:                          # not viewable yet (e.g. hidden parent)
            logger.debug('Report dialog shown without grab')
        self.comment.focus_set()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill='both', expand=True)
        wrap = 300

        ttk.Label(frame, text=UI_TEXT['report_intro'], wraplength=wrap).pack(anchor='w')
        ttk.Label(frame, text=UI_TEXT['report_always'], wraplength=wrap,
                  foreground='gray').pack(anchor='w', pady=(4, 6))

        ttk.Checkbutton(frame, text=UI_TEXT['report_analysis'], variable=self.include_analysis,
                        state='normal' if self._analysis_files else 'disabled').pack(anchor='w')
        score_text = UI_TEXT['report_score']
        if self._score_file is not None:
            score_text += f' ({self._score_file.name})'
        ttk.Checkbutton(frame, text=score_text, variable=self.include_score,
                        state='normal' if self._score_file else 'disabled').pack(anchor='w')

        ttk.Label(frame, text=UI_TEXT['report_email']).pack(anchor='w', pady=(8, 0))
        ttk.Entry(frame, textvariable=self.email, width=40).pack(fill='x')
        ttk.Label(frame, text=UI_TEXT['report_comment']).pack(anchor='w', pady=(8, 0))
        self.comment = tk.Text(frame, width=40, height=5, wrap='word')
        self.comment.pack(fill='x')

        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(10, 0))
        ttk.Label(buttons, textvariable=self.status_text, foreground='gray').pack(side='left')
        ttk.Button(buttons, text='Cancel', command=self.destroy).pack(side='right')
        self.send_button = ttk.Button(buttons, text=UI_TEXT['report_send'], command=self._send)
        self.send_button.pack(side='right', padx=(0, 6))

    def final_content(self) -> ReportContent:
        """The report as the tester set it up in the dialog."""
        return dataclasses.replace(
            self._content,
            email=self.email.get().strip(),
            comment=self.comment.get('1.0', 'end').strip(),
            score_file=self._score_file if self.include_score.get() else None,
            analysis_files=self._analysis_files if self.include_analysis.get() else {},
        )

    def _send(self) -> None:
        content = self.final_content()
        self.send_button.config(state='disabled')
        self.status_text.set(UI_TEXT['report_sending'])
        outcome: queue.Queue = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                self._sender(content)
                outcome.put(None)
            except Exception as e:                   # shown to the tester, with a fallback
                logger.warning(f'Bug report not sent: {e}')
                outcome.put(e)

        threading.Thread(target=worker, daemon=True).start()
        self._poll(content, outcome)

    def _poll(self, content: ReportContent, outcome: queue.Queue) -> None:
        try:
            error = outcome.get_nowait()
        except queue.Empty:
            self.after(self.POLL_MS, self._poll, content, outcome)
            return
        if error is None:
            messagebox.showinfo(title=UI_TEXT['report_title'], message=UI_TEXT['report_sent'],
                                parent=self)
        elif messagebox.askyesno(title=UI_TEXT['report_title'],
                                 message=UI_TEXT['report_failed'].format(error=error),
                                 parent=self):
            webbrowser.open(mailto_url(content))
            open_folder(log_dir())
        self.destroy()
