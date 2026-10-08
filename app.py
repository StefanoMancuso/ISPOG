# -*- coding: utf-8 -*-
"""
ISPOG - Web app
The desktop analysis in the browser (Gradio), on the same core: same options (every part
with its own tuning and frets), same output files, same report, same problem list
(plan, F9).

    pip install ".[web]"
    python app.py                  # http://127.0.0.1:7860

On Render (``render.yaml``) the ``PORT`` variable is set: the app then listens on every
interface at that port.

Privacy: uploads and results live in Gradio's cache and are deleted after
``WEB_FILE_MAX_AGE``; the copies written here for Gradio are deleted as soon as Gradio has
taken them (``_discard``), or at the next analysis at the latest.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import gradio as gr

from config import (DEFAULT_NUM_FRETS, LICENSE_NAME, LOG_DATE_FORMAT, LOG_FORMAT,
                    PAPER_CITATION, REPOSITORY_URL, TUNING_PRESETS, UI_TEXT, WEB_DEFAULT_PORT,
                    WEB_FILE_MAX_AGE, WEB_MAX_FILE_SIZE, WEB_QUEUE_SIZE, WEB_SHOW_REPOSITORY,
                    WEB_TEXT)
from config.version import __version__
from core import (AnalysisConfig, IspogError, PartInfo, PartSettings, analyze, list_parts,
                  load_score, output_names, parse_tuning, preselected_part_ids, problem_points,
                  render_report, render_summary, report_name)

logger = logging.getLogger('ispog.web')

STAGING_ROOT = Path(tempfile.gettempdir()) / 'ispog-web'
STAGING_MAX_AGE = 600               # seconds: leftovers of analyses whose cleanup did not run
STANDARD = tuple(TUNING_PRESETS['standard'].get_tuning())
PART_COLUMNS = ('column_analyze', 'column_part', 'column_tuning', 'column_frets')
PROBLEM_COLUMNS = ('column_where', 'column_problem', 'column_part', 'column_reason')
STATUS_MARKS = {'orange': '🟠', 'red': '🔴', 'purple': '🟣'}


# ---------------------------------------------------------------------------
# Logic (no Gradio: tested directly, tests/test_web.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WebResult:
    """What one analysis shows on the page."""

    files: list[Path]                  # scores, then the report
    report: str
    summary: str
    problems: list[list[str]]          # rows of the problem table
    workdir: Path                      # to delete once Gradio has copied the files


def preset_choices() -> list[tuple[str, str]]:
    """(label, value) of the dropdown that fills the tuning of the ticked parts."""
    return [(preset.name, key) for key, preset in TUNING_PRESETS.items()]


def part_rows(parts: Sequence[PartInfo]) -> list[list[Any]]:
    """
    One row per part: analyze (the guitars), name, tuning (the one written in the score,
    else standard), frets.
    """
    preselected = set(preselected_part_ids(parts))
    return [[p.part_id in preselected, f'{p.name} ({p.part_id})', ' '.join(p.tuning or STANDARD),
             DEFAULT_NUM_FRETS] for p in parts]


def read_parts(path: Path) -> tuple[list[list[Any]], list[str], str]:
    """
    Parts of an uploaded score: rows of the part table, part ids (same order), status line.

    Raises:
        UnsupportedFileError: not a readable MusicXML score.
    """
    parts = list_parts(load_score(path))
    rows = part_rows(parts)
    if any(row[0] for row in rows):
        status = UI_TEXT['parts_found'].format(guitars=sum(p.is_guitar for p in parts),
                                               total=len(parts))
    else:
        status = UI_TEXT['no_guitar_found']
    logger.info('%s: %d part(s), %d guitar(s)', path.name, len(parts),
                sum(p.is_guitar for p in parts))
    return rows, [p.part_id for p in parts], status


def _ticked(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'x', '✓')
    return bool(value)


def settings_from_rows(rows: Sequence[Sequence[Any]],
                       part_ids: Sequence[str]) -> dict[str, PartSettings]:
    """
    The instrument of every ticked part, by part id, from the part table.

    Raises:
        ValueError: a ticked part has an invalid tuning or number of frets (the message
            names the part and can be shown as is).
    """
    settings = {}
    for row, part_id in zip(rows, part_ids):
        if not _ticked(row[0]):
            continue
        name = str(row[1])
        try:
            frets = int(float(row[3]))
        except (TypeError, ValueError):
            raise ValueError(f'{name}: invalid number of frets {row[3]!r}') from None
        try:
            settings[part_id] = PartSettings(parse_tuning(str(row[2] or '')), frets)
        except ValueError as e:
            raise ValueError(f'{name}: {e}') from None
    return settings


def apply_preset(rows: Sequence[Sequence[Any]], preset: str) -> list[list[Any]]:
    """The part table with the tuning of ``preset`` in every ticked part."""
    tuning = ' '.join(TUNING_PRESETS[preset].get_tuning())
    return [[row[0], row[1], tuning if _ticked(row[0]) else row[2], row[3]] for row in rows]


def problem_rows(reports) -> list[list[str]]:
    """Rows of the problem table: where, problem, part, reason and notes (markdown)."""
    rows = []
    for report in reports:
        for point in problem_points(report):
            rows.append([f'{STATUS_MARKS.get(point.color, "")} m. {point.measure}, '
                         f'beat {point.beat}', f'{point.status} · {point.label}',
                         point.part_name, '<br>'.join([point.reason, *point.details])])
    return rows


def run_analysis(score: Path, part_ids: Sequence[str], tuning: Sequence[str], num_frets: int,
                 output_mode: str, labels: bool, staging_root: Path = STAGING_ROOT,
                 part_settings: Optional[Mapping[str, PartSettings]] = None) -> WebResult:
    """
    Analyze ``score`` and write its outputs, with the desktop file names, to a new folder
    under ``staging_root``. ``part_settings`` gives the instrument of single parts; the
    others use ``tuning`` and ``num_frets``.

    Raises:
        ValueError: invalid options (the message can be shown as is).
        IspogError: the score cannot be analyzed.
    """
    config = AnalysisConfig(score, tuning=tuning, num_frets=int(num_frets),
                            part_ids=list(part_ids), output_mode=output_mode, labels=labels,
                            part_settings=dict(part_settings or {}))
    result = analyze(config)
    report = render_report(result)

    workdir = _new_workdir(staging_root)
    names = output_names(result)
    files = []
    for key, data in result.outputs.items():
        path = workdir / names[key]
        path.write_bytes(data)
        files.append(path)
    report_path = workdir / report_name(result)
    report_path.write_text(report, encoding='utf-8')
    files.append(report_path)

    summary = '\n'.join(f'- {render_summary(r)}' for r in result.reports)
    return WebResult(files=files, report=report, problems=problem_rows(result.reports),
                     summary=f"{WEB_TEXT['summary_title']}\n\n{summary}", workdir=workdir)


def _new_workdir(staging_root: Path) -> Path:
    """A fresh folder for one analysis; leftovers older than ``STAGING_MAX_AGE`` go."""
    staging_root.mkdir(parents=True, exist_ok=True)
    limit = time.time() - STAGING_MAX_AGE
    for old in staging_root.iterdir():
        try:
            if old.stat().st_mtime < limit:
                shutil.rmtree(old, ignore_errors=True)
        except OSError:
            pass                                   # removed meanwhile by another request
    workdir = staging_root / uuid.uuid4().hex
    workdir.mkdir()
    return workdir


def discard(workdir: Optional[str]) -> None:
    """Delete the folder of one analysis (Gradio has its own copy of the files)."""
    if workdir:
        shutil.rmtree(workdir, ignore_errors=True)


def footer() -> str:
    items = [WEB_TEXT['footer'].format(version=__version__, license=LICENSE_NAME)]
    if WEB_SHOW_REPOSITORY:
        items.append(WEB_TEXT['footer_repository'].format(url=REPOSITORY_URL))
    return '\n\n'.join([' · '.join(items), WEB_TEXT['cite'].format(citation=PAPER_CITATION),
                        WEB_TEXT['privacy']])


# ---------------------------------------------------------------------------
# Gradio handlers: logic above, errors as messages on the page
# ---------------------------------------------------------------------------

def _part_table(rows: list[list[Any]]) -> gr.Dataframe:
    """The part table of a score (rows added by hand have no part and are ignored)."""
    return gr.Dataframe(value=rows)


def on_score_change(score: Optional[str]):
    """New or removed score: list its parts; results of the previous score are cleared."""
    cleared = (None, '', '', [])                        # files, report, summary, problems
    if not score:
        return _part_table([]), [], '', *cleared
    try:
        rows, part_ids, status = read_parts(Path(score))
    except IspogError as e:
        logger.warning('File refused: %s', e)
        return _part_table([]), [], f'⚠ {e}', *cleared
    return _part_table(rows), part_ids, status, *cleared


def on_preset(rows: list[list[Any]], preset: Optional[str]):
    if not preset or not rows:
        return gr.skip()
    return apply_preset(rows, preset)


def on_analyze(score: Optional[str], rows: Optional[list[list[Any]]], part_ids: list[str],
               output_mode: str, labels: bool):
    rows = rows or []
    try:
        settings = settings_from_rows(rows, part_ids)
    except ValueError as e:
        raise gr.Error(str(e)) from e
    missing = (UI_TEXT['no_file_selected'] if not score
               else UI_TEXT['no_parts_selected'] if not settings else None)
    if missing:
        gr.Warning(missing)
        return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
    first = next(iter(settings.values()))
    try:
        result = run_analysis(Path(score), list(settings), first.tuning, first.num_frets,
                              output_mode, labels, part_settings=settings)
    except (IspogError, ValueError) as e:
        logger.warning('Analysis refused: %s', e)
        raise gr.Error(str(e)) from e
    except Exception as e:
        logger.error('Analysis failed', exc_info=True)
        raise gr.Error(WEB_TEXT['unexpected_error']) from e
    summary = result.summary + ('' if result.problems else f"\n\n{WEB_TEXT['no_problems']}")
    return ([str(p) for p in result.files], result.report, summary, result.problems,
            str(result.workdir))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def build_demo() -> gr.Blocks:
    with gr.Blocks(title=WEB_TEXT['title'], analytics_enabled=False,
                   delete_cache=(WEB_FILE_MAX_AGE // 4, WEB_FILE_MAX_AGE)) as demo:
        gr.Markdown(f"# {WEB_TEXT['title']}\n\n{WEB_TEXT['intro']}")
        workdir = gr.State(None)
        part_ids = gr.State([])

        with gr.Row():
            with gr.Column(scale=1):
                score = gr.File(label=WEB_TEXT['score'], type='filepath',
                                file_types=['.musicxml', '.mxl', '.xml'])
                status = gr.Markdown()
                parts = gr.Dataframe(
                    label=WEB_TEXT['parts'], headers=[WEB_TEXT[c] for c in PART_COLUMNS],
                    datatype=['bool', 'str', 'str', 'number'], type='array', value=[],
                    column_count=len(PART_COLUMNS), interactive=True,
                    static_columns=[1], column_widths=['9%', '43%', '35%', '13%'])
                preset = gr.Dropdown(label=WEB_TEXT['set_tuning'], choices=preset_choices(),
                                     value=None)
                with gr.Row():
                    output_mode = gr.Radio(label=WEB_TEXT['output'], value='full', choices=[
                        (WEB_TEXT['output_full'], 'full'), (WEB_TEXT['output_split'], 'split')])
                    labels = gr.Checkbox(label=WEB_TEXT['labels'], value=True)
                run = gr.Button(WEB_TEXT['analyze'], variant='primary')

            with gr.Column(scale=1):
                summary = gr.Markdown()
                problems = gr.Dataframe(
                    label=WEB_TEXT['problems'], headers=[WEB_TEXT[c] for c in PROBLEM_COLUMNS],
                    datatype=['str', 'str', 'str', 'markdown'], type='array', value=[],
                    interactive=False, wrap=True, column_widths=['17%', '21%', '16%', '46%'])
                results = gr.File(label=WEB_TEXT['results'], file_count='multiple',
                                  interactive=False)
                # monospaced, so that the report columns line up as in the .txt file
                report = gr.Code(label=WEB_TEXT['report'], language=None, lines=14,
                                 max_lines=30, interactive=False, wrap_lines=True,
                                 show_line_numbers=False, buttons=['copy'])

        gr.Markdown(footer())

        private = {'api_visibility': 'private'}
        score.change(on_score_change, score,
                     [parts, part_ids, status, results, report, summary, problems], **private)
        preset.input(on_preset, [parts, preset], parts, **private)
        run.click(on_analyze, [score, parts, part_ids, output_mode, labels],
                  [results, report, summary, problems, workdir], **private
                  ).then(discard, workdir, None, **private)
    return demo


def main() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    shutil.rmtree(STAGING_ROOT, ignore_errors=True)          # leftovers of a previous run
    port = os.environ.get('PORT')
    logger.info('ISPOG web %s starting', __version__)
    demo = build_demo()
    demo.queue(max_size=WEB_QUEUE_SIZE, default_concurrency_limit=1)
    demo.launch(
        # Render sets PORT and needs every interface; locally only this computer
        server_name='0.0.0.0' if port else '127.0.0.1',
        server_port=int(port or WEB_DEFAULT_PORT),
        max_file_size=WEB_MAX_FILE_SIZE,
        footer_links=['gradio'],
        run_history=False,
        ssr_mode=False,
    )


if __name__ == '__main__':
    main()
