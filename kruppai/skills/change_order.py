"""Change Order Builder — Skill #9.

Takes a PM's rough notes about a scope change and generates a formal
change order proposal with cost breakdown, schedule impact, and
contractual justification.
"""

from __future__ import annotations

import json
from datetime import date
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

VALID_REASONS = {
    "owner_change",
    "design_error",
    "unforeseen_condition",
    "code_requirement",
    "value_engineering",
}

REASON_LABELS = {
    "owner_change": "Owner-Directed Change",
    "design_error": "Design Error/Omission",
    "unforeseen_condition": "Unforeseen Site Condition",
    "code_requirement": "Code/Regulatory Requirement",
    "value_engineering": "Value Engineering",
}


class ChangeOrderSkill(BaseSkill):
    """Generate formal change order proposals from rough notes."""

    skill_name = "change_order"
    display_name = "Change Order Builder"
    description = "Generate a formal change order proposal from rough notes"
    phase = 2
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate change order input.

        Required: project (code), description, reason.
        Optional: cost, schedule_days, markup_percent.
        """
        project_code = kwargs.get("project")
        description = kwargs.get("description")
        reason = kwargs.get("reason", "owner_change")
        cost = kwargs.get("cost")
        schedule_days = kwargs.get("schedule_days", 0)
        markup_percent = kwargs.get("markup", 10.0)

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not description:
            raise ValueError(
                "Change description is required. Use --description or -d."
            )

        desc_str = str(description)
        if len(desc_str.strip()) < 10:
            raise ValueError(
                "Description must be at least 10 characters."
            )

        reason_str = str(reason).lower()
        if reason_str not in VALID_REASONS:
            raise ValueError(
                f"Invalid reason: '{reason_str}'. "
                f"Valid options: {', '.join(sorted(VALID_REASONS))}"
            )

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "description": desc_str,
            "reason": reason_str,
            "cost_cents": int(float(str(cost)) * 100) if cost else None,
            "schedule_days": int(schedule_days) if schedule_days else 0,
            "markup_percent": float(markup_percent) if markup_percent else 10.0,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for change order generation."""
        company = context.company if context else {}
        project = context.project if context else {}

        project_context = ""
        if context:
            project_context = (
                f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})\n"
                f"Client: {project.get('client_name', 'N/A')}\n"
                f"Contract Type: {project.get('contract_type', 'N/A')}\n"
                f"Delivery Method: {project.get('delivery_method', 'N/A')}\n"
                f"Current Contract: ${project.get('current_contract_cents', 0) / 100:,.2f}\n"
            )

        # Get existing change orders for context
        co_summary = ""
        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "SELECT co_number, title, cost_cents, status "
                "FROM change_orders WHERE project_id = ? ORDER BY co_number",
                (validated["project_id"],),
            )
            rows = cursor.fetchall()
            if rows:
                lines = []
                for r in rows:
                    cost = r["cost_cents"] or 0
                    lines.append(
                        f"  CO #{r['co_number']}: {r['title']} — "
                        f"${cost / 100:,.2f} ({r['status']})"
                    )
                co_summary = "\n".join(lines)
            else:
                co_summary = "No existing change orders."

        cost_hint = ""
        if validated["cost_cents"]:
            cost_hint = f"\nEstimated cost provided by PM: ${validated['cost_cents'] / 100:,.2f}"

        reason_label = REASON_LABELS.get(validated["reason"], validated["reason"])

        system_prompt = f"""You are a senior construction project manager for {company.get('name', 'Krupp General Contractors')}.
You are preparing a formal change order proposal.

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

EXISTING CHANGE ORDERS:
{co_summary}

CHANGE ORDER REASON: {reason_label}
MARKUP PERCENTAGE: {validated['markup_percent']}%
{cost_hint}

INSTRUCTIONS:
1. Write a formal TITLE for this change order (max 80 characters).

2. Write a formal DESCRIPTION that:
   - Clearly states what is changing and why
   - References the contractual basis (e.g., "Per Section X of the Agreement...")
   - Is professional and suitable for owner review

3. Create a COST BREAKDOWN with line items:
   - Labor, material, equipment, subcontractor costs
   - Apply markup percentage
   - All amounts in cents for JSON

4. Assess SCHEDULE IMPACT:
   - Number of days added/subtracted
   - Impact on critical path activities
   - Mitigation approach if any

5. List any SUPPORTING REFERENCES:
   - Related RFIs, field observations, owner requests
   - Contract clauses that apply

6. OUTPUT FORMAT:
   Return JSON:
   {{
     "title": "Change Order title",
     "formal_description": "Formal description paragraph",
     "reason_category": "{validated['reason']}",
     "cost_breakdown": [
       {{"item": "Labor", "description": "", "amount_cents": 0}},
       {{"item": "Material", "description": "", "amount_cents": 0}},
       {{"item": "Equipment", "description": "", "amount_cents": 0}},
       {{"item": "Subcontractor", "description": "", "amount_cents": 0}}
     ],
     "subtotal_cents": 0,
     "markup_percent": {validated['markup_percent']},
     "markup_cents": 0,
     "total_cents": 0,
     "schedule_impact_days": {validated['schedule_days']},
     "schedule_impact_description": "",
     "supporting_references": ["ref1", "ref2"],
     "contractual_basis": "Relevant contract clause or provision"
   }}"""

        return [
            {"role": "user", "content": f"CHANGE DESCRIPTION:\n{validated['description']}"},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format change order as branded DOCX."""
        data = parse_claude_json(response)

        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        # Get CO number
        with get_db(self.settings) as conn:
            co_number = get_next_number(
                conn, "change_orders", validated["project_id"], "co_number"
            )

        # Header fields
        reason_label = REASON_LABELS.get(validated["reason"], validated["reason"])
        header_fields = {
            "Change Order Number": str(co_number),
            "Date": date.today().isoformat(),
            "Project": f"{project.get('name', '')} ({validated['project_code']})",
            "Owner": project.get("client_name", "N/A"),
            "Reason": reason_label,
        }

        # Sections
        sections: list[Section] = [
            Section("Description", data.get("formal_description", "")),
        ]

        if data.get("contractual_basis"):
            sections.append(
                Section("Contractual Basis", data["contractual_basis"])
            )

        # Schedule impact
        sched_days = data.get("schedule_impact_days", 0)
        sched_desc = data.get("schedule_impact_description", "")
        if sched_days or sched_desc:
            impact_text = f"Schedule Impact: {sched_days} calendar day(s)"
            if sched_desc:
                impact_text += f"\n\n{sched_desc}"
            sections.append(Section("Schedule Impact", impact_text))

        # Supporting references
        refs = data.get("supporting_references", [])
        if refs:
            sections.append(
                Section("Supporting References", "\n".join(f"- {r}" for r in refs))
            )

        # Signature block
        sections.append(
            Section(
                "Approval",
                "Submitted By: _________________________  Date: ____________\n\n"
                "Approved By:  _________________________  Date: ____________\n\n"
                "Owner Approval: _______________________  Date: ____________",
            )
        )

        # Cost breakdown table
        tables: list[TableData] = []
        breakdown = data.get("cost_breakdown", [])
        if breakdown:
            cost_rows = []
            for item in breakdown:
                amt = item.get("amount_cents", 0)
                cost_rows.append([
                    str(item.get("item", "")),
                    str(item.get("description", "")),
                    f"${amt / 100:,.2f}" if amt else "$0.00",
                ])
            # Add subtotal, markup, total
            subtotal = data.get("subtotal_cents", 0)
            markup = data.get("markup_cents", 0)
            total = data.get("total_cents", 0)
            cost_rows.append(["", "Subtotal", f"${subtotal / 100:,.2f}"])
            cost_rows.append([
                "",
                f"Markup ({data.get('markup_percent', 0)}%)",
                f"${markup / 100:,.2f}",
            ])
            cost_rows.append(["", "TOTAL", f"${total / 100:,.2f}"])

            tables.append(
                TableData(
                    headers=["Item", "Description", "Amount"],
                    rows=cost_rows,
                    title="Cost Breakdown",
                )
            )

        content = DocumentContent(
            title=f"Change Order Proposal — CO #{co_number}",
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist
        self._persist_change_order(validated, data, co_number, output_path)

        return output_path

    def _persist_change_order(
        self, validated: dict, data: dict, co_number: int, output_path: Path
    ) -> None:
        """Save change order to database."""
        total = data.get("total_cents", 0)
        subtotal = data.get("subtotal_cents", 0)

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO change_orders "
                "(project_id, co_number, title, description, raw_input, "
                "reason, cost_cents, markup_percent, total_with_markup_cents, "
                "schedule_impact_days, subcontractor_quotes, status, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    validated["project_id"],
                    co_number,
                    data.get("title", ""),
                    data.get("formal_description", ""),
                    validated["description"],
                    validated["reason"],
                    subtotal,
                    validated["markup_percent"],
                    total,
                    data.get("schedule_impact_days", 0),
                    json.dumps(data.get("cost_breakdown", [])),
                    str(output_path),
                ),
            )
