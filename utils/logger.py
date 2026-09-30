# -*- coding: utf-8 -*-
"""
ISPOG - Logging Utilities
Provides logging functionality for all modules.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import LOG_FORMAT, LOG_DATE_FORMAT
from utils.io import log_dir as _log_dir


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger for a module.
    
    Args:
        name: Module name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def setup_file_logging(level: int = logging.DEBUG) -> Path:
    """
    Setup file logging for the application.
    Called once at startup from main.py.
    
    Args:
        level: Logging level (default: DEBUG)
        
    Returns:
        Path to the log file
    """
    # Create logs directory
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'ispog_{timestamp}.log'
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Log startup info
    logger = get_logger(__name__)
    logger.info('=' * 60)
    logger.info('ISPOG Logging initialized')
    logger.info(f'Log file: {log_file}')
    logger.info('=' * 60)
    
    return log_file


def current_log_file() -> Optional[Path]:
    """The file the root logger writes to, if ``setup_file_logging`` was called."""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler):
            return Path(handler.baseFilename)
    return None
