"""Tests for the Budget Forecaster skill."""

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
from kruppai.skills.budget_forecaster import BudgetForecasterSkill


MOCK_FORECAST_JSON = json.dumps({
    "health_status": "at_risk",
    "executive_summary": "The project is trending slightly over budget due to "
    "electrical cost overruns. Contingency draw-down is ahead of schedule.",
    "original_budget_cents": 1_250_000_000,
    "approved_changes_cents": 35_000_000,
    "current_budget_cents": 1_285_000_000,
    "committed_costs_cents": 1_100_000_000,
    "actual_costs_cents": 450_000_000,
    "projected_final_cents": 1_310_000_000,
    "variance_cents": -25_000_000,
    "contingency_remaining_cents": 50_000_000,
    "contingency_recommended_cents": 75_000_000,
    "budget_lines": [
        {
            "cost_code": "03.000",
            "description": "Concrete",
            "budget_cents": 45_000_000,
            "committed_cents": 44_000_000,
            "actual_cents": 20_000_000,
            "projected_cents": 44_500_000,
            "variance_cents": 500_000,
            "percent_complete": 45.0,
            "status": "on_track",
            "notes": "Within budget",
        },
        {
            "cost_code": "26.000",
            "description": "Electrical",
            "budget_cents": 120_000_000,
            "committed_cents": 125_000_000,
            "actual_cents": 60_000_000,
            "projected_cents": 130_000_000,
            "variance_cents": -10_000_000,
            "percent_complete": 46.0,
            "status": "over_budget",
            "notes": "Committed costs exceed budget due to medical-grade upgrades",
        },
    ],
    "risk_items": [
        {
            "cost_code": "26.000",
            "description": "Electrical cost overrun from medical-grade requirements",
            "risk_level": "high",
            "potential_impact_cents": 10_000_000,
            "mitigation": "Negotiate VE options with electrical sub",
        },
    ],
    "recommendations": [
        "Request detailed cost breakdown from electrical sub",
        "Review contingency allocation with owner",
    ],
})


def _make_skill(settings: Settings) -> BudgetForecasterSkill:
    """Build a BudgetForecasterSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_FORECAST_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=4000,
        output_tokens=3000,
        cost_cents=5,
        duration_ms=6000,
    )
    mock_api.settings = settings
    return BudgetForecasterSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestBudgetForecasterValidation:
    """Test input validation for budget forecaster."""

    def test_validate_input_valid(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            file=str(sample_xlsx),
        )
        assert result["project_id"] == 1
        assert result["file_path"] == str(sample_xlsx)

    def test_validate_input_missing_project(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(file=str(sample_xlsx))

    def test_validate_input_missing_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Job cost report file is required"):
            skill.validate_input(project="KRUPP-2026-TEST")

    def test_validate_input_file_not_found(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="File not found"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                file="/nonexistent/budget.xlsx",
            )

    def test_validate_input_wrong_format(self, seeded_db: Settings, tmp_path: Path) -> None:
        bad_file = tmp_path / "report.txt"
        bad_file.write_text("test")
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="XLSX, XLS, or CSV"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                file=str(bad_file),
            )


class TestBudgetForecasterPrompt:
    """Test prompt building for budget forecaster."""

    def test_build_prompt_includes_estimate_data(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(sample_xlsx),
            "notes": None,
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"
        assert "JOB COST REPORT" in messages[0]["content"]


class TestBudgetForecasterOutput:
    """Test output formatting for budget forecaster."""

    def test_format_output_creates_docx_and_xlsx(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(sample_xlsx),
            "notes": None,
        }
        output_path = skill.format_output(MOCK_FORECAST_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists_to_budget_forecasts(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(sample_xlsx),
            "notes": None,
        }
        skill.format_output(MOCK_FORECAST_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM budget_forecasts WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["variance_cents"] == -25_000_000
            assert row["projected_final_cents"] == 1_310_000_000


class TestBudgetForecasterEndToEnd:
    """Test full budget forecaster lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            file=str(sample_xlsx),
        )
        assert result.output_path.exists()
        assert result.skill_name == "budget_forecaster"
        assert result.project_code == "KRUPP-2026-TEST"
