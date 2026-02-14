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
    kruppai estimate-review           Review a cost estimate against benchmarks
    kruppai bid-compare               Compare multiple bids for a trade
    kruppai change-order              Generate a change order proposal
    kruppai schedule-analysis         Analyze schedule variance
    kruppai submittal-status          Track submittals and flag overdue items
    kruppai contract-review           Review a contract or insurance cert
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
# Quick Mode — Guided interactive workflow
# =============================================================================


SKILL_MENU = [
    ("1", "Daily Report", "daily-report", "Write up today's field notes"),
    ("2", "RFI", "rfi", "Create a request for information"),
    ("3", "Meeting Minutes", "minutes", "Document a meeting"),
    ("4", "Client Update", "client-update", "Write a progress letter to the owner"),
    ("5", "Safety Talk", "safety-talk", "Generate a toolbox safety talk"),
    ("6", "Punch List", "punch-list", "Create a punch list from walk-through notes"),
    ("7", "Estimate Review", "estimate-review", "Review a cost estimate against benchmarks"),
    ("8", "Bid Comparison", "bid-compare", "Compare multiple bids for a trade"),
    ("9", "Change Order", "change-order", "Generate a change order proposal"),
    ("10", "Schedule Analysis", "schedule-analysis", "Analyze schedule variance and risks"),
    ("11", "Submittal Status", "submittal-status", "Track submittals and flag overdue items"),
    ("12", "Contract Review", "contract-review", "Review a contract or insurance cert"),
    ("13", "Proposal", "proposal", "Generate a project proposal"),
    ("14", "Budget Forecast", "budget-forecast", "Analyze budget vs. actuals with projections"),
    ("15", "Closeout Package", "closeout", "Assemble a project closeout checklist"),
    ("16", "Lessons Learned", "lessons-learned", "Capture lessons from project experience"),
    ("17", "Case Study", "case-study", "Build a marketing case study from project data"),
    ("18", "Incident Report", "incident-report", "Document a safety incident or near miss"),
]


@cli.command("quick")
@click.pass_context
def quick(ctx: click.Context) -> None:
    """Interactive mode — guided step-by-step workflow.

    The easiest way to use KruppAI. Just run 'kruppai quick'
    and follow the prompts.
    """
    from kruppai.cli.helpers import ensure_initialized, read_notes_input, select_project

    settings: Settings = ctx.obj["settings"]

    if not ensure_initialized(settings):
        return

    # Step 1: What do you want to do?
    console.print("\n[bold]What would you like to create?[/bold]\n")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Document", style="bold white")
    table.add_column("Description", style="dim")

    for num, name, _, desc in SKILL_MENU:
        table.add_row(num, name, desc)
    console.print(table)
    console.print()

    choice = click.prompt("Enter number", type=click.IntRange(1, len(SKILL_MENU)), value_proc=int)
    _, skill_name, command, _ = SKILL_MENU[choice - 1]

    console.print(f"\n[bold]Creating: {skill_name}[/bold]\n")

    # Step 2: Select project (except safety talk which is optional)
    project_code = None
    needs_project = command != "safety-talk"

    if needs_project:
        project_code = select_project(settings)
        if project_code is None:
            return

    # Step 3: Get input based on skill type
    if command == "daily-report":
        notes = read_notes_input(None, "Enter today's field notes")
        if not notes:
            console.print("[red]No notes provided.[/red]")
            return
        ctx.invoke(
            daily_report, project=project_code, notes=notes,
            date=None, weather_override=None, output_dir=None,
        )

    elif command == "rfi":
        issue = read_notes_input(None, "Describe the design question or issue")
        if not issue:
            console.print("[red]No issue provided.[/red]")
            return
        to = click.prompt("Directed to", default="Architect")
        priority = click.prompt(
            "Priority",
            type=click.Choice(["urgent", "high", "normal", "low"]),
            default="normal",
        )
        ctx.invoke(
            rfi, project=project_code, issue=issue, to=to,
            priority=priority, drawing_ref=None, spec_ref=None,
        )

    elif command == "minutes":
        meeting_type = click.prompt(
            "Meeting type",
            type=click.Choice(["oac", "subcontractor", "safety", "preconstruction", "internal"]),
            default="oac",
        )
        notes = read_notes_input(None, "Enter meeting notes")
        if not notes:
            console.print("[red]No notes provided.[/red]")
            return
        ctx.invoke(
            minutes, project=project_code, meeting_type=meeting_type,
            notes=notes, date=None, attendees=None,
        )

    elif command == "client-update":
        notes = read_notes_input(None, "Enter your project update notes")
        if not notes:
            console.print("[red]No notes provided.[/red]")
            return
        ctx.invoke(
            client_update, project=project_code, notes=notes, period="weekly",
        )

    elif command == "safety-talk":
        topic = read_notes_input(None, "What safety topic should we cover?")
        if not topic:
            console.print("[red]No topic provided.[/red]")
            return
        use_project = False
        if project_code is None:
            use_project = click.confirm("Link to a specific project?", default=False)
            if use_project:
                project_code = select_project(settings)
        ctx.invoke(
            safety_talk, topic=topic, project=project_code,
            season=None, trades=None,
        )

    elif command == "punch-list":
        area = click.prompt("Building area/zone (e.g., '2nd Floor')", default="")
        notes = read_notes_input(None, "Enter walk-through observations")
        if not notes:
            console.print("[red]No notes provided.[/red]")
            return
        ctx.invoke(
            punch_list, project=project_code, notes=notes,
            area=area or None, name=None,
        )

    elif command == "estimate-review":
        file_path = click.prompt("Path to estimate file (XLSX/CSV)")
        project_type = click.prompt(
            "Project type",
            type=click.Choice(["commercial", "healthcare", "education", "industrial", "residential"]),
            default="commercial",
        )
        sqft = click.prompt("Square footage (or press Enter to skip)", default="", show_default=False)
        ctx.invoke(
            estimate_review, project=project_code, file=file_path,
            project_type=project_type,
            sqft=int(sqft) if sqft else None,
            region="National Average",
        )

    elif command == "bid-compare":
        trade = click.prompt("Trade being bid (e.g., 'electrical')")
        bids_input = click.prompt("Bid file paths (comma-separated)")
        ctx.invoke(
            bid_compare, project=project_code, trade=trade, bids=bids_input,
        )

    elif command == "change-order":
        description = read_notes_input(None, "Describe the scope change")
        if not description:
            console.print("[red]No description provided.[/red]")
            return
        reason = click.prompt(
            "Reason",
            type=click.Choice(["owner_change", "design_error", "unforeseen_condition", "code_requirement", "value_engineering"]),
            default="owner_change",
        )
        cost_str = click.prompt("Estimated cost in dollars (or press Enter to skip)", default="", show_default=False)
        ctx.invoke(
            change_order, project=project_code, description=description,
            reason=reason,
            cost=float(cost_str) if cost_str else None,
            schedule_days=0, markup=10.0,
        )

    elif command == "schedule-analysis":
        file_path = click.prompt("Path to schedule file (PDF/XLSX)")
        notes = read_notes_input(None, "Any observations? (press Enter to skip)")
        ctx.invoke(
            schedule_analysis, project=project_code, file=file_path,
            notes=notes or None,
        )

    elif command == "submittal-status":
        file_path = click.prompt("Path to submittal log file (PDF/XLSX)")
        notes = read_notes_input(None, "Any notes? (press Enter to skip)")
        ctx.invoke(
            submittal_status, project=project_code, file=file_path,
            notes=notes or None,
        )

    elif command == "contract-review":
        file_path = click.prompt("Path to contract/insurance document (PDF/DOCX)")
        doc_type = click.prompt(
            "Document type",
            type=click.Choice(["subcontract", "prime_contract", "insurance_cert", "bond"]),
            default="subcontract",
        )
        ctx.invoke(
            contract_review, project=project_code, file=file_path,
            doc_type=doc_type,
        )

    elif command == "proposal":
        client = click.prompt("Client name")
        description = read_notes_input(None, "Describe the project opportunity")
        if not description:
            console.print("[red]No description provided.[/red]")
            return
        proposal_type = click.prompt(
            "Proposal type",
            type=click.Choice(["full", "letter", "qualification"]),
            default="full",
        )
        rfp_path = click.prompt("Path to RFP document (or press Enter to skip)", default="", show_default=False)
        ctx.invoke(
            proposal, project=project_code, client=client,
            description=description, proposal_type=proposal_type,
            rfp_file=rfp_path or None,
        )

    elif command == "budget-forecast":
        file_path = click.prompt("Path to job cost report (XLSX)")
        notes = read_notes_input(None, "Any observations? (press Enter to skip)")
        ctx.invoke(
            budget_forecast, project=project_code, file=file_path,
            notes=notes or None,
        )

    elif command == "closeout":
        notes = read_notes_input(None, "Enter closeout status notes")
        if not notes:
            console.print("[red]No notes provided.[/red]")
            return
        mode = click.prompt(
            "Mode",
            type=click.Choice(["generate", "update"]),
            default="generate",
        )
        ctx.invoke(
            closeout, project=project_code, notes=notes, mode=mode,
        )

    elif command == "lessons-learned":
        notes = read_notes_input(None, "Enter lessons learned session notes")
        if not notes:
            console.print("[red]No notes provided.[/red]")
            return
        mode = click.prompt(
            "Mode",
            type=click.Choice(["manual", "extract"]),
            default="manual",
        )
        category = click.prompt(
            "Focus category (or press Enter for all)",
            default="", show_default=False,
        )
        ctx.invoke(
            lessons_learned_cmd, project=project_code, notes=notes,
            mode=mode, category=category or None,
        )

    elif command == "case-study":
        notes = read_notes_input(None, "Enter project highlights for the case study")
        if not notes:
            console.print("[red]No notes provided.[/red]")
            return
        audience = click.prompt(
            "Target audience",
            type=click.Choice(["client", "marketing", "proposal"]),
            default="marketing",
        )
        ctx.invoke(
            case_study_cmd, project=project_code, notes=notes,
            audience=audience,
        )

    elif command == "incident-report":
        description = read_notes_input(None, "Describe what happened")
        if not description:
            console.print("[red]No description provided.[/red]")
            return
        inc_type = click.prompt(
            "Incident type",
            type=click.Choice(["near_miss", "first_aid", "recordable", "lost_time", "property_damage", "environmental"]),
        )
        inc_date = click.prompt("Date (YYYY-MM-DD, or Enter for today)", default="", show_default=False)
        inc_time = click.prompt("Time (HH:MM, or Enter to skip)", default="", show_default=False)
        ctx.invoke(
            incident_report_cmd, project=project_code,
            description=description, type=inc_type,
            date=inc_date or None, time=inc_time or None,
        )


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


# =============================================================================
# Phase 2 Skill Commands
# =============================================================================


@cli.command("estimate-review")
@click.option("--project", "-p", default=None, help="Project code (optional)")
@click.option("--file", "-f", "file", required=True, help="Path to estimate file (XLSX/CSV)")
@click.option("--type", "-t", "project_type", default="commercial", help="Project type")
@click.option("--sqft", type=int, default=None, help="Building square footage")
@click.option("--region", default="National Average", help="Cost region")
@click.pass_context
def estimate_review(
    ctx: click.Context,
    project: str | None,
    file: str,
    project_type: str,
    sqft: int | None,
    region: str,
) -> None:
    """Review a cost estimate against benchmarks and flag anomalies."""
    from kruppai.skills.estimate_reviewer import EstimateReviewerSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(EstimateReviewerSkill, settings)
    try:
        with console.status("[bold]Analyzing estimate (using Opus for precision)..."):
            result = skill.execute(
                file=file, project=project, type=project_type,
                sqft=sqft, region=region,
            )
        console.print(f"\n[green]Estimate review generated:[/green] {result.output_path}")
        console.print("[dim]XLSX analysis workbook also created.[/dim]")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error analyzing estimate:[/red] {e}")


@cli.command("bid-compare")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--trade", "-t", required=True, help="Trade being bid (e.g., 'electrical')")
@click.option("--bids", "-b", required=True, help="Comma-separated bid file paths")
@click.pass_context
def bid_compare(
    ctx: click.Context,
    project: str,
    trade: str,
    bids: str,
) -> None:
    """Compare multiple bids side-by-side and recommend best value."""
    from kruppai.skills.bid_comparison import BidComparisonSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(BidComparisonSkill, settings)
    try:
        with console.status("[bold]Analyzing bids..."):
            result = skill.execute(project=project, trade=trade, bids=bids)
        console.print(f"\n[green]Bid comparison generated:[/green] {result.output_path}")
        console.print("[dim]XLSX bid matrix also created.[/dim]")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error comparing bids:[/red] {e}")


@cli.command("change-order")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--description", "-d", required=True, help="Description of the scope change")
@click.option(
    "--reason", "-r",
    type=click.Choice(
        ["owner_change", "design_error", "unforeseen_condition", "code_requirement", "value_engineering"],
        case_sensitive=False,
    ),
    default="owner_change",
    help="Reason for change",
)
@click.option("--cost", type=float, default=None, help="Estimated cost in dollars")
@click.option("--schedule-days", type=int, default=0, help="Schedule impact in days")
@click.option("--markup", type=float, default=10.0, help="Markup percentage")
@click.pass_context
def change_order(
    ctx: click.Context,
    project: str,
    description: str,
    reason: str,
    cost: float | None,
    schedule_days: int,
    markup: float,
) -> None:
    """Generate a formal change order proposal from rough notes."""
    from kruppai.skills.change_order import ChangeOrderSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(ChangeOrderSkill, settings)
    try:
        with console.status("[bold]Generating change order..."):
            result = skill.execute(
                project=project, description=description, reason=reason,
                cost=cost, schedule_days=schedule_days, markup=markup,
            )
        console.print(f"\n[green]Change order generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating change order:[/red] {e}")


@cli.command("schedule-analysis")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--file", "-f", "file", required=True, help="Path to schedule file (PDF/XLSX)")
@click.option("--notes", "-n", default=None, help="PM observations")
@click.pass_context
def schedule_analysis(
    ctx: click.Context,
    project: str,
    file: str,
    notes: str | None,
) -> None:
    """Analyze a project schedule for variance and critical path risks."""
    from kruppai.skills.schedule_variance import ScheduleVarianceSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(ScheduleVarianceSkill, settings)
    try:
        with console.status("[bold]Analyzing schedule..."):
            result = skill.execute(project=project, file=file, notes=notes)
        console.print(f"\n[green]Schedule analysis generated:[/green] {result.output_path}")
        console.print("[dim]XLSX detail workbook also created.[/dim]")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error analyzing schedule:[/red] {e}")


@cli.command("submittal-status")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--file", "-f", "file", required=True, help="Path to submittal log (PDF/XLSX)")
@click.option("--notes", "-n", default=None, help="Additional notes")
@click.pass_context
def submittal_status(
    ctx: click.Context,
    project: str,
    file: str,
    notes: str | None,
) -> None:
    """Track submittals, flag overdue items, and generate status report."""
    from kruppai.skills.submittal_tracker import SubmittalTrackerSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(SubmittalTrackerSkill, settings)
    try:
        with console.status("[bold]Analyzing submittal log..."):
            result = skill.execute(project=project, file=file, notes=notes)
        console.print(f"\n[green]Submittal status report generated:[/green] {result.output_path}")
        console.print("[dim]XLSX tracking log also created.[/dim]")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error analyzing submittals:[/red] {e}")


@cli.command("contract-review")
@click.option("--project", "-p", default=None, help="Project code (optional)")
@click.option("--file", "-f", "file", required=True, help="Path to contract/insurance document (PDF/DOCX)")
@click.option(
    "--type", "-t", "doc_type",
    type=click.Choice(["subcontract", "prime_contract", "insurance_cert", "bond"], case_sensitive=False),
    default="subcontract",
    help="Document type",
)
@click.pass_context
def contract_review(
    ctx: click.Context,
    project: str | None,
    file: str,
    doc_type: str,
) -> None:
    """Review a contract or insurance cert for compliance and risk."""
    from kruppai.skills.contract_checker import ContractCheckerSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(ContractCheckerSkill, settings)
    try:
        with console.status("[bold]Reviewing document (using Opus for precision)..."):
            result = skill.execute(file=file, type=doc_type, project=project)
        console.print(f"\n[green]Contract review generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error reviewing document:[/red] {e}")


# =============================================================================
# Phase 3 Skill Commands
# =============================================================================


@cli.command("proposal")
@click.option("--project", "-p", default=None, help="Project code (optional)")
@click.option("--client", "-c", required=True, help="Client name")
@click.option("--description", "-d", required=True, help="Project description or opportunity notes")
@click.option(
    "--type", "-t", "proposal_type",
    type=click.Choice(["full", "letter", "qualification"], case_sensitive=False),
    default="full",
    help="Proposal type",
)
@click.option("--rfp-file", default=None, help="Path to RFP document (optional)")
@click.pass_context
def proposal(
    ctx: click.Context,
    project: str | None,
    client: str,
    description: str,
    proposal_type: str,
    rfp_file: str | None,
) -> None:
    """Generate a project proposal using Opus for premium quality."""
    from kruppai.skills.proposal_generator import ProposalGeneratorSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(ProposalGeneratorSkill, settings)
    try:
        with console.status("[bold]Generating proposal (using Opus)..."):
            result = skill.execute(
                project=project, client=client, description=description,
                proposal_type=proposal_type, rfp_file=rfp_file,
            )
        console.print(f"\n[green]Proposal generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating proposal:[/red] {e}")


@cli.command("budget-forecast")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--file", "-f", "file", required=True, help="Path to job cost report (XLSX)")
@click.option("--notes", "-n", default=None, help="PM observations")
@click.pass_context
def budget_forecast(
    ctx: click.Context,
    project: str,
    file: str,
    notes: str | None,
) -> None:
    """Generate a budget-to-actual variance report with projections."""
    from kruppai.skills.budget_forecaster import BudgetForecasterSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(BudgetForecasterSkill, settings)
    try:
        with console.status("[bold]Analyzing budget..."):
            result = skill.execute(project=project, file=file, notes=notes)
        console.print(f"\n[green]Budget forecast generated:[/green] {result.output_path}")
        console.print("[dim]XLSX workbook also created.[/dim]")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error analyzing budget:[/red] {e}")


@cli.command("closeout")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--notes", "-n", required=True, help="Closeout status notes")
@click.option(
    "--mode", "-m",
    type=click.Choice(["generate", "update"], case_sensitive=False),
    default="generate",
    help="Generate new or update existing",
)
@click.pass_context
def closeout(
    ctx: click.Context,
    project: str,
    notes: str,
    mode: str,
) -> None:
    """Assemble a project closeout package with checklist."""
    from kruppai.skills.closeout_assembler import CloseoutAssemblerSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(CloseoutAssemblerSkill, settings)
    try:
        with console.status("[bold]Assembling closeout package..."):
            result = skill.execute(project=project, notes=notes, mode=mode)
        console.print(f"\n[green]Closeout package generated:[/green] {result.output_path}")
        console.print("[dim]XLSX tracking checklist also created.[/dim]")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error assembling closeout:[/red] {e}")


@cli.command("lessons-learned")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--notes", "-n", required=True, help="Session notes or analysis guidance")
@click.option(
    "--mode", "-m",
    type=click.Choice(["manual", "extract"], case_sensitive=False),
    default="manual",
    help="Manual (from notes) or extract (from project data)",
)
@click.option("--category", default=None, help="Focus category (optional)")
@click.pass_context
def lessons_learned_cmd(
    ctx: click.Context,
    project: str,
    notes: str,
    mode: str,
    category: str | None,
) -> None:
    """Capture and structure lessons learned from project experience."""
    from kruppai.skills.lessons_learned import LessonsLearnedSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(LessonsLearnedSkill, settings)
    try:
        with console.status("[bold]Analyzing lessons learned..."):
            result = skill.execute(
                project=project, notes=notes, mode=mode, category=category,
            )
        console.print(f"\n[green]Lessons learned report generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error capturing lessons:[/red] {e}")


@cli.command("case-study")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--notes", "-n", required=True, help="Project highlights for the case study")
@click.option(
    "--audience", "-a",
    type=click.Choice(["client", "marketing", "proposal"], case_sensitive=False),
    default="marketing",
    help="Target audience",
)
@click.pass_context
def case_study_cmd(
    ctx: click.Context,
    project: str,
    notes: str,
    audience: str,
) -> None:
    """Build a marketing case study from project data."""
    from kruppai.skills.case_study import CaseStudySkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(CaseStudySkill, settings)
    try:
        with console.status("[bold]Building case study..."):
            result = skill.execute(
                project=project, notes=notes, audience=audience,
            )
        console.print(f"\n[green]Case study generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error building case study:[/red] {e}")


@cli.command("incident-report")
@click.option("--project", "-p", required=True, help="Project code")
@click.option("--description", "-d", required=True, help="Description of the incident")
@click.option(
    "--type", "-t", "type",
    required=True,
    type=click.Choice(
        ["near_miss", "first_aid", "recordable", "lost_time", "property_damage", "environmental"],
        case_sensitive=False,
    ),
    help="Incident type",
)
@click.option("--date", default=None, help="Incident date (YYYY-MM-DD, defaults to today)")
@click.option("--time", "time", default=None, help="Incident time (HH:MM)")
@click.pass_context
def incident_report_cmd(
    ctx: click.Context,
    project: str,
    description: str,
    type: str,
    date: str | None,
    time: str | None,
) -> None:
    """Document a safety incident or near miss."""
    from kruppai.skills.incident_report import IncidentReportSkill

    settings: Settings = ctx.obj["settings"]
    skill = _build_skill(IncidentReportSkill, settings)
    try:
        with console.status("[bold]Generating incident report..."):
            result = skill.execute(
                project=project, description=description,
                type=type, date=date, time=time,
            )
        console.print(f"\n[green]Incident report generated:[/green] {result.output_path}")
        console.print(
            f"[dim]Cost: ${result.cost_cents / 100:.2f} | "
            f"Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out | "
            f"Time: {result.duration_ms / 1000:.1f}s[/dim]"
        )
    except ValueError as e:
        console.print(f"[red]Validation error:[/red] {e}")
    except Exception as e:
        console.print(f"[red]Error generating incident report:[/red] {e}")


if __name__ == "__main__":
    cli()
