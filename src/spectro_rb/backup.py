"""Timestamped backups of the Rekordbox database."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

BACKUP_ROOT = Path.home() / "Library/Application Support/spectro-rb-sync/backups"
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


@dataclass(slots=True)
class Backup:
    directory: Path
    files: list[Path]
    created_at: datetime

    @property
    def total_bytes(self) -> int:
        return sum(f.stat().st_size for f in self.files)

    def as_dict(self) -> dict:
        return {
            "directory": str(self.directory),
            "files": [str(f) for f in self.files],
            "bytes": self.total_bytes,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }


def backup_database(db_path: Path, root: Path | None = None) -> Backup:
    """Copy master.db (and its SQLite sidecars) into a timestamped folder."""
    db_path = Path(db_path)
    created_at = datetime.now()
    root = Path(root) if root else BACKUP_ROOT
    directory = root / created_at.strftime("%Y-%m-%d_%H-%M-%S")
    directory.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    sources = [db_path] + [
        db_path.with_name(db_path.name + suffix) for suffix in SIDECAR_SUFFIXES
    ]
    for source in sources:
        if not source.is_file():
            continue
        target = directory / source.name
        shutil.copy2(source, target)
        copied.append(target)

    if not copied:
        raise FileNotFoundError(f"Nothing to back up at {db_path}")
    return Backup(directory=directory, files=copied, created_at=created_at)


def list_backups(root: Path | None = None) -> list[Path]:
    root = Path(root) if root else BACKUP_ROOT
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir()), reverse=True)
