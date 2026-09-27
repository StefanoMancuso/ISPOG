# -*- coding: utf-8 -*-
"""
Extract a note-by-note color table from a MusicXML file colored by ISPOG,
and compare two tables (e.g. pre-refactor baseline vs. new version).

Each row identifies a note by (part, measure, index), where index is the position of the
<note> element inside its measure (rests included). The pitch column doubles as an
alignment check: if two versions disagree on pitch, rows are not comparable.

Usage (from the repository root):
    python tests/tools/extract_colors.py score.musicxml               # CSV next to the score
    python tests/tools/extract_colors.py score.musicxml -o colors.csv
    python tests/tools/extract_colors.py --diff baseline.csv new.csv  # exit code 1 if different

Standard library only: it must run on the pre-refactor code base, before lxml is added.
"""

from __future__ import annotations

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

FIELDS = ["part", "measure", "index", "voice", "staff", "pitch", "chord", "color"]
KEY = ("part", "measure", "index")

# Hex codes written by ISPOG (config/settings.py, COLOR_CODES)
COLOR_NAMES = {"#cf0000": "red", "#005000": "green", "#ff8c00": "orange", "#000000": "black"}
ACCIDENTALS = {"0": "", "1": "#", "-1": "b", "2": "##", "-2": "bb"}


def pitch_name(note: ET.Element) -> str:
    pitch = note.find("pitch")
    if pitch is None:
        return "rest" if note.find("rest") is not None else "unpitched"
    alter = (pitch.findtext("alter") or "0").strip()
    accidental = ACCIDENTALS.get(alter, f"({alter})")
    return f"{pitch.findtext('step')}{accidental}{pitch.findtext('octave')}"


def note_color(note: ET.Element) -> str:
    head = note.find("notehead")
    raw = (head.get("color") if head is not None else None) or note.get("color")
    if not raw:
        return "-"
    return COLOR_NAMES.get(raw.strip().lower(), raw.strip())


def extract_colors(path: Path) -> list[dict[str, str]]:
    root = ET.parse(path).getroot()
    if root.tag != "score-partwise":
        raise ValueError(f"{path}: expected score-partwise, found {root.tag}")
    rows = []
    for part in root.findall("part"):
        for measure in part.findall("measure"):
            for index, note in enumerate(measure.findall("note")):
                rows.append({
                    "part": part.get("id", ""),
                    "measure": measure.get("number", ""),
                    "index": str(index),
                    "voice": note.findtext("voice", "1"),
                    "staff": note.findtext("staff", "1"),
                    "pitch": pitch_name(note),
                    "chord": "y" if note.find("chord") is not None else "",
                    "color": note_color(note),
                })
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def color_summary(rows: list[dict[str, str]]) -> str:
    counts = Counter(r["color"] for r in rows if r["pitch"] not in ("rest", "unpitched"))
    return ", ".join(f"{c} {counts[c]}" for c in ("green", "orange", "red", "black", "-") if counts[c])


def diff(old_path: Path, new_path: Path) -> int:
    old = {tuple(r[k] for k in KEY): r for r in read_csv(old_path)}
    new = {tuple(r[k] for k in KEY): r for r in read_csv(new_path)}
    problems = []

    for key in sorted(old.keys() | new.keys(), key=lambda k: (k[0], _num(k[1]), int(k[2]))):
        a, b = old.get(key), new.get(key)
        where = f"part {key[0]}, m. {key[1]}, note #{key[2]}"
        if a is None or b is None:
            problems.append(f"{where}: only in {'new' if a is None else 'old'}")
        elif a["pitch"] != b["pitch"]:
            problems.append(f"{where}: MISALIGNED pitch {a['pitch']} -> {b['pitch']}")
        elif a["color"] != b["color"]:
            problems.append(f"{where} ({a['pitch']}): {a['color']} -> {b['color']}")

    print(f"old: {color_summary(list(old.values()))}")
    print(f"new: {color_summary(list(new.values()))}")
    if not problems:
        print("Identical.")
        return 0
    print(f"{len(problems)} difference(s):")
    print("\n".join(f"  {p}" for p in problems))
    return 1


def _num(measure: str) -> tuple[int, str]:
    """Sort measure numbers numerically, keeping non-numeric ones (e.g. 'X1') stable."""
    digits = "".join(ch for ch in measure if ch.isdigit())
    return (int(digits) if digits else 0, measure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Output CSV (default: <score>_colors.csv)")
    parser.add_argument("--diff", action="store_true", help="Compare two CSV files")
    args = parser.parse_args()

    if args.diff:
        if len(args.files) != 2:
            parser.error("--diff needs exactly two CSV files")
        return diff(*args.files)

    if len(args.files) != 1:
        parser.error("give one MusicXML file (or use --diff)")
    source = args.files[0]
    rows = extract_colors(source)
    output = args.output or source.with_name(f"{source.stem}_colors.csv")
    write_csv(rows, output)
    print(f"{len(rows)} notes -> {output} ({color_summary(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
