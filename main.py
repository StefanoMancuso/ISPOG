# -*- coding: utf-8 -*-
"""
ISPOG - Is it Playable on Guitar?
Main entry point for the application.

    python main.py [score]
    python main.py --self-test [report.json]

A score given on the command line is loaded at start-up: this is also what happens when a
file is dropped on the program icon or opened with "Open with" (Windows). On macOS the
Finder sends the file as an event instead (see ``MainWindow``).

``--self-test`` checks the installation without showing a window (``gui/selftest.py``);
the release workflow runs it on every executable.
"""

import sys
import traceback
from pathlib import Path
from tkinter import messagebox

from config.version import __version__
from utils import setup_file_logging, get_logger

SELF_TEST = '--self-test'

__author__ = 'Stefano Mancuso'


def self_test(args: list[str]) -> int:
    """Exit code of the self-test; never raises (a windowed executable would show a dialog)."""
    try:
        setup_file_logging()
        from gui.selftest import run_self_test
        return run_self_test(Path(args[0]) if args else None)
    except BaseException:
        traceback.print_exc()
        return 1


def main():
    """Initialize and run the application."""
    if sys.argv[1:2] == [SELF_TEST]:
        sys.exit(self_test(sys.argv[2:]))

    # Setup logging first
    log_file = setup_file_logging()
    logger = get_logger(__name__)
    
    try:
        from gui import MainWindow

        logger.info(f'ISPOG {__version__} started')
        logger.info('Initializing GUI...')
        
        # Create main window
        root = MainWindow()
        root.set_version(__version__)
        if len(sys.argv) > 1:
            score = Path(sys.argv[1])
            logger.info(f'Score from the command line: {score}')
            root.after_idle(root.file_selector.load, score)
        
        logger.info('Starting main loop...')
        root.mainloop()
        
        logger.info('Application closed normally')
        
    except Exception as e:
        # Log complete error
        logger.critical('CRITICAL ERROR DURING EXECUTION', exc_info=True)
        
        # User-friendly message
        error_msg = (
            f"A critical error occurred:\n\n"
            f"{type(e).__name__}: {str(e)}\n\n"
            f"Check the log file for details:\n{log_file}"
        )
        
        print("\n" + "="*60)
        print("CRITICAL ERROR:")
        print("="*60)
        traceback.print_exc()
        print("="*60 + "\n")
        
        try:
            messagebox.showerror("ISPOG - Critical Error", error_msg)
        except Exception:
            logger.error('Could not show error dialog', exc_info=True)
        
        sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info('Application interrupted by user (Ctrl+C)')
        sys.exit(0)


if __name__ == '__main__':
    main()
