"""Render text into binary pixel grids and terminal previews."""

from datetime import timedelta

try:
    from contribution_art.font import FONT_HEIGHT, MINI_HEIGHT, get_glyph, get_mini_glyph
except ImportError:  # pragma: no cover - fallback for direct script use
    from .font import FONT_HEIGHT, MINI_HEIGHT, get_glyph, get_mini_glyph

# Intensity level -> commits mapping (binary mode uses commits_per_pixel).
INTENSITY_COMMITS = {1: 1, 2: 3, 3: 6, 4: 10}

FULL = '\u2588\u2588'
EMPTY = '  '


def render_text(text, spacing=1):
    """Render text to a 7-row binary grid (list of 7 lists of int).

    One blank column of `spacing` pixels separates characters (no
    trailing separator). Space characters contribute blank columns.
    """
    rows = [[0] * 0 for _ in range(FONT_HEIGHT)]
    glyphs = [get_glyph(c) for c in text]
    for i, g in enumerate(glyphs):
        w = len(g[0])
        for r in range(FONT_HEIGHT):
            rows[r].extend(1 if c == '1' else 0 for c in g[r])
        if i != len(glyphs) - 1:
            for r in range(FONT_HEIGHT):
                rows[r].extend([0] * spacing)
    return rows


def text_to_grid(text, spacing=1):
    """Alias for render_text."""
    return render_text(text, spacing=spacing)


def render_mini(text, spacing=1):
    """Render text with the compact 3-row font -> 3-row binary grid."""
    rows = [[0] * 0 for _ in range(MINI_HEIGHT)]
    glyphs = [get_mini_glyph(c) for c in text]
    for i, g in enumerate(glyphs):
        for r in range(MINI_HEIGHT):
            rows[r].extend(1 if c == '1' else 0 for c in g[r])
        if i != len(glyphs) - 1:
            for r in range(MINI_HEIGHT):
                rows[r].extend([0] * spacing)
    return rows


def render_stacked(line1, line2, spacing=1):
    """Stack two mini-font lines in one 7-row grid (same week columns).

    Line 1 occupies rows 0-2, row 3 is the gap, line 2 rows 4-6:
    3+1+3 fills all 7 rows, nothing wasted.
    Grid width = wider line; the shorter is left-aligned, padded right.
    """
    g1 = render_mini(line1, spacing=spacing)
    g2 = render_mini(line2, spacing=spacing)
    width = max(len(g1[0]) if g1[0] else 0, len(g2[0]) if g2[0] else 0)

    def _pad(grid):
        out = []
        for row in grid:
            out.append(list(row) + [0] * (width - len(row)))
        return out

    gap = [[0] * width]
    return _pad(g1) + gap + _pad(g2)


def grid_width(grid):
    """Return number of columns in a grid (0 for empty)."""
    if not grid or not grid[0]:
        return 0
    return len(grid[0])


def grid_height(grid):
    """Return number of rows (always 7 for our font)."""
    return len(grid)


def count_active_pixels(grid):
    """Count cells == 1."""
    return sum(sum(row) for row in grid)


def map_intensity(grid, level=1):
    """Attach a uniform intensity level (binary default). Passthrough grid."""
    return grid


def commits_for_grid(grid, commits_per_pixel=3, intensity_map=None):
    """Estimate commits: active pixels * per-pixel count.

    intensity_map optionally maps stored intensity values; for binary
    grids every active pixel uses commits_per_pixel.
    """
    pixels = count_active_pixels(grid)
    if intensity_map:
        # Binary grids store only 0/1; level>=1 pixels use map when given.
        return pixels * intensity_map.get(1, commits_per_pixel)
    return pixels * commits_per_pixel


def render_preview(grid):
    """Render grid with Unicode full blocks: '1' -> '\u2588\u2588'."""
    lines = []
    for row in grid:
        lines.append(''.join(FULL if c else EMPTY for c in row))
    return '\n'.join(lines)


def render_preview_boxed(grid, title='CONTRIBUTION ART PREVIEW'):
    """Wrap render_preview in a box border."""
    art = render_preview(grid).split('\n')
    width = max(len(t) for t in title.split('\n')) if title else 0
    width = max(width, *(len(l) for l in art))
    top = '\u250c' + '\u2500' * (width + 2) + '\u2510'
    sep = '\u251c' + '\u2500' * (width + 2) + '\u2524'
    bot = '\u2514' + '\u2500' * (width + 2) + '\u2518'
    out = [top, '\u2502 ' + title.ljust(width) + ' \u2502', sep]
    for line in art:
        out.append('\u2502 ' + line.ljust(width) + ' \u2502')
    out.append(bot)
    return '\n'.join(out)


MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

DAY_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', '']

OFF_CELL = '··'


def shade_cell(commits_per_pixel):
    """Intensity shade for a filled cell, mirroring GitHub's Less->More."""
    if commits_per_pixel <= 1:
        return '░░'
    if commits_per_pixel <= 3:
        return '▒▒'
    if commits_per_pixel <= 6:
        return '▓▓'
    return '██'


def render_github(grid, start_sunday, commits_per_pixel=3):
    """Render grid like GitHub's contribution calendar.

    Columns are weeks (with month labels), rows are Sun-Sat (Mon/Wed/Fri
    labeled), filled cells shaded by intensity, plus a Less->More legend.
    start_sunday must be a Sunday; column c, row r == start + c*7 + r days.
    """
    height = len(grid)
    width = len(grid[0]) if height else 0
    on = shade_cell(commits_per_pixel)
    # Month header: 2-letter abbrev where the month changes.
    header = ['    ']
    seen = None
    for col in range(width):
        month = (start_sunday + timedelta(days=col * 7)).month
        if month != seen:
            header.append(MONTH_ABBR[month - 1][:2])
            seen = month
        else:
            header.append('  ')
    lines = [''.join(header).rstrip()]
    for row in range(height):
        label = DAY_LABELS[row] if row < len(DAY_LABELS) else ''
        cells = [OFF_CELL if not grid[row][col] else on for col in range(width)]
        lines.append('%-3s %s' % (label, ' '.join(cells)))
    lines.append('')
    lines.append('Less %s %s %s %s More  (%d commits/pixel)'
                 % ('░░', '▒▒', '▓▓', '██', commits_per_pixel))
    return '\n'.join(lines)
