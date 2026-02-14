"""Toolbox / Safety Talk Generator — Skill #5.

Generates a 5-10 minute safety talk document on any construction safety
topic. These are required daily on most job sites and PMs/supers often
struggle to keep them fresh and relevant.
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
    TableData,
)
from kruppai.skills.base import BaseSkill

VALID_SEASONS = {"spring", "summer", "fall", "winter"}


class SafetyTalkSkill(BaseSkill):
    """Generate toolbox safety talks for construction crews."""

    skill_name = "safety_talk"
    display_name = "Toolbox Safety Talk"
    description = "Generate a safety talk document on any construction topic"
    phase = 1
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate safety talk input.

        Required: topic.
        Optional: project, season, trades.
        """
        topic = kwargs.get("topic")
        project_code = kwargs.get("project")
        season = kwargs.get("season")
        trades = kwargs.get("trades")

        if not topic:
            raise ValueError("Safety topic is required. Use --topic or -t.")

        topic_str = str(topic)
        if len(topic_str.strip()) < 5:
            raise ValueError("Topic must be at least 5 characters.")

        # Optional project context
        project_id = None
        if project_code:
            context = self.context_manager.load_by_code(str(project_code))
            project_id = context.project["id"]

        # Validate season
        season_str = None
        if season:
            season_str = str(season).lower()
            if season_str not in VALID_SEASONS:
                raise ValueError(
                    f"Invalid season: '{season_str}'. "
                    f"Choose from: {', '.join(VALID_SEASONS)}"
                )

        # Parse trades
        trades_list: list[str] = []
        if trades:
            trades_list = [t.strip() for t in str(trades).split(",") if t.strip()]

        return {
            "project_id": project_id,
            "project_code": str(project_code) if project_code else None,
            "topic": topic_str,
            "season": season_str,
            "trades": trades_list,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for safety talk generation."""
        company = context.company if context else {}

        safety_standards = self.knowledge_base.load_file("safety_standards") or ""

        project_context_str = ""
        if context:
            project = context.project
            project_context_str = (
                f"\nPROJECT CONTEXT:\n"
                f"Project: {project.get('name', 'N/A')}\n"
                f"Location: {project.get('address', 'N/A')}, "
                f"{project.get('city', '')}, {project.get('state', '')}\n"
                f"Type: {project.get('project_type', 'N/A')}\n"
                f"Percent Complete: {project.get('current_percent_complete', 0)}%"
            )

        season_note = ""
        if validated.get("season"):
            season_note = f"\nSEASON: {validated['season'].title()} — adjust content for seasonal hazards."

        trades_note = ""
        if validated.get("trades"):
            trades_note = f"\nATTENDING TRADES: {', '.join(validated['trades'])}"

        system_prompt = f"""You are a construction safety professional writing a toolbox talk for {company.get('name', 'Krupp General Contractors')}.

COMPANY SAFETY STANDARDS:
{safety_standards}
{project_context_str}
{season_note}
{trades_note}

INSTRUCTIONS:
1. Write a 5-10 minute toolbox safety talk on the given topic.

2. STRUCTURE:
   - TITLE: Clear, specific title
   - INTRODUCTION (30 seconds): Why this topic matters TODAY. Reference current site conditions if project context is provided.
   - KEY HAZARDS (2 minutes): What can go wrong. Be specific and vivid — not abstract.
   - PROTECTIVE MEASURES (3 minutes): What workers must do. Numbered, actionable steps. Reference specific PPE, procedures, and OSHA requirements.
   - REAL-WORLD EXAMPLE (1 minute): A brief, realistic scenario (not graphic) that illustrates the hazard.
   - DISCUSSION QUESTIONS (2 minutes): 2-3 questions to engage the crew in dialogue.
   - SUMMARY: 3-5 key takeaways as bullet points.
   - OSHA REFERENCES: Applicable OSHA standards (e.g., 29 CFR 1926.501 for fall protection)

3. TONE RULES:
   - Conversational, not lecture-style. This is a foreman talking to a crew.
   - Specific to construction, not generic workplace safety.
   - Seasonal awareness: heat stress in summer, cold stress in winter, etc.
   - Trade-specific when applicable.
   - Respectful of workers' experience — don't be condescending.

4. OUTPUT FORMAT:
   Return the complete talk as formatted text with clear section headers.
   Use markdown ## headers for each section."""

        return [
            {"role": "user", "content": f"SAFETY TOPIC:\n{validated['topic']}"},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format the safety talk as a branded DOCX with sign-in sheet."""
        project_info = ProjectInfo(
            project_code=validated.get("project_code") or "GENERAL",
            name=context.project.get("name", "") if context else "",
            client_name="",
        )

        # Parse sections from markdown response
        sections = self._parse_talk_sections(response)

        header_fields = {
            "Date": date.today().isoformat(),
            "Topic": validated["topic"][:80],
        }
        if validated.get("project_code") and context:
            header_fields["Project"] = (
                f"{context.project.get('name', '')} ({validated['project_code']})"
            )
        if validated.get("season"):
            header_fields["Season"] = validated["season"].title()
        if validated.get("trades"):
            header_fields["Trades"] = ", ".join(validated["trades"])

        # Sign-in table (15 blank rows)
        sign_in_rows = [["", "", ""] for _ in range(15)]
        tables = [
            TableData(
                headers=["Name", "Company", "Signature"],
                rows=sign_in_rows,
                title="Attendee Sign-In",
            )
        ]

        content = DocumentContent(
            title="Toolbox Safety Talk",
            date=date.today().isoformat(),
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist to safety_talks table
        self._persist_safety_talk(validated, response, output_path)

        return output_path

    def _parse_talk_sections(self, response: str) -> list[Section]:
        """Parse markdown-formatted safety talk into Section objects."""
        sections: list[Section] = []
        current_heading = ""
        current_lines: list[str] = []

        for line in response.split("\n"):
            stripped = line.strip()
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

        if current_heading or current_lines:
            sections.append(
                Section(current_heading, "\n".join(current_lines))
            )

        if not sections:
            sections.append(Section("Safety Talk", response))

        return sections

    def _persist_safety_talk(
        self,
        validated: dict,
        talk_content: str,
        output_path: Path,
    ) -> None:
        """Save safety talk to the safety_talks table."""
        import json

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO safety_talks "
                "(project_id, topic, raw_input, talk_content, "
                "applicable_trades, season, talk_date, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated.get("project_id"),
                    validated["topic"],
                    validated["topic"],
                    talk_content,
                    json.dumps(validated.get("trades", [])),
                    validated.get("season"),
                    date.today().isoformat(),
                    str(output_path),
                ),
            )
