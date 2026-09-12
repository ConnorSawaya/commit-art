import json
from datetime import date

from contribution_art.renderer import (
    render_text, render_github, shade_cell,
)
from contribution_art.backup import (
    export_plan, backup_repos, list_backups, restore_backup,
)
from commit_art import parse_args, build_plan


def test_shade_levels():
    assert shade_cell(1) == '░░'
    assert shade_cell(3) == '▒▒'
    assert shade_cell(6) == '▓▓'
    assert shade_cell(10) == '██'


def test_github_view_has_labels_and_legend():
    grid = render_text('HI')
    out = render_github(grid, date(2026, 1, 4), commits_per_pixel=3)
    assert 'Mon' in out and 'Wed' in out and 'Fri' in out
    assert 'Less' in out and 'More' in out
    assert '3 commits/pixel' in out
    # 7 day rows + header + blank + legend
    assert len(out.split('\n')) == 10


def test_export_plan_json(tmp_path):
    args = parse_args(['HI', '--no-color'])
    ctx = build_plan(args)
    dest = tmp_path / 'hi-plan.json'
    out = export_plan(ctx, args, str(dest))
    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['text'] == 'HI'
    assert data['estimated_commits'] == ctx['plan']['estimated_commits']
    assert len(data['dates']) == len(ctx['uniq_dates'])


def test_backup_and_restore_roundtrip(tmp_path, monkeypatch):
    import contribution_art.backup as bak
    monkeypatch.setattr(bak, 'default_backup_dir', lambda *a: tmp_path / 'backups')
    # fake a generated repo (no .git needed? backup requires .git) — make one
    repo = tmp_path / 'out' / 'HI'
    (repo / '.git').mkdir(parents=True)
    (repo / 'contribution-art.log').write_text('x\n', encoding='utf-8')
    dest = backup_repos(tmp_path / 'out', backup_dir=tmp_path / 'backups',
                        stamp='TEST')
    assert dest.exists()
    assert list_backups(tmp_path / 'backups') == [dest]
    names = restore_backup(str(dest), tmp_path / 'restored')
    assert names == ['HI']
    assert (tmp_path / 'restored' / 'HI' / 'contribution-art.log').exists()


def test_backup_empty_dir_errors(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        backup_repos(tmp_path / 'empty', backup_dir=tmp_path / 'b')


def test_restore_rejects_unsafe_zip(tmp_path):
    import zipfile, pytest
    evil = tmp_path / 'evil.zip'
    with zipfile.ZipFile(evil, 'w') as z:
        z.writestr('../evil.txt', 'x')
    with pytest.raises(ValueError):
        restore_backup(str(evil), tmp_path / 'out')
