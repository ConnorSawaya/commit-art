# Commit Art — Git Contribution-Calendar Artwork (local-only)

Draw words on a GitHub-style contribution calendar by generating
correctly back-dated Git commits — entirely on your own machine.
This tool **never pushes, never touches GitHub, and never changes your
global Git config**.

```
┌──────────────────────────┐
│ CONTRIBUTION ART PREVIEW │
├──────────────────────────┤
│ ██      ██  ██████       │
│ ██      ██    ██         │
│ ██      ██    ██         │
│ ██████████    ██         │
│ ██      ██    ██         │
│ ██      ██    ██         │
│ ██      ██  ██████       │
└──────────────────────────┘
```

## How contribution calendars work

GitHub renders ~52–53 columns (weeks) × 7 rows (Sunday–Saturday).
Each cell's shade reflects commit count on that date. This tool maps
each "on" pixel of a 5×7 font to a calendar date
(`date = start_sunday + week*7 + weekday`) and creates that many Git
commits with explicit `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE`, then
verifies the history with `git log` itself.

> Honesty note: back-dated art shows *when commits claim to be*, not real
> work done — don't use generated activity to misrepresent project
> participation or work history.

## Publishing to GitHub (opt-in)

```bash
python commit_art.py "HELLO" --publish --repo my-art
```

1. Uses your existing `gh` login (`gh auth login` first) — no tokens
   handled here. Commits are authored as your account (name + primary
   or noreply email) so squares attribute to you.
2. Creates a **private** repo by default (`--public` to change that),
   builds the commits fresh, verifies them locally, then asks you to
   **type the repo name to confirm** (`--yes` skips the prompt).
3. Pushes once to `main` and prints the URL.

Private repos only shade your graph if "Private contributions" is
enabled in GitHub profile settings. Honesty note still applies:
back-dated art shows *when commits claim to be*, not real work done —
don't use it to misrepresent your history.

## Installation

Requires Python 3.10+ and `git`. No third-party runtime dependencies.

```bash
pip install -r requirements.txt   # pytest only, for the test suite
```

## Interactive mode

```bash
python commit_art.py --interactive   # or -i
```

Full-screen TUI: artwork on top, menu below. In a real terminal use
**Up/Down + Enter** (letter shortcuts also work); when piped, plain
letter/Enter input is used instead. The screen fully redraws on every
action. Menu: new text, build + verify (`T`), dry-run (`D`), brightness
(`C`), auto-wrap (`W`), start date (`S`), two-line mode (`2`), view
toggle (`G`), backup (`B`), quit (`Q`). Typing new text always resets to
single-line mode; blank line 1 in the `2` dialog exits two-line mode.

## Full-screen TUI (optional)

```bash
pip install textual
python commit_art.py --tui
```

A real Textual app (terminals can't render HTML/CSS/JS — that's
browser-only tech — so this uses a terminal-UI framework instead):
artwork panel on the **left**, stats + settings + action buttons on the
**right**, scrolling log at the **bottom**, everything visible at once.
Type and the art re-renders live; `Build+Verify` runs the real commit
backend in a worker thread with milestone lines in the log and prints
PASS/FAIL there too. Keys: type in the fields, `Esc` to unfocus, then `t`/`d`/`g`/`b`
shortcuts work (`q` quits). Small terminals scroll each panel.

Colors, banner, and progress bar show in a real terminal (auto-disabled
when piped or with `NO_COLOR=1` / `--no-color`). Key lines
(`RESULT: PASS`, `DRY RUN COMPLETE`, …) stay plain-text greppable.

## Usage

```bash
python commit_art.py "HELLO" --preview        # boxed preview, zero commits
python commit_art.py "HELLO" --preview --view github  # GitHub-calendar look
python commit_art.py "HELLO" --dry-run        # full plan + every date, zero commits
python commit_art.py "HELLO" --local-test     # disposable repo in ./test-output/HELLO/
python commit_art.py "HELLO" --local-test --backup    # + zip repos into backups/
python commit_art.py --list-backups           # list backup zips
python commit_art.py --restore backups/<file>.zip     # restore into test-output/
python commit_art.py "HELLO" --dry-run --export-plan backups/HELLO-plan.json
python commit_art.py "LONG PHRASE" --auto-wrap --dry-run
python commit_art.py --line1 "HELLO" --line2 "WORLD" --local-test
python commit_art.py "HELLO" --start 2026-01-04 --local-test   # must be a Sunday
python commit_art.py "HELLO" --commits-per-pixel 5 --dry-run
python commit_art.py --help
```

## Examples (real output)

![Contribution-graph art mockup](docs/contribution-preview.png)

Single line:

```text
$ python commit_art.py "HELLO" --preview
Text: HELLO
Width: 29 weeks
Available: 52 weeks
Usage: 55.8%
Active pixels: 73
Commits/pixel: 3
Estimated commits: 219
Layout: SINGLE LINE
```

Two stacked lines, GitHub-calendar view (`--line1 HI --line2 YO
--preview --view github`) — top band and bottom band share the same
weeks; Wednesday stays empty (gap row):

```text
    JuAu        Se
    ▒▒ ·· ▒▒ ·· ▒▒ ▒▒ ▒▒
Mon ▒▒ ▒▒ ▒▒ ·· ·· ▒▒ ··
    ▒▒ ·· ▒▒ ·· ▒▒ ▒▒ ▒▒
Wed ·· ·· ·· ·· ·· ·· ··
    ▒▒ ·· ▒▒ ·· ·· ▒▒ ··
Fri ·· ▒▒ ·· ·· ▒▒ ·· ▒▒
    ·· ▒▒ ·· ·· ·· ▒▒ ··

Less ░░ ▒▒ ▓▓ ██ More  (3 commits/pixel)
```

Local test verdict (`--local-test` builds a disposable repo and checks
it with git itself):

```text
Wrote 28 commits.
PASS
  log_parseable: ok
  commit_count_match: ok
  all_dates_present: ok
  no_unexpected_dates: ok
  author_dates_match: ok
  committer_dates_match: ok
  no_future_dates: ok
RESULT: PASS
```

## How automatic wrapping works

A 5-wide font with 1-column spacing needs ~6 week-columns per character,
so 52 weeks fit ~8 characters per line. If text doesn't fit and
`--auto-wrap` is given, the layout engine tries every word-boundary split
and picks one where both lines fit with the most balanced widths — never
splitting mid-word unless a single word is too long.

## How two-line (stacked) mode works

One line uses the full 7-row font. Two lines (`--line1/--line2` or
`--auto-wrap`) switch to a compact 3-row font and stack for real: line 1
on rows 0–2, one gap row, line 2 on rows 4–6 — 3+1+3 fills all 7 rows,
both lines in the **same** week columns, one date range, one calendar.
Three rows cannot render every letter distinctly, so the glyphs are
best-effort blocky (uniqueness is enforced by test) — but letters sit
truly on top of each other.

## How estimates are calculated

- `pixel width` = rendered columns (chars + spacing); 1 column = 1 week
- `active pixels` = filled cells; `estimated commits` = pixels × commits-per-pixel
- `usage %` = widest line ÷ `--max-weeks` × 100
- `fits` = every line ≤ `--max-weeks` (advisory; `--local-test` still works,
  the art just spans more than one on-screen year)

## How dates work

- Default `--start auto` ends art on the last **fully past** week, so no
  future commits are ever created (even on Fridays).
- Explicit `--start` must be a Sunday; ranges ending after today are rejected.
- Pure `datetime.date` arithmetic → leap years and year boundaries just work.
- Every date function takes an explicit `today` parameter → deterministic tests.

## Brightness / intensity

`--commits-per-pixel 1..10` (default 3). `renderer.INTENSITY_COMMITS`
maps levels `{1:1, 2:3, 3:6, 4:10}` for multi-level art; binary mode is default.

## Safety

- No `push`, no remotes, no GitHub API, no `--global` config — `run_git`
  raises on any push attempt.
- Disposable repos under `./test-output/` use the fake identity
  `Contribution Art Test <contribution-art-test@example.invalid>`.
- Every `--local-test` re-verifies count, dates, author/committer stamps,
  and future-date absence, printing PASS/FAIL.

## Backend: real commits + backups

- **Real commits**: `--local-test` actually runs `git init / add / commit`
  per pixel with explicit `GIT_AUTHOR_DATE` + `GIT_COMMITTER_DATE`, then
  inspects the history via `git log` — not a mock frontend.
- **Backups**: `--local-test --backup` zips `test-output/` (including
  `.git` history) into `backups/commit-art-backup-<stamp>.zip`;
  `--list-backups` / `--restore <zip>` manage them. Interactive mode's
  `B` menu exports the current plan (JSON), zips repos, or lists backups.
- **Two views**: `--view blocks` (default) or `--view github` — the GitHub
  view shows week columns with month headers, Mon/Wed/Fri row labels,
  intensity shading (`░░▒▒▓▓██`) scaled by commits-per-pixel, and a
  Less→More legend. Toggle live with `G` in interactive mode.

## Project structure

```text
commit-art/
├── commit_art.py          # CLI: preview / dry-run / local-test / publish
├── tui.py                 # full-screen Textual app (optional, --tui)
├── contribution_art/
│   ├── font.py            # 7-row font + 3-row stacked font (easy to extend)
│   ├── renderer.py        # grids, Unicode + GitHub-calendar rendering
│   ├── layout.py          # measuring, auto-wrap, single/stacked planning
│   ├── dates.py           # Sunday-anchored, never-future date math
│   ├── git_writer.py      # local-only commits (push raises here)
│   ├── verifier.py        # inspects git log, prints PASS/FAIL
│   ├── publish.py         # opt-in --publish via `gh` CLI (sole push path)
│   ├── backup.py          # plan export + repo zip/restore
│   ├── cli_ui.py          # colors, banners, progress (stdlib ANSI)
│   ├── keys.py            # arrow-key reading (msvcrt/termios)
│   └── tui_text.py        # panel text builders for the TUI
├── tests/                 # pytest suite (stdlib + pytest only)
├── .github/workflows/ci.yml
├── README.md
└── requirements.txt
```

## Limitations

- Very long phrases can overflow one screen-year; stacked mode reports
  DOES NOT FIT honestly instead of pretending.
- Stacked glyphs are blocky (3 rows can't match 7-row detail).
- Shades depend on the viewer's theme; commit counts only approximate color.
- `--publish` pushes fabricated history to your own repo — it shows when
  commits claim to be, not real work; don't misrepresent it.
