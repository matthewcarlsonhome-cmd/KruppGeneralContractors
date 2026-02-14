"""KruppAI CLI — main entry point.

Usage:
    kruppai --help                    Show all commands
    kruppai init                      Initialize database and directories
    kruppai project list              List all projects
    kruppai project add               Add a new project
    kruppai status                    Show API usage, costs, recent docs
    kruppai daily-report              Generate a daily field report
    kruppai rfi                       Generate an RFI document
    kruppai minutes                   Generate meeting minutes
    kruppai client-update             Generate a client update letter
    kruppai safety-talk               Generate a safety talk
    kruppai punch-list                Generate a punch list
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


def _build_skill(skill_class: type, settings: Settings):
    """Instantiate a skill with all its dependencies."""
    from kruppai.core.api_client import AnthropicClient
    from kruppai.core.context_manager import ContextManager
    from kruppai.core.knowledge_base import KnowledgeBase
    from kruppai.core.output_formatter import OutputFormatter

    return skill_class(
        settings=settings,
        api_client=AnthropicClient(settings),
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


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


# =============================================================================
# Phase 1 Skill Commands
# =============================================================================


@cli.command("daily-report")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--notes", "-n", required=True, help="Field notes (text or path to .txt file)")
@click.option("--date", "-d", default=None, help="Report date (YYYY-MM-DD, defaults to today)")
@click.option("--weather-override", default=None, help="Manual weather override")
@click.option("--output-dir", "-o", default=None, help="Override output directory")
@click.pass_context
def daily_report(
    ctx: click.Context,
    project: str,
    notes: str,
    date: str | None,
    weather_override: str | None,
    output_dir: str | None,
) -> None:
    """Generate a daily field report from rough notes."""
    from kruppai.skills.daily_report import DailyReportSkill

    settings: Settings = ctx.obj["settings"]
    if output_dir:
        from pathlib import Path

        settings.output_dir = Path(output_dir)

    skill = _build_skill(DailyReportSkill, settings)
    try:
        with console.status("[bold]Generating daily report..."):
            result = skill.execute(
                project=project,
                notes=notes,
                date=date,
                weather_override=weather_override,
            )
        console.print(f"\n[green]Daily report generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating report:[/red] {e}")


@cli.command("rfi")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--issue", "-i", required=True, help="Description of the design question/issue")
@click.option("--to", default="Architect", help="Who to direct the RFI to")
@click.option(
    "--priority",
    type=click.Choice(["urgent", "high", "normal", "low"], case_sensitive=False),
    default="normal",
    help="RFI priority",
)
@click.option("--drawing-ref", default=None, help="Drawing sheet reference")
@click.option("--spec-ref", default=None, help="Specification section reference")
@click.pass_context
def rfi(
    ctx: click.Context,
    project: str,
    issue: str,
    to: str,
    priority: str,
    drawing_ref: str | None,
    spec_ref: str | None,
) -> None:
    """Generate a formal RFI from an issue description."""
    from kruppai.skills.rfi_generator import RfiGeneratorSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(RfiGeneratorSkill, settings)
    try:
        with console.status("[bold]Generating RFI..."):
            result = skill.execute(
                project=project,
                issue=issue,
                to=to,
                priority=priority,
                drawing_ref=drawing_ref,
                spec_ref=spec_ref,
            )
        console.print(f"\n[green]RFI generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating RFI:[/red] {e}")


@cli.command("minutes")
@click.option("--project", "-p", required=True, help="Project code")
@click.option(
    "--type",
    "-t",
    "meeting_type",
    required=True,
    type=click.Choice(["oac", "subcontractor", "safety", "preconstruction", "internal"], case_sensitive=False),
    help="Meeting type",
)
@click.option("--notes", "-n", required=True, help="Meeting notes (text or path to .txt file)")
@click.option("--date", "-d", default=None, help="Meeting date (YYYY-MM-DD, defaults to today)")
@click.option("--attendees", "-a", default=None, help="Comma-separated attendee list")
@click.pass_context
def minutes(
    ctx: click.Context,
    project: str,
    meeting_type: str,
    notes: str,
    date: str | None,
    attendees: str | None,
) -> None:
    """Generate meeting minutes from rough notes."""
    from kruppai.skills.meeting_minutes import MeetingMinutesSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(MeetingMinutesSkill, settings)
    try:
        with console.status("[bold]Generating meeting minutes..."):
            result = skill.execute(
                project=project,
                type=meeting_type,
                notes=notes,
                date=date,
                attendees=attendees,
            )
        console.print(f"\n[green]Minutes generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating minutes:[/red] {e}")


@cli.command("client-update")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--notes", "-n", required=True, help="PM's update notes (text or path to .txt file)")
@click.option(
    "--period",
    type=click.Choice(["weekly", "monthly"], case_sensitive=False),
    default="weekly",
    help="Update period",
)
@click.pass_context
def client_update(
    ctx: click.Context,
    project: str,
    notes: str,
    period: str,
) -> None:
    """Generate a client update letter on Krupp letterhead."""
    from kruppai.skills.client_update import ClientUpdateSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(ClientUpdateSkill, settings)
    try:
        with console.status("[bold]Generating client update..."):
            result = skill.execute(
                project=project,
                notes=notes,
                period=period,
            )
        console.print(f"\n[green]Client update generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating update:[/red] {e}")


@cli.command("safety-talk")
@click.option("--topic", "-t", required=True, help="Safety topic or rough notes")
@click.option("--project", "-p", default=None, help="Project code (optional)")
@click.option(
    "--season",
    type=click.Choice(["spring", "summer", "fall", "winter"], case_sensitive=False),
    default=None,
    help="Season for seasonal relevance",
)
@click.option("--trades", default=None, help="Comma-separated trades attending")
@click.pass_context
def safety_talk(
    ctx: click.Context,
    topic: str,
    project: str | None,
    season: str | None,
    trades: str | None,
) -> None:
    """Generate a toolbox safety talk document."""
    from kruppai.skills.safety_talk import SafetyTalkSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(SafetyTalkSkill, settings)
    try:
        with console.status("[bold]Generating safety talk..."):
            result = skill.execute(
                topic=topic,
                project=project,
                season=season,
                trades=trades,
            )
        console.print(f"\n[green]Safety talk generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating safety talk:[/red] {e}")


@cli.command("punch-list")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--notes", "-n", required=True, help="Walk-through observations (text or path to .txt file)")
@click.option("--area", default=None, help="Building area/zone (e.g., '2nd Floor')")
@click.option("--name", default=None, help="List name (defaults to 'Punch List - area - date')")
@click.pass_context
def punch_list(
    ctx: click.Context,
    project: str,
    notes: str,
    area: str | None,
    name: str | None,
) -> None:
    """Generate a punch list in DOCX and XLSX formats."""
    from kruppai.skills.punch_list import PunchListSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(PunchListSkill, settings)
    try:
        with console.status("[bold]Generating punch list..."):
            result = skill.execute(
                project=project,
                notes=notes,
                area=area,
                name=name,
            )
        console.print(f"\n[green]Punch list generated:[/green] {result.output_path}")
        console.print("[dim]XLSX tracking spreadsheet also created.[/dim]")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating punch list:[/red] {e}")


if __name__ == "__main__":
    cli()
