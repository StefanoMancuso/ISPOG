# -*- coding: utf-8 -*-
"""
ISPOG - Core Functions
Refactored professional version with proper logging and modular structure.
"""

import re
import logging
from pathlib import Path
from typing import Tuple, Dict, List, Optional
import tkinter.filedialog as fd
from tkinter.messagebox import showinfo

from entity import nota, bar, fretboard
from chord_analyzer import ChordAnalyzer
from config.settings import COLOR_CODES

logger = logging.getLogger(__name__)


# ============================================================================
# FILE I/O FUNCTIONS
# ============================================================================

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


# ============================================================================
# MUSICXML PROCESSING
# ============================================================================

def add_ispog_credit(xml_content: str) -> str:
    """
    Add ISPOG credit mark to MusicXML header.
    
    Args:
        xml_content: Original MusicXML content
        
    Returns:
        Modified XML with credit added
    """
    logger.debug("Adding ISPOG credit to MusicXML")
    
    try:
        # Split at <part-list
        parts = re.split('<part-list', xml_content, maxsplit=1)
        
        if len(parts) != 2:
            logger.warning("Could not find <part-list tag, credit not added")
            return xml_content
        
        # Add credit
        credit = (
            '  <credit page="1">'
            '<credit-words default-x="600.24" default-y="507.692243" '
            'justify="center" valign="middle" font-style="italic" font-size="20">'
            'Analyzed by ISPOG'
            '</credit-words></credit>\n'
        )
        
        result = parts[0] + credit + '  <part-list' + parts[1]
        logger.debug("Credit added successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error adding credit: {e}", exc_info=True)
        return xml_content  # Return original on error


def parse_measures(xml_content: str, fretboard_matrix: List[List[str]]) -> Tuple[List[bar], List[str]]:
    """
    Parse MusicXML into bar objects.
    
    Args:
        xml_content: MusicXML file content
        fretboard_matrix: Fretboard matrix for note positioning
        
    Returns:
        Tuple of (bar objects list, raw measure strings list)
    """
    logger.info("Parsing measures from MusicXML")
    
    # Split into measures
    measure_strings = re.split('<measure ', xml_content)
    
    # First element is header (before first measure)
    header = measure_strings[0]
    measures = measure_strings[1:]
    
    logger.info(f"Found {len(measures)} measures")
    
    # Create bar objects
    bar_objects = []
    for i, measure_str in enumerate(measures, start=1):
        try:
            bar_obj = bar(i, measure_str, fretboard_matrix)
            bar_objects.append(bar_obj)
        except Exception as e:
            logger.error(f"Error parsing measure {i}: {e}", exc_info=True)
    
    logger.info(f"Successfully parsed {len(bar_objects)} bar objects")
    
    # Return full list including header for reconstruction
    return bar_objects, [header] + measures


def merge_bars_to_score(bars: List[bar]) -> Dict[int, List[nota]]:
    """
    Merge all bars into a single continuous score with proper voice handling.
    Adds rests where needed to align voices.
    
    Args:
        bars: List of bar objects
        
    Returns:
        Dictionary mapping voice number to list of notes
    """
    logger.info(f"Merging {len(bars)} bars into continuous score")
    
    # Initialize score for 4 voices
    score: Dict[int, List[nota]] = {1: [], 2: [], 3: [], 4: []}
    
    for bar in bars:
        bar_score = bar.getScoreMatrix()
        
        # Calculate max duration in this bar across all voices
        durations = [0.0, 0.0, 0.0, 0.0]
        
        for voice in range(1, 5):
            if voice in bar_score:
                for note in bar_score[voice]:
                    if not note.isChord():  # Don't count chord notes in duration
                        durations[voice - 1] += note.getValue()
        
        max_duration = max(durations)
        logger.debug(f"Bar max duration: {max_duration}, voice durations: {durations}")
        
        # Add notes and fill gaps with rests
        for voice in range(1, 5):
            if voice in bar_score:
                # Add real notes
                voice_duration = 0.0
                for note in bar_score[voice]:
                    score[voice].append(note)
                    if not note.isChord():
                        voice_duration += note.getValue()
                
                # Add rest if this voice is shorter than max
                if voice_duration < max_duration:
                    from entity import newNote
                    rest_duration = max_duration - voice_duration
                    rest = newNote({
                        'pitch': ['rest', '0'],
                        'value': rest_duration,
                        'voice': voice
                    })
                    score[voice].append(rest)
                    logger.debug(f"Added rest of duration {rest_duration} to voice {voice}")
            else:
                # No notes in this voice for this bar - add full rest
                from entity import newNote
                rest = newNote({
                    'pitch': ['rest', '0'],
                    'value': max_duration,
                    'voice': voice
                })
                score[voice].append(rest)
    
    # Log final statistics
    for voice in range(1, 5):
        logger.info(f"Voice {voice}: {len(score[voice])} notes")
    
    return score


# ============================================================================
# PLAYABILITY ANALYSIS
# ============================================================================

def analyze_chord_playability(notes: List[nota]) -> None:
    """
    Analyze chord playability and color notes accordingly.
    Uses the professional ChordAnalyzer.
    
    Args:
        notes: List of concurrent notes to analyze
    """
    analyzer = ChordAnalyzer()
    analyzer.analyze_chord(notes)


def analyze_score_playability(score: Dict[int, List[nota]]) -> None:
    """
    Analyze entire score for playability by finding concurrent notes.
    
    This function walks through the score timeline and identifies which
    notes are playing simultaneously, then analyzes each chord.
    
    Args:
        score: Dictionary mapping voice to note list
    """
    logger.info("Analyzing score playability")
    
    # Track current position in each voice
    voice_indices = {1: 0, 2: 0, 3: 0, 4: 0}
    voice_times = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    
    # Track when voices finish
    voices_finished = 0
    current_time = 0.0
    
    while voices_finished < 4:
        # Collect concurrent notes
        concurrent_notes: List[nota] = []
        
        for voice in range(1, 5):
            # Skip if this voice is finished
            if voice_indices[voice] >= len(score[voice]):
                if voice_indices[voice] == len(score[voice]):
                    voices_finished += 1
                    voice_indices[voice] += 1  # Mark as counted
                continue
            
            # If this voice is at current time, include its note
            if abs(voice_times[voice] - current_time) < 0.001:  # Float comparison
                note = score[voice][voice_indices[voice]]
                concurrent_notes.append(note)
                
                # Advance this voice if not a chord continuation
                if not note.isChord():
                    voice_times[voice] += note.getValue()
                voice_indices[voice] += 1
                
                # Check for chord notes (consecutive notes with isChord=True)
                while voice_indices[voice] < len(score[voice]):
                    next_note = score[voice][voice_indices[voice]]
                    if next_note.isChord():
                        concurrent_notes.append(next_note)
                        voice_indices[voice] += 1
                    else:
                        break
        
        # Analyze this chord
        if concurrent_notes:
            logger.debug(f"Time {current_time}: analyzing {len(concurrent_notes)} concurrent notes")
            analyze_chord_playability(concurrent_notes)
        
        # Advance to next event time
        if voices_finished < 4:
            next_times = [voice_times[v] for v in range(1, 5) 
                         if voice_indices[v] < len(score[v])]
            if next_times:
                current_time = min(next_times)
            else:
                break
    
    logger.info("Playability analysis complete")


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def write_colored_score(original_measures: List[str], bars: List[bar]) -> str:
    """
    Reconstruct MusicXML with note colors applied.
    
    Args:
        original_measures: Original measure strings (includes header at [0])
        bars: Bar objects with colored notes
        
    Returns:
        Complete MusicXML string with colors
    """
    logger.info("Writing colored score to MusicXML")
    
    # Start with header
    output = original_measures[0]
    
    # Process each measure
    for i, bar_obj in enumerate(bars, start=1):
        measure_str = bar_obj.getScore()
        notes = bar_obj.getNotes()
        
        # Split measure into notes
        note_parts = re.split('<note ', measure_str)
        
        # Reconstruct with colors
        output += '<measure ' + note_parts[0]
        
        for j in range(1, len(note_parts)):
            note_str = note_parts[j]
            
            # Check if this is a rest (skip coloring)
            if '<rest' in note_str:
                output += '<note ' + note_str
                continue
            
            # Get corresponding note object
            if j - 1 < len(notes):
                note_obj = notes[j - 1]
                color = note_obj.getColor()
                color_code = COLOR_CODES.get(color, COLOR_CODES['black'])
                
                # Split at </note> to insert color
                parts = re.split('</note', note_str)
                if len(parts) == 2:
                    # Insert notehead color before </note>
                    colored = (
                        parts[0] + 
                        f'<notehead color={color_code}>normal</notehead>\n\t\t\t\t'
                        '</note' + parts[1]
                    )
                    output += '<note ' + colored
                else:
                    output += '<note ' + note_str
            else:
                output += '<note ' + note_str
    
    logger.info("Colored score written successfully")
    return output


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_fretboard_matrix(num_strings: int, num_frets: int, tuning: List[str]) -> List[List[str]]:
    """
    Generate fretboard matrix for note positioning.
    
    Args:
        num_strings: Number of guitar strings
        num_frets: Number of frets
        tuning: List of tuning notes (e.g., ['E4', 'B3', 'G3', ...])
        
    Returns:
        Fretboard matrix
    """
    logger.debug(f"Generating fretboard: {num_strings} strings, {num_frets} frets")
    fb = fretboard(num_strings, num_frets, tuning)
    return fb.getMatrix()


def remove_file_extension(filepath: str) -> str:
    """
    Remove .musicxml extension from filepath.
    
    Args:
        filepath: Path to file
        
    Returns:
        Path without extension
    """
    return re.split(r'\.musicxml', filepath)[0]


def create_debug_note_list(score: Dict[int, List[nota]], output_path: str) -> None:
    """
    Create debug file listing all notes with their properties.
    
    Args:
        score: Score dictionary (voice -> notes)
        output_path: Base path for output file
    """
    logger.info("Creating debug note list")
    
    debug_file = remove_file_extension(output_path) + '_noteList.txt'
    
    try:
        with open(debug_file, 'w', encoding='utf-8') as f:
            for voice in range(1, 5):
                f.write(f'VOICE {voice}:\n')
                f.write('=' * 80 + '\n')
                
                for note in score[voice]:
                    try:
                        f.write(
                            f'Pitch: {note.getPitch()}, '
                            f'Value: {note.getValue()}, '
                            f'Fret: {note.getFret()}, '
                            f'Color: {note.getColor()}, '
                            f'IsChord: {note.isChord()}\n'
                        )
                    except Exception as e:
                        f.write(f'ERROR: {e}\n')
                
                f.write('\n\n')
        
        logger.info(f"Debug file created: {debug_file}")
        
    except Exception as e:
        logger.error(f"Error creating debug file: {e}", exc_info=True)


# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

def rewriteScore_legacy(score: List[str], barList: List[bar]) -> None:
    """
    Legacy wrapper for rewriteScore that maintains old behavior.
    Writes colored score AND saves it with dialog.
    
    Args:
        score: Original measure strings (includes header at [0])
        barList: Bar objects with colored notes
    """
    logger.info("rewriteScore (legacy mode) - write and save")
    
    # Generate colored score
    colored_xml = write_colored_score(score, barList)
    
    # Auto-save with dialog
    save_musicxml(colored_xml, "analyzed.musicxml")


# Keep old function names for backward compatibility
leggifile = load_musicxml
saveFile = save_musicxml
addMark = add_ispog_credit
makeBarList = parse_measures
mergeBarList = merge_bars_to_score
makeColor = analyze_score_playability
rewriteScore = rewriteScore_legacy  # ← Usa wrapper che salva!
fbMatrix = lambda n, f: None  # Deprecated
noExtension = remove_file_extension
debugNoteList = create_debug_note_list
colorChord = analyze_chord_playability


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == '__main__':
    # Test with a sample file
    print("functions.py loaded successfully")
    print(f"Color codes: {COLOR_CODES}")
    print(f"Orange color available: {'orange' in COLOR_CODES}")
