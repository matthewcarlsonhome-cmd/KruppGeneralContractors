"""Submittal Tracker — Skill #11.

Parses a submittal log (PDF or XLSX), identifies upcoming deadlines,
overdue items, and critical-path submittals. Generates a status report
with action items for the project team.
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
    SpreadsheetContent,
    TableData,
)
from kruppai.skills.base import BaseSkill


class SubmittalTrackerSkill(BaseSkill):
    """Track submittals, flag overdue items, and report status."""

    skill_name = "submittal_tracker"
    display_name = "Submittal Tracker"
    description = "Analyze a submittal log and flag overdue or at-risk items"
    phase = 2
    default_model = "sonnet"
    output_formats = ["docx", "xlsx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate submittal tracker input.

        Required: project (code), file (path to submittal log).
        Optional: notes.
        """
        project_code = kwargs.get("project")
        file_path = kwargs.get("file")
        notes = kwargs.get("notes", "")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not file_path:
            raise ValueError(
                "Submittal log file is required. Use --file or -f."
            )

        path = Path(str(file_path))
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        if path.suffix.lower() not in {".pdf", ".xlsx", ".xls", ".csv"}:
            raise ValueError(
                "Submittal log must be PDF, XLSX, XLS, or CSV format."
            )

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "file_path": str(path),
            "notes": str(notes) if notes else "",
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for submittal analysis."""
        company = context.company if context else {}
        project = context.project if context else {}

        # Parse submittal log
        parsed = parse_file(Path(validated["file_path"]))
        if parsed.error:
            raise ValueError(f"Could not parse submittal log: {parsed.error}")

        project_context = ""
        if context:
            project_context = (
                f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})\n"
                f"Substantial Completion: {project.get('substantial_completion_date', 'N/A')}\n"
                f"Current % Complete: {project.get('current_percent_complete', 0)}%\n"
            )

        # Get existing submittal data
        existing_submittals = ""
        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "SELECT submittal_number, title, status, submitted_date, "
                "required_date, lead_time_days, is_critical_path "
                "FROM submittals WHERE project_id = ? "
                "ORDER BY submittal_number",
                (validated["project_id"],),
            )
            rows = cursor.fetchall()
            if rows:
                lines = []
                for r in rows:
                    cp = " [CRITICAL PATH]" if r["is_critical_path"] else ""
                    lines.append(
                        f"  {r['submittal_number']}: {r['title']} — "
                        f"{r['status']}{cp}"
                    )
                existing_submittals = "\n".join(lines)
            else:
                existing_submittals = "No submittals currently tracked in database."

        system_prompt = f"""You are a senior project engineer for {company.get('name', 'Krupp General Contractors')}.
You are analyzing a submittal log to identify status, risks, and required actions.

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

EXISTING TRACKED SUBMITTALS:
{existing_submittals}

TODAY'S DATE: {date.today().isoformat()}

INSTRUCTIONS:
1. PARSE the submittal log and identify each submittal item:
   - Submittal number (CSI-based, e.g., "03.30.001")
   - Title/description
   - Spec section reference
   - Responsible subcontractor
   - Status (pending, submitted, approved, approved_as_noted, revise_resubmit, rejected)
   - Key dates (submitted, required on site, review due)
   - Lead time in days
   - Whether it's on the critical path

2. IDENTIFY issues:
   - Overdue submittals (past review due date and not approved)
   - Upcoming deadlines within 14 days
   - Critical path submittals not yet submitted
   - Long-lead items that need expediting
   - Items requiring resubmission

3. GENERATE action items:
   - Who needs to do what and by when
   - Priority level for each action

4. OUTPUT FORMAT:
   Return JSON:
   {{
     "overall_status": "summary paragraph",
     "total_submittals": 0,
     "status_summary": {{
       "pending": 0,
       "submitted": 0,
       "approved": 0,
       "approved_as_noted": 0,
       "revise_resubmit": 0,
       "rejected": 0
     }},
     "submittals": [
       {{
         "submittal_number": "",
         "title": "",
         "spec_section": "",
         "subcontractor": "",
         "status": "",
         "submitted_date": "",
         "required_date": "",
         "review_due_date": "",
         "lead_time_days": 0,
         "is_critical_path": false,
         "notes": ""
       }}
     ],
     "overdue_items": [
       {{"submittal_number": "", "title": "", "days_overdue": 0, "impact": ""}}
     ],
     "upcoming_deadlines": [
       {{"submittal_number": "", "title": "", "due_date": "", "days_remaining": 0}}
     ],
     "action_items": [
       {{"action": "", "assigned_to": "", "due_date": "", "priority": "urgent|high|normal"}}
     ],
     "recommendations": ["rec1", "rec2"]
   }}"""

        user_content = f"SUBMITTAL LOG DATA:\n{parsed.text[:50000]}"
        if validated["notes"]:
            user_content += f"\n\nPM NOTES:\n{validated['notes']}"

        return [
            {"role": "user", "content": user_content},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format submittal analysis as DOCX + XLSX."""
        data = parse_claude_json(response)

        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=context.project.get("name", "") if context else "",
            client_name=context.project.get("client_name", "") if context else "",
        )

        # DOCX report
        docx_path = self._create_docx(data, project_info, validated)

        # XLSX tracking log
        self._create_xlsx(data, project_info)

        # Persist submittals to database
        self._persist_submittals(validated, data, docx_path)

        return docx_path

    def _create_docx(
        self, data: dict, project_info: ProjectInfo, validated: dict
    ) -> Path:
        """Create DOCX submittal status report."""
        status_summary = data.get("status_summary", {})

        sections = [
            Section("Overall Status", data.get("overall_status", "")),
            Section(
                "Status Summary",
                f"Total Submittals: {data.get('total_submittals', 0)}\n"
                f"Pending: {status_summary.get('pending', 0)}\n"
                f"Submitted (Under Review): {status_summary.get('submitted', 0)}\n"
                f"Approved: {status_summary.get('approved', 0)}\n"
                f"Approved as Noted: {status_summary.get('approved_as_noted', 0)}\n"
                f"Revise & Resubmit: {status_summary.get('revise_resubmit', 0)}\n"
                f"Rejected: {status_summary.get('rejected', 0)}",
            ),
        ]

        # Overdue items
        overdue = data.get("overdue_items", [])
        if overdue:
            lines = []
            for item in overdue:
                lines.append(
                    f"- {item.get('submittal_number', '?')}: {item.get('title', '')} — "
                    f"{item.get('days_overdue', 0)} days overdue. {item.get('impact', '')}"
                )
            sections.append(Section("Overdue Items", "\n".join(lines)))

        # Action items
        actions = data.get("action_items", [])
        if actions:
            lines = []
            for a in actions:
                lines.append(
                    f"- [{a.get('priority', 'normal').upper()}] {a.get('action', '')} "
                    f"(Assigned: {a.get('assigned_to', 'TBD')}, Due: {a.get('due_date', 'TBD')})"
                )
            sections.append(Section("Action Items", "\n".join(lines)))

        # Recommendations
        recs = data.get("recommendations", [])
        if recs:
            sections.append(
                Section("Recommendations", "\n".join(f"- {r}" for r in recs))
            )

        # Submittal log table
        tables = []
        submittals = data.get("submittals", [])
        if submittals:
            rows = []
            for s in submittals:
                cp = "Yes" if s.get("is_critical_path") else ""
                rows.append([
                    str(s.get("submittal_number", "")),
                    str(s.get("title", "")),
                    str(s.get("subcontractor", "")),
                    str(s.get("status", "")).replace("_", " ").title(),
                    str(s.get("required_date", "")),
                    cp,
                ])
            tables.append(
                TableData(
                    headers=["Number", "Title", "Subcontractor", "Status", "Required Date", "Critical Path"],
                    rows=rows,
                    title="Submittal Log",
                )
            )

        # Upcoming deadlines table
        upcoming = data.get("upcoming_deadlines", [])
        if upcoming:
            u_rows = []
            for u in upcoming:
                u_rows.append([
                    str(u.get("submittal_number", "")),
                    str(u.get("title", "")),
                    str(u.get("due_date", "")),
                    str(u.get("days_remaining", "")),
                ])
            tables.append(
                TableData(
                    headers=["Number", "Title", "Due Date", "Days Remaining"],
                    rows=u_rows,
                    title="Upcoming Deadlines",
                )
            )

        content = DocumentContent(
            title="Submittal Status Report",
            date=date.today().isoformat(),
            header_fields={
                "File": Path(validated["file_path"]).name,
                "Analysis Date": date.today().isoformat(),
                "Total Submittals": str(data.get("total_submittals", 0)),
                "Overdue": str(len(overdue)),
            },
            sections=sections,
            tables=tables,
        )

        return self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

    def _create_xlsx(self, data: dict, project_info: ProjectInfo) -> Path:
        """Create XLSX submittal tracking workbook."""
        # Full submittal log
        log_rows = []
        for s in data.get("submittals", []):
            cp = "Yes" if s.get("is_critical_path") else "No"
            log_rows.append([
                str(s.get("submittal_number", "")),
                str(s.get("title", "")),
                str(s.get("spec_section", "")),
                str(s.get("subcontractor", "")),
                str(s.get("status", "")),
                str(s.get("submitted_date", "")),
                str(s.get("required_date", "")),
                str(s.get("review_due_date", "")),
                str(s.get("lead_time_days", "")),
                cp,
                str(s.get("notes", "")),
            ])

        # Action items sheet
        action_rows = []
        for a in data.get("action_items", []):
            action_rows.append([
                str(a.get("action", "")),
                str(a.get("assigned_to", "")),
                str(a.get("due_date", "")),
                str(a.get("priority", "")),
            ])

        sheets = {
            "Submittal Log": TableData(
                headers=[
                    "Number", "Title", "Spec Section", "Subcontractor",
                    "Status", "Submitted", "Required Date", "Review Due",
                    "Lead Time (Days)", "Critical Path", "Notes",
                ],
                rows=log_rows,
            ),
            "Action Items": TableData(
                headers=["Action", "Assigned To", "Due Date", "Priority"],
                rows=action_rows,
            ),
        }

        spreadsheet = SpreadsheetContent(title="Submittal Tracker", sheets=sheets)
        return self.formatter.create_xlsx(
            spreadsheet, project_info, skill_name=self.skill_name
        )

    def _persist_submittals(
        self, validated: dict, data: dict, docx_path: Path
    ) -> None:
        """Persist submittal data to database."""
        with get_db(self.settings) as conn:
            for s in data.get("submittals", []):
                sub_num = s.get("submittal_number", "")
                if not sub_num:
                    continue
                # Upsert: if submittal_number + revision exists, skip
                cursor = conn.execute(
                    "SELECT id FROM submittals "
                    "WHERE project_id = ? AND submittal_number = ? AND revision_number = 0",
                    (validated["project_id"], sub_num),
                )
                if cursor.fetchone():
                    # Update status only
                    conn.execute(
                        "UPDATE submittals SET status = ?, "
                        "submitted_date = ?, required_date = ?, "
                        "review_due_date = ?, lead_time_days = ?, "
                        "is_critical_path = ? "
                        "WHERE project_id = ? AND submittal_number = ? AND revision_number = 0",
                        (
                            s.get("status", "pending"),
                            s.get("submitted_date"),
                            s.get("required_date"),
                            s.get("review_due_date"),
                            s.get("lead_time_days"),
                            1 if s.get("is_critical_path") else 0,
                            validated["project_id"],
                            sub_num,
                        ),
                    )
                else:
                    conn.execute(
                        "INSERT INTO submittals "
                        "(project_id, submittal_number, title, spec_section, "
                        "submitted_by, status, submitted_date, required_date, "
                        "review_due_date, lead_time_days, is_critical_path, "
                        "document_path) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            validated["project_id"],
                            sub_num,
                            s.get("title", ""),
                            s.get("spec_section", ""),
                            s.get("subcontractor", ""),
                            s.get("status", "pending"),
                            s.get("submitted_date"),
                            s.get("required_date"),
                            s.get("review_due_date"),
                            s.get("lead_time_days"),
                            1 if s.get("is_critical_path") else 0,
                            str(docx_path),
                        ),
                    )
