"""Bid Comparison Analyzer — Skill #8.

Parses 2–8 bid PDFs or spreadsheets for a given trade, then produces a
side-by-side comparison matrix. Flags scope gaps, exclusions, qualifications,
and recommends the best-value bidder.
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


class BidComparisonSkill(BaseSkill):
    """Compare multiple bids for a given trade and recommend best value."""

    skill_name = "bid_comparison"
    display_name = "Bid Comparison"
    description = "Compare multiple bids side-by-side and recommend best value"
    phase = 2
    default_model = "sonnet"
    output_formats = ["docx", "xlsx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate bid comparison input.

        Required: project (code), trade, bids (list of file paths).
        """
        project_code = kwargs.get("project")
        trade = kwargs.get("trade")
        bids = kwargs.get("bids")  # comma-separated paths or list

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not trade:
            raise ValueError(
                "Trade is required (e.g., 'electrical'). Use --trade or -t."
            )

        # Parse bid file paths
        if isinstance(bids, str):
            bid_paths = [Path(p.strip()) for p in bids.split(",") if p.strip()]
        elif isinstance(bids, (list, tuple)):
            bid_paths = [Path(str(p)) for p in bids]
        else:
            raise ValueError(
                "Bid files are required. Provide comma-separated file paths."
            )

        if len(bid_paths) < 2:
            raise ValueError("At least 2 bid files are required for comparison.")
        if len(bid_paths) > 8:
            raise ValueError("Maximum 8 bid files supported.")

        for path in bid_paths:
            if not path.exists():
                raise ValueError(f"Bid file not found: {path}")
            if path.suffix.lower() not in {".pdf", ".xlsx", ".xls", ".csv", ".docx"}:
                raise ValueError(
                    f"Unsupported file format: {path.suffix}. "
                    "Use PDF, XLSX, XLS, CSV, or DOCX."
                )

        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "trade": str(trade).strip(),
            "bid_paths": [str(p) for p in bid_paths],
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for bid comparison."""
        company = context.company if context else {}
        project = context.project if context else {}

        # Parse all bid documents
        bid_texts = []
        for i, bid_path in enumerate(validated["bid_paths"], start=1):
            parsed = parse_file(Path(bid_path))
            if parsed.error:
                bid_texts.append(f"\n--- BID #{i}: {Path(bid_path).name} ---\n[Parse error: {parsed.error}]")
            else:
                bid_texts.append(f"\n--- BID #{i}: {Path(bid_path).name} ---\n{parsed.text[:20000]}")

        all_bids_text = "\n".join(bid_texts)

        project_context = ""
        if context:
            project_context = (
                f"Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})\n"
                f"Type: {project.get('project_type', 'N/A')}\n"
                f"Contract Value: ${project.get('current_contract_cents', 0) / 100:,.2f}\n"
            )

        system_prompt = f"""You are a senior preconstruction manager for {company.get('name', 'Krupp General Contractors')}.
You are analyzing competitive bids for the {validated['trade']} trade package.

PROJECT CONTEXT:
{project_context or 'No project context provided.'}

INSTRUCTIONS:
1. EXTRACT from each bid:
   - Company name
   - Base bid amount (in cents for JSON, display as dollars in explanations)
   - Alternates (add/deduct items with amounts)
   - Qualifications (conditions or assumptions)
   - Exclusions (items NOT included in their bid)
   - Notable terms (payment terms, schedule constraints, bond included, etc.)

2. COMPARE all bids:
   - Side-by-side base bid comparison
   - Identify scope gaps: items excluded by some bidders but included by others
   - Flag any qualifications that change the effective bid amount
   - Calculate adjusted bid (base bid + estimated cost of excluded items)

3. RECOMMEND:
   - Best value bidder (not necessarily lowest) with clear reasoning
   - Items to clarify with each bidder before award
   - Risk factors for each bidder

4. OUTPUT FORMAT:
   Return JSON:
   {{
     "bidders": [
       {{
         "company": "Company Name",
         "base_bid_cents": 0,
         "alternates": [{{"description": "", "amount_cents": 0}}],
         "qualifications": ["qual1", "qual2"],
         "exclusions": ["excl1", "excl2"],
         "notable_terms": ["term1"],
         "adjusted_bid_cents": 0,
         "strengths": ["str1"],
         "concerns": ["con1"]
       }}
     ],
     "scope_gaps": [
       {{"item": "", "included_by": ["Company A"], "excluded_by": ["Company B"], "estimated_cost_cents": 0}}
     ],
     "recommendation": {{
       "recommended_bidder": "Company Name",
       "reasoning": "explanation",
       "clarifications_needed": ["item1", "item2"]
     }},
     "spread_analysis": {{
       "low_bid_cents": 0,
       "high_bid_cents": 0,
       "spread_percent": 0.0,
       "average_bid_cents": 0,
       "notes": "analysis"
     }},
     "overall_assessment": "summary paragraph"
   }}"""

        return [
            {"role": "user", "content": f"BID DOCUMENTS FOR {validated['trade'].upper()} TRADE:\n{all_bids_text}"},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format bid comparison as DOCX + XLSX."""
        data = parse_claude_json(response)

        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=context.project.get("name", "") if context else "",
            client_name=context.project.get("client_name", "") if context else "",
        )

        # DOCX report
        docx_path = self._create_docx(data, project_info, validated)

        # XLSX matrix
        xlsx_path = self._create_xlsx(data, project_info)

        # Persist
        self._persist_comparison(validated, data, docx_path, xlsx_path)

        return docx_path

    def _create_docx(
        self, data: dict, project_info: ProjectInfo, validated: dict
    ) -> Path:
        """Create DOCX bid comparison report."""
        sections = [
            Section("Overall Assessment", data.get("overall_assessment", "")),
        ]

        # Recommendation
        rec = data.get("recommendation", {})
        if rec:
            sections.append(
                Section(
                    "Recommendation",
                    f"Recommended Bidder: {rec.get('recommended_bidder', 'N/A')}\n\n"
                    f"{rec.get('reasoning', '')}",
                )
            )
            clarifications = rec.get("clarifications_needed", [])
            if clarifications:
                sections.append(
                    Section(
                        "Clarifications Needed",
                        "\n".join(f"- {c}" for c in clarifications),
                    )
                )

        # Scope gaps
        gaps = data.get("scope_gaps", [])
        if gaps:
            lines = []
            for gap in gaps:
                est = gap.get("estimated_cost_cents", 0)
                est_str = f" (est. ${est / 100:,.2f})" if est else ""
                lines.append(
                    f"- {gap.get('item', '?')}: "
                    f"Included by {', '.join(gap.get('included_by', []))}; "
                    f"Excluded by {', '.join(gap.get('excluded_by', []))}"
                    f"{est_str}"
                )
            sections.append(Section("Scope Gaps", "\n".join(lines)))

        # Spread analysis
        spread = data.get("spread_analysis", {})
        if spread:
            low = spread.get("low_bid_cents", 0)
            high = spread.get("high_bid_cents", 0)
            sections.append(
                Section(
                    "Spread Analysis",
                    f"Low Bid: ${low / 100:,.2f}\n"
                    f"High Bid: ${high / 100:,.2f}\n"
                    f"Spread: {spread.get('spread_percent', 0):.1f}%\n\n"
                    f"{spread.get('notes', '')}",
                )
            )

        # Bidder comparison table
        tables = []
        bidders = data.get("bidders", [])
        if bidders:
            rows = []
            for b in bidders:
                base = b.get("base_bid_cents", 0)
                adj = b.get("adjusted_bid_cents", 0)
                rows.append([
                    str(b.get("company", "")),
                    f"${base / 100:,.2f}" if base else "N/A",
                    f"${adj / 100:,.2f}" if adj else "N/A",
                    str(len(b.get("exclusions", []))),
                    str(len(b.get("qualifications", []))),
                ])
            tables.append(
                TableData(
                    headers=["Bidder", "Base Bid", "Adjusted Bid", "Exclusions", "Qualifications"],
                    rows=rows,
                    title="Bid Summary",
                )
            )

        content = DocumentContent(
            title=f"Bid Comparison — {validated['trade'].title()}",
            date=date.today().isoformat(),
            header_fields={
                "Trade": validated["trade"].title(),
                "Number of Bids": str(len(bidders)),
                "Date": date.today().isoformat(),
            },
            sections=sections,
            tables=tables,
        )

        return self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

    def _create_xlsx(self, data: dict, project_info: ProjectInfo) -> Path:
        """Create XLSX bid matrix workbook."""
        # Bid summary sheet
        bid_rows = []
        for b in data.get("bidders", []):
            base = b.get("base_bid_cents", 0)
            adj = b.get("adjusted_bid_cents", 0)
            bid_rows.append([
                str(b.get("company", "")),
                f"${base / 100:,.2f}" if base else "N/A",
                f"${adj / 100:,.2f}" if adj else "N/A",
                "; ".join(b.get("exclusions", [])),
                "; ".join(b.get("qualifications", [])),
                "; ".join(b.get("strengths", [])),
                "; ".join(b.get("concerns", [])),
            ])

        # Scope gaps sheet
        gap_rows = []
        for gap in data.get("scope_gaps", []):
            est = gap.get("estimated_cost_cents", 0)
            gap_rows.append([
                str(gap.get("item", "")),
                ", ".join(gap.get("included_by", [])),
                ", ".join(gap.get("excluded_by", [])),
                f"${est / 100:,.2f}" if est else "N/A",
            ])

        sheets = {
            "Bid Summary": TableData(
                headers=["Bidder", "Base Bid", "Adjusted Bid", "Exclusions", "Qualifications", "Strengths", "Concerns"],
                rows=bid_rows,
            ),
            "Scope Gaps": TableData(
                headers=["Item", "Included By", "Excluded By", "Est. Cost"],
                rows=gap_rows,
            ),
        }

        spreadsheet = SpreadsheetContent(title="Bid Comparison", sheets=sheets)
        return self.formatter.create_xlsx(
            spreadsheet, project_info, skill_name=self.skill_name
        )

    def _persist_comparison(
        self, validated: dict, data: dict, docx_path: Path, xlsx_path: Path
    ) -> None:
        """Persist bid comparison to database."""
        spread = data.get("spread_analysis", {})
        rec = data.get("recommendation", {})
        bidders = data.get("bidders", [])

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO bid_comparisons "
                "(project_id, trade, comparison_name, bid_date, "
                "number_of_bidders, low_bid_cents, high_bid_cents, "
                "spread_percent, recommendation, analysis, "
                "bidder_data, document_path, excel_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated["project_id"],
                    validated["trade"],
                    f"{validated['trade'].title()} Bid Comparison",
                    date.today().isoformat(),
                    len(bidders),
                    spread.get("low_bid_cents", 0),
                    spread.get("high_bid_cents", 0),
                    spread.get("spread_percent", 0),
                    rec.get("reasoning", ""),
                    data.get("overall_assessment", ""),
                    json.dumps(bidders),
                    str(docx_path),
                    str(xlsx_path),
                ),
            )
