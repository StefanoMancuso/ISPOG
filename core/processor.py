# -*- coding: utf-8 -*-
"""
ISPOG - Core Processor
Main workflow orchestrator for guitar playability analysis.
This module coordinates the entire analysis pipeline.
"""

from pathlib import Path

from utils.logger import get_logger
from utils.io import load_musicxml
from .entities import Fretboard
from .musicxml import (
    parse_measures,
    merge_bars_to_score,
    analyze_score_playability,
    write_colored_score,
    create_debug_note_list
)

logger = get_logger(__name__)


class AnalysisConfig:
    """Configuration for a single analysis run."""
    
    def __init__(
        self,
        filepath: str,
        num_strings: int,
        tuning: list[str],
        num_frets: int = 19
    ):
        self.filepath = filepath
        self.num_strings = num_strings
        self.tuning = tuning
        self.num_frets = num_frets
        
        # Validate
        self._validate()
    
    def _validate(self):
        """Validate configuration parameters."""
        if not Path(self.filepath).exists():
            raise FileNotFoundError(f"File not found: {self.filepath}")
        
        if not 4 <= self.num_strings <= 8:
            raise ValueError(f"Invalid number of strings: {self.num_strings}")
        
        if len(self.tuning) != self.num_strings:
            raise ValueError(
                f"Tuning list length ({len(self.tuning)}) "
                f"doesn't match num_strings ({self.num_strings})"
            )
        
        if self.num_frets < 12 or self.num_frets > 24:
            raise ValueError(f"Invalid number of frets: {self.num_frets}")


class PlayabilityAnalyzer:
    """
    Main processor for guitar playability analysis.
    Orchestrates the complete workflow from file loading to output generation.
    """
    
    def __init__(self, config: AnalysisConfig):
        """
        Initialize analyzer with configuration.
        
        Args:
            config: Analysis configuration object
        """
        self.config = config
        logger.info("="*60)
        logger.info("Playability Analyzer initialized")
        logger.info(f"File: {config.filepath}")
        logger.info(f"Strings: {config.num_strings}")
        logger.info(f"Tuning: {config.tuning}")
        logger.info(f"Frets: {config.num_frets}")
        logger.info("="*60)
    
    def analyze(self) -> bool:
        """
        Execute complete analysis workflow.
        
        Returns:
            True if analysis completed successfully, False otherwise
        """
        try:
            logger.info("Starting analysis workflow")
            
            # Step 1: Load MusicXML file
            if not self._load_file():
                return False
            
            # Step 2: Generate fretboard matrix
            if not self._generate_fretboard():
                return False
            
            # Step 3: Parse measures
            if not self._parse_measures():
                return False
            
            # Step 4: Merge bars into continuous score
            if not self._merge_bars():
                return False
            
            # Step 5: Analyze playability and color notes
            if not self._analyze_playability():
                return False
            
            # Step 6: Write colored score and save
            if not self._write_output():
                return False
            
            # Step 7: Generate debug file
            self._generate_debug_file()
            
            logger.info("="*60)
            logger.info("Analysis workflow completed successfully!")
            logger.info("="*60)
            return True
            
        except Exception:
            logger.error("Critical error in analysis workflow", exc_info=True)
            return False
    
    def _load_file(self) -> bool:
        """Step 1: Load MusicXML file."""
        logger.info("Step 1: Loading MusicXML file")
        
        self.score = load_musicxml(self.config.filepath)
        
        if self.score is None:
            logger.error("Failed to load file")
            return False
        
        logger.info(f"Loaded {len(self.score)} characters")
        return True
    
    def _generate_fretboard(self) -> bool:
        """Step 2: Generate fretboard matrix."""
        logger.info("Step 2: Generating fretboard matrix")
        
        try:
            fretboard_obj = Fretboard(
                self.config.num_strings,
                self.config.num_frets,
                self.config.tuning
            )
            self.fretboard_matrix = fretboard_obj.get_matrix()
            
            logger.info(
                f"Fretboard generated: {len(self.fretboard_matrix)} strings, "
                f"{len(self.fretboard_matrix[0])} positions per string"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate fretboard: {e}", exc_info=True)
            return False
    
    def _parse_measures(self) -> bool:
        """Step 3: Parse MusicXML into measures."""
        logger.info("Step 3: Parsing measures")
        
        try:
            self.bar_objects, self.score_list = parse_measures(
                self.score,
                self.fretboard_matrix
            )
            
            logger.info(f"Parsed {len(self.bar_objects)} measures")
            return True
            
        except Exception as e:
            logger.error(f"Failed to parse measures: {e}", exc_info=True)
            return False
    
    def _merge_bars(self) -> bool:
        """Step 4: Merge bars into continuous score."""
        logger.info("Step 4: Merging bars into continuous score")
        
        try:
            self.final_score = merge_bars_to_score(self.bar_objects)
            
            # Log statistics
            for voice in range(1, 5):
                note_count = len(self.final_score[voice])
                logger.info(f"Voice {voice}: {note_count} notes")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to merge bars: {e}", exc_info=True)
            return False
    
    def _analyze_playability(self) -> bool:
        """Step 5: Analyze playability and color notes."""
        logger.info("Step 5: Analyzing playability")
        
        try:
            analyze_score_playability(self.final_score)
            
            # Count colors for statistics
            color_stats = {'green': 0, 'orange': 0, 'red': 0, 'black': 0}
            
            for voice in range(1, 5):
                for note in self.final_score[voice]:
                    color = note.get_color()
                    if color in color_stats:
                        color_stats[color] += 1
            
            logger.info("Playability analysis complete:")
            logger.info(f"  🟢 Playable (green): {color_stats['green']}")
            logger.info(f"  🟠 Difficult (orange): {color_stats['orange']}")
            logger.info(f"  🔴 Unplayable (red): {color_stats['red']}")
            logger.info(f"  ⚫ Other (black): {color_stats['black']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze playability: {e}", exc_info=True)
            return False
    
    def _write_output(self) -> bool:
        """Step 6: Write colored score and save."""
        logger.info("Step 6: Writing colored output")
        
        try:
            from utils.io import save_musicxml
            
            # Generate colored XML
            colored_xml = write_colored_score(self.score_list, self.bar_objects)
            logger.info(f"Colored score generated: {len(colored_xml)} characters")

            # Save with dialog
            save_musicxml(colored_xml, "analyzed.musicxml")
            
            logger.info("Colored score written and saved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write output: {e}", exc_info=True)
            return False
    
    def _generate_debug_file(self) -> None:
        """Step 7: Generate debug note list file."""
        logger.info("Step 7: Generating debug file")
        
        try:
            create_debug_note_list(self.final_score, self.config.filepath)
            logger.info("Debug file generated")
        except Exception as e:
            logger.warning(f"Failed to generate debug file: {e}")
            # Non-critical, continue anyway


# ============================================================================
# PUBLIC API
# ============================================================================

def analyze_file(
    filepath: str,
    num_strings: int,
    tuning: list[str],
    num_frets: int = 19
) -> bool:
    """
    Analyze a MusicXML file for guitar playability.
    
    This is the main entry point for the analysis workflow.
    
    Args:
        filepath: Path to MusicXML file
        num_strings: Number of guitar strings (4-8)
        tuning: List of tuning notes (e.g., ['E4', 'B3', 'G3', 'D3', 'A2', 'E2'])
        num_frets: Number of frets on guitar (default: 19)
        
    Returns:
        True if analysis completed successfully, False otherwise
        
    Example:
        >>> success = analyze_file(
        ...     'song.musicxml',
        ...     6,
        ...     ['E4', 'B3', 'G3', 'D3', 'A2', 'E2']
        ... )
        >>> if success:
        ...     print("Analysis complete!")
    """
    try:
        config = AnalysisConfig(filepath, num_strings, tuning, num_frets)
        analyzer = PlayabilityAnalyzer(config)
        return analyzer.analyze()
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return False


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == '__main__':
    # Test configuration
    test_config = AnalysisConfig(
        filepath='test.musicxml',
        num_strings=6,
        tuning=['E4', 'B3', 'G3', 'D3', 'A2', 'E2'],
        num_frets=19
    )
    
    analyzer = PlayabilityAnalyzer(test_config)
    success = analyzer.analyze()
    
    print(f"\nAnalysis {'succeeded' if success else 'failed'}!")
