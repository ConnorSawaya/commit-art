from contribution_art.renderer import (
    render_text, render_mini, render_stacked, text_to_grid,
    grid_width, grid_height,
    count_active_pixels, commits_for_grid, render_preview,
    INTENSITY_COMMITS,
)


def test_grid_is_7_rows():
    g = render_text('HI')
    assert grid_height(g) == 7
    assert grid_width(g) > 0


def test_grid_width_consistent():
    g = render_text('HELLO')
    w = grid_width(g)
    for row in g:
        assert len(row) == w


def test_spacing_increases_width():
    assert grid_width(render_text('HI', spacing=2)) > grid_width(render_text('HI', spacing=1))


def test_space_renders_blank():
    assert count_active_pixels(render_text(' ')) == 0
    assert count_active_pixels(render_text('HI')) > 0


def test_text_to_grid_alias():
    assert text_to_grid('A') == render_text('A')


def test_commits_estimate_math():
    g = render_text('HI')
    px = count_active_pixels(g)
    assert commits_for_grid(g, 1) == px
    assert commits_for_grid(g, 3) == px * 3
    assert commits_for_grid(g, 5) == px * 5


def test_intensity_map():
    assert INTENSITY_COMMITS[1] == 1
    assert INTENSITY_COMMITS[2] == 3
    assert INTENSITY_COMMITS[3] == 6
    assert INTENSITY_COMMITS[4] == 10


def test_preview_shape_and_blocks():
    g = render_text('HI')
    prev = render_preview(g)
    assert len(prev.split('\n')) == 7
    assert '\u2588\u2588' in prev


def test_mini_is_3_rows():
    g = render_mini('HI')
    assert len(g) == 3
    assert grid_width(g) > 0


def test_stacked_top_and_bottom_share_weeks():
    g = render_stacked('HI', 'YO')
    assert grid_height(g) == 7
    assert all(v == 0 for v in g[3])  # the single gap row
    top = count_active_pixels([g[0], g[1], g[2]])
    bottom = count_active_pixels([g[4], g[5], g[6]])
    assert top > 0 and bottom > 0
    # Width fits the wider line (shorter padded, same columns).
    assert grid_width(g) == max(grid_width(render_mini('HI')),
                                grid_width(render_mini('YO')))
