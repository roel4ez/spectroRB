# spectro-rb-sync

Sync [Spectro](https://spectro.app) audio-quality verdicts into Rekordbox track colours —
as a native macOS app or from the command line.

It only ever writes `DjmdContent.ColorID`. Ratings, cues, beat grids, comments, tags and
playlists are never touched.

```
$ spectro-rb sync "Spectro Batch.csv" --dry-run

Rekordbox database: /Users/you/Library/Pioneer/rekordbox/master.db
 4,273 tracks found

Spectro results:
 🟢 LOSSLESS 65
 🟡 MEDIUM 2,519
 🔴 FAKE 272

Would update Rekordbox...
 4,273 tracks checked
 2,853 colors changed
 259 of those already had a different colour

Dry run — nothing was written.
```

## Safety model

| Guarantee | How |
| --- | --- |
| Never runs while Rekordbox is open | Process check before reading *and* again immediately before writing |
| Always backed up | Timestamped copy of `master.db` (plus `-wal`/`-shm`) into `~/Library/Application Support/spectro-rb-sync/backups/` before any write |
| Colour only | The engine assigns exactly one field, `ColorID`; nothing else is ever set |
| Preview first | `--dry-run` (CLI) and **Dry run** (app) analyse and report without opening a write transaction |
| No silent mismatches | Fuzzy matches are dropped when a filename is ambiguous, and reported as unmatched |
| Rekordbox can't sneak in | The check runs when you press Sync, not when the app opens, and the core re-checks again before writing |

## Colour mapping

| Spectro verdict | Rekordbox colour |
| --- | --- |
| 🟢 `LOSSLESS` | Green |
| 🟡 `MEDIUM` | Yellow |
| 🔴 `FAKE` | Red |

Tracks with no row in the CSV are left completely untouched.

### Existing colours

By default a Spectro verdict wins over whatever colour a track already had. Turn off
**Overwrite existing colours** in the app (or pass `--keep-existing-colors`) to only colour
tracks that have no colour yet — useful if you already use colours for something else.
Either way, tracks that already carry the right colour are reported as *already correct*,
not as kept.

## Files the CSV has but Rekordbox doesn't

They are never guessed at. They're counted in the summary, listed under **Not found in Rekordbox**
in the app (exportable to CSV), printed by `--show N`, and written in full by `--report PATH`.
Same for filenames too ambiguous to match safely.

## Matching

CSV rows are matched to collection entries in three passes, stopping at the first hit:

1. Exact path (normalised: `file://` URLs decoded, `~` expanded, unicode normalised to NFC —
   macOS mixes NFC and NFD in filenames)
2. Case-insensitive path
3. Unique filename — only when the name is unique on *both* sides

If several CSV rows resolve to the same track, the worst verdict wins.

## The macOS app

```bash
./scripts/build_app.sh
open dist/SpectroRB.app
```

The build downloads a standalone CPython, installs the core into it and embeds the whole
runtime inside `SpectroRB.app`, so the app has no system Python dependency. The Swift UI
talks to the core over a newline-delimited JSON event stream (`spectro-rb sync --json`).

The app auto-detects the Rekordbox database, shows a live "Rekordbox open/closed" badge,
disables **Sync** while Rekordbox is running, and lists every planned colour change.

## The CLI

```bash
python3 -m venv .venv && .venv/bin/pip install -e .

.venv/bin/spectro-rb doctor                       # detected db, rekordbox state, backups
.venv/bin/spectro-rb sync export.csv --dry-run    # preview
.venv/bin/spectro-rb sync export.csv --show 20    # apply, print first 20 changes
.venv/bin/spectro-rb sync export.csv --json       # machine-readable event stream
```

| Flag | Meaning |
| --- | --- |
| `--db PATH` | Use a specific `master.db` instead of auto-detection |
| `--dry-run`, `-n` | Analyse only; write nothing |
| `--no-backup` | Skip the backup (not recommended) |
| `--keep-existing-colors` | Leave tracks that already have a colour untouched |
| `--json` | Newline-delimited JSON events on stdout |
| `--show N` | Print the first N planned changes, and the files Rekordbox doesn't have |
| `--report PATH` | Write every unmatched / ambiguous / unreadable CSV row to a CSV file |

Exit codes: `2` bad CSV, `3` no database found, `4` Rekordbox is running, `5` database error.

## Database detection

Rekordbox 6 and 7 databases are SQLCipher-encrypted. The app asks Rekordbox's own settings
(via `pyrekordbox`) first, then falls back to scanning `~/Library/Pioneer/rekordbox{,6,7}`,
and picks the most recently modified valid database. If the decryption key is missing:

```bash
python -m pyrekordbox download-key
```

## Restoring a backup

Quit Rekordbox, then copy the files from the timestamped folder back over
`~/Library/Pioneer/rekordbox/`.

## Tests

```bash
.venv/bin/pip install pytest && .venv/bin/pytest
```

`samples/` holds a real CSV export and library dump and is deliberately git-ignored.
