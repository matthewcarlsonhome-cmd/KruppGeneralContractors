"""Tests for the Case Study Generator skill."""

import json
from unittest.mock import MagicMock

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.case_study import CaseStudySkill


MOCK_CASE_STUDY_RESPONSE = (
    "City Center Medical Office Building: Setting the Standard in Healthcare Construction"
    "\n---SECTION BREAK---\n"
    "- 45,000 SF, 3-story medical office building\n"
    "- Completed on time and under budget\n"
    "- Zero OSHA recordable incidents\n"
    "- GMP delivery method with open-book accounting"
    "\n---SECTION BREAK---\n"
    "The Challenge\n"
    "Regional Health Partners needed a state-of-the-art medical office "
    "building that could accommodate advanced imaging equipment while "
    "maintaining patient comfort. The site was constrained by an active "
    "adjacent clinic that could not be disrupted during construction."
    "\n---SECTION BREAK---\n"
    "Our Approach\n"
    "Krupp implemented a phased construction approach with dedicated "
    "vibration monitoring near the imaging suite. BIM coordination "
    "identified 47 MEP clashes before construction began, saving an "
    "estimated 3 weeks of rework."
    "\n---SECTION BREAK---\n"
    "The project was delivered 2 weeks ahead of schedule and $150,000 "
    "under the GMP. The facility achieved LEED Silver certification "
    "and has received positive feedback from clinical staff."
    "\n---SECTION BREAK---\n"
    '{"contract_value": "$12.85M", "duration_months": 12, '
    '"square_footage": 45000, "on_time": true, "on_budget": true, '
    '"safety_record": "365 days without incident", '
    '"change_order_percent": 2.8, "rfis_closed": 42}'
    "\n---SECTION BREAK---\n"
    "Sarah Chen served as Project Manager, bringing 15 years of "
    "healthcare construction experience. Mike Rodriguez led field "
    "operations as Senior Superintendent."
    "\n---SECTION BREAK---\n"
    '"Krupp\'s team was exceptional. They delivered a world-class '
    'facility on time and within budget." — Dr. Amanda Foster, '
    "Regional Health Partners"
)


def _make_skill(settings: Settings) -> CaseStudySkill:
    """Build a CaseStudySkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_CASE_STUDY_RESPONSE,
        model="claude-sonnet-4-5-20250929",
        input_tokens=3000,
        output_tokens=2000,
        cost_cents=4,
        duration_ms=5000,
    )
    mock_api.settings = settings
    return CaseStudySkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestCaseStudyValidation:
    """Test input validation for case study generator."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Project completed on time. Zero safety incidents. "
            "Client very satisfied with communication and quality.",
        )
        assert result["project_id"] == 1
        assert result["audience"] == "marketing"
        assert result["photos"] == []

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                notes="Project highlights for the case study document.",
            )

    def test_validate_input_missing_notes(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project notes are required"):
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

    def test_validate_input_invalid_audience(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid audience"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                notes="Project highlights for the case study generation process.",
                audience="internal",
            )

    def test_validate_input_proposal_audience(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            notes="Project completed with excellent safety record and client satisfaction.",
            audience="proposal",
        )
        assert result["audience"] == "proposal"


class TestCaseStudyPrompt:
    """Test prompt building for case study generator."""

    def test_build_prompt_includes_highlights(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Project completed on time with zero incidents.",
            "audience": "marketing",
            "photos": [],
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"
        assert "HIGHLIGHTS" in messages[0]["content"]


class TestCaseStudyOutput:
    """Test output formatting for case study generator."""

    def test_format_output_creates_docx(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Project completed on time.",
            "audience": "marketing",
            "photos": [],
        }
        output_path = skill.format_output(
            MOCK_CASE_STUDY_RESPONSE, context, validated
        )
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists_to_case_studies(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "notes": "Project completed on time.",
            "audience": "marketing",
            "photos": [],
        }
        skill.format_output(MOCK_CASE_STUDY_RESPONSE, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM case_studies WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["status"] == "draft"
            assert row["target_audience"] == "marketing"
            assert "City Center" in row["title"]


class TestCaseStudyEndToEnd:
    """Test full case study lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="Project completed on time. Zero safety incidents. "
            "Client very satisfied with communication and quality.",
        )
        assert result.output_path.exists()
        assert result.skill_name == "case_study"
        assert result.project_code == "KRUPP-2026-TEST"
