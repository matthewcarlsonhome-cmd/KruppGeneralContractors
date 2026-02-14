"""Tests for the Submittal Tracker skill."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.submittal_tracker import SubmittalTrackerSkill


MOCK_SUBMITTAL_JSON = json.dumps({
    "overall_status": "Submittal tracking is behind on 3 items. Two critical path submittals need immediate attention.",
    "total_submittals": 8,
    "status_summary": {
        "pending": 2,
        "submitted": 3,
        "approved": 2,
        "approved_as_noted": 1,
        "revise_resubmit": 0,
        "rejected": 0,
    },
    "submittals": [
        {
            "submittal_number": "03.30.001",
            "title": "Concrete Mix Design",
            "spec_section": "03 30 00",
            "subcontractor": "ABC Concrete",
            "status": "approved",
            "submitted_date": "2026-01-15",
            "required_date": "2026-02-01",
            "review_due_date": "2026-01-29",
            "lead_time_days": 14,
            "is_critical_path": False,
            "notes": "Approved with no exceptions.",
        },
        {
            "submittal_number": "26.05.001",
            "title": "Electrical Switchgear",
            "spec_section": "26 05 00",
            "subcontractor": "ABC Electrical Services",
            "status": "submitted",
            "submitted_date": "2026-02-01",
            "required_date": "2026-04-15",
            "review_due_date": "2026-02-15",
            "lead_time_days": 45,
            "is_critical_path": True,
            "notes": "Long lead time — on critical path.",
        },
    ],
    "overdue_items": [
        {
            "submittal_number": "23.05.001",
            "title": "HVAC Equipment",
            "days_overdue": 5,
            "impact": "May delay mechanical rough-in start by 1 week.",
        },
    ],
    "upcoming_deadlines": [
        {
            "submittal_number": "26.05.001",
            "title": "Electrical Switchgear",
            "due_date": "2026-02-15",
            "days_remaining": 2,
        },
    ],
    "action_items": [
        {
            "action": "Expedite HVAC equipment submittal review with architect",
            "assigned_to": "Sarah Chen",
            "due_date": "2026-02-14",
            "priority": "urgent",
        },
        {
            "action": "Follow up with ABC Electrical on switchgear shop drawings",
            "assigned_to": "James Park",
            "due_date": "2026-02-16",
            "priority": "high",
        },
    ],
    "recommendations": [
        "Prioritize overdue HVAC submittal to prevent schedule impact",
        "Pre-order switchgear upon approval to protect lead time",
    ],
})


def _make_skill(settings: Settings) -> SubmittalTrackerSkill:
    """Build a SubmittalTrackerSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_SUBMITTAL_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=3500,
        output_tokens=2200,
        cost_cents=4,
        duration_ms=5000,
    )
    mock_api.settings = settings
    return SubmittalTrackerSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


def _create_submittal_log(tmp_path: Path) -> Path:
    """Create a minimal submittal log XLSX for testing."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Submittal Log"
    ws.append(["Number", "Title", "Status", "Required Date", "Submitted"])
    ws.append(["03.30.001", "Concrete Mix", "Approved", "2026-02-01", "2026-01-15"])
    ws.append(["26.05.001", "Switchgear", "Submitted", "2026-04-15", "2026-02-01"])
    path = tmp_path / "submittal_log.xlsx"
    wb.save(str(path))
    return path


class TestSubmittalTrackerValidation:
    """Test input validation for submittal tracker."""

    def test_validate_input_valid(self, seeded_db: Settings, tmp_path: Path) -> None:
        log_file = _create_submittal_log(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            file=str(log_file),
        )
        assert result["project_id"] == 1
        assert result["file_path"] == str(log_file)

    def test_validate_input_missing_project(self, seeded_db: Settings, tmp_path: Path) -> None:
        log_file = _create_submittal_log(tmp_path)
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(file=str(log_file))

    def test_validate_input_missing_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Submittal log file is required"):
            skill.validate_input(project="KRUPP-2026-TEST")

    def test_validate_input_file_not_found(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="File not found"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                file="/nonexistent/log.xlsx",
            )


class TestSubmittalTrackerOutput:
    """Test output formatting for submittal tracker."""

    def test_format_output_creates_file(self, seeded_db: Settings, tmp_path: Path) -> None:
        log_file = _create_submittal_log(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(log_file),
            "notes": "",
        }
        output_path = skill.format_output(MOCK_SUBMITTAL_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists_submittals(self, seeded_db: Settings, tmp_path: Path) -> None:
        log_file = _create_submittal_log(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(log_file),
            "notes": "",
        }
        skill.format_output(MOCK_SUBMITTAL_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM submittals WHERE project_id = 1"
            )
            rows = cursor.fetchall()
            assert len(rows) == 2
            numbers = [r["submittal_number"] for r in rows]
            assert "03.30.001" in numbers
            assert "26.05.001" in numbers


class TestSubmittalTrackerEndToEnd:
    """Test full submittal tracker lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings, tmp_path: Path) -> None:
        log_file = _create_submittal_log(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            file=str(log_file),
        )
        assert result.output_path.exists()
        assert result.skill_name == "submittal_tracker"
        assert result.project_code == "KRUPP-2026-TEST"
