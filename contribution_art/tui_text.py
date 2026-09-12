"""Pure text builders for the full-screen TUI panels.

No Textual dependency here — this module is importable and testable with
stdlib only. `tui.py` (the Textual app) renders these strings into panels.
"""

import argparse

try:
    from contribution_art.renderer import (
        render_preview_boxed, render_github,
    )
except ImportError:  # pragma: no cover
    from .renderer import render_preview_boxed, render_github


def make_ns(text=None, line1=None, line2=None, commits_per_pixel=3,
            spacing=1, max_weeks=52, start='auto', auto_wrap=False,
            view='blocks', output=None):
    """Build the argparse-like namespace build_plan() needs."""
    return argparse.Namespace(
        text=text, line1=line1, line2=line2,
        preview=False, dry_run=False, local_test=False,
        auto_wrap=auto_wrap, start=start,
        commits_per_pixel=commits_per_pixel,
        spacing=spacing, max_weeks=max_weeks,
        output=output, verbose=False, no_color=True,
        view=view, interactive=False)


def art_text(ctx, view='blocks', cpp=3):
    """Artwork panel: the single grid (stacked lines share it)."""
    grid = ctx['grids'][0]
    if view == 'github':
        return render_github(grid, ctx['starts'][0], cpp) + '\n'
    return render_preview_boxed(grid, 'CONTRIBUTION ART PREVIEW') + '\n'


def stats_text(ctx, cpp=3, max_weeks=52):
    """Right-hand stats panel: dimensions, estimates, dates, fit."""
    plan = ctx['plan']
    widths = '+'.join(str(w) for w in plan['widths'])
    lines = [
        'Text:              %s' % ctx['text_label'],
        'Mode:              %s' % plan['mode'],
        'Width:             %s weeks' % widths,
        'Available:         %d weeks' % max_weeks,
        'Usage:             %.1f%%' % plan['usage_percent'],
    ]
    for i, w in enumerate(plan['widths']):
        lines.append('Line %d weeks:      %d of %d' % (i + 1, w, max_weeks))
    lines.extend([
        'Active pixels:     %d' % plan['total_pixels'],
        'Commits/pixel:     %d' % cpp,
        'Estimated commits: %d' % plan['estimated_commits'],
        'Layout:            %s' % ('SINGLE LINE' if plan['mode'] == 'single'
                                   else 'STACKED'),
        'Fits:              %s' % ('yes' if plan['fits'] else 'NO'),
        'Earliest:          %s' % ctx['uniq_dates'][0].isoformat(),
        'Latest:            %s' % ctx['uniq_dates'][-1].isoformat(),
        'Dates used:        %d' % len(ctx['uniq_dates']),
    ])
    return '\n'.join(lines) + '\n'


def dry_run_text(ctx):
    """Full dry-run report (goes to the scrolling log panel)."""
    plan = ctx['plan']
    lines = ['DRY RUN: %s  (%d commits, %d dates)' % (
        ctx['text_label'], plan['estimated_commits'], len(ctx['uniq_dates']))]
    lines.extend('  %s' % d.isoformat() for d in ctx['uniq_dates'])
    lines.append('Fits: %s | Future dates: %s'
                 % ('yes' if plan['fits'] else 'NO',
                    'YES - ABORT' if any(d > ctx['today'] for d in ctx['uniq_dates'])
                    else 'no'))
    return '\n'.join(lines) + '\n'
