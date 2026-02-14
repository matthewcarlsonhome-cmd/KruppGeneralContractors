"""Budget Forecaster — Skill #14.

Parses a job cost report (XLSX), analyzes budget vs. actual spending by
cost code, projects final costs, identifies cost risks and opportunities,
and generates a DOCX executive summary with an XLSX workbook containing
three sheets: Budget vs Actual, Projections, and Risk Register.
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


class BudgetForecasterSkill(BaseSkill):
    """Forecast project budget health from a job cost report."""

    skill_name = "budget_forecaster"
    display_name = "Budget Forecaster"
    description = "Analyze a job cost report and forecast budget health"
    phase = 3
    default_model = "sonnet"
    output_formats = ["docx", "xlsx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate budget forecaster input.

        Required: project (code), file (path to XLSX).
        Optional: notes.
        """
        project_code = kwargs.get("project")
        file_path = kwargs.get("file")
        notes = kwargs.get("notes")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not file_path:
            raise ValueError(
                "Job cost report file is required. Use --file or -f."
            )

        path = Path(str(file_path))
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        if path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            raise ValueError(
                "Job cost report must be in XLSX, XLS, or CSV format."
            )

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "file_path": str(path),
            "notes": str(notes).strip() if notes else None,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for budget forecasting."""
        company = context.company if context else {}
        project = context.project if context else {}

        # Parse the job cost report
        parsed = parse_file(Path(validated["file_path"]))
        if parsed.error:
            raise ValueError(
                f"Could not parse job cost report: {parsed.error}"
            )

        # Build project financial context
        project_context = ""
        if context:
            original = project.get("original_contract_cents", 0) or 0
            current = project.get("current_contract_cents", 0) or 0
            estimated = project.get("estimated_cost_cents", 0) or 0
            pct_complete = project.get("current_percent_complete", 0) or 0

            project_context = (
                f"Project: {project.get('name', 'N/A')} "
                f"({project.get('project_code', 'N/A')})\n"
                f"Type: {project.get('project_type', 'N/A')}\n"
                f"Original Contract: ${original / 100:,.2f}\n"
                f"Current Contract (with COs): ${current / 100:,.2f}\n"
                f"Estimated Cost: ${estimated / 100:,.2f}\n"
                f"Percent Complete: {pct_complete:.0f}%\n"
                f"Delivery Method: {project.get('delivery_method', 'N/A')}\n"
                f"Contract Type: {project.get('contract_type', 'N/A')}\n"
            )

        # Load previous forecasts for trend analysis
        forecast_history = self._load_forecast_history(validated)

        # Load approved change orders
        co_context = self._load_change_orders(validated)

        notes_section = ""
        if validated.get("notes"):
            notes_section = f"\nPM OBSERVATIONS:\n{validated['notes']}\n"

        system_prompt = f"""You are a senior project accountant and cost engineer for {company.get('name', 'Krupp General Contractors')}.
You are analyzing a job cost report to forecast project budget health.

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

{co_context}

{forecast_history}
{notes_section}

INSTRUCTIONS:
1. PARSE the job cost report and identify each cost code / line item.

2. ANALYZE each cost code:
   - Budget amount (original + approved changes)
   - Committed costs (subcontracts, POs)
   - Actual costs to date
   - Projected final cost (actual + estimated to complete)
   - Variance (budget - projected)

3. DETERMINE overall project health:
   - health_status: "on_track" | "at_risk" | "over_budget" | "critical"
   - Provide a clear executive summary

4. IDENTIFY RISKS:
   - Cost codes trending over budget
   - Uncommitted budget items
   - Areas where contingency may be needed

5. OUTPUT FORMAT:
   Return JSON:
   {{
     "health_status": "on_track|at_risk|over_budget|critical",
     "executive_summary": "2-3 paragraph executive summary",
     "original_budget_cents": 0,
     "approved_changes_cents": 0,
     "current_budget_cents": 0,
     "committed_costs_cents": 0,
     "actual_costs_cents": 0,
     "projected_final_cents": 0,
     "variance_cents": 0,
     "contingency_remaining_cents": 0,
     "contingency_recommended_cents": 0,
     "budget_lines": [
       {{
         "cost_code": "XX.XXX",
         "description": "Line item description",
         "budget_cents": 0,
         "committed_cents": 0,
         "actual_cents": 0,
         "projected_cents": 0,
         "variance_cents": 0,
         "percent_complete": 0.0,
         "status": "on_track|at_risk|over_budget",
         "notes": "analysis note"
       }}
     ],
     "risk_items": [
       {{
         "cost_code": "XX.XXX",
         "description": "Risk description",
         "risk_level": "low|medium|high|critical",
         "potential_impact_cents": 0,
         "mitigation": "Recommended action"
       }}
     ],
     "recommendations": ["rec1", "rec2"]
   }}

CRITICAL: All monetary values must be in cents (integer)."""

        return [
            {
                "role": "user",
                "content": f"JOB COST REPORT:\n{parsed.text[:40000]}",
            },
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format budget forecast as DOCX executive summary + XLSX workbook."""
        data = parse_claude_json(response)

        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=context.project.get("name", "") if context else "",
            client_name=context.project.get("client_name", "") if context else "",
        )

        # DOCX executive summary
        docx_path = self._create_docx(data, project_info, validated)

        # XLSX workbook with 3 sheets
        xlsx_path = self._create_xlsx(data, project_info)

        # Persist to database
        self._persist_forecast(validated, data, docx_path, xlsx_path)

        return docx_path

    def _create_docx(
        self, data: dict, project_info: ProjectInfo, validated: dict
    ) -> Path:
        """Create the DOCX budget forecast report."""
        health = data.get("health_status", "unknown").replace("_", " ").upper()

        sections: list[Section] = []

        # Executive summary
        sections.append(
            Section(
                "Executive Summary",
                data.get("executive_summary", "No summary available."),
            )
        )

        # Financial overview
        original = data.get("original_budget_cents", 0)
        changes = data.get("approved_changes_cents", 0)
        current = data.get("current_budget_cents", 0)
        committed = data.get("committed_costs_cents", 0)
        actual = data.get("actual_costs_cents", 0)
        projected = data.get("projected_final_cents", 0)
        variance = data.get("variance_cents", 0)
        cont_remaining = data.get("contingency_remaining_cents", 0)
        cont_recommended = data.get("contingency_recommended_cents", 0)

        overview_text = (
            f"Original Budget: ${original / 100:,.2f}\n"
            f"Approved Changes: ${changes / 100:,.2f}\n"
            f"Current Budget: ${current / 100:,.2f}\n"
            f"Committed Costs: ${committed / 100:,.2f}\n"
            f"Actual Costs to Date: ${actual / 100:,.2f}\n"
            f"Projected Final Cost: ${projected / 100:,.2f}\n"
            f"Variance: ${variance / 100:,.2f}\n"
            f"Contingency Remaining: ${cont_remaining / 100:,.2f}\n"
            f"Contingency Recommended: ${cont_recommended / 100:,.2f}"
        )
        sections.append(Section("Financial Overview", overview_text))

        # Risk items
        risks = data.get("risk_items", [])
        if risks:
            lines = []
            for risk in risks:
                impact = risk.get("potential_impact_cents", 0)
                lines.append(
                    f"[{risk.get('risk_level', '?').upper()}] "
                    f"{risk.get('cost_code', 'N/A')} - "
                    f"{risk.get('description', '')}\n"
                    f"  Potential Impact: ${impact / 100:,.2f}\n"
                    f"  Mitigation: {risk.get('mitigation', 'N/A')}"
                )
            sections.append(Section("Risk Register", "\n\n".join(lines)))

        # Recommendations
        recs = data.get("recommendations", [])
        if recs:
            sections.append(
                Section("Recommendations", "\n".join(f"- {r}" for r in recs))
            )

        # Budget summary table
        tables: list[TableData] = []
        budget_lines = data.get("budget_lines", [])
        if budget_lines:
            rows = []
            for line in budget_lines:
                budget = line.get("budget_cents", 0)
                proj = line.get("projected_cents", 0)
                var = line.get("variance_cents", 0)
                rows.append([
                    str(line.get("cost_code", "")),
                    str(line.get("description", "")),
                    f"${budget / 100:,.2f}" if budget else "N/A",
                    f"${proj / 100:,.2f}" if proj else "N/A",
                    f"${var / 100:,.2f}" if var else "$0.00",
                    str(line.get("status", "")).replace("_", " ").upper(),
                ])
            tables.append(
                TableData(
                    headers=[
                        "Code",
                        "Description",
                        "Budget",
                        "Projected",
                        "Variance",
                        "Status",
                    ],
                    rows=rows,
                    title="Budget vs. Projected Summary",
                )
            )

        content = DocumentContent(
            title="Budget Forecast Report",
            date=date.today().isoformat(),
            header_fields={
                "Project": f"{project_info.name} ({project_info.project_code})",
                "Health Status": health,
                "Source File": Path(validated["file_path"]).name,
                "Forecast Date": date.today().isoformat(),
            },
            sections=sections,
            tables=tables,
        )

        return self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

    def _create_xlsx(self, data: dict, project_info: ProjectInfo) -> Path:
        """Create XLSX workbook with 3 sheets."""
        # Sheet 1: Budget vs Actual
        budget_rows = []
        for line in data.get("budget_lines", []):
            budget = line.get("budget_cents", 0)
            committed = line.get("committed_cents", 0)
            actual = line.get("actual_cents", 0)
            projected = line.get("projected_cents", 0)
            variance = line.get("variance_cents", 0)
            pct = line.get("percent_complete", 0)
            budget_rows.append([
                str(line.get("cost_code", "")),
                str(line.get("description", "")),
                f"${budget / 100:,.2f}" if budget else "$0.00",
                f"${committed / 100:,.2f}" if committed else "$0.00",
                f"${actual / 100:,.2f}" if actual else "$0.00",
                f"${projected / 100:,.2f}" if projected else "$0.00",
                f"${variance / 100:,.2f}" if variance else "$0.00",
                f"{pct:.0f}%",
                str(line.get("status", "")),
            ])

        # Sheet 2: Projections (summary-level)
        projection_rows = [
            [
                "Original Budget",
                f"${data.get('original_budget_cents', 0) / 100:,.2f}",
            ],
            [
                "Approved Changes",
                f"${data.get('approved_changes_cents', 0) / 100:,.2f}",
            ],
            [
                "Current Budget",
                f"${data.get('current_budget_cents', 0) / 100:,.2f}",
            ],
            [
                "Committed Costs",
                f"${data.get('committed_costs_cents', 0) / 100:,.2f}",
            ],
            [
                "Actual Costs to Date",
                f"${data.get('actual_costs_cents', 0) / 100:,.2f}",
            ],
            [
                "Projected Final",
                f"${data.get('projected_final_cents', 0) / 100:,.2f}",
            ],
            [
                "Variance",
                f"${data.get('variance_cents', 0) / 100:,.2f}",
            ],
            [
                "Contingency Remaining",
                f"${data.get('contingency_remaining_cents', 0) / 100:,.2f}",
            ],
            [
                "Contingency Recommended",
                f"${data.get('contingency_recommended_cents', 0) / 100:,.2f}",
            ],
        ]

        # Sheet 3: Risk Register
        risk_rows = []
        for risk in data.get("risk_items", []):
            impact = risk.get("potential_impact_cents", 0)
            risk_rows.append([
                str(risk.get("cost_code", "")),
                str(risk.get("description", "")),
                str(risk.get("risk_level", "")),
                f"${impact / 100:,.2f}" if impact else "N/A",
                str(risk.get("mitigation", "")),
            ])

        sheets = {
            "Budget vs Actual": TableData(
                headers=[
                    "Cost Code",
                    "Description",
                    "Budget",
                    "Committed",
                    "Actual",
                    "Projected",
                    "Variance",
                    "% Complete",
                    "Status",
                ],
                rows=budget_rows,
            ),
            "Projections": TableData(
                headers=["Category", "Amount"],
                rows=projection_rows,
            ),
            "Risk Register": TableData(
                headers=[
                    "Cost Code",
                    "Description",
                    "Risk Level",
                    "Potential Impact",
                    "Mitigation",
                ],
                rows=risk_rows,
            ),
        }

        spreadsheet = SpreadsheetContent(
            title="Budget Forecast", sheets=sheets
        )
        return self.formatter.create_xlsx(
            spreadsheet, project_info, skill_name=self.skill_name
        )

    def _persist_forecast(
        self,
        validated: dict,
        data: dict,
        docx_path: Path,
        xlsx_path: Path,
    ) -> None:
        """Persist budget forecast to the database."""
        budget_lines = data.get("budget_lines", [])

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO budget_forecasts "
                "(project_id, forecast_date, forecast_month, "
                "original_budget_cents, approved_changes_cents, "
                "current_budget_cents, committed_costs_cents, "
                "actual_costs_cents, projected_final_cents, "
                "variance_cents, cost_code_breakdown, risk_items, "
                "contingency_remaining_cents, contingency_recommended_cents, "
                "analysis, recommendations, document_path, excel_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated["project_id"],
                    date.today().isoformat(),
                    date.today().strftime("%Y-%m"),
                    data.get("original_budget_cents", 0),
                    data.get("approved_changes_cents", 0),
                    data.get("current_budget_cents", 0),
                    data.get("committed_costs_cents", 0),
                    data.get("actual_costs_cents", 0),
                    data.get("projected_final_cents", 0),
                    data.get("variance_cents", 0),
                    json.dumps(budget_lines),
                    json.dumps(data.get("risk_items", [])),
                    data.get("contingency_remaining_cents", 0),
                    data.get("contingency_recommended_cents", 0),
                    data.get("executive_summary", ""),
                    json.dumps(data.get("recommendations", [])),
                    str(docx_path),
                    str(xlsx_path),
                ),
            )

    def _load_forecast_history(self, validated: dict) -> str:
        """Load previous budget forecasts for trend context."""
        try:
            with get_db(self.settings) as conn:
                cursor = conn.execute(
                    "SELECT forecast_date, projected_final_cents, "
                    "variance_cents, analysis "
                    "FROM budget_forecasts "
                    "WHERE project_id = ? "
                    "ORDER BY forecast_date DESC LIMIT 3",
                    (validated["project_id"],),
                )
                rows = cursor.fetchall()

                if not rows:
                    return "No prior forecasts available."

                lines = ["PRIOR FORECASTS:"]
                for row in rows:
                    proj = row["projected_final_cents"] or 0
                    var = row["variance_cents"] or 0
                    lines.append(
                        f"  {row['forecast_date']}: "
                        f"Projected ${proj / 100:,.2f}, "
                        f"Variance ${var / 100:,.2f}"
                    )
                return "\n".join(lines)
        except Exception:
            return "No prior forecasts available."

    def _load_change_orders(self, validated: dict) -> str:
        """Load approved change orders for context."""
        try:
            with get_db(self.settings) as conn:
                cursor = conn.execute(
                    "SELECT co_number, title, total_with_markup_cents, status "
                    "FROM change_orders "
                    "WHERE project_id = ? "
                    "ORDER BY co_number",
                    (validated["project_id"],),
                )
                rows = cursor.fetchall()

                if not rows:
                    return "CHANGE ORDERS: None recorded."

                lines = ["CHANGE ORDERS:"]
                for row in rows:
                    amount = row["total_with_markup_cents"] or 0
                    lines.append(
                        f"  CO #{row['co_number']}: {row['title']} "
                        f"(${amount / 100:,.2f}) — {row['status']}"
                    )
                return "\n".join(lines)
        except Exception:
            return "CHANGE ORDERS: Unable to load."
