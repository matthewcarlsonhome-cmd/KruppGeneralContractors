"""Client Update Letter Generator — Skill #4.

Generates a professional client update letter on Krupp letterhead
summarizing project progress — the weekly/biweekly email a PM sends
to the owner.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from kruppai.core.context_manager import ProjectContext
from kruppai.core.database import get_db
from kruppai.core.output_formatter import (
    DocumentContent,
    ProjectInfo,
    Section,
)
from kruppai.skills.base import BaseSkill


class ClientUpdateSkill(BaseSkill):
    """Generate professional client update letters on Krupp letterhead."""

    skill_name = "client_update"
    display_name = "Client Update Letter"
    description = "Generate a professional project status letter for the client"
    phase = 1
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate client update input.

        Required: project (code), notes.
        Optional: period.
        """
        project_code = kwargs.get("project")
        notes = kwargs.get("notes")
        period = kwargs.get("period", "weekly")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not notes:
            raise ValueError(
                "Update notes are required. Use --notes or -n."
            )

        notes_str = str(notes)
        notes_path = Path(notes_str)
        if notes_path.exists() and notes_path.is_file():
            notes_str = notes_path.read_text(encoding="utf-8")

        if len(notes_str.strip()) < 20:
            raise ValueError(
                "Update notes must be at least 20 characters."
            )

        period_str = str(period).lower()
        if period_str not in {"weekly", "monthly"}:
            raise ValueError("Period must be 'weekly' or 'monthly'.")

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "notes": notes_str,
            "period": period_str,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for client update letter generation."""
        project = context.project if context else {}
        company = context.company if context else {}

        company_profile = self.knowledge_base.load_file("company_profile") or ""
        writing_standards = self.knowledge_base.load_file("writing_standards") or ""

        # Build project context with financials
        full_context = self._format_full_context(context)

        # Build recent activity summary
        activity_summary = self._get_recent_activity(validated, context)

        # Find PM info
        pm_name = "Project Manager"
        pm_title = "Project Manager"
        if context:
            for member in context.team:
                if member.get("project_role") == "project_manager":
                    pm_name = f"{member['first_name']} {member['last_name']}"
                    pm_title = member.get("title", "Project Manager")
                    break

        client_contact = project.get("client_contact_name", "Client")
        client_name = project.get("client_name", "Client")

        system_prompt = f"""You are writing a professional project update letter for {company.get('name', 'Krupp General Contractors')}, addressed to the client.

COMPANY CONTEXT:
{company_profile}

PROJECT CONTEXT:
{full_context}

RECENT PROJECT ACTIVITY:
{activity_summary}

WRITING STANDARDS:
{writing_standards}

LETTER CONTEXT:
Addressed to: {client_contact}, {client_name}
From: {pm_name}, {pm_title}, {company.get('name', 'Krupp General Contractors')}
Period: {validated['period']}

INSTRUCTIONS:
1. Write a professional letter with these sections:
   - GREETING: Professional salutation
   - PROJECT STATUS SUMMARY: 2-3 sentence overview. Emphasize positive progress. Be honest about challenges but frame constructively.
   - SCHEDULE UPDATE: Current status vs. plan. Note any impacts and mitigation steps.
   - BUDGET/CHANGE ORDER UPDATE: Pending COs, approved COs this period. Brief descriptions.
   - KEY ACTIVITIES THIS PERIOD: Bullet points of major work completed.
   - UPCOMING MILESTONES: What to expect in the next period.
   - ITEMS REQUIRING OWNER ACTION: RFI responses needed, selections due, approvals pending. This is the call-to-action.
   - CLOSING: Professional sign-off.

2. TONE RULES:
   - Professional but warm — this is a relationship letter, not a legal filing.
   - Confidence without arrogance. "We are on track" not "We crushed it."
   - Challenges are "items we're managing" not "problems."
   - Always include at least one positive milestone or achievement.
   - End with a forward-looking statement.

3. OUTPUT FORMAT:
   Return the complete letter text (not JSON). Use markdown formatting for sections.
   The output formatter will apply letterhead and formatting."""

        return [
            {
                "role": "user",
                "content": f"PM'S UPDATE NOTES:\n{validated['notes']}",
            },
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format the client update as a branded DOCX with letterhead."""
        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        # Find PM name
        pm_name = "Project Manager"
        pm_title = "Project Manager"
        if context:
            for member in context.team:
                if member.get("project_role") == "project_manager":
                    pm_name = f"{member['first_name']} {member['last_name']}"
                    pm_title = member.get("title", "Project Manager")
                    break

        # Parse the letter text into sections
        sections = self._parse_letter_sections(response)

        # Add signature block
        sections.append(
            Section(
                "",
                f"Sincerely,\n\n{pm_name}\n{pm_title}\n"
                f"Krupp General Contractors",
                level=2,
            )
        )

        header_fields = {
            "Date": date.today().isoformat(),
            "To": f"{project.get('client_contact_name', 'Client')}, "
            f"{project.get('client_name', '')}",
            "From": f"{pm_name}, Krupp General Contractors",
            "Re": f"{project.get('name', '')} — "
            f"{validated['period'].title()} Status Update",
        }

        content = DocumentContent(
            title=f"Project Status Update — {validated['period'].title()}",
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            use_letterhead=True,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        return output_path

    def _parse_letter_sections(self, response: str) -> list[Section]:
        """Parse Claude's markdown response into Section objects."""
        sections: list[Section] = []
        current_heading = ""
        current_lines: list[str] = []

        for line in response.split("\n"):
            stripped = line.strip()
            # Detect markdown headings
            if stripped.startswith("## "):
                if current_heading or current_lines:
                    sections.append(
                        Section(current_heading, "\n".join(current_lines))
                    )
                current_heading = stripped.lstrip("# ").strip()
                current_lines = []
            elif stripped.startswith("# "):
                if current_heading or current_lines:
                    sections.append(
                        Section(current_heading, "\n".join(current_lines))
                    )
                current_heading = stripped.lstrip("# ").strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Final section
        if current_heading or current_lines:
            sections.append(
                Section(current_heading, "\n".join(current_lines))
            )

        # If no headings found, treat whole response as a single section
        if not sections:
            sections.append(Section("", response))

        return sections

    def _format_full_context(self, context: ProjectContext | None) -> str:
        """Format project context with financial details."""
        if not context:
            return "No project context available."

        project = context.project
        lines = [
            f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})",
            f"Client: {project.get('client_name', 'N/A')}",
            f"Status: {project.get('status', 'N/A')}",
            f"Percent Complete: {project.get('current_percent_complete', 0)}%",
        ]

        if project.get("original_contract_cents"):
            lines.append(
                f"Original Contract: ${project['original_contract_cents'] / 100:,.2f}"
            )
        if project.get("current_contract_cents"):
            lines.append(
                f"Current Contract: ${project['current_contract_cents'] / 100:,.2f}"
            )
        if project.get("substantial_completion_date"):
            lines.append(
                f"Substantial Completion: {project['substantial_completion_date']}"
            )

        return "\n".join(lines)

    def _get_recent_activity(
        self, validated: dict, context: ProjectContext | None
    ) -> str:
        """Build a summary of recent project activity from the database."""
        lines: list[str] = []

        try:
            with get_db(self.settings) as conn:
                pid = validated["project_id"]

                # Open RFIs
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM rfis "
                    "WHERE project_id = ? AND status IN ('draft', 'submitted')",
                    (pid,),
                )
                open_rfis = cursor.fetchone()[0]
                lines.append(f"- Open RFIs: {open_rfis}")

                # Open RFI subjects
                if open_rfis > 0:
                    cursor = conn.execute(
                        "SELECT rfi_number, subject FROM rfis "
                        "WHERE project_id = ? AND status IN ('draft', 'submitted') "
                        "ORDER BY rfi_number",
                        (pid,),
                    )
                    for row in cursor.fetchall():
                        lines.append(
                            f"    RFI #{row['rfi_number']}: {row['subject']}"
                        )

                # Pending change orders
                cursor = conn.execute(
                    "SELECT co_number, title, total_with_markup_cents "
                    "FROM change_orders "
                    "WHERE project_id = ? AND status IN ('draft', 'submitted') "
                    "ORDER BY co_number",
                    (pid,),
                )
                cos = cursor.fetchall()
                if cos:
                    lines.append(f"- Pending Change Orders: {len(cos)}")
                    for co in cos:
                        amount = ""
                        if co["total_with_markup_cents"]:
                            amount = f" (${co['total_with_markup_cents'] / 100:,.2f})"
                        lines.append(
                            f"    CO #{co['co_number']}: {co['title']}{amount}"
                        )
                else:
                    lines.append("- Pending Change Orders: 0")

                # Open action items
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM action_items "
                    "WHERE project_id = ? AND status IN ('open', 'in_progress')",
                    (pid,),
                )
                open_items = cursor.fetchone()[0]
                lines.append(f"- Open Action Items: {open_items}")

        except Exception:
            lines.append("- Recent activity data unavailable.")

        return "\n".join(lines) if lines else "No recent activity data available."
