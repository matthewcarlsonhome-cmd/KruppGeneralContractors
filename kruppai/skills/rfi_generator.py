"""RFI Generator — Skill #2.

Transforms a PM's rough description of a design question into a formal,
numbered RFI with spec references, cost/schedule impact flags, and
suggested resolution.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from kruppai.core.api_client import parse_claude_json
from kruppai.core.context_manager import ProjectContext
from kruppai.core.database import get_db, get_next_number
from kruppai.core.output_formatter import (
    DocumentContent,
    ProjectInfo,
    Section,
    TableData,
)
from kruppai.skills.base import BaseSkill


class RfiGeneratorSkill(BaseSkill):
    """Generate formal RFIs from rough issue descriptions."""

    skill_name = "rfi_generator"
    display_name = "RFI Generator"
    description = "Transform issue descriptions into formal RFI documents"
    phase = 1
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate RFI input.

        Required: project (code), issue (description).
        Optional: to, priority, drawing_ref, spec_ref.
        """
        project_code = kwargs.get("project")
        issue = kwargs.get("issue")
        to = kwargs.get("to", "Architect")
        priority = kwargs.get("priority", "normal")
        drawing_ref = kwargs.get("drawing_ref")
        spec_ref = kwargs.get("spec_ref")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not issue:
            raise ValueError(
                "Issue description is required. Use --issue or -i."
            )

        issue_str = str(issue)
        if len(issue_str.strip()) < 10:
            raise ValueError(
                "Issue description must be at least 10 characters."
            )

        valid_priorities = {"urgent", "high", "normal", "low"}
        priority_str = str(priority).lower()
        if priority_str not in valid_priorities:
            raise ValueError(
                f"Priority must be one of: {', '.join(valid_priorities)}"
            )

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "issue": issue_str,
            "to": str(to),
            "priority": priority_str,
            "drawing_ref": str(drawing_ref) if drawing_ref else None,
            "spec_ref": str(spec_ref) if spec_ref else None,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for RFI generation."""
        project = context.project if context else {}
        company = context.company if context else {}

        # Build project context string
        project_context = self._format_project_context(context)

        # Get existing RFIs summary
        rfi_summary = "No existing RFIs."
        if context:
            with get_db(self.settings) as conn:
                cursor = conn.execute(
                    "SELECT rfi_number, subject, status FROM rfis "
                    "WHERE project_id = ? ORDER BY rfi_number",
                    (validated["project_id"],),
                )
                rows = cursor.fetchall()
                if rows:
                    lines = [
                        f"  RFI #{r['rfi_number']}: {r['subject']} ({r['status']})"
                        for r in rows
                    ]
                    rfi_summary = "\n".join(lines)

        writing_standards = self.knowledge_base.load_file("writing_standards") or ""

        system_prompt = f"""You are a professional construction RFI writer for {company.get('name', 'Krupp General Contractors')}, a general contractor.

Your task: Transform the project manager's rough description of a design issue into a formal Request for Information (RFI) document.

PROJECT CONTEXT:
{project_context}

OPEN RFIs ON THIS PROJECT:
{rfi_summary}

WRITING STANDARDS:
{writing_standards}

INSTRUCTIONS:
1. Write a clear, specific SUBJECT LINE (max 80 characters) that identifies the issue precisely.

2. Write a formal QUESTION section that:
   - States the discrepancy or missing information clearly
   - References specific drawing sheets and/or spec sections when mentioned
   - Is written as a direct question to the architect/engineer
   - Is factual and non-accusatory

3. Assess IMPACT:
   - Cost Impact: 'none', 'potential', or 'confirmed' with brief explanation
   - Schedule Impact: 'none', 'potential', or 'confirmed' with brief explanation
   - Note any upcoming deadlines that make this time-sensitive

4. Write a SUGGESTED RESOLUTION if the PM's notes imply one. If not, omit this section.

5. CRITICAL RULES:
   - RFIs are contractual documents. Every word matters.
   - Be precise with drawing/spec references.
   - Never assume the answer — the point is to ASK.
   - Flag urgency clearly if schedule is impacted.
   - Use [VERIFY] for any references you're uncertain about.

6. OUTPUT FORMAT:
   Return JSON:
   {{
     "subject": "RFI subject line",
     "question": "Formal question text",
     "spec_reference": "Section X.X.X or null",
     "drawing_reference": "Sheet A-xxx or null",
     "cost_impact": "none|potential|confirmed",
     "cost_impact_notes": "explanation or null",
     "schedule_impact": "none|potential|confirmed",
     "schedule_impact_notes": "explanation or null",
     "suggested_solution": "Suggested resolution or null",
     "priority": "urgent|high|normal|low"
   }}"""

        user_content = f"ISSUE DESCRIPTION:\n{validated['issue']}"
        if validated.get("drawing_ref"):
            user_content += f"\n\nDRAWING REFERENCE: {validated['drawing_ref']}"
        if validated.get("spec_ref"):
            user_content += f"\n\nSPEC REFERENCE: {validated['spec_ref']}"
        user_content += f"\n\nPRIORITY: {validated['priority']}"
        user_content += f"\n\nDIRECTED TO: {validated['to']}"

        return [
            {"role": "user", "content": user_content},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format the RFI as a branded DOCX."""
        data = parse_claude_json(response)

        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        # Get RFI number
        with get_db(self.settings) as conn:
            rfi_number = get_next_number(
                conn, "rfis", validated["project_id"], "rfi_number"
            )

        # Calculate response due date
        priority = data.get("priority", validated["priority"])
        if priority == "urgent":
            due_days = 3
        else:
            due_days = 14
        response_due = (date.today() + timedelta(days=due_days)).isoformat()

        # Header fields
        header_fields = {
            "RFI Number": str(rfi_number),
            "Date": date.today().isoformat(),
            "Project": f"{project.get('name', '')} ({validated['project_code']})",
            "To": validated["to"],
            "From": "Krupp General Contractors",
            "Priority": priority.upper(),
            "Response Due": response_due,
        }

        # Sections
        sections: list[Section] = []

        sections.append(
            Section("Subject", data.get("subject", "No subject provided"))
        )
        sections.append(
            Section("Question", data.get("question", "No question provided"))
        )

        # Spec/drawing references
        refs = []
        if data.get("spec_reference"):
            refs.append(f"Specification: {data['spec_reference']}")
        if data.get("drawing_reference"):
            refs.append(f"Drawing: {data['drawing_reference']}")
        if refs:
            sections.append(Section("References", "\n".join(refs)))

        if data.get("suggested_solution"):
            sections.append(
                Section("Suggested Resolution", data["suggested_solution"])
            )

        # Impact assessment table
        tables: list[TableData] = []
        impact_rows = [
            [
                "Cost Impact",
                (data.get("cost_impact") or "unknown").upper(),
                data.get("cost_impact_notes") or "N/A",
            ],
            [
                "Schedule Impact",
                (data.get("schedule_impact") or "unknown").upper(),
                data.get("schedule_impact_notes") or "N/A",
            ],
        ]
        tables.append(
            TableData(
                headers=["Impact Type", "Status", "Notes"],
                rows=impact_rows,
                title="Impact Assessment",
            )
        )

        # Response section (blank)
        sections.append(
            Section(
                "Response",
                "Response: _______________________________________________\n\n"
                "Responded By: ________________  Date: ________________",
            )
        )

        content = DocumentContent(
            title=f"Request for Information — RFI #{rfi_number}",
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist to rfis table
        self._persist_rfi(validated, data, rfi_number, response_due, output_path)

        return output_path

    def _persist_rfi(
        self,
        validated: dict,
        data: dict,
        rfi_number: int,
        response_due: str,
        output_path: Path,
    ) -> None:
        """Save RFI data to the rfis table."""
        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO rfis "
                "(project_id, rfi_number, subject, question, raw_input, "
                "spec_reference, drawing_reference, cost_impact, "
                "schedule_impact, suggested_solution, priority, "
                "assigned_to, status, response_due_date, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)",
                (
                    validated["project_id"],
                    rfi_number,
                    data.get("subject", ""),
                    data.get("question", ""),
                    validated["issue"],
                    data.get("spec_reference"),
                    data.get("drawing_reference"),
                    data.get("cost_impact", "unknown"),
                    data.get("schedule_impact", "unknown"),
                    data.get("suggested_solution"),
                    data.get("priority", validated["priority"]),
                    validated["to"],
                    response_due,
                    str(output_path),
                ),
            )

    def _format_project_context(self, context: ProjectContext | None) -> str:
        """Format full project context for the prompt."""
        if not context:
            return "No project context available."

        project = context.project
        contract_display = "N/A"
        if project.get("current_contract_cents"):
            contract_display = f"${project['current_contract_cents'] / 100:,.2f}"

        lines = [
            f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})",
            f"Client: {project.get('client_name', 'N/A')}",
            f"Location: {project.get('address', 'N/A')}",
            f"Contract Value: {contract_display}",
            f"Percent Complete: {project.get('current_percent_complete', 0)}%",
        ]

        if context.subcontractors:
            lines.append("\nSubcontractors:")
            for sub in context.subcontractors:
                lines.append(
                    f"  - {sub['company_name']} ({sub['trade']}): "
                    f"{sub.get('scope_description', 'N/A')}"
                )

        return "\n".join(lines)
