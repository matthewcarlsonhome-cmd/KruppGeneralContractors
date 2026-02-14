"""Schedule Variance Analyzer — Skill #10.

Parses an uploaded project schedule (PDF or XLSX), compares planned vs
actual progress, identifies critical path risks, and generates a
narrative analysis with recommendations.
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


class ScheduleVarianceSkill(BaseSkill):
    """Analyze schedule variance and identify critical path risks."""

    skill_name = "schedule_variance"
    display_name = "Schedule Variance Analyzer"
    description = "Analyze a project schedule for variance and critical path risks"
    phase = 2
    default_model = "sonnet"
    output_formats = ["docx", "xlsx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate schedule analysis input.

        Required: project (code), file (path to schedule).
        Optional: notes (PM observations).
        """
        project_code = kwargs.get("project")
        file_path = kwargs.get("file")
        notes = kwargs.get("notes", "")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not file_path:
            raise ValueError("Schedule file is required. Use --file or -f.")

        path = Path(str(file_path))
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        if path.suffix.lower() not in {".pdf", ".xlsx", ".xls", ".csv"}:
            raise ValueError(
                "Schedule file must be PDF, XLSX, XLS, or CSV format."
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
        """Build the Claude API messages for schedule analysis."""
        company = context.company if context else {}
        project = context.project if context else {}

        # Parse schedule file
        parsed = parse_file(Path(validated["file_path"]))
        if parsed.error:
            raise ValueError(f"Could not parse schedule file: {parsed.error}")

        project_context = ""
        if context:
            project_context = (
                f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})\n"
                f"NTP Date: {project.get('notice_to_proceed_date', 'N/A')}\n"
                f"Substantial Completion: {project.get('substantial_completion_date', 'N/A')}\n"
                f"Current % Complete: {project.get('current_percent_complete', 0)}%\n"
                f"Contract Value: ${project.get('current_contract_cents', 0) / 100:,.2f}\n"
            )

        # Get prior schedule snapshots
        prior_snapshots = ""
        with get_db(self.settings) as conn:
            cursor = conn.execute(
                "SELECT snapshot_date, variance_days, projected_completion_date "
                "FROM schedule_snapshots "
                "WHERE project_id = ? ORDER BY snapshot_date DESC LIMIT 3",
                (validated["project_id"],),
            )
            rows = cursor.fetchall()
            if rows:
                lines = []
                for r in rows:
                    v = r["variance_days"] or 0
                    status = "behind" if v > 0 else "ahead" if v < 0 else "on time"
                    lines.append(
                        f"  {r['snapshot_date']}: {abs(v)} days {status} "
                        f"(projected: {r['projected_completion_date'] or 'N/A'})"
                    )
                prior_snapshots = "\n".join(lines)
            else:
                prior_snapshots = "No prior schedule snapshots."

        pm_notes = ""
        if validated["notes"]:
            pm_notes = f"\n\nPM OBSERVATIONS:\n{validated['notes']}"

        system_prompt = f"""You are a senior construction scheduler for {company.get('name', 'Krupp General Contractors')}.
You are analyzing a project schedule to identify variance, critical path risks, and recovery opportunities.

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

PRIOR SCHEDULE SNAPSHOTS:
{prior_snapshots}

TODAY'S DATE: {date.today().isoformat()}

INSTRUCTIONS:
1. PARSE the schedule data and identify:
   - Activities that are behind schedule
   - Activities on the critical path
   - Float consumption trends
   - Upcoming milestones at risk

2. CALCULATE schedule variance:
   - Overall project variance in days (positive = behind, negative = ahead)
   - Projected completion date vs planned completion
   - Identify the top 5 activities driving delay

3. ASSESS RISK:
   - Critical path activities at risk
   - Activities with minimal remaining float
   - Weather, procurement, or inspection risks
   - Subcontractor performance concerns

4. RECOMMEND recovery actions:
   - Specific schedule recovery strategies
   - Resource adjustments
   - Resequencing opportunities
   - Overtime or acceleration options with cost implications

5. OUTPUT FORMAT:
   Return JSON:
   {{
     "overall_assessment": "summary paragraph",
     "snapshot_date": "{date.today().isoformat()}",
     "planned_completion_date": "",
     "projected_completion_date": "",
     "variance_days": 0,
     "percent_complete_planned": 0.0,
     "percent_complete_actual": 0.0,
     "critical_path_items": [
       {{"activity": "", "planned_finish": "", "projected_finish": "", "variance_days": 0, "status": "on_track|at_risk|behind|critical"}}
     ],
     "at_risk_items": [
       {{"activity": "", "risk": "", "impact_days": 0, "mitigation": ""}}
     ],
     "delay_drivers": [
       {{"activity": "", "cause": "", "days_impact": 0, "responsible_party": ""}}
     ],
     "recovery_actions": [
       {{"action": "", "potential_recovery_days": 0, "estimated_cost_cents": 0, "feasibility": "high|medium|low"}}
     ],
     "upcoming_milestones": [
       {{"milestone": "", "planned_date": "", "projected_date": "", "status": "on_track|at_risk|behind"}}
     ],
     "recommendations": ["rec1", "rec2"]
   }}"""

        user_content = f"SCHEDULE DATA:\n{parsed.text[:50000]}"
        if pm_notes:
            user_content += pm_notes

        return [
            {"role": "user", "content": user_content},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format schedule analysis as DOCX + XLSX."""
        data = parse_claude_json(response)

        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=context.project.get("name", "") if context else "",
            client_name=context.project.get("client_name", "") if context else "",
        )

        # DOCX report
        docx_path = self._create_docx(data, project_info, validated)

        # XLSX detail
        self._create_xlsx(data, project_info)

        # Persist snapshot
        self._persist_snapshot(validated, data, docx_path)

        return docx_path

    def _create_docx(
        self, data: dict, project_info: ProjectInfo, validated: dict
    ) -> Path:
        """Create DOCX schedule variance report."""
        variance = data.get("variance_days", 0)
        status_label = "BEHIND" if variance > 0 else "AHEAD" if variance < 0 else "ON TIME"

        sections = [
            Section("Overall Assessment", data.get("overall_assessment", "")),
            Section(
                "Schedule Status",
                f"Variance: {abs(variance)} days {status_label}\n"
                f"Planned Completion: {data.get('planned_completion_date', 'N/A')}\n"
                f"Projected Completion: {data.get('projected_completion_date', 'N/A')}",
            ),
        ]

        # Delay drivers
        drivers = data.get("delay_drivers", [])
        if drivers:
            lines = []
            for d in drivers:
                lines.append(
                    f"- {d.get('activity', '?')}: {d.get('cause', '')} "
                    f"({d.get('days_impact', 0)} days, {d.get('responsible_party', 'N/A')})"
                )
            sections.append(Section("Delay Drivers", "\n".join(lines)))

        # Recovery actions
        actions = data.get("recovery_actions", [])
        if actions:
            lines = []
            for a in actions:
                cost = a.get("estimated_cost_cents", 0)
                cost_str = f" (est. ${cost / 100:,.2f})" if cost else ""
                lines.append(
                    f"- {a.get('action', '?')}: "
                    f"Potential recovery: {a.get('potential_recovery_days', 0)} days{cost_str} "
                    f"[Feasibility: {a.get('feasibility', 'N/A')}]"
                )
            sections.append(Section("Recovery Actions", "\n".join(lines)))

        # Recommendations
        recs = data.get("recommendations", [])
        if recs:
            sections.append(
                Section("Recommendations", "\n".join(f"- {r}" for r in recs))
            )

        # Critical path table
        tables = []
        cp_items = data.get("critical_path_items", [])
        if cp_items:
            rows = []
            for item in cp_items:
                rows.append([
                    str(item.get("activity", "")),
                    str(item.get("planned_finish", "")),
                    str(item.get("projected_finish", "")),
                    str(item.get("variance_days", 0)),
                    str(item.get("status", "")).replace("_", " ").title(),
                ])
            tables.append(
                TableData(
                    headers=["Activity", "Planned Finish", "Projected Finish", "Variance (Days)", "Status"],
                    rows=rows,
                    title="Critical Path Activities",
                )
            )

        # Milestone table
        milestones = data.get("upcoming_milestones", [])
        if milestones:
            m_rows = []
            for m in milestones:
                m_rows.append([
                    str(m.get("milestone", "")),
                    str(m.get("planned_date", "")),
                    str(m.get("projected_date", "")),
                    str(m.get("status", "")).replace("_", " ").title(),
                ])
            tables.append(
                TableData(
                    headers=["Milestone", "Planned Date", "Projected Date", "Status"],
                    rows=m_rows,
                    title="Upcoming Milestones",
                )
            )

        content = DocumentContent(
            title="Schedule Variance Report",
            date=date.today().isoformat(),
            header_fields={
                "File": Path(validated["file_path"]).name,
                "Analysis Date": date.today().isoformat(),
                "Variance": f"{abs(variance)} days {status_label}",
            },
            sections=sections,
            tables=tables,
        )

        return self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

    def _create_xlsx(self, data: dict, project_info: ProjectInfo) -> Path:
        """Create XLSX schedule detail workbook."""
        # Critical path sheet
        cp_rows = []
        for item in data.get("critical_path_items", []):
            cp_rows.append([
                str(item.get("activity", "")),
                str(item.get("planned_finish", "")),
                str(item.get("projected_finish", "")),
                str(item.get("variance_days", 0)),
                str(item.get("status", "")),
            ])

        # At-risk items sheet
        risk_rows = []
        for item in data.get("at_risk_items", []):
            risk_rows.append([
                str(item.get("activity", "")),
                str(item.get("risk", "")),
                str(item.get("impact_days", 0)),
                str(item.get("mitigation", "")),
            ])

        # Recovery actions sheet
        action_rows = []
        for a in data.get("recovery_actions", []):
            cost = a.get("estimated_cost_cents", 0)
            action_rows.append([
                str(a.get("action", "")),
                str(a.get("potential_recovery_days", 0)),
                f"${cost / 100:,.2f}" if cost else "N/A",
                str(a.get("feasibility", "")),
            ])

        sheets = {
            "Critical Path": TableData(
                headers=["Activity", "Planned Finish", "Projected Finish", "Variance (Days)", "Status"],
                rows=cp_rows,
            ),
            "At-Risk Items": TableData(
                headers=["Activity", "Risk", "Impact (Days)", "Mitigation"],
                rows=risk_rows,
            ),
            "Recovery Actions": TableData(
                headers=["Action", "Recovery (Days)", "Est. Cost", "Feasibility"],
                rows=action_rows,
            ),
        }

        spreadsheet = SpreadsheetContent(title="Schedule Analysis", sheets=sheets)
        return self.formatter.create_xlsx(
            spreadsheet, project_info, skill_name=self.skill_name
        )

    def _persist_snapshot(
        self, validated: dict, data: dict, docx_path: Path
    ) -> None:
        """Persist schedule snapshot to database."""
        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO schedule_snapshots "
                "(project_id, snapshot_date, source_file_path, "
                "planned_completion_date, projected_completion_date, "
                "variance_days, critical_path_items, at_risk_items, "
                "analysis, recommendations, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated["project_id"],
                    date.today().isoformat(),
                    validated["file_path"],
                    data.get("planned_completion_date"),
                    data.get("projected_completion_date"),
                    data.get("variance_days", 0),
                    json.dumps(data.get("critical_path_items", [])),
                    json.dumps(data.get("at_risk_items", [])),
                    data.get("overall_assessment", ""),
                    json.dumps(data.get("recommendations", [])),
                    str(docx_path),
                ),
            )
