"""Estimate Reviewer — Skill #7.

Parses a contractor's cost estimate (XLSX/CSV), benchmarks each CSI
division against industry data for the given project type and region,
flags outliers, identifies missing scopes, and provides a confidence-scored
overall assessment.  Uses the Opus model for financial precision.
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

VALID_EXTENSIONS = {".xlsx", ".xls", ".csv"}


class EstimateReviewerSkill(BaseSkill):
    """Review a cost estimate against industry benchmarks and flag anomalies."""

    skill_name = "estimate_reviewer"
    display_name = "Estimate Reviewer"
    description = "Review a cost estimate against benchmarks and flag anomalies"
    phase = 2
    default_model = "opus"
    output_formats = ["docx", "xlsx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate estimate review input.

        Required: file (path to XLSX/XLS/CSV).
        Optional: project (code), type (project type), sqft, region.
        """
        file_path = kwargs.get("file")
        project_code = kwargs.get("project")
        project_type = kwargs.get("type", "commercial")
        sqft = kwargs.get("sqft")
        region = kwargs.get("region", "National Average")

        if not file_path:
            raise ValueError("Estimate file is required")

        path = Path(str(file_path))
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        if path.suffix.lower() not in VALID_EXTENSIONS:
            raise ValueError(
                f"Estimate file must be .xlsx, .xls, or .csv format. "
                f"Got: {path.suffix}"
            )

        project_id = None
        project_code_str: str | None = None
        if project_code:
            context = self.context_manager.load_by_code(str(project_code))
            project_id = context.project["id"]
            project_code_str = str(project_code)

        return {
            "project_id": project_id,
            "project_code": project_code_str,
            "file_path": str(path),
            "project_type": str(project_type) if project_type else "commercial",
            "sqft": int(sqft) if sqft else None,
            "region": str(region) if region else "National Average",
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for estimate review."""
        company = context.company if context else {}
        project = context.project if context else {}

        # Parse the estimate file
        parsed = parse_file(Path(validated["file_path"]))
        if parsed.error:
            raise ValueError(f"Could not parse estimate file: {parsed.error}")

        project_context = ""
        if context:
            contract_display = "N/A"
            if project.get("current_contract_cents"):
                contract_display = f"${project['current_contract_cents'] / 100:,.2f}"
            project_context = (
                f"Project: {project.get('name', 'N/A')} "
                f"({project.get('project_code', 'N/A')})\n"
                f"Type: {project.get('project_type', 'N/A')}\n"
                f"Contract Value: {contract_display}\n"
                f"Square Footage: {project.get('square_footage', 'N/A')}\n"
            )

        sqft_context = ""
        if validated.get("sqft"):
            sqft_context = f"\nBuilding Square Footage: {validated['sqft']:,} SF"

        # Load historical cost data for benchmarking
        historical_context = self._load_historical_costs(validated)

        system_prompt = f"""You are a senior preconstruction estimator for {company.get('name', 'Krupp General Contractors')}.
You are reviewing a cost estimate to benchmark against industry norms and identify anomalies.

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

Project Type: {validated['project_type']}
Region: {validated['region']}{sqft_context}

{historical_context}

INSTRUCTIONS:
1. PARSE the estimate data and identify each CSI division or cost category.

2. BENCHMARK each line item against typical costs for this project type and region:
   - Calculate per-SF costs where square footage is available
   - Flag items significantly above or below industry norms
   - Identify missing CSI divisions that would typically be included

3. ASSESS overall estimate quality:
   - Overall variance from benchmark
   - Confidence level (high, medium, low)
   - Recommended contingency percentage

4. FLAG HIGH-RISK ITEMS:
   - Items with >15% variance from benchmark
   - Unusually low items (may indicate scope gaps)
   - Unusually high items (may indicate padding or misunderstanding)

5. OUTPUT FORMAT:
   Return JSON:
   {{
     "overall_assessment": "Executive summary paragraph",
     "confidence_level": "high|medium|low",
     "total_estimate_cents": 0,
     "benchmark_total_cents": 0,
     "variance_percent": 0.0,
     "recommended_contingency_percent": 0.0,
     "missing_divisions": [
       {{"csi_code": "XX", "description": "Division name", "typical_range": "$X-$Y"}}
     ],
     "flagged_items": [
       {{
         "csi_code": "XX",
         "description": "Item description",
         "estimated_cents": 0,
         "benchmark_cents": 0,
         "variance_percent": 0.0,
         "flag": "HIGH|LOW|MISSING",
         "risk": "low|medium|high",
         "explanation": "Why this is flagged"
       }}
     ],
     "category_analysis": [
       {{
         "division": "XX - Division Name",
         "estimated_cents": 0,
         "per_sf_cents": 0,
         "benchmark_per_sf_cents": 0,
         "notes": "Analysis note"
       }}
     ],
     "recommendations": ["rec1", "rec2"]
   }}

CRITICAL: All monetary values must be in cents (integer). For example, $1,250,000 = 125000000 cents."""

        return [
            {
                "role": "user",
                "content": (
                    f"ESTIMATE DATA:\n{parsed.text[:40000]}"
                ),
            },
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format estimate review as DOCX + XLSX."""
        data = parse_claude_json(response)

        project_info = ProjectInfo(
            project_code=validated.get("project_code") or "REVIEW",
            name=context.project.get("name", "") if context else "",
            client_name=context.project.get("client_name", "") if context else "",
        )

        # DOCX report
        docx_path = self._create_docx(data, project_info, validated)

        # XLSX analysis workbook
        xlsx_path = self._create_xlsx(data, project_info)

        # Persist to database
        self._persist_review(validated, data, docx_path)

        return docx_path

    def _create_docx(
        self, data: dict, project_info: ProjectInfo, validated: dict
    ) -> Path:
        """Create the DOCX estimate review report."""
        sections: list[Section] = []

        # Overall assessment
        sections.append(
            Section(
                "Overall Assessment",
                data.get("overall_assessment", "No assessment available."),
            )
        )

        # Summary metrics
        total_est = data.get("total_estimate_cents", 0)
        total_bench = data.get("benchmark_total_cents", 0)
        variance = data.get("variance_percent", 0)
        confidence = data.get("confidence_level", "N/A")
        contingency = data.get("recommended_contingency_percent", 0)

        summary_text = (
            f"Total Estimate: ${total_est / 100:,.2f}\n"
            f"Benchmark Total: ${total_bench / 100:,.2f}\n"
            f"Overall Variance: {variance:+.1f}%\n"
            f"Confidence Level: {confidence.upper()}\n"
            f"Recommended Contingency: {contingency:.1f}%"
        )
        sections.append(Section("Summary Metrics", summary_text))

        # Flagged items
        flagged = data.get("flagged_items", [])
        if flagged:
            lines = []
            for item in flagged:
                est = item.get("estimated_cents", 0)
                bench = item.get("benchmark_cents", 0)
                var_pct = item.get("variance_percent", 0)
                lines.append(
                    f"[{item.get('flag', '?')}] {item.get('csi_code', '??')} "
                    f"- {item.get('description', '')}\n"
                    f"  Estimated: ${est / 100:,.2f} | "
                    f"Benchmark: ${bench / 100:,.2f} | "
                    f"Variance: {var_pct:+.1f}%\n"
                    f"  Risk: {item.get('risk', 'N/A').upper()} | "
                    f"{item.get('explanation', '')}"
                )
            sections.append(Section("Flagged Items", "\n\n".join(lines)))

        # Missing divisions
        missing = data.get("missing_divisions", [])
        if missing:
            lines = []
            for div in missing:
                lines.append(
                    f"- Division {div.get('csi_code', '??')}: "
                    f"{div.get('description', '')} "
                    f"(typical range: {div.get('typical_range', 'N/A')})"
                )
            sections.append(Section("Missing Divisions", "\n".join(lines)))

        # Recommendations
        recs = data.get("recommendations", [])
        if recs:
            sections.append(
                Section("Recommendations", "\n".join(f"- {r}" for r in recs))
            )

        # Category analysis table
        tables: list[TableData] = []
        categories = data.get("category_analysis", [])
        if categories:
            rows = []
            for cat in categories:
                est = cat.get("estimated_cents", 0)
                per_sf = cat.get("per_sf_cents", 0)
                bench_sf = cat.get("benchmark_per_sf_cents", 0)
                rows.append([
                    str(cat.get("division", "")),
                    f"${est / 100:,.2f}" if est else "N/A",
                    f"${per_sf / 100:.2f}/SF" if per_sf else "N/A",
                    f"${bench_sf / 100:.2f}/SF" if bench_sf else "N/A",
                    str(cat.get("notes", "")),
                ])
            tables.append(
                TableData(
                    headers=[
                        "Division",
                        "Estimated",
                        "$/SF",
                        "Benchmark $/SF",
                        "Notes",
                    ],
                    rows=rows,
                    title="Category Analysis",
                )
            )

        # Flagged items table
        if flagged:
            flag_rows = []
            for item in flagged:
                est = item.get("estimated_cents", 0)
                bench = item.get("benchmark_cents", 0)
                flag_rows.append([
                    str(item.get("flag", "")),
                    f"{item.get('csi_code', '')} - {item.get('description', '')}",
                    f"${est / 100:,.2f}" if est else "N/A",
                    f"${bench / 100:,.2f}" if bench else "N/A",
                    f"{item.get('variance_percent', 0):+.1f}%",
                    str(item.get("risk", "")).upper(),
                ])
            tables.append(
                TableData(
                    headers=[
                        "Flag",
                        "Item",
                        "Estimated",
                        "Benchmark",
                        "Variance",
                        "Risk",
                    ],
                    rows=flag_rows,
                    title="Flagged Items Summary",
                )
            )

        content = DocumentContent(
            title="Estimate Review Report",
            date=date.today().isoformat(),
            header_fields={
                "Project Type": validated["project_type"].title(),
                "Region": validated["region"],
                "Square Footage": (
                    f"{validated['sqft']:,} SF" if validated.get("sqft") else "N/A"
                ),
                "Source File": Path(validated["file_path"]).name,
                "Confidence": data.get("confidence_level", "N/A").upper(),
                "Date": date.today().isoformat(),
            },
            sections=sections,
            tables=tables,
        )

        return self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

    def _create_xlsx(self, data: dict, project_info: ProjectInfo) -> Path:
        """Create XLSX analysis workbook."""
        # Category analysis sheet
        cat_rows = []
        for cat in data.get("category_analysis", []):
            est = cat.get("estimated_cents", 0)
            per_sf = cat.get("per_sf_cents", 0)
            bench_sf = cat.get("benchmark_per_sf_cents", 0)
            cat_rows.append([
                str(cat.get("division", "")),
                f"${est / 100:,.2f}" if est else "N/A",
                f"${per_sf / 100:.2f}" if per_sf else "N/A",
                f"${bench_sf / 100:.2f}" if bench_sf else "N/A",
                str(cat.get("notes", "")),
            ])

        # Flagged items sheet
        flag_rows = []
        for item in data.get("flagged_items", []):
            est = item.get("estimated_cents", 0)
            bench = item.get("benchmark_cents", 0)
            flag_rows.append([
                str(item.get("flag", "")),
                str(item.get("csi_code", "")),
                str(item.get("description", "")),
                f"${est / 100:,.2f}" if est else "N/A",
                f"${bench / 100:,.2f}" if bench else "N/A",
                f"{item.get('variance_percent', 0):+.1f}%",
                str(item.get("risk", "")),
                str(item.get("explanation", "")),
            ])

        # Missing divisions sheet
        missing_rows = []
        for div in data.get("missing_divisions", []):
            missing_rows.append([
                str(div.get("csi_code", "")),
                str(div.get("description", "")),
                str(div.get("typical_range", "")),
            ])

        sheets = {
            "Category Analysis": TableData(
                headers=[
                    "Division",
                    "Estimated",
                    "Per SF",
                    "Benchmark Per SF",
                    "Notes",
                ],
                rows=cat_rows,
            ),
            "Flagged Items": TableData(
                headers=[
                    "Flag",
                    "CSI Code",
                    "Description",
                    "Estimated",
                    "Benchmark",
                    "Variance %",
                    "Risk",
                    "Explanation",
                ],
                rows=flag_rows,
            ),
            "Missing Divisions": TableData(
                headers=["CSI Code", "Description", "Typical Range"],
                rows=missing_rows,
            ),
        }

        spreadsheet = SpreadsheetContent(
            title="Estimate Review Analysis", sheets=sheets
        )
        return self.formatter.create_xlsx(
            spreadsheet, project_info, skill_name=self.skill_name
        )

    def _persist_review(
        self, validated: dict, data: dict, docx_path: Path
    ) -> None:
        """Persist estimate review results to the database."""
        flagged_items = data.get("flagged_items", [])
        recommendations = data.get("recommendations", [])

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO estimate_reviews "
                "(project_id, estimate_name, source_file_path, "
                "total_estimate_cents, total_benchmark_cents, "
                "variance_percent, findings, high_risk_items, "
                "recommendations, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated.get("project_id"),
                    Path(validated["file_path"]).stem,
                    validated["file_path"],
                    data.get("total_estimate_cents", 0),
                    data.get("benchmark_total_cents", 0),
                    data.get("variance_percent", 0),
                    json.dumps(data.get("category_analysis", [])),
                    json.dumps(flagged_items),
                    json.dumps(recommendations),
                    str(docx_path),
                ),
            )

    def _load_historical_costs(self, validated: dict) -> str:
        """Load historical cost data from the database for benchmarking context."""
        project_id = validated.get("project_id")
        if not project_id:
            return "No historical cost data available."

        try:
            with get_db(self.settings) as conn:
                cursor = conn.execute(
                    "SELECT csi_code, csi_description, "
                    "AVG(unit_cost_cents) as avg_cost, "
                    "COUNT(*) as sample_count "
                    "FROM cost_history "
                    "GROUP BY csi_code "
                    "ORDER BY csi_code"
                )
                rows = cursor.fetchall()

                if not rows:
                    return "No historical cost data available."

                lines = ["HISTORICAL COST BENCHMARKS:"]
                for row in rows:
                    avg = row["avg_cost"]
                    lines.append(
                        f"  Division {row['csi_code']} "
                        f"({row['csi_description'] or 'N/A'}): "
                        f"avg ${avg / 100:,.2f}/unit "
                        f"({row['sample_count']} samples)"
                    )
                return "\n".join(lines)
        except Exception:
            return "No historical cost data available."
