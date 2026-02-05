# -*- coding: utf-8 -*-
"""
ISPOG - Chord Analyzer
Professional implementation of guitar chord playability analysis.
"""

from typing import List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging

from .entities import Note

logger = logging.getLogger(__name__)


class Playability(Enum):
    """Enum for chord playability status."""
    PLAYABLE = "green"
    DIFFICULT = "orange"  # Requires pinky barré or stretch
    UNPLAYABLE = "red"


@dataclass
class FretPosition:
    """Represents a finger position on the fretboard."""
    string: int  # 1-6 (or more)
    fret: int    # 0-19 (0 = open string)
    
    def is_open(self) -> bool:
        """Returns True if this is an open string."""
        return self.fret == 0
    
    def __hash__(self):
        return hash((self.string, self.fret))


@dataclass
class FingeringAnalysis:
    """Result of fingering analysis for a chord."""
    playability: Playability
    positions: List[FretPosition]
    fingers_used: int
    has_barre: bool
    barre_fret: Optional[int] = None
    span: int = 0  # Fret span (max - min fret, excluding open strings)
    reason: str = ""  # Why unplayable/difficult


class ChordAnalyzer:
    """
    Analyzes guitar chord playability considering:
    - Maximum 4 fingers (index, middle, ring, pinky)
    - Barré technique with index finger
    - Fret span limitations
    - String conflicts
    """
    
    MAX_FINGERS = 4
    MAX_FRET_SPAN = 4  # Maximum comfortable stretch
    MAX_FRET_SPAN_WITH_OPEN = 5  # Slightly more with open strings
    
    def __init__(self):
        logger.debug("ChordAnalyzer initialized")
    
    def analyze_chord(self, notes: List[Note]) -> None:
        """
        Main entry point: analyzes a chord and sets colors on notes.
        
        Args:
            notes: List of Note objects to analyze
        """
        # Remove rests
        chord_notes = [n for n in notes if n.get_pitch()[0] != 'rest']
        
        if not chord_notes:
            logger.debug("Empty chord (all rests)")
            return
        
        logger.debug(f"Analyzing chord with {len(chord_notes)} notes")
        
        # Try to find a playable fingering
        best_fingering = self._find_best_fingering(chord_notes)
        
        # Apply colors based on result
        self._apply_colors(chord_notes, best_fingering)
        
        logger.debug(f"Chord playability: {best_fingering.playability.name}")
    
    def _find_best_fingering(self, notes: List[Note]) -> FingeringAnalysis:
        """
        Finds the best fingering for a chord, trying different positions.
        
        Returns the most playable fingering found.
        """
        # Sort notes by pitch (highest to lowest)
        sorted_notes = self._sort_notes_by_pitch(notes)
        
        # Try all possible position combinations
        best_result = None
        best_playability = Playability.UNPLAYABLE
        
        # Generate all valid fingering options
        for fingering_option in self._generate_fingering_options(sorted_notes):
            analysis = self._analyze_fingering(fingering_option)
            
            # Keep best result
            if analysis.playability.value == "green":
                return analysis  # Found perfect solution
            elif analysis.playability.value == "orange" and best_playability != Playability.PLAYABLE:
                best_result = analysis
                best_playability = Playability.DIFFICULT
            elif best_result is None:
                best_result = analysis
        
        return best_result or FingeringAnalysis(
            playability=Playability.UNPLAYABLE,
            positions=[],
            fingers_used=0,
            has_barre=False,
            reason="No valid fingering found"
        )
    
    def _generate_fingering_options(self, notes: List[Note]) -> List[List[FretPosition]]:
        """
        Generates all possible fingering combinations for the chord.
        Each note can be played on multiple positions.
        """
        options = []
        
        def recurse(index: int, current_fingering: List[FretPosition]):
            if index == len(notes):
                # Check basic validity (no string conflicts)
                if self._has_no_string_conflicts(current_fingering):
                    options.append(current_fingering.copy())
                return
            
            # Try each possible position for this note
            for pos_tuple in notes[index].get_fret_pos():
                pos = FretPosition(string=pos_tuple[0], fret=pos_tuple[1])
                current_fingering.append(pos)
                recurse(index + 1, current_fingering)
                current_fingering.pop()
        
        recurse(0, [])
        
        logger.debug(f"Generated {len(options)} fingering options")
        return options
    
    def _has_no_string_conflicts(self, positions: List[FretPosition]) -> bool:
        """Check if two notes are on the same string."""
        strings = [pos.string for pos in positions]
        return len(strings) == len(set(strings))
    
    def _analyze_fingering(self, positions: List[FretPosition]) -> FingeringAnalysis:
        """
        Analyzes a specific fingering to determine playability.
        
        This is where the magic happens: counts fingers, detects barré, etc.
        """
        if not positions:
            return FingeringAnalysis(
                playability=Playability.UNPLAYABLE,
                positions=[],
                fingers_used=0,
                has_barre=False,
                reason="No positions"
            )
        
        # Separate open strings from fretted notes
        open_strings = [p for p in positions if p.is_open()]
        fretted = [p for p in positions if not p.is_open()]
        
        if not fretted:
            # All open strings - always playable!
            return FingeringAnalysis(
                playability=Playability.PLAYABLE,
                positions=positions,
                fingers_used=0,
                has_barre=False,
                span=0,
                reason="All open strings"
            )
        
        # Check for barré
        barre_info = self._detect_barre(fretted)
        
        # Count unique fingers needed
        fingers_needed = self._count_fingers_needed(fretted, barre_info)
        
        # Calculate fret span
        fret_numbers = [p.fret for p in fretted]
        span = max(fret_numbers) - min(fret_numbers)
        
        # Determine playability
        playability, reason = self._determine_playability(
            fingers_needed, span, barre_info, len(open_strings) > 0
        )
        
        return FingeringAnalysis(
            playability=playability,
            positions=positions,
            fingers_used=fingers_needed,
            has_barre=barre_info['has_barre'],
            barre_fret=barre_info.get('fret'),
            span=span,
            reason=reason
        )
    
    def _detect_barre(self, fretted_positions: List[FretPosition]) -> dict:
        """
        Detects if a barré is present and whether it's with index or pinky.
        
        Barré = multiple notes on the same fret.
        Index barré = barré on the lowest fret (most common)
        Pinky barré = barré on the highest fret (difficult)
        """
        if len(fretted_positions) < 2:
            return {'has_barre': False}
        
        # Count notes per fret
        fret_counts = {}
        for pos in fretted_positions:
            fret_counts[pos.fret] = fret_counts.get(pos.fret, 0) + 1
        
        # Find barré candidates (2+ notes on same fret)
        barre_frets = [fret for fret, count in fret_counts.items() if count >= 2]
        
        if not barre_frets:
            return {'has_barre': False}
        
        # Check if barré is on lowest fret (index finger) or highest (pinky)
        min_fret = min(pos.fret for pos in fretted_positions)
        max_fret = max(pos.fret for pos in fretted_positions)
        
        if min_fret in barre_frets:
            # Index barré (normal)
            notes_in_barre = sum(1 for p in fretted_positions if p.fret == min_fret)
            return {
                'has_barre': True,
                'fret': min_fret,
                'type': 'index',
                'notes_count': notes_in_barre
            }
        elif max_fret in barre_frets:
            # Pinky barré (difficult)
            notes_in_barre = sum(1 for p in fretted_positions if p.fret == max_fret)
            return {
                'has_barre': True,
                'fret': max_fret,
                'type': 'pinky',
                'notes_count': notes_in_barre
            }
        else:
            # Barré on middle fret (weird but possible)
            barre_fret = barre_frets[0]
            notes_in_barre = sum(1 for p in fretted_positions if p.fret == barre_fret)
            return {
                'has_barre': True,
                'fret': barre_fret,
                'type': 'middle',
                'notes_count': notes_in_barre
            }
    
    def _count_fingers_needed(self, fretted_positions: List[FretPosition], 
                              barre_info: dict) -> int:
        """
        Counts how many fingers are needed for the fingering.
        
        Key logic:
        - Each unique fret = 1 finger
        - Barré counts as 1 finger even if covering multiple strings
        - Maximum 4 fingers available (index, middle, ring, pinky)
        """
        if not fretted_positions:
            return 0
        
        # Get unique frets
        unique_frets = set(pos.fret for pos in fretted_positions)
        
        if barre_info['has_barre']:
            # Barré covers multiple strings but uses only 1 finger
            # So we count unique frets (barré counts as 1)
            fingers = len(unique_frets)
        else:
            # No barré: each note needs a separate finger
            fingers = len(fretted_positions)
        
        logger.debug(f"Fingers needed: {fingers} (barré: {barre_info['has_barre']})")
        return fingers
    
    def _determine_playability(self, fingers_needed: int, span: int, 
                               barre_info: dict, has_open_strings: bool) -> Tuple[Playability, str]:
        """
        Determines final playability based on all factors.
        
        Rules:
        1. More than 4 fingers → UNPLAYABLE
        2. Span > 4 without open strings → UNPLAYABLE
        3. Span > 5 with open strings → UNPLAYABLE
        4. Pinky barré → DIFFICULT (orange)
        5. Span = 4 without open → DIFFICULT (orange)
        6. Otherwise → PLAYABLE (green)
        """
        # Rule 1: Too many fingers
        if fingers_needed > self.MAX_FINGERS:
            return (
                Playability.UNPLAYABLE,
                f"Requires {fingers_needed} fingers (max 4)"
            )
        
        # Rule 2 & 3: Span too large
        max_span = self.MAX_FRET_SPAN_WITH_OPEN if has_open_strings else self.MAX_FRET_SPAN
        if span > max_span:
            return (
                Playability.UNPLAYABLE,
                f"Fret span {span} too large (max {max_span})"
            )
        
        # Rule 4: Pinky barré (difficult)
        if barre_info.get('type') == 'pinky':
            return (
                Playability.DIFFICULT,
                "Requires pinky barré (difficult)"
            )
        
        # Rule 5: Maximum comfortable span
        if span == self.MAX_FRET_SPAN and not has_open_strings:
            return (
                Playability.DIFFICULT,
                "Maximum fret span (stretchy)"
            )
        
        # All good!
        return (Playability.PLAYABLE, "Playable")
    
    def _apply_colors(self, notes: List[Note], analysis: FingeringAnalysis) -> None:
        """Apply color codes to notes based on analysis."""
        color = analysis.playability.value
        
        # Set fret positions and colors
        for i, note in enumerate(notes):
            if i < len(analysis.positions):
                pos = analysis.positions[i]
                note.set_fret((pos.string, pos.fret))
            note.set_color(color)
        
        logger.debug(f"Applied color '{color}' to {len(notes)} notes: {analysis.reason}")
    
    def _sort_notes_by_pitch(self, notes: List[Note]) -> List[Note]:
        """
        Sort notes by pitch (highest to lowest).
        Uses bubble sort for simplicity (lists are small).
        """
        sorted_notes = notes.copy()
        
        for i in range(len(sorted_notes)):
            for j in range(len(sorted_notes) - 1):
                pitch1 = sorted_notes[j].get_pitch()[0]
                pitch2 = sorted_notes[j + 1].get_pitch()[0]
                
                # Compare octave first
                octave1 = int(pitch1[-1])
                octave2 = int(pitch2[-1])
                
                if octave1 < octave2:
                    sorted_notes[j], sorted_notes[j + 1] = sorted_notes[j + 1], sorted_notes[j]
                elif octave1 == octave2:
                    # Same octave, compare note name
                    note_order = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
                    note1 = pitch1[0]
                    note2 = pitch2[0]
                    
                    if note_order.index(note1) < note_order.index(note2):
                        sorted_notes[j], sorted_notes[j + 1] = sorted_notes[j + 1], sorted_notes[j]
        
        return sorted_notes



