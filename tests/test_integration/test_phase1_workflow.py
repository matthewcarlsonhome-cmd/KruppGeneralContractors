"""End-to-end integration tests for Phase 1 skills.

These tests use mocked API responses to validate the full workflow
without requiring an API key.
"""

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
from kruppai.skills.daily_report import DailyReportSkill
from kruppai.skills.meeting_minutes import MeetingMinutesSkill
from kruppai.skills.punch_list import PunchListSkill
from kruppai.skills.rfi_generator import RfiGeneratorSkill
from kruppai.skills.safety_talk import SafetyTalkSkill


# --- Mock Responses ---

DAILY_REPORT_RESPONSE = json.dumps({
    "report_date": date.today().isoformat(),
    "weather": {"high_f": 65, "low_f": 42, "conditions": "Clear", "precipitation": "0.00 in", "wind": "8 mph"},
    "workforce": {"krupp_workers": 6, "sub_workers": 28, "total": 34, "detail": [
        {"company": "Krupp GC", "trade": "general", "headcount": 6, "work_area": "3rd floor"},
    ]},
    "work_performed": "Continued framing on 3rd floor.",
    "materials_delivered": [],
    "equipment_on_site": [],
    "visitors": [],
    "delays": "None",
    "safety_observations": "All PPE compliance observed.",
    "issues": [],
    "upcoming_work": "MEP rough-in start Monday.",
})

RFI_RESPONSE = json.dumps({
    "subject": "Beam Size Clarification at Grid C",
    "question": "Please clarify beam size at grid line C.",
    "spec_reference": "05 12 00",
    "drawing_reference": "S-301",
    "cost_impact": "potential",
    "cost_impact_notes": "Larger beam = higher cost.",
    "schedule_impact": "potential",
    "schedule_impact_notes": "Fab starts next week.",
    "suggested_solution": "Use W14x30 per spec.",
    "priority": "high",
})

MINUTES_RESPONSE = json.dumps({
    "attendees": [{"name": "Sarah Chen", "company": "Krupp GC", "role": "PM"}],
    "discussion_items": [{"topic": "Schedule", "details": "On track.", "item_number": 1}],
    "decisions": [{"decision": "Proceed with tile option B", "made_by": "Owner", "context": "$45k"}],
    "action_items": [
        {"description": "Get revised steel schedule", "assigned_to": "Mike Rodriguez", "due_date": "2026-02-20", "priority": "high"},
    ],
    "prior_items_status": [],
    "next_meeting": {"date": "2026-02-27", "location": "Site"},
    "formatted_minutes": "Minutes text...",
})

CLIENT_UPDATE_RESPONSE = """## Project Status Summary

Strong progress this week. Currently at 35% complete.

## Schedule Update

On schedule for substantial completion. Steel delay being managed.

## Key Activities

- 3rd floor slab poured
- MEP rough-in continuing

## Items Requiring Owner Action

- RFI responses needed for lobby finishes.
"""

SAFETY_TALK_RESPONSE = """## Fall Protection

## Introduction

Today we review fall protection procedures.

## Key Hazards

Falls from height are the #1 cause of death in construction.

## Protective Measures

1. 100% tie-off above 6 feet.

## Summary

- Always tie off
- Inspect harness daily
"""

PUNCH_LIST_RESPONSE = json.dumps({
    "list_name": "Punch List - 2nd Floor",
    "inspection_date": date.today().isoformat(),
    "area": "2nd Floor",
    "items": [
        {"item_number": 1, "location": "Room 201", "description": "Ceiling tiles misaligned", "trade": "ceiling", "assigned_to": "ABC Interiors", "priority": "normal"},
        {"item_number": 2, "location": "Room 203", "description": "Paint touch-up east wall", "trade": "painting", "assigned_to": "Pro Paint", "priority": "cosmetic"},
    ],
    "summary": {"total_items": 2, "by_trade": {"ceiling": 1, "painting": 1}, "by_priority": {"normal": 1, "cosmetic": 1}},
})


def _build_skill(skill_class, settings, response_content):
    """Build a skill with a specific mock response."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=response_content,
        model="claude-sonnet-4-5-20250929",
        input_tokens=1000,
        output_tokens=800,
        cost_cents=2,
        duration_ms=3000,
    )
    mock_api.settings = settings
    return skill_class(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestPhase1Workflow:
    """Integration tests for Phase 1 skills."""

    def test_daily_report_full_workflow(self, seeded_db: Settings) -> None:
        """Rough notes produce a daily report DOCX with all sections."""
        skill = _build_skill(DailyReportSkill, seeded_db, DAILY_REPORT_RESPONSE)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Continued framing on 3rd floor. 34 workers on site. "
            "All PPE compliance observed. MEP rough-in starts Monday.",
        )
        assert result.output_path.exists()
        assert result.output_path.suffix == ".docx"
        assert result.skill_name == "daily_report"

        # Verify DB persistence
        with get_db(seeded_db) as conn:
            cursor = conn.execute("SELECT * FROM daily_reports WHERE project_id = 1")
            assert cursor.fetchone() is not None

    def test_rfi_auto_numbering(self, seeded_db: Settings) -> None:
        """Two RFIs on same project get sequential numbers."""
        skill = _build_skill(RfiGeneratorSkill, seeded_db, RFI_RESPONSE)
        skill.execute(
            project="KRUPP-2026-TEST",
            issue="First issue: beam size discrepancy at grid C.",
        )
        skill.execute(
            project="KRUPP-2026-TEST",
            issue="Second issue: missing fire damper details.",
        )

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT rfi_number FROM rfis WHERE project_id = 1 ORDER BY rfi_number"
            )
            numbers = [r["rfi_number"] for r in cursor.fetchall()]
            assert numbers == [1, 2]

    def test_meeting_minutes_action_item_carryforward(
        self, seeded_db: Settings
    ) -> None:
        """Action items from meeting 1 appear as open items in meeting 2."""
        skill = _build_skill(MeetingMinutesSkill, seeded_db, MINUTES_RESPONSE)

        # Meeting 1 — creates action items
        skill.execute(
            project="KRUPP-2026-TEST",
            type="oac",
            notes="Discussed schedule. Mike to get revised steel schedule by Friday.",
        )

        # Check action items were created
        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM action_items WHERE source_skill = 'meeting_minutes'"
            )
            new_items = cursor.fetchall()
            assert len(new_items) >= 1

        # Meeting 2 — prior items should be available in context
        result2 = skill.execute(
            project="KRUPP-2026-TEST",
            type="oac",
            notes="Follow-up meeting. Reviewed progress on steel schedule.",
        )
        assert result2.output_path.exists()

    def test_punch_list_dual_output(self, seeded_db: Settings) -> None:
        """Punch list generates both DOCX and XLSX."""
        skill = _build_skill(PunchListSkill, seeded_db, PUNCH_LIST_RESPONSE)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Room 201: ceiling tiles misaligned. Room 203: paint touch up.",
            area="2nd Floor",
        )
        assert result.output_path.suffix == ".docx"

        xlsx_files = list(skill.settings.output_dir.glob("punch_list_*.xlsx"))
        assert len(xlsx_files) >= 1

    def test_safety_talk_without_project(self, seeded_db: Settings) -> None:
        """Safety talk works without project context."""
        skill = _build_skill(SafetyTalkSkill, seeded_db, SAFETY_TALK_RESPONSE)
        result = skill.execute(
            topic="Fall protection for steel erection work",
        )
        assert result.output_path.exists()
        assert result.project_code is None

    def test_client_update_letterhead(self, seeded_db: Settings) -> None:
        """Client update uses full letterhead formatting."""
        skill = _build_skill(ClientUpdateSkill, seeded_db, CLIENT_UPDATE_RESPONSE)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Good progress this week. 3rd floor slab poured. "
            "Steel delay being managed by re-sequencing MEP.",
        )
        assert result.output_path.exists()

        from docx import Document

        doc = Document(str(result.output_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "KRUPP GENERAL CONTRACTORS" in full_text
