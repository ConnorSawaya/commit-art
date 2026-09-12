"""Layout engine: measure text, fit checks, auto-wrap, stacked plans."""

try:
    from contribution_art.renderer import (
        render_text, render_mini, render_stacked,
        count_active_pixels, grid_width,
    )
except ImportError:  # pragma: no cover
    from .renderer import (
        render_text, render_mini, render_stacked,
        count_active_pixels, grid_width,
    )


def measure_text(text, spacing=1):
    """Measure a single full-size line -> dict with dimensions."""
    grid = render_text(text, spacing=spacing)
    width = grid_width(grid)
    pixels = count_active_pixels(grid)
    return {
        'characters': len(text),
        'pixel_width': width,
        'weeks_required': width,  # 1 pixel column == 1 calendar week column
        'active_pixels': pixels,
    }


def measure_mini(text, spacing=1):
    """Measure one stacked-mode (3-row font) line -> same dict shape."""
    grid = render_mini(text, spacing=spacing)
    return {
        'characters': len(text),
        'pixel_width': grid_width(grid),
        'weeks_required': grid_width(grid),
        'active_pixels': count_active_pixels(grid),
    }


def fits_single_line(text, max_weeks=52, spacing=1):
    """True if text pixel width fits within max_weeks columns."""
    return measure_text(text, spacing=spacing)['pixel_width'] <= max_weeks


def usage_percent(pixel_width, max_weeks):
    """Horizontal graph width used, in percent."""
    if max_weeks <= 0:
        return 0.0
    return pixel_width / max_weeks * 100.0


def estimate_commits(active_pixels, commits_per_pixel=3):
    """Estimated commit count for given active pixels."""
    return active_pixels * commits_per_pixel


def auto_wrap(text, max_weeks=52, spacing=1, measure=None):
    """Split text into two balanced lines at a space.

    Returns (line1, line2). If text already fits, returns (text, '').
    `measure` picks the font: full-size by default, mini for stacked mode.
    Prefers splits where both lines fit and widths are similar.
    Falls back to minimizing the max width; hard-splits mid-word only
    when no spaces exist.
    """
    measure = measure or measure_text
    text = text.strip()
    if not text:
        return ('', '')
    if measure(text, spacing=spacing)['pixel_width'] <= max_weeks:
        return (text, '')
    words = text.split()
    if len(words) < 2:
        # Hard split a single long word near the middle.
        mid = len(text) // 2
        return (text[:mid].rstrip(), text[mid:].lstrip())
    best = None
    best_key = None
    for i in range(1, len(words)):
        l1 = ' '.join(words[:i])
        l2 = ' '.join(words[i:])
        w1 = measure(l1, spacing=spacing)['pixel_width']
        w2 = measure(l2, spacing=spacing)['pixel_width']
        fits_both = w1 <= max_weeks and w2 <= max_weeks
        key = (0 if fits_both else 1, abs(w1 - w2), max(w1, w2))
        if best_key is None or key < best_key:
            best_key = key
            best = (l1, l2)
    return best


def plan_layout(text='', max_weeks=52, spacing=1, commits_per_pixel=3,
                auto_wrap_enabled=False, line1=None, line2=None):
    """Plan single-line (full font) or stacked two-line (mini font) layout.

    Stacked mode puts line 1 on rows 0-2 and line 2 on rows 4-6 of the
    SAME week columns — letters truly on top of each other in one graph.
    Returns dict: mode ('single'|'stacked'), lines, widths,
    pixels_per_line, total_pixels, estimated_commits, fits,
    usage_percent, warnings.
    """
    warnings = []
    stacked = False
    if line1 is not None or line2 is not None:
        l1 = (line1 or '').strip()
        l2 = (line2 or '').strip()
        nonempty = [l for l in (l1, l2) if l]
        if not nonempty:
            raise ValueError('line1/line2 mode needs at least one line')
        if len(nonempty) == 1:
            lines = nonempty
        else:
            lines = nonempty
            stacked = True
    elif auto_wrap_enabled:
        a, b = auto_wrap(text, max_weeks=max_weeks, spacing=spacing,
                         measure=measure_mini)
        if b:
            lines = [a, b]
            stacked = True
        else:
            lines = [text]
    else:
        lines = [text]

    mode = 'stacked' if stacked else 'single'
    widths = []
    pixels_per_line = []
    for ln in lines:
        m = (measure_mini(ln, spacing=spacing) if stacked
             else measure_text(ln, spacing=spacing))
        widths.append(m['pixel_width'])
        pixels_per_line.append(m['active_pixels'])

    grid_width_cols = max(widths) if widths else 0
    grid = render_stacked(*lines, spacing=spacing) if stacked else None
    total_pixels = (count_active_pixels(grid) if grid is not None
                    else sum(pixels_per_line))
    estimated = estimate_commits(total_pixels, commits_per_pixel)
    fits = grid_width_cols <= max_weeks
    if mode == 'single' and not fits:
        warnings.append(
            'Text needs %d weeks but only %d available; try --auto-wrap '
            'or --line1/--line2.' % (grid_width_cols, max_weeks))
    if stacked and not fits:
        warnings.append(
            'Stacked lines need %d weeks but only %d available.'
            % (grid_width_cols, max_weeks))
    if stacked:
        warnings.append(
            'Stacked mode uses the compact 3-row font: line 1 on rows 0-2, '
            'line 2 on rows 4-6, same weeks.')

    return {
        'mode': mode,
        'lines': lines,
        'widths': widths,
        'grid_width': grid_width_cols,
        'pixels_per_line': pixels_per_line,
        'total_pixels': total_pixels,
        'estimated_commits': estimated,
        'fits': fits,
        'usage_percent': usage_percent(grid_width_cols, max_weeks),
        'warnings': warnings,
    }
