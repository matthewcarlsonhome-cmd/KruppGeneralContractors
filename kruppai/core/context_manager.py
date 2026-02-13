"""Loads project context from database for prompt assembly.

A ProjectContext contains everything a skill needs to generate a document:
project details, team, subs, open action items, recent documents, and company info.
"""

import sqlite3
from dataclasses import dataclass, field

from kruppai.core.config import Settings
from kruppai.core.database import ProjectNotFoundError, get_db


@dataclass
class ProjectContext:
    """Complete context for a project, assembled from database."""

    project: dict
    team: list[dict] = field(default_factory=list)
    subcontractors: list[dict] = field(default_factory=list)
    open_action_items: list[dict] = field(default_factory=list)
    recent_documents: list[dict] = field(default_factory=list)
    company: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert list of sqlite3.Row to list of dicts."""
    return [dict(r) for r in rows]


class ContextManager:
    """Loads project context from the database."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def load(self, project_id: int) -> ProjectContext:
        """Load full project context by project ID.

        Raises:
            ProjectNotFoundError: If project_id doesn't exist.
        """
        with get_db(self.settings) as conn:
            return self._load_from_conn(conn, project_id)

    def load_by_code(self, project_code: str) -> ProjectContext:
        """Load full project context by project code (e.g., 'KRUPP-2026-003').

        Raises:
            ProjectNotFoundError: If project_code doesn't exist.
        """
        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "SELECT id FROM projects WHERE project_code = ?",
                (project_code,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ProjectNotFoundError(
                    f"Project with code '{project_code}' not found"
                )
            return self._load_from_conn(conn, row["id"])

    def get_project_list(self) -> list[dict]:
        """Return list of all active projects for CLI selection."""
        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "SELECT id, project_code, name, client_name, status, "
                "current_percent_complete "
                "FROM projects "
                "WHERE is_archived = 0 "
                "ORDER BY project_code"
            )
            return _rows_to_dicts(cursor.fetchall())

    def _load_from_conn(
        self, conn: sqlite3.Connection, project_id: int
    ) -> ProjectContext:
        """Load full context using an existing connection."""
        # Project record
        cursor = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        project_row = cursor.fetchone()
        if project_row is None:
            raise ProjectNotFoundError(
                f"Project with id {project_id} not found"
            )
        project = _row_to_dict(project_row)

        # Team members
        cursor = conn.execute(
            "SELECT tm.*, pt.project_role, pt.is_primary "
            "FROM team_members tm "
            "JOIN project_team pt ON tm.id = pt.team_member_id "
            "WHERE pt.project_id = ? AND pt.removed_date IS NULL "
            "ORDER BY pt.is_primary DESC",
            (project_id,),
        )
        team = _rows_to_dicts(cursor.fetchall())

        # Subcontractors
        cursor = conn.execute(
            "SELECT s.*, ps.contract_value_cents, ps.scope_description, "
            "ps.contract_status, ps.change_order_total_cents "
            "FROM subcontractors s "
            "JOIN project_subcontractors ps ON s.id = ps.subcontractor_id "
            "WHERE ps.project_id = ?",
            (project_id,),
        )
        subcontractors = _rows_to_dicts(cursor.fetchall())

        # Open action items
        cursor = conn.execute(
            "SELECT * FROM action_items "
            "WHERE project_id = ? AND status IN ('open', 'in_progress') "
            "ORDER BY "
            "CASE priority "
            "  WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 "
            "  WHEN 'normal' THEN 3 WHEN 'low' THEN 4 END, "
            "due_date",
            (project_id,),
        )
        open_action_items = _rows_to_dicts(cursor.fetchall())

        # Recent documents (last 10)
        cursor = conn.execute(
            "SELECT * FROM generated_documents "
            "WHERE project_id = ? AND is_current = 1 "
            "ORDER BY created_at DESC LIMIT 10",
            (project_id,),
        )
        recent_documents = _rows_to_dicts(cursor.fetchall())

        # Company profile
        cursor = conn.execute("SELECT * FROM company LIMIT 1")
        company_row = cursor.fetchone()
        company = _row_to_dict(company_row) if company_row else {}

        # Stats
        stats = self._calculate_stats(conn, project_id)

        return ProjectContext(
            project=project,
            team=team,
            subcontractors=subcontractors,
            open_action_items=open_action_items,
            recent_documents=recent_documents,
            company=company,
            stats=stats,
        )

    def _calculate_stats(
        self, conn: sqlite3.Connection, project_id: int
    ) -> dict:
        """Calculate project statistics from database."""
        stats: dict = {}

        cursor = conn.execute(
            "SELECT COUNT(*) FROM rfis WHERE project_id = ?",
            (project_id,),
        )
        stats["total_rfis"] = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COUNT(*) FROM rfis "
            "WHERE project_id = ? AND status = 'submitted'",
            (project_id,),
        )
        stats["open_rfis"] = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COUNT(*) FROM change_orders WHERE project_id = ?",
            (project_id,),
        )
        stats["total_cos"] = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COALESCE(SUM(total_with_markup_cents), 0) "
            "FROM change_orders "
            "WHERE project_id = ? AND status = 'approved'",
            (project_id,),
        )
        stats["approved_co_value_cents"] = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COUNT(*) FROM action_items "
            "WHERE project_id = ? AND status IN ('open', 'in_progress')",
            (project_id,),
        )
        stats["open_action_items"] = cursor.fetchone()[0]

        cursor = conn.execute(
            "SELECT COUNT(*) FROM daily_reports WHERE project_id = ?",
            (project_id,),
        )
        stats["total_daily_reports"] = cursor.fetchone()[0]

        return stats
