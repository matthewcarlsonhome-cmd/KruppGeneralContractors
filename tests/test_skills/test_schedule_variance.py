"""Tests for the Schedule Variance Analyzer skill."""

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
from kruppai.skills.schedule_variance import ScheduleVarianceSkill


MOCK_SCHEDULE_JSON = json.dumps({
    "overall_assessment": "Project is 12 days behind schedule primarily due to steel delivery delay. "
    "Two critical path activities are at risk.",
    "snapshot_date": "2026-02-13",
    "planned_completion_date": "2026-09-15",
    "projected_completion_date": "2026-09-27",
    "variance_days": 12,
    "percent_complete_planned": 38.0,
    "percent_complete_actual": 35.0,
    "critical_path_items": [
        {
            "activity": "Structural Steel Erection",
            "planned_finish": "2026-04-15",
            "projected_finish": "2026-04-29",
            "variance_days": 14,
            "status": "behind",
        },
        {
            "activity": "MEP Rough-In 2nd Floor",
            "planned_finish": "2026-05-30",
            "projected_finish": "2026-06-05",
            "variance_days": 6,
            "status": "at_risk",
        },
    ],
    "at_risk_items": [
        {
            "activity": "Exterior Curtain Wall",
            "risk": "Dependent on steel completion",
            "impact_days": 14,
            "mitigation": "Pre-order curtain wall panels to shorten installation window",
        },
    ],
    "delay_drivers": [
        {
            "activity": "Steel Delivery",
            "cause": "Fabrication shop backlog",
            "days_impact": 14,
            "responsible_party": "Smith Steel Fabricators",
        },
    ],
    "recovery_actions": [
        {
            "action": "Authorize overtime for steel erection crews",
            "potential_recovery_days": 5,
            "estimated_cost_cents": 7_500_000,
            "feasibility": "high",
        },
        {
            "action": "Re-sequence MEP rough-in to start on 1st floor during steel delay",
            "potential_recovery_days": 7,
            "estimated_cost_cents": 0,
            "feasibility": "high",
        },
    ],
    "upcoming_milestones": [
        {
            "milestone": "Steel Topping Out",
            "planned_date": "2026-04-15",
            "projected_date": "2026-04-29",
            "status": "behind",
        },
    ],
    "recommendations": [
        "Authorize overtime for steel erection to recover 5 days",
        "Re-sequence MEP work to start on completed floors",
        "Issue schedule recovery plan to owner within 1 week",
    ],
})


def _make_skill(settings: Settings) -> ScheduleVarianceSkill:
    """Build a ScheduleVarianceSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_SCHEDULE_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=3000,
        output_tokens=2000,
        cost_cents=4,
        duration_ms=5500,
    )
    mock_api.settings = settings
    return ScheduleVarianceSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


def _create_schedule_xlsx(tmp_path: Path) -> Path:
    """Create a minimal schedule XLSX for testing."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(["Activity", "Start", "Finish", "% Complete", "Status"])
    ws.append(["Structural Steel", "2026-02-01", "2026-04-15", "45%", "Behind"])
    ws.append(["MEP Rough-In", "2026-03-15", "2026-05-30", "10%", "On Track"])
    path = tmp_path / "project_schedule.xlsx"
    wb.save(str(path))
    return path


class TestScheduleVarianceValidation:
    """Test input validation for schedule variance."""

    def test_validate_input_valid(self, seeded_db: Settings, tmp_path: Path) -> None:
        schedule_file = _create_schedule_xlsx(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            file=str(schedule_file),
            notes="Steel delivery delayed by 2 weeks.",
        )
        assert result["project_id"] == 1
        assert result["file_path"] == str(schedule_file)

    def test_validate_input_missing_project(self, seeded_db: Settings, tmp_path: Path) -> None:
        schedule_file = _create_schedule_xlsx(tmp_path)
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(file=str(schedule_file))

    def test_validate_input_missing_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Schedule file is required"):
            skill.validate_input(project="KRUPP-2026-TEST")

    def test_validate_input_file_not_found(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="File not found"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                file="/nonexistent/schedule.xlsx",
            )

    def test_validate_input_wrong_format(self, seeded_db: Settings, tmp_path: Path) -> None:
        bad_file = tmp_path / "schedule.txt"
        bad_file.write_text("test")
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="must be PDF"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                file=str(bad_file),
            )


class TestScheduleVarianceOutput:
    """Test output formatting for schedule variance."""

    def test_format_output_creates_file(self, seeded_db: Settings, tmp_path: Path) -> None:
        schedule_file = _create_schedule_xlsx(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(schedule_file),
            "notes": "",
        }
        output_path = skill.format_output(MOCK_SCHEDULE_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists(self, seeded_db: Settings, tmp_path: Path) -> None:
        schedule_file = _create_schedule_xlsx(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(schedule_file),
            "notes": "",
        }
        skill.format_output(MOCK_SCHEDULE_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM schedule_snapshots WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["variance_days"] == 12


class TestScheduleVarianceEndToEnd:
    """Test full schedule variance lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings, tmp_path: Path) -> None:
        schedule_file = _create_schedule_xlsx(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            file=str(schedule_file),
            notes="Steel delivery delayed.",
        )
        assert result.output_path.exists()
        assert result.skill_name == "schedule_variance"
        assert result.project_code == "KRUPP-2026-TEST"
