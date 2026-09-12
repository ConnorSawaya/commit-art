#!/usr/bin/env python3
"""commit_art.py - Git commit-history artwork on a GitHub-style calendar.

SAFETY: this tool NEVER pushes. It only creates local commits inside a
disposable ./test-output/ repository when you pass --local-test. Dry-run
and preview modes create zero commits and make zero network requests.

Examples:
  python commit_art.py "HELLO WORLD" --preview
  python commit_art.py "HELLO" --dry-run
  python commit_art.py "HELLO" --local-test
  python commit_art.py "THIS IS LONG" --auto-wrap --dry-run
  python commit_art.py --line1 "HELLO" --line2 "WORLD" --local-test
  python commit_art.py "HELLO" --start 2026-01-04 --local-test
  python commit_art.py "HELLO" --commits-per-pixel 5 --dry-run
"""

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contribution_art.renderer import (
    render_text, render_stacked, count_active_pixels, grid_width, render_preview,
    render_preview_boxed, render_github,
)
from contribution_art.layout import measure_text, plan_layout
from contribution_art.dates import (
    parse_start, resolve_start_single,
    grid_to_dates, check_no_future, prev_sunday,
)
from contribution_art.git_writer import init_repo, write_art, get_log
from contribution_art.verifier import verify_repo, format_result
from contribution_art.publish import (
    gh_logged_in, gh_user, gh_primary_email, repo_exists, create_repo,
    push_repo,
)
from contribution_art.backup import (
    export_plan, backup_repos, list_backups, restore_backup,
    default_backup_dir,
)
from contribution_art.cli_ui import (
    supports_color, paint, banner, warn_line, error_line, section_title,
    progress_bar, clear_screen, BOLD, CYAN, GREEN, YELLOW, RED, DIM,
)
from contribution_art.keys import read_key, arrows_available


def _color(args):
    return supports_color(getattr(args, 'no_color', False))


def _kv(label, value, enabled, value_color=None):
    """'Label: value' with a bold label; substrings stay greppable."""
    left = paint('%s:' % label, BOLD, enabled=enabled)
    if value_color:
        return '%s %s' % (left, paint(str(value), value_color, enabled=enabled))
    return '%s %s' % (left, value)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description='Generate Git commit-history artwork (local-only, never pushes).',
        epilog='Examples: %(prog)s "HELLO" --preview | %(prog)s "HELLO" --local-test | '
               '%(prog)s --line1 "HELLO" --line2 "WORLD" --dry-run')
    p.add_argument('text', nargs='?', default=None, help='Text to render (e.g. "HELLO WORLD").')
    p.add_argument('--preview', action='store_true', help='Show boxed preview, create zero commits.')
    p.add_argument('--dry-run', action='store_true', help='Show full plan + dates, create zero commits.')
    p.add_argument('--local-test', action='store_true', help='Create disposable local repo under ./test-output/.')
    p.add_argument('--auto-wrap', action='store_true', help='Auto-split long text into two stacked lines at spaces.')
    p.add_argument('--line1', default=None, help='Stacked line 1 (top).')
    p.add_argument('--line2', default=None, help='Stacked line 2 (bottom).')
    p.add_argument('--start', default='auto', help='Sunday YYYY-MM-DD or "auto" (default).')
    p.add_argument('--commits-per-pixel', type=int, default=3, help='Commits per active pixel 1-10 (default 3).')
    p.add_argument('--spacing', type=int, default=1, help='Blank columns between chars (default 1).')
    p.add_argument('--max-weeks', type=int, default=52, help='Available calendar weeks (default 52).')
    p.add_argument('--output', default=None, help='Override test-output directory.')
    p.add_argument('--verbose', action='store_true', help='Verbose output.')
    p.add_argument('--no-color', action='store_true', help='Disable colored output.')
    p.add_argument('--view', choices=['blocks', 'github'], default='blocks',
                   help='Art style: plain blocks or GitHub-calendar (default blocks).')
    p.add_argument('--export-plan', default=None, metavar='FILE',
                   help='Write the plan + dates to FILE as JSON (works with any mode).')
    p.add_argument('--backup', action='store_true',
                   help='Zip all repos in test-output/ into backups/ (real backend backup).')
    p.add_argument('--list-backups', action='store_true', help='List backup zips and exit.')
    p.add_argument('--restore', default=None, metavar='ZIP',
                   help='Restore a backup zip into test-output/ and exit.')
    p.add_argument('--interactive', '-i', action='store_true',
                   help='Full interactive mode: type text, preview, tweak, test.')
    p.add_argument('--tui', action='store_true',
                   help='Full-screen Textual TUI (needs: pip install textual).')
    p.add_argument('--publish', action='store_true',
                   help='Create a GitHub repo and push the art (asks to confirm).')
    p.add_argument('--repo', default=None, metavar='NAME',
                   help='GitHub repo name for --publish (default: commit-art-<text>).')
    p.add_argument('--public', action='store_true',
                   help='Make the published repo public (default: private).')
    p.add_argument('--yes', action='store_true',
                   help='Skip the --publish confirmation prompt.')
    return p.parse_args(argv)


def safe_name(s):
    n = re.sub(r'[^A-Za-z0-9-]+', '_', s).strip('_-')
    return (n or 'ART')[:50]


def build_plan(args, today=None):
    """Validate args, plan layout, resolve dates. Returns dict."""
    today = today if today is not None else date.today()
    if args.commits_per_pixel < 1 or args.commits_per_pixel > 10:
        raise SystemExit('--commits-per-pixel must be 1-10')
    if args.spacing < 0:
        raise SystemExit('--spacing must be >= 0')
    if args.max_weeks < 1:
        raise SystemExit('--max-weeks must be >= 1')
    if args.line1 is not None or args.line2 is not None:
        text_label = ' '.join(x for x in (args.line1 or '', args.line2 or '') if x).strip()
        if not text_label:
            raise SystemExit('--line1/--line2 needs at least one non-empty line')
        plan = plan_layout('', max_weeks=args.max_weeks, spacing=args.spacing,
                           commits_per_pixel=args.commits_per_pixel,
                           line1=args.line1, line2=args.line2)
    else:
        if not args.text:
            raise SystemExit('need TEXT or --line1/--line2 (see --help)')
        text_label = args.text
        plan = plan_layout(args.text, max_weeks=args.max_weeks, spacing=args.spacing,
                           commits_per_pixel=args.commits_per_pixel,
                           auto_wrap_enabled=args.auto_wrap)
    start = parse_start(args.start)
    # One grid, one date range — stacked lines share the same weeks.
    if plan['mode'] == 'stacked':
        grid = render_stacked(plan['lines'][0], plan['lines'][1],
                              spacing=args.spacing)
    else:
        grid = render_text(plan['lines'][0], spacing=args.spacing)
    s = resolve_start_single(grid_width(grid), today=today, start=start,
                             max_weeks=args.max_weeks)
    dated = grid_to_dates(grid, s)
    if not dated:
        raise SystemExit('text produces no active pixels (blank input?) - nothing to draw')
    uniq_dates = sorted({d for (_, _, d) in dated})
    return {'plan': plan, 'grids': [grid], 'starts': [s], 'dated': dated,
            'uniq_dates': uniq_dates, 'text_label': text_label, 'today': today}


def print_layout_summary(ctx, args):
    plan = ctx['plan']
    ec = _color(args)
    print(paint('TEXT: %s' % ctx['text_label'], BOLD, CYAN, enabled=ec))
    print('')
    print(_kv('Characters', sum(len(l) for l in plan['lines']), ec))
    print(_kv('Pixel width', plan['widths'][0] if len(plan['widths']) == 1
              else '+'.join(str(w) for w in plan['widths']), ec))
    print(_kv('Available weeks', args.max_weeks, ec))
    print(_kv('Active pixels', plan['total_pixels'], ec))
    print(_kv('Commits per pixel', args.commits_per_pixel, ec))
    print(_kv('Estimated commits', plan['estimated_commits'], ec, GREEN))
    print(_kv('Layout', 'SINGLE LINE' if plan['mode'] == 'single' else 'STACKED',
              ec, CYAN))
    print('')
    if plan['mode'] == 'single':
        print(paint('Single-line layout:', BOLD, enabled=ec))
        print('%d weeks required' % plan['widths'][0])
        print(paint('Fits' if plan['fits'] else 'Does not fit',
                    GREEN if plan['fits'] else YELLOW, enabled=ec))
    else:
        print(paint('Stacked layout (line 2 under line 1, same weeks):', BOLD, enabled=ec))
        for i, ln in enumerate(plan['lines']):
            print('Line %d: %s' % (i + 1, ln))
        print('')
        for i, w in enumerate(plan['widths']):
            okw = w <= args.max_weeks
            print('Line %d width: %s' % (
                i + 1, paint('%d weeks' % w, GREEN if okw else YELLOW, enabled=ec)))
        print('Graph width: %d weeks' % plan['grid_width'])
        print(_kv('Status', 'FITS' if plan['fits'] else 'DOES NOT FIT', ec,
                  GREEN if plan['fits'] else YELLOW))
    for w in plan['warnings']:
        print(warn_line(w, ec))


def _render_art(grid, start, args):
    """Render one grid in the selected view (blocks or github)."""
    if getattr(args, 'view', 'blocks') == 'github':
        return render_github(grid, start, getattr(args, 'commits_per_pixel', 3))
    return render_preview(grid)


def cmd_preview(ctx, args):
    ec = _color(args)
    print(banner('COMMIT ART', 'contribution-calendar preview', enabled=ec))
    print('')
    if getattr(args, 'view', 'blocks') == 'blocks':
        print(render_preview_boxed(ctx['grids'][0], 'CONTRIBUTION ART PREVIEW'))
    else:
        print(_render_art(ctx['grids'][0], ctx['starts'][0], args))
    print('')
    plan = ctx['plan']
    print(_kv('Text', ctx['text_label'], ec))
    print(_kv('Width', '%s weeks' % '+'.join(str(w) for w in plan['widths']), ec))
    print(_kv('Available', '%d weeks' % args.max_weeks, ec))
    print(_kv('Usage', '%.1f%%' % plan['usage_percent'], ec))
    print(_kv('Active pixels', plan['total_pixels'], ec))
    print(_kv('Commits/pixel', args.commits_per_pixel, ec))
    print(_kv('Estimated commits', plan['estimated_commits'], ec, GREEN))
    print(_kv('Layout', 'SINGLE LINE' if plan['mode'] == 'single' else 'STACKED',
              ec, CYAN))


def cmd_dry_run(ctx, args):
    plan = ctx['plan']
    ec = _color(args)
    print(banner('COMMIT ART', 'dry run - no commits will be created', enabled=ec))
    print('')
    print_layout_summary(ctx, args)
    print(section_title('ARTWORK', enabled=ec))
    if plan['mode'] == 'stacked':
        print(paint('Line 1 (top): %s' % plan['lines'][0], BOLD, enabled=ec))
        print(paint('Line 2 (bottom): %s' % plan['lines'][1], BOLD, enabled=ec))
    print(_render_art(ctx['grids'][0], ctx['starts'][0], args))
    print('')
    print(section_title('DATES', enabled=ec))
    print(_kv('Date range', '%s .. %s' % (ctx['uniq_dates'][0].isoformat(),
                                          ctx['uniq_dates'][-1].isoformat()), ec))
    print('Dates that WOULD receive commits (%d):' % len(ctx['uniq_dates']))
    for d in ctx['uniq_dates']:
        print('  %s' % d.isoformat())
    print(_kv('Layout mode', plan['mode'], ec, CYAN))
    print(_kv('Fits on graph', 'yes' if plan['fits'] else 'NO', ec,
              GREEN if plan['fits'] else YELLOW))
    future = [d for d in ctx['uniq_dates'] if d > ctx['today']]
    print(_kv('Any date in the future', 'YES - ABORT' if future else 'no', ec,
              RED if future else GREEN))
    if args.verbose:
        print('Start Sundays: %s' % ', '.join(s.isoformat() for s in ctx['starts']))
        print('Today: %s (prev Sunday %s)' % (
            ctx['today'].isoformat(), prev_sunday(ctx['today']).isoformat()))
    print('')
    print(paint('DRY RUN COMPLETE', BOLD, GREEN, enabled=ec))
    print(paint('No Git commits were created.', GREEN, enabled=ec))


def _rmtree_onerror(func, path, _exc):
    # Windows: git object files can be read-only; clear flag and retry once.
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def cmd_local_test(ctx, args):
    plan = ctx['plan']
    ec = _color(args)
    print(banner('COMMIT ART', 'local test - disposable repo, never pushed', enabled=ec))
    print('')
    print_layout_summary(ctx, args)
    print('')
    base = Path(args.output) if args.output else Path(__file__).resolve().parent / 'test-output'
    repo = base / safe_name(ctx['text_label'] + ('_2line' if plan['mode'] == 'stacked' else ''))
    print(_kv('Local repo', repo, ec))
    if repo.exists():
        # Disposable dir: start fresh so verification counts exact commits.
        shutil.rmtree(repo, onerror=_rmtree_onerror)
        if repo.exists():
            print(error_line('cannot clear %s (close programs using it)' % repo, ec),
                  file=sys.stderr)
            return False
    init_repo(repo)
    # One grid, one date range: stacked lines share the same weeks.
    show_bar = ec and sys.stdout.isatty()

    def _prog(done, _total):
        if show_bar:
            sys.stdout.write('\r  ' + progress_bar(done, plan['estimated_commits']))
            sys.stdout.flush()

    stats = write_art(repo, ctx['dated'], ctx['text_label'],
                      commits_per_pixel=args.commits_per_pixel,
                      progress=_prog if show_bar else None)
    total = stats['commit_count']
    if show_bar:
        sys.stdout.write('\n')
    print(_kv('Wrote', '%d commits' % total, ec, GREEN))
    entries = get_log(repo)
    print(paint('git log sample (first 5):', BOLD, enabled=ec))
    for e in entries[:5]:
        print('  %s | %s | %s | %s' % (e['hash'][:7], e['author_iso'], e['committer_iso'], e['subject'][:60]))
    report = verify_repo(repo, ctx['uniq_dates'], plan['estimated_commits'], today=ctx['today'])
    print(format_result(report))
    print(paint('RESULT: %s' % ('PASS' if report['ok'] else 'FAIL'),
                GREEN if report['ok'] else RED, BOLD, enabled=ec))
    return report['ok']


def _ask(prompt, default=None):
    """Prompt with optional default; returns None on EOF/Ctrl-C-quit."""
    tag = ' [%s]' % default if default is not None else ''
    try:
        ans = input('%s%s: ' % (prompt, tag))
    except (EOFError, KeyboardInterrupt):
        print('')
        return None
    ans = ans.strip()
    return ans if ans else default


def _pause():
    """'Press Enter to continue'. False means quit (EOF/Ctrl-C)."""
    try:
        input('Press Enter to continue... ')
    except (EOFError, KeyboardInterrupt):
        print('')
        return False
    return True


def _setup_two_line(l1, l2):
    """Prompt for two-line mode. Returns (two, l1, l2, combined) or None on quit.

    Blank line 1 exits to single-line mode; blank line 2 keeps line 1
    as single-line text. Raw input (no defaults) so blank is unambiguous.
    """
    cur = ' [current: %s / %s]' % (l1 or '-', l2 or '-') if (l1 or l2) else ''
    try:
        nl1 = input('Line 1 (blank = single-line mode)%s: ' % cur).strip()
        if not nl1:
            return (False, None, None, None)
        nl2 = input('Line 2 (blank = line 1 alone): ').strip()
    except (EOFError, KeyboardInterrupt):
        print('')
        return None
    if not nl2:
        return (False, None, None, nl1)
    return (True, nl1, nl2, '%s %s' % (nl1, nl2))


def _settings_bar(cpp, auto, start, view, enabled):
    return paint('settings: commits/pixel=%d   auto-wrap=%s   start=%s   view=%s'
                 % (cpp, 'on' if auto else 'off', start, view), DIM, enabled=enabled)


# (action id, label, shortcut key) for the interactive menu.
ACTIONS = [
    ('new', 'New text', 'Enter'),
    ('test', 'Build + verify locally', 'T'),
    ('dry', 'Full dry-run (every date)', 'D'),
    ('cpp', 'Commits per pixel', 'C'),
    ('wrap', 'Auto-wrap on/off', 'W'),
    ('start', 'Start date', 'S'),
    ('two', 'Two-line mode', '2'),
    ('view', 'View blocks/github', 'G'),
    ('backup', 'Backup repos', 'B'),
    ('quit', 'Quit', 'Q'),
]

_SHORTCUT_TO_ACTION = {'t': 'test', 'd': 'dry', 'c': 'cpp', 'w': 'wrap',
                       's': 'start', '2': 'two', 'g': 'view', 'b': 'backup',
                       'q': 'quit', 'n': 'new'}


def _print_menu(selected, enabled):
    print('')
    print(paint(' Actions  (Up/Down + Enter, or letter key)', BOLD, enabled=enabled))
    for i, (_aid, label, key) in enumerate(ACTIONS):
        marker = '>>' if i == selected else '  '
        row = '%s [%s] %s' % (marker, key, label)
        if i == selected:
            print(paint(row, BOLD, CYAN, enabled=enabled))
        else:
            print(row)


def _render_screen(ctx, ns, cpp, auto, start, view, ec):
    """Full display reset: banner, art, stats, settings (no menu)."""
    clear_screen(ec)
    cmd_preview(ctx, ns)
    print('')
    print(_settings_bar(cpp, auto, start, view, ec))


def _arrow_menu(ctx, ns, cpp, auto, start, view, ec):
    """Arrow-key menu. Returns an action id ('new','test',...)."""
    idx = 0
    while True:
        _render_screen(ctx, ns, cpp, auto, start, view, ec)
        _print_menu(idx, ec)
        try:
            key = read_key()
        except (KeyboardInterrupt, EOFError):
            print('')
            return 'quit'
        if key is None:  # stdin went away; fall back to quit, not hang
            return 'quit'
        if key == 'up':
            idx = (idx - 1) % len(ACTIONS)
        elif key == 'down':
            idx = (idx + 1) % len(ACTIONS)
        elif key == 'enter':
            return ACTIONS[idx][0]
        elif key in ('esc',):
            return 'quit'
        elif isinstance(key, str) and len(key) == 1:
            hit = _SHORTCUT_TO_ACTION.get(key.lower())
            if hit is not None:
                return hit
        # ignore left/right/unknown keys, redraw


def run_interactive(args):
    """Full-screen TUI: art on top, arrow-key menu below. Returns exit code."""
    ec = _color(args)
    cpp = args.commits_per_pixel
    auto = args.auto_wrap
    start = args.start
    view = getattr(args, 'view', 'blocks')
    l1, l2 = args.line1, args.line2
    use_arrows = arrows_available()
    clear_screen(ec)
    print(banner('COMMIT ART', 'interactive mode - arrows + Enter, Q quits', enabled=ec))
    print(paint('Type words, see them as contribution art, test them locally.',
                enabled=ec))
    while True:
        text = _ask('\nText (e.g. HELLO WORLD)', default=None)
        if text is None:
            print('Bye.')
            return 0
        if not text:
            continue
        if text.lower() in ('q', 'quit', 'exit'):
            print('Bye.')
            return 0
        # Fresh input always starts single-line; two-line is set via the
        # menu. (Fixes old bug where two-line state stuck across new texts.)
        l1, l2 = None, None
        two = False
        while True:
            ns = argparse.Namespace(
                text=None if two else text,
                line1=l1 if two else None,
                line2=l2 if two else None,
                preview=False, dry_run=False, local_test=False,
                auto_wrap=auto, start=start, commits_per_pixel=cpp,
                spacing=args.spacing, max_weeks=args.max_weeks,
                output=args.output, verbose=False, no_color=args.no_color,
                view=view, interactive=False)
            try:
                ctx = build_plan(ns)
            except (ValueError, SystemExit) as e:
                print(error_line(e, ec))
                break
            if use_arrows:
                action = _arrow_menu(ctx, ns, cpp, auto, start, view, ec)
            else:
                _render_screen(ctx, ns, cpp, auto, start, view, ec)
                _print_menu(0, ec)
                choice = _ask('Choice', default='')
                if choice is None or choice.lower() in ('q', 'quit', 'exit'):
                    action = 'quit'
                else:
                    c = choice.lower()
                    action = {'': 'new', 't': 'test', 'd': 'dry', 'c': 'cpp',
                              'w': 'wrap', 's': 'start', '2': 'two',
                              'g': 'view', 'b': 'backup'}.get(c, 'unknown')
            if action == 'quit':
                print('Bye.')
                return 0
            if action == 'new':
                clear_screen(ec)
                break  # outer loop asks for new text
            elif action == 'test':
                ok = cmd_local_test(ctx, ns)
                if not _pause():
                    print('Bye.')
                    return 0
                if not ok:
                    break
            elif action == 'dry':
                print('')
                cmd_dry_run(ctx, ns)
                if not _pause():
                    print('Bye.')
                    return 0
            elif action == 'cpp':
                val = _ask('Commits per pixel (1-10)', default=str(cpp))
                if val is None:
                    print('Bye.')
                    return 0
                try:
                    cpp = max(1, min(10, int(val)))
                except ValueError:
                    print(error_line('not a number, keeping %d' % cpp, ec))
                    if not _pause():
                        print('Bye.')
                        return 0
            elif action == 'wrap':
                auto = not auto
                print('auto-wrap %s' % ('ON' if auto else 'OFF'))
            elif action == 'start':
                val = _ask('Start Sunday YYYY-MM-DD or auto', default=start)
                if val is None:
                    print('Bye.')
                    return 0
                start = val
            elif action == 'two':
                res = _setup_two_line(l1, l2)
                if res is None:
                    print('Bye.')
                    return 0
                two, l1, l2, combined = res
                if combined is not None:
                    text = combined
            elif action == 'view':
                view = 'github' if view == 'blocks' else 'blocks'
                print('view: %s' % view)
            elif action == 'backup':
                _backup_menu(ctx, ns, ec)
                if not _pause():
                    print('Bye.')
                    return 0
            else:  # 'unknown' from letter fallback
                print(error_line('unknown choice', ec))
                if not _pause():
                    print('Bye.')
                    return 0


def _backup_menu(ctx, ns, ec):
    """Backup submenu inside interactive mode (export plan / zip / list)."""
    base = Path(ns.output) if ns.output else Path(__file__).resolve().parent / 'test-output'
    print(paint(' Backup', BOLD, enabled=ec))
    print('  [E] export this plan to JSON')
    print('  [Z] zip all test-output repos into backups/')
    print('  [L] list backups')
    sub = _ask('Backup choice (E/Z/L)', default='')
    if sub is None or sub == '':
        return
    s = sub.lower()
    try:
        if s == 'e':
            dest = _ask('Export file', default='backups/%s-plan.json'
                        % safe_name(ctx['text_label']))
            if dest is None:
                return
            out = export_plan(ctx, ns, dest)
            print(paint('Exported plan -> %s' % out, GREEN, enabled=ec))
        elif s == 'z':
            dest = backup_repos(base)
            print(paint('Backup -> %s' % dest, GREEN, enabled=ec))
        elif s == 'l':
            for b in list_backups():
                print('  %s' % b)
        else:
            print(error_line('unknown backup choice %r' % sub, ec))
    except (ValueError, FileNotFoundError, OSError) as e:
        print(error_line(e, ec))


def _maybe_export(ctx, args, ec):
    if getattr(args, 'export_plan', None):
        try:
            out = export_plan(ctx, args, args.export_plan)
            print(paint('Exported plan -> %s' % out, GREEN, enabled=ec))
        except OSError as e:
            print(error_line(e, ec), file=sys.stderr)


def cmd_publish(ctx, args):
    """Build art with the GitHub identity, create repo, push. Explicit only.

    Returns True on success. Aborts (False) when gh is missing/logged
    out, the user declines confirmation, or any step fails.
    """
    plan = ctx['plan']
    ec = _color(args)
    if not gh_logged_in():
        print(error_line('not logged in: run `gh auth login` first', ec))
        return False
    user = gh_user()
    email = gh_primary_email()
    print(_kv('GitHub account', user['login'], ec, CYAN))
    print(_kv('Commit author', '%s <%s>' % (user['name'], email), ec))
    repo_name = args.repo or ('commit-art-' + safe_name(ctx['text_label']).lower())
    full = '%s/%s' % (user['login'], repo_name)
    print(_kv('New repo', full + (' (public)' if args.public else ' (private)'), ec))
    print(_kv('Commits to push', plan['estimated_commits'], ec, GREEN))
    if not args.yes:
        print(paint('This will create %s and push %d commits to GitHub.'
                    % (full, plan['estimated_commits']), YELLOW, BOLD, enabled=ec))
        ans = _ask('Type the repo name to confirm', default=None)
        if ans != repo_name:
            print('Aborted. Nothing was created or pushed.')
            return False
    try:
        full = create_repo(repo_name, private=not args.public,
                           description='Contribution-calendar art: %s' % ctx['text_label'])
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(error_line('create repo failed: %s' % e, ec))
        return False
    print(paint('Created %s' % full, GREEN, enabled=ec))
    base = Path(args.output) if args.output else Path(__file__).resolve().parent / 'test-output'
    repo = base / (safe_name(ctx['text_label']) + '-pub')
    if repo.exists():
        shutil.rmtree(repo, onerror=_rmtree_onerror)
    init_repo(repo, user_name=user['name'], user_email=email)
    stats = write_art(repo, ctx['dated'], ctx['text_label'],
                      commits_per_pixel=args.commits_per_pixel,
                      user_name=user['name'], user_email=email)
    total = stats['commit_count']
    report = verify_repo(repo, ctx['uniq_dates'], plan['estimated_commits'],
                         today=ctx['today'])
    if not report['ok']:
        print(error_line('local verification failed, NOT pushing', ec))
        print(format_result(report))
        return False
    try:
        url = push_repo(repo, full)
    except subprocess.CalledProcessError as e:
        print(error_line('push failed: %s' % e, ec))
        return False
    print(paint('Pushed %d commits -> %s' % (total, url), GREEN, BOLD, enabled=ec))
    if not args.public:
        print('Private repo: enable "Private contributions" in GitHub profile')
        print('settings if the squares do not show up.')
    return True


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    args = parse_args(argv)
    ec = _color(args)
    if args.interactive:
        return run_interactive(args)
    if getattr(args, 'tui', False):
        try:
            from tui import run_tui
        except ImportError:
            print(error_line('the --tui screen needs Textual: pip install textual', ec),
                  file=sys.stderr)
            return 2
        return run_tui(args)
    if args.list_backups:
        found = list_backups()
        if not found:
            print('No backups yet.')
        for b in found:
            print(str(b))
        return 0
    if args.restore:
        base = Path(args.output) if args.output else Path(__file__).resolve().parent / 'test-output'
        try:
            names = restore_backup(args.restore, base)
        except (ValueError, FileNotFoundError, OSError) as e:
            print(error_line(e, ec), file=sys.stderr)
            return 2
        print(paint('Restored %d repo(s) into %s' % (len(names), base), GREEN, enabled=ec))
        for n in names:
            print('  %s' % n)
        return 0
    try:
        ctx = build_plan(args)
    except ValueError as e:
        print(error_line(e, ec), file=sys.stderr)
        return 2
    if args.preview:
        cmd_preview(ctx, args)
        _maybe_export(ctx, args, ec)
        return 0
    if args.dry_run:
        cmd_dry_run(ctx, args)
        _maybe_export(ctx, args, ec)
        return 0
    if args.local_test:
        ok = cmd_local_test(ctx, args)
        _maybe_export(ctx, args, ec)
        if args.backup and ok:
            try:
                dest = backup_repos(Path(args.output) if args.output
                                    else Path(__file__).resolve().parent / 'test-output')
                print(paint('Backup -> %s' % dest, GREEN, enabled=ec))
            except (FileNotFoundError, OSError) as e:
                print(error_line(e, ec), file=sys.stderr)
                return 1
        return 0 if ok else 1
    if args.publish:
        _maybe_export(ctx, args, ec)
        return 0 if cmd_publish(ctx, args) else 1
    # Default: plan + preview, no commits.
    print(banner('COMMIT ART', 'plan only - no commits created', enabled=ec))
    print('')
    print_layout_summary(ctx, args)
    print('')
    print(_render_art(ctx['grids'][0], ctx['starts'][0], args))
    print('')
    print('No commits created. Use --dry-run for detail or --local-test for a disposable local repo.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
