# Prompt 03: Phase 2 Skills — Core Operations
## 6 Skills for Document Analysis, Financial Tracking, and Compliance

> **Target**: Build 6 Phase 2 skills that analyze uploaded documents (PDFs, spreadsheets) and generate professional outputs.
> **Estimated time**: 10-14 development days across Weeks 5-8
> **Prerequisites**: Foundation + Phase 1 fully operational. Document parser handling PDFs and XLSX reliably.
> **Key difference from Phase 1**: These skills accept **file uploads** as input, not just text. They analyze existing construction documents and produce structured assessments.

---

## Testing Requirements (ALL PHASE 2 SKILLS)

Phase 2 skills are more complex — they accept file inputs. Each skill test file must include:

1. **All 9 standard tests from Phase 1** (validate, prompt, format, execute, CLI)
2. **`test_parse_input_document`** — Skill correctly extracts data from a sample PDF/XLSX
3. **`test_large_document_handling`** — Documents >50 pages are truncated gracefully, not crashed
4. **`test_malformed_input_file`** — Corrupt/password-protected file returns user-friendly error
5. **`test_output_accuracy_smoke`** — With known mock API response, output contains expected analysis sections
6. **`test_multiple_file_inputs`** — Skills accepting multiple files handle 2-5 files correctly (Bid Comparison)

Create test fixture files:
- `tests/fixtures/sample_estimate.xlsx` — Simple 3-sheet estimate workbook (10 line items)
- `tests/fixtures/sample_bid.pdf` — 2-page bid proposal with pricing table
- `tests/fixtures/sample_schedule.pdf` — Basic CPM schedule printout
- `tests/fixtures/sample_subcontract.pdf` — 5-page subcontract agreement
- `tests/fixtures/sample_insurance_cert.pdf` — Standard ACORD certificate
- `tests/fixtures/sample_submittal.pdf` — Product submittal with spec reference

Generate these fixtures programmatically in `tests/fixtures/generate_fixtures.py` using python-docx, openpyxl, and reportlab (or FPDF) so they're reproducible and contain known content for assertion.

---

## Skill #7: Estimate Reviewer / Benchmarker

### Purpose
Analyze a construction cost estimate (XLSX) against historical data and industry benchmarks. Flag line items that are unusually high, low, or missing. This is the estimating chief's second set of eyes.

### CLI Interface
```
kruppai estimate-review --file estimate_medical_office.xlsx --project KRUPP-2026-003 --type healthcare
```

**Options:**
- `--file` / `-f` (required): Path to estimate spreadsheet (.xlsx)
- `--project` / `-p` (optional): Project code for context
- `--type` (optional): Project type for benchmark selection (commercial, healthcare, education, industrial)
- `--sqft` (optional): Total square footage for unit cost calculation
- `--region` (optional): Geographic region for cost adjustment

### Input Processing
```python
def parse_estimate(file_path: Path) -> EstimateData:
    """
    Parse an Excel estimate into structured line items.

    Expected format (flexible — handle common variations):
    - Column headers in row 1-5 (search for header row)
    - Look for columns: CSI Code, Description, Quantity, Unit, Unit Cost, Extended Cost
    - Handle subtotals, section headers, blank rows
    - Multiple sheets: "Summary" sheet if present, otherwise first sheet with data

    Returns:
        EstimateData with:
        - line_items: [{csi_code, description, quantity, unit, unit_cost, extended, category}]
        - total: sum of extended costs
        - categories: {division: subtotal} grouped by CSI division
    """
```

### System Prompt Template
```
You are a senior construction cost estimator reviewing a cost estimate for {company_name}.
You have decades of experience with {project_type} construction in the {region} region.

PROJECT CONTEXT:
{project_context_if_available}

HISTORICAL COST DATA FROM COMPLETED PROJECTS:
{historical_cost_data_by_csi_code}

ESTIMATE BEING REVIEWED:
Total Estimated Cost: ${total_estimate}
Square Footage: {sqft} ({cost_per_sf})
Number of Line Items: {line_item_count}

LINE ITEMS:
{formatted_line_item_table}

INSTRUCTIONS:
1. COMPLETENESS CHECK:
   - Are all major CSI divisions represented for a {project_type} project?
   - Flag any MISSING divisions that would typically be included.
   - Note any line items that seem unusually detailed or vague.

2. COST BENCHMARKING:
   - Compare each major category to historical data (if available) and industry norms.
   - Flag items that are >20% above or below benchmark as [HIGH] or [LOW].
   - Calculate $/SF for major categories and compare to industry ranges.

3. RISK ASSESSMENT:
   For each flagged item, explain:
   - What the benchmark range is
   - Why this might be high/low (legitimate reasons vs. potential error)
   - Risk level: 'low', 'medium', 'high'

4. RECOMMENDATIONS:
   - Top 5 items to investigate further
   - Overall confidence level in the estimate
   - Suggested contingency percentage based on estimate quality

5. OUTPUT FORMAT:
   Return JSON:
   {
     "overall_assessment": "summary paragraph",
     "confidence_level": "high|medium|low",
     "total_estimate_cents": 0,
     "benchmark_total_cents": 0,
     "variance_percent": 0.0,
     "recommended_contingency_percent": 0.0,
     "missing_divisions": [{"csi_code": "", "description": "", "typical_range": ""}],
     "flagged_items": [
       {
         "csi_code": "", "description": "", "estimated_cents": 0,
         "benchmark_cents": 0, "variance_percent": 0.0,
         "flag": "HIGH|LOW", "risk": "low|medium|high",
         "explanation": ""
       }
     ],
     "category_analysis": [
       {"division": "", "estimated_cents": 0, "per_sf_cents": 0, "benchmark_per_sf_cents": 0, "notes": ""}
     ],
     "recommendations": ["rec1", "rec2"]
   }
```

**Model**: `claude-opus-4-6` — This skill requires precision. Financial errors have real consequences.

### Historical Data Integration
Query `cost_history` table for the same CSI codes from completed projects:
```sql
SELECT csi_code, csi_description,
       AVG(unit_cost_cents) as avg_unit_cost,
       MIN(unit_cost_cents) as min_unit_cost,
       MAX(unit_cost_cents) as max_unit_cost,
       COUNT(*) as data_points
FROM cost_history
WHERE year >= strftime('%Y', 'now') - 3
GROUP BY csi_code
```

### Output Formatting (DOCX + XLSX)
**DOCX**: Executive summary with risk flags, category analysis table, detailed findings
**XLSX**: Sheet 1: "Line Item Analysis" with color-coded flags. Sheet 2: "Benchmark Comparison" with formulas. Sheet 3: "Missing Items Checklist"

---

## Skill #8: Bid Comparison Analyzer

### Purpose
Analyze multiple bid proposals for the same trade scope and produce a structured comparison matrix. On bid day, PMs get 3-8 bids per trade and need to compare them fast.

### CLI Interface
```
kruppai bid-compare --project KRUPP-2026-003 --trade "Electrical" --bids bid_abc_electric.pdf bid_pacific_electric.pdf bid_valley_electric.pdf
```

**Options:**
- `--project` / `-p` (required): Project code
- `--trade` / `-t` (required): Trade being bid (e.g., "Electrical")
- `--bids` (required): Paths to 2-8 bid PDF files (multiple values)
- `--budget` (optional): Budget amount for this trade (for over/under comparison)

### Input Processing
Parse each PDF to extract:
- Bidder company name
- Base bid amount
- Alternates (numbered, with amounts)
- Qualifications and exclusions
- Bid bond included (yes/no)
- Addenda acknowledged

```python
def parse_bid_proposals(bid_files: list[Path]) -> list[BidData]:
    """
    Extract structured bid data from PDF proposals.
    Each PDF is parsed independently, then results are merged for comparison.
    Uses Claude to extract structured data from unstructured bid letters.
    """
```

### System Prompt Template (Two-stage)

**Stage 1: Extract data from each bid** (called once per bid PDF)
```
You are extracting structured bid data from a construction bid proposal.

BID DOCUMENT TEXT:
{parsed_pdf_text}

Extract the following information. If a field is not found, return null.
Return JSON:
{
  "company_name": "",
  "base_bid_cents": 0,
  "alternates": [{"number": 1, "description": "", "amount_cents": 0, "add_or_deduct": "add"}],
  "qualifications": ["qual1", "qual2"],
  "exclusions": ["excl1", "excl2"],
  "bid_bond": true|false,
  "addenda_acknowledged": [1, 2, 3],
  "completion_days": null,
  "payment_terms": "",
  "unit_prices": [{"item": "", "unit": "", "price_cents": 0}]
}
```

**Stage 2: Analyze and compare all bids**
```
You are a construction bid analyst for {company_name}.

TRADE: {trade}
BUDGET: ${budget_if_provided}
NUMBER OF BIDS: {bid_count}

BID SUMMARY:
{formatted_bid_comparison_table}

DETAILED BID DATA:
{all_bids_json}

INSTRUCTIONS:
1. BID SPREAD ANALYSIS:
   - Low bid, high bid, and spread percentage
   - Average bid (excluding outliers)
   - How each bid compares to budget (if provided)

2. QUALIFICATION/EXCLUSION ANALYSIS:
   - Items excluded by some bidders but included by others (creates apples-to-oranges comparison)
   - Qualifications that shift risk to the GC
   - Missing addenda acknowledgments

3. ALTERNATE ANALYSIS:
   - Compare alternate pricing across bidders
   - Best value combinations

4. RECOMMENDATION:
   - Recommended bidder with rationale
   - Items to negotiate
   - Risk flags

5. OUTPUT FORMAT:
   Return JSON:
   {
     "trade": "",
     "bid_date": "",
     "low_bid": {"company": "", "amount_cents": 0},
     "high_bid": {"company": "", "amount_cents": 0},
     "spread_percent": 0.0,
     "recommendation": {"company": "", "rationale": ""},
     "comparison_matrix": [
       {"company": "", "base_bid_cents": 0, "adjusted_bid_cents": 0, "exclusion_risk": "low|medium|high", "notes": ""}
     ],
     "exclusion_analysis": [{"item": "", "included_by": [], "excluded_by": [], "estimated_value_cents": 0}],
     "alternate_comparison": [{"alternate": "", "prices": [{"company": "", "amount_cents": 0}]}],
     "risk_flags": ["flag1"],
     "negotiation_items": ["item1"]
   }
```

### Output Formatting (DOCX + XLSX)
**DOCX**: Executive summary, recommendation, bid spread analysis, risk flags
**XLSX**: Sheet 1: "Bid Comparison Matrix" (the money table). Sheet 2: "Exclusion Analysis". Sheet 3: "Alternates". Auto-formatted, color-coded low/high.

---

## Skill #9: Change Order Builder

### Purpose
Transform a PM's rough description of changed work into a formal change order document with cost breakdown, schedule impact, and proper contractual language.

### CLI Interface
```
kruppai change-order --project KRUPP-2026-003 --description "Owner wants to add a generator for the server room. Not in original scope. Need new 200KW generator, concrete pad, electrical connections, and transfer switch. ABC Electric quoted $45,000 for electrical, Pacific Mechanical quoted $8,000 for gas piping." --reason owner_change
```

**Options:**
- `--project` / `-p` (required): Project code
- `--description` / `-d` (required): Description of changed work
- `--reason` / `-r` (required): owner_change / design_error / unforeseen_condition / code_requirement / value_engineering
- `--sub-quotes` (optional): Paths to subcontractor quote files
- `--schedule-impact` (optional): Estimated schedule impact in days
- `--markup` (optional): Override default markup percentage

### System Prompt Template
```
You are a construction change order writer for {company_name}.

PROJECT CONTEXT:
{project_context_with_contract_info}

EXISTING CHANGE ORDERS:
{existing_co_summary}

CHANGE ORDER REASON: {reason_type}

INSTRUCTIONS:
1. Write a formal change order description that:
   - Clearly describes the changed work
   - References the reason (owner request, design error, etc.)
   - States what was in the original scope vs. what is being added/changed
   - Uses contractual language appropriate for {contract_type} contracts

2. COST BREAKDOWN:
   - Organize by sub quotes provided
   - Add GC general conditions if applicable
   - Apply standard markup: {markup_percent}% (or per contract terms)
   - Calculate total with markup
   - Note: GC overhead/profit markup typically applies to sub costs

3. SCHEDULE IMPACT:
   - Estimate schedule impact based on scope description
   - Differentiate between critical path impact and float consumption
   - Note: Some COs have cost impact but no schedule impact

4. OUTPUT FORMAT:
   Return JSON:
   {
     "title": "Brief CO title",
     "description": "Formal change order description",
     "reason": "owner_change|design_error|unforeseen_condition|code_requirement|value_engineering",
     "cost_breakdown": [
       {"item": "", "subcontractor": "", "amount_cents": 0, "notes": ""}
     ],
     "subtotal_cents": 0,
     "markup_percent": 0.0,
     "markup_cents": 0,
     "total_cents": 0,
     "schedule_impact_days": 0,
     "schedule_impact_notes": "",
     "contract_reference": "Relevant contract section for this type of change",
     "supporting_docs": ["list of referenced documents"]
   }
```

### Output Formatting (DOCX)
- **Formal CO form**: CO #, Date, Project, From/To
- **Description section**
- **Cost table**: Item | Subcontractor | Amount, with subtotal, markup, total
- **Schedule impact section**
- **Signature lines**: GC, Owner, Architect

### Database Persistence
Insert into `change_orders` table. Auto-increment co_number per project. Update `current_contract_cents` on the project if approved.

---

## Skill #10: Schedule Variance Analyzer

### Purpose
Analyze a project schedule (uploaded as PDF or XLSX) against the baseline and produce a variance report highlighting critical path impacts, at-risk activities, and recovery recommendations.

### CLI Interface
```
kruppai schedule-analysis --project KRUPP-2026-003 --file current_schedule_feb2026.pdf --baseline-completion 2026-09-15
```

**Options:**
- `--project` / `-p` (required): Project code
- `--file` / `-f` (required): Current schedule file (PDF or XLSX)
- `--baseline-completion` (optional): Original completion date for variance calculation
- `--critical-activities` (optional): Path to list of critical activities to track

### System Prompt Template
```
You are a construction scheduling expert analyzing a project schedule for {company_name}.

PROJECT CONTEXT:
{project_context_with_schedule_dates}

SCHEDULE DATA:
{parsed_schedule_content}

BASELINE COMPLETION: {baseline_date}
CURRENT PROJECTED COMPLETION: {if_available}
CONTRACT COMPLETION: {substantial_completion_date}

INSTRUCTIONS:
1. OVERALL STATUS:
   - Is the project ahead, on track, or behind schedule?
   - What is the projected completion date vs. baseline?
   - Total variance in calendar days

2. CRITICAL PATH ANALYSIS:
   - Identify activities on or near the critical path
   - Flag any critical activities that are behind schedule
   - Note float consumption on near-critical activities

3. AT-RISK ACTIVITIES:
   - Activities with negative float
   - Activities with less than 5 days of float
   - Activities with long durations remaining (concentration risk)

4. TRADE/SUBCONTRACTOR IMPACT:
   - Which trades are causing delays?
   - Which trades are impacted by delays from others?

5. RECOVERY RECOMMENDATIONS:
   - Specific, actionable steps to recover schedule
   - Cost implications of acceleration (overtime, additional crews)
   - Realistic vs. optimistic recovery timeline

6. OUTPUT FORMAT:
   Return JSON:
   {
     "overall_status": "ahead|on_track|behind",
     "baseline_completion": "",
     "projected_completion": "",
     "variance_days": 0,
     "critical_path_items": [
       {"activity": "", "planned_finish": "", "projected_finish": "", "variance_days": 0, "responsible_trade": ""}
     ],
     "at_risk_items": [
       {"activity": "", "remaining_float_days": 0, "risk_level": "high|medium", "notes": ""}
     ],
     "trade_impacts": [
       {"trade": "", "status": "on_track|behind|ahead", "notes": ""}
     ],
     "recovery_recommendations": [
       {"action": "", "estimated_recovery_days": 0, "estimated_cost": "", "priority": "high|medium|low"}
     ],
     "summary": "Executive summary paragraph"
   }
```

### Output Formatting (DOCX)
- **Executive summary** with status indicator (green/yellow/red)
- **Variance table**: Activity | Planned | Projected | Variance | Status
- **Risk matrix**: At-risk items with float and impact
- **Recommendations section** with priority ranking

---

## Skill #11: Submittal Tracker

### Purpose
Two modes: (1) Parse a submittal log export and identify overdue/missing submittals, or (2) Generate a submittal cover sheet for a specific submittal package.

### CLI Interface
```
# Mode 1: Analyze submittal log
kruppai submittal-tracker --project KRUPP-2026-003 --log submittal_log_export.xlsx --mode analyze

# Mode 2: Generate cover sheet
kruppai submittal-tracker --project KRUPP-2026-003 --mode cover --spec-section "09.30.00" --title "Ceramic Tile" --sub "Pacific Tile & Stone"
```

**Options:**
- `--project` / `-p` (required): Project code
- `--mode` / `-m` (required): analyze / cover
- `--log` (required for analyze): Path to submittal log XLSX
- `--spec-section` (required for cover): Spec section number
- `--title` (required for cover): Submittal title
- `--sub` (optional for cover): Submitting subcontractor

### Analyze Mode Prompt
```
You are analyzing a construction submittal log for {company_name}.

PROJECT CONTEXT:
{project_context}

SUBMITTAL LOG DATA:
{parsed_submittal_log_table}

TODAY'S DATE: {today}

INSTRUCTIONS:
1. OVERDUE ANALYSIS:
   - Identify submittals past their required date that haven't been submitted
   - Identify submittals submitted but not returned within review period (14 days default)
   - Flag critical path submittals with urgency

2. STATUS SUMMARY:
   - Total submittals: X
   - Approved: X
   - Approved as Noted: X
   - Pending Review: X
   - Revise & Resubmit: X
   - Not Yet Submitted: X
   - Overdue: X

3. LEAD TIME RISKS:
   - Submittals for items with long lead times that haven't been submitted
   - Items where approval + lead time exceeds available schedule float

4. OUTPUT FORMAT:
   Return JSON with status_summary, overdue_items, lead_time_risks, recommendations
```

### Cover Sheet Mode Prompt
```
Generate a professional submittal cover sheet for:
Spec Section: {spec_section}
Title: {title}
Subcontractor: {sub_name}
Project: {project_name}

Include standard fields: submittal number ({auto_generated}), date, copies provided,
review action requested, remarks field, approval signature block.
```

### Output Formatting
- **Analyze mode**: DOCX report + XLSX with color-coded status
- **Cover mode**: Single-page DOCX cover sheet (print-ready)

---

## Skill #12: Contract & Insurance Checker

### Purpose
Review a subcontract or insurance certificate against standard requirements and flag gaps, non-standard clauses, missing coverages, and compliance issues.

### CLI Interface
```
# Check a subcontract
kruppai contract-check --project KRUPP-2026-003 --file subcontract_abc_electric.pdf --type subcontract

# Check an insurance certificate
kruppai contract-check --project KRUPP-2026-003 --file acord_abc_electric.pdf --type insurance
```

**Options:**
- `--project` / `-p` (optional): Project code for context
- `--file` / `-f` (required): Path to document (PDF)
- `--type` / `-t` (required): subcontract / insurance / bond

### Subcontract Review Prompt
```
You are a construction contract reviewer for {company_name}. You are reviewing a subcontract agreement.

COMPANY STANDARDS:
- Standard subcontract provisions Krupp requires are listed below.
- Flag any deviation from these standards.

STANDARD REQUIRED PROVISIONS:
1. Indemnification: Broad form indemnification of GC and Owner
2. Insurance: Must carry GL, Auto, Workers Comp, Umbrella per project requirements
3. Payment terms: Pay-when-paid provisions
4. Change order process: Written CO required before performing changed work
5. Schedule: Sub bound to project schedule, liquidated damages flow-down
6. Safety: Compliance with site safety plan, OSHA standards
7. Warranty: Minimum 1-year warranty from substantial completion
8. Dispute resolution: Mediation before arbitration/litigation
9. Termination: GC right to terminate for cause and convenience
10. Retainage: Per project requirements (typically 10%)

DOCUMENT TEXT:
{parsed_contract_text}

INSTRUCTIONS:
1. CLAUSE-BY-CLAUSE REVIEW:
   - For each standard provision above, determine if it's present, missing, or modified.
   - For modified provisions, explain the deviation and assess risk.

2. NON-STANDARD CLAUSES:
   - Flag any unusual provisions not typically found in construction subcontracts.
   - Assess each for risk to the GC.

3. FINANCIAL TERMS:
   - Contract value, payment terms, retainage
   - Are there cost escalation provisions? Material price clauses?

4. RISK ASSESSMENT:
   - Overall risk level: low/medium/high/critical
   - Top 3 items requiring negotiation

5. OUTPUT FORMAT:
   Return JSON:
   {
     "document_type": "subcontract",
     "subcontractor": "",
     "contract_value_cents": 0,
     "risk_level": "low|medium|high|critical",
     "compliance_score": 85,
     "clause_review": [
       {"provision": "", "status": "present|missing|modified", "details": "", "risk": "low|medium|high"}
     ],
     "non_standard_clauses": [
       {"clause": "", "description": "", "risk": "", "recommendation": ""}
     ],
     "financial_terms": {"contract_value": "", "payment_terms": "", "retainage": "", "escalation": ""},
     "top_negotiation_items": ["item1", "item2", "item3"],
     "summary": "Executive summary"
   }
```

### Insurance Review Prompt
```
You are reviewing a Certificate of Insurance (ACORD form) for compliance with project requirements.

REQUIRED COVERAGES FOR THIS PROJECT:
- Commercial General Liability: $1,000,000 per occurrence / $2,000,000 aggregate
- Automobile Liability: $1,000,000 combined single limit
- Workers Compensation: Statutory limits
- Employers Liability: $1,000,000
- Umbrella/Excess: $5,000,000
- Additional Insured: {company_name} and {owner_name} must be listed
- Certificate Holder: {company_name}
- Waiver of Subrogation: Required for GL, Auto, WC

CERTIFICATE TEXT:
{parsed_cert_text}

INSTRUCTIONS:
1. COVERAGE VERIFICATION:
   For each required coverage, verify:
   - Coverage present (yes/no)
   - Limits meet or exceed requirements
   - Policy dates (not expired)

2. ADDITIONAL REQUIREMENTS:
   - Additional insured endorsement present?
   - Waiver of subrogation present?
   - Certificate holder correctly listed?
   - 30-day notice of cancellation?

3. GAPS:
   - List any missing or insufficient coverages
   - List expired policies

4. OUTPUT FORMAT:
   Return JSON with coverage_review, gaps, expiring_soon, compliance_score
```

**Model**: `claude-opus-4-6` — Contract review demands the highest accuracy. Legal exposure is real.

### Output Formatting (DOCX)
- **Cover page**: Document type, reviewer, date
- **Compliance scorecard**: Visual status table (green/yellow/red per provision)
- **Detailed findings**: Each provision with status and recommendation
- **Risk summary**: Top items requiring action
- **Signature line**: For GC reviewer acknowledgment

---

## Phase 2 Integration Test Suite

Create `tests/test_integration/test_phase2_workflow.py`:

```python
class TestPhase2Workflow:
    def test_estimate_review_with_historical_data(self, seeded_db_with_cost_history, mock_api_client):
        """Estimate review pulls historical cost data for benchmarking."""

    def test_bid_comparison_three_bids(self, seeded_db, mock_api_client, sample_bid_pdfs):
        """Three bid PDFs analyzed and compared correctly."""

    def test_change_order_auto_numbering(self, seeded_db, mock_api_client):
        """Sequential CO numbering per project."""

    def test_change_order_updates_contract_value(self, seeded_db, mock_api_client):
        """Approved CO updates project.current_contract_cents."""

    def test_submittal_tracker_overdue_detection(self, seeded_db, mock_api_client, sample_submittal_log):
        """Correctly identifies overdue submittals from XLSX log."""

    def test_contract_check_identifies_missing_provisions(self, mock_api_client, sample_subcontract_pdf):
        """Flags missing indemnification clause in sample contract."""

    def test_insurance_check_coverage_gaps(self, mock_api_client, sample_insurance_cert):
        """Identifies insufficient GL limits in sample cert."""
```

---

## Verification Checklist

1. `pytest tests/test_skills/test_estimate_reviewer.py -v` — Passes
2. `pytest tests/test_skills/test_bid_comparison.py -v` — Passes
3. `pytest tests/test_skills/test_change_order.py -v` — Passes
4. `pytest tests/test_skills/test_schedule_variance.py -v` — Passes
5. `pytest tests/test_skills/test_submittal_tracker.py -v` — Passes (both modes)
6. `pytest tests/test_skills/test_contract_checker.py -v` — Passes (both types)
7. `pytest tests/test_integration/test_phase2_workflow.py -v` — Passes
8. All 6 CLI commands respond to `--help`
9. DOCX outputs open correctly in Word
10. XLSX outputs open correctly in Excel with formatting intact
11. API cost tracking shows Opus usage for skills #7 and #12
12. Test fixtures generate reproducible sample documents
