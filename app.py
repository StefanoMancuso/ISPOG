# -*- coding: utf-8 -*-
"""
ISPOG - Web app
The desktop analysis in the browser (Gradio), on the same core: same options, same output
files, same report (plan, F9).

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
from typing import Optional, Sequence

import gradio as gr

from config import (DEFAULT_NUM_FRETS, LICENSE_NAME, LOG_DATE_FORMAT, LOG_FORMAT, MAX_FRETS,
                    MAX_STRINGS, MIN_FRETS, MIN_STRINGS, NOTE_LIST, PAPER_CITATION,
                    REPOSITORY_URL, STANDARD_TUNING_INDICES, TUNING_PRESETS, UI_TEXT,
                    WEB_DEFAULT_PORT, WEB_FILE_MAX_AGE, WEB_MAX_FILE_SIZE, WEB_QUEUE_SIZE,
                    WEB_SHOW_REPOSITORY, WEB_TEXT)
from config.version import __version__
from core import (AnalysisConfig, IspogError, PartInfo, analyze, list_parts, load_score,
                  output_names, preselected_part_ids, render_report, render_summary,
                  report_name)

logger = logging.getLogger('ispog.web')

CUSTOM = 'custom'
DEFAULT_PRESET = 'standard'
STAGING_ROOT = Path(tempfile.gettempdir()) / 'ispog-web'
STAGING_MAX_AGE = 600               # seconds: leftovers of analyses whose cleanup did not run
DEFAULT_CUSTOM_NOTES = tuple(NOTE_LIST[i] for i in STANDARD_TUNING_INDICES)


# ---------------------------------------------------------------------------
# Logic (no Gradio: tested directly, tests/test_web.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WebResult:
    """What one analysis shows on the page."""

    files: list[Path]                  # scores, then the report
    report: str
    summary: str
    workdir: Path                      # to delete once Gradio has copied the files


def tuning_choices() -> list[tuple[str, str]]:
    """(label, value) of the tuning dropdown: the presets, then Custom."""
    return [(preset.name, key) for key, preset in TUNING_PRESETS.items()] + [
        (WEB_TEXT['custom'], CUSTOM)]


def resolve_tuning(preset: str, num_strings: int, custom_notes: Sequence[str]) -> tuple[str, ...]:
    """
    Open strings, highest first: those of a preset, or the first ``num_strings`` custom
    notes (as the desktop Tuning panel).

    Raises:
        ValueError: unknown preset, or not enough custom notes.
    """
    if preset in TUNING_PRESETS:
        return tuple(TUNING_PRESETS[preset].get_tuning())
    if preset != CUSTOM:
        raise ValueError(f'unknown tuning: {preset!r}')
    num_strings = int(num_strings)
    notes = tuple(custom_notes[:num_strings])
    if len(notes) != num_strings or not all(notes):
        raise ValueError(f'choose a note for each of the {num_strings} strings')
    return notes


def part_label(part: PartInfo) -> str:
    return f'{part.name} ({part.part_id})'


def read_parts(path: Path) -> tuple[list[tuple[str, str]], list[str], str]:
    """
    Parts of an uploaded score: (label, id) choices, the ids to preselect, a status line.

    Raises:
        UnsupportedFileError: not a readable MusicXML score.
    """
    parts = list_parts(load_score(path))
    preselected = preselected_part_ids(parts)
    if preselected:
        status = UI_TEXT['parts_found'].format(guitars=sum(p.is_guitar for p in parts),
                                               total=len(parts))
    else:
        status = UI_TEXT['no_guitar_found']
    logger.info('%s: %d part(s), %d guitar(s)', path.name, len(parts),
                sum(p.is_guitar for p in parts))
    return [(part_label(p), p.part_id) for p in parts], preselected, status


def run_analysis(score: Path, part_ids: Sequence[str], tuning: Sequence[str], num_frets: int,
                 output_mode: str, labels: bool, staging_root: Path = STAGING_ROOT) -> WebResult:
    """
    Analyze ``score`` and write its outputs, with the desktop file names, to a new folder
    under ``staging_root``.

    Raises:
        ValueError: invalid options (the message can be shown as is).
        IspogError: the score cannot be analyzed.
    """
    config = AnalysisConfig(score, tuning=tuning, num_frets=int(num_frets),
                            part_ids=list(part_ids), output_mode=output_mode, labels=labels)
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
    return WebResult(files=files, report=report,
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

def on_score_change(score: Optional[str]):
    """New or removed score: list its parts; results of the previous score are cleared."""
    cleared = (None, '', '')                            # results, report, summary
    if not score:
        return gr.CheckboxGroup(choices=[], value=[]), '', *cleared
    try:
        choices, preselected, status = read_parts(Path(score))
    except IspogError as e:
        logger.warning('File refused: %s', e)
        return gr.CheckboxGroup(choices=[], value=[]), f'⚠ {e}', *cleared
    return gr.CheckboxGroup(choices=choices, value=preselected), status, *cleared


def on_tuning_change(preset: str):
    """A preset fills the custom fields with its notes, as in the desktop panel."""
    custom = preset == CUSTOM
    group = gr.Group(visible=custom)
    if custom:
        return (group, gr.skip(), *[gr.skip() for _ in range(MAX_STRINGS)])
    tuning = TUNING_PRESETS[preset]
    return (group, gr.Slider(value=tuning.strings),
            *[gr.Dropdown(value=note) for note in tuning.notes[:MAX_STRINGS]])


def on_strings_change(num_strings: int):
    return [gr.Dropdown(interactive=i < int(num_strings)) for i in range(MAX_STRINGS)]


def on_analyze(score: Optional[str], part_ids: list[str], preset: str, num_strings: int,
               num_frets: int, output_mode: str, labels: bool, *custom_notes: str):
    missing = (UI_TEXT['no_file_selected'] if not score
               else UI_TEXT['no_parts_selected'] if not part_ids else None)
    if missing:
        gr.Warning(missing)
        return gr.skip(), gr.skip(), gr.skip(), gr.skip()
    try:
        tuning = resolve_tuning(preset, num_strings, custom_notes)
        result = run_analysis(Path(score), part_ids, tuning, num_frets, output_mode, labels)
    except (IspogError, ValueError) as e:
        logger.warning('Analysis refused: %s', e)
        raise gr.Error(str(e)) from e
    except Exception as e:
        logger.error('Analysis failed', exc_info=True)
        raise gr.Error(WEB_TEXT['unexpected_error']) from e
    return [str(p) for p in result.files], result.report, result.summary, str(result.workdir)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def build_demo() -> gr.Blocks:
    with gr.Blocks(title=WEB_TEXT['title'], analytics_enabled=False,
                   delete_cache=(WEB_FILE_MAX_AGE // 4, WEB_FILE_MAX_AGE)) as demo:
        gr.Markdown(f"# {WEB_TEXT['title']}\n\n{WEB_TEXT['intro']}")
        workdir = gr.State(None)

        with gr.Row():
            with gr.Column(scale=1):
                score = gr.File(label=WEB_TEXT['score'], type='filepath',
                                file_types=['.musicxml', '.mxl', '.xml'])
                status = gr.Markdown()
                parts = gr.CheckboxGroup(label=WEB_TEXT['parts'], choices=[])
                with gr.Row():
                    output_mode = gr.Radio(label=WEB_TEXT['output'], value='full', choices=[
                        (WEB_TEXT['output_full'], 'full'), (WEB_TEXT['output_split'], 'split')])
                    labels = gr.Checkbox(label=WEB_TEXT['labels'], value=True)
                with gr.Row():
                    preset = gr.Dropdown(label=WEB_TEXT['tuning'], choices=tuning_choices(),
                                         value=DEFAULT_PRESET)
                    frets = gr.Slider(label=WEB_TEXT['frets'], minimum=MIN_FRETS,
                                      maximum=MAX_FRETS, step=1, value=DEFAULT_NUM_FRETS)
                with gr.Group(visible=False) as custom:
                    strings = gr.Slider(label=WEB_TEXT['strings'], minimum=MIN_STRINGS,
                                        maximum=MAX_STRINGS, step=1,
                                        value=TUNING_PRESETS[DEFAULT_PRESET].strings)
                    notes = []
                    for block in range(0, MAX_STRINGS, 4):
                        with gr.Row():
                            notes += [gr.Dropdown(
                                label=WEB_TEXT['string'].format(number=i + 1),
                                choices=list(NOTE_LIST), value=DEFAULT_CUSTOM_NOTES[i],
                                interactive=i < TUNING_PRESETS[DEFAULT_PRESET].strings,
                                min_width=80) for i in range(block, block + 4)]
                run = gr.Button(WEB_TEXT['analyze'], variant='primary')

            with gr.Column(scale=1):
                summary = gr.Markdown()
                results = gr.File(label=WEB_TEXT['results'], file_count='multiple',
                                  interactive=False)
                # monospaced, so that the report columns line up as in the .txt file
                report = gr.Code(label=WEB_TEXT['report'], language=None, lines=14,
                                 max_lines=30, interactive=False, wrap_lines=True,
                                 show_line_numbers=False, buttons=['copy'])

        gr.Markdown(footer())

        private = {'api_visibility': 'private'}
        score.change(on_score_change, score, [parts, status, results, report, summary],
                     **private)
        preset.change(on_tuning_change, preset, [custom, strings, *notes], **private)
        strings.change(on_strings_change, strings, notes, **private)
        run.click(on_analyze, [score, parts, preset, strings, frets, output_mode, labels, *notes],
                  [results, report, summary, workdir], **private
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
