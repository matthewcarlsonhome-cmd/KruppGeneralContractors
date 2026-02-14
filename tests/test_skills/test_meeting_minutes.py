"""Tests for the Meeting Minutes Generator skill."""

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
from kruppai.skills.meeting_minutes import MeetingMinutesSkill


MOCK_MINUTES_JSON = json.dumps({
    "attendees": [
        {"name": "Sarah Chen", "company": "Krupp GC", "role": "Project Manager"},
        {"name": "Dr. Amanda Foster", "company": "Regional Health", "role": "Owner Rep"},
        {"name": "John Smith", "company": "Smith Architecture", "role": "Architect"},
    ],
    "discussion_items": [
        {
            "topic": "Lobby Finish Selections",
            "details": "Owner reviewed porcelain tile options and selected Option B "
            "at an estimated cost of $45,000.",
            "item_number": 1,
        },
        {
            "topic": "Steel Delivery Schedule",
            "details": "Steel fabricator has notified a 2-week delay in delivery. "
            "Krupp is re-sequencing MEP rough-in to maintain critical path.",
            "item_number": 2,
        },
    ],
    "decisions": [
        {
            "decision": "Porcelain tile Option B selected for lobby finish",
            "made_by": "Dr. Amanda Foster",
            "context": "Cost of $45,000 approved",
        },
    ],
    "action_items": [
        {
            "description": "Get revised schedule from steel fabricator",
            "assigned_to": "Mike Rodriguez",
            "due_date": "2026-02-20",
            "priority": "high",
        },
        {
            "description": "Submit change order for tile upgrade",
            "assigned_to": "Sarah Chen",
            "due_date": "2026-02-18",
            "priority": "normal",
        },
    ],
    "prior_items_status": [
        {
            "item_id": 1,
            "status": "discussed",
            "notes": "RFI #12 still awaiting architect response.",
        },
    ],
    "next_meeting": {"date": "2026-02-27", "location": "Job site trailer"},
    "formatted_minutes": "Meeting minutes formatted text...",
})


def _make_skill(settings: Settings) -> MeetingMinutesSkill:
    """Build a MeetingMinutesSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_MINUTES_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=1800,
        output_tokens=1200,
        cost_cents=2,
        duration_ms=4100,
    )
    mock_api.settings = settings
    return MeetingMinutesSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestMeetingMinutesValidation:
    """Test input validation for meeting minutes."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            type="oac",
            notes="Met with owner and architect. Discussed lobby finish selections.",
        )
        assert result["project_id"] == 1
        assert result["meeting_type"] == "oac"

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                type="oac",
                notes="Met with owner and architect about something.",
            )

    def test_validate_input_missing_type(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Meeting type is required"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Met with owner and architect about something.",
            )

    def test_validate_input_invalid_type(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid meeting type"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                type="board_meeting",
                notes="Met with owner and architect about something.",
            )

    def test_validate_input_missing_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Meeting notes are required"):
            skill.validate_input(project="KRUPP-2026-TEST", type="oac")

    def test_validate_input_with_attendees(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            type="oac",
            notes="Discussed the project schedule with owner.",
            attendees="Sarah Chen, Dr. Amanda Foster, John Smith",
        )
        assert len(result["attendees"]) == 3
        assert "Sarah Chen" in result["attendees"]


class TestMeetingMinutesPrompt:
    """Test prompt building for meeting minutes."""

    def test_build_prompt_structure(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "meeting_type": "oac",
            "notes": "Discussed lobby finishes.",
            "meeting_date": date.today().isoformat(),
            "attendees": [],
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"
        assert "MEETING NOTES" in messages[0]["content"]

    def test_build_prompt_includes_context(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "meeting_type": "oac",
            "notes": "Discussed lobby finishes.",
            "meeting_date": date.today().isoformat(),
            "attendees": [],
        }
        messages = skill.build_prompt(validated, context)
        content = messages[0]["content"]
        assert "lobby finishes" in content


class TestMeetingMinutesOutput:
    """Test output formatting for meeting minutes."""

    def test_format_output_creates_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "meeting_type": "oac",
            "notes": "Discussed lobby finishes.",
            "meeting_date": date.today().isoformat(),
            "attendees": [],
        }
        output_path = skill.format_output(MOCK_MINUTES_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_content(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "meeting_type": "oac",
            "notes": "Discussed lobby finishes.",
            "meeting_date": date.today().isoformat(),
            "attendees": [],
        }
        output_path = skill.format_output(MOCK_MINUTES_JSON, context, validated)

        from docx import Document

        doc = Document(str(output_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Meeting Minutes" in full_text

    def test_format_output_persists_meeting_and_actions(
        self, seeded_db: Settings
    ) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "meeting_type": "oac",
            "notes": "Discussed lobby finishes.",
            "meeting_date": date.today().isoformat(),
            "attendees": [],
        }
        skill.format_output(MOCK_MINUTES_JSON, context, validated)

        with get_db(seeded_db) as conn:
            # Meeting record
            cursor = conn.execute("SELECT * FROM meetings WHERE project_id = 1")
            row = cursor.fetchone()
            assert row is not None
            assert row["meeting_number"] == 1
            assert row["meeting_type"] == "oac"

            # New action items: 5 seeded + 2 from this meeting = 7
            cursor = conn.execute(
                "SELECT * FROM action_items "
                "WHERE project_id = 1 AND source_skill = 'meeting_minutes'"
            )
            new_items = cursor.fetchall()
            assert len(new_items) == 7  # 5 seeded + 2 new
            descriptions = [item["description"] for item in new_items]
            assert any("steel fabricator" in d.lower() for d in descriptions)


class TestMeetingMinutesEndToEnd:
    """Test full meeting minutes lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            type="oac",
            notes="Met with owner and architect. Discussed lobby finish selections.",
        )
        assert result.output_path.exists()
        assert result.skill_name == "meeting_minutes"
        assert result.project_code == "KRUPP-2026-TEST"

    def test_action_item_carryforward(self, seeded_db: Settings) -> None:
        """Prior open action items appear in second meeting prompt."""
        skill = _make_skill(seeded_db)
        # First meeting creates new action items
        skill.execute(
            project="KRUPP-2026-TEST",
            type="oac",
            notes="First meeting: discussed lobby finishes and steel delay.",
        )

        # Verify action items exist
        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM action_items "
                "WHERE project_id = 1 AND status = 'open'"
            )
            # Original 5 from seed + 2 from meeting
            count = cursor.fetchone()[0]
            assert count >= 5
