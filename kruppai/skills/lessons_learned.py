"""Lessons Learned — Skill #16.

Two modes of operation:
- **manual**: PM provides session notes from a lessons-learned workshop;
  Claude structures them into categorized, actionable lessons.
- **extract**: Claude mines existing project data (daily reports, meeting
  minutes, change orders) and surfaces patterns worth capturing.
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

VALID_CATEGORIES = {
    "scheduling",
    "budget",
    "subcontractor",
    "design",
    "safety",
    "client",
    "procurement",
    "quality",
}

CATEGORY_LABELS = {
    "scheduling": "Scheduling & Sequencing",
    "budget": "Budget & Cost Control",
    "subcontractor": "Subcontractor Management",
    "design": "Design & Coordination",
    "safety": "Safety",
    "client": "Client Relations",
    "procurement": "Procurement & Materials",
    "quality": "Quality Control",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class LessonsLearnedSkill(BaseSkill):
    """Extract and structure project lessons learned."""

    skill_name = "lessons_learned"
    display_name = "Lessons Learned"
    description = "Capture and structure lessons learned from project experience"
    phase = 3
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate lessons learned input.

        Required: project (code), notes.
        Optional: mode (manual/extract), category.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        project_code = kwargs.get("project")
        notes = kwargs.get("notes")
        mode = kwargs.get("mode", "manual")
        category = kwargs.get("category")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not notes:
            raise ValueError(
                "Session notes are required. Use --notes or -n."
            )

        notes_str = str(notes)
        if len(notes_str.strip()) < 20:
            raise ValueError(
                "Notes must be at least 20 characters."
            )

        mode_str = str(mode).lower()
        if mode_str not in {"manual", "extract"}:
            raise ValueError(
                "Mode must be 'manual' or 'extract'."
            )

        if category:
            cat_str = str(category).lower()
            if cat_str not in VALID_CATEGORIES:
                raise ValueError(
                    f"Invalid category: '{cat_str}'. "
                    f"Valid options: {', '.join(sorted(VALID_CATEGORIES))}"
                )
        else:
            cat_str = None

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "notes": notes_str,
            "mode": mode_str,
            "category": cat_str,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for lessons learned generation.

        In manual mode, the PM's session notes are provided directly.
        In extract mode, project data is mined from the database and
        appended so Claude can surface patterns.
        """
        company = context.company if context else {}
        project = context.project if context else {}

        project_context = self._format_project_context(context)

        # Fetch existing lessons to avoid duplicates
        existing_titles = self._get_existing_lesson_titles(
            validated["project_id"]
        )
        existing_note = ""
        if existing_titles:
            existing_note = (
                "\n\nEXISTING LESSONS ALREADY CAPTURED (do not duplicate):\n"
                + "\n".join(f"  - {t}" for t in existing_titles)
            )

        category_filter = ""
        if validated["category"]:
            label = CATEGORY_LABELS.get(
                validated["category"], validated["category"]
            )
            category_filter = (
                f"\n\nFOCUS CATEGORY: {label} — concentrate analysis on "
                f"this category, but include others if clearly warranted."
            )

        writing_standards = (
            self.knowledge_base.load_file("writing_standards") or ""
        )

        system_prompt = f"""You are a senior construction lessons-learned facilitator for {company.get('name', 'Krupp General Contractors')}.

PROJECT CONTEXT:
{project_context}
{existing_note}
{category_filter}

WRITING STANDARDS:
{writing_standards}

INSTRUCTIONS:
1. Analyze the provided input and extract distinct, actionable lessons learned.

2. For each lesson, produce:
   - title: Short descriptive title (max 80 chars)
   - category: One of {sorted(VALID_CATEGORIES)}
   - situation: What happened (2-3 sentences)
   - impact: Consequence — schedule, cost, quality, safety, or relationship (1-2 sentences)
   - lesson: The takeaway (1-2 sentences, starts with a verb)
   - recommendation: Specific action for future projects (1-2 sentences)
   - severity: 'low', 'medium', 'high', or 'critical'
   - applicable_project_types: JSON array of project types this applies to (e.g., ["commercial", "healthcare"])
   - tags: JSON array of searchable keywords

3. RULES:
   - Each lesson must be distinct and actionable.
   - Do NOT duplicate any existing lessons listed above.
   - severity reflects the potential consequence if the lesson is ignored.
   - Be specific: reference trades, phases, or systems where possible.
   - Use professional, objective language.
   - Return between 3 and 15 lessons depending on the input richness.

4. OUTPUT FORMAT:
   Return a JSON array:
   [
     {{
       "title": "Lesson title",
       "category": "scheduling",
       "situation": "What happened",
       "impact": "What was the consequence",
       "lesson": "What we learned",
       "recommendation": "What to do differently",
       "severity": "high",
       "applicable_project_types": ["commercial"],
       "tags": ["coordination", "MEP"]
     }}
   ]"""

        # Build user content based on mode
        if validated["mode"] == "manual":
            user_content = (
                f"LESSONS LEARNED SESSION NOTES:\n{validated['notes']}"
            )
        else:
            # Extract mode: mine project data
            project_data = self._extract_project_data(
                validated["project_id"]
            )
            user_content = (
                f"GUIDANCE:\n{validated['notes']}\n\n"
                f"PROJECT DATA TO ANALYZE:\n{project_data}"
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
        """Format lessons learned as a branded DOCX.

        Lessons are sorted by severity (critical first), then grouped
        into sections. A summary table is included at the top.
        """
        lessons = parse_claude_json(response)
        if not isinstance(lessons, list):
            lessons = [lessons]

        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
        )

        # Sort by severity
        lessons.sort(
            key=lambda l: SEVERITY_ORDER.get(
                l.get("severity", "medium"), 2
            )
        )

        # Header fields
        header_fields = {
            "Date": date.today().isoformat(),
            "Project": (
                f"{project.get('name', '')} ({validated['project_code']})"
            ),
            "Mode": validated["mode"].title(),
            "Total Lessons": str(len(lessons)),
        }

        sections: list[Section] = []
        tables: list[TableData] = []

        # Summary table
        summary_rows = []
        for idx, lesson in enumerate(lessons, start=1):
            summary_rows.append([
                str(idx),
                lesson.get("title", "Untitled"),
                CATEGORY_LABELS.get(
                    lesson.get("category", ""), lesson.get("category", "")
                ),
                lesson.get("severity", "medium").upper(),
            ])

        tables.append(
            TableData(
                headers=["#", "Title", "Category", "Severity"],
                rows=summary_rows,
                title="Lessons Summary",
            )
        )

        # Detailed sections — one per lesson
        for idx, lesson in enumerate(lessons, start=1):
            title = lesson.get("title", "Untitled")
            category = CATEGORY_LABELS.get(
                lesson.get("category", ""), lesson.get("category", "")
            )
            severity = lesson.get("severity", "medium").upper()

            body_parts = [
                f"Category: {category}  |  Severity: {severity}",
                "",
                f"Situation: {lesson.get('situation', 'N/A')}",
                "",
                f"Impact: {lesson.get('impact', 'N/A')}",
                "",
                f"Lesson: {lesson.get('lesson', 'N/A')}",
                "",
                f"Recommendation: {lesson.get('recommendation', 'N/A')}",
            ]

            tags = lesson.get("tags", [])
            if tags:
                body_parts.append("")
                body_parts.append(f"Tags: {', '.join(tags)}")

            applicable = lesson.get("applicable_project_types", [])
            if applicable:
                body_parts.append(
                    f"Applicable To: {', '.join(applicable)}"
                )

            sections.append(
                Section(f"Lesson {idx}: {title}", "\n".join(body_parts))
            )

        # Category breakdown table
        category_counts: dict[str, int] = {}
        for lesson in lessons:
            cat = lesson.get("category", "other")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        cat_rows = [
            [CATEGORY_LABELS.get(cat, cat), str(count)]
            for cat, count in sorted(
                category_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ]
        tables.append(
            TableData(
                headers=["Category", "Count"],
                rows=cat_rows,
                title="Lessons by Category",
            )
        )

        content = DocumentContent(
            title="Lessons Learned Report",
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist each lesson individually
        self._persist_lessons(validated, lessons, output_path)

        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_existing_lesson_titles(self, project_id: int) -> list[str]:
        """Return titles of lessons already recorded for this project."""
        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "SELECT title FROM lessons_learned WHERE project_id = ?",
                (project_id,),
            )
            return [row["title"] for row in cursor.fetchall()]

    def _extract_project_data(self, project_id: int) -> str:
        """Mine daily reports, meetings, and change orders for extract mode."""
        lines: list[str] = []

        with get_db(self.settings) as conn:
            # Daily reports — look for delays and issues
            cursor = conn.execute(
                "SELECT report_date, delays, issues, safety_observations, "
                "quality_observations "
                "FROM daily_reports WHERE project_id = ? "
                "ORDER BY report_date DESC LIMIT 30",
                (project_id,),
            )
            rows = cursor.fetchall()
            if rows:
                lines.append("=== DAILY REPORTS (recent 30) ===")
                for r in rows:
                    parts = [f"Date: {r['report_date']}"]
                    if r["delays"]:
                        parts.append(f"  Delays: {r['delays']}")
                    if r["issues"]:
                        parts.append(f"  Issues: {r['issues']}")
                    if r["safety_observations"]:
                        parts.append(
                            f"  Safety: {r['safety_observations']}"
                        )
                    if r["quality_observations"]:
                        parts.append(
                            f"  Quality: {r['quality_observations']}"
                        )
                    if len(parts) > 1:
                        lines.append("\n".join(parts))

            # Meetings — decisions and action items
            cursor = conn.execute(
                "SELECT meeting_date, meeting_type, decisions, "
                "formatted_minutes "
                "FROM meetings WHERE project_id = ? "
                "ORDER BY meeting_date DESC LIMIT 20",
                (project_id,),
            )
            rows = cursor.fetchall()
            if rows:
                lines.append("\n=== MEETINGS (recent 20) ===")
                for r in rows:
                    parts = [
                        f"Date: {r['meeting_date']} "
                        f"({r['meeting_type']})"
                    ]
                    if r["decisions"]:
                        parts.append(f"  Decisions: {r['decisions']}")
                    lines.append("\n".join(parts))

            # Change orders — reasons and impacts
            cursor = conn.execute(
                "SELECT co_number, title, reason, cost_cents, "
                "schedule_impact_days, description "
                "FROM change_orders WHERE project_id = ? "
                "ORDER BY co_number",
                (project_id,),
            )
            rows = cursor.fetchall()
            if rows:
                lines.append("\n=== CHANGE ORDERS ===")
                for r in rows:
                    cost = r["cost_cents"] or 0
                    lines.append(
                        f"CO #{r['co_number']}: {r['title']} — "
                        f"Reason: {r['reason']}, "
                        f"Cost: ${cost / 100:,.2f}, "
                        f"Schedule: {r['schedule_impact_days'] or 0} days"
                    )
                    if r["description"]:
                        lines.append(f"  {r['description'][:200]}")

        return "\n".join(lines) if lines else "No project data found."

    def _persist_lessons(
        self,
        validated: dict,
        lessons: list[dict],
        output_path: Path,
    ) -> None:
        """Save each lesson individually to the lessons_learned table."""
        source = "manual" if validated["mode"] == "manual" else "extract"

        with get_db(self.settings) as conn:
            for lesson in lessons:
                applicable = lesson.get("applicable_project_types", [])
                tags = lesson.get("tags", [])

                conn.execute(
                    "INSERT INTO lessons_learned "
                    "(project_id, category, title, situation, impact, "
                    "lesson, recommendation, applicable_project_types, "
                    "tags, severity, source, document_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        validated["project_id"],
                        lesson.get("category", "quality"),
                        lesson.get("title", "Untitled"),
                        lesson.get("situation", ""),
                        lesson.get("impact", ""),
                        lesson.get("lesson", ""),
                        lesson.get("recommendation", ""),
                        json.dumps(applicable),
                        json.dumps(tags),
                        lesson.get("severity", "medium"),
                        source,
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
            f"Status: {project.get('status', 'N/A')}",
            f"Contract Value: {contract_display}",
            f"Percent Complete: {project.get('current_percent_complete', 0)}%",
        ]

        if context.subcontractors:
            lines.append("\nSubcontractors:")
            for sub in context.subcontractors:
                lines.append(
                    f"  - {sub['company_name']} ({sub['trade']})"
                )

        return "\n".join(lines)
