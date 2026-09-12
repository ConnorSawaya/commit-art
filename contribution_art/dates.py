"""Date math for GitHub-style contribution grids.

Grid convention: 7 rows, row 0 == Sunday .. row 6 == Saturday.
Columns are weeks. Active pixel (row, col) maps to
date = start_sunday + col*7 + row days.
"""

from datetime import date, timedelta


def is_sunday(d):
    """True if d is a Sunday. Python weekday(): Mon=0..Sun=6."""
    return d.weekday() == 6


def prev_sunday(d):
    """Most recent Sunday on or before d."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def next_sunday(d):
    """Next Sunday on or after d."""
    return d + timedelta(days=(6 - d.weekday()) % 7)


def parse_start(s):
    """Parse --start value: None/'auto' -> None; 'YYYY-MM-DD' -> date."""
    if s is None or (isinstance(s, str) and s.lower() == 'auto'):
        return None
    if isinstance(s, date):
        return s
    try:
        y, m, dd = [int(p) for p in str(s).split('-')]
        return date(y, m, dd)
    except Exception:
        raise ValueError("bad --start %r: expected YYYY-MM-DD or 'auto'" % s)


def _today_or(today):
    return today if today is not None else date.today()


def resolve_start_single(pixel_width_weeks, today=None, start=None,
                         max_weeks=52):
    """Return the Sunday starting a single-section range.

    Auto placement ends the art on the most recent full week
    (prev_sunday(today)) so no future commits are created.
    Explicit start must be a Sunday and must not end in the future.
    """
    today = _today_or(today)
    if pixel_width_weeks <= 0:
        raise ValueError('pixel width must be positive')
    if start is not None:
        if not is_sunday(start):
            raise ValueError('--start %s is not a Sunday' % start.isoformat())
        end = start + timedelta(days=(pixel_width_weeks - 1) * 7 + 6)
        if end > today:
            raise ValueError(
                '--start %s with width %d ends %s (after today %s)' % (
                    start.isoformat(), pixel_width_weeks,
                    end.isoformat(), today.isoformat()))
        return start
    end_sunday = prev_sunday(today)
    if end_sunday + timedelta(days=6) > today:
        # Current week is still in progress; end art on last Saturday
        # so auto placement can never yield future dates.
        end_sunday -= timedelta(days=7)
    return end_sunday - timedelta(days=(pixel_width_weeks - 1) * 7)


def grid_to_dates(grid, start_sunday):
    """Map active pixels to dates -> sorted list of (row, col, date)."""
    if not is_sunday(start_sunday):
        raise ValueError('start must be a Sunday')
    out = []
    height = len(grid)
    width = len(grid[0]) if height else 0
    for col in range(width):
        for row in range(height):
            if grid[row][col]:
                out.append((row, col, start_sunday + timedelta(days=col * 7 + row)))
    out.sort(key=lambda t: t[2])
    return out


def check_no_future(dates, today=None):
    """True if every date in `dates` is on or before today."""
    today = _today_or(today)
    only = [d[2] if isinstance(d, tuple) else d for d in dates]
    return all(d <= today for d in only)
