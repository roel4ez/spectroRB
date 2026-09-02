"""Match Spectro CSV rows to Rekordbox collection entries.

macOS mixes NFC and NFD unicode in filenames, so every path is normalised to NFC
before comparison.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from .model import MatchKind


def normalize_path(raw: str) -> str:
    """Normalise a filesystem path or file:// URL for comparison."""
    if not raw:
        return ""
    value = raw.strip()
    if value.startswith("file://"):
        parsed = urlparse(value)
        value = unquote(parsed.path)
    value = unicodedata.normalize("NFC", value)
    value = os.path.normpath(os.path.expanduser(value))
    return value


def path_key(raw: str) -> str:
    return normalize_path(raw)


def casefold_key(raw: str) -> str:
    return normalize_path(raw).casefold()


def filename_key(raw: str) -> str:
    return unicodedata.normalize("NFC", Path(normalize_path(raw)).name).casefold()


@dataclass(slots=True)
class TrackIndex:
    """Lookup tables over the Rekordbox collection.

    Keys that resolve to more than one track are dropped from the fuzzier
    indexes so a fallback can never silently colour the wrong track.
    """

    by_path: dict[str, object] = field(default_factory=dict)
    by_casefold: dict[str, object] = field(default_factory=dict)
    by_filename: dict[str, object] = field(default_factory=dict)
    _ambiguous_casefold: set[str] = field(default_factory=set)
    _ambiguous_filename: set[str] = field(default_factory=set)
    size: int = 0

    @classmethod
    def build(cls, tracks, path_of) -> TrackIndex:
        index = cls()
        for track in tracks:
            raw = path_of(track)
            if not raw:
                continue
            index.size += 1
            exact = path_key(raw)
            index.by_path.setdefault(exact, track)

            folded = casefold_key(raw)
            if folded in index.by_casefold:
                if index.by_casefold[folded] is not track:
                    index._ambiguous_casefold.add(folded)
            else:
                index.by_casefold[folded] = track

            name = filename_key(raw)
            if name in index.by_filename:
                if index.by_filename[name] is not track:
                    index._ambiguous_filename.add(name)
            else:
                index.by_filename[name] = track

        for key in index._ambiguous_casefold:
            index.by_casefold.pop(key, None)
        for key in index._ambiguous_filename:
            index.by_filename.pop(key, None)
        return index

    def lookup(self, raw_path: str, filename: str | None = None):
        """Return (track, MatchKind). Track is None when nothing safe matched."""
        exact = self.by_path.get(path_key(raw_path))
        if exact is not None:
            return exact, MatchKind.EXACT_PATH

        folded = casefold_key(raw_path)
        if folded in self._ambiguous_casefold:
            return None, MatchKind.AMBIGUOUS
        insensitive = self.by_casefold.get(folded)
        if insensitive is not None:
            return insensitive, MatchKind.CASE_INSENSITIVE_PATH

        name = filename_key(filename or raw_path)
        if name in self._ambiguous_filename:
            return None, MatchKind.AMBIGUOUS
        by_name = self.by_filename.get(name)
        if by_name is not None:
            return by_name, MatchKind.FILENAME

        return None, MatchKind.UNMATCHED
