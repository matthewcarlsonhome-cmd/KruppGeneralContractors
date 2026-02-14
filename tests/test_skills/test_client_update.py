"""Tests for the Client Update Letter Generator skill."""

import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.client_update import ClientUpdateSkill


MOCK_CLIENT_UPDATE_TEXT = """## Dear Dr. Foster

Thank you for the opportunity to provide this weekly update on the City Center Medical Office Building project.

## Project Status Summary

We are pleased to report strong progress this week. The 3rd floor slab pour was completed on schedule, and MEP rough-in is progressing well on the 2nd floor. We are currently tracking at 35% complete.

## Schedule Update

The project remains on schedule for substantial completion. We have identified a 2-week delay in structural steel delivery for the penthouse. Our team is re-sequencing MEP rough-in work to maintain the critical path and avoid overall schedule impact.

## Budget/Change Order Update

Change Order #4 for additional fire suppression in the parking garage has been submitted for your review at $34,000. No other pending change orders at this time.

## Key Activities This Period

- Completed 3rd floor concrete slab pour (Section B)
- Continued electrical conduit installation on 2nd floor
- Received structural steel delivery for penthouse structure
- Initiated 1st floor punch list walkthrough

## Upcoming Milestones

- 2nd floor MEP rough-in completion
- Penthouse steel erection (pending delivery confirmation)
- 1st floor finish work commencement

## Items Requiring Owner Action

- RFI responses needed: Lobby finish materials and roof drain locations remain outstanding with the architect. Your follow-up would help maintain our schedule.
- CO #4 approval: Fire suppression change order ($34,000) pending your review.

## Closing

We appreciate your continued partnership on this project. Please don't hesitate to reach out with any questions or to schedule a site visit.
"""


def _make_skill(settings: Settings) -> ClientUpdateSkill:
    """Build a ClientUpdateSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_CLIENT_UPDATE_TEXT,
        model="claude-sonnet-4-5-20250929",
        input_tokens=2000,
        output_tokens=1500,
        cost_cents=3,
        duration_ms=5000,
    )
    mock_api.settings = settings
    return ClientUpdateSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestClientUpdateValidation:
    """Test input validation for client updates."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Good progress this week. 3rd floor slab poured, on schedule.",
        )
        assert result["project_id"] == 1
        assert result["period"] == "weekly"

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                notes="Good progress this week on the project.",
            )

    def test_validate_input_missing_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Update notes are required"):
            skill.validate_input(project="KRUPP-2026-TEST")

    def test_validate_input_notes_too_short(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="at least 20 characters"):
            skill.validate_input(
                project="KRUPP-2026-TEST", notes="Short."
            )

    def test_validate_input_invalid_period(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Period must be"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Good progress this week. 3rd floor slab poured.",
                period="quarterly",
            )

    def test_validate_input_monthly_period(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Good progress this month. Major milestones completed.",
            period="monthly",
        )
        assert result["period"] == "monthly"


class TestClientUpdatePrompt:
    """Test prompt building for client updates."""

    def test_build_prompt_structure(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Good progress this week.",
            "period": "weekly",
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"

    def test_build_prompt_includes_context(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Good progress this week.",
            "period": "weekly",
        }
        messages = skill.build_prompt(validated, context)
        content = messages[0]["content"]
        assert "Good progress" in content


class TestClientUpdateOutput:
    """Test output formatting for client updates."""

    def test_format_output_creates_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Good progress this week.",
            "period": "weekly",
        }
        output_path = skill.format_output(
            MOCK_CLIENT_UPDATE_TEXT, context, validated
        )
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_has_letterhead(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Good progress this week.",
            "period": "weekly",
        }
        output_path = skill.format_output(
            MOCK_CLIENT_UPDATE_TEXT, context, validated
        )

        from docx import Document

        doc = Document(str(output_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        # Should have Krupp letterhead
        assert "KRUPP GENERAL CONTRACTORS" in full_text

    def test_format_output_content(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Good progress this week.",
            "period": "weekly",
        }
        output_path = skill.format_output(
            MOCK_CLIENT_UPDATE_TEXT, context, validated
        )

        from docx import Document

        doc = Document(str(output_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Status Update" in full_text


class TestClientUpdateEndToEnd:
    """Test full client update lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Good progress this week. 3rd floor slab poured, on schedule. "
            "Steel delivery pushed 2 weeks but re-sequencing MEP.",
        )
        assert result.output_path.exists()
        assert result.skill_name == "client_update"
        assert result.project_code == "KRUPP-2026-TEST"
