"""Tests for the Lessons Learned skill."""

import json
from unittest.mock import MagicMock

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.lessons_learned import LessonsLearnedSkill


MOCK_LESSONS_JSON = json.dumps([
    {
        "title": "Early MEP coordination prevents costly rework",
        "category": "design",
        "situation": "Mechanical and electrical rough-ins conflicted at the "
        "second-floor ceiling plenum. The HVAC ductwork routing was not "
        "coordinated with conduit runs during design.",
        "impact": "Required 3 days of rework and a $15,000 change order to "
        "reroute conduit. Schedule impact of 2 days on the critical path.",
        "lesson": "Conduct BIM clash detection for all MEP systems before "
        "rough-in begins on each floor.",
        "recommendation": "Add a mandatory BIM coordination milestone 2 weeks "
        "before MEP rough-in for all future healthcare projects.",
        "severity": "high",
        "applicable_project_types": ["healthcare", "commercial"],
        "tags": ["BIM", "MEP", "coordination", "clash detection"],
    },
    {
        "title": "Submittal review delays cascade to procurement",
        "category": "procurement",
        "situation": "Architect review of mechanical submittals took 4 weeks "
        "instead of the contractual 2 weeks, delaying equipment procurement.",
        "impact": "Medical gas equipment arrived 3 weeks late, impacting the "
        "third-floor schedule by 10 days.",
        "lesson": "Track submittal review durations weekly and escalate at the "
        "1-week mark if no response.",
        "recommendation": "Implement an automated submittal aging report and "
        "escalation process in the first week of each project.",
        "severity": "medium",
        "applicable_project_types": ["healthcare"],
        "tags": ["submittals", "procurement", "schedule"],
    },
    {
        "title": "Safety stand-down after near miss improved crew awareness",
        "category": "safety",
        "situation": "A near miss occurred when unsecured material fell from "
        "the third floor to the work area below. No injuries resulted.",
        "impact": "A safety stand-down was called and all work stopped for "
        "2 hours. Crew safety awareness improved measurably afterward.",
        "lesson": "Treat near misses with the same urgency as actual incidents "
        "to reinforce safety culture.",
        "recommendation": "Conduct a formal safety stand-down within 4 hours of "
        "any near miss and document corrective actions.",
        "severity": "critical",
        "applicable_project_types": ["commercial", "healthcare", "education"],
        "tags": ["safety", "near miss", "stand-down"],
    },
])


def _make_skill(settings: Settings) -> LessonsLearnedSkill:
    """Build a LessonsLearnedSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_LESSONS_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=3000,
        output_tokens=2500,
        cost_cents=4,
        duration_ms=5000,
    )
    mock_api.settings = settings
    return LessonsLearnedSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestLessonsLearnedValidation:
    """Test input validation for lessons learned."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="MEP coordination was a major challenge. We had multiple "
            "clash issues between mechanical and electrical systems.",
        )
        assert result["project_id"] == 1
        assert result["mode"] == "manual"
        assert result["category"] is None

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                notes="Lessons learned from the MEP coordination issues.",
            )

    def test_validate_input_missing_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Session notes are required"):
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

    def test_validate_input_extract_mode(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Focus on schedule and budget lessons from this project phase.",
            mode="extract",
        )
        assert result["mode"] == "extract"

    def test_validate_input_invalid_mode(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Mode must be"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Lessons learned notes that are long enough to pass validation.",
                mode="auto",
            )

    def test_validate_input_valid_category(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Focus on safety lessons from the third-floor incident.",
            category="safety",
        )
        assert result["category"] == "safety"

    def test_validate_input_invalid_category(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid category"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Lessons learned notes that are long enough to pass validation.",
                category="logistics",
            )


class TestLessonsLearnedPrompt:
    """Test prompt building for lessons learned."""

    def test_build_prompt_manual_mode(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "MEP coordination caused 3 days of rework.",
            "mode": "manual",
            "category": None,
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"
        assert "LESSONS LEARNED SESSION NOTES" in messages[0]["content"]

    def test_build_prompt_extract_mode(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Focus on schedule delays and cost overruns.",
            "mode": "extract",
            "category": None,
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"
        assert "PROJECT DATA TO ANALYZE" in messages[0]["content"]


class TestLessonsLearnedOutput:
    """Test output formatting for lessons learned."""

    def test_format_output_creates_docx(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "MEP coordination was a challenge.",
            "mode": "manual",
            "category": None,
        }
        output_path = skill.format_output(MOCK_LESSONS_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists_each_lesson(self, seeded_db: Settings) -> None:
        """Each lesson should be persisted individually to lessons_learned table."""
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "MEP coordination was a challenge.",
            "mode": "manual",
            "category": None,
        }
        skill.format_output(MOCK_LESSONS_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM lessons_learned WHERE project_id = 1 "
                "ORDER BY id"
            )
            rows = cursor.fetchall()
            assert len(rows) == 3
            # Lessons are sorted by severity before persisting (critical first)
            assert rows[0]["title"] == "Safety stand-down after near miss improved crew awareness"
            assert rows[0]["category"] == "safety"
            assert rows[0]["severity"] == "critical"
            assert rows[0]["source"] == "manual"
            assert rows[2]["severity"] == "medium"


class TestLessonsLearnedEndToEnd:
    """Test full lessons learned lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="MEP coordination was a major challenge. We had multiple "
            "clash issues between mechanical and electrical systems.",
        )
        assert result.output_path.exists()
        assert result.skill_name == "lessons_learned"
        assert result.project_code == "KRUPP-2026-TEST"
