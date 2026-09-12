"""Backup backend: export plans (JSON) and zip/restore generated repos.

Stdlib only (json, zipfile, datetime). All paths stay local — no network.
Backups live in <project>/backups/ by default.
"""

import json
import zipfile
from datetime import datetime
from pathlib import Path

BACKUP_DIRNAME = 'backups'


def default_backup_dir(project_root=None):
    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
    d = root / BACKUP_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_plan(ctx, args, dest_path):
    """Write the current plan + dates to JSON. Returns Path."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    plan = ctx['plan']
    data = {
        'text': ctx['text_label'],
        'mode': plan['mode'],
        'lines': plan['lines'],
        'widths': plan['widths'],
        'pixels_per_line': plan['pixels_per_line'],
        'total_pixels': plan['total_pixels'],
        'estimated_commits': plan['estimated_commits'],
        'fits': plan['fits'],
        'usage_percent': plan['usage_percent'],
        'commits_per_pixel': getattr(args, 'commits_per_pixel', 3),
        'spacing': getattr(args, 'spacing', 1),
        'max_weeks': getattr(args, 'max_weeks', 52),
        'starts': [s.isoformat() for s in ctx['starts']],
        'dates': [d.isoformat() for d in ctx['uniq_dates']],
        'exported_at': datetime.now().isoformat(timespec='seconds'),
    }
    dest.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return dest


def backup_repos(output_dir, backup_dir=None, stamp=None):
    """Zip all generated repos in output_dir. Returns zip Path.

    Raises FileNotFoundError if output_dir has no repos to back up.
    """
    output_dir = Path(output_dir)
    repos = sorted(p for p in output_dir.iterdir() if p.is_dir() and (p / '.git').exists()) \
        if output_dir.exists() else []
    if not repos:
        raise FileNotFoundError('nothing to back up in %s' % output_dir)
    bdir = Path(backup_dir) if backup_dir else default_backup_dir()
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or datetime.now().strftime('%Y%m%d-%H%M%S')
    dest = bdir / ('commit-art-backup-%s.zip' % stamp)
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for repo in repos:
            for f in sorted(repo.rglob('*')):
                # Skip .git internals? No — include them so restore keeps history.
                # But skip nothing; zip everything (repos are small in tests).
                if f.is_file():
                    z.write(f, f.relative_to(output_dir))
    return dest


def list_backups(backup_dir=None):
    """Return sorted list of backup zips (newest last)."""
    bdir = Path(backup_dir) if backup_dir else default_backup_dir()
    if not bdir.exists():
        return []
    return sorted(bdir.glob('commit-art-backup-*.zip'))


def restore_backup(zip_path, output_dir):
    """Extract a backup zip into output_dir. Returns list of restored names."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        bad = [n for n in z.namelist() if n.startswith('/') or '..' in n]
        if bad:
            raise ValueError('unsafe paths in backup: %s' % bad[:3])
        z.extractall(output_dir)
        return sorted({n.split('/')[0] for n in z.namelist() if '/' in n})
