# -*- coding: utf-8 -*-
"""
ISPOG - File I/O Utilities
Functions for loading and saving MusicXML files.
"""

import logging
from pathlib import Path
from typing import Optional
import tkinter.filedialog as fd
from tkinter.messagebox import showinfo

logger = logging.getLogger(__name__)


def load_musicxml(file_path: str) -> Optional[str]:
    """
    Load a MusicXML file and return its content.
    
    Args:
        file_path: Path to the MusicXML file
        
    Returns:
        File content as string, or None if error
    """
    logger.info(f"Loading MusicXML file: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        logger.info(f"Successfully loaded {len(content)} characters")
        return content
        
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        showinfo(
            title='File Error',
            message=f'File not found:\n{file_path}'
        )
        return None
        
    except UnicodeDecodeError:
        logger.error(f"Encoding error reading file: {file_path}")
        showinfo(
            title='File Error',
            message='File encoding error. Make sure it\'s a valid MusicXML file.'
        )
        return None
        
    except Exception as e:
        logger.error(f"Error loading file: {e}", exc_info=True)
        showinfo(
            title='File Error',
            message=f'Error loading file:\n{str(e)}'
        )
        return None


def save_musicxml(content: str, default_name: str = "output.musicxml") -> bool:
    """
    Save MusicXML content to file using file dialog.
    
    Args:
        content: MusicXML content to save
        default_name: Default filename suggestion
        
    Returns:
        True if saved successfully, False otherwise
    """
    logger.info("Opening save dialog")
    
    file_types = (
        ('MusicXML (uncompressed)', '*.musicxml'),
        ('All files', '*.*')
    )
    
    try:
        file = fd.asksaveasfile(
            title='Save MusicXML File',
            initialdir=Path.home(),
            initialfile=default_name,
            filetypes=file_types,
            defaultextension=".musicxml"
        )
        
        if file:
            file.write(content)
            file.close()
            
            logger.info(f"File saved successfully: {file.name}")
            showinfo(
                title='File Saved',
                message=f'File saved successfully:\n{Path(file.name).name}'
            )
            return True
        else:
            logger.info("Save cancelled by user")
            return False
            
    except Exception as e:
        logger.error(f"Error saving file: {e}", exc_info=True)
        showinfo(
            title='Save Error',
            message=f'Error saving file:\n{str(e)}'
        )
        return False
