"""Single-keypress reading (arrows + letters), stdlib only.

Windows uses msvcrt; Unix uses termios/tty raw mode. Returns the strings
'up' / 'down' / 'left' / 'right' / 'enter' / 'esc', a single character for
normal keys, or None when stdin is not a TTY (pipes/tests) or on error.
"""

import os
import sys


def _windows_key():
    import msvcrt
    ch = msvcrt.getch()
    if ch in (b'\xe0', b'\x00'):  # arrow/function-key prefix
        ch2 = msvcrt.getch()
        return {b'H': 'up', b'P': 'down',
                b'K': 'left', b'M': 'right'}.get(ch2)
    if ch in (b'\r', b'\n'):
        return 'enter'
    if ch == b'\x1b':
        return 'esc'
    if ch == b'\x03':
        raise KeyboardInterrupt
    try:
        return ch.decode('utf-8', 'ignore') or None
    except Exception:
        return None


def _unix_key():
    import tty
    import termios
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            nxt = sys.stdin.read(1)
            if nxt == '[':
                code = sys.stdin.read(1)
                return {'A': 'up', 'B': 'down',
                        'C': 'right', 'D': 'left'}.get(code, 'esc')
            return 'esc'
        if ch in ('\r', '\n'):
            return 'enter'
        if ch == '\x03':
            raise KeyboardInterrupt
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_key():
    """Read one key. See module docstring for return values."""
    try:
        if not sys.stdin.isatty():
            return None
    except Exception:
        return None
    try:
        if os.name == 'nt':
            return _windows_key()
        return _unix_key()
    except (KeyboardInterrupt, EOFError):
        raise
    except Exception:
        return None


def arrows_available():
    """True if interactive arrow navigation can work (real TTY stdin)."""
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False
