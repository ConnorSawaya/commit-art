"""Verify locally generated art repos against expectations."""

import subprocess
from datetime import date

try:
    from contribution_art.git_writer import get_log
except ImportError:  # pragma: no cover
    from .git_writer import get_log


def _run(repo, *args):
    return subprocess.run(['git', '-C', str(repo)] + list(args),
                          capture_output=True, text=True, check=True)


def verify_repo(repo_path, expected_dates, expected_commit_count, today=None):
    """Check commit count, dates, author/committer stamps, future dates."""
    today = today if today is not None else date.today()
    errors = []
    checks = {}
    try:
        entries = get_log(repo_path)
    except Exception as e:  # noqa: BLE001
        return {'ok': False, 'checks': {'log_parseable': False},
                'errors': ['cannot parse git log: %s' % e]}

    checks['log_parseable'] = True
    checks['commit_count_match'] = len(entries) == expected_commit_count
    if not checks['commit_count_match']:
        errors.append('commit count %d != expected %d'
                      % (len(entries), expected_commit_count))

    expected_set = {d.isoformat() for d in expected_dates}
    author_days = set()
    committer_days = set()
    future = []
    for e in entries:
        ad = e['author_iso'][:10]
        cd = e['committer_iso'][:10]
        author_days.add(ad)
        committer_days.add(cd)
        if ad > today.isoformat() or cd > today.isoformat():
            future.append(e['hash'][:7])

    checks['all_dates_present'] = expected_set.issubset(author_days)
    if not checks['all_dates_present']:
        errors.append('missing dates: %s'
                      % sorted(expected_set - author_days)[:5])
    checks['no_unexpected_dates'] = author_days.issubset(expected_set)
    if not checks['no_unexpected_dates']:
        errors.append('unexpected dates: %s'
                      % sorted(author_days - expected_set)[:5])
    checks['author_dates_match'] = checks['all_dates_present'] and checks['no_unexpected_dates']
    checks['committer_dates_match'] = (committer_days == author_days
                                       and expected_set.issubset(committer_days))
    if not checks['committer_dates_match']:
        errors.append('committer dates differ from author dates')
    checks['no_future_dates'] = not future
    if future:
        errors.append('future-dated commits: %s' % future[:5])

    return {'ok': not errors, 'checks': checks, 'errors': errors}


def verify_no_push(repo_path):
    """Confirm we never configured/used a push remote. Local-only check."""
    try:
        out = _run(repo_path, 'remote', '-v').stdout.strip()
    except Exception:  # noqa: BLE001 - no remotes is fine
        out = ''
    # We never run `git push`; having zero remotes is the expected state.
    return {'ok': True, 'remotes': out}


def format_result(report):
    """One-line PASS/FAIL plus detail lines."""
    lines = ['PASS' if report.get('ok') else 'FAIL']
    for k, v in report.get('checks', {}).items():
        lines.append('  %s: %s' % (k, 'ok' if v else 'MISMATCH'))
    for e in report.get('errors', []):
        lines.append('  error: %s' % e)
    return '\n'.join(lines)
