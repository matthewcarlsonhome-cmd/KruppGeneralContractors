"""Tests for the Contract & Insurance Checker skill."""

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
from kruppai.skills.contract_checker import ContractCheckerSkill


MOCK_CONTRACT_REVIEW_JSON = json.dumps({
    "document_name": "ABC Electrical Subcontract Agreement",
    "document_type": "subcontract",
    "overall_summary": "The subcontract is generally acceptable with standard AIA terms. "
    "However, there are concerns about the indemnification clause being overly broad "
    "and the lack of a waiver of consequential damages.",
    "risk_level": "medium",
    "compliance_score": 78,
    "findings": [
        {
            "item": "Broad Form Indemnification",
            "severity": "high",
            "description": "Section 8.1 contains a broad form indemnification that may not be enforceable "
            "in Colorado and exposes Krupp to excessive liability.",
            "recommendation": "Negotiate to intermediate form indemnification per AIA A401 standard.",
            "clause_reference": "Section 8.1",
        },
        {
            "item": "Missing Waiver of Consequential Damages",
            "severity": "medium",
            "description": "No mutual waiver of consequential damages is included.",
            "recommendation": "Add standard AIA mutual waiver of consequential damages clause.",
            "clause_reference": None,
        },
    ],
    "missing_items": [
        {
            "item": "Dispute Resolution Clause",
            "importance": "required",
            "impact": "No defined process for resolving disputes may lead to costly litigation.",
        },
    ],
    "non_standard_clauses": [
        {
            "clause": "Pay-if-paid provision in Section 5.3",
            "concern": "Pay-if-paid clauses are disfavored in Colorado and may be unenforceable.",
            "risk": "medium",
        },
    ],
    "insurance_gaps": [],
    "recommendations": [
        "Negotiate indemnification to intermediate form",
        "Add mutual waiver of consequential damages",
        "Replace pay-if-paid with pay-when-paid language",
        "Add dispute resolution via mediation then arbitration",
    ],
    "action_required": True,
})

MOCK_INSURANCE_REVIEW_JSON = json.dumps({
    "document_name": "Pacific Mechanical Certificate of Insurance",
    "document_type": "insurance_cert",
    "overall_summary": "Insurance certificate shows adequate general liability coverage but has "
    "gaps in umbrella coverage and is missing additional insured endorsement.",
    "risk_level": "high",
    "compliance_score": 62,
    "findings": [
        {
            "item": "Missing Additional Insured Endorsement",
            "severity": "critical",
            "description": "The certificate does not list Krupp GC as additional insured.",
            "recommendation": "Request amended certificate with AI endorsement before work begins.",
            "clause_reference": None,
        },
    ],
    "missing_items": [
        {
            "item": "Additional Insured Endorsement",
            "importance": "required",
            "impact": "Krupp has no coverage under sub's policy without this endorsement.",
        },
    ],
    "non_standard_clauses": [],
    "insurance_gaps": [
        {
            "coverage_type": "Umbrella/Excess Liability",
            "required": "$5,000,000",
            "provided": "$2,000,000",
            "gap": "$3,000,000 shortfall",
        },
    ],
    "recommendations": [
        "Request additional insured endorsement immediately",
        "Require umbrella increase to $5M before contract execution",
    ],
    "action_required": True,
})


def _make_skill(settings: Settings) -> ContractCheckerSkill:
    """Build a ContractCheckerSkill with mocked API client."""
    mock_api = MagicMock()
    mock_api.call.return_value = ApiResponse(
        content=MOCK_CONTRACT_REVIEW_JSON,
        model="claude-opus-4-6",
        input_tokens=8000,
        output_tokens=4000,
        cost_cents=42,
        duration_ms=12000,
    )
    mock_api.settings = settings
    return ContractCheckerSkill(
        settings=settings,
        api_client=mock_api,
        formatter=OutputFormatter(settings),
        context_manager=ContextManager(settings),
        knowledge_base=KnowledgeBase(settings),
    )


def _create_contract_pdf(tmp_path: Path) -> Path:
    """Create a minimal PDF for testing."""
    # Create a simple DOCX since our parser supports it
    from docx import Document

    doc = Document()
    doc.add_paragraph("SUBCONTRACT AGREEMENT")
    doc.add_paragraph("Between Krupp General Contractors and ABC Electrical Services")
    doc.add_paragraph("Section 5.3: Payment shall be made within 30 days of receipt.")
    doc.add_paragraph("Section 8.1: Subcontractor shall indemnify and hold harmless...")
    path = tmp_path / "subcontract.docx"
    doc.save(str(path))
    return path


class TestContractCheckerValidation:
    """Test input validation for contract checker."""

    def test_validate_input_valid(self, seeded_db: Settings, tmp_path: Path) -> None:
        contract_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            file=str(contract_file),
            type="subcontract",
            project="KRUPP-2026-TEST",
        )
        assert result["document_type"] == "subcontract"
        assert result["project_id"] == 1

    def test_validate_input_no_project(self, seeded_db: Settings, tmp_path: Path) -> None:
        """Contract review works without a project."""
        contract_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            file=str(contract_file),
            type="subcontract",
        )
        assert result["project_id"] is None

    def test_validate_input_missing_file(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Document file is required"):
            skill.validate_input(type="subcontract")

    def test_validate_input_file_not_found(self, seeded_db: Settings) -> None:
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="File not found"):
            skill.validate_input(
                file="/nonexistent/contract.pdf",
                type="subcontract",
            )

    def test_validate_input_wrong_format(self, seeded_db: Settings, tmp_path: Path) -> None:
        bad_file = tmp_path / "contract.xlsx"
        from openpyxl import Workbook
        wb = Workbook()
        wb.save(str(bad_file))
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="must be in PDF or DOCX"):
            skill.validate_input(file=str(bad_file), type="subcontract")

    def test_validate_input_invalid_type(self, seeded_db: Settings, tmp_path: Path) -> None:
        contract_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        with pytest.raises(ValueError, match="Invalid document type"):
            skill.validate_input(
                file=str(contract_file),
                type="purchase_order",
            )

    def test_validate_input_insurance_cert(self, seeded_db: Settings, tmp_path: Path) -> None:
        cert_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.validate_input(
            file=str(cert_file),
            type="insurance_cert",
        )
        assert result["document_type"] == "insurance_cert"


class TestContractCheckerOutput:
    """Test output formatting for contract checker."""

    def test_format_output_creates_file(self, seeded_db: Settings, tmp_path: Path) -> None:
        contract_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(contract_file),
            "document_type": "subcontract",
        }
        output_path = skill.format_output(MOCK_CONTRACT_REVIEW_JSON, context, validated)
        assert output_path.exists()
        assert output_path.suffix == ".docx"

    def test_format_output_persists(self, seeded_db: Settings, tmp_path: Path) -> None:
        contract_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(contract_file),
            "document_type": "subcontract",
        }
        skill.format_output(MOCK_CONTRACT_REVIEW_JSON, context, validated)

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM contract_reviews WHERE project_id = 1"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["risk_level"] == "medium"
            assert row["compliance_score"] == 78

    def test_format_insurance_review(self, seeded_db: Settings, tmp_path: Path) -> None:
        """Insurance reviews include coverage gap analysis."""
        cert_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        # Override mock response with insurance review
        skill.api_client.call.return_value = ApiResponse(
            content=MOCK_INSURANCE_REVIEW_JSON,
            model="claude-opus-4-6",
            input_tokens=6000,
            output_tokens=3000,
            cost_cents=32,
            duration_ms=10000,
        )
        context = skill.context_manager.load_by_code("KRUPP-2026-TEST")
        validated = {
            "project_id": 1,
            "project_code": "KRUPP-2026-TEST",
            "file_path": str(cert_file),
            "document_type": "insurance_cert",
        }
        output_path = skill.format_output(MOCK_INSURANCE_REVIEW_JSON, context, validated)
        assert output_path.exists()

        with get_db(seeded_db) as conn:
            cursor = conn.execute(
                "SELECT * FROM contract_reviews WHERE document_type = 'insurance_cert'"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["risk_level"] == "high"
            gaps = json.loads(row["insurance_gaps"])
            assert len(gaps) == 1


class TestContractCheckerEndToEnd:
    """Test full contract checker lifecycle."""

    def test_execute_end_to_end(self, seeded_db: Settings, tmp_path: Path) -> None:
        contract_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.execute(
            file=str(contract_file),
            type="subcontract",
            project="KRUPP-2026-TEST",
        )
        assert result.output_path.exists()
        assert result.skill_name == "contract_checker"
        assert result.project_code == "KRUPP-2026-TEST"

    def test_execute_without_project(self, seeded_db: Settings, tmp_path: Path) -> None:
        """Contract review works without project context."""
        contract_file = _create_contract_pdf(tmp_path)
        skill = _make_skill(seeded_db)
        result = skill.execute(
            file=str(contract_file),
            type="subcontract",
        )
        assert result.output_path.exists()
        assert result.project_code is None
