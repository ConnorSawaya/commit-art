"""Publish tests. All GitHub interaction is mocked — these tests must
never touch the network or the real `gh` account."""

import subprocess
import types

import pytest

import commit_art
from commit_art import parse_args, build_plan, cmd_publish
from contribution_art import publish
from contribution_art.publish import (
    gh_logged_in, gh_user, gh_primary_email, create_repo, push_repo,
)


def _cp(stdout='', stderr=''):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)


def test_gh_logged_in_true(monkeypatch):
    monkeypatch.setattr(publish, '_run_gh',
                        lambda a: _cp(stdout='x', stderr='Logged in to github.com as u'))
    assert gh_logged_in() is True


def test_gh_logged_in_false(monkeypatch):
    def _boom(a):
        raise subprocess.CalledProcessError(1, 'gh')
    monkeypatch.setattr(publish, '_run_gh', _boom)
    assert gh_logged_in() is False


def test_gh_user_parses_and_falls_back(monkeypatch):
    monkeypatch.setattr(publish, '_run_gh',
                        lambda a: _cp(stdout='{"login": "octo", "name": null}'))
    assert gh_user() == {'login': 'octo', 'name': 'octo'}


def test_gh_primary_email_strips_quotes(monkeypatch):
    monkeypatch.setattr(publish, '_run_gh', lambda a: _cp(stdout='"octo@users.noreply.github.com"\n'))
    assert gh_primary_email() == 'octo@users.noreply.github.com'


def test_gh_primary_email_noreply_fallback(monkeypatch):
    import json

    def _fake(args):
        if 'user/emails' in args:
            raise subprocess.CalledProcessError(1, 'gh')
        return _cp(stdout=json.dumps({'id': 123, 'login': 'octo'}))

    monkeypatch.setattr(publish, '_run_gh', _fake)
    assert gh_primary_email() == '123+octo@users.noreply.github.com'


def test_create_repo_aborts_when_taken(monkeypatch):
    monkeypatch.setattr(publish, 'gh_user', lambda: {'login': 'u', 'name': 'U'})
    monkeypatch.setattr(publish, 'repo_exists', lambda full: True)
    with pytest.raises(RuntimeError):
        create_repo('taken')


def test_create_repo_private_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(publish, 'gh_user', lambda: {'login': 'u', 'name': 'U'})
    monkeypatch.setattr(publish, 'repo_exists', lambda full: False)
    monkeypatch.setattr(publish, '_run_gh', lambda a: calls.append(a) or _cp())
    assert create_repo('art', private=True) == 'u/art'
    assert '--private' in calls[0]
    calls.clear()
    create_repo('art2', private=False)
    assert '--public' in calls[0]


def test_push_repo_sequence(monkeypatch, tmp_path):
    calls = []
    fake_remote = {'out': ''}

    def _fake(args, cwd):
        calls.append(list(args))
        if args[0] == 'remote' and len(args) == 1:
            return _cp(stdout=fake_remote['out'])
        return _cp()

    monkeypatch.setattr(publish, '_run_git', _fake)
    url = push_repo(tmp_path, 'u/art')
    assert url == 'https://github.com/u/art'
    assert calls[0][:2] == ['branch', '-M']
    assert calls[1] == ['remote']
    assert calls[2][:3] == ['remote', 'add', 'origin']
    assert calls[3][:2] == ['push', '-u']


def test_cmd_publish_aborts_when_logged_out(monkeypatch, capsys):
    monkeypatch.setattr(commit_art, 'gh_logged_in', lambda: False)
    ctx = build_plan(parse_args(['HI', '--no-color']))
    assert cmd_publish(ctx, parse_args(['HI', '--publish', '--no-color'])) is False


def test_cmd_publish_aborts_on_wrong_confirm(monkeypatch):
    monkeypatch.setattr(commit_art, 'gh_logged_in', lambda: True)
    monkeypatch.setattr(commit_art, 'gh_user', lambda: {'login': 'u', 'name': 'U'})
    monkeypatch.setattr(commit_art, 'gh_primary_email', lambda: 'u@e')
    created = []
    monkeypatch.setattr(commit_art, 'create_repo',
                        lambda *a, **k: created.append(1) or 'u/x')
    monkeypatch.setattr('builtins.input', lambda *a: 'wrong-name')
    ctx = build_plan(parse_args(['HI', '--no-color']))
    args = parse_args(['HI', '--publish', '--repo', 'x', '--no-color'])
    assert cmd_publish(ctx, args) is False
    assert created == []


def test_cmd_publish_success_yes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(commit_art, 'gh_logged_in', lambda: True)
    monkeypatch.setattr(commit_art, 'gh_user', lambda: {'login': 'u', 'name': 'U'})
    monkeypatch.setattr(commit_art, 'gh_primary_email', lambda: 'u@e')
    monkeypatch.setattr(commit_art, 'create_repo', lambda *a, **k: 'u/x')
    monkeypatch.setattr(commit_art, 'push_repo',
                        lambda repo, full, branch='main': 'https://github.com/u/x')
    ctx = build_plan(parse_args(['HI', '--no-color']))
    args = parse_args(['HI', '--publish', '--yes', '--repo', 'x',
                       '--commits-per-pixel', '1', '--no-color',
                       '--output', str(tmp_path)])
    # Same args must drive plan + publish (as main() does).
    ctx = build_plan(args)
    assert cmd_publish(ctx, args) is True
    out = capsys.readouterr().out
    assert 'https://github.com/u/x' in out
    # Real local commits used the GitHub identity, not the test identity.
    log = (tmp_path / 'HI-pub' / 'contribution-art.log')
    assert log.exists()


def test_init_repo_custom_identity(tmp_path):
    from contribution_art.git_writer import init_repo, run_git
    repo = init_repo(tmp_path / 'r', user_name='Octo', user_email='o@gh')
    assert run_git(['config', 'user.email'], repo).stdout.strip() == 'o@gh'
    assert run_git(['config', 'user.name'], repo).stdout.strip() == 'Octo'
