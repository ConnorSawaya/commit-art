"""GitHub publish backend (explicit opt-in only).

Nothing here runs unless the user passes --publish AND confirms.
Authentication is delegated entirely to the `gh` CLI (already logged in
as the user) - this module never handles tokens or passwords.

Usage from the CLI:
    python commit_art.py "HELLO" --publish --repo my-art --yes

Attribution: commits are authored with the GitHub account's own name and
primary email so the squares count on the user's graph. (The local-only
test identity is NOT used for published repos.)
"""

import shutil
import subprocess
from pathlib import Path


def _run_gh(args):
    """Run `gh ...`, return CompletedProcess (raises on failure)."""
    if not shutil.which('gh'):
        raise RuntimeError("the `gh` CLI is required: see https://cli.github.com")
    return subprocess.run(['gh'] + list(args), capture_output=True,
                          text=True, check=True)


def _run_git(args, cwd):
    """Plain git runner for publish (push allowed ONLY on this path)."""
    return subprocess.run(['git'] + list(args), cwd=str(cwd),
                          capture_output=True, text=True, check=True)


def gh_logged_in():
    """True if `gh` has an active GitHub account."""
    try:
        out = _run_gh(['auth', 'status'])
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError):
        return False
    return 'Logged in to github.com' in (out.stdout + out.stderr)


def gh_user():
    """Return {'login': ..., 'name': ...} for the active account."""
    out = _run_gh(['api', 'user', '--jq', '{login: .login, name: .name}'])
    import json
    data = json.loads(out.stdout.strip())
    if not data.get('name'):
        data['name'] = data['login']
    return data


def gh_primary_email():
    """Primary email for attribution.

    Prefers the account's primary email; if the token lacks the `user`
    scope (`gh auth refresh -s user` grants it), falls back to GitHub's
    private noreply address <id>+<login>@users.noreply.github.com,
    which still counts toward the contribution graph.
    """
    try:
        out = _run_gh(['api', 'user/emails', '--jq',
                       '[.[] | select(.primary) | .email][0]'])
        email = out.stdout.strip().strip('"')
        if email and email != 'null':
            return email
    except subprocess.CalledProcessError:
        pass
    import json
    out = _run_gh(['api', 'user', '--jq', '{id: .id, login: .login}'])
    data = json.loads(out.stdout.strip())
    return '%s+%s@users.noreply.github.com' % (data['id'], data['login'])


def repo_exists(full_name):
    """True if owner/repo already exists on GitHub."""
    try:
        _run_gh(['repo', 'view', full_name, '--json', 'name'])
    except subprocess.CalledProcessError:
        return False
    return True


def create_repo(name, private=True, description='Contribution-calendar art'):
    """Create an empty GitHub repo. Returns 'owner/name'. Aborts if taken."""
    login = gh_user()['login']
    full = '%s/%s' % (login, name)
    if repo_exists(full):
        raise RuntimeError('repo %s already exists on GitHub' % full)
    visibility = '--private' if private else '--public'
    _run_gh(['repo', 'create', name, visibility,
             '--description', description])
    return full


def push_repo(repo_path, full_name, branch='main'):
    """Rename branch, attach origin, push. Returns the repo URL.

    This is the ONLY sanctioned push path in the whole project, and it
    only runs from the --publish flow after explicit user confirmation.
    """
    repo_path = Path(repo_path)
    _run_git(['branch', '-M', branch], repo_path)
    existing = _run_git(['remote'], repo_path).stdout.split()
    url = 'https://github.com/%s.git' % full_name
    if 'origin' not in existing:
        _run_git(['remote', 'add', 'origin', url], repo_path)
    _run_git(['push', '-u', 'origin', branch], repo_path)
    return 'https://github.com/%s' % full_name
