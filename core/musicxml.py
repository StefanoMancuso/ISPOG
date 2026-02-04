# -*- coding: utf-8 -*-
"""
ISPOG - MusicXML Processing
Functions for parsing, processing, and writing MusicXML files.
"""

import re
import logging
from typing import Tuple, Dict, List

from core.entities import Note, Bar, newNote
from core.analyzer import ChordAnalyzer

# Import color codes
try:
    from config.settings import COLOR_CODES
except ImportError:
    COLOR_CODES = {
        'red': '"#cf0000"',
        'green': '"#005000"',
        'orange': '"#ff8c00"',
        'black': '"#000000"'
    }

logger = logging.getLogger(__name__)


# ============================================================================
# MUSICXML PARSING
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
        parts = re.split('<part-list', xml_content, maxsplit=1)
        
        if len(parts) != 2:
            logger.warning("Could not find <part-list tag, credit not added")
            return xml_content
        
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
        return xml_content


def parse_measures(xml_content: str, fretboard_matrix: List[List[str]]) -> Tuple[List[Bar], List[str]]:
    """
    Parse MusicXML into bar objects.
    
    Args:
        xml_content: MusicXML file content
        fretboard_matrix: Fretboard matrix for note positioning
        
    Returns:
        Tuple of (bar objects list, raw measure strings list)
    """
    logger.info("Parsing measures from MusicXML")
    
    measure_strings = re.split('<measure ', xml_content)
    header = measure_strings[0]
    measures = measure_strings[1:]
    
    logger.info(f"Found {len(measures)} measures")
    
    bar_objects = []
    for i, measure_str in enumerate(measures, start=1):
        try:
            bar_obj = Bar(i, measure_str, fretboard_matrix)
            bar_objects.append(bar_obj)
        except Exception as e:
            logger.error(f"Error parsing measure {i}: {e}", exc_info=True)
    
    logger.info(f"Successfully parsed {len(bar_objects)} bar objects")
    return bar_objects, [header] + measures


def merge_bars_to_score(bars: List[Bar]) -> Dict[int, List[Note]]:
    """
    Merge all bars into a single continuous score with proper voice handling.
    Adds rests where needed to align voices.
    
    Args:
        bars: List of bar objects
        
    Returns:
        Dictionary mapping voice number to list of notes
    """
    logger.info(f"Merging {len(bars)} bars into continuous score")
    
    score: Dict[int, List[Note]] = {1: [], 2: [], 3: [], 4: []}
    
    for bar in bars:
        bar_score = bar.getScoreMatrix()
        
        # Calculate max duration in this bar
        durations = [0.0, 0.0, 0.0, 0.0]
        
        for voice in range(1, 5):
            if voice in bar_score:
                for note in bar_score[voice]:
                    if not note.isChord():
                        durations[voice - 1] += note.getValue()
        
        max_duration = max(durations)
        logger.debug(f"Bar max duration: {max_duration}")
        
        # Add notes and fill gaps with rests
        for voice in range(1, 5):
            if voice in bar_score:
                voice_duration = 0.0
                for note in bar_score[voice]:
                    score[voice].append(note)
                    if not note.isChord():
                        voice_duration += note.getValue()
                
                # Add rest if needed
                if voice_duration < max_duration:
                    rest_duration = max_duration - voice_duration
                    rest = newNote({
                        'pitch': ['rest', '0'],
                        'value': rest_duration,
                        'voice': voice
                    })
                    score[voice].append(rest)
            else:
                # Full rest for this voice
                rest = newNote({
                    'pitch': ['rest', '0'],
                    'value': max_duration,
                    'voice': voice
                })
                score[voice].append(rest)
    
    for voice in range(1, 5):
        logger.info(f"Voice {voice}: {len(score[voice])} notes")
    
    return score


# ============================================================================
# PLAYABILITY ANALYSIS
# ============================================================================

def analyze_chord_playability(notes: List[Note]) -> None:
    """
    Analyze chord playability and color notes accordingly.
    Uses ChordAnalyzer.
    
    Args:
        notes: List of concurrent notes to analyze
    """
    analyzer = ChordAnalyzer()
    analyzer.analyze_chord(notes)


def analyze_score_playability(score: Dict[int, List[Note]]) -> None:
    """
    Analyze entire score for playability by finding concurrent notes.
    
    Args:
        score: Dictionary mapping voice to note list
    """
    logger.info("Analyzing score playability")
    
    voice_indices = {1: 0, 2: 0, 3: 0, 4: 0}
    voice_times = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    voices_finished = 0
    current_time = 0.0
    
    while voices_finished < 4:
        concurrent_notes: List[Note] = []
        
        for voice in range(1, 5):
            if voice_indices[voice] >= len(score[voice]):
                if voice_indices[voice] == len(score[voice]):
                    voices_finished += 1
                    voice_indices[voice] += 1
                continue
            
            if abs(voice_times[voice] - current_time) < 0.001:
                note = score[voice][voice_indices[voice]]
                concurrent_notes.append(note)
                
                if not note.isChord():
                    voice_times[voice] += note.getValue()
                voice_indices[voice] += 1
                
                # Check for chord notes
                while voice_indices[voice] < len(score[voice]):
                    next_note = score[voice][voice_indices[voice]]
                    if next_note.isChord():
                        concurrent_notes.append(next_note)
                        voice_indices[voice] += 1
                    else:
                        break
        
        if concurrent_notes:
            logger.debug(f"Time {current_time}: {len(concurrent_notes)} concurrent notes")
            analyze_chord_playability(concurrent_notes)
        
        if voices_finished < 4:
            next_times = [voice_times[v] for v in range(1, 5) 
                         if voice_indices[v] < len(score[v])]
            if next_times:
                current_time = min(next_times)
            else:
                break
    
    logger.info("Playability analysis complete")


# ============================================================================
# MUSICXML OUTPUT
# ============================================================================

def write_colored_score(original_measures: List[str], bars: List[Bar]) -> str:
    """
    Reconstruct MusicXML with note colors applied.
    
    Args:
        original_measures: Original measure strings (includes header at [0])
        bars: Bar objects with colored notes
        
    Returns:
        Complete MusicXML string with colors
    """
    logger.info("Writing colored score to MusicXML")
    
    output = original_measures[0]
    
    for i, bar_obj in enumerate(bars, start=1):
        measure_str = bar_obj.getScore()
        notes = bar_obj.getNotes()
        
        note_parts = re.split('<note ', measure_str)
        output += '<measure ' + note_parts[0]
        
        for j in range(1, len(note_parts)):
            note_str = note_parts[j]
            
            if '<rest' in note_str:
                output += '<note ' + note_str
                continue
            
            if j - 1 < len(notes):
                note_obj = notes[j - 1]
                color = note_obj.getColor()
                color_code = COLOR_CODES.get(color, COLOR_CODES['black'])
                
                parts = re.split('</note', note_str)
                if len(parts) == 2:
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

def remove_file_extension(filepath: str) -> str:
    """Remove .musicxml extension from filepath."""
    return re.split(r'\.musicxml', filepath)[0]


def create_debug_note_list(score: Dict[int, List[Note]], output_path: str) -> None:
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

# Keep old names for backward compatibility
makeBarList = parse_measures
mergeBarList = merge_bars_to_score
makeColor = analyze_score_playability
rewriteScore = write_colored_score  # Note: returns string, doesn't save
addMark = add_ispog_credit
noExtension = remove_file_extension
debugNoteList = create_debug_note_list
colorChord = analyze_chord_playability
