"""Meeting Minutes Generator — Skill #3.

Transforms rough meeting notes into formatted minutes with attendees,
discussion items, decisions, and tracked action items that carry forward
between meetings.
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

VALID_MEETING_TYPES = {"oac", "subcontractor", "safety", "preconstruction", "internal"}
MEETING_TYPE_LABELS = {
    "oac": "Owner/Architect/Contractor (OAC)",
    "subcontractor": "Subcontractor",
    "safety": "Safety",
    "preconstruction": "Preconstruction",
    "internal": "Internal",
}


class MeetingMinutesSkill(BaseSkill):
    """Generate professional meeting minutes with action item tracking."""

    skill_name = "meeting_minutes"
    display_name = "Meeting Minutes"
    description = "Transform meeting notes into formatted minutes with action tracking"
    phase = 1
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate meeting minutes input.

        Required: project (code), type, notes.
        Optional: date, attendees.
        """
        project_code = kwargs.get("project")
        meeting_type = kwargs.get("type")
        notes = kwargs.get("notes")
        meeting_date = kwargs.get("date")
        attendees = kwargs.get("attendees")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not meeting_type:
            raise ValueError(
                f"Meeting type is required. Choose from: {', '.join(VALID_MEETING_TYPES)}"
            )
        if not notes:
            raise ValueError("Meeting notes are required. Use --notes or -n.")

        meeting_type_str = str(meeting_type).lower()
        if meeting_type_str not in VALID_MEETING_TYPES:
            raise ValueError(
                f"Invalid meeting type: '{meeting_type_str}'. "
                f"Choose from: {', '.join(VALID_MEETING_TYPES)}"
            )

        notes_str = str(notes)
        notes_path = Path(notes_str)
        if notes_path.exists() and notes_path.is_file():
            notes_str = notes_path.read_text(encoding="utf-8")

        if len(notes_str.strip()) < 20:
            raise ValueError(
                "Meeting notes must be at least 20 characters."
            )

        if meeting_date:
            try:
                parsed_date = datetime.strptime(str(meeting_date), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(
                    f"Invalid date format: '{meeting_date}'. Use YYYY-MM-DD."
                )
        else:
            parsed_date = date.today()

        # Parse attendees
        attendees_list: list[str] = []
        if attendees:
            attendees_list = [a.strip() for a in str(attendees).split(",") if a.strip()]

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "meeting_type": meeting_type_str,
            "notes": notes_str,
            "meeting_date": parsed_date.isoformat(),
            "attendees": attendees_list,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for meeting minutes generation."""
        project = context.project if context else {}
        company = context.company if context else {}

        # Format project context
        project_context = self._format_project_context(context)

        # Get open action items for carry-forward
        open_items_str = "No open action items."
        if context and context.open_action_items:
            lines = []
            for item in context.open_action_items:
                due = item.get("due_date", "TBD")
                lines.append(
                    f"  [{item['id']}] {item['description']} — "
                    f"Assigned to: {item['assigned_to']} — "
                    f"Due: {due} — Priority: {item.get('priority', 'normal')}"
                )
            open_items_str = "\n".join(lines)

        meeting_type_label = MEETING_TYPE_LABELS.get(
            validated["meeting_type"], validated["meeting_type"]
        )

        attendees_str = ""
        if validated["attendees"]:
            attendees_str = ", ".join(validated["attendees"])

        writing_standards = self.knowledge_base.load_file("writing_standards") or ""

        system_prompt = f"""You are a professional construction meeting minutes writer for {company.get('name', 'Krupp General Contractors')}.

MEETING CONTEXT:
Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})
Meeting Type: {meeting_type_label}
Date: {validated['meeting_date']}
Attendees: {attendees_str or 'Not specified — See sign-in sheet'}

PROJECT CONTEXT:
{project_context}

OPEN ACTION ITEMS FROM PREVIOUS MEETINGS:
{open_items_str}

WRITING STANDARDS:
{writing_standards}

INSTRUCTIONS:
1. Format the meeting notes into professional minutes with these sections:
   - ATTENDEES (if provided, otherwise note "See sign-in sheet")
   - DISCUSSION ITEMS: Organize by topic. Number each item. Include key details and any decisions made.
   - DECISIONS MADE: List each decision clearly with who made it.
   - ACTION ITEMS: Extract every action item with:
     * Description of the action
     * Person/company responsible
     * Due date (if mentioned, otherwise "TBD")
     * Priority (infer from context: urgent if deadline-driven)
   - OPEN ITEMS FROM PREVIOUS MEETINGS: For each prior open action item, note if it was discussed/resolved.
   - NEXT MEETING: Date/time if mentioned.

2. CRITICAL RULES:
   - Decisions are legally binding representations. Be precise.
   - Action items must have a clear owner — never "someone should..."
   - Match names to the project team/sub list when possible.
   - Dollar amounts must be exact as stated.
   - If something is unclear, use [VERIFY] tag.
   - Previous action items that aren't mentioned should be carried forward as still open.

3. OUTPUT FORMAT:
   Return JSON:
   {{
     "attendees": [{{"name": "", "company": "", "role": ""}}],
     "discussion_items": [{{"topic": "", "details": "", "item_number": 1}}],
     "decisions": [{{"decision": "", "made_by": "", "context": ""}}],
     "action_items": [{{"description": "", "assigned_to": "", "due_date": "", "priority": "normal"}}],
     "prior_items_status": [{{"item_id": 0, "status": "resolved|still_open|discussed", "notes": ""}}],
     "next_meeting": {{"date": "", "location": ""}},
     "formatted_minutes": "Full formatted minutes as narrative text"
   }}"""

        return [
            {"role": "user", "content": f"MEETING NOTES:\n{validated['notes']}"},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format the meeting minutes as a branded DOCX."""
        data = parse_claude_json(response)

        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        # Get meeting number
        with get_db(self.settings) as conn:
            meeting_number = get_next_number(
                conn, "meetings", validated["project_id"], "meeting_number"
            )

        meeting_type_label = MEETING_TYPE_LABELS.get(
            validated["meeting_type"], validated["meeting_type"]
        )

        # Header fields
        header_fields = {
            "Project": f"{project.get('name', '')} ({validated['project_code']})",
            "Meeting Type": meeting_type_label,
            "Meeting Number": str(meeting_number),
            "Date": validated["meeting_date"],
        }

        sections: list[Section] = []
        tables: list[TableData] = []

        # Attendees
        attendees = data.get("attendees", [])
        if attendees:
            attendee_rows = []
            for a in attendees:
                attendee_rows.append([
                    str(a.get("name", "")),
                    str(a.get("company", "")),
                    str(a.get("role", "")),
                ])
            tables.append(
                TableData(
                    headers=["Name", "Company", "Role"],
                    rows=attendee_rows,
                    title="Attendees",
                )
            )
        else:
            sections.append(Section("Attendees", "See sign-in sheet"))

        # Discussion items
        discussion = data.get("discussion_items", [])
        if discussion:
            content_lines = []
            for item in discussion:
                num = item.get("item_number", "")
                content_lines.append(
                    f"{num}. {item.get('topic', '')}\n{item.get('details', '')}"
                )
            sections.append(
                Section("Discussion Items", "\n\n".join(content_lines))
            )

        # Decisions
        decisions = data.get("decisions", [])
        if decisions:
            decision_rows = []
            for d in decisions:
                decision_rows.append([
                    str(d.get("decision", "")),
                    str(d.get("made_by", "")),
                    str(d.get("context", "")),
                ])
            tables.append(
                TableData(
                    headers=["Decision", "Made By", "Context"],
                    rows=decision_rows,
                    title="Decisions Made",
                )
            )

        # Action items
        action_items = data.get("action_items", [])
        if action_items:
            action_rows = []
            for ai in action_items:
                action_rows.append([
                    str(ai.get("description", "")),
                    str(ai.get("assigned_to", "")),
                    str(ai.get("due_date", "TBD")),
                    str(ai.get("priority", "normal")),
                ])
            tables.append(
                TableData(
                    headers=["Action Item", "Assigned To", "Due Date", "Priority"],
                    rows=action_rows,
                    title="Action Items",
                )
            )

        # Prior items status
        prior_status = data.get("prior_items_status", [])
        if prior_status:
            prior_rows = []
            for ps in prior_status:
                prior_rows.append([
                    str(ps.get("item_id", "")),
                    str(ps.get("status", "")),
                    str(ps.get("notes", "")),
                ])
            tables.append(
                TableData(
                    headers=["Item ID", "Status", "Notes"],
                    rows=prior_rows,
                    title="Prior Action Items Status",
                )
            )

        # Next meeting
        next_meeting = data.get("next_meeting", {})
        if next_meeting and next_meeting.get("date"):
            sections.append(
                Section(
                    "Next Meeting",
                    f"Date: {next_meeting.get('date', 'TBD')}\n"
                    f"Location: {next_meeting.get('location', 'TBD')}",
                )
            )

        doc_content = DocumentContent(
            title=f"{meeting_type_label} Meeting Minutes",
            subtitle=f"Meeting #{meeting_number}",
            date=validated["meeting_date"],
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            doc_content, project_info, skill_name=self.skill_name
        )

        # Persist meeting and manage action items
        self._persist_meeting(validated, data, meeting_number, output_path)

        return output_path

    def _persist_meeting(
        self,
        validated: dict,
        data: dict,
        meeting_number: int,
        output_path: Path,
    ) -> None:
        """Save meeting data and update action items."""
        with get_db(self.settings) as conn:
            # Insert meeting
            cursor = conn.execute(
                "INSERT INTO meetings "
                "(project_id, meeting_number, meeting_type, meeting_date, "
                "attendees, raw_notes, formatted_minutes, decisions, "
                "next_meeting_date, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated["project_id"],
                    meeting_number,
                    validated["meeting_type"],
                    validated["meeting_date"],
                    json.dumps(data.get("attendees", [])),
                    validated["notes"],
                    data.get("formatted_minutes", ""),
                    json.dumps(data.get("decisions", [])),
                    (data.get("next_meeting") or {}).get("date"),
                    str(output_path),
                ),
            )
            meeting_id = cursor.lastrowid

            # Update prior action items
            for item_status in data.get("prior_items_status", []):
                item_id = item_status.get("item_id")
                status = item_status.get("status", "still_open")
                if item_id and status == "resolved":
                    conn.execute(
                        "UPDATE action_items SET status = 'complete', "
                        "completion_date = ?, notes = ? WHERE id = ?",
                        (
                            date.today().isoformat(),
                            item_status.get("notes", ""),
                            item_id,
                        ),
                    )

            # Insert new action items
            for ai in data.get("action_items", []):
                conn.execute(
                    "INSERT INTO action_items "
                    "(project_id, meeting_id, source_skill, description, "
                    "assigned_to, due_date, priority, status) "
                    "VALUES (?, ?, 'meeting_minutes', ?, ?, ?, ?, 'open')",
                    (
                        validated["project_id"],
                        meeting_id,
                        ai.get("description", ""),
                        ai.get("assigned_to", "Unassigned"),
                        ai.get("due_date") if ai.get("due_date") != "TBD" else None,
                        ai.get("priority", "normal"),
                    ),
                )

    def _format_project_context(self, context: ProjectContext | None) -> str:
        """Format project context for the prompt."""
        if not context:
            return "No project context available."

        project = context.project
        lines = [
            f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})",
            f"Client: {project.get('client_name', 'N/A')}",
            f"Status: {project.get('status', 'N/A')}",
            f"Percent Complete: {project.get('current_percent_complete', 0)}%",
        ]

        if context.team:
            lines.append("\nTeam:")
            for member in context.team:
                lines.append(
                    f"  - {member['first_name']} {member['last_name']} "
                    f"({member.get('project_role', member.get('role', 'N/A'))})"
                )

        if context.subcontractors:
            lines.append("\nSubcontractors:")
            for sub in context.subcontractors:
                lines.append(
                    f"  - {sub['company_name']} ({sub['trade']})"
                )

        return "\n".join(lines)
