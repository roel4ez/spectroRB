"""Read Spectro CSV exports."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .model import SpectroRow, Verdict

PATH_COLUMNS = ("path", "file", "filepath", "file_path", "full_path", "location")
VERDICT_COLUMNS = ("verdict", "result", "status")
NAME_COLUMNS = ("filename", "name", "file_name")


class InvalidSpectroCsv(ValueError):
    pass


@dataclass(slots=True)
class SpectroExport:
    rows: list[SpectroRow]
    skipped: list[tuple[int, str]]
    verdict_counts: dict[str, int]
    source: Path

    @property
    def total_rows(self) -> int:
        return len(self.rows) + len(self.skipped)


def _pick(fieldnames: list[str], options: tuple[str, ...]) -> str | None:
    lookup = {name.strip().lower(): name for name in fieldnames if name}
    for option in options:
        if option in lookup:
            return lookup[option]
    return None


def read_spectro_csv(path: str | Path) -> SpectroExport:
    path = Path(path).expanduser()
    if not path.is_file():
        raise InvalidSpectroCsv(f"No CSV file at {path}")

    rows: list[SpectroRow] = []
    skipped: list[tuple[int, str]] = []

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise InvalidSpectroCsv(f"{path.name} has no header row")

        path_col = _pick(reader.fieldnames, PATH_COLUMNS)
        verdict_col = _pick(reader.fieldnames, VERDICT_COLUMNS)
        name_col = _pick(reader.fieldnames, NAME_COLUMNS)
        if not path_col or not verdict_col:
            raise InvalidSpectroCsv(
                f"{path.name} does not look like a Spectro export "
                "(missing a 'path' and/or 'verdict' column)"
            )

        # DictReader line numbers count the header, so data starts at line 2.
        for line, raw in enumerate(reader, start=2):
            file_path = (raw.get(path_col) or "").strip()
            raw_verdict = (raw.get(verdict_col) or "").strip()
            if not file_path:
                skipped.append((line, "no path"))
                continue
            verdict = Verdict.parse(raw_verdict)
            if verdict is None:
                skipped.append((line, f"unknown verdict {raw_verdict!r}"))
                continue
            rows.append(
                SpectroRow(
                    filename=(raw.get(name_col) or "").strip() if name_col else Path(file_path).name,
                    path=file_path,
                    verdict=verdict,
                    raw_verdict=raw_verdict,
                    line=line,
                )
            )

    counts = Counter(row.verdict.value for row in rows)
    return SpectroExport(
        rows=rows,
        skipped=skipped,
        verdict_counts={v.value: counts.get(v.value, 0) for v in Verdict},
        source=path,
    )
