"""Punch List Generator — Skill #6.

Transforms a superintendent's walk-through notes into a formatted,
trade-organized punch list in both DOCX (for distribution) and XLSX
(for tracking).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from kruppai.core.api_client import parse_claude_json
from kruppai.core.context_manager import ProjectContext
from kruppai.core.database import get_db
from kruppai.core.output_formatter import (
    DocumentContent,
    ProjectInfo,
    Section,
    SpreadsheetContent,
    TableData,
)
from kruppai.skills.base import BaseSkill


class PunchListSkill(BaseSkill):
    """Generate trade-organized punch lists in DOCX + XLSX formats."""

    skill_name = "punch_list"
    display_name = "Punch List Generator"
    description = "Transform walk-through notes into organized punch lists"
    phase = 1
    default_model = "sonnet"
    output_formats = ["docx", "xlsx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate punch list input.

        Required: project (code), notes.
        Optional: area, name.
        """
        project_code = kwargs.get("project")
        notes = kwargs.get("notes")
        area = kwargs.get("area")
        list_name = kwargs.get("name")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not notes:
            raise ValueError("Walk-through notes are required. Use --notes or -n.")

        notes_str = str(notes)
        notes_path = Path(notes_str)
        if notes_path.exists() and notes_path.is_file():
            notes_str = notes_path.read_text(encoding="utf-8")

        if len(notes_str.strip()) < 20:
            raise ValueError(
                "Walk-through notes must be at least 20 characters."
            )

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        area_str = str(area) if area else None

        if not list_name:
            parts = ["Punch List"]
            if area_str:
                parts.append(area_str)
            parts.append(date.today().isoformat())
            list_name = " - ".join(parts)

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "notes": notes_str,
            "area": area_str,
            "list_name": str(list_name),
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for punch list generation."""
        project = context.project if context else {}
        company = context.company if context else {}

        # Format project context
        project_context = self._format_project_context(context)

        # Build subcontractor list with scopes
        sub_list = "No subcontractors listed."
        if context and context.subcontractors:
            lines = []
            for sub in context.subcontractors:
                lines.append(
                    f"- {sub['company_name']} ({sub['trade']}): "
                    f"{sub.get('scope_description', 'N/A')}"
                )
            sub_list = "\n".join(lines)

        system_prompt = f"""You are organizing a construction punch list for {company.get('name', 'Krupp General Contractors')}.

PROJECT CONTEXT:
{project_context}

SUBCONTRACTORS ON PROJECT:
{sub_list}

INSTRUCTIONS:
1. Parse the superintendent's walk-through notes into individual punch items.

2. FOR EACH ITEM:
   - Location: Room number, area, or zone (be specific)
   - Description: Clear, professional description of the deficiency
   - Trade: Which trade is responsible (electrical, painting, flooring, mechanical, etc.)
   - Responsible Sub: Match to project subcontractor list. If uncertain, use [VERIFY: {{best guess}}]
   - Priority: 'critical' (safety/code), 'high' (functional), 'normal' (cosmetic), 'cosmetic' (minor appearance)

3. ORGANIZATION RULES:
   - Group items by location first, then by trade within location
   - Number items sequentially
   - Be specific enough that a sub can find and fix the item without calling the super
   - "Paint touch up" -> "Touch up paint on east wall, approximately 2'x3' area, scuff marks at 4' height"

4. OUTPUT FORMAT:
   Return JSON:
   {{
     "list_name": "",
     "inspection_date": "",
     "area": "",
     "items": [
       {{
         "item_number": 1,
         "location": "Room 201",
         "description": "Detailed deficiency description",
         "trade": "ceiling",
         "assigned_to": "ABC Interiors",
         "priority": "normal"
       }}
     ],
     "summary": {{
       "total_items": 0,
       "by_trade": {{"electrical": 2, "painting": 1}},
       "by_priority": {{"critical": 0, "high": 1, "normal": 5, "cosmetic": 2}}
     }}
   }}"""

        user_content = f"INSPECTION DATE: {date.today().isoformat()}\n"
        if validated.get("area"):
            user_content += f"AREA: {validated['area']}\n"
        user_content += f"\nWALK-THROUGH NOTES:\n{validated['notes']}"

        return [
            {"role": "user", "content": user_content},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format the punch list as both DOCX and XLSX. Returns the DOCX path."""
        data = parse_claude_json(response)

        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        items = data.get("items", [])
        summary = data.get("summary", {})

        # Create DOCX
        docx_path = self._create_docx(
            data, items, summary, project_info, validated
        )

        # Create XLSX
        self._create_xlsx(items, summary, project_info, validated)

        # Persist to database
        self._persist_punch_list(validated, data, items, docx_path)

        return docx_path

    def _create_docx(
        self,
        data: dict,
        items: list[dict],
        summary: dict,
        project_info: ProjectInfo,
        validated: dict,
    ) -> Path:
        """Create the DOCX punch list for distribution."""
        header_fields = {
            "Project": f"{project_info.name} ({validated['project_code']})",
            "List Name": validated["list_name"],
            "Inspection Date": date.today().isoformat(),
            "Total Items": str(summary.get("total_items", len(items))),
        }
        if validated.get("area"):
            header_fields["Area"] = validated["area"]

        # Main items table
        item_rows = []
        for item in items:
            item_rows.append([
                str(item.get("item_number", "")),
                str(item.get("location", "")),
                str(item.get("description", "")),
                str(item.get("trade", "")),
                str(item.get("assigned_to", "")),
                str(item.get("priority", "normal")),
                "Open",
            ])

        tables = [
            TableData(
                headers=[
                    "Item #",
                    "Location",
                    "Description",
                    "Trade",
                    "Responsible",
                    "Priority",
                    "Status",
                ],
                rows=item_rows,
                title="Punch List Items",
            )
        ]

        # Summary section
        sections: list[Section] = []
        summary_lines = []
        by_trade = summary.get("by_trade", {})
        if by_trade:
            summary_lines.append("Items by Trade:")
            for trade, count in sorted(by_trade.items()):
                summary_lines.append(f"  - {trade.title()}: {count}")

        by_priority = summary.get("by_priority", {})
        if by_priority:
            summary_lines.append("\nItems by Priority:")
            for priority, count in sorted(by_priority.items()):
                summary_lines.append(f"  - {priority.title()}: {count}")

        if summary_lines:
            sections.append(Section("Summary", "\n".join(summary_lines)))

        content = DocumentContent(
            title="Punch List",
            subtitle=validated["list_name"],
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        return self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

    def _create_xlsx(
        self,
        items: list[dict],
        summary: dict,
        project_info: ProjectInfo,
        validated: dict,
    ) -> Path:
        """Create the XLSX punch list for tracking."""
        # Sheet 1: Punch Items
        item_rows = []
        for item in items:
            item_rows.append([
                str(item.get("item_number", "")),
                str(item.get("location", "")),
                str(item.get("description", "")),
                str(item.get("trade", "")),
                str(item.get("assigned_to", "")),
                str(item.get("priority", "normal")),
                "Open",
                "",  # Completion Date
                "",  # Notes
            ])

        items_table = TableData(
            headers=[
                "Item #",
                "Location",
                "Description",
                "Trade",
                "Responsible",
                "Priority",
                "Status",
                "Completion Date",
                "Notes",
            ],
            rows=item_rows,
        )

        # Sheet 2: Summary
        summary_rows: list[list[str]] = []
        by_trade = summary.get("by_trade", {})
        if by_trade:
            summary_rows.append(["BY TRADE", ""])
            for trade, count in sorted(by_trade.items()):
                summary_rows.append([trade.title(), str(count)])
            summary_rows.append(["", ""])

        by_priority = summary.get("by_priority", {})
        if by_priority:
            summary_rows.append(["BY PRIORITY", ""])
            for priority, count in sorted(by_priority.items()):
                summary_rows.append([priority.title(), str(count)])

        summary_rows.append(["", ""])
        summary_rows.append([
            "TOTAL ITEMS",
            str(summary.get("total_items", len(items))),
        ])

        summary_table = TableData(
            headers=["Category", "Count"],
            rows=summary_rows,
        )

        spreadsheet = SpreadsheetContent(
            title=validated["list_name"],
            sheets={
                "Punch Items": items_table,
                "Summary": summary_table,
            },
        )

        return self.formatter.create_xlsx(
            spreadsheet, project_info, skill_name=self.skill_name
        )

    def _persist_punch_list(
        self,
        validated: dict,
        data: dict,
        items: list[dict],
        docx_path: Path,
    ) -> None:
        """Save punch list and items to the database."""
        summary = data.get("summary", {})

        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "INSERT INTO punch_lists "
                "(project_id, list_name, inspection_date, area, "
                "total_items, raw_input, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    validated["project_id"],
                    validated["list_name"],
                    date.today().isoformat(),
                    validated.get("area"),
                    summary.get("total_items", len(items)),
                    validated["notes"],
                    str(docx_path),
                ),
            )
            punch_list_id = cursor.lastrowid

            # Try to match subcontractors by name
            sub_map = self._build_sub_map(conn, validated["project_id"])

            for item in items:
                assigned_to = item.get("assigned_to", "")
                sub_id = sub_map.get(assigned_to.lower())

                conn.execute(
                    "INSERT INTO punch_items "
                    "(punch_list_id, project_id, item_number, location, "
                    "description, trade, subcontractor_id, assigned_to, "
                    "priority, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')",
                    (
                        punch_list_id,
                        validated["project_id"],
                        item.get("item_number", 0),
                        item.get("location", ""),
                        item.get("description", ""),
                        item.get("trade", ""),
                        sub_id,
                        assigned_to,
                        item.get("priority", "normal"),
                    ),
                )

    def _build_sub_map(
        self, conn: object, project_id: int
    ) -> dict[str, int | None]:
        """Build a mapping of subcontractor names (lowercase) to IDs."""
        sub_map: dict[str, int | None] = {}
        cursor = conn.execute(  # type: ignore[union-attr]
            "SELECT s.id, s.company_name FROM subcontractors s "
            "JOIN project_subcontractors ps ON s.id = ps.subcontractor_id "
            "WHERE ps.project_id = ?",
            (project_id,),
        )
        for row in cursor.fetchall():
            sub_map[row["company_name"].lower()] = row["id"]
        return sub_map

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
        return "\n".join(lines)
