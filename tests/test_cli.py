import pytest

from commit_art import parse_args, build_plan, run_interactive


def test_blank_input_refused_cleanly():
    with pytest.raises(SystemExit):
        build_plan(parse_args([' ', '--dry-run']))


def test_blank_lines_refused_cleanly():
    with pytest.raises(SystemExit):
        build_plan(parse_args(['--line1', '   ', '--dry-run']))


def test_bad_spacing_rejected():
    with pytest.raises(SystemExit):
        build_plan(parse_args(['HI', '--spacing', '-1']))


def test_bad_max_weeks_rejected():
    with pytest.raises(SystemExit):
        build_plan(parse_args(['HI', '--max-weeks', '0']))


def test_bad_cpp_rejected():
    with pytest.raises(SystemExit):
        build_plan(parse_args(['HI', '--commits-per-pixel', '99']))


def test_missing_text_errors():
    with pytest.raises(SystemExit):
        build_plan(parse_args(['--preview']))


def test_non_sunday_start_errors():
    args = parse_args(['HI', '--start', '2026-09-09'])  # Wednesday
    with pytest.raises(ValueError):
        build_plan(args)


def test_manual_stacked_plan():
    ctx = build_plan(parse_args(['--line1', 'HELLO', '--line2', 'WORLD']))
    assert ctx['plan']['mode'] == 'stacked'
    assert len(ctx['starts']) == 1  # one shared week range
    assert len(ctx['grids']) == 1 and len(ctx['grids'][0]) == 7
    assert len(ctx['uniq_dates']) > 0


def test_interactive_quits_on_q(monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda *a: 'q')
    assert run_interactive(parse_args(['--no-color'])) == 0


def test_interactive_eof_quits(monkeypatch, capsys):
    def _boom(*a):
        raise EOFError
    monkeypatch.setattr('builtins.input', _boom)
    assert run_interactive(parse_args(['--no-color'])) == 0


def test_interactive_preview_then_quit(monkeypatch, capsys):
    answers = iter(['HI', 'q'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    assert run_interactive(parse_args(['--no-color'])) == 0
    out = capsys.readouterr().out
    assert 'CONTRIBUTION ART PREVIEW' in out


def test_interactive_toggle_and_setting_cycle(monkeypatch, capsys):
    answers = iter(['HI', 'w', 'c', '5', 'q'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    assert run_interactive(parse_args(['--no-color'])) == 0
    out = capsys.readouterr().out
    assert 'auto-wrap ON' in out
    assert 'settings: commits/pixel=5' in out


def test_interactive_unknown_choice_pauses_then_quits(monkeypatch, capsys):
    answers = iter(['HI', 'zzz', '', 'q'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    assert run_interactive(parse_args(['--no-color'])) == 0
    assert 'unknown choice' in capsys.readouterr().out


def test_interactive_view_toggle(monkeypatch, capsys):
    answers = iter(['HI', 'g', 'q'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    assert run_interactive(parse_args(['--no-color'])) == 0
    out = capsys.readouterr().out
    assert 'view: github' in out
    assert 'Less' in out  # github view rendered after toggle


def test_interactive_two_line_mode(monkeypatch, capsys):
    answers = iter(['HI', '2', 'AAA', 'BBB', 'q'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    assert run_interactive(parse_args(['--no-color'])) == 0
    out = capsys.readouterr().out
    assert 'STACKED' in out
    assert 'AAA BBB' in out  # combined label proves both lines are live


def test_interactive_new_text_resets_two_line(monkeypatch, capsys):
    # Regression: two-line state must not stick across new texts.
    answers = iter(['HELLO', 'q'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    args = parse_args(['--no-color', '--line1', 'AA', '--line2', 'BB'])
    assert run_interactive(args) == 0
    out = capsys.readouterr().out
    assert 'SINGLE LINE' in out
    assert 'STACKED' not in out


def test_interactive_two_line_back_to_single(monkeypatch, capsys):
    answers = iter(['HI', '2', 'AAA', 'BBB', '2', '', 'q'])
    monkeypatch.setattr('builtins.input', lambda *a: next(answers))
    assert run_interactive(parse_args(['--no-color'])) == 0
    out = capsys.readouterr().out
    assert 'SINGLE LINE' in out  # blank line 1 exits two-line mode


def test_arrow_menu_select_first(monkeypatch, capsys):
    import commit_art
    from commit_art import _arrow_menu, build_plan
    args = parse_args(['HI', '--no-color'])
    ctx = build_plan(args)
    monkeypatch.setattr(commit_art, 'read_key', lambda: 'enter')
    assert _arrow_menu(ctx, args, 3, False, 'auto', 'blocks', False) == 'new'


def test_arrow_menu_up_wraps_to_quit(monkeypatch, capsys):
    import commit_art
    from commit_art import _arrow_menu, build_plan
    args = parse_args(['HI', '--no-color'])
    ctx = build_plan(args)
    keys = iter(['up', 'enter'])
    monkeypatch.setattr(commit_art, 'read_key', lambda: next(keys))
    assert _arrow_menu(ctx, args, 3, False, 'auto', 'blocks', False) == 'quit'


def test_arrow_menu_letter_shortcut(monkeypatch, capsys):
    import commit_art
    from commit_art import _arrow_menu, build_plan
    args = parse_args(['HI', '--no-color'])
    ctx = build_plan(args)
    keys = iter(['z', 'g'])  # unknown ignored, then G = view toggle
    monkeypatch.setattr(commit_art, 'read_key', lambda: next(keys))
    assert _arrow_menu(ctx, args, 3, False, 'auto', 'blocks', False) == 'view'
