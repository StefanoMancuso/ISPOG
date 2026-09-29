# -*- coding: utf-8 -*-
"""
Freeze the 0.9.2 fretboard positions (plan, phase F3).

Runs the string-matrix Fretboard of core.entities on every spelled note C0..B7 with
alterations -1, 0, +1, for a few tunings, and saves the positions to
tests/baseline/fretboard_0.9.2.json. tests/test_fretboard.py compares the MIDI-based
core.fretboard against this file.

Run it ONCE, while core.entities still exists, from the repository root:
    python tests/tools/make_fretboard_baseline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.entities import Fretboard, Note  # noqa: E402

TUNINGS = [
    (["E4", "B3", "G3", "D3", "A2", "E2"], 19),                    # standard
    (["E4", "B3", "G3", "D3", "A2", "D2"], 19),                    # drop D
    (["D4", "B3", "G3", "D3", "G2", "D2"], 12),                    # open G, short neck
    (["E4", "B3", "G3", "D3", "A2", "E2", "B1", "F#1"], 24),       # 8 strings
]
ACCIDENTAL = {-1: "b", 0: "", 1: "#"}
OUTPUT = ROOT / "tests" / "baseline" / "fretboard_0.9.2.json"


def positions(matrix: list[list[str]], step: str, alter: int, octave: int) -> list[list[int]]:
    note = Note(f"<pitch><step>{step}</step><alter>{alter}</alter><octave>{octave}</octave>"
                f"</pitch><duration>1</duration>")
    note.set_fret_pos(matrix)
    return sorted([list(p) for p in note.get_fret_pos()])


def main() -> int:
    cases = []
    for tuning, frets in TUNINGS:
        matrix = Fretboard(len(tuning), frets, tuning).get_matrix()
        table = {
            f"{step}{ACCIDENTAL[alter]}{octave}": positions(matrix, step, alter, octave)
            for octave in range(8) for step in "CDEFGAB" for alter in (-1, 0, 1)
        }
        cases.append({"tuning": tuning, "frets": frets, "positions": table})
    # one note per line: readable and diff-friendly
    lines = ["["]
    for i, case in enumerate(cases):
        lines.append(f' {{"tuning": {json.dumps(case["tuning"])}, "frets": {case["frets"]}, '
                     f'"positions": {{')
        items = list(case["positions"].items())
        for j, (name, pos) in enumerate(items):
            comma = "," if j < len(items) - 1 else ""
            lines.append(f"  {json.dumps(name)}: {json.dumps(pos)}{comma}")
        lines.append(" }}" + ("," if i < len(cases) - 1 else ""))
    lines.append("]")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)}: {len(cases)} tunings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
