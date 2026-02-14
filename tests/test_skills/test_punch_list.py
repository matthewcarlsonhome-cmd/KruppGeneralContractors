"""Tests for the Punch List Generator skill."""

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
from kruppai.skills.punch_list import PunchListSkill


MOCK_PUNCH_LIST_JSON = json.dumps({
    "list_name": "Punch List - 2nd Floor - 2026-02-13",
    "inspection_date": "2026-02-13",
    "area": "2nd Floor",
    "items": [
        {
            "item_number": 1,
            "location": "Room 201",
            "description": "Ceiling tiles misaligned along south wall. "
            "Approximately 4 tiles need to be re-seated in grid.",
            "trade": "ceiling",
            "assigned_to": "ABC Interiors",
            "priority": "normal",
        },
        {
            "item_number": 2,
            "location": "Room 203",
            "description": "Paint touch-up required on east wall, approximately "
            "2'x3' area with visible scuff marks at 4' height.",
            "trade": "painting",
            "assigned_to": "Pro Painters LLC",
            "priority": "cosmetic",
        },
        {
            "item_number": 3,
            "location": "Room 205",
            "description": "Door hardware (lever handle) loose on entry door. "
            "Screws need to be tightened or replaced.",
            "trade": "doors/hardware",
            "assigned_to": "Door Systems Inc",
            "priority": "normal",
        },
        {
            "item_number": 4,
            "location": "Bathroom 210",
            "description": "Grout cracking at shower base along north edge. "
            "Requires removal and re-grouting.",
            "trade": "tile",
            "assigned_to": "ABC Interiors",
            "priority": "high",
        },
        {
            "item_number": 5,
            "location": "Bathroom 210",
            "description": "Towel bar not installed per plans at specified location.",
            "trade": "accessories",
            "assigned_to": "[VERIFY: ABC Interiors]",
            "priority": "normal",
        },
        {
            "item_number": 6,
            "location": "Bathroom 210",
            "description": "Exhaust fan not operational. "
            "Check electrical connection and fan unit.",
            "trade": "electrical",
            "assigned_to": "ABC Electrical Services",
            "priority": "high",
        },
        {
            "item_number": 7,
            "location": "Corridor",
            "description": "Base trim not installed at elevator lobby. "
            "Material is on site.",
            "trade": "finish carpentry",
            "assigned_to": "ABC Interiors",
            "priority": "normal",
        },
        {
            "item_number": 8,
            "location": "Corridor",
            "description": "Fire extinguisher cabinet has visible scratch on glass door.",
            "trade": "fire protection",
            "assigned_to": "[VERIFY: Fire Systems Co]",
            "priority": "cosmetic",
        },
        {
            "item_number": 9,
            "location": "Electrical Closet 2E",
            "description": "Panel cover missing on Panel 2A.",
            "trade": "electrical",
            "assigned_to": "ABC Electrical Services",
            "priority": "high",
        },
        {
            "item_number": 10,
            "location": "Electrical Closet 2E",
            "description": "Circuit labeling incomplete on Panel 2A. "
            "Multiple circuits unlabeled.",
            "trade": "electrical",
            "assigned_to": "ABC Electrical Services",
            "priority": "normal",
        },
    ],
    "summary": {
        "total_items": 10,
        "by_trade": {
            "ceiling": 1,
            "painting": 1,
            "doors/hardware": 1,
            "tile": 1,
            "accessories": 1,
            "electrical": 3,
            "finish carpentry": 1,
            "fire protection": 1,
        },
        "by_priority": {
            "critical": 0,
            "high": 3,
            "normal": 5,
            "cosmetic": 2,
        },
    },
})


def _make_skill(settings: Settings) -> PunchListSkill:
    """Build a PunchListSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_PUNCH_LIST_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=1400,
        output_tokens=1600,
        cost_cents=3,
        duration_ms=4200,
    )
    mock_api.settings = settings
    return PunchListSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestPunchListValidation:
    """Test input validation for punch lists."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Room 201: ceiling tiles misaligned. Room 203: paint touch up needed.",
            area="2nd Floor",
        )
        assert result["project_id"] == 1
        assert result["area"] == "2nd Floor"
        assert "Punch List" in result["list_name"]

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                notes="Room 201: ceiling tiles misaligned on south wall.",
            )

    def test_validate_input_missing_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Walk-through notes are required"):
            skill.validate_input(project="KRUPP-2026-TEST")

    def test_validate_input_notes_too_short(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="at least 20 characters"):
            skill.validate_input(project="KRUPP-2026-TEST", notes="Short.")

    def test_validate_input_custom_name(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Room 201: ceiling tiles misaligned on south wall.",
            name="Pre-Substantial Completion Punch List",
        )
        assert result["list_name"] == "Pre-Substantial Completion Punch List"


class TestPunchListPrompt:
    """Test prompt building for punch lists."""

    def test_build_prompt_structure(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Room 201: ceiling tiles misaligned.",
            "area": "2nd Floor",
            "list_name": "Test Punch List",
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"
        assert "WALK-THROUGH NOTES" in messages[0]["content"]

    def test_build_prompt_includes_context(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Room 201: ceiling tiles misaligned.",
            "area": "2nd Floor",
            "list_name": "Test Punch List",
        }
        messages = skill.build_prompt(validated, context)
        content = messages[0]["content"]
        assert "ceiling tiles" in content
        assert "2nd Floor" in content


class TestPunchListOutput:
    """Test output formatting for punch lists."""

    def test_format_output_creates_docx(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Room 201: ceiling tiles misaligned.",
            "area": "2nd Floor",
            "list_name": "Test Punch List",
        }
        output_path = skill.format_output(
            MOCK_PUNCH_LIST_JSON, context, validated
        )
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_creates_xlsx_too(self, seeded_db: Settings) -> None:
        """Punch list generates both DOCX and XLSX."""
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Room 201: ceiling tiles misaligned.",
            "area": "2nd Floor",
            "list_name": "Test Punch List",
        }
        skill.format_output(MOCK_PUNCH_LIST_JSON, context, validated)

        # Check that an XLSX was also created in the output dir
        xlsx_files = list(skill.settings.output_dir.glob("punch_list_*.xlsx"))
        assert len(xlsx_files) >= 1

    def test_format_output_content(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Room 201: ceiling tiles misaligned.",
            "area": "2nd Floor",
            "list_name": "Test Punch List",
        }
        output_path = skill.format_output(
            MOCK_PUNCH_LIST_JSON, context, validated
        )

        from docx import Document

        doc = Document(str(output_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Punch List" in full_text

    def test_format_output_persists_to_db(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Room 201: ceiling tiles misaligned.",
            "area": "2nd Floor",
            "list_name": "Test Punch List",
        }
        skill.format_output(MOCK_PUNCH_LIST_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM punch_lists WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["total_items"] == 10

            cursor = conn.execute(
                "SELECT COUNT(*) FROM punch_items WHERE project_id = 1"
            )
            count = cursor.fetchone()[0]
            assert count == 10

    def test_punch_items_match_subs(self, seeded_db: Settings) -> None:
        """Items assigned to known subs get subcontractor_id linked."""
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Room 201: ceiling tiles misaligned.",
            "area": "2nd Floor",
            "list_name": "Test Punch List",
        }
        skill.format_output(MOCK_PUNCH_LIST_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM punch_items "
                "WHERE project_id = 1 AND assigned_to = 'ABC Electrical Services'"
            )
            rows = cursor.fetchall()
            # ABC Electrical is a known sub — should have subcontractor_id set
            for row in rows:
                assert row["subcontractor_id"] is not None


class TestPunchListEndToEnd:
    """Test full punch list lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Room 201: ceiling tiles misaligned. Room 203: paint touch up "
            "needed east wall. Bathroom 210: grout cracking.",
            area="2nd Floor",
        )
        assert result.output_path.exists()
        assert result.skill_name == "punch_list"
        assert result.project_code == "KRUPP-2026-TEST"

    def test_dual_output(self, seeded_db: Settings) -> None:
        """Punch list generates both DOCX and XLSX."""
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Room 201: ceiling tiles misaligned. Room 203: paint issues.",
            area="2nd Floor",
        )
        assert result.output_path.suffix == ".docx"

        # XLSX should also exist
        xlsx_files = list(skill.settings.output_dir.glob("punch_list_*.xlsx"))
        assert len(xlsx_files) >= 1
