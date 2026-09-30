# -*- coding: utf-8 -*-
"""
Create the pre-refactor baseline (plan, phase F0).

Runs the CURRENT string-based pipeline on a MusicXML file without the GUI and saves,
in tests/baseline/:
    <name>_baseline.musicxml     colored output, exactly as the current code writes it
    <name>_baseline_colors.csv   note-by-note color table (see extract_colors.py)

Run it ONCE, before the lxml refactor, from the repository root:
    python tests/tools/make_baseline.py tests/fixtures/Test01.musicxml

HISTORICAL: this script no longer runs. It needs the 0.9 string pipeline (core.entities,
core.musicxml, utils.io.load_musicxml), removed in phase F5. The files it produced in F0
are the reference; to run it again, check out the commit "F0: pre-refactor baseline for
Test01". extract_colors.py --diff compares a new output against the baseline.

Only meaningful for single-part guitar scores: the current code merges all parts into
one sequence, so a multi-part file such as test_poli has no valid baseline.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.entities import Fretboard                                  # noqa: E402
from core.musicxml import (                                          # noqa: E402
    analyze_score_playability,
    merge_bars_to_score,
    parse_measures,
    write_colored_score,
)
from utils.io import load_musicxml                                   # noqa: E402
from extract_colors import color_summary, extract_colors, write_csv  # noqa: E402

STANDARD_TUNING = ["E4", "B3", "G3", "D3", "A2", "E2"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the pre-refactor baseline.")
    parser.add_argument("source", type=Path, help="Single-part guitar MusicXML file")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "tests" / "baseline")
    parser.add_argument("--frets", type=int, default=19)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    xml = load_musicxml(str(args.source))
    if xml is None:
        print(f"Cannot read {args.source}", file=sys.stderr)
        return 1

    fretboard = Fretboard(len(STANDARD_TUNING), args.frets, STANDARD_TUNING).get_matrix()
    bars, chunks = parse_measures(xml, fretboard)
    score = merge_bars_to_score(bars)
    analyze_score_playability(score)
    colored = write_colored_score(chunks, bars)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    xml_out = args.out_dir / f"{args.source.stem}_baseline.musicxml"
    csv_out = args.out_dir / f"{args.source.stem}_baseline_colors.csv"
    xml_out.write_text(colored, encoding="utf-8", newline="")

    rows = extract_colors(xml_out)
    write_csv(rows, csv_out)
    print(f"{xml_out.relative_to(ROOT)}")
    print(f"{csv_out.relative_to(ROOT)}: {len(rows)} notes ({color_summary(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
