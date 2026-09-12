#!/usr/bin/env python3
"""Full-screen Textual TUI for commit-art (optional extra).

Requires `pip install textual`. Launched via:

    python commit_art.py --tui

Layout: artwork panel (left) + stats/settings/actions (right) + scrolling
log (bottom) - everything visible at once. All Git work stays local:
Build creates a disposable repo under ./test-output/ and verifies it.
Never pushes (the backend raises on any push attempt).
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button, Footer, Header, Input, Log, Select, Static,
)

from commit_art import build_plan, safe_name, _rmtree_onerror
from contribution_art.backup import backup_repos
from contribution_art.git_writer import init_repo, write_art, get_log
from contribution_art.tui_text import make_ns, art_text, stats_text, dry_run_text
from contribution_art.verifier import verify_repo


def run_build_sync(ctx, ns, repo, progress=None):
    """Blocking backend: fresh repo, real commits, verified. Returns report str."""
    if repo.exists():
        shutil.rmtree(repo, onerror=_rmtree_onerror)
    init_repo(repo)
    stats = write_art(repo, ctx['dated'], ctx['text_label'],
                      commits_per_pixel=ns.commits_per_pixel,
                      progress=progress)
    total = stats['commit_count']
    entries = get_log(repo)
    report = verify_repo(repo, ctx['uniq_dates'],
                         ctx['plan']['estimated_commits'], today=ctx['today'])
    lines = ['Built %d commits in %s' % (total, repo),
             'Log entries: %d (author+committer dates checked)' % len(entries)]
    for e in entries[:3]:
        lines.append('  %s | %s | %s' % (e['hash'][:7], e['author_iso'][:10],
                                         e['subject'][:50]))
    lines.append('RESULT: %s' % ('PASS' if report['ok'] else 'FAIL'))
    for err in report.get('errors', []):
        lines.append('  error: %s' % err)
    return '\n'.join(lines)


class CommitArtApp(App):
    """Side-by-side art + controls + log, everything visible at once."""

    TITLE = 'Commit Art'
    SUB_TITLE = 'contribution-calendar studio (local only)'

    CSS = """
    #main { height: 1fr; }
    #left { width: 2fr; border: solid green; padding: 0 1; overflow-y: auto; }
    #right { width: 38; border: solid cyan; padding: 0 1; overflow-y: auto; }
    #art { height: auto; }
    #stats { height: auto; border-top: solid cyan; margin-top: 1; }
    #log { height: 10; border: solid yellow; }
    Button { margin-right: 1; }
    """

    BINDINGS = [
        Binding('t', 'build', 'Build+verify'),
        Binding('d', 'dryrun', 'Dry-run'),
        Binding('g', 'view', 'Toggle view'),
        Binding('b', 'backup', 'Backup'),
        Binding('q', 'quit', 'Quit'),
    ]

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.ctx = None
        self.ns = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id='main'):
            with Vertical(id='left'):
                yield Static('Type text on the right to preview...', id='art')
            with Vertical(id='right'):
                yield Input(placeholder='Text e.g. HELLO WORLD', id='text')
                yield Input(placeholder='Line 1 (two-line, optional)', id='line1')
                yield Input(placeholder='Line 2 (two-line, optional)', id='line2')
                with Horizontal():
                    yield Select([('Blocks', 'blocks'), ('GitHub', 'github')],
                                 value=getattr(self.args, 'view', 'blocks'), id='view')
                    yield Select([('1/px', 1), ('3/px', 3), ('5/px', 5), ('10/px', 10)],
                                 value=self.args.commits_per_pixel, id='cpp')
                with Horizontal():
                    yield Select([('wrap off', False), ('wrap on', True)],
                                 value=self.args.auto_wrap, id='wrap')
                    yield Input(value=str(self.args.start), placeholder='start',
                                id='start')
                with Horizontal():
                    yield Button('Build+Verify', id='build', variant='success')
                    yield Button('Dry-run', id='dry')
                    yield Button('Backup', id='backup')
                yield Static('stats...', id='stats')
        yield Log(id='log', highlight=True)
        yield Footer()

    # -- state ---------------------------------------------------------
    def current_ns(self):
        text = (self.query_one('#text', Input).value or '').strip() or None
        l1 = (self.query_one('#line1', Input).value or '').strip() or None
        l2 = (self.query_one('#line2', Input).value or '').strip() or None
        two = bool(l1 or l2)  # any line input wins over the single text box
        return make_ns(
            text=None if two else text,
            line1=l1 if two else None,
            line2=l2 if two else None,
            commits_per_pixel=self.query_one('#cpp', Select).value,
            spacing=self.args.spacing, max_weeks=self.args.max_weeks,
            start=(self.query_one('#start', Input).value or 'auto').strip(),
            auto_wrap=bool(self.query_one('#wrap', Select).value),
            view=self.query_one('#view', Select).value,
            output=self.args.output)

    def refresh_panels(self):
        art = self.query_one('#art', Static)
        stats = self.query_one('#stats', Static)
        try:
            self.ns = self.current_ns()
            if (not self.ns.text) and self.ns.line1 is None and self.ns.line2 is None:
                art.update('Type text on the right to preview...')
                stats.update('stats...')
                self.ctx = None
                return
            self.ctx = build_plan(self.ns)
        except (ValueError, SystemExit) as e:
            self.ctx = None
            art.update('Cannot preview: %s' % e)
            return
        except Exception as e:  # noqa: BLE001 - TUI must never traceback
            self.ctx = None
            art.update('Cannot preview (unexpected): %s: %s'
                       % (type(e).__name__, e))
            return
        art.update(art_text(self.ctx, self.ns.view, self.ns.commits_per_pixel))
        stats.update(stats_text(self.ctx, self.ns.commits_per_pixel,
                                self.ns.max_weeks))

    def log_line(self, msg):
        self.query_one('#log', Log).write_line(msg)

    # -- events --------------------------------------------------------
    async def on_key(self, event):
        # Typing in an input consumes letters; Esc drops focus to the
        # body so single-key shortcuts (t/d/g/b/q) work afterwards.
        if event.key == 'escape':
            self.screen.set_focus(None)

    @on(Input.Changed)
    @on(Select.Changed)
    def on_setting_changed(self, event):
        self.refresh_panels()

    @on(Button.Pressed, '#dry')
    def do_dryrun(self):
        if not self.ctx:
            self.refresh_panels()
        if not self.ctx:
            self.log_line('Nothing to dry-run yet.')
            return
        self.log_line(dry_run_text(self.ctx))

    @on(Button.Pressed, '#backup')
    def do_backup(self):
        base = Path(self.args.output) if self.args.output \
            else Path(__file__).resolve().parent / 'test-output'
        try:
            dest = backup_repos(base)
        except (FileNotFoundError, OSError) as e:
            self.log_line('Backup failed: %s' % e)
            return
        self.log_line('Backup -> %s' % dest)

    @on(Button.Pressed, '#build')
    def do_build(self):
        if not self.ctx:
            self.refresh_panels()
        if not self.ctx:
            self.log_line('Nothing to build yet.')
            return
        base = Path(self.args.output) if self.args.output \
            else Path(__file__).resolve().parent / 'test-output'
        plan = self.ctx['plan']
        repo = base / safe_name(self.ctx['text_label']
                                + ('_2line' if plan['mode'] == 'stacked' else ''))
        self.log_line('Building %s (%d commits)...'
                      % (repo.name, plan['estimated_commits']))
        self.run_worker(self._build_task(repo), exclusive=True)

    async def _build_task(self, repo):
        total = self.ctx['plan']['estimated_commits']
        seen = set()

        def _prog(done, _total):
            if not total:
                return
            mark = done * 100 // total // 25
            if mark not in seen:
                seen.add(mark)
                self.call_from_thread(
                    self.log_line,
                    '... %d%% (%d/%d commits)' % (mark * 25, done, total))

        try:
            out = await asyncio.to_thread(
                run_build_sync, self.ctx, self.ns, repo, _prog)
        except Exception as e:  # noqa: BLE001 - show, don't crash the TUI
            self.log_line('Build failed: %s' % e)
            return
        self.log_line(out)

    # -- key actions ---------------------------------------------------
    def action_build(self):
        self.do_build()

    def action_dryrun(self):
        self.do_dryrun()

    def action_backup(self):
        self.do_backup()

    def action_view(self):
        sel = self.query_one('#view', Select)
        sel.value = 'github' if sel.value == 'blocks' else 'blocks'
        self.refresh_panels()


def run_tui(args):
    """Entry point for `commit_art.py --tui`. Returns exit code."""
    CommitArtApp(args).run()
    return 0
