# -*- coding: utf-8 -*-
"""
ISPOG - Core Entities
Domain entities for music notation and guitar fretboard representation.
"""

import re
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# BAR (MEASURE) ENTITY
# ============================================================================

class Bar:
    """
    Represents a musical measure (bar) with notes and metadata.
    
    Attributes:
        index: Bar index in the score
        num: Bar number (from MusicXML)
        width: Width in MusicXML units
        score: Raw MusicXML string for this bar
        notes: List of Note objects
        score_matrix: Dict mapping voice number to list of notes
    """
    
    def __init__(self, index_bar: int, score: str, fretboard_matrix: list[list[str]]):
        """
        Parse a bar from MusicXML string.
        
        Args:
            index_bar: Index of this bar in the score
            score: Raw MusicXML string for this measure
            fretboard_matrix: Fretboard matrix for note positioning
        """
        logger.debug(f"Creating Bar {index_bar}")
        
        self._index_bar = index_bar
        self._score = score
        self._num_bar: int = -1
        self._width_bar: float = -1
        self._score_matrix: dict[int, list[Note]] = {}
        self._notes: list[Note] = []
        
        self._extract_bar_info()
        self._extract_notes(fretboard_matrix)
    
    def _extract_bar_info(self):
        """Extract bar number and width from MusicXML."""
        try:
            parts = re.split('"', self._score)
            self._num_bar = int(parts[1])
            self._width_bar = float(parts[3])
            logger.debug(f"Bar {self._num_bar}, width: {self._width_bar}")
        except (IndexError, ValueError) as e:
            logger.warning(f"Error extracting bar info: {e}")
            self._num_bar = self._index_bar
            self._width_bar = 100  # Default width
    
    def _extract_notes(self, fretboard_matrix: list[list[str]]):
        """Parse notes from MusicXML and organize by voice."""
        note_strings = re.split('<note ', self._score)[1:]
        logger.debug(f"Found {len(note_strings)} notes in bar {self._num_bar}")
        
        for note_str in note_strings:
            note = Note(note_str)
            note.set_fret_pos(fretboard_matrix)
            self._notes.append(note)
            
            # Organize by voice
            voice = note.get_voice()
            if voice not in self._score_matrix:
                self._score_matrix[voice] = []
            self._score_matrix[voice].append(note)
    
    # Getters (keep original names for backward compatibility)
    def get_index_bar(self) -> int:
        return self._index_bar
    
    def get_notes(self) -> list['Note']:
        return self._notes
    
    def get_num_bar(self) -> int:
        return self._num_bar
    
    def get_score(self) -> str:
        return self._score
    
    def get_score_matrix(self) -> dict[int, list['Note']]:
        return self._score_matrix
    
    def __str__(self) -> str:
        return str(self.__dict__)

# ============================================================================
# FRETBOARD ENTITY
# ============================================================================

class Fretboard:
    """
    Represents a guitar fretboard with strings and frets.
    Generates matrix of note positions for a given tuning.
    """
    
    # Chromatic scale
    SCALE = ['C', '', 'D', '', 'E', 'F', '', 'G', '', 'A', '', 'B']
    
    def __init__(self, num_strings: int, num_frets: int, tuning: list[str]):
        """
        Create fretboard matrix.
        
        Args:
            num_strings: Number of strings (4-8)
            num_frets: Number of frets (typically 19-24)
            tuning: List of open string notes (e.g., ['E4', 'B3', ...])
        """
        logger.debug(f"Creating Fretboard: {num_strings} strings, {num_frets} frets")
        
        self._tuning = tuning
        self._matrix: list[list[str]] = []
        
        # Generate matrix for each string
        for string_idx in range(num_strings):
            string_notes = self._generate_string_notes(
                tuning[string_idx],
                num_frets
            )
            self._matrix.append(string_notes)
    
    def _generate_string_notes(self, open_note: str, num_frets: int) -> list[str]:
        """
        Generate all notes for a single string.
        
        Args:
            open_note: Note for open string (e.g., 'E4', 'G#3')
            num_frets: Number of frets
            
        Returns:
            List of notes from fret 0 to num_frets
        """
        notes = []
        
        # Parse open note
        if len(open_note) >= 2 and open_note[1].isnumeric():
            # Natural note (e.g., 'E4')
            note_name = open_note[0]
            octave = int(open_note[1])
            start_idx = self.SCALE.index(note_name)
        elif len(open_note) >= 3 and open_note[1] == '#':
            # Sharp (e.g., 'F#4')
            note_name = open_note[0]
            octave = int(open_note[2])
            start_idx = self.SCALE.index(note_name) + 1
        elif len(open_note) >= 3 and open_note[1] == 'b':
            # Flat (e.g., 'Bb3')
            note_name = open_note[0]
            octave = int(open_note[2])
            start_idx = self.SCALE.index(note_name) - 1
        else:
            logger.error(f"Invalid tuning note: {open_note}")
            start_idx = 0
            octave = 4
        
        # Generate notes for each fret
        for fret in range(num_frets + 1):
            note_idx = (start_idx + fret) % 12
            note = self.SCALE[note_idx]
            
            # Calculate octave (increases every 12 semitones)
            current_octave = octave + (start_idx + fret) // 12
            
            # Add octave number (except for empty string positions)
            if note:
                notes.append(f"{note}{current_octave}")
            else:
                notes.append('')
        
        # Reverse to match expected order (high fret to low)
        notes.reverse()
        return notes
    
    def get_matrix(self) -> list[list[str]]:
        """Returns the fretboard matrix."""
        return self._matrix
    

# ============================================================================
# NOTE ENTITY
# ============================================================================

class Note:
    """
    Represents a musical note with pitch, duration, and guitar position.
    
    Attributes:
        pitch: [note_name+octave, alteration] (e.g., ['C4', '0'])
        value: Duration as fraction
        voice: Voice number (1-4)
        is_chord: True if part of a chord
        is_grace: True if grace note
        prev_tied: True if tied from previous note
        next_tied: True if tied to next note
        fret_pos: List of possible fret positions [(string, fret), ...]
        digit: Fingering number
        fret: Chosen fret position (string, fret)
        color: Note color (green/orange/red/black)
    """
    
    def __init__(self, xml_string: str):
        """
        Parse note from MusicXML string.
        
        Args:
            xml_string: MusicXML string for this note (after '<note ' split)
        """
        # Initialize attributes
        self._pitch: list[str] = ['0', '0']
        self._value: float = 0
        self._voice: int = 1
        self._is_chord: bool = False
        self._is_grace: bool = False
        self._prev_tied: bool = False
        self._next_tied: bool = False
        self._fret_pos: list[tuple[int, int]] = []
        self._digit: int = -1
        self._fret: tuple[int, int] = (-1, -1)
        self._color: str = 'black'
        
        self._parse_note(xml_string)
    
    def _parse_note(self, xml: str):
        """Parse note properties from XML."""
        # Check if chord note
        if '<chord/>' in xml:
            self._is_chord = True
        
        # Parse pitch or rest
        if '<pitch' in xml:
            self._parse_pitch(xml)
        elif '<rest' in xml:
            self._pitch = ['rest', '0']
        
        # Parse duration
        try:
            duration_match = re.search(r'<duration>([^<]+)</duration>', xml)
            if duration_match:
                self._value = float(duration_match.group(1))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing duration: {e}")
            self._value = 0
        
        # Parse voice
        try:
            voice_match = re.search(r'<voice>([^<]+)</voice>', xml)
            if voice_match:
                self._voice = int(voice_match.group(1))
        except (ValueError, AttributeError):
            self._voice = 1
        
        # Check for grace note
        if '<grace slash="yes"/>' in xml:
            self._is_grace = True
        
        # Check for ties
        if '<tied type="start"/>' in xml:
            self._next_tied = True
        if '<tied type="stop"/>' in xml:
            self._prev_tied = True
    
    def _parse_pitch(self, xml: str):
        """Parse pitch information."""
        try:
            # Extract step (note name)
            step_match = re.search(r'<step>([A-G])</step>', xml)
            # Extract octave
            octave_match = re.search(r'<octave>(\d)</octave>', xml)
            
            if step_match and octave_match:
                note_name = step_match.group(1)
                octave = octave_match.group(1)
                self._pitch[0] = f"{note_name}{octave}"
            
            # Extract alteration if present
            alter_match = re.search(r'<alter>([^<]+)</alter>', xml)
            if alter_match:
                self._pitch[1] = alter_match.group(1)
            else:
                self._pitch[1] = '0'
                
        except AttributeError as e:
            logger.warning(f"Error parsing pitch: {e}")
    
    def set_fret_pos(self, fretboard: list[list[str]]):
        """
        Find all possible fret positions for this note.
        
        Args:
            fretboard: Fretboard matrix
        """
        if self._pitch[0] == 'rest':
            return
        
        for string_idx, string_notes in enumerate(fretboard):
            for fret_idx, fret_note in enumerate(string_notes):
                if fret_note == self._pitch[0]:
                    # Calculate actual fret number
                    fret_num = len(string_notes) - fret_idx - 1 + int(self._pitch[1])
                    if fret_num >= 0:
                        self._fret_pos.append((string_idx + 1, fret_num))
    
    # Getters
    def get_color(self) -> str:
        return self._color
    
    def get_digit(self) -> int:
        return self._digit
    
    def get_fret(self) -> tuple[int, int]:
        return self._fret
    
    def get_pitch(self) -> list[str]:
        return self._pitch
    
    def get_value(self) -> float:
        return self._value
    
    def get_voice(self) -> int:
        return self._voice
    
    def is_chord(self) -> bool:
        return self._is_chord
    
    def is_grace(self) -> bool:
        return self._is_grace
    
    def get_prev_tied(self) -> bool:
        return self._prev_tied
    
    def get_next_tied(self) -> bool:
        return self._next_tied
    
    def get_fret_pos(self) -> list[tuple[int, int]]:
        return self._fret_pos
    
    # Setters
    def set_color(self, color: str):
        self._color = color
    
    def set_digit(self, digit: int):
        self._digit = digit
    
    def set_fret(self, fret: tuple[int, int]):
        self._fret = fret
    
    def __str__(self) -> str:
        return str(self.__dict__)


# ============================================================================
# NEW NOTE (for rests created during merge)
# ============================================================================

class NewNote(Note):
    """
    Note created programmatically (e.g., rests for alignment).
    Used by merge_bars_to_score in functions.
    """
    
    def __init__(self, attributes: dict):
        """
        Create note from attribute dictionary.
        
        Args:
            attributes: Dict with 'pitch', 'value', 'voice' keys
        """
        # Skip parent __init__ since we're setting attributes directly
        self._pitch = attributes['pitch']
        self._value = attributes['value']
        self._voice = attributes['voice']
        self._is_chord = False
        self._is_grace = False
        self._prev_tied = False
        self._next_tied = False
        self._fret_pos = []
        self._digit = -1
        self._fret = (-1, -1)
        self._color = 'black'
