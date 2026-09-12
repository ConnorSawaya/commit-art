from datetime import date, timedelta

import pytest

from contribution_art.dates import (
    is_sunday, prev_sunday, next_sunday, parse_start,
    resolve_start_single,
    grid_to_dates, check_no_future,
)


def test_sunday_helpers():
    sun = date(2026, 1, 4)  # a Sunday
    assert is_sunday(sun) is True
    assert is_sunday(sun + timedelta(days=1)) is False
    assert prev_sunday(sun) == sun
    assert prev_sunday(sun + timedelta(days=3)) == sun
    assert next_sunday(sun) == sun
    assert next_sunday(sun + timedelta(days=1)) == sun + timedelta(days=7)


def test_parse_start():
    assert parse_start(None) is None
    assert parse_start('auto') is None
    assert parse_start('2026-01-04') == date(2026, 1, 4)
    with pytest.raises(ValueError):
        parse_start('not-a-date')


def test_resolve_single_returns_sunday_and_no_future():
    today = date(2026, 9, 11)  # Friday
    s = resolve_start_single(9, today=today)
    assert is_sunday(s)
    end = s + timedelta(days=8 * 7 + 6)
    assert end <= today


@pytest.mark.parametrize('today', [date(2024, 2, 29), date(2026, 1, 4),
                                   date(2026, 9, 11), date(2026, 9, 12)])
def test_auto_never_future_any_weekday(today):
    from contribution_art.renderer import render_text, grid_width
    for text in ['HI', 'HELLO WORLD']:
        w = grid_width(render_text(text))
        s = resolve_start_single(w, today=today)
        for (_, _, d) in grid_to_dates(render_text(text), s):
            assert d <= today, (text, today, d)


def test_explicit_start_must_be_sunday():
    with pytest.raises(ValueError):
        resolve_start_single(5, today=date(2026, 9, 11),
                             start=date(2026, 9, 9))  # Wednesday


def test_explicit_future_start_rejected():
    with pytest.raises(ValueError):
        resolve_start_single(10, today=date(2026, 1, 10),
                             start=date(2026, 1, 4))  # ends after today


def test_grid_mapping_sunday_saturday():
    grid = [[1], [0], [0], [0], [0], [0], [1]]  # Sun + Sat of one week
    s = date(2026, 1, 4)
    pts = grid_to_dates(grid, s)
    assert pts[0][2] == s  # row 0 -> Sunday
    assert pts[1][2] == s + timedelta(days=6)  # row 6 -> Saturday
    assert pts[0][0] == 0 and pts[1][0] == 6


def test_leap_year():
    # Range covering Feb 29 2024 must include it when pixel active every day.
    grid = [[1] * 10 for _ in range(7)]
    s = date(2024, 2, 25)  # Sunday before leap day
    got = {d for (_, _, d) in grid_to_dates(grid, s)}
    assert date(2024, 2, 29) in got


def test_year_boundary():
    grid = [[1] * 3 for _ in range(7)]
    s = date(2025, 12, 28)  # Sunday
    got = sorted({d for (_, _, d) in grid_to_dates(grid, s)})
    assert got[0] == date(2025, 12, 28)
    assert date(2026, 1, 1) in got


def test_check_no_future():
    assert check_no_future([date(2026, 1, 1)], today=date(2026, 9, 11)) is True
    assert check_no_future([date(2026, 9, 12)], today=date(2026, 9, 11)) is False


def test_stacked_grid_uses_single_range():
    # Stacked lines share one week range: rows 0-2 and 4-6, same columns.
    from contribution_art.renderer import render_stacked
    grid = render_stacked('HI', 'YO')
    assert len(grid) == 7
    assert all(v == 0 for v in grid[3])  # single gap row
    s = resolve_start_single(len(grid[0]), today=date(2026, 9, 11))
    pts = grid_to_dates(grid, s)
    top = {d for (r, _, d) in pts if r in (0, 1, 2)}
    bottom = {d for (r, _, d) in pts if r in (4, 5, 6)}
    assert top and bottom
    # Same week columns -> dates share the same Sunday-anchored weeks.
    assert min(top) >= s and max(bottom) <= date(2026, 9, 11)
