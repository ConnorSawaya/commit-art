"""Regression tests for the live TUI app (needs textual; headless pilot)."""
import asyncio

import pytest

textual = pytest.importorskip('textual')

from commit_art import parse_args  # noqa: E402
from tui import CommitArtApp  # noqa: E402
from textual.widgets import Input, Static  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_tui_single_line1_never_crashes():
    """Exact user repro: text + only Line 1 set must render, not traceback."""
    async def _go():
        app = CommitArtApp(parse_args(['--no-color']))
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one('#text', Input).value = 'hi'
            app.query_one('#line1', Input).value = '2'
            app.refresh_panels()
            await pilot.pause()
            assert app.ctx is not None
            assert app.ctx['plan']['mode'] == 'single'
            assert app.ctx['plan']['lines'] == ['2']
            art = str(app.query_one('#art', Static).render())
            assert 'Traceback' not in art
    _run(_go())


def test_tui_lines_win_over_text():
    async def _go():
        app = CommitArtApp(parse_args(['--no-color']))
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one('#text', Input).value = 'hi'
            app.query_one('#line1', Input).value = 'AA'
            app.query_one('#line2', Input).value = 'BB'
            ns = app.current_ns()
            assert ns.text is None
            assert (ns.line1, ns.line2) == ('AA', 'BB')
            app.refresh_panels()
            await pilot.pause()
            assert app.ctx['plan']['mode'] == 'stacked'
    _run(_go())


def test_tui_blank_lines_use_text():
    async def _go():
        app = CommitArtApp(parse_args(['--no-color']))
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one('#text', Input).value = 'hi'
            ns = app.current_ns()
            assert ns.text == 'hi'
            assert ns.line1 is None and ns.line2 is None
    _run(_go())
