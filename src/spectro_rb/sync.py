"""The sync engine: plan colour changes, then optionally apply them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .backup import Backup, backup_database
from .discovery import DatabaseCandidate, resolve_database
from .guard import ensure_rekordbox_closed
from .matching import TrackIndex
from .model import DEFAULT_MAPPING, NO_COLOR, MatchKind, SyncPlan, TrackChange, Verdict
from .rekordbox import RekordboxCollection, open_collection
from .spectro import SpectroExport, read_spectro_csv

Progress = Callable[[str, dict], None]


def _noop(event: str, payload: dict) -> None:  # pragma: no cover - trivial
    return None


@dataclass(slots=True)
class SyncResult:
    plan: SyncPlan
    database: DatabaseCandidate
    csv_path: Path
    dry_run: bool
    applied: int = 0
    backup: Backup | None = None

    def as_dict(self) -> dict:
        return {
            "database": self.database.as_dict(),
            "csv": str(self.csv_path),
            "dry_run": self.dry_run,
            "applied": self.applied,
            "backup": self.backup.as_dict() if self.backup else None,
            "summary": self.plan.summary(),
        }


def build_plan(
    export: SpectroExport,
    collection: RekordboxCollection,
    mapping: dict[Verdict, str] | None = None,
    progress: Progress = _noop,
    overwrite_existing: bool = True,
) -> SyncPlan:
    mapping = mapping or DEFAULT_MAPPING
    tracks = collection.tracks()
    progress("collection_loaded", {"tracks": len(tracks)})

    index = TrackIndex.build(tracks, RekordboxCollection.path_of)
    plan = SyncPlan(
        collection_size=len(tracks),
        csv_rows=len(export.rows),
        verdict_counts=dict(export.verdict_counts),
        skipped_rows=list(export.skipped),
        overwrite_existing=overwrite_existing,
    )

    seen_content: dict[str, TrackChange] = {}
    for row in export.rows:
        track, kind = index.lookup(row.path, row.filename)
        if track is None:
            if kind is MatchKind.AMBIGUOUS:
                plan.ambiguous.append(row)
            else:
                plan.unmatched.append(row)
            continue

        existing = RekordboxCollection.color_of(track)
        target = mapping[row.verdict]
        change = TrackChange(
            content_id=str(track.ID),
            title=track.Title or "",
            artist=(track.Artist.Name if getattr(track, "Artist", None) else "") or "",
            path=RekordboxCollection.path_of(track),
            verdict=row.verdict,
            old_color=existing,
            new_color=target,
            match_kind=kind,
            # Only a real conflict counts as protected: a track that already
            # carries the right colour is "already correct", not "kept".
            protected=(
                not overwrite_existing and existing != NO_COLOR and existing != target
            ),
        )
        # If several CSV rows hit the same track, the worst verdict wins.
        previous = seen_content.get(change.content_id)
        if previous is not None:
            severity = {Verdict.LOSSLESS: 0, Verdict.MEDIUM: 1, Verdict.FAKE: 2}
            if severity[row.verdict] <= severity[previous.verdict]:
                continue
            plan.changes.remove(previous)
        seen_content[change.content_id] = change
        plan.changes.append(change)

    progress("plan_ready", plan.summary())
    return plan


def apply_plan(
    plan: SyncPlan,
    collection: RekordboxCollection,
    progress: Progress = _noop,
) -> int:
    """Write the planned colours. Only ``ColorID`` is ever assigned."""
    pending = plan.pending
    if not pending:
        return 0

    by_id = {str(t.ID): t for t in collection.tracks()}
    applied = 0
    for change in pending:
        track = by_id.get(change.content_id)
        if track is None:
            continue
        RekordboxCollection.set_color(track, change.new_color)
        applied += 1
        if applied % 100 == 0:
            progress("applying", {"applied": applied, "total": len(pending)})

    try:
        collection.commit()
    except Exception:
        collection.rollback()
        raise
    progress("applied", {"applied": applied})
    return applied


def sync(
    csv_path: str | Path,
    db_path: str | Path | None = None,
    dry_run: bool = False,
    skip_backup: bool = False,
    mapping: dict[Verdict, str] | None = None,
    progress: Progress = _noop,
    backup_root: Path | None = None,
    overwrite_existing: bool = True,
) -> SyncResult:
    """Full pipeline: guard, discover, back up, plan, apply."""
    export = read_spectro_csv(csv_path)
    progress(
        "csv_loaded",
        {
            "path": str(export.source),
            "rows": len(export.rows),
            "skipped": len(export.skipped),
            "verdict_counts": export.verdict_counts,
        },
    )

    database = resolve_database(db_path)
    progress("database_found", database.as_dict())

    ensure_rekordbox_closed()

    backup: Backup | None = None
    if not dry_run and not skip_backup:
        backup = backup_database(database.path, root=backup_root)
        progress("backup_created", backup.as_dict())

    with open_collection(database.path) as collection:
        plan = build_plan(
            export,
            collection,
            mapping=mapping,
            progress=progress,
            overwrite_existing=overwrite_existing,
        )
        applied = 0
        if not dry_run:
            # Re-check: Rekordbox may have been launched while we were reading.
            ensure_rekordbox_closed()
            applied = apply_plan(plan, collection, progress=progress)

    return SyncResult(
        plan=plan,
        database=database,
        csv_path=Path(csv_path),
        dry_run=dry_run,
        applied=applied,
        backup=backup,
    )


def iter_change_dicts(changes: Iterable[TrackChange]) -> list[dict]:
    return [c.as_dict() for c in changes]
