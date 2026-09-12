from commit_art import parse_args, build_plan
from contribution_art.tui_text import (
    make_ns, art_text, stats_text, dry_run_text,
)


def test_make_ns_roundtrip():
    args = parse_args(['HI', '--no-color'])
    ctx = build_plan(args)
    ns = make_ns(text='HI')
    ctx2 = build_plan(ns)
    assert ctx2['plan']['estimated_commits'] == ctx['plan']['estimated_commits']


def test_art_text_blocks():
    ctx = build_plan(parse_args(['HI', '--no-color']))
    out = art_text(ctx, 'blocks', 3)
    assert 'CONTRIBUTION ART PREVIEW' in out
    assert '\u2588\u2588' in out


def test_art_text_github_stacked():
    ctx = build_plan(parse_args(['--line1', 'HI', '--line2', 'YO', '--no-color']))
    assert ctx['plan']['mode'] == 'stacked'
    out = art_text(ctx, 'github', 3)
    assert out.count('Less') == 1 and 'More' in out
    # Both lines' pixels land in the one shared grid.
    from contribution_art.renderer import count_active_pixels
    assert count_active_pixels(ctx['grids'][0]) == ctx['plan']['total_pixels']


def test_stats_text_fields():
    ctx = build_plan(parse_args(['HI', '--no-color']))
    out = stats_text(ctx, 3, 52)
    for field in ['Text:', 'Width:', 'Usage:', 'Active pixels:',
                  'Estimated commits:', 'Fits:', 'Earliest:', 'Latest:',
                  'Mode:', 'Line 1 weeks:', 'Dates used:']:
        assert field in out, field
    assert 'HI' in out
    assert '9 of 52' in out  # Line 1 weeks vs available weeks


def test_dry_run_text_lists_dates():
    ctx = build_plan(parse_args(['HI', '--no-color']))
    out = dry_run_text(ctx)
    assert 'DRY RUN: HI' in out
    assert ctx['uniq_dates'][0].isoformat() in out
    assert 'Future dates: no' in out
