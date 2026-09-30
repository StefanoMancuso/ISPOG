# -*- coding: utf-8 -*-
"""
ISPOG - Chord Analyzer
Professional implementation of guitar chord playability analysis.
"""

from typing import List, Tuple, Optional, Sequence
from dataclasses import dataclass, field
from enum import Enum
import logging

from .fretboard import Fretboard
from .model import Note

logger = logging.getLogger(__name__)


class Playability(Enum):
    """Enum for chord playability status."""
    PLAYABLE = "green"
    DIFFICULT = "orange"  # Requires pinky barré or stretch
    UNPLAYABLE = "red"


class Issue:
    """Machine-readable cause of a result, for short labels (``reason`` is the long text)."""
    NONE = ""
    FINGERS = "fingers"            # more than 4 fingers
    SPAN = "span"                  # fret span too large
    OUT_OF_RANGE = "out_of_range"  # a note has no position on the neck
    STRINGS = "strings"            # more notes than strings
    CONFLICT = "conflict"          # no string assignment (held notes or shared strings)
    PINKY_BARRE = "pinky_barre"
    STRETCH = "stretch"            # maximum comfortable span


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
    issue: str = Issue.NONE  # machine-readable cause, see Issue
    fixed: List[FretPosition] = field(default_factory=list)  # held notes, first in positions
    held: List[Note] = field(default_factory=list)  # the notes behind ``fixed``


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


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

    # Ordering for choosing the best fingering (lower = better)
    _RANK = {
        Playability.PLAYABLE: 0,
        Playability.DIFFICULT: 1,
        Playability.UNPLAYABLE: 2,
    }

    def __init__(self, fretboard: Optional[Fretboard] = None):
        """
        Args:
            fretboard: used only to explain why a note has no position
                (``below the lowest string``, ``above fret 19``).
        """
        self._fretboard = fretboard
        logger.debug("ChordAnalyzer initialized")

    def analyze_chord(self, new_notes: List[Note],
                      sustained_notes: Sequence[Note] = ()) -> Optional[FingeringAnalysis]:
        """
        Analyze notes attacked at the current time.
        Sustained notes act as fixed constraints (string+fret) and are NOT recolored.
        Sustained notes already UNPLAYABLE (or without fret) do not constrain.
        
        Args:
            new_notes: Notes starting at the current time
            sustained_notes: Notes still sounding from previous onsets

        Returns:
            The chosen fingering (``fixed`` = held notes), or None without attacked notes.
        """
        attacked = [n for n in new_notes if n.midi is not None]
        if not attacked:
            return None

        held = [
            n for n in sustained_notes
            if n.get_fret() != (-1, -1)
            and n.get_color() != Playability.UNPLAYABLE.value
        ]
        fixed = [FretPosition(*n.get_fret()) for n in held]

        sorted_notes = self._sort_notes_by_pitch(attacked)
        logger.debug(f"Analyzing {len(sorted_notes)} new notes, {len(fixed)} fixed")

        best = self._find_best_fingering(sorted_notes, fixed, held)
        best.fixed = fixed
        best.held = held
        self._apply_colors(sorted_notes, best, offset=len(fixed))

        logger.debug(f"Chord playability: {best.playability.name}")
        return best

    def _find_best_fingering(self, notes: List[Note], fixed: List[FretPosition],
                             held: Sequence[Note] = ()) -> FingeringAnalysis:
        """
        Return first PLAYABLE fingering, else the best ranked one.
        Resulting positions = fixed + new (in this order).
        """
        best: Optional[FingeringAnalysis] = None

        for option in self._generate_fingering_options(notes, fixed):
            analysis = self._analyze_fingering(fixed + option)
            if analysis.playability is Playability.PLAYABLE:
                return analysis
            if best is None or self._RANK[analysis.playability] < self._RANK[best.playability]:
                best = analysis

        if best is not None:
            return best
        reason, issue = self._explain_no_fingering(notes, fixed, held)
        return FingeringAnalysis(
            playability=Playability.UNPLAYABLE,
            positions=[],
            fingers_used=0,
            has_barre=False,
            reason=reason,
            issue=issue,
        )

    def _explain_no_fingering(self, notes: List[Note], fixed: List[FretPosition],
                              held: Sequence[Note]) -> Tuple[str, str]:
        """Why no string assignment exists for the attacked notes: (reason, issue)."""
        unreachable = [n for n in notes if not n.get_fret_pos()]
        if unreachable:
            return '; '.join(self._out_of_range(n) for n in unreachable), Issue.OUT_OF_RANGE

        if self._fretboard is not None:
            strings = self._fretboard.num_strings
        else:
            strings = len({s for n in notes for s, _ in n.get_fret_pos()}
                          | {p.string for p in fixed})
        if len(notes) + len(fixed) > strings:
            held_text = f" + {_count(len(fixed), 'held note')}" if fixed else ''
            return (f"{_count(len(notes), 'note')}{held_text} on {strings} strings",
                    Issue.STRINGS)

        if fixed:
            held_list = ', '.join(f'{n.pitch_name} ({p.string}/{p.fret})'
                                  for n, p in zip(held, fixed))
            return f"string conflict with held notes: {held_list}", Issue.CONFLICT
        return "string conflict: " + ' '.join(n.pitch_name for n in notes), Issue.CONFLICT

    def _out_of_range(self, note: Note) -> str:
        if self._fretboard is None:
            return f"{note.pitch_name} out of range"
        detail = self._fretboard.out_of_range_reason(note.midi)
        return f"{note.pitch_name} out of range ({detail})"
    
    
    def _generate_fingering_options(self, notes: List[Note],
                                    fixed: List[FretPosition]) -> List[List[FretPosition]]:
        """
        All string assignments for new notes.
        Strings held by fixed (sustained) notes are excluded.
        """
        options: List[List[FretPosition]] = []
        used = {p.string for p in fixed}
        current: List[FretPosition] = []

        def recurse(i: int) -> None:
            if i == len(notes):
                options.append(current.copy())
                return
            for string, fret in notes[i].get_fret_pos():
                if string in used:
                    continue
                used.add(string)
                current.append(FretPosition(string, fret))
                recurse(i + 1)
                current.pop()
                used.discard(string)

        recurse(0)
        logger.debug(f"Generated {len(options)} fingering options")
        return options
        
    
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
                reason="open strings"
            )
        
        # Check for barré
        barre_info = self._detect_barre(fretted)
        
        # Count unique fingers needed
        fingers_needed = self._count_fingers_needed(fretted, barre_info)
        
        # Calculate fret span
        fret_numbers = [p.fret for p in fretted]
        span = max(fret_numbers) - min(fret_numbers)
        
        # Determine playability
        playability, reason, issue = self._determine_playability(
            fingers_needed, span, barre_info, len(open_strings) > 0
        )
        
        return FingeringAnalysis(
            playability=playability,
            positions=positions,
            fingers_used=fingers_needed,
            has_barre=barre_info['has_barre'],
            barre_fret=barre_info.get('fret'),
            span=span,
            reason=reason,
            issue=issue,
        )
    
    def _detect_barre(self, fretted_positions: List[FretPosition]) -> dict:
        """
        Detects valid barré considering realistic finger limitations.
        
        INDEX BARRÉ (lowest fret):
        - Can cover any combination of strings (contiguous or not)
        - Most common and versatile
        
        PINKY BARRÉ (highest fret):
        - ONLY valid on strings from 1 to 4 (contiguous, starting from string 1)
        - All other notes must be on LOWER frets or open strings
        """
        if len(fretted_positions) < 2:
            return {'has_barre': False}
        
        # Group positions by fret
        fret_groups = {}
        for pos in fretted_positions:
            if pos.fret not in fret_groups:
                fret_groups[pos.fret] = []
            fret_groups[pos.fret].append(pos.string)
        
        # Find frets with 2+ notes
        barre_candidates = {fret: strings for fret, strings in fret_groups.items() 
                            if len(strings) >= 2}
        
        if not barre_candidates:
            return {'has_barre': False}
        
        min_fret = min(pos.fret for pos in fretted_positions)
        max_fret = max(pos.fret for pos in fretted_positions)
        
        # Check for INDEX BARRÉ (lowest fret, no restrictions on string layout)
        if min_fret in barre_candidates:
            strings = sorted(barre_candidates[min_fret])
            logger.debug(f"Index barré detected: fret {min_fret}, strings {strings}")
            return {
                'has_barre': True,
                'fret': min_fret,
                'type': 'index',
                'strings': strings,
                'notes_count': len(strings)
            }
        
        # Check for PINKY BARRÉ (highest fret, strict requirements)
        if max_fret in barre_candidates:
            strings = sorted(barre_candidates[max_fret])
            
            # Pinky barré requirements:
            # 1. Must start from string 1 (highest pitched)
            # 2. Strings must be contiguous
            # 3. Maximum 4 strings (1-2-3-4)
            
            is_valid_pinky = (
                strings[0] == 1 and  # Starts from string 1
                len(strings) <= 4 and  # Max 4 strings
                all(strings[i+1] - strings[i] == 1 for i in range(len(strings) - 1))  # Contiguous
            )
            
            if is_valid_pinky:
                logger.debug(f"Valid pinky barré: fret {max_fret}, strings {strings}")
                return {
                    'has_barre': True,
                    'fret': max_fret,
                    'type': 'pinky',
                    'strings': strings,
                    'notes_count': len(strings)
                }
            else:
                logger.debug(f"Invalid pinky barré (strings {strings} don't meet requirements)")
        
        # No valid barré found
        logger.debug("No valid barré configuration found")
        return {'has_barre': False}

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
                               barre_info: dict,
                               has_open_strings: bool) -> Tuple[Playability, str, str]:
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
                f"requires {fingers_needed} fingers (max {self.MAX_FINGERS})",
                Issue.FINGERS,
            )
        
        # Rule 2 & 3: Span too large
        max_span = self.MAX_FRET_SPAN_WITH_OPEN if has_open_strings else self.MAX_FRET_SPAN
        if span > max_span:
            return (
                Playability.UNPLAYABLE,
                f"fret span {span} (max {max_span})",
                Issue.SPAN,
            )
        
        # Rule 4: Pinky barré (difficult)
        if barre_info.get('type') == 'pinky':
            strings = barre_info['strings']
            return (
                Playability.DIFFICULT,
                f"pinky barré on fret {barre_info['fret']}, strings {strings[0]}–{strings[-1]}",
                Issue.PINKY_BARRE,
            )
        
        # Rule 5: Maximum comfortable span
        if span == self.MAX_FRET_SPAN and not has_open_strings:
            return (
                Playability.DIFFICULT,
                f"maximum stretch (span {span})",
                Issue.STRETCH,
            )
        
        # All good!
        return (Playability.PLAYABLE, "playable", Issue.NONE)
    
    def _apply_colors(self, notes: List[Note], analysis: FingeringAnalysis,
                      offset: int = 0) -> None:
        """
        Apply color and fret to new notes only.
        analysis.positions[offset:] map 1:1 to notes.
        """
        color = analysis.playability.value
        positions = analysis.positions[offset:]

        for i, note in enumerate(notes):
            pos = positions[i] if i < len(positions) else None
            note.set_fret((pos.string, pos.fret) if pos else (-1, -1))
            note.set_color(color)
            note.set_reason(analysis.reason)

        logger.debug(f"Applied color '{color}' to {len(notes)} notes: {analysis.reason}")

    def _sort_notes_by_pitch(self, notes: List[Note]) -> List[Note]:
        """
        Sort notes by sounding pitch, highest first. The sort is stable: notes with the
        same pitch keep their order.
        """
        return sorted(notes, key=lambda n: n.midi, reverse=True)
