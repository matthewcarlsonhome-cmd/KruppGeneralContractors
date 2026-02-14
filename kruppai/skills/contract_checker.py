"""Contract & Insurance Checker — Skill #12.

Parses a subcontract or insurance certificate (PDF), checks for missing
provisions, non-standard clauses, coverage gaps, and compliance issues.
Uses Opus model for legal/financial precision.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from kruppai.core.api_client import parse_claude_json
from kruppai.core.context_manager import ProjectContext
from kruppai.core.database import get_db
from kruppai.core.document_parser import parse_file
from kruppai.core.output_formatter import (
    DocumentContent,
    ProjectInfo,
    Section,
    TableData,
)
from kruppai.skills.base import BaseSkill

VALID_DOCUMENT_TYPES = {
    "subcontract",
    "prime_contract",
    "insurance_cert",
    "bond",
}

DOCUMENT_TYPE_LABELS = {
    "subcontract": "Subcontract Agreement",
    "prime_contract": "Prime Contract",
    "insurance_cert": "Insurance Certificate",
    "bond": "Surety Bond",
}


class ContractCheckerSkill(BaseSkill):
    """Review contracts and insurance certificates for compliance issues."""

    skill_name = "contract_checker"
    display_name = "Contract & Insurance Checker"
    description = "Review a contract or insurance cert for compliance and risk"
    phase = 2
    default_model = "opus"  # Legal precision required
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate contract review input.

        Required: file (path to PDF), type (document type).
        Optional: project.
        """
        file_path = kwargs.get("file")
        doc_type = kwargs.get("type", "subcontract")
        project_code = kwargs.get("project")

        if not file_path:
            raise ValueError("Document file is required. Use --file or -f.")

        path = Path(str(file_path))
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        if path.suffix.lower() not in {".pdf", ".docx"}:
            raise ValueError(
                "Document must be in PDF or DOCX format."
            )

        doc_type_str = str(doc_type).lower()
        if doc_type_str not in VALID_DOCUMENT_TYPES:
            raise ValueError(
                f"Invalid document type: '{doc_type_str}'. "
                f"Valid options: {', '.join(sorted(VALID_DOCUMENT_TYPES))}"
            )

        project_id = None
        if project_code:
            context = self.context_manager.load_by_code(str(project_code))
            project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code) if project_code else None,
            "file_path": str(path),
            "document_type": doc_type_str,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for contract review."""
        company = context.company if context else {}

        # Parse the document
        parsed = parse_file(Path(validated["file_path"]))
        if parsed.error:
            raise ValueError(f"Could not parse document: {parsed.error}")

        doc_type_label = DOCUMENT_TYPE_LABELS.get(
            validated["document_type"], validated["document_type"]
        )

        project_context = ""
        if context:
            project = context.project
            project_context = (
                f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})\n"
                f"Contract Type: {project.get('contract_type', 'N/A')}\n"
                f"Delivery Method: {project.get('delivery_method', 'N/A')}\n"
            )

        # Build type-specific instructions
        if validated["document_type"] == "insurance_cert":
            type_instructions = self._insurance_instructions()
        elif validated["document_type"] in ("subcontract", "prime_contract"):
            type_instructions = self._contract_instructions()
        else:
            type_instructions = self._bond_instructions()

        system_prompt = f"""You are a senior construction risk manager and contract reviewer for {company.get('name', 'Krupp General Contractors')}.
You are reviewing a {doc_type_label} for compliance, risk, and completeness.

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

{type_instructions}

GENERAL INSTRUCTIONS:
1. Risk level should be: 'low', 'medium', 'high', or 'critical'
2. Compliance score: 0-100 where 100 is fully compliant
3. Be specific about clause numbers and page references when possible
4. Flag anything unusual or non-standard
5. Provide actionable recommendations

OUTPUT FORMAT:
Return JSON:
{{
  "document_name": "Name/title of the document",
  "document_type": "{validated['document_type']}",
  "overall_summary": "Executive summary paragraph",
  "risk_level": "low|medium|high|critical",
  "compliance_score": 0,
  "findings": [
    {{
      "item": "Finding title",
      "severity": "info|low|medium|high|critical",
      "description": "Detailed finding",
      "recommendation": "What to do about it",
      "clause_reference": "Section/clause number if applicable"
    }}
  ],
  "missing_items": [
    {{"item": "Required item not found", "importance": "required|recommended", "impact": "Impact if missing"}}
  ],
  "non_standard_clauses": [
    {{"clause": "Clause text or summary", "concern": "Why it's non-standard", "risk": "low|medium|high"}}
  ],
  "insurance_gaps": [
    {{"coverage_type": "", "required": "", "provided": "", "gap": ""}}
  ],
  "recommendations": ["rec1", "rec2"],
  "action_required": true
}}"""

        return [
            {"role": "user", "content": f"DOCUMENT TO REVIEW ({doc_type_label}):\n{parsed.text[:50000]}"},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format contract review as DOCX report."""
        data = parse_claude_json(response)

        project_info = ProjectInfo(
            project_code=validated.get("project_code") or "REVIEW",
            name=context.project.get("name", "") if context else "",
            client_name="",
        )

        doc_type_label = DOCUMENT_TYPE_LABELS.get(
            validated["document_type"], validated["document_type"]
        )

        # Sections
        sections = [
            Section("Executive Summary", data.get("overall_summary", "")),
            Section(
                "Risk Assessment",
                f"Risk Level: {data.get('risk_level', 'N/A').upper()}\n"
                f"Compliance Score: {data.get('compliance_score', 0)}/100",
            ),
        ]

        # Findings
        findings = data.get("findings", [])
        if findings:
            lines = []
            for f in findings:
                ref = f" [{f.get('clause_reference', '')}]" if f.get("clause_reference") else ""
                lines.append(
                    f"[{f.get('severity', '?').upper()}]{ref} {f.get('item', '')}\n"
                    f"  {f.get('description', '')}\n"
                    f"  Recommendation: {f.get('recommendation', 'N/A')}"
                )
            sections.append(Section("Findings", "\n\n".join(lines)))

        # Missing items
        missing = data.get("missing_items", [])
        if missing:
            lines = []
            for m in missing:
                lines.append(
                    f"- [{m.get('importance', '?').upper()}] {m.get('item', '')}: "
                    f"{m.get('impact', '')}"
                )
            sections.append(Section("Missing Items", "\n".join(lines)))

        # Non-standard clauses
        non_standard = data.get("non_standard_clauses", [])
        if non_standard:
            lines = []
            for ns in non_standard:
                lines.append(
                    f"- [{ns.get('risk', '?').upper()}] {ns.get('clause', '')}\n"
                    f"  Concern: {ns.get('concern', '')}"
                )
            sections.append(Section("Non-Standard Clauses", "\n".join(lines)))

        # Insurance gaps (if insurance cert)
        gaps = data.get("insurance_gaps", [])
        if gaps:
            lines = []
            for g in gaps:
                lines.append(
                    f"- {g.get('coverage_type', '')}: "
                    f"Required: {g.get('required', 'N/A')}, "
                    f"Provided: {g.get('provided', 'N/A')}, "
                    f"Gap: {g.get('gap', 'N/A')}"
                )
            sections.append(Section("Insurance Gaps", "\n".join(lines)))

        # Recommendations
        recs = data.get("recommendations", [])
        if recs:
            sections.append(
                Section("Recommendations", "\n".join(f"- {r}" for r in recs))
            )

        # Findings table
        tables = []
        if findings:
            f_rows = []
            for f in findings:
                f_rows.append([
                    str(f.get("severity", "")).upper(),
                    str(f.get("item", "")),
                    str(f.get("recommendation", "")),
                ])
            tables.append(
                TableData(
                    headers=["Severity", "Finding", "Recommendation"],
                    rows=f_rows,
                    title="Findings Summary",
                )
            )

        content = DocumentContent(
            title=f"{doc_type_label} Review Report",
            date=date.today().isoformat(),
            header_fields={
                "Document": data.get("document_name", Path(validated["file_path"]).name),
                "Type": doc_type_label,
                "Risk Level": data.get("risk_level", "N/A").upper(),
                "Compliance Score": f"{data.get('compliance_score', 0)}/100",
            },
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist
        self._persist_review(validated, data, output_path)

        return output_path

    def _insurance_instructions(self) -> str:
        """Return insurance-specific review instructions."""
        return """INSURANCE CERTIFICATE REVIEW:
1. Verify required coverage types:
   - Commercial General Liability (min $1M per occurrence, $2M aggregate)
   - Automobile Liability (min $1M combined single limit)
   - Workers' Compensation (statutory limits)
   - Umbrella/Excess Liability (min $5M)
   - Professional Liability (if applicable)

2. Check:
   - Certificate holder is correctly named
   - Additional insured endorsement is included
   - Waiver of subrogation is included
   - Policy dates cover the project duration
   - Per-project aggregate (for CGL)
   - All required endorsements listed

3. Flag any coverage gaps, expired policies, or missing endorsements."""

    def _contract_instructions(self) -> str:
        """Return contract-specific review instructions."""
        return """CONTRACT REVIEW:
1. Check for REQUIRED provisions:
   - Scope of work clearly defined
   - Contract sum and payment terms
   - Schedule requirements and liquidated damages
   - Insurance requirements (matching project requirements)
   - Indemnification clause (mutual or one-sided?)
   - Dispute resolution mechanism
   - Change order procedures
   - Warranty provisions
   - Termination clauses (for cause and convenience)
   - Pay-if-paid vs pay-when-paid
   - Retainage terms

2. Flag NON-STANDARD clauses:
   - Unusual indemnification (broad form, additional insured)
   - Onerous payment terms (>30 days)
   - Excessive liquidated damages
   - Unusual termination provisions
   - Hidden liability shifts
   - Waiver of consequential damages (or lack thereof)

3. Assess flow-down provisions (if subcontract):
   - Do prime contract obligations properly flow down?
   - Are scope gaps created by flow-down?"""

    def _bond_instructions(self) -> str:
        """Return bond-specific review instructions."""
        return """BOND REVIEW:
1. Verify:
   - Bond type (performance, payment, bid, maintenance)
   - Principal correctly named
   - Obligee correctly named
   - Surety is on Treasury list (note if unable to verify)
   - Bond amount matches contract value
   - Bond form is standard (AIA A312 or equivalent)
   - Effective dates cover project duration

2. Flag any non-standard conditions or limitations."""

    def _persist_review(
        self, validated: dict, data: dict, output_path: Path
    ) -> None:
        """Persist contract review to database."""
        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO contract_reviews "
                "(project_id, document_name, document_type, source_file_path, "
                "review_date, risk_level, findings, missing_items, "
                "non_standard_clauses, insurance_gaps, compliance_score, "
                "summary, recommendations, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated.get("project_id"),
                    data.get("document_name", Path(validated["file_path"]).name),
                    validated["document_type"],
                    validated["file_path"],
                    date.today().isoformat(),
                    data.get("risk_level"),
                    json.dumps(data.get("findings", [])),
                    json.dumps(data.get("missing_items", [])),
                    json.dumps(data.get("non_standard_clauses", [])),
                    json.dumps(data.get("insurance_gaps", [])),
                    data.get("compliance_score"),
                    data.get("overall_summary", ""),
                    json.dumps(data.get("recommendations", [])),
                    str(output_path),
                ),
            )
