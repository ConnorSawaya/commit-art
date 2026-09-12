"""Terminal styling for the commit-art CLI (stdlib only, no dependencies).

Colors auto-disable when output is piped, when NO_COLOR is set, or with
--no-color. All styling is plain ANSI so key output substrings
(e.g. 'RESULT: PASS') stay greppable.
"""

import os
import sys

RESET = '\x1b[0m'
BOLD = '\x1b[1m'
DIM = '\x1b[2m'
CYAN = '\x1b[36m'
GREEN = '\x1b[32m'
YELLOW = '\x1b[33m'
RED = '\x1b[31m'
MAGENTA = '\x1b[35m'


def supports_color(force_off=False):
    """True if we should emit ANSI colors."""
    if force_off or os.environ.get('NO_COLOR'):
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:
        return False
    if os.name == 'nt':
        # Enable virtual-terminal processing on Windows 10+.
        try:
            os.system('')
        except Exception:
            return False
    return True


def paint(text, *codes, enabled=True):
    """Wrap text in ANSI codes (passthrough when disabled)."""
    if not enabled or not codes:
        return text
    return ''.join(codes) + text + RESET


def banner(title, subtitle=None, enabled=True):
    """A centered header banner."""
    width = max(46, len(title) + 8)
    bar = '=' * width
    lines = [paint(bar, BOLD, CYAN, enabled=enabled),
             paint(title.center(width), BOLD, CYAN, enabled=enabled)]
    if subtitle:
        lines.append(paint(subtitle.center(width), DIM, enabled=enabled))
    lines.append(paint(bar, BOLD, CYAN, enabled=enabled))
    return '\n'.join(lines)


def stat_row(label, value, enabled=True, value_color=None):
    """One aligned `Label ......... value` row."""
    dots = '.' * max(2, 20 - len(label))
    left = paint('%-18s' % label, BOLD, enabled=enabled) + paint(' %s ' % dots, DIM, enabled=enabled)
    right = paint(str(value), value_color, enabled=enabled) if value_color else str(value)
    return left + right


def warn_line(msg, enabled=True):
    return paint('! Warning: %s' % msg, YELLOW, enabled=enabled)


def error_line(msg, enabled=True):
    return paint('x Error: %s' % msg, RED, BOLD, enabled=enabled)


def ok_line(msg, enabled=True):
    return paint(msg, GREEN, BOLD, enabled=enabled)


def section_title(msg, enabled=True):
    return paint('\n--- %s ---' % msg, BOLD, MAGENTA, enabled=enabled)


def progress_bar(done, total, width=24):
    """Render `[██████░░░░] 45% (90/200)` (no printing)."""
    if total <= 0:
        return '[%s] -- (0/0)' % ('░' * width)
    frac = min(1.0, done / total)
    fill = int(frac * width)
    bar = '█' * fill + '░' * (width - fill)
    return '[%s] %3d%% (%d/%d)' % (bar, int(frac * 100), done, total)


def clear_screen(enabled=True):
    """Clear the terminal (only on real TTYs; never in pipes/tests)."""
    if not enabled:
        return
    try:
        if not sys.stdout.isatty():
            return
    except Exception:
        return
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        pass
