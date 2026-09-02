"""Write a CSV report of everything that could not be synced."""

from __future__ import annotations

import csv
from pathlib import Path

from .model import SyncPlan


def write_report(plan: SyncPlan, path: str | Path) -> Path:
    """Write unmatched, ambiguous and unreadable CSV rows to ``path``."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "reason",
                "csv_line",
                "verdict",
                "trusted",
                "confidence_pct",
                "cutoff_khz",
                "filename",
                "path",
            ]
        )

        def _row(reason: str, row) -> list:
            return [
                reason,
                row.line,
                row.verdict.value,
                "yes" if row.trusted else "no",
                "" if row.confidence_pct is None else row.confidence_pct,
                "" if row.cutoff_khz is None else row.cutoff_khz,
                row.filename,
                row.path,
            ]

        for row in plan.unmatched:
            writer.writerow(_row("not in collection", row))
        for row in plan.ambiguous:
            writer.writerow(_row("ambiguous filename", row))
        for line, reason in plan.skipped_rows:
            writer.writerow([f"unreadable row: {reason}", line, "", "", "", "", "", ""])
    return path
