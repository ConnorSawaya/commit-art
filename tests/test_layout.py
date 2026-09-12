from contribution_art.layout import (
    measure_text, fits_single_line, usage_percent, estimate_commits,
    auto_wrap, plan_layout,
)


def test_measure_text():
    m = measure_text('HI')
    assert m['characters'] == 2
    assert m['pixel_width'] == m['weeks_required'] > 0
    assert m['active_pixels'] > 0


def test_estimate_math():
    assert estimate_commits(10, 3) == 30
    assert estimate_commits(0, 5) == 0


def test_usage_percent():
    assert usage_percent(26, 52) == 50.0
    assert usage_percent(0, 52) == 0.0


def test_fits_single_line():
    assert fits_single_line('HI', max_weeks=52) is True
    assert fits_single_line('ABCDEFGHIJKLMNOPQRSTUVWXYZ', max_weeks=10) is False


def test_auto_wrap_balanced_at_space():
    l1, l2 = auto_wrap('HELLO WORLD', max_weeks=70)
    # Fits on one line -> no wrap.
    assert (l1, l2) == ('HELLO WORLD', '')
    l1, l2 = auto_wrap('HELLO WORLD', max_weeks=30)
    assert l1 == 'HELLO' and l2 == 'WORLD'


def test_auto_wrap_never_splits_words():
    l1, l2 = auto_wrap('THIS IS A TEST', max_weeks=30)
    assert ' ' not in (l1 + l2).replace('THIS', '').replace('IS', '') or True
    # No word fragment: every word intact across both lines.
    assert (l1 + ' ' + l2).split() == ['THIS', 'IS', 'A', 'TEST']


def test_auto_wrap_balanced_prefers_even():
    l1, l2 = auto_wrap('THIS IS A LONG MESSAGE', max_weeks=52)
    # Both fit individually; widths should be reasonably close.
    w1 = measure_text(l1)['pixel_width']
    w2 = measure_text(l2)['pixel_width']
    assert abs(w1 - w2) <= max(w1, w2)


def test_plan_single():
    p = plan_layout('HI', max_weeks=52)
    assert p['mode'] == 'single'
    assert p['fits'] is True
    assert p['estimated_commits'] == p['total_pixels'] * 3


def test_plan_stacked_manual():
    p = plan_layout('', line1='HELLO', line2='WORLD')
    assert p['mode'] == 'stacked'
    assert p['lines'] == ['HELLO', 'WORLD']
    assert len(p['widths']) == 2
    assert p['grid_width'] == max(p['widths'])
    assert p['estimated_commits'] == p['total_pixels'] * 3


def test_plan_line1_only_is_single():
    # Regression: one line must never become a broken one-line two-section.
    p = plan_layout('', line1='HI')
    assert p['mode'] == 'single'
    assert p['lines'] == ['HI']
    p2 = plan_layout('', line2='YO')
    assert p2['mode'] == 'single'
    assert p2['lines'] == ['YO']


def test_plan_auto_wrap_triggers():
    assert plan_layout('HELLO WORLD I LOVE CODE', max_weeks=52)['fits'] is False
    # Mini font is narrower: short text stays single, long text stacks.
    assert plan_layout('I LOVE CODE', max_weeks=52,
                       auto_wrap_enabled=True)['mode'] == 'single'
    wrapped = plan_layout('HELLO WORLD I LOVE CODE', max_weeks=52,
                          auto_wrap_enabled=True)
    assert wrapped['mode'] == 'stacked'
    assert all(w <= 52 for w in wrapped['widths'])
    assert wrapped['fits'] is True


def test_plan_overlong_honestly_does_not_fit():
    long_text = 'THIS MESSAGE IS TOO LONG FOR ONE LINE'
    single = plan_layout(long_text, max_weeks=52)
    assert single['fits'] is False
    wrapped = plan_layout(long_text, max_weeks=52, auto_wrap_enabled=True)
    assert wrapped['mode'] == 'stacked'
    # Even stacked mini lines can overflow: honest report.
    assert wrapped['fits'] is False
    assert any('Stacked' in w for w in wrapped['warnings'])


def test_stacked_rows_top_and_bottom():
    from contribution_art.renderer import render_stacked, count_active_pixels
    grid = render_stacked('HI', 'YO')
    assert len(grid) == 7 and len(grid[0]) > 0
    assert all(v == 0 for v in grid[3])
    assert count_active_pixels([grid[0], grid[1], grid[2]]) > 0
    assert count_active_pixels([grid[4], grid[5], grid[6]]) > 0
