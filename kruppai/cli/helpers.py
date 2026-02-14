"""CLI helper utilities for KruppAI quick mode and interactive workflows.

Provides convenience functions used by the ``quick`` command in main.py:
- Database initialization check
- Multi-line notes input (from file or interactive prompt)
- Interactive project selector
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from kruppai.core.config import Settings
from kruppai.core.database import get_db

console = Console()


def ensure_initialized(settings: Settings) -> bool:
    """Check whether the KruppAI database exists and is usable.

    If the database file is missing or cannot be opened, prints a
    helpful message suggesting ``kruppai init`` and returns ``False``.

    Args:
        settings: Application settings containing the database path.

    Returns:
        True if the database exists and is accessible, False otherwise.
    """
    db_path = settings.db_path
    if not db_path.exists():
        console.print(
            "[yellow]KruppAI is not initialized.[/yellow]\n"
            "Run [bold]kruppai init[/bold] to create the database "
            "and output directories."
        )
        return False

    # Verify the database is readable
    try:
        with get_db(settings) as conn:
            conn.execute("SELECT 1 FROM projects LIMIT 1")
    except Exception:
        console.print(
            "[yellow]Database appears corrupted or incomplete.[/yellow]\n"
            "Run [bold]kruppai init[/bold] to re-initialize."
        )
        return False

    return True


def read_notes_input(file_path: str | None, prompt_text: str) -> str:
    """Read notes from a file or prompt the user for multi-line input.

    If *file_path* is provided and points to a readable file, its contents
    are returned verbatim.  Otherwise the user is prompted to enter
    multi-line text interactively (terminated by an empty line).

    Args:
        file_path: Optional path to a ``.txt`` or ``.md`` file.
        prompt_text: Prompt label shown when requesting interactive input.

    Returns:
        The notes text.  May be empty if the user provides nothing.
    """
    # Attempt to read from file first
    if file_path:
        path = Path(file_path)
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    console.print(
                        f"[dim]Read {len(content)} characters from {path.name}[/dim]"
                    )
                    return content
            except Exception as exc:
                console.print(
                    f"[yellow]Could not read file {path}: {exc}[/yellow]"
                )

    # Interactive multi-line input
    console.print(
        f"[bold]{prompt_text}[/bold] "
        "[dim](enter text, then press Enter twice to finish)[/dim]"
    )

    lines: list[str] = []
    while True:
        try:
            line = click.prompt("", default="", show_default=False, prompt_suffix="")
        except click.Abort:
            break
        if line == "" and lines:
            break
        lines.append(line)

    return "\n".join(lines).strip()


def select_project(settings: Settings) -> str | None:
    """Display an interactive project list and let the user pick one.

    Queries the database for all active (non-archived) projects, renders
    them as a Rich table, and prompts for a selection by number.

    Args:
        settings: Application settings for database access.

    Returns:
        The selected project code, or ``None`` if no projects exist or
        the user cancels.
    """
    try:
        with get_db(settings) as conn:
            cursor = conn.execute(
                "SELECT project_code, name, client_name, status, "
                "current_percent_complete "
                "FROM projects WHERE is_archived = 0 "
                "ORDER BY project_code"
            )
            rows = [dict(r) for r in cursor.fetchall()]
    except Exception:
        console.print(
            "[yellow]Could not load projects. "
            "Is the database initialized?[/yellow]"
        )
        return None

    if not rows:
        console.print("[yellow]No projects found.[/yellow]")
        console.print("Add a project first with: [bold]kruppai project add[/bold]")
        return None

    # Render table
    table = Table(title="Select a Project")
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Code", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Client", style="white")
    table.add_column("Status", style="green")
    table.add_column("% Complete", justify="right")

    for idx, row in enumerate(rows, start=1):
        pct = (
            f"{row['current_percent_complete']:.0f}%"
            if row["current_percent_complete"]
            else "0%"
        )
        table.add_row(
            str(idx),
            row["project_code"],
            row["name"],
            row["client_name"] or "",
            row["status"],
            pct,
        )

    console.print(table)
    console.print()

    choice = click.prompt(
        "Enter project number",
        type=click.IntRange(1, len(rows)),
    )
    selected = rows[choice - 1]
    console.print(
        f"[dim]Selected: {selected['project_code']} — {selected['name']}[/dim]\n"
    )
    return selected["project_code"]
