"""Tests for the Change Order Builder skill."""

import json
from unittest.mock import MagicMock

import pytest

from kruppai.core.api_client import ApiResponse
from kruppai.core.config import Settings
from kruppai.core.context_manager import ContextManager
from kruppai.core.database import get_db
from kruppai.core.knowledge_base import KnowledgeBase
from kruppai.core.output_formatter import OutputFormatter
from kruppai.skills.change_order import ChangeOrderSkill


MOCK_CHANGE_ORDER_JSON = json.dumps({
    "title": "Add Emergency Generator for MRI Suite",
    "formal_description": "Per owner's directive dated February 10, 2026, add a dedicated 500kW emergency "
    "generator to serve the MRI suite. This change is required to meet updated hospital "
    "accreditation standards.",
    "reason_category": "owner_change",
    "cost_breakdown": [
        {"item": "Labor", "description": "Electrical installation labor, 320 hours", "amount_cents": 3_200_000},
        {"item": "Material", "description": "500kW Caterpillar generator, transfer switch, conduit", "amount_cents": 8_500_000},
        {"item": "Equipment", "description": "Crane rental for generator placement", "amount_cents": 1_500_000},
        {"item": "Subcontractor", "description": "Concrete pad by ABC Concrete", "amount_cents": 750_000},
    ],
    "subtotal_cents": 13_950_000,
    "markup_percent": 10.0,
    "markup_cents": 1_395_000,
    "total_cents": 15_345_000,
    "schedule_impact_days": 14,
    "schedule_impact_description": "Generator has 8-week lead time. Installation requires 2 weeks. "
    "Can be sequenced to minimize critical path impact by beginning pad work during lead time.",
    "supporting_references": [
        "Owner email dated 2026-02-10",
        "Updated accreditation requirements",
    ],
    "contractual_basis": "Per Section 7.2 of the GMP Agreement, Owner-directed changes shall be "
    "documented via Change Order with agreed-upon markup.",
})


def _make_skill(settings: Settings) -> ChangeOrderSkill:
    """Build a ChangeOrderSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_CHANGE_ORDER_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=2000,
        output_tokens=1500,
        cost_cents=3,
        duration_ms=5000,
    )
    mock_api.settings = settings
    return ChangeOrderSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestChangeOrderValidation:
    """Test input validation for change orders."""

    def test_validate_input_valid(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            description="Owner wants to add emergency generator for MRI suite.",
            reason="owner_change",
            cost=150000,
            schedule_days=14,
        )
        assert result["project_id"] == 1
        assert result["reason"] == "owner_change"
        assert result["cost_cents"] == 15_000_000
        assert result["schedule_days"] == 14

    def test_validate_input_missing_project(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                description="Add generator.",
                reason="owner_change",
            )

    def test_validate_input_missing_description(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Change description is required"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                reason="owner_change",
            )

    def test_validate_input_short_description(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="at least 10 characters"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                description="Add gen",
                reason="owner_change",
            )

    def test_validate_input_invalid_reason(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid reason"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                description="Owner wants to add emergency generator.",
                reason="whimsy",
            )


class TestChangeOrderPrompt:
    """Test prompt building for change orders."""

    def test_build_prompt_structure(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "description": "Add emergency generator for MRI suite.",
            "reason": "owner_change",
            "cost_cents": 15_000_000,
            "schedule_days": 14,
            "markup_percent": 10.0,
        }
        messages = skill.build_prompt(validated, context)
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"
        assert "CHANGE DESCRIPTION" in messages[0]["content"]


class TestChangeOrderOutput:
    """Test output formatting for change orders."""

    def test_format_output_creates_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "description": "Add emergency generator.",
            "reason": "owner_change",
            "cost_cents": 15_000_000,
            "schedule_days": 14,
            "markup_percent": 10.0,
        }
        output_path = skill.format_output(MOCK_CHANGE_ORDER_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "description": "Add emergency generator.",
            "reason": "owner_change",
            "cost_cents": 15_000_000,
            "schedule_days": 14,
            "markup_percent": 10.0,
        }
        skill.format_output(MOCK_CHANGE_ORDER_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM change_orders WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["co_number"] == 1
            assert row["status"] == "draft"
            assert row["total_with_markup_cents"] == 15_345_000


class TestChangeOrderEndToEnd:
    """Test full change order lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            description="Owner wants to add emergency generator for MRI suite.",
            reason="owner_change",
            cost=150000,
        )
        assert result.output_path.exists()
        assert result.skill_name == "change_order"
        assert result.project_code == "KRUPP-2026-TEST"

    def test_sequential_co_numbers(self, seeded_db: Settings) -> None:
        """CO numbers should auto-increment per project."""
        skill = _make_skill(seeded_db)
        result1 = skill.execute(
            project="KRUPP-2026-TEST",
            description="First change: add generator for MRI suite.",
            reason="owner_change",
        )
        result2 = skill.execute(
            project="KRUPP-2026-TEST",
            description="Second change: upgrade lobby finishes per owner directive.",
            reason="owner_change",
        )

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT co_number FROM change_orders "
                "WHERE project_id = 1 ORDER BY co_number"
            )
            numbers = [row["co_number"] for row in cursor.fetchall()]
            assert numbers == [1, 2]
