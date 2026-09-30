# -*- coding: utf-8 -*-
"""
ISPOG - MusicXML Processing
Functions for parsing, processing, and writing MusicXML files.
"""

import re
import logging
from typing import Tuple, Dict, List, Optional

from .entities import Note, Bar, NewNote
from .analyzer import ChordAnalyzer

from config.settings import COLOR_CODES

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
        bar_score = bar.get_score_matrix()
        
        # Calculate max duration in this bar
        durations = [0.0, 0.0, 0.0, 0.0]
        
        for voice in range(1, 5):
            if voice in bar_score:
                for note in bar_score[voice]:
                    if not note.is_chord():
                        durations[voice - 1] += note.get_value()
        
        max_duration = max(durations)
        logger.debug(f"Bar max duration: {max_duration}")
        
        # Add notes and fill gaps with rests
        for voice in range(1, 5):
            if voice in bar_score:
                voice_duration = 0.0
                for note in bar_score[voice]:
                    score[voice].append(note)
                    if not note.is_chord():
                        voice_duration += note.get_value()
                
                # Add rest if needed
                if voice_duration < max_duration:
                    rest_duration = max_duration - voice_duration
                    rest = NewNote({
                        'pitch': ['rest', '0'],
                        'value': rest_duration,
                        'voice': voice
                    })
                    score[voice].append(rest)
            else:
                # Full rest for this voice
                rest = NewNote({
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

def analyze_score_playability(score: Dict[int, List[Note]]) -> None:
    """
    Walk the score in time. At each onset, new notes are analyzed against
    notes still sounding (sustained), which act as fixed constraints.
    """
    logger.info("Analyzing score playability")

    analyzer = ChordAnalyzer()
    voice_indices = {v: 0 for v in range(1, 5)}
    voice_times = {v: 0.0 for v in range(1, 5)}
    active_notes: Dict[int, List[Tuple[Note, float]]] = {v: [] for v in range(1, 5)}

    voices_finished = 0
    current_time = 0.0

    while voices_finished < 4:
        # 1. Drop ended notes
        for voice in range(1, 5):
            active_notes[voice] = [
                (note, end) for note, end in active_notes[voice]
                if end > current_time + 0.001
            ]

        # 2. Snapshot sustained notes (before adding new onsets)
        sustained_notes = [note for v in range(1, 5) for note, _ in active_notes[v]]

        # 3. Collect notes attacked at current_time
        new_notes: List[Note] = []
        for voice in range(1, 5):
            if voice_indices[voice] >= len(score[voice]):
                if voice_indices[voice] == len(score[voice]):
                    voices_finished += 1
                    voice_indices[voice] += 1
                continue

            if abs(voice_times[voice] - current_time) < 0.001:
                note = score[voice][voice_indices[voice]]
                onset = [note]
                if not note.is_chord():
                    voice_times[voice] += note.get_value()
                voice_indices[voice] += 1

                while voice_indices[voice] < len(score[voice]):
                    next_note = score[voice][voice_indices[voice]]
                    if not next_note.is_chord():
                        break
                    onset.append(next_note)
                    voice_indices[voice] += 1

                for n in onset:
                    if n.get_pitch()[0] != 'rest':
                        new_notes.append(n)
                        active_notes[voice].append((n, current_time + n.get_value()))

        # 4. Analyze new notes against sustained constraints
        if new_notes:
            logger.debug(f"Time {current_time}: {len(new_notes)} new, "
                         f"{len(sustained_notes)} sustained")
            analyzer.analyze_chord(new_notes, sustained_notes)

        # 5. Advance time
        if voices_finished < 4:
            next_times = [voice_times[v] for v in range(1, 5)
                          if voice_indices[v] < len(score[v])]
            if not next_times:
                break
            current_time = min(next_times)

    logger.info("Playability analysis complete")

# ============================================================================
# MUSICXML OUTPUT
# ============================================================================

def write_colored_score(original_measures: List[str], bars: List[Bar]) -> str:
    """
    Reconstruct MusicXML with note colors applied.
    XML <note> parts and Bar.get_notes() are aligned 1:1 (rests included),
    since both come from splitting the same measure string on '<note '.
    """
    logger.info("Writing colored score to MusicXML")

    bars_by_index = {bar.get_index_bar(): bar for bar in bars}
    output = [original_measures[0]]

    for idx, measure_str in enumerate(original_measures[1:], start=1):
        bar_obj = bars_by_index.get(idx)
        if bar_obj is None:
            logger.warning(f"Measure {idx} not parsed, written unchanged")
            output.append('<measure ' + measure_str)
            continue

        note_parts = measure_str.split('<note ')
        notes = bar_obj.get_notes()
        if len(note_parts) - 1 != len(notes):
            logger.warning(f"Measure {idx}: {len(note_parts) - 1} XML notes "
                           f"vs {len(notes)} parsed notes")

        output.append('<measure ' + note_parts[0])
        for j, note_str in enumerate(note_parts[1:]):
            note_obj = notes[j] if j < len(notes) else None
            output.append('<note ' + _colorize_note(note_str, note_obj))

    logger.info("Colored score written successfully")
    return ''.join(output)


def _colorize_note(note_str: str, note_obj: Optional[Note]) -> str:
    """Insert (or update) notehead color. Rests and unmatched notes unchanged."""
    if note_obj is None or '<rest' in note_str:
        return note_str

    color_code = f'"{COLOR_CODES.get(note_obj.get_color(), COLOR_CODES["black"])}"'

    if '<notehead' in note_str:
        # Existing notehead: add color attribute if missing
        return re.sub(r'<notehead(?![^>]*\bcolor=)',
                      f'<notehead color={color_code}', note_str, count=1)

    # '</note>' (with '>') avoids matching '</notehead>'
    head, sep, tail = note_str.rpartition('</note>')
    if not sep:
        return note_str
    return f'{head}<notehead color={color_code}>normal</notehead>\n\t\t\t\t</note>{tail}'


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
                            f'Pitch: {note.get_pitch()}, '
                            f'Value: {note.get_value()}, '
                            f'Fret: {note.get_fret()}, '
                            f'Color: {note.get_color()}, '
                            f'IsChord: {note.is_chord()}\n'
                        )
                    except Exception as e:
                        f.write(f'ERROR: {e}\n')
                
                f.write('\n\n')
        
        logger.info(f"Debug file created: {debug_file}")
        
    except Exception as e:
        logger.error(f"Error creating debug file: {e}", exc_info=True)

