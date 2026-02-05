# -*- coding: utf-8 -*-
"""
ISPOG - Is it Playable on Guitar?
Main entry point for the application.
"""

import sys
import traceback
from tkinter import messagebox

from gui import MainWindow
from utils import setup_file_logging, get_logger

# Metadata
__version__ = '0.9.0'
__status__ = 'alpha'
__date__ = '2026-01-09'
__author__ = 'Stefano Mancuso'


def main():
    """Initialize and run the application."""
    # Setup logging first
    log_file = setup_file_logging()
    logger = get_logger(__name__)
    
    version_string = f'{__version__}-{__status__} ({__date__})'
    
    try:
        logger.info(f'ISPOG v{version_string} started')
        logger.info('Initializing GUI...')
        
        # Create main window
        root = MainWindow()
        root.set_version(version_string)
        
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
        except:
            logger.error('Could not show error dialog')
        
        sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info('Application interrupted by user (Ctrl+C)')
        sys.exit(0)


if __name__ == '__main__':
    main()
