"""KruppAI CLI — main entry point.

Usage:
    kruppai --help                    Show all commands
    kruppai init                      Initialize database and directories
    kruppai project list              List all projects
    kruppai project add               Add a new project
    kruppai status                    Show API usage, costs, recent docs
"""

import click
from rich.console import Console
from rich.table import Table

from kruppai.core.config import Settings
from kruppai.core.database import get_db, init_db

console = Console()


def _get_settings() -> Settings:
    """Load settings, handling missing .env gracefully."""
    try:
        return Settings()
    except Exception:
        return Settings(_env_file=None)


@click.group()
@click.version_option(version="0.1.0", prog_name="kruppai")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """KruppAI — Construction AI Toolkit.

    AI-powered document generation for construction general contractors.
    """
    ctx.ensure_object(dict)
    ctx.obj["settings"] = _get_settings()


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize KruppAI database and directories."""
    settings: Settings = ctx.obj["settings"]
    settings.ensure_directories()
    init_db(settings)
    console.print(
        f"[green]Database initialized:[/green] {settings.db_path}"
    )
    console.print(
        f"[green]Output directory:[/green] {settings.output_dir}"
    )
    console.print("\n[bold]KruppAI is ready to use.[/bold]")


@cli.group()
def project() -> None:
    """Manage projects."""


@project.command("list")
@click.pass_context
def project_list(ctx: click.Context) -> None:
    """List all projects."""
    settings: Settings = ctx.obj["settings"]

    try:
        with get_db(settings) as conn:
            cursor = conn.execute(
                "SELECT project_code, name, client_name, status, "
                "current_percent_complete "
                "FROM projects WHERE is_archived = 0 "
                "ORDER BY project_code"
            )
            rows = cursor.fetchall()
    except Exception:
        console.print(
            "[yellow]Database not initialized. Run 'kruppai init' first.[/yellow]"
        )
        return

    if not rows:
        console.print("[yellow]No projects found.[/yellow]")
        console.print("Add a project with: kruppai project add")
        return

    table = Table(title="Active Projects")
    table.add_column("Code", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Client", style="white")
    table.add_column("Status", style="green")
    table.add_column("% Complete", justify="right")

    for row in rows:
        pct = f"{row['current_percent_complete']:.0f}%" if row["current_percent_complete"] else "0%"
        table.add_row(
            row["project_code"],
            row["name"],
            row["client_name"] or "",
            row["status"],
            pct,
        )

    console.print(table)


@project.command("add")
@click.option("--code", prompt="Project code (e.g., KRUPP-2026-001)", help="Unique project code")
@click.option("--name", prompt="Project name", help="Project name")
@click.option("--client", prompt="Client name", help="Client name")
@click.option(
    "--type",
    "project_type",
    type=click.Choice(
        ["commercial", "healthcare", "education", "industrial", "residential", "municipal"],
        case_sensitive=False,
    ),
    prompt="Project type",
    help="Project type",
)
@click.option(
    "--status",
    type=click.Choice(
        ["preconstruction", "active", "punch_list", "closeout", "complete"],
        case_sensitive=False,
    ),
    default="active",
    help="Project status",
)
@click.option("--address", default="", help="Project address")
@click.option("--latitude", type=float, default=None, help="Latitude for weather")
@click.option("--longitude", type=float, default=None, help="Longitude for weather")
@click.pass_context
def project_add(
    ctx: click.Context,
    code: str,
    name: str,
    client: str,
    project_type: str,
    status: str,
    address: str,
    latitude: float | None,
    longitude: float | None,
) -> None:
    """Add a new project."""
    settings: Settings = ctx.obj["settings"]

    try:
        with get_db(settings) as conn:
            conn.execute(
                "INSERT INTO projects "
                "(project_code, name, client_name, project_type, status, "
                "address, latitude, longitude) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    code,
                    name,
                    client,
                    project_type,
                    status,
                    address,
                    latitude,
                    longitude,
                ),
            )
        console.print(f"[green]Project '{code}' created successfully.[/green]")
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            console.print(f"[red]Project code '{code}' already exists.[/red]")
        else:
            console.print(f"[red]Error creating project: {e}[/red]")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show system status — API usage, costs, recent documents."""
    settings: Settings = ctx.obj["settings"]

    try:
        with get_db(settings) as conn:
            # API usage summary
            cursor = conn.execute(
                "SELECT skill_name, COUNT(*) as calls, "
                "SUM(cost_cents) as total_cost, "
                "SUM(input_tokens) as input_tok, "
                "SUM(output_tokens) as output_tok "
                "FROM api_usage WHERE success = 1 "
                "GROUP BY skill_name ORDER BY total_cost DESC"
            )
            usage_rows = cursor.fetchall()

            # Today's cost
            from datetime import date as dt_date

            today = dt_date.today().isoformat()
            cursor = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
                "WHERE created_at >= ? AND success = 1",
                (today,),
            )
            today_cost = cursor.fetchone()[0]

            # This month's cost
            month = today[:7] + "-01"
            cursor = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
                "WHERE created_at >= ? AND success = 1",
                (month,),
            )
            month_cost = cursor.fetchone()[0]

            # Recent documents
            cursor = conn.execute(
                "SELECT skill_name, file_name, created_at "
                "FROM generated_documents "
                "WHERE is_current = 1 "
                "ORDER BY created_at DESC LIMIT 5"
            )
            recent_docs = cursor.fetchall()

    except Exception:
        console.print(
            "[yellow]Database not initialized. Run 'kruppai init' first.[/yellow]"
        )
        return

    # Cost summary
    console.print("\n[bold]API Cost Summary[/bold]")
    console.print(
        f"  Today:      ${today_cost / 100:.2f} / "
        f"${settings.daily_cost_limit_cents / 100:.2f}"
    )
    console.print(
        f"  This month: ${month_cost / 100:.2f} / "
        f"${settings.monthly_cost_limit_cents / 100:.2f}"
    )

    # Usage by skill
    if usage_rows:
        table = Table(title="\nUsage by Skill")
        table.add_column("Skill", style="cyan")
        table.add_column("Calls", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Tokens (in/out)", justify="right")

        for row in usage_rows:
            table.add_row(
                row["skill_name"],
                str(row["calls"]),
                f"${row['total_cost'] / 100:.2f}",
                f"{row['input_tok']:,} / {row['output_tok']:,}",
            )
        console.print(table)
    else:
        console.print("\n[dim]No API usage recorded yet.[/dim]")

    # Recent documents
    if recent_docs:
        table = Table(title="\nRecent Documents")
        table.add_column("Skill", style="cyan")
        table.add_column("File", style="white")
        table.add_column("Created", style="dim")

        for row in recent_docs:
            table.add_row(
                row["skill_name"],
                row["file_name"],
                row["created_at"][:16],
            )
        console.print(table)
    else:
        console.print("\n[dim]No documents generated yet.[/dim]")


if __name__ == "__main__":
    cli()
