"""Incident Report — Skill #18.

Takes a PM's or superintendent's rough account of a jobsite incident and
generates a formal incident report with root cause analysis, corrective
actions, OSHA classification, and signature blocks.
"""

from __future__ import annotations

import json
from datetime import date, datetime
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

VALID_INCIDENT_TYPES = {
    "near_miss",
    "first_aid",
    "recordable",
    "lost_time",
    "property_damage",
    "environmental",
}

INCIDENT_TYPE_LABELS = {
    "near_miss": "Near Miss",
    "first_aid": "First Aid",
    "recordable": "OSHA Recordable",
    "lost_time": "Lost Time Injury",
    "property_damage": "Property Damage",
    "environmental": "Environmental Release",
}

SEVERITY_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}


class IncidentReportSkill(BaseSkill):
    """Generate formal incident reports from rough field accounts."""

    skill_name = "incident_report"
    display_name = "Incident Report"
    description = "Generate a formal incident report from a field description"
    phase = 3
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate incident report input.

        Required: project (code), description, type.
        Optional: date (YYYY-MM-DD), time.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        project_code = kwargs.get("project")
        description = kwargs.get("description")
        incident_type = kwargs.get("type")
        incident_date = kwargs.get("date")
        incident_time = kwargs.get("time")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not description:
            raise ValueError(
                "Incident description is required. Use --description or -d."
            )

        desc_str = str(description)
        if len(desc_str.strip()) < 20:
            raise ValueError(
                "Description must be at least 20 characters."
            )

        if not incident_type:
            raise ValueError(
                "Incident type is required. Use --type or -t."
            )

        type_str = str(incident_type).lower()
        if type_str not in VALID_INCIDENT_TYPES:
            raise ValueError(
                f"Invalid incident type: '{type_str}'. "
                f"Valid options: {', '.join(sorted(VALID_INCIDENT_TYPES))}"
            )

        # Validate date if provided
        if incident_date:
            date_str = str(incident_date)
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValueError(
                    f"Invalid date format: '{date_str}'. "
                    "Use YYYY-MM-DD format."
                )
        else:
            date_str = date.today().isoformat()

        time_str = str(incident_time) if incident_time else None

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "description": desc_str,
            "incident_type": type_str,
            "incident_date": date_str,
            "incident_time": time_str,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for incident report generation.

        Loads safety standards from the knowledge base and provides
        project context for a thorough root-cause analysis.
        """
        company = context.company if context else {}
        project = context.project if context else {}

        project_context = self._format_project_context(context)

        # Load safety standards
        safety_standards = (
            self.knowledge_base.load_file("safety_standards") or ""
        )

        type_label = INCIDENT_TYPE_LABELS.get(
            validated["incident_type"], validated["incident_type"]
        )

        system_prompt = f"""You are a safety manager for {company.get('name', 'Krupp General Contractors')}, preparing a formal incident report.

PROJECT CONTEXT:
{project_context}

SAFETY STANDARDS:
{safety_standards}

INCIDENT CLASSIFICATION: {type_label}
INCIDENT DATE: {validated['incident_date']}
{f"INCIDENT TIME: {validated['incident_time']}" if validated['incident_time'] else ""}

INSTRUCTIONS:
1. Analyze the incident description and generate a comprehensive report.

2. Produce the following fields:
   - summary: A clear, factual 2-3 sentence summary of the incident
   - location: Specific location on the jobsite (infer from description)
   - involved_persons: JSON array of {{name, company, role, injury_description}}
     (use names if provided; otherwise [UNKNOWN WORKER])
   - witnesses: JSON array of {{name, company}}
   - immediate_actions: What was done immediately after the incident (2-3 sentences)
   - root_cause: The underlying root cause (1-2 sentences)
   - contributing_factors: JSON array of contributing factors (strings)
   - corrective_actions: JSON array of {{action, responsible_party, due_date}}
     (due_date in YYYY-MM-DD format, typically 1-14 days out)
   - preventive_actions: JSON array of preventive measures (strings)
   - is_osha_recordable: boolean — true if the incident meets OSHA 29 CFR 1904 criteria
   - osha_notification_required: boolean — true if OSHA must be notified within 8/24 hours
   - severity: 'minor', 'moderate', 'serious', or 'critical'

3. OSHA CLASSIFICATION RULES:
   - Near misses: NOT recordable, but document for prevention
   - First aid: NOT recordable unless it results in a prescription, stitches, or restricted duty
   - Recordable: Work-related injury requiring medical treatment beyond first aid
   - Lost time: Any injury causing days away from work — ALWAYS recordable
   - Property damage: NOT recordable for OSHA, but document for insurance
   - Environmental: May require EPA/state notification

4. RULES:
   - Be factual and objective — no blame language
   - Reference specific OSHA standards where applicable
   - Corrective actions must be specific, assignable, and time-bound
   - If information is insufficient for a field, use "To be determined" or [VERIFY]
   - severity reflects the actual or potential consequence

5. OUTPUT FORMAT:
   Return JSON:
   {{
     "summary": "Factual incident summary",
     "location": "Specific site location",
     "involved_persons": [{{"name": "", "company": "", "role": "", "injury_description": ""}}],
     "witnesses": [{{"name": "", "company": ""}}],
     "immediate_actions": "Actions taken",
     "root_cause": "Root cause analysis",
     "contributing_factors": ["factor1", "factor2"],
     "corrective_actions": [{{"action": "", "responsible_party": "", "due_date": ""}}],
     "preventive_actions": ["action1", "action2"],
     "is_osha_recordable": false,
     "osha_notification_required": false,
     "severity": "moderate"
   }}"""

        user_content = (
            f"INCIDENT DESCRIPTION:\n{validated['description']}"
        )

        return [
            {"role": "user", "content": user_content},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format incident report as a branded DOCX.

        Includes severity/classification section at top, tables for
        persons and witnesses, corrective action tracking, and a
        signature block.
        """
        data = parse_claude_json(response)

        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        # Get incident number
        with get_db(self.settings) as conn:
            incident_number = get_next_number(
                conn,
                "incident_reports",
                validated["project_id"],
                "incident_number",
            )

        type_label = INCIDENT_TYPE_LABELS.get(
            validated["incident_type"], validated["incident_type"]
        )
        severity = data.get("severity", "moderate")
        is_recordable = data.get("is_osha_recordable", False)
        osha_required = data.get("osha_notification_required", False)

        # Header fields
        header_fields = {
            "Incident Number": str(incident_number),
            "Date of Incident": validated["incident_date"],
            "Time of Incident": validated["incident_time"] or "Not specified",
            "Date of Report": date.today().isoformat(),
            "Project": (
                f"{project.get('name', '')} ({validated['project_code']})"
            ),
            "Location": data.get("location", "See description"),
        }

        sections: list[Section] = []
        tables: list[TableData] = []

        # Severity and classification section (at top)
        classification_lines = [
            f"Incident Type: {type_label}",
            f"Severity: {severity.upper()}",
            f"OSHA Recordable: {'YES' if is_recordable else 'No'}",
            f"OSHA Notification Required: {'YES - IMMEDIATE' if osha_required else 'No'}",
        ]
        if osha_required:
            classification_lines.append(
                "\nWARNING: OSHA must be notified within 8 hours for "
                "fatalities and within 24 hours for in-patient "
                "hospitalizations, amputations, or loss of an eye."
            )
        sections.append(
            Section(
                "Classification & Severity",
                "\n".join(classification_lines),
            )
        )

        # Summary
        sections.append(
            Section(
                "Incident Summary",
                data.get("summary", "No summary provided."),
            )
        )

        # Involved persons table
        persons = data.get("involved_persons", [])
        if persons:
            person_rows = []
            for p in persons:
                person_rows.append([
                    p.get("name", "Unknown"),
                    p.get("company", "Unknown"),
                    p.get("role", "N/A"),
                    p.get("injury_description", "N/A"),
                ])
            tables.append(
                TableData(
                    headers=["Name", "Company", "Role", "Injury/Involvement"],
                    rows=person_rows,
                    title="Involved Persons",
                )
            )

        # Witnesses table
        witnesses = data.get("witnesses", [])
        if witnesses:
            witness_rows = []
            for w in witnesses:
                witness_rows.append([
                    w.get("name", "Unknown"),
                    w.get("company", "Unknown"),
                ])
            tables.append(
                TableData(
                    headers=["Name", "Company"],
                    rows=witness_rows,
                    title="Witnesses",
                )
            )

        # Immediate actions
        if data.get("immediate_actions"):
            sections.append(
                Section("Immediate Actions Taken", data["immediate_actions"])
            )

        # Root cause
        if data.get("root_cause"):
            sections.append(
                Section("Root Cause Analysis", data["root_cause"])
            )

        # Contributing factors
        factors = data.get("contributing_factors", [])
        if factors:
            sections.append(
                Section(
                    "Contributing Factors",
                    "\n".join(f"- {f}" for f in factors),
                )
            )

        # Corrective actions table
        corrective = data.get("corrective_actions", [])
        if corrective:
            action_rows = []
            for idx, ca in enumerate(corrective, start=1):
                action_rows.append([
                    str(idx),
                    ca.get("action", ""),
                    ca.get("responsible_party", "TBD"),
                    ca.get("due_date", "TBD"),
                    "Open",
                ])
            tables.append(
                TableData(
                    headers=[
                        "#", "Corrective Action", "Responsible",
                        "Due Date", "Status",
                    ],
                    rows=action_rows,
                    title="Corrective Actions",
                )
            )

        # Preventive actions
        preventive = data.get("preventive_actions", [])
        if preventive:
            sections.append(
                Section(
                    "Preventive Actions",
                    "\n".join(f"- {p}" for p in preventive),
                )
            )

        # Signature block
        sections.append(
            Section(
                "Signatures",
                "Prepared By: _________________________  "
                "Date: ____________\n\n"
                "Safety Manager: ______________________  "
                "Date: ____________\n\n"
                "Project Manager: _____________________  "
                "Date: ____________\n\n"
                "Superintendent: ______________________  "
                "Date: ____________",
            )
        )

        content = DocumentContent(
            title=(
                f"Incident Report — #{incident_number}"
            ),
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist to incident_reports table
        self._persist_incident(
            validated, data, incident_number, output_path
        )

        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _persist_incident(
        self,
        validated: dict,
        data: dict,
        incident_number: int,
        output_path: Path,
    ) -> None:
        """Save incident report to the incident_reports table."""
        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO incident_reports "
                "(project_id, incident_number, incident_date, "
                "incident_time, report_date, incident_type, severity, "
                "is_osha_recordable, location, description, raw_input, "
                "involved_persons, witnesses, immediate_actions, "
                "root_cause, contributing_factors, corrective_actions, "
                "preventive_actions, status, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, 'draft', ?)",
                (
                    validated["project_id"],
                    incident_number,
                    validated["incident_date"],
                    validated["incident_time"],
                    date.today().isoformat(),
                    validated["incident_type"],
                    data.get("severity", "moderate"),
                    1 if data.get("is_osha_recordable") else 0,
                    data.get("location", ""),
                    data.get("summary", ""),
                    validated["description"],
                    json.dumps(data.get("involved_persons", [])),
                    json.dumps(data.get("witnesses", [])),
                    data.get("immediate_actions", ""),
                    data.get("root_cause", ""),
                    json.dumps(data.get("contributing_factors", [])),
                    json.dumps(data.get("corrective_actions", [])),
                    json.dumps(data.get("preventive_actions", [])),
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
            contract_display = (
                f"${project['current_contract_cents'] / 100:,.2f}"
            )

        lines = [
            f"Project: {project.get('name', 'N/A')} "
            f"({project.get('project_code', 'N/A')})",
            f"Client: {project.get('client_name', 'N/A')}",
            f"Location: {project.get('address', 'N/A')}",
            f"Contract Value: {contract_display}",
            f"Status: {project.get('status', 'N/A')}",
        ]

        if context.subcontractors:
            lines.append("\nSubcontractors on Site:")
            for sub in context.subcontractors:
                lines.append(
                    f"  - {sub['company_name']} ({sub['trade']})"
                )

        return "\n".join(lines)
