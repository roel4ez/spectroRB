"""Thin wrapper around pyrekordbox that only ever touches track colours."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from .model import NO_COLOR


class RekordboxError(RuntimeError):
    pass


class RekordboxCollection:
    """Read the collection, and write nothing except ``DjmdContent.ColorID``."""

    def __init__(self, db):
        self._db = db

    @property
    def db(self):
        return self._db

    def tracks(self) -> list:
        """Active (not locally deleted) collection entries with a file path."""
        try:
            contents = list(self._db.get_content())
        except Exception as exc:  # pragma: no cover - depends on local db
            raise RekordboxError(f"Could not read the Rekordbox collection: {exc}") from exc
        return [c for c in contents if not int(c.rb_local_deleted or 0) and c.FolderPath]

    @staticmethod
    def path_of(track) -> str:
        return track.FolderPath or ""

    @staticmethod
    def color_of(track) -> str:
        value = track.ColorID
        return NO_COLOR if value in (None, "") else str(value)

    @staticmethod
    def set_color(track, color_id: str) -> None:
        track.ColorID = str(color_id)

    def commit(self) -> None:
        try:
            self._db.commit()
        except Exception as exc:  # pragma: no cover - depends on local db
            raise RekordboxError(f"Could not save changes to Rekordbox: {exc}") from exc

    def rollback(self) -> None:
        try:
            self._db.rollback()
        except Exception:
            pass


@contextmanager
def open_collection(db_path: str | Path, unlock: bool = True):
    """Open the Rekordbox database, yielding a :class:`RekordboxCollection`."""
    try:
        from pyrekordbox import Rekordbox6Database
    except Exception as exc:  # pragma: no cover - import guard
        raise RekordboxError(f"pyrekordbox is not available: {exc}") from exc

    try:
        db = Rekordbox6Database(path=str(db_path), unlock=unlock)
    except Exception as exc:
        raise RekordboxError(
            f"Could not open the Rekordbox database at {db_path}: {exc}\n"
            "If this is a decryption-key problem, run: python -m pyrekordbox download-key"
        ) from exc

    collection = RekordboxCollection(db)
    try:
        yield collection
    finally:
        try:
            db.close()
        except Exception:
            pass
