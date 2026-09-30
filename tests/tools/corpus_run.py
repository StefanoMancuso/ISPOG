# -*- coding: utf-8 -*-
"""
Analyze every score of the corpus and save the results for a visual check (plan, F8).

For each file in tests/corpus (or ISPOG_CORPUS), writes to tests/corpus/_output/:
    <name>_ispog.musicxml       colored score with labels, to open in MuseScore and in the
                                editor the file came from
    <name>_ispog_report.txt     playability report
and prints one line per file: exporting software, parts, guitars, notes per color, errors.
It also lists the sources F8 asks for that the corpus does not cover yet.

From the repository root:
    python tests/tools/corpus_run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conftest import CORPUS_DIR, CORPUS_OUTPUT, corpus_files  # noqa: E402
from core import (AnalysisConfig, IspogError, analyze, list_parts, load_score,  # noqa: E402
                  render_report)

STANDARD = ("E4", "B3", "G3", "D3", "A2", "E2")

# Sources required by F8: label -> words expected in <encoding><software> (lower case)
SOURCES = {
    "MuseScore 3": ("musescore 3",),
    "MuseScore 4": ("musescore 4", "musescore studio 4"),
    "Sibelius": ("sibelius",),
    "Finale": ("finale",),
    "Dorico": ("dorico",),
    "Guitar Pro": ("guitar pro",),
}


def software(path: Path) -> str:
    try:
        text = load_score(path).getroot().findtext("identification/encoding/software")
    except IspogError:
        return "?"
    return (text or "?").strip()


def main() -> int:
    files = corpus_files()
    if not files:
        print(f"No scores in {CORPUS_DIR}")
        return 0
    out_dir = CORPUS_DIR / CORPUS_OUTPUT
    out_dir.mkdir(exist_ok=True)

    header = f"{'file':<36} {'software':<24} parts guit notes green orange red  black"
    print(header)
    print("-" * len(header))
    seen_software, failures, kinds = [], 0, set()
    for path in files:
        name = path.relative_to(CORPUS_DIR).as_posix()
        soft = software(path)
        seen_software.append(soft.lower())
        kinds.add(path.suffix.lower())
        try:
            parts = list_parts(load_score(path))
            result = analyze(AnalysisConfig(path, tuning=STANDARD))
        except IspogError as e:
            failures += 1
            print(f"{name[:36]:<36} {soft[:24]:<24} ERROR {e}")
            continue
        stem = path.stem
        (out_dir / f"{stem}_ispog.musicxml").write_bytes(result.outputs["full"])
        (out_dir / f"{stem}_ispog_report.txt").write_text(render_report(result),
                                                          encoding="utf-8")
        totals = {c: sum(r.counts[c] for r in result.reports)
                  for c in ("green", "orange", "red", "black")}
        notes = sum(totals.values())
        guitars = sum(p.is_guitar for p in parts)
        if len(parts) > 1 and guitars > 1:
            kinds.add("ensemble")
        print(f"{name[:36]:<36} {soft[:24]:<24} {len(parts):>5} {guitars:>4} {notes:>5} "
              f"{totals['green']:>5} {totals['orange']:>6} {totals['red']:>4} "
              f"{totals['black']:>6}")

    missing = [label for label, words in SOURCES.items()
               if not any(w in s for s in seen_software for w in words)]
    if ".mxl" not in kinds:
        missing.append(".mxl (compressed)")
    if "ensemble" not in kinds:
        missing.append("ensemble with 2+ guitars")
    print()
    print(f"Output: {out_dir}")
    print("Missing sources: " + (", ".join(missing) if missing else "none"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
