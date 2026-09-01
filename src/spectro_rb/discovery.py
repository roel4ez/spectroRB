"""Locate the Rekordbox database without asking the user."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DB_DIRS = [
    Path.home() / "Library/Pioneer/rekordbox",
    Path.home() / "Library/Pioneer/rekordbox6",
    Path.home() / "Library/Pioneer/rekordbox7",
]


@dataclass(slots=True)
class DatabaseCandidate:
    path: Path
    source: str
    version: str | None = None

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    @property
    def modified(self) -> datetime:
        return datetime.fromtimestamp(self.path.stat().st_mtime)

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "source": self.source,
            "version": self.version,
            "size": self.size,
            "modified": self.modified.isoformat(timespec="seconds"),
        }


def _from_pyrekordbox() -> list[DatabaseCandidate]:
    """Ask pyrekordbox, which also reads Rekordbox's own settings files."""
    found: list[DatabaseCandidate] = []
    try:
        from pyrekordbox.config import get_config
    except Exception:
        return found

    for key, version in (("rekordbox7", "7"), ("rekordbox6", "6")):
        try:
            db_path = get_config(key, "db_path")
        except Exception:
            continue
        if db_path and Path(db_path).is_file():
            found.append(
                DatabaseCandidate(Path(db_path), source="rekordbox settings", version=version)
            )
    return found


def _from_default_dirs() -> list[DatabaseCandidate]:
    found = []
    for directory in DEFAULT_DB_DIRS:
        candidate = directory / "master.db"
        if candidate.is_file():
            found.append(DatabaseCandidate(candidate, source="default location"))
    return found


def _looks_encrypted(path: Path) -> bool:
    """Rekordbox 6/7 databases are SQLCipher-encrypted, so they lack the SQLite header."""
    try:
        with path.open("rb") as fh:
            return fh.read(16) != b"SQLite format 3\x00"
    except OSError:
        return False


def discover_databases() -> list[DatabaseCandidate]:
    """All plausible Rekordbox databases, best candidate first."""
    seen: dict[Path, DatabaseCandidate] = {}
    for candidate in _from_pyrekordbox() + _from_default_dirs():
        resolved = candidate.path.resolve()
        if resolved in seen or not _looks_encrypted(resolved):
            continue
        seen[resolved] = DatabaseCandidate(resolved, candidate.source, candidate.version)
    return sorted(seen.values(), key=lambda c: c.modified, reverse=True)


class DatabaseNotFound(RuntimeError):
    pass


def resolve_database(explicit: str | os.PathLike[str] | None = None) -> DatabaseCandidate:
    """Resolve the database to use: an explicit path, else auto-detection."""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise DatabaseNotFound(f"No Rekordbox database at {path}")
        return DatabaseCandidate(path, source="user supplied")

    candidates = discover_databases()
    if not candidates:
        raise DatabaseNotFound(
            "Could not find a Rekordbox database. Looked in "
            + ", ".join(str(d) for d in DEFAULT_DB_DIRS)
            + ". Pass one explicitly with --db."
        )
    return candidates[0]
