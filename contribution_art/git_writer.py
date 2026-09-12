"""Create local-only Git histories for contribution art.

SAFETY: this module never pushes, never creates GitHub repos, never
touches global git config, never accesses the network. It only runs
`git init / config (local) / add / commit / log` inside a disposable
directory passed in by the caller.
"""

import os
import subprocess
from pathlib import Path

TEST_USER_NAME = 'Contribution Art Test'
TEST_USER_EMAIL = 'contribution-art-test@example.invalid'
ART_FILE = 'contribution-art.log'


def run_git(args, cwd, env=None):
    """Run a git command inside cwd. No push commands are allowed."""
    for a in args:
        if str(a).lower() == 'push':
            raise RuntimeError('git push is forbidden in local-test mode')
    return subprocess.run(
        ['git'] + list(args), cwd=str(cwd), env=env,
        capture_output=True, text=True, check=True)


def init_repo(path, user_name=TEST_USER_NAME, user_email=TEST_USER_EMAIL):
    """Create dir, git init, set LOCAL-ONLY identity. Return Path.

    Published repos pass the GitHub account's own name/email so the
    squares attribute; test repos use the fake test identity default.
    Identity is always repo-local (never --global).
    """
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    try:
        run_git(['init'], repo)
    except subprocess.CalledProcessError:
        run_git(['init', '.'], repo)
    # Local-only identity (never --global).
    run_git(['config', 'user.name', user_name], repo)
    run_git(['config', 'user.email', user_email], repo)
    run_git(['config', 'commit.gpgsign', 'false'], repo)
    return repo


def _commit_env(day, user_name=TEST_USER_NAME, user_email=TEST_USER_EMAIL):
    """Environment with explicit author+committer timestamps for `day`."""
    stamp = '%sT12:00:00' % day.isoformat()
    env = dict(os.environ)
    env['GIT_AUTHOR_DATE'] = stamp
    env['GIT_COMMITTER_DATE'] = stamp
    env['GIT_AUTHOR_NAME'] = user_name
    env['GIT_AUTHOR_EMAIL'] = user_email
    env['GIT_COMMITTER_NAME'] = user_name
    env['GIT_COMMITTER_EMAIL'] = user_email
    return env


def commit_for_date(repo, day, message, line_no=0,
                    user_name=TEST_USER_NAME, user_email=TEST_USER_EMAIL):
    """Append one line to ART_FILE and commit it dated `day`. Return hash."""
    repo = Path(repo)
    log = repo / ART_FILE
    with open(log, 'a', encoding='utf-8') as f:
        f.write('%s | %s | line=%s\n' % (message, day.isoformat(), line_no))
    run_git(['add', ART_FILE], repo)
    run_git(['commit', '-m', '%s | %s | #%s' % (message, day.isoformat(), line_no)],
            repo, env=_commit_env(day, user_name, user_email))
    out = run_git(['rev-parse', 'HEAD'], repo)
    return out.stdout.strip()


def write_art(repo_path, dated_pixels, text_label, commits_per_pixel=3,
              intensity_map=None, progress=None,
              user_name=TEST_USER_NAME, user_email=TEST_USER_EMAIL):
    """Write N commits per active pixel, in date order.

    dated_pixels: iterable of (row, col, date). Returns stats dict.
    progress: optional callable(done, total) invoked after each commit.
    """
    repo = Path(repo_path)
    items = sorted(dated_pixels, key=lambda t: t[2])
    total = len(items) * commits_per_pixel
    count = 0
    for (row, col, day) in items:
        n = commits_per_pixel
        if intensity_map and isinstance(n, int):
            pass  # binary grids: uniform count
        for k in range(n):
            count += 1
            commit_for_date(
                repo, day,
                '%s | pixel=(%d,%d) | commit=%d' % (text_label, row, col, k + 1),
                line_no=count, user_name=user_name, user_email=user_email)
            if progress is not None:
                progress(count, total)
    dates = sorted({d for (_, _, d) in items})
    return {
        'commit_count': count,
        'dates_used': dates,
        'first_date': dates[0] if dates else None,
        'last_date': dates[-1] if dates else None,
    }


def get_log(repo):
    """Parse git log -> list of {hash, author_iso, committer_iso, subject}."""
    repo = Path(repo)
    out = run_git(
        ['log', '--pretty=format:%H%x1f%aI%x1f%cI%x1f%s%x1e'], repo)
    entries = []
    for rec in out.stdout.split('\x1e'):
        rec = rec.strip()
        if not rec:
            continue
        parts = rec.split('\x1f')
        if len(parts) != 4:
            continue
        entries.append({'hash': parts[0], 'author_iso': parts[1],
                        'committer_iso': parts[2], 'subject': parts[3]})
    return entries
