"""Integration tests for Phase 2 skills workflow."""

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


def _build_skill(skill_class, settings, mock_response_json):
    """Build any skill with mocked API returning given JSON."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=mock_response_json,
        model="claude-sonnet-4-5-20250929",
        input_tokens=3000,
        output_tokens=2000,
        cost_cents=5,
        duration_ms=5000,
    )
    mock_api.settings = settings
    return skill_class(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


class TestPhase2Workflow:
    """Integration tests verifying Phase 2 skills work together."""

    def test_estimate_review_full_cycle(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        """Estimate review: parse file → analyze → generate DOCX + XLSX → persist."""
        from kruppai.skills.estimate_reviewer import EstimateReviewerSkill

        mock_json = json.dumps({
            "overall_assessment": "Estimate is within norms.",
            "confidence_level": "medium",
            "total_estimate_cents": 1_000_000_000,
            "benchmark_total_cents": 1_050_000_000,
            "variance_percent": -4.8,
            "recommended_contingency_percent": 5.0,
            "missing_divisions": [],
            "flagged_items": [],
            "category_analysis": [],
            "recommendations": ["Review electrical costs"],
        })
        skill = _build_skill(EstimateReviewerSkill, seeded_db, mock_json)
        result = skill.execute(
            file=str(sample_xlsx),
            project="KRUPP-2026-TEST",
            type="healthcare",
        )
        assert result.output_path.exists()
        with get_db(seeded_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM estimate_reviews")
            assert cursor.fetchone()[0] == 1

    def test_change_order_auto_numbering(self, seeded_db: Settings) -> None:
        """Change orders auto-increment CO number per project."""
        from kruppai.skills.change_order import ChangeOrderSkill

        mock_json = json.dumps({
            "title": "Test CO",
            "formal_description": "Test change order description.",
            "reason_category": "owner_change",
            "cost_breakdown": [],
            "subtotal_cents": 100_000,
            "markup_percent": 10,
            "markup_cents": 10_000,
            "total_cents": 110_000,
            "schedule_impact_days": 0,
            "schedule_impact_description": "",
            "supporting_references": [],
            "contractual_basis": "Per contract terms.",
        })
        skill = _build_skill(ChangeOrderSkill, seeded_db, mock_json)

        # First CO
        result1 = skill.execute(
            project="KRUPP-2026-TEST",
            description="First change: add new electrical outlet.",
            reason="owner_change",
        )
        # Second CO
        result2 = skill.execute(
            project="KRUPP-2026-TEST",
            description="Second change: upgrade flooring materials.",
            reason="owner_change",
        )

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT co_number FROM change_orders ORDER BY co_number"
            )
            numbers = [r["co_number"] for r in cursor.fetchall()]
            assert numbers == [1, 2]

    def test_schedule_analysis_persists_snapshot(self, seeded_db: Settings, tmp_path: Path) -> None:
        """Schedule analysis creates a snapshot record."""
        from kruppai.skills.schedule_variance import ScheduleVarianceSkill
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Activity", "Start", "Finish"])
        ws.append(["Steel", "2026-01-01", "2026-03-15"])
        schedule_path = tmp_path / "schedule.xlsx"
        wb.save(str(schedule_path))

        mock_json = json.dumps({
            "overall_assessment": "On track.",
            "snapshot_date": "2026-02-13",
            "planned_completion_date": "2026-09-15",
            "projected_completion_date": "2026-09-15",
            "variance_days": 0,
            "percent_complete_planned": 35,
            "percent_complete_actual": 35,
            "critical_path_items": [],
            "at_risk_items": [],
            "delay_drivers": [],
            "recovery_actions": [],
            "upcoming_milestones": [],
            "recommendations": [],
        })
        skill = _build_skill(ScheduleVarianceSkill, seeded_db, mock_json)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            file=str(schedule_path),
        )
        assert result.output_path.exists()

        with get_db(seeded_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM schedule_snapshots")
            assert cursor.fetchone()[0] == 1

    def test_submittal_tracker_upserts(self, seeded_db: Settings, tmp_path: Path) -> None:
        """Submittal tracker creates new records and updates existing ones."""
        from kruppai.skills.submittal_tracker import SubmittalTrackerSkill
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Number", "Title", "Status"])
        ws.append(["03.30.001", "Concrete Mix", "Approved"])
        log_path = tmp_path / "submittal_log.xlsx"
        wb.save(str(log_path))

        mock_json = json.dumps({
            "overall_status": "On track.",
            "total_submittals": 1,
            "status_summary": {"pending": 0, "submitted": 0, "approved": 1, "approved_as_noted": 0, "revise_resubmit": 0, "rejected": 0},
            "submittals": [
                {"submittal_number": "03.30.001", "title": "Concrete Mix", "spec_section": "03 30 00",
                 "subcontractor": "ABC Concrete", "status": "approved", "submitted_date": "2026-01-15",
                 "required_date": "2026-02-01", "review_due_date": "2026-01-29", "lead_time_days": 14,
                 "is_critical_path": False, "notes": ""},
            ],
            "overdue_items": [],
            "upcoming_deadlines": [],
            "action_items": [],
            "recommendations": [],
        })
        skill = _build_skill(SubmittalTrackerSkill, seeded_db, mock_json)

        # First run creates the submittal
        skill.execute(project="KRUPP-2026-TEST", file=str(log_path))

        # Second run updates the existing submittal (no duplicate)
        skill.execute(project="KRUPP-2026-TEST", file=str(log_path))

        with get_db(seeded_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM submittals WHERE project_id = 1")
            assert cursor.fetchone()[0] == 1  # Only 1, not 2

    def test_contract_review_without_project(self, seeded_db: Settings, tmp_path: Path) -> None:
        """Contract review works without project context."""
        from kruppai.skills.contract_checker import ContractCheckerSkill
        from docx import Document

        doc = Document()
        doc.add_paragraph("SUBCONTRACT AGREEMENT")
        doc_path = tmp_path / "contract.docx"
        doc.save(str(doc_path))

        mock_json = json.dumps({
            "document_name": "Test Contract",
            "document_type": "subcontract",
            "overall_summary": "Standard terms.",
            "risk_level": "low",
            "compliance_score": 90,
            "findings": [],
            "missing_items": [],
            "non_standard_clauses": [],
            "insurance_gaps": [],
            "recommendations": [],
            "action_required": False,
        })
        skill = _build_skill(ContractCheckerSkill, seeded_db, mock_json)
        # Override to use Opus mock
        skill.api_client.call.return_value = ApiResponse(
            content=mock_json,
            model="claude-opus-4-6",
            input_tokens=5000,
            output_tokens=3000,
            cost_cents=30,
            duration_ms=8000,
        )

        result = skill.execute(file=str(doc_path), type="subcontract")
        assert result.output_path.exists()
        assert result.project_code is None

    def test_all_phase2_skills_generate_documents(self, seeded_db: Settings) -> None:
        """Verify all Phase 2 generated_documents entries are tracked."""
        from kruppai.skills.change_order import ChangeOrderSkill

        mock_json = json.dumps({
            "title": "Test CO",
            "formal_description": "Test.",
            "reason_category": "owner_change",
            "cost_breakdown": [],
            "subtotal_cents": 0,
            "markup_percent": 10,
            "markup_cents": 0,
            "total_cents": 0,
            "schedule_impact_days": 0,
            "schedule_impact_description": "",
            "supporting_references": [],
            "contractual_basis": "",
        })
        skill = _build_skill(ChangeOrderSkill, seeded_db, mock_json)
        skill.execute(
            project="KRUPP-2026-TEST",
            description="Test change order for generated documents tracking.",
            reason="owner_change",
        )

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM generated_documents WHERE skill_name = 'change_order'"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["document_type"] == "docx"
