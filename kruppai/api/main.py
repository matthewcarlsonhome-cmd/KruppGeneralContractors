"""KruppAI REST API — FastAPI backend.

Exposes all 18 skills via REST endpoints.
Deployment: Render (Docker container) or any ASGI host.
"""

from __future__ import annotations

import importlib
import json
import os
import tempfile
from datetime import date as dt_date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kruppai.core.config import Settings
from kruppai.core.database import get_db, init_db

app = FastAPI(
    title="KruppAI API",
    version="1.0.0",
    description="AI-powered document generation for construction contractors",
)

# CORS — allow all for development, restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files — serve the single-page frontend
# ---------------------------------------------------------------------------

_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
async def root() -> FileResponse:
    """Serve the main frontend HTML page."""
    return FileResponse(os.path.join(_static_dir, "index.html"))


# ---------------------------------------------------------------------------
# Skill registry — maps skill_name to (module_path, class_name)
# ---------------------------------------------------------------------------

SKILL_MAP: dict[str, tuple[str, str]] = {
    "daily_report": ("kruppai.skills.daily_report", "DailyReportSkill"),
    "rfi_generator": ("kruppai.skills.rfi_generator", "RfiGeneratorSkill"),
    "meeting_minutes": ("kruppai.skills.meeting_minutes", "MeetingMinutesSkill"),
    "client_update": ("kruppai.skills.client_update", "ClientUpdateSkill"),
    "safety_talk": ("kruppai.skills.safety_talk", "SafetyTalkSkill"),
    "punch_list": ("kruppai.skills.punch_list", "PunchListSkill"),
    "estimate_reviewer": ("kruppai.skills.estimate_reviewer", "EstimateReviewerSkill"),
    "bid_comparison": ("kruppai.skills.bid_comparison", "BidComparisonSkill"),
    "change_order": ("kruppai.skills.change_order", "ChangeOrderSkill"),
    "schedule_variance": (
        "kruppai.skills.schedule_variance",
        "ScheduleVarianceSkill",
    ),
    "submittal_tracker": (
        "kruppai.skills.submittal_tracker",
        "SubmittalTrackerSkill",
    ),
    "contract_checker": ("kruppai.skills.contract_checker", "ContractCheckerSkill"),
    "proposal_generator": (
        "kruppai.skills.proposal_generator",
        "ProposalGeneratorSkill",
    ),
    "budget_forecaster": (
        "kruppai.skills.budget_forecaster",
        "BudgetForecasterSkill",
    ),
    "closeout_assembler": (
        "kruppai.skills.closeout_assembler",
        "CloseoutAssemblerSkill",
    ),
    "lessons_learned": ("kruppai.skills.lessons_learned", "LessonsLearnedSkill"),
    "case_study": ("kruppai.skills.case_study", "CaseStudySkill"),
    "incident_report": ("kruppai.skills.incident_report", "IncidentReportSkill"),
}

# Human-friendly metadata for skills that may not be importable yet
# (Phase 3 skills are listed in the schema but may not have modules).
SKILL_METADATA: dict[str, dict] = {
    "daily_report": {
        "display_name": "Daily Field Report",
        "description": "Transform field notes into a professional daily report",
        "phase": 1,
        "requires_file": False,
        "required_params": ["project", "notes"],
    },
    "rfi_generator": {
        "display_name": "RFI Generator",
        "description": "Transform issue descriptions into formal RFI documents",
        "phase": 1,
        "requires_file": False,
        "required_params": ["project", "issue"],
    },
    "meeting_minutes": {
        "display_name": "Meeting Minutes",
        "description": "Transform meeting notes into formatted minutes with action tracking",
        "phase": 1,
        "requires_file": False,
        "required_params": ["project", "type", "notes"],
    },
    "client_update": {
        "display_name": "Client Update Letter",
        "description": "Generate a professional project status letter for the client",
        "phase": 1,
        "requires_file": False,
        "required_params": ["project", "notes"],
    },
    "safety_talk": {
        "display_name": "Toolbox Safety Talk",
        "description": "Generate a safety talk document on any construction topic",
        "phase": 1,
        "requires_file": False,
        "required_params": ["topic"],
    },
    "punch_list": {
        "display_name": "Punch List Generator",
        "description": "Transform walk-through notes into organized punch lists",
        "phase": 1,
        "requires_file": False,
        "required_params": ["project", "notes"],
    },
    "estimate_reviewer": {
        "display_name": "Estimate Reviewer",
        "description": "Review a cost estimate against benchmarks and flag anomalies",
        "phase": 2,
        "requires_file": True,
        "required_params": ["file"],
    },
    "bid_comparison": {
        "display_name": "Bid Comparison",
        "description": "Compare multiple bids side-by-side and recommend best value",
        "phase": 2,
        "requires_file": True,
        "required_params": ["project", "trade", "bids"],
    },
    "change_order": {
        "display_name": "Change Order Builder",
        "description": "Generate a formal change order proposal from rough notes",
        "phase": 2,
        "requires_file": False,
        "required_params": ["project", "description", "reason"],
    },
    "schedule_variance": {
        "display_name": "Schedule Variance Analyzer",
        "description": "Analyze a project schedule for variance and critical path risks",
        "phase": 2,
        "requires_file": True,
        "required_params": ["project", "file"],
    },
    "submittal_tracker": {
        "display_name": "Submittal Tracker",
        "description": "Analyze a submittal log and flag overdue or at-risk items",
        "phase": 2,
        "requires_file": True,
        "required_params": ["project", "file"],
    },
    "contract_checker": {
        "display_name": "Contract & Insurance Checker",
        "description": "Review a contract or insurance cert for compliance and risk",
        "phase": 2,
        "requires_file": True,
        "required_params": ["file"],
    },
    "proposal_generator": {
        "display_name": "Proposal Generator",
        "description": "Generate a professional construction proposal from project details",
        "phase": 3,
        "requires_file": False,
        "required_params": ["project", "notes"],
    },
    "budget_forecaster": {
        "display_name": "Budget Forecaster",
        "description": "Forecast project budget and identify cost risks",
        "phase": 3,
        "requires_file": True,
        "required_params": ["project", "file"],
    },
    "closeout_assembler": {
        "display_name": "Closeout Assembler",
        "description": "Assemble project closeout documentation package",
        "phase": 3,
        "requires_file": False,
        "required_params": ["project"],
    },
    "lessons_learned": {
        "display_name": "Lessons Learned",
        "description": "Compile and structure project lessons learned",
        "phase": 3,
        "requires_file": False,
        "required_params": ["project", "notes"],
    },
    "case_study": {
        "display_name": "Case Study",
        "description": "Generate a marketing case study from project data",
        "phase": 3,
        "requires_file": False,
        "required_params": ["project", "notes"],
    },
    "incident_report": {
        "display_name": "Incident Report",
        "description": "Generate a formal incident report from field notes",
        "phase": 3,
        "requires_file": False,
        "required_params": ["project", "notes"],
    },
}


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class SkillRequest(BaseModel):
    """Request body for executing a skill."""

    skill_name: str
    project_code: str | None = None
    parameters: dict = {}


class SkillResponse(BaseModel):
    """Response from a skill execution."""

    success: bool
    output_path: str | None = None
    download_url: str | None = None
    cost_cents: int = 0
    tokens_used: int = 0
    error: str | None = None


class ProjectCreate(BaseModel):
    """Request body for creating a new project."""

    project_code: str
    name: str
    client_name: str | None = None
    project_type: str = "commercial"
    status: str = "active"
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None


class ProjectResponse(BaseModel):
    """Response for a project listing entry."""

    id: int
    project_code: str
    name: str
    client_name: str | None
    status: str
    percent_complete: float


class StatusResponse(BaseModel):
    """Dashboard status response."""

    today_cost_cents: int
    month_cost_cents: int
    daily_limit_cents: int
    monthly_limit_cents: int
    recent_documents: list[dict]


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_settings() -> Settings:
    """Resolve application settings from environment / .env file."""
    try:
        return Settings()
    except Exception:
        return Settings(_env_file=None)


def _get_db_factory(settings: Settings):
    """Return a callable that yields db connections for the AnthropicClient."""
    from kruppai.core.database import get_db as _get_db

    def factory():
        return _get_db(settings)

    return factory


def _build_skill(skill_class: type, settings: Settings):
    """Instantiate a skill with all its dependencies.

    Mirrors the pattern used in kruppai.cli.main._build_skill.
    """
    from kruppai.core.api_client import AnthropicClient
    from kruppai.core.context_manager import ContextManager
    from kruppai.core.knowledge_base import KnowledgeBase
    from kruppai.core.output_formatter import OutputFormatter

    return skill_class(
        settings=settings,
        api_client=AnthropicClient(settings, db_conn_factory=_get_db_factory(settings)),
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


def _resolve_skill_class(skill_name: str) -> type:
    """Dynamically import and return the skill class for *skill_name*.

    Raises:
        HTTPException: If the skill name is unknown or the module cannot
        be imported (e.g. Phase 3 skill not yet implemented).
    """
    if skill_name not in SKILL_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown skill '{skill_name}'. "
            f"Available: {sorted(SKILL_MAP.keys())}",
        )

    module_path, class_name = SKILL_MAP[skill_name]
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        raise HTTPException(
            status_code=501,
            detail=f"Skill '{skill_name}' is registered but its module "
            f"({module_path}) has not been implemented yet.",
        )

    skill_class = getattr(module, class_name, None)
    if skill_class is None:
        raise HTTPException(
            status_code=501,
            detail=f"Class '{class_name}' not found in module '{module_path}'.",
        )

    return skill_class


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize database and output directories on server start."""
    settings = get_settings()
    settings.ensure_directories()
    init_db(settings)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
async def health() -> dict:
    """Health check endpoint."""
    settings = get_settings()
    db_exists = settings.db_path.exists()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": "connected" if db_exists else "missing",
        "output_dir": str(settings.output_dir),
    }


@app.get("/api/v1/config-check")
async def config_check() -> dict:
    """Check configuration status — helps frontend show setup issues."""
    settings = get_settings()
    api_key = settings.anthropic_api_key or ""
    has_key = bool(api_key and api_key != "sk-ant-api03-your-key-here")
    db_exists = settings.db_path.exists()
    issues: list[str] = []
    if not has_key:
        issues.append(
            "Anthropic API key is not configured. Add ANTHROPIC_API_KEY=sk-ant-... to your .env file."
        )
    if not db_exists:
        issues.append(
            "Database not found. Run 'kruppai init' or restart the server."
        )
    return {
        "api_key_configured": has_key,
        "database_ready": db_exists,
        "issues": issues,
        "status": "ready" if (has_key and db_exists) else "needs_setup",
    }


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@app.get("/api/v1/projects", response_model=list[ProjectResponse])
async def list_projects(settings: Settings = Depends(get_settings)) -> list[dict]:
    """List all active (non-archived) projects."""
    try:
        with get_db(settings) as conn:
            cursor = conn.execute(
                "SELECT id, project_code, name, client_name, status, "
                "current_percent_complete "
                "FROM projects WHERE is_archived = 0 "
                "ORDER BY project_code"
            )
            rows = cursor.fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}. Run 'kruppai init' if the DB is missing.",
        )

    return [
        {
            "id": row["id"],
            "project_code": row["project_code"],
            "name": row["name"],
            "client_name": row["client_name"],
            "status": row["status"],
            "percent_complete": row["current_percent_complete"] or 0.0,
        }
        for row in rows
    ]


@app.get("/api/v1/projects/{project_code}/stats")
async def project_stats(
    project_code: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Return live project stats for the dashboard command center."""
    try:
        with get_db(settings) as conn:
            # Resolve project_id
            cursor = conn.execute(
                "SELECT id, name, address, latitude, longitude "
                "FROM projects WHERE project_code = ?",
                (project_code,),
            )
            proj = cursor.fetchone()
            if proj is None:
                raise HTTPException(status_code=404, detail="Project not found.")
            pid = proj["id"]

            # Open RFIs
            cursor = conn.execute(
                "SELECT COUNT(*) FROM rfis "
                "WHERE project_id = ? AND status IN ('draft', 'submitted')",
                (pid,),
            )
            open_rfis = cursor.fetchone()[0]

            # Overdue RFIs
            today = dt_date.today().isoformat()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM rfis "
                "WHERE project_id = ? AND status = 'submitted' "
                "AND response_due_date IS NOT NULL AND response_due_date < ?",
                (pid, today),
            )
            overdue_rfis = cursor.fetchone()[0]

            # Pending COs
            cursor = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(total_with_markup_cents), 0) "
                "FROM change_orders "
                "WHERE project_id = ? AND status IN ('draft', 'submitted')",
                (pid,),
            )
            co_row = cursor.fetchone()
            pending_cos = co_row[0]
            pending_co_cents = co_row[1]

            # Daily report count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM daily_reports WHERE project_id = ?",
                (pid,),
            )
            daily_report_count = cursor.fetchone()[0]

            # Open action items
            cursor = conn.execute(
                "SELECT COUNT(*) FROM action_items "
                "WHERE project_id = ? AND status IN ('open', 'in_progress')",
                (pid,),
            )
            open_action_items = cursor.fetchone()[0]

            # Open punch items
            cursor = conn.execute(
                "SELECT COUNT(*) FROM punch_items "
                "WHERE project_id = ? AND status != 'complete'",
                (pid,),
            )
            open_punch_items = cursor.fetchone()[0]

            # Team and sub counts
            cursor = conn.execute(
                "SELECT COUNT(*) FROM project_team "
                "WHERE project_id = ? AND removed_date IS NULL",
                (pid,),
            )
            team_count = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM project_subcontractors "
                "WHERE project_id = ?",
                (pid,),
            )
            sub_count = cursor.fetchone()[0]

            # Last client update
            cursor = conn.execute(
                "SELECT created_at FROM generated_documents "
                "WHERE project_id = ? AND skill_name = 'client_update' "
                "ORDER BY created_at DESC LIMIT 1",
                (pid,),
            )
            row = cursor.fetchone()
            last_client_update = row["created_at"] if row else None

            # Next auto-numbers
            cursor = conn.execute(
                "SELECT COALESCE(MAX(report_number), 0) + 1 "
                "FROM daily_reports WHERE project_id = ?",
                (pid,),
            )
            next_daily = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COALESCE(MAX(rfi_number), 0) + 1 "
                "FROM rfis WHERE project_id = ?",
                (pid,),
            )
            next_rfi = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COALESCE(MAX(co_number), 0) + 1 "
                "FROM change_orders WHERE project_id = ?",
                (pid,),
            )
            next_co = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COALESCE(MAX(incident_number), 0) + 1 "
                "FROM incident_reports WHERE project_id = ?",
                (pid,),
            )
            next_incident = cursor.fetchone()[0]

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return {
        "project_code": project_code,
        "address": proj["address"] or "",
        "open_rfis": open_rfis,
        "overdue_rfis": overdue_rfis,
        "pending_cos": pending_cos,
        "pending_co_cents": pending_co_cents,
        "daily_report_count": daily_report_count,
        "open_action_items": open_action_items,
        "open_punch_items": open_punch_items,
        "team_count": team_count,
        "sub_count": sub_count,
        "last_client_update": last_client_update,
        "next_daily_report": next_daily,
        "next_rfi": next_rfi,
        "next_co": next_co,
        "next_incident": next_incident,
    }


@app.get("/api/v1/projects/{project_code}/activity")
async def project_activity(
    project_code: str,
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    """Return recent activity feed for a project."""
    try:
        with get_db(settings) as conn:
            cursor = conn.execute(
                "SELECT id FROM projects WHERE project_code = ?",
                (project_code,),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Project not found.")
            pid = row["id"]

            events: list[dict] = []

            # Recent documents
            cursor = conn.execute(
                "SELECT skill_name, file_name, created_at "
                "FROM generated_documents "
                "WHERE project_id = ? AND is_current = 1 "
                "ORDER BY created_at DESC LIMIT 10",
                (pid,),
            )
            for r in cursor.fetchall():
                events.append({
                    "date": r["created_at"],
                    "type": "document",
                    "skill": r["skill_name"],
                    "text": f"{r['file_name']} generated",
                })

            # Recent RFIs
            cursor = conn.execute(
                "SELECT rfi_number, subject, status, created_at, "
                "response_due_date "
                "FROM rfis WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT 5",
                (pid,),
            )
            for r in cursor.fetchall():
                due = ""
                if r["response_due_date"] and r["status"] == "submitted":
                    due = f" (due {r['response_due_date']})"
                events.append({
                    "date": r["created_at"],
                    "type": "rfi",
                    "text": f"RFI #{r['rfi_number']} {r['status']}{due}: {r['subject']}",
                })

            # Recent COs
            cursor = conn.execute(
                "SELECT co_number, title, status, "
                "total_with_markup_cents, created_at "
                "FROM change_orders WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT 5",
                (pid,),
            )
            for r in cursor.fetchall():
                amt = ""
                if r["total_with_markup_cents"]:
                    amt = f" (${r['total_with_markup_cents'] / 100:,.0f})"
                events.append({
                    "date": r["created_at"],
                    "type": "co",
                    "text": f"CO #{r['co_number']} {r['status']}{amt}: {r['title']}",
                })

            # Recent action items
            cursor = conn.execute(
                "SELECT description, assigned_to, status, created_at "
                "FROM action_items WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT 5",
                (pid,),
            )
            for r in cursor.fetchall():
                events.append({
                    "date": r["created_at"],
                    "type": "action",
                    "text": f"Action item ({r['status']}): {r['description'][:60]}",
                })

            # Sort all by date desc
            events.sort(key=lambda e: e.get("date", ""), reverse=True)
            return events[:20]

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")


@app.get("/api/v1/documents/all")
async def all_documents(
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    """Return all documents across all projects (My Documents concept)."""
    try:
        with get_db(settings) as conn:
            cursor = conn.execute(
                "SELECT gd.id, gd.skill_name, gd.file_name, "
                "gd.document_type, gd.created_at, gd.project_id, "
                "p.project_code, p.name as project_name "
                "FROM generated_documents gd "
                "LEFT JOIN projects p ON gd.project_id = p.id "
                "WHERE gd.is_current = 1 "
                "ORDER BY gd.created_at DESC LIMIT 50"
            )
            return [
                {
                    "id": r["id"],
                    "skill_name": r["skill_name"],
                    "file_name": r["file_name"],
                    "document_type": r["document_type"],
                    "created_at": r["created_at"],
                    "project_code": r["project_code"],
                    "project_name": r["project_name"],
                    "download_url": f"/api/v1/documents/{r['id']}/download",
                }
                for r in cursor.fetchall()
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")


@app.post("/api/v1/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Create a new project."""
    try:
        with get_db(settings) as conn:
            cursor = conn.execute(
                "INSERT INTO projects "
                "(project_code, name, client_name, project_type, status, "
                "address, latitude, longitude) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    project.project_code,
                    project.name,
                    project.client_name,
                    project.project_type,
                    project.status,
                    project.address,
                    project.latitude,
                    project.longitude,
                ),
            )
            project_id = cursor.lastrowid
    except Exception as exc:
        if "UNIQUE constraint" in str(exc):
            raise HTTPException(
                status_code=409,
                detail=f"Project code '{project.project_code}' already exists.",
            )
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return {
        "id": project_id,
        "project_code": project.project_code,
        "name": project.name,
        "client_name": project.client_name,
        "status": project.status,
        "percent_complete": 0.0,
    }


# ---------------------------------------------------------------------------
# Skills — listing
# ---------------------------------------------------------------------------


@app.get("/api/v1/skills")
async def list_skills() -> list[dict]:
    """List all available skills with metadata.

    For each skill, reports whether its implementation module is present
    so the frontend can grey-out not-yet-available skills.
    """
    results: list[dict] = []
    for skill_name, (module_path, class_name) in SKILL_MAP.items():
        meta = SKILL_METADATA.get(skill_name, {})
        # Check if the module is importable
        available = True
        try:
            importlib.import_module(module_path)
        except ModuleNotFoundError:
            available = False

        results.append(
            {
                "skill_name": skill_name,
                "display_name": meta.get("display_name", skill_name),
                "description": meta.get("description", ""),
                "phase": meta.get("phase", 0),
                "requires_file": meta.get("requires_file", False),
                "required_params": meta.get("required_params", []),
                "available": available,
            }
        )

    return sorted(results, key=lambda s: (s["phase"], s["skill_name"]))


# ---------------------------------------------------------------------------
# Skills — execution (JSON parameters)
# ---------------------------------------------------------------------------


@app.post("/api/v1/skills/{skill_name}/execute", response_model=SkillResponse)
async def execute_skill(
    skill_name: str,
    request: SkillRequest,
    settings: Settings = Depends(get_settings),
) -> SkillResponse:
    """Execute any skill via API.

    The ``parameters`` dict is forwarded as **kwargs to the skill's
    ``execute()`` method.  Include ``project`` (project code) inside
    ``parameters`` or use the top-level ``project_code`` field.
    """
    skill_class = _resolve_skill_class(skill_name)

    # Merge project_code into parameters if provided at top level
    params = dict(request.parameters)
    if request.project_code and "project" not in params:
        params["project"] = request.project_code

    # Check API key before attempting execution
    if not settings.anthropic_api_key or settings.anthropic_api_key == "sk-ant-api03-your-key-here":
        return SkillResponse(
            success=False,
            error="Anthropic API key is not configured. Add your key to the .env file and restart the server.",
        )

    skill = _build_skill(skill_class, settings)
    try:
        result = skill.execute(**params)
    except ValueError as exc:
        return SkillResponse(success=False, error=f"Validation error: {exc}")
    except FileNotFoundError as exc:
        return SkillResponse(success=False, error=f"File not found: {exc}")
    except Exception as exc:
        error_msg = str(exc)
        if "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
            error_msg = (
                "API authentication failed. Please check that your ANTHROPIC_API_KEY "
                "in the .env file is valid and has not expired."
            )
        elif "rate_limit" in error_msg.lower() or "429" in error_msg:
            error_msg = "API rate limit reached. Please wait a moment and try again."
        elif "CostLimitExceeded" in error_msg or "cost limit" in error_msg.lower():
            error_msg = f"Cost limit reached: {exc}"
        return SkillResponse(success=False, error=error_msg)

    return SkillResponse(
        success=True,
        output_path=str(result.output_path),
        download_url=f"/api/v1/documents/path/{result.output_path.name}",
        cost_cents=result.cost_cents,
        tokens_used=result.input_tokens + result.output_tokens,
    )


# ---------------------------------------------------------------------------
# Skills — execution with file upload
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/skills/{skill_name}/execute-with-file",
    response_model=SkillResponse,
)
async def execute_skill_with_file(
    skill_name: str,
    file: UploadFile = File(...),
    project_code: str = Form(None),
    parameters: str = Form("{}"),
    settings: Settings = Depends(get_settings),
) -> SkillResponse:
    """Execute a skill that requires a file upload.

    The uploaded file is written to a temporary location and its path is
    passed as the ``file`` parameter to the skill's ``execute()`` method.
    """
    # Check API key before attempting execution
    if not settings.anthropic_api_key or settings.anthropic_api_key == "sk-ant-api03-your-key-here":
        return SkillResponse(
            success=False,
            error="Anthropic API key is not configured. Add your key to the .env file and restart the server.",
        )

    skill_class = _resolve_skill_class(skill_name)

    # Parse JSON parameters from the form field
    try:
        params: dict = json.loads(parameters)
    except json.JSONDecodeError:
        return SkillResponse(
            success=False,
            error="Invalid JSON in 'parameters' form field.",
        )

    if project_code and "project" not in params:
        params["project"] = project_code

    # Save uploaded file to a temp directory preserving original extension
    suffix = Path(file.filename).suffix if file.filename else ""
    tmp_dir = tempfile.mkdtemp(prefix="kruppai_upload_")
    tmp_path = Path(tmp_dir) / (file.filename or f"upload{suffix}")
    try:
        contents = await file.read()
        tmp_path.write_bytes(contents)
    except Exception as exc:
        return SkillResponse(
            success=False,
            error=f"Failed to save uploaded file: {exc}",
        )

    params["file"] = str(tmp_path)

    skill = _build_skill(skill_class, settings)
    try:
        result = skill.execute(**params)
    except ValueError as exc:
        return SkillResponse(success=False, error=f"Validation error: {exc}")
    except FileNotFoundError as exc:
        return SkillResponse(success=False, error=f"File not found: {exc}")
    except Exception as exc:
        error_msg = str(exc)
        if "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
            error_msg = (
                "API authentication failed. Please check that your ANTHROPIC_API_KEY "
                "in the .env file is valid and has not expired."
            )
        elif "rate_limit" in error_msg.lower() or "429" in error_msg:
            error_msg = "API rate limit reached. Please wait a moment and try again."
        return SkillResponse(success=False, error=error_msg)

    return SkillResponse(
        success=True,
        output_path=str(result.output_path),
        download_url=f"/api/v1/documents/path/{result.output_path.name}",
        cost_cents=result.cost_cents,
        tokens_used=result.input_tokens + result.output_tokens,
    )


# ---------------------------------------------------------------------------
# Document download — by database ID
# ---------------------------------------------------------------------------


@app.get("/api/v1/documents/{doc_id}/download")
async def download_document(
    doc_id: int,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Download a generated document by its database ID."""
    try:
        with get_db(settings) as conn:
            cursor = conn.execute(
                "SELECT file_path, file_name, document_type "
                "FROM generated_documents WHERE id = ?",
                (doc_id,),
            )
            row = cursor.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document with id {doc_id} not found.",
        )

    file_path = Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found on disk: {file_path}",
        )

    media_type_map = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    media_type = media_type_map.get(
        row["document_type"], "application/octet-stream"
    )

    return FileResponse(
        path=str(file_path),
        filename=row["file_name"],
        media_type=media_type,
    )


# ---------------------------------------------------------------------------
# Document download — by filename (convenience for frontend)
# ---------------------------------------------------------------------------


@app.get("/api/v1/documents/path/{filename}")
async def download_document_by_name(
    filename: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Download a generated document by filename from the output directory."""
    # Search in the configured output directory
    file_path = settings.output_dir / filename
    if not file_path.exists():
        # Try a recursive search in output_dir
        matches = list(settings.output_dir.rglob(filename))
        if not matches:
            raise HTTPException(
                status_code=404,
                detail=f"File '{filename}' not found in output directory.",
            )
        file_path = matches[0]

    suffix = file_path.suffix.lstrip(".")
    media_type_map = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    media_type = media_type_map.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )


# ---------------------------------------------------------------------------
# Status / dashboard
# ---------------------------------------------------------------------------


@app.get("/api/v1/status", response_model=StatusResponse)
async def get_status(
    settings: Settings = Depends(get_settings),
) -> StatusResponse:
    """Dashboard data: costs, usage, recent documents."""
    today = dt_date.today().isoformat()
    month_start = today[:7] + "-01"

    try:
        with get_db(settings) as conn:
            # Today's cost
            cursor = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
                "WHERE created_at >= ? AND success = 1",
                (today,),
            )
            today_cost: int = cursor.fetchone()[0]

            # This month's cost
            cursor = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) FROM api_usage "
                "WHERE created_at >= ? AND success = 1",
                (month_start,),
            )
            month_cost: int = cursor.fetchone()[0]

            # Recent documents (last 10)
            cursor = conn.execute(
                "SELECT id, skill_name, file_name, document_type, created_at "
                "FROM generated_documents "
                "WHERE is_current = 1 "
                "ORDER BY created_at DESC LIMIT 10"
            )
            recent_rows = cursor.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    recent_documents = [
        {
            "id": row["id"],
            "skill_name": row["skill_name"],
            "file_name": row["file_name"],
            "document_type": row["document_type"],
            "created_at": row["created_at"],
            "download_url": f"/api/v1/documents/{row['id']}/download",
        }
        for row in recent_rows
    ]

    return StatusResponse(
        today_cost_cents=today_cost,
        month_cost_cents=month_cost,
        daily_limit_cents=settings.daily_cost_limit_cents,
        monthly_limit_cents=settings.monthly_cost_limit_cents,
        recent_documents=recent_documents,
    )
