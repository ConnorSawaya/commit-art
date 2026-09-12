from contribution_art.cli_ui import (
    supports_color, paint, banner, stat_row, warn_line, error_line,
    progress_bar,
)


def test_no_color_env_disables(monkeypatch):
    monkeypatch.setenv('NO_COLOR', '1')
    assert supports_color() is False
    assert supports_color(force_off=False) is False


def test_force_off():
    assert supports_color(force_off=True) is False


def test_paint_passthrough_when_disabled():
    assert paint('hi', '\x1b[1m', enabled=False) == 'hi'
    assert 'hi' in paint('hi', '\x1b[1m', enabled=True)


def test_banner_has_title():
    out = banner('COMMIT ART', enabled=False)
    assert 'COMMIT ART' in out


def test_stat_warn_error_keep_substrings():
    assert 'Warning:' in warn_line('oops', enabled=False)
    assert 'Error:' in error_line('bad', enabled=False)
    row = stat_row('Foo', 'bar', enabled=False)
    assert 'Foo' in row and 'bar' in row


def test_progress_bar_format():
    assert progress_bar(0, 0) == '[░░░░░░░░░░░░░░░░░░░░░░░░] -- (0/0)'
    full = progress_bar(10, 10)
    assert '100%' in full and '(10/10)' in full
    half = progress_bar(1, 2)
    assert '50%' in half
