"""Case Study Generator — Skill #17.

Builds a polished project case study from PM notes and project data.
Output is audience-tailored (client, marketing, or proposal) and uses a
section-break delimited response format rather than JSON.
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
    TableData,
)
from kruppai.skills.base import BaseSkill

SECTION_DELIMITER = "---SECTION BREAK---"

VALID_AUDIENCES = {"client", "marketing", "proposal"}

# Expected sections in Claude's response, in order
EXPECTED_SECTIONS = [
    "title",
    "at_a_glance",
    "challenge",
    "approach",
    "results",
    "metrics",
    "team",
    "testimonial",
]


class CaseStudySkill(BaseSkill):
    """Generate polished project case studies for different audiences."""

    skill_name = "case_study"
    display_name = "Case Study Generator"
    description = "Create a professional project case study from notes and data"
    phase = 3
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate case study input.

        Required: project (code), notes.
        Optional: audience (client/marketing/proposal), photos.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        project_code = kwargs.get("project")
        notes = kwargs.get("notes")
        audience = kwargs.get("audience", "marketing")
        photos = kwargs.get("photos")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not notes:
            raise ValueError(
                "Project notes are required. Use --notes or -n."
            )

        notes_str = str(notes)
        if len(notes_str.strip()) < 20:
            raise ValueError(
                "Notes must be at least 20 characters."
            )

        audience_str = str(audience).lower()
        if audience_str not in VALID_AUDIENCES:
            raise ValueError(
                f"Invalid audience: '{audience_str}'. "
                f"Valid options: {', '.join(sorted(VALID_AUDIENCES))}"
            )

        # Parse optional photo paths
        photo_list: list[str] = []
        if photos:
            photo_list = [
                p.strip() for p in str(photos).split(",") if p.strip()
            ]

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "notes": notes_str,
            "audience": audience_str,
            "photos": photo_list,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for case study generation.

        Loads company profile, project metrics, and lessons learned to
        give Claude rich context for a compelling narrative.
        """
        company = context.company if context else {}
        project = context.project if context else {}

        project_context = self._format_project_context(context)

        # Load knowledge base files
        company_profile = (
            self.knowledge_base.load_file("company_profile") or ""
        )

        # Gather project metrics from database
        metrics_text = self._gather_project_metrics(validated["project_id"])

        # Get lessons learned summary
        lessons_summary = self._get_lessons_summary(validated["project_id"])

        # Audience-specific writing guidance
        audience_guidance = self._get_audience_guidance(validated["audience"])

        system_prompt = f"""You are a professional construction marketing writer for {company.get('name', 'Krupp General Contractors')}.

COMPANY PROFILE:
{company_profile}

PROJECT CONTEXT:
{project_context}

PROJECT METRICS:
{metrics_text}

LESSONS LEARNED SUMMARY:
{lessons_summary}

AUDIENCE: {validated['audience'].upper()}
{audience_guidance}

INSTRUCTIONS:
Write a compelling project case study using the section-break format below.
Each section is separated by the delimiter: {SECTION_DELIMITER}

SECTIONS (in order):
1. TITLE — A compelling project title (max 100 chars) and optional subtitle
2. AT A GLANCE — 3-5 bullet points summarizing key project facts
3. CHALLENGE — What made this project difficult or unique (2-3 paragraphs)
4. APPROACH — How the team tackled the challenges (2-3 paragraphs)
5. RESULTS — What was achieved (2-3 paragraphs, quantified where possible)
6. METRICS — JSON object with key metrics:
   {{"contract_value": "$X.XM", "duration_months": N, "square_footage": N, "on_time": true/false, "on_budget": true/false, "safety_record": "X days without incident", "change_order_percent": X.X, "rfis_closed": N, "punch_items_resolved": N}}
7. TEAM — Key team members and their roles (brief paragraph)
8. TESTIMONIAL — A client testimonial quote (real if provided, otherwise a plausible placeholder marked [PLACEHOLDER])

RULES:
- Use {SECTION_DELIMITER} between each section, exactly 8 sections.
- Write in a professional but engaging tone.
- Quantify results wherever possible.
- Do NOT fabricate specific numbers — use project data provided or mark as [VERIFY].
- For the METRICS section, output valid JSON only (no surrounding text).
- Tailor tone and emphasis to the {validated['audience']} audience."""

        # Build user content
        user_content = f"HIGHLIGHTS:\n{validated['notes']}"

        if validated["photos"]:
            user_content += (
                "\n\nPHOTO REFERENCES:\n"
                + "\n".join(
                    f"  - {p}" for p in validated["photos"]
                )
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
        """Format case study as a branded DOCX.

        Parses the section-break delimited response into 8 sections
        and builds a polished document.
        """
        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        # Parse sections from response
        parsed = self._parse_sections(response)

        title_text = parsed.get("title", project.get("name", "Case Study"))
        at_a_glance = parsed.get("at_a_glance", "")
        challenge = parsed.get("challenge", "")
        approach = parsed.get("approach", "")
        results = parsed.get("results", "")
        metrics_raw = parsed.get("metrics", "{}")
        team_text = parsed.get("team", "")
        testimonial = parsed.get("testimonial", "")

        # Parse metrics JSON
        try:
            metrics = parse_claude_json(metrics_raw)
            if not isinstance(metrics, dict):
                metrics = {}
        except Exception:
            metrics = {}

        # Header fields
        header_fields = {
            "Date": date.today().isoformat(),
            "Project": (
                f"{project.get('name', '')} ({validated['project_code']})"
            ),
            "Client": project.get("client_name", "N/A"),
            "Audience": validated["audience"].title(),
        }

        sections: list[Section] = []
        tables: list[TableData] = []

        # At a Glance
        if at_a_glance:
            sections.append(Section("At a Glance", at_a_glance))

        # Challenge
        if challenge:
            sections.append(Section("The Challenge", challenge))

        # Approach
        if approach:
            sections.append(Section("Our Approach", approach))

        # Results
        if results:
            sections.append(Section("Results", results))

        # Team
        if team_text:
            sections.append(Section("Project Team", team_text))

        # Testimonial
        if testimonial:
            sections.append(Section("Client Testimonial", testimonial))

        # Metrics table
        if metrics:
            metric_rows = []
            metric_labels = {
                "contract_value": "Contract Value",
                "duration_months": "Duration (Months)",
                "square_footage": "Square Footage",
                "on_time": "On Time",
                "on_budget": "On Budget",
                "safety_record": "Safety Record",
                "change_order_percent": "Change Order %",
                "rfis_closed": "RFIs Closed",
                "punch_items_resolved": "Punch Items Resolved",
            }
            for key, label in metric_labels.items():
                if key in metrics:
                    value = metrics[key]
                    if isinstance(value, bool):
                        value = "Yes" if value else "No"
                    metric_rows.append([label, str(value)])

            if metric_rows:
                tables.append(
                    TableData(
                        headers=["Metric", "Value"],
                        rows=metric_rows,
                        title="Key Metrics",
                    )
                )

        content = DocumentContent(
            title=title_text,
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            tables=tables,
            use_letterhead=True,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist to case_studies table
        self._persist_case_study(
            validated, parsed, metrics, output_path
        )

        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_sections(self, response: str) -> dict[str, str]:
        """Parse the section-break delimited response into a dict.

        Returns:
            Dict mapping section name to content for each of the 8
            expected sections.
        """
        parts = response.split(SECTION_DELIMITER)
        # Strip whitespace from each part
        parts = [p.strip() for p in parts if p.strip()]

        result: dict[str, str] = {}
        for idx, section_name in enumerate(EXPECTED_SECTIONS):
            if idx < len(parts):
                result[section_name] = parts[idx]
            else:
                result[section_name] = ""

        return result

    def _gather_project_metrics(self, project_id: int) -> str:
        """Gather quantitative metrics from the database."""
        lines: list[str] = []

        with get_db(self.settings) as conn:
            # Change order count and total
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt, "
                "COALESCE(SUM(total_with_markup_cents), 0) as total "
                "FROM change_orders WHERE project_id = ?",
                (project_id,),
            )
            row = cursor.fetchone()
            co_count = row["cnt"]
            co_total = row["total"]
            lines.append(
                f"Change Orders: {co_count} "
                f"(total: ${co_total / 100:,.2f})"
            )

            # Safety — incidents
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM incident_reports "
                "WHERE project_id = ?",
                (project_id,),
            )
            incident_count = cursor.fetchone()["cnt"]
            lines.append(f"Safety Incidents: {incident_count}")

            # RFIs
            cursor = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed "
                "FROM rfis WHERE project_id = ?",
                (project_id,),
            )
            rfi_row = cursor.fetchone()
            lines.append(
                f"RFIs: {rfi_row['total']} total, "
                f"{rfi_row['closed'] or 0} closed"
            )

            # Punch items
            cursor = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) "
                "as completed "
                "FROM punch_items WHERE project_id = ?",
                (project_id,),
            )
            punch_row = cursor.fetchone()
            lines.append(
                f"Punch Items: {punch_row['total']} total, "
                f"{punch_row['completed'] or 0} completed"
            )

        return "\n".join(lines) if lines else "No metrics available."

    def _get_lessons_summary(self, project_id: int) -> str:
        """Get a brief summary of lessons learned for this project."""
        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "SELECT title, category, severity "
                "FROM lessons_learned WHERE project_id = ? "
                "ORDER BY "
                "CASE severity "
                "  WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
                "  WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END "
                "LIMIT 10",
                (project_id,),
            )
            rows = cursor.fetchall()
            if not rows:
                return "No lessons learned recorded yet."

            lines = []
            for r in rows:
                lines.append(
                    f"  - [{r['severity'].upper()}] {r['category']}: "
                    f"{r['title']}"
                )
            return "\n".join(lines)

    def _get_audience_guidance(self, audience: str) -> str:
        """Return audience-specific writing guidance.

        Args:
            audience: Target audience — 'client', 'marketing', or 'proposal'.

        Returns:
            Guidance string for the system prompt.
        """
        if audience == "client":
            return (
                "TONE GUIDANCE:\n"
                "- Write for the project owner/client.\n"
                "- Emphasize value delivered, schedule adherence, and "
                "relationship quality.\n"
                "- Keep technical jargon minimal.\n"
                "- Highlight how challenges were resolved transparently.\n"
                "- Suitable for a thank-you package or project close-out."
            )
        elif audience == "proposal":
            return (
                "TONE GUIDANCE:\n"
                "- Write for inclusion in a future bid or proposal.\n"
                "- Emphasize relevant experience, problem-solving capability, "
                "and quantifiable results.\n"
                "- Highlight team qualifications and approach.\n"
                "- Use language that builds confidence in the reader.\n"
                "- Include metrics that demonstrate performance."
            )
        else:  # marketing
            return (
                "TONE GUIDANCE:\n"
                "- Write for the company website, brochure, or social media.\n"
                "- Lead with a compelling narrative — the story matters.\n"
                "- Balance technical achievement with human interest.\n"
                "- Make it visually scannable with clear section breaks.\n"
                "- Suitable for a general audience."
            )

    def _persist_case_study(
        self,
        validated: dict,
        parsed: dict[str, str],
        metrics: dict,
        output_path: Path,
    ) -> None:
        """Save case study to the case_studies table."""
        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO case_studies "
                "(project_id, title, raw_input, executive_summary, "
                "challenge_section, solution_section, results_section, "
                "key_metrics, testimonial, photo_paths, "
                "target_audience, status, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    validated["project_id"],
                    parsed.get("title", "Untitled Case Study"),
                    validated["notes"],
                    parsed.get("at_a_glance", ""),
                    parsed.get("challenge", ""),
                    parsed.get("approach", ""),
                    parsed.get("results", ""),
                    json.dumps(metrics),
                    parsed.get("testimonial"),
                    json.dumps(validated["photos"]),
                    validated["audience"],
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
            f"Type: {project.get('project_type', 'N/A')}",
            f"Delivery Method: {project.get('delivery_method', 'N/A')}",
            f"Contract Value: {contract_display}",
            f"Square Footage: {project.get('square_footage', 'N/A')}",
            f"Status: {project.get('status', 'N/A')}",
            f"Percent Complete: "
            f"{project.get('current_percent_complete', 0)}%",
        ]

        if project.get("actual_start_date"):
            lines.append(f"Start Date: {project['actual_start_date']}")
        if project.get("actual_completion_date"):
            lines.append(
                f"Completion Date: {project['actual_completion_date']}"
            )
        elif project.get("substantial_completion_date"):
            lines.append(
                f"Target Completion: "
                f"{project['substantial_completion_date']}"
            )

        if context.team:
            lines.append("\nProject Team:")
            for member in context.team:
                name = (
                    f"{member.get('first_name', '')} "
                    f"{member.get('last_name', '')}"
                ).strip()
                role = member.get("project_role", member.get("title", ""))
                lines.append(f"  - {name} ({role})")

        if context.subcontractors:
            lines.append("\nKey Subcontractors:")
            for sub in context.subcontractors:
                lines.append(
                    f"  - {sub['company_name']} ({sub['trade']})"
                )

        return "\n".join(lines)
