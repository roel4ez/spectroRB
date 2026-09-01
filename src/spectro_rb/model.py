"""Shared value objects and the verdict -> Rekordbox colour mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    LOSSLESS = "LOSSLESS"
    MEDIUM = "MEDIUM"
    FAKE = "FAKE"

    @classmethod
    def parse(cls, raw: str) -> "Verdict | None":
        try:
            return cls(raw.strip().upper())
        except ValueError:
            return None


# Rekordbox stores colours as DjmdColor row IDs. These are fixed by rekordbox.
COLOR_IDS: dict[str, str] = {
    "PINK": "1",
    "RED": "2",
    "ORANGE": "3",
    "YELLOW": "4",
    "GREEN": "5",
    "AQUA": "6",
    "BLUE": "7",
    "PURPLE": "8",
}
COLOR_NAMES: dict[str, str] = {v: k.capitalize() for k, v in COLOR_IDS.items()}
NO_COLOR = "0"

DEFAULT_MAPPING: dict[Verdict, str] = {
    Verdict.LOSSLESS: COLOR_IDS["GREEN"],
    Verdict.MEDIUM: COLOR_IDS["YELLOW"],
    Verdict.FAKE: COLOR_IDS["RED"],
}


def color_label(color_id: str | None) -> str:
    if not color_id or str(color_id) == NO_COLOR:
        return "None"
    return COLOR_NAMES.get(str(color_id), f"#{color_id}")


@dataclass(slots=True)
class SpectroRow:
    """One row of a Spectro CSV export."""

    filename: str
    path: str
    verdict: Verdict
    raw_verdict: str
    line: int


class MatchKind(str, Enum):
    EXACT_PATH = "exact_path"
    CASE_INSENSITIVE_PATH = "case_insensitive_path"
    FILENAME = "filename"
    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"


@dataclass(slots=True)
class TrackChange:
    """A single planned (or applied) colour change."""

    content_id: str
    title: str
    artist: str
    path: str
    verdict: Verdict
    old_color: str
    new_color: str
    match_kind: MatchKind

    @property
    def changed(self) -> bool:
        return str(self.old_color or NO_COLOR) != str(self.new_color)

    def as_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "title": self.title,
            "artist": self.artist,
            "path": self.path,
            "verdict": self.verdict.value,
            "old_color": color_label(self.old_color),
            "new_color": color_label(self.new_color),
            "match_kind": self.match_kind.value,
            "changed": self.changed,
        }


@dataclass(slots=True)
class SyncPlan:
    """The full result of analysing a CSV against a Rekordbox collection."""

    collection_size: int
    csv_rows: int
    verdict_counts: dict[str, int] = field(default_factory=dict)
    changes: list[TrackChange] = field(default_factory=list)
    unmatched: list[SpectroRow] = field(default_factory=list)
    ambiguous: list[SpectroRow] = field(default_factory=list)
    skipped_rows: list[tuple[int, str]] = field(default_factory=list)

    @property
    def matched(self) -> list[TrackChange]:
        return self.changes

    @property
    def pending(self) -> list[TrackChange]:
        return [c for c in self.changes if c.changed]

    @property
    def recolored(self) -> list[TrackChange]:
        """Changes that overwrite an existing, different colour."""
        return [c for c in self.pending if str(c.old_color or NO_COLOR) != NO_COLOR]

    def summary(self) -> dict:
        return {
            "collection_size": self.collection_size,
            "csv_rows": self.csv_rows,
            "verdict_counts": self.verdict_counts,
            "matched": len(self.changes),
            "changes": len(self.pending),
            "already_correct": len(self.changes) - len(self.pending),
            "overwrites_existing_color": len(self.recolored),
            "unmatched": len(self.unmatched),
            "ambiguous": len(self.ambiguous),
            "skipped_rows": len(self.skipped_rows),
        }
