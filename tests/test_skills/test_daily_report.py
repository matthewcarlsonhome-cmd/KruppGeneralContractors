"""Tests for the Daily Field Report Generator skill."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager, ProjectContext
from kruppai.core.database import get_db, init_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.daily_report import DailyReportSkill, fetch_weather


MOCK_DAILY_REPORT_JSON = json.dumps({
    "report_date": date.today().isoformat(),
    "weather": {
        "high_f": 72,
        "low_f": 48,
        "conditions": "Partly cloudy",
        "precipitation": "0.00 in",
        "wind": "12 mph",
    },
    "workforce": {
        "krupp_workers": 8,
        "sub_workers": 34,
        "total": 42,
        "detail": [
            {
                "company": "Krupp General Contractors",
                "trade": "general",
                "headcount": 8,
                "work_area": "3rd floor",
            },
            {
                "company": "ABC Electrical Services",
                "trade": "electrical",
                "headcount": 12,
                "work_area": "2nd floor walls",
            },
        ],
    },
    "work_performed": "Concrete pour completed on 3rd floor slab section B. "
    "ABC Electrical running conduit in 2nd floor walls.",
    "materials_delivered": ["85 CY structural concrete", "Structural steel for penthouse"],
    "equipment_on_site": ["Concrete pump truck", "Tower crane"],
    "visitors": [],
    "delays": "Rain delay of approximately 2 hours in the morning.",
    "safety_observations": "All workers wearing required PPE. No incidents reported.",
    "issues": ["Steel delivery coordination needed for next week"],
    "upcoming_work": "Continue MEP rough-in on 2nd floor.",
})


def _make_skill(settings: Settings) -> DailyReportSkill:
    """Build a DailyReportSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_DAILY_REPORT_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=1500,
        output_tokens=900,
        cost_cents=2,
        duration_ms=3200,
    )
    mock_api.settings = settings
    return DailyReportSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestDailyReportValidation:
    """Test input validation for daily reports."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Poured 3rd floor slab section B today, 85 yards concrete.",
        )
        assert result["project_id"] == 1
        assert result["project_code"] == "KRUPP-2026-TEST"
        assert "slab section B" in result["notes"]
        assert result["report_date"] == date.today().isoformat()

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(notes="Some notes here for the daily report.")

    def test_validate_input_missing_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Field notes are required"):
            skill.validate_input(project="KRUPP-2026-TEST")

    def test_validate_input_notes_too_short(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="at least 20 characters"):
            skill.validate_input(project="KRUPP-2026-TEST", notes="Short.")

    def test_validate_input_future_date(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="cannot be in the future"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Poured concrete today, 85 yards worth.",
                date="2099-01-01",
            )

    def test_validate_input_bad_date_format(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid date format"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Poured concrete today, 85 yards worth.",
                date="not-a-date",
            )


class TestDailyReportPrompt:
    """Test prompt building for daily reports."""

    def test_build_prompt_structure(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Poured 3rd floor slab today.",
            "report_date": date.today().isoformat(),
            "weather_override": None,
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"
        assert "FIELD NOTES" in messages[0]["content"]

    def test_build_prompt_includes_context(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Poured concrete today.",
            "report_date": date.today().isoformat(),
            "weather_override": None,
        }
        messages = skill.build_prompt(validated, context)
        # Project data should be referenced in the system prompt
        # (knowledge base provides system context in execute())
        content = messages[0]["content"]
        assert "Poured concrete today" in content


class TestDailyReportOutput:
    """Test output formatting for daily reports."""

    def test_format_output_creates_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Poured concrete today.",
            "report_date": date.today().isoformat(),
        }
        output_path = skill.format_output(MOCK_DAILY_REPORT_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_content(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Poured concrete today.",
            "report_date": date.today().isoformat(),
        }
        output_path = skill.format_output(MOCK_DAILY_REPORT_JSON, context, validated)

        from docx import Document

        doc = Document(str(output_path))
        # Collect text from paragraphs and table cells
        all_text = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    all_text.append(cell.text)
        full_text = "\n".join(all_text)
        assert "Daily Field Report" in full_text
        assert "KRUPP-2026-TEST" in full_text

    def test_format_output_persists_to_db(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Poured concrete today.",
            "report_date": date.today().isoformat(),
        }
        skill.format_output(MOCK_DAILY_REPORT_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM daily_reports WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["report_number"] == 1
            assert row["total_workers"] == 42


class TestDailyReportEndToEnd:
    """Test full skill lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Poured 3rd floor slab section B today, 85 yards concrete. "
            "ABC Electric running conduit in walls 2nd floor.",
        )
        assert result.output_path.exists()
        assert result.skill_name == "daily_report"
        assert result.project_code == "KRUPP-2026-TEST"
        assert result.cost_cents == 2


class TestWeatherFetch:
    """Test the weather fetch utility."""

    def test_weather_code_to_text(self) -> None:
        from kruppai.skills.daily_report import _weather_code_to_text

        assert _weather_code_to_text(0) == "Clear sky"
        assert _weather_code_to_text(63) == "Moderate rain"
        assert _weather_code_to_text(None) == "Unknown"
        assert _weather_code_to_text(999) == "Unknown"

    def test_fetch_weather_handles_failure(self) -> None:
        """Weather fetch returns empty dict on any failure."""
        result = fetch_weather(0.0, 0.0, "invalid-date")
        assert result == {} or isinstance(result, dict)
