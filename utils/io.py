# -*- coding: utf-8 -*-
"""
ISPOG - File I/O Utilities
Functions for loading and saving MusicXML files.
"""

import logging
import os
import zipfile
import tempfile
import sys
from pathlib import Path
from typing import Optional
import tkinter.filedialog as fd
from tkinter.messagebox import showinfo

logger = logging.getLogger(__name__)


def load_musicxml(file_path: str) -> Optional[str]:
    """
    Load a MusicXML file and return its content.
    Supports both .musicxml (uncompressed) and .mxl (compressed) formats.
    
    Args:
        file_path: Path to the MusicXML file
        
    Returns:
        File content as string, or None if error
    """
    logger.info(f"Loading MusicXML file: {file_path}")
    
    try:
        # Check if it's a compressed file (.mxl)
        if file_path.lower().endswith('.mxl'):
            return _load_compressed_mxl(file_path)
        else:
            return _load_uncompressed_musicxml(file_path)
        
    except Exception as e:
        logger.error(f"Error loading file: {e}", exc_info=True)
        showinfo(
            title='File Error',
            message=f'Error loading file:\n{str(e)}'
        )
        return None


def _load_uncompressed_musicxml(file_path: str) -> str:
    """Load uncompressed .musicxml file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    logger.info(f"Successfully loaded {len(content)} characters")
    return content


def _load_compressed_mxl(file_path: str) -> str:
    """
    Load and decompress .mxl file.
    
    MXL files are ZIP archives containing:
    - META-INF/container.xml (points to the main .musicxml file)
    - One or more .musicxml files
    """
    logger.info(f"Decompressing MXL file: {file_path}")
    
    with zipfile.ZipFile(file_path, 'r') as zip_file:
        # Find the main musicxml file
        # Usually it's referenced in META-INF/container.xml
        musicxml_file = None
        
        # Try to read container.xml
        try:
            container = zip_file.read('META-INF/container.xml').decode('utf-8')
            # Extract rootfile path from container.xml
            import re
            match = re.search(r'full-path="([^"]+\.musicxml)"', container)
            if match:
                musicxml_file = match.group(1)
                logger.debug(f"Found main file in container: {musicxml_file}")
        except KeyError:
            logger.warning("No container.xml found, searching for .musicxml")
        
        # Fallback: find first .musicxml file
        if not musicxml_file:
            for name in zip_file.namelist():
                if name.endswith('.musicxml'):
                    musicxml_file = name
                    logger.debug(f"Using first .musicxml found: {musicxml_file}")
                    break
        
        if not musicxml_file:
            raise ValueError("No .musicxml file found in .mxl archive")
        
        # Extract and read the musicxml content
        content = zip_file.read(musicxml_file).decode('utf-8')
        logger.info(f"Successfully decompressed {len(content)} characters")
        return content


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
    
def resource_path(relative_path: str) -> Path:
    """Path per risorse bundlate (read-only)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(relative_path)

def writable_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        app_data = Path(os.environ.get("APPDATA", Path.home())) / "ISPOG"
        app_data.mkdir(exist_ok=True)
        return app_data / relative_path
    return Path(relative_path)