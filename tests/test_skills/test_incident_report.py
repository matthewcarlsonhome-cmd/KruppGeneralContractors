"""Tests for the Incident Report skill."""

import json
from unittest.mock import MagicMock

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.incident_report import IncidentReportSkill


MOCK_INCIDENT_JSON = json.dumps({
    "summary": "A worker sustained a laceration to the left forearm when a "
    "sheet metal duct fitting slipped during installation on the second "
    "floor. First aid was administered on site. The worker returned to "
    "modified duty the same day.",
    "location": "Second floor, mechanical room, grid C-4",
    "involved_persons": [
        {
            "name": "John Martinez",
            "company": "Pacific Mechanical",
            "role": "Sheet metal installer",
            "injury_description": "3-inch laceration to left forearm, treated with butterfly bandages",
        },
    ],
    "witnesses": [
        {"name": "Tom Baker", "company": "ABC Electrical Services"},
        {"name": "Mike Rodriguez", "company": "Krupp General Contractors"},
    ],
    "immediate_actions": "First aid kit was retrieved and wound was cleaned "
    "and bandaged. Worker was evaluated by the on-site safety officer. "
    "Area was secured and sharp edges on ductwork were flagged.",
    "root_cause": "The duct fitting was not properly secured in the vise "
    "before the worker began cutting, allowing it to shift and expose "
    "a sharp edge.",
    "contributing_factors": [
        "Worker was not wearing cut-resistant gloves",
        "Vise was positioned on an unstable temporary table",
        "Inadequate lighting in the work area",
    ],
    "corrective_actions": [
        {
            "action": "Require cut-resistant gloves for all sheet metal work",
            "responsible_party": "Pacific Mechanical",
            "due_date": "2026-02-15",
        },
        {
            "action": "Provide stable workbenches for all cutting operations",
            "responsible_party": "Krupp General Contractors",
            "due_date": "2026-02-16",
        },
        {
            "action": "Install temporary lighting in mechanical room",
            "responsible_party": "ABC Electrical Services",
            "due_date": "2026-02-17",
        },
    ],
    "preventive_actions": [
        "Add cut-resistant glove requirement to site safety plan",
        "Include sheet metal handling in next weekly toolbox talk",
        "Audit all temporary work surfaces on each floor",
    ],
    "is_osha_recordable": False,
    "osha_notification_required": False,
    "severity": "minor",
})


def _make_skill(settings: Settings) -> IncidentReportSkill:
    """Build an IncidentReportSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_INCIDENT_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=2500,
        output_tokens=2000,
        cost_cents=3,
        duration_ms=4500,
    )
    mock_api.settings = settings
    return IncidentReportSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestIncidentReportValidation:
    """Test input validation for incident reports."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            description="Worker cut his arm on a sheet metal fitting during "
            "duct installation on the second floor.",
            type="first_aid",
            date="2026-02-13",
        )
        assert result["project_id"] == 1
        assert result["incident_type"] == "first_aid"
        assert result["incident_date"] == "2026-02-13"

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                description="Worker injured on the second floor during installation.",
                type="first_aid",
            )

    def test_validate_input_missing_description(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Incident description is required"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                type="first_aid",
            )

    def test_validate_input_short_description(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="at least 20 characters"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                description="Worker cut arm",
                type="first_aid",
            )

    def test_validate_input_missing_type(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Incident type is required"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                description="Worker cut his arm on a sheet metal fitting during installation.",
            )

    def test_validate_input_invalid_type(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid incident type"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                description="Worker cut his arm on a sheet metal fitting during installation.",
                type="minor_scratch",
            )

    def test_validate_input_invalid_date_format(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid date format"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                description="Worker cut his arm on a sheet metal fitting during installation.",
                type="first_aid",
                date="02/13/2026",
            )

    def test_validate_input_defaults_date_to_today(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            description="Worker cut his arm on a sheet metal fitting during installation.",
            type="first_aid",
        )
        # Date should default to today (not None)
        assert result["incident_date"] is not None
        assert len(result["incident_date"]) == 10  # YYYY-MM-DD format


class TestIncidentReportPrompt:
    """Test prompt building for incident reports."""

    def test_build_prompt_includes_incident_description(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "description": "Worker cut his arm on sheet metal.",
            "incident_type": "first_aid",
            "incident_date": "2026-02-13",
            "incident_time": "10:30",
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"
        assert "INCIDENT DESCRIPTION" in messages[0]["content"]


class TestIncidentReportAutoNumbering:
    """Test auto-incrementing incident numbers."""

    def test_incident_numbers_auto_increment(self, seeded_db: Settings) -> None:
        """Incident numbers should auto-increment per project."""
        skill = _make_skill(seeded_db)

        result1 = skill.execute(
            project="KRUPP-2026-TEST",
            description="First incident: worker cut arm on sheet metal fitting.",
            type="first_aid",
            date="2026-02-13",
        )
        result2 = skill.execute(
            project="KRUPP-2026-TEST",
            description="Second incident: near miss with falling material from scaffold.",
            type="near_miss",
            date="2026-02-14",
        )

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT incident_number FROM incident_reports "
                "WHERE project_id = 1 ORDER BY incident_number"
            )
            numbers = [row["incident_number"] for row in cursor.fetchall()]
            assert numbers == [1, 2]


class TestIncidentReportOutput:
    """Test output formatting for incident reports."""

    def test_format_output_creates_docx(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "description": "Worker cut his arm on sheet metal.",
            "incident_type": "first_aid",
            "incident_date": "2026-02-13",
            "incident_time": "10:30",
        }
        output_path = skill.format_output(MOCK_INCIDENT_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists_with_draft_status(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "description": "Worker cut his arm on sheet metal.",
            "incident_type": "first_aid",
            "incident_date": "2026-02-13",
            "incident_time": "10:30",
        }
        skill.format_output(MOCK_INCIDENT_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM incident_reports WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["status"] == "draft"
            assert row["incident_type"] == "first_aid"
            assert row["severity"] == "minor"
            assert row["is_osha_recordable"] == 0


class TestIncidentReportEndToEnd:
    """Test full incident report lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            description="Worker cut his arm on a sheet metal fitting during "
            "duct installation on the second floor.",
            type="first_aid",
            date="2026-02-13",
        )
        assert result.output_path.exists()
        assert result.skill_name == "incident_report"
        assert result.project_code == "KRUPP-2026-TEST"
