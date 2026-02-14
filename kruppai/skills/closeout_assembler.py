"""Closeout Assembler — Skill #15.

Generates a project closeout package consisting of a branded cover letter
(on Krupp letterhead) and a comprehensive XLSX closeout tracker.  Tracks
all required closeout items organized by category: Contractual, Technical,
Financial, Owner Turnover, and Regulatory.

Supports two modes:
- ``generate``: Creates a new closeout checklist from project context and notes
- ``update``: Updates an existing closeout tracker from an uploaded XLSX file
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

VALID_MODES = {"generate", "update"}

CLOSEOUT_CATEGORIES = [
    "Contractual",
    "Technical",
    "Financial",
    "Owner Turnover",
    "Regulatory",
]


class CloseoutAssemblerSkill(BaseSkill):
    """Generate or update a project closeout package."""

    skill_name = "closeout_assembler"
    display_name = "Closeout Assembler"
    description = "Generate a project closeout package with cover letter and tracker"
    phase = 3
    default_model = "sonnet"
    output_formats = ["docx", "xlsx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate closeout assembler input.

        Required: project (code), notes (min 20 chars).
        Optional: mode (generate/update), checklist_file (XLSX).
        """
        project_code = kwargs.get("project")
        notes = kwargs.get("notes")
        mode = kwargs.get("mode", "generate")
        checklist_file = kwargs.get("checklist_file")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not notes:
            raise ValueError(
                "Closeout notes are required. Use --notes or -n."
            )

        notes_str = str(notes).strip()
        if len(notes_str) < 20:
            raise ValueError(
                "Closeout notes must be at least 20 characters. "
                "Include key items like remaining punch items, "
                "outstanding submittals, and financial status."
            )

        mode_str = str(mode).lower()
        if mode_str not in VALID_MODES:
            raise ValueError(
                f"Invalid mode: '{mode_str}'. "
                f"Valid options: {', '.join(sorted(VALID_MODES))}"
            )

        # Validate checklist file if provided
        checklist_path_str: str | None = None
        if checklist_file:
            checklist_path = Path(str(checklist_file))
            if not checklist_path.exists():
                raise ValueError(
                    f"Checklist file not found: {checklist_path}"
                )
            if checklist_path.suffix.lower() not in {".xlsx", ".xls"}:
                raise ValueError(
                    "Checklist file must be in XLSX or XLS format."
                )
            checklist_path_str = str(checklist_path)

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "notes": notes_str,
            "mode": mode_str,
            "checklist_file_path": checklist_path_str,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for closeout assembly."""
        company = context.company if context else {}
        project = context.project if context else {}

        # Build project context
        project_context = self._format_project_context(context)

        # Load subcontractor status for lien waivers
        sub_context = self._load_subcontractor_status(validated, context)

        # Load existing closeout data if updating
        existing_checklist = ""
        if validated.get("checklist_file_path"):
            parsed = parse_file(Path(validated["checklist_file_path"]))
            if not parsed.error:
                existing_checklist = (
                    f"\nEXISTING CHECKLIST DATA:\n{parsed.text[:20000]}\n"
                )

        # Load punch list status
        punch_context = self._load_punch_status(validated)

        # Load open action items
        action_context = ""
        if context and context.open_action_items:
            lines = ["OPEN ACTION ITEMS:"]
            for item in context.open_action_items[:20]:
                lines.append(
                    f"  - [{item.get('priority', 'normal').upper()}] "
                    f"{item.get('description', '')} "
                    f"(assigned to: {item.get('assigned_to', 'N/A')})"
                )
            action_context = "\n".join(lines)

        mode_instruction = ""
        if validated["mode"] == "update":
            mode_instruction = (
                "You are UPDATING an existing closeout checklist. "
                "Review the existing data and update statuses based on "
                "the PM's notes. Add any new items identified."
            )
        else:
            mode_instruction = (
                "You are GENERATING a new closeout checklist from scratch. "
                "Create a comprehensive list of all required closeout items "
                "for this project type."
            )

        categories_list = ", ".join(CLOSEOUT_CATEGORIES)

        system_prompt = f"""You are a senior project manager for {company.get('name', 'Krupp General Contractors')} assembling a project closeout package.

{mode_instruction}

PROJECT CONTEXT:
{project_context}

{sub_context}

{punch_context}

{action_context}
{existing_checklist}

INSTRUCTIONS:
1. Generate a professional COVER LETTER addressed to the owner/client
   summarizing the closeout status. This will be on Krupp letterhead.

2. Create a comprehensive CLOSEOUT CHECKLIST organized by these categories:
   {categories_list}

3. CATEGORY DETAILS:
   - Contractual: Final lien waivers, consent of surety, certificate of
     substantial completion, final payment application, warranty letters,
     maintenance bonds
   - Technical: As-built drawings, O&M manuals, test/balance reports,
     commissioning reports, training documentation, spare parts/attic stock
   - Financial: Final change order log, retention reconciliation, final
     cost report, budget close-out, subcontractor final payments
   - Owner Turnover: Keys/access cards, building systems training, warranty
     binder, emergency contacts, equipment inventory
   - Regulatory: Certificate of occupancy, final inspections, environmental
     compliance, fire marshal sign-off, ADA compliance documentation

4. For each checklist item include:
   - Item name
   - Category
   - Responsible party (Krupp, specific sub, architect, owner)
   - Status: "not_started", "in_progress", "complete", "not_applicable"
   - Due date or target (if determinable)
   - Notes

5. Assess items by responsibility (who has the most outstanding items).

6. OUTPUT FORMAT:
   Return JSON:
   {{
     "cover_letter_text": "Full cover letter text",
     "status_summary": {{
       "total_items": 0,
       "complete": 0,
       "in_progress": 0,
       "not_started": 0,
       "not_applicable": 0,
       "percent_complete": 0.0
     }},
     "checklist_items": [
       {{
         "item_name": "Item description",
         "category": "Contractual|Technical|Financial|Owner Turnover|Regulatory",
         "responsible_party": "Krupp|Sub Name|Architect|Owner",
         "status": "not_started|in_progress|complete|not_applicable",
         "due_date": "YYYY-MM-DD or null",
         "notes": "Additional notes"
       }}
     ],
     "items_by_responsibility": [
       {{
         "party": "Company or role name",
         "total": 0,
         "complete": 0,
         "outstanding": 0
       }}
     ],
     "recommendations": ["rec1", "rec2"]
   }}"""

        return [
            {
                "role": "user",
                "content": f"CLOSEOUT NOTES:\n{validated['notes']}",
            },
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format closeout package as DOCX cover letter + XLSX tracker."""
        data = parse_claude_json(response)

        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=context.project.get("name", "") if context else "",
            client_name=context.project.get("client_name", "") if context else "",
        )

        # DOCX cover letter
        docx_path = self._create_docx(data, project_info, validated, context)

        # XLSX closeout tracker
        xlsx_path = self._create_xlsx(data, project_info)

        # Persist to database
        self._persist_closeout(validated, data, docx_path, xlsx_path, context)

        return docx_path

    def _create_docx(
        self,
        data: dict,
        project_info: ProjectInfo,
        validated: dict,
        context: ProjectContext | None,
    ) -> Path:
        """Create the DOCX cover letter with closeout status summary."""
        project = context.project if context else {}

        sections: list[Section] = []

        # Cover letter body
        cover_letter = data.get("cover_letter_text", "")
        if cover_letter:
            sections.append(Section("", cover_letter))

        # Status summary
        summary = data.get("status_summary", {})
        if summary:
            summary_text = (
                f"Total Closeout Items: {summary.get('total_items', 0)}\n"
                f"Complete: {summary.get('complete', 0)}\n"
                f"In Progress: {summary.get('in_progress', 0)}\n"
                f"Not Started: {summary.get('not_started', 0)}\n"
                f"Not Applicable: {summary.get('not_applicable', 0)}\n"
                f"Percent Complete: {summary.get('percent_complete', 0):.0f}%"
            )
            sections.append(Section("Closeout Status Summary", summary_text))

        # Items by category summary
        items = data.get("checklist_items", [])
        for category in CLOSEOUT_CATEGORIES:
            cat_items = [
                i for i in items if i.get("category") == category
            ]
            if cat_items:
                lines = []
                for item in cat_items:
                    status_icon = {
                        "complete": "DONE",
                        "in_progress": "IN PROGRESS",
                        "not_started": "PENDING",
                        "not_applicable": "N/A",
                    }.get(item.get("status", ""), "PENDING")
                    lines.append(
                        f"[{status_icon}] {item.get('item_name', '')}"
                        f" — {item.get('responsible_party', 'TBD')}"
                    )
                sections.append(Section(category, "\n".join(lines)))

        # Responsibility summary
        resp_items = data.get("items_by_responsibility", [])
        tables: list[TableData] = []
        if resp_items:
            rows = []
            for r in resp_items:
                rows.append([
                    str(r.get("party", "")),
                    str(r.get("total", 0)),
                    str(r.get("complete", 0)),
                    str(r.get("outstanding", 0)),
                ])
            tables.append(
                TableData(
                    headers=["Party", "Total", "Complete", "Outstanding"],
                    rows=rows,
                    title="Items by Responsible Party",
                )
            )

        # Recommendations
        recs = data.get("recommendations", [])
        if recs:
            sections.append(
                Section("Recommendations", "\n".join(f"- {r}" for r in recs))
            )

        content = DocumentContent(
            title=f"Project Closeout Package — {project_info.project_code}",
            subtitle=project_info.name,
            date=date.today().isoformat(),
            header_fields={
                "Project": f"{project_info.name} ({project_info.project_code})",
                "Client": project_info.client_name or "N/A",
                "Closeout Date": date.today().isoformat(),
                "Status": f"{summary.get('percent_complete', 0):.0f}% Complete",
            },
            sections=sections,
            tables=tables,
            use_letterhead=True,
        )

        return self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

    def _create_xlsx(self, data: dict, project_info: ProjectInfo) -> Path:
        """Create XLSX closeout tracker workbook."""
        items = data.get("checklist_items", [])

        # Master checklist sheet
        master_rows = []
        for item in items:
            master_rows.append([
                str(item.get("category", "")),
                str(item.get("item_name", "")),
                str(item.get("responsible_party", "")),
                str(item.get("status", "")).replace("_", " ").title(),
                str(item.get("due_date", "") or ""),
                str(item.get("notes", "")),
            ])

        # Per-category sheets
        sheets: dict[str, TableData] = {
            "Master Checklist": TableData(
                headers=[
                    "Category",
                    "Item",
                    "Responsible Party",
                    "Status",
                    "Due Date",
                    "Notes",
                ],
                rows=master_rows,
            ),
        }

        for category in CLOSEOUT_CATEGORIES:
            cat_items = [
                i for i in items if i.get("category") == category
            ]
            if cat_items:
                cat_rows = []
                for item in cat_items:
                    cat_rows.append([
                        str(item.get("item_name", "")),
                        str(item.get("responsible_party", "")),
                        str(item.get("status", "")).replace("_", " ").title(),
                        str(item.get("due_date", "") or ""),
                        str(item.get("notes", "")),
                    ])
                sheets[category] = TableData(
                    headers=[
                        "Item",
                        "Responsible Party",
                        "Status",
                        "Due Date",
                        "Notes",
                    ],
                    rows=cat_rows,
                )

        # Responsibility summary sheet
        resp_items = data.get("items_by_responsibility", [])
        if resp_items:
            resp_rows = []
            for r in resp_items:
                resp_rows.append([
                    str(r.get("party", "")),
                    str(r.get("total", 0)),
                    str(r.get("complete", 0)),
                    str(r.get("outstanding", 0)),
                ])
            sheets["By Responsibility"] = TableData(
                headers=["Party", "Total Items", "Complete", "Outstanding"],
                rows=resp_rows,
            )

        spreadsheet = SpreadsheetContent(
            title="Closeout Tracker", sheets=sheets
        )
        return self.formatter.create_xlsx(
            spreadsheet, project_info, skill_name=self.skill_name
        )

    def _persist_closeout(
        self,
        validated: dict,
        data: dict,
        docx_path: Path,
        xlsx_path: Path,
        context: ProjectContext | None,
    ) -> None:
        """Persist closeout package to the database."""
        project = context.project if context else {}
        items = data.get("checklist_items", [])
        summary = data.get("status_summary", {})

        # Organize items for database columns
        required_docs = [
            i for i in items
            if i.get("category") in ("Technical", "Contractual")
        ]
        lien_waivers = [
            i for i in items
            if "lien" in (i.get("item_name", "") or "").lower()
        ]
        inspections = [
            i for i in items if i.get("category") == "Regulatory"
        ]
        training = [
            i for i in items
            if "training" in (i.get("item_name", "") or "").lower()
        ]
        spare_parts = [
            i for i in items
            if "spare" in (i.get("item_name", "") or "").lower()
            or "attic" in (i.get("item_name", "") or "").lower()
        ]

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO closeout_packages "
                "(project_id, package_name, status, "
                "required_documents, lien_waivers, final_inspections, "
                "training_sessions, spare_parts, "
                "final_contract_cents, retention_held_cents, "
                "cover_letter_path, checklist_path, document_path, "
                "substantial_completion_date, final_completion_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated["project_id"],
                    f"Closeout Package — {validated['project_code']}",
                    "in_progress",
                    json.dumps(required_docs),
                    json.dumps(lien_waivers),
                    json.dumps(inspections),
                    json.dumps(training),
                    json.dumps(spare_parts),
                    project.get("current_contract_cents"),
                    None,  # retention_held_cents — not calculated here
                    str(docx_path),
                    str(xlsx_path),
                    str(docx_path),
                    project.get("substantial_completion_date"),
                    project.get("final_completion_date"),
                ),
            )

    def _format_project_context(self, context: ProjectContext | None) -> str:
        """Format project context for the prompt."""
        if not context:
            return "No project context available."

        project = context.project
        original = project.get("original_contract_cents", 0) or 0
        current = project.get("current_contract_cents", 0) or 0
        pct = project.get("current_percent_complete", 0) or 0

        lines = [
            f"Project: {project.get('name', 'N/A')} "
            f"({project.get('project_code', 'N/A')})",
            f"Client: {project.get('client_name', 'N/A')}",
            f"Type: {project.get('project_type', 'N/A')}",
            f"Original Contract: ${original / 100:,.2f}",
            f"Current Contract: ${current / 100:,.2f}",
            f"Percent Complete: {pct:.0f}%",
            f"Status: {project.get('status', 'N/A')}",
            f"Substantial Completion: "
            f"{project.get('substantial_completion_date', 'TBD')}",
            f"Final Completion: "
            f"{project.get('final_completion_date', 'TBD')}",
        ]

        return "\n".join(lines)

    def _load_subcontractor_status(
        self, validated: dict, context: ProjectContext | None
    ) -> str:
        """Load subcontractor information for lien waiver tracking."""
        if not context or not context.subcontractors:
            return "SUBCONTRACTORS: No subcontractor data available."

        lines = ["SUBCONTRACTORS:"]
        for sub in context.subcontractors:
            contract_val = sub.get("contract_value_cents", 0) or 0
            co_val = sub.get("change_order_total_cents", 0) or 0
            lines.append(
                f"  - {sub['company_name']} ({sub.get('trade', 'N/A')}): "
                f"Contract ${contract_val / 100:,.2f}, "
                f"COs ${co_val / 100:,.2f}, "
                f"Status: {sub.get('contract_status', 'N/A')}"
            )

        return "\n".join(lines)

    def _load_punch_status(self, validated: dict) -> str:
        """Load punch list status for closeout context."""
        try:
            with get_db(self.settings) as conn:
                cursor = conn.execute(
                    "SELECT list_name, total_items, completed_items, status "
                    "FROM punch_lists "
                    "WHERE project_id = ? "
                    "ORDER BY created_at DESC LIMIT 5",
                    (validated["project_id"],),
                )
                rows = cursor.fetchall()

                if not rows:
                    return "PUNCH LISTS: No punch lists recorded."

                lines = ["PUNCH LISTS:"]
                for row in rows:
                    total = row["total_items"] or 0
                    done = row["completed_items"] or 0
                    lines.append(
                        f"  - {row['list_name']}: "
                        f"{done}/{total} complete "
                        f"({row['status']})"
                    )
                return "\n".join(lines)
        except Exception:
            return "PUNCH LISTS: Unable to load."
