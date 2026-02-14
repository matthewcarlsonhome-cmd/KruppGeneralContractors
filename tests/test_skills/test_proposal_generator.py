"""Tests for the Proposal Generator skill."""

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
from kruppai.skills.proposal_generator import ProposalGeneratorSkill


MOCK_PROPOSAL_RESPONSE = (
    "Dear Dr. Foster,\n\n"
    "Krupp General Contractors is pleased to submit this proposal for the "
    "City Center Medical Office Building renovation.\n"
    "---SECTION BREAK---\n"
    "Executive Summary\n"
    "Krupp brings 20 years of healthcare construction expertise to this project. "
    "Our team has completed over $200M in medical office facilities.\n"
    "---SECTION BREAK---\n"
    "Approach\n"
    "Our phased approach will minimize disruption to adjacent clinic operations. "
    "We will use BIM coordination for all MEP systems.\n"
    "---SECTION BREAK---\n"
    "Team\n"
    "Sarah Chen, PMP, LEED AP — Project Manager with 15 years of experience.\n"
    "---SECTION BREAK---\n"
    "Experience\n"
    "We have completed similar projects including Regional Medical Pavilion "
    "and Downtown Health Center.\n"
    "---SECTION BREAK---\n"
    "Schedule\n"
    "We propose a 12-month construction schedule with a phased turnover.\n"
    "---SECTION BREAK---\n"
    "Safety\n"
    "Krupp maintains an EMR of 0.72 and has an OSHA-compliant safety program.\n"
    "---SECTION BREAK---\n"
    "Fee Narrative\n"
    "Our GMP approach provides transparent pricing with open-book accounting."
)


def _make_skill(settings: Settings) -> ProposalGeneratorSkill:
    """Build a ProposalGeneratorSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_PROPOSAL_RESPONSE,
        model="claude-opus-4-6",
        input_tokens=6000,
        output_tokens=4000,
        cost_cents=40,
        duration_ms=12000,
    )
    mock_api.settings = settings
    return ProposalGeneratorSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestProposalGeneratorValidation:
    """Test input validation for proposal generator."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            client="Regional Health Partners",
            description="New 45,000 SF medical office building with three floors.",
            proposal_type="full",
        )
        assert result["project_id"] == 1
        assert result["client"] == "Regional Health Partners"
        assert result["proposal_type"] == "full"

    def test_validate_input_missing_client(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Client name is required"):
            skill.validate_input(
                description="New medical office building renovation project.",
            )

    def test_validate_input_missing_description(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project description is required"):
            skill.validate_input(
                client="Regional Health Partners",
            )

    def test_validate_input_short_description(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="at least 20 characters"):
            skill.validate_input(
                client="Regional Health Partners",
                description="Short desc",
            )

    def test_validate_input_invalid_proposal_type(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid proposal type"):
            skill.validate_input(
                client="Regional Health Partners",
                description="New 45,000 SF medical office building renovation project.",
                proposal_type="executive",
            )


class TestProposalGeneratorPrompt:
    """Test prompt building for proposal generator."""

    def test_build_prompt_includes_knowledge_base(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "client": "Regional Health Partners",
            "description": "New 45,000 SF medical office building.",
            "proposal_type": "full",
            "rfp_file_path": None,
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"
        assert "OPPORTUNITY" in messages[0]["content"]
        assert "Regional Health Partners" in messages[0]["content"]


class TestProposalGeneratorOutput:
    """Test output formatting for proposal generator."""

    def test_format_output_creates_docx(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "client": "Regional Health Partners",
            "description": "New 45,000 SF medical office building.",
            "proposal_type": "full",
            "rfp_file_path": None,
        }
        output_path = skill.format_output(MOCK_PROPOSAL_RESPONSE, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists_to_proposals(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "client": "Regional Health Partners",
            "description": "New 45,000 SF medical office building.",
            "proposal_type": "full",
            "rfp_file_path": None,
        }
        skill.format_output(MOCK_PROPOSAL_RESPONSE, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM proposals WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["status"] == "draft"
            assert row["client_name"] == "Regional Health Partners"
            assert row["proposal_type"] == "full"


class TestProposalGeneratorEndToEnd:
    """Test full proposal generator lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            client="Regional Health Partners",
            description="New 45,000 SF medical office building with three floors.",
            proposal_type="full",
        )
        assert result.output_path.exists()
        assert result.skill_name == "proposal_generator"
        assert result.project_code == "KRUPP-2026-TEST"
