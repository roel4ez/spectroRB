"""Command line interface: ``spectro-rb``."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .backup import list_backups
from .discovery import DatabaseNotFound, discover_databases
from .guard import RekordboxRunning
from .model import Verdict, color_label
from .rekordbox import RekordboxError
from .spectro import InvalidSpectroCsv
from .sync import SyncResult, sync

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Sync Spectro audio-quality verdicts into Rekordbox track colours.",
)
console = Console()
err_console = Console(stderr=True)

VERDICT_STYLE = {
    Verdict.LOSSLESS: ("🟢", "green"),
    Verdict.MEDIUM: ("🟡", "yellow"),
    Verdict.FAKE: ("🔴", "red"),
}


class JsonEmitter:
    """Newline-delimited JSON events, for the macOS app to parse."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, event: str, payload: dict) -> None:
        if not self.enabled:
            return
        sys.stdout.write(json.dumps({"event": event, **payload}) + "\n")
        sys.stdout.flush()


def _render_result(result: SyncResult, show_changes: int) -> None:
    plan = result.plan
    console.print()
    console.print(f"Rekordbox database: [dim]{result.database.path}[/dim]")
    if result.backup:
        console.print(f"Backup: [dim]{result.backup.directory}[/dim]")
    console.print(f" {plan.collection_size:,} tracks found")
    console.print()
    console.print("Spectro results:")
    for verdict in Verdict:
        icon, style = VERDICT_STYLE[verdict]
        count = plan.verdict_counts.get(verdict.value, 0)
        console.print(f" {icon} [{style}]{verdict.value}[/{style}] {count:,}")
    console.print()

    verb = "Would update" if result.dry_run else "Updating"
    console.print(f"{verb} Rekordbox...")
    console.print(f" {plan.collection_size:,} tracks checked")
    changed = result.applied if not result.dry_run else len(plan.pending)
    console.print(f" {changed:,} colors changed")
    if plan.recolored:
        console.print(
            f" [dim]{len(plan.recolored):,} of those already had a different colour[/dim]"
        )
    if plan.protected:
        console.print(
            f" [dim]{len(plan.protected):,} kept their existing colour (--keep-existing-colors)[/dim]"
        )
    if plan.unmatched:
        console.print(f" [dim]{len(plan.unmatched):,} CSV rows not in the collection[/dim]")
    if plan.ambiguous:
        console.print(f" [dim]{len(plan.ambiguous):,} CSV rows too ambiguous to match[/dim]")
    if plan.skipped_rows:
        console.print(f" [dim]{len(plan.skipped_rows):,} CSV rows skipped (unreadable)[/dim]")

    if show_changes and plan.pending:
        table = Table(title=None, box=None, pad_edge=False)
        table.add_column("Verdict")
        table.add_column("Colour")
        table.add_column("Artist", overflow="ellipsis", max_width=28)
        table.add_column("Title", overflow="ellipsis", max_width=38)
        for change in plan.pending[:show_changes]:
            icon, style = VERDICT_STYLE[change.verdict]
            table.add_row(
                f"{icon} {change.verdict.value}",
                f"{color_label(change.old_color)} → [{style}]{color_label(change.new_color)}[/{style}]",
                change.artist,
                change.title,
            )
        console.print()
        console.print(table)
        if len(plan.pending) > show_changes:
            console.print(f" [dim]… and {len(plan.pending) - show_changes:,} more[/dim]")

    if show_changes and plan.unmatched:
        console.print()
        console.print("[yellow]Not found in Rekordbox[/yellow] (left untouched):")
        for row in plan.unmatched[:show_changes]:
            icon, _ = VERDICT_STYLE[row.verdict]
            console.print(f" {icon} [dim]{row.path}[/dim]")
        if len(plan.unmatched) > show_changes:
            console.print(f" [dim]… and {len(plan.unmatched) - show_changes:,} more[/dim]")

    console.print()
    console.print("[dim]Dry run — nothing was written.[/dim]" if result.dry_run else "Done.")
    console.print()


def _fail(message: str, code: int = 1) -> None:
    err_console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code)


@app.command("sync")
def sync_command(
    csv: Path = typer.Argument(..., help="Spectro CSV export to read."),
    db: Optional[Path] = typer.Option(
        None, "--db", help="Rekordbox master.db (auto-detected when omitted)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show what would change without writing."
    ),
    skip_backup: bool = typer.Option(
        False, "--no-backup", help="Skip the timestamped database backup (not recommended)."
    ),
    keep_existing: bool = typer.Option(
        False,
        "--keep-existing-colors",
        "--keep-existing-colours",
        help="Leave tracks that already have a colour untouched.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit newline-delimited JSON events."),
    show: int = typer.Option(0, "--show", help="Print the first N planned changes."),
    json_changes: int = typer.Option(
        10000, "--json-changes", help="Max number of changes included in the JSON result."
    ),
    report: Optional[Path] = typer.Option(
        None, "--report", help="Write unmatched/ambiguous/unreadable CSV rows to this CSV file."
    ),
) -> None:
    """Sync colours from a Spectro CSV export into Rekordbox."""
    emitter = JsonEmitter(json_output)
    try:
        result = sync(
            csv_path=csv,
            db_path=db,
            dry_run=dry_run,
            skip_backup=skip_backup,
            overwrite_existing=not keep_existing,
            progress=emitter,
        )
    except InvalidSpectroCsv as exc:
        emitter("error", {"kind": "csv", "message": str(exc)})
        _fail(str(exc), code=2)
    except DatabaseNotFound as exc:
        emitter("error", {"kind": "database_not_found", "message": str(exc)})
        _fail(str(exc), code=3)
    except RekordboxRunning as exc:
        emitter("error", {"kind": "rekordbox_running", "message": str(exc)})
        _fail(str(exc), code=4)
    except RekordboxError as exc:
        emitter("error", {"kind": "rekordbox", "message": str(exc)})
        _fail(str(exc), code=5)

    report_path: Path | None = None
    if report is not None:
        from .report import write_report

        report_path = write_report(result.plan, report)
        emitter("report_written", {"path": str(report_path)})

    if json_output:
        payload = result.as_dict()
        payload["report"] = str(report_path) if report_path else None
        payload["changes"] = [c.as_dict() for c in result.plan.pending[:json_changes]]
        payload["unmatched"] = [
            {"path": r.path, "filename": r.filename, "verdict": r.verdict.value}
            for r in result.plan.unmatched[:json_changes]
        ]
        emitter("result", payload)
    else:
        _render_result(result, show_changes=show)
        if report_path:
            console.print(f"Report: [dim]{report_path}[/dim]")
            console.print()


@app.command("doctor")
def doctor(json_output: bool = typer.Option(False, "--json")) -> None:
    """Check database detection, Rekordbox state and backups."""
    from .guard import running_rekordbox_processes

    databases = [c.as_dict() for c in discover_databases()]
    processes = running_rekordbox_processes()
    backups = [str(p) for p in list_backups()[:5]]

    if json_output:
        console.print_json(
            data={"version": __version__, "databases": databases, "rekordbox_processes": processes, "backups": backups}
        )
        return

    console.print(f"spectro-rb {__version__}")
    console.print()
    console.print("Databases found:" if databases else "[red]No Rekordbox database found.[/red]")
    for entry in databases:
        console.print(f"  {entry['path']}  [dim]({entry['source']}, {entry['modified']})[/dim]")
    console.print()
    if processes:
        console.print(f"[yellow]Rekordbox is running:[/yellow] {', '.join(sorted(set(processes)))}")
    else:
        console.print("[green]Rekordbox is not running.[/green]")
    console.print()
    console.print("Recent backups:" if backups else "No backups yet.")
    for entry in backups:
        console.print(f"  {entry}")


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
