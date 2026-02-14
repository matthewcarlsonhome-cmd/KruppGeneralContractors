"""Tests for the Estimate Reviewer skill."""

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
from kruppai.skills.estimate_reviewer import EstimateReviewerSkill


MOCK_REVIEW_JSON = json.dumps({
    "overall_assessment": "The estimate is generally within industry norms for a healthcare project of this size.",
    "confidence_level": "medium",
    "total_estimate_cents": 1_250_000_000,
    "benchmark_total_cents": 1_280_000_000,
    "variance_percent": -2.3,
    "recommended_contingency_percent": 7.5,
    "missing_divisions": [
        {"csi_code": "10", "description": "Specialties", "typical_range": "$50,000-$150,000"},
    ],
    "flagged_items": [
        {
            "csi_code": "26",
            "description": "Electrical Systems",
            "estimated_cents": 120_000_000,
            "benchmark_cents": 100_000_000,
            "variance_percent": 20.0,
            "flag": "HIGH",
            "risk": "medium",
            "explanation": "Electrical costs are 20% above benchmark, likely due to medical-grade requirements.",
        },
    ],
    "category_analysis": [
        {"division": "03 - Concrete", "estimated_cents": 45_000_000, "per_sf_cents": 1000, "benchmark_per_sf_cents": 950, "notes": "Within range"},
        {"division": "26 - Electrical", "estimated_cents": 120_000_000, "per_sf_cents": 2667, "benchmark_per_sf_cents": 2222, "notes": "Above benchmark"},
    ],
    "recommendations": [
        "Request detailed breakdown of electrical costs from sub",
        "Verify specialties division is included elsewhere",
    ],
})


def _make_skill(settings: Settings) -> EstimateReviewerSkill:
    """Build an EstimateReviewerSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_REVIEW_JSON,
        model="claude-opus-4-6",
        input_tokens=5000,
        output_tokens=3000,
        cost_cents=30,
        duration_ms=8000,
    )
    mock_api.settings = settings
    return EstimateReviewerSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestEstimateReviewerValidation:
    """Test input validation for estimate reviewer."""

    def test_validate_input_valid(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            file=str(sample_xlsx),
            project="KRUPP-2026-TEST",
            type="commercial",
            sqft=45000,
        )
        assert result["file_path"] == str(sample_xlsx)
        assert result["project_type"] == "commercial"
        assert result["sqft"] == 45000

    def test_validate_input_missing_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Estimate file is required"):
            skill.validate_input(project="KRUPP-2026-TEST")

    def test_validate_input_file_not_found(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="File not found"):
            skill.validate_input(file="/nonexistent/estimate.xlsx")

    def test_validate_input_wrong_format(self, seeded_db: Settings, tmp_path: Path) -> None:
        bad_file = tmp_path / "notes.txt"
        bad_file.write_text("test")
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="must be .xlsx"):
            skill.validate_input(file=str(bad_file))

    def test_validate_input_no_project(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        """Estimate review works without a project."""
        skill = _make_skill(seeded_db)
        result = skill.validate_input(file=str(sample_xlsx))
        assert result["project_id"] is None
        assert result["project_type"] == "commercial"


class TestEstimateReviewerPrompt:
    """Test prompt building for estimate reviewer."""

    def test_build_prompt_structure(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(sample_xlsx),
            "project_type": "commercial",
            "sqft": 45000,
            "region": "National Average",
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"
        assert "ESTIMATE DATA" in messages[0]["content"]


class TestEstimateReviewerOutput:
    """Test output formatting for estimate reviewer."""

    def test_format_output_creates_file(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(sample_xlsx),
            "project_type": "commercial",
            "sqft": 45000,
            "region": "National Average",
        }
        output_path = skill.format_output(MOCK_REVIEW_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(sample_xlsx),
            "project_type": "commercial",
            "sqft": 45000,
            "region": "National Average",
        }
        skill.format_output(MOCK_REVIEW_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM estimate_reviews WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["variance_percent"] == -2.3


class TestEstimateReviewerEndToEnd:
    """Test full estimate review lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            file=str(sample_xlsx),
            project="KRUPP-2026-TEST",
            type="commercial",
            sqft=45000,
        )
        assert result.output_path.exists()
        assert result.skill_name == "estimate_reviewer"
        assert result.project_code == "KRUPP-2026-TEST"
