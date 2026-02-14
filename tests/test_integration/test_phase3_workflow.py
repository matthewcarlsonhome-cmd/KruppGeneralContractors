"""Integration tests for Phase 3 skills workflow."""

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


def _build_skill(skill_class, settings, mock_response_content):
    """Build any skill with mocked API returning given content."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=mock_response_content,
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


class TestPhase3Workflow:
    """Integration tests verifying Phase 3 skills work together."""

    def test_lessons_to_case_study_pipeline(self, seeded_db: Settings) -> None:
        """Lessons learned data feeds into case study generation."""
        from kruppai.skills.case_study import CaseStudySkill
        from kruppai.skills.lessons_learned import LessonsLearnedSkill

        # Step 1: Generate lessons learned
        lessons_json = json.dumps([
            {
                "title": "BIM coordination prevents rework",
                "category": "design",
                "situation": "MEP clashes found before rough-in via BIM.",
                "impact": "Saved 2 weeks of rework.",
                "lesson": "Run BIM clash detection early.",
                "recommendation": "Make BIM coordination a gate for rough-in.",
                "severity": "high",
                "applicable_project_types": ["healthcare"],
                "tags": ["BIM", "coordination"],
            },
        ])
        lessons_skill = _build_skill(
            LessonsLearnedSkill, seeded_db, lessons_json
        )
        lessons_result = lessons_skill.execute(
            project="KRUPP-2026-TEST",
            notes="BIM coordination was critical. Found 47 clashes before "
            "construction began, saving weeks of potential rework.",
        )
        assert lessons_result.output_path.exists()

        # Verify lesson was persisted
        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM lessons_learned WHERE project_id = 1"
            )
            assert cursor.fetchone()[0] == 1

        # Step 2: Generate case study (which queries lessons_learned)
        case_study_response = (
            "City Center Medical Office: BIM-Driven Healthcare Construction"
            "\n---SECTION BREAK---\n"
            "- 45,000 SF medical office\n- Zero rework from BIM coordination"
            "\n---SECTION BREAK---\n"
            "The project required complex MEP systems."
            "\n---SECTION BREAK---\n"
            "BIM coordination identified 47 clashes pre-construction."
            "\n---SECTION BREAK---\n"
            "Delivered on time with zero rework incidents."
            "\n---SECTION BREAK---\n"
            '{"contract_value": "$12.85M", "duration_months": 12, '
            '"square_footage": 45000, "on_time": true, "on_budget": true}'
            "\n---SECTION BREAK---\n"
            "Sarah Chen led the project team."
            "\n---SECTION BREAK---\n"
            '"Outstanding project delivery." — Dr. Amanda Foster'
        )
        case_study_skill = _build_skill(
            CaseStudySkill, seeded_db, case_study_response
        )
        cs_result = case_study_skill.execute(
            project="KRUPP-2026-TEST",
            notes="Project completed on time thanks to BIM coordination. "
            "Zero safety incidents. Client very satisfied.",
        )
        assert cs_result.output_path.exists()

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM case_studies WHERE project_id = 1"
            )
            assert cursor.fetchone()[0] == 1

    def test_incident_auto_numbering_across_executions(self, seeded_db: Settings) -> None:
        """Incident numbers auto-increment across separate skill executions."""
        from kruppai.skills.incident_report import IncidentReportSkill

        mock_json = json.dumps({
            "summary": "Test incident.",
            "location": "First floor",
            "involved_persons": [],
            "witnesses": [],
            "immediate_actions": "Area secured.",
            "root_cause": "Unsecured material.",
            "contributing_factors": ["Poor housekeeping"],
            "corrective_actions": [],
            "preventive_actions": ["Improve housekeeping"],
            "is_osha_recordable": False,
            "osha_notification_required": False,
            "severity": "minor",
        })
        skill = _build_skill(IncidentReportSkill, seeded_db, mock_json)

        # Execute three incidents
        for i in range(3):
            skill.execute(
                project="KRUPP-2026-TEST",
                description=f"Incident number {i + 1}: near miss with falling debris on floor {i + 1}.",
                type="near_miss",
                date="2026-02-13",
            )

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT incident_number FROM incident_reports "
                "WHERE project_id = 1 ORDER BY incident_number"
            )
            numbers = [row["incident_number"] for row in cursor.fetchall()]
            assert numbers == [1, 2, 3]

    def test_closeout_persists_package(self, seeded_db: Settings) -> None:
        """Closeout assembler creates a persistent package record."""
        from kruppai.skills.closeout_assembler import CloseoutAssemblerSkill

        mock_json = json.dumps({
            "cover_letter_text": "Dear client, closeout is underway.",
            "status_summary": {
                "total_items": 10,
                "complete": 3,
                "in_progress": 4,
                "not_started": 2,
                "not_applicable": 1,
                "percent_complete": 30.0,
            },
            "checklist_items": [
                {
                    "item_name": "Final Lien Waivers",
                    "category": "Contractual",
                    "responsible_party": "Krupp",
                    "status": "in_progress",
                    "due_date": "2026-09-30",
                    "notes": "Awaiting sub waivers",
                },
            ],
            "items_by_responsibility": [
                {"party": "Krupp", "total": 10, "complete": 3, "outstanding": 7},
            ],
            "recommendations": ["Follow up on lien waivers"],
        })
        skill = _build_skill(CloseoutAssemblerSkill, seeded_db, mock_json)

        result = skill.execute(
            project="KRUPP-2026-TEST",
            notes="All MEP rough-ins complete. Punch list down to 15 items. "
            "Waiting on final lien waivers from subs.",
        )
        assert result.output_path.exists()

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM closeout_packages WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["status"] == "in_progress"
            assert "KRUPP-2026-TEST" in row["package_name"]

    def test_all_phase3_skills_track_documents(self, seeded_db: Settings) -> None:
        """Verify all Phase 3 skills create generated_documents entries."""
        from kruppai.skills.incident_report import IncidentReportSkill
        from kruppai.skills.lessons_learned import LessonsLearnedSkill

        # Lessons learned
        lessons_json = json.dumps([
            {
                "title": "Test lesson",
                "category": "safety",
                "situation": "Test situation.",
                "impact": "Test impact.",
                "lesson": "Test lesson content.",
                "recommendation": "Test recommendation.",
                "severity": "medium",
                "applicable_project_types": ["commercial"],
                "tags": ["test"],
            },
        ])
        lessons_skill = _build_skill(
            LessonsLearnedSkill, seeded_db, lessons_json
        )
        lessons_skill.execute(
            project="KRUPP-2026-TEST",
            notes="Safety lessons learned from the project construction phase.",
        )

        # Incident report
        incident_json = json.dumps({
            "summary": "Test incident.",
            "location": "First floor",
            "involved_persons": [],
            "witnesses": [],
            "immediate_actions": "Area secured.",
            "root_cause": "Root cause.",
            "contributing_factors": [],
            "corrective_actions": [],
            "preventive_actions": [],
            "is_osha_recordable": False,
            "osha_notification_required": False,
            "severity": "minor",
        })
        incident_skill = _build_skill(
            IncidentReportSkill, seeded_db, incident_json
        )
        incident_skill.execute(
            project="KRUPP-2026-TEST",
            description="Near miss with unsecured material falling from scaffold.",
            type="near_miss",
            date="2026-02-13",
        )

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT skill_name FROM generated_documents "
                "WHERE skill_name IN ('lessons_learned', 'incident_report') "
                "ORDER BY skill_name"
            )
            skill_names = [row["skill_name"] for row in cursor.fetchall()]
            assert "incident_report" in skill_names
            assert "lessons_learned" in skill_names

    def test_budget_forecast_full_cycle(self, seeded_db: Settings, sample_xlsx: Path) -> None:
        """Budget forecast: parse file -> analyze -> generate DOCX + XLSX -> persist."""
        from kruppai.skills.budget_forecaster import BudgetForecasterSkill

        mock_json = json.dumps({
            "health_status": "on_track",
            "executive_summary": "Project is on track financially.",
            "original_budget_cents": 1_250_000_000,
            "approved_changes_cents": 0,
            "current_budget_cents": 1_250_000_000,
            "committed_costs_cents": 1_000_000_000,
            "actual_costs_cents": 400_000_000,
            "projected_final_cents": 1_240_000_000,
            "variance_cents": 10_000_000,
            "contingency_remaining_cents": 60_000_000,
            "contingency_recommended_cents": 50_000_000,
            "budget_lines": [],
            "risk_items": [],
            "recommendations": [],
        })
        skill = _build_skill(BudgetForecasterSkill, seeded_db, mock_json)
        result = skill.execute(
            project="KRUPP-2026-TEST",
            file=str(sample_xlsx),
        )
        assert result.output_path.exists()

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM budget_forecasts WHERE project_id = 1"
            )
            assert cursor.fetchone()[0] == 1
