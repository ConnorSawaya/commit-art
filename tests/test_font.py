import string

from contribution_art.font import (
    FONT, FONT_HEIGHT, MINI, MINI_HEIGHT,
    get_glyph, get_mini_glyph, glyph_width,
)


def test_alphabet_present():
    for c in string.ascii_uppercase:
        assert c in FONT, 'missing glyph %r' % c


def test_digits_present():
    for c in string.digits:
        assert c in FONT, 'missing glyph %r' % c


def test_punctuation_present():
    for c in ['!', '?', '.', '-', '*', '_', ':']:
        assert c in FONT, 'missing glyph %r' % c
    assert ' ' in FONT


def test_glyphs_exactly_7_rows():
    for c, g in FONT.items():
        assert len(g) == FONT_HEIGHT, c
        w = len(g[0])
        assert 1 <= w <= 5, (c, w)
        for row in g:
            assert len(row) == w, c
            assert set(row) <= {'0', '1'}, c


def test_lowercase_fallback():
    assert get_glyph('h') == get_glyph('H')
    assert get_glyph('z') == get_glyph('Z')


def test_unknown_char_never_crashes():
    g = get_glyph('@')
    assert len(g) == FONT_HEIGHT
    g2 = get_glyph('\u00e9')
    assert len(g2) == FONT_HEIGHT


def test_space_is_blank_but_sized():
    g = get_glyph(' ')
    assert glyph_width(' ') > 0
    assert all(c == '0' for row in g for c in row)


def test_narrow_chars():
    assert glyph_width('I') < glyph_width('M')
    assert glyph_width('!') <= 2
    assert glyph_width('.') <= 2


def test_punctuation_has_pixels():
    from contribution_art.renderer import render_text, count_active_pixels
    for c in ['!', '?', '.', '-', '*', '_', ':']:
        assert count_active_pixels(render_text(c)) > 0, c


def test_mini_font_complete_and_shaped():
    for c in string.ascii_uppercase + string.digits:
        assert c in MINI, 'missing mini glyph %r' % c
    for c in ['!', '?', '.', '-', '*', '_', ':', ' ']:
        assert c in MINI, 'missing mini glyph %r' % c
    for c, g in MINI.items():
        assert len(g) == MINI_HEIGHT, c
        w = len(g[0])
        assert 1 <= w <= 5, (c, w)
        for row in g:
            assert len(row) == w and set(row) <= {'0', '1'}, c


def test_mini_lowercase_and_unknown():
    assert get_mini_glyph('h') == get_mini_glyph('H')
    g = get_mini_glyph('@')
    assert len(g) == MINI_HEIGHT


def test_mini_renders_pixels():
    from contribution_art.renderer import render_mini, count_active_pixels
    assert count_active_pixels(render_mini('HELLO')) > 0
    assert count_active_pixels(render_mini(' ')) == 0


def test_mini_glyphs_unique():
    # 2 rows leave no room for lookalikes: every glyph must differ.
    seen = {}
    for c, g in MINI.items():
        key = tuple(g)
        assert key not in seen, '%r collides with %r' % (c, seen.get(key))
        seen[key] = c
