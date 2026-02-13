"""Tests for kruppai.core.context_manager."""

import pytest

from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager, ProjectContext
from kruppai.core.database import ProjectNotFoundError


class TestContextManager:
    def test_load_full_context(self, seeded_db: Settings) -> None:
        """With seeded DB, returns ProjectContext with all fields populated."""
        cm = ContextManager(seeded_db)
        ctx = cm.load(1)

        assert isinstance(ctx, ProjectContext)
        assert ctx.project["project_code"] == "KRUPP-2026-TEST"
        assert ctx.project["client_name"] == "Regional Health Partners"
        assert len(ctx.team) == 3
        assert len(ctx.subcontractors) == 2
        assert len(ctx.open_action_items) == 5
        assert isinstance(ctx.company, dict)
        assert ctx.company["name"] == "Krupp General Contractors"

    def test_load_empty_project(self, test_db: Settings) -> None:
        """New project with no docs/subs returns valid context with empty lists."""
        # Insert a bare project
        from kruppai.core.database import get_db

        with get_db(test_db) as conn:
            conn.execute(
                "INSERT INTO company (name) VALUES (?)",
                ("Test Company",),
            )
            conn.execute(
                "INSERT INTO projects (project_code, name, status) "
                "VALUES (?, ?, ?)",
                ("TEST-001", "Empty Project", "active"),
            )

        cm = ContextManager(test_db)
        ctx = cm.load(1)
        assert ctx.project["project_code"] == "TEST-001"
        assert ctx.team == []
        assert ctx.subcontractors == []
        assert ctx.open_action_items == []
        assert ctx.recent_documents == []

    def test_stats_calculation(self, seeded_db: Settings) -> None:
        """Stats calculated correctly from DB."""
        cm = ContextManager(seeded_db)
        ctx = cm.load(1)

        assert ctx.stats["total_rfis"] == 0  # No RFIs seeded
        assert ctx.stats["open_action_items"] == 5
        assert ctx.stats["total_daily_reports"] == 0

    def test_project_not_found(self, test_db: Settings) -> None:
        """Invalid project_id raises ProjectNotFoundError."""
        cm = ContextManager(test_db)
        with pytest.raises(ProjectNotFoundError):
            cm.load(99999)

    def test_load_by_code(self, seeded_db: Settings) -> None:
        """Can look up by project code string."""
        cm = ContextManager(seeded_db)
        ctx = cm.load_by_code("KRUPP-2026-TEST")
        assert ctx.project["name"] == "City Center Medical Office Building"

    def test_load_by_code_not_found(self, test_db: Settings) -> None:
        """Invalid code raises ProjectNotFoundError."""
        cm = ContextManager(test_db)
        with pytest.raises(ProjectNotFoundError):
            cm.load_by_code("NONEXISTENT-CODE")

    def test_get_project_list(self, seeded_db: Settings) -> None:
        """Project list returns active projects."""
        cm = ContextManager(seeded_db)
        projects = cm.get_project_list()
        assert len(projects) == 1
        assert projects[0]["project_code"] == "KRUPP-2026-TEST"

    def test_get_project_list_empty(self, test_db: Settings) -> None:
        """Empty database returns empty list."""
        cm = ContextManager(test_db)
        projects = cm.get_project_list()
        assert projects == []
