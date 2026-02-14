"""Tests for the Bid Comparison skill."""

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
from kruppai.skills.bid_comparison import BidComparisonSkill


MOCK_BID_COMPARISON_JSON = json.dumps({
    "bidders": [
        {
            "company": "ABC Electrical Services",
            "base_bid_cents": 120_000_000,
            "alternates": [{"description": "LED upgrade", "amount_cents": 1_500_000}],
            "qualifications": ["Excludes fire alarm testing"],
            "exclusions": ["Security system wiring"],
            "notable_terms": ["Net 30 payment"],
            "adjusted_bid_cents": 125_000_000,
            "strengths": ["Prior project experience", "Local workforce"],
            "concerns": ["Excludes security wiring"],
        },
        {
            "company": "Delta Electric Co",
            "base_bid_cents": 115_000_000,
            "alternates": [],
            "qualifications": ["Subject to union wage rates"],
            "exclusions": ["Fire alarm system", "Security wiring"],
            "notable_terms": ["Progress billing monthly"],
            "adjusted_bid_cents": 135_000_000,
            "strengths": ["Low base bid"],
            "concerns": ["Multiple exclusions inflate adjusted bid"],
        },
    ],
    "scope_gaps": [
        {
            "item": "Security system wiring",
            "included_by": [],
            "excluded_by": ["ABC Electrical", "Delta Electric"],
            "estimated_cost_cents": 5_000_000,
        },
    ],
    "recommendation": {
        "recommended_bidder": "ABC Electrical Services",
        "reasoning": "Lower adjusted bid with fewer exclusions. Prior project experience is a significant advantage.",
        "clarifications_needed": ["Confirm fire alarm testing scope", "Verify security wiring add"],
    },
    "spread_analysis": {
        "low_bid_cents": 115_000_000,
        "high_bid_cents": 120_000_000,
        "spread_percent": 4.3,
        "average_bid_cents": 117_500_000,
        "notes": "Tight spread suggests competitive market. Delta's exclusions make their effective bid higher.",
    },
    "overall_assessment": "Two competitive bids received. ABC offers better value despite higher base bid due to fewer exclusions.",
})


def _make_skill(settings: Settings) -> BidComparisonSkill:
    """Build a BidComparisonSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_BID_COMPARISON_JSON,
        model="claude-sonnet-4-5-20250929",
        input_tokens=4000,
        output_tokens=2500,
        cost_cents=5,
        duration_ms=6000,
    )
    mock_api.settings = settings
    return BidComparisonSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


def _create_bid_files(tmp_path: Path) -> list[Path]:
    """Create two minimal XLSX bid files for testing."""
    from openpyxl import Workbook

    paths = []
    for name in ["bid_abc.xlsx", "bid_delta.xlsx"]:
        wb = Workbook()
        ws = wb.active
        ws.title = "Bid"
        ws.append(["Item", "Description", "Amount"])
        ws.append(["1", "Base electrical", "1200000"])
        path = tmp_path / name
        wb.save(str(path))
        paths.append(path)
    return paths


class TestBidComparisonValidation:
    """Test input validation for bid comparison."""

    def test_validate_input_valid(self, seeded_db: Settings, tmp_path: Path) -> None:
        bid_files = _create_bid_files(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            project="KRUPP-2026-TEST",
            trade="electrical",
            bids=",".join(str(p) for p in bid_files),
        )
        assert result["trade"] == "electrical"
        assert len(result["bid_paths"]) == 2

    def test_validate_input_missing_project(self, seeded_db: Settings, tmp_path: Path) -> None:
        bid_files = _create_bid_files(tmp_path)
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Project code is required"):
            skill.validate_input(
                trade="electrical",
                bids=",".join(str(p) for p in bid_files),
            )

    def test_validate_input_missing_trade(self, seeded_db: Settings, tmp_path: Path) -> None:
        bid_files = _create_bid_files(tmp_path)
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Trade is required"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                bids=",".join(str(p) for p in bid_files),
            )

    def test_validate_input_too_few_bids(self, seeded_db: Settings, tmp_path: Path) -> None:
        bid_files = _create_bid_files(tmp_path)
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="At least 2 bid files"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                trade="electrical",
                bids=str(bid_files[0]),
            )

    def test_validate_input_file_not_found(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Bid file not found"):
            skill.validate_input(
                project="KRUPP-2026-TEST",
                trade="electrical",
                bids="/nonexistent/a.xlsx,/nonexistent/b.xlsx",
            )


class TestBidComparisonOutput:
    """Test output formatting for bid comparison."""

    def test_format_output_creates_files(self, seeded_db: Settings, tmp_path: Path) -> None:
        bid_files = _create_bid_files(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "trade": "electrical",
            "bid_paths": [str(p) for p in bid_files],
        }
        output_path = skill.format_output(MOCK_BID_COMPARISON_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists(self, seeded_db: Settings, tmp_path: Path) -> None:
        bid_files = _create_bid_files(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "trade": "electrical",
            "bid_paths": [str(p) for p in bid_files],
        }
        skill.format_output(MOCK_BID_COMPARISON_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM bid_comparisons WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["trade"] == "electrical"
            assert row["number_of_bidders"] == 2


class TestBidComparisonEndToEnd:
    """Test full bid comparison lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings, tmp_path: Path) -> None:
        bid_files = _create_bid_files(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            trade="electrical",
            bids=",".join(str(p) for p in bid_files),
        )
        assert result.output_path.exists()
        assert result.skill_name == "bid_comparison"
        assert result.project_code == "KRUPP-2026-TEST"
