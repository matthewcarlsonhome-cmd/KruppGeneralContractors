"""Tests for the Closeout Assembler skill."""

import json
from unittest.mock import MagicMock

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.closeout_assembler import CloseoutAssemblerSkill


MOCK_CLOSEOUT_JSON = json.dumps({
    "cover_letter_text": "Dear Dr. Foster,\n\nWe are pleased to present the "
    "closeout package for the City Center Medical Office Building project. "
    "We appreciate the collaborative partnership throughout construction.",
    "status_summary": {
        "total_items": 25,
        "complete": 10,
        "in_progress": 8,
        "not_started": 5,
        "not_applicable": 2,
        "percent_complete": 40.0,
    },
    "checklist_items": [
        {
            "item_name": "Final Lien Waivers",
            "category": "Contractual",
            "responsible_party": "Krupp",
            "status": "in_progress",
            "due_date": "2026-09-30",
            "notes": "Awaiting 2 of 5 subcontractor waivers",
        },
        {
            "item_name": "As-Built Drawings",
            "category": "Technical",
            "responsible_party": "Krupp",
            "status": "in_progress",
            "due_date": "2026-09-15",
            "notes": "MEP as-builts 80% complete",
        },
        {
            "item_name": "Certificate of Occupancy",
            "category": "Regulatory",
            "responsible_party": "Krupp",
            "status": "not_started",
            "due_date": "2026-09-30",
            "notes": "Pending final inspections",
        },
        {
            "item_name": "Building Systems Training",
            "category": "Owner Turnover",
            "responsible_party": "Pacific Mechanical",
            "status": "not_started",
            "due_date": "2026-09-20",
            "notes": "HVAC and plumbing training sessions",
        },
        {
            "item_name": "Final Cost Report",
            "category": "Financial",
            "responsible_party": "Krupp",
            "status": "complete",
            "due_date": None,
            "notes": "Delivered 2026-08-15",
        },
    ],
    "items_by_responsibility": [
        {"party": "Krupp", "total": 15, "complete": 8, "outstanding": 7},
        {"party": "Pacific Mechanical", "total": 5, "complete": 1, "outstanding": 4},
        {"party": "ABC Electrical Services", "total": 5, "complete": 1, "outstanding": 4},
    ],
    "recommendations": [
        "Schedule owner training sessions for week of Sept 15",
        "Follow up with subs on outstanding lien waivers",
    ],
})


def _make_skill(settings: Settings) -> CloseoutAssemblerSkill:
    """Build a CloseoutAssemblerSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_CLOSEOUT_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=3500,
        output_tokens=2500,
        cost_cents=4,
        duration_ms=5500,
    )
    mock_api.settings = settings
    return CloseoutAssemblerSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestCloseoutAssemblerValidation:
    """Test input validation for closeout assembler."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="All MEP rough-ins complete. Punch list down to 15 items. "
            "Waiting on final lien waivers from electrical and mechanical subs.",
        )
        assert result["project_id"] == 1
        assert result["mode"] == "generate"

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                notes="Closeout notes for the project are ready to go.",
            )

    def test_validate_input_missing_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Closeout notes are required"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
            )

    def test_validate_input_short_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="at least 20 characters"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Too short",
            )

    def test_validate_input_invalid_mode(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid mode"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="All MEP rough-ins complete. Punch list is almost done.",
                mode="review",
            )

    def test_validate_input_update_mode(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Updated status: lien waivers received from all subs now.",
            mode="update",
        )
        assert result["mode"] == "update"


class TestCloseoutAssemblerPrompt:
    """Test prompt building for closeout assembler."""

    def test_build_prompt_includes_closeout_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "All MEP rough-ins complete. Waiting on lien waivers.",
            "mode": "generate",
            "checklist_file_path": None,
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"
        assert "CLOSEOUT NOTES" in messages[0]["content"]


class TestCloseoutAssemblerOutput:
    """Test output formatting for closeout assembler."""

    def test_format_output_creates_docx(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "All rough-ins complete. Waiting on waivers.",
            "mode": "generate",
            "checklist_file_path": None,
        }
        output_path = skill.format_output(MOCK_CLOSEOUT_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists_to_closeout_packages(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "All rough-ins complete. Waiting on waivers.",
            "mode": "generate",
            "checklist_file_path": None,
        }
        skill.format_output(MOCK_CLOSEOUT_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM closeout_packages WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["status"] == "in_progress"
            assert row["package_name"] == "Closeout Package — KRUPP-2026-TEST"


class TestCloseoutAssemblerEndToEnd:
    """Test full closeout assembler lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="All MEP rough-ins complete. Punch list down to 15 items. "
            "Waiting on final lien waivers from electrical and mechanical subs.",
        )
        assert result.output_path.exists()
        assert result.skill_name == "closeout_assembler"
        assert result.project_code == "KRUPP-2026-TEST"
