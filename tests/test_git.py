import shutil
from datetime import date
from pathlib import Path

import pytest

git = shutil.which('git')
needs_git = pytest.mark.skipif(git is None, reason='git not installed')

from contribution_art import git_writer
from contribution_art.git_writer import (
    init_repo, write_art, get_log, ART_FILE,
    TEST_USER_NAME, TEST_USER_EMAIL,
)
from contribution_art.renderer import render_text
from contribution_art.dates import resolve_start_single, grid_to_dates
from contribution_art.verifier import verify_repo


@needs_git
def test_init_repo_local_identity(tmp_path):
    repo = init_repo(tmp_path / 'r')
    assert (repo / '.git').exists()
    out = git_writer.run_git(['config', 'user.email'], repo)
    assert out.stdout.strip() == TEST_USER_EMAIL
    out = git_writer.run_git(['config', 'user.name'], repo)
    assert out.stdout.strip() == TEST_USER_NAME


@needs_git
def test_write_art_commit_count_and_file(tmp_path):
    repo = init_repo(tmp_path / 'r')
    grid = render_text('HI')
    start = resolve_start_single(len(grid[0]), today=date(2026, 9, 11))
    dated = grid_to_dates(grid, start)
    stats = write_art(repo, dated, 'HI', commits_per_pixel=1)
    assert stats['commit_count'] == len(dated)
    assert (repo / ART_FILE).exists()
    assert len(get_log(repo)) == len(dated)


@needs_git
def test_author_and_committer_timestamps(tmp_path):
    repo = init_repo(tmp_path / 'r')
    grid = render_text('HI')
    start = resolve_start_single(len(grid[0]), today=date(2026, 9, 11))
    dated = grid_to_dates(grid, start)
    write_art(repo, dated, 'HI', commits_per_pixel=2)
    expected = sorted({d for (_, _, d) in dated})
    report = verify_repo(repo, expected, len(dated) * 2, today=date(2026, 9, 11))
    assert report['ok'] is True, report
    assert report['checks']['author_dates_match'] is True
    assert report['checks']['committer_dates_match'] is True
    assert report['checks']['no_future_dates'] is True


@needs_git
def test_verifier_catches_wrong_count(tmp_path):
    repo = init_repo(tmp_path / 'r')
    grid = render_text('HI')
    start = resolve_start_single(len(grid[0]), today=date(2026, 9, 11))
    dated = grid_to_dates(grid, start)
    write_art(repo, dated, 'HI', commits_per_pixel=1)
    expected = sorted({d for (_, _, d) in dated})
    bad = verify_repo(repo, expected, 9999, today=date(2026, 9, 11))
    assert bad['ok'] is False


def test_never_calls_push():
    src = Path(git_writer.__file__).read_text(encoding='utf-8')
    # No push invocation anywhere except the safety guard/message lines.
    lines = [l for l in src.split('\n')
             if 'push' in l.lower() and 'forbidden' not in l.lower()
             and 'never push' not in l.lower() and 'allowed' not in l.lower()
             and 'never pushes' not in l.lower() and 'lower()' not in l]
    assert lines == [], lines
    # run_git actively blocks push
    with pytest.raises(RuntimeError):
        git_writer.run_git(['push'], '.')
