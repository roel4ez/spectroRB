"""Refuse to touch the database while Rekordbox is running."""

from __future__ import annotations

import subprocess

REKORDBOX_PROCESS_HINTS = ("rekordbox", "rekordboxAgent", "rekordboxAgentService")


class RekordboxRunning(RuntimeError):
    def __init__(self, processes: list[str]):
        self.processes = processes
        joined = ", ".join(sorted(set(processes)))
        super().__init__(
            f"Rekordbox appears to be running ({joined}). "
            "Quit Rekordbox completely before syncing."
        )


def running_rekordbox_processes() -> list[str]:
    """Names of running Rekordbox-related processes."""
    try:
        output = subprocess.run(
            ["/bin/ps", "-Ao", "comm="],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    hits = []
    for line in output.splitlines():
        name = line.strip().rsplit("/", 1)[-1]
        # Prefix match, so unrelated tools with "rekordbox" in the name don't trip it.
        if name.lower().startswith("rekordbox"):
            hits.append(name)
    return hits


def ensure_rekordbox_closed() -> None:
    processes = running_rekordbox_processes()
    if processes:
        raise RekordboxRunning(processes)
