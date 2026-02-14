"""Proposal Generator — Skill #13.

Generates full construction proposals, letter proposals, or statements of
qualifications for new business pursuits.  Loads the complete company
knowledge base (profile, team bios, writing standards, safety standards)
and queries completed projects and case studies from the database to
populate the experience section.

Uses the Opus model for the precision and quality required in client-facing
proposals.
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
    TableData,
)
from kruppai.skills.base import BaseSkill

VALID_PROPOSAL_TYPES = {"full", "letter", "qualification"}

PROPOSAL_TYPE_LABELS = {
    "full": "Full Proposal",
    "letter": "Letter Proposal",
    "qualification": "Statement of Qualifications",
}

# Sections expected in Claude's output, separated by ---SECTION BREAK---
PROPOSAL_SECTIONS = [
    "Cover Letter",
    "Executive Summary",
    "Approach",
    "Team",
    "Experience",
    "Schedule",
    "Safety",
    "Fee Narrative",
]


class ProposalGeneratorSkill(BaseSkill):
    """Generate professional construction proposals from rough descriptions."""

    skill_name = "proposal_generator"
    display_name = "Proposal Generator"
    description = "Generate a professional construction proposal or SOQ"
    phase = 3
    default_model = "opus"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate proposal generator input.

        Required: client, description.
        Optional: project, proposal_type, rfp_file.
        """
        project_code = kwargs.get("project")
        client = kwargs.get("client")
        description = kwargs.get("description")
        proposal_type = kwargs.get("proposal_type", "full")
        rfp_file = kwargs.get("rfp_file")

        if not client:
            raise ValueError(
                "Client name is required. Use --client or -c."
            )
        if not description:
            raise ValueError(
                "Project description is required. Use --description or -d."
            )

        desc_str = str(description).strip()
        if len(desc_str) < 20:
            raise ValueError(
                "Project description must be at least 20 characters."
            )

        proposal_type_str = str(proposal_type).lower()
        if proposal_type_str not in VALID_PROPOSAL_TYPES:
            raise ValueError(
                f"Invalid proposal type: '{proposal_type_str}'. "
                f"Valid options: {', '.join(sorted(VALID_PROPOSAL_TYPES))}"
            )

        # Validate RFP file if provided
        rfp_path_str: str | None = None
        if rfp_file:
            rfp_path = Path(str(rfp_file))
            if not rfp_path.exists():
                raise ValueError(f"RFP file not found: {rfp_path}")
            if rfp_path.suffix.lower() not in {".pdf", ".docx", ".xlsx", ".txt"}:
                raise ValueError(
                    "RFP file must be PDF, DOCX, XLSX, or TXT format."
                )
            rfp_path_str = str(rfp_path)

        project_id = None
        project_code_str: str | None = None
        if project_code:
            context = self.context_manager.load_by_code(str(project_code))
            project_id = context.project["id"]
            project_code_str = str(project_code)

        return {
            "project_id": project_id,
            "project_code": project_code_str,
            "client": str(client).strip(),
            "description": desc_str,
            "proposal_type": proposal_type_str,
            "rfp_file_path": rfp_path_str,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for proposal generation."""
        company = context.company if context else {}

        # Load ALL knowledge base files
        company_profile = self.knowledge_base.load_file("company_profile") or ""
        team_bios = self.knowledge_base.load_file("team_bios") or ""
        writing_standards = self.knowledge_base.load_file("writing_standards") or ""
        safety_standards = self.knowledge_base.load_file("safety_standards") or ""

        # Load completed projects and case studies for experience section
        experience_context = self._load_experience_data()

        # Build project context if available
        project_context = ""
        if context:
            project = context.project
            contract_display = "N/A"
            if project.get("current_contract_cents"):
                contract_display = (
                    f"${project['current_contract_cents'] / 100:,.2f}"
                )
            project_context = (
                f"Project: {project.get('name', 'N/A')} "
                f"({project.get('project_code', 'N/A')})\n"
                f"Type: {project.get('project_type', 'N/A')}\n"
                f"Contract Value: {contract_display}\n"
                f"Delivery Method: {project.get('delivery_method', 'N/A')}\n"
            )

        # Parse RFP if provided
        rfp_text = ""
        if validated.get("rfp_file_path"):
            parsed_rfp = parse_file(Path(validated["rfp_file_path"]))
            if not parsed_rfp.error:
                rfp_text = f"\nRFP DOCUMENT:\n{parsed_rfp.text[:30000]}\n"

        proposal_type_label = PROPOSAL_TYPE_LABELS.get(
            validated["proposal_type"], "Full Proposal"
        )
        sections_list = "\n".join(
            f"  {i + 1}. {s}" for i, s in enumerate(PROPOSAL_SECTIONS)
        )

        system_prompt = f"""You are a senior business development writer for {company.get('name', 'Krupp General Contractors')}.
You are creating a {proposal_type_label} for {validated['client']}.

COMPANY PROFILE:
{company_profile or 'Krupp General Contractors is a full-service general contractor and construction manager.'}

TEAM BIOS:
{team_bios or 'Team information not available.'}

WRITING STANDARDS:
{writing_standards or 'Use professional, client-facing tone. Be specific, avoid vague claims.'}

SAFETY STANDARDS:
{safety_standards or 'Krupp maintains a best-in-class safety program.'}

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

EXPERIENCE / COMPLETED PROJECTS:
{experience_context}

INSTRUCTIONS:
1. Generate a professional {proposal_type_label} that positions Krupp as the
   best-value contractor for this opportunity.

2. The proposal MUST contain these sections, each separated by exactly
   "---SECTION BREAK---" on its own line:
{sections_list}

3. SECTION REQUIREMENTS:
   - Cover Letter: Personalized letter to the client, expressing interest and
     key differentiators. Professional but warm tone. Address the client by name.
   - Executive Summary: Concise overview of Krupp's understanding of the project,
     approach, and value proposition. 2-3 paragraphs.
   - Approach: Detailed construction approach, phasing, logistics, quality
     control, and communication plan.
   - Team: Proposed project team with relevant experience. Reference actual
     team members from bios when available.
   - Experience: 3-5 relevant completed projects. Use actual completed
     projects and case studies when available.
   - Schedule: High-level schedule approach, milestones, and commitment
     to the client's timeline.
   - Safety: Krupp's safety program overview, EMR, training, site-specific
     safety planning.
   - Fee Narrative: Value-based fee discussion (do NOT include specific
     dollar amounts unless provided). Emphasize transparency, open-book
     approach, and cost controls.

4. CRITICAL RULES:
   - Sound like Krupp, not generic AI — use the company voice from writing standards
   - Be specific: reference project types, team names, and real capabilities
   - Client-facing quality: this will be sent to the client
   - No placeholder text like "[Insert X]" — generate complete content
   - If information is missing, write confidently with reasonable assumptions
     marked with [VERIFY]

5. OUTPUT FORMAT:
   Return the full proposal text with sections separated by "---SECTION BREAK---".
   Do NOT return JSON. Return formatted text only."""

        user_content = (
            f"OPPORTUNITY:\n"
            f"Client: {validated['client']}\n"
            f"Proposal Type: {proposal_type_label}\n"
            f"Description: {validated['description']}"
        )
        if rfp_text:
            user_content += f"\n\n{rfp_text}"

        return [
            {"role": "user", "content": user_content},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format the proposal as a branded DOCX document."""
        project_info = ProjectInfo(
            project_code=validated.get("project_code") or "PROPOSAL",
            name=validated["description"][:60],
            client_name=validated["client"],
        )

        # Parse sections from the response
        sections = self._parse_sections(response)

        # Build document
        doc_sections: list[Section] = []
        for heading, content in sections:
            doc_sections.append(Section(heading, content))

        proposal_type_label = PROPOSAL_TYPE_LABELS.get(
            validated["proposal_type"], "Full Proposal"
        )

        content = DocumentContent(
            title=f"{proposal_type_label} — {validated['client']}",
            subtitle=validated["description"][:100],
            date=date.today().isoformat(),
            header_fields={
                "Client": validated["client"],
                "Proposal Type": proposal_type_label,
                "Date": date.today().isoformat(),
                "Prepared By": "Krupp General Contractors",
            },
            sections=doc_sections,
            tables=[],
            use_letterhead=True,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist to proposals table
        self._persist_proposal(validated, sections, output_path)

        return output_path

    def _parse_sections(self, response: str) -> list[tuple[str, str]]:
        """Parse Claude's response into (heading, content) tuples.

        The response is expected to have sections separated by
        ``---SECTION BREAK---``.  If no separators are found, the entire
        response is returned as a single section.
        """
        parts = response.split("---SECTION BREAK---")

        # Clean up parts
        cleaned_parts = [p.strip() for p in parts if p.strip()]

        if not cleaned_parts:
            return [("Proposal", response.strip())]

        result: list[tuple[str, str]] = []
        for idx, part in enumerate(cleaned_parts):
            # Try to use the expected section headings
            if idx < len(PROPOSAL_SECTIONS):
                heading = PROPOSAL_SECTIONS[idx]
            else:
                heading = f"Section {idx + 1}"

            # If the part starts with a heading-like line, extract it
            lines = part.split("\n", 1)
            first_line = lines[0].strip().strip("#").strip(":").strip()

            # Check if the first line matches a known section heading
            if first_line.lower() in {s.lower() for s in PROPOSAL_SECTIONS}:
                heading = first_line
                content = lines[1].strip() if len(lines) > 1 else ""
            else:
                content = part

            result.append((heading, content))

        return result

    def _load_experience_data(self) -> str:
        """Load completed projects and case studies from the database."""
        try:
            with get_db(self.settings) as conn:
                # Completed projects
                cursor = conn.execute(
                    "SELECT name, client_name, project_type, "
                    "current_contract_cents, square_footage, "
                    "description "
                    "FROM projects "
                    "WHERE status = 'complete' "
                    "ORDER BY actual_completion_date DESC "
                    "LIMIT 10"
                )
                projects = cursor.fetchall()

                # Case studies
                cursor = conn.execute(
                    "SELECT cs.title, cs.executive_summary, "
                    "cs.results_section, cs.key_metrics, "
                    "p.client_name, p.project_type "
                    "FROM case_studies cs "
                    "JOIN projects p ON cs.project_id = p.id "
                    "WHERE cs.status != 'draft' "
                    "ORDER BY cs.created_at DESC "
                    "LIMIT 5"
                )
                case_studies = cursor.fetchall()
        except Exception:
            return "No completed project data available."

        lines: list[str] = []

        if projects:
            lines.append("COMPLETED PROJECTS:")
            for proj in projects:
                value = ""
                if proj["current_contract_cents"]:
                    value = f" | ${proj['current_contract_cents'] / 100:,.0f}"
                sqft = ""
                if proj["square_footage"]:
                    sqft = f" | {proj['square_footage']:,} SF"
                lines.append(
                    f"  - {proj['name']} ({proj['project_type'] or 'N/A'})"
                    f" for {proj['client_name'] or 'N/A'}{value}{sqft}"
                )
                if proj["description"]:
                    lines.append(f"    {proj['description'][:200]}")

        if case_studies:
            lines.append("\nCASE STUDIES:")
            for cs in case_studies:
                lines.append(f"  - {cs['title']}")
                if cs["executive_summary"]:
                    lines.append(f"    {cs['executive_summary'][:300]}")
                if cs["key_metrics"]:
                    try:
                        metrics = json.loads(cs["key_metrics"])
                        metrics_str = ", ".join(
                            f"{k}: {v}" for k, v in metrics.items()
                        )
                        lines.append(f"    Metrics: {metrics_str}")
                    except (json.JSONDecodeError, AttributeError):
                        pass

        return "\n".join(lines) if lines else "No completed project data available."

    def _persist_proposal(
        self,
        validated: dict,
        sections: list[tuple[str, str]],
        output_path: Path,
    ) -> None:
        """Persist the proposal to the proposals table."""
        # Map sections to database columns
        section_map: dict[str, str] = {}
        for heading, content in sections:
            section_map[heading.lower()] = content

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO proposals "
                "(project_id, proposal_name, client_name, "
                "project_description, raw_input, rfp_file_path, "
                "proposal_type, executive_summary, approach, "
                "team_section, experience_section, schedule_section, "
                "safety_section, fee_narrative, status, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    validated.get("project_id"),
                    f"Proposal for {validated['client']}",
                    validated["client"],
                    validated["description"],
                    validated["description"],
                    validated.get("rfp_file_path"),
                    validated["proposal_type"],
                    section_map.get("executive summary", ""),
                    section_map.get("approach", ""),
                    section_map.get("team", ""),
                    section_map.get("experience", ""),
                    section_map.get("schedule", ""),
                    section_map.get("safety", ""),
                    section_map.get("fee narrative", ""),
                    str(output_path),
                ),
            )
